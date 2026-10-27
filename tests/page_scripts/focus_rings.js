// Browser focus evidence. The callbacks share one reading of focus, resolved ink,
// and ring paint; each evaluation keeps its helpers local to that observation.
(helpers) => {
  const { named } = helpers;

  function deepFocus() {
    let e = document.activeElement;
    while (e) {
      let next = e.shadowRoot?.activeElement;
      if (!next && e.tagName === "IFRAME") {
        const child = e.contentDocument?.activeElement;
        if (child && child !== e.contentDocument.body) next = child;
      }
      if (!next) break;
      e = next;
    }
    return e;
  }

  // The box a node is laid out and painted inside: its slot where it is slotted, else its
  // parent, else the host of the shadow tree it is the top of. A control slotted into a
  // field stands inside the field's own shadow tree, whose frame draws the ring for it
  // (`::part(base lf-focus-within)`); the DOM parent skips that frame for the host.
  const flatParent = (n) =>
    n.assignedSlot ?? n.parentElement ?? n.getRootNode().host ?? null;

  // The focus ring where a box casts it as a shadow rather than drawing it as an outline,
  // and how far past its edge that band reaches. Two rules in the layer draw it that way —
  // the anchored response bar, which writes `outline: none` so its states keep one
  // silhouette, and the target hint the keyboard is browsing, a chip in a layer nothing can
  // focus — and to a user they are the same band as every other ring (--focus-shadow,
  // theme.css).
  //
  // What makes it that band rather than the layer's other shadows: no offsets, no blur, and
  // the ring's own width as its spread. The elevation shadows are the third length away —
  // a lift blurs and a ring does not — and the two inset washes are the `inset` keyword
  // away. Returned as the width, because a spread has no offset of its own, so the outset
  // a caller measures is the whole of the band; nought where the box paints no such thing.
  //
  // The accent arrives resolved twice because the layer spells it twice: a plain
  // `var(--accent)` serializes as `rgb(...)` while a `color-mix()` into srgb serializes as
  // `color(srgb r g b / a)`. The mix is matched on its triple alone, so how much of the
  // accent a rule laid down is not part of the question — the bar carries an accent border
  // as well and wants less of it than a chip standing over the page's own words.
  function shadowBand(cs, accent, mixed) {
    const w = parseFloat(cs.getPropertyValue("--focus-ring-w")) || 0;
    if (!w) return 0;
    // Split on the commas between layers, not on the ones inside `rgba(...)`.
    for (const layer of cs.boxShadow.split(/,(?![^(]*\))/)) {
      const text = layer.trim();
      if (/(^|\s)inset(\s|$)/.test(text)) continue;
      const lengths = text.match(/-?(?:\d*\.)?\d+px/g);
      if (!lengths || lengths.length < 4) continue;
      const [x, y, blur, spread] = lengths.map(parseFloat);
      if (x || y || blur || spread !== w) continue;
      const ink = text.replace(/-?(?:\d*\.)?\d+px/g, "").trim();
      if (ink === accent || (mixed && ink.includes(mixed))) return w;
    }
    return 0;
  }

  // The accent as the browser resolves it, in both of the spellings the layer writes it in.
  // Read back through an outline so a comparison is between values of one kind: read
  // straight off an element, a custom property serializes as it was written while
  // `outline-color` serializes as it resolved, and the two agree for `#2f5480` and for
  // nothing more exotic. `color-mix()` or `light-dark()` in a package's accent left every
  // rule in the layer uncredited and the gate red on a page drawing every ring correctly.
  //
  // `mixed` is the srgb triple a `color-mix()` resolves the accent into, which is a
  // different serialization of the same colour, so a shadow written that way is read on the
  // triple and not on the whole string.
  //
  // In <head>, because this must not put a node in the page's own content while the page is
  // being read. The same span in <body> answers the same.
  function accentSwatch() {
    const swatch = document.createElement("span");
    swatch.style.cssText = "outline: 1px solid var(--accent)";
    document.head.append(swatch);
    const accent = getComputedStyle(swatch).outlineColor;
    swatch.style.outlineColor = "color-mix(in srgb, var(--accent) 100%, transparent)";
    const mixed =
      getComputedStyle(swatch).outlineColor.match(
        /color\(srgb ([\d.]+ [\d.]+ [\d.]+)/,
      )?.[1] ?? null;
    swatch.style.outlineColor = "var(--mark-ink)";
    const markInk = getComputedStyle(swatch).outlineColor;
    swatch.remove();
    return { accent, mixed, markInk };
  }

  // Which rule drew a ring is the browser's answer, not the page's: the readings below
  // decide from the paint that a box wears the band, and leave the boxes here for
  // `ring_rules` (render_cases_layout.py), which asks the DevTools protocol which matched
  // rule won the outline or shadow. A page script cannot hand an element to the protocol
  // by value, so each reading leaves its boxes on this one global, in the order of the
  // answers it returns, and the Python side takes them off again.
  function stash(boxes) {
    globalThis.__lfRingBoxes = boxes;
  }

  // The carriers of every focus ring the page is showing right now. Faults are read
  // after the protocol supplies the pseudo-elements' own border boxes.
  //
  // Asked of every box painting one, rather than of the focused one.
  // The two are not the same set: three rules draw the ring on something other than the
  // control holding focus — a decision wears it for whichever of its controls the user
  // reached, a joined option group wears the one its picks give up, and an element
  // a focused thread is anchored to wears it with no focus of its own — and a reading that
  // asks only `getComputedStyle(activeElement)` returns `no ring here` for every one. A 2px
  // cut planted on one of those carriers passed the entire example corpus.
  //
  // The focused element is a candidate too, whatever paints its outline, so a ring the
  // platform draws and the layer never drew is still measured.
  //
  // Both carriers of the band are read. Most of the layer's rules draw it as an outline;
  // two cast it as a shadow instead, and a reading that knew only the outline reported the
  // response bar and the browsed target hint as boxes with no ring on them at all.
  function ringCandidates() {
    const { accent, mixed } = accentSwatch();
    // The band this box casts as a shadow, where it draws one, in the width it draws it
    // at. Its own comment carries what makes a shadow that band rather than a lift.
    const hereShadow = (cs) => shadowBand(cs, accent, mixed);
    // Whether this box paints the layer's ring: `--focus-ring` is
    // `var(--focus-ring-w) solid var(--accent)`, so style, width and colour are all what
    // the element computes them to.
    //
    // Or the same band cast as a shadow, which is the same ring to the user and so the
    // same ring here: the anchored response bar and the browsed target hint draw it that
    // way. Left out, the bar's own controls came back drawn by the floor rule whose
    // outline this one takes away, and the hint's band went unmeasured wherever it stood.
    const focused = deepFocus();
    const isFocusRing = (cs) =>
      (cs.outlineStyle === "solid" &&
        cs.outlineWidth === cs.getPropertyValue("--focus-ring-w").trim() &&
        cs.outlineColor === accent) ||
      hereShadow(cs) > 0;
    // Every box painting the ring, read off the composed page. Whether a ring is there is
    // what the paint says, so this asks the paint; which rule drew it is the protocol's
    // answer, taken after (`ring_rules`).
    //
    // An annotated source can also carry an authored contour in the same ink.
    // The rule reading keeps that contour out unless a ring rule or actual focus
    // claims it. Projected target feedback is excluded by its state below.
    //
    // The focused element joins them whatever paints its outline, since a visible ring
    // cut in half is a fault whoever drew it.
    //
    // Roots are collected as the sweep goes. Pushing onto the array being walked carries
    // it into a shadow tree another shadow tree opened, which a pass over the document's
    // own hosts never reached.
    const roots = [document];
    const claimed = [];
    for (const root of roots)
      for (const el of root.querySelectorAll("*")) {
        if (el.shadowRoot) roots.push(el.shadowRoot);
        // Target feedback shares the ring's ink and token, but its clipped ends
        // say which object is referenced, not where keyboard input goes.
        if (
          el.matches(
            ".lf-aim, .lf-target-trace, .lf-visual-mark:not(.lf-visual-mark-focus)",
          )
        )
          continue;
        const cs = getComputedStyle(el);
        if (isFocusRing(cs)) claimed.push({ el, cs });
        const after = getComputedStyle(el, "::after");
        if (after.content !== "none" && isFocusRing(after))
          claimed.push({ el, cs: after, pseudo: true });
      }
    if (
      focused &&
      focused !== document.body &&
      focused !== document.documentElement &&
      !claimed.some((claim) => claim.el === focused)
    )
      claimed.push({ el: focused, cs: getComputedStyle(focused) });
    // A skipped until-found panel retains stale boxes; only rendered carriers count. A
    // `display: contents` element has no box, so the platform calls it unrendered, but
    // its pseudo-element still renders, in its parent's box: a page of parts' holder
    // draws the open part's ring that way. Such a pseudo is shown where its parent is.
    const shown = (el, pseudo) =>
      pseudo && getComputedStyle(el).display === "contents"
        ? shown(flatParent(el), false)
        : el.checkVisibility({
            contentVisibilityAuto: true,
            opacityProperty: true,
            visibilityProperty: true,
          });
    const visible = claimed.filter(({ el, pseudo }) => shown(el, pseudo));
    const rings = visible
      .map((claim) => ({
        ...claim,
        outlined:
          claim.cs.outlineStyle === "none" ? 0 : parseFloat(claim.cs.outlineWidth) || 0,
        cast: hereShadow(claim.cs),
        here: isFocusRing(claim.cs),
      }))
      .filter(({ outlined, cast }) => outlined || cast);
    globalThis.__lfRingClaims = rings;
    stash(rings.map(({ el }) => el));
    return rings.map(({ outlined, pseudo }) => ({
      pseudo: pseudo ? "after" : null,
      carrier: outlined ? "outline" : "box-shadow",
    }));
  }

  // Complete the same candidate reading after the protocol has measured pseudo boxes.
  // A pseudo-element need not share its originating element's border box: anchored
  // frames and frames moving with scrolled contents both depend on its actual layout.
  async function ringsDrawn(rectangles) {
    // shownBand, rather than a fourth reading of what a box clips to. Its own comment
    // carries why: page check --render imports it so the band a handover is refused
    // against and the band the page paints to are one reading, and written twice they
    // disagreed twice. This was the third copy and it was wrong in both of the ways that
    // comment names — it asked only about overflow, so paint containment and
    // content-visibility clipped a ring away with nothing said, and it measured the
    // padding box with the scrollbar's gutter still in it.
    const { shownBand } = await window.__lfCheckApi();
    const holds = (a, b) => {
      for (let n = b; n; n = flatParent(n)) if (n === a) return true;
      return false;
    };
    const focused = deepFocus();
    const claimed = globalThis.__lfRingClaims;
    delete globalThis.__lfRingClaims;
    const answers = [];
    for (const [index, { el, cs, pseudo, cast, outlined, here }] of claimed.entries()) {
      // Straight off the computed style, which holds because no ring in this layer moves.
      // A ring on its way somewhere reads as wherever it has got to — mid-transition the
      // platform reports the animated value, which early on is the value the property is
      // leaving — and this once read every ring that way, because the theme's
      // reduced-motion guard shortened transitions rather than removing them and
      // `transition-property` is `all`, so a ring arriving was a ring in transit for two
      // frames on every page. That is fixed where it was made (theme.css). A layer that
      // deliberately animates a ring owes this reading a wait on `getAnimations()`; one
      // written here now would wait on nothing, in front of the reading it is meant to
      // protect.
      //
      // The band, and how far past the box's own edge it reaches. An outline's is its
      // width and its offset, which the layer's inset rings write negative; a shadow
      // ring's is its spread, which has no offset to add. The outline answers first
      // wherever there is one, so every box this reading already measured is measured the
      // same way: the two carriers are on different boxes in this layer, and where a box
      // ever wears both, the outline is the one the layer's own rules put there.
      const w = outlined || cast;
      const grow = outlined ? outlined + (parseFloat(cs.outlineOffset) || 0) : cast;
      const b = pseudo ? rectangles[index] : el.getBoundingClientRect();
      const ring = {
        top: b.top - grow,
        left: b.left - grow,
        bottom: b.bottom + grow,
        right: b.right + grow,
      };
      const at = (r) => [r.left, r.top, r.right, r.bottom].map(Math.round).join();
      // A ring drawn inside its control's box — twelve of the layer's rules inset theirs —
      // cannot leave it, so `cuts` is empty for those by geometry and the covers half is
      // the whole of what this says about them.
      const cuts = [];
      let scrolled = false;
      const above = flatParent;
      // One side, one message, named for the innermost box that took it. A scroll region's
      // edge is often the window's to the pixel — a list flush with a window-edge panel
      // shares its right edge, which is innerWidth — and one ring reported twice reads as
      // two defects. The innermost box is the more useful of the two answers anyway: it
      // is the box the control lives in.
      const taken = {};
      const took = (band, who) => {
        // Only the sides where this box is showing the control's own edge, which is the
        // claim a box can be held to: where the control can be seen, so can the ring
        // around it. Asked of the edge rather than of the size, because the two answers
        // differ for everything not focused — a code block taller than the window hangs
        // out of it however the browser scrolls; a decision wears its ring for a control the
        // user reached near its top and its own foot is below the fold; a thread's
        // element mark is painted on a widget nobody has scrolled to at all. None of
        // those is a ring drawn outside its box, and a size test excuses the first and
        // reports the other two.
        //
        // What it gives up in exchange: a control whose own box its holder clips gets no
        // ring reading on that side, where a size test would have reported one. That is
        // a control drawn where no user can reach it rather than a ring leaving its
        // box, and CLIPPED_CONTROLS is the reading that owns it.
        //
        // Asked of the control's border box and not of its ring, because a ring is the one
        // thing a box is asked to find room for beyond what it holds: a control filling its
        // scroller to the pixel excused itself from every reading it should have answered.
        const shows = {
          top: b.top >= band.top - 0.5,
          bottom: b.bottom <= band.bottom + 0.5,
          left: b.left >= band.left - 0.5,
          right: b.right <= band.right + 0.5,
        };
        for (const [side, by] of Object.entries({
          top: band.top - ring.top,
          left: band.left - ring.left,
          bottom: ring.bottom - band.bottom,
          right: ring.right - band.right,
        }))
          if (!taken[side] && by > 0.5 && shows[side])
            taken[side] =
              `its ${side} edge is ${Math.round(by * 10) / 10}px outside ` +
              who +
              ` (ring ${at(ring)} vs band ${at(band)})`;
      };
      // `clipped` in runtime/geometry.js is this walk, and this is its shape: from the box itself
      // rather than its parent, skipping the box's own band because an element is not clipped
      // by its own overflow, and stopping at the first fixed box. Its comment records what
      // starting at the parent cost — "the question of every ancestor of a fixed box and
      // never of the box" — which is the bug this reading had too.
      for (let a = el; a; a = above(a)) {
        if (a !== el) {
          if (a.scrollHeight > a.clientHeight) scrolled = true;
          const band = shownBand(a);
          if (band) took(band, named(a));
        }
        if (getComputedStyle(a).position === "fixed") break;
      }
      // The window last, so an inner box that shares an edge with it is the one named, and
      // unconditionally, because the walk above may have stopped at a fixed box and every
      // box stops somewhere. It is the outermost clip there is: a fixed subtree is laid out
      // against it, and everything else reaches it through body, which is this page's
      // scroller. Not a claim that nothing else could clip a fixed box — a containing block
      // established by transform, filter or containment is a real case, and a chrome
      // surface's backdrop-filter is one such generator — but the walk covers that case
      // now by asking every box on the way up instead of branching on the focused one's
      // own position.
      took({ top: 0, left: 0, bottom: innerHeight, right: innerWidth }, "the window");
      for (const side of ["top", "left", "bottom", "right"])
        if (taken[side]) cuts.push(taken[side]);
      // Whether a box paints at a ring sample: its fill anywhere, or its border where the
      // sample lies on it. A face drawn by its border alone, such as a playground choice,
      // covered 1px of its neighbour's ring unseen while this read only fills.
      const clear = (colour) => /^(transparent$|rgba\(.*,\s*0\))/.test(colour);
      const paints = (n, x, y) => {
        const s = getComputedStyle(n);
        if (s.backgroundImage !== "none" || !clear(s.backgroundColor)) return true;
        const o = n.getBoundingClientRect();
        return Object.entries({
          Left: x - o.left,
          Right: o.right - x,
          Top: y - o.top,
          Bottom: o.bottom - y,
        }).some(
          ([side, by]) =>
            by < parseFloat(s[`border${side}Width`]) && !clear(s[`border${side}Color`]),
        );
      };
      const mid = (x, y) => (x + y) / 2;
      const covers = [];
      // Whether this reading has an order to read at all. It works by hit-testing the ring's
      // own pixels and taking whatever comes back as standing over them — but an outline is
      // painted by its control, at its control's level, and an outline's pixels are not
      // hit-testable. A pixel of ring outside the control's box therefore returns whatever
      // is beneath, and beneath is where the answer would have to come from.
      //
      // That is sound where an ancestor's hit surface covers the sample. A chrome layer
      // that takes no hits, such as the floating panel's window-wide ground, returns the
      // page underneath for a ring pixel there, unless a box inside it restores hits
      // over the sample. Read each ring side under the nearest such box;
      // `cuts` remains a geometry reading even where hit order says nothing.
      const orderedAt = (x, y) => {
        let hitSurface = null;
        for (let a = el; a; a = above(a)) {
          if (getComputedStyle(a).pointerEvents === "none") {
            if (!hitSurface) return false;
            const b = hitSurface.getBoundingClientRect();
            return x >= b.left && x <= b.right && y >= b.top && y <= b.bottom;
          }
          hitSurface = a;
        }
        return true;
      };
      // Whether a fixed surface standing over this ring is worth reporting. Tab scrolls
      // the control it lands on clear of fixed chrome — that is what the document's
      // scroll-padding is for — so a fixed bar over the focused control's ring is a
      // promise broken. Over a ring some ancestor wears it is not: nobody scrolled that
      // box, and where its top edge comes to rest a pixel under the bar is the user's
      // scroll position rather than the layer's doing. An option group 2261px tall, whose
      // pick the walk had landed on, is the case.
      const fixedOver = (n) => {
        for (let a = n; a; a = above(a))
          if (getComputedStyle(a).position === "fixed") return true;
        return false;
      };
      const scrolledTo = el === focused;
      // Whether a box inside the control paints after the ring. The control's own outline
      // paints with its in-flow content, so a descendant standing on it paints beneath it
      // unless a positioned box, itself or one between it and the control, lifts it into
      // the positioned layer painted afterwards. The margin card's reply row was the case:
      // pinned to the transcript's foot and painting the thread's surface, it took the
      // bottom run of the thread's inset ring while this reading excused everything inside
      // the control as the control itself. A ring carried by a positioned `::after` is in
      // that layer already, at its own z-index and after every descendant in tree order,
      // so only a descendant lifted to a higher z-index stands over it.
      //
      // A z-index places a flex or grid item as it places a positioned box, and makes either
      // a stacking context that holds everything inside it at its own level. The thread
      // list's ring is the case: a `::after` at z-index 1 over the list, both grid items of
      // one frame, the list at 0, so an open card filling the list reaches the ring's bottom
      // run and stays beneath it.
      const stacked = (s, holder) =>
        s.zIndex !== "auto" &&
        (s.position !== "static" || /flex|grid/.test(getComputedStyle(holder).display));
      const carrier = pseudo && stacked(cs, el) ? parseFloat(cs.zIndex) || 0 : null;
      const lifted = (n) => {
        let lift = null;
        for (let a = n; a && a !== el; a = above(a)) {
          const s = getComputedStyle(a);
          if (stacked(s, above(a))) lift = parseFloat(s.zIndex) || 0;
          else if (s.position !== "static") lift = Math.max(lift ?? 0, 0);
        }
        return lift !== null && (carrier === null || lift > carrier);
      };
      // Each run sampled in the middle of the part of it that is on screen, rather than in
      // the middle of the whole run. They differ for anything taller or wider than the
      // window, and then the plain midpoint is a point the user cannot see: an option
      // group 1791px tall was sampled 22px down the window, which is inside the chrome
      // fixed there, and its status dot came back as standing over its ring.
      const runX = [Math.max(ring.left, 0), Math.min(ring.right, innerWidth)];
      const runY = [Math.max(ring.top, 0), Math.min(ring.bottom, innerHeight)];
      const shownRun = runX[0] <= runX[1] && runY[0] <= runY[1];
      // Each run sampled in the middle of the band it is, rather than half a pixel inside
      // its outer edge. Both points are on the ring; the outer one is also the last
      // fraction of a pixel of the control, and hit testing rounds a subpixel edge to the
      // device pixel it shares with the next box. Butted cells are where that shows: an
      // options group's rows meet on a fractional line, so the ring on the row the
      // keyboard is on reported the row below as painting over its bottom edge — the
      // seam's rounding, not anything drawn there. Floored at half a pixel so a hairline
      // ring still samples inside itself.
      const into = Math.max(w / 2, 0.5);
      for (const [side, x, y] of shownRun
        ? [
            ["top", mid(...runX), ring.top + into],
            ["bottom", mid(...runX), ring.bottom - into],
            ["left", ring.left + into, mid(...runY)],
            ["right", ring.right - into, mid(...runY)],
          ]
        : []) {
        if (x < 0 || y < 0 || x > innerWidth || y > innerHeight) continue;
        if (!orderedAt(x, y)) continue;
        for (const over of document.elementsFromPoint(x, y)) {
          if (over === el || holds(over, el)) break;
          if (holds(el, over)) {
            if (!lifted(over)) break;
            if (!paints(over, x, y)) continue;
            covers.push(
              `its ${side} edge is under ` +
                named(over) +
                `, inside it` +
                ` (ring ${at(ring)}, sampled ${Math.round(x)},${Math.round(y)})`,
            );
            break;
          }
          if (!paints(over, x, y)) continue;
          if (!scrolledTo && fixedOver(over)) break;
          // Is the control itself under this too? Where a control stands partly behind
          // something, the ring's run on that side is behind whatever the control is behind,
          // which is a fact about where the control was put rather than about the ring being
          // drawn outside its box. The claim worth making is the other one: where the control
          // can be seen, so can the ring that names it. Stated without a case on purpose —
          // the one this was written for was a drawer's edge handle running the whole height
          // of the window under the chrome at its top, which stopped being true in 3a8f16f0,
          // the commit that added this comment and the handle's top inset together.
          //
          // The step in has to clear the ring's own band. Past an outward ring, `grow + 1`
          // lands on the control's own outermost pixels, so a control whose edge stands
          // behind the cover counts as behind it: a button whose last 4px ran under the
          // open Threads panel was reported for the ring's run there. An inset ring, where
          // grow is nought, needs `grow + w + 1` to land `w + 1` inside the box. With
          // `grow + 1` there, every covered inset ring answered that the control was behind
          // the same thing and was dropped without a word. The rings the panel's own list
          // draws are all inset, so this went blind in the same commit that made them so —
          // a thread lying two pixels under a cover is a card with three sides, and the
          // gate written to catch exactly that reported nothing.
          const step = grow > 0 ? grow + 1 : grow + w + 1;
          const inx = x + (side === "left" ? step : side === "right" ? -step : 0);
          const iny = y + (side === "top" ? step : side === "bottom" ? -step : 0);
          const inside = document.elementsFromPoint(inx, iny);
          if (inside.includes(over)) break;
          // The same surface counts, not only the same box: a page control under the open
          // Threads panel, where it overlays a narrow window, had its ring's run under one
          // card's title while the stepped-in point landed on the card's body.
          const front = inside.findIndex((n) => n === el || holds(el, n));
          if (
            inside
              .slice(0, front < 0 ? inside.length : front)
              .some((n) => holds(n, over) && !holds(n, el))
          )
            break;
          // Or the other way about: a box the control itself paints over. An outline is
          // painted by its control at its control's level, so a box the control stands in
          // front of cannot stand over the ring around it — and the sample lands on one of
          // those whenever a control floats above content its own holder scrolls, which
          // the coarse-pointer edge grip does over the panel's threads. Left unasked, the
          // grip's ring read as covered by whichever line of a thread its band happened to
          // cross, and a two-pixel change to the card's own padding was enough to move one
          // under it.
          //
          // Read off the stepped-in point already taken, whose stack is the paint order
          // there: `over` is not in it, but a box holding `over` usually is, and one
          // ranking below the control puts everything it holds below the control too. A
          // box that holds the control answers nothing — the control is inside it — so the
          // walk stops there rather than reading its rank.
          //
          // A z-index named on the way up orders its box only inside the stacking context
          // around it, so the walk goes on from that context, which paints in the
          // positioned layer around it as a positioned box does. Position lifts a box
          // the same way without naming one — a positioned box leaves its holder's place in
          // the flow to paint in the positioned layer of the nearest ancestor stacking
          // context. A positioned holder still answers for it, since the two paint in that
          // same layer and, with the control outside the holder, in the holder's own tree
          // order. A static holder does not, and the question is then whether the control
          // stands above that layer at all — which is what a z-index of its own says, and
          // what the grip's `z-index: 1` says: nothing painting there can reach its ring,
          // whatever holds it. A control that names none shares the layer, and a neighbour
          // lifted into it can stand over the ring, so the reading reports it.
          const control = inside.findIndex((n) => n === el || holds(el, n));
          // Whether this box stands clear of the layer a box with no z-index of its own
          // paints in, read up to the box that holds them both.
          const clears = (n) => {
            for (let a = n; a && !holds(a, over); a = above(a)) {
              const z = parseFloat(getComputedStyle(a).zIndex);
              if (!Number.isNaN(z)) return z > 0;
            }
            return false;
          };
          // Ending the walk at the first z-index left the grip's ring reported under a
          // thread's sticky title, whose z-index lifts it inside the list and no further,
          // while every pixel of the ring's run was the ring's. The context paints as one
          // unit, so its own rank answers for everything in it; a static holder above a
          // static context answers through `clears`, as above a positioned box.
          const forms = (n) => {
            const s = getComputedStyle(n);
            return (
              stacked(s, above(n)) ||
              s.position === "fixed" ||
              s.position === "sticky" ||
              s.isolation === "isolate" ||
              s.transform !== "none" ||
              s.filter !== "none" ||
              parseFloat(s.opacity) < 1
            );
          };
          // The level a box's side paints at inside the box holding both sides: the
          // outermost stacking context on its way up, at its z-index, or at nought for a
          // context that names none.
          const level = (n) => {
            let z = 0;
            for (let a = n; a && !(holds(a, el) && holds(a, over)); a = above(a)) {
              const s = getComputedStyle(a);
              if (stacked(s, above(a))) z = parseFloat(s.zIndex) || 0;
              else if (forms(a)) z = 0;
            }
            return z;
          };
          let under = false;
          let hoisted = false;
          for (let a = over; a && control >= 0;) {
            // Neither side ranked at the stepped-in point, so their order is that of the
            // two sides inside the box holding both: a control whose side paints at a
            // higher level paints over the cover. A shot's rail, sticky at z-index 1, is
            // the case: its buttons' rings run onto the image the rail stands above.
            if (holds(a, el)) {
              under = level(el) > level(over);
              break;
            }
            const acs = getComputedStyle(a);
            const ranked = inside.indexOf(a);
            if (ranked >= 0) {
              under =
                hoisted && acs.position === "static" ? clears(el) : ranked > control;
              break;
            }
            if (acs.zIndex !== "auto") {
              let context = above(a);
              while (context && !holds(context, el) && !forms(context))
                context = above(context);
              a = context;
              hoisted = false;
              continue;
            }
            if (acs.position !== "static" || forms(a)) hoisted = true;
            a = above(a);
          }
          // Nothing beneath a box the control paints over is over the ring either, so this
          // side is answered rather than carried on down the stack.
          if (under) break;
          const o = over.getBoundingClientRect();
          // Or the control is in front of it, which answers the same question and answers
          // it exactly. An outline is painted by its control, at its control's level, so a
          // box the control paints over cannot be over the ring either, however little of
          // the control it reaches. The depth test above cannot tell that from a band laid
          // across the ring, because both are a box overlapping the control, and only the
          // order says which — and the depth it asks for is more than a shallow overlap
          // has: the comment panel's touch grip stands 44px over a scrolling list, a
          // thread's receipt reached the last two pixels of it, and the ring's bottom run
          // came back reported while every pixel of it was the accent's own. Asked where
          // the two boxes meet, since that is the only place hit testing can order them,
          // and only when both answer there — a point some third box owns says nothing
          // about these two. Hit testing answers a control inside a shadow root with its
          // host, as it does a code block's Copy, whose ring is its shadow button's, so
          // the control's place in the stack is the first box that is it or holds it.
          const meetX = [Math.max(o.left, b.left), Math.min(o.right, b.right)];
          const meetY = [Math.max(o.top, b.top), Math.min(o.bottom, b.bottom)];
          if (meetX[0] <= meetX[1] && meetY[0] <= meetY[1]) {
            const stack = document.elementsFromPoint(mid(...meetX), mid(...meetY));
            const control = stack.findIndex((n) => n === el || holds(n, el));
            const covering = stack.indexOf(over);
            if (control >= 0 && covering >= 0 && control < covering) break;
          }
          covers.push(
            `its ${side} edge is under ` +
              named(over) +
              ` (ring ${at(ring)} vs ${at(o)}, sampled ${Math.round(x)},` +
              `${Math.round(y)})`,
          );
          break;
        }
      }
      answers.push({
        who: named(el),
        here,
        mark: el.matches(".lf-mark-el"),
        pseudo: pseudo ? "after" : null,
        carrier: outlined ? "outline" : "box-shadow",
        focused: el === focused || el.matches(".lf-visual-mark-focus"),
        sample:
          el === focused ||
          el.matches(".lf-visual-mark-focus") ||
          holds(el, focused) ||
          holds(focused, el) ||
          el.hasAttribute("data-lf-ring-sample"),
        scrolled,
        cuts,
        covers,
      });
    }
    return answers;
  }

  // A keyboard stop this sweep has not reached, one it has, or the document boundary.
  // This deliberately waits for no settled geometry: focus paint, and the scroll that
  // brings a stop into view, are synchronous, so the rings a stop lights read as it
  // lands, and only a stop whose rings read faulty waits for the page to come to rest
  // before it is read again. Avoiding a layout-settlement probe at every Tab keeps a
  // complete native-stop sweep affordable.
  function newStop() {
    const e = deepFocus();
    if (!e || e === document.body || e === document.documentElement) return "empty";
    if (window.__lfSeen.has(e)) return "seen";
    window.__lfSeen.add(e);
    return "new";
  }

  // A focused sample the user cannot find, or null when they can.
  //
  // Three answers count, because the layer leaves "here" drawn in three ways and every one of
  // them is the user seeing the same thing.
  //
  // The platform's own ring (`outline-style: auto`) is the first and the commonest. Leaf
  // restyles the controls it draws and leaves that ring on the rest — an authored link, a
  // `summary`, a widget's own native control — and replacing it everywhere would be a
  // change to how the product looks rather than a thing this test is owed.
  //
  // The layer's focus ring is the second, on the stop, a child, or an ancestor: a `choose` group
  // takes the ring for the pick mark inside it, whose own rule states `outline: none`
  // exactly so the two do not both draw, and the user sees the group.
  //
  // What this cannot see, said out loud so a green is not read as more than it is. A
  // joined `lf-options` carrying log news — restated, pending, reported — deliberately
  // stands its ring down, because an element takes one outline and the log has claimed it;
  // the layer's own comment (packages/default/widgets.css) names the carriers that stand in
  // its place as the washed cell and the key badges, and neither is an outline nor an
  // accent shadow. That is a fifth way of drawing "here" and this reading has no honest
  // test for it: accepting a background would pass every stop on a tinted page. No corpus
  // example reaches the state — none carries `restated`, the one shipped log carries no
  // report, and the samples make no gesture — so nothing here is being excused today. A
  // reading of the wash has to come with the corpus case that shows it.
  //
  // A marked element answers the keyboard with the same accent ring as any other
  // focusable passage. Its hover and current-thread contours are written out rather
  // than drawn with the ring's token, so they cannot be mistaken for focus.
  //
  // The band cast as a shadow is the third. The anchored response bar draws it that way —
  // its focused states take the outline off so the field and its choices keep one
  // silhouette — and to a user that is the same ring. It is the sweep's own reading
  // (shadowBand), so the paint and keyboard-stop readings agree on an accent shadow ring
  // rather than each keeping a spelling of it: the earlier one here took any shadow
  // carrying the accent, which a wash or a tinted lift would have satisfied. Read on the
  // stop itself and never on an ancestor, since a card's decorative drop shadow is no
  // answer to where the keyboard is and accepting one from any ancestor would pass every
  // stop on a page with one shadowed box above it.
  //
  // Every colour is resolved through a swatch rather than compared as written, and the
  // accent is resolved twice: `outline-color` serializes as the browser resolved it, and a
  // `color-mix` resolves into a different space than a plain token does, so the ring's
  // `rgb(...)` and the shadow's `color(srgb ...)` are the same colour written two ways and
  // each needs the browser to say so.
  function seenStop() {
    const e = deepFocus();
    if (!e) return null;
    const { accent, mixed } = accentSwatch();
    const ringed = (cs) =>
      cs.outlineStyle === "solid" &&
      cs.outlineWidth === cs.getPropertyValue("--focus-ring-w").trim() &&
      cs.outlineColor === accent;
    // A box whose own content paints over its outline draws the same ring on a later
    // pseudo-element instead: the scrolling thread list's frame, a page thread over its
    // pinned reply row, a code block's host over its sticky notes. It answers under the
    // same rule as an ancestor's outline.
    //
    // Off the stop itself, a ring answers only where the rule that drew it draws with
    // the ring's token. Every ancestor on this chain contains the focus by construction,
    // so containing it says nothing; what separates a ring drawn because the user is here
    // from an authored contour is that the layer's focus rules draw the token.
    // Which rule drew a box's ring is the protocol's answer (`seen_stop`), so the boxes that
    // need it are left for it and returned beside what to say if none of them does.
    const carriers = [];
    const overlaid = (el) => {
      const cs = getComputedStyle(el, "::after");
      if (cs.content !== "none" && ringed(cs)) carriers.push([el, "after"]);
    };
    const cs = getComputedStyle(e);
    if (cs.outlineStyle === "auto" || ringed(cs)) return null;
    if (shadowBand(cs, accent, mixed) > 0) return null;
    overlaid(e);
    // The target painter's focus state names the current keyboard carrier even
    // when its source has no id. Its other states are reference brackets.
    const projected = e.ownerDocument.querySelector(".lf-visual-mark-focus");
    if (projected?.checkVisibility({ visibilityProperty: true })) overlaid(projected);
    // Tabs draw focus on their label inside the larger hit target.
    for (const child of e.querySelectorAll("*"))
      if (child.checkVisibility({ visibilityProperty: true, opacityProperty: true })) {
        if (ringed(getComputedStyle(child))) carriers.push([child, null]);
        overlaid(child);
      }
    // A diff's scroller gives its ring to the following frame so its rows cannot
    // paint over the band. The frame is outside the focused node's ancestry.
    const frame = e.nextElementSibling;
    if (frame?.matches(".lf-diff-frame") && ringed(getComputedStyle(frame)))
      carriers.push([frame, null]);
    for (let el = flatParent(e); el; el = flatParent(el)) {
      const up = getComputedStyle(el);
      if (up.outlineStyle === "auto") return null;
      if (ringed(up)) carriers.push([el, null]);
      overlaid(el);
    }
    const cls =
      typeof e.className === "string" && e.className.trim()
        ? "." + e.className.trim().split(/\s+/).join(".")
        : "";
    const lost =
      e.tagName.toLowerCase() +
      (e.id ? "#" + e.id : "") +
      cls +
      " [outline " +
      cs.outlineStyle +
      ", shadow " +
      cs.boxShadow +
      "]";
    stash(carriers.map(([el]) => el));
    return { lost, carriers: carriers.map(([, pseudo]) => pseudo) };
  }

  return {
    ringCandidates,
    ringsDrawn,
    newStop,
    seenStop,
  };
};
