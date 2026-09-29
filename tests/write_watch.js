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
// While `window.lfWrites` is an array, every write is also appended to it, numbered by
// `window.lfWriteStep`, for a test that reads what a gesture wrote (scroll_writes).
(() => {
  const place = (node) =>
    node.nodeType === 1
      ? `${node.localName}${node.id ? "#" + node.id : ""}` +
        `${node.classList.length ? "." + [...node.classList].join(".") : ""}`
      : `${node.nodeName} in ${node.parentElement ? place(node.parentElement) : "nothing"}`;
  const serial = (nodes) =>
    [...nodes].map((node) => node.outerHTML ?? node.data ?? "").join("");
  let count = 0;
  const numbered = new WeakMap();
  const number = (node) => {
    if (!numbered.has(node)) numbered.set(node, ++count);
    return numbered.get(node);
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
        console.error(
          `unchanged write: ${record.attributeName ?? "text"} on ${place(record.target)}`,
        );
    started.clear();
  };
  const observer = new MutationObserver((records) => {
    for (const record of records) {
      const key = `${number(record.target)} ${record.type} ${record.attributeName}`;
      if (record.type === "childList") {
        const removed = serial(record.removedNodes);
        if (removed !== "" && removed === serial(record.addedNodes))
          console.error(`unchanged write: children of ${place(record.target)}`);
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
