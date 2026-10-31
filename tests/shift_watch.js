// Checks the Stability contract using protected reading/control landmarks.
//
// Scope. The sensor credits movement the browser's own placement mechanisms produce,
// modelled in general for any markup, never for one shape Leaf ships: scrolling,
// which layout coordinates remove, except where it carries the control a gesture was
// made on (Scrolls a gesture makes); sticky positioning, through its scroller's travel;
// CSS anchor positioning, through its anchor's scroll; and native animation, scroll-
// driven included, through sampled translation or reflow from size changes.
// Beside those, it credits only what the Stability contract itself declares:
// a gesture's rendering, the page before it
// presents or as it returns from a hidden tab, and runtime regions declared with
// `data-lf-reflow`. A script that moves a box by writing its geometry has no credit
// of its own, however the page means it, so a surface that should follow something
// stands by a native mechanism that does. A new layout shape therefore needs no rule
// here: where its motion is native, the general rule already credits it, and where it
// is scripted, the sensor reports it.
//
// Leaf's floating surfaces (floating.js) keep two credits for what their solver still
// writes, until a native mechanism carries it: the inset an attachment limiter rewrites
// as an anchored surface's target travels (`native_camera`), and a switch between the
// page's plane and the window or region edge that holds it in (`floating_plane`). The
// owner's last-written held-edge point, published as `lfFloatingSelections`, declares
// each under the same subject, anchor and tenure; its solver dimensions, not the
// holder's rendered displacement, supply the credit, and a rewrite is credited only
// within the travel of its source. That travel is read from an independent, unpainted
// native anchor (a camera), whose point no displacement of the holder moves.
//
// Chrome admits painted layout transitions; a retained per-frame ledger supplies
// their meaning. Source rectangles do not choose which landmarks get examined, so
// anonymous sources, decorative pseudos and the five-source cap cannot excuse a
// surviving control or reading line that was carried. Native visibility records
// closed disclosure content correctly; sampled hidden layout is not painted text.
//
// A box may grow or shrink at one edge while text and controls remain stationary.
// Reading text is measured with Range fragments, including text inside a stationary
// parent. A control's complete text identifies its label: a retained fragment inside
// a replaced label is new content, even when a renderer reuses its text node.
// The control's own box remains protected through that replacement.
// Controls and declared regions keep their actual boxes. Runtime-declared
// bounded reflow retains its historical ownership, stationary-boundary and clipping
// proof. An append region may carry following content inside its stationary
// scrollport or floating container by its measured suffix growth: new children,
// the existing ones retaining their boxes, or, where none joins, its last child
// growing at its foot where that
// child declares itself the growing tail (`data-lf-append-tail`), as a thread's
// working message and a reply still streaming do, or that tail giving way to the
// children joining in its place, as the working message does to the answer. A
// scrollport that grows at its foot by no more than that growth, as a floating card
// sized to its thread does, is stationary for this: it keeps its other edges. One that declares it stands on its
// foot (`data-lf-rises`), as the floating panel's thread view stands on its row, may
// instead rise at its head by no more than that growth, carrying all it holds, and its
// own head, up by its rise: the one case where news may carry controls (`appendGrowth`).
// Layout coordinates remove scrolling; sticky descendants retain their
// mechanical scroller's ownership. Portals with one unique anchor, in their tree or
// inside the `anchor-scope` that limits its name, and a direct native anchor inset,
// inline or in their tree's own rules, retain that scroller too; nested CSS
// expressions, ambiguous names and rules that disagree receive no inferred ownership.
//
// Scrolls a gesture makes. Layout coordinates remove scrolling, so a scroll inside a
// gesture's rendering would credit itself, though it carries the control the user
// just pressed out from under their aim (browser/AGENTS.md, "Stability"). So the
// gesture's aim, the control a press lands on or the one holding focus for a key,
// keeps its place on screen through that rendering, read fresh in viewport pixels
// beside the scroll offsets of the boxes that carry it. A scroll may hold it still,
// or take back part of what the gesture's own layout moved it, or bring it whole into
// the view of a box that showed only part of it (its scrollport less its
// scroll-padding, which the aim's scroll-margin must clear) by no more than the part
// it hid, as the browser's own focus does, and carry it no further. A gesture that takes the user somewhere may:
// a command declares it (`travels` on its register row, which the dispatcher's
// `lf-command-invoked` carries), and so does the history entry a gesture adds, as a
// root tab set's switch adds one; a link does by the platform's meaning, its script's
// travel included, and a key the page leaves to the browser by the browser's. Back
// and Forward are the user's gestures, made in the browser's chrome, and open a
// rendering as an input does. Caret navigation is also the editor's own where it
// implements those platform keys itself, preventing their defaults (CodeMirror
// does). The runtime owns both the caret keys and which controls take text. A scroll
// is the gesture's on each box its own work called a scrolling API on, and for a
// reveal or focus that doesn't prevent its scroll on every box holding the target,
// as input_work_watch.js names the input of the call; a call work no input owns
// makes during the rendering, as a test's script does, leaves the rendering
// unjudged. So a scroll begun where the input's source is lost, after a native
// `await` or in an observer's delivery, goes unjudged, as does one the browser makes
// alone, such as a clamp. The driver's own scroll before its next press counts only
// on a box the gesture's own work scrolled too.
//
// Each trusted gesture owns its counted rendering until declared completion. A widget
// preparation it began (`observePreparations`) works on in a promise the loop
// cannot see; the gesture owns that preparation's landing, as a rendering from the
// task that settles it until the loop settles again, and nothing while it waits. It
// began one only when its declaration carries that input's exact callback source.
// Native effects it began retain their sampled displacement within their subtree.
// A native size animation also credits a later box when its size change travels
// through the layout path to that box and matches its movement. Its continued
// lifetime never owns unrelated page movement.
// Native scroll effects belong to their retained scroll source, regardless of the
// gesture that created them. Stable timeline bindings and translation trajectories
// credit only source-collinear travel bounded by that source's viewport scroll.
// A uniform keyframe origin rebase is removed from the sampled translation, so a
// compensated placement cannot erase its scroll cause or adopt unrelated motion.
// News starts passive rendering except the first frame shared with the gesture.
// A typing field is observed at its native edit start, independently of Chrome's
// clipped or shadowed source rectangles. Its subject, protected reading/control and
// declared-region ancestors, and visibly painted holders retain their poses.
// Transparent coordinate carriers have no independent pose to protect: a compensated
// carrier rebase can leave every painted subject stationary. Motion
// already running on its ancestors belongs to the gesture that began that motion.
// Continuing translation is credited from sampled animated property values, not
// the ancestor's whole box: independent movement of it or its children still fails.
// This proof supports unique replace effects with pure transform translation, a
// `translate` in pixels or percentages of the border box (including a directly bound
// inline custom property), a pixel-only stylesheet consumer of an inherited custom
// property, or pixel
// left/top/marginLeft/marginTop. A sticky box's animated inset is the line it sticks
// at, not an offset, so it credits only the box's move within its containing block
// (`stickyInsetMotion`). Scale, rotation and
// composed effects receive no inferred translation credit.
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
// animation anywhere in the composed tree, or one that stopped or left the set,
// except a scroll-driven one, which moves only as the scroll and layout announced
// here move it; input, focus, scroll, drag, resize, load, reset and beforetoggle
// events; the emulated media tests change; this frame's own visibility; and the
// calls that restyle without a DOM write (custom states, constructed and adopted
// sheets, form-control values and ranges, animation mutators). A child cannot
// observe every change in its embedding page, so child-frame readings remain
// complete. Every
// VERIFY-th unannounced frame, and the first one once the fixture asks for the test's
// verdict, reads completely and fails where any reading differs, naming the innermost
// node that changed, so a source missing from this list is found rather than
// leaving the readings between entries stale. A page that writes while it is read
// announces its change by that write. A change to this gate runs the suite with
// VERIFY = 1, which checks every frame.
//
// Unpresented frames. Until the runtime stamps `data-lf-presented`, movement without
// input is exempt (Scope: the page before it presents). While such a page is still
// changing, with nothing focused and no input's rendering retained, a frame takes no
// complete reading and leaves its changes unread. The first frame in which the page
// rests reads them, and so does a trusted input before any of the page's handlers
// run; focus, an input's rendering or the stamp then ends the deferral. So
// verification and the poses an input's verdicts look back to are read as before,
// with one known exception: on a page that never rests, a script that scrolls and
// focuses in one task moves an anchored field before the watch first sees it, and
// that scroll goes uncredited if typing follows within a frame. A page still
// upgrading changes in nearly every frame, and each of those readings forced a style
// and layout pass of its own.
//
// Movement findings retain the exact comparison and credits that decided them,
// alongside the sampled scroll/attachment/animation inputs. Only admitted failures
// serialize that evidence; healthy frames emit nothing. Passive chains keep their
// individual comparisons instead of inventing an aggregate credit after the fact.
//
// Every finding fails the ordinary browser fixture. It installs this sensor after
// write_watch.js and binds the canonical control and clipping vocabulary.
(() => {
  const { listen } = window.lfWatchPlatform;
  // A native paint/task checkpoint retires only evidence it has judged. Execution
  // time says nothing about whether Chrome has delivered an earlier painted shift.
  let retainedFrom = -Infinity;
  const pruneSamples = (list) => {
    while (list.length > 1 && list[1].at <= retainedFrom) list.shift();
  };
  const GEOMETRY =
    /^(transform|translate|scale|rotate|inset|top|left|right|bottom|width|height|blockSize|inlineSize|minBlockSize|minInlineSize|maxBlockSize|maxInlineSize|margin|padding)/;
  const SIZE_GEOMETRY = new Set(["blockSize", "height", "inlineSize", "width"]);
  // Retain the consumer through finish cleanup. Replacing it while the effect is
  // active cannot borrow the animation's input ownership.
  const translationBindings = new WeakMap();
  const animationProperties = (animation) => {
    const keys = [
      ...new Set((animation.effect?.getKeyframes() ?? []).flatMap(Object.keys)),
    ];
    const properties = keys.filter((key) => GEOMETRY.test(key));
    // A registered property can drive a native translate indirectly. Read the
    // resulting translate, rather than treating its custom-property value as
    // geometry; the box motion uses this to keep translate and clip in one clock.
    if (!translationBindings.has(animation)) {
      const consumer = animation.effect?.target?.style.translate ?? "";
      const vars = new Set(
        [...consumer.matchAll(/var\(\s*(--[-\w]+)/g)].map((match) => match[1]),
      );
      translationBindings.set(
        animation,
        !properties.includes("translate") && keys.some((key) => vars.has(key))
          ? consumer
          : null,
      );
    }
    if (translationBindings.get(animation)) properties.push("translate");
    return properties;
  };
  // Use the runtime's rendered ancestry, including forwarding slots and shadow hosts.
  const up = renderedParent;
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
  // Where a node stands (write_watch.js, `place`); null once the API no longer names it.
  const name = (node) => (node ? window.lfPlace(node) : null);
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
  // Native media sources and nodes detached during a reading can have no computed
  // length. Keep that absence stable; NaN would disagree with itself every frame.
  const pixels = (value) => (/^-?[\d.]+px$/.test(value) ? parseFloat(value) : null);
  // A preparation owns only its source-bound landing below. Waiting for its full
  // settlement here would give the input every unrelated move while it waits.
  const settled = () =>
    document.querySelector("script[data-lf-entry]")?.lfRenderingState?.()
      .updatesSettled ?? true;
  // An animation that can move a box: one of its keyframes sets a geometric property.
  const moves = (animation) =>
    animationProperties(animation).length > 0 ||
    GEOMETRY.test(animation.transitionProperty ?? "") ||
    inheritedBindings(animation).length > 0;
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
  // Pausing keeps the gesture's effect; seeking changes only its sampled native
  // displacement and never credits independent layout or a replaced consumer.
  const activeMotion = (animation) =>
    ["running", "paused"].includes(animation.playState);
  // Motion begun since `start` that moves a box; one still pending begins now.
  const begun = (start) =>
    allAnimations().filter(
      (animation) =>
        activeMotion(animation) &&
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
  // Declarations that can win a property: an important inline one alone, else
  // important matching rules, else inline style, else every matching rule. No API
  // reports the cascade's specificity/layer/order result, so consumers require all
  // candidates in that tier to prove the same relationship. Gather only rules
  // stating the requested property, once per sheet and property.
  const declarationRules = new WeakMap();
  const rulesStating = (sheet, property) => {
    if (
      sheet.href &&
      new URL(sheet.href).origin !== window.origin &&
      !sheet.ownerNode?.hasAttribute("crossorigin")
    )
      return [];
    const length = sheet.cssRules.length;
    const cached = declarationRules.get(sheet) ?? new Map();
    const known = cached.get(property);
    if (known?.length === length) return known.rules;
    const rules = [];
    const visit = (list, conditions) => {
      for (const rule of list) {
        if (rule instanceof CSSStyleRule) {
          if (rule.style.getPropertyValue(property)) rules.push({ rule, conditions });
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
    cached.set(property, { length, rules });
    declarationRules.set(sheet, cached);
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
      for (const { rule, conditions } of rulesStating(sheet, property)) {
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
  // A direct translation consumer is proved from declarations, not a coincidental
  // equality of computed values. Keep the existing conservative cascade tiers:
  // every candidate in the winning tier must name the same animated variable.
  const declaredValues = (node, property) => {
    const inline = node.style.getPropertyValue(property);
    if (inline && node.style.getPropertyPriority(property)) return [inline];
    const rules = declaredRules(node, property, Boolean(inline));
    return rules.important.length ? rules.important : inline ? [inline] : rules.normal;
  };
  const inheritedConsumers = new WeakMap();
  const findConsumers = (target, keys) => {
    keys = keys.filter((key) => key.startsWith("--"));
    const consumers = [];
    if (target && keys.length) {
      const trees = [
        target,
        ...[...roots].filter((root) => {
          for (let at = root.host; at; at = up(at)) if (at === target) return true;
          return false;
        }),
      ];
      for (const node of new Set(
        trees.flatMap((tree) => [
          ...(tree instanceof Element ? [tree] : []),
          ...tree.querySelectorAll("*"),
        ]),
      )) {
        const values = declaredValues(node, "translate");
        const key = keys.find(
          (key) =>
            values.length && values.every((value) => value.trim() === `var(${key})`),
        );
        if (key) consumers.push({ node, key });
      }
    }
    return consumers;
  };
  const inheritedBindings = (animation) => {
    if (!inheritedConsumers.has(animation))
      inheritedConsumers.set(
        animation,
        translationBindings.get(animation)
          ? []
          : findConsumers(animation.effect?.target, [
              ...new Set((animation.effect?.getKeyframes() ?? []).flatMap(Object.keys)),
            ]),
      );
    return inheritedConsumers.get(animation);
  };
  const consumerOrigins = (bindings) =>
    new Map(
      bindings.map(({ node }) => [
        node,
        animatedValue(node, getComputedStyle(node), "translate"),
      ]),
    );
  const inheritedReading = (animation, binding, returning) => {
    const { node, key } = binding,
      target = animation.effect.target;
    if (
      animation.effect.composite !== "replace" ||
      animation.effect
        .getKeyframes()
        .some(
          (frame) => frame.composite && !["auto", "replace"].includes(frame.composite),
        ) ||
      scrollBinding(animation) ||
      target
        .getAnimations()
        .some(
          (other) =>
            other !== animation &&
            other.effect?.getKeyframes().some((frame) => key in frame),
        )
    )
      return null;
    const values = declaredValues(node, "translate");
    if (
      !node.isConnected ||
      !values.length ||
      !values.every((value) => value.trim() === `var(${key})`)
    )
      return null;
    let reached = false;
    for (let at = node; at; at = up(at)) {
      if (at === target) {
        reached = true;
        break;
      }
      // An override, including an independent animation, breaks inherited source
      // ownership even when its numeric trajectory happens to match.
      if (
        declaredValues(at, key).length ||
        at
          .getAnimations()
          .some(
            (other) =>
              other !== animation &&
              other.effect?.getKeyframes().some((frame) => key in frame),
          )
      )
        return null;
    }
    if (
      !reached ||
      node
        .getAnimations()
        .some(
          (other) =>
            other !== animation && animationProperties(other).includes("translate"),
        )
    )
      return null;
    const style = getComputedStyle(node);
    if (style.getPropertyValue(key) !== getComputedStyle(target).getPropertyValue(key))
      return null;
    const value = animatedValue(node, style, "translate");
    const expected = animationTranslation(
      "translate",
      style.getPropertyValue(key).trim(),
    );
    const actual = animationTranslation("translate", value);
    if (
      !expected ||
      !actual ||
      expected.left !== actual.left ||
      expected.top !== actual.top
    )
      return null;
    if (returning && origins.get(animation)?.consumers?.get(node) !== value)
      return null;
    return { node, key, value, axes: translationAxes(node) };
  };
  const anchoredInset = (node, style, property, axis) => {
    const inline = node.style.getPropertyValue(property);
    if (inline && node.style.getPropertyPriority(property))
      return anchorInset(inline, axis);
    if (!style.positionAnchor.startsWith("--"))
      return inline ? anchorInset(inline, axis) : false;
    const candidates = declaredValues(node, property);
    if (candidates.every((value) => anchorInset(value, axis)))
      return candidates.length > 0;
    if (!candidates.some((value) => value.trim() === "revert-layer")) return false;
    // A rollback can expose a lower tier. Prove every declared alternative,
    // including normal rules under an important rollback, before allowing it.
    // With none left, an inset is auto: Typed OM preserves that keyword where
    // CSSOM's resolved style hides it as a used pixel position.
    const rules = declaredRules(node, property, false);
    const values = [...rules.normal, ...rules.important, inline].filter(
      (value) => value && value.trim() !== "revert-layer",
    );
    return (
      values.length > 0 &&
      values.every((value) => anchorInset(value, axis)) &&
      (node.computedStyleMap?.().get(property)?.toString() ?? "auto") !== "auto"
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
        (style.content !== '""' || paintsBox(style))
      );
    });
  // Whether anything that can change a node's reading has happened since the last
  // complete one (the header's "Unchanged frames"). Each source sets it in the same
  // task as the change it announces, so it is set before the next frame's reading.
  let unread = true;
  // Whether anything was announced since the last frame's reading, which tells a frame
  // where the page is still changing from one where it has come to rest.
  let fresh = true;
  // Whether a frame has left changes unread before the page presented.
  let deferring = false;
  const announce = () => {
    unread = fresh = true;
  };
  // Chrome animates native details' ::details-content without exposing that
  // transition through getAnimations(). Keep the closure through its final painted
  // frame: a loaded browser can paint the last size change after the nominal CSS
  // duration, and the layout-shift observer reports that paint later still.
  const nativeClosures = new Map();
  const durationMs = (value) =>
    Math.max(
      0,
      ...value.split(",").map((part) => {
        const time = part.trim();
        return (parseFloat(time) || 0) * (time.endsWith("ms") ? 1 : 1000);
      }),
    );
  const observeWrites = (records) => {
    if (!records.length) return;
    const at = nativePerformance.now();
    for (const record of records) {
      const node = record.target;
      if (
        record.type !== "attributes" ||
        record.attributeName !== "open" ||
        !(node instanceof HTMLDetailsElement)
      )
        continue;
      if (node.open) {
        nativeClosures.delete(node);
        continue;
      }
      const style = getComputedStyle(node, "::details-content");
      if (
        !style.transitionProperty
          .split(",")
          .some((name) => name.trim() === "block-size")
      )
        continue;
      const duration = durationMs(style.transitionDuration);
      if (duration) nativeClosures.set(node, { until: at + duration, settledAt: null });
    }
    announce();
  };
  const writes = new MutationObserver(observeWrites);
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
      listen(tree, type, announce, { capture: true, passive: true });
  };
  watchTree(document);
  for (const type of ["resize", "hashchange", "pageshow", "focus", "blur"])
    listen(window, type, announce, { capture: true, passive: true });
  for (const type of ["resize", "scroll"])
    window.visualViewport?.addEventListener(type, announce);
  document.fonts?.addEventListener("loadingdone", announce);
  // Emulated media changes style with no event but its query's.
  const presentationMedia = [
    "print",
    "(prefers-color-scheme: dark)",
    "(prefers-reduced-motion: reduce)",
    "(forced-colors: active)",
    "(prefers-contrast: more)",
  ].map((query) => matchMedia(query));
  for (const query of presentationMedia) query.addEventListener("change", announce);
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
  // A zero-sized native anchor independently exposes the compositor source pose
  // consumed by an anchored floating surface. Its own point stays at the source's
  // origin, so displacement of the measured holder cannot pick another camera.
  // Fixed, empty and hidden, it cannot reflow content, paint or receive focus.
  const cameras = new Map();
  const cameraNodes = new Set();
  const readCameras = (selections) => {
    for (const [owner, camera] of cameras)
      if (!selections.has(owner) || !owner.isConnected) {
        camera.remove();
        cameras.delete(owner);
        cameraNodes.delete(camera);
      }
    const readings = new Map();
    for (const [owner, selection] of selections) {
      if (!(selection.frame instanceof Element)) continue;
      const style = getComputedStyle(owner);
      if (
        !["fixed", "absolute"].includes(style.position) ||
        !getComputedStyle(selection.frame)
          .anchorName.split(",")
          .map((name) => name.trim())
          .includes(style.positionAnchor)
      )
        continue;
      let camera = cameras.get(owner);
      if (!camera) {
        camera = document.createElement("lf-shift-camera");
        camera.style.cssText =
          "all:initial;position:fixed;left:anchor(left);top:anchor(top);width:0;height:0;margin:0;padding:0;border:0;visibility:hidden;pointer-events:none";
        cameras.set(owner, camera);
        cameraNodes.add(camera);
      }
      if (camera.style.positionAnchor !== style.positionAnchor)
        camera.style.positionAnchor = style.positionAnchor;
      if (camera.parentElement !== owner.parentElement) owner.before(camera);
      readings.set(owner, camera.getBoundingClientRect());
    }
    return readings;
  };
  const everything = () => {
    const nodes = [...document.querySelectorAll("*")];
    // The HTML parser creates declarative roots without calling attachShadow.
    // Discover them in the same traversal that records their rendered ancestors.
    const discover = (node) => {
      if (node.shadowRoot && !roots.has(node.shadowRoot)) {
        roots.add(node.shadowRoot);
        watchTree(node.shadowRoot);
      }
    };
    nodes.forEach(discover);
    for (const root of roots)
      if (root.host.isConnected) {
        const children = [...root.querySelectorAll("*")];
        children.forEach(discover);
        nodes.push(...children);
      }
    const words = nodes.flatMap((node) =>
      [...node.childNodes].filter(
        (child) =>
          child.nodeType === Node.TEXT_NODE &&
          child.textContent.trim() &&
          !node.matches("script, style"),
      ),
    );
    return [...nodes.filter((node) => !cameraNodes.has(node)), ...words];
  };
  // Each frame keeps its node population; geometry and paint evidence keep changes
  // only. Later hiding, clipping, reparenting or removal cannot erase a sampled box.
  const frames = [];
  const placed = new WeakMap();
  const scrolled = new WeakMap();
  const animated = new WeakMap();
  const floating = new WeakMap();
  let floatingOwners = new Set();
  // An animated property's value as a translation reads it. The individual `translate`
  // keeps its percentages in its computed value, each of the target's border box (an
  // HTML element's transform reference box), so the reading resolves them to pixels.
  const animatedValue = (target, style, property) => {
    const value = style[property];
    if (
      property !== "translate" ||
      !value.includes("%") ||
      !(target instanceof HTMLElement)
    )
      return value;
    const edges = (a, b) =>
      ["padding", "border"].reduce(
        (sum, part) =>
          sum +
          parseFloat(style[`${part}${a}${part === "border" ? "Width" : ""}`]) +
          parseFloat(style[`${part}${b}${part === "border" ? "Width" : ""}`]),
        0,
      );
    const content = style.boxSizing === "content-box";
    const size = [
      parseFloat(style.width) + (content ? edges("Left", "Right") : 0),
      parseFloat(style.height) + (content ? edges("Top", "Bottom") : 0),
    ];
    return value
      .split(" ")
      .map((length, axis) =>
        length.endsWith("%") ? `${(parseFloat(length) / 100) * size[axis]}px` : length,
      )
      .join(" ");
  };
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
    // The individual property, which a surface's entrance often slides by: none, or
    // pixel lengths along x, y and z. Travel along z is not a pure translation.
    if (property === "translate") {
      if (value === "none") return { left: 0, top: 0 };
      const [x, y = "0px", z = "0px", ...rest] = value.split(" ");
      return !rest.length &&
        [x, y, z].every((length) => /^-?[\d.]+(?:e[-+]?\d+)?px$/.test(length)) &&
        parseFloat(z) === 0
        ? { left: parseFloat(x), top: parseFloat(y) }
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
  // Cleanup may remove a zero-valued translate binding: `none` and `0px`
  // are the same underlying endpoint, despite their different computed strings.
  const sameTranslation = (property, before, after) => {
    if (before === after) return true;
    if (before === undefined || after === undefined) return false;
    const first = animationTranslation(property, before);
    const last = animationTranslation(property, after);
    return (
      first !== null &&
      last !== null &&
      first.left === last.left &&
      first.top === last.top
    );
  };
  const translationAxes = (target) => {
    const parent = elementAxes(up(target));
    const zoom = Number(getComputedStyle(target).zoom);
    return {
      transform: elementAxes(target),
      layout: {
        x: { x: parent.x.x * zoom, y: parent.x.y * zoom },
        y: { x: parent.y.x * zoom, y: parent.y.y * zoom },
      },
    };
  };
  const scrollBinding = (animation) => {
    const timeline = animation.timeline;
    if (
      typeof window.ScrollTimeline !== "function" ||
      !(timeline instanceof ScrollTimeline) ||
      !(timeline.source instanceof Element)
    )
      return null;
    const source = timeline.source;
    const style = getComputedStyle(source);
    const vertical = !style.writingMode.startsWith("horizontal");
    const axis =
      timeline.axis === "block"
        ? vertical
          ? "x"
          : "y"
        : timeline.axis === "inline"
          ? vertical
            ? "y"
            : "x"
          : timeline.axis;
    // Typed CSS values have no enumerable value in JSON. Retain their unit and
    // value, including percent animation ranges and pixel view-timeline insets.
    const signature = JSON.stringify(
      {
        axis,
        writingMode: style.writingMode,
        direction: style.direction,
        axes: scrollAxes(source),
        width: source.clientWidth,
        height: source.clientHeight,
        scrollWidth: source.scrollWidth,
        scrollHeight: source.scrollHeight,
        start: timeline.startOffset,
        end: timeline.endOffset,
        inset: timeline.inset,
        timing: animation.effect.getTiming(),
        rangeStart: animation.rangeStart,
        rangeEnd: animation.rangeEnd,
        playbackRate: animation.playbackRate,
        startTime: animation.startTime,
      },
      (_, value) =>
        value instanceof CSSUnitValue
          ? { value: value.value, unit: value.unit }
          : value,
    );
    return {
      timeline,
      effect: animation.effect,
      target: animation.effect.target,
      source,
      subject: timeline.subject,
      axis,
      signature,
    };
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
      ["transform", "translate", "left", "top", "marginLeft", "marginTop"]
        .filter((property) => !competing.has(property))
        .map((property) => [property, animatedValue(target, style, property)]),
    );
  };
  const animate = Element.prototype.animate;
  Element.prototype.animate = function (...args) {
    announce();
    const values = underlying(this);
    const frames = Array.isArray(args[0]) ? args[0] : [args[0] ?? {}];
    const bindings = findConsumers(this, [...new Set(frames.flatMap(Object.keys))]);
    const consumers = consumerOrigins(bindings);
    const at = nativePerformance.now();
    const animation = animate.apply(this, args);
    beganAt.set(animation, { at });
    animationProperties(animation);
    inheritedConsumers.set(
      animation,
      translationBindings.get(animation) ? [] : bindings,
    );
    origins.set(animation, {
      ...Object.fromEntries(
        animationProperties(animation)
          .filter((property) => property in values)
          .map((property) => [property, values[property]]),
      ),
      consumers,
    });
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
      if (origin) origin.consumers = consumerOrigins(inheritedBindings(this));
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
      ...new Set([...allAnimations(), ...(ending?.effect?.target ? [ending] : [])]),
    ].filter((animation) => animation.effect?.target?.isConnected && moves(animation));
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
      const binding = translationBindings.get(animation);
      const values = Object.fromEntries(
        animationProperties(animation)
          .filter(
            (property) =>
              replace &&
              uses.get(effect.target)?.get(property) === 1 &&
              (property !== "translate" ||
                !binding ||
                effect.target.style.translate === binding ||
                returning) &&
              (!returning ||
                sameTranslation(
                  property,
                  origin?.[property],
                  animatedValue(effect.target, style, property),
                )),
          )
          .map((property) => [property, animatedValue(effect.target, style, property)]),
      );
      const readings = animated.get(animation) ?? [];
      readings.push({
        at,
        values,
        axes: translationAxes(effect.target),
        scroll: scrollBinding(animation),
        keyframes: effect.getKeyframes(),
        consumers: inheritedBindings(animation).map((binding) =>
          inheritedReading(animation, binding, returning),
        ),
      });
      pruneSamples(readings);
      animated.set(animation, readings);
    }
  };
  // A cancelled no-fill effect returns to its underlying style before the next
  // frame. Keep both sides of that native change while the effect still names its
  // target; getAnimations() no longer includes it after cancel().
  const cancel = Animation.prototype.cancel;
  Animation.prototype.cancel = function (...args) {
    const applied =
      this.effect?.target &&
      moves(this) &&
      this.effect.getComputedTiming().progress !== null;
    if (applied) readMotion(nativePerformance.now());
    const result = cancel.apply(this, args);
    if (applied) {
      readMotion(nativePerformance.now(), this);
      announce();
    }
    return result;
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
  // One finding for a reading that found unannounced changes: the innermost node that
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
    const named = node ? name(node) : null;
    report(JSON.stringify(["missed", named]), {
      code: "shift-watch-missed",
      node: named,
      changed,
      others: misses.length - 1,
    });
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
    const nativeCameras = readCameras(selections);
    readMotion(at);
    // A running animation changes poses on every frame, and the frame after it stops
    // or leaves the set settles the last of them. A scroll-driven one moves only as
    // its scroller scrolls or its layout changes, which announce themselves, so it
    // reads completely only on those frames, as the contents' window does in lf-toc.
    const animations = allAnimations();
    for (const [node, closure] of nativeClosures) {
      if (!node.isConnected) {
        nativeClosures.delete(node);
        continue;
      }
      if (
        closure.settledAt === null &&
        at >= closure.until &&
        parseFloat(getComputedStyle(node, "::details-content").blockSize) === 0
      )
        closure.settledAt = at;
    }
    const running =
      animations.some(
        ({ playState, timeline }) =>
          playState === "running" &&
          !(
            typeof window.ScrollTimeline === "function" &&
            timeline instanceof ScrollTimeline
          ),
      ) || [...nativeClosures.values()].some(({ settledAt }) => settledAt === null);
    observeWrites(writes.takeRecords());
    // A child frame reads completely on every frame, since its embedding page can
    // hide or move it without telling it; only a hidden tab announces itself here.
    const drawn = !document.hidden;
    const active =
      fresh ||
      drawn !== wasDrawn ||
      running ||
      wasRunning ||
      animations.length !== seenAnimations.length ||
      animations.some((animation, i) => animation !== seenAnimations[i]);
    if (frame) fresh = false;
    const announced = unread || window !== top || active;
    // Native anchoring follows its scroller one frame late, so the frame after the
    // one that reads an announced change reads completely too.
    const changing = announced || (frame && owed > 0);
    if (frame && owed > 0) owed--;
    if (announced) owed = frame ? 1 : 2;
    wasRunning = running;
    wasDrawn = drawn;
    seenAnimations = animations;
    // A page still changing before it presents leaves its changes unread for the
    // first frame where it rests ("Unpresented frames" above).
    const deferred = frame && active && unpresented();
    if (deferred) unread = deferring = true;
    const verifying = !deferred && !changing && frame && ++quiet % VERIFY === 0;
    if (deferred || (!changing && !verifying)) {
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
    unread = deferring = false;
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
    const entry = frame
      ? {
          at,
          start: time,
          nodes,
          motion: animations.filter(
            (animation) => animated.get(animation)?.at(-1)?.scroll,
          ),
          complete: true,
        }
      : null;
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
      let labelOwner = null;
      if (range)
        for (
          let ancestor = element;
          ancestor instanceof Element;
          ancestor = up(ancestor)
        )
          if (ancestor.matches(pressControls)) {
            labelOwner = ancestor;
            break;
          }
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
      // Boxless elements retain computed CSS but cannot own clipping,
      // scrollports, or positioned geometry for their descendants.
      const hasBox = !range && node.getClientRects().length > 0;
      const position = hasBox ? style.position : "static";
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
      const selection = selections.get(node);
      const nativeOrigin =
        selection?.frame && anchorOf(node, style, anchors) === selection.frame
          ? (nativeCameras.get(node) ?? {})
          : {};
      const paint = {
        parent: up(node),
        domParent: node.parentNode,
        next: range ? null : node.nextElementSibling,
        display: style.display,
        float: style.float,
        writingMode: style.writingMode,
        anchor: range ? null : anchorOf(node, style, anchors),
        anchorX:
          !range &&
          ["fixed", "absolute"].includes(position) &&
          ["left", "right"].some((side) => anchoredInset(node, style, side, "left")),
        anchorY:
          !range &&
          ["fixed", "absolute"].includes(position) &&
          ["top", "bottom"].some((side) => anchoredInset(node, style, side, "top")),
        nativeLeft: nativeOrigin.left,
        nativeTop: nativeOrigin.top,
        insetX: range ? null : `${node.style.left}|${node.style.right}`,
        insetY: range ? null : `${node.style.top}|${node.style.bottom}`,
        position,
        stickyTop: position === "sticky" ? pixels(style.top) : null,
        stickyBottom: position === "sticky" ? pixels(style.bottom) : null,
        scrollXx: axes?.x.x ?? 1,
        scrollXy: axes?.x.y ?? 0,
        scrollYx: axes?.y.x ?? 0,
        scrollYy: axes?.y.y ?? 1,
        block: ["fixed", "absolute"].includes(position) ? node.offsetParent : null,
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
        clipsX: hasBox && clipping.x,
        clipsY: hasBox && clipping.y,
        scrollportY: hasBox && ["auto", "scroll", "hidden"].includes(style.overflowY),
        paddingTop: range ? null : pixels(style.paddingTop),
        paddingBottom: range ? null : pixels(style.paddingBottom),
        reflow: range ? null : node.getAttribute("data-lf-reflow"),
        appendTail: !range && node.hasAttribute("data-lf-append-tail"),
        rises: !range && node.hasAttribute("data-lf-rises"),
        appendChildren,
        runtime: !range && node.matches(".lf-chrome, [data-lf-runtime]"),
        control: !range && node.matches(interactive),
        reading: Boolean(range) || readingMedia(element),
        labelOwner,
        labelText: labelOwner?.textContent ?? null,
        shown,
      };
      const words = range ? node.textContent : null;
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
        last.words === words &&
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
        nativeOrigin,
        rect,
        fragments,
        words,
        paint,
      });
      pruneSamples(seen);
      placed.set(node, seen);
    }
    if (entry) entry.written = written;
    // A page that wrote while it was read, as a reading that patches the DOM API
    // does, announced its own change.
    const pending = writes.takeRecords();
    if (pending.length) observeWrites(pending);
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
  const inputRenderings = new WeakMap();
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
  const begin = (start, typing = null, own = new Set(), event = null) => {
    // A newer input ends the open one's aim, after a last look at where it stands.
    if (open) judgeAim(open);
    end();
    open = {
      start,
      first: true,
      through: Infinity,
      own,
      told: false,
      last: false,
      typing,
      event,
    };
    renderings.push(open);
    if (event) inputRenderings.set(event, open);
  };
  // The renderings preparations' landings opened, each running until the loop settles
  // as an input's own does. The canonical callback source identifies the input that
  // began each preparation; sharing a widget or overlapping its rendering is no cause.
  const landing = new Set();
  const preparing = new WeakMap();
  const prepared = (phase, preparation) => {
    if (phase === "begin") {
      const source = window.lfInputWork.current();
      const owner = source && inputRenderings.get(source.event);
      if (owner) preparing.set(preparation, owner);
      return;
    }
    const owner = preparing.get(preparation);
    if (!owner) return;
    preparing.delete(preparation);
    if (phase === "cancel") return;
    const rendering = {
      start: nativePerformance.now(),
      first: true,
      through: Infinity,
      own: owner.own,
      told: false,
      last: false,
      typing: owner.typing,
      event: owner.event,
    };
    landing.add(rendering);
    renderings.push(rendering);
  };
  // The runtime publishes its observer on its entry script after this script runs.
  Object.defineProperty(HTMLScriptElement.prototype, "lfObserveWidgetPreparations", {
    configurable: true,
    set(observe) {
      Object.defineProperty(this, "lfObserveWidgetPreparations", {
        value: observe,
        writable: true,
        enumerable: true,
        configurable: true,
      });
      observe(prepared);
    },
  });
  // Shifts whose frame has no reading after it yet.
  const waiting = [];
  const tick = (time) => {
    presentationChanged();
    const at = read(time);
    if (open) {
      judgeAim(open);
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
    for (const rendering of landing) {
      if (!rendering.told)
        for (const animation of begun(rendering.start)) rendering.own.add(animation);
      if (rendering.last) landing.delete(rendering);
      else rendering.last = settled();
    }
    // A gesture owns its counted rendering until canonical completion. News seals
    // that credit; continuing motion retains its separate ownership below. A newer
    // input still leaves the prior gesture its first two frame readings.
    for (const rendering of renderings) {
      if (
        !rendering.first &&
        (rendering.through === Infinity ||
          ((rendering === open || landing.has(rendering)) && !rendering.told))
      )
        rendering.through = at;
      rendering.first = false;
    }
    const motion = frames.at(-1).motion;
    for (const rendering of renderings)
      for (const animation of rendering.own)
        if (activeMotion(animation)) motion.push(animation);
    audit();
    judge(waiting.splice(0));
    nativeFrame(tick);
  };
  nativeFrame(tick);
  window.lfInputWork.subscribeEdits(({ node: field, event }) => {
    const holding = [];
    for (let at = field; at instanceof Element; at = up(at)) holding.push(at);
    const start = nativePerformance.now();
    const at = read(start, false);
    begin(
      start,
      {
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
          .filter((animation) => activeMotion(animation) && moves(animation)),
        until: Infinity,
      },
      new Set(),
      event,
    );
  });
  // Resizing and media preferences change the browser's presentation. Their new
  // state is the fact: layout can precede the native event, as when an embedding page
  // resizes a frame and the frame lays out and paints before its resize event, so each
  // frame checks it before reading, and so does the observer before a shift record
  // delivered meanwhile. The preceding pose seals typing; taking a new pose here would
  // attribute the presentation change to the key.
  const presentationState = () => [
    innerWidth,
    innerHeight,
    ...presentationMedia.map((query) => query.matches),
  ];
  let presentation = presentationState();
  const presentationChanged = () => {
    const next = presentationState();
    if (next.every((value, index) => value === presentation[index])) return;
    presentation = next;
    // Layout can precede the native event, so this observation also makes the
    // next reading complete, including clipping changes with no shift record.
    announce();
    // What the new presentation moves is its own, not the open gesture's.
    if (open) open.aim = null;
    const before = frames.at(-1)?.at ?? nativePerformance.now();
    if (open?.typing?.until === Infinity) open.typing.until = before;
    begin(nativePerformance.now());
  };
  listen(window, "resize", presentationChanged);
  for (const query of presentationMedia) listen(query, "change", presentationChanged);
  // When the page adopted each server reading.
  new MutationObserver(() => {
    unwatch();
    if (open) open.told = true;
    for (const rendering of landing) rendering.told = true;
  }).observe(document, { subtree: true, attributeFilter: ["data-lf-reading"] });
  // A gesture's aim: the control it was made on, which a scroll during the gesture's
  // rendering may not carry on screen (Scrolls a gesture makes, above). A press aims
  // at the control under the pointer, a key at whatever holds focus. A link's
  // activation takes the user somewhere by the platform's own meaning, whether the
  // browser follows it or the page's script travels in its place, and a key the
  // page leaves to the browser, as Tab, Space or an arrow, does what the platform does
  // with it; neither aims. Wheels and drags move the page by the user's own hand.
  const aimOf = (event) => {
    let node = null;
    if (event.type === "keydown") {
      // A key pressed in another document aims at nothing here.
      if (event.target.ownerDocument !== document) return null;
      node = document.activeElement;
      while (node?.shadowRoot?.activeElement) node = node.shadowRoot.activeElement;
      if (node === document.body || node === document.documentElement) node = null;
    } else if (["pointerdown", "pointerup", "click"].includes(event.type)) {
      const path = event.composedPath();
      if (path.some((at) => at instanceof Element && at.matches("a[href], area[href]")))
        return null;
      node = path.find((at) => at instanceof Element && at.matches(interactive));
    }
    if (!node || node.ownerDocument !== document) return null;
    const pose = aimPose(node);
    // Focus can stand on a control scrolled off screen, which nobody aims at.
    const { rect } = pose ?? {};
    if (
      !rect ||
      rect.bottom <= 0 ||
      rect.right <= 0 ||
      rect.top >= innerHeight ||
      rect.left >= innerWidth
    )
      return null;
    return { node, event, ...pose };
  };
  // Where the aim stands on screen, and the scroll offset of each box whose scroll
  // carries it: its rendered ancestors up to the first fixed box among it and them,
  // with what each that scrolls shows (`shownBy`). Read fresh, not from the ledger,
  // whose last reading can predate a script's scroll that the input follows within
  // the frame.
  const aimPose = (node) => {
    if (!node.isConnected || !node.checkVisibility()) return null;
    const rect = node.getBoundingClientRect();
    if (!rect.width && !rect.height) return null;
    const scrolls = new Map();
    for (let child = node; ;) {
      if (getComputedStyle(child).position === "fixed") break;
      const parent = up(child);
      if (!(parent instanceof Element)) break;
      const scrolling =
        parent.scrollWidth > parent.clientWidth ||
        parent.scrollHeight > parent.clientHeight;
      scrolls.set(parent, {
        left: parent.scrollLeft,
        top: parent.scrollTop,
        shown: scrolling ? shownBy(parent) : null,
      });
      child = parent;
    }
    return { rect, scrolls };
  };
  // Where a scroller shows what it holds whole: its scrollport less its scroll-padding,
  // the region the browser's own reveals bring a target into, clear of what the
  // scroller declares stands over its edges (a stuck header, a strip's edge press).
  const shownBy = (box) => {
    const root = box === document.scrollingElement;
    const rect = root ? { left: 0, top: 0 } : box.getBoundingClientRect();
    const style = getComputedStyle(box);
    const inset = (side) => pixels(style[`scrollPadding${side}`]) ?? 0;
    const left = rect.left + (root ? 0 : box.clientLeft);
    const top = rect.top + (root ? 0 : box.clientTop);
    return {
      left: left + inset("Left"),
      top: top + inset("Top"),
      right: left + box.clientWidth - inset("Right"),
      bottom: top + box.clientHeight - inset("Bottom"),
    };
  };
  // A control as a reveal brings it into view: out to its scroll-margin, its ring's room.
  const ringed = (node, rect) => {
    const style = getComputedStyle(node);
    const margin = (side) => pixels(style[`scrollMargin${side}`]) ?? 0;
    return {
      left: rect.left - margin("Left"),
      top: rect.top - margin("Top"),
      right: rect.right + margin("Right"),
      bottom: rect.bottom + margin("Bottom"),
    };
  };
  const whole = (rect, shown, start, end) =>
    rect[start] > shown[start] - 1 && rect[end] < shown[end] + 1;
  // A scroll carried the aim on screen where both its edges moved one way on an axis
  // and the scroll moved it that way too. A scroll that holds it still, or takes back
  // part of what the gesture's own layout moved, carries it nowhere; layout motion
  // stays the gesture's own (Scope). Nor does a box's scroll that brings the aim whole
  // into what that box shows from partly past it, by no more than the part it hid, as
  // the browser's own focus does: the user pressed the part they could see, and the
  // reveal shows them the rest.
  const judgeAim = (rendering) => {
    const aim = rendering.aim;
    if (!aim?.scrolled || aim.foreign) return;
    if (
      aim.event.type === "keydown" &&
      (!aim.event.defaultPrevented ||
        (caretKeys.includes(aim.event.key) &&
          document.documentElement.lfInputs?.typesText(aim.node)))
    ) {
      rendering.aim = null;
      return;
    }
    const now = aimPose(aim.node);
    if (!now) return;
    const scrolled = { left: 0, top: 0 };
    let carriedBy = false;
    const [from, to] = [aim.rect, now.rect].map((rect) => ringed(aim.node, rect));
    for (const [axis, far] of [
      ["left", "right"],
      ["top", "bottom"],
    ]) {
      for (const [box, offset] of now.scrolls) {
        const was = aim.scrolls.get(box);
        if (!was || !aim.scrolled.has(box)) continue;
        const past =
          was.shown &&
          Math.max(was.shown[axis] - from[axis], from[far] - was.shown[far]);
        const reveals =
          past >= 1 &&
          Math.abs(offset[axis] - was[axis]) < past + 1 &&
          offset.shown &&
          whole(to, offset.shown, axis, far);
        if (!reveals) scrolled[axis] -= offset[axis] - was[axis];
      }
      if (
        carried(aim.rect, now.rect, axis, far) &&
        Math.abs(scrolled[axis]) >= 1 &&
        Math.sign(scrolled[axis]) === Math.sign(now.rect[axis] - aim.rect[axis])
      )
        carriedBy = true;
    }
    if (!carriedBy) return;
    rendering.aim = null;
    const input =
      aim.event.type === "keydown"
        ? `${aim.event.type} ${aim.event.key}`
        : aim.event.type;
    report(JSON.stringify(["scrolled", name(aim.node)]), {
      code: "gesture-scrolled",
      node: name(aim.node),
      input,
      by: by(aim.rect, now.rect),
      beside: [],
      evidence: {
        kind: "gesture",
        node: name(aim.node),
        input,
        before: box(aim.rect),
        after: box(now.rect),
        scrolled: [Math.round(scrolled.left), Math.round(scrolled.top)],
      },
    });
  };
  // Whose scroll it was (Scrolls a gesture makes, above): the aim is judged once the
  // gesture's own work has called a scrolling API, and never once other work has
  // during its rendering. A scroll the call starts, a smooth one too, is the gesture's
  // through the rendering, on the boxes the call scrolls: the one it names, or for a
  // reveal or focus every box holding its target.
  const scrollCalled = (target, holders = false) => {
    const aim = open?.aim;
    if (!aim) return;
    const source = window.lfInputWork.current();
    const owner = source && inputRenderings.get(source.event);
    if (!owner || (owner !== open && owner.own !== open.own)) {
      aim.foreign = true;
      return;
    }
    aim.scrolled ??= new Set();
    if (target === window) aim.scrolled.add(document.scrollingElement);
    else if (!holders) aim.scrolled.add(target);
    else
      for (let box = up(target); box instanceof Element; box = up(box))
        aim.scrolled.add(box);
  };
  for (const [owner, names, holders] of [
    [Element.prototype, ["scroll", "scrollTo", "scrollBy"], false],
    [Element.prototype, ["scrollIntoView", "scrollIntoViewIfNeeded"], true],
    [window, ["scroll", "scrollTo", "scrollBy"], false],
    [HTMLElement.prototype, ["focus"], true],
    [SVGElement.prototype, ["focus"], true],
  ])
    for (const key of names) {
      const call = owner[key];
      if (typeof call !== "function") continue;
      owner[key] = function (...args) {
        if (key !== "focus" || !args[0]?.preventScroll) scrollCalled(this, holders);
        return call.apply(this, args);
      };
    }
  for (const key of ["scrollTop", "scrollLeft"]) {
    const offset = Object.getOwnPropertyDescriptor(Element.prototype, key);
    Object.defineProperty(Element.prototype, key, {
      ...offset,
      set(value) {
        scrollCalled(this);
        offset.set.call(this, value);
      },
    });
  }
  // A command that takes the user somewhere declares it on its register row
  // (`travels`, keyboard/bindings.js), which the dispatcher announces as it runs it.
  listen(document, "lf-command-invoked", ({ detail }) => {
    if (detail?.travels && open) open.aim = null;
  });
  // So does a gesture that adds a history entry, as a followed link or a root tab
  // set's switch does; renaming the entry the user is on (`replaceState`) takes them
  // nowhere. Back or Forward is the user's own gesture, made in the browser's chrome,
  // which no input event here carries, so it opens a rendering as hearing an input does.
  if (window.navigation)
    listen(window.navigation, "navigate", ({ navigationType }) => {
      if (navigationType === "traverse") begin(nativePerformance.now());
      else if (navigationType === "push" && open) open.aim = null;
    });
  listen(
    window,
    "pointercancel",
    (event) => {
      if (open?.aim?.event.pointerId === event.pointerId) open.aim = null;
    },
    true,
  );
  // Press, drag, release and native activation are phases of one pointer gesture.
  // Each phase keeps its own paint boundary while sharing the effects that press
  // began. A later press starts fresh; native timeline reassignment cannot adopt
  // an unrelated older effect into it.
  const presses = new Map();
  const heard = (event) => {
    if (!event.isTrusted || (event.type === "pointermove" && !event.buttons)) return;
    if (event.type === "pointerdown") presses.set(event.pointerId, new Set());
    begin(
      nativePerformance.now(),
      null,
      presses.get(event.pointerId) ?? new Set(),
      event,
    );
    open.aim = aimOf(event);
    if (event.type === "click") presses.delete(event.pointerId);
  };
  // An input's credits look back to the poses it began from, so where frames left
  // changes unread, read them before any handler of the page's can move anything.
  for (const type of [
    "keydown",
    "pointerdown",
    "pointermove",
    "pointerup",
    "click",
    "wheel",
  ])
    listen(
      window,
      type,
      (event) => {
        if (deferring && event.isTrusted && (type !== "pointermove" || event.buttons))
          read(nativePerformance.now(), false);
      },
      true,
    );
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
      listen(held, type, heard, true);
    listen(held, "pointercancel", (event) => presses.delete(event.pointerId), true);
    if (view === view.parent) break;
  }
  // An embedding page this document cannot read, as an opaque sample's host is, sends
  // its input here only as work its port carries under that input's source, which
  // input_work_watch.js marks `carried`. The first such work opens the input's
  // rendering here, as hearing the input would have.
  window.lfInputWork.subscribe((source) => {
    if (source?.carried && !inputRenderings.has(source.event))
      begin(nativePerformance.now(), null, new Set(), source.event);
  });
  // Each finding goes to the fixture as a record (`leaf/findings.py` words it),
  // once per `key`, with every node in it named.
  const reported = new Set();
  const report = (key, finding) => {
    if (reported.has(key)) return;
    reported.add(key);
    window.__leafWatchFinding(
      JSON.parse(
        JSON.stringify(finding, (_, value) =>
          value instanceof Node ? name(value) : value,
        ),
      ),
    );
  };
  const box = ({ left, top, width, height }) => ({
    left: Math.round(left),
    top: Math.round(top),
    width: Math.round(width),
    height: Math.round(height),
  });
  const by = (from, to) => [
    Math.round(to.left - from.left),
    Math.round(to.top - from.top),
  ];
  const beside = (sources, node) =>
    sources.filter((source) => source.node !== node).map((source) => name(source.node));
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
  listen(document, "lf-reading-continuity", ({ detail }) => {
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
  const unpresented = () =>
    presented === null &&
    renderings.length === 0 &&
    (document.activeElement ?? document.body) === document.body &&
    document.querySelector("script[data-lf-entry]") !== null;
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
  // followers in the same stationary runtime scrollport or floating container may
  // be carried by it. A container sized to what it holds grows at its foot with
  // that growth, keeping
  // every other edge, and counts as stationary.
  //
  // A scrollport that declares it stands on its foot (`data-lf-rises`), as the floating
  // panel's thread view stands on its row, instead rises at its head as it grows with
  // that growth, by no more than it, keeping its other edges. Its holdings are then
  // read from its head, which carries them all up by its rise, and so does every box
  // standing on its foot with it (its stand): what stands in that stand above the
  // scrollport, such as the view's name, rises with it by the same distance and no
  // more. This is the one place news may carry what is read without a gesture
  // (`browser/AGENTS.md`, "Stability": an answer the user waits for grows the
  // panel's thread view).
  const appendGrowth = (around) => {
    if (around.length !== 3) return [];
    const first = around[0].at,
      last = around[2].at;
    // How far a standing scrollport's head has risen by `at`, which its holdings'
    // layout coordinates are read net of.
    let lift = () => 0;
    const read = (node, at, screen = false) => {
      const rect = screen ? boxAt(node, at) : layoutAt(node, at);
      if (!rect || screen) return rect;
      const by = lift(at);
      return { ...rect, top: rect.top - by, bottom: rect.bottom - by };
    };
    const stable = (node, screen = false) => {
      const rects = around.map(({ at }) => read(node, at, screen));
      return rects.every(Boolean) && rects.every((rect) => !moved(rects[0], rect));
    };
    // Whether `node` keeps every edge but its foot, which grows by no more than `by`.
    const footGrowth = (node, by, screen = false) => {
      const rects = around.map(({ at }) => read(node, at, screen));
      return (
        rects.every(Boolean) &&
        rects.every(
          (rect) =>
            ["left", "right", "top"].every(
              (edge) => Math.abs(rect[edge] - rects[0][edge]) < 1,
            ) &&
            rect.bottom - rects[0].bottom > -1 &&
            rect.bottom - rects[0].bottom < by + 1,
        )
      );
    };
    // Whether `node` keeps every edge but its head, which rises; how far, or 0.
    const headRise = (node) => {
      const rects = around.map(({ at }) => boxAt(node, at));
      if (!rects.every(Boolean)) return 0;
      const rise = rects[0].top - rects[2].top;
      return rise >= 1 &&
        rects.every(
          (rect) =>
            ["left", "right", "bottom"].every(
              (edge) => Math.abs(rect[edge] - rects[0][edge]) < 1,
            ) &&
            rects[0].top - rect.top > -1 &&
            rects[0].top - rect.top < rise + 1,
        )
        ? rise
        : 0;
    };
    return around[0].nodes.flatMap((source) => {
      lift = () => 0;
      const readings = around.map(({ at }) => paintAt(source, at));
      if (!readings.every((paint) => paint?.reflow === "append")) return [];
      // A floating container owns its following controls even when it clips
      // without scrolling, or temporarily exposes its contents during motion.
      const containsAppend = (owner, at) => {
        const paint = paintAt(owner, at);
        return paint?.scrollportY || ["fixed", "absolute"].includes(paint?.position);
      };
      const port = ancestryAt(source, first).find(
        (owner) => owner !== source && containsAppend(owner, first),
      );
      const rise =
        port && around.every(({ at }) => paintAt(port, at)?.rises) ? headRise(port) : 0;
      if (rise) {
        const head = boxAt(port, first).top;
        lift = (at) => boxAt(port, at).top - head;
      }
      // Hidden checkpoints may disappear when their visible tail becomes an answer.
      // Only children with a box contribute to the prefix whose geometry we protect.
      const children = readings.map((paint, index) =>
        paint.appendChildren.filter((child) => {
          const box = read(child, around[index].at);
          return box && box.bottom - box.top >= 0.5;
        }),
      );
      const before = children[0],
        after = children[2];
      const prior = read(source, first),
        next = read(source, last);
      if (!prior || !next || next.bottom - prior.bottom < 1) return [];
      const grown = next.bottom - prior.bottom;
      // The end grows: children join after the old ones, which keep their boxes, or,
      // where none joins, the last old one grows at its foot where it declares itself
      // the region's growing tail (`data-lf-append-tail`), as a thread's working
      // message does, taking a longer step, and a streaming reply, taking more words.
      // A tail may also give way to what it stood for, as the working message does to
      // the answer: it leaves, the others keep their boxes, and what joins stands
      // from where it stood.
      const tail = before.at(-1);
      const tailBox = tail && read(tail, first);
      const replaced =
        Boolean(tailBox) &&
        paintAt(tail, first)?.appendTail &&
        !after.includes(tail) &&
        after.length >= before.length &&
        before
          .slice(0, -1)
          .every(
            (child, i) =>
              children.every((nodes) => nodes[i] === child) && stable(child),
          ) &&
        after.slice(before.length - 1).every((child) => {
          const box = read(child, last);
          return box && box.top >= tailBox.top - 1;
        });
      if (
        !before.length ||
        (!replaced &&
          (after.length < before.length ||
            !before.every(
              (child, i) =>
                children.every((nodes) => nodes[i] === child) &&
                (stable(child) ||
                  (after.length === before.length &&
                    i === before.length - 1 &&
                    // Read before the growth: a streaming reply that completes drops
                    // the mark in the render that adds its last words.
                    paintAt(child, first)?.appendTail &&
                    footGrowth(child, grown) &&
                    // The tail's own growth is the region's whole growth.
                    Math.abs(
                      read(child, last).bottom - read(child, first).bottom - grown,
                    ) < 1)),
            ) ||
            // Where none joins, the growth is the tail's: the region's own box growing
            // around unchanged children is no arrival.
            (after.length === before.length && stable(before.at(-1))))) ||
        !footGrowth(source, grown)
      )
        return [];
      if (
        !port ||
        port === document.scrollingElement ||
        !(
          stable(port, true) ||
          footGrowth(port, grown, true) ||
          (rise && rise < grown + 1)
        ) ||
        !around.every(
          ({ at }) =>
            ancestryAt(source, at).includes(port) &&
            containsAppend(port, at) &&
            ancestryAt(port, at).some((owner) => paintAt(owner, at)?.runtime) &&
            ancestryAt(source, at)
              .slice(1, ancestryAt(source, at).indexOf(port) + 1)
              .every((owner) => !paintAt(owner, at)?.reflow),
        )
      )
        return [];
      // The boxes standing on their foot with a rising port, each risen as far.
      let stand = port;
      if (rise)
        for (const owner of ancestryAt(port, first).slice(1)) {
          if (Math.abs(headRise(owner) - rise) >= 1) break;
          stand = owner;
        }
      if (
        rise &&
        !ancestryAt(stand, first).some((owner) => paintAt(owner, first)?.runtime)
      )
        return [];
      return [
        {
          source,
          port,
          bottom: prior.bottom,
          by: grown,
          rise,
          stand,
          head: boxAt(port, first).top,
        },
      ];
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
    // A standing port's rise carries all it holds, and what stands above it in its
    // stand.
    const rise = growth
      .filter(
        ({ port, stand, head }) =>
          ancestry.every((parents) => parents.includes(port)) ||
          (ancestry.every((parents) => parents.includes(stand)) &&
            boxAt(node, first).bottom <= head + 1),
      )
      .reduce((sum, each) => sum + each.rise, 0);
    if (!by && !rise) return false;
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
    // cannot excuse an extra move or repacking by one of its descendants. A text's
    // words may change as it is carried, as a message's state does, so its fragment's
    // end is its own; where it starts is not.
    const priorBox = boxAt(node, first),
      nextBox = boxAt(node, last);
    const edges =
      node.nodeType === Node.TEXT_NODE
        ? ["left", "top", "bottom"]
        : ["left", "right", "top", "bottom"];
    return edges.every((edge) => {
      const axis = edge === "left" || edge === "right" ? "left" : "top";
      const prior = previousRect[edge] - priorBox[axis] + before[axis];
      const next = currentRect[edge] - nextBox[axis] + after[axis];
      return Math.abs(next - prior - (axis === "top" ? by - rise : 0)) < 1;
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
  const credit = (motion, branch, owner, axis, amount, inputs) => {
    motion[axis] += amount;
    motion.terms.push({ branch, owner, axis, amount, inputs });
  };
  const nativeScrollMotion = (node, from, to) => {
    const element = node.nodeType === Node.TEXT_NODE ? up(node) : node;
    const sticky = ancestryAt(element, to).find(
      (owner) => paintAt(owner, to)?.position === "sticky",
    );
    const motion = { left: 0, top: 0, terms: [] };
    if (!sticky) return motion;
    const before = boxAt(sticky, from),
      after = boxAt(sticky, to);
    if (!before || !after) return motion;
    for (const axis of ["left", "top"]) {
      const ancestors = ancestryAt(sticky, to);
      const fixed = ancestors.findIndex(
        (owner) =>
          paintAt(owner, from)?.position === "fixed" ||
          paintAt(owner, to)?.position === "fixed",
      );
      // A sticky header inside a floating surface is carried by that surface,
      // not by the document scroll outside its fixed containing block.
      const carrying = fixed < 0 ? ancestors : ancestors.slice(0, fixed + 1);
      const sources = carrying.flatMap((owner) => {
        const prior = scrollAt(owner, from),
          next = scrollAt(owner, to);
        return prior && next
          ? [
              {
                source: owner,
                before: prior,
                after: next,
                viewport: viewportScroll(owner, to, {
                  left: next.left - prior.left,
                  top: next.top - prior.top,
                }),
              },
            ]
          : [];
      });
      const scroll = sources.reduce((sum, source) => sum + source.viewport[axis], 0);
      const shifted = after[axis] - before[axis];
      // Scroll carries the sticky owner on that axis, through at most its native
      // scroll delta. Descendants retain their local position relative to it.
      if (
        scroll &&
        shifted >= Math.min(0, -scroll) - 1 &&
        shifted <= Math.max(0, -scroll) + 1
      )
        credit(motion, "sticky_scroll", sticky, axis, shifted, {
          before,
          after,
          scroll,
          sources,
          fixed_boundary: fixed < 0 ? null : ancestors[fixed],
        });
    }
    return motion;
  };
  const writtenPoint = (selection, axis) =>
    selection.point[axis] -
    (selection.edges[axis] === axis
      ? 0
      : selection.size[axis === "left" ? "width" : "height"]);
  const scrollMotion = (node, from, to, animations = []) => {
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
      if (sameAttachment && was.frame && was.frame === now.frame) {
        const before = readingAt(owner, from)?.nativeOrigin;
        const after = readingAt(owner, to)?.nativeOrigin;
        const beforeLayout = layoutAt(was.frame, from);
        const afterLayout = layoutAt(now.frame, to);
        for (const axis of ["left", "top"]) {
          if (
            !Number.isFinite(before?.[axis]) ||
            !Number.isFinite(after?.[axis]) ||
            !beforeLayout ||
            !afterLayout ||
            Math.abs(beforeLayout[axis] - afterLayout[axis]) >= 1
          )
            continue;
          // An attachment limiter can release or constrain the same page-plane
          // surface as its target enters the viewport. Its declared world point
          // must still follow within the exact native source travel it consumed.
          const travel = after[axis] - before[axis];
          const placed = writtenPoint(now, axis) - writtenPoint(was, axis) + travel;
          if (placed >= Math.min(0, travel) - 1 && placed <= Math.max(0, travel) + 1) {
            credit(motion, "native_camera", owner, axis, placed, {
              before,
              after,
              before_layout: beforeLayout,
              after_layout: afterLayout,
              before_selection: was,
              after_selection: now,
              crosses_fixed: crossesFixed,
              travel,
              placed,
            });
            anchored[axis] = true;
          }
        }
      }
      if (sameAttachment && was.plane !== now.plane) {
        // A selection's point is measured from its frame's box: the subject anchor's
        // in the page's plane, the holding region's in a region's, the window's in
        // the window's.
        const origin = (selection, time) => {
          if (!selection.frame) return { left: 0, top: 0 };
          const source = boxAt(selection.frame, time);
          const retained = readingAt(owner, time);
          return (
            source && {
              left: retained?.nativeOrigin?.left ?? source.left,
              top: retained?.nativeOrigin?.top ?? source.top,
              camera: retained?.nativeOrigin ?? null,
              frame: source,
            }
          );
        };
        const before = origin(was, from),
          after = origin(now, to);
        if (before && after) {
          for (const axis of ["left", "top"]) {
            if (anchored[axis]) continue;
            const predicted = (selection, frame) =>
              writtenPoint(selection, axis) + frame[axis];
            const beforePoint = predicted(was, before),
              afterPoint = predicted(now, after);
            credit(motion, "floating_plane", owner, axis, afterPoint - beforePoint, {
              before: was,
              after: now,
              before_origin: before,
              after_origin: after,
              crosses_fixed: crossesFixed,
              same_attachment: sameAttachment,
              before_point: beforePoint,
              after_point: afterPoint,
            });
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
      // An anchored surface follows its source's owned native translation too.
      // Effects on a shared ancestor already carry the surface itself, so only the
      // source's independent effects belong to this placement credit.
      const owners = ancestryAt(owner, to);
      const translated = animationMotion(
        anchor,
        start,
        to,
        animations.filter((animation) => !owners.includes(animation.effect.target)),
      );
      for (const [axis, held] of [
        ["left", "anchorX"],
        ["top", "anchorY"],
      ]) {
        if (!prior[held] || !next[held] || anchored[axis]) continue;
        anchored[axis] = true;
        const layoutStable =
          Math.abs(afterLayout[axis] - beforeLayout[axis] - translated[axis]) < 1;
        credit(
          motion,
          "native_anchor",
          owner,
          axis,
          layoutStable ? after[axis] - before[axis] : carried[axis] + translated[axis],
          {
            anchor,
            pose_at: start,
            before,
            after,
            before_layout: beforeLayout,
            after_layout: afterLayout,
            layout_stable: layoutStable,
            sticky_terms: carried.terms,
            animation_terms: translated.terms,
          },
        );
      }
    }
    return motion;
  };
  // Only an unchanged trajectory can explain native source travel. Replacing all
  // translation keyframes by the same offset changes its placement origin, not
  // that trajectory; every other keyframe field must retain its meaning.
  const translationRebase = (property, before, after) => {
    if (before.length !== after.length || !before.length) return null;
    let delta = null;
    for (const [i, prior] of before.entries()) {
      const next = after[i];
      const metadata = (frame) =>
        JSON.stringify(
          Object.fromEntries(Object.entries(frame).filter(([key]) => key !== property)),
        );
      if (metadata(prior) !== metadata(next)) return null;
      if (!(property in prior) || !(property in next)) return null;
      const was = animationTranslation(property, prior[property]);
      const now = animationTranslation(property, next[property]);
      if (!was || !now) return null;
      const by = { left: now.left - was.left, top: now.top - was.top };
      if (
        delta &&
        (Math.abs(delta.left - by.left) > 0.01 || Math.abs(delta.top - by.top) > 0.01)
      )
        return null;
      delta = by;
    }
    return delta;
  };
  const viewportTranslation = (property, before, after, by) => {
    // Animated transforms translate in their target's local basis. The individual
    // `translate` applies outside the target's own transform, rotate and scale, so
    // like physical insets and margins it translates in its parent's basis with its
    // own CSS zoom. Every effect uses this same viewport conversion, and a changed
    // basis cannot explain translation with the earlier coordinate system.
    const key = property === "transform" ? "transform" : "layout";
    const axes = before.axes[key];
    if (JSON.stringify(axes) !== JSON.stringify(after.axes[key])) return null;
    return {
      left: by.left * axes.x.x + by.top * axes.y.x,
      top: by.left * axes.x.y + by.top * axes.y.y,
    };
  };
  const scrollEffectMotion = (property, before, after, from, to, by) => {
    const was = before.scroll,
      now = after.scroll;
    if (
      !was ||
      !now ||
      ["timeline", "effect", "target", "source", "subject", "axis", "signature"].some(
        (key) => was[key] !== now[key],
      )
    )
      return null;
    const localRebase = translationRebase(property, before.keyframes, after.keyframes);
    if (!localRebase) return null;
    const rebase = viewportTranslation(property, before, after, localRebase);
    if (!rebase) return null;
    const prior = scrollAt(was.source, from),
      next = scrollAt(was.source, to);
    if (!prior || !next) return null;
    const source = viewportScroll(was.source, from, {
      left: was.axis === "x" ? prior.left - next.left : 0,
      top: was.axis === "y" ? prior.top - next.top : 0,
    });
    const carried = { left: by.left - rebase.left, top: by.top - rebase.top };
    const travel = Math.hypot(source.left, source.top);
    if (!travel) return null;
    const along = (carried.left * source.left + carried.top * source.top) / travel;
    const across = (carried.left * source.top - carried.top * source.left) / travel;
    return Math.abs(across) < 1 && along >= -0.01 && along <= travel + 0.01
      ? {
          motion: carried,
          rebase,
          source,
          travel,
          along,
          across,
          before_scroll: prior,
          after_scroll: next,
        }
      : null;
  };
  // A reading kept for the task that takes it. Each moved box a credit is weighed for
  // asks the same questions of the same animations and ancestors, and nothing the watch
  // does in one task restyles the page or edits an effect, so an answer read once holds
  // until the task ends.
  const endOfTask = window.lfWatchPlatform.microtask;
  const forTask = (read) => {
    let kept = null;
    return (key) => {
      if (!kept) {
        kept = new Map();
        endOfTask(() => {
          kept = null;
        });
      }
      if (!kept.has(key)) kept.set(key, read(key));
      return kept.get(key);
    };
  };
  const effectProperties = forTask(animationProperties);
  // Reflow belongs to the layout the size animation started in. Its final task may
  // move the folded box into a closed disclosure before this paint is judged.
  const inFlow = (element, at) => {
    const style = paintAt(element, at);
    return (
      style && !["absolute", "fixed"].includes(style.position) && style.float === "none"
    );
  };
  const boxParent = (element, at) => {
    let parent = paintAt(element, at)?.parent;
    while (parent && paintAt(parent, at)?.display === "contents")
      parent = paintAt(parent, at)?.parent;
    return parent;
  };
  // Retain DOM sibling order as well as ancestry. Named slots can reorder those
  // siblings visually; this has the same limit as compareDocumentPosition did.
  const followsAt = (branch, follower, at) => {
    const ancestors = new Set();
    for (let node = follower; node; node = paintAt(node, at)?.domParent)
      ancestors.add(node);
    let before = branch;
    while (
      paintAt(before, at)?.domParent &&
      !ancestors.has(paintAt(before, at).domParent)
    )
      before = paintAt(before, at).domParent;
    const parent = paintAt(before, at)?.domParent;
    if (!parent) return false;
    let after = follower;
    while (after && paintAt(after, at)?.domParent !== parent)
      after = paintAt(after, at)?.domParent;
    if (!after) return false;
    for (let next = paintAt(before, at)?.next; next; next = paintAt(next, at)?.next)
      if (next === after) return true;
    return false;
  };
  const sizeReaches = (target, element, from, to, axis, change) => {
    const size = axis === "top" ? "height" : "width";
    // The source keeps its old layout path; the receiving box must still belong to
    // that flow in the new reading. Leaving flow cannot borrow the old fold's credit.
    const path = [];
    for (let at = element; at; at = boxParent(at, to)) path.push(at);
    const holding = new Set(path);
    let branch = target;
    while (boxParent(branch, from) && !holding.has(boxParent(branch, from))) {
      if (!inFlow(branch, from)) return false;
      branch = boxParent(branch, from);
      const before = boxAt(branch, from),
        after = boxAt(branch, to);
      if (!before || !after || Math.abs(after[size] - before[size] - change) >= 1)
        return false;
    }
    const flow = boxParent(branch, from);
    if (!inFlow(branch, from) || !flow) return false;
    // An in-flow box moves with its parent, and an absolutely positioned one with its
    // containing block: its nearest positioned ancestor or a box nearer still, such as
    // a transformed one. So an absolute box is carried only where a positioned box
    // between it and the follower holds it, as a diff line holds its comment button.
    const reach = path.indexOf(flow);
    if (reach < 1) return false;
    const follower = path[reach - 1];
    let placed = true;
    for (const box of path.slice(0, reach - 1)) {
      const style = paintAt(box, to);
      if (style.position === "fixed" || style.float !== "none") return false;
      if (style.position === "absolute") placed = false;
      else if (!placed && style.position !== "static") placed = true;
    }
    if (!placed && paintAt(follower, to).position === "static") return false;
    // Block-level children stack vertically in a horizontal-writing block flow.
    // A block container can also hold inline siblings, whose height does not carry
    // the next sibling down; flex, grid, and vertical writing have other axes.
    if (
      axis !== "top" ||
      !["block", "flow-root"].includes(paintAt(flow, to).display) ||
      paintAt(flow, to).writingMode !== "horizontal-tb" ||
      !["block", "flow-root"].includes(paintAt(branch, from).display) ||
      !["block", "flow-root"].includes(paintAt(follower, to).display)
    )
      return false;
    return inFlow(follower, to) && followsAt(branch, follower, from);
  };
  // A sticky box's inset is the line it sticks at, not an offset. While the box stands
  // at that line, a change of the inset moves it by that change within its containing
  // block; while it stands short of the line, not at all. So an animated inset credits
  // the box's move within that block where the move lies between none and the inset's
  // change. box-motion.js's ride relies on this: it carries a scroller's children and
  // moves their sticky heads' insets against the carry, so a stuck head holds its line
  // and one short of it rides with its message. The box's static place, which would
  // say which of the two it is, is not readable, so another move within that span is
  // credited too, as `sticky_scroll` credits one within a scroll's.
  const STICKY_INSETS = {
    top: { axis: "top", sign: 1 },
    bottom: { axis: "top", sign: -1 },
    left: { axis: "left", sign: 1 },
    right: { axis: "left", sign: -1 },
  };
  const stickyInsetMotion = (motion, target, property, before, after, from, to) => {
    const { axis, sign } = STICKY_INSETS[property];
    const prior = pixels(before.values[property]),
      next = pixels(after.values[property]);
    const block = paintAt(target, to).parent;
    if (prior === null || next === null || paintAt(target, from)?.parent !== block)
      return;
    const change = sign * (next - prior);
    const reach = viewportTranslation(property, before, after, {
      left: axis === "left" ? change : 0,
      top: axis === "top" ? change : 0,
    });
    const was = boxAt(target, from),
      now = boxAt(target, to),
      blockWas = boxAt(block, from),
      blockNow = boxAt(block, to);
    if (!reach || !was || !now || !blockWas || !blockNow) return;
    const within = Object.fromEntries(
      ["left", "top"].map((side) => [
        side,
        now[side] - blockNow[side] - (was[side] - blockWas[side]),
      ]),
    );
    if (
      !["left", "top"].every(
        (side) =>
          within[side] >= Math.min(0, reach[side]) - 1 &&
          within[side] <= Math.max(0, reach[side]) + 1,
      )
    )
      return;
    for (const side of ["left", "top"])
      credit(motion, "sticky_inset", target, side, within[side], {
        property,
        before: before.values[property],
        after: after.values[property],
        reach,
        block,
      });
  };
  const animationMotion = (node, from, to, animations) => {
    const element = node.nodeType === Node.TEXT_NODE ? up(node) : node;
    const motion = { left: 0, top: 0, terms: [] };
    if (!element) return motion;
    for (const details of nativeClosures.keys()) {
      const before = boxAt(details, from),
        after = boxAt(details, to),
        first = layoutAt(element, from),
        last = layoutAt(element, to);
      if (!before || !after || !first || !last) continue;
      const change = after.height - before.height;
      if (
        change <= -1 &&
        Math.abs(last.top - first.top - change) < 1 &&
        sizeReaches(details, element, from, to, "top", change)
      )
        credit(motion, "native_details_reflow", details, "top", change, {
          before,
          after,
          first,
          last,
        });
    }
    const seen = new Map();
    for (const animation of new Set(animations)) {
      const target = animation.effect.target;
      if (!target) continue;
      const samples = animated.get(animation);
      const earlier = samples?.findLast((reading) => reading.at <= from);
      const later = samples?.findLast((reading) => reading.at <= to);
      for (let index = 0; index < (earlier?.consumers?.length ?? 0); index++) {
        const first = earlier.consumers[index],
          last = later?.consumers?.[index];
        if (
          !first ||
          !last ||
          first.node !== last.node ||
          !ancestryAt(element, from).includes(first.node) ||
          !ancestryAt(element, to).includes(first.node)
        )
          continue;
        const prior = animationTranslation("translate", first.value);
        const next = animationTranslation("translate", last.value);
        if (!prior || !next) continue;
        const by = viewportTranslation(
          "translate",
          { axes: first.axes },
          { axes: last.axes },
          { left: next.left - prior.left, top: next.top - prior.top },
        );
        if (!by) continue;
        for (const axis of ["left", "top"])
          credit(motion, "inherited_translation", first.node, axis, by[axis], {
            property: first.key,
            before: first.value,
            after: last.value,
          });
      }
      if (!ancestryAt(element, to).includes(target)) {
        // A size animation can move boxes later in its flow. The size change
        // must propagate through its ancestors to a following in-flow branch.
        const properties = effectProperties(animation);
        if (!properties.some((property) => SIZE_GEOMETRY.has(property))) continue;
        const before = boxAt(target, from),
          after = boxAt(target, to);
        const first = layoutAt(element, from),
          last = layoutAt(element, to);
        if (!before || !after || !first || !last) continue;
        for (const axis of ["left", "top"]) {
          const size = axis === "top" ? "height" : "width";
          const logicalSize = axis === "top" ? "blockSize" : "inlineSize";
          if (
            !properties.some(
              (property) => property === size || property === logicalSize,
            )
          )
            continue;
          const change = after[size] - before[size];
          if (
            Math.abs(change) < 1 ||
            Math.abs(last[axis] - first[axis] - change) >= 1 ||
            !sizeReaches(target, element, from, to, axis, change)
          )
            continue;
          credit(motion, "animation_reflow", target, axis, change, {
            before,
            after,
            first,
            last,
            properties,
          });
        }
        continue;
      }
      const readings = animated.get(animation);
      const before = readings?.findLast((reading) => reading.at <= from);
      const after = readings?.findLast((reading) => reading.at <= to);
      if (!before || !after) continue;
      const properties = seen.get(target) ?? new Set();
      for (const property of effectProperties(animation)) {
        if (properties.has(property)) continue;
        properties.add(property);
        if (!(property in before.values) || !(property in after.values)) continue;
        if (property in STICKY_INSETS && paintAt(target, to)?.position === "sticky") {
          stickyInsetMotion(motion, target, property, before, after, from, to);
          continue;
        }
        const prior = animationTranslation(property, before.values[property]);
        const next = animationTranslation(property, after.values[property]);
        if (!prior || !next) continue;
        const by = viewportTranslation(property, before, after, {
          left: next.left - prior.left,
          top: next.top - prior.top,
        });
        if (!by) continue;
        const scroll =
          before.scroll || after.scroll
            ? scrollEffectMotion(property, before, after, from, to, by)
            : null;
        if ((before.scroll || after.scroll) && !scroll) continue;
        const amount = scroll?.motion ?? by;
        // A timeline binding contains platform objects; the signature already
        // retains its deciding numeric/CSS configuration in serializable form.
        const sample = (reading) => ({
          at: reading.at,
          values: reading.values,
          axes: reading.axes,
          keyframes: reading.keyframes,
          scroll: reading.scroll
            ? {
                source: reading.scroll.source,
                axis: reading.scroll.axis,
                signature: reading.scroll.signature,
              }
            : null,
        });
        const inputs = {
          property,
          before: sample(before),
          after: sample(after),
          viewport: by,
          scroll,
        };
        for (const axis of ["left", "top"])
          credit(
            motion,
            scroll ? "scroll_animation" : "animation",
            target,
            axis,
            amount[axis],
            inputs,
          );
      }
      seen.set(target, properties);
    }
    return motion;
  };
  // The credit owners retain their accepted terms. A failing comparison keeps
  // these exact terms until paint admission; reporting never re-runs the solver.
  // Keep the sampled endpoints even when no term was accepted: otherwise zero
  // credit cannot distinguish a missing owner from a missing or ineligible sample.
  // Size effects can reflow siblings, including after their target leaves that
  // flow. Keep those candidates even when they are not the receiver's ancestors;
  // filtering by successful propagation would hide the rejected proof we need.
  const motionEvidence = (node, from, to, selected) => {
    const ancestors = new Set([
      ...ancestryAt(node, from),
      ...ancestryAt(node, to),
      node,
    ]);
    const candidates = new Set([
      ...selected,
      ...renderings.flatMap((rendering) => [...rendering.own]),
    ]);
    const endpoint = (sample) =>
      sample ? { at: sample.at, values: sample.values } : null;
    return [...candidates]
      .filter(
        (animation) =>
          ancestors.has(animation.effect?.target) ||
          effectProperties(animation).some((property) => SIZE_GEOMETRY.has(property)),
      )
      .map((animation) => {
        const samples = animated.get(animation) ?? [];
        return {
          target: animation.effect.target,
          selected: selected.includes(animation),
          properties: effectProperties(animation),
          before: endpoint(samples.findLast((sample) => sample.at <= from)),
          after: endpoint(samples.findLast((sample) => sample.at <= to)),
        };
      });
  };
  const motionComparison = (
    from,
    to,
    before,
    after,
    layoutBefore,
    layoutAfter,
    scroll,
    motion,
    node,
    selected,
  ) => {
    const observed = { left: after.left - before.left, top: after.top - before.top };
    return {
      before: { at: from, rect: before, layout: layoutBefore },
      after: { at: to, rect: after, layout: layoutAfter },
      observed,
      scroll_credit: { left: scroll.left, top: scroll.top },
      animation_credit: { left: motion.left, top: motion.top },
      residual: {
        left: observed.left - scroll.left - motion.left,
        top: observed.top - scroll.top - motion.top,
      },
      scroll_terms: scroll.terms,
      animation_terms: motion.terms,
      animations: motionEvidence(node, from, to, selected),
    };
  };
  const pendingMotion = [];
  // Whether a frame's reading held `node`. A node that left the page keeps its last
  // reading in the ledger, so a node that returns elsewhere, as a notice taken down
  // and later shown again does, would otherwise read as carried from where it last
  // stood; what returns is a new reading, which no motion compares.
  const frameNodes = new WeakMap();
  const readIn = (frame, node) => {
    let held = frameNodes.get(frame.nodes);
    if (!held) frameNodes.set(frame.nodes, (held = new Set(frame.nodes)));
    return held.has(node);
  };
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
        if (
          prior.paint.labelOwner &&
          (prior.paint.labelOwner !== next.paint.labelOwner ||
            prior.paint.labelText !== next.paint.labelText)
        )
          continue;
        // A changed text node is a new reading, even when Lit retained its DOM
        // identity. Its old and new glyph fragments are not the same landmark.
        if (node.nodeType === Node.TEXT_NODE && prior.words !== next.words) continue;
        const animations = around.flatMap((frame) => frame.motion);
        const scroll = scrollMotion(
          node,
          around[before].at,
          around[after].at,
          animations,
        );
        const motion = animationMotion(
          node,
          around[before].at,
          around[after].at,
          animations,
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
            readIn(around[before], node) &&
            readIn(around[after], node) &&
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
              evidence: motionComparison(
                around[before].at,
                around[after].at,
                previousRect,
                currentRect,
                { left: layoutLeft, top: layoutTop },
                { left: nextLeft, top: nextTop },
                scroll,
                motion,
                node,
                animations,
              ),
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
          report(JSON.stringify(["moved", name(node)]), {
            code: "moved-without-input",
            node: name(node),
            by: by(proof.previousRect, proof.currentRect),
            beside: beside(entry.sources, node),
            evidence: {
              kind: "passive",
              node: name(node),
              fragment,
              paint_at: entry.startTime,
              comparisons: (stable ? chain : [proof]).map((move) => move.evidence),
            },
          });
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
      const scroll = scrollMotion(node, typing.at, painted, typing.moving);
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
      const field = name(typing.field),
        place = name(node);
      report(JSON.stringify(["typing", field, place]), {
        code: "typing-moved",
        node: place,
        field,
        by: by(before, after),
        found: box(before),
        painted: box(after),
        beside: beside(entry.sources, node),
        evidence: {
          kind: "typing",
          node: name(node),
          field: name(typing.field),
          paint_at: entry.startTime,
          comparisons: [
            motionComparison(
              typing.at,
              painted,
              before,
              after,
              from,
              to,
              scroll,
              motion,
              node,
              typing.moving,
            ),
          ],
        },
      });
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
    presentationChanged();
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
    // `drained` judges native shift records before retiring their closing motion.
    // A settled closure can leave only after the paint checkpoint that followed
    // its final size has passed.
    for (const [node, { settledAt }] of nativeClosures)
      if (settledAt !== null && settledAt <= through) nativeClosures.delete(node);
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
        !landing.has(rendering) &&
        rendering.through < retainedFrom &&
        (rendering.typing?.until ?? -Infinity) < retainedFrom &&
        ![...rendering.own].some(activeMotion)
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
  // The fixture awaits actual paint and observer drainage. An outer hang watchdog
  // may fail this wait; no elapsed-time fallback can turn unfinished paint green.
  window.lfShiftsJudged = () => {
    // The next unannounced frame is checked, so a test that ends before the
    // periodic check still has its last change compared.
    quiet = VERIFY - 1;
    const through = nativePerformance.now();
    // A document nobody can see has no paint pending on screen: Chrome stops
    // rendering a hidden tab, and a child frame its embedding page hides, clips or
    // scrolls out of the viewport, as it does a gallery's samples below the fold.
    // Its existing records are still judged against a fresh pose; whether it is on
    // screen is a native fact, not a time limit.
    const unseen = () => {
      read(nativePerformance.now());
      drained(through);
    };
    if (document.hidden) {
      unseen();
      return Promise.resolve();
    }
    return new Promise((resolve) => {
      let complete = false;
      const leftScreen = () => {
        if (complete) return;
        try {
          unseen();
        } finally {
          finish();
        }
      };
      const tabHidden = () => {
        if (document.hidden) leftScreen();
      };
      // Intersection with the top-level viewport covers every way an embedding page
      // takes a frame off screen, across origins, and Chrome delivers it to a frame
      // whose rendering it has stopped. It is read through a box the watch stands
      // over the frame's own viewport while it waits, since the root's box can scroll
      // out of that viewport, as a live page's does. Its first entry reports the
      // present state. The runtime instead asks the page holding the frame
      // (runtime/frame-visibility.js), which no page's own styles can mislead; the
      // watch runs in every frame, Leaf's or not, before that runtime, and has no
      // holder to ask. A page whose styles transform `html` carries this box off
      // screen with its root, so the watch judges it as hidden.
      let screen = null;
      let onScreen = null;
      if (window !== top) {
        screen = document.createElement("lf-shift-screen");
        screen.style.cssText =
          "all:initial;position:fixed;inset:0;visibility:hidden;pointer-events:none";
        cameraNodes.add(screen);
        document.documentElement.append(screen);
        onScreen = new IntersectionObserver((entries) => {
          if (!entries.at(-1).isIntersecting) leftScreen();
        });
        onScreen.observe(screen);
      }
      const finish = () => {
        if (complete) return;
        complete = true;
        onScreen?.disconnect();
        screen?.remove();
        cameraNodes.delete(screen);
        document.removeEventListener("visibilitychange", tabHidden);
        resolve();
      };
      document.addEventListener("visibilitychange", tabHidden);
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
