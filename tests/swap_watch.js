// Watches every page for a line of occupants that grows or shrinks as one occupant
// gives way to another: the "What takes turns in a place doesn't size it" rule
// (browser/AGENTS.md, "Stability"). The browser fixture installs it on every page a test
// opens (render_harness.watched), so every test checks it.
//
// A swap is a frame in which a box keeps its place on the page while, among its
// children, one that drew a box stops drawing one and another that drew none starts:
// removed and inserted, hidden and shown, or any mix. A child counts by its rendered
// parent, so one slotted into a shadow tree counts in its slot, and a `display:
// contents` parent hands its children to the box that holds them. The frame is the unit
// rather than the task, since a renderer may take one occupant away in the gesture's
// task and draw the next in its frame. A box that drew nothing before or after, or that
// itself arrived in the frame, holds no place. A test's next key or press often comes
// before the browser paints what the last one changed, and a swap it undoes would
// never be painted, so a trusted key or press first judges what changed since the last
// frame as the page then lays it out (`judgeNow`).
//
// The watch judges a place that lays its occupants out in a line, a flex row, and only
// its height, the size across the line. Growth along a line moves the occupants beside
// the one that changed, which the shift watch reports; growth across it, a row standing
// on its foot that rises at its top, moves no word or control in the row, so the shift
// watch passes it, as it passed page search standing the floating panel's row taller
// than the comment field it replaced. Three readings keep a firing to an occupant
// sizing its place:
//
// - the row's height changes the way its tallest occupant's does: a row that grows as a
//   shorter occupant arrives grew for another reason, such as a field beside it taking
//   a line;
// - the change reaches the box that holds the row: a row inside a line that keeps its
//   height, as a crumb inside a taller controls row, shows the reader nothing;
// - the taller occupant is no taller for its content, which the rule lets grow a
//   place: it holds no typed words, as a reply box that arrives with its draft does,
//   and kept the height it appeared at while it stood, which a comment box grown to two
//   lines did not, though Send emptied it in the frame it gave way to the reply.
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
// of which the shift watch exempts for the same reasons, nor a frame the window was
// resized in, where container queries may swap occupants and every place take a new
// size.
//
// The sizes come from one ResizeObserver on every element: each frame's reading is the
// layout the frame painted, read after layout and before paint, and an element's
// previous size is the one the observer last reported. Children's arrivals and
// departures come from a MutationObserver over the document and every shadow root;
// showing and hiding come from the same ResizeObserver, as a size that leaves or reaches
// zero. A subtree that leaves the page and stays away is unobserved, so the watch holds
// no node the page let go.
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
  // The box that holds a child: its rendered parent, past any `display: contents`.
  const holder = (parent) => {
    let at = parent instanceof ShadowRoot ? parent.host : parent;
    while (at && getComputedStyle(at).display === "contents") at = up(at);
    return at ?? null;
  };
  function* elementsOf(node) {
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    yield node;
    if (roots.has(node))
      for (const child of roots.get(node).children) yield* elementsOf(child);
    for (const child of node.children) yield* elementsOf(child);
  }
  // Fields as words_watch.js reads them: a text input, a textarea, an editable element,
  // or a `leaf-text`, whose `value` is its text.
  const TYPED = new Set(["text", "search", "url", "email", "tel", "number"]);
  const holdsWords = (element) =>
    [...elementsOf(element)].some(
      (field) =>
        (field.localName === "input"
          ? TYPED.has(field.type)
          : field.matches("textarea, [contenteditable], leaf-text")) &&
        (typeof field.value === "string" ? field.value : field.textContent).trim(),
    );

  let resized = false;
  listen(window, "resize", () => {
    resized = true;
  });
  // The page before it presents runs until the second frame after the runtime stamps
  // `data-lf-presented`, and a hidden-tab return until the runtime's continuity
  // boundary says the reading is continuous again (shift_watch.js, `presenting`).
  let presented = null;
  const presentation = new MutationObserver(() => {
    if (presented !== null || !document.body?.hasAttribute("data-lf-presented")) return;
    presented = false;
    presentation.disconnect();
    frame(() =>
      frame(() => {
        presented = true;
      }),
    );
  });
  presentation.observe(document, {
    subtree: true,
    attributeFilter: ["data-lf-presented"],
  });
  let returning = false;
  listen(document, "lf-reading-continuity", ({ detail }) => {
    returning = !detail.continuous;
  });
  const judged = () =>
    !resized &&
    !returning &&
    (presented === true || !document.querySelector("script[data-lf-entry]"));

  // What the frame changed among each place's children, the elements whose attributes
  // it wrote, and the last input behind it.
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
          sizes.delete(element);
          resizes.observe(element, { box: "border-box" });
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
    const container = holder(up(place));
    const was = container && sizes.get(container);
    const is = container && read(container);
    if (!was || Math.abs(is.height - was.height) < 1) return false;
    const taller = grew > 0 ? arriving : leaving;
    return (
      !holdsWords(taller.child) &&
      Math.abs(taller.size.height - appeared.get(taller.child)) < 1
    );
  };

  // Judges what changed since the last judgement from `now`, the sizes read since,
  // and `read`, an element's size as it stands.
  const judge = (now, read) => {
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
    for (const element of arrived) {
      if (!element.isConnected || !draws(read(element))) continue;
      appeared.set(element, read(element).height);
      if (!arrived.has(up(element))) seat(up(element), "came", element, read(element));
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
    arrived = new Set();
    departed = [];
    written = new Set();
    source = null;
    resized = false;
  };
  const resizes = new ResizeObserver((entries) => {
    take(changes.takeRecords(), window.lfInputWork.current());
    const now = new Map(entries.map((entry) => [entry.target, box(entry)]));
    judge(now, (element) => now.get(element) ?? sizes.get(element));
  });
  // A test's input often comes before the browser paints what the last one changed, so
  // a trusted key or press first judges that change as the page now lays it out. Only
  // what it wrote can have been shown or hidden: an element whose attributes changed,
  // or a child of one. Each element read is observed afresh, so the next frame reports
  // its size even where it returns to the one the observer last reported.
  const measure = (element) =>
    element instanceof HTMLElement
      ? { width: element.offsetWidth, height: element.offsetHeight }
      : (({ width, height }) => ({ width, height }))(element.getBoundingClientRect());
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
      if (element.isConnected)
        for (const each of [element, ...element.children])
          if (sizes.has(each)) read(each);
    judge(now, read);
    for (const element of now.keys())
      if (element.isConnected) resizes.observe(element, { box: "border-box" });
  };
  for (const type of ["keydown", "pointerdown", "mousedown", "touchstart"])
    listen(window, type, judgeNow, true);
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
