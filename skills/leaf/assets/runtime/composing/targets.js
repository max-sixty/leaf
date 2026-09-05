/* This module owns keyboard item hints and whole-page text search. */
import { sameAnchor } from "../anchors.js";
import { bindings } from "../keyboard/bindings.js";

// Keyboard item selection and whole-page text search. `s` opens a viewport-local map of
// the same stable items and visual parts Alt-click reaches, then raises their general
// response actions; `/` opens the page's text search directly or from that map.

const HINT_KEYS = [..."asdfghjklqwertyuiopzxcvbnm"];
const HINT_INDENT = 10;

export function createTargetSelection({
  commentOnTarget,
  aimTargets,
  allButTheReference,
  anchoringIsReady,
  announce,
  banner,
  blockAt,
  contextAround,
  cut,
  el,
  findText,
  focused,
  hasCapturedTarget,
  inChrome,
  keyline,
  pageText,
  paintHere,
  quoteFrom,
  rangeOf,
  scrollToRange,
  selectionInput,
  selectionLayer,
  selectionSearch,
  selectionStatus,
  shownParts,
  shownRect,
  updateFab,
}) {
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
    const line = keyline.getBoundingClientRect();
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

  // Replacing a leaf in the alphabet with all of its children makes a prefix-free code.
  // Most pages therefore get one-letter hints; only the tail pays for a second letter.
  function hintCodes(count) {
    const codes = [...HINT_KEYS];
    while (codes.length < count) {
      const shortest = Math.min(...codes.map((code) => code.length));
      const at = codes.findLastIndex((code) => code.length === shortest);
      const parent = codes[at];
      codes.splice(at, 1, ...HINT_KEYS.map((key) => parent + key));
    }
    return codes.slice(0, count);
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
    commentOnTarget(target);
    announce(`Selected ${target.label}. Choose a response.`);
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
    announce(
      `Hint ${target.code}: ${cut(target.label, 0, 72)}. Press Enter to select.`,
    );
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

  const movedTo = (box, left, top) => ({
    left,
    right: left + box.width,
    top,
    bottom: top + box.height,
    width: box.width,
    height: box.height,
  });
  // Nested items can begin at exactly the same corner. Hints are the only route to their
  // targets, so keep every one and step later faces down (or up at the key line) until
  // each is legible. Read every face before moving one, keeping the pass to one layout.
  function spreadHints(hints) {
    const gap = 2;
    const measured = hints.map(({ chip, target }) => {
      const start = chip.getBoundingClientRect();
      const line = keyline.getBoundingClientRect();
      const lineBand = {
        left: line.left,
        top: line.top,
        right: line.right,
        bottom: innerHeight,
      };
      // Keep the established top-left/nesting placement unless it puts the face back
      // over a band already subtracted from its target. A surviving rectangle on the
      // line's right has a direct horizontal seat; a piece too narrow for the face is
      // moved above the band in the pass below.
      const rightSeat = Math.max(target.left, line.right);
      const canSitRight = rightSeat + start.width <= target.right;
      const left =
        line.height && overlaps(start, lineBand) && canSitRight
          ? rightSeat
          : start.left;
      return [chip, movedTo(start, left, start.top), start, lineBand];
    });
    const placed = [];
    for (const [chip, seated, start, lineBand] of measured) {
      let box = seated;
      for (
        let collisions = placed.filter((other) => overlaps(box, other));
        collisions.length;
        collisions = placed.filter((other) => overlaps(box, other))
      )
        box = movedTo(
          box,
          box.left,
          Math.max(...collisions.map((other) => other.bottom)) + gap,
        );
      const meetsLine = lineBand.bottom > lineBand.top && overlaps(box, lineBand);
      if (meetsLine || box.bottom > innerHeight) {
        const upperEdge = meetsLine ? lineBand.top : innerHeight;
        box = movedTo(box, box.left, upperEdge - gap - box.height);
        for (
          let collisions = placed.filter((other) => overlaps(box, other));
          collisions.length;
          collisions = placed.filter((other) => overlaps(box, other))
        )
          box = movedTo(
            box,
            box.left,
            Math.min(...collisions.map((other) => other.top)) - gap - box.height,
          );
      }
      const sideShift = box.left - start.left;
      const shift = box.top - start.top;
      if (sideShift) chip.style.left = `${parseFloat(chip.style.left) + sideShift}px`;
      if (shift) chip.style.top = `${parseFloat(chip.style.top) + shift}px`;
      placed.push(box);
    }
  }

  function paintTargets() {
    if (!open) {
      if (selectionLayer.childElementCount) selectionLayer.replaceChildren();
      return;
    }
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
    selectionLayer.replaceChildren(...drawn);
    if (!searching) spreadHints(hints);
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

  const PAGE_SEARCH = {
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

  const SELECT = {
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

  return {
    PAGE_SEARCH,
    SELECT,
    isSelecting: () => open,
    paintTargets,
    startSelecting: () => setOpen(true),
  };
}
