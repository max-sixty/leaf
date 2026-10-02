import { declarationFor, inChrome } from "/runtime/widget-api.js";
import { at } from "./locate.js";
import { openRoots } from "./open-roots.js";

// A box that draws an inset and shows a different one. A child's outer margin normally
// collapses through its parent and is spent between blocks; where the parent draws
// something at that edge, or holds a formatting context of its own, it cannot get out and
// is painted as the parent's inset instead. So the number a stylesheet states is not the
// number a user sees, and which of the two they get depends on what the author wrote
// inside: a card ending in a sentence showed its 16px, the same card ending in a paragraph
// showed 29. theme.css states the trim and a box opts in where it draws the frame
// (`--lf-block-frame`); this is what says when one hasn't.
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
      if (s.display === "none" || node.hasAttribute("hidden")) continue;
      if (s.position === "absolute" || s.position === "fixed") continue;
      if (s.float !== "none") continue;
      if (s.display === "contents") {
        for (const child of flow(node))
          out.push({
            ...child,
            contents: [node.tagName.toLowerCase(), ...(child.contents || [])],
          });
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
  // Follow an edge only through boxes whose children's margins can collapse through
  // them, which is where a margin inside the frame reaches the frame's edge. The shared
  // trim follows every edge child, so a margin found on this path means the frame
  // itself has not declared (or something overrides the trim).
  const edgeMargin = (kid, edge, through = []) => {
    if (!kid.node) return null;
    const path = [...through, ...(kid.contents || [])];
    const side = edge === "above" ? "Top" : "Bottom";
    const end = edge === "above" ? "Start" : "End";
    const own = px(kid.s["marginBlock" + end]);
    let deeper = null;
    const s = kid.s;
    if (
      !holds(s) &&
      s.containerType === "normal" &&
      !s.display.startsWith("inline") &&
      !s.display.includes("flex") &&
      !s.display.includes("grid") &&
      !px(s["padding" + side]) &&
      !px(s["border" + side + "Width"]) &&
      getComputedStyle(kid.node, edge === "above" ? "::before" : "::after").content ===
        "none"
    ) {
      const kids = flow(kid.node);
      if (kids.length) {
        deeper = edgeMargin(edge === "above" ? kids[0] : kids[kids.length - 1], edge, [
          ...path,
          kid.node.tagName.toLowerCase(),
        ]);
      }
    }
    return own >= (deeper?.margin || 0)
      ? { margin: own, child: kid.node.tagName.toLowerCase(), through: path }
      : deeper;
  };
  const found = [];
  for (const root of openRoots(document))
    for (const el of root.querySelectorAll("*")) {
      const s = getComputedStyle(el);
      if (s.display === "none" || s.display === "contents" || el.closest("[hidden]"))
        continue;
      // An inline box lays no vertical margin out, so it traps nothing.
      if (s.display.startsWith("inline") && s.display !== "inline-block") continue;
      if (s.display.includes("flex") || s.display.includes("grid")) continue;
      const kids = flow(el);
      if (!kids.length) continue;
      for (const [edge, side, kid, pseudo] of [
        ["above", "Top", kids[0], "::before"],
        ["below", "Bottom", kids[kids.length - 1], "::after"],
      ]) {
        if (!kid.node) continue;
        if (getComputedStyle(el, pseudo).content !== "none") continue;
        const drawn = px(s["padding" + side]) + px(s["border" + side + "Width"]);
        if (!drawn && !holds(s)) continue;
        const leak = edgeMargin(kid, edge);
        if (leak && leak.margin > 0.5)
          found.push({
            tag: el.tagName.toLowerCase(),
            id: el.id || null,
            cls: el.classList[0] || null,
            edge,
            drawn,
            margin: leak.margin,
            child: leak.child,
            through: leak.through,
            frameDeclared: s.getPropertyValue("--lf-block-frame").trim() === "1",
            chrome: inChrome(el),
          });
      }
    }
  return found;
}

// The items a flex or grid box lays out: its children the page put there and the box
// places, which leaves out what is not drawn, what is out of flow, and the layer's own
// generated boxes. The arrangement reading (layout.js) counts the same items.
export const laidOutItems = (box) =>
  [...box.children].filter((child) => {
    if (child.matches(".lf-ui, [data-lf-gen]")) return false;
    const c = getComputedStyle(child);
    return c.display !== "none" && c.position !== "absolute" && c.position !== "fixed";
  });

