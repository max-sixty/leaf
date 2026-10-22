/* This module owns the target picker and whole-page text search. Its transient hints,
 * search marks, and status are synchronous Lit projections over native controller state. */
import { anchoringIsReady } from "../anchor-resolution.js";
import { bindings, bindingEnabled, cycledRow } from "../keyboard/bindings.js";
import { el, LAYOUT, searchField } from "../widget-elements.js";
import { iconElement } from "../icons.js";
import { coarsePointer } from "../pointer.js";
import { html, nothing, render, signal } from "/vendor/browser-runtime.js";

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
import { shownBox } from "../geometry.js";
import { visibleTargetParts } from "../visible-target-parts.js";
import { repaint } from "../repaint.js";
import { intersect, union } from "../rect.js";
import { anchorFor } from "../css-anchors.js";
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
} from "../keyboard/key-sequence.js";
import { announce } from "../notifications.js";
import { keeps } from "../keeps.js";
import { beginWalk, walkPosition } from "../walk-position.js";

import {
  allButCommandReference,
  pageCommand,
  pageScope,
} from "../keyboard/register.js";

// Hints and the active search result are paint only. The floating panel seats the
// search's own native field and match controls in its main row, keeping the comment
// editor intact while search owns the field.
export const targetPickerHintLayer = el("div", "lf-ui lf-target-picker-hints");
targetPickerHintLayer.setAttribute("aria-hidden", "true");
const hintRoot = el("div", "lf-key-chips");
const markRoot = el("div", "lf-key-chips");
targetPickerHintLayer.append(hintRoot, markRoot);
const pageSearchInput = searchField("lf-page-search-box", {
  name: "page-search",
  label: "Search page text",
  placeholder: "Find text",
});
pageSearchInput.maxlength = 160;
const pageSearchStatus = el("span", "lf-page-search-status");
pageSearchStatus.setAttribute("role", "status");
const pageSearchWords = el("span");
pageSearchStatus.append(pageSearchWords);
// The box walks its own matches, as a browser's find bar does: up and down beside the
// count they move, the walk's one control for a finger and a mouse. A press leaves focus
// in the field, so a phone's keyboard stays up and the next letter still edits the query.
// Tab is their key, so they are no stop of its own.
const matchStep = (icon, name) => {
  const control = el(
    "button",
    "lf-btn lf-icon-action lf-quiet-action lf-page-search-step",
  );
  control.type = "button";
  control.tabIndex = -1;
  control.append(iconElement(icon, "lf-action-icon"));
  control.setAttribute("aria-label", name);
  control.title = name;
  control.addEventListener("mousedown", (event) => event.preventDefault());
  return control;
};
const previousMatchControl = matchStep("up", "Previous match");
const nextMatchControl = matchStep("down", "Next match");
const pageSearchControls = [pageSearchStatus, previousMatchControl, nextMatchControl];
const noMatches = "No matches";
const searchCount = (position, total) => `${position} of ${total}`;

// Target choosing and whole-page text search. `s` opens a viewport-local map of
// the same stable addressables and visual parts Alt-click reaches, then opens Comment on the
// chosen target; `/` opens the page's text search directly or from that map. The floating
// panel's Select element opens this same picker. A choice
// in Design mode keeps that mode's design intent; Draw reserves the page for ink and
// offers no picker. Area capture also claims the page until it ends. While the picker
// stands, the page is armed as it is under a held Alt (aim.js): a mouse shows the target
// under it, and a press, by finger or mouse, chooses that target without activating
// authored controls. The key and the modifier are two ways into one gesture, so a press
// means the same under either.
//
// `keyboard/hints.js` owns the map itself: arming, codes, the typed prefix, the audible
// walk, the scroll freeze, and the paint. What this module declares is which members the
// map holds and where each chip sits among them. An ancestor and descendant painting the
// same visible box name one target, and the innermost remains, matching direct aim. A
// target's chip sits outside its own box, keeping controls and their labels readable.
// Shared hint seating separates those faces without moving page content, and steps
// each chip before a nest of targets out by its level in that nest, so a group's chip
// and its members' chips read as an outline (`nestOutsets`, hints.js).
// Admission and clipping stay with key-badge-placement.js.
//
// `/` opens a real search input over the whole page reading, either directly from the
// page or from the visible target hints. Tab walks repeated occurrences, as the box's
// arrows do, and Enter or a press on the active match makes a native browser Selection
// from it. Once the prompt closes, n repeats that
// accepted search and N reverses it. Escape returns to the surface that opened search:
// the page after a direct `/`, or the visible hints after `s` then `/`. The interaction keeps
// `?` available and claims the rest of the page's keyboard while it stands.

