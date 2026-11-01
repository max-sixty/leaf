/* How a floating box follows a change of its layout, whatever made the change, a line
 * the field gained, more room, a view opening, the box folding to its leaf: the one model
 * of motion for the floating panel (floating-panel.js, `followBox`), the margin thread
 * card (thread-preview.js, `followCard`) and the comment box beside a passage
 * (composing/floating-response.js, `followFab`), whose Send grows the card out of its
 * field (`drawnAt`). The user asked on 25 October for one canonical animation, after a
 * card's send jumped to its new turn's head while a second mechanism slid its words by
 * scrolling, and on 26 October for the comment box to move the same way, which grew a
 * line in one frame and grew its card by a clip of its own on another clock.
 *
 * The layout changes in one step, so nothing a press aims at waits on a tween, and what
 * the user sees then travels from where it was drawn to where it now stands, every part
 * on one shared tween:
 *
 * - The box's outline is drawn by its surface, layers of their own behind it cut to
 *   the outline, so the outline moves by its cut from where it was drawn to where it
 *   stands. A ring the box or a part of it wears, such as the field's focus ring, is
 *   drawn there too while it moves (`ring`), since no transform draws a box changing
 *   size. The surface stands behind every part, so the box's face is the only ground
 *   between it and a ring it draws: a part around the ring's wearer that paints its
 *   own would cover the ring's band. The wearer's own ground already stands at its new
 *   size and would cover the band on the side it grows toward, so the surface draws
 *   that ground too, inside the ring. A box anchored in the page holds its surface
 *   inside itself, so the page's scroll carries both.
 * - A part that kept its size is carried: drawn where it stood, and moved by a
 *   transform to where it stands.
 * - A part that changed size and holds parts of its own leaves each of them to these
 *   rules. A ring is drawn by the surface. A painted face travels by its start
 *   corner, clipped in that moving frame; its children subtract that carry from
 *   their own translation, so the face never clips children travelling independently
 *   from another place. A part holding something placed against the window cannot
 *   carry or clip it, so leaves its face at rest.
 * - A part that changed size and holds only its own content, such as words, carries
 *   that content by its start corner, where its layout sets it from, cut to its
 *   outline growing from where it stood, whether it grew or shrank. A field left
 *   empty, and in a send the frames around the field it empties, holds nothing that
 *   carries on, so where it shrank while its far edge stayed it travels by that edge.
 *   An editor carries its words inside its own box (`--lf-field-carry`,
 *   `--lf-field-cut`, composing/text-field.js), so the field's own box stays where
 *   the user types. That box cuts its words off at its edges, so where the editor's
 *   start moved up or back, as more room re-wrapping a paragraph moves it, the editor
 *   is carried whole instead; while the user types, as when a line is removed, the
 *   box stops cutting them as far as they travel (`--lf-field-reach`). A field that
 *   stops scrolling carries its words by the scroll it gave up too. A part that
 *   scrolls and changed size shows what its scroll puts in it, which the reader
 *   landing in it measures mid-tween, so it only grows from where it stood; one that
 *   kept its size is carried.
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
 * moved, so the eye follows it. A key changes the box in the frame it lands, though,
 * as it changes a textarea sized to its words, since what a key adds is what the user
 * reads next: a tween cut off the glyph just typed for its first frames as the box
 * widened, and the word and caret a new line took for about 100 ms, and a tween each
 * key restarted never settled. Only a line a key takes away travels, both edges on
 * the one tween, as anything leaving the page folds (motion.js), so words the box
 * carries down with its top edge stay where the eye can follow them, and nothing the
 * user reads waits on it. The user asked on 30 October for typing to grow the box as
 * a textarea's grows, and chose on 31 October to keep a removed line's travel. News,
 * such as an answer arriving, moves nothing the reader reads (browser/AGENTS.md,
 * "The page holds still under the user's aim"): each part it moved shows where it now
 * stands, revealed by the frame it stands in or growing from its own old box, while
 * the box's outline and ring still follow.
 *
 * A change arriving during the tween starts each part from where it is drawn then;
 * news arriving while the user's change still carries parts shows them where they now
 * stand, but for a send's ride (below). A part placed against the window, as the
 * attachment shelf is, moves with no ancestor's transform, so a part holding one is
 * never carried whole: its parts are placed one by one. The motion is presentation
 * only: each part's layout is where it stands from the change on, and a part's motion
 * ends with the tween, so nothing it leaves behind needs undoing. Each part's motion
 * plays through motion.js's `playMotion`, so reduced motion and the presentation
 * boundary are answered there: while motion does not play, each reading takes the box
 * as it stands, and a user asking for stillness mid-tween finishes what is moving.
 *
 * Every reading is taken in the box's own plane: a box the page's scroll or its
 * placement carries whole is read from the edges that hold it (`held`), so only a change
 * of its layout moves anything.
 *
 * A send is the user's change joining a stream ("send" from `theirs()`, read where
 * the stream starts from with `stream`). What the box shows above its field then
 * moves as one stream sliding up to take the new turn: a scroller's content, every
 * child of it, is carried from where it was drawn when the send began, its own scroll
 * included, so the new turn comes up at the scroller's foot while every turn above it
 * rides up with the name over them; and a part new to the box, as a view the send
 * opens is, rises with the box's top edge out of the box's old outline rather than
 * being uncovered in place, while one standing inside that outline, as a reply field
 * taking the row's seat, is revealed there. The user asked for this on 25 October: a
 * stream that slides up to take the new message, its header moving with it. A head
 * stuck to the scroller's edge rides as a scroll that far back would stick it
 * (`streamContent`). While the
 * content rides, the scroller's end stays where its layout puts it
 * (scrolling.js, `contentRides`), and its scroll is anchored to nothing, so neither
 * a landing at its end nor the browser's scroll anchoring chases the ride, and a reading
 * meanwhile, news included, carries the ride on from where it is drawn. Rejected:
 * scrolling the scroller through the ride, which a card's send once did on its own
 * clock after its box had already grown, so its new turn's head jumped into view
 * before its words slid; every landing during the ride would also stop it.
 *
 * The platform's own way to move a layout change, a view transition, draws the old
 * state as a picture, sends every press to the root while it runs, and abandons a
 * running one when the next change starts, as each keystroke would; here every part
 * stays live and pressable, which takes reading where each was drawn. */
