/* The banner shelf owns the complete generated control run.
 *
 * Contributors register one stable native control with an explicit rank and policy.
 * This synchronous light-DOM Lit owner is then the only code that decides inventory,
 * order, presence, row-versus-overflow placement, and the overflow door's state. The
 * native controls are retained islands: their own owners keep commands, words, and
 * local state while this owner moves the same nodes between its two Lit lists.
 *
 * Geometry remains mechanical browser state. The owner measures the live row, moves
 * whole controls until it fits, freezes that partition while the disclosure is open,
 * and restores focus after a move. It does not publish application state or join the
 * application presentation transaction.
 */
import { html, render, repeat } from "../vendor/browser-runtime.js";
import { el } from "./widget-elements.js";
import { repaint } from "./repaint.js";

// The final two offered controls stay on the row. They are the page's reading loop at
// the end of the complete run (approval and Threads on sign-off pages; Versions and
// Threads otherwise), matching the shelf's established narrow-layout contract.
const KEPT = 2;
const EMPTY = Object.freeze([]);

export const BANNER_CONTROL_RANK = Object.freeze({
  session: 10,
  preview: 20,
  leaves: 30,
  latest: 40,
  asks: 50,
  map: 60,
  blanket: 70,
  versions: 80,
  approval: 90,
  threads: 100,
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
let folding = false;
let newsFoldQueued = false;
const pendingMeasurements = new Set();

const ordered = () =>
  [...controls.values()].sort(
    (left, right) => left.rank - right.rank || left.sequence - right.sequence,
  );
const visible = (entry) => entry.present && (!entry.conditional || entry.offered);
const occupies = (entry) => visible(entry) || (entry.present && entry.reserved);

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
  const displayed = row.includes(entry) ? occupies(entry) : visible(entry);
  entry.control.style.display = displayed ? "" : "none";
  entry.control.style.visibility = visible(entry) ? "" : "hidden";
}

function paintDoor() {
  const hasMenu = menu.some(occupies);
  const news = menu.some((entry) => entry.urgent && visible(entry));
  // Keep the native invoker standing until its open popover has closed. A semantic
  // update can retire the last visible item while the reader is inside the frozen
  // partition; closing then lets the ordinary fold remove the empty door.
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
  entry.control.tabIndex >= 0 &&
  !entry.control.matches(":disabled, [aria-disabled='true']") &&
  !entry.control.closest("[inert]") &&
  entry.control.checkVisibility();
const canRetainFocus = (entry) =>
  visible(entry) &&
  !entry.control.matches(":disabled") &&
  !entry.control.closest("[inert]") &&
  entry.control.checkVisibility();

overflowMenu.addEventListener("toggle", (event) => {
  const open = event.newState === "open";
  overflowBtn.setAttribute("aria-expanded", String(open));
  if (open && document.activeElement === overflowBtn)
    menu.find(focusable)?.control.focus();
  if (!open) {
    const measurements = [...pendingMeasurements];
    pendingMeasurements.clear();
    if (measurements.length)
      measureBannerControls(() => measurements.forEach((run) => run()));
    else foldShelf();
  }
  repaint();
});

function normalizePartition() {
  const run = ordered();
  const known = new Set(run);
  row = row.filter((entry) => known.has(entry) && !entry.alwaysFolded);
  menu = menu.filter((entry) => known.has(entry));
  const placed = new Set([...row, ...menu]);
  for (const entry of run) {
    if (placed.has(entry)) continue;
    (entry.alwaysFolded ? menu : row).push(entry);
  }
  for (const entry of [...row]) {
    if (!entry.alwaysFolded) continue;
    row = row.filter((candidate) => candidate !== entry);
    menu.push(entry);
  }
  row = run.filter((entry) => row.includes(entry));
  menu = run.filter((entry) => menu.includes(entry));
}

function replaceEntry(prior, next) {
  controls.set(next.control, next);
  row = row.map((entry) => (entry === prior ? next : entry));
  menu = menu.map((entry) => (entry === prior ? next : entry));
  normalizePartition();
}

/** Register one internal banner contribution and synchronously seat its native node. */
export function registerBannerControl({
  key,
  control,
  rank,
  alwaysFolded = false,
  conditional = false,
  present = true,
  offered = !conditional,
  reserved = false,
  urgent = false,
}) {
  if (!key || !(control instanceof Element) || !Number.isFinite(rank))
    throw new TypeError(
      "A banner control needs a key, native control, and numeric rank",
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
      rank,
      sequence: sequence++,
      alwaysFolded: Boolean(alwaysFolded),
      conditional: Boolean(conditional),
      present: Boolean(present),
      offered: Boolean(offered),
      reserved: Boolean(reserved),
      urgent: Boolean(urgent),
    }),
  );
  normalizePartition();
  paint();
  if (bannerActions.isConnected) foldShelf();
  return control;
}

