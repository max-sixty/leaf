/* The banner toolbar owns the complete generated control run.
 *
 * Contributors register one stable control with an explicit rank and seat.
 * A compound control also names its retained focus target.
 * This synchronous light-DOM Lit owner is then the only code that decides inventory,
 * order, presence, row-versus-overflow placement, and the overflow door's state. The
 * native controls are retained islands: their own owners keep commands, words, and
 * local state while this owner retains the same nodes in its two Lit lists.
 *
 * Three seats partition the run, and geometry never changes the partition:
 *
 * - `row`: Approval and Threads, the page's standing reading loop.
 * - `menu`: every secondary action, in one stable seat behind More.
 * - `gesture`: the next step of something the user is doing right now, such as
 *   commenting on the words a touch just selected, or a finger's way out of the mode it
 *   stands in. It exists only while that gesture or mode holds it, and it is the one
 *   thing the user came to the banner for, so it stands on the row in the reading
 *   loop's place until the gesture ends. The row has no
 *   room to seat both beside More on a 320px phone, and a step hidden behind More is
 *   two presses on a door nothing points to. For the same reason one contributor's
 *   steps stand at a time, and the higher rank is the nearer gesture: words selected
 *   inside a mode or a search are what the user is doing now, and the mode's steps
 *   return once the selection goes.
 */
import { html, render, repeat } from "../vendor/browser-runtime.js";
import { el } from "./widget-elements.js";
import { repaint } from "./repaint.js";
import { deepFocus, focusDestination, readCaret, releaseFocus } from "./focus.js";
import { selectEnds } from "./passages.js";

const EMPTY = Object.freeze([]);

export const BANNER_CONTROL_RANK = Object.freeze({
  session: 10,
  preview: 20,
  layer: 30,
  leaves: 40,
  latest: 50,
  asks: 60,
  map: 70,
  // The page's commands a finger reaches here rather than by key (touch-controls.js),
  // among themselves in the shortcut line's order.
  commands: 75,
  blanket: 80,
  versions: 90,
  approval: 100,
  threads: 110,
  // The way out of the mode or picker the user stands in, under a finger.
  steps: 120,
  commentSelection: 130,
});

export const bannerActions = el("div", "lf-banner-actions");
export const overflowMenu = el("div", "lf-ui lf-banner-menu");
overflowMenu.setAttribute("popover", "auto");
overflowMenu.setAttribute("role", "group");
overflowMenu.setAttribute("aria-label", "More page controls");

const controls = new Map();
let sequence = 0;
let row = EMPTY;
let menu = EMPTY;

const ordered = () =>
  [...controls.values()].sort(
    (left, right) => left.rank - right.rank || left.sequence - right.sequence,
  );
const onOffer = (entry) => entry.present && (!entry.conditional || entry.offered);
// A gesture step displaces the reading loop only while it is on the row itself, and the
// nearest gesture displaces the others.
const nearestGesture = () =>
  Math.max(
    ...row
      .filter((entry) => entry.seat === "gesture" && onOffer(entry))
      .map((e) => e.rank),
  );
const visible = (entry) => {
  if (!onOffer(entry)) return false;
  if (entry.seat === "row") return nearestGesture() === -Infinity;
  return entry.seat !== "gesture" || entry.rank === nearestGesture();
};

// The door is part of the row's template, so Lit writes its state only where it moved.
function rowTemplate() {
  const open = overflowMenu.matches(":popover-open");
  const news = menu.some((entry) => entry.urgent && visible(entry));
  const name = news ? "More page controls, new" : "More page controls";
  // Keep the native invoker standing until its open popover has closed. A semantic
  // update can retire the last visible item while the user is inside it; closing then
  // lets paint remove the empty door.
  return html`
    ${repeat(
      row,
      (entry) => entry.key,
      (entry) => entry.control,
    )}
    <button
      class="lf-btn lf-banner-more"
      type="button"
      aria-expanded=${String(open)}
      aria-label=${name}
      title=${name}
      ?data-lf-news=${news}
      ?hidden=${!open && !menu.some(visible)}
    >
      ⋯
    </button>
  `;
}

function menuTemplate() {
  return html`${repeat(
    menu,
    (entry) => entry.key,
    (entry) => entry.control,
  )}`;
}

