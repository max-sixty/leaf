/* The text field's editor: CodeMirror over a `leaf-text`'s exact source.
 *
 * `text-field.js` owns the field and when it gets this editor; this module owns what the
 * editor does once it has one. The field imports it the first time any field is needed,
 * so a page whose fields stay hidden never fetches CodeMirror.
 *
 * A `TextEditor` starts from the draft the field held before it arrived: the words the
 * last value write left, then each owner step and external edit in order, then the words
 * and selection as they stand. Replaying them gives undo the same steps it would have
 * had if the editor had been there from the start; the native typing between them
 * becomes one input step each.
 *
 * The editor's model is one CodeMirror state. It lives in a view while the field is
 * mounted and as a bare state between mounts, so a field moved or hidden and shown again
 * keeps its words, caret and history. A mount observes the host for the field's own
 * reveal and overflow readings; an unmount releases them with the view's listeners on
 * the window and document.
 */
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
import { inputCount } from "../focus.js";
import { loadMarkdown, markdownReady, placedMarkdownTokens } from "../markdown.js";
import { sizeObserver } from "../rendering.js";

const insertNewline = standardKeymap.find(({ key }) => key === "Enter").run;

// A step an owner recorded in the words' history (`record`): `run` makes it happen when
// the history reaches it, and `back` is the step the other way.
const ownerStep = StateEffect.define();

const hide = Decoration.replace({});
const dim = Decoration.mark({ class: "lf-md-mark" });
const link = Decoration.mark({ class: "lf-md-link" });
const line = (cls) => Decoration.line({ class: cls });

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
  for (const { token, from, to, contentFrom, contentTo, escapes } of placed) {
    const syntax = touches(state, from, to) ? dim : hide;
    // The construct as it stands in the draft, which a container may have rewritten
    // before the renderer read it.
    const text = state.doc.sliceString(from, to);
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
      const end = from + text.trimEnd().length;
      const atx = text.match(/^ {0,3}#{1,6}(?:[ \t]+|$)/);
      lines(from, end, (each) => {
        const underline = !atx && each.to >= end;
        if (underline) add(each.from, each.to, dim);
        else out.push(line("lf-md-heading").range(each.from));
      });
      if (atx) add(from, from + atx[0].length, syntax);
    } else if (token.type === "fence" || token.type === "code_block") {
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
    } else if (token.type === "blockquote_open") {
      lines(from, from + text.trimEnd().length, (each) => {
        out.push(line("lf-md-quote").range(each.from));
        const mark = each.text.match(/^ {0,3}> ?/);
        if (mark) add(each.from, each.from + mark[0].length, dim);
      });
    } else if (token.type === "list_item_open") {
      const mark = text.match(/^ {0,3}(?:[*+-]|\d{1,9}[.)])/);
      if (mark) add(from, from + mark[0].length, dim);
    }
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
const lastLineRoom = EditorView.decorations.compute(["doc"], (state) => {
  const last = state.doc.line(state.doc.lines);
  return last.text.trim()
    ? Decoration.set([lastLine.range(last.from)])
    : Decoration.none;
});

// The change taking `state`'s words to `text`: only the run between their common start
// and end, so a replayed run of typing reads as the words it added.
function changeTo(state, text) {
  const old = state.doc.toString();
  let from = 0;
  while (from < old.length && from < text.length && old[from] === text[from]) from++;
  let to = old.length;
  let end = text.length;
  while (to > from && end > from && old[to - 1] === text[end - 1]) {
    to--;
    end--;
  }
  return { from, to, insert: text.slice(from, end) };
}

const selectionOf = (start, end, direction) =>
  direction === "backward"
    ? { anchor: end, head: start }
    : { anchor: start, head: end };

export class TextEditor {
  #host;
  #root;
  #frame;
  #states;
  #beforeEdit;
  #edited;
  #model;
  #view = null;
  #nativeInput = false;
  #reparentHold = null;
  #editable = new Compartment();
  #history = new Compartment();
  #attributes = new Compartment();
  #sizes;
  #overflow;

