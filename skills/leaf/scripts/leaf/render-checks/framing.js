import { inChrome } from "/runtime/widget-api.js";
import { openRoots } from "./open-roots.js";

// A box that draws an inset and shows a different one. A child's outer margin normally
// collapses through its parent and is spent between blocks; where the parent draws
// something at that edge, or holds a formatting context of its own, it cannot get out and
// is painted as the parent's inset instead. So the number a stylesheet states is not the
// number a reader sees, and which of the two they get depends on what the author wrote
// inside: a card ending in a sentence showed its 16px, the same card ending in a paragraph
// showed 29. theme.css states the trim and a box opts in where it draws the frame
// (`--lf-frame`); this is what says when one hasn't.
//
// It is a reading of the rendered page because nothing else can be. The trim is a style
// query, the frame is a declaration in whichever layer drew the box, and a project overlays
// its own theme over leaf's — so which rule won, and whether the child that ended up at the
// edge is the one the stylesheet's author had in mind, are facts only the browser holds. A
// lint over the CSS would be reading the declarations and not the result, which is the same
// mistake the reserved-width lint made before the press sweep replaced it.
//
// Two exclusions, both about what a margin means where it stands. A flex or grid container
// collapses no margin anywhere, so a margin on an item at its edge is a placement rather
// than room that could not get out — the switch under a screenshot pair carries 3px of
// exactly that, the UA's own on a checkbox. And an edge whose box is a generated one (a
// pseudo-element, an `x-says` word, an injected control) is the layer's own paint, stated
// in the same rule as the frame: what the trim looks for is the first and last block the
// page itself put there, so this looks for the same, and a card's absolutely-positioned
// pick mark is not the thing under its last paragraph.
//
// A box reading wearing a computed-style reading's clothes: inside `display: none` an
// element's own `display` is still `block` and its padding and margins still resolve,
// so this reads the shut thread panel and gets plausible numbers. They are not the
// panel's numbers — a size container query does not match in there, so a rule that
// switches a slot between two forms is stuck on one of them, and a percentage margin
// comes back unresolved. Each finding is therefore tagged with which document it is in;
// the render gate takes the page's half, and the suite opens the panel, where such a
// widget has a box at last, before putting the layer half to it.
//
// Deduped per tag and edge, because one mistake is on every instance of that widget.
export function trappedMargins() {
  // Which document each box is in is OPEN_ROOTS', imported rather than restated, for
  // the same reason UNMARKABLE_ITEMS imports its two: the runtime's layer holds shadow
  // roots of its own, and a `closest` written out here stops at the first of them and
  // calls what it finds the page's.
  const px = (v) => parseFloat(v) || 0;
  // The platform's own answer to "does a child's margin reach my edge, and can it get
  // past it": a box that establishes a formatting context keeps every margin inside.
  const holds = (s) =>
    s.display === "flow-root" ||
    s.display === "inline-block" ||
    s.display.startsWith("table") ||
    s.overflow !== "visible" ||
    s.float !== "none" ||
    s.position === "absolute" ||
    s.position === "fixed" ||
    s.contain.includes("layout") ||
    s.contain.includes("paint");
  // The page's own boxes in this box's flow, in order. Out-of-flow children are not in
  // it, a floated one spends its margins rather than reserving them, a generated one is
  // the layer's paint, and a boxless child hands its own children to the flow.
  const flow = (el) => {
    const out = [];
    for (const node of el.childNodes) {
      if (node.nodeType === 3) {
        if (node.data.trim()) out.push({});
        continue;
      }
      if (node.nodeType !== 1) continue;
      const s = getComputedStyle(node);
      if (s.display === "none") continue;
      if (s.position === "absolute" || s.position === "fixed") continue;
      if (s.float !== "none") continue;
      if (s.display === "contents") {
        out.push(...flow(node));
        continue;
      }
      if (node.matches(".lf-ui, [data-lf-gen]")) {
        out.push({});
        continue;
      }
      out.push({ node, s });
    }
    return out;
  };
  const found = [];
  for (const root of openRoots(document))
    for (const el of root.querySelectorAll("*")) {
      const s = getComputedStyle(el);
      if (s.display === "none" || s.display === "contents") continue;
      // An inline box lays no vertical margin out, so it traps nothing.
      if (s.display.startsWith("inline") && s.display !== "inline-block") continue;
      if (s.display.includes("flex") || s.display.includes("grid")) continue;
      const kids = flow(el);
      if (!kids.length) continue;
      for (const [edge, side, end, kid, pseudo] of [
        ["above", "Top", "Start", kids[0], "::before"],
        ["below", "Bottom", "End", kids[kids.length - 1], "::after"],
      ]) {
        if (!kid.node) continue;
        if (getComputedStyle(el, pseudo).content !== "none") continue;
        const drawn = px(s["padding" + side]) + px(s["border" + side + "Width"]);
        if (!drawn && !holds(s)) continue;
        const margin = px(kid.s["marginBlock" + end]);
        if (margin > 0.5)
          found.push({
            tag: el.tagName.toLowerCase(),
            id: el.id || null,
            cls: el.classList[0] || null,
            edge,
            drawn,
            margin,
            child: kid.node.tagName.toLowerCase(),
            chrome: inChrome(el),
          });
      }
    }
  return found;
}

// How long the render gate waits on the server for one of the documents it reads.
// The same patience playwright gives `wait_for_function` above it, and stated here
// because it is the number that turns a wedged server into a sentence.