// A box that lays its children out side by side and stands at a frame's edge, where the
// shared trim took the margin off its edge item but not off the items beside it: the row
// no longer lines up. The trim follows the edge through whatever stands at it, and a
// stylesheet cannot ask a box for its display, so a flex or grid box says so itself
// (`--lf-holds-edge: 1`, theme.css) and this says when one hasn't. Items are in one row
// when their margin boxes start (or end) on the same line.
export function splitEdges() {
  const px = (v) => parseFloat(v) || 0;
  const found = [];
  for (const root of openRoots(document))
    for (const el of root.querySelectorAll("*")) {
      const s = getComputedStyle(el);
      if (!s.display.includes("flex") && !s.display.includes("grid")) continue;
      if (el.closest("[hidden]")) continue;
      if (s.getPropertyValue("--lf-holds-edge").trim() === "1") continue;
      const items = laidOutItems(el);
      if (items.length < 2) continue;
      for (const [edge, token, prop, item, line] of [
        [
          "above",
          "--lf-frame-start",
          "marginBlockStart",
          items[0],
          (b, m) => b.top - m,
        ],
        [
          "below",
          "--lf-frame-end",
          "marginBlockEnd",
          items[items.length - 1],
          (b, m) => b.bottom + m,
        ],
      ]) {
        if (s.getPropertyValue(token).trim() !== "1") continue;
        const own = px(getComputedStyle(item)[prop]);
        if (own > 0.5) continue;
        const at = line(item.getBoundingClientRect(), own);
        const beside = items
          .filter((other) => other !== item)
          .map((other) => {
            const m = px(getComputedStyle(other)[prop]);
            return { m, at: line(other.getBoundingClientRect(), m) };
          })
          .find(({ m, at: other }) => m > 0.5 && Math.abs(other - at) < 2);
        if (beside)
          found.push({
            tag: el.tagName.toLowerCase(),
            id: el.id || null,
            cls: el.classList[0] || null,
            edge,
            margin: beside.m,
            chrome: inChrome(el),
          });
      }
    }
  return found;
}

// The runtime's own apparatus standing among the elements the page wrote. A page's rules
// read its structure: which child is first, last, or only, and what an `h2 + p` rule
// finds next. An element the runtime adds beside the page's own changes those answers for
// as long as it stands, so the page's own rules restyle and move its content, which
// nothing Leaf draws may do (assets/AGENTS.md, "Space and scrolling"). What the runtime
// says about an element stands in the chrome instead (details-shelf.js).
//
// The page's own elements are the document tree under `main`, the authored content root.
// A widget's own children are its module's to arrange, whether the layer declares it or
// the page defines it, and so is everything inside one whose content is not the page's
// markup; inside a markup container, such as a tab's panel, the page's elements are the
// page's again. The developer gallery's section asks for the runtime's replay controls
// (`data-interaction-gallery`), so its row is furniture the page requested. An inline box's children are
// its run of words, where the question is not which block comes first or next, so a code
// block's highlighting or the mark ending a link's words is not this. An anchored
// overlay is out of flow too: its sibling is where its keyboard stop belongs, but
// its box is positioned from an anchor instead of participating in the page's layout.
export function apparatusAmongAuthored() {
  const generated = ".lf-ui, [data-lf-gen]";
  const declared = (el) =>
    declarationFor(el, "type") !== undefined || customElements.get(el.localName);
  const modules = (parent) => {
    if (declared(parent) || parent.matches("[data-interaction-gallery]")) return true;
    for (
      let at = parent.parentElement;
      at && at.localName !== "main";
      at = at.parentElement
    )
      if (declared(at)) return declarationFor(at, "x-content") !== "markup";
    return false;
  };
  const found = new Set();
  for (const el of document.querySelectorAll(`main :is(${generated})`)) {
    const parent = el.parentElement;
    if (parent.closest(generated) || inChrome(parent) || modules(parent)) continue;
    if (getComputedStyle(parent).display === "inline") continue;
    const style = getComputedStyle(el);
    if (
      ["absolute", "fixed"].includes(style.position) &&
      style.positionAnchor &&
      style.positionAnchor !== "auto"
    ) continue;
    found.add(`${at(el)} stands among the children of ${at(parent)}`);
  }
  return [...found];
}
