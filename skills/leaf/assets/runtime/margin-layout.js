/* One geometry owner for the rows that stand in the margin or over the page.

   Every margin row lives in the chrome's margin layer and is tied to its target by anchor
   positioning, so nothing Leaf draws is inserted into the page's content and nothing it
   draws moves that content. A row stands in one of two postures (`margin-placement.js`):
   in the rail, the strip beside `main` where the room there holds one, or as a pin over the
   page by its target, seated where it covers no words when there is room for it
   (`seatPins`). The stylesheet places each row from what this pass writes on it
   (theme.css, at .lf-margin-cluster): its posture as `data-lf-place`, its seat as
   `--lf-inset-top` and `--lf-inset-right`, and the push packing gives it as `--lf-push`. Scrolling moves a row with its target on the compositor, whether the
   document scrolls or a pane does, with no pass at all.

   The layer is a static, zero-height block. A positioned wrapper would become every row's
   containing block, and a row can only anchor to what stands inside its containing block,
   so every target outside it would be an invalid anchor. Rows whose targets scroll with
   the document stand in the root lane; each
   bounded reading region (one whose body scrolls on its own) gets a lane of its own,
   clipped with `clip-path` to what that region shows, and across to the rail for a
   bounded block in the column's flow, which clips a row's paint and presses without
   making the lane a containing block.

   An anchor name reaches only its own tree, so a target inside a shadow tree anchors
   through its host, and a `display: contents` target through its first shown part.
   `position-visibility` hides a row whose anchor its scroller has clipped away, but not
   one whose anchor is invalid (missing, `display: contents`, inside
   `content-visibility: hidden`): every position function in the stylesheet therefore
   parks the row off screen when its anchor fails, and this pass marks a row withheld,
   out of the tab order, when its target has no shown part in its region.

   Visibility reads `shownParts`, not the target's raw client rect: a project may set
   `display: contents` while its rendered descendants remain usable, and a collapsed
   target has no rendered part to offer. */
import { TAB_STOP } from "./focus.js";
import { cancelRender, nextFrame, nextRender, sizeObserver } from "./rendering.js";
import { shellRight, shownBand, shownExtent, shownParts, skipped } from "./geometry.js";
import { shadowHost, under, upFrom } from "./shadow.js";
import { scrollerFor } from "./reading-regions.js";
import { boundedBlockOf } from "./bounds.js";
import { pageScroller } from "./scrolling.js";
import { packRows, rowPosture, seatRows } from "./margin-placement.js";
import { overlaps } from "./rect.js";
import { pointBand } from "./pointed-place.js";
import { anchorElement, anchorReading, nameAnchor } from "./anchor-names.js";
import { repaintPage } from "./repaint.js";
import { keeps, layoutPx } from "./keeps.js";

const rows = new Map();
const GAP = 4;
// The anchor name the rail hangs from: `main`'s own box.
const PAGE_ANCHOR = "--lf-page";
let pending = 0;
let observer = null;
let observedColumn = null;
let layer = null;

const marginColumn = () => document.querySelector("main") || document.body;

// The postures a margin resident may take besides the rail: the side each stands on and
// the token holding the room it needs there beyond `main`'s box. The stylesheet says
// which element takes which, in order of preference (`--lf-resident`, theme.css, at
// aside.sidebar), so the media and Layout conditions on each are the stylesheet's own.
const POSTURES = {
  sidebar: ["left", "--sidebar"],
  map: ["left", "--map"],
  note: ["right", "--note"],
};

// Which residents stand in the margin, and how far the column moves off centre to seat
// them: one reading of the room beside `main`, so the rail, the contents map, a sidebar
// and the sidenotes all answer the same measurement, whatever width the page's own CSS
// gave the column. It is written on `main` as `data-lf-margin`, one token per resident
// standing, and `--lf-shift`, which the column Layout applies (layouts.css); the
// stylesheet keys every margin posture on those.
//
// The rail comes first and stands where the room right of the centred column holds
// `--rail`; it never moves the column. Then the left side's resident and the notes, which
// share one decision: each takes the first of its postures for which the room either
// side of the column, together, holds what those admitted so far need on each side and
// this posture's need too, the column moving over by what one side lacks. One that fits
// none stays in flow. The room is read with the column centred, so a shift this pass
// wrote is taken back out of the reading and the decision never feeds itself.
//
// A page declares otherwise on `body`: `data-rail="right"` makes the shell give up the
// rail's width on its right (theme.css), which this reads as room like any other, and
// `data-rail="none"` keeps its margin for its own residents, so its markers are pins.
// Chrome layout asks for it on every pass (chrome-layout.js, `syncLayout`), which runs
// more than once in a frame, so the reading is taken at most once a frame
// (`scheduleResidency`): a second ask in a frame already read waits for the next. A change
// brings this module's pass, since a moved column moves every margin row, and a page
// repaint; this pass reads the answer off `main`.
let residencyPending = 0;
let residencyRead = -1;
function residencyPass(time) {
  residencyPending = 0;
  if (time === residencyRead) {
    residencyPending = nextFrame(residencyPass);
    return;
  }
  residencyRead = time;
  if (!settleResidency()) return;
  scheduleMarginLayout();
  repaintPage();
}
export function scheduleResidency() {
  residencyPending ||= nextRender(residencyPass);
}

