/* The Go-to sequence: `g` opens one prefix grammar, and this owner holds its vocabulary.

   Visible, visually discovered targets share one generated-letter namespace. Links,
   tabs, folds, the presses a widget built, and visible margin targets are read together
   in screen order and receive short prefix-free labels. `hints.js` owns that map — the
   codes, the typed prefix, the audible walk, the scroll freeze, the revalidation before
   activation, and the paint — and this owner declares what the scene holds, what a chip
   says, and what taking one does. The lowercase kind mnemonics are separate commands
   that filter the map: `g h` shows hyperlinks, `g f` folds, `g m` margin targets, `g t`
   Thread controls. A filtered map keeps each member's code from
   the complete map, which is why codes are assigned here rather than by the session.

   Lowercase `g`, `j`, `k`, and `p` retain their structural meanings, while `f`, `h`, `m`,
   and `t` name filters; `i` resumes writing, `v` restores selection and `z` aligns the current item at the top; these are excluded from the generated alphabet. `g g` and
   `g G` glide to the page edges; from a focused thread, `g k` and `g j` place its card at
   an edge of the list; `g p` returns focus to the page while leaving open surfaces
   in place. Uppercase mnemonics remain named
   global destinations: `g T` Threads, `g M` On me, `g L` All pages, `g P` the
   searchable Page Map and `g V` Versions. `g T`, `g M` and `g L` open the floating
   panel's view of that name, and `g V` its Versions, through the panel's own doors
   (`doors`, floating-panel.js), as its marks and menu rows open them. Completing one that
   opens a surface leaves the user in that surface, whose own Escape step is the way out
   of it — the same step for a surface the user already had, and none of this sequence's
   to declare; completing the mnemonic again closes it.

   Named destinations contribute complete command rows. Each has an unbound semantic route for the
   command reference and a prefixed keyboard presentation; arming the sequence changes
   which keys reach it, not whether its capability exists. Another owner contributes a
   complete row through `directDestinations`. `TARGET_KINDS`
   declares the members, label, exposure rule, and activation for each visible target
   family. `TARGET_FILTERS` declares semantic subsets of that complete map. Exact duplicate
   activation elements collapse to one candidate, while distinct overlapping actions remain
   distinct.

   Arming paints `data-lf-go-to-active` on the body and puts an overlay hint on each
   visible page target. Generated targets show only their suffix; the reference retains
   that shared prefix. A moving page target cannot carry a readable opaque route, so the generated
   part of the map is withheld until the scene settles. Escape removes one typed letter,
   then a filter, then closes the sequence. A letter from the hint alphabet is consumed
   even when a scene refresh made it invalid, with explicit feedback instead of an
   unrelated page action; another unrelated key closes the sequence and is redispatched with
   its ordinary meaning.

   A press may deliberately leave layers standing while moving focus outside them. That is
   not an Escape rung, because it gives no layer back. The Go-to address states what
   remains open: `g p` returns to the document and keeps the panel's open view.

   A destination declares no way back. `g T`, `g M` and `g L` may exchange one of the
   panel's views for another, and the surface the user ends in owns the one step that
   takes it off again — the same step whichever door opened it, and the same for a
   surface they already had. Exchanging one for another is lateral, so the one replaced
   is not put back; the user reaches it the way they reached it the first time.

   The Go-to sequence has no timeout. The user is not charged a time limit for reading
   the hints just painted. */
import { bindings, commandRun, labelOf, live, nativePress } from "./bindings.js";
import { keyBadgePlacement } from "./key-badge-placement.js";
import { createHintSession, HINT_KEYS, codedHints, renderKeys } from "./hints.js";
import {
  keySequenceModel,
  keySequenceTemplate,
  progressSteps,
} from "./key-sequence.js";
import { html, nothing } from "/runtime/framework.js";
import { isExternalPageLink } from "../declared-words.js";
import { PAGE_PAINT_ATTRIBUTE } from "../page-paint.js";
import { el, PRESSABLE } from "../widget-elements.js";
import { allButCommandReference, pageCommand, pageScope } from "./register.js";
import { focusedThreadTarget } from "../thread/focus.js";
import { letGo, focusDestination, focused } from "../focus.js";
import { pageParts } from "../passages.js";
import { addressableSays } from "../addressable-names.js";
import { announce, notice } from "../notifications.js";
import { closestAcross, inPage, pageQueryAll } from "../passages.js";

