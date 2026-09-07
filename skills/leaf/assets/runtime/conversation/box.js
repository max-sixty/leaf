/* This module owns page-seated first-message boxes: the conversation a widget declares
 * through `x-conversation`, built by `conversationBox`. */
import { runtime } from "../context.js";
import { loadDraft, saveDraft, sendMessage, watchDraft } from "../drafts.js";
import { inChrome } from "../passages.js";
import { matchesWhen, registry } from "../registry.js";
import { offer, quoted } from "../widget-elements.js";
import { post } from "../outbox.js";
import { wireInput } from "../composing/input.js";
import { notice } from "../notifications.js";
import { renderPanel } from "./reconcile.js";

export const conversationBox = (el, hint) => {
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
  const send = offer("button", "lf-btn primary", "Send");
  const hold = declaration.hold ? offer("button", "lf-btn", declaration.hold) : null;
  const ctx = "say:" + el.id;
  ta.value = loadDraft(ctx) ?? "";
  ta.setAttribute("aria-label", hint);
  row.append(ta, send, ...(hold ? [hold] : []));
  const sendComment = (text, raw, owns, holds = false) =>
    sendMessage(ctx, owns, (attempt) =>
      post({
        kind: "comment",
        revision: runtime.currentRevision,
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
    // is the acknowledgement; a notice saying the same thing would be a second one. The
    // hold button still says what its press did beyond sending.
    send: (text, raw, owns) => {
      sendComment(text, raw, owns);
    },
    altSend: hold
      ? (text, raw, owns) => {
          if (sendComment(text, raw, owns, true)) notice("Goal paused");
        }
      : null,
  });
  sync();
  box.lfFirstMessage = row;
  const off = watchDraft(ctx, (value) => {
    if (!box.isConnected) return off();
    sync.load(value ?? "");
    renderPanel();
  });
  box.append(row);
  return box;
};
