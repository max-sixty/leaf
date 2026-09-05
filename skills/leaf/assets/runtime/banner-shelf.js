// How many addresses stay on the row whatever the width. The last two are the page's
// reading loop — approval and the conversation — and a reader must never open a menu to
// find them. Everything before them is a destination, and a destination is what a menu
// is for.
const KEPT = 2;

export function createBannerShelf({ el, paintHere }) {
  const bannerActions = el("div", "lf-banner-actions");

  // The addresses that do not fit, in one menu, behind one press. They are the row's own
  // nodes moved rather than copied, so a folded address keeps its accessible name, its
  // state paint, its title, its press and its own page key: nothing about it changes
  // except where it stands. That is also why there is no second order to keep in step —
  // the menu's contents followed by the row's are the row's one order, read straight
  // through.
  //
  // A disclosure rather than a menu, which is what it is: the same buttons, in the same
  // order, somewhere else. The version chooser next door really is a menu — a walk over
  // rows that are a list to read down — and says so in its roles. Claiming those roles
  // here would mean giving these controls menuitem semantics for as long as the fold
  // holds them and taking them away again when the window widens, which is the same
  // address describing itself two ways.
  const overflowBtn = el("button", "lf-btn lf-banner-more", "⋯");
  overflowBtn.type = "button";
  overflowBtn.setAttribute("aria-expanded", "false");
  overflowBtn.setAttribute("aria-label", "More page addresses");
  overflowBtn.title = "More page addresses";
  // The row's first child for the page's whole life, shown only once there is something
  // behind it. Standing there rather than being added and removed is what lets a fold
  // hand the reader the door without the door itself having just left the document.
  overflowBtn.hidden = true;
  bannerActions.append(overflowBtn);
  const overflowMenu = el("div", "lf-ui lf-banner-menu");
  overflowMenu.setAttribute("popover", "auto");
  overflowMenu.setAttribute("role", "group");
  overflowMenu.setAttribute("aria-label", "More page addresses");
  // The press is the popover's declared invoker rather than a click handler reading the
  // state, for the reason the version chooser states: a press on a standing auto
  // popover's invoker is a light dismissal *and* a press, so a handler that asks whether
  // the menu is open opens it straight back. The browser knows the two are one gesture.
  overflowBtn.popoverTargetElement = overflowMenu;
  overflowMenu.lfInvoker = overflowBtn;
  overflowMenu.addEventListener("toggle", (event) => {
    const open = event.newState === "open";
    overflowBtn.setAttribute("aria-expanded", String(open));
    // A keyboard opener lands on the first address rather than on the menu's box, and a
    // reader already standing inside is left where they are.
    if (open && !overflowMenu.contains(document.activeElement))
      folded()
        .find((control) => control.getClientRects().length)
        ?.focus();
    // Whatever the row asked for while the menu stood open is asked again now it has not.
    if (!open) foldShelf();
    paintHere();
  });

  // The controls the banner's news arrives as, each present only while it has something
  // to say. What being absent costs differs by where the control stands, so this is one
  // writer stating the whole outcome for both places, per showComposer and showFab.
  //
  // On the row, room a control has once taken is room it keeps for the rest of the page's
  // life. A live root pays nothing for news it may never get. A pinned version is
  // different: falling behind is part of its contract, so it reserves the future chip
  // before publication can move approval or Threads under a reaching pointer.
  //
  // A menu row has no neighbours to hold still for and no width to hold open, so an
  // address with nothing to say is simply not in the menu. That is not a second rule: it
  // is the same rule asked of a place where taking room costs nothing to give back.
  const newsControls = new Set();
  let newsFoldQueued = false;
  function queueNewsFold() {
    if (newsFoldQueued) return;
    newsFoldQueued = true;
    queueMicrotask(() => {
      newsFoldQueued = false;
      foldShelf();
    });
  }
  // The presence those two facts state, read as a value rather than written straight
  // out, so the same rule answers what the control should look like and whether it
  // already looks like that.
  function presence(control) {
    const speaking = control.classList.contains("lf-news-shown");
    const holds = control.parentElement === bannerActions && control.dataset.lfReserved;
    return {
      display: speaking || holds ? "" : "none",
      visibility: speaking ? "" : "hidden",
    };
  }
  function paintPresence(control) {
    const { display, visibility } = presence(control);
    control.style.display = display;
    control.style.visibility = visibility;
  }
  // Whether this reading leaves the row exactly as it found it: the same news, the slot
  // showing it has already reserved, and the presence both of those paint.
  function newsStands(control, on) {
    if (!newsControls.has(control)) return false;
    if (control.classList.contains("lf-news-shown") !== on) return false;
    if (on && !control.dataset.lfReserved) return false;
    const { display, visibility } = presence(control);
    return control.style.display === display && control.style.visibility === visibility;
  }

  function showNews(control, on) {
    on = Boolean(on);
    // Most calls are a poll restating the news the row already carries — a page whose
    // asks are all answered says so on every refresh, once per widget that repaints in
    // it. Folding on that reading measures the row against a set of addresses nothing
    // moved, and a measurement after a write is a forced layout, so the heartbeat's cost
    // grew with the page rather than with what changed on it. A reading that moves
    // nothing therefore stops here; every fact the fold reads is either written below or
    // watched by the mutation observer that follows this row's children.
    if (newsStands(control, on)) return;
    newsControls.add(control);
    // News can arrive while a deferred activation leaves the reader working in this live
    // banner, and a control that settles its own decisions goes away while it still owns
    // focus. Hand the reader to the next standing address rather than dropping them on
    // body. The row packs against its end, so a control arriving or leaving moves only
    // what stands before it: an address the reader is holding keeps its coordinate
    // without anyone spending a scroll to put it back.
    const focused = bannerActions.contains(document.activeElement)
      ? document.activeElement
      : null;
    const siblings = [...bannerActions.children];
    const focusedIndex = siblings.indexOf(control);
    const focusTransfer =
      focused === control && !on
        ? [
            ...siblings.slice(focusedIndex + 1),
            ...siblings.slice(0, focusedIndex).reverse(),
          ].find((candidate) => {
            const style = getComputedStyle(candidate);
            return (
              candidate.getClientRects().length &&
              style.display !== "none" &&
              style.visibility !== "hidden" &&
              !candidate.matches(":disabled, [aria-disabled='true']")
            );
          })
        : null;
    if (on) reserveNewsSlot(control);
    control.classList.toggle("lf-news-shown", on);
    paintPresence(control);
    // One state application can refresh Decisions, blanket answers, Requests, and live
    // leaves in succession. They all change the same row; fold it once after that write
    // batch, against the final words and presence of every address.
    queueNewsFold();
    if (focusTransfer) focusTransfer.focus({ preventScroll: true });
  }

  function reserveNewsSlot(control) {
    control.dataset.lfReserved = "1";
  }

  const folded = () => [...overflowMenu.children];
  // Every address back on the row, for a caller that needs one to have a box. A control
  // measures its own words in its own live face (`reserve`), and inside a shut popover
  // every word measures zero — so the banner's reservations are taken with the whole run
  // standing, and the fold is asked again once they are.
  function unfoldShelf() {
    const back = folded();
    if (!back.length) return;
    overflowBtn.after(...back);
    for (const control of back) if (newsControls.has(control)) paintPresence(control);
    overflowBtn.hidden = true;
  }
  // The addresses this row may fold, in the row's own order: everything before the
  // reading loop at its end.
  function foldable() {
    const run = [...bannerActions.children].filter(
      (control) => control !== overflowBtn,
    );
    return run.slice(0, Math.max(0, run.length - KEPT));
  }

  // What the row keeps and what the menu takes, decided by measuring the row rather than
  // by counting controls or naming a width. The stylesheet caps the row at the room the
  // status sentence's floor leaves; anything past that cap overflows, and overflowing is
  // the whole of the question this asks. So the two facts this rests on are ones the
  // banner already keeps true: each control that rewrites its own words holds room for
  // the widest it may say (the `reserve` calls where the banner is built), and the cap is
  // a share of the row rather than of the sentence currently in it. A count turning over,
  // or a status ageing from "is working" to "last checked in", therefore moves nothing at
  // all.
  //
  // It moves the one address whose place has changed and no others. Emptying the menu and
  // refilling it on every layout pass answers the same question, and takes every node out
  // of the document and puts it back to do it — which blurs whatever the reader was
  // standing on, replays every animation those nodes wear, and re-announces anything live
  // inside them. Room is handed back before it is taken, newest fold first, so a window
  // widening returns addresses in the order a window narrowing took them.
  //
  // Nothing is refolded while the menu stands open. It is a transient reading of the row,
  // and re-deciding its contents under the hands of a reader walking it is a list that
  // changes while being read; closing it asks again.
  let folding = false;
  function foldShelf() {
    if (folding || overflowMenu.matches(":popover-open")) return;
    folding = true;
    try {
      refold();
    } finally {
      folding = false;
    }
  }
  // The row is an open layer. A registry-declared blanket answer joins it when the
  // registry lands, and a project's own address can join it later still; neither knows
  // about the fold, and a row that refolded only when the window moved would seat a new
  // address in a row that no longer has room for it. The fold's own moves are what this
  // must not answer, and it does not try to tell one mutation from another: it compares
  // which addresses are on the row with which ones the last fold decided about, and a
  // fold moving them between the row and the menu leaves that answer alone.
  let seats = 0;
  const runKey = () =>
    [...overflowMenu.children, ...bannerActions.children]
      .map((control) => (control.dataset.lfSeat ||= String(++seats)))
      .sort()
      .join(" ");
  let lastRun = null;
  new MutationObserver(() => {
    if (runKey() !== lastRun) foldShelf();
  }).observe(bannerActions, { childList: true });
  function refold() {
    const focused =
      bannerActions.contains(document.activeElement) ||
      overflowMenu.contains(document.activeElement)
        ? document.activeElement
        : null;
    // The door costs room of its own, so its presence is part of every reading here. It
    // is hidden rather than taken out: a door removed and put back is a node the reader
    // can be standing on leaving the document, which is the loss this whole function is
    // written to avoid.
    const fits = () => {
      overflowBtn.hidden = overflowMenu.children.length === 0;
      return bannerActions.scrollWidth <= bannerActions.clientWidth;
    };
    for (let back = overflowMenu.lastElementChild; back;) {
      overflowBtn.after(back);
      if (newsControls.has(back)) paintPresence(back);
      if (fits()) {
        back = overflowMenu.lastElementChild;
        continue;
      }
      overflowMenu.append(back);
      if (newsControls.has(back)) paintPresence(back);
      fits();
      break;
    }
    while (!fits()) {
      const [first] = foldable();
      // A row whose reading loop alone outgrows it has nothing left to fold. It keeps what
      // it has and clips, which is the honest end of a row two addresses wide in a window
      // narrower than two addresses.
      if (!first) break;
      overflowMenu.append(first);
      if (newsControls.has(first)) paintPresence(first);
    }
    paintDoor();
    lastRun = runKey();
    if (focused?.isConnected && document.activeElement !== focused)
      (overflowMenu.contains(focused) ? overflowBtn : focused).focus({
        preventScroll: true,
      });
  }

  // News behind the door. An address the fold has taken is an address whose arrival the
  // reader cannot see, and the page they are reading having been replaced is exactly the
  // arrival they are owed — so the door says there is something, in ink and in its own
  // name, and the address behind it goes on saying what. State is paint here as it is
  // everywhere else on this row: no metric changes, so nothing beside the door moves for
  // news arriving behind it.
  //
  // Which news is worth a door saying so is the address's own claim (data-lf-urgent), not
  // this module's guess. Every folded address has something to say — that is what a
  // banner address is — and a door lit whenever it holds one is a light that is always
  // on, which says nothing at all.
  function paintDoor() {
    const news = folded().some(
      (control) =>
        control.dataset.lfUrgent && control.classList.contains("lf-news-shown"),
    );
    overflowBtn.toggleAttribute("data-lf-news", news);
    const name = news ? "More page addresses, new" : "More page addresses";
    overflowBtn.setAttribute("aria-label", name);
    overflowBtn.title = name;
  }

  return {
    bannerActions,
    foldShelf,
    overflowBtn,
    overflowMenu,
    reserveNewsSlot,
    showNews,
    unfoldShelf,
  };
}
