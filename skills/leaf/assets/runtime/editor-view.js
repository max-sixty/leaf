/* Leaf's CodeMirror adapter owns focus admission and document-local reveals.
 *
 * Runtime composers and package file editors share this view. Native focus never
 * reveals an enclosing frame, and editor reveal requests use Leaf's scroll owner
 * before CodeMirror can invoke its native mobile-viewport fallback. That fallback
 * also runs on desktop when a classic horizontal scrollbar reduces visualViewport.
 * The canonical navigation compartment survives retained states and is installed
 * when a caller replaces the complete state. Editor history and local scrollports
 * remain CodeMirror's. The scroll handler honors its requested alignment and
 * margins inside the editor before revealing the caret outward with nearest
 * alignment; PageUp and PageDown retain their caret position within that viewport.
 */
import {
  Compartment,
  Direction,
  EditorState,
  EditorView,
  StateEffect,
} from "../vendor/codemirror.esm.js";
import { canPlaceFocus } from "./focus.js";
import { scrollIntoView } from "./landing-scroll.js";
import { clamp, union } from "./rect.js";

// CodeMirror exposes its scroll request and margin providers through this hook,
// but does not expose a native-free version of its default reveal. Translate that
// request only for the editor's own scrollport; Leaf owns the enclosing placement.
function travel(start, end, low, high, alignment, margin, side) {
  if (alignment === "nearest") {
    if (start < low + margin) {
      const movement = start - low - margin;
      return side > 0 && end > high + movement ? end - high + margin : movement;
    }
    if (end > high - margin) {
      const movement = end - high + margin;
      return side < 0 && start - movement < low ? start - low - margin : movement;
    }
    return 0;
  }
  if (alignment === "center" && end - start <= high - low)
    return (start + end - low - high) / 2;
  return alignment === "start" || (alignment === "center" && side < 0)
    ? start - low - margin
    : end - high + margin;
}

function caretAt(view, at) {
  const position = view.domAtPos(at);
  const caret = document.createRange();
  caret.setStart(position.node, position.offset);
  caret.collapse(true);
  if (caret.getClientRects().length)
    return { destination: caret, rectangle: caret.getBoundingClientRect() };
  // Empty lines have a BR rather than a text caret rectangle. Reveal their line
  // vertically while keeping the caret at its writing edge horizontally.
  const destination =
    position.node instanceof Element ? position.node : position.node.parentElement;
  const box = destination.getBoundingClientRect();
  const x = view.textDirection === Direction.LTR ? box.left : box.right;
  return {
    destination,
    rectangle: { left: x, right: x, top: box.top, bottom: box.bottom },
  };
}

function placeWithinEditor(view, selection, options, head) {
  const rectangle = union(
    selection.empty ? [head] : [head, caretAt(view, selection.anchor).rectangle],
  );
  const margins = { top: 0, bottom: 0, left: 0, right: 0 };
  for (const provider of view.state.facet(EditorView.scrollMargins)) {
    const supplied = provider(view);
    if (supplied)
      for (const edge of Object.keys(margins))
        margins[edge] = Math.max(margins[edge], supplied[edge] ?? 0);
  }
  const port = view.scrollDOM;
  const box = port.getBoundingClientRect();
  const { scaleX, scaleY } = view;
  const left = box.left + port.clientLeft * scaleX;
  const top = box.top + port.clientTop * scaleY;
  const right = left + port.clientWidth * scaleX;
  const bottom = top + port.clientHeight * scaleY;
  const side = selection.head < selection.anchor ? -1 : 1;
  const horizontal =
    view.textDirection === Direction.RTL
      ? options.x === "start"
        ? "end"
        : options.x === "end"
          ? "start"
          : options.x
      : options.x;
  const xMargin = clamp(options.xMargin, -port.offsetWidth, port.offsetWidth);
  const yMargin = clamp(options.yMargin, -port.offsetHeight, port.offsetHeight);
  const x =
    horizontal === "center"
      ? (rectangle.left -
          margins.left +
          rectangle.right +
          margins.right -
          left -
          right) /
        2
      : travel(
          rectangle.left - margins.left,
          rectangle.right + margins.right,
          left,
          right,
          horizontal,
          xMargin,
          side,
        );
  const y = travel(
    rectangle.top - margins.top,
    rectangle.bottom + margins.bottom,
    top,
    bottom,
    options.y,
    yMargin,
    side,
  );
  port.scrollBy({
    left: port.scrollWidth > port.clientWidth ? x / scaleX : 0,
    top: port.scrollHeight > port.clientHeight ? y / scaleY : 0,
    behavior: "instant",
  });
}

const navigation = new Compartment();
const reveal = EditorView.scrollHandler.of((view, selection, options) => {
  const { destination, rectangle } = caretAt(view, selection.head);
  placeWithinEditor(view, selection, options, rectangle);
  scrollIntoView(destination, { block: "nearest", behavior: "instant" });
  return true;
});
const withNavigation = (state) =>
  navigation.get(state) === undefined
    ? state.update({ effects: StateEffect.appendConfig.of(navigation.of(reveal)) })
        .state
    : state;

export class LeafEditorView extends EditorView {
  constructor(config = {}) {
    super({
      ...config,
      state: withNavigation(config.state ?? EditorState.create(config)),
    });
  }

  setState(state) {
    super.setState(withNavigation(state));
  }

  // Safari reveals a retained inactive contenteditable selection even when native
  // focus prevents scrolling. Detach only this editor's selection before arrival,
  // then place its recorded caret; composed ranges reach closed shadow roots.
  focus() {
    if (!canPlaceFocus()) return;
    const selection =
      this.root.getSelection?.() ?? this.dom.ownerDocument.getSelection();
    if (
      this.root.activeElement !== this.contentDOM &&
      selection
        .getComposedRanges({
          shadowRoots: this.root instanceof ShadowRoot ? [this.root] : [],
        })
        .some(
          (range) =>
            this.contentDOM.contains(range.startContainer) ||
            this.contentDOM.contains(range.endContainer),
        )
    )
      selection.removeAllRanges();
    this.contentDOM.focus({ preventScroll: true });
    if (this.root.activeElement !== this.contentDOM) return;
    const { anchor, head } = this.state.selection.main;
    const from = this.domAtPos(anchor);
    const to = this.domAtPos(head);
    selection.setBaseAndExtent(from.node, from.offset, to.node, to.offset);
  }
}
