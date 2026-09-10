/* This module owns page-seated first-message boxes: the conversation a widget declares
 * through `x-conversation`, built by `conversationBox`. */
import { loadDraft, saveDraft, sendMessage, watchDraft } from "../drafts.js";
import { inChrome } from "../passages.js";
import { matchesWhen, registry } from "../registry.js";
import { offer, quoted } from "../widget-elements.js";
import { notice } from "../notifications.js";

export const conversationBox = (
  el,
  hint,
  { createComment, onDraftChanged, wireInput },
) => {
  if (inChrome(el) || quoted(el)) return null;
  const declaration = registry[el.localName]?.["x-conversation"];
  if (!declaration || !matchesWhen(el, declaration.when))
    throw new TypeError(
      `<${el.localName}> placed a conversation outside its x-conversation predicate`,
    );
  if (!el.id)
    throw new TypeError(`<${el.localName}> needs an id to own a conversation`);
  const box = offer("div", "lf-conversation");
  box.dataset.lfConversation = el.id;
  const row = offer("div", "lf-say");
  const ta = offer("textarea");
  ta.name = "comment";
  const send = offer("button", "lf-btn primary", "Send");
  const hold = declaration.hold ? offer("button", "lf-btn", declaration.hold) : null;
  const ctx = "say:" + el.id;
  ta.value = loadDraft(ctx) ?? "";
  ta.setAttribute("aria-label", hint);
  row.append(ta, send, ...(hold ? [hold] : []));
  const sendComment = (text, owns, holds = false) =>
    sendMessage(ctx, owns, (attempt) =>
      createComment({
        anchor: { section: el.id },
        text,
        attempt,
        ...(declaration.response && { response: declaration.response }),
        ...(holds && { holds: el.id }),
      }),
    );
  const sync = wireInput(ta, {
    hint,
    sends: "send",
    sendBtn: send,
    altBtn: hold,
    save: (value) => saveDraft(ctx, value),
    // The message stands in the seat's own conversation the moment it is sent, and that
    // is the acknowledgement; a notice saying the same thing would be a second one. A
    // reader with no view of the seat hears the send from the live region, which `post`
    // writes for every message. The hold says what its press did beyond sending — and
    // names the send too, because it is the later write to that one region and would
    // otherwise be all the reader heard.
    send: (_text, raw, owns) => {
      sendComment(raw, owns);
    },
    altSend: hold
      ? (_text, raw, owns) => {
          if (sendComment(raw, owns, true)) notice("Message sent — goal paused");
        }
      : null,
  });
  sync();
  box.lfFirstMessage = row;
  const off = watchDraft(ctx, (value) => {
    if (!box.isConnected) return off();
    sync.load(value ?? "");
    onDraftChanged();
  });
  box.append(row);
  return box;
};
