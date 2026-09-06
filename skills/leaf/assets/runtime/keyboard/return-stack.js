/* The return stack: what a keyboard entry owes the reader on the way back out.

   A press that takes the reader in pushes one layer. Escape pops one. The way out is
   therefore as deep as the way in, and the reader walks it back without having counted:
   three presses in, three Escapes out, each giving up the press that earned it.

   A command that enters a temporary surface declares one `returnFrame`. The dispatcher
   captures the reader's exact focus or reading block before it runs, and pushes the frame
   only after the declared layer is active. Escape closes that frame and restores the
   captured place. The command may reveal containing chrome and focus its destination in
   one transaction: `c` from the page opens and focuses the page-comment box, and its one
   Escape closes that whole entry because the panel is the box's container, not a second
   destination the reader requested.

   A frame is active only while its owning surface still stands and the reader remains in
   the layer it entered. A latent filter value or mode flag is not enough: closing a panel
   or leaving a widget must retire its frame so core Escape cannot advertise or mutate
   hidden state elsewhere on the page.

   Two independently requested entries remain two frames. `g T` enters the Threads list;
   `c` from that list enters its page-comment box. Two Escapes return first to the list
   and then to the exact place and workspace `g T` displaced. A filter or other state
   entered inside a surface gets its own frame or its control's own nearer Escape step.
   Never infer the inverse of a keyboard entry from whatever panels happen to be open
   afterwards.

   A bounded mode may instead own its complete entry, nesting, cancellation, and origin
   machine inside the one scope that claims the keyboard while it stands. Help, the `g`
   address window, item selection, page search, and reactions use that form. Such a mode
   does not also push a command frame. What is forbidden is the middle state: opening with
   an ordinary `run`, then asking a shared scene inspection or unrelated outer scope to
   guess what Escape should restore.

   Landing focus in what a press opened is arrival, not a second layer: a tray on its
   first row, the versions menu on a version, the panel on its list, or the comment box
   `c` named. A later command into a different mode is another layer. The reference's
   search box is part of its one complete mode because `HELP` owns the whole keyboard
   while it stands; its letters were never the page's to take back.

   The rule holds for a sequence as much as for a surface, where the stack it is about is
   the reader's rather than the dispatcher's. The address chord arms on `g`. A panel
   mnemonic exchanges that window for its destination, so `g T` leaves the Threads panel
   as one Escape rung. A multi-letter generated hint narrows the visible target map
   instead; Escape removes one typed letter before another Escape closes the chord.

   The return stack records entry history; `rung()` is only the fallback for state reached
   without a registered entry, such as a pointer-opened panel or focus the reader moved by
   ordinary traversal. A keyboard command with `returnFrame` never asks `rung()` to guess
   its inverse. Moving within an entered surface—`t` walking from the Threads list to a
   thread, for example—does not push another frame, so Escape still returns through the
   entry that opened the surface.

   `restoreReturnPlace` restores the exact connected control a command displaced. When the
   reader had no control focused it restores the captured reading block without leaving
   that block as an artificial activation target; if neither survives, it focuses `body`.
   Pointer and ordinary-traversal fallbacks use `rung` and `letGo` for that last case.
   `body` has a tab stop because a short page may not become focusable from overflow
   alone. Focus rather than blur hands Space, PageDown, arrows, Home, and End back to the
   page's actual scroll box. `letGo` also runs synchronously during module evaluation so a
   fresh page accepts native scrolling before asynchronous upgrade, without stealing focus
   from a control the reader reaches during that upgrade. */
import { word } from "./bindings.js";
import { focusDestination } from "../widget-elements.js";
import { focused, paintHere } from "./scopes.js";
import { readingBlock } from "../version.js";

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

// The stack itself. Commands declare their second half as `returnFrame`; the dispatcher
// is the only code that captures and pushes it, which keeps one entry one frame and one
// successful Escape one pop, instead of asking the resulting scene to guess how it arose.
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
export function invoke(row, binding, run, suppliedOrigin = null) {
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

export function current() {
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

export const RETURN = {
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
