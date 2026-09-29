// Watches every page for typing that moves the field being typed in. The browser
// fixture installs it after write_watch.js on every page a test opens
// (render_harness.watched), so any test that types checks it.
//
// A keystroke may grow its field, at whichever edge its layout grows it: down in a
// card, up in a composer pinned to the panel's foot. It never carries the field, as a
// "Draft" mark appearing in the header above a reply box once did
// (skills/leaf/assets/AGENTS.md, "Stability"). Every frame from a keystroke until the
// page has rendered what it asked for compares the field's box with its box just before
// the keystroke, net of every scroll that moves the field, and reports a field whose
// opposite edges both moved as a browser problem on the console, which fails the test
// like any other. Each field is reported once per document, named by write_watch.js's
// `lfPlace`.
//
// A keystroke is a trusted `beforeinput`, whose composed path names the field: a
// textarea, an input, or the host of a `leaf-text`'s closed editor. Measuring there
// reads the layout every earlier change left, and none of the keystroke's own. A key
// the page answers without editing, such as Enter sending a reply, fires none, and it
// or a press ends the watch, and so does news: the page adopting a server reading
// (`data-lf-reading`, runtime/presentation.js), after which a reply arriving above the
// box moves it for its own reason. Otherwise the keystroke's rendering is over at the
// first frame after the runtime's settled reading (runtime/rendering.js) says nothing it
// queued is waiting, the first frame on a page without the runtime, and a second at
// most.
(() => {
  const WINDOW = 1000;
  // An element's parent in the composed tree, crossing from a shadow root to its host.
  const up = (node) =>
    node.parentNode instanceof ShadowRoot ? node.parentNode.host : node.parentNode;
  // The field's edges in the coordinates of everything it scrolls with. A fixed
  // ancestor stands in the viewport, so no scroll beyond it moves the field.
  const measure = (field) => {
    const box = field.getBoundingClientRect();
    let x = 0;
    let y = 0;
    for (let at = up(field); at instanceof Element; at = up(at)) {
      x += at.scrollLeft;
      y += at.scrollTop;
      if (getComputedStyle(at).position === "fixed") break;
    }
    return {
      top: box.top + y,
      bottom: box.bottom + y,
      left: box.left + x,
      right: box.right + x,
    };
  };
  const carried = (from, to, start, end) =>
    Math.abs(to[start] - from[start]) >= 1 && Math.abs(to[end] - from[end]) >= 1;
  const settled = () =>
    document.querySelector("script[data-lf-entry]")?.lfRenderingSettled?.() ?? true;
  const reported = new Set();
  let typing = null;
  let frame = 0;
  const watch = () => {
    const { field, at, base, last } = typing;
    if (!field.isConnected) return;
    const now = measure(field);
    const what = window.lfPlace(field);
    if (
      !reported.has(what) &&
      (carried(base, now, "top", "bottom") || carried(base, now, "left", "right"))
    ) {
      reported.add(what);
      const dx = Math.round(now.left - base.left);
      const dy = Math.round(now.top - base.top);
      console.error(`typing in ${what} moved it by (${dx}, ${dy})px`);
    }
    if (last || performance.now() - at > WINDOW) return;
    // A settled reading here counts updates before this one; this frame's own
    // callbacks may still move the field, so the next frame is the last one read.
    typing.last = settled();
    frame = requestAnimationFrame(watch);
  };
  // A field an animation is carrying, such as a panel still sliding in from the press
  // that opened it, moves for that press's reason.
  const inMotion = (field) => {
    for (let at = field; at instanceof Element; at = up(at))
      if (at.getAnimations().some((animation) => animation.playState === "running"))
        return true;
    return false;
  };
  document.addEventListener(
    "beforeinput",
    (event) => {
      if (!event.isTrusted) return;
      cancelAnimationFrame(frame);
      const field = event.composedPath()[0];
      if (inMotion(field)) return;
      typing = { field, at: event.timeStamp, base: measure(field), last: false };
      frame = requestAnimationFrame(watch);
    },
    true,
  );
  new MutationObserver(() => cancelAnimationFrame(frame)).observe(document, {
    subtree: true,
    attributeFilter: ["data-lf-reading"],
  });
  for (const type of ["keydown", "pointerdown"])
    document.addEventListener(
      type,
      (event) => {
        if (event.isTrusted) cancelAnimationFrame(frame);
      },
      true,
    );
})();
