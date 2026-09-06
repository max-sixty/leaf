/* This module owns keyboard item hints and whole-page text search. */
import { aimTargets, anchoringIsReady, sameAnchor, scrollToRange } from "../anchors.js";
import { bindings } from "../keyboard/bindings.js";
import { el } from "../widget-elements.js";
import { banner } from "../banner.js";
import { keylineEl } from "../keyboard/keyline.js";
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
import { focused, paintHere } from "../keyboard/scopes.js";
import { HINT_KEYS, hintCodes, spreadHints } from "../keyboard/hints.js";
import { announce } from "../notifications.js";
import { selectTarget, updateFab } from "./surface.js";
import {
  allButTheReference,
  hasCapturedTarget,
  responseInstructions,
} from "../keyboard/page.js";

// The selection chooser's two faces. Hints and the active search result are paint only;
// the search box is a real control, kept beside them so its focus and accessible name are
// the platform's rather than a keyboard mode's imitation of one.
export const selectionLayer = el("div", "lf-ui lf-targets");
selectionLayer.setAttribute("aria-hidden", "true");
export const selectionSearch = el("div", "lf-ui lf-target-search");
selectionSearch.setAttribute("role", "search");
selectionSearch.hidden = true;
const selectionInput = document.createElement("input");
selectionInput.className = "lf-target-search-box";
selectionInput.type = "search";
selectionInput.autocomplete = "off";
selectionInput.spellcheck = false;
selectionInput.maxLength = 160;
selectionInput.placeholder = "Search page text";
selectionInput.setAttribute("aria-label", "Search page text");
const selectionStatus = el("span", "lf-target-search-status");
selectionStatus.setAttribute("role", "status");
selectionSearch.append(selectionInput, selectionStatus);

// Keyboard item selection and whole-page text search. `s` opens a viewport-local map of
// the same stable items and visual parts Alt-click reaches, then raises their general
// response actions; `/` opens the page's text search directly or from that map.
//
// The short, viewport-local hints form a prefix-free tree over one alphabet. Most
// targets cost one letter; only the tail branches when the viewport holds more targets
// than the alphabet. Unlike `g` addresses, these hints are ephemeral and make no promise
// across a scroll or revision. They are the whole route, so none may be dropped because
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
// Tab and Shift-Tab walk the visible target map and announce each item. Enter chooses
// the last one announced. A viewport change that removes or renames that target clears
// the announced choice before Enter can act on it.
//
// `/` opens a real search input over the whole page reading, either directly from the
// page or from the visible item hints. Tab walks repeated occurrences and Enter makes a
// native browser Selection from the active match. Escape returns to the surface that
// opened search: the page after a direct `/`, or the visible hints after `s` then `/`.
// The mode keeps `?` available and claims the rest of the page's keyboard while it
// stands.

const HINT_INDENT = 10;

