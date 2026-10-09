/* The user rewriting a message of their own, where the message stands.

   A message the user wrote with words is theirs to rewrite (`editable`), and the rewrite
   is a turn the agent answers (events.md, `edit`). Two facts make up a rewrite, each
   with the owner its kind has elsewhere:

   - Its words are a draft under `rewrite:<message id>` (drafts.js), once the user
     changes them, so they survive a reload, reach every tab, and come back on a
     refusal. Escape, Cancel and Save settle them; words left by a reload or a refusal
     wait in the draft, the message saying it holds them (`keptRewrite`), and opening the
     rewrite again finds them. Words the message already says, and no words at all, are
     no rewrite: neither is kept, and a box with no draft holds the message's own words,
     in this tab and in every other.
   - That an editor stands open is disclosure, this document's mechanical state, held
     here by message id. One view of the message draws it: the one it was opened in,
     or, once that view is gone, the next view of the message on the same surface
     (the Threads panel, or the page), which takes the editor as a replacement node
     takes words and caret. A view on the other surface, or in another tab, draws the
     message as it was, since nothing the user did there asked it to change. A thread
     holds one open editor whose words are the message's own: opening another closes
     it, as ↑ to an earlier message does. One whose words the user changed stays open
     until a key or press of theirs puts it away, so a second press elsewhere in the
     thread opens a second editor beside it, each named for its message.

   Escape discards changed words, as Cancel does, so one Escape undoes the ↑ that opened
   the rewrite, as in Slack, Discord and Telegram (the user's decision, 2026-10-06).
   Rejected: Escape keeping them as an unsaved edit, as a reply box keeps its draft,
   which left the user a draft to find and drop that the message could barely show.

   The editor takes the message's place without moving it. Its box surrounds the words
   where they stood, and its Cancel and Save stand at the message's head, where the
   message's own control stood (shadow.css, `.lf-msg-edit-actions`), so opening and
   closing it moves nothing around the message, and a line wraps where it wrapped.

   A double click on the message or a press on its Edit control opens it. The keyboard
   opens it with ↑: from the thread's empty reply box, the user's latest message, and
   from the start of an open rewrite not yet changed, their message before it, so Edit
   takes no Tab stop in every thread the user opened. A resolved thread shows no reply
   box; Enter on it reopens it into that box, as replying there starts, since a saved
   rewrite reopens it anyway, and ↑ goes on from there. Resume writing (`g i`) opens a
   rewrite whose words were kept on the message in the Threads panel
   (`openMessageEditIn`). Opening brings the editor into view. Enter saves; Escape and
   Cancel close it, discarding changed words; opening another rewrite in the thread
   puts this one aside, keeping them. The
   editor is a rung below the thread's reply box, so Enter, Escape and Cancel each hand
   the user to that box, or, in a thread showing none, onto the thread (`land`). Save sends
   through the one ledger, which draws the new words on the message in the gesture
   (`foldThreads`), and a refusal gives its words back to the draft, the message saying
   it holds them beside the words it stands at. A rewrite names the revision it was
   written over, and the log refuses it once another tab has rewritten the message
   since; opening a rewrite shows what its thread holds, so it starts from the words as
   they stand. Words the message already says are no rewrite, so saving them closes the
   editor and sends nothing. */
import {
  clearDraft,
  draftHasContent,
  forgetWritingPlace,
  loadDraft,
  loadDraftPayload,
  mirrorDraft,
  saveDraft,
  sendDraft,
  tellDraft,
  watchDraft,
} from "../drafts.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { caretAtKey, focusDestination } from "../focus.js";
import { PENDING } from "./identity.js";
import { keys } from "../keyboard/scopes.js";
import { announce, notice } from "../notifications.js";
import { sizeObserver } from "../rendering.js";
import { retainUserIntent } from "../user-intent.js";
import { offer } from "../widget-elements.js";

export const editContext = (id) => `rewrite:${id}`;
// What a message's view answers by opening its rewrite, as a press on its Edit control.
export const OPEN_MESSAGE_EDIT = "lf-open-message-edit";
// message id -> {view, panel}: the view drawing its editor, null once that view is
// gone, and whether it stood in the Threads panel.
const open = new Map();
// Rewrites whose words are on their way to the log: neither open nor kept.
const sending = new Set();

// Whether `view`, on the surface `panel` says, draws the editor for message `id`: the
// view holding it, or the first on the same surface to ask once no view does.
export function holdsMessageEdit(id, view, panel) {
  const holder = open.get(id);
  if (!holder || holder.panel !== panel) return false;
  if (holder.view !== null && holder.view !== view) return false;
  holder.view = view;
  return true;
}

