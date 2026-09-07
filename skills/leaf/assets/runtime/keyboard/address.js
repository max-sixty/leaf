/* The go-to sequence: `g` opens one destination mode, and this owner holds its vocabulary.

   Visible, visually discovered targets share one generated-letter namespace. Links,
   tabs, folds, the presses a widget built, and visible margin elements are read together
   in screen order and receive short prefix-free labels. Most cost one letter; only the
   tail branches when the scene contains more targets than the available alphabet. The
   lowercase kind mnemonics filter that map: `g h` shows hyperlinks,
   `g t` tabs, `g f` folds, `g m` margin elements, and `g a` actions. A filtered map gets
   its own shorter codes. The mapping is local to the
   visible scene: scrolling refreshes it once motion settles, while a partly typed label
   freezes it until the reader completes or backs out of that prefix. Routine repaints do
   not regenerate a standing map. A candidate is revalidated before activation, so a
   target that left the scene cannot be worked by a stale label. Tab and Shift-Tab announce
   the current candidates and Enter activates the last one announced, because the painted
   labels themselves are visual chrome.

   Lowercase `g`, `j`, `k`, and `p` retain their structural meanings, while `a`, `f`, `h`,
   `m`, and `t` name filters; all nine are excluded from the generated alphabet. `g g` and
   `g G` glide to the page edges; from a focused thread, `g k` and `g j` place its card at
   an edge of the list; from a beside-panel, `g p` returns focus to the page while keeping
   the panel open. Uppercase mnemonics remain named
   global destinations: `g T` Threads, `g A` Asks, `g L` All leaves, `g M` the searchable
   Page map, `g V` Versions, and `g D` the unsent draft the composer put away. Completing
   one exchanges the transient sequence for a return
   frame which restores the standing and workspace captured before `g` armed.

   `BUILTIN_DIRECT_DESTINATIONS` declares the uppercase destinations this owner implements;
   another owner contributes a complete row through `directDestinations`. `TARGET_KINDS`
   declares the semantic members, label, exposure rule, and activation for each visible
   target family. Exact duplicate activation elements collapse to one candidate, while
   distinct overlapping actions remain distinct.

   Arming paints `data-lf-goto` on the body and one compact route over every candidate.
   The route shows only the generated suffix; the shortcut bar and reference retain the
   complete sequence and therefore own its context.
   Generated hints are opaque routes, so none may be dropped for a collision; the shared
   hint placement pass spreads them around the shortcut bar and one another. Escape removes
   one typed letter, then a filter, then closes the mode. A letter from the hint alphabet is consumed
   even when a scene refresh made it invalid, with explicit feedback instead of an
   unrelated page action; another unrelated key closes the mode and is redispatched with
   its ordinary meaning.

   A press may deliberately leave layers standing while moving focus outside them. That is
   not an Escape rung, because it gives no layer back. The address sequence states what
   remains open: beside the document, `g p` returns from the thread panel to the document
   and keeps both the panel and its narrowing. A panel covering the document cannot make
   that promise, so its ordinary Escape rung remains the route back.

   Keyboard destinations also capture the workspace they replace. `g T`, `g A`, and
   `g L` may exchange a standing panel or tray for another; their return frame restores
   that prior workspace and re-resolves its semantic row when reconciliation rebuilt it.
   `g M` uses the same frame for the complete Page-map sheet. `g V` contributes the
   version menu's own return frame to that destination vocabulary. Direct destinations
   therefore restore the standing their owner displaced rather than merely focusing the
   destination's banner control after closing it.

   The address mode has no timeout. The reader is not charged a time limit for reading
   the hints just painted. */
