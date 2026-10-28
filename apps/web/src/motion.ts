type MotionRule = {
  watch: string;
  targets: string;
  frames: Keyframe[];
  duration: number;
};
type MotionProfile = {
  name: string;
  press: Keyframe[];
  neighbors: string;
  rules: MotionRule[];
};
/** Finite, event-driven motion. No entrance timeline, polling, layout reads, or content delays. */
function installMotion(profile: MotionProfile) {
  const preference = matchMedia("(prefers-reduced-motion: no-preference)");
  const running = new Set<Animation>();
  const owned = new WeakMap<Element, Animation>();
  let observer: MutationObserver | undefined;
  let events: AbortController | undefined;
  let frame = 0;
  let interacted = false;
  const pending = new Map<MotionRule, Set<Element>>();
  const snapshots = new WeakMap<Element, Map<MotionRule, string[]>>();
  document.documentElement.dataset.motionProfile = profile.name;
  const play = (element: Element, frames: Keyframe[], duration: number) => {
    if (
      !preference.matches ||
      !element.isConnected ||
      document.hidden ||
      typeof element.animate !== "function"
    )
      return;
    if (
      !(element instanceof HTMLElement) ||
      element.matches(
        "input,textarea,[contenteditable],.drag-handle,.note-body",
      ) ||
      element.querySelector(
        "input:focus,textarea:focus,[contenteditable]:focus",
      )
    )
      return;
    // Stream updates never restart an in-flight effect; each owns at most one compositor animation.
    if (owned.get(element)?.playState === "running") return;
    const animation = element.animate(frames, {
      duration,
      easing: "cubic-bezier(0.16, 1, 0.3, 1)",
      iterations: 1,
      fill: "none",
    });
    owned.set(element, animation);
    running.add(animation);
    const clear = () => {
      running.delete(animation);
      if (owned.get(element) === animation) owned.delete(element);
    };
    animation.onfinish = clear;
    animation.oncancel = clear;
  };
  const flush = () => {
    frame = 0;
    for (const [rule, groups] of pending)
      for (const group of groups) {
        const targets =
          rule.targets === ":self"
            ? [group]
            : Array.from(group.querySelectorAll(rule.targets)).slice(0, 6);
        const history = snapshots.get(group) || new Map<MotionRule, string[]>();
        const previous = history.get(rule) || [];
        const current: string[] = [];
        for (const [index, target] of targets.entries()) {
          const signature =
            (group.getAttribute("class") || "") +
            "|" +
            group.hasAttribute("open") +
            "|" +
            (target.textContent || "").slice(0, 2048) +
            "|" +
            target.getAttribute("class") +
            "|" +
            target.getAttribute("aria-pressed") +
            "|" +
            target.getAttribute("aria-current");
          current.push(signature);
          if (previous[index] !== signature) {
            if (interacted) play(target, rule.frames, rule.duration);
          }
        }
        history.set(rule, current);
        snapshots.set(group, history);
      }
    pending.clear();
  };
  const enqueue = (rule: MotionRule, group: Element | null) => {
    if (!group) return;
    if (!pending.has(rule)) pending.set(rule, new Set());
    const groups = pending.get(rule)!;
    if (groups.size < 4) groups.add(group);
    if (!frame) frame = requestAnimationFrame(flush);
  };
  const stop = () => {
    observer?.disconnect();
    events?.abort();
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    pending.clear();
    for (const animation of running) animation.cancel();
    running.clear();
  };
  const start = () => {
    stop();
    if (!preference.matches) return;
    events = new AbortController();
    const signal = events.signal;
    const press = (event: Event) => {
      if (event instanceof KeyboardEvent && !["Enter", " "].includes(event.key))
        return;
      const source = event.target instanceof Element ? event.target : null;
      const control = source?.closest("button,summary,a.button");
      if (
        !control ||
        control.matches(
          ':disabled,[aria-disabled="true"],.drag-handle,.note-body',
        )
      )
        return;
      interacted = true;
      play(control, profile.press, 160);
      if (control.matches(profile.neighbors)) {
        for (const sibling of Array.from(control.parentElement?.children || [])
          .filter((x) => x !== control && x.matches(profile.neighbors))
          .slice(0, 2)) {
          play(
            sibling,
            [
              { transform: "translateX(0) scaleX(1)" },
              { transform: "translateX(2px) scaleX(0.985)", offset: 0.28 },
              { transform: "translateX(0) scaleX(1)" },
            ],
            190,
          );
        }
      }
    };
    // Animate only once click targeting is committed; shrinking a pressed hitbox can otherwise lose edge clicks.
    document.addEventListener("click", press, { capture: true, signal });
    document.addEventListener("keydown", press, { capture: true, signal });
    for (const event of ["click", "change"])
      document.addEventListener(
        event,
        () => {
          interacted = true;
        },
        { capture: true, signal },
      );
    observer = new MutationObserver((records) => {
      for (const record of records) {
        const source =
          record.target instanceof Element
            ? record.target
            : record.target.parentElement;
        if (!source) continue;
        for (const rule of profile.rules) {
          enqueue(rule, source.closest(rule.watch));
          for (const added of Array.from(record.addedNodes).slice(0, 6))
            if (added instanceof Element) {
              enqueue(
                rule,
                added.matches(rule.watch)
                  ? added
                  : added.querySelector(rule.watch),
              );
            }
        }
      }
    });
    observer.observe(document.body, {
      subtree: true,
      childList: true,
      characterData: true,
      attributes: true,
      attributeFilter: ["class", "aria-current", "aria-pressed", "open"],
    });
  };
  preference.addEventListener("change", () =>
    preference.matches ? start() : stop(),
  );
  window.addEventListener("pagehide", stop, { once: true });
  window.addEventListener("pageshow", (event) => {
    if (event.persisted && preference.matches) start();
  });
  start();
}

installMotion({
  name: "gatekeeper",
  press: [
    {
      transform: "scaleX(0.97)",
    },
    {
      transform: "scaleX(1)",
    },
  ],
  neighbors: ".tabs button",
  rules: [
    {
      watch: ".timeline",
      targets: ".badge",
      frames: [
        {
          transform: "scaleX(0.88)",
        },
        {
          transform: "scaleX(1)",
        },
      ],
      duration: 180,
    },
    {
      watch: ".result",
      targets: ".mono,strong",
      frames: [
        {
          transform: "translateX(-4px)",
        },
        {
          transform: "translateX(0.8px)",
          offset: 0.65,
        },
        {
          transform: "translateX(0)",
        },
      ],
      duration: 170,
    },
    {
      watch: ".stats",
      targets: "strong,b",
      frames: [
        {
          transform: "translateX(3px)",
        },
        {
          transform: "translateX(0)",
        },
      ],
      duration: 160,
    },
  ],
});
