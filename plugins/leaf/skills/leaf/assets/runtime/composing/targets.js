// Keyboard passage selection. `s` opens a viewport-local map of the smallest text blocks
// a reader can see; `/` replaces that map with ordinary whole-page find. Both routes end
// by making a native Selection (or raising an atomic item), so comment capture has one input
// no matter whether the passage came from a pointer, caret browsing, a hint, or search.

const HINT_KEYS = [..."asdfghjklqwertyuiopzxcvbnm"];
const MIN_SEARCH = 3;

export function createTargetSelection({
  allButTheReference,
  anchoringIsReady,
  announce,
  banner,
  blockAt,
  containsAcross,
  contextAround,
  cut,
  el,
  findText,
  focused,
  inChrome,
  isItem,
  itemSelector,
  itemSays,
  itemWord,
  keyline,
  pageQueryAll,
  pageText,
  paintHere,
  quoteFrom,
  raiseOnItem,
  rangeOf,
  scrollToRange,
  selectionInput,
  selectionLayer,
  selectionSearch,
  selectionStatus,
  shownRect,
  textBlockSelector,
  textNodesUnder,
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
  // so geometry alone would put a key on the comment panel for a card hidden behind it.
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
    const text = [];
    for (const block of pageQueryAll(textBlockSelector())) {
      if (inChrome(block)) continue;
      const segments = textNodesUnder(block).filter(
        (segment) => blockAt(segment.node) === block,
      );
      const quote = quoteFrom(segments);
      if ([...quote].length < MIN_SEARCH) continue;
      const range = rangeOf(segments);
      const rect = firstShown(range, block, cache);
      if (rect) text.push({ kind: "text", block, quote, range, rect });
    }

    // A text-bearing widget is reached through the blocks inside it. Items without one —
    // an image, chart, or other atomic visual — remain literal targets of their own. Keep
    // only the innermost visible atomic item so a widget and its empty wrapper never wear
    // two hints for the same press.
    const items = pageQueryAll(itemSelector())
      .filter((item) => isItem(item) && !inChrome(item))
      .filter((item) => !text.some(({ block }) => containsAcross(item, block)))
      .map((item) => ({ item, rect: shownRect(item, cache) }))
      .filter(({ rect }) => exposed(rect));
    const atomic = items
      .filter(
        ({ item }) =>
          !items.some(
            ({ item: other }) => other !== item && containsAcross(item, other),
          ),
      )
      .map(({ item, rect }) => ({
        kind: "item",
        item,
        quote: (() => {
          const name =
            itemSays(item) ||
            item.getAttribute("aria-label") ||
            item.querySelector("[aria-label]")?.getAttribute("aria-label");
          return [itemWord(item), name].filter(Boolean).join(": ");
        })(),
        rect,
      }));

    const targets = [...text, ...atomic].sort(
      (a, b) => a.rect.top - b.rect.top || a.rect.left - b.rect.left,
    );
    const codes = hintCodes(targets.length);
    return targets.map((target, index) => ({
      ...target,
      code: codes[index],
    }));
  }

  function setOpen(on, restore = false) {
    if (on && !anchoringIsReady()) return;
    if (on) opener = focused();
    const returnTo = !on && restore ? opener : null;
    open = on;
    searching = false;
    prefix = "";
    matches = [];
    active = -1;
    hintActive = -1;
    selectionInput.value = "";
    selectionSearch.hidden = true;
    if (on) {
      candidates = visibleTargets();
      if (!candidates.length) {
        announce(
          "There is no visible passage to select. Press slash to search the page.",
        );
      } else {
        announce(
          `Select a passage — type one of ${candidates.length} hints, press Tab to hear them, or slash to search the page.`,
        );
      }
    } else {
      candidates = [];
      selectionLayer.replaceChildren();
      opener = null;
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
      announce("Select a passage — type a hint, or slash to search the page.");
    }
    paintHere();
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

  function chooseText(range, quote, kind) {
    setOpen(false);
    document.body.focus({ preventScroll: true });
    const selection = getSelection();
    selection.removeAllRanges();
    selection.addRange(range);
    updateFab();
    announce(`Selected ${kind}: ${cut(quote, 0, 72)}. Press c to comment.`);
  }

  function choose(target) {
    if (target.kind === "item") {
      setOpen(false);
      document.body.focus({ preventScroll: true });
      const { left, right, top, bottom } =
        shownRect(target.item, clips()) ?? target.rect;
      raiseOnItem(target.item, {
        left: (left + right) / 2,
        top: (top + bottom) / 2,
      });
      announce(`Selected ${target.quote}. Press c to comment.`);
    } else chooseText(target.range, target.quote, "passage");
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
    } else announce(`${left.length} passages remain.`);
    paintHere();
  }

  const hinted = () => candidates.filter(({ code }) => code.startsWith(prefix));

  function moveHint(direction) {
    const targets = hinted();
    if (!targets.length) return;
    hintActive = (hintActive + direction + targets.length) % targets.length;
    const target = targets[hintActive];
    announce(
      `Hint ${target.code}: ${cut(target.quote, 0, 72)}. Press Enter to select.`,
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
    chooseText(range, quoteFrom(matches[active]), "match");
  }

  function back() {
    if (searching) return setSearching(false);
    if (prefix) {
      prefix = prefix.slice(0, -1);
      hintActive = -1;
      announce(prefix ? `Hint ${prefix}.` : "All passage hints.");
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
              target.kind === heard.kind &&
              (target.block ?? target.item) === (heard.block ?? heard.item) &&
              target.code === heard.code,
          )
        : -1;
      hintActive = still;
    }
    const drawn = [];
    if (!searching) {
      const cache = clips();
      for (const target of candidates) {
        if (!target.code.startsWith(prefix)) continue;
        const rect = refreshed
          ? target.rect
          : target.kind === "text"
            ? firstShown(target.range, target.block, cache)
            : shownRect(target.item, cache);
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

  const SELECT = {
    title: "Selecting a passage",
    at: () => open,
    claims: allButTheReference,
    rows: [
      {
        id: "selection.hint.choose",
        keys: HINT_KEYS,
        label: "a–z",
        does: "Choose the passage wearing that hint",
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
            does: "Hear the next visible target",
          },
          {
            id: "selection.hint.previous",
            binding: "Shift+Tab",
            does: "Hear the previous visible target",
          },
        ],
        does: "Hear the next / previous visible target",
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
        id: "selection.search.open",
        keys: ["/"],
        does: "Search all the text on the page",
        line: "search page",
        when: () => !searching,
        run: () => setSearching(true),
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
            ? "Return to the visible passage hints"
            : prefix
              ? "Remove the last hint letter"
              : "Cancel passage selection",
        line: () =>
          searching ? "back to hints" : prefix ? "back one letter" : "cancel",
        run: back,
      },
    ],
  };

  return {
    SELECT,
    isSelecting: () => open,
    paintTargets,
    startSelecting: () => setOpen(true),
  };
}
