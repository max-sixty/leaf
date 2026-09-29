// Watches every page for typing that moves the field being typed in. The browser
// fixture installs it after write_watch.js on every page a test opens
// (render_harness.watched), so any test that types checks it.
//
// A keystroke may grow its field, at whichever edge its layout grows it: down in a
// card, up in a composer pinned to the panel's foot. It never carries the field, as a
// "Draft" mark appearing in the header above a reply box once did
// (skills/leaf/assets/AGENTS.md, "Stability").
//
// Chrome's Layout Instability API is the evidence: it compares painted frames, net of
// scrolling, so it sees a move that paints and is undone before any script could look,
// and names the elements that moved (the five that moved most, in a frame that moved
// more). What it cannot say is why. A move the step before
// the keystroke laid out but had not yet painted, such as a widget a test removed by
// script, paints in the keystroke's first frame and reads as the typing's. So at each
// keystroke, a trusted `beforeinput` whose composed path names the field (a textarea,
// an input, or the host of a `leaf-text`'s closed editor), the field's box and the box
// of every element holding it are read with a forced layout: every earlier change, and
// none of the keystroke's own. A shift during the keystroke's rendering is the typing's
// where it names one of those elements at a box whose opposite edges both differ from
// that reading. It is reported as a browser problem on the console, which fails the test
// like any other, beside every element the same frame moved, once per pair of field and
// element, named by write_watch.js's `lfPlace`.
//
// The keystroke's rendering runs until the first frame after the runtime's settled
// reading (runtime/rendering.js) says nothing it queued is waiting, the first frame on a
// page without the runtime, or a second at most. It ends sooner where something else
// may move the field: another key or press (a key the page answers without editing,
// such as Enter sending a reply, fires no `beforeinput`); news, the page adopting a
// server reading (`data-lf-reading`, runtime/presentation.js), after which a reply
// arriving above the box moves it for its own reason; and a scroll of the document or
// an element holding the field, which moves every box after the reading at the key.
(() => {
  const WINDOW = 1000;
  // An element's parent in the composed tree, crossing from a shadow root to its host.
  const up = (node) =>
    node.parentNode instanceof ShadowRoot ? node.parentNode.host : node.parentNode;
  const holds = (node, field) => {
    for (let at = field; at; at = up(at)) if (at === node) return true;
    return false;
  };
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
  // Each keystroke's rendering: its field, the boxes it found, and when it ran.
  const renderings = [];
  let open = null;
  let frame = 0;
  const close = () => {
    if (open) open.end = performance.now();
    open = null;
    cancelAnimationFrame(frame);
  };
  const watch = () => {
    if (open.last || performance.now() - open.start > WINDOW) return close();
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
      const found = new Map();
      for (let at = field; at instanceof Element; at = up(at))
        found.set(at, at.getBoundingClientRect());
      open = { field, found, start: event.timeStamp, end: Infinity, last: false };
      renderings.push(open);
      if (renderings.length > 50) renderings.shift();
      frame = requestAnimationFrame(watch);
    },
    true,
  );
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
  for (const type of ["keydown", "pointerdown"])
    document.addEventListener(
      type,
      (event) => {
        if (event.isTrusted) close();
      },
      true,
    );
  const reported = new Set();
  const judge = (entries) => {
    for (const entry of entries) {
      const rendering = renderings.find(
        ({ start, end }) => start <= entry.startTime && entry.startTime <= end,
      );
      if (!rendering) continue;
      // A source whose element is gone, or is a pseudo-element, names no node to place.
      const moved = entry.sources.filter(({ node }) => node instanceof Element);
      for (const { node, currentRect } of moved) {
        const before = rendering.found.get(node);
        if (
          !before ||
          (!carried(before, currentRect, "top", "bottom") &&
            !carried(before, currentRect, "left", "right"))
        )
          continue;
        const what = `typing in ${window.lfPlace(rendering.field)} moved ${window.lfPlace(node)}`;
        if (reported.has(what)) continue;
        reported.add(what);
        const dx = Math.round(currentRect.left - before.left);
        const dy = Math.round(currentRect.top - before.top);
        const beside = moved
          .map(({ node: other }) => window.lfPlace(other))
          .filter((place) => place !== window.lfPlace(node));
        console.error(
          `${what} by (${dx}, ${dy})px` +
            (beside.length ? `; the same frame moved ${beside.join(", ")}` : ""),
        );
      }
    }
  };
  const observer = new PerformanceObserver((list) => judge(list.getEntries()));
  observer.observe({ type: "layout-shift" });
  // The observer hears a frame's shifts a task or more after it paints, so a test whose
  // last act is a keystroke would end before the report. The browser fixture calls this
  // before it reads a page's problems, to judge every shift already painted. It waits
  // for nothing: by then the page's server may be gone.
  window.lfTypingJudged = () => judge(observer.takeRecords());
})();
