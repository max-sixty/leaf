/* Document-order placement and grouping for conversation threads. */
export function createThreadPlacement(dependencies) {
  const { inChrome, itemSays, itemWord, layerPart, pageParts, placedAt, sectionOf } =
    dependencies;

  // ---------- where the panel puts a thread ----------
  // The list reads in the page's order, not the log's. A page is a document with a
  // beginning and an end, and the reader walks the conversation the way they walk the
  // prose it is about: the thread on the lede is the first one, the thread on the punch
  // list is the last, and j/k, the g c digits, the marks out on the page and the panel's
  // own scroll all say the same order. Log order answered a different question — when a
  // thread was opened — which is a question about one thread rather than about a list, and
  // the message clocks already answer it.
  //
  // Where a thread stands is where the anchor pass resolved its passage to (`placed`) — the
  // same resolution the marks are drawn from, so the list and the page cannot disagree about
  // which of two threads comes first.
  //
  // A passage this version has rewritten falls back to the element the anchor names, which
  // is the whole point of an anchor carrying one: an id survives a rewrite that takes the
  // quote down with it, so a thread whose words are gone still belongs where it was about.
  // It reads as detached in the list and sits under its own heading, which are two true
  // things rather than one true and one lost.
  //
  // What is left resolves nowhere at all: a general comment, which names nowhere, and an
  // anchor whose element this version no longer holds either. Both go under the list rather
  // than at some point in the middle of it.
  // Where a thread stands, said in the document's own tree. A passage a widget renders into
  // a declared shadow root is placed inside that root, and `compareDocumentPosition` answers
  // across trees with "disconnected, in an implementation-specific order" — an order no
  // reader has ever seen, and one `contains` cannot correct. The host is the element the
  // page holds, and where the page holds it is where those words are. A place in no tree at
  // all — an element a version activation has replaced — is no place, which is the same
  // answer an anchor that resolves nowhere gets.
  const inPage = (el) => {
    let at = el;
    while (at && at.getRootNode() !== document) at = at.getRootNode().host ?? null;
    return at;
  };

  const threadPlace = (t) =>
    inPage(placedAt(t.root.id) ?? (t.root.anchor ? sectionOf(t.root.anchor) : null));

  // Which of two elements the reader reaches first. `compareDocumentPosition` answers for
  // a containing element too — a section reaches the reader before the paragraph inside it
  // — which is what makes it the whole reading rather than a comparison of two indexes
  // into a list this file would have to keep.
  const pageOrder = (a, b) =>
    a === b
      ? 0
      : a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING
        ? -1
        : 1;

  // The log's order is the tiebreak, so two threads on one paragraph read in the order they
  // were opened, and a page that gave nothing an id keeps exactly the list it had.
  function inPageOrder(threads) {
    const seat = new Map(threads.map((t, i) => [t, i]));
    const place = new Map(threads.map((t) => [t, threadPlace(t)]));
    return [...threads].sort((a, b) => {
      const pa = place.get(a);
      const pb = place.get(b);
      if (!pa || !pb) return (pa ? 0 : 1) - (pb ? 0 : 1) || seat.get(a) - seat.get(b);
      return pageOrder(pa, pb) || seat.get(a) - seat.get(b);
    });
  }

  // The page's own outline, in document order. Read off the headings the author wrote
  // rather than off <section> nesting, because both shapes are in the corpus and a heading
  // is the thing a reader navigates by in either — a page written as one flow of h2s has an
  // outline just as much as one written as nested sections. The runtime's own chrome
  // contributes none (pageParts), which also keeps a heading inside a reply's Markdown out
  // of the page's outline.
  const pageOutline = () => pageParts("h1, h2, h3, h4, h5, h6");

  // Which part of the page an element is in: the heading that names everything from itself
  // to the next one. A place that contains a heading takes that heading rather than the one
  // before it — an anchor on a whole <section> is about that section, not about the end of
  // the one above.
  function headingFor(place, outline) {
    let above = null;
    for (const heading of outline) {
      if (heading === place || place.contains(heading)) return heading;
      if (heading.compareDocumentPosition(place) & Node.DOCUMENT_POSITION_FOLLOWING)
        above = heading;
      else break;
    }
    return above;
  }

  // The run of threads a heading stands over, named. The key is what the panel reconciles
  // the heading node by, so it is positional (the outline's own index) rather than an id the
  // author may not have written. The named keys below it are the places a page has no seat
  // for; none of them ever carries a target, so a group's node keeps its kind — a button
  // where there is somewhere to go, a plain line where there is not — across every
  // reconcile.
  function groupFor(t, outline) {
    const place = threadPlace(t);
    if (!place)
      return t.root.anchor
        ? { key: "gone", label: "No longer in this version" }
        : { key: "page", label: "About the page as a whole" };
    if (inChrome(place))
      return layerPart(place)
        ? { key: "layer", label: "The page's own layer" }
        : { key: "sent", label: "Sent in the conversation" };
    const heading = headingFor(place, outline);
    // A page its author wrote no headings into has no runs to name, and a run with no name
    // gets no line: "Above the first heading" over the whole list would be a landmark
    // naming a landmark the page hasn't got. The list is still the page's order.
    if (!heading)
      return { key: "top", label: outline.length ? "Above the first heading" : "" };
    return {
      key: "h" + outline.indexOf(heading),
      label: itemSays(heading) || itemWord(heading),
      target: heading,
    };
  }

  return { groupFor, inPageOrder, pageOutline };
}
