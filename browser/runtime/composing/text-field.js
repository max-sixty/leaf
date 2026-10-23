/* The runtime's text field: a Markdown editor that presents itself as a textarea.
 *
 * Every composer the runtime builds is a `leaf-text`. Inside a closed shadow root it
 * runs CodeMirror over the draft's exact source, and draws that source the way a sent
 * message will read: inline code in code type, emphasis and strong in their weights,
 * a link as a link, a heading in bold, a list item at the message's inset under the
 * message's own marker. The syntax that produces each (backticks, asterisks, brackets,
 * hashes, list markers) is hidden unless the selection touches the construct. List
 * markers reveal their source only inside the marker: the caret after its trailing
 * space is ready to type content, so even an empty new item already shows its bullet
 * or number. The user can move back into the marker to edit every source character.
 * Nothing is converted: the value is always the source the user typed, which is what
 * the agent reads. The constructs come from the renderer that sends the message
 * (`markdownTokens`), never from a second grammar, so the preview and the message agree
 * on what is a link, a heading or code. CodeMirror's own Markdown grammar serves only
 * editing: Shift+Enter continuing a list.
 *
 * Focus is the field's own, as a textarea's is. `focus()` puts the user in the words
 * with the caret where it stood, `blur()` takes them out, and a press anywhere in the
 * box's padding puts the caret at the nearest character. The root delegates focus, so a
 * focus that never meets the element's own `focus()` — the platform's, or a test
 * driver's from its isolated world — still lands in the words rather than on a host
 * that takes none; CodeMirror's scroller gives up its tab stop so that it is not the
 * node delegation picks.
 *
 * The root is closed because the field is one control, the way a native textarea is:
 * focus, the scope climb and every `focused() === box` comparison land on the host,
 * never on CodeMirror's content node. Outside, the host answers the textarea members the
 * runtime uses — `value`, the selection triple, `setSelectionRange`, `placeholder`,
 * `readOnly`, `name` — and brackets user edits with `lf-before-edit` and `input`.
 * The first announces the old layout before browser text input or an editor command
 * changes the words; the second announces the updated value and layout. A
 * write to `value` fires nothing, puts the caret at the end, and starts a new undo
 * history, so undo never walks back into a draft the runtime swapped out.
 * `edit(text)` replaces the words as external text input, such as dictation: it keeps
 * undo history and emits the same before-edit/input bracket as native typing.
 * `lf-caret-move` says the user moved the caret or selection without editing, as an
 * arrow key does; a write to the selection triple fires nothing.
 * A box owner that takes pasted pictures intercepts paste in capture; otherwise the field pastes
 * the clipboard's text, including text carried beside a picture.
 * `naturalBlockSize` reads the field's intrinsic border-box block size in CSS pixels,
 * before the host's block size or its minimum and maximum constrain the writing room.
 *
 * The placeholder is a layer under the words, shown while the field is empty. It reads
 * the `placeholder` attribute, and a child in slot `placeholder` stands in its place when
 * a box wants more than one run of text there, such as a label and the key that sends.
 * It is drawn in the theme's muted ink; a box that wants another face for it styles
 * `::part(placeholder)`, which a slotted child inherits.
 *
 * A connected field holding words draws them in its editor. An empty one builds its
 * editor when the user arrives in it (`#build`), since a page can show many empty
 * fields the user never writes in. A field removed and not put back in the same task
 * keeps its state and destroys its editor, which releases the listeners CodeMirror
 * holds on the window and document; reconnecting builds another. `:state(ready)` means
 * the connected field draws its words: in its editor, or as an empty line. A reading
 * surface being replaced can keep its words in flow until then, so measuring the
 * connecting field never collapses the scrollport before it has content.
 *
 * The host is also the control accessibility tooling addresses, since nothing outside a
 * closed root sees into it: it takes `role="textbox"`, `aria-multiline` and a tab stop
 * unless the page gave it its own, and it carries the name, description and busy state
 * the page writes on it. The content node inside is where focus and assistive
 * technology land, so it wears the same `aria-label`, the placeholder as
 * `aria-placeholder`, and the host's description through `ariaDescribedByElements`,
 * the one reference that reaches from inside a shadow root to the page around it.
 *
 * A box whose Send action stands in the field's trailing corner sets
 * `--lf-field-end-room` to the room the action takes beyond the field's end padding.
 * The field keeps that room after its last words only, on the line the action stands
 * beside, so the lines above wrap at the box's full measure. Under a finger, whose hit
 * box is taller than a line, and while the field scrolls, other lines pass beside the
 * action too, so there the room is held on every line. A sent message that keeps the
 * draft's wrapping keeps the same room.
 *
 * Leaf's key dispatcher owns submission and Escape. Return inserts a newline unless
 * its owner cancels `lf-edit-return` to reserve the press for submission. Android's
 * EditContext supplies no native insertion after CodeMirror handles the press, so this
 * editing route is explicit. Shift+Enter inserts a line and continues
 * a list or quote. Mod+Z and Mod+Shift+Z walk one history: the words' edits, and the
 * steps an owner records for what its draft holds beside them (`record`), such as a
 * composer's drawing, each taken back or redone in the order it was made.
 *
 * The host is the textarea's scrollport. CodeMirror's content-sized inner scroller
 * never clips the words; the page sizes the host. When that room changes, the field
 * reveals its focused selection again under the new constraint. CodeMirror's edit
 * reveal may have preceded the owner's sizing pass, and its own resize observer
 * watches the inner scroller, whose natural height need not change with the host.
 * This reveal belongs to the host alone: resizing a focused field does not move a
 * reading pane the user scrolled away from it.
 */
