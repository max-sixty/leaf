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
 *
 * The class extends CodeMirror's view, so it is built over the CodeMirror module its
 * caller has loaded (`leafEditorView`), once per module, rather than imported with
 * this one: that keeps CodeMirror off the opening of a page that never edits, and a
 * caller that imports CodeMirror statically still gets the class synchronously.
 */
import { setScroll } from "./arrivals.js";
import { canPlaceFocus } from "./focus.js";
import { scrollIntoView } from "./landing-scroll.js";
import { clamp, union } from "./rect.js";

// CodeMirror exposes its scroll request and margin providers through this hook,
// but does not expose a native-free version of its default reveal. Translate that
// request only for the editor's own scrollport; Leaf owns the enclosing placement.
/** @typedef {Parameters<Parameters<typeof import("@codemirror/view").EditorView.scrollHandler.of>[0]>[2]} ScrollOptions */
/** @param {number} start @param {number} end @param {number} low @param {number} high
 * @param {ScrollOptions["x"]} alignment @param {number} margin @param {number} side */
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

/** @type {WeakMap<typeof import("/vendor/codemirror.esm.js"), ReturnType<typeof editorViewOver>>} */
const classes = new WeakMap();
/** The view class over `codemirror`, the namespace of `/vendor/codemirror.esm.js`.
 * @param {typeof import("/vendor/codemirror.esm.js")} codemirror */
export function leafEditorView(codemirror) {
  let made = classes.get(codemirror);
  if (!made) classes.set(codemirror, (made = editorViewOver(codemirror)));
  return made;
}

/** @param {typeof import("/vendor/codemirror.esm.js")} codemirror */
function editorViewOver({
  Compartment,
  Direction,
  EditorState,
  EditorView,
  StateEffect,
}) {
  // The caret at `at`, as a node a reveal can land and its rectangle, read from the DOM
  // so a scroll handler may call it while the view updates (`LeafEditorView.caretAt`).
  /** @param {import("@codemirror/view").EditorView} view @param {number} at */
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
    if (!destination)
      throw new Error("CodeMirror returned a caret outside its editor DOM");
    const box = destination.getBoundingClientRect();
    const x = view.textDirection === Direction.LTR ? box.left : box.right;
    return {
      destination,
      rectangle: { left: x, right: x, top: box.top, bottom: box.bottom },
    };
  }

  /** @param {import("@codemirror/view").EditorView} view
   * @param {import("@codemirror/state").SelectionRange} selection @param {ScrollOptions} options
   * @param {import("./rect.js").Box} head */
  function placeWithinEditor(view, selection, options, head) {
    const rectangle = union(
      selection.empty ? [head] : [head, caretAt(view, selection.anchor).rectangle],
    );
    /** @type {Record<"top" | "bottom" | "left" | "right", number>} */
    const margins = { top: 0, bottom: 0, left: 0, right: 0 };
    for (const provider of view.state.facet(EditorView.scrollMargins)) {
      const supplied = provider(view);
      if (supplied)
        for (const edge of EDGES)
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
    setScroll(port, {
      left: port.scrollLeft + (port.scrollWidth > port.clientWidth ? x / scaleX : 0),
      top: port.scrollTop + (port.scrollHeight > port.clientHeight ? y / scaleY : 0),
      behavior: "instant",
    });
  }

  /** @type {(keyof import("./rect.js").Box)[]} */
  const EDGES = ["top", "bottom", "left", "right"];
  const navigation = new Compartment();
  const reveal = EditorView.scrollHandler.of((view, selection, options) => {
    const { destination, rectangle } = caretAt(view, selection.head);
    placeWithinEditor(view, selection, options, rectangle);
    scrollIntoView(destination, { block: "nearest", behavior: "instant" });
    return true;
  });
  /** @param {import("@codemirror/state").EditorState} state */
  const withNavigation = (state) =>
    navigation.get(state) === undefined
      ? state.update({ effects: StateEffect.appendConfig.of(navigation.of(reveal)) })
          .state
      : state;

  return class LeafEditorView extends EditorView {
    // Set while `focus()` moves native focus, which places the caret itself once
    // focus has landed.
    #focusing = false;

    /** @param {import("@codemirror/view").EditorViewConfig} [config] */
    constructor(config = {}) {
      super({
        ...config,
        state: withNavigation(config.state ?? EditorState.create(config)),
      });
      this.scrollDOM.classList.add("scroll");
      // Native Tab and shadow-root delegation bypass focus(). A hidden retained
      // editor may have lost its DOM selection while its state kept the caret.
      // Restore that caret in the arrival task, before the next key can edit at the
      // browser's collapsed position. Pointer selection follows focus and still places
      // the caret at the words the user pressed. A selection written inside the
      // focus event, before the platform finishes its focus steps, is one WebKit
      // reveals across frames as it would a retained one, so `focus()` places its
      // caret after native focus returns instead.
      this.contentDOM.addEventListener("focus", () => {
        if (!this.#focusing) this.placeSelection();
      });
    }

    /** The caret at `at`: a node a reveal can land, and its rectangle. */
    /** @param {import("@codemirror/view").EditorView} view @param {number} at */
    static caretAt(view, at) {
      return caretAt(view, at);
    }

    /** @param {import("@codemirror/state").EditorState} state */
    setState(state) {
      super.setState(withNavigation(state));
    }

    // Safari reveals a retained inactive contenteditable selection even when native
    // focus prevents scrolling. Detach only this editor's selection before arrival,
    // then place its recorded caret; composed ranges reach closed shadow roots.
    focus() {
      if (!canPlaceFocus()) return;
      const selection = this.#selection();
      if (!selection) return;
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
      this.#focusing = true;
      try {
        this.contentDOM.focus({ preventScroll: true });
      } finally {
        this.#focusing = false;
      }
      this.placeSelection();
    }

    // Write the recorded selection into the focused editor's DOM. A move that keeps focus
    // (`moveBefore`) still collapses the native selection, which the view would otherwise
    // read back as its own.
    placeSelection() {
      if (this.root.activeElement !== this.contentDOM) return;
      const { anchor, head } = this.state.selection.main;
      const from = this.domAtPos(anchor);
      const to = this.domAtPos(head);
      this.#selection()?.setBaseAndExtent(from.node, from.offset, to.node, to.offset);
    }

    // Firefox and WebKit lack ShadowRoot.getSelection; the document holds theirs.
    #selection() {
      return this.root.getSelection?.() ?? this.dom.ownerDocument.getSelection();
    }
  };
}
