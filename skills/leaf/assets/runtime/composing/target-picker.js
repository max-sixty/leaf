/* This module owns the target picker and whole-page text search. Its transient hints,
 * search marks, and status are synchronous Lit projections over native controller state. */
import { anchoringIsReady } from "../anchor-resolution.js";
import { bindings, bindingEnabled } from "../keyboard/bindings.js";
import { el, LAYOUT, reserve } from "../widget-elements.js";
import { coarsePointer } from "../pointer.js";
import { html, nothing, render } from "../../vendor/browser-runtime.js";

import {
  contextAround,
  findText,
  inChrome,
  pageText,
  quoteFrom,
  rangeOf,
  selectEnds,
  segmentBlock,
} from "../passages.js";
import { bannerFoot, shownBox, shownParts } from "../geometry.js";
import { repaint } from "../repaint.js";
import { union } from "../rect.js";
import { anchorFor } from "../anchor-names.js";
import { paintSet } from "../target-paint-geometry.js";
import {
  handBack,
  releaseFocus,
  focusDestination,
  closeLayer,
  openLayer,
  openerOf,
} from "../focus.js";
import {
  createHintSession,
  HINT_KEYS,
  hintCodes,
  renderKeys,
} from "../keyboard/hints.js";
import { keyBadgePlacement } from "../keyboard/key-badge-placement.js";
import {
  keySequenceModel,
  keySequenceTemplate,
  progressStates,
} from "../keyboard/presentation.js";
import { announce } from "../notifications.js";
import { keepsHidden } from "../keeps.js";
import { beginWalk, walkPosition } from "../walk-position.js";

import {
  allButCommandReference,
  coveringAuxiliarySurface,
  pageCommand,
  pageScope,
} from "../keyboard/register.js";

// The target picker and page search have separate faces. Hints and the active search
// result are paint only; the search box is a real control, kept beside them so its focus
// and accessible name are the platform's rather than a keyboard interaction's imitation
// of one.
export const targetPickerHintLayer = el("div", "lf-ui lf-target-picker-hints");
targetPickerHintLayer.setAttribute("aria-hidden", "true");
const hintRoot = el("div", "lf-key-chips");
const markRoot = el("div", "lf-key-chips");
targetPickerHintLayer.append(hintRoot, markRoot);
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
const noMatches = "No matches";
const searchCount = (position, total) => `${position} of ${total}`;

// Target choosing and whole-page text search. `s` opens a viewport-local map of
// the same stable addressables and visual parts Alt-click reaches, then opens Comment on the
// chosen target; `/` opens the page's text search directly or from that map. The banner's
// Select element opens this same picker, and its Cancel selection closes it. A choice
// in Design mode keeps that mode's design intent; Draw reserves the page for ink and
// offers no picker. While the picker stands, the page is armed as it is under a held
// Alt (aim.js): a mouse shows the target
// under it, and a press, by finger or mouse, chooses that target without activating
// authored controls. The key and the modifier are two ways into one gesture, so a press
// means the same under either.
//
// `keyboard/hints.js` owns the map itself: arming, codes, the typed prefix, the audible
// walk, the scroll freeze, and the paint. What this module declares is which members the
// map holds and where each chip sits among them. An ancestor and descendant painting the
// same visible box name one target, and the innermost remains, matching direct aim. A
// target's chip sits outside its own box, keeping controls and their labels readable. Shared hint seating separates those faces without moving page content.
// Admission and clipping stay with key-badge-placement.js.
//
// `/` opens a real search input over the whole page reading, either directly from the
// page or from the visible target hints. Tab walks repeated occurrences and Enter makes a
// native browser Selection from the active match. Once the prompt closes, n repeats that
// accepted search and N reverses it. Escape returns to the surface that opened search:
// the page after a direct `/`, or the visible hints after `s` then `/`. The interaction keeps
// `?` available and claims the rest of the page's keyboard while it stands.

