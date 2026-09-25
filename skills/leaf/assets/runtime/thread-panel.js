/* Open, close, and toggle the thread panel. The panel must be shown before
 * synchronous conversation reconciliation: hidden-dialog geometry is zero. Opening
 * preserves the invoker's focus. A close by pointer hands focus to the surviving toggle
 * when focus was inside. Layout receives no surface commands, and refreshConversation is
 * supplied by the application so this owner never imports a presenter.
 *
 * This owner declares the panel's Escape ladder. Once the user releases a selected
 * thread to the whole panel, narrowing unwinds before the panel closes. Closing the
 * panel lands the user on the document. Thread selection and release belong to
 * keyboard/page.js; leaving text entry belongs to conversation/landing.js. */
import { inPanel as panelFocusIsInside } from "./conversation/panel-elements.js";
import { narrowed, threadSearchActive } from "./conversation/narrowing.js";
import { letGo } from "./focus.js";
import { pageRung } from "./keyboard/register.js";
import { currentAuxiliarySurface } from "./auxiliary-surfaces.js";
import { slide } from "./motion.js";
import { pressIsKeyboardActivation } from "./pointer.js";

export const panelIsOpen = () => currentAuxiliarySurface() === "threads";

export function createThreadPanelController({
  auxiliarySurfaces,
  elements: { panel, toggleBtn, threadsBox },
  widen,
  activeInlineThread,
  showThread,
  refreshConversation,
  closeReactionMode,
  closePreview,
  syncGeneral,
}) {
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
    if (open || panelIsOpen())
      auxiliarySurfaces.select(open ? "threads" : null, options);
  }
  function paintPanel(open, phase) {
    // Closing while focus is inside would drop it on body, the user's place lost
    // silently; it lands on the one control that reopens what just closed, which is where
    // the pointer already is. The Escape step below lands the user on the page instead.
    if (!open && panel.contains(document.activeElement))
      toggleBtn.focus({ preventScroll: true });
    panel.classList.toggle("open", open);
    toggleBtn.setAttribute("aria-expanded", String(open));
    if (open) {
      // The layer before what goes in it. The panel is a dialog, and a dialog nobody has
      // shown yet is display:none, so anything rendered into it measures zero — and
      // refreshConversation is where the anchor pass runs for the threads it draws. A mark hangs
      // on the boxes its element shows through (shownParts), so a widget an agent sent in
      // a reply resolved to an element with no box, took no mark, and left the thread
      // still open in the panel pointing at nothing on either side.
      showPanelLayer();
      if (phase === "gesture") slide(panel, "right", "in");
      refreshConversation();
      syncGeneral(); // a restored draft has to reach the Send button's disabled state
    } else if (panel.open) {
      // Closed at once, with no slide out: the panel is a dialog that the thread list,
      // the walks and placement all read as open while it shows, so a panel still on
      // screen after the press would take the next key the user meant for the page.
      panel.close();
    }
    if (open) closePreview();
  }
  auxiliarySurfaces.registerAuxiliarySurface({
    key: "threads",
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
  function mountThreadPanel() {
    // The press moves focus off the inline thread before its click arrives, so a pointer
    // click reads the thread the press recorded. A keyboard click has no press and reads
    // the thread where it stands.
    let pressedInlineThread = null;
    toggleBtn.addEventListener("pointerdown", () => {
      pressedInlineThread = activeInlineThread()?.dataset.thread ?? null;
    });
    toggleBtn.onclick = (event) => {
      const pressed = pressIsKeyboardActivation(event) ? null : pressedInlineThread;
      pressedInlineThread = null;
      if (panelIsOpen()) {
        setPanel(false);
        return;
      }
      const inlineThread = pressed ?? activeInlineThread()?.dataset.thread;
      if (inlineThread) showThread(inlineThread, { focus: "thread" });
      else setPanel(true);
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
  // Last of the panel's layers, and the one that leaves the chrome. The panel's parent is
  // the document, so that is where this step lands the user — whatever opened the
  // panel, and never the toggle, which is where `setPanel` puts focus first so that a
  // close by pointer has somewhere to leave it.
  pageRung("panel", () =>
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

  return { setPanel, mountThreadPanel };
}
