/* The ask view: where the reader is standing, the ring that says so, the Asks tray's
   rows, and the walks and arrivals that move between asks.

   Focus is the reader's current place. `focused` follows it through declared shadow
   roots. A native label activation may pass through `body` or a focusable container
   between the pointer press and the control's focus; Leaf treats that interval as one
   logical standing without changing DOM focus or preventing label text selection.
   `documentFocused` retargets the logical standing to its document host. Painted focus
   readings use one of those two functions; CSS reads the matching `.lf-focus`,
   `.lf-focus-visible`, and `.lf-focus-within` projections. A key ends the pointer
   interval and restores physical focus before dispatch. Code that acts on physical focus
   otherwise reads `document.activeElement` directly. `markHere` paints one `--here-ring`
   around the semantic ask or control that contains focus. The ring is derived on
   each paint; it does not store the ask walk's position.

   The ring is therefore paintable on an ask the `a`/`A` ask walk will not step to.
   The tray does list it: the walk is a worklist, while the tray is the complete route
   through the active Ask inventory. The Escape rung still reads focus rather than either
   list, so the way out is the one it always has.

   Working an ask and standing in one are different facts, and `markHere`'s ring
   answers the second. A reader who tabbed to a link inside a question has named something
   more particular than the question, so a press there means the link's own block; reading
   the ring instead overrode what they named, and made the same markup answer differently
   according to whether its question was still open. The two agree wherever the reader is
   working the ask, which is every arrival the ask walk makes.

   `standingConversation` (conversation/landing.js) is the exception, and covers all three
   containers that hold a conversation the reader can stand in: the panel's thread, a
   conversation seated on the page, and each thread inside that seat. It asks for the box
   rather than for the container's class, because a resolved thread is built by the same
   function and wears the same class while having no box to reach, and a collapsed one
   answers the same honest way.

   `landed` stores where the ask walk last arrived. This is distinct from focus:
   clicking elsewhere removes the focus-derived ring without erasing either the walk's
   useful continuation point or the answer progress in the banner.

   `shownParts` supplies ring targets when a page styles an ask with `display:
   contents`. A normal boxed ask wears one outline on its own box. Hoisted controls
   use the same ring token through the shared chip rule.

   Ask rows come from every active local `x-awaits` source and holder declaring
   `x-request.ask`, answered or open, not from a list of ask tags. Where a
   source is nested in an `x-ask-surface` region, the row names the region: its heading,
   context, and evidence are the ask the reader is being sent to, while the source
   remains the owner of the answer. `addressableSays` supplies each row's own label and the owned
   command scope's `options.answer` supplies its current answer. Selecting a tray row
   travels through the same ask-arrival function as `a` and `A`, so the panel and
   directional walk agree about focus, reveal, arrival placement, and `landed`; only the
   tray's list is wider, preserving answered routes for review and revision.

   An arrival stands the reader on the ask, which is the element the scroll has just
   aligned and the one the ring names. The widget's contributed actions are addressable
   there by their declared bindings, with `1`–`9` as the default; its controls remain the
   next Tab stops, a stop at `tabindex: -1` keeping its place in document order. Landing
   the answering control instead puts them as far down the ask as its context and
   evidence are long, off the screen the same gesture arranged. An Ask a page styles
   boxless has nothing to stand on and keeps the control as its landing. A widget rebuilt
   under a reader is not an arrival and hands back the control they were working
   (`standOn`).

   A directional page walk starts from the reader's place, in this order:

   1. current focus;
   2. selection or caret;
   3. the walk's last `landed` item;
   4. the current reading block and scroll position.

   The chrome is a binding badge, not a page position, so its controls do not become the walk's
   origin. `askStep` compares document positions rather than incrementing an index
   remembered by the walk. A panel thread walk may use log order because the list itself
   is its complete ordered space.

   Arriving at a page ask puts its arrival region's start below the banner, not the
   ask's own top edge. A widget declaring `x-ask-surface` states that region and the
   walk is handed the region rather than the source inside it. Nothing else declares one,
   and an edit to a phrase cannot: what explains it is the sentence it stands in and the
   heading over that. `arrivalRegion` reads that region off the document instead. Its
   candidates are the blocks before the ask whose own parent still contains it — so a
   block wrapped in something the ask stands outside of, another ask or a section of
   its own, is not this ask's context — and of those it takes the last heading, then
   the text block holding the ask or, for a change that is its own block, the nearest
   remaining block before it. The first candidate whose start still leaves the ask's
   foot on screen wins, falling back to the ask itself. That bound is what lets the
   widest candidate go first, and it keeps the region inside one screen without a rule
   about distance. A candidate that paints no box is not a place to arrive at: an element
   generating none measures at the document's origin, which would read as a region at the
   top of the page.

   The sweep is the document's own blocks in document order, so an ask staged inside a
   declared shadow tree takes a heading standing over its host but not one inside that
   tree. The travel moves the page's scroller, so the ask's own box is brought into
   view first for the sake of an ask inside a nested scroller, which that placement
   would never reach. An Ask whose region already stands clear of the banner, and
   which `readableDestination` reads as unclipped on every edge, is not travelled to at
   all: the press moves the ring and the focus and leaves the page still. A thread
   ask keeps its centred arrival in the panel's own list. */

import { shownBox, shownParts } from "../geometry.js";
import { askProgressModel, createAskBannerControls } from "./banner-controls.js";
import { keyBadgePlacement } from "../keyboard/key-badge-placement.js";
import {
  ariaShortcuts,
  bindings,
  contextualRoute,
  decisionControls,
  routedCommand,
  spell,
} from "../keyboard/bindings.js";
import {
  closestAcross,
  containsAcross,
  elementById,
  elementFromPointAcross,
  inChrome,
  TEXT_BLOCK,
} from "../passages.js";
import { scrollerFor } from "../reading-regions.js";
import { el, reserve, reveal } from "../widget-elements.js";
import { asksBtn, asksList, asksOffered, asksPanel, trayIsOpen } from "../trays.js";
import { registry, tagsDeclaring } from "../registry.js";
import {
  allAsks as readAllAsks,
  askEntry,
  askSource,
  openAsks as readOpenAsks,
  unansweredAsks as readUnansweredAsks,
} from "./model.js";
import { beginWalk, listWalkPosition, walkPositionLabel } from "../walk-position.js";
import {
  commandScopesWithin,
  commandsWithin,
  documentFocused,
  focused,
  paintKeys,
} from "../keyboard/scopes.js";
import { addressableSays, addressableWord } from "../anchor-resolution.js";
import { PAGE_PAINT_ATTRIBUTE } from "../presentation.js";
import { scrollBehavior } from "../motion.js";
import { ASK_CONTROL, askActionLayer } from "./view-elements.js";
import { ASK_AT } from "./tray-list.js";
import { availableCommandRoutes } from "../keyboard/dispatch.js";
import { PRESENTATION } from "../presentation.js";
import {
  attachApplicationPresentation,
  failSoftAfterRetention,
  PresentationRetentionError,
  readApplication,
  watchSemantic,
} from "../semantic-state.js";

