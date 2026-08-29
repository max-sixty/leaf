/* One reply draft and send lifecycle shared by every view of a thread. */
export function createReplies({
  landTyping,
  loadDraft,
  mirrorDraft,
  post,
  runtime,
  saveDraft,
  sendDraft,
  tellDraft,
  wireInput,
}) {
  // A thread has one send in flight even though its reply draft may have several views.
  // wireInput's private hold is still the right scope for every other composer, which has
  // one control; a reply adds this thread-scoped hold and announces it on the document bus
  // so every Send control renders the same fact. The promise is the post itself, because a queue would
  // serialize the duplicate rather than refuse it.
  const REPLY_FLIGHT_NEWS = "lf-reply-flight";
  const replyFlights = new Map(); // thread id -> post in flight
  const replyBusy = (id) => replyFlights.has(id);
  const tellReplyFlight = (id) =>
    document.dispatchEvent(new CustomEvent(REPLY_FLIGHT_NEWS, { detail: { id } }));

  function mirrorReplyFlight(ta, sync, id) {
    const update = (ev) => {
      if (ev.detail.id !== id) return;
      if (!ta.isConnected)
        return document.removeEventListener(REPLY_FLIGHT_NEWS, update);
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

  // One reply draft and one send path, however many views the thread has. The panel can
  // reveal a sent message immediately; textual views receive it through reconciliation.
  // Everything else — persistence, mirroring, the wire event and focus landing — is the
  // thread's and is stated once.
  function wireReply(t, input, send, { landed } = {}) {
    const draftCtx = "reply:" + t.root.id;
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
      send: async (text, raw) => {
        const sent = await sendReply(t, text, raw, () => input.value === raw);
        if (!sent) return;
        landed?.(sent);
        landTyping(input);
      },
    });
    sync();
    mirrorDraft(input, sync, draftCtx);
    mirrorReplyFlight(input, sync, t.root.id);
    return sync;
  }

  return { wireReply };
}