  /** `host` is the field, which `root` and `frame` belong to and `states` describes.
   * `edited(changed)` runs after every update the view applies, with whether its words
   * changed; `beforeEdit()` runs before a user edit changes them. `draft` is what the
   * field held before the editor: `base`, `steps`, `value`, `selection`, `readOnly`,
   * `attributes` (`text-field.js`, `#draft`). */
  constructor(host, { root, frame, states, beforeEdit, edited }, draft) {
    this.#host = host;
    this.#root = root;
    this.#frame = frame;
    this.#states = states;
    this.#beforeEdit = beforeEdit;
    this.#edited = edited;
    this.#sizes = sizeObserver(() => this.#reveal());
    // Host overflow holds the action's room on every line. The host stops at the page's
    // height limit while words grow inside it, so the reading watches the editor's
    // scroller too. Editor updates and size changes share its read/write phase: the room
    // changes layout there, rather than feeding back into resize observer delivery.
    this.#overflow = sizeObserver(() => this.#measureOverflow());
    let state = this.#create(draft.base, draft.readOnly, draft.attributes);
    for (const step of draft.steps)
      state = state.update(this.#replay(state, step)).state;
    this.#model = state.update({
      changes: changeTo(state, draft.value),
      selection: selectionOf(...draft.selection),
      userEvent: "input.type",
    }).state;
  }

  #replay(state, step) {
    if (step.record)
      return {
        effects: ownerStep.of({ run: step.record.redo, back: step.record.undo }),
        annotations: isolateHistory.of("full"),
      };
    if (step.edit !== undefined)
      return {
        changes: { from: 0, to: state.doc.length, insert: step.edit },
        selection: { anchor: step.edit.length },
        userEvent: "input.dictation",
      };
    return { changes: changeTo(state, step.text), userEvent: "input.type" };
  }

  // A fresh state holding `text`, caret at its end. A new state is also a new undo
  // history.
  #create(text, readOnly, attributes) {
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
              this.#host.dispatchEvent(
                new Event("lf-edit-return", { cancelable: true }),
              ) && insertNewline(view),
          },
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
        lastLineRoom,
        EditorView.lineWrapping,
        this.#editable.of(EditorState.readOnly.of(readOnly)),
        this.#attributes.of(EditorView.contentAttributes.of(attributes)),
      ],
    });
  }

  get mounted() {
    return this.#view !== null;
  }

  get content() {
    return this.#view?.contentDOM ?? null;
  }

  get #state() {
    return this.#view?.state ?? this.#model;
  }

  #apply(spec) {
    if (this.#view) this.#view.dispatch(spec);
    else this.#model = this.#model.update(spec).state;
  }

  /** Build the view in the field's frame. */
  mount() {
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
        this.#measureOverflow();
        this.#edited(edited);
      },
    });
    this.#model = null;
    this.#sizes.observe(this.#host);
    this.#overflow.observe(this.#host);
    this.#overflow.observe(this.#view.scrollDOM);
    // The scroller is focusable only so a press on it keeps focus in the editor, and
    // the field's scroller never scrolls; left focusable it is the node the root
    // delegates focus to, which holds no caret.
    this.#view.scrollDOM.removeAttribute("tabindex");
    this.#measureOverflow();
  }

  /** Destroy the view and keep its state. */
  unmount() {
    this.#reparentHold?.stop();
    this.#model = this.#view.state;
    this.#sizes.disconnect();
    this.#overflow.disconnect();
    this.#view.destroy();
    this.#view = null;
  }

  /** The mounted field moved between parents within one task. */
  reconnected() {
    // Reparenting keeps the CodeMirror view but can leave a pending native
    // selectionchange that replaces its recorded caret with the DOM's reset 0.
    // Only a focused editor needs the hold. An unfocused move may produce no
    // selectionchange, leaving a listener to override a later intentional caret.
    if (!this.#view.hasFocus) {
      this.#reparentHold?.stop();
      return;
    }
    // CodeMirror hears that event after reconnecting. Consume it once,
    // restoring the held selection if needed, unless the user acted first.
    const intent = inputCount();
    const previous = this.#reparentHold;
    if (
      previous?.view === this.#view &&
      previous.doc === this.#view.state.doc &&
      previous.intent === intent
    )
      return;
    previous?.stop();
    const { from, to } = this.#view.state.selection.main;
    const hold = {
      view: this.#view,
      doc: this.#view.state.doc,
      caret: [from, to, this.selectionDirection],
      intent,
    };
    const stop = () => {
      document.removeEventListener("selectionchange", onSelectionChange);
      if (this.#reparentHold === hold) this.#reparentHold = null;
    };
    const restore = () => {
      if (this.#reparentHold !== hold) return;
      if (
        this.#view !== hold.view ||
        !this.#host.isConnected ||
        !hold.view.hasFocus ||
        hold.view.state.doc !== hold.doc ||
        inputCount() !== hold.intent
      ) {
        stop();
        return;
      }
      stop();
      if (
        this.selectionStart !== hold.caret[0] ||
        this.selectionEnd !== hold.caret[1] ||
        this.selectionDirection !== hold.caret[2]
      ) {
        this.setSelectionRange(...hold.caret);
      }
    };
    const onSelectionChange = () => queueMicrotask(restore);
    hold.stop = stop;
    this.#reparentHold = hold;
    document.addEventListener("selectionchange", onSelectionChange);
  }

  // A focused field whose room changed reveals its caret again inside the host.
  #reveal() {
    const view = this.#view;
    const host = this.#host;
    if (view?.hasFocus)
      view.requestMeasure({
        key: this,
        read: () => {
          const caret = view.coordsAtPos(view.state.selection.main.head);
          const box = host.getBoundingClientRect();
          const { scaleX, scaleY } = view;
          return {
            caret,
            scaleX,
            scaleY,
            top: box.top + host.clientTop * scaleY,
            left: box.left + host.clientLeft * scaleX,
            // client dimensions round fractional CSS sizes. Keep the trailing
            // edges on the actual box, inset by its native border and scrollbar.
            bottom:
              box.bottom -
              (host.offsetHeight - host.clientTop - host.clientHeight) * scaleY,
            right:
              box.right -
              (host.offsetWidth - host.clientLeft - host.clientWidth) * scaleX,
          };
        },
        write: ({ caret, top, left, bottom, right, scaleX, scaleY }) => {
          if (!caret) return;
          // Native scroll offsets quantize a fractional correction. Round away from
          // zero so a caret just beyond an edge actually enters the host's scrollport.
          const wholePixel = (distance) =>
            distance < 0 ? Math.floor(distance) : Math.ceil(distance);
          host.scrollBy({
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
  }

  #measureOverflow() {
    const host = this.#host;
    this.#view?.requestMeasure({
      key: this.#overflow,
      read: () => host.scrollHeight > host.clientHeight,
      write: (scrolls) => {
        if (scrolls) this.#states.add("scrolls");
        else this.#states.delete("scrolls");
      },
    });
  }

  /** Focus the words; true when they hold focus. */
  focus() {
    this.#view.focus();
    return this.#root.activeElement === this.#view.contentDOM;
  }

  blur() {
    this.#view?.contentDOM.blur();
  }

  // A press on the box outside the editor's own area — its padding — lands in the words
  // at the nearest character, the way a textarea's does. Presses inside the editor are
  // CodeMirror's to place.
  pressPadding(event) {
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

  get value() {
    return this.#state.doc.toString();
  }

  // A new draft starts its own undo history: removing and restoring the history in
  // successive states starts it empty, and both transactions paint together and
  // announce no user edit.
  #load(state, text) {
    const reset = state.update({
      changes: { from: 0, to: state.doc.length, insert: text },
      selection: { anchor: text.length },
      effects: this.#history.reconfigure([]),
    });
    return [
      reset,
      reset.state.update({ effects: this.#history.reconfigure(history()) }),
    ];
  }

  set value(text) {
    if (!this.#view) {
      this.#model = this.#load(this.#model, text)[1].state;
      return;
    }
    // Loading another draft ends the old native composition. Deactivating its
    // attachment resets the platform's replacement range without moving focus.
    // Updating the live view keeps its native input context in sync with the words.
    const content = this.#view.contentDOM;
    const composing = this.#view.composing && content.editContext;
    if (composing) content.editContext = null;
    this.#view.update(this.#load(this.#view.state, text));
    if (composing) content.editContext = composing;
    this.#measureOverflow();
  }

  edit(text) {
    this.#apply({
      changes: { from: 0, to: this.#state.doc.length, insert: text },
      selection: { anchor: text.length },
      userEvent: "input.dictation",
    });
  }

  record(undo, redo) {
    this.#apply({
      effects: ownerStep.of({ run: redo, back: undo }),
      annotations: isolateHistory.of("full"),
    });
  }

  // Dropping the history's field and adding it back starts it empty.
  restartHistory() {
    this.#apply({ effects: this.#history.reconfigure([]) });
    this.#apply({ effects: this.#history.reconfigure(history()) });
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
  setSelectionRange(start, end, direction) {
    this.#apply({ selection: selectionOf(start, end, direction) });
  }

  setReadOnly(on) {
    this.#apply({ effects: this.#editable.reconfigure(EditorState.readOnly.of(on)) });
  }

  setAttributes(attributes) {
    this.#apply({
      effects: this.#attributes.reconfigure(
        EditorView.contentAttributes.of(attributes),
      ),
    });
  }
}
