/* One geometry owner for controls and readings that hang in the document margin.

   `margin-layout` places, packs, docks, and measures the complete host and its transient
   control labels. Its rail claim is
   the widest stable contribution seen over a floor of the generated marker's own margin entry,
   and is monotonic for the document's lifetime, so neither settling an action nor taking
   one back shifts the readable column. A first contribution wider than that floor still
   widens the claim once; `reserve` is how a contribution declares that width in advance.
   A temporary contribution registers with `claim: false`: it borrows available RHS room
   and docks the complete host when it cannot fit, without moving the column on first open
   or leaving blank room after close. A stable contribution whose future primary and `…`
   margin entry is wider than its resting one declares that pixel width with `reserve`; the
   claim includes it before the control changes. Below the margin breakpoint the complete
   host docks into flow. Visibility and vertical placement read `shownParts` and
   `shownBox`, not the target's raw client rect: a project may set `display: contents`
   while its rendered descendants remain usable, and a collapsed target has no rendered
   part to offer.

   Every live page may grow a page-edge margin entry — an anchored comment can arrive on one
   made entirely of prose — so the margin projection reserves the rail as it is built and
   never gives it back. The runtime states that reservation as `data-lf-rail` on the root,
   and the cascade spends it there; neither reads what is standing in the margin, because
   a row's placement depends on the strip it would be answering about. A copy takes no
   gestures, so the bake drops the reservation unless a margin contribution survived into the
   file.

   Where a durable margin contribution stands is the same question in every medium, and a file
   cannot dock: the packing pass measured the rail at the width the page was exported at
   and left with the scripts. So under that floor and on paper, where no rail is drawn, a
   copy's remaining margin contributions take the docked shape rather than the absolute seat they
   were exported into, which hangs off the page box. Not the rows that same pass withheld:
   an item whose target is not shown wears `lf-withheld` into the file, and a shape taken
   on the medium's terms would be the only thing standing a record beside a passage the
   file was folding away when exported. Paper later unfolds that passage through CSS, but
   a script-free copy cannot rerun the packing pass, so its serialized `lf-withheld`
   reading remains withheld. Changing that behavior belongs to the live and copied layouts
   together, not to this export override. */
const rows = new Map();
// The horizontal space a row was last docked against. A dock holds while that space and
// the row itself do. The shell's presentation carry is the exception: its moving column
// is transient, so rows keep their answer until the column rests.
// Cleared wherever a row restates itself, since its own size is the other half of the
// answer.
const dockedAgainst = new WeakMap();
const GAP = 4;
let pending = 0;
let observer = null;
let observedColumn = null;
let claimedRail = 0;
let railReserved = false;

const marginColumn = () => document.querySelector("main") || document.body;

const labelRect = (name, left, top, label) => ({
  name,
  rect: {
    left,
    right: left + label.width,
    top,
    bottom: top + label.height,
  },
});

const rectsOverlap = (left, right) =>
  left.left < right.right &&
  left.right > right.left &&
  left.top < right.bottom &&
  left.bottom > right.top;

function placeMarginEntryLabel(control) {
  const label = control.querySelector(":scope > .lf-margin-entry-label");
  if (!label || !control.checkVisibility()) return;
  const marginEntryBox = control.getBoundingClientRect();
  const labelBox = label.getBoundingClientRect();
  const edgeAligned = Math.max(
    4,
    Math.min(marginEntryBox.right - labelBox.width, innerWidth - 4 - labelBox.width),
  );
  const cluster = control.closest(".lf-margin-cluster") ?? control.parentElement;
  const clusterMarginEntries = [
    ...(cluster?.querySelectorAll(".lf-margin-entry") ?? []),
  ]
    .filter((candidate) => candidate.checkVisibility())
    .map((candidate) => candidate.getBoundingClientRect());
  const clusterLeft = Math.min(...clusterMarginEntries.map((box) => box.left));
  const clusterRight = Math.max(...clusterMarginEntries.map((box) => box.right));
  const centered = (marginEntryBox.top + marginEntryBox.bottom - labelBox.height) / 2;
  const candidates = [
    labelRect("below", edgeAligned, marginEntryBox.bottom + 6, labelBox),
    labelRect("above", edgeAligned, marginEntryBox.top - 6 - labelBox.height, labelBox),
    labelRect("after", clusterRight + 6, centered, labelBox),
    labelRect("before", clusterLeft - 6 - labelBox.width, centered, labelBox),
  ];
  const blockers = [
    ...[...document.querySelectorAll(".lf-margin-entry")].filter(
      (candidate) => candidate !== control && candidate.checkVisibility(),
    ),
    ...document.querySelectorAll(".lf-banner, .lf-shortcut-bar"),
  ].map((candidate) => candidate.getBoundingClientRect());
  const fits = ({ rect }) =>
    rect.left >= 4 &&
    rect.right <= innerWidth - 4 &&
    rect.top >= 4 &&
    rect.bottom <= innerHeight - 4;
  const choice =
    candidates.find(
      (candidate) =>
        fits(candidate) &&
        !blockers.some((blocker) => rectsOverlap(candidate.rect, blocker)),
    ) ??
    candidates.find(fits) ??
    candidates[0];
  control.dataset.lfLabelSide = choice.name;
  label.style.setProperty(
    "--lf-label-x",
    `${choice.rect.left - marginEntryBox.left}px`,
  );
  label.style.setProperty("--lf-label-y", `${choice.rect.top - marginEntryBox.top}px`);
}

