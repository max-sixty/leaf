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
 * (draft.css): Edit (a pencil) and Copy at rest, Save, Discard and Copy while editing.
 * Copy copies the Markdown source the box shows. The toolbar takes no room, so the box
 * is the same size with its controls as without them, and opening the editor adds no
 * row of buttons under it; a refused save's status joins the toolbar. Copy keeps the
 * last seat, and Discard opens where Edit stood, so a second press on the pencil gives
 * the box back unchanged. When the toolbar shows and takes presses is draft.css's,
 * which reads two marks the toolbar wears: `data-lf-typing`, from a keystroke in the
 * editor until the pointer has rested on the toolbar (`restArming`) or focus leaves
 * the editor, and `data-lf-pointed`, while the pointer is on the toolbar meanwhile.
 * The rest stands though ⌘Z takes a Discard back: a press aimed at the words under the
 * toolbar would otherwise land on Save, which sends the agent a turn, or on Discard,
 * which closes the editor mid-sentence. Clicking the prose still opens the editor at
 * that spot. Rejected: a resting row under the prose holding only Edit, which doubled a
 * one-line box, and marks set into the box's corner, which either covered the first
 * line's last words or took room from them and changed the box's size as the editor
 * opened. The same command declarations own pointer activation, keyboard routes,
 * availability and accessible shortcut hints. The editor's own keys, Save's and
 * Escape's, show in the shared command reference (`?`). The controls take no context
 * keys, so an obligation lends them no digits; Tab reaches them, as it does every
 * native button. Comments and workflow receipts keep their own annotation layer;
 * hiding annotations cannot hide the editor's controls. The editor and its tools are
 * Leaf surfaces even inside the document, so Draw and Design modes leave them operable
 * while the saved reading remains the page's to draw on or comment on.
 *
 * The editor opens where the prose stood and in its faces: its field takes each
 * block's type and the gaps between blocks from the draft's place on the page, and
 * draws a picture as the picture, under its source once the caret reaches it
 * (`facesOf`, annotations/composing/text-field.js), so no word moves as it opens. It
 * draws each blank line typed between blocks, and saving writes each run of them as the
 * one gap the prose draws (`valueToSave`). Rejected: drawing drafts in a sent message's
 * face, which the editor already wore, since drafts would lose their document type,
 * chosen by the user.
 *
 * A draft reads as a Markdown file: a line break inside a paragraph is a space
 * (`paintMarkdown`), so a draft wrapped for a wider editor, as an agent copies a
 * passage of a hard-wrapped file, wraps to the box, and the editor joins those lines
 * as the prose does. Return in a paragraph writes a hard break, which both show as a
 * line (the user's decision). Rejected: keeping each source line break as a hard one,
 * as a message does, which drew a passage wrapped at 88 columns in a narrower box with
 * a short line after each long one.
 *
 * The editor reads as an ordinary text box: its words stand in the field until the user
 * leaves it, and the field's own undo walks them back. Two ways out throw its changes
 * away, Discard and Escape, as a message rewrite's do, and ⌘Z, which their notice
 * offers, puts them back and opens the editor on them (the draft's `discard`), so a
 * stray press on Discard loses nothing for good; every other way out saves them as Save
 * does, which submits one absolute edit through the shared send generation. A press
 * away from the draft saves (dom/focus.js, `onPressAway`), so a tap elsewhere on a
 * phone keeps what was typed without finding Save first, and Android's back gesture
 * saves the same way (`keep`, close-requests.js). A stray edge swipe therefore sends
 * the agent a turn, as a stray tap does (the user's decision). Rejected: back closing
 * the editor with its words kept unsaved, a third way out whose state the closed box
 * had to show beside Edit; and saving at each pause in the typing, as a form does,
 * since every save is an edit delivered to the agent, which would read half-written
 * words. Pointer Discard returns the frame over a short native size interpolation; its
 * words and Edit focus return at once. Keyboard discarding and reduced motion are
 * instant; reopening cancels the effect. A saved edit is withdrawn with the page's undo
 * (⌘Z), and the log keeps every version for the agent. Rejected: Escape setting unsent
 * words aside for the next opening, which needed a Close button beside Discard and left
 * a closed box holding words it gave no sign of; and a Changes list that restored
 * earlier versions, which the page's undo already does.
 *
 * The draft holds its source as its `text` output (the registry's `text-document`
 * contract), named as the Markdown file it reads as, `<id>.md`, so a reading bound to
 * it, such as a diff against an earlier text, shows it as it would a file's: the saved
 * text, the words a save sends while it travels, or the open editor's unsent words once
 * typing in them rests.
 *
 * The shared draft store holds an open editor's words, so they survive a reload, a live
 * revision that replaces this element, the element leaving the page and coming back,
 * and the tab closing, and every tab's open editor shows the same words. Another tab's
 * settlement closes its matching editor without taking focus from an unrelated place.
 * A refused save reopens the retained source with Retry, and takes the focus only from
 * this draft or from nowhere. Print keeps the saved reading and omits controls.
 *
 * How it is drawn. An Effect UI component (runtime/effect-widget.js) draws beside the
 * authored body, in the light DOM, since comments, anchoring and the version diff read
 * the body there and its editor takes its place in the box's grid. Leaf's reading of
 * the draft arrives as `state`: the saved source and whether it may be edited.
 *
 * - `PaintBody` paints the saved source into the light body (`paintMarkdown`) and holds
 *   the drawing until its code and formulas are dressed (`dressCode`).
 * - `EditDraft` owns the editor, a `leaf-text` (CodeMirror inside), on a box of its
 *   own, together with what has to reach that editor synchronously: the draft store's
 *   words, the command rows whose Save reads them, the press away and Android's back,
 *   the caret a click carries in, focus as the editor opens and closes, the send, and
 *   the `text` output, which `defineWidget` has no option for.
 *   Its args are Leaf's reading; it reports what the user did and what became of a
 *   save as messages. The editor's words and caret live only in the editor and the
 *   store, so no redraw, new reading or revision touches them.
 * - The Model is what the toolbar draws: whether the editor stands, a save is in
 *   flight or was refused, and the typing rest above.
 *
 * A new reading while the editor stands repaints the hidden body and leaves the
 * editor's words alone, so the widget holds no drawing back for it. */
import {
  Component,
  Effect,
  Html,
  Mount,
  Queue,
  Schema,
  Stream,
  UiSchema,
} from "/vendor/effect-ui.js";
import {
  aimedAt,
  nameOf,
  motion,
  draft,
  dressCode,
  focusDestination,
  retainUserIntent,
  scrollIntoView,
  onCurrentLocation,
  onPressAway,
  pageLinks,
} from "/runtime/widget-api.js";
import { RecordAction } from "/runtime/widget-services.js";
import { declare, defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { offerActionElement, offerAttributes, offer } from "/runtime/lib/controls.js";
import { keeps } from "/runtime/lib/keeps.js";
import { addressableWord } from "/runtime/lib/element-word.js";
import { nextRender } from "/runtime/lib/frame-pass.js";
import { restArming } from "/runtime/lib/rest-arming.js";
import { motionTime } from "/runtime/lib/motion-timing.js";
import { PendingTaskEvent } from "/runtime/lib/pending-task.js";
import {
  paintMarkdown,
  markdownSourceOffset,
  markdownWords,
} from "/runtime/lib/markdown.js";

type Editor = HTMLElementTagNameMap["leaf-text"];
type Caret = [number, number];
type Tool = "edit" | "save" | "cancel";
type Holder = HTMLElement & { text?: { name: string; text: string } | null };

// How long typing in the editor rests before the `text` output takes its words, in ms,
// the pause a file editor waits before it saves.
const PAUSE = 500;

const DraftProps = Schema.Struct({
  ...widgetProps,
  exhibit: Schema.Boolean,
  named: Schema.String,
});
const DraftModel = Schema.Struct({
  editing: Schema.Boolean,
  sending: Schema.Boolean,
  failed: Schema.Boolean,
  typing: Schema.Boolean,
  pointed: Schema.Boolean,
});
export const DraftMessage = UiSchema.TaggedEnum({
  OpenedEditor: {},
  ClosedEditor: {},
  TypedInEditor: {},
  KeptTools: {},
  PointedAtTools: {},
  LeftTools: {},
  StartedSave: {},
  CompletedSave: {},
  RefusedSave: {},
});

// The draft's reading as Leaf set it: its saved Markdown and whether it may be edited.
const readingOf = (state: unknown) => {
  const edit = (
    state as { edit?: { value?: unknown; available?: unknown } } | undefined
  )?.edit;
  if (typeof edit?.value !== "string")
    throw new Error("A draft reading must contain its Markdown text");
  return { saved: edit.value, available: Boolean(edit.available) };
};

const hostOf = (node: Element) => {
  const host = node.closest("lf-draft");
  if (!(host instanceof HTMLElement)) throw new Error("draft drawn outside lf-draft");
  return host;
};
const bodyOf = (host: HTMLElement) => {
  const body = host.querySelector<HTMLElement>(":scope > .lf-markdown-body");
  if (!body) throw new Error("draft needs its prepared Markdown body");
  return body;
};

// Carry a rendered caret into source; a padding press has no caret to transfer.
function caretAt(body: HTMLElement, x: number, y: number): Caret | null {
  const pos = document.caretPositionFromPoint(x, y);
  const source = body.dataset.lfSourceWords;
  if (!pos || source === undefined) return null;
  const offset = markdownSourceOffset(body, source, pos.offsetNode, pos.offset, false);
  return offset === null ? null : [offset, offset];
}

// The saved source in the light body, and its code and formulas dressed before the
// drawing counts as done (`pending-task`).
const PaintBody = Mount.make(
  "PaintBody",
  { args: { text: Schema.String } },
  (face: HTMLElement, _args, changes) =>
    Stream.runForEach(changes, ({ text }) =>
      Effect.sync(() => {
        const host = hostOf(face);
        const body = bodyOf(host);
        keeps(body, "class", "lf-draft-body lf-markdown-body"); // NOT .lf-ui: anchoring and Δ must see this
        paintMarkdown(body, text, pageLinks);
        host.dispatchEvent(new PendingTaskEvent(dressCode(body)));
      }),
    ).pipe(Effect.as(Component.noop)),
);

// A toolbar mark: its face and the symbol of the action it names.
const OfferMark = Mount.make(
  "OfferMark",
  { args: { action: Schema.String } },
  (node: HTMLButtonElement, _args, changes) =>
    Stream.runForEach(changes, ({ action }) =>
      Effect.sync(() => {
        offerActionElement(node, "mark", "", undefined, { action });
      }),
    ).pipe(Effect.as(Component.noop)),
);

// Leaf's reading, and what the toolbar draws from the Model, whose drawn controls and
// titles the command rows name.
type EditArgs = {
  saved: string;
  available: boolean;
  named: string;
  editing: boolean;
  failed: boolean;
};
type RecordEdit = (args: {
  verb: string;
  detail: { value: string };
  says: string;
  attempt: string;
}) => Effect.Effect<"admitted" | "refused" | "unrecorded">;

/* The editor and everything that reaches it synchronously, for one draft element while
 * its root stands. It reports to the component what the toolbar draws. */
class DraftEditing {
  readonly #host: HTMLElement;
  readonly #room: HTMLElement;
  readonly #tools: HTMLElement;
  readonly #body: HTMLElement;
  readonly #edit: ReturnType<typeof draft>;
  readonly #send: (message: unknown) => void;
  readonly #record: RecordEdit;
  #args: EditArgs;
  #editor: Editor | null = null;
  #sending = false;
  #failed = false;
  #typing = false;
  #cancelSize: number | null = null;
  #rests = 0;
  // The words a save in flight sends, which the `text` output holds meanwhile.
  #submitted: string | null = null;
  #returnMotion: ReturnType<typeof motion> | null = null;
  #stopPressAway: (() => void) | null = null;
  readonly #stops: (() => void)[] = [];
  readonly #commands: NonNullable<HTMLElement["lfCommands"]>;
  // The toolbar shows again, after typing put it away, while the pointer is on it, and
  // takes presses once the pointer has rested there.
  readonly #arming: ReturnType<typeof restArming>;

  constructor(
    room: HTMLElement,
    args: EditArgs,
    send: (message: unknown) => void,
    record: RecordEdit,
  ) {
    this.#room = room;
    this.#args = args;
    this.#send = send;
    this.#record = record;
    const host = (this.#host = hostOf(room));
    this.#body = bodyOf(host);
    const tools = room.parentElement?.querySelector<HTMLElement>(
      ":scope > .lf-draft-tools",
    );
    if (!tools) throw new Error("draft needs its toolbar");
    this.#tools = tools;
    // The unsent edit, kept under the draft's id. Deleting every character is an
    // unsent edit too, so only a missing record means none is pending.
    this.#edit = draft("edit:" + host.id);
    this.#arming = restArming(() => this.#tools, {
      point: () => send(DraftMessage.PointedAtTools()),
      arm: () => this.#keepTools(),
      unpoint: () => send(DraftMessage.LeftTools()),
    });
    this.#commands = {
      title: "On a draft",
      rows: [
        {
          id: "draft.edit",
          keys: [],
          control: () => this.#control("edit"),
          decision: true,
          title: "Edit",
          when: () => !this.#editor && !this.#sending && this.#args.available,
          run: () => this.#open(),
        },
        {
          id: "draft.save",
          reach: "in an open draft editor",
          keys: ["Mod+Enter"],
          control: () => this.#control("save"),
          decision: true,
          title: () => (this.#failed ? "Retry" : "Save"),
          when: () => Boolean(this.#editor) && !this.#sending && this.#args.available,
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
      ],
    };
    declare(room, { lfCommands: this.#commands });
    // Leaf stands Copy last in the toolbar (`lfBar`), so Tab from the editor reaches
    // Save first. It copies the source the box shows, the editor's while it is open.
    host.lfCopy = () => this.#editor?.value ?? this.#args.saved;
    host.lfBar = tools;
    host.dataset.lfCopy = "Markdown";
    this.#listen();
    // A recovered edit outranks the authored text: the user typed it and never got it
    // sent, so it must survive exactly as the composer's drafts do. The store holds
    // words only while an editor stands open on them, so any it holds reopen that
    // editor. They are not compared with the current text: words walking a saved edit
    // back to the authored text are an edit all the same.
    //
    // An edit coming back is not the user arriving, though, so the box does not take
    // the focus. A revision that rewrote this draft connects it again while the user
    // stands somewhere else, and news with no gesture behind it moves nobody, the same
    // reason the store's news leaves a closed box closed. On a page that has just
    // loaded, startup hands the focus to the page after this runs either way.
    const pending = this.#edit.read();
    if (pending) this.#open(pending.text, undefined, false);
    this.#holdText();
  }

  // Hold the source the box shows as the `text` output.
  #holdText() {
    clearTimeout(this.#rests);
    this.#rests = 0;
    const host: Holder = this.#host;
    const text = this.#editor?.value ?? this.#submitted ?? this.#args.saved;
    if (host.text?.text === text) return;
    host.text = { name: `${host.id}.md`, text };
    host.dispatchEvent(new Event("change"));
  }

  // Typing moves the output once it rests.
  #restText() {
    clearTimeout(this.#rests);
    this.#rests = window.setTimeout(() => this.#holdText(), PAUSE);
  }

  #listen() {
    const host = this.#host;
    const controller = new AbortController();
    const { signal } = controller;
    this.#stops.push(() => controller.abort());
    // The pointer coming to the toolbar brings it back after typing put it away, and
    // resting there gives it its presses back.
    const point = (event: PointerEvent) => {
      if (this.#typing) this.#arming.move(event);
    };
    host.addEventListener("pointermove", point, { signal });
    host.addEventListener("pointerleave", point, { signal });
    // Capture only the pointer Discard's old allocation. The command still owns
    // closing, discarding and focus; its new reading is true before this effect.
    host.addEventListener(
      "click",
      (event) => {
        this.#cancelSize = null;
        if (
          event.button !== 0 ||
          event.detail === 0 ||
          !(
            event.target instanceof Element &&
            event.target.closest('[data-lf-draft-action="cancel"]')
          ) ||
          !this.#editor ||
          !CSS.supports("block-size", "calc-size(auto, size)")
        )
          return;
        this.#cancelSize = host.getBoundingClientRect().height;
      },
      { capture: true, signal },
    );
    // A click opens the exact source at its rendered caret. A control or link inside
    // the draft and a completed word selection own their own gestures (`aimedAt`);
    // what the draft stands in, such as a reply's thread message, does not.
    host.addEventListener(
      "click",
      (event) => {
        // A keyboard activation carries no place, and the keyboard's door is the ✎. The
        // primary button only: a middle- or right-press is not the gesture this is for.
        if (event.detail === 0 || event.button !== 0 || aimedAt(event, host) !== host)
          return;
        if (!this.#args.available) return;
        event.preventDefault();
        this.#open(undefined, caretAt(this.#body, event.clientX, event.clientY));
      },
      { signal },
    );
    // One edit, however many tabs are open on the page. An open box follows what is
    // typed in another; a closed one stays closed, because news arriving has no gesture
    // behind it and the box would open under whatever the user is doing here; it takes
    // up the words at the next opening either way (`#open` reads the store). A
    // settlement is the case that does move this tab: the words are sent or discarded,
    // so an open box holding them has nothing left to hold.
    this.#stops.push(
      this.#edit.watch(
        (text) => {
          if (text === null) this.#close(false);
          else if (this.#editor && this.#editor.value !== text) {
            this.#editor.value = text;
            this.#restText();
          }
        },
        {
          input: () => this.#editor,
          resume: () =>
            this.#args.available
              ? {
                  where: host,
                  input: () => this.#editor,
                  open: () => this.#open(undefined, undefined, false),
                }
              : null,
        },
      ),
    );
    // Typing lasts while the caret does: a box the user has left shows Save and
    // Discard, so it never reads as saved while it still holds their words.
    this.#stops.push(
      onCurrentLocation((node: Element | null) => {
        if (this.#typing && node !== this.#editor) this.#keepTools();
      }),
    );
  }

  show(args: EditArgs) {
    const drew =
      args.editing !== this.#args.editing || args.failed !== this.#args.failed;
    this.#args = args;
    if (this.#editor) this.#editor.readOnly = !args.available;
    if (!this.#rests) this.#holdText();
    // The toolbar has drawn the controls and title the rows name: Leaf reads them again.
    if (drew) declare(this.#room, { lfCommands: this.#commands });
  }

  close() {
    clearTimeout(this.#rests);
    this.#returnMotion?.cancel();
    this.#stopPressAway?.();
    for (const stop of this.#stops.splice(0)) stop();
    this.#host.removeAttribute("aria-busy");
    delete this.#host.dataset.lfCopy;
    this.#host.lfCopy = this.#host.lfBar = undefined;
  }

  #control(key: Tool) {
    return this.#tools.querySelector<HTMLButtonElement>(
      `[data-lf-draft-action="${key}"]`,
    );
  }

  // The toolbar stands and takes presses as it does before any typing.
  #keepTools() {
    this.#arming.reset();
    if (!this.#typing) return;
    this.#typing = false;
    this.#send(DraftMessage.KeptTools());
  }

  #open(seed?: string, at?: Caret | null, arrive = true) {
    this.#returnMotion?.cancel();
    this.#returnMotion = null;
    if (this.#editor) return;
    if (this.#sending) {
      window.dispatchEvent(
        new CustomEvent("lf-error", {
          detail: "Wait for the current edit to finish saving",
        }),
      );
      return;
    }
    const editor = offer("leaf-text", "lf-draft-edit");
    editor.dataset.lfRuntime = "";
    // It stands where the prose did, so it reads in the prose's faces.
    editor.facesOf = this.#body;
    // Words another tab's open editor holds outrank the current text: they are the
    // same unsent edit.
    const saved = this.#args.saved;
    editor.value = seed ?? this.#edit.read()?.text ?? saved;
    editor.readOnly = !this.#args.available;
    editor.setAttribute("aria-label", `Edit ${this.#args.named}`);
    editor.addEventListener("input", () => {
      this.#arming.reset();
      this.#edit.save(editor.value);
      this.#restText();
      this.#typing = true;
      this.#failed = false;
      this.#send(DraftMessage.TypedInEditor());
    });
    // The composer's bindings on the box that replaces the page's own words. Escape
    // being the innermost scope's is what keeps the runtime's own rung from running
    // behind it and closing a panel too.
    this.#editor = editor;
    editor.lfCommands = this.#commands;
    this.#room.append(editor);
    this.#holdText();
    this.#send(DraftMessage.OpenedEditor());
    editor.dispatchEvent(
      new CustomEvent("lf-commands", { bubbles: true, composed: true }),
    );
    // Its toolbar stands inside the draft, so Discard and Copy are no press away.
    this.#stopPressAway = onPressAway(
      (path) => !path.includes(this.#host),
      () => void this.#commit(),
    );
    // Only the pointer names a place; the Edit control and a recovered draft leave the
    // caret where focus put it, at the end of the text. The range was measured in the
    // body's text, so it names a word only in a box holding that text: a resumed edit
    // opens with different words at those offsets. A padding press carries null.
    if (at && editor.value === saved) editor.setSelectionRange(at[0], at[1]);
    if (arrive) {
      focusDestination(editor, "move");
      if (at === undefined) scrollIntoView(editor, { block: "nearest" });
    }
  }

  #close(discard: boolean) {
    const editor = this.#editor;
    if (!editor) return;
    const before = this.#cancelSize;
    this.#cancelSize = null;
    // Hold the old allocation before any control repaint can read layout and clamp a
    // reader at the document foot. Native auto follows the restored body.
    if (before !== null)
      this.#returnMotion = motion(
        this.#host,
        [{ blockSize: `${before}px` }, { blockSize: "calc-size(auto, size)" }],
        motionTime("--lf-motion-fold"),
      );
    // Words the box already says are no loss, so only changed ones are kept for ⌘Z to
    // take back.
    if (discard && editor.value === this.#args.saved) this.#edit.clear();
    else if (discard) this.#edit.discard();
    this.#stopPressAway?.();
    this.#stopPressAway = null;
    // Only where the user was in it. A close this tab's own gesture made has focus in
    // the box that is going, and the draft's one persistent control is where it lands
    // so a keyboard user isn't dropped back at the page top; a close another tab's
    // settlement brings takes focus from wherever they actually are.
    const left = document.activeElement;
    const stood = this.#host.contains(left);
    const mayReturn = retainUserIntent({ source: left });
    editor.remove();
    this.#editor = null;
    this.#holdText();
    this.#arming.reset();
    this.#typing = false;
    this.#failed = false;
    this.#send(DraftMessage.ClosedEditor());
    if (!stood) return;
    if (this.#sending) focusDestination(this.#host, "return");
    else
      nextRender(() => {
        // The toolbar has drawn Edit by this callback. A new gesture elsewhere wins
        // over handing back the editor's vacated focus.
        const edit = this.#control("edit");
        if (this.#host.isConnected && !this.#editor && mayReturn() && edit)
          focusDestination(edit, "return");
      });
  }

  async #commit() {
    const editor = this.#editor;
    if (!editor || this.#sending || !this.#args.available) return;
    const { saved, named } = this.#args;
    // Saved as the prose reads it, with one blank line for each gap. Opening and
    // leaving a draft written with more saves nothing.
    const text = editor.value === saved ? saved : editor.valueToSave;
    if (text === saved) {
      this.#close(true);
      return;
    }
    this.#sending = true;
    this.#submitted = text;
    this.#send(DraftMessage.StartedSave());
    this.#close(false);
    this.#host.setAttribute("aria-busy", "true");
    const ok = await this.#edit.send(
      () => true,
      (attempt) =>
        Effect.runPromise(
          this.#record({
            verb: "edit",
            detail: { value: text },
            says: `Edited ${named}`,
            attempt,
          }),
        ).then((delivery) =>
          delivery === "admitted" ? true : delivery === "refused" ? false : null,
        ),
    );
    this.#sending = false;
    this.#submitted = null;
    this.#host.removeAttribute("aria-busy");
    if (ok) {
      this.#holdText();
      this.#send(DraftMessage.CompletedSave());
      return;
    }
    // Null means the same shared generation was settled by the other tab while this
    // one waited to send. Its action will replay this body, so do not resurrect the
    // editor as if a network failure had occurred. A stored generation is either the
    // failed send itself or newer shared text; both stay editable. Leaf has set the
    // authoritative body before this call resolves, so opening the saved generation
    // must not overwrite it with the stale pre-send snapshot.
    const stored = this.#edit.read();
    if (!stored) {
      this.#holdText();
      this.#send(DraftMessage.CompletedSave());
      return;
    }
    this.#failed = true;
    this.#send(DraftMessage.RefusedSave());
    // A press away may have taken the user on to another place, such as the next
    // draft's editor, which keeps the focus.
    const here = document.activeElement;
    this.#open(
      stored.text,
      undefined,
      !here || here === document.body || this.#host.contains(here),
    );
  }
}

// The editor on its own box, fed Leaf's reading and reporting what the user does.
const EditDraft = Mount.makeStream(
  "EditDraft",
  {
    args: {
      saved: Schema.String,
      available: Schema.Boolean,
      named: Schema.String,
      editing: Schema.Boolean,
      failed: Schema.Boolean,
    },
  },
  (room: HTMLElement, args, changes) =>
    Stream.callback((queue) =>
      Effect.gen(function* () {
        const record = (yield* RecordAction) as unknown as RecordEdit;
        const editing = yield* Effect.acquireRelease(
          Effect.sync(
            () =>
              new DraftEditing(
                room,
                args,
                (message) => Queue.offerUnsafe(queue, message),
                record,
              ),
          ),
          (editing) => Effect.sync(() => editing.close()),
        );
        yield* Stream.runForEach(changes, (next) =>
          Effect.sync(() => editing.show(next)),
        ).pipe(Effect.forkScoped);
      }),
    ),
);

const TOOLS: [Tool, string][] = [
  ["edit", "edit"],
  ["save", "save"],
  ["cancel", "discard"],
];

export const Draft = Html.component({
  name: "Draft",
  props: DraftProps,
  model: DraftModel,
  message: DraftMessage,
}).make({
  init: () => ({
    editing: false,
    sending: false,
    failed: false,
    typing: false,
    pointed: false,
  }),
  update: {
    OpenedEditor: ($) => $.evolve({ editing: true }),
    ClosedEditor: ($) =>
      $.evolve({ editing: false, failed: false, typing: false, pointed: false }),
    TypedInEditor: ($) => $.evolve({ typing: true, pointed: false, failed: false }),
    KeptTools: ($) => $.evolve({ typing: false, pointed: false }),
    PointedAtTools: ($) => $.evolve({ pointed: true }),
    LeftTools: ($) => $.evolve({ pointed: false }),
    StartedSave: ($) => $.evolve({ sending: true }),
    CompletedSave: ($) => $.evolve({ sending: false }),
    RefusedSave: ($) => $.evolve({ sending: false, failed: true }),
  },
  view: (h: any, model: any) => {
    const { saved, available } = readingOf(h.props.state);
    const face = h.div.class("lf-draft-face").onMount(PaintBody({ text: saved }));
    // A quoted draft is an exhibit: the same formatted text, none of the doors: no
    // controls, box press or editing shortcuts. Quoting gates the action channel, not
    // presentation.
    if (h.props.exhibit) return face;
    const { editing, failed, typing, pointed } = model;
    return face.children(
      h.div
        .class("lf-draft-room")
        .onMount(
          EditDraft({ saved, available, named: h.props.named, editing, failed }),
        ),
      // A refused save's status stands in the toolbar, before its marks, so saying it
      // moves no words either.
      h.div
        .attrs(offerAttributes("div", "lf-draft-tools lf-mark-bar"))
        .attr("data-lf-runtime", "")
        // Its marks join into one toolbar (controls.css, `data-lf-joined`).
        .attr("data-lf-joined", "")
        .attr("data-lf-typing", typing ? "" : undefined)
        .attr("data-lf-pointed", pointed ? "" : undefined)
        .children(
          h.span
            .attrs(offerAttributes("span", "lf-draft-status"))
            .attr("role", "status")
            .attr("hidden", failed ? undefined : "")
            .children(failed ? "Save failed. The edit is kept." : ""),
          ...TOOLS.map(([key, action]) =>
            h.button
              .attr("data-lf-draft-action", key)
              .attr("hidden", (key === "edit" ? editing : !editing) ? "" : undefined)
              .attr("aria-expanded", key === "edit" ? String(editing) : undefined)
              .onMount(
                OfferMark({ action: key === "save" && failed ? "retry" : action }),
              ),
          ),
        ),
    );
  },
});

defineWidget("lf-draft", Draft, {
  // The draft as the rest of the chrome names it, never by its id.
  inputs: (element) => {
    const label = nameOf(element);
    return {
      exhibit: element.matches("[data-lf-exhibit] *"),
      named: label ? `“${label}”` : `the ${addressableWord(element)}`,
    };
  },
  statics: {
    // What the obligation was answered with: the current words, read as the body draws
    // them, as a Markdown file.
    answerWords(value: unknown) {
      if (typeof value !== "string")
        throw new Error("A draft answer must be Markdown text");
      return markdownWords(value, false).trim() || "Empty";
    },
  },
});
