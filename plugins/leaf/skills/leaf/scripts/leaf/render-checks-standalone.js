// A DOM-only probe that also runs against exported file:// pages, where the runtime and
// its public API have deliberately been removed. Kept as a real module so both the HTTP
// render gate and standalone-copy tests execute this one implementation.
export function coveredWords({
  holdFloating = true,
  holdHidden = true,
  holdLabelLines = true,
} = {}) {
  const runs = [];
  const at = (el) => {
    const named = el.closest("[id]");
    return named
      ? `<${named.tagName.toLowerCase()} id=${named.id}>`
      : `<${el.tagName.toLowerCase()}>`;
  };
  const outOfFlow = (style) =>
    style.position === "absolute" || style.position === "fixed";
  const floating = (el) => {
    for (
      let ancestor = el.closest("[data-lf-offer]");
      ancestor;
      ancestor = ancestor.parentElement?.closest("[data-lf-offer]")
    )
      if (outOfFlow(getComputedStyle(ancestor))) return true;
    return false;
  };
  const walk = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walk.nextNode(); node; node = walk.nextNode()) {
    const el = node.parentElement;
    if (
      !node.data.trim() ||
      el.closest(".lf-chrome, .lf-quiet") ||
      (holdHidden && el.closest("[hidden]"))
    )
      continue;
    if (!el.checkVisibility({ visibilityProperty: true, opacityProperty: true }))
      continue;
    if (holdFloating && floating(el)) continue;
    const range = document.createRange();
    range.selectNodeContents(node);
    const label = el.closest("text");
    for (const box of range.getClientRects())
      if (box.width > 1 && box.height > 1)
        runs.push({ el, label, box, text: node.data.trim().slice(0, 40) });
  }
  const found = [];
  for (let i = 0; i < runs.length; i++)
    for (let j = i + 1; j < runs.length; j++) {
      const a = runs[i];
      const b = runs[j];
      if (a.el === b.el || a.el.contains(b.el) || b.el.contains(a.el)) continue;
      if (holdLabelLines && a.label && a.label === b.label) continue;
      const across =
        Math.min(a.box.right, b.box.right) - Math.max(a.box.left, b.box.left);
      const down =
        Math.min(a.box.bottom, b.box.bottom) - Math.max(a.box.top, b.box.top);
      if (across <= 2 || down <= 2) continue;
      found.push(
        `${at(a.el)} draws ${JSON.stringify(a.text)} in the same place as ` +
          `${at(b.el)}'s ${JSON.stringify(b.text)}`,
      );
    }
  return [...new Set(found)];
}