import { labelOf, live, spell } from "./bindings.js";
import { addressPlacement } from "./address-placement.js";
import { HINT_KEYS, hintCodes, spreadHints } from "./hints.js";
import { shortcutBarEl } from "./shortcut-bar.js";
import { keySequence, progressStates } from "./presentation.js";
import { banner, toggleBtn } from "../banner.js";
import { isExternalPageLink, PAGE_PAINT_ATTRIBUTE } from "../presentation.js";
import { targetElement } from "../resolved-target.js";
import { focusDestination, PRESSABLE } from "../widget-elements.js";
import { el } from "../widget-elements.js";
import { CHOOSER } from "../version.js";
import { KEPT_DRAFT } from "../composing/selection.js";
import {
  allButTheReference,
  focusedThread,
  letGo,
  pageParts,
  restoreWorkspace,
  workspaceState,
} from "./page.js";
import { fragmentId, itemSays, resolveAnchor, scrollToElement } from "../anchors.js";
import { announce } from "../notifications.js";
import {
  closestAcross,
  containsAcross,
  elementFromPointAcross,
  pageQueryAll,
} from "../passages.js";
import { inPanel, panelCovers, panelIsOpen, setPanel } from "../chrome-layout.js";
import { threadsBox } from "../conversation/panel.js";
import {
  currentTray,
  askRows,
  asksOffered,
  asksPanel,
  asksBtn,
  othersBtn,
  othersPanel,
  showTray,
} from "../trays.js";
import { leavesOffered, othersLinks } from "../live-leaves.js";
import {
  enterPageMap,
  activeInlineThread,
  leavePageMap,
  openPageMapMarginElement,
  pageMapIsActive,
  pageMapMarginElements,
  mapButton,
} from "../living-margin.js";
import { showThread } from "../conversation/landing.js";

import { claimsEsc, focused, paintHere, saying } from "./scopes.js";
import { glideTo, placeThreadEdge, seenScroller, stopGlide } from "../navigation.js";

// The eye's copy of the go-to map. The layer is aria-hidden because the live region and
// Tab walk provide the same map without asking a screen reader to traverse paint chrome.
export const addressLayer = el("div", "lf-ui lf-targets lf-goto-targets");
addressLayer.setAttribute("aria-hidden", "true");

// Asked when the sequence is built: CHOOSER is version.js's and KEPT_DRAFT the selection
// composer's, both modules in the cycle.
const directDestinations = () => [CHOOSER, KEPT_DRAFT];

// How a destination in this sequence is written where the sequence itself is not on screen —
// a notice naming the way back to a draft that has just gone down, say. Spelled off the
// row's own binding, so a rebinding cannot leave a sentence promising the old press.
export const goAddress = (row) =>
  [...sequencePrefix(), labelOf(row)].filter(Boolean).join(" ");

// ---------- the g sequence: visible page targets ----------
// These queries declare which page actions join the generated namespace. A link belongs
// to the page when it is inside main, including link apparatus a page widget generated:
// lf-toc's roomy map is chrome so passage capture ignores its repeated heading words, but
// its visible anchors are still routes through this page. Chrome-owned panels sit outside
// main and remain named global destinations. Other platform targets use pageParts so an
// injected control inside the document does not silently become a tab or fold route.
const pageLinks = () =>
  pageQueryAll("a[href]").filter((link) => closestAcross(link, "main"));
// The tabs rather than their panels: the visible choice is what wears the address and
// what the reader stands on afterwards. `role=tab` is the platform vocabulary, so an
// authored tab pattern and lf-tabs take the same route without naming a widget family.
const pageTabs = () => pageParts('[role="tab"]');
// The summaries rather than the boxes they head: a summary is what the reader stands on,
// what a chip sits beside, and the only part of a disclosure the platform gives a key to —
// so a <details> whose author wrote no summary has nothing here to address. Every
// disclosure and not the shut ones, for the reason above: a list counting what is shut
// means a different section the moment one of them opens.
const pageDisclosures = () => pageParts("details > summary");
// Narrower than the disclosure scope's own reading: this route can reveal a native
// disclosure by its summary, while an aria-expanded group has no equivalent arrival.
// The presses themselves, wherever a widget put them. Each is declared as it is built:
// `offer` writes the tag for a button and `selectableOffer` the role it gave, which is the
// value the theme's hand already reads, so a widget joins by building its control rather
// than by an entry here. The register stays about capabilities; a press is a route to one,
// and this is how a route that spends no key of its own is reached.
//
// The reading stops where the hand stops, because it is the same reading. `offer` writes
// the empty string for every tag but `button`, so a press built as another native control
// is outside both — the diff's soft-wrap box is `offer("input")` given `type = "checkbox"`
// afterwards, and it spends `Alt+w` for want of the route this cannot give it.
//
// TODO(2026-09-06): the value names the tag rather than pressability, which an `input`
// carries in its `type` and sets after `offer` returns. Widening it moves the hand, the
// copy, and the render gate together, so it is its own change rather than a clause here.
const pageControls = () => pageParts(PRESSABLE);

