// Compiled from view.ts by build/typescript.mjs; edit that file.
/* Mechanical presentation and arrival for the obligations placed on the page, widgets'
   (records/obligations/place.js).

   The application publisher owns the complete obligation inventory, typed answers,
   completion and attention. This view selects widget sources and resolves their
   current nodes for focus, geometry, contextual commands and blanket actions. Questions
   answered in words navigate through their thread owner instead.

   An obligation keeps its source identity. Its prompt.target names where the user arrives:
   the group the author declares round it (records/obligations/place.js), otherwise the widget
   itself. The source owns the answer and the explicit context bindings. The group
   changes neither the obligation nor its answer.

   Focus, through records/current-target.js, determines which obligation wears the location
   ring. The m/M work walk visits the user's current queue; an answered obligation can
   still receive an explicit review arrival and the same contextual editing routes.
   The selected destination has a lent tab stop at its opening, preserving document
   order so its controls are the next Tab stops. A boxless destination lands on its
   visible source control instead. A revision restores the source identity, leaving
   exact control retention to the widget that replaces that control.

   Every widget arrival shares the same retained-intent travel. Thread sources
   are materialized at their exact owning message through the thread owner. A page
   source arrives at the window's head, at the group holding it, or, for a change set
   among words, at the block holding it, where either fits. A destination already readable
   on every clipped edge keeps its scroll position. DOM measurements and renderer
   nodes never enter the obligation record.

   Blanket actions come from `awaits.all` and invoke each source's declared decision
   method. They preserve one admitted action per widget rather than recording a second
   page-wide answer. */

import { capitalized } from "../../lib/words.js";
import { landingRoom } from "../../readings/landing-scroll.js";
import { offFlow } from "../../readings/off-flow.js";
import { landingBand, shownBox } from "../../dom/geometry.js";
import { PAGE_CONTROL_RANK, registerPageControl } from "../../base/page-controls.js";
import { decisionControls, nativePress } from "../../dom/keyboard/bindings.js";
import { elementById } from "../../readings/passages.js";
import { TEXT_BLOCK } from "../../state/kernel-facts.js";
import { scrollerFor } from "../../readings/reading-regions.js";
import { scrollersOf } from "../../readings/scroll-containers.js";
import { whereGlidesLand } from "../../dom/scrolling.js";
import { decisionFor, registry, tagsDeclaring } from "../../state/registry.js";
import { hasObligationSource } from "../../state/obligations/source.js";
import { obligationEntry } from "./model.js";
import { focused } from "../../dom/focus.js";
import {
  commandDeclarationsWithin,
  commandsWithin,
  contextScopes,
} from "../../dom/keyboard/scopes.js";
import { paintLocation } from "../../readings/target-paint.js";
import { scrollBehavior } from "../../dom/motion.js";
import { OBLIGATION_CONTROL } from "./view-elements.js";
import { ownedObligationControl } from "./answer.js";
import { obligationIn } from "../current-target.js";
import { PRESENTATION } from "../../readings/presentation.js";
import { retainUserIntent } from "../../dom/user-intent.js";
import { bindQueuedWork } from "../../lib/queued-work.js";
import { applicationPresenter, PRESENTATION_DOM } from "../../state/semantic-state.js";
import { under, upFrom, closestAcross } from "../../lib/shadow-tree.js";
import { showHeld } from "../thread/held-news.js";
import { obligationPlace, readObligations } from "./place.js";
import { inChrome } from "../../base/ui-marks.js";

