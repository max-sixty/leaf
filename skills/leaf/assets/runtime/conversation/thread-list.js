/* Retained comment-panel list reconciliation.

   `renderThreads` holds one live card through every list mutation. It chooses the card
   under the pointer while the pointer is in the list, then the card containing focus,
   then the topmost visible card. It records later visible cards before the mutation
   and refreshes their baselines after each correction, so a live successor can take
   over if the first leaves or becomes hidden. The held `paintAcknowledgments` call
   covers claim-only mutations too. The list follows changes in the card's content
   position, keeping reflow out from under the pointer without fighting an intentional
   scroll. Browser scroll anchoring is disabled only for the life of a hold so those two
   authorities cannot compensate the same change; outside a held mutation the browser
   keeps its native safety net. The correction runs after each mutation and on every
   frame of a resolution fold; fold completion removes its node through
   `renderThreads`, under the same hold.

   `pageOutline` reads the page's own headings, and `groupFor` names the run of threads
   under each (conversation/placement.js). A run's heading is one node kept across
   reconciles and stuck to the top of the list while its run scrolls past. A stuck box
   is held by its margin edge inside the scroller's content, so the room above a
   heading is its own padding and the pin is drawn back over `--lf-list-inset`, the
   property the list spends its own inset from. A margin there, or a `top` of zero,
   leaves a strip the list scrolls through in full view.

   Being pinned is `.lf-pinned`, worn by the run headings. It is also what
   `renderThreads` sweeps to answer how much of the list's top stands covered. That
   answer is the one number in the list's `scroll-padding` that CSS
   cannot work out, because a long heading wraps — the tallest is written to
   `--lf-head-room`, and a `ResizeObserver` on the list writes it again when the reader
   draws the panel narrower and a heading wraps — a drag posts no event, so a reconcile
   never comes. Without it a walk lands threads under the heading with the opening
   words of the comment behind it, which is what
   `test_no_focus_ring_the_keyboard_lands_on_is_cut_or_covered` holds.

   The measurement is taken only while the panel is open, and this is a rule rather
   than an optimization. Shut, the panel is `display: none` and every heading measures
   zero, so the number written is not the room a heading takes but the absence of a
   panel. Taking it anyway costs a forced layout on every reconcile, for a page whose
   reader may never open the panel at all — and that cost is not notional: it delayed
   an event's acknowledgement past the window an undo is offered in, so a press the key
   line had just promised was refused, which
   `test_an_action_response_accounts_for_its_gesture_without_a_follow_up_poll` caught
   under a loaded machine and nowhere else. The observer covers the reopen, a box
   arriving being a resize, so the number is written at the first moment it can be
   right. A retained value from the last open panel is a real measurement and stands
   until then; the property is unset until the first open, where the `0px` fallback in
   the rule is the honest answer.

   Reserved room only reaches a control that lands in it, and a press lands nowhere:
   the browser focuses the card under the pointer and scrolls nothing. So the thread
   list lands a thread that takes the focus, whoever moved it, and that is the row the
   ownership map in skills/leaf/assets/CLAUDE.md carries. Without it a list nudged a dozen pixels leaves the first
   card of a run under its own stuck heading by the width of an inset ring, which is a
   card with three sides. A press lands when it is over rather than as focus arrives,
   because focus arrives on the way down and the press may be the start of a drag
   across the comment's own words; a drag that ends in the thread takes no landing at
   all. What it lands is the thread the completed gesture leaves the reader in, not the
   one the focus moved to, so a press on the thread they are already standing in —
   which moves no focus — brings it back like any other.

   This is an arrival rule and not a promise about the paint. Scrolling the list under
   a standing thread cuts its ring again, and nothing re-lands it: the reader is moving
   away from what they were standing in, and a control under something is a fact about
   where it was put. A thread taller than the list's own scrollport is the excepted
   case in both directions — there is no scroll that shows all of it, which is the same
   thing the ring reading declines to report. Landing in a reply inside such a thread
   reveals its composer and actions together; an editor too tall to fit with its
   actions reveals the focused control itself.

   `test_no_ring_the_panel_draws_on_a_walk_down_its_list_is_cut_or_covered`,
   `test_a_comment_the_pointer_lands_on_comes_out_from_under_the_run_heading`, and
   `test_every_ring_the_layer_draws_is_shown_whole_somewhere_in_the_corpus` hold this
   for the panel's own walk, for a press inside its list, and for every shipped page's
   tab order. They ask one question: where the control can be seen, so can the ring
   that names it. A control that itself stands under a fixed bar is not a finding —
   that is a fact about where it was put — and neither is a box too tall for the region
   it is in. */
