/* Open, close, and toggle the thread panel. The panel must be shown before
 * synchronous thread reconciliation: hidden-dialog geometry is zero. Opening
 * preserves the invoker's focus. A close by pointer hands focus to the surviving toggle
 * when focus was inside. Layout receives no surface commands, and refreshThread is
 * supplied by the application so this owner never imports a presenter.
 *
 * This owner declares the panel's Escape ladder, which is the way out of a thread in
 * it: narrowing unwinds before the panel closes. Closing the panel lands the user on
 * the document. Leaving text entry belongs to thread/landing.js. */
import { handBack, letGo } from "./focus.js";
import { pageRung } from "./keyboard/register.js";
import { slide } from "./motion.js";
import { pressIsKeyboardActivation } from "./pointer.js";

export function createThreadPanelController({
  auxiliarySurfaces,
  elements: { panel, toggleBtn, threadsBox, inPanel: panelFocusIsInside },
  key = "threads",
  narrowing,
  threadHere,
  showThread,
  refreshThread,
  closeReactionMode,
  closePreview,
  syncGeneral,
}) {
  const panelIsOpen = () => auxiliarySurfaces.selectedSurface() === panel;
  // Opening a <dialog> runs the browser's dialog focusing steps whichever way it is opened,
  // so the invoker has to be given its focus back: raising the panel is not a request to
  // leave where the user was standing, and the toggle that lost it would otherwise hold
  // aria-expanded with no ring on it and hand the user's next Space to a button they
  // never chose. A user who asked to go in says so with the press that takes them —
  // `g T` focuses the list and `c` focuses its requested box — and setPanel's own handoff
  // is the other thing that moves them.
  function showPanelLayer() {
    // Both a comment destination and Threads navigation may ask for a panel that is already
    // showing. Nothing to redo, and the focus below would otherwise fire against a user
    // already standing inside.
    if (panel.open) return;
    const invoker = document.activeElement;
    panel.show();
    if (invoker?.isConnected && !panel.contains(invoker))
      invoker.focus({ preventScroll: true });
  }
  function setPanel(open, options) {
    if (open || panelIsOpen()) auxiliarySurfaces.select(open ? key : null, options);
  }
  let viewRequest = 0;
  async function showView({ status, waiting, thread } = {}) {
    const request = ++viewRequest;
    setPanel(true);
    await narrowing.select({ status, waiting });
    if (request !== viewRequest || !panelIsOpen()) return false;
    return thread ? showThread(thread, { focus: false }) : true;
  }

  function paintPanel(open, phase) {
    // Closing while focus is inside would drop it on body, the user's place lost
    // silently; it lands on the one control that reopens what just closed, which is where
    // the pointer already is. The Escape step below lands the user on the page instead.
    if (!open && panel.contains(document.activeElement)) handBack(toggleBtn);
    panel.classList.toggle("open", open);
    toggleBtn.setAttribute("aria-expanded", String(open));
    if (open) {
      // The layer before what goes in it. The panel is a dialog, and a dialog nobody has
      // shown yet is display:none, so anything rendered into it measures zero — and
      // refreshThread is where the anchor pass runs for the threads it draws. A mark hangs
      // on the boxes its element shows through (shownParts), so a widget an agent sent in
      // a reply resolved to an element with no box, took no mark, and left the thread
      // still open in the panel pointing at nothing on either side.
      showPanelLayer();
      if (phase === "gesture") slide(panel, "right", "in");
      refreshThread();
      syncGeneral(); // a restored draft has to reach the Send button's disabled state
    } else if (panel.open) {
      ++viewRequest;
      // Closed at once, with no slide out: the panel is a dialog that the thread list,
      // the walks and placement all read as open while it shows, so a panel still on
      // screen after the press would take the next key the user meant for the page.
      panel.close();
    }
    if (open) closePreview();
  }
  const stopSurface = auxiliarySurfaces.registerAuxiliarySurface({
    key,
    surface: panel,
    scroller: () => threadsBox,
    // The panel stands over the right of the page, and the page beside it stays live: a
    // user presses the marks and passages its threads are about while it is open. It
    // takes the covering boundary only where it leaves less than a usable page.
    beside: true,
    focus: () => threadsBox,
    show: ({ phase }) => paintPanel(true, phase),
    hide: () => paintPanel(false),
  });
  let mounted = false;
  let pressedInlineThread = null;
  const rememberInlineThread = () => {
    pressedInlineThread = threadHere()?.dataset.thread ?? null;
  };
  const toggle = (event) => {
    const pressed = pressIsKeyboardActivation(event) ? null : pressedInlineThread;
    pressedInlineThread = null;
    if (panelIsOpen()) {
      setPanel(false);
      return;
    }
    const inlineThread = pressed ?? threadHere()?.dataset.thread;
    if (inlineThread) showThread(inlineThread, { focus: "thread" });
    else setPanel(true);
  };
  function mountThreadPanel() {
    if (mounted) return;
    mounted = true;
    // The press moves focus off the inline thread before its click arrives, so a pointer
    // click reads the thread the press recorded. A keyboard click has no press and reads
    // the thread where it stands.
    toggleBtn.addEventListener("pointerdown", rememberInlineThread);
    toggleBtn.onclick = toggle;
    addEventListener("resize", closeReactionMode);
  }

  // Search repeat is the useful contextual hint after Enter accepts the first result, so
  // both steps yield the compact line there. Escape remains live and stays in the complete
  // reference without occupying that slot. Both are rooted at the panel, so they survive
  // the width at which it covers the page and becomes the floor.
  const yieldsToSearch = () =>
    !narrowing.threadSearchActive() || !panelFocusIsInside(panelIsOpen);
  const stopNarrowingRung = pageRung("narrowing", () =>
    panelIsOpen() && narrowing.narrowed()
      ? {
          root: panel,
          says: "show all",
          does: "Show every thread again",
          lineWhen: yieldsToSearch(),
          out: () => narrowing.widen(),
        }
      : null,
  );
  // Last of the panel's layers, and the one that leaves the chrome. The panel's parent is
  // the document, so that is where this step lands the user — whatever opened the
  // panel, and never the toggle, which is where `setPanel` puts focus first so that a
  // close by pointer has somewhere to leave it.
  const stopPanelRung = pageRung("panel", () =>
    panelIsOpen()
      ? {
          root: panel,
          says: "close threads",
          does: "Close the thread panel",
          lineWhen: yieldsToSearch(),
          out: () => {
            setPanel(false);
            letGo();
          },
        }
      : null,
  );

  function dispose() {
    if (mounted) {
      toggleBtn.removeEventListener("pointerdown", rememberInlineThread);
      if (toggleBtn.onclick === toggle) toggleBtn.onclick = null;
      globalThis.removeEventListener("resize", closeReactionMode);
      mounted = false;
    }
    stopPanelRung();
    stopNarrowingRung();
    stopSurface?.();
  }
  return { panelIsOpen, setPanel, showView, mountThreadPanel, dispose };
}
