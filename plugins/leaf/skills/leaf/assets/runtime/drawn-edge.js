export function createDrawnEdge({ el, keys, readerStore, stateStrip, syncLayout }) {
  // The step an arrow takes, in the column's own gutter: the smallest move that shows in a
  // page of prose.
  const EDGE_STEP = 24;
  /** A region held to one side of the window, and the boundary the reader draws it by.
   *
   * The page has two — the comment panel on the right, the tray panel on the left — and
   * they are the same furniture reflected, so this is one function rather than two
   * near-copies. What differs is what it is handed: which side the region is held to, the
   * width it stands at until the reader says otherwise, how narrow they may draw it, the
   * property the cascade reads the standing width from, the key their store keeps the choice
   * under, and one noun, which every surface that names the region says in its own sentence.
   * Nothing below differs, which is the point: the second edge cost a call rather than a
   * copy, and a third would too.
   *
   * The width the reader asked for and the width the region stands at are two facts rather
   * than one. A window too narrow to honour a choice does not un-make it, and widening that
   * window again is not a request to be told what the reader once said — so the choice is
   * kept and the standing width is derived from it. Everything reads `width`; nothing holds
   * the number.
   *
   * One width, and a handle for each region on that side: the left edge holds two trays one
   * at a time, and each wears the edge it is drawn by, because a handle outside them both
   * would not slide in with the tray it belongs to. They are handles onto one fact rather
   * than two facts — `state` is the one writer, and it says the same thing on every one.
   */
  return function drawnEdge({ side, noun, wide, min, prop, key, covering, when }) {
    // Whether the region stands over the page rather than beside it — the same fact as
    // which of the two rules that take the strip the page is under. Asked of the query
    // rather than stored, so no reader of it can hold an answer from a window that has gone.
    const over = matchMedia(covering);
    const handles = new Set();
    let chosen = wide;
    // What the window will allow. Beside the page, half of it, which is the bargain the
    // covering query already strikes for the default width — the page keeps at least what
    // the region takes — asked here of whatever width this reader chose. Over the page the
    // region takes nothing from it, so the only bound there is the window itself.
    const cap = () => document.documentElement.clientWidth / (over.matches ? 1 : 2);
    // The floor gives way to the cap and not the other way about: a window too narrow for
    // the floor is still the window, and a region wider than the one it stands in has put
    // its own controls off the screen. Asked in two places and written once — of a width the
    // reader is dragging to, so the edge never goes anywhere their hand did not, and of the
    // width they chose on some other day, whose window is not this one.
    const held = (want) => Math.min(cap(), Math.max(min, want));
    const width = () => held(chosen);
    // The one writer of the property the cascade reads that width from: the region's own box
    // and the strip the page yields are both stated against it. Written rather than read back
    // off the region because a closed one measures zero, which is exactly when the page most
    // needs to know how wide it will be. The runtime's own readers — the toast's corner, the
    // room a wide widget spends — ask `width` instead of this property, so what the cascade
    // lays out and what the runtime measures cannot come apart.
    function state() {
      document.documentElement.style.setProperty(prop, width() + "px");
      // Where the edge stands and how far it may go, which is what a listener hears change
      // on every step — the platform's own announcement, and the whole reason the edge is a
      // separator. The cap moves with the window, so it is restated wherever the width is.
      for (const handle of handles) {
        handle.setAttribute("aria-valuenow", String(Math.round(width())));
        handle.setAttribute("aria-valuemax", String(Math.round(cap())));
        // A boundary with no distance to travel is not a control. This happens to the
        // comment sheet at the supported 320px floor: leaving its separator in the tab
        // order promised a resize no pointer or arrow could make. Transfer a reader who
        // was standing on it before taking it away — the browser otherwise silently
        // drops focus to body during a rotation that closes the range.
        const fixed = cap() <= min;
        if (fixed && handle === document.activeElement)
          handle.lfFixedFocus().focus({ preventScroll: true });
        handle.hidden = fixed;
      }
    }
    // The reader's answer, taken and kept. Held to the window on the way in, because a drag
    // is direct: what they see is what they asked for, and storing a width the window
    // refused would hand it back to them on some later window as a place they never put the
    // edge.
    function set(want) {
      chosen = Math.round(held(want));
      readerStore.set(key, String(chosen));
      state();
      stateStrip();
      syncLayout();
    }
    /** The region's own edge, said as what it is: a separator between two regions, which is
     * the platform's word for a boundary the reader moves. That word is worth having for
     * what comes with it — the edge carries the width it stands at, so an arrow step is
     * announced by the platform itself, where a press built for the job would have had to say
     * so in words of its own and would have promised an activation an edge has not got.
     *
     * It goes in the region rather than beside it, so it travels with whatever the region
     * does: the tray panel's edge slides in with the tray standing on it, and a closed
     * region's edge is hidden by the same rule that hides the region.
     */
    function handle(region, fixedFocus) {
      const edge = el("div", "lf-ui lf-edge");
      // The owner names the control that survives when this edge has no range. Stored on
      // the handle because state walks all mirrored handles together, while the target is
      // each region's own — the comment panel closes, each tray returns to its toggle.
      edge.lfFixedFocus = fixedFocus;
      edge.dataset.lfSide = side;
      edge.setAttribute("role", "separator");
      edge.setAttribute("aria-orientation", "vertical");
      // The name a listener hears, and the one design mode shows under the pointer, where
      // it is cut at CONTROL_WORD_CAP — so the noun leads and the word for what is being
      // measured follows it, which is what keeps the longer of the two inside the cut.
      edge.setAttribute("aria-label", `${noun[0].toUpperCase()}${noun.slice(1)} width`);
      edge.setAttribute("aria-valuemin", String(min));
      edge.tabIndex = 0;
      // Where on the edge the reader took hold, kept for the length of the drag so the
      // boundary stays under the point they grabbed. Without it the region jumps by up to
      // the handle's own width on the first move, which is the page moving under an aim that
      // had just arrived.
      let grab = 0;
      edge.addEventListener("pointerdown", (event) => {
        // Refusing the press stops the compatibility mouse events, and with them the
        // selection a drag makes: without it a gesture about the edge would drop whatever the
        // reader had selected and paint a new one over the paragraphs it passed. Focus is
        // then taken by hand, refusing the press having refused that too, so the arrows are
        // live on the edge the reader is holding.
        event.preventDefault();
        edge.setPointerCapture(event.pointerId);
        const box = region.getBoundingClientRect();
        grab = event.clientX - (side === "right" ? box.left : box.right);
        edge.focus({ preventScroll: true });
        document.body.toggleAttribute("data-lf-sizing", true);
      });
      edge.addEventListener("pointermove", (event) => {
        if (!edge.hasPointerCapture(event.pointerId)) return;
        // The region's far edge is the window's, so the width is what the pointer leaves
        // between the two — read off the window rather than off the region, which is the box
        // this is about to resize.
        const at = event.clientX - grab;
        set(side === "right" ? document.documentElement.clientWidth - at : at);
      });
      // Both ends of the gesture, because a drag the browser takes away — a window losing the
      // pointer, a touch cancelled — leaves the page in the sizing posture otherwise, and the
      // slide would be gone for the rest of the session with nothing to say why.
      for (const ending of ["pointerup", "pointercancel"])
        edge.addEventListener(ending, () =>
          document.body.toggleAttribute("data-lf-sizing", false),
        );
      // Arrows, and not a pair of letters, because the reader is standing on the edge
      // itself — the direction is the whole of what they have left to say. Away from the
      // side the region is held to widens it, which is the same reading the pointer makes of
      // the same gesture.
      const wider = side === "right" ? "ArrowLeft" : "ArrowRight";
      keys(
        edge,
        `On the ${noun}'s edge`,
        [
          {
            id: "region.resize",
            keys: ["ArrowLeft", "ArrowRight"],
            routes: [
              {
                id: "region.resize-left",
                binding: "ArrowLeft",
                does: `Move the ${noun}'s edge left`,
              },
              {
                id: "region.resize-right",
                binding: "ArrowRight",
                does: `Move the ${noun}'s edge right`,
              },
            ],
            label: "arrows",
            does: `Resize the ${noun}`,
            line: `resize the ${noun}`,
            repeat: true,
            run: (binding) =>
              set(width() + (binding === wider ? EDGE_STEP : -EDGE_STEP)),
          },
        ],
        when,
      );
      handles.add(edge);
      region.prepend(edge);
      state();
      return edge;
    }
    // The reader's own answer, put back over the default at the foot of the module, where
    // every other remembered arrangement is restored. Stated whether or not they have chosen
    // one, since a reader who has said nothing is a reader whose answer is the default.
    function restore() {
      chosen = parseFloat(readerStore.get(key)) || wide;
      state();
    }
    return { width, state, restore, handle, key, over };
  };
}
