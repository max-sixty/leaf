/* Anchor resolution, geometry, painting, and navigation. */
export function createAnchors(dependencies) {
  const {
    DATUM,
    LANDMARK_CAP,
    SCROLL,
    TEXT_BLOCK,
    aimBox,
    aimIsOn,
    aimedItem,
    anchorLabel,
    anchorsReady,
    blockAt,
    buildThreads,
    closestAcross,
    composerAbout,
    composerAnchor,
    composerIsOpen,
    composerQuote,
    containsAcross,
    cut,
    designIsOn,
    designName,
    designTarget,
    elementById,
    elementFromPointAcross,
    elementOver,
    findQuote,
    focusedThreadOf,
    inChrome,
    inUi,
    inspectEl,
    landedAt,
    offer,
    pageQueryAll,
    pageScroller,
    pageText,
    pageWords,
    paintThreadQuotes,
    panel,
    quoteFrom,
    queueLegend,
    rangeOf,
    registry,
    reveal,
    runtime,
    scrollerFor,
    setLanded,
    setPanel,
    settledAway,
    tagsDeclaring,
    textNodesUnder,
    threadsBox,
    uiInside,
    under,
  } = dependencies;

  // ---------- view continuity ----------
  // Following a new version replaces the authored main, whether the live root keeps this
  // document or historical travel opens another one. A raw replacement leaves the reader
  // at the top mid-session, standing nowhere in the walk they were making. Where they are
  // rides across as one semantic view — and through tabStore on document travel, per-tab
  // because a place in a page shouldn't outlive it. Two things are recorded, because
  // askPosition reads two the runtime can write down: the passage they were reading, and
  // the ask the n/p walk had stepped them to. The passage travels as a landmark rather
  // than a pixel offset, since content moves between versions: re-find it by its text
  // within its section, then the section alone, and only fall back to the raw offset when
  // neither survived the revision. The panel's own open state is restored separately
  // (PANEL_KEY); because that runs first, the column is already reflowed by the time we
  // scroll.
  const VIEW_KEY = "lf-view";

  // The page's own text blocks the reader can see, in document order, with the rect of each
  // one's first line — one reading of what is in front of them, for the two questions that
  // ask it: which passage a version change should land them back on (below), and where a
  // walk over the page's asks starts when they have pointed at nothing (askPosition).
  // A block's landmark is the top of its first line (a range), not its border box; restore
  // measures the matched text the same way, so the line box's leading cancels out.
  function* blocksOnScreen() {
    for (const block of document.querySelectorAll(TEXT_BLOCK)) {
      // [hidden] needs an explicit skip: hidden="until-found" resolves to
      // content-visibility, under which descendants still report real rects —
      // but what's behind an inactive tab isn't what the reader is reading.
      if (inChrome(block) || block.closest("[hidden]")) continue;
      const range = document.createRange();
      range.selectNodeContents(block);
      const rect = range.getBoundingClientRect();
      if (rect.height && rect.bottom > 42) yield [block, rect]; // 42 = banner height
    }
  }
  // The quote and the section it's searched in come from the same block, or the search is
  // filtered to a section the text isn't in and can only ever fail — restore then falls back
  // to the section, which doesn't absorb content added above the reader inside it.
  function captureView() {
    const view = { v: runtime.currentVersion, y: pageScroller.scrollTop };
    // Where the ask walk left off, which is the reader's place stated more exactly than
    // any block can state it — the walk put them there on purpose. Its element identity
    // does not survive an authored-main replacement, and the module variable does not
    // survive document travel, so the id is the one form both can restore. The ring is not
    // recorded beside it: it is painted from focus, and another document starts on the page.
    view.ask = landedAt()?.id;
    for (const [block, rect] of blocksOnScreen()) {
      const section = block.closest("[id]");
      if (!view.section && section) {
        // The first on-screen block's section, kept only until a quotable block supplies
        // its own: a page with nothing quotable on screen still has somewhere to land.
        view.section = section.id;
        view.sectionTop = shownBox(section).top;
      }
      // Written down the way a comment's quote is, so the search that re-finds it is
      // looking for a string of the same kind.
      const text = cut(quoteFrom(textNodesUnder(block)), 0, LANDMARK_CAP);
      // A short line ("Risks") would match anywhere; keep scanning for a quotable block.
      if (text.length >= 24) {
        // Unconditionally, so a quotable block under no section clears the earlier one
        // rather than sending the search into a subtree its text isn't in.
        view.section = section?.id;
        view.sectionTop = section && shownBox(section).top;
        view.quote = text;
        view.quoteTop = rect.top;
        break;
      }
    }
    return view;
  }

  // A restore jumps rather than glides: a page is free to set scroll-behavior: smooth, and
  // animating from the replacement's raw position is worse than the jump it replaces.
  // Moving to a mark the reader asked for is the other case, and says so.
  // The document scrolls for its own content; the panel's list scrolls for a widget an
  // agent sent in a reply. Most callers mean the document, so it remains the default.
  const jumpBy = (dy, behavior = "instant", box = pageScroller) =>
    box.scrollBy({ top: dy, behavior });
  function restoreView(view) {
    // Where the walk left off, put back before the scroll below restores the coarser
    // reading of the same fact — and put back whether or not this version answered that
    // ask, since an ask the reader has not stepped off is still the one they would step
    // from. The document's own lookup rather than elementById: the ask list is the
    // document's (openAsks), and a landing inside a shadow tree is one askStep could never
    // measure against. A thread's ask is not here yet — the panel is rebuilt from the log
    // on the first poll, which is behind this — so the record answers for the page's asks
    // and says nothing about the panel's, rather than restoring a second time later over a
    // walk the reader has made since.
    setLanded((view.ask && document.getElementById(view.ask)) || null);
    const text = pageText();
    const found = view.quote && resolveAnchor(view, text);
    if (found?.segments) {
      reveal(found.segments[0].node.parentElement); // the passage may sit behind a tab
      jumpBy(rangeOf(found.segments).getBoundingClientRect().top - view.quoteTop);
      return;
    }
    const section = resolveAnchor({ section: view.section }, text)?.element;
    if (section) {
      reveal(section);
      // The shown reading on both sides of the subtraction, because the landmark is
      // whatever id stands nearest the block the reader was on, and a section that
      // generates no box of its own is one a suggestion wrapping whole sections leaves
      // there. Read raw, both sides come back 0 and the correction is 0 — so the restore
      // that had somewhere to land did nothing, silently, and left the reader at the top.
      jumpBy(shownBox(section).top - view.sectionTop);
    } else pageScroller.scrollTo({ top: view.y, behavior: "instant" });
  }

  // ---------- anchors ----------
  // An anchor names a passage: a section id, a quote, or both. Resolving one is the only
  // place the page is searched, so the three things that read a passage back — a thread's
  // mark, the composer's own, and the reading position a version change rides on — cannot
  // disagree about where to look. A quoteless anchor has no text to paint and resolves to
  // its element instead.
  // The search always reads the whole document — the same text the capture wrote the
  // neighbours from — and the section the anchor names filters where a candidate may sit.
  // A section the page no longer has filters nothing, so the quote is still looked for
  // everywhere, which is all a stale section ever meant.
  // Which element an anchor names, asked in one place: the element it resolves to when it
  // carries no quote, the subtree a candidate has to sit inside when it does, and the holder
  // of the line saying a passage carries a comment are all this question.
  const sectionOf = (anchor) => (anchor.section ? elementById(anchor.section) : null);

  // ---------- pointing at an item ----------
  // One gesture reaches any item: ⌥-click — direct aim, no selection, no chrome, and the
  // only route to an item whose words are all inside controls. A plain click reaches the
  // visuals, which have no text to select. Two more routes were tried and cut: a rule in
  // the margin raised by hovering, too strong for what it offered and placed at the
  // item's own left edge, which is the page's margin only for an item the page happens
  // to have left-aligned; and a row of chips beside the 💬 offering the selection's
  // enclosing chain ("⬚ paragraph", "⬚ section") — a correction nobody had asked for,
  // paid in chrome beside every selection a user made.
  //
  // What both write is the anchor leaf already has. A comment on an element is
  // {section: <id>} with no quote — the shape a click on a diagram has made since the
  // beginning — so none of this is a new representation, a new event field, or a second
  // thing for a version to carry. What is missing is only the gesture, and how the panel
  // says which item a thread is on.
  //
  // An item is an element the author gave an id, outside the runtime's own layer and
  // outside the panel (a reply's frozen widget markup carries ids of its own). `version
  // check` holds every id across versions, which is exactly why an anchor naming one
  // survives a rewrite that takes a quote down with it. An id under the runtime's own
  // prefix is not the author's — a module coins one for what it draws (a diagram's svg
  // wears `lf-mermaid-N`, numbered by draw order) — so an anchor on it names nothing a
  // version holds and something the next load may number differently. The item is the
  // element around it, which is the widget.
  const ITEM = '[id]:not(.lf-ui):not([id^="lf-"])';
  // Whether an element is an item: what the aim walks up to, and what the legend draws a
  // box for — one predicate, so the two cannot disagree about what is on the page. Never
  // one the user's decision settled off the page: the aim's paint already refused those,
  // and a press answered by a different predicate anchored a composer to a retired
  // element — a box about nothing, promised by nothing. And never one inside a widget
  // that renders as a picture (x-visual): a diagram's nodes carry the ids its renderer
  // coined — `root-1`, `actor0`, under no prefix of ours — and an anchor on one names
  // nothing a version holds. The entry says the click's anchor is the widget rather than
  // a generated part inside it, and the aim is a click; the plain-click path already
  // took the outermost visual, and the aim named the node under the pointer.
  function isItem(at) {
    if (!at.matches(ITEM) || inChrome(at) || inUi(at) || settledAway(at)) return false;
    const visual = tagsDeclaring((e) => e["x-visual"]).join(",");
    return !(visual && at.parentElement && closestAcross(at.parentElement, visual));
  }
  // The innermost item: a card rather than its column, the column rather than the board —
  // the smallest thing under the pointer is the thing pointed at. The walk continues
  // upward past what is not one, because the enclosing item is what is on screen.
  function itemAt(node) {
    let at = node?.nodeType === 1 ? node : node?.parentElement;
    for (; at; at = at.parentElement) if (isItem(at)) return at;
    return null;
  }
  // What to call an item, in a word the user reads beside a thread's § label. A widget
  // names itself: its tag minus the prefix is already the word the vocabulary chose
  // ("card", "option", "column"), so the twelfth widget gets a name here without core
  // hearing about it.
  //
  // The page's own elements have no such word. A tag is markup rather than English, and a
  // label reading "§ p · …" over ordinary prose names the thing to a browser and to nobody
  // else. So HTML's tags get the nouns a reader would use, and an unlisted one falls back
  // to its tag, which is worse than a word and better than nothing.
  const HTML_WORDS = {
    // Every one of these is a control the platform gives keys to and no letters — a radio,
    // a checkbox, a slider, a colour or file button. The ones that take letters never reach
    // this reading, the typing scope having claimed the key before the page is asked, so
    // there is no field here for "control" to misname. Worth a word at all because `c` names
    // what it is about, and a reader standing on a toggle was told "the input".
    input: "control",
    select: "control",
    button: "control",
    p: "paragraph",
    li: "item",
    tr: "row",
    td: "cell",
    th: "cell",
    figure: "figure",
    blockquote: "quote",
    pre: "block",
    section: "section",
    article: "section",
    aside: "aside",
    ul: "list",
    ol: "list",
    dl: "list",
    table: "table",
    details: "note",
    h1: "heading",
    h2: "heading",
    h3: "heading",
    h4: "heading",
    h5: "heading",
    h6: "heading",
  };
  function itemWord(item) {
    if (!item) return "";
    const tag = item.tagName.toLowerCase();
    // A widget whose kind is not its tag says which it is. Three shapes of change are all
    // <lf-suggestion>, and naming each of them by the tag put a deletion on the asks tray
    // under the words it proposed to remove, reading exactly like the insertion above it.
    // Asked only where an entry says there is something to ask, and answered only by an
    // element that has upgraded — before that, and for every widget that declares nothing,
    // the tag is the word.
    if (registry[tag]?.["x-word"] === "module") {
      const own = item.lfWord?.();
      if (own) return own;
    }
    if (tag.startsWith("lf-")) return tag.slice(3);
    // A <pre> is a block of something and the something is in the markup: the documented
    // shape for source is <pre><code class="language-*">, and a <pre> without the <code> is
    // the shape for what isn't source — a transcript, a stack trace, command output. So the
    // word is read rather than assumed, and a user who calls it a code block is offered
    // one.
    if (tag === "pre") return item.querySelector(":scope > code") ? "code" : "block";
    return HTML_WORDS[tag] ?? tag;
  }
  // The item's own opening words, read the way anchoring reads everything else — so a label
  // a widget declared as the page speaking is in it and the runtime's own chrome (the hidden
  // "2 comments" line) is not. Cut back to a word boundary and marked as cut, because a label
  // ending mid-word reads as a quote that lost its tail rather than as a name for the thing.
  const ITEM_SAYS_CAP = 52;
  // The reading is the whole answer, and it is the answer wherever the item stands. An
  // ask carried by a message is still an ask, and it is read here exactly as an ask on
  // the page is: rooted at the item, so the panel around it is nobody's chrome (see the
  // note on `overIn`) while the item's own marks and offers still are. A veto on
  // `inChrome` stood in front of this, from the days only an anchor's section reached it:
  // it threw the reading away and left the asks tray naming the question by its raw id.
  function itemSays(item) {
    if (!item) return "";
    const whole = quoteFrom(textNodesUnder(item));
    if ([...whole].length <= ITEM_SAYS_CAP) return whole;
    const short = cut(whole, 0, ITEM_SAYS_CAP);
    const at = short.lastIndexOf(" ");
    return (at > ITEM_SAYS_CAP / 2 ? short.slice(0, at) : short).trimEnd() + "…";
  }
  function resolveAnchor(anchor, text) {
    // An element anchor asks a different question — whether the section is still on the
    // user's page — and the whole page is not an answer to it. Existence alone isn't
    // either: a decided element whose markup settles to nothing is present in the
    // document and absent from the screen, and an anchor held to it read as attached
    // while outlining nothing.
    if (anchor.datum) {
      const source = sectionOf(anchor);
      const datum = source
        ? [...source.children].filter(
            (el) =>
              el.matches(DATUM) &&
              el.dataset.lfProjection === anchor.section &&
              el.dataset.lfDatum === anchor.datum,
          )
        : [];
      // A projection/key pair identifies exactly one current fact. Disappearance detaches;
      // duplicates refuse to guess. Where its old display text still stands, mark those
      // exact words. Where the value changed, outline the same datum whole instead of
      // silently following the old string to some other fact.
      if (datum.length !== 1) return null;
      if (!anchor.quote) return { element: datum[0] };
      const segments = findQuote(text, anchor.quote, anchor, datum[0]);
      return segments.length ? { segments } : { element: datum[0] };
    }
    if (!anchor.quote) {
      const section = sectionOf(anchor);
      return section && !settledAway(section) ? { element: section } : null;
    }
    const segments = findQuote(text, anchor.quote, anchor, sectionOf(anchor));
    return segments.length ? { segments } : null;
  }

  // Every mark the page wears, drawn by one pass, so ownership of an element both a thread
  // and the open composer point at is a branch inside a loop rather than an agreement
  // between functions ("One writer per thing" in CLAUDE.md, and why).
  //
  // One range per segment, never one spanning the passage: a single range would paint back
  // over everything the search stepped around on the way — a widget's Choose button, a drag
  // grip, a diagram's generated stylesheet.
  //
  // Keyed by thread, not by mark: a passage is several segments and two comments may land on
  // the same element, so mark → thread loses one of them — and losing it told the panel the
  // passage wasn't in this version while it sat outlined on screen. Every consumer but the
  // hit-test asks "where is thread X", and that is now the direction the map runs.
  const MARK = "lf-mark";
  const PENDING = "lf-pending";
  const NOTE = "lf-mark-note";
  const marked = new Map(); // thread id -> (Range | Element)[]: the pass's record of what it drew
  // thread id -> the element its passage lands in. A different question from `marked`, and
  // the one the panel's order asks: where a thread is, rather than what was drawn for it. A
  // resolved thread has a place and no paint, and an element anchor's paint is the boxes its
  // contents show through (shownParts) rather than the element the anchor named — so neither
  // record answers for the other. Written only by the pass that resolves the anchors, so the
  // two readings can never come from different resolutions.
  const placed = new Map();
  let pendingMarks = []; // the same record for the open composer's own passage
  let pendingOutline = []; // the elements the open draft outlines, owned by nobody else
  // What the pointer would take, in whichever arming stands — the ⌥ aim's item, or design
  // mode's target: the element, and the control's word where the pointer is on one — and
  // null when neither is armed. One answer for the box, the cursor and the name.
  function aimTarget() {
    if (aimIsOn()) {
      const item = aimedItem();
      return item ? { el: item, part: "" } : null;
    }
    if (designIsOn() && pointer.x >= 0)
      return designTarget(document.elementFromPoint(pointer.x, pointer.y));
    return null;
  }
  // What a container lets the reader see of what it holds, or null where it shows all of
  // it. Overflow is one of three ways to draw nothing past an edge: paint containment and
  // content-visibility both clip while overflow computes `visible`, and a box under either
  // would be drawn at a rect the reader never sees. The band itself is the padding box less
  // whatever a scrollbar takes — clientLeft and clientWidth, where a border box says
  // nothing about either, and a box drawn under a border is drawn nowhere as surely as one
  // past the edge.
  //
  // `version check --render` imports this to ask which container cut a box away, so the
  // band a handover is refused against and the band the page paints to are one reading.
  // Written twice they disagreed twice, each copy right about one of the two things above
  // and wrong about the other.
  function shownBand(el) {
    const s = getComputedStyle(el);
    if (
      s.overflowX === "visible" &&
      s.overflowY === "visible" &&
      !/paint|strict|content/.test(s.contain) &&
      s.contentVisibility === "visible"
    )
      return null;
    const b = el.getBoundingClientRect();
    const left = b.left + el.clientLeft,
      top = b.top + el.clientTop;
    return {
      left,
      top,
      right: left + el.clientWidth,
      bottom: top + el.clientHeight,
    };
  }
  // The box an element shows as. An element that generates none of its own — a
  // display: contents wrapper — shows as what its contents paint, so its bounds are
  // theirs, and a range asks the platform for that union in one read. Its own rect is
  // (0,0) at the document's origin, which is not a degenerate box but a wrong one: it
  // reads as a real place at the top of the page, so whatever measured it travelled there.
  //
  // No widget in the vocabulary is one now — lf-suggestion was, and its theme comment
  // carries what that cost — but the wrong answer is the platform's rather than that
  // widget's: a page or a project layer styles any wrapper this way in a line. This
  // lived inside the legend's own reading once, where it stood as a fact about the
  // legend rather than about elements, which is exactly why the travel went on asking
  // the element directly and centred the top of the document. One answer to "where is
  // this element", so there is no second way to ask.
  function shownBox(el) {
    const r = el.getBoundingClientRect();
    if (r.width || r.height) return r;
    const contents = document.createRange();
    contents.selectNodeContents(el);
    return contents.getBoundingClientRect();
  }
  // The same reading in elements rather than pixels, for the marks the runtime paints on
  // the page's own elements: an outline needs a box to hang on, so a mark aimed at a
  // boxless element goes to the boxes its contents make. Read from the platform rather
  // than from the registry, because generating no box is not a fact about which widget
  // this is — any wrapper in any layer can do it, and CSS has no selector that says so.
  //
  // Area, where shownBox asks only for a box, because the two want different things of
  // one: bounds are bounds whichever dimension is flat, while a ring is only worth hanging
  // where it can be seen.
  //
  // The runtime's own chrome leaves by name rather than on that test. Area read as though
  // it were doing the job, and it was doing it by luck: a suggestion hangs its controls off
  // a span with no width, so the apparatus fell out on its own. The line saying how many
  // comments a block holds is clipped to a pixel and has one — so an ask that had been
  // commented on wore its ring on the runtime's word about the page rather than on the
  // page, and the pixel it hung from moves the first time a comment lands. That question is
  // already asked, declared labels and all, and it is the one the anchor pass puts
  // to a text node — so what a mark hangs on and what a quote may name cannot come apart.
  // Bounded at the element, for the reason given where the question is stated: a widget an
  // agent sent stands inside the panel, and asked about the page instead it would have no
  // child of its own left to fall back to.
  function shownParts(el) {
    const r = el.getBoundingClientRect();
    if (r.width && r.height) return [el];
    return [...el.children]
      .filter((child) => !uiInside(child, el))
      .flatMap((child) => shownParts(child));
  }
  // An item's bounds, held to what the page shows of them: the rect a box in the chrome's
  // layer is drawn from, for the aim's box and the legend's alike. The layer is one no
  // ancestor's clip can reach — that is the point of it — so the box owes the clips an
  // answer of its own: an option's table box runs on under its group's overflow: hidden,
  // and a card half-scrolled out of a board is half gone. A box drawn from the raw rect
  // claims pixels the page has already refused, over the neighbour standing in them.
  // body is the page's own scroller, so its edge is one of these too: what is scrolled
  // off screen has no rect, and a legend draws boxes for what is on it and nothing for
  // the rest.
  //
  // The walk stops at a box the viewport holds rather than the document: nothing above a
  // `position: fixed` element clips it, so the ancestors past that one are answering about a
  // flow the element left. Every box in the chrome is behind one — the comment panel is
  // fixed, and body is the page's scroller narrowed to the column beside it — so a reply box
  // measured through body's band came back wholly clipped away, at any window wide enough for
  // the panel to stand beside the page rather than over it. The one caller before this asked
  // only about the page's own items, none of which is ever inside a fixed box, which is why
  // the walk could be written as "every ancestor" and read as complete.
  //
  // Which leaves the viewport itself, applied to everything: for a box in the page it is
  // what body's own band already said, and for one in a fixed layer it is the whole of what
  // clips it.
  //
  // `clips` caches each ancestor's answer for one pass: the legend asks for every item
  // on the page in one breath, and the items share their scrollers, so what a pass spends
  // on the walk is two style reads per ancestor rather than two per item per ancestor.
  function shownRect(item, clips) {
    return clipped(shownBox(item), item, clips);
  }
  // Where a member begins, as the reader sees it: the first of the boxes it paints that
  // survives the clips, rather than the bounds of all of them. They are the same box for
  // anything in flow and different for an inline that wraps, whose bounds run from the
  // column's left margin to its right — so a digit placed on that corner sat four hundred
  // pixels from the link it addressed, a line above it, on top of somebody else's sentence.
  // `shownBox`'s union answers "how much room does this take", which is what a legend box and
  // an aim outline want; this answers "where does it start", which is what anything hung on a
  // corner wants. The first that survives rather than the first outright, since a link whose
  // opening line has scrolled away still has a corner on the line below it.
  const startsAt = (item, clips) => {
    const fragments = item.getClientRects();
    return (fragments.length ? [...fragments] : [shownBox(item)])
      .map((box) => clipped(box, item, clips))
      .find(Boolean);
  };
  // The clips standing over a box, applied to it. Taken apart from shownRect because the two
  // readings above want the same walk over different boxes.
  function clipped(box, item, clips) {
    let left = Math.max(box.left, 0),
      top = Math.max(box.top, 0),
      right = Math.min(box.right, innerWidth),
      bottom = Math.min(box.bottom, innerHeight);
    // From the box itself, not from its parent: an element is not clipped by its own
    // overflow — that clips what it holds — so its band is skipped and only its position is
    // read. Starting at the parent instead asked the question of every ancestor of a fixed
    // box and never of the box, which is the same bug one level up: in design mode the aim
    // resolves the comment panel itself, and the panel measured through body's band came
    // back wholly clipped away, so a mode whose row promises a click on the chrome drew
    // nothing over the chrome.
    for (let a = item; a; a = a.parentElement) {
      let c = clips.get(a);
      if (c === undefined)
        clips.set(
          a,
          (c = {
            band: shownBand(a),
            // Read here rather than out of shownBand, whose answer is a band and is the
            // render gate's too: what clips a box and what a box is positioned against are
            // two facts, and one of them is this walk's alone.
            fixed: getComputedStyle(a).position === "fixed",
          }),
        );
      if (a !== item && c.band) {
        left = Math.max(left, c.band.left);
        top = Math.max(top, c.band.top);
        right = Math.min(right, c.band.right);
        bottom = Math.min(bottom, c.band.bottom);
      }
      if (c.fixed) break;
    }
    return right > left && bottom > top ? { left, top, right, bottom } : null;
  }
  // The aim's one writer, and the whole of its paint: the box in the chrome's layer
  // (aimBox), the cursor's half of the same promise, and in design mode the name of what
  // the box is on. Everything is derived fresh on every ask — the aimed item, lf-over-item,
  // the box's geometry — because a latch here was a second answer to the question the
  // press asks fresh, and a replay repainted it stale. Synchronous, not coalesced to a
  // frame the way refreshHover is: the keydown that arms the page is followed by the press
  // in the same gesture, and a promise a frame behind the arm is one the press can outrun.
  // What each ask costs is one hit-test and one rect walk, which is what the repaint gate
  // this replaced already spent per event on deciding whether to run a far dearer pass.
  function refreshAim() {
    const target = aimTarget();
    const aimed = target?.el ?? null;
    // The cursor's half, written where the box's half is decided, so the hand cannot
    // stand over a press the paint knows takes nothing. `aiming` alone says the page
    // is armed; this says the aim has landed on something.
    document.body.classList.toggle("lf-over-item", Boolean(aimed));
    const r = aimed && shownRect(aimed, new Map());
    if (!r) {
      aimBox.style.display = "none";
      aimBox.removeAttribute("data-for");
      paintInspect(null);
      return;
    }
    const { left, top, right, bottom } = r;
    aimBox.setAttribute("data-for", aimed.id);
    // The item's own corner radius, so the ring hugs the corner the item draws.
    Object.assign(aimBox.style, {
      display: "block",
      left: left + "px",
      top: top + pageScroller.scrollTop + "px",
      width: right - left + "px",
      height: bottom - top + "px",
      borderRadius: getComputedStyle(aimed).borderRadius,
    });
    paintInspect(designIsOn() ? target : null, { left, top });
  }
  // The name of what design mode is aimed at, at the box's top-left corner — above it
  // where there is room, inside it where there isn't (the banner sits at the top edge).
  // Document-anchored like the box, so a scroll moves the two together between the events
  // that re-derive them.
  function paintInspect(target, corner) {
    inspectEl.classList.toggle("lf-shown", Boolean(target));
    if (!target) return;
    const name = target.part
      ? `${target.part} · ${designName(target.el)}`
      : designName(target.el);
    if (inspectEl.textContent !== name) inspectEl.textContent = name;
    const above = corner.top - inspectEl.offsetHeight - 2;
    inspectEl.style.left = `${Math.max(2, corner.left)}px`;
    inspectEl.style.top = `${(above >= 0 ? above : corner.top + 2) + pageScroller.scrollTop}px`;
  }
  const pointer = { x: -1, y: -1 }; // last seen, so a repaint can re-answer the hover
  let hovering = null;
  let hoverQueued = false;
  const marksOf = (id) => marked.get(id) ?? [];
  const allMarks = () => [...marked.values()].flat();
  // What a reader who cannot see the paint is told. A highlight is glyphs, not an element, so
  // it builds no accessibility node — where a <mark> wrapper was a `mark` node, the paint is
  // nothing at all, and a passage carrying a comment reads exactly like one that doesn't.
  // Neither relation ARIA offers brings it back on something not focusable: NVDA ignores
  // aria-describedby there in browse mode and reports none of the labelling attributes on a
  // bare p or div at all, VoiceOver reads it only on an interactive, image or landmark role,
  // and aria-details is supported unevenly and says only that details exist. What every
  // screen reader announces in every mode is text, so the fact is carried as text — one
  // hidden, unselectable line inside whatever holds the mark, saying how many comments are
  // on it.
  //
  // Coarser than the mark, and deliberately: it names the block a passage sits in rather than
  // the passage, because naming the passage means wrapping it, and wrapping is what a redraw
  // between a mousedown and its mouseup turns into a swallowed click. The panel still carries
  // each thread's own quote. Written only where the text differs from what is already there,
  // because a screen reader rebuilds its buffer on every mutation and this pass runs on every
  // poll.
  function noteMarks(noted) {
    for (const [holder, threadIds] of noted) {
      const note =
        holder.querySelector(`:scope > .${NOTE}`) ??
        holder.appendChild(offer("button", NOTE));
      note.lfThreads = threadIds;
      note.onclick = () => {
        setPanel(true);
        const id = note.lfThreads.find((threadId) =>
          threadsBox.querySelector(`:scope > .lf-thread[data-id="${threadId}"]`),
        );
        const thread =
          id && threadsBox.querySelector(`:scope > .lf-thread[data-id="${id}"]`);
        if (!thread) return;
        thread.focus({ preventScroll: true });
        scrollToThread(id);
      };
      const n = threadIds.length;
      const said = `${n} comment${n === 1 ? "" : "s"}`;
      if (note.textContent !== said) note.textContent = said;
    }
    for (const note of pageQueryAll(`.${NOTE}`))
      if (!noted.has(note.parentElement)) note.remove();
  }

  function paintAnchors(threads = buildThreads()) {
    if (!anchorsReady()) return;
    for (const where of allMarks())
      if (where instanceof Element) where.classList.remove("lf-mark-el");
    for (const el of pendingOutline) el.classList.remove("lf-mark-el", PENDING);
    marked.clear();
    placed.clear();
    pendingOutline = [];

    const text = pageText(); // read once, for every anchor this pass places
    const posted = [];
    const noted = new Map(); // element -> ordered thread ids marking something inside it
    for (const t of threads) {
      if (!t.root.anchor) continue;
      const found = resolveAnchor(t.root.anchor, text);
      if (!found) continue;
      // Where the thread's passage lands in this version, recorded for every thread the
      // page still holds — the resolved ones too, which take no paint but do take a place
      // in the panel's order and keep the one they had while they fold out of it.
      placed.set(t.root.id, found.element ?? elementOver(found.segments[0].node));
      if (t.resolved) continue;
      if (found.element) {
        // The boxes the element shows through, for the same reason the ask ring hangs on
        // those: an outline needs a box, and a wrapper that generates none took its ring
        // to the document's origin and drew nothing there. The record is what the pass
        // clears, what the pointer hit-tests, and what the composer stands off, so all
        // three follow the paint by holding the parts rather than the element.
        const parts = shownParts(found.element);
        for (const part of parts) part.classList.add("lf-mark-el");
        marked.set(t.root.id, parts);
      } else {
        const ranges = found.segments.map((seg) => rangeOf([seg]));
        marked.set(t.root.id, ranges);
        posted.push(...ranges);
      }
      // Where the line goes: every block the passage crosses, so the reader of any of them
      // hears it — or, for a passage that sits in no block of its own, the element the
      // anchor names, which is where the runtime already puts chrome a widget has to live
      // with (a card's drag grip). Never the inline run or the body div in between, because
      // a widget reads those back as its own: lf-draft seeds the editor a user types
      // into from its body div, and a line inside it is chrome in the text they send back.
      const blocks = found.element
        ? [found.element]
        : [...new Set(found.segments.map((seg) => blockAt(seg.node)))].filter(Boolean);
      // Not inside the chrome: the line is the runtime's word inside the page's own
      // blocks, and a design comment on a runtime part is on chrome the panel already
      // reads out — an aria-hidden injected note button would be focusable content nobody
      // is told about.
      for (const holder of blocks.length ? blocks : [sectionOf(t.root.anchor)])
        if (holder && !inChrome(holder))
          noted.set(holder, [...(noted.get(holder) ?? []), t.root.id]);
    }

    // The composer's own passage, in the accent rather than the mark's own ink, so a draft
    // never reads as a posted comment. An element a thread already outlines keeps the posted
    // colour: there is one outline to give, and the thread's is the clickable one.
    //
    // The ⌥ aim does not wear this paint, though it is the same fact one step earlier:
    // a promise has to interrupt where an annotation may whisper, so the aim has a box
    // of its own in the chrome's layer (refreshAim, and the .lf-aim rule's account of
    // why). An open composer doesn't stand the aim down — a press while the box is up
    // re-anchors it to the aimed item (openOnItem) — so the two can show at once, which
    // is the true state: where the draft stands, and where a press would move it.
    const draft =
      composerIsOpen() && composerAnchor()
        ? resolveAnchor(composerAnchor(), text)
        : null;
    // Where the draft's passage is, recorded the way the threads' is, because placeComposer
    // has to keep the box off it. An element a thread already outlines belongs
    // in the record too — it is marked, just in the posted colour rather than the accent.
    pendingMarks = draft
      ? draft.element
        ? shownParts(draft.element)
        : draft.segments.map((seg) => rangeOf([seg]))
      : [];
    const pending = [];
    if (draft?.element) {
      // Part by part, because a thread's outline is claimed the same way: the draft takes
      // whichever boxes are still free and leaves the rest in the posted colour. The record
      // above is the parts too, so placeComposer stands the box off the passage the reader
      // can see rather than off a wrapper whose rect sits at the top of the document.
      const taken = allMarks();
      for (const part of pendingMarks)
        if (!taken.includes(part)) {
          part.classList.add("lf-mark-el", PENDING);
          pendingOutline.push(part);
        }
    }
    if (draft?.segments) pending.push(...pendingMarks);

    // The composer's echo of its own passage, decided here because here is where it is known
    // whether the page is showing that passage. Usually it is — the box opens beside the words
    // it just marked, and printing them inside it says the same sentence twice, side by side.
    // So the quote is the fallback rather than the statement: it shows where the mark can't,
    // which is where this version no longer holds the passage — a draft the user carried
    // onto a newer version, whose text survived the trip when its passage didn't. Dashed and
    // muted, the panel's detached treatment, for the same fact.
    //
    // Scrolled out of view looks like that case and is not: the passage is still there, one
    // scroll back, and the reader put it there seconds ago. A quote coming and going with the
    // scroll position would resize the box under the hands typing in it.
    //
    // Out of sight is not gone: a painted mark has no accessibility exposure at all, so the
    // quote stays in the tree as the box's description whichever way it renders. Written only
    // when it changes, because assigning textContent replaces the node even with the same
    // string, and this pass reruns whenever a comment arrives — a stranded quote is the only
    // copy of that passage left, so it is text a user may be selecting to keep.
    const label = composerIsOpen()
      ? anchorLabel(composerAnchor(), composerAbout())
      : "";
    if (composerQuote.textContent !== label) composerQuote.textContent = label;
    // A design comment's label stays: the outline says which element, and only the words
    // say the comment is about the layer and which control the press landed on.
    composerQuote.classList.toggle(
      "lf-unseen",
      !label || (Boolean(draft) && !composerAbout()),
    );

    // Ranked so each reading survives the ones under it: a posted mark, the hover over it,
    // the standing comment's own mark, and the draft above all three. A higher highlight
    // supplies only the properties it states, so the standing mark under the pointer takes
    // the hover's wash and keeps its own ink. The
    // passage under the pointer answers the pointer.
    CSS.highlights.set(MARK, new Highlight(...posted));
    CSS.highlights.set(
      PENDING,
      Object.assign(new Highlight(...pending), { priority: 3 }),
    );
    noteMarks(noted); // and the same fact for a reader who can't see any of it
    paintStanding(); // the ranges are new objects and the element classes were just cleared
    // The semantic thread may be unchanged while this pass replaced every Range or
    // element part that paints its hover. Rebind the projection before geometry decides
    // whether the parked pointer still indicates that thread at all.
    if (hovering || hoverThread || hoverParts.length) paintHover(hovering);
    pageShifted(); // the content moved: the hover, a held aim's promise, the legend ask again

    paintThreadQuotes();

    // A message pointing at the page — [the group](#d-channel) — travels by the
    // browser's own fragment navigation, which is already the whole feature within one
    // document: collapsed content wears hidden="until-found", so the jump fires
    // beforematch and the owning tab or settled group opens itself. Opened in a new tab
    // it is an arrival rather than a jump, and landArrival is what answers it there.
    // What the browser has no answer for is the id
    // this version hasn't got. A comment outlives the version it was written on, so
    // that happens without anyone doing anything wrong — and unmarked, the reference
    // reads live, moves nothing on the press, and leaves a fragment nobody holds in the
    // URL for the next load to honor. So it wears the same detached face a quote whose
    // passage left the page wears, asked of the same resolveAnchor, and its press is
    // taken rather than spent. aria-disabled because the title only reaches a pointer.
    for (const a of panel.querySelectorAll(MSG_REF)) {
      const id = fragmentId(a.getAttribute("href"));
      const alive = Boolean(resolveAnchor({ section: id }));
      a.classList.toggle("detached", !alive);
      if (alive) a.removeAttribute("aria-disabled");
      else a.setAttribute("aria-disabled", "true");
      a.title = alive
        ? `Jump to § ${id}`
        : `§ ${id} isn't in the version you're viewing`;
    }
  }

  // Re-resolve marks after a package replaces derived passage nodes during replay.
  let projectionAnchorPaintQueued = false;
  document.addEventListener("lf-projection", () => {
    if (projectionAnchorPaintQueued) return;
    projectionAnchorPaintQueued = true;
    queueMicrotask(() => {
      projectionAnchorPaintQueued = false;
      paintAnchors();
    });
  });

  // A reference a message makes into the page: its own Markdown link, or one a widget
  // in its frozen markup writes (a lf-option's `for`). One selector, so what the paint
  // above dresses and what the press below refuses are the same set.
  const MSG_REF = '.lf-msg-body a[href^="#"]';
  // The id a fragment names. An href holds it as the renderer percent-encoded it and
  // location.hash as the browser did; the document holds it as written. A malformed
  // escape ("#100%") keeps its own characters. One reading for both, because a reference
  // the panel paints and a URL the page arrived at name their element the same way.
  function fragmentId(fragment) {
    const raw = fragment.slice(1);
    try {
      return decodeURIComponent(raw);
    } catch {
      return raw;
    }
  }
  // The only press this layer takes from the browser: a reference this version can't
  // follow. Everything else — the travel, the reveal, the back button — is the
  // platform's, and an exported copy keeps it by having a real href to jump through.
  panel.addEventListener("click", (ev) => {
    const a = ev.target.closest(MSG_REF);
    if (a && !resolveAnchor({ section: fragmentId(a.getAttribute("href")) }))
      ev.preventDefault();
  });

  // Which thread's mark is under a point. A painted range is not an element, so the pointer
  // finds it by the boxes the range occupies rather than by hit-testing the DOM — asking for
  // the caret position instead would claim the empty space past the end of a short line.
  function markAt(x, y) {
    const over = document.elementFromPoint(x, y);
    if (!pageWords(over)) return null;
    // The retargeted element answers the chrome question, whose subject is which layer the
    // pointer is in; an element mark needs the tree's own answer, because a host contains
    // every mark staged inside it and so tells none of them apart.
    const deep = elementFromPointAcross(x, y);
    for (const [id, marks] of marked)
      for (const where of marks) {
        const hit =
          where instanceof Range
            ? [...where.getClientRects()].some(
                (r) => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom,
              )
            : containsAcross(where, deep);
        if (hit) return id;
      }
    return null;
  }

  // Bring an element in the document to the position its caller names. A thread's element
  // anchor takes the middle; an Ask takes the readable start so its context comes before
  // its control. Which box does the travelling is scrollerFor's answer, asked here rather
  // than assumed: the document's scroller was written into this twice, so an element
  // standing in the panel's list was taken into view by the platform and then had this
  // travel spent on the page behind it, moving a reader who had asked for nothing there.
  // Reveal first, since opening a tab or settled group moves
  // everything below it. For a centred destination, "the middle" means the viewport's:
  // scrollIntoView measures against the scroller's own
  // scroll-padding-top — declared so a native fragment jump clears the banner — and every
  // "center" through it therefore landed 27px low. An element taller than the viewport has
  // no middle to show, and centring one puts its opening words above the top edge, so it
  // takes that same banner clearance instead and the reader starts at the start.
  //
  // The viewport is the scroller's own box rather than the window's, which is the same
  // number for the document — body is the page's scroller and is the window's height — and
  // is the panel's list where that is what scrolls.
  //
  // It glides, because a page the reader is already holding is one the motion keeps their
  // place in — the same reason a restore doesn't (jumpBy). An arrival passes "instant" for
  // exactly that reason: a document that appeared a moment ago holds no place to keep, so
  // the glide would be animating from nowhere.
  function centreBy(where, block = "center", box = pageScroller) {
    const rect =
      where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
    // The scroller's own box rather than the window's: the same number for the document,
    // whose scroller is body, and the list's own where the list is what scrolls.
    const view = shownBox(box);
    const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
    const place =
      where instanceof Range
        ? (view.height - rect.height) / 2
        : block === "start"
          ? clear
          : Math.max((view.height - rect.height) / 2, clear);
    return rect.top - view.top - place;
  }
  function scrollToElement(el, behavior = SCROLL, block = "center") {
    reveal(el);
    el.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "instant" });
    const box = scrollerFor(el);
    if (!under(el, box)) return;
    jumpBy(centreBy(el, block, box), behavior, box);
  }

  // Move to where a thread is painted, if it still is — asked of the pass's own record, so the
  // panel and the page can't disagree about whether the passage survived. A painted range has
  // no element to scroll into view, so its own box does the work.
  //
  // Every "show me that comment's passage" route ends here. The focus its caller already
  // placed in the thread owns the standing paint; this function owns only the travel. It
  // makes the target's box visible in both axes, then glides the exact mark to the centre
  // of the region that holds it. No transient effect waits on that motion or survives it
  // as separate state.
  function scrollToThread(id) {
    const where = marksOf(id)[0] ?? placed.get(id);
    if (!where) return;
    if (!(where instanceof Range)) {
      reveal(where);
      if (!marksOf(id).length) paintAnchors();
      scrollToElement(marksOf(id)[0] ?? where);
      return;
    }
    const holder = where.startContainer.parentElement;
    reveal(holder);
    // Sideways first, and only as far as it takes: a passage inside a wide `pre` or a
    // rendered diagram sits in a box with its own horizontal scroll, which the vertical
    // jump below cannot reach — scrolling to it in one axis leaves it off-screen in the other.
    holder.scrollIntoView({ block: "nearest", inline: "nearest", behavior: "instant" });
    jumpBy(centreBy(where), SCROLL);
  }

  // Pointer feedback a wrapped <mark> got from :hover and cursor: pointer, neither of which
  // ::highlight() can carry — it styles glyphs, not boxes. Same hit-test as the click, so
  // what lights up is what would open. It is a function of where the pointer is and what the
  // page's geometry is, so everything that moves either asks again: the pointer moving, the
  // page scrolling under a still pointer, and the pass redrawing the ranges themselves.
  //
  // The pointer can indicate a thread from either surface, and the panel is the other one.
  // A card is the thread's view in the list the way a mark is its view in the prose, so
  // resting on the card lights the passage exactly as resting on the passage lights it —
  // the same wash, because it is the same fact, and a second strength would be a third
  // thing to learn on a page that already asks the reader to tell a mark from a standing
  // mark. It answers the question a reader scanning a full list keeps asking, which of
  // these is about what, without a press and without a travel they may not want; the
  // standing mark answers it for the one comment they chose, and this answers it for the
  // one under their hand.
  //
  // One answer rather than two, because the pointer is in one place: markAt refuses a point
  // that lands in the chrome, so the panel's reading and the page's cannot both name a
  // thread. That is also why the two are read here rather than painted by separate hands —
  // a second writer to this highlight would be overwritten by whichever frame ran last, and
  // the hit-test runs on every pointer move.
  //
  // The whole card and not the quote alone, though the quote is the part that presses. The
  // card is where the eye is while it reads the comment, and the question arrives there
  // rather than on the three clamped lines at the top; a reader who wanted the quote's
  // press would already be on it.
  const HOVER = "lf-mark-hover";
  const hoveredThreadOf = () => threadsBox.querySelector(".lf-thread:hover");
  let hoverParts = [];
  let hoverThread = null;
  const hoverCardOf = (id) =>
    id ? threadsBox.querySelector(`:scope > .lf-thread[data-id="${id}"]`) : null;
  function paintHover(id) {
    hovering = id;
    // The page and panel are reciprocal views of the thread. The highlight paints the
    // passage when the pointer is on its card; this class paints the card when the pointer
    // is on its passage. One writer keeps them on the same id, and keeping the node lets a
    // sweep touch only the two cards whose answer changed.
    const thread = hoverCardOf(id);
    if (hoverThread !== thread) {
      hoverThread?.classList.remove(HOVER);
      thread?.classList.add(HOVER);
      hoverThread = thread;
    }
    const where = marksOf(id);
    // Both kinds of anchor, for the reason paintStanding takes both: one question about one
    // thread, and a reading that answered only the passages with words left an element
    // anchor saying nothing back. Only what changed, and guarded on each side, for the
    // reason spelled out there — this runs on every frame of a pointer sweep.
    const parts = where.filter((mark) => mark instanceof Element);
    for (const part of hoverParts)
      if (!parts.includes(part)) part.classList.remove(HOVER);
    for (const part of parts)
      if (!part.classList.contains(HOVER)) part.classList.add(HOVER);
    hoverParts = parts;
    CSS.highlights.set(
      HOVER,
      Object.assign(new Highlight(...where.filter((mark) => mark instanceof Range)), {
        priority: 1,
      }),
    );
  }
  // Which comment the reader is standing in, said out on the page. The panel has always
  // answered it on its own surface — the thread holds the focus, and a press on a mark
  // flashes the thread it opens — while the page answered nothing back: every posted mark
  // wears one wash, so a reader sent from a comment to its passage arrived among a dozen
  // identical marks with no way to tell which one they had asked to see. The j/k walk's
  // comment already called the panel and the page "two views of the same thread"; this is
  // the view that was missing.
  //
  // Derived from the focus rather than written where the travel put the reader, for the
  // reason markHere gives about the ask ring: a mark written at the arrival says where the
  // reader was *sent*, and goes on saying it after they have clicked away, read on down the
  // page and come back tomorrow. Every way into a thread then paints it — the quote's press,
  // j/k, `g c 2`, a plain click on the card — because they all end in the same focus, and no
  // way in has to be taught to paint.
  //
  // Read through `closest` rather than off the thread itself, so a reader typing a reply is
  // still standing in the comment they are replying to; that is exactly when knowing which
  // passage it is on is worth most.
  //
  // Above the hover and below the draft. A pointer resting on the standing mark supplies
  // the middle wash, while this higher paint keeps the strongest wash and its accent ink:
  // the cursor promises the press, and the ink answers "which one".
  const HERE = "lf-mark-here";
  let hereParts = [];
  function paintStanding() {
    const where = marksOf(focusedThreadOf()?.dataset.id);
    const parts = where.filter((mark) => mark instanceof Element);
    // Only what changed, because the anchor pass calls this and the anchor pass runs on
    // every poll: an element that keeps the class would otherwise have it taken off and put
    // straight back, writing the page's own attribute twice a poll for as long as the
    // reader stands there, and a mutation on an authored element is something this page's
    // observers hear. Both sides are guarded, because Chrome records a mutation for a
    // classList.add of a token already in the list — the same reason noteMarks writes its
    // line only when the words differ.
    for (const part of hereParts)
      if (!parts.includes(part)) part.classList.remove(HERE);
    for (const part of parts)
      if (!part.classList.contains(HERE)) part.classList.add(HERE);
    hereParts = parts;
    CSS.highlights.set(
      HERE,
      Object.assign(new Highlight(...where.filter((mark) => mark instanceof Range)), {
        priority: 2,
      }),
    );
  }
  // Coalesced to a frame: scroll outruns layout, the hit-test reads layout, and a repaint
  // asks from inside a pass that must stay cheap enough to run from a mousedown. The frame
  // is what settles the panel's half too — that reading is the browser's own :hover state,
  // and asking for it from inside the pointer event that is moving it asks mid-move.
  function refreshHover() {
    if (hoverQueued || (!marked.size && !hovering && !hoverThread)) return;
    hoverQueued = true;
    requestAnimationFrame(() => {
      hoverQueued = false;
      // The cursor stays with the page's own reading. It is the promise that a press here
      // opens something, and over a card the press on offer is the card's own — which the
      // panel already says for itself, on the quote that makes it. Unconditional because
      // toggle runs no update step when the answer has not changed, unlike the add that
      // noteMarks and the standing paint have to guard.
      const onMark = markAt(pointer.x, pointer.y);
      document.body.classList.toggle("lf-over-mark", Boolean(onMark));
      const id = hoveredThreadOf()?.dataset.id ?? onMark;
      // A reconcile normally keeps a thread node, but settlement replaces it. If the
      // pointer stayed over the same semantic thread, repaint the reciprocal class onto
      // that new card even though the id did not change.
      if (id !== hovering || hoverCardOf(id) !== hoverThread) paintHover(id);
    });
  }
  // The pointer's place is read off a pointer event and not off `mousemove`, because the
  // legacy mouse events round clientX/clientY to whole pixels and the browser hit-tests the
  // position they were rounded from. Every consumer of this record asks a hit-test question
  // — what a press would take, whether a mark is under the hand — so a rounded point is an
  // answer about somewhere the pointer is not, and within a pixel of a boundary it is a
  // different element: an ⌥ aim outlined the option above the one the press then took,
  // because the outline asked elementFromPoint at the rounded point while the press read
  // the target the browser resolved at the true one.
  document.addEventListener("pointermove", (ev) => {
    pointer.x = ev.clientX;
    pointer.y = ev.clientY;
    refreshHover();
  });
  // A finger arrives already down. A tap dispatches `pointerdown` and then the
  // compatibility mouse events — no `pointermove` anywhere in it — so a record kept from
  // movement alone is still its start value when the click asks, and a consumer with no
  // guard asks elementFromPoint about a point off the page: the quote under the finger
  // opened nothing. The press is the pointer's place too, and on touch it is the only
  // statement of it. No hover refresh with it: a mouse has already moved to this point
  // and refreshed there, and there is no hover to paint under a finger.
  document.addEventListener("pointerdown", (ev) => {
    pointer.x = ev.clientX;
    pointer.y = ev.clientY;
  });
  // The page moving under a parked pointer is the pointer moving over the page: what a
  // press would take, whether a mark is under the hand, and where every legend box
  // stands can all change with no mouse event to say so, and a box left over the old
  // item promises a press the click no longer makes. One repaint set for every door
  // that says so — a scroll, a window resize, a replay's marks landing (paintAnchors),
  // a widget's FLIP settling, and the reflows only the legend's observers hear, the
  // panel opening re-centring the column among them.
  function pageShifted() {
    refreshHover();
    refreshAim();
    // A board scrolled sideways carries its cards out from under their boxes, and the
    // page scrolled brings items into view that had no box yet (shownRect).
    queueLegend();
  }
  // At the document and at capture, because scroll does not bubble and body is not the
  // page's only scroller: a board scrolls its columns sideways, and a card carried under
  // a parked pointer that way is the same fact as the page scrolling under it. Capture is
  // the one place every scroller's event passes.
  document.addEventListener("scroll", pageShifted, { capture: true, passive: true });

  return {
    VIEW_KEY,
    blocksOnScreen,
    captureView,
    restoreView,
    sectionOf,
    ITEM,
    isItem,
    itemAt,
    itemWord,
    itemSays,
    resolveAnchor,
    NOTE,
    marked,
    placed,
    shownBand,
    shownBox,
    shownParts,
    shownRect,
    startsAt,
    refreshAim,
    paintAnchors,
    pointer,
    fragmentId,
    markAt,
    scrollToElement,
    scrollToThread,
    paintStanding,
    refreshHover,
    pageShifted,
    get pendingMarks() {
      return pendingMarks;
    },
  };
}
