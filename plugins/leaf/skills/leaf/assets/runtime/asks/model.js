export function createAskModel({
  authoredParentOf,
  awaitsAgent,
  buildThreads,
  closestAcross,
  elementById,
  inChrome,
  matchesProjectedWhen,
  matchesWhen,
  pagePresented,
  projectedFacet,
  quoted,
  registry,
  runtime,
  seatRoot,
  settledAway,
  stateCoordinate,
  stateProjection,
  tagsDeclaring,
}) {
  // ---------- the ask, collected ----------
  // An ask is a standing request to the reader: a question with no pick on it, a change
  // nobody has decided, a piece of work the page says is waiting on them. Which widgets
  // can source one is the registry's answer (x-awaits); x-ask may give that source a
  // broader reading and arrival surface. Nothing out here names a tag —
  // the banner's count, the n/p walk, and the "?" overlay's row are three readings of this
  // one list, so what the banner counts and what the key steps to cannot disagree. The
  // count used to be a query for `lf-suggestion:not([data-lf-state])`, which was
  // perfect for suggestions and silently blind to every other thing a page asks.
  //
  // Both halves of "unanswered" were already written down. Asking is the entry's own
  // condition over the element's attributes: a group takes picks only with `choose` and
  // stops asking once it is `settled`, a task waits only at `review` or `blocked`. And
  // answered is the state of one of x-awaits' explicit answer verbs. An attribute record
  // lets authored markup honor a pick and lets clearing it reopen the ask; another named
  // verb answers through its surviving fold entry. Verbs not named there are orthogonal
  // state, so moving a deadline cannot silently answer the decision it postpones.
  const askEntry = (el) => registry[el.tagName.toLowerCase()]?.["x-awaits"];
  // A request may begin before the widget that records its answer. x-ask gives that
  // complete reading one authored region: the heading, context and evidence above the
  // control travel with it, while the nested x-awaits widget remains the state owner.
  // Both directions are structural and declaration-driven, so a custom region and a
  // custom request join without core naming either tag. `version check` holds each region
  // to one nested source, which makes askSource's answer unambiguous.
  const askSurfaceTags = () => tagsDeclaring((entry) => entry["x-ask"]);
  function askSurface(el) {
    const tags = askSurfaceTags();
    return (tags.length && closestAcross(el, tags.join(","))) || el;
  }
  function askSource(el) {
    if (askEntry(el)) return el;
    const tags = askTags();
    if (!tags.length || !registry[el.localName]?.["x-ask"]) return el;
    return (
      [...el.querySelectorAll(tags.join(","))].find(
        (candidate) => askSurface(candidate) === el,
      ) ?? el
    );
  }
  // Every declared attribute holding one of the values that ask — a flag's two values
  // being its presence and its absence, since it carries none of its own.
  function answeredAsk(el, projection) {
    const entry = registry[el.tagName.toLowerCase()];
    const verbs = entry["x-awaits"].answers ?? [];
    // The fold holds one entry per facet and unit, so a recordless verb is
    // answered only by an entry that is actually its own — a `choose` surviving in
    // the selection facet says nothing about `answer`'s completion facet, and a
    // cleared pick must ask again.
    return verbs.some((verb) => {
      const spec = entry["x-state"][verb];
      return ["attribute", "value"].includes(spec.record?.kind)
        ? ![null, ""].includes(projectedFacet(el, spec, projection.actions))
        : projection.actions.get(stateCoordinate(el.id, el.id, spec))?.e.action ===
            verb;
    });
  }
  const askTags = () => tagsDeclaring((entry) => entry["x-awaits"]);

  function askContext(projection = stateProjection(runtime.currentVersion)) {
    const positionedParents = new Map();
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
        positionedParents.set(unit, parent);
    }
    const threads = buildThreads();
    return {
      projection,
      positionedParents,
      settled: new Set(
        threads.filter((thread) => thread.resolved).map((thread) => thread.root.id),
      ),
      // The widgets whose own seat holds a conversation now waiting on the agent. What
      // makes this the reader's-list reading, and what `answeredContext` takes back out.
      seatsWithAgent: new Set(
        threads
          .filter((thread) => awaitsAgent(thread))
          .map((thread) => seatRoot(thread))
          .filter(Boolean),
      ),
    };
  }

  // The same reducer asked the other question: whether a request is answered, rather than
  // whether it is the reader's to deal with. `seatsWithAgent` is the entire difference
  // between the two contexts, so emptying it is the entire difference here. Every reading
  // built on either context rests on that being true of the whole shape: a second member
  // derived from those same conversations would pass through this spread untouched and
  // reach both callers unemptied, so derive one only by widening this function to empty it
  // too. Stated here rather than by a caller writing the spread inline, so the two answers
  // cannot drift apart.
  //
  // Three callers ask it. An action's `requires`: a conversation does not answer a
  // question the widget holds no state for, and refusing a pick over the reader's own
  // remark would refuse them the answer they were asked for. The version-response resolve
  // gate asks the same projection on the file side. And `unansweredAsks`, for where the
  // reader is standing: the ring and `c`'s destination say what they are working, not what
  // they owe.
  function answeredContext(projection) {
    return { ...askContext(projection), seatsWithAgent: new Set() };
  }

  function askExists(el, context) {
    if (quoted(el) || settledAway(el)) return false;
    const thread = closestAcross(el, ".lf-thread, .lf-going");
    return !thread || !context.settled.has(thread.dataset.id);
  }

  function projectedParent(el, context) {
    return (
      (el.id && context.positionedParents.get(el.id)) ??
      authoredParentOf(el) ??
      el.parentElement
    );
  }

  function nearestRollup(el, context) {
    for (
      let node = projectedParent(el, context);
      node;
      node = projectedParent(node, context)
    )
      if (askEntry(node)?.rollup) return node;
    return null;
  }

  function projectedContains(ancestor, el, context) {
    for (let node = el; node; node = projectedParent(node, context))
      if (node === ancestor) return true;
    return false;
  }

  function locallyAsks(el, context) {
    return (
      askExists(el, context) &&
      matchesProjectedWhen(el, askEntry(el).when, context.projection)
    );
  }

  // A conversation standing in this widget's own seat, with the agent. Declaration-driven
  // at both ends: a widget with no x-conversation offers no seat, and one whose attributes
  // miss the predicate has none placed on this instance either — so an element anchor
  // written onto some other widget by `leaf comment` reaches nothing here.
  // `conversationBox` asks the same question of the same declaration when it places the
  // box, so the cell the reader can see and the request this takes off their list are the
  // same one. It reads the live attributes because that is what the placement read; the
  // registry refuses a record-written attribute in this predicate, which is what keeps the
  // two from drifting as the log replays.
  //
  // Whose thread it is does not enter into it. The agent may open one in the seat too, and
  // once the reader has answered there the question is with the agent either way — which is
  // the only thing this is claiming.
  function seatWithAgent(el, context) {
    const declaration = registry[el.localName]?.["x-conversation"];
    return Boolean(
      declaration &&
      matchesWhen(el, declaration.when) &&
      context.seatsWithAgent.has(el.id),
    );
  }

  // Whether a request is still one the reader has to deal with. Two things take it off
  // their hands, and only one of them is an answer.
  //
  // A state verb answers it outright. A conversation standing in the widget's own seat does
  // not — the group holds no pick and its controls still offer one — but while that
  // conversation is with the agent the request is not the reader's to act on, and saying it
  // is asked them a second time for what they had just written, in a box the page itself
  // put under the question. That was the panel and the banner telling one fact two ways.
  //
  // So this is the reader's-list reading, and it is what the banner, the asks tray and the
  // `n`/`p` walk want. Three readings want the other one — whether the request is answered
  // at all — and all say so by asking with no seats in their context. An action's
  // `requires` is one: a pick refused because the reader had remarked on the question would
  // be refusing them the very answer they were asked for. The file-side version-response
  // resolve gate is another. Where the reader is standing is the third (`unansweredAsks`),
  // because standing in a question is what the reader is working and not what they owe.
  //
  // An ordinary reply or resolve hands the conversation back. A version-response
  // conversation takes no reply. Its originating request must become answered; if it was
  // already answered, the later version must instead change the declared answer record.
  // A seat answer that held for good would let a clarifying question retire a decision
  // nobody made, invisibly to both sides, which is what the log's own defaults exist to
  // refuse.
  //
  // Frozen thread markup seats no conversation of its own — `conversationBox` declines a
  // widget standing inside a thread, whose reply box is already that seat — so this reaches
  // only the page's widgets, which is exactly where there is a box to answer in.
  function asksTheReader(el, context) {
    return inChrome(el)
      ? !answeredThreadAsk(el, context.projection)
      : !answeredAsk(el, context.projection) && !seatWithAgent(el, context);
  }

  // The ordinary case is one local request. A roll-up is the same request projected
  // through a nested plan: a non-requesting node stops the walk; direct interventions
  // take precedence; otherwise child roll-ups recurse; a leaf
  // that matches its condition waits. Every relation is discovered from x-awaits, so
  // a custom goal and a custom intervention join without a tag branch.
  function isAwaiting(el, context) {
    if (!askExists(el, context)) return false;
    if (!matchesProjectedWhen(el, askEntry(el).when, context.projection)) return false;
    const entry = askEntry(el);
    if (!entry.rollup) return asksTheReader(el, context);

    const tags = askTags();
    const direct = tags.length
      ? [...document.querySelectorAll(tags.join(","))].filter(
          (candidate) => candidate !== el && nearestRollup(candidate, context) === el,
        )
      : [];
    const interventions = direct.filter(
      (candidate) => !askEntry(candidate).rollup && locallyAsks(candidate, context),
    );
    if (interventions.length)
      return interventions.some((candidate) => isAwaiting(candidate, context));
    const children = direct.filter((candidate) => askEntry(candidate).rollup);
    if (children.length)
      return children.some((candidate) => isAwaiting(candidate, context));
    return asksTheReader(el, context);
  }

  // The reader's list: the requests still theirs to deal with, which is what the banner,
  // the asks tray and the `n`/`p` walk follow. The panel's count is a different fact —
  // threads open, not answers owed.
  function openAsks() {
    return asksIn(askContext);
  }
  // The same list read for the other question, the one `answeredContext` states: which
  // requests nothing has answered, rather than which are the reader's to deal with. A
  // widget whose seat holds a conversation with the agent is on this list and off the
  // other, its controls live and its answer unmade. `standingIn` is its reader: where the
  // reader is standing is not what the reader owes.
  function unansweredAsks() {
    return asksIn(answeredContext);
  }
  // What either question comes to on the page, the context saying which — the shape the
  // rest of this file already takes, `askExists`, `asksTheReader` and `isAwaiting` all
  // taking one, and `openAsks` the one member that built its own.
  //
  // In document order, because that is the order the page asks them in and the order the
  // reader walks — the chrome container sits after the page's blocks, so a thread's
  // question queues behind the page's own. Quoted material asks nothing (an exhibited
  // decision is a mention). A widget in a thread asks like one on the page: a question is a
  // request to the reader wherever it stands.
  //
  // The context arrives as the reader of one rather than one already built: both are
  // uncached full passes over the log, and the two guards below exist to skip exactly that
  // work. An argument is evaluated before the call, so a built context paid for both folds
  // on every early return — once per painted frame through the whole pre-presentation
  // window, where the answer is `[]` either way.
  function asksIn(readContext) {
    // Before the first replay, the DOM carries authored initial state while the log may
    // already answer it. This list drives both pixels and actions, so an empty list is the
    // only honest answer until the presentation boundary says replay is complete.
    if (!pagePresented()) return [];
    const tags = askTags();
    if (!tags.length) return [];
    const context = readContext();
    const open = [...document.querySelectorAll(tags.join(","))].filter((el) =>
      isAwaiting(el, context),
    );
    // A roll-up delegates its visible request to the open intervention or child that
    // made it true. Keep the actionable leaf in the banner and keyboard walk, not the
    // same request repeated at each ancestor.
    const visible = open.filter(
      (el) =>
        !askEntry(el).rollup ||
        !open.some(
          (candidate) => candidate !== el && projectedContains(el, candidate, context),
        ),
    );
    // The source decides whether the request stands; the surface is what the reader is
    // asked to take in. A set keeps a malformed duplicate from inflating the chrome while
    // the authored boundary still reports the ambiguity at version check.
    return [...new Set(visible.map(askSurface))];
  }
  // A thread ask has no version or restatement, but undo still withdraws an action.
  // `x-awaits.until` therefore reads the same standing action projection as the DOM:
  // a posted answer closes the ask, and taking it back opens the ask again.
  function answeredThreadAsk(el, projection) {
    const entry = registry[el.tagName.toLowerCase()];
    if (!Object.keys(entry["x-state"] ?? {}).length) return true;
    const until = entry["x-awaits"].until;
    if (until && matchesProjectedWhen(el, until.when, projection))
      return [...projection.actions.values()].some(
        ({ e }) => e.widget === el.id && e.action === until.verb,
      );
    return answeredAsk(el, projection);
  }

  return {
    answeredContext,
    askEntry,
    askSource,
    isAwaiting,
    openAsks,
    projectedParent,
    unansweredAsks,
  };
}
