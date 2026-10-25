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
 *   rules. A ring is drawn by the surface. A painted face travels by its start
 *   corner, clipped in that moving frame; its children subtract that carry from
 *   their own translation, so the face never clips children travelling independently
 *   from another place. A part holding something placed against the window cannot
 *   carry or clip it, so leaves its face at rest.
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
 *   leaf leaving the corner, rather than showing under it. A new part holding one
 *   placed against the window has its parts revealed one by one, as a part holding one
 *   is never carried whole.
 *
 * Translation and clips are animated through registered properties so they paint
 * together. Direct translate or clip-path animations can advance independently on the
 * compositor and leave content outside its focus ring despite identical clocks.
 * Translation's consumer stays in ordinary style: Firefox can composite even a
 * constant translate keyframe that reads an animated property. Restore that temporary
 * declaration when its part stops moving, retaining it across a reversal.
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
 * leaves behind needs undoing. Each part's motion plays through motion.js's `playMotion`,
 * so reduced motion and the presentation boundary are answered there: while motion
 * does not play, each reading takes the box as it stands, and a user asking for
 * stillness mid-tween finishes what is moving.
 *
 * A send is the user's change joining a stream ("send" from `theirs()`, read where
 * the stream starts from with `stream`). What the box shows above its field then
 * moves as one stream sliding up to take the new turn: a scroller's content is
 * carried from where it stood when the send began, its own scroll included, so the
 * new turn comes up at the scroller's foot while every turn above it rides up with
 * the name over them; and a part new to the box, as a view the send opens is, rises
 * with the box's top edge out of the box's old outline rather than being uncovered in
 * place. The user asked for this on 25 October: a stream that slides up to take the
 * new message, its header moving with it.
 *
 * The platform's own way to move a layout change, a view transition, draws the old
 * state as a picture, sends every press to the root while it runs, and abandons a
 * running one when the next change starts, as each keystroke would; here every part
 * stays live and pressable, which takes reading where each was drawn. */
