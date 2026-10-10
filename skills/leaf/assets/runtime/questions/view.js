/* Mechanical presentation and arrival for widget Questions.

   The application publisher owns the complete Question inventory, typed answers,
   completion and attention. This view selects widget sources and resolves their
   current nodes for focus, geometry, contextual commands and blanket actions. Prose
   Questions navigate through their thread owner instead.

   A Question keeps its source identity. Its prompt.target names the context the user
   arrives at: an optional lf-ask or other declared x-question-context region, otherwise
   the widget itself. The source owns the answer and the explicit context bindings.
   Adding a context wrapper changes neither the Question nor its answer.

   Focus, through standing-target.js, determines which Question wears the location
   ring. The q/Q work walk visits the user's current queue; an answered Question can
   still receive an explicit review arrival and the same contextual editing routes.
   The selected destination has a lent tab stop at its opening, preserving document
   order so its controls are the next Tab stops. A boxless destination lands on its
   visible source control instead. A revision restores the source identity, leaving
   exact control retention to the widget that replaces that control.

   Every widget arrival shares the same retained-intent travel. Frozen thread sources
   are materialized at their exact owning message through the thread owner. A page
   source arrives below the banner, at its declared context region or the nearest
   fitting heading/text block supplied by its document. A destination already readable
   on every clipped edge keeps its scroll position. DOM measurements and renderer
   nodes never enter the Question record.

   Blanket actions come from x-awaits.all and invoke each source's declared decision
   method. They preserve one admitted action per widget rather than recording a second
   page-wide answer. */

import { scrollIntoView } from "../landing-scroll.js";
import { landingBand, shownBox, shownParts } from "../geometry.js";
import { createQuestionBannerControls } from "./banner-controls.js";
import { decisionControls } from "../keyboard/bindings.js";
import { closestAcross, inChrome, showsWords, TEXT_BLOCK } from "../passages.js";
import { scrollerFor } from "../reading-regions.js";
import { reserve } from "../widget-elements.js";
import { keeps } from "../keeps.js";
import { queueList } from "../drawers.js";
import { decisionFor, registry, tagsDeclaring } from "../registry.js";
import { questionEntry, readQuestions } from "./model.js";
import { walkPositionLabel } from "../walk-position.js";
import { focused } from "../focus.js";
import {
  commandDeclarationsWithin,
  commandsWithin,
  documentFocused,
  contextScopes,
} from "../keyboard/scopes.js";
import { PAGE_PAINT_ATTRIBUTE } from "../page-paint.js";
import { scrollBehavior } from "../motion.js";
import { QUESTION_CONTROL } from "./view-elements.js";
import { ownedQuestionControl } from "./answer.js";
import { rowAt } from "../queue-list.js";
import { questionHolding, placeOf, sideOf } from "../standing-target.js";
import { PRESENTATION } from "../presentation.js";
import { retainUserIntent } from "../user-intent.js";
import { bindQueuedWork } from "../queued-work.js";
import {
  applicationPresenter,
  failSoftAfterRetention,
  PRESENTATION_ORDER,
  PresentationRetentionError,
  readApplication,
  watchSemantic,
} from "../semantic-state.js";
import { hostIn, under, upFrom } from "../shadow.js";
import { showHeld } from "../thread/held-news.js";
import { questionPlace } from "./place.js";

