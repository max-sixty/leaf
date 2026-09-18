/* The Go-to sequence: `g` opens one prefix grammar, and this owner holds its vocabulary.

   Visible, visually discovered targets share one generated-letter namespace. Links,
   tabs, folds, the presses a widget built, and visible margin targets are read together
   in screen order and receive short prefix-free labels. `hints.js` owns that map — the
   codes, the typed prefix, the audible walk, the scroll freeze, the revalidation before
   activation, and the paint — and this owner declares what the scene holds, what a chip
   says, and what taking one does. The lowercase kind mnemonics are separate commands
   that filter the map: `g h` shows hyperlinks, `g f` folds, `g m` margin targets, `g t`
   Thread controls, and `g a` Ask controls. A filtered map keeps each member's code from
   the complete map, which is why codes are assigned here rather than by the session.

   Lowercase `g`, `j`, `k`, and `p` retain their structural meanings, while `a`, `f`, `h`,
   `m`, and `t` name filters; all nine are excluded from the generated alphabet. `g g` and
   `g G` glide to the page edges; from a focused thread, `g k` and `g j` place its card at
   an edge of the list; from a beside-panel, `g p` returns focus to the page while keeping
   the panel open. Uppercase mnemonics remain named
   global destinations: `g T` Threads, `g A` Asks, `g L` All leaves, `g M` the searchable
   Page Map, `g V` Versions, and `g D` the unsent draft the composer put away. A named
   panel destination toggles that panel, matching its visible control. Completing one that
   opens a surface exchanges the transient sequence for a return frame which restores the
   standing and auxiliary chrome state captured before `g` armed; completing it again closes the
   surface without adding a frame. These destinations remain available when an auxiliary surface
   covers the page: the sequence belongs to that modal surface while the inert document's
   ordinary scopes remain unavailable.

   `BUILTIN_DIRECT_DESTINATIONS` declares the uppercase destinations this owner implements;
   another owner contributes a complete row through `directDestinations`. `TARGET_KINDS`
   declares the members, label, exposure rule, and activation for each visible target
   family. `TARGET_FILTERS` declares semantic subsets of that complete map. Exact duplicate
   activation elements collapse to one candidate, while distinct overlapping actions remain
   distinct.

   Arming paints `data-lf-go-to-active` on the body and puts the same overlay hint shape on named
   banner destinations and visible page targets. Named destinations show the complete
   sequence and stay put through a scroll, since they stand on fixed chrome; the session
   takes them as its fixed chips and spreads the generated ones around them. Generated
   targets show only their suffix; the shortcut bar and reference retain that shared
   prefix. A moving page target cannot carry a readable opaque route, so the generated
   part of the map is withheld until the scene settles. Escape removes one typed letter,
   then a filter, then closes the sequence. A letter from the hint alphabet is consumed
   even when a scene refresh made it invalid, with explicit feedback instead of an
   unrelated page action; another unrelated key closes the sequence and is redispatched with
   its ordinary meaning.

   A press may deliberately leave layers standing while moving focus outside them. That is
   not an Escape rung, because it gives no layer back. The Go-to address states what
   remains open: beside the document, `g p` returns from the thread panel to the document
   and keeps both the panel and its narrowing. A panel covering the document cannot make
   that promise, so its ordinary Escape rung remains the route back.

   Keyboard destinations also capture the auxiliary chrome state they replace. `g T`, `g A`, and
   `g L` may exchange a standing panel or tray for another; their return frame restores
   that prior auxiliary surface and re-resolves its semantic row when reconciliation rebuilt it.
   `g M` uses the same frame for the Page Map dialog. `g V` contributes the
   version menu's own return frame to that destination vocabulary. Direct destinations
   therefore restore the standing their owner displaced rather than merely focusing the
   destination's banner control after closing it.

   The Go-to sequence has no timeout. The reader is not charged a time limit for reading
   the hints just painted. */