import { keeps } from "./keeps.js";
import { motionPlays, playMotion } from "./motion.js";
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
const clipFrame = (sides, radius = 0) => ({
  clipPath: `inset(var(--lf-box-cut) round ${radius}px)`,
  "--lf-box-cut": sides.map((side) => `${side}px`).join(" "),
});
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
  // Folding finishes the change of size while the compact object is still travelling.
  // Keep that path here too when a new gesture interrupts it: the next motion starts
  // from the shape on screen, not the rectangle a simultaneous resize would draw.
  let shapeUntil = 1;
  let rtl = false;
  // Where each scroller's content stood when a send began, in the window, as carried
  // parts are read: the send's stream starts from there (`stream`).
  let streamFrom = new Map();
  const interpolate = (from, to, progress) => {
    const rect = between(from, to, progress);
    const shape = Math.min(1, progress / shapeUntil);
    const w = width(from) + (width(to) - width(from)) * shape;
    const h = height(from) + (height(to) - height(from)) * shape;
    if (rtl) rect.left = rect.right - w;
    else rect.right = rect.left + w;
    rect.top = rect.bottom - h;
    return rect;
  };
  const translations = new Map();
  const restoreTranslations = (keep = new Set()) => {
    for (const [element, { value, priority }] of translations) {
      if (keep.has(element)) continue;
      element.style.setProperty("translate", value, priority);
      translations.delete(element);
    }
  };
  let observed = new Set();
  // The parts read whole, whose insides no reading reads.
  let wholes = new WeakSet();
  const insideWhole = (node) => {
    for (let up = node.parentElement; up && up !== root; up = up.parentElement)
      if (wholes.has(up)) return true;
    return false;
  };

  // The nearest carrier's global offset includes every carrying ancestor: each
  // nested translation subtracts its parent's offset, so the local offsets telescope.
  function carriedBy(progress) {
    const offsets = new Map();
    const offset = (carrier) => {
      if (!offsets.has(carrier)) {
        const { from, to, carries: edge } = motions.get(carrier);
        const now = between(from, to, progress);
        offsets.set(carrier, [now[edge] - to[edge], now.top - to.top]);
      }
      return offsets.get(carrier);
    };
    return (element) => {
      for (let up = element; up && up !== root; up = up.parentElement)
        if (motions.get(up)?.carries) return offset(up);
      return [0, 0];
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
    // CSS-anchored surfaces already follow their anchor's painted position. Reading
    // that travel as a layout change would retarget the anchor on every frame.
    if (style.positionAnchor.startsWith("--")) return;
    const [dx, dy] = carried(element);
    const part = {
      element,
      style,
      box: shifted(boxOf(element.getBoundingClientRect()), -dx, -dy),
      window: style.position === "fixed",
      parts: [],
    };
    part.scrolls = /auto|scroll/.test(`${style.overflowX} ${style.overflowY}`);
    // The motion owner exposes its own parts, even when its host is a custom element.
    // Descendant widgets keep their independent rendering opaque.
    part.whole =
      (element !== root && element.localName.includes("-")) ||
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
      const moving = motions.get(element);
      if (moving?.revealed && progress < 1) continue;
      at.set(
        element,
        moving
          ? (element === box ? interpolate : between)(moving.from, moving.to, progress)
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

  function follow({ duration, easing }, compact = false) {
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
    // A send's scroll moves a scroller's content without changing any part's layout,
    // as in a view already at its cap: that content still rides.
    const scrolled =
      theirs() === "send" &&
      [...streamFrom].some(([scroller, then]) => {
        const content = scroller.firstElementChild;
        if (!content || (motions.get(content)?.stream && progress < 1)) return false;
        return !near(
          content.getBoundingClientRect().top - carried(content)[1],
          then.top,
        );
      });
    // Nothing's layout changed, as when the observer reads a part it starts observing:
    // whatever moves keeps moving.
    if (
      !scrolled &&
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
      restoreTranslations();
      rests = null;
      motions = new Map();
      return;
    }
    // The first reading, and any while motion does not play, is taken as it stands.
    const was = motionPlays() && rests ? drawn(progress, carried) : null;
    const gesture = theirs();
    // A part holding parts of its own that was growing is drawn at a size of its own,
    // so its parts are placed again from where each is drawn.
    const framed = new Set(
      [...motions].filter(([, moving]) => moving.frames).map(([element]) => element),
    );
    const before = rests;
    // A stream's content mid-ride starts the next reading from where it is drawn.
    const streamed = new Map();
    if (progress < 1)
      for (const [element, moving] of motions)
        if (moving.stream)
          streamed.set(element, between(moving.from, moving.to, progress));
    motions = new Map();
    rests = next;

    const space = boxOf(room.getBoundingClientRect());
    const outline = (at, grow, radius) => [
      [
        at.top - space.top - grow,
        space.right - at.right - grow,
        space.bottom - at.bottom - grow,
        at.left - space.left - grow,
      ],
      radius + grow,
    ];
    const boxAt = rests.get(box);
    const boxRadius = radiusOf(getComputedStyle(box));
    for (const [layer, reach] of surface())
      keeps(
        layer,
        "style",
        `clip-path: ${insetOf(...outline(boxAt, reach, boxRadius))}`,
      );
    if (!was?.has(box)) {
      restoreTranslations();
      return;
    }
    const boxFrom = was.get(box);
    shapeUntil = compact ? 0.55 : 1;
    rtl = getComputedStyle(box).direction === "rtl";
    // Every part moves on one clock, through the one door for motion; it plays here,
    // since this reading found that it does.
    const start = (element, keyframes) =>
      running.push(playMotion(element, keyframes, { duration, easing }));
    const contour = (from, to, grow, radius, compact = false) => {
      const frames = [clipFrame(...outline(from, grow, radius))];
      if (compact)
        frames.push({
          ...clipFrame(...outline(interpolate(from, to, shapeUntil), grow, radius)),
          offset: shapeUntil,
        });
      frames.push(clipFrame(...outline(to, grow, radius)));
      return frames;
    };
    const hold = (element, property, value) =>
      start(element, [{ [property]: value }, { [property]: value }]);
    const translated = new Set();
    const move = (element, dx, dy) => {
      // From/to stay in window coordinates; nested translations are relative to the
      // nearest carrying ancestor, so their local offsets add to this global one.
      const [carriedX, carriedY] = carriedBy(0)(element.parentElement);
      dx -= carriedX;
      dy -= carriedY;
      if (!translations.has(element))
        translations.set(element, {
          value: element.style.getPropertyValue("translate"),
          priority: element.style.getPropertyPriority("translate"),
        });
      translated.add(element);
      element.style.setProperty("translate", "var(--lf-box-carry)");
      start(element, [
        { "--lf-box-carry": `${dx}px ${dy}px` },
        { "--lf-box-carry": "0px 0px" },
      ]);
    };
    const cutFrom = (element, cut, radius = 0) =>
      start(element, [clipFrame(cut, radius), clipFrame([0, 0, 0, 0], radius)]);

    // Moved whole, from where it was drawn.
    function carry(part, from) {
      const dx = from.left - part.box.left;
      const dy = from.top - part.box.top;
      const [carriedX, carriedY] = carriedBy(0)(part.element.parentElement);
      if (near(dx, carriedX) && near(dy, carriedY)) return;
      motions.set(part.element, { from, to: part.box, carries: "left" });
      move(part.element, dx, dy);
    }

    // Its content carried by its start corner, cut to its outline growing from where
    // it stood.
    function carryContent(part, from) {
      const to = part.box;
      if (part.scrolls && !part.element.matches(TEXT_FIELD)) {
        grow(part, from);
        if (gesture === "send") streamContent(part);
        return;
      }
      let dx = rtl ? from.right - to.right : from.left - to.left;
      let dy = from.top - to.top;
      // A shrinking frame starts outside its final box, so children remain visible
      // in the larger outline they occupied before the change.
      const end = width(to) - width(from);
      const foot = height(to) - height(from);
      const cut = rtl ? [0, 0, foot, end] : [0, end, foot, 0];
      // The editor's own box cuts its words off at its edges, so it carries them
      // inside itself only as far as that box holds them. Where its start moved up or
      // back, the editor is carried whole instead, unless the user is typing in it,
      // when a moving field would move under their typing.
      const editor = part.element.matches(TEXT_FIELD);
      const inside = (rtl ? dx <= 0 : dx >= 0) && dy >= 0;
      if (!editor || (!inside && gesture !== "typing")) {
        motions.set(part.element, { from, to, carries: rtl ? "right" : "left" });
        move(part.element, dx, dy);
        cutFrom(part.element, cut, radiusOf(part.style));
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
      // A cut on a part holding one placed against the window would cut that one too,
      // so its parts are revealed one by one.
      if (part.holdsWindow) {
        motions.set(part.element, { from: to, to, revealed: true });
        for (const inner of part.parts) reveal(inner, frame, siblings);
        return;
      }
      const carriedTo = shifted(to, ...carriedBy(0)(part.element.parentElement));
      const side = (inset, beyond) => (beyond ? 0 : Math.max(0, inset));
      /** @type {[number, number, number, number]} */
      const from = [
        side(frame.from.top - carriedTo.top, to.top < frame.to.top - 0.5),
        side(carriedTo.right - frame.from.right, to.right > frame.to.right + 0.5),
        side(carriedTo.bottom - frame.from.bottom, to.bottom > frame.to.bottom + 0.5),
        side(frame.from.left - carriedTo.left, to.left < frame.to.left - 0.5),
      ];
      /** @type {[number, number, number, number]} */
      const end = [0, 0, 0, 0];
      const overlaps = (a, b, low, high) => a[low] < b[high] && b[low] < a[high];
      for (const sibling of siblings) {
        const moving = motions.get(sibling.element);
        if (!moving || moving.revealed) continue;
        const { from: then, to: at } = moving;
        const across = overlaps(at, to, "top", "bottom");
        const along = overlaps(at, to, "left", "right");
        // On each side the part stands beside it, how far in it reaches, then and at
        // rest.
        [
          along && { then: then.bottom - carriedTo.top, rest: at.bottom - to.top },
          across && { then: carriedTo.right - then.left, rest: to.right - at.left },
          along && { then: carriedTo.bottom - then.top, rest: to.bottom - at.top },
          across && { then: then.right - carriedTo.left, rest: at.right - to.left },
        ].forEach((reach, index) => {
          if (reach && reach.rest <= 0.5 && reach.then > from[index]) {
            from[index] = reach.then;
            end[index] = reach.rest;
          }
        });
      }
      if (from.every((inset) => near(inset, 0))) return;
      motions.set(part.element, { from: to, to, revealed: true });
      start(part.element, [clipFrame(from), clipFrame(end)]);
    }

    // A part new to the box, in a send: it rises with the box's top edge, from as far
    // below its rest as that edge rises, cut where the box's old outline stood, so it
    // comes up out of the box as the stream does.
    function rise(part, frame, siblings) {
      const to = part.box;
      const dy = boxFrom.top - boxAt.top;
      if (dy < 0.5) return reveal(part, frame, siblings);
      motions.set(part.element, { from: shifted(to, 0, dy), to, carries: "left" });
      move(part.element, 0, dy);
      // How far it stands below the old outline's top at its start; the cut reaches
      // nothing once the part has risen clear of it.
      const first = Math.max(0, to.bottom + dy - boxFrom.top);
      if (first < 0.5) return;
      const clear = 1 - Math.max(0, boxFrom.top - to.bottom) / dy;
      const frames = [clipFrame([0, 0, first, 0])];
      if (clear > 0 && clear < 1)
        frames.push({ ...clipFrame([0, 0, 0, 0]), offset: clear });
      frames.push(clipFrame([0, 0, 0, 0]));
      start(part.element, frames);
    }

    // A scroller's content in a send: carried from where it stood when the send began,
    // or from where it is drawn while the stream already carries it, so its new turn
    // comes up at the scroller's foot under the scroller's own clip.
    function streamContent(part) {
      const content = part.element.firstElementChild;
      if (!content) return;
      const then = streamed.get(content) ?? streamFrom.get(part.element);
      if (!then) return;
      const [cx, cy] = carriedBy(0)(content);
      const now = shifted(boxOf(content.getBoundingClientRect()), -cx, -cy);
      const dy = then.top - now.top;
      if (Math.abs(dy) < 0.5) return;
      motions.set(content, { from: shifted(now, 0, dy), to: now, stream: true });
      move(content, 0, dy);
    }

    function streamWithin(part) {
      if (part.scrolls) streamContent(part);
      else part.parts.forEach(streamWithin);
    }

    function place(part, frame, siblings = []) {
      const { element, style, box: to } = part;
      const from = was.get(element);
      if (!from)
        return gesture === "send"
          ? rise(part, frame, siblings)
          : reveal(part, frame, siblings);
      const rest = before.get(element);
      const sized =
        !framed.has(element) &&
        near(width(rest), width(to)) &&
        near(height(rest), height(to));
      let within = frame;
      if (element !== box && element !== root) {
        const carries = gesture !== null;
        if (sized && !part.holdsWindow) {
          if (!carries) return reveal(part, frame, siblings);
          carry(part, from);
          // A part carried whole still holds the stream a send moves.
          if (gesture === "send") streamWithin(part);
          return;
        }
        if (part.whole) return carries ? carryContent(part, from) : grow(part, from);
        if (!same(from, to)) within = { from, to };
        if (!sized && rings(style)) {
          // The surface draws the ring while it moves, in the ring's own colour.
          const offset = Number.parseFloat(style.outlineOffset);
          const reach = Number.parseFloat(style.outlineWidth) + offset;
          const radius = radiusOf(style);
          keeps(ringLayer, "style", `background: ${style.outlineColor}`);
          hold(element, "outlineColor", "transparent");
          for (const [layer, grown] of [
            [ringLayer, reach],
            // The fill meets the outline's inner edge, including an inward ring.
            [ringFill, offset],
          ])
            start(layer, contour(from, to, grown, radius));
        } else if (!sized && paints(style) && !part.holdsWindow)
          carries ? carryContent(part, from) : grow(part, from);
        if (!same(from, to))
          motions.set(element, { ...motions.get(element), from, to, frames: true });
      }
      // What carries is placed first, so what is new beside it is revealed from it.
      const placed = [...part.parts].sort(
        (a, b) => Number(!was.has(a.element)) - Number(!was.has(b.element)),
      );
      for (const inner of placed) place(inner, within, part.parts);
    }

    for (const part of parts) place(part, { from: boxFrom, to: boxAt });
    restoreTranslations(translated);
    if (running.length === 0 && same(boxFrom, boxAt)) return;
    motions.set(box, { from: boxFrom, to: boxAt });
    for (const [layer, reach] of surface())
      start(layer, contour(boxFrom, boxAt, reach, boxRadius, compact));
    // The box stands transparent over the surface's own fill while everything moves,
    // and lets what it carries stand past its rest outline on the way.
    hold(box, "backgroundColor", "transparent");
    hold(box, "overflow", "visible");
    const animations = running;
    animations.at(-1).onfinish = () => {
      if (running === animations) restoreTranslations();
    };
  }

  return {
    follow,
    // A send begins: read where each scroller's content stands now, before the send
    // draws, so the readings the send makes carry it from here.
    stream() {
      const progress = running[0]?.effect.getComputedTiming().progress ?? 1;
      const carried = carriedBy(progress);
      streamFrom = new Map();
      for (const element of rests?.keys() ?? []) {
        const content = element.firstElementChild;
        if (!content || !/auto|scroll/.test(getComputedStyle(element).overflowY))
          continue;
        const [dx, dy] = carried(content);
        streamFrom.set(
          element,
          shifted(boxOf(content.getBoundingClientRect()), -dx, -dy),
        );
      }
    },
    // The window changed size: the next reading takes the box as it stands.
    forget() {
      rests = null;
    },
  };
}