import { scrollBehavior } from "../motion.js";
import { threadsBox } from "./panel-elements.js";
import { pointerAt } from "../pointer.js";
import { focused } from "../keyboard/scopes.js";
import { conversational, threadKey } from "./model.js";
import { runtime } from "../context.js";
import { ago } from "../presence.js";
import { retireConversationNode } from "./reaction-strips.js";
import { readApplication, whenWidgetsPresented } from "../semantic-state.js";
import { captureAuthoredFacets } from "../projection/authored.js";
import { reachScrollers } from "../reach.js";
import { foldOut, hasFolding, isFolding } from "./folding.js";
import { inPageOrder, pageOutline, threadGroups } from "./placement.js";
import { inFilter, noMatchText, paintNarrowing } from "./narrowing.js";
import { paintThreadQuotes, threadNode } from "./thread-card.js";

// The open threads, in the order t/T walk either surface. The panel's children are the
// canonical list: folding a settled thread renames it out of this list in that frame.
export const openThreads = ({
  visibleOnly = true,
  panelOpen = threadsBox.checkVisibility(),
} = {}) =>
  [...threadsBox.querySelectorAll(":scope > .lf-thread")].filter(
    (thread) =>
      (!visibleOnly || !thread.hidden) &&
      (panelOpen || thread.dataset.resolved !== "true"),
  );

const emptyText =
  "No threads yet. Select any text on the page to comment on it, or use the box below.";

// The one number in the list's scroll-padding that CSS cannot work out: a run heading
// sticks over the top of this box, and a long one wraps, so how much of the top is
// covered is a measurement rather than a constant. The tallest, not the stuck one — the
// browser is given one number to scroll by and cannot be told which heading will be under
// the landing, and reserving more than a shorter heading needs only lands the thread a few
// pixels lower.
//
// It follows the box rather than the log. Wrapping is a function of the list's width, and
// the reader sets that themselves by dragging the panel's edge — a drag posts no event, so
// a reconcile never came, and a heading that had grown from one line to two went on being
// reserved for at one. Threads then landed under it, which is the whole defect this
// number exists to prevent. Writing a custom property does not resize the observed box,
// so the observer cannot feed itself.
function paintHeadRoom(panelIsOpen) {
  // Not while the panel is shut, which is most of a page's life. Every heading measures
  // zero in `display: none`, so the answer is never the room a heading takes — it is the
  // absence of a panel, written at the cost of a forced layout on every reconcile for a
  // number no reader can be standing in. That cost is not theoretical: under a loaded
  // machine it delayed an event's acknowledgement past the window an undo is offered in,
  // and `test_an_action_response_accounts_for_its_gesture_without_a_follow_up_poll` lost
  // its press to a gesture that had not settled yet. The observer fires when the panel
  // opens — a box arriving is a resize — so the measurement lands the moment it means
  // something, which is also the only moment it can be right.
  if (!panelIsOpen()) return;
  const heads = [...threadsBox.querySelectorAll(".lf-pinned")];
  threadsBox.style.setProperty(
    "--lf-head-room",
    `${Math.max(0, ...heads.map((h) => h.offsetHeight))}px`,
  );
}
// Observed once the chrome is mounted (leaf.js): the list is the panel's.
export function mountThreadList(panelIsOpen) {
  new ResizeObserver(() => paintHeadRoom(panelIsOpen)).observe(threadsBox);
}

// Keep one card at the same viewport position while this list changes around it.
// The pointer is the most recent place the reader named; focus is the standing place
// when the hand is elsewhere, and the first visible card is the list's own fallback.
// Capture the later visible cards too, so removing the first choice can hand the hold
// to the next card without trying to recover its old position after the mutation.
let activeHold = null;
const contentTop = (card) => card.getBoundingClientRect().top + threadsBox.scrollTop;
const maxScrollTop = () =>
  Math.max(0, threadsBox.scrollHeight - threadsBox.clientHeight);
