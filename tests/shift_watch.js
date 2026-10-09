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
// proof. An append region may carry following content inside its stationary
// scrollport by its measured suffix growth; existing children retain their boxes.
// Layout coordinates remove scrolling; sticky descendants retain their
// mechanical scroller's ownership. Portals with one unique anchor, in their tree or
// inside the `anchor-scope` that limits its name, and a direct native anchor inset,
// inline or in their tree's own rules, retain that scroller too; nested CSS
// expressions, ambiguous names and rules that disagree receive no inferred ownership.
//
// Each trusted gesture owns its counted rendering until declared completion.
// Native effects it began retain only their sampled displacement within their
// own subtree; their continued lifetime never owns unrelated page movement.
// News starts passive rendering except the first frame shared with the gesture.
// A typing field is observed at its native edit start, independently of Chrome's
// clipped or shadowed source rectangles. Its subject, protected reading/control and
// declared-region ancestors, and visibly painted holders retain their poses.
// Transparent coordinate carriers have no independent pose to protect: a compensated
// carrier rebase can leave every painted subject stationary. Motion
// already running on its ancestors belongs to the gesture that began that motion.
// Continuing translation is credited from sampled animated property values, not
// the ancestor's whole box: independent movement of it or its children still fails.
// This proof supports unique replace effects with pure transform translation or
// pixel left/top/marginLeft/marginTop. Scale, rotation and composed effects receive
// no inferred translation credit. A floating owner's last-written held-edge point
// declares page/window plane changes under the same subject, anchor and tenure;
// its solver dimensions, not the holder's rendered displacement, supply that credit.
// Observed page attachments in the window plane retain their carrying source offsets,
// physical attachment point and written solver point. Source travel bounds physical
// following, which bounds the solver's constrained movement. Only that written
// movement is credited; extra holder/child movement still fails.
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
// Unchanged frames. A reading appends to the ledger only where a node's reading
// differs from its last, so a frame on which nothing could have changed keeps the
// last complete reading and its population instead of reading every node again.
// Every passive verdict starts from a layout-shift entry, and an entry, whether the
// observer hears it or a paint checkpoint takes it, makes the reading that judges
// it complete: every node is read, and the entry's paint is read then where the
// following frame kept an unchanged reading, unless a later input already makes
// that endpoint ambiguous. So whatever moved a landmark without input, its verdict
// compares complete readings. Announcements keep the readings between entries
// current, which input ownership and typing's verdicts rest on: a frame reads
// completely when a change was announced since the last complete reading, and on
// the frame after one that read an announced change, since native anchoring
// follows its scroller a frame late. Each announcement is made in the task of the
// change it covers: DOM writes in the document and every shadow root; a running
// animation anywhere in the composed tree, or one that stopped or left the set;
// input, focus, scroll, drag, resize, load, reset and beforetoggle events; the
// emulated media tests change; this frame's own visibility; and the calls that
// restyle without a DOM write (custom states, constructed and adopted sheets,
// form-control values and ranges, animation mutators). Every VERIFY-th unannounced
// frame, and the first one once the fixture asks for the test's verdict, reads
// completely and fails the test where any reading differs, naming the innermost
// node that changed, so a source missing from this list is found rather than
// leaving the readings between entries stale. A page that writes while it is read
// announces its change by that write. A change to this gate runs the suite with
// VERIFY = 1, which checks every frame.
//
// Every finding fails the ordinary browser fixture. It installs this sensor after
// write_watch.js and binds the canonical control and clipping vocabulary.
(() => {
  // A native paint/task checkpoint retires only evidence it has judged. Execution
  // time says nothing about whether Chrome has delivered an earlier painted shift.
  let retainedFrom = -Infinity;
  const pruneSamples = (list) => {
    while (list.length > 1 && list[1].at <= retainedFrom) list.shift();
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
  // Every animation in the composed tree: the document's own list leaves out those
  // whose targets are in shadow trees, so each connected shadow root adds its own.
  const allAnimations = () => [
    ...new Set(
      [document, ...[...roots].filter((root) => root.host.isConnected)].flatMap(
        (tree) => tree.getAnimations(),
      ),
    ),
  ];
  // Native timeline startTime changes when playback rate changes. Input ownership
  // follows the operation that began motion, not that mutable clock coordinate.
  const beganAt = new WeakMap();
  // Motion begun since `start` that moves a box; one still pending begins now.
  const begun = (start) =>
    allAnimations().filter(
      (animation) =>
        animation.playState === "running" &&
        (beganAt.get(animation)?.at ?? animation.startTime ?? Infinity) >= start &&
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
  // What decides a positioned box's inset on an axis, as the declarations that can win
  // it: an important inline one alone, else the important rules of the box's own tree
  // that match it now, else its inline style, else every matching rule. Within a tier
  // the cascade weighs specificity, layers and order, which no API reports, so the
  // inset counts as anchored only where every candidate there is a direct anchor
  // inset: rules that disagree are ambiguous, like a name that is. Rules are read only
  // for a box naming an anchor, since every frame samples it, and only those that
  // state an inset at all, gathered once per sheet.
  const INSETS = ["top", "right", "bottom", "left"];
  const insetRules = new WeakMap();
  const rulesStatingInsets = (sheet) => {
    const length = sheet.cssRules.length;
    const known = insetRules.get(sheet);
    if (known?.length === length) return known.rules;
    const rules = [];
    const visit = (list, conditions) => {
      for (const rule of list) {
        if (rule instanceof CSSStyleRule) {
          if (INSETS.some((side) => rule.style.getPropertyValue(side)))
            rules.push({ rule, conditions });
        } else if (rule.cssRules)
          visit(
            rule.cssRules,
            rule instanceof CSSMediaRule || rule instanceof CSSSupportsRule
              ? [...conditions, rule]
              : conditions,
          );
      }
    };
    visit(sheet.cssRules, []);
    insetRules.set(sheet, { length, rules });
    return rules;
  };
  const holds = (condition) =>
    condition instanceof CSSMediaRule
      ? matchMedia(condition.conditionText).matches
      : CSS.supports(condition.conditionText);
  // An inline inset loses only to an important rule, so a box with one reads those
  // alone: the comment box's placer writes its insets on every frame it moves.
  const declaredRules = (node, property, importantOnly) => {
    const root = node.getRootNode();
    const found = { important: [], normal: [] };
    for (const sheet of [
      ...(root.styleSheets ?? []),
      ...(root.adoptedStyleSheets ?? []),
    ])
      for (const { rule, conditions } of rulesStatingInsets(sheet)) {
        const value = rule.style.getPropertyValue(property);
        if (!value || (importantOnly && !rule.style.getPropertyPriority(property)))
          continue;
        if (!conditions.every(holds)) continue;
        let matches = false;
        try {
          matches = node.matches(rule.selectorText);
        } catch {
          // A selector `matches` cannot take, such as a pseudo-element's.
        }
        if (matches)
          found[rule.style.getPropertyPriority(property) ? "important" : "normal"].push(
            value,
          );
      }
    return found;
  };
  const anchoredInset = (node, style, property, axis) => {
    const inline = node.style.getPropertyValue(property);
    if (inline && node.style.getPropertyPriority(property))
      return anchorInset(inline, axis);
    if (!style.positionAnchor.startsWith("--"))
      return inline ? anchorInset(inline, axis) : false;
    const rules = declaredRules(node, property, Boolean(inline));
    const candidates = rules.important.length
      ? rules.important
      : inline
        ? [inline]
        : rules.normal;
    return (
      candidates.length > 0 && candidates.every((value) => anchorInset(value, axis))
    );
  };
  // The box a positioned box's `position-anchor` names. A name an `anchor-scope`
  // limits resolves inside the scoping box, so a name declared once per repeated
  // component still names one anchor for each; elsewhere it must be unique in its tree.
  const anchorOf = (node, style, anchors) => {
    const name = style.positionAnchor;
    if (!name.startsWith("--")) return null;
    const names = (value) => value.split(",").map((part) => part.trim());
    for (let at = up(node); at instanceof Element; at = up(at)) {
      const scope = getComputedStyle(at).anchorScope;
      if (scope !== "all" && !names(scope).includes(name)) continue;
      const found = [at, ...at.querySelectorAll("*")].filter((el) =>
        names(getComputedStyle(el).anchorName).includes(name),
      );
      return found.length === 1 ? found[0] : null;
    }
    return anchors.get(node.getRootNode())?.get(name) ?? null;
  };
  const boxes = (nodes) =>
    new Map([...nodes].map((node) => [node, node.getBoundingClientRect()]));
  // A field's painted holder is a surface in its own right. Pure coordinate
  // containers paint no box; their children keep their independently protected
  // controls and reading landmarks even when carrier coordinates are rebased.
  const paintsBox = (style) =>
    (style.backgroundColor !== "transparent" &&
      !/^rgba\([^,]+,[^,]+,[^,]+,\s*0\)$/.test(style.backgroundColor) &&
      !/\/\s*0\)$/.test(style.backgroundColor)) ||
    style.backgroundImage !== "none" ||
    style.boxShadow !== "none" ||
    ["Top", "Right", "Bottom", "Left"].some(
      (edge) =>
        !["none", "hidden"].includes(style[`border${edge}Style`]) &&
        parseFloat(style[`border${edge}Width`]) > 0,
    ) ||
    (style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0);
  const paintedHolder = (node) =>
    paintsBox(getComputedStyle(node)) ||
    ["::before", "::after"].some((pseudo) => {
      const style = getComputedStyle(node, pseudo);
      return (
        style.display !== "none" &&
        style.visibility === "visible" &&
        style.opacity !== "0" &&
        !["none", "normal"].includes(style.content) &&
        (style.content !== '\"\"' || paintsBox(style))
      );
    });
  // Whether anything that can change a node's reading has happened since the last
  // complete one (the header's "Unchanged frames"). Each source sets it in the same
  // task as the change it announces, so it is set before the next frame's reading.
  let unread = true;
  const announce = () => {
    unread = true;
  };
  const writes = new MutationObserver(announce);
  // Input, scrolling, loads and native element state, heard in each tree they are
  // dispatched in: scroll, load and toggle do not cross a shadow boundary or reach
  // the window, so the document and every shadow root listen in capture.
  // Pointer events also stand for touch and mouse; a drag suppresses them, so its
  // own events are heard. beforetoggle precedes every popover change, whatever
  // began it.
  const EVENTS = [
    "pointerdown",
    "pointermove",
    "pointerup",
    "pointercancel",
    "pointerover",
    "pointerout",
    "keydown",
    "keyup",
    "beforeinput",
    "input",
    "change",
    "focus",
    "blur",
    "focusin",
    "focusout",
    "dragenter",
    "dragover",
    "dragleave",
    "drop",
    "dragend",
    "scroll",
    "load",
    "error",
    "reset",
    "beforetoggle",
    "contentvisibilityautostatechange",
  ];
  const watchTree = (tree) => {
    writes.observe(tree, {
      subtree: true,
      attributes: true,
      childList: true,
      characterData: true,
    });
    for (const type of EVENTS)
      tree.addEventListener(type, announce, { capture: true, passive: true });
  };
  watchTree(document);
  for (const type of ["resize", "hashchange", "pageshow", "focus", "blur"])
    window.addEventListener(type, announce, { capture: true, passive: true });
  for (const type of ["resize", "scroll"])
    window.visualViewport?.addEventListener(type, announce);
  document.fonts?.addEventListener("loadingdone", announce);
  // Emulated media changes style with no event but its query's.
  for (const query of [
    "print",
    "(prefers-color-scheme: dark)",
    "(prefers-reduced-motion: reduce)",
    "(forced-colors: active)",
    "(prefers-contrast: more)",
  ])
    matchMedia(query).addEventListener("change", announce);
  // Page state that matches selectors or applies style without a DOM write.
  const announcing = (proto, names) => {
    for (const name of names) {
      const own = Object.getOwnPropertyDescriptor(proto, name);
      const original = own.set ?? own.value;
      const wrapped = function (...args) {
        announce();
        return Reflect.apply(original, this, args);
      };
      Object.defineProperty(
        proto,
        name,
        own.set ? { ...own, set: wrapped } : { ...own, value: wrapped },
      );
    }
  };
  announcing(CSSStyleSheet.prototype, [
    "replace",
    "replaceSync",
    "insertRule",
    "deleteRule",
  ]);
  announcing(StyleSheet.prototype, ["disabled"]);
  announcing(Document.prototype, ["adoptedStyleSheets"]);
  announcing(ShadowRoot.prototype, ["adoptedStyleSheets"]);
  announcing(Animation.prototype, [
    "cancel",
    "finish",
    "play",
    "pause",
    "reverse",
    "updatePlaybackRate",
    "persist",
    "effect",
    "timeline",
    "startTime",
    "currentTime",
    "playbackRate",
  ]);
  announcing(KeyframeEffect.prototype, ["setKeyframes", "target", "composite"]);
  announcing(AnimationEffect.prototype, ["updateTiming"]);
  announcing(HTMLInputElement.prototype, [
    "value",
    "checked",
    "indeterminate",
    "setRangeText",
    "stepUp",
    "stepDown",
  ]);
  announcing(HTMLTextAreaElement.prototype, ["value", "setRangeText"]);
  announcing(HTMLSelectElement.prototype, ["value", "selectedIndex"]);
  announcing(HTMLOptionElement.prototype, ["selected"]);
  // A custom state matches `:state()`; the runtime restates them freely, so only a
  // call that changes the set announces.
  const states = CustomStateSet.prototype;
  const { add, delete: remove, clear, has } = states;
  Object.assign(states, {
    add(state) {
      if (!has.call(this, state)) announce();
      return add.call(this, state);
    },
    delete(state) {
      if (has.call(this, state)) announce();
      return remove.call(this, state);
    },
    clear() {
      if (this.size) announce();
      return clear.call(this);
    },
  });
  // Every shadow root, a closed one included, so a reading reaches every element.
  const roots = new Set();
  const attachShadow = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (init) {
    const root = attachShadow.call(this, init);
    roots.add(root);
    watchTree(root);
    announce();
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
  const floating = new WeakMap();
  let floatingOwners = new Set();
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
  // A finishing owner may retire its held native effect before the next frame.
  // Read its actual final properties in the finished-promise checkpoint, while
  // that effect still applies, using the same eligibility proof as frame samples.
  const endings = new WeakMap();
  // A no-fill native effect retires before its finished promise runs. Capture its
  // underlying translation at the producer, before animate() applies the effect;
  // a later authored change cannot be mistaken for that native return endpoint.
  const origins = new WeakMap();
  const underlying = (target, excluded = null) => {
    const style = getComputedStyle(target);
    const competing = new Set(
      target
        .getAnimations()
        .filter((animation) => animation !== excluded && moves(animation))
        .flatMap(animationProperties),
    );
    return Object.fromEntries(
      ["transform", "left", "top", "marginLeft", "marginTop"]
        .filter((property) => !competing.has(property))
        .map((property) => [property, style[property]]),
    );
  };
  const animate = Element.prototype.animate;
  Element.prototype.animate = function (...args) {
    announce();
    const values = underlying(this);
    const at = nativePerformance.now();
    const animation = animate.apply(this, args);
    beganAt.set(animation, { at });
    origins.set(
      animation,
      Object.fromEntries(
        animationProperties(animation)
          .filter((property) => property in values)
          .map((property) => [property, values[property]]),
      ),
    );
    return animation;
  };
  // Reusing a native effect is a new operation when play resumes or reverse changes
  // its direction. Changing playback rate alone does not transfer input ownership.
  for (const method of ["play", "reverse"]) {
    const original = Animation.prototype[method];
    Animation.prototype[method] = function (...args) {
      const beginning = method === "reverse" || this.playState !== "running";
      const origin =
        this.effect?.target &&
        moves(this) &&
        this.effect.getComputedTiming().progress === null
          ? underlying(this.effect.target, this)
          : null;
      const at = nativePerformance.now();
      const result = original.apply(this, args);
      if (beginning) {
        beganAt.set(this, { at });
        if (origin) origins.set(this, origin);
      }
      return result;
    };
  }
  const observedStates = new WeakMap();
  const readMotion = (at, ending = null) => {
    const effects = [
      ...new Set([
        ...allAnimations(),
        ...(ending?.playState === "finished" ? [ending] : []),
      ]),
    ].filter((animation) => animation.effect?.target && moves(animation));
    const uses = new Map();
    for (const animation of effects) {
      const priorState = observedStates.get(animation);
      if (!beganAt.has(animation))
        beganAt.set(animation, { at: animation.startTime ?? at });
      else if (
        priorState?.state === "paused" &&
        animation.playState === "running" &&
        priorState.beginning === beganAt.get(animation)
      )
        // CSS play-state can resume without calling the native play producer.
        // An explicit play() already supplied a new operation; never restamp it.
        beganAt.set(animation, { at });
      observedStates.set(animation, {
        state: animation.playState,
        beginning: beganAt.get(animation),
      });
      if (
        animation.effect.getComputedTiming().progress === null &&
        animation !== ending
      )
        continue;
      const properties = uses.get(animation.effect.target) ?? new Map();
      for (const property of animationProperties(animation))
        properties.set(property, (properties.get(property) ?? 0) + 1);
      uses.set(animation.effect.target, properties);
    }
    for (const animation of effects) {
      const finished = animation.finished;
      if (endings.get(animation) !== finished) {
        endings.set(animation, finished);
        finished.then(
          () => readMotion(nativePerformance.now(), animation),
          () => {},
        );
      }
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
      const returning =
        animation === ending && effect.getComputedTiming().progress === null;
      const origin = origins.get(animation);
      const values = Object.fromEntries(
        animationProperties(animation)
          .filter(
            (property) =>
              replace &&
              uses.get(effect.target)?.get(property) === 1 &&
              (!returning || origin?.[property] === style[property]),
          )
          .map((property) => [property, style[property]]),
      );
      const readings = animated.get(animation) ?? [];
      readings.push({ at, values });
      pruneSamples(readings);
      animated.set(animation, readings);
    }
  };
  // Unchanged frames: the last complete reading's population, the ledger entries
  // appended so far, the unannounced frames in a row, and what the last read saw.
  const VERIFY = 30;
  let held = [];
  let written = 0;
  let quiet = 0;
  let wasRunning = false;
  let owed = 0;
  let wasDrawn = null;
  let seenAnimations = [];
  // One line for a reading that found unannounced changes: the innermost node that
  // changed, what changed on it, and how many other nodes changed with it.
  const missed = (misses) => {
    const depth = (node) => {
      let count = 0;
      for (let at = node; at; at = up(at)) count++;
      return count;
    };
    const [node, changed] = misses.reduce((deepest, miss) =>
      depth(miss[0]) > depth(deepest[0]) ? miss : deepest,
    );
    const others = misses.length - 1;
    report(
      `shift watch missed a change to ${node ? name(node) : "the page's nodes"}`,
      ` (${changed.join(", ")})` +
        (others ? ` and to ${others} other node${others === 1 ? "" : "s"}` : "") +
        ": a source of change is missing from the sensor's announcements" +
        ' (shift_watch.js, "Unchanged frames")',
    );
  };
  const read = (time, frame = true) => {
    // Poses belong to their synchronous observation time. The native frame start
    // is kept separately to associate Chrome's painted shift with that frame.
    const at = nativePerformance.now();
    const selections = new Map(
      (
        document.querySelector("script[data-lf-entry]")?.lfFloatingSelections?.() ?? []
      ).map((selection) => [selection.floating, selection]),
    );
    for (const owner of new Set([...floatingOwners, ...selections.keys()])) {
      const readings = floating.get(owner) ?? [];
      readings.push({ at, selection: selections.get(owner) ?? null });
      pruneSamples(readings);
      floating.set(owner, readings);
    }
    floatingOwners = new Set(selections.keys());
    readMotion(at);
    // A running animation changes poses on every frame, and the frame after it stops
    // or leaves the set settles the last of them.
    const animations = allAnimations();
    const running = animations.some(({ playState }) => playState === "running");
    if (writes.takeRecords().length) unread = true;
    // An embedding page can hide this document's frame without telling it.
    const drawn = drawing();
    const announced =
      unread ||
      drawn !== wasDrawn ||
      running ||
      wasRunning ||
      animations.length !== seenAnimations.length ||
      animations.some((animation, i) => animation !== seenAnimations[i]);
    // Native anchoring follows its scroller one frame late, so the frame after the
    // one that reads an announced change reads completely too.
    const changing = announced || (frame && owed > 0);
    if (frame && owed > 0) owed--;
    if (announced) owed = frame ? 1 : 2;
    wasRunning = running;
    wasDrawn = drawn;
    seenAnimations = animations;
    const verifying = !changing && frame && ++quiet % VERIFY === 0;
    if (!changing && !verifying) {
      if (frame)
        frames.push({
          at,
          start: time,
          nodes: held,
          motion: [],
          written,
          complete: false,
        });
      return at;
    }
    unread = false;
    if (changing) quiet = 0;
    const misses = [];
    const nodes = everything();
    if (
      verifying &&
      (nodes.length !== held.length || nodes.some((node, i) => node !== held[i]))
    )
      misses.push([null, ["population"]]);
    held = nodes;
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
    const entry = frame ? { at, start: time, nodes, motion: [], complete: true } : null;
    if (entry) frames.push(entry);
    for (const node of nodes) {
      const scrolls = scrolled.get(node) ?? [];
      const scroll = { left: node.scrollLeft, top: node.scrollTop };
      const prior = scrolls.at(-1)?.scroll;
      if (prior?.left !== scroll.left || prior?.top !== scroll.top) {
        if (verifying) misses.push([node, ["scroll offset"]]);
        written++;
        scrolls.push({ at, scroll });
        pruneSamples(scrolls);
        scrolled.set(node, scrolls);
      }
      const element = node.nodeType === Node.TEXT_NODE ? up(node) : node;
      const range = node.nodeType === Node.TEXT_NODE ? document.createRange() : null;
      if (range) range.selectNodeContents(node);
      const rect = range ? range.getBoundingClientRect() : node.getBoundingClientRect();
      const scaleX = !range && node.offsetWidth ? rect.width / node.offsetWidth : 1;
      const scaleY = !range && node.offsetHeight ? rect.height / node.offsetHeight : 1;
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
      const clipping = clippingAxes(style);
      const axes =
        node instanceof Element &&
        (node.scrollLeft ||
          node.scrollTop ||
          node.scrollWidth > node.clientWidth ||
          node.scrollHeight > node.clientHeight)
          ? scrollAxes(node)
          : null;
      const last = placed.get(node)?.at(-1);
      let appendChildren =
        !range && node.getAttribute("data-lf-reflow") === "append"
          ? [...node.children]
          : null;
      if (
        appendChildren &&
        last?.paint.appendChildren?.length === appendChildren.length &&
        appendChildren.every((child, i) => child === last.paint.appendChildren[i])
      )
        appendChildren = last.paint.appendChildren;
      const paint = {
        parent: up(node),
        anchor: range ? null : anchorOf(node, style, anchors),
        anchorX:
          !range &&
          ["fixed", "absolute"].includes(style.position) &&
          ["left", "right"].some((side) => anchoredInset(node, style, side, "left")),
        anchorY:
          !range &&
          ["fixed", "absolute"].includes(style.position) &&
          ["top", "bottom"].some((side) => anchoredInset(node, style, side, "top")),
        insetX: range ? null : `${node.style.left}|${node.style.right}`,
        insetY: range ? null : `${node.style.top}|${node.style.bottom}`,
        position: range ? "static" : style.position,
        stickyTop:
          !range && style.position === "sticky" && /^-?[\d.]+px$/.test(style.top)
            ? parseFloat(style.top)
            : null,
        stickyBottom:
          !range && style.position === "sticky" && /^-?[\d.]+px$/.test(style.bottom)
            ? parseFloat(style.bottom)
            : null,
        scrollXx: axes?.x.x ?? 1,
        scrollXy: axes?.x.y ?? 0,
        scrollYx: axes?.y.x ?? 0,
        scrollYy: axes?.y.y ?? 1,
        block:
          !range && ["fixed", "absolute"].includes(style.position)
            ? node.offsetParent
            : null,
        clipLeft: range
          ? null
          : node === document.scrollingElement
            ? 0
            : rect.left + node.clientLeft * scaleX,
        clipTop: range
          ? null
          : node === document.scrollingElement
            ? 0
            : rect.top + node.clientTop * scaleY,
        clipRight: range
          ? null
          : node === document.scrollingElement
            ? innerWidth
            : rect.left + (node.clientLeft + node.clientWidth) * scaleX,
        clipBottom: range
          ? null
          : node === document.scrollingElement
            ? innerHeight
            : rect.top + (node.clientTop + node.clientHeight) * scaleY,
        visibility: style.visibility,
        opacity: style.opacity,
        clipsX: clipping.x,
        clipsY: clipping.y,
        scrollportY: !range && ["auto", "scroll", "hidden"].includes(style.overflowY),
        paddingTop: range ? null : parseFloat(style.paddingTop),
        paddingBottom: range ? null : parseFloat(style.paddingBottom),
        reflow: range ? null : node.getAttribute("data-lf-reflow"),
        appendChildren,
        runtime: !range && node.matches(".lf-chrome, [data-lf-runtime]"),
        control: !range && node.matches(interactive),
        reading: Boolean(range) || readingMedia(element),
        shown,
      };
      const seen = placed.get(node) ?? [];
      const sameBox =
        last &&
        ["left", "top", "right", "bottom"].every(
          (edge) => last.rect[edge] === rect[edge],
        );
      const sameCoordinates =
        last &&
        ["position", "block", "anchor", "anchorX", "anchorY", "insetX", "insetY"].every(
          (key) => last.paint[key] === paint[key],
        );
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
      if (verifying)
        misses.push([
          node,
          [
            ...(last ? [] : ["first reading"]),
            ...(last && !sameBox ? ["box"] : []),
            ...(last &&
            (fragments.length !== last.fragments.length ||
              fragments.some((rect, i) =>
                ["left", "top", "right", "bottom"].some(
                  (edge) => rect[edge] !== last.fragments[i][edge],
                ),
              ))
              ? ["fragments"]
              : []),
            ...Object.keys(paint).filter(
              (key) => last && last.paint[key] !== paint[key],
            ),
          ],
        ]);
      written++;
      seen.push({
        at,
        poseAt: sameBox && sameCoordinates ? last.poseAt : at,
        rect,
        fragments,
        paint,
      });
      pruneSamples(seen);
      placed.set(node, seen);
    }
    if (entry) entry.written = written;
    // A page that wrote while it was read, as a reading that patches the DOM API
    // does, announced its own change.
    if (writes.takeRecords().length) unread = true;
    else if (misses.length) missed(misses);
    return at;
  };
  const readingAt = (node, at) => placed.get(node)?.findLast((item) => item.at <= at);
  // A coordinate binding can stand longer than the retained ledger. Its origin
  // begins at the shared history boundary once the earlier samples are retired.
  const poseAt = (node, at) => Math.max(readingAt(node, at).poseAt, retainedFrom);
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
  // Scroll offsets are local layout pixels; protected poses are viewport pixels.
  // Retain each source's axes with its pose so a later transform cannot rewrite
  // the coordinate space in which an earlier scroll was observed.
  const viewportScroll = (node, at, offset = scrollAt(node, at)) => {
    const paint = paintAt(node, at);
    if (!paint) {
      const history = (samples) => ({
        count: samples?.length ?? 0,
        first: samples?.[0].at,
        last: samples?.at(-1).at,
      });
      throw new Error(
        `Missing retained scroll paint: ${JSON.stringify({
          node: name(node),
          nodeType: node.nodeType,
          connected: node.isConnected,
          at: String(at),
          atType: typeof at,
          atFinite: Number.isFinite(at),
          retainedFrom: String(retainedFrom),
          offset: offset ?? null,
          poses: history(placed.get(node)),
          scrolls: history(scrolled.get(node)),
        })}; caller: ${new Error().stack}`,
      );
    }
    const left = offset?.left ?? 0,
      top = offset?.top ?? 0;
    return {
      left: left * paint.scrollXx + top * paint.scrollYx,
      top: left * paint.scrollXy + top * paint.scrollYy,
    };
  };
  const layoutAt = (node, at) => {
    const rect = boxAt(node, at);
    if (!rect) return null;
    // The root border box travels with its own native scroll; nested scrollport
    // borders stay put while their contents move.
    const rootScroll =
      node === document.scrollingElement ? viewportScroll(node, at) : null;
    let left = rect.left + (rootScroll?.left ?? 0),
      top = rect.top + (rootScroll?.top ?? 0);
    for (
      let child = node, parent = paintAt(child, at).parent;
      parent instanceof Element;
      child = parent, parent = paintAt(parent, at).parent
    ) {
      if (paintAt(child, at).position === "fixed") break;
      const scroll = viewportScroll(parent, at);
      left += scroll.left;
      top += scroll.top;
    }
    return { left, top, right: left + rect.width, bottom: top + rect.height };
  };
  // Each input's rendering: when it began; the latest frame it owns; the motion
  // it began; whether news has landed since; and a keystroke's typing, which holds
  // its field; the box of the field
  // and of each element holding it at the key; the animations already moving any of
  // them; and until when the typing rule reads it.
  const renderings = [];
  let open = null;
  // The typing rule stops reading the open rendering, which runs on.
  const unwatch = () => {
    if (open?.typing?.until === Infinity)
      open.typing.until = read(nativePerformance.now(), false);
  };
  const end = () => {
    unwatch();
    // Seal effects the gesture already began before a newer input replaces it.
    if (open && !open.told) {
      for (const animation of begun(open.start)) open.own.add(animation);
      open.told = true;
    }
    open = null;
  };
  const begin = (start, typing = null, own = new Set()) => {
    end();
    open = {
      start,
      first: true,
      through: Infinity,
      own,
      told: false,
      last: false,
      typing,
    };
    renderings.push(open);
  };
  // Shifts whose frame has no reading after it yet.
  const waiting = [];
  const tick = (time) => {
    const at = read(time);
    if (open) {
      // Effects begun before news retain their exact property evidence below.
      // A persistent attachment or a still-running time effect does not keep the
      // creator's counted input rendering open after its declared completion.
      if (!open.told)
        for (const animation of begun(open.start)) open.own.add(animation);
      if (open.last) end();
      // A settled reading here counts updates before this one; this frame's own
      // callbacks may still move a box, so the rendering runs through the next.
      else open.last = settled();
    }
    // A gesture owns its counted rendering until canonical completion. News seals
    // that credit; continuing motion retains its separate ownership below. A newer
    // input still leaves the prior gesture its first two frame readings.
    for (const rendering of renderings) {
      if (
        !rendering.first &&
        (rendering.through === Infinity || (rendering === open && !rendering.told))
      )
        rendering.through = at;
      rendering.first = false;
    }
    const motion = frames.at(-1).motion;
    for (const rendering of renderings)
      for (const animation of rendering.own)
        if (animation.playState === "running") motion.push(animation);
    audit();
    judge(waiting.splice(0));
    nativeFrame(tick);
  };
  nativeFrame(tick);
  window.lfInputWork.subscribeEdits(({ node: field }) => {
    const holding = [];
    for (let at = field; at instanceof Element; at = up(at)) holding.push(at);
    const start = nativePerformance.now();
    const at = read(start, false);
    begin(start, {
      field,
      at,
      found: boxes(
        holding.filter((node) => {
          const paint = paintAt(node, at);
          return (
            node === field ||
            paint.reading ||
            paint.control ||
            paint.reflow ||
            paintedHolder(node)
          );
        }),
      ),
      moving: holding
        .flatMap((node) => node.getAnimations())
        .filter((animation) => animation.playState === "running" && moves(animation)),
      until: Infinity,
    });
  });
  // A viewport resize is input, and its new size is the fact. Chrome lays out the
  // resized viewport before dispatching resize, which precedes the frame's callbacks,
  // so tick() always runs after it; a layout-shift record delivered between the two,
  // as one from an earlier frame can be on a busy machine, has its pose read at the new
  // size, so the observer looks at the size before reading. The preceding pose seals
  // typing; taking a new pose here would attribute the resize to the key.
  let viewport = [innerWidth, innerHeight];
  const resized = () => {
    if (innerWidth === viewport[0] && innerHeight === viewport[1]) return;
    viewport = [innerWidth, innerHeight];
    const before = frames.at(-1)?.at ?? nativePerformance.now();
    if (open?.typing?.until === Infinity) open.typing.until = before;
    begin(nativePerformance.now());
  };
  window.addEventListener("resize", resized);
  // When the page adopted each server reading.
  new MutationObserver(() => {
    unwatch();
    if (open) open.told = true;
  }).observe(document, { subtree: true, attributeFilter: ["data-lf-reading"] });
  // Press, drag, release and native activation are phases of one pointer gesture.
  // Each phase keeps its own paint boundary while sharing the effects that press
  // began. A later press starts fresh; native timeline reassignment cannot adopt
  // an unrelated older effect into it.
  const presses = new Map();
  const heard = (event) => {
    if (!event.isTrusted || (event.type === "pointermove" && !event.buttons)) return;
    if (event.type === "pointerdown") presses.set(event.pointerId, new Set());
    begin(nativePerformance.now(), null, presses.get(event.pointerId) ?? new Set());
    if (event.type === "click") presses.delete(event.pointerId);
  };
  for (let view = window; ; view = view.parent) {
    let held;
    try {
      held = view.document;
    } catch {
      break;
    }
    // A gesture has press, active movement and activation/release phases. Hover
    // supplies no geometry ownership; native click also covers keyboard activation.
    for (const type of [
      "keydown",
      "pointerdown",
      "pointermove",
      "pointerup",
      "click",
      "wheel",
    ])
      held.addEventListener(type, heard, true);
    held.addEventListener(
      "pointercancel",
      (event) => presses.delete(event.pointerId),
      true,
    );
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
    nativeFrame(() =>
      nativeFrame((at) => {
        presented = at;
      }),
    );
  }).observe(document, { subtree: true, attributeFilter: ["data-lf-presented"] });
  // A hidden-tab return deliberately replaces the layout the reader left. Its
  // first refreshed presentation belongs to that return, even when the network
  // answer arrives later. Consume the runtime's boundary, never a timed grace.
  const returns = [];
  let continuityTurn = 0;
  document.addEventListener("lf-reading-continuity", ({ detail }) => {
    const turn = ++continuityTurn;
    const current = returns.at(-1);
    if (!detail.continuous) {
      if (current?.through === Infinity) return;
      returns.push({ start: nativePerformance.now(), through: Infinity });
    } else if (current?.through === Infinity) {
      nativeFrame(() =>
        nativeFrame((at) => {
          if (turn === continuityTurn) current.through = at;
        }),
      );
    }
  });
  const presenting = ({ startTime }) =>
    document.querySelector("script[data-lf-entry]") &&
    (presented === null ||
      startTime < presented ||
      returns.some(({ start, through }) => startTime >= start && startTime <= through));
  const permittedReflow = ({ node, previousRect, currentRect }, around) => {
    const element = node?.nodeType === Node.TEXT_NODE ? up(node) : node;
    if (around.length !== 3) return false;
    const regions = new Set(
      around.flatMap(({ at }) =>
        ancestryAt(element, at).filter((ancestor) => {
          const mode = paintAt(ancestor, at)?.reflow;
          return typeof mode === "string" && mode !== "append";
        }),
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
  // Append declarations own a source, not all motion in a container. The retained
  // prefix proves that growth came after the old children; unchanged old boxes keep
  // a fold or a rewritten message from borrowing that growth. Only its normal-flow
  // followers in the same stationary runtime scrollport may be carried by it.
  const appendGrowth = (around) => {
    if (around.length !== 3) return [];
    const first = around[0].at,
      last = around[2].at;
    const stable = (node, screen = false) => {
      const rects = around.map(({ at }) =>
        screen ? boxAt(node, at) : layoutAt(node, at),
      );
      return rects.every(Boolean) && rects.every((rect) => !moved(rects[0], rect));
    };
    return around[0].nodes.flatMap((source) => {
      const readings = around.map(({ at }) => paintAt(source, at));
      if (!readings.every((paint) => paint?.reflow === "append")) return [];
      const before = readings[0].appendChildren,
        after = readings[2].appendChildren;
      if (
        !before.length ||
        after.length <= before.length ||
        !before.every(
          (child, i) =>
            readings.every((paint) => paint.appendChildren[i] === child) &&
            stable(child),
        )
      )
        return [];
      const prior = layoutAt(source, first),
        next = layoutAt(source, last);
      if (
        !prior ||
        !next ||
        next.bottom - prior.bottom < 1 ||
        !around.every(({ at }) => {
          const box = layoutAt(source, at);
          return (
            box &&
            ["left", "right", "top"].every(
              (edge) => Math.abs(box[edge] - prior[edge]) < 1,
            )
          );
        })
      )
        return [];
      const port = ancestryAt(source, first).find(
        (owner) => owner !== source && paintAt(owner, first)?.scrollportY,
      );
      if (
        !port ||
        port === document.scrollingElement ||
        !stable(port, true) ||
        !around.every(
          ({ at }) =>
            ancestryAt(source, at).includes(port) &&
            paintAt(port, at)?.scrollportY &&
            ancestryAt(port, at).some((owner) => paintAt(owner, at)?.runtime) &&
            ancestryAt(source, at)
              .slice(1, ancestryAt(source, at).indexOf(port) + 1)
              .every((owner) => !paintAt(owner, at)?.reflow),
        )
      )
        return [];
      return [{ source, port, bottom: prior.bottom, by: next.bottom - prior.bottom }];
    });
  };
  const permittedAppend = (node, previousRect, currentRect, around, growth) => {
    const first = around[0].at,
      last = around[2].at;
    const element = node.nodeType === Node.TEXT_NODE ? up(node) : node;
    const ancestry = around.map(({ at }) => ancestryAt(element, at));
    const before = layoutAt(node, first),
      after = layoutAt(node, last);
    if (!before || !after) return false;
    const carries = growth.filter(
      ({ source, port, bottom }) =>
        ancestry.every(
          (parents) => parents.includes(port) && !parents.includes(source),
        ) && before.top >= bottom - 1,
    );
    let by = carries.reduce((sum, each) => sum + each.by, 0);
    if (!by) return false;
    // A following sticky row receives that carry only until its unchanged inset
    // meets the scrollport's padded content edge. Its descendants keep that exact
    // clamped carry, so extra motion remains an independent finding.
    const sticky = ancestry[2].find(
      (owner) => paintAt(owner, last)?.position === "sticky",
    );
    if (sticky) {
      const binding = paintAt(sticky, first);
      if (
        !around.every(({ at }) => {
          const paint = paintAt(sticky, at);
          return (
            paint?.position === "sticky" &&
            paint.stickyTop === binding.stickyTop &&
            paint.stickyBottom === binding.stickyBottom
          );
        })
      )
        return false;
      const port = ancestryAt(sticky, last).find(
        (owner) => owner !== sticky && paintAt(owner, last)?.scrollportY,
      );
      if (!carries.every((each) => each.port === port)) return false;
      const prior = layoutAt(sticky, first),
        paint = paintAt(sticky, last),
        portPaint = paintAt(port, last),
        portBox = boxAt(port, last),
        portLayout = layoutAt(port, last);
      const edge = (side, inset) =>
        portLayout.top +
        portPaint[side] -
        portBox.top +
        viewportScroll(port, last).top +
        viewportScroll(port, last, { left: 0, top: inset }).top;
      if (paint.stickyTop !== null)
        by =
          Math.max(
            prior.top + by,
            edge("clipTop", portPaint.paddingTop + paint.stickyTop),
          ) - prior.top;
      if (paint.stickyBottom !== null)
        by =
          Math.min(
            prior.bottom + by,
            edge("clipBottom", -portPaint.paddingBottom - paint.stickyBottom),
          ) - prior.bottom;
    }
    // Compare each fragment in its retained layout coordinates. A carried container
    // cannot excuse an extra move or repacking by one of its descendants.
    const priorBox = boxAt(node, first),
      nextBox = boxAt(node, last);
    return ["left", "right", "top", "bottom"].every((edge) => {
      const axis = edge === "left" || edge === "right" ? "left" : "top";
      const prior = previousRect[edge] - priorBox[axis] + before[axis];
      const next = currentRect[edge] - nextBox[axis] + after[axis];
      return Math.abs(next - prior - (axis === "top" ? by : 0)) < 1;
    });
  };
  const paintState = (node, rect, at) => {
    const own = paintAt(node, at);
    if (!own.shown || own.visibility !== "visible" || own.opacity === "0")
      return { paintable: false, visible: false };
    let left = Math.max(0, rect.left),
      top = Math.max(0, rect.top);
    let right = Math.min(innerWidth, rect.right),
      bottom = Math.min(innerHeight, rect.bottom);
    let escaped = false,
      containing = null;
    for (
      let parent = own.reading ? own.parent : node;
      parent instanceof Element;
      parent = paintAt(parent, at)?.parent
    ) {
      const style = paintAt(parent, at);
      if (style.opacity === "0") return { paintable: false, visible: false };
      if (escaped && parent === containing) escaped = false;
      if (!escaped && parent !== node) {
        if (style.clipsX) {
          left = Math.max(left, style.clipLeft);
          right = Math.min(right, style.clipRight);
        }
        if (style.clipsY) {
          top = Math.max(top, style.clipTop);
          bottom = Math.min(bottom, style.clipBottom);
        }
      }
      if (
        !escaped &&
        style.block !== undefined &&
        ["fixed", "absolute"].includes(style.position)
      ) {
        escaped = true;
        containing = style.block;
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
        return (
          sum +
          (prior && next
            ? viewportScroll(owner, to, {
                left: next.left - prior.left,
                top: next.top - prior.top,
              })[axis]
            : 0)
        );
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
  const writtenPoint = (selection, axis) =>
    selection.point[axis] -
    (selection.edges[axis] === axis
      ? 0
      : selection.size[axis === "left" ? "width" : "height"]);
  const scrollMotion = (node, from, to) => {
    const motion = nativeScrollMotion(node, from, to);
    const element = node.nodeType === Node.TEXT_NODE ? up(node) : node;
    const anchored = { left: false, top: false };
    const ancestors = ancestryAt(element, to);
    for (const owner of ancestors) {
      const selections = floating.get(owner);
      const was = selections?.findLast((reading) => reading.at <= from)?.selection;
      const now = selections?.findLast((reading) => reading.at <= to)?.selection;
      const crossesFixed = ancestors
        .slice(0, ancestors.indexOf(owner))
        .some(
          (node) =>
            paintAt(node, from)?.position === "fixed" ||
            paintAt(node, to)?.position === "fixed",
        );
      const sameAttachment =
        was &&
        now &&
        !crossesFixed &&
        was.tenure === now.tenure &&
        was.subject === now.subject &&
        was.anchor === now.anchor;
      if (
        sameAttachment &&
        was.plane === "window" &&
        now.plane === "window" &&
        was.scrollOffsets &&
        now.scrollOffsets?.length === was.scrollOffsets.length &&
        was.scrollOffsets.every(
          (source, i) => source.source === now.scrollOffsets[i].source,
        )
      ) {
        const reach = { left: [0, 0], top: [0, 0] };
        for (const [i, before] of was.scrollOffsets.entries()) {
          const after = now.scrollOffsets[i];
          if (before.left === after.left && before.top === after.top) continue;
          const by = viewportScroll(before.source, from, {
            left: before.left - after.left,
            top: before.top - after.top,
          });
          for (const axis of ["left", "top"]) {
            reach[axis][0] += Math.min(0, by[axis]);
            reach[axis][1] += Math.max(0, by[axis]);
          }
        }
        for (const axis of ["left", "top"]) {
          const carried = now.reference[axis] - was.reference[axis];
          const placed = writtenPoint(now, axis) - writtenPoint(was, axis);
          if (
            carried >= reach[axis][0] - 1 &&
            carried <= reach[axis][1] + 1 &&
            placed >= Math.min(0, carried) - 1 &&
            placed <= Math.max(0, carried) + 1
          )
            motion[axis] += placed;
        }
      }
      if (sameAttachment && was.plane !== now.plane) {
        // A selection's point is measured from its frame's box: the subject anchor's
        // in the page's plane, the holding region's in a region's, the window's in
        // the window's.
        const origin = (selection, time) =>
          selection.frame ? boxAt(selection.frame, time) : { left: 0, top: 0 };
        const before = origin(was, poseAt(owner, from)),
          after = origin(now, to);
        if (before && after) {
          for (const axis of ["left", "top"]) {
            if (anchored[axis]) continue;
            const predicted = (selection, frame) =>
              writtenPoint(selection, axis) + frame[axis];
            motion[axis] += predicted(now, after) - predicted(was, before);
            anchored[axis] = true;
          }
        }
      }
      const prior = paintAt(owner, from),
        next = paintAt(owner, to);
      const anchor = prior?.anchor;
      if (!anchor || anchor !== next?.anchor) continue;
      // Native anchor layout can follow its scroller in the next frame. Credit
      // source scrolling since this retained portal pose was first observed.
      const start = poseAt(owner, from);
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
    const growth = appendGrowth(around);
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
            !permittedAppend(node, previousRect, currentRect, around, growth) &&
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
  const inputOwns = (at) =>
    renderings.some((gesture) => at >= gesture.start && at <= gesture.through);
  const audit = () => {
    if (frames.length < 2) return;
    const at = nativePerformance.now(),
      frame = frames.at(-1).at;
    const rendering = renderings.findLast(({ start }) => start <= at);
    if (rendering?.typing && at <= rendering.typing.until) return;
    const entry = { startTime: at, sources: [] };
    // Gesture ownership is its bounded rendering, not Chrome's half-second credit.
    if (presenting(entry) || inputOwns(frame)) return;
    const before = frames.at(-2),
      after = frames.at(-1);
    // No pose was appended between the two readings, so none moved.
    if (before.written === after.written) return;
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
  // Native observer delivery can precede the next health frame. Its passive pose
  // belongs to the native paint it reports; a later input cannot replace that pose
  // with its own geometry merely because health-frame sampling was delayed.
  const observedPaint = new WeakMap();
  const judge = (entries) => {
    for (const entry of entries) {
      const at = entry.startTime;
      // The frame that painted the shift, and the next, whose start reads what it
      // painted. Readings older than are kept are gone (-1).
      const frame = frames.findLastIndex(({ start: time }) => time <= at);
      const observed = observedPaint.get(entry);
      const next = observed?.at ?? frames[frame + 1]?.at;
      if (frame !== -1 && next === undefined) {
        waiting.push(entry);
        continue;
      }
      const rendering = renderings.findLast(({ start }) => start <= at);
      if (observed && frame !== -1)
        protectedMotion([frames[frame], frames[frame], observed]);
      const typing = rendering?.typing;
      if (typing && at <= typing.until) {
        // A later frame may include the next gesture; typed() caps its reading at
        // the closing pose captured before that gesture began.
        if (frame !== -1) typed(entry, typing, next);
      }
      admittedMotion(entry, next ?? nativePerformance.now(), rendering);
    }
  };
  // Native records, delivered to the observer or taken at a paint checkpoint. A
  // painted shift is the evidence every verdict starts from, so the reading that
  // judges it is complete whatever changed the page, announced or not.
  const received = (entries) => {
    announce();
    resized();
    for (const entry of entries) {
      const frame = frames.findLastIndex(({ start }) => start <= entry.startTime);
      // Layout follows the entering frame callback. Counted work can still own
      // that frame when the paint's timestamp is newer than its sampled pose. A
      // following frame that kept an unchanged reading has not read this paint.
      if (
        frame === -1 ||
        frames[frame + 1]?.complete ||
        presenting(entry) ||
        inputOwns(entry.startTime) ||
        inputOwns(frames[frame].at)
      )
        continue;
      // A newer input already dispatched makes this observation an ambiguous
      // endpoint. Retain the native entry for the ordinary frame ledger instead.
      if (renderings.some(({ start }) => start > entry.startTime)) continue;
      const at = read(nativePerformance.now(), false);
      observedPaint.set(entry, {
        at,
        nodes: everything(),
        motion: frames[frame].motion,
      });
    }
    judge(entries);
  };
  const observer = new PerformanceObserver((list) => received(list.getEntries()));
  observer.observe({ type: "layout-shift" });
  // Once two native frames and their task checkpoint complete, Chrome has painted
  // the work preceding `through`. Drain its native records before retiring that
  // history. Keep the entering pose and active typing's origin, whose comparison
  // can outlive any number of paint checkpoints. Unadmitted movement before this
  // checkpoint was not painted as a layout shift (e.g. a transform-only move).
  const retire = (through) => {
    for (let i = pendingMotion.length - 1; i >= 0; i--)
      if (
        pendingMotion[i].after <= through &&
        !waiting.some((entry) => pendingMotion[i].before <= entry.startTime)
      )
        pendingMotion.splice(i, 1);
    const needed = Math.min(
      through,
      ...waiting.map((entry) => entry.startTime),
      ...pendingMotion.map((move) => move.before),
      ...renderings
        .filter(
          (rendering) =>
            rendering.typing &&
            (rendering.typing.until === Infinity ||
              waiting.some(
                (entry) =>
                  entry.startTime >= rendering.start &&
                  entry.startTime <= rendering.typing.until,
              )),
        )
        .map((rendering) => rendering.typing.at),
    );
    while (frames.length > 2 && frames[1].start < needed) frames.shift();
    // Native frame starts associate painted shifts; poses are sampled later in the
    // callback's synchronous turn. Retaining that frame cannot retire an earlier
    // input pose its readers still need. All coordinate histories keep the same
    // earliest required reading.
    retainedFrom = Math.min(needed, frames[0]?.at ?? -Infinity);
    for (let i = renderings.length - 1; i >= 0; i--) {
      const rendering = renderings[i];
      if (
        rendering !== open &&
        rendering.through < retainedFrom &&
        (rendering.typing?.until ?? -Infinity) < retainedFrom &&
        ![...rendering.own].some(({ playState }) => playState === "running")
      )
        renderings.splice(i, 1);
    }
  };
  const drained = (through) => {
    judge(waiting.splice(0));
    const records = observer.takeRecords();
    if (records.length) received(records);
    retire(through);
  };
  // Paint checkpoints keep the ledger bounded by outstanding evidence, even on a
  // page that stays still and therefore sends no layout-shift observer callbacks.
  // Only tick() samples poses and classifies their input ownership; a task between
  // frames must not manufacture another frame with a different ownership reading.
  const checkpoint = () => {
    const through = nativePerformance.now();
    nativeFrame(() =>
      nativeFrame(() =>
        nativeTask(() => {
          drained(through);
          checkpoint();
        }),
      ),
    );
  };
  checkpoint();
  const drawing = () => {
    if (document.hidden) return false;
    // The driver sees owners across origins; an opaque child cannot. Read it
    // again while draining because an ancestor can hide after judgement starts.
    if (window.lfWatchJudgement?.ancestorsDrawn === false) return false;
    for (let view = window; view.frameElement; view = view.parent)
      if (!view.frameElement.checkVisibility()) return false;
    return true;
  };
  // The fixture awaits actual paint and observer drainage. An outer hang watchdog
  // may fail this wait; no elapsed-time fallback can turn unfinished paint green.
  window.lfShiftsJudged = () => {
    // The next unannounced frame is checked, so a test that ends before the
    // periodic check still has its last change compared.
    quiet = VERIFY - 1;
    const through = nativePerformance.now();
    const hidden = () => {
      // Hidden documents have no pending native paint. Their existing records are
      // still judged against a fresh pose; visibility is a fact, not a time limit.
      read(nativePerformance.now());
      drained(through);
    };
    if (!drawing()) {
      hidden();
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      let complete = false;
      let visibilityTask;
      const finish = () => {
        if (complete) return;
        complete = true;
        window.lfWatchPlatform.cancelLater(visibilityTask);
        resolve();
      };
      // Display can change through CSSOM, media queries or ancestor layout without
      // a DOM mutation or visibility event. Poll its platform fact while paint is
      // pending; the interval schedules a reading and never decides the result.
      const visibility = () => {
        if (complete) return;
        if (!drawing()) {
          hidden();
          finish();
        } else visibilityTask = nativeTask(visibility, 100);
      };
      visibilityTask = nativeTask(visibility, 100);
      nativeFrame(() =>
        nativeFrame(() =>
          nativeTask(() => {
            if (complete) return;
            drained(through);
            // Records of this checkpoint's latest paint need the following native
            // frame's pose. tick() judges them there before this task resolves.
            nativeFrame(() => nativeTask(finish));
          }),
        ),
      );
    });
  };
})();
