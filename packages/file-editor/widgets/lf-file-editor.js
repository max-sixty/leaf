/* The explicitly bound UTF-8 files `binding` names, one open at a time. Their
 * authoritative bytes live on disk, outside Leaf's event log; this owner keeps only
 * each file's editing buffer, acknowledged file revision and recoverable tab-local
 * draft. CodeMirror owns editing mechanics.
 *
 * The draft is tab-local because the file on disk is what tabs share: every tab
 * autosaves to it within half a second, and a copy shared across tabs would set two
 * live buffers against one file with no log to settle between them. The draft only
 * has to survive this tab's reloads, including the forced one when Leaf's layer
 * changes, which is what lets the editor say the draft is kept.
 *
 * The editor publishes its files as a `files` output, each named by the label the
 * page's server gives it and keyed by its binding, with the open one `current`, so a
 * navigator beside it lists them. A reveal of a binding (`navigateToDatum`, a link to
 * `#<editor>:<binding>`) opens that file. Which file is open is how this tab looks at
 * the files, not a change to them, so it enters no log; a reload opens the one its
 * address names, else the first. Each file keeps its own text, selection, history and
 * scroll while another is open, and leaving a file saves what it holds at once. A file
 * the reader has left settles its saves as the open one does; a failure or conflict
 * there is announced by the file's name and stands in the status when it is opened.
 *
 * Autosave serializes snapshots, retaining later typing while each receipt adopts
 * exactly the submitted snapshot. A clean editor follows external revisions through
 * CodeMirror transactions. A dirty one takes in an external revision that changed only
 * lines apart from the draft's, as a line merge would, so an agent writing one part of
 * a file while the reader types in another meets no conflict however the two requests
 * interleave; changes to the same or adjacent lines retain both versions for explicit
 * review. Either way the version taken in starts the file's undo history afresh, open
 * or kept (editor.js, `writeFromElsewhere`), and the lines it changed stay marked until
 * the next such version or the reader's edit of them (editor.js, `written`), so a
 * reader whose file an agent edited sees where; a file's first reading marks nothing.
 * The editor takes the open file from the page's state (`boundFile().read`) when it
 * connects, when the reader opens it and when the state carries the binding anew
 * (`boundFile().watch`), so the file is drawn with the page's state and the page
 * presents with it. A state read taken before a save's answer can arrive after it, so
 * a reading older than the version the editor holds (`taken`) is passed over; the
 * save's own news brings a newer one. A reading that arrives while a save is in
 * flight, or while a failed save or a conflict holds the file, stays owed until a
 * later reading or save covers it.
 * Ordinary writes have no status transition. A write pending for one second earns a
 * quiet word in the header's fixed status slot until the newest buffer is
 * acknowledged. A failure and a conflict stand in that same slot, so the editor's top
 * and height measure the same in every state (`browser/AGENTS.md`, "The page holds still under the user's aim"). A
 * failure reads "Not saved" beside Retry, a symbol, with the error as the status's
 * tooltip and Retry's description; a file the server can't read reads "Not saved"
 * without Retry, since the state brings the file back once it can be read. A
 * conflict reads "Changed on disk", an inline press
 * in the warning's tone, opening a small menu of its choices: Compare, Save draft, Use
 * file version.
 * A Save draft that fails keeps that control, since Save draft is the retry and the
 * other choices still stand; it then reads "Not saved", the slot's one line having
 * no room for both, with the error as its description. Where no file
 * could be read at all, the status reads "Unavailable" and the empty editor shows
 * why, as its placeholder.
 * The comparison of both versions opens below the editor only on the reader's
 * Compare, and shares the editing room with it. Rejected: a pane below
 * the editor holding the error, the choices and the comparison, which took the
 * editor's room as each problem arrived, and room held empty for that pane, which
 * every reader would pay for the rare one who meets a conflict. Each failure and
 * conflict is announced once as it arrives. The compared disk version stays fixed for
 * the reader's choice; saving the draft checks that revision again. Connection
 * lifetime pauses the file watch and listeners while retaining the editor, its
 * history and in-flight receipt.
 */