export function createTargetPicker({
  scrollToRange,
  hintChrome,
  commentOnTarget,
  updateFab,
  fabAnchorAt,
  pointerModeActive,
  readTargets,
  armChanged,
  searchInPanel,
}) {
  const canChoose = () => anchoringIsReady() && !pointerModeActive();

  let pickerOpen = false;
  let pageSearchOpen = false;
  // The search's matches are a signal because the walk's rows read them for the arrows'
  // availability, which follows the signals it reads (keyboard/scopes.js): a query
  // that arrives with no key, as a paste does, offers the arrows all the same.
  const matches = signal([]);
  let matchesIn = null; // the reading `matches` were found in
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
    return visibleTargetParts(element).length > 0;
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
      openLayer(pageSearchInput);
      paintTargetPicker(on, withHints);
      return;
    }
    // An opener of nowhere hands back nothing, and `handBack` lets the user go.
    const landing = restore && pickerOpen;
    const opener = openerOf(pageSearchInput);
    closeLayer(
      () => paintTargetPicker(on, withHints),
      landing && (() => handBack(opener)),
    );
  }
  function paintTargetPicker(on, withHints) {
    pickerOpen = on;
    pageSearchOpen = false;
    searchReturnsToHints = false;
    matches.value = [];
    active = -1;
    pageSearchInput.value = "";
    presentSearchField();
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

  function presentSearchField() {
    searchInPanel({
      input: pageSearchInput,
      controls: pageSearchControls,
      open: pageSearchOpen,
    });
  }
  function setPageSearch(on) {
    pageSearchOpen = on;
    presentSearchField();
    if (on) {
      // A nonempty query cannot match more often than there are characters. Hold the
      // room of the whole reading's count before editing, so narrowing never resizes
      // the field.
      const maximum = pageText().raw.length;
      keeps(
        pageSearchStatus,
        "data-lf-room",
        `${noMatches}\n${searchCount(maximum, maximum)}`,
      );
      focusDestination(pageSearchInput, "move");
      presentSearchStatus();
      announce("Search the page.");
    } else {
      pageSearchInput.value = "";
      matches.value = [];
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
    const next = found.findIndex(
      (segments) => rangeOf(segments).getBoundingClientRect().bottom > 0,
    );
    return next === -1 ? 0 : next;
  }

  function presentSearchStatus() {
    const query = pageSearchInput.value.trim();
    const status = !query
      ? nothing
      : matches.value.length
        ? searchCount(active + 1, matches.value.length)
        : noMatches;
    render(html`${status}`, pageSearchWords);
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
    if (!query || active < 0 || active >= matches.value.length) return null;
    if (!matchIsRangeable(matches.value[active])) return null;
    // An open search owns its highlighted match. A repeated n/N search owns a native
    // selection instead; leaving that selection retires both its readout and refresh.
    if (!pageSearchOpen && !selectionIs(matches.value[active])) return null;
    return {
      target: matchIdentity(query, matches.value[active]),
      position: active + 1,
      total: matches.value.length,
      qualifier: "",
    };
  }

  function find(query) {
    matchesIn = pageText();
    return findText(matchesIn, query);
  }

  // A match is a run of one reading's segments, placed in the reading it came from. A
  // change to the page's words, such as a revision landing while the search stands open,
  // makes a new reading with no position for the old nodes. So each reader finds the
  // matches again first, keeping the active one where it still stands.
  function refreshMatches() {
    const query = pageSearchOpen ? pageSearchInput.value.trim() : repeatedSearch?.query;
    const current = matches.value[active];
    if (!query || !current || pageText() === matchesIn) return false;
    const found = find(query);
    const same = found.findIndex((candidate) => sameMatch(candidate, current));
    active = same >= 0 ? same : found.length ? Math.min(active, found.length - 1) : -1;
    matches.value = found;
    if (repeatedSearch && !pageSearchOpen && active >= 0) repeatedSearch.index = active;
    return true;
  }

  // Layout invalidation is the mechanical source of an active walk's refresh: a reflow
  // moves the marked line boxes even where the words stand, so the walk repaints either
  // way. The read handed to the shared walk remains a cheap cached lookup.
  function refreshMatchWalk() {
    if (walkPosition()?.kind !== "page-search") return;
    if (refreshMatches() && pageSearchOpen) presentSearchStatus();
    repaint();
  }

  function search() {
    const query = pageSearchInput.value.trim();
    matches.value = query ? find(query) : [];
    active = matches.value.length ? startingMatch(matches.value) : -1;
    presentSearchStatus();
    showMatch();
    repaint();
  }

  function showMatch() {
    const segments = matches.value[active];
    if (!segments || matchRect(segments)) return;
    scrollToRange(rangeOf(segments), "instant");
  }

  function moveMatch(direction) {
    refreshMatches();
    if (!matches.value.length) return presentSearchStatus();
    const { row, wrapped } = cycledRow(matches.value, matches.value[active], direction);
    active = matches.value.indexOf(row);
    presentSearchStatus();
    showMatch();
    const query = pageSearchInput.value.trim();
    beginWalk("page-search", "Match", () => matchWalkPosition(query), wrapped);
    announce(
      `Match ${active + 1} of ${matches.value.length}: ${matchDescription(matches.value[active])}.`,
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
    refreshMatches();
    const segments = matches.value[active];
    if (!segments) return;
    const quote = quoteFrom(matches.value[active]);
    repeatedSearch = { query: pageSearchInput.value.trim(), index: active };
    setTargetPicker(false);
    selectMatch(segments);
    announce(
      `Selected match: ${quote}. ${
        coarsePointer.matches || !bindingEnabled("c")
          ? "A press on the comment field comments on it."
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
    matches.value = find(repeatedSearch.query);
    if (!matches.value.length) {
      repeatedSearch = null;
      active = -1;
      announce("The page no longer contains that search.");
      return repaint();
    }
    const from = Math.min(repeatedSearch.index, matches.value.length - 1);
    const { row, wrapped } = cycledRow(matches.value, matches.value[from], direction);
    active = matches.value.indexOf(row);
    repeatedSearch.index = active;
    showMatch();
    selectMatch(matches.value[active]);
    const query = repeatedSearch.query;
    beginWalk("page-search", "Match", () => matchWalkPosition(query), wrapped);
    announce(
      `Match ${active + 1} of ${matches.value.length}: ${matchDescription(matches.value[active])}.`,
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
      return seated.map(([target, rect]) => {
        const steps = [...target.code];
        return {
          candidate: target,
          model: Object.freeze({
            key: hintRenderKey(hintElement(target)),
            className: `lf-key-badge lf-key-hint lf-target-picker-hint${
              target === current ? " lf-current" : ""
            }${rect.clippedTop || rect.top < 0 ? " lf-in" : ""}`,
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
          top: Math.max(0, rect.top),
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

  // A mark for each box the match's words take, while any of it is in sight, standing
  // over what holds the words and carried by what carries them
  // (`anchorFor`).
  function paintSearchMatches() {
    const segments = matches.value[active];
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
        rect: intersect(box, own),
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
    menu: "navigate",
    keys: ["/"],
    title: "search page",
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
    title: () =>
      pageSearchOpen
        ? searchReturnsToHints
          ? "back to hints"
          : "close search"
        : hints.prefix()
          ? "back one letter"
          : "close picker",
    // The ✕ of both stances (keyboard/AGENTS.md, "Touch routes"). While the user
    // has typed part of a hint it takes back a letter, as its words say; a finger,
    // which types none, always closes.
    exit: true,
    run: back,
  };

  const targetingClaims = (binding) =>
    allButCommandReference(binding) && !bindings(PAGE_SEARCH).includes(binding);

  const TARGET_HINT_TYPE = {
    id: "target.picker.hint.type",
    touch: false,
    keys: HINT_KEYS,
    label: "a–z",
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
      ...hints.walkRows({
        id: "target.picker.hint",
        choose: {
          title: "choose target",
        },
      }),
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
        title: "select match",
        // A finger presses the marked match itself (`pressMatch`).
        touch: false,
        when: () => matches.value.length > 0,
        run: chooseMatch,
      },
      {
        id: "page.search.match.walk",
        keys: ["Tab", "Shift+Tab"],
        touch: false,
        routes: [
          {
            id: "page.search.match.previous",
            binding: "Shift+Tab",
            title: "Go to the previous search match",
            control: previousMatchControl,
          },
          {
            id: "page.search.match.next",
            binding: "Tab",
            title: "Go to the next search match",
            control: nextMatchControl,
          },
        ],
        title: "matches",
        repeat: true,
        when: () => matches.value.length > 0,
        run: (binding) => moveMatch(binding === "Tab" ? 1 : -1),
      },
      TARGETING_BACK,
    ],
  };

  const targetPickerOpen = () => pickerOpen;
  const openTargetPicker = () => setTargetPicker(true);
  const closeTargetPicker = () => setTargetPicker(false);

  // A press on the marked match selects it, as Enter does: the match is what the user is
  // looking at, and a phone's keyboard may offer no Enter. The press's mouse events are
  // the match's alone, claimed at its mousedown and taken at capture to its click: the
  // browser starts no selection from it, the page's selection gesture (surface.js) does
  // not snap it on mouseup, and no link the words stand in is followed. Its pointer
  // events pass, so whatever reads input still hears the press. A press lands on the
  // match only through the block holding its words, so a control painted over them
  // keeps its own.
  let pressOnMatch = false;
  function onMarkedMatch(ev) {
    if (!pageSearchOpen || ev.button !== 0) return false;
    refreshMatches();
    const segments = matches.value[active];
    if (!segments || !ev.composedPath().includes(matchOwner(segments))) return false;
    const { clientX: x, clientY: y } = ev;
    return [...rangeOf(segments).getClientRects()].some(
      (rect) => x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom,
    );
  }
  function pressMatch(ev) {
    if (ev.type === "mousedown") pressOnMatch = onMarkedMatch(ev);
    if (!pressOnMatch) return;
    if (ev.type !== "mouseup") ev.preventDefault();
    ev.stopPropagation();
    if (ev.type !== "click") return;
    pressOnMatch = false;
    chooseMatch();
  }

  function mount() {
    // Connect the native input at startup, hidden in the panel, so its first shadow
    // render is ready before a search gesture asks for focus (including on a phone).
    presentSearchField();
    pageSearchInput.addEventListener("input", search);
    for (const type of ["mousedown", "mouseup", "click"])
      document.addEventListener(type, pressMatch, true);
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
    menu: "annotate",
    when: canChoose,
    run: (/** @type {Parameters<typeof openTargetPicker>} */ ...args) =>
      openTargetPicker(...args),
  });
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