import { bindings, labelOf, live, spell, word } from "./bindings.js";
import { keyBadgePlacement } from "./key-badge-placement.js";
import { createHintSession, HINT_KEYS, hintCodes, renderKeys } from "./hints.js";
import {
  keySequenceModel,
  keySequenceTemplate,
  progressStates,
} from "./presentation.js";
import { html, nothing } from "../../vendor/browser-runtime.js";
import { isExternalPageLink, PAGE_PAINT_ATTRIBUTE } from "../presentation.js";
import { targetElement } from "../resolved-target.js";
import { focusDestination } from "../focus.js";
import { el, PRESSABLE } from "../widget-elements.js";
import { allButCommandReference } from "./register.js";
import { focusedThread } from "../conversation/focus.js";
import { letGo } from "../focus.js";
import { pageParts } from "../passages.js";
import { fragmentId, addressableSays, resolveAnchor } from "../anchor-resolution.js";
import { announce, notice } from "../notifications.js";
import {
  closestAcross,
  containsAcross,
  elementFromPointAcross,
  pageQueryAll,
} from "../passages.js";
import { inPanel as panelFocusIsInside } from "../conversation/panel-elements.js";
import { threadsBox } from "../conversation/panel-elements.js";
import {
  currentTray,
  askRows,
  asksOffered,
  asksPanel,
  asksBtn,
  othersBtn,
  othersPanel,
} from "../trays.js";
import { mapButton } from "../page-map-dialog.js";

import { claimsEsc, focused, saying } from "./scopes.js";
import { repaint } from "../repaint.js";

// The eye's copy of the go-to map. The layer is aria-hidden because the live region and
// Tab walk provide the same map without asking a screen reader to traverse paint chrome.
export const goToHintLayer = el("div", "lf-ui lf-go-to-hints");
goToHintLayer.setAttribute("aria-hidden", "true");

