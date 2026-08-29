/* Authored widget state captured before projection changes the live DOM. */
export function createAuthoredProjection(dependencies) {
  const { quoteFrom, textNodesUnder, widgetEntries } = dependencies;

  // ---------- decided, awaiting the honoring version ----------
  // The registry's x-state names each verb's fold unit and record form, so one
  // pass renders "the user decided this and no version has carried it yet"
  // for every widget alike — choose had its mark, edit its tint, move nothing,
  // and the asymmetry was each widget remembering (or not) on its own. The
  // authored facets are captured once per page load, after upgrades and before
  // the first replay: the markup's initial condition, which replay then
  // overwrites in the DOM.
  const authoredFacets = new Map(); // (owner, unit, facet) -> authored record value

  // Both channels: a report's record form is a facet exactly as an action's is,
  // so the authored-facet capture and the diff's state half serve the two alike.
  // Named members rather than a tuple, because every consumer takes a different subset
  // and positional destructuring once bound a verb where it wanted the spec. Nothing
  // threw; the diff simply marked no recorded state.
  function stateSpecs() {
    const specs = [];
    for (const [tag, entry] of widgetEntries())
      for (const channel of ["x-state", "x-report"])
        for (const [verb, spec] of Object.entries(entry[channel] ?? {}))
          specs.push({ tag, channel, verb, spec });
    return specs;
  }

  // A recorded part belongs to the nearest widget that owns recorded state, regardless
  // of tag. Custom containers and shipped widgets compose through the same registry, so
  // same-tag scoping is too weak: an outer group must not read or reset a nested group's
  // chosen members merely because the inner owner has another name.
  const recordedOwner = (member) => {
    const selector = [
      ...new Set(
        stateSpecs()
          .filter(({ spec }) => spec.record)
          .map(({ tag }) => tag),
      ),
    ].join(",");
    return selector ? member.closest(selector) : null;
  };
  const ownedRecordMembers = (widget, selector) =>
    [...widget.querySelectorAll(selector)].filter(
      (member) => recordedOwner(member) === widget,
    );

  // What the page shows for one unit's declared record form, asked of the live
  // DOM or of the diff's parsed base document alike. An attribute record is the
  // set of elements wearing it — a group taking several picks marks several — so
  // both readings collapse to the sorted ids, and comparing them stays a !==.
  //
  // The id-bearing ones only, because an id is how a member of that set is named
  // everywhere else: in the canonical value the server projects (and the local
  // outbox adapter sorts before that round trip) and in interact.py's reading of the
  // same page, which can see none but those. One marked element without an id contributed an empty
  // string that sorted to the front of the join, so a set the two sides agreed on
  // came out with a leading space on this one.
  function domFacet(el, record) {
    if (record.kind === "attribute")
      return ownedRecordMembers(el, `[${record.attr}]`)
        .map((o) => o.id)
        .filter(Boolean)
        .sort()
        .join(" ");
    if (record.kind === "value") return el.getAttribute(record.attr);
    if (record.kind === "position") return el.closest(record.within)?.id ?? null;
    return quoteFrom(textNodesUnder(el)); // "body": the words, read the way a quote is
  }

  // The same capture read the other way: the detail that *states* each unit's
  // authored placement, keyed by the verb that would state it. The facet above is
  // what a comparison needs, and it is deliberately lossy — a position collapses to
  // its column, a body to its collapsed words — because the log's own detail is
  // compared collapsed. Taking a gesture back needs a statement rather than a
  // comparison, and the two are different questions about one record: a card put
  // back on the right list in the wrong place is the facet's answer, correct and
  // useless.
  const authoredDetails = new Map(); // (owner, unit, facet) -> the detail stating it
  // Reconciliation resets a dirty widget as one composition boundary before replaying
  // its winners. Position units share sibling order, so restoring only the unit whose
  // winner disappeared would make its authored index relative to a still-projected
  // container and then replay the other units from the wrong order.
  const authoredStatements = new Map(); // widget id -> coordinate -> absolute statement

  // And the markup itself, for state no action detail can state: a recordless
  // settlement, or an optional authored scalar absent before its first action. Keep a
  // clone only where one declared action needs that route.
  //
  // Taken beside the passage fences and for the same reason, which is that both are
  // readings of what the *version* wrote: the moment after the registry lands and before
  // the modules import is the only one at which the page holds the author's markup and
  // nothing else. A clone taken a moment later is a clone of the upgraded page — the
  // injected controls, the marks, and `once`'s own stamp with them — so putting it back
  // would put back a widget that had already been upgraded and would never upgrade again.
  const authoredMarkup = new Map(); // widget id -> the markup this version wrote
  const authoredParents = new WeakMap(); // element -> its pre-upgrade parent
  // By tag rather than by verb, because a family declaring two record-less verbs — a
  // suggestion's accept and its reject — would otherwise clone every one of its
  // instances once per verb and keep the last.
  function rememberAuthoredMarkup(root = document) {
    const elements = root.nodeType === Node.ELEMENT_NODE ? [root] : [];
    elements.push(...root.querySelectorAll("*"));
    for (const element of elements)
      if (!authoredParents.has(element))
        authoredParents.set(element, element.parentElement);

    const specs = new Map();
    for (const declared of stateSpecs().filter(({ channel }) => channel === "x-state"))
      specs.set(declared.tag, [...(specs.get(declared.tag) ?? []), declared]);
    for (const [tag, declared] of specs) {
      for (const widget of root.querySelectorAll(tag))
        if (
          widget.id &&
          !authoredMarkup.has(widget.id) &&
          declared.some(
            ({ spec }) =>
              !spec.record ||
              (spec.record.kind === "value" && !widget.hasAttribute(spec.record.attr)),
          )
        )
          authoredMarkup.set(widget.id, widget.cloneNode(true));
    }
  }

  const authoredWidgets = new Set();
  function captureAuthoredFacets(root = document) {
    const byTag = new Map();
    for (const statement of stateSpecs()) {
      if (!statement.spec.record) continue;
      const statements = byTag.get(statement.tag) ?? [];
      statements.push(statement);
      byTag.set(statement.tag, statements);
    }
    for (const [tag, statements] of byTag) {
      for (const widget of root.querySelectorAll(tag)) {
        if (!widget.id || authoredWidgets.has(widget.id)) continue;
        for (const { verb, spec } of statements) {
          if (spec.unit === "widget")
            rememberAuthored(widget, widget, widget.id, verb, spec);
          else
            // A position facet is carried by the container's direct id'd children.
            // Ownership stops at the nearest widget declaring recorded state, so an
            // outer custom container cannot capture a nested widget's parts.
            for (const part of widget.querySelectorAll(`${spec.record.within} > [id]`))
              if (recordedOwner(part.parentElement) === widget)
                rememberAuthored(widget, part, part.id, verb, spec);
        }
        authoredWidgets.add(widget.id);
      }
    }
  }

  // The facet and the statement that restores it are both authored facts. Reports are
  // not undoable gestures, but a report can be the projected state displaced by an
  // action; when that action is withdrawn, reconciliation needs the same baseline.
  function rememberAuthored(widget, el, unit, verb, spec) {
    const coordinate = stateCoordinate(widget.id, unit, spec);
    authoredFacets.set(coordinate, domFacet(el, spec.record));
    const detail = authoredDetail(el, unit, spec);
    if (!detail) return;
    authoredDetails.set(coordinate, detail);
    const statements = authoredStatements.get(widget.id) ?? new Map();
    if (!statements.has(coordinate))
      statements.set(coordinate, { coordinate, unit, action: verb, detail, spec });
    authoredStatements.set(widget.id, statements);
  }

  // Built from the record form alone, so no widget is named here and a twelfth one is
  // covered the day it declares. Null where this version's markup states no placement
  // at all — an unset scalar, a part standing outside the container its record names —
  // and a unit with no authored statement simply has no first gesture to take back.
  function authoredDetail(el, unit, spec) {
    const record = spec.record;
    const detail = spec.unit !== "widget" ? { [spec.unit]: unit } : {};
    if (record.kind === "attribute")
      detail[record.value] = ownedRecordMembers(el, `[${record.attr}]`)
        .map((o) => o.id)
        .filter(Boolean)
        .sort();
    else if (record.kind === "value") {
      const value = el.getAttribute(record.attr);
      if (value === null) return null;
      detail[record.value] = value;
    } else if (record.kind === "body")
      // Uncollapsed, where domFacet collapses: what is being reproduced is the
      // words, and a draft's paragraphs are the whole of the difference. The same
      // walk either way, so the two readings cannot disagree about *which* words
      // are the page's — only about the whitespace between them.
      detail[record.value] = textNodesUnder(el)
        .map((seg) => seg.node.data.slice(seg.start, seg.end))
        .join("");
    else {
      const within = el.closest(record.within);
      if (!within?.id) return null;
      detail[record.value] = within.id;
      // Among the container's id'd children, which is the same list the capture
      // above walks — and the same one a board counts, a column admitting nothing
      // but cards.
      detail[record.order] = [...within.children].filter((c) => c.id).indexOf(el);
    }
    return detail;
  }

  // Which element one event states, per the verb's declared fold unit: the widget itself
  // where the verb is absolute across the group, and the element its detail names where
  // it is absolute per part. One sentence, because two copies of it are two readings of
  // the registry free to disagree about what an event is about.
  const unitOf = (e, spec) => (spec.unit === "widget" ? e.widget : e.detail[spec.unit]);
  // One stable representation for the semantic coordinate in every derived view.
  // JSON's array form preserves the boundary even when an id contains punctuation.
  const stateCoordinate = (owner, unit, spec) =>
    JSON.stringify([owner, unit, spec.facet]);

  return {
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
  };
}
