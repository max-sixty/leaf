/* The layer stack: what stands over the page, and what each entry owes the reader on the
   way back out.

   One ordered list holds every layer standing over the page, oldest at the bottom. A
   popover or a modal dialog pushes an entry as it opens, and a keyboard command that
   enters a temporary surface pushes a return frame. Both are entries on the same stack,
   so their order against each other is recorded when it happens rather than inferred
   from focus ancestry and open state at every read.

   An entry carrying a `root` is a native layer, `popover` or `modal` by its `kind`. An
   entry carrying `does` is a return frame: the descriptor its command declared, the
   origin the dispatcher captured, and the guard that retires it. A command that opened a
   native layer adopts that layer's entry instead of pushing a second one, so `g V` leaves
   one entry that is both the versions popover and the route back out of it. A native
   layer stands while the browser holds it open, whatever the frame it carries says: a
   frame whose guard has gone stops answering Escape without surrendering the popover's
   ownership of the keyboard.

   A layer may open through a prototype method or through declarative popover activation,
   and a popover need not move focus into itself, so every opener declares its own
   opening: the `showModal` and `showPopover` patches, and `beforetoggle` and `toggle` at
   the document and at each declared shadow boundary. `beforetoggle` makes a declarative
   opening visible synchronously to the command that caused it; `toggle` follows the
   completed native transition, and carries an opening whose earlier declarations this
   module was not yet listening for. An opening arrives once, so a declaration naming a
   layer the stack already holds leaves its entry where the arrival put it, however many
   more times that same opening is declared. Dismissal stays each layer's own `popover`
   or `closedby` value. A
   popover opened declaratively inside a shadow root nobody staged fires a `toggle` this
   module cannot hear, so it never reaches the stack; `shadowStage` is the declared route
   for a widget's shadow tree.

   Every read prunes first, and an entry whose surface no longer stands is removed
   wherever it sits, so a dialog closed by script beneath a re-shown popover cannot linger
   as a false floor. The exception is an entry under an active modal: `showModal` hides
   the auto popovers beneath it and the command reference re-shows the ones it displaced,
   so those entries wait with their frames intact rather than retiring. The modal marks
   them suspended as it is pushed, and only a suspended or standing entry is lifted when
   its node reopens. `current()` is the top entry when it carries a live frame and nothing
   otherwise, which is the whole suspension rule: a frame is unavailable because something
   stands above it, not because of an order comparison.

   A covering auxiliary surface is not an entry. It takes modal semantics without entering
   the browser's top layer, and a frame entered while its panel stood beside the page has
   to survive a resize into the covering posture and back. The dispatcher reads that
   surface as the floor when no modal entry stands; this stack never sees it.

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
   and then to the exact place and auxiliary chrome state `g T` displaced. A filter or other state
   entered inside a surface gets its own frame or its control's own nearer Escape step.
   Never infer the inverse of a keyboard entry from whatever panels happen to be open
   afterwards.

   A bounded interaction may instead own its complete entry, nesting, cancellation, and origin
   machine inside the one scope that claims the keyboard while it stands. The shortcut
   command reference, the `g`
   Go-to sequence, target chooser, page search, and reactions use that form. Such an interaction
   does not also push a command frame. What is forbidden is the middle state: opening with
   an ordinary `run`, then asking a shared scene inspection or unrelated outer scope to
   guess what Escape should restore.

   Landing focus in what a press opened is arrival, not a second layer: a tray on its
   first row, the versions menu on a version, the panel on its list, or the comment box
   `c` named. A later command into a different interaction is another layer. The command
   reference's search box is part of its one complete search context because
   `COMMAND_REFERENCE_SCOPE` owns the whole keyboard
   while it stands; its letters were never the page's to take back.

   The rule holds for a sequence as much as for a surface, where the stack it is about is
   the reader's rather than the dispatcher's. The Go-to sequence arms on `g`. A panel
   mnemonic exchanges that window for its destination, so `g T` leaves the Threads panel
   as one Escape rung. A multi-letter generated hint narrows the visible target map
   instead; Escape removes one typed letter before another Escape closes the sequence.

   The stack records entry history; `rung()` is only the fallback for chrome state reached
   without a registered entry, such as a pointer-opened panel. A keyboard command with
   `returnFrame` never asks `rung()` to guess its inverse.

   Standing — holding a destination inside a layer: a card in the list, an Ask or a
   heading on the page — is one rung of its own, however the reader got there. The page's
   STANDING scope lets go of it onto the floor of the layer they are in, the list or the
   body, and that step is inner: it stands ahead of every frame, because standing is the
   newest thing the reader did with a Tab, a hint, or a pointer. A press that stood them
   there instead records itself as a frame, and a frame holds the standing unless it
   declares `standing: false`, so it answers in the stack's order: `t` from the list
   pushes one frame for the whole walk, a second `t` made standing on a thread pushes
   nothing, `t` then `w` unwinds the narrowing before the walk, and `a` opening the panel
   for an Ask closes the panel in the one Escape that undoes the one press. A frame says
   false when its press stood the reader nowhere: `g T` and the trays land on a floor or
   a chrome row, and `w` moves nobody. `heldStanding` is that reading, and a `standing`
   that reads focus retires with it, as `a`'s does once the reader Tabs off its Ask.

   `restoreReturnPlace` restores the exact connected control a command displaced. When the
   reader had no control focused it restores the captured reading block without leaving
   that block as an artificial activation target; if neither survives, it focuses `body`.
   Pointer and ordinary-traversal fallbacks use `rung` and `letGo` for that last case.
   `body` has a tab stop because a short page may not become focusable from overflow
   alone. Focus rather than blur hands Space, PageDown, arrows, Home, and End back to the
   page's actual scroll box. `letGo` also runs synchronously during module evaluation so a
   fresh page accepts native scrolling before asynchronous upgrade, without stealing focus
   from a control the reader reaches during that upgrade.

   A pointer press that opens a layer is a command too, and enters through `invoke` with
   the place it displaced: the Threads toggle, a margin marker or its unfolded option
   row, a page mark, its note. A pointer moves focus onto what it pressed before the
   click arrives, so that place is read at pointerdown and handed out by `pressOrigin`; a
   keyboard activation's click finds no press in flight and reads focus at the click,
   which is the control the reader stood on. The Escape that closes a clicked-open panel
   or conversation view therefore hands back the reader's place before the click — the
   page, for a reader who was reading — and never the control the click happened to
   focus. A close by pointer — the view's ×, the panel's Close — is not that way out: the
   pointer is already on the surface that is closing, and focus lands on the surviving
   control that reopens it. */
