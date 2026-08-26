export function createSelectionCapture({
  anchoringIsReady,
  blockOf,
  closestAcross,
  cut,
  datumSelector,
  elementOver,
  neighbourhood,
  pageRange,
  pageText,
  pageWords,
  quoteFrom,
  segmentText,
  segmentsIn,
  spanIn,
}) {
  // How much of a passage's surroundings an anchor writes down. Only the capture decides
  // this; the search asks for whatever a given anchor happens to hold.
  const CONTEXT = 24;
  // The anchor a selection makes: the enclosing section, and the passage as the document
  // holds it. Not the selection's own toString(), which is what the reader sees rendered —
  // text-transform uppercases an eyebrow or a table header, and the runtime's own chrome
  // inside the passage comes along — and a quote the search can't find is no highlight while
  // composing and a comment that posts permanently detached. A selection with nothing
  // quotable in it yields no quote, which makes it an element anchor on its section: what
  // such a selection meant anyway.
  //
  // The whole of it, however long. A cap here read as an economy and was a claim: the
  // stored quote is the passage, so the mark paints it and the comment is on it, and a
  // reader who selected a paragraph past the cap got a comment on its opening and a
  // highlight that shrank to match — silently, on most of the paragraphs a leaf page
  // holds. What the cap was really bounding is the search's pattern, which is where the
  // bound now lives (LEAD_CAP), so nothing has to be given up to keep it cheap.
  function selectionAnchor(sel) {
    const range = pageRange(sel);
    const node = range.commonAncestorContainer;
    const holder = node.nodeType === Node.ELEMENT_NODE ? node : node.parentElement;
    // The neighbours come from the same indexed reading the search uses and stop at
    // the same opaque-widget fences as the file-side capture. The browser knows words
    // a module generated and may quote them; it does not pretend the file can confirm
    // context across their seam.
    const segments = segmentsIn(range);
    const quote = quoteFrom(segments);
    const dataNodes = new Set(
      segments.map((seg) => closestAcross(seg.node, datumSelector())).filter(Boolean),
    );
    const [onlyDatum] = dataNodes;
    const datum =
      dataNodes.size === 1 &&
      segments.every((seg) => closestAcross(seg.node, datumSelector()) === onlyDatum)
        ? onlyDatum
        : null;
    const section =
      datum?.dataset.lfProjection ??
      closestAcross(holder, "[id]:not(.lf-ui)")?.id ??
      null;
    // Identity is the context for projected data. Neighbouring display values may reorder
    // or repeat, so storing their words as prefix/suffix would make incidental layout a
    // second, conflicting answer to which datum the reader selected.
    if (datum)
      return {
        section,
        datum: datum.dataset.lfDatum,
        quote,
      };
    const reading = pageText();
    const [start, stop] = spanIn(reading, segments);
    const prefix = cut(
      neighbourhood(reading.origin, reading.fences, start, CONTEXT, true),
      -CONTEXT,
      Infinity,
    );
    const suffix = cut(
      neighbourhood(reading.origin, reading.fences, stop, CONTEXT, false),
      0,
      CONTEXT,
    );
    // Only what there is. A passage against the document's own edge has no neighbour on
    // that side, and writing that down as an empty string puts a field in the event that
    // never says anything.
    return {
      section,
      quote,
      ...(prefix && { prefix }),
      ...(suffix && { suffix }),
    };
  }

  // A selection of the page's own words, as against none, a bare caret, or one made inside
  // the runtime's own layer. That is the line between a user reaching for a passage and
  // one working the chrome, and it is the question every caller here is really asking.
  const pageSelection = () => {
    const sel = getSelection();
    return sel && !sel.isCollapsed && pageWords(sel.anchorNode) ? sel : null;
  };
  // Where a send ends is where typing continues, and the reader has the last word on it.
  // A send is a round trip, so this step lands whenever the server answers — long after
  // the gesture on a loaded machine — and focusing a box collapses whatever the page had
  // selected. A passage picked out while the send was in the wire is a later gesture and
  // stands, for the same reason a later edit does. It has less recourse than the edit:
  // nothing re-decides the 💬 until the reader gestures again, so the words in front of
  // them stop being something to comment on, and no surface says why. Stated once, for
  // the three boxes a send can land in, because it is one fact about a send landing.
  //
  // A box is the whole of it, which is why this is named for typing rather than for
  // focus. The panel's other two landings — a resolve and a reopen, each behind a round
  // trip of its own — put the reader on a thread node instead, and Chrome collapses the
  // selection for a landing that takes a caret, not a control as such — a button and a
  // select leave it standing, and so does a `tabindex="-1"` div. Same
  // shape, then, and not the same steal: those two keep the standing place a control
  // that folds away with its thread owes the reader.
  function landTyping(box) {
    if (!pageSelection()) box?.focus({ preventScroll: true });
  }
  // A drag stops where the hand stopped, not where the reader aimed: a release two glyphs
  // short of a word's end meant the word, and the capture would store the fragment as if
  // the fragment were the point. So the pointer path grows a selection outward — never
  // inward — until each end sits on a boundary of the same word units the runtime already
  // reads sequences by (textUnits), and only where the end fell strictly inside a
  // word-like unit. An end resting on a boundary, in space, or against punctuation stays
  // exactly where the reader put it, and keyboard selections never come here at all:
  // shift-arrow is the reader being precise, and precision is not a thing to correct.
  //
  // One end, because the two are the same question asked at two places, and the words are
  // read in the indexed text every other reading of the page uses. That is what keeps a
  // snap from claiming what the capture would refuse: a word never continues across a
  // fence, and never across a block seam, which is where the collapse writes the space the
  // markup doesn't hold. One seam is snapping's own, past what the collapse knows: where
  // machine-placed words (data-lf-gen) stand flush against the author's — a chip row is
  // written with no space after the title it follows — the two runs read as one word, and
  // growing across that seam would hand a selection of the chip the title too.
  function snapOut(reading, at, back) {
    const { raw, origin, fences } = reading;
    const behind = fences.filter((f) => f <= at).at(-1) ?? 0;
    const ahead = fences.find((f) => f >= at) ?? raw.length;
    const spoke = (o) => elementOver(o.node).closest("[data-lf-gen]");
    // An EDGE's neighbours are the nearest characters, not the nearest cells: an empty
    // text node is an empty segment, which puts two EDGEs flush, and every reader of
    // `origin` steps over its nulls.
    const joined = (i) => {
      if (origin[i] !== null) return true;
      let a = i - 1;
      while (origin[a] === null) a--;
      let b = i + 1;
      while (b < origin.length && origin[b] === null) b++;
      const prev = origin[a];
      const next = origin[b];
      if (!prev || !next) return false;
      return blockOf(prev.node) === blockOf(next.node) && spoke(prev) === spoke(next);
    };
    const inRun = (i) => !/\s/.test(raw[i]) && joined(i);
    let lo = at;
    while (lo > behind && inRun(lo - 1)) lo--;
    let hi = at;
    while (hi < ahead && inRun(hi)) hi++;
    let run = "";
    let boundary = 0; // the end's own index within `run`
    const from = []; // from[i] = the raw index run[i] came from; an EDGE holds no character
    for (let i = lo; i < hi; i++) {
      if (origin[i] === null) continue;
      if (i < at) boundary++;
      from.push(i);
      run += raw[i];
    }
    const word = segmentText(run).containing(boundary);
    if (!word || word.index >= boundary || !word.isWordLike) return at;
    return back ? from[word.index] : from[word.index + word.segment.length - 1] + 1;
  }
  // An end the snap didn't move keeps the boundary the browser gave it: a drag out into
  // chrome ends past the last quotable character, and rewriting that end from the reading
  // would pull the visible selection off words the reader chose to cover. The gesture's
  // direction survives too, or the shift-click that next extends the selection would
  // extend it from the wrong end.
  function snapSelection() {
    if (!anchoringIsReady()) return;
    const sel = pageSelection();
    if (!sel) return;
    const range = pageRange(sel);
    const segments = segmentsIn(range);
    if (!segments.length) return;
    const reading = pageText();
    const [start, stop] = spanIn(reading, segments);
    const lo = snapOut(reading, start, true);
    const hi = snapOut(reading, stop, false);
    if (lo === start && hi === stop) return;
    const head =
      lo === start
        ? [range.startContainer, range.startOffset]
        : [reading.origin[lo].node, reading.origin[lo].offset];
    const tail =
      hi === stop
        ? [range.endContainer, range.endOffset]
        : [reading.origin[hi - 1].node, reading.origin[hi - 1].offset + 1];
    // Backward means the anchor sits past the range's start — asked of boundary points,
    // because node order misreads containment: a focus on the element holding the anchor's
    // text node both precedes and contains it.
    //
    // Both points have to be in one tree to be compared at all. Inside an x-shadow widget
    // they are not: the selection's own anchorNode is the light-DOM one Chrome clamped to
    // the host, while the range is the composed one this snapped from, and comparing them
    // throws rather than answering. A selection that never left the widget has no direction
    // worth recovering — there is one text node under the pointer either way — so it snaps
    // forward, which is what a drag inside one block does regardless.
    const probe = document.createRange();
    probe.setStart(sel.anchorNode, sel.anchorOffset);
    const comparable =
      sel.anchorNode.getRootNode() === range.commonAncestorContainer.getRootNode();
    const backward =
      comparable && probe.compareBoundaryPoints(Range.START_TO_START, range) > 0;
    if (backward) sel.setBaseAndExtent(...tail, ...head);
    else sel.setBaseAndExtent(...head, ...tail);
  }

  return {
    landTyping,
    pageSelection,
    selectionAnchor,
    snapSelection,
  };
}
