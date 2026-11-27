/* The user rewriting a message of their own, where the message stands.

   A message the user wrote with words is theirs to rewrite (`editable`), and the rewrite
   is a turn the agent answers (events.md, `edit`). Two facts make up a rewrite, each
   with the owner its kind has elsewhere:

   - Its words are a draft under `rewrite:<message id>` (records/drafts.js), once the user
     changes them, so they survive a reload, reach every tab, and come back on a
     refusal. Escape, Discard and Save settle them; words left by a reload or a refusal
     wait in the draft, the message saying it holds them (`keptRewrite`), and opening the
     rewrite again finds them. Words the message already says, and no words at all, are
     no rewrite to keep: neither is kept, and a box with no draft holds the message's own
     words, in this tab and in every other.
   - That an editor stands open is disclosure, this document's mechanical state, held
     here by message id. One view of the message draws it: the one it was opened in,
     or, once that view is gone, the next view of the message, which takes the editor as
     a replacement node takes words and caret. A view in another tab draws the message as
     it was, since nothing the user did there asked it to change. A thread
     holds one open editor whose words are the message's own: opening another closes
     it, as ↑ to an earlier message does. One whose words the user changed stays open
     until a key or press of theirs puts it away, so a second press elsewhere in the
     thread opens a second editor beside it, each named for its message.

   Escape discards changed words, as Discard does, so one Escape undoes the ↑ that opened
   the rewrite, as in Slack, Discord and Telegram (the user's decision).
   Rejected: Escape keeping them as an unsaved edit, as a reply box keeps its draft,
   which left the user a draft to find and drop that the message could barely show.
   Android's back gesture, which may be an accidental edge swipe, keeps them instead
   (`keep`, dom/keyboard/close-requests.js): the editor closes as on Escape, a notice says
   "Edit kept", and the message's head says "unsaved edit" until the user opens the
   rewrite again, which finds them, or Resume writing does. Back lands on the message's
   Edit control rather than the reply box, whose caret would raise a phone's keyboard.
   So an accidental Escape or Discard loses nothing for good: ⌘Z puts the discarded
   words back in the rewrite's draft and opens its message on them (records/undo.js,
   `takeDiscard`). Where the close leaves the user decides when ⌘Z reaches it (below).
   On the message's Edit control ⌘Z is Leaf's, and the discard's notice shows its Undo
   at once. The thread's reply box keeps ⌘Z for its own words, so from there ⌘Z
   reaches the discard once the user leaves the box, and the notice shows its Undo
   then. The notice answers the user's own gesture with a press, so it stays past its
   time until the first input after it (transport/notifications.js, `showNotice`), and the
   Escape that leaves the box within that time shows its Undo.

   The editor stands where the message stood and as it read (browser/AGENTS.md,
   "Typed words survive"): a comment box over the message's body, every line of its words
   where it stood and broken where it broke, its pictures under them as the message
   draws them (`sentMedia`), each with the removal mark a rewrite adds, and the field's
   frame and padding in the room around them (response.css, `.lf-msg-editor`). Discard
   and Save stand among the message's head controls as glyphs, where its Edit stood
   (`.lf-msg-edit-actions`), standing over the end of a short head's labels on the
   message's ground (controls.css), so the head's words stay where they stood. The
   thread's Resolve leaves its row while the
   rewrite is open (response.css), and a message of pictures alone gains the line the
   caret needs for words.
   Rejected, by the user: the thread's reply box at its own width and
   padding, with the pictures in a draft's cropped shelf
   over it, which pushes the words down by the pictures' height and rewraps them in
   the panel. Rejected too: a box painted around the words with no padding of
   its own, which reads as a thinner field than the reply box beside it.

   A double click on the message or a press on its Edit control opens it. The keyboard
   opens it with ↑: from the thread's empty reply box, the user's latest message, and
   from the start of an open rewrite not yet changed, their message before it, so Edit
   takes no Tab stop in every thread the user opened. A resolved card shows no reply
   box; Enter on it reopens it into that box, as replying there starts, since a saved
   rewrite reopens it anyway, and ↑ goes on from there. Every reader that draws a
   message offers its rewrite, a package's primary reader drawing it on its own as Feed
   mode does among them: one owner per thread (`threadRewrites`) gives each the same
   ↑, landing and putting aside, over the views that reader draws. Resume writing
   (`g i`) opens a rewrite whose words were kept on the message where a message part
   opens (`openMessageEditIn`). Opening brings the editor into view. Enter saves; Escape and
   Discard close it, throwing away changed words; opening another rewrite in the thread
   puts this one aside, keeping them. Escape and Discard take back the gesture that
   opened the rewrite, so they return the user to where that gesture started (the
   user's decision). A rewrite ↑ opened is a rung below the thread's reply box, and
   closing it hands the user to that box, or, in a thread showing none, onto the thread
   (`land`). A rewrite opened on its message, by a press on Edit, a double click,
   Resume writing or ⌘Z, returns the user to the message's Edit control, where Back
   lands too.
   Rejected: every close handing the user to the reply box, where ⌘Z is the box's own,
   so after a stray press on Discard ⌘Z seemed to do nothing and no Undo showed until
   the user left the box. Enter leaves the box for the thread, as every send does (`saved`;
   records/thread/landing.js, `landSent`), whether it saves words or finds none changed; `c`
   then ↑ opens the next rewrite. The user chose the thread for a send; Save follows
   because a key pressed just after it most often leaves the box for the thread, and in
   the box a walk key types a letter.
   Rejected: Save handing the user back to the reply box, ↑'s rung, where that letter
   landed, or, in a resolved thread the save reopens, to the box it then draws. Save sends
   through the one ledger, which draws the new words on the message in the gesture
   (`foldThreads`), and a refusal gives its words back to the draft, the message saying
   it holds them beside the words it stands at. A rewrite names the revision it was
   written over, and the log refuses it once another tab has rewritten the message
   since; opening a rewrite shows what its thread holds, so it starts from the words as
   they stand. Until the user changes them, the editor follows the message: a rewrite
   the reader draws on it, such as one held back as news until the editor opened,
   moves the editor's words and revision too. Words the message already says are no
   rewrite, so saving them closes the editor and sends nothing. Saving no words at all
   deletes the message (events.md, "Messages"), which then reads Deleted in its place
   (messages.js): a box emptied of words says so before the press, its field reading
   Delete message and its Save turning to Delete, so no dialog asks again: ⌘Z takes a
   saved rewrite back, a deletion as any other (records/undo.js).
   Rejected: refusing an empty rewrite, which left a Save that drew as live and did
   nothing, so the user typed a placeholder such as "[removed]" over their words (the
   user's decision); and deleting by withdrawing the message (`undo`),
   which nothing could then take back, as ⌘Z takes back a deletion. ⌘Z withdraws the
   message the user sent last instead, and the empty save deletes an older one (the
   user's decision). */
