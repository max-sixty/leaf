/* Open, close, and toggle the thread panel. The panel must be shown before
 * synchronous thread reconciliation: hidden-surface geometry is zero. Opening
 * preserves the invoker's focus beside it unless a keyboard activation requests entry.
 * A close by pointer hands focus to the surviving toggle
 * when focus was inside. Layout receives no surface commands, and refreshThread is
 * supplied by the application so this owner never imports a presenter.
 *
 * This owner declares the panel's Escape ladder, which is the way out of a thread in
 * it: narrowing unwinds before the panel closes. Closing the panel lands the user on
 * the document. Leaving text entry belongs to thread/landing.js. */
import { letGo } from "./focus.js";
import { pageRung } from "./keyboard/register.js";
import { slide } from "./motion.js";
import { retainUserIntent } from "./user-intent.js";
import { pressIsKeyboardActivation } from "./pointer.js";
import { closestAcross } from "./passages.js";
import { declareSide } from "./standing-target.js";

export function createThreadPanelController({
  auxiliarySurfaces,
  elements: { panel, toggleBtn, threadsBox, inPanel: panelFocusIsInside },
  key = "threads",
  narrowing,
  threadAtStanding,
  placedAt,
  showThread,
  refreshThread,
  closeReactionMode,
  closePreview,
  syncGeneral,
}) {
  const stopSide = declareSide((node) => {
    const listed = panel.contains(node)
      ? closestAcross(node, ".lf-thread[data-id]")
      : null;
    return listed ? (placedAt(listed.dataset.id)?.place ?? null) : null;
  });
  const panelIsOpen = () => auxiliarySurfaces.selectedSurface() === panel;
  function setPanel(open, options) {
    if (open || panelIsOpen()) auxiliarySurfaces.select(open ? key : null, options);
  }
  let viewRequest = 0;
  async function showView({ status, waiting, thread, signal } = {}) {
    const request = ++viewRequest;
    const intent = retainUserIntent({
      available: () => request === viewRequest && !signal.aborted && panel.isConnected,
      fallback: threadsBox,
    });
    intent.handoff(() => setPanel(true));
    await narrowing.select({ status, waiting });
    if (!intent() || !panelIsOpen()) return false;
    return thread ? Boolean(await showThread(thread, { focus: false, intent })) : true;
  }

  function paintPanel(open, phase) {
    panel.classList.toggle("open", open);
    toggleBtn.setAttribute("aria-expanded", String(open));
    if (open) {
      // The visible scaffold precedes reconciliation, whose anchor pass measures it.
      if (phase === "gesture") slide(panel, "right", "in");
      refreshThread();
      syncGeneral(); // a restored draft has to reach the Send button's disabled state
    } else {
      ++viewRequest;
      // The selected surface closes at once so it cannot answer the next page key.
    }
    if (open) closePreview?.();
  }
  const stopSurface = auxiliarySurfaces.registerAuxiliarySurface({
    key,
    surface: panel,
    scroller: () => threadsBox,
    // The panel stands over the right of the page, and the page beside it stays live: a
    // user presses the marks and passages its threads are about while it is open. It
    // takes the covering boundary only where it leaves less than a usable page.
    beside: true,
    landing: () => threadsBox,
    // Closing while focus is inside would drop it on body, the user's place lost
    // silently; it lands on the one control that reopens what just closed, which is where
    // the pointer already is. The Escape step below lands the user on the page instead.
    opener: () => toggleBtn,
    show: ({ phase }) => paintPanel(true, phase),
    hide: () => paintPanel(false),
  });
  let mounted = false;
  let pressedInlineThread = null;
  const rememberInlineThread = () => {
    pressedInlineThread = threadAtStanding();
  };
  const toggle = (event) => {
    const pressed = pressIsKeyboardActivation(event) ? null : pressedInlineThread;
    pressedInlineThread = null;
    if (panelIsOpen()) {
      setPanel(false);
      return;
    }
    const inlineThread = pressed ?? threadAtStanding();
    if (inlineThread) showThread(inlineThread, { focus: "thread" });
    else setPanel(true, { focus: pressIsKeyboardActivation(event) });
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
          title: "show all",
          description: "Show every thread again",
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
          title: "close threads",
          description: "Close the thread panel",
          lineWhen: yieldsToSearch(),
          out: () => setPanel(false, { land: letGo }),
        }
      : null,
  );

  function dispose() {
    stopSide();
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
