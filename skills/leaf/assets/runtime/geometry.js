/* This module owns the shared readings of visible boxes and clipping, how much of the
 * window the page shows, and the one conversion from viewport boxes to
 * document-positioned chrome. */
import { renderedParent, uiInside, under, upFrom } from "./shadow.js";
import { overlaps, overlapsAcross, union } from "./rect.js";

/* Shared readings of the boxes the page actually shows.

   `shownBox` returns an element's own box or the union of the boxes its
   `display: contents` descendants paint. `shownParts` returns the visible elements on
   which an outline can be drawn, and `shownExtent` the box they cover together.
   `shownRect` clips an element's `shownBox` through scrolling ancestors' visible bands (less the sticky headers stuck over their tops) and the viewport,
   stopping ancestor clipping at a fixed-position box, then takes away what a declared
   occluder stands over (`declareOccluder`). It is what a box may be drawn over, which
   chrome can be: the banner and the shortcut bar are drawn above the page, not cut out
   of it. `seenRect` holds that to the room the chrome leaves (`shownWindow`), and it is
   the one reading of whether the user can see something.
   `clippedRect` applies that same clipping walk to a box measured some other way for an
   element, and `clippedContents` to a box measured from a Range, starting at the element
   that holds the Range and counting that element's own clip. Use:

   - `shownBox` for travel, bounds, and reading-position landmarks;
   - `shownParts` for Ask rings and element-anchor outlines;
   - `shownExtent` for what stands beside a target's parts: a margin row, the
     response field's room;
   - `shownRect` for visible placement of floating chrome and key badges;
   - `seenRect` for whether, and how much of, something is in front of the user;
   - `clippedRect` for an element's box the caller has adjusted;
   - `pagePlaneRect` for the same box drawn by paint in the document plane, which the
     window does not cut;
   - `clippedContents` when the subject has no element box of its own.

   `skipped` is asked first by a reading that can leave out a box the browser is not
   drawing, since reading one in skipped content forces that content's style and layout.

   Do not read `getBoundingClientRect()` directly when the target may generate no box.
   A `display: contents` element reports an origin-like zero rectangle that does not
   represent where its contents are. An area greater than zero is not enough for shown
   parts either: clipped note text and hoisted controls can have measurable boxes while
   remaining the wrong semantic target, which is why `shownParts` takes the bounded
   chrome question (`uiInside`). `unmarkableElements`, in the render checks, detects
   declared items with no visible part on which a mark can land. */
// Where the page's shell ends on the right — the far edge of the room the document has,
// which is what a margin resident is placed against and what the response surface may not
// overhang. The auxiliary surfaces stand over the page and take none of it.
export const shellRight = () => document.body.getBoundingClientRect().right;

// How much of the window the page shows: the visible viewport, less the banner over its
// head and the bottom bar at its foot. Both bars are chrome fixed to the window that
// stand over the page without clipping it, so no clip walk finds them; the owner of each
// declares it here (`declareBanner`, banner.js; `declareBottomBar`,
// keyboard/shortcut-bar.js), and every reading of the room the page has starts from
// `bannerFoot` or `shownWindow` rather than measuring the chrome itself.
//
// The banner's foot is its painted edge, since its declared height (`--lf-banner-h`) is a
// safe-area `calc()` whose serialized value is not a number. The bottom bar is read as
// the boxes standing in it rather than as its
// stated height (`--lf-bottom-bar-h`), because the status rises above a covering panel's
// foot; it bounds only the room its boxes stand across.
//
// The visible viewport is the part of the window the user sees: pinch zoom and a phone's
// software keyboard shrink it without resizing the layout viewport the page and its fixed
// chrome are laid out in, and a surface placed in the layout viewport alone can stand
// under the keyboard. `within` narrows the room to a box the caller keeps to, such as a
// reading region's shown bounds, and `gap` holds what stands in the room that far inside
// each of its edges. `viewport: "layout"` reads the room in the layout viewport instead,
// the window the page scrolls through, for a caller asking whether a scroll has carried
// something out of the page's room rather than whether the user can see it.
let banner = null;
let bottomBar = () => [];
export const declareBanner = (element) => {
  banner = element;
};
export const declareBottomBar = (boxes) => {
  bottomBar = boxes;
};
export const bannerFoot = () => banner?.getBoundingClientRect().bottom ?? 0;
export function shownWindow({ within = null, gap = 0, viewport = "visual" } = {}) {
  const { offsetLeft, offsetTop, width, height } =
    viewport === "visual"
      ? window.visualViewport
      : {
          offsetLeft: 0,
          offsetTop: 0,
          width: document.documentElement.clientWidth,
          height: document.documentElement.clientHeight,
        };
  const left = Math.max(offsetLeft, within?.left ?? -Infinity) + gap;
  const right = Math.min(offsetLeft + width, within?.right ?? Infinity) - gap;
  const top = Math.max(offsetTop, bannerFoot(), within?.top ?? -Infinity) + gap;
  const foot = bottomBar()
    .filter((box) => overlapsAcross(box, { left, right }))
    .map((box) => box.top);
  const bottom =
    Math.min(offsetTop + height, within?.bottom ?? Infinity, ...foot) - gap;
  return new DOMRect(left, top, Math.max(0, right - left), Math.max(0, bottom - top));
}