import {
  clearDraft,
  discardDraft,
  draftHasContent,
  rewriteContext,
  forgetWritingPlace,
  loadDraft,
  mirrorDraft,
  saveDraft,
  sendDraft,
  tellDraft,
  watchDraft,
} from "../drafts.js";
import { TEXT_FIELD } from "../../dom/control-selectors.js";
import { caretAtKey, focusDestination } from "../../dom/focus.js";
import { seenRect } from "../../dom/geometry.js";
import { revealEditor } from "./reply-landing.js";
import { PENDING } from "../../state/thread/identity.js";
import { keys } from "../../dom/keyboard/scopes.js";
import { announce, notice } from "../../transport/notifications.js";
import { afterScript } from "../../base/rendering.js";
import { sizeObserver } from "../../lib/frame-pass.js";
import { retainUserIntent } from "../../dom/user-intent.js";
import { offer, offerAction } from "../../lib/controls.js";
import { raiseError } from "../../transport/errors.js";
import { signal } from "/vendor/signals-core.js";
import type { MessageView } from "./messages.js";
import type { createThreadActions } from "./actions.js";
import type { WireInput } from "../composition-input.js";
import type { LeafTextElement } from "../../annotations/composing/text-field.js";

type EditOptions = NonNullable<
  Parameters<ReturnType<typeof createThreadActions>["edit"]>[3]
>;
type SendRewrite = (
  text: string,
  options: EditOptions,
) => ReturnType<ReturnType<typeof createThreadActions>["edit"]>;
type EditorCommands = {
  wireInput: WireInput;
  said: () => string;
  base: () => string;
  send: SendRewrite;
  land: () => unknown;
  saved: () => unknown;
  paint: () => void;
  previous: () => MessageView | null;
  reveal: (caretLine: Element) => void;
};

