/* One reply draft and send lifecycle shared by every view of a thread.

   A reply send draws its turn in the gesture that makes it. Its provisional result
   masks the words while the session still owes a refusal; acceptance finishes editing.
   The send preserves the panel's narrowing and, whichever control sent it, leaves the
   caret in the box for the next message, on a card or a seat as in the floating
   panel's field; Escape takes the user to the thread. The user chose this on 31
   October, as an experiment for consistency with the panel: a second send by mistake
   is rare, so keeping the caret costs little. Reverting it would again leave focus on
   the conversation's card or title (`landSent`, landing.js), ringed, where the next
   message takes `c` or Enter on the thread first. A saved draft preserves
   words independently of the editor. External settlement retains a reply the user is
   editing; deliberate Resolve leaves that editing place and closes the editor. Native
   Tab preserves the row's session independently of focus. The complete presentation
   carries its detached native owner through a complete commit, then hands the
   session to the current same-key route. The owner's row is the session's, not its
   view's, so the editor moves with the thread, its caret and undo history with it. A
   view that can draw the thread no more, a seat the thread left, a margin card whose
   thread left the margin, open or closed, or the floating panel's view of a thread the
   page takes from it, releases the row (`releaseReplies`): to a view that draws the
   thread now, or else to a parked place, connected and out of sight, until the next
   view drawing the thread claims it in place of its own row (`claim`). A thread pass releases and claims in one task, so a user writing in the
   row keeps focus throughout; a row left parked past it keeps its words, caret and
   history, but not the user. A route's view also puts the row in place of its own
   (`carry`), taking it from a view that holds it out of sight. A closed card whose
   thread is still in the margin, and a hidden panel, keep their rows, since the user
   goes on there when they open again. Every view draws whichever row it holds, a
   primary reader's reply part (primary-reader.js) as a card does. */
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
import {
  drawn,
  readCaret,
  blurFocused,
  currentLocationIn,
  onPressAway,
} from "../focus.js";
import { threadKey } from "./model.js";
import { closestAcross } from "../passages.js";
import { retainUserIntent, restrictUserIntent } from "../user-intent.js";
import { THREAD, SAY_ROW, threadPart } from "./selectors.js";
import { el, offer } from "../widget-elements.js";
import { signal } from "/runtime/framework.js";
import { move } from "../dom-move.js";
import { chromeRoot, chromeForeground } from "../chrome.js";
import { TEXT_FIELD } from "../control-selectors.js";
import { tick } from "../version-signal.js";

/** @typedef {ReturnType<typeof import("../composing/input.js").createCompositionInputs>["wireInput"]} WireInput */
/** @typedef {{actions: {reply: (key: string, text: string, options: {attempt: string}) => ReturnType<ReturnType<typeof import("./actions.js").createThreadActions>["reply"]>},
 * wireInput: WireInput,
 * landSent: ReturnType<typeof import("./landing.js").createThreadLanding>["landSent"],
 * landInThread: ReturnType<typeof import("./landing.js").createThreadLanding>["landInThread"]}} ReplyCommands */
/** @typedef {Partial<Pick<import("../composing/input.js").InputOptions,
 * "hint" | "hintParts" | "hintLead" | "accessibleName" | "busy">> & {
 * onChange?: () => void,
 * editLast?: ReturnType<typeof import("./message-edit.js").threadRewrites>["editLast"] | null,
 * sending?: (() => void) | null, sent?: (() => unknown) | null}} ReplyOptions */
/** @typedef {ReplyCommands & {onChange: () => void,
 * editLast: ReplyOptions["editLast"], sending: ReplyOptions["sending"], sent: ReplyOptions["sent"],
 * give: () => () => void, take: (owner: Composition) => void}} Binding */
/** @typedef {{context: string, key: string, row: HTMLDivElement,
 * controls: {input: ReturnType<typeof import("../composing/text-field.js").textField>, send: HTMLButtonElement | null},
 * send: import("../composing/input.js").Sender | null,
 * binding: Binding | null, changed: () => void, sync: ReturnType<WireInput>, retired?: boolean}} Composition */
/** @typedef {{owner: Composition | null,
 * editing?: NonNullable<ReturnType<typeof captureDraftEditing>>, continuing?: boolean}} Session */