// Construct the command vocabulary once; boot mounts the viewport listeners after
// the chrome is attached. All travel and auxiliary-surface effects are explicit capabilities.
export function createGoToSequence({
  panelIsOpen,
  panelCovers,
  elements: { banner, toggleBtn },
  hintChrome,
  directDestinations,
  captureAuxiliaryChromeState,
  restoreAuxiliaryChromeState,
  setPanel,
  setOpenTray,
  scrollToElement,
  showThread,
  leavesOffered,
  othersLinks,
  activateMarginEntry,
  activeInlineThread,
  marginEntryKind,
  visibleMarginEntries,
  glideTo,
  placeThreadEdge,
  seenScroller,
  stopGlide,
  coveringAuxiliarySurface,
  enterPageMap,
  leavePageMap,
  pageMapIsActive,
}) {
  const inPanel = () => panelFocusIsInside(panelIsOpen);
  // How a destination in this sequence is written where the sequence itself is not on screen —
  // a notice naming the way back to a draft that has just gone down, say. Spelled off the
  // row's own binding, so a rebinding cannot leave a sentence promising the old press.
  const formatGoToAddress = (row) =>
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
  // The tabs rather than their panels: the visible choice is what wears the hint and
  // what the reader stands on afterwards. `role=tab` is the platform vocabulary, so an
  // authored tab pattern and lf-tabs take the same route without naming a widget family.
  const pageTabs = () => pageParts('[role="tab"]');
  // The summaries rather than the boxes they head: a summary is what the reader stands on,
  // what a chip sits beside, and the only part of a disclosure the platform gives a key to —
  // so a <details> whose author wrote no summary has no visible target here. Every
  // disclosure and not the shut ones, for the reason above: a list counting what is shut
  // means a different section the moment one of them opens.
  const pageDisclosures = () => pageParts("details > summary");
  // Narrower than the disclosure scope's own reading: this route can reveal a native
  // disclosure by its summary, while an aria-expanded group has no equivalent arrival.
  // The presses themselves, wherever a widget put them. Each is declared as it is built:
  // `offer` writes the native press's tag or input type and `selectableOffer` the role it
  // gave, which is the value the theme's hand already reads. A widget joins by building its
  // control rather than by an entry here. The register stays about capabilities; a press is
  // a route to one, and this is how a route that spends no key of its own is reached. The
  // reading stops where the hand stops, because it is the same reading.
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
      const name =
        link.getAttribute("aria-label")?.trim() || addressableSays(link) || "Link";
      announce(`Opened ${name} in a new tab`);
    }
  }

  // One-off direct travel is one vocabulary too. The mnemonic completes the trip or closes
  // the named panel already standing, and every destination owns the liveness, landing, and
  // close that make its surface useful rather than leaving the dispatcher to know which
  // furniture it enters.
  const BUILTIN_DIRECT_DESTINATIONS = [
    {
      id: "navigation.panel.threads",
      key: "Shift+t",
      does: () =>
        panelIsOpen() ? "Close the Threads panel" : "Go to the Threads panel",
      line: () => (panelIsOpen() ? "close Threads panel" : "Threads panel"),
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
      close: () => setPanel(false),
      // The arrival is the list, the panel's own floor, so what the reader then stands on
      // in the panel is theirs to let go of before this frame answers — unless the press
      // carried an inline thread into the panel and stood them on its card, which the
      // one Escape then gives back.
      standing: () => Boolean(activeInlineThread()),
      toggle: true,
    },
    {
      id: "navigation.tray.asks",
      key: "Shift+a",
      does: () =>
        currentTray() === "asks" ? "Close the Asks tray" : "Go to the Asks tray",
      line: () => (currentTray() === "asks" ? "close Asks tray" : "Asks tray"),
      control: () => asksBtn,
      when: (...args) => asksOffered(...args),
      go: () => {
        setOpenTray("asks");
        (askRows()[0] ?? asksPanel).focus({ preventScroll: true });
      },
      active: () => currentTray() === "asks",
      close: () => setOpenTray(null),
      toggle: true,
    },
    {
      id: "navigation.tray.leaves",
      key: "Shift+l",
      does: () =>
        currentTray() === "leaves" ? "Close the Leaves tray" : "Go to the Leaves tray",
      line: () => (currentTray() === "leaves" ? "close Leaves tray" : "Leaves tray"),
      control: () => othersBtn,
      when: (...args) => leavesOffered(...args),
      go: () => {
        setOpenTray("leaves");
        (othersLinks()[0] ?? othersPanel).focus({ preventScroll: true });
      },
      active: () => currentTray() === "leaves",
      close: () => setOpenTray(null),
      toggle: true,
    },
    {
      id: "navigation.page-map",
      key: "Shift+m",
      does: "Open the Page Map dialog",
      line: "Page Map dialog",
      control: () => mapButton,
      when: () => true,
      go: (...args) => enterPageMap(...args),
      active: pageMapIsActive,
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

  const MARGIN_TARGET_KIND = "Margin entry";
  const TARGET_KINDS = [
    {
      kind: MARGIN_TARGET_KIND,
      list: visibleMarginEntries,
      go: (...args) => activateMarginEntry(...args),
      exposure: "self",
    },
    {
      kind: "Tab",
      list: pageTabs,
      go: press,
    },
    // After Tab, because a tab a widget built answers both queries and the tab is the
    // nearer meaning. The collapse above keeps whichever kind is read first.
    {
      kind: "Control",
      list: pageControls,
      go: press,
    },
    {
      kind: "Link",
      list: pageLinks,
      // Use the platform click method so authored handlers, cancellation, fragments,
      // targets, and downloads keep their anchor semantics.
      go: followLink,
    },
    {
      kind: "Fold",
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
  const TARGET_FILTERS = [
    {
      id: "margin-entries",
      key: "m",
      word: "margin targets",
      matches: ({ kind }) => kind === MARGIN_TARGET_KIND,
    },
    {
      id: "threads",
      key: "t",
      word: "Thread controls",
      matches: ({ kind, member }) =>
        kind === MARGIN_TARGET_KIND && marginEntryKind(member) === "comment",
    },
    {
      id: "asks",
      key: "a",
      word: "Ask controls",
      matches: ({ kind, member }) =>
        kind === MARGIN_TARGET_KIND && marginEntryKind(member) === "ask",
    },
    {
      id: "hyperlinks",
      key: "h",
      word: "hyperlinks",
      matches: ({ kind }) => kind === "Link",
    },
    {
      id: "folds",
      key: "f",
      word: "folds",
      matches: ({ kind }) => kind === "Fold",
    },
  ];
  const THREAD_EDGE_KEYS = ["k", "j"];
  const PAGE_RETURN_KEYS = ["p"];
  const PAGE_EDGE_KEYS = ["g", "Shift+g"];
  const FILTER_KEYS = TARGET_FILTERS.map(({ key }) => key);
  const STRUCTURAL_KEYS = new Set(
    [
      ...THREAD_EDGE_KEYS,
      ...PAGE_RETURN_KEYS,
      ...PAGE_EDGE_KEYS,
      ...FILTER_KEYS,
    ].filter((key) => /^[a-z]$/.test(key)),
  );
  const GO_TO_HINT_KEYS = HINT_KEYS.filter((key) => !STRUCTURAL_KEYS.has(key));

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
  const nativeLabelWords = (member) =>
    [...(member.labels ?? [])].map(visibleWords).filter(Boolean).join(" ");

  function visibleCandidates(filter = null) {
    const placement = keyBadgePlacement();
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
        const rect = placement.badgeBox(member);
        if (!rect || !exposed(member, rect, entry.exposure)) continue;
        seen.add(member);
        const says =
          member.getAttribute("aria-label")?.trim() ||
          nativeLabelWords(member) ||
          addressableSays(member) ||
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
    const codes = hintCodes(found.length, GO_TO_HINT_KEYS);
    const coded = found.map((candidate, index) => ({
      ...candidate,
      code: codes[index],
    }));
    return filter ? coded.filter(filter.matches) : coded;
  }

  // Every complete route starts with the same stable prefix. A partial generated hint is
  // added to the live sequence so the shortcut bar and chips can paint how far it has advanced.
  const sequencePrefix = () => [labelOf(OPEN_GO_TO)].filter(Boolean);
  const sequenceKeys = () =>
    [...sequencePrefix(), targetFilter?.key, ...hints.prefix()].filter(Boolean);
  const hintRenderKey = renderKeys();
  const goToHintModel = (candidate, current) => {
    const steps = [...candidate.code];
    const marginEntryKey = candidate.member.dataset?.lfMarginEntryKey;
    const targetId =
      closestAcross(candidate.member, "[data-lf-margin-for]")?.dataset.lfMarginFor ||
      candidate.member.id ||
      candidate.member.dataset.lfMarginFor ||
      candidate.member.getAttribute("aria-controls");
    return Object.freeze({
      key: hintRenderKey(candidate.member),
      className: `lf-key-badge lf-key-hint lf-go-to-hint${current ? " lf-current" : ""}`,
      hintCode: candidate.code,
      kind: candidate.kind,
      marginEntryKey: marginEntryKey || null,
      targetId: targetId || null,
      commandId: null,
      address: null,
      sequence: keySequenceModel(steps, progressStates(steps, [...hints.prefix()])),
    });
  };

  const goToHintTemplate = (model) => html`
    <span
      class=${model.className}
      data-lf-hint-code=${model.hintCode ?? nothing}
      data-lf-go-to-kind=${model.kind ?? nothing}
      data-lf-go-to-margin-entry=${model.marginEntryKey ?? nothing}
      data-lf-go-to-target=${model.targetId ?? nothing}
      data-lf-go-to-command=${model.commandId ?? nothing}
      data-lf-go-to-address=${model.address ?? nothing}
      >${keySequenceTemplate(model.sequence)}</span
    >
  `;

  // Named destinations in the banner use the same detached chip and key sequence as page
  // targets. The shared placement pass centers the hint in the open space below and keeps
  // it clear of its control if the viewport forces it elsewhere. Controls folded into the
  // closed overflow menu have no visible place to label; their routes remain in the key
  // line and complete reference.
  const directDestinationHint = (row) => {
    const control = word(row.control);
    if (
      !control ||
      !banner.contains(control) ||
      !control.checkVisibility() ||
      !live(row) ||
      bindings(row).length === 0
    )
      return null;
    const box = control.getBoundingClientRect();
    if (!box.width || !box.height) return null;
    const steps = [...sequencePrefix(), labelOf(row)].filter(Boolean);
    const model = Object.freeze({
      key: hintRenderKey(row),
      className: "lf-key-badge lf-key-hint lf-go-to-hint",
      hintCode: null,
      kind: null,
      marginEntryKey: null,
      targetId: null,
      commandId: row.id,
      address: steps.join(" "),
      sequence: keySequenceModel(steps, progressStates(steps, sequenceKeys())),
    });
    return { model, target: box, belowTarget: true, left: box.left, top: box.top };
  };
  const directDestinationHints = () =>
    GO_TO_SCOPE.rows.map(directDestinationHint).filter(Boolean);
  // The armed window owns every key wherever focus sits. The shared hint session holds
  // the map, the typed prefix, the audible walk, and the scroll freeze; this owner holds
  // only which kind filter the reader has asked for.
  let goToActive = false;
  let targetFilter = null;

  // A generated label over an inline link must not become a span the passage walk then
  // has to understand, so the chips are chrome and the scene is read rather than marked.
  const hints = createHintSession({
    layer: goToHintLayer,
    walk: "go-to-target",
    read: () => visibleCandidates(targetFilter),
    identity: (candidate) => candidate.member,
    scene: keyBadgePlacement,
    layout: (candidates, { current, reading }) =>
      candidates.flatMap((candidate) => {
        const rect = reading.badgeBox(candidate.member);
        if (
          !candidate.member.checkVisibility() ||
          !rect ||
          !exposed(candidate.member, rect, candidate.exposure)
        )
          return [];
        return {
          candidate,
          model: goToHintModel(candidate, candidate === current),
          target: rect,
          belowTarget: false,
          left: rect.left,
          top: rect.top,
        };
      }),
    template: goToHintTemplate,
    take: (candidate) => {
      setGoToSequence(false);
      candidate.go(candidate.member);
    },
    words: {
      describe: (candidate) => `${candidate.kind}, ${candidate.says}`,
      take: "go there",
      all: "All go-to hints.",
    },
    chrome: hintChrome,
    extras: directDestinationHints,
  });

  function setGoToSequence(on) {
    // Armed over a control that has claimed Escape, one press would have two owners — the
    // control's rung and the sequence's cancel — so the sequence refuses to arm there at all.
    if (on && !goToActive && claimsEsc(focused())) return;
    if (on) stopGlide(seenScroller());
    goToActive = on;
    // The sequence itself reveals page navigation such as a roomy contents map. Publish that
    // state before taking the visible-scene reading so those routes enter the same map as
    // links that were already standing in the document.
    document.body.toggleAttribute(PAGE_PAINT_ATTRIBUTE.goto, on);
    targetFilter = null;
    if (!on) {
      hints.disarm();
      return repaint();
    }
    const found = hints.arm();
    // The chips are the eye's copy; the sequence itself is spoken, or the context change is silent
    // to exactly the reader who cannot see them.
    announce(
      `Go to — ${found.length ? `${found.length} visible targets; type a hint or press Tab to hear them. ` : "No visible targets. "}${saying(GO_TO_SCOPE.rows)}`,
    );
    repaint();
  }

  const targetCapability = () => TARGET_KINDS.some((entry) => entry.list().length > 0);
  const atGoToTargets = () => !targetFilter && !hints.prefix();

  function filterTargets(binding) {
    targetFilter = TARGET_FILTERS.find(({ key }) => key === binding);
    const found = hints.refresh();
    const message = found.length
      ? `${found.length} visible ${targetFilter.word}; type a hint or press Tab to hear them.`
      : `No visible ${targetFilter.word}.`;
    if (found.length) notice(message);
    else announce(message);
    repaint();
  }

  // An empty active filter is useful state, not a four-second event. The candidate map is
  // the reading the hint session already holds; using it here keeps the shortcut repaint
  // out of the expensive visibility and hit-test pass.
  function goToStatus() {
    if (!goToActive || !targetFilter || hints.candidates().length) return null;
    return `No visible ${targetFilter.word}.`;
  }

  // The sequence is one scope: generated visible targets, named global destinations, structural
  // placements, and its own way out. Structural and named rows stand only before a hint
  // prefix; once a generated route has begun, only valid continuations, audible browsing,
  // activation, and backing remain.
  let goRows = null;
  const GO_TO_SCOPE = {
    title: "Go to",
    escape: "inner",
    root: () => coveringAuxiliarySurface() ?? document,
    reach: "with g armed",
    sequence: sequenceKeys,
    sequencePrefix,
    liveInCommandReference: true,
    at: () => goToActive,
    claims: allButCommandReference,
    // Built on first use, after composition supplied the other owners' destination rows.
    get rows() {
      return (goRows ??= [
        {
          id: "navigation.thread.edge",
          // A focused thread is one place, so its two placements complete the sequence
          // without naming a list or taking a digit. This is the thread-local counterpart
          // to the page edges below: k/j place the card inside its panel rather than moving
          // the document to the passage the card is about. It leads while live because it
          // is the one offer specific to where the reader stands; list members wear their
          // Go-to hints directly when the sequence starts.
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
          when: () => atGoToTargets() && Boolean(focusedThread()),
          run: (binding) => {
            const thread = focusedThread();
            setGoToSequence(false);
            placeThreadEdge(thread, binding === "k" ? "start" : "end");
          },
        },
        {
          id: "navigation.page.return",
          // This is travel from the panel to the page, not an Escape rung: every layer
          // remains standing, so the Go-to address says what stays open. A covering panel locks
          // the document scroller and has no page to hand back; ordinary Escape remains
          // the truthful route there. It follows the focused thread's own placements so
          // they keep the short line a reader standing on that card arrived to use.
          keys: PAGE_RETURN_KEYS,
          does: "Return to the page, keeping the thread panel open",
          line: "page — threads kept",
          when: () => atGoToTargets() && inPanel() && !panelCovers(),
          run: () => {
            setGoToSequence(false);
            letGo();
          },
        },
        {
          id: "navigation.target",
          runFromCommandReference: false,
          // Every alphabet key is claimed while the map stands. If a scene refresh retired
          // a remembered route, that old letter must report the miss rather than falling
          // through to an unrelated page shortcut such as `d`.
          keys: () => (hints.prefix() ? HINT_KEYS : GO_TO_HINT_KEYS),
          label: "letters",
          sequenceSteps: () => [
            ...(targetFilter ? [targetFilter.key] : []),
            ...(hints.prefix() ? [...hints.prefix(), "…"] : ["letters"]),
          ],
          completeSequenceSteps: () => [
            ...(targetFilter ? [targetFilter.key] : []),
            "letters",
          ],
          does: "Type a visible target's hint",
          line: "visible target",
          // Once armed, keep the alphabet claimed even when a filter has no members. A key
          // then reports the miss inside this sequence rather than falling through to a page
          // command whose letter happened to match it.
          when: () => (goToActive ? true : targetCapability()),
          run: hints.type,
        },
        {
          id: "navigation.target.filter",
          keys: FILTER_KEYS,
          routes: TARGET_FILTERS.map(({ id, key, word }) => ({
            id: `navigation.target.filter.${id}`,
            binding: key,
            does: `Show only visible ${word}`,
          })),
          label: FILTER_KEYS.join(" / "),
          sequenceSteps: ["kind"],
          does: "Filter visible targets by kind",
          line: "filter by kind",
          when: () => atGoToTargets() && targetCapability(),
          run: filterTargets,
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
          when: () => (goToActive ? hints.candidates().length > 0 : targetCapability()),
          run: (binding) => hints.walk(binding === "Tab" ? 1 : -1),
        },
        {
          id: "navigation.target.choose",
          keys: ["Enter"],
          does: "Go to the target just announced",
          line: "go to target",
          when: hints.walking,
          run: hints.choose,
        },
        ...BUILTIN_DIRECT_DESTINATIONS.map((destination) => ({
          id: destination.id,
          keys: [destination.key],
          label: spell(destination.key),
          does: destination.does,
          line: destination.line,
          control: destination.control,
          when: () => atGoToTargets() && destination.when(),
          returnFrame: () => {
            const previousAuxiliaryChrome = captureAuxiliaryChromeState();
            return {
              active: destination.active,
              close: () => {
                destination.close?.();
                return restoreAuxiliaryChromeState(previousAuxiliaryChrome);
              },
              does: `Return from ${word(destination.line)}`,
              line: "back",
              // A direct destination lands on a floor or a chrome row — the list, a tray's
              // first row, a version — so what the reader then stands on is theirs to let
              // go of first, unless the destination says its arrival was a standing.
              standing: destination.standing?.() ?? false,
            };
          },
          run: () => {
            const closing = destination.toggle && destination.active();
            setGoToSequence(false);
            if (closing) destination.close();
            else destination.go();
          },
        })),
        // A destination whose control belongs to another runtime owner joins this one
        // vocabulary as its complete row. The Go-to hint layer contributes only the sequence's
        // progress and cancellation; liveness, words, landing, and return remain with the
        // owner that can keep them true.
        ...directDestinations().map((destination) => ({
          ...destination,
          when: () => atGoToTargets() && live(destination),
          run: (binding) => {
            setGoToSequence(false);
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
          when: atGoToTargets,
          run: (binding) => {
            setGoToSequence(false); // before the travel, so the arrival's own scrolling paints nothing
            const box = seenScroller();
            glideTo(box, binding === "g" ? 0 : box.scrollHeight);
          },
        },
        {
          id: "navigation.go-to.back",
          keys: ["Escape"],
          sequenceControl: true,
          does: () =>
            hints.prefix()
              ? "Remove the last hint letter"
              : targetFilter
                ? "Show all visible targets"
                : "Cancel the sequence",
          line: () =>
            hints.prefix()
              ? "back one letter"
              : targetFilter
                ? "all targets"
                : "cancel",
          run: () => {
            if (hints.backOneLetter()) return;
            if (targetFilter) {
              targetFilter = null;
              hints.invalidate();
              announce("All go-to targets.");
              return;
            }
            setGoToSequence(false);
            announce("Go to cancelled");
          },
        },
      ]);
    },
  };

  // The way in to the sequence. Its row supplies the same leader every painted Go-to hint uses,
  // so the letter the reader presses and the letter the page prints cannot diverge.
  //
  // The page-level row promises the sequence rather than any particular ephemeral hint.
  const OPEN_GO_TO = {
    id: "navigation.go-to.open",
    keys: ["g"],
    does: "Go to a visible target, panel, page, or edge",
    line: "go to",
    // No `when`: the window this press stands up always holds at least the page's edges.
    run: () => setGoToSequence(true),
  };

  const goToSequenceActive = () => goToActive;

  return {
    GO_TO_SCOPE,
    OPEN_GO_TO,
    goToStatus,
    formatGoToAddress,
    setGoToSequence,
    paintGoToHints: hints.paint,
    goToSequenceActive,
    mountGoToSequence: hints.mount,
  };
}
