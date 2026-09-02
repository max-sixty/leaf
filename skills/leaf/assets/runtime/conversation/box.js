import { runtime } from "../context.js";
import { loadDraft, saveDraft, sendDraft, watchDraft } from "../drafts.js";
import { inChrome } from "../passages.js";
import { matchesWhen, registry } from "../registry.js";
import { offer, quoted } from "../widget-elements.js";

let publishedConversationBox;
export const conversationBox = (...args) => publishedConversationBox(...args);

export function createConversationBox({ post, renderPanel, notice, wireInput }) {
  publishedConversationBox = (el, hint) => {
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
    const sendComment = (text, raw, holds = false) =>
      sendDraft(
        ctx,
        () => ta.value === raw,
        (attempt) =>
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
      send: async (text, raw) => {
        if (!(await sendComment(text, raw))) return;
        notice("Message recorded");
      },
      altSend: hold
        ? async (text, raw) => {
            if (!(await sendComment(text, raw, true))) return;
            notice("Message recorded — goal paused");
          }
        : null,
    });
    sync();
    box.lfFirstMessage = row;
    const off = watchDraft(ctx, (value) => {
      if (!box.isConnected) return off();
      const text = value ?? "";
      if (ta.value !== text) ta.value = text;
      sync();
      renderPanel();
    });
    box.append(row);
    return box;
  };
}
