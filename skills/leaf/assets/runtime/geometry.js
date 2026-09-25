/* This module owns the shared readings of visible boxes and clipping, and the one
 * conversion from viewport boxes to document-positioned chrome. */
import { sizeObserver } from "./rendering.js";
import { setRuntimeRootStyle } from "./root-state.js";
import { uiInside, under, upFrom } from "./shadow.js";

/* Shared readings of the boxes the page actually shows.

   `shownBox` returns an element's own box or the union of the boxes its
   `display: contents` descendants paint. `shownParts` returns the visible elements on
   which an outline can be drawn. `shownRect` clips the result through scrolling
   ancestors' visible bands (less the stuck covers over their edges) and the viewport,
   stopping ancestor clipping at a fixed-position box, then takes away what a declared
   occluder stands over (`declareOccluder`); it is the one reading of whether something
   is on screen.
   `clippedRect` applies that same clipping walk to a box measured some other way for an
   element, and `clippedContents` to a box measured from a Range, starting at the element
   that holds the Range and counting that element's own clip. Use:

   - `shownBox` for travel, bounds, and reading-position landmarks;
   - `shownParts` for Ask rings and element-anchor outlines;
   - `shownRect` for visible placement of floating chrome and key badges;
   - `clippedRect` for an element's box the caller has adjusted;
   - `clippedContents` when the subject has no element box of its own.

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
// Whether two boxes share any pixel. The one spelling of a question three chrome passes
// ask: placement, badge reservation, and the clear part left of a box behind furniture.
export const overlaps = (a, b) =>
  a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;

// Document-anchored chrome is positioned from the document origin, while the boxes it
// follows are read in viewport coordinates. Convert once at that boundary.
export function documentPoint(left, top) {
  return {
    left: left + scrollX,
    top: top + scrollY,
  };
}

// What a container lets the user see of what it holds, or null where it shows all of
// it. Overflow is one of three ways to draw nothing past an edge: paint containment and
// content-visibility both clip while overflow computes `visible`, and a box under either
// would be drawn at a rect the user never sees. The band itself is the padding box less
// whatever a scrollbar takes — clientLeft and clientWidth, where a border box says
// nothing about either, and a box drawn under a border is drawn nowhere as surely as one
// past the edge.
//
// `version check --render` imports this to ask which container cut a box away, so the
// band a handover is refused against and the band the page paints to are one reading.
// Written twice they disagreed twice, each copy right about one of the two things above
// and wrong about the other.
//
// The element's own document answers, so a specimen can ask it of the containing page's
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
// `visibleBand` is what the user can see through a scroller now: its shown band less
// the covers stuck over an edge of it. A cover is a sticky box declared through
// `declareCoverRoom` (below): the thread list's run headings, an `lf-diff` file header,
// a root `lf-tabs` strip.
// Stuck, it paints over the scroller's contents without clipping them, so a band that
// ignored it would call what is under it shown. The clip walk below applies this band at
// every ancestor, so `shownRect` and the readings built on it (read acknowledgement, the
// summaries a thread card keeps open, arrival checks, chrome placement) all answer "on
// screen" the same way; the place a re-render holds asks it of its one scroller directly.
//
// A cover belongs to the scroller it sticks in, found by climbing out of shadow trees
// as the clip walk does: a run heading inside the thread list is that list's, not the
// document's, though the document holds it too. And a cover does not hide itself or what
// it holds, so the band a node inside one is read against (`item`) leaves that cover out.
//
// `landingBand` is where a landing may put something: the shown band less the
// `scroll-padding` the scroller declares, which is also what `scrollIntoView` honours.
// It reserves room for the tallest cover wherever one might stick, so it is never wider
// than the visible band a landing arrives in.
export const PINNED = ".lf-pinned";
const scrolls = (el) => {
  const { overflowX, overflowY } = getComputedStyle(el);
  return /auto|scroll|hidden/.test(`${overflowX} ${overflowY}`);
};
// The scroller a sticky box sticks in: its nearest scrolling ancestor, else the root.
const stuckIn = (cover) => {
  for (let a = upFrom(cover); a && a !== document.documentElement; a = upFrom(a))
    if (scrolls(a)) return a;
  return document.scrollingElement;
};
// Every shown cover's box, by the scroller it sticks in, with the sticky insets it is
// held at (insetBand). Built once per clip pass, since a pass asks it at each ancestor of
// every item. A detached cover is only skipped: its observer lets it go, and a cover put
// back and declared again must still be one.
const COVERS = Symbol("covers");
function coversByScroller(clips = null) {
  let index = clips?.get(COVERS);
  if (index) return index;
  index = new Map();
  for (const cover of declaredCovers) {
    if (!cover.isConnected || !cover.checkVisibility()) continue;
    const scroller = stuckIn(cover);
    if (!index.has(scroller)) index.set(scroller, []);
    const { left, right, top, bottom } = cover.getBoundingClientRect();
    const style = getComputedStyle(cover);
    index.get(scroller).push({
      cover,
      box: {
        left,
        right,
        top,
        bottom,
        stickyTop: Number.parseFloat(style.top) || 0,
        stickyBottom: Number.parseFloat(style.bottom) || 0,
      },
    });
  }
  clips?.set(COVERS, index);
  return index;
}
const bandLess = (band, covers, item) =>
  insetBand(
    band,
    covers.filter(({ cover }) => !item || !under(item, cover)).map(({ box }) => box),
  );
export function visibleBand(scroller, item = null) {
  const band = shownBand(scroller);
  return band && bandLess(band, coversByScroller().get(scroller) ?? [], item);
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
  measureUnseenCovers(scroller);
  const style = getComputedStyle(scroller);
  const inset = (side) => Number.parseFloat(style[`scrollPadding${side}`]) || 0;
  return {
    top: inset("Top"),
    right: inset("Right"),
    bottom: inset("Bottom"),
    left: inset("Left"),
  };
}
// Declaring a box's covers does two things. Each becomes a cover for `visibleBand`, and
// the room they take is kept on the box as a custom property, so the `scroll-padding` or
// `scroll-margin` that reads it reserves that room for every native landing (and a
// scroller's `scroll-padding` for the runtime's own, through `landingInsets`). How tall
// a cover is is a measurement rather than a constant: a heading or a file path wraps,
// and the user sets the width by drawing a panel's edge, which posts no event. So the
// covers are observed rather than measured by whoever renders them, and a declaration
// that replaces covers forces no layout. Only a host's first covers are measured as
// they are declared, since a first observation comes after the frame's layout: a
// document's initial fragment landing reads the room in that window, and read as none
// it stopped a root tab strip's height short, under the strip. A cover that replaces
// another starts at the room its host already keeps. The tallest is the room, since a
// landing cannot know which cover will stick
// over it. A cover that stops rendering (its panel shut) keeps the room it last
// measured, so a frame that runs before the reopening's observation reads the room
// rather than none. A cover first declared while its panel was shut has measured
// nothing, and the frame after that panel's first opening would read its room as none;
// so a landing's reading of the host's insets measures any cover shown but not yet
// measured shown, before the observer's first report of it. Called again with the box's
// current covers, it replaces the set; a cover that leaves the document is let go on its
// own.
const declaredCovers = new Set();
const coverRooms = new WeakMap();
const coverHosts = new WeakMap();
const unseenCovers = new WeakSet();
let coverObserver = null;
const paintCoverRoom = (host) => {
  const { property, covers } = coverRooms.get(host);
  const room = `${Math.max(0, ...covers.values())}px`;
  // The document root's inline style is shared with the authored revision, which keeps
  // only what the runtime registered as its own (root-state.js).
  if (host === document.documentElement) setRuntimeRootStyle(host, property, room);
  else host.style.setProperty(property, room);
};
const letGo = (cover) => {
  coverObserver.unobserve(cover);
  declaredCovers.delete(cover);
};
export function declareCoverRoom(host, property, covers) {
  coverObserver ??= sizeObserver((entries) => {
    const touched = new Set();
    for (const { target, borderBoxSize } of entries) {
      const host = coverHosts.get(target);
      const room = host && coverRooms.get(host);
      if (!room?.covers.has(target)) continue;
      if (!target.isConnected) {
        letGo(target);
        room.covers.delete(target);
      } else if (target.checkVisibility()) {
        room.covers.set(target, borderBoxSize[0]?.blockSize ?? 0);
        unseenCovers.delete(target);
      } else continue;
      touched.add(host);
    }
    for (const host of touched) paintCoverRoom(host);
  });
  const prior = coverRooms.get(host)?.covers ?? new Map();
  const next = new Map();
  const kept = Math.max(0, ...prior.values());
  const fresh = [];
  for (const cover of covers) {
    next.set(cover, prior.get(cover) ?? kept);
    if (prior.has(cover)) continue;
    fresh.push(cover);
    unseenCovers.add(cover);
    coverHosts.set(cover, host);
    declaredCovers.add(cover);
    coverObserver.observe(cover);
  }
  const left = [...prior.keys()].filter((cover) => !next.has(cover));
  for (const cover of left) letGo(cover);
  coverRooms.set(host, { property, covers: next });
  if (!prior.size) measureUnseenCovers(host, false);
  if (fresh.length || left.length) paintCoverRoom(host);
}
function measureUnseenCovers(host, paint = true) {
  const room = coverRooms.get(host);
  if (!room) return;
  let measured = false;
  for (const cover of room.covers.keys())
    if (unseenCovers.has(cover) && cover.isConnected && cover.checkVisibility()) {
      room.covers.set(cover, cover.getBoundingClientRect().height);
      unseenCovers.delete(cover);
      measured = true;
    }
  if (measured && paint) paintCoverRoom(host);
}
// A band less the covers standing over its edges. A cover stands over the top edge when
// it straddles it, and a cover resting on another stuck cover straddles the edge the
// first one leaves, so the covers are taken in order from the edge inward. A cover in
// the middle of the band is content passing through, not chrome over it. Null once the
// covers leave no band.
//
// A cover may also be stuck short of the edge, at the sticky inset it is held at
// (`stickyTop`, `stickyBottom`, 0 when absent): a document's covers stick under the
// banner, so they never reach the root's top edge, and read by straddling alone a
// stuck root tab strip or `lf-diff` file header hid nothing. Such a cover takes the
// band from the edge to its far side, the inset with it. The inset is room kept clear
// for something standing there, the banner in a live page.
export function insetBand(band, covers) {
  const across = covers.filter(
    (cover) => cover.left < band.right && cover.right > band.left,
  );
  let { top, bottom } = band;
  for (const cover of [...across].sort((a, b) => a.top - b.top))
    if (
      (cover.top <= top || cover.top <= band.top + (cover.stickyTop ?? 0)) &&
      cover.bottom > top
    )
      top = cover.bottom;
  for (const cover of [...across].sort((a, b) => b.bottom - a.bottom))
    if (
      (cover.bottom >= bottom ||
        cover.bottom >= band.bottom - (cover.stickyBottom ?? 0)) &&
      cover.top < bottom
    )
      bottom = cover.top;
  return bottom > top ? { ...band, top, bottom } : null;
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
// The same walk for a box measured from what an element holds: a Range inside it. The
// holder's own band stands over its contents, where it says nothing about the holder's
// own box, so text scrolled out of the `pre` it sits in directly is text nobody sees.
export const clippedContents = (box, holder, clips) =>
  clipped(box, holder, clips, true);
function clipped(box, item, clips, held) {
  let left = Math.max(box.left, 0),
    top = Math.max(box.top, 0),
    right = Math.min(box.right, innerWidth),
    bottom = Math.min(box.bottom, innerHeight);
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
  for (let a = item; a; a = upFrom(a)) {
    let c = clips.get(a);
    if (c === undefined) {
      const band = shownBand(a);
      clips.set(
        a,
        (c = {
          band,
          // What stands over the band's edges without clipping it (visibleBand).
          covers: band ? (coversByScroller(clips).get(a) ?? []) : [],
          // Read here rather than out of shownBand, whose answer is a band and is the
          // render gate's too: what clips a box and what a box is positioned against are
          // two facts, and one of them is this walk's alone.
          fixed: getComputedStyle(a).position === "fixed",
        }),
      );
    }
    if ((held || a !== item) && c.band) {
      const band = c.covers.length ? bandLess(c.band, c.covers, item) : c.band;
      if (!band) return null;
      left = Math.max(left, band.left);
      top = Math.max(top, band.top);
      right = Math.min(right, band.right);
      bottom = Math.min(bottom, band.bottom);
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
// stands over, so the surface declares itself, as a sticky cover declares its room. The
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
export const declareOccluder = (surface) => occluders.add(surface);
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
