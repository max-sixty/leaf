/* One reply draft and send lifecycle shared by every view of a thread.

   A reply send draws its turn in the gesture that makes it. Its provisional result
   masks the words while the session still owes a refusal; acceptance finishes editing.
   The send preserves the panel's narrowing and, whichever control sent it, leaves
   focus on the conversation's card or title (`landSent`). Sending never returns focus
   to the page. `c`, or Enter on the thread, opens the box again. A saved draft preserves
   words independently of the editor. External settlement retains a reply the user is
   editing; deliberate Resolve leaves that editing place and closes the editor. Native
   Tab preserves the row's session independently of focus. The complete presentation
   carries its detached native owner through a complete commit, then hands the
   session to the current same-key route. The owner's row is the session's, not its
   view's: the route's view puts it in place of its own row (`carry`), taking it from a
   view that holds it out of sight, as a closed margin card does, so the editor moves
   with the thread, its caret and undo history with it. A view that cannot draw
   another row, a package mirror, takes the session and caret into its own. */
import {
  captureDraftEditing,
  loadDraft,
  draftHasContent,
  draftEditingStands,
  mirrorDraft,
  replyContext,
  rewriteContext,
  saveDraft,
  sendMessage,
  tellDraft,
} from "../drafts.js";
import { sendLanding } from "./reply-landing.js";
import { readCaret, focused } from "../focus.js";
import { threadKey } from "./model.js";
import { closestAcross } from "../passages.js";
import { retainUserIntent, restrictUserIntent } from "../user-intent.js";
import { THREAD, SAY_ROW } from "./selectors.js";
import { offer } from "../widget-elements.js";
import { TEXT_FIELD } from "../control-selectors.js";

const REPLY_COMPOSITION = Symbol("reply composition");
const compositions = new Map(); // context -> native session, with its current owner
const views = new Map();
const available = (composition) =>
  Boolean(composition) &&
  views.get(composition.context)?.has(composition) &&
  composition.controls.input.isConnected;
function adopt(context, composition) {
  const session = compositions.get(context);
  if (session?.owner !== composition) session?.owner?.sync.cancelDictation();
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
          adopt(context, carry(replacement, owner));
      }
    } finally {
      for (const { session } of displaced) session.continuing = false;
    }
  };
}

// Whether the thread under `key` holds words the user has not sent: in its reply box,
// or in a rewrite of one of its messages, `ids`, they closed without saving.
export const threadHoldsDraft = (key, ids) =>
  draftHasContent(replyContext(key)) ||
  ids.some((id) => draftHasContent(rewriteContext(id)));

// Revision admission asks the owner about every native editing session, including
// one the user left by Tab. Persisted words alone do not create a session.
export const replyDraftsHold = (retains) =>
  [...compositions].some(
    ([context, session]) =>
      loadDraft(context) !== null && !retains(session.owner?.controls.input),
  );

// A composition is the row's mechanical session, not the saved draft and not focus.
// Native Tab walks its controls and the surrounding page without dismissing it.
function dismissContext(context) {
  const session = compositions.get(context);
  if (!session) return;
  compositions.delete(context);
  session.owner?.sync.cancelDictation();
  session.owner?.changed();
}
export const dismissReply = (key) => dismissContext(replyContext(key));
// Withholding an entire surface ends capture without dismissing its editing session
// or discarding its words. A panel can retain all its reply nodes while it is hidden.
export function cancelReplyDictation(surface) {
  for (const instances of views.values())
    for (const composition of instances)
      if (surface.contains(composition.controls.input))
        composition.sync.cancelDictation();
}
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

// Once no view shows the session's row, the view now drawing its thread puts that row
// in place of its own, and the user goes on in their own editor, with its undo history.
// A view holding the row out of sight, as a closed margin card does, gives it up and
// draws a fresh one. A view that cannot draw another row, a package mirror, keeps its
// own.
function carry(target, owner) {
  const giver = owner.binding;
  if (
    target === owner ||
    owner.retired ||
    !target.binding?.take ||
    (giver && (!giver.give || owner.row.checkVisibility()))
  )
    return target;
  const session = compositions.get(owner.context);
  if (session && session.owner !== owner && session.owner !== target) return target;
  // The giver lets go before the taker attaches, and draws its fresh row only once the
  // taker has moved this one out, so the row never leaves the document between them.
  const redrawGiver = giver?.give();
  target.binding.take(owner);
  redrawGiver?.();
  if (session) session.owner = owner;
  return owner;
}

// The producer gives each native control its place in the same row on another view.
// A handoff carries Send as Send and an editor as that editor, in the row itself where
// no view holds it any more (`carry`).
export function replyControlDestination(node) {
  const composition = compositionOf(node);
  if (!composition) return null;
  const part = Object.keys(composition.controls).find(
    (name) => composition.controls[name] === node,
  );
  if (!part) return null;
  return (thread) => {
    const target = compositionOf(thread?.querySelector(SAY_ROW));
    return target ? carry(target, composition).controls[part] : null;
  };
}

