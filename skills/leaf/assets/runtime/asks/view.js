/* The ask view: where the user is standing, the ring that says so, the banner's blanket
   answers, and the arrivals that move between asks.

   Focus is the user's current place. `focused` follows it through declared shadow
   roots. A native label activation may pass through `body` or a focusable container
   between the pointer press and the control's focus; Leaf treats that interval as one
   logical standing without changing DOM focus or preventing label text selection.
   `documentFocused` retargets the logical standing to its document host. Painted focus
   readings use one of those two functions; CSS reads the matching `.lf-focus`,
   `.lf-focus-visible`, and `.lf-focus-within` projections. A key ends the pointer
   interval and restores physical focus before dispatch. Code that acts on physical focus
   otherwise reads `document.activeElement` directly. `markHere` paints one `--focus-ring`
   around the semantic ask or control that contains focus. The ring is derived on
   each paint; it does not store the queue walk's position or move either reading surface.
   An explicit Ask arrival reveals its matching Queue panel row; ordinary focus and
   refresh preserve the place the user has chosen in that list.

   The ring is therefore paintable on an ask the `a`/`A` queue walk will not step to.
   The Queue panel lists an answered one under Done (queue-panel.js): the walk is the
   user's worklist, while the panel also keeps the route back to each answered Ask. The
   Escape rung still reads focus rather than either list, so the way out is the one it
   always has.

   Working an ask and standing in one are different facts, and `markHere`'s ring
   answers the second. A user who tabbed to a link inside a question has named something
   more particular than the question, so a press there means the link's own block; reading
   the ring instead overrode what they named, and made the same markup answer differently
   according to whether its question was still open. The two agree wherever the user is
   working the ask, which is every arrival at an Ask the queue walk makes.

   `standingThread` (thread/landing.js) is the exception, and covers all three
   containers that hold a thread the user can stand in: the panel's thread, a
   thread seated on the page, and each thread inside that seat. It asks for the box
   rather than for the container's class, because a resolved thread is built by the same
   function and wears the same class while having no box to reach, and a collapsed one
   answers the same honest way.

   `shownParts` supplies ring targets when a page styles an ask with `display:
   contents`. A normal boxed ask wears one outline on its own box. Hoisted controls
   use the same ring token through the shared chip rule.

   Asks come from every active local `x-awaits` source, answered or open, not from a
   list of ask tags. Where a source is nested in an `x-ask-surface` region, the Ask is
   the region: its heading, context, and evidence are the ask the user is being sent
   to, while the source remains the owner of the answer, which `askAnswers` (answer.js)
   reads for the Queue panel's Done rows. Every arrival at an Ask, from `a`, a Queue
   panel row or a Page Map entry, travels through the one ask-arrival function
   (`arriveAtAsk`), so they agree about focus, reveal, and arrival placement.

   An arrival stands the user on the ask, which is the element the scroll has just
   aligned and the one the ring names. The widget's contributed actions are addressable
   there by their declared context bindings; its controls remain the
   next Tab stops, a stop at `tabindex: -1` keeping its place in document order. Landing
   the answering control instead puts them as far down the ask as its context and
   evidence are long, off the screen the same gesture arranged. An Ask a page styles
   boxless has nothing to stand on and keeps the control as its landing. A widget rebuilt
   under a user is not an arrival and hands back the control they were working.

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
   tree. Shared travel reveals the destination through its nested scrollports, then glides
   the owning reading region without a preliminary page jump. An Ask whose region
   already stands clear of the banner, and
   which travel reads as whole on every edge once whatever surface hid it is cleared
   (anchor-travel.js, `prepareTrip`), is not travelled to at all: the press moves the ring and
   the focus and leaves the page still. A thread ask keeps its centred arrival in the
   panel's own list. */