function settleResidency() {
  const main = document.querySelector("main");
  if (!main) {
    decidePins(false);
    return false;
  }
  const style = getComputedStyle(main);
  const need = (token) => parseFloat(style.getPropertyValue(token)) || 0;
  // The offset the column stands at, which is the written shift only where the Layout
  // applies it: page CSS may override the offset, and under `dir="rtl"` it is `right`.
  const shifted =
    style.position === "relative"
      ? parseFloat(style.left) || -parseFloat(style.right) || 0
      : 0;
  const written = parseFloat(main.style.getPropertyValue("--lf-shift")) || 0;
  const column = main.getBoundingClientRect();
  const shell = document.body.getBoundingClientRect();
  const room = {
    left: column.left - shifted - shell.left,
    right: shell.right - column.right + shifted,
  };
  const taken = { left: 0, right: 0 };
  const standing = [];
  if (
    document.body.getAttribute("data-rail") !== "none" &&
    room.right >= need("--rail")
  ) {
    standing.push("rail");
    taken.right = need("--rail");
  }
  const declared = new Map();
  // A resident a box around it hides (a closed disclosure, a tab not chosen) needs no
  // room. One the page hides itself stays a resident, since a page may hide it until it
  // stands in the margin. One in skipped content is asked nothing (`skipped`).
  for (const aside of main.querySelectorAll("aside")) {
    if (skipped(aside)) continue;
    const own = getComputedStyle(aside);
    const hiddenItself =
      own.display === "none" && aside.parentElement.checkVisibility();
    if (!aside.checkVisibility() && !hiddenItself) continue;
    const postures = own
      .getPropertyValue("--lf-resident")
      .split(" ")
      .filter((posture) => posture in POSTURES);
    if (postures.length) declared.set(postures.join(" "), postures);
  }
  const side = (postures) => POSTURES[postures[0]][0];
  for (const postures of [...declared.values()].sort(
    (a, b) => (side(a) === "left" ? 0 : 1) - (side(b) === "left" ? 0 : 1),
  ))
    for (const posture of postures) {
      const [at, token] = POSTURES[posture];
      const wants = { ...taken, [at]: Math.max(taken[at], need(token)) };
      if (wants.left + wants.right > room.left + room.right + 0.5) continue;
      standing.push(posture);
      Object.assign(taken, wants);
      break;
    }
  const shift = Math.round(
    taken.left > room.left
      ? taken.left - room.left
      : taken.right > room.right
        ? room.right - taken.right
        : 0,
  );
  const tokens = standing.join(" ");
  decidePins(standing.includes("rail"));
  const changed =
    (main.getAttribute("data-lf-margin") ?? "") !== tokens || shift !== written;
  if (!changed) return false;
  keeps(main, "data-lf-margin", tokens);
  setStyle(main, "--lf-shift", shift ? `${shift}px` : null);
  return true;
}

const railStands = (main) =>
  (main.getAttribute("data-lf-margin") ?? "").split(" ").includes("rail");

// Said on the chrome root where the margin's standing is decided: where the markers are
// pins, the banner offers the Page Map in their place (chrome.css). Until the standing
// is decided it says nothing, rather than one answer the decision then takes back.
let railStood = null;
function decidePins(stands) {
  railStood = stands;
  paintPins();
}
function paintPins() {
  if (railStood !== null)
    layer?.root.closest(".lf-chrome").toggleAttribute("data-lf-pins", !railStood);
}

const labelRect = (name, left, top, label) => ({
  name,
  rect: {
    left,
    right: left + label.width,
    top,
    bottom: top + label.height,
  },
});

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
        !blockers.some((blocker) => overlaps(candidate.rect, blocker)),
    ) ??
    candidates.find(fits) ??
    candidates[0];
  keeps(control, "data-lf-label-side", choice.name);
  label.style.setProperty(
    "--lf-label-x",
    `${choice.rect.left - marginEntryBox.left}px`,
  );
  label.style.setProperty("--lf-label-y", `${choice.rect.top - marginEntryBox.top}px`);
}

