/* How a floating box follows a change of its layout: the floating panel's one model of
 * motion (floating-panel.js, `followBox`), whatever made the change, a line the field
 * gained, more room, a view opening, the box folding to its leaf.
 *
 * The layout changes in one step, so nothing a press aims at waits on a tween, and what
 * the user sees then travels from where it was drawn to where it now stands, every part
 * on one shared tween:
 *
 * - The box's outline is drawn by its surface, layers of their own behind it cut to
 *   the outline, so the outline moves by its cut from where it was drawn to where it
 *   stands. A ring a part of the box wears, such as the field's focus ring, is drawn
 *   there too while it moves (`ring`), since no transform draws a box changing size.
 * - A part that kept its size is carried: drawn where it stood, and moved by a
 *   transform to where it stands.
 * - A part that changed size and holds parts of its own leaves each of them to these
 *   rules. If it paints, a face or a ring, that grows from where it stood with it: a
 *   ring drawn by the surface, a face by cutting the part to its outline growing,
 *   unless the part holds something placed against the window, which any cut on it
 *   would cut too.
 * - A part that changed size and holds only its own content, such as words, carries
 *   that content by its start corner, cut to its outline growing from where it stood.
 *   An editor carries its words inside its own box (`--lf-field-carry`,
 *   `--lf-field-cut`, composing/text-field.js), since a transform on the editor would
 *   move the field under the user's typing. That box cuts its words off at its edges,
 *   so where the editor's start moved up or back, as more room re-wrapping a paragraph
 *   moves it, the editor is carried whole instead, unless the user is typing in it,
 *   when the words show where they now stand. A part that scrolls and changed size shows
 *   what its scroll puts in it, which the reader landing in it measures mid-tween, so
 *   it only grows from where it stood; one that kept its size is carried.
 * - A part new to the box is revealed: cut to the frame it stands in, the surface or
 *   the part holding it, as that frame's edges reach it, and still new while that
 *   lasts. A side where it stands out of its frame, as the attachments hanging over the
 *   box's top do, is cut only at its own edge. A part carried past it in that frame
 *   cuts it too, so it comes out from behind that part, as the field does behind the
 *   leaf leaving the corner, rather than showing under it.
 *
 * Whose change it is decides what travels. The user's own change, a key, a press or
 * typing, owns what it sets going until that rendering settles, and carries what it
 * moved, so the eye follows it. News, such as an answer arriving, moves nothing the
 * reader reads (assets/AGENTS.md, "Stability"): each part it moved shows where it now
 * stands, revealed by the frame it stands in or growing from its own old box, while
 * the box's outline and ring still follow.
 *
 * A change arriving during the tween starts each part from where it is drawn then;
 * news arriving while the user's change still carries parts shows them where they now
 * stand. A part placed against the window, as the attachment shelf is, moves with no
 * ancestor's transform, so a part holding one is never carried whole: its parts are
 * placed one by one. The motion is presentation only: each part's layout is where it
 * stands from the change on, and a part's motion ends with the tween, so nothing it
 * leaves behind needs undoing.
 *
 * The platform's own way to move a layout change, a view transition, draws the old
 * state as a picture, sends every press to the root while it runs, and abandons a
 * running one when the next change starts, as each keystroke would; here every part
 * stays live and pressable, which takes reading where each was drawn. */
import { keeps } from "./keeps.js";
import { TEXT_FIELD } from "./control-selectors.js";
import { nextRender } from "./rendering.js";

const near = (a, b) => Math.abs(a - b) < 0.5;
const boxOf = (rect) => ({
  left: rect.left,
  top: rect.top,
  right: rect.right,
  bottom: rect.bottom,
});
const width = (box) => box.right - box.left;
const height = (box) => box.bottom - box.top;
const same = (a, b) =>
  ["left", "top", "right", "bottom"].every((side) => near(a[side], b[side]));
const between = (from, to, progress) =>
  Object.fromEntries(
    Object.keys(to).map((side) => [
      side,
      from[side] + (to[side] - from[side]) * progress,
    ]),
  );
const shifted = (box, dx, dy) => ({
  left: box.left + dx,
  top: box.top + dy,
  right: box.right + dx,
  bottom: box.bottom + dy,
});
const insetOf = ([top, right, bottom, left], radius = 0) =>
  `inset(${top}px ${right}px ${bottom}px ${left}px round ${radius}px)`;
const radiusOf = (style) => Number.parseFloat(style.borderTopLeftRadius) || 0;
const paints = (style) =>
  !/^(transparent|rgba\(.*,\s*0\))$/.test(style.backgroundColor) ||
  style.backgroundImage !== "none" ||
  style.boxShadow !== "none" ||
  ["Top", "Right", "Bottom", "Left"].some(
    (side) => Number.parseFloat(style[`border${side}Width`]) > 0,
  );
