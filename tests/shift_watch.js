// Watches every page for layout shifts the "Stability" rule forbids
// (skills/leaf/assets/AGENTS.md). The browser fixture installs it after write_watch.js
// on every page a test opens (render_harness.watched), so every test checks it.
//
// Chrome's Layout Instability API is the evidence: it compares painted frames, net of
// scrolling, so it sees a move that paints and is undone before any script could look,
// and names the elements that moved (the five that moved most, in a frame that moved
// more). It also says whether the user gave the page input in the half second before
// the frame (`hadRecentInput`; a key, a press or a resize is input, a script's click or
// a server's news is not). Text inserted without a key, as Playwright's `fill` and
// `insert_text` and a committed composition do, is not input to Chrome, but its trusted
// `beforeinput` is typing here, judged by the second rule alone. Two rules read it:
//
// - Nothing moves without input. News, a page loading, and whatever a timer or a
//   server's answer changes may repaint a box or grow it into free room, but a shift
//   Chrome reports without recent input moved something the user did not ask to move.
//   It is reported for every element the frame moved, once per element, named by
//   write_watch.js's `lfPlace`. `EXPECTED` holds the ones the page does today.
// - Typing never carries its field. A keystroke may grow its field, at whichever edge
//   its layout grows it: down in a card, up in a composer pinned to the panel's foot. It
//   never moves the field whole, as a "Draft" mark appearing in the header above a reply
//   box once did.
//
// What the API cannot say is why a frame moved. A move the step before the keystroke
// laid out but had not yet painted, such as a widget a test removed by script, paints in
// the keystroke's first frame and reads as the typing's. So at each keystroke, a trusted
// `beforeinput` whose composed path names the field (a textarea, an input, or the host
// of a `leaf-text`'s closed editor), the field's box and the box of every element holding
// it are read with a forced layout: every earlier change, and none of the keystroke's
// own. A shift during the keystroke's rendering is the typing's where it names one of
// those elements at a box whose opposite edges both differ from that reading.
//
// The keystroke's rendering runs until the first frame after the runtime's settled
// reading (runtime/rendering.js) says nothing it queued is waiting, the first frame on a
// page without the runtime, or a second at most. It ends sooner where something else
// may move the field: another key or press (a key the page answers without editing,
// such as Enter sending a reply, fires no `beforeinput`); news, the page adopting a
// server reading (`data-lf-reading`, runtime/presentation.js), after which a reply
// arriving above the box moves it for its own reason; and a scroll of the document or
// an element holding the field, which moves every box after the reading at the key.
//
// Each finding is reported on the console as a browser problem, which fails the test
// like any other.
(() => {
  const WINDOW = 1000;
  // Shifts without input the page makes today, by the report they make. Each is a
  // defect to fix, not a behavior to keep: fixing one deletes its lines.
  const EXPECTED = [
    // The section after a diff, 68px down, as the page first reads the log
    // (PANEL_PAGE, tests/render_cases_interaction.py).
    /^section#s-merge moved/,
    // A package's Ask on a live page, and the paragraphs after it
    // (tests/render_cases_interaction.py).
    /^(lf-ask#package-ask|p#live-lead-\d+) moved/,
    // The paragraphs at the foot of the live pages and of the page whose tail a thread
    // reads (tests/render_cases_interaction.py).
    /^p#(live-)?tail-\d+ moved/,
    // ship-review's tasks (examples/ship-review.html).
    /^lf-task#off-t-[\w-]+(\.lf-mark-el)? moved/,
    // A screenshot on the process page, its margin entry, and the passage after it
    // (tests/test_render_mcp.py).
    /^(lf-shot#mcp-shot|button\.lf-ui\.lf-margin-entry\.lf-shot-toggle) moved/,
    /^#text in p in section#plan moved/,
    // The MCP App's surface, stage and actions, inside its frame.
    /^(section#surface\.surface|span\.stage|span\.actions|div#page-host|div\.lf-banner-actions|div\.composer-actions) moved/,
    // A sample frame, its clip, and the thread panel's foot
    // (tests/test_render_read_state.py).
    /^(iframe\.lf-sample-frame|div#read-clip|div\.lf-thread-panel-foot) moved/,
    // The gallery's column, 21px sideways (tests/test_render_semantic_news.py).
    /^main\.layout-column moved/,
  ];
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
  const report = (what, detail) => {
    if (reported.has(what) || EXPECTED.some((known) => known.test(what))) return;
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
  const unasked = (entry) => {
    for (const { node, previousRect, currentRect } of entry.sources)
      report(
        `${name(node)} moved without input`,
        by(previousRect, currentRect) + beside(entry.sources, node),
      );
  };
  const typed = (entry, rendering) => {
    for (const { node, previousRect, currentRect } of entry.sources) {
      const before = rendering.found.get(node);
      if (
        !before ||
        (!carried(before, currentRect, "top", "bottom") &&
          !carried(before, currentRect, "left", "right"))
      )
        continue;
      report(
        `typing in ${window.lfPlace(rendering.field)} moved ${window.lfPlace(node)}`,
        by(before, currentRect) +
          `; the key found ${box(before)}, and Chrome painted ${box(previousRect)}` +
          ` then ${box(currentRect)}` +
          beside(entry.sources, node),
      );
    }
  };
  const judge = (entries) => {
    for (const entry of entries) {
      const rendering = renderings.find(
        ({ start, end }) => start <= entry.startTime && entry.startTime <= end,
      );
      if (rendering) typed(entry, rendering);
      else if (!entry.hadRecentInput) unasked(entry);
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