let labelPlacementFrame = 0;
export function scheduleMarginEntryLabels() {
  if (labelPlacementFrame) return;
  labelPlacementFrame = nextRender(() => {
    labelPlacementFrame = 0;
    for (const control of document.querySelectorAll(
      '.lf-margin-entry:is(:hover, :focus-visible, .lf-focus-visible, [data-lf-held-word]):not([aria-expanded="true"])',
    ))
      placeMarginEntryLabel(control);
  });
}

// The layer's root lane, where rows whose targets scroll with the document stand, and one
// lane per bounded reading region, keyed by the box that scrolls it. A scroll anywhere
// but the document's may take a target out of view or bring it back, so it is heard once,
// here, rather than per lane: a table or a board scrolled sideways is no lane of its own.
export function mountMarginLayer(root) {
  layer = { root, lanes: new Map(), sizes: sizeObserver(scheduleMarginLayout) };
  paintPins();
  hearScrolls(document);
  // Opening or closing a disclosure shows or hides the residents inside it. `toggle`
  // does not bubble, so it is heard on the way down.
  document.addEventListener("toggle", scheduleResidency, { capture: true });
}

// A scroll event does not leave its shadow tree, so a target inside one is heard on each
// tree holding it as well as on the document.
const heard = new WeakSet();
function hearScrolls(root) {
  if (heard.has(root)) return;
  heard.add(root);
  root.addEventListener(
    "scroll",
    (event) => {
      if (event.target === document || !(event.target instanceof Element)) return;
      scrolled.add(event.target);
      scheduleScrollReading();
    },
    { capture: true, passive: true },
  );
}

function laneFor(scroller) {
  if (scroller === pageScroller) return layer.root;
  let lane = layer.lanes.get(scroller);
  if (!lane) {
    lane = document.createElement("div");
    lane.className = "lf-margin-lane";
    layer.root.parentElement.append(lane);
    layer.lanes.set(scroller, lane);
    layer.sizes.observe(scroller);
  }
  return lane;
}

// The part of a box its scrollers show, short of the document's own: each scroller's band
// between the box and the document cuts it. The window does not count, since a row
// scrolled off it is still the user's to walk to. `stop` ends the walk at a scroller
// short of the document, for a reading that must not change as that scroller scrolls.
// `bands` caches each box's band for one reading.
const EVERYWHERE = {
  left: -Infinity,
  top: -Infinity,
  right: Infinity,
  bottom: Infinity,
};
function clippedBand(el, rect, bands, stop = pageScroller) {
  let { left, top, right, bottom } = rect;
  for (let at = upFrom(el); at && at !== pageScroller && at !== stop; at = upFrom(at)) {
    let band = bands.get(at);
    if (band === undefined) bands.set(at, (band = shownBand(at)));
    if (!band) continue;
    left = Math.max(left, band.left);
    top = Math.max(top, band.top);
    right = Math.min(right, band.right);
    bottom = Math.min(bottom, band.bottom);
  }
  return right > left && bottom > top ? { left, top, right, bottom } : null;
}

// How far right the figure a target belongs to reaches: the furthest of its own box and
// the boxes holding it inside `main`, so a card in a board grown past the rail stands its
// comment on the board as a figure does. Read off the boxes rather than the declared
// widths, so a block an agent widened with its own CSS counts too. A scroller cuts what
// it holds to what it shows: a cell far along a wide table is not a figure past the rail.
function reach(anchor, box, main, reaches) {
  let right = box.right;
  for (let el = anchor.parentElement; el && el !== main; el = el.parentElement) {
    let edge = reaches.get(el);
    if (edge === undefined) {
      const b = el.getBoundingClientRect();
      edge = {
        right: b.right,
        clip:
          getComputedStyle(el).overflowX === "visible"
            ? null
            : b.left + el.clientLeft + el.clientWidth,
      };
      reaches.set(el, edge);
    }
    if (edge.clip !== null) right = Math.min(right, edge.clip);
    right = Math.max(right, edge.right);
  }
  return right;
}

// The boxes a pin's target is drawn in: one per line for a run of text, so the room at the
// end of the line it ends on is seen as room rather than as part of its extent.
function partsOf(target) {
  return shownParts(target)
    .flatMap((part) => [...part.getClientRects()])
    .filter((box) => box.width && box.height);
}

// The block a target's words belong to: the target where it is a block, and otherwise the
// box its line runs in.
function blockOf(target) {
  let el = target;
  while (el.parentElement && el !== marginColumn()) {
    const display = getComputedStyle(el).display;
    if (!display.startsWith("inline") && display !== "contents") break;
    el = el.parentElement;
  }
  return el;
}