// What a message's view answers by opening its rewrite, as a press on its Edit control.
export const OPEN_MESSAGE_EDIT = "lf-open-message-edit";
// message id -> {view, thread}: the view drawing its editor, null once that view is
// gone, and the key of its thread.
const open: Map<string, { view: MessageView | null; thread: string }> = new Map();
// Rewrites whose words are on their way to the log: neither open nor kept.
const sending = new Set<string>();
// Moves each time any reader draws a message (`messageDrawn`, called by
// MessageView.present). Which of the user's messages can be rewritten is read off the
// views a reader drew, so the reply box's ↑ row reads this to be reflected again
// whenever a draw may have changed that (dom/keyboard/scopes.js), whichever reader drew.
const drawn = signal(0);
export const messageDrawn = () => {
  drawn.value = drawn.peek() + 1;
};

// Whether `view` draws the editor for message `id`: the view holding it, or the first to
// ask once no view does.
export function holdsMessageEdit(id: string, view: MessageView) {
  const holder = open.get(id);
  if (!holder) return false;
  if (holder.view !== null && holder.view !== view) return false;
  holder.view = view;
  return true;
}

// The view drawing `id`'s editor is gone; the next view of the message takes it.
export function releaseMessageEdit(id: string, view: MessageView) {
  const holder = open.get(id);
  if (holder?.view === view) holder.view = null;
}

// Open a rewrite of `id`, a message of thread `thread`, in `view`. A view drawing it
// elsewhere, in another reader of the thread, draws the message as it stands again, so
// one editor shows it; and one rewrite stands open in a thread unless the user changed
// its words, so another left as its message says it closes, whichever reader holds it.
function openMessageEdit(id: string, view: MessageView, thread: string) {
  for (const [other, holder] of [...open]) {
    if (other === id || holder.thread !== thread) continue;
    // One no view draws any longer closes as an editor would: words the user left as
    // they were leave no draft to keep it open.
    if (holder.view) holder.view.putEditAside();
    else if (!draftHasContent(rewriteContext(other))) open.delete(other);
  }
  const displaced = open.get(id)?.view;
  open.set(id, { view, thread });
  if (displaced && displaced !== view) displaced.closeEdit();
}

// Whether a rewrite of `id` holds words no editor shows: a reload's or a refusal's.
export const keptRewrite = (id: string) =>
  !open.has(id) && !sending.has(id) && draftHasContent(rewriteContext(id));

// Call `changed` on news of the words of a rewrite of `id`, from this tab or another.
// Returns the unsubscribe.
export const watchRewrite = (id: string, changed: () => void) =>
  watchDraft(rewriteContext(id), changed);

// Open the rewrite of message `id` where `thread`, a drawn thread, shows it, and answer
// the box its words are in: none where the thread does not draw that message as one the
// user may rewrite.
export function openMessageEditIn(thread: Element | null, id: string) {
  const message = [...(thread?.querySelectorAll(".lf-msg") ?? [])].find(
    (node) => node.getAttribute("data-lf-event") === id,
  );
  message?.dispatchEvent(new CustomEvent(OPEN_MESSAGE_EDIT));
  return (
    message?.querySelector(`:scope > .lf-msg-body > .lf-msg-editor ${TEXT_FIELD}`) ??
    null
  );
}

/** One thread's rewrites as a reader draws them, whatever shape it lays the thread out
 * in: a whole card, or a package's parts, such as Feed mode's one message each. Each
 * view of a message in the thread takes `edit`, as its commands' `edit`; the reader's
 * reply box takes `editLast`, its ↑ route.
 *
 * `views` answers the reader's MessageViews of the thread in its order;
 * `paint(node)` draws the view at `node` again at once;
 * `box` answers the thread's reply box, or null where the reader shows none; `home(node)`
 * answers the drawn thread around message `node`, which the user is on once the
 * editor goes where the box is out of view; `opening(id)` is the reader's own share of
 * a rewrite of `id` opening, such as unfolding the summary that holds it. The message
 * reading carries its owning thread key; the view sends through ThreadActions directly. */
