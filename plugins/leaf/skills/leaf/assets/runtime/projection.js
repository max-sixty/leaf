import { createAuthoredProjection } from "./projection/authored.js";

/* Declaration-driven state projection and reconciliation. */
export function createProjection(runtime, dependencies) {
  const {
    ASK_ROW,
    COLLAPSE,
    MARKED_ANYWHERE,
    MARKED_IN_PAGE,
    PAGE_PAINT_ATTRIBUTE,
    PAGE_PAINT_ATTRIBUTES,
    agentName,
    askContext,
    askEntry,
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
    paintWorkLines,
    post,
    projectedParent,
    quoteFrom,
    reachScrollers,
    rememberPassageParts,
    removeOutbox,
    renderQuiet,
    renderRetired,
    reportPageError,
    settlementSlots,
    standOn,
    textNodesUnder,
    toast,
    widgetEntries,
  } = dependencies;
  const { registry } = runtime;

  // The DOM's one checkpoint: each semantic coordinate names the projected winner
  // painted there and the widget/unit nodes that held it. Event ids alone cannot prove
  // state survived a recordless rebuild or a thread reconcile; node identity can. A
  // coordinate with no winner is committed too, once its authored baseline stands.
  const committedProjection = new Map();
  // What an action rests on: the widget that sent it, and the parts of that widget
  // its detail names — a `move` rests on its card as much as on the board. Either
  // can be taken back, which is what lets a rewritten card drop its own moves while
  // the rest of the board stays where the user put it. Containment is the test,
  // not "the page has an element by that id", so a literal detail value can't
  // collide with an unrelated element that happens to be called the same thing.
  function restsOn(e, widget) {
    // flat(), because a detail field may name several elements at once (a group's
    // set of picks) and each of them is something the action rests on.
    const parts = Object.values(e.detail)
      .flat()
      .map((v) => (typeof v === "string" ? elementById(v) : null))
      .filter((el) => el && widget && containsAcross(widget, el))
      .map((el) => el.id);
    return [e.widget, ...parts];
  }
  // Which of those a later version took back. One spelling of the rule, because three
  // readings ask it — replay, the fold, and the thread list — and a decision standing in
  // one of them and retracted in another is the drift `restated` exists to prevent. The
  // ids rather than a boolean, since replay says so on the page (data-lf-restated) and
  // the other two only count them.
  //
  // A widget the page no longer holds answers for itself alone, which is what a version
  // honoring a decision leaves behind: the wrapper is retired, so there is nothing to ask
  // about containment and nothing that should read as a retraction — retirement is the
  // decision being carried out, not taken back. That is also the answer interact.py gives
  // without trying, reading a version file where the same element is simply absent.
  function retractedIds(e, floors, widget) {
    return restsOn(e, widget).filter((id) => (floors.get(id) ?? 0) > e.version);
  }
  // Retractions: a version that rewrote the words or state under a decision says
  // so with `restated`, and publishing records it on the note that released it.
  // Reading it from the log rather than from the markup is what makes it last —
  // the version *after* the rewrite declares nothing, and its silence would
  // otherwise hand the user's retracted state straight back.
  // Retractions and settlements are separate durable relations carried by the same
  // version note. `restated` retracts reader decisions; typed `settles` targets end
  // provisional agent facts without overloading a field name or an id namespace.
  // Memoized on the log's identity and the relation/window query: `events` has one writer,
  // which replaces the array wholesale (poll), so a cached answer cannot be stale and
  // every consumer shares the same filter-and-max fold.
  const noteFloorsMemo = new WeakMap();
  function noteFloors(relation, upto, idsOf) {
    let byQuery = noteFloorsMemo.get(runtime.events);
    if (!byQuery) noteFloorsMemo.set(runtime.events, (byQuery = new Map()));
    const query = `${relation}:${upto}`;
    if (byQuery.has(query)) return byQuery.get(query);
    const floors = new Map();
    for (const e of runtime.events)
      if (e.kind === "note" && e.version <= upto)
        for (const id of idsOf(e))
          floors.set(id, Math.max(floors.get(id) ?? 0, e.version));
    byQuery.set(query, floors);
    return floors;
  }
  const retractionFloors = (upto) =>
    noteFloors("retraction", upto, (e) => e.restated ?? []);
  // A report's end: the ids the notes in the window answered, absorbed or
  // overruled — the agent channel's mirror of retractionFloors, read from the
  // log for the same reason (the version after the answer declares nothing, and
  // its silence must not hand the report back).
  const settledReports = (upto) =>
    noteFloors("settlement:report", upto, (e) =>
      (e.settles ?? [])
        .filter((target) => target.kind === "report")
        .map((target) => target.id),
    );
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
    for (const el of [root, ...root.querySelectorAll("[id]")]) {
      if (!el.id) continue;
      const attrs = [...el.attributes]
        .filter((a) => !PAGE_PAINT_ATTRIBUTES.has(a.name))
        .map((a) => `${a.name}=${a.value}`)
        .sort()
        .join(" ");
      const kin = [...(el.parentElement?.children ?? [])].filter((c) => c.id);
      sigs.set(
        el.id,
        `${el.tagName} [${attrs}] in=${el.parentElement?.id ?? ""}#${kin.indexOf(el)}`,
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
    stateSpecs,
    unitOf,
  } = createAuthoredProjection({ quoteFrom, textNodesUnder, widgetEntries });

  // The state the folded action left, from the detail field the record declares,
  // collapsed the way the DOM reading collapses — its words where it is words,
  // its sorted ids where it is a set.
  function foldedFacet(e, record) {
    const value = e.detail[record.value];
    if (record.kind === "body")
      return String(value ?? "")
        .replace(COLLAPSE, " ")
        .trim();
    if (record.kind === "attribute") return [...value].sort().join(" ");
    return value ?? null;
  }

  // One canonical current reading for action admission as for replay: the latest desired
  // action/report at an owner-unit-facet coordinate, falling back to the version's
  // captured authored facet. A gesture may already have changed the live DOM before it
  // calls sendAction, so eligibility never reads that mutable rendering.
  function projectedFacet(
    widget,
    spec,
    winners = stateProjection(runtime.currentVersion).desired,
  ) {
    const coordinate = stateCoordinate(widget.id, widget.id, spec);
    const winner = winners.get(coordinate);
    return winner
      ? foldedFacet(winner.e, winner.spec.record)
      : authoredFacets.get(coordinate);
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
        return permitted.includes(node.localName) && askEntry(node) ? node : null;
    return null;
  }

  function requirementMatches(widget, spec) {
    if (!pagePresented()) return false;
    const requirement = spec.requires;
    const context = askContext();
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
    };
    entry.projection = projection;
    committedProjection.set(coordinate, {
      widgetId: e.widget,
      widget,
      unit: elementById(unit),
      entry: projection,
    });
  }

  function compareProjected(a, b) {
    const aLogged = Number.isInteger(a.e.seq);
    const bLogged = Number.isInteger(b.e.seq);
    if (aLogged && bLogged) return a.e.seq - b.e.seq;
    if (aLogged) return -1;
    if (bLogged) return 1;
    return a.localOrder - b.localOrder;
  }

  // Both durable channels projected in one pass. Actions holds the last surviving
  // reader action per coordinate. Reports keeps every live report because publishing
  // answers all of them there. Desired gives the reader's action precedence over
  // provisional agent news on the same fact.
  // The projection is deliberately pure and uncached: its declarations resolve through
  // the live DOM, which panel construction and a recordless rebuild can replace.
  function stateProjection(upto, without = null) {
    const floors = retractionFloors(upto);
    const withdrawn = takenBack();
    const settled = settledReports(upto);
    const actions = new Map();
    const reports = new Map();
    const classified = new Map();
    for (const e of runtime.events) {
      if (e.kind !== "action" && e.kind !== "report") continue;
      const el = elementById(e.widget);
      if (!el) {
        classified.set(e.id, { e, terminal: true });
        continue;
      }
      const chrome = inChrome(el);
      // Reply widgets live in frozen log markup and therefore see the whole action
      // sequence. Reports belong to versions, as do actions on page widgets.
      if (
        e.kind === "report" ? chrome || e.version > upto : !chrome && e.version > upto
      ) {
        classified.set(e.id, { e, terminal: true });
        continue;
      }
      const channel = e.kind === "action" ? "x-state" : "x-report";
      const spec = registry[el.tagName.toLowerCase()]?.[channel]?.[e.action];
      if (!spec) {
        classified.set(e.id, { e, terminal: true });
        continue;
      }
      const unit = unitOf(e, spec);
      if (typeof unit !== "string") {
        classified.set(e.id, { e, terminal: true });
        continue;
      }
      const coordinate = stateCoordinate(e.widget, unit, spec);
      const entry = { unit, e, spec, coordinate };
      classified.set(e.id, entry);
      if (e.kind === "action") {
        if (e.id === without || withdrawn.has(e.id)) continue;
        const restated = chrome ? [] : retractedIds(e, floors, el);
        entry.restated = restated;
        if (restated.length) continue;
        actions.set(coordinate, entry);
      } else if (!settled.has(e.id)) {
        const standing = reports.get(coordinate) ?? [];
        standing.push(entry);
        reports.set(coordinate, standing);
      }
    }
    // A retained accepted attempt already appears above at its true log position. Every
    // other surviving recorded action is newer local state, in the order the one outbox
    // will deliver it. Rejections are tombstones, not winners.
    const loggedAttempts = new Set(
      runtime.events.map((e) => e.attempt).filter(Boolean),
    );
    for (const out of outbox) {
      const entry = out.projection;
      if (!entry || out.rejected || loggedAttempts.has(out.event.attempt)) continue;
      actions.set(entry.coordinate, entry);
    }
    const desired = new Map(
      [...reports].map(([coordinate, standing]) => [coordinate, standing.at(-1)]),
    );
    for (const [coordinate, entry] of actions) desired.set(coordinate, entry);
    return {
      actions,
      reports,
      classified,
      desired,
    };
  }

  // What this page's folds hold, handed out so the one premise underneath them can
  // be tested from outside: every applyAction is absolute, and neither fold is a
  // fold if one isn't. `version check --render` applies each of these a second
  // time and asks what moved (RELATIVE_REPLAYS, in interact.py) — the page has
  // already replayed them, so a widget stating the whole value has nothing to do
  // and one stepping from what it reads moves again.
  //
  // Both channels, because both fold the same way: a report states an absolute
  // value exactly as an action does. The widget rather than the unit, because
  // applyAction is the widget's method and the detail is what names the part.
  //
  // In the log's own order, which is the whole of what makes re-applying them a
  // no-op. An absolute applyAction states its unit whole and says nothing about
  // any other, so where two units share an ordered container the page is the
  // *sequence's* result rather than any one action's: two cards dragged to the
  // head of one column leave it holding the second above the first, and replaying
  // the first alone lifts it back over the second. Neither implementation moved;
  // the reading did. A fold is keyed by coordinate and a Map keeps each key where it
  // first appeared, so the surviving events have to be put back in `seq` order
  // rather than taken as the fold hands them over.
  //
  // The widget and the facet are both read at the call rather than held, because
  // an application earlier in the batch is free to have replaced the element a
  // later one names. A unit the current version dropped has no facet at all —
  // its widget survived it.
  //
  // Every action this page holds, the panel's included. A widget an agent sent folds the
  // way a widget on the page does, and the poll replays its standing action over the state
  // that action already produced, exactly as it does for the page's — so the premise binds
  // it and the gate that tests the premise has to see it. A filter on `inChrome` stood here
  // and meant the one verb only a message can carry (`answer`, the Done press on a question
  // asked in a reply) was the one verb whose absoluteness nothing ever checked.
  //
  // Actions and not reports, though both channels come through here: a report has to be
  // answerable by a version and thread markup is frozen, so every door refuses one on a
  // widget an agent sent and the projection above marks any that reached the log terminal.
  const standingState = () => {
    const projection = stateProjection(runtime.currentVersion);
    return [...projection.desired]
      .sort(([, a], [, b]) => compareProjected(a, b))
      .map(([_coordinate, { unit, e, spec }]) => ({
        get widget() {
          return elementById(e.widget);
        },
        unit,
        facet: spec.facet,
        record: spec.record?.kind ?? null,
        action: e.action,
        detail: e.detail,
        read: () => {
          const el = spec.record && elementById(unit);
          return el ? domFacet(el, spec.record) : null;
        },
      }));
  };

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
  const takenBack = () =>
    new Set(runtime.events.filter((e) => e.undoes).map((e) => e.undoes));
  // Whether removing one action leaves the reconciler a state it can paint. The actual
  // transition belongs to reconciliation; this is only the keyboard offer, bounded to
  // the version where the gesture was made.
  function canUndoAction(e) {
    const el = elementById(e.widget);
    if (!el || !el.applyAction) return false;
    const spec = registry[el.tagName.toLowerCase()]?.["x-state"]?.[e.action];
    if (!spec) return false;
    if (!spec.record) return authoredMarkup.has(e.widget);
    const unit = unitOf(e, spec);
    const coordinate = stateCoordinate(e.widget, unit, spec);
    return (
      stateProjection(runtime.currentVersion, e.id).desired.has(coordinate) ||
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
    const withdrawn = takenBack();
    for (let i = runtime.events.length - 1; i >= 0; i--) {
      const e = runtime.events[i];
      if (e.author !== "user" || e.kind === "undo" || withdrawn.has(e.id)) continue;
      if (e.kind === "resolve" || e.kind === "unresolve") return e;
      // On the version it was made against: a later version may have been written
      // around the decision, and a press that paints nothing is not one to offer. What
      // *hearing* such an undo owes is reconciliation's, and is not the same answer.
      const widget = e.kind === "action" && elementById(e.widget);
      if (
        widget &&
        (inChrome(widget) || e.version === runtime.currentVersion) &&
        canUndoAction(e)
      )
        return e;
    }
    return null;
  }

  // Said in the kinds this file owns, never in the verb the action carries: `move` and
  // `edit` read as nouns in that sentence and `choose` does not, and which of the two a
  // widget's word is is not core's to know. It is the same rule that keeps "accept" out
  // of the answer-all row's words, met here in its smallest form.
  const UNDO_WORDS = {
    resolve: "Reopened the thread",
    unresolve: "Resolved the thread again",
    action: "Took back your last change",
  };

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
    if (!e) return;
    runtime.undoing = true;
    paintKeys();
    try {
      if (await post({ kind: "undo", undoes: e.id }))
        toast(`${UNDO_WORDS[e.kind]} — sent to ${agentName()}`);
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
      (containsAcross(el, here) || Boolean(here.closest?.(`[${ASK_ROW}="${id}"]`)));
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
    el.replaceWith(fresh); // defined already, so connectedCallback runs on insertion
    // The rest of what the upgrade gives every subtree beyond its module's own work. Not
    // awaited as the upgrade awaits it: nothing is holding a first paint here, and a
    // widget with async work of its own settles it the way it always does.
    dress(fresh);
    reachScrollers(fresh);
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
    const projection = stateProjection(runtime.currentVersion);
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
    for (const e of runtime.events) {
      if (e.kind === "action" || e.kind === "report") {
        if (projectionCommitted(projection, e)) covered += 1;
      } else if (e.kind === "undo") {
        const target = projection.classified.get(e.undoes);
        if (!target || target.terminal || projectionCommitted(projection, target.e))
          covered += 1;
      }
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
        projection = stateProjection(runtime.currentVersion);
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
      projection = stateProjection(runtime.currentVersion);
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
    const eventSeq = runtime.events.at(-1)?.seq ?? 0;
    const complete = runtime.statePhase === "ready" && eventSeq <= runtime.lastEventSeq;
    const authoredOnly = runtime.lastEventSeq < 0 && runtime.events.length === 0;
    if (!complete && !authoredOnly) return false;
    reconcileState();
    paintWorkLines();
    return true;
  }

  // data-lf-pending: this element's decided state differs from what the version's
  // markup arrived showing — the record is behind the log. It clears when a
  // version carries the decision (the two agree again) or a retraction hands the
  // state back to the author. A decided suggestion has no record form to agree
  // with (honoring retires the wrapper), so it stays marked while the wrapper
  // stands.
  function paintPending() {
    for (const attr of [PAGE_PAINT_ATTRIBUTE.pending, PAGE_PAINT_ATTRIBUTE.reported])
      for (const el of pageQueryAll(`[${attr}]`)) el.removeAttribute(attr);
    const projection = stateProjection(runtime.currentVersion);
    for (const [coordinate, { unit, e, spec }] of projection.desired) {
      const el = elementById(unit);
      if (!el || inChrome(el)) continue;
      const behind = spec.record
        ? foldedFacet(e, spec.record) !== authoredFacets.get(coordinate)
        : true;
      if (!behind) continue;
      // The channels keep separate marks so provisional worker news never wears
      // the reader's color. The desired projection chooses which channel owns a
      // coordinate; independent facets can still leave both marks on one unit.
      const attr =
        e.kind === "action"
          ? PAGE_PAINT_ATTRIBUTE.pending
          : PAGE_PAINT_ATTRIBUTE.reported;
      el.setAttribute(attr, "1");
    }
  }

  return {
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
    foldedFacet,
    markSettled,
    matchesProjectedWhen,
    paintPending,
    projectedFacet,
    projectionCommitted,
    rebuild,
    reconcileKnownState,
    reconcileState,
    releaseProjectedOutbox,
    rememberAuthoredMarkup,
    requirementMatches,
    retractedIds,
    retractionFloors,
    shallowSigs,
    stageOutboxAction,
    standingState,
    stateCoordinate,
    stateProjection,
    stateSpecs,
    takenBack,
    undoLast,
    undoable,
    unitOf,
  };
}
