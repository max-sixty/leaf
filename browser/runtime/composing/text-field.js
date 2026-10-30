/* The runtime's text field: a Markdown editor that presents itself as a textarea.
 *
 * Every composer the runtime builds is a `leaf-text`. Inside a closed shadow root it
 * runs CodeMirror over the draft's exact source, and draws that source the way a sent
 * message will read: inline code in code type, emphasis and strong in their weights, a
 * link as a link, a heading in bold, a list item at the message's inset under the
 * message's own marker, a picture as the picture, drawn after its source while the
 * caret is in it, and a link that leaves the page with the mark the page draws after
 * one (prepaint.js). The syntax that produces each (backticks, asterisks, brackets,
 * hashes, list markers, a picture's source) is hidden unless the selection touches the
 * construct. List markers reveal their source only inside the marker: the caret after
 * its trailing space is ready to type content, so even an empty new item already shows
 * its bullet or number. The user can move back into the marker to edit every source
 * character. Nothing is converted: the value is always the source the user typed,
 * which is what the agent reads. The constructs come from the renderer that sends the
 * message (`markdownTokens`), never from a second grammar, so the preview and the
 * message agree on what is a link, a heading or code. CodeMirror's own Markdown
 * grammar serves only editing: Shift+Enter continuing a list.
 *
 * A field that edits words where they are shown, as a draft's does over its prose, names
 * the element that shows them (`facesOf`) and draws them in that display's faces
 * instead of the message's: each heading and code block in the type, padding and indent
 * the page gives it there, each outermost block's quote and list insets, and the
 * display's gap between two outermost blocks in place of the blank lines that part them
 * in the source, so no word moves as the editor opens (browser/AGENTS.md, "Editing in
 * place"). The cascade answers what those faces are: as the editor builds, and when its
 * width changes, an empty copy of that element holding one of each block stands hidden
 * beside the field, where the page's own rules and density reach it, and is read and
 * removed in the same task. The rules it yields go in a sheet of the field's own, which
 * the lines' classes name, so the field draws nothing differently without one. A code
 * fence's line and a Setext heading's rule then stand for the block's padding while the
 * caret is away from that line. A list's inner gaps, a quote's inner blocks and a table
 * keep the source's lines. Rejected: rules the theme states for each element also stated
 * for parts the field exposes, which can set type but not the gaps, since CodeMirror
 * measures a line without its margins and a gap collapses two blocks'; and a style
 * attribute on each line, which CodeMirror writes again on every redraw.
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
 * That bracket bubbles across enclosing shadow stages, as a textarea's input does.
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
 * CodeMirror isn't part of the page's opening: it loads once the page has presented
 * (field-editor.js, `loadFieldEditor`), well before a reader usually starts writing, so
 * arriving in a field still builds its editor in the same turn. A field that must build
 * sooner, holding words before then or with the user arriving in it, keeps a rendering
 * hold until CodeMirror arrives, draws its words plain in the empty line's place, and
 * keeps the user's focus there; what they type meanwhile lands natively in that place,
 * which the field reads back as its value, so the editor builds holding it. Rejected:
 * loading CodeMirror with the page, about 345 KB of the bytes before the server's
 * state shows, for a capability most openings never use.
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
 * The field keeps that room at the end of every line, so where its words wrap depends
 * only on the words and the box's width, never on which line Send stands beside or on
 * what follows the last word. A sent message that keeps the draft's wrapping keeps the
 * same room. Rejected: the room after the last words only (#1871 to #3678), which ran
 * the lines above under Send's column but made the last line's wrapping turn on the
 * caret's surroundings: an inline spacer after the last word wrapped alone or carried
 * that word with it, so typing a space after a word could pull it back up a line,
 * and it needed separate modes under a finger and while the field scrolled.
 *
 * A box may instead give the words the whole line and set `--lf-field-corner` to the
 * square at the field's trailing foot its action stands in. The field then says
 * whether words in view, or its caret, reach that square (`:state(corner-taken)`), and
 * the box shows its action while the corner is free, and over the words only when
 * focus comes to it or the pointer rests on it. Wrapping still turns on nothing but the words; only the
 * action comes and goes. Under a mouse, Return sends when the action is hidden.
 *
 * Leaf's key dispatcher owns submission and Escape. Return inserts a newline unless
 * its owner cancels `lf-edit-return` to reserve the press for submission. Android's
 * EditContext supplies no native insertion after CodeMirror handles the press, so this
 * editing route is explicit. Shift+Enter inserts a line and continues a list or
 * quote. A host the page marks `aria-multiline="false"`, such as an option's title,
 * holds one line: Shift+Enter inserts nothing, a line break pasted or inserted any other
 * way becomes a space, and its owner reserves Return. Mod+Z
 * and Mod+Shift+Z walk one history: the words' edits, and the steps an owner records
 * for what its draft holds beside them (`record`), such as a composer's drawing, each
 * taken back or redone in the order it was made.
 *
 * The host is the textarea's scrollport. CodeMirror's content-sized inner scroller
 * never clips the words; the page sizes the host. The field reveals the caret's whole
 * row, its leading as well as the caret, inside the host's padding, so typing on the
 * last line rests the words at their end with nothing more to scroll to. A native
 * textarea reveals only the caret and leaves its foot's padding, and in Chromium part
 * of the row, out of view. An edit's reveal does this before the view carries the
 * caret out through the page, and when the host's room changes the field reveals its
 * focused caret again under the new constraint: CodeMirror's edit reveal may have
 * preceded the owner's sizing pass, and its own resize observer watches the inner
 * scroller, whose natural height need not change with the host. The resize reveal
 * belongs to the host alone: resizing a focused field does not move a reading pane
 * the user scrolled away from it.
 */
