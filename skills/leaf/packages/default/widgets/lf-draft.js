/* lf-draft: one Markdown source, read as prose and edited in place.
 *
 * The body record and edit log hold the complete source. The shared declared-format
 * renderer supplies safe Markdown in the light DOM, where comments and revision
 * comparison can read it. The editor opens that source unchanged and carries a
 * clicked caret through the shared source/visible alignment. Links and selections
 * keep their native gestures. Quoted drafts are read-only exhibits.
 *
 * Editing controls belong to the box, in a persistent local footer. The same
 * command declarations own pointer activation, keyboard routes, availability and
 * accessible shortcut hints. Visual shortcuts belong to the shared shortcut bar. Comments and workflow receipts keep their own
 * annotation layer; hiding annotations cannot hide the editor's controls.
 * History shares the footer only when edits exist and the editor is closed.
 * It draws the controller's published reading; local control changes retain that
 * reading until the next publication, including while an editor defers replay.
 *
 * The shared draft store retains unsent source across reloads and tabs. Save
 * submits one absolute edit through the shared send generation; Cancel discards,
 * while Close/Escape keeps the draft. An active editor defers authoritative
 * projection until it closes. Another tab's settlement closes its matching
 * editor without taking focus from an unrelated place. Failure reopens the
 * retained source with Retry. Print keeps the saved reading and omits controls.
 */
import {
  commandScope,
  DISCLOSE,
  holdFocus,
  html,
  render,
  repeat,
  offered,
  nothing,
  guard,
  once,
  offer,
  TEXT_FIELD,
  paintKeys,
  quoted,
  revisionLabel,
  sendDraft,
  notice,
  commands,
  saveDraft,
  loadDraft,
  clearDraft,
  watchDraft,
  whileConnected,
  alignText,
  alignedNodes,
  widgetController,
  reachedForWords,
  paintMarkdown,
  markdownSourceOffset,
  markdownWords,
  focusDestination,
  nextRender,
  retainUserIntent,
  scrollIntoView,
} from "/runtime/widget-api.js";