import { landingBand, shownBox, shownParts } from "../geometry.js";
import { createAskBannerControls } from "./banner-controls.js";
import { decisionControls } from "../keyboard/bindings.js";
import { closestAcross, elementById, inChrome, TEXT_BLOCK } from "../passages.js";
import { scrollerFor } from "../reading-regions.js";
import { reserve } from "../widget-elements.js";
import { keeps } from "../keeps.js";
import { queueList } from "../drawers.js";
import { decisionFor, registry, tagsDeclaring } from "../registry.js";
import {
  allAsks as readAllAsks,
  askEntry,
  openAsks as readOpenAsks,
  unansweredAsks as readUnansweredAsks,
} from "./model.js";
import { walkPositionLabel } from "../walk-position.js";
import {
  commandDeclarationsWithin,
  commandsWithin,
  documentFocused,
  focused,
  contextScopes,
} from "../keyboard/scopes.js";
import { PAGE_PAINT_ATTRIBUTE } from "../page-paint.js";
import { scrollBehavior } from "../motion.js";
import { ASK_CONTROL } from "./view-elements.js";
import { ownedAskControl } from "./answer.js";
import { rowAt } from "../queue-list.js";
import { askHolding, placeOf, sideOf } from "../standing-target.js";
import { PRESENTATION } from "../presentation.js";
import { retainUserIntent } from "../user-intent.js";
import {
  applicationPresenter,
  failSoftAfterRetention,
  PRESENTATION_ORDER,
  PresentationRetentionError,
  readApplication,
  watchSemantic,
} from "../semantic-state.js";
import { hostIn, under, upFrom } from "../shadow.js";