// The obligation view owns contextual action routes and navigation; the keyboard presenter owns their hints.
export function createObligationView({
  prepareNavigationStep,
  arrive,
  openPageThread,
  threadLanding,
  focusForNavigation,
  presentedControl,
  repaint,
}) {
  const obligationNode = (item) => obligationPlace(item).node;
  const sourceNode = (item) => obligationPlace(item).source;
  // The widget whose commands answer an obligation.
  const sourceOwner = (item) =>
    item?.source.kind === "widget" ? elementById(item.source.id) : null;
  const hasObligation = (items, candidate) =>
    Boolean(candidate && items.some((item) => item.id === candidate.id));
  const unansweredIds = () => new Set(readObligations().unanswered.map(({ id }) => id));

  // A thread obligation is part of the application reading before its message's markup
  // has a live reader node. Navigation and activation are the two boundaries that need
  // that node, so materialize the existing thread projection there rather than
  // narrowing the semantic inventory to what happens to be in the DOM.
  //
  // Bulk answers reuse existing nodes and materialize only those not built yet.
  // Explicit arrivals reveal the addressed message, then use the canonical
  // destination policy to select and present its current reader.
  //
  // An obligation a held turn carries has no node until its thread shows what it holds
  // (held-news.js), and that release draws before `showHeld` returns.
  const obligationNodes = (item) => ({
    target: obligationNode(item),
    source: sourceNode(item),
  });
  const reachObligation = (item) => {
    if (item.thread && !obligationNode(item)) showHeld(item.thread);
    return obligationNodes(item);
  };
  const unbuiltMessage = (item, { target, source }) =>
    !target || !source ? item.message : null;
  async function materializeObligation(item, message, intent = null) {
    reachObligation(item);
    await openPageThread(message, {
      part: "message",
      focus: false,
      travel: false,
      ...(intent && { intent }),
    });
    return obligationNodes(item);
  }
  const answeringAll = new Set();
  const bulkAnswers = new Map();
  async function answerAll(outcome) {
    if (answeringAll.has(outcome)) return;
    answeringAll.add(outcome);
    void syncObligations();
    try {
      // Resolve the current open inventory at activation. A control can survive several
      // publications and toolbar moves; it never captures an earlier obligation or DOM node.
      for (const item of readObligations().user) {
        if (
          !hasObligationSource(item, "widget") ||
          obligationEntry(item)?.all !== outcome
        )
          continue;
        const nodes = reachObligation(item);
        const message = unbuiltMessage(item, nodes);
        const { source } = message ? await materializeObligation(item, message) : nodes;
        // An obligation answered for all at once is a widget's, which names its tag.
        const decision = decisionFor(item.source.tag);
        if (!source || !decision) continue;
        const answer = Reflect.get(source, decision.verb);
        if (answer == null) continue;
        if (typeof answer !== "function")
          throw new TypeError(
            `<${item.source.tag}> has no callable ${decision.verb} decision`,
          );
        await Reflect.apply(answer, source, [outcome]);
      }
    } finally {
      answeringAll.delete(outcome);
      void syncObligations();
    }
  }
  let mounted = false;
  // The page's current location paint (dom/repaint.js) reads the asks: which one the user is at,
  // and which keys each answers. A publication that changes them repaints it.
  const presenter = applicationPresenter({
    region: "obligations",
    after: PRESENTATION_DOM.thread,
    reading: () => (mounted ? true : null),
    paint: () => {
      readObligations();
      repaint();
    },
  });

  // One blanket answer per outcome a widget declares one for (`awaits.all`), each
  // deciding its obligations one at a time so the log records what was consented to rather than
  // one blanket yes — accepting the rest after rejecting one stays honest. The widget's
  // module exposes a method named for its deciding verb that takes the outcome; the
  // label is built from the outcome's word. Each is a row of the page's controls,
  // offered while an ask it would take is open.
  //
  // Built from the obligations each reading carries rather than written out above, so the second
  // widget to declare one gets its control by declaring it, and a widget in a thread
  // message declares it under its own publication. Which outcomes exist is what the
  // obligations' own declarations answer, so core names none.
  function buildBulkAnswers() {
    for (const tag of tagsDeclaring((entry) => entry.awaits?.all)) {
      const outcome = registry[tag].awaits.all;
      if (bulkAnswers.has(outcome)) continue;
      const label = capitalized(outcome);
      bulkAnswers.set(outcome, label);
      const waiting = () =>
        readObligations().user.filter((item) => obligationEntry(item)?.all === outcome)
          .length;
      registerPageControl({
        key: `blanket:${outcome}`,
        rank: PAGE_CONTROL_RANK.blanket,
        label: () => `${label} all (${waiting()})`,
        offered: () => waiting() > 0,
        disabled: () => answeringAll.has(outcome),
        group: "page",
        press: () => void answerAll(outcome),
      });
    }
  }
  // A publication that changes the obligations opens the region's ticket synchronously, before
  // its deferred read, so the application barrier already knows the inherited obligation paint
  // is stale. The pass runs this reading after the thread whose markup its rows stand
  // on. A local change, such as a blanket answer starting, claims here.
  function syncObligations() {
    return presenter.present();
  }

  // An answered obligation normally keeps semantic focus on its own element after an On
  // panel row's arrival. A boxless answered widget cannot: its visible revision control
  // is the only focus target. Remember that exact target for this arrival, and only while
  // it still owns focus, so returning to the same control ordinarily does not promote it
  // from its own local meaning to the whole obligation again.
  let reviewedThrough = null;
  function hasReviewedFocus() {
    if (reviewedThrough?.isConnected && focused() === reviewedThrough) return true;
    reviewedThrough = null;
    return false;
  }
  // The obligation the user is in: the one holding the focus, or the one a control
  // hoisted into the margin decides, or the one a thread asking or about it holds the
  // focus for (`obligationIn`).
  //
  // The unanswered obligations rather than the user's list, because being in an obligation is
  // about where the user is working and not about what they owe. The two part on a widget
  // whose own seat holds a thread waiting on the agent: it leaves the list while its pick
  // stays unmade and its controls stay live, and reading the list would take the ring off
  // that widget and move `c` from the seat the user is writing in down to whichever option
  // their focus rests on — a second thread on the child rather than the next line of their
  // own — and the agent's reply would put both back, though nothing the user did moved
  // either. An
  // answered obligation leaves both worklists but stays in the active inventory: the
  // On Me's Done rows can return the user to it, and being there restores
  // the same numeric action route so they can revise the recorded answer.
  function currentLocationObligation(held = focused()) {
    if (!held || held === document.body) return null;
    const record = obligationIn(held);
    if (!record) return null;
    if (readObligations().unanswered.some((item) => item.id === record.id))
      return record;
    // An answered obligation is the current location only on an explicit review route: the obligation element,
    // or chrome that stands for it from outside it, as an On card, a margin entry, a thread's view
    // or a control on a widget in its reply does. A widget host can be the document's retargeted focus without being the
    // obligation itself; treating that as an arrival would make an ordinary click on a chosen
    // option steal the option's own semantics.
    const answered = record;
    const item = obligationNode(answered);
    return held === item || (inChrome(held) && !under(held, item)) || hasReviewedFocus()
      ? answered
      : null;
  }
  const currentLocationIn = () => obligationNode(currentLocationObligation());

  // Widgets own context aliases. The obligation view selects declarations through the same current location
  // relation that maps a margin entry or thread back to its source; the generic
  // compiler retains original command identity and availability.
  const actionsFor = (owner) =>
    decisionControls(commandsWithin(owner), `Obligation ${owner.id}`).filter(
      ({ source: commandSource, control }) =>
        ownedObligationControl(owner, commandSource) &&
        control.getAttribute("aria-busy") !== "true",
    );
  const actionsOf = (item) => {
    const owner = sourceOwner(item);
    return owner ? actionsFor(owner) : [];
  };
  // The answers an obligation offers, for a surface that answers it away from where it stands,
  // as the floating panel's On view does: each Decision control's own words, whether
  // the page advises it, whether it commits the answer, and its own press, so the
  // answer is the widget's, recorded as a press there would be.
  // Null while the obligation's source has no node, as in a thread turn not yet drawn; the
  // caller then offers the arrival instead.
  function choicesOf(item) {
    const owner = sourceOwner(item);
    if (!owner) return null;
    return actionsFor(owner).map(
      ({ id, label, description, recommended, commits, control }) =>
        Object.freeze({
          id,
          label,
          description,
          recommended,
          commits,
          chosen:
            control.getAttribute("aria-pressed") === "true" ||
            control.getAttribute("aria-checked") === "true" ||
            (control.localName === "input" && control.checked),
          press: () => nativePress(presentedControl(control))?.(),
        }),
    );
  }
  // The commands that answer where `origin` stands: the obligation the user there is in
  // (`obligationIn`), which is a widget's, since only a widget's obligation has a place.
  function obligationContext(origin) {
    if (!origin) return null;
    const record = obligationIn(origin);
    let root = null;
    // Keep the projection outside any nearer widget scope, but inside the
    // keyboard boundary of a thread. Native input claims precede context scopes.
    let node = origin;
    for (; record && node; node = upFrom(node)) {
      if (obligationIn(node)?.id !== record.id) break;
      root = node;
      if (node.hasAttribute("data-lf-thread-surface")) break;
    }
    if (!root) return null;
    return {
      root,
      declarations: () => {
        const owner = sourceOwner(record);
        return owner
          ? commandDeclarationsWithin(owner).filter(({ source: commandSource }) =>
              ownedObligationControl(owner, commandSource),
            )
          : [];
      },
    };
  }
  // The ring that says so, painted from the focus rather than written where the user was
  // put. Rejected: the walk writing it, which then says where the walk left them rather
  // than where they are: click away, work in the panel, come back tomorrow, and an obligation
  // nobody is in goes on wearing "you are here". Every other way into an obligation —
  // Tab, a click on one of its controls — leaves the ring somewhere else entirely, so the
  // same place is marked or not by how the user reached it.
  //
  // Pointer and keyboard arrivals share this location reading, as they share the
  // focused control's ring. An On Me row's press lands the focus by script
  // after a click, and the obligation it brought the user to must show where they are.
  //
  // The obligation and every box it shows through wear its stamp and its ring
  // (readings/target-paint.js, `paintLocation`): the obligation is what carries the id
  // captureView writes down and the place the queue walk measures from, while a landing
  // keeps the ring's room at a scroller's edge round each box it lands on (chrome.css).
  function markHere() {
    paintLocation(obligationNode(currentLocationObligation()));
  }
  // Where an arrival lands: on the obligation, which is what the scroll has just brought to
  // the top of the window and what the ring is about to name. Its controls are then the
  // next Tab stops, in the order they are written, because a tab stop at `tabindex: -1`
  // keeps its place in document order and everything inside an obligation comes after it.
  // The obligation's exact action routes remain active as Tab moves into its controls;
  // nearer widget scopes still own their local mechanics.
  // The shared arrival owns focus and its temporary tab stop. The obligation view owns which node
  // means being here, including the visible answering control of a boxless obligation.
  function arrivalFocus(record, review = false) {
    const item = obligationNode(record);
    const source = sourceNode(record);
    if (!item) return null;
    // A boxless decided obligation can retain a zero-height layout rect after its
    // content retires. It has no visible surface to receive the return focus.
    const target =
      !source || [...item.getClientRects()].some((rect) => rect.width && rect.height)
        ? item
        : (source.querySelector(OBLIGATION_CONTROL) ??
          actionsOf(record).map(({ control }) => presentedControl(control))[0] ??
          source);
    reviewedThrough = review ? target : null;
    return target;
  }

  // The user's current location on an obligation, said in terms a replaced document can still answer.
  // Focus on an unnamed control does not cross a document replacement (records/carry.js), but an
  // obligation is not unnamed. Its id is a declared identity that the inventory, the On
  // panel's rows, and the walk already resolve against whichever document is current,
  // so a user working an obligation when a revision lands is put back on the same obligation rather
  // than dropped to `body`.
  //
  // The id is the whole of what is captured, and the obligation itself is the whole of what is
  // handed back. Which control inside it they held is not something this can answer: the
  // controls are the widget's, most carry no id of their own, and the first
  // answering control is the walk's landing rule rather than a restore. Handing that back
  // would guess: a user holding the second option would be given the first, and their
  // next press would choose it. The obligation's own opening
  // is the one place that cannot misfire, because it holds a lent tab stop rather than
  // a decision: the widget's context routes are live there and Space decides nothing.
  //
  // Chrome is excluded because it has nothing to restore: an On Me row and a
  // margin entry for the same obligation are keyed by that id already, so a patch hands each of
  // them back as the same element, still holding the focus the user put on it.
  function captureCurrentLocation() {
    const held = focused(document);
    if (!held || held === document.body || inChrome(held)) return null;
    return currentLocationObligation()?.id ?? null;
  }

  // Put the user back, once the arriving document has been upgraded and presented.
  // Current location is restored rather than asserted: a user the revision left where they were
  // is already there, and an obligation the revision took away is nowhere to stand, so
  // each of those returns and `body` keeps the focus the replacement gave it.
  function restoreCurrentLocation(item) {
    if (!item || currentLocationObligation()?.id === item) return;
    const record = readObligations().byId.get(item);
    const target = record && arrivalFocus(record);
    if (target) focusForNavigation(target, "return");
  }

  // Where the user arrives at a page obligation: the region whose start has to be in front
  // of them for the obligation to make sense. The group the author declares round a
  // question is that region (`prompt.target`): its name, then the context and evidence,
  // then the control. Where the obligation stands at the group alone, the group is also
  // its place, so its arrival is simply its start, however tall the group is. A group
  // several obligations share is the region only where it fits above the source.
  //
  // A suggestion declares no group: it is an edit to a phrase, and what explains it is
  // the sentence it stands in. Landing on the change alone would put its own top edge
  // under the window's head and take that sentence with it, leaving the user at
  // ✓ Accept with nothing on screen saying what they are accepting. So the block
  // holding it is its region where that fits. Leaf reads no heading or neighbouring
  // block for a region, since the author declares the region of anything else that
  // asks: the heading over the change, or the block before it, would be a region Leaf
  // inferred, and a block before a change can be another question's.
  function arrivalRegion(item, group, currentLocation) {
    if (group && group === currentLocation) return group;
    // A region has to be somewhere the user can be taken, beginning at or above the
    // obligation: an element generating no box measures (0,0) at the document's origin,
    // which is not a degenerate answer but a wrong one naming the top of the page
    // (dom/geometry.js says so at shownBox). The screen the user can use is the room a
    // landing at the region's start leaves for the run down to the obligation's foot
    // (readings/landing-scroll.js, `landingRoom`): clear of the window's head over its top and the
    // floating panel's room over its bottom, so an obligation's foot that fits is one the
    // user can read rather than one under the panel.
    const fits = (region) => {
      if (!region) return false;
      const start = shownBox(region);
      const target = shownBox(item);
      return (
        start.height > 0 &&
        start.top <= target.top &&
        target.bottom - start.top <= landingRoom(region, item).height
      );
    };
    return [group, closestAcross(item, TEXT_BLOCK)].find(fits) ?? item;
  }

  // The arrival the user already has. The press then moves the ring and the focus and
  // leaves the page where it stands: they can see the obligation and the words around it, and
  // scrolling to rebuild a view they are already looking at is motion that says nothing.
  //
  // Whether the obligation itself is readable is travel's question (`readable`), asked of
  // every edge through whatever clips it or stands over it — an obligation half cut off by a
  // board's own scroller, or reaching under the floating panel, is not in front of the
  // user for having a box inside the window. Its place and its source are both asked, since
  // a group can stand in the window while a card in it scrolls its answer out of sight.
  // This adds the one thing that reading
  // cannot know: the arrival is the region's start, so the start has to be standing
  // clear of the window's head too, read like the obligation where the glides under way
  // will leave it (dom/scrolling.js, `whereGlidesLand`).
  function alreadyArrived(record, region, item, source, box, readable) {
    return (
      whereGlidesLand(scrollersOf(region), () => {
        const band = landingBand(box);
        return !!band && shownBox(region).top >= band.top;
      }) &&
      readable(item) &&
      readable(source) &&
      actionsOf(record).every(({ control }) => readable(presentedControl(control)))
    );
  }

  // Being on one obligation: what m and Shift+m do once the queue walk has decided on an obligation
  // (panel/queue-walk.js), what an On Me row does, and what a Page Map entry does having
  // been told outright. One
  // function because it is one act — a second would be a second answer to "how do I put
  // the user on an obligation", and the two would drift the first time either the reveal or the
  // focus rule changed. It answers whether the user arrived; the caller announces where,
  // since it is the one that knows which list it walked.
  async function arriveAtRecordNow(next) {
    const mayArrive = retainUserIntent({
      available: () => hasObligation(readObligations().all, next),
    });
    // Materializing an obligation can yield before its destination opens a narrowed thread.
    // The arrival is this walk's deferred invocation; its returned tail is separate.
    const arriveAtRecord = bindQueuedWork(arrive);
    // The place the user leaves, read before drawing the obligation opens its thread,
    // which renames the entry they are on (records/thread/address.js); only a successful
    // arrival commits the departure.
    const departure = prepareNavigationStep();
    // A thread source must exist before the walk can arrive at it.
    if (hasObligationSource(next, "widget") && next.thread)
      await materializeObligation(next, next.message, mayArrive);
    // A thread obligation uses the same retained destination as every other thread
    // arrival. The selected reader may need to disclose a different conversation.
    const { target } = reachObligation(next);
    if (!mayArrive() || !target) return false;
    // A page obligation starts at the window's head so its context comes before its control, and
    // what counts as its context is arrivalRegion's answer: the group holding it, or the
    // block holding a change set among words. Whether this
    // press moves the page is `alreadyArrived`'s answer, and travel's departure owns what follows
    // from it: clearing a surface that hides the obligation, and whether the press is a departure. It runs before the
    // focus lands, since focus sent behind a covering surface is sent back into it.
    // A thread obligation in the floating panel arrives centred in that region, a step
    // as every arrival at a stop the user wasn't on is (features/anchor-travel.js,
    // `prepareNavigationStep`). One in a thread's
    // card, which stands fixed over the page by the thread's words where no scroll of
    // the boxes around the obligation moves it, lands as an arrival at the thread
    // does (features/anchor-travel.js, `threadLanding`). Which box either travel moves is the
    // travel's own question (scrollerFor) rather than a second one asked here.
    // A context other than the widget itself is the group the author declared round it.
    const inGroup = next.source.id !== next.prompt.target;
    const destination = () => {
      const { node: target, source, context } = obligationPlace(next);
      // A widget is arrived at once its source is drawn.
      if (!target || !source) return null;
      if (inChrome(target)) {
        const landing =
          next.thread && offFlow(target) ? threadLanding(next.thread, target) : null;
        return { target, source, box: null, region: null, landing };
      }
      return {
        target,
        source,
        box: scrollerFor(target),
        region: arrivalRegion(source, inGroup ? context : null, target),
        landing: null,
      };
    };
    const initial = destination();
    if (!initial) return false;
    const {
      box: initialBox,
      region: initialRegion,
      source: initialSource,
      landing,
    } = initial;
    const moving = landing
      ? departure.plan(landing.where)
      : departure.plan(
          initial.target,
          initialBox
            ? {
                there: (readable) =>
                  alreadyArrived(
                    next,
                    initialRegion,
                    initial.target,
                    initialSource,
                    initialBox,
                    readable,
                  ),
              }
            : {},
        );
    const arrived = await arriveAtRecord(
      () => {
        const here = destination();
        if (!here) return null;
        const { target, source, box, region, landing } = here;
        const reveal = inGroup
          ? [sourceNode(next)].filter((node) => node !== null)
          : [];
        const focus = arrivalFocus(next, !unansweredIds().has(next.id));
        // The thread's place is where a card's arrival lands, so a fold in the card
        // holding the obligation opens as one around the place would.
        if (landing) return { ...landing, reveal: [target, ...reveal], focus };
        return {
          where: target,
          reveal,
          focus,
          // Reveal the obligation's source through its own inner scrollports before
          // aligning its region, which may stand outside them, as a group round a card
          // that scrolls its answer does. An obligation already arrived at requests no
          // motion.
          scroll: !box
            ? [{ at: target, behavior: scrollBehavior(), block: "center" }]
            : moving
              ? [
                  {
                    at: source,
                    align: region,
                    behavior: scrollBehavior(),
                    block: "start",
                  },
                ]
              : [],
        };
      },
      { intent: mayArrive, departure },
    );
    return arrived;
  }

  // A widget's obligation, which its thread draws first where it stands in one; the
  // rest are their thread owner's.
  function arriveAtRecord(next) {
    if (next.source.kind !== "widget") return Promise.resolve(false);
    const ready = arriveAtRecordNow(next);
    void ready.catch(() => {});
    return ready;
  }

  let stopContextScopes = null;
  const actionsChanged = () => mounted && void syncObligations();

  function mount() {
    if (mounted) return;
    mounted = true;
    stopContextScopes = contextScopes("While answering", obligationContext);
    void syncObligations();
    document.addEventListener(PRESENTATION, actionsChanged);
    addEventListener("resize", repaint);
  }

  function destroy() {
    if (mounted) {
      mounted = false;
      document.removeEventListener(PRESENTATION, actionsChanged);
      globalThis.removeEventListener("resize", repaint);
    }
    stopContextScopes?.();
    stopContextScopes = null;
    presenter.disconnect();
    paintLocation(null);
  }

  return {
    mount,
    destroy,
    buildBulkAnswers,
    syncObligations,
    currentLocationIn,
    captureCurrentLocation,
    restoreCurrentLocation,
    markHere,
    arriveAtRecord,
    choicesOf,
  };
}
