/* The runtime's text field: a Markdown editor that presents itself as a textarea.
 *
 * Every composer the runtime builds is a `leaf-text`. Inside a closed shadow root its
 * editor runs CodeMirror over the draft's exact source, and draws that source the way a
 * sent message will read: inline code in code type, emphasis and strong in their
 * weights, a link as a link, a heading in bold. The syntax that produces each (backticks,
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
 * `readOnly`, `name` — and brackets user edits with `lf-before-edit` and `input`.
 * The first announces the old layout before browser text input or an editor command
 * changes the words; the second announces the updated value and layout. A
 * write to `value` fires nothing, puts the caret at the end, and starts a new undo
 * history, so undo never walks back into a draft the runtime swapped out.
 * `edit(text)` replaces the words as external text input, such as dictation: it keeps
 * undo history and emits the same before-edit/input bracket as native typing.
 * A box owner that takes pasted pictures intercepts paste in capture; otherwise the field pastes
 * the clipboard's text, including text carried beside a picture.
 * `naturalBlockSize` reads the field's intrinsic border-box block size in CSS pixels,
 * before the host's block size or its minimum and maximum constrain the writing room.
 * `writingInlineSize` reads the editor's allocated writing measure, including room
 * reserved for its trailing action, in CSS pixels. `writingEndRoom` reads that room's
 * exact width so a sent message can keep the same writing measure.
 *
 * The placeholder is a layer under the words, shown while the field is empty. It reads
 * the `placeholder` attribute, and a child in slot `placeholder` stands in its place when
 * a box wants more than one run of text there, such as a label and the key that sends.
 *
 * The editor arrives when the field is first needed rather than when it is built: when
 * it is shown with a box, or focused. Composers stand hidden from the first paint, so a
 * page whose fields stay hidden never loads CodeMirror (`text-editor.js`). Until the
 * editor is there a native textarea stands in for it, in the same frame: it holds the
 * words and selection and takes typing, paste, input-method composition, dictation and
 * caret placement natively, so nothing the user does while the editor loads waits on
 * it or is replayed by hand. It shows the words plain, holding the trailing action's
 * room on every line. Owner steps and external edits made meanwhile are kept in order
 * with the words they followed, and the editor replays them, so undo walks the same
 * history. Once CodeMirror has loaded, a field builds its editor in the turn it is
 * needed; before that, when the module lands, carrying focus, words and selection
 * across, after any input-method composition or held pointer on the stand-in ends. A
 * field needed without its editor holds the page's rendering readiness until the editor
 * is built, so a page reads ready only once every field on screen has it. If the module
 * fails to load, the stand-in goes on taking words and the next need tries again.
 *
 * A built editor lives while the element is in a document. A field removed and not put
 * back in the same task keeps its state and destroys its view, which releases the
 * listeners CodeMirror holds on the window and document; reconnecting builds another.
 * `:state(ready)` means the field draws its words, in the stand-in or the editor. A
 * reading surface being replaced can keep its words in flow until then, so measuring
 * the connecting editor never collapses the scrollport before it has content.
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
import { TEXT_FIELD } from "../control-selectors.js";
import { canPlaceFocus } from "../focus.js";
import { keeps } from "../keeps.js";
import { holdRendering, nextRender, sizeObserver } from "../rendering.js";

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
  .cm-line { padding: 0; }
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
  :host(:state(scrolls)) .lf-field { padding-inline-end: var(--lf-field-end-room); }
  :host(:state(scrolls)) .cm-line.lf-field-last::after { content: none; }
  /* The stand-in draws the words plain where the editor will, and cannot hold room
     after the last words alone, so it holds it on every line. */
  .lf-field-stand-in { display: block; box-sizing: border-box; inline-size: 100%;
    min-block-size: 1lh; field-sizing: content; margin: 0; border: 0; padding: 0;
    background: transparent; outline: none; resize: none; overflow: hidden;
    white-space: pre-wrap; overflow-wrap: anywhere; word-break: break-word;
    font: inherit; letter-spacing: inherit; word-spacing: inherit; color: inherit;
    caret-color: currentColor; text-align: inherit; }
  :host(:state(stand-in)) .lf-field { padding-inline-end: var(--lf-field-end-room); }
  :host(:state(stand-in)) .lf-field-placeholder { padding-inline-end: 0; }
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
    padding-inline-start: var(--quote-inset); color: var(--muted); }
  .lf-md-code-block { font-family: var(--mono); font-size: var(--code-size);
    line-height: var(--code-line); color: var(--code-ink); background: var(--pre-bg);
    font-variant-ligatures: none; border-inline: 1px solid var(--code-border);
    padding-inline: var(--pre-inset); }
  .lf-md-code-first { border-block-start: 1px solid var(--code-border);
    border-start-start-radius: var(--r); border-start-end-radius: var(--r); }
  .lf-md-code-last { border-block-end: 1px solid var(--code-border);
    border-end-start-radius: var(--r); border-end-end-radius: var(--r); }