// Document-anchored chrome is positioned from the document origin, while the boxes it
// follows are read in viewport coordinates. Convert once at that boundary.
export function documentPoint(left, top) {
  return {
    left: left + scrollX,
    top: top + scrollY,
  };
}

// A positioned chip stands on whole pixels. The inline style keeps a length to six
// significant digits, so a fractional place reads back as a nearby one, and a pass that
// computes from what it reads writes a value that differs from what stands while saying
// the same thing. A whole pixel reads back as itself.
export function placeChip(chip, left, top) {
  chip.style.left = `${Math.round(left)}px`;
  chip.style.top = `${Math.round(top)}px`;
}

// The box a positioned chip would take at `at`, a `left` and `top` in its own
// coordinates, read off where it stands now. A placement pass measures a chip at its
// anchor this way rather than moving it there to look, so the chip is written once, to
// where the pass seats it; one not yet placed is put at `at` to be read.
export function boxAt(chip, at) {
  if (!chip.style.left || !chip.style.top) placeChip(chip, at.left, at.top);
  const now = chip.getBoundingClientRect();
  return new DOMRect(
    now.left + at.left - parseFloat(chip.style.left),
    now.top + at.top - parseFloat(chip.style.top),
    now.width,
    now.height,
  );
}

// What a container lets the user see of what it holds, or null where it shows all of
// it. Overflow is one of three ways to draw nothing past an edge: paint containment and
// content-visibility both clip while overflow computes `visible`, and a box under either
// would be drawn at a rect the user never sees. The band itself is the padding box less
// whatever a scrollbar takes — clientLeft and clientWidth, where a border box says
// nothing about either, and a box drawn under a border is drawn nowhere as surely as one
// past the edge.
//
// `page check --render` imports this to ask which container cut a box away, so the
// band a handover is refused against and the band the page paints to are one reading.
// Written twice they disagreed twice, each copy right about one of the two things above
// and wrong about the other.
//
// The element's own document answers, so a sample can ask it of the containing page's
// boxes in that page's viewport coordinates.
export function shownBand(el) {
  const doc = el.ownerDocument;
  // The root element's border box travels with the document, while its scrollport stays
  // pinned to the viewport. Every other scroller's visible band can be derived from its
  // own box; the root is the platform-defined exception.
  if (el === doc.scrollingElement)
    return {
      left: 0,
      top: 0,
      right: doc.documentElement.clientWidth,
      bottom: doc.documentElement.clientHeight,
    };
  const s = doc.defaultView.getComputedStyle(el);
  if (
    s.overflowX === "visible" &&
    s.overflowY === "visible" &&
    !/paint|strict|content/.test(s.contain) &&
    s.contentVisibility === "visible"
  )
    return null;
  const b = el.getBoundingClientRect();
  const left = b.left + el.clientLeft,
    top = b.top + el.clientTop;
  return {
    left,
    top,
    right: left + el.clientWidth,
    bottom: top + el.clientHeight,
  };
}