/** @type {WeakMap<Element, Composition>} */
const rowCompositions = new WeakMap();
/** @type {Map<string, Session>} */
const compositions = new Map(); // context -> native session, with its current owner
// Which threads have a session is a reading paints follow (`replyIsEditing`): a
// settled thread keeps its margin entry and its box while one stands, so a session's
// start and end repaint them. Which view owns a session moves nothing here.
const sessions = signal(0);
/** @param {string} context @param {Session} session */
function openSession(context, session) {
  compositions.set(context, session);
  tick(sessions);
  return session;
}
/** @param {string} context */
function closeSession(context) {
  if (compositions.delete(context)) tick(sessions);
}
/** @type {Set<{composition: Composition, binding: Binding}>} */
const views = new Set();
/** @param {Composition | null | undefined} composition */
const available = (composition) =>
  !!composition &&
  [...views].some((view) => view.composition === composition) &&
  composition.controls.input.isConnected;
/** @param {string} context @param {Composition} composition */
function adopt(context, composition) {
  const session = compositions.get(context);
  if (session?.owner !== composition) session?.owner?.sync.cancelDictation();
  const caret = readCaret(session?.owner?.controls.input ?? null);
  if (session) session.owner = composition;
  else openSession(context, { owner: composition });
  if (caret) composition.controls.input.setSelectionRange(...caret);
  remember(composition);
}
/** @param {Composition} composition */
function remember(composition) {
  const session = compositions.get(composition.context);
  if (!session || session.owner !== composition) return;
  const editing = captureDraftEditing(composition.controls.input);
  if (editing) session.editing = editing;
}
/** @param {Element | null | undefined} node */
const compositionOf = (node) => {
  const row = closestAcross(node ?? null, SAY_ROW);
  return row ? rowCompositions.get(row) : undefined;
};
/** @param {Element | null} node */
export const replyDraftContext = (node) => compositionOf(node)?.context ?? null;
// The `threadKey` of the thread a reply row writes in, wherever the row stands, the park
// included.
/** @param {Element | null} node */
export const replyThreadKey = (node) => compositionOf(node)?.key ?? null;
// Capture native owners before preparation can detach their subscriptions. A complete
// cohort then continues through the core destination policy, independently of its own
// presentation ticket: revealing that route may need another Thread presentation.
/** @param {readonly import("./thread-card.js").ThreadRecord[]} threads
 * @param {(id: string, intent: ReturnType<typeof retainUserIntent>) => Promise<Element | null>} realize */
export function holdReplyCompositions(threads, realize) {
  const current = new Map(
    threads.map((thread) => [replyContext(threadKey(thread)), thread]),
  );
  /** @type {{context: string, session: Session, owner: Composition,
   * id: string, intent: ReturnType<typeof retainUserIntent>}[]} */
  const retained = [];
  /** @type {[string, Session][]} */
  const retired = [];
  for (const [context, session] of compositions) {
    const thread = current.get(context);
    if (!thread) {
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
    retained.push({ context, session, owner, intent, id: thread.id });
  }
  return async (/** @type {(() => unknown) | null | undefined} */ restore) => {
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
      for (const { context, owner, intent, id } of displaced) {
        if (available(owner) || !intent()) continue;
        const destination = await realize(id, intent);
        // Native Tab may move the current location while this route paints. The session still
        // owns its caret; only focus and scroll require the older placement intent.
        if (!intent.available()) continue;
        const replacement =
          compositionOf(destination) ??
          compositionOf(destination?.querySelector(SAY_ROW));
        if (replacement && drawn(replacement.controls.input))
          adopt(context, carry(replacement, owner));
      }
    } finally {
      for (const { session } of displaced) session.continuing = false;
    }
  };
}

// Whether the thread under `key` holds words the user has not sent: in its reply box,
// or in a rewrite of one of its messages, `ids`, they closed without saving.
/** @param {string} key @param {readonly string[]} ids */
export const threadHoldsDraft = (key, ids) =>
  draftHasContent(replyContext(key)) ||
  ids.some((id) => draftHasContent(rewriteContext(id)));

