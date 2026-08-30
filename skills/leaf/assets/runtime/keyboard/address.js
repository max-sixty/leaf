import { labelOf, spell } from "./bindings.js";
import { keySequence } from "./presentation.js";

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
  focused,
  focusedThread,
  glideTo,
  inPanel,
  keylineEl,
  leavesOffered,
  letGo,
  openPageMapItem,
  othersLinks,
  othersPanel,
  pageMapItems,
  pageParts,
  pageMapOffered,
  paintHere,
  panelCovers,
  placeThreadEdge,
  saying,
  seenScroller,
  setPanel,
  showTray,
  startsAt,
  scrollToElement,
  threadsBox,
}) {
  // ---------- the g chord: the page's destinations ----------
  // g names one-off travel. An uppercase mnemonic completes a direct destination (`g T`
  // Threads, `g A` Asks, `g L` All leaves, `g M` Page map), while a numbered list takes a
  // following digit (`g h 3` is the third hyperlink and `g f 2` the second fold).
  // Repeated movement through threads and asks belongs to their single-key category walks,
  // t/T and a/A, so those categories do not also carry numbered addresses.
  //
  // Which numbered lists there are is this table and nothing else. The chord's scope, the chips, the
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
  // The whole document and not the parts on screen, which is the tempting reading and the
  // wrong one twice over. An address that counted what is in the window is an address that
  // means a different link at every scroll position, so a reader who has just learnt that the
  // PR is `g h 2` is wrong a moment later; and it would put the key line's own truth on the
  // scroll, since a row that goes dead as the page moves is a row the line has to be
  // repainted to stop promising — a paint measured at 1.3ms on the corpus, on every scroll
  // frame of every page, for one row. The numbered route therefore keeps document order
  // stable and offers its first nine members; later members remain in the document's own
  // navigation rather than making a one-digit address ambiguous.
  //
  // Above the table rather than beside the other readings below it, because an entry
  // holds the function itself and the array literal reads it as the module evaluates.
  const pageLinks = () => pageParts("a[href]");
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
    },
    {
      id: "navigation.page-map",
      key: "Shift+m",
      does: "Go to the Page map",
      line: "Page map",
      when: pageMapOffered,
      go: enterPageMap,
    },
  ];
  const ADDRESSES = [
    {
      id: "navigation.page-map-item",
      key: "m",
      word: "page-map items",
      does: "Go to the nth page-map item",
      list: pageMapItems,
      go: openPageMapItem,
    },
    {
      id: "navigation.link",
      key: "h",
      word: "hyperlinks",
      does: "Follow the nth hyperlink",
      list: pageLinks,
      // Completing the address is the link's activation. Use the platform click method
      // so authored handlers, cancellation, fragments, targets, and downloads keep their
      // anchor semantics.
      go: (link) => link.click(),
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
  // vocabulary: every member has one digit, every digit completes immediately, and every
  // consumer below reads this same prefix rather than applying its own cap.
  const MAX_NUMBERED_ADDRESSES = 9;
  const addressed = (entry) => entry.list().slice(0, MAX_NUMBERED_ADDRESSES);
  const range = (n) => (n > 1 ? `1–${n}` : "1");
  // How far the chord has come: `g`, and the list's letter once one has named a list. The
  // key line shows this prefix once; the reference combines the standing-page prefix with
  // each full route. Page chips omit that prefix and show the complete suffix still needed
  // for their target.
  const chordKeys = () => [labelOf(GOTO), aimedList?.key].filter(Boolean);
  const addressChip = (entry, n) => {
    const chip = el("span", "lf-address lf-chord-address");
    chip.append(keySequence(aimedList ? [String(n)] : [entry.key, String(n)]));
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
    chordArmed = on;
    aimedList = on ? list : null;
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
  // At the first stage, every visible member shows its list letter and digit, the complete
  // remaining suffix that distinguishes it from the other lists. Naming a list narrows those
  // chips to the digit still needed. Every key in a chip remains neutral because none of its
  // displayed suffix has been pressed.
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
    const chips = [];
    if (chordArmed) {
      const clips = new Map();
      // The banner stands over the page rather than in it, so shownRect says nothing about
      // it — that reading is what the page's own boxes clip, and the bar clips none of them.
      // The chip is the one thing that has to care, being drawn above the bar: placed on a
      // corner the bar has taken, it is an address floating over the status line, naming
      // nothing the reader can see there. So it rides the covered edge, and a member with
      // nothing left below that edge wears no chip at all.
      const covered = banner.getBoundingClientRect().bottom;
      for (const entry of aimedList ? [aimedList] : ADDRESSES) {
        for (const [i, member] of addressed(entry).entries()) {
          const r = startsAt(member, clips);
          if (!r || r.bottom <= covered) continue; // nothing to see, nothing to address
          const chip = addressChip(entry, i + 1);
          if (r.top < covered) chip.classList.add("lf-in");
          chip.style.left = `${r.left}px`;
          chip.style.top = `${Math.max(r.top, covered)}px`;
          chips.push(chip);
        }
      }
    }
    addressLayer.replaceChildren(...chips);
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
    // Every box is read after the one write and every removal made after the last read, so
    // the pass stays at the single layout the write already cost.
    //
    // The key line is standing in that same corner and goes in first, so a chip loses to it
    // the way it loses to a chip already drawn. It is the legend saying what these digits
    // mean, on screen exactly as long as they are, so covering it is the one collision that
    // takes away the reader's answer rather than one of its members. The bar at the other
    // edge is dodged earlier and by clamping, because a chip has somewhere to go there: the
    // covered edge is above the member, while sliding clear of a line at the foot would put
    // the chip on a member it no longer sits on.
    const kept = [keylineEl.getBoundingClientRect()];
    const piled = [];
    for (const chip of chips) {
      const box = chip.getBoundingClientRect();
      if (kept.some((standing) => overlaps(box, standing))) piled.push(chip);
      else kept.push(box);
    }
    for (const chip of piled) chip.remove();
  }
  // Whether two boxes share any pixel. Touching edges do not, so two chips laid exactly a
  // chip's width apart sit side by side rather than one of them being taken down. That
  // boundary is the chip's own width and moves with it — the face is a little wider than it
  // was — so what survives a crowded line is a fact about the face rather than a constant,
  // and a page whose members used to clear it by a pixel is not promised to now.
  const overlaps = (a, b) =>
    a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
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
  addEventListener("scroll", () => chordArmed && paintHere(), {
    capture: true,
    passive: true,
  });
  addEventListener("resize", () => chordArmed && paintHere());

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
        // inside it — the pressed prefix grows and the page chips narrow to that list — so
        // one Escape gives the letter back and the next closes the window. It took both at
        // once, which is the same drift `c` had at the panel: a reader who had narrowed to
        // the wrong list wanted the other one, and cancelling put them back on the page,
        // pressing `g` again to reach a window that had been standing the whole time.
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