// The box a card can hold the list's place by, or null where it can hold nothing: a
// fold renames its node out of .lf-thread on the way out, and a narrowing hides one.
// One statement of it, so what takes a hold and what corrects one cannot disagree over
// which cards are still standing.
const heldBox = (card) => {
  if (
    !card.isConnected ||
    !threadsBox.contains(card) ||
    !card.matches(".lf-thread") ||
    !card.checkVisibility()
  )
    return null;
  const box = card.getBoundingClientRect();
  return box.width && box.height ? box : null;
};
function takeScrollHold(panelIsOpen) {
  const priorHold = activeHold;
  if (priorHold) correctScrollHold(priorHold, panelIsOpen);
  activeHold = null;
  if (!panelIsOpen()) {
    threadsBox.style.removeProperty("overflow-anchor");
    return null;
  }
  const view = threadsBox.getBoundingClientRect();
  if (!view.width || !view.height) {
    threadsBox.style.removeProperty("overflow-anchor");
    return null;
  }
  const cards = [...threadsBox.querySelectorAll(".lf-thread")];
  const boxes = new Map(cards.map((card) => [card, card.getBoundingClientRect()]));
  const { x, y } = pointerAt();
  const overList =
    x >= view.left && x <= view.right && y >= view.top && y <= view.bottom;
  const underPointer = overList
    ? document.elementFromPoint(x, y)?.closest?.(".lf-thread")
    : null;
  const standing = focused()?.closest?.(".lf-thread");
  const visible = cards
    .filter((card) => {
      const box = boxes.get(card);
      return (
        card.checkVisibility() &&
        box.width &&
        box.height &&
        box.bottom > view.top &&
        box.top < view.bottom
      );
    })
    .sort((a, b) => boxes.get(a).top - boxes.get(b).top);
  // A fold is a mutation still running, and the hold that took it is the page's one
  // account of where the reader was standing when it started. The list slides both
  // ways around a folding card — the room closes under the cards below it and the
  // cards above come down into it — so the pointer stops naming that place as soon as
  // the motion begins: read again mid-fold it answers with whatever slid under it,
  // and a hold taken from that pins the wrong side of the movement while everything
  // past the fold, the successor the reader was aiming at among it, goes on moving.
  // A render arriving inside a fold therefore inherits the standing hold's own
  // reference, which has already handed off past the card that is leaving.
  const inherited = hasFolding()
    ? priorHold?.references.find(({ card }) => heldBox(card))?.card
    : null;
  const lead = inherited || underPointer || standing || visible[0];
  const leadAt = visible.indexOf(lead);
  const fallbacks =
    leadAt < 0
      ? visible
      : [...visible.slice(leadAt + 1), ...visible.slice(0, leadAt + 1)];
  const seen = new Set();
  const references = [inherited, underPointer, standing, ...fallbacks]
    .filter((card) => {
      if (!card || !threadsBox.contains(card) || seen.has(card)) return false;
      seen.add(card);
      return true;
    })
    .map((card) => ({
      card,
      contentTop: contentTop(card),
    }));
  if (!references.length) {
    threadsBox.style.removeProperty("overflow-anchor");
    return null;
  }
  activeHold = {
    references,
    scrollTop: threadsBox.scrollTop,
    maxScrollTop: maxScrollTop(),
  };
  // This hold is the sole scroll-anchor authority for its mutation. Leaving the
  // browser's independent anchor enabled can compensate the same reflow twice.
  threadsBox.style.setProperty("overflow-anchor", "none");
  return activeHold;
}

function releaseScrollHold(hold) {
  if (activeHold !== hold) return;
  activeHold = null;
  threadsBox.style.removeProperty("overflow-anchor");
}