// Revision admission asks the owner about every native editing session, including
// one the user left by Tab. Persisted words alone do not create a session.
/** @param {(input: Element | undefined) => boolean} retains */
export const replyDraftsHold = (retains) =>
  [...compositions].some(
    ([context, session]) =>
      loadDraft(context) !== null && !retains(session.owner?.controls.input),
  );

// A composition is the row's mechanical session, not the saved draft and not focus.
// Native Tab walks its controls and the surrounding page without dismissing it.
/** @param {string} context */
function endSession(context) {
  const session = compositions.get(context);
  closeSession(context);
  // A parked row goes with its session; a row a view holds stays that view's.
  if (session?.owner && !session.owner.binding) session.owner.row.remove();
  return session;
}
/** @param {string} context */
function dismissContext(context) {
  const session = endSession(context);
  if (!session) return;
  session.owner?.sync.cancelDictation();
  session.owner?.changed();
}
/** @param {string} key */
export const dismissReply = (key) => dismissContext(replyContext(key));
// A press within the owning thread keeps its composition, including its controls
// and messages outside the reply row. Read the row first so a parked editor still
// owns its press. The declared reply part gives a split drawing the same scope.
/** @param {EventTarget | undefined} target */
const pressContext = (target) => {
  const node = target instanceof Element ? target : null;
  const row = replyDraftContext(node);
  if (row !== null) return row;
  const thread = closestAcross(node, THREAD);
  return thread ? replyDraftContext(threadPart(thread, "reply")) : null;
};
// A press away puts the composition away (focus.js, `onPressAway`); a drag into
// or out of its thread leaves it standing.
onPressAway(
  ([node]) =>
    [...compositions.keys()].some((context) => context !== pressContext(node)),
  ([node], [from]) => {
    const kept = [pressContext(node), pressContext(from)];
    for (const context of [...compositions.keys()])
      if (!kept.includes(context)) dismissContext(context);
  },
);

/** @param {Element | null} node */
export const dismissReplyAt = (node) => {
  const context = replyDraftContext(node);
  if (context !== null) dismissContext(context);
};

// The giver lets go before the taker attaches, and draws its fresh row only once the
// taker has moved this one out, so the row never leaves the document between them.
/** @param {Composition} target @param {Composition} owner @param {Binding} binding */
function handOver(target, owner, binding) {
  const redrawGiver = owner.binding?.give();
  binding.take(owner);
  redrawGiver?.();
  const session = compositions.get(owner.context);
  if (session) session.owner = owner;
  return owner;
}

// Once no view shows the session's row, the view now drawing its thread puts that row
// in place of its own, and the user goes on in their own editor, with its undo history.
// A view holding the row out of sight gives it up and draws a fresh one.
/** @param {Composition} target @param {Composition} owner */
function carry(target, owner) {
  if (
    target === owner ||
    owner.retired ||
    !target.binding ||
    (owner.binding && drawn(owner.row))
  )
    return target;
  const session = compositions.get(owner.context);
  if (session && session.owner !== owner && session.owner !== target) return target;
  return handOver(target, owner, target.binding);
}

// Where a released row waits for the next view of its thread: in the chrome, so a user
// writing in it keeps the editor, its caret and its undo history through both moves,
// and hidden. The thread pass that released it puts the thread up again in the same
// task, where a view drawing it claims the row (`claim`) before the browser drops focus
// from a hidden node.
/** @type {HTMLDivElement | null} */
let park = null;
/** @param {HTMLDivElement} row */
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
/** @param {Element} surface */
export function releaseReplies(surface) {
  for (const { owner } of compositions.values()) {
    if (!owner?.binding || !surface.contains(owner.row)) continue;
    const shown = [...views].find(
      ({ composition: view }) =>
        view.context === owner.context && view !== owner && drawn(view.controls.input),
    );
    // This view is leaving. Redrawing its replacement row could restore focus into
    // that retiring view and adopt a new session owner just before it disappears.
    owner.binding.give();
    if (shown) shown.binding.take(owner);
    else parkRow(owner.row);
  }
}

