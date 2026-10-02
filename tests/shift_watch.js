// Checks the Stability contract using protected reading/control landmarks.
// Chrome admits painted layout transitions; a retained per-frame ledger supplies
// their meaning. Source rectangles do not choose which landmarks get examined, so
// anonymous sources, decorative pseudos and the five-source cap cannot excuse a
// surviving control or reading line that was carried. Native visibility records
// closed disclosure content correctly; sampled hidden layout is not painted text.
//
// A box may grow or shrink at one edge while text and controls remain stationary.
// Reading text is measured with Range fragments, including text inside a stationary
// parent. Controls and declared regions keep their actual boxes. Runtime-declared
// bounded reflow retains its historical ownership, stationary-boundary and clipping
// proof. Layout coordinates remove scrolling; sticky descendants retain their
// mechanical scroller's ownership. Portals with one unique same-tree anchor and
// a direct native anchor inset retain that scroller too; nested CSS expressions
// and ambiguous names receive no inferred ownership.
//
// Each trusted gesture owns its bounded rendering, including geometry motion it
// began. News starts passive rendering except the first frame shared with the
// gesture or continuing motion already owned by it. A typing field is observed at
// beforeinput, independently of Chrome's clipped/shadowed source rectangles. Motion
// already running on its ancestors belongs to the gesture that began that motion.
// Continuing translation is credited from sampled animated property values, not
// the ancestor's whole box: independent movement of it or its children still fails.
// This proof supports unique replace effects with pure transform translation or
// pixel left/top/marginLeft/marginTop. Scale, rotation and composed effects receive
// no inferred translation credit.
//
// Chrome's paint signal and landmark poses answer distinct questions. The ledger
// retains samples that precede the source-associated frame window and is classified
// before paint admission, so delayed observer delivery cannot erase a sampled move.
// A never-painted roundtrip is dismissed; matching source motion can corroborate a
// sampled roundtrip already restored when the observer hears it. Transform-only
// motion produces no Layout Instability event and is outside this paint signal.
// A painted one-frame roundtrip omitted from Chrome's sources and reverted before
// any subsequent sampled pose remains an unresolved observability limit.
//
// Every finding fails the ordinary browser fixture. It installs this sensor after
// write_watch.js and binds the canonical runtime/control-selectors.js declaration.
(() => {
  const WINDOW = 1000;
  // How long what the observer may yet judge is kept: it hears of a frame's shifts a
  // task or more after the frame, which a loaded machine stretches.
  const KEPT = 10000;
  const prune = (list, time = (item) => item, retain = 1) => {
    const old = performance.now() - KEPT;
    while (list.length > retain && time(list[0]) < old) list.shift();
  };
  const GEOMETRY =
    /^(transform|translate|scale|rotate|inset|top|left|right|bottom|width|height|margin|padding)/;
  // An element's parent in the composed tree, crossing from a shadow root to its host.
  const up = (node) =>
    node.parentNode instanceof ShadowRoot ? node.parentNode.host : node.parentNode;
  // Decorative media is not an independent reading. Hidden accessibility trees
  // include hoisted target paint and icon faces; their retained text/controls are
  // still measured separately, so this declaration cannot hide a moved button.
  const readingMedia = (element) => {
    if (!element.matches("img, svg, canvas, video, iframe, object, [role=img]"))
      return false;
    if (element.matches('[role="presentation"], [role="none"]')) return false;
    for (let at = element; at instanceof Element; at = up(at))
      if (at.getAttribute("aria-hidden") === "true") return false;
    return true;
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
  // A direct native anchor inset, not an unused var() fallback or a named
  // different anchor inside the expression. Floating placement writes this form.
  const anchorInset = (value, axis) => {
    const side =
      axis === "left"
        ? "(?:left|right|center|start|end)"
        : "(?:top|bottom|center|start|end)";
    const anchor = `anchor\\(${side}(?:,\\s*-?[\\d.]+px)?\\)`;
    return new RegExp(
      `^(?:${anchor}|calc\\((?:${anchor}\\s*[+-]\\s*-?[\\d.]+px|-?[\\d.]+px\\s*\\+\\s*${anchor}|${anchor})\\))$`,
    ).test(value);
  };
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
    const words = nodes.flatMap((node) =>
      [...node.childNodes].filter(
        (child) =>
          child.nodeType === Node.TEXT_NODE &&
          child.textContent.trim() &&
          !node.matches("script, style"),
      ),
    );
    return [...nodes, ...words];
  };
  // Each frame keeps its node population; geometry and paint evidence keep changes
  // only. Later hiding, clipping, reparenting or removal cannot erase a sampled box.
  const frames = [];
  const placed = new WeakMap();
  const scrolled = new WeakMap();
  const animated = new WeakMap();
  const animationProperties = (animation) => [
    ...new Set(
      animation.effect
        .getKeyframes()
        .flatMap((frame) => Object.keys(frame).filter((key) => GEOMETRY.test(key))),
    ),
  ];
  const animationTranslation = (property, value) => {
    if (property === "transform") {
      const matrix = new DOMMatrixReadOnly(value === "none" ? undefined : value);
      return matrix.is2D &&
        matrix.a === 1 &&
        matrix.b === 0 &&
        matrix.c === 0 &&
        matrix.d === 1
        ? { left: matrix.e, top: matrix.f }
        : null;
    }
    if (
      ["left", "top", "marginLeft", "marginTop"].includes(property) &&
      /^-?[\d.]+px$/.test(value)
    )
      return {
        left: property.endsWith("Left") || property === "left" ? parseFloat(value) : 0,
        top: property.endsWith("Top") || property === "top" ? parseFloat(value) : 0,
      };
    return null;
  };
  const read = (time, frame = true) => {
    // Poses belong to their synchronous observation time. The native frame start
    // is kept separately to associate Chrome's painted shift with that frame.
    const at = performance.now();
    const effects = document.getAnimations().filter(moves);
    const uses = new Map();
    for (const animation of effects) {
      if (animation.effect.getComputedTiming().progress === null) continue;
      const properties = uses.get(animation.effect.target) ?? new Map();
      for (const property of animationProperties(animation))
        properties.set(property, (properties.get(property) ?? 0) + 1);
      uses.set(animation.effect.target, properties);
    }
    for (const animation of effects) {
      const effect = animation.effect,
        style = getComputedStyle(effect.target);
      const replace =
        effect.composite === "replace" &&
        effect
          .getKeyframes()
          .every(
            (frame) =>
              !frame.composite || ["auto", "replace"].includes(frame.composite),
          );
      const values = Object.fromEntries(
        animationProperties(animation)
          .filter((property) => replace && uses.get(effect.target)?.get(property) === 1)
          .map((property) => [property, style[property]]),
      );
      const readings = animated.get(animation) ?? [];
      readings.push({ at, values });
      prune(readings, (reading) => reading.at);
      animated.set(animation, readings);
    }
    const nodes = everything();
    const anchors = new Map();
    for (const node of nodes.filter((node) => node instanceof Element)) {
      const tree = node.getRootNode();
      if (!anchors.has(tree)) anchors.set(tree, new Map());
      const names = anchors.get(tree);
      for (const name of getComputedStyle(node)
        .anchorName.split(",")
        .map((name) => name.trim())) {
        if (!name || name === "none") continue;
        names.set(name, names.has(name) ? null : node);
      }
    }
    const modal = document
      .querySelector("script[data-lf-entry]")
      ?.lfNativeLayers?.()
      .findLast((entry) => entry.kind === "modal")?.root;
    // Native modal dialogs escape ancestor inertness and own the current reading;
    // an explicit inert node within that dialog still excludes its descendants.
    const exposed = (element) => {
      for (let at = element; at instanceof Element; at = up(at)) {
        if (at.inert) return false;
        if (at === modal) return true;
      }
      return !modal;
    };
    if (frame) {
      frames.push({ at, start: time, nodes, motion: [] });
      prune(frames, (frame) => frame.at);
    }
    for (const node of nodes) {
      const scrolls = scrolled.get(node) ?? [];
      const scroll = { left: node.scrollLeft, top: node.scrollTop };
      const prior = scrolls.at(-1)?.scroll;
      if (prior?.left !== scroll.left || prior?.top !== scroll.top) {
        scrolls.push({ at, scroll });
        prune(scrolls, (item) => item.at);
        scrolled.set(node, scrolls);
      }
      const element = node.nodeType === Node.TEXT_NODE ? up(node) : node;
      const range = node.nodeType === Node.TEXT_NODE ? document.createRange() : null;
      if (range) range.selectNodeContents(node);
      const rect = range ? range.getBoundingClientRect() : node.getBoundingClientRect();
      const fragments = range ? [...range.getClientRects()] : [rect];
      const style = getComputedStyle(element);
      let paintedElement = element;
      while (
        paintedElement instanceof Element &&
        getComputedStyle(paintedElement).display === "contents"
      )
        paintedElement = up(paintedElement);
      const shown =
        paintedElement instanceof Element &&
        exposed(element) &&
        paintedElement.checkVisibility({ checkOpacity: true });
      const paint = {
        parent: up(node),
        anchor: range
          ? null
          : (anchors.get(node.getRootNode())?.get(style.positionAnchor) ?? null),
        anchorX:
          !range &&
          ["fixed", "absolute"].includes(style.position) &&
          [node.style.left, node.style.right].some((value) =>
            anchorInset(value, "left"),
          ),
        anchorY:
          !range &&
          ["fixed", "absolute"].includes(style.position) &&
          [node.style.top, node.style.bottom].some((value) =>
            anchorInset(value, "top"),
          ),
        position: range ? "static" : style.position,
        visibility: style.visibility,
        opacity: style.opacity,
        overflowX: style.overflowX,
        overflowY: style.overflowY,
        reflow: range ? null : node.getAttribute("data-lf-reflow"),
        runtime: !range && node.matches(".lf-chrome, [data-lf-runtime]"),
        control: !range && node.matches(interactive),
        reading: Boolean(range) || readingMedia(element),
        shown,
      };
      const seen = placed.get(node) ?? [];
      const last = seen.at(-1);
      if (
        last?.rect.left === rect.left &&
        last.rect.top === rect.top &&
        last.rect.right === rect.right &&
        last.rect.bottom === rect.bottom &&
        Object.keys(paint).every((key) => last.paint[key] === paint[key]) &&
        fragments.length === last.fragments.length &&
        fragments.every((rect, i) =>
          ["left", "top", "right", "bottom"].every(
            (edge) => rect[edge] === last.fragments[i][edge],
          ),
        )
      )
        continue;
      seen.push({ at, rect, fragments, paint });
      prune(seen, (item) => item.at);
      placed.set(node, seen);
    }
    return at;
  };
  const readingAt = (node, at) => placed.get(node)?.findLast((item) => item.at <= at);
  const boxAt = (node, at) => readingAt(node, at)?.rect;
  const paintAt = (node, at) => readingAt(node, at)?.paint;
  const ancestryAt = (node, at) => {
    const ancestors = [];
    for (
      let parent = node;
      parent instanceof Element;
      parent = paintAt(parent, at)?.parent
    )
      ancestors.push(parent);
    return ancestors;
  };
  // Layout coordinates remove scrolling, which Chrome also removes from its shifts.
  const scrollAt = (node, at) =>
    scrolled.get(node)?.findLast((item) => item.at <= at)?.scroll;
  const layoutAt = (node, at) => {
    const rect = boxAt(node, at);
    if (!rect) return null;
    // The root border box travels with its own native scroll; nested scrollport
    // borders stay put while their contents move.
    const rootScroll = node === document.scrollingElement ? scrollAt(node, at) : null;
    let left = rect.left + (rootScroll?.left ?? 0),
      top = rect.top + (rootScroll?.top ?? 0);
    for (
      let child = node, parent = paintAt(child, at).parent;
      parent instanceof Element;
      child = parent, parent = paintAt(parent, at).parent
    ) {
      if (paintAt(child, at).position === "fixed") break;
      const scroll = scrollAt(parent, at);
      left += scroll?.left ?? 0;
      top += scroll?.top ?? 0;
    }
    return { left, top, right: left + rect.width, bottom: top + rect.height };
  };
  // Each input's rendering: when it began; the start of its second frame; the motion
  // it began, and the start of the latest frame that motion moved; whether news has
  // landed since; and a keystroke's typing, which holds its field; the box of the field
  // and of each element holding it at the key; the animations already moving any of
  // them; and until when the typing rule reads it.
  const renderings = [];
  let open = null;
  // The typing rule stops reading the open rendering, which runs on.
  const unwatch = () => {
    if (open?.typing?.until === Infinity)
      open.typing.until = read(performance.now(), false);
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
  const tick = (time) => {
    const at = read(time);
    if (open) {
      // The input's motion is what began after it and before news since it, which
      // may begin motion of its own. Still running here, it moves this frame, as it
      // moved the one before if it ran at that frame's start, finishing in it.
      if (!open.told)
        for (const animation of begun(open.start)) open.own.add(animation);
      const motion = [...open.own].some(({ playState }) => playState === "running");
      if (motion || open.motion) open.moved = at;
      open.motion = motion;
      if (!open.first && open.second === Infinity) open.second = at;
      open.first = false;
      if (open.last || at - open.start > WINDOW) end();
      // A settled reading here counts updates before this one; this frame's own
      // callbacks may still move a box, so the rendering runs through the next.
      else open.last = settled() && !motion;
    }
    const motion = frames.at(-1).motion;
    for (const rendering of renderings)
      for (const animation of rendering.own)
        if (animation.playState === "running") motion.push(animation);
    audit();
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
      const at = read(event.timeStamp, false);
      begin(event.timeStamp, {
        field,
        at,
        found: boxes(holding),
        moving: holding
          .flatMap((node) => node.getAnimations())
          .filter((animation) => animation.playState === "running" && moves(animation)),
        until: Infinity,
      });
    },
    true,
  );
  // A resize is input to Chrome, and lays the page out anew, the field with it.
  window.addEventListener("resize", (event) => begin(event.timeStamp));
  // When the page adopted each server reading.
  new MutationObserver(() => {
    unwatch();
    if (open) open.told = true;
  }).observe(document, { subtree: true, attributeFilter: ["data-lf-reading"] });
  const heard = (view) => (event) => {
    if (!event.isTrusted) return;
    const at = event.timeStamp + view.performance.timeOrigin - performance.timeOrigin;
    begin(at);
  };
  for (let view = window; ; view = view.parent) {
    let held;
    try {
      held = view.document;
    } catch {
      break;
    }
    for (const type of ["keydown", "pointerdown", "wheel"])
      held.addEventListener(type, heard(view), true);
    if (view === view.parent) break;
  }
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
  // Widgets upgrade after the authored document has painted,
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
  const permittedReflow = ({ node, previousRect, currentRect }, around) => {
    const element = node?.nodeType === Node.TEXT_NODE ? up(node) : node;
    if (around.length !== 3) return false;
    const regions = new Set(
      around.flatMap(({ at }) =>
        ancestryAt(element, at).filter(
          (ancestor) => typeof paintAt(ancestor, at)?.reflow === "string",
        ),
      ),
    );
    if (!regions.size) return false;
    const stationary = (node) => {
      const rects = around.map(({ at }) => layoutAt(node, at));
      const screen = around.map(({ at }) => boxAt(node, at));
      return (
        rects.every(Boolean) &&
        (rects.every((rect) => !moved(rect, rects[2])) ||
          screen.every((rect) => !moved(rect, screen[2])))
      );
    };
    // Each declaration owns its actual box. Nested regions keep every enclosing
    // guarantee, without borrowing a valid boundary to excuse an invalid one.
    for (const region of regions) {
      // Runtime ownership follows passages.js `leafSurface`, including inline threads.
      if (
        !around.every(({ at }) =>
          ancestryAt(region, at).some((owner) => paintAt(owner, at)?.runtime),
        )
      )
        return false;
      const modes = around.map(({ at }) => paintAt(region, at)?.reflow);
      if (modes.some((mode) => mode !== "text" && mode !== "controls")) return false;
      if (!stationary(region)) return false;
      if (modes.includes("text")) {
        for (const { at, nodes } of around)
          for (const control of nodes)
            if (
              paintAt(control, at)?.control &&
              ancestryAt(control, at).includes(region) &&
              !stationary(control)
            )
              return false;
      }
      const inside = (rect) =>
        around.some(({ at }) => {
          const frame = boxAt(region, at);
          return (
            rect.left >= frame.left - 1 &&
            rect.top >= frame.top - 1 &&
            rect.right <= frame.right + 1 &&
            rect.bottom <= frame.bottom + 1
          );
        });
      if (!inside(previousRect) || !inside(currentRect)) return false;
    }
    return true;
  };
  const paintState = (node, rect, at) => {
    const own = paintAt(node, at);
    if (!own.shown || own.visibility !== "visible" || own.opacity === "0")
      return { paintable: false, visible: false };
    let left = Math.max(0, rect.left),
      top = Math.max(0, rect.top);
    let right = Math.min(innerWidth, rect.right),
      bottom = Math.min(innerHeight, rect.bottom);
    for (
      let parent = own.reading ? up(node) : node;
      parent instanceof Element;
      parent = paintAt(parent, at)?.parent
    ) {
      const style = paintAt(parent, at);
      if (style.opacity === "0") return { paintable: false, visible: false };
      if (parent === node) continue;
      const clip = boxAt(parent, at);
      if (!clip) return { paintable: false, visible: false };
      if (style.overflowX !== "visible") {
        left = Math.max(left, clip.left);
        right = Math.min(right, clip.right);
      }
      if (style.overflowY !== "visible") {
        top = Math.max(top, clip.top);
        bottom = Math.min(bottom, clip.bottom);
      }
    }
    return { paintable: true, visible: right > left && bottom > top };
  };
  // Chrome signals a changed painted frame; actual reading/control geometry decides
  // motion. A container can grow at one edge while all protected landmarks stand.
  // Null or decorative pseudo sources do not override those landmark readings.
  const nativeScrollMotion = (node, from, to) => {
    const element = node.nodeType === Node.TEXT_NODE ? up(node) : node;
    const sticky = ancestryAt(element, to).find(
      (owner) => paintAt(owner, to)?.position === "sticky",
    );
    const motion = { left: 0, top: 0 };
    if (!sticky) return motion;
    const before = boxAt(sticky, from),
      after = boxAt(sticky, to);
    if (!before || !after) return motion;
    for (const axis of ["left", "top"]) {
      const scroll = ancestryAt(sticky, to).reduce((sum, owner) => {
        const prior = scrollAt(owner, from),
          next = scrollAt(owner, to);
        return sum + (prior && next ? next[axis] - prior[axis] : 0);
      }, 0);
      const shifted = after[axis] - before[axis];
      // Scroll carries the sticky owner on that axis, through at most its native
      // scroll delta. Descendants retain their local position relative to it.
      if (
        scroll &&
        shifted >= Math.min(0, -scroll) - 1 &&
        shifted <= Math.max(0, -scroll) + 1
      )
        motion[axis] = shifted;
    }
    return motion;
  };
  const scrollMotion = (node, from, to) => {
    const motion = nativeScrollMotion(node, from, to);
    const element = node.nodeType === Node.TEXT_NODE ? up(node) : node;
    const anchored = { left: false, top: false };
    for (const owner of ancestryAt(element, to)) {
      const prior = paintAt(owner, from),
        next = paintAt(owner, to);
      const anchor = prior?.anchor;
      if (!anchor || anchor !== next?.anchor) continue;
      // Native anchor layout can follow its scroller in the next frame. Credit
      // source scrolling since this retained portal pose was first observed.
      const start = readingAt(owner, from).at;
      const before = boxAt(anchor, start),
        after = boxAt(anchor, to);
      const beforeLayout = layoutAt(anchor, start),
        afterLayout = layoutAt(anchor, to);
      if (!before || !after || !beforeLayout || !afterLayout) continue;
      const carried = nativeScrollMotion(anchor, start, to);
      for (const [axis, held] of [
        ["left", "anchorX"],
        ["top", "anchorY"],
      ]) {
        if (!prior[held] || !next[held] || anchored[axis]) continue;
        anchored[axis] = true;
        motion[axis] +=
          Math.abs(afterLayout[axis] - beforeLayout[axis]) < 1
            ? after[axis] - before[axis]
            : carried[axis];
      }
    }
    return motion;
  };
  const animationMotion = (node, from, to, animations) => {
    const element = node.nodeType === Node.TEXT_NODE ? up(node) : node;
    const motion = { left: 0, top: 0 };
    const seen = new Map();
    for (const animation of new Set(animations)) {
      const target = animation.effect.target;
      if (!ancestryAt(element, to).includes(target)) continue;
      const readings = animated.get(animation);
      const before = readings?.findLast((reading) => reading.at <= from);
      const after = readings?.findLast((reading) => reading.at <= to);
      if (!before || !after) continue;
      const properties = seen.get(target) ?? new Set();
      for (const property of animationProperties(animation)) {
        if (properties.has(property)) continue;
        properties.add(property);
        if (!(property in before.values) || !(property in after.values)) continue;
        const prior = animationTranslation(property, before.values[property]);
        const next = animationTranslation(property, after.values[property]);
        if (!prior || !next) continue;
        motion.left += next.left - prior.left;
        motion.top += next.top - prior.top;
      }
      seen.set(target, properties);
    }
    return motion;
  };
  const pendingMotion = [];
  const protectedMotion = (around) => {
    for (const node of new Set(around.flatMap(({ nodes }) => nodes))) {
      const readings = around.map(({ at }) => readingAt(node, at));
      if (!readings.every(Boolean)) continue;
      if (!readings.some(({ paint }) => paint.reading || paint.control || paint.reflow))
        continue;
      for (const [before, after] of [[0, 2]]) {
        const prior = readings[before],
          next = readings[after];
        const scroll = scrollMotion(node, around[before].at, around[after].at);
        const motion = animationMotion(
          node,
          around[before].at,
          around[after].at,
          around.flatMap((frame) => frame.motion),
        );
        for (
          let i = 0;
          i < Math.min(prior.fragments.length, next.fragments.length);
          i++
        ) {
          const previousRect = prior.fragments[i],
            currentRect = next.fragments[i];
          if (
            !previousRect.width ||
            !previousRect.height ||
            !currentRect.width ||
            !currentRect.height
          )
            continue;
          if (
            !carried(previousRect, currentRect, "top", "bottom") &&
            !carried(previousRect, currentRect, "left", "right")
          )
            continue;
          const from = layoutAt(node, around[before].at),
            to = layoutAt(node, around[after].at);
          const layoutLeft = previousRect.left - prior.rect.left + from.left;
          const layoutTop = previousRect.top - prior.rect.top + from.top;
          const nextLeft = currentRect.left - next.rect.left + to.left;
          const nextTop = currentRect.top - next.rect.top + to.top;
          const x =
            carried(previousRect, currentRect, "left", "right") &&
            Math.abs(layoutLeft - nextLeft) >= 1 &&
            Math.abs(
              currentRect.left - previousRect.left - scroll.left - motion.left,
            ) >= 1;
          const y =
            carried(previousRect, currentRect, "top", "bottom") &&
            Math.abs(layoutTop - nextTop) >= 1 &&
            Math.abs(currentRect.top - previousRect.top - scroll.top - motion.top) >= 1;
          if (!x && !y) continue;
          const fromPaint = paintState(node, previousRect, around[before].at);
          const toPaint = paintState(node, currentRect, around[after].at);
          if (
            fromPaint.paintable &&
            toPaint.paintable &&
            (fromPaint.visible || toPaint.visible) &&
            !permittedReflow({ node, previousRect, currentRect }, around)
          )
            pendingMotion.push({
              node,
              fragment: i,
              previousRect,
              currentRect,
              before: around[before].at,
              after: around[after].at,
            });
        }
      }
    }
  };
  const audit = () => {
    prune(pendingMotion, (move) => move.after, 0);
    if (frames.length < 2) return;
    const at = performance.now(),
      frame = frames.at(-1).at;
    const rendering = renderings.findLast(({ start }) => start <= at);
    if (rendering?.typing && at <= rendering.typing.until) return;
    const entry = { startTime: at, sources: [] };
    // Gesture ownership is its bounded rendering, not Chrome's half-second credit.
    if (
      presenting(entry) ||
      (rendering && (frame <= rendering.second || frame <= rendering.moved))
    )
      return;
    const before = frames.at(-2),
      after = frames.at(-1);
    protectedMotion([before, before, after]);
  };
  // A painted layout transition admits the retained landmark ledger. Chrome's
  // source list never selects which landmarks get checked; source geometry only
  // corroborates a sampled roundtrip already undone by the time it is heard.
  const admittedMotion = (entry, next, rendering) => {
    if (presenting(entry)) return;
    const admitted = pendingMotion.filter(
      (move) => move.before <= entry.startTime && move.after <= next,
    );
    const groups = new Map();
    for (const move of admitted) {
      const byFragment = groups.get(move.node) ?? new Map();
      const chain = byFragment.get(move.fragment) ?? [];
      chain.push(move);
      byFragment.set(move.fragment, chain);
      groups.set(move.node, byFragment);
    }
    const confirms = (move) =>
      entry.sources.some((source) => {
        const element =
          move.node.nodeType === Node.TEXT_NODE ? up(move.node) : move.node;
        if (source.node !== move.node && source.node !== element) return false;
        return (
          Math.abs(
            source.currentRect.left -
              source.previousRect.left -
              (move.currentRect.left - move.previousRect.left),
          ) < 1 &&
          Math.abs(
            source.currentRect.top -
              source.previousRect.top -
              (move.currentRect.top - move.previousRect.top),
          ) < 1
        );
      });
    for (const [node, fragments] of groups)
      for (const [fragment, chain] of fragments) {
        const first = chain[0],
          last = chain.at(-1);
        const current = readingAt(node, next)?.fragments[fragment];
        const net =
          carried(first.previousRect, last.currentRect, "top", "bottom") ||
          carried(first.previousRect, last.currentRect, "left", "right");
        const stable = net && (!current || moved(current, first.previousRect));
        const proof = stable
          ? { previousRect: first.previousRect, currentRect: last.currentRect }
          : chain.find(confirms);
        if (proof)
          report(
            `${name(node)} moved without input`,
            by(proof.previousRect, proof.currentRect) + beside(entry.sources, node),
          );
      }
    for (let i = pendingMotion.length - 1; i >= 0; i--)
      if (admitted.includes(pendingMotion[i])) pendingMotion.splice(i, 1);
  };
  // Chrome's rects are what a node paints, clipped to the viewport, so they are held
  // against the frame's own reading, never against the key's.
  const typed = (entry, typing, painted) => {
    painted = Math.min(painted, typing.until);
    for (const [node, before] of typing.found) {
      const after = before && boxAt(node, painted);
      if (!before || !after) continue;
      const from = layoutAt(node, typing.at),
        to = layoutAt(node, painted);
      if (!from || !to) continue;
      const scroll = scrollMotion(node, typing.at, painted);
      const motion = animationMotion(node, typing.at, painted, typing.moving);
      const x =
        carried(before, after, "left", "right") &&
        Math.abs(from.left - to.left) >= 1 &&
        Math.abs(after.left - before.left - scroll.left - motion.left) >= 1;
      const y =
        carried(before, after, "top", "bottom") &&
        Math.abs(from.top - to.top) >= 1 &&
        Math.abs(after.top - before.top - scroll.top - motion.top) >= 1;
      if (!x && !y) continue;
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
      const frame = frames.findLastIndex(({ start: time }) => time <= at);
      const next = frames[frame + 1]?.at;
      if (frame !== -1 && next === undefined) {
        waiting.push(entry);
        continue;
      }
      const rendering = renderings.findLast(({ start }) => start <= at);
      const typing = rendering?.typing;
      if (typing && at <= typing.until) {
        // A later frame may include the next gesture; typed() caps its reading at
        // the closing pose captured before that gesture began.
        if (frame !== -1) typed(entry, typing, next);
      }
      admittedMotion(entry, next ?? performance.now(), rendering);
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
        audit();
        judge([...waiting.splice(0), ...observer.takeRecords()]);
        resolve();
      };
      requestAnimationFrame(() => requestAnimationFrame(() => setTimeout(drain)));
      setTimeout(drain, 500);
    });
})();
