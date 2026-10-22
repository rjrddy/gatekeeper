import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";
type Quarantine = {
  test: string;
  environment: string;
  mixed_commits: number;
  expires_at: number;
};
type Finding = {
  address: string;
  reasons: string[];
  affected: string[];
  affected_count: number;
};
type Analysis = {
  quarantine: Quarantine[];
  clusters: { group: number; label: string; log: string }[];
  plans: { blocked: boolean; findings: Finding[]; comment_preview?: string }[];
};
type Report = {
  id: number;
  kind: string;
  body: Analysis | Supply;
  created: number;
};
type Supply = {
  approved: boolean;
  blocked?: string[];
  artifact_sha256?: string;
  error?: string;
  components?: number;
  vulnerability_matches?: number;
  exit_code?: number;
};
type State = {
  runs: {
    repo: string;
    id: string;
    attempt: number;
    sha: string;
    status: string;
    conclusion: string | null;
  }[];
  reports: Report[];
  audit: { id: number; kind: string; created: number; body: string }[];
  rollout: {
    epoch: number;
    state: string;
    active: string;
    stable: string;
    candidate: string | null;
    last_result: string | null;
  };
};
function App() {
  const [ready, setReady] = useState(false),
    [password, setPassword] = useState(""),
    [csrf, setCsrf] = useState(""),
    [state, setState] = useState<State | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [tab, setTab] = useState("Release"),
    [probe, setProbe] = useState<string>(""),
    [search, setSearch] = useState("");
  async function load() {
    try {
      const res = await fetch("/api/state");
      if (res.status === 401) {
        setReady(false);
        return;
      }
      if (!res.ok) throw Error("Evidence service unavailable");
      setState(await res.json());
      setReady(true);
      const s = await fetch("/api/session");
      if (s.ok) setCsrf((await s.json()).csrf ?? "");
    } catch (e) {
      setError(String(e));
    }
  }
  useEffect(() => {
    void load();
    const id = setInterval(() => void load(), 1500);
    return () => clearInterval(id);
  }, []);
  async function action(path: string, body?: unknown) {
    setBusy(true);
    setError("");
    try {
      const r = await fetch(path, {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
        body: JSON.stringify(body ?? {}),
      });
      const data = await r.json();
      if (!r.ok) throw Error(data.detail ?? data.error ?? "Action failed");
      await load();
      return data;
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }
  async function login(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    try {
      const r = await fetch("/api/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const body = await r.json();
      if (!r.ok) throw Error(body.detail ?? "Sign in failed");
      setCsrf(body.csrf);
      setPassword("");
      void load();
    } catch (e) {
      setError(String(e));
    }
  }
  const analysis = state?.reports.find((r) => r.kind === "analysis")?.body as
    | Analysis
    | undefined;
  const supply = state?.reports.find((r) => r.kind === "supply")?.body as
    | Supply
    | undefined;
  const publicAnalysis = state?.reports.find(
    (r) => r.kind === "public-analysis",
  )?.body as Analysis | undefined;
  const clusters = Array.from(
    new Set(analysis?.clusters.map((c) => c.group) ?? []),
  );
  async function routeProbe() {
    try {
      const r = await fetch("/demo/value?x=7");
      const body = await r.json();
      if (!r.ok) throw Error(body.detail);
      setProbe(
        JSON.stringify(body) +
          " · upstream " +
          r.headers.get("X-Gatekeeper-Upstream"),
      );
    } catch (e) {
      setError(String(e));
    }
  }
  return (
    <>
      <header>
        <a className="brand" href="/">
          ⌘ GATEKEEPER
        </a>
        <span className="headerlabel">RELEASE EVIDENCE / OPERATIONS</span>
        {ready && (
          <button
            className="secondary"
            onClick={() =>
              void action("/api/logout").then(() => setReady(false))
            }
          >
            Sign out
          </button>
        )}
        <a href="https://github.com/rjrddy/gatekeeper">Source ↗</a>
      </header>
      <main>
        <div className="heading">
          <div>
            <p className="eyebrow">A DECISION NEEDS EVIDENCE.</p>
            <h1>
              Trust the release.
              <br />
              Keep the reasons.
            </h1>
            <p className="intro">
              CI signals, infrastructure changes and signed artifacts, joined to
              a real canary route.
            </p>
          </div>
          <span className={ready ? "badge" : "badge neutral"}>
            {ready ? "● Evidence service connected" : "○ Operator sign-in"}
          </span>
        </div>
        {error && (
          <div className="error" role="alert">
            {error}
          </div>
        )}
        {!ready ? (
          <form className="panel login" onSubmit={login}>
            <h2>Open the operations console</h2>
            <p className="muted">
              Use the operator password from your ignored .env. The demo uses
              synthetic scenarios and public CI evidence.
            </p>
            <label>
              Operator password
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                autoComplete="current-password"
                required
              />
            </label>
            <button>Sign in →</button>
          </form>
        ) : (
          <>
            <nav className="tabs">
              {["Release", "CI signals", "Infrastructure", "Audit trail"].map(
                (t) => (
                  <button
                    key={t}
                    onClick={() => setTab(t)}
                    className={tab === t ? "selected" : ""}
                  >
                    {t}
                  </button>
                ),
              )}
            </nav>
            <div className="stats">
              {[
                [state?.rollout.state ?? "unknown", "Rollout state"],
                [state?.rollout.active ?? "unknown", "Actual proxy route"],
                [analysis?.quarantine.length ?? "—", "Quarantine proposals"],
                [
                  supply
                    ? supply.approved
                      ? "Allowed"
                      : "Blocked"
                    : "Not checked",
                  "Artifact policy",
                ],
              ].map(([v, k]) => (
                <div key={String(k)}>
                  <strong>{v}</strong>
                  <span>{k}</span>
                </div>
              ))}
            </div>
            {tab === "Release" && (
              <div className="grid">
                <section className="panel">
                  <div className="sectiontitle">
                    <h2>Canary controller</h2>
                    <span className="mono">epoch {state?.rollout.epoch}</span>
                  </div>
                  <p className="muted">
                    These actions switch an actual local HTTP proxy between
                    synthetic upstream services. A failed comparison routes new
                    requests back to the last stable version.
                  </p>
                  <div className="route">
                    <span>Browser / API client</span>
                    <i>→</i>
                    <span>Persistent proxy</span>
                    <i>→</i>
                    <b>{state?.rollout.active}</b>
                  </div>
                  <div className="actions">
                    <button
                      disabled={busy || state?.rollout.state === "probing"}
                      onClick={() =>
                        void action("/api/canary", {
                          candidate: "candidate-bad",
                          expected_epoch: state?.rollout.epoch,
                        })
                      }
                    >
                      Test bad candidate
                    </button>
                    <button
                      className="secondary"
                      disabled={busy || state?.rollout.state === "probing"}
                      onClick={() =>
                        void action("/api/canary", {
                          candidate: "candidate-good",
                          expected_epoch: state?.rollout.epoch,
                        })
                      }
                    >
                      Test good candidate
                    </button>
                    <button
                      className="secondary"
                      disabled={busy || state?.rollout.state === "probing"}
                      onClick={() =>
                        void action("/api/canary", {
                          candidate: "candidate-slow",
                          expected_epoch: state?.rollout.epoch,
                        })
                      }
                    >
                      Inject timeout
                    </button>
                  </div>
                  <div className="result">
                    <p className="eyebrow">ACTUAL ROUTED RESPONSE</p>
                    <button
                      className="secondary"
                      onClick={() => void routeProbe()}
                    >
                      Probe x = 7
                    </button>
                    <pre>
                      {probe ||
                        "Send a request to inspect the routed response."}
                    </pre>
                  </div>
                  {state?.rollout.last_result && (
                    <div className="result">
                      <p className="eyebrow">CONTROLLER EVIDENCE</p>
                      <pre>
                        {JSON.stringify(
                          JSON.parse(state.rollout.last_result),
                          null,
                          2,
                        )}
                      </pre>
                    </div>
                  )}
                </section>
                <section className="panel">
                  <div className="sectiontitle">
                    <h2>Supply-chain gate</h2>
                    <span className="badge neutral">Local trusted key</span>
                  </div>
                  <p className="muted">
                    Rust checks Ed25519 signatures, artifact/SBOM/scan digests,
                    commit binding, expiry and vulnerability severity. A valid
                    signature cannot waive a blocking finding.
                  </p>
                  <button
                    disabled={busy}
                    onClick={() => void action("/api/evidence/verify")}
                  >
                    Verify signed evidence
                  </button>
                  {supply ? (
                    <>
                      <div
                        className={
                          supply.approved ? "verdict pass" : "verdict block"
                        }
                      >
                        {supply.approved ? "POLICY ALLOWED" : "POLICY BLOCKED"}
                      </div>
                      <code className="digest">
                        {supply.artifact_sha256 ??
                          "Signature or freshness failed"}
                      </code>
                      <ul>
                        {supply.blocked?.slice(0, 8).map((b, i) => (
                          <li key={i}>{b}</li>
                        ))}
                      </ul>
                      {supply.error && <p>{supply.error}</p>}
                      <p className="muted">
                        Scanner components:{" "}
                        {supply.components ?? "not measured"} · Matches:{" "}
                        {supply.vulnerability_matches ?? "not measured"}
                      </p>
                    </>
                  ) : (
                    <div className="empty">
                      No verification stored. Run the supply-chain benchmark
                      first to prepare actual signed scanner evidence.
                    </div>
                  )}
                  <aside>
                    Local-key integrity is not transparency-log or SLSA
                    provenance. The negative fixture contains vulnerable package
                    metadata; vulnerable code is not installed.
                  </aside>
                </section>
              </div>
            )}
            {tab === "CI signals" && (
              <>
                <section className="panel">
                  <div className="sectiontitle">
                    <h2>Quarantine proposals</h2>
                    <button
                      disabled={busy}
                      onClick={() => void action("/api/demo/analyze")}
                    >
                      Analyze seeded scenarios
                    </button>
                  </div>
                  <p className="muted">
                    Mixed outcomes must share a commit and environment.
                    Proposals expire and keep scheduled runs; this is evidence
                    for review, not proof of the underlying cause.
                  </p>
                  <div className="tablewrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Test</th>
                          <th>Environment</th>
                          <th>Mixed commits</th>
                          <th>Proposal expires</th>
                        </tr>
                      </thead>
                      <tbody>
                        {analysis?.quarantine.map((q) => (
                          <tr key={q.test + q.environment}>
                            <td>{q.test}</td>
                            <td>{q.environment}</td>
                            <td>{q.mixed_commits}</td>
                            <td>
                              {new Date(q.expires_at * 1000).toLocaleString()}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {!analysis && (
                    <p className="empty">
                      Analyze the seeded scenarios to populate actual analysis
                      results.
                    </p>
                  )}
                </section>
                <section className="panel">
                  <div className="sectiontitle">
                    <h2>Public CI evidence</h2>
                    <button
                      disabled={busy}
                      onClick={() => void action("/api/public/analyze")}
                    >
                      Analyze public excerpts
                    </button>
                  </div>
                  <p className="muted">
                    Reviewed visible signatures from pytest-dev/pytest. Small
                    selected sample, not an installed GitHub App or a general
                    accuracy claim.
                  </p>
                  {publicAnalysis?.clusters.map((r, i) => (
                    <details key={i}>
                      <summary>
                        Group {r.group} · {r.label}
                      </summary>
                      <pre>{r.log}</pre>
                    </details>
                  ))}
                </section>
                <section className="panel">
                  <div className="sectiontitle">
                    <h2>Failure signatures</h2>
                    <span>{clusters.length || "No"} stored groups</span>
                  </div>
                  <label>
                    Filter log evidence
                    <input
                      value={search}
                      onChange={(e) => setSearch(e.target.value)}
                      placeholder="TimeoutError, signature…"
                    />
                  </label>
                  <p className="muted">
                    The examples below are synthetic injections. Public-source
                    evaluation is saved separately with source URLs and reviewed
                    labels.
                  </p>
                  <div className="clusters">
                    {clusters.map((group) => {
                      const rows =
                        analysis?.clusters.filter(
                          (c) =>
                            c.group === group &&
                            c.log.toLowerCase().includes(search.toLowerCase()),
                        ) ?? [];
                      return rows.length ? (
                        <details key={group}>
                          <summary>
                            Group {group}{" "}
                            <span>
                              {rows.length} excerpts · {rows[0].label}
                            </span>
                          </summary>
                          <pre>{rows[0].log}</pre>
                        </details>
                      ) : null;
                    })}
                  </div>
                </section>
                <section className="panel">
                  <h2>Signed webhook deliveries</h2>
                  <p className="muted">
                    Only validated workflow_run events appear here. Duplicate
                    delivery bytes do not add a second event.
                  </p>
                  <div className="tablewrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Repository</th>
                          <th>Run / attempt</th>
                          <th>Commit</th>
                          <th>Outcome</th>
                        </tr>
                      </thead>
                      <tbody>
                        {state?.runs.map((r) => (
                          <tr key={r.repo + r.id + r.attempt}>
                            <td>{r.repo}</td>
                            <td>
                              {r.id} / {r.attempt}
                            </td>
                            <td>
                              <code>{r.sha.slice(0, 12)}</code>
                            </td>
                            <td>{r.conclusion ?? r.status}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </section>
              </>
            )}
            {tab === "Infrastructure" && (
              <section className="panel">
                <div className="sectiontitle">
                  <h2>Plan review and dependency reach</h2>
                  <button
                    disabled={busy}
                    onClick={() => void action("/api/demo/analyze")}
                  >
                    Analyze seeded plans
                  </button>
                </div>
                <p className="muted">
                  AWS root-module plan fixtures. Affected resources are
                  dependency reachability, not a causal failure prediction. No
                  Terraform plan is applied.
                </p>
                {analysis?.plans
                  .filter((p) => p.blocked)
                  .flatMap((p) => p.findings)
                  .map((f, i) => (
                    <article className="finding" key={i}>
                      <div>
                        <h3>{f.address}</h3>
                        <span className="badge warning">Review required</span>
                      </div>
                      <p>{f.reasons.join(" · ")}</p>
                      <p className="muted">
                        Dependency reach: {f.affected_count} resource instances
                      </p>
                      <div className="route">
                        {f.affected.map((a) => (
                          <code key={a}>{a}</code>
                        ))}
                      </div>
                    </article>
                  ))}
                <h3>PR comment preview</h3>
                <p className="muted">
                  Reviewable Markdown only; this console never posts to a
                  repository.
                </p>
                {analysis?.plans
                  .filter((p) => p.blocked)
                  .slice(0, 1)
                  .map((p, i) => (
                    <pre key={i}>{p.comment_preview}</pre>
                  ))}
              </section>
            )}
            {tab === "Audit trail" && (
              <section className="panel">
                <h2>Committed event timeline</h2>
                <p className="muted">
                  Persisted delivery and rollout events. Temporal correlation
                  alone does not establish causality.
                </p>
                <div className="timeline">
                  {state?.audit.map((a) => (
                    <article key={a.id}>
                      <time>
                        {new Date(a.created * 1000).toLocaleTimeString()}
                      </time>
                      <div>
                        <h3>{a.kind}</h3>
                        <pre>{JSON.stringify(JSON.parse(a.body), null, 2)}</pre>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            )}
          </>
        )}
        <footer>
          <span>Public / synthetic evidence · Single-host demo</span>
          <a href="https://github.com/rjrddy/gatekeeper/blob/main/docs/DESIGN.md">
            Design and guarantees ↗
          </a>
        </footer>
      </main>
    </>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
