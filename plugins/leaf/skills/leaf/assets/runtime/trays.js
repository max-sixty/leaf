// The trays' edge, on the left, and everything said above said again for it: the width
// it stands at until the reader moves it, how narrow they may draw it, and the window
// under which a tray covers the page rather than standing beside it. The same bargain at
// the same ratio, because a reader who has learned one edge has learned the other.
//
// 220 is where the tray's own row stops being one. A leaf's row spends 45px before any
// word of the page's — the status dot's 9px, its 8px gap, and the 20px and 8px the row
// and the tray take for padding — and what is left holds a title that ellipsizes rather
// than wrapping, so under this the tray is furniture showing the first syllable of every
// name on it. The asks tray's rows clamp to three lines instead and would go on reading
// further down, which is why the floor is the leaves tray's to set.
const TRAY_W = 300;
const TRAY_MIN = 220;
export const TRAY_COVERING = `(width <= ${TRAY_W * 2}px)`;
// Where the standing width is written, and where the cascade reads it. Named rather than
// spelled, because the stylesheet and the runtime's writer are two ends of one fact and
// a property spelled twice is two facts the day one of them moves.
export const TRAY_PROP = "--lf-tray-w";
// Which trays take their room out of the page rather than lying over it, read by the rule
// that takes the strip and by the runtime for what the page has left — so the two cannot
// disagree about whether the page is yielding one.
//
// The leaves tray is not on the list, and that is not an inconsistency between two twins:
// a leaf's row is a way out of this page and an ask's row is a way around it, so pressing
// an ask's row scrolls the document to the ask and stands you on the control that answers
// it — and a tray lying over the document would be hiding the very thing it just sent you
// to. A 300px tray and a 720px column overlap on any window under about 1320px, which is
// most of them, so this is the common case rather than the narrow one.
const STRIP_TRAYS = ["asks"];
export const STRIP_TRAY_RULE = `body:is(${STRIP_TRAYS.map(
  (tray) => `[data-lf-tray="${tray}"]`,
).join(",")})`;

export const TRAY_KEY = "lf-tray-up";

