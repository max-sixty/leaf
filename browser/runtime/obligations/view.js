/* Mechanical presentation and arrival for the obligations placed on the page: widgets'
   and to-dos on the user (obligations/place.js).

   The application publisher owns the complete obligation inventory, typed answers,
   completion and attention. This view selects widget sources and resolves their
   current nodes for focus, geometry, contextual commands and blanket actions. Questions
   answered in words navigate through their thread owner instead. A to-do has a place
   and no source, so it takes the ring and the arrival and has no commands or choices:
   its Done is the queue walk's (queue-walk.js).

   An obligation keeps its source identity. Its prompt.target names where the user arrives:
   the enclosing widget (an lf-ask or another declaring `x-encloses`), otherwise
   the widget itself. The source owns the answer and the explicit context bindings.
   Adding an enclosing widget changes neither the obligation nor its answer.

   Focus, through current-target.js, determines which obligation wears the location
   ring. The m/M work walk visits the user's current queue; an answered obligation can
   still receive an explicit review arrival and the same contextual editing routes.
   The selected destination has a lent tab stop at its opening, preserving document
   order so its controls are the next Tab stops. A boxless destination lands on its
   visible source control instead. A revision restores the source identity, leaving
   exact control retention to the widget that replaces that control.

   Every widget arrival shares the same retained-intent travel. Frozen thread sources
   are materialized at their exact owning message through the thread owner. A page
   source arrives at the window's head, at its declared context region or the nearest
   fitting heading/text block supplied by its document. A destination already readable
   on every clipped edge keeps its scroll position. DOM measurements and renderer
   nodes never enter the obligation record.

   Blanket actions come from x-awaits.all and invoke each source's declared decision
   method. They preserve one admitted action per widget rather than recording a second
   page-wide answer. */

import { landingRoom } from "../landing-scroll.js";
import { landingBand, shownBox, shownParts } from "../geometry.js";
import { PAGE_CONTROL_RANK, registerPageControl } from "../page-controls.js";
import { decisionControls } from "../keyboard/bindings.js";
import { closestAcross, elementById, inChrome, showsWords } from "../passages.js";
import { TEXT_BLOCK } from "../kernel-facts.js";
import { scrollerFor } from "../reading-regions.js";
import { keeps } from "../keeps.js";
import { decisionFor, registry, tagsDeclaring } from "../registry.js";
import { obligationEntry, readObligations } from "./model.js";
import { walkPositionLabel } from "../walk-position.js";
import { focused } from "../focus.js";
import {
  commandDeclarationsWithin,
  commandsWithin,
  contextScopes,
} from "../keyboard/scopes.js";
import { PAGE_PAINT_ATTRIBUTE } from "../page-paint.js";
import { scrollBehavior } from "../motion.js";
import { OBLIGATION_CONTROL } from "./view-elements.js";
import { obligationWord, ownedObligationControl } from "./answer.js";
import { obligationHolding, placeOf } from "../current-target.js";
import { PRESENTATION } from "../presentation.js";
import { retainUserIntent } from "../user-intent.js";
import { bindQueuedWork } from "../queued-work.js";
import { applicationPresenter, PRESENTATION_DOM } from "../semantic-state.js";
import { hostIn, under, upFrom } from "../shadow.js";
import { showHeld } from "../thread/held-news.js";
import { obligationPlace } from "./place.js";
import { partOver } from "../thread/placement.js";
import { revealAddressed } from "../anchor-resolution.js";