let labelPlacementFrame = 0;
export function scheduleMarginEntryLabels() {
  if (labelPlacementFrame) return;
  labelPlacementFrame = requestAnimationFrame(() => {
    labelPlacementFrame = 0;
    for (const control of document.querySelectorAll(
      '.lf-margin-entry:is(:hover, :focus-visible, .lf-focus-visible):not([aria-expanded="true"])',
    ))
      placeMarginEntryLabel(control);
  });
}

// Whether the page takes a margin strip at all, as distinct from how wide the strip is.
// The width is `--rail` below and only ever grows; this says the page has taken the
// strip, and once taken it is never given back. Claimed only while something stands in
// it, the strip arrived with the gesture that raised the first margin entry and left again
// with the undo, and each of those moved the readable column under the reader. The
// cascade reads this attribute rather than asking whether a row is standing, because a
// row's own placement depends on the strip and a live question about it would feed the
// reservation back into itself.
export function reserveRail() {
  if (railReserved) return;
  railReserved = true;
  document.documentElement.setAttribute("data-lf-rail", "");
}

function scheduleMarginLayout() {
  if (pending) return;
  pending = requestAnimationFrame(layoutMarginRows);
}

function observeLayout() {
  const column = marginColumn();
  if (!observer) {
    observer = new ResizeObserver(scheduleMarginLayout);
    observer.observe(document.body);
  }
  if (observedColumn === column) return;
  if (observedColumn) observer.unobserve(observedColumn);
  observedColumn = column;
  observer.observe(observedColumn);
}

export function registerMarginRow(row, options = {}) {
  rows.set(row, options);
  dockedAgainst.delete(row);
  observeLayout();
  scheduleMarginLayout();
  return () => unregisterMarginRow(row);
}

export function updateMarginRow(row, options = {}) {
  if (!rows.has(row)) return registerMarginRow(row, options);
  rows.set(row, options);
  dockedAgainst.delete(row);
  observeLayout();
  scheduleMarginLayout();
  return () => unregisterMarginRow(row);
}

export function unregisterMarginRow(row) {
  rows.delete(row);
  row?.classList.remove("lf-docked", "lf-withheld");
  if (row) row.style.transform = "";
  if (!rows.size) {
    observer?.disconnect();
    observer = null;
    observedColumn = null;
    for (const el of document.querySelectorAll("[data-lf-space][data-lf-yield]"))
      el.removeAttribute("data-lf-yield");
  }
  scheduleMarginLayout();
}

// The other half of the clear below: `add` re-serializes the class attribute whether
// or not the token is new, and the posture read leaves a row that still cannot hang
// carrying `lf-docked` from one pass into the next, so it arrives at its mark already
// wearing it. Ask before marking.
function mark(row, name) {
  if (!row.classList.contains(name)) row.classList.add(name);
}

function placeRows(columnRect) {
  const placements = [...rows].map(([row, options]) =>
    options.place?.(row, columnRect),
  );
  for (const place of placements) place?.();
}