function correctScrollHold(hold, panelIsOpen) {
  if (activeHold !== hold || !panelIsOpen()) return false;
  let box = null;
  const reference = hold.references.find(({ card }) => {
    box = heldBox(card);
    return box;
  });
  if (!reference) return false;
  // A card's viewport top moves both when content before it reflows and when the reader
  // scrolls. Adding scrollTop removes the second term, so this follows only reflow and
  // never fights a wheel, keyboard landing, narrowing reset, or scrollIntoView.
  const nextContentTop = box.top + threadsBox.scrollTop;
  const delta = nextContentTop - reference.contentTop;
  // Shrinking content can lower the scroll limit before this frame gets to correct
  // the hold. Chromium clamps the list to that new limit first; treating that forced
  // scroll as part of the reflow pays for it twice and moves the held card. Remove only
  // a clamp identified by both the falling limit and the list standing exactly on it.
  // Other scroll movement remains the reader's and is left intact.
  const limit = maxScrollTop();
  const clamped =
    limit < hold.maxScrollTop &&
    hold.scrollTop > limit &&
    threadsBox.scrollTop === limit
      ? threadsBox.scrollTop - hold.scrollTop
      : 0;
  if (delta || clamped) threadsBox.scrollTop += delta - clamped;
  // Every fallback observed this frame's reflow too. Refresh all live baselines after
  // the correction, or handing off later would apply movement already paid for while
  // the primary stood.
  for (const candidate of hold.references) {
    const candidateBox = heldBox(candidate.card);
    if (candidateBox) candidate.contentTop = candidateBox.top + threadsBox.scrollTop;
  }
  hold.scrollTop = threadsBox.scrollTop;
  hold.maxScrollTop = maxScrollTop();
  return true;
}

function followScrollHold(hold, panelIsOpen) {
  if (!correctScrollHold(hold, panelIsOpen)) {
    releaseScrollHold(hold);
    return;
  }
  if (hasFolding()) requestAnimationFrame(() => followScrollHold(hold, panelIsOpen));
  else releaseScrollHold(hold);
}

function finishScrollHold(hold, panelIsOpen) {
  if (!hold) return;
  correctScrollHold(hold, panelIsOpen);
  if (hasFolding()) requestAnimationFrame(() => followScrollHold(hold, panelIsOpen));
  else releaseScrollHold(hold);
}

export function holdScrollPosition(mutate, panelIsOpen) {
  const hold = takeScrollHold(panelIsOpen);
  try {
    return mutate();
  } finally {
    finishScrollHold(hold, panelIsOpen);
  }
}

// The DOM is the one record of what's rendered, reconciled against the log: nodes the
// list already holds are kept, and only what the log changed is added, moved, or
// dropped. The rebuild this replaced destroyed every node on every render and then
// hand-restored the reader's place — scroll offset, focused thread, caret — and what
// no restore could give back was identity: nothing could animate, one send route kept
// focus and the other dropped it, and a user's own comment landed below the fold
// of a list put back exactly where it was. Nodes surviving is what deleted all of it.
let renderGeneration = 0;

// A failed candidate may still leave one coherent list on screen. The list returns
// that recovery to the outer conversation paint, which promotes it to this proof only
// after every sibling surface has finished. Errors elsewhere remain pending.
export class RetainedThreadListError extends Error {
  constructor(reason, proof) {
    super(reason?.message ?? String(reason), { cause: reason });
    this.name = "RetainedThreadListError";
    this.proof = proof;
  }
}

export function retainedThreadListProof(reason) {
  if (!(reason instanceof RetainedThreadListError)) throw reason;
  return reason.proof;
}