import { claimsEsc, saying } from "./scopes.js";
import { repaint } from "../repaint.js";
import { pageScroller } from "../scrolling.js";

// The eye's copy of the go-to map. The layer is aria-hidden because the live region and
// Tab walk provide the same map without asking a screen reader to traverse paint chrome.
export const goToHintLayer = el("div", "lf-ui lf-key-chips lf-go-to-hints");
goToHintLayer.setAttribute("aria-hidden", "true");

// Construct the command vocabulary once; boot mounts the viewport listeners after
// the chrome is attached. All travel and auxiliary-surface effects are explicit capabilities.
/** @typedef {import("./bindings.js").Command} Command
 * @typedef {{kind: string, member: Element, go: () => unknown, exposure: "self" | "across"}} TargetMember
 * @typedef {{key: number, className: string, hintCode: string, kind: string, marginEntryKey: string | null,
 * targetId: string | null, commandId: null, address: null, sequence: ReturnType<typeof keySequenceModel>}} GoToHintModel
 * @typedef {{id: string, key: string, word: string, matches: (target: TargetMember) => boolean}} TargetFilter
 * @typedef {Object} GoToOptions
 * @property {Pick<ReturnType<typeof import("../floating-panel.js").createFloatingPanel>["doors"], "threads" | "queue" | "leaves">} doors
 * @property {{barriers: () => import("../rect.js").Box[]}} hintChrome
 * @property {() => unknown} openPageMap
 * @property {() => readonly Command[]} directDestinations
 * @property {ReturnType<typeof import("../anchor-travel.js").createAnchorTravel>["scrollToElement"]} scrollToElement
 * @property {() => boolean} leavesOffered
 * @property {{visibleMarginEntries: () => HTMLElement[], activateMarginEntry: (element: HTMLElement) => unknown, marginEntryKind: (element: Element) => string | null} | null} marginEntries
 * @property {typeof import("../navigation.js").glideTo} glideTo
 * @property {typeof import("../navigation.js").placeThreadEdge} placeThreadEdge
 * @property {typeof import("../navigation.js").stopGlide} stopGlide
 */