import { inlineStyle, keeps } from "./keeps.js";
import { motionEasing, motionPlays, motionTime, playMotion } from "./motion.js";
import { TEXT_FIELD } from "./control-selectors.js";
import { onUserInput } from "./focus.js";
import { afterSettling, nextRender } from "./rendering.js";
import { contentRides } from "./scrolling.js";

/** @typedef {import('./rect.js').Box} Box
 * @typedef {import('./css-anchors.js').Anchor} Anchor
 * @typedef {keyof Box} Edge
 * @typedef {[number, number]} Offset
 * @typedef {[number, number, number, number]} Insets
 * @typedef {{element: Element, style: CSSStyleDeclaration, box: Box, window: boolean,
 * parts: Part[], scrolls: boolean, whole: boolean, holdsWindow: boolean}} Part
 * @typedef {{from: Box, to: Box, carries?: [Edge, Edge], frames?: boolean,
 * revealed?: boolean, gaveUp?: number}} Moving
 * @typedef {{child: Element, top: number}} StreamStart
 * @typedef {{child: Element, from: number, to: number}} Stream
 * @typedef {(element: Element | null) => Offset} Carried
 * @typedef {{duration: number, easing: string}} Timing */

// Whose change it is, one clock for every box, since an input anywhere is the user's:
// their key, press or typing owns what it sets going until that rendering settles
// (rendering.js, `afterSettling`), so changes to a box meanwhile are theirs, and what
// changes it after, such as an answer arriving, is news. News landing before the
// gesture's rendering settles, a reading back within a frame or two, is taken as
// theirs. Typing is told apart, since the field it types in must not move under it.
// Activation is a new gesture too: a held press can settle before its click.
/** @type {"typing" | "press" | null} */
let gesture = null;
let gestures = 0;
/** @param {Event} event */
function beginGesture(event) {
  if (!["keydown", "pointerdown", "input", "touchstart", "click"].includes(event.type))
    return;
  gesture = event.type === "input" ? "typing" : "press";
  const own = ++gestures;
  afterSettling(() => {
    if (gestures === own) gesture = null;
  });
}
let listening = false;
function listen() {
  if (listening) return;
  listening = true;
  onUserInput(beginGesture);
  window.addEventListener("click", beginGesture, { capture: true, passive: true });
}

// How far a lift of the theme's (`--raise-N`, base.css) paints past the box it raises,
// cast as a filter's drop shadow: its drop, and twice its blur, which a filter takes as
// the deviation of its Gaussian, so the shadow has faded to nothing seen by then. Read
// off `element`, where the theme registers them as lengths. Cut at the drop and one
// blur, the shadow stopped in a step.
/** @param {Element} element @param {number} level */
const liftReach = (element, level) => {
  const lift = getComputedStyle(element);
  const drop = Number.parseFloat(lift.getPropertyValue(`--raise-${level}-drop`));
  const blur = Number.parseFloat(lift.getPropertyValue(`--raise-${level}-blur`));
  return drop + 2 * blur;
};

/** @param {number} a @param {number} b */
const near = (a, b) => Math.abs(a - b) < 0.5;
/** @param {Box} rect @returns {Box} */
const boxOf = (rect) => ({
  left: rect.left,
  top: rect.top,
  right: rect.right,
  bottom: rect.bottom,
});
/** @param {Box} box */
const width = (box) => box.right - box.left;
/** @param {Box} box */
const height = (box) => box.bottom - box.top;
/** @param {Box} a @param {Box} b */
const same = (a, b) =>
  near(a.left, b.left) &&
  near(a.top, b.top) &&
  near(a.right, b.right) &&
  near(a.bottom, b.bottom);
/** @param {Box} from @param {Box} to @param {number} progress @returns {Box} */
const between = (from, to, progress) => ({
  left: from.left + (to.left - from.left) * progress,
  top: from.top + (to.top - from.top) * progress,
  right: from.right + (to.right - from.right) * progress,
  bottom: from.bottom + (to.bottom - from.bottom) * progress,
});
/** @param {Box} box @param {number} dx @param {number} dy */
const shifted = (box, dx, dy) => ({
  left: box.left + dx,
  top: box.top + dy,
  right: box.right + dx,
  bottom: box.bottom + dy,
});
/** @param {Insets} sides @param {number} [radius] */
const insetOf = ([top, right, bottom, left], radius = 0) =>
  `inset(${top}px ${right}px ${bottom}px ${left}px round ${radius}px)`;
/** @param {readonly number[]} sides @param {number} [radius] @returns {Keyframe} */
const clipFrame = (sides, radius = 0) => ({
  clipPath: `inset(var(--lf-box-cut) round ${radius}px)`,
  "--lf-box-cut": sides.map((side) => `${side}px`).join(" "),
});
// Whether an anchor is in the document: an element, or the start of what a scroller
// holds (css-anchors.js, `ContentStart`).
/** @param {Anchor} anchor */
const connected = (anchor) =>
  "scroller" in anchor ? anchor.scroller.isConnected : anchor.isConnected;