export function layoutMarginRows() {
  cancelAnimationFrame(pending);
  pending = 0;
  // A compact page keeps every margin row in document flow. Pulling those rows out to
  // re-measure the same posture briefly shortens the document, so a browser clamps a
  // reader standing at its end before the rows return. Read the current posture as one
  // batch and leave rows whose owner still says they cannot hang where they are.
  const dockedRows = [...rows].filter(
    ([row]) => row.isConnected && row.classList.contains("lf-docked"),
  );
  const staysDocked = new Set();
  if (dockedRows.length) {
    const postureColumn = marginColumn();
    const postureColumnRect = postureColumn.getBoundingClientRect();
    const postureRoom = document.body.getBoundingClientRect().right;
    const columnMoving =
      parseFloat(
        getComputedStyle(postureColumn).getPropertyValue("--lf-shell-motion-x"),
      ) !== 0;
    for (const [row, options] of dockedRows) {
      const anchor =
        typeof options.anchor === "function" ? options.anchor() : options.anchor;
      const shown =
        options.shown?.(anchor) ??
        (anchor instanceof Element ? anchor.checkVisibility() : row.checkVisibility());
      if (!shown) continue;
      const hangs =
        options.hangs?.(
          row,
          row.getBoundingClientRect(),
          postureColumnRect,
          postureRoom,
        ) ?? true;
      // Its owner still says it cannot hang, so the answer needs no measuring.
      if (!hangs) {
        staysDocked.add(row);
        continue;
      }
      // It hangs by its owner's reading and docked anyway, which means it did not fit
      // the horizontal space. Floating it to measure that again moves a host that may
      // hold focus, so keep the answer while its inputs hold. During the shell's carry,
      // every frame has a different drawn column but only the resting position is
      // durable space to answer about.
      const against = dockedAgainst.get(row);
      if (
        against?.room === postureRoom &&
        (columnMoving ||
          (against.columnLeft === postureColumnRect.left &&
            against.columnRight === postureColumnRect.right))
      )
        staysDocked.add(row);
    }
  }
  for (const [row, options] of rows) {
    if (!row.isConnected) {
      rows.delete(row);
      continue;
    }
    if (staysDocked.has(row)) continue;
    if (row.classList.contains("lf-docked")) options.float?.(row);
    // `remove` re-serializes the class attribute whether or not the tokens stand, and
    // this pass runs on the heartbeat, so ask before clearing: a row that hangs in the
    // margin carries neither class and has nothing to be put back.
    if (row.classList.contains("lf-docked") || row.classList.contains("lf-withheld"))
      row.classList.remove("lf-docked", "lf-withheld");
    row.style.transform = "";
  }
  if (!rows.size) {
    observer?.disconnect();
    observer = null;
    observedColumn = null;
  }

  // Each phase reads every row before writing any. A placement callback returns
  // its writer so target measurements never flush the previous row's changes.
  const columnRect = marginColumn().getBoundingClientRect();
  const room = document.body.getBoundingClientRect().right;
  placeRows(columnRect);
  const measured = [...rows].map(([row, options]) => {
    const anchor =
      typeof options.anchor === "function" ? options.anchor() : options.anchor;
    const rect = row.getBoundingClientRect();
    const width =
      typeof options.claim === "function"
        ? options.claim(row, rect)
        : options.claim
          ? rect.width
          : 0;
    const claim = width
      ? Math.ceil(width + (parseFloat(getComputedStyle(row).marginLeft) || 0))
      : 0;
    return {
      row,
      options,
      rect,
      claim,
      hangs: options.hangs?.(row, rect, columnRect, room) ?? true,
      shown:
        options.shown?.(anchor) ??
        (anchor instanceof Element ? anchor.checkVisibility() : row.checkVisibility()),
    };
  });
  const claim = Math.max(0, ...measured.map(({ claim }) => claim));
  if (claim) {
    reserveRail();
    if (claim > claimedRail) {
      claimedRail = claim;
      document.documentElement.style.setProperty("--rail", `${claimedRail}px`);
    }
  }
  const inMargin = [];
  let docked = false;
  for (const { row, options, rect, shown, hangs } of measured) {
    if (!shown) mark(row, "lf-withheld");
    // A row the posture read kept docked is measured where it stands, in flow, so its
    // own rect says it fits a rail it is not in. It takes the docked path on the reading
    // that kept it, not on a measurement of somewhere it is not standing.
    else if (!hangs || staysDocked.has(row) || rect.right > room) {
      if (options.fallback === "hide") mark(row, "lf-withheld");
      else {
        mark(row, "lf-docked");
        dockedAgainst.set(row, {
          room,
          columnLeft: columnRect.left,
          columnRight: columnRect.right,
        });
        options.dock?.(row);
        docked = true;
      }
    } else inMargin.push(row);
  }

  // Docked rows enter document flow and move every later target. Measure those
  // targets in the final flow before packing the rows that still hang beside them.
  if (docked) placeRows(marginColumn().getBoundingClientRect());

  const placed = inMargin
    .map((row) => ({
      row,
      rect: row.getBoundingClientRect(),
      priority: rows.get(row)?.priority ?? 0,
    }))
    .sort((a, b) => a.priority - b.priority || a.rect.top - b.rect.top);
  const bands = [];
  for (const { row, rect } of placed) {
    let top = rect.top;
    for (const band of [...bands].sort((a, b) => a.top - b.top))
      if (top < band.bottom + GAP && top + rect.height > band.top - GAP)
        top = band.bottom + GAP;
    const push = top - rect.top;
    if (push) row.style.transform = `translateY(${push}px)`;
    bands.push({ top, bottom: top + rect.height });
  }

  const wide = [...document.querySelectorAll("[data-lf-space]")].map((el) => {
    const box = el.getBoundingClientRect();
    return {
      el,
      yieldRight: bands.some((band) => band.top < box.bottom && band.bottom > box.top),
    };
  });
  for (const { el, yieldRight } of wide) {
    if (yieldRight) {
      if (el.getAttribute("data-lf-yield") !== "r")
        el.setAttribute("data-lf-yield", "r");
    } else if (el.hasAttribute("data-lf-yield")) el.removeAttribute("data-lf-yield");
  }
  document.dispatchEvent(new CustomEvent("lf-margin-layout"));
}

export { scheduleMarginLayout };
