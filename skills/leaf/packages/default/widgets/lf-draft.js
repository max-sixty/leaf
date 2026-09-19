/* lf-draft: a block of text the user owns — rewrite it in place, and the exact
 * words reach the agent.
 *
 * The problem this solves that no other widget does: lf-board and lf-options let the
 * user *choose* among things the agent wrote, but never *change* the words. The
 * fastest correction to a sentence is typing the better sentence, not describing it in
 * a comment. That capability is the whole element: one verb (`edit`, the entire new
 * text), no container, no approve/skip chrome. Decisions compose from structures that
 * already own them — put a draft inside a lf-card and the column is the verdict; page
 * assent is sign-off — rather than growing a second set of buttons here.
 *
 * Two rules shape the implementation:
 *
 * 1. Authored text stays in the light DOM as real text. A textarea's value lives off
 *    the text-node tree, so anything inside one is invisible to comment anchoring and
 *    to the version diff. So the body is a plain div — generated, but deliberately NOT
 *    marked .lf-ui or data-lf-gen, because those are exactly the markers that tell the
 *    anchor pass and the diff to look away. A div and not the <pre> the markup wrote,
 *    which would be the tidier swap: <pre> is a text block, and the runtime's comment
 *    line lands on the nearest one, so keeping it puts that line inside the words the
 *    editor is seeded from — the exact failure the marker rules exist for. The textarea
 *    exists only while an edit is open, and its result is written back as text. Read
 *    mode is the resting state; comments and Δ work there. Leaf's authored-body
 *    decoder strips the indentation the HTML source gave every line, so an agent can
 *    indent a draft like any other child content without the indentation becoming part
 *    of the draft's text.
 * 2. renderState states absolute values — the whole body, never a patch — so replay is
 *    idempotent and two tabs converge on the last write. Reader edits remain effective
 *    across revisions. The runtime marks an effective body that differs from authored
 *    text with data-lf-reader-override.
 *
 * Editing has two doors: the box itself, which opens the editor with the caret where the
 * press landed, or the ✎ button (the door the keyboard uses). The block being its own
 * door is what a reader finds without being told — the ✎ sits in the margin, 45px from
 * the words it edits, and the gesture that used to open the box in place was a
 * double-click nothing advertised. The draft
 * contributes that disclosure to its target's shared margin entry cluster. Save and Cancel
 * replace it for the length of an edit, with their width reserved before presentation,
 * so opening the editor changes what the one RHS item offers without moving the
 * document. Unsent
 * keystrokes ride the runtime's draft store
 * (saveDraft/clearDraft), the composer's discipline: written on input, cleared only by a
 * successful send or explicit Cancel, so reload, version switch, server death and the
 * tab's own close all recover. The text goes in bare, an empty edit being a real
 * replacement the store keeps and only a settlement removing the key — the store's rule,
 * not this widget's exception to it. One edit has one copy across the reader's tabs
 * (watchDraft): an open box follows the words being typed in another, a settled draft
 * closes the box it left behind, and a closed one stays closed.
 * A send owns the shared draft generation until its response, as every composer does:
 * the log attempt makes two tabs' Save presses one action, while the instance flag closes
 * this tab's other edit doors during the request.
 *
 * Once an edit exists, a native disclosure compares the authored body with the
 * standing one and lists the widget's absolute edit actions in log order. The runtime
 * owns that sequence and version boundary; the module owns only
 * its presentation. Restoring a row sends its text as one more ordinary edit, which
 * keeps one state model and lets another tab converge without knowing that the gesture
 * happened in a history view.
 *
 * The box's door is taken on click rather than on mousedown, and that is what lets a
 * drag across the draft still take its words: the gesture is only a press once the
 * button comes up somewhere that isn't a selection, which is the question
 * `reachedForWords` answers for every other press on the page's own words. A single
 * press makes a collapsed caret, so there is no selection to flash and nothing to
 * cancel — the word-flash this door used to have to preventDefault away was the second
 * mousedown of a double-click, and that mousedown now lands in the open textarea, where
 * selecting a word is what a double-click means everywhere else.
 *
 * The local editor and history are injected through the runtime's `offer`, which marks them
 * .lf-ui for the chrome look, data-lf-gen so the diff ignores them, and data-lf-offer for a
 * thing to work. The margin controls are projection-owned DOM rendered from this widget's
 * immutable contribution. Those boundaries keep chrome off the printed page, out of the
 * anchor pass, and out of the way of the box's own door below; the class also earns the
 * edit box the runtime's one textarea rule. Presentation is theme CSS, the
 * swap between the two views included: an open edit is the box being in the document, so
 * the CSS reads that and this module writes no display state at all. Which is also what
 * lets paper disagree — it drops the box and keeps the words. History is chrome too and
 * exists only on a live page; a scriptless copy cannot honestly offer restore. Authored
 * content is never discarded, so there is no failSoft.
 */