/** @param {GoToOptions} options */
export function createGoToSequence({
  doors,
  hintChrome,
  openPageMap,
  directDestinations,
  scrollToElement,
  leavesOffered,
  marginEntries,
  glideTo,
  placeThreadEdge,
  stopGlide,
}) {
  // How a destination in this sequence is written where the sequence itself is not on screen —
  // a notice naming the way back to a draft that has just gone down, say. Spelled off the
  // row's own binding, so a rebinding cannot leave a sentence promising the old press.
  /** @param {Command} row */
  const formatGoToAddress = (row) =>
    [...sequencePrefix(), labelOf(row)].filter(Boolean).join(" ");

  // ---------- the g sequence: visible page targets ----------
  // These queries declare which page actions join the generated namespace. A link belongs
  // to the authored body, including link apparatus a page widget generated: lf-toc's
  // map repeats heading words, but its visible anchors are still routes through this
  // page. Runtime surfaces remain named global destinations. Other platform targets use pageParts so an
  // injected control inside the document does not silently become a tab or fold route.
  /** @returns {HTMLAnchorElement[]} */
  const pageLinks = () => {
    /** @type {HTMLAnchorElement[]} */
    const links = pageQueryAll("a[href]");
    return links.filter(inPage);
  };
  // The tabs rather than their panels: the visible choice is what wears the hint and
  // what the user is on afterwards. `role=tab` is the platform vocabulary, so an
  // authored tab pattern and lf-tabs take the same route without naming a widget family.
  /** @returns {HTMLElement[]} */
  const pageTabs = () => pageParts('[role="tab"]');
  // The summaries rather than the boxes they head: a summary is what the user is on,
  // what a chip sits beside, and the only part of a disclosure the platform gives a key to —
  // so a <details> whose author wrote no summary has no visible target here. Every
  // disclosure and not the shut ones, for the reason above: a list counting what is shut
  // means a different section the moment one of them opens.
  /** @returns {HTMLElement[]} */
  const pageDisclosures = () => pageParts("details > summary");
  // Narrower than the disclosure scope's own reading: this route can reveal a native
  // disclosure by its summary, while an aria-expanded group has no equivalent arrival.
  // The presses themselves, wherever a widget put them. Each is declared as it is built:
  // `offer` writes the native press's tag or input type, or the tag of a custom host that
  // opted into its own press contract; `selectableOffer` writes the role it gave. Those are
  // the values the theme's hand already reads. A widget joins by building its control rather
  // than by an entry here. The register stays about capabilities; a press is
  // a route to one, and this is how a route that spends no key of its own is reached. The
  // reading stops where the hand stops, because it is the same reading.
  /** @returns {HTMLElement[]} */
  const pageControls = () => pageParts(PRESSABLE);

  // A link keeps the platform activation that its author wrote. Fragment travel owns
  // arrival for every activation route; the sequence only names an external new tab.
  // A cancelled click has replaced that navigation step with one of its own.
  /** @param {HTMLAnchorElement} link */
  function followLink(link) {
    const activation = { prevented: false };
    link.addEventListener(
      "click",
      (event) => (activation.prevented = event.defaultPrevented),
      {
        capture: true,
        once: true,
      },
    );
    link.click();
    if (activation.prevented) return;
    if (isExternalPageLink(link) && link.target === "_blank") {
      const name =
        link.getAttribute("aria-label")?.trim() || addressableSays(link) || "Link";
      announce(`Opened ${name} in a new tab`);
    }
  }

  // One-off direct travel is one vocabulary too. The mnemonic completes the navigation step or closes
  // the named panel already open, and every destination owns the liveness, landing, and
  // close that make its surface useful rather than leaving the dispatcher to know which
  // furniture it enters. Other owners' destinations rank ahead of the fixed doors, so a
  // narrow line keeps the step a notice just named, such as Resume writing.
  /** @type {Command[]} */
  const destinations = [
    ...directDestinations(),
    {
      id: "navigation.panel.threads",
      keys: ["Shift+t"],
      title: () => (doors.threads.shows() ? "close Threads" : "Threads"),
      run: () => doors.threads.press(),
      when: () => true,
    },
    {
      id: "navigation.panel.queue",
      keys: ["Shift+m"],
      // Its door is On me's, so where the On view shows the agent's list it turns to
      // the user's rather than closing.
      title: () => (doors.queue.shows() ? "close On me" : "On me"),
      run: () => doors.queue.press(),
      when: () => true,
    },
    {
      id: "navigation.panel.leaves",
      keys: ["Shift+l"],
      title: () => (doors.leaves.shows() ? "close All pages" : "All pages"),
      run: () => doors.leaves.press(),
      when: () => doors.leaves.shows() || leavesOffered(),
    },
    {
      id: "navigation.page-map",
      keys: ["Shift+p"],
      title: "Page Map dialog",
      run: () => openPageMap(),
      when: () => true,
    },
  ];
  // Whether each door's surface stands, by the door's id.
  const DOOR_STANDS = new Map([
    ["navigation.panel.threads", () => doors.threads.shows()],
    ["navigation.panel.queue", () => doors.queue.shows()],
    ["navigation.panel.leaves", () => doors.leaves.shows()],
  ]);
  // A press hint is an activation and an arrival. Reveal first so a nested control can open
  // the panel that holds it, then focus and use its click path so pointer and keyboard
  // remain one behavior.
  /** @param {HTMLElement} control */
  function press(control) {
    scrollToElement(control, undefined, "nearest");
    focusDestination(control, "press");
    nativePress(control)?.();
  }

  const MARGIN_TARGET_KIND = "Margin entry";
  /** Each declaration binds native activation to its actual selected element before
   * heterogeneous target families join the shared map.
   * @template {Element} E @param {string} kind @param {() => E[]} list
   * @param {(element: E) => unknown} go @param {"self" | "across"} [exposure] */
  const targetKind = (kind, list, go, exposure = "across") => ({
    list: () =>
      list().map((member) => ({ kind, member, go: () => go(member), exposure })),
  });
  const TARGET_KINDS = [
    ...(marginEntries
      ? [
          targetKind(
            MARGIN_TARGET_KIND,
            marginEntries.visibleMarginEntries,
            marginEntries.activateMarginEntry,
            "self",
          ),
        ]
      : []),
    targetKind("Tab", pageTabs, press),
    targetKind("Link", pageLinks, followLink),
    targetKind("Fold", pageDisclosures, (summary) => {
      scrollToElement(summary.parentElement, undefined, "nearest");
      focusDestination(summary, "move");
    }),
    targetKind("Control", pageControls, press),
  ];
  /** @type {TargetFilter[]} */
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
        kind === MARGIN_TARGET_KIND &&
        marginEntries?.marginEntryKind(member) === "comment",
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
      ...directDestinations().flatMap((row) => bindings(row)),
    ].filter((key) => /^[a-z]$/.test(key)),
  );
  const GO_TO_HINT_KEYS = HINT_KEYS.filter((key) => !STRUCTURAL_KEYS.has(key));

  /** @param {Element} member */
  const visibleWords = (member) =>
    member instanceof HTMLElement ? member.innerText.replace(/\s+/g, " ").trim() : "";
  /** @param {Element} member */
  const nativeLabelWords = (member) =>
    "labels" in member && member.labels instanceof NodeList
      ? [...member.labels]
          .filter((node) => node instanceof Element)
          .map(visibleWords)
          .filter(Boolean)
          .join(" ")
      : "";

  /** @param {TargetFilter | null} [filter] */
  function visibleCandidates(filter = null) {
    const placement = keyBadgePlacement();
    /** @type {Set<Element>} */
    const seen = new Set();
    const found = [];
    for (const [order, entry] of TARGET_KINDS.entries())
      for (const candidate of entry.list()) {
        const { member } = candidate;
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
        if (!rect || !placement.exposes(member, rect, candidate.exposure)) continue;
        seen.add(member);
        const says =
          member.getAttribute("aria-label")?.trim() ||
          nativeLabelWords(member) ||
          addressableSays(member) ||
          visibleWords(member) ||
          candidate.kind;
        found.push({ ...candidate, order, rect, says });
      }
    found.sort(
      (left, right) =>
        left.rect.top - right.rect.top ||
        left.rect.left - right.rect.left ||
        left.order - right.order,
    );
    const coded = codedHints(found, GO_TO_HINT_KEYS.join(""));
    return filter ? coded.filter(filter.matches) : coded;
  }

  // Every complete route starts with the same stable prefix. A partial generated hint is
  // added to the live sequence so the chips can paint how far it has advanced.
  const sequencePrefix = () => [labelOf(OPEN_GO_TO)].filter(Boolean);
  const sequenceKeys = () => [
    ...sequencePrefix(),
    ...(targetFilter ? [targetFilter.key] : []),
    ...hints.prefix(),
  ];
  const hintRenderKey = renderKeys();
  /** @param {ReturnType<typeof visibleCandidates>[number]} candidate @param {boolean} current @returns {GoToHintModel} */
  const goToHintModel = (candidate, current) => {
    const steps = [...candidate.code];
    const marginEntryKey = candidate.member.getAttribute("data-lf-margin-entry-key");
    const targetId =
      closestAcross(candidate.member, "[data-lf-margin-for]")?.getAttribute(
        "data-lf-margin-for",
      ) ||
      candidate.member.id ||
      candidate.member.getAttribute("data-lf-margin-for") ||
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
      sequence: keySequenceModel(progressSteps(steps, [...hints.prefix()])),
    });
  };

  /** @param {GoToHintModel} model */
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

  // The armed window owns every key wherever focus sits. The shared hint session holds
  // the map, the typed prefix, the audible walk, and the scroll freeze; this owner holds
  // only which kind filter the user has asked for.
  let goToActive = false;
  /** @type {TargetFilter | null} */
  let targetFilter = null;

  // A generated label over an inline link must not become a span the passage walk then
  // has to understand, so the chips are chrome and the scene is read rather than marked.
  /** @type {import("./hints.js").HintSessionOptions<ReturnType<typeof visibleCandidates>[number], ReturnType<typeof keyBadgePlacement>, GoToHintModel>} */
  const hintOptions = {
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
          !reading.exposes(candidate.member, rect, candidate.exposure)
        )
          return [];
        return {
          candidate,
          model: goToHintModel(candidate, candidate === current),
          target: rect,
          placement: "corner",
          left: rect.left,
          top: rect.top,
        };
      }),
    template: goToHintTemplate,
    take: (candidate) => {
      setGoToSequence(false);
      candidate.go();
    },
    words: {
      describe: (candidate) => `${candidate.kind}, ${candidate.says}`,
      take: "go there",
      all: "All go-to hints.",
    },
    chrome: hintChrome,
  };
  const hints = createHintSession(hintOptions);

  /** @param {boolean} on */
  function setGoToSequence(on) {
    // Armed over a control that has claimed Escape, one press would have two owners — the
    // control's rung and the sequence's cancel — so the sequence refuses to arm there at all.
    if (on && !goToActive && claimsEsc(focused())) return;
    if (on) stopGlide(pageScroller);
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
    // to exactly the user who cannot see them.
    announce(
      `Go to — ${found.length ? `${found.length} visible targets; type a hint or press Tab to hear them. ` : "No visible targets. "}${saying(GO_TO_SCOPE.rows)}`,
    );
    repaint();
  }

  const targetCapability = () => TARGET_KINDS.some((entry) => entry.list().length > 0);
  const atGoToTargets = () => !targetFilter && !hints.prefix();

  /** @param {string} binding */
  function filterTargets(binding) {
    const chosen = TARGET_FILTERS.find(({ key }) => key === binding);
    if (!chosen) return;
    targetFilter = chosen;
    const found = hints.refresh();
    const message = found.length
      ? `${found.length} visible ${chosen.word}; type a hint or press Tab to hear them.`
      : `No visible ${chosen.word}.`;
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
  /** @type {Command[] | null} */
  let goRows = null;
  /** @type {import("./bindings.js").Scope} */
  const GO_TO_SCOPE = {
    title: "Go to",
    escape: "inner",
    root: () => document,
    reach: "with g armed",
    sequence: sequenceKeys,
    sequencePrefix,
    liveInCommandReference: true,
    at: () => goToActive,
    claims: allButCommandReference,
    // Built on first use, after composition supplied the other owners' destination rows.
    // The door to a surface that stands leads them all: its press closes what the user
    // stands beside, and a line too narrow for every door keeps that one.
    get rows() {
      goRows ??= build();
      const open = goRows.filter((row) => DOOR_STANDS.get(row.id)?.());
      return open.length
        ? [...open, ...goRows.filter((row) => !open.includes(row))]
        : goRows;
    },
  };

  /** @returns {Command[]} */
  function build() {
    return [
      {
        id: "navigation.thread.edge",
        touch: false,
        // A focused thread is one place, so its two placements complete the sequence
        // without naming a list or taking a digit. This is the thread-local counterpart
        // to the page edges below: k/j place the card inside its panel rather than moving
        // the document to the passage the card is about. It leads while live, after
        // only the door to the open surface, because it is the one offer specific to
        // where the user is; list members wear their Go-to hints directly when the
        // sequence starts.
        keys: THREAD_EDGE_KEYS,
        routes: [
          {
            id: "navigation.thread.top",
            binding: "k",
            title: "Put the focused thread at the top of its list",
          },
          {
            id: "navigation.thread.bottom",
            binding: "j",
            title: "Put the focused thread at the bottom of its list",
          },
        ],
        title: "thread top / bottom",
        travels: true,
        when: () => atGoToTargets() && Boolean(focusedThreadTarget()),
        runKey: (binding) => {
          const thread = focusedThreadTarget();
          setGoToSequence(false);
          placeThreadEdge(thread, binding === "k" ? "start" : "end");
        },
      },
      {
        id: "navigation.page.focus",
        touch: false,
        // This changes focus without unwinding an open surface.
        keys: PAGE_RETURN_KEYS,
        title: "page",
        when: () => atGoToTargets(),
        run: () => {
          setGoToSequence(false);
          letGo();
        },
      },
      {
        id: "navigation.target",
        touch: false,
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
        title: "visible target",
        travels: true,
        // Once armed, keep the alphabet claimed even when a filter has no members. A key
        // then reports the miss inside this sequence rather than falling through to a page
        // command whose letter happened to match it.
        when: () => (goToActive ? true : targetCapability()),
        runKey: hints.type,
      },
      {
        id: "navigation.target.filter",
        touch: false,
        keys: FILTER_KEYS,
        routes: TARGET_FILTERS.map(({ id, key, word }) => ({
          id: `navigation.target.filter.${id}`,
          binding: key,
          title: `Show only visible ${word}`,
        })),
        label: FILTER_KEYS.join(" / "),
        sequenceSteps: ["kind"],
        title: "filter by kind",
        when: () => atGoToTargets() && targetCapability(),
        runKey: filterTargets,
      },
      ...hints.walkRows({
        id: "navigation.target",
        when: () => (goToActive ? hints.candidates().length > 0 : targetCapability()),
        choose: {
          title: "go to target",
        },
      }),
      // A destination whose control belongs to another runtime owner joins this one
      // vocabulary as its complete row. The Go-to hint layer contributes only the sequence's
      // progress and cancellation; liveness, words, landing, and return remain with the
      // owner that can keep them true.
      ...destinations.map(
        /** @returns {Command} */ (destination) => {
          const { run, runKey, ...metadata } = destination;
          return {
            ...metadata,
            // A direct destination's finger route is its permanent page command in
            // More. Arming this keyboard sequence doesn't seat another gesture control.
            touch: false,
            when: () => atGoToTargets() && live(destination),
            runKey: (binding) => {
              setGoToSequence(false);
              commandRun(destination, binding)?.();
            },
          };
        },
      ),
      {
        id: "navigation.page.edge",
        touch: false,
        keys: PAGE_EDGE_KEYS,
        routes: [
          {
            id: "navigation.page.top",
            binding: "g",
            title: "Go to the top of the page",
          },
          {
            id: "navigation.page.bottom",
            binding: "Shift+g",
            title: "Go to the bottom of the page",
          },
        ],
        title: "top / bottom",
        travels: true,
        when: atGoToTargets,
        runKey: (binding) => {
          setGoToSequence(false); // before the travel, so the arrival's own scrolling paints nothing
          const box = pageScroller;
          glideTo(box, binding === "g" ? 0 : box.scrollHeight);
        },
      },
      {
        id: "navigation.go-to.back",
        touch: false,
        keys: ["Escape"],
        sequenceControl: true,
        title: () =>
          hints.prefix() ? "back one letter" : targetFilter ? "all targets" : "cancel",
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
    ];
  }

  // The way in to the sequence. Its row supplies the same leader every painted Go-to hint uses,
  // so the letter the user presses and the letter the page prints cannot diverge.
  //
  // The page-level row promises the sequence rather than any particular ephemeral hint.
  /** @type {Command} */
  const OPEN_GO_TO = {
    id: "navigation.go-to.open",
    touch: false,
    keys: ["g"],
    description: "Show hints for targets, panels and page edges",
    title: "go to",
    // No `when`: the window this press stands up always holds at least the page's edges.
    run: () => setGoToSequence(true),
  };

  const goToSequenceActive = () => goToActive;

  pageScope("go to", GO_TO_SCOPE);
  pageCommand(OPEN_GO_TO);
  // Every named capability stays invocable by id outside the armed sequence. Native
  // control activation and generated touch controls remain separate from that route:
  // a run-less row delegates to its control without replacing its native default.
  for (const destination of destinations) {
    const registered = {
      ...destination,
      keys: [],
      touch: destination.touch ?? false,
    };
    // Invocation is a live capability. Spreading a destination would freeze an
    // unavailable getter at registration, before its owner can offer the action.
    for (const name of ["run", "runKey"]) {
      const handler = Object.getOwnPropertyDescriptor(destination, name);
      if (handler) Object.defineProperty(registered, name, handler);
    }
    pageCommand(registered);
  }

  return {
    goToStatus,
    formatGoToAddress,
    setGoToSequence,
    paintGoToHints: hints.paint,
    goToSequenceActive,
    mountGoToSequence: hints.mount,
  };
}