// A link keeps the platform activation that its author wrote. The sequence adds only the
// arrival it otherwise lacks: a local fragment hands focus to the place the browser just
// revealed, while an external link names the new tab that Leaf opens. A cancelled click
// does neither, because its handler has replaced the link's trip with one of its own.
function fragmentSection(link) {
  try {
    const url = new URL(link.getAttribute("href"), document.baseURI);
    if (!url.hash) return null;
    const here = new URL(location.href);
    if (
      url.origin !== here.origin ||
      url.pathname !== here.pathname ||
      url.search !== here.search
    )
      return null;
    return fragmentId(url.hash);
  } catch {
    return null;
  }
}

// A generated native-fragment sentinel can carry the scroll coordinate while remaining
// absent from the accessibility tree. Such a point sits immediately before the content it
// names. Never put keyboard focus on aria-hidden apparatus; after the browser follows the
// fragment, place the reader on that visible content instead.
function fragmentFocusTarget(destination) {
  if (!destination || destination.getAttribute("aria-hidden") !== "true")
    return destination;
  const content = destination.nextElementSibling;
  return content?.checkVisibility() && !closestAcross(content, '[aria-hidden="true"]')
    ? content
    : null;
}

function followLink(link) {
  const section = fragmentSection(link);
  let activation = null;
  link.addEventListener("click", (event) => (activation = event), {
    capture: true,
    once: true,
  });
  link.click();
  if (!activation || activation.defaultPrevented) return;
  const destination = fragmentFocusTarget(
    section && targetElement(resolveAnchor({ section })),
  );
  if (destination) return focusDestination(destination);
  if (isExternalPageLink(link) && link.target === "_blank") {
    const name = link.getAttribute("aria-label")?.trim() || itemSays(link) || "Link";
    announce(`Opened ${name} in a new tab`);
  }
}

// One-off direct travel is one vocabulary too. The mnemonic completes the trip, and
// every destination owns the liveness and landing that make its surface useful rather
// than leaving the dispatcher to know which furniture it enters.
const BUILTIN_DIRECT_DESTINATIONS = [
  {
    id: "navigation.panel.threads",
    key: "Shift+t",
    does: "Go to the Threads panel",
    line: "Threads panel",
    control: () => toggleBtn,
    when: () => true,
    go: () => {
      const inline = activeInlineThread();
      if (inline) showThread(inline.dataset.thread, { focus: "thread" });
      else {
        setPanel(true);
        threadsBox.focus({ preventScroll: true });
      }
    },
    active: (...args) => panelIsOpen(...args),
  },
  {
    id: "navigation.panel.asks",
    key: "Shift+a",
    does: "Go to the Asks panel",
    line: "Asks panel",
    control: () => asksBtn,
    when: (...args) => asksOffered(...args),
    go: () => {
      showTray("asks");
      (askRows()[0] ?? asksPanel).focus({ preventScroll: true });
    },
    active: () => currentTray() === "asks",
  },
  {
    id: "navigation.panel.leaves",
    key: "Shift+l",
    does: "Go to the All leaves panel",
    line: "All leaves panel",
    control: () => othersBtn,
    when: (...args) => leavesOffered(...args),
    go: () => {
      showTray("leaves");
      (othersLinks()[0] ?? othersPanel).focus({ preventScroll: true });
    },
    active: () => currentTray() === "leaves",
  },
  {
    id: "navigation.page-map",
    key: "Shift+m",
    does: "Go to the Page map",
    line: "Page map",
    control: () => mapButton,
    when: () => true,
    go: (...args) => enterPageMap(...args),
    active: (...args) => pageMapIsActive(...args),
    close: (...args) => leavePageMap(...args),
  },
];
// A press hint is an activation and an arrival. Reveal first so a nested control can open
// the panel that holds it, then focus and use its click path so pointer and keyboard
// remain one behavior.
function press(control) {
  scrollToElement(control, undefined, "nearest");
  control.focus({ preventScroll: true });
  control.click();
}

