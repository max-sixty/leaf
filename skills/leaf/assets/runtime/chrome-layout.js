// The width the panel stands at for a reader who has not moved its edge. 420 since
// threads carry questions — option rows are the one thread content that can't scroll or
// scale its width away, and 360 crowded them. A default rather than the width, because
// what a conversation needs is a fact about the conversation: a thread quoting a table
// wants room the same thread quoting a sentence does not, and only the reader looking at
// it knows which this is. So the edge is a thing they take hold of (`drawnEdge`), and
// this is where it stands until they do.
export const PANEL_W = 420;
// How narrow they may draw it in. 320 is the narrowest window the panel is held to
// standing up in (test_a_thread_gives_its_reply_the_full_row_and_its_actions_the_next),
// so it is the narrowest width anything has laid a thread's reply box and its two
// actions out at; below it nothing says they still fit. Wanting the panel gone is what
// closing it is for, and narrowing it to nothing is not the same wish.
export const PANEL_MIN = 320;
// The window under which yielding the strip is worse than being covered by it, as a
// query rather than a number, because three things ask it: the rule that takes the strip,
// the rule that hands scrolling to the sheet instead, and the runtime, for what follows
// from which of those the page is under. Written as the covering half, since that is the
// half the runtime asks about; the strip is its complement, spelled `not` where it is
// taken.
//
// Asked of the default width and not of the reader's own, so widening the panel can never
// flip the posture out from under the hand doing it: a panel dragged past half its window
// would otherwise stop standing beside the page and cover it instead, which is the whole
// page rearranging itself in answer to one pixel of a drag. What the reader's width does
// answer to is the edge's own `cap`, which holds it to the same bargain this line
// strikes — the page keeps at least what the panel takes — without putting the posture
// itself in play.
export const COVERING = `(width <= ${PANEL_W * 2}px)`;
export const NON_COVERING = `(width > ${PANEL_W * 2}px)`;
// Where each standing width is written, and where the cascade reads it. Named rather than
// spelled, because the stylesheet and the runtime's writer are two ends of one fact
// and a property spelled twice is two facts the day one of them moves.
export const PANEL_PROP = "--lf-panel-w";

// Panel open/closed is remembered too: it survives live activation, document travel,
// and reload, so reopening the panel by hand after every revision gets old fast.
export const PANEL_KEY = "lf-panel-open";

