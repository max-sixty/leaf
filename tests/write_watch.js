// Watches every DOM write a page makes, in its document and in each shadow root, from
// before the first byte parses. The browser fixture installs it on every page a test
// opens (render_harness.watched).
//
// A write that changes nothing is reported on the console as a browser problem, which
// fails the test like any other. "Nothing" is judged per frame: the writes to one place
// (an attribute, a text node's data) between two renderings change nothing when the
// place holds the value it started with once the frame has rendered, whether one writer
// restated it or two writers took turns, and a child-list write changes nothing when it
// puts back nodes that serialize as the ones it took out. Such a write still costs a
// style pass and a repaint, of the whole document while a CSS highlight holds a range,
// so code writes only what changed (skills/leaf/assets/AGENTS.md).
//
// Each finding is reported once per document: a writer that fires every frame would
// otherwise bury the report under its own repetitions.
//
// While `window.lfWrites` is an array, every write is also appended to it, numbered by
// `window.lfWriteStep`, for a test that reads what a gesture wrote (scroll_writes).
(() => {
  // An element by its tag, id and classes, and one with neither by where it stands.
  const place = (node) => {
    if (node.nodeType !== 1)
      return `${node.nodeName} in ${node.parentElement ? place(node.parentElement) : "nothing"}`;
    const named =
      `${node.localName}${node.id ? "#" + node.id : ""}` +
      `${node.classList.length ? "." + [...node.classList].join(".") : ""}`;
    const parent = node.parentElement ?? node.getRootNode().host;
    return node.id || node.classList.length || !parent
      ? named
      : `${named} in ${place(parent)}`;
  };
  const serial = (nodes) =>
    [...nodes].map((node) => node.outerHTML ?? node.data ?? "").join("");
  let count = 0;
  const numbered = new WeakMap();
  const number = (node) => {
    if (!numbered.has(node)) numbered.set(node, ++count);
    return numbered.get(node);
  };
  // Writes that restate a value for a reason of their own, by how a report begins.
  const EXPECTED = [
    // CodeMirror writes every attribute of its content element when it mounts a view,
    // the tab-size style that element already holds among them.
    "style on div.cm-content",
    // Web Awesome's icon reflects its `library` property onto the attribute it came from.
    "library on wa-icon",
    // Letting go of focus borrows the body's tab stop to move where the next Tab starts,
    // and gives it back in the same task (focus.js, `releaseFocus`).
    "tabindex on body",
    // The contents map decides whether it needs its crowded face by measuring its labels
    // without it, on every measure.
    "data-lf-compact on lf-toc",
  ];
  const reported = new Set();
  const report = (what) => {
    if (reported.has(what) || EXPECTED.some((known) => what.startsWith(known))) return;
    reported.add(what);
    console.error(`unchanged write: ${what}`);
  };
  const valueOf = (record) =>
    record.type === "attributes"
      ? record.target.getAttribute(record.attributeName)
      : record.target.data;
  // The first write to each place since the last rendering, judged once a frame has
  // rendered after it.
  const started = new Map();
  let judging = false;
  const judge = () => {
    judging = false;
    for (const record of started.values())
      if (valueOf(record) === record.oldValue)
        report(`${record.attributeName ?? "text"} on ${place(record.target)}`);
    started.clear();
  };
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      const key = `${number(record.target)} ${record.type} ${record.attributeName}`;
      if (record.type === "childList") {
        const removed = serial(record.removedNodes);
        if (removed !== "" && removed === serial(record.addedNodes))
          report(`children of ${place(record.target)}`);
      } else if (!started.has(key)) {
        started.set(key, record);
        if (!judging) requestAnimationFrame(() => setTimeout(judge));
        judging = true;
      }
      if (Array.isArray(window.lfWrites))
        window.lfWrites.push({
          step: window.lfWriteStep ?? null,
          key,
          type: record.type,
          attribute: record.attributeName,
          target: place(record.target),
        });
    }
  });
  const options = {
    subtree: true,
    attributes: true,
    childList: true,
    characterData: true,
    attributeOldValue: true,
    characterDataOldValue: true,
  };
  observer.observe(document, options);
  const attachShadow = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (init) {
    const root = attachShadow.call(this, init);
    observer.observe(root, options);
    return root;
  };
})();
