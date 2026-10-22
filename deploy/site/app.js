const proof = await fetch('/proof.json').then(r => {if(!r.ok)throw Error('Evidence unavailable');return r.json()});
const {analysis:a, supply:s, canary:c, recording:r} = proof;
const node = (tag, text, cls) => {const e=document.createElement(tag);e.textContent=text;if(cls)e.className=cls;return e};
for(const [value,label,scope] of [
  [`${(a.flakes.precision*100).toFixed(0)}% / ${(a.flakes.recall*100).toFixed(0)}%`,'Flake precision / recall',`${a.flakes.truth} injected tests · ${a.flakes.observations.toLocaleString()} observations`],
  [String(s.fixtures.bad.verdict.blocked.length),'High findings blocked',`${s.fixtures.bad.verdict.vulnerability_matches} advisories in vulnerable metadata`],
  [`${a.plans.caught} / ${a.plans.risky}`,'Risky plans caught',`${a.plans.samples} fixtures · ${a.plans.false_positives} false positives`]
]){const card=node('article','');card.append(node('strong',value),node('h3',label),node('p',scope,'muted'));document.querySelector('#metrics').append(card)}
for(const row of c.canaries){const tr=node('tr','');for(const value of [row.candidate,row.state.state,row.proxy_after.upstream,JSON.stringify(row.proxy_after.body)])tr.append(node('td',value));document.querySelector('#canaries').append(tr)}
document.querySelector('#recovery').textContent=`API SIGKILL during a probe → restarted state: ${c.recovery.state.state} → proxy restored to ${c.recovery.proxy_after.upstream}.`;
document.querySelector('#supply').textContent=`The Rust gate blocked ${s.fixtures.bad.verdict.blocked.length} High findings for urllib3 ${s.fixtures.bad.version}. The ${s.fixtures.control.version} metadata control passed with ${s.fixtures.control.verdict.vulnerability_matches} scanner matches. Artifact tampering was rejected for both.`;
document.querySelector('#accuracy').textContent=`${a.synthetic_clusters.samples} synthetic logs formed ${a.synthetic_clusters.clusters} groups, with purity ${a.synthetic_clusters.purity.toFixed(2)} and pairwise recall ${a.synthetic_clusters.pairwise_recall.toFixed(2)}. Separately: ${a.public_clusters.samples} reviewed public excerpts, ${a.public_clusters.clusters} visible signature groups.`;
document.querySelector('#recording').textContent=`Actual console recording: ${Number(r.format.duration).toFixed(2)} seconds. Local services; no simulated live counters on this page.`;