// The two bands of a scrollport, one reading each, beside the clip they start from.
//
// `visibleBand` is what the user can see through a scroller now: its shown band less the
// sticky headers stuck over its top. A sticky header, such as a page `lf-tabs` strip or
// an `lf-diff` file header, has a stated height and paints over the scroller's contents
// without clipping them, so a band that ignored it would call what is under it shown.
// Which headers stand over a box is a fact of where the box stands, so the band is read
// for one box (`item`), and `headerInset` says how far the headers reach over it. The clip
// walk below applies the same reading at every ancestor, so `shownRect` and the readings
// built on it (read acknowledgement, the summaries a thread card keeps open, arrival
// checks, chrome placement) all answer "on screen" the same way; the place a re-render
// holds asks it of its one scroller directly.
//
// `landingBand` is where a landing may put something: the shown band less the
// `scroll-padding` the scroller declares, which is also what `scrollIntoView` honours.
// It clears what stands over the whole scroller (the banner, a page tab strip); a header
// over part of it, a diff's file header, is cleared by the `scroll-margin` of the rows
// it stands over.
const scrolls = (el) => {
  const { overflowX, overflowY } = getComputedStyle(el);
  return /auto|scroll|hidden/.test(`${overflowX} ${overflowY}`);
};
// How far below the top of `scroller`'s band the view of `el` starts, past the sticky
// headers stuck over it. Each header adds its stated height to `--lf-top` for what it
// stands over (theme.css), so where the `--lf-top` computed at `el` exceeds the
// scroller's own, headers stand over `el`, and their foot is that value below the
// scroller's padding edge, where a sticky box is measured from. The root's own value is
// the banner, which is left to `shownWindow`, so with no header over `el` nothing is
// taken. A header that is not stuck stands above its content anyway, so the reading
// holds whether it is stuck or not. A header sticks in a box that scrolls, so a box that
// only clips (`overflow: clip`, paint containment) has none over it. A stack only grows
// inward, except where a box that scrolls starts it again for what it holds, so `el`
// stands under the larger of its own value and its parent's.
const lfTop = (el) =>
  Number.parseFloat(getComputedStyle(el).getPropertyValue("--lf-top")) || 0;
