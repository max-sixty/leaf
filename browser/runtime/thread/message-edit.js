/* The user rewriting a message of their own, where the message stands.

   A message the user wrote with words is theirs to rewrite (`editable`), and the rewrite
   is a turn the agent answers (events.md, `edit`). Two facts make up a rewrite, each
   with the owner its kind has elsewhere:

   - Its words are a draft under `rewrite:<message id>` (drafts.js), once the user
     changes them, so they survive a reload, reach every tab, and come back on a
     refusal. Escape, Discard and Save settle them; words left by a reload or a refusal
     wait in the draft, the message saying it holds them (`keptRewrite`), and opening the
     rewrite again finds them. Words the message already says, and no words at all, are
     no rewrite: neither is kept, and a box with no draft holds the message's own words,
     in this tab and in every other.
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
   the rewrite, as in Slack, Discord and Telegram (the user's decision, 2026-10-06).
   Rejected: Escape keeping them as an unsaved edit, as a reply box keeps its draft,
   which left the user a draft to find and drop that the message could barely show.
   Android's back gesture, which may be an accidental edge swipe, keeps them instead
   (`keep`, keyboard/close-requests.js): the editor closes as on Escape, a notice says
   "Edit kept", and the message's head says "unsaved edit" until the user opens the
   rewrite again, which finds them, or Resume writing does. Back lands on the message's
   Edit control rather than the reply box, whose caret would raise a phone's keyboard.
   So an accidental Escape loses nothing for good: the last changed rewrite this
   document discarded stays in its memory until another takes its place or the document
   reloads, and Restore discarded edit (`g D`, a keyboard's convenience as Resume writing
   is, with no row on every page's menu) puts it back in its draft and opens its message on it. Recovery has no
   timer and never replaces words of the rewrite's own, open, sending or newer from
   another tab. The notice that follows a discard names the key.
   Rejected: a timed Undo chip after the discard, a target the user cannot learn
   (notifications.js), and a row of every page's menu for a pointer or finger, which put
   a command on each page for a mishap of one keyboard gesture (the user's decision).

   The editor stands where the message stood and as it read (browser/AGENTS.md,
   "Editing in place"): a comment box over the message's body, every line of its words
   where it stood and broken where it broke, its pictures under them as the message
   draws them (`sentMedia`), each with the removal mark a rewrite adds, and the field's
   frame and padding in the room around them (response.css, `.lf-msg-editor`). Discard
   and Save stand at the message's head as glyphs, where its own control stood
   (`.lf-msg-edit-actions`), covering the end of the head's labels while they show, so
   the head's words stay where they stood. The thread's Resolve leaves its row while the
   rewrite is open (response.css), and a message of pictures alone gains the line the
   caret needs for words.
   Rejected, by the user on 2026-10-22: the thread's reply box at its own width and
   padding, which they chose on 2026-10-13, with the pictures in a draft's cropped shelf
   over it, which pushed the words down by the pictures' height and rewrapped them in
   the panel. Rejected before that: a box painted around the words with no padding of
   its own, which read as a thinner field than the reply box beside it.

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
   puts this one aside, keeping them. The
   editor is a rung below the thread's reply box, so Enter, Escape and Discard each hand
   the user to that box, or, in a thread showing none, onto the thread (`land`). Save sends
   through the one ledger, which draws the new words on the message in the gesture
   (`foldThreads`), and a refusal gives its words back to the draft, the message saying
   it holds them beside the words it stands at. A rewrite names the revision it was
   written over, and the log refuses it once another tab has rewritten the message
   since; opening a rewrite shows what its thread holds, so it starts from the words as
   they stand. Until the user changes them, the editor follows the message: a rewrite
   the reader draws on it, such as one held back as news until the editor opened,
   moves the editor's words and revision too. Words the message already says are no
   rewrite, so saving them closes the editor and sends nothing. */
import {
  clearDraft,
  draftHasContent,
  rewriteContext,
  forgetWritingPlace,
  loadDraft,
  loadDraftPayload,
  mirrorDraft,
  restoreDraft,
  saveDraft,
  sendDraft,
  tellDraft,
  watchDraft,
} from "../drafts.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { caretAtKey, focusDestination } from "../focus.js";
import { seenRect } from "../geometry.js";
import { revealEditor } from "./reply-landing.js";
import { PENDING } from "./identity.js";
import { keys } from "../keyboard/scopes.js";
import { announce, notice } from "../notifications.js";
import { afterScript, sizeObserver } from "../rendering.js";
import { whenDocumentPresented } from "../semantic-state.js";
import { retainUserIntent } from "../user-intent.js";
import { nameAction, offer } from "../widget-elements.js";
import { raiseError } from "../errors.js";
import { signal } from "/runtime/framework.js";

