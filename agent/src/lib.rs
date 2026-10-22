use anyhow::{bail, Context, Result};
use ed25519_dalek::{Signature, Signer, SigningKey, VerifyingKey};
use serde::{Deserialize, Serialize};
use serde_json::Value;
use sha2::{Digest, Sha256};

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Claim {
    pub kind: String,
    pub commit: String,
    pub artifact_sha256: String,
    pub sbom_sha256: String,
    pub scan_sha256: String,
    pub issued: u64,
    pub expires: u64,
    pub policy: String,
}
#[derive(Debug, Serialize, Deserialize)]
#[serde(deny_unknown_fields)]
pub struct Envelope {
    pub payload_hex: String,
    pub signature_hex: String,
}
#[derive(Debug, Serialize)]
pub struct Verdict {
    pub approved: bool,
    pub artifact_sha256: String,
    pub blocked: Vec<String>,
    pub components: usize,
    pub vulnerability_matches: usize,
}
pub fn digest(data: &[u8]) -> String {
    hex::encode(Sha256::digest(data))
}
pub fn sign(claim: &Claim, key: &SigningKey) -> Result<Envelope> {
    let payload = serde_json::to_vec(claim)?;
    Ok(Envelope {
        signature_hex: hex::encode(key.sign(&payload).to_bytes()),
        payload_hex: hex::encode(payload),
    })
}
pub fn verify(
    artifact: &[u8],
    sbom: &[u8],
    scan: &[u8],
    envelope: &Envelope,
    trusted: &VerifyingKey,
    commit: &str,
    now: u64,
) -> Result<Verdict> {
    let payload = hex::decode(&envelope.payload_hex).context("invalid attestation payload")?;
    let signature = Signature::from_slice(&hex::decode(&envelope.signature_hex)?)?;
    trusted
        .verify_strict(&payload, &signature)
        .context("signature does not match the trusted key")?;
    let claim: Claim = serde_json::from_slice(&payload)?;
    if claim.kind != "gatekeeper-release-v1" || claim.policy != "high-critical-v1" {
        bail!("unrecognized claim or policy")
    }
    if claim.commit != commit
        || commit.len() != 40
        || !commit.bytes().all(|b| b.is_ascii_hexdigit())
    {
        bail!("commit binding mismatch")
    }
    if claim.issued > now
        || claim.expires <= now
        || claim.expires <= claim.issued
        || claim.expires - claim.issued > 86400
    {
        bail!("attestation time bounds rejected")
    }
    if claim.artifact_sha256 != digest(artifact)
        || claim.sbom_sha256 != digest(sbom)
        || claim.scan_sha256 != digest(scan)
    {
        bail!("signed digest binding mismatch")
    }
    let bom: Value = serde_json::from_slice(sbom)?;
    let report: Value = serde_json::from_slice(scan)?;
    if bom.get("bomFormat").and_then(Value::as_str) != Some("CycloneDX") {
        bail!("CycloneDX SBOM required")
    }
    let components = bom
        .get("components")
        .and_then(Value::as_array)
        .context("missing component list")?;
    let packages: Vec<_> = components
        .iter()
        .filter(|c| c.get("type").and_then(Value::as_str) != Some("file"))
        .collect();
    if packages.is_empty() {
        bail!("empty SBOM is not approval evidence")
    }
    for component in packages {
        if component.get("name").and_then(Value::as_str).is_none()
            || component.get("version").and_then(Value::as_str).is_none()
        {
            bail!("component identity missing")
        }
    }
    if report.pointer("/descriptor/name").and_then(Value::as_str) != Some("grype") {
        bail!("recognized scanner report required")
    }
    let matches = report
        .get("matches")
        .and_then(Value::as_array)
        .context("scanner matches missing")?;
    let mut blocked = Vec::new();
    for row in matches {
        let id = row
            .pointer("/vulnerability/id")
            .and_then(Value::as_str)
            .context("vulnerability ID missing")?;
        let severity = row
            .pointer("/vulnerability/severity")
            .and_then(Value::as_str)
            .context("severity missing")?;
        match severity.to_lowercase().as_str() {
            "critical" | "high" | "unknown" | "negligible" => {
                if severity.to_lowercase() != "negligible" {
                    blocked.push(format!("{id}: {severity}"))
                }
            }
            "medium" | "low" => {}
            _ => bail!("unknown severity encoding"),
        }
    }
    Ok(Verdict {
        approved: blocked.is_empty(),
        artifact_sha256: digest(artifact),
        blocked,
        components: components.len(),
        vulnerability_matches: matches.len(),
    })
}
#[cfg(test)]
mod tests {
    use super::*;
    fn inputs() -> (Vec<u8>, Vec<u8>, Vec<u8>, Claim, SigningKey) {
        let artifact = b"synthetic build".to_vec();
        let sbom =
            br#"{"bomFormat":"CycloneDX","components":[{"name":"demo","version":"1"}]}"#.to_vec();
        let scan = br#"{"descriptor":{"name":"grype"},"matches":[]}"#.to_vec();
        let claim = Claim {
            kind: "gatekeeper-release-v1".into(),
            commit: "a".repeat(40),
            artifact_sha256: digest(&artifact),
            sbom_sha256: digest(&sbom),
            scan_sha256: digest(&scan),
            issued: 100,
            expires: 200,
            policy: "high-critical-v1".into(),
        };
        (
            artifact,
            sbom,
            scan,
            claim,
            SigningKey::from_bytes(&[7; 32]),
        )
    }
    #[test]
    fn valid_signature_and_digest_pass() {
        let (a, b, s, c, k) = inputs();
        assert!(
            verify(
                &a,
                &b,
                &s,
                &sign(&c, &k).unwrap(),
                &k.verifying_key(),
                &c.commit,
                150
            )
            .unwrap()
            .approved
        )
    }
    #[test]
    fn artifact_mutation_blocked() {
        let (_, b, s, c, k) = inputs();
        assert!(verify(
            b"tampered",
            &b,
            &s,
            &sign(&c, &k).unwrap(),
            &k.verifying_key(),
            &c.commit,
            150
        )
        .is_err())
    }
    #[test]
    fn untrusted_key_blocked() {
        let (a, b, s, c, k) = inputs();
        let other = SigningKey::from_bytes(&[9; 32]);
        assert!(verify(
            &a,
            &b,
            &s,
            &sign(&c, &k).unwrap(),
            &other.verifying_key(),
            &c.commit,
            150
        )
        .is_err())
    }
    #[test]
    fn expiry_and_future_claims_blocked() {
        let (a, b, s, c, k) = inputs();
        for now in [99, 200, 201] {
            assert!(verify(
                &a,
                &b,
                &s,
                &sign(&c, &k).unwrap(),
                &k.verifying_key(),
                &c.commit,
                now
            )
            .is_err())
        }
    }
    #[test]
    fn high_severity_cannot_be_signed_into_approval() {
        let (a, b, _, mut c, k) = inputs();
        let s=br#"{"descriptor":{"name":"grype"},"matches":[{"vulnerability":{"id":"SYNTHETIC-HIGH","severity":"High"}}]}"#;
        c.scan_sha256 = digest(s);
        assert!(
            !verify(
                &a,
                &b,
                s,
                &sign(&c, &k).unwrap(),
                &k.verifying_key(),
                &c.commit,
                150
            )
            .unwrap()
            .approved
        )
    }
    #[test]
    fn scanner_error_is_not_clean_scan() {
        let (a, b, _, mut c, k) = inputs();
        let s = b"{}";
        c.scan_sha256 = digest(s);
        assert!(verify(
            &a,
            &b,
            s,
            &sign(&c, &k).unwrap(),
            &k.verifying_key(),
            &c.commit,
            150
        )
        .is_err())
    }
    #[test]
    fn wrong_commit_is_rejected() {
        let (a, b, s, c, k) = inputs();
        assert!(verify(
            &a,
            &b,
            &s,
            &sign(&c, &k).unwrap(),
            &k.verifying_key(),
            &"b".repeat(40),
            150
        )
        .is_err())
    }
    #[test]
    fn arbitrary_byte_mutations_rejected() {
        let (a, b, s, c, k) = inputs();
        let e = sign(&c, &k).unwrap();
        for i in 0..a.len() {
            let mut changed = a.clone();
            changed[i] ^= 1;
            assert!(verify(&changed, &b, &s, &e, &k.verifying_key(), &c.commit, 150).is_err())
        }
    }
}
