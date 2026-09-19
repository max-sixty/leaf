/* Open, close, and toggle the thread panel. The panel must be shown before
 * synchronous conversation reconciliation: hidden-dialog geometry is zero. Opening
 * preserves the invoker's focus. A press on the toggle is a command like `g T`: it
 * enters the layer stack with the place the reader held before the press, so the
 * Escape that closes the panel hands that place back — the page, for a reader who
 * clicked — rather than the toggle the click happened to focus. A close by pointer
 * hands focus to the surviving toggle when it was inside.
 * Layout receives no surface commands, and refreshConversation is supplied by the
 * application so this owner never imports a presenter.
 *
 * This owner also declares what Escape takes off the panel, layer by layer, for a reader
 * who got here without a registered entry — a Tab into the list, or a panel that was open
 * when the page arrived. A narrowing is a layer of the panel the way a tray is a layer of
 * the page: the reader put it on, and the list in front of them is not the whole of the
 * conversation until it comes off, so it unwinds first and from wherever they are
 * standing. The find box binds the same step for itself, being the one place the reader
 * can see what they are backing out of. */
import { inPanel as panelFocusIsInside } from "./conversation/panel-elements.js";
import {
  narrowed,
  narrowingIntent,
  threadSearchActive,
} from "./conversation/narrowing.js";
import { invoke, pressOrigin } from "./keyboard/layer-stack.js";
import { pageRung } from "./keyboard/register.js";

export const THREAD_PANEL_KEY = "lf-thread-panel-open";

// Visibility is application state, while the dialog, class, and body attribute are its
// rendering. Construct this reading before layout so every consumer can receive the same
// query without recovering state from those rendered effects. Only setPanel receives the
// writer.
export function createPanelVisibility() {
  let open = false;
  return {
    panelIsOpen: () => open,
    setPanelOpen: (next) => (open = next),
  };
}