const TARGET_KINDS = [
  {
    kind: "Margin control or status indicator",
    filterKey: "m",
    filterWord: "margin controls and status indicators",
    list: pageMapMarginElements,
    go: (...args) => openPageMapMarginElement(...args),
    exposure: "self",
  },
  {
    kind: "Tab",
    filterKey: "t",
    filterWord: "tabs",
    list: pageTabs,
    go: press,
  },
  // After Tab, because a tab a widget built answers both queries and the tab is the
  // nearer meaning. The collapse above keeps whichever kind is read first.
  {
    kind: "Control",
    filterKey: "a",
    filterWord: "actions",
    list: pageControls,
    go: press,
  },
  {
    kind: "Link",
    filterKey: "h",
    filterWord: "hyperlinks",
    list: pageLinks,
    // Use the platform click method so authored handlers, cancellation, fragments,
    // targets, and downloads keep their anchor semantics.
    go: followLink,
  },
  {
    kind: "Fold",
    filterKey: "f",
    filterWord: "folds",
    list: pageDisclosures,
    // Opening is the arrival. Scroll the disclosure rather than its summary so a section
    // taller than the viewport starts at its start, then leave focus on the summary for
    // the platform's own close route.
    go: (summary) => {
      scrollToElement(summary.parentElement, undefined, "nearest");
      summary.focus({ preventScroll: true });
    },
  },
];
const THREAD_EDGE_KEYS = ["k", "j"];
const PAGE_RETURN_KEYS = ["p"];
const PAGE_EDGE_KEYS = ["g", "Shift+g"];
const FILTER_KEYS = TARGET_KINDS.map(({ filterKey }) => filterKey);
const STRUCTURAL_KEYS = new Set(
  [...THREAD_EDGE_KEYS, ...PAGE_RETURN_KEYS, ...PAGE_EDGE_KEYS, ...FILTER_KEYS].filter(
    (key) => /^[a-z]$/.test(key),
  ),
);
const ADDRESS_KEYS = HINT_KEYS.filter((key) => !STRUCTURAL_KEYS.has(key));
const TARGET_KEYS = [...FILTER_KEYS, ...ADDRESS_KEYS];

const pointIn = (box) => ({
  x: Math.max(0, Math.min(innerWidth - 1, (box.left + box.right) / 2)),
  y: Math.max(0, Math.min(innerHeight - 1, (box.top + box.bottom) / 2)),
});

function exposed(member, box, exposure) {
  const point = pointIn(box);
  const onTop = elementFromPointAcross(point.x, point.y);
  return exposure === "self" ? member.contains(onTop) : containsAcross(member, onTop);
}

const visibleWords = (member) => member.innerText?.replace(/\s+/g, " ").trim();

function visibleCandidates(filter = null) {
  const placement = addressPlacement();
  const seen = new Set();
  const found = [];
  for (const [order, entry] of TARGET_KINDS.entries())
    for (const member of entry.list()) {
      // A role=tab anchor is one activation surface, not a tab and a link. TARGET_KINDS
      // orders the more specific meaning first; genuinely different nested elements stay.
      const unavailable =
        seen.has(member) ||
        !member.isConnected ||
        !member.checkVisibility() ||
        member.matches(":disabled") ||
        member.getAttribute("aria-disabled") === "true" ||
        closestAcross(member, "[inert]");
      if (unavailable) continue;
      const rect = placement.visibleBox(member);
      if (!rect || !exposed(member, rect, entry.exposure)) continue;
      seen.add(member);
      const says =
        member.getAttribute("aria-label")?.trim() ||
        itemSays(member) ||
        visibleWords(member) ||
        entry.kind;
      found.push({ ...entry, order, member, rect, says });
    }
  found.sort(
    (left, right) =>
      left.rect.top - right.rect.top ||
      left.rect.left - right.rect.left ||
      left.order - right.order,
  );
  const filtered = filter ? found.filter(({ kind }) => kind === filter.kind) : found;
  const codes = hintCodes(filtered.length, ADDRESS_KEYS);
  return filtered.map((candidate, index) => ({ ...candidate, code: codes[index] }));
}