const rowModel = (all, commands) => {
  // The conversations. A bare reaction is paint on the page and a chip on the page
  // row, and counts for nothing here: no card, no destination, no place in the walk.
  const threads = all.filter(conversational);
  const open = threads.filter((t) => !t.resolved);
  // The page's outline, read once for the whole reconcile: every thread asks it where it
  // stands and which run it belongs to.
  const outline = pageOutline();
  const group = threadGroups(threads, outline, commands.placedAt);
  // Newcomers settle in (`grow`) only when the user already has the list in front
  // of them: the first populated render is the page loading, not news arriving, and a
  // node animated while the panel is closed would replay the moment it opens.
  // (Reduced motion isn't asked here: grow is a CSS animation, and those are the
  // theme's one global guard's to stop.)
  const grow =
    commands.panelIsOpen() && Boolean(threadsBox.querySelector(":scope > .lf-thread"));

  // Where the reader's own narrowing applies, and the only place it does: the page's
  // marks, the inline conversation seats and the banner's count are readings of the log
  // and go on saying what the log says. What the panel shows is the panel's business.
  const ordered = inPageOrder(threads, commands.placedAt);
  const shown = ordered.filter((t) => inFilter(t, group.get(t)));
  const rows = [];
  if (!threads.length)
    rows.push(Object.freeze({ kind: "empty", key: "empty", text: emptyText }));
  else if (!shown.length)
    rows.push(Object.freeze({ kind: "empty", key: "no-match", text: noMatchText() }));
  // Walked in the page's order rather than the log's (inPageOrder), because that is the
  // order every other reading of these threads is in: the marks down the page and the walk
  // t/T makes. A thread on its way out still stands between its
  // neighbours while it folds (foldOut), which is why the walk is over the whole list
  // with the resolved ones taken at their own place. A folding thread is walked by nothing: the log
  // has already settled it, and only its room is still here.
  //
  // A heading goes in wherever the run changes, so the reader scrolling a list four
  // thousand pixels long is told which part of the page they are reading about — and,
  // the headings being sticky, is still told halfway down a long run.
  //
  // An open thread the narrowing hides keeps its node, hidden, rather than leaving the
  // list: a widget an agent sent in a reply is instantiated once, here, and every other
  // reading of it — the banner's Asks count, the tray's rows, the a/A walk — finds it by
  // id in the document. Pressing "Waiting on you" after answering a thread's question
  // took that thread's node out and, with it, the question from the page's count: 2/2
  // became 1/1 while the log said nothing had changed. Hidden is a fact about this list;
  // gone is a claim about the log. Resolved threads are ordinary filtered cards too.
  const visible = new Set(shown);
  for (const t of ordered) {
    rows.push(
      Object.freeze({
        kind: "thread",
        key: `thread:${threadKey(t)}`,
        thread: t,
        group: Object.freeze({ ...group.get(t) }),
        grow,
        visible: visible.has(t),
      }),
    );
  }
  for (const e of runtime.browser?.conversation?.done ?? [])
    rows.push(
      Object.freeze({
        kind: "system",
        key: `system:${e.id}`,
        id: e.id,
        text: `✓ Approved ${ago(e.ts)}`,
      }),
    );
  return {
    model: Object.freeze({ rows: Object.freeze(rows) }),
    groups: group,
    open,
    shown,
    threads,
  };
};

function materializeThread(row, commands) {
  const t = row.thread;
  // Under the default Open state, a newly resolved card gives its room back where it
  // stood before becoming a retained hidden card. Under the Resolved state it is an
  // ordinary visible result and changes directly to its resolved shape.
  const prior = t.resolved
    ? threadsBox.querySelector(
        `:scope > .lf-thread[data-id="${CSS.escape(t.root.id)}"]`,
      )
    : null;
  if (t.resolved && isFolding(t.root.id))
    return foldOut(t, commands.repaintConversation);
  if (
    t.resolved &&
    !row.visible &&
    prior &&
    !prior.hidden &&
    prior.dataset.resolved === "false"
  )
    return foldOut(t, commands.repaintConversation);
  return threadNode(t, row.grow, {
    reply: commands.card.reply,
    settlement: commands.card.settlement,
    reaction: commands.card.reaction,
    travel: commands.card.travel,
    anchors: commands.card.anchors,
    openThreads,
  });
}

function configureList(commands) {
  threadsBox.configure({
    activateGroup: (target) =>
      commands.scrollToElement(target, scrollBehavior(), "start"),
    materialize: (row) => materializeThread(row, commands),
    retire: (node) => retireConversationNode(node, commands.closeReactionMode),
  });
}

function postPaint({ groups, open, shown, threads }, commands) {
  paintHeadRoom(commands.panelIsOpen);
  commands.setThreadCount(open.length);
  paintNarrowing(threads, shown, groups);
  // The anchor pass wrote its record before this list existed, and this reconcile may have
  // built the nodes that wear it. Both passes therefore repaint it: the one that changes
  // the record, and the one that changes what the record is painted on.
  paintThreadQuotes({
    placedAt: commands.placedAt,
    isMarked: commands.isMarked,
  });
  commands.onListChanged();
  // Narrowing and reconciliation can move another card under a pointer that did not
  // move. Read :hover after the browser has laid out this list, in refreshHover's frame.
  commands.refreshAnchorHover();
}

