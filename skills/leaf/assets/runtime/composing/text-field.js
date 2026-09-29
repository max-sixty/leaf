/* The runtime's text field: a Markdown editor that presents itself as a textarea.
 *
 * Every composer the runtime builds is a `leaf-text`. Inside a closed shadow root it
 * runs CodeMirror over the draft's exact source, and draws that source the way a sent
 * message will read: inline code in code type, emphasis and strong in their weights,
 * a link as a link, a heading in bold. The syntax that produces each (backticks,
 * asterisks, brackets, hashes) is hidden unless the selection touches the construct, so
 * the user sees their words rendered and can still reach every character they typed.
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
 * `readOnly`, `name` — and fires `input` for a user edit only, as a textarea does. A
 * write to `value` fires nothing, puts the caret at the end, and starts a new undo
 * history, so undo never walks back into a draft the runtime swapped out. A pasted
 * picture is the box owner's: the field leaves that paste to the host's listeners.
 *
 * The placeholder is a layer under the words, shown while the field is empty. It reads
 * the `placeholder` attribute, and a child in slot `placeholder` stands in its place when
 * a box wants more than one run of text there, such as a label and the key that sends.
 *
 * The editor lives while the element is in a document. A field removed and not put
 * back in the same task keeps its state and destroys its view, which releases the
 * listeners CodeMirror holds on the window and document; reconnecting builds another.
 *
 * The host is also the control accessibility tooling addresses, since nothing outside a
 * closed root sees into it: it takes `role="textbox"`, `aria-multiline` and a tab stop
 * unless the page gave it its own, and it carries the name, description and busy state
 * the page writes on it. The content node inside is where focus and assistive
 * technology land, so it wears the same `aria-label`, the placeholder as
 * `aria-placeholder`, and the host's description through `ariaDescribedByElements`,
 * the one reference that reaches from inside a shadow root to the page around it.
 *
 * Enter, Mod+Enter and Escape are not bound here. Leaf's key dispatcher owns them on the
 * document, and cancels the press it acts on; Shift+Enter inserts a line and continues
 * a list or quote.
 */
import {
  EditorView,
  EditorState,
  Compartment,
  Decoration,
  LanguageSupport,
  ViewPlugin,
  keymap,
  history,
  standardKeymap,
  historyKeymap,
  markdownLanguage,
  insertNewlineContinueMarkup,
} from "../../vendor/codemirror.esm.js";
import { TEXT_FIELD } from "../focus.js";
import { loadMarkdown, markdownReady, markdownTokens } from "../markdown.js";

