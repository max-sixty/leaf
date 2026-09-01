import { shownBox } from "./geometry.js";
import { moveScrollerBy } from "./scrolling.js";

/* Semantic reading position preserved across authored-document replacement. */
const VIEW_KEY = "lf-view";
const LANDMARK_CAP = 160;

export function createViewContinuity(dependencies) {
  const {
    TEXT_BLOCK,
    banner,
    closestAcross,
    containsAcross,
    cut,
    elementById,
    focusDestination,
    focused,
    inChrome,
    landedAt,
    pageScroller,
    pageText,
    quoteFrom,
    rangeOf,
    resolveAnchor,
    reveal,
    runtime,
    setLanded,
    textNodesUnder,
  } = dependencies;

  // Following a new version replaces the authored main, whether the live root keeps this
  // document or historical travel opens another one. A raw replacement leaves the reader
  // at the top mid-session, standing nowhere in the walk they were making. Where they are
  // rides across as one semantic view — and through tabStore on document travel, per-tab
  // because a place in a page shouldn't outlive it. Two things are recorded, because
  // decisionPosition reads two the runtime can write down: the passage they were reading, and
  // the ask the a/A walk had stepped them to. The passage travels as a landmark rather
  // than a pixel offset, since content moves between versions: re-find it by its text
  // within its section, then the section alone, and only fall back to the raw offset when
  // neither survived the revision. The panel's own open state is restored separately
  // (PANEL_KEY); because that runs first, the column is already reflowed by the time we
  // scroll.

  // The page's own text blocks the reader can see, in document order, with the rect of each
  // one's first line — one reading of what is in front of them, for the two questions that
  // ask it: which passage a version change should land them back on (below), and where a
  // walk over the page's decisions starts when they have pointed at nothing (decisionPosition).
  // A block's landmark is the top of its first line (a range), not its border box; restore
  // measures the matched text the same way, so the line box's leading cancels out.
  function* blocksOnScreen() {
    // Read the painted edge directly. The declared height may contain a safe-area
    // `calc()`, whose serialized value is not a number even though its box is exact.
    const bannerBottom = banner.getBoundingClientRect().bottom;
    for (const block of document.querySelectorAll(TEXT_BLOCK)) {
      // [hidden] needs an explicit skip: hidden="until-found" resolves to
      // content-visibility, under which descendants still report real rects —
      // but what's behind an inactive tab isn't what the reader is reading.
      if (inChrome(block) || block.closest("[hidden]")) continue;
      const range = document.createRange();
      range.selectNodeContents(block);
      const rect = range.getBoundingClientRect();
      if (rect.height && rect.bottom > bannerBottom) yield [block, rect];
    }
  }

  // The quote and the section it's searched in come from the same block, or the search is
  // filtered to a section the text isn't in and can only ever fail — restore then falls back
  // to the section, which doesn't absorb content added above the reader inside it.
  function captureView() {
    const view = { revision: runtime.currentRevision, y: pageScroller.scrollTop };
    // Where the decision walk left off, which is the reader's place stated more exactly than
    // any block can state it — the walk put them there on purpose. Its element identity
    // does not survive an authored-main replacement, and the module variable does not
    // survive document travel, so the id is the one form both can restore. The ring is not
    // recorded beside it: it is painted from focus, and another document starts on the page.
    view.decision = landedAt()?.id;
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
  function restoreView(view) {
    // Where the walk left off, put back before the scroll below restores the coarser
    // reading of the same fact — and put back whether or not this version answered that
    // decision, since a decision the reader has not stepped off is still the one they would step
    // from. The document's own lookup rather than elementById: the decision list is the
    // document's (openDecisions), and a landing inside a shadow tree is one decisionStep could never
    // measure against. A thread's decision is not here yet — the panel is rebuilt from the log
    // on the first poll, which is behind this — so the record answers for the page's decisions
    // and says nothing about the panel's, rather than restoring a second time later over a
    // walk the reader has made since.
    setLanded((view.decision && document.getElementById(view.decision)) || null);
    const text = pageText();
    const found = view.quote && resolveAnchor(view, text);
    if (found?.segments) {
      reveal(found.segments[0].node.parentElement); // the passage may sit behind a tab
      moveScrollerBy(
        pageScroller,
        rangeOf(found.segments).getBoundingClientRect().top - view.quoteTop,
      );
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
      moveScrollerBy(pageScroller, shownBox(section).top - view.sectionTop);
    } else pageScroller.scrollTo({ top: view.y, behavior: "instant" });
  }

  // Where the reader is standing in the authored page, written down so the swap can hand
  // it back. The key line over a focused pick mark offers "1–2 toggle the nth"; those are
  // presses the reader is about to make, and a replacement that dropped the focus onto
  // body took the offer down with it — the digit then picked nothing, silently. Node
  // identity does not survive the swap, so the place is stated the way the decision above
  // is, by id: the nearest element carrying one, and within it the control by kind and
  // position, since a grip or a pick mark is the runtime's and carries no id of its own.
  // A control staged in a shadow tree is out of the place's own query and comes back as
  // the place. The chrome stays through a swap and so does focus inside it, so a reader
  // standing there has nothing to write down. The place is an authored element, read the
  // way the anchor pass reads which section a passage is in: an injected row carries an
  // id too, and is not a place a revision keeps.
  function captureStanding() {
    const held = focused();
    if (!held || held === document.body || inChrome(held)) return null;
    const main = document.querySelector("body > main");
    const place = closestAcross(held, "[id]:not(.lf-ui)");
    if (!place || !main || !containsAcross(main, place)) return null;
    if (place === held) return { id: place.id };
    // The first class is the one the control was built with; later ones are state the
    // fresh control will not be wearing yet. Escaped, since an authored class need not
    // be a bare identifier.
    const kind = [held.localName, held.classList[0] && CSS.escape(held.classList[0])]
      .filter(Boolean)
      .join(".");
    return {
      id: place.id,
      kind,
      index: [...place.querySelectorAll(kind)].indexOf(held),
    };
  }
  // The same control where the revision kept it; the place where it kept only that; and
  // nothing where it kept neither — a reader whose item the revision removed is standing
  // nowhere, and body, where the page's own keys are live, is the honest answer.
  function restoreStanding(standing) {
    if (!standing) return;
    // Only where the swap left the reader standing nowhere. The activation settles its
    // modules asynchronously after the swap, and a reader who moved into the chrome
    // across that gap has taken a place of their own.
    const held = focused();
    if (held && held !== document.body) return;
    const place = elementById(standing.id);
    if (!place) return;
    const control =
      standing.kind === undefined
        ? place
        : (place.querySelectorAll(standing.kind)[standing.index] ?? place);
    focusDestination(control);
  }

  function installArrival({ fragmentId, ready, scrollToElement, tabStore }) {
    // Ordinary reload and history travel belong to the browser. The root is its document
    // scrollport, so native restoration is both more complete and less surprising than a
    // parallel session-store reading. Leaf intervenes after upgrades only for two semantic
    // cases the platform cannot know: a fresh URL aimed at a target generated or hidden by
    // a widget, and travel to a different authored revision where a passage is a better
    // landmark than the old document's pixels.
    const navigationType = performance.getEntriesByType("navigation")[0]?.type;
    // Parsed inside its own guard, which is a different question from whether the store
    // answered: tabStore hands back null for a store that refused, and what a page wrote
    // there is only JSON while every version of this runtime agrees about the shape. A
    // landmark that no longer parses costs the reader their scroll position; throwing here
    // would cost them the page, at module top level, with nothing else having run.
    const savedView = (() => {
      try {
        return JSON.parse(tabStore.get(VIEW_KEY) || "null");
      } catch {
        return null;
      }
    })();
    addEventListener("pagehide", () => {
      if (!ready()) return;
      tabStore.set(VIEW_KEY, JSON.stringify(captureView()));
    });
    function landArrival() {
      const aimed =
        navigationType === "navigate" &&
        resolveAnchor({ section: fragmentId(location.hash) })?.element;
      if (aimed) scrollToElement(aimed, "instant");
      else if (
        navigationType === "navigate" &&
        savedView &&
        savedView.revision !== runtime.currentRevision
      )
        restoreView(savedView);
    }
    return { landArrival, savedView };
  }

  return {
    blocksOnScreen,
    captureStanding,
    captureView,
    installArrival,
    restoreStanding,
    restoreView,
  };
}