import { scrollIntoView } from "../landing-scroll.js";
import { landingInsets } from "../geometry.js";
import {
  EditorView,
  EditorState,
  StateEffect,
  Compartment,
  Decoration,
  LanguageSupport,
  ViewPlugin,
  keymap,
  history,
  standardKeymap,
  historyKeymap,
  isolateHistory,
  invertedEffects,
  markdownLanguage,
  insertNewlineContinueMarkup,
} from "../../vendor/codemirror.esm.js";
import { LeafEditorView } from "../editor-view.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { loadMarkdown, markdownReady, placedMarkdownTokens } from "../markdown.js";
import { sizeObserver } from "../rendering.js";

const insertNewline = standardKeymap.find(({ key }) => key === "Enter").run;

const sheet = new CSSStyleSheet();
sheet.replaceSync(`
  :host { display: block; cursor: text; }
  /* CodeMirror's provider places its defaults in lf-base. This control owns the
     unlayered editor face: the host supplies type and colour, and these are the
     only internal padding declarations before Markdown's explicit insets below. */
  .cm-editor { font: inherit; color: inherit; background-color: transparent; }
  .cm-editor.cm-focused { outline: none; }
  .cm-scroller { font-family: inherit; line-height: inherit; overflow: visible; }
  .cm-content { padding: 0; caret-color: currentColor; min-height: 1lh; }
  /* An empty field draws no editor until the user arrives in it (#build). This box
     holds the empty line's place, as tall as the editor's line, and takes the focus
     that builds the editor. */
  .lf-field-rest { min-height: 1lh; outline: none; }
  .cm-line { padding: 0; }
  /* The placeholder is a layer under the words, as a textarea's is, never content in
     the line: a widget in an empty line is what the platform would draw the caret
     against. Both layers share one grid cell, inside the host's padding. */
  .lf-field { display: grid; }
  .lf-field > * { grid-area: 1 / 1; min-width: 0; }
  /* An owner moving the field's edges can carry the words from where they were with
     them, by the host's --lf-field-carry, and cut them to the box it draws growing, by
     --lf-field-cut (theme.css): a transform and a cut that move neither the field nor
     its layout. The field's content box cuts off what the field doesn't hold yet,
     such as a new line and its caret, and keeps the travel from widening the host's
     scrolling. A cut naming none is invalid, which leaves the words uncut. */
  .lf-field { overflow: clip; }
  .lf-field > * {
    translate: var(--lf-field-carry);
    clip-path: inset(var(--lf-field-cut));
  }
  /* The placeholder is one line that never widens the box — a response bar sizes to the
     words — and shortens with an ellipsis where the box is narrow, so it reads the same
     height whether it shows the plain words or a keyed hint. */
  .lf-field-placeholder { pointer-events: none; white-space: nowrap;
    contain: inline-size; overflow-x: clip; text-overflow: ellipsis;
    color: var(--muted); }
  :host(:not(:state(placeholder-shown))) .lf-field-placeholder { visibility: hidden; }
  /* The trailing action's room, after the last word. A box too narrow for it on the
     word's line takes it on a line of its own, so the field grows rather than run a
     word under the action. */
  .cm-line.lf-field-last::after { content: ""; display: inline-block;
    inline-size: var(--lf-field-end-room); }
  /* The placeholder is a single line, so it stands where a last line would. */
  .lf-field-placeholder { padding-inline-end: var(--lf-field-end-room); }
  /* The action stands beside more than the last line under a finger, whose hit box is
     taller than a line, and in a scrolled field, which carries other lines past it. */
  @media (pointer: coarse) {
    .lf-field { padding-inline-end: var(--lf-field-end-room); }
    .lf-field-placeholder { padding-inline-end: 0; }
    .cm-line.lf-field-last::after { content: none; }
  }
  :host([data-scrolls]) .lf-field { padding-inline-end: var(--lf-field-end-room); }
  :host([data-scrolls]) .cm-line.lf-field-last::after { content: none; }
  /* A draft wears the sent message's faces. Strong, emphasis and strikethrough are the
     elements themselves, which the platform dresses here as it does in the message;
     the rest read the theme's tokens, since its element rules stop at this root. A
     heading is bold, as the platform draws one, at the size of the words around it. A
     block is drawn line by line, so a code block's frame is each line's sides, closed
     above its first line and below its last. Syntax that holds its room while the
     caret is away, as a code fence's line does, is there unseen and unspoken. */
  .lf-md-mark { color: var(--muted); }
  .lf-md-unseen { color: transparent; }
  code { font-family: var(--mono); font-size: var(--code-inline-size);
    background: var(--code-bg); border-radius: var(--code-inline-r);
    padding: var(--code-inline-pad); box-decoration-break: slice; }
  .lf-md-heading { font-weight: bold; }
  .lf-md-link { color: var(--accent); text-decoration: underline var(--link-underline);
    text-underline-offset: var(--link-underline-offset); }
  .lf-md-quote { border-inline-start: var(--quote-rule); font-style: var(--quote-style);
    padding-inline-start: var(--quote-inset); color: var(--muted);
    --lf-marker-inset: var(--quote-inset); }
  /* A quote's and a list item's words stand where the message's do, and the source's
     marker stands in the inset before them, unseen while the caret is away, so
     revealing it moves no word. A list item's lines stand one list inset in per level,
     under the platform's own list marker, as in the message, so it is the same bullet
     or number at the same place. */
  .lf-md-item { margin-inline-start: calc(var(--lf-list-depth) * var(--list-inset));
    --lf-marker-inset: var(--list-inset); }
  .lf-md-marker { display: inline-flex; justify-content: flex-end; white-space: pre;
    inline-size: var(--lf-marker-inset);
    margin-inline-start: calc(-1 * var(--lf-marker-inset)); }
  .lf-md-listed { display: list-item; }
  .lf-md-disc { list-style-type: disc; }
  .lf-md-circle { list-style-type: circle; }
  .lf-md-square { list-style-type: square; }
  .lf-md-number { list-style-type: decimal; }
  .lf-md-code-block { font-family: var(--mono); font-size: var(--code-size);
    line-height: var(--code-line); color: var(--code-ink); background: var(--pre-bg);
    font-variant-ligatures: none; border-inline: 1px solid var(--code-border);
    padding-inline: var(--pre-inset); }
  .lf-md-code-first { border-block-start: 1px solid var(--code-border);
    border-start-start-radius: var(--r); border-start-end-radius: var(--r); }
  .lf-md-code-last { border-block-end: 1px solid var(--code-border);
    border-end-start-radius: var(--r); border-end-end-radius: var(--r); }
  /* Code with no fence lines takes the message's padding at its ends instead. */
  .lf-md-code-bare.lf-md-code-first { padding-block-start: var(--pre-pad-block); }
  .lf-md-code-bare.lf-md-code-last { padding-block-end: var(--pre-pad-block); }
`);