// Every complete route starts with the same stable prefix. A partial generated hint is
// added to the live sequence so the shortcut bar and chips can paint how far it has advanced.
const sequencePrefix = () => [labelOf(GOTO)].filter(Boolean);
const sequenceKeys = () =>
  [...sequencePrefix(), targetFilter?.filterKey, ...prefix].filter(Boolean);
const addressChip = (candidate) => {
  const steps = [...candidate.code];
  const chip = el("span", "lf-address lf-target-hint lf-sequence-address");
  chip.dataset.lfAddress = candidate.code;
  chip.dataset.lfAddressKind = candidate.kind;
  const source = candidate.member.lfForwardedControl ?? candidate.member;
  const marginElementKey = source.dataset?.lfMarginElementKey;
  if (marginElementKey) chip.dataset.lfAddressMarginElement = marginElementKey;
  const targetId =
    closestAcross(candidate.member, "[data-lf-margin-for]")?.dataset.lfMarginFor ||
    candidate.member.id ||
    candidate.member.dataset.lfMarginFor ||
    candidate.member.getAttribute("aria-controls");
  if (targetId) chip.dataset.lfAddressFor = targetId;
  chip.append(keySequence(steps, progressStates(steps, prefix.length)));
  return chip;
};

// The armed window owns every key wherever focus sits. Generated candidates stay stable
// through ordinary repaints, refresh after viewport motion settles, and freeze after the
// first hint letter.
let sequenceActive = false;
let targetFilter = null;
let prefix = "";
let candidates = [];
let hintActive = -1;
let scrolling = false;
let scrollTimer = 0;
let refreshCandidates = false;

export function setSequence(on) {
  // Armed over a control that has claimed Escape, one press would have two owners — the
  // control's rung and the sequence's cancel — so the sequence refuses to arm there at all.
  if (on && !sequenceActive && claimsEsc(focused())) return;
  if (on) stopGlide(seenScroller());
  sequenceActive = on;
  // The mode itself reveals page navigation such as a roomy contents map. Publish that
  // state before taking the visible-scene reading so those routes enter the same map as
  // links that were already standing in the document.
  document.body.toggleAttribute(PAGE_PAINT_ATTRIBUTE.goto, on);
  targetFilter = null;
  prefix = "";
  candidates = on ? visibleCandidates() : [];
  hintActive = -1;
  scrolling = false;
  refreshCandidates = false;
  clearTimeout(scrollTimer);
  // The chips are the eye's copy; the window itself is spoken, or the mode change is silent
  // to exactly the reader who cannot see them.
  if (on)
    announce(
      `Go to — ${candidates.length ? `${candidates.length} visible targets; type a hint or press Tab to hear them. ` : "No visible targets. "}${saying(GO.rows)}`,
    );
  paintHere();
}

const hinted = () => candidates.filter(({ code }) => code.startsWith(prefix));
const targetCapability = () => TARGET_KINDS.some((entry) => entry.list().length > 0);
const atTargetMenu = () => !targetFilter && !prefix;

function candidateIsCurrent(candidate) {
  return visibleCandidates(targetFilter).some(
    (current) => current.member === candidate.member && current.kind === candidate.kind,
  );
}

function filterTargets(binding) {
  targetFilter = TARGET_KINDS.find(({ filterKey }) => filterKey === binding);
  prefix = "";
  candidates = visibleCandidates(targetFilter);
  hintActive = -1;
  announce(
    candidates.length
      ? `${candidates.length} visible ${targetFilter.filterWord}; type a hint or press Tab to hear them.`
      : `No visible ${targetFilter.filterWord}.`,
  );
  paintHere();
}

function activateCandidate(candidate) {
  if (!candidate || !candidateIsCurrent(candidate)) {
    prefix = "";
    candidates = visibleCandidates(targetFilter);
    hintActive = -1;
    announce("That target is no longer visible. The hints are reset.");
    return paintHere();
  }
  setSequence(false);
  candidate.go(candidate.member);
}

