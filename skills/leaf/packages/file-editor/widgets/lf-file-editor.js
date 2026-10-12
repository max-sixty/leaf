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
 * quiet, fixed status slot until the newest buffer is acknowledged. Failures and
 * conflicts remain visible. The compared disk version stays fixed for the reader's
 * choice; saving the draft checks that revision again. Connection lifetime pauses
 * the file watch and listeners while retaining the editor, its history and in-flight
 * receipt.
 */
import {
  boundFile,
  focusDestination,
  focused,
  html,
  nothing,
  render,
  repeat,
  offer,
  offered,
  once,
  shadowStage,
  tabStore,
  watchOwner,
  widgetController,
} from "/runtime/widget-api.js";
import { createEditor } from "./editor.js";

customElements.define(
  "lf-file-editor",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      this.initialize();
    }

    initialize() {
      const api = boundFile(this.getAttribute("binding"));
      const recoveryKey = `file:${this.id}:${this.getAttribute("binding")}`;
      // Stage one retained owner: Lit's markers belong inside it, and CodeMirror's
      // mounts are persistent node values within the template.
      const view = offer("div", "lf-file-editor-view");
      const mount = offer("div", "lf-file-editor-edit");
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
        focusDestination(editor.contentDOM, "return");
        if (owed) void refresh();
      };
      const keepDraft = (event) => void flush(true, event.currentTarget);
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
        comparison = null;
      let generation = 0,
        timer = null,
        stopWatch = null,
        slowTimer = null;
      let recovering = false,
        owed = false,
        connected = false,
        slow = false,
        announcement = "";
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
        announcement = !failure && !latest && !dirty() ? "Changes saved." : "";
      }
      function paint() {
        const label = base?.label ?? thisBinding;
        editor.setLabel(label);
        editor.readOnly = base === null || !api.writable;
        render(
          html`
            <div ${offered("lf-file-editor-head")}>
              <span ${offered("lf-file-editor-name")}>${label}</span>
              <span ${offered("lf-file-editor-status")} aria-hidden="true"
                >${
                  failure
                    ? base
                      ? "Not saved"
                      : "Unavailable"
                    : latest
                      ? "Needs review"
                      : slow
                        ? "Saving changes…"
                        : ""
                }</span
              >
            </div>
            ${mount}
            <div ${offered("lf-file-editor-problem")} ?hidden=${!latest && !failure}>
              <p
                ${offered("lf-file-editor-explanation")}
                role="alert"
                .textContent=${
                  failure
                    ? `${failure.message}${base && dirty() ? " Your draft is kept." : ""}`
                    : latest
                      ? "The file changed on disk. Use the file version to discard your draft, or save your draft over the version shown below."
                      : ""
                }
              ></p>
              <p ${offered("lf-file-editor-legend")} ?hidden=${!latest}>
                Removed text is on disk. Added text is your draft.
              </p>
              <div ${offered("lf-file-editor-actions")}>
                ${repeat(
                  [
                    ["Use file version", !latest, useFile],
                    ["Save my version", !latest, keepDraft],
                    ["Retry", !failure || !api.writable, retry],
                  ],
                  ([label]) => label,
                  ([label, hidden, run]) => html`
                    <button
                      type="button"
                      ${offered("button")}
                      ?hidden=${hidden}
                      aria-disabled=${busy ? "true" : nothing}
                      @click=${run}
                    >
                      ${label}
                    </button>
                  `,
                )}
              </div>
              <div ${offered("lf-file-editor-comparison")} ?hidden=${!latest}></div>
            </div>
            <span
              ${offered("lf-file-editor-announcement")}
              role="status"
              aria-live="polite"
              >${announcement}</span
            >
          `,
          view,
        );
        const comparisonMount = view.querySelector(".lf-file-editor-comparison");
        if (latest) {
          if (!comparison)
            comparison = createEditor(comparisonMount, {
              text: editor.value,
              filename: label,
              original: latest.text,
              readOnly: true,
              label: "Compare versions",
              description:
                "Read only. Removed text is on disk. Added text is your draft.",
            });
          comparison.value = editor.value;
          comparison.setLabel(label);
          comparison.setConflict(latest.text);
        } else if (comparison) {
          comparison.disconnect();
          comparison = null;
        }
      }
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
            announcement = "Saving changes.";
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
          if (returning && returnFrom.hidden)
            focusDestination(editor.contentDOM, "return");
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
          if (returning && returnFrom.hidden)
            focusDestination(editor.contentDOM, "return");
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
      let initial = true;
      watchOwner(this, {
        connect: () => {
          connected = true;
          editor.connect();
          comparison?.connect();
          window.addEventListener("beforeunload", beforeUnload);
          document.addEventListener("visibilitychange", visibility);
          const ready = refresh();
          if (initial) {
            widgetController(this).present(ready);
            initial = false;
          }
          stopWatch = api.watch(() => void refresh());
        },
        disconnect: () => {
          connected = false;
          stopWatch();
          stopWatch = null;
          clearTimeout(timer);
          finishSaving();
          paint();
          window.removeEventListener("beforeunload", beforeUnload);
          document.removeEventListener("visibilitychange", visibility);
          remember();
          editor.disconnect();
          comparison?.disconnect();
        },
      });
    }
  },
);
