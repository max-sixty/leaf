/* This module owns page-seated first-message boxes: the thread a widget declares
 * through `x-thread-seat`, built by `threadBox`. */
import { whileConnected } from "../arrivals.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { loadDraft, saveDraft, sendMessage, watchDraft } from "../drafts.js";
import { inChrome } from "../passages.js";
import { matchesWhen, registry } from "../registry.js";
import { offer } from "../widget-elements.js";
import { quoted } from "../widget-descriptors.js";
import { notice } from "../notifications.js";
import { mountFirstMessage } from "./inline.js";
import { sendLanding } from "./reply-landing.js";

export const threadBox = (el, hint, { createComment, onDraftChanged, wireInput }) => {
  if (inChrome(el) || quoted(el)) return null;
  const declaration = registry[el.localName]?.["x-thread-seat"];
  if (!declaration || !matchesWhen(el, declaration.when))
    throw new TypeError(
      `<${el.localName}> placed a thread outside its x-thread-seat predicate`,
    );
  const box = offer("div", "lf-thread-seat");
  box.dataset.lfRuntime = "";
  box.dataset.lfThreadSeat = el.id;
  const row = offer("div", "lf-say lf-comment-box");
  const ta = offer(TEXT_FIELD);
  ta.name = "comment";
  const ctx = "say:" + el.id;
  ta.value = loadDraft(ctx) ?? "";
  ta.setAttribute("aria-label", hint);
  row.append(ta);
  // A seat that keeps its box after the send shows the new thread above it; one that
  // gives its box up hands the user to the thread it started (inline.js).
  const sendComment = (text, owns, holds = false) => {
    const land = sendLanding(ta);
    const sent = sendMessage(ctx, owns, (attempt) =>
      createComment({
        anchor: { section: el.id },
        text,
        attempt,
        ...(holds && { holds: el.id }),
      }),
    );
    if (sent) land();
    return sent;
  };
  const sync = wireInput(ta, {
    hint,
    sends: "send",
    altLabel: declaration.hold ?? null,
    save: (value) => saveDraft(ctx, value),
    // The message stands in the seat's own thread the moment it is sent, and that
    // is the acknowledgement; a notice saying the same thing would be a second one. A
    // user with no view of the seat hears the send from the live region, which `post`
    // writes for every message. The hold says what its press did beyond sending — and
    // names the send too, because it is the later write to that one region and would
    // otherwise be all the user heard.
    send: (_text, raw, owns) => {
      sendComment(raw, owns);
    },
    altSend: declaration.hold
      ? (_text, raw, owns) => {
          if (sendComment(raw, owns, true)) notice("Replied — goal paused");
        }
      : null,
  });
  sync();
  box.lfFirstMessage = row;
  // The seat's box is this draft's editor while it stands, so a revision that takes the
  // seat away leaves Resume writing nothing holding its words (drafts.js).
  whileConnected(box, () =>
    watchDraft(
      ctx,
      (value) => {
        sync.load(value ?? "");
        onDraftChanged();
      },
      {
        input: ta,
        resume: () => ({ where: el, input: () => ta }),
      },
    ),
  );
  mountFirstMessage(box, row);
  return box;
};
