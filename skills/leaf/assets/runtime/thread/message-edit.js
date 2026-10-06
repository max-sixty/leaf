/* The user rewriting a message of their own, where the message stands.

   A message the user wrote with words is theirs to rewrite (`editable`), and the rewrite
   is a turn the agent answers (events.md, `edit`). Two facts make up a rewrite, each
   with the owner its kind has elsewhere:

   - Its words are a draft under `edit:<message id>` (drafts.js), so they keep every
     promise a reply's words keep: they survive a reload, reach every tab, come back on
     a refusal, and stay until Save or Cancel settles them. Opening a rewrite again
     finds the words a closed one left.
   - That an editor stands open is disclosure, this document's mechanical state, held
     here by message id. One view of the message draws it: the one it was opened in,
     or, once that view is gone, the next view of the message this document presents,
     which takes the editor as a replacement node takes words and caret. Another view
     of the same message, or another tab, draws the message as it was, since nothing
     the user did there asked it to change.

   A double click on the message, its Edit control, or ↑ in the thread's empty reply box
   opens it. Enter saves; Escape closes it and keeps its words; Cancel discards them. All
   three leave the user standing on the thread, as a sent reply does. Save sends through
   the one ledger, which draws the new words on the message in the gesture
   (`foldThreads`), and a refusal opens the editor again on the words it gives back.
   Words the message already says are no rewrite, so saving them closes the editor and
   sends nothing. */
import {
  clearDraft,
  loadDraft,
  mirrorDraft,
  saveDraft,
  sendDraft,
  tellDraft,
} from "../drafts.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { offer } from "../widget-elements.js";

const editContext = (id) => `edit:${id}`;
const open = new Map(); // message id -> the view drawing its editor, or null

// Whether `view` draws the editor for message `id`: the view holding it, or the first to
// ask once no view does.
export function holdsMessageEdit(id, view) {
  if (!open.has(id)) return false;
  const holder = open.get(id);
  if (holder !== null && holder !== view) return false;
  open.set(id, view);
  return true;
}

// The view drawing `id`'s editor is gone; whichever view of the message comes next
// takes it.
export function releaseMessageEdit(id, view) {
  if (open.get(id) === view) open.set(id, null);
}

// Open a rewrite of `id` in `view`, on the words a closed one left or the message's own.
export function openMessageEdit(id, text, view) {
  const ctx = editContext(id);
  if (loadDraft(ctx) === null) {
    saveDraft(ctx, text);
    tellDraft(ctx, text);
  }
  open.set(id, view);
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
 * closes. */
export class MessageEditor {
  #stop;

  constructor(id, view, { wireInput, said, send, land, paint }) {
    const ctx = editContext(id);
    this.node = offer("div", "lf-msg-editor");
    this.input = offer(TEXT_FIELD);
    this.input.name = "edit";
    const save = offer("button", "lf-btn lf-thread-send", "Save");
    const cancel = offer("button", "lf-btn lf-msg-edit-cancel", "Cancel");
    this.node.append(this.input, save);
    this.input.value = loadDraft(ctx) ?? "";
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
        // A refusal has given the words back to the draft; show them where they were.
        if (!sent && loadDraft(ctx) !== null) {
          openMessageEdit(id, raw, view);
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
          run: () => leave(false),
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
