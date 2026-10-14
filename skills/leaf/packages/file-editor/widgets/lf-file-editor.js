/* One explicitly bound UTF-8 file. Its authoritative bytes live on disk, outside
 * Leaf's event log; this owner keeps only the editing buffer, acknowledged file
 * revision and recoverable tab-local draft. CodeMirror owns editing mechanics.
 *
 * The draft is tab-local because the file on disk is what tabs share: every tab
 * autosaves to it within half a second, and a copy shared across tabs would set two
 * live buffers against one file with no log to settle between them. The draft only
 * has to survive this tab's reloads, including the forced one when Leaf's layer
 * changes, which is what lets the editor say the draft is kept.
 *
 * Autosave serializes snapshots, retaining later typing while each receipt adopts
 * exactly the submitted snapshot. A clean editor follows external revisions through
 * CodeMirror transactions; a dirty one retains both versions for explicit review.
 * The editor reads the file when it connects, when the tab is shown again, and when
 * the page's state stamps the binding anew (`boundFile().watch`). A read asked for
 * while another request is in flight, or while a failure or conflict holds the
 * editor, stays owed until a later read or save covers it.
 * Ordinary writes have no status transition. A write pending for one second earns a
 * quiet word in the header's fixed status slot until the newest buffer is
 * acknowledged. A failure and a conflict stand in that same slot, so the editor's top
 * and height measure the same in every state (`assets/AGENTS.md`, "Stability"). A
 * failure reads "Not saved · Retry", with the error as the status's tooltip and
 * Retry's description. A conflict reads "Changed on disk" in the warning tone, one
 * control opening a small menu of its choices: Compare, Save draft, Use file version.
 * A Save draft that fails keeps that control, since Save draft is the retry and the
 * other choices still stand; it then reads "Not saved", the slot's one line having
 * no room for both, with the error as its description. Where no file
 * could be read at all, the status reads "Unavailable" and the empty editor shows
 * why, as its placeholder.
 * The comparison of both versions opens below the editor only on the reader's
 * Compare, and shares the editing room with it. Rejected (2026-10-14): a pane below
 * the editor holding the error, the choices and the comparison, which took the
 * editor's room as each problem arrived, and room held empty for that pane, which
 * every reader would pay for the rare one who meets a conflict. Each failure and
 * conflict is announced once as it arrives. The compared disk version stays fixed for
 * the reader's choice; saving the draft checks that revision again. Connection
 * lifetime pauses the file watch and listeners while retaining the editor, its
 * history and in-flight receipt.
 */
import {
  allButCommandReference,
  announce,
  boundFile,
  closeLayer,
  closeNativeLayer,
  commandsOn,
  focusDestination,
  focused,
  handBack,
  html,
  iconTemplate,
  isNativeLayer,
  LeafElement,
  nothing,
  offer,
  offered,
  rove,
  rowWalk,
  shadowStage,
  tabStore,
  whileConnected,
} from "/runtime/widget-api.js";
import { createEditor } from "./editor.js";

