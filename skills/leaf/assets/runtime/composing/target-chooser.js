/* This module owns the target chooser and whole-page text search. Its transient hints,
 * search marks, and status are synchronous Lit projections over native controller state. */
import { aimTargets, anchoringIsReady } from "../anchor-resolution.js";
import { bindings } from "../keyboard/bindings.js";
import { el, LAYOUT } from "../widget-elements.js";
import { html, nothing, render, repeat } from "../../vendor/browser-runtime.js";

import {
  blockAt,
  contextAround,
  cut,
  findText,
  inChrome,
  pageText,
  quoteFrom,
  rangeOf,
} from "../passages.js";
import { shownParts } from "../geometry.js";
import { focused } from "../keyboard/scopes.js";
import { repaint } from "../repaint.js";
import {
  createHintSession,
  HINT_KEYS,
  hintCodes,
  renderKeys,
} from "../keyboard/hints.js";
import { chromeTop, keyBadgePlacement } from "../keyboard/key-badge-placement.js";
import {
  keySequenceModel,
  keySequenceTemplate,
  progressStates,
} from "../keyboard/presentation.js";
import { announce } from "../notifications.js";
import { beginWalk, walkPosition } from "../walk-position.js";

import { allButCommandReference } from "../keyboard/register.js";

// The target chooser and page search have separate faces. Hints and the active search result are paint only;
// the search box is a real control, kept beside them so its focus and accessible name are
// the platform's rather than a keyboard interaction's imitation of one.
export const targetChooserHintLayer = el("div", "lf-ui lf-target-chooser-hints");
targetChooserHintLayer.setAttribute("aria-hidden", "true");
export const pageSearchSurface = el("div", "lf-ui lf-page-search");
pageSearchSurface.setAttribute("role", "search");
pageSearchSurface.hidden = true;
const pageSearchInput = document.createElement("input");
pageSearchInput.className = "lf-page-search-box";
pageSearchInput.type = "search";
pageSearchInput.name = "page-search";
pageSearchInput.autocomplete = "off";
pageSearchInput.spellcheck = false;
pageSearchInput.maxLength = 160;
pageSearchInput.placeholder = "Search page text";
pageSearchInput.setAttribute("aria-label", "Search page text");
const pageSearchStatus = el("span", "lf-page-search-status");
pageSearchStatus.setAttribute("role", "status");
pageSearchSurface.append(pageSearchInput, pageSearchStatus);

// Target choosing and whole-page text search. `s` opens a viewport-local map of
// the same stable addressables and visual parts Alt-click reaches, then opens Comment on the
// chosen target; `/` opens the page's text search directly or from that map.
//
// `keyboard/hints.js` owns the map itself: arming, codes, the typed prefix, the audible
// walk, the scroll freeze, and the paint. What this module declares is which members the
// map holds and where each chip sits among them. An ancestor and descendant painting the
// same visible box name one target, and the innermost remains, matching direct aim. A
// target whose visible box is strictly smaller and fully enclosed by another steps its
// chip right once per enclosing box, so nested corners stay apart; equal boxes outside
// one containment chain stay at the same depth and the shared placement pass separates
// their chips. Both the seat and that step are read off one box per paint, which is why
// the reading here is a member's whole box rather than the corner the Go-to map hangs a
// chip on; a member the bottom chrome's lane covers has no box left and leaves the map.
//
// `/` opens a real search input over the whole page reading, either directly from the
// page or from the visible target hints. Tab walks repeated occurrences and Enter makes a
// native browser Selection from the active match. Once the prompt closes, n repeats that
// accepted search and N reverses it. Escape returns to the surface that opened search:
// the page after a direct `/`, or the visible hints after `s` then `/`. The interaction keeps
// `?` available and claims the rest of the page's keyboard while it stands.