import { scrollIntoView } from "../landing-scroll.js";
import { moveScrollerBy } from "../scrolling.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { afterPresentation } from "../presentation.js";
import { loadFieldEditor, readFaces } from "./field-editor.js";
import { holdRendering, sizeObserver } from "../rendering.js";

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
     that builds the editor; while the editor loads, it holds the words, wrapped as
     the editor wraps them. */
  .lf-field-rest { min-height: 1lh; outline: none; white-space: pre-wrap;
    overflow-wrap: break-word; }
  .cm-line { padding: 0; }
  /* A space after a line's last word hangs past its end, as in a textarea and in the
     sent message (reading.css, \`.lf-msg-text > p\`), rather than taking room on the
     line and carrying the word to the next one, as CodeMirror's \`break-spaces\`
     does. */
  .cm-editor .cm-content.cm-lineWrapping { white-space: pre-wrap; }
  /* CodeMirror's caret stops beside a widget hang from the text's top, which stands
     above a line set tighter than its type, as a heading's is, and would make that
     line taller than the heading it draws. The field's caret is the platform's. */
  .cm-widgetBuffer { vertical-align: top; }
  /* The placeholder is a layer under the words, as a textarea's is, never content in
     the line: a widget in an empty line is what the platform would draw the caret
     against. Both layers share one grid cell, inside the host's padding. */
  .lf-field { display: grid; }
  .lf-field > * { grid-area: 1 / 1; min-width: 0; }
  /* An owner moving the field's edges can carry the words from where they were with
     them, by the host's --lf-field-carry, and cut them to the box it draws growing, by
     --lf-field-cut (base.css): a transform and a cut that move neither the field nor
     its layout. The field's content box cuts off what the field doesn't hold yet,
     such as a new line and its caret, and keeps the travel from widening the host's
     scrolling. A cut naming none is invalid, which leaves the words uncut. The clip
     reaches 2px past that box, the caret's width at a line's end: Firefox paints the
     caret from its offset onward and pulls it inside only a scroll container, so a
     caret after a line that fills the box, as a trailing space can, was
     cut away whole. Words an owner carries down from above the box, as a line removed
     carries them, need more: it sets --lf-field-reach as far as they travel, and
     stops the host scrolling meanwhile. Chrome refuses calc() here, so the reach
     replaces the caret's margin rather than adding to it, so the owner keeps at
     least 2px there and at the moving content's inline clip edges. */
  .lf-field { overflow: clip; overflow-clip-margin: var(--lf-field-reach, 2px); }
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
  /* The trailing action's room, on every line. */
  .lf-field { padding-inline-end: var(--lf-field-end-room); }
  /* A draft wears the sent message's faces, or where it stands in place, those its
     display gives each block (\`standBlocks\`), written on its lines over these. Strong,
     emphasis and strikethrough are the elements themselves, which the platform dresses
     here as it does in the message; the rest read the theme's tokens, since its element
     rules stop at this root. A heading is bold, as the platform draws one, at the size
     of the words around it. A block is drawn line by line, so a code block's frame is
     each line's sides, closed above its first line and below its last. Syntax that holds
     its room while the caret is away, as a code fence's line does, is there unseen and
     unspoken. Its glyphs go unfilled while its colour stays the words', because the
     caret can stand at the end of unseen text, as just past a new item's marker, and the
     browser draws it in that text's colour. */
  .lf-md-mark { color: var(--muted); }
  .lf-md-unseen { -webkit-text-fill-color: transparent; }
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
  /* A sent pre reserves 8px below its lines for a horizontal scrollbar. */
  .cm-line.lf-md-code-last { border-block-end: 1px solid var(--code-border);
    border-end-start-radius: var(--r); border-end-end-radius: var(--r);
    padding-block-end: 8px; }
  /* A picture fits the field as media fits its container on the page, centred on its
     line (base.css), and the mark after a link that leaves the page is the page's
     own (surfaces.css). */
  .lf-md-picture { max-width: 100%; height: auto; vertical-align: middle; }
  .lf-external-mark { display: inline-block; width: 0.75em; height: 0.75em;
    margin-inline-start: 0.24em; vertical-align: 0.03em; color: var(--accent);
    fill: none; stroke: currentColor; stroke-width: 1.5; stroke-linecap: round;
    stroke-linejoin: round; overflow: visible; user-select: none;
    -webkit-user-select: none; }
  /* A fence's line, while the caret is away from it, stands for the sent pre's padding,
     and code with no fence lines takes that padding at its ends instead. A field that
     edits in place reads its display's padding over this (\`readFaces\`). */
  .lf-face-fence-open, .lf-face-fence-close { line-height: var(--pre-pad-block); }
  .lf-md-code-bare.lf-md-code-first { padding-block-start: var(--pre-pad-block); }
  .lf-md-code-bare.lf-md-code-last { padding-block-end: calc(var(--pre-pad-block) + 8px); }
