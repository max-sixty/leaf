/* Retained comment-panel list reconciliation.

   Every change to this list's content holds the user's place through it: the renders
   `renderThreads` drives, receipt updates among them, and the disclosure the browser
   drives when a user opens a card and the named group closes the one that was open.
   The hold is `user-place.js`'s, keyed by each card's thread; this module decides only
   which changes take one. A resolution fold is followed frame by frame until it ends,
   and its completion removes its node through `renderThreads`, under the same hold.
   A new agent turn, or growth of the last one, follows while the user has not named
   another card and the previous last message is visible in the panel's landing band.
   Where the list scrolls, that thread's tail must still reach the landing edge.
   Following keeps a pinned reply box at the list's foot, and the turn's
   newest words end above it however tall the turn has grown.
   Reading earlier turns keeps the place hold, and a reply in another thread does not
   move this one.

   The list is threads alone, each title standing directly on the next: no heading
   names the page part a run of them is about. The order already says it, since the
   list reads in the page's (thread/placement.js), and each card's passage link says
   where its own thread stands.

   Reserved room only reaches a control that lands in it, and a press lands nowhere:
   the browser focuses the card under the pointer and scrolls nothing. So the thread
   list lands a thread that takes the focus, whoever moved it. Without it a list
   nudged a dozen pixels leaves a card cut at the list's edge by the width of an inset
   ring, which is a card with three sides. A press lands when it is over rather than as focus arrives,
   because focus arrives on the way down and the press may be the start of a drag
   across the comment's own words; a drag that ends in the thread takes no landing at
   all. What it lands is the thread the completed gesture leaves the user in, not the
   one the focus moved to, so a press on the thread they are already standing in —
   which moves no focus — brings it back like any other.

   This is an arrival rule and not a promise about the paint. Scrolling the list under
   a standing thread cuts its ring again, and nothing re-lands it: the user is moving
   away from what they were standing in, and a control under something is a fact about
   where it was put. A thread taller than the list's own scrollport is the excepted
   case in both directions — there is no scroll that shows all of it, which is the same
   thing the ring reading declines to report. Landing in a reply inside such a thread
   reveals its composer and actions together; an editor too tall to fit with its
   actions reveals the focused control itself.

   `test_no_focus_mark_the_panel_draws_on_a_walk_down_its_list_is_cut_or_covered` and
   `test_each_sampled_focus_ring_is_shown_whole_in_its_surface` hold this
   for the panel's own walk and for each surface a key opens. They ask one question: where the control can be seen, so can the ring
   that names it. A control that itself stands under a fixed bar is not a finding —
   that is a fact about where it was put — and neither is a box too tall for the region
   it is in. */
import { nextRender } from "../rendering.js";
import { placeKeeper } from "../user-place.js";
import { landingBand } from "../geometry.js";
import { retainUserIntent } from "../user-intent.js";
import { discussed, threadKey } from "./model.js";
import { ago } from "../presence.js";
import { readApplication, whenWidgetsPresented } from "../semantic-state.js";
import { reachScrollers } from "../reach.js";
import { hasFolding } from "./folding.js";
import { inPageOrder, inRecentOrder, pageOutline, threadSection } from "./placement.js";
import { threadSearchReading } from "./narrowing.js";
import { threadReading } from "./thread-card.js";

// A failed candidate can leave a coherent list on screen; the outer thread paint
// promotes the retained proof only after its sibling surfaces have finished.
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

