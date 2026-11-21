/* Each line of a code block in a box of its own, so the rows a long line wraps onto
   start two columns past that line's indent, behind a muted ↪ that says the row goes
   on with the line above (reading.css, `pre`). The face wraps a block's long lines,
   and CSS has no selector for the rows a wrap makes and no way to indent each line by
   its own leading columns, so both need a box per line. The user chose the mark: it is
   how print (LaTeX's fvextra) and terminal editors (Emacs, Vim's `showbreak`) tell a
   wrapped row from a line break, which no indent does alone, since a real line can
   start in any column a wrapped row does.

   The boxes change no text. A <span> is no text block (syntax.js), and each box holds
   its line through the newline that ends it, so the anchor pass, a selection and the
   clipboard each read one newline at a line's end, and `textContent` is the source.
   The pass moves the block's own nodes into the boxes, cutting a text node after each
   newline, so an authored element keeps its identity, attributes and listeners, and
   the tokenizer that runs after it (syntax.js) cuts its tokens at the lines' edges.
   A block keeps the face's hang alone, two columns from its edge, where an element
   holds a newline before its own end, which boxing would cut in two, where a <br> ends
   a line, where its <code> shares it with other content (`holderOf`), and where its
   rows are boxes already, as in a widget's listing or a block this pass has boxed. A
   block in a widget whose body is data is the widget's to draw (`DATA_BODY`).

   The hang an indented line takes is not reserved before the pass, so a wrapped
   indented line moves once as the runtime starts, as lf-code's does (code.css). */
import { setChildLists } from "./dom-children.js";
import { DATA_BODY, wearsReadingFace } from "./syntax.js";

const LINE = "data-lf-pre-line";
// A box of its own in the block's flow, not a run of its lines' words.
const BLOCK_LEVEL = /^(block|flow-root|list-item|flex|grid|table)/;

// How many columns a line's leading whitespace takes, a tab reaching the next stop of
// eight, as a <pre>'s does.
/** @param {string} text */
export const indentColumns = (text) => {
  let columns = 0;
  for (const char of text) {
    if (char === " ") columns++;
    else if (char === "\t") columns += 8 - (columns % 8);
    else break;
  }
  return columns;
};

// The element whose children are the block's lines: its one <code>, <samp> or <kbd>
// where that is all it holds, as Markdown writes a fenced block, or else the block
// itself. None where a <code> shares the block with anything else, since what reads a
// block's source finds its <code> as the block's child (syntax.js, formulas.js).
/** @param {HTMLPreElement} pre */
const holderOf = (pre) => {
  const only = pre.firstChild;
  if (only instanceof Element && !only.nextSibling && only.matches("code, samp, kbd"))
    return only;
  return pre.querySelector(":scope > code") ? null : pre;
};

// Whether the holder's children fall into lines whole.
/** @param {Element} holder */
const divides = (holder) => {
  if (!holder.firstChild || holder.querySelector(`br, :scope > [${LINE}]`))
    return false;
  for (let child = holder.firstElementChild; child; child = child.nextElementSibling) {
    const text = child.textContent ?? "";
    const newline = text.indexOf("\n");
    if (newline !== -1 && newline !== text.length - 1) return false;
    if (BLOCK_LEVEL.test(getComputedStyle(child).display)) return false;
  }
  return true;
};

/** @param {Node} node */
const textOf = (node) =>
  node instanceof Text || node instanceof Element ? (node.textContent ?? "") : "";

// The holder's children by line, and a box for each. A line ends after the node that
// ends in its newline. A text node holding more than one line keeps its first and
// gives each later one a node of its own; what follows the last newline is a line of
// its own unless it is empty text.
/** @param {Element} holder
 * @returns {(readonly [Element, Node[]])[]} */
function boxed(holder) {
  /** @type {Node[]} */
  let line = [];
  const lines = [line];
  for (let node = holder.firstChild; node; node = node.nextSibling) {
    /** @type {Node[]} */
    let pieces = [node];
    if (node instanceof Text) {
      const [first = "", ...rest] = node.data.split(/(?<=\n)/);
      if (rest.length) {
        node.data = first;
        pieces = [node, ...rest.map((part) => document.createTextNode(part))];
      }
    }
    for (const piece of pieces) {
      line.push(piece);
      if (textOf(piece).endsWith("\n")) lines.push((line = []));
    }
  }
  const last = lines.at(-2);
  if (last && line.every((node) => node instanceof Text && !node.data)) {
    last.push(...line);
    lines.pop();
  }
  return lines.map((nodes) => {
    const box = document.createElement("span");
    box.setAttribute(LINE, "");
    const indent = indentColumns(nodes.map(textOf).join(""));
    if (indent) box.style.setProperty("--lf-code-indent", String(indent));
    return /** @type {const} */ ([box, nodes]);
  });
}

// Box the lines of each code block in `root`, or holding it, that wears the face. Every
// block is read before any is boxed, and every box is placed in one move, so the pass
// costs one style computation and one selection hold however many blocks it boxes.
/** @param {Document | DocumentFragment | Element} root */
export function boxLines(root) {
  const blocks = [...root.querySelectorAll("pre")];
  if (root instanceof Element) {
    const holding = root.closest("pre");
    if (holding) blocks.unshift(holding);
  }
  const holders = blocks
    .filter((pre) => !pre.matches(DATA_BODY) && wearsReadingFace(pre))
    .map(holderOf)
    .filter((holder) => holder !== null && divides(holder));
  if (!holders.length) return;
  setChildLists(
    holders.flatMap((holder) => {
      const lines = boxed(/** @type {Element} */ (holder));
      return [
        /** @type {const} */ ([
          /** @type {Element} */ (holder),
          lines.map(([box]) => box),
        ]),
        ...lines,
      ];
    }),
  );
}