`);

// The editor's module, shared by every field once one has needed it.
let editing = null;
let loading = null;
const loadEditing = () =>
  (loading ??= import("./text-editor.js").then(
    (module) => (editing = module),
    (error) => {
      loading = null;
      throw error;
    },
  ));

const normalized = (text) => String(text ?? "").replace(/\r\n?/g, "\n");

class LeafText extends HTMLElement {
  #root;
  #internals = null;
  #placeholderLayer = document.createElement("div");
  #placeholderText = document.createTextNode("");
  #frame = document.createElement("div");
  #readOnly = false;
  // The textarea holding the words until the editor arrives, and what the editor
  // replays then: the words the last value write left, and each owner step and
  // external edit after the words it followed.
  #standIn = document.createElement("textarea");
  #draft = { base: "", steps: [] };
  #editor = null;
  // The readiness this field holds while it is needed without its editor.
  #held = null;
  #composing = false;
  #pressed = false;
  // A box is a need. The editor builds in the next pass rather than in this delivery,
  // whose loop would not deliver the observers a build starts on the same host.
  #shown = sizeObserver(() => {
    if (this.checkVisibility()) nextRender(() => this.#need());
  });

  static observedAttributes = ["aria-label", "aria-describedby", "placeholder"];

  constructor() {
    super();
    this.#root = this.attachShadow({ mode: "closed", delegatesFocus: true });
    this.#root.adoptedStyleSheets = [sheet];
    this.#frame.className = "lf-field";
    this.#placeholderLayer.className = "lf-field-placeholder";
    this.#placeholderLayer.setAttribute("aria-hidden", "true");
    const hint = document.createElement("slot");
    hint.name = "placeholder";
    hint.append(this.#placeholderText);
    this.#placeholderLayer.append(hint);
    const standIn = this.#standIn;
    standIn.className = "lf-field-stand-in";
    standIn.rows = 1;
    this.#paintStandIn();
    this.#frame.append(this.#placeholderLayer, standIn);
    this.#root.append(this.#frame);
    standIn.addEventListener("input", () => this.#edited(true));
    standIn.addEventListener("keydown", (event) => this.#standInReturn(event));
    standIn.addEventListener("focus", () => this.#need());
    standIn.addEventListener("compositionstart", () => (this.#composing = true));
    // A gesture's end comes back to the upgrade after the events that finish it, which
    // still target the stand-in: a composition's commit, a press's mouseup and click.
    standIn.addEventListener("compositionend", () => {
      this.#composing = false;
      nextRender(() => this.#upgrade());
    });
    standIn.addEventListener("pointerdown", () => this.#press());
    this.addEventListener("mousedown", (event) => {
      if (this.#editor?.mounted) this.#editor.pressPadding(event);
    });
    this.#root.addEventListener("beforeinput", () => this.#beforeEdit(), {
      capture: true,
    });
    // The content node's own input events would reach the host too, retargeted, and
    // announce every edit twice. The host's is the one the page hears.
    for (const type of ["input", "beforeinput"])
      this.#root.addEventListener(type, (event) => event.stopPropagation());
  }

  attributeChangedCallback(name) {
    if (name === "placeholder") this.#placeholderText.data = this.placeholder;
    if (name === "aria-describedby") return this.#describe();
    if (this.#editor) this.#editor.setAttributes(this.#contentAttributes());
    else this.#paintStandIn();
  }

  connectedCallback() {
    if (this.#editor?.mounted) {
      this.#editor.reconnected();
      return;
    }
    if (!this.hasAttribute("role")) this.setAttribute("role", "textbox");
    if (!this.hasAttribute("aria-multiline"))
      this.setAttribute("aria-multiline", "true");
    // A tab stop, as a textarea is: delegation already stops Tab in the words, and a
    // host reading -1 is one every stop-counting walk would miss.
    if (!this.hasAttribute("tabindex")) this.tabIndex = 0;
    if (!this.#internals) {
      this.#internals = this.attachInternals();
      this.#internals.states.add("stand-in");
    }
    this.#paintEmpty();
    // A field that has had its editor builds it again at once, as it did before.
    if (this.#editor) {
      this.#mount();
      return;
    }
    this.#describe();
    this.#internals.states.add("ready");
    this.#shown.observe(this);
  }

  // A move between parents reconnects within the task and keeps its editor.
  disconnectedCallback() {
    queueMicrotask(() => {
      if (this.isConnected) return;
      this.#shown.unobserve(this);
      this.#internals.states.delete("ready");
      if (this.#editor?.mounted) this.#editor.unmount();
    });
  }

  // The field is needed: it has a box or focus. It builds its editor in this turn once
  // CodeMirror has loaded, and holds readiness until then.
  #need() {
    if (!this.isConnected || this.#editor?.mounted) return;
    this.#held ??= holdRendering();
    if (editing) this.#upgrade();
    else
      loadEditing().then(
        () => this.#upgrade(),
        () => this.#release(),
      );
  }

  #release() {
    this.#held?.();
    this.#held = null;
  }

  // Builds the editor the field was needed for, unless the user is mid-gesture in the
  // stand-in: a composition or a press ends first, and its end comes back here. A
  // field taken out meanwhile keeps its stand-in until it is next needed.
  #upgrade() {
    if (!this.#held || !editing) return;
    if (!this.isConnected) return this.#release();
    if (!this.#editor) {
      if (this.#composing || this.#pressed) return;
      this.#editor = new editing.TextEditor(
        this,
        {
          root: this.#root,
          frame: this.#frame,
          states: this.#internals.states,
          beforeEdit: () => this.#beforeEdit(),
          edited: (changed) => this.#edited(changed),
        },
        {
          ...this.#draft,
          value: this.#standIn.value,
          selection: [this.selectionStart, this.selectionEnd, this.selectionDirection],
          readOnly: this.#readOnly,
          attributes: this.#contentAttributes(),
        },
      );
      this.#draft = null;
    }
    if (!this.#editor.mounted) this.#mount();
    this.#release();
  }

  #mount() {
    const standIn = this.#standIn;
    const focused = Boolean(standIn) && this.#root.activeElement === standIn;
    this.#editor.mount();
    this.#shown.unobserve(this);
    if (standIn) {
      // Focus moves inside the closed root, so the page hears no blur or focus.
      if (focused) this.#editor.focus();
      standIn.remove();
      this.#standIn = null;
      this.#internals.states.delete("stand-in");
    }
    this.#describe();
    this.#internals.states.add("ready");
  }

  #press() {
    this.#pressed = true;
    const done = () => {
      window.removeEventListener("pointerup", done, true);
      window.removeEventListener("pointercancel", done, true);
      this.#pressed = false;
      nextRender(() => this.#upgrade());
    };
    window.addEventListener("pointerup", done, true);
    window.addEventListener("pointercancel", done, true);
  }

  // The editor's Return route (`lf-edit-return`) for the stand-in, whose own Return
  // inserts the newline when the owner leaves the press to the field.
  #standInReturn(event) {
    if (
      event.key !== "Enter" ||
      event.isComposing ||
      event.shiftKey ||
      event.altKey ||
      event.ctrlKey ||
      event.metaKey
    )
      return;
    if (!this.dispatchEvent(new Event("lf-edit-return", { cancelable: true })))
      event.preventDefault();
  }

  #beforeEdit() {
    this.dispatchEvent(new Event("lf-before-edit", { bubbles: true }));
  }

  #edited(changed) {
    this.#paintEmpty();
    if (changed) this.dispatchEvent(new Event("input", { bubbles: true }));
  }

  #describe() {
    const content = this.#editor ? this.#editor.content : this.#standIn;
    if (!this.isConnected || !content || !("ariaDescribedByElements" in content))
      return;
    const root = this.getRootNode();
    content.ariaDescribedByElements = (this.getAttribute("aria-describedby") ?? "")
      .split(/\s+/)
      .filter(Boolean)
      .map((id) => root.getElementById(id))
      .filter(Boolean);
  }

  // The editor adapter places its recorded caret without native scrolling. The
  // field reveals itself separately when its caller requests ordinary focus.
  focus(options) {
    this.#need();
    if (this.#editor?.mounted) {
      if (!this.#editor.focus()) return;
    } else {
      if (!this.#standIn || !canPlaceFocus()) return;
      this.#standIn.focus({ preventScroll: true });
      if (this.#root.activeElement !== this.#standIn) return;
    }
    if (!options?.preventScroll) scrollIntoView(this, { block: "nearest" });
  }

  blur() {
    if (this.#editor) this.#editor.blur();
    else this.#standIn.blur();
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

  #paintStandIn() {
    const attributes = {
      "aria-placeholder": null,
      "aria-label": null,
      ...this.#contentAttributes(),
    };
    for (const [name, value] of Object.entries(attributes))
      keeps(this.#standIn, name, value);
  }

  #paintEmpty() {
    const states = this.#internals?.states;
    if (this.value.length) states?.delete("placeholder-shown");
    else states?.add("placeholder-shown");
  }

  // Where the field holds its action's room now: `every-line`, `last-line` after its
  // last words, or `none` while its last line is blank. A sent message keeping the
  // draft's wrapping holds the same.
  get endRoom() {
    if (parseFloat(getComputedStyle(this.#frame).paddingInlineEnd) > 0)
      return "every-line";
    const text = this.value;
    return text.slice(text.lastIndexOf("\n") + 1).trim() ? "last-line" : "none";
  }

  get writingEndRoom() {
    return parseFloat(getComputedStyle(this).getPropertyValue("--lf-field-end-room"));
  }

  get value() {
    return this.#editor ? this.#editor.value : this.#standIn.value;
  }

  set value(text) {
    text = normalized(text);
    if (text === this.value) return;
    if (this.#editor) this.#editor.value = text;
    else {
      this.#standIn.value = text;
      this.#draft = { base: text, steps: [] };
    }
    this.#paintEmpty();
  }

  edit(text) {
    text = normalized(text);
    if (text === this.value) return;
    if (this.#editor) {
      this.#editor.edit(text);
      this.#paintEmpty();
      return;
    }
    this.#beforeEdit();
    this.#draft.steps.push({ text: this.#standIn.value }, { edit: text });
    this.#standIn.value = text;
    this.#edited(true);
  }

  // Records a change the owner has just made outside the words as a step of the words'
  // history, standing alone: taking the step back calls `undo`, redoing it calls `redo`.
  record(undo, redo) {
    if (this.#editor) this.#editor.record(undo, redo);
    else
      this.#draft.steps.push({ text: this.#standIn.value }, { record: { undo, redo } });
  }

  // Forgets the history and keeps the words, the caret and the editor's DOM, for a box
  // that takes up a draft as it stands.
  restartHistory() {
    if (this.#editor) this.#editor.restartHistory();
    else this.#draft = { base: this.#standIn.value, steps: [] };
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

  get writingInlineSize() {
    const frame = getComputedStyle(this.#frame);
    return parseFloat(frame.inlineSize) + parseFloat(frame.paddingInlineEnd);
  }

  get selectionStart() {
    return (this.#editor ?? this.#standIn).selectionStart;
  }
  get selectionEnd() {
    return (this.#editor ?? this.#standIn).selectionEnd;
  }
  get selectionDirection() {
    if (this.#editor) return this.#editor.selectionDirection;
    const { selectionStart, selectionEnd, selectionDirection } = this.#standIn;
    return selectionStart === selectionEnd ? "none" : selectionDirection;
  }
  // A textarea's clamping: each end within the words, and a start past the end moved to
  // the end.
  setSelectionRange(start, end, direction = "none") {
    const length = this.value.length;
    const to = Math.min(Math.max(Number(end) || 0, 0), length);
    const from = Math.min(Math.max(Number(start) || 0, 0), to);
    (this.#editor ?? this.#standIn).setSelectionRange(from, to, direction);
  }
  select() {
    this.setSelectionRange(0, this.value.length);
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
    if (this.#editor) this.#editor.setReadOnly(this.#readOnly);
    else this.#standIn.toggleAttribute("readonly", this.#readOnly);
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
