/* This module owns the target picker and whole-page text search. Its transient hints,
 * search marks, and status are synchronous Lit projections over native controller state. */
import { selectEnds } from "../native-selection.js";
import { anchoringIsReady } from "../anchor-resolution.js";
import { bindings, bindingEnabled, cycledRow, hasRows } from "../keyboard/bindings.js";
import { el, offerAction, searchField } from "../widget-elements.js";
import { LAYOUT } from "../widget-upgrade.js";
import { coarsePointer } from "../pointer.js";
import { html, nothing, render, signal } from "/runtime/framework.js";

import {
  contextAround,
  inChrome,
  pageMatches,
  pageReadingVersion,
  readingHolding,
  quoteFrom,
  rangeOf,
  passageStart,
  segmentPieces,
  segmentsBox,
} from "../passages.js";
import { shownBox } from "../geometry.js";
import { skipped } from "../shadow-tree.js";
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
  codedHints,
  renderKeys,
} from "../keyboard/hints.js";
import { keyBadgePlacement } from "../keyboard/key-badge-placement.js";
import {
  keySequenceModel,
  keySequenceTemplate,
  progressSteps,
} from "../keyboard/key-sequence.js";
import { announce, notice } from "../notifications.js";
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
  placeholder: "Find text…",
});
pageSearchInput.maxlength = 160;
pageSearchInput.withClear = false;
const pageSearchStatus = el("span", "lf-page-search-status");
pageSearchStatus.setAttribute("role", "status");
const pageSearchWords = el("span");
pageSearchStatus.append(pageSearchWords);
// The box walks its own matches, as a browser's find bar does: up and down beside the
// count they move, the walk's one control for a finger and a mouse. A press leaves focus
// in the field, so a phone's keyboard stays up and the next letter still edits the query.
// Tab is their key, so they are no stop of its own.
/** @param {"previous-match" | "next-match"} action */
const matchStep = (action) => {
  const control = offerAction("symbol", "lf-page-search-step", undefined, { action });
  control.tabIndex = -1;
  control.addEventListener("mousedown", (event) => event.preventDefault());
  return control;
};
const previousMatchControl = matchStep("previous-match");
const nextMatchControl = matchStep("next-match");
const pageSearchControls = [pageSearchStatus, previousMatchControl, nextMatchControl];
const noMatches = "No matches";
const searching = "Searching";
/** @param {number} position @param {number} total */
// Where the user stands among the matches, as every walk says it.
const searchCount = (position, total) => `${position} of ${total}`;

// Target choosing and whole-page text search. `s` opens a viewport-local map of
// the same stable addressables and visual parts Alt-click reaches, then opens Comment on the
// chosen target; `/` opens the page's text search directly or from that map. The leaf
// menu's Annotations → Select mode opens this same picker. A choice
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
// from it. Accepting a match keeps its live position after the prompt closes; n repeats
// that accepted search and N reverses it. Starting or canceling a search, or entering
// another page mode, retires that position without forgetting the accepted query.
// Escape returns to the surface that opened search:
// the page after a direct `/`, or the visible hints after `s` then `/`. The interaction keeps
// `?` available and claims the rest of the page's keyboard while it stands.

/** @typedef {import("../passages.js").Segment[]} Match
 * @typedef {ReturnType<typeof keyBadgePlacement>} PlacementReading
 * @typedef {ReturnType<typeof keyBadgePlacement>["visibleBounds"] extends (...args: never[]) => infer T ? NonNullable<T> : never} VisibleBox
 * @typedef {import("../anchor-resolution.js").AimTarget} PickerTarget
 * @typedef {Object} TargetPickerOptions
 * @property {ReturnType<typeof import("../anchor-travel.js").createAnchorTravel>["scrollToPassage"]} scrollToPassage
 * @property {{barriers: () => import("../rect.js").Box[]}} hintChrome
 * @property {(target: PickerTarget) => unknown} commentOnTarget
 * @property {() => unknown} updateFab
 * @property {() => import("./selection.js").Anchor | null} fabAnchorAt
 * @property {() => boolean} pointerModeActive
 * @property {() => PickerTarget[]} readTargets
 * @property {() => unknown} armChanged
 * @property {(reading: {input: typeof pageSearchInput, controls: readonly HTMLElement[], open: boolean}) => unknown} searchInPanel
 */
