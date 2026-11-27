// Leaf's boxes against the frames they stand in and against each other, read in one
// page as it stands: the in-page half of `leaf_dev.geometry`, whose header says how
// `leaf-dev stills` compares two arms' readings.
//
// A box is an element Leaf draws whose own edge shows: a border, a ground unlike the
// one behind it, a picture, or a lifted shadow, and for the overlap reading a replaced
// element such as an image. A gradient is a mark drawn inside a box (a rule, a fade,
// stripes), not its edge, and a run of words' highlight takes its line's height, so
// neither makes a box. Leaf draws it where it is Leaf's chrome (`inChrome`), a widget's
// own control (`uiInside`), the inside of a widget's shadow tree, or wears an `lf-`
// name no idiom gives an author (`idioms`, the registry's class keys). Three kinds of
// box stand where something other than Leaf's placement puts them, and are not read:
// a part of a library's component (a shadow tree whose host is no element of Leaf's),
// whose own look Leaf keeps (root AGENTS.md, "Use dependencies"), and what that
// component places through its slots; a thumb, inside a slider or scrollbar or moved
// by a scroll timeline, which the rule lets stand anywhere on its track; and a box in
// a drawing, which owns its coordinates (`--lf-drawing`).
//
// Edges (browser/AGENTS.md, "A box inside a frame either meets its edge or stands
// clear of it"). A box's frame is the nearest box around it in the flat tree; one
// whose nearest box is the author's stands where the author put it, and is not read.
// A floating box's outline is the one its surface draws, a layer of rings and fills cut
// to the box (dom/box-motion.js, `.lf-box-ground`), so a box whose border box is a
// surface's ring is framed by that ring's fill and its rounding. Only the sides both
// the frame and the box show are read: a frame edged on one side has one edge. For each,
// and each rounded corner the box stands in, the clearance from the frame's inner edge
// is measured, around the arc at a corner. A side the box reaches through a scroller
// that scrolls on that axis moves with the scroll and is not read, and a box that fills
// its frame on every side is one box with it. A mark centred on the edge, as a count
// on a control's corner, stands on the frame rather than in it, and is not read either.
//   near       0 < clearance < --lf-clear: the box nearly meets the edge
//   round      a round mark (a circle) closer than --lf-clear, meeting it included
//   overhang   the box crosses the frame's edge where nothing clips it
//   cut        a clip between the box and its frame, the frame's own included, cuts a
//              pixel or more off it
//   rounded    the box meets a straight run of the edge with a rounded corner there
//
// Overlaps. Two innermost boxes of one surface (a mark, a picture, a control's face;
// a box holding others is their ground) whose shown parts cross by two pixels or more
// each way. A surface is what stands over the page on its own: a box placed against
// the window, one stuck to its scroller's edge, or the top layer, so a card over the
// page's words, a head stuck over the words it scrolls past and a menu over its trigger
// are each on a surface of their own. A box's shown part is what the clips around it
// leave in the window. A control's icon is its glyph, which its badges may stand over.
//
// Each finding names its kind, the box, its frame or the box it crosses, the side and
// the clearance in CSS pixels, negative where it crosses. `api` is the page's own check
// API, which geometry.py imports from the page's entry.
({ idioms, slack = 0.5, seam = 2 }, api) => {
  const authored = new Set(idioms);

  const parentOf = (el) =>
    el.assignedSlot ?? el.parentElement ?? el.getRootNode()?.host ?? null;
  const ancestors = function* (el) {
    for (let a = parentOf(el); a && a !== document.documentElement; a = parentOf(a))
      yield a;
  };
  const within = (node, outer) => {
    for (let a = node; a; a = parentOf(a)) if (a === outer) return true;
    return false;
  };
  // The runtime's answers where it exports them (`base/ui-marks.js`,
  // `dom/geometry.js`), and the same questions asked here of a runtime that doesn't.
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
      return { left, top, right: left + el.clientWidth, bottom: top + el.clientHeight };
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

  const leafTag = (el) => /^(lf|leaf)-/.test(el.localName);
  const drawnByLeaf = (el) => {
    if (inChrome(el) || uiInside(el, null)) return true;
    const root = el.getRootNode();
    if (root instanceof ShadowRoot && root.host.localName.includes("-")) return true;
    if (el.localName.includes("-")) return true;
    return [...el.classList].some((c) => c.startsWith("lf-") && !authored.has(c));
  };
  // A part a library's component draws inside itself, whose look is the library's.
  const libraryPart = (el) => {
    const root = el.getRootNode();
    return root instanceof ShadowRoot && !leafTag(root.host);
  };
  // The library component that places `el`, through a slot of its own that `el` or a
  // box around it is assigned to, as a comparison stacks its two pictures.
  const placedBy = (el) => {
    for (let a = el; a; a = parentOf(a)) {
      const root = a.assignedSlot?.getRootNode();
      if (root instanceof ShadowRoot && !leafTag(root.host)) return root.host;
    }
    return null;
  };
  // A thumb, which moves along its track as its value changes: inside a slider or a
  // scrollbar, or moved by a scroll timeline, as an overview's window follows what its
  // scroller shows.
  const thumb = (el) => {
    if (nearest(el, "[role=slider], [role=scrollbar]")) return true;
    const timeline = cs(el).animationTimeline;
    return !!timeline && !["auto", "none"].includes(timeline);
  };
  const inDrawing = (el) => {
    const parent = parentOf(el);
    return !!parent && cs(parent).getPropertyValue("--lf-drawing").trim() === "1";
  };
  // A box the top layer lifts out of the boxes it is written in.
  const lifted = (el) => {
    try {
      return el.matches(":popover-open, dialog[open]");
    } catch {
      return el.matches("dialog[open]");
    }
  };

  const canvas = (() => {
    for (const el of [document.body, document.documentElement]) {
      const bg = el && cs(el).backgroundColor;
      if (bg && alpha(bg) > 0) return bg;
    }
    return "rgb(255, 255, 255)";
  })();
  // The ground behind an element: the nearest ground an ancestor paints.
  const groundBehind = (el) => {
    for (const a of ancestors(el)) {
      const bg = cs(a).backgroundColor;
      if (alpha(bg) > 0) return bg;
    }
    return canvas;
  };

  const SIDES = ["top", "right", "bottom", "left"];
  const Side = { top: "Top", right: "Right", bottom: "Bottom", left: "Left" };
  const CORNERS = [
    ["TopLeft", "top", "left"],
    ["TopRight", "top", "right"],
    ["BottomRight", "bottom", "right"],
    ["BottomLeft", "bottom", "left"],
  ];
  const axisOf = (side) => (side === "left" || side === "right" ? "x" : "y");
  const round1 = (n) => Math.round(n * 10) / 10;
  const near = (a, b) => Math.abs(a - b) <= 1;

  // Each surface's ring and fill as they stand: the rectangle and rounding each layer
  // is cut to (`inset(top right bottom left round r)` against the layer's own box). A
  // collapsed cut, as a surface at rest leaves its moving ring, draws nothing.
  const cutOf = (layer) => {
    const m = cs(layer).clipPath.match(/^inset\(([^)]*?)(?:\s+round\s+([^)]*))?\)$/);
    if (!m || m[1].includes("%")) return null;
    const [t, r = t, b = t, l = r] = m[1].trim().split(/\s+/).map(parseFloat);
    const box = layer.getBoundingClientRect();
    const radii = (m[2] ?? "0").split("/")[0].trim().split(/\s+/).map(parseFloat);
    const [r1, r2 = r1, r3 = r1, r4 = r2] = radii;
    return {
      top: box.top + t,
      right: box.right - r,
      bottom: box.bottom - b,
      left: box.left + l,
      radii: { TopLeft: r1, TopRight: r2, BottomRight: r3, BottomLeft: r4 },
    };
  };
  const surfaces = [...document.querySelectorAll(".lf-box-ground")]
    .map((ground) => {
      const [ring, fill] = ground.children;
      return ring && fill ? { ring: cutOf(ring), fill: cutOf(fill) } : null;
    })
    .filter((s) => s?.ring && s.fill);
  const surfaceDrawing = (rect) =>
    surfaces.find(
      ({ ring }) =>
        near(ring.left, rect.left) &&
        near(ring.right, rect.right) &&
        near(ring.top, rect.top) &&
        near(ring.bottom, rect.bottom),
    );

  const border = (s, side) => {
    const w = parseFloat(s[`border${Side[side]}Width`]) || 0;
    const shows =
      w > 0 &&
      !["none", "hidden"].includes(s[`border${Side[side]}Style`]) &&
      alpha(s[`border${Side[side]}Color`]) > 0;
    return { w, shows };
  };
  // A shadow that lifts the box or draws its hairline shows its whole edge; a ring's
  // band (no blur, wider than a hairline) is the focus ring's, read in rings.py.
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
  // Which sides of an element show as an edge, or null where none does.
  const edges = (el) => {
    const s = cs(el);
    if (s.display === "contents") return null;
    const ground =
      (alpha(s.backgroundColor) > 0 && differs(s.backgroundColor, groundBehind(el))) ||
      s.backgroundImage.includes("url(") ||
      shadowEdge(s) ||
      !!surfaceDrawing(el.getBoundingClientRect());
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
  // A frame's inner edge and the rounding of each inner corner: its surface's fill
  // where a surface draws it, else its padding box and its radii less its border.
  const inside = (frame) => {
    const fs = cs(frame);
    const fr = frame.getBoundingClientRect();
    const drawn = surfaceDrawing(fr);
    if (drawn) return drawn.fill;
    const radii = {};
    for (const [corner, v, h] of CORNERS)
      radii[corner] = Math.max(
        0,
        radius(fs, corner, fr) - Math.max(border(fs, v).w, border(fs, h).w),
      );
    return {
      top: fr.top + border(fs, "top").w,
      right: fr.right - border(fs, "right").w,
      bottom: fr.bottom - border(fs, "bottom").w,
      left: fr.left + border(fs, "left").w,
      radii,
    };
  };

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
  // The boxes that hold `el` as layout does, nearest first: the containing block of an
  // absolutely placed box, nothing past a box placed against the window.
  const holders = function* (el) {
    for (let a = el; a;) {
      const s = cs(a);
      if (s.position === "fixed") return;
      a = s.position === "absolute" ? containing(a) : parentOf(a);
      if (!a || a === document.documentElement) return;
      yield a;
    }
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
  const rectOf = (r) => [r.left, r.top, r.right - r.left, r.bottom - r.top].map(round1);

  const all = [];
  const walk = (root) => {
    for (const el of root.querySelectorAll("*")) {
      all.push(el);
      if (el.shadowRoot) walk(el.shadowRoot);
    }
  };
  walk(document);

  // A picture or a frame of content a box can cover. An icon is a control's glyph,
  // which the control's own badges may stand over.
  const REPLACED = new Set(["img", "video", "canvas", "iframe"]);
  const findings = [];
  const overlapping = [];
  for (const el of all) {
    if (el instanceof SVGElement && el.localName !== "svg") continue;
    if (!drawnByLeaf(el)) continue;
    if (!el.checkVisibility({ opacityProperty: true, visibilityProperty: true }))
      continue;
    const s = cs(el);
    if (s.display === "inline" || el.closest(".lf-box-ground")) continue;
    if (libraryPart(el) || thumb(el) || inDrawing(el)) continue;
    const own = edges(el);
    const rect = el.getBoundingClientRect();
    if (rect.width < 1 || rect.height < 1) continue;
    if (own || REPLACED.has(el.localName)) overlapping.push(el);
    if (!own || s.position === "fixed" || lifted(el)) continue;

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
      if (cs(a).position === "fixed" || lifted(a)) break;
      between.push(a);
    }
    if (!frame || !drawnByLeaf(frame) || libraryPart(frame)) continue;
    const fs = cs(frame);
    const fshown = edges(frame);
    const inner = inside(frame);
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
    // A box that fills its frame on every side, or stands on the outline its frame's
    // surface draws, is one box with it.
    const fr = frame.getBoundingClientRect();
    const outline = { top: fr.top, right: fr.right, bottom: fr.bottom, left: fr.left };
    if (
      SIDES.every((side) => Math.abs(gaps[side]) <= slack) ||
      SIDES.every((side) => Math.abs(rect[side] - outline[side]) <= slack)
    )
      continue;
    const moving = {
      x: between.some((a) => scrollsOn(a, "x")),
      y: between.some((a) => scrollsOn(a, "y")),
    };
    const clear =
      parseFloat(s.getPropertyValue("--lf-clear")) ||
      parseFloat(fs.getPropertyValue("--lf-clear")) ||
      4;
    const report = (kind, side, gap) =>
      findings.push({
        kind,
        side,
        gap: round1(gap),
        box: placed(el),
        frame: placed(frame),
        at: rectOf(rect),
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
        if (!own[side] || !clipsOn(a, axis) || scrollsOn(a, axis) || moving[axis])
          continue;
        if (past[side] >= 1 - 0.05 && !cut.has(side)) {
          cut.add(side);
          report("cut", side, -past[side]);
        }
      }
    }

    // A mark centred on the edge, its middle within a couple of pixels of it, stands
    // on the frame rather than in it.
    const seated = (gap, extent) => gap <= 2 - extent / 2;
    // Corners: the box's clearance around the frame's inner arc where it stands in
    // a rounded corner.
    const inCorner = new Set();
    for (const [corner, v, h] of CORNERS) {
      if (moving.x || moving.y) continue;
      const r = inner.radii[corner];
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
        // A frame, or a box around it, that clips to its rounding cuts the box to it,
        // which is the box taking the frame's corner (a pane clips to its rounding).
        const clipped = [frame, ...ancestors(frame)].some(
          (a) =>
            clipsOn(a, "x") &&
            clipsOn(a, "y") &&
            radius(cs(a), corner, a.getBoundingClientRect()) > 0,
        );
        if (!cut.has(v) && !cut.has(h) && !clipped)
          if (!seated(gap, Math.min(rect.width, rect.height)))
            report("overhang", corner, gap);
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
      const extent = axisOf(side) === "x" ? rect.width : rect.height;
      if (gap < -slack) {
        if (!cut.has(side) && !seated(gap, extent)) report("overhang", side, gap);
      } else if (isRound) {
        if (gap < clear - slack) report("round", side, gap);
      } else if (gap > slack && gap < clear - slack) {
        report("near", side, gap);
      } else if (Math.abs(gap) <= slack) {
        if (corners.some(([c]) => radius(s, c, rect) > 1)) report("rounded", side, gap);
      }
    }
  }

  // The surface a box stands on: the nearest box around it, itself included, that
  // stands over the page on its own.
  const surfaceOf = (el) => {
    for (let a = el; a && a !== document.documentElement; a = parentOf(a)) {
      const position = cs(a).position;
      if (position === "fixed" || position === "sticky" || lifted(a)) return a;
    }
    return document.documentElement;
  };
  // What of a box shows: its border box less what the clips around it cut off, in the
  // window.
  const shownOf = (el) => {
    const r = el.getBoundingClientRect();
    let shown = {
      left: Math.max(r.left, 0),
      top: Math.max(r.top, 0),
      right: Math.min(r.right, innerWidth),
      bottom: Math.min(r.bottom, innerHeight),
    };
    for (const a of holders(el)) {
      if (!clipsOn(a, "x") && !clipsOn(a, "y")) continue;
      const band = shownBand(a);
      if (!band) continue;
      shown = {
        left: clipsOn(a, "x") ? Math.max(shown.left, band.left) : shown.left,
        right: clipsOn(a, "x") ? Math.min(shown.right, band.right) : shown.right,
        top: clipsOn(a, "y") ? Math.max(shown.top, band.top) : shown.top,
        bottom: clipsOn(a, "y") ? Math.min(shown.bottom, band.bottom) : shown.bottom,
      };
    }
    return shown.right - shown.left >= 1 && shown.bottom - shown.top >= 1
      ? shown
      : null;
  };
  // Only the innermost boxes cross: a mark, a picture, a control's face. A box holding
  // others is the ground they stand on, as a card is its controls'.
  const holding = new Set();
  for (const el of overlapping)
    for (const a of ancestors(el)) {
      if (holding.has(a)) break;
      holding.add(a);
    }
  const bySurface = new Map();
  for (const el of overlapping) {
    if (holding.has(el)) continue;
    const shown = shownOf(el);
    if (!shown) continue;
    const surface = surfaceOf(el);
    if (!bySurface.has(surface)) bySurface.set(surface, []);
    bySurface.get(surface).push({ el, shown });
  }
  for (const boxes of bySurface.values())
    for (let i = 0; i < boxes.length; i++)
      for (let j = i + 1; j < boxes.length; j++) {
        const a = boxes[i],
          b = boxes[j];
        if (within(a.el, b.el) || within(b.el, a.el)) continue;
        const library = placedBy(a.el);
        if (library && library === placedBy(b.el)) continue;
        const across =
          Math.min(a.shown.right, b.shown.right) - Math.max(a.shown.left, b.shown.left);
        const down =
          Math.min(a.shown.bottom, b.shown.bottom) - Math.max(a.shown.top, b.shown.top);
        if (across < seam || down < seam) continue;
        const [first, second] = [a, b].sort((p, q) =>
          placed(p.el) < placed(q.el) ? -1 : 1,
        );
        const left = Math.max(a.shown.left, b.shown.left);
        const top = Math.max(a.shown.top, b.shown.top);
        findings.push({
          kind: "overlap",
          side: "",
          gap: -round1(Math.min(across, down)),
          box: placed(first.el),
          frame: placed(second.el),
          at: rectOf({ left, top, right: left + across, bottom: top + down }),
        });
      }
  return findings;
};