// Ask owns contextual action routes and navigation; the keyboard presenter owns their hints.
export function createAskView({
  panelIsOpen,
  setPanel,
  prepareTrip,
  arrive,
  refreshThread,
  revealThread,
  focusForNavigation,
  presentedControl,
  announce,
  repaint,
}) {
  const allAsks = readAllAsks;
  const openAsks = readOpenAsks;
  const unansweredAsks = readUnansweredAsks;
  const askNode = (ask) => (ask ? elementById(ask.id) : null);
  const askRow = (ask) => (ask ? rowAt(queueList, ask.id) : null);
  const sourceNode = (ask) => (ask ? elementById(ask.sourceId) : null);
  const hasAsk = (asks, candidate) =>
    Boolean(candidate && asks.some((ask) => ask.id === candidate.id));
  const unansweredIds = () => new Set(unansweredAsks().map(({ id }) => id));

  // A thread Ask is part of the application reading before its frozen markup has a
  // live panel node. Navigation and activation are the two boundaries that need that
  // node, so materialize the existing thread projection there rather than
  // narrowing the semantic inventory to what happens to be in the DOM.
  //
  // Only an Ask that has to be built is waited for. One whose nodes already stand is
  // looked up at once, so the arrival that follows still runs inside the gesture that
  // asked for it: what it does to the page, such as widening a narrowing that hides
  // the Ask's thread and clearing the words searched for, is that key's or press's
  // doing, in its own turn.
  const askNodes = (ask) => ({ target: askNode(ask), source: sourceNode(ask) });
  const unbuilt = (ask, { target, source }) => (!target || !source) && ask.thread;
  async function materializeAsk(ask, intent = null) {
    if (!panelIsOpen()) {
      if (intent) {
        if (!intent.handoff(() => setPanel(true))) return {};
      } else setPanel(true);
    }
    await revealThread(ask.thread);
    await refreshThread();
    return askNodes(ask);
  }
  const presentedActionControl = (control) => presentedControl?.(control) ?? control;
  const answeringAll = new Set();
  const bulkAnswers = new Map();
  const bannerControls = createAskBannerControls(async (outcome) => {
    if (answeringAll.has(outcome)) return;
    answeringAll.add(outcome);
    void syncAsks();
    try {
      // Resolve the current open inventory at activation. A control can survive several
      // publications and toolbar moves; it never captures an earlier Ask or DOM node.
      for (const ask of openAsks()) {
        if (askEntry(ask)?.all !== outcome) continue;
        const nodes = askNodes(ask);
        const { source } = unbuilt(ask, nodes) ? await materializeAsk(ask) : nodes;
        await source?.[decisionFor(ask.sourceTag)?.verb]?.(outcome);
      }
    } finally {
      answeringAll.delete(outcome);
      void syncAsks();
    }
  });
  const asksRenderer = Object.freeze({ banner: bannerControls });
  const presenter = applicationPresenter({
    region: "asks",
    renderer: asksRenderer,
    order: PRESENTATION_ORDER.asks,
    current: () => (mounted ? readApplication().semanticEpoch : null),
    failSoft: failSoftAfterRetention(asksRenderer),
    paint: (epoch, current) => paintAsks(current),
  });

  // One blanket answer per outcome a widget declares one for (x-awaits.all), each
  // deciding its asks one at a time so the log records what was consented to rather than
  // one blanket yes — accepting the rest after rejecting one stays honest. The widget's
  // module exposes a method named for its deciding verb that takes the outcome; the
  // label is built from the outcome's word.
  //
  // Built when the registry lands rather than written out above, so the second widget to
  // declare one gets its control by declaring it. Each takes its place in the row rather
  // than a box of its own: a control with no siblings is a control the press sweep walks
  // past, and one that only ever appears at upgrade spends the spacer's slack, not the
  // room of anything to its right.
  function buildBulkAnswers() {
    for (const tag of tagsDeclaring((entry) => entry["x-awaits"]?.all)) {
      const outcome = registry[tag]["x-awaits"].all;
      if (bulkAnswers.has(outcome)) continue;
      const label = outcome[0].toUpperCase() + outcome.slice(1);
      const btn = bannerControls.registerBulk(outcome, label);
      bulkAnswers.set(outcome, label);
      // In the row now, so it holds the widest it reaches below a thousand — the same
      // words syncAsks writes, measured in the face it will render in (see reserve).
      reserve(btn, [`${label} all (999)`]);
    }
  }

  // Each blanket answer with the asks it would take, from the list above. The banner
  // writes its controls and counts from this one reading, without naming an outcome in
  // core; which outcomes exist is the registry's answer.
  function blanketAnswers(asks) {
    return [...bulkAnswers].map(([outcome, label]) => {
      const n = asks.filter((ask) => askEntry(ask)?.all === outcome).length;
      return Object.freeze({
        busy: answeringAll.has(outcome),
        offered: Boolean(n),
        text: `${label} all (${n})`,
        title: `${label} every one still waiting on you`,
        outcome,
      });
    });
  }
  // The banner's reading of that one list. Every semantic publication refreshes it,
  // and a publication is where the server's Ask reading changes, so a send moves
  // these counts once the state its POST returns has been adopted.
  async function paintAsks(current) {
    const bannerModel = Object.freeze({
      bulk: Object.freeze(blanketAnswers(openAsks())),
    });
    repaint();
    try {
      const bannerPaint = await bannerControls.present(bannerModel);
      if (!current()) return [];
      bannerControls.commit();
      return [bannerPaint];
    } catch (error) {
      // A current paint owns the same faces now. It will either commit or restore them;
      // an obsolete attempt must not roll its predecessor over the newer reading.
      if (!current()) return [];
      try {
        await bannerControls.retainCommitted();
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
  // The pass runs this reading after the thread whose markup its rows stand on.
  function syncAsks() {
    return presenter.present();
  }

  // An answered Ask normally keeps semantic focus on its own element after a Queue row's
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
  // Resolve a mechanical standing back to one record from the publisher-owned
  // inventory: the innermost of `asks` holding the place `node` stands at
  // (standing-target.js). DOM containment says where focus is; it never decides whether
  // the Ask belongs to that inventory.
  const askAt = (asks, node) => askHolding(asks, placeOf(node));
  // The ask the user is standing in: the one holding the focus, or the one a control
  // hoisted into the margin decides, or the one a thread about it holds the focus for.
  //
  // The unanswered asks rather than the user's list, because standing in a question is
  // about where the user is working and not about what they owe. The two part on a widget
  // whose own seat holds a thread waiting on the agent: it leaves the list while its pick
  // stays unmade and its controls stay live, and reading the list took the ring off that
  // widget and moved `c` from the seat the user was writing in down to whichever option
  // their focus rested on — a second thread on the child rather than the next line of their
  // own. The agent's reply put both back. Nothing the user did moved either. An
  // answered ask leaves both worklists but stays in the active inventory: the
  // Queue panel's Done rows can return the user to it, and standing there restores the same numeric
  // action route so they can revise the recorded answer.
  //
  // Document focus rather than the inner control: a control staged in a shadow tree
  // retargets to its host, and the host is the place in the document this wants.
  function standingAsk(held = documentFocused()) {
    if (!held || held === document.body) return null;
    const unanswered = askAt(unansweredAsks(), held);
    if (unanswered) return unanswered;
    // An answered Ask is standing only on an explicit review route: the ask element,
    // or chrome whose owner declares it stands at that element (`sideOf`), as a Queue
    // row does. A widget host can be the document's retargeted focus without being the
    // ask itself; treating that as an arrival would make an ordinary click on a chosen
    // option steal the option's own semantics.
    const answered = askAt(allAsks(), held);
    if (!answered) return null;
    const ask = askNode(answered);
    return held === ask ||
      (inChrome(held) && sideOf(held) === ask) ||
      hasReviewedFocus()
      ? answered
      : null;
  }
  const standingIn = () => askNode(standingAsk());

  // Widgets own context aliases. Ask selects declarations through the same standing
  // relation that maps a margin entry or thread back to its source; the generic
  // compiler retains original command identity and availability.
  const actionsFor = (source) =>
    decisionControls(commandsWithin(source), `Ask ${source.id}`).filter(
      ({ source: commandSource, control }) =>
        ownedAskControl(source, commandSource) &&
        control.getAttribute("aria-busy") !== "true",
    );
  const actionsOf = (ask) => {
    const source = ask && sourceNode(ask);
    return source ? actionsFor(source) : [];
  };
  function questionContext(origin) {
    const record = askAt(allAsks(), hostIn(origin, document));
    let root = null;
    // Keep the projection outside any nearer widget scope, but inside the
    // keyboard boundary of a thread. Native input claims precede context scopes.
    for (let node = origin; record && node; node = upFrom(node)) {
      if (askAt(allAsks(), node)?.id !== record.id) break;
      root = node;
      if (node.hasAttribute("data-lf-thread-surface")) break;
    }
    if (!root) return null;
    return {
      root,
      declarations: () => {
        const source = sourceNode(record);
        return source
          ? commandDeclarationsWithin(source).filter(({ source: commandSource }) =>
              ownedAskControl(source, commandSource),
            )
          : [];
      },
    };
  }
  // The ring that says so, painted from the focus rather than written where the user was
  // put. The walk used to write it, and it then said where the walk had left them rather
  // than where they were: click away, work in the panel, come back tomorrow, and an ask
  // nobody was standing in went on wearing "you are here". Every other way into an ask —
  // Tab, a click on one of its controls — left the ring somewhere else entirely, so the
  // same place was marked or not by how the user had reached it.
  //
  // TODO(2026-09-06): Keep the Ask-wide location ring for keyboard navigation and
  // Queue-directed focus without painting it after an ordinary pointer click inside the
  // Ask. On a large interactive widget, that click currently leaves a prominent ring
  // around the entire surface even though the focused control already shows the action.
  //
  // Keyed on focus and not on :focus-visible, which is a claim about the last input rather
  // than about where the user is: a Queue row's press lands the focus by script after a
  // click, and the ask it brought the user to would wear nothing at all.
  //
  // The ask wears it, and so does every box it shows through (shownParts): the ask is
  // what carries the id captureView writes down and the place the queue walk measures from,
  // while an outline needs a box to hang on. Every widget in the vocabulary draws one
  // box now — the wrapper that declined to took a form instead, in its own stylesheet,
  // after the ring went out over its pieces and read as two boxes touching rather than
  // as the one ask the user is standing in — so on shipped pages the parts are the
  // ask itself, and the fallback answers the wrapper any page can still style boxless
  // in a line, the same way the thread's mark does (paintAnchors).
  //
  // The Queue panel's row for the ask is a second surface showing this one fact, so it
  // is painted from this one reading rather than from a mark the panel keeps for itself —
  // and the ring is the chrome's as much as the page's (the [data-lf-ask] rule in the
  // stylesheet is written against the attribute, not against the page), so wearing the
  // attribute is the whole of what the row needs.
  function markHere() {
    const record = standingAsk();
    const here = askNode(record);
    const row = askRow(record);
    const wearing = new Set(
      here ? [here, ...shownParts(here), ...(row ? [row] : [])] : [],
    );
    for (const marked of document.querySelectorAll(`[${PAGE_PAINT_ATTRIBUTE.ask}]`))
      if (!wearing.has(marked)) marked.removeAttribute(PAGE_PAINT_ATTRIBUTE.ask);
    for (const marked of wearing) keeps(marked, PAGE_PAINT_ATTRIBUTE.ask, "1");
  }
  // Where an arrival lands: on the ask, which is what the scroll has just brought to
  // the top of the window and what the ring is about to name. Its controls are then the
  // next Tab stops, in the order they are written, because a tab stop at `tabindex: -1`
  // keeps its place in document order and everything inside an ask comes after it.
  // The ask's exact action routes remain active as Tab moves into its controls;
  // nearer widget scopes still own their local mechanics.
  // The shared arrival owns focus and its temporary tab stop. Ask owns which node
  // means standing here, including the visible answering control of a boxless Ask.
  function arrivalFocus(record, review = false) {
    const ask = askNode(record);
    const source = sourceNode(record);
    if (!ask || !source) return null;
    // A boxless decided Ask can retain a zero-height layout rect after its
    // content retires. It has no visible surface to receive the return focus.
    const target = [...ask.getClientRects()].some((rect) => rect.width && rect.height)
      ? ask
      : (source.querySelector(ASK_CONTROL) ??
        actionsFor(source).map(({ control }) => presentedActionControl(control))[0] ??
        source);
    reviewedThrough = review ? target : null;
    return target;
  }

  // The user's standing on an Ask, said in terms a replaced document can still answer.
  // Focus by shape does not cross a document replacement — version.js says why — but an
  // Ask is not a shape. Its id is a declared identity that the inventory, the Queue rows,
  // and the walk already resolve against whichever document is standing, so a user
  // working an Ask when a revision lands is put back on the same Ask rather than dropped
  // to `body`.
  //
  // The id is the whole of what is captured, and the Ask itself is the whole of what is
  // handed back. Which control inside it they held is not something this can answer: the
  // controls are the widget's, most carry no id of their own, and the first
  // answering control is the walk's landing rule rather than a restore. Handing that back
  // is the failure version.js's header names — a user holding the second option was
  // given the first, and their next press chose it. The Ask's own opening is the one
  // place that cannot misfire, because it holds a lent tab stop rather than a decision:
  // the widget's context routes are live there and Space decides nothing.
  //
  // Chrome is excluded because it has nothing to restore: a Queue row and a margin entry
  // for the same Ask are keyed by that id already, so a patch hands each of them back as
  // the same element, still holding the focus the user put on it.
  function captureStanding() {
    const held = documentFocused();
    if (!held || held === document.body || inChrome(held)) return null;
    return standingAsk()?.id ?? null;
  }

  // Put the user back, once the arriving document has been upgraded and presented.
  // Standing is restored rather than asserted: a user the revision left where they were
  // is already standing there, and an Ask the revision took away is nowhere to stand, so
  // each of those returns and `body` keeps the focus the replacement gave it.
  function restoreStanding(ask) {
    if (!ask || standingAsk()?.id === ask) return;
    const record = allAsks().find((candidate) => candidate.id === ask);
    const target = record && arrivalFocus(record);
    if (target) focusForNavigation(target);
  }

  const HEADING = "h1,h2,h3,h4,h5,h6";

  // Where the user arrives at a page ask: the region whose start has to be in front
  // of them for the question to make sense. A widget declaring x-ask-surface states its own —
  // one heading, then the context and evidence, then the control — and this walk is handed
  // that region rather than the widget inside it, so its arrival is simply its start.
  //
  // The kind that most needs a region is the kind that cannot declare one. A suggestion is
  // an edit to a phrase, and what explains it is the sentence it stands in and the heading
  // over that — so it can never satisfy "an ask must name itself without context outside
  // the ask", and no x-ask-surface can be written round it. Landing on the change alone put
  // its own top edge under the banner and took that sentence with it: the user arrived
  // at ✓ Accept with nothing on screen saying what they were accepting. So where the
  // author has not declared a region, the document supplies one in the shape a declared
  // region has.
  //
  // Candidates widest first — the heading titling this part of the document, then the
  // block the change stands in, or, for a change that is its own block, the block before
  // it. The first whose start still leaves the ask's own foot on screen wins, so a
  // region never grows past what the user takes in at once and an ask with nothing
  // that fits keeps the landing this walk always gave it. That bound is what lets the
  // widest candidate go first: a heading a long way up fails to fit, rather than needing a
  // rule about how far up is too far.
  function arrivalRegion(ask, box) {
    if (registry[ask.localName]?.["x-ask-surface"]) return ask;
    // The screen the user can use is the scroller's landing band: clear of the banner
    // over its top and the bottom bar over its bottom, so an ask's foot that fits is one
    // the user can read rather than one under the shortcut bar.
    const band = landingBand(box);
    const room = band.bottom - band.top;
    // A region has to be somewhere the user can be taken. An element generating no box
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
    // to write them — and the user arrives reading the wrong question as the context
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
    // on the two questions asked of each block: `under` for the container, and
    // the host climb below for the order, which together let an ask staged inside a
    // shadow tree take the heading standing over its host.
    //
    // `hidden` goes with `inChrome`: content-visibility leaves real rects behind, so a
    // block behind a shut disclosure otherwise measures like one the user can see.
    //
    // Order is asked of the ask as the block's own tree sees it, which for a
    // ask staged in a shadow tree is its host and not the ask. Two nodes in
    // different roots are DISCONNECTED, and the direction bit that comes with it is
    // arbitrary-but-consistent rather than positional: Chrome answers PRECEDING for every
    // block in the document, whichever side of the host it stands. Asked straight, the
    // filter therefore kept the blocks after such an ask too, and the last heading in
    // the container won — the wrong-question arrival this bound exists to remove, in the
    // one shape the crossing above was written to serve.
    const seenBy = (block) => hostIn(ask, block.getRootNode());
    const before = [...document.querySelectorAll(TEXT_BLOCK)].filter((block) => {
      const from = seenBy(block);
      return (
        from &&
        !inChrome(block) &&
        !block.closest("[hidden]") &&
        !under(ask, block) &&
        block.parentElement &&
        under(ask, block.parentElement) &&
        from.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_PRECEDING
      );
    });
    const heading = before.findLast((block) => block.matches(HEADING));
    return [heading, closestAcross(ask, TEXT_BLOCK) ?? before.at(-1)].find(fits) ?? ask;
  }

  // The arrival the user already has. The press then moves the ring and the focus and
  // leaves the page where it stands: they can see the ask and the words around it, and
  // scrolling to rebuild a view they are already looking at is motion that says nothing.
  //
  // Whether the ask itself is readable is travel's question (`readable`), asked of
  // every edge through whatever clips it or stands over it — an ask half cut off by a
  // board's own scroller, or reaching under the thread panel, is not in front of the
  // user for having a box inside the window. This adds the one thing that reading
  // cannot know: the arrival is the region's start, so the start has to be standing
  // clear of the banner too.
  function framed(record, region, ask, box, readable) {
    return (
      readable(ask) &&
      shownBox(region).top >= landingBand(box).top &&
      actionsOf(record).every(({ control }) =>
        readable(presentedActionControl(control)),
      )
    );
  }

  // Standing on one ask: what a and Shift+a do once the queue walk has decided on an Ask
  // (queue-walk.js), what a Queue panel row does, and what a Page Map entry does having
  // been told outright. One
  // function because it is one act — a second would be a second answer to "how do I put
  // the user on an ask", and the two would drift the first time either the reveal or the
  // focus rule changed. It answers whether the user arrived; the caller announces where,
  // since it is the one that knows which list it walked.
  async function arriveAtAskNow(next) {
    const mayArrive = retainUserIntent({
      available: () => hasAsk(allAsks(), next),
    });
    // A thread's ask lives in the panel, which has no geometry while closed — the
    // same reason reveal() opens a settled group before the scroll. Waited for only
    // where it has to be built, so an Ask already standing is arrived at in the turn.
    const nodes = askNodes(next);
    let { target } = unbuilt(next, nodes)
      ? await materializeAsk(next, mayArrive)
      : nodes;
    if (!mayArrive() || !target) return false;
    if (inChrome(target) && !panelIsOpen()) {
      if (!mayArrive.handoff(() => setPanel(true))) return false;
      await refreshThread();
      if (!mayArrive()) return false;
      target = askNode(next);
      if (!target) return false;
    }
    // A page Ask starts below the banner so its context comes before its control, and
    // what counts as its context is arrivalRegion's answer: the region an author declared,
    // or the one the document supplies for a change that cannot declare one. Whether this
    // press moves the page is `framed`'s answer, and travel's departure owns what follows
    // from it: clearing a surface that hides the Ask (a covering drawer, or the thread
    // panel standing over it), and whether the press is a departure. It runs before the
    // focus lands, since focus sent behind a covering surface is sent back into it.
    // Capture the outgoing place before reveal can reshape it; only a successful
    // arrival commits the departure. A thread Ask is
    // in the panel's own list, whose arrival stays centred in that region and is no
    // trip. Which box either travel moves is the travel's own question (scrollerFor)
    // rather than a second one asked here.
    const destination = () => {
      const target = askNode(next);
      if (!target || !sourceNode(next)) return null;
      const box = !inChrome(target) && scrollerFor(target);
      return { target, box, region: box && arrivalRegion(target, box) };
    };
    const initial = destination();
    if (!initial) return false;
    const departure = prepareTrip({
      landing: () => askNode(next),
      intent: mayArrive,
    });
    const moving = Boolean(
      initial.box &&
      departure.plan(initial.target, {
        there: (readable) =>
          framed(next, initial.region, initial.target, initial.box, readable),
      }),
    );
    const arrived = await arrive(
      () => {
        const here = destination();
        if (!here) return null;
        const { target, box, region } = here;
        return {
          where: target,
          reveal: next.sourceId !== next.id ? [sourceNode(next)] : [],
          focus: arrivalFocus(next, !unansweredIds().has(next.id)),
          // Reveal the Ask through its own inner scrollports before aligning its
          // context, which may stand outside them. A framed Ask requests no motion.
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
      {
        intent: mayArrive,
        departure,
        keep: true,
      },
    );
    if (!arrived) return false;
    askRow(next)?.scrollIntoView({ block: "nearest" });
    return true;
  }

  function arriveAtAsk(next) {
    const ready = arriveAtAskNow(next);
    void ready.catch(() => {});
    return ready;
  }

  // A press naming an Ask outright, as a Page Map entry does: the arrival, then its
  // place in the list the caller names.
  function goToAsk(next, asks) {
    const ready = arriveAtAsk(next).then((arrived) => {
      if (!arrived) return false;
      const state = unansweredIds().has(next.id) ? "waiting on you" : "answered";
      const index = asks.findIndex((ask) => ask.id === next.id);
      announce(walkPositionLabel("Ask", index + 1, asks.length, state));
      return true;
    });
    void ready.catch(() => {});
    return ready;
  }

  let mounted = false;
  let stopActionChanges = null;
  let stopContextScopes = null;
  const actionsChanged = () => mounted && void syncAsks();

  function mount() {
    if (mounted) return;
    mounted = true;
    stopContextScopes = contextScopes("In this question", questionContext);
    stopActionChanges = watchSemantic(actionsChanged);
    document.addEventListener(PRESENTATION, actionsChanged);
    addEventListener("resize", repaint);
  }

  function destroy() {
    if (mounted) {
      mounted = false;
      stopActionChanges?.();
      stopActionChanges = null;
      document.removeEventListener(PRESENTATION, actionsChanged);
      globalThis.removeEventListener("resize", repaint);
    }
    stopContextScopes?.();
    stopContextScopes = null;
    presenter.disconnect();
    for (const marked of document.querySelectorAll(`[${PAGE_PAINT_ATTRIBUTE.ask}]`))
      marked.removeAttribute(PAGE_PAINT_ATTRIBUTE.ask);
  }

  return {
    mount,
    destroy,
    buildBulkAnswers,
    syncAsks,
    standingIn,
    captureStanding,
    restoreStanding,
    markHere,
    arriveAtAsk,
    goToAsk,
  };
}