let open = false;
let searching = false;
let prefix = "";
let candidates = [];
let matches = [];
let active = -1;
let hintActive = -1;
let opener = null;
let searchReturnsToHints = false;
let scrolling = false;

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
// spans the window and clips one edge. The key line is a bottom band in one horizontal
// lane, so a target crossing that lane keeps the larger of the space above, before, or
// after it. Treating the line's top as a scalar dropped a target merely because some
// other part of its box stood behind unrelated chrome on the left.
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
  const line = keylineEl.getBoundingClientRect();
  const band = {
    left: line.left,
    top: line.top,
    right: line.right,
    bottom: innerHeight,
  };
  if (!line.height || !overlaps(shown, band)) return shown;
  return (
    [
      rect(
        shown.left,
        shown.top,
        shown.right,
        Math.min(shown.bottom, band.top),
        sourceTop,
      ),
      rect(
        shown.left,
        shown.top,
        Math.min(shown.right, band.left),
        shown.bottom,
        sourceTop,
      ),
      rect(
        Math.max(shown.left, band.right),
        shown.top,
        shown.right,
        shown.bottom,
        sourceTop,
      ),
    ]
      .filter(Boolean)
      .sort((a, b) => b.width * b.height - a.width * a.height)[0] ?? null
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
// item has no box of its own and stays eligible through a visible child.
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

export function visibleTargets() {
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
  // Direct aiming chooses the innermost stable item under the pointer. When an
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

function setOpen(on, restore = false, withHints = true) {
  if (on && !anchoringIsReady()) return;
  if (on) opener = focused();
  const returnTo = !on && restore ? opener : null;
  open = on;
  searching = false;
  searchReturnsToHints = false;
  prefix = "";
  matches = [];
  active = -1;
  hintActive = -1;
  scrolling = false;
  selectionInput.value = "";
  selectionSearch.hidden = true;
  if (on && withHints) {
    candidates = visibleTargets();
    if (!candidates.length) {
      announce("There is no visible item to select. Press slash to search the page.");
    } else {
      announce(
        `Select an item — type one of ${candidates.length} hints, press Tab to hear them, or slash to search the page.`,
      );
    }
  } else if (!on) {
    candidates = [];
    selectionLayer.replaceChildren();
    opener = null;
  } else {
    candidates = [];
  }
  paintHere();
  if (returnTo?.isConnected) returnTo.focus({ preventScroll: true });
}

function setSearching(on) {
  searching = on;
  prefix = "";
  hintActive = -1;
  selectionSearch.hidden = !on;
  if (on) {
    selectionInput.focus({ preventScroll: true });
    selectionStatus.textContent = "";
    announce("Search the page.");
  } else {
    selectionInput.value = "";
    matches = [];
    active = -1;
    document.body.focus({ preventScroll: true });
    announce("Select an item — type a hint, or slash to search the page.");
  }
  paintHere();
}

function startSearching() {
  const fromHints = open;
  if (!open) setOpen(true, false, false);
  searchReturnsToHints = fromHints;
  setSearching(true);
}

const matchRange = () => (matches[active] ? rangeOf(matches[active]) : null);

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
  if (!selectionInput.value.trim()) selectionStatus.textContent = "";
  else if (!matches.length) selectionStatus.textContent = "No matches";
  else selectionStatus.textContent = `${active + 1} of ${matches.length}`;
}

function search() {
  const query = selectionInput.value.trim();
  matches = query ? findText(pageText(), query) : [];
  active = matches.length ? startingMatch(matches) : -1;
  syncStatus();
  showMatch();
  paintHere();
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
  announce(
    `Match ${active + 1} of ${matches.length}: ${matchDescription(matches[active])}.`,
  );
  paintHere();
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

function choose(target) {
  setOpen(false);
  document.body.focus({ preventScroll: true });
  selectTarget(target);
  announce(`Selected ${target.label}. ${responseInstructions()}`);
}

function typeHint(key) {
  hintActive = -1;
  prefix += key;
  const left = candidates.filter(({ code }) => code.startsWith(prefix));
  const target = left.find(({ code }) => code === prefix);
  if (target) return choose(target);
  if (!left.length) {
    prefix = "";
    announce("That hint is not on screen. The hints are reset.");
  } else announce(`${left.length} items remain.`);
  paintHere();
}

const hinted = () => candidates.filter(({ code }) => code.startsWith(prefix));

function moveHint(direction) {
  const targets = hinted();
  if (!targets.length) return;
  hintActive = (hintActive + direction + targets.length) % targets.length;
  const target = targets[hintActive];
  announce(`Hint ${target.code}: ${cut(target.label, 0, 72)}. Press Enter to select.`);
  paintHere();
}

function chooseHint() {
  const target = hinted()[hintActive];
  if (target) choose(target);
}

function chooseMatch() {
  const range = matchRange();
  if (!range) return;
  const quote = quoteFrom(matches[active]);
  setOpen(false);
  document.body.focus({ preventScroll: true });
  const selection = getSelection();
  selection.removeAllRanges();
  selection.addRange(range);
  updateFab();
  announce(`Selected match: ${cut(quote, 0, 72)}. Press c to comment.`);
}

function back() {
  if (searching) {
    if (searchReturnsToHints) return setSearching(false);
    setOpen(false, true);
    announce("Page search closed.");
    return;
  }
  if (prefix) {
    prefix = prefix.slice(0, -1);
    hintActive = -1;
    announce(prefix ? `Hint ${prefix}.` : "All item hints.");
    return paintHere();
  }
  setOpen(false, true);
  announce("Selection cancelled.");
}

function hintChip(target) {
  const chip = el("span", "lf-address lf-target-hint");
  chip.dataset.lfTarget = target.code;
  if (hinted()[hintActive] === target) chip.classList.add("lf-current");
  if (prefix) {
    chip.append(
      el("span", "lf-spent", prefix),
      el("span", "lf-lit", target.code.slice(prefix.length)),
    );
  } else chip.textContent = target.code;
  return chip;
}

export function paintTargets() {
  if (!open) {
    if (selectionLayer.childElementCount) selectionLayer.replaceChildren();
    return;
  }
  const wasActive = hintActive >= 0;
  const refreshed = !searching && !prefix && !scrolling;
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
  if (!searching) {
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
  } else if (matches[active]) {
    const owner = matchOwner(matches[active]);
    const clip = owner ? shownRect(owner, clips()) : null;
    if (clip)
      for (const box of rangeOf(matches[active]).getClientRects()) {
        const rect = clippedRect(box, clip);
        if (!exposed(rect)) continue;
        const mark = el("span", "lf-target-match");
        mark.style.left = `${rect.left}px`;
        mark.style.top = `${rect.top}px`;
        mark.style.width = `${rect.width}px`;
        mark.style.height = `${rect.height}px`;
        drawn.push(mark);
      }
  }
  if (!refreshed && heard && !drawnTargets.has(heard)) hintActive = -1;
  // The key line was painted before geometry retired the browsed hint.
  if (wasActive && hintActive < 0) paintHere();
  selectionLayer.replaceChildren(...drawn);
  if (!searching)
    spreadHints(hints, {
      lineBox: keylineEl.getBoundingClientRect(),
      viewportTop: covered(),
    });
}

selectionInput.addEventListener("input", search);
addEventListener(
  "scroll",
  () => {
    if (!open) return;
    scrolling = true;
    paintHere();
  },
  { capture: true, passive: true },
);
addEventListener(
  "scrollend",
  () => {
    if (!open || !scrolling) return;
    scrolling = false;
    paintHere();
  },
  { capture: true, passive: true },
);
addEventListener("resize", () => {
  if (!open) return;
  scrolling = false;
  paintHere();
});

export const PAGE_SEARCH = {
  id: "page.search.open",
  keys: ["/"],
  does: "Search all the text on the page",
  line: "search page",
  // Once a target is in hand, its actions own the two short-line slots. Search stays
  // live to replace that target and remains in the complete reference.
  lineWhen: () => !hasCapturedTarget(),
  when: () => anchoringIsReady() && !searching,
  run: startSearching,
};

export const SELECT = {
  title: "Selecting an item",
  at: () => open,
  // The page owns search, even when item hints are standing over it. Exempt the
  // binding read from that row so one declaration drives both entry routes and every
  // keyboard projection. If character shortcuts are off, the row binds nothing and
  // this mode claims slash with the rest of the page keyboard.
  claims: (binding) =>
    allButTheReference(binding) && !bindings(PAGE_SEARCH).includes(binding),
  rows: [
    {
      id: "selection.hint.choose",
      keys: HINT_KEYS,
      label: "a–z",
      does: "Choose the item wearing that hint",
      line: "choose hint",
      when: () => !searching && candidates.length > 0,
      run: typeHint,
    },
    {
      id: "selection.hint.walk",
      keys: ["Tab", "Shift+Tab"],
      routes: [
        {
          id: "selection.hint.next",
          binding: "Tab",
          does: "Hear the next visible item",
        },
        {
          id: "selection.hint.previous",
          binding: "Shift+Tab",
          does: "Hear the previous visible item",
        },
      ],
      does: "Hear the next / previous visible item",
      line: "browse hints",
      repeat: true,
      when: () => !searching && candidates.length > 0,
      run: (binding) => moveHint(binding === "Tab" ? 1 : -1),
    },
    {
      id: "selection.hint.select",
      keys: ["Enter"],
      does: "Select the target just announced",
      line: "select target",
      when: () => !searching && hintActive >= 0,
      run: chooseHint,
    },
    {
      id: "selection.match.walk",
      keys: ["Tab", "Shift+Tab"],
      routes: [
        {
          id: "selection.match.next",
          binding: "Tab",
          does: "Go to the next search match",
        },
        {
          id: "selection.match.previous",
          binding: "Shift+Tab",
          does: "Go to the previous search match",
        },
      ],
      does: "Next / previous search match",
      line: "matches",
      repeat: true,
      when: () => searching && matches.length > 0,
      run: (binding) => moveMatch(binding === "Tab" ? 1 : -1),
    },
    {
      id: "selection.match.select",
      keys: ["Enter"],
      does: "Select the current search match",
      line: "select match",
      when: () => searching && matches.length > 0,
      run: chooseMatch,
    },
    {
      id: "selection.back",
      keys: ["Escape"],
      does: () =>
        searching
          ? searchReturnsToHints
            ? "Return to the visible item hints"
            : "Close page search"
          : prefix
            ? "Remove the last hint letter"
            : "Cancel item selection",
      line: () =>
        searching
          ? searchReturnsToHints
            ? "back to hints"
            : "close search"
          : prefix
            ? "back one letter"
            : "cancel",
      run: back,
    },
  ],
};

export const isSelecting = () => open;
export const startSelecting = () => setOpen(true);
export const stopSelecting = () => setOpen(false);
