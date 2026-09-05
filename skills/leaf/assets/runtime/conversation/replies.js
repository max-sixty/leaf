/* One reply draft and send lifecycle shared by every view of a thread.

   A reply send keeps its editor and actions visible only while the reader remains
   there. Moving to another input, closing the panel, or scrolling away relinquishes
   that continuation. The send preserves the panel's narrowing. A general-comment send
   keeps focus in its originating box.

   The send focuses the reply box only when no later selection, edit, or typing gesture
   stands. */
import { heldConversation, revealConversation } from "./landing.js";
import { loadDraft, mirrorDraft, saveDraft, sendDraft, tellDraft } from "../drafts.js";
import { post } from "../outbox.js";
import { runtime } from "../context.js";
import { wireInput } from "../composing/input.js";
import { focused } from "../keyboard/scopes.js";
import { landTyping, mayLandTyping } from "../composing/capture.js";

// A thread has one send in flight even though its reply draft may have several views.
// wireInput's private hold is still the right scope for every other composer, which has
// one control; a reply adds this thread-scoped hold and announces it on the document bus
// so every Send control renders the same fact. The promise is the post itself, because a queue would
// serialize the duplicate rather than refuse it.
const REPLY_FLIGHT_NEWS = "lf-reply-flight";
const REPLY_DRAFT_CONTEXT = Symbol("reply draft context");
const replyFlights = new Map(); // thread id -> post in flight
const replyBusy = (id) => replyFlights.has(id);
const tellReplyFlight = (id) =>
  document.dispatchEvent(new CustomEvent(REPLY_FLIGHT_NEWS, { detail: { id } }));

function mirrorReplyFlight(ta, sync, id) {
  const update = (ev) => {
    if (ev.detail.id !== id) return;
    if (!ta.isConnected) return document.removeEventListener(REPLY_FLIGHT_NEWS, update);
    sync();
  };
  document.addEventListener(REPLY_FLIGHT_NEWS, update);
}

async function sendReply(t, text, raw, owns) {
  const id = t.root.id;
  if (replyBusy(id)) return null;
  const draftCtx = "reply:" + id;
  const flight = sendDraft(draftCtx, owns, (attempt) =>
    post({
      kind: "reply",
      parent: id,
      revision: runtime.currentRevision,
      text,
      attempt,
    }),
  );
  replyFlights.set(id, flight);
  tellReplyFlight(id);
  try {
    return await flight;
  } finally {
    replyFlights.delete(id);
    tellReplyFlight(id);
  }
}

// One reply draft, send, and typing continuation across every view of a thread.
export function wireReply(t, input, send) {
  const draftCtx = "reply:" + t.root.id;
  input[REPLY_DRAFT_CONTEXT] = draftCtx;
  input.value = loadDraft(draftCtx) ?? "";
  const sync = wireInput(input, {
    hint: "Reply",
    sends: "send",
    sendBtn: send,
    busy: () => replyBusy(t.root.id),
    // localStorage notifies other tabs but skips this document. Page, margin, and panel
    // reply boxes are views of one draft here, so they take the same bus directly.
    // Other draft kinds still have one view per document.
    save: (v) => {
      saveDraft(draftCtx, v);
      tellDraft(draftCtx, v);
    },
    send: async (text, raw, owns) => {
      // Scrolling away or leaving the window can keep the old editor's focus. Both
      // withdraw this send's continuation, while its draft and delivery still settle.
      const continuation = new AbortController();
      const listening = { capture: true, passive: true, signal: continuation.signal };
      const leave = () => continuation.abort();
      addEventListener("blur", leave, { signal: continuation.signal });
      document.addEventListener("wheel", leave, listening);
      document.addEventListener("touchmove", leave, listening);
      document.addEventListener(
        "pointerdown",
        (event) => {
          const path = event.composedPath();
          if (!path.includes(input) && !path.includes(send)) leave();
        },
        listening,
      );
      try {
        const sent = await sendReply(t, text, raw, owns);
        if (
          !sent ||
          continuation.signal.aborted ||
          (focused() !== input && focused() !== send) ||
          !mayLandTyping(input)
        )
          return;
        landTyping(input);
        revealConversation(heldConversation(), input);
      } finally {
        continuation.abort();
      }
    },
  });
  sync();
  // A box growing under the reader pushes its own Send and Resolve below the list's
  // foot: eight lines of reply left the blue button a sliver at the scrollport's edge,
  // reachable only by the send key the placeholder happened to name. Landing reveals
  // the composer with its actions (revealConversation); growth is the same claim made
  // again. On the reader's own keystrokes and nothing else: a send settling after they
  // scrolled away, or a draft mirrored from another tab, must not pull the list back.
  // Instant, not smooth — a line typed while the last line's glide is still running
  // lands the list where that glide was going, two lines short of the box it is now.
  input.addEventListener("input", () => {
    if (focused() !== input) return;
    const held = input.closest(".lf-thread, .lf-conversation-thread, .lf-conversation");
    if (held) revealConversation(held, input, "instant");
  });
  mirrorDraft(input, sync, draftCtx);
  mirrorReplyFlight(input, sync, t.root.id);
  return sync;
}

// null means this is not a reply box. False is the useful third state: a reply box
// opened by the runtime but never edited, whose empty focus is a landing rather than
// a composition the next live revision must preserve.
export const replyBoxHasDraft = (input) => {
  const ctx = input?.[REPLY_DRAFT_CONTEXT];
  return ctx ? loadDraft(ctx) !== null : null;
};