export function createTargetChooser({
  scrollToRange,
  hintChrome,
  commentOnTarget,
  updateFab,
  fabAnchorAt,
}) {
  const HINT_INDENT = 10;

  let chooserOpen = false;
  let pageSearchOpen = false;
  let matches = [];
  let active = -1;
  let opener = null;
  let searchReturnsToHints = false;
  let repeatedSearch = null;
  const matchNodeIds = new WeakMap();
  let nextMatchNodeId = 1;

  // Target elements and text coordinates stay outside the immutable readings. Lit receives
  // only opaque primitive identities, retaining unchanged hint and keycap nodes on repaint.
  const hintRenderKey = renderKeys();

  const matchRenderKey = (identity, index) => `${identity}\u0000${index}`;

  // One reading of the room the reader has, shared by every member of a pass: the clips
  // over their common ancestors are walked once, and admission, exposure, and paint read
  // the same boxes.
  const room = keyBadgePlacement;
  // A fixed sheet can cover a page box without clipping it. Hints live above the chrome,
  // so geometry alone would put a key on the thread panel for a card hidden behind it.
  // Ask the rendered stack at the hint's corner; pointer-events:none keeps an existing
  // hint from answering this question itself.
  const exposed = (box) => {
    if (!box) return false;
    const x = Math.max(0, Math.min(innerWidth - 1, box.left + 1));
    const y = Math.max(chromeTop(), Math.min(innerHeight - 1, box.top + 1));
    return !inChrome(document.elementFromPoint(x, y));
  };
  // Chromium retains geometry for descendants suppressed by a closed disclosure. Ask
  // visibility before geometry so those descendants cost no box reads. A display: contents
  // addressable has no box of its own and stays eligible through a visible child.
  const targetShown = ({ element }) =>
    element.checkVisibility() ||
    (getComputedStyle(element).display === "contents" &&
      shownParts(element).some((part) => part.checkVisibility()));

  function firstShown(range, owner, reading) {
    const clip = reading.clipOver(owner);
    if (!clip) return null;
    return (
      [...range.getClientRects()]
        .map((box) => reading.clearPart(box, clip))
        .find(exposed) ?? null
    );
  }

  const sameVisibleBox = (a, b) =>
    Math.abs(a.left - b.left) < 0.5 &&
    Math.abs(a.top - b.top) < 0.5 &&
    Math.abs(a.right - b.right) < 0.5 &&
    Math.abs(a.bottom - b.bottom) < 0.5;

  function visibleTargets() {
    const reading = room();
    const targets = aimTargets()
      .filter(({ element }) => !inChrome(element))
      .filter(targetShown)
      .map((target) => ({
        ...target,
        rect: reading.visibleBounds(target.element),
      }))
      .filter(({ rect }) => exposed(rect))
      .sort((a, b) => a.rect.top - b.rect.top || a.rect.left - b.rect.left);
    // Direct aiming chooses the innermost stable addressable under the pointer. When an
    // ancestor and descendant paint the same visible box, naming both would offer two
    // keys for that one choice. Keep distinct nested extents and unrelated overlaps.
    const unique = targets.filter(
      (outer) =>
        !targets.some(
          (inner) =>
            inner !== outer &&
            outer.element !== inner.element &&
            outer.element.contains(inner.element) &&
            sameVisibleBox(outer.rect, inner.rect),
        ),
    );
    const codes = hintCodes(unique.length);
    return unique.map((target, index) => ({ ...target, code: codes[index] }));
  }

  // How many of the map's other members enclose this one, counted over the boxes of one
  // paint. Two corners in the same place would name two different targets, so each
  // enclosed chip steps right once per box around it. Strictly larger in one dimension,
  // because an equal box is the same place rather than a box around it.
  const enclosedBy = (box, boxes) =>
    boxes.filter(
      (outer) =>
        outer !== box &&
        outer.left <= box.left &&
        outer.top <= box.top &&
        outer.right >= box.right &&
        outer.bottom >= box.bottom &&
        (outer.right - outer.left > box.right - box.left ||
          outer.bottom - outer.top > box.bottom - box.top),
    ).length;

  // `withHints` opens the shared mode without a target map: a direct slash is page
  // search over the whole document, and reading a viewport-local map it would then hide
  // is work for nobody.
  function setTargetChooser(on, restore = false, withHints = true) {
    if (on && !anchoringIsReady()) return;
    if (on) opener = focused();
    const returnTo = !on && restore ? opener : null;
    chooserOpen = on;
    pageSearchOpen = false;
    searchReturnsToHints = false;
    matches = [];
    active = -1;
    pageSearchInput.value = "";
    pageSearchSurface.hidden = true;
    if (on && withHints) {
      const found = hints.arm();
      announce(
        found.length
          ? `Choose a target — type one of ${found.length} hints, press Tab to hear them, or slash to search the page.`
          : "There is no visible target to choose. Press slash to search the page.",
      );
    } else {
      hints.disarm();
      if (!on) opener = null;
    }
    repaint();
    if (returnTo?.isConnected) returnTo.focus({ preventScroll: true });
  }

  function setPageSearch(on) {
    pageSearchOpen = on;
    pageSearchSurface.hidden = !on;
    if (on) {
      pageSearchInput.focus({ preventScroll: true });
      presentSearchStatus();
      announce("Search the page.");
    } else {
      pageSearchInput.value = "";
      matches = [];
      active = -1;
      document.body.focus({ preventScroll: true });
      // Search may have travelled to a match, so the map the reader comes back to is read
      // again rather than being the one search covered.
      hints.invalidate();
      announce("Choose a target — type a hint, or slash to search the page.");
    }
    repaint();
  }

  function openPageSearch() {
    const fromHints = chooserOpen;
    if (!chooserOpen) setTargetChooser(true, false, false);
    searchReturnsToHints = fromHints;
    setPageSearch(true);
  }

  function matchOwner(segments) {
    const first = segments[0];
    return first ? (blockAt(first.node) ?? first.node.parentElement) : null;
  }

  function matchRect(segments, reading = room()) {
    const owner = matchOwner(segments);
    return owner ? firstShown(rangeOf(segments), owner, reading) : null;
  }

  function startingMatch(found) {
    const top = chromeTop();
    const next = found.findIndex(
      (segments) => rangeOf(segments).getBoundingClientRect().bottom > top,
    );
    return next === -1 ? 0 : next;
  }

  function presentSearchStatus() {
    const query = pageSearchInput.value.trim();
    const status = !query
      ? nothing
      : matches.length
        ? `${active + 1} of ${matches.length}`
        : "No matches";
    render(html`${status}`, pageSearchStatus);
  }

  function sameMatch(left, right) {
    return (
      left.length === right.length &&
      left.every(
        (segment, index) =>
          segment.node === right[index].node &&
          segment.start === right[index].start &&
          segment.end === right[index].end,
      )
    );
  }

  function matchIdentity(query, segments) {
    const parts = segments.map(({ node, start, end }) => {
      if (!matchNodeIds.has(node)) matchNodeIds.set(node, nextMatchNodeId++);
      return `${matchNodeIds.get(node)}:${start}:${end}`;
    });
    return `${query}\u0000${parts.join(",")}`;
  }

  function matchIsRangeable(segments) {
    return (
      segments.length > 0 &&
      segments.every(
        ({ node, start, end }) =>
          node.isConnected && start >= 0 && start <= end && end <= node.length,
      )
    );
  }

  function selectionIs(segments) {
    const selection = getSelection();
    if (
      selection.rangeCount !== 1 ||
      selection.isCollapsed ||
      !matchIsRangeable(segments)
    )
      return false;
    const selected = selection.getRangeAt(0);
    const match = rangeOf(segments);
    return (
      selected.startContainer === match.startContainer &&
      selected.startOffset === match.startOffset &&
      selected.endContainer === match.endContainer &&
      selected.endOffset === match.endOffset
    );
  }

  function matchWalkPosition(query) {
    if (!query || active < 0 || active >= matches.length) return null;
    if (!matchIsRangeable(matches[active])) return null;
    // An open search owns its highlighted match. A repeated n/N search owns a native
    // selection instead; leaving that selection retires both its readout and refresh.
    if (!pageSearchOpen && !selectionIs(matches[active])) return null;
    return {
      target: matchIdentity(query, matches[active]),
      position: active + 1,
      total: matches.length,
      qualifier: "",
    };
  }

  // Page text is the one walk source too expensive to rebuild on every chrome paint.
  // Layout invalidation is its mechanical source, so refresh only while this
  // owner is standing; the read handed to the shared walk remains a cheap cached lookup.
  function refreshMatchWalk() {
    if (walkPosition()?.kind !== "page-search") return;
    const query = pageSearchOpen ? pageSearchInput.value.trim() : repeatedSearch?.query;
    const current = matches[active];
    if (!query || !current) return;
    const found = findText(pageText(), query);
    const same = found.findIndex((candidate) => sameMatch(candidate, current));
    active = same >= 0 ? same : found.length ? Math.min(active, found.length - 1) : -1;
    matches = found;
    if (repeatedSearch && !pageSearchOpen && active >= 0) repeatedSearch.index = active;
    if (pageSearchOpen) presentSearchStatus();
    repaint();
  }

  function search() {
    const query = pageSearchInput.value.trim();
    matches = query ? findText(pageText(), query) : [];
    active = matches.length ? startingMatch(matches) : -1;
    presentSearchStatus();
    showMatch();
    repaint();
  }

  function showMatch() {
    const segments = matches[active];
    if (!segments || matchRect(segments)) return;
    scrollToRange(rangeOf(segments), "instant");
  }

  function moveMatch(direction) {
    if (!matches.length) return;
    active = (active + direction + matches.length) % matches.length;
    presentSearchStatus();
    showMatch();
    const query = pageSearchInput.value.trim();
    beginWalk("page-search", "Match", () => matchWalkPosition(query));
    announce(
      `Match ${active + 1} of ${matches.length}: ${matchDescription(matches[active])}.`,
    );
    repaint();
  }

  function matchDescription(segments) {
    const { before, after } = contextAround(pageText(), segments);
    const phrase = quoteFrom(segments);
    return cut(
      `${before ? `…${before} ` : ""}${phrase}${after ? ` ${after}…` : ""}`,
      0,
      96,
    );
  }

  function chooseTarget(target) {
    setTargetChooser(false);
    document.body.focus({ preventScroll: true });
    commentOnTarget(target);
    announce(`Chosen ${target.label}.`);
  }

  function chooseMatch() {
    const segments = matches[active];
    if (!segments) return;
    const quote = quoteFrom(matches[active]);
    repeatedSearch = { query: pageSearchInput.value.trim(), index: active };
    setTargetChooser(false);
    selectMatch(segments);
    announce(
      `Selected match: ${cut(quote, 0, 72)}. Press n for next, Shift+n for previous, or c to comment.`,
    );
  }

  function selectMatch(segments) {
    document.body.focus({ preventScroll: true });
    const selection = getSelection();
    selection.removeAllRanges();
    selection.addRange(rangeOf(segments));
    updateFab();
  }

  function repeatSearch(direction) {
    matches = findText(pageText(), repeatedSearch.query);
    if (!matches.length) {
      repeatedSearch = null;
      active = -1;
      announce("The page no longer contains that search.");
      return repaint();
    }
    const from = Math.min(repeatedSearch.index, matches.length - 1);
    active = (from + direction + matches.length) % matches.length;
    repeatedSearch.index = active;
    showMatch();
    selectMatch(matches[active]);
    const query = repeatedSearch.query;
    beginWalk("page-search", "Match", () => matchWalkPosition(query));
    announce(
      `Match ${active + 1} of ${matches.length}: ${matchDescription(matches[active])}.`,
    );
  }

  function back() {
    if (pageSearchOpen) {
      if (searchReturnsToHints) return setPageSearch(false);
      setTargetChooser(false, true);
      announce("Page search closed.");
      return;
    }
    if (hints.backOneLetter()) return;
    setTargetChooser(false, true);
    announce("Target chooser closed.");
  }

  const hintTemplate = (model) =>
    html`<span class=${model.className} data-lf-hint-code=${model.hintCode}
      >${keySequenceTemplate(model.sequence)}</span
    >`;

  // The chooser's hints and the open search's marks are two faces in one layer, and only
  // one of them stands at a time: search covers the map that opened it.
  const hints = createHintSession({
    layer: targetChooserHintLayer,
    walk: "target-chooser",
    read: visibleTargets,
    identity: (target) => target.element,
    scene: room,
    layout: (candidates, { current, reading }) => {
      const seated = candidates
        .map((target) => [
          target,
          targetShown(target) ? reading.visibleBounds(target.element) : null,
        ])
        .filter(([, rect]) => exposed(rect));
      const boxes = seated.map(([, rect]) => rect);
      const top = chromeTop();
      return seated.map(([target, rect]) => {
        const steps = [...target.code];
        return {
          candidate: target,
          model: Object.freeze({
            key: hintRenderKey(target.element),
            className: `lf-key-badge lf-key-hint lf-target-chooser-hint${
              target === current ? " lf-current" : ""
            }${rect.clippedTop || rect.top < top ? " lf-in" : ""}`,
            hintCode: target.code,
            sequence: keySequenceModel(
              steps,
              progressStates(steps, [...hints.prefix()]),
            ),
          }),
          target: rect,
          belowTarget: false,
          left: Math.max(10, rect.left + enclosedBy(rect, boxes) * HINT_INDENT),
          top: Math.max(top, rect.top),
        };
      });
    },
    template: hintTemplate,
    take: chooseTarget,
    words: {
      describe: (target) => cut(target.label, 0, 72),
      take: "choose",
      all: "All target hints.",
    },
    chrome: hintChrome,
    followsScroll: true,
  });

  function paintSearchMatches() {
    const segments = matches[active];
    const owner = segments && matchIsRangeable(segments) ? matchOwner(segments) : null;
    const reading = room();
    const clip = owner ? reading.clipOver(owner) : null;
    const plans = [];
    if (clip)
      for (const [index, box] of [...rangeOf(segments).getClientRects()].entries()) {
        const rect = reading.clearPart(box, clip);
        if (!exposed(rect)) continue;
        plans.push({
          key: matchRenderKey(
            matchIdentity(pageSearchInput.value.trim(), segments),
            index,
          ),
          rect,
        });
      }
    render(
      html`${repeat(
        plans,
        ({ key }) => key,
        () => html`<span class="lf-page-search-match"></span>`,
      )}`,
      targetChooserHintLayer,
    );
    for (const [index, { rect }] of plans.entries()) {
      const mark = targetChooserHintLayer.children[index];
      mark.style.left = `${rect.left}px`;
      mark.style.top = `${rect.top}px`;
      mark.style.width = `${rect.width}px`;
      mark.style.height = `${rect.height}px`;
    }
  }

  function paintTargetChooserHints() {
    if (chooserOpen && pageSearchOpen) return paintSearchMatches();
    hints.paint();
  }

  const PAGE_SEARCH = {
    id: "page.search.open",
    keys: ["/"],
    does: "Search all the text on the page",
    line: "search page",
    // Once a target is in hand, its actions own the two short-line slots. Search stays
    // live to replace that target and remains in the complete reference.
    lineWhen: () => !Boolean(fabAnchorAt()),
    when: () => anchoringIsReady() && !pageSearchOpen,
    run: openPageSearch,
  };

  const REPEAT_PAGE_SEARCH = {
    id: "page.search.repeat",
    keys: ["n", "Shift+n"],
    routes: [
      {
        id: "page.search.next",
        binding: "n",
        does: "Go to the next match for the last page search",
      },
      {
        id: "page.search.previous",
        binding: "Shift+n",
        does: "Go to the previous match for the last page search",
      },
    ],
    does: "Next / previous match for the last page search",
    line: "search matches",
    repeat: true,
    when: () => Boolean(repeatedSearch),
    run: (binding) => repeatSearch(binding === "n" ? 1 : -1),
  };

  const TARGETING_BACK = {
    id: "targeting.back",
    keys: ["Escape"],
    // Search keeps its two unfamiliar operations on the shortcut bar; Escape remains
    // available in the complete reference.
    promoteEscape: () => !pageSearchOpen,
    does: () =>
      pageSearchOpen
        ? searchReturnsToHints
          ? "Return to the visible target hints"
          : "Close page search"
        : hints.prefix()
          ? "Remove the last hint letter"
          : "Close the target chooser",
    line: () =>
      pageSearchOpen
        ? searchReturnsToHints
          ? "back to hints"
          : "close search"
        : hints.prefix()
          ? "back one letter"
          : "close chooser",
    run: back,
  };

  const targetingClaims = (binding) =>
    allButCommandReference(binding) && !bindings(PAGE_SEARCH).includes(binding);

  const TARGET_CHOOSER_SCOPE = {
    title: "In the target chooser",
    escape: "inner",
    at: () => chooserOpen && !pageSearchOpen,
    // The page owns search, even when target hints are standing over it. Exempt the
    // binding read from that row so one declaration drives both entry routes and every
    // keyboard projection.
    claims: targetingClaims,
    rows: [
      {
        id: "target.chooser.hint.type",
        keys: HINT_KEYS,
        label: "a–z",
        does: "Type the hint for a target",
        line: "type hint",
        when: () => hints.candidates().length > 0,
        run: hints.type,
      },
      {
        id: "target.chooser.hint.walk",
        keys: ["Tab", "Shift+Tab"],
        routes: [
          {
            id: "target.chooser.hint.next",
            binding: "Tab",
            does: "Hear the next visible target",
          },
          {
            id: "target.chooser.hint.previous",
            binding: "Shift+Tab",
            does: "Hear the previous visible target",
          },
        ],
        does: "Hear the next / previous visible target",
        line: "browse hints",
        repeat: true,
        when: () => hints.candidates().length > 0,
        run: (binding) => hints.walk(binding === "Tab" ? 1 : -1),
      },
      {
        id: "target.chooser.target.choose",
        keys: ["Enter"],
        does: "Choose the target just announced",
        line: "choose target",
        when: hints.walking,
        run: hints.choose,
      },
      TARGETING_BACK,
    ],
  };

  const PAGE_SEARCH_SCOPE = {
    title: "In page search",
    escape: "inner",
    at: () => pageSearchOpen,
    claims: targetingClaims,
    rows: [
      {
        id: "page.search.match.select",
        keys: ["Enter"],
        does: "Select the current search match",
        line: "select match",
        when: () => matches.length > 0,
        run: chooseMatch,
      },
      {
        id: "page.search.match.walk",
        keys: ["Tab", "Shift+Tab"],
        routes: [
          {
            id: "page.search.match.next",
            binding: "Tab",
            does: "Go to the next search match",
          },
          {
            id: "page.search.match.previous",
            binding: "Shift+Tab",
            does: "Go to the previous search match",
          },
        ],
        does: "Next / previous search match",
        line: "matches",
        repeat: true,
        when: () => matches.length > 0,
        run: (binding) => moveMatch(binding === "Tab" ? 1 : -1),
      },
      TARGETING_BACK,
    ],
  };

  const targetChooserOpen = () => chooserOpen;
  const openTargetChooser = () => setTargetChooser(true);
  const closeTargetChooser = () => setTargetChooser(false);

  function mount() {
    pageSearchInput.addEventListener("input", search);
    hints.mount();
    // The open search's mark is page-attached paint in a layer no ancestor scrolls, so it
    // follows the page only while something asks for a frame. The hint session's own door
    // answers for the map, and a slash pressed from the page arms no map — so search asks
    // for its own. Capture, because a panel's list and a board's own overflow scroll in
    // boxes of their own and a scroll event does not bubble.
    const followMatch = () => {
      if (pageSearchOpen) repaint();
    };
    addEventListener("scroll", followMatch, { capture: true, passive: true });
    addEventListener("resize", followMatch);
    document.addEventListener(LAYOUT, refreshMatchWalk);
  }
  return {
    visibleTargets,
    paintTargetChooserHints,
    PAGE_SEARCH,
    REPEAT_PAGE_SEARCH,
    TARGET_CHOOSER_SCOPE,
    PAGE_SEARCH_SCOPE,
    targetChooserOpen,
    openTargetChooser,
    closeTargetChooser,
    mount,
  };
}