// What a pin may not stand on across a band of the page (`cover`): every run of words,
// each box that paints what no text node says (an image, a drawing, a widget's shadow
// tree, the target's own if it is one), every control, and, whole, every other box that
// paints its own extent (`paintsItsBox`). A box that draws a fill, a rule or a shadow
// reads as one thing, so a pin anywhere on it, even over its empty end, reads as that
// box's: a card, a callout, a framed table or code block. Every other block that paints
// nothing is a `neighbour`: it covers only by its words, so the empty end of a short
// heading or line beside the target is room, but a pin there can read as that block's,
// and `pinSpot` takes it only where the target has no room of its own. Inside the
// target's own block nothing counts whole, since that is the pin's own. A box that holds
// the target is not one to avoid, since the pin stands on it. The walk leaves any
// subtree whose box misses the band, so a long page costs what lies near the target.
//
// The controls come back apart as well, since packing keeps the pin off them, a pin left
// at its corner too (`packRows`, `fixed`): a pin at a card's top-right would otherwise
// take the presses meant for the card's grip. Anything the keyboard can reach is a control, so a package need declare
// nothing. Each counts as the part of it its own scrollers show, short of the one that
// scrolls the pin (`stop`): a pin can take no press from a control nobody can see, as a
// pane body's options scrolled behind the pane's footer, but a control scrolled with the
// pin counts whole, so the pane's scroll never moves the pin's seat.
const OPAQUE = "img, svg, canvas, video, iframe, object, embed";

// Whether an element draws its own extent: a fill, a rule on any side, or a shadow. An
// inline box paints along its lines of words, which count already, and a `display:
// contents` element has no box to paint.
const SIDES = ["Top", "Right", "Bottom", "Left"];
const unseen = (color) =>
  color === "transparent" || /^rgba\(.*,\s*0\)$|\/\s*0\)$/.test(color);
function paintsItsBox(style) {
  if (style.display === "inline" || style.display === "contents") return false;
  return (
    style.backgroundImage !== "none" ||
    style.boxShadow !== "none" ||
    !unseen(style.backgroundColor) ||
    SIDES.some(
      (side) =>
        parseFloat(style[`border${side}Width`]) > 0 &&
        !unseen(style[`border${side}Color`]),
    )
  );
}

function coverIn(root, band, target, block, bands, stop) {
  const cover = [];
  const neighbours = [];
  const controls = [];
  const meets = (box) => box.bottom > band.top && box.top < band.bottom;
  const edges = ({ left, top, right, bottom }) => ({ left, top, right, bottom });
  const visit = (el) => {
    for (const node of el.childNodes) {
      if (node.nodeType === Node.TEXT_NODE) {
        if (!node.data.trim()) continue;
        const words = document.createRange();
        words.selectNodeContents(node);
        for (const box of words.getClientRects())
          if (box.width > 1 && box.height > 1 && meets(box)) cover.push(edges(box));
        continue;
      }
      if (node.nodeType !== Node.ELEMENT_NODE || node.closest(".lf-chrome")) continue;
      const box = node.getBoundingClientRect();
      const boxless = !box.width && !box.height;
      if (!boxless && !meets(box)) continue;
      const holds = node !== target && node.contains(target);
      const control = node.matches(TAB_STOP);
      if (
        !boxless &&
        !holds &&
        (node.shadowRoot || node.matches(OPAQUE) || control) &&
        node.checkVisibility()
      ) {
        const shown = clippedBand(node, box, bands, stop);
        if (shown) cover.push(shown);
        if (shown && control) controls.push(shown);
        continue;
      }
      if (node instanceof SVGElement) continue;
      if (!boxless && !holds && !block.contains(node)) {
        const style = getComputedStyle(node);
        if (paintsItsBox(style)) {
          cover.push(edges(box));
          continue;
        }
        if (!style.display.startsWith("inline") && style.display !== "contents")
          neighbours.push(edges(box));
      }
      // A closed disclosure draws only its summary; reading the rest would force its
      // skipped content's layout (`skipped`).
      if (node.localName === "details" && !node.open) {
        const summary = node.querySelector(":scope > summary");
        if (summary) visit({ childNodes: [summary] });
        continue;
      }
      visit(node);
    }
  };
  visit(root);
  return { cover, neighbours, controls };
}

// The whole content a scroller scrolls, wherever it is scrolled to: a pin in a pane is
// seated inside it, so its seat is the same at every scroll.
function contentBox(scroller) {
  const box = scroller.getBoundingClientRect();
  const left = box.left + scroller.clientLeft - scroller.scrollLeft;
  const top = box.top + scroller.clientTop - scroller.scrollTop;
  return {
    left,
    top,
    right: left + Math.max(scroller.scrollWidth, scroller.clientWidth),
    bottom: top + Math.max(scroller.scrollHeight, scroller.clientHeight),
  };
}

