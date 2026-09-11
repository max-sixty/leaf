/* This module owns the target chooser and whole-page text search. */
import { aimTargets, anchoringIsReady } from "../anchor-resolution.js";
import { sameAnchor } from "../anchor-coordinate.js";
import { bindings } from "../keyboard/bindings.js";
import { el } from "../widget-elements.js";

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
import { shownParts, shownRect } from "../geometry.js";
import { focused } from "../keyboard/scopes.js";
import { repaint } from "../repaint.js";
import { HINT_KEYS, hintCodes, spreadHints } from "../keyboard/hints.js";
import { keySequence, progressStates } from "../keyboard/presentation.js";
import { announce } from "../notifications.js";
import { beginWalk, listWalkPosition, walkPosition } from "../walk-position.js";

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
// The short, viewport-local hints form a prefix-free tree over one alphabet. Most
// targets cost one letter; only the tail branches when the viewport holds more targets
// than the alphabet. These hints are ephemeral and make no promise across a scroll or
// revision. They are the whole route, so none may be dropped because
// its chip collides. Each chip begins at its target's visible top-left corner. A target
// whose visible box is strictly smaller and fully enclosed by another target steps its
// chip right once per enclosing box. If that position crosses the key-line band and the
// target has visible room beside it, the chip moves into that room; otherwise it moves
// above the band. An ancestor and descendant with the same visible box name one target:
// the innermost remains, matching direct aim. Equal boxes outside one containment chain
// stay at the same depth, and the collision pass separates their chips without inventing
// a hierarchy or moving them beyond the viewport foot. Membership is fixed for the
// length of a scroll and re-read once it settles, so a target arriving mid-scroll is
// named at rest rather than on the frame it appears.
//
// Tab and Shift-Tab walk the visible target map and announce each target. Enter chooses
// the last one announced. A viewport change that removes or renames that target clears
// the announced choice before Enter can act on it.
//
// `/` opens a real search input over the whole page reading, either directly from the
// page or from the visible target hints. Tab walks repeated occurrences and Enter makes a
// native browser Selection from the active match. Once the prompt closes, n repeats that
// accepted search and N reverses it. Escape returns to the surface that opened search:
// the page after a direct `/`, or the visible hints after `s` then `/`. The interaction keeps
// `?` available and claims the rest of the page's keyboard while it stands.

