use anyhow::{bail, Context, Result};
use clap::{Parser, Subcommand};
use ed25519_dalek::{SigningKey, VerifyingKey};
use gatekeeper_agent::{digest, sign, verify, Claim, Envelope};
use rand::rngs::OsRng;
use std::{
    fs,
    io::{Read, Write},
    path::PathBuf,
    time::{SystemTime, UNIX_EPOCH},
};
#[derive(Parser)]
#[command(about = "Digest-bound release evidence; local trusted keys, no network signing")]
struct Args {
    #[command(subcommand)]
    command: Command,
}
#[derive(Subcommand)]
enum Command {
    Keygen {
        #[arg(long)]
        private: PathBuf,
        #[arg(long)]
        public: PathBuf,
    },
    Attest {
        #[arg(long)]
        artifact: PathBuf,
        #[arg(long)]
        sbom: PathBuf,
        #[arg(long)]
        scan: PathBuf,
        #[arg(long)]
        commit: String,
        #[arg(long)]
        key: PathBuf,
        #[arg(long, default_value_t = 3600)]
        ttl: u64,
        #[arg(long)]
        output: PathBuf,
    },
    Verify {
        #[arg(long)]
        artifact: PathBuf,
        #[arg(long)]
        sbom: PathBuf,
        #[arg(long)]
        scan: PathBuf,
        #[arg(long)]
        commit: String,
        #[arg(long)]
        attestation: PathBuf,
        #[arg(long)]
        public_key: PathBuf,
    },
}
fn bounded(path: &PathBuf) -> Result<Vec<u8>> {
    let mut data = Vec::new();
    fs::File::open(path)?
        .take(32 * 1024 * 1024 + 1)
        .read_to_end(&mut data)?;
    if data.len() > 32 * 1024 * 1024 {
        bail!("input exceeds bound")
    };
    Ok(data)
}
fn secret(path: &PathBuf) -> Result<SigningKey> {
    let data = hex::decode(String::from_utf8(bounded(path)?)?.trim())?;
    Ok(SigningKey::from_bytes(
        data.as_slice()
            .try_into()
            .context("key must contain 32 bytes")?,
    ))
}
fn run() -> Result<bool> {
    let now = SystemTime::now().duration_since(UNIX_EPOCH)?.as_secs();
    match Args::parse().command {
        Command::Keygen { private, public } => {
            if private.exists() || public.exists() {
                bail!("refusing to overwrite existing key material")
            }
            let key = SigningKey::generate(&mut OsRng);
            let mut options = fs::OpenOptions::new();
            options.write(true).create_new(true);
            #[cfg(unix)]
            {
                use std::os::unix::fs::OpenOptionsExt;
                options.mode(0o600);
            }
            let mut f = options.open(private)?;
            f.write_all(hex::encode(key.to_bytes()).as_bytes())?;
            fs::OpenOptions::new()
                .write(true)
                .create_new(true)
                .open(public)?
                .write_all(hex::encode(key.verifying_key().to_bytes()).as_bytes())?;
            println!("Generated local key; secret value not displayed");
            Ok(true)
        }
        Command::Attest {
            artifact,
            sbom,
            scan,
            commit,
            key,
            ttl,
            output,
        } => {
            if ttl == 0 || ttl > 86400 {
                bail!("TTL outside policy")
            };
            let claim = Claim {
                kind: "gatekeeper-release-v1".into(),
                commit,
                artifact_sha256: digest(&bounded(&artifact)?),
                sbom_sha256: digest(&bounded(&sbom)?),
                scan_sha256: digest(&bounded(&scan)?),
                issued: now,
                expires: now + ttl,
                policy: "high-critical-v1".into(),
            };
            fs::write(
                output,
                serde_json::to_vec_pretty(&sign(&claim, &secret(&key)?)?)?,
            )?;
            Ok(true)
        }
        Command::Verify {
            artifact,
            sbom,
            scan,
            commit,
            attestation,
            public_key,
        } => {
            let key = hex::decode(String::from_utf8(bounded(&public_key)?)?.trim())?;
            let trusted =
                VerifyingKey::from_bytes(key.as_slice().try_into().context("public key length")?)?;
            let envelope: Envelope = serde_json::from_slice(&bounded(&attestation)?)?;
            let result = verify(
                &bounded(&artifact)?,
                &bounded(&sbom)?,
                &bounded(&scan)?,
                &envelope,
                &trusted,
                &commit,
                now,
            )?;
            println!("{}", serde_json::to_string_pretty(&result)?);
            Ok(result.approved)
        }
    }
}
fn main() {
    match run() {
        Ok(true) => {}
        Ok(false) => std::process::exit(1),
        Err(e) => {
            eprintln!(
                "{}",
                serde_json::json!({"approved":false,"error":e.to_string()})
            );
            std::process::exit(2)
        }
    }
}