export function threadRewrites({
  views,
  paint,
  box,
  home,
  opening = () => {},
  landInThread,
  landSent,
}: {
  views: () => readonly MessageView[];
  paint: (node: Element) => void;
  box: () => Element | null;
  home: (node?: Element) => Element;
  opening?: (id: string) => void;
  landInThread: typeof import("./landing.js").landInThread;
  landSent: typeof import("./landing.js").landSent;
}) {
  // The view of the user's latest words the reader draws, or the latest before message
  // `before`, which ↑ opens: from the empty reply box, or from the start of a rewrite
  // already open. A message with no words, such as a bare drawing, is passed over; none
  // while the words found cannot be rewritten, such as a message still sending, rather
  // than older words.
  const lastEditable = (before: string | null = null) => {
    const drawn = views();
    const end =
      before === null
        ? drawn.length
        : drawn.findIndex(({ model }) => model?.id === before);
    const view = drawn
      .slice(0, Math.max(end, 0))
      .findLast(
        (view): view is MessageView & { model: NonNullable<MessageView["model"]> } => {
          const model = view.model;
          return (
            model?.author === "user" &&
            model.body.kind !== "reaction" &&
            Boolean(model.body.text)
          );
        },
      );
    return view?.model.editable ? view : null;
  };
  return {
    edit: {
      paint,
      // The rung above a rewrite Escape or Discard takes back is the thread's reply box,
      // where ↑ came from, while it is in view; a thread showing none, as a resolved
      // one, or one whose box is off screen, hands the user on as a send does.
      land: (message: Element) => {
        const input = box();
        if (input && seenRect(input, new Map())) landInThread(input);
        else landSent(home(message));
      },
      // A save lands on the thread, as every send does.
      saved: (message: Element) => landSent(home(message)),
      previous: (id: string) => lastEditable(id),
      // A rewrite of message `id` opens in `view`. It starts from the words as they
      // stand, so opening one is acting in the thread (`openMessageEdit`).
      opening: (
        message: Pick<NonNullable<MessageView["model"]>, "id" | "thread">,
        view: MessageView,
      ) => {
        opening(message.id);
        openMessageEdit(message.id, view, message.thread);
      },
      reveal: (message: Element, caretLine: Element) =>
        revealEditor(message, caretLine),
    },
    editLast: {
      available: () => {
        void drawn.value;
        return Boolean(lastEditable());
      },
      open: () => lastEditable()?.openEdit({ walked: true }),
    },
  };
}

function closeMessageEdit(id: string, { discard }: { discard: boolean }) {
  open.delete(id);
  if (!discard) return;
  const ctx = rewriteContext(id);
  clearDraft(ctx);
  tellDraft(ctx, null);
  forgetWritingPlace(ctx);
}

/** One view's editor over one message's rewrite.
 *
 * `said` reads the message's words now, and `base` the revision they are; `send`
 * posts the rewrite, written over the revision the editor opened on, through the
 * thread's typed action and returns its answer; `land` puts the user back on the thread's reply
 * box, or on the thread where it shows none, before the editor leaves the page; `paint`
 * draws the view again once the editor opens or closes; `previous` answers the view of
 * the user's message before this one that ↑ opens, or null; `reveal` brings the open
 * editor into view. */
export class MessageEditor {
  declare node: HTMLDivElement;
  declare input: LeafTextElement;
  declare actions: HTMLSpanElement;
  declare foot: HTMLSpanElement;

  // Whether ↑ opened the rewrite, so closing it goes back up ↑'s rung (`enter`).
  #walked = false;
  #stop;
  #putAside;
  #reveal;
  #settling: ResizeObserver | null = null;
  #follow;

