/* Native scroll motion: a layer the browser translates with a scroller's scroll.

   A box drawn outside a scroller that must move with what scrolls inside it is
   carried by CSS position only through the scrolls around its own containing block,
   or, anchored, around its anchor. Frames nested inside one another to cut such a box
   at each scroller's edge cannot be anchored, since an anchor outside a box's
   containing block cannot position it. A motion layer is a box translated by a scroll
   driven animation instead, one layer per axis a scroller scrolls along, so the
   browser moves it in the frame that scrolls and no script answers the scroll. Nested
   layers compose in that same frame; two effects added on one node compose a frame
   late.

   Sticky and fixed ancestry cannot be represented by a linear scroll trajectory,
   and a scroller used as its own subject supplies no visibility interval. Such
   attachments use their existing observed placement path before paint.

   Each animation runs on a ViewTimeline of a `subject` the scroller holds: the box the
   layer's contents stand over, or the next scroller in. Its progress runs over the
   scrolls that carry the subject across the scroller's view, `reach` viewport pixels beyond its edges,
   a range that depends on where the subject stands and how large it and the view are.
   A ScrollTimeline's runs over the scroller's whole reach, which content growing
   anywhere in the scroller changes with no scroll and no layout event the placement
   hears, leaving the layer off by as much. Outside the range the layer stops, with
   the subject out of view. An axis that starts at its far end uses a ScrollTimeline
   instead (right to left, a vertical writing mode, a reversed flex box),
   where Chrome measures a ViewTimeline's range from the wrong end. Those animations
   declare pixel ranges from the subject's visible interval, so their displacement
   remains independent of unrelated overflow growth. A virtual reference supplies
   its measured rectangle and contextElement when words scroll inside their own
   physical context; it uses the same pixel-range trajectory.

   `scrollMotions` reads the axes a scroller carries a subject along, and
   `followScroll` animates a layer along one of them. `origin` is the scroll offset at
   which the layer's contents were placed where they stand untranslated: the offset
   read when they were measured, or zero for contents placed where they stand at the
   scroller's start, which a later scroll does not change, so placing them again
   writes nothing. */
import { scrollAxes } from "./geometry.js";
import { renderedParent } from "./shadow.js";

// Timelines express displacement linear in scroll, while sticky and fixed boxes
// have browser-owned positional constraints. Those attachments keep their observed
// placement path; the capability belongs here, rather than in each consumer.
export function scrollFollows(subject = null, source = null) {
  if (subject && subject === source) return false;
  if (
    typeof window.ViewTimeline !== "function" ||
    typeof window.ScrollTimeline !== "function"
  )
    return false;
  const box = subject?.contextElement ?? subject;
  for (let at = box; at instanceof Element; at = renderedParent(at))
    if (/^(sticky|fixed)$/.test(getComputedStyle(at).position)) return false;
  return true;
}

const scrollContainer = (box) =>
  box === box.ownerDocument.scrollingElement ||
  /auto|scroll|hidden/.test(
    `${getComputedStyle(box).overflowX} ${getComputedStyle(box).overflowY}`,
  );

// Whether `source` starts scrolled to the far end of `axis`, its right or bottom, where
// `scrollLeft` or `scrollTop` runs negative: the platform's rule, from the writing mode
// and direction that set its inline and block axes, and a flex box that reverses one.
function startsAtFar(source, axis) {
  const style = getComputedStyle(source);
  const vertical = !style.writingMode.startsWith("horizontal");
  const inline = vertical ? "y" : "x";
  let far =
    axis === inline
      ? (style.direction === "rtl") !== (style.writingMode === "sideways-lr")
      : /-rl$/.test(style.writingMode);
  if (/flex/.test(style.display)) {
    const row = !style.flexDirection.startsWith("column");
    const main = row === (axis === inline);
    if (
      main
        ? style.flexDirection.endsWith("-reverse")
        : style.flexWrap === "wrap-reverse"
    )
      far = !far;
  }
  return far;
}

// The box `subject` stands in that generates one: a timeline of a box that draws none
// (`display: contents`) has no scroller. The scroller itself where none lies between.
function carried(subject, source) {
  if (!(subject instanceof Element)) return subject;
  let box = subject;
  while (box && box !== source && !box.getClientRects().length)
    box = renderedParent(box);
  return box ?? source;
}

