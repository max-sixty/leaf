/* One reply draft and send lifecycle shared by every view of a thread.

   A reply send draws its turn in the gesture that makes it. Its provisional result
   masks the words while the session still owes a refusal; acceptance finishes editing.
   The send preserves the panel's
   narrowing and, whichever control sent it, takes the user out of the reply box to stand
   on the thread (`landSent`), since a reply is usually their last word until the agent
   answers. `c`, or Enter on the thread, opens the box again. A saved draft preserves
   words independently of the editor. External settlement retains a reply the user is
   editing; deliberate Resolve leaves that editing place and closes the editor. Native
   Tab preserves the row's session independently of focus. The complete presentation
   carries its detached native owner through a complete commit, then hands the
   session and caret to the current same-key route. */
import {
  captureDraftEditing,
  loadDraft,
  draftHasContent,
  draftEditingStands,
  mirrorDraft,
  saveDraft,
  sendMessage,
  tellDraft,
} from "../drafts.js";
import { sendLanding } from "./reply-landing.js";
import { readCaret } from "../focus.js";
import { threadKey } from "./model.js";
import { closestAcross } from "../passages.js";
import { focused } from "../keyboard/scopes.js";
import { retainUserIntent, restrictUserIntent } from "../user-intent.js";
import { THREAD, SAY_ROW } from "./selectors.js";

const REPLY_COMPOSITION = Symbol("reply composition");
const compositions = new Map(); // context -> native session, with its current owner
const views = new Map();
const replyContext = (key) => "reply:" + key;
const available = (composition) =>
  Boolean(composition) &&
  views.get(composition.context)?.has(composition) &&
  composition.controls.input.isConnected;
function adopt(context, composition) {
  const session = compositions.get(context);
  const caret = readCaret(session?.owner?.controls.input);
  if (session) session.owner = composition;
  else compositions.set(context, { owner: composition });
  if (caret) composition.controls.input.setSelectionRange(...caret);
  remember(composition);
}
function remember(composition) {
  const session = compositions.get(composition.context);
  if (session?.owner !== composition) return;
  const editing = captureDraftEditing(composition.controls.input);
  if (editing) session.editing = editing;
}
const compositionOf = (node) => closestAcross(node, SAY_ROW)?.[REPLY_COMPOSITION];
export const replyDraftContext = (node) => compositionOf(node)?.context ?? null;
// Capture native owners before preparation can detach their subscriptions. A complete
// cohort then continues through the core destination policy, independently of its own
// presentation ticket: revealing that route may need another Thread presentation.
export function holdReplyCompositions(threads, realize) {
  const current = new Map(
    threads.map((thread) => [replyContext(threadKey(thread)), thread]),
  );
  const retained = [];
  const retired = [];
  for (const [context, session] of compositions) {
    if (!current.has(context)) {
      retired.push([context, session]);
      continue;
    }
    if (!session.owner || session.continuing) continue;
    const owner = session.owner;
    const editing = captureDraftEditing(owner.controls.input) ?? session.editing;
    if (!editing) continue;
    session.editing = editing;
    const intent = restrictUserIntent(
      retainUserIntent(),
      () =>
        compositions.get(context) === session &&
        session.owner === owner &&
        draftEditingStands(editing),
    );
    retained.push({ context, session, owner, intent });
  }
  return async (restore) => {
    for (const [context, session] of retired)
      if (compositions.get(context) === session) compositions.delete(context);
    const displaced = retained.filter(
      ({ session, owner, intent }) =>
        !available(owner) && !session.continuing && intent(),
    );
    // Focus restoration can itself reveal a route and start another Thread cohort.
    // Claim the whole continuation before that wait, not just its nonfocus tail.
    for (const { session } of displaced) session.continuing = true;
    try {
      await restore?.();
      for (const { context, owner, intent } of displaced) {
        if (available(owner) || !intent()) continue;
        const destination = await realize(current.get(context).id, intent);
        // Native Tab may move standing while this route paints. The session still
        // owns its caret; only focus and scroll require the older placement intent.
        if (!intent.available()) continue;
        const replacement =
          compositionOf(destination) ??
          compositionOf(destination?.querySelector(SAY_ROW));
        if (replacement && replacement.controls.input.checkVisibility())
          adopt(context, replacement);
      }
    } finally {
      for (const { session } of displaced) session.continuing = false;
    }
  };
}