// The producer gives each native control its place in the same row on another view.
// A handoff carries Send as Send and an editor as that editor, in the row itself where
// no view holds it any more (`carry`).
/** @param {Element | null} node */
export function replyControlDestination(node) {
  const composition = compositionOf(node);
  if (!composition) return null;
  /** @type {readonly (keyof Composition["controls"])[]} */
  const parts = ["input", "send"];
  const part = parts.find((name) => composition.controls[name] === node);
  if (!part) return null;
  return (/** @type {Element | null} */ thread) => {
    const target = compositionOf(thread?.querySelector(SAY_ROW));
    return target ? carry(target, composition).controls[part] : null;
  };
}

// A thread's reply draft has several views, and sending claims its exact generation.
// A second view pressing Send afterwards reads the generation as
// spent and refuses on its own — in this tab and in any other showing the page, which is
// further than a hold kept in this document's memory reached. A send returns the
// message it drew; nothing when nothing was sent.
/** @param {string} draftCtx @param {string} key @param {string} text
 * @param {Parameters<typeof sendMessage>[1]} owns @param {ReplyCommands["actions"]} actions */
function sendReply(draftCtx, key, text, owns, actions) {
  return sendMessage(draftCtx, owns, (attempt) =>
    actions.reply(key, text, { attempt }),
  );
}

// One reply row: its native editor, wired once to the thread's draft, send, and typing
// continuation. `key` is the thread's `threadKey`, which names its draft; `parent` reads
// the message the reply answers when it is sent, since the log can name that message
// after the draft began. The typed action resolves that target from the current reading.
// What the row does for a view, its actions, `onChange` and `editLast`, is the binding
// of whichever view holds it now (`attach`).
/** @param {string} key @param {HTMLDivElement} row
 * @param {ReturnType<typeof import("../composing/text-field.js").textField>} input
 * @param {ReplyCommands} commands
 * @param {Required<Pick<ReplyOptions, "hint" | "hintParts" | "hintLead" | "accessibleName" | "busy">>} options */
function wireReply(
  key,
  row,
  input,
  commands,
  { hint, hintParts, hintLead, accessibleName, busy },
) {
  row.classList.add("lf-comment-box");
  const draftCtx = replyContext(key);
  input.value = loadDraft(draftCtx)?.text ?? "";
  const sync = commands.wireInput(input, {
    hint,
    hintParts,
    hintLead,
    accessibleName,
    busy,
    sends: "send",
    sendClass: "lf-thread-send",
    // localStorage notifies other tabs but skips this document. Page, margin, and panel
    // reply boxes are views of one draft here, so they take the same bus directly.
    // Other draft kinds still have one view per document.
    save: (v) => {
      saveDraft(draftCtx, v);
      tellDraft(draftCtx, v);
      remember(composition);
    },
    // The new turn is drawn above the box, which keeps the caret; the landing shows the
    // turn with the box, read before the send draws. A view that lands its turns
    // itself, as the floating panel's does, says so (`sent`).
    send: (...args) => composition.send?.(...args),
    // ↑ from an empty box reaches back to the user's own last words in the thread, to
    // rewrite them where they stand (`message-edit.js`). A box holding words keeps the
    // key for its caret.
    rows: [
      {
        id: "message.edit.last",
        keys: ["ArrowUp"],
        title: "edit last message",
        when: () =>
          !sync.value() && Boolean(composition.binding?.editLast?.available()),
        run: () => composition.binding?.editLast?.open(),
      },
    ],
  });
  /** @type {Composition} */
  const composition = {
    context: draftCtx,
    key,
    row,
    controls: { input, send: sync.button },
    send: null,
    binding: null,
    changed: () => composition.binding?.onChange(),
    sync,
  };
  rowCompositions.set(row, composition);
  sync();
  return composition;
}

// A view takes the row: it joins the thread's draft views and mirrors the draft, and
// focus in it makes it the editing session's owner. The returned detach gives it up.
/** @param {Composition} composition @param {Binding} binding */
function attach(composition, binding) {
  const { context, row, controls, sync } = composition;
  composition.binding = binding;
  composition.send = (_text, raw, owns) => {
    const { actions, sending, sent } = binding;
    const land = sendLanding(controls.input);
    sending?.();
    if (!sendReply(context, composition.key, raw, owns, actions)) return;
    if (sent) return sent();
    land(controls.input);
  };
  const attached = { composition, binding };
  views.add(attached);
  const begin = () => {
    adopt(context, composition);
    composition.changed();
  };
  // A row taken again catches up with words another view or tab wrote meanwhile. The
  // same words are left alone, with their caret and undo history (drafts.js, `sync.load`).
  sync.load(loadDraft(context)?.text ?? "");
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
    row.removeEventListener("focusin", begin);
    views.delete(attached);
    composition.binding = null;
    composition.send = null;
  };
}