export function createThreadPanelController({
  visibility: { panelIsOpen, setPanelOpen },
  layout: { moveContentFrame, syncLayout },
  elements: { panel, toggleBtn },
  hideTray,
  widen,
  activeInlineThread,
  showThread,
  refreshConversation,
  closeReactionMode,
  closePreview,
  syncGeneral,
  refreshHover,
  rememberOpen,
  modality,
  repaint,
}) {
  // Opening a <dialog> runs the browser's dialog focusing steps whichever way it is opened,
  // so the invoker has to be given its focus back: raising the panel is not a request to
  // leave where the reader was standing, and the toggle that lost it would otherwise hold
  // aria-expanded with no ring on it and hand the reader's next Space to a button they
  // never chose. A reader who asked to go in says so with the press that takes them —
  // `g T` focuses the list and `c` focuses its requested box — and setPanel's own handoff
  // is the other thing that moves them.
  function showPanelLayer() {
    // Both a comment destination and Threads navigation may ask for a panel that is already
    // showing. Nothing to redo, and the focus below would otherwise fire against a reader
    // already standing inside.
    if (panel.open) return;
    const invoker = document.activeElement;
    panel.show();
    if (invoker?.isConnected && !panel.contains(invoker))
      invoker.focus({ preventScroll: true });
  }
  function setPanel(open, { remember = true } = {}) {
    if (open) hideTray({ remember });
    else modality.sync(false);
    // Closing while focus is inside would drop it on body, the user's place lost
    // silently; it lands on the one control that reopens what just closed. A close that
    // pops a return frame then restores the frame's own origin over this.
    if (!open && panel.contains(document.activeElement))
      toggleBtn.focus({ preventScroll: true });
    // Twice, the two readers being on opposite sides of the chrome's own scope: the class
    // shows the panel, from a rule inside it, and the attribute is what the page yields its
    // strip to, from a rule outside. A document-level rule naming .lf-thread-panel would be a name
    // a page could coin and take the strip with, which is the leak
    // test_a_coined_class_cannot_reach_the_chromes_rules pins, so the posture is stated on
    // body, where page CSS can see it without naming private chrome.
    setPanelOpen(open);
    panel.classList.toggle("open", open);
    moveContentFrame(() => {
      if (open) document.body.dataset.lfAuxiliarySurface = "threads";
      else delete document.body.dataset.lfAuxiliarySurface;
    });
    toggleBtn.setAttribute("aria-expanded", String(open));
    if (open) {
      // The layer before what goes in it. The panel is a dialog, and a dialog nobody has
      // shown yet is display:none, so anything rendered into it measures zero — and
      // refreshConversation is where the anchor pass runs for the threads it draws. A mark hangs
      // on the boxes its element shows through (shownParts), so a widget an agent sent in
      // a reply resolved to an element with no box, took no mark, and left the thread
      // still open in the panel pointing at nothing on either side.
      showPanelLayer();
      refreshConversation();
      syncGeneral(); // a restored draft has to reach the Send button's disabled state
      modality.sync(true);
    } else if (panel.open) panel.close();
    syncLayout();
    if (open) closePreview();
    if (remember) rememberOpen(open);
    repaint();
    // The panel is one of the two surfaces the hover reads, so its arriving or going away
    // is the pointer moving even when the pointer has not: closing it with the keyboard,
    // from a hand resting on a card, took the card out from under the pointer and left the
    // page lit about a comment with no panel to explain it. The open half comes free from
    // the conversation paint, which reads :hover once the list it drew has laid out
    // (thread-list.js's postPaint); this is the half that has no render.
    refreshHover();
  }
  // The frame of a press that opened the panel, one shape for every door: the toggle,
  // `g T`, a page mark whose thread has no place on the page. `carried` is the thread the
  // press stood the reader on, if it did.
  //
  // A narrowing the reader put on inside the panel is the newer layer, by a chip they
  // clicked or a `w` whose own frame has already gone, so the frame's close takes that
  // off first and stays for the next press (`back` reads the false), and its words say
  // which of the two the press will do; then the panel closes. The rungs below take the
  // same two steps for a panel no press opened. The frame names the panel as the surface
  // it entered, so what the reader has since put on out on the page unwinds before it.
  //
  // Only a narrowing put on since the press is that newer layer. One that stood on the
  // list before the press, or that the arrival itself chose so its thread would show, is
  // part of what the press opened, and the one Escape still undoes the one press. So the
  // frame keeps the narrowing as the press left it, read on the stack's first look after
  // the run, and compares by identity, the way the narrowing's own holders do.
  //
  // Opening the list stands the reader nowhere; opening to a thread stands them on its
  // card, for as long as they stay on it — a Tab to another card is a standing of their
  // own, theirs to let go of first.
  const panelFrame = ({
    carried = null,
    does = "Close the thread panel",
    line = "close threads",
  } = {}) => {
    let entered;
    const narrowedSince = () => narrowed() && narrowingIntent() !== entered;
    return {
      active: () => {
        entered ??= narrowingIntent();
        return panelIsOpen();
      },
      close: () => {
        if (narrowedSince() && widen()) return false;
        setPanel(false);
      },
      does: () => (narrowedSince() ? "Show every thread again" : does),
      line: () => (narrowedSince() ? "show all" : line),
      surface: panel,
      standing: () =>
        carried !== null &&
        panel.querySelector(".lf-thread:focus-within")?.dataset.id === carried,
    };
  };
  function mountThreadPanel() {
    let pressedInlineThread = null;
    let opensTo = null;
    const TOGGLE = {
      id: "threads.toggle",
      returnFrame: () => panelFrame({ carried: opensTo }),
    };
    toggleBtn.addEventListener("pointerdown", () => {
      pressedInlineThread = activeInlineThread()?.dataset.thread ?? null;
    });
    toggleBtn.addEventListener("pointercancel", () => {
      pressedInlineThread = null;
    });
    toggleBtn.addEventListener("pointerup", () => {
      setTimeout(() => (pressedInlineThread = null));
    });
    toggleBtn.onclick = () => {
      if (panelIsOpen()) {
        setPanel(false);
        return;
      }
      const inlineThread = pressedInlineThread ?? activeInlineThread()?.dataset.thread;
      pressedInlineThread = null;
      opensTo = inlineThread ?? null;
      invoke(
        TOGGLE,
        null,
        () => (opensTo ? showThread(opensTo, { focus: "thread" }) : setPanel(true)),
        pressOrigin(),
      );
    };
    addEventListener("resize", closeReactionMode);
  }

  // Search repeat is the useful contextual hint after Enter accepts the first result, so
  // both steps yield the compact line there. Escape remains live and stays in the complete
  // reference without occupying that slot. Both are rooted at the panel, so they survive
  // the width at which it covers the page and becomes the floor.
  const yieldsToSearch = () =>
    !threadSearchActive() || !panelFocusIsInside(panelIsOpen);
  pageRung("narrowing", () =>
    panelIsOpen() && narrowed()
      ? {
          root: panel,
          says: "show all",
          does: "Show every thread again",
          lineWhen: yieldsToSearch(),
          out: (...args) => widen(...args),
        }
      : null,
  );
  // Last of the panel's layers, and the one that leaves the chrome. A panel a press
  // opened, by key or by pointer, has a frame that hands back the place the press
  // displaced; this rung is for the panel no press opened — open on arrival, or entered
  // by Tab — and closing it lands the reader on the control that closes it, deliberately
  // (setPanel says why).
  pageRung("panel", () =>
    panelIsOpen()
      ? {
          root: panel,
          says: "close threads",
          does: "Close the thread panel",
          lineWhen: yieldsToSearch(),
          out: () => setPanel(false),
        }
      : null,
  );

  return { setPanel, panelFrame, mountThreadPanel };
}