// A step an owner recorded in the words' history (`record`): `run` makes it happen when
// the history reaches it, and `back` is the step the other way.
const ownerStep = StateEffect.define();

const hide = Decoration.replace({});
const dim = Decoration.mark({ class: "lf-md-mark" });
const link = Decoration.mark({ class: "lf-md-link" });
const unseen = Decoration.mark({
  class: "lf-md-unseen",
  attributes: { "aria-hidden": "true" },
});
const marker = Decoration.mark({
  class: "lf-md-marker lf-md-unseen",
  attributes: { "aria-hidden": "true" },
});
const shownMarker = Decoration.mark({ class: "lf-md-marker lf-md-mark" });
const line = (cls) => Decoration.line({ class: cls });
// A list item's line at its depth, wearing the marker a message's list draws there: the
// bullet the platform's style sheet nests, or the item's number in its list. An item's
// later line, and one whose source marker shows, wear none.
const BULLETS = ["lf-md-disc", "lf-md-circle", "lf-md-square"];
const itemLine = (depth, kind, number) =>
  Decoration.line({
    class: kind ? `lf-md-item lf-md-listed ${kind}` : "lf-md-item",
    attributes: {
      style: `--lf-list-depth: ${depth}${kind === "lf-md-number" ? `; counter-set: list-item ${number}` : ""}`,
    },
  });

// The inline constructs the preview draws, by the renderer's token type: each as the
// element the renderer sends it as.
const INLINE = {
  code_inline: Decoration.mark({ tagName: "code" }),
  em_open: Decoration.mark({ tagName: "em" }),
  strong_open: Decoration.mark({ tagName: "strong" }),
  s_open: Decoration.mark({ tagName: "s" }),
};

// Whether the selection touches [from, to], ends included: the caret standing just
// after a closing backtick still reveals it, so the user can delete what they see.
const touches = (state, from, to) =>
  state.selection.ranges.some((range) => range.from <= to && range.to >= from);

// The draft as the renderer reads it, placed. Empty until the renderer has loaded.
const read = (state) => {
  return placedMarkdownTokens(state.doc.toString());
};

