/* One reply draft and send lifecycle shared by every view of a thread.

   A reply send returns in the gesture that makes it, so whether the reader is still in
   this box is read once, there, and typing continues here only on that reading. The
   send preserves the panel's narrowing, and focuses the reply box only when no later
   selection, edit, or typing gesture stands. A general-comment send keeps focus in its
   originating box. */
import {
  loadDraft,
  mirrorDraft,
  saveDraft,
  sendMessage,
  tellDraft,
} from "../drafts.js";
import { threadKey } from "./model.js";
import { focused } from "../keyboard/scopes.js";
import { landTyping, mayLandTyping } from "../composing/capture.js";

const REPLY_DRAFT_CONTEXT = Symbol("reply draft context");

// A thread's reply draft has several views, and sending settles that draft in the
// gesture that sends it. A second view pressing Send afterwards reads the generation as
// spent and refuses on its own — in this tab and in any other showing the page, which is
// further than a hold kept in this document's memory reached.
const sendReply = (t, liveId, text, owns, createReply) =>
  sendMessage("reply:" + threadKey(t), owns, (attempt) =>
    createReply({
      parent: liveId(),
      text,
      attempt,
    }),
  );

// One reply draft, send, and typing continuation across every view of a thread.
export function wireReply(
  t,
  input,
  send,
  {
    liveId = () => t.root.id,
    createReply,
    revealReplyEditor,
    wireInput,
    onDraftLoaded = null,
  },
) {
  const draftCtx = "reply:" + threadKey(t);
  input[REPLY_DRAFT_CONTEXT] = draftCtx;
  input.value = loadDraft(draftCtx) ?? "";
  const sync = wireInput(input, {
    hint: "Reply",
    accessibleName: "Reply",
    sends: "send",
    sendBtn: send,
    // localStorage notifies other tabs but skips this document. Page, margin, and panel
    // reply boxes are views of one draft here, so they take the same bus directly.
    // Other draft kinds still have one view per document.
    save: (v) => {
      saveDraft(draftCtx, v);
      tellDraft(draftCtx, v);
    },
    // The send returns in the gesture, so where the reader is reading is still where
    // they were when they pressed it. Whether typing continues here is that one
    // reading, taken now, rather than a race against a scroll or a blur arriving during
    // a flight this no longer waits on.
    send: (_text, raw, owns) => {
      const sent = sendReply(t, liveId, raw, owns, createReply);
      if (!sent || (focused() !== input && focused() !== send) || !mayLandTyping(input))
        return;
      landTyping(input);
      revealReplyEditor(input);
    },
  });
  sync();
  onDraftLoaded?.(sync.value());
  // A box growing under the reader pushes its embedded Send below the list's foot:
  // eight lines of reply left the blue button a sliver at the scrollport's edge,
  // reachable only by the send key the placeholder happened to name. Landing reveals
  // the composer with its controls (revealConversation); growth is the same claim made
  // again. On the reader's own keystrokes and nothing else: a send settling after they
  // scrolled away, or a draft mirrored from another tab, must not pull the list back.
  // Instant, not smooth — a line typed while the last line's glide is still running
  // lands the list where that glide was going, two lines short of the box it is now.
  input.addEventListener("input", () => {
    if (focused() !== input) return;
    const held = input.closest(".lf-thread, .lf-conversation-thread, .lf-conversation");
    if (held) revealReplyEditor(input, "instant");
  });
  mirrorDraft(
    input,
    {
      load: (value) => {
        sync.load(value);
        onDraftLoaded?.(sync.value());
      },
    },
    draftCtx,
  );
  return sync;
}

// null means this is not a reply box. False is the useful third state: a reply box
// opened by the runtime but never edited, whose empty focus is a landing rather than
// a composition the next live revision must preserve.
export const replyBoxHasDraft = (input) => {
  const ctx = input?.[REPLY_DRAFT_CONTEXT];
  return ctx ? loadDraft(ctx) !== null : null;
};
