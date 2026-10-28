/* Finite project-context motion; no fake live progress. */
(()=>{
/** Finite, event-driven motion. No entrance timeline, polling, layout reads, or content delays. */
function installMotion(profile) {
    const preference = matchMedia('(prefers-reduced-motion: no-preference)');
    const running = new Set();
    const owned = new WeakMap();
    let observer;
    let events;
    let frame = 0;
    let interacted = false;
    const pending = new Map();
    const snapshots = new WeakMap();
    document.documentElement.dataset.motionProfile = profile.name;
    const play = (element, frames, duration) => {
        if (!preference.matches || !element.isConnected || document.hidden || typeof element.animate !== 'function')
            return;
        if (!(element instanceof HTMLElement) || element.matches('input,textarea,[contenteditable],.drag-handle,.note-body') || element.querySelector('input:focus,textarea:focus,[contenteditable]:focus'))
            return;
        // Stream updates never restart an in-flight effect; each owns at most one compositor animation.
        if (owned.get(element)?.playState === 'running')
            return;
        const animation = element.animate(frames, { duration, easing: 'cubic-bezier(0.16, 1, 0.3, 1)', iterations: 1, fill: 'none' });
        owned.set(element, animation);
        running.add(animation);
        const clear = () => { running.delete(animation); if (owned.get(element) === animation)
            owned.delete(element); };
        animation.onfinish = clear;
        animation.oncancel = clear;
    };
    const flush = () => {
        frame = 0;
        for (const [rule, groups] of pending)
            for (const group of groups) {
                const targets = rule.targets === ':self' ? [group] : Array.from(group.querySelectorAll(rule.targets)).slice(0, 6);
                const history = snapshots.get(group) || new Map();
                const previous = history.get(rule) || [];
                const current = [];
                for (const [index, target] of targets.entries()) {
                    const signature = (group.getAttribute('class') || '') + '|' + group.hasAttribute('open') + '|' + (target.textContent || '').slice(0, 2048) + '|' + target.getAttribute('class') + '|' + target.getAttribute('aria-pressed') + '|' + target.getAttribute('aria-current');
                    current.push(signature);
                    if (previous[index] !== signature) {
                        if (interacted)
                            play(target, rule.frames, rule.duration);
                    }
                }
                history.set(rule, current);
                snapshots.set(group, history);
            }
        pending.clear();
    };
    const enqueue = (rule, group) => {
        if (!group)
            return;
        if (!pending.has(rule))
            pending.set(rule, new Set());
        const groups = pending.get(rule);
        if (groups.size < 4)
            groups.add(group);
        if (!frame)
            frame = requestAnimationFrame(flush);
    };
    const stop = () => {
        observer?.disconnect();
        events?.abort();
        if (frame)
            cancelAnimationFrame(frame);
        frame = 0;
        pending.clear();
        for (const animation of running)
            animation.cancel();
        running.clear();
    };
    const start = () => {
        stop();
        if (!preference.matches)
            return;
        events = new AbortController();
        const signal = events.signal;
        const press = (event) => {
            if (event instanceof KeyboardEvent && !['Enter', ' '].includes(event.key))
                return;
            const source = event.target instanceof Element ? event.target : null;
            const control = source?.closest('button,summary,a.button');
            if (!control || control.matches(':disabled,[aria-disabled="true"],.drag-handle,.note-body'))
                return;
            interacted = true;
            play(control, profile.press, 160);
            if (control.matches(profile.neighbors)) {
        const neighbors = [control.previousElementSibling, control.nextElementSibling];
        for (const [index, sibling] of neighbors.entries()) {
          if (!sibling || !sibling.matches(profile.neighbors)) continue;
          const displacement = index === 0 ? -2 : 2;
          play(sibling, [{transform:'translateX(0) scaleX(1)'}, {transform:'translateX('+displacement+'px) scaleX(0.985)',offset:0.28}, {transform:'translateX(0) scaleX(1)'}], 190);
        }
      }
        };
        // Animate only once click targeting is committed; shrinking a pressed hitbox can otherwise lose edge clicks.
        document.addEventListener('click', press, { capture: true, signal });
        document.addEventListener('keydown', press, { capture: true, signal });
        for (const event of ['click', 'change'])
            document.addEventListener(event, () => { interacted = true; }, { capture: true, signal });
        observer = new MutationObserver(records => {
            for (const record of records) {
                const source = record.target instanceof Element ? record.target : record.target.parentElement;
                if (!source)
                    continue;
                for (const rule of profile.rules) {
                    enqueue(rule, source.closest(rule.watch));
                    for (const added of Array.from(record.addedNodes).slice(0, 6))
                        if (added instanceof Element) {
                            enqueue(rule, added.matches(rule.watch) ? added : added.querySelector(rule.watch));
                        }
                }
            }
        });
        observer.observe(document.body, { subtree: true, childList: true, characterData: true, attributes: true, attributeFilter: ['class', 'aria-current', 'aria-pressed', 'open'] });
    };
    preference.addEventListener('change', () => preference.matches ? start() : stop());
    window.addEventListener('pagehide', stop, { once: true });
    window.addEventListener('pageshow', event => { if (event.persisted && preference.matches)
        start(); });
    start();
}
installMotion({
    "name": "gatekeeper",
    "press": [
        {
            "transform": "scaleX(0.97)"
        },
        {
            "transform": "scaleX(1)"
        }
    ],
    "neighbors": ".fault-tabs button,.instrument-keys button",
    "rules": [
        {
            "watch": "#canaries",
            "targets": "td:last-child",
            "frames": [
                {
                    "transform": "scaleX(0.88)"
                },
                {
                    "transform": "scaleX(1)"
                }
            ],
            "duration": 180
        },
        {
            "watch": ".motion-notes",
            "targets": "summary",
            "frames": [
                {
                    "transform": "scaleX(0.88)"
                },
                {
                    "transform": "scaleX(1)"
                }
            ],
            "duration": 180
        }
    ]
});

})();
const proof = await fetch("/proof.json").then((r) => {
  if (!r.ok) throw Error("Evidence unavailable");
  return r.json();
});
const { analysis: a, supply: s, canary: c, recording: r } = proof;
const node = (tag, text, cls) => {
  const e = document.createElement(tag);
  e.textContent = text;
  if (cls) e.className = cls;
  return e;
};
for (const [value, label, scope] of [
  [
    `${(a.flakes.precision * 100).toFixed(0)}% / ${(a.flakes.recall * 100).toFixed(0)}%`,
    "Flake precision / recall",
    `${a.flakes.truth} injected tests · ${a.flakes.observations.toLocaleString()} observations`,
  ],
  [
    String(s.fixtures.bad.verdict.blocked.length),
    "High findings blocked",
    `${s.fixtures.bad.verdict.vulnerability_matches} advisories in vulnerable metadata`,
  ],
  [
    `${a.plans.caught} / ${a.plans.risky}`,
    "Risky plans caught",
    `${a.plans.samples} fixtures · ${a.plans.false_positives} false positives`,
  ],
]) {
  const card = node("article", "");
  card.append(
    node("strong", value),
    node("h3", label),
    node("p", scope, "muted"),
  );
  document.querySelector("#metrics").append(card);
}
for (const row of c.canaries) {
  const tr = node("tr", "");
  for (const value of [
    row.candidate,
    row.state.state,
    row.proxy_after.upstream,
    JSON.stringify(row.proxy_after.body),
  ])
    tr.append(node("td", value));
  document.querySelector("#canaries").append(tr);
}
document.querySelector("#recovery").textContent =
  `API SIGKILL during a probe → restarted state: ${c.recovery.state.state} → proxy restored to ${c.recovery.proxy_after.upstream}.`;
document.querySelector("#supply").textContent =
  `The Rust gate blocked ${s.fixtures.bad.verdict.blocked.length} High findings for urllib3 ${s.fixtures.bad.version}. The ${s.fixtures.control.version} metadata control passed with ${s.fixtures.control.verdict.vulnerability_matches} scanner matches. Artifact tampering was rejected for both.`;
document.querySelector("#accuracy").textContent =
  `${a.synthetic_clusters.samples} synthetic logs formed ${a.synthetic_clusters.clusters} groups, with purity ${a.synthetic_clusters.purity.toFixed(2)} and pairwise recall ${a.synthetic_clusters.pairwise_recall.toFixed(2)}. Separately: ${a.public_clusters.samples} reviewed public excerpts, ${a.public_clusters.clusters} visible signature groups.`;
document.querySelector("#recording").textContent =
  `Actual console recording: ${Number(r.format.duration).toFixed(2)} seconds. Local services; no simulated live counters on this page.`;