function typeHint(key) {
  const next = prefix + key;
  if (!candidates.some(({ code }) => code.startsWith(next))) {
    announce(`No hint ${next}. The current hints are unchanged.`);
    return;
  }
  prefix = next;
  hintActive = -1;
  const target = hinted().find(({ code }) => code === prefix);
  if (target) return activateCandidate(target);
  announce(`${hinted().length} targets remain.`);
  paintHere();
}

function refineOrType(key) {
  if (!targetFilter && FILTER_KEYS.includes(key)) return filterTargets(key);
  typeHint(key);
}

function moveHint(direction) {
  const targets = hinted();
  if (!targets.length) return;
  hintActive = (hintActive + direction + targets.length) % targets.length;
  const target = targets[hintActive];
  const stop = /[.!?]$/.test(target.says) ? "" : ".";
  announce(
    `Hint ${target.code}: ${target.kind}, ${target.says}${stop} Press Enter to go there.`,
  );
  paintHere();
}

const chooseHint = () => activateCandidate(hinted()[hintActive]);

// The layer is chrome rather than authored markup: a generated label over an inline link
// must not become a span the passage walk then has to understand. Candidates are measured
// together, attached once, and then spread without dropping any opaque route.
export function paintAddresses() {
  if (!sequenceActive) {
    addressLayer.replaceChildren();
    return;
  }
  // A moving target cannot carry a readable opaque route. Suppress the visual map until
  // the scene settles, then regenerate it once; the alphabet remains claimed meanwhile,
  // so a remembered stale letter still cannot fall through to another page command.
  if (scrolling) {
    addressLayer.replaceChildren();
    return;
  }
  const wasActive = hintActive >= 0;
  const heard = hinted()[hintActive];
  // A scroll keeps one map until it settles. Reconciliation is different: every old
  // candidate is detached at once, so holding that map would paint nothing indefinitely
  // if the replacement's scroll restoration does not produce a final scrollend.
  const detached = candidates.some(({ member }) => !member.isConnected);
  const refreshed =
    !prefix && !scrolling && (refreshCandidates || detached || !candidates.length);
  if (refreshed) {
    candidates = visibleCandidates(targetFilter);
    hintActive = heard
      ? candidates.findIndex(
          (candidate) =>
            candidate.member === heard.member && candidate.code === heard.code,
        )
      : -1;
    refreshCandidates = false;
  }
  const activeCandidate = hinted()[hintActive];
  const placement = addressPlacement();
  const chips = [];
  const placed = [];
  const drawn = new Set();
  for (const candidate of hinted()) {
    const r = placement.visibleBox(candidate.member);
    if (
      !candidate.member.checkVisibility() ||
      !r ||
      !exposed(candidate.member, r, candidate.exposure)
    )
      continue;
    const chip = addressChip(candidate);
    if (activeCandidate === candidate) chip.classList.add("lf-current");
    chip.style.left = `${r.left}px`;
    chip.style.top = `${r.top}px`;
    chips.push(chip);
    placed.push({ chip, target: r });
    drawn.add(candidate);
  }
  if (wasActive && activeCandidate && !drawn.has(activeCandidate)) hintActive = -1;
  addressLayer.replaceChildren(...chips);
  spreadHints(placed, {
    lineBox: shortcutBarEl.getBoundingClientRect(),
    viewportTop: banner.getBoundingClientRect().bottom,
  });
  if (wasActive && hintActive < 0) paintHere();
}
// A page that moves under an armed window makes opaque labels temporarily untrustworthy,
// so the scroll pass hides them and remaps once the scene settles. Capture, because the
// panel's list and a board's own overflow scroll in boxes of their own and a scroll event
// does not bubble.
//
// Only while the sequence is armed, which is why this is a listener of its own rather than a
// line in the page's own repaint door (pageShifted): what the line says about the sequence
// holds at every scroll position, no list's membership moving with the page, so the door
// that repaints on every scroll of every page would be repainting for nobody. Armed, the
// paint is the whole of paintHere — the ring and the line are cheap beside the chips, and
// one door is what stops the chips having a repaint set of their own to keep in step.
addEventListener(
  "scroll",
  () => {
    if (!sequenceActive) return;
    scrolling = true;
    refreshCandidates = true;
    clearTimeout(scrollTimer);
    scrollTimer = setTimeout(() => {
      if (!sequenceActive || !scrolling) return;
      scrolling = false;
      paintHere();
    }, 80);
    paintHere();
  },
  { capture: true, passive: true },
);
addEventListener(
  "scrollend",
  () => {
    if (!sequenceActive || !scrolling) return;
    clearTimeout(scrollTimer);
    scrolling = false;
    paintHere();
  },
  { capture: true, passive: true },
);
addEventListener("resize", () => {
  if (!sequenceActive) return;
  clearTimeout(scrollTimer);
  scrolling = false;
  refreshCandidates = true;
  paintHere();
});