function decorate(state, placed) {
  const out = [];
  // The ends of the lists open at the token being read, each list line's item, and the
  // code blocks, whose lines their own reading indents.
  const lists = [];
  const items = new Map();
  const code = [];
  const add = (from, to, deco) => {
    if (from >= to) return;
    // A hidden range may not hold a line break; such syntax stays drawn.
    if (deco === hide && state.doc.sliceString(from, to).includes("\n")) deco = dim;
    out.push(deco.range(from, to));
  };
  const lines = (from, to, each) => {
    for (let at = from; at < to;) {
      const current = state.doc.lineAt(at);
      each(current);
      at = current.to + 1;
    }
  };
  for (const {
    token,
    from,
    to,
    contentFrom,
    contentTo,
    escapes,
    markers,
    contentLines,
  } of placed) {
    const syntax = touches(state, from, to) ? dim : hide;
    if (token.type === "code_inline" || contentFrom !== undefined) {
      const words =
        token.type === "code_inline"
          ? [from + token.markup.length, to - token.markup.length]
          : [contentFrom, contentTo];
      if (words[0] > words[1]) continue;
      if (INLINE[token.type]) add(from, to, INLINE[token.type]);
      else if (token.type === "link_open" && token.meta.linked)
        add(words[0], words[1], link);
      add(from, words[0], syntax);
      add(words[1], to, syntax);
    } else if (token.type === "text") {
      for (const at of escapes ?? [])
        add(at, at + 1, touches(state, at, at + 2) ? dim : hide);
    } else if (token.type === "heading_open") {
      lines(...contentLines, (each) => {
        out.push(line("lf-md-heading").range(each.from));
      });
      for (const [a, b] of markers)
        add(a, b, token.markup.startsWith("#") ? syntax : dim);
    } else if (token.type === "fence" || token.type === "code_block") {
      code.push([from, to]);
      // Each line of code keeps the indent the parser's reading of it keeps; the rest,
      // a list item's or an indented block's own four spaces, the message drops.
      const body = token.content.split("\n");
      const opened = state.doc.lineAt(from).number + (token.type === "fence" ? 1 : 0);
      lines(from, to, (each) => {
        const ends = [
          each.from <= from ? " lf-md-code-first" : "",
          each.to + 1 >= to ? " lf-md-code-last" : "",
          token.type === "code_block" ? " lf-md-code-bare" : "",
        ].join("");
        out.push(line(`lf-md-code-block${ends}`).range(each.from));
        const kept = body[each.number - opened];
        if (kept === undefined || each.number - opened >= body.length - 1) return;
        const lead = each.text.match(/^[ \t]*/)[0].length;
        add(each.from, each.from + lead - kept.match(/^[ \t]*/)[0].length, hide);
      });
      // A fence's lines keep their room, as the message's code keeps its padding.
      const fence = touches(state, from, to - 1) ? dim : unseen;
      for (const [a, b] of markers ?? []) add(a, b, fence);
    } else if (token.type === "blockquote_open") {
      lines(from, to, (each) => {
        out.push(line("lf-md-quote").range(each.from));
      });
      for (const [a, b] of markers)
        add(a, b, touches(state, a, b) ? shownMarker : marker);
    } else if (
      token.type === "bullet_list_open" ||
      token.type === "ordered_list_open"
    ) {
      while (lists.at(-1)?.to <= from) lists.pop();
      const ordered = token.type === "ordered_list_open";
      lists.push({ to, next: ordered ? Number(token.attrGet("start") ?? 1) : null });
    } else if (token.type === "list_item_open") {
      while (lists.at(-1)?.to <= from) lists.pop();
      const list = lists.at(-1);
      const depth = lists.length;
      // An item's later lines stand under its words, their indent hidden as the
      // message drops it, and never revealed, so the words don't jump as the caret
      // arrives: a paragraph's whole indent, and in code what the code's reading drops
      // (above). A nested item, read after its parent, takes its own lines.
      const head = state.doc.lineAt(from);
      const [at, end] = markers[0];
      // The marker's own indent stands in the inset with it. A quote's line keeps the
      // quote's rule and prefix at its start, where the platform's marker can't stand,
      // so an item there keeps its source marker, drawn as the prefix is.
      const start = at - head.text.slice(0, at - head.from).match(/[ \t]*$/)[0].length;
      if (head.text.slice(0, start - head.from).trim()) {
        add(start, end, dim);
        continue;
      }
      lines(head.to + 1, Math.min(to, state.doc.length), (each) => {
        items.set(each.from, { depth, continued: true });
      });
      const kind =
        list.next === null
          ? BULLETS[Math.min(depth, BULLETS.length) - 1]
          : "lf-md-number";
      const shown = state.selection.ranges.some(
        (range) => range.from < end && range.to >= start,
      );
      items.set(head.from, { depth, kind: shown ? null : kind, number: list.next });
      if (list.next !== null) list.next++;
      add(start, end, shown ? shownMarker : marker);
    }
  }
  for (const [from, { depth, kind, number, continued }] of items) {
    out.push(itemLine(depth, kind, number).range(from));
    if (!continued || code.some(([a, b]) => from >= a && from < b)) continue;
    add(from, from + state.doc.lineAt(from).text.match(/^[ \t]*/)[0].length, hide);
  }
  return Decoration.set(out, true);
}

// The draft is read by the renderer that will send it, so the preview styles exactly what
// the message will: the same constructs, the same links. The reading is taken again when
// the words change and the styling when the selection moves. The renderer loads lazily;
// until it has, the words stand plain, and its arrival draws every open field.
const livePreview = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.live = true;
      this.placed = read(view.state);
      this.decorations = decorate(view.state, this.placed);
      this.judged = markdownReady();
      if (!this.judged)
        loadMarkdown().then(
          () => this.live && view.dispatch({}),
          () => {},
        );
    }
    destroy() {
      this.live = false;
    }
    update(update) {
      const judged = markdownReady();
      if (update.docChanged || judged !== this.judged) {
        this.judged = judged;
        this.placed = read(update.state);
      } else if (!update.selectionSet) return;
      this.decorations = decorate(update.state, this.placed);
    }
  },
  { decorations: (plugin) => plugin.decorations },
);

// The last line, while it holds words. A blank last line has none to run under the
// action, and an inline box after its break would stand on a line of its own. The room
// stays on the last line rather than on the last with words, so the line above gives it
// up as Shift+Enter opens a line, not when the first character lands on the new one: the
// keystroke that changes the lines is the one that rewraps them.
const lastLine = Decoration.line({ class: "lf-field-last" });
const lastWithWords = (state) => {
  const last = state.doc.line(state.doc.lines);
  return last.text.trim() ? last : null;
};
const lastLineRoom = EditorView.decorations.compute(["doc"], (state) => {
  const last = lastWithWords(state);
  return last ? Decoration.set([lastLine.range(last.from)]) : Decoration.none;
});

