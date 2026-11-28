/* The explicitly bound UTF-8 files `binding` names, one open at a time. Their
 * authoritative bytes live on disk, outside Leaf's event log; this owner keeps only
 * each file's editing buffer, acknowledged file revision and recoverable tab-local
 * draft. CodeMirror owns editing mechanics.
 *
 * The draft is tab-local because the file on disk is what tabs share: every tab
 * autosaves to it within half a second, and a copy shared across tabs would set two
 * live buffers against one file with no log to settle between them. The draft only
 * has to survive this tab's reloads, including the forced one when Leaf's layer
 * changes, which is what lets the editor say the draft is kept. A save can reach the
 * file while its answer never reaches the tab, as when a reload cancels the request, so
 * until a save is answered the draft also records the text it sent, and leaving the
 * page asks first; a read or a stale answer that then finds that text on disk takes it
 * as the version the draft stands over. Rejected: keeping the draft without that text,
 * since the read then takes the save's words as a write from elsewhere, and the line
 * merge puts them in place of a reader's later typing, or calls the reader's own save
 * a conflict.
 *
 * The editor holds its files as its `files` output, each named by the label the
 * page's server gives it and keyed by its binding, with the open one `current`, so a
 * navigator beside it lists them, and the open file's name and its text as the reader
 * has it, saved or not, as its `text` output, so a reading bound to it, such as a
 * Markdown preview, follows their typing once it rests (`holdText`). A reveal of a
 * binding (`navigateToDatum`, a link to `#<editor>:<binding>`) opens that file. Which
 * file is open is how this tab looks at the files, not a change to them, so it enters
 * no log; a reload opens the one its address names, else the first. Each file keeps
 * its own text, selection, history and scroll while another is open, and leaving a
 * file saves what it holds at once. A file the reader has left settles its requests as
 * the open one does; a failure or conflict there is announced by the file's name and
 * stands in the status when it is opened.
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
 * The editor reads the open file when it connects, when the tab is shown again, when
 * the reader opens it and when the page's state stamps its binding anew
 * (`boundFile().watch`). A read asked for while another request on that file is in
 * flight, while a conflict holds it, or while a failure holds it with a draft or a
 * save whose answer was lost, stays owed until a later read or save covers it; a
 * clean file whose last request failed, as before the page bound it, reads again.
 * Ordinary writes have no status transition. A write pending for one second earns a
 * quiet word in the header's fixed status slot until the newest buffer is
 * acknowledged. A failure and a conflict stand in that same slot, so the editor's top
 * and height measure the same in every state (`browser/AGENTS.md`, "The page holds still under the user's aim"). A
 * failure reads "Not saved" beside Retry, a symbol, with the error as the status's
 * tooltip and Retry's description. A conflict reads "Changed on disk", an inline press
 * in the warning's tone, opening a small menu of its choices: Compare, Save draft, Use
 * file version.
 * A Save draft that fails keeps that control, since Save draft is the retry and the
 * other choices still stand; it then reads "Not saved", the slot's one line having
 * no room for both, with the error as its description. Where no file
 * could be read at all, the status reads "Unavailable" and the empty editor shows
 * why, as its placeholder. The page waits to present until the file it opens with
 * is read, so the text and the gutter's width are there when the reader first has
 * the page. A local page's read answers well within a second. Once a first read
 * has waited that second, as on leaf.page while a visitor's container starts, the
 * placeholder says "Loading file…" until the read answers and the page presents
 * without the file, whose text then lands as an arrival; the page's own controls
 * and the names in its state don't wait for a server that is still starting.
 * Rejected: the word in the status slot, which sits at the header's far end from
 * the empty line the reader looks at; and never holding the page for the file,
 * since a file of a hundred lines widens the gutter under the reader as it lands.
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
import {
  afterPresentation,
  boundFile,
  focusDestination,
  onCurrentLocation,
  rowWalk,
  shadowStage,
  tabStore,
  whileConnected,
} from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { rove } from "/runtime/lib/roving.js";
import { el } from "/runtime/lib/elements.js";
import { PendingTaskEvent } from "/runtime/lib/pending-task.js";
import { offered, offeredAction } from "/runtime/lib/controls.js";
import { iconTemplate } from "/runtime/lib/icons.js";
import { describeFailure } from "/runtime/lib/exception.js";
import { createEditor, followKept, mergeKept } from "./editor.js";

/** @typedef {import("../../../browser/types/contract.js").ServedFileSnapshot} FileSnapshot */
/** @typedef {{kind: "read", message: string} | {kind: "save", message: string, replace: boolean}} FileFailure */
/** One bound file as this tab knows it: what the server last acknowledged (`base`), a
 * newer disk version held for the reader's choice (`latest`), and the requests on it.
 * `kept` is what the editor held of it while another file is open, and `named` the
 * name the editor's `files` output last listed it by. `sent` is the text of the last
 * save the server hasn't answered, in flight or lost, until it answers or a read
 * settles it.
 * @typedef {{
 *   binding: string, api: ReturnType<typeof boundFile>, recoveryKey: string,
 *   base: FileSnapshot | null, latest: FileSnapshot | null, sent: string | null,
 *   failure: FileFailure | null, spoken: FileSnapshot | FileFailure | null,
 *   busy: boolean, comparing: boolean, recovering: boolean, owed: boolean,
 *   slow: boolean, loading: boolean, generation: number, timer: number,
 *   slowTimer: number | null,
 *   kept: import("./editor.js").KeptFile | null, named: string | null,
 * }} OpenFile */

