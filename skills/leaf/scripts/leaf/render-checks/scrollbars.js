/* Horizontal scrollbars must leave the words and controls at the end of their
 * content readable. macOS widens an overlay track to 15px under the pointer. The
 * earlier code/table and opted-in widget spacers protect those layouts; this
 * reading asks the composed geometry, including unmarked and shadow scrollers.
 * It reads the content at its vertical end without scrolling or changing styles,
 * so a check neither disturbs the reader nor depends on whether a hidden overlay
 * scrollbar happened to paint in the headless browser. */
import { renderedParent, upFrom } from "/runtime/widget-api.js";
import { at, place } from "./locate.js";
import { openRoots } from "./open-roots.js";

const visible = (el) =>
  el.checkVisibility({ opacityProperty: true, visibilityProperty: true }) &&
  !el.closest("[hidden], script, style");
const px = (value) => parseFloat(value) || 0;
const controls = 'button, input, select, textarea, [role="button"], a[href], img, svg';
const scaleY = (el) => el.getBoundingClientRect().height / el.offsetHeight;

// A nested clip's hidden words are not paint in the outer scroller. Keep the
// vertical intersection only: every horizontal position is reachable by scrolling.
const paintedBottom = (el, rect, scroller) => {
  let top = rect.top,
    bottom = rect.bottom;
  for (let node = el; node && node !== scroller; node = renderedParent(node)) {
    const style = getComputedStyle(node);
    if (style.position === "fixed") return -Infinity;
    if (style.overflowY !== "visible") {
      const bounds = node.getBoundingClientRect();
      const scale = scaleY(node);
      top = Math.max(top, bounds.top + node.clientTop * scale);
      bottom = Math.min(
        bottom,
        bounds.top + (node.clientTop + node.clientHeight) * scale,
      );
    }
  }
  return bottom > top ? bottom : -Infinity;
};

export function scrollbarClearance() {
  const root = document.querySelector("main");
  if (!root) return [];
  const found = [];
  for (const tree of openRoots(root))
    for (const box of [
      ...(tree === root ? [root] : []),
      ...tree.querySelectorAll("*"),
    ]) {
      if (!visible(box)) continue;
      const style = getComputedStyle(box);
      if (
        !/auto|scroll/.test(style.overflowX) ||
        box.scrollWidth <= box.clientWidth + 1
      )
        continue;
      const bar = getComputedStyle(box, "::-webkit-scrollbar");
      if (
        style.scrollbarWidth === "none" ||
        bar.display === "none" ||
        bar.height === "0px"
      )
        continue;
      // A classic track occupies space below the content instead of covering it.
      const allocated =
        box.offsetHeight -
        box.clientHeight -
        px(style.borderTopWidth) -
        px(style.borderBottomWidth);
      const required = Math.max(0, (px(bar.height) || 15) - allocated);
      if (!required) continue;
      let last = -Infinity,
        content = "";
      const take = (el, rect, kind) => {
        const bottom = paintedBottom(el, rect, box);
        if (bottom > last) {
          last = bottom;
          content = kind;
        }
      };
      for (const scope of openRoots(box)) {
        const walk = document.createTreeWalker(scope, NodeFilter.SHOW_TEXT);
        for (let node; (node = walk.nextNode());) {
          const parent = upFrom(node);
          if (!node.data.trim() || !visible(parent)) continue;
          const range = document.createRange();
          range.selectNodeContents(node);
          for (const rect of range.getClientRects()) take(parent, rect, "words");
        }
        for (const el of scope.querySelectorAll(controls))
          if (visible(el)) take(el, el.getBoundingClientRect(), "controls");
      }
      if (!Number.isFinite(last)) continue;
      const bounds = box.getBoundingClientRect();
      const clear =
        box.scrollHeight +
        box.clientTop -
        box.scrollTop -
        (last - bounds.top) / scaleY(box);
      // scrollHeight rounds to integer CSS pixels; tolerate that rounding alone.
      if (clear < required - 1)
        found.push({
          at: at(box),
          place: place(box),
          clear: Math.round(clear),
          required,
          content,
        });
    }
  return found;
}
