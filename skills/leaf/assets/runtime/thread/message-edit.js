/* The user rewriting a message of their own, where the message stands.

   A message the user wrote with words is theirs to rewrite (`editable`), and the rewrite
   is a turn the agent answers (events.md, `edit`). Two facts make up a rewrite, each
   with the owner its kind has elsewhere:

   - Its words are a draft under `rewrite:<message id>` (drafts.js), once the user
     changes them, so they keep every promise a reply's words keep: they survive a
     reload, reach every tab, come back on a refusal, and stay until Save or Cancel
     settles them. Opening a rewrite again finds the words a closed one left, and the
     message says it holds them (`keptRewrite`). Words the message already says, and no
     words at all, are no rewrite: neither is kept, and a box with no draft holds the
     message's own words, in this tab and in every other.
   - That an editor stands open is disclosure, this document's mechanical state, held
     here by message id. One view of the message draws it: the one it was opened in,
     or, once that view is gone, the next view of the message on the same surface
     (the Threads panel, or the page), which takes the editor as a replacement node
     takes words and caret. A view on the other surface, or in another tab, draws the
     message as it was, since nothing the user did there asked it to change. A thread
     holds one open editor: opening another closes the first as Escape would.

   The editor takes the message's place without moving it. Its box surrounds the words
   where they stood, and its Cancel and Save stand at the message's head, where the
   message's own control stood (shadow.css, `.lf-msg-edit-actions`), so opening and
   closing it moves nothing around the message, and a line wraps where it wrapped.

   A double click on the message or a press on its Edit control opens it. The keyboard
   opens it with ↑: from the thread's empty reply box, the user's latest message, and
   from the start of an open rewrite, their message before it, so Edit takes no Tab stop
   in every thread the user opened. Resume writing (`g i`) opens a rewrite whose words
   were kept where its thread lands (`openMessageEditIn`). Opening brings the editor into
   view. Enter saves; Escape closes it and keeps changed words; Cancel discards them.
   The editor is a rung below the thread's reply box, so each of the three hands the
   user to that box, or, in a thread showing none, onto the thread (`land`). Save sends
   through the one ledger, which draws the new words on the message in the gesture
   (`foldThreads`), and a refusal gives its words back to the draft, the message saying
   it holds them beside the words it stands at. A rewrite names the revision it was
   written over, and the log refuses it once another tab has rewritten the message
   since; opening a rewrite is acting in its thread, so it starts from the words as they
   stand (held-news.js, `rewritingIn`). Words the message already says are no rewrite,
   so saving them closes the editor and sends nothing. */
import {
  clearDraft,
  draftHasContent,
  loadDraft,
  mirrorDraft,
  saveDraft,
  sendDraft,
  tellDraft,
  watchDraft,
} from "../drafts.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { keys } from "../keyboard/scopes.js";
import { announce } from "../notifications.js";
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

// Whether a rewrite of one of `thread`'s messages stands open, which is acting in the
// thread (held-news.js): its words must be the words as they stand.
export const rewritingIn = (thread) => thread.msgs.some(({ id }) => open.has(id));

// Whether the user closed a rewrite of `id` and kept its words for later.
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
  #leave;
  #reveal;
  // Where the caret stood when ↑ went down, while it is down: the editor's own ↑ moves
  // it to the start from anywhere on the first line before the key's binding reads it.
  #upFromStart = null;

  constructor(
    id,
    view,
    { wireInput, said, base: standing, send, land, paint, previous, reveal },
  ) {
    const ctx = editContext(id);
    // The revision these words are written over, which the log holds the rewrite to.
    const base = standing();
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
    this.node.append(this.input, actions);
    // The words a closed rewrite left, or the message's own. An empty draft is none.
    this.input.value = loadDraft(ctx) || said();
    // Words the message already says, and no words, are nothing to keep.
    const nothingToKeep = () => {
      const words = this.input.value.trim();
      return !words || words === said().trim();
    };
    const leave = (discard, { landing = true, says = null } = {}) => {
      if (landing) land();
      closeMessageEdit(id, { discard });
      paint();
      if (says) announce(says);
    };
    // Closing as Escape does, with the words kept where they changed.
    const close = (options) =>
      nothingToKeep()
        ? leave(true, { ...options, says: "Stopped editing" })
        : leave(false, { ...options, says: "Stopped editing; your words are kept" });
    this.#leave = close;
    const sync = wireInput(this.input, {
      hint: "Edit message",
      accessibleName: "Edit your message",
      sends: "save",
      icon: null,
      sendBtn: save,
      submitIn: actions,
      save: (value) => {
        saveDraft(ctx, value);
        tellDraft(ctx, value);
      },
      send: async (text, raw, owns) => {
        if (text === said().trim()) return leave(true, { says: "No change to save" });
        sending.add(id);
        leave(false);
        try {
          await sendDraft(ctx, owns, (attempt) => send(raw, { attempt, base }));
        } finally {
          sending.delete(id);
        }
        // A refusal gives the words back to the draft, which the message says it holds
        // beside the words it stands at, as Escape leaves them: a message another tab has
        // since rewritten shows that rewrite, which an editor opened at once would hide,
        // and opening the words again writes them over what the user can now see.
        paint();
      },
      rows: [
        {
          id: "message.edit.previous",
          keys: ["ArrowUp"],
          description: "From the start of the box, edit your message before this one",
          title: "edit previous message",
          when: () =>
            (this.#upFromStart ??
              (this.input.selectionStart === 0 && this.input.selectionEnd === 0)) &&
            Boolean(previous()),
          run: () => {
            const before = previous();
            close({ landing: false });
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
          description:
            "Stop editing, keeping the message as it was and any words you changed for later",
          title: "stop editing",
          run: () => close(),
        },
      ],
      { escape: "inner" },
    );
    cancel.addEventListener("mousedown", (event) => event.preventDefault());
    cancel.addEventListener("click", () =>
      leave(true, { says: "Edit cancelled; the message is as it was" }),
    );
    this.input.addEventListener(
      "keydown",
      (event) => {
        if (event.key === "ArrowUp")
          this.#upFromStart =
            this.input.selectionStart === 0 && this.input.selectionEnd === 0;
      },
      { capture: true },
    );
    this.input.addEventListener("keyup", (event) => {
      if (event.key === "ArrowUp") this.#upFromStart = null;
    });
    this.#stop = mirrorDraft(this.input, sync, ctx, { retained: true, blank: said });
  }

  // Focus the words with the caret after them, where a rewrite usually starts, and bring
  // the editor into view.
  focus() {
    const end = this.input.value.length;
    this.input.focus({ preventScroll: true });
    this.input.setSelectionRange(end, end);
    this.#reveal(this.node);
  }

  // Close without landing, as another editor opening in the thread does.
  close() {
    this.#leave({ landing: false });
  }

  dispose() {
    this.#stop();
  }
}
