/* Browser-side latency measurement for leaf-dev bench-latency and profile.
 *
 * Installed before each document. The goals stay in sessionStorage so a revision
 * that reloads the page is sampled by the document that replaces it. Sampling
 * records the first painted frame that meets each goal and the traffic from arming
 * through settlement; Python drives the gestures and agent writes in the top tab.
 * Embedded examples have their own semantic document and share no measurement.
 */
(() => {
  if (window !== window.top || location.protocol === "about:") return;
  const WATCH = "leaf-bench-watch";
  performance.setResourceTimingBufferSize(1000000);
  const documentId = crypto.randomUUID();
  const clock = () => performance.timeOrigin + performance.now();
  let input = null;
  addEventListener(
    "keydown",
    (event) => {
      if (event.key === "Enter") input = performance.timeOrigin + event.timeStamp;
    },
    true,
  );
  const shown = (node) => Boolean(node?.checkVisibility());
  const messages = (words) =>
    [
      ...document.querySelectorAll(
        ":is(.lf-thread, .lf-page-thread) :is([data-mid], [data-event])",
      ),
    ].filter((node) => node.textContent.includes(words) && shown(node));
  let semantic = null;
  let stopWatching = null;
  async function diagnostics() {
    const entry = document.querySelector("script[data-lf-entry]").dataset.lfEntry;
    semantic ??= await import(
      new URL("runtime/check-api.js", new URL(entry, location.href)).href
    );
  }
  const facts = {
    message: (words) => messages(words).length > 0,
    // Admission and presentation belong to this exact gesture, even when its
    // workflow already advanced beyond the initial delivery receipt.
    delivered: (_intent, attempt) =>
      Boolean(attempt) &&
      Boolean(semantic) &&
      semantic.applicationPresented() &&
      semantic
        .readApplication()
        .authoritative?.browser.receipts.some((receipt) => receipt.attempt === attempt),
    card: ({ card, to }) => {
      const node = document.getElementById(card);
      return (
        node?.parentElement?.id === to &&
        !node.classList.contains("lf-lift") &&
        shown(node)
      );
    },
    status: (detail) => {
      const node = document.querySelector(".lf-status-text");
      return shown(node) && node.textContent.includes(detail);
    },
    revision: ({ revision, id, words }) => {
      const node = document.getElementById(id);
      return (
        Number(document.querySelector('meta[name="lf-revision"]')?.content) >=
          revision &&
        document.body.hasAttribute("data-lf-presented") &&
        shown(node) &&
        node.textContent.includes(words)
      );
    },
  };
  const watched = () => JSON.parse(sessionStorage.getItem(WATCH) ?? "null");
  let sampling = false;
  function sample() {
    if (sampling) return;
    sampling = true;
    const frame = () =>
      requestAnimationFrame(() => {
        const channel = new MessageChannel();
        channel.port1.onmessage = () => {
          const watch = watched();
          if (!watch) return (sampling = false);
          const at = clock();
          let open = false;
          for (const goal of watch.goals) {
            if (goal.at !== null) continue;
            const met = facts[goal.fact](goal.arg, goal.attempt);
            if (met) {
              goal.at = at;
              // Where a trace of the page finds this frame (`leaf-dev profile`).
              performance.mark(`lf-bench:${goal.name}`);
            } else open = true;
          }
          sessionStorage.setItem(WATCH, JSON.stringify(watch));
          if (open) frame();
          else sampling = false;
        };
        channel.port2.postMessage(null);
      });
    frame();
  }
  const ledger = () =>
    JSON.parse(document.documentElement.dataset.lfTraffic ?? '{"sends":0,"asked":0}');
  const resources = (entries) => ({
    requests: entries.length,
    bytes: entries.reduce((total, entry) => total + entry.transferSize, 0),
  });
  Object.defineProperty(window, "__leafBench", {
    value: Object.freeze({
      async arm(goals) {
        const delivering = goals.some((goal) => goal.fact === "delivered");
        if (delivering) await diagnostics();
        stopWatching?.();
        input = null;
        const watch = {
          goals: goals.map((goal) => ({ ...goal, at: null })),
          document: documentId,
          since: performance.now(),
          ledger: ledger(),
        };
        sessionStorage.setItem(WATCH, JSON.stringify(watch));
        if (delivering) {
          const existing = new Set(
            semantic.readApplication().unresolved.map((entry) => entry.event.attempt),
          );
          // Bind before the POST can answer: a fast admission may remove its local
          // ledger entry before the next frame samples the painted result.
          stopWatching = semantic.watchSemantic((root) => {
            const watch = watched();
            for (const goal of watch.goals) {
              if (goal.fact !== "delivered" || goal.attempt) continue;
              const entry = root.unresolved.find(
                ({ event }) =>
                  !existing.has(event.attempt) &&
                  event.kind === goal.arg.kind &&
                  (!goal.arg.unit || event.detail.unit === goal.arg.unit),
              );
              if (entry) goal.attempt = entry.event.attempt;
            }
            sessionStorage.setItem(WATCH, JSON.stringify(watch));
          });
        }
        sample();
      },
      watch: watched,
      disarm() {
        stopWatching?.();
        stopWatching = null;
        sessionStorage.removeItem(WATCH);
      },
      input: () => input,
      revision: () =>
        Number(document.querySelector('meta[name="lf-revision"]')?.content),
      quiet() {
        const ready =
          document.querySelector("script[data-lf-entry]")?.lfReadiness?.() === null;
        const trips = ledger();
        return (
          ready &&
          trips.acked === trips.sends &&
          trips.heard === trips.asked &&
          !trips.pending?.length
        );
      },
      // What the page did since `arm`: in this document the resource entries started
      // since then, and after a reload everything the new document loaded.
      traffic() {
        const watch = watched();
        const now = ledger();
        if (watch.document === documentId)
          return {
            install: "in place",
            sends: now.sends - watch.ledger.sends,
            asked: now.asked - watch.ledger.asked,
            ...resources(
              performance
                .getEntriesByType("resource")
                .filter((entry) => entry.startTime >= watch.since),
            ),
          };
        return {
          install: "reload",
          sends: now.sends,
          asked: now.asked,
          ...resources([
            ...performance.getEntriesByType("navigation"),
            ...performance.getEntriesByType("resource"),
          ]),
        };
      },
    }),
  });
  if (watched()) {
    if (watched().goals.some((goal) => goal.fact === "delivered"))
      addEventListener("DOMContentLoaded", diagnostics, { once: true });
    sample();
  }
})();
