// Watches every DOM write a page makes, in its document and in each shadow root, from
// before the first byte parses. The browser fixture installs it on every page a test
// opens (render_harness.watched).
//
// A write that changes nothing is reported on the console as a browser problem, which
// fails the test like any other. "Nothing" is judged per script, up to the microtask
// checkpoint that ends it (an event listener, a frame callback, a task), which is when
// the observer delivers: the writes one script makes to one place (an attribute, a text
// node's data) change nothing when the place ends the script holding the value it
// started with, whether the script restated it or took it away and put it back, and a
// child-list write changes nothing when it puts back nodes equal to the ones it took
// out. Such a write still costs a style pass and a repaint, of the whole document while
// a CSS highlight holds a range, so code writes only what changed
// (skills/leaf/assets/AGENTS.md).
//
// Each finding is reported once per document: a writer that fires every frame would
// otherwise bury the report under its own repetitions.
//
// While `window.lfWrites` is an array, every write is also appended to it, numbered by
// `window.lfWriteStep`, for a test that reads what a gesture wrote (scroll_writes).
(() => {
  // An element by its tag, id and classes, one with neither by where it stands, and one
  // in a shadow tree by the tree's host too.
  const place = (node) => {
    if (node.nodeType !== 1)
      return `${node.nodeName} in ${node.parentElement ? place(node.parentElement) : "nothing"}`;
    const named =
      `${node.localName}${node.id ? "#" + node.id : ""}` +
      `${node.classList.length ? "." + [...node.classList].join(".") : ""}`;
    if (!node.id && !node.classList.length && node.parentElement)
      return `${named} in ${place(node.parentElement)}`;
    const root = node.getRootNode();
    return root instanceof ShadowRoot
      ? `${named} in shadow of ${place(root.host)}`
      : named;
  };
  // Nodes put back as the ones taken out: the same count, each equal to its twin.
  const restored = ({ removedNodes, addedNodes }) =>
    removedNodes.length > 0 &&
    removedNodes.length === addedNodes.length &&
    [...removedNodes].every((node, at) => node.isEqualNode(addedNodes[at]));
  let count = 0;
  const numbered = new WeakMap();
  const number = (node) => {
    if (!numbered.has(node)) numbered.set(node, ++count);
    return numbered.get(node);
  };
  // Writes that restate a value for a reason of their own, by the report they make.
  const EXPECTED = [
    // CodeMirror writes every attribute of its content element when it mounts a view,
    // the tab-size style that element already holds among them.
    /^style on div\.cm-content/,
    // Web Awesome's components reflect each property onto the attribute it came from
    // as they update, and restate what their own shadow trees hold.
    /^[\w-]+ on wa-/,
    / in shadow of wa-[\w-]+/,
    // The contents map decides which face it needs, roomy, compact or an open outline,
    // by measuring its labels in each; a label's height is where it wraps in that face.
    /^data-lf-(compact|outline) on lf-toc/,
    // Sortable takes a dragged card's ghost class off and puts it back as the drag
    // crosses into another lane.
    /^class on .*\.lf-ghost/,
    // TODO(2026-09-28): a comment's visual mark is placed twice in one script where the
    // part it marks moves (target-paint.js, `paintTargets`); seen on diagram parts and
    // a visual action following its scroller. Not yet traced to the second placement.
    /^style on div\.lf-ui\.lf-visual-mark/,
  ];
  const reported = new Set();
  const report = (what) => {
    if (reported.has(what) || EXPECTED.some((known) => known.test(what))) return;
    reported.add(what);
    console.error(`unchanged write: ${what}`);
  };
  const valueOf = (record) =>
    record.type === "attributes"
      ? record.target.getAttribute(record.attributeName)
      : record.target.data;
  // Writes that take a value away and put it back for a reason of their own, by the
  // values they passed through. An arrival lends an element a tab stop to move where the
  // next Tab starts, and gives it back on the blur (focus.js, `lendStop`), at once where
  // the element will not take the focus. And the margin shows a withheld row for the
  // moment it takes to measure where the row would stand, which a row withheld as
  // `display: none` cannot answer, and withholds it again where that is outside what
  // its pane shows (margin-layout.js, `layoutMarginRows`).
  const tokens = (value) => new Set([...(value ?? "").split(" "), "lf-withheld"]);
  const sameTokens = (a, b) => a.size === b.size && [...a].every((t) => b.has(t));
  const putBack = ({ record, through }) =>
    (record.attributeName === "tabindex" &&
      record.oldValue === null &&
      through.every((value) => value === "-1")) ||
    (record.attributeName === "class" &&
      record.target.matches(".lf-margin-cluster") &&
      through.every((value) => sameTokens(tokens(value), tokens(record.oldValue))));
  // An element reference set through reflection (`ariaDetailsElements`, and the rest of
  // the aria-*Elements family) writes an empty attribute whatever the elements are, so
  // an empty value that stays empty says nothing about whether the relation changed.
  const reflected = (record) =>
    record.attributeName?.startsWith("aria-") && record.oldValue === "";
  // The first write to each place in this script, with each value the place passed
  // through after it.
  const started = new Map();
  const judge = () => {
    for (const write of started.values()) {
      const { record, through } = write;
      if (
        valueOf(record) === record.oldValue &&
        !reflected(record) &&
        !(through.length && putBack(write))
      )
        report(`${record.attributeName ?? "text"} on ${place(record.target)}`);
    }
    started.clear();
  };
  const watch = (records) => {
    for (const record of records) {
      const key = `${number(record.target)} ${record.type} ${record.attributeName}`;
      if (record.type === "childList") {
        if (restored(record)) report(`children of ${place(record.target)}`);
      } else if (started.has(key)) started.get(key).through.push(record.oldValue);
      else {
        started.set(key, { record, through: [] });
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
    judge();
  };
  const observer = new MutationObserver(watch);
  const options = {
    subtree: true,
    attributes: true,
    childList: true,
    characterData: true,
    attributeOldValue: true,
    characterDataOldValue: true,
  };
  observer.observe(document, options);
  // An instrument reads a page by changing it and putting it back: the render gate
  // resolves a paint through a custom property set on the element and renders a widget
  // at its authored baseline before restoring it, and a test lifts a state off a control
  // to read what it would wear without it. Those are the instrument's writes, not the
  // page's, so what a synchronous reading inside `lfUnwatched` writes is dropped: it is
  // all still pending when the reading returns. The gate's probes are synchronous
  // (render-checks/driver.js), so each probe call is one such reading.
  const unwatched = (read) => {
    watch(observer.takeRecords());
    try {
      return read();
    } finally {
      observer.takeRecords();
    }
  };
  window.lfUnwatched = unwatched;
  // typing_watch.js names what moved the same way.
  window.lfPlace = place;
  const probing = (driver) =>
    driver &&
    Object.freeze({
      ...driver,
      call: (request) => unwatched(() => driver.call(request)),
    });
  // The driver may be installed before this script or after it.
  let driver = probing(globalThis.__leafRenderDriver);
  Object.defineProperty(globalThis, "__leafRenderDriver", {
    configurable: true,
    get: () => driver,
    set: (installed) => {
      driver = probing(installed);
    },
  });
  const attachShadow = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (init) {
    const root = attachShadow.call(this, init);
    observer.observe(root, options);
    return root;
  };
})();
