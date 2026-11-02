// Aim readings: how large a target each control offers a pointer. Both sweeps read one
// control's aim the same way and differ only in which controls they stand in front of.
(() => {
  // The element a press at a point lands on, through every shadow tree it crosses: a
  // press on a control's own pseudo-element lands on the control.
  function pressed(x, y) {
    let at = document.elementFromPoint(x, y);
    while (at?.shadowRoot) {
      const inner = at.shadowRoot.elementFromPoint(x, y);
      if (!inner || inner === at) break;
      at = inner;
    }
    return at;
  }
  const takes = (el, x, y) => {
    for (let at = pressed(x, y); at; at = at.parentNode || at.host)
      if (at === el) return true;
    return false;
  };
  // Whether a press at a point lands on another control lying over this one, its face
  // or its reach.
  const PRESS = 'button, a[href], summary, [role="button"], [data-lf-offer]';
  const FIELD =
    'input, textarea, select, leaf-text, [contenteditable=""], [contenteditable="true"]';
  const closestAcross = (at, sel) => {
    for (; at; at = at.parentNode || at.host)
      if (at.nodeType === 1 && at.matches(sel)) return at;
    return null;
  };
  // The chrome stands over the page, and an open popover or dialog over everything, so
  // a press of theirs over a control's edge is theirs to take; a page control over a
  // page control, or chrome over chrome, is one control lying over another.
  const TOP = ":popover-open, dialog[open]";
  const overlay = (el, over) =>
    !!closestAcross(over, ".lf-chrome") !== !!closestAcross(el, ".lf-chrome") ||
    closestAcross(over, TOP) !== closestAcross(el, TOP);
  const reachedBy = (el, x, y) => {
    for (let at = pressed(x, y); at; at = at.parentNode || at.host) {
      if (at === el) return false;
      if (at.nodeType !== 1 || !at.matches(PRESS)) continue;
      return !overlay(el, at);
    }
    return false;
  };
  // Where a press on a control is judged. A part of a control outside a scroller's view
  // is reached by scrolling it there, as a part outside the window is reached by
  // scrolling the page, so a press is judged only inside the view of every scroller that
  // holds the control: its scrollport, less the `scroll-padding` it keeps for what
  // stands over its edges on each side it can still scroll toward, such as a tab
  // strip's paging edge or a page's sticky header.
  function viewOf(el) {
    const root = document.scrollingElement;
    let [left, top, right, bottom] = [0, 0, innerWidth, innerHeight];
    const up = (at) => at.assignedSlot || at.parentNode || at.host;
    for (let at = up(el); at; at = up(at)) {
      if (at.nodeType !== 1) continue;
      const overX = at.scrollWidth - at.clientWidth;
      const overY = at.scrollHeight - at.clientHeight;
      if (overX < 1 && overY < 1) continue;
      const style = getComputedStyle(at);
      const box = at === root ? new DOMRect() : at.getBoundingClientRect();
      const [x0, y0] = [box.left + at.clientLeft, box.top + at.clientTop];
      const pad = (side, size) => {
        const value = style[`scrollPadding${side}`];
        return (parseFloat(value) || 0) * (value.endsWith("%") ? size / 100 : 1);
      };
      if (overX >= 1 && /auto|scroll/.test(style.overflowX)) {
        const before =
          style.direction === "rtl" ? overX + at.scrollLeft : at.scrollLeft;
        left = Math.max(left, x0 + (before >= 1 ? pad("Left", at.clientWidth) : 0));
        right = Math.min(
          right,
          x0 +
            at.clientWidth -
            (overX - before >= 1 ? pad("Right", at.clientWidth) : 0),
        );
      }
      if (overY >= 1 && /auto|scroll/.test(style.overflowY)) {
        const before = at.scrollTop;
        top = Math.max(top, y0 + (before >= 1 ? pad("Top", at.clientHeight) : 0));
        bottom = Math.min(
          bottom,
          y0 +
            at.clientHeight -
            (overY - before >= 1 ? pad("Bottom", at.clientHeight) : 0),
        );
      }
    }
    return { left, top, right, bottom };
  }
  // Whether a reach that takes a press at a point lies over a field there, which then
  // loses that press: a control's reach is for room nothing else uses. What would take
  // the press without the reach is the first box beneath the control, so a field a
  // surface already covers, as the panel covers the page, loses nothing to it. A
  // field's own action, standing in the field's box as Send does, is the field's to
  // place, and its reach over the room the field keeps for it is not judged here.
  const overField = (el, x, y) => {
    const face = el.getBoundingClientRect();
    const [cx, cy] = [face.left + face.width / 2, face.top + face.height / 2];
    const beneath = document.elementsFromPoint(x, y).find((at) => !el.contains(at));
    const field = beneath && closestAcross(beneath, FIELD);
    if (!field || field === el || el.contains(field) || field.contains(el))
      return false;
    const b = field.getBoundingClientRect();
    return !(cx >= b.left && cx <= b.right && cy >= b.top && cy <= b.bottom);
  };
  // Whether a press at the end of a control's reach misses it because the reach is cut
  // short: clipped by a box that holds the control, so the press lands on that box, or
  // covered by another control. A press that lands on something else drawn over the
  // spot, such as the panel's words over the page, is that surface's to take.
  const cut = (el, x, y) => {
    if (takes(el, x, y)) return false;
    const at = pressed(x, y);
    if (!at) return true;
    if (overlay(el, at)) return false;
    for (let up = el.parentNode || el.host; up; up = up.parentNode || up.host)
      if (up === at) return true;
    for (let up = at; up; up = up.parentNode || up.host)
      if (up.nodeType === 1 && up.matches(PRESS)) return true;
    return false;
  };
  // The element a press must land on to act. A control whose press is a shadow button,
  // as Web Awesome's copy button runs on its `button` part, acts only on that button: a
  // press that stops at the host runs nothing.
  const actionable = (el) => el.shadowRoot?.querySelector('[part~="button"]') ?? el;
  // What a press that missed the control landed on, for the finding to name.
  const landed = (x, y) => {
    const at = pressed(x, y);
    if (!at) return "nothing";
    const cls =
      typeof at.className === "string" ? at.className.trim().split(/\s+/)[0] : "";
    return cls ? `.${cls}` : at.localName;
  };

  // A control's aim is its box together with any absolutely positioned pseudo it hangs
  // that takes presses, its reach (surfaces.css), because a control enlarges its target
  // outside layout rather than make the visible line or row taller. A reach only counts
  // as far as a press there lands on the control: a box that clips it, or a neighbour
  // standing over it, cuts it short, which its computed size would not show. So where
  // the control is in view (`viewOf`), each end of its reach is pressed, and a reach
  // either end of which lands elsewhere counts for nothing; a control out of view keeps
  // its computed reach, unpressed. With a finite floor, only a central box of that
  // size must be clear; without one, the whole face is checked.
  function aim(control, floor = Infinity) {
    const el = actionable(control);
    const box = el.getBoundingClientRect();
    let [w, h] = [box.width, box.height];
    let [x, y] = [box.left + w / 2, box.top + h / 2];
    for (const pseudo of ["::before", "::after"]) {
      const at = getComputedStyle(el, pseudo);
      if (at.content === "none" || at.position !== "absolute") continue;
      if (at.pointerEvents === "none") continue;
      const width = parseFloat(at.width) || 0;
      const height = parseFloat(at.height) || 0;
      // A static control's reach can fill an ancestor, as a command's fills its
      // row. Its centre is that containing block's, not the label's: on touch the
      // description stands below the label. Computed insets locate the reach;
      // keep the label's centre on axes where its face already meets the floor.
      const owner = getComputedStyle(el).position === "static" ? el.offsetParent : el;
      if (owner && (width > w || height > h)) {
        const origin = owner.getBoundingClientRect();
        if (width > w && box.width < floor)
          x =
            origin.left +
            owner.clientLeft -
            owner.scrollLeft +
            (parseFloat(at.left) || 0) +
            (parseFloat(at.marginLeft) || 0) +
            width / 2;
        if (height > h && box.height < floor)
          y =
            origin.top +
            owner.clientTop -
            owner.scrollTop +
            (parseFloat(at.top) || 0) +
            (parseFloat(at.marginTop) || 0) +
            height / 2;
      }
      w = Math.max(w, width);
      h = Math.max(h, height);
    }
    const view = viewOf(el);
    const shown = (px, py) =>
      px >= view.left && py >= view.top && px < view.right && py < view.bottom;
    // A host that takes the press at its button's very middle stands over all of the
    // button, as a reach of the host's own would.
    if (el !== control && shown(x, y) && pressed(x, y) === control)
      return { box, w: 0, h: 0, by: landed(x, y) };
    if (shown(x, y) && cut(el, x, y)) return { box, w: 0, h: 0, by: landed(x, y) };
    if (shown(x, y) && takes(el, x, y)) {
      // A minimum-size reading asks for a usable floor-sized box, not every
      // point of a wider face. A version row shares its end with Compare but
      // still offers a large independent target in the middle.
      const faceW = Math.min(box.width, floor);
      const faceH = Math.min(box.height, floor);
      const edges = [
        [y - faceH / 2 >= view.top, x, y - faceH / 2 + 1],
        [y + faceH / 2 <= view.bottom, x, y + faceH / 2 - 1],
        [x - faceW / 2 >= view.left, x - faceW / 2 + 1, y],
        [x + faceW / 2 <= view.right, x + faceW / 2 - 1, y],
      ]
        .filter(([inside]) => inside)
        .map(([, px, py]) => [px, py]);
      const over = edges.find(([px, py]) => reachedBy(el, px, py));
      if (over) return { box, w: 0, h: 0, by: landed(...over) };
      const [top, bottom] = [y - h / 2 + 1, y + h / 2 - 1];
      const [left, right] = [x - w / 2 + 1, x + w / 2 - 1];
      let by;
      if (h > box.height && shown(x, top) && shown(x, bottom)) {
        const end = [top, bottom].find((py) => cut(el, x, py));
        if (end !== undefined) [h, by] = [box.height, landed(x, end)];
        const field = [top, bottom].find(
          (py) => takes(el, x, py) && overField(el, x, py),
        );
        if (field !== undefined) return { box, w: 0, h: 0, by: "a field it lies over" };
      }
      if (w > box.width && shown(left, y) && shown(right, y)) {
        const end = [left, right].find((px) => cut(el, px, y));
        if (end !== undefined) [w, by] = [box.width, landed(end, y)];
        const field = [left, right].find(
          (px) => takes(el, px, y) && overField(el, px, y),
        );
        if (field !== undefined) return { box, w: 0, h: 0, by: "a field it lies over" };
      }
      return { box, w, h, by };
    }
    return { box, w, h };
  }

  // Every control the layer's floor rule names in `roots`, in each and every shadow tree
  // within, measured under whatever pointer the page is shown to. A box and not
  // checkVisibility(): the corpus renders much of itself inside content-visibility
  // sections, which this browser answers no for, and a control laid out inside one is a
  // control a user reaches by scrolling to it. Each control is held to the floor it
  // computes, as the floor rule holds it: a press that is one row of a stack of lines,
  // as a diff line's number is, has no room for a reach or a floor-tall face, and says
  // so by setting its own `--aim-floor` to 0px. Only the control's own declaration
  // lowers its floor; one it inherits from a container holds it to the document's, and
  // an aim another box covers to nothing is short under any floor.
  function flooredAims(roots, selectors) {
    const floor = parseFloat(
      getComputedStyle(document.documentElement).getPropertyValue("--aim-floor"),
    );
    const short = [];
    let seen = 0;
    const sweep = (root) => {
      for (const el of root.querySelectorAll(selectors)) {
        // An inactive tab's panel is `hidden`, its content skipped rather than laid
        // out, so the boxes it leaves are stale and press nothing.
        if (closestAcross(el.parentNode || el.host, "[hidden]")) continue;
        const shown = getComputedStyle(el);
        if (shown.visibility === "hidden" || shown.pointerEvents === "none") continue;
        const { box, w, h, by } = aim(el);
        if (!box.width || !box.height) continue;
        seen += 1;
        const own = parseFloat(shown.getPropertyValue("--aim-floor"));
        const parent = el.parentElement ?? el.getRootNode().host;
        const inherited =
          parent &&
          parseFloat(getComputedStyle(parent).getPropertyValue("--aim-floor")) === own;
        if (Math.min(w, h) < Math.max(inherited ? floor : own, 1) - 0.5)
          short.push(
            `${Math.round(w)}x${Math.round(h)} ${el.className || el.localName}${by ? ` under ${by}` : ""}` +
              ` in ${el.closest("[id]")?.id ?? el.getRootNode().host?.closest?.("[id]")?.id ?? "?"}`,
          );
      }
      for (const el of [root, ...root.querySelectorAll("*")])
        if (el.shadowRoot) sweep(el.shadowRoot);
    };
    for (const root of roots) sweep(root);
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
      if (!["pointer", "grab"].includes(getComputedStyle(actionable(el)).cursor))
        continue;
      // A box that takes no press is not an aim, however its cursor reads.
      if (style.pointerEvents === "none") continue;
      if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
        continue;
      if (style.display === "inline") continue;
      // The option mark is the one control held out, and it is a handover rather than an
      // exemption: its box is being rewritten alongside the group's pressable rule, and
      // this line goes with that change. It stands at 11x11 today.
      if (el.classList.contains("lf-pick")) continue;
      const { box, w, h, by } = aim(el, floor);
      if (!box.width || !box.height) continue;
      const name =
        (el.className || el.tagName).toString().trim().split(/\s+/)[0] +
        ` ${JSON.stringify((el.textContent || "").trim().slice(0, 32))}`;
      if (Math.min(w, h) < floor - 0.5)
        found.push(
          `${name} at ${w.toFixed(1)}x${h.toFixed(1)}${by ? ` under ${by}` : ""}`,
        );
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