export function createTargetChooser({
  scrollToRange,
  banner,
  bottomChromeBoxes,
  shortcutBarEl,
  standingStatusBoxes,
  commentOnTarget,
  updateFab,
  fabAnchorAt,
}) {
  const HINT_INDENT = 10;

  let chooserOpen = false;
  let pageSearchOpen = false;
  let prefix = "";
  let candidates = [];
  let matches = [];
  let active = -1;
  let hintActive = -1;
  let opener = null;
  let searchReturnsToHints = false;
  let scrolling = false;
  let repeatedSearch = null;
  const matchNodeIds = new WeakMap();
  let nextMatchNodeId = 1;

  const clips = () => new Map();
  const covered = () => banner.getBoundingClientRect().bottom;
  const overlaps = (a, b) =>
    a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  const rect = (left, top, right, bottom, sourceTop = top) =>
    right > left && bottom > top
      ? {
          left,
          top,
          right,
          bottom,
          width: right - left,
          height: bottom - top,
          clippedTop: sourceTop < top,
        }
      : null;
  // The largest visible rectangle left after viewport chrome is subtracted. The banner
  // spans the window and clips one edge. Bottom chrome reserves its whole lane to the
  // viewport foot. Each blocker divides a target
  // crossing it into the open space above, below, before, or after it.
  //
  // A coarse pointer is shown no line, and an empty one takes itself down. A zero box must
  // therefore answer with the viewport foot rather than a top of 0, or `s` names no items
  // and `/` paints no match with nothing on screen saying why.
  function visibleRect(box, sourceTop = box?.top) {
    if (!box) return null;
    const shown = rect(
      Math.max(box.left, 0),
      Math.max(box.top, covered()),
      Math.min(box.right, innerWidth),
      Math.min(box.bottom, innerHeight),
      sourceTop,
    );
    if (!shown) return null;
    const blockers = bottomChromeBoxes().map((box) => ({
      left: box.left,
      top: box.top,
      right: box.right,
      bottom: innerHeight,
    }));
    const candidates = blockers.reduce(
      (available, box) => {
        return available.flatMap((candidate) =>
          overlaps(candidate, box)
            ? [
                rect(
                  candidate.left,
                  candidate.top,
                  candidate.right,
                  Math.min(candidate.bottom, box.top),
                  sourceTop,
                ),
                rect(
                  candidate.left,
                  candidate.top,
                  Math.min(candidate.right, box.left),
                  candidate.bottom,
                  sourceTop,
                ),
                rect(
                  Math.max(candidate.left, box.right),
                  candidate.top,
                  candidate.right,
                  candidate.bottom,
                  sourceTop,
                ),
                rect(
                  candidate.left,
                  Math.max(candidate.top, box.bottom),
                  candidate.right,
                  candidate.bottom,
                  sourceTop,
                ),
              ].filter(Boolean)
            : [candidate],
        );
      },
      [shown],
    );
    return (
      candidates.sort((a, b) => b.width * b.height - a.width * a.height)[0] ?? null
    );
  }
  // A fixed sheet can cover a page box without clipping it. Hints live above the chrome,
  // so geometry alone would put a key on the thread panel for a card hidden behind it.
  // Ask the rendered stack at the hint's corner; pointer-events:none keeps an existing
  // hint from answering this question itself.
  const exposed = (box) => {
    if (!box) return false;
    const x = Math.max(0, Math.min(innerWidth - 1, box.left + 1));
    const y = Math.max(covered(), Math.min(innerHeight - 1, box.top + 1));
    return !inChrome(document.elementFromPoint(x, y));
  };
  // Chromium retains geometry for descendants suppressed by a closed disclosure. Ask
  // visibility before geometry so those descendants cost no box reads. A display: contents
  // addressable has no box of its own and stays eligible through a visible child.
  const targetShown = ({ element }) =>
    element.checkVisibility() ||
    (getComputedStyle(element).display === "contents" &&
      shownParts(element).some((part) => part.checkVisibility()));

  function clippedRect(box, clip) {
    if (!box || !clip) return null;
    const left = Math.max(box.left, clip.left, 0);
    const top = Math.max(box.top, clip.top, covered());
    const right = Math.min(box.right, clip.right, innerWidth);
    const bottom = Math.min(box.bottom, clip.bottom, innerHeight);
    return visibleRect({ left, top, right, bottom }, box.top);
  }

  function firstShown(range, owner, cache) {
    const clip = shownRect(owner, cache);
    if (!clip) return null;
    return (
      [...range.getClientRects()].map((box) => clippedRect(box, clip)).find(exposed) ??
      null
    );
  }

  const sameVisibleBox = (a, b) =>
    Math.abs(a.left - b.left) < 0.5 &&
    Math.abs(a.top - b.top) < 0.5 &&
    Math.abs(a.right - b.right) < 0.5 &&
    Math.abs(a.bottom - b.bottom) < 0.5;

  function visibleTargets() {
    const cache = clips();
    const targets = aimTargets()
      .filter(({ element }) => !inChrome(element))
      .filter(targetShown)
      .map((target) => ({
        ...target,
        rect: visibleRect(shownRect(target.element, cache)),
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
    return unique.map((target, index) => ({
      ...target,
      code: codes[index],
      nesting: unique.filter(
        (outer) =>
          outer !== target &&
          outer.rect.left <= target.rect.left &&
          outer.rect.top <= target.rect.top &&
          outer.rect.right >= target.rect.right &&
          outer.rect.bottom >= target.rect.bottom &&
          (outer.rect.right - outer.rect.left > target.rect.right - target.rect.left ||
            outer.rect.bottom - outer.rect.top > target.rect.bottom - target.rect.top),
      ).length,
    }));
  }

  function setTargetChooser(on, restore = false, withHints = true) {
    if (on && !anchoringIsReady()) return;
    if (on) opener = focused();
    const returnTo = !on && restore ? opener : null;
    chooserOpen = on;
    pageSearchOpen = false;
    searchReturnsToHints = false;
    prefix = "";
    matches = [];
    active = -1;
    hintActive = -1;
    scrolling = false;
    pageSearchInput.value = "";
    pageSearchSurface.hidden = true;
    if (on && withHints) {
      candidates = visibleTargets();
      if (!candidates.length) {
        announce(
          "There is no visible target to choose. Press slash to search the page.",
        );
      } else {
        announce(
          `Choose a target — type one of ${candidates.length} hints, press Tab to hear them, or slash to search the page.`,
        );
      }
    } else if (!on) {
      candidates = [];
      targetChooserHintLayer.replaceChildren();
      opener = null;
    } else {
      candidates = [];
    }
    repaint();
    if (returnTo?.isConnected) returnTo.focus({ preventScroll: true });
  }

  function setPageSearch(on) {
    pageSearchOpen = on;
    prefix = "";
    hintActive = -1;
    pageSearchSurface.hidden = !on;
    if (on) {
      pageSearchInput.focus({ preventScroll: true });
      pageSearchStatus.textContent = "";
      announce("Search the page.");
    } else {
      pageSearchInput.value = "";
      matches = [];
      active = -1;
      document.body.focus({ preventScroll: true });
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

  function matchRect(segments, cache = clips()) {
    const owner = matchOwner(segments);
    return owner ? firstShown(rangeOf(segments), owner, cache) : null;
  }

  function startingMatch(found) {
    const top = covered();
    const next = found.findIndex(
      (segments) => rangeOf(segments).getBoundingClientRect().bottom > top,
    );
    return next === -1 ? 0 : next;
  }

  function syncStatus() {
    if (!pageSearchInput.value.trim()) pageSearchStatus.textContent = "";
    else if (!matches.length) pageSearchStatus.textContent = "No matches";
    else pageSearchStatus.textContent = `${active + 1} of ${matches.length}`;
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
  // `lf-actions` is the runtime's broad source invalidation, so refresh only while this
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
    if (pageSearchOpen) syncStatus();
    repaint();
  }

  function search() {
    const query = pageSearchInput.value.trim();
    matches = query ? findText(pageText(), query) : [];
    active = matches.length ? startingMatch(matches) : -1;
    syncStatus();
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
    syncStatus();
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

  function typeHint(key) {
    hintActive = -1;
    prefix += key;
    const left = candidates.filter(({ code }) => code.startsWith(prefix));
    const target = left.find(({ code }) => code === prefix);
    if (target) return chooseTarget(target);
    if (!left.length) {
      prefix = "";
      announce("That hint is not on screen. The hints are reset.");
    } else announce(`${left.length} targets remain.`);
    repaint();
  }

  const hinted = () => candidates.filter(({ code }) => code.startsWith(prefix));

  function moveHint(direction) {
    const targets = hinted();
    if (!targets.length) return;
    hintActive = (hintActive + direction + targets.length) % targets.length;
    const target = targets[hintActive];
    beginWalk("target-chooser", "Target", () =>
      listWalkPosition(hinted(), hinted()[hintActive], {
        identity: (candidate) => candidate.element,
      }),
    );
    announce(
      `Hint ${target.code}: ${cut(target.label, 0, 72)}. Press Enter to choose.`,
    );
    repaint();
  }

  function chooseHint() {
    const target = hinted()[hintActive];
    if (target) chooseTarget(target);
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
    if (prefix) {
      prefix = prefix.slice(0, -1);
      hintActive = -1;
      announce(prefix ? `Hint ${prefix}.` : "All target hints.");
      return repaint();
    }
    setTargetChooser(false, true);
    announce("Target chooser closed.");
  }

  function hintChip(target) {
    const chip = el("span", "lf-key-badge lf-key-hint lf-target-chooser-hint");
    chip.dataset.lfHintCode = target.code;
    if (hinted()[hintActive] === target) chip.classList.add("lf-current");
    const steps = [...target.code];
    chip.append(keySequence(steps, progressStates(steps, [...prefix])));
    return chip;
  }

  function paintTargetChooserHints() {
    if (!chooserOpen) {
      if (targetChooserHintLayer.childElementCount)
        targetChooserHintLayer.replaceChildren();
      return;
    }
    const wasActive = hintActive >= 0;
    const refreshed = !pageSearchOpen && !prefix && !scrolling;
    const heard = hinted()[hintActive];
    if (refreshed) {
      candidates = visibleTargets();
      const still = heard
        ? candidates.findIndex(
            (target) =>
              sameAnchor(target.anchor, heard.anchor) && target.code === heard.code,
          )
        : -1;
      hintActive = still;
    }
    const drawn = [];
    const hints = [];
    const drawnTargets = new Set();
    if (!pageSearchOpen) {
      const cache = clips();
      for (const target of candidates) {
        if (!target.code.startsWith(prefix)) continue;
        if (!targetShown(target)) continue;
        const rect = refreshed
          ? target.rect
          : visibleRect(shownRect(target.element, cache));
        if (!exposed(rect)) continue;
        const chip = hintChip(target);
        chip.style.left = `${Math.max(10, rect.left + target.nesting * HINT_INDENT)}px`;
        chip.style.top = `${Math.max(covered(), rect.top)}px`;
        if (rect.clippedTop || rect.top < covered()) chip.classList.add("lf-in");
        drawn.push(chip);
        hints.push({ chip, target: rect });
        drawnTargets.add(target);
      }
    } else if (matches[active] && matchIsRangeable(matches[active])) {
      const owner = matchOwner(matches[active]);
      const clip = owner ? shownRect(owner, clips()) : null;
      if (clip)
        for (const box of rangeOf(matches[active]).getClientRects()) {
          const rect = clippedRect(box, clip);
          if (!exposed(rect)) continue;
          const mark = el("span", "lf-page-search-match");
          mark.style.left = `${rect.left}px`;
          mark.style.top = `${rect.top}px`;
          mark.style.width = `${rect.width}px`;
          mark.style.height = `${rect.height}px`;
          drawn.push(mark);
        }
    }
    if (!refreshed && heard && !drawnTargets.has(heard)) hintActive = -1;
    // The shortcut bar was painted before geometry retired the browsed hint.
    if (wasActive && hintActive < 0) repaint();
    targetChooserHintLayer.replaceChildren(...drawn);
    if (!pageSearchOpen)
      spreadHints(hints, {
        barriers: standingStatusBoxes(),
        lineBox: shortcutBarEl.getBoundingClientRect(),
        viewportTop: covered(),
      });
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
        : prefix
          ? "Remove the last hint letter"
          : "Close the target chooser",
    line: () =>
      pageSearchOpen
        ? searchReturnsToHints
          ? "back to hints"
          : "close search"
        : prefix
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
        when: () => candidates.length > 0,
        run: typeHint,
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
        when: () => candidates.length > 0,
        run: (binding) => moveHint(binding === "Tab" ? 1 : -1),
      },
      {
        id: "target.chooser.target.choose",
        keys: ["Enter"],
        does: "Choose the target just announced",
        line: "choose target",
        when: () => hintActive >= 0,
        run: chooseHint,
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
    addEventListener(
      "scroll",
      () => {
        if (!chooserOpen) return;
        scrolling = true;
        repaint();
      },
      { capture: true, passive: true },
    );
    addEventListener(
      "scrollend",
      () => {
        if (!chooserOpen || !scrolling) return;
        scrolling = false;
        repaint();
      },
      { capture: true, passive: true },
    );
    addEventListener("resize", () => {
      if (!chooserOpen) return;
      scrolling = false;
      repaint();
    });
    document.addEventListener("lf-actions", refreshMatchWalk);
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
