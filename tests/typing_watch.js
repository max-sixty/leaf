// Watches every page for typing that moves the field being typed in. The browser
// fixture installs it after write_watch.js on every page a test opens
// (render_harness.watched), so any test that types checks it.
//
// A keystroke may grow its field, at whichever edge its layout grows it: down in a
// card, up in a composer pinned to the panel's foot. It never carries the field, as a
// "Draft" mark appearing in the header above a reply box once did
// (skills/leaf/assets/AGENTS.md, "Stability"). Every frame from a keystroke until the
// page has rendered what it asked for compares the field's box in the viewport with its
// box just before the keystroke, and reports a field whose opposite edges both moved as
// a browser problem on the console, which fails the test like any other. Each field is
// reported once per document, named by write_watch.js's `lfPlace`.
//
// A keystroke is a trusted `beforeinput`, whose composed path names the field: a
// textarea, an input, or the host of a `leaf-text`'s closed editor. Measuring there
// reads the layout every earlier change left, and none of the keystroke's own.
//
// The watch ends where something other than the keystroke may move the field: another
// key or press (a key the page answers without editing, such as Enter sending a reply,
// fires no `beforeinput`); a scroll of the document or of an element holding the field,
// whether the browser bringing the caret into view or the page keeping its place;
// news, the page adopting a server reading (`data-lf-reading`, runtime/presentation.js);
// and an animation already carrying the field when the key lands, such as a panel still
// sliding in from the press that opened it. Otherwise the keystroke's rendering is over
// at the first frame after the runtime's settled reading (runtime/rendering.js) says
// nothing it queued is waiting, the first frame on a page without the runtime, and a
// second at most.
(() => {
  const WINDOW = 1000;
  // An element's parent in the composed tree, crossing from a shadow root to its host.
  const up = (node) =>
    node.parentNode instanceof ShadowRoot ? node.parentNode.host : node.parentNode;
  const holds = (node, field) => {
    for (let at = field; at; at = up(at)) if (at === node) return true;
    return false;
  };
  const carried = (from, to, start, end) =>
    Math.abs(to[start] - from[start]) >= 1 && Math.abs(to[end] - from[end]) >= 1;
  const inMotion = (field) => {
    for (let at = field; at instanceof Element; at = up(at))
      if (at.getAnimations().some((animation) => animation.playState === "running"))
        return true;
    return false;
  };
  const settled = () =>
    document.querySelector("script[data-lf-entry]")?.lfRenderingSettled?.() ?? true;
  const reported = new Set();
  let typing = null;
  let frame = 0;
  const stop = () => {
    typing = null;
    cancelAnimationFrame(frame);
  };
  const watch = () => {
    const { field, at, base, last } = typing;
    if (!field.isConnected) return;
    const now = field.getBoundingClientRect();
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
  document.addEventListener(
    "beforeinput",
    (event) => {
      if (!event.isTrusted) return;
      stop();
      const field = event.composedPath()[0];
      if (inMotion(field)) return;
      typing = { field, at: event.timeStamp, base: field.getBoundingClientRect() };
      frame = requestAnimationFrame(watch);
    },
    true,
  );
  document.addEventListener(
    "scroll",
    (event) => {
      if (typing && holds(event.target, typing.field)) stop();
    },
    true,
  );
  new MutationObserver(stop).observe(document, {
    subtree: true,
    attributeFilter: ["data-lf-reading"],
  });
  for (const type of ["keydown", "pointerdown"])
    document.addEventListener(
      type,
      (event) => {
        if (event.isTrusted) stop();
      },
      true,
    );
})();
