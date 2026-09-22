/* The banner shelf owns the complete generated control run.
 *
 * Contributors register one stable control with an explicit rank and seat.
 * A compound control also names its retained focus target.
 * This synchronous light-DOM Lit owner is then the only code that decides inventory,
 * order, presence, row-versus-overflow placement, and the overflow door's state. The
 * native controls are retained islands: their own owners keep commands, words, and
 * local state while this owner retains the same nodes in its two Lit lists. Approval
 * and Threads form the page's reading loop on the row; every secondary action has one
 * stable seat behind More. Geometry never changes that partition.
 */
import { html, render, repeat } from "../vendor/browser-runtime.js";
import { el } from "./widget-elements.js";
import { repaint } from "./repaint.js";

const EMPTY = Object.freeze([]);

export const BANNER_CONTROL_RANK = Object.freeze({
  session: 10,
  preview: 20,
  layer: 30,
  select: 35,
  leaves: 40,
  latest: 50,
  asks: 60,
  map: 70,
  blanket: 80,
  versions: 90,
  approval: 100,
  threads: 110,
  cancelSelection: 120,
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
const visible = (entry) => entry.present && (!entry.conditional || entry.offered);

function rowTemplate() {
  return html`
    <button
      class="lf-btn lf-banner-more"
      type="button"
      aria-expanded="false"
      aria-label="More page controls"
      title="More page controls"
      hidden
    >
      ⋯
    </button>
    ${repeat(
      row,
      (entry) => entry.key,
      (entry) => entry.control,
    )}
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

export const overflowBtn = bannerActions.querySelector(".lf-banner-more");
overflowBtn.popoverTargetElement = overflowMenu;
overflowMenu.lfInvoker = overflowBtn;

function paintControl(entry) {
  entry.control.classList.toggle("lf-news-shown", entry.conditional && entry.offered);
  // These are paint only. The owner's entry is the value read by layout and door
  // decisions; neither class nor style is read back as authority.
  const displayed = visible(entry);
  entry.control.style.display = displayed ? "" : "none";
  entry.control.style.visibility = visible(entry) ? "" : "hidden";
}

function paintDoor() {
  const hasMenu = menu.some(visible);
  const news = menu.some((entry) => entry.urgent && visible(entry));
  // Keep the native invoker standing until its open popover has closed. A semantic
  // update can retire the last visible item while the reader is inside it; closing then
  // lets paint remove the empty door.
  overflowBtn.hidden = !hasMenu && !overflowMenu.matches(":popover-open");
  overflowBtn.toggleAttribute("data-lf-news", news);
  const name = news ? "More page controls, new" : "More page controls";
  overflowBtn.setAttribute("aria-label", name);
  overflowBtn.title = name;
}

function paint() {
  render(rowTemplate(), bannerActions);
  render(menuTemplate(), overflowMenu);
  for (const entry of controls.values()) paintControl(entry);
  paintDoor();
}

const focusable = (entry) =>
  visible(entry) &&
  entry.focusTarget.tabIndex >= 0 &&
  !entry.focusTarget.matches(":disabled, [aria-disabled='true']") &&
  !entry.control.closest("[inert]") &&
  entry.control.checkVisibility();
overflowMenu.addEventListener("toggle", (event) => {
  const open = event.newState === "open";
  overflowBtn.setAttribute("aria-expanded", String(open));
  if (open && document.activeElement === overflowBtn)
    menu.find(focusable)?.focusTarget.focus();
  if (!open) paintDoor();
  repaint();
});

function seatControls() {
  const run = ordered();
  row = run.filter((entry) => entry.seat === "row");
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
    !["row", "menu"].includes(seat)
  )
    throw new TypeError(
      "A banner control needs a key, native control, numeric rank, and row or menu seat",
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
export function showBannerControl(control, shown) {
  let entry = controls.get(control);
  if (!entry) throw new TypeError("Banner control is not registered");
  shown = Boolean(shown);
  if (entry.present === shown) return;
  const heldFocus = document.activeElement === entry.focusTarget;
  const wasInMenu = menu.includes(entry);
  const prior = entry;
  entry = Object.freeze({ ...entry, present: shown });
  replaceEntry(prior, entry);
  paint();
  if (heldFocus && !shown) focusAfterRemoval(entry, wasInMenu);
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

// The node a reader can actually put focus on to reach this control: the control
// itself while it stands on the row, and otherwise the More door holding it. A menu
// control fails `checkVisibility()` inside a shut popover, and `focus()` on it is a
// no-op, so a caller that hands the reader somewhere has to ask this rather than the
// control. Null means the shelf offers no way in, which happens only off the banner.
export function bannerControlDoor(control) {
  if (control.isConnected && control.checkVisibility()) return control;
  const menu = control.closest(".lf-banner-menu");
  return menu?.lfInvoker?.checkVisibility() ? menu.lfInvoker : null;
}

export function dismissBannerControls() {
  if (overflowMenu.matches(":popover-open")) overflowMenu.hidePopover();
}