const holdsHeaders = (el) => el === el.ownerDocument?.scrollingElement || scrolls(el);
export function headerInset(el, scroller) {
  if (!holdsHeaders(scroller) || el === scroller) return 0;
  const parent = upFrom(el);
  const top = Math.max(lfTop(el), parent?.nodeType === 1 ? lfTop(parent) : 0);
  if (top <= lfTop(scroller)) return 0;
  return (Number.parseFloat(getComputedStyle(scroller).paddingTop) || 0) + top;
}
export function visibleBand(scroller, item = null) {
  const band = shownBand(scroller);
  if (!band || !item) return band;
  const top = band.top + headerInset(item, scroller);
  return band.bottom > top ? { ...band, top } : null;
}
export function landingBand(scroller) {
  const band = shownBand(scroller);
  if (!band) return null;
  const inset = landingInsets(scroller);
  return {
    left: band.left + inset.left,
    top: band.top + inset.top,
    right: band.right - inset.right,
    bottom: band.bottom - inset.bottom,
  };
}
// How far each edge of `landingBand` stands in from the scroller's shown band: the
// `scroll-padding` it declares. Callers that measure from the scroller's own box take
// the clearance here rather than reading the style themselves.
export function landingInsets(scroller) {
  const style = getComputedStyle(scroller);
  const inset = (side) => Number.parseFloat(style[`scrollPadding${side}`]) || 0;
  return {
    top: inset("Top"),
    right: inset("Right"),
    bottom: inset("Bottom"),
    left: inset("Left"),
  };
}
// Whether `el` stands in content the browser skips: what a `content-visibility: hidden`
// box holds, which a hidden tab's panel (`hidden="until-found"`) is, and a closed
// disclosure's content. The browser leaves skipped content unstyled and unlaid, and one
// question about any box inside — its computed style, its rect, its scroll offsets —
// makes it style and lay out that whole subtree first to answer. On the corpus, whose
// examples each stand in a hidden tab, those forced passes were most of a revision's
// style time. So a reading that has nothing to say about a box on no screen — where it
// stands, whether it scrolls, what room it takes — asks this first and leaves the box
// out until a pass after it is drawn: revealing a panel or opening a disclosure resizes
// what holds it, which brings those passes round. A reading that marks what the user
// will see once it is drawn (an anchor's outline) still asks, and pays.
//
// Answered without forcing anything: `checkVisibility` reads the tree the browser has,
// and is false for a box that is not drawn for any reason. The nearest drawn ancestor
// says which reason — a box skipping what it holds, or `display: none`/`contents` on
// the way down, which are not skipped and cheap to ask about — and it is drawn, so its
// own style is not skipped either. A disclosure skips through a pseudo-element of its
// own, so it is asked by its state rather than by its style.
export function skipped(el) {
  if (el.checkVisibility()) return false;
  let child = el;
  let box = renderedParent(el);
  while (box && !box.checkVisibility()) {
    child = box;
    box = renderedParent(box);
  }
  if (!box) return false;
  if (box.localName === "details") return !box.open && child.localName !== "summary";
  return getComputedStyle(box).contentVisibility === "hidden";
}
// The box an element shows as. An element that generates none of its own — a
// display: contents wrapper — shows as what its contents paint, so its bounds are
// theirs, and a range asks the platform for that union in one read. Its own rect is
// (0,0) at the document's origin, which is not a degenerate box but a wrong one: it
// reads as a real place at the top of the page, so whatever measured it travelled there.
//
// No widget in the vocabulary is one now — lf-suggestion was, and its theme comment
// carries what that cost — but the wrong answer is the platform's rather than that
// widget's: a page or a project layer styles any wrapper this way in a line. This
// lived inside the legend's own reading once, where it stood as a fact about the
// legend rather than about elements, which is exactly why the travel went on asking
// the element directly and centred the top of the document. One answer to "where is
// this element", so there is no second way to ask.
export function shownBox(el) {
  if (el === document.scrollingElement)
    return {
      x: 0,
      y: 0,
      left: 0,
      top: 0,
      right: document.documentElement.clientWidth,
      bottom: document.documentElement.clientHeight,
      width: document.documentElement.clientWidth,
      height: document.documentElement.clientHeight,
    };
  const r = el.getBoundingClientRect();
  if (r.width || r.height) return r;
  const contents = document.createRange();
  contents.selectNodeContents(el);
  return contents.getBoundingClientRect();
}
// The same reading in elements rather than pixels, for the marks the runtime paints on
// the page's own elements: an outline needs a box to hang on, so a mark aimed at a
// boxless element goes to the boxes its contents make. Read from the platform rather
// than from the registry, because generating no box is not a fact about which widget
// this is — any wrapper in any layer can do it, and CSS has no selector that says so.
//
// Area, where shownBox asks only for a box, because the two want different things of
// one: bounds are bounds whichever dimension is flat, while a ring is only worth hanging
// where it can be seen.
//
// The runtime's own chrome leaves by name rather than on that test. Area read as though
// it were doing the job, and it was doing it by luck: a suggestion hangs its controls off
// a span with no width, so the apparatus fell out on its own. The line saying how many
// comments a block holds is clipped to a pixel and has one — so a decision that had been
// commented on wore its ring on the runtime's word about the page rather than on the
// page, and the pixel it hung from moves the first time a comment lands. That question is
// already asked, declared labels and all, and it is the one the anchor pass puts
// to a text node — so what a mark hangs on and what a quote may name cannot come apart.
// Bounded at the element, for the reason given where the question is stated: a widget an
// agent sent stands inside the panel, and asked about the page instead it would have no
// child of its own left to fall back to.
export function shownParts(el) {
  const r = el.getBoundingClientRect();
  if (r.width && r.height) return [el];
  return [...el.children]
    .filter((child) => !uiInside(child, el))
    .flatMap((child) => shownParts(child));
}
// The box an element's shown parts cover together: a mark hung on the element stands at
// its corner, so a comment on one shape of a drawing stands on that shape rather than at
// the drawing's edge. An element with no shown part has none.
export const shownExtent = (el) =>
  union(shownParts(el).map((part) => part.getBoundingClientRect()));