// How far from its target's nearest part a pin may stand when its corner covers words.
const REACH = 12;

// Each pin's seat, measured from the box it anchors to, as the last pass took it: a pin
// under the pointer or holding focus keeps it (`seatRows`), and a scroll inside a pane
// reads it to say whether the pin still stands inside what the pane shows.
const seats = new WeakMap();

// Seats every pin (`seatRows`): reads what each may not stand on around its target and
// the room it may take, then writes each seat into its entry's rect for packing, with the
// controls packing keeps it off. A pin inside a shadow tree stays at its corner: the words
// around it are the tree's, which this walk does not read.
function seatPins(standing, { bands, shell, pinInset }) {
  const main = marginColumn();
  const pins = [];
  for (const entry of standing) {
    const { read } = entry;
    if (read.place !== "pin") continue;
    const { target, point, row, box } = read;
    const home = entry.rect;
    const height = home.bottom - home.top;
    const width = home.right - home.left;
    const held = seats.get(row);
    entry.held =
      held && row.matches(":hover, :focus-within")
        ? {
            left: box.right - held.right - width,
            right: box.right - held.right,
            top: box.top + held.top,
            bottom: box.top + held.top + height,
          }
        : null;
    // A pin level with a pointed row keeps to that row, as a pin keeps to its target;
    // the row's boxes are read wherever it is drawn, a widget's shadow tree included,
    // since the walk below reads the room around the target, which is the document's.
    const parts = target.getRootNode() === document ? partsOf(point ?? target) : [];
    const around = height + REACH + GAP;
    const band = {
      top: Math.min(home.top, ...parts.map((part) => part.top)) - around,
      bottom: Math.max(home.bottom, ...parts.map((part) => part.bottom)) + around,
    };
    // Only what scrolls with the pin is read: in a pane, the pane's own content. The pane's
    // header, standing still above it, would enter the band as the pane scrolled the
    // target up to it, and seat the pin differently at that scroll.
    const stop = read.scroller;
    const { cover, neighbours, controls } = coverIn(
      stop === pageScroller ? main : stop,
      band,
      target,
      blockOf(target),
      bands,
      stop,
    );
    entry.fixed = controls;
    // A run of text is finished at the end of its last line, and the pin sits there,
    // level with that line; a block's pin keeps its corner, and so does a shape in a
    // drawing, whose `display` says nothing about lines.
    const end = parts.at(-1);
    const inline =
      !point &&
      target instanceof HTMLElement &&
      getComputedStyle(target).display.startsWith("inline");
    const within = stop === pageScroller ? null : contentBox(stop);
    // A board or table can clip the target across without owning its reading region.
    // Search only the room it shows; otherwise the nearest clear spot can leave the
    // scroller and targetShown withholds an otherwise reachable action.
    const clipped = clippedBand(target, EVERYWHERE, bands, stop);
    pins.push({
      key: entry,
      rect: home,
      priority: entry.priority,
      held: entry.held,
      parts,
      cover,
      neighbours,
      seat: inline
        ? {
            left: end.right + GAP,
            right: end.right + GAP + width,
            top: (end.top + end.bottom - height) / 2,
            bottom: (end.top + end.bottom + height) / 2,
          }
        : home,
      bounds: {
        left: Math.max(within?.left ?? 0, clipped?.left ?? 0) + pinInset,
        right: Math.min(within?.right ?? shell, clipped?.right ?? shell) - pinInset,
        top: within?.top ?? -Infinity,
        bottom: within?.bottom ?? Infinity,
      },
    });
  }
  for (const [entry, rect] of seatRows(pins, { reach: REACH, gap: GAP })) {
    entry.rect = rect;
    seats.set(entry.read.row, {
      top: rect.top - entry.read.box.top,
      right: entry.read.box.right - rect.right,
    });
  }
}

function scheduleMarginLayout() {
  if (pending) return;
  pending = nextRender(layoutMarginRows);
}

function observeLayout() {
  const column = marginColumn();
  if (!observer) {
    observer = sizeObserver(scheduleMarginLayout);
    observer.observe(document.body);
  }
  if (observedColumn === column) return;
  if (observedColumn) observer.unobserve(observedColumn);
  observedColumn = column;
  observer.observe(observedColumn);
}

// Each row states its target (`anchor`), the row inside it it stands level with, if any
// (`point`, pointed-place.js), its place among the others in the layer (`order`), its
// packing priority, and how to move it between lanes without dropping the focus it holds
// (`move`).
export function registerMarginRow(row, options = {}) {
  rows.set(row, options);
  observeLayout();
  scheduleMarginLayout();
}