// The view drawing `id`'s editor is gone; the next view of the message on its surface
// takes it.
export function releaseMessageEdit(id, view) {
  const holder = open.get(id);
  if (holder?.view === view) holder.view = null;
}

// Open a rewrite of `id` in `view`.
export function openMessageEdit(id, view, panel) {
  open.set(id, { view, panel });
}

// Whether a rewrite of `id` holds words no editor shows: a reload's or a refusal's.
export const keptRewrite = (id) =>
  !open.has(id) && !sending.has(id) && draftHasContent(editContext(id));

// Call `changed` on news of the words of a rewrite of `id`, from this tab or another.
// Returns the unsubscribe.
export const watchRewrite = (id, changed) => watchDraft(editContext(id), changed);

// Open the rewrite of message `id` where `thread`, a drawn thread, shows it, and answer
// the box its words are in: none where the thread does not draw that message as one the
// user may rewrite.
export function openMessageEditIn(thread, id) {
  const message = [...(thread?.querySelectorAll(".lf-msg") ?? [])].find(
    (node) => (node.dataset.mid ?? node.dataset.event) === id,
  );
  message?.dispatchEvent(new CustomEvent(OPEN_MESSAGE_EDIT));
  return (
    message?.querySelector(`:scope > .lf-msg-body > .lf-msg-editor ${TEXT_FIELD}`) ??
    null
  );
}

function closeMessageEdit(id, { discard }) {
  open.delete(id);
  if (!discard) return;
  const ctx = editContext(id);
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

  constructor(
    id,
    view,
    { wireInput, said, base: standing, send, land, paint, previous, reveal },
  ) {
    const ctx = editContext(id);
    // The revision these words are written over, which the log holds the rewrite to: the
    // message as it stands now. Words kept from an earlier opening carry the revision
    // they were written over; where the message has changed since, the user is told what
    // it says now before the kept words go over it.
    const base = standing();
    const keptOver = loadDraftPayload(ctx)?.over;
    // Words kept over the user's own edit still sending name it by its pending id, which
    // is no change of anyone else's.
    if (keptOver && keptOver !== base && !keptOver.startsWith(PENDING))
      notice(
        `This message changed since you wrote your edit. It now says: “${said()}”`,
      );
    this.#reveal = reveal;
    this.node = offer("div", "lf-msg-editor");
    this.input = offer(TEXT_FIELD);
    this.input.name = "edit";
    const actions = offer("span", "lf-msg-edit-actions");
    const save = offer("button", "lf-msg-control lf-msg-edit-save");
    const cancel = offer("button", "lf-msg-control lf-msg-edit-cancel");
    cancel.type = "button";
    cancel.title = "Cancel, discarding your changes";
    cancel.textContent = "Cancel";
    actions.append(cancel);
    // The box's last line, where the caret stands on opening: the field's own lines are
    // in a closed tree, so a mark of no size after it is what a reveal can aim at.
    this.foot = document.createElement("span");
    this.foot.className = "lf-msg-edit-foot";
    this.node.append(this.input, this.foot, actions);
    // The words a closed rewrite left, or the message's own. An empty draft is none.
    this.input.value = loadDraft(ctx) || said();
    // Words the message already says, and no words, are no change.
    const unchanged = () => {
      const words = this.input.value.trim();
      return !words || words === said().trim();
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
    // Closing as Escape and Cancel do, discarding what changed.
    const close = () =>
      leave(true, {
        says: unchanged()
          ? "Stopped editing"
          : "Edit discarded; the message is as it was",
      });
    // Making way for another rewrite, as ↑ to an earlier message or opening one
    // elsewhere in the thread does, closes one the user has not changed; changed words
    // stay in their box, which no key here meant to put away.
    const putAside = () => {
      if (unchanged()) leave(true, { landing: false });
    };
    this.#putAside = putAside;
    const sync = wireInput(this.input, {
      hint: "Edit message",
      accessibleName: () => `Edit your message: ${said().slice(0, 60)}`,
      sends: "save",
      icon: null,
      sendBtn: save,
      submitIn: actions,
      save: (value) => {
        saveDraft(ctx, value, { over: base });
        tellDraft(ctx, value, { over: base });
      },
      send: async (text, raw, owns) => {
        if (text === said().trim()) return leave(true, { says: "No change to save" });
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
          description:
            "From the start of an unchanged box, edit your message before this one",
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
    keys(
      this.node,
      "Editing a message",
      [
        {
          id: "message.edit.close",
          keys: ["Escape"],
          description: "Stop editing, leaving the message as it was",
          title: "stop editing",
          run: () => close(),
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