// A thread's reply draft has several views, and sending claims its exact generation.
// A second view pressing Send afterwards reads the generation as
// spent and refuses on its own — in this tab and in any other showing the page, which is
// further than a hold kept in this document's memory reached.
const sendReply = (draftCtx, key, text, owns, actions) =>
  sendMessage(draftCtx, owns, (attempt) => actions.reply(key, text, { attempt }));

// One reply row: its native editor, wired once to the thread's draft, send, and typing
// continuation. `key` is the thread's `threadKey`, which names its draft; `parent` reads
// the message the reply answers when it is sent, since the log can name that message
// after the draft began. The typed action resolves that target from the current reading.
// What the row does for a view, its actions, `onChange` and `editLast`, is the binding
// of whichever view holds it now (`attach`).
function wireReply(key, row, input, send, wireInput) {
  row.classList.add("lf-comment-box");
  const draftCtx = replyContext(key);
  const composition = {
    context: draftCtx,
    row,
    controls: { input, send },
    binding: null,
    changed: () => composition.binding?.onChange(),
  };
  row[REPLY_COMPOSITION] = composition;
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
      const { actions, landSent } = composition.binding;
      if (!sendReply(draftCtx, key, raw, owns, actions)) return;
      landSent(closestAcross(input, THREAD));
      sendLanding(input, focused())();
    },
    // ↑ from an empty box reaches back to the user's own last words in the thread, to
    // rewrite them where they stand (`message-edit.js`). A box holding words keeps the
    // key for its caret.
    rows: [
      {
        id: "message.edit.last",
        keys: ["ArrowUp"],
        description: "Edit your last message in the thread",
        title: "edit last message",
        when: () =>
          !sync.value() && Boolean(composition.binding?.editLast?.available()),
        run: () => composition.binding?.editLast?.open(),
      },
    ],
  });
  composition.sync = sync;
  sync();
  return composition;
}

// A view takes the row: it joins the thread's draft views and mirrors the draft, and
// focus in it makes it the editing session's owner. The returned detach gives it up.
function attach(composition, binding) {
  const { context, row, controls, sync } = composition;
  composition.binding = binding;
  controls.input.lfRevealReply = binding.reveal ?? undefined;
  binding.sizes?.observe(row);
  let instances = views.get(context);
  if (!instances) views.set(context, (instances = new Set()));
  instances.add(composition);
  const begin = () => {
    adopt(context, composition);
    composition.changed();
  };
  // A row taken again catches up with words another view or tab wrote meanwhile. The
  // same words are left alone, with their caret and undo history (drafts.js, `sync.load`).
  sync.load(loadDraft(context) ?? "");
  // Attaching supplies a mirror, not ownership: a hidden panel mirror cannot take the
  // session from the current route while that route is being replaced. Nor does it
  // tell the view, which draws the row itself (`redraw`): a told view of a settled
  // thread asks for a presentation, whose continuation would carry again.
  const stopMirror = mirrorDraft(controls.input, sync, context, {
    retained: true,
    mirrored: true,
    onChange: (value) => {
      // A provisional send masks words; only settlement ends their native session.
      // Refusal restores the same generation unless the user already put it away.
      if (value === null && !draftHasContent(context)) dismissContext(context);
      remember(composition);
      composition.changed();
    },
  });
  row.addEventListener("focusin", begin);
  return () => {
    sync.cancelDictation();
    stopMirror();
    binding.sizes?.unobserve(row);
    delete controls.input.lfRevealReply;
    row.removeEventListener("focusin", begin);
    instances.delete(composition);
    if (!instances.size) views.delete(context);
    composition.binding = null;
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

// Native editor construction has one home; cards and package fragments share its
// draft, input, delivery and recovery lifetime rather than constructing another one.
export function createReplyView(
  key,
  commands,
  {
    onChange = () => {},
    editLast = null,
    reveal = null,
    sizes = null,
    redraw = null,
  } = {},
) {
  const fresh = () => {
    const row = offer("div", "lf-thread-reply");
    const input = offer(TEXT_FIELD);
    input.name = "reply";
    const send = offer("button", "lf-btn lf-thread-send", "Send");
    row.append(input, send);
    return wireReply(key, row, input, send, commands.wireInput);
  };
  let composition = fresh();
  const binding = { ...commands, onChange, editLast, reveal, sizes };
  let detach = attach(composition, binding);
  // A view that draws its row again on `redraw` can take the session's in its place,
  // and give its own up for a fresh one (`carry`), drawn by the step it returns.
  if (redraw) {
    binding.give = () => {
      detach();
      composition = fresh();
      detach = attach(composition, binding);
      return redraw;
    };
    binding.take = (owner) => {
      // The row going holds no place of the user's: whoever carries the owner's row
      // puts them in it (focus.js, `replyDestination`), not the redraw's focus hold.
      if (composition.row.contains(focused())) focused().blur();
      detach();
      // The row given up is gone for good, so no later hand-off carries it back.
      composition.retired = true;
      composition = owner;
      detach = attach(composition, binding);
      redraw();
    };
  }
  return {
    get node() {
      return composition.row;
    },
    get input() {
      return composition.controls.input;
    },
    cancelDictation: () => composition.sync.cancelDictation(),
    dispose: () => detach(),
  };
}