/** Show or hide one retained contribution without changing its registered identity. */
export function showBannerControl(control, shown) {
  let entry = controls.get(control);
  if (!entry) throw new TypeError("Banner control is not registered");
  shown = Boolean(shown);
  if (entry.present === shown) return;
  const heldFocus = document.activeElement === control;
  const wasInMenu = menu.includes(entry);
  const prior = entry;
  entry = Object.freeze({ ...entry, present: shown });
  replaceEntry(prior, entry);
  paint();
  foldShelf();
  if (heldFocus && !shown) focusAfterRemoval(entry, wasInMenu);
}

function queueNewsFold() {
  if (newsFoldQueued) return;
  newsFoldQueued = true;
  queueMicrotask(() => {
    newsFoldQueued = false;
    foldShelf();
  });
}

export function showNews(control, on) {
  let entry = controls.get(control);
  if (!entry) throw new TypeError("Banner news control is not registered");
  on = Boolean(on);
  if (entry.conditional && entry.offered === on && (!on || entry.reserved)) return;
  const focused = document.activeElement === control;
  const wasInMenu = menu.includes(entry);
  const prior = entry;
  entry = Object.freeze({
    ...entry,
    conditional: true,
    offered: on,
    reserved: entry.reserved || on,
  });
  replaceEntry(prior, entry);
  paint();
  queueNewsFold();
  if (focused && !on) {
    focusAfterRemoval(entry, wasInMenu);
  }
}

export function reserveNewsSlot(control) {
  let entry = controls.get(control);
  if (!entry) throw new TypeError("Banner news control is not registered");
  if (entry.reserved) return;
  const prior = entry;
  entry = Object.freeze({ ...entry, reserved: true });
  replaceEntry(prior, entry);
  paint();
}

function focusAfterRemoval(entry, wasInMenu) {
  const run = wasInMenu ? menu : ordered();
  const at = Math.max(
    0,
    run.findIndex((candidate) => candidate === entry),
  );
  const next = [...run.slice(at), ...run.slice(0, at).reverse()].find(focusable);
  (next?.control ?? overflowBtn).focus({ preventScroll: true });
}

function heldShelfFocus() {
  const focused = document.activeElement;
  return focused === overflowBtn || controls.has(focused) ? focused : null;
}

function restoreShelfFocus(focused) {
  if (!focused) return;
  let target = null;
  if (focused === overflowBtn) {
    if (!overflowBtn.hidden && overflowBtn.checkVisibility()) target = overflowBtn;
  } else {
    const entry = controls.get(focused);
    if (entry && canRetainFocus(entry)) target = focused;
    else if (entry && menu.includes(entry) && !overflowBtn.hidden) target = overflowBtn;
  }
  target ??= row.find(focusable)?.control;
  if (target && document.activeElement !== target)
    target.focus({ preventScroll: true });
}

function unfoldShelf() {
  const run = ordered();
  row = run;
  menu = EMPTY;
  paint();
}

/** Measure retained controls on the live row without disturbing an open disclosure. */
export function measureBannerControls(measure) {
  if (typeof measure !== "function")
    throw new TypeError("Banner control measurement needs a function");
  if (overflowMenu.matches(":popover-open")) {
    pendingMeasurements.add(measure);
    return;
  }
  const focused = heldShelfFocus();
  unfoldShelf();
  try {
    measure();
  } finally {
    foldShelfFrom(focused);
  }
}

export function focusBannerControl(control) {
  const menu = control.closest("[popover]");
  if (menu && !menu.matches(":popover-open")) menu.showPopover();
  control.focus({ preventScroll: true });
}

export function dismissBannerControls() {
  if (overflowMenu.matches(":popover-open")) overflowMenu.hidePopover();
}

function foldable() {
  const present = row.filter(occupies);
  return present.slice(0, Math.max(0, present.length - KEPT));
}

function foldShelfFrom(focused) {
  if (folding || overflowMenu.matches(":popover-open") || !bannerActions.isConnected)
    return;
  folding = true;
  try {
    refold(focused);
  } finally {
    folding = false;
  }
}

export function foldShelf() {
  foldShelfFrom(heldShelfFocus());
}

function refold(focused) {
  normalizePartition();
  // Normalization is a state transition too: in particular, unfolding temporarily
  // seats always-folded diagnostics on the row, and refolding must move those retained
  // nodes back before geometry is measured. Keep the two Lit roots in lockstep with
  // the typed partition before either fold loop decides there is no work to do.
  paint();

  // Hand ordinary controls back in reverse fold order without assuming the registered
  // ranks put every permanent-overflow contribution before them. Then take the earliest
  // foldable control until the row fits.
  const giveBack = () => menu.findLast((entry) => !entry.alwaysFolded);
  for (let back = giveBack(); back; back = giveBack()) {
    menu = menu.filter((entry) => entry !== back);
    row.push(back);
    normalizePartition();
    paint();
    if (bannerActions.scrollWidth <= bannerActions.clientWidth) continue;
    row = row.filter((entry) => entry !== back);
    menu.push(back);
    normalizePartition();
    paint();
    break;
  }
  while (bannerActions.scrollWidth > bannerActions.clientWidth) {
    const [first] = foldable();
    if (!first) break;
    row = row.filter((entry) => entry !== first);
    menu.push(first);
    normalizePartition();
    paint();
  }
  paintDoor();
  restoreShelfFocus(focused);
}
