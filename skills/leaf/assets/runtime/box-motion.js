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
 *   rules, and is itself cut to its outline growing from where it stood, which draws
 *   whatever it paints growing with it.
 * - A part that changed size and holds only its own content, such as words or a
 *   scrolling list, carries that content by its start corner, cut to its outline
 *   growing from where it stood. An editor carries its words inside its own box
 *   (`--lf-field-carry`, `--lf-field-cut`, composing/text-field.js), where a transform
 *   on the editor would move the field under the user's typing; words that box no
 *   longer holds where they stood show where they now stand.
 * - A part new to the box is revealed: cut to the frame it stands in, the surface or
 *   the part holding it, as that frame's edges reach it. A side where it stands out of
 *   its frame, as the attachments hanging over the box's top do, is left uncut.
 *
 * A change arriving during the tween starts from where everything is drawn then. A
 * part placed against the window, as the attachment shelf is, moves with no ancestor's
 * transform, so a part holding one is never carried whole: its parts are placed one by
 * one. The motion is presentation only: each part's layout is where it stands from the
 * change on, and a part's motion ends with the tween, so nothing it leaves behind needs
 * undoing. */
import { keeps } from "./keeps.js";
import { TEXT_FIELD } from "./control-selectors.js";

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
// inside it. observer: reads the box again when any part changes size.
export function boxMotion({
  root,
  box,
  room,
  surface,
  ring: [ringLayer, ringFill],
  observer,
}) {
  // Each part's box as its layout placed it at the last reading, in the window.
  let rests = null;
  // Each part moving, from the box it was drawn at to its rest, on one clock.
  let motions = new Map();
  let running = [];
  let observed = new Set();

  // A part, with its layout box and what decides how it moves.
  function read(element, into) {
    const style = getComputedStyle(element);
    if (style.display === "contents") {
      for (const child of element.children) read(child, into);
      return;
    }
    if (!element.checkVisibility()) return;
    const part = {
      element,
      style,
      box: boxOf(element.getBoundingClientRect()),
      window: style.position === "fixed",
      parts: [],
    };
    part.whole =
      element.localName.includes("-") ||
      element instanceof SVGElement ||
      /auto|scroll/.test(`${style.overflowX} ${style.overflowY}`) ||
      element.childElementCount === 0 ||
      [...element.childNodes].some(
        (node) => node.nodeType === Node.TEXT_NODE && node.data.trim(),
      );
    if (!part.whole) for (const child of element.children) read(child, part.parts);
    part.holdsWindow = part.parts.some((inner) => inner.window || inner.holdsWindow);
    into.push(part);
  }

  // Where each part of the last reading is drawn now, mid-tween or at rest: its own
  // motion's box, or its rest moved as far as a part carrying it is. A part still
  // being revealed has none: it is still new.
  function drawn() {
    const progress = running[0]?.effect.getComputedTiming().progress ?? 1;
    const offsets = new Map();
    const offset = (carrier) => {
      if (!offsets.has(carrier)) {
        const { from, to } = motions.get(carrier);
        const now = between(from, to, progress);
        offsets.set(carrier, [now.left - to.left, now.top - to.top]);
      }
      return offsets.get(carrier);
    };
    const at = new Map();
    for (const [element, rest] of rests) {
      const motion = motions.get(element);
      if (motion?.revealed && progress < 1) continue;
      let where = motion ? between(motion.from, motion.to, progress) : rest;
      for (let up = element.parentElement; up && up !== root; up = up.parentElement)
        if (motions.get(up)?.carries) where = shifted(where, ...offset(up));
      at.set(element, where);
    }
    return at;
  }

  // A part arriving without moving any part already read, as an attachment hung over
  // the box does, is read at once, so the next change carries it from where it shows.
  // The observer reads a part it starts observing.
  new MutationObserver((records) => {
    for (const record of records)
      for (const node of record.type === "childList"
        ? record.addedNodes
        : [record.target])
        if (node instanceof Element && !observed.has(node)) {
          observed.add(node);
          observer.observe(node);
        }
  }).observe(root, { subtree: true, childList: true, attributeFilter: ["hidden"] });

  function follow(timing) {
    const was = timing && rests ? drawn() : null;
    for (const animation of running) animation.cancel();
    running = [];
    motions = new Map();
    const parts = [];
    read(root, parts);
    rests = new Map();
    const note = (part) => {
      rests.set(part.element, part.box);
      part.parts.forEach(note);
    };
    parts.forEach(note);
    for (const element of observed)
      if (!rests.has(element)) observer.unobserve(element);
    for (const element of rests.keys())
      if (!observed.has(element)) observer.observe(element);
    observed = new Set(rests.keys());

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
    for (const [layer, grow] of surface())
      keeps(layer, "style", `clip-path: ${outline(boxAt, grow, boxRadius)}`);
    if (!was?.has(box)) return;
    const boxFrom = was.get(box);

    const rtl = getComputedStyle(box).direction === "rtl";
    const start = (element, keyframes) =>
      running.push(element.animate(keyframes, timing));
    const hold = (element, property, value) =>
      start(element, [{ [property]: value }, { [property]: value }]);
    const move = (element, dx, dy) =>
      start(element, [
        { translate: `${dx}px ${dy}px`, composite: "add" },
        { translate: "0px 0px", composite: "add" },
      ]);
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
      let dx = rtl ? from.right - to.right : from.left - to.left;
      let dy = from.top - to.top;
      const end = Math.max(0, width(to) - width(from));
      const foot = Math.max(0, height(to) - height(from));
      const cut = rtl ? [0, 0, foot, end] : [0, end, foot, 0];
      motions.set(part.element, { from, to, carries: true });
      if (!part.element.matches(TEXT_FIELD)) {
        move(part.element, dx, dy);
        cutFrom(part.element, cut);
        return;
      }
      // The editor's own box cuts its words off at its edges, so it carries them
      // only as far as that box holds them.
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

    // Cut to the frame it stands in as the frame's edges reach it, on every side but
    // one it stands out of.
    function reveal(part, frame) {
      const to = part.box;
      const side = (inset, beyond) => (beyond ? 0 : Math.max(0, inset));
      const cut = [
        side(frame.from.top - to.top, to.top < frame.to.top - 0.5),
        side(to.right - frame.from.right, to.right > frame.to.right + 0.5),
        side(to.bottom - frame.from.bottom, to.bottom > frame.to.bottom + 0.5),
        side(frame.from.left - to.left, to.left < frame.to.left - 0.5),
      ];
      if (cut.every((inset) => near(inset, 0))) return;
      motions.set(part.element, { from: to, to, revealed: true });
      cutFrom(part.element, cut);
    }

    function place(part, frame) {
      const { element, style, box: to } = part;
      const from = was.get(element);
      if (!from) return reveal(part, frame);
      const sized = near(width(from), width(to)) && near(height(from), height(to));
      let within = frame;
      if (element !== box && element !== root) {
        if (sized && !part.holdsWindow) return carry(part, from);
        if (part.whole) return carryContent(part, from);
        if (!same(from, to)) {
          motions.set(element, { from, to });
          within = { from, to };
        }
        if (!sized && rings(style)) {
          // The surface draws the ring while it moves, in the ring's own colour.
          const grow =
            Number.parseFloat(style.outlineWidth) +
            Number.parseFloat(style.outlineOffset);
          const radius = radiusOf(style);
          keeps(ringLayer, "style", `background: ${style.outlineColor}`);
          hold(element, "outlineColor", "transparent");
          for (const [layer, reach] of [
            [ringLayer, grow],
            [ringFill, 0],
          ])
            start(layer, [
              { clipPath: outline(from, reach, radius) },
              { clipPath: outline(to, reach, radius) },
            ]);
        } else if (!sized && paints(style) && !part.holdsWindow)
          cutFrom(
            element,
            [
              from.top - to.top,
              to.right - from.right,
              to.bottom - from.bottom,
              from.left - to.left,
            ].map((inset) => Math.max(0, inset)),
            radiusOf(style),
          );
      }
      for (const inner of part.parts) place(inner, within);
    }

    for (const part of parts) place(part, { from: boxFrom, to: boxAt });
    if (running.length === 0 && same(boxFrom, boxAt)) return;
    motions.set(box, { from: boxFrom, to: boxAt });
    for (const [layer, grow] of surface())
      start(layer, [
        { clipPath: outline(boxFrom, grow, boxRadius) },
        { clipPath: outline(boxAt, grow, boxRadius) },
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