// An item's bounds, held to what the page shows of them: the rect a box in the chrome's
// layer is drawn from, for the aim's box and the legend's alike. The layer is one no
// ancestor's clip can reach — that is the point of it — so the box owes the clips an
// answer of its own: an option's table box runs on under its group's overflow: hidden,
// and a card half-scrolled out of a board is half gone. A box drawn from the raw rect
// claims pixels the page has already refused, over the neighbour standing in them.
// The root scrollport's viewport band is one of these too: what is scrolled off screen
// has no rect, and a legend draws boxes for what is on it and nothing for the rest.
//
// The walk stops at a box the viewport holds rather than the document: nothing above a
// `position: fixed` element clips it, so the ancestors past that one are answering about a
// flow the element left. Every box in the chrome is behind one — the thread panel is
// fixed, so a reply box measured through the page flow's ancestors came back wholly clipped
// away whenever the page had scrolled. The one caller before this asked
// only about the page's own items, none of which is ever inside a fixed box, which is why
// the walk could be written as "every ancestor" and read as complete.
//
// Which leaves the viewport itself, applied to everything: for a box in the page it is
// the root's band, and for one in a fixed layer it is the whole of what clips it.
//
// `clips` caches each ancestor's answer for one pass: the legend asks for every item
// on the page in one breath, and the items share their scrollers, so what a pass spends
// on the walk is two style reads per ancestor rather than two per item per ancestor.
export function shownRect(item, clips) {
  return clippedRect(shownBox(item), item, clips);
}
// What of an item the user sees: what every box over it lets through, within the room the
// chrome leaves. `within` keeps a bottom-bar box from cutting the item unless it stands
// across it. The chrome cuts the item's top and foot only; its sides stay shownRect's, the
// layout viewport's, since a pinch zoom's visual viewport is a pan across the page and not
// a clip — read with its sides, a message wider than the zoomed view was never seen whole
// across, and never counted read. Null when none of it shows.
export function seenRect(item, clips) {
  const shown = shownRect(item, clips);
  if (!shown) return null;
  const room = shownWindow({ within: shown });
  return room.width > 0 && room.height > 0
    ? { left: shown.left, top: room.top, right: shown.right, bottom: room.bottom }
    : null;
}
// Where a member begins, as the user sees it: the first of the boxes it paints that
// survives the clips, rather than the bounds of all of them. They are the same box for
// anything in flow and different for an inline that wraps, whose bounds run from the
// column's left margin to its right — so a digit placed on that corner sat four hundred
// pixels from the link it addressed, a line above it, on top of somebody else's sentence.
// `shownBox`'s union answers "how much room does this take", which is what a legend box and
// an aim outline want; this answers "where does it start", which is what anything hung on a
// corner wants. The first that survives rather than the first outright, since a link whose
// opening line has scrolled away still has a corner on the line below it.
export const startsAt = (item, clips) => {
  const fragments = item.getClientRects();
  return (fragments.length ? [...fragments] : [shownBox(item)])
    .map((box) => clippedRect(box, item, clips))
    .find(Boolean);
};
// The clips standing over a box, applied to it. Taken apart from shownRect because the two
// readings above and a painted Range want the same walk over different boxes.
export const clippedRect = (box, item, clips) => clipped(box, item, clips, false);
// The same walk for paint that stands in the document plane, which a root scroll carries
// with the page: the page's own boxes cut it, and the window does not, since cutting it
// there moves the cut with every scroll and has the paint written again for each one.
// A header stuck over the root's edge still cuts it, since it stands over the page.
export const pagePlaneRect = (box, item, clips) =>
  clipped(box, item, clips, false, false);
