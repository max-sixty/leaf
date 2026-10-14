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
   view's, so the editor moves with the thread, its caret and undo history with it. A
   view that can draw the thread no more, a seat the thread left or a margin card whose
   thread left the margin, open or closed, releases the row (`releaseReplies`): to a
   view that draws the thread now, or else to a parked place, connected and out of
   sight, until the next view drawing the thread claims it in place of its own row
   (`claim`). A thread pass releases and claims in one task, so a user writing in the
   row keeps focus throughout; a row left parked past it keeps its words, caret and
   history, but not the user. A route's view also puts the row in place of its own
   (`carry`), taking it from a view that holds it out of sight. A closed card whose
   thread is still in the margin, and a hidden panel, keep their rows, since the user
   goes on there when they open again. A view that cannot draw another row, a package
   mirror, takes the session and caret into its own. */
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
import { readCaret, focused, standingIn } from "../focus.js";
import { threadKey } from "./model.js";
import { closestAcross } from "../passages.js";
import { retainUserIntent, restrictUserIntent } from "../user-intent.js";
import { THREAD, SAY_ROW } from "./selectors.js";
import { editContext } from "./message-edit.js";
import { el, offer } from "../widget-elements.js";
import { move } from "../dom-move.js";
import { chromeRoot, chromeForeground } from "../chrome.js";
import { pressIsKeyboardActivation } from "../pointer.js";
import { TEXT_FIELD } from "../control-selectors.js";

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
// The `threadKey` of the thread a reply row writes in, wherever the row stands, the park
// included.
export const replyThreadKey = (node) => compositionOf(node)?.key ?? null;
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
      if (compositions.get(context) === session) endSession(context);
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
  ids.some((id) => draftHasContent(editContext(id)));

// Revision admission asks the owner about every native editing session, including
// one the user left by Tab. Persisted words alone do not create a session.
export const replyDraftsHold = (retains) =>
  [...compositions].some(
    ([context, session]) =>
      loadDraft(context) !== null && !retains(session.owner?.controls.input),
  );

// A composition is the row's mechanical session, not the saved draft and not focus.
// Native Tab walks its controls and the surrounding page without dismissing it.
function endSession(context) {
  const session = compositions.get(context);
  compositions.delete(context);
  // A parked row goes with its session; a row a view holds stays that view's.
  if (session?.owner && !session.owner.binding) session.owner.row.remove();
  return session;
}
function dismissContext(context) {
  const session = endSession(context);
  if (!session) return;
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
    if (pressIsKeyboardActivation(event)) return;
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

// The giver lets go before the taker attaches, and draws its fresh row only once the
// taker has moved this one out, so the row never leaves the document between them.
function handOver(target, owner) {
  const redrawGiver = owner.binding?.give();
  target.binding.take(owner);
  redrawGiver?.();
  const session = compositions.get(owner.context);
  if (session) session.owner = owner;
  return owner;
}

// Once no view shows the session's row, the view now drawing its thread puts that row
// in place of its own, and the user goes on in their own editor, with its undo history.
// A view holding the row out of sight gives it up and draws a fresh one. A view that
// cannot draw another row, a package mirror, keeps its own.
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
  return handOver(target, owner);
}

// Where a released row waits for the next view of its thread: in the chrome, so a user
// writing in it keeps the editor, its caret and its undo history through both moves,
// and hidden. The thread pass that released it puts the thread up again in the same
// task, where a view drawing it claims the row (`claim`) before the browser drops focus
// from a hidden node.
let park = null;
function parkRow(row) {
  if (!park) {
    park = el("div", "lf-reply-park");
    park.hidden = true;
  }
  if (!park.isConnected) move(chromeRoot, park, chromeForeground);
  move(park, row, null);
}

// A view that can draw its thread no more (above) releases the session rows it holds
// within `surface`: each goes to a view drawing that thread now, or to the park.
export function releaseReplies(surface) {
  for (const { owner } of compositions.values()) {
    if (!owner?.binding?.give || !surface.contains(owner.row)) continue;
    const shown = [...views.get(owner.context)].find(
      (view) =>
        view !== owner && view.binding.take && view.controls.input.checkVisibility(),
    );
    if (shown) handOver(shown, owner);
    else {
      const redrawGiver = owner.binding.give();
      parkRow(owner.row);
      redrawGiver();
    }
  }
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
function wireReply(key, row, input, send, wireInput, { hint, accessibleName }) {
  row.classList.add("lf-comment-box");
  const draftCtx = replyContext(key);
  const composition = {
    context: draftCtx,
    key,
    row,
    controls: { input, send },
    binding: null,
    changed: () => composition.binding?.onChange(),
  };
  row[REPLY_COMPOSITION] = composition;
  input.value = loadDraft(draftCtx) ?? "";
  const sync = wireInput(input, {
    hint,
    accessibleName,
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
    // sent from, around wherever the send left them standing. A view whose box stays
    // for the next turn lands the send itself (`sent`).
    send: (_text, raw, owns) => {
      const { actions, landSent, sent } = composition.binding;
      if (!sendReply(draftCtx, key, raw, owns, actions)) return;
      if (sent) return sent();
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
        description: "Edit my last message in the thread",
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
  // A row handed on to another view (`give`) keeps its dictation, as it keeps focus,
  // caret and history; one this view ends with it stops listening.
  return ({ handingOn = false } = {}) => {
    if (!handingOn) sync.cancelDictation();
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
// A presentation may say what its empty box reads (`hint`) and is named
// (`accessibleName`), and where its box stays for the next turn, as the floating
// panel's field does, land a send itself (`sent`) rather than stand on the thread.
export function createReplyView(
  key,
  commands,
  {
    onChange = () => {},
    editLast = null,
    reveal = null,
    sizes = null,
    redraw = null,
    hint = "Reply",
    accessibleName = "Reply",
    sent = null,
  } = {},
) {
  const fresh = () => {
    const row = offer("div", "lf-thread-reply");
    const input = offer(TEXT_FIELD);
    input.name = "reply";
    const send = offer("button", "lf-btn lf-thread-send", "Send");
    row.append(input, send);
    return wireReply(key, row, input, send, commands.wireInput, {
      hint,
      accessibleName,
    });
  };
  let composition = fresh();
  const binding = { ...commands, onChange, editLast, reveal, sizes, sent };
  let detach = attach(composition, binding);
  // A view that draws its row again on `redraw` can take the session's in its place,
  // and give its own up for a fresh one (`carry`), drawn by the step it returns.
  if (redraw) {
    binding.give = () => {
      detach({ handingOn: true });
      composition = fresh();
      detach = attach(composition, binding);
      return redraw;
    };
    binding.take = (owner) => {
      // The row going holds no place of the user's: whoever carries the owner's row
      // puts them in it (focus.js, `replyDestination`), not the redraw's focus hold.
      if (standingIn(composition.row)) focused().blur();
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
    // A view drawing the thread takes its session's row where no view holds it: one
    // released to the park, or one whose view went. It does so once it stands in the
    // document, `shown`, so the move keeps the user in the row (dom-move.js).
    claim(shown) {
      const owner = compositions.get(composition.context)?.owner;
      if (
        binding.take &&
        owner &&
        owner !== composition &&
        !owner.binding &&
        !owner.retired &&
        shown()
      )
        binding.take(owner);
    },
    dispose: () => detach(),
  };
}