`);

// The field's editor (field-editor.js), once CodeMirror under it has loaded. It loads as
// soon as the page has presented, as an arrival the page answers for, so a field the
// user arrives in builds its editor in the turn that brings them, as it did when
// CodeMirror loaded with the page; a field that must draw before then asks for it
// sooner.
/** @typedef {Awaited<ReturnType<typeof loadFieldEditor>>} FieldEditor */
/** @type {FieldEditor | null} */
let editor = null;
const loadEditor = () => loadFieldEditor().then((loaded) => (editor = loaded));
afterPresentation(loadEditor);

// A field's words before it has an editor: the source, the selection, and the steps an
// owner recorded in its history (`record`), which the editor's history takes up as it
// builds.
// `base` is the words the history starts from, which a `value` write sets and the
// user's typing doesn't.
class Draft {
  steps = [];
  constructor(text) {
    this.text = this.base = text;
    this.anchor = this.head = text.length;
  }
}

// The words a node of the empty line's place holds: its text, with a line for each
// break.
const placeWords = (node) =>
  node.nodeType === Node.TEXT_NODE
    ? /** @type {Text} */ (node).data
    : node.nodeName === "BR"
      ? "\n"
      : [...node.childNodes].map(placeWords).join("");

/** @typedef {LeafText} LeafTextElement For its tag (`runtime-globals.d.ts`). */
class LeafText extends HTMLElement {
  // The field's one model. Until the field has first built an editor it is a Draft;
  // building the editor hands it to the view that edits it from then on (`#build`),
  // and an editor destroyed as the field leaves the page hands back its state, undo
  // history included.
  /** @type {Draft | ReturnType<FieldEditor["fieldState"]>} */
  #model = new Draft("");
  #view = null;
  // The empty line's place while the field has no editor, and the node focus lands on
  // there, whichever route brought it. While the editor loads, it holds the words, plain,
  // and takes what the user types (`#typeAtRest`).
  #rest = document.createElement("div");
  // The rendering hold of a field waiting for its editor to load (`#build`).
  #waiting = null;
  // Whether an input method is composing in the empty line's place. The words it
  // holds are unfinished until it ends, so they join the draft, and the editor builds,
  // only then.
  #composing = false;
  #nativeInput = false;
  #root;
  #internals = null;
  /** The element whose blocks a field editing words where they are shown shows them
   * as, such as a draft's prose; unset, the field draws a sent message's faces.
   * @type {Element | null} */
  facesOf = null;
  // The rules that draw the words in its blocks' faces (`readFaces`), as last read.
  #faces = new CSSStyleSheet();
  #facesRead = "";
  #readFaces() {
    if (!this.facesOf?.isConnected || !this.isConnected) return;
    const rules = readFaces(this, this.facesOf);
    if (rules === this.#facesRead) return;
    this.#facesRead = rules;
    this.#faces.replaceSync(rules);
  }
  #placeholderLayer = document.createElement("div");
  #placeholderText = document.createTextNode("");
  #frame = document.createElement("div");
  #readOnly = false;
  #sizes = sizeObserver(() => {
    // A new width can set the display's blocks in other faces, as a heading sized to
    // its container's width is.
    this.#readFaces();
    const view = this.#view;
    if (view?.hasFocus)
      view.requestMeasure({
        key: this,
        read: () => this.#rowTravel(view, view.state.selection.main.head),
        write: (travel) => moveScrollerBy(this, travel),
      });
  });

  // How far the host scrolls to show the row holding `pos` whole, its leading as well
  // as the caret, inside the host's padding (see the header). The words wrap, so the
  // host scrolls only down and up.
  #rowTravel(view, pos) {
    const { destination, rectangle: caret } = view.caretAt(pos);
    const node =
      destination instanceof Range ? destination.startContainer : destination;
    const row =
      (node instanceof Element ? node : node.parentElement)?.closest(".cm-line") ??
      this;
    const { scaleY } = view;
    const leading =
      Math.max(
        0,
        (parseFloat(getComputedStyle(row).lineHeight) * scaleY -
          (caret.bottom - caret.top)) /
          2,
      ) || 0;
    const style = getComputedStyle(this);
    const box = this.getBoundingClientRect();
    const top = box.top + (this.clientTop + parseFloat(style.paddingTop)) * scaleY;
    // client dimensions round fractional CSS sizes. Keep the bottom on the actual box,
    // inset by its native border and scrollbar.
    const bottom =
      box.bottom -
      (this.offsetHeight -
        this.clientTop -
        this.clientHeight +
        parseFloat(style.paddingBottom)) *
        scaleY;
    const travel =
      (Math.min(0, caret.top - leading - top) +
        Math.max(0, caret.bottom + leading - bottom)) /
      scaleY;
    // Native scroll offsets quantize a fractional correction. Round away from zero so
    // a row just beyond an edge actually enters.
    return travel < 0 ? Math.floor(travel) : Math.ceil(travel);
  }

  // Whether the host's words overflow it (`data-scrolls`), and which edges they run
  // past (`more-above`, `more-below`), read again as the host scrolls, so an owner can
  // show there is more without a scrollbar. The host stops at the page's height limit
  // while words grow inside it, so the reading watches the editor's content too, in the
  // editor's read/write phase. A scroll timeline would say it in CSS alone, but Firefox
  // lacks scroll timelines.
  #overflow = sizeObserver(() => this.#measureOverflow());

  #measureOverflow() {
    this.#view?.requestMeasure({
      key: this.#overflow,
      // Words, not the host's padding, run past an edge.
      read: (view) => {
        const style = getComputedStyle(this);
        return {
          scrolls: this.scrollHeight > this.clientHeight,
          above: this.scrollTop > Number.parseFloat(style.paddingTop) + 1,
          below:
            this.scrollTop + this.clientHeight <
            this.scrollHeight - Number.parseFloat(style.paddingBottom) - 1,
          corner: this.#cornerTaken(view, style),
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
          ["corner-taken", reading.corner],
        ]) {
          // Adding a state already set restyles all the same, on every scrolled frame.
          if (this.#internals.states.has(state) === on) continue;
          if (on) this.#internals.states.add(state);
          else this.#internals.states.delete(state);
        }
      },
    });
  }

  // Whether words in view, or the caret, reach the square `--lf-field-corner` wide at
  // the host's trailing foot, where a box stands its action over the words. The action
  // stands beside one row, the one across the square's middle, counted at its line
  // height. Rejected: every row whose line box touches the square, since the action
  // is taller than a row, so a row above that ran to the edge hid it beside a short
  // last row, and a new empty line brought it back.
  #cornerTaken(view, style) {
    const size = Number.parseFloat(style.getPropertyValue("--lf-field-corner"));
    if (!(size > 0)) return false;
    const { scaleX, scaleY } = view;
    const box = this.getBoundingClientRect();
    const rtl = style.direction === "rtl";
    const left = rtl ? box.left : box.right - size * scaleX;
    const right = rtl ? box.left + size * scaleX : box.right;
    const top = box.bottom - size * scaleY;
    const middle = box.bottom - (size * scaleY) / 2;
    const reaches = (rect, leading) =>
      rect.left < right &&
      rect.right > left &&
      rect.top - leading <= middle &&
      rect.bottom + leading > middle;
    for (const line of view.contentDOM.children) {
      const block = line.getBoundingClientRect();
      if (block.bottom <= top || block.top >= box.bottom) continue;
      const height = Number.parseFloat(getComputedStyle(line).lineHeight) * scaleY;
      const words = document.createRange();
      words.selectNodeContents(line);
      for (const rect of words.getClientRects())
        if (reaches(rect, Math.max(0, (height - rect.height) / 2) || 0)) return true;
    }
    if (!view.hasFocus) return false;
    const { rectangle: caret } = view.caretAt(view.state.selection.main.head);
    const { left: x, top: y, bottom: foot } = caret;
    return reaches({ left: x, right: x + 1, top: y, bottom: foot }, 0);
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
    for (const type of ["beforeinput", "input", "compositionstart", "compositionend"])
      this.#rest.addEventListener(type, (event) => this.#typeAtRest(event));
    this.#frame.append(this.#placeholderLayer, this.#rest);
    this.#root.append(this.#frame);
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

  // What the user types before the editor has loaded lands natively in the empty line's
  // place, and the draft takes it from there, words and caret, so the editor builds
  // holding it: read again after each input, as the page's own `input`, and after an
  // input method finishes. Return asks its owner first, as in the editor, whether it
  // may make a new line; Shift+Return, a line break, does unless the field holds one
  // line (`#oneLine`).
  #typeAtRest(event) {
    if (this.#view || !(this.#model instanceof Draft)) return;
    if (event.type === "compositionstart") {
      this.#composing = true;
      return;
    }
    if (event.type === "beforeinput") {
      if (
        this.#readOnly ||
        (event.inputType === "insertParagraph" && !this.#returned()) ||
        (event.inputType === "insertLineBreak" && this.#oneLine)
      )
        event.preventDefault();
      return;
    }
    if (event.type === "compositionend") this.#composing = false;
    else if (this.#composing || /** @type {InputEvent} */ (event).isComposing) return;
    this.#readRest();
    this.#paintEmpty();
    this.#emit("input");
    if (event.type === "compositionend" && editor) this.#build();
  }

  // Takes the words and caret of the empty line's place into the draft. The last
  // break only holds an empty last line open, and a one-line field takes a pasted
  // line break as a space, as its editor does.
  #readRest() {
    const words = placeWords(this.#rest);
    const kept = this.#rest.lastChild?.nodeName === "BR" ? words.slice(0, -1) : words;
    const text = this.#oneLine ? kept.replaceAll("\n", " ") : kept;
    const selection = this.#selection();
    const [range] = selection.getComposedRanges({ shadowRoots: [this.#root] });
    const at = (node, offset) => {
      if (!this.#rest.contains(node)) return text.length;
      const before = document.createRange();
      before.setStart(this.#rest, 0);
      before.setEnd(node, offset);
      return Math.min(placeWords(before.cloneContents()).length, text.length);
    };
    const from = range ? at(range.startContainer, range.startOffset) : text.length;
    const to = range ? at(range.endContainer, range.endOffset) : text.length;
    const backward = selection.direction === "backward";
    Object.assign(this.#model, {
      text,
      anchor: backward ? to : from,
      head: backward ? from : to,
    });
    if (text !== kept) this.#paintRest();
  }

  // Firefox and WebKit lack ShadowRoot.getSelection; the document holds theirs.
  #selection() {
    return this.#root.getSelection?.() ?? document.getSelection();
  }

  // The words a field without an editor shows, plain, in the empty line's place, and,
  // while the user is in it, the draft's caret there.
  #paintRest() {
    if (this.#composing) return;
    const text = this.#view ? "" : this.#text;
    const here = !this.#view && this.#root.activeElement === this.#rest;
    const last = this.#rest.lastChild?.nodeName === "BR";
    const shown = placeWords(this.#rest).slice(0, last ? -1 : undefined) === text;
    // Placing the caret needs the words as one text node, a break after them where
    // the last line is empty, as this writes them.
    const plain = (node) => node?.nodeType === Node.TEXT_NODE;
    const one =
      this.#rest.childNodes.length === (text ? 1 : 0) + Number(last) &&
      (!text || plain(this.#rest.firstChild));
    if (shown && (!here || one)) return this.#placeRestCaret(here);
    this.#rest.replaceChildren(
      ...(text ? [text] : []),
      ...(!text || text.endsWith("\n") ? [document.createElement("br")] : []),
    );
    this.#placeRestCaret(here);
  }

  #placeRestCaret(here) {
    if (!here) return;
    const { anchor, head } = this.#range;
    const words = this.#rest.firstChild;
    if (words.nodeType === Node.TEXT_NODE)
      this.#selection().setBaseAndExtent(words, anchor, words, head);
    else this.#selection().setBaseAndExtent(this.#rest, 0, this.#rest, 0);
  }

  #returned() {
    return this.dispatchEvent(new Event("lf-edit-return", { cancelable: true }));
  }

  // The hooks the editor's state calls (`fieldState`).
  #hooks() {
    return {
      readOnly: this.#readOnly,
      attributes: this.#contentAttributes(),
      returned: () => this.#returned(),
      oneLine: () => this.#oneLine,
      // The caret counts toward the corner only while it shows.
      focused: () => this.#measureOverflow(),
      revealed: (view, pos) => moveScrollerBy(this, this.#rowTravel(view, pos)),
      typed: (native, insert) => {
        this.#nativeInput = native;
        try {
          insert();
        } finally {
          this.#nativeInput = false;
        }
      },
    };
  }

  // The field's model as it stands: the editor's state, the state a destroyed editor
  // left, or the draft.
  get #state() {
    return this.#view?.state ?? this.#model;
  }
  get #text() {
    const state = this.#state;
    return state instanceof Draft ? state.text : state.doc.toString();
  }
  get #length() {
    const state = this.#state;
    return state instanceof Draft ? state.text.length : state.doc.length;
  }
  // The selection's `anchor` and `head`.
  get #range() {
    const state = this.#state;
    return state instanceof Draft ? state : state.selection.main;
  }

  /** Applies a change to the editor, to the state a destroyed editor left, or, before
   * the field has an editor, to its draft (`draft`). `spec` reads the editor module.
   * @param {(module: FieldEditor) => object} spec
   * @param {(draft: Draft) => unknown} [draft] */
  #change(spec, draft = () => {}) {
    if (this.#view) this.#view.dispatch(spec(editor));
    else if (this.#model instanceof Draft) draft(this.#model);
    else this.#model = this.#model.update(spec(editor)).state;
  }

  attributeChangedCallback(name) {
    if (name === "placeholder") this.#placeholderText.data = this.placeholder;
    if (name === "aria-describedby") return this.#describe();
    this.#dressRest();
    this.#change((module) => module.contentAttributes(this.#contentAttributes()));
  }

  // A move by `moveBefore` keeps the editor and its focus but collapses the native
  // selection in it, which CodeMirror would read back as a caret at the start. With this
  // callback the move is no disconnection, and the view puts its caret back as it lands.
  connectedMoveCallback() {
    this.#view?.placeSelection();
  }

  connectedCallback() {
    this.classList.toggle("scroll", true);
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
    this.#root.adoptedStyleSheets = [sheet, this.#faces];
    if (this.#length) this.#build();
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
  //
  // Before the editor module has loaded, the field holds a rendering hold and builds
  // the moment it arrives, showing its words plain in the empty line's place until then,
  // with the user's focus there, so what they type meanwhile is the editor's first words
  // (`#typeAtRest`).
  #build() {
    if (this.#view) return;
    if (!editor) {
      this.#paintRest();
      if (this.#waiting) return;
      this.#waiting = holdRendering();
      // The hold covers the load. An input method still composing as it lands holds
      // the build until it ends, which waits on the user rather than on the page.
      void loadEditor()
        .then(() => this.isConnected && this.#build())
        .finally(() => {
          this.#waiting();
          this.#waiting = null;
        });
      return;
    }
    // An input method composing in the empty line's place builds the editor as it
    // ends (`#typeAtRest`).
    if (this.#composing) return;
    if (this.#model instanceof Draft && this.#root.activeElement === this.#rest)
      this.#readRest();
    // A field that stands where its words are shown takes their faces from there, read
    // as the editor builds: the field is in place, and nothing has drawn its words yet.
    this.#readFaces();
    const module = editor;
    this.#view = new module.LeafEditorView({
      root: this.#root,
      parent: this.#frame,
      state:
        this.#model instanceof Draft
          ? module.fieldState(this.#model, this.#hooks())
          : this.#model,
      // Dispatched word changes are the user's. The value setter updates the view
      // directly and silently; an owner's `record` changes no words.
      dispatchTransactions: (transactions, view) => {
        const edited = transactions.some((tr) => tr.docChanged);
        if (edited && !this.#nativeInput) this.#beforeEdit();
        view.update(transactions);
        module.runOwnerSteps(transactions);
        this.#paintEmpty();
        this.#measureOverflow();
        if (edited) this.#emit("input");
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
    this.#paintRest();
    this.#measureOverflow();
  }

  #emit(type) {
    this.dispatchEvent(new Event(type, { bubbles: true, composed: true }));
  }

  #beforeEdit() {
    this.#emit("lf-before-edit");
  }

  // A move between parents reconnects within the task and keeps its editor.
  disconnectedCallback() {
    queueMicrotask(() => {
      if (this.isConnected) return;
      this.#internals.states.delete("ready");
      this.#internals.states.delete("corner-taken");
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
  // field reveals itself separately when its caller requests ordinary focus. While
  // the editor loads, the user stands in the empty line's place.
  focus(options) {
    if (!this.isConnected) return;
    this.#build();
    if (this.#view) this.#view.focus();
    else this.#rest.focus({ preventScroll: true });
    if (this.#root.activeElement !== (this.#view?.contentDOM ?? this.#rest)) return;
    if (!options?.preventScroll) scrollIntoView(this, { block: "nearest" });
  }

  blur() {
    (this.#view?.contentDOM ?? this.#rest).blur();
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

  get #oneLine() {
    return this.getAttribute("aria-multiline") === "false";
  }

  #contentAttributes() {
    const attributes = {
      spellcheck: "true",
      autocorrect: "on",
      autocapitalize: "sentences",
      "aria-multiline": String(!this.#oneLine),
    };
    if (this.placeholder) attributes["aria-placeholder"] = this.placeholder;
    const label = this.getAttribute("aria-label");
    if (label !== null) attributes["aria-label"] = label;
    return attributes;
  }

  #paintEmpty() {
    if (this.#length) this.#internals.states.delete("placeholder-shown");
    else this.#internals.states.add("placeholder-shown");
  }

  get value() {
    return this.#text;
  }

  edit(text) {
    text = String(text).replace(/\r\n?/g, "\n");
    if (text === this.value) return;
    if (!this.#view && this.isConnected) this.#build();
    this.#change(
      () => ({
        changes: { from: 0, to: this.#length, insert: text },
        selection: { anchor: text.length },
        userEvent: "input.dictation",
      }),
      (draft) => {
        if (this.isConnected) this.#beforeEdit();
        draft.text = text;
        draft.anchor = draft.head = text.length;
        if (!this.isConnected) return;
        this.#paintRest();
        this.#paintEmpty();
        this.#emit("input");
      },
    );
  }

  // Records a change the owner has just made outside the words as a step of the words'
  // history, standing alone: taking the step back calls `undo`, redoing it calls `redo`.
  record(undo, redo) {
    this.#change(
      (module) => module.record(undo, redo),
      (draft) => draft.steps.push([undo, redo]),
    );
  }

  // Forgets the history and keeps the words, the caret and the editor's DOM, for a box
  // that takes up a draft as it stands.
  restartHistory() {
    this.#change(
      (module) => module.forgetHistory,
      (draft) => Object.assign(draft, { steps: [], base: draft.text }),
    );
    this.#change((module) => module.startHistory());
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
      this.#model = new Draft(text);
      if (!this.isConnected) return;
      this.#paintRest();
      this.#paintEmpty();
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
      ...editor.forgetHistory,
    });
    const fresh = reset.state.update(editor.startHistory());
    this.#view.update([reset, fresh]);
    if (composing) content.editContext = composing;
    this.#paintEmpty();
    this.#measureOverflow();
  }

  get selectionStart() {
    const { anchor, head } = this.#range;
    return Math.min(anchor, head);
  }
  get selectionEnd() {
    const { anchor, head } = this.#range;
    return Math.max(anchor, head);
  }
  get selectionDirection() {
    const { anchor, head } = this.#range;
    return anchor === head ? "none" : head < anchor ? "backward" : "forward";
  }
  // A textarea's clamping: each end within the words, and a start past the end moved to
  // the end.
  setSelectionRange(start, end, direction = "none") {
    const length = this.#length;
    const to = Math.min(Math.max(Number(end) || 0, 0), length);
    const from = Math.min(Math.max(Number(start) || 0, 0), to);
    const [anchor, head] = direction === "backward" ? [to, from] : [from, to];
    // A draft's caret also stands in its place, where typing lands until the editor
    // builds and which the editor builds from (`#readRest`).
    this.#change(
      () => ({ selection: { anchor, head } }),
      (draft) => {
        Object.assign(draft, { anchor, head });
        this.#paintRest();
      },
    );
  }
  select() {
    this.setSelectionRange(0, this.#length);
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
    this.#change((module) => module.readOnly(this.#readOnly));
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
