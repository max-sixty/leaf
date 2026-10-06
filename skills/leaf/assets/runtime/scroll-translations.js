/* Native motion in a document-plane overlay.
 *
 * Geometry owners measure a spot and its scroll origins together. These translations
 * carry that spot by each scroller's subsequent motion on the compositor, including
 * transformed axes. They own no geometry, focus, semantic state or scroll writes.
 * Additive effects compose independent ancestors without introducing containing blocks
 * or moving the native subtree. The caller retains the effects for that placement and
 * cancels them when its node or measurement leaves.
 */
import { scrollAxes } from "./geometry.js";

export const nativeScrollTranslations = () =>
  typeof window.ScrollTimeline === "function";

// Timeline progress runs from the scroll origin to its opposite edge. DOM scroll
// offsets remain physical coordinates: a right or bottom origin has negative ones.
// The origin is block/inline-start, or main/cross-start in a flex scrollport.
function scrollDirections(source) {
  const style = getComputedStyle(source);
  const horizontal = style.writingMode === "horizontal-tb";
  const inline = style.direction === "rtl" ? -1 : 1;
  const directions = horizontal
    ? { x: inline, y: 1 }
    : {
        x: style.writingMode.endsWith("-rl") ? -1 : 1,
        y: style.writingMode === "sideways-lr" ? -inline : inline,
      };
  if (style.display === "flex" || style.display === "inline-flex") {
    const main = style.flexDirection.startsWith("row")
      ? horizontal
        ? "x"
        : "y"
      : horizontal
        ? "y"
        : "x";
    if (style.flexDirection.endsWith("reverse")) directions[main] *= -1;
    if (style.flexWrap === "wrap-reverse") directions[main === "x" ? "y" : "x"] *= -1;
  }
  return directions;
}

export function readScrollTranslations(sources) {
  return sources.flatMap((source) => {
    const axes = scrollAxes(source);
    const directions = scrollDirections(source);
    return [
      ["x", source.scrollLeft, source.scrollWidth - source.clientWidth],
      ["y", source.scrollTop, source.scrollHeight - source.clientHeight],
    ]
      .filter(([, , extent]) => extent > 0)
      .map(([axis, scroll, extent]) => ({
        source,
        axis,
        scroll,
        extent: extent * directions[axis],
        vector: axes[axis],
      }));
  });
}

export function scrollTranslation(node, { source, axis, scroll, extent, vector }) {
  const value = (amount) => `translate(${amount * vector.x}px, ${amount * vector.y}px)`;
  return node.animate(
    [{ transform: value(scroll) }, { transform: value(scroll - extent) }],
    {
      timeline: new window.ScrollTimeline({ source, axis }),
      duration: "auto",
      fill: "both",
      composite: "add",
    },
  );
}