const rings = (style) =>
  style.outlineStyle !== "none" && Number.parseFloat(style.outlineWidth) > 0;

// root: the element whose parts move, the box among them. box: the part the surface
// draws. room: the surface's layer, fixed over the whole window, against which its
// cuts are measured. surface(): each layer drawing the box, with how far past the
// outline it reaches. ring: the two layers that draw a part's ring, a ring and a fill
// inside it. observer: reads the box again when any part changes size. theirs():
// whose change is being read, "typing" or "press" for the user's own, null for news.
export function boxMotion({
  root,
  box,
  room,
  surface,
  ring: [ringLayer, ringFill],
  observer,
  theirs,
}) {
  // Each part's box as its layout placed it at the last reading, in the window.
  let rests = null;
  // Each part moving, from the box it was drawn at to its rest, on one clock.
  let motions = new Map();
  let running = [];
  let observed = new Set();
  // The parts read whole, whose insides no reading reads.
  let wholes = new WeakSet();
  const insideWhole = (node) => {
    for (let up = node.parentElement; up && up !== root; up = up.parentElement)
      if (wholes.has(up)) return true;
    return false;
  };

  // How far the parts carrying an element have it drawn from its rest now, it among
  // them, on the clock every motion shares.
  function carriedBy(progress) {
    const offsets = new Map();
    const offset = (carrier) => {
      if (!offsets.has(carrier)) {
        const { from, to } = motions.get(carrier);
        const now = between(from, to, progress);
        offsets.set(carrier, [now.left - to.left, now.top - to.top]);
      }
      return offsets.get(carrier);
    };
    return (element) => {
      let dx = 0;
      let dy = 0;
      for (let up = element; up && up !== root; up = up.parentElement)
        if (motions.get(up)?.carries) {
          const [x, y] = offset(up);
          dx += x;
          dy += y;
        }
      return [dx, dy];
    };
  }

  // A part, with its box as its layout places it and what decides how it moves.
  function read(element, into, carried) {
    const style = getComputedStyle(element);
    if (style.display === "contents") {
      for (const child of element.children) read(child, into, carried);
      return;
    }
    if (!element.checkVisibility()) return;
    const [dx, dy] = carried(element);
    const part = {
      element,
      style,
      box: shifted(boxOf(element.getBoundingClientRect()), -dx, -dy),
      window: style.position === "fixed",
      parts: [],
    };
    part.scrolls = /auto|scroll/.test(`${style.overflowX} ${style.overflowY}`);
    part.whole =
      element.localName.includes("-") ||
      element instanceof SVGElement ||
      part.scrolls ||
      element.childElementCount === 0 ||
      [...element.childNodes].some(
        (node) => node.nodeType === Node.TEXT_NODE && node.data.trim(),
      );
    if (!part.whole)
      for (const child of element.children) read(child, part.parts, carried);
    part.holdsWindow = part.parts.some((inner) => inner.window || inner.holdsWindow);
    if (part.whole) wholes.add(element);
    into.push(part);
  }

  // Where each part of the last reading is drawn now, mid-tween or at rest: its own
  // motion's box, or its rest moved as far as the parts carrying it are. A part still
  // being revealed has none: it is still new.
  function drawn(progress, carried) {
    const at = new Map();
    for (const [element, rest] of rests) {
      const motion = motions.get(element);
      if (motion?.revealed && progress < 1) continue;
      at.set(
        element,
        motion
          ? between(motion.from, motion.to, progress)
          : shifted(rest, ...carried(element)),
      );
    }
    return at;
  }

  // The observer reads the box again when any part read changes size, and reads a part
  // it starts observing, so a part arriving without moving any part already read, as an
  // attachment hung over the box does, is read at once, and the next change carries it
  // from where it shows. Observing starts in the next frame, since a part observed
  // while the observer delivers would be read in that same delivery, which the browser
  // reports as a loop.
  const arrived = new Set();
  let watching = 0;
  const watch = () => {
    watching ||= nextRender(() => {
      watching = 0;
      const parts = new Set([box, ...(rests?.keys() ?? []), ...arrived]);
      arrived.clear();
      for (const element of observed)
        if (!parts.has(element)) observer.unobserve(element);
      for (const element of parts)
        if (!observed.has(element)) observer.observe(element);
      observed = parts;
    });
  };
  new MutationObserver((records) => {
    for (const record of records)
      for (const node of record.type === "childList"
        ? record.addedNodes
        : [record.target])
        if (node instanceof Element && !insideWhole(node)) arrived.add(node);
    watch();
  }).observe(root, { subtree: true, childList: true, attributeFilter: ["hidden"] });

  function follow(timing) {
    const progress = running[0]?.effect.getComputedTiming().progress ?? 1;
    const carried = carriedBy(progress);
    const parts = [];
    wholes = new WeakSet();
    read(root, parts, carried);
    const next = new Map();
    const note = (part) => {
      next.set(part.element, part.box);
      part.parts.forEach(note);
    };
    parts.forEach(note);
    watch();
    // Nothing's layout changed, as when the observer reads a part it starts observing:
    // whatever moves keeps moving.
    if (
      rests?.size === next.size &&
      [...next].every(
        ([element, at]) => rests.has(element) && same(rests.get(element), at),
      )
    )
      return;
    for (const animation of running) animation.cancel();
    running = [];
    // A box not drawn at all, as in print, has nothing to move, and its next reading
    // takes it as it stands.
    if (!next.has(box)) {
      rests = null;
      motions = new Map();
      return;
    }
    const was = timing && rests ? drawn(progress, carried) : null;
    const gesture = theirs();
    // A part holding parts of its own that was growing is drawn at a size of its own,
    // so its parts are placed again from where each is drawn.
    const framed = new Set(
      [...motions].filter(([, motion]) => motion.frames).map(([element]) => element),
    );
    const before = rests;
    motions = new Map();
    rests = next;

    const space = boxOf(room.getBoundingClientRect());
    const outline = (at, grow, radius) =>
      insetOf(
        [
          at.top - space.top - grow,
          space.right - at.right - grow,
          space.bottom - at.bottom - grow,
          at.left - space.left - grow,
        ],
        radius + grow,
      );
    const boxAt = rests.get(box);
    const boxRadius = radiusOf(getComputedStyle(box));
    for (const [layer, reach] of surface())
      keeps(layer, "style", `clip-path: ${outline(boxAt, reach, boxRadius)}`);
    if (!was?.has(box)) return;
    const boxFrom = was.get(box);

    const rtl = getComputedStyle(box).direction === "rtl";
    const start = (element, keyframes) =>
      running.push(element.animate(keyframes, timing));
    const hold = (element, property, value) =>
      start(element, [{ [property]: value }, { [property]: value }]);
    const move = (element, dx, dy) =>
      start(element, [{ translate: `${dx}px ${dy}px` }, { translate: "0px 0px" }]);
    const cutFrom = (element, cut, radius = 0) =>
      start(element, [
        { clipPath: insetOf(cut, radius) },
        { clipPath: insetOf([0, 0, 0, 0], radius) },
      ]);

    // Moved whole, from where it was drawn.
    function carry(part, from) {
      const dx = from.left - part.box.left;
      const dy = from.top - part.box.top;
      if (near(dx, 0) && near(dy, 0)) return;
      motions.set(part.element, { from, to: part.box, carries: true });
      move(part.element, dx, dy);
    }

    // Its content carried by its start corner, cut to its outline growing from where
    // it stood.
    function carryContent(part, from) {
      const to = part.box;
      if (part.scrolls && !part.element.matches(TEXT_FIELD)) return grow(part, from);
      let dx = rtl ? from.right - to.right : from.left - to.left;
      let dy = from.top - to.top;
      const end = Math.max(0, width(to) - width(from));
      const foot = Math.max(0, height(to) - height(from));
      const cut = rtl ? [0, 0, foot, end] : [0, end, foot, 0];
      // The editor's own box cuts its words off at its edges, so it carries them
      // inside itself only as far as that box holds them. Where its start moved up or
      // back, the editor is carried whole instead, unless the user is typing in it,
      // when a moving field would move under their typing.
      const editor = part.element.matches(TEXT_FIELD);
      const inside = (rtl ? dx <= 0 : dx >= 0) && dy >= 0;
      if (!editor || (!inside && gesture !== "typing")) {
        motions.set(part.element, { from, to, carries: true });
        move(part.element, dx, dy);
        cutFrom(part.element, cut);
        return;
      }
      motions.set(part.element, { from, to });
      dx = rtl ? Math.min(0, dx) : Math.max(0, dx);
      dy = Math.max(0, dy);
      start(part.element, [
        {
          "--lf-field-carry": `${dx}px ${dy}px`,
          "--lf-field-cut": cut.map((side) => `${side}px`).join(" "),
        },
        { "--lf-field-carry": "0px 0px", "--lf-field-cut": "0px 0px 0px 0px" },
      ]);
    }

    // Drawn where its layout puts it, cut to its outline growing from where it stood.
    function grow(part, from) {
      const to = part.box;
      motions.set(part.element, { from, to });
      cutFrom(
        part.element,
        [
          from.top - to.top,
          to.right - from.right,
          to.bottom - from.bottom,
          from.left - to.left,
        ].map((inset) => Math.max(0, inset)),
        radiusOf(part.style),
      );
    }

    // Cut to the frame it stands in as the frame's edges reach it, on every side but
    // one it stands out of, and to each carried part beside it in that frame as that
    // part passes, so it comes out from behind the part rather than under it.
    function reveal(part, frame, siblings) {
      const to = part.box;
      const side = (inset, beyond) => (beyond ? 0 : Math.max(0, inset));
      /** @type {[number, number, number, number]} */
      const from = [
        side(frame.from.top - to.top, to.top < frame.to.top - 0.5),
        side(to.right - frame.from.right, to.right > frame.to.right + 0.5),
        side(to.bottom - frame.from.bottom, to.bottom > frame.to.bottom + 0.5),
        side(frame.from.left - to.left, to.left < frame.to.left - 0.5),
      ];
      /** @type {[number, number, number, number]} */
      const end = [0, 0, 0, 0];
      const overlaps = (a, b, low, high) => a[low] < b[high] && b[low] < a[high];
      for (const sibling of siblings) {
        const motion = motions.get(sibling.element);
        if (!motion || motion.revealed) continue;
        const { from: then, to: at } = motion;
        const across = overlaps(at, to, "top", "bottom");
        const along = overlaps(at, to, "left", "right");
        // On each side the part stands beside it, how far in it reaches, then and at
        // rest.
        [
          along && { then: then.bottom - to.top, rest: at.bottom - to.top },
          across && { then: to.right - then.left, rest: to.right - at.left },
          along && { then: to.bottom - then.top, rest: to.bottom - at.top },
          across && { then: then.right - to.left, rest: at.right - to.left },
        ].forEach((reach, index) => {
          if (reach && reach.rest <= 0.5 && reach.then > from[index]) {
            from[index] = reach.then;
            end[index] = reach.rest;
          }
        });
      }
      if (from.every((inset) => near(inset, 0))) return;
      motions.set(part.element, { from: to, to, revealed: true });
      start(part.element, [{ clipPath: insetOf(from) }, { clipPath: insetOf(end) }]);
    }

    function place(part, frame, siblings = []) {
      const { element, style, box: to } = part;
      const from = was.get(element);
      if (!from) return reveal(part, frame, siblings);
      const rest = before.get(element);
      const sized =
        !framed.has(element) &&
        near(width(rest), width(to)) &&
        near(height(rest), height(to));
      let within = frame;
      if (element !== box && element !== root) {
        const carries = gesture !== null;
        if (sized && !part.holdsWindow)
          return carries ? carry(part, from) : reveal(part, frame, siblings);
        if (part.whole) return carries ? carryContent(part, from) : grow(part, from);
        if (!same(from, to)) within = { from, to };
        if (!sized && rings(style)) {
          // The surface draws the ring while it moves, in the ring's own colour.
          const reach =
            Number.parseFloat(style.outlineWidth) +
            Number.parseFloat(style.outlineOffset);
          const radius = radiusOf(style);
          keeps(ringLayer, "style", `background: ${style.outlineColor}`);
          hold(element, "outlineColor", "transparent");
          for (const [layer, grown] of [
            [ringLayer, reach],
            [ringFill, 0],
          ])
            start(layer, [
              { clipPath: outline(from, grown, radius) },
              { clipPath: outline(to, grown, radius) },
            ]);
        } else if (!sized && paints(style) && !part.holdsWindow) grow(part, from);
        if (!same(from, to)) motions.set(element, { from, to, frames: true });
      }
      // What carries is placed first, so what is new beside it is revealed from it.
      const placed = [...part.parts].sort(
        (a, b) => Number(!was.has(a.element)) - Number(!was.has(b.element)),
      );
      for (const inner of placed) place(inner, within, part.parts);
    }

    for (const part of parts) place(part, { from: boxFrom, to: boxAt });
    if (running.length === 0 && same(boxFrom, boxAt)) return;
    motions.set(box, { from: boxFrom, to: boxAt });
    for (const [layer, reach] of surface())
      start(layer, [
        { clipPath: outline(boxFrom, reach, boxRadius) },
        { clipPath: outline(boxAt, reach, boxRadius) },
      ]);
    // The box stands transparent over the surface's own fill while everything moves,
    // and lets what it carries stand past its rest outline on the way.
    hold(box, "backgroundColor", "transparent");
    hold(box, "overflow", "visible");
  }

  return {
    follow,
    // The window changed size: the next reading takes the box as it stands.
    forget() {
      rests = null;
    },
  };
}