export function unregisterMarginRow(row) {
  rows.delete(row);
  if (row) {
    row.classList.toggle("lf-withheld", false);
    row.removeAttribute("data-lf-place");
    row.removeAttribute("data-lf-parked");
    for (const property of [
      "--lf-inset-top",
      "--lf-inset-right",
      "--lf-push",
      "--lf-step",
      "position-anchor",
    ])
      row.style.removeProperty(property);
    pushes.delete(row);
    steps.delete(row);
    parked.delete(row);
  }
  if (!rows.size) {
    observer?.disconnect();
    observer = null;
    observedColumn = null;
  }
  scheduleMarginLayout();
}

function setStyle(row, property, value) {
  if (value === null) {
    if (row.style.getPropertyValue(property)) row.style.removeProperty(property);
  } else if (row.style.getPropertyValue(property) !== value)
    row.style.setProperty(property, value);
}

// Whether a row has somewhere to stand: its target renders, its scrollers leave some of
// it in view — the pane that scrolls it, a table or board it has been scrolled sideways
// out of, or a scroller inside the shadow tree it anchors through, which can take the
// target away while the host it anchors through still shows — and the row itself stands
// inside what those scrollers show. `stands` is where the row stands: a rail row's top is
// its target's, and a pin's is its seat, which may lie above or beside its target. Its top
// line counts, since a row standing above a pane's top would be clipped by its lane and
// still take the keyboard, and for a pin its right edge too: a card half past a board's
// edge would stand its pin outside the board, beside nothing and past the page. A pin not
// yet seated passes `stands` null, and is asked again once it is.
function targetShown(target, extent, stands, bands) {
  const shown = (part) =>
    part.checkVisibility() && clippedBand(part, part.getBoundingClientRect(), bands);
  if (!shownParts(target).some(shown)) return false;
  if (!clippedBand(target, extent, bands)) return false;
  if (!stands) return true;
  const view = clippedBand(target, EVERYWHERE, bands);
  return (
    stands.top >= view.top - 1 &&
    (stands.right === undefined || stands.right <= view.right + 1)
  );
}

// Where a pin stood at the last pass, from the box it anchors to now: its seat and its
// push, which a scroll moves only with that box.
function pinStands(row, box) {
  const seat = seats.get(row);
  if (!seat) return null;
  return {
    top: box.top + seat.top + (pushes.get(row) ?? 0),
    right: box.right - seat.right,
  };
}

const pushes = new Map();
const steps = new Map();
const clips = new WeakMap();
// A row whose anchor the browser would not take — one behind an author's `anchor-scope`,
// say — stands at its fallback off screen. The pass finds it there once and
// withholds it for as long as it anchors to the same box, rather than finding it again on
// every heartbeat. `data-lf-parked` says so for the render gate.
const parked = new WeakMap();

// A scroll inside anything but the document moves its rows on the compositor. What it can
// change is which of them still have somewhere to stand, so only rows under a box that
// scrolled are read again, once a frame, and a row that changes answer brings the whole
// pass, which places it. A row anchored through a shadow host stands at an inset from the
// host, so a scroll inside the host moves its target and not the row: that brings the
// pass too, which takes the inset again.
const scrolled = new Set();
let scrollReading = 0;
function scheduleScrollReading() {
  if (scrollReading) return;
  scrollReading = nextRender(() => {
    scrollReading = 0;
    const boxes = [...scrolled];
    scrolled.clear();
    const bands = new Map();
    for (const [row, options] of rows) {
      const target = options.anchor();
      if (!target?.isConnected || parked.has(row)) continue;
      const anchor = anchorElement(target);
      // A box scrolled inside the anchor moves a pointed row against the box the row is
      // inset from, as it moves a target inside its host.
      const point = options.point?.();
      if (point && boxes.some((box) => under(point, box) && under(box, anchor))) {
        scheduleMarginLayout();
        return;
      }
      const moving = boxes.filter((box) => under(target, box));
      if (!moving.length) continue;
      if (anchor !== target && moving.some((box) => under(box, anchor))) {
        scheduleMarginLayout();
        return;
      }
      const extent = shownExtent(target);
      const stands =
        row.dataset.lfPlace === "pin"
          ? pinStands(row, anchor.getBoundingClientRect())
          : { top: extent?.top };
      if (
        targetShown(target, extent, stands, bands) ===
        row.classList.contains("lf-withheld")
      ) {
        scheduleMarginLayout();
        return;
      }
    }
  });
}

