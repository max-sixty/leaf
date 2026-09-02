import { createAuthoredProjection } from "./projection/authored.js";
import { createProjectionFold } from "./projection/fold.js";
import { stateSpecs } from "./registry.js";

let publishedProjection;
export const shallowSigs = (...args) => publishedProjection.shallowSigs(...args);
export const standingState = (...args) => publishedProjection.standingState(...args);
export const withdraw = (...args) => publishedProjection.withdraw(...args);
export const undoableAction = (...args) => publishedProjection.undoableAction(...args);

/* Declaration-driven state projection and reconciliation. */
export function createProjection(runtime, dependencies) {
  const {
    DECISION_ROW,
    COLLAPSE,
    MARKED_ANYWHERE,
    MARKED_IN_PAGE,
    PAGE_PAINT_ATTRIBUTE,
    PAGE_PAINT_ATTRIBUTES,
    answeredContext,
    decisionEntry,
    containsAcross,
    dress,
    elementById,
    failSoft,
    focused,
    inChrome,
    isAwaiting,
    markDeclared,
    outbox,
    pagePresented,
    pageQueryAll,
    pageShifted,
    paintAnchors,
    paintKeys,
    paintAcknowledgments,
    post,
    projectedParent,
    quoteFrom,
    reachScrollers,
    rememberPassageParts,
    removeOutbox,
    renderQuiet,
    renderRetired,
    reportPageError,
    settling,
    settlementSlots,
    standOn,
    textNodesUnder,
    notice,
    unaccountedGesture,
  } = dependencies;
  const { registry } = runtime;

  // The DOM's one checkpoint: each semantic coordinate names the projected winner
  // painted there and the widget/unit nodes that held it. Event ids alone cannot prove
  // state survived a recordless rebuild or a thread reconcile; node identity can. A
  // coordinate with no winner is committed too, once its authored baseline stands.
  const committedProjection = new Map();
  // An id-bearing element's state as markup can say it: tag, attributes, and
  // place among its id-bearing kin. Text is deliberately absent — words are the
  // static gate's subject (restatement_errors); this is the rest, the state no
  // version file can speak. What the runtime itself paints onto page elements —
  // exactly PAGE_PAINT_ATTRIBUTES — is absent too: no version can assert those,
  // and looking away from them keeps a reading taken from the live DOM equal to
  // one taken from the file without hiding a widget's own data-lf state. Diffed around each replay batch to
  // record what replay wrote, and imported by version check --render to read the version
  // files with the same eyes, so the two readings cannot drift.
  function shallowSigs(root) {
    const sigs = new Map();
    const siblingPositions = new Map();
    for (const el of [root, ...root.querySelectorAll("[id]")]) {
      if (!el.id) continue;
      const attrs = [...el.attributes]
        .filter((a) => !PAGE_PAINT_ATTRIBUTES.has(a.name))
        .map((a) => `${a.name}=${a.value}`)
        .sort()
        .join(" ");
      const parent = el.parentElement;
      let positions = siblingPositions.get(parent);
      if (!positions) {
        positions = new Map();
        for (const sibling of parent?.children ?? [])
          if (sibling.id) positions.set(sibling, positions.size);
        siblingPositions.set(parent, positions);
      }
      sigs.set(
        el.id,
        `${el.tagName} [${attrs}] in=${parent?.id ?? ""}#${positions.get(el) ?? -1}`,
      );
    }
    return sigs;
  }
  // The settlement mark is the layer's paint of a logged decision, never a module
  // obligation: x-retired-when and x-parent already state which verbs settle a holder,
  // so the writer with the registry and the log both in hand is this replay. It used to
  // be each holder module's duty, documented in the scaffold and enforced nowhere — the
  // suggestion remembered, and the first module that forgot would have silently split
  // the page's reading from the file's, with `leaf comment` refusing quotes as the only
  // symptom. A module is still free to say the mark sooner as its own gesture's paint
  // (lf-suggestion does, choreographing its fold around it); this write is then the
  // no-op that makes the guarantee unconditional. Written only where an action retires
  // behind the version and retraction gates — applied, thrown, or with no applyAction
  // to call — so a pinned older page and a restated decision stay unmarked. The mark
  // follows the fold both ways: the file's standing settlement is the last surviving
  // action at that owner-unit-facet coordinate, so another outcome there displaces the
  // decision and the mark goes with it — left standing, the page would silence slots the
  // log had handed back. Returns whether it wrote, for the one caller that would otherwise
  // report nothing written.
  function markSettled(el, action) {
    const outcomes = settlementSlots()[el.localName];
    if (!outcomes) return false;
    if (outcomes[action]) {
      el.setAttribute("data-lf-state", action);
      renderRetired(el);
      return true;
    }
    const state = registry[el.localName]?.["x-state"] ?? {};
    const spec = state[action];
    const settlementFacet = state[el.getAttribute("data-lf-state")]?.facet;
    if (
      spec?.unit === "widget" &&
      spec.facet === settlementFacet &&
      el.hasAttribute("data-lf-state")
    ) {
      el.removeAttribute("data-lf-state");
      renderRetired(el);
      return true;
    }
    return false;
  }
  function clearSettled(el, facet) {
    const action = el.getAttribute("data-lf-state");
    const spec = registry[el.localName]?.["x-state"]?.[action];
    if (!action || spec?.unit !== "widget" || spec.facet !== facet) return false;
    el.removeAttribute("data-lf-state");
    renderRetired(el);
    return true;
  }
  const {
    authoredDetails,
    authoredFacets,
    authoredMarkup,
    authoredParents,
    authoredStatements,
    authoredWidgets,
    captureAuthoredFacets,
    domFacet,
    rememberAuthoredMarkup,
    stateCoordinate,
    unitOf,
  } = createAuthoredProjection({ quoteFrom, textNodesUnder });

  function resetAuthoredPage() {
    // A live revision replaces the page document, not the frozen widget markup in
    // conversations. Clearing every baseline made a standing thread action become the
    // next baseline when the panel reconciled: Undo then restored the replayed choice
    // instead of the reply's inert authored state. Page and thread ids cannot overlap,
    // so remove only owners currently declared by the page and leave the conversation's
    // second document intact.
    const pageOwners = new Set();
    for (const { tag } of stateSpecs())
      for (const widget of pageQueryAll(tag))
        if (widget.id && !inChrome(widget)) pageOwners.add(widget.id);
    const dropCoordinates = (records) => {
      for (const coordinate of records.keys()) {
        const [owner] = JSON.parse(coordinate);
        if (pageOwners.has(owner)) records.delete(coordinate);
      }
    };
    dropCoordinates(authoredFacets);
    dropCoordinates(authoredDetails);
    dropCoordinates(committedProjection);
    for (const owner of pageOwners) {
      authoredStatements.delete(owner);
      authoredMarkup.delete(owner);
      authoredWidgets.delete(owner);
    }
    for (const attr of [
      PAGE_PAINT_ATTRIBUTE.applied,
      PAGE_PAINT_ATTRIBUTE.replayWrote,
      PAGE_PAINT_ATTRIBUTE.reportWrote,
    ])
      document.body.removeAttribute(attr);
  }

  const {
    compareProjected,
    foldedFacet,
    projectionFromView,
    standingState,
    stateProjection,
  } = createProjectionFold(runtime, {
    COLLAPSE,
    domFacet,
    elementById,
    outbox,
  });

  // One canonical current reading for action admission as for replay: the latest desired
  // action/report at an owner-unit-facet coordinate, falling back to the version's
  // captured authored facet. A gesture may already have changed the live DOM before it
  // calls sendAction, so eligibility never reads that mutable rendering.
  function projectedFacet(widget, spec, winners = stateProjection().desired) {
    const coordinate = stateCoordinate(widget.id, widget.id, spec);
    const winner = winners.get(coordinate);
    return winner ? winner.value : authoredFacets.get(coordinate);
  }

  // x-awaits conditions normally name authored configuration attributes (choose,
  // multiple), but a value record can make the tested attribute itself current state
  // (a task's reported status). Read that field from the same fold that replay uses,
  // never from DOM a gesture or a not-yet-painted poll may already have changed.
  function matchesProjectedWhen(widget, when, projection) {
    return Object.entries(when ?? {}).every(([attr, values]) => {
      const declaration = stateSpecs().find(
        ({ tag, spec }) =>
          tag === widget.localName &&
          spec.unit === "widget" &&
          spec.record?.kind === "value" &&
          spec.record.attr === attr,
      );
      const value = declaration
        ? projectedFacet(widget, declaration.spec, projection.desired)
        : widget.getAttribute(attr);
      const present = declaration ? value !== null : widget.hasAttribute(attr);
      return values.some((candidate) =>
        typeof candidate === "boolean" ? present === candidate : value === candidate,
      );
    });
  }

  // Parent means the nearest enclosing vocabulary widget. The registry boundary has
  // already proved it is one of the sender's x-parent holders and that every permitted
  // holder declares this facet, so runtime code neither names nor skips widget families.
  function requirementTarget(widget, target, context) {
    if (target === "self") return widget;
    const permitted = registry[widget.localName]["x-parent"] ?? [];
    for (
      let node = projectedParent(widget, context);
      node;
      node = projectedParent(node, context)
    )
      if (registry[node.localName])
        return permitted.includes(node.localName) && decisionEntry(node) ? node : null;
    return null;
  }

  function requirementMatches(widget, spec) {
    if (!pagePresented()) return false;
    const requirement = spec.requires;
    // Whether the request is answered, which is not the question the banner asks: a
    // conversation standing in the widget's own seat takes the decision off the reader's
    // list without answering it. Reading the reader's list here would refuse the pick
    // because the reader had remarked on the question, which is refusing them the answer
    // they were asked for. One reducer, and the caller names the question it wants.
    const context = answeredContext();
    const target = requirementTarget(widget, requirement.target, context);
    if (!target) return false;
    const awaiting = isAwaiting(target, context);
    return awaiting === requirement.awaiting;
  }

  // A recorded action has already been painted by its widget when it enters this door.
  // Give that optimistic value the same semantic coordinate as authoritative state, and
  // commit it on the exact nodes that carry it. Record-less actions paint only after
  // acceptance, so putting one in this overlay would show a decision the server may refuse.
  function stageOutboxAction(entry) {
    const e = entry.event;
    if (e.kind !== "action") return;
    const widget = elementById(e.widget);
    const spec = widget && registry[widget.localName]?.["x-state"]?.[e.action];
    if (!spec?.record) return;
    const unit = unitOf(e, spec);
    if (typeof unit !== "string") return;
    const coordinate = stateCoordinate(e.widget, unit, spec);
    const projection = {
      unit,
      spec,
      coordinate,
      localOrder: entry.order,
      e: { ...e, id: entry.localId },
      value: foldedFacet(e, spec.record),
    };
    entry.projection = projection;
    committedProjection.set(coordinate, {
      widgetId: e.widget,
      widget,
      unit: elementById(unit),
      entry: projection,
    });
  }

  // ---------- taking a gesture back ----------
  // Undo withdraws; it never deletes. The log is append-only and the page is a fold over
  // it, so `z` posts one event naming the gesture it takes back, and every fold and the
  // thread reading drop that gesture. The page is then the version plus what still
  // stands — the same sentence a reload has always read, and the same one `restated`
  // already writes from the author's side. Nothing states a counter-gesture into the
  // log: a card put back where it came from would read as a decision to move it there,
  // and "undecided" is not a value any verb can carry, so a page whose reader takes back
  // an accept could never have been stated at all.
  //
  // What the reader *sees* is derived from that rather than restated, and by the
  // cheapest faithful means. Where the log still leaves the unit a state that can be
  // stated — a prior action's detail, or the placement this version's markup arrived
  // showing — the widget is told it, so the card travels back under the reader's eye and
  // keeps its focus. Where the verb records nothing, there is no such state, so the
  // widget is rebuilt from the version's own markup and whatever survives is replayed
  // onto it. Both routes are chosen by a declaration and neither knows a widget's name.
  // Whether removing one action leaves the reconciler a state it can paint. The actual
  // transition belongs to reconciliation; this is only the keyboard offer, bounded to
  // the version where the gesture was made.
  function canUndoAction(candidate) {
    const e = candidate.event;
    const el = elementById(e.widget);
    if (!el || !el.applyAction) return false;
    const spec = registry[el.tagName.toLowerCase()]?.["x-state"]?.[e.action];
    if (!spec) return false;
    if (!spec.record) return authoredMarkup.has(e.widget);
    const unit = unitOf(e, spec);
    const coordinate = stateCoordinate(e.widget, unit, spec);
    return (
      candidate.restores_desired ||
      authoredDetails.has(coordinate) ||
      authoredMarkup.has(e.widget)
    );
  }

  // The newest gesture of the reader's own that still stands and can still be taken off
  // the page. Newest-first over the whole log rather than a stack this tab keeps,
  // because a stack is a second store: it would die on the reload a new version
  // performs, and a second tab would hold a different one. The reader's own — an agent's
  // `leaf resolve` is not theirs to undo — and never an undo itself, which is what makes
  // repeated presses a walk backwards instead of a toggle.
  function undoable() {
    for (const candidate of runtime.view?.undo ?? []) {
      const e = candidate.event;
      if (e.kind === "resolve" || e.kind === "unresolve") return e;
      // A reaction, while it is still a mark: a message with words in it is said rather
      // than unsaid, and a token someone has answered is a conversation now — the
      // reader's move is in the thread the answer opened. One standing on a resolved
      // thread paints nothing, so there is nothing to offer the press. The server
      // refuses the same three (undo_error), this being the offer and that the door.
      if (e.token) return e;
      // The approval, while it is the one the button is showing. Scoped the way
      // paintApproval scopes what it reads, because a reader on v3 taking back their
      // sign-off of v2 would be undoing a press whose result is nowhere on the page —
      // and the button is the whole of what says the press happened.
      if (
        e.kind === "done" &&
        e.revision === runtime.currentRevision &&
        e.version === runtime.currentStamp
      )
        return e;
      // On the version it was made against: a later version may have been written
      // around the decision, and a press that paints nothing is not one to offer. What
      // *hearing* such an undo owes is reconciliation's, and is not the same answer.
      const widget = e.kind === "action" && elementById(e.widget);
      if (
        widget &&
        (inChrome(widget) || e.revision === runtime.currentRevision) &&
        canUndoAction(candidate)
      )
        return e;
    }
    return null;
  }

  // A local Undo names an action rather than walking to the newest one, but it has
  // exactly the same authored-version and replayability boundary as the keyboard walk.
  function undoableAction(widget, action) {
    const candidate = (runtime.view?.undo ?? []).find(
      ({ event }) =>
        event.kind === "action" &&
        event.widget === widget.id &&
        event.action === action &&
        (inChrome(widget) || event.revision === runtime.currentRevision),
    );
    return candidate && canUndoAction(candidate) ? candidate.event : null;
  }

  // Said in the kinds this file owns, never in the verb the action carries: `move` and
  // `edit` read as nouns in that sentence and `choose` does not, and which of the two a
  // widget's word is is not core's to know. It is the same rule that keeps "accept" out
  // of the answer-all row's words, met here in its smallest form.
  const UNDO_WORDS = {
    resolve: "Reopened the thread",
    unresolve: "Resolved the thread again",
    action: "Took back your last change",
    done: "Took back your approval",
  };
  // A reaction's word is the token, which is the layer's word rather than a widget's
  // verb — read off the event, as the bar and the strip read it.
  const undoWord = (e) => (e.token ? `Took back your ${e.token}` : UNDO_WORDS[e.kind]);

  // This press's own record of being in flight, read by unaccountedGesture with the
  // layer's other two.

  // The press posts and nothing else. What the page does about it is reconciliation's,
  // where it is done once for every tab off the log rather than here for this one off
  // the gesture — the second tab has to arrive at the same page, and a route only this
  // tab took would be a second answer to converge with. The round trip is the cost, and
  // it is the one gesture that can afford it: a drag has to follow the pointer, where a
  // keypress has nothing on screen waiting on the frame.
  async function undoLast() {
    const e = undoable();
    if (e) await withdraw(e);
  }
  // Naming the gesture rather than walking to it: a standing mark is its own eraser — a
  // reaction's glyph in the margin, its pill on a strip — and a press there takes back
  // exactly that event, which need not be the newest. Same door, same notice.
  async function withdraw(e) {
    if (unaccountedGesture()) {
      notice("Wait for the current change to finish before undoing");
      return null;
    }
    runtime.undoing = true;
    paintKeys();
    try {
      const accepted = await post({ kind: "undo", undoes: e.id });
      if (accepted) notice(`${undoWord(e)} — recorded`);
      return accepted;
    } finally {
      runtime.undoing = false;
      paintKeys();
    }
  }

  // The widget put back as the version wrote it, for the withdrawal no state can state.
  // A rebuild rather than an un-apply, because there is no un-apply to call: applyAction
  // states a value, and the value here is "whatever the markup says", which only the
  // markup holds. The clone is this version's, taken before replay first touched the
  // page, so what goes back is exactly what a reload would render before the log is read
  // — and the log is then read onto it, the same pass that reads it onto a fresh load.
  function rebuild(el) {
    const id = el.id;
    // Whether the reader is standing in what is about to be replaced — inside it, or on
    // a control the widget hoisted out of it — because they have to be handed the place
    // back afterwards. The other route never asks: a widget told its state keeps its own
    // focus, and it was only the rebuild that dropped a reader onto <body> without a
    // word, which is the silence the ladder's own rung exists to avoid.
    const here = focused();
    const standing =
      Boolean(here) &&
      (containsAcross(el, here) ||
        Boolean(here.closest?.(`[${DECISION_ROW}="${id}"]`)));
    // Chrome the widget hoisted out of itself goes with it, and the widget is what takes
    // it: a control hung in the page margin is outside the subtree being replaced, so
    // only its owner knows to take it away, and disconnectedCallback is where the
    // platform already asks. Sweeping `[data-lf-for]` here as well would be a second
    // writer for one fact — and one that a widget hoisting chrome under some other
    // marker would silently escape anyway. What holds it is the render gate, where a row
    // left behind shows as two rows on one change.
    const fresh = authoredMarkup.get(id).cloneNode(true);
    // Before the insertion, as the load writes it before the modules import: a widget
    // that declares a width model or an inline run asks for it on its first render, and
    // connectedCallback is that render. The table is the place's: a rebuild reaches a
    // widget in a reply too — buildMsgBody remembers its markup the same way — and in
    // there the width half stays off for the reason that function gives, the room being
    // the panel's rather than the document's.
    markDeclared(fresh, inChrome(el) ? MARKED_ANYWHERE : MARKED_IN_PAGE);
    const settlingFrom = settling.length;
    el.replaceWith(fresh); // defined already, so connectedCallback runs on insertion
    // The rest of what the upgrade gives every subtree beyond its module's own work. Not
    // awaited as the upgrade awaits it: nothing is holding a first paint here, and a
    // widget with async work of its own settles it the way it always does. The scroller
    // sweep does wait, on what this insertion queued: the box a widget scrolls is one its
    // module builds, and swept before that build returns it is neither reachable nor
    // held (reach.js, on what every caller owes it).
    dress(fresh);
    Promise.allSettled(settling.slice(settlingFrom)).then(() => reachScrollers(fresh));
    // The fences the passage reading walks are node identities, and these are new nodes
    // holding the same markup — so the index is taken again rather than left naming a
    // subtree the page no longer has.
    rememberPassageParts();
    if (standing) standOn(fresh);
    return fresh;
  }

  const committedEvent = (commit) => commit?.entry?.e.id ?? null;

  function coordinateProjectionCommitted(projection, entry) {
    const desired = projection.desired.get(entry.coordinate);
    const commit = committedProjection.get(entry.coordinate);
    return (
      commit?.widget === elementById(entry.e.widget) &&
      commit.unit === elementById(entry.unit) &&
      committedEvent(commit) === (desired?.e.id ?? null)
    );
  }

  function projectionCommitted(projection, e) {
    const entry = projection.classified.get(e.id);
    if (!entry) return false;
    if (entry.terminal) return true;
    return coordinateProjectionCommitted(projection, entry);
  }

  function localCoordinateCommitted(projection, entry) {
    const local = entry.projection;
    if (!local) return true; // record-less actions never painted before acceptance
    const widget = elementById(local.e.widget);
    if (!widget) return true;
    const desired = projection.desired.get(local.coordinate) ?? null;
    const commit = committedProjection.get(local.coordinate);
    return (
      commit?.widget === widget &&
      commit.unit === elementById(local.unit) &&
      committedEvent(commit) === (desired?.e.id ?? null)
    );
  }

  // Delivery and projection are separate facts. Accepted entries leave only after a
  // complete read has committed the coordinate that now represents them; rejected
  // entries leave only after their optimistic token no longer represents the DOM.
  function releaseProjectedOutbox() {
    const projection = stateProjection();
    let removed = false;
    for (const entry of [...outbox]) {
      if (!entry.answered || entry.event.kind !== "action") continue;
      const settled = entry.rejected
        ? localCoordinateCommitted(projection, entry)
        : Boolean(entry.readEvent && projectionCommitted(projection, entry.readEvent));
      if (!settled) continue;
      removeOutbox(entry);
      removed = true;
    }
    return removed;
  }

  // Readiness remains event-counted even though painting is coordinate-based. Every
  // superseded action and absorbed report is settled when the one state that represents
  // its coordinate has been committed; an undo is settled by that same transition back
  // to a prior winner or the authored baseline.
  function projectionCoverage(projection) {
    let covered = 0;
    for (const record of runtime.view?.coverage ?? []) {
      if (record.coordinate === null) {
        covered += 1;
        continue;
      }
      const e = record.event;
      const target = projection.classified.get(e.kind === "undo" ? e.undoes : e.id);
      if (!target || target.terminal || projectionCommitted(projection, target.e))
        covered += 1;
    }
    return covered;
  }

  function rememberWrites(before, kind) {
    const now = shallowSigs(document.body);
    const changed = [...new Set([...before.keys(), ...now.keys()])].filter(
      (id) => before.get(id) !== now.get(id) && !inChrome(elementById(id)),
    );
    if (!changed.length) return;
    const attr =
      kind === "action"
        ? PAGE_PAINT_ATTRIBUTE.replayWrote
        : PAGE_PAINT_ATTRIBUTE.reportWrote;
    const prior = document.body.getAttribute(attr)?.split(" ") ?? [];
    document.body.setAttribute(attr, [...new Set([...prior, ...changed])].join(" "));
  }

  let projectionDragObserver = null;
  function watchProjectionDrag() {
    if (projectionDragObserver) return;
    projectionDragObserver = new MutationObserver(() => {
      if (document.querySelector(".lf-dragging")) return;
      projectionDragObserver.disconnect();
      projectionDragObserver = null;
      if (reconcileKnownState() && releaseProjectedOutbox()) paintKeys();
      document.dispatchEvent(new Event("lf-actions"));
    });
    projectionDragObserver.observe(document.body, {
      attributes: true,
      subtree: true,
      attributeFilter: ["class"],
    });
  }

  // Make the DOM equal the projection. A widget is the application boundary: if any of
  // its coordinates changed, all of its surviving winners are replayed in log order so
  // sibling units sharing an ordered container retain their collective placement.
  function reconcileState() {
    if (document.querySelector(".lf-dragging")) {
      watchProjectionDrag();
      return;
    }
    projectionDragObserver?.disconnect();
    projectionDragObserver = null;

    const started = [];
    let painted = false;
    let projection;
    const priorProjectionMode = runtime.projectingState;
    if (outbox.some((entry) => entry.rejected && entry.projection))
      runtime.projectingState = true;
    try {
      // A baseline no action detail can state replaces a subtree: a recordless verb, or
      // an optional authored scalar absent before its first action.
      for (;;) {
        projection = stateProjection();
        for (const entry of projection.classified.values())
          for (const id of entry.restated ?? [])
            elementById(id)?.setAttribute(PAGE_PAINT_ATTRIBUTE.restated, "1");

        for (const [coordinate, commit] of committedProjection)
          if (!elementById(commit.widgetId)) committedProjection.delete(coordinate);

        const coordinates = new Map();
        for (const entry of projection.classified.values())
          if (!entry.terminal) coordinates.set(entry.coordinate, entry);
        for (const [coordinate, entry] of projection.desired)
          if (!coordinates.has(coordinate)) coordinates.set(coordinate, entry);
        for (const [coordinate, commit] of committedProjection)
          if (!coordinates.has(coordinate)) coordinates.set(coordinate, commit.entry);

        const widgets = new Map();
        for (const [coordinate, sample] of coordinates) {
          if (!sample) continue;
          const widgetId = sample.e.widget;
          const widget = elementById(widgetId);
          if (!widget) continue;
          const desired = projection.desired.get(coordinate) ?? null;
          const commit = committedProjection.get(coordinate);
          const unit = elementById(sample.unit);
          const clean =
            commit?.widget === widget &&
            commit.unit === unit &&
            committedEvent(commit) === (desired?.e.id ?? null);
          const states = widgets.get(widgetId) ?? [];
          states.push({ coordinate, sample, desired, commit, clean });
          widgets.set(widgetId, states);
        }

        let rebuilt = false;
        for (const [widgetId, states] of widgets) {
          if (states.every((state) => state.clean)) continue;
          let widget = elementById(widgetId);
          if (!widget) continue;

          // A newly constructed thread widget or rebuilt descendant already carries its
          // authored baseline. A dirty recorded widget is reset whole below: its units
          // compose through shared containers, so restoring only one authored placement
          // would make its index relative to still-projected siblings.
          const removals = states.filter(
            ({ desired, commit }) =>
              !desired && commit?.entry && commit.widget === widget,
          );
          const markupOnly = removals.find(
            ({ coordinate, commit }) =>
              !commit.entry.spec.record ||
              (!authoredDetails.has(coordinate) && authoredMarkup.has(widgetId)),
          );
          if (markupOnly) {
            widget = rebuild(widget);
            committedProjection.set(markupOnly.coordinate, {
              widgetId,
              widget,
              unit: elementById(markupOnly.sample.unit),
              entry: null,
            });
            painted = true;
            rebuilt = true;
            break;
          }

          if (!widget.applyAction) {
            if (document.body.dataset.lfUpgraded !== "1") continue;
            for (const { commit } of removals)
              if (commit.entry.e.kind === "action")
                painted = clearSettled(widget, commit.entry.spec.facet) || painted;
            for (const { desired } of states) {
              if (desired?.e.kind !== "action") continue;
              const before = inChrome(widget) ? null : shallowSigs(document.body);
              if (!markSettled(widget, desired.e.action)) continue;
              if (before) rememberWrites(before, desired.e.kind);
              painted = true;
            }
          } else {
            let deferred = false;
            // Authored records are the zero point. Restore the widget's complete authored
            // composition before replaying every current winner in log/local order.
            for (const statement of authoredStatements.get(widgetId)?.values() ?? []) {
              widget = elementById(widgetId);
              if (!widget?.applyAction) {
                deferred = true;
                break;
              }
              const priorMotion = new Set(document.getAnimations());
              try {
                if (widget.applyAction(statement.action, statement.detail) === false)
                  deferred = true;
                else clearSettled(widget, statement.spec.facet);
              } catch (error) {
                reportPageError(
                  `<${widget.localName}> applyAction(${statement.action}) threw: ${error?.message ?? error}`,
                );
                failSoft(widget, error);
                clearSettled(widget, statement.spec.facet);
              }
              if (deferred) break;
              started.push(
                ...document
                  .getAnimations()
                  .filter((animation) => !priorMotion.has(animation)),
              );
              painted = true;
            }
            if (deferred) continue;

            const desired = states
              .map((state) => state.desired)
              .filter(Boolean)
              .sort(compareProjected);
            for (const entry of desired) {
              widget = elementById(widgetId);
              if (!widget?.applyAction) {
                deferred = true;
                break;
              }
              const before = inChrome(widget) ? null : shallowSigs(document.body);
              const priorMotion = new Set(document.getAnimations());
              try {
                if (
                  widget.applyAction(entry.e.action, entry.e.detail, entry.e) === false
                ) {
                  deferred = true;
                  break;
                }
                if (entry.e.kind === "action") markSettled(widget, entry.e.action);
              } catch (error) {
                reportPageError(
                  `<${widget.localName}> applyAction(${entry.e.action}) threw: ${error?.message ?? error}`,
                );
                failSoft(widget, error);
                if (entry.e.kind === "action") markSettled(widget, entry.e.action);
              }
              if (before) rememberWrites(before, entry.e.kind);
              started.push(
                ...document
                  .getAnimations()
                  .filter((animation) => !priorMotion.has(animation)),
              );
              painted = true;
            }
            if (deferred) continue;
          }

          widget = elementById(widgetId);
          if (!widget) continue;
          for (const { coordinate, sample } of states) {
            const desired = projection.desired.get(coordinate) ?? null;
            committedProjection.set(coordinate, {
              widgetId,
              widget,
              unit: elementById(sample.unit),
              entry: desired,
            });
          }
        }
        if (!rebuilt) break;
      }

      if (painted) {
        paintAnchors();
        Promise.allSettled(started.map((animation) => animation.finished)).then(() =>
          pageShifted(),
        );
      }
      renderQuiet(document.body);
      paintPending();
      projection = stateProjection();
      document.body.setAttribute(
        PAGE_PAINT_ATTRIBUTE.applied,
        String(projectionCoverage(projection)),
      );
    } finally {
      runtime.projectingState = priorProjectionMode;
    }
  }

  // `events` is installed before every other state surface renders, so a later throw can
  // leave it ahead of the last complete read. Only receiveState may project that candidate
  // while completing the read itself; every asynchronous wake-up must use either the
  // authored-only starting point or an event list whose whole state already committed.
  function reconcileKnownState() {
    const eventSeq = runtime.browser?.basis?.through_seq ?? 0;
    const complete = runtime.statePhase === "ready" && eventSeq <= runtime.lastEventSeq;
    const authoredOnly = runtime.lastEventSeq < 0 && eventSeq === 0;
    if (!complete && !authoredOnly) return false;
    reconcileState();
    paintAcknowledgments();
    return true;
  }

  // data-lf-pending: this element's decided state differs from what the version's
  // markup arrived showing — the record is behind the log. It clears when a
  // version carries the decision (the two agree again) or a retraction hands the
  // state back to the author. A decided suggestion has no record form to agree
  // with (honoring retires the wrapper), so it stays marked while the wrapper
  // stands.
  function paintPending() {
    const marks = new Map(
      [PAGE_PAINT_ATTRIBUTE.pending, PAGE_PAINT_ATTRIBUTE.reported].map((attr) => [
        attr,
        new Set(),
      ]),
    );
    const projection = stateProjection();
    for (const [coordinate, { unit, e, spec, value }] of projection.desired) {
      const el = elementById(unit);
      if (!el || inChrome(el)) continue;
      const behind = spec.record ? value !== authoredFacets.get(coordinate) : true;
      if (!behind) continue;
      // The channels keep separate marks so provisional worker news never wears
      // the reader's color. The desired projection chooses which channel owns a
      // coordinate; independent facets can still leave both marks on one unit.
      const attr =
        e.kind === "action"
          ? PAGE_PAINT_ATTRIBUTE.pending
          : PAGE_PAINT_ATTRIBUTE.reported;
      marks.get(attr).add(el);
    }
    for (const [attr, wanted] of marks) {
      for (const el of pageQueryAll(`[${attr}]`))
        if (!wanted.has(el)) el.removeAttribute(attr);
      for (const el of wanted)
        if (el.getAttribute(attr) !== "1") el.setAttribute(attr, "1");
    }
  }

  const projection = {
    authoredDetails,
    authoredFacets,
    authoredMarkup,
    authoredParents,
    authoredStatements,
    authoredWidgets,
    captureAuthoredFacets,
    committedProjection,
    coordinateProjectionCommitted,
    domFacet,
    markSettled,
    matchesProjectedWhen,
    paintPending,
    projectedFacet,
    projectionFromView,
    projectionCommitted,
    rebuild,
    reconcileKnownState,
    reconcileState,
    releaseProjectedOutbox,
    rememberAuthoredMarkup,
    resetAuthoredPage,
    requirementMatches,
    shallowSigs,
    stageOutboxAction,
    standingState,
    stateCoordinate,
    stateProjection,
    undoLast,
    undoable,
    undoableAction,
    unitOf,
    withdraw,
  };
  publishedProjection = projection;
  return projection;
}
