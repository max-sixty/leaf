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
  // its earlier value. Attribute order does not affect equality.
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
    const valueAt = (node, boundary) => {
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
      return [
        node.nodeType,
        node.namespaceURI,
        node.nodeName,
        text,
        [...attributes].sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)),
        children.map((child) => valueAt(child, boundary)),
        shadows.has(node) ? valueAt(shadows.get(node), boundary) : null,
      ];
    };
    return {
      position: (record) => positions.get(record),
      read: (nodes, boundary) =>
        JSON.stringify(nodes.map((node) => valueAt(node, boundary))),
    };
  };
  const renderedChildren = (nodes) =>
    [...nodes].filter((node) => node.nodeType !== Node.COMMENT_NODE);
  const restored = (target, records, readings) => {
    if (!records.some((record) => renderedChildren(record.removedNodes).length))
      return false;
    // Preserve the atomic check even when unrelated changes share its delivery.
    if (
      records.some((record) => {
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
      if ([...record.removedNodes].some((node) => residents.has(node))) {
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
        (pending.get(after.length) ?? []).includes(
          readings.read(after, readings.position(record) + 1),
        )
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
  // Writes that restate a value for a reason of their own, by the report they make.
  const EXPECTED = [
    // Mermaid's diagram renderers and their shared viewport helper both assign the SVG's
    // width while measuring the same drawing. Its upstream-owned paint is separate
    // from Leaf's adapter, which uses keeps when setting the final natural width.
    /^width on svg#lf-diagram-\d+(?:\.|$)/,
    // Mermaid's timeline wraps and measures labels by restating tspan text. Its
    // measurement groups have already detached by the observer's reading.
    /^children of tspan in text in g(?: in g\.timeline-node\.section--?\d+)?$/,
    // CodeMirror writes every attribute of its content element when it mounts a view,
    // the tab-size style that element already holds among them.
    /^style on div\.cm-content/,
    // CodeMirror reapplies this line decoration when the editor view updates, even
    // when the last line still holds the same words and the class is unchanged.
    /^class on div\.cm-line\.lf-field-last in shadow of leaf-text/,
    // CodeMirror's CompositeTile.sync replaces a line's children while reconciling
    // editor updates, including equivalent line-break nodes after clearing a field.
    /^children of div\.cm-line(?:\.[\w-]+)* in shadow of leaf-text(?:[.#]|$)/,
    // CodeMirror's GutterElement.setMarkers restates its class as marker sets
    // change, including when the resulting gutter class remains the same.
    /^class on div\.cm-gutterElement(?:\.| in shadow|$)/,
    // Web Awesome's components reflect each property onto the attribute it came from
    // as they update, and restate what their own shadow trees hold.
    /^[\w-]+ on wa-/,
    / in shadow of wa-[\w-]+/,
    // Vis Timeline reuses axis labels and grid nodes but restates their classes
    // and contents during redraw. Viewer.js similarly reapplies image/canvas
    // classes and magnifier visibility when an inspected image changes. These
    // are upstream-owned renderers; Leaf's adapter controls remain watched.
    /^(?:class|style|title|aria-hidden|children|text) (?:on|of) (?:div|img)\.(?:vis-|viewer-)/,
    // The contents map decides which face it needs, roomy, compact or an open outline,
    // by measuring its labels in each; a label's height is where it wraps in that face.
    /^data-lf-(compact|outline) on lf-toc/,
    // Sortable takes a dragged card's ghost class off and puts it back as the drag
    // crosses into another lane.
    /^class on .*\.lf-ghost/,
    // PhotoSwipe reasserts its root's zoom and pointer classes while handling
    // gestures and viewport changes, including when those classes already stand.
    /^class on div\.pswp(?:\.|$)/,
  ];
  const reported = new Set();
  // `what` is the attribute written, `text`, or `children`, and `node` the place.
  const report = (what, node) => {
    const words = what === "children" ? `children of ${node}` : `${what} on ${node}`;
    if (reported.has(words) || EXPECTED.some((known) => known.test(words))) return;
    reported.add(words);
    window.__leafWatchFinding({ code: "unchanged-write", what, node });
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
  // Residency verifies that authored CSS actually supplies a requested grid shift.
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
  const putBack = ({ record, through }) =>
    (record.attributeName === "tabindex" &&
      record.oldValue === null &&
      through.every((value) => value === "-1")) ||
    (record.attributeName === "class" &&
      record.target.matches(".lf-margin-cluster") &&
      through.every((value) => sameTokens(tokens(value), tokens(record.oldValue)))) ||
    columnProbe({ record, through }) ||
    nativeFocusGuard({ record, through });
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
        report(record.attributeName ?? "text", place(record.target));
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
        if (restored(target, changed, readings)) report("children", place(target));
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