export function createTrays({
  beforeOpen,
  drawnEdge,
  el,
  keys,
  leavesOffered,
  motion,
  openAsks,
  pagePresented,
  paintKeys,
  PRESS,
  readerStore,
  renderAsks,
  stateStrip,
  syncLayout,
  walkRows,
}) {
  // The rows' own box, one per tray. Collected privately as they are made, because what
  // the layout reserves at the foot of one it reserves at the foot of every one — and a
  // second place to remember that is exactly where the asks tray was left out of it: its
  // walk parked the last row 47px under the key line, on the one tray nothing had ever
  // walked to the end of. Callers state the clearance; this owner decides which lists it
  // reaches and how each one spends it.
  const trayLists = [];
  function trayList(panel) {
    const list = el("div", "lf-tray-list");
    panel.append(list);
    trayLists.push(list);
    return list;
  }
  function reserveListClearance(clear) {
    for (const list of trayLists) {
      list.style.paddingBottom = clear;
      list.style.scrollPaddingBottom = clear;
    }
  }

  const traysEdge = drawnEdge({
    side: "left",
    noun: "tray panel",
    wide: TRAY_W,
    min: TRAY_MIN,
    prop: TRAY_PROP,
    key: "lf-tray-width",
    covering: TRAY_COVERING,
    // A page with no tray to open has no edge to draw, so the reference does not name one.
    when: () => leavesOffered() || asksOffered(),
  });

  // What the page is still waiting on the reader for, and the way to the next one — the
  // same list n/p step and the "?" overlay names, counted here so a reader who
  // has not scrolled that far still knows there is something to answer.
  const asksBtn = el("button", "lf-btn lf-asks", "");
  asksBtn.title = "Show or hide what this page needs your input on";
  // The machine's live leaves and what each is doing: a left panel of rows, each a
  // link opening that page in its own tab, judged by the same `presented` the banner
  // answers with, from the same facts — `others` on /api/state carries them for every
  // live page, and every URL in the list carries only the key this reader already
  // holds, since there is one key for the machine (`host_key`). The current page heads
  // the list as a marked, unlinked row, so the panel reads as the whole machine. A
  // status tray's point is being live, so rows reconcile on every applied state, keyed by URL —
  // the stable identity, since address, port and key all survive a restart — and a
  // status change repaints the row's own dot and words without moving it.
  const othersBtn = el("button", "lf-btn lf-others", "");
  othersBtn.title = "Leaves live on this machine, and what each is doing";
  // A nav, because navigation is what it is and a bare div may not carry the
  // aria-label the card needs (axe: aria-prohibited-attr, serious).
  const othersPanel = el("nav", "lf-ui lf-tray-panel lf-others-panel");
  othersPanel.setAttribute("aria-label", "Leaves on this machine");
  traysEdge.handle(othersPanel, () => othersBtn);
  const leavesList = trayList(othersPanel);
  // A tray of the page's own open asks, on the same edge: one row per thing the page is
  // waiting on the reader for, in the order the page asks them. The list is openAsks() and
  // nothing else, so a widget joins the tray by declaring x-awaits and no row here knows
  // what kind of thing it is standing for.
  const asksPanel = el("nav", "lf-ui lf-tray-panel lf-asks-panel");
  asksPanel.setAttribute("aria-label", "What this page is waiting on you for");
  traysEdge.handle(asksPanel, () => asksBtn);
  const asksList = trayList(asksPanel);

  // The left edge holds one tray at a time. Leaves and asks are the same furniture asking
  // at two scopes — which page needs me, and what this page needs of me — and each has to
  // stand while the reader works, which is the whole reason either is a fixed edge rather
  // than a menu over the page. So which one is up is one fact held in one place. A boolean
  // per tray would be one guarantee written twice, and the two would first disagree on the
  // day a third surface opened one without closing the other; the reader would then have
  // two trays over one edge with the lower one unreachable.
  //
  // Registered rather than listed, for the same reason the widgets are: the toggle, the
  // press, the reload and the Escape rung all read this map, so a third tray joins by
  // registering and none of them names a tray to do its job.
  const trays = new Map();
  // A reader gesture writes through showTray. A reload writes saved intent later through
  // restoreTrays, after registration and the late asks painter have been initialized.
  let trayUp = null;
  const currentTray = () => trayUp;
  const openTray = (key) => trayUp === key;
  function showTray(key) {
    if (trayUp === key) return;
    // Comments and trays are alternate workspaces. Retire the standing one before another
    // opens so layout, focus, and persisted state never have to reconcile two of them.
    if (key) beforeOpen();
    trayUp = key;
    for (const [name, { panel, btn, paint }] of trays) {
      const open = name === key;
      btn.setAttribute("aria-expanded", String(open));
      if (open) {
        // Filled before it is shown, so the tray is its own list from the first frame of
        // the slide rather than a blank card that populates a moment later. The way down
        // is the mirror of it, below: emptied once it is hidden, never before, or the
        // reader watches the list they just closed blank out and an empty card slide away.
        paint?.();
        panel.classList.add("open");
        motion(
          panel,
          [{ transform: "translateX(-100%)" }, { transform: "translateX(0)" }],
          200,
        );
      } else if (panel.classList.contains("open")) {
        // Slid out before hidden, and hidden only if still closed on arrival — a
        // reopen mid-slide leaves the panel standing rather than racing the finish.
        const out = motion(
          panel,
          [{ transform: "translateX(0)" }, { transform: "translateX(-100%)" }],
          160,
        );
        const hide = () => {
          if (trayUp === name) return; // reopened mid-slide; it stays up, list and all
          panel.classList.remove("open");
          paint?.();
        };
        if (out) out.finished.then(hide, () => {});
        else hide();
        if (panel.contains(document.activeElement)) btn.focus();
      }
    }
    // Both of the page's answers to the tray are made here rather than left to the
    // observation, for the reasons setPanel gives at the same two lines: the strip the
    // idioms hang in is body's own padding, which the observation's writer may not touch,
    // and a tray that covers the page moves body's box by nothing at all, so there is no
    // observation to deliver.
    stateStrip();
    syncLayout();
    readerStore.set(TRAY_KEY, key ?? "");
    // Publish the tray this gesture chose so the stylesheet can say what it costs the
    // page's own box.
    if (key) document.body.dataset.lfTray = key;
    else delete document.body.dataset.lfTray;
    paintKeys();
  }
  // Registration only. No tray opens while this factory evaluates: showTray runs from a
  // press, and restoreTrays runs from the entry's restore block after every owner is
  // published.
  function trayIs(key, panel, btn, paint) {
    trays.set(key, { panel, btn, paint });
    btn.onclick = () => showTray(openTray(key) ? null : key);
    btn.setAttribute("aria-expanded", "false");
  }
  trayIs("leaves", othersPanel, othersBtn);
  trayIs("asks", asksPanel, asksBtn, renderAsks);
  const trayNames = Object.freeze([...trays.keys()]);

  // A persisted tray is state-dependent chrome: Asks folds the log and Leaves comes from
  // the first state response. Keep the remembered intent in trayUp, but restore its pixels
  // only once that response has produced the page's presentation. Unlike showTray, this
  // first paint does not animate — it is part of the page arriving, not a reader gesture.
  function restoreTray() {
    if (!trayUp) return;
    const tray = trays.get(trayUp);
    if (!tray) return;
    beforeOpen();
    tray.btn.setAttribute("aria-expanded", "true");
    tray.paint?.();
    tray.panel.classList.add("open");
    document.body.dataset.lfTray = trayUp;
  }
  function restoreTrays() {
    // Remembered tray intent is staged here, after every declaration exists. Its strip is
    // part of the arrival geometry, but its state-dependent rows stay hidden until the first
    // replay presents the page and restoreTray paints them. An already-presented document
    // (an exported or pre-presented DOM) can restore immediately through the same function.
    trayUp = readerStore.get(TRAY_KEY) || null;
    if (trayUp) document.body.dataset.lfTray = trayUp;
    if (pagePresented()) restoreTray();
  }

  // Each tray's one offer: something to show, or the tray already standing — the key that
  // opened it must still close it, and its button must still be pressable. The button's
  // visibility and the key both ask the tray's own predicate, so the two surfaces cannot
  // disagree about whether there is a tray to open. An asks tray of none is the same.
  const asksOffered = () =>
    pagePresented() && (openAsks().length > 0 || openTray("asks"));
  const askRows = () => [...asksPanel.querySelectorAll("button.lf-asks-row")];
  // The asks tray's own walk, the leaves tray's twin: ArrowUp and ArrowDown are the page's
  // scroll everywhere else and the tray's here, and Enter is the platform's, a row being a
  // button — so the scope names what walking does and leaves the press to the button.
  keys(asksPanel, "In the asks tray", [
    {
      keys: ["ArrowUp", "ArrowDown"],
      does: "Walk the asks",
      line: "walk the asks",
      repeat: true,
      run: (binding) => walkRows(askRows(), binding === "ArrowDown" ? 1 : -1),
    },
  ]);

  const trayStrip = () =>
    STRIP_TRAYS.includes(trayUp) && !traysEdge.over.matches ? traysEdge.width() : 0;

  return {
    askRows,
    asksBtn,
    asksList,
    asksOffered,
    asksPanel,
    currentTray,
    leavesList,
    openTray,
    othersBtn,
    othersPanel,
    reserveListClearance,
    restoreTray,
    restoreTrays,
    showTray,
    trayNames,
    traysEdge,
    trayStrip,
  };
}