async function prepareFrozenWidgets(current) {
  // Frozen markup has the same initial-value boundary as a page: connected and fully
  // presented, before its first projection. Later list reconciles retain the first
  // capture instead of adopting a reader's live value.
  const root = readApplication();
  const uncaptured = [...root.document.descriptors.values()]
    .filter(
      (descriptor) =>
        descriptor.document.kind === "thread" &&
        !root.document.authored.has(descriptor.id) &&
        threadsBox.querySelector(`#${CSS.escape(descriptor.id)}`),
    )
    .map((descriptor) => descriptor.id);
  await whenWidgetsPresented(uncaptured);
  if (!current()) return;
  captureAuthoredFacets(threadsBox);
  reachScrollers(threadsBox);
}

async function retainCommitted(current, candidate) {
  if (!current()) return;
  try {
    await threadsBox.retainCommitted(candidate);
  } catch (retaining) {
    throw new AggregateError(
      [retaining],
      "Thread list presentation and retention failed",
    );
  }
}

// A renderer exception can be transient (for example, a custom element upgrading in
// the same turn). Restore the committed list before one retry so a second render starts
// from a coherent tree. Only a retry that fully paints the candidate can prove the
// surrounding conversation reading; a second failure leaves the region pending.
async function presentList(model, current) {
  try {
    if (!(await threadsBox.present(model)) || !current()) return null;
    return { recovered: null };
  } catch (error) {
    if (!current()) return null;
    await retainCommitted(current, model);
    if (!current()) return null;
    try {
      if (!(await threadsBox.present(model)) || !current()) return null;
    } catch (retrying) {
      if (!current()) return null;
      await retainCommitted(current, model);
      throw new AggregateError(
        [error, retrying],
        "Thread list presentation retry failed",
      );
    }
    return { recovered: error };
  }
}

// The Lit update, its geometry-dependent paint, and newly connected frozen widgets are
// one proof for the existing conversation presentation ticket. Only the newest call can
// run post-paint work, capture authored values, or commit a fallback.
export async function renderThreads(all, commands) {
  const generation = ++renderGeneration;
  const current = () => generation === renderGeneration;
  const reading = rowModel(all, commands);
  configureList(commands);
  const hold = takeScrollHold(commands.panelIsOpen);
  let held = true;
  let recovered = null;
  try {
    const candidate = await presentList(reading.model, current);
    if (!candidate) return;
    recovered = candidate.recovered;
    postPaint(reading, commands);
    // The keyed list and its count/narrowing/quote readings are one committed candidate.
    // Frozen descendants remain inside the conversation ticket below, but their own
    // fail-soft settlement cannot roll this coherent parent reading back by itself.
    threadsBox.commit(reading.model);
    finishScrollHold(hold, commands.panelIsOpen);
    held = false;
    await prepareFrozenWidgets(current);
  } catch (error) {
    if (!current()) return;
    await retainCommitted(current, reading.model);
    throw error;
  } finally {
    if (held) finishScrollHold(hold, commands.panelIsOpen);
  }
  return { recovered, proof: threadsBox };
}

export async function renderThreadListUnavailable(text, commands) {
  const generation = ++renderGeneration;
  const current = () => generation === renderGeneration;
  configureList(commands);
  const model = Object.freeze({
    rows: Object.freeze([Object.freeze({ kind: "empty", key: "unavailable", text })]),
  });
  const hold = takeScrollHold(commands.panelIsOpen);
  let recovered = null;
  try {
    const candidate = await presentList(model, current);
    if (!candidate) return;
    recovered = candidate.recovered;
    paintHeadRoom(commands.panelIsOpen);
    threadsBox.commit(model);
  } catch (error) {
    await retainCommitted(current, model);
    throw error;
  } finally {
    finishScrollHold(hold, commands.panelIsOpen);
  }
  return { recovered, proof: threadsBox };
}