import { html, nothing, render } from "/vendor/lit.js";
import { EditorView } from "/vendor/codemirror.esm.js";
import {
  allButCommandReference,
  announce,
  boundFile,
  describeFailure,
  RequestError,
  closeLayer,
  closeNativeLayer,
  commandsOn,
  el,
  focusDestination,
  focused,
  handBack,
  iconTemplate,
  isNativeLayer,
  LeafElement,
  offered,
  offeredAction,
  onCurrentLocation,
  publishOutput,
  rove,
  rowWalk,
  shadowStage,
  tabStore,
  whileConnected,
} from "/runtime/widget-api.js";
import { createEditor, followKept, mergeKept } from "./editor.js";

/** @typedef {import("../../../browser/types/contract.js").ServedFileSnapshot} FileSnapshot */
/** @typedef {{kind: "read", message: string} | {kind: "save", message: string, replace: boolean}} FileFailure */
/** One bound file as this tab knows it: what the server last acknowledged (`base`), a
 * newer disk version held for the reader's choice (`latest`), and its saves.
 * `kept` is what the editor held of it while another file is open, and `named` the
 * name the editor's `files` output last listed it by.
 * @typedef {{
 *   binding: string, api: ReturnType<typeof boundFile>, recoveryKey: string,
 *   base: FileSnapshot | null, latest: FileSnapshot | null,
 *   failure: FileFailure | null, spoken: FileSnapshot | FileFailure | null,
 *   busy: boolean, comparing: boolean, recovering: boolean, owed: boolean,
 *   slow: boolean, timer: number, slowTimer: number | null,
 *   kept: import("./editor.js").KeptFile | null, named: string | null,
 * }} OpenFile */

