/* This module owns the return stack: the place a keyboard entry displaced, one frame
 * per entry, and the Escape that pops it. */
import { word } from "./bindings.js";
import { focusDestination } from "../widget-elements.js";

export function captureReturnPlace({ focused, readingBlock }) {
  const control = focused();
  return control && control !== document.body
    ? { control, reading: null }
    : { control: null, reading: readingBlock() };
}

export function restoreReturnPlace({ control, reading }) {
  if (control) {
    if (control.isConnected) focusDestination(control);
    // Reconciliation may replace a control in the same task. Its first paint is
    // asynchronous, so give that exact node one frame to reconnect before conceding.
    if (!control.isConnected || !control.matches(":focus"))
      requestAnimationFrame(() => {
        if (control.isConnected) focusDestination(control);
      });
    return;
  }
  if (reading?.isConnected) {
    focusDestination(reading);
    reading.blur();
    return;
  }
  document.body.focus({ preventScroll: true });
}

// A keyboard entry is not travel: it temporarily puts another surface in front of the
// reader, and Escape owes them the exact place and workspace state the entry displaced.
// Commands declare that second half as `returnFrame`; the dispatcher is the only code
// that captures and pushes it. Keeping the stack here makes one entry one frame and one
// successful Escape one pop, instead of asking the resulting scene to guess how it arose.
export function createReturnStack({ focused, paintHere, readingBlock }) {
  const frames = [];

  function descriptorFor(row, binding) {
    if (!row.returnFrame) return null;
    const frame = row.returnFrame(binding);
    if (frame == null) return null;
    if (
      !frame ||
      typeof frame.active !== "function" ||
      typeof frame.close !== "function" ||
      !frame.does ||
      !frame.line
    )
      throw new TypeError(
        `leaf: ${row.id} must return active, close, does, and line from returnFrame`,
      );
    return frame;
  }

  // Capture before the command runs; publish only after it has really entered the layer.
  // A liveness guard that changed during the command therefore cannot leave a phantom
  // frame behind.
  function invoke(row, binding, run, suppliedOrigin = null) {
    const frame = descriptorFor(row, binding);
    const origin = frame
      ? (suppliedOrigin ?? captureReturnPlace({ focused, readingBlock }))
      : null;
    const result = run();
    prune();
    if (frame?.active()) frames.push({ ...frame, origin });
    return result;
  }

  function prune() {
    while (frames.length && !frames.at(-1).active()) frames.pop();
  }

  function current() {
    prune();
    return frames.at(-1) ?? null;
  }

  function back() {
    const frame = current();
    if (!frame) return false;
    // A layer may have a deeper, non-command state of its own. Thread and diff filters,
    // for example, clear a live query first and deliberately retain the entry frame.
    const replacement = frame.close();
    if (replacement === false) {
      paintHere();
      return true;
    }
    frames.pop();
    restoreReturnPlace(
      replacement instanceof Element
        ? { ...frame.origin, control: replacement }
        : frame.origin,
    );
    paintHere();
    return true;
  }

  const RETURN = {
    title: "After entering a surface",
    when: () => Boolean(current()),
    at: () => Boolean(current()),
    rows: [
      {
        id: "navigation.return",
        keys: ["Escape"],
        does: () => word(current()?.does),
        line: () => word(current()?.line),
        runFromReference: false,
        run: back,
      },
    ],
  };

  return { RETURN, invoke, current };
}
