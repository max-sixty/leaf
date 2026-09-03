import { labelOf, spell } from "./bindings.js";
import { createAddressPlacement, MAX_NUMBERED_ADDRESSES } from "./address-placement.js";
import { keySequence, progressStates } from "./presentation.js";
import { isExternalPageLink, PAGE_PAINT_ATTRIBUTE } from "../presentation.js";
import { focusDestination } from "../widget-elements.js";

export function createAddress({
  EVERYTHING,
  addressLayer,
  announce,
  decisionRows,
  decisionsPanel,
  decisionsOffered,
  banner,
  claimsEsc,
  el,
  enterPageMap,
  leavePageMap,
  focused,
  focusedThread,
  fragmentId,
  glideTo,
  inPanel,
  itemSays,
  keylineEl,
  leavesOffered,
  letGo,
  openPageMapItem,
  othersLinks,
  othersPanel,
  pageMapItems,
  pageParts,
  paintHere,
  panelCovers,
  panelIsOpen,
  pageMapIsActive,
  placeThreadEdge,
  resolveAnchor,
  saying,
  seenScroller,
  setPanel,
  showTray,
  currentTray,
  workspaceState,
  restoreWorkspace,
  startsAt,
  scrollToElement,
  threadsBox,
}) {
  // ---------- the g chord: the page's destinations ----------
  // g names one-off travel. An uppercase mnemonic completes a direct destination (`g T`
  // Threads, `g A` Asks, `g L` All leaves, `g M` Page map), while a lowercase list
  // mnemonic takes a following digit (`g m 2` presses the first Button at the second
  // Page-map location, `g t 2` selects the second tab, `g h 3` follows the third hyperlink,
  // and `g f 2` opens the second fold).
  // Repeated movement through threads and asks belongs to their single-key category walks,
  // t/T and a/A, so those categories do not also carry numbered addresses.
  //
  // Which numbered lists there are is this table and nothing else. The complete Page map
  // remains a direct destination because this one-digit list stops at nine. The chord's scope, the chips, the
  // line's words and the reference are all readings of it, so a fourth list is an entry here
  // rather than an edit to four consumers, and nothing that reads the table asks which list
  // it is holding. An entry says its letter, the word every surface calls the list by, the
  // sentence the reference reads, its members in address order, and how to arrive at one.
  // What the document holds, in reading order, as against what the chrome holds: the banner,
  // the versions and the panels are direct destinations, while a comment's message is the
  // Threads panel's rather than the page's. The addresses read the document through here, where
  // a scope naming a platform key reads `pageQueryAll` and crosses the declared shadow roots
  // as well: an address is a place in a list the reader counts down the page, and a tree a
  // module built has no place in that count, while what the reader can stand on is wherever
  // the markup ended up — a diff stages a <details> per file in a root they tab straight
  // into.
  //
  // Tabs, links, and folds use addresses as durable identities: a link the reader learnt
  // as `g h 2` must not change when the page scrolls. Page-map addresses answer a spatial
  // question instead. A location already in front of the reader is the useful numeric
  // window, while its complete, searchable identity lives in the Page map sheet. That
  // window stays fixed during a scroll and is read again only when scrolling settles.
  //
  // Above the table rather than beside the other readings below it, because an entry
  // holds the function itself and the array literal reads it as the module evaluates.
  const pageLinks = () => pageParts("a[href]");
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
  // Narrower than the disclosure scope's own reading on purpose, and in both directions: an
  // address is a place in a list the reader counts down the authored page, so it stops at the
  // document where the scope crosses declared roots, and it counts the platform's spelling
  // where the scope also answers ARIA's. So a settled option group takes the arrows and takes
  // no digit, and `g f` can say three where four things fold. Widening it is not free —
  // `go` scrolls the box and leans on `reveal`, which cannot open a group from its row — and
  // the count a reader wants under `g` is of the sections the author wrote.

  // A link keeps the platform activation that its author wrote. The chord adds only the
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
  function followLink(link) {
    const section = fragmentSection(link);
    let activation = null;
    link.addEventListener("click", (event) => (activation = event), {
      capture: true,
      once: true,
    });
    link.click();
    if (!activation || activation.defaultPrevented) return;
    const destination = section && resolveAnchor({ section })?.element;
    if (destination) return focusDestination(destination);
    if (isExternalPageLink(link) && link.target === "_blank") {
      const name = link.getAttribute("aria-label")?.trim() || itemSays(link) || "Link";
      announce(`Opened ${name} in a new tab`);
    }
  }

  // One-off direct travel is one vocabulary too. The mnemonic completes the trip, and
  // every destination owns the liveness and landing that make its surface useful rather
  // than leaving the dispatcher to know which furniture it enters.
  const DIRECT_DESTINATIONS = [
    {
      id: "navigation.panel.threads",
      key: "Shift+t",
      does: "Go to the Threads panel",
      line: "Threads panel",
      when: () => true,
      go: () => {
        setPanel(true);
        threadsBox.focus({ preventScroll: true });
      },
      active: panelIsOpen,
    },
    {
      id: "navigation.panel.decisions",
      key: "Shift+a",
      does: "Go to the Asks panel",
      line: "Asks panel",
      when: decisionsOffered,
      go: () => {
        showTray("decisions");
        (decisionRows()[0] ?? decisionsPanel).focus({ preventScroll: true });
      },
      active: () => currentTray() === "decisions",
    },
    {
      id: "navigation.panel.leaves",
      key: "Shift+l",
      does: "Go to the All leaves panel",
      line: "All leaves panel",
      when: leavesOffered,
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
      when: () => true,
      go: enterPageMap,
      active: pageMapIsActive,
      close: leavePageMap,
    },
  ];
  const ADDRESSES = [
    {
      id: "navigation.page-map-item",
      key: "m",
      word: "Page map locations",
      does: "Press the first Button at the nth Page map location",
      list: pageMapItems,
      go: openPageMapItem,
      viewport: true,
    },
    {
      id: "navigation.tab",
      key: "t",
      word: "tabs",
      does: "Select the nth tab",
      list: pageTabs,
      // A numbered tab is an activation and an arrival. Reveal first so a nested tab can
      // open its owning panel, then focus the control and use its click path so the
      // widget's pointer and keyboard selection remain one behavior.
      go: (tab) => {
        scrollToElement(tab, undefined, "nearest");
        tab.focus({ preventScroll: true });
        tab.click();
      },
    },
    {
      id: "navigation.link",
      key: "h",
      word: "hyperlinks",
      does: "Follow the nth hyperlink",
      list: pageLinks,
      // Completing the address is the link's activation. Use the platform click method
      // so authored handlers, cancellation, fragments, targets, and downloads keep their
      // anchor semantics; followLink adds the chord's focus and announcement afterwards.
      go: followLink,
    },
    {
      id: "navigation.fold",
      key: "f",
      word: "folds",
      does: "Go to the nth fold and open it",
      list: pageDisclosures,
      // Opening is the arrival and not a press that follows it. Every arrival here reveals
      // the collapsed containers on its way — this is the one whose target is the container,
      // so the reveal that was travel for the others is the whole motion for this one, and a
      // reader who wanted the section open has it open having asked once. The scroll takes
      // the box rather than the summary, since a section taller than the window starts at its
      // start where a centred summary would put half the screen above it. Standing on the
      // summary afterwards leaves the platform's own press to close it again, which the
      // disclosure scope names on the line.
      go: (summary) => {
        scrollToElement(summary.parentElement, undefined, "nearest");
        summary.focus({ preventScroll: true });
      },
    },
  ];
  // A list's addressable members, and the range its label names. Nine is the whole numbered
  // vocabulary: every member has one digit and every digit completes immediately. Ordinary
  // lists take the stable document prefix. A viewport list takes the visible prefix and
  // holds that reading for the duration of a scroll.
  let viewportWindows = new Map();
  function currentAddressed(entry) {
    const members = entry.list();
    if (!entry.viewport) return members.slice(0, MAX_NUMBERED_ADDRESSES);
    const placement = createAddressPlacement({ banner, keylineEl, startsAt });
    return members
      .filter((member) => placement.visibleBox(member))
      .slice(0, MAX_NUMBERED_ADDRESSES);
  }
  function refreshViewportWindows() {
    viewportWindows = new Map(
      ADDRESSES.filter((entry) => entry.viewport).map((entry) => [
        entry,
        currentAddressed(entry),
      ]),
    );
  }
  const addressed = (entry) =>
    entry.viewport && chordArmed
      ? (viewportWindows.get(entry) ?? [])
      : currentAddressed(entry);
  const range = (n) => (n > 1 ? `1–${n}` : "1");
  // How far the chord has come: `g`, and the list's letter once one has named a list. The
  // key line and page chips combine that progress with each full route; the reference shows
  // the same routes at rest.
  const chordKeys = () => [labelOf(GOTO), aimedList?.key].filter(Boolean);
  const addressChip = (entry, n) => {
    const steps = [labelOf(GOTO), entry.key, String(n)];
    const chip = el("span", "lf-address lf-chord-address");
    chip.append(keySequence(steps, progressStates(steps, chordKeys().length)));
    return chip;
  };

  // Whether the chord is up, and the list a digit addresses once a letter has named one.
  // The armed window is a mode the whole keyboard is in, and a digit pressed inside it
  // belongs to the chord wherever focus sits. A widget's own digit keys used to have to ask
  // this before consuming one; they no longer do, and lf-options no longer imports it — the
  // chord's scope claims everything, so the dispatcher never reaches an inner scope while the
  // window stands, and the mode enforces itself where it was a rule each widget had to keep.
  //
  // `aimedList` and not `aimed`, which this file already spends on the aim chord's element
  // (refreshAim, aimTarget, aimBox): two concepts under one word, in one file, shadowing each
  // other inside the functions that hold both.
  let chordArmed = false;
  let aimedList = null;
  let scrolling = false;
  // Arming, aiming and disarming are one call, because they are one window: naming a list
  // re-opens it rather than starting a second.
  //
  // It stands until one of those, where it stood for a second and a half. A timeout is how a
  // keyboard resolves an ambiguous prefix, and there is none here: `g` is a prefix and
  // nothing else, any key the chord does not bind disarms it and then runs with its ordinary
  // meaning, so nothing is ever swallowed by a window left open. What the clock did instead
  // was charge the reader for reading the menu the press had just painted — and a letter
  // arriving a moment late is not a no-op but the page's own key, so a slow reader pressing
  // `l` got the leaves tray rather than the links.
  function setChord(on, list = null) {
    // Armed over a control that has claimed Escape, one press would have two owners — the
    // control's rung and the chord's cancel — so the chord refuses to arm there at all.
    if (on && !chordArmed && claimsEsc(focused())) return;
    if (on) refreshViewportWindows();
    else viewportWindows.clear();
    chordArmed = on;
    aimedList = on ? list : null;
    scrolling = false;
    document.body.toggleAttribute(PAGE_PAINT_ATTRIBUTE.goto, on);
    // The chips are the eye's copy; the window itself is spoken, or the mode change is
    // silent to exactly the reader who can't see them. Off the rows either way, since the
    // rows are what the window answers now — the letters at the first stage, the named
    // list's digits at the second — and a sentence written here for the second would have
    // been the row's own words, restated where nothing could correct them.
    if (on) announce(`Go to — ${saying(GO.rows)}`);
    paintHere();
  }

  // The chips: one per addressable member, drawn in the chrome's layer (addressLayer) and
  // placed from the member's own visible box, so a chip cannot claim room the page has
  // already refused — a thread scrolled out of the panel's list, a card half out of a board.
  //
  // Every visible member keeps its complete address. Naming a list narrows the members but
  // does not narrow their labels: the list key changes from neutral to pressed in place, so
  // the route's geometry stays fixed while the reader advances through it.
  //
  // The layer is the chrome's rather than the page's own markup for the reason every mark is
  // (see "Paint; don't wrap"): the addressable things include links set mid-sentence, and a
  // span written into a paragraph to carry a number is a span the passage walk then has to
  // know about.
  //
  // Every chip is built detached and the layer takes them in one write, which is the rule
  // the legend states for this same layer: a chip in the tree is a DOM write, and the next
  // member's rect read after one is a layout forced per member, on every scroll frame a
  // numbered-list window stands through.
  function paintAddresses() {
    if (!chordArmed) {
      addressLayer.replaceChildren();
      return;
    }
    // A state render or version activation can replace Page-map hosts without scrolling.
    // Refresh at every resting presentation boundary; a live scroll keeps the old window
    // until its own `scrollend` boundary below.
    if (!scrolling) refreshViewportWindows();
    const placement = createAddressPlacement({ banner, keylineEl, startsAt });
    const chips = [];
    for (const entry of aimedList ? [aimedList] : ADDRESSES) {
      for (const [i, member] of addressed(entry).entries()) {
        const r = placement.visibleBox(member);
        if (!r) continue;
        const chip = addressChip(entry, i + 1);
        chip.style.left = `${r.left}px`;
        chip.style.top = `${r.top}px`;
        chips.push(chip);
      }
    }
    // A chip that lands on one already drawn is taken down. Two addressable things can start
    // within a chip's width of each other — footnote markers in a row, a link that is the
    // whole of a summary — and stacked chips do not read as two: the one underneath shows an
    // edge, and its neighbour's digit is the number the reader takes for its own. That is the
    // one failure worse than saying nothing, because pressing it goes somewhere else.
    //
    // Dropping it costs nothing the page had promised. A chip is already only drawn for a
    // member the reader can see, and an address holds whether or not its chip does — so this
    // is the same answer, given to a member the page has no room to say it about rather than
    // to one that has scrolled away.
    //
    // Clamp each complete face before checking collisions: bringing a chip on screen
    // can move it onto its neighbour. Measure every face before moving or removing one.
    // The key line reserves its own box first, so the chips cannot cover their legend.
    placement.paint(addressLayer, chips);
  }
  // A page that moves under an armed window moves the boxes the chips were placed from, so
  // the chips follow it rather than standing where the page used to be. Capture, because the
  // panel's list and a board's own overflow scroll in boxes of their own and a scroll event
  // does not bubble.
  //
  // Only while the chord is armed, which is why this is a listener of its own rather than a
  // line in the page's own repaint door (pageShifted): what the line says about the chord
  // holds at every scroll position, no list's membership moving with the page, so the door
  // that repaints on every scroll of every page would be repainting for nobody. Armed, the
  // paint is the whole of paintHere — the ring and the line are cheap beside the chips, and
  // one door is what stops the chips having a repaint set of their own to keep in step.
  addEventListener(
    "scroll",
    () => {
      if (!chordArmed) return;
      scrolling = true;
      paintHere();
    },
    { capture: true, passive: true },
  );
  addEventListener(
    "scrollend",
    () => {
      if (!chordArmed || !scrolling) return;
      scrolling = false;
      paintHere();
    },
    { capture: true, passive: true },
  );
  addEventListener("resize", () => {
    if (!chordArmed) return;
    scrolling = false;
    paintHere();
  });

  // The chord: one scope, a row per panel and addressable list, a row for the page's two
  // edges, and the window's own way out. A panel's mnemonic completes its travel. A list
  // row holds the route after g — its letter names the list, and the one digit it
  // then binds is the address into it. That is `v`'s shape,
  // a chooser whose second key belongs to the scope the first one stood up, and the reason
  // it is one row rather than two is that a digits row of its own could not name which list
  // it meant. The edges row is the same motion one key shorter: an edge is one place, so its
  // letter completes the route, and it is why the scope has no `when` — every page has a
  // top, so the window g arms is never empty.
  //
  // A row's `when` carries both questions here, where a scope usually carries one of them: a
  // list the page hasn't got is a capability, and which list is aimed at is whether the press
  // moves now. They can share the answer because a mode is not somewhere the reader stands
  // near — see showHelp, which reads a mode's rows by their own liveness for exactly that
  // reason. Written as a scope per list instead, each stating its own capability, the two
  // were named apart at the price of three scopes under one title, and the reference then
  // gathered them in the order it walks the stack — backwards, so it named the lists in the
  // opposite order to the line that had just offered them.
  const GO = {
    title: "Go to",
    reach: "with g armed",
    chord: chordKeys,
    at: () => chordArmed,
    claims: EVERYTHING,
    rows: [
      {
        id: "navigation.thread.edge",
        // A focused thread is one place, so its two placements complete the chord
        // without naming a list or taking a digit. This is the thread-local counterpart
        // to the page edges below: k/j place the card inside its panel rather than moving
        // the document to the passage the card is about. It leads while live because it
        // is the one offer specific to where the reader stands; list members wear their
        // address chips directly when the chord arms.
        keys: ["k", "j"],
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
        when: () => !aimedList && Boolean(focusedThread()),
        run: (binding) => {
          const thread = focusedThread();
          setChord(false);
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
        keys: ["p"],
        does: "Return to the page, keeping the thread panel open",
        line: "page — threads kept",
        when: () => !aimedList && inPanel() && !panelCovers(),
        run: () => {
          setChord(false);
          letGo();
        },
      },
      ...DIRECT_DESTINATIONS.map((destination) => ({
        id: destination.id,
        keys: [destination.key],
        label: spell(destination.key),
        does: destination.does,
        line: destination.line,
        when: () => !aimedList && destination.when(),
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
          setChord(false);
          destination.go();
        },
      })),
      ...ADDRESSES.map((entry) => ({
        id: entry.id,
        runFromReference: false,
        keys: () => {
          if (aimedList !== entry) return [entry.key];
          return addressed(entry).map((_, i) => String(i + 1));
        },
        // The range the capped list actually holds, so the label cannot offer an address
        // no member wears.
        label: () => (aimedList === entry ? range(addressed(entry).length) : entry.key),
        chordSteps: () => {
          if (aimedList === entry) return [range(addressed(entry).length)];
          return [entry.key];
        },
        completeChordSteps: () => [entry.key, range(addressed(entry).length)],
        does: entry.does,
        line: entry.word,
        when: () => addressed(entry).length > 0 && (!aimedList || aimedList === entry),
        run: (binding) => {
          if (aimedList !== entry) return setChord(true, entry);
          const member = addressed(entry)[Number(binding) - 1];
          setChord(false); // before the travel, so the arrival's own scrolling paints nothing
          entry.go(member);
        },
      })),
      {
        id: "navigation.page.edge",
        keys: ["g", "Shift+g"],
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
        when: () => !aimedList,
        run: (binding) => {
          setChord(false); // before the travel, so the arrival's own scrolling paints nothing
          const box = seenScroller();
          glideTo(box, binding === "g" ? 0 : box.scrollHeight);
        },
      },
      {
        id: "navigation.address.back",
        // Two presses in, two presses out. `g` opens the window and a letter names a list
        // inside it. The complete routes stay fixed while that letter turns pressed, so one
        // Escape gives the letter back and the next closes the window. Collapsing both at
        // once stranded a reader who had narrowed to the wrong list back on the page, making
        // them press `g` again to reach a window that had been standing the whole time.
        keys: ["Escape"],
        chordControl: true,
        does: () => (aimedList ? "Back to the lists" : "Cancel the chord"),
        line: () => (aimedList ? "back to the lists" : "cancel"),
        // Re-arming rather than a field of its own: `setChord` is where arming, aiming and
        // disarming already live, and re-opening the window with no list named is exactly
        // what the second stage backs out to.
        run: () => {
          if (aimedList) return setChord(true);
          setChord(false);
          announce("Go to cancelled");
        },
      },
    ],
  };

  // The way in to the chord. Its row supplies the same leader every painted address uses,
  // so the letter the reader presses and the letter the page prints cannot diverge.
  //
  // The key alone on the line: what it opens is a table, so the scope it stands up names the
  // available lists and their complete ranges, one chip each.
  const GOTO = {
    id: "navigation.address.open",
    keys: ["g"],
    does: "Go to a panel, list member, page, or edge",
    line: "go to",
    // No `when`: the window this press stands up always holds at least the page's edges.
    run: () => setChord(true),
  };

  const isChordArmed = () => chordArmed;
  return {
    GO,
    GOTO,
    isChordArmed,
    paintAddresses,
    setChord,
  };
}
