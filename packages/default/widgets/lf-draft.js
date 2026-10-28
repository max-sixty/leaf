/* lf-draft: one Markdown source, read as prose and edited in place.
 *
 * The body record and edit log hold the complete source. The shared declared-format
 * renderer supplies safe Markdown in the light DOM, where comments and revision
 * comparison can read it. The editor opens that source unchanged and carries a
 * clicked caret through the shared source/visible alignment. Links and selections
 * keep their native gestures. Quoted drafts are read-only exhibits.
 *
 * Editing controls belong to the box, as marks on a small toolbar hovering over its
 * edge at the right, the top edge for a pointer and the bottom under a finger
 * (draft.css): Edit (a pencil) and Copy at rest, Save, Discard and Copy while editing. Copy copies the Markdown source the box shows. The toolbar takes no room,
 * so the box is the same size with its controls as without them, and opening the
 * editor adds no row of buttons under it; a refused save's status joins the toolbar.
 * Copy keeps the last seat, and Discard opens where Edit stood, so a second press on
 * the pencil gives the box back unchanged. A pointer sees the toolbar while over the
 * box or a key stands in it, and the open editor, a draft that asks for an edit and a
 * finger always, since a pencil that shows only under the pointer left a needed draft
 * with no sign of how to answer it; clicking the prose still opens the editor at that spot. Rejected: a resting row under the prose
 * holding only Edit, which doubled a one-line box, and marks set into the box's
 * corner, which either covered the first line's last words or took room from them
 * and changed the box's size as the editor opened. The same
 * command declarations own pointer activation, keyboard routes, availability and
 * accessible shortcut hints. The editor's own keys, Save's and Escape's, show in the
 * shared command reference (`?`). The controls take no context keys, so an obligation lends them
 * no digits; Tab reaches them, as it does every native button. Comments and workflow
 * receipts keep their own annotation layer; hiding annotations cannot hide the
 * editor's controls. The editor and its tools are Leaf surfaces even inside the
 * document, so Draw and Design modes leave them operable while the saved reading
 * remains the page's to draw on or comment on.
 *
 * The editor opens where the prose stood and in its faces: its field takes each
 * block's type and the gaps between blocks from the draft's place on the page, and
 * draws a picture as the picture, under its source once the caret reaches it
 * (`facesOf`, composing/text-field.js), so no word moves as it opens. Rejected:
 * drawing drafts in a sent message's face, which the editor already wore, since drafts
 * would lose their document type, chosen by the user on 2026-10-23.
 *
 * The editor reads as an ordinary text box: its words stand in the field until the user
 * leaves it, and the field's own undo walks them back. Two ways out throw its changes
 * away, Discard and Escape, as a message rewrite's do; every other way out saves them
 * as Save does, which submits one absolute edit through the shared send generation. A
 * press away from the draft saves (focus.js, `onPressAway`), so a tap elsewhere on a
 * phone keeps what was typed without finding Save first, and Android's back
 * gesture saves the same way (`keep`, close-requests.js). A stray edge swipe therefore
 * sends the agent a turn, as a stray tap does (the user's decision, 2026-10-27). Rejected: back closing the editor with its
 * words kept unsaved, a third way out whose state the closed box had to show beside
 * Edit; and saving at each pause in the typing, as a form does, since every save is an
 * edit delivered to the agent, which would read half-written words. Pointer Discard returns the frame
 * over a short native size interpolation; its words and Edit focus return at once.
 * Keyboard discarding and reduced motion are instant; reopening cancels the effect.
 * A saved edit is withdrawn with the page's undo (`z`), and the log keeps every version for the agent. Rejected: Escape setting
 * unsent words aside for the next opening, which needed a Close button beside Discard
 * and left a closed box holding words it gave no sign of; and a Changes list that
 * restored earlier versions, which the page's undo already does.
 *
 * The shared draft store still holds an open editor's words, so they survive a
 * reload, a live revision that replaces this element, and the tab closing, and every
 * tab's open editor shows the same words. An active editor defers authoritative
 * projection until it closes. Another tab's settlement closes its matching editor
 * without taking focus from an unrelated place. A refused save reopens the retained
 * source with Retry, and takes the focus only from this draft or from nowhere. Print keeps the saved reading and omits controls.
 */
