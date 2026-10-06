/* The user rewriting a message of their own, where the message stands.

   A message the user wrote with words is theirs to rewrite (`editable`), and the rewrite
   is a turn the agent answers (events.md, `edit`). Its words are a draft under
   `edit:<message id>` (drafts.js), so they keep every promise a reply's words keep: a
   re-render or a reload leaves them, every view of the message and every tab shows the
   same words, and a refusal gives them back. An active draft is an open editor: each
   view of the message draws its editor in place of the words while one stands, and
   Save or Cancel settling it closes them all.

   A double click on the message, its Edit control, or ↑ in the thread's empty reply box
   opens it, holding the message's words. Enter saves and Escape cancels, keeping the
   message as it was; both leave the user standing on the thread, as a sent reply does.
   Save sends through the one ledger, which draws the new words on the message in the
   gesture (`foldThreads`). Words the message already says are no rewrite, so saving
   them closes the editor and sends nothing. */
import {
  clearDraft,
  loadDraft,
  mirrorDraft,
  saveDraft,
  sendDraft,
  tellDraft,
  watchDraft,
} from "../drafts.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { offer } from "../widget-elements.js";

const editContext = (id) => `edit:${id}`;

// Whether the user has a rewrite of this message open, here or in another tab.
export const editingMessage = (id) => loadDraft(editContext(id)) !== null;

// News that a rewrite of `id` opened, changed, closed or came back on a refusal.
export const watchMessageEdit = (id, changed) => watchDraft(editContext(id), changed);

// Open the rewrite with the message's words, or leave one already open as it stands.
export function openMessageEdit(id, text) {
  const ctx = editContext(id);
  if (loadDraft(ctx) !== null) return;
  saveDraft(ctx, text);
  tellDraft(ctx, text);
}

function closeMessageEdit(id) {
  const ctx = editContext(id);
  clearDraft(ctx);
  tellDraft(ctx, null);
}

/** One view's editor over one message's rewrite.
 *
 * `said` reads the message's words now, `send` posts the rewrite through the thread's
 * typed action and returns its answer, and `land` puts the user back on the thread
 * before the editor leaves the page. */
export class MessageEditor {
  #stop;

  constructor(id, { wireInput, said, send, land }) {
    const ctx = editContext(id);
    this.node = offer("div", "lf-msg-editor");
    this.input = offer(TEXT_FIELD);
    this.input.name = "edit";
    const save = offer("button", "lf-btn lf-thread-send", "Save");
    const cancel = offer("button", "lf-btn lf-msg-edit-cancel", "Cancel");
    this.node.append(this.input, save);
    this.input.value = loadDraft(ctx) ?? "";
    const leave = () => {
      land();
      closeMessageEdit(id);
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
      send: (text, raw, owns) => {
        if (text === said().trim()) return leave();
        land();
        return sendDraft(ctx, owns, (attempt) => send(raw, { attempt }));
      },
      rows: [
        {
          id: "message.edit.cancel",
          keys: ["Escape"],
          description: "Stop editing, keeping the message as it was",
          title: "cancel edit",
          run: leave,
        },
      ],
    });
    this.node.append(cancel);
    cancel.addEventListener("click", leave);
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