// The obligation view owns contextual action routes and navigation; the keyboard presenter owns their hints.
export function createObligationView({
  prepareNavigationStep,
  arrive,
  openPageThread,
  focusForNavigation,
  presentedControl,
  announce,
  repaint,
}) {
  const obligationNode = (item) => obligationPlace(item).node;
  const sourceNode = (item) => obligationPlace(item).source;
  // The widget whose commands answer an obligation; a to-do has none.
  const sourceOwner = (item) =>
    item?.source.kind === "widget" ? elementById(item.source.id) : null;
  const hasObligation = (items, candidate) =>
    Boolean(candidate && items.some((item) => item.id === candidate.id));
  const unansweredIds = () => new Set(readObligations().unanswered.map(({ id }) => id));

  // A thread obligation is part of the application reading before its frozen markup has a
  // live reader node. Navigation and activation are the two boundaries that need that
  // node, so materialize the existing thread projection there rather than
  // narrowing the semantic inventory to what happens to be in the DOM.
  //
  // Bulk answers reuse existing nodes and materialize only those not built yet.
  // Explicit arrivals reveal the addressed frozen turn, then use the canonical
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
  const unbuilt = (item, { target, source }) => (!target || !source) && item.thread;
  async function materializeObligation(item, intent = null) {
    reachObligation(item);
    await openPageThread(item.message, {
      part: "message",
      focus: false,
      travel: false,
      ...(intent && { intent }),
    });
    return obligationNodes(item);
  }
  const presentedActionControl = (control) => presentedControl?.(control) ?? control;
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
        if (obligationEntry(item)?.all !== outcome) continue;
        const nodes = reachObligation(item);
        const { source } = unbuilt(item, nodes)
          ? await materializeObligation(item)
          : nodes;
        // An obligation answered for all at once is a widget's, which names its tag.
        const { tag } = /** @type {{tag?: string}} */ (item.source);
        await source?.[decisionFor(tag)?.verb]?.(outcome);
      }
    } finally {
      answeringAll.delete(outcome);
      void syncObligations();
    }
  }
  let mounted = false;
  // The page's current location paint (repaint.js) reads the asks: which one the user is at,
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

  // One blanket answer per outcome a widget declares one for (x-awaits.all), each
  // deciding its obligations one at a time so the log records what was consented to rather than
  // one blanket yes — accepting the rest after rejecting one stays honest. The widget's
  // module exposes a method named for its deciding verb that takes the outcome; the
  // label is built from the outcome's word. Each is a row of the page's controls,
  // offered while an ask it would take is open.
  //
  // Built from the obligations each reading carries rather than written out above, so the second
  // widget to declare one gets its control by declaring it, and a widget in a frozen
  // message declares it under its own publication. Which outcomes exist is what the
  // obligations' own declarations answer, so core names none.
  function buildBulkAnswers() {
    for (const tag of tagsDeclaring((entry) => entry["x-awaits"]?.all)) {
      const outcome = registry[tag]["x-awaits"].all;
      if (bulkAnswers.has(outcome)) continue;
      const label = outcome[0].toUpperCase() + outcome.slice(1);
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
  // Resolve a current location back to one record from the publisher-owned
  // inventory: the source or unambiguous context holding where `node` stands
  // (current-target.js). DOM containment says where focus is; it never decides whether
  // the obligation belongs to that inventory.
  const obligationAt = (items, node) => obligationHolding(items, placeOf(node));
  // The obligation the user is in: the one holding the focus, or the one a control
  // hoisted into the margin decides, or the one a thread about it holds the focus for.
  //
  // The unanswered obligations rather than the user's list, because being in an obligation is
  // about where the user is working and not about what they owe. The two part on a widget
  // whose own seat holds a thread waiting on the agent: it leaves the list while its pick
  // stays unmade and its controls stay live, and reading the list took the ring off that
  // widget and moved `c` from the seat the user was writing in down to whichever option
  // their focus rested on — a second thread on the child rather than the next line of their
  // own. The agent's reply put both back. Nothing the user did moved either. An
  // answered obligation leaves both worklists but stays in the active inventory: the
  // On me's Done rows can return the user to it, and being there restores
  // the same numeric action route so they can revise the recorded answer.
  function currentLocationObligation(held = focused()) {
    if (!held || held === document.body) return null;
    const record = obligationAt(readObligations().all, held);
    if (!record) return null;
    if (readObligations().unanswered.some((item) => item.id === record.id))
      return record;
    // An answered obligation is the current location only on an explicit review route: the obligation element,
    // or chrome that stands at that element (`placeOf`), as an On card, a thread's view
    // or a control on a widget in its reply does. A widget host can be the document's retargeted focus without being the
    // obligation itself; treating that as an arrival would make an ordinary click on a chosen
    // option steal the option's own semantics.
    const answered = record;
    const item = obligationNode(answered);
    return held === item ||
      (inChrome(held) && placeOf(held) === item) ||
      hasReviewedFocus()
      ? answered
      : null;
  }
  const currentLocationIn = () => obligationNode(currentLocationObligation());

  // Widgets own context aliases. The obligation view selects declarations through the same current location
  // relation that maps a margin entry or thread back to its source; the generic
  // compiler retains original command identity and availability.
  const actionsFor = (source, owner = source) =>
    decisionControls(commandsWithin(owner), `Obligation ${owner.id}`).filter(
      ({ source: commandSource, control }) =>
        ownedObligationControl(owner, commandSource) &&
        (source === owner || under(control, source)) &&
        control.getAttribute("aria-busy") !== "true",
    );
  const actionsOf = (item) => {
    const source = item && sourceNode(item);
    return source ? actionsFor(source, sourceOwner(item)) : [];
  };
  // The answers an obligation offers, for a surface that answers it away from where it stands,
  // as the floating panel's On view does: each Decision control's own words, whether
  // the page advises it, whether it commits the answer, and its own press, so the
  // answer is the widget's, recorded as a press there would be.
  // Null while the obligation's source has no node, as in a thread turn not yet drawn; the
  // caller then offers the arrival instead.
  function choicesOf(item) {
    const source = sourceNode(item);
    if (!source) return null;
    return actionsFor(source, sourceOwner(item)).map(
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
          press: () => presentedActionControl(control).click(),
        }),
    );
  }
  // The widget obligation whose commands answer where `node` stands. A to-do has no
  // commands, so one standing inside a question, or on it, leaves its digits live.
  const answerableAt = (node) => {
    const all = readObligations().all;
    return obligationHolding(
      all.filter((item) => item.source.kind === "widget"),
      placeOf(node),
      all,
    );
  };
  function obligationContext(origin) {
    const record = answerableAt(hostIn(origin, document));
    let root = null;
    // Keep the projection outside any nearer widget scope, but inside the
    // keyboard boundary of a thread. Native input claims precede context scopes.
    for (let node = origin; record && node; node = upFrom(node)) {
      if (answerableAt(node)?.id !== record.id) break;
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
  // put. The walk used to write it, and it then said where the walk had left them rather
  // than where they were: click away, work in the panel, come back tomorrow, and an obligation
  // nobody was in went on wearing "you are here". Every other way into an obligation —
  // Tab, a click on one of its controls — left the ring somewhere else entirely, so the
  // same place was marked or not by how the user had reached it.
  //
  // Pointer and keyboard arrivals share this location reading, as they share the
  // focused control's ring. An On me row's press lands the focus by script
  // after a click, and the obligation it brought the user to must show where they are.
  //
  // The obligation wears it, and so does every box it shows through (shownParts): the obligation is
  // what carries the id captureView writes down and the place the queue walk measures from,
  // while an outline needs a box to hang on. Every widget in the vocabulary draws one
  // box now — the wrapper that declined to took a form instead, in its own stylesheet,
  // after the ring went out over its pieces and read as two boxes touching rather than
  // as the one obligation the user is in — so on shipped pages the parts are the
  // obligation itself, and the fallback answers the wrapper any page can still style boxless
  // in a line, the same way the thread's mark does (paintAnchors).
  //
  // On me's row for the obligation is a second surface showing this one fact, so it
  // is painted from this one reading rather than from a mark the panel keeps for itself —
  // and the ring is the chrome's as much as the page's (the [data-lf-obligation] rule in the
  // stylesheet is written against the attribute, not against the page), so wearing the
  // attribute is the whole of what the row needs.
  function markHere() {
    const record = currentLocationObligation();
    const here = obligationNode(record);
    const wearing = new Set(here ? [here, ...shownParts(here)] : []);
    for (const marked of document.querySelectorAll(
      `[${PAGE_PAINT_ATTRIBUTE.obligation}]`,
    ))
      if (!wearing.has(marked)) marked.removeAttribute(PAGE_PAINT_ATTRIBUTE.obligation);
    for (const marked of wearing) keeps(marked, PAGE_PAINT_ATTRIBUTE.obligation, "1");
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
          actionsFor(source, sourceOwner(record)).map(({ control }) =>
            presentedActionControl(control),
          )[0] ??
          source);
    reviewedThrough = review ? target : null;
    return target;
  }

  // The user's current location on an obligation, said in terms a replaced document can still answer.
  // Focus by shape does not cross a document replacement — version.js says why — but an
  // obligation is not a shape. Its id is a declared identity that the inventory, the On
  // panel's rows, and the walk already resolve against whichever document is current,
  // so a user working an obligation when a revision lands is put back on the same obligation rather
  // than dropped to `body`.
  //
  // The id is the whole of what is captured, and the obligation itself is the whole of what is
  // handed back. Which control inside it they held is not something this can answer: the
  // controls are the widget's, most carry no id of their own, and the first
  // answering control is the walk's landing rule rather than a restore. Handing that back
  // is the failure version.js's header names — a user holding the second option was
  // given the first, and their next press chose it. The obligation's own opening is the one
  // place that cannot misfire, because it holds a lent tab stop rather than a decision:
  // the widget's context routes are live there and Space decides nothing.
  //
  // Chrome is excluded because it has nothing to restore: an On me row and a
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
    const record = readObligations().all.find((candidate) => candidate.id === item);
    const target = record && arrivalFocus(record);
    if (target) focusForNavigation(target, "return");
  }

  // Where the user arrives at a page obligation: the region whose start has to be in front
  // of them for the obligation to make sense. A widget declaring `x-encloses` is its own frame —
  // one heading, then the context and evidence, then the control — and this walk is handed
  // that region rather than the widget inside it, so its arrival is simply its start.
  //
  // The kind that most needs a region is the kind that cannot declare one. A suggestion is
  // an edit to a phrase, and what explains it is the sentence it stands in and the heading
  // over that — so it can never satisfy "a question must name itself without context outside
  // the question", and no enclosing widget can be written round it. Landing on the change alone put
  // its own top edge under the window's head and took that sentence with it: the user arrived
  // at ✓ Accept with nothing on screen saying what they were accepting. So where the
  // author has not declared a region, the document supplies one in the shape a declared
  // region has.
  //
  // Candidates widest first — the heading titling this part of the document, then the
  // block the change stands in, or, for a change that is its own block, the block before
  // it. The first whose start still leaves the obligation's own foot on screen wins, so a
  // region never grows past what the user takes in at once and an obligation with nothing
  // that fits keeps the landing this walk always gave it. That bound is what lets the
  // widest candidate go first: a heading a long way up fails to fit, rather than needing a
  // rule about how far up is too far.
  function arrivalRegion(item, context, currentLocation) {
    // A unique declared context names the region even when taller than the screen:
    // the reader arrives at its opening and reads down to the answering controls.
    // Shared context must fit above this source; otherwise use its nearby words.
    // With only the default source target, infer the words preceding it instead.
    const declared = context && registry[context.localName]?.["x-encloses"];
    if (declared && context === currentLocation) return context;
    // A region has to be somewhere the user can be taken. An element generating no box
    // measures (0,0) at the document's origin, which is not a degenerate answer but a
    // wrong one naming the top of the page (geometry.js says so at shownBox): a hidden
    // paragraph before the change fits every time, and the press then scrolls the page up
    // by the head room's clearance instead of travelling to the obligation.
    // A region also has to begin at or above the change: it is the run-up to it, and one
    // starting below would be a region the change is not in. Document order alone does
    // not promise that — a preceding block can be painted lower — and the span such a
    // region measures is negative, which fits every screen there is.
    // The screen the user can use is the room a landing at the region's start leaves
    // for the run down to the obligation's foot (landing-scroll.js, `landingRoom`): clear
    // of the window's head over its top and the floating panel's room over its bottom,
    // so an obligation's foot that fits is one the user can read rather than one under the panel.
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
    // The heading is what names the obligation's part of the page (thread/placement.js,
    // `partOver`), bounded by the container both stand under, as below.
    //
    // The blocks before this one that are about the same part of the document: the two
    // stand under one container, as a heading and what it heads do. Without that bound
    // the block before can be the previous obligation's own, and the user arrives
    // reading the wrong obligation as the context for this one.
    //
    // An ancestor both contains and precedes, so the block holding an inline change is
    // asked for by name and excluded here — or the walk backwards would stop at the
    // sentence the change is already inside and call it the one before.
    // The document's own blocks, in document order, which is what picking the nearest
    // block rests on. `pageQueryAll` would reach a widget's
    // declared shadow tree as well, and it concatenates each root's answer rather than
    // composing one order, so the last heading it reported could be from another tree
    // entirely — a worse answer than the one this misses. The heading is read off the
    // page's outline, which composes that order (`partOver`). The crossing worth having is
    // on the two questions asked of each block: `under` for the container, and
    // the host climb below for the order, which together let an obligation staged inside a
    // shadow tree take the heading standing over its host.
    //
    // `showsWords` goes with `inChrome`: a block behind a shut disclosure keeps its
    // boxes, so it would otherwise measure like one the user can see.
    //
    // Order is asked of the obligation as the block's own tree sees it, which for an
    // obligation staged in a shadow tree is its host and not the obligation. Two nodes in
    // different roots are DISCONNECTED, and the direction bit that comes with it is
    // arbitrary-but-consistent rather than positional: Chrome answers PRECEDING for every
    // block in the document, whichever side of the host it stands. Asked straight, the
    // filter therefore kept the blocks after such an obligation too, and a block after it
    // won — the wrong-question arrival this bound exists to remove, in the one shape the
    // crossing above was written to serve.
    const seenBy = (block) => hostIn(item, block.getRootNode());
    const before = [...document.querySelectorAll(TEXT_BLOCK)].filter((block) => {
      const from = seenBy(block);
      return (
        from &&
        !inChrome(block) &&
        showsWords(block) &&
        !under(item, block) &&
        block.parentElement &&
        under(item, block.parentElement) &&
        from.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_PRECEDING
      );
    });
    return (
      [
        declared ? context : null,
        partOver(item),
        closestAcross(item, TEXT_BLOCK) ?? before.at(-1),
      ].find(fits) ?? item
    );
  }

  // The arrival the user already has. The press then moves the ring and the focus and
  // leaves the page where it stands: they can see the obligation and the words around it, and
  // scrolling to rebuild a view they are already looking at is motion that says nothing.
  //
  // Whether the obligation itself is readable is travel's question (`readable`), asked of
  // every edge through whatever clips it or stands over it — an obligation half cut off by a
  // board's own scroller, or reaching under the floating panel, is not in front of the
  // user for having a box inside the window. This adds the one thing that reading
  // cannot know: the arrival is the region's start, so the start has to be standing
  // clear of the window's head too.
  function framed(record, region, item, box, readable) {
    return (
      readable(item) &&
      shownBox(region).top >= landingBand(box).top &&
      actionsOf(record).every(({ control }) =>
        readable(presentedActionControl(control)),
      )
    );
  }

  // Being on one obligation: what m and Shift+m do once the queue walk has decided on an obligation
  // (queue-walk.js), what an On me row does, and what a Page Map entry does having
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
    // A frozen source must exist before its owner can reveal a projected record.
    if (next.thread) await materializeObligation(next, mayArrive);
    if (next.source.unit) {
      const owner = sourceOwner(next);
      if (owner) {
        const hydration = revealAddressed(owner, next.source.unit);
        if (hydration?.then) await hydration;
        if (!mayArrive()) return false;
      }
    }
    // A thread obligation uses the same retained destination as every other thread
    // arrival. The selected reader may need to disclose a different conversation.
    const { target } = reachObligation(next);
    if (!mayArrive() || !target) return false;
    // A page obligation starts at the window's head so its context comes before its control, and
    // what counts as its context is arrivalRegion's answer: the region an author declared,
    // or the one the document supplies for a change that cannot declare one. Whether this
    // press moves the page is `framed`'s answer, and travel's departure owns what follows
    // from it: clearing a surface that hides the obligation, and whether the press is a departure. It runs before the
    // focus lands, since focus sent behind a covering surface is sent back into it.
    // Capture the outgoing place before reveal can reshape it; only a successful
    // arrival commits the departure. A thread obligation is
    // in the panel's own list, whose arrival stays centred in that region and is no
    // navigation step. Which box either travel moves is the travel's own question (scrollerFor)
    // rather than a second one asked here.
    const destination = () => {
      const { node: target, source, context } = obligationPlace(next);
      // A widget is arrived at once its source is drawn; a to-do has none.
      if (!target || (!source && next.source.kind === "widget")) return null;
      const box = !inChrome(target) && scrollerFor(target);
      return {
        target,
        box,
        region: box && arrivalRegion(source ?? target, context, target),
      };
    };
    const initial = destination();
    if (!initial) return false;
    const departure = prepareNavigationStep({
      landing: () => obligationNode(next),
      intent: mayArrive,
    });
    const moving = Boolean(
      initial.box &&
      departure.plan(initial.target, {
        there: (readable) =>
          framed(next, initial.region, initial.target, initial.box, readable),
      }),
    );
    const arrived = await arriveAtRecord(
      () => {
        const here = destination();
        if (!here) return null;
        const { target, box, region } = here;
        return {
          where: target,
          reveal:
            next.source.id !== next.prompt.target
              ? [sourceNode(next)].filter(Boolean)
              : [],
          focus: arrivalFocus(next, !unansweredIds().has(next.id)),
          // Reveal the obligation through its own inner scrollports before aligning its
          // context, which may stand outside them. A framed obligation requests no motion.
          scroll: !box
            ? [{ at: target, behavior: scrollBehavior(), block: "center" }]
            : moving
              ? [
                  {
                    at: target,
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

  // A widget's obligation, which its thread draws first where it stands in one, and a
  // to-do placed on the page outside any thread; the rest are their thread owner's.
  function arriveAtRecord(next) {
    const placed = next.thread === null && Boolean(obligationNode(next));
    if (next.source.kind !== "widget" && !placed) return Promise.resolve(false);
    const ready = arriveAtRecordNow(next);
    void ready.catch(() => {});
    return ready;
  }

  // A press naming an obligation outright, as a Page Map entry does: the arrival, then its
  // place in the list the caller names.
  function goToObligation(next, items) {
    const ready = arriveAtRecord(next).then((arrived) => {
      if (!arrived) return false;
      const state = unansweredIds().has(next.id) ? "waiting on me" : "answered";
      const index = items.findIndex((item) => item.id === next.id);
      announce(walkPositionLabel(obligationWord(next), index + 1, items.length, state));
      return true;
    });
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
    for (const marked of document.querySelectorAll(
      `[${PAGE_PAINT_ATTRIBUTE.obligation}]`,
    ))
      marked.removeAttribute(PAGE_PAINT_ATTRIBUTE.obligation);
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
    goToObligation,
    choicesOf,
  };
}
