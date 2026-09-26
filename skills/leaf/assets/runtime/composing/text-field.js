/* The runtime's text field: a Markdown editor that presents itself as a textarea.
 *
 * Every composer the runtime builds is a `leaf-text`. Inside a closed shadow root it
 * runs CodeMirror over the draft's exact source, and draws that source the way a sent
 * message will read: inline code in code type, emphasis and strong in their weights,
 * a link as a link, a heading in bold. The syntax that produces each (backticks,
 * asterisks, brackets, hashes) is hidden unless the selection touches the construct, so
 * the user sees their words rendered and can still reach every character they typed.
 * Nothing is converted: the value is always the source the user typed, which is what
 * the agent reads and what `marked` renders once the message is sent.
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
 * `readOnly`, `name` — and fires `input` for a user edit only, as a textarea does; a
 * write to `value` fires nothing and puts the caret at the end.
 *
 * The host is also the control accessibility tooling addresses, since nothing outside a
 * closed root sees into it: it takes `role="textbox"` and `aria-multiline` unless the
 * page gave it its own, and it carries the name, description and busy state the page
 * writes on it. The content node inside is where focus and assistive technology land,
 * so it wears the same `aria-label` and the placeholder as `aria-placeholder`.
 *
 * Enter, Mod+Enter and Escape are not bound here. Leaf's key dispatcher owns them on the
 * document, and cancels the press it acts on; Shift+Enter inserts a line and continues
 * a list or quote.
 */
import {
  Annotation,
  EditorView,
  EditorState,
  Compartment,
  Decoration,
  ViewPlugin,
  keymap,
  history,
  standardKeymap,
  historyKeymap,
  syntaxTree,
  markdown,
  markdownLanguage,
  insertNewlineContinueMarkup,
} from "../../vendor/codemirror.esm.js";
import { TEXT_FIELD } from "../focus.js";

// Marks a transaction the value setter made, which is not the user's edit.
const programmatic = Annotation.define();

const sheet = new CSSStyleSheet();
sheet.replaceSync(`
  :host { display: block; cursor: text; }
  /* The placeholder is a layer under the words, as a textarea's is, never content in
     the line: a widget in an empty line is what the platform would draw the caret
     against. Both layers share one grid cell, inside the host's padding. */
  .lf-field { display: grid; }
  .lf-field > * { grid-area: 1 / 1; min-width: 0; }
  .lf-field-placeholder { pointer-events: none; white-space: pre-wrap;
    overflow-wrap: anywhere; color: var(--lf-placeholder-color, var(--muted)); }
  :host(:not(:state(placeholder-shown))) .lf-field-placeholder { visibility: hidden; }
  .lf-md-mark { color: var(--muted); }
  .lf-md-code { font-family: var(--mono); font-size: 0.9em;
    background: var(--code-bg); border-radius: 3px; padding: 0.1em 0.25em; }
  .lf-md-code-block { font-family: var(--mono); font-size: 0.9em;
    background: var(--code-bg); }
  .lf-md-em { font-style: italic; }
  .lf-md-strong, .lf-md-heading { font-weight: 650; }
  .lf-md-strike { text-decoration: line-through; }
  .lf-md-link { color: var(--accent); text-decoration: underline;
    text-underline-offset: 2px; }
  .lf-md-quote { border-inline-start: 3px solid var(--border-2);
    padding-inline-start: 8px !important; color: var(--muted); }
`);

// The editor wears the box's type and colour: the host is the textarea-shaped control
// the page styles, and CodeMirror only lays the words out inside it. Its own theme
// mechanism outranks its base theme, which would otherwise set monospace.
const fieldTheme = EditorView.theme({
  "&": { font: "inherit", color: "inherit", backgroundColor: "transparent" },
  "&.cm-focused": { outline: "none" },
  ".cm-scroller": { fontFamily: "inherit", lineHeight: "inherit", overflow: "visible" },
  ".cm-content": { padding: "0", caretColor: "currentColor", minHeight: "1lh" },
  ".cm-line": { padding: "0" },
});