// The sequence is one scope: generated visible targets, named global destinations, structural
// placements, and its own way out. Structural and named rows stand only before a hint
// prefix; once a generated route has begun, only valid continuations, audible browsing,
// activation, and backing remain.
let goRows = null;
export const GO = {
  title: "Go to",
  reach: "with g armed",
  sequence: sequenceKeys,
  sequencePrefix,
  liveInReference: true,
  at: () => sequenceActive,
  claims: allButTheReference,
  // Built on first use: the version chooser's row is version.js's, a module in the cycle,
  // so it is read once every module has evaluated.
  get rows() {
    return (goRows ??= [
      {
        id: "navigation.thread.edge",
        // A focused thread is one place, so its two placements complete the sequence
        // without naming a list or taking a digit. This is the thread-local counterpart
        // to the page edges below: k/j place the card inside its panel rather than moving
        // the document to the passage the card is about. It leads while live because it
        // is the one offer specific to where the reader stands; list members wear their
        // address chips directly when the sequence arms.
        keys: THREAD_EDGE_KEYS,
        routes: [
          {
            id: "navigation.thread.top",
            binding: "k",
            does: "Put the focused thread at the top of its list",
          },
          {
            id: "navigation.thread.bottom",
            binding: "j",
            does: "Put the focused thread at the bottom of its list",
          },
        ],
        does: "Put the focused thread at the top / bottom of its list",
        line: "thread top / bottom",
        when: () => atTargetMenu() && Boolean(focusedThread()),
        run: (binding) => {
          const thread = focusedThread();
          setSequence(false);
          placeThreadEdge(thread, binding === "k" ? "start" : "end");
        },
      },
      {
        id: "navigation.page.return",
        // This is travel from the panel to the page, not an Escape rung: every layer
        // remains standing, so the address says what stays open. A covering panel locks
        // the document scroller and has no page to hand back; ordinary Escape remains
        // the truthful route there. It follows the focused thread's own placements so
        // they keep the short line a reader standing on that card arrived to use.
        keys: PAGE_RETURN_KEYS,
        does: "Return to the page, keeping the thread panel open",
        line: "page — threads kept",
        when: () => atTargetMenu() && inPanel() && !panelCovers(),
        run: () => {
          setSequence(false);
          letGo();
        },
      },
      {
        id: "navigation.target",
        runFromReference: false,
        // Every alphabet key is claimed while the map stands. If a scene refresh retired
        // a remembered route, that old letter must report the miss rather than falling
        // through to an unrelated page shortcut such as `d`.
        keys: () => (targetFilter ? ADDRESS_KEYS : TARGET_KEYS),
        label: () => (targetFilter ? "letters" : `letters / ${FILTER_KEYS.join(" ")}`),
        sequenceSteps: () => [
          ...(targetFilter ? [targetFilter.filterKey] : []),
          ...(prefix
            ? [...prefix, "…"]
            : [targetFilter ? "letters" : "letters / kind"]),
        ],
        completeSequenceSteps: () => [
          ...(targetFilter ? [targetFilter.filterKey] : []),
          targetFilter ? "letters" : sequenceActive ? "letters / kind" : "letters",
        ],
        does: () =>
          targetFilter
            ? "Type a visible target's hint"
            : "Type a visible target's hint, or filter first: m margin controls and status indicators, t tabs, a actions, h hyperlinks, f folds",
        line: () => (targetFilter ? "visible target" : "visible target / filter"),
        when: () => (sequenceActive ? candidates.length > 0 : targetCapability()),
        run: refineOrType,
      },
      {
        id: "navigation.target.walk",
        keys: ["Tab", "Shift+Tab"],
        routes: [
          {
            id: "navigation.target.next",
            binding: "Tab",
            does: "Hear the next visible target",
          },
          {
            id: "navigation.target.previous",
            binding: "Shift+Tab",
            does: "Hear the previous visible target",
          },
        ],
        does: "Hear the next / previous visible target",
        line: "browse hints",
        repeat: true,
        when: () => (sequenceActive ? candidates.length > 0 : targetCapability()),
        run: (binding) => moveHint(binding === "Tab" ? 1 : -1),
      },
      {
        id: "navigation.target.choose",
        keys: ["Enter"],
        does: "Go to the target just announced",
        line: "go to target",
        when: () => hintActive >= 0,
        run: chooseHint,
      },
      ...BUILTIN_DIRECT_DESTINATIONS.map((destination) => ({
        id: destination.id,
        keys: [destination.key],
        label: spell(destination.key),
        does: destination.does,
        line: destination.line,
        control: destination.control,
        when: () => atTargetMenu() && destination.when(),
        returnFrame: () => {
          const workspace = workspaceState();
          return {
            active: destination.active,
            close: () => {
              destination.close?.();
              return restoreWorkspace(workspace);
            },
            does: `Return from ${destination.line}`,
            line: "back",
          };
        },
        run: () => {
          setSequence(false);
          destination.go();
        },
      })),
      // A destination whose control belongs to another runtime owner joins this one
      // vocabulary as its complete row. The address layer contributes only the sequence's
      // progress and cancellation; liveness, words, landing, and return remain with the
      // owner that can keep them true.
      ...directDestinations().map((destination) => ({
        ...destination,
        when: () => atTargetMenu() && live(destination),
        run: (binding) => {
          setSequence(false);
          destination.run(binding);
        },
      })),
      {
        id: "navigation.page.edge",
        keys: PAGE_EDGE_KEYS,
        routes: [
          {
            id: "navigation.page.top",
            binding: "g",
            does: "Go to the top of the page",
          },
          {
            id: "navigation.page.bottom",
            binding: "Shift+g",
            does: "Go to the bottom of the page",
          },
        ],
        does: "Go to the top / bottom of the page",
        line: "top / bottom",
        when: atTargetMenu,
        run: (binding) => {
          setSequence(false); // before the travel, so the arrival's own scrolling paints nothing
          const box = seenScroller();
          glideTo(box, binding === "g" ? 0 : box.scrollHeight);
        },
      },
      {
        id: "navigation.address.back",
        keys: ["Escape"],
        sequenceControl: true,
        does: () =>
          prefix
            ? "Remove the last hint letter"
            : targetFilter
              ? "Show all visible targets"
              : "Cancel the sequence",
        line: () =>
          prefix ? "back one letter" : targetFilter ? "all targets" : "cancel",
        run: () => {
          if (prefix) {
            prefix = prefix.slice(0, -1);
            hintActive = -1;
            announce(prefix ? `Hint ${prefix}.` : "All go-to hints.");
            return paintHere();
          }
          if (targetFilter) {
            targetFilter = null;
            candidates = visibleCandidates();
            hintActive = -1;
            announce("All go-to targets.");
            return paintHere();
          }
          setSequence(false);
          announce("Go to cancelled");
        },
      },
    ]);
  },
};

// The way in to the sequence. Its row supplies the same leader every painted address uses,
// so the letter the reader presses and the letter the page prints cannot diverge.
//
// The page-level row promises the mode rather than any particular ephemeral hint.
export const GOTO = {
  id: "navigation.address.open",
  keys: ["g"],
  does: "Go to a visible target, panel, page, or edge",
  line: "go to",
  // No `when`: the window this press stands up always holds at least the page's edges.
  run: () => setSequence(true),
};

export const isSequenceActive = () => sequenceActive;