// The open threads, in the order t/T walk either surface. The panel's children are the
// canonical list: folding a settled thread renames it out of this list in that frame.
// With the panel shut the walk is the page's, whichever order the panel was left in.
export function createThreadListController({ panel, threadsBox, narrowingView }) {
  const openThreads = ({
    visibleOnly = true,
    panelOpen = threadsBox.checkVisibility(),
  } = {}) => {
    const threads = [...threadsBox.querySelectorAll(":scope > .lf-thread")].filter(
      (thread) =>
        (!visibleOnly || !thread.hidden) &&
        (panelOpen || thread.dataset.resolved !== "true"),
    );
    return panelOpen ? threads : threadsBox.inPageOrder(threads);
  };

  const emptyText =
    "No threads yet. Select any text on the page to comment on it, or use the box below.";

  // Mounted once the chrome is (leaf.js): the list is the panel's.
  function mountThreadList(panelIsOpen) {
    holdThroughDisclosure(panelIsOpen);
  }

  // Opening a card is the third thing that reflows this list, beside the two renders, and
  // the only one the browser performs on its own: the named group closes the card that was
  // open, and every card after it — the title the user just pressed among them — comes up
  // by that card's open height. Native scroll anchoring answers this only when the node it
  // picked happens to be the pressed card or below it; picked above, it holds the room that
  // did not change and lets the pressed title travel, measured at 186px on an ordinary
  // panel and off the top of the scrollport from the first visible row. So disclosure takes
  // the same hold the renders take. `toggle` arrives with the reflow already in the
  // geometry, so the hold is taken on the way down, while the closed title's focus or click
  // has yet to reach the list that opens it (thread-list-view.js), and corrected on the
  // frame that paints it. A title already open changes nothing, and a hold there would
  // undo a landing's own scroll. Every route lands the right card: `takeScrollHold` leads
  // with the card under the pointer, and with the card holding focus when the hand is
  // elsewhere.
  function holdThroughDisclosure(panelIsOpen) {
    const hold = (event) => {
      const summary = event.target?.closest?.(".lf-thread-summary");
      const card = summary?.parentElement;
      if (!card?.matches?.(".lf-thread") || card.open) return;
      if (event.type === "focusin" && summary.matches(":active")) return;
      const taken = takeScrollHold(panelIsOpen);
      if (taken) nextRender(() => finishScrollHold(taken, panelIsOpen));
    };
    for (const type of ["focusin", "click"])
      threadsBox.addEventListener(type, hold, true);
  }

  // The list's place through every change to its content (user-place.js). A card is
  // rendered under its thread's root id, so a card the render rebuilt hands the place to
  // its successor node, and a folding card, renamed out of `.lf-thread`, hands it to the
  // next card still standing.
  let place = null;
  const listPlace = (panelIsOpen) =>
    (place ??= placeKeeper(threadsBox, {
      items: ".lf-thread",
      identity: (card) => card.dataset.id,
      active: panelIsOpen,
    }));
  const takeScrollHold = (panelIsOpen) => listPlace(panelIsOpen).take();
  const finishScrollHold = (hold, panelIsOpen) =>
    listPlace(panelIsOpen).finish(hold, () => hasFolding(threadsBox));

  // The list's place hold reports what the user named. Follow while they have not
  // named another thread and this thread's tail meets the landing edge.
  const FOLLOW_ROOM = 80;
  function incomingAtLatest(reading, panelIsOpen, namedCard) {
    if (!panelIsOpen()) return null;
    const card = threadsBox.querySelector(":scope > .lf-thread[open]:not([hidden])");
    if (namedCard && namedCard !== card) return null;
    const prior = threadsBox.committed.rows.find(
      (row) => row.kind === "thread" && row.descriptor.id === card?.dataset.id,
    )?.descriptor;
    const next = reading.rows.find(
      (row) => row.kind === "thread" && row.descriptor.id === card?.dataset.id,
    )?.descriptor;
    if (!prior || !next) return null;
    const known = new Set(prior.messages.map((message) => message.key));
    const incoming = next.messages.filter(
      (message) => message.author === "agent" && !known.has(message.key),
    );
    const latest = prior.messages.at(-1);
    const nextLatest = next.messages.at(-1);
    const grown =
      latest?.key === nextLatest?.key &&
      nextLatest?.author === "agent" &&
      latest.body.text !== nextLatest.body.text;
    if (!incoming.length && !grown) return null;
    const node =
      latest &&
      card.querySelector(
        latest.attempt
          ? `.lf-msg[data-attempt="${CSS.escape(latest.attempt)}"]`
          : `.lf-msg[data-mid="${CSS.escape(latest.id)}"]`,
      );
    const band = landingBand(threadsBox);
    if (!node || !band) return null;
    const tailStart = node.getBoundingClientRect().bottom;
    const tailEnd = card.getBoundingClientRect().bottom;
    const scrolls = threadsBox.scrollHeight > threadsBox.clientHeight;
    if (
      tailStart < band.top ||
      tailStart > band.bottom + FOLLOW_ROOM ||
      (scrolls && tailEnd < band.bottom - FOLLOW_ROOM)
    )
      return null;
    return {
      id: incoming.at(-1)?.id ?? nextLatest.id,
      top: threadsBox.scrollTop,
      end: tailEnd,
      box: card.querySelector(":scope > .lf-thread-reply")?.getBoundingClientRect().top,
      current: retainUserIntent({ available: panelIsOpen }),
    };
  }

  // One immutable presentation reading contains the rows, count, and narrowing paint.
  // The list checkpoints it only when the whole thread batch commits; retention
  // restores that reading through the same owners while preserving native identities.
  let renderGeneration = 0;

  // Following grows the thread up into the room scrolled past: the card's end stays where
  // it stood, so nothing after it moves, and the newest words end above the reply box,
  // however tall the turn has grown. The box stands at the list's foot (chrome.css), pinned
  // there while the card's end lies below it, so the words may reach past where it stood
  // by more than the card grew. The scroll lands in the render's own frame. A short card has no
  // scroll room to absorb news; HeldNews keeps it behind the existing notice instead.
  function followThreadEnd(newest, incoming) {
    const card = newest.closest(".lf-thread");
    const by = Math.max(
      card.getBoundingClientRect().bottom - incoming.end,
      newest.getBoundingClientRect().bottom - (incoming.box ?? Infinity),
    );
    if (by > 0) threadsBox.scrollBy({ top: by, behavior: "instant" });
  }

  const rowModel = (all, commands) => {
    // The threads. A bare reaction is paint on the page and a chip on the page
    // row, and counts for nothing here: no card, no destination, no place in the walk.
    const threads = all.filter(discussed);
    const open = threads.filter((t) => !t.resolved);
    // The page's outline, read once for the whole reconcile: every thread asks it which
    // part of the page it stands in, which the narrowing's search and Placement read.
    const outline = pageOutline();
    const places = new Map(
      threads.map((t) => [t, threadSection(t, outline, commands.placedAt)]),
    );
    // Newcomers settle in (`grow`) only when the user already has the list in front
    // of them: the first populated render is the page loading, not news arriving, and a
    // node animated while the panel is closed would replay the moment it opens.
    // (Reduced motion isn't asked here: grow is a CSS animation, and those are the
    // theme's one global guard's to stop.)
    const grow =
      commands.panelIsOpen() &&
      Boolean(threadsBox.querySelector(":scope > .lf-thread"));

    // Where the user's own narrowing applies, and the only place it does: the page's
    // marks, the inline thread seats and the banner's count are readings of the log
    // and go on saying what the log says. What the panel shows is the panel's business,
    // and so is the order it shows it in. The page's order is kept either way for the
    // walk with the panel shut.
    const narrowing = commands.narrowing.model(threads, places);
    const kept = new Map(
      threads
        .filter((thread) => !narrowing.shown.includes(thread))
        .map((thread) => [thread, threadsBox.keeping(thread, narrowing.intent)])
        .filter(([, why]) => why),
    );
    const shown = threads.filter(
      (thread) => narrowing.shown.includes(thread) || kept.has(thread),
    );
    const inPage = inPageOrder(threads, commands.placedAt);
    const recent = narrowing.intent.order === "recent";
    const ordered = recent ? inRecentOrder(threads) : inPage;
    const rows = [];
    if (!threads.length)
      rows.push(Object.freeze({ kind: "empty", key: "empty", text: emptyText }));
    else if (!shown.length)
      rows.push(
        Object.freeze({ kind: "empty", key: "no-match", text: narrowing.emptyText }),
      );
    // Walked in the order the user chose above. A thread on its way out still stands
    // between its neighbours while it folds (foldOut), which is why the walk is over the
    // whole list with the resolved ones taken at their own place. A folding thread is
    // walked by nothing: the log has already settled it, and only its room is still here.
    //
    // An open thread the narrowing hides keeps its node, hidden, rather than leaving the
    // list: a widget an agent sent in a reply is instantiated once, here, and every other
    // reading of it — the banner's Asks count, the drawer's rows, the a/A walk — finds it by
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
          descriptor: threadReading(t, "panel", commands.card, {
            visible: visible.has(t),
            kept: kept.get(t) ?? null,
            grow,
            search: threadSearchReading(t, narrowing.intent.finding),
          }),
        }),
      );
    }
    for (const e of readApplication().effective.acceptedApprovals)
      rows.push(
        Object.freeze({
          kind: "system",
          key: `system:${e.id}`,
          id: e.id,
          text: `✓ Approved ${ago(e.ts)}`,
        }),
      );
    return Object.freeze({
      rows: Object.freeze(rows),
      intent: narrowing.intent,
      count: open.length,
      unread: threads.filter((t) => t.unread.length).length,
      narrowing: narrowing.presentation,
      pageSeats: new Map(inPage.map((t, i) => [t.id, i])),
    });
  };

  function configureList(commands) {
    threadsBox.configure(
      {
        card: {
          ...commands.card,
          openThreads,
          listRoot: threadsBox,
          repaintThread: commands.repaintThread,
        },
        repaintThread: commands.repaintThread,
        presentSummary: (model) => postPaint(model, commands),
      },
      Object.freeze({
        rows: Object.freeze([]),
        count: null,
        unread: 0,
        narrowing: commands.narrowing.model([], new Map()).presentation,
        pageSeats: new Map(),
      }),
    );
  }

  function postPaint({ count, unread, narrowing }, commands) {
    commands.setThreadCounts(count, unread);
    narrowingView.present(narrowing);
    commands.onListChanged();
    // Narrowing and reconciliation can move another card under a pointer that did not
    // move. Read :hover after the browser has laid out this list, in refreshHover's frame.
    commands.refreshAnchorHover?.();
  }

  async function prepareFrozenWidgets(current) {
    const widgets = [...readApplication().document.descriptors.values()]
      .filter(
        (descriptor) =>
          descriptor.document.kind === "thread" &&
          threadsBox.querySelector(`#${CSS.escape(descriptor.id)}`),
      )
      .map((descriptor) => descriptor.id);
    await whenWidgetsPresented(widgets);
    if (current()) reachScrollers(threadsBox);
  }

  async function retainCommitted(current, candidate, reason) {
    if (!current()) return;
    try {
      await threadsBox.retainCommitted(candidate);
    } catch (retaining) {
      throw new AggregateError(
        [reason, retaining],
        "Thread list presentation and retention failed",
      );
    }
  }

  // A renderer exception can be transient (for example, a custom element upgrading in
  // the same turn). Restore the committed list before one retry so a second render starts
  // from a coherent tree. Only a retry that fully paints the candidate can prove the
  // surrounding thread reading; a second failure leaves the region pending.
  async function presentList(model, current) {
    try {
      if (!(await threadsBox.present(model)) || !current()) return null;
      return { recovered: null };
    } catch (error) {
      if (!current()) return null;
      await retainCommitted(current, model, error);
      if (!current()) return null;
      try {
        if (!(await threadsBox.present(model)) || !current()) return null;
      } catch (retrying) {
        if (!current()) return null;
        const failure = new AggregateError(
          [error, retrying],
          "Thread list presentation retry failed",
        );
        await retainCommitted(current, model, failure);
        throw failure;
      }
      return { recovered: error };
    }
  }

  // The Lit update, its geometry-dependent paint, and newly connected frozen widgets are
  // one proof for the existing thread presentation ticket. Only the newest call can
  // run post-paint work, capture authored values, or commit a fallback.
  async function renderThreads(collection, commands) {
    const all = collection.threads;
    const generation = ++renderGeneration;
    const current = () => generation === renderGeneration;
    let reading = rowModel(all, commands);
    configureList(commands);
    const hold = takeScrollHold(commands.panelIsOpen);
    const incoming = incomingAtLatest(reading, commands.panelIsOpen, hold?.named);
    let held = true;
    let recovered = null;
    try {
      const candidate = await presentList(reading, current);
      if (!candidate) return;
      recovered = candidate.recovered;
      // Newly connected frozen markup can supply the words a different thread's
      // quote names. Re-derive that batch reading through the same descriptor owner.
      const connected = rowModel(all, commands);
      const changedQuotes = connected.rows.some((row, index) => {
        if (row.kind !== "thread") return false;
        const prior = reading.rows[index];
        return (
          prior?.key !== row.key ||
          JSON.stringify(prior.descriptor.quote) !==
            JSON.stringify(row.descriptor.quote)
        );
      });
      if (changedQuotes) {
        reading = connected;
        const refreshed = await presentList(reading, current);
        if (!refreshed) return;
        recovered ??= refreshed.recovered;
      }
      // The surrounding thread batch commits this complete list with its sibling
      // seats. Frozen descendants already entered the application as authored source;
      // wait only for their connected presentation proof inside this same ticket.
      finishScrollHold(hold, commands.panelIsOpen);
      held = false;
      await prepareFrozenWidgets(current);
      const newest =
        current() && incoming?.current() && threadsBox.scrollTop >= incoming.top - 2
          ? threadsBox.querySelector(`.lf-msg[data-mid="${CSS.escape(incoming.id)}"]`)
          : null;
      if (newest) followThreadEnd(newest, incoming);
    } catch (error) {
      if (!current()) return;
      await retainCommitted(current, reading, error);
      throw error;
    } finally {
      if (held) finishScrollHold(hold, commands.panelIsOpen);
    }
    return {
      recovered,
      proof: threadsBox,
      commit: () => threadsBox.commit(reading),
    };
  }

  async function renderThreadListUnavailable(text, commands) {
    const generation = ++renderGeneration;
    const current = () => generation === renderGeneration;
    configureList(commands);
    const model = Object.freeze({
      rows: Object.freeze([Object.freeze({ kind: "empty", key: "unavailable", text })]),
      count: null,
      narrowing: commands.narrowing.model([], new Map()).presentation,
      pageSeats: new Map(),
    });
    const hold = takeScrollHold(commands.panelIsOpen);
    let recovered = null;
    try {
      const candidate = await presentList(model, current);
      if (!candidate) return;
      recovered = candidate.recovered;
    } catch (error) {
      await retainCommitted(current, model, error);
      throw error;
    } finally {
      finishScrollHold(hold, commands.panelIsOpen);
    }
    return { recovered, proof: threadsBox, commit: () => threadsBox.commit(model) };
  }

  const cancel = () => {
    ++renderGeneration;
  };

  async function restoreThreadList() {
    cancel();
    await threadsBox.retainCommitted(threadsBox.model);
  }

  return {
    openThreads,
    mountThreadList,
    renderThreads,
    renderThreadListUnavailable,
    restoreThreadList,
    cancel,
  };
}