const sheet = new CSSStyleSheet();
sheet.replaceSync(`
  :host { display: block; cursor: text; }
  /* The placeholder is a layer under the words, as a textarea's is, never content in
     the line: a widget in an empty line is what the platform would draw the caret
     against. Both layers share one grid cell, inside the host's padding. */
  .lf-field { display: grid; }
  .lf-field > * { grid-area: 1 / 1; min-width: 0; }
  /* The placeholder is one line that never widens the box — a response bar sizes to the
     words — and shortens with an ellipsis where the box is narrow, so it reads the same
     height whether it shows the plain words or a keyed hint. */
  .lf-field-placeholder { pointer-events: none; white-space: nowrap;
    contain: inline-size; overflow-x: clip; text-overflow: ellipsis;
    color: var(--muted); }
  :host(:not(:state(placeholder-shown))) .lf-field-placeholder { visibility: hidden; }
  /* A draft wears the sent message's faces. Strong, emphasis and strikethrough are the
     elements themselves, which the platform dresses here as it does in the message;
     the rest read the theme's tokens, since its element rules stop at this root. A
     heading is bold, as the platform draws one, at the size of the words around it. A
     block is drawn line by line, so a code block's frame is each line's sides, closed
     above its first line and below its last. */
  .lf-md-mark { color: var(--muted); }
  code { font-family: var(--mono); font-size: var(--code-inline-size);
    background: var(--code-bg); border-radius: var(--code-inline-r);
    padding: var(--code-inline-pad); box-decoration-break: slice; }
  .lf-md-heading { font-weight: bold; }
  .lf-md-link { color: var(--accent); text-decoration: underline var(--link-underline);
    text-underline-offset: var(--link-underline-offset); }
  .lf-md-quote { border-inline-start: var(--quote-rule); font-style: var(--quote-style);
    padding-inline-start: var(--quote-inset) !important; color: var(--muted); }
  .lf-md-code-block { font-family: var(--mono); font-size: var(--code-size);
    line-height: var(--code-line); color: var(--code-ink); background: var(--pre-bg);
    font-variant-ligatures: none; border-inline: 1px solid var(--code-border);
    padding-inline: var(--pre-inset) !important; }
  .lf-md-code-first { border-block-start: 1px solid var(--code-border);
    border-start-start-radius: var(--r); border-start-end-radius: var(--r); }
  .lf-md-code-last { border-block-end: 1px solid var(--code-border);
    border-end-start-radius: var(--r); border-end-end-radius: var(--r); }
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

const hide = Decoration.replace({});
const dim = Decoration.mark({ class: "lf-md-mark" });
const link = Decoration.mark({ class: "lf-md-link" });
const line = (cls) => Decoration.line({ class: cls });

// The inline constructs the preview draws, by the renderer's token type: each as the
// element the renderer sends it as.
const INLINE = {
  codespan: Decoration.mark({ tagName: "code" }),
  em: Decoration.mark({ tagName: "em" }),
  strong: Decoration.mark({ tagName: "strong" }),
  del: Decoration.mark({ tagName: "del" }),
};

// Whether the selection touches [from, to], ends included: the caret standing just
// after a closing backtick still reveals it, so the user can delete what they see.
const touches = (state, from, to) =>
  state.selection.ranges.some((range) => range.from <= to && range.to >= from);

// A token's children in source order: its inline or block content, a list's items, and
// a table's cells, header first.
const children = (token) => [
  ...(token.tokens ?? []),
  ...(token.items ?? []),
  ...(token.header ?? []).flatMap((cell) => cell.tokens),
  ...(token.rows ?? []).flat().flatMap((cell) => cell.tokens),
];

// Where a token's `raw` stands in the draft, as [from, to]: the earliest run at or
// after `at` that ends by `limit`. A token read at the top level is its exact source.
// One a container handed on was rewritten first, in exactly two ways the match walks
// through: a quote or a list drops each continuation line's markers and indent, and a
// table cell drops the backslash of an escaped pipe. Null where no such run stands.
function locate(source, raw, at, limit) {
  for (let start = source.indexOf(raw[0], at); start >= 0 && start < limit;) {
    let s = start;
    let r = 0;
    while (r < raw.length && s < limit) {
      if (source[s] === raw[r]) {
        s++;
        r++;
      } else if (raw[r] === "|" && source[s] === "\\" && source[s + 1] === "|") s++;
      else if (raw[r - 1] === "\n" && /[ \t>]/.test(source[s])) s++;
      else break;
    }
    if (r === raw.length) return [start, s];
    start = source.indexOf(raw[0], start + 1);
  }
  return null;
}

// Where each token the renderer read stands in the draft, each found at or after the
// one before it and inside the span of the token that holds it.
function place(source, tokens, from, limit, found) {
  let at = from;
  for (const token of tokens) {
    const span = token.raw ? locate(source, token.raw, at, limit) : null;
    if (span) found.push({ token, from: span[0], to: span[1] });
    place(source, children(token), span ? span[0] : at, span ? span[1] : limit, found);
    if (span) at = span[1];
  }
  return found;
}

// Where a link's label closes: the `]` matching its opening `[`, backslash escapes
// skipped, as CommonMark reads a label.
function labelEnd(raw) {
  for (let at = 1, depth = 0; at < raw.length; at++) {
    if (raw[at] === "\\") at++;
    else if (raw[at] === "[") depth++;
    else if (raw[at] === "]" && depth-- === 0) return at;
  }
  return -1;
}

// How much of an inline construct's source `text` opens and closes it, read from the
// source itself: the renderer's child tokens hold unescaped text, which the source need
// not contain. Null for a construct the preview does not style.
function syntaxLengths(token, raw) {
  if (token.type === "codespan") {
    const run = raw.match(/^`+/)[0].length;
    return [run, run];
  }
  if (token.type === "em") return [1, 1];
  if (token.type === "strong") return [2, 2];
  if (token.type === "del") return raw.startsWith("~~") ? [2, 2] : [1, 1];
  if (token.type !== "link") return null;
  if (raw.startsWith("<")) return [1, 1];
  if (!raw.startsWith("[")) return [0, 0];
  const end = labelEnd(raw);
  return end < 0 ? null : [1, raw.length - end];
}

// The draft as the renderer reads it, placed. Empty until the renderer has loaded.
const read = (state) => {
  const source = state.doc.toString();
  const tokens = markdownTokens(source);
  return tokens ? place(source, tokens, 0, source.length, []) : [];
};