import {
  commandScope,
  DISCLOSE,
  once,
  offer,
  paintKeys,
  quoted,
  revisionLabel,
  registerMarginContribution,
  sendDraft,
  notice,
  keeps,
  commands,
  saveDraft,
  loadDraft,
  marginEntry,
  clearDraft,
  watchDraft,
  alignText,
  alignedNodes,
  widgetController,
  reachedForWords,
} from "/runtime/widget-api.js";

// The store key for a draft's unsent edit. The page's port is its own origin, so
// the id alone is unambiguous — the same scoping every composer draft relies on.
// Presence and content are different for this widget, because deleting every character is
// an unsent edit — and that is the shared store's own rule, so the text goes in bare and
// the store's null is "nothing pending".
const ctx = (id) => "edit:" + id;
const saveEdit = (id, text) => saveDraft(ctx(id), text);
const clearEdit = (id) => clearDraft(ctx(id));
const loadEdit = (id) => loadDraft(ctx(id));
const draftReserve = () => {
  const aim = parseFloat(
    getComputedStyle(document.documentElement).getPropertyValue("--aim-floor"),
  );
  return Math.max(32, aim || 0) * 2 + 4;
};

// Where the click asked for the caret, as an offset in the body's text — the body holds
// one text node, so its offsets are the textarea's offsets. Past the end of the text
// there is no offset to carry at all, and the box opens where focus alone would have put
// it.
//
// A collapsed caret and not a word, because one click means one caret everywhere else.
// This used to widen the offset to the word around it, through an Intl.Segmenter that
// knew the boundaries of the language the draft was written in, because the door was a
// double-click and a double-click means the word. The door is a single click now, and
// the second click of a double lands in the textarea the first one opened — so the word
// is selected by the browser, in its own box, by the same segmentation it uses in every
// other text field. The widget had been reimplementing that to hand it back.
function caretAt(body, x, y) {
  const pos = document.caretPositionFromPoint(x, y);
  if (!pos || pos.offsetNode !== body.firstChild) return null;
  return [pos.offset, pos.offset];
}

