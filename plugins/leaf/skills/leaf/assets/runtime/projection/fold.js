/* Canonical action and report state folded from the event log and local outbox. */
export function createProjectionFold(runtime, dependencies) {
  const {
    COLLAPSE,
    containsAcross,
    domFacet,
    elementById,
    inChrome,
    outbox,
    stateCoordinate,
    unitOf,
  } = dependencies;
  const { registry } = runtime;

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

  function compareProjected(a, b) {
    const aLogged = Number.isInteger(a.e.seq);
    const bLogged = Number.isInteger(b.e.seq);
    if (aLogged && bLogged) return a.e.seq - b.e.seq;
    if (aLogged) return -1;
    if (bLogged) return 1;
    return a.localOrder - b.localOrder;
  }

  const takenBack = () =>
    new Set(runtime.events.filter((e) => e.undoes).map((e) => e.undoes));

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

  return {
    compareProjected,
    foldedFacet,
    retractedIds,
    retractionFloors,
    standingState,
    stateProjection,
    takenBack,
  };
}