import { word } from "./bindings.js";
import { focused } from "./scopes.js";
import { focusDestination } from "../focus.js";
import { retainReaderIntent } from "../reader-intent.js";
import { repaint } from "../repaint.js";
import { under } from "../shadow.js";

export function restoreReturnPlace({ control, reading }) {
  const landed = () => {
    if (control.isConnected) focusDestination(control);
    return control.matches(":focus");
  };
  if (control) {
    if (landed()) return;
    // Reconciliation may replace a control in the same task, and a paint the close asked
    // for may still hold it hidden — a widened list shows its cards on its next paint.
    // That first paint is asynchronous, so give that exact node one frame before
    // conceding. A control that is then gone or hidden is so for good — the layer it
    // stood in closed under the press this frame records, as the conversation view does
    // when the toggle carries its thread into the panel — and the place is the block the
    // reader was reading, which every origin carries beside its control. A control that
    // is there to see and still refused focus keeps the one retry and nothing more:
    // taking the reader somewhere else over it would be a second guess. Neither happens
    // to a reader who has moved on inside that frame: their next press is the newer word.
    const mayLand = retainReaderIntent();
    requestAnimationFrame(() => {
      if (!mayLand() || landed()) return;
      if (!control.isConnected || !control.checkVisibility())
        restoreReturnPlace({ control: null, reading });
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

// The place a press displaced (see the header). `mountPressOrigin` is wired once by the
// keyboard controller with the same capture the dispatcher uses for a key's origin.
//
// Whether a click had a press behind it is the click's own fact: a keyboard or scripted
// activation carries `detail` 0, and it forgets whatever press came before it, in the
// capture phase, ahead of every door. So a press that became no click — a right-click, a
// drag that ended elsewhere — never lends its place to the Enter that follows, and no
// timer has to win a race against the reader's next key to say so: a key pressed straight
// after a click reaches the page before a timeout queued at that click's release does. A
// click that did have a press always follows its own pointerdown, which has already
// replaced the record, so nothing else needs clearing.
let capturePlace = null;
let pressed = null;
export function mountPressOrigin(capture) {
  capturePlace = capture;
  document.addEventListener(
    "pointerdown",
    () => {
      pressed = { control: focused() };
    },
    true,
  );
  document.addEventListener(
    "click",
    (event) => {
      if (!event.detail) pressed = null;
    },
    true,
  );
}
export function pressOrigin() {
  if (!capturePlace)
    throw new Error("leaf: pressOrigin read before the keyboard mounted");
  return pressed ? capturePlace(pressed.control) : capturePlace();
}

// The stack itself. Commands declare their second half as `returnFrame`; the dispatcher
// is the only code that captures and pushes it, which keeps one entry one frame and one
// successful Escape one pop, instead of asking the resulting scene to guess how it arose.
const entries = [];
const watchedRoots = new WeakSet();

const held = (node) =>
  Boolean(node?.isConnected) && node.matches(":popover-open, dialog:modal");

// Top down, so the newest modal is known before the entries it covers are judged. An
// entry seen standing sheds its suspension mark: the mark is for the gap between a modal
// hiding a surface and that surface's return, and an opening after this one starts fresh.
function prune() {
  let covered = false;
  for (let index = entries.length - 1; index >= 0; index -= 1) {
    const entry = entries[index];
    if (entry.active()) {
      entry.suspended = false;
      covered ||= entry.kind === "modal";
      continue;
    }
    if (!covered) entries.splice(index, 1);
  }
}

// An opening that names a node already on the stack keeps that entry, frame and all, when
// the entry is standing or a modal suspended it: the command reference re-shows the
// popovers its modal displaced, and the way back out of one is the way the reader entered
// it, not a fresh layer with no history. Lifting a suspended entry before the prune keeps
// that history across the moment between the modal's close and the popover's return, when
// neither stands. An entry that simply closed, by light dismissal or by script, is not
// lifted: the prune retires it and the reopening starts a fresh entry, so a stale frame
// cannot restore an origin the reader never asked to return to.
//
// A modal marks what it covers as it is pushed, before the native call hides the auto
// popovers beneath it, so the mark is set by the cause rather than by whichever read
// happens to run while the modal stands. The mark stays through the return: one opening is
// declared more than once — by the patched method before the native call, by `beforetoggle`
// during it, and by `toggle` once the native transition completes — and a later declaration
// finds the entry lifted but not yet open.
//
// A standing entry is left alone wherever it sits, and not merely where it is already on
// top. `toggle` is queued rather than synchronous, so a command entered from the layer can
// push its return frame in the gap before that last declaration lands; lifting the layer
// there made it the newest thing on the stack, and the reader's Escape dismissed the
// surface they were standing in instead of handing back the place the command displaced.
export function pushNativeLayer(node, kind) {
  const at = entries.findIndex((entry) => entry.root === node);
  const standing = at < 0 ? null : entries[at];
  if (standing?.active()) return;
  const lifted = standing?.suspended ? standing : null;
  if (lifted) {
    entries.splice(at, 1);
    lifted.kind = kind;
  }
  prune();
  if (kind === "modal") for (const entry of entries) entry.suspended = true;
  entries.push(
    lifted ?? { root: node, kind, active: () => held(node), suspended: false },
  );
}

export function watchLayers(root) {
  if (watchedRoots.has(root)) return;
  watchedRoots.add(root);
  const opened = (event) => {
    if (event.newState === "open" && event.target?.matches?.("[popover]"))
      pushNativeLayer(event.target, "popover");
  };
  root.addEventListener("beforetoggle", opened, true);
  root.addEventListener("toggle", opened, true);
}

watchLayers(document);

// The layers the browser is holding, bottom to top. A suspended entry is not one of them:
// its surface is hidden under a modal, so no scope is standing inside it.
export function nativeLayers() {
  prune();
  return entries.filter((entry) => entry.root && entry.active());
}

// Modal owners close pre-existing popovers before establishing a new floor.
export const openPopovers = () =>
  nativeLayers()
    .filter((entry) => entry.kind === "popover")
    .map((entry) => entry.root);

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
  if (!["undefined", "boolean", "function"].includes(typeof frame.standing))
    throw new TypeError(
      `leaf: ${row.id} must return standing as a boolean or a function from returnFrame`,
    );
  if (!["undefined", "boolean"].includes(typeof frame.ownEntry))
    throw new TypeError(
      `leaf: ${row.id} must return ownEntry as a boolean from returnFrame`,
    );
  if (!["undefined", "object", "function"].includes(typeof frame.surface))
    throw new TypeError(
      `leaf: ${row.id} must return surface as an element or a function from returnFrame`,
    );
  return frame;
}

// The caller captures the origin before the command runs. Evaluate the frame before the
// run too, because its descriptor may preserve pre-entry auxiliary chrome state; publish it only
// after the command has really entered the layer. A liveness guard that changed during
// the command therefore cannot leave a phantom frame behind. A command whose entry lands
// asynchronously — the Ask walk opens the panel and reveals its destination across
// several awaits — says so by returning its promise, and its frame is judged when that
// settles, which is the first moment the layer it declared is either standing or not.
export function invoke(row, binding, run, suppliedOrigin = null) {
  const frame = descriptorFor(row, binding);
  const origin = frame ? suppliedOrigin : null;
  // Read before the run, like the origin: what already answers Escape is older than this
  // press, whatever it goes on to open.
  const older = frame?.surface === undefined ? null : escapeCensus();
  const before = new Set(entries);
  const result = run();
  // What the run itself pushed, read now: a settle that lands later must not adopt a
  // layer something else opened in the meantime.
  const pushed = entries.at(-1);
  const settle = () => {
    prune();
    if (!frame?.active()) return;
    const top = entries.at(-1);
    // One gesture, one entry: a command that opened a native layer is that layer's way
    // out, so it takes over the entry its own run pushed rather than stacking a second
    // rung the reader never asked for. A frame whose life is not the layer's — the
    // thread walk outlives the conversation view it opened when it walks on to a thread
    // seated on the page — says `ownEntry` and stands above the layer as its own.
    if (
      top &&
      top === pushed &&
      top.root &&
      !top.does &&
      !before.has(top) &&
      !frame.ownEntry
    )
      Object.assign(top, frame, {
        origin,
        older,
        active: top.active,
        holds: frame.active,
      });
    else entries.push({ ...frame, origin, older, holds: frame.active });
  };
  if (frame && typeof result?.then === "function")
    result.then(
      () => {
        settle();
        repaint();
      },
      () => {},
    );
  else settle();
  return result;
}

export function current() {
  prune();
  const top = entries.at(-1);
  return top?.does && top.holds() ? top : null;
}

// Whether a live frame holds what the reader is standing on. A frame does unless it says
// `standing: false`: the press that pushed it is what stood the reader where they are —
// the `t` walk on a card, `a` on an Ask it opened the panel for, a widget command in the
// layer it opened — so the scene's own "let go" stands down and Escape goes back through
// that press instead. `g T` says false because its arrival is the list, the panel's own
// floor, and what the reader then stands on in that panel is theirs to let go of first.
export function heldStanding() {
  prune();
  return entries.some(
    (entry) => entry.does && word(entry.standing) !== false && entry.holds(),
  );
}

// Whether an Escape step rooted at `root` takes off something newer than the current
// frame. A frame that stood the reader nowhere says which surface its press entered —
// the panel, a tray — and what the reader has since put on outside that surface came
// after it without a frame of its own: a selection, the page composer a click opened, a
// margin cluster they unfolded, a mode. Those unwind first. Since, and not merely
// outside: a target captured before `g T` is older than the panel, and the one Escape
// still closes the panel over it. Unframed state records no time of its own, so the
// stack takes a census of the steps already answering Escape as each such press is made
// (`mountEscapeCensus`, installed by the dispatcher, which is the one that can name
// them), and a step in that census is not newer. A step inside the surface is the
// frame's own to order (its `close` takes an inner layer off and says false), and a
// frame that names no surface, or holds the standing, yields to nothing.
let escapeCensus = () => new Set();
export function mountEscapeCensus(read) {
  escapeCensus = read;
}
export function outsideCurrentFrame(root, steps) {
  const frame = current();
  if (!frame || heldStanding()) return false;
  const surface = word(frame.surface);
  if (!surface || under(root, surface)) return false;
  return steps.some((step) => !frame.older?.has(step));
}

function back() {
  const frame = current();
  if (!frame) return false;
  // A layer may have a deeper, non-command state of its own. Thread and diff filters,
  // for example, clear a live query first and deliberately retain the entry frame.
  const replacement = frame.close();
  if (replacement === false) {
    repaint();
    return true;
  }
  const at = entries.lastIndexOf(frame);
  if (at >= 0) entries.length = at;
  restoreReturnPlace(
    replacement instanceof Element
      ? { ...frame.origin, control: replacement }
      : (frame.origin ?? { control: null, reading: null }),
  );
  repaint();
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
      // A frame may keep its Escape route while yielding the compact line to the action
      // that advances work inside the entered surface.
      lineWhen: () => word(current()?.lineWhen) !== false,
      promoteEscape: () => word(current()?.promoteEscape) !== false,
      runFromCommandReference: false,
      run: back,
    },
  ],
};