export function createChromeLayout({
  banner,
  chromeRoot,
  commentsEdge,
  composer,
  composerIsOpen,
  closeReactions,
  containsAcross,
  currentTray,
  dockSeats,
  focused,
  generalRow,
  keylineEl,
  pageShifted,
  paintHere,
  panel,
  placeComposer,
  readerStore,
  refreshFab,
  refreshHover,
  renderPanel,
  reserveListClearance,
  scrollerGutter,
  showTray,
  syncReactLayout,
  syncGeneral,
  toastEl,
  toggleBtn,
  trayStrip,
  traysEdge,
}) {
  // The width the theme wants a page's box to have before it takes a strip of it for the
  // margin (theme.css's --strip-min, stated there because that is where the strips and
  // their breakpoints are). Read blind: the runtime reports how wide the box is against
  // the number the theme states and never learns which idiom spends it. A theme without
  // the token leaves this NaN, every comparison against it false, and the media query
  // alone deciding — which is the same answer a page with no runtime already gets. Read
  // from body at the moment of the question rather than caching root's default: a composed
  // margin posture may override the floor under the media query that grants it, and an
  // arriving panel must ask that composed value without the runtime learning which idioms
  // contributed it.
  const stripMin = () =>
    parseFloat(getComputedStyle(document.body).getPropertyValue("--strip-min"));

  // The room the head of the document leaves for the bar, measured off the bar as
  // rendered rather than stated as a number — --lf-banner-h is what the bar is drawn to
  // and a second copy of it here would be a release behind it the day either moved. What
  // spends this, and why it is spent as a box rather than as body's own padding, is the
  // rule in chrome-style.js that reads it. The key line's reservation at the foot is the same
  // arrangement, written by syncLayout because it is the same measurement every time the
  // line's height changes.
  document.body.style.setProperty("--lf-head", banner.offsetHeight + "px");

  // Until the first state answer, [] means "not read", not "no comments". Keep that
  // distinction for a Threads panel restored or opened during startup; its General
  // composer stays usable while the log-derived list says what it is waiting for.

  // The threads the panel last reconciled. A work line repaints on the heartbeat's clock and
  // not only on the log's, because its age is half of what it says and a claim nobody
  // renews is exactly the one whose age has stopped moving. Keeping the last fold is what
  // makes that cheap: buildThreads walks the log and the page, and a second walk every two
  // seconds would answer nothing the last one didn't.
  let panelOpen = false;
  const panelIsOpen = () => panelOpen;
  // Whether the panel stands over the page rather than beside it — the same fact as which
  // of the two rules that take the strip the page is under, and as which region the
  // reader's own scrolling moves. Asked of the edge's query rather than stored, so no reader
  // of it can hold an answer from a window that has gone.
  const panelCovers = () => panelOpen && commentsEdge.over.matches;
  // Whether the reader is standing in the panel rather than merely looking at it — focus,
  // not visibility, the same line PANEL draws for its own scope and the one every surface
  // here reads. A press that acts on where the reader is standing has to ask it of the
  // focus: beside the page the panel is a column of its own, and a reader working down the
  // list is in it whatever the window is wide enough to show behind them.
  const inPanel = () => panelOpen && containsAcross(panel, focused());
  // The strip the page yields to the thread panel is its edge's width until the window is
  // too narrow to give one up. One expression keeps the margin the rule takes and the room
  // measured against it on the same terms.
  const panelStrip = () => (panelOpen && !panelCovers() ? commentsEdge.width() : 0);
  // Whether the page still has room for the margin the theme's idioms hang in. The strips
  // are granted by a media query, which asks the window; the page's box is the window less
  // whatever the panel holds of it, and this is the only thing that knows the difference. So
  // it asks the theme's own floor of the box and vetoes the grant where the room has gone —
  // a fact about the page rather than about any idiom that spends it. Without it a 1024px
  // window with the panel beside it left a page carrying sidenotes a 151px column, painting
  // its widest widgets out past the edge of one, and neither `version check --render` nor
  // the render suite can see that posture: both open a 1200px window with no panel in it.
  //
  // Its own function, and not syncLayout's, because the strip it vetoes is body's own
  // padding (theme.css) and syncLayout runs from an observation of that box — CLAUDE.md's
  // "The one writer may not write the box the layout is measured from", and the same reason
  // the strip the panel takes is a rule in the stylesheet.
  //
  // So it is called and not observed, and it is only as fresh as its callers — which is
  // enough, because each fact it turns on either arrives on an occasion of its own or does
  // not move at all. The window states the cap on a resize, and the panel its strip on the
  // gesture that moves it. The scroller's gutter is the one with no occasion to arrive on:
  // body gains or loses its bar as the document's height crosses the viewport, and replay
  // retiring a slot, a widget settling late, or an image arriving can each do that with no
  // resize and no chrome gesture behind it. What answers that is the stylesheet rather than
  // a call from every such path — body is given scrollbar-gutter: stable in the same rule
  // that makes it the scroller (chrome-style.js), so the room is reserved whether or not a
  // bar is drawn in it and the difference between the two boxes holds still for the page's
  // life. Joining layoutSizes would be the fix if it did not, and it is the one the rule
  // above forbids: the strip this vetoes is padding on the observed box, and stateRoom can
  // be observed only because it writes nothing that box is measured from.
  //
  // The strip is stated rather than measured off body, whose clientWidth is the box itself
  // and would be the natural reading. The margin transitions, so a measurement taken during
  // the slide is the posture flipping and flipping back across a fifth of a second, which is
  // a page rewrapping its notes into the margin and out of it while the panel opens. Stated,
  // it is the width being arrived at.
  // Two answers from the one reading, because they are the same fact asked coarsely and
  // finely: whether the page can afford a margin strip at all, and how much of one it still
  // owes. The width is published rather than spent here for the reason the floor is read
  // blind — the runtime says how wide the page's box is and never learns which idiom hangs
  // something in the margin, so an idiom's own rule does its own arithmetic against it, the
  // way the wide rules already spend --lf-room. A query cannot see the panel or the
  // scroller's own bar and this can, which is the whole of what the runtime adds; a page with
  // no runtime behind it falls back to the viewport in each rule that reads it.
  function stateStrip() {
    // The scroller's gutter, which stateRoom takes off for the same reason and by the same
    // reading: body is the document's scroller, so a classic bar comes out of the room this
    // page has while the window says nothing about it. The coarse answer owes it as much as
    // the fine one. Without it the floor was met by a window with a bar's width less page
    // behind it, and the strip came out of the column the floor exists to keep it out of —
    // a sidenote page at exactly 1152px read at a 705px measure, and a sidebar and a note at
    // 1416px did the same.
    const avail =
      document.documentElement.clientWidth -
      scrollerGutter() -
      panelStrip() -
      trayStrip();
    document.body.toggleAttribute("data-lf-cramped", avail < stripMin());
    document.documentElement.style.setProperty("--lf-avail", avail + "px");
  }
  // A window that has changed is a cap that has changed, so the width each edge stands at
  // is restated beside the veto — one listener, every fact on it being an answer to the same
  // event, and none of them a reading of the box syncLayout measures.
  addEventListener("resize", () => {
    commentsEdge.state();
    traysEdge.state();
    stateStrip();
  });
  // Every writer here is a writer of the chrome, so nothing this function does resizes the
  // box it reads: the strip the page yields to the panel is the stylesheet's, and the strip
  // it yields to a margin idiom is stated above.
  function syncLayout() {
    const panelBeside = panelOpen && !panelCovers();
    // The toast lives in the same corner as the panel's Send button. Beside a wide
    // panel it steps left; over a covering sheet it stays inside the viewport and
    // rises above the whole composer, including a textarea grown by an unsent draft.
    toastEl.style.right = `calc(${panelBeside ? commentsEdge.width() + 18 : 18}px + var(--lf-safe-right))`;
    toastEl.style.bottom = `calc(${panelCovers() ? generalRow.offsetHeight + 18 : 18}px + var(--lf-safe-bottom))`;
    // The key line takes the toast's lift over a covering sheet, or the sheet's own
    // composer stands on the words saying what Esc will do to it.
    keylineEl.style.bottom = `calc(${panelCovers() ? generalRow.offsetHeight + 14 : 14}px + var(--lf-safe-bottom))`;
    // Beside the page, the thread panel owns the right strip all the way to its foot. The
    // line starts at the window's left, so cap its room at that strip rather than letting a
    // long computed hint cross into the general comment box. A covering panel is handled by
    // the lift above and leaves the line the window's full width.
    keylineEl.style.setProperty(
      "--lf-keyline-right",
      (panelBeside ? commentsEdge.width() : 0) + "px",
    );
    // One line stands over two scroll regions, so one measurement is what they both
    // reserve — off the rendered line rather than stated as a number, which is what
    // keeps it true when the line's face or its padding moves.
    const clear = keylineEl.offsetHeight + 20 + "px";
    // The document's, taken as the chrome container's own box rather than as padding on
    // body: body's padding comes out of the box the room is measured from (stateRoom), so
    // writing it here made this function a writer of the box it reads, and every page that
    // watched that box — three do — was one change in the line's height from a
    // ResizeObserver loop on the window's error channel. CLAUDE.md's "The one writer may not
    // write the box the layout is measured from" carries the whole of it. The container is
    // in the flow, holds nothing but out-of-flow chrome, and is watched by nobody, so what
    // it takes is room the document has and no measurement's business.
    chromeRoot.style.paddingBottom = clear;
    // A tray's list is the page's other scroll region, in the corner the line is
    // written into, so it reserves the same room — and states it twice, because it reaches
    // the bottom two ways that take their room from different places. A wheel to the end
    // reads the padding. A walk's own scroll reads none of it: scroll-padding is what a
    // scroll-into-view stops short of, and without it the last row's clearance is however
    // far Chrome happens to overshoot, which is a fact about row height and not about the
    // line standing there. Stepping the line clear instead was the other answer, and it
    // takes the tray's width off the line's: a busy scope already fills a laptop's, so
    // the room it gives up is chips clipped off the right-hand end.
    reserveListClearance(clear);
    stateRoom();
    syncFloats();
    dockSeats();
  }
  // The room a widget declared wide may take: the document's own content box, less the
  // gutter the column already gives its prose, so a breakout is centred on the column's
  // axis and stops where the page stops.
  //
  // Measured, and measured here, because the panel is the thing no stylesheet can see: it
  // holds whatever of the window the reader has drawn it to while it is open, and no query
  // can ask that, and a rule written against 100vw would also spend the rail a suggestion
  // hangs in and the classic scrollbar this platform doesn't draw. The three of them come
  // off body's own box for free. That box is watched (layoutSizes), so the room is restated
  // whenever it changes shape whatever changed it, for the same reason the floats are
  // placed again.
  //
  // The gutter is read off the column rather than stated, since 24px is theme.css's number
  // and a second copy here would be a release behind it. Below the column's own width the
  // two coincide exactly, so the rule that spends this is a no-op on a narrow window rather
  // than a case anyone has to write.
  //
  // The strips the chrome holds are the part of that box which isn't settled when this
  // runs: each is handed over as motion, so body's margins are still the old ones for the
  // length of the transition and the box in front of us is neither the width the page has
  // nor the one it is going to. Both readings are wrong, in opposite directions and at
  // different prices, so the room takes whichever of the two is smaller and the page never
  // owes room it hasn't got. Both sides, because both yield one: the tray panel's margin
  // eases exactly as the thread panel's does, and reading it off the box alone left every
  // exhibit a tray's width too wide for the fifth of a second the tray took to arrive.
  //
  // The two readings are compared rather than added, which is the same arithmetic done in
  // whole pixels. Subtracting the margin the box has already taken from the strip it is
  // going to take says the same thing and says it in two number systems at once: a client
  // box is an integer and a transitioning margin is not, so their sum flickered a pixel
  // either way on every frame of a slide — and a property every wide exhibit is laid out
  // from cannot flicker, because each flicker is a relayout inside the observation that
  // asked for it. Opening, that is the width being arrived at, stated at once: the strip
  // is being taken away, and an exhibit that waited out the slide would spend it hanging
  // over the panel with a sideways scrollbar underneath. Closing, it is the width in front
  // of us: the strip is coming back, and an exhibit that took it before the page had it
  // scrolled sideways for a fifth of a second every time the panel was dismissed — which
  // is what the suggestion sweep caught, on a window narrow enough for the returning strip
  // to matter. What is given back is picked up as it is given: the box is watched, so every
  // frame of the slide is a reading of it, and the growth lands the frame the room is real.
  function stateRoom() {
    const main = document.querySelector("main");
    if (!main) return;
    const body = getComputedStyle(document.body);
    const column = getComputedStyle(main);
    // The gutter body reserves for its own scrollbar, which the window does not know about
    // and the box in front of us has already given up. One reading (scrolling.js), because
    // the veto above owes the same number and a second spelling of it here would be true by
    // inspection rather than by construction.
    const room =
      Math.min(
        document.body.clientWidth,
        document.documentElement.clientWidth -
          panelStrip() -
          trayStrip() -
          scrollerGutter(),
      ) -
      parseFloat(body.paddingLeft) -
      parseFloat(body.paddingRight) -
      parseFloat(column.paddingLeft) -
      parseFloat(column.paddingRight);
    document.documentElement.style.setProperty(
      "--lf-room",
      Math.max(0, Math.floor(room)) + "px",
    );
  }
  // The floats live in the document, and syncLayout is where its box changes shape — the
  // panel takes or returns its strip, a resize moves every rect, the composer's own
  // textarea grows under typing — so whatever float is up is placed again against the
  // new geometry: the composer from its own marks (a detached one re-clamps where it
  // stands), the button from the live selection where one still stands, and by
  // re-clamping alone where none does. Skipping this leaves a float placed at a wide
  // window's edge overhanging the box a panel then narrows, and an absolute child past
  // body's client box is sideways-scrollable overflow: the document panned 328px left
  // under a trackpad, with the composer standing on the panel that had displaced it.
  function syncFloats() {
    if (composerIsOpen()) {
      const box = composer.getBoundingClientRect();
      placeComposer(box.left, box.top);
    }
    if (syncReactLayout()) return;
    refreshFab();
  }
  function setPanel(open) {
    if (open && currentTray()) showTray(null);
    // Closing while focus is inside would drop it on body, the user's place
    // lost silently; it lands on the one control that reopens what just closed.
    if (!open && panel.contains(document.activeElement))
      toggleBtn.focus({ preventScroll: true });
    panelOpen = open;
    // Twice, the two readers being on opposite sides of the chrome's own scope: the class
    // shows the panel, from a rule inside it, and the attribute is what the page yields its
    // strip to, from a rule outside. A document-level rule naming .lf-panel would be a name
    // a page could coin and take the strip with, which is the leak
    // test_a_coined_class_cannot_reach_the_chromes_rules pins, so the posture is stated on
    // body, beside data-lf-cramped.
    panel.classList.toggle("open", open);
    document.body.toggleAttribute("data-lf-panel", open);
    toggleBtn.setAttribute("aria-expanded", String(open));
    // Both of the page's answers to the panel are made here rather than left to the
    // observation, and for the same reason at each: the strip the idioms hang in is body's
    // own padding, which the observation's writer may not touch, and the chrome's posture
    // over a covering sheet follows an open that moves body's box by nothing at all — the
    // sheet stands over the page, so there is no observation to deliver.
    stateStrip();
    syncLayout();
    readerStore.set(PANEL_KEY, open ? "1" : "0");
    if (open) {
      renderPanel();
      syncGeneral(); // a restored draft has to reach the Send button's disabled state
    }
    paintHere();
    // The panel is one of the two surfaces the hover reads, so its arriving or going away
    // is the pointer moving even when the pointer has not: closing it with the keyboard,
    // from a hand resting on a card, took the card out from under the pointer and left the
    // page lit about a comment with no panel to explain it. The open half came free through
    // renderPanel; this is the half that has no render.
    refreshHover();
  }
  toggleBtn.onclick = () => setPanel(!panelOpen);
  addEventListener("resize", () => {
    closeReactions();
    pageShifted();
  });
  // field-sizing and every other rendered-size change feed the one geometry writer —
  // the key line included, whose height is the room the chrome reserves under it.
  const layoutSizes = new ResizeObserver(syncLayout);
  // The page's own box, which is what the room is measured from and what the floats hang
  // in. Watched rather than derived, because an enumeration of the occasions the box moves
  // fails twice over. It cannot be complete: the room followed such a list once — the
  // panel, the window, the one call at the end of upgrade — and a widget that took a margin
  // any other way got no restatement at all. And each entry on it is read at a moment
  // somebody chose, which the panel's strip breaks by being motion: read where the slide
  // began and again where it was expected to end, a slide the reader interrupted was
  // answered at neither. Watching is every frame of it, the last frame included, and the
  // window comes with them — body is the window's own height and width here, so a `resize`
  // listener beside this would be one fact arriving twice. Nothing this observer calls may
  // write this box, which is what the key line's reservation being a flow box and the
  // panel's strip being the cascade's are both about.
  layoutSizes.observe(document.body);
  layoutSizes.observe(generalRow);
  layoutSizes.observe(keylineEl);
  // The composer grows under typing (field-sizing), and a box placed above its passage
  // grows downward, back over the mark it was moved off — so its own resize re-places it.
  layoutSizes.observe(composer);

  return { inPanel, panelCovers, panelIsOpen, setPanel, stateStrip, syncLayout };
}
