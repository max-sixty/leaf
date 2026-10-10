/* One explicitly bound UTF-8 file. Its authoritative bytes live on disk, outside
 * Leaf's event log; this owner keeps only the editing buffer, acknowledged file
 * revision and recoverable tab-local draft. CodeMirror owns editing mechanics.
 *
 * Autosave serializes snapshots, retaining later typing while each receipt adopts
 * exactly the submitted snapshot. A clean editor follows external revisions through
 * CodeMirror transactions; a dirty one retains both versions for explicit review.
 * Ordinary writes have no status transition. A write pending for one second earns a
 * quiet, fixed status slot until the newest buffer is acknowledged. Failures and
 * conflicts remain visible. Connection lifetime pauses polling and listeners while
 * retaining the editor, its history and an in-flight write's receipt.
 */
import {
  afterPresentation,
  boundFile,
  focusDestination,
  focused,
  keeps,
  keepsHidden,
  keepsText,
  offer,
  once,
  shadowStage,
  tabStore,
  watchOwner,
  widgetController,
} from "/runtime/widget-api.js";
import { createEditor } from "./editor.js";

customElements.define(
  "lf-file",
  class extends HTMLElement {
    connectedCallback() {
      if (!once(this)) return;
      this.initialize();
    }

    initialize() {
      const api = boundFile(this.getAttribute("binding"));
      const recoveryKey = `file:${this.id}:${this.getAttribute("binding")}`;
      const head = offer("div", "lf-file-head");
      const title = offer("span", "lf-file-name", this.getAttribute("binding"));
      const status = offer("span", "lf-file-status");
      status.setAttribute("aria-hidden", "true");
      const announcement = offer("span", "lf-file-announcement");
      announcement.setAttribute("role", "status");
      announcement.setAttribute("aria-live", "polite");
      const problem = offer("div", "lf-file-problem");
      const explanation = offer("p", "lf-file-explanation");
      explanation.setAttribute("role", "alert");
      const legend = offer(
        "p",
        "lf-file-legend",
        "Removed text is on disk. Added text is your draft.",
      );
      const actions = offer("div", "lf-file-actions");
      const action = (label, run) => {
        const button = offer("button", "button", label);
        button.type = "button";
        button.addEventListener("click", () => {
          if (!busy) run();
        });
        return button;
      };
      const useFile = action("Use file version", () => {
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
      });
      const keepDraft = action("Save my version", async () => {
        await flush(true, keepDraft);
      });
      const retry = action("Retry", async () => {
        const operation = failure;
        if (operation?.kind === "save") await flush(operation.replace, retry);
        else await refresh(retry);
      });
      actions.append(useFile, keepDraft, retry);
      const comparisonMount = offer("div", "lf-file-comparison");
      problem.append(explanation, legend, actions, comparisonMount);
      head.append(title, status);
      const mount = offer("div", "lf-file-edit");
      shadowStage(this, [head, mount, problem, announcement]);
      this.replaceChildren();
      let base = null,
        latest = null,
        failure = null,
        busy = false,
        comparison = null;
      let generation = 0,
        timer = null,
        poll = null,
        slowTimer = null;
      let recovering = false,
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
        keepsText(
          announcement,
          !failure && !latest && !dirty() ? "Changes saved." : "",
        );
      }
      function paint() {
        const label = base?.label ?? thisBinding;
        keepsText(title, label);
        editor.setLabel(label);
        editor.readOnly = base === null || !api.writable;
        keepsText(
          status,
          failure
            ? base
              ? "Not saved"
              : "Unavailable"
            : latest
              ? "Needs review"
              : slow
                ? "Saving changes…"
                : "",
        );
        keepsHidden(problem, !latest && !failure);
        keepsText(
          explanation,
          failure
            ? `${failure.message}${base && dirty() ? " Your draft is kept." : ""}`
            : latest
              ? "The file changed on disk. Use the file version to discard your draft, or save your draft over the version shown below."
              : "",
        );
        keepsHidden(legend, !latest);
        keepsHidden(useFile, !latest);
        keepsHidden(keepDraft, !latest);
        keepsHidden(retry, !failure || !api.writable);
        for (const button of [useFile, keepDraft, retry])
          keeps(button, "aria-disabled", busy ? "true" : null);
        keepsHidden(comparisonMount, !latest);
        if (latest) {
          if (!comparison)
            comparison = createEditor(comparisonMount, {
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
        if (!slow && slowTimer === null)
          slowTimer = setTimeout(() => {
            slow = true;
            slowTimer = null;
            keepsText(announcement, "Saving changes.");
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
          } else failure = { kind: "save", message: fault.message, replace };
        } finally {
          busy = false;
          if (connected) remember();
          if (!dirty() || failure || latest || !connected) finishSaving();
          else if (!slow) {
            clearTimeout(slowTimer);
            slowTimer = null;
          }
          const returning =
            connected && returnFrom && focused() === returnFrom && !failure && !latest;
          paint();
          if (returning) focusDestination(editor.contentDOM, "return");
          schedule(0);
        }
      }
      async function refresh(returnFrom = null) {
        if (!connected || busy || (failure && !returnFrom)) return;
        busy = true;
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
          const returning =
            connected && returnFrom && focused() === returnFrom && !failure && !latest;
          paint();
          if (returning) focusDestination(editor.contentDOM, "return");
          schedule(0);
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
          afterPresentation(() => {
            if (connected && poll === null)
              poll = setInterval(() => {
                if (!document.hidden) void refresh();
              }, 2000);
          });
        },
        disconnect: () => {
          connected = false;
          window.clearInterval(poll);
          poll = null;
          clearTimeout(timer);
          finishSaving();
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
