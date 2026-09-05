import { createAuthoredProjection } from "./projection/authored.js";
import { createProjectionFold } from "./projection/fold.js";
import { stateSpecs } from "./registry.js";

let publishedProjection;
export const shallowSigs = (...args) => publishedProjection.shallowSigs(...args);
export const standingState = (...args) => publishedProjection.standingState(...args);
export const withdraw = (...args) => publishedProjection.withdraw(...args);
export const undoableAction = (...args) => publishedProjection.undoableAction(...args);

/* Declaration-driven state projection and reconciliation: the DOM's one checkpoint of
   what it represents, the optimistic overlay of unresolved gestures, the reconciliation
   every complete state goes through, and undo.

   A recorded action may be optimistic because its gesture has already changed the DOM.
   Drag and edit are examples. `stageOutboxAction` gives that local value the same
   semantic coordinate as the server view and commits it on the exact widget and unit
   nodes that carry it. The browser projection adapter overlays all surviving recorded
   outbox actions after authoritative winners in `outboxOrder`. Until a complete read
   accounts for an attempt, its local winner outranks any older log winner on the same
   coordinate.

   `committedProjection` is not a second state authority. It is a checkpoint of what node
   identities and semantic winner the DOM currently represents. Each entry records the
   widget node, unit node, and projected entry for one coordinate. Node identity matters
   because a revision activation or thread reconciliation may replace a node without
   changing an event id. A coordinate with no winner is committed when its authored
   baseline stands.

   `projectionCommitted` compares the desired coordinate with that checkpoint. Terminal
   events count as committed because this version has no applicable state to paint. The
   server supplies coverage records and `projectionCoverage` checks their coordinates
   against DOM commits for `data-lf-applied`: superseded actions and answered reports are
   covered when the coordinate that represents them is committed, and an undo is covered
   when its target's coordinate has moved to the prior winner or authored baseline.

   `reconcileKnownState` protects the wakeups that follow a state application — focus,
   undo, draft settlement, and later asynchronous work (state-application.js). It permits
   reconciliation only from the last complete sequence, or from the authored-only initial
   state before any events have been installed. A read that brought nothing is allowed
   to retry a deferred correction against that known state. It must not project a newer
   candidate whose surrounding render failed.

   `reconcileState` delivers one complete facet map through `renderState(state)`.
   `widgetStates` starts with typed authored values, overlays the server's desired
   winners and unresolved local gestures, and composes ordered containers entirely in
   memory. No reset actions, baseline replay, or cloned subtree reconstruction occur.

   Each widget facet has `{action, value, detail}`. `action` is the winning verb, or
   `null` for authored state. `value` is the typed record value, or the winning verb
   (with `null` meaning undecided) for a recordless facet. `detail` preserves the winning
   event's detail, including generated child labels; the authored detail contains the
   declared record field. A facet with a non-widget unit has `units`, mapping each
   standing unit to that same facet shape. Its `value` maps container ids to complete
   ordered id lists for a position record, and is an empty object for recordless units.
   Missing recordless units are undecided. Widget-absolute position records retain their
   containing id as `value` and their final index in the declared detail field; ordering
   across those owners is composed together.

   Render every declared facet, including null/empty values, while retaining the widget
   and independent child widgets. Repeating a complete state must change nothing. Return
   `false` only while a live gesture prevents safe rendering; the coordinate and outbox
   hold stay uncommitted until a later wakeup. A widget ending that gesture dispatches
   `lf-projection` on `document`; the state feed coalesces retries into a microtask so
   the gesture stages its local action before correction runs. Throwing reports a page
   error and fails soft; the layer still renders declared settlement marks. `renderState`
   writes only attributes represented by declared record forms on authored elements;
   generated chrome may use platform attributes and `data-*` state. Returning success
   while writing undeclared author-namespace attributes breaks the file/DOM comparison.

   `watchProjectionDrag` waits for the last `.lf-dragging` marker to clear, then
   reconciles, releases eligible outbox entries, repaints keys, and dispatches
   `lf-actions`. Do not let a read or the heartbeat fight the pointer by applying
   projection during a drag.

   `shallowSigs` reads authored tags, individual attributes, and placement. The render
   gate temporarily renders the authored state and surviving decisions from earlier
   revisions, intersects their writes with the author's changed facts, then restores
   current state. New actions on this revision cannot contradict its authoring. No
   per-render DOM write history is kept. Text has the passage and restatement checks.

   An `undo` event names the event it withdraws. Every fold drops that gesture (Python's
   `taken_back`, the browser's `withdraw`); the log stays append-only. `undoable` walks
   the whole authoritative log newest first, selects a standing user gesture, and offers
   an action only on the version where that action was made. Thread resolution is not
   version-scoped. Undo has no tab-local stack.

   `canUndoAction` requires a mounted authored owner with a complete renderer or generic
   retirement semantics. Undo selects a different complete projection; the same renderer
   handles it without replacing the owner, its independent children, or their controls.

   `renderSettlement` and `renderRetired` are layer responsibilities. The registry's
   `x-parent` and `x-retired-when` declarations identify the holder and slots; the
   complete facet's winning action paints the outcome, and its null baseline clears it. A
   module may render the same marks as part of its animation choreography.

   `paintStateOrigins` compares each desired record with its authored facet. It paints
   `data-lf-reader-override` for reader actions and `data-lf-reported` for reports only
   while the log differs from this version's authored state. Recordless decisions retain
   the reader-origin mark while their holder remains in the document. These marks
   describe origin, not unfinished work; receipts own processing and completion. They are
   renderings of the projection, never inputs to it.

   `shallowSigs` excludes exactly those attributes and reads only id-bearing elements
   accepted by the bounded `authored` predicate. Generated elements are absent; generated
   parents and siblings contribute neither the `in=` id nor sibling position. An authored
   widget inside conversation chrome remains visible because its widget frame bounds that
   predicate. A widget's own `data-lf-*` state remains visible to replay and to the
   render gate. */
