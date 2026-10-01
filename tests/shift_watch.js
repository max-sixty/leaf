// Watches every page for layout shifts the "Stability" rule forbids
// (skills/leaf/assets/AGENTS.md). The browser fixture installs it after write_watch.js
// on every ordinary test's page and on nightly tests marked watch_shifts
// (known_faults.py, `watches_shifts`).
//
// Chrome's Layout Instability API is the evidence: it compares painted frames, net of
// scrolling, so it sees a move that paints and is undone before any script could look,
// and names the elements that moved (the five that moved most, in a frame that moved
// more). It also says whether the user gave the page input in the half second before
// the frame (`hadRecentInput`; a key, a press or a resize is input, a script's click or
// a server's news is not). It credits none to a frame nested in another page, where a
// trusted key or press in the frame's own document, or in a same-origin document
// holding it, counts the same way. Text inserted without a key, as Playwright's `fill`
// and `insert_text` and a committed composition do, is not input to Chrome, but its
// trusted `beforeinput` is typing here. Two rules read the API:
//
// - Nothing moves without input. News, a page loading, and whatever a timer or a
//   server's answer changes may repaint a box or grow it into free room, but a box
//   Chrome reports moved in a frame without input moved something the user did not ask
//   to move. It is reported for every element the frame moved, once per element, named
//   by write_watch.js's `lfPlace`. The tests whose pages still do are
//   `known_faults.py`.
// - Typing never carries its field. A keystroke may grow its field, at whichever edge
//   its layout grows it: down in a card, up in a composer pinned to the panel's foot. It
//   never moves the field whole, as a "Draft" mark appearing in the header above a reply
//   box once did.
//
// Every input, a key, a press, a keystroke or a resize, has a rendering: the frames
// from the input until the first frame after the runtime's settled reading
// (runtime/rendering.js) says nothing it queued is waiting and no motion the input began
// still moves a box, the first such frame on a page without the runtime, a second at
// most, or the next input. The rendering says which frames that motion moved.
//
// News is the page adopting a server reading (`data-lf-reading`,
// runtime/presentation.js), the one a send of the user's returns included: what the
// user does is drawn in the turn they do it, before the server answers. Once the page
// has adopted news since the latest input began, every frame is without input whatever
// Chrome's flag says, until the next input: tests deliver a reply right after a press,
// and Chrome counts the reply's frames as the press's for half a second. Two kinds of
// frame stay the input's. Its first frame paints what the input drew, which news
// adopted before that frame paints beside; no reading tells the two apart, and judging
// it news failed a thread the user opened from its notice. And a frame in which motion
// the input began still runs, such as a panel sliding in, moves what the input asked
// to move: motion begun after the input and before the news, which may begin its own.
//
// Chrome's rects are what a node paints, a focus ring or a shadow included, clipped to
// the viewport, not the node's box. Nor are they always where it was on screen: Chrome
// measures a node against its nearest box that clips, at that box's place after the
// frame, and nets the scroll anchoring above that box only where every box between
// scrolls. A box that clips without scrolling (`overflow: hidden` or `clip`, or `auto`
// with nothing to scroll), as a diff's file does, drops it: where a reply grows a
// thread seated in the diff above the window and the root's anchoring holds what the
// user sees, Chrome reports the diff's rows below the thread as moved by the
// anchoring's amount. So at the start of every frame the box of every element, in the
// document and in every shadow tree, is read. A node Chrome reports moved without input
// is reported here only where its box differs among the readings at the start of the
// frame before the shift's, of the shift's own, and of the next. Neither of the first
// two alone is the box before the shift: a task's change before the shift's frame is
// already in the second, and what a frame callback after this one drew in the frame
// before is missing from the first. A move such a callback drew and a task took back
// before the next frame is in no reading. A node with no reading, as a text node, a
// pseudo-element or a node new to the page has none, is reported on Chrome's word.
//
// What the API cannot say is why a frame moved. A move the step before a keystroke laid
// out but had not yet painted, such as a widget a test removed by script, paints in the
// keystroke's first frame and would read as the typing's. So at each keystroke, a
// trusted `beforeinput` whose composed path names the field (a textarea, an input, or
// the host of a `leaf-text`'s closed editor), the box of the field and of every element
// holding it is read with a forced layout: every earlier change, and none of the
// keystroke's own. A shift Chrome reports during the keystroke's rendering is the
// typing's where it names one of those elements at a box, in the next frame's reading,
// whose opposite edges both differ from the key's. The typing rule stops reading the
// rendering early where something else may move the field: news, after which a reply
// arriving above the box moves it for its own reason; and a scroll of the document or
// an element holding the field, which moves every box after the reading at the key. A
// rendering whose first frame finds still running an animation that moves a box, one
// already running on the field or an element holding it at the key, as a panel's slide
// is when the user types into it before it stops, is left to neither rule: that motion
// is the gesture's that began it.
//
// Each finding is reported on the console as a browser problem, which fails the test
// like any other.
(() => {
  const WINDOW = 1000;
  const RECENT = 500;
  // How long what the observer may yet judge is kept: it hears of a frame's shifts a
  // task or more after the frame, which a loaded machine stretches.
  const KEPT = 10000;
  const prune = (list, time = (item) => item) => {
    const old = performance.now() - KEPT;
    while (list.length > 1 && time(list[0]) < old) list.shift();
  };
  const GEOMETRY =
    /^(transform|translate|scale|rotate|inset|top|left|right|bottom|width|height|margin|padding)/;
  // An element's parent in the composed tree, crossing from a shadow root to its host.
  const up = (node) =>
    node.parentNode instanceof ShadowRoot ? node.parentNode.host : node.parentNode;
  const holds = (node, field) => {
    for (let at = field; at; at = up(at)) if (at === node) return true;
    return false;
  };
  // What the API names, which it does not once the node is gone.
  const name = (node) => (node ? window.lfPlace(node) : "a node since removed");
  // Both edges moved the same way. A box that grew moved one edge, or both apart, as
  // the painted box of a field does when it gains its focus ring.
  const carried = (from, to, start, end) => {
    const near = to[start] - from[start];
    const far = to[end] - from[end];
    return (
      Math.abs(near) >= 1 && Math.abs(far) >= 1 && Math.sign(near) === Math.sign(far)
    );
  };
  const moved = (from, to) =>
    ["left", "top", "right", "bottom"].some(
      (edge) => Math.abs(to[edge] - from[edge]) >= 1,
    );
  const settled = () =>
    document.querySelector("script[data-lf-entry]")?.lfRenderingSettled?.() ?? true;
  // An animation that can move a box: one of its keyframes sets a geometric property.
  const moves = (animation) =>
    animation.effect
      ?.getKeyframes()
      .some((keyframe) => Object.keys(keyframe).some((key) => GEOMETRY.test(key))) ||
    GEOMETRY.test(animation.transitionProperty ?? "");
  // Motion begun since `start` that moves a box; one still pending begins now.
  const begun = (start) =>
    document
      .getAnimations()
      .filter(
        (animation) =>
          animation.playState === "running" &&
          (animation.startTime ?? Infinity) >= start &&
          moves(animation),
      );
  const boxes = (nodes) =>
    new Map([...nodes].map((node) => [node, node.getBoundingClientRect()]));
  // Every shadow root, a closed one included, so a reading reaches every element.
  const roots = new Set();
  const attachShadow = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (init) {
    const root = attachShadow.call(this, init);
    roots.add(root);
    return root;
  };
  const everything = () => {
    const nodes = [...document.querySelectorAll("*")];
    for (const root of roots)
      if (root.host.isConnected) nodes.push(...root.querySelectorAll("*"));
    return nodes;
  };
  // When each recent frame started, and each element's box at the start of every frame
  // that changed it: what the frame before painted. The element's box at the start of a
  // frame is its latest at or before it.
  const frames = [];
  const placed = new WeakMap();
  const read = (time) => {
    // The judging fixture's own reading may postdate the start of the frame after it.
    const at = Math.max(time, frames.at(-1) ?? time);
    frames.push(at);
    prune(frames);
    for (const node of everything()) {
      const rect = node.getBoundingClientRect();
      const seen = placed.get(node) ?? [];
      const last = seen.at(-1)?.rect;
      if (
        last?.left === rect.left &&
        last.top === rect.top &&
        last.right === rect.right &&
        last.bottom === rect.bottom
      )
        continue;
      seen.push({ at, rect });
      prune(seen, (item) => item.at);
      placed.set(node, seen);
    }
  };
  const boxAt = (node, at) => placed.get(node)?.findLast((item) => item.at <= at)?.rect;
  // Each input's rendering: when it began; the start of its second frame; the motion
  // it began, and the start of the latest frame that motion moved; whether news has
  // landed since; and a keystroke's typing, which holds its field; the box of the field
  // and of each element holding it at the key; the animations already moving any of
  // them; and until when the typing rule reads it.
  const renderings = [];
  let open = null;
  // The typing rule stops reading the open rendering, which runs on.
  const unwatch = () => {
    if (open?.typing?.until === Infinity) open.typing.until = performance.now();
  };
  const end = () => {
    unwatch();
    open = null;
  };
  const begin = (start, typing = null) => {
    end();
    open = {
      start,
      first: true,
      second: Infinity,
      moved: -Infinity,
      own: new Set(),
      motion: false,
      told: false,
      last: false,
      typing,
    };
    renderings.push(open);
    prune(renderings, (rendering) => rendering.start);
  };
  // Shifts whose frame has no reading after it yet.
  const waiting = [];
  const tick = (at) => {
    read(at);
    if (open) {
      // The input's motion is what began after it and before news since it, which
      // may begin motion of its own. Still running here, it moves this frame, as it
      // moved the one before if it ran at that frame's start, finishing in it.
      if (!open.told)
        for (const animation of begun(open.start)) open.own.add(animation);
      const motion = [...open.own].some(({ playState }) => playState === "running");
      if (motion || open.motion) open.moved = at;
      open.motion = motion;
      // Motion the key found under way carries the field for the gesture that began
      // it, so a rendering whose first frame finds it still running is no one's to
      // judge: its frames are that motion's.
      if (open.first) {
        if (open.typing?.moving.some(({ playState }) => playState === "running"))
          open.typing.free = true;
      } else if (open.second === Infinity) open.second = at;
      open.first = false;
      if (open.last || at - open.start > WINDOW) end();
      // A settled reading here counts updates before this one; this frame's own
      // callbacks may still move a box, so the rendering runs through the next.
      else open.last = settled() && !motion;
    }
    judge(waiting.splice(0));
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
  document.addEventListener(
    "beforeinput",
    (event) => {
      if (!event.isTrusted) return;
      const field = event.composedPath()[0];
      const holding = [];
      for (let at = field; at instanceof Element; at = up(at)) holding.push(at);
      begin(event.timeStamp, {
        field,
        found: boxes(holding),
        moving: holding.flatMap((node) => node.getAnimations()).filter(moves),
        free: false,
        until: Infinity,
      });
    },
    true,
  );
  // A resize is input to Chrome, and lays the page out anew, the field with it.
  window.addEventListener("resize", (event) => begin(event.timeStamp));
  document.addEventListener(
    "scroll",
    (event) => {
      if (open?.typing && holds(event.target, open.typing.field)) unwatch();
    },
    true,
  );
  // When the page adopted each server reading.
  const news = [];
  new MutationObserver(() => {
    unwatch();
    if (open) open.told = true;
    news.push(performance.now());
    prune(news);
  }).observe(document, { subtree: true, attributeFilter: ["data-lf-reading"] });
  // Every recent key or press is kept: the observer may judge a frame after a later
  // key.
  const presses = [];
  const heard = (view) => (event) => {
    if (!event.isTrusted) return;
    const at = event.timeStamp + view.performance.timeOrigin - performance.timeOrigin;
    presses.push(at);
    prune(presses);
    begin(at);
  };
  for (let view = window; ; view = view.parent) {
    let held;
    try {
      held = view.document;
    } catch {
      break;
    }
    for (const type of ["keydown", "pointerdown"])
      held.addEventListener(type, heard(view), true);
    if (view === view.parent) break;
  }
  // `frame` is the start of the shift's frame.
  const input = (entry, rendering, frame) => {
    const at = entry.startTime;
    const since = rendering?.start ?? -Infinity;
    const drawn = rendering && (frame < rendering.second || frame <= rendering.moved);
    if (!drawn && news.some((n) => n > since && n <= at)) return false;
    return (
      entry.hadRecentInput ||
      presses.some((press) => press <= at && at - press < RECENT)
    );
  };
  const reported = new Set();
  const report = (what, detail) => {
    if (reported.has(what)) return;
    reported.add(what);
    console.error(`${what}${detail}`);
  };
  const box = ({ left, top, width, height }) =>
    `${Math.round(left)},${Math.round(top)} ${Math.round(width)}x${Math.round(height)}`;
  const by = (from, to) =>
    ` by (${Math.round(to.left - from.left)}, ${Math.round(to.top - from.top)})px`;
  const beside = (sources, node) => {
    const others = sources
      .filter((source) => source.node !== node)
      .map((source) => name(source.node));
    return others.length ? `; the same frame moved ${others.join(", ")}` : "";
  };
  // One known defect is every page's, so it is known here by when it happens rather than
  // in `known_faults.py` by test: widgets upgrade after the authored document has painted,
  // and the frame that presents the page carries every box their upgrade reshaped. The
  // page before it is presented runs until the second frame after the runtime stamps
  // `data-lf-presented` on a page that has one (runtime/presentation.js). Fixing the
  // defect deletes this.
  let presented = null;
  new MutationObserver(() => {
    if (presented !== null || !document.body?.hasAttribute("data-lf-presented")) return;
    presented = Infinity;
    requestAnimationFrame(() =>
      requestAnimationFrame((at) => {
        presented = at;
      }),
    );
  }).observe(document, { subtree: true, attributeFilter: ["data-lf-presented"] });
  const presenting = ({ startTime }) =>
    document.querySelector("script[data-lf-entry]") &&
    (presented === null || startTime < presented);
  // `before` and `after` are the starts of the frames either side of the shift's.
  // `frame` indexes the start of the shift's frame in `frames`.
  const unasked = (entry, frame) => {
    if (presenting(entry)) return;
    const around = frame < 1 ? [] : frames.slice(frame - 1, frame + 2);
    for (const { node, previousRect, currentRect } of entry.sources) {
      const read = node ? around.map((at) => boxAt(node, at)) : [];
      if (
        read.length === 3 &&
        read.every(Boolean) &&
        !read.some((box) => moved(box, read[2]))
      )
        continue;
      report(
        `${name(node)} moved without input`,
        by(previousRect, currentRect) + beside(entry.sources, node),
      );
    }
  };
  // Chrome's rects are what a node paints, clipped to the viewport, so they are held
  // against the frame's own reading, never against the key's.
  const typed = (entry, typing, painted) => {
    for (const { node } of entry.sources) {
      const before = typing.found.get(node);
      const after = before && boxAt(node, painted);
      if (
        !before ||
        !after ||
        (!carried(before, after, "top", "bottom") &&
          !carried(before, after, "left", "right"))
      )
        continue;
      report(
        `typing in ${window.lfPlace(typing.field)} moved ${window.lfPlace(node)}`,
        by(before, after) +
          `; the key found ${box(before)}, the frame painted ${box(after)}` +
          beside(entry.sources, node),
      );
    }
  };
  const judge = (entries) => {
    for (const entry of entries) {
      const at = entry.startTime;
      // The frame that painted the shift, and the next, whose start reads what it
      // painted. Readings older than are kept are gone (-1).
      const frame = frames.findLastIndex((time) => time <= at);
      const next = frames[frame + 1];
      if (frame !== -1 && next === undefined) {
        waiting.push(entry);
        continue;
      }
      const rendering = renderings.findLast(({ start }) => start <= at);
      const typing = rendering?.typing;
      if (typing && at <= typing.until) {
        // A frame the typing rule stopped reading before the next one is no one's.
        if (!typing.free && frame !== -1 && next <= typing.until)
          typed(entry, typing, next);
      } else if (!input(entry, rendering, frames[frame] ?? -Infinity))
        unasked(entry, frame);
    }
  };
  const observer = new PerformanceObserver((list) => judge(list.getEntries()));
  observer.observe({ type: "layout-shift" });
  // A frame's shifts reach the observer only once it paints, and a task or more after,
  // so a test whose last act moves the page would end before the report. The browser
  // fixture awaits this as the test body returns: the frames the last act changed paint,
  // then every shift so far is judged. Chrome paints no frame for a page it is not
  // drawing, so that wait is capped, and a shift still waiting for the next frame's
  // reading is judged against one taken then.
  window.lfShiftsJudged = () =>
    new Promise((resolve) => {
      let judged = false;
      const drain = () => {
        if (judged) return;
        judged = true;
        read(performance.now());
        judge([...waiting.splice(0), ...observer.takeRecords()]);
        resolve();
      };
      requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(drain)));
      setTimeout(drain, 500);
    });
})();
