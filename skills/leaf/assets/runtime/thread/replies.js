/* One reply draft and send lifecycle shared by every view of a thread.

   A reply send returns in the gesture that makes it. The send preserves the panel's
   narrowing and, whichever control sent it, takes the user out of the reply box to stand
   on the thread (`landSent`), since a reply is usually their last word until the agent
   answers. `c`, or Enter on the thread, opens the box again. Settlement changes
   the conversation, never an unfinished reply: every surface retains the editor
   while its shared draft holds words, and sending them resumes the thread. */
import {
  loadDraft,
  draftHasContent,
  mirrorDraft,
  saveDraft,
  sendMessage,
  tellDraft,
} from "../drafts.js";
import { sendLanding } from "./reply-landing.js";
import { closestAcross } from "../passages.js";
import { focused } from "../keyboard/scopes.js";
import { THREAD } from "./selectors.js";

const REPLY_DRAFT_CONTEXT = Symbol("reply draft context");
export const replyDraftContext = (input) => input?.[REPLY_DRAFT_CONTEXT] ?? null;

// A thread's reply draft has several views, and sending settles that draft in the
// gesture that sends it. A second view pressing Send afterwards reads the generation as
// spent and refuses on its own — in this tab and in any other showing the page, which is
// further than a hold kept in this document's memory reached.
const sendReply = (draftCtx, key, text, owns, actions) =>
  sendMessage(draftCtx, owns, (attempt) => actions.reply(key, text, { attempt }));

// One reply draft, send, and typing continuation across every view of a thread. `key`
// is the thread's `threadKey`, which names its draft; `parent` reads the message the
// reply answers when it is sent, since the log can name that message after the draft
// began. The typed action resolves that target from the current reading.
export function wireReply(
  key,
  input,
  send,
  { actions, wireInput, landSent, onDraftLoaded = null },
) {
  const draftCtx = "reply:" + key;
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
    // The new turn is drawn above the box; the landing shows it with the box the user
    // sent from, around wherever the send left them standing.
    send: (_text, raw, owns) => {
      if (!sendReply(draftCtx, key, raw, owns, actions)) return;
      landSent(closestAcross(input, THREAD));
      sendLanding(input, focused())();
    },
  });
  sync();
  onDraftLoaded?.(sync.value());
  const dispose = mirrorDraft(
    input,
    {
      load: (value) => {
        sync.load(value);
        onDraftLoaded?.(sync.value());
      },
    },
    draftCtx,
    { retained: true, mirrored: true },
  );
  return { sync, dispose };
}

// null means this is not a reply box. False is the useful third state: a reply box
// opened by the runtime but never edited, whose empty focus is a landing rather than
// a composition the next live revision must preserve.
export const replyBoxHasDraft = (input) => {
  const ctx = replyDraftContext(input);
  return ctx ? loadDraft(ctx) !== null : null;
};

// Mechanical draft presence is independent of the conversation's settlement.
export const replyHasWords = (key) => draftHasContent("reply:" + key);