// What a message's view answers by opening its rewrite, as a press on its Edit control.
export const OPEN_MESSAGE_EDIT = "lf-open-message-edit";
// message id -> {view, thread}: the view drawing its editor, null once that view is
// gone, and the key of its thread.
const open = new Map();
// Rewrites whose words are on their way to the log: neither open nor kept.
const sending = new Set();
// The changed words this document's latest discard threw away, with the revision they
// were written over: values, never the closed editor. Not a draft, so the discard still
// settles that draft in every tab and Resume writing goes back where it went before.
let discarded = null;

// Restore discarded edit: the words go back to the rewrite's draft, and its message
// opens on them as it does on words a reload kept, the editor raising its warning where
// the message changed since. Words of the rewrite's own, open, sending or in another
// tab, are newer, so the command stands dead over them.
export function createRewriteRestore({ revealInThread, holdsThreadDraft }) {
  const restorable = () =>
    discarded &&
    !open.has(discarded.id) &&
    !draftHasContent(rewriteContext(discarded.id)) &&
    holdsThreadDraft(rewriteContext(discarded.id));
  return {
    id: "message.edit.restore",
    keys: ["Shift+d"],
    title: "Restore discarded edit",
    touch: "Restore discarded edit",
    menu: "keys",
    when: () => Boolean(restorable()),
    run: async () => {
      if (!restorable()) return;
      const { id, text, over } = discarded;
      const ctx = rewriteContext(id);
      if (!restoreDraft(ctx, text, { over })) return;
      discarded = null;
      await revealInThread(ctx, retainUserIntent());
    },
  };
}

// Moves each time any reader draws a message (`messageDrawn`, called by
// MessageView.present). Which of the user's messages can be rewritten is read off the
// views a reader drew, so the reply box's ↑ row reads this to be reflected again
// whenever a draw may have changed that (keyboard/scopes.js), whichever reader drew.
const drawn = signal(0);
export const messageDrawn = () => {
  drawn.value = drawn.peek() + 1;
};

// Whether `view` draws the editor for message `id`: the view holding it, or the first to
// ask once no view does.
export function holdsMessageEdit(id, view) {
  const holder = open.get(id);
  if (!holder) return false;
  if (holder.view !== null && holder.view !== view) return false;
  holder.view = view;
  return true;
}

// The view drawing `id`'s editor is gone; the next view of the message takes it.
export function releaseMessageEdit(id, view) {
  const holder = open.get(id);
  if (holder?.view === view) holder.view = null;
}

