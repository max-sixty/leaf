// Watches every page for a line of occupants that grows or shrinks as one occupant
// gives way to another: the "What takes turns in a place doesn't size it" rule
// (browser/AGENTS.md, "Stability"). The browser fixture installs it on every page a test
// opens (render_harness.watched), so every test checks it.
//
// A swap is a frame in which a box stays on the page while, among its children, one
// that drew a box stops drawing one and another starts: removed and inserted, moved in
// from elsewhere, hidden and shown, or any mix. A child counts by its rendered parent,
// so one slotted into a shadow tree counts in its slot, and a `display: contents`
// parent hands its children to the box that holds them. The frame is the unit rather
// than the task, since a renderer may take one occupant away in the gesture's task and
// draw the next in its frame; a swap a renderer spreads over two frames is not seen. A
// box that drew nothing before or after, or that itself arrived in the frame, holds no
// place. A test's next key or press often comes before the browser paints what the last
// one changed, and a swap it undoes would never be painted, so a trusted key or pointer
// press first judges what changed since the last frame as the page then lays it out
// (`judgeNow`).
//
// The watch judges a place that lays its occupants out in a line, a flex row, and only
// its height, the size across the line. Growth along a line moves the occupants beside
// the one that changed, which the shift watch reports; growth across it, a row standing
// on its foot that rises at its top, moves no word or control in the row, so the shift
// watch passes it, as it passed page search standing the floating panel's row taller
// than the comment field it replaced. Three readings keep a firing to an occupant
// sizing its place:
//
// - the row's height changes the way its tallest occupant's does, and that occupant
//   is the row's tallest child on its side of the swap: a row that grows as a shorter
//   occupant arrives, or as a field beside the arrival takes a line, grew for another
//   reason;
// - the change reaches the box that holds the row: a row inside a line that keeps its
//   height, as a crumb inside a taller controls row, shows the reader nothing;
// - the taller occupant is no taller for its content, which the rule lets grow a
//   place: it holds no words in a field that grows with them, as a reply box that
//   arrives with its draft does, and kept the height it appeared at while it stood,
//   which a comment box grown to two lines did not, though Send emptied it in the frame
//   it gave way to the reply. A one-line input's words never size it.
//
// Rejected: judging every place in every axis. Nearly all its firings were views, lists
// and cards growing with what they show, the content the rule allows. A flex column's
// width, a grid and an inline line are outside the rule as written here; each column
// that fired in the survey was a card or a list taking the width of its words.
//
// Where a swap sizes its row, the watch reports a `place-resized` record through the
// fixture's `__leafWatchFinding` binding, once per place and pair of occupants, a
// browser problem that fails the test like any other. It judges a gesture's swap and
// news' alike, naming the input that caused it where input_work_watch.js attributes one.
// It doesn't judge the page before it presents, or as it returns from a hidden tab, both
// until two frames after the runtime says so, as the shift watch counts them, nor the
// two frames after a window resize, where container queries may swap occupants and
// every place take a new size.
//
// The sizes come from one ResizeObserver on every element: each frame's reading is the
// layout the frame painted, read after layout and before paint, and an element's
// previous size is the one the observer last reported. Children's arrivals and
// departures come from a MutationObserver over the document and every shadow root;
// showing and hiding come from the same ResizeObserver, as a size that leaves or reaches
// zero. A subtree that leaves the page and stays away is unobserved, so the watch holds
// no node the page let go. Observing every element has one cost a page can see: a
// ResizeObserver callback of the page's own that resizes an element shallower than its
// target leaves this observer a notice it can't deliver that frame, which the browser
// reports as a loop error. Leaf's runtime defers such writes to the next frame
// (rendering.js), and no test in the survey met one.
(() => {
  const { frame, listen } = window.lfWatchPlatform;
  const sizes = new WeakMap();
  // The height each element had when it last appeared, inserted or shown.
  const appeared = new WeakMap();
  const roots = new WeakMap();
  const box = (entry) => {
    const [size] = entry.borderBoxSize;
    return { width: size.inlineSize, height: size.blockSize };
  };
  const draws = (size) => !!size && size.width > 0 && size.height > 0;
  const up = (node) => node.assignedSlot ?? node.parentElement ?? node.parentNode?.host;
  // The box that holds a child: its rendered parent, past any `display: contents`. A
  // document, which `document.open()` empties, holds no place.
  const holder = (parent) => {
    let at = parent instanceof ShadowRoot ? parent.host : parent;
    while (at instanceof Element && getComputedStyle(at).display === "contents")
      at = up(at);
    return at instanceof Element ? at : null;
  };
  // The children a place lays out: its shadow tree's where it hosts one, through any
  // `display: contents` child, and a slot's assigned elements in the slot's place.
  const laidOut = (box) => {
    if (box.localName !== "slot") return (roots.get(box) ?? box).children;
    const assigned = box.assignedElements({ flatten: true });
    return assigned.length ? assigned : box.children;
  };
  function* seatedIn(place) {
    for (const child of laidOut(place))
      if (getComputedStyle(child).display === "contents") yield* seatedIn(child);
      else yield child;
  }
  function* elementsOf(node) {
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    yield node;
    if (roots.has(node))
      for (const child of roots.get(node).children) yield* elementsOf(child);
    for (const child of node.children) yield* elementsOf(child);
  }
  // Watching an element again makes the observer report its size at the next frame,
  // even where that is the size it last reported; observing it a second time without
  // letting go first reports nothing.
  const watch = (element) => {
    resizes.unobserve(element);
    resizes.observe(element, { box: "border-box" });
  };
  // A field whose height grows with its words, as words_watch.js reads them.
  const holdsWords = (element) =>
    [...elementsOf(element)].some(
      (field) =>
        field.matches("textarea, [contenteditable], leaf-text") &&
        (typeof field.value === "string" ? field.value : field.textContent).trim(),
    );

  // Each exemption lasts until the second frame after its cause, so the page's own
  // reaction to it, a frame later, is exempt too.
  const exemptions = new Map();
  const exempt = (cause) => {
    const turn = {};
    exemptions.set(cause, turn);
    frame(() =>
      frame(() => {
        if (exemptions.get(cause) === turn) exemptions.delete(cause);
      }),
    );
  };
  listen(window, "resize", () => exempt("resize"));
  let returning = false;
  listen(document, "lf-reading-continuity", ({ detail }) => {
    returning = !detail.continuous;
    if (detail.continuous) exempt("return");
  });
  let presented = false;
  const presentation = new MutationObserver(() => {
    if (!document.body?.hasAttribute("data-lf-presented")) return;
    presentation.disconnect();
    presented = true;
    exempt("presentation");
  });
  presentation.observe(document, {
    subtree: true,
    attributeFilter: ["data-lf-presented"],
  });
  const judged = () =>
    exemptions.size === 0 &&
    !returning &&
    (presented || !document.querySelector("script[data-lf-entry]"));

  // What changed since the last judgement among each place's children, the elements
  // whose attributes were written, and the last input behind it.
  let arrived = new Set();
  let departed = [];
  let written = new Set();
  let source = null;
  const take = (records, from) => {
    for (const record of records) {
      // Any write names the input behind the frame; hiding a child is an attribute's.
      if (from) source = from;
      if (record.type === "attributes") written.add(record.target);
      if (record.type !== "childList") continue;
      for (const node of record.removedNodes)
        if (node.nodeType === Node.ELEMENT_NODE)
          departed.push({ node, parent: record.target, size: sizes.get(node) });
      for (const node of record.addedNodes)
        for (const element of elementsOf(node)) {
          arrived.add(element);
          watch(element);
        }
    }
  };

  const reported = new Set();
  const report = (place, before, after, left, came) => {
    const name = (node) => window.lfPlace(node);
    const finding = {
      code: "place-resized",
      place: name(place),
      left: left.map(({ child }) => name(child)),
      arrived: came.map(({ child }) => name(child)),
    };
    const key = JSON.stringify(finding);
    if (reported.has(key)) return;
    reported.add(key);
    window.__leafWatchFinding({
      ...finding,
      before,
      after,
      input: source?.event.type ?? null,
    });
  };
  const tallest = (side) =>
    side.reduce((most, seat) => (seat.size.height > most.size.height ? seat : most));
  const sizedBy = (place, before, after, left, came, read) => {
    const { display, flexDirection } = getComputedStyle(place);
    if (!display.endsWith("flex") || !flexDirection.startsWith("row")) return false;
    const grew = after.height - before.height;
    if (Math.abs(grew) < 1) return false;
    const [arriving, leaving] = [tallest(came), tallest(left)];
    if ((arriving.size.height - leaving.size.height) * grew <= 0) return false;
    // The children that stood through the swap, at their size on the taller side.
    const swapped = new Set([...left, ...came].map(({ child }) => child));
    const stood = [...seatedIn(place)]
      .filter((child) => !swapped.has(child))
      .map((child) => (grew > 0 ? read(child) : sizes.get(child))?.height ?? 0);
    const taller = grew > 0 ? arriving : leaving;
    if (stood.some((height) => height >= taller.size.height - 0.5)) return false;
    const container = holder(up(place));
    const was = container && sizes.get(container);
    const is = container && read(container);
    if (!was || !is || Math.abs(is.height - was.height) < 1) return false;
    return (
      !holdsWords(taller.child) &&
      Math.abs(taller.size.height - appeared.get(taller.child)) < 1
    );
  };

  // Judges what changed since the last judgement from `now`, the sizes read since,
  // and `read`, an element's size as it stands.
  const judge = (now, read) => {
    try {
      const places = new Map();
      const seat = (parent, side, child, size) => {
        const place = parent && holder(parent);
        if (!place?.isConnected || arrived.has(place)) return;
        if (!places.has(place)) places.set(place, { left: [], came: [] });
        places.get(place)[side].push({ child, size });
      };
      for (const [element, size] of now) {
        const was = sizes.get(element);
        if (arrived.has(element) || !element.isConnected || was === undefined) continue;
        if (draws(was) && !draws(size)) seat(up(element), "left", element, was);
        else if (!draws(was) && draws(size)) {
          appeared.set(element, size.height);
          seat(up(element), "came", element, size);
        }
      }
      // A child taken out and put back in the same place, as a keyed list reorders,
      // takes no seat: it was there already.
      const stayed = new Set(
        departed
          .filter(({ node, size }) => draws(size) && node.isConnected)
          .filter(({ node, parent }) => holder(parent) === holder(up(node)))
          .map(({ node }) => node),
      );
      for (const element of arrived) {
        if (!element.isConnected || !draws(read(element))) continue;
        appeared.set(element, read(element).height);
        if (!arrived.has(up(element)) && !stayed.has(element))
          seat(up(element), "came", element, read(element));
      }
      for (const { node, parent, size } of departed)
        if (!node.isConnected && draws(size)) seat(parent, "left", node, size);
      if (judged())
        for (const [place, { left, came }] of places) {
          if (!left.length || !came.length) continue;
          const before = sizes.get(place);
          const after = read(place);
          if (
            draws(before) &&
            draws(after) &&
            sizedBy(place, before, after, left, came, read)
          )
            report(place, before, after, left, came);
        }
      for (const [element, size] of now) sizes.set(element, size);
      for (const { node } of departed)
        if (!node.isConnected)
          for (const element of elementsOf(node)) resizes.unobserve(element);
    } finally {
      arrived = new Set();
      departed = [];
      written = new Set();
      source = null;
    }
  };
  const resizes = new ResizeObserver((entries) => {
    take(changes.takeRecords(), window.lfInputWork.current());
    const now = new Map(entries.map((entry) => [entry.target, box(entry)]));
    judge(now, (element) => now.get(element) ?? sizes.get(element));
  });
  // Judging before the frame reads the layout as the observer would: the border box,
  // and nothing for an inline box, which the observer reports as empty. What changed
  // since the frame is what was inserted or removed, or written to: an element whose
  // attributes changed, or anything inside it, as a panel's mode attribute shows one
  // occupant and hides another. A class on the root or the body, which the runtime sets
  // as the pointer moves, is left to the next frame, since reading the whole page at
  // every press cost tens of milliseconds. Each element read is watched again, so the
  // next frame reports its size even where it returns to the one the observer last
  // reported.
  // Only a key and the pointer's first event start a gesture: the mouse and touch
  // events that follow a pointerdown run in its task, before any frame.
  const measure = (element) => {
    if (/^(inline|contents|none)$/.test(getComputedStyle(element).display))
      return { width: 0, height: 0 };
    if (element instanceof HTMLElement)
      return { width: element.offsetWidth, height: element.offsetHeight };
    const { width, height } = element.getBoundingClientRect();
    return { width, height };
  };
  const judgeNow = (event) => {
    if (!event.isTrusted) return;
    take(changes.takeRecords(), window.lfInputWork.current());
    if (!arrived.size && !departed.length && !written.size) return;
    const now = new Map();
    const read = (element) => {
      if (!now.has(element)) now.set(element, measure(element));
      return now.get(element);
    };
    for (const element of written)
      if (
        element.isConnected &&
        element !== document.body &&
        element !== document.documentElement
      )
        for (const each of elementsOf(element)) if (sizes.has(each)) read(each);
    judge(now, read);
    for (const element of now.keys()) if (element.isConnected) watch(element);
  };
  for (const type of ["keydown", "pointerdown"]) listen(window, type, judgeNow, true);
  const changes = new MutationObserver((records) =>
    take(records, window.lfInputWork.current()),
  );
  const options = { subtree: true, childList: true, attributes: true };
  changes.observe(document, options);
  // Records belong to the input whose callback made them: read them at each of its
  // checkpoints, before the observer would deliver them without it.
  window.lfInputWork.subscribe((from) => take(changes.takeRecords(), from));
  const attachShadow = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (init) {
    const root = attachShadow.call(this, init);
    roots.set(this, root);
    changes.observe(root, options);
    return root;
  };

  // Judgement waits for the frame that lays out the test's last act; a page the browser
  // doesn't render has no frame to wait for.
  window.lfSwapsJudged = async () => {
    await window.lfInputWork.dispatched();
    if (document.visibilityState !== "visible") return;
    await new Promise((resolve) => frame(() => frame(resolve)));
  };
})();
