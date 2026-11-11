/* When a page first painted each goal a benchmark waits for: each input `leaf-dev
 * bench`'s paint pass times (`painted.py`).
 *
 * Installed before each document. The goals stay in sessionStorage so a revision
 * that reloads the page is sampled by the document that replaces it. Sampling
 * records the first painted frame that meets each goal, read as the frame renders
 * and recorded once it has painted; the trips the runtime's ledger counted from
 * arming through settlement; and, where `main_thread.js` is installed too, the long
 * animation frames this document ran since arming, with the scripts that ran in
 * each. The input a gesture's time counts from is its last Enter or pointer click.
 * Python drives the gestures and agent writes in the top tab, and reads the requests
 * from the browser. Embedded examples have their own semantic document and share no
 * measurement.
 *
 * A goal is read in the probe's animation callback, before the frame's later
 * callbacks, their microtasks and ResizeObserver delivery, so a goal that those make
 * true counts at the next frame: each time is an upper bound, at most a frame above
 * the paint that first showed its goal. That holds only for a goal that stays met
 * once met, since a later callback in the same frame could otherwise undo it after it
 * was read. `message`, `card` and `delivered`'s event stay once there, and
 * `delivered` and `revision` also ask that presentation has finished, which a later
 * reading can only delay. `status` stays only while nothing else sets the page's
 * status, as in bench's runs. `met` reads one goal's fact once, without sampling,
 * for a reader that only waits for the result.
 */
(() => {
  if (window !== window.top || location.protocol === "about:") return;
  const WATCH = "leaf-bench-watch";
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
  addEventListener(
    "click",
    (event) => {
      // A pointer's, which counts its presses; Enter's click on a button counts none.
      if (event.detail) input = performance.timeOrigin + event.timeStamp;
    },
    true,
  );
  const shown = (node) => Boolean(node?.checkVisibility());
  const messages = (words) =>
    [
      ...document.querySelectorAll(
        ":is(.lf-thread, .lf-page-thread) :is([data-mid], [data-lf-event])",
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
    // No margin row shows for `target`, as once a resolved thread's row leaves.
    rowLeft: (target) =>
      ![...document.querySelectorAll("[data-lf-margin-for]")].some(
        (row) => row.dataset.lfMarginFor === target && shown(row),
      ),
    // Admission and presentation belong to this exact gesture, even when its
    // workflow already advanced beyond the initial delivery receipt.
    delivered: (_intent, attempt) =>
      Boolean(attempt) &&
      Boolean(semantic) &&
      semantic.applicationPresented() &&
      semantic
        .readApplication()
        .authoritative?.events.some((event) => event.attempt === attempt),
    card: ({ card, to }) => {
      const node = document.getElementById(card);
      return (
        node?.parentElement?.id === to &&
        !node.classList.contains("lf-lift") &&
        shown(node)
      );
    },
    // The floating panel's leaf: its name carries the status in the paint that colours
    // its dot. The empty field's placeholder says the status too, but only once a
    // passing notice, such as the agent becoming active, has had its seat.
    status: (detail) => {
      const node = document.querySelector(".lf-fp-leaf");
      return shown(node) && Boolean(node.getAttribute("aria-label")?.includes(detail));
    },
    revision: ({ revision, id, words }) => {
      const node = document.getElementById(id);
      return (
        Number(document.querySelector('meta[name="lf-revision"]')?.content) >=
          revision &&
        document
          .querySelector("script[data-lf-entry]")
          ?.lfReadiness?.(null, "presented") === null &&
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
        // The goals that hold as this frame renders, which its paint shows. Read
        // after the paint instead, a reading the server's answer brought between
        // the two would count before any frame had shown it.
        const rendering = watched();
        if (!rendering) return (sampling = false);
        const painting = new Set(
          rendering.goals
            .filter(
              (goal) => goal.at === null && facts[goal.fact](goal.arg, goal.attempt),
            )
            .map((goal) => goal.name),
        );
        const channel = new MessageChannel();
        // The first task after the frame, once it has painted.
        channel.port1.onmessage = () => {
          const watch = watched();
          if (!watch) return (sampling = false);
          const at = clock();
          for (const goal of watch.goals) {
            if (goal.at !== null || !painting.has(goal.name)) continue;
            goal.at = at;
            // Where a trace of the page finds this frame (`bench --profile`).
            performance.mark(`lf-bench:${goal.name}`);
          }
          sessionStorage.setItem(WATCH, JSON.stringify(watch));
          if (watch.goals.some((goal) => goal.at === null)) frame();
          else sampling = false;
        };
        channel.port2.postMessage(null);
      });
    frame();
  }
  const ledger = () =>
    JSON.parse(document.documentElement.dataset.lfTraffic ?? '{"sends":0,"asked":0}');
  Object.defineProperty(window, "__leafBench", {
    value: Object.freeze({
      async arm(goals) {
        const delivering = goals.some((goal) => goal.fact === "delivered");
        if (delivering) await diagnostics();
        stopWatching?.();
        input = null;
        window.__leafMainThread?.reset();
        const watch = {
          goals: goals.map((goal) => ({ ...goal, at: null })),
          document: documentId,
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
      met: (fact, arg) => facts[fact](arg),
      disarm() {
        stopWatching?.();
        stopWatching = null;
        sessionStorage.removeItem(WATCH);
      },
      input: () => input,
      frames: () => window.__leafMainThread.reading().frames,
      revision: () =>
        Number(document.querySelector('meta[name="lf-revision"]')?.content),
      // Every trip the runtime's ledger counts, its event posts and state reads, has
      // ended (runtime/traffic.js).
      quiet() {
        const trips = ledger();
        return (
          trips.acked === trips.sends &&
          trips.heard === trips.asked &&
          !trips.pending?.length
        );
      },
      // The trips the runtime's ledger counted since `arm`, in this document or, after
      // a reload, in the new one.
      traffic() {
        const watch = watched();
        const now = ledger();
        if (watch.document === documentId)
          return {
            install: "in place",
            sends: now.sends - watch.ledger.sends,
            asked: now.asked - watch.ledger.asked,
          };
        return { install: "reload", sends: now.sends, asked: now.asked };
      },
    }),
  });
  if (watched()) {
    if (watched().goals.some((goal) => goal.fact === "delivered"))
      addEventListener("DOMContentLoaded", diagnostics, { once: true });
    sample();
  }
})();
