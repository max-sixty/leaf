/* Open, close, and toggle the thread workspace. The panel must be shown before
 * synchronous conversation reconciliation: hidden-dialog geometry is zero. Opening
 * preserves the invoker's focus; closing hands focus to the surviving toggle.
 * Layout receives no workspace commands, and refreshConversation is supplied by the
 * application so this owner never imports a presenter. */
export const PANEL_KEY = "lf-panel-open";

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

export function createPanelWorkspace({
  visibility: { panelIsOpen, setPanelOpen },
  layout: { moveShell, syncLayout },
  elements: { panel, toggleBtn },
  hideTray,
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
    // Closing while focus is inside would drop it on body, the user's place
    // lost silently; it lands on the one control that reopens what just closed.
    if (!open && panel.contains(document.activeElement))
      toggleBtn.focus({ preventScroll: true });
    // Twice, the two readers being on opposite sides of the chrome's own scope: the class
    // shows the panel, from a rule inside it, and the attribute is what the page yields its
    // strip to, from a rule outside. A document-level rule naming .lf-panel would be a name
    // a page could coin and take the strip with, which is the leak
    // test_a_coined_class_cannot_reach_the_chromes_rules pins, so the posture is stated on
    // body, where page CSS can see it without naming private chrome.
    setPanelOpen(open);
    panel.classList.toggle("open", open);
    const played = moveShell(() =>
      document.body.toggleAttribute("data-lf-panel", open),
    );
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
    // page lit about a comment with no panel to explain it. The open half came free through
    // refreshConversation; this is the half that has no render.
    refreshHover();
    return played;
  }
  function mountPanelWorkspace() {
    let pressedInlineThread = null;
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
      if (inlineThread) showThread(inlineThread, { focus: "thread" });
      else setPanel(true);
    };
    addEventListener("resize", closeReactionMode);
  }
  return { setPanel, mountPanelWorkspace };
}