// The part of a move `moved` that a plane moving `limit` accounts for: no farther than
// the plane moved, and only in its direction.
/** @param {number} moved @param {number} limit */
const planeShare = (moved, limit) =>
  moved * limit > 0 ? Math.sign(limit) * Math.min(Math.abs(moved), Math.abs(limit)) : 0;
/** @param {CSSStyleDeclaration} style */
const radiusOf = (style) => Number.parseFloat(style.borderTopLeftRadius) || 0;
/** @param {string} color */
const seeThrough = (color) => /^(transparent|rgba\(.*,\s*0\))$/.test(color);
/** @param {CSSStyleDeclaration} style */
const paints = (style) =>
  !seeThrough(style.backgroundColor) ||
  style.backgroundImage !== "none" ||
  style.boxShadow !== "none" ||
  ["top", "right", "bottom", "left"].some(
    (side) => Number.parseFloat(style.getPropertyValue(`border-${side}-width`)) > 0,
  );
/** @param {CSSStyleDeclaration} style */
const rings = (style) =>
  style.outlineStyle !== "none" && Number.parseFloat(style.outlineWidth) > 0;

// root: the element whose parts move, the box among them, and only what moves with the
// box: a part with a job of its own beside it, such as a grip whose clip leaves its
// middle open to presses, stands outside it, since a cut would replace that clip. box:
// the part the surface draws. surface: the class of the surface's layer (`ground`),
// which the caller stands behind the box in the box's plane, and whose rule places it
// reaching past every outline the box can travel through, against which its cuts are
// measured, and colours its ring and fill (`--lf-box-ring`, `--lf-box-fill`,
// chrome.css). lift: the theme's lift (`--raise-N`) whose shadow the surface casts.
// outset: how far the surface's ring stands outside the box, 1 for a ring around it, 0
// for one drawn inside its edge as a border is. observer: reads the box again when any
// part changes size. held(): the root's edges that hold it in its plane, the anchor of
// what it stands by, and the element the plane moves with (`plane`), null for the
// window's; or null for a box fixed in the window.
/** @param {{
 * root: HTMLElement, box: HTMLElement, surface: string, lift: number, outset: number,
 * observer: ResizeObserver,
 * held?: () => {
 *   x: "left" | "right", y: "top" | "bottom", by?: Anchor | null, plane?: Anchor | null,
 * } | null,
 * }} options */
