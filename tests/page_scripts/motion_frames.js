// Records where a floating box's painted parts stand at every frame, for a test that
// judges how they move (journeys/test_floating_box_motion.py). A test installs it as an init
// script after leaf_dev's frames.js, which reads the page once each frame has drawn, so
// the parts' translations and the surface's cuts that dom/box-motion.js animates stand as
// their animations sample them. The test brackets its inputs with
// `lfMotionFrames.begin({box, ring})`, the selectors of the box and of the ring its
// surface draws, and `lfMotionFrames.end()`, which returns the frames, waiting on
// `lfMotionFrames.count()` for the frames it needs on either side of them.
//
// Each part is read as the reader sees it, not as its box is laid out:
//
// - the box's outline, as its surface's ring is cut (dom/box-motion.js, `ground`), on
//   each of its four edges;
// - each control's box;
// - each run of words by its first letter, in the page and in every shadow tree under
//   the box, closed ones included, which the recorder keeps as they are attached.
//
// A part hidden, or reaching no farther than the window, is not read. The caret is not a
// part: the user's key moves it, by design in one frame.
(() => {
  const roots = new Set();
  const attach = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (init) {
    const root = attach.call(this, init);
    roots.add(root);
    return root;
  };
  let nextId = 1;
  const ids = new WeakMap();
  const idOf = (node) => {
    if (!ids.has(node)) ids.set(node, nextId++);
    return ids.get(node);
  };
  const round = (value) => Math.round(value * 10) / 10;
  const shown = (element) =>
    element.checkVisibility({ opacityProperty: true, visibilityProperty: true });
  const onScreen = (rect) =>
    rect.bottom > 0 &&
    rect.top < innerHeight &&
    rect.right > 0 &&
    rect.left < innerWidth;
  const name = (element) => {
    const own =
      element.localName +
      [...element.classList]
        .filter((token) => token.startsWith("lf-") || token.startsWith("cm-"))
        .map((token) => "." + token)
        .join("");
    const host = element.getRootNode().host;
    return host ? `${name(host)} >> ${own}` : own;
  };
  // Every node in `root`'s tree, and in the shadow trees of its hosts.
  function* nodes(root) {
    const walker = document.createTreeWalker(
      root,
      NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT,
    );
    for (let node = walker.currentNode; node; node = walker.nextNode()) {
      yield node;
      const tree = node.shadowRoot ?? [...roots].find((each) => each.host === node);
      if (tree) yield* nodes(tree);
    }
  }
  const letter = document.createRange();
  // The ring a box-motion surface draws, as its cut leaves it.
  const outline = (ring) => {
    const box = ring.getBoundingClientRect();
    const cut = /inset\(([^)]*?)(?: round [^)]*)?\)/.exec(
      getComputedStyle(ring).clipPath,
    );
    const [top, right = top, bottom = top, left = right] = cut
      ? cut[1].trim().split(/\s+/).map(parseFloat)
      : [0];
    return {
      left: box.left + left,
      top: box.top + top,
      right: box.right - right,
      bottom: box.bottom - bottom,
    };
  };
  function read(box, ring) {
    const parts = {};
    if (ring && shown(ring)) {
      const rect = outline(ring);
      for (const edge of ["left", "top", "right", "bottom"])
        parts[`outline ${edge}`] = { at: round(rect[edge]) };
    }
    for (const node of nodes(box)) {
      if (node.nodeType === Node.TEXT_NODE) {
        const start = node.data.search(/\S/);
        const holder = node.parentElement;
        if (start < 0 || !holder || !shown(holder)) continue;
        letter.setStart(node, start);
        letter.setEnd(node, start + 1);
        const rect = letter.getBoundingClientRect();
        if (!rect.width || !onScreen(rect)) continue;
        const key = `words ${idOf(node)} "${node.data.trim().slice(0, 20)}" in ${name(holder)}`;
        parts[`${key} x`] = { at: round(rect.left) };
        parts[`${key} y`] = { at: round(rect.top) };
      } else if (
        node.nodeType === Node.ELEMENT_NODE &&
        node.matches("button, [role=button]") &&
        shown(node)
      ) {
        const rect = node.getBoundingClientRect();
        if (!rect.width || !onScreen(rect)) continue;
        const key = `control ${idOf(node)} ${node.getAttribute("aria-label") ?? ""} ${name(node)}`;
        parts[`${key} x`] = { at: round(rect.left) };
        parts[`${key} y`] = { at: round(rect.top) };
      }
    }
    return Object.fromEntries(Object.entries(parts).map(([key, { at }]) => [key, at]));
  }
  window.lfMotionFrames = {
    begin({ box: boxSelector, ring: ringSelector }) {
      window.lfFrames.begin(() => {
        const box = document.querySelector(boxSelector);
        const ring = document.querySelector(ringSelector);
        return box ? read(box, ring) : {};
      });
    },
    // How many frames stand recorded.
    count: () => window.lfFrames.count(),
    // How many inputs the page has handled, which a test reads before each of its own:
    // a frame belongs to the input whose events it has seen.
    inputs: () => window.lfFrames.inputs(),
    end: () =>
      window.lfFrames.end().map(({ inputs, read: parts }) => ({ inputs, parts })),
  };
})();
