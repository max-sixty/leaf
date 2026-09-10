/* Where the reader is standing, split around chrome layout so geometry consumers read
   the content painted in the same frame. repaint.js owns the fixed sequence and leaf.js
   supplies these phases at boot. */
// Construct the fixed phases from narrow painters. No phase imports a feature's
// commands or schedules the full presenter while drawing its own geometry.
export function createStanding({
  markHere,
  paintStanding,
  renderLine,
  paintAddresses,
  paintTargets,
  paintCoreControls,
  paintInputs,
}) {
  // Content whose resulting boxes chrome layout must measure.
  function paintStandingContent() {
    markHere();
    paintStanding();
    // The shortcut bar is geometry for every address and target painted around it. Render
    // its new words first, then let chrome-layout.js place that resulting
    // box before any consumer reads it. ResizeObserver remains the door for font, window,
    // and other size changes; state-driven content changes complete in this frame rather
    // than leaving placement and hints one observer frame behind.
    renderLine();
  }

  // Controls and geometry that depend on the laid-out content above.
  function paintStandingGeometry() {
    // The chips are where the reader can go, beside the ring saying where they are and the
    // line saying what the next press does — one paint, because a chip repainted by its
    // own door alone went stale on the door it did not
    // have: a poll that retires an Ask moves the list under an armed window, and only the
    // panel's own render was calling the chip pass.
    paintAddresses();
    paintTargets();
    paintCoreControls();
    paintInputs();
  }

  return { paintStandingContent, paintStandingGeometry };
}
