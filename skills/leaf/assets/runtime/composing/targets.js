import { sameAnchor } from "../anchors.js";
import { bindings } from "../keyboard/bindings.js";

// Keyboard item aim and whole-page text search. `s` opens a viewport-local map of the
// same stable items and visual parts Alt-click reaches; `/` opens the page's text search
// directly or from that map.

const HINT_KEYS = [..."asdfghjklqwertyuiopzxcvbnm"];
const MIN_SEARCH = 3;

export function createTargetSelection({
  activateAimTarget,
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

  const clips = () => new Map();
  const covered = () => banner.getBoundingClientRect().bottom;
  const bottomCovered = () => keyline.getBoundingClientRect().top;
  const visible = (box) =>
    box &&
    (box.width ?? box.right - box.left) > 0 &&
    (box.height ?? box.bottom - box.top) > 0 &&
    box.right > 0 &&
    box.left < innerWidth &&
    box.bottom > covered() &&
    box.top < bottomCovered();
  // A fixed sheet can cover a page box without clipping it. Hints live above the chrome,
  // so geometry alone would put a key on the thread panel for a card hidden behind it.
  // Ask the rendered stack at the hint's corner; pointer-events:none keeps an existing
  // hint from answering this question itself.
  const exposed = (box) => {
    if (!visible(box)) return false;
    const x = Math.max(0, Math.min(innerWidth - 1, box.left + 1));
    const y = Math.max(covered(), Math.min(innerHeight - 1, box.top + 1));
    return !inChrome(document.elementFromPoint(x, y));
  };

  function clippedRect(box, clip) {
    if (!box || !clip) return null;
    const left = Math.max(box.left, clip.left, 0);
    const top = Math.max(box.top, clip.top, covered());
    const right = Math.min(box.right, clip.right, innerWidth);
    const bottom = Math.min(box.bottom, clip.bottom, bottomCovered());
    return right > left && bottom > top
      ? {
          left,
          top,
          right,
          bottom,
          width: right - left,
          height: bottom - top,
          clippedTop: box.top < top,
        }
      : null;
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

  function visibleTargets() {
    const cache = clips();
    const targets = aimTargets()
      .filter(({ element }) => !inChrome(element))
      .map((target) => ({ ...target, rect: shownRect(target.element, cache) }))
      .filter(({ rect }) => exposed(rect))
      .sort((a, b) => a.rect.top - b.rect.top || a.rect.left - b.rect.left);
    const codes = hintCodes(targets.length);
    return targets.map((target, index) => ({
      ...target,
      code: codes[index],
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
      selectionStatus.textContent = `Type ${MIN_SEARCH} or more characters`;
      announce(`Search the page. Type ${MIN_SEARCH} or more characters.`);
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

  function nearestMatch(found) {
    const middle = covered() + (bottomCovered() - covered()) / 2;
    let best = 0;
    let distance = Infinity;
    for (const [index, segments] of found.entries()) {
      const rect = rangeOf(segments).getBoundingClientRect();
      const next = Math.abs(rect.top - middle);
      if (next < distance) {
        best = index;
        distance = next;
      }
    }
    return best;
  }

  function syncStatus() {
    if ([...selectionInput.value.trim()].length < MIN_SEARCH)
      selectionStatus.textContent = `Type ${MIN_SEARCH} or more characters`;
    else if (!matches.length) selectionStatus.textContent = "No matches";
    else selectionStatus.textContent = `${active + 1} of ${matches.length}`;
  }

  function search() {
    const query = selectionInput.value.trim();
    matches = [...query].length < MIN_SEARCH ? [] : findText(pageText(), query);
    active = matches.length ? nearestMatch(matches) : -1;
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
    activateAimTarget(target);
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

  const overlaps = (a, b) =>
    a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
  const movedBy = (box, top) => ({
    left: box.left,
    right: box.right,
    top,
    bottom: top + box.height,
    width: box.width,
    height: box.height,
  });
  // Nested items can begin at exactly the same corner. Hints are the only route to their
  // targets, so keep every one and step later faces down (or up at the key line) until
  // each is legible. Read every face before moving one, keeping the pass to one layout.
  function spreadHints(chips) {
    const gap = 2;
    const measured = chips.map((chip) => [chip, chip.getBoundingClientRect()]);
    const placed = [];
    for (const [chip, start] of measured) {
      let box = start;
      for (
        let collisions = placed.filter((other) => overlaps(box, other));
        collisions.length;
        collisions = placed.filter((other) => overlaps(box, other))
      )
        box = movedBy(box, Math.max(...collisions.map((other) => other.bottom)) + gap);
      if (box.bottom > bottomCovered()) {
        box = start;
        for (
          let collisions = placed.filter((other) => overlaps(box, other));
          collisions.length;
          collisions = placed.filter((other) => overlaps(box, other))
        )
          box = movedBy(
            box,
            Math.min(...collisions.map((other) => other.top)) - gap - box.height,
          );
      }
      const shift = box.top - start.top;
      if (shift) chip.style.top = `${parseFloat(chip.style.top) + shift}px`;
      placed.push(box);
    }
  }

  function paintTargets() {
    if (!open) {
      if (selectionLayer.childElementCount) selectionLayer.replaceChildren();
      return;
    }
    const refreshed = !searching && !prefix;
    if (refreshed) {
      const heard = hinted()[hintActive];
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
    if (!searching) {
      const cache = clips();
      for (const target of candidates) {
        if (!target.code.startsWith(prefix)) continue;
        const rect = refreshed ? target.rect : shownRect(target.element, cache);
        if (!exposed(rect)) continue;
        const chip = hintChip(target);
        chip.style.left = `${Math.max(10, rect.left)}px`;
        chip.style.top = `${Math.min(bottomCovered() - 10, Math.max(covered(), rect.top))}px`;
        if (rect.clippedTop || rect.top < covered()) chip.classList.add("lf-in");
        drawn.push(chip);
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
    selectionLayer.replaceChildren(...drawn);
    if (!searching) spreadHints(drawn);
  }

  selectionInput.addEventListener("input", search);
  addEventListener(
    "scroll",
    () => {
      if (!open) return;
      paintHere();
    },
    { capture: true, passive: true },
  );
  addEventListener("resize", () => open && paintHere());

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
