// Watches every page for a line of occupants that grows or shrinks as one occupant
// gives way to another: the "Shared containers determine control dimensions" rule
// (browser/AGENTS.md, "The page holds still under the user's aim"). The browser fixture installs it on every page a test
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
//   reason. A place taller than its tallest occupant on the taller side holds
//   several lines or other room, so it is not a line sized by that occupant;
// - the change reaches the box that holds the row: a row inside a line that keeps its
//   height, as a crumb inside a taller controls row, shows the reader nothing;
// - the taller occupant is no taller for its content, which the rule lets grow a
//   place: it is not an SVG drawing or a field holding words that grow the field,
//   as a reply box that arrives with its draft does, and kept the height it appeared
//   at while it stood, which a comment box grown to two lines did not, though Send
//   emptied it in the frame it gave way to the reply. A one-line input's words never
//   size it.
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
// A MutationObserver over the document and every shadow root supplies arrivals and
// departures, and the boxes are read from the update that paints them: in each update
// the page changed anything in, an IntersectionObserver reads every flex row, its
// occupants and the box around each row, after that update's every ResizeObserver
// delivery and before its paint. That one reading gives an element's first box, the
// height it appeared at, each box a swap is judged against and each it is judged by,
// all in the coordinates the user sees, transforms included; a size that leaves or
// reaches zero is a child hiding or showing. The previous box is the one the last such
// update read, so a box that changes with nothing in the page changing, as an image or
// a font arriving or a transition running, is judged against the box before it. A
// hidden tab runs no update, so what it changed is read in the first update after it
// returns, which the return covers. A subtree that leaves is let go.
//
// Rejected: reading the boxes with a ResizeObserver. Watching a row changes the depth
// at which the browser delivers the page's own observers below it, so a page observer
// on a deeper box that validly changes the row in its delivery became a loop error, and
// one started inside a delivery was one too, however long the watch waited to start it.
(() => {
  const { frame, listen } = window.lfWatchPlatform;
  const sizes = new WeakMap();
  // The height each element had when it last appeared, inserted or shown.
  const appeared = new WeakMap();
  const roots = new WeakMap();
  // A box as the user sees it, and nothing for an inline box or one that draws none.
  const box = (element, rect) =>
    /^(inline|contents|none)$/.test(getComputedStyle(element).display)
      ? { width: 0, height: 0 }
      : { width: rect.width, height: rect.height };
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
  // A shadow tree attached by script reaches the patched `attachShadow` below; an open
  // one the parser built from a declarative template is found when its host arrives.
  const adopt = (root) => {
    roots.set(root.host, root);
    changes.observe(root, options);
  };
  function* elementsOf(node) {
    if (node.nodeType !== Node.ELEMENT_NODE) return;
    yield node;
    if (node.shadowRoot && !roots.has(node)) adopt(node.shadowRoot);
    if (roots.has(node))
      for (const child of roots.get(node).children) yield* elementsOf(child);
    for (const child of node.children) yield* elementsOf(child);
  }
  // A field whose height grows with its words, or a drawing whose own geometry
  // determines its height. An icon nested in a control does not excuse the control.
  const holdsContent = (element) =>
    element.localName === "svg" ||
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
    frame(() => {
      for (const element of elementsOf(document.documentElement)) watchArrival(element);
    });
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
  const watched = new Set();
  const flexRows = new WeakSet();
  const flexRow = (element) => {
    if (!element?.isConnected) return false;
    const { display, flexDirection } = getComputedStyle(element);
    return display.endsWith("flex") && flexDirection.startsWith("row");
  };
  // The next update's reading of every watched box, asked for once the page changes
  // anything: an IntersectionObserver gives each box it starts watching an entry from the
  // update that follows. Its entries are that update's, judged together as soon as the
  // watch is next called, and before any record taken after them.
  let asked = false;
  const ask = () => {
    if (asked) return;
    asked = true;
    for (const element of watched) reading.observe(element);
  };
  const painted = (entries) => {
    if (!entries.length) return;
    asked = false;
    const now = new Map();
    for (const { target, boundingClientRect } of entries) {
      reading.unobserve(target);
      if (target.isConnected) now.set(target, box(target, boundingClientRect));
    }
    judge(now, (element) => now.get(element) ?? sizes.get(element) ?? measure(element));
  };
  const reading = new IntersectionObserver(painted);
  const observeOnce = (element) => {
    if (!element || watched.has(element)) return;
    watched.add(element);
    ask();
    reading.observe(element);
  };
  const watchArrival = (element) => {
    // Leaf has not presented its first arrangement yet. Its widgets may still
    // hide panels, so observing their descendants now can force premature style.
    if (!presented && document.querySelector("script[data-lf-entry]")) return false;
    // Only a flex row, its occupants and its container contribute to this rule, and
    // every update the page changes anything in reads each box watched.
    // `hidden="until-found"` keeps a panel's own box while skipping its contents.
    // Even checkVisibility() would force that content through style resolution.
    if (element.parentElement?.closest("[hidden]")) return false;
    if (element.hasAttribute("hidden")) {
      if (flexRows.has(up(element))) {
        observeOnce(element);
        return true;
      }
      return false;
    }
    const direct = up(element);
    if (flexRows.has(direct)) {
      observeOnce(element);
      return true;
    }
    // A hidden panel can grow without being styled by Leaf. The watch must not
    // force its descendants through computed style just to rule them out.
    if (!element.checkVisibility()) return false;
    const parent = holder(direct);
    const row = flexRow(element) ? element : flexRow(parent) ? parent : null;
    if (!row) return false;
    flexRows.add(row);
    observeOnce(row);
    observeOnce(holder(up(row)));
    if (element !== row) observeOnce(element);
    return true;
  };
  const letGo = (element) => {
    reading.unobserve(element);
    watched.delete(element);
    flexRows.delete(element);
  };
  const release = (node) => {
    if (node.isConnected) return;
    for (const element of elementsOf(node)) letGo(element);
  };
  const take = (records, from) => {
    painted(reading.takeRecords());
    if (records.length) ask();
    for (const record of records) {
      // Any write names the input behind the frame; hiding a child is an attribute's.
      if (from) source = from;
      if (record.type === "attributes") {
        if (record.target.isConnected) written.add(record.target);
        if (record.attributeName === "hidden" && record.target.hasAttribute("hidden"))
          for (const child of record.target.children)
            for (const element of elementsOf(child)) letGo(element);
        if (
          record.target !== document.body &&
          record.target !== document.documentElement &&
          (record.attributeName === "hidden" || !watched.has(record.target))
        )
          for (const element of elementsOf(record.target)) watchArrival(element);
      }
      if (record.type !== "childList") continue;
      for (const node of record.removedNodes)
        if (node.nodeType === Node.ELEMENT_NODE) {
          if (flexRows.has(holder(record.target)))
            departed.push({ node, parent: record.target, size: sizes.get(node) });
          else release(node);
        }
      for (const node of record.addedNodes)
        for (const element of elementsOf(node)) {
          if (watchArrival(element)) arrived.add(element);
        }
    }
    // An attribute changed before its owner left can still be in this batch.
    // An unrelated detached subtree has no row to judge and must not be kept alive.
    for (const element of written) if (!element.isConnected) written.delete(element);
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
    const style = getComputedStyle(place);
    const { display, flexDirection } = style;
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
    const insets = [
      "paddingTop",
      "paddingBottom",
      "borderTopWidth",
      "borderBottomWidth",
    ].reduce((sum, name) => sum + parseFloat(style[name]), 0);
    // A wrapping list takes room for all its lines, not just its tallest control.
    // Judge the taller side, including when those lines are being put away.
    if (Math.max(before.height, after.height) > taller.size.height + insets + 1)
      return false;
    if (stood.some((height) => height >= taller.size.height - 0.5)) return false;
    const container = holder(up(place));
    const was = container && sizes.get(container);
    const is = container && read(container);
    if (!was || !is || Math.abs(is.height - was.height) < 1) return false;
    return (
      !holdsContent(taller.child) &&
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
      for (const { node } of departed) release(node);
    } finally {
      arrived = new Set();
      departed = [];
      written = new Set();
      source = null;
    }
  };
  // Judging before the frame reads the layout as the update's reading would, in the
  // same coordinates. What changed since the frame is what was inserted or removed, or
  // written to: an element whose attributes changed, or anything inside it, as a panel's
  // mode attribute shows one occupant and hides another. A class on the root or the
  // body, which the runtime sets as the pointer moves, is left to the next frame, since
  // reading the whole page at every press cost tens of milliseconds.
  // Only a key and the pointer's first event start a gesture: the mouse and touch
  // events that follow a pointerdown run in its task, before any frame.
  const measure = (element) => box(element, element.getBoundingClientRect());
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
    adopt(root);
    return root;
  };

  // The fixture drains the shift watch before this reading. That drain waits for the
  // last painted frames when the page is visible and finishes without frames when a
  // tab or embedded page is hidden. A second frame wait here would hang in an
  // offscreen frame, whose document still reports visibilityState === "visible".
  window.lfSwapsJudged = async () => {
    await window.lfInputWork.dispatched();
    painted(reading.takeRecords());
  };
})();
