/* The user rewriting a message of their own, where the message stands.

   A message the user wrote with words is theirs to rewrite (`editable`), and the rewrite
   is a turn the agent answers (events.md, `edit`). Two facts make up a rewrite, each
   with the owner its kind has elsewhere:

   - Its words are a draft under `rewrite:<message id>` (drafts.js), once the user
     changes them, so they keep every promise a reply's words keep: they survive a
     reload, reach every tab, come back on a refusal, and stay until Save or Cancel
     settles them. Opening a rewrite again finds the words a closed one left, and the
     message says it holds them (`keptRewrite`).
   - That an editor stands open is disclosure, this document's mechanical state, held
     here by message id. One view of the message draws it: the one it was opened in,
     or, once that view is gone, the next view of the message on the same surface
     (the Threads panel, or the page), which takes the editor as a replacement node
     takes words and caret. A view on the other surface, or in another tab, draws the
     message as it was, since nothing the user did there asked it to change.

   A double click on the message or a press on its Edit control opens it. The keyboard
   opens it with ↑: from the thread's empty reply box, the user's latest message, and
   from the start of an open rewrite, their message before it, so Edit takes no Tab stop
   in every thread the user opened. Resume writing (`g i`) opens a rewrite whose words were kept where its
   thread lands (`openMessageEditIn`). Enter saves; Escape closes it and keeps its
   words; Cancel discards them. All three leave the user standing on the thread, as a
   sent reply does. Save sends through
   the one ledger, which draws the new words on the message in the gesture
   (`foldThreads`), and a refusal opens the editor again on the words it gives back.
   Words the message already says are no rewrite, so saving them closes the editor and
   sends nothing. */
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
import { offer } from "../widget-elements.js";

export const editContext = (id) => `rewrite:${id}`;
// What a message's view answers by opening its rewrite, as a press on its Edit control.
export const OPEN_MESSAGE_EDIT = "lf-open-message-edit";
// message id -> {view, panel}: the view drawing its editor, null once that view is
// gone, and whether it stood in the Threads panel.
const open = new Map();

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

// Whether the user closed a rewrite of `id` and kept its words for later.
export const keptRewrite = (id) => !open.has(id) && draftHasContent(editContext(id));

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
    message?.querySelector(`:scope > .lf-msg-body > .lf-msg-editor > ${TEXT_FIELD}`) ??
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
 * `said` reads the message's words now; `send` posts the rewrite through the thread's
 * typed action and returns its answer; `land` puts the user back on the thread before
 * the editor leaves the page; `paint` draws the view again once the editor opens or
 * closes; `previous` answers the view of the user's message before this one that ↑
 * opens, or null. */
export class MessageEditor {
  #stop;

  constructor(id, view, panel, { wireInput, said, send, land, paint, previous }) {
    const ctx = editContext(id);
    this.node = offer("div", "lf-msg-editor");
    this.input = offer(TEXT_FIELD);
    this.input.name = "edit";
    const save = offer("button", "lf-btn lf-thread-send", "Save");
    const cancel = offer("button", "lf-btn lf-msg-edit-cancel", "Cancel");
    this.node.append(this.input, save);
    // The words a closed rewrite left, or the message's own.
    this.input.value = loadDraft(ctx) ?? said();
    const leave = (discard) => {
      land();
      closeMessageEdit(id, { discard });
      paint();
    };
    const sync = wireInput(this.input, {
      hint: "Edit message",
      accessibleName: "Edit your message",
      sends: "save",
      icon: "check",
      sendBtn: save,
      save: (value) => {
        saveDraft(ctx, value);
        tellDraft(ctx, value);
      },
      send: async (text, raw, owns) => {
        if (text === said().trim()) return leave(true);
        leave(false);
        const sent = await sendDraft(ctx, owns, (attempt) => send(raw, { attempt }));
        // A refusal has given the words back to the draft; show them where they were,
        // while that view stands. Otherwise they wait in the draft for the next opening.
        if (!sent && loadDraft(ctx) !== null && view.node.isConnected) {
          openMessageEdit(id, view, panel);
          paint();
        }
      },
      rows: [
        {
          id: "message.edit.close",
          keys: ["Escape"],
          description:
            "Stop editing, keeping the message as it was and your words for later",
          title: "stop editing",
          // Words the message already says are nothing to keep.
          run: () => leave(this.input.value.trim() === said().trim()),
        },
        {
          id: "message.edit.previous",
          keys: ["ArrowUp"],
          description: "From the start of the box, edit your message before this one",
          title: "edit previous message",
          when: () =>
            this.input.selectionStart === 0 &&
            this.input.selectionEnd === 0 &&
            Boolean(previous()),
          run: () => {
            const before = previous();
            leave(this.input.value.trim() === said().trim());
            before.openEdit();
          },
        },
      ],
    });
    this.node.append(cancel);
    cancel.addEventListener("click", () => leave(true));
    this.#stop = mirrorDraft(this.input, sync, ctx, { retained: true });
  }

  // Focus the words with the caret after them, where a rewrite usually starts.
  focus() {
    const end = this.input.value.length;
    this.input.focus({ preventScroll: true });
    this.input.setSelectionRange(end, end);
  }

  dispose() {
    this.#stop();
  }
}
