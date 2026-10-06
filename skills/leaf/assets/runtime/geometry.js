/* This module owns the shared readings of visible boxes and clipping, how much of the
 * window the page shows, and the one conversion from viewport boxes to
 * document-positioned chrome. */
import { renderedParent, uiInside, under, upFrom } from "./shadow.js";
import { overlaps, overlapsAcross, union, clippingAxes } from "./rect.js";

/* Shared readings of the boxes the page actually shows.

   `shownBox` returns an element's own box or the union of the boxes its
   `display: contents` descendants paint. `shownParts` returns the visible elements on
   which an outline can be drawn, and `shownExtent` the box they cover together.
   `shownRect` clips an element's `shownBox` through scrolling ancestors' visible bands (less the sticky headers stuck over their tops) and the viewport,
   following native positioned containing blocks past intermediate overflow clips,
   then takes away what a declared occluder stands over (`declareOccluder`). It is what a box may be drawn over, which
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
   - `seenRect` for whether, and how much of, something is in front of the user, and
     `whenOffScreen` to hear when all of something has left the window;
   - `clippedRect` for an element's box the caller has adjusted;
   - `pagePlaneRect` for the same box in the document plane, which the window does
     not cut;
   - `paintClips` for what cuts paint standing over an element, each cut in the plane
     of the box it belongs to;
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
//
// A chip stands in the plane of what holds it: its layer's, where the scroll that carries
// the layer carries it, or the window's (`held`), where the window's edge or the banner
// holds it in, so that a scroll leaves it standing. A held chip in a layer the document
// carries would otherwise be carried by each scroll frame and placed back. Its `left`
// and `top` are in its layer's coordinates either way.
export function placeChip(chip, left, top, held = false) {
  const origin = held ? chip.parentElement.getBoundingClientRect() : null;
  if (held) chip.style.position = "fixed";
  else chip.style.removeProperty("position");
  chip.style.left = `${Math.round(left + (origin?.left ?? 0))}px`;
  chip.style.top = `${Math.round(top + (origin?.top ?? 0))}px`;
}

// Where a chip's inline `left` and `top` are measured from, in its layer's coordinates.
const chipOrigin = (chip) =>
  chip.style.position === "fixed"
    ? chip.parentElement.getBoundingClientRect()
    : { left: 0, top: 0 };

// The box a positioned chip would take at `at`, a `left` and `top` in its layer's
// coordinates, read off where it stands now. A placement pass measures a chip at its
// anchor this way rather than moving it there to look, so the chip is written once, to
// where the pass seats it; one not yet placed is put at `at` to be read.
export function boxAt(chip, at) {
  if (!chip.style.left || !chip.style.top) placeChip(chip, at.left, at.top);
  const now = chip.getBoundingClientRect();
  const origin = chipOrigin(chip);
  return new DOMRect(
    now.left + at.left - (parseFloat(chip.style.left) - origin.left),
    now.top + at.top - (parseFloat(chip.style.top) - origin.top),
    now.width,
    now.height,
  );
}

// One local scroll pixel's viewport displacement. Scroll offsets are in layout pixels;
// a scaled or rotated scrollport carries its contents along transformed axes. Browser
// matrices compose through the same rendered ancestry used by clipping, across slots
// and shadow roots. Origins and translations do not change these direction vectors.
export function scrollAxes(source) {
  if (source === source.ownerDocument.scrollingElement)
    return { x: { x: 1, y: 0 }, y: { x: 0, y: 1 } };
  let matrix = new window.DOMMatrix();
  for (let node = source; node instanceof Element; node = renderedParent(node)) {
    const style = getComputedStyle(node);
    let local = new window.DOMMatrix();
    if (style.rotate !== "none") {
      const parts = style.rotate.split(" ");
      const angle = parts.pop();
      const degrees =
        parseFloat(angle) *
        (angle.endsWith("turn")
          ? 360
          : angle.endsWith("grad")
            ? 0.9
            : angle.endsWith("rad")
              ? 180 / Math.PI
              : 1);
      const axis =
        parts.length === 3
          ? parts.map(Number)
          : parts[0] === "x"
            ? [1, 0, 0]
            : parts[0] === "y"
              ? [0, 1, 0]
              : [0, 0, 1];
      local = local.rotateAxisAngle(...axis, degrees);
    }
    if (style.scale !== "none") {
      const scale = style.scale.split(" ").map(Number);
      local = local.scale(scale[0], scale[1] ?? scale[0], scale[2] ?? 1);
    }
    if (style.transform !== "none")
      local = local.multiply(new window.DOMMatrix(style.transform));
    const zoom = Number(style.zoom);
    local = local.scale(zoom, zoom);
    matrix = local.multiply(matrix);
  }
  return { x: { x: matrix.a, y: matrix.b }, y: { x: matrix.c, y: matrix.d } };
}

// Convert a viewport reveal movement into the scrollport's own layout offsets. A
// one-axis scroller uses that axis's projected displacement; a two-axis scroller uses
// the inverse basis, so rotated horizontal motion never becomes a vertical-only guess.
export function localScrollBy(source, { x, y }) {
  const axes = scrollAxes(source);
  const horizontal = source.scrollWidth > source.clientWidth;
  const vertical = source.scrollHeight > source.clientHeight;
  const along = (axis) => {
    const amounts = [
      ...(x && axis.x ? [x / axis.x] : []),
      ...(y && axis.y ? [y / axis.y] : []),
    ];
    return amounts.reduce(
      (move, amount) => (Math.abs(amount) > Math.abs(move) ? amount : move),
      0,
    );
  };
  if (!horizontal) return { left: 0, top: vertical ? along(axes.y) : 0 };
  if (!vertical) return { left: along(axes.x), top: 0 };
  const determinant = axes.x.x * axes.y.y - axes.x.y * axes.y.x;
  return {
    left: (x * axes.y.y - y * axes.y.x) / determinant,
    top: (y * axes.x.x - x * axes.x.y) / determinant,
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
  const axes = clippingAxes(s);
  if (!axes.x && !axes.y) return null;
  const b = el.getBoundingClientRect();
  const scaleX = el.offsetWidth ? b.width / el.offsetWidth : 1;
  const scaleY = el.offsetHeight ? b.height / el.offsetHeight : 1;
  const left = b.left + el.clientLeft * scaleX,
    top = b.top + el.clientTop * scaleY;
  return {
    left,
    top,
    right: left + el.clientWidth * scaleX,
    bottom: top + el.clientHeight * scaleY,
  };
}

// The two bands of a scrollport, one reading each, beside the clip they start from.
//
// `visibleBand` is what the user can see through a scroller now: its shown band less the
// sticky headers stuck over its top and the sticky footers over its foot. A sticky
// header, such as a page `lf-tabs` strip or an `lf-diff` file header, has a stated
// height and paints over the scroller's contents without clipping them, so a band that
// ignored it would call what is under it shown. Which headers stand over a box is a fact
// of where the box stands, so the band is read for one box (`item`), and `headerInset`
// says how far the headers reach over it, as `footerInset` says for footers, such as a
// long thread's pinned reply row. The clip walk below applies the same reading at every
// ancestor, so `shownRect` and the readings built on it (read acknowledgement, the
// summaries a thread card keeps open, arrival checks, chrome placement) all answer "on
// screen" the same way; the place a re-render holds asks it of its one scroller
// directly.
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
// taken. A header that is not stuck stands above its content, so the reading holds
// whether it is stuck or not, except at the end of what the header stands over, where
// the header is pushed up with it and the reading still counts its height as covered. A
// header sticks in a box that scrolls, so a box that only clips (`overflow: clip`, paint
// containment) has none over it. A box that scrolls starts `--lf-top` again for what it
// holds, so it is read where it stands, at its parent; a header's holder puts the
// stacked value on a box that does not scroll (theme.css, at `--lf-top`).
const holdsHeaders = (el) => el === el.ownerDocument?.scrollingElement || scrolls(el);
const edgeInset = (el, scroller, slot, padding) => {
  if (!holdsHeaders(scroller) || el === scroller) return 0;
  const at = el.nodeType === 1 && scrolls(el) ? upFrom(el) : el;
  const read = (box) =>
    Number.parseFloat(getComputedStyle(box).getPropertyValue(slot)) || 0;
  const inset = at?.nodeType === 1 ? read(at) : 0;
  if (inset <= read(scroller)) return 0;
  return (Number.parseFloat(getComputedStyle(scroller)[padding]) || 0) + inset;
};
export const headerInset = (el, scroller) =>
  edgeInset(el, scroller, "--lf-top", "paddingTop");
// The same reading at the foot, for a box sticking there (`--lf-bottom`, theme.css):
// how far above the bottom of `scroller`'s band the view of `el` ends.
export const footerInset = (el, scroller) =>
  edgeInset(el, scroller, "--lf-bottom", "paddingBottom");
export function visibleBand(scroller, item = null) {
  const band = shownBand(scroller);
  if (!band || !item) return band;
  const top = band.top + headerInset(item, scroller);
  const bottom = band.bottom - footerInset(item, scroller);
  return bottom > top ? { ...band, top, bottom } : null;
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
// Positioned descendants escape intermediate overflow clips up to their native
// containing block. The viewport holds a fixed box with no offsetParent; a transformed,
// filtered or layout-contained ancestor instead holds it and still clips its contents.
// Absolute boxes follow the same containing-block boundary. A DOM ancestor's overflow
// does not clip a box whose containing block lies outside that ancestor.
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
// Calls `leave` each time none of `nodes` shows in the window any longer, and returns
// the step that stops watching. The window here is the browser's, which the chrome does
// not cut, so a box wholly under the banner still counts as showing.
export function whenOffScreen(nodes, leave) {
  const showing = new Set();
  const observer = new IntersectionObserver((entries) => {
    for (const { target, isIntersecting } of entries)
      if (isIntersecting) showing.add(target);
      else showing.delete(target);
    if (!showing.size) leave();
  });
  for (const node of nodes) observer.observe(node);
  return () => observer.disconnect();
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
// What cuts paint standing over an item's `box`, by the plane each cut stands in.
// `plane` is the one the paint stands in: the window's where a fixed box escapes every
// clip around it, and the page's otherwise, which the root scroll carries. `bands` are
// the boxes between it and the item whose bands cut it, outermost first, each band less
// the headers stuck over the item's view of it (`headerInset`); each stands in the plane
// of the box that holds it. `window` is what the window leaves the paint, in the
// window's plane: the room below a header stuck over the root's top, cut, for paint
// stacked `aboveSurfaces`, at the edge of each declared occluder standing over what the
// bands leave of the box, on the side `occluded` keeps, or null where neither cuts it,
// and empty where a cut hides the box whole. Paint stacked under the surfaces is hidden
// by them where they stand. The window's own edges cut nothing in the page's plane, since paint past them
// is not drawn anyway, and cutting it there would move the cut with every scroll.
export function paintClips(item, box, clips, aboveSurfaces) {
  const walk = clipWalk(item, clips, false);
  const plane = walk.fixed ? "window" : "page";
  const root = item.ownerDocument.scrollingElement;
  const hidden = { plane, window: { left: 0, top: 0, right: 0, bottom: 0 }, bands: [] };
  let shown = cutBy(box, walk.cuts, root, false);
  if (!shown) return hidden;
  // The root's band is the window's, which cuts only below a header stuck over it.
  let window = walk.cuts.find(({ box: cut, covered }) => cut === root && covered)?.band;
  for (const { surface, box: over, level } of aboveSurfaces
    ? standingOccluders(clips)
    : []) {
    if (!overlaps(shown, over) || under(item, surface) || stackLevel(item) >= level)
      continue;
    const left = uncovered(shown, over);
    if (!left) return hidden;
    window ??= shownBand(root);
    window = {
      left: left.left > shown.left ? Math.max(window.left, over.right) : window.left,
      top: left.top > shown.top ? Math.max(window.top, over.bottom) : window.top,
      right:
        left.right < shown.right ? Math.min(window.right, over.left) : window.right,
      bottom:
        left.bottom < shown.bottom ? Math.min(window.bottom, over.top) : window.bottom,
    };
    shown = left;
  }
  return {
    plane,
    window: window ?? null,
    bands: walk.cuts.filter(({ box: cut }) => cut !== root).reverse(),
  };
}
// The same walk for a box drawn in the document plane, which a root scroll carries with
// the page: the page's own boxes cut it, and the window does not, so a box scrolled off
// screen keeps its place for a reader asking how far away it stands.
export const pagePlaneRect = (box, item, clips) =>
  clipped(box, item, clips, false, false);
// The same walk for a box measured from what an element holds: a Range inside it. The
// holder's own band stands over its contents, where it says nothing about the holder's
// own box, so text scrolled out of the `pre` it sits in directly is text nobody sees.
export const clippedContents = (box, holder, clips) =>
  clipped(box, holder, clips, true);
function clipped(box, item, clips, held, inWindow = true) {
  const root = item.ownerDocument.scrollingElement;
  const shown = cutBy(box, clipWalk(item, clips, held).cuts, root, inWindow);
  return shown && occluded(shown, item, clips);
}
// `box` less the bands of `cuts`, each on the axes it clips, or null where they leave
// none of it. In the window's plane the window cuts it; in the page's plane the root's
// band is the window, which cuts nothing there, and only a header stuck over its top
// does.
function cutBy(box, cuts, root, inWindow) {
  let left = inWindow ? Math.max(box.left, 0) : box.left,
    top = inWindow ? Math.max(box.top, 0) : box.top,
    right = inWindow ? Math.min(box.right, innerWidth) : box.right,
    bottom = inWindow ? Math.min(box.bottom, innerHeight) : box.bottom;
  for (const { box: cut, band, axes, covered } of cuts) {
    if (!band) return null;
    const edges =
      !inWindow && cut === root
        ? {
            left: -Infinity,
            top: covered ? band.top : -Infinity,
            right: Infinity,
            bottom: Infinity,
          }
        : band;
    if (axes.x) {
      left = Math.max(left, edges.left);
      right = Math.min(right, edges.right);
    }
    if (axes.y) {
      top = Math.max(top, edges.top);
      bottom = Math.min(bottom, edges.bottom);
    }
  }
  return right > left && bottom > top ? { left, top, right, bottom } : null;
}
// The clips standing over an item, innermost first: each ancestor whose band cuts it,
// with that band less the headers stuck over its top and the footers over its foot, and
// whether a fixed box among the item's ancestors escapes every clip further out, the
// root's included.
function clipWalk(item, clips, held) {
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
  // The box just inside each scroller, where the sticky headers over its top and footers
  // over its foot are read (`headerInset`, `footerInset`): the item at its own scroller,
  // and the scroller below at each one further out.
  let inner = item;
  let escaped = false,
    containing = null;
  const cuts = [];
  for (let a = item; a; a = upFrom(a)) {
    let c = clips.get(a);
    if (c === undefined) {
      clips.set(
        a,
        (c = {
          band: shownBand(a),
          axes:
            a === a.ownerDocument.scrollingElement
              ? { x: true, y: true }
              : clippingAxes(getComputedStyle(a)),
          // Read here rather than out of shownBand, whose answer is a band and is the
          // render gate's too: what clips a box and what a box is positioned against are
          // two facts, and one of them is this walk's alone.
          positioned:
            a.offsetParent !== undefined &&
            ["fixed", "absolute"].includes(getComputedStyle(a).position),
          block: a.offsetParent,
          scrolls: holdsHeaders(a),
        }),
      );
    }
    if (escaped && a === containing) escaped = false;
    if (!escaped && (held || a !== item) && c.band) {
      const covered = c.band.top + headerInset(inner, a);
      const footed = c.band.bottom - footerInset(inner, a);
      cuts.push({
        box: a,
        axes: c.axes,
        covered: c.axes.y && covered > c.band.top,
        band:
          c.axes.y && covered >= footed
            ? null
            : c.axes.y
              ? { ...c.band, top: covered, bottom: footed }
              : c.band,
      });
      if (c.scrolls) inner = a;
    }
    if (!escaped && c.positioned) {
      escaped = true;
      containing = c.block;
    }
  }
  return { cuts, fixed: escaped && !containing };
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
    rect = uncovered(rect, box);
    if (!rect) return null;
  }
  return rect;
}
// The largest part of `rect` that `box` does not stand over, or null where it covers it.
function uncovered(rect, box) {
  if (!overlaps(rect, box)) return rect;
  const sides = [
    { ...rect, right: Math.min(rect.right, box.left) },
    { ...rect, left: Math.max(rect.left, box.right) },
    { ...rect, bottom: Math.min(rect.bottom, box.top) },
    { ...rect, top: Math.max(rect.top, box.bottom) },
  ].filter((side) => side.right > side.left && side.bottom > side.top);
  return sides.length
    ? sides.reduce((most, side) => (area(side) > area(most) ? side : most))
    : null;
}
