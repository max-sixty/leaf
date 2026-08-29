let publishedAskModel;
export const answeredContext = (...args) => publishedAskModel.answeredContext(...args);
export const askSource = (...args) => publishedAskModel.askSource(...args);
export const openAsks = (...args) => publishedAskModel.openAsks(...args);

/* Server-projected ask state, resolved onto the browser's live DOM. */
export function createAskModel({
  authoredParentOf,
  closestAcross,
  elementById,
  pagePresented,
  registry,
  runtime,
  stateProjection,
  tagsDeclaring,
}) {
  const askEntry = (el) => registry[el.tagName.toLowerCase()]?.["x-awaits"];
  const requestAskEntry = (el) => {
    const request = registry[el.tagName.toLowerCase()]?.["x-request"];
    return request?.ask ? request : null;
  };
  const askSourceEntry = (el) => askEntry(el) ?? requestAskEntry(el);
  const askTags = () =>
    tagsDeclaring((entry) => entry["x-awaits"] || entry["x-request"]?.ask);
  const askSurfaceTags = () => tagsDeclaring((entry) => entry["x-ask"]);

  function askSurface(el) {
    const tags = askSurfaceTags();
    return (tags.length && closestAcross(el, tags.join(","))) || el;
  }

  function askSource(el) {
    if (askSourceEntry(el)) return el;
    const tags = askTags();
    if (!tags.length || !registry[el.localName]?.["x-ask"]) return el;
    return (
      [...el.querySelectorAll(tags.join(","))].find(
        (candidate) => askSurface(candidate) === el,
      ) ?? el
    );
  }

  function positionedParents(projection) {
    const parents = new Map();
    for (const { unit, e, spec } of projection.desired.values()) {
      if (spec.record?.kind !== "position") continue;
      const parent = elementById(e.detail[spec.record.value]);
      const moved = elementById(unit);
      let holder = parent;
      while (holder && !registry[holder.localName])
        holder = authoredParentOf(holder) ?? holder.parentElement;
      if (
        parent &&
        moved &&
        holder &&
        (registry[moved.localName]?.["x-parent"] ?? []).includes(holder.localName)
      )
        parents.set(unit, parent);
    }
    return parents;
  }

  const awaitingValues = (answered) => ({
    ...(answered
      ? runtime.view?.document?.asks?.unanswered_awaiting
      : runtime.view?.document?.asks?.awaiting),
    ...(runtime.browser?.conversation?.asks?.awaiting ?? {}),
  });

  function context(answered = false) {
    const projection = stateProjection();
    return {
      awaiting: awaitingValues(answered),
      positionedParents: positionedParents(projection),
      projection,
    };
  }

  const answeredContext = () => context(true);
  const isAwaiting = (el, reading) => Boolean(reading.awaiting[el.id]);
  const projectedParent = (el, reading) =>
    (el.id && reading.positionedParents.get(el.id)) ??
    authoredParentOf(el) ??
    el.parentElement;

  function asks(kind) {
    if (!pagePresented()) return [];
    const documentAsks = runtime.view?.document?.asks?.[kind] ?? [];
    const conversationAsks = runtime.browser?.conversation?.asks?.[kind] ?? [];
    const elements = [...documentAsks, ...conversationAsks]
      .map((ask) => elementById(ask.id))
      .filter(Boolean);
    return [...new Set(elements)].sort((left, right) => {
      if (left === right) return 0;
      return left.compareDocumentPosition(right) & Node.DOCUMENT_POSITION_FOLLOWING
        ? -1
        : 1;
    });
  }

  // TODO(2026-08-28): Consider whether Decision is the clearer reader-facing name
  // for Ask. Rename this one category if so; do not add a parallel Decision category.
  const openAsks = () => asks("reader");
  const unansweredAsks = () => asks("unanswered");

  const model = {
    answeredContext,
    askEntry,
    askSource,
    isAwaiting,
    openAsks,
    projectedParent,
    unansweredAsks,
  };
  publishedAskModel = model;
  return model;
}
