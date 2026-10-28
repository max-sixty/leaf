// Watches every DOM write a page makes, in its document and in each shadow root, from
// before the first byte parses. The browser fixture installs it on every page a test
// opens (render_harness.watched).
//
// A write that changes nothing is reported as an `unchanged-write` record through the
// fixture's `__leafWatchFinding` binding, a browser problem that fails the test like any
// other. "Nothing" is judged per script, up to the microtask
// checkpoint that ends it (an event listener, a frame callback, a task), which is when
// the observer delivers: the writes one script makes to one place (an attribute, a text
// node's data) change nothing when the place ends the script holding the value it
// started with, whether the script restated it or took it away and put it back, and a
// child-list write changes nothing when it puts back rendered nodes equal to the ones
// it took out. Comments draw no content; renderers such as Lit replace their ownership
// markers while updating real content, so comment-only restoration is not judged.
// Such a rendered write still costs a style pass and a repaint, of the whole document while
// a CSS highlight holds a range, so code writes only what changed
// (browser/AGENTS.md).
//
// Each finding is reported once per document: a writer that fires every frame would
// otherwise bury the report under its own repetitions.
//
// While `window.lfWrites` is an array, every write is also appended to it, numbered by
// `window.lfWriteStep`, for a test that reads what a gesture wrote (scroll_writes).
(() => {
  // Where a node stands, as the steps a reader finds it by, innermost first: an element
  // by its tag, id and classes (`div#id.class`), any other node by its name (`#text`).
  // A step with neither id nor class is followed by its parent, and the last step in a
  // shadow tree by `#shadow-root` and the tree's host, so `div.cm-line` in a
  // `leaf-text#field` is `["div.cm-line", "#shadow-root", "leaf-text#field"]`.
  // Findings carry the steps; `leaf/findings.py` writes their words.
  const place = (node) => {
    const element = node.nodeType === 1;
    const step = element
      ? `${node.localName}${node.id ? "#" + node.id : ""}` +
        `${node.classList.length ? "." + [...node.classList].join(".") : ""}`
      : node.nodeName;
    if ((!element || (!node.id && !node.classList.length)) && node.parentElement)
      return [step, ...place(node.parentElement)];
    const root = node.getRootNode();
    return root instanceof ShadowRoot
      ? [step, "#shadow-root", ...place(root.host)]
      : [step];
  };
  // Naming is shared with the shift sensor, including in opaque child frames.
  window.lfPlace = place;

  // Server-allocated samples run Leaf and share its DOM-write contract. Other
  // opaque previews may disable scripts, which refuses observer callbacks with
  // console errors; their containing page remains watched.
  const leafSample = /\/api\/samples\/[a-f0-9]{32}(?:\/|$)/.test(location.pathname);
  if (window !== window.top && globalThis.origin === "null" && !leafSample) return;

  // Read one script's child-list changes together: remove() followed by append()
  // delivers two records, unlike replaceChildren(), but can restate the same list.
  // Nodes in native records stay live. Read only the compared subtree at a record
  // boundary, undoing its later native changes rather than treating today's node as
  // its earlier value. Attribute order does not affect equality. A list re-rendered
  // row by row is read once per record, so each subtree nothing wrote into is read
  // once per batch: reading every subtree at every record made a 76-row table's
  // re-render take a second.
  const batchReadings = (records) => {
    const changes = new Map();
    const positions = new Map();
    const shadows = new Map(
      [...trees]
        .filter((tree) => tree instanceof ShadowRoot)
        .map((root) => [root.host, root]),
    );
    records.forEach((record, position) => {
      positions.set(record, position);
      if (!changes.has(record.target)) changes.set(record.target, []);
      changes.get(record.target).push({ record, position });
    });
    // Each node whose subtree, shadow trees included, holds a written node now. A
    // subtree the batch wrote into at any point holds one still: a node a write took
    // out of it was taken out by a write to a node within it. So any other subtree
    // holds the same at every boundary.
    const written = new Set();
    for (const target of changes.keys())
      for (
        let node = target;
        node && !written.has(node);
        node = node instanceof ShadowRoot ? node.host : node.parentNode
      )
        written.add(node);
    // A node's value at a boundary, its shadow tree included, as a string, which is
    // the same string at every boundary for a subtree nothing wrote into.
    const unwritten = new Map();
    const valueAt = (node, boundary) => {
      if (written.has(node)) return readAt(node, boundary);
      if (!unwritten.has(node)) unwritten.set(node, readAt(node, boundary));
      return unwritten.get(node);
    };
    const readAt = (node, boundary) => {
      const children = [...node.childNodes];
      const attributes = new Map(
        [...(node.attributes ?? [])].map((attribute) => [
          JSON.stringify([attribute.namespaceURI, attribute.localName]),
          attribute.value,
        ]),
      );
      let text = node.nodeValue;
      for (const { record, position } of [...(changes.get(node) ?? [])].reverse()) {
        if (position < boundary) break;
        if (record.type === "childList") {
          for (const added of record.addedNodes)
            children.splice(children.indexOf(added), 1);
          const at = record.nextSibling
            ? children.indexOf(record.nextSibling)
            : children.length;
          children.splice(at, 0, ...record.removedNodes);
        } else if (record.type === "attributes") {
          const key = JSON.stringify([record.attributeNamespace, record.attributeName]);
          if (record.oldValue === null) attributes.delete(key);
          else attributes.set(key, record.oldValue);
        } else text = record.oldValue;
      }
      const own = JSON.stringify([
        node.nodeType,
        node.namespaceURI,
        node.nodeName,
        text,
        [...attributes].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)),
      ]);
      const inner = children.map((child) => valueAt(child, boundary)).join(",");
      const shadow = shadows.has(node) ? valueAt(shadows.get(node), boundary) : null;
      return `[${own},[${inner}],${shadow}]`;
    };
    return {
      position: (record) => positions.get(record),
      read: (nodes, boundary) =>
        `[${nodes.map((node) => valueAt(node, boundary)).join(",")}]`,
    };
  };
  // Detaching an iframe retires its browsing context even if the same element is
  // reinserted before observer delivery; DOM equality cannot see that change.
  const hasFrame = (node) =>
    node instanceof HTMLIFrameElement ||
    [...node.childNodes].some(hasFrame) ||
    [...trees].some(
      (tree) => tree instanceof ShadowRoot && tree.host === node && hasFrame(tree),
    );
  const renderedChildren = (nodes) =>
    [...nodes].filter((node) => node.nodeType !== Node.COMMENT_NODE);
  const restored = (target, records, readings) => {
    const frameRecords = new Set(
      records.filter((record) =>
        [...record.removedNodes, ...record.addedNodes].some(hasFrame),
      ),
    );
    const ordinary = records.filter((record) => !frameRecords.has(record));
    if (!ordinary.some((record) => renderedChildren(record.removedNodes).length))
      return false;
    // Preserve the atomic check even when unrelated changes share its delivery.
    if (
      ordinary.some((record) => {
        const removed = renderedChildren(record.removedNodes);
        const position = readings.position(record);
        return (
          removed.length &&
          readings.read(removed, position) ===
            readings.read(renderedChildren(record.addedNodes), position + 1)
        );
      })
    )
      return true;
    // Undo the native records once, then replay their actual sequence. A restored
    // interval is still redundant when a later record adds meaningful content.
    const current = [...target.childNodes];
    for (const record of [...records].reverse()) {
      for (const node of record.addedNodes) current.splice(current.indexOf(node), 1);
      const at = record.nextSibling
        ? current.indexOf(record.nextSibling)
        : current.length;
      current.splice(at, 0, ...record.removedNodes);
    }
    // A freshly introduced measuring node can come and go without rewriting a
    // resident. Snapshots live only in this callback and compare equal lengths.
    const residents = new Set(renderedChildren(current));
    const pending = new Map();
    for (const record of records) {
      if (
        !frameRecords.has(record) &&
        [...record.removedNodes].some((node) => residents.has(node))
      ) {
        const before = renderedChildren(current);
        if (!pending.has(before.length)) pending.set(before.length, []);
        pending
          .get(before.length)
          .push(readings.read(before, readings.position(record)));
      }
      for (const node of record.removedNodes) current.splice(current.indexOf(node), 1);
      const at = record.nextSibling
        ? current.indexOf(record.nextSibling)
        : current.length;
      current.splice(at, 0, ...record.addedNodes);
      const after = renderedChildren(current);
      if (
        !frameRecords.has(record) &&
        pending.has(after.length) &&
        pending
          .get(after.length)
          .includes(readings.read(after, readings.position(record) + 1))
      )
        return true;
    }
    return false;
  };
  let count = 0;
  const numbered = new WeakMap();
  const number = (node) => {
    if (!numbered.has(node)) numbered.set(node, ++count);
    return numbered.get(node);
  };
  // Writes that restate a value for a reason of their own, each a test of what was
  // written (an attribute, `text`, or `children`) and the live node it was written on.
  const is = (node, selector) => node.nodeType === 1 && node.matches(selector);
  // The hosts of the shadow trees holding a node, innermost first.
  const hosts = (node) => {
    const found = [];
    for (let root = node.getRootNode(); root instanceof ShadowRoot;) {
      found.push(root.host);
      root = root.host.getRootNode();
    }
    return found;
  };
  const EXPECTED = [
    // A repeated live announcement replaces its text node so assistive technology
    // hears a fresh arrival even when the words match the previous announcement.
    (what, node) => what === "children" && is(node, "div.lf-ui.lf-live"),
    // Lit's keyed repeat moves equivalent marker nodes when a visual action in
    // the group changes identity, while the rendered controls update in place.
    (what, node) => what === "children" && is(node, "div.lf-visual-actions"),
    // CodeMirror writes every attribute of its content element when it mounts a view,
    // the tab-size style that element already holds among them.
    (what, node) => what === "style" && is(node, "div.cm-content"),
    // CodeMirror's setAttrs assigns a line's style whenever it syncs the line's
    // attributes, as a list item's line carries its depth and number.
    (what, node) =>
      what === "style" && is(node, "div.cm-line.lf-md-item") && hosts(node).length > 0,
    // CodeMirror also restates a line's decoration class when it reconciles an
    // editor update, even when the preview gives that line the same face.
    (what, node) =>
      what === "class" &&
      is(node, "div.cm-line") &&
      hosts(node)[0]?.localName === "leaf-text",
    // CodeMirror's CompositeTile.sync replaces a line's children while reconciling
    // editor updates, including equivalent line-break nodes in either editor host.
    (what, node) =>
      what === "children" && is(node, "div.cm-line") && hosts(node).length > 0,
    // CodeMirror's GutterElement.setMarkers restates its class as marker sets
    // change, including when the resulting gutter class remains the same.
    (what, node) => what === "class" && is(node, "div.cm-gutterElement"),
    // CodeMirror's syncGutters reinserts the gutter beside unchanged content when
    // its editor view updates.
    (what, node) =>
      what === "children" &&
      is(node, "div.cm-scroller") &&
      hosts(node)[0]?.localName === "lf-file-editor",
    // Web Awesome's components reflect each property onto the attribute it came from
    // as they update, and restate what their own shadow trees hold.
    (what, node) => what !== "children" && node.localName?.startsWith("wa-"),
    (what, node) => hosts(node).some((host) => host.localName.startsWith("wa-")),
    // Trees restores native row focus after closing search, restating the focus
    // marker its row renderer already painted.
    (what, node) =>
      what === "data-item-focused" &&
      is(node, 'button[role="treeitem"]') &&
      hosts(node)[0]?.localName === "lf-file-tree",
    // Viewer.js reapplies image/canvas classes and magnifier visibility when an
    // inspected image changes. It is an upstream-owned renderer; Leaf's adapter
    // controls remain watched.
    (what, node) =>
      ["class", "style", "title", "aria-hidden", "children"].includes(what) &&
      is(node, ":is(div, img):is([class^='viewer-'], [class*=' viewer-'])"),
    // The contents map decides which face it needs, roomy, compact or an open outline,
    // by measuring its labels in each; a label's height is where it wraps in that face.
    (what, node) =>
      ["data-lf-compact", "data-lf-outline"].includes(what) && is(node, "lf-toc"),
    // Sortable takes a dragged card's ghost class off and puts it back as the drag
    // crosses into another lane.
    (what, node) => what === "class" && is(node, ".lf-ghost"),
    // Sortable's drop sets the pressed card's `draggable` to false on every release of
    // its grip, whether or not the press became a drag.
    (what, node) => what === "draggable" && is(node, "lf-card"),
    // PhotoSwipe reasserts its root's zoom and pointer classes while handling
    // gestures and viewport changes, including when those classes already stand.
    (what, node) => what === "class" && is(node, "div.pswp"),
  ];
  const reported = new Set();
  // `what` is the attribute written, `text`, or `children`, and `node` the node written.
  const report = (what, node) => {
    if (EXPECTED.some((expected) => expected(what, node))) return;
    const finding = { code: "unchanged-write", what, node: place(node) };
    const key = JSON.stringify(finding);
    if (reported.has(key)) return;
    reported.add(key);
    window.__leafWatchFinding(finding);
  };
  const valueOf = (record) =>
    record.type === "attributes"
      ? record.target.getAttributeNS(record.attributeNamespace, record.attributeName)
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
  // Native layer posture and focus eligibility are browser state, not reflected
  // attributes. close→showModal changes a nonmodal dialog to modal while `open`
  // returns to the same value. A temporary inert layer suppresses opening focus;
  // inerting the document and its modal roots suppresses native return focus on
  // close. Modals escape ancestor inertness, including inside closed shadow roots.
  // Credit only roots inhibited during an actual native transition and only inert
  // roundtrips that changed eligibility; unrelated restatements remain failures.
  const trees = new Set([document]);
  let dialogTransitions = new WeakSet();
  let focusGuards = new WeakSet();
  const posture = (dialog) =>
    dialog.matches(":modal") ? "modal" : dialog.open ? "nonmodal" : "closed";
  const watchNativeTransitions = (prototype, methods, read) => {
    for (const method of methods) {
      const native = prototype[method];
      prototype[method] = function (...args) {
        const before = read(this);
        const inhibited = (
          before === "closed"
            ? [this]
            : [
                document.documentElement,
                ...[...trees].flatMap((tree) => [
                  ...tree.querySelectorAll("dialog:modal"),
                ]),
              ]
        ).filter((node) => node.isConnected && node.inert);
        const result = native.apply(this, args);
        if (read(this) !== before) {
          if (prototype === HTMLDialogElement.prototype) dialogTransitions.add(this);
          for (const node of inhibited) focusGuards.add(node);
        }
        return result;
      };
    }
  };
  watchNativeTransitions(
    HTMLDialogElement.prototype,
    ["show", "showModal", "close"],
    posture,
  );
  watchNativeTransitions(
    HTMLElement.prototype,
    ["showPopover", "hidePopover", "togglePopover"],
    (popover) => (popover.matches(":popover-open") ? "popover" : "closed"),
  );
  const nativeTransition = (record) =>
    record.attributeName === "open" && dialogTransitions.has(record.target);
  const nativeFocusGuard = ({ record, through }) =>
    record.attributeName === "inert" &&
    record.oldValue === null &&
    through.some((value) => value !== null) &&
    focusGuards.has(record.target);
  // Margin layout verifies that authored CSS actually supplies a requested grid shift.
  // An ignored request is withdrawn in the same reading; every other style member
  // must remain unchanged. A settled failed placement must not probe again (the
  // authored-track browser test separately asserts zero subsequent mutations).
  const columnProbe = ({ record, through }) => {
    if (record.attributeName !== "style" || record.target !== document.body)
      return false;
    const withoutShift = (value) => {
      const style = document.createElement("div").style;
      style.cssText = value ?? "";
      style.removeProperty("--lf-column-shift");
      return style.cssText;
    };
    const before = withoutShift(record.oldValue);
    return (
      through.some((value) => value !== record.oldValue) &&
      through.every((value) => withoutShift(value) === before)
    );
  };
  // Reopening a menu during its closing fade retains the status nodes. holdMenu
  // measures their fresh text without the previous opening's line limits, then
  // restores the limits. Equal dimensions still required that layout read. Credit
  // only removal/restoration of those limits, never a direct repeated assignment.
  const menuMeasurement = ({ record, through }) =>
    through.every((value) => value === null) &&
    ((record.attributeName === "data-held" &&
      record.oldValue === "" &&
      is(record.target, "div.lf-fp-state")) ||
      (record.attributeName === "style" &&
        /^--lines: \d+$/.test(record.oldValue ?? "") &&
        is(
          record.target,
          ".lf-fp-state > :is(span.lf-fp-summary, span.lf-fp-explain)",
        )));
  const putBack = ({ record, through }) =>
    (record.attributeName === "tabindex" &&
      record.oldValue === null &&
      through.every((value) => value === "-1")) ||
    (record.attributeName === "class" &&
      record.target.matches(".lf-margin-cluster") &&
      through.every((value) => sameTokens(tokens(value), tokens(record.oldValue)))) ||
    columnProbe({ record, through }) ||
    nativeFocusGuard({ record, through }) ||
    menuMeasurement({ record, through });
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
        !nativeTransition(record) &&
        !(through.length && putBack(write))
      )
        report(record.attributeName ?? "text", record.target);
    }
    started.clear();
    dialogTransitions = new WeakSet();
    focusGuards = new WeakSet();
  };
  const watch = (records) => {
    const children = new Map();
    for (const record of records) {
      const key = JSON.stringify([
        number(record.target),
        record.type,
        record.attributeNamespace,
        record.attributeName,
      ]);
      if (record.type === "childList") {
        if (!children.has(record.target)) children.set(record.target, []);
        children.get(record.target).push(record);
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
          ...(record.type === "childList"
            ? { nodes: [...record.removedNodes, ...record.addedNodes].map(number) }
            : {}),
        });
    }
    if (children.size) {
      const readings = batchReadings(records);
      for (const [target, changed] of children)
        if (restored(target, changed, readings)) report("children", target);
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
    trees.add(root);
    observer.observe(root, options);
    return root;
  };
})();