customElements.define(
  "lf-draft",
  class extends HTMLElement {
    #controller = widgetController(this);
    #body;
    #history = null;
    #historyKey = "";
    #alignments = new Map();
    #ta = null;
    #sending = false;
    #failed = false;
    #margin = null;
    #commandScope = null;
    #stopReading = null;
    #stopDraft = null;
    #resumeProjection = null;
    #recovered = false;

    connectedCallback() {
      if (!once(this)) {
        this.#offer();
        this.#paintAvailability();
        this.#watchReading();
        this.#watchDraft();
        return;
      }

      this.textContent = "";

      this.#body = document.createElement("div");
      this.#body.className = "lf-draft-body"; // NOT .lf-ui: anchoring and Δ must see this
      this.append(this.#body);

      // A quoted draft is an exhibit: the same dedented text, none of the doors —
      // no pencil, no press on the box, no edit keys in the command reference dialog. Quoting
      // gates the action channel, not presentation.
      if (quoted(this)) {
        this.#watchReading();
        return;
      }

      this.#offer();

      // Reserve the editor's wider pair before the page is presented, then keep the
      // resting pencil against the marker at the entry's right edge. Opening the editor
      // changes the immutable entries without moving the document beneath it.
      // Establish availability before the action watcher makes its first synchronous
      // reading, which no longer notifies. Every later transition this paints — failed,
      // sending, engaged — already runs through a notifying margin update, so the
      // watcher's own callback would fan one shared refresh out through every draft for
      // a projection none of them changed.
      this.#refreshMargin();
      this.#watchReading();

      // The box is the door. A draft is the one block on the page whose whole purpose is
      // that the reader rewrites it, so a press anywhere in it opens the editor with the
      // caret where they pressed — the ✎ is 45px away in the margin, and a double-click
      // is a gesture nothing on the block advertised.
      //
      // A click on the widget's own chrome belongs to that control — above all to the
      // edit box, which is inside this element and would otherwise reopen on every press
      // in it. What the guard means is "a thing to work", so it reads the marker that
      // says so and not the chrome face, which is a look and would answer by coincidence.
      //
      // A drag that ended on these words was the reader taking them, not opening
      // anything: the same complaint `reachedForWords` is for, and the same answer, which
      // is why it is asked here rather than reimplemented. Opening on the drag's mouseup
      // would throw the selection away at the moment it was finished.
      this.addEventListener("click", (ev) => {
        // A keyboard activation carries no place, and the keyboard's door is the ✎. The
        // primary button only: a middle- or right-press is not the gesture this is for.
        if (ev.detail === 0 || ev.button !== 0 || ev.target.closest("[data-lf-offer]"))
          return;
        if (reachedForWords(this)) return;
        if (!this.#available()) return;
        this.#open(undefined, caretAt(this.#body, ev.clientX, ev.clientY));
      });

      // One edit, however many tabs are open on the page. An open box follows what is
      // typed in another; a closed one stays closed, because news arriving has no gesture
      // behind it and the box would open under whatever the reader is doing here — it
      // takes up the words at the next opening either way (#open reads the store). A
      // settlement is the case that does move this tab: the words are sent or discarded,
      // so an open box holding them has nothing left to hold, and closing it lets replay
      // paint whatever the log ends up saying.
      this.#watchDraft();
    }

    disconnectedCallback() {
      this.#stopReading?.();
      this.#stopReading = null;
      this.#stopDraft?.();
      this.#stopDraft = null;
      this.#margin?.unregister();
      this.#margin = null;
      this.#resumeProjection?.();
      this.#resumeProjection = null;
    }

    #watchReading() {
      const interactive = !quoted(this);
      if (
        interactive &&
        this.#ta &&
        !this.#resumeProjection &&
        this.#controller.read().actions.edit.available
      )
        this.#resumeProjection = this.#controller.defer();
      this.#stopReading ??= this.#controller.subscribe((reading) => {
        if (!interactive) return;
        this.#renderHistory(reading);
        this.#paintAvailability();
        this.#recoverEdit(reading);
        if (this.#ta && !this.#resumeProjection && reading.actions.edit.available)
          this.#resumeProjection = this.#controller.defer();
      });
    }

    #recoverEdit(reading) {
      if (this.#recovered) return;
      this.#recovered = true;
      // A recovered edit outranks the authored text: the user typed it and never got
      // it sent, so it must survive exactly as the composer's drafts do. This runs in
      // the first complete controller publication, after renderState established the
      // source-authored body. A live revision's replacement nodes connect before their
      // atomic document adoption and deliberately receive no partial semantic reading.
      //
      // An edit coming back is not the reader arriving, though, so the box does not take
      // the focus. A revision that rewrote this draft connects it again while the reader
      // stands somewhere else, and news with no gesture behind it moves nobody — the same
      // reason `#watchDraft` leaves a closed box closed. On a page that has just loaded,
      // startup hands the focus to the page after this runs either way.
      const pending = loadEdit(this.id);
      const authored = reading.authored.body.value;
      if (pending !== null && pending !== authored)
        this.#open(pending, undefined, false);
      else if (pending === authored) clearEdit(this.id);
    }

    #watchDraft() {
      if (quoted(this) || !this.#margin) return;
      this.#stopDraft ??= watchDraft(ctx(this.id), (text) => {
        if (text === null) this.#close(false);
        else if (this.#ta && this.#ta.value !== text) this.#ta.value = text;
      });
    }

    #offer() {
      if (quoted(this) || this.#margin) return;
      this.#ensureCommands();
      this.#margin = registerMarginContribution({
        key: `draft:${this.id}`,
        target: () => this,
        read: () => this.#readMargin(),
        activate: (activation) => {
          if (activation === "edit" && this.#available()) return this.#open();
          if (activation === "commit") return this.#commit();
          if (activation === "cancel") return this.#close(true);
        },
      });
    }

    #ensureCommands() {
      if (this.#commandScope) return;
      this.#commandScope = commandScope(
        "On a draft",
        [
          {
            id: "draft.edit",
            keys: [],
            control: () => this.#margin?.control("edit"),
            decision: "Edit…",
            does: "Edit the text in place",
            line: "edit",
            when: () => !this.#ta,
            run: () => this.#margin?.activate("edit"),
          },
          {
            id: "draft.save",
            reach: "in an open draft editor",
            keys: ["Mod+Enter"],
            control: () => this.#margin?.control(this.#saveKey()),
            decision: () => (this.#failed ? "Retry" : "Save"),
            does: () => (this.#failed ? "Retry saving the edit" : "Save the edit"),
            line: () => (this.#failed ? "retry" : "save"),
            when: () => Boolean(this.#ta),
            run: () => this.#margin?.activate(this.#saveKey()),
          },
          {
            id: "draft.cancel",
            reach: "in an open draft editor",
            keys: [],
            control: () => this.#margin?.control("cancel"),
            decision: "Cancel",
            does: "Cancel the edit",
            line: "cancel",
            when: () => Boolean(this.#ta),
            run: () => this.#margin?.activate("cancel"),
          },
          {
            id: "draft.close",
            reach: "in an open draft editor",
            keys: ["Escape"],
            does: "Close the editor, keeping the edit",
            line: "close — edit kept",
            when: () => Boolean(this.#ta),
            run: () => this.#close(false),
          },
        ],
        { answer: () => this.#controller.read().state.body.value.trim() || "Empty" },
      );
      commands(this, this.#commandScope);
    }

    #button(text, onClick, variant) {
      const b = offer("button", "lf-btn" + (variant ? " " + variant : ""), text);
      b.addEventListener("click", onClick);
      return b;
    }

    #saveKey() {
      return this.#failed ? "retry" : "save";
    }

    #entries() {
      const available = this.#available();
      if (!this.#ta)
        return [
          marginEntry({
            key: "edit",
            icon: "edit",
            label: "Edit",
            accessibleLabel: `Edit ${this.id}`,
            behavior: "disclosure",
            rank: "primary",
            state: this.#sending ? "busy" : "idle",
            disabled: this.#sending || !available,
            activation: "edit",
            className: "lf-draft-pencil",
            scope: this.#commandScope,
          }),
        ];
      return [
        marginEntry({
          key: this.#saveKey(),
          icon: this.#failed ? "retry" : "check",
          label: this.#failed ? "Retry" : "Save",
          tone: "positive",
          rank: "complete",
          state: this.#failed ? "failed" : "engaged",
          disabled: !available,
          activation: "commit",
          scope: this.#commandScope,
        }),
        marginEntry({
          key: "cancel",
          icon: "cross",
          label: "Cancel",
          rank: "escape",
          state: this.#failed ? "failed" : "engaged",
          activation: "cancel",
          scope: this.#commandScope,
        }),
      ];
    }

    #readMargin() {
      return {
        subject: null,
        state: this.#failed
          ? "failed"
          : this.#sending
            ? "busy"
            : this.#ta
              ? "engaged"
              : "idle",
        side: "before",
        claim: true,
        reserve: draftReserve(),
        notice: this.#failed && this.#ta ? { text: "Failed", tone: "negative" } : null,
        entries: this.#entries(),
        readings: [
          {
            id: `draft:${this.id}`,
            text: this.#ta ? "Save or cancel draft edit" : `Edit ${this.id}`,
            activate: () => {
              if (this.#ta) this.#ta.focus({ preventScroll: true });
              else this.#margin?.focus("edit");
            },
          },
        ],
      };
    }

    #setRestoreAvailability() {
      const blocked = !this.#available();
      for (const restore of this.querySelectorAll(".lf-draft-restore")) {
        keeps(restore, "aria-disabled", blocked);
        const stop = blocked ? -1 : 0;
        if (restore.tabIndex !== stop) restore.tabIndex = stop;
      }
    }

    #refreshMargin({ immediate = false, focus = null } = {}) {
      this.#setRestoreAvailability();
      this.#margin?.update({ immediate, focus });
      paintKeys();
    }

    #paintAvailability = () => this.#refreshMargin();

    #available() {
      return Boolean(this.#controller.read().actions.edit?.available);
    }

    #dispatch(text, attempt) {
      return this.#controller.dispatch({
        kind: "action",
        verb: "edit",
        detail: { text },
        ...(attempt && { attempt }),
      });
    }

    #delta(before, after, cache = true) {
      const line = document.createElement("div");
      line.className = "lf-draft-delta";
      const key = JSON.stringify([before, after]);
      let alignment = this.#alignments.get(key);
      if (!alignment) {
        alignment = alignText(before, after);
        if (cache) this.#alignments.set(key, alignment);
      }
      line.append(...alignedNodes(alignment));
      if (!line.childNodes.length) line.textContent = "Empty";
      return line;
    }

    #snapshot(label, text, comparison, standing) {
      const item = document.createElement("li");
      const head = document.createElement("div");
      head.className = "lf-draft-revision-head";
      const name = document.createElement("strong");
      name.textContent = label;
      head.append(name);
      if (text !== standing) {
        const restore = this.#button(`Restore ${label.toLowerCase()}`, () =>
          this.#restore(text, label),
        );
        restore.classList.add("lf-draft-restore");
        head.append(restore);
      }
      let body;
      if (comparison === null) {
        body = document.createElement("div");
        body.className = "lf-draft-snapshot";
        body.textContent = text || "Empty";
      } else body = this.#delta(comparison, text);
      item.append(head, body);
      return item;
    }

    #renderHistory(reading) {
      this.#paintAvailability();
      if (this.#sending) return;
      const authored = reading.authored.body.value;
      const actions = reading.actions.edit.history;
      const standing = reading.state.body.value;
      const key = JSON.stringify([
        authored,
        standing,
        actions.map((event) => [event.seq, event.revision, event.detail.text]),
      ]);
      if (key === this.#historyKey) return;
      this.#historyKey = key;
      if (!actions.length && standing === authored) {
        this.#history?.remove();
        this.#history = null;
        return;
      }

      const wasOpen = this.#history?.open ?? false;
      const keepFocus = Boolean(this.#history?.contains(document.activeElement));
      const history = offer("details", "lf-draft-history");
      history.open = wasOpen;
      const summary = document.createElement("summary");
      summary.textContent = `Changes · ${actions.length} ${actions.length === 1 ? "edit" : "edits"}`;

      const current = document.createElement("section");
      current.className = "lf-draft-current";
      const currentLabel = document.createElement("strong");
      currentLabel.textContent =
        standing === authored
          ? "Standing text matches this version"
          : "This version → standing text";
      current.append(currentLabel);
      // This pair changes with every standing edit. Recomputing it once for the new
      // history render is cheaper than retaining every obsolete full-body comparison;
      // adjacent log revisions below are stable and remain worth caching.
      if (standing !== authored) current.append(this.#delta(authored, standing, false));

      const list = document.createElement("ol");
      list.className = "lf-draft-revisions";
      list.append(this.#snapshot("Version text", authored, null, standing));
      let previous = null;
      actions.forEach((event, index) => {
        const text = event.detail.text;
        list.append(
          this.#snapshot(
            `Edit ${index + 1} · ${revisionLabel(event.revision)}`,
            text,
            previous,
            standing,
          ),
        );
        previous = text;
      });
      // The disclosure scope is what works this box, so this binds no `run` and only says
      // the word — one more contributor to the section the draft's other two declare,
      // since the reader standing here is still on a draft. Both cells are read where they
      // are painted: which way the press goes is something the reader can see, and which
      // keys it takes is the scope's own answer for where this box is standing.
      commands(summary, "On a draft", [
        {
          id: "draft.history.toggle",
          keys: () => DISCLOSE(summary),
          does: () => `${history.open ? "Hide" : "Show"} the edit history`,
          line: () => `${history.open ? "hide" : "show"} the history`,
        },
      ]);

      history.append(summary, current, list);
      this.#history?.replaceWith(history);
      if (!this.#history) this.append(history);
      this.#history = history;
      this.#setRestoreAvailability();
      if (keepFocus) summary.focus();
    }

    async #restore(text, label) {
      if (!this.#available()) return;
      if (this.#sending) {
        notice("Wait for the current edit to finish sending");
        return;
      }
      if (this.#ta) {
        notice("Save or cancel the open edit before restoring history");
        return;
      }
      if (text === this.#controller.read().state.body.value) return;
      this.#sending = true;
      this.setAttribute("aria-busy", "true");
      this.#refreshMargin();
      const ok = await this.#dispatch(text)?.delivery;
      this.#sending = false;
      this.removeAttribute("aria-busy");
      this.#refreshMargin();
      this.#renderHistory(this.#controller.read());
      if (ok) notice(`Restored ${label.toLowerCase()} — sent`);
    }

    #open(seed, at, arrive = true) {
      if (this.#ta) return;
      if (this.#sending) {
        notice("Wait for the current edit to finish sending");
        return;
      }
      if (this.#available()) this.#resumeProjection ??= this.#controller.defer();
      const ta = offer("textarea", "lf-draft-edit");
      ta.name = "edit";
      // A set-aside edit outranks the authored text here too: reopening resumes it.
      const effective = this.#controller.read().state.body.value;
      ta.value = seed ?? loadEdit(this.id) ?? effective;
      ta.setAttribute("aria-label", `Edit ${this.id}`);
      ta.addEventListener("input", () => {
        saveEdit(this.id, ta.value);
        if (this.#failed) {
          this.#failed = false;
          this.#refreshMargin();
        }
      });
      // The composer's bindings on the box that replaces the page's own words. Escape sets
      // the edit aside rather than discarding it (never lose user text: Cancel is the only
      // discard) — and being the innermost scope's is what keeps the runtime's own rung
      // from running behind it and closing the panel too, which the widget used to have to
      // prevent by consuming the press.
      this.#ta = ta;
      commands(ta, this.#commandScope);
      this.#body.after(ta);
      this.#refreshMargin();
      if (arrive) ta.focus();
      // Only the pointer names a place; the pencil and a recovered draft leave the
      // caret where focus put it, at the start of the text. The range was measured
      // in the body's text, so it names a word only in a box holding that text — a
      // resumed edit opens with different words at those offsets.
      if (at && ta.value === effective) ta.setSelectionRange(at[0], at[1]);
    }

    #close(discard) {
      if (!this.#ta) return;
      if (discard) clearEdit(this.id);
      // Only where the reader was standing in it. A close this tab's own gesture made
      // has focus in the box that is going, and the draft's one persistent control is
      // where it lands so a keyboard user isn't dropped back at the page top; a close
      // another tab's settlement brings takes focus from wherever they actually are.
      const stood =
        this.contains(document.activeElement) ||
        this.#margin?.contains(document.activeElement);
      this.#ta.remove();
      this.#ta = null;
      this.#failed = false;
      this.#refreshMargin({
        immediate: stood,
        focus: stood ? "edit" : null,
      });
      // Replay may have been held by this editor. Its close is the generic projection
      // invalidation that lets the state feed retry the complete reading now.
      this.#resumeProjection?.();
      this.#resumeProjection = null;
    }

    async #commit() {
      if (!this.#ta || this.#sending) return;
      if (!this.#available()) return;
      const text = this.#ta.value;
      if (text === this.#controller.read().state.body.value) {
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
      this.#refreshMargin();
      this.#renderHistory(this.#controller.read());
      if (ok) {
        notice(`Edited “${this.id}” — sent`);
      } else {
        const standing = loadEdit(this.id);
        // Null means the same shared generation was settled by the other tab while
        // this one waited to send. Its action will replay this body, so do
        // not resurrect the editor as if a network failure had occurred. A standing
        // generation is either the failed send itself or newer shared text; both stay
        // editable. The outbox has already projected the authoritative body before
        // resolving this call, so opening the saved generation must not overwrite it
        // with the stale pre-send snapshot.
        if (standing !== null) {
          this.#failed = true;
          this.#open(standing);
        }
      }
    }

    // A live editor owns its transient text; the complete state waits for it.
    renderState(state) {
      if (this.#body.textContent !== state.body.value)
        this.#body.textContent = state.body.value;
    }
  },
);