export function createTargetPicker({
  scrollToRange,
  hintChrome,
  commentOnTarget,
  updateFab,
  fabAnchorAt,
  drawModeActive,
  readTargets,
  armChanged,
}) {
  const canChoose = () =>
    anchoringIsReady() && !coveringAuxiliarySurface() && !drawModeActive();

  let pickerOpen = false;
  let pageSearchOpen = false;
  let matches = [];
  let active = -1;
  let searchReturnsToHints = false;
  let repeatedSearch = null;
  const matchNodeIds = new WeakMap();
  let nextMatchNodeId = 1;

  // Target elements and text coordinates stay outside the immutable readings. Lit receives
  // only opaque primitive identities, retaining unchanged hint and keycap nodes on repaint.
  const hintRenderKey = renderKeys();
  // The open search's mark stands over its words in the frames that cut them, carried
  // by what carries the words (target-paint-geometry.js, `paintSet`), so no scroll
  // writes it.
  const marks = paintSet(markRoot);
  const markBoxes = [];

  // One reading of the room the user has, shared by every member of a pass: the clips
  // over their common ancestors are walked once, and admission, exposure, and paint read
  // the same boxes.
  const room = keyBadgePlacement;
  // Chromium retains geometry for descendants suppressed by a closed disclosure. Ask
  // visibility before geometry so those descendants cost no box reads. A display: contents
  // addressable has no box of its own and stays eligible through a visible child.
  const hintElement = (target) => target.controlElement ?? target.element;
  const targetBounds = (target, reading) =>
    union(
      (target.controlFaces ?? [hintElement(target)])
        .map((face) => ({ face, rect: reading.visibleBounds(face) }))
        .filter(({ face, rect }) => reading.exposes(face, rect))
        .map(({ rect }) => rect),
    );
  const targetShown = (target) => {
    const element = hintElement(target);
    return (
      element.checkVisibility() ||
      (getComputedStyle(element).display === "contents" &&
        shownParts(element).some((part) => part.checkVisibility()))
    );
  };

  function firstShown(range, owner, reading) {
    const clip = reading.clipOver(owner);
    if (!clip) return null;
    return (
      [...range.getClientRects()]
        .map((box) => reading.clearPart(box, clip))
        .find((part) => reading.exposes(null, part)) ?? null
    );
  }

  const sameVisibleBox = (a, b) =>
    Math.abs(a.left - b.left) < 0.5 &&
    Math.abs(a.top - b.top) < 0.5 &&
    Math.abs(a.right - b.right) < 0.5 &&
    Math.abs(a.bottom - b.bottom) < 0.5;

  function visibleTargets() {
    const reading = room();
    const targets = readTargets()
      .filter((target) => !inChrome(hintElement(target)))
      .filter(targetShown)
      .map((target) => ({
        ...target,
        rect: targetBounds(target, reading),
      }))
      .filter((target) => target.rect)
      .sort((a, b) => a.rect.top - b.rect.top || a.rect.left - b.rect.left);
    // Direct aiming chooses the innermost stable addressable under the pointer. When an
    // ancestor and descendant paint the same visible box, naming both would offer two
    // keys for that one choice. Keep distinct nested extents and unrelated overlaps.
    const unique = targets.filter(
      (outer) =>
        !targets.some(
          (inner) =>
            inner !== outer &&
            hintElement(outer) !== hintElement(inner) &&
            hintElement(outer).contains(hintElement(inner)) &&
            sameVisibleBox(outer.rect, inner.rect),
        ),
    );
    const codes = hintCodes(unique.length);
    return unique.map((target, index) => ({ ...target, code: codes[index] }));
  }

  // `withHints` opens the shared mode without a target map: a direct slash is page
  // search over the whole document, and reading a viewport-local map it would then hide
  // is work for nobody.
  // The picker's opener is the control the user stood on as it opened (focus.js,
  // `openLayer`); a close that restores hands them back to it as it closes.
  function setTargetPicker(on, restore = false, withHints = true) {
    if (on && (!anchoringIsReady() || (withHints && !canChoose()))) return;
    if (on) {
      openLayer(pageSearchSurface);
      paintTargetPicker(on, withHints);
      return;
    }
    // An opener of nowhere hands back nothing, and `handBack` lets the user go.
    const landing = restore && pickerOpen;
    const opener = openerOf(pageSearchSurface);
    closeLayer(
      () => paintTargetPicker(on, withHints),
      landing && (() => handBack(opener)),
    );
  }
  function paintTargetPicker(on, withHints) {
    pickerOpen = on;
    pageSearchOpen = false;
    searchReturnsToHints = false;
    matches = [];
    active = -1;
    pageSearchInput.value = "";
    keepsHidden(pageSearchSurface, true);
    if (on && withHints) {
      const found = hints.arm();
      announce(
        found.length
          ? `Choose a target — press an element${bindings(TARGET_HINT_TYPE).length ? `, type one of ${found.length} hints` : ""}, or press Tab to hear targets and Enter to choose.${bindings(PAGE_SEARCH).length ? " Press slash to search the page." : ""}`
          : `There is no visible target to choose.${bindings(PAGE_SEARCH).length ? " Press slash to search the page." : ""}`,
      );
    } else {
      hints.disarm();
    }
    armChanged();
    repaint();
  }

  function setPageSearch(on) {
    pageSearchOpen = on;
    keepsHidden(pageSearchSurface, !on);
    if (on) {
      // A nonempty query cannot match more often than there are characters. Reserve
      // the whole reading's count before editing, so narrowing never resizes the field.
      const maximum = pageText().raw.length;
      reserve(pageSearchStatus, [noMatches, searchCount(maximum, maximum)]);
      focusDestination(pageSearchInput, "move");
      presentSearchStatus();
      announce("Search the page.");
    } else {
      pageSearchInput.value = "";
      matches = [];
      active = -1;
      releaseFocus();
      // Search may have travelled to a match, so the map the user comes back to is read
      // again rather than being the one search covered.
      hints.invalidate();
      announce(
        `Choose a target — ${bindings(TARGET_HINT_TYPE).length ? "type a hint, or " : ""}press Tab to hear targets and Enter to choose.${bindings(PAGE_SEARCH).length ? " Press slash to search the page." : ""}`,
      );
    }
    armChanged();
    repaint();
  }

  function openPageSearch() {
    const fromHints = pickerOpen;
    if (!pickerOpen) setTargetPicker(true, false, false);
    searchReturnsToHints = fromHints;
    setPageSearch(true);
  }

  function matchOwner(segments) {
    const first = segments[0];
    return first ? segmentBlock(first) : null;
  }

  function matchRect(segments, reading = room()) {
    const owner = matchOwner(segments);
    return owner ? firstShown(rangeOf(segments), owner, reading) : null;
  }

  function startingMatch(found) {
    const top = bannerFoot();
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
        ? searchCount(active + 1, matches.length)
        : noMatches;
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
    return `${before ? `…${before} ` : ""}${phrase}${after ? ` ${after}…` : ""}`;
  }

  function chooseTarget(candidate) {
    const target = candidate.capture ? candidate.capture() : candidate;
    setTargetPicker(false);
    releaseFocus();
    commentOnTarget(target);
    announce(`Chosen ${target.label}.`);
  }

  function chooseMatch() {
    const segments = matches[active];
    if (!segments) return;
    const quote = quoteFrom(matches[active]);
    repeatedSearch = { query: pageSearchInput.value.trim(), index: active };
    setTargetPicker(false);
    selectMatch(segments);
    announce(
      `Selected match: ${quote}. ${
        coarsePointer.matches || !bindingEnabled("c")
          ? "Comment on selection on the banner comments on it."
          : "Press n for next, Shift+n for previous, or c to comment."
      }`,
    );
  }

  function selectMatch(segments) {
    releaseFocus();
    const range = rangeOf(segments);
    selectEnds(
      [range.startContainer, range.startOffset],
      [range.endContainer, range.endOffset],
    );
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
      setTargetPicker(false, true);
      announce("Page search closed.");
      return;
    }
    if (hints.backOneLetter()) return;
    setTargetPicker(false, true);
    announce("Target picker closed.");
  }

  const hintTemplate = (model) =>
    html`<span class=${model.className} data-lf-hint-code=${model.hintCode}
      >${keySequenceTemplate(model.sequence)}</span
    >`;

  // The picker's hints and the open search's marks are two faces in one layer, and only
  // one of them stands at a time: search covers the map that opened it.
  const hints = createHintSession({
    layer: hintRoot,
    walk: "target-picker",
    read: visibleTargets,
    identity: hintElement,
    scene: room,
    layout: (candidates, { current, reading }) => {
      const seated = candidates
        .map((target) => [
          target,
          targetShown(target) ? targetBounds(target, reading) : null,
        ])
        .filter(([, rect]) => rect);
      const top = bannerFoot();
      return seated.map(([target, rect]) => {
        const steps = [...target.code];
        return {
          candidate: target,
          model: Object.freeze({
            key: hintRenderKey(hintElement(target)),
            className: `lf-key-badge lf-key-hint lf-target-picker-hint${
              target === current ? " lf-current" : ""
            }${rect.clippedTop || rect.top < top ? " lf-in" : ""}`,
            hintCode: target.code,
            sequence: keySequenceModel(
              steps,
              progressStates(steps, [...hints.prefix()]),
            ),
          }),
          target: rect,
          placement: target.controlElement ? "above" : "before",
          // Control keys sit just outside their own upper-left corner. Owner keys
          // stay before the owner; neither route writes a key into its target.
          left: rect.left,
          top: Math.max(top, rect.top),
        };
      });
    },
    template: hintTemplate,
    take: chooseTarget,
    words: {
      describe: (target) => (target.capture ? target.capture() : target).label,
      take: "choose",
      all: "All target hints.",
    },
    chrome: hintChrome,
  });

  // A mark for each box the match's words take, while a covering surface leaves any of
  // it in sight, standing over what holds the words and carried by what carries them
  // (`anchorFor`).
  function paintSearchMatches() {
    const segments = matches[active];
    const owner = segments && matchIsRangeable(segments) ? matchOwner(segments) : null;
    const reading = room();
    const clip = owner ? reading.clipOver(owner) : null;
    const boxes = clip
      ? [...rangeOf(segments).getClientRects()].filter((box) =>
          reading.exposes(null, reading.clearPart(box, clip)),
        )
      : [];
    const anchor = owner && anchorFor(segments[0].node);
    // A line's box can reach past the block that holds it; the mark keeps to the block.
    const own = owner && shownBox(owner);
    while (markBoxes.length < boxes.length)
      markBoxes.push(el("span", "lf-page-search-match"));
    marks.place(
      boxes.map((box, index) => ({
        node: markBoxes[index],
        target: owner,
        held: true,
        anchor,
        rect: {
          left: Math.max(box.left, own.left),
          top: Math.max(box.top, own.top),
          right: Math.min(box.right, own.right),
          bottom: Math.min(box.bottom, own.bottom),
        },
      })),
    );
  }

  function paintTargetPickerHints() {
    if (pickerOpen && pageSearchOpen) return paintSearchMatches();
    marks.place([]);
    hints.paint();
  }

  const PAGE_SEARCH = {
    id: "page.search.open",
    // A finger can select words it can see, but not find them elsewhere on a long page.
    touch: "Search page",
    keys: ["/"],
    description: "Search all the text on the page",
    title: "search page",
    // Once a target is in hand, its actions own the two short-line slots. Search stays
    // live to replace that target and remains in the complete reference.
    lineWhen: () => !Boolean(fabAnchorAt()),
    when: () => anchoringIsReady() && !pageSearchOpen,
    run: openPageSearch,
  };

  const REPEAT_PAGE_SEARCH = {
    id: "page.search.repeat",
    touch: false,
    keys: ["n", "Shift+n"],
    routes: [
      {
        id: "page.search.next",
        binding: "n",
        title: "Go to the next match for the last page search",
      },
      {
        id: "page.search.previous",
        binding: "Shift+n",
        title: "Go to the previous match for the last page search",
      },
    ],
    title: "search matches",
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
    description: () =>
      pageSearchOpen
        ? searchReturnsToHints
          ? "Return to the visible target hints"
          : "Close page search"
        : hints.prefix()
          ? "Remove the last hint letter"
          : "Close the target picker",
    title: () =>
      pageSearchOpen
        ? searchReturnsToHints
          ? "back to hints"
          : "close search"
        : hints.prefix()
          ? "back one letter"
          : "close picker",
    touch: () =>
      pageSearchOpen
        ? searchReturnsToHints
          ? "Back to hints"
          : "Close search"
        : hints.prefix()
          ? "Back one letter"
          : "Cancel selection",
    run: back,
  };

  const targetingClaims = (binding) =>
    allButCommandReference(binding) && !bindings(PAGE_SEARCH).includes(binding);

  const TARGET_HINT_TYPE = {
    id: "target.picker.hint.type",
    keys: HINT_KEYS,
    label: "a–z",
    description: "Type the hint for a target",
    title: "type hint",
    when: () => hints.candidates().length > 0,
    run: hints.type,
  };

  const TARGET_PICKER_SCOPE = {
    title: "In the target picker",
    escape: "inner",
    at: () => pickerOpen && !pageSearchOpen,
    // The page owns search, even when target hints are standing over it. Exempt the
    // binding read from that row so one declaration drives both entry routes and every
    // keyboard projection.
    claims: targetingClaims,
    rows: [
      TARGET_HINT_TYPE,
      {
        id: "target.picker.hint.walk",
        keys: ["Tab", "Shift+Tab"],
        routes: [
          {
            id: "target.picker.hint.next",
            binding: "Tab",
            title: "Hear the next visible target",
          },
          {
            id: "target.picker.hint.previous",
            binding: "Shift+Tab",
            title: "Hear the previous visible target",
          },
        ],
        title: "browse hints",
        repeat: true,
        when: () => hints.candidates().length > 0,
        run: (binding) => hints.walk(binding === "Tab" ? 1 : -1),
      },
      {
        id: "target.picker.target.choose",
        keys: ["Enter"],
        description: "Choose the target just announced",
        title: "choose target",
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
        description: "Select the current search match",
        title: "select match",
        touch: "Select",
        when: () => matches.length > 0,
        run: chooseMatch,
      },
      {
        id: "page.search.match.walk",
        keys: ["Tab", "Shift+Tab"],
        routes: [
          {
            id: "page.search.match.previous",
            binding: "Shift+Tab",
            title: "Go to the previous search match",
            touch: "Previous",
          },
          {
            id: "page.search.match.next",
            binding: "Tab",
            title: "Go to the next search match",
            touch: "Next",
          },
        ],
        title: "matches",
        repeat: true,
        when: () => matches.length > 0,
        run: (binding) => moveMatch(binding === "Tab" ? 1 : -1),
      },
      TARGETING_BACK,
    ],
  };

  const targetPickerOpen = () => pickerOpen;
  const openTargetPicker = () => setTargetPicker(true);
  const closeTargetPicker = () => setTargetPicker(false);

  function mount() {
    pageSearchInput.addEventListener("input", search);
    hints.mount();
    addEventListener("resize", () => {
      if (pageSearchOpen) repaint();
    });
    document.addEventListener(LAYOUT, refreshMatchWalk);
  }
  pageScope("page search", PAGE_SEARCH_SCOPE);
  pageScope("target picker", TARGET_PICKER_SCOPE);
  // The page itself is already a Comment target; `s` plus a hint names a more particular
  // one. Either route opens Comment, while reactions wait for a target.
  pageCommand({
    id: "target.picker.open",
    keys: ["s"],
    description: () =>
      bindings(TARGET_HINT_TYPE).length
        ? "Choose an element by pressing it or typing its hint, then comment"
        : "Choose an element by pressing it or browsing targets with Tab and Enter, then comment",
    title: "select element",
    touch: "Select element",
    // Once the field is open, its typing scope owns character keys. This gate also keeps
    // the route off the short line while a target is in hand.
    lineWhen: () => !Boolean(fabAnchorAt()),
    when: canChoose,
    run: (...args) => openTargetPicker(...args),
  });
  // Search remains one press from the expanded shortcut bar and named in full by the
  // reference.
  pageCommand(PAGE_SEARCH);
  pageCommand(REPEAT_PAGE_SEARCH);

  return {
    visibleTargets,
    chooseTarget,
    // The map, not the mode: a direct slash opens the mode for search alone.
    choosing: () => hints.armed() && !pageSearchOpen,
    paintTargetPickerHints,
    targetPickerOpen,
    openTargetPicker,
    closeTargetPicker,
    mount,
  };
}