  constructor(
    id: string,
    {
      wireInput,
      said,
      base: currentBase,
      send,
      land,
      saved,
      paint,
      previous,
      reveal,
    }: EditorCommands,
  ) {
    const ctx = rewriteContext(id);
    // The revision these words are written over, which the log holds the rewrite to: the
    // message as it stands now. Words kept from an earlier opening carry the revision
    // they were written over; where the message has changed since, the user is told what
    // it says now before the kept words go over it.
    let base = currentBase();
    const kept = loadDraft(ctx);
    const payload = kept?.payload;
    const keptOver =
      payload && "over" in payload && typeof payload.over === "string"
        ? payload.over
        : null;
    // Words kept over the user's own edit still sending name it by its pending id, which
    // is no change of anyone else's.
    if (keptOver && keptOver !== base && !keptOver.startsWith(PENDING))
      raiseError(
        `This message changed since this edit began. It now says: “${said()}”`,
      );
    this.#reveal = reveal;
    this.node = offer("div", "lf-msg-editor lf-comment-box");
    this.input = offer(TEXT_FIELD);
    this.input.name = "edit";
    // Discard and Save, which the message draws among its head's controls.
    const actions = (this.actions = offer("span", "lf-msg-edit-actions"));
    const cancel = offerAction(
      "symbol",
      "lf-msg-control lf-msg-edit-cancel",
      undefined,
      {
        action: "discard",
      },
    );
    cancel.type = "button";
    actions.append(cancel);
    // The box's last line, where the caret stands on opening: the field's own lines are
    // in a closed tree, so a mark of no size after it is what a reveal can aim at.
    this.foot = document.createElement("span");
    this.foot.className = "lf-msg-edit-foot";
    this.node.append(this.input);
    // The words a closed rewrite left, or the message's own. An empty draft is none.
    this.input.value = kept?.text || said();
    // Until the user changes them, the words are the message's, so a rewrite the view
    // draws on the message meanwhile, as one a reader held back as news while this
    // opened, carries them and its revision with it: Save then writes over what the
    // message says, rather than sending the old words over the new revision, which
    // the log refuses.
    // The rewrite whole, its words and its pictures, as the box holds it: `.value` is
    // the words alone (input.js, `sync.value`), so a picture taken off changes only this.
    // Until the box is wired, its field holds them whole.
    let sync: ReturnType<typeof wireInput> | null = null;
    const whole = () => sync?.value() ?? this.input.value;
    let opened: string | null = null;
    this.#follow = () => {
      if (base === currentBase() || draftHasContent(ctx) || whole() !== opened) return;
      base = currentBase();
      sync?.load((opened = said()));
    };
    // What the message already says, exactly, and nothing at all, leave no rewrite to
    // keep, take back or walk past. Leading and trailing space is part of what a rewrite
    // sends, as a suggestion's newline is.
    const emptied = () => !whole().trim();
    const unchanged = () => emptied() || whole() === said();
    // Where the user goes as the box closes: back up its rung (`land`), onto the thread
    // a save leaves them on (`saved`), or nowhere, for a close that lands them itself.
    const leave = (
      discard: boolean,
      {
        landing = land,
        says = null,
        painting = true,
      }: {
        landing?: (() => unknown) | null;
        says?: string | null;
        painting?: boolean;
      } = {},
    ) => {
      landing?.();
      // A closing box shows no more of its draft: settled by a save, it would refill
      // with the message's old words before the paint that takes it away.
      this.#stop();
      closeMessageEdit(id, { discard });
      if (painting) paint();
      if (says) announce(says);
    };
    // The message's Edit control, which reopens its words, drawn once the editor has
    // gone: false where the message draws none.
    const toEdit = (message: Element | null) => {
      const control: HTMLButtonElement | null | undefined =
        message?.querySelector(".lf-msg-edit");
      if (control) focusDestination(control, "return");
      return Boolean(control);
    };
    // Closing as Escape and Discard do, throwing away what changed, which ⌘Z brings
    // back (records/undo.js, `keepDiscard`), and returning the user to where the rewrite was
    // opened (the header): up ↑'s rung, or onto the message's Edit control.
    const close = () => {
      const says = unchanged() ? "Stopped editing" : null;
      if (!says) discardDraft(ctx);
      if (this.#walked) return leave(true, { says });
      const message = this.node.closest(".lf-msg");
      leave(true, { landing: null, says });
      if (!toEdit(message)) land();
    };
    // Back's way out (`keep`, dom/keyboard/close-requests.js): closing as Escape does, but
    // changed words stay in the draft, which the message says it holds, and opening the
    // rewrite again finds them. The user lands on the message's Edit control, beside
    // that sign, rather than in the reply box, whose caret would raise a phone's
    // keyboard just as back put it away and would cover the notice.
    const keep = () => {
      if (unchanged()) return close();
      const message = this.node.closest(".lf-msg");
      leave(false, { landing: null });
      toEdit(message);
      notice("Edit kept");
    };
    // Making way for another rewrite, as ↑ to an earlier message or opening one
    // elsewhere in the thread does, closes one the user has not changed; changed words
    // stay in their box, which no key here meant to put away. The closed box is drawn
    // away once the script ends, so a reader drawing the other one's opening meanwhile
    // draws both in one paint, rather than the thread shrinking and growing back.
    const putAside = () => {
      if (!unchanged()) return;
      leave(true, { landing: null, painting: false });
      afterScript(paint);
    };
    this.#putAside = putAside;
    const wired = wireInput(this.input, {
      // The field shows its hint only once emptied, when saving deletes the message.
      hint: "Delete message",
      accessibleName: () => `Edit message: ${said().slice(0, 60)}`,
      sends: () => (emptied() ? "delete" : "save"),
      sendClass: "lf-msg-control lf-msg-edit-save",
      action: () => (emptied() ? "delete" : "save"),
      hasContent: () => true,
      submitIn: actions,
      sentMedia: true,
      save: (value) => {
        saveDraft(ctx, value, { over: base });
        tellDraft(ctx, value, { over: base });
      },
      send: async (_text, raw, owns) => {
        if (whole() === said())
          return leave(true, { landing: saved, says: "No change to save" });
        const deleting = emptied();
        sending.add(id);
        // The send's own paint, which draws the new words on the message, closes the
        // editor too, so the message changes once: a paint of its own here drew the old
        // words between the box and the new ones.
        const flight = sendDraft(ctx, owns, (attempt) =>
          send(deleting ? "" : raw, { attempt, base }),
        );
        leave(false, {
          landing: saved,
          painting: false,
          says: deleting ? "Message deleted" : null,
        });
        let sent;
        try {
          sent = await flight;
        } finally {
          sending.delete(id);
        }
        // Saved words leave nothing to resume. A refusal gives them back to the draft,
        // which the message says it holds beside the words it stands at: a message
        // another tab has since rewritten shows that rewrite, which an editor opened at
        // once would hide, and opening the words again writes them over what the user
        // can now see.
        if (sent) forgetWritingPlace(ctx);
        paint();
      },
      rows: [
        {
          id: "message.edit.previous",
          keys: ["ArrowUp"],
          description: "When the box is unchanged and the caret is at its start",
          title: "edit previous message",
          // A walk passes over words as they stand: words the user changed hold ↑ for
          // the caret, as a reply box holding words does, until Save or Escape. It
          // starts where the caret stood as the key went down, before the field's own ↑
          // took it to the start of a first line; a held ↑'s repeats run no row.
          when: () => {
            const [start, end] = caretAtKey(this.input) ?? [
              this.input.selectionStart,
              this.input.selectionEnd,
            ];
            return start === 0 && end === 0 && unchanged() && Boolean(previous());
          },
          run: () => {
            const before = previous();
            if (!before) return;
            putAside();
            before.openEdit({ walked: true });
          },
        },
      ],
    });
    sync = wired;
    opened = whole();
    // The foot follows the words, ahead of the message's pictures under them.
    this.input.after(this.foot);
    // Escape answers on the editor's controls as in its words, so it is a scope of the
    // editor's own, on the box and on its controls, rather than a row of the text box
    // alone; closing is a step ahead of the ladder's way out of a text box.
    for (const where of [this.node, actions])
      keys(
        where,
        "Editing a message",
        [
          {
            id: "message.edit.close",
            keys: ["Escape"],
            title: "discard",
            run: () => close(),
            keep,
          },
        ],
        { escape: "inner" },
      );
    cancel.addEventListener("mousedown", (event) => event.preventDefault());
    cancel.addEventListener("click", () => close());
    this.#stop = mirrorDraft(this.input, wired, ctx, { retained: true, blank: said });
  }

  // Put the user on the words with the caret after them, where a rewrite usually starts,
  // and bring the editor into view, its last line, where the caret stands, at least. A
  // long one's lines take their height only as the field draws them, after this, so the
  // reveal follows the box's size until the user does anything. Every opening is the
  // user's own gesture, so the arrival is a move; `walked` where it was ↑.
  enter({ walked = false } = {}) {
    this.#walked = walked;
    const end = this.input.value.length;
    focusDestination(this.input, "move", { caret: [end, end] });
    this.#reveal(this.foot);
    this.#settling?.disconnect();
    const mayReveal = retainUserIntent();
    this.#settling = sizeObserver((_entries, observer) => {
      if (!mayReveal() || !this.node.isConnected) return observer.disconnect();
      this.#reveal(this.foot);
    });
    this.#settling.observe(this.node);
  }

  // The message this rewrites stands as `said` and `base` now read it.
  follow() {
    this.#follow();
  }

  // Make way for another editor opening in the thread, without moving the user: close
  // this one where the user has changed nothing in it.
  putAside() {
    this.#putAside();
  }

  dispose() {
    this.#settling?.disconnect();
    this.#stop();
  }
}