// The inline constructs whose syntax hides away from the selection, and the class
// their content wears. A mark child is hidden; everything else in the node is styled.
const INLINE = {
  InlineCode: { cls: "lf-md-code", marks: ["CodeMark"] },
  Emphasis: { cls: "lf-md-em", marks: ["EmphasisMark"] },
  StrongEmphasis: { cls: "lf-md-strong", marks: ["EmphasisMark"] },
  Strikethrough: { cls: "lf-md-strike", marks: ["StrikethroughMark"] },
};
const hide = Decoration.replace({});
const dim = Decoration.mark({ class: "lf-md-mark" });
const marked = (cls) => Decoration.mark({ class: cls });
const line = (cls) => Decoration.line({ class: cls });

// Whether the selection touches [from, to], ends included: the caret standing just
// after a closing backtick still reveals it, so the user can delete what they see.
const touches = (state, from, to) =>
  state.selection.ranges.some((range) => range.from <= to && range.to >= from);

function decorate(view) {
  const { state } = view;
  const out = [];
  const add = (from, to, deco) => from < to && out.push(deco.range(from, to));
  for (const { from, to } of view.visibleRanges) {
    syntaxTree(state).iterate({
      from,
      to,
      enter: (node) => {
        const name = node.name;
        const active = touches(state, node.from, node.to);
        const inline = INLINE[name];
        if (inline) {
          add(node.from, node.to, marked(inline.cls));
          for (const mark of node.node.getChildren(inline.marks[0]))
            add(mark.from, mark.to, active ? dim : hide);
          return;
        }
        if (name === "Link") {
          // `[words](url)`: the words are the link; the brackets and destination are
          // syntax, shown only while the selection is in the link.
          const marks = node.node.getChildren("LinkMark");
          if (marks.length < 2) return;
          add(marks[0].to, marks[1].from, marked("lf-md-link"));
          if (active) {
            add(marks[0].from, marks[0].to, dim);
            add(marks[1].from, node.to, dim);
          } else {
            add(marks[0].from, marks[0].to, hide);
            add(marks[1].from, node.to, hide);
          }
          return false;
        }
        if (/^ATXHeading\d$/.test(name)) {
          out.push(line("lf-md-heading").range(state.doc.lineAt(node.from).from));
          const mark = node.node.getChild("HeaderMark");
          // The hash and the space after it.
          if (mark) add(mark.from, Math.min(mark.to + 1, node.to), active ? dim : hide);
          return;
        }
        if (name === "FencedCode") {
          for (let at = node.from; at <= node.to;) {
            const each = state.doc.lineAt(at);
            out.push(line("lf-md-code-block").range(each.from));
            at = each.to + 1;
          }
          for (const mark of node.node.getChildren("CodeMark"))
            add(mark.from, mark.to, dim);
          const info = node.node.getChild("CodeInfo");
          if (info) add(info.from, info.to, dim);
          return false;
        }
        if (name === "Blockquote") {
          for (let at = node.from; at <= node.to;) {
            const each = state.doc.lineAt(at);
            out.push(line("lf-md-quote").range(each.from));
            at = each.to + 1;
          }
          return;
        }
        if (name === "QuoteMark" || name === "ListMark") add(node.from, node.to, dim);
      },
    });
  }
  return Decoration.set(out, true);
}

const livePreview = ViewPlugin.fromClass(
  class {
    constructor(view) {
      this.decorations = decorate(view);
    }
    update(update) {
      if (
        update.docChanged ||
        update.selectionSet ||
        update.viewportChanged ||
        syntaxTree(update.state) !== syntaxTree(update.startState)
      )
        this.decorations = decorate(update.view);
    }
  },
  { decorations: (plugin) => plugin.decorations },
);

class LeafText extends HTMLElement {
  // The field's one model. Until the element first connects it is a bare EditorState,
  // which holds the value, selection and configuration without a DOM; connecting hands
  // it to the view that edits it from then on. A composer built and never shown pays
  // for no editor.
  #model;
  #view = null;
  #root;
  #internals = null;
  #editable = new Compartment();
  #attributes = new Compartment();
  #placeholderLayer = document.createElement("div");
  #frame = document.createElement("div");
  #readOnly = false;

  static observedAttributes = ["aria-label", "placeholder"];