// The same walk for a box measured from what an element holds: a Range inside it. The
// holder's own band stands over its contents, where it says nothing about the holder's
// own box, so text scrolled out of the `pre` it sits in directly is text nobody sees.
export const clippedContents = (box, holder, clips) =>
  clipped(box, holder, clips, true);
function clipped(box, item, clips, held, inWindow = true) {
  let left = inWindow ? Math.max(box.left, 0) : box.left,
    top = inWindow ? Math.max(box.top, 0) : box.top,
    right = inWindow ? Math.min(box.right, innerWidth) : box.right,
    bottom = inWindow ? Math.min(box.bottom, innerHeight) : box.bottom;
  // From the box itself, not from its parent: an element is not clipped by its own
  // overflow — that clips what it holds — so its band is skipped and only its position is
  // read. Starting at the parent instead asked the question of every ancestor of a fixed
  // box and never of the box, which is the same bug one level up: in design mode the aim
  // resolves the thread panel itself, and the panel measured through body's band came
  // back wholly clipped away, so a mode whose row promises a click on the chrome drew
  // nothing over the chrome.
  // Cross an open shadow boundary through its host. A package surface rendered in a
  // declared shadow stage is still clipped by that host and by the page containers
  // outside it; stopping at the ShadowRoot would let chrome paint where the package
  // itself cannot.
  // The box just inside each scroller, where the sticky headers over its top are read
  // (`headerInset`): the item at its own scroller, and the scroller below at each one
  // further out.
  let inner = item;
  for (let a = item; a; a = upFrom(a)) {
    let c = clips.get(a);
    if (c === undefined) {
      clips.set(
        a,
        (c = {
          band: shownBand(a),
          // Read here rather than out of shownBand, whose answer is a band and is the
          // render gate's too: what clips a box and what a box is positioned against are
          // two facts, and one of them is this walk's alone.
          fixed: getComputedStyle(a).position === "fixed",
          scrolls: holdsHeaders(a),
        }),
      );
    }
    if ((held || a !== item) && c.band) {
      const covered = c.band.top + headerInset(inner, a);
      if (covered >= c.band.bottom) return null;
      let band = covered > c.band.top ? { ...c.band, top: covered } : c.band;
      // In the page's plane the root's band is the window, which cuts nothing there;
      // only a header stuck over its top does.
      if (!inWindow && a === a.ownerDocument?.scrollingElement)
        band = {
          left: -Infinity,
          top: band.top > c.band.top ? band.top : -Infinity,
          right: Infinity,
          bottom: Infinity,
        };
      left = Math.max(left, band.left);
      top = Math.max(top, band.top);
      right = Math.min(right, band.right);
      bottom = Math.min(bottom, band.bottom);
      if (c.scrolls) inner = a;
    }
    if (c.fixed) break;
  }
  return right > left && bottom > top
    ? occluded({ left, top, right, bottom }, item, clips)
    : null;
}