/** @param {TargetPickerOptions} options */
export function createTargetPicker({
  scrollToPassage,
  hintChrome,
  commentOnTarget,
  updateFab,
  fabAnchorAt,
  pointerModeActive,
  readTargets,
  armChanged,
  searchInPanel,
}) {
  const searchQuery = () => pageSearchInput.value?.trim() ?? "";
  const canChoose = () => anchoringIsReady() && !pointerModeActive();

  // Mode predicates feed tracked keyboard controls and the shared panel, so mode
  // changes publish themselves even when accepting a match retains its list.
  const pickerMode = signal("closed");
  const targetPickerOpen = () => pickerMode.value !== "closed";
  const pageSearchOpen = () => pickerMode.value === "search";
  // The search's matches are a signal because the walk's rows read them for the arrows'
  // availability, which follows the signals it reads (keyboard/scopes.js): a query
  // that arrives with no key, as a paste does, offers the arrows all the same.
  /** @type {import("@preact/signals-core").Signal<Match[]>} */
  const matches = signal([]);
  /** @type {object | null} */
  let matchesIn = null; // the page reading `matches` were found in (`pageReadingVersion`)
  let matchesFor = ""; // the query they match
  let active = -1;
  // A search's matches arrive a slice at a time (passages.js, `pageMatches`): the first
  // slice in the task the query changed in, each later one in a task of its own, so no
  // search holds the page while it reads documents the page hasn't read or checks a
  // million matches. `matches` holds what has arrived, in reading order. Its signal
  // changes as the first match arrives, which is all its readers ask (the arrows'
  // availability), and the array grows in place after. `pending` finds the rest. A step
  // or a choice takes matches at once until it can be answered as it would be with every
  // match in (`settle`).
  /** @type {Iterator<Match | null> | null} */
  let pending = null;
  // Where the search lands once it can tell: the match the search stood on before the
  // page changed, found again, else the match at its index; for a new query, the first
  // match at or below the top of the window, else the first. `show` brings it into view.
  /** @type {{was: Match | null, index: number, show: boolean} | null} */
  let landing = null;
  // How long a slice searches before the page may draw.
  const SLICE_MS = 8;
  let searchReturnsToHints = false;
  /** @type {{query: string, index: number} | null} */
  let repeatedSearch = null;
  /** @type {WeakMap<Text, number>} */
  const matchNodeIds = new WeakMap();
  let nextMatchNodeId = 1;

  // Target elements and text coordinates stay outside the immutable readings. Lit receives
  // only opaque primitive identities, retaining unchanged hint and keycap nodes on repaint.
  const hintRenderKey = renderKeys();
  // The open search's mark stands over its words in the frames that cut them, carried
  // by what carries the words (target-paint-geometry.js, `paintSet`), so no scroll
  // writes it.
  const marks = paintSet(markRoot);
  /** @type {Map<number, HTMLElement>} */
  const markBoxes = new Map();

  // One reading of the room the user has, shared by every member of a pass: the clips
  // over their common ancestors are walked once, and admission, exposure, and paint read
  // the same boxes.
  const room = keyBadgePlacement;
  // Chromium retains geometry for descendants suppressed by a closed disclosure. Ask
  // visibility before geometry so those descendants cost no box reads. A display: contents
  // addressable has no box of its own and stays eligible through a visible child.
  /** @param {PickerTarget} target */
  const hintElement = (target) => target.controlElement ?? target.element;
  /** @param {PickerTarget} target @param {PlacementReading} reading */
  const targetBounds = (target, reading) =>
    union(
      (target.controlFaces ?? [hintElement(target)])
        .map((face) => ({ face, rect: reading.visibleBounds(face) }))
        .flatMap(({ face, rect }) =>
          rect && reading.exposes(face, rect) ? [rect] : [],
        ),
    );
  /** @param {PickerTarget} target */
  const targetShown = (target) => {
    const element = hintElement(target);
    return visibleTargetParts(element).length > 0;
  };

  // The first part of a match's lines the user can see, each piece clipped by what
  // clips its own block.
  /** @param {Match} segments @param {PlacementReading} reading */
  function firstShown(segments, reading) {
    for (const { segment, block, lines } of segmentPieces(segments)) {
      const holder = segment.node.parentElement;
      if (!block || (holder && skipped(holder))) continue;
      const clip = reading.clipOver(block);
      const part =
        clip &&
        lines
          .map((box) => reading.clearPart(box, clip, block))
          .find((shown) => reading.exposes(null, shown));
      if (part) return part;
    }
    return null;
  }

  /** @param {import("../rect.js").Box} a @param {import("../rect.js").Box} b */
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
      .filter(
        /** @returns {target is PickerTarget & {rect: NonNullable<ReturnType<typeof targetBounds>>}} */ (
          target,
        ) => target.rect !== null,
      )
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
    return codedHints(unique);
  }

  // `withHints` opens the shared mode without a target map: a direct slash is page
  // search over the whole document, and reading a viewport-local map it would then hide
  // is work for nobody.
  // The picker's opener is the control the user was on as it opened (focus.js,
  // `openLayer`); a close that restores hands them back to it as it closes.
  /** @param {boolean} on @param {boolean} [restore] @param {boolean} [withHints] */
  function setTargetPicker(on, restore = false, withHints = true) {
    if (on && (!anchoringIsReady() || (withHints && !canChoose()))) return;
    if (on) {
      openLayer(pageSearchInput);
      paintTargetPicker(on, withHints);
      return;
    }
    // An opener of nowhere hands back nothing, and `handBack` lets the user go.
    const landing = restore && targetPickerOpen();
    const opener = openerOf(pageSearchInput);
    closeLayer(
      () => paintTargetPicker(on, withHints),
      landing && (() => handBack(opener)),
    );
  }
  /** @param {boolean} on @param {boolean} withHints */
  function paintTargetPicker(on, withHints) {
    pickerMode.value = on ? "hints" : "closed";
    if (on) clearMatches();
    searchReturnsToHints = false;
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
      open: pageSearchOpen(),
    });
  }
  function clearMatches() {
    matches.value = [];
    matchesIn = null;
    matchesFor = "";
    active = -1;
    pending = null;
    landing = null;
  }
  // Whether a step from match `at` goes back past the first while the search runs.
  /** @param {number} at @param {import("../keyboard/bindings.js").Step} direction */
  const stillFinding = (at, direction) => pending !== null && direction < 0 && at === 0;
  /** @param {boolean} on */
  function setPageSearch(on) {
    pickerMode.value = on ? "search" : "hints";
    presentSearchField();
    if (on) {
      focusDestination(pageSearchInput, "move");
      presentSearchStatus();
      announce("Search the page.");
    } else {
      pageSearchInput.value = "";
      clearMatches();
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
    const fromHints = targetPickerOpen();
    if (!targetPickerOpen()) setTargetPicker(true, false, false);
    searchReturnsToHints = fromHints;
    setPageSearch(true);
  }

  /** @param {Match} segments @param {PlacementReading} [reading] */
  function matchRect(segments, reading = room()) {
    return firstShown(segments, reading);
  }

  // While the search runs, the count grows where it stands, and before it lands the
  // slot, as wide as "99 of 99", shows an ellipsis. The status is busy meanwhile, so a
  // screen reader says the count once the search ends rather than at each slice.
  function presentSearchStatus() {
    const query = searchQuery();
    const total = matches.value.length;
    const status = !query
      ? nothing
      : pending && active < 0
        ? "…"
        : total
          ? searchCount(active + 1, total)
          : searchCount(0, 0);
    const label = !query
      ? null
      : pending && active < 0
        ? searching
        : total
          ? `Match ${active + 1} of ${total}${pending ? " so far" : ""}`
          : noMatches;
    keeps(pageSearchStatus, "aria-label", label);
    keeps(pageSearchStatus, "aria-busy", query && pending ? "true" : null);
    render(html`${status}`, pageSearchWords);
  }

  /** @param {Match} left @param {Match} right */
  function sameMatch(left, right) {
    return (
      left.length === right.length &&
      left.every(
        (segment, index) =>
          segment.node === right[index]?.node &&
          segment.start === right[index]?.start &&
          segment.end === right[index]?.end,
      )
    );
  }

  /** @param {string} query @param {Match} segments */
  function matchIdentity(query, segments) {
    const parts = segments.map(({ node, start, end }) => {
      if (!matchNodeIds.has(node)) matchNodeIds.set(node, nextMatchNodeId++);
      return `${matchNodeIds.get(node)}:${start}:${end}`;
    });
    return `${query}\u0000${parts.join(",")}`;
  }

  /** @param {Match} segments */
  function matchIsRangeable(segments) {
    return (
      segments.length > 0 &&
      segments.every(
        ({ node, start, end }) =>
          node.isConnected && start >= 0 && start <= end && end <= node.length,
      )
    );
  }

  /** @param {Match} segments */
  function selectionIs(segments) {
    const selection = getSelection();
    if (
      !selection ||
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

  /** @param {string} query */
  function matchWalkPosition(query) {
    const selected = matches.value[active];
    if (!query || !selected || !matchIsRangeable(selected)) return null;
    // An open search owns its highlighted match. An accepted search owns a native
    // selection instead; leaving that selection retires both its readout and refresh.
    if (!pageSearchOpen() && !selectionIs(selected)) return null;
    return {
      target: matchIdentity(query, selected),
      position: active + 1,
      total: matches.value.length,
      qualifier: "",
    };
  }

  // Starts a search for `query`, landing as `to` says, or nowhere without it, and takes
  // its first slice.
  /** @param {string} query @param {{ was: Match | null, index: number, show: boolean } | null} to
   * @returns {void} */
  function find(query, to) {
    matchesIn = pageReadingVersion();
    matchesFor = query;
    pending = query ? pageMatches(query) : null;
    landing = query ? to : null;
    matches.value = [];
    active = -1;
    findMore(true);
  }

  // The search again, standing where it stood, after the page changed under it.
  function restart() {
    find(
      matchesFor,
      landing ?? {
        was: matches.value[active] ?? null,
        index: Math.max(active, 0),
        show: false,
      },
    );
  }

  // One slice of the standing search, and the next asked for while it stands. The count
  // is drawn each slice, and the page after the first, where the search lands and where
  // it ends.
  /** @param {boolean} [first] @returns {void} */
  function findMore(first = false) {
    const search = pending;
    if (search && pageReadingVersion() !== matchesIn) {
      // A search the field no longer shows, as after Enter, stops where the page
      // changed; `n` searches again (`repeatSearch`).
      if (!pageSearchOpen()) {
        pending = null;
        return;
      }
      return restart();
    }
    const landed = search !== null && take(() => false, performance.now() + SLICE_MS);
    presentSearchStatus();
    if (landed || !pending || first) repaint();
    if (pending) setTimeout(() => pending === search && findMore());
  }

  // Takes the standing search's matches until `enough` holds of them or the clock passes
  // `until`, landing it as soon as a match tells where; whether it landed.
  /** @param {(found: Match[]) => boolean} enough @param {number} until */
  function take(enough, until) {
    const search = /** @type {Iterator<Match | null>} */ (pending);
    const found = matches.value;
    const from = found.length;
    for (let next = search.next(); ; next = search.next()) {
      if (next.done) {
        pending = null;
        break;
      }
      if (next.value) {
        found.push(next.value);
        if (active < 0 && landing && landsOn(next.value, landing.was))
          active = found.length - 1;
      }
      if (enough(found) || performance.now() >= until) break;
    }
    if (found.length && !from) matches.value = [...found];
    if (!landing) return false;
    if (active < 0 && !pending && found.length)
      active = landing.was ? Math.min(landing.index, found.length - 1) : 0;
    if (active < 0 && pending) return false;
    const { show } = landing;
    landing = null;
    if (repeatedSearch && !pageSearchOpen() && active >= 0)
      repeatedSearch.index = active;
    if (show) showMatch();
    return true;
  }
  // Whether the search lands on `match`: the match it stood on, found again, or for a
  // new query the first at or below the top of the window.
  /** @param {Match} match @param {Match | null} was */
  const landsOn = (match, was) =>
    was ? sameMatch(match, was) : segmentsBox(match).bottom > 0;

  // Takes matches at once until a step or a choice can be answered as it would be with
  // every match in: the search has landed, where it lands, and `more` holds of what has
  // arrived, or it has ended. The page changing under the search starts it again, so a
  // step after a match revealed a closed tab waits for the match it stood on. A step
  // back past the first match is the one step whose match comes last, so while the
  // search runs it stays put (`stillFinding`) rather than wait for all of it.
  /** @param {(found: Match[]) => boolean} [more] */
  function settle(more = () => true) {
    if (pending && pageReadingVersion() !== matchesIn) restart();
    else refreshMatches();
    /** @param {Match[]} found */
    const enough = (found) => (active >= 0 || !landing) && more(found);
    if (!pending || enough(matches.value)) return;
    take(enough, Infinity);
  }

  // A match is a run of one reading's segments, placed in the reading it came from. A
  // change to the page's words, such as a revision landing while the search stands open,
  // makes a new reading with no position for the old nodes. So each reader of the open
  // search finds the matches again first, keeping the active one where it still stands.
  // Once the field has closed, only `n` searches again (`repeatSearch`), so a page an
  // agent keeps revising runs no search the user has finished with.
  function refreshMatches() {
    const query = searchQuery();
    const current = matches.value[active];
    if (!pageSearchOpen() || !query || !current || pageReadingVersion() === matchesIn)
      return false;
    find(query, { was: current, index: active, show: false });
    return true;
  }

  // Layout invalidation is the mechanical source of an active walk's refresh: a reflow
  // moves the marked line boxes even where the words stand, so the walk repaints either
  // way. The read handed to the shared walk remains a cheap cached lookup.
  function refreshMatchWalk() {
    if (walkPosition()?.kind !== "page-search") return;
    if (refreshMatches() && pageSearchOpen()) presentSearchStatus();
    repaint();
  }

  function search() {
    find(searchQuery(), { was: null, index: 0, show: true });
  }

  // A match out of sight is brought into it where its words start (anchor-travel.js,
  // `scrollToPassage`).
  function showMatch() {
    const segments = matches.value[active];
    if (!segments || matchRect(passageStart(segments))) return;
    scrollToPassage(segments, "instant");
  }

  /** @param {import("../keyboard/bindings.js").Step} direction */
  function moveMatch(direction) {
    settle((found) => direction < 0 || active + 1 < found.length);
    const found = matches.value;
    if (!hasRows(found)) return presentSearchStatus();
    if (stillFinding(active, direction)) {
      presentSearchStatus();
      return notice(searching);
    }
    const selected = cycledRow(found, found[active], direction);
    active = found.indexOf(selected);
    presentSearchStatus();
    showMatch();
    const query = searchQuery();
    beginWalk("page-search", "Match", () => matchWalkPosition(query));
    announce(
      `Match ${active + 1} of ${matches.value.length}: ${matchDescription(selected)}.`,
    );
    repaint();
  }

  /** @param {Match} segments */
  function matchDescription(segments) {
    const { before, after } = contextAround(
      readingHolding(segments[0]?.node ?? document.body),
      segments,
    );
    const phrase = quoteFrom(segments);
    return `${before ? `…${before} ` : ""}${phrase}${after ? ` ${after}…` : ""}`;
  }

  /** @param {PickerTarget} candidate */
  function chooseTarget(candidate) {
    const target = candidate.capture ? candidate.capture() : candidate;
    closeTargetPicker();
    releaseFocus();
    commentOnTarget(target);
    announce(`Chosen ${target.label}.`);
  }

  function chooseMatch() {
    settle();
    const segments = matches.value[active];
    if (!segments) return;
    const quote = quoteFrom(segments);
    repeatedSearch = { query: searchQuery(), index: active };
    // Closing the prompt transfers the match to a native selection. Its position stays
    // live until that selection is left, just as a subsequent n/N landing does.
    setTargetPicker(false);
    landOnMatch(segments, repeatedSearch.query);
    announce(
      `Selected match: ${quote}. ${
        coarsePointer.matches || !bindingEnabled("c")
          ? "A press on the comment field comments on it."
          : "Press n for next, Shift+n for previous, or c to comment."
      }`,
    );
  }

  /** @param {Match} segments @param {string} query */
  function landOnMatch(segments, query) {
    releaseFocus();
    const first = segments[0];
    const last = segments.at(-1);
    if (first && last) selectEnds([first.node, first.start], [last.node, last.end]);
    updateFab();
    beginWalk("page-search", "Match", () => matchWalkPosition(query));
  }

  /** @param {import("../keyboard/bindings.js").Step} direction */
  function repeatSearch(direction) {
    const repetition = repeatedSearch;
    if (!repetition) return;
    const { index } = repetition;
    // It steps from where it stood, so the search it starts again lands nowhere.
    if (matchesFor !== repetition.query || pageReadingVersion() !== matchesIn)
      find(repetition.query, null);
    settle((found) => found.length > index + (direction > 0 ? 1 : 0));
    const found = matches.value;
    if (!hasRows(found)) {
      repeatedSearch = null;
      active = -1;
      notice(`No matches left for “${repetition.query}”`);
      return repaint();
    }
    const from = Math.min(index, found.length - 1);
    if (stillFinding(from, direction)) return notice(searching);
    const selected = cycledRow(found, found[from], direction);
    active = found.indexOf(selected);
    repetition.index = active;
    showMatch();
    landOnMatch(selected, repetition.query);
    announce(
      `Match ${active + 1} of ${matches.value.length}: ${matchDescription(selected)}.`,
    );
  }

  function back() {
    if (pageSearchOpen()) {
      if (searchReturnsToHints) return setPageSearch(false);
      closeTargetPicker(true);
      announce("Page search closed.");
      return;
    }
    closeTargetPicker(true);
    announce("Target picker closed.");
  }

  /** @param {{className: string, hintCode: string, sequence: ReturnType<typeof keySequenceModel>}} model */
  const hintTemplate = (model) =>
    html`<span class=${model.className} data-lf-hint-code=${model.hintCode}
      >${keySequenceTemplate(model.sequence)}</span
    >`;

  // The picker's hints and the open search's marks are two faces in one layer, and only
  // one of them stands at a time: search covers the map that opened it.
  /** @type {import("../keyboard/hints.js").HintSessionOptions<ReturnType<typeof visibleTargets>[number], PlacementReading, {key: number, className: string, hintCode: string, sequence: ReturnType<typeof keySequenceModel>} >} */
  const hintOptions = {
    layer: hintRoot,
    walk: "target-picker",
    read: visibleTargets,
    identity: hintElement,
    scene: room,
    layout: (candidates, { current, reading }) => {
      const seated = candidates.flatMap((target) => {
        const rect = targetShown(target) ? targetBounds(target, reading) : null;
        return rect ? [{ target, rect }] : [];
      });
      return seated.map(({ target, rect }) => {
        const steps = [...target.code];
        return {
          candidate: target,
          model: Object.freeze({
            key: hintRenderKey(hintElement(target)),
            className: `lf-key-badge lf-key-hint lf-target-picker-hint${
              target === current ? " lf-current" : ""
            }${rect.top < 0 ? " lf-in" : ""}`,
            hintCode: target.code,
            sequence: keySequenceModel(progressSteps(steps, [...hints.prefix()])),
          }),
          target: rect,
          placement: target.controlElement ? "above" : "before",
          // A control's key tries just above its upper-left corner, then before it;
          // an owner's tries before it, then above; failing both, it stands on the
          // corner `left` and `top` name (keyboard/hints.js, `seatHints`).
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
  };
  const hints = createHintSession(hintOptions);

  // A mark for each box the match's words take, while any of it is in sight, standing
  // over the block that holds each piece's words, clipped by what clips that block and
  // carried by what carries the piece (`anchorFor`).
  function paintSearchMatches() {
    const segments = matches.value[active];
    if (!segments || !matchIsRangeable(segments)) return marks.place([]);
    const reading = room();
    const boxes = segmentPieces(segments).flatMap(({ segment, block, lines }) => {
      const clip = block && reading.clipOver(block);
      const own = block && shownBox(block);
      if (!block || !clip || !own) return [];
      const anchor = anchorFor(segment.node);
      return lines
        .filter((box) => reading.exposes(null, reading.clearPart(box, clip, block)))
        .map((box) => ({ target: block, anchor, rect: intersect(box, own) }));
    });
    marks.place(
      boxes.map((box, index) => {
        let node = markBoxes.get(index);
        if (!node) {
          node = el("span", "lf-page-search-match");
          markBoxes.set(index, node);
        }
        return { node, held: true, ...box };
      }),
    );
  }

  function paintTargetPickerHints() {
    if (pageSearchOpen()) return paintSearchMatches();
    marks.place([]);
    hints.paint();
  }

  /** @type {import("../keyboard/bindings.js").Command} */
  const PAGE_SEARCH = {
    id: "page.search.open",
    // A finger can select words it can see, but not find them elsewhere on a long page.
    touch: "Search page",
    menu: "navigate",
    keys: ["/"],
    title: "search page",
    when: () => anchoringIsReady() && !pageSearchOpen(),
    run: openPageSearch,
  };

  /** @type {import("../keyboard/bindings.js").Command} */
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
    travels: true,
    // With no search to repeat, the press says so, as every walk with nothing to step
    // through does (keyboard/AGENTS.md, "Page grammar").
    runKey: (binding) =>
      repeatedSearch
        ? repeatSearch(binding === "n" ? 1 : -1)
        : notice("No search to repeat"),
  };

  // Escape takes back a typed hint letter, one at a time, before it closes the picker,
  // as a step of its own (`TARGETING_LETTER`), so the way out's words, key and press
  // always end what they name.
  const lettersTyped = () => !pageSearchOpen() && Boolean(hints.prefix());
  /** @type {import("../keyboard/bindings.js").Command} */
  const TARGETING_LETTER = {
    id: "targeting.letter.back",
    keys: ["Escape"],
    title: "back one letter",
    touch: false,
    when: lettersTyped,
    run: () => hints.backOneLetter(),
  };
  /** @type {import("../keyboard/bindings.js").Command} */
  const TARGETING_BACK = {
    id: "targeting.back",
    keys: () => (lettersTyped() ? [] : ["Escape"]),
    title: () =>
      pageSearchOpen()
        ? searchReturnsToHints
          ? "back to hints"
          : "close search"
        : "close picker",
    // The way out of both stances, which the panel offers (keyboard/AGENTS.md, "Touch
    // routes"). Its press closes the picker, typed letters and all.
    exit: true,
    run: back,
  };

  /** @param {string} binding */
  const targetingClaims = (binding) =>
    allButCommandReference(binding) && !bindings(PAGE_SEARCH).includes(binding);

  /** @type {import("../keyboard/bindings.js").Command} */
  const TARGET_HINT_TYPE = {
    id: "target.picker.hint.type",
    touch: false,
    keys: HINT_KEYS,
    label: "a–z",
    title: "type hint",
    travels: true,
    when: () => hints.candidates().length > 0,
    runKey: hints.type,
  };

  /** @type {import("../keyboard/bindings.js").Scope} */
  const TARGET_PICKER_SCOPE = {
    title: "In the target picker",
    escape: "inner",
    at: () => pickerMode.value === "hints",
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
      TARGETING_LETTER,
      TARGETING_BACK,
    ],
  };

  /** @type {import("../keyboard/bindings.js").Scope} */
  const PAGE_SEARCH_SCOPE = {
    title: "In page search",
    escape: "inner",
    at: () => pageSearchOpen(),
    claims: targetingClaims,
    rows: [
      {
        id: "page.search.match.select",
        keys: ["Enter"],
        title: "select match",
        travels: true,
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
        travels: true,
        when: () => matches.value.length > 0,
        runKey: (binding) => moveMatch(binding === "Tab" ? 1 : -1),
      },
      TARGETING_BACK,
    ],
  };

  const openTargetPicker = () => setTargetPicker(true);
  const closeTargetPicker = (restore = false) => {
    clearMatches();
    setTargetPicker(false, restore);
  };

  // A press on the marked match selects it, as Enter does: the match is what the user is
  // looking at, and a phone's keyboard may offer no Enter. The press's mouse events are
  // the match's alone, claimed at its mousedown and taken at capture to its click: the
  // browser starts no selection from it, the page's selection gesture (surface.js) does
  // not snap it on mouseup, and no link the words stand in is followed. Its pointer
  // events pass, so whatever reads input still hears the press. A press lands on the
  // match only through the block holding its words, so a control painted over them
  // keeps its own.
  let pressOnMatch = false;
  /** @param {MouseEvent} ev */
  function onMarkedMatch(ev) {
    if (!pageSearchOpen() || ev.button !== 0) return false;
    refreshMatches();
    const segments = matches.value[active];
    if (!segments) return false;
    const path = ev.composedPath();
    const { clientX: x, clientY: y } = ev;
    return segmentPieces(segments).some(
      ({ block, lines }) =>
        block &&
        path.includes(block) &&
        lines.some(
          (rect) =>
            x >= rect.left && x <= rect.right && y >= rect.top && y <= rect.bottom,
        ),
    );
  }
  /** @param {MouseEvent} ev */
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
    /** @type {readonly ("mousedown" | "mouseup" | "click")[]} */
    const mouseEvents = ["mousedown", "mouseup", "click"];
    for (const type of mouseEvents) document.addEventListener(type, pressMatch, true);
    hints.mount();
    addEventListener("resize", () => {
      if (pageSearchOpen()) repaint();
    });
    document.addEventListener(LAYOUT, refreshMatchWalk);
  }
  pageScope("page search", PAGE_SEARCH_SCOPE);
  pageScope("target picker", TARGET_PICKER_SCOPE);
  // The page itself is already a Comment target; `s` plus a hint names a more particular
  // one. Either route opens Comment, while reactions wait for a target. The leaf menu's
  // Annotations lists it for every pointer. The user chose this on 24 October 2026 over
  // listing it only where no keyboard was there to press `s`: a mouse user who never
  // learned `s` had no visible way to comment on a whole widget or picture, since
  // selecting words picks neither. A row at the menu's top level was shown and set
  // aside for Annotations. It is named Select mode beside Draw and Design mode, as the
  // user chose on 30 October over Comment on an element.
  pageCommand({
    id: "target.picker.open",
    keys: ["s"],
    description: () =>
      bindings(TARGET_HINT_TYPE).length
        ? "Choose an element by pressing it or typing its hint, then comment"
        : "Choose an element by pressing it or browsing targets with Tab and Enter, then comment",
    title: "select mode",
    touch: "Select mode",
    menu: "annotate",
    when: canChoose,
    run: openTargetPicker,
  });
  pageCommand(PAGE_SEARCH);
  pageCommand(REPEAT_PAGE_SEARCH);

  return {
    visibleTargets,
    chooseTarget,
    // The map, not the mode: a direct slash opens the mode for search alone.
    choosing: () => hints.armed() && !pageSearchOpen(),
    paintTargetPickerHints,
    targetPickerOpen,
    openTargetPicker,
    closeTargetPicker,
    mount,
  };
}