function decorate(state, placed) {
  const out = [];
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
  for (const { token, from, to } of placed) {
    const syntax = touches(state, from, to) ? dim : hide;
    // The construct as it stands in the draft, which a container may have rewritten
    // before the renderer read it.
    const text = state.doc.sliceString(from, to);
    const lengths = syntaxLengths(token, text);
    if (lengths) {
      // The construct's words, between its opening and closing syntax.
      const words = [from + lengths[0], to - lengths[1]];
      if (words[0] > words[1]) continue;
      // `[words](url)`, `[words][id]`, `<url>` and a bare address are drawn as links
      // where the renderer kept them (`linked`); one it refused sends its words alone,
      // so its syntax steps aside all the same.
      if (token.type !== "link") add(from, to, INLINE[token.type]);
      else if (token.linked) add(words[0], words[1], link);
      add(from, words[0], syntax);
      add(words[1], to, syntax);
    } else if (token.type === "escape") {
      // A backslash escape (`\*`) sends the character alone.
      add(from, from + 1, syntax);
    } else if (token.type === "heading") {
      const end = from + text.trimEnd().length;
      const atx = text.match(/^ {0,3}#{1,6}(?:[ \t]+|$)/);
      lines(from, end, (each) => {
        const underline = !atx && each.to >= end;
        if (underline) add(each.from, each.to, dim);
        else out.push(line("lf-md-heading").range(each.from));
      });
      if (atx) add(from, from + atx[0].length, syntax);
    } else if (token.type === "code") {
      const end = from + text.trimEnd().length;
      const fenced = /^ {0,3}(`{3,}|~{3,})/.test(text);
      lines(from, end, (each) => {
        const ends = [
          each.from <= from ? " lf-md-code-first" : "",
          each.to >= end ? " lf-md-code-last" : "",
        ].join("");
        out.push(line(`lf-md-code-block${ends}`).range(each.from));
        if (
          fenced &&
          (each.from === from || /^ {0,3}(`{3,}|~{3,})\s*$/.test(each.text))
        )
          add(each.from, each.to, dim);
      });
    } else if (token.type === "blockquote") {
      lines(from, from + text.trimEnd().length, (each) => {
        out.push(line("lf-md-quote").range(each.from));
        const mark = each.text.match(/^ {0,3}> ?/);
        if (mark) add(each.from, each.from + mark[0].length, dim);
      });
    } else if (token.type === "list_item") {
      const mark = text.match(/^ {0,3}(?:[*+-]|\d{1,9}[.)])/);
      if (mark) add(from, from + mark[0].length, dim);
    }
  }
  return Decoration.set(out, true);
}

// A paste carrying a picture is left to the box's owner, which uploads it and keeps the
// words as they were (`wireInput`); the editor would otherwise insert the clipboard's
// text, or delete the selection for a clipboard with none, before the owner hears it.
const pastesPicture = EditorView.domEventHandlers({
  paste: (event) =>
    [...(event.clipboardData?.items ?? [])].some(
      (item) => item.kind === "file" && item.type.startsWith("image/"),
    ),
});

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
  #placeholderText = document.createTextNode("");
  #frame = document.createElement("div");
  #readOnly = false;

  static observedAttributes = ["aria-label", "aria-describedby", "placeholder"];

  constructor() {
    super();
    this.#root = this.attachShadow({ mode: "closed", delegatesFocus: true });
    this.#frame.className = "lf-field";
    this.#placeholderLayer.className = "lf-field-placeholder";
    this.#placeholderLayer.setAttribute("aria-hidden", "true");
    const hint = document.createElement("slot");
    hint.name = "placeholder";
    hint.append(this.#placeholderText);
    this.#placeholderLayer.append(hint);
    this.#frame.append(this.#placeholderLayer);
    this.#root.append(this.#frame);
    this.#model = this.#create("");
    this.addEventListener("mousedown", (event) => this.#pressPadding(event));
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
        new LanguageSupport(markdownLanguage),
        livePreview,
        pastesPicture,
        fieldTheme,
        EditorView.lineWrapping,
        this.#editable.of(EditorState.readOnly.of(this.#readOnly)),
        this.#attributes.of(EditorView.contentAttributes.of(this.#contentAttributes())),
      ],
    });
  }

  attributeChangedCallback(name) {
    if (name === "placeholder") this.#placeholderText.data = this.placeholder;
    if (name === "aria-describedby") return this.#describe();
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
    // A tab stop, as a textarea is: delegation already stops Tab in the words, and a
    // host reading -1 is one every stop-counting walk would miss.
    if (!this.hasAttribute("tabindex")) this.tabIndex = 0;
    this.#internals ??= this.attachInternals();
    this.#root.adoptedStyleSheets = [sheet];
    this.#view = new EditorView({
      root: this.#root,
      parent: this.#frame,
      state: this.#model,
      // Every transaction is the user's: the value setter replaces the state instead.
      dispatchTransactions: (transactions, view) => {
        view.update(transactions);
        this.#paintEmpty();
        if (transactions.some((tr) => tr.docChanged))
          this.dispatchEvent(new Event("input", { bubbles: true }));
      },
    });
    this.#model = null;
    // The scroller is focusable only so a press on it keeps focus in the editor, and
    // the field's scroller never scrolls; left focusable it is the node the root
    // delegates focus to, which holds no caret.
    this.#view.scrollDOM.removeAttribute("tabindex");
    this.#describe();
    this.#paintEmpty();
  }

  // A move between parents reconnects within the task and keeps its editor.
  disconnectedCallback() {
    queueMicrotask(() => {
      if (this.isConnected || !this.#view) return;
      this.#model = this.#view.state;
      this.#view.destroy();
      this.#view = null;
    });
  }

  #describe() {
    const content = this.#view?.contentDOM;
    if (!content || !("ariaDescribedByElements" in content)) return;
    const root = this.getRootNode();
    content.ariaDescribedByElements = (this.getAttribute("aria-describedby") ?? "")
      .split(/\s+/)
      .filter(Boolean)
      .map((id) => root.getElementById(id))
      .filter(Boolean);
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
    if (this.#root.activeElement !== view.contentDOM) return;
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
    const state = this.#create(text);
    if (!this.#view) {
      this.#model = state;
      return;
    }
    this.#view.setState(state);
    this.#paintEmpty();
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