  constructor() {
    super();
    this.#root = this.attachShadow({ mode: "closed", delegatesFocus: true });
    this.#frame.className = "lf-field";
    this.#placeholderLayer.className = "lf-field-placeholder";
    this.#placeholderLayer.setAttribute("aria-hidden", "true");
    this.#frame.append(this.#placeholderLayer);
    this.#root.append(this.#frame);
    this.#model = EditorState.create({
      extensions: [
        history(),
        keymap.of([
          { key: "Shift-Enter", run: insertNewlineContinueMarkup },
          {
            key: "Shift-Enter",
            run: (view) => (view.dispatch(view.state.replaceSelection("\n")), true),
          },
          ...standardKeymap.filter(
            ({ key }) => key !== "Escape" && key !== "Enter" && key !== "Mod-Enter",
          ),
          ...historyKeymap,
        ]),
        markdown({ base: markdownLanguage }),
        livePreview,
        fieldTheme,
        EditorView.lineWrapping,
        this.#editable.of(EditorState.readOnly.of(false)),
        this.#attributes.of(EditorView.contentAttributes.of(this.#contentAttributes())),
      ],
    });
  }

  attributeChangedCallback(name) {
    if (name === "placeholder") this.#placeholderLayer.textContent = this.placeholder;
    this.#apply({
      effects: this.#attributes.reconfigure(
        EditorView.contentAttributes.of(this.#contentAttributes()),
      ),
    });
  }

  connectedCallback() {
    if (this.#view) return;
    if (!this.hasAttribute("role")) this.setAttribute("role", "textbox");
    if (!this.hasAttribute("aria-multiline"))
      this.setAttribute("aria-multiline", "true");
    this.#internals = this.attachInternals();
    this.#root.adoptedStyleSheets = [sheet];
    this.#view = new EditorView({
      root: this.#root,
      parent: this.#frame,
      state: this.#model,
      dispatchTransactions: (transactions, view) => {
        view.update(transactions);
        this.#paintEmpty();
        // A user edit is an input; a write through `value` is not, as with a textarea.
        if (
          transactions.some(
            (tr) => tr.docChanged && tr.annotation(programmatic) !== true,
          )
        )
          this.dispatchEvent(new Event("input", { bubbles: true }));
      },
    });
    this.#model = null;
    // The scroller is focusable only so a press on it keeps focus in the editor, and
    // the field's scroller never scrolls; left focusable it is the node the root
    // delegates focus to, which holds no caret.
    this.#view.scrollDOM.removeAttribute("tabindex");
    this.addEventListener("mousedown", (event) => this.#pressPadding(event));
    // The content node's own input events would reach the host too, retargeted, and
    // announce every edit twice. The host's is the one the page hears.
    for (const type of ["input", "beforeinput"])
      this.#root.addEventListener(type, (event) => event.stopPropagation());
    this.#paintEmpty();
  }

  // A focus through the element puts the caret back where it stood, as a textarea's
  // does. The platform, delegating, lands it at the start of the words; CodeMirror's own
  // focus leaves the page's selection wherever the user last pressed when its record of
  // the DOM selection predates that press, and then reads the platform's caret back as
  // the user's. So the element writes the page's selection from the field's own.
  focus(options) {
    if (!this.#view) return super.focus(options);
    const view = this.#view;
    view.focus();
    const { anchor, head } = view.state.selection.main;
    const from = view.domAtPos(anchor);
    const to = view.domAtPos(head);
    // A shadow root answers for its own selection only in Chromium, as CodeMirror reads it.
    const selection = this.#root.getSelection?.() ?? document.getSelection();
    selection.setBaseAndExtent(from.node, from.offset, to.node, to.offset);
    if (!options?.preventScroll) this.scrollIntoView({ block: "nearest" });
  }

  blur() {
    this.#view?.contentDOM.blur();
  }

  // A press on the box outside the editor's own area — its padding — lands in the words
  // at the nearest character, the way a textarea's does. Presses inside the editor are
  // CodeMirror's to place.
  #pressPadding(event) {
    if (event.button !== 0 || !this.#view) return;
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

  get value() {
    return this.#state.doc.toString();
  }
  set value(text) {
    text = String(text ?? "").replace(/\r\n?/g, "\n");
    if (text === this.value) return;
    this.#apply({
      changes: { from: 0, to: this.#state.doc.length, insert: text },
      selection: { anchor: text.length },
      annotations: programmatic.of(true),
    });
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
  setSelectionRange(start, end, direction = "none") {
    const length = this.#state.doc.length;
    const from = Math.min(start, length);
    const to = Math.min(Math.max(end, from), length);
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