import {
  addressableLabel,
  addressableWord,
  commandScope,
  motion,
  returnDuration,
  html,
  render,
  offered,
  offeredAction,
  nothing,
  LeafElement,
  offer,
  TEXT_FIELD,
  paintKeys,
  quoted,
  sendDraft,
  raiseError,
  commands,
  copyBlock,
  saveDraft,
  loadDraft,
  clearDraft,
  watchDraft,
  whileConnected,
  pressIsKeyboardActivation,
  reachedForWords,
  paintMarkdown,
  markdownSourceOffset,
  markdownWords,
  focusDestination,
  nextRender,
  retainUserIntent,
  scrollIntoView,
  focused,
  onPressAway,
  PRESSABLE,
} from "/runtime/widget-api.js";

// Each control's key and the action whose mark it shows.
const TOOLS = [
  ["edit", "edit"],
  ["save", "save"],
  ["cancel", "discard"],
];

// The store key for a draft's unsent edit. The page's port is its own origin, so
// the id alone is unambiguous — the same scoping every composer draft relies on.
// Presence and content are different for this widget, because deleting every character is
// an unsent edit — and that is the shared store's own rule, so the text goes in bare and
// the store's null is "nothing pending".
const ctx = (id) => "edit:" + id;
const saveEdit = (id, text) => saveDraft(ctx(id), text);
const clearEdit = (id) => clearDraft(ctx(id));
const loadEdit = (id) => loadDraft(ctx(id));

// Carry a rendered caret into source; a padding press has no caret to transfer.
function caretAt(body, x, y) {
  const pos = document.caretPositionFromPoint(x, y);
  if (!pos) return null;
  const offset = markdownSourceOffset(body, pos.offsetNode, pos.offset);
  return offset === null ? null : [offset, offset];
}