// Question owns contextual action routes and navigation; the keyboard presenter owns their hints.
export function createQuestionView({
  prepareTrip,
  arrive,
  openPageThread,
  focusForNavigation,
  presentedControl,
  announce,
  repaint,
}) {
  const questionNode = (question) => questionPlace(question).node;
  const questionRow = (question) => (question ? rowAt(queueList, question.id) : null);
  const sourceNode = (question) => questionPlace(question).source;
  const hasQuestion = (questions, candidate) =>
    Boolean(candidate && questions.some((question) => question.id === candidate.id));
  const unansweredIds = () => new Set(readQuestions().unanswered.map(({ id }) => id));

  // A thread Question is part of the application reading before its frozen markup has a
  // live reader node. Navigation and activation are the two boundaries that need that
  // node, so materialize the existing thread projection there rather than
  // narrowing the semantic inventory to what happens to be in the DOM.
  //
  // Bulk answers reuse standing nodes and materialize only those not built yet.
  // Explicit arrivals reveal the addressed frozen turn, then use the canonical
  // destination policy to select and present its current reader.
  //
  // A Question a held turn carries has no node until its thread shows what it holds
  // (held-news.js), and that release draws before `showHeld` returns.
  const questionNodes = (question) => ({
    target: questionNode(question),
    source: sourceNode(question),
  });
  const reachQuestion = (question) => {
    if (question.thread && !questionNode(question)) showHeld(question.thread);
    return questionNodes(question);
  };
  const unbuilt = (question, { target, source }) =>
    (!target || !source) && question.thread;
  async function materializeQuestion(question, intent = null) {
    reachQuestion(question);
    await openPageThread(question.message, {
      part: "message",
      focus: false,
      travel: false,
      ...(intent && { intent }),
    });
    return questionNodes(question);
  }
  const presentedActionControl = (control) => presentedControl?.(control) ?? control;
  const answeringAll = new Set();
  const bulkAnswers = new Map();
  const bannerControls = createQuestionBannerControls(async (outcome) => {
    if (answeringAll.has(outcome)) return;
    answeringAll.add(outcome);
    void syncQuestions();
    try {
      // Resolve the current open inventory at activation. A control can survive several
      // publications and toolbar moves; it never captures an earlier Question or DOM node.
      for (const question of readQuestions().user) {
        if (questionEntry(question)?.all !== outcome) continue;
        const nodes = reachQuestion(question);
        const { source } = unbuilt(question, nodes)
          ? await materializeQuestion(question)
          : nodes;
        await source?.[decisionFor(question.source.tag)?.verb]?.(outcome);
      }
    } finally {
      answeringAll.delete(outcome);
      void syncQuestions();
    }
  });
  const questionsRenderer = Object.freeze({ banner: bannerControls });
  const presenter = applicationPresenter({
    region: "questions",
    renderer: questionsRenderer,
    order: PRESENTATION_ORDER.questions,
    current: () => (mounted ? readApplication().semanticEpoch : null),
    failSoft: failSoftAfterRetention(questionsRenderer),
    paint: (epoch, current) => paintQuestions(current),
  });

  // One blanket answer per outcome a widget declares one for (x-awaits.all), each
  // deciding its questions one at a time so the log records what was consented to rather than
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
      // words syncQuestions writes, measured in the face it will render in (see reserve).
      reserve(btn, [`${label} all (999)`]);
    }
  }

  // Each blanket answer with the questions it would take, from the list above. The banner
  // writes its controls and counts from this one reading, without naming an outcome in
  // core; which outcomes exist is the registry's answer.
  function blanketAnswers(questions) {
    return [...bulkAnswers].map(([outcome, label]) => {
      const n = questions.filter(
        (question) => questionEntry(question)?.all === outcome,
      ).length;
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
  // and a publication is where the server's Question reading changes, so a send moves
  // these counts once the state its POST returns has been adopted.
  async function paintQuestions(current) {
    const bannerModel = Object.freeze({
      bulk: Object.freeze(blanketAnswers(readQuestions().user)),
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
          "Question presentation and retention failed",
        );
      }
      throw error;
    }
  }
  // Every semantic notification opens the region's ticket synchronously, before its
  // deferred read. Package subscribers therefore finish their own synchronous updates
  // first, while the application barrier already knows this inherited Question paint is stale.
  // The pass runs this reading after the thread whose markup its rows stand on.
  function syncQuestions() {
    return presenter.present();
  }

  // An answered Question normally keeps semantic focus on its own element after a Questions
  // panel row's arrival. A boxless answered widget cannot: its visible revision control
  // is the only focus target. Remember that exact target for this arrival, and only while
  // it still owns focus, so returning to the same control ordinarily does not promote it
  // from its own local meaning to the whole Question again.
  let reviewedThrough = null;
  function hasReviewedFocus() {
    if (reviewedThrough?.isConnected && focused() === reviewedThrough) return true;
    reviewedThrough = null;
    return false;
  }
  // Resolve a mechanical standing back to one record from the publisher-owned
  // inventory: the source or unambiguous context holding where `node` stands
  // (standing-target.js). DOM containment says where focus is; it never decides whether
  // the Question belongs to that inventory.
  const questionAt = (questions, node) =>
    questionHolding(
      questions.filter((question) => question.source.kind === "widget"),
      placeOf(node),
    );
  // The question the user is standing in: the one holding the focus, or the one a control
  // hoisted into the margin decides, or the one a thread about it holds the focus for.
  //
  // The unanswered questions rather than the user's list, because standing in a question is
  // about where the user is working and not about what they owe. The two part on a widget
  // whose own seat holds a thread waiting on the agent: it leaves the list while its pick
  // stays unmade and its controls stay live, and reading the list took the ring off that
  // widget and moved `c` from the seat the user was writing in down to whichever option
  // their focus rested on — a second thread on the child rather than the next line of their
  // own. The agent's reply put both back. Nothing the user did moved either. An
  // answered question leaves both worklists but stays in the active inventory: the
  // Questions panel's Done rows can return the user to it, and standing there restores
  // the same numeric action route so they can revise the recorded answer.
  //
  // Document focus rather than the inner control: a control staged in a shadow tree
  // retargets to its host, and the host is the place in the document this wants.
  function standingQuestion(held = documentFocused()) {
    if (!held || held === document.body) return null;
    const record = questionAt(readQuestions().all, held);
    if (!record) return null;
    if (readQuestions().unanswered.some((question) => question.id === record.id))
      return record;
    // An answered Question is standing only on an explicit review route: the question element,
    // or chrome whose owner declares it stands at that element (`sideOf`), as a Queue
    // row does. A widget host can be the document's retargeted focus without being the
    // question itself; treating that as an arrival would make an ordinary click on a chosen
    // option steal the option's own semantics.
    const answered = record;
    const question = questionNode(answered);
    return held === question ||
      (inChrome(held) && sideOf(held) === question) ||
      hasReviewedFocus()
      ? answered
      : null;
  }
  const standingIn = () => questionNode(standingQuestion());

  // Widgets own context aliases. Question selects declarations through the same standing
  // relation that maps a margin entry or thread back to its source; the generic
  // compiler retains original command identity and availability.
  const actionsFor = (source) =>
    decisionControls(commandsWithin(source), `Question ${source.id}`).filter(
      ({ source: commandSource, control }) =>
        ownedQuestionControl(source, commandSource) &&
        control.getAttribute("aria-busy") !== "true",
    );
  const actionsOf = (question) => {
    const source = question && sourceNode(question);
    return source ? actionsFor(source) : [];
  };
  function questionContext(origin) {
    const record = questionAt(readQuestions().all, hostIn(origin, document));
    let root = null;
    // Keep the projection outside any nearer widget scope, but inside the
    // keyboard boundary of a thread. Native input claims precede context scopes.
    for (let node = origin; record && node; node = upFrom(node)) {
      if (questionAt(readQuestions().all, node)?.id !== record.id) break;
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
              ownedQuestionControl(source, commandSource),
            )
          : [];
      },
    };
  }
  // The ring that says so, painted from the focus rather than written where the user was
  // put. The walk used to write it, and it then said where the walk had left them rather
  // than where they were: click away, work in the panel, come back tomorrow, and a question
  // nobody was standing in went on wearing "you are here". Every other way into a question —
  // Tab, a click on one of its controls — left the ring somewhere else entirely, so the
  // same place was marked or not by how the user had reached it.
  //
  // TODO(2026-09-06): Keep the Question-wide location ring for keyboard navigation and
  // Queue-directed focus without painting it after an ordinary pointer click inside the
  // Question. On a large interactive widget, that click currently leaves a prominent ring
  // around the entire surface even though the focused control already shows the action.
  //
  // Keyed on focus and not on :focus-visible, which is a claim about the last input rather
  // than about where the user is: a Questions panel row's press lands the focus by script
  // after a click, and the question it brought the user to would wear nothing at all.
  //
  // The question wears it, and so does every box it shows through (shownParts): the question is
  // what carries the id captureView writes down and the place the queue walk measures from,
  // while an outline needs a box to hang on. Every widget in the vocabulary draws one
  // box now — the wrapper that declined to took a form instead, in its own stylesheet,
  // after the ring went out over its pieces and read as two boxes touching rather than
  // as the one question the user is standing in — so on shipped pages the parts are the
  // question itself, and the fallback answers the wrapper any page can still style boxless
  // in a line, the same way the thread's mark does (paintAnchors).
  //
  // The Questions panel's row for the question is a second surface showing this one fact, so it
  // is painted from this one reading rather than from a mark the panel keeps for itself —
  // and the ring is the chrome's as much as the page's (the [data-lf-question] rule in the
  // stylesheet is written against the attribute, not against the page), so wearing the
  // attribute is the whole of what the row needs.
  function markHere() {
    const record = standingQuestion();
    const here = questionNode(record);
    const row = questionRow(record);
    const wearing = new Set(
      here ? [here, ...shownParts(here), ...(row ? [row] : [])] : [],
    );
    for (const marked of document.querySelectorAll(
      `[${PAGE_PAINT_ATTRIBUTE.question}]`,
    ))
      if (!wearing.has(marked)) marked.removeAttribute(PAGE_PAINT_ATTRIBUTE.question);
    for (const marked of wearing) keeps(marked, PAGE_PAINT_ATTRIBUTE.question, "1");
  }
  // Where an arrival lands: on the question, which is what the scroll has just brought to
  // the top of the window and what the ring is about to name. Its controls are then the
  // next Tab stops, in the order they are written, because a tab stop at `tabindex: -1`
  // keeps its place in document order and everything inside a question comes after it.
  // The question's exact action routes remain active as Tab moves into its controls;
  // nearer widget scopes still own their local mechanics.
  // The shared arrival owns focus and its temporary tab stop. Question owns which node
  // means standing here, including the visible answering control of a boxless Question.
  function arrivalFocus(record, review = false) {
    const question = questionNode(record);
    const source = sourceNode(record);
    if (!question || !source) return null;
    // A boxless decided Question can retain a zero-height layout rect after its
    // content retires. It has no visible surface to receive the return focus.
    const target = [...question.getClientRects()].some(
      (rect) => rect.width && rect.height,
    )
      ? question
      : (source.querySelector(QUESTION_CONTROL) ??
        actionsFor(source).map(({ control }) => presentedActionControl(control))[0] ??
        source);
    reviewedThrough = review ? target : null;
    return target;
  }

  // The user's standing on a Question, said in terms a replaced document can still answer.
  // Focus by shape does not cross a document replacement — version.js says why — but an
  // Question is not a shape. Its id is a declared identity that the inventory, the Questions
  // panel's rows, and the walk already resolve against whichever document is standing,
  // so a user working a Question when a revision lands is put back on the same Question rather
  // than dropped to `body`.
  //
  // The id is the whole of what is captured, and the Question itself is the whole of what is
  // handed back. Which control inside it they held is not something this can answer: the
  // controls are the widget's, most carry no id of their own, and the first
  // answering control is the walk's landing rule rather than a restore. Handing that back
  // is the failure version.js's header names — a user holding the second option was
  // given the first, and their next press chose it. The Question's own opening is the one
  // place that cannot misfire, because it holds a lent tab stop rather than a decision:
  // the widget's context routes are live there and Space decides nothing.
  //
  // Chrome is excluded because it has nothing to restore: a Questions panel row and a
  // margin entry for the same Question are keyed by that id already, so a patch hands each of
  // them back as the same element, still holding the focus the user put on it.
  function captureStanding() {
    const held = documentFocused();
    if (!held || held === document.body || inChrome(held)) return null;
    return standingQuestion()?.id ?? null;
  }

  // Put the user back, once the arriving document has been upgraded and presented.
  // Standing is restored rather than asserted: a user the revision left where they were
  // is already standing there, and a Question the revision took away is nowhere to stand, so
  // each of those returns and `body` keeps the focus the replacement gave it.
  function restoreStanding(question) {
    if (!question || standingQuestion()?.id === question) return;
    const record = readQuestions().all.find((candidate) => candidate.id === question);
    const target = record && arrivalFocus(record);
    if (target) focusForNavigation(target, "return");
  }

  const HEADING = "h1,h2,h3,h4,h5,h6";

  // Where the user arrives at a page question: the region whose start has to be in front
  // of them for the question to make sense. A widget declaring x-question-context states its own —
  // one heading, then the context and evidence, then the control — and this walk is handed
  // that region rather than the widget inside it, so its arrival is simply its start.
  //
  // The kind that most needs a region is the kind that cannot declare one. A suggestion is
  // an edit to a phrase, and what explains it is the sentence it stands in and the heading
  // over that — so it can never satisfy "a question must name itself without context outside
  // the question", and no x-question-context can be written round it. Landing on the change alone put
  // its own top edge under the banner and took that sentence with it: the user arrived
  // at ✓ Accept with nothing on screen saying what they were accepting. So where the
  // author has not declared a region, the document supplies one in the shape a declared
  // region has.
  //
  // Candidates widest first — the heading titling this part of the document, then the
  // block the change stands in, or, for a change that is its own block, the block before
  // it. The first whose start still leaves the question's own foot on screen wins, so a
  // region never grows past what the user takes in at once and a question with nothing
  // that fits keeps the landing this walk always gave it. That bound is what lets the
  // widest candidate go first: a heading a long way up fails to fit, rather than needing a
  // rule about how far up is too far.
  function arrivalRegion(question, box, context, standing) {
    // A unique declared context names the region even when taller than the screen:
    // the reader arrives at its opening and reads down to the answering controls.
    // Shared context must fit above this source; otherwise use its nearby words.
    // With only the default source target, infer the words preceding it instead.
    const declared = context && registry[context.localName]?.["x-question-context"];
    if (declared && context === standing) return context;
    // The screen the user can use is the scroller's landing band: clear of the banner
    // over its top and the bottom bar over its bottom, so a question's foot that fits is one
    // the user can read rather than one under the shortcut bar.
    const band = landingBand(box);
    const room = band.bottom - band.top;
    // A region has to be somewhere the user can be taken. An element generating no box
    // measures (0,0) at the document's origin, which is not a degenerate answer but a
    // wrong one naming the top of the page (geometry.js says so at shownBox): a hidden
    // paragraph before the change fits every time, and the press then scrolls the page up
    // by the banner's clearance instead of travelling to the question.
    // A region also has to begin at or above the change: it is the run-up to it, and one
    // starting below would be a region the change is not in. Document order alone does
    // not promise that — a preceding block can be painted lower — and the span such a
    // region measures is negative, which fits every screen there is.
    const fits = (region) => {
      if (!region) return false;
      const start = shownBox(region);
      const target = shownBox(question);
      return (
        start.height > 0 && start.top <= target.top && target.bottom - start.top <= room
      );
    };
    // The blocks before this one that are about the same part of the document: the two
    // stand under one container, which is what "the heading over this" means and is the
    // whole of the bound the search needs. Without it the nearest preceding heading can
    // be the previous question's own — two questions written one after another is the ordinary way
    // to write them — and the user arrives reading the wrong question as the context
    // for this one. It also stops the walk at the section the question is in rather than
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
    // the host climb below for the order, which together let a question staged inside a
    // shadow tree take the heading standing over its host.
    //
    // `showsWords` goes with `inChrome`: a block behind a shut disclosure keeps its
    // boxes, so it would otherwise measure like one the user can see.
    //
    // Order is asked of the question as the block's own tree sees it, which for a
    // question staged in a shadow tree is its host and not the question. Two nodes in
    // different roots are DISCONNECTED, and the direction bit that comes with it is
    // arbitrary-but-consistent rather than positional: Chrome answers PRECEDING for every
    // block in the document, whichever side of the host it stands. Asked straight, the
    // filter therefore kept the blocks after such a question too, and the last heading in
    // the container won — the wrong-question arrival this bound exists to remove, in the
    // one shape the crossing above was written to serve.
    const seenBy = (block) => hostIn(question, block.getRootNode());
    const before = [...document.querySelectorAll(TEXT_BLOCK)].filter((block) => {
      const from = seenBy(block);
      return (
        from &&
        !inChrome(block) &&
        showsWords(block) &&
        !under(question, block) &&
        block.parentElement &&
        under(question, block.parentElement) &&
        from.compareDocumentPosition(block) & Node.DOCUMENT_POSITION_PRECEDING
      );
    });
    const heading = before.findLast((block) => block.matches(HEADING));
    return (
      [
        declared ? context : null,
        heading,
        closestAcross(question, TEXT_BLOCK) ?? before.at(-1),
      ].find(fits) ?? question
    );
  }

  // The arrival the user already has. The press then moves the ring and the focus and
  // leaves the page where it stands: they can see the question and the words around it, and
  // scrolling to rebuild a view they are already looking at is motion that says nothing.
  //
  // Whether the question itself is readable is travel's question (`readable`), asked of
  // every edge through whatever clips it or stands over it — a question half cut off by a
  // board's own scroller, or reaching under the thread panel, is not in front of the
  // user for having a box inside the window. This adds the one thing that reading
  // cannot know: the arrival is the region's start, so the start has to be standing
  // clear of the banner too.
  function framed(record, region, question, box, readable) {
    return (
      readable(question) &&
      shownBox(region).top >= landingBand(box).top &&
      actionsOf(record).every(({ control }) =>
        readable(presentedActionControl(control)),
      )
    );
  }

  // Standing on one question: what q and Shift+q do once the queue walk has decided on a Question
  // (queue-walk.js), what a Questions panel row does, and what a Page Map entry does having
  // been told outright. One
  // function because it is one act — a second would be a second answer to "how do I put
  // the user on a question", and the two would drift the first time either the reveal or the
  // focus rule changed. It answers whether the user arrived; the caller announces where,
  // since it is the one that knows which list it walked.
  async function arriveAtQuestionNow(next) {
    const mayArrive = retainUserIntent({
      available: () => hasQuestion(readQuestions().all, next),
    });
    // Materializing a Question can yield before its destination opens a narrowed thread.
    // The arrival is this walk's deferred invocation; its returned tail is separate.
    const arriveAtQuestion = bindQueuedWork(arrive);
    // A thread Question uses the same retained destination as every other thread
    // arrival. The selected reader may need to disclose a different conversation.
    const { target } = next.thread
      ? await materializeQuestion(next, mayArrive)
      : reachQuestion(next);
    if (!mayArrive() || !target) return false;
    // A page Question starts below the banner so its context comes before its control, and
    // what counts as its context is arrivalRegion's answer: the region an author declared,
    // or the one the document supplies for a change that cannot declare one. Whether this
    // press moves the page is `framed`'s answer, and travel's departure owns what follows
    // from it: clearing a surface that hides the Question (a covering drawer, or the thread
    // panel standing over it), and whether the press is a departure. It runs before the
    // focus lands, since focus sent behind a covering surface is sent back into it.
    // Capture the outgoing place before reveal can reshape it; only a successful
    // arrival commits the departure. A thread Question is
    // in the panel's own list, whose arrival stays centred in that region and is no
    // trip. Which box either travel moves is the travel's own question (scrollerFor)
    // rather than a second one asked here.
    const destination = () => {
      const { node: target, source, context } = questionPlace(next);
      if (!target || !source) return null;
      const box = !inChrome(target) && scrollerFor(target);
      return {
        target,
        source,
        box,
        region: box && arrivalRegion(source, box, context, target),
      };
    };
    const initial = destination();
    if (!initial) return false;
    const departure = prepareTrip({
      landing: () => questionNode(next),
      intent: mayArrive,
    });
    const moving = Boolean(
      initial.box &&
      departure.plan(initial.target, {
        required: [initial.source],
        there: (readable) =>
          framed(next, initial.region, initial.target, initial.box, readable),
      }),
    );
    const arrived = await arriveAtQuestion(
      () => {
        const here = destination();
        if (!here) return null;
        const { target, box, region } = here;
        return {
          where: target,
          reveal: next.source.id !== next.prompt.target ? [sourceNode(next)] : [],
          focus: arrivalFocus(next, !unansweredIds().has(next.id)),
          // Reveal the Question through its own inner scrollports before aligning its
          // context, which may stand outside them. A framed Question requests no motion.
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
    scrollIntoView(questionRow(next), { block: "nearest" });
    return true;
  }

  function arriveAtQuestion(next) {
    if (next.source.kind !== "widget") return Promise.resolve(false);
    const ready = arriveAtQuestionNow(next);
    void ready.catch(() => {});
    return ready;
  }

  // A press naming a Question outright, as a Page Map entry does: the arrival, then its
  // place in the list the caller names.
  function goToQuestion(next, questions) {
    const ready = arriveAtQuestion(next).then((arrived) => {
      if (!arrived) return false;
      const state = unansweredIds().has(next.id) ? "waiting on you" : "answered";
      const index = questions.findIndex((question) => question.id === next.id);
      announce(walkPositionLabel("Question", index + 1, questions.length, state));
      return true;
    });
    void ready.catch(() => {});
    return ready;
  }

  let mounted = false;
  let stopActionChanges = null;
  let stopContextScopes = null;
  const actionsChanged = () => mounted && void syncQuestions();

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
    for (const marked of document.querySelectorAll(
      `[${PAGE_PAINT_ATTRIBUTE.question}]`,
    ))
      marked.removeAttribute(PAGE_PAINT_ATTRIBUTE.question);
  }

  return {
    mount,
    destroy,
    buildBulkAnswers,
    syncQuestions,
    standingIn,
    captureStanding,
    restoreStanding,
    markHere,
    arriveAtQuestion,
    goToQuestion,
  };
}