// Each axis `source` scrolls `subject` along: its offset now, the offsets between which
// the subject crosses the view, and the viewport displacement one scroll pixel gives
// what it holds (`scrollAxes`). Offsets are signed as `scrollLeft` and `scrollTop` read
// them, negative toward the far end of an axis the scroller starts at; the timeline
// measures distance from its start. A subject the scroller does not carry, one
// positioned outside it, has none. Without scroll timelines each axis is listed with
// none to follow, so a caller sees what it must place again on each scroll instead.
export function scrollMotions(source, subject, reach = 0) {
  if (!scrollContainer(source)) return [];
  const axes = scrollAxes(source);
  const holder = carried(subject, source);
  const motions = [];
  for (const [axis, scroll, extent] of [
    ["x", source.scrollLeft, source.scrollWidth - source.clientWidth],
    ["y", source.scrollTop, source.scrollHeight - source.clientHeight],
  ]) {
    if (!(extent > 0)) continue;
    if (!scrollFollows(holder, source)) {
      motions.push({ source, subject: holder, axis, scroll, vector: axes[axis] });
      continue;
    }
    const sign = startsAtFar(source, axis) ? -1 : 1;
    const whole = sign < 0 || !(holder instanceof Element);
    const timeline = whole
      ? new window.ScrollTimeline({ source, axis })
      : new window.ViewTimeline({
          subject: holder,
          axis,
          inset: [
            CSS.px(-reach / Math.hypot(axes[axis].x, axes[axis].y)),
            CSS.px(-reach / Math.hypot(axes[axis].x, axes[axis].y)),
          ],
        });
    if (timeline.source !== source) continue;
    // A reversed source's ScrollTimeline still measures its growing whole extent.
    // Fix the animation's range in physical scroll pixels, over precisely the
    // interval where this subject can intersect the viewport. Growing unrelated
    // overflow then changes neither displacement nor the attachment's interval.
    const [start, end] = whole
      ? visibleRange(source, holder, axes, axis, scroll, reach, sign)
      : [timeline.startOffset.value, timeline.endOffset.value];
    motions.push({
      source,
      subject: holder,
      axis,
      scroll,
      from: sign * start,
      to: sign * end,
      vector: axes[axis],
      timeline,
      whole,
    });
  }
  return motions;
}

function visibleRange(source, subject, axes, axis, scroll, reach, sign) {
  const project = ({ left, top, right, bottom }) => {
    // Invert both transformed scroll axes, so sideways scrolling cannot change
    // this axis's interval even when a skew makes those directions nonorthogonal.
    const determinant = axes.x.x * axes.y.y - axes.x.y * axes.y.x;
    const points = [
      [left, top],
      [right, top],
      [left, bottom],
      [right, bottom],
    ].map(([x, y]) =>
      axis === "x"
        ? (x * axes.y.y - y * axes.y.x) / determinant
        : (y * axes.x.x - x * axes.x.y) / determinant,
    );
    return [Math.min(...points), Math.max(...points)];
  };
  const view = source.getBoundingClientRect();
  const [near, far] = project({
    left: view.left - reach,
    top: view.top - reach,
    right: view.right + reach,
    bottom: view.bottom + reach,
  });
  const [first, last] = project(subject.getBoundingClientRect());
  const from = scroll + first - far;
  const to = scroll + last - near;
  return sign < 0
    ? [Math.max(0, -to), Math.max(0, -from)]
    : [Math.max(0, from), Math.max(0, to)];
}

// Where the scrolls of `motions` have carried a point from where it stood at their
// scrollers' start: the translation `followScroll` gives a layer placed at origin zero.
export const scrolledBy = (motions) =>
  motions.reduce(
    (by, { scroll, vector }) => ({
      x: by.x - scroll * vector.x,
      y: by.y - scroll * vector.y,
    }),
    { x: 0, y: 0 },
  );

export function followScroll(layer, { from, to, vector, timeline, whole }, origin) {
  const value = (offset) =>
    `translate(${(origin - offset) * vector.x}px, ${(origin - offset) * vector.y}px)`;
  // A source with no overflow has an inactive timeline. Its zero-scroll position
  // remains the underlying placement, including an attachment measured mid-scroll.
  layer.style.transform = value(0);
  return layer.animate([{ transform: value(from) }, { transform: value(to) }], {
    timeline,
    duration: "auto",
    fill: "both",
    composite: "replace",
    ...(whole
      ? { rangeStart: `${Math.abs(from)}px`, rangeEnd: `${Math.abs(to)}px` }
      : {}),
  });
}
