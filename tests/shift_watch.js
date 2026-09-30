// Watches every page for layout shifts the "Stability" rule forbids
// (skills/leaf/assets/AGENTS.md). The browser fixture installs it after write_watch.js
// on every page a test opens (render_harness.watched), so every test checks it, except
// a nightly-marked one for now (known_shifts.py, `watches_shifts`).
//
// Chrome's Layout Instability API is the evidence: it compares painted frames, net of
// scrolling, so it sees a move that paints and is undone before any script could look,
// and names the elements that moved (the five that moved most, in a frame that moved
// more). It also says whether the user gave the page input in the half second before
// the frame (`hadRecentInput`; a key, a press or a resize is input, a script's click or
// a server's news is not). It credits none to a frame nested in another page, where a
// trusted key or press in the frame's own document counts the same way. Text inserted without a key, as Playwright's `fill` and
// `insert_text` and a committed composition do, is not input to Chrome, but its trusted
// `beforeinput` is typing here: a frame of that keystroke's rendering (below) is the
// second rule's alone, and a frame after it is judged like any other. Two rules read the
// API:
//
// - Nothing moves without input. News, a page loading, and whatever a timer or a
//   server's answer changes may repaint a box or grow it into free room, but a shift
//   Chrome reports without recent input moved something the user did not ask to move.
//   It is reported for every element the frame moved, once per element, named by
//   write_watch.js's `lfPlace`. The tests whose pages still do are
//   `known_shifts.py`.
// - Typing never carries its field. A keystroke may grow its field, at whichever edge
//   its layout grows it: down in a card, up in a composer pinned to the panel's foot. It
//   never moves the field whole, as a "Draft" mark appearing in the header above a reply
//   box once did.
//
// What the API cannot say is why a frame moved. A move the step before the keystroke
// laid out but had not yet painted, such as a widget a test removed by script, paints in
// the keystroke's first frame and reads as the typing's. And its rects are what a node
// paints, a focus ring or a shadow included, clipped to the viewport, not the node's
// box. So at each keystroke, a trusted `beforeinput` whose composed path names the field
// (a textarea, an input, or the host of a `leaf-text`'s closed editor), the box of the
// field and of every element holding it is read with a forced layout: every earlier
// change, and none of the keystroke's own. The same boxes are read again at the start of
// each frame of the keystroke's rendering, which is what the frame before it painted. A
// shift Chrome reports during the rendering is the typing's where it names one of those
// elements at a box, in the next frame's reading, whose opposite edges both differ from
// the key's.
//
// The keystroke's rendering runs until the first frame after the runtime's settled
// reading (runtime/rendering.js) says nothing it queued is waiting, the first frame on a
// page without the runtime, or a second at most. It ends sooner where something else
// may move the field: another key or press (a key the page answers without editing,
// such as Enter sending a reply, fires no `beforeinput`); news, the page adopting a
// server reading (`data-lf-reading`, runtime/presentation.js), after which a reply
// arriving above the box moves it for its own reason; a resize of the window; and a
// scroll of the document or an element holding the field, which moves every box after
// the reading at the key. A
// frame that finds still running an animation that moves a box, one already running on
// the field or an element holding it at the key, as a panel's slide is when the user
// types into it before it stops, leaves the rest of the rendering to neither rule: that
// motion is the gesture's that began it.
//
// Each finding is reported on the console as a browser problem, which fails the test
// like any other.
(() => {
  const WINDOW = 1000;
  const RECENT = 500;
  const GEOMETRY =
    /^(transform|translate|scale|rotate|inset|top|left|right|bottom|width|height|margin|padding)/;
  // An element's parent in the composed tree, crossing from a shadow root to its host.
  const up = (node) =>
    node.parentNode instanceof ShadowRoot ? node.parentNode.host : node.parentNode;
  const holds = (node, field) => {
    for (let at = field; at; at = up(at)) if (at === node) return true;
    return false;
  };
  // What the API names, which it does not once the node is gone.
  const name = (node) => (node ? window.lfPlace(node) : "a node since removed");
  // Both edges moved the same way. A box that grew moved one edge, or both apart, as
  // the painted box of a field does when it gains its focus ring.
  const carried = (from, to, start, end) => {
    const near = to[start] - from[start];
    const far = to[end] - from[end];
    return (
      Math.abs(near) >= 1 && Math.abs(far) >= 1 && Math.sign(near) === Math.sign(far)
    );
  };
  const settled = () =>
    document.querySelector("script[data-lf-entry]")?.lfRenderingSettled?.() ?? true;
  // An animation that can move a box: one of its keyframes sets a geometric property.
  const moves = (animation) =>
    animation.effect
      ?.getKeyframes()
      .some((keyframe) => Object.keys(keyframe).some((key) => GEOMETRY.test(key))) ||
    GEOMETRY.test(animation.transitionProperty ?? "");
  const boxes = (nodes) =>
    new Map([...nodes].map((node) => [node, node.getBoundingClientRect()]));
  // Each keystroke's rendering: its field; the box of the field and of each element
  // holding it, at the key and at the start of every frame after, which is what the
  // frame before it painted; the animations already moving any of them; and when it ran.
  const renderings = [];
  let open = null;
  let frame = 0;
  const close = () => {
    if (open) open.end = performance.now();
    open = null;
    cancelAnimationFrame(frame);
  };
  const watch = (at) => {
    // Motion the key found under way carries the field for the gesture that began it,
    // so from the first frame that finds it still running no reading is the typing's:
    // the rendering's frames are its own, and none of them is judged.
    if (open.moving?.some(({ playState }) => playState === "running"))
      open.moving = null;
    if (open.moving) open.frames.push({ at, boxes: boxes(open.found.keys()) });
    judge(open.waiting.splice(0));
    if (open.last || at - open.start > WINDOW) return close();
    // A settled reading here counts updates before this one; this frame's own
    // callbacks may still move the field, so the rendering runs through the next.
    open.last = settled();
    frame = requestAnimationFrame(watch);
  };
  document.addEventListener(
    "beforeinput",
    (event) => {
      if (!event.isTrusted) return;
      close();
      const field = event.composedPath()[0];
      const holding = [];
      for (let at = field; at instanceof Element; at = up(at)) holding.push(at);
      open = {
        field,
        found: boxes(holding),
        moving: holding.flatMap((node) => node.getAnimations()).filter(moves),
        frames: [],
        waiting: [],
        start: event.timeStamp,
        end: Infinity,
        last: false,
      };
      renderings.push(open);
      if (renderings.length > 50) renderings.shift();
      frame = requestAnimationFrame(watch);
    },
    true,
  );
  // A resize lays the page out anew, the field with it.
  window.addEventListener("resize", () => close());
  document.addEventListener(
    "scroll",
    (event) => {
      if (open && holds(event.target, open.field)) close();
    },
    true,
  );
  new MutationObserver(close).observe(document, {
    subtree: true,
    attributeFilter: ["data-lf-reading"],
  });
  // Chrome credits no input to a frame nested in another page, so a trusted key or
  // press in this document, or in a same-origin document holding it, counts for as long
  // as Chrome counts one (`hadRecentInput`). Every recent one is kept: the observer may
  // judge a frame after a later key.
  const presses = [];
  const heard = (view) => (event) => {
    if (!event.isTrusted) return;
    presses.push(
      event.timeStamp + view.performance.timeOrigin - performance.timeOrigin,
    );
    if (presses.length > 50) presses.shift();
    if (view === window) close();
  };
  for (let view = window; ; view = view.parent) {
    let held;
    try {
      held = view.document;
    } catch {
      break;
    }
    for (const type of ["keydown", "pointerdown"])
      held.addEventListener(type, heard(view), true);
    if (view === view.parent) break;
  }
  const input = (entry) =>
    entry.hadRecentInput ||
    presses.some((at) => at <= entry.startTime && entry.startTime - at < RECENT);
  const reported = new Set();
  const report = (what, detail) => {
    if (reported.has(what)) return;
    reported.add(what);
    console.error(`${what}${detail}`);
  };
  const box = ({ left, top, width, height }) =>
    `${Math.round(left)},${Math.round(top)} ${Math.round(width)}x${Math.round(height)}`;
  const by = (from, to) =>
    ` by (${Math.round(to.left - from.left)}, ${Math.round(to.top - from.top)})px`;
  const beside = (sources, node) => {
    const others = sources
      .filter((source) => source.node !== node)
      .map((source) => name(source.node));
    return others.length ? `; the same frame moved ${others.join(", ")}` : "";
  };
  // One known defect is every page's, so it is known here by when it happens rather than
  // in `known_shifts.py` by test: widgets upgrade after the authored document has painted,
  // and the frame that presents the page carries every box their upgrade reshaped. The
  // page before it is presented runs until the second frame after the runtime stamps
  // `data-lf-presented` on a page that has one (runtime/presentation.js). Fixing the
  // defect deletes this.
  let presented = null;
  new MutationObserver(() => {
    if (presented !== null || !document.body?.hasAttribute("data-lf-presented")) return;
    presented = Infinity;
    requestAnimationFrame(() =>
      requestAnimationFrame((at) => {
        presented = at;
      }),
    );
  }).observe(document, { subtree: true, attributeFilter: ["data-lf-presented"] });
  const presenting = ({ startTime }) =>
    document.querySelector("script[data-lf-entry]") &&
    (presented === null || startTime < presented);
  const unasked = (entry) => {
    if (presenting(entry)) return;
    for (const { node, previousRect, currentRect } of entry.sources) {
      report(
        `${name(node)} moved without input`,
        by(previousRect, currentRect) + beside(entry.sources, node),
      );
    }
  };
  // Chrome's rects are what a node paints, clipped to the viewport, so they are held
  // against the frame's own reading, never against the key's.
  const typed = (entry, rendering, painted) => {
    for (const { node } of entry.sources) {
      const before = rendering.found.get(node);
      const after = painted.get(node);
      if (
        !before ||
        (!carried(before, after, "top", "bottom") &&
          !carried(before, after, "left", "right"))
      )
        continue;
      report(
        `typing in ${window.lfPlace(rendering.field)} moved ${window.lfPlace(node)}`,
        by(before, after) +
          `; the key found ${box(before)}, the frame painted ${box(after)}` +
          beside(entry.sources, node),
      );
    }
  };
  const judge = (entries) => {
    for (const entry of entries) {
      const rendering = renderings.find(
        ({ start, end }) => start <= entry.startTime && entry.startTime <= end,
      );
      const painted = rendering?.frames.find(({ at }) => at > entry.startTime);
      if (painted) typed(entry, rendering, painted.boxes);
      else if (rendering === open && open) open.waiting.push(entry);
      // A frame the keystroke's rendering ended before reading is no one's to judge.
      else if (!rendering && !input(entry)) unasked(entry);
    }
  };
  const observer = new PerformanceObserver((list) => judge(list.getEntries()));
  observer.observe({ type: "layout-shift" });
  // A frame's shifts reach the observer only once it paints, and a task or more after,
  // so a test whose last act moves the page would end before the report. The browser
  // fixture awaits this as the test body returns: the frames the last act changed paint,
  // then every shift so far is judged. Chrome paints no frame for a page it is not
  // drawing, so that wait is capped.
  window.lfShiftsJudged = () =>
    new Promise((resolve) => {
      let judged = false;
      const drain = () => {
        if (judged) return;
        judged = true;
        judge(observer.takeRecords());
        resolve();
      };
      requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(drain)));
      setTimeout(drain, 500);
    });
})();
