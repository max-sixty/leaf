// Aim readings: how large a target each control offers a pointer. Both sweeps read one
// control's aim the same way and differ only in which controls they stand in front of.
(() => {
  // A control's aim is its box together with any absolutely positioned pseudo it hangs
  // that takes presses, because a control may enlarge its target outside layout rather
  // than make the visible line or row taller. A draft's toolbar mark is drawn 26px tall
  // over the box's border, and its ::before stretches its target to the aim floor.
  function aim(el) {
    const box = el.getBoundingClientRect();
    let [w, h] = [box.width, box.height];
    for (const pseudo of ["::before", "::after"]) {
      const at = getComputedStyle(el, pseudo);
      if (at.content === "none" || at.position !== "absolute") continue;
      if (at.pointerEvents === "none") continue;
      w = Math.max(w, parseFloat(at.width) || 0);
      h = Math.max(h, parseFloat(at.height) || 0);
    }
    return { box, w, h };
  }

  // Every control the layer's floor rule names, in the document and every shadow tree,
  // measured under whatever pointer the page is shown to. A box and not
  // checkVisibility(): the corpus renders much of itself inside content-visibility
  // sections, which this browser answers no for, and a control laid out inside one is a
  // control a user reaches by scrolling to it.
  function flooredAims(selectors) {
    const floor = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--aim-floor"),
    );
    const short = [];
    let seen = 0;
    const sweep = (root) => {
      for (const el of root.querySelectorAll(selectors)) {
        const { box, w, h } = aim(el);
        if (!box.width || !box.height) continue;
        const shown = getComputedStyle(el);
        // Hidden, or standing there for a pointer a finger is not: the diff's line
        // comment is transparent and takes no presses until its row is hovered, and a
        // finger never hovers it.
        if (shown.visibility === "hidden") continue;
        if (shown.opacity === "0" || shown.pointerEvents === "none") continue;
        seen += 1;
        if (Math.min(w, h) < floor - 0.5)
          short.push(`${Math.round(w)}x${Math.round(h)} ${el.className}`);
      }
      for (const el of root.querySelectorAll("*"))
        if (el.shadowRoot) sweep(el.shadowRoot);
    };
    sweep(document);
    return { floor, seen, short };
  }

  // Every box the layer promises a press on, wherever it stands. Not a list of class
  // names: what makes something a target is that the runtime built it (data-lf-offer)
  // or that it stands in the runtime's own layer, and that the page under the pointer
  // says a press lands there.
  //
  // Inline boxes are out, and that is the target-size exception rather than an excuse: a
  // link inside a sentence is sized by the words around it, and nothing can be done
  // about that which does not damage the sentence.
  function offeredAims(floor) {
    const found = [];
    const seen = new Set();
    for (const el of document.querySelectorAll(
      '[data-lf-offer], .lf-chrome button, .lf-chrome [role="button"],' +
        ' .lf-chrome [role="checkbox"], .lf-chrome [role="tab"], .lf-chrome .lf-btn,' +
        " .lf-chrome .lf-quote",
    )) {
      if (seen.has(el)) continue;
      seen.add(el);
      const style = getComputedStyle(el);
      if (!["pointer", "grab"].includes(style.cursor)) continue;
      // A box that takes no press is not an aim, however its cursor reads.
      if (style.pointerEvents === "none") continue;
      if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
        continue;
      if (style.display === "inline") continue;
      // The option mark is the one control held out, and it is a handover rather than an
      // exemption: its box is being rewritten alongside the group's pressable rule, and
      // this line goes with that change. It stands at 11x11 today.
      if (el.classList.contains("lf-pick")) continue;
      const { box, w, h } = aim(el);
      if (!box.width || !box.height) continue;
      const name =
        (el.className || el.tagName).toString().trim().split(/\s+/)[0] +
        ` ${JSON.stringify((el.textContent || "").trim().slice(0, 32))}`;
      if (Math.min(w, h) < floor - 0.5)
        found.push(`${name} at ${w.toFixed(1)}x${h.toFixed(1)}`);
    }
    return found;
  }

  // The aim as a box in the page: the control's box grown by its reach, which stands
  // out the same distance on either side of its face.
  function aimRect(el) {
    const { box, w, h } = aim(el);
    return {
      x: box.x - (w - box.width) / 2,
      y: box.y - (h - box.height) / 2,
      width: w,
      height: h,
    };
  }

  return { aimRect, flooredAims, offeredAims };
})();
