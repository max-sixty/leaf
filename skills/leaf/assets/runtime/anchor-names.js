/* CSS anchor names for the boxes Leaf positions against page content: the margin's rows
 * (margin-layout.js) and the floating surfaces (floating.js). One owner, so a box named
 * for one keeps the same name for the other. */
import { shownParts } from "./geometry.js";
import { hostIn } from "./shadow.js";

// Anchor names are global to their tree, so one per target element, merged with whatever
// name the author gave the same box. The name stays for the element's life: rows come and
// go on the heartbeat and a name written each time would restyle the target each time.
// The pass reads what a box is named before it writes any name (`anchorReading`), since
// reading the author's name is a style read.
const anchorNames = new WeakMap();
let anchorOrdinal = 0;
export function anchorReading(
  el,
  name = anchorNames.get(el) ?? `--lf-a${++anchorOrdinal}`,
) {
  anchorNames.set(el, name);
  const written = el.style.anchorName;
  if (written.split(",").some((part) => part.trim() === name)) return { el, name };
  // What the author's stylesheet names this box, read only where this pass has not already
  // written: a revision patch that rewrote the style attribute has taken the name away.
  const authored = written || getComputedStyle(el).anchorName;
  return {
    el,
    name,
    write: !authored || authored === "none" ? name : `${authored}, ${name}`,
  };
}
export function nameAnchor({ el, name, write }) {
  if (write) el.style.anchorName = write;
  return name;
}

// The box a row or a float anchors to. An anchor name reaches only its own tree, so a
// target inside a shadow tree anchors through its host; a shape inside an SVG drawing has
// no CSS box of its own, so it anchors through the drawing; a `display: contents` target
// through its first shown part. Wherever it anchors, what stands against it is written as
// insets from the anchor's box.
export function anchorElement(target) {
  let el = hostIn(target, document);
  while (el instanceof SVGElement && el.ownerSVGElement) el = el.ownerSVGElement;
  if (el !== target) return el;
  const [part] = shownParts(target);
  return part && part !== target ? part : target;
}

// The name `el` answers to as an anchor, given it first where it has none.
export const anchorName = (el) => nameAnchor(anchorReading(el));