customElements.define(
  "lf-draft",
  class extends LeafElement {
    // What the obligation was answered with: the current words.
    static answerWords(value) {
      return markdownWords(value).trim() || "Empty";
    }

    #body;
    #editor = null;
    #sending = false;
    #failed = false;
    #tools = null;
    #copy = null;
    #commandScope = null;
    #resumeProjection = null;
    #recovered = false;
    #returnMotion = null;
    #cancelSize = null;
    #stopPressAway = null;

    setup() {
      this.#body = this.querySelector(":scope > .lf-markdown-body");
      if (this.childNodes.length !== 1 || this.firstChild !== this.#body)
        this.replaceChildren(this.#body);
      this.#body.className = "lf-draft-body lf-markdown-body"; // NOT .lf-ui: anchoring and Δ must see this

      // A quoted draft is an exhibit: the same formatted text, none of the doors —
      // no controls, box press or editing shortcuts. Quoting
      // gates the action channel, not presentation.
      if (quoted(this)) return;

      this.#offerControls();
      // Capture only the pointer Discard's old allocation. The command still owns
      // closing, discarding and focus; its new reading is true before this effect.
      this.addEventListener(
        "click",
        (event) => {
          this.#cancelSize = null;
          if (
            event.button !== 0 ||
            pressIsKeyboardActivation(event) ||
            !(
              /** @type {Element} */ (event.target).closest(
                '[data-lf-draft-action="cancel"]',
              )
            ) ||
            !this.#editor ||
            !CSS.supports("block-size", "calc-size(auto, size)")
          )
            return;
          this.#cancelSize = this.getBoundingClientRect().height;
        },
        { capture: true },
      );

      // A click opens the exact source at its rendered caret. Presses, links and
      // completed word selections own their own gestures; Leaf's generated chrome that
      // is no press, such as the thread message a reply's draft stands in, does not.
      this.addEventListener("click", (ev) => {
        // A keyboard activation carries no place, and the keyboard's door is the ✎. The
        // primary button only: a middle- or right-press is not the gesture this is for.
        if (
          pressIsKeyboardActivation(ev) ||
          ev.button !== 0 ||
          /** @type {Element} */ (ev.target).closest(`${PRESSABLE}, a, button`)
        )
          return;
        if (reachedForWords(this)) return;
        if (!this.#available()) return;
        this.#open(undefined, caretAt(this.#body, ev.clientX, ev.clientY));
      });

      // One edit, however many tabs are open on the page. An open box follows what is
      // typed in another; a closed one stays closed, because news arriving has no gesture
      // behind it and the box would open under whatever the user is doing here — it
      // takes up the words at the next opening either way (#open reads the store). A
      // settlement is the case that does move this tab: the words are sent or discarded,
      // so an open box holding them has nothing left to hold, and closing it lets replay
      // paint whatever the log ends up saying.
      whileConnected(this, () => {
        const stopDraft = this.#watchDraft();
        if (
          this.#editor &&
          !this.#resumeProjection &&
          this.controller.read().actions.edit.available
        )
          this.#resumeProjection = this.controller.defer();
        return () => {
          this.#returnMotion?.cancel();
          this.#stopPressAway?.();
          this.#stopPressAway = null;
          stopDraft?.();
          this.#resumeProjection?.();
          this.#resumeProjection = null;
        };
      });
    }

    #recoverEdit() {
      if (this.#recovered) return;
      this.#recovered = true;
      // A recovered edit outranks the authored text: the user typed it and never got
      // it sent, so it must survive exactly as the composer's drafts do. This runs in
      // the first complete reading, after the render established the source-authored
      // body. A live revision's replacement nodes connect before their atomic document
      // adoption and deliberately receive no partial semantic reading.
      //
      // An edit coming back is not the user arriving, though, so the box does not take
      // the focus. A revision that rewrote this draft connects it again while the user
      // stands somewhere else, and news with no gesture behind it moves nobody — the same
      // reason `#watchDraft` leaves a closed box closed. On a page that has just loaded,
      // startup hands the focus to the page after this runs either way.
      //
      // The store holds words only while an editor stands open on them, so any it
      // holds reopen that editor. They are not compared with the current text: this
      // first reading can precede the log's, and words walking a saved edit back to the
      // authored text are an edit all the same.
      const pending = loadEdit(this.id);
      if (pending !== null) this.#open(pending, undefined, false);
    }

    #watchDraft() {
      if (quoted(this) || !this.#tools) return;
      return watchDraft(
        ctx(this.id),
        (text) => {
          if (text === null) this.#close(false);
          else if (this.#editor && this.#editor.value !== text)
            this.#editor.value = text;
        },
        {
          input: () => this.#editor,
          resume: () =>
            this.#available()
              ? {
                  where: this,
                  input: () => this.#editor,
                  open: () => this.#open(undefined, undefined, false),
                }
              : null,
        },
      );
    }

    #offerControls() {
      if (quoted(this) || this.#tools) return;
      this.#tools = offer("div", "lf-draft-tools lf-mark-bar");
      this.#tools.dataset.lfRuntime = "";
      this.append(this.#tools);
      // Copy is the toolbar's last mark, so Tab from the editor reaches Save first.
      this.#copy = copyBlock(
        this,
        () => this.#editor?.value ?? this.controller.read().state.edit.value,
        "Markdown",
      );
      this.#paintTools();
      this.#ensureCommands();
    }

    #ensureCommands() {
      if (this.#commandScope) return;
      this.#commandScope = commandScope("On a draft", [
        {
          id: "draft.edit",
          keys: [],
          control: () => this.#control("edit"),
          decision: true,
          title: "Edit",
          when: () => !this.#editor && !this.#sending && this.#available(),
          run: () => this.#open(),
        },
        {
          id: "draft.save",
          reach: "in an open draft editor",
          keys: ["Mod+Enter"],
          control: () => this.#control("save"),
          decision: true,
          title: () => (this.#failed ? "Retry" : "Save"),
          when: () => Boolean(this.#editor) && !this.#sending && this.#available(),
          run: () => this.#commit(),
        },
        {
          id: "draft.cancel",
          reach: "in an open draft editor",
          keys: ["Escape"],
          control: () => this.#control("cancel"),
          decision: true,
          title: "Discard",
          when: () => Boolean(this.#editor),
          run: () => this.#close(true),
          keep: () => this.#commit(),
        },
      ]);
      commands(this, this.#commandScope);
    }

    #control(key) {
      return this.#tools?.querySelector(`[data-lf-draft-action="${key}"]`) ?? null;
    }

    // The editor and the toolbar's controls follow one reading of availability. A
    // refused save's status stands in the toolbar, before its marks, so saying it
    // moves no words either.
    #paintTools() {
      if (!this.#tools) return;
      const editing = Boolean(this.#editor);
      if (this.#editor) this.#editor.readOnly = !this.#available();
      render(
        html`<span ${offered("lf-draft-status")} role="status"
            >${this.#failed ? "Save failed. The edit is kept." : ""}</span
          >
          ${TOOLS.map(
            ([key, action]) =>
              html`<button
                ${offeredAction("mark", "", undefined, {
                  action: key === "save" && this.#failed ? "retry" : action,
                })}
                data-lf-draft-action=${key}
                ?hidden=${key === "edit" ? editing : !editing}
                aria-expanded=${key === "edit" ? String(editing) : nothing}
              ></button>`,
          )}
          ${this.#copy}`,
        this.#tools,
      );
      paintKeys();
    }

    #available() {
      return Boolean(this.controller.read().actions.edit?.available);
    }

    // The draft as the rest of the chrome names it, never by its id.
    #named() {
      const label = addressableLabel(this);
      return label ? `“${label}”` : `the ${addressableWord(this)}`;
    }

    #dispatch(text, attempt) {
      return this.controller.dispatch({
        kind: "action",
        verb: "edit",
        detail: { value: text },
        ...(attempt && { attempt }),
        says: `Edited ${this.#named()}`,
      });
    }

    #open(seed, at, arrive = true) {
      this.#returnMotion?.cancel();
      this.#returnMotion = null;
      if (this.#editor) return;
      if (this.#sending) {
        raiseError("Wait for the current edit to finish saving");
        return;
      }
      if (this.#available()) this.#resumeProjection ??= this.controller.defer();
      const editor = offer(TEXT_FIELD, "lf-draft-edit");
      editor.dataset.lfRuntime = "";
      // It stands where the prose did, so it reads in the prose's faces.
      editor.facesOf = this.#body;
      // Words another tab's open editor holds outrank the current text: they are the
      // same unsent edit.
      const effective = this.controller.read().state.edit.value;
      editor.value = seed ?? loadEdit(this.id) ?? effective;
      editor.setAttribute("aria-label", `Edit ${this.#named()}`);
      editor.addEventListener("input", () => {
        saveEdit(this.id, editor.value);
        if (this.#failed) {
          this.#failed = false;
          this.#paintTools();
        }
      });
      // The composer's bindings on the box that replaces the page's own words. Escape
      // being the innermost scope's is what keeps the runtime's own rung from running
      // behind it and closing a panel too.
      this.#editor = editor;
      commands(editor, this.#commandScope);
      this.#body.after(editor);
      // Its toolbar stands inside the draft, so Discard and Copy are no press away.
      this.#stopPressAway = onPressAway(
        (path) => !path.includes(this),
        () => void this.#commit(),
      );
      this.#paintTools();
      // A pointer is already on visible words. Opening their editor preserves that
      // place before handing the clicked caret across; the Edit control instead reveals
      // the initial caret at the end of the text. A padding press carries null.
      // Only the pointer names a place; the Edit control and a recovered draft leave the
      // caret where focus put it, at the end of the text. The range was measured
      // in the body's text, so it names a word only in a box holding that text — a
      // resumed edit opens with different words at those offsets.
      if (at && editor.value === effective) editor.setSelectionRange(at[0], at[1]);
      if (arrive) {
        focusDestination(editor, "move");
        if (at === undefined) scrollIntoView(editor, { block: "nearest" });
      }
    }

    #close(discard) {
      if (!this.#editor) return;
      const before = this.#cancelSize;
      this.#cancelSize = null;
      // Hold the old allocation before any control repaint can read layout and
      // clamp a reader at the document foot. Native auto follows the restored body.
      if (before !== null)
        this.#returnMotion = motion(
          this,
          [{ blockSize: `${before}px` }, { blockSize: "calc-size(auto, size)" }],
          returnDuration(),
        );
      if (discard) clearEdit(this.id);
      this.#stopPressAway?.();
      this.#stopPressAway = null;
      // Only where the user was in it. A close this tab's own gesture made
      // has focus in the box that is going, and the draft's one persistent control is
      // where it lands so a keyboard user isn't dropped back at the page top; a close
      // another tab's settlement brings takes focus from wherever they actually are.
      const left = focused(document);
      const stood = this.contains(left);
      const mayReturn = retainUserIntent({ source: left });
      this.#editor.remove();
      this.#editor = null;
      this.#failed = false;
      this.#paintTools();
      if (stood) {
        if (this.#sending) focusDestination(this, "return");
        else
          nextRender(() => {
            // Command availability is painted before this callback. A new gesture
            // elsewhere wins over handing back the editor's vacated focus.
            if (this.isConnected && !this.#editor && mayReturn())
              focusDestination(this.#control("edit"), "return");
          });
      }
      // Replay may have been held by this editor. Its close is the generic projection
      // invalidation that lets the state feed retry the complete reading now.
      this.#resumeProjection?.();
      this.#resumeProjection = null;
    }

    async #commit() {
      if (!this.#editor || this.#sending) return;
      if (!this.#available()) return;
      const text = this.#editor.value;
      if (text === this.controller.read().state.edit.value) {
        this.#close(true);
        return;
      }
      this.#sending = true;
      this.#close(false);
      this.setAttribute("aria-busy", "true");
      const ok = await sendDraft(
        ctx(this.id),
        () => true,
        (attempt) => this.#dispatch(text, attempt)?.delivery ?? null,
      );
      this.#sending = false;
      this.removeAttribute("aria-busy");
      this.#paintTools();
      if (!ok) {
        const stored = loadEdit(this.id);
        // Null means the same shared generation was settled by the other tab while
        // this one waited to send. Its action will replay this body, so do
        // not resurrect the editor as if a network failure had occurred. A stored
        // generation is either the failed send itself or newer shared text; both stay
        // editable. The outbox has already projected the authoritative body before
        // resolving this call, so opening the saved generation must not overwrite it
        // with the stale pre-send snapshot.
        if (stored !== null) {
          this.#failed = true;
          // A press away may have taken the user on to another place, such as the
          // next draft's editor, which keeps the focus.
          const here = focused(document);
          this.#open(
            stored,
            undefined,
            !here || here === document.body || this.contains(here),
          );
        }
      }
    }

    // A live editor owns its transient text; the complete state waits for it.
    render() {
      const { state, actions } = this.reading;
      paintMarkdown(this.#body, state.edit.value);
      if (quoted(this)) return nothing;
      // Recovery chooses the first action face: an unsent editor opens with Save
      // and Discard, without briefly publishing the resting Edit control.
      this.#recoverEdit();
      this.#paintTools();
      if (this.#editor && !this.#resumeProjection && actions.edit.available)
        this.#resumeProjection = this.controller.defer();
      return nothing;
    }
  },
);