export const hasReplyComposition = () => compositions.size > 0;

// A composition is the row's mechanical session, not the saved draft and not focus.
// Native Tab walks its controls and the surrounding page without dismissing it.
function dismissContext(context) {
  const session = compositions.get(context);
  if (!session) return;
  compositions.delete(context);
  session.owner?.changed();
}
export const dismissReply = (key) => dismissContext(replyContext(key));
// A pointer press elsewhere puts the composition away. Keyboard activation emits
// click too, but Send, Resolve and the declared leave command own their addressed row.
document.addEventListener(
  "click",
  (event) => {
    if (event.detail === 0) return;
    const within = replyDraftContext(event.composedPath()[0]);
    for (const context of compositions.keys())
      if (context !== within) dismissContext(context);
  },
  true,
);

export const dismissReplyAt = (node) => {
  const context = replyDraftContext(node);
  if (context !== null) dismissContext(context);
};

// The producer gives each native control its place in the same row on another view.
// A handoff carries Send as Send and an editor as that editor, with its caret.
export function replyControlDestination(node) {
  const composition = compositionOf(node);
  if (!composition) return null;
  const part = Object.keys(composition.controls).find(
    (name) => composition.controls[name] === node,
  );
  return part
    ? (thread) => compositionOf(thread?.querySelector(SAY_ROW))?.controls[part] ?? null
    : null;
}

// A thread's reply draft has several views, and sending claims its exact generation.
// A second view pressing Send afterwards reads the generation as
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
  row,
  input,
  send,
  { actions, wireInput, landSent, onChange },
) {
  const draftCtx = replyContext(key);
  const composition = {
    context: draftCtx,
    controls: { input, send },
    changed: onChange,
  };
  row[REPLY_COMPOSITION] = composition;
  let instances = views.get(draftCtx);
  if (!instances) views.set(draftCtx, (instances = new Set()));
  instances.add(composition);
  const begin = () => {
    adopt(draftCtx, composition);
    onChange();
  };
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
      remember(composition);
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
  // Construction supplies a mirror, not ownership: a hidden panel mirror cannot
  // take the session from the current route while that route is being replaced.
  onChange();
  const stopMirror = mirrorDraft(input, sync, draftCtx, {
    retained: true,
    mirrored: true,
    onChange: (value) => {
      // A provisional send masks words; only settlement ends their native session.
      // Refusal restores the same generation unless the user already put it away.
      if (value === null && !draftHasContent(draftCtx)) dismissContext(draftCtx);
      remember(composition);
      onChange();
    },
  });
  row.addEventListener("focusin", begin);
  return {
    sync,
    dispose: () => {
      stopMirror();
      row.removeEventListener("focusin", begin);
      instances.delete(composition);
      if (!instances.size) views.delete(draftCtx);
    },
  };
}

// null means this is not a reply composition. False is the useful third state: a row
// opened by the runtime but never edited, whose empty focus is a landing rather than
// a composition the next live revision must preserve.
export const replyCompositionHasDraft = (node) => {
  const ctx = replyDraftContext(node);
  return ctx ? loadDraft(ctx) !== null : null;
};

// Editing belongs to the reply row's session, including Send and native Tab browsing.
// Persisted words alone never reopen an editor after settlement or reload.
export const replyIsEditing = (key) => compositions.has(replyContext(key));

// Every reply renderer and route shares the same admission: open conversation,
// or a settled conversation whose native editing session still owns its words.
export const replyAvailable = (thread) =>
  !thread.resolved || replyIsEditing(threadKey(thread));

// A live revision carries an actual editing session, under its draft subscription's
// exact generation. A fresh document has not materialized its native owner yet: the
// session stands through that route's awaited landing, then either has an owner or
// retires. Ordinary reload carries no editing capability and never enters this path.
export async function restoreReplyEditing(editing, land) {
  if (!editing?.mirrored || !draftEditingStands(editing)) return null;
  const context = editing.context;
  let session = compositions.get(context);
  if (!session) compositions.set(context, (session = { owner: null }));
  try {
    return await land();
  } finally {
    if (compositions.get(context) === session && !available(session.owner))
      compositions.delete(context);
  }
}