// A surface that stands over the page without clipping it: the thread panel, over the
// right of a live page at a desktop window. Nothing in the page's own tree says so,
// since the surface is fixed chrome beside the page rather than an ancestor of what it
// stands over, so the surface declares itself. The
// clip walk then takes what it stands over away from any box stacked beneath it, and a
// travel destination, an exposure reading, and a badge's placement all read the part
// under it as hidden. What the surface holds is its own to show, and what stacks above
// it (a door's menu, the key-badge layer, the top layer) is drawn over it rather than
// hidden by it.
//
// What is left of a box is a box: the largest rectangle of it the occluder leaves, so
// every pixel of the answer is one the user sees, and a box the occluder reaches into
// reads as less than whole.
const occluders = new Set();
// An occluder on its way out (motion.js, `slide`) covers nothing the user is reading past.
export const LEAVING = "data-lf-leaving";
// Where an occluder stands, not where its slide has carried it this frame: every declared
// occluder is fixed to the window, so its offset box is its viewport box without the
// slide's transform.
const standingBox = (surface) => ({
  left: surface.offsetLeft,
  top: surface.offsetTop,
  right: surface.offsetLeft + surface.offsetWidth,
  bottom: surface.offsetTop + surface.offsetHeight,
});
export const declareOccluder = (surface) => {
  occluders.add(surface);
  return () => occluders.delete(surface);
};
// A clip pass that reads past some occluders. Travel asks what the page shows of a
// destination beside the surface it leaves standing, which is the most any movement of
// the page can show while that surface stands.
const PAST = Symbol("past");
export const clipsPast = (surfaces) => new Map([[PAST, new Set(surfaces)]]);
// Whether an occluder hides a destination, an element or a Range, wherever travel lands
// it: whether it stands over most of it, more than half its width. A block the width of
// the column keeps most of itself clear of the thread panel at a desktop window and is
// seen where it stands, beside the panel; words at the right end of a line, or a box in
// the right margin, land under it. The one kind declared stands the window's height at
// one side of it, and travel moves a destination along its scroller's block axis only,
// so the question is the inline one, asked of what the page's clips leave of the
// destination. One scrolled out of the window is asked it at its own box, which is
// where the landing will bring it into view.
export function hides(surface, where) {
  const holder = placeHolder(where);
  if (
    !holder ||
    !occluders.has(surface) ||
    surface.hasAttribute(LEAVING) ||
    !surface.checkVisibility()
  )
    return false;
  if (under(holder, surface) || stackLevel(holder) >= stackLevel(surface)) return false;
  const box = where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
  const seen =
    where instanceof Range
      ? clippedContents(box, holder, clipsPast([surface]))
      : clippedRect(box, holder, clipsPast([surface]));
  const { left, right } = seen ?? box;
  const column = standingBox(surface);
  const covered = Math.min(right, column.right) - Math.max(left, column.left);
  return covered > (right - left) / 2;
}
// The element a destination is measured through: itself, or the element holding a
// Range's start.
export const placeHolder = (where) =>
  where instanceof Range
    ? where.startContainer instanceof Element
      ? where.startContainer
      : where.startContainer.parentElement
    : where;
// Where a box stacks among the page's root-level layers: the z-index of its outermost
// positioned ancestor that sets one, and above all of them in the top layer.
function stackLevel(node) {
  let level = 0;
  for (let a = node; a; a = upFrom(a)) {
    if (a.matches(":popover-open, dialog:modal")) return Infinity;
    const { position, zIndex } = getComputedStyle(a);
    if (position !== "static" && zIndex !== "auto") level = Number(zIndex);
  }
  return level;
}
const OCCLUDERS = Symbol("occluders");
function standingOccluders(clips) {
  let standing = clips.get(OCCLUDERS);
  if (standing) return standing;
  const past = clips.get(PAST);
  standing = [...occluders]
    .filter(
      (surface) =>
        surface.isConnected &&
        !surface.hasAttribute(LEAVING) &&
        surface.checkVisibility(),
    )
    .filter((surface) => !past?.has(surface))
    .map((surface) => ({
      surface,
      box: standingBox(surface),
      level: stackLevel(surface),
    }));
  clips.set(OCCLUDERS, standing);
  return standing;
}
const area = (box) => (box.right - box.left) * (box.bottom - box.top);
function occluded(rect, item, clips) {
  for (const { surface, box, level } of standingOccluders(clips)) {
    if (!overlaps(rect, box) || under(item, surface) || stackLevel(item) >= level)
      continue;
    const sides = [
      { ...rect, right: Math.min(rect.right, box.left) },
      { ...rect, left: Math.max(rect.left, box.right) },
      { ...rect, bottom: Math.min(rect.bottom, box.top) },
      { ...rect, top: Math.max(rect.top, box.bottom) },
    ].filter((side) => side.right > side.left && side.bottom > side.top);
    if (!sides.length) return null;
    rect = sides.reduce((most, side) => (area(side) > area(most) ? side : most));
  }
  return rect;
}
