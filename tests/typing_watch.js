// Watches every page for typing that moves what the user is looking at. The browser
// fixture installs it on every page a test opens (render_harness.watched), so any test
// that types into a field checks it.
//
// Typing in a field may grow that field and push what comes after it, but it moves
// nothing else: not the field itself, and nothing before it, such as a "Draft" mark
// appearing in the header above the box (skills/leaf/assets/AGENTS.md, "Stability").
// Chrome's Layout Instability API reports each element whose start position changed in
// a frame, net of scrolling; a shift within a second of a keystroke, with no other key
// or press since, is that keystroke's. A shifted element that holds the field or stands
// before it in tree order is reported on the console as a browser problem, which fails
// the test like any other.
//
// A keystroke is a trusted `beforeinput`, whose composed path names the field: a
// textarea, an input, or the host of a `leaf-text`'s closed editor. A key the page
// answers without editing, such as Enter sending a reply, fires none, so what it moves
// is not typing's. Each finding is reported once per document.
(() => {
  const WINDOW = 1000;
  // An element by its tag, id and classes, one with neither by where it stands.
  const place = (node) => {
    const named =
      `${node.localName}${node.id ? "#" + node.id : ""}` +
      `${node.classList.length ? "." + [...node.classList].join(".") : ""}`;
    return !node.id && !node.classList.length && node.parentElement
      ? `${named} in ${place(node.parentElement)}`
      : named;
  };
  // The node's parent in the composed tree, crossing from a shadow root to its host.
  const up = (node) => (node instanceof ShadowRoot ? node.host : node.parentNode);
  const chain = (node) => {
    const nodes = [];
    for (let at = node; at; at = up(at)) nodes.push(at);
    return nodes;
  };
  // Whether a shift of `node` moves the field: it holds the field, or stands before it.
  const moves = (node, field) => {
    const fields = chain(field);
    if (fields.includes(node)) return true;
    const nodes = chain(node);
    if (nodes.includes(field)) return false;
    const common = nodes.find((at) => fields.includes(at));
    if (!common) return false;
    const mine = nodes[nodes.indexOf(common) - 1];
    const theirs = fields[fields.indexOf(common) - 1];
    return Boolean(mine.compareDocumentPosition(theirs) & Node.DOCUMENT_POSITION_FOLLOWING);
  };
  let typing = null;
  document.addEventListener(
    "beforeinput",
    (event) => {
      if (event.isTrusted) typing = { field: event.composedPath()[0], at: event.timeStamp };
    },
    true,
  );
  for (const type of ["keydown", "pointerdown"])
    document.addEventListener(
      type,
      (event) => {
        if (event.isTrusted) typing = null;
      },
      true,
    );
  const reported = new Set();
  new PerformanceObserver((list) => {
    for (const entry of list.getEntries()) {
      if (!typing || entry.startTime - typing.at > WINDOW) continue;
      const { field } = typing;
      // A source whose element is gone, or is a pseudo-element, names no node to place.
      for (const { node, previousRect, currentRect } of entry.sources) {
        if (!(node instanceof Element) || !moves(node, field)) continue;
        const what = `typing in ${place(field)} moved ${place(node)}`;
        if (reported.has(what)) continue;
        reported.add(what);
        const dx = Math.round(currentRect.x - previousRect.x);
        const dy = Math.round(currentRect.y - previousRect.y);
        console.error(`${what} by (${dx}, ${dy})px`);
      }
    }
  }).observe({ type: "layout-shift" });
})();