customElements.define(
  "lf-file-editor",
  class extends LeafElement {
    #placeSelection = null;
    #view = null;
    #template = null;
    #drawn = null;

    setup() {
      this.initialize();
    }

    createRenderRoot() {
      return this.#view;
    }

    render() {
      return this.#template?.() ?? nothing;
    }

    // What follows a draw runs outside the render, since configuring CodeMirror can
    // report a change that draws again.
    updated(changed) {
      super.updated(changed);
      this.#drawn?.();
    }

    // A move keeps the views and the user's focus in one, since their connection
    // lifetime follows the arrival batch (`whileConnected`), but `moveBefore` collapses
    // the native selection, which CodeMirror would read back as a caret at the start.
    connectedMoveCallback() {
      this.#placeSelection?.();
    }

    initialize() {
      const api = boundFile(this.getAttribute("binding"));
      const recoveryKey = `file:${this.id}:${this.getAttribute("binding")}`;
      // The host's grid gives the comparison half the editing room while it is open.
      const internals = this.attachInternals();
      // Stage one retained owner: Lit's markers belong inside it, and CodeMirror's
      // mounts are persistent node values within the template.
      const element = this;
      const view = (this.#view = offer("div", "lf-file-editor-view"));
      const mount = offer("div", "lf-file-editor-edit");
      const comparisonMount = offer("div", "lf-file-editor-comparison");
      view.append(mount);
      shadowStage(this, [view]);
      this.replaceChildren();
      const useFile = () => {
        if (busy || !latest) return;
        base = latest;
        latest = null;
        failure = null;
        recovering = false;
        editor.value = base.text;
        remember();
        finishSaving();
        paint();
        returnToEditor();
        if (owed) void refresh();
      };
      // The status control naming the conflict, and the menu of its choices. A choice
      // and Escape put the menu away onto that control, so a save that settles the
      // conflict returns the reader from it to the editor. A press away from the menu
      // leaves them where they pressed.
      const conflictControl = () => view.querySelector(".lf-file-editor-conflict");
      const choices = () => view.querySelector(".lf-file-editor-choices");
      const choiceRows = () => [...choices().querySelectorAll("button")];
      const putChoicesAway = () =>
        closeLayer(
          () => closeNativeLayer(choices()),
          () => handBack(conflictControl()),
        );
      const choose = (run) => () => {
        putChoicesAway();
        run();
      };
      const compare = choose(() => {
        comparing = !comparing;
        paint();
      });
      const keepDraft = choose(() => void flush(true, conflictControl()));
      const choiceOpened = (event) => {
        if (event.newState !== "open") return;
        const [first] = choiceRows();
        rove(choiceRows(), first);
        focusDestination(first, "move");
      };
      const choiceKeys = [
        ...rowWalk({
          id: "file.choice",
          noun: "Choice",
          plural: "choices",
          rows: choiceRows,
          // A menu names its rows' places to a screen reader itself.
          position: () => null,
          landed: (row) => rove(choiceRows(), row),
        }),
        {
          id: "file.choice.close",
          keys: ["Escape"],
          title: "close",
          run: putChoicesAway,
        },
        // Tab leaves the menu as it leaves a menu button's menu: the menu goes, and the
        // browser moves the reader on from the control that opened it, either way.
        ...["Tab", "Shift+Tab"].map((key) => ({
          id: `file.choice.leave-${key === "Tab" ? "forward" : "backward"}`,
          keys: [key],
          title: key === "Tab" ? "leave forward" : "leave backward",
          native: true,
          run: putChoicesAway,
        })),
      ];
      const retry = (event) => {
        if (busy) return;
        const operation = failure;
        if (operation?.kind === "save")
          void flush(operation.replace, event.currentTarget);
        else void refresh(event.currentTarget);
      };
      let base = null,
        latest = null,
        failure = null,
        busy = false,
        comparing = false,
        comparison = null,
        spoken = null;
      let generation = 0,
        timer = null,
        slowTimer = null;
      let recovering = false,
        owed = false,
        connected = false,
        slow = false;
      const editor = createEditor(mount, {
        readOnly: true,
        onChange() {
          generation++;
          remember();
          paint();
          schedule();
        },
        onSave() {
          clearTimeout(timer);
          void flush();
        },
      });
      // Landing the reader back in the editor shows them where they type.
      const returnToEditor = () => {
        focusDestination(editor.contentDOM, "return");
        editor.revealCaret();
      };
      const dirty = () => base !== null && editor.value !== base.text;
      const unsettled = () => dirty() || latest !== null;
      function remember() {
        tabStore.set(
          recoveryKey,
          base && unsettled() ? JSON.stringify({ base, text: editor.value }) : null,
        );
      }
      function finishSaving() {
        clearTimeout(slowTimer);
        slowTimer = null;
        if (!slow) return;
        slow = false;
        if (!failure && !latest && !dirty()) announce("Changes saved.");
      }
      // A paint draws now, since what follows it reads the controls it drew.
      function paint() {
        // The comparison belongs to the conflict it opened on.
        if (!latest) comparing = false;
        element.requestUpdate();
        element.performUpdate();
      }
      // What follows each draw: the editor's own state, the host's, the menu, the news
      // and the comparison's editor, all of which read the controls the draw made.
      this.#drawn = () => {
        const label = base?.label ?? thisBinding;
        editor.setLabel(label);
        editor.readOnly = base === null || !api.writable;
        // With no file to show, as on an export or an unbound page, the empty editor
        // says why, where a finger and the eye already are.
        editor.placeholder = base === null ? (failure?.message ?? "") : "";
        if (comparing) internals.states.add("comparing");
        else internals.states.delete("comparing");
        if (!latest && isNativeLayer(choices())) closeNativeLayer(choices());
        // Each failure and conflict is news once, as it arrives; the status shows it.
        const news = failure ?? latest;
        if (news && news !== spoken)
          announce(
            failure
              ? `${failure.message}${base && dirty() ? " The draft is kept." : ""}`
              : "The file changed on disk. The draft is kept.",
          );
        spoken = news;
        if (comparing) {
          if (!comparison)
            comparison = createEditor(comparisonMount, {
              text: editor.value,
              filename: label,
              original: latest.text,
              readOnly: true,
              label: "Compare versions",
              description:
                "Read only. Removed text is on disk. Added text is the draft.",
            });
          comparison.value = editor.value;
          comparison.setLabel(label);
          comparison.setConflict(latest.text);
        } else if (comparison) {
          comparison.disconnect();
          comparison = null;
        }
      };
      this.#template = () => {
        const label = base?.label ?? thisBinding;
        // A conflict keeps its choices through a failed Save draft, which is its own
        // retry; the failure then describes the control rather than taking its place.
        const conflicted = Boolean(latest);
        const retryable = Boolean(failure) && !latest && api.writable;
        return html`
          <div ${offered("lf-file-editor-head")}>
            <span ${offered("lf-file-editor-name")}>${label}</span>
            <span
              ${offered("lf-file-editor-status")}
              title=${failure?.message ?? nothing}
              >${
                latest
                  ? ""
                  : failure
                    ? base
                      ? "Not saved"
                      : "Unavailable"
                    : slow
                      ? "Saving changes…"
                      : ""
              }${retryable ? html`<span aria-hidden="true">&nbsp;·&nbsp;</span>` : nothing}<button
                ${offered("lf-file-editor-retry")}
                ?hidden=${!retryable}
                aria-description=${failure?.message ?? nothing}
                aria-disabled=${busy ? "true" : nothing}
                @click=${retry}
              >
                Retry</button
              ><button
                ${offered("lf-file-editor-conflict")}
                ?hidden=${!conflicted}
                aria-description=${failure?.message ?? nothing}
                popovertarget="lf-file-editor-choices"
                aria-haspopup="menu"
              >
                ${failure ? "Not saved" : "Changed on disk"}${iconTemplate(
                  "down",
                  "lf-file-editor-chevron",
                )}
              </button></span
            >
          </div>
          <div
            ${offered("lf-file-editor-choices")}
            id="lf-file-editor-choices"
            popover="auto"
            role="menu"
            aria-label="The file changed on disk"
            @toggle=${choiceOpened}
            ${commandsOn("In the file's conflict menu", choiceKeys, {
              claims: allButCommandReference,
            })}
          >
            <button
              ${offered("lf-btn")}
              role="menuitemcheckbox"
              aria-checked=${String(comparing)}
              aria-controls="lf-file-editor-compared"
              @click=${compare}
            >
              Compare
            </button>
            ${[
              ["Save draft", keepDraft],
              ["Use file version", choose(useFile)],
            ].map(
              ([label, run]) => html`
                <button
                  ${offered("lf-btn")}
                  role="menuitem"
                  aria-disabled=${busy ? "true" : nothing}
                  @click=${run}
                >
                  ${label}
                </button>
              `,
            )}
          </div>
          ${mount}
          <div
            ${offered("lf-file-editor-compared")}
            id="lf-file-editor-compared"
            ?hidden=${!comparing}
          >
            <p ${offered("lf-file-editor-legend")}>
              Removed text is on disk. Added text is the draft.
            </p>
            ${comparing ? comparisonMount : nothing}
          </div>
        `;
      };
      const thisBinding = this.getAttribute("binding");
      function schedule(delay = 500) {
        clearTimeout(timer);
        if (connected && api.writable && !latest && !failure && dirty())
          timer = setTimeout(() => void flush(), delay);
      }
      async function flush(replace = false, returnFrom = null) {
        clearTimeout(timer);
        if (
          !connected ||
          !api.writable ||
          busy ||
          !base ||
          (failure && !returnFrom) ||
          (latest && !replace) ||
          (!dirty() && !(replace && latest))
        )
          return;
        const against = replace ? latest : base;
        const text = editor.value;
        busy = true;
        // The host compares the file before writing, so a receipt or a stale answer
        // covers any read owed before it starts; a failure read nothing.
        const owedBefore = owed;
        owed = false;
        if (!slow && slowTimer === null)
          slowTimer = setTimeout(() => {
            slow = true;
            slowTimer = null;
            announce("Saving changes.");
            paint();
          }, 1000);
        paint();
        try {
          base = await api.save({ revision: against.revision, text });
          latest = null;
          failure = null;
        } catch (fault) {
          if (fault.current) {
            latest = fault.current;
            failure = null;
          } else {
            failure = { kind: "save", message: fault.message, replace };
            owed ||= owedBefore;
          }
        } finally {
          busy = false;
          if (connected) remember();
          if (!dirty() || failure || latest || !connected) finishSaving();
          else if (!slow) {
            clearTimeout(slowTimer);
            slowTimer = null;
          }
          const returning = connected && returnFrom && focused() === returnFrom;
          paint();
          if (returning && returnFrom.hidden) returnToEditor();
          schedule(0);
          if (owed) void refresh();
        }
      }
      async function refresh(returnFrom = null) {
        if (!connected) return;
        if (busy || ((failure || latest) && !returnFrom)) {
          owed = true;
          return;
        }
        busy = true;
        owed = false;
        const seenGeneration = generation;
        try {
          const current = await api.read();
          if (!base || (!recovering && !unsettled() && seenGeneration === generation)) {
            base = current;
            latest = null;
            editor.value = current.text;
          } else if (current.text === editor.value) {
            base = current;
            latest = null;
          } else latest = current.revision !== base.revision ? current : null;
          recovering = false;
          failure = null;
        } catch (fault) {
          failure = { kind: "read", message: fault.message };
        } finally {
          busy = false;
          if (connected) remember();
          if (failure || latest || !dirty()) finishSaving();
          const returning = connected && returnFrom && focused() === returnFrom;
          paint();
          if (returning && returnFrom.hidden) returnToEditor();
          schedule(0);
          if (owed) void refresh();
        }
      }
      const beforeUnload = (event) => {
        if (unsettled()) {
          event.preventDefault();
          event.returnValue = "";
        }
      };
      const visibility = () => {
        if (document.hidden) void flush();
        else void refresh();
      };
      const pending = tabStore.get(recoveryKey);
      if (pending && api.writable) {
        const recovered = JSON.parse(pending);
        base = recovered.base;
        editor.value = recovered.text;
        recovering = true;
      }
      paint();
      this.#placeSelection = () => {
        editor.placeSelection();
        comparison?.placeSelection();
      };
      let initial = true;
      whileConnected(this, (signal) => {
        connected = true;
        editor.connect();
        comparison?.connect();
        window.addEventListener("beforeunload", beforeUnload, { signal });
        document.addEventListener("visibilitychange", visibility, { signal });
        const ready = refresh();
        if (initial) {
          this.controller.present(ready);
          initial = false;
        }
        const stopWatch = api.watch(() => void refresh());
        return () => {
          connected = false;
          stopWatch();
          clearTimeout(timer);
          finishSaving();
          paint();
          remember();
          editor.disconnect();
          comparison?.disconnect();
        };
      });
    }
  },
);