export function layoutMarginRows() {
  cancelRender(pending);
  pending = 0;
  if (!layer) return;
  const main = marginColumn();
  const page = anchorReading(main, PAGE_ANCHOR);
  const columnRect = main.getBoundingClientRect();
  const shell = shellRight();
  const stands = railStands(main);
  const rootStyle = getComputedStyle(document.documentElement);
  const hang = parseFloat(rootStyle.getPropertyValue("--rail-hang")) || 0;
  const pinInset = parseFloat(rootStyle.getPropertyValue("--pin-inset")) || 0;
  const railInner = columnRect.right + hang;
  // The rail lies beside the column, so it stands beside the rows of what flows in the
  // column: the document's own, and a bounded block's, which scrolls inside the document
  // as a paragraph does. A pane is not in that flow, so its rows pin wherever it stands.
  const railBeside = (scroller) => {
    if (scroller === pageScroller) return true;
    const block = boundedBlockOf(scroller);
    return Boolean(block) && scrollerFor(upFrom(block)) === pageScroller;
  };
  // The half that decides rail or pin is a rail marker's: a pin's entries are smaller.
  const entry = layer.root.parentElement.querySelector(
    '.lf-margin-cluster:not([data-lf-place="pin"]) .lf-margin-entry:not([hidden])',
  );
  const size = entry?.offsetWidth || 32;
  // The notes hanging in the margin the rail stands in (theme.css, aside.sidenote): a
  // marker level with one would be drawn over it.
  const notes = [...main.querySelectorAll("aside.sidenote")]
    .filter((note) => !skipped(note))
    .map((note) => note.getBoundingClientRect())
    .filter((note) => note.width && note.left >= columnRect.right - 1);

  // Every read before any write: a write between two reads forces a layout per row.
  const bands = new Map();
  const reaches = new Map();
  const reads = [];
  for (const [row, options] of rows) {
    const target = options.anchor();
    if (!target?.isConnected) {
      reads.push({ row, options, lane: layer.root, shown: false });
      continue;
    }
    // A target in skipped content — a tab not chosen, a closed disclosure — has nowhere
    // to stand, and every reading below would force that content's style and layout to
    // say so (`skipped`). Withheld like a target that has gone, it is anchored by the
    // pass that runs once it is drawn, and keeps the lane it stands in meanwhile, so a
    // tab switch does not move the rows of a reading region's hidden panels between
    // lanes.
    if (skipped(target)) {
      reads.push({ row, options, lane: row.parentElement ?? layer.root, shown: false });
      continue;
    }
    const anchor = anchorElement(target);
    // Level with the row a gesture pointed into, where the row's comment has one
    // (pointed-place.js); otherwise level with the target's top.
    const point = options.point?.() ?? null;
    for (
      let root = (point ?? target).getRootNode();
      shadowHost(root);
      root = root.host.getRootNode()
    )
      hearScrolls(root);
    if (parked.has(row) && parked.get(row) !== anchor) parked.delete(row);
    const scroller = scrollerFor(target);
    const rootLane = scroller === pageScroller;
    const box = anchor.getBoundingClientRect();
    const extent = shownExtent(target);
    const top = extent && point ? pointBand(extent, point).top : extent?.top;
    const level = point ? top : box.top;
    const place = rowPosture({
      railStands: stands,
      besideRail: railBeside(scroller),
      blockRight: reach(anchor, box, main, reaches),
      railInner,
      half: size / 2,
      noted: notes.some((note) => note.top < level + size && note.bottom > level),
    });
    const shown =
      !parked.has(row) &&
      targetShown(target, extent, place === "pin" ? null : { top }, bands);
    reads.push({
      row,
      options,
      target,
      point,
      anchor,
      naming: anchorReading(anchor),
      scroller,
      lane: rootLane ? layer.root : null,
      shown,
      place,
      box,
      extent,
      top,
    });
  }
  // What each lane's region shows, cut by the scrollers around it but not by the window,
  // so a pane below the fold is clipped where its own edges will be when it arrives.
  const regions = new Map();
  for (const read of reads)
    if (read.scroller && read.scroller !== pageScroller && !regions.has(read.scroller))
      regions.set(
        read.scroller,
        clippedBand(
          read.scroller,
          shownBand(read.scroller) ?? read.scroller.getBoundingClientRect(),
          bands,
        ),
      );

  nameAnchor(page);
  // Lanes, in the order the rows are given, moving only what is out of place; each lane
  // after the last, so the tab order runs the lanes as the rows run.
  for (const read of reads) read.lane ??= laneFor(read.scroller);
  const byLane = new Map();
  for (const read of [...reads].sort(
    (a, b) => (a.options.order ?? 0) - (b.options.order ?? 0),
  ))
    byLane.set(read.lane, [...(byLane.get(read.lane) ?? []), read]);
  let lastLane = layer.root;
  for (const [lane, members] of byLane) {
    if (lane !== layer.root) {
      if (lastLane.nextElementSibling !== lane) lastLane.after(lane);
      lastLane = lane;
    }
    let before = lane.firstElementChild;
    for (const { row, options } of members) {
      if (before === row) {
        before = row.nextElementSibling;
        continue;
      }
      const into = () => lane.insertBefore(row, before);
      if (options.move) options.move(into);
      else into();
    }
  }
  for (const [scroller, lane] of layer.lanes)
    if (!byLane.has(lane)) {
      lane.remove();
      layer.lanes.delete(scroller);
      layer.sizes.unobserve(scroller);
    }

  // A withheld row is anchored too, so that when its target comes into view it has only
  // to show. Its insets are written once packing has said where it stands.
  const px = (length) => (length ? `${length}px` : null);
  for (const { row, naming, shown, place, box, extent, top } of reads) {
    row.classList.toggle("lf-withheld", !shown);
    if (!naming) continue;
    setStyle(row, "position-anchor", nameAnchor(naming));
    if (row.dataset.lfPlace !== place) row.dataset.lfPlace = place;
    if (shown) continue;
    setStyle(row, "--lf-inset-top", px(extent && top - box.top));
    setStyle(row, "--lf-inset-right", px(extent && box.right - extent.right));
  }

  // Packing reads where each row stands with no push, then writes every push together.
  // Each row stands level with its target's top, or the row inside it its comment
  // pointed at, and a pin `--pin-inset` inside its right
  // edge, so where it will stand is worked out from the target rather than read back; only
  // its size and whether the browser took its anchor are read off the row.
  const placed = reads
    .filter((read) => read.shown)
    .map((read) => {
      const box = read.row.getBoundingClientRect();
      const step = steps.get(read.row) ?? 0;
      return {
        key: read.row,
        // At its off-screen fallback: the browser did not take the anchor.
        stranded: box.bottom + scrollY < -1000,
        rect: {
          left:
            read.place === "pin"
              ? read.extent.right - pinInset - box.width
              : box.left - step,
          right: read.place === "pin" ? read.extent.right - pinInset : box.right - step,
          top: read.top,
          bottom: read.top + box.height,
        },
        priority: read.options.priority ?? 0,
        read,
      };
    });
  for (const { key: row, stranded, read } of placed) {
    row.toggleAttribute("data-lf-parked", stranded);
    if (stranded) {
      parked.set(row, read.anchor);
      row.classList.toggle("lf-withheld", true);
    }
  }
  const standing = placed.filter(({ stranded }) => !stranded);
  seatPins(standing, { bands, shell, pinInset });
  const packed = packRows(standing, GAP);
  for (const { key: row, rect, read } of standing) {
    // Written as insets from the box the row anchors to, so the row keeps its place
    // beside its target through every scroll with no pass.
    setStyle(row, "--lf-inset-top", px(rect.top - read.box.top));
    setStyle(
      row,
      "--lf-inset-right",
      read.place === "pin" ? px(read.box.right - pinInset - rect.right) : null,
    );
    const push = packed.get(row) ?? 0;
    pushes.set(row, push);
    setStyle(row, "--lf-push", push ? `${push}px` : null);
    // A pin seated beside its target can stand outside what its pane shows though the
    // target is inside it, so a seated pin is withheld by where it stands.
    if (read.place === "pin")
      row.classList.toggle(
        "lf-withheld",
        !targetShown(
          read.target,
          read.extent,
          { top: rect.top + push, right: rect.right },
          bands,
        ),
      );
    // A rail row wider than the rail, unfolded or holding more than its resting budget,
    // steps back from the shell's edge rather than widening the page.
    const step = read.place === "rail" ? Math.min(0, shell - rect.right) : 0;
    steps.set(row, step);
    setStyle(row, "--lf-step", step ? `${step}px` : null);
  }

  // Each lane shows its region's rows only inside what that region shows, with room for a
  // focus ring, and across to the rail where the rail stands beside the region. The clip
  // is in the lane's own coordinates, so it is taken again whenever the pass runs, which
  // a resize of the region's box also brings.
  for (const [scroller, lane] of layer.lanes) {
    const region = regions.get(scroller);
    const at = lane.getBoundingClientRect();
    const ring = 6;
    const right = (stands && railBeside(scroller) ? shell : region?.right) + ring;
    const clip = region
      ? `polygon(${[
          [region.left - ring, region.top],
          [right, region.top],
          [right, region.bottom],
          [region.left - ring, region.bottom],
        ]
          .map(([x, y]) => `${layoutPx(x - at.left)} ${layoutPx(y - at.top)}`)
          .join(", ")})`
      : "polygon(0 0)";
    if (clips.get(lane) !== clip) {
      lane.style.clipPath = clip;
      clips.set(lane, clip);
    }
  }
  document.dispatchEvent(new CustomEvent("lf-margin-layout"));
}

export { scheduleMarginLayout };