/** @typedef {LeafText} LeafTextElement For its tag (`runtime-globals.d.ts`). */
class LeafText extends HTMLElement {
  // The field's one model. Until the field has an editor it is a bare EditorState,
  // which holds the value, selection and configuration without a DOM; building the
  // editor hands it to the view that edits it from then on (`#build`).
  #model;
  #view = null;
  // The empty line's place while the field has no editor, and the node focus lands on
  // there, whichever route brought it.
  #rest = document.createElement("div");
  #nativeInput = false;
  #root;
  #internals = null;
  #editable = new Compartment();
  #history = new Compartment();
  #attributes = new Compartment();
  #placeholderLayer = document.createElement("div");
  #placeholderText = document.createTextNode("");
  #frame = document.createElement("div");
  #readOnly = false;
  #sizes = sizeObserver(() => {
    const view = this.#view;
    if (view?.hasFocus)
      view.requestMeasure({
        key: this,
        read: () => {
          const caret = view.coordsAtPos(view.state.selection.main.head);
          const box = this.getBoundingClientRect();
          const { scaleX, scaleY } = view;
          // The caret's whole line, its leading as well as the caret, lands inside
          // the host's `scroll-padding`, as a landing does.
          const inset = landingInsets(this);
          const leading = caret
            ? Math.max(
                0,
                (parseFloat(getComputedStyle(this).lineHeight) * scaleY -
                  (caret.bottom - caret.top)) /
                  2,
              )
            : 0;
          return {
            caret,
            scaleX,
            scaleY,
            top: box.top + (this.clientTop + inset.top) * scaleY + leading,
            left: box.left + (this.clientLeft + inset.left) * scaleX,
            // client dimensions round fractional CSS sizes. Keep the trailing
            // edges on the actual box, inset by its native border and scrollbar.
            bottom:
              box.bottom -
              (this.offsetHeight - this.clientTop - this.clientHeight + inset.bottom) *
                scaleY -
              leading,
            right:
              box.right -
              (this.offsetWidth - this.clientLeft - this.clientWidth + inset.right) *
                scaleX,
          };
        },
        write: ({ caret, top, left, bottom, right, scaleX, scaleY }) => {
          if (!caret) return;
          // Native scroll offsets quantize a fractional correction. Round away from
          // zero so a caret just beyond an edge actually enters the host's scrollport.
          const wholePixel = (distance) =>
            distance < 0 ? Math.floor(distance) : Math.ceil(distance);
          this.scrollBy({
            top: wholePixel(
              (Math.min(0, caret.top - top) + Math.max(0, caret.bottom - bottom)) /
                scaleY,
            ),
            left: wholePixel(
              (Math.min(0, caret.left - left) + Math.max(0, caret.right - right)) /
                scaleX,
            ),
            behavior: "instant",
          });
        },
      });
  });

  // Host overflow holds the action's room on every line. The host stops at the page's
  // height limit while words grow inside it, so the reading watches the editor's
  // content too. Editor updates and size changes share its read/write phase: the room
  // changes layout there, rather than feeding back into resize observer delivery. The
  // same reading says which edges words run past (`more-above`, `more-below`), read
  // again as the host scrolls, so an owner can show there is more without a scrollbar.
  // A scroll timeline would say it in CSS alone, but Firefox lacks scroll timelines.
  #overflow = sizeObserver(() => this.#measureOverflow());

  #measureOverflow() {
    this.#view?.requestMeasure({
      key: this.#overflow,
      // Words, not the host's padding, run past an edge.
      read: () => {
        const style = getComputedStyle(this);
        return {
          scrolls: this.scrollHeight > this.clientHeight,
          above: this.scrollTop > Number.parseFloat(style.paddingTop) + 1,
          below:
            this.scrollTop + this.clientHeight <
            this.scrollHeight - Number.parseFloat(style.paddingBottom) - 1,
        };
      },
      write: (reading) => {
        // WebKit can retain style from a removed custom state after the words shrink.
        // An attribute invalidates the field's CSS at the same layout boundary.
        if (this.hasAttribute("data-scrolls") !== reading.scrolls)
          this.toggleAttribute("data-scrolls", reading.scrolls);
        for (const [state, on] of [
          ["more-above", reading.scrolls && reading.above],
          ["more-below", reading.scrolls && reading.below],
        ]) {
          // Adding a state already set restyles all the same, on every scrolled frame.
          if (this.#internals.states.has(state) === on) continue;
          if (on) this.#internals.states.add(state);
          else this.#internals.states.delete(state);
        }
      },
    });
  }

  static observedAttributes = ["aria-label", "aria-describedby", "placeholder"];

  constructor() {
    super();
    this.#root = this.attachShadow({ mode: "closed", delegatesFocus: true });
    this.#frame.className = "lf-field";
    this.#placeholderLayer.className = "lf-field-placeholder";
    this.#placeholderLayer.setAttribute("aria-hidden", "true");
    this.#placeholderLayer.setAttribute("part", "placeholder");
    const hint = document.createElement("slot");
    hint.name = "placeholder";
    hint.append(this.#placeholderText);
    this.#placeholderLayer.append(hint);
    this.#rest.className = "lf-field-rest";
    // The break an empty editable line holds, as the editor's own empty line does, so
    // the place reads the same value to assistive technology.
    this.#rest.append(document.createElement("br"));
    // In `focusin`, never `focus`: Chrome and Firefox send no `focusin` for a node that
    // passes focus on in its own `focus` handler, and the move inside the closed root
    // reaches nothing outside it, so the page would never hear the field take focus.
    this.#rest.addEventListener("focusin", () => this.#build());
    this.#frame.append(this.#placeholderLayer, this.#rest);
    this.#root.append(this.#frame);
    this.#model = this.#create("");
    this.#dressRest();
    this.addEventListener("mousedown", (event) => this.#pressPadding(event));
    // Words dragged in drop where the editor will take them.
    this.addEventListener("dragenter", () => {
      if (!this.#view) this.#build();
    });
    this.addEventListener("scroll", () => this.#measureOverflow(), { passive: true });
    this.#root.addEventListener("beforeinput", () => this.#beforeEdit(), {
      capture: true,
    });
    // The content node's own input events would reach the host too, retargeted, and
    // announce every edit twice. The host's is the one the page hears.
    for (const type of ["input", "beforeinput"])
      this.#root.addEventListener(type, (event) => event.stopPropagation());
  }

  // A fresh state holding `text`, caret at its end, under the field's current
  // configuration. A new state is also a new undo history.
  #create(text) {
    return EditorState.create({
      doc: text,
      selection: { anchor: text.length },
      extensions: [
        // DOM input has already changed the words when CodeMirror reads it, so its
        // bracket started at beforeinput. EditContext leaves rendering to the editor;
        // its transactions, like commands, still start before the DOM changes.
        EditorView.inputHandler.of((view, _from, _to, _text, insert) => {
          this.#nativeInput = !view.contentDOM.editContext;
          try {
            view.dispatch(insert());
          } finally {
            this.#nativeInput = false;
          }
          return true;
        }),
        this.#history.of(history()),
        invertedEffects.of((tr) =>
          tr.effects
            .filter((effect) => effect.is(ownerStep))
            .map(({ value }) => ownerStep.of({ run: value.back, back: value.run })),
        ),
        keymap.of([
          {
            key: "Enter",
            run: (view) =>
              this.dispatchEvent(new Event("lf-edit-return", { cancelable: true })) &&
              insertNewline(view),
          },
          { key: "Shift-Enter", run: insertNewlineContinueMarkup },
          // Outside a list or quote, a plain new line, which asks to be seen as typing
          // does, so a field at its height limit scrolls to it.
          {
            key: "Shift-Enter",
            run: (view) => (
              view.dispatch(
                view.state.update(view.state.replaceSelection("\n"), {
                  scrollIntoView: true,
                  userEvent: "input",
                }),
              ),
              true
            ),
          },
          ...standardKeymap.filter(
            ({ key }) => key !== "Escape" && key !== "Enter" && key !== "Mod-Enter",
          ),
          ...historyKeymap,
        ]),
        new LanguageSupport(markdownLanguage),
        livePreview,
        lastLineRoom,
        EditorView.lineWrapping,
        this.#editable.of(EditorState.readOnly.of(this.#readOnly)),
        this.#attributes.of(EditorView.contentAttributes.of(this.#contentAttributes())),
      ],
    });
  }

  attributeChangedCallback(name) {
    if (name === "placeholder") this.#placeholderText.data = this.placeholder;
    if (name === "aria-describedby") return this.#describe();
    this.#dressRest();
    this.#apply({
      effects: this.#attributes.reconfigure(
        EditorView.contentAttributes.of(this.#contentAttributes()),
      ),
    });
  }

  // A move by `moveBefore` keeps the editor and its focus but collapses the native
  // selection in it, which CodeMirror would read back as a caret at the start. With this
  // callback the move is no disconnection, and the view puts its caret back as it lands.
  connectedMoveCallback() {
    this.#view?.placeSelection();
  }

  connectedCallback() {
    // A move by `insertBefore` reconnects within the task, keeping the view
    // (`disconnectedCallback`); the hold that returns the user restores the caret.
    if (this.#view) return;
    if (!this.hasAttribute("role")) this.setAttribute("role", "textbox");
    if (!this.hasAttribute("aria-multiline"))
      this.setAttribute("aria-multiline", "true");
    // A tab stop, as a textarea is: delegation already stops Tab in the words, and a
    // host reading -1 is one every stop-counting walk would miss.
    if (!this.hasAttribute("tabindex")) this.tabIndex = 0;
    this.#internals ??= this.attachInternals();
    this.#root.adoptedStyleSheets = [sheet];
    if (this.#model.doc.length) this.#build();
    else this.#describe();
    this.#paintEmpty();
    this.#internals.states.add("ready");
  }

  // Until the field has an editor, its empty line's place stands in for the editor's
  // content node to assistive technology, so the tree reads the same before and after
  // the editor builds. CodeMirror's node is a multiline textbox, `contenteditable` (its
  // theme makes it plain text only) and `aria-readonly` while the field is read-only,
  // and it wears the field's name, hint and description (`#describe`). This place
  // declares the same, and being editable it is a tab stop where the editor's node is.
  #dressRest() {
    const wanted = {
      ...this.#contentAttributes(),
      role: "textbox",
      "aria-multiline": "true",
      contenteditable: "plaintext-only",
      ...(this.#readOnly && { "aria-readonly": "true" }),
    };
    for (const name of ["aria-label", "aria-placeholder", "aria-readonly"])
      if (!(name in wanted)) this.#rest.removeAttribute(name);
    for (const [name, value] of Object.entries(wanted))
      if (this.#rest.getAttribute(name) !== value) this.#rest.setAttribute(name, value);
  }

  // A connected field draws its words in an editor, and an empty one builds its editor
  // only when the user arrives in it, by its own `focus()`, a press, or native focus by
  // any route, which lands on the empty line's place, or when words are written into
  // it. Building on arrival hands focus to the words in the same task, so the first key
  // the user types lands in them. A page holding many fields, such as one under each
  // list of options, builds none of them to show itself.
  #build() {
    this.#view = new LeafEditorView({
      root: this.#root,
      parent: this.#frame,
      state: this.#model,
      // Dispatched word changes are the user's. The value setter updates the view
      // directly and silently; an owner's `record` changes no words.
      dispatchTransactions: (transactions, view) => {
        const edited = transactions.some((tr) => tr.docChanged);
        if (edited && !this.#nativeInput) this.#beforeEdit();
        view.update(transactions);
        for (const tr of transactions)
          if (tr.isUserEvent("undo") || tr.isUserEvent("redo"))
            for (const effect of tr.effects)
              if (effect.is(ownerStep)) effect.value.run();
        this.#paintEmpty();
        this.#measureOverflow();
        if (edited) this.dispatchEvent(new Event("input", { bubbles: true }));
        else if (transactions.some((tr) => tr.isUserEvent("select")))
          this.dispatchEvent(new Event("lf-caret-move", { bubbles: true }));
      },
    });
    this.#model = null;
    this.#sizes.observe(this);
    this.#overflow.observe(this);
    // The host can keep the same height when a long draft shrinks. Watch the words'
    // box too: its height changes even when the scroller's viewport does not.
    this.#overflow.observe(this.#view.contentDOM);
    // The scroller is focusable only so a press on it keeps focus in the editor, and
    // the field's scroller never scrolls; left focusable it is the node the root
    // delegates focus to, which holds no caret.
    this.#view.scrollDOM.removeAttribute("tabindex");
    this.#describe();
    // Focus that landed on the empty line's place moves on into the words, in that
    // place's `focusin`, which goes on to reach the page as the field's.
    if (this.#root.activeElement === this.#rest) {
      this.#view.contentDOM.focus({ preventScroll: true });
      this.#view.placeSelection();
    }
    this.#rest.hidden = true;
    this.#measureOverflow();
  }

  #beforeEdit() {
    this.dispatchEvent(new Event("lf-before-edit", { bubbles: true }));
  }

  // A move between parents reconnects within the task and keeps its editor.
  disconnectedCallback() {
    queueMicrotask(() => {
      if (this.isConnected) return;
      this.#internals.states.delete("ready");
      if (!this.#view) return;
      this.#model = this.#view.state;
      this.#sizes.disconnect();
      this.#overflow.disconnect();
      this.#view.destroy();
      this.#view = null;
      this.#rest.hidden = false;
    });
  }

  #describe() {
    if (!this.isConnected) return;
    const content = this.#view?.contentDOM ?? this.#rest;
    const root = /** @type {Document | ShadowRoot} */ (this.getRootNode());
    const described = (this.getAttribute("aria-describedby") ?? "")
      .split(/\s+/)
      .filter(Boolean)
      .map((id) => root.getElementById(id))
      .filter(Boolean);
    const current = content.ariaDescribedByElements ?? [];
    if (
      described.length !== current.length ||
      described.some((element, at) => element !== current[at])
    )
      content.ariaDescribedByElements = described;
  }

  // The editor adapter places its recorded caret without native scrolling. The
  // field reveals itself separately when its caller requests ordinary focus.
  focus(options) {
    if (!this.#view && this.isConnected) this.#build();
    if (!this.#view) return;
    this.#view.focus();
    if (this.#root.activeElement !== this.#view.contentDOM) return;
    if (!options?.preventScroll) scrollIntoView(this, { block: "nearest" });
  }

  blur() {
    this.#view?.contentDOM.blur();
  }

  // A press on the box outside the editor's own area — its padding — lands in the words
  // at the nearest character, the way a textarea's does. Presses inside the editor are
  // CodeMirror's to place.
  #pressPadding(event) {
    if (event.button !== 0) return;
    if (!this.#view) {
      // The field is empty, so wherever the press lands the caret stands at its start.
      // Another button's press focuses the empty line's place natively, which builds the
      // editor before the press's own action, such as a context menu's, reads its target.
      event.preventDefault();
      this.focus({ preventScroll: true });
      return;
    }
    const area = this.#view.scrollDOM.getBoundingClientRect();
    const { clientX: x, clientY: y } = event;
    if (x >= area.left && x < area.right && y >= area.top && y < area.bottom) return;
    event.preventDefault();
    const clamp = (value, low, high) => Math.min(Math.max(value, low), high - 1);
    const at = this.#view.posAtCoords(
      { x: clamp(x, area.left, area.right), y: clamp(y, area.top, area.bottom) },
      false,
    );
    this.#view.focus();
    this.#view.dispatch({ selection: { anchor: at } });
  }

  get #state() {
    return this.#view?.state ?? this.#model;
  }

  #apply(spec) {
    if (!this.#view && spec.changes && this.isConnected) this.#build();
    if (this.#view) this.#view.dispatch(spec);
    else this.#model = this.#model.update(spec).state;
  }

  #contentAttributes() {
    const attributes = {
      spellcheck: "true",
      autocorrect: "on",
      autocapitalize: "sentences",
    };
    if (this.placeholder) attributes["aria-placeholder"] = this.placeholder;
    const label = this.getAttribute("aria-label");
    if (label !== null) attributes["aria-label"] = label;
    return attributes;
  }

  #paintEmpty() {
    if (this.#state.doc.length) this.#internals.states.delete("placeholder-shown");
    else this.#internals.states.add("placeholder-shown");
  }

  // Where the field holds its action's room now: `every-line`, `last-line` after its
  // last words, or `none` while its last line is blank.
  get endRoom() {
    if (parseFloat(getComputedStyle(this.#frame).paddingInlineEnd) > 0)
      return "every-line";
    return lastWithWords(this.#state) ? "last-line" : "none";
  }

  get value() {
    return this.#state.doc.toString();
  }

  edit(text) {
    text = String(text).replace(/\r\n?/g, "\n");
    if (text === this.value) return;
    this.#apply({
      changes: { from: 0, to: this.#state.doc.length, insert: text },
      selection: { anchor: text.length },
      userEvent: "input.dictation",
    });
  }

  // Records a change the owner has just made outside the words as a step of the words'
  // history, standing alone: taking the step back calls `undo`, redoing it calls `redo`.
  record(undo, redo) {
    this.#apply({
      effects: ownerStep.of({ run: redo, back: undo }),
      annotations: isolateHistory.of("full"),
    });
  }

  // Forgets the history and keeps the words, the caret and the editor's DOM, for a box
  // that takes up a draft as it stands. Dropping the history's field and adding it back
  // starts it empty.
  restartHistory() {
    this.#apply({ effects: this.#history.reconfigure([]) });
    this.#apply({ effects: this.#history.reconfigure(history()) });
  }

  get naturalBlockSize() {
    const host = getComputedStyle(this);
    return (
      parseFloat(getComputedStyle(this.#frame).blockSize) +
      parseFloat(host.paddingBlockStart) +
      parseFloat(host.paddingBlockEnd) +
      parseFloat(host.borderBlockStartWidth) +
      parseFloat(host.borderBlockEndWidth)
    );
  }

  set value(text) {
    text = String(text ?? "").replace(/\r\n?/g, "\n");
    if (text === this.value) return;
    if (!this.#view && this.isConnected) this.#build();
    if (!this.#view) {
      this.#model = this.#create(text);
      return;
    }
    // Loading another draft ends the old native composition. Deactivating its
    // attachment resets the platform's replacement range without moving focus.
    const content = this.#view.contentDOM;
    const composing = this.#view.composing && content.editContext;
    if (composing) content.editContext = null;
    // Updating the live view keeps its native input context in sync with the words.
    // Remove and restore history in successive states so the loaded draft starts it
    // empty, while both transactions paint together and announce no user edit.
    const reset = this.#view.state.update({
      changes: { from: 0, to: this.#view.state.doc.length, insert: text },
      selection: { anchor: text.length },
      effects: this.#history.reconfigure([]),
    });
    const fresh = reset.state.update({
      effects: this.#history.reconfigure(history()),
    });
    this.#view.update([reset, fresh]);
    if (composing) content.editContext = composing;
    this.#paintEmpty();
    this.#measureOverflow();
  }

  get selectionStart() {
    return this.#state.selection.main.from;
  }
  get selectionEnd() {
    return this.#state.selection.main.to;
  }
  get selectionDirection() {
    const { main } = this.#state.selection;
    return main.empty ? "none" : main.head < main.anchor ? "backward" : "forward";
  }
  // A textarea's clamping: each end within the words, and a start past the end moved to
  // the end.
  setSelectionRange(start, end, direction = "none") {
    const length = this.#state.doc.length;
    const to = Math.min(Math.max(Number(end) || 0, 0), length);
    const from = Math.min(Math.max(Number(start) || 0, 0), to);
    this.#apply({
      selection:
        direction === "backward"
          ? { anchor: to, head: from }
          : { anchor: from, head: to },
    });
  }
  select() {
    this.setSelectionRange(0, this.#state.doc.length);
  }

  get placeholder() {
    return this.getAttribute("placeholder") ?? "";
  }
  set placeholder(text) {
    this.setAttribute("placeholder", text);
  }

  get readOnly() {
    return this.#readOnly;
  }
  set readOnly(on) {
    this.#readOnly = Boolean(on);
    this.#dressRest();
    this.#apply({
      effects: this.#editable.reconfigure(EditorState.readOnly.of(this.#readOnly)),
    });
  }

  get name() {
    return this.getAttribute("name") ?? "";
  }
  set name(value) {
    this.setAttribute("name", value);
  }
}

if (!customElements.get(TEXT_FIELD)) customElements.define(TEXT_FIELD, LeafText);

export const textField = () => document.createElement(TEXT_FIELD);