// Contextual actions for the Ask the reader is standing in. These share the binding-badge face
// but not the g sequence's lifecycle: the ask view paints them whenever its semantic
// focus and the dispatch stack leave the contributed action row reachable.
export function createAskView({
  panelIsOpen,
  pendingRequests,
  setPanel,
  setOpenTray,
  trayCovers,
  readableDestination,
  scrollToElement,
  refreshConversation,
  focusForNavigation,
  presentedControl,
  readingBlock,
  placeBulkAnswer,
  announce,
  repaint,
}) {
  const allAsks = readAllAsks;
  const openAsks = () => readOpenAsks(pendingRequests());
  const unansweredAsks = () => readUnansweredAsks(pendingRequests());
  const presentedActionControl = (control) => presentedControl(control) ?? control;
  const answeringAll = new Set();
  const bulkAnswers = new Map();
  const bannerControls = createAskBannerControls(asksBtn, async (verb) => {
    if (answeringAll.has(verb)) return;
    answeringAll.add(verb);
    void syncAsks();
    try {
      // Resolve the current open inventory at activation. A control can survive several
      // publications and shelf moves; it never captures an earlier Ask or DOM node.
      for (const ask of openAsks()) {
        const source = askSource(ask);
        if (askEntry(source)?.all === verb) await source[verb]?.();
      }
    } finally {
      answeringAll.delete(verb);
      void syncAsks();
    }
  });
  asksList.configure({
    activate: (id) => {
      const route = allAsks();
      const to = route.find((candidate) => candidate.id === id);
      if (to) goToAsk(to, route);
    },
    fallback: asksBtn,
  });
  const asksRenderer = Object.freeze({ banner: bannerControls, list: asksList });
  let asksPresentation = null;
  const presentation = () => {
    asksPresentation ??= attachApplicationPresentation("asks", asksRenderer);
    return asksPresentation;
  };

  // One blanket answer per verb a widget declares one for (x-awaits.all), each deciding
  // its asks one at a time so the log records what was consented to rather than one
  // blanket yes — accepting the rest after rejecting one stays honest. The widget
  // exposes a method named for the verb; the label is built from the same word.
  //
  // Built when the registry lands rather than written out above, so the second widget to
  // declare one gets its control by declaring it. Each takes its place in the row rather
  // than a box of its own: a control with no siblings is a control the press sweep walks
  // past, and one that only ever appears at upgrade spends the spacer's slack, not the
  // room of anything to its right.
  function buildBulkAnswers() {
    for (const tag of tagsDeclaring((entry) => entry["x-awaits"]?.all)) {
      const verb = registry[tag]["x-awaits"].all;
      if (bulkAnswers.has(verb)) continue;
      const label = verb[0].toUpperCase() + verb.slice(1);
      const btn = bannerControls.registerBulk(verb, label);
      bulkAnswers.set(verb, label);
      placeBulkAnswer(btn);
      // In the row now, so it holds the widest it reaches below a thousand — the same
      // words syncAsks writes, measured in the face it will render in (see reserve).
      reserve(btn, [`${label} all (999)`]);
    }
  }

  // Each blanket answer with the asks it would take, from the list above. The banner
  // writes its controls and counts from this one reading, without naming a verb in core;
  // which verbs exist is the registry's answer.
  function blanketAnswers(asks) {
    return [...bulkAnswers].map(([verb, label]) => {
      const n = asks.filter((ask) => askEntry(askSource(ask))?.all === verb).length;
      return Object.freeze({
        busy: answeringAll.has(verb),
        offered: Boolean(n),
        text: `${label} all (${n})`,
        title: `${label} every one still waiting on you`,
        verb,
      });
    });
  }
  // The banner's reading of that one list. Refreshed from every signal that can change
  // it: a widget saying it has just taken an answer (lf-answered, which is also when the
  // page's own words change), and every semantic publication, which is where the fold
  // moves and where a send that failed has its optimism taken back.
  let shortcutsOffered = false;
  let rowWalkOffered = false;
  const ANSWER_CAP = 120;
  const answerWords = (value) => {
    const whole = String(value ?? "")
      .replace(/\s+/g, " ")
      .trim();
    if ([...whole].length <= ANSWER_CAP) return whole;
    const short = [...whole].slice(0, ANSWER_CAP).join("");
    const at = short.lastIndexOf(" ");
    return (at > ANSWER_CAP / 2 ? short.slice(0, at) : short).trimEnd() + "…";
  };
  function currentAskAnswer(ask) {
    const source = askSource(ask);
    const readers = commandScopesWithin(source)
      .filter(
        ({ source: commandSource, answer }) =>
          answer && ownedAskControl(source, commandSource),
      )
      .map(({ answer }) => answer);
    if (readers.length > 1)
      throw new TypeError(`Ask ${ask.id} has more than one answer reader`);
    return answerWords(readers[0]?.());
  }
  const rowModel = (ask, unanswered) => {
    const kind = addressableWord(ask);
    const says = addressableSays(ask) || ask.id;
    const answered = !unanswered.has(ask);
    const answer = answered ? currentAskAnswer(ask) : "";
    return Object.freeze({
      id: ask.id,
      kind,
      says,
      answer,
      answerState: answered ? "answered" : "open",
      title: `${kind} · ${says}${answer ? ` · ${answer}` : ""}`,
    });
  };

  let askPaintGeneration = 0;
  async function paintAsks(generation) {
    const current = () => generation === askPaintGeneration;
    const asks = openAsks();
    const all = allAsks();
    const unanswered = new Set(unansweredAsks());
    const completed = all.filter((ask) => !unanswered.has(ask)).length;
    const offered = asksOffered();
    // Only while the tray is up: the count above is what a closed tray says, and these
    // rows are what an open one says. The list owner receives an explicit closed model
    // so no hidden generated controls remain in the document.
    const open = trayIsOpen("asks");
    const listModel = Object.freeze({
      open,
      rows: Object.freeze(open ? all.map((ask) => rowModel(ask, unanswered)) : []),
    });
    const bannerModel = Object.freeze({
      progress: askProgressModel(completed, all.length, offered),
      bulk: Object.freeze(blanketAnswers(asks)),
    });
    // The a/A row stands on this list, so the surfaces reading it are repainted
    // where it changes — the rule showFab and setOpenTray already keep for the words
    // they write. A capability change also moves the tray edge's machine-readable keys.
    const walkOffered = asks.length > 0;
    if (offered !== shortcutsOffered || walkOffered !== rowWalkOffered) {
      shortcutsOffered = offered;
      rowWalkOffered = walkOffered;
      paintKeys();
    } else repaint();
    try {
      // The controls are stable nodes and can be restored without losing identity. Paint
      // them first, then the keyed list: a failed face never lets a row be removed, and a
      // failed list can roll the controls back before either owner commits this reading.
      const bannerPaint = await bannerControls.present(bannerModel);
      if (!current()) return [];
      const listPaint = await asksList.present(listModel);
      if (!current()) return [];
      asksList.commit();
      bannerControls.commit();
      return [listPaint, bannerPaint];
    } catch (error) {
      // A current paint owns the same faces now. It will either commit or restore them;
      // an obsolete attempt must not roll its predecessor over the newer reading.
      if (!current()) return [];
      try {
        await Promise.all([
          asksList.retainCommitted(),
          bannerControls.retainCommitted(),
        ]);
      } catch (retaining) {
        throw new PresentationRetentionError(
          [error, retaining],
          "Ask presentation and retention failed",
        );
      }
      throw error;
    }
  }
  // Every semantic notification opens the region's ticket synchronously, before its
  // deferred read. Package subscribers therefore finish their own synchronous updates
  // first, while the application barrier already knows this inherited Ask paint is stale.
  // A newer signal replaces and releases the obsolete completion before either paint.
  let scheduled = null;
  function syncAsks() {
    let resolve;
    let reject;
    const completion = new Promise((done, fail) => {
      resolve = done;
      reject = fail;
    });
    const pending = { generation: ++askPaintGeneration, resolve, reject };
    const prior = scheduled;
    scheduled = pending;
    const ready = presentation().present(
      readApplication().semanticEpoch,
      completion,
      failSoftAfterRetention(asksRenderer),
    );
    prior?.resolve();
    queueMicrotask(() => {
      if (scheduled !== pending) return;
      scheduled = null;
      try {
        Promise.resolve(paintAsks(pending.generation)).then(resolve, reject);
      } catch (error) {
        reject(error);
      }
    });
    return ready;
  }
  const renderAsks = syncAsks;

  // The walk over what the page is waiting on the reader for. It wraps at both ends,
  // because asks are a worklist rather than a document to read through: answering one takes
  // it out of the list, so forward is the direction that has somewhere to go, and a walk
  // that clamped there would strand them at the end of it.
  //
  // Somewhere inside the ask the reader can be stood: one within it, or one hoisted out of
  // it and pointing back (a suggestion's row is the column's child, so that it can hang in
  // the page margin). Landing on it rather than on the ask puts the reader on something
  // that works it, and Tab walks the rest of that ask's own controls from there.
  //
  // Which ask such a control decides, where the widget hoisted it out of the element (the
  // attribute lf-suggestion writes on the row it hangs in the margin).
  const ASK_ROW = "data-lf-for";
  // Chrome that stands *at* an ask without deciding it: the asks tray's rows. Separate
  // from ASK_ROW above, because the two say different things about the same element and
  // one of them has a consumer that must not confuse them — stepAsk looks through ASK_ROW
  // for the control to put the reader on, and a row that merely points at the ask is not
  // that control. What they share is this: focus on either means the reader is standing at
  // that ask, which is the one question askPlace asks.
  // Where a stand-in stands: the ask decided by the control it re-presents. Separate from
  // ASK_ROW again, and for a sharper reason than ASK_AT's — ASK_ROW names one element per
  // ask, the row lf-suggestion hangs in the margin, and the runtime, the theme and the
  // suite all read `[data-lf-for="<id>"]` as that row. A proxy wearing it would be a second
  // answer to every selector meaning "the row for this change". What a stand-in needs is
  // only the reading below: focus on it means the reader is standing at the ask its press
  // decides.
  const ASK_STANDS = "data-lf-stands";
  // The tab stop this walk lends an ask that holds nothing to work: such an ask has no box
  // in the tab order and the runtime writes it one — which is paint on the author's element,
  // and PAGE_PAINT_ATTRIBUTES is the whole of what the runtime may leave standing there (a
  // `tabindex` in it would blind the replay signature to an authored one). So the lend lasts
  // exactly as long as the ring it goes with: the walk hands the stop over as it moves, and
  // markHere takes it back when the reader leaves.
  //
  // One function for both ends of it, because written as statements at each end the walk's
  // half only ever wrote — it took the last lend's reference with it and left the stop
  // standing. Two control-less asks in a row is all it took, and the walk in the shipped
  // examples goes through two: stepping off a task left it wearing a tab stop that nothing
  // afterwards was ever going to remove.
  let askLent = null;
  function lend(ask) {
    if (askLent === ask) return;
    askLent?.removeAttribute("tabindex");
    askLent = ask;
    if (ask) ask.tabIndex = -1;
  }
  // Where the walk last left off. Not the same question as where the reader is standing,
  // though one answer used to serve both: the ring said where they were and the walk read
  // its own last landing off it. A reader who has pressed the banner's Asks button is
  // standing in the banner, and the ring is rightly gone from the page — leaving the walk
  // with nothing to step from but whatever happens to be on screen, which would send the
  // next press back up the page.
  let landed = null;
  // An answered Ask normally keeps semantic focus on its own element after a tray-row
  // arrival. A boxless answered widget cannot: its visible revision control is the only
  // focus target. Remember that exact target for this arrival, and only while it still
  // owns focus, so returning to the same control ordinarily does not promote it from its
  // own local meaning to the whole Ask again.
  let reviewedThrough = null;
  function hasReviewedFocus() {
    if (reviewedThrough?.isConnected && focused() === reviewedThrough) return true;
    reviewedThrough = null;
    return false;
  }
  // The ask a node points back at, as the id it names, or null where it points at none.
  const standsAt = (node) => {
    const el = node.nodeType === 1 ? node : node.parentElement;
    const row = el?.closest(`[${ASK_ROW}], [${ASK_AT}], [${ASK_STANDS}]`);
    return (
      row?.getAttribute(ASK_ROW) ??
      row?.getAttribute(ASK_AT) ??
      row?.getAttribute(ASK_STANDS) ??
      null
    );
  };
  // What a surface re-presenting a control has to say about it: the control's own
  // attribution, so a stand-in stands where the control it forwards to stands. The living
  // margin builds one when a hoisted control spills into a More options group, and the
  // press it forwards decides the same ask. Saying nothing left the proxy standing nowhere:
  // the ring came off the suggestion for as long as the reader held its own ✗ Reject, and
  // the walk measured its next step from the margin rather than from the change.
  //
  // Said in ASK_STANDS rather than in the row's own attribute, because the stand-in is a
  // second element for the one ask: the row keeps sole answer to `[data-lf-for="<id>"]`,
  // and standsAt above reads the two together.
  //
  // Written only where it changes, like every other repaint of a standing surface: a
  // heartbeat that re-presents the same control restates nothing.
  function standsWith(node, source) {
    const at = (source && standsAt(source)) ?? null;
    if (node.getAttribute(ASK_STANDS) === at) return;
    if (at) node.setAttribute(ASK_STANDS, at);
    else node.removeAttribute(ASK_STANDS);
  }
  // A place in the document, stated as the ask it belongs to wherever it belongs to one: a
  // control hoisted out of its ask and pointing back at it stands for that ask and not for
  // the block it was hung beside, or stepping back from a suggestion's own ✓ Accept would
  // land on the suggestion the reader is already standing on.
  function askPlace(node) {
    const at = standsAt(node);
    return (at && elementById(at)) ?? node;
  }
  // The ask the reader is standing in: the one holding the focus, or the one a control
  // hoisted into the margin decides. The innermost of them, an ask being able to hold
  // another (a question inside a suggestion's lf-new) — the list answers in document order,
  // so the last container in the list is the nearest one.
  //
  // The unanswered asks rather than the reader's list, because standing in a question is
  // about where the reader is working and not about what they owe. The two part on a widget
  // whose own seat is mid-conversation with the agent: it leaves the list while its pick
  // stays unmade and its controls stay live, and reading the list took the ring off that
  // widget and moved `c` from the seat the reader was writing in down to whichever option
  // their focus rested on — a second thread on the child rather than the next line of their
  // own. The agent's reply put both back. Nothing the reader did moved either. An
  // answered ask leaves both worklists but stays in the active inventory: the
  // Asks tray can return the reader to it, and standing there restores the same numeric
  // action route so they can revise the recorded answer.
  //
  // Document focus rather than the inner control, for the reason askPosition gives: a
  // control staged in a shadow tree retargets to its host, and the host is the place in the
  // document this wants.
  function standingIn() {
    const held = documentFocused();
    if (!held || held === document.body) return null;
    const place = askPlace(held);
    const unanswered = unansweredAsks().findLast(
      (ask) => ask === place || ask.contains(place),
    );
    if (unanswered) return unanswered;
    // An answered Ask is standing only on the explicit review route: its tray row or
    // the ask element that row lands on. A widget host can be the document's
    // retargeted focus without being the ask itself; treating that as an arrival
    // would make an ordinary click on a chosen option steal the option's own semantics.
    const answered = allAsks().findLast((ask) => ask === place || ask.contains(place));
    if (!answered) return null;
    return held === answered || held.closest(".lf-asks-row") || hasReviewedFocus()
      ? answered
      : null;
  }

  // The Ask-local action map. A package contributes exact controls through the same
  // command scopes dispatch and Help already consume. Each action receives a contextual
  // digit independently of any intrinsic widget binding. The map stays active as Tab
  // moves into the Ask; each route points back to the contributed command, while nearer
  // local scopes still own the keys they declare and the dispatcher's ordinary shadowing
  // keeps an unavailable digit out of every projection.
  function ownedAskControl(askSource, commandSource) {
    const selector = tagsDeclaring(
      (entry) => entry["x-awaits"] || entry["x-request"]?.ask,
    ).join(",");
    return !selector || closestAcross(commandSource, selector) === askSource;
  }
  const MAX_ASK_ACTIONS = 9;
  const availableActions = () => {
    const ask = standingIn();
    if (!ask) return [];
    const source = askSource(ask);
    const actions = decisionControls(commandsWithin(source), `Ask ${ask.id}`).filter(
      ({ source: commandSource, control }) =>
        ownedAskControl(source, commandSource) &&
        control.isConnected &&
        !control.matches(":disabled") &&
        control.getAttribute("aria-disabled") !== "true" &&
        control.getAttribute("aria-busy") !== "true",
    );
    const contextual = bindings({
      keys: Array.from({ length: MAX_ASK_ACTIONS }, (_, index) => String(index + 1)),
    });
    return actions
      .slice(0, contextual.length)
      .map((action, index) => ({ ...action, binding: contextual[index] }));
  };
  // A binding with a different result is a different command. Keep each action as a
  // route under one compact row, so the dispatcher, command reference, shortcut bar, and the
  // control-facing projections all consume the same binding-to-control identity.
  const actionRoutes = () =>
    availableActions().map(
      ({ id, control, label, bindingBadge, intrinsicBindings, command, binding }) =>
        contextualRoute(
          {
            id,
            binding,
            does: `Activate the “${label}” action`,
            line: label,
            control,
            bindingBadge,
            intrinsicBindings,
          },
          command,
        ),
    );
  const actionRow = {
    id: "ask.activate-nth",
    keys: () => actionRoutes().map(({ binding }) => binding),
    routes: actionRoutes,
    label: () => {
      const count = actionRoutes().length;
      return count > 1 ? `1–${count}` : "1";
    },
    does: () =>
      `Activate an action in this Ask: ${actionRoutes()
        .map(({ binding, line }) => `${spell(binding)} ${line}`)
        .join("; ")}`,
    line: () =>
      actionRoutes()
        .map(({ line }) => line)
        .join(" / "),
    when: () => actionRoutes().length > 0,
  };
  const reachableActionRoutes = (available = availableCommandRoutes()) => {
    const reachable = available.get(actionRow) ?? new Set();
    return actionRoutes().filter(({ binding }) => reachable.has(binding));
  };

  // The chips are an eye's projection of the same row, and aria-keyshortcuts is its
  // listener-facing projection on each exact action control. A widget that already owns
  // a binding-badge face lends that face and its exact placement; other actions get chrome at
  // the visible margin entry's corner. Off-screen actions keep their working badge and name
  // on the shortcut bar but wear no chip. A nearer keyboard layer suppresses the row and both
  // projections through the exact reachable bindings, so a digit never stays
  // promised after a sequence, text box, or modal has taken it.
  const wornBindingBadges = new Map();
  const wornShortcuts = new Map();
  function exposedBindingBadge(bindingBadge, control, visible) {
    const whole = bindingBadge.getBoundingClientRect();
    if (
      ["left", "right", "top", "bottom"].some(
        (edge) => Math.abs(whole[edge] - visible[edge]) > 0.5,
      )
    )
      return false;
    const x = (visible.left + visible.right) / 2;
    const y = (visible.top + visible.bottom) / 2;
    const inset = Math.min(
      3,
      (visible.right - visible.left) / 4,
      (visible.bottom - visible.top) / 4,
    );
    // An option's state control shares this slot and turns fully transparent while its
    // binding badge stands. It remains in the hit-test stack without covering the face.
    const transparentControl =
      Number.parseFloat(getComputedStyle(control).opacity) === 0;
    return [
      [x, y],
      [x, visible.top + inset],
      [x, visible.bottom - inset],
      [visible.left + inset, y],
      [visible.right - inset, y],
    ].every(([atX, atY]) => {
      const onTop = elementFromPointAcross(atX, atY);
      return (
        containsAcross(bindingBadge, onTop) ||
        (transparentControl && containsAcross(control, onTop))
      );
    });
  }
  function restoreBindingBadge(bindingBadge, { display, priority, text }) {
    bindingBadge.removeAttribute("data-lf-ask-binding-badge");
    bindingBadge.textContent = text;
    if (display) bindingBadge.style.setProperty("display", display, priority);
    else bindingBadge.style.removeProperty("display");
  }
  function clearActionProjections() {
    for (const [bindingBadge, previous] of wornBindingBadges)
      restoreBindingBadge(bindingBadge, previous);
    wornBindingBadges.clear();
    for (const [control, { previous, projected }] of wornShortcuts) {
      if (control.getAttribute("aria-keyshortcuts") !== projected) continue;
      if (previous === null) control.removeAttribute("aria-keyshortcuts");
      else control.setAttribute("aria-keyshortcuts", previous);
    }
    wornShortcuts.clear();
  }
  function paintActionProjections() {
    clearActionProjections();
    const available = availableCommandRoutes();
    const routes = reachableActionRoutes(available);
    if (!routes.length) {
      askActionLayer.replaceChildren();
      return;
    }
    // A covering tray does not invalidate the commands or their accessible shortcuts,
    // but it does hide the page controls that inline binding-badge faces claim to label.
    const bindingBadgesVisible = !(trayIsOpen("asks") && trayCovers());
    const placement = keyBadgePlacement();
    const bindingBadgeClaims = new Map();
    for (const { bindingBadge } of routes)
      if (bindingBadge)
        bindingBadgeClaims.set(
          bindingBadge,
          (bindingBadgeClaims.get(bindingBadge) ?? 0) + 1,
        );

    // Reuse a widget's page-local binding badge where it has one. Besides preserving the
    // widget's own card-versus-row alignment, leaving this face in the page's stack keeps
    // the fixed shortcut bar above it. One face belongs to one action, and every part of
    // it must be visible on top; otherwise the ordinary core chip carries the same route.
    for (const route of routes) {
      const { binding, intrinsicBindings, control, bindingBadge } = route;
      const previousShortcut = control.getAttribute("aria-keyshortcuts");
      const intrinsicAvailable = available.get(routedCommand(route).row) ?? new Set();
      const intrinsicShortcuts = new Set(
        ariaShortcuts([{ keys: intrinsicBindings }], false).split(/\s+/),
      );
      const projected = ariaShortcuts(
        [
          {
            keys: [
              ...intrinsicBindings.filter((key) => intrinsicAvailable.has(key)),
              binding,
            ],
          },
        ],
        false,
      ).split(/\s+/);
      const projectedShortcut = [
        ...new Set([
          ...(previousShortcut ?? "")
            .split(/\s+/)
            .filter((key) => key && !intrinsicShortcuts.has(key)),
          ...projected,
        ]),
      ].join(" ");
      wornShortcuts.set(control, {
        previous: previousShortcut,
        projected: projectedShortcut,
      });
      control.setAttribute("aria-keyshortcuts", projectedShortcut);
      if (
        !bindingBadgesVisible ||
        !bindingBadge?.isConnected ||
        bindingBadgeClaims.get(bindingBadge) !== 1
      )
        continue;
      const previous = {
        display: bindingBadge.style.getPropertyValue("display"),
        priority: bindingBadge.style.getPropertyPriority("display"),
        text: bindingBadge.textContent,
      };
      bindingBadge.setAttribute("data-lf-ask-binding-badge", "");
      bindingBadge.textContent = spell(binding);
      bindingBadge.style.display = "block";
      const box = bindingBadge.checkVisibility() && placement.visibleBox(bindingBadge);
      if (
        !box ||
        !exposedBindingBadge(bindingBadge, control, box) ||
        !placement.reserve(box)
      ) {
        restoreBindingBadge(bindingBadge, previous);
        continue;
      }
      wornBindingBadges.set(bindingBadge, previous);
    }

    const chips = [];
    for (const { binding, control, bindingBadge } of bindingBadgesVisible
      ? routes
      : []) {
      if (bindingBadge && wornBindingBadges.has(bindingBadge)) continue;
      const presented = presentedActionControl(control);
      if (!presented.checkVisibility()) continue;
      const box = placement.visibleBox(presented);
      if (!box) continue;
      const chip = el("span", "lf-key-badge lf-ask-binding-badge", spell(binding));
      chip.setAttribute("aria-hidden", "true");
      chip.style.left = `${box.left}px`;
      chip.style.top = `${box.top}px`;
      chips.push(chip);
    }
    placement.paint(askActionLayer, chips);
  }
  // Resizing can make routes unreachable or put their controls under a covering tray.
  // Repaint unconditionally so either transition clears the prior projections.
  // The ring that says so, painted from the focus rather than written where the reader was
  // put. The walk used to write it, and it then said where the walk had left them rather
  // than where they were: click away, work in the panel, come back tomorrow, and an ask
  // nobody was standing in went on wearing "you are here". Every other way into an ask —
  // Tab, a click on one of its controls — left the ring somewhere else entirely, so the
  // same place was marked or not by how the reader had reached it.
  //
  // TODO(2026-09-06): Keep the Ask-wide location ring for keyboard navigation and
  // tray-directed focus without painting it after an ordinary pointer click inside the
  // Ask. On a large interactive widget, that click currently leaves a prominent ring
  // around the entire surface even though the focused control already shows the action.
  //
  // Keyed on focus and not on :focus-visible, which is a claim about the last input rather
  // than about where the reader is: a tray row's press lands the focus by script after a
  // click, and the ask it brought the reader to would wear nothing at all.
  //
  // The ask wears it, and so does every box it shows through (shownParts): the ask is
  // what carries the id captureView writes down and the place askStep measures from,
  // while an outline needs a box to hang on. Every widget in the vocabulary draws one
  // box now — the wrapper that declined to took a form instead, in its own stylesheet,
  // after the ring went out over its pieces and read as two boxes touching rather than
  // as the one ask the reader is standing in — so on shipped pages the parts are the
  // ask itself, and the fallback answers the wrapper any page can still style boxless
  // in a line, the same way the thread's mark does (paintAnchors).
  //
  // The tray's row for the ask is a second surface showing this one fact, so it is
  // painted from this one reading rather than from a mark the tray keeps for itself —
  // and the ring is the chrome's as much as the page's (the [data-lf-ask] rule in the
  // stylesheet is written against the attribute, not against the page), so wearing the
  // attribute is the whole of what the row needs.
  function markHere() {
    const here = standingIn();
    const row = here && asksPanel.querySelector(`[${ASK_AT}="${here.id}"]`);
    const wearing = new Set(
      here ? [here, ...shownParts(here), ...(row ? [row] : [])] : [],
    );
    // A walk that runs past the foot of an open tray leaves its mark off screen, which is
    // the tray saying nothing exactly while the reader is using it. `nearest` so a row
    // already in view moves nothing.
    if (row && trayIsOpen("asks")) row.scrollIntoView({ block: "nearest" });
    for (const marked of document.querySelectorAll(`[${PAGE_PAINT_ATTRIBUTE.ask}]`))
      if (!wearing.has(marked)) marked.removeAttribute(PAGE_PAINT_ATTRIBUTE.ask);
    // A control-less request can borrow its own tab stop while the broader x-ask-surface
    // region wears the ring. Keep that stop until the reader leaves the region.
    const holder = here && askSource(here);
    if (askLent && askLent !== here && askLent !== holder) lend(null);
    for (const marked of wearing) marked.setAttribute(PAGE_PAINT_ATTRIBUTE.ask, "1");
    paintActionProjections();
  }
  // The place a node puts the reader in the space this walk measures against, and null where
  // it puts them outside that space. The chrome stands over the page rather than in it, and
  // its controls are binding badges the reader holds from wherever they are: a reader who pressed
  // the Asks button is standing on it, so measuring from it would send the next press back to
  // the top. The layer is also appended after the page, so once the walk clamped at its edges
  // instead of wrapping, taking any of it for a place put the reader behind every ask
  // there is. From a thread in the conversation panel, `a` and `A` both landed on the last.
  //
  // The route runs through the chrome all the same. A widget frozen into a reply is a
  // ask the walk visits, collected beside the document's, and a reader working its
  // controls is standing in the ordered space. So what decides it is membership of that
  // space: the ask a hoisted control or a tray row names (askPlace), or the one the
  // node stands inside. The rest of the layer names none.
  const walkPlace = (node) => {
    const place = askPlace(node);
    if (!inChrome(place)) return place;
    const holding = allAsks().some(
      (ask) => ask === place || containsAcross(ask, place),
    );
    return holding ? place : null;
  };
  // Where the walk measures from: where the reader is standing, rather than where the walk
  // last put them. It carried an id of its own, so every walk the reader had not made with
  // this key started at the top of the page — select a paragraph and press `d` and you were
  // taken back past everything you had read, and so was anyone scrolled halfway down
  // pressing it for the first time. Space page travel measures from the scroll position and t/T from the
  // focused thread; this measured from its own memory, which is the one place the reader
  // isn't.
  //
  // Read in the order of how directly each says where they are: what they have focused,
  // what they have selected, where this walk last left off (`landed`), and what they are
  // reading. Every one of them can be absent, and then the first ask is the only answer
  // there is.
  //
  // Document focus rather than the inner control: a control staged in a shadow tree
  // retargets to its host, which is exactly what this question wants — a place in the
  // document to measure the asks against, not the control the register would dispatch to.
  function askPosition() {
    const held = documentFocused();
    if (held && held !== document.body) {
      const place = walkPlace(held);
      if (place) return place;
    }
    const sel = getSelection();
    // A caret counts here, where the composer's reading of the selection (pageSelection)
    // wants words to quote: a click that placed one is the reader saying where they are.
    if (sel?.focusNode) {
      const place = walkPlace(sel.focusNode);
      if (place) return place;
    }
    // A landing whose element a later version dropped is no place at all, and
    // compareDocumentPosition against a detached node answers about no document.
    return (landed?.isConnected ? landed : null) ?? readingBlock();
  }
  // The ask `dir` steps to from there, clamped at the first and last open asks.
  // Document position rather than an index into the list, because the reader's place is a
  // place and not a row: an ask holding it is the one they are standing on, so it is
  // what they step off rather than what they step to.
  function askStep(asks, dir) {
    const here = askPosition();
    if (!here) return dir > 0 ? asks[0] : asks.at(-1);
    const side =
      dir > 0 ? Node.DOCUMENT_POSITION_FOLLOWING : Node.DOCUMENT_POSITION_PRECEDING;
    const reach = asks.filter((ask) => {
      const rel = here.compareDocumentPosition(ask);
      return !(rel & Node.DOCUMENT_POSITION_CONTAINS) && rel & side;
    });
    return dir > 0 ? (reach[0] ?? asks.at(-1)) : (reach.at(-1) ?? asks[0]);
  }
  // Putting the reader back on the control they were working when a widget rebuilt itself
  // underneath them (rebuild): the control that works this ask — one inside it, or
  // one the widget hoisted into the margin and pointed back at it — or the ask
  // itself, lent a tab stop where it holds nothing to work.
  //
  // This is not where an arrival lands, and the two parted when the scroll and the focus
  // were measured against each other. Arrival puts the ask's opening at the top of
  // the window, and the first control that answers it is as far down the ask as its
  // context and evidence are long: measured on the shipped corpus at 1200x900, the heading
  // stood at 54px and the pick the walk focused ran from 847 to 1107 in a 900px window. So
  // the reader was told to look at one thing and stood on another, off the bottom of the
  // screen, and their next local action could have worked a control they could not see.
  function standOn(el, review = false) {
    const source = askSource(el);
    const control =
      source.querySelector(ASK_CONTROL) ??
      document.querySelector(`[${ASK_ROW}="${source.id}"] ${ASK_CONTROL}`);
    if (!control) lend(source);
    const target = control ?? source;
    if (review) reviewedThrough = target;
    focusForNavigation(target);
  }
  // Where an arrival lands: on the ask, which is what the scroll has just brought to
  // the top of the window and what the ring is about to name. Its controls are then the
  // next Tab stops, in the order they are written, because a tab stop at `tabindex: -1`
  // keeps its place in document order and everything inside an ask comes after it.
  // The ask's exact action routes remain active as Tab moves into its controls;
  // nearer widget scopes still own their local mechanics.
  function arriveAt(ask, review = false) {
    reviewedThrough = review ? ask : null;
    ask.focus({ preventScroll: true });
    if (ask.matches(":focus")) return;
    lend(ask);
    ask.focus({ preventScroll: true });
    if (ask.matches(":focus")) return;
    // An Ask the page styles boxless generates nothing to stand on, and a lent stop
    // does not change that. There the control that answers it is the only place the
    // reader can be, which is where every arrival used to land.
    lend(null);
    standOn(ask, review);
  }

  // The screen the reader can use, and the distance two boxes stand apart in it. The
  // clearance is the scroller's own declared scroll-padding, where it already says how
  // much of its top edge the banner stands over, rather than a second copy of that number
  // kept here.
  const clearanceOf = (box) => parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
  const HEADING = "h1,h2,h3,h4,h5,h6";

  // Where the reader arrives at a page ask: the region whose start has to be in front
  // of them for the question to make sense. A widget declaring x-ask-surface states its own —
  // one heading, then the context and evidence, then the control — and this walk is handed
  // that region rather than the widget inside it, so its arrival is simply its start.
  //
  // The kind that most needs a region is the kind that cannot declare one. A suggestion is
  // an edit to a phrase, and what explains it is the sentence it stands in and the heading
  // over that — so it can never satisfy "an ask must name itself without context outside
  // the ask", and no x-ask-surface can be written round it. Landing on the change alone put
  // its own top edge under the banner and took that sentence with it: the reader arrived
  // at ✓ Accept with nothing on screen saying what they were accepting. So where the
  // author has not declared a region, the document supplies one in the shape a declared
  // region has.
  //
  // Candidates widest first — the heading titling this part of the document, then the
  // block the change stands in, or, for a change that is its own block, the block before
  // it. The first whose start still leaves the ask's own foot on screen wins, so a
  // region never grows past what the reader takes in at once and an ask with nothing
  // that fits keeps the landing this walk always gave it. That bound is what lets the
  // widest candidate go first: a heading a long way up fails to fit, rather than needing a
  // rule about how far up is too far.
  function arrivalRegion(ask, box) {
    if (registry[ask.localName]?.["x-ask-surface"]) return ask;
    const room = shownBox(box).height - clearanceOf(box);
    // A region has to be somewhere the reader can be taken. An element generating no box
    // measures (0,0) at the document's origin, which is not a degenerate answer but a
    // wrong one naming the top of the page (geometry.js says so at shownBox): a hidden
    // paragraph before the change fits every time, and the press then scrolls the page up
    // by the banner's clearance instead of travelling to the ask.
    // A region also has to begin at or above the change: it is the run-up to it, and one
    // starting below would be a region the change is not in. Document order alone does
    // not promise that — a preceding block can be painted lower — and the span such a
    // region measures is negative, which fits every screen there is.
    const fits = (region) => {
      if (!region) return false;
      const start = shownBox(region);
      const target = shownBox(ask);
      return (
        start.height > 0 && start.top <= target.top && target.bottom - start.top <= room
      );
    };
    // The blocks before this one that are about the same part of the document: the two
    // stand under one container, which is what "the heading over this" means and is the
    // whole of the bound the search needs. Without it the nearest preceding heading can
    // be the previous ask's own — two asks written one after another is the ordinary way
    // to write them — and the reader arrives reading the wrong question as the context
    // for this one. It also stops the walk at the section the ask is in rather than
    // running back through the whole document to find a heading.
    //
    // An ancestor both contains and precedes, so the block holding an inline change is
    // asked for by name and excluded here — or the walk backwards would stop at the
    // sentence the change is already inside and call it the one before.
    // The document's own blocks, in document order, which is what picking the last
    // heading and the nearest block both rest on. `pageQueryAll` would reach a widget's
    // declared shadow tree as well, and it concatenates each root's answer rather than
    // composing one order, so the last heading it reported could be from another tree
    // entirely — a worse answer than the one this misses. The crossing worth having is
    // on the two questions asked of each block: `containsAcross` for the container, and
    // the host climb below for the order, which together let an ask staged inside a
    // shadow tree take the heading standing over its host.
    //
    // `hidden` goes with `inChrome`: content-visibility leaves real rects behind, so a
    // block behind a shut disclosure otherwise measures like one the reader can see.
    //
    // Order is asked of the ask as the block's own tree sees it, which for a
    // ask staged in a shadow tree is its host and not the ask. Two nodes in
    // different roots are DISCONNECTED, and the direction bit that comes with it is
    // arbitrary-but-consistent rather than positional: Chrome answers PRECEDING for every
    // block in the document, whichever side of the host it stands. Asked straight, the
    // filter therefore kept the blocks after such an ask too, and the last heading in
    // the container won — the wrong-question arrival this bound exists to remove, in the
    // one shape the crossing above was written to serve.
    const seenBy = (block) => {
      const root = block.getRootNode();
      let node = ask;
      while (node && node.getRootNode() !== root)
        node = node.getRootNode().host ?? null;
      return node;
    };
    const before = [...document.querySelectorAll(TEXT_BLOCK)].filter((block) => {
      const from = seenBy(block);
      return (
        from &&
        !inChrome(block) &&
        !block.closest("[hidden]") &&
        !containsAcross(block, ask) &&
        block.parentElement &&
        containsAcross(block.parentElement, ask) &&
        from.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_PRECEDING
      );
    });
    const heading = before.findLast((block) => block.matches(HEADING));
    return [heading, closestAcross(ask, TEXT_BLOCK) ?? before.at(-1)].find(fits) ?? ask;
  }

  // The arrival the reader already has. The press then moves the ring and the focus and
  // leaves the page where it stands: they can see the ask and the words around it, and
  // scrolling to rebuild a view they are already looking at is motion that says nothing.
  //
  // Whether the ask itself is readable is `readableDestination`'s question, asked of
  // every edge through whatever clips it — an ask half cut off by a board's own
  // scroller is not in front of the reader for having a box inside the window. This adds
  // the one thing that reading cannot know: the arrival is the region's start, so the
  // start has to be standing clear of the banner too.
  function framed(region, ask, box, readableDestination) {
    return (
      readableDestination(ask) &&
      shownBox(region).top >= shownBox(box).top + clearanceOf(box) &&
      availableActions().every(({ control }) =>
        readableDestination(presentedActionControl(control)),
      )
    );
  }

  // Standing on one ask: what d and D do once they have decided which, and what a press on
  // a tray row does having been told outright. One function because it is one act — a
  // second would be a second answer to "how do I put the reader on an ask", and the two
  // would drift the first time either the reveal or the focus rule changed.
  //
  // The list comes with the ask, because the announcement names a place in it and the caller
  // is the one that knows which list it walked: the walk's own or the tray's.
  function goToAsk(next, asks) {
    // A thread's ask lives in the panel, which has no geometry while closed — the
    // same reason reveal() opens a settled group before the scroll.
    if (inChrome(next) && !panelIsOpen()) setPanel(true);
    // A tray beside the page stays standing as a working index. A covering tray has
    // become the whole visible surface, so selecting a page destination closes it
    // before the reveal and focus land; otherwise the correct navigation happens
    // invisibly behind the very sheet that offered it.
    if (!inChrome(next) && trayIsOpen("asks") && trayCovers()) setOpenTray(null);
    reveal(next); // a settled group or an inactive tab has no geometry until it opens
    const source = askSource(next);
    if (source !== next) reveal(source); // let the answering widget settle its own chrome
    landed = next;
    // The ring follows: the focus move is what paints it, so the walk says where to stand
    // and markHere says where the reader is standing, rather than both saying the second.
    arriveAt(next, !unansweredAsks().includes(next));
    // A page Ask starts below the banner so its context comes before its control, and
    // what counts as its context is arrivalRegion's answer: the region an author declared,
    // or the one the document supplies for a change that cannot declare one. A thread
    // Ask is in the panel's own list, whose arrival stays centred in that region.
    // Which box either travel moves is the travel's own question (scrollerFor) rather than
    // a second one asked here.
    //
    // A page arrival the reader already has is left alone. The ring and the focus have
    // moved to the next ask, which is the whole of what this press had left to say.
    if (inChrome(next)) scrollToElement(next, scrollBehavior(), "center");
    else {
      const box = scrollerFor(next);
      const region = arrivalRegion(next, box);
      if (!framed(region, next, box, readableDestination)) {
        // The ask's own box first, which is the only pass that moves a scroller
        // other than the page's: the placement below moves whichever box scrolls the
        // region, and for a region out on the page that is never the board's own
        // scroller. Handing that placement the region alone left an ask inside a
        // card unscrolled in its card, with the ring and focus on a change the reader
        // could not see. `nearest` is a request to reveal only, which is exactly
        // what this needs and what the placement then builds on.
        scrollToElement(next, "instant", "nearest");
        scrollToElement(region, scrollBehavior(), "start");
      }
    }
    const state = unansweredAsks().includes(next) ? "waiting on you" : "answered";
    announce(walkPositionLabel("Ask", asks.indexOf(next) + 1, asks.length, state));
  }

  function stepAsk(dir) {
    const asks = openAsks();
    if (!asks.length) return;
    const next = askStep(asks, dir);
    goToAsk(next, asks);
    beginWalk("ask", "Ask", () =>
      listWalkPosition(openAsks(), standingIn(), {
        identity: (ask) => ask.id,
        qualifier: "open",
      }),
    );
  }

  const answered = () => {
    void syncAsks();
    refreshConversation();
  };
  let mounted = false;
  let stopActionChanges = null;
  const actionsChanged = () => mounted && void syncAsks();
  const pageScrolled = () => reachableActionRoutes().length && repaint();

  function mount() {
    if (mounted) return;
    mounted = true;
    stopActionChanges = watchSemantic(actionsChanged);
    document.addEventListener("lf-answered", answered);
    document.addEventListener(PRESENTATION, actionsChanged);
    addEventListener("scroll", pageScrolled, { capture: true, passive: true });
    addEventListener("resize", repaint);
  }

  function destroy() {
    if (mounted) {
      mounted = false;
      stopActionChanges?.();
      stopActionChanges = null;
      document.removeEventListener("lf-answered", answered);
      document.removeEventListener(PRESENTATION, actionsChanged);
      globalThis.removeEventListener("scroll", pageScrolled, { capture: true });
      globalThis.removeEventListener("resize", repaint);
    }
    scheduled?.resolve();
    scheduled = null;
    asksPresentation?.disconnect();
    asksPresentation = null;
    clearActionProjections();
    askActionLayer.replaceChildren();
    for (const marked of document.querySelectorAll(`[${PAGE_PAINT_ATTRIBUTE.ask}]`))
      marked.removeAttribute(PAGE_PAINT_ATTRIBUTE.ask);
    lend(null);
  }

  return {
    mount,
    destroy,
    buildBulkAnswers,
    syncAsks,
    renderAsks,
    standsWith,
    askPlace,
    standingIn,
    actionRow,
    markHere,
    goToAsk,
    stepAsk,
    landedAt: () => landed,
    setLanded: (value) => (landed = value),
  };
}
