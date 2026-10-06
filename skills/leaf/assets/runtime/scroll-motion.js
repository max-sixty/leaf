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

   Each animation runs on a ViewTimeline of a `subject` the scroller holds: the box the
   layer's contents stand over, or the next scroller in. Its progress runs over the
   scrolls that carry the subject across the scroller's view, `reach` beyond its edges,
   a range that depends on where the subject stands and how large it and the view are.
   A ScrollTimeline's runs over the scroller's whole reach, which content growing
   anywhere in the scroller changes with no scroll and no layout event the placement
   hears, leaving the layer off by as much. Outside the range the layer stops, with
   the subject out of view. Two cases keep the ScrollTimeline and that dependence: words
   standing in the scroller itself, with no box between, and an axis the scroller
   starts at its far end (right to left, a vertical writing mode, a reversed flex box),
   where Chrome measures a ViewTimeline's range from the wrong end.

   `scrollMotions` reads the axes a scroller carries a subject along, and
   `followScroll` animates a layer along one of them. `origin` is the scroll offset at
   which the layer's contents were placed where they stand untranslated: the offset
   read when they were measured, or zero for contents placed where they stand at the
   scroller's start, which a later scroll does not change, so placing them again
   writes nothing. */
import { scrollAxes } from "./geometry.js";
import { upFrom } from "./shadow.js";

export const scrollFollows = () => typeof window.ViewTimeline === "function";

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
  let box = subject;
  while (box && box !== source && !box.getClientRects().length) box = upFrom(box);
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
    if (!scrollFollows()) {
      motions.push({ source, subject: holder, axis, scroll, vector: axes[axis] });
      continue;
    }
    const sign = startsAtFar(source, axis) ? -1 : 1;
    const whole = holder === source || sign < 0;
    const timeline = whole
      ? new window.ScrollTimeline({ source, axis })
      : new window.ViewTimeline({
          subject: holder,
          axis,
          inset: [CSS.px(-reach), CSS.px(-reach)],
        });
    if (timeline.source !== source) continue;
    const [start, end] = whole
      ? [0, extent]
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
    });
  }
  return motions;
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

export function followScroll(layer, { from, to, vector, timeline }, origin) {
  const value = (offset) =>
    `translate(${(origin - offset) * vector.x}px, ${(origin - offset) * vector.y}px)`;
  return layer.animate([{ transform: value(from) }, { transform: value(to) }], {
    timeline,
    duration: "auto",
    fill: "both",
    composite: "replace",
  });
}