export function createProjection(runtime, dependencies) {
  const {
    COLLAPSE,
    PAGE_PAINT_ATTRIBUTE,
    PAGE_PAINT_ATTRIBUTES,
    answeredContext,
    authored,
    decisionEntry,
    elementById,
    failSoft,
    inChrome,
    isAwaiting,
    outbox,
    pagePresented,
    pageQueryAll,
    pageShifted,
    paintKeys,
    post,
    projectedParent,
    quoteFrom,
    removeOutbox,
    reconcileThreads,
    renderQuiet,
    renderRetired,
    reportPageError,
    settlementSlots,
    textNodesUnder,
    notice,
    unaccountedGesture,
  } = dependencies;
  const { registry } = runtime;

  // The DOM's one checkpoint: each semantic coordinate names the projected winner
  // painted there and the widget/unit nodes that held it. Event ids alone cannot prove
  // state survived a revision activation or a thread reconcile; node identity can. A
  // coordinate with no winner is committed too, once its authored baseline stands.
  const committedProjection = new Map();
  // Stable, structured signatures of authored tag, attributes and placement.
  // Generated chrome and runtime paint are absent. The render gate compares the
  // same facts in source documents and in the DOM; text has its own reading.
  function shallowSigs(root) {
    const sigs = new Map();
    const siblingPositions = new Map();
    const isAuthored = (el) => Boolean(el.id) && authored(el)(el);
    for (const el of [root, ...root.querySelectorAll("[id]")]) {
      if (!isAuthored(el)) continue;
      const attrs = Object.fromEntries(
        [...el.attributes]
          .filter((a) => !PAGE_PAINT_ATTRIBUTES.has(a.name))
          .map((a) => [a.name, a.value])
          .sort(([a], [b]) => a.localeCompare(b)),
      );
      const parent = el.parentElement;
      let positions = siblingPositions.get(parent);
      if (!positions) {
        positions = new Map();
        for (const sibling of parent?.children ?? [])
          if (isAuthored(sibling)) positions.set(sibling, positions.size);
        siblingPositions.set(parent, positions);
      }
      sigs.set(
        el.id,
        JSON.stringify({
          tag: el.tagName,
          attrs,
          parent: parent && isAuthored(parent) ? parent.id : "",
          index: positions.get(el) ?? -1,
        }),
      );
    }
    return sigs;
  }
  // Settlement is a total facet too: the null baseline withdraws every mark.
  // The registry owns retirement even when a content element needs no renderer.
  function renderSettlement(widget, state) {
    const outcomes = settlementSlots()[widget.localName];
    if (!outcomes) return;
    const spec = registry[widget.localName]["x-state"][Object.keys(outcomes)[0]];
    const outcome = state[spec.facet].action;
    if (outcomes[outcome]) widget.setAttribute("data-lf-state", outcome);
    else widget.removeAttribute("data-lf-state");
    renderRetired(widget);
  }
  const {
    authoredStates,
    authoredParents,
    authoredFacet,
    captureAuthoredFacets,
    domFacet,
    rememberAuthoredParents,
    stateCoordinate,
    unitOf,
  } = createAuthoredProjection({ COLLAPSE, quoteFrom, textNodesUnder });
  const committedWidgets = new Map();

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
    dropCoordinates(committedProjection);
    for (const owner of pageOwners) {
      authoredStates.delete(owner);
      committedWidgets.delete(owner);
    }
    document.body.removeAttribute(PAGE_PAINT_ATTRIBUTE.applied);
  }

  const {
    foldedFacet,
    projectionFromView,
    standingState,
    stateProjection,
    widgetStates,
  } = createProjectionFold(runtime, {
    COLLAPSE,
    authoredStates,
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
    return winner ? winner.value : authoredFacet(coordinate);
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
    committedWidgets.delete(e.widget);
    committedProjection.set(coordinate, {
      widgetId: e.widget,
      widget,
      unit: elementById(unit),
      entry: projection,
    });
  }

  // Undo withdraws a gesture; complete projection supplies the resulting state,
  // including undecided and absent values. It never needs an inverse event.
  function canUndoAction(candidate) {
    const widget = elementById(candidate.event.widget);
    return Boolean(
      widget &&
      authoredStates.has(widget.id) &&
      (widget.renderState || settlementSlots()[widget.localName]),
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
      if (accepted) notice(`${undoWord(e)} — sent`);
      return accepted;
    } finally {
      runtime.undoing = false;
      paintKeys();
    }
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

  // Each owner sees one complete desired composition. Baselines and winners are
  // folded before this boundary; renderers never reset, replay or replace widgets.
  let deferredProjection = false;
  const projectionDeferred = () => deferredProjection;

  function reconcileState() {
    deferredProjection = false;
    if (document.querySelector(".lf-dragging")) {
      deferredProjection = true;
      watchProjectionDrag();
      return;
    }
    projectionDragObserver?.disconnect();
    projectionDragObserver = null;
    const projection = stateProjection();
    const priorProjectionMode = runtime.projectingState;
    if (outbox.some((entry) => entry.rejected && entry.projection))
      runtime.projectingState = true;
    let painted = false;
    const started = new Set(document.getAnimations());
    try {
      for (const entry of projection.classified.values())
        for (const id of entry.restated ?? [])
          elementById(id)?.setAttribute(PAGE_PAINT_ATTRIBUTE.restated, "1");
      const states = widgetStates(projection);
      for (const [widgetId, { state, entries }] of states) {
        const widget = elementById(widgetId);
        if (!widget) continue;
        const key = JSON.stringify(state);
        const commit = committedWidgets.get(widgetId);
        const unitsChanged = entries.some(
          ({ coordinate, unit }) =>
            committedProjection.get(coordinate)?.unit !== elementById(unit),
        );
        if (commit?.widget !== widget || commit.key !== key || unitsChanged) {
          try {
            if (widget.renderState?.(state) === false) {
              deferredProjection = true;
              continue;
            }
            renderSettlement(widget, state);
          } catch (error) {
            reportPageError(
              `<${widget.localName}> renderState threw: ${error?.message ?? error}`,
            );
            failSoft(widget, error);
            renderSettlement(widget, state);
          }
          committedWidgets.set(widgetId, { widget, key });
          painted = true;
        }
        const coordinates = new Map();
        for (const entry of projection.classified.values())
          if (!entry.terminal && entry.e.widget === widgetId)
            coordinates.set(entry.coordinate, entry);
        for (const entry of entries) coordinates.set(entry.coordinate, entry);
        for (const [coordinate, commit] of committedProjection)
          if (commit.widgetId === widgetId && commit.entry)
            coordinates.set(coordinate, commit.entry);
        for (const [coordinate, sample] of coordinates)
          committedProjection.set(coordinate, {
            widgetId,
            widget,
            unit: elementById(sample.unit),
            entry: projection.desired.get(coordinate) ?? null,
          });
      }
      for (const [coordinate, commit] of committedProjection)
        if (!elementById(commit.widgetId)) committedProjection.delete(coordinate);
      if (painted) {
        reconcileThreads();
        Promise.allSettled(
          document
            .getAnimations()
            .filter((animation) => !started.has(animation))
            .map((animation) => animation.finished),
        ).then(() => pageShifted());
      }
      renderQuiet(document.body);
      paintStateOrigins(projection);
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
    reconcileThreads();
    return true;
  }

  // Mark effective state supplied by the log instead of authored markup. These
  // outlines describe its origin; processing and completion belong to work
  // receipts. A decided suggestion remains reader-owned while its wrapper stands.
  function paintStateOrigins(projection) {
    const marks = new Map(
      [PAGE_PAINT_ATTRIBUTE.readerOverride, PAGE_PAINT_ATTRIBUTE.reported].map(
        (attr) => [attr, new Set()],
      ),
    );
    for (const [coordinate, { unit, e, spec, value }] of projection.desired) {
      const el = elementById(unit);
      if (!el || inChrome(el)) continue;
      const overridesSource = spec.record ? value !== authoredFacet(coordinate) : true;
      if (!overridesSource) continue;
      // The channels keep separate marks so provisional worker news never wears
      // the reader's color. The desired projection chooses which channel owns a
      // coordinate; independent facets can still leave both marks on one unit.
      const attr =
        e.kind === "action"
          ? PAGE_PAINT_ATTRIBUTE.readerOverride
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
    authoredParents,
    captureAuthoredFacets,
    committedProjection,
    coordinateProjectionCommitted,
    domFacet,
    matchesProjectedWhen,
    paintStateOrigins,
    projectedFacet,
    projectionFromView,
    projectionDeferred,
    projectionCommitted,
    reconcileKnownState,
    reconcileState,
    releaseProjectedOutbox,
    rememberAuthoredParents,
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