customElements.define(
  "lf-file-editor",
  class extends LeafElement {
    /** @type {(() => void) | null} */
    #placeSelection = null;
    #view = el("div", "lf-file-editor-view lf-ui");
    /** @type {(() => import("lit").TemplateResult) | null} */
    #template = null;
    /** @type {(() => void) | null} */
    #drawn = null;
    /** @type {((binding: string, line: number | null) => Promise<void> | null) | null} */
    #open = null;
    /** @type {(() => string | null) | null} */
    #shown = null;
    /** @type {((binding: string) => string | null) | null} */
    #label = null;

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
    /** @param {import("lit").PropertyValues} changed */
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

    // A key names a file this editor can show by its binding, and a line of it as
    // `<binding>:<line>`, as a note's link to `#<editor>:values:12` does: revealing it
    // opens the file with the caret at the start of that line, and the promise
    // settles once the page's state has drawn the file.
    /** @param {string} key */
    lfRevealDatum(key) {
      const [binding = "", line] = key.split(":");
      return this.#open?.(binding, Number(line) || null) ?? null;
    }

    /** @param {string} key */
    lfElementsFor(key) {
      return this.#shown?.() === key.split(":")[0] ? [this] : [];
    }

    /** @param {string} key */
    lfDatumLabel(key) {
      const [binding = "", line] = key.split(":");
      const name = this.#label?.(binding);
      return name && line ? `${name}, line ${line}` : (name ?? null);
    }

    initialize() {
      const bindings = (this.getAttribute("binding") ?? "")
        .split(/\s+/)
        .filter(Boolean);
      if (!bindings.length) throw new Error("file editor needs its binding");
      const element = this;
      /** @type {Map<string, OpenFile>} */
      const files = new Map(
        bindings.map((binding) => [
          binding,
          {
            binding,
            api: boundFile(binding),
            recoveryKey: `file:${this.id}:${binding}`,
            base: null,
            latest: null,
            failure: null,
            spoken: null,
            busy: false,
            comparing: false,
            recovering: false,
            owed: false,
            slow: false,
            timer: 0,
            slowTimer: null,
            kept: null,
            named: null,
          },
        ]),
      );
      const fileFor = (/** @type {string} */ binding) =>
        /** @type {OpenFile} */ (files.get(binding));
      // The file the reader has open.
      let file = fileFor(/** @type {string} */ (bindings[0]));
      const label = (/** @type {OpenFile} */ of) =>
        of.api.label ?? of.base?.label ?? of.binding;
      this.#shown = () => file.binding;
      this.#label = (binding) => (files.has(binding) ? label(fileFor(binding)) : null);
      // The host's grid gives the comparison half the editing room while it is open.
      const internals = this.attachInternals();
      // Stage one retained owner: Lit's markers belong inside it, and CodeMirror's
      // mounts are persistent node values within the template.
      // The stage, the mounts and the comparison hold the file, which prints, so they are
      // plain elements and only the editor's controls are offers. `lf-ui` keeps the
      // file's words out of the page's passages.
      const view = this.#view;
      const mount = el("div", "lf-file-editor-edit");
      const comparisonMount = el("div", "lf-file-editor-comparison");
      shadowStage(this, [view]);
      const useFile = () => {
        const of = file;
        if (of.busy || !of.latest) return;
        of.base = of.latest;
        of.latest = null;
        of.failure = null;
        of.recovering = false;
        editor.value = of.base.text;
        remember(of);
        finishSaving(of);
        paint();
        returnToEditor();
        if (of.owed) refresh(of);
      };
      // The status control naming the conflict, and the menu of its choices. A choice
      // and Escape put the menu away onto that control, so a save that settles the
      // conflict returns the reader from it to the editor. A press away from the menu
      // leaves them where they pressed.
      const conflictControl = () => controls.conflict;
      const choices = () => controls.menu;
      const choiceRows = () => [...choices().querySelectorAll("button")];
      const putChoicesAway = () =>
        closeLayer(
          () => closeNativeLayer(choices()),
          () => handBack(conflictControl()),
        );
      /** @param {() => unknown} run */
      const choose = (run) => () => {
        putChoicesAway();
        run();
      };
      const compare = choose(() => {
        file.comparing = !file.comparing;
        paint();
      });
      const keepDraft = choose(() => void flush(file, true, conflictControl()));
      /** @param {ToggleEvent} event */
      const choiceOpened = (event) => {
        if (event.newState !== "open") return;
        rove(choiceRows(), controls.first);
        focusDestination(controls.first, "move");
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
      /** @param {HTMLElement | null} [returnFrom] */
      const retry = (returnFrom = null) => {
        const of = file;
        const operation = of.failure;
        if (!of.busy && operation?.kind === "save")
          void flush(of, operation.replace, returnFrom);
      };
      /** @type {ReturnType<typeof createEditor> | null} */
      let comparison = null;
      let connected = false;
      // Landing the reader back in the editor shows them where they type.
      const returnToEditor = () => {
        focusDestination(editor.contentDOM, "return");
        editor.revealCaret();
      };
      // A file's text: the editor's while it is open, else what the editor kept of it
      // or, where it kept nothing, the version last read.
      const text = (/** @type {OpenFile} */ of) =>
        of === file
          ? editor.value
          : (of.kept?.state.doc.toString() ?? of.base?.text ?? "");
      const dirty = (/** @type {OpenFile} */ of) =>
        of.base !== null && text(of) !== of.base.text;
      const unsettled = (/** @type {OpenFile} */ of) => dirty(of) || of.latest !== null;
      // A version written elsewhere that changed other lines than the draft did joins
      // the draft, which then stands over that version and saves on its own.
      /** @param {OpenFile} of @param {FileSnapshot} current */
      function settle(of, current) {
        if (!of.base) return false;
        if (of === file) {
          if (!editor.merge(of.base.text, current.text)) return false;
        } else {
          const merged = of.kept && mergeKept(of.kept, of.base.text, current.text);
          if (!merged) return false;
          of.kept = merged;
        }
        of.base = current;
        of.latest = null;
        return true;
      }
      /** @param {OpenFile} of */
      function remember(of) {
        tabStore.set(
          of.recoveryKey,
          of.base && unsettled(of)
            ? JSON.stringify({ base: of.base, text: text(of) })
            : null,
        );
      }
      /** @param {OpenFile} of */
      function finishSaving(of) {
        if (of.slowTimer !== null) clearTimeout(of.slowTimer);
        of.slowTimer = null;
        if (!of.slow) return;
        of.slow = false;
        if (of === file && !of.failure && !of.latest && !dirty(of))
          announce("Changes saved.");
      }
      // A failure or conflict arriving on a file the reader has left is news once, as
      // the open file's is (`#drawn`), and the file names itself.
      /** @param {OpenFile} of */
      function tell(of) {
        const news = of.failure ?? of.latest;
        if (of === file || !news || news === of.spoken) return;
        of.spoken = news;
        announce(
          of.failure
            ? `${label(of)} was not saved: ${of.failure.message} The draft is kept.`
            : `${label(of)} changed on disk. The draft is kept.`,
        );
      }
      // A paint draws now, since what follows it reads the controls it drew.
      function paint() {
        // The comparison belongs to the conflict it opened on.
        if (!file.latest) file.comparing = false;
        element.requestUpdate();
        element.performUpdate();
      }
      // The files a navigator lists, each by the name the page's state gives it, and the
      // one open. It is built when a name or the open file changes, never as the reader
      // types, so a keystroke's work doesn't grow with how many files the editor holds.
      // Two bindings of one file list it once, since a navigator keys its rows by path.
      const publishFiles = () => {
        /** @type {Set<string>} */
        const listed = new Set();
        /** @type {{path: string, key: string}[]} */
        const named = [];
        for (const of of files.values()) {
          of.named = of.api.label;
          if (!of.named || listed.has(of.named)) continue;
          listed.add(of.named);
          named.push({ path: of.named, key: of.binding });
        }
        publishOutput(
          this,
          "files",
          named.length
            ? { files: named, ...(file.named ? { current: file.named } : {}) }
            : null,
        );
      };
      // What follows each draw: the editor's own state, the host's, the menu, the news
      // and the comparison's editor, all of which read the controls the draw made.
      this.#drawn = () => {
        const of = file;
        const name = label(of);
        editor.setLabel(name);
        editor.readOnly = of.base === null || !of.api.writable;
        // With no file to show, as on an export or an unbound page, the empty editor
        // says why, where a finger and the eye already are.
        editor.placeholder = of.base === null ? (of.failure?.message ?? "") : "";
        if (of.comparing) internals.states.add("comparing");
        else internals.states.delete("comparing");
        if (!of.latest && isNativeLayer(choices())) closeNativeLayer(choices());
        // Each failure and conflict is news once, as it arrives; the status shows it.
        const news = of.failure ?? of.latest;
        if (news && news !== of.spoken)
          announce(
            of.failure
              ? `${of.failure.message}${of.base && dirty(of) ? " The draft is kept." : ""}`
              : "The file changed on disk. The draft is kept.",
          );
        of.spoken = news;
        if (of.comparing && of.latest) {
          if (!comparison)
            comparison = createEditor(comparisonMount, {
              text: editor.value,
              filename: name,
              original: of.latest.text,
              readOnly: true,
              label: "Compare versions",
              description:
                "Read only. Removed text is on disk. Added text is the draft.",
            });
          comparison.value = editor.value;
          comparison.setLabel(name);
          comparison.setConflict(of.latest.text);
        } else if (comparison) {
          comparison.disconnect();
          comparison = null;
        }
      };
      this.#template = () => {
        const of = file;
        // A conflict keeps its choices through a failed Save draft, which is its own
        // retry; the failure then describes the control rather than taking its place.
        const conflicted = Boolean(of.latest);
        const retryable = of.failure?.kind === "save" && !of.latest;
        return html`
          <div class="lf-file-editor-head">
            <span class="lf-file-editor-name" data-lf-scroll>${label(of)}</span>
            <span
              ${offered("lf-file-editor-status")}
              .lfPreview=${() => (of.failure ? { detail: [of.failure.message] } : null)}
              >${
                of.latest
                  ? ""
                  : of.failure
                    ? of.base
                      ? "Not saved"
                      : "Unavailable"
                    : of.slow
                      ? "Saving changes…"
                      : ""
              }${retryable ? html`&nbsp;` : nothing}<button
                ${offeredAction("symbol", "lf-file-editor-retry", undefined, {
                  action: "retry",
                })}
                ?hidden=${!retryable}
                aria-description=${of.failure?.message ?? nothing}
                aria-disabled=${of.busy ? "true" : nothing}
                @click=${(/** @type {MouseEvent} */ event) => retry(event.currentTarget instanceof HTMLElement ? event.currentTarget : null)}
              ></button
              ><button
                ${offeredAction("inline", "lf-file-editor-conflict")}
                data-lf-tone="warn"
                ?hidden=${!conflicted}
                aria-description=${of.failure?.message ?? nothing}
                popovertarget="lf-file-editor-choices"
                aria-haspopup="menu"
                aria-expanded="false"
              >
                ${of.failure ? "Not saved" : "Changed on disk"}${iconTemplate(
                  "down",
                  "lf-file-editor-icon",
                )}
              </button></span
            >
          </div>
          <div
            ${offered("lf-file-editor-choices lf-popover")}
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
              ${offeredAction("word")}
              role="menuitemcheckbox"
              aria-checked=${String(of.comparing)}
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
                  ${offeredAction("word")}
                  role="menuitem"
                  aria-disabled=${of.busy ? "true" : nothing}
                  @click=${run}
                >
                  ${label}
                </button>
              `,
            )}
          </div>
          ${mount}
          <div
            class="lf-file-editor-compared"
            id="lf-file-editor-compared"
            ?hidden=${!of.comparing}
          >
            <p class="lf-file-editor-legend">
              Removed text is on disk. Added text is the draft.
            </p>
            ${of.comparing ? comparisonMount : nothing}
          </div>
        `;
      };
      // CodeMirror discovers its shadow root from the connected mount.
      render(this.#template(), view, this.renderOptions);
      /** @type {HTMLButtonElement | null} */
      const conflictButton = view.querySelector(".lf-file-editor-conflict");
      /** @type {HTMLDivElement | null} */
      const choicesMenu = view.querySelector(".lf-file-editor-choices");
      const firstChoice = choicesMenu?.querySelector("button");
      if (!conflictButton || !choicesMenu || !firstChoice)
        throw new Error("file editor controls did not render");
      const controls = {
        conflict: conflictButton,
        menu: choicesMenu,
        first: firstChoice,
      };
      const editor = createEditor(mount, {
        readOnly: true,
        onChange() {
          remember(file);
          paint();
          schedule(file);
        },
        onSave() {
          clearTimeout(file.timer);
          if (file.failure) retry(editor.contentDOM);
          else void flush(file);
        },
      });
      /** @param {OpenFile} of */
      function schedule(of, delay = 500) {
        clearTimeout(of.timer);
        if (connected && of.api.writable && !of.latest && !of.failure && dirty(of))
          of.timer = setTimeout(() => void flush(of), delay);
      }
      // Each request settles the file it was made for, whichever file is open by then;
      // only the open one paints.
      /** @param {OpenFile} of @param {boolean} [replace] @param {HTMLElement | null} [returnFrom] */
      async function flush(of, replace = false, returnFrom = null) {
        clearTimeout(of.timer);
        if (
          !connected ||
          !of.api.writable ||
          of.busy ||
          !of.base ||
          (of.failure && !returnFrom) ||
          (of.latest && !replace) ||
          (!dirty(of) && !(replace && of.latest))
        )
          return;
        const against = replace && of.latest ? of.latest : of.base;
        const submitted = text(of);
        of.busy = true;
        // The host compares the file before writing, so a receipt or a stale answer
        // covers any read owed before it starts; a failure read nothing.
        const owedBefore = of.owed;
        of.owed = false;
        if (!of.slow && of.slowTimer === null)
          of.slowTimer = setTimeout(() => {
            of.slow = true;
            of.slowTimer = null;
            if (of !== file) return;
            announce("Saving changes.");
            paint();
          }, 1000);
        if (of === file) paint();
        try {
          of.base = await of.api.save({ revision: against.revision, text: submitted });
          of.latest = null;
          of.failure = null;
        } catch (fault) {
          if (fault instanceof RequestError && fault.current) {
            if (replace || !settle(of, fault.current)) of.latest = fault.current;
            of.failure = null;
          } else {
            of.failure = { kind: "save", message: describeFailure(fault), replace };
            of.owed ||= owedBefore;
          }
        } finally {
          of.busy = false;
          if (connected) remember(of);
          if (!dirty(of) || of.failure || of.latest || !connected) finishSaving(of);
          else if (!of.slow) {
            if (of.slowTimer !== null) clearTimeout(of.slowTimer);
            of.slowTimer = null;
          }
          const returning = connected && returnFrom && focused() === returnFrom;
          if (of === file) {
            paint();
            if (returning && returnFrom.hidden) returnToEditor();
          } else tell(of);
          schedule(of, 0);
          if (of.owed) refresh(of);
        }
      }
      // Settles once the editor has taken a file from the page's state, which every
      // file the page binds arrives with.
      /** @type {PromiseWithResolvers<void>} */
      const stateTaken = Promise.withResolvers();
      /** @param {OpenFile} of */
      function refresh(of) {
        if (!connected) return;
        if (of.busy || of.latest || of.failure?.kind === "save") {
          of.owed = true;
          return;
        }
        of.owed = false;
        /** @type {FileSnapshot | null} */
        let current = null;
        try {
          current = of.api.read();
          if (!current) return;
        } catch (fault) {
          of.failure = { kind: "read", message: describeFailure(fault) };
        }
        if (current && !(of.base && current.taken < of.base.taken)) {
          if (!of.base || (!of.recovering && !unsettled(of))) {
            // A first reading shows the file; a later one follows what was written
            // elsewhere and marks where.
            const first = !of.base;
            of.base = current;
            if (of === file) {
              if (first) {
                editor.value = current.text;
                // CodeMirror lays the text out in a frame of its own, which moves the
                // gutter; the page presents once it has.
                element.controller.present(
                  new Promise((done) => {
                    const view = EditorView.findFromDOM(editor.contentDOM);
                    if (!view) return done(undefined);
                    view.requestMeasure({ read() {}, write: () => done(undefined) });
                  }),
                );
              } else editor.follow(current.text);
            } else if (of.kept && text(of) !== current.text)
              of.kept = followKept(of.kept, current.text);
          } else if (current.text === text(of)) of.base = current;
          else if (current.revision !== of.base.revision && !settle(of, current))
            of.latest = current;
          of.recovering = false;
          of.failure = null;
        }
        stateTaken.resolve();
        remember(of);
        if (of.failure || of.latest || !dirty(of)) finishSaving(of);
        if (of === file) paint();
        else tell(of);
        schedule(of, 0);
      }
      /** @param {BeforeUnloadEvent} event */
      const beforeUnload = (event) => {
        if ([...files.values()].some(unsettled)) {
          event.preventDefault();
          event.returnValue = "";
        }
      };
      const visibility = () => {
        if (document.hidden) void flush(file);
      };
      /** @type {(() => void) | null} */
      let stopWatch = null;
      // The open file's watch, a kept draft's until it settles, and every file's name
      // for the navigator.
      const watch = () => {
        stopWatch?.();
        const stops = [...files.values()].map((of) =>
          of.api.watch(() => {
            if (of.api.label !== of.named) publishFiles();
            if (of === file || of.recovering) refresh(of);
          }),
        );
        stopWatch = () => stops.forEach((stop) => stop());
      };
      // A draft this tab kept, as across a reload, stands over the file until a reading
      // settles it.
      /** @param {OpenFile} of */
      const recover = (of) => {
        const pending = tabStore.get(of.recoveryKey);
        if (!pending || !of.api.writable) return;
        /** @type {{base: FileSnapshot, text: string}} */
        const recovered = JSON.parse(pending);
        of.base = recovered.base;
        of.recovering = true;
        return recovered.text;
      };
      // Every file's draft comes back, the closed ones' kept as if left in this load,
      // so each settles against its file as the open one does.
      for (const of of files.values()) {
        const draft = recover(of);
        if (draft === undefined) continue;
        if (of === file) editor.value = draft;
        else of.kept = editor.keep(draft);
      }
      // Opening another file saves what the one being left holds at once and keeps
      // its place, then shows the other where the reader left it, or read afresh.
      this.#open = (binding, line) => {
        if (!files.has(binding)) return null;
        if (binding !== file.binding) show(binding);
        return stateTaken.promise.then(() => {
          if (line && file.binding === binding) editor.goToLine(line);
        });
      };
      /** @param {string} binding */
      const show = (binding) => {
        const leaving = file;
        leaving.kept = editor.suspend();
        if (comparison) {
          comparison.disconnect();
          comparison = null;
        }
        file = fileFor(binding);
        editor.resume(file.kept, file.base?.text ?? "", label(file));
        file.kept = null;
        remember(leaving);
        void flush(leaving);
        refresh(file);
        paint();
        publishFiles();
      };
      paint();
      publishFiles();
      this.#placeSelection = () => {
        editor.placeSelection();
        comparison?.placeSelection();
      };
      whileConnected(this, (signal) => {
        connected = true;
        editor.connect();
        comparison?.connect();
        window.addEventListener("beforeunload", beforeUnload, { signal });
        document.addEventListener("visibilitychange", visibility, { signal });
        for (const of of files.values()) if (of === file || of.recovering) refresh(of);
        watch();
        // A route to a file, such as a link to `#<editor>:<binding>`, lands on the
        // editor, and the reader goes on to type where they left that file.
        const stopLanding = onCurrentLocation((/** @type {Element | null} */ node) => {
          if (node === this) returnToEditor();
        });
        return () => {
          connected = false;
          stopLanding();
          stopWatch?.();
          stopWatch = null;
          for (const of of files.values()) {
            clearTimeout(of.timer);
            finishSaving(of);
          }
          paint();
          remember(file);
          editor.disconnect();
          comparison?.disconnect();
        };
      });
    }
  },
);