const ACTIONS = [
  ["edit", "Edit"],
  ["save", "Save"],
  ["cancel", "Cancel", "Cancel — discard the unsent edit"],
  ["close", "Close", "Close — keep the unsent edit"],
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
  class extends HTMLElement {
    // What the Question was answered with: the standing words.
    static answerWords(value) {
      return markdownWords(value).trim() || "Empty";
    }

    #controller = widgetController(this);
    #body;
    #reading = null;
    #historySummary = null;
    #editor = null;
    #sending = false;
    #failed = false;
    #footer = null;
    #commandScope = null;
    #resumeProjection = null;
    #recovered = false;

    connectedCallback() {
      if (!once(this)) return;

      this.#body = this.querySelector(":scope > .lf-markdown-body");
      if (this.childNodes.length !== 1 || this.firstChild !== this.#body)
        this.replaceChildren(this.#body);
      this.#body.className = "lf-draft-body lf-markdown-body"; // NOT .lf-ui: anchoring and Δ must see this

      // A quoted draft is an exhibit: the same formatted text, none of the doors —
      // no controls, box press or editing shortcuts. Quoting
      // gates the action channel, not presentation.
      if (quoted(this)) {
        this.#subscribeReading();
        return;
      }

      this.#offerControls();

      this.#subscribeReading();

      // A click opens the exact source at its rendered caret. Native controls,
      // links and completed word selections own their own gestures.
      this.addEventListener("click", (ev) => {
        // A keyboard activation carries no place, and the keyboard's door is the ✎. The
        // primary button only: a middle- or right-press is not the gesture this is for.
        if (
          ev.detail === 0 ||
          ev.button !== 0 ||
          ev.target.closest("[data-lf-offer], a, button")
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
          this.#controller.read().actions.edit.available
        )
          this.#resumeProjection = this.#controller.defer();
        return () => {
          stopDraft?.();
          this.#resumeProjection?.();
          this.#resumeProjection = null;
        };
      });
    }

    #subscribeReading() {
      const interactive = !quoted(this);
      this.#controller.subscribe((reading) => {
        if (!interactive) return;
        this.#reading = reading;
        // Recovery chooses the first action face: an unsent editor opens with Save
        // and Cancel, without briefly publishing the resting Edit control.
        this.#recoverEdit(reading);
        this.#paintAvailability();
        if (this.#editor && !this.#resumeProjection && reading.actions.edit.available)
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
      // An edit coming back is not the user arriving, though, so the box does not take
      // the focus. A revision that rewrote this draft connects it again while the user
      // stands somewhere else, and news with no gesture behind it moves nobody — the same
      // reason `#watchDraft` leaves a closed box closed. On a page that has just loaded,
      // startup hands the focus to the page after this runs either way.
      const pending = loadEdit(this.id);
      const authored = reading.authored.edit.value;
      if (pending !== null && pending !== authored)
        this.#open(pending, undefined, false);
      else if (pending === authored) clearEdit(this.id);
    }

    #watchDraft() {
      if (quoted(this) || !this.#footer) return;
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
      if (quoted(this) || this.#footer) return;
      this.#footer = offer("div", "lf-draft-footer");
      this.append(this.#footer);
      this.#paintFooter();
      this.#ensureCommands();
    }

    #ensureCommands() {
      if (this.#commandScope) return;
      this.#commandScope = commandScope("On a draft", [
        {
          id: "draft.edit",
          contextKeys: ["1"],
          keys: [],
          control: () => this.#control("edit"),
          decision: true,
          title: "Edit",
          description: "Edit the text in place",
          when: () => !this.#editor && !this.#sending && this.#available(),
          run: () => this.#open(),
        },
        {
          id: "draft.save",
          contextKeys: ["1"],
          reach: "in an open draft editor",
          keys: ["Mod+Enter"],
          control: () => this.#control("save"),
          decision: true,
          title: () => (this.#failed ? "Retry" : "Save"),
          description: () => (this.#failed ? "Retry saving the edit" : "Save the edit"),
          when: () => Boolean(this.#editor) && !this.#sending && this.#available(),
          run: () => this.#commit(),
        },
        {
          id: "draft.cancel",
          contextKeys: ["2"],
          reach: "in an open draft editor",
          keys: [],
          control: () => this.#control("cancel"),
          decision: true,
          title: "Cancel",
          description: "Cancel the edit",
          when: () => Boolean(this.#editor),
          run: () => this.#close(true),
        },
        {
          id: "draft.close",
          reach: "in an open draft editor",
          keys: ["Escape"],
          control: () => this.#control("close"),
          title: "Close — edit kept",
          when: () => Boolean(this.#editor),
          run: () => this.#close(false),
        },
      ]);
      commands(this, this.#commandScope);
    }

    #control(key) {
      return this.#footer?.querySelector(`[data-lf-draft-action="${key}"]`) ?? null;
    }

    #paintFooter() {
      if (!this.#footer) return;
      const editing = Boolean(this.#editor);
      const blocked = !this.#available();
      // A restore control disappears when its text becomes the standing text.
      // Surviving controls keep native focus; that completed action returns to history.
      const history = this.#historySummary?.parentElement;
      const restore = history && holdFocus(history);
      render(
        html`${this.#historyView(this.#reading, editing, blocked)}
          <span ${offered("lf-draft-status")} role="status"
            >${this.#failed ? "Save failed. Your edit is kept." : ""}</span
          >
          <div ${offered("lf-draft-tools")}>
            ${ACTIONS.map(
              ([key, title, hint]) =>
                html`<button
                  ${offered("lf-btn lf-draft-action")}
                  data-lf-draft-action=${key}
                  title=${hint ?? nothing}
                  ?hidden=${key === "edit" ? editing : !editing}
                  aria-expanded=${key === "edit" ? String(editing) : nothing}
                >
                  ${key === "save" && this.#failed ? "Retry" : title}
                </button>`,
            )}
          </div>`,
        this.#footer,
      );
      this.#declareHistoryKeys();
      restore?.(this.#historySummary);
      paintKeys();
    }

    #paintAvailability = () => {
      if (this.#editor) this.#editor.readOnly = !this.#available();
      this.#paintFooter();
    };

    #available() {
      return Boolean(this.#controller.read().actions.edit?.available);
    }

    #dispatch(text, attempt) {
      return this.#controller.dispatch({
        kind: "action",
        verb: "edit",
        detail: { value: text },
        ...(attempt && { attempt }),
      });
    }

    #historyView(reading, editing, blocked) {
      if (!reading) return nothing;
      const authored = reading.authored.edit.value;
      const standing = reading.state.edit.value;
      const actions = reading.actions.edit.history;
      if (!actions.length && standing === authored) return nothing;
      const rows = [
        { key: "authored", label: "Version text", text: authored, before: null },
        ...actions.map((event, index) => ({
          key: event.seq,
          label: `Edit ${index + 1} · ${revisionLabel(event.revision)}`,
          text: event.detail.value,
          before: index ? actions[index - 1].detail.value : null,
        })),
      ];
      return html`<details ${offered("lf-draft-history")} ?hidden=${editing}>
        <summary>
          Changes · ${actions.length} ${actions.length === 1 ? "edit" : "edits"}
        </summary>
        <section class="lf-draft-current">
          <strong>
            ${
              standing === authored
                ? "Standing text matches this version"
                : "This version → standing text"
            }
          </strong>
          ${standing === authored ? nothing : this.#delta(authored, standing)}
        </section>
        <ol class="lf-draft-revisions">
          ${repeat(
            rows,
            (row) => row.key,
            (row) =>
              html`<li>
                <div class="lf-draft-revision-head">
                  <strong>${row.label}</strong>
                  ${
                    row.text === standing
                      ? nothing
                      : html`<button
                          ${offered("lf-btn lf-draft-restore")}
                          aria-disabled=${String(blocked)}
                          tabindex=${blocked ? -1 : 0}
                          @click=${() => this.#restore(row.text, row.label)}
                        >
                          Restore ${row.label.toLowerCase()}
                        </button>`
                  }
                </div>
                ${
                  row.before === null
                    ? html`<div class="lf-draft-snapshot">${row.text || "Empty"}</div>`
                    : this.#delta(row.before, row.text)
                }
              </li>`,
          )}
        </ol>
      </details>`;
    }

    // The aligned run is computed once per pair; guard keeps its nodes across renders.
    #delta(before, after) {
      const content = guard([before, after], () => {
        const nodes = alignedNodes(alignText(before, after));
        return nodes.length ? nodes : "Empty";
      });
      return html`<div class="lf-draft-delta">${content}</div>`;
    }

    // The summary is a stable node now; its disclosure line is declared once per node.
    #declareHistoryKeys() {
      const summary = this.#footer.querySelector(":scope > details > summary");
      if (!summary || summary === this.#historySummary) return;
      this.#historySummary = summary;
      commands(summary, "On a draft", [
        {
          id: "draft.history.toggle",
          keys: () => DISCLOSE(summary),
          title: () => `${summary.parentElement.open ? "hide" : "show"} the history`,
        },
      ]);
    }

    async #restore(text, label) {
      if (!this.#available()) return;
      if (this.#sending) {
        notice("Wait for the current edit to finish sending");
        return;
      }
      if (this.#editor) {
        notice("Save or cancel the open edit before restoring history");
        return;
      }
      if (text === this.#controller.read().state.edit.value) return;
      this.#sending = true;
      this.setAttribute("aria-busy", "true");
      this.#paintFooter();
      const ok = await this.#dispatch(text)?.delivery;
      this.#sending = false;
      this.removeAttribute("aria-busy");
      this.#paintFooter();
      if (ok) notice(`Restored ${label.toLowerCase()} — sent`);
    }

    #open(seed, at, arrive = true) {
      if (this.#editor) return;
      if (this.#sending) {
        notice("Wait for the current edit to finish sending");
        return;
      }
      if (this.#available()) this.#resumeProjection ??= this.#controller.defer();
      const editor = offer(TEXT_FIELD, "lf-draft-edit");
      // A set-aside edit outranks the authored text here too: reopening resumes it.
      const effective = this.#controller.read().state.edit.value;
      editor.value = seed ?? loadEdit(this.id) ?? effective;
      editor.setAttribute("aria-label", `Edit ${this.id}`);
      editor.addEventListener("input", () => {
        saveEdit(this.id, editor.value);
        if (this.#failed) {
          this.#failed = false;
          this.#paintFooter();
        }
      });
      // The composer's bindings on the box that replaces the page's own words. Escape sets
      // the edit aside rather than discarding it (never lose user text: Cancel is the only
      // discard) — and being the innermost scope's is what keeps the runtime's own rung
      // from running behind it and closing the panel too, which the widget used to have to
      // prevent by consuming the press.
      this.#editor = editor;
      commands(editor, this.#commandScope);
      this.#body.after(editor);
      this.#paintAvailability();
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
      if (discard) clearEdit(this.id);
      // Only where the user was standing in it. A close this tab's own gesture made
      // has focus in the box that is going, and the draft's one persistent control is
      // where it lands so a keyboard user isn't dropped back at the page top; a close
      // another tab's settlement brings takes focus from wherever they actually are.
      const left = document.activeElement;
      const stood = this.contains(left);
      const mayReturn = retainUserIntent({ source: left });
      this.#editor.remove();
      this.#editor = null;
      this.#failed = false;
      this.#paintFooter();
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
      if (text === this.#controller.read().state.edit.value) {
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
      this.#paintFooter();
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
      paintMarkdown(this.#body, state.edit.value);
    }
  },
);