// null means this is not a reply composition. False is the useful third state: a row
// opened by the runtime but never edited, whose empty focus is a landing rather than
// a composition the next live revision must preserve.
/** @param {Element | null} node */
export const replyCompositionHasDraft = (node) => {
  const ctx = replyDraftContext(node);
  return ctx ? loadDraft(ctx) !== null : null;
};

// Editing belongs to the reply row's session, including Send and native Tab browsing.
// Persisted words alone never reopen an editor after settlement or reload.
/** @param {string} key */
export const replyIsEditing = (key) => {
  sessions.value;
  return compositions.has(replyContext(key));
};

// A live revision carries an actual editing session, under its draft subscription's
// exact generation. A fresh document has not materialized its native owner yet: the
// session stands through that route's awaited landing, then either has an owner or
// retires. Ordinary reload carries no editing capability and never enters this path.
/** @param {ReturnType<typeof captureDraftEditing>} editing
 * @param {() => Promise<Element | null>} land */
export async function restoreReplyEditing(editing, land) {
  if (!editing?.mirrored || !draftEditingStands(editing)) return null;
  const context = editing.context;
  let session = compositions.get(context);
  if (!session) session = openSession(context, { owner: null });
  try {
    return await land();
  } finally {
    if (compositions.get(context) === session && !available(session.owner))
      closeSession(context);
  }
}

// Native editor construction has one home; cards and package fragments share its
// draft, input, delivery and recovery lifetime rather than constructing another one.
// A presentation may say what its empty box reads (`hint`), what stands before that
// (`hintLead`), and is named (`accessibleName`), hold its sends while it covers the box's words (`busy`), and
// land a send's turn itself (`sent`), as the floating panel's view does at its end,
// told before the send draws (`sending`). The view draws its row again
// on `redraw`, as it takes another in its place.
/** @param {string} key @param {ReplyCommands} commands
 * @param {() => void} redraw @param {ReplyOptions} [options] */
export function createReplyView(
  key,
  commands,
  redraw,
  {
    onChange = () => {},
    editLast = null,
    hint = () => "Reply",
    hintParts = null,
    hintLead = () => "",
    accessibleName = "Reply",
    busy = () => false,
    sending = null,
    sent = null,
  } = {},
) {
  const fresh = () => {
    const row = offer("div", "lf-thread-reply");
    const input = offer(TEXT_FIELD);
    input.name = "reply";
    row.append(input);
    return wireReply(key, row, input, commands, {
      hint,
      hintParts,
      hintLead,
      accessibleName,
      busy,
    });
  };
  let composition = fresh();
  /** @type {Binding} */
  const binding = {
    ...commands,
    onChange,
    editLast,
    sending,
    sent,
    give: () => {
      detach({ handingOn: true });
      composition = fresh();
      detach = attach(composition, binding);
      return redraw;
    },
    take: (owner) => {
      if (currentLocationIn(composition.row)) blurFocused();
      detach();
      composition.retired = true;
      composition = owner;
      detach = attach(composition, binding);
      redraw();
    },
  };
  let detach = attach(composition, binding);
  // A view takes the session's row in its place and draws it (`redraw`), and gives its
  // own up for a fresh one (`carry`), drawn by the step it returns.
  return {
    get node() {
      return composition.row;
    },
    get input() {
      return composition.controls.input;
    },
    cancelDictation: () => composition.sync.cancelDictation(),
    // Paint the box again where what its `hint` reads has changed.
    sync: () => composition.sync(),
    // A view drawing the thread takes its session's row where no view holds it: one
    // released to the park, or one whose view went. It does so once it stands in the
    // document, `shown`, so the move keeps the user in the row (dom-move.js).
    /** @param {() => boolean} shown */
    claim(shown) {
      const owner = compositions.get(composition.context)?.owner;
      if (owner && owner !== composition && !owner.binding && !owner.retired && shown())
        binding.take(owner);
    },
    dispose: () => detach(),
  };
}
