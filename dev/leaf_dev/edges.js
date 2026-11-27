// Leaf's boxes against the frames they stand in (browser/AGENTS.md, "A box inside a
// frame either meets its edge or stands clear of it"), read in one page as it stands.
//
// A box is an element Leaf draws whose own edge shows: a border, a ground unlike the
// one behind it, a picture, or a lifted shadow. A gradient is a mark drawn inside a
// box (a rule, a fade, stripes), not its edge, and a run of words' highlight takes
// its line's height, so neither makes a box. Leaf draws it where it is Leaf's chrome
// (`inChrome`), a widget's own control (`uiInside`), the inside of a widget's shadow
// tree, or wears an `lf-` name no idiom gives an author (`idioms`, the registry's
// class keys). Its frame is the nearest box around it in the flat tree; a box whose
// nearest box is the author's stands where the author put it, and is not read. Only
// the frame's sides that show are read: a frame edged on one side has one edge.
//
// For each side both the frame and the box show, and each rounded corner the box
// stands in, the box's clearance from the frame's inner edge (padding box, or border
// box where the frame has no border) is measured, around the arc at a corner. A side
// the box reaches through a scroller that scrolls on that axis is not read, since its
// distance moves with the scroll. A box that fills its frame on every side is one box
// with it. Then:
//   near       0 < clearance < --lf-clear: the box nearly meets the edge
//   round      a round mark (a circle) closer than --lf-clear, meeting it included
//   overhang   the box crosses the frame's edge where nothing clips it
//   seated     a mark centred on the edge, as a count on a control's corner, which
//              stands on the frame rather than in it, kept apart from the rest
//   cut        a clip between the box and its frame, the frame's own included, cuts a
//              pixel or more off it
//   rounded    the box meets a straight run of the edge with a rounded corner there
// Each finding names the box, its frame, the side and the clearance in CSS pixels.
async ({ idioms, slack = 0.5 }) => {
  const api = await import("/runtime/check-api.js");
  const authored = new Set(idioms);

  const parentOf = (el) =>
    el.assignedSlot ?? el.parentElement ?? el.getRootNode()?.host ?? null;
  const ancestors = function* (el) {
    for (let a = parentOf(el); a && a !== document.documentElement; a = parentOf(a))
      yield a;
  };
  // The runtime's answers where it exports them (`base/ui-marks.js`,
  // `dom/geometry.js`), and the same questions asked here for an older runtime.
  const nearest = (el, selector) => {
    for (let a = el; a; a = parentOf(a)) if (a.matches?.(selector)) return a;
    return null;
  };
  const inChrome = api.inChrome ?? ((el) => !!nearest(el, ".lf-chrome"));
  const uiInside =
    api.uiInside ??
    ((el) => {
      const near = nearest(el, ".lf-ui, [data-lf-said]");
      return !!near && !near.matches("[data-lf-said]");
    });
  const shownBand =
    api.shownBand ??
    ((el) => {
      const r = el.getBoundingClientRect();
      const left = r.left + el.clientLeft,
        top = r.top + el.clientTop;
      return {
        left,
        top,
        right: left + el.clientWidth,
        bottom: top + el.clientHeight,
      };
    });

  // A computed colour as sRGB channels and alpha, whatever notation the engine
  // serializes it in (`rgb()`, `color(srgb …)`, `oklab()` from a mix), read back
  // from a canvas pixel.
  const pixel = document.createElement("canvas").getContext("2d", {
    willReadFrequently: true,
  });
  const channels = new Map();
  const rgba = (colour) => {
    let c = channels.get(colour);
    if (!c) {
      pixel.clearRect(0, 0, 1, 1);
      pixel.fillStyle = "rgba(0, 0, 0, 0)";
      pixel.fillStyle = colour;
      pixel.fillRect(0, 0, 1, 1);
      const [r, g, b, a] = pixel.getImageData(0, 0, 1, 1).data;
      channels.set(colour, (c = { r, g, b, a: a / 255 }));
    }
    return c;
  };
  const alpha = (colour) => (!colour || colour === "transparent" ? 0 : rgba(colour).a);
  // Whether a ground laid over another shows as a colour of its own.
  const differs = (over, under) => {
    const o = rgba(over),
      u = rgba(under);
    return ["r", "g", "b"].some(
      (k) => Math.abs(o[k] * o.a + u[k] * (1 - o.a) - u[k]) > 2,
    );
  };
  const style = new Map();
  const cs = (el) => {
    let s = style.get(el);
    if (!s) style.set(el, (s = getComputedStyle(el)));
    return s;
  };

  const drawnByLeaf = (el) => {
    if (inChrome(el) || uiInside(el, null)) return true;
    const root = el.getRootNode();
    if (root instanceof ShadowRoot && root.host.localName.includes("-")) return true;
    if (/^(lf|wa)-/.test(el.localName)) return true;
    return [...el.classList].some((c) => c.startsWith("lf-") && !authored.has(c));
  };
  // A box the top layer lifts out of the boxes it is written in.
  const surface = (el) => {
    try {
      return el.matches(":popover-open, dialog[open]");
    } catch {
      return el.matches("dialog[open]");
    }
  };

  // The ground behind an element: the nearest ground an ancestor paints.
  const canvas = (() => {
    for (const el of [document.body, document.documentElement]) {
      const bg = el && cs(el).backgroundColor;
      if (bg && alpha(bg) > 0) return bg;
    }
    return "rgb(255, 255, 255)";
  })();
  const groundBehind = (el) => {
    for (const a of ancestors(el)) {
      const bg = cs(a).backgroundColor;
      if (alpha(bg) > 0) return bg;
    }
    return canvas;
  };

  const SIDES = ["top", "right", "bottom", "left"];
  const Side = { top: "Top", right: "Right", bottom: "Bottom", left: "Left" };
  const border = (s, side) => {
    const w = parseFloat(s[`border${Side[side]}Width`]) || 0;
    const shows =
      w > 0 &&
      !["none", "hidden"].includes(s[`border${Side[side]}Style`]) &&
      alpha(s[`border${Side[side]}Color`]) > 0;
    return { w, shows };
  };
  // A shadow that lifts the box or draws its hairline shows its whole edge; a ring's
  // band (no blur, wider than a hairline) is the ring sweep's, not an edge.
  const shadowEdge = (s) =>
    s.boxShadow !== "none" &&
    s.boxShadow.split(/,(?![^(]*\))/).some((layer) => {
      if (/(^|\s)inset(\s|$)/.test(layer)) return false;
      const lengths = (layer.match(/-?(?:\d*\.)?\d+px/g) || []).map(parseFloat);
      const colour = layer.replace(/-?(?:\d*\.)?\d+px/g, "").trim();
      if (alpha(colour) === 0) return false;
      const [, , blur = 0, spread = 0] = lengths;
      return blur > 0 || (spread > 0 && spread <= 1);
    });
  // A floating box whose outline its surface draws, a layer beside it holding the
  // ring and fill cut to the box's edge (dom/box-motion.js, `.lf-box-ground`): the box
  // paints a transparent border, and the ring shows through it.
  const surfaced = (el) =>
    [...(el.parentElement?.children ?? [])].some(
      (sibling) => sibling !== el && sibling.classList.contains("lf-box-ground"),
    );
  // Which sides of an element show as an edge, or null where none does.
  const edges = (el) => {
    const s = cs(el);
    if (s.display === "contents") return null;
    const ground =
      (alpha(s.backgroundColor) > 0 && differs(s.backgroundColor, groundBehind(el))) ||
      s.backgroundImage.includes("url(") ||
      shadowEdge(s) ||
      surfaced(el);
    const shown = {};
    let any = false;
    for (const side of SIDES) {
      shown[side] = ground || border(s, side).shows;
      any ||= shown[side];
    }
    return any ? shown : null;
  };

  const radius = (s, corner, rect) => {
    const v = s[`border${corner}Radius`].split(" ")[0];
    const r = v.endsWith("%")
      ? (parseFloat(v) / 100) * Math.min(rect.width, rect.height)
      : parseFloat(v) || 0;
    return Math.min(r, rect.width / 2, rect.height / 2);
  };
  const CORNERS = [
    ["TopLeft", "top", "left"],
    ["TopRight", "top", "right"],
    ["BottomRight", "bottom", "right"],
    ["BottomLeft", "bottom", "left"],
  ];
  const axisOf = (side) => (side === "left" || side === "right" ? "x" : "y");

  const scrollsOn = (a, axis) => {
    const s = cs(a);
    const overflow = axis === "x" ? s.overflowX : s.overflowY;
    if (!["auto", "scroll"].includes(overflow)) return false;
    return axis === "x"
      ? a.scrollWidth > a.clientWidth + 1
      : a.scrollHeight > a.clientHeight + 1;
  };
  const clipsOn = (a, axis) => {
    const s = cs(a);
    if (/paint|strict|content/.test(s.contain)) return true;
    return (axis === "x" ? s.overflowX : s.overflowY) !== "visible";
  };
  // The box an absolutely placed box hangs off, which with the boxes around it is all
  // that clips it: a static box it happens to be written inside clips it not at all.
  const containing = (el) => {
    for (const a of ancestors(el)) {
      const t = cs(a);
      if (
        t.position !== "static" ||
        t.transform !== "none" ||
        t.filter !== "none" ||
        /paint|layout|strict|content/.test(t.contain)
      )
        return a;
    }
    return null;
  };

  const short = (el) => {
    const names = [...el.classList].filter((c) => c.startsWith("lf-")).slice(0, 2);
    return el.localName + names.map((c) => `.${c}`).join("");
  };
  const placed = (el) => {
    const parts = [short(el)];
    for (const a of ancestors(el)) {
      if (parts.length >= 3) break;
      if (
        [...a.classList].some((c) => c.startsWith("lf-")) ||
        a.localName.includes("-")
      )
        parts.unshift(short(a));
    }
    return parts.join(" > ");
  };
  const round1 = (n) => Math.round(n * 10) / 10;
  // The element drawn at a point, through open shadow roots, and flat-tree descent.
  const hit = (x, y) => {
    let e = document.elementFromPoint(x, y);
    while (e?.shadowRoot) {
      const inner = e.shadowRoot.elementFromPoint(x, y);
      if (!inner || inner === e) break;
      e = inner;
    }
    return e;
  };
  const within = (node, outer) => {
    for (let a = node; a; a = parentOf(a)) if (a === outer) return true;
    return false;
  };

  const all = [];
  const walk = (root) => {
    for (const el of root.querySelectorAll("*")) {
      all.push(el);
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(document);

  const findings = [];
  let boxes = 0;
  for (const el of all) {
    if (el instanceof SVGElement && el.localName !== "svg") continue;
    if (!drawnByLeaf(el)) continue;
    if (!el.checkVisibility({ opacityProperty: true, visibilityProperty: true }))
      continue;
    const s = cs(el);
    if (s.position === "fixed" || surface(el)) continue;
    // A run of words' highlight takes the line's height, not a box's; a surface's
    // layers paint another box's outline; a drawing owns its own coordinates, as the
    // viewport it declares says (`--lf-drawing`, render-checks/layout.js).
    if (s.display === "inline" || el.closest(".lf-box-ground")) continue;
    const drawing = parentOf(el);
    if (drawing && cs(drawing).getPropertyValue("--lf-drawing").trim() === "1")
      continue;
    const own = edges(el);
    if (!own) continue;
    const rect = el.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) continue;
    const isRound =
      Math.abs(rect.width - rect.height) <= 1 &&
      CORNERS.every(([c]) => radius(s, c, rect) >= rect.width / 2 - slack);
    // The frame: the nearest box around this one. The boxes between say which axes
    // move with a scroll, and which clip.
    let frame = null;
    const between = [];
    for (const a of ancestors(el)) {
      if (edges(a)) {
        frame = a;
        break;
      }
      if (cs(a).position === "fixed" || surface(a)) break;
      between.push(a);
    }
    if (!frame || !drawnByLeaf(frame)) continue;
    const fs = cs(frame);
    const fr = frame.getBoundingClientRect();
    const fshown = edges(frame);
    const inner = {
      top: fr.top + border(fs, "top").w,
      right: fr.right - border(fs, "right").w,
      bottom: fr.bottom - border(fs, "bottom").w,
      left: fr.left + border(fs, "left").w,
    };
    // Not inside the frame at all, as a popover hung from a control is not.
    if (
      rect.right <= inner.left ||
      rect.left >= inner.right ||
      rect.bottom <= inner.top ||
      rect.top >= inner.bottom
    )
      continue;
    const gaps = {
      top: rect.top - inner.top,
      right: inner.right - rect.right,
      bottom: inner.bottom - rect.bottom,
      left: rect.left - inner.left,
    };
    // A box that fills its frame on every side is one box with it, as a field
    // filling the bar that lifts it is.
    if (SIDES.every((side) => Math.abs(gaps[side]) <= slack)) continue;
    boxes++;
    const moving = {
      x: between.some((a) => scrollsOn(a, "x")),
      y: between.some((a) => scrollsOn(a, "y")),
    };
    const clear =
      parseFloat(s.getPropertyValue("--lf-clear")) ||
      parseFloat(fs.getPropertyValue("--lf-clear")) ||
      4;
    // Whether something else is drawn over the box's middle, or it is off screen, so
    // a capture of this state wouldn't show it.
    const top = hit(rect.left + rect.width / 2, rect.top + rect.height / 2);
    const covered = !top || !(within(top, el) || within(el, top));
    const report = (kind, side, gap, extra = {}) =>
      findings.push({
        covered,
        kind,
        side,
        gap: round1(gap),
        box: placed(el),
        frame: placed(frame),
        at: [rect.left, rect.top, rect.width, rect.height].map(round1),
        frameAt: [fr.left, fr.top, fr.width, fr.height].map(round1),
        ...extra,
      });

    // Cuts: a clip between the box and its frame, the frame's own included. An
    // absolutely placed box is clipped only from its containing block out.
    const cut = new Set();
    const cb = s.position === "absolute" ? containing(el) : null;
    let reached = !cb;
    for (const a of [...between, frame]) {
      if (!reached && a !== cb) continue;
      reached = true;
      if (!clipsOn(a, "x") && !clipsOn(a, "y")) continue;
      const band = shownBand(a);
      if (!band) continue;
      const past = {
        top: band.top - rect.top,
        right: rect.right - band.right,
        bottom: rect.bottom - band.bottom,
        left: band.left - rect.left,
      };
      for (const side of SIDES) {
        const axis = axisOf(side);
        if (!own[side]) continue;
        if (!clipsOn(a, axis) || scrollsOn(a, axis) || moving[axis]) continue;
        if (past[side] >= 1 - 0.05 && !cut.has(side)) {
          cut.add(side);
          report("cut", side, -past[side], { clip: placed(a) });
        }
      }
    }

    // Corners: the box's clearance around the frame's inner arc where it stands in
    // a rounded corner.
    const inCorner = new Set();
    for (const [corner, v, h] of CORNERS) {
      if (moving.x || moving.y) continue;
      const R = radius(fs, corner, fr);
      const r = Math.max(0, R - Math.max(border(fs, v).w, border(fs, h).w));
      if (r < 1 || !fshown[v] || !fshown[h] || !own[v] || !own[h]) continue;
      const rb = isRound ? rect.width / 2 : radius(s, corner, rect);
      const cx = h === "left" ? inner.left + r : inner.right - r;
      const cy = v === "top" ? inner.top + r : inner.bottom - r;
      const bx = h === "left" ? rect.left + rb : rect.right - rb;
      const by = v === "top" ? rect.top + rb : rect.bottom - rb;
      const inArc =
        (h === "left" ? bx <= cx + slack : bx >= cx - slack) &&
        (v === "top" ? by <= cy + slack : by >= cy - slack);
      if (!inArc) continue;
      inCorner.add(corner);
      const gap = r - (Math.hypot(cx - bx, cy - by) + rb);
      if (gap < -slack) {
        // A frame that clips cuts the box to its own rounding, which is the box
        // taking the frame's corner (a pane clips to its rounding).
        if (!cut.has(v) && !cut.has(h) && !(clipsOn(frame, "x") && clipsOn(frame, "y")))
          report(
            gap <= 2 - Math.min(rect.width, rect.height) / 2 ? "seated" : "overhang",
            corner,
            gap,
          );
      } else if (gap < clear - slack && (isRound || gap > slack)) {
        report(isRound ? "round" : "near", corner, gap);
      }
    }

    for (const side of SIDES) {
      if (!fshown[side] || !own[side] || moving[axisOf(side)]) continue;
      // A side the box stands in a corner's arc beside is read at the corner.
      const corners = CORNERS.filter(([, v, h]) => v === side || h === side);
      if (corners.some(([c]) => inCorner.has(c))) continue;
      const gap = gaps[side];
      // A mark seated on the edge, its middle within a couple of pixels of it, as a
      // count stands on a control's corner or a stop on a rail, stands on the frame
      // rather than in it.
      const extent = axisOf(side) === "x" ? rect.width : rect.height;
      if (gap < -slack) {
        if (cut.has(side)) continue;
        report(gap <= 2 - extent / 2 ? "seated" : "overhang", side, gap);
      } else if (isRound) {
        if (gap < clear - slack) report("round", side, gap);
      } else if (gap > slack && gap < clear - slack) {
        report("near", side, gap);
      } else if (Math.abs(gap) <= slack) {
        const rounded = corners.filter(([c]) => radius(s, c, rect) > 1);
        if (rounded.length)
          report("rounded", side, gap, {
            corners: rounded.map(([c]) => c),
            radius: round1(radius(s, rounded[0][0], rect)),
          });
      }
    }
  }
  return { boxes, findings };
};