render(rowTemplate(), bannerActions);
render(menuTemplate(), overflowMenu);

const overflowBtn = bannerActions.querySelector(".lf-banner-more");
overflowBtn.popoverTargetElement = overflowMenu;
overflowMenu.lfInvoker = overflowBtn;

// More temporarily borrows the reader's focus. Context-preserving commands return
// that browser checkpoint before acting; it never becomes a remembered page target.
let opener = null;
function holdOpener(node = deepFocus()) {
  if (node === overflowBtn || overflowMenu.contains(node)) return;
  const selection = getSelection();
  opener = {
    node,
    caret: readCaret(node),
    ends:
      selection?.rangeCount && !selection.isCollapsed
        ? [
            [selection.anchorNode, selection.anchorOffset],
            [selection.focusNode, selection.focusOffset],
          ]
        : null,
  };
}
overflowBtn.addEventListener("pointerdown", () => holdOpener());
document.addEventListener("focusout", (event) => {
  if (event.relatedTarget === overflowBtn) holdOpener(event.composedPath()[0]);
});
document.addEventListener("focusin", (event) => {
  if (event.target !== overflowBtn && !overflowMenu.contains(event.target))
    opener = null;
});
export function bannerStanding() {
  const at = deepFocus();
  return at === overflowBtn || overflowMenu.contains(at) ? opener : null;
}
export function restoreBannerStanding(held) {
  opener = null;
  if (held?.node?.isConnected && held.node !== document.body)
    focusDestination(held.node, held.caret);
  else releaseFocus();
  if (held?.ends?.every(([node]) => node.isConnected)) selectEnds(...held.ends);
}

function paintControl(entry) {
  entry.control.classList.toggle("lf-news-shown", entry.conditional && entry.offered);
  // These are paint only. The owner's entry is the value read by layout and door
  // decisions; neither class nor style is read back as authority.
  const displayed = visible(entry);
  entry.control.style.display = displayed ? "" : "none";
  entry.control.style.visibility = visible(entry) ? "" : "hidden";
}

function paint() {
  render(rowTemplate(), bannerActions);
  render(menuTemplate(), overflowMenu);
  for (const entry of controls.values()) paintControl(entry);
}

const focusable = (entry) =>
  visible(entry) &&
  entry.focusTarget.tabIndex >= 0 &&
  !entry.focusTarget.matches(":disabled, [aria-disabled='true']") &&
  !entry.control.closest("[inert]") &&
  entry.control.checkVisibility();
overflowMenu.addEventListener("toggle", (event) => {
  const open = event.newState === "open";
  render(rowTemplate(), bannerActions);
  if (open && document.activeElement === overflowBtn)
    menu.find(focusable)?.focusTarget.focus();
  if (!open) opener = null;
  repaint();
});

function seatControls() {
  const run = ordered();
  row = run.filter((entry) => entry.seat !== "menu");
  menu = run.filter((entry) => entry.seat === "menu");
}

function replaceEntry(prior, next) {
  controls.set(next.control, next);
  row = row.map((entry) => (entry === prior ? next : entry));
  menu = menu.map((entry) => (entry === prior ? next : entry));
}

/** Register one internal banner contribution and synchronously seat its native node. */
export function registerBannerControl({
  key,
  control,
  focusTarget = control,
  rank,
  seat = "menu",
  conditional = false,
  present = true,
  offered = !conditional,
  urgent = false,
}) {
  if (
    !key ||
    !(control instanceof Element) ||
    !Number.isFinite(rank) ||
    !["row", "menu", "gesture"].includes(seat)
  )
    throw new TypeError(
      "A banner control needs a key, native control, numeric rank, and row, menu, or gesture seat",
    );
  const byKey = [...controls.values()].find((entry) => entry.key === key);
  if (byKey && byKey.control !== control)
    throw new TypeError(`Banner control key ${key} is already registered`);
  const prior = controls.get(control);
  if (prior) return prior.control;
  controls.set(
    control,
    Object.freeze({
      key,
      control,
      focusTarget,
      rank,
      sequence: sequence++,
      seat,
      conditional: Boolean(conditional),
      present: Boolean(present),
      offered: Boolean(offered),
      urgent: Boolean(urgent),
    }),
  );
  seatControls();
  paint();
  return control;
}