// How long typing rests before the editor saves it and its `text` output moves, in ms.
const PAUSE = 500;

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
    /** @type {((line: number) => boolean) | null} */
    #caretOn = null;
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
    // settles once the file's first read has drawn.
    /** @param {string} key */
    lfRevealDatum(key) {
      const [binding = "", line] = key.split(":");
      return this.#open?.(binding, Number(line) || null) ?? null;
    }

    // A key names the editor while it shows the key's file, and, for a line, while
    // the caret stands on that line, so a link to a line of the open file still asks
    // for the line to be revealed (`lfRevealDatum`), as on a fresh load of its URL.
    /** @param {string} key */
    lfElementsFor(key) {
      const [binding = "", line] = key.split(":");
      if (this.#shown?.() !== binding) return [];
      return !Number(line) || this.#caretOn?.(Number(line)) ? [this] : [];
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
            sent: null,
            failure: null,
            spoken: null,
            busy: false,
            comparing: false,
            recovering: false,
            owed: false,
            slow: false,
            loading: false,
            generation: 0,
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
      // A file takes typing once its text is known and its binding can be written.
      const readOnly = (/** @type {OpenFile} */ of) =>
        of.base === null || !of.api.writable;
      this.#shown = () => file.binding;
      this.#caretOn = (line) => file.base !== null && editor.caretOn(line);
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
        if (of.owed) void refresh(of);
      };
      // The status control naming the conflict, and the menu of its choices. A choice
      // and Escape put the menu away onto that control, so a save that settles the
      // conflict returns the reader from it to the editor. The browser hands focus
      // back only from inside the menu, and a pointer press in Safari or Firefox on
      // macOS leaves the row it pressed unfocused, so the menu puts the user there
      // itself. A press away from the menu leaves them where they pressed.
      const conflictControl = () => controls.conflict;
      const choices = () => controls.menu;
      const choiceRows = () => [...choices().querySelectorAll("button")];
      const putChoicesAway = () => {
        choices().hidePopover();
        focusDestination(conflictControl(), "return");
      };
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
        if (of.busy) return;
        const operation = of.failure;
        // A failed save is settled by reading the file where nothing is left to write,
        // and where the save may have reached the file, since a second send would
        // forget the first one's words (`sent`) and take them, found on disk, for a
        // write from elsewhere.
        if (
          operation?.kind === "save" &&
          of.sent === null &&
          unsaved(of, operation.replace)
        )
          void flush(of, operation.replace, returnFrom);
        else void refresh(of, returnFrom);
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
      const unsettled = (/** @type {OpenFile} */ of) =>
        dirty(of) || of.latest !== null || of.sent !== null;
      // Whether a save would write anything: a draft apart from its base, or one the
      // reader chose to save over a newer disk version.
      const unsaved = (/** @type {OpenFile} */ of, replace = false) =>
        dirty(of) || (replace && of.latest !== null);
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
            ? JSON.stringify({ base: of.base, text: text(of), sent: of.sent })
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
          window.dispatchEvent(
            new CustomEvent("lf-announce", { detail: "Changes saved." }),
          );
      }
      // A failure or conflict arriving on a file the reader has left is news once, as
      // the open file's is (`#drawn`), and the file names itself.
      /** @param {OpenFile} of */
      function tell(of) {
        const news = of.failure ?? of.latest;
        if (of === file || !news || news === of.spoken) return;
        of.spoken = news;
        window.dispatchEvent(
          new CustomEvent("lf-announce", {
            detail: of.failure
              ? `${label(of)} was not saved: ${of.failure.message} The draft is kept.`
              : `${label(of)} changed on disk. The draft is kept.`,
          }),
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
      const holdFiles = () => {
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
        // The `files` output: held here, and `change` says it moved.
        this.files = named.length
          ? { files: named, ...(file.named ? { current: file.named } : {}) }
          : null;
        this.dispatchEvent(new Event("change"));
      };
      // The `text` output (the registry's `text-document` contract): the open file's
      // name, its binding as the key that names it however the names of the page's
      // files change, and its text as the reader has it, saved or not, so a reading
      // follows the draft while a save fails or a conflict stands, or `null` until it
      // is read. Typing moves it once it has rested for the pause autosave waits
      // (`PAUSE`), since a reading bound to it redraws from the whole text: moved at
      // each key, a keystroke's work grew with the file, past the frame's budget at a
      // thousand lines. Every other change moves it at once.
      /** @type {{key: string, name: string, text: string} | null} */
      this.text = null;
      let rests = 0;
      const holdText = () => {
        clearTimeout(rests);
        rests = 0;
        const name = label(file);
        const held = this.text;
        const text = file.base ? editor.value : null;
        if (
          text === null
            ? held === null
            : held?.text === text && held.name === name && held.key === file.binding
        )
          return;
        this.text = text === null ? null : { key: file.binding, name, text };
        this.dispatchEvent(new Event("change"));
      };
      // What follows each draw: the editor's own state, the host's, the menu, the news
      // and the comparison's editor, all of which read the controls the draw made.
      this.#drawn = () => {
        const of = file;
        if (!rests) holdText();
        const name = label(of);
        editor.setLabel(name);
        editor.readOnly = readOnly(of);
        // With no file to show, as on an export or an unbound page, or while a slow
        // first read waits, the empty editor says why, where a finger and the eye
        // already are.
        editor.placeholder =
          of.base === null
            ? (of.failure?.message ?? (of.loading ? "Loading file…" : ""))
            : "";
        if (of.comparing) internals.states.add("comparing");
        else internals.states.delete("comparing");
        if (!of.latest) choices().hidePopover();
        // Each failure and conflict is news once, as it arrives; the status shows it.
        const news = of.failure ?? of.latest;
        if (news && news !== of.spoken)
          window.dispatchEvent(
            new CustomEvent("lf-announce", {
              detail: of.failure
                ? `${of.failure.message}${of.base && dirty(of) ? " The draft is kept." : ""}`
                : "The file changed on disk. The draft is kept.",
            }),
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
        const retryable = Boolean(of.failure) && !of.latest && of.api.writable;
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
      choicesMenu.lfCommands = {
        title: "In the file's conflict menu",
        rows: choiceKeys,
      };
      choicesMenu.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
      // A draft this tab kept, as across a reload, stands over the file until a read
      // settles it. Drafts come back before the editor exists, so it starts as editable
      // as the file it shows rather than switching within the same task.
      /** @param {OpenFile} of */
      const recover = (of) => {
        const pending = tabStore.get(of.recoveryKey);
        if (!pending || !of.api.writable) return;
        /** @type {{base: FileSnapshot, text: string, sent: string | null}} */
        const recovered = JSON.parse(pending);
        of.base = recovered.base;
        of.sent = recovered.sent;
        of.recovering = true;
        return recovered.text;
      };
      /** @type {Map<OpenFile, string>} */
      const drafts = new Map();
      for (const of of files.values()) {
        const draft = recover(of);
        if (draft !== undefined) drafts.set(of, draft);
      }
      const editor = createEditor(mount, {
        readOnly: readOnly(file),
        onChange() {
          file.generation++;
          remember(file);
          clearTimeout(rests);
          rests = setTimeout(holdText, PAUSE);
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
      function schedule(of, delay = PAUSE) {
        clearTimeout(of.timer);
        if (connected && of.api.writable && !of.latest && !of.failure && dirty(of))
          of.timer = setTimeout(() => void flush(of), delay);
      }
      // Runs once a read or save of `of` ends. The open file paints, and hands the reader
      // back to the editor if the control they retried from went away; another file
      // announces its news. Then the file's own saves resume, and a read it owes runs.
      // The control's tree keeps naming it as active while the window is in the
      // background, as it may be when a request ends.
      /** @param {OpenFile} of @param {HTMLElement | null} returnFrom */
      function ended(of, returnFrom) {
        const returning =
          connected &&
          returnFrom &&
          /** @type {Document | ShadowRoot} */ (returnFrom.getRootNode())
            .activeElement === returnFrom;
        if (of === file) {
          paint();
          if (returning && returnFrom.hidden) returnToEditor();
        } else tell(of);
        schedule(of, 0);
        if (of.owed) void refresh(of);
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
          !unsaved(of, replace)
        )
          return;
        const against = replace && of.latest ? of.latest : of.base;
        const submitted = text(of);
        // An earlier save whose answer was lost, which the file may hold.
        const lost = of.sent;
        of.busy = true;
        of.sent = submitted;
        // The host compares the file before writing, so a receipt or a stale answer
        // covers any read owed before it starts; a failure read nothing.
        const owedBefore = of.owed;
        of.owed = false;
        if (!of.slow && of.slowTimer === null)
          of.slowTimer = setTimeout(() => {
            of.slow = true;
            of.slowTimer = null;
            if (of !== file) return;
            window.dispatchEvent(
              new CustomEvent("lf-announce", { detail: "Saving changes." }),
            );
            paint();
          }, 1000);
        if (of === file) paint();
        try {
          const saved = await of.api.save({
            revision: against.revision,
            text: submitted,
          });
          // An answer ends the save: it wrote the file, or, refused in the server's own
          // words, wrote nothing.
          of.sent = null;
          if (!("refused" in saved)) {
            of.base = saved;
            of.latest = null;
            of.failure = null;
          } else if (saved.current) {
            // A file holding this save or a lost earlier one holds the draft's own
            // words, which the draft stands over, as a read takes them (`refresh`).
            const held = saved.current.text;
            if (held === submitted || held === lost) {
              of.base = saved.current;
              of.latest = null;
            } else if (replace || !settle(of, saved.current)) of.latest = saved.current;
            of.failure = null;
          } else {
            of.failure = { kind: "save", message: saved.refused, replace };
            of.owed ||= owedBefore;
          }
        } catch (fault) {
          // A save with no answer, as when a reload cancels it or a proxy answers for
          // the server, may have reached the file, so its text stays until a read says.
          of.failure = { kind: "save", message: describeFailure(fault), replace };
          of.owed ||= owedBefore;
        } finally {
          of.busy = false;
          if (connected) remember(of);
          if (!dirty(of) || of.failure || of.latest || !connected) finishSaving(of);
          else if (!of.slow) {
            if (of.slowTimer !== null) clearTimeout(of.slowTimer);
            of.slowTimer = null;
          }
          ended(of, returnFrom);
        }
      }
      // Settles once a first read has waited a second, which is when the page stops
      // waiting for the file it opens with.
      /** @type {PromiseWithResolvers<void>} */
      const waited = Promise.withResolvers();
      /** @param {OpenFile} of @param {HTMLElement | null} [returnFrom] */
      async function refresh(of, returnFrom = null) {
        if (!connected) return;
        // A failure holds the file only while it holds words a read could set against
        // the file: a draft, or a save whose answer was lost. A clean editor whose read
        // failed, as before the page bound its file, reads again.
        const held = of.failure && (dirty(of) || of.sent !== null);
        if (of.busy || ((held || of.latest) && !returnFrom)) {
          of.owed = true;
          return;
        }
        // An offline read refuses immediately; no file operation is in flight.
        of.busy = of.api.writable;
        of.owed = false;
        const seenGeneration = of.generation;
        const slow = of.base
          ? 0
          : setTimeout(() => {
              of.loading = true;
              if (of === file) paint();
              waited.resolve();
            }, 1000);
        try {
          const current = await of.api.read();
          if (
            !of.base ||
            (!of.recovering && !unsettled(of) && seenGeneration === of.generation)
          ) {
            // A first reading shows the file; a later one follows what was written
            // elsewhere and marks where.
            const first = !of.base;
            of.base = current;
            of.latest = null;
            if (of === file) {
              if (first) editor.value = current.text;
              else editor.follow(current.text);
            } else if (of.kept && text(of) !== current.text)
              of.kept = followKept(of.kept, current.text);
          } else if (
            current.text === text(of) ||
            current.revision === of.base.revision ||
            current.text === of.sent
          ) {
            // The file holds the draft, the version it was typed over, or the save
            // whose answer was lost; the draft stands over it.
            of.base = current;
            of.latest = null;
          } else if (!settle(of, current)) of.latest = current;
          of.recovering = false;
          of.sent = null;
          of.failure = null;
        } catch (fault) {
          of.failure = { kind: "read", message: describeFailure(fault) };
        } finally {
          clearTimeout(slow);
          of.loading = false;
          of.busy = false;
          if (connected) remember(of);
          if (of.failure || of.latest || !dirty(of)) finishSaving(of);
          ended(of, returnFrom);
        }
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
        else void refresh(file);
      };
      /** @type {(() => void) | null} */
      let stopWatch = null;
      // The open file's watch, and every file's name for the navigator.
      const watch = () => {
        stopWatch?.();
        const stops = [...files.values()].map((of) =>
          of.api.watch(() => {
            if (of.api.label !== of.named) holdFiles();
            if (of === file) void refresh(of);
          }),
        );
        stopWatch = () => stops.forEach((stop) => stop());
      };
      // Every file's draft comes back, the closed ones' kept as if left in this load,
      // so each settles against its file as the open one does.
      for (const [of, draft] of drafts) {
        if (of === file) editor.value = draft;
        else of.kept = editor.keep(draft);
      }
      /** @type {Promise<void> | null} */
      let opening = null;
      // Opening another file saves what the one being left holds at once and keeps
      // its place, then shows the other where the reader left it, or read afresh.
      this.#open = (binding, line) => {
        if (!files.has(binding)) return null;
        const ready = binding === file.binding ? opening : show(binding);
        if (!line) return ready;
        return (ready ?? Promise.resolve()).then(() => {
          if (file.binding === binding) editor.goToLine(line);
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
        holdText();
        paint();
        holdFiles();
        opening = connected ? refresh(file) : null;
        return opening;
      };
      paint();
      holdFiles();
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
        opening = refresh(file);
        for (const of of files.values())
          if (of !== file && of.recovering) void refresh(of);
        if (initial) {
          const first = opening;
          this.dispatchEvent(
            new PendingTaskEvent(Promise.race([first, waited.promise])),
          );
          void afterPresentation(() => first);
          initial = false;
        }
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