export function boxMotion({
  root,
  box,
  surface: surfaceClass,
  lift,
  outset,
  observer,
  held = () => null,
}) {
  listen();
  // The surface: a ring and a fill inside it, cut to the box's outline, under one
  // shadow, and a ring a part of the box wears, drawn here only while the box moves,
  // in that ring's own colour, since no transform draws a ring changing size.
  /** @param {string} name */
  const layer = (name) => {
    const node = document.createElement("div");
    node.className = name;
    return node;
  };
  const room = layer(`lf-box-ground ${surfaceClass}`);
  room.setAttribute("aria-hidden", "true");
  const ring = layer("lf-box-ring");
  const fill = layer("lf-box-fill");
  const ringLayer = layer("lf-box-moving-ring");
  const ringFill = layer("lf-box-fill");
  room.append(ring, fill, ringLayer, ringFill);
  const shadowReach = () => liftReach(room, lift);
  // Each layer, how far past the outline it is cut, and what it paints besides.
  /** @returns {[HTMLElement, number, string][]} */
  const surface = () => [
    [room, shadowReach(), `filter: drop-shadow(var(--raise-${lift})); `],
    [ring, outset, ""],
    [fill, outset - 1, ""],
  ];
  // Whether this box's send is the gesture under way (`stream`): the gesture's number.
  let sent = -1;
  const theirs = () => (gesture !== null && sent === gestures ? "send" : gesture);
  // Each part's box as its layout placed it at the last reading, in the window.
  /** @type {Map<Element, Box> | null} */
  let rests = null;
  // The root's box when the readings kept were taken, in the window. A box anchored in
  // the page moves with the page's scroll, and a placement can carry it whole, as
  // dragging it does; neither is a change of its layout. So every reading kept is moved
  // first as far as the edges holding the root moved since (`rebase`), and a box held
  // by its foot that grows at its top reads as growing, not as moving.
  /** @type {Box | null} */
  let frame = null;
  // What the box stands by, and where it stood in the box's plane at the last reading
  // or placement, or null for a box that stands by nothing (`beside`).
  /** @type {{by: Anchor, plane: Anchor | null, x: number, y: number} | null} */
  let besideAt = null;
  // The timing of the last reading, which a send's scroll reads again with (`stream`).
  /** @type {Timing | null} */
  let timing = null;
  // Each part moving, from the box it was drawn at to its rest, on one clock.
  /** @type {Map<Element, Moving>} */
  let motions = new Map();
  /** @type {Animation[]} */
  let running = [];
  // Folding finishes the change of size while the compact object is still travelling.
  // Keep that path here too when a new gesture interrupts it: the next motion starts
  // from the shape on screen, not the rectangle a simultaneous resize would draw.
  let shapeUntil = 1;
  let rtl = false;
  // Where each scroller's content was drawn when a send began, in the window, read by
  // one of its children: the send's stream starts from there (`stream`).
  /** @type {Map<Element, StreamStart>} */
  let streamFrom = new Map();
  // Each scroller's content riding a stream, by that child, from where it was drawn to
  // where it stands, on the clock every part shares.
  /** @type {Map<Element, Stream>} */
  let streams = new Map();
  let stopStreaming = new AbortController();
  // How far each editor had scrolled its words before the change being read: taken at
  // each reading, again as each press or key begins, and as the field opens an edit
  // (`lf-before-edit`, composing/text-field.js), since a field scrolls as it is typed
  // in without changing size, and paste or dictation edit it with no key.
  /** @type {Map<Element, number>} */
  let fieldScrolls = new Map();
  const noteFieldScrolls = () => {
    for (const field of fieldScrolls.keys()) fieldScrolls.set(field, field.scrollTop);
  };
  // An `input` reports an edit already made, so it is too late.
  onUserInput((event) => {
    if (event.type !== "input") noteFieldScrolls();
  });
  root.addEventListener("lf-before-edit", noteFieldScrolls, { passive: true });
  const forget = () => {
    rests = null;
  };
  // The window changed size: the next reading takes the box as it stands, rather than
  // trail the window's edge by a tween.
  addEventListener("resize", forget);
  // Moves every reading kept, and what is moving, as far as the plane carried the box.
  /** @param {number} dx @param {number} dy */
  function carryReadings(dx, dy) {
    if (near(dx, 0) && near(dy, 0)) return;
    if (rests)
      rests = new Map(
        [...rests].map(([element, rest]) => [element, shifted(rest, dx, dy)]),
      );
    for (const moving of motions.values()) {
      moving.from = shifted(moving.from, dx, dy);
      moving.to = shifted(moving.to, dx, dy);
    }
    for (const then of streamFrom.values()) then.top += dy;
    for (const riding of streams.values()) {
      riding.from += dy;
      riding.to += dy;
    }
  }
  // What the box stands by, and where it stands in the plane that holds the box: from
  // the element the plane moves with, or from the window. It is read off those
  // elements, never off the box, which Chromium lays out off its spot until the next
  // frame after a placement takes it into its anchor's plane: a reading of the box then
  // is off by the same amount in every part, and carried whole, but a move of the box
  // against its anchor would read as one.
  /** @param {ReturnType<typeof held>} edges */
  function beside(edges) {
    const by = edges?.by;
    const plane = edges?.plane ?? null;
    if (!by || !connected(by) || (plane && !connected(plane))) return null;
    const at = by.getBoundingClientRect();
    const origin = plane?.getBoundingClientRect() ?? { left: 0, top: 0 };
    return { by, plane, x: at.left - origin.left, y: at.top - origin.top };
  }
  // Carries every reading kept as far as the edges holding the root moved since
  // (`frame`), and returns the root's box and how far what the box stands by moved in the box's plane
  // meanwhile, as a scroll moves a passage past a box the window's edge holds.
  function rebase() {
    const at = boxOf(root.getBoundingClientRect());
    const edges = held();
    const dx = frame && edges ? at[edges.x] - frame[edges.x] : 0;
    const dy = frame && edges ? at[edges.y] - frame[edges.y] : 0;
    frame = at;
    carryReadings(dx, dy);
    const now = beside(edges);
    const past =
      now && besideAt?.by === now.by && besideAt.plane === now.plane
        ? { x: now.x - besideAt.x, y: now.y - besideAt.y }
        : { x: 0, y: 0 };
    besideAt = now;
    return { at, past };
  }
  /** @param {Box} from @param {Box} to @param {number} progress */
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
  /** @type {Map<Element, {value: string, priority: string}>} */
  const translations = new Map();
  /** @param {Set<Element>} [keep] */
  const restoreTranslations = (keep = new Set()) => {
    for (const [element, { value, priority }] of translations) {
      if (keep.has(element)) continue;
      inlineStyle(element).setProperty("translate", value, priority);
      translations.delete(element);
    }
  };
  /** @type {Set<Element>} */
  let observed = new Set();
  // The parts read whole, whose insides no reading reads.
  /** @type {WeakSet<Element>} */
  let wholes = new WeakSet();
  /** @param {Element} node */
  const insideWhole = (node) => {
    for (let up = node.parentElement; up && up !== root; up = up.parentElement)
      if (wholes.has(up)) return true;
    return false;
  };

  // The nearest carrier's global offset includes every carrying ancestor: each
  // nested translation subtracts its parent's offset, so the local offsets telescope.
  /** @param {number} progress @returns {Carried} */
  function carriedBy(progress) {
    /** @type {Map<Element, Offset>} */
    const offsets = new Map();
    return (element) => {
      for (let up = element; up && up !== root; up = up.parentElement) {
        const moving = motions.get(up);
        if (!moving?.carries) continue;
        let offset = offsets.get(up);
        if (!offset) {
          const {
            from,
            to,
            carries: [x, y],
          } = moving;
          const now = between(from, to, progress);
          offsets.set(up, (offset = [now[x] - to[x], now[y] - to[y]]));
        }
        return offset;
      }
      return [0, 0];
    };
  }

  // A part, with its box as its layout places it and what decides how it moves.
  /** @param {Element} element @param {Part[]} into @param {Carried} carried */
  function read(element, into, carried) {
    // The surface draws the box, and is no part of it.
    if (element === room) return;
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
    /** @type {Part} */
    const part = {
      element,
      style,
      box: shifted(boxOf(element.getBoundingClientRect()), -dx, -dy),
      window: style.position === "fixed",
      parts: [],
      scrolls: /auto|scroll/.test(`${style.overflowX} ${style.overflowY}`),
      whole: false,
      holdsWindow: false,
    };
    // The motion owner exposes its own parts, even when its host is a custom element.
    // Descendant widgets keep their independent rendering opaque.
    part.whole =
      (element !== root && element.localName.includes("-")) ||
      element instanceof SVGElement ||
      part.scrolls ||
      element.childElementCount === 0 ||
      [...element.childNodes].some(
        (node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim(),
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
  /** @param {number} progress @param {Carried} carried @param {Map<Element, Box>} rests */
  function drawn(progress, carried, rests) {
    const at = new Map();
    for (const [element, rest] of rests) {
      const moving = motions.get(element);
      if (moving?.revealed && progress < 1) continue;
      at.set(element, {
        from: moving
          ? (element === box ? interpolate : between)(moving.from, moving.to, progress)
          : shifted(rest, ...carried(element)),
        rest,
      });
    }
    return at;
  }

  // The observer reads the box again when any part read changes size, and reads a part
  // it starts observing, so a part arriving without moving any part already read, as an
  // attachment hung over the box does, is read at once, and the next change carries it
  // from where it shows. Observing starts in the next frame, since a part observed
  // while the observer delivers would be read in that same delivery, which the browser
  // reports as a loop.
  /** @type {Set<Element>} */
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

  // The tween a change of layout travels on, the box's own unless its caller names
  // another (`--lf-motion-box-resize`, chrome.css).
  /** @param {Partial<Timing>} [timing] @param {boolean} [compact] */
  function follow(
    {
      duration = motionTime("--lf-motion-box-resize", box),
      easing = motionEasing("--lf-motion-box-ease", box),
    } = {},
    compact = false,
  ) {
    timing = { duration, easing };
    rebase();
    const progress = running[0]?.effect?.getComputedTiming().progress ?? 1;
    const carried = carriedBy(progress);
    /** @type {Part[]} */
    const parts = [];
    wholes = new WeakSet();
    read(root, parts, carried);
    /** @type {Map<Element, Box>} */
    const next = new Map();
    /** @param {Part} part */
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
      [...streamFrom].some(
        ([scroller, then]) =>
          !(streams.has(scroller) && progress < 1) &&
          scroller.contains(then.child) &&
          !near(then.child.getBoundingClientRect().top, then.top),
      );
    // Nothing's layout changed, as when the observer reads a part it starts observing:
    // whatever moves keeps moving.
    if (
      !scrolled &&
      rests?.size === next.size &&
      [...next].every(([element, at]) => {
        const rest = rests?.get(element);
        return rest !== undefined && same(rest, at);
      })
    )
      return;
    for (const scroller of streams.keys()) contentRides(scroller, false);
    for (const animation of running) animation.cancel();
    running = [];
    // A box not drawn at all, as in print, has nothing to move, and its next reading
    // takes it as it stands.
    const boxAt = next.get(box);
    if (!boxAt) {
      restoreTranslations();
      rests = null;
      motions = new Map();
      streams = new Map();
      return;
    }
    const gesture = theirs();
    // The first reading, and any while motion does not play, is taken as it stands, as
    // is one a key makes, but for a line it takes away.
    const previous = motionPlays() && rests ? drawn(progress, carried, rests) : null;
    const drawnBox = previous?.get(box)?.from;
    const closes = drawnBox && height(boxAt) < height(drawnBox) - 0.5;
    const was = gesture === "typing" && !closes ? null : previous;
    // A part holding parts of its own that was growing is drawn at a size of its own,
    // so its parts are placed again from where each is drawn.
    const framed = new Set(
      [...motions].filter(([, moving]) => moving.frames).map(([element]) => element),
    );
    // A stream's content mid-ride starts the next reading from where it is drawn.
    const streamed = new Map();
    if (progress < 1)
      for (const [scroller, { child, from, to }] of streams)
        streamed.set(scroller, { child, top: from + (to - from) * progress });
    streams = new Map();
    const moved = motions;
    motions = new Map();
    rests = next;
    const scrolledFrom = fieldScrolls;
    fieldScrolls = new Map(
      [...rests.keys()]
        .filter((element) => element.matches(TEXT_FIELD))
        .map((element) => [element, element.scrollTop]),
    );

    const space = boxOf(room.getBoundingClientRect());
    /** @param {Box} at @param {number} grow @param {number} radius @returns {[Insets, number]} */
    const outline = (at, grow, radius) => [
      [
        at.top - space.top - grow,
        space.right - at.right - grow,
        space.bottom - at.bottom - grow,
        at.left - space.left - grow,
      ],
      radius + grow,
    ];
    const boxStyle = getComputedStyle(box);
    const boxRadius = radiusOf(boxStyle);
    for (const [layer, reach, paint] of surface())
      keeps(
        layer,
        "style",
        `${paint}clip-path: ${insetOf(...outline(boxAt, reach, boxRadius))}`,
      );
    const previousBox = was?.get(box);
    if (!was || !previousBox) {
      restoreTranslations();
      return;
    }
    const boxFrom = previousBox.from;
    shapeUntil = compact ? 0.55 : 1;
    rtl = getComputedStyle(box).direction === "rtl";
    // Every part moves on one clock, through the one door for motion; it plays here,
    // since this reading found that it does.
    /** @param {Element} element @param {Keyframe[]} keyframes */
    const start = (element, keyframes) => {
      const animation = playMotion(element, keyframes, { duration, easing });
      if (animation) running.push(animation);
      return animation;
    };
    /** @param {Box} from @param {Box} to @param {number} grow @param {number} radius @param {boolean} [compact] */
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
    /** @param {Element} element @param {string} property @param {string} value */
    const hold = (element, property, value) =>
      start(element, [{ [property]: value }, { [property]: value }]);
    const translated = new Set();
    /** @param {Element} element @param {number} dx @param {number} dy */
    const move = (element, dx, dy) => {
      // From/to stay in window coordinates; nested translations are relative to the
      // nearest carrying ancestor, so their local offsets add to this global one.
      const [carriedX, carriedY] = carriedBy(0)(element.parentElement);
      dx -= carriedX;
      dy -= carriedY;
      if (!translations.has(element))
        translations.set(element, {
          value: inlineStyle(element).getPropertyValue("translate"),
          priority: inlineStyle(element).getPropertyPriority("translate"),
        });
      translated.add(element);
      inlineStyle(element).setProperty("translate", "var(--lf-box-carry)");
      start(element, [
        { "--lf-box-carry": `${dx}px ${dy}px` },
        { "--lf-box-carry": "0px 0px" },
      ]);
    };
    /** @param {Element} element @param {readonly number[]} cut @param {number} [radius] */
    const cutFrom = (element, cut, radius = 0) =>
      start(element, [clipFrame(cut, radius), clipFrame([0, 0, 0, 0], radius)]);

    // Moved whole, from where it was drawn.
    /** @param {Part} part @param {Box} from */
    function carry(part, from) {
      const dx = from.left - part.box.left;
      const dy = from.top - part.box.top;
      const [carriedX, carriedY] = carriedBy(0)(part.element.parentElement);
      if (near(dx, carriedX) && near(dy, carriedY)) return;
      motions.set(part.element, { from, to: part.box, carries: ["left", "top"] });
      move(part.element, dx, dy);
    }

    // Its content carried by its start corner, where its layout sets it from, cut to its
    // outline growing from where it stood: a field losing a line or the room it was
    // given carries its words down with its top edge, as one given more room carries
    // them up. An emptied field is the exception, a send's included, and in a send the
    // frames around it: its words left, so nothing in it carries on. On an axis where
    // such a part shrank and its far edge stayed, it travels by that edge, so the
    // emptied field standing at its box's foot stays there while the box closes onto
    // it, rather than showing at its old top and sliding down. The user asked on 26
    // October for a line removed to move the words with the field's top edge, which
    // until then traveled while they jumped.
    /** @param {Part} part @param {Box} from */
    function carryContent(part, from) {
      const to = part.box;
      if (part.scrolls && !part.element.matches(TEXT_FIELD)) {
        grow(part, from);
        if (gesture === "send") streamContent(part);
        return;
      }
      const emptied =
        gesture === "send" || part.element.matches(":state(placeholder-shown)");
      /** @param {Edge} start @param {Edge} end @param {(box: Box) => number} length */
      const edgeBy = (start, end, length) =>
        emptied &&
        length(to) < length(from) - 0.5 &&
        near(from[end], to[end]) &&
        !near(from[start], to[start])
          ? end
          : start;
      /** @type {[Edge, Edge]} */
      const carries = [
        rtl ? edgeBy("right", "left", width) : edgeBy("left", "right", width),
        edgeBy("top", "bottom", height),
      ];
      const dx = from[carries[0]] - to[carries[0]];
      let dy = from[carries[1]] - to[carries[1]];
      // Cut to where it stood, as far as its box carried there reaches: a shrinking
      // frame starts outside its final box, so children remain visible in the larger
      // outline they occupied before the change.
      const cut = () => [
        from.top - (to.top + dy),
        to.right + dx - from.right,
        to.bottom + dy - from.bottom,
        from.left - (to.left + dx),
      ];
      // The editor's own box cuts its words off at its edges, so it carries them
      // inside itself as far as that box holds them. Where its start moved up or back,
      // as more room re-wrapping a paragraph moves it, the editor is carried whole
      // instead, except while the user types in it, since typing never moves the field
      // (browser/AGENTS.md, "The page holds still under the user's aim"): a line the user removed carries the words
      // down from above the field's box, which stops cutting them off that far
      // (`--lf-field-reach`, composing/text-field.js) and stops scrolling while they
      // travel, since what it holds now fits.
      const editor = part.element.matches(TEXT_FIELD);
      const inside = (rtl ? dx <= 0 : dx >= 0) && dy >= 0;
      if (!editor || (!inside && gesture !== "typing")) {
        motions.set(part.element, { from, to, carries });
        move(part.element, dx, dy);
        cutFrom(part.element, cut(), radiusOf(part.style));
        return;
      }
      // A field the change lets stop scrolling, as deleting lines below its cap does,
      // moves its words by the scroll it gave up as well as by its edge, and the cut
      // keeps what that scroll hid out of sight until the outline reaches it. Its box
      // follows the edge, so a change mid-tween carries on what is left of that scroll.
      const fits = part.element.scrollHeight <= part.element.clientHeight;
      const gaveUp = fits && !emptied ? (scrolledFrom.get(part.element) ?? 0) : 0;
      const left = (moved.get(part.element)?.gaveUp ?? 0) * (1 - progress);
      dy -= gaveUp + left;
      motions.set(part.element, { from, to, gaveUp: gaveUp + left });
      const reach = Math.max(0, rtl ? dx : -dx, -dy);
      if (reach > 0) hold(part.element, "overflow", "visible");
      // The field's line-end caret needs its 2px paint margin during motion too,
      // both beyond its own overflow clip and beyond the moving content's cut.
      const caretRoom = 2;
      const fieldCut = cut().map((side, index) => side - (index % 2 ? caretRoom : 0));
      start(part.element, [
        {
          "--lf-field-carry": `${dx}px ${dy}px`,
          "--lf-field-cut": fieldCut.map((side) => `${side}px`).join(" "),
          "--lf-field-reach": `${Math.max(caretRoom, reach)}px`,
        },
        {
          "--lf-field-carry": "0px 0px",
          "--lf-field-cut": `0px -${caretRoom}px 0px -${caretRoom}px`,
          "--lf-field-reach": `${Math.max(caretRoom, reach)}px`,
        },
      ]);
    }

    // Drawn where its layout puts it, cut to its outline growing from where it stood.
    // Cancel any carrying ancestor: native scroll and landing already put its content
    // where it belongs, so inheriting that carry would move it away and back.
    /** @param {Part} part @param {Box} from */
    function grow(part, from) {
      const to = part.box;
      motions.set(part.element, { from: to, to });
      carry(part, to);
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
    /** @param {Part} part @param {{from: Box, to: Box}} frame @param {Part[]} siblings */
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
      /** @param {number} inset @param {boolean} beyond */
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
      /** @param {Box} a @param {Box} b @param {Edge} low @param {Edge} high */
      const overlaps = (a, b, low, high) => a[low] < b[high] && b[low] < a[high];
      for (const sibling of siblings) {
        const moving = motions.get(sibling.element);
        if (!moving || moving.revealed) continue;
        const { from: then, to: at } = moving;
        const across = overlaps(at, to, "top", "bottom");
        const along = overlaps(at, to, "left", "right");
        // On each side the part stands beside it, how far in it reaches, then and at
        // rest.
        const reaches = [
          along && { then: then.bottom - carriedTo.top, rest: at.bottom - to.top },
          across && { then: carriedTo.right - then.left, rest: to.right - at.left },
          along && { then: carriedTo.bottom - then.top, rest: to.bottom - at.top },
          across && { then: then.right - carriedTo.left, rest: at.right - to.left },
        ];
        from.forEach((inset, index) => {
          const reach = reaches[index];
          if (reach && reach.rest <= 0.5 && reach.then > inset) {
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
    // comes up out of the box as the stream does. One standing inside the old outline,
    // as the thread's reply field taking the page field's seat in the row does, has no
    // edge bringing it, so it is revealed where it stands: risen from below, it showed
    // nothing of the row's field until the tween's last frames.
    /** @param {Part} part @param {{from: Box, to: Box}} frame @param {Part[]} siblings */
    const rise = (part, frame, siblings) => {
      const to = part.box;
      const dy = boxFrom.top - boxAt.top;
      if (dy < 0.5 || to.top >= boxFrom.top - 0.5) return reveal(part, frame, siblings);
      motions.set(part.element, {
        from: shifted(to, 0, dy),
        to,
        carries: ["left", "top"],
      });
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
    };

    // A scroller's content in a send: carried from where it was drawn when the send
    // began, or from where it is drawn while the stream already carries it, so its new
    // turn comes up at the scroller's foot under the scroller's own clip. Every child
    // rides by the one distance its first child travels, which keeps whichever child
    // was read first. A box stuck to the scroller's edge inside it (`position:
    // sticky`) sticks in layout where the scroll stands now, which the carry would
    // move off that edge, so its inset travels against the carry on the same clock:
    // layout then sticks it where it stuck with the content standing that far back,
    // which is where a scroll that far back would stick it, and it changes over from
    // one head to the next as the content rides past.
    /** @param {{element: Element}} part */
    function streamContent(part) {
      const scroller = part.element;
      const then = streamed.get(scroller) ?? streamFrom.get(scroller);
      if (!then || !scroller.contains(then.child)) return;
      // Where layout stands the child: a part holding the scroller may already be
      // carried, which its box includes and `move` subtracts again.
      const to = then.child.getBoundingClientRect().top - carriedBy(0)(then.child)[1];
      const dy = then.top - to;
      if (Math.abs(dy) < 0.5) return;
      contentRides(scroller, true);
      // Firefox anchors the scroll to where a child is drawn, so it would scroll the
      // ride away frame by frame.
      hold(scroller, "overflowAnchor", "none");
      streams.set(scroller, { child: then.child, from: then.top, to });
      for (const child of scroller.children)
        if (child.checkVisibility()) move(child, 0, dy);
      for (const stuck of scroller.querySelectorAll("*")) {
        const style = getComputedStyle(stuck);
        if (style.position !== "sticky") continue;
        for (const [side, against] of /** @type {const} */ ([
          ["top", -dy],
          ["bottom", dy],
        ]))
          if (style[side] !== "auto") {
            const at = Number.parseFloat(style[side]);
            start(stuck, [{ [side]: `${at + against}px` }, { [side]: `${at}px` }]);
          }
      }
    }

    // The surface draws a ring that changes size while it moves, in the ring's own
    // colour, the box's own ring among them, and inside it the part's own ground, which
    // the part stands without meanwhile.
    /** @param {Element} element @param {CSSStyleDeclaration} style @param {Box} from @param {Box} to @param {boolean} [compact] */
    function drawRing(element, style, from, to, compact = false) {
      const offset = Number.parseFloat(style.outlineOffset);
      const reach = Number.parseFloat(style.outlineWidth) + offset;
      const radius = radiusOf(style);
      const colour = seeThrough(style.backgroundColor) ? null : style.backgroundColor;
      keeps(ringLayer, "style", `background: ${style.outlineColor}`);
      keeps(ringFill, "style", colour && `background: ${colour}`);
      hold(element, "outlineColor", "transparent");
      if (colour) hold(element, "backgroundColor", "transparent");
      /** @type {[Element, number][]} */
      const layers = [
        [ringLayer, reach],
        // The fill meets the outline's inner edge, including an inward ring.
        [ringFill, offset],
      ];
      for (const [layer, grown] of layers)
        start(layer, contour(from, to, grown, radius, compact));
    }

    /** @param {Part} part */
    function streamWithin(part) {
      if (part.scrolls) streamContent(part);
      else part.parts.forEach(streamWithin);
    }

    /** @param {Part} part @param {{from: Box, to: Box}} frame @param {Part[]} [siblings] @returns {void} */
    const place = (part, frame, siblings = []) => {
      const { element, style, box: to } = part;
      const previous = was.get(element);
      if (!previous)
        return gesture === "send"
          ? rise(part, frame, siblings)
          : reveal(part, frame, siblings);
      const { from, rest } = previous;
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
        if (!sized && rings(style)) drawRing(element, style, from, to);
        else if (!sized && paints(style) && !part.holdsWindow)
          carries ? carryContent(part, from) : grow(part, from);
        if (!same(from, to))
          motions.set(element, { from, to, ...motions.get(element), frames: true });
      }
      // What carries is placed first, so what is new beside it is revealed from it.
      const placed = [...part.parts].sort(
        (a, b) => Number(!was.has(a.element)) - Number(!was.has(b.element)),
      );
      for (const inner of placed) place(inner, within, part.parts);
    };

    for (const part of parts) place(part, { from: boxFrom, to: boxAt });
    // A ride under way goes on from where it is drawn through any reading, news
    // included, since stopping it would move every turn the reader reads at once.
    for (const scroller of streamed.keys())
      if (!streams.has(scroller) && rests.has(scroller))
        streamContent({ element: scroller });
    restoreTranslations(translated);
    if (running.length === 0 && same(boxFrom, boxAt)) return;
    motions.set(box, { from: boxFrom, to: boxAt });
    for (const [layer, reach] of surface())
      start(layer, contour(boxFrom, boxAt, reach, boxRadius, compact));
    // A ring the box comes to wear while it moves, as focus reaching the card a
    // comment's Send opened does, would stand at the box's rest size over an outline
    // still travelling, so it waits for the tween's end.
    if (rings(boxStyle)) drawRing(box, boxStyle, boxFrom, boxAt, compact);
    else hold(box, "outlineColor", "transparent");
    // The box stands transparent over the surface's own fill while everything moves,
    // and lets what it carries stand past its rest outline on the way.
    hold(box, "backgroundColor", "transparent");
    hold(box, "overflow", "visible");
    const animations = running;
    const last = animations.at(-1);
    if (last)
      last.onfinish = () => {
        if (running !== animations) return;
        restoreTranslations();
        for (const scroller of streams.keys()) contentRides(scroller, false);
      };
  }

  return {
    // The surface's layer, which the caller stands behind the box.
    ground: room,
    // How far the surface's shadow reaches past the box's outline.
    shadowReach,
    follow,
    // whose change is being read: "typing" or "press" for the user's own, "send" once
    // that gesture sends from this box (`stream`), null for news.
    theirs,
    // A send begins, from within the user's gesture: read where each scroller's
    // content is drawn now, before the send draws, so the readings the send makes
    // carry it from here. A send that only scrolls a scroller, as one at its cap does,
    // changes no part's size, so that scroll is read too.
    stream() {
      if (gesture === null) return;
      sent = gestures;
      rebase();
      streamFrom = new Map();
      stopStreaming.abort();
      stopStreaming = new AbortController();
      const { signal } = stopStreaming;
      for (const element of rests?.keys() ?? []) {
        if (
          element.matches(TEXT_FIELD) ||
          !/auto|scroll/.test(getComputedStyle(element).overflowY)
        )
          continue;
        const child = [...element.children].find((node) => node.checkVisibility());
        if (!child) continue;
        streamFrom.set(element, { child, top: child.getBoundingClientRect().top });
        element.addEventListener(
          "scroll",
          () => {
            if (theirs() === "send" && timing) follow(timing);
            else stopStreaming.abort();
          },
          { signal, passive: true },
        );
        // A wheel or a finger in the scroller starts no gesture, but the scroll it
        // makes is the user's, which the content follows rather than rides.
        for (const type of ["wheel", "touchstart"])
          element.addEventListener(type, () => stopStreaming.abort(), {
            signal,
            passive: true,
          });
      }
    },
    // The box's placement stands it (`place`): once the box has a motion, its owner
    // stands every placement through here, and reads a change of the box's size only
    // once the placement that change asks for has stood it. A placement can change the
    // edges that hold the box, as a line taking it past the window's foot holds it by
    // that foot, so the plane's carry is read first, by the edges that held it until
    // then. What the placement moves then is the plane's or the box's own. At the size
    // last read it is the plane's, as when a scroll re-solves a box held at the window's
    // edge: the next reading carries the box by the edges that hold it now. At a new
    // size it is the box's own and travels from where the box was drawn, but for as far
    // as what the box stands by moved past it meanwhile, as a scroll moves a passage
    // past a box the window's edge holds: the plane carries that much. `place` says how
    // far it moved the box by its own answer: in Chromium, a box it just took into its
    // anchor's plane lays out off its spot until the browser next places it, by
    // hundreds of pixels (floating.js, `clientBox`).
    /** @param {() => {x: number, y: number}} place */
    placed(place) {
      const { at, past } = rebase();
      const read = rests?.get(root);
      const resized =
        !read || !near(width(read), width(at)) || !near(height(read), height(at));
      const moved = place();
      besideAt = beside(held());
      if (!resized) return;
      carryReadings(planeShare(moved.x, past.x), planeShare(moved.y, past.y));
      frame = shifted(at, moved.x, moved.y);
    },
    // The box's outline where it is drawn now, in the window: where its motion has
    // carried it, or its rest.
    outline() {
      const moving = motions.get(box);
      const progress = running[0]?.effect?.getComputedTiming().progress ?? 1;
      if (moving && progress < 1) return interpolate(moving.from, moving.to, progress);
      return boxOf(box.getBoundingClientRect());
    },
    // The box was drawn a moment ago at `rect`, in the window, as the card a comment's
    // Send opens was the field it replaces: the next reading draws the box's outline
    // from there, and reveals each part as that outline's edges reach it.
    /** @param {Box} rect */
    drawnAt(rect) {
      frame = boxOf(root.getBoundingClientRect());
      motions = new Map();
      rests = new Map([[box, boxOf(rect)]]);
    },
    // Nothing stands the box where the next reading could move it from, such as a box
    // no placement stands yet: that reading takes it as it stands.
    forget,
  };
}