/** Show or hide one retained contribution without changing its registered identity. */
export const showBannerControl = (control, shown) =>
  showBannerControls([[control, shown]]);

/**
 * Show or hide several retained contributions, as `[control, shown]` pairs, in one
 * paint. Which controls stand on the row depends on every contribution at once (a
 * gesture step displaces the reading loop), so a contributor that moves several says
 * so in one call: moved one at a time, a step leaving and the next arriving would put
 * the reading loop back and take it away again in between.
 */
export function showBannerControls(changes) {
  const moved = [];
  for (const [control, shown] of changes) {
    const prior = controls.get(control);
    if (!prior) throw new TypeError("Banner control is not registered");
    if (prior.present === Boolean(shown)) continue;
    moved.push({
      prior,
      entry: Object.freeze({ ...prior, present: Boolean(shown) }),
      heldFocus: document.activeElement === prior.focusTarget,
      wasInMenu: menu.includes(prior),
    });
  }
  if (!moved.length) return;
  const loopFocus = row.find(
    (candidate) =>
      candidate.seat !== "menu" && document.activeElement === candidate.focusTarget,
  );
  for (const { prior, entry } of moved) replaceEntry(prior, entry);
  paint();
  const removed = moved.find(({ entry, heldFocus }) => heldFocus && !entry.present);
  if (removed) focusAfterRemoval(removed.entry, removed.wasInMenu);
  // The step takes the place of the control focus stood on, so focus takes it too.
  else if (loopFocus && !visible(loopFocus))
    moved
      .find(({ entry }) => entry.present)
      ?.entry.focusTarget.focus({ preventScroll: true });
}

export function showNews(control, on) {
  let entry = controls.get(control);
  if (!entry) throw new TypeError("Banner news control is not registered");
  on = Boolean(on);
  if (entry.conditional && entry.offered === on) return;
  const focused = document.activeElement === entry.focusTarget;
  const wasInMenu = menu.includes(entry);
  const prior = entry;
  entry = Object.freeze({
    ...entry,
    conditional: true,
    offered: on,
  });
  replaceEntry(prior, entry);
  paint();
  if (focused && !on) {
    focusAfterRemoval(entry, wasInMenu);
  }
}

function focusAfterRemoval(entry, wasInMenu) {
  const run = wasInMenu ? menu : row;
  const at = Math.max(
    0,
    run.findIndex((candidate) => candidate === entry),
  );
  const next = [...run.slice(at), ...run.slice(0, at).reverse()].find(focusable);
  (next?.focusTarget ?? overflowBtn).focus({ preventScroll: true });
}

// A secondary control stands behind a door this owner holds shut, so it
// answers the layer's shared disclosure route: `reveal` walks the ancestors of what a
// caller means to show, and this is the only one that can open for a menu control.
overflowMenu.addEventListener("lf-reveal", () => {
  if (!overflowMenu.matches(":popover-open")) overflowMenu.showPopover();
});

// The node a user can actually put focus on to reach this control: the control
// itself while it stands on the row, and otherwise the More door holding it. A menu
// control fails `checkVisibility()` inside a shut popover, and `focus()` on it is a
// no-op, so a caller that hands the user somewhere has to ask this rather than the
// control. Null means the toolbar offers no way in, which happens only off the banner.
export function bannerControlDoor(control) {
  if (control.isConnected && control.checkVisibility()) return control;
  const menu = control.closest(".lf-banner-menu");
  return menu?.lfInvoker?.checkVisibility() ? menu.lfInvoker : null;
}

// Escape from a layer that opens from a banner control lands on that control, its parent
// (runtime/keyboard/AGENTS.md, "Escape unwinds the hierarchy"). A control behind More is
// reached as its door reaches it: More opens from the door, so More's own Escape then
// hands the user back to the door, and the user stands on the control.
export function returnToBannerControl(control) {
  if (overflowMenu.contains(control) && !overflowMenu.matches(":popover-open")) {
    overflowBtn.focus({ preventScroll: true });
    overflowMenu.showPopover();
  }
  control.focus({ preventScroll: true });
}

export function dismissBannerControls() {
  if (overflowMenu.matches(":popover-open")) overflowMenu.hidePopover();
}