// Open a rewrite of `id`, a message of thread `thread`, in `view`. A view drawing it
// elsewhere, in another reader of the thread, draws the message as it stands again, so
// one editor shows it; and one rewrite stands open in a thread unless the user changed
// its words, so another left as its message says it closes, whichever reader holds it.
function openMessageEdit(id, view, thread) {
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
export const keptRewrite = (id) =>
  !open.has(id) && !sending.has(id) && draftHasContent(rewriteContext(id));

// Call `changed` on news of the words of a rewrite of `id`, from this tab or another.
// Returns the unsubscribe.
export const watchRewrite = (id, changed) => watchDraft(rewriteContext(id), changed);

// Open the rewrite of message `id` where `thread`, a drawn thread, shows it, and answer
// the box its words are in: none where the thread does not draw that message as one the
// user may rewrite.
export function openMessageEditIn(thread, id) {
  const message = [...(thread?.querySelectorAll(".lf-msg") ?? [])].find(
    (node) => node.dataset.event === id,
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
 * `views` answers the reader's MessageViews of the thread in its order; `send` posts a
 * rewrite of message `id`; `paint(node)` draws the view at `node` again at once;
 * `box` answers the thread's reply box, or null where the reader shows none; `home(node)`
 * answers the drawn thread around message `node`, which the user is on once the
 * editor goes where the box is out of view; `opening(id)` is the reader's own share of
 * a rewrite of `id` opening, such as unfolding the summary that holds it; `thread`
 * answers the thread's key, which every reader of it shares.
 *
 * @param {{
 *   thread: () => string,
 *   views: () => any[],
 *   send: (id: string, text: string, options: any) => any,
 *   paint: (node: any) => void,
 *   box: () => HTMLElement | null,
 *   home: (node?: Element) => Element,
 *   opening?: (id: string) => void,
 *   landInThread?: any,
 *   landSent?: any,
 * }} reader */
export function threadRewrites({
  thread,
  views,
  send,
  paint,
  box,
  home,
  opening = () => {},
  landInThread,
  landSent,
}) {
  // The view of the user's latest words the reader draws, or the latest before message
  // `before`, which ↑ opens: from the empty reply box, or from the start of a rewrite
  // already open. A message with no words, such as a bare drawing, is passed over; none
  // while the words found cannot be rewritten, such as a message still sending, rather
  // than older words.
  const lastEditable = (before = null) => {
    const drawn = views();
    const end =
      before === null
        ? drawn.length
        : drawn.findIndex(({ model }) => model?.id === before);
    const view = drawn
      .slice(0, Math.max(end, 0))
      .findLast(
        ({ model }) =>
          model?.author === "user" && model.body.kind !== "reaction" && model.body.text,
      );
    return view?.model.editable ? view : null;
  };
  return {
    edit: {
      paint,
      send,
      // The rung above a rewrite is the thread's reply box, where ↑ came from, while it
      // is in view; a thread showing none, as a resolved one or a margin card not
      // replying, or one whose box is off screen, hands the user on as a sent reply
      // does, which moves nothing. A save in a resolved thread reopens it, so the box
      // its presentation draws then takes the caret, as Reopen's landing gives it
      // (#46, the user's decision, 2026-10-07).
      land: (message) => {
        const shown = () => {
          const input = box();
          return input && seenRect(input, new Map()) ? input : null;
        };
        const input = shown();
        if (input) return landInThread(input);
        landSent(home(message));
        const mayLand = retainUserIntent();
        void whenDocumentPresented().then(() => {
          const drawn = shown();
          if (drawn && mayLand()) landInThread(drawn);
        });
      },
      previous: (id) => lastEditable(id),
      // A rewrite of message `id` opens in `view`. It starts from the words as they
      // stand, so opening one is acting in the thread (`openMessageEdit`).
      opening: (id, view) => {
        opening(id);
        openMessageEdit(id, view, thread());
      },
      reveal: (message, caretLine) => revealEditor(message, caretLine),
    },
    editLast: {
      available: () => {
        void drawn.value;
        return Boolean(lastEditable());
      },
      open: () => lastEditable()?.openEdit(),
    },
  };
}

function closeMessageEdit(id, { discard }) {
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
  #stop;
  #putAside;
  #reveal;
  #settling = null;
  #follow;

  constructor(
    id,
    view,
    { wireInput, said, base: currentBase, send, land, paint, previous, reveal },
  ) {
    const ctx = rewriteContext(id);
    // The revision these words are written over, which the log holds the rewrite to: the
    // message as it stands now. Words kept from an earlier opening carry the revision
    // they were written over; where the message has changed since, the user is told what
    // it says now before the kept words go over it.
    let base = currentBase();
    const keptOver = loadDraftPayload(ctx)?.over;
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
    const actions = offer("span", "lf-msg-edit-actions");
    const cancel = offer("button", "lf-msg-control lf-msg-edit-cancel");
    cancel.type = "button";
    nameAction(cancel, "discard", { className: "lf-msg-control-icon" });
    actions.append(cancel);
    // The box's last line, where the caret stands on opening: the field's own lines are
    // in a closed tree, so a mark of no size after it is what a reveal can aim at.
    this.foot = document.createElement("span");
    this.foot.className = "lf-msg-edit-foot";
    this.node.append(this.input, actions);
    // The words a closed rewrite left, or the message's own. An empty draft is none.
    this.input.value = loadDraft(ctx) || said();
    // Until the user changes them, the words are the message's, so a rewrite the view
    // draws on the message meanwhile, as one a reader held back as news while this
    // opened, carries them and its revision with it: Save then writes over what the
    // message says, rather than sending the old words over the new revision, which
    // the log refuses.
    // The rewrite whole, its words and its pictures, as the box holds it: `.value` is
    // the words alone (input.js, `sync.value`), so a picture taken off changes only this.
    const whole = () => sync.value();
    let opened = null;
    this.#follow = () => {
      if (base === currentBase() || draftHasContent(ctx) || whole() !== opened) return;
      base = currentBase();
      sync.load((opened = said()));
    };
    // What the message already says, exactly, and nothing at all, are no change. Leading
    // and trailing space is part of what a rewrite sends, as a suggestion's newline is.
    const unchanged = () => {
      const now = whole();
      return !now.trim() || now === said();
    };
    const leave = (discard, { landing = true, says = null, painting = true } = {}) => {
      if (landing) land();
      // A closing box shows no more of its draft: settled by a save, it would refill
      // with the message's old words before the paint that takes it away.
      this.#stop();
      closeMessageEdit(id, { discard });
      if (painting) paint();
      if (says) announce(says);
    };
    // Closing as Escape and Discard do, throwing away what changed.
    const close = () => {
      if (unchanged()) return leave(true, { says: "Stopped editing" });
      discarded = { id, text: whole(), over: base };
      leave(true);
      notice("Edit discarded; g D restores it");
    };
    // Back's way out (`keep`, keyboard/close-requests.js): closing as Escape does, but
    // changed words stay in the draft, which the message says it holds, and opening the
    // rewrite again finds them. The user lands on the message's Edit control, beside
    // that sign, rather than in the reply box, whose caret would raise a phone's
    // keyboard just as back put it away and would cover the notice.
    const keep = () => {
      if (unchanged()) return close();
      const message = this.node.closest(".lf-msg");
      leave(false, { landing: false });
      const reopen = message?.querySelector(".lf-msg-edit");
      if (reopen) focusDestination(reopen, "return");
      notice("Edit kept");
    };
    // Making way for another rewrite, as ↑ to an earlier message or opening one
    // elsewhere in the thread does, closes one the user has not changed; changed words
    // stay in their box, which no key here meant to put away. The closed box is drawn
    // away once the script ends, so a reader drawing the other one's opening meanwhile
    // draws both in one paint, rather than the thread shrinking and growing back.
    const putAside = () => {
      if (!unchanged()) return;
      leave(true, { landing: false, painting: false });
      afterScript(paint);
    };
    this.#putAside = putAside;
    const sync = wireInput(this.input, {
      hint: "Edit message",
      accessibleName: () => `Edit message: ${said().slice(0, 60)}`,
      sends: "save",
      sendClass: "lf-msg-control lf-msg-edit-save",
      action: "save",
      submitIn: actions,
      sentMedia: true,
      save: (value) => {
        saveDraft(ctx, value, { over: base });
        tellDraft(ctx, value, { over: base });
      },
      send: async (_text, raw, owns) => {
        if (unchanged()) return leave(true, { says: "No change to save" });
        sending.add(id);
        // The send's own paint, which draws the new words on the message, closes the
        // editor too, so the message changes once: a paint of its own here drew the old
        // words between the box and the new ones.
        const flight = sendDraft(ctx, owns, (attempt) => send(raw, { attempt, base }));
        leave(false, { painting: false });
        let sent = null;
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
            putAside();
            before.openEdit();
          },
        },
      ],
    });
    // Escape answers on the editor's controls as in its words, so it is the editor's
    // own scope, around both, rather than a row of the text box alone; closing is a step
    // ahead of the ladder's way out of a text box.
    opened = whole();
    // The foot follows the words, ahead of the message's pictures under them.
    this.input.after(this.foot);
    keys(
      this.node,
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
    this.#stop = mirrorDraft(this.input, sync, ctx, { retained: true, blank: said });
  }

  // Put the user on the words with the caret after them, where a rewrite usually starts,
  // and bring the editor into view, its last line, where the caret stands, at least. A
  // long one's lines take their height only as the field draws them, after this, so the
  // reveal follows the box's size until the user does anything. Every opening is the
  // user's own gesture, so the arrival is a move.
  enter() {
    const end = this.input.value.length;
    focusDestination(this.input, "move", { caret: [end, end] });
    this.#reveal(this.foot);
    this.#settling?.disconnect();
    const mayReveal = retainUserIntent();
    this.#settling = sizeObserver((entries, observer) => {
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
