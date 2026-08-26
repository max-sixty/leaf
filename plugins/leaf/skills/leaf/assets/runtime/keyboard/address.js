import { labelOf } from "./bindings.js";

export function createAddress({
  EVERYTHING,
  SAY_BOX,
  addressLayer,
  announce,
  banner,
  claimsEsc,
  el,
  focused,
  glideTo,
  goToAsk,
  keylineEl,
  landIn,
  openAsks,
  openThreads,
  pageParts,
  paintHere,
  panelIsOpen,
  saying,
  seenScroller,
  setPanel,
  startsAt,
  scrollToElement,
}) {
  // ---------- the g chord: the page's addresses ----------
  // g arms a mode in which a letter names one of the page's lists and a digit is a place in
  // it: `g c 2` is the second open comment's reply box, `g a 1` the first thing the page is
  // waiting on, `g l 3` the third link. Two completions take no digit: `g g` is the top of
  // the page and `g G` the bottom — each edge is one place, so the second key is the whole
  // address. `g G` rather than vim's bare G because g is the page's one go-to prefix, and
  // an edge is one more place it names rather than a second leader. Naming a list shows it
  // — the panel opens for the comments — and each of its addressable members then wears its
  // digit as a chip, so the addresses are on screen wherever the reader is looking. A digit
  // consumes the mode; so
  // does Escape, and so does focus entering a box. Any other key disarms and then runs with
  // its ordinary meaning, which the dispatcher spells as disarming and walking the stack
  // again rather than as a rule of its own — a mistyped g therefore costs the reader nothing
  // beyond the press their next key was going to make anyway.
  //
  // The chord was one list deep once — g then a digit, and the digit meant a reply box —
  // which spent the whole of a leader on the one list that had asked for it first. The letter
  // is what opens that: a second list costs a letter rather than a second chord, and the line
  // says `g` alone rather than a range that only ever counted threads.
  //
  // Which lists there are is this table and nothing else. The chord's scope, the chips, the
  // line's words and the reference are all readings of it, so a fourth list is an entry here
  // rather than an edit to four consumers, and nothing that reads the table asks which list
  // it is holding. One place names a list at all, and it is not a reader of the table: a
  // member with a surface of its own has to say which list that surface belongs to, which is
  // the reply box's placeholder (COMMENTS, below). An entry says its letter, the word every surface calls the list by, the sentence
  // the reference reads, its members in address order, and how to arrive at one. `spot` is
  // where the chip hangs when that is not the member itself — a comment's address belongs on
  // the box the digit lands in, not on the thread's far corner.
  // What the document holds, in reading order, as against what the chrome holds: the banner,
  // the versions and the leaves tray have keys of their own, and a comment's message is the
  // panel's rather than the page's. The addresses read the document through here, where
  // a scope naming a platform key reads `pageQueryAll` and crosses the declared shadow roots
  // as well: an address is a place in a list the reader counts down the page, and a tree a
  // module built has no place in that count, while what the reader can stand on is wherever
  // the markup ended up — a diff stages a <details> per file in a root they tab straight
  // into.
  //
  // The whole document and not the parts on screen, which is the tempting reading and the
  // wrong one twice over. An address that counted what is in the window is an address that
  // means a different link at every scroll position, so a reader who has just learnt that the
  // PR is `g l 2` is wrong a moment later; and it would put the key line's own truth on the
  // scroll, since a row that goes dead as the page moves is a row the line has to be
  // repainted to stop promising — a paint measured at 1.3ms on the gallery, on every scroll
  // frame of every page, for one row. Document order costs the pages holding more than nine
  // links their tail, which is the bound every list here has.
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
  // no digit, and `g d` can say three where four things fold. Widening it is not free —
  // `go` scrolls the box and leans on `reveal`, which cannot open a group from its row — and
  // the count a reader wants under `g` is of the sections the author wrote.

  // How many members of a list a digit can reach. The bound is the keyboard's — ten digits,
  // one of them no ordinal — and not any list's, so it is stated once here rather than in
  // each entry.
  const ADDRESS_CAP = 9;
  // The one entry with a name of its own, because one of its members has a standing
  // surface to speak its address on: a reply box's placeholder says "Reply · g c 2" at
  // all times, and the panel builds that box (threadNode). Every other list is reached
  // through the table.
  const COMMENTS = {
    key: "c",
    word: "comments",
    does: "Go to the nth open comment's reply box",
    list: openThreads,
    spot: (thread) => thread.querySelector(":scope > .lf-compose"),
    // What it takes to show this list, and the way back. The panel holds it and draws
    // nothing while closed, so a letter that named it and left the panel shut painted no
    // chip at all. An entry whose members are on the page states no reveal at all.
    //
    // The undo is the entry's for the same reason the reveal is: core never learns what a
    // panel is. It states none where the panel already stood, because then the aim put
    // nothing there — and closing it would be the chord taking back something that was
    // never its to take.
    reveal: () => {
      if (panelIsOpen()) return null;
      setPanel(true);
      return () => setPanel(false);
    },
    // stepThread-to-nth and its Enter in one press. The box by its place in the thread and
    // not the first textarea inside it, a message being free to carry a widget with one of
    // its own — a draft's open editor stands before the reply box in the DOM.
    go: (thread) => landIn({ held: thread, box: thread.querySelector(SAY_BOX) }),
  };
  const ADDRESSES = [
    COMMENTS,
    {
      key: "a",
      word: "asks",
      does: "Go to the nth thing this page is waiting on you for",
      // The list n/p walk, addressed rather than stepped: one reading, so the digit and the
      // walk cannot disagree about which ask is the third one. The arrival is handed that
      // whole list and not the nine a digit can spell, so what it announces is the ask's
      // place among everything the page is waiting on.
      list: openAsks,
      go: (ask) => goToAsk(ask, openAsks()),
    },
    {
      key: "l",
      word: "links",
      does: "Go to the nth link",
      list: pageLinks,
      // Focus, not a follow: g says go, and what a focused link then answers is the
      // platform's Enter, which the link scope names on the line. A press that navigated
      // would be a door with no landing to look at first.
      go: (link) => {
        scrollToElement(link);
        link.focus({ preventScroll: true });
      },
    },
    {
      key: "d",
      word: "disclosures",
      does: "Go to the nth disclosure and open it",
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
        scrollToElement(summary.parentElement);
        summary.focus({ preventScroll: true });
      },
    },
  ];
  // A list's addressable members, and the range its label names. Capped where it is read
  // rather than where each list is written, so an entry states what it holds and this states
  // what the keyboard can reach.
  const addressed = (entry) => entry.list().slice(0, ADDRESS_CAP);
  const range = (n) => (n > 1 ? `1–${n}` : "1");
  // How an address is spelled, in one place and off the row that binds the key (GOTO): the
  // keys it takes, in press order. A member with a standing surface of its own says the
  // whole motion there — a reply box's placeholder reads "Reply · g c 2" — and the chord's
  // own chip is built from the same array. Written out at each of them, `g` was a letter
  // three sites had agreed on and none could correct.
  //
  // An array rather than a string, because the surfaces drawn inside the armed window differ
  // only in how much of the address the reader has already pressed: the key line drops those
  // keys, having said them once in the chip that heads it, and an address on the page dims
  // them. `n` is a digit on a chip and a range on the line, which is the same array either
  // way — spelled out at both, the space between letter and digit was a third site to keep
  // in step.
  const addressKeys = (entry, n) => [labelOf(GOTO), entry.key, String(n)];
  const addressLabel = (entry, n) => addressKeys(entry, n).join(" ");
  // How far the chord has come: `g`, and the list's letter once one has named a list. Every
  // surface that shows an address asks it — the chip that heads the key line, the ranges
  // beside it, the reference's full chords and the dimmed half of a chip on the page — so
  // none of them can disagree about which press comes next.
  //
  // The chord's stage and not the reader's presses, which is the reading the reference needs:
  // `?` reaches it from a page nobody has armed (declaredStack walks every scope, live or
  // not), where the reference puts that prefix in front of each row to show the complete
  // chord. The key line instead speaks the prefix in its own armed chip and lets the rows say
  // what remains inside the mode. A chip is the one surface with nothing around it to carry
  // the leader, and it is drawn only while the window is up, so its two questions — how far
  // in, and how much the surroundings already say — have one answer.
  const chordKeys = () => [labelOf(GOTO), aimedList?.key].filter(Boolean);
  // An address as the page wears it: the whole of it, the keys already pressed standing back
  // and the ones still to come lit. The whole of it, because a chip is the address — the same
  // one its reply box's placeholder speaks while nothing is armed at all, and a chip saying
  // `c 2` two pixels from a placeholder saying `g c 2` was a second spelling of one motion,
  // the shorter of which reaches nothing from a standing start.
  //
  // Both halves are set at the chip's one size, and the split is carried by ground: the spent
  // keys sit on the chip's own, the live ones on a lit block. Size was the channel once — the
  // spent keys two points smaller — and it cost more than it bought. One box held two type
  // sizes, which reads as a fault rather than a hierarchy; and because the split moves a key
  // from one size to the other, naming a list re-set every chip on screen, each one narrowing
  // 2.4px and sliding 1.2px under the eye that was reading them. Ground carries the same
  // distinction and takes no advance, so a press lights one more key and moves no glyph.
  // That last part is the stylesheet's doing and not this function's: the lit block's padding
  // is cancelled by an equal negative margin. Paid for in advance instead, the key crossing
  // between the halves stepped 3px on the press — measured, and larger than the 1.2px slide
  // this replaced, so the fault would have survived one glyph smaller.
  //
  // The space between the two halves is the address's own, the one `addressLabel` joins on,
  // so what the chip reads is what every other surface spells. It is a text node and the box
  // is block rather than flex for exactly that reason: flex drops a whitespace-only child, and
  // the chip came out `ga 1`.
  //
  // `lf-lit` and not `lf-live`, which this layer already spends on the visually-hidden live
  // region: a span wearing that name is clipped to a pixel by the stylesheet's own rule, so
  // the half of the address still to be pressed would have been drawn nowhere at all.
  //
  // Built only inside the armed window, which is where the chord's own keys are never none —
  // and, past the letter, only for the list the chord has named (paintAddresses narrows to
  // `aimedList` there), which is what makes those keys a prefix of this address rather than a
  // different list's. So `.lf-spent` is always present on a chord chip and never on the bare
  // digit an options group wears, which is how one stylesheet dresses both.
  const addressChip = (entry, n) => {
    const keys = addressKeys(entry, n);
    const made = chordKeys().length;
    const chip = el("span", "lf-address");
    chip.append(
      el("span", "lf-spent", keys.slice(0, made).join(" ")),
      " ",
      el("span", "lf-lit", keys.slice(made).join(" ")),
    );
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
  // What the aim put on screen, and the way to take it back. Naming a list that draws
  // nothing until asked is one press doing two things — it narrows the window and opens the
  // panel the chips are drawn from — so the press that gives the letter back has to give
  // both back, or the reader keeps a layer they never asked for and the chord costs three
  // presses out for two in. That is the keyboard-is-a-stack rule failing inside the fix
  // written for it, which is how it was found.
  //
  // Every unused way down takes it back: Escape off the aim, a stray key, focus entering a
  // box. What makes a way down *used* is the reader landing in what the reveal showed, which
  // `keepShown` states — and both routes there have to say it. The digit is one; a click into
  // the panel the chord just opened is the other, and with only the digit exempt that click
  // closed the panel under the reader's own pointer and dropped them on the toggle button.
  let aimShowed = null;
  const keepShown = () => (aimShowed = null);
  // Arming, aiming and disarming are one call, because they are one window: naming a list
  // re-opens it rather than starting a second, and every way down — Escape, a stray key,
  // focus entering a box — takes the aim with it.
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
    // A list the reader cannot see is a list wearing no addresses: the panel holds the
    // comments and draws nothing while closed, so naming that list opens it, and the chips
    // land on boxes that have a geometry to be placed from. The open belongs here rather
    // than in the arrival, where it left the letter painting nothing at all.
    //
    // Taken back before the next state is written, so an aim ending — into the bare window,
    // or out of the chord altogether — leaves the screen as the letter found it.
    aimShowed?.();
    aimShowed = list?.reveal ? list.reveal() : null;
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
  // Each carries its whole address, which is what lets every list paint at once: a bare
  // digit promises nothing until a letter has named a list, so the chips could only follow
  // the letter, and the press that opened the mode moved nothing the reader could see.
  //
  // The layer is the chrome's rather than the page's own markup for the reason every mark is
  // (see "Paint; don't wrap"): the addressable things include links set mid-sentence, and a
  // span written into a paragraph to carry a number is a span the passage walk then has to
  // know about.
  //
  // Every chip is built detached and the layer takes them in one write, which is the rule
  // the legend states for this same layer: a chip in the tree is a DOM write, and the next
  // member's rect read after one is a layout forced per member — up to nine per list, and
  // every list until a letter narrows them, on every scroll frame an armed window stands
  // through.
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
      // Every list until one is named, and then that one alone: the offer narrows as the
      // chord advances, and the addresses a reader was already reading keep their places.
      // Narrows rather than summons, for every list drawn where the reader can see it — a
      // list that draws nothing until revealed (the shut comment panel) has no box to place
      // a chip from, so its letter is what both reveals it and paints it.
      for (const entry of aimedList ? [aimedList] : ADDRESSES) {
        for (const [i, member] of addressed(entry).entries()) {
          const r = startsAt(entry.spot?.(member) ?? member, clips);
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

  // The chord: one scope, a row per addressable list, a row for the page's two edges, and
  // the window's own way out. A list row holds the whole motion — its letter names the
  // list, and the digits it then binds are the addresses into it. That is `v`'s shape, a
  // chooser whose second key belongs to the scope the first one stood up, and the reason it
  // is one row rather than two is that a digits row of its own could not name which list it
  // meant. The edges row is the same motion one key shorter: an edge is one place, so its
  // letter is the whole address, and it is why the scope has no `when` — every page has a
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
    title: "Go by address",
    chord: () => chordKeys().join(" "),
    at: () => chordArmed,
    claims: EVERYTHING,
    rows: [
      ...ADDRESSES.map((entry) => ({
        keys: () =>
          aimedList === entry
            ? addressed(entry).map((_, i) => String(i + 1))
            : [entry.key],
        // The range the list actually holds, so the label cannot offer an address no member
        // wears. The keys already pressed drop off the front for the armed key line; the
        // reference puts the scope's chord back in front to show the motion from rest.
        label: () =>
          addressKeys(entry, range(addressed(entry).length))
            .slice(chordKeys().length)
            .join(" "),
        does: entry.does,
        line: entry.word,
        when: () => entry.list().length > 0 && (!aimedList || aimedList === entry),
        run: (binding) => {
          if (aimedList !== entry) return setChord(true, entry);
          const member = addressed(entry)[+binding - 1];
          // The reveal has done its work: the reader is about to stand in what it showed,
          // so it is theirs now rather than the aim's to take down.
          keepShown();
          setChord(false); // before the travel, so the arrival's own scrolling paints nothing
          entry.go(member);
        },
      })),
      {
        keys: ["g", "Shift+g"],
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
        // Two presses in, two presses out. `g` opens the window and a letter names a list
        // inside it — the armed chip says so, reading `g` and then `g c`, and the chips on
        // the page narrow with it — so one Escape gives the letter back and the next
        // closes the window. It took both at once, which is the same drift `c` had at the
        // panel: a reader who had narrowed to the wrong list wanted the other one, and
        // cancelling put them back on the page, pressing `g` again to reach a window that
        // had been standing the whole time.
        keys: ["Escape"],
        does: () => (aimedList ? "Back to the lists" : "Cancel the chord"),
        line: () => (aimedList ? "back to the lists" : "cancel"),
        // Re-arming rather than a field of its own: `setChord` is where arming, aiming and
        // disarming already live, and re-opening the window with no list named is exactly
        // what the second stage backs out to.
        run: () => setChord(Boolean(aimedList)),
      },
    ],
  };

  // The way in to the chord, named for the reason the two rows above it are: the armed chip
  // and every address a member speaks are built from this row's own key (addressLabel), so
  // the letter the reader presses and the letter the page prints cannot be two decisions.
  //
  // The key alone on the line: what it opens is a table, and a label naming one of its lists
  // would be the chord's old shape wearing a letter — `g 1–9` said "threads" without saying
  // it, and the day a second list arrived there was no honest range to print. The scope the
  // press stands up names them all, one chip each.
  const GOTO = {
    keys: ["g"],
    does: "Go by address — the next key names one of the page's lists, or its top or bottom",
    line: "go to",
    // No `when`: the window this press stands up always holds at least the page's edges.
    run: () => setChord(true),
  };

  const isChordArmed = () => chordArmed;
  return {
    COMMENTS,
    GO,
    GOTO,
    addressLabel,
    addressed,
    isChordArmed,
    keepShown,
    paintAddresses,
    setChord,
  };
}
