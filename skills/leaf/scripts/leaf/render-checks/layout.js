import {
  openAsks,
  pageScroller,
  readingPosture,
  readingRegions,
  shownBand,
  shownRegionBounds,
  TEXT_BOX,
  uiInside,
} from "/runtime/widget-api.js";
import { laidOutItems } from "./framing.js";
import { at as element, place } from "./locate.js";
import { openRoots } from "./open-roots.js";
import { shrunkLabelReading } from "./words.js";

export const rootOverflow = () => pageScroller.scrollWidth - pageScroller.clientWidth;
const at = (el) => (el === pageScroller ? "<root scrollport>" : element(el));

// The page's own margin residents, without Leaf's rail: that holds only markers and
// never moves the column. Both a sweep sample and its breakpoint refinement read the
// tokens the margin layout publishes, rather than rediscovering residency from boxes.
export function marginResidents() {
  return (document.querySelector("main")?.getAttribute("data-lf-margin") ?? "")
    .split(" ")
    .filter((token) => token && token !== "rail")
    .join(" ");
}

// One settled-width geometry sample: the readings the gate reports across the width
// sweep, each field read by its own consumer in render_gate/readings.py. Which findings
// the gate answers for at every width is its choice, not a property of the reader:
// strandedMargins and reachabilityReading also move with the width, and the gate
// reports them only at the viewports it renders (validation.md). These readers are
// synchronous and read-only: taking them in one browser turn preserves their findings
// while removing the protocol round trips between fields. Resize and rendering
// completion belong to the caller, so a sample neither advances the page nor waits for
// a different layout.
export function geometryReading(open) {
  return {
    overflow: rootOverflow(),
    misplaced: misplacedBoxes(),
    margin: marginResidents(),
    arrangement: arrangedBoxes(open),
    panes: heldPanes(),
    regions: overflowingRegions(),
    labels: shrunkLabelReading(),
  };
}

// The fixed viewport's column and margin findings, before the table experiment
// temporarily changes wrapping. Keep singleton readers for callers asking one fact.
export function columnGeometry() {
  return {
    overflow: rootOverflow(),
    misplaced: misplacedBoxes(),
    stranded: strandedMargins(),
  };
}

// How the page's own arrangement stands: for each flex or grid box the page wrote (a
// Layout, or the page's own grid), how many of its items stand in each row. The walk goes
// through the widgets named in `open`, those whose content is the page's own markup or
// members, since a pane's or a tab's content is the page's; a widget's own box is the
// widget's business and is not read, and nothing Leaf generates is. Each box comes back
// with its place under `main`, a selector another load of the same page resolves to the
// same box, and the name every finding uses (locate.js).
export function arrangedBoxes(open) {
  const main = document.querySelector("main");
  if (!main) return [];
  const opens = new Set(open);
  const boxes = [];
  const walk = (el, path) => {
    if (el.matches(".lf-ui, [data-lf-gen]")) return;
    const widget = el.localName.includes("-");
    if (widget && !opens.has(el.localName)) return;
    if (!widget) boxes.push([el, path]);
    [...el.children].forEach((child, i) =>
      walk(child, `${path} > :nth-child(${i + 1})`),
    );
  };
  walk(main, "main");
  return boxes.flatMap(([box, path]) => {
    if (!/flex|grid/.test(getComputedStyle(box).display)) return [];
    const tops = laidOutItems(box)
      .map((item) => item.getBoundingClientRect())
      .filter((r) => r.width > 0 && r.height > 0)
      .map((r) => Math.round(r.top));
    if (tops.length < 2) return [];
    const rows = [];
    for (const top of tops) {
      const row = rows.find((r) => Math.abs(r.top - top) <= 2);
      if (row) row.count++;
      else rows.push({ top, count: 1 });
    }
    return [{ path, at: element(box), rows: rows.map((r) => r.count).join("+") }];
  });
}

// How a workspace holds the page's own panes: for each body of a `main.layout-workspace`
// that has panes the page wrote as its cells, whether the Layout fills the window
// (`--lf-full-height`, layouts.css) and the most of those panes that stand side by side, meaning
// how many share some stretch of the page's height. One is a column of panes; a grid with
// two stacked on the left of a tall third is two.
export function heldPanes() {
  const main = document.querySelector("main.layout-workspace");
  if (!main) return [];
  const held =
    getComputedStyle(main).getPropertyValue("--lf-full-height").trim() === "1";
  return [...main.children].flatMap((body) => {
    if (body.matches("header, footer")) return [];
    const rects = [...body.children]
      .filter((el) => el.matches(AUTHORED_PANE))
      .map((pane) => pane.getBoundingClientRect())
      .filter((r) => r.width > 0 && r.height > 0);
    if (rects.length < 2) return [];
    const beside = Math.max(
      ...rects.map(
        (r) => rects.filter((o) => o.top < r.bottom - 1 && r.top < o.bottom - 1).length,
      ),
    );
    return [
      { at: element(body), place: place(body), held, panes: rects.length, beside },
    ];
  });
}
const AUTHORED_PANE = '[data-lf-reading-role="pane"]:not([data-lf-generated])';

// Each region of a screen that runs past its room. A full-height workspace is a screen
// rather than a page to scroll (page-authoring.md, A workspace), so each region of it the
// page wrote is meant to show what it holds: a pane the page wrote, and the body itself,
// which the Layout marks (`--lf-reading-region: layout`, layouts.css). A bounded block
// declares that it scrolls, and a widget's own regions are its to hold, so neither is
// here. A workspace the window is too small to hold flows and scrolls as a page, and is
// no screen. Each comes back with its id, the name every finding uses, how far its
// body runs past its scrollport, and how many of the Asks still open to the user it
// holds: a region stacking several is a queue read as one long scroll.
export function overflowingRegions() {
  const main = document.querySelector("body > main.layout-workspace");
  if (
    !main ||
    getComputedStyle(main).getPropertyValue("--lf-full-height").trim() !== "1"
  )
    return [];
  const screenRegion = (host) =>
    host.matches(AUTHORED_PANE) ||
    (host.parentElement === main &&
      getComputedStyle(host).getPropertyValue("--lf-reading-region").trim() ===
        "layout");
  // Shown ones only: a queue's closed items hold open Asks too, and a region that
  // already is the queue is not stacking them.
  const asks = openAsks()
    .map((ask) => document.getElementById(ask.id))
    .filter((ask) => ask?.checkVisibility());
  return readingRegions().flatMap((region) => {
    if (!main.contains(region.host) || !screenRegion(region.host)) return [];
    if (!shownRegionBounds(region) || readingPosture(region) !== "bounded") return [];
    const over = region.body.scrollHeight - region.body.clientHeight;
    return over > 1
      ? [
          {
            id: region.id,
            at: element(region.host),
            over: Math.round(over),
            asks: asks.filter((ask) => region.body.contains(ask)).length,
          },
        ]
      : [];
  });
}

// Every box is drawn somewhere, and something has to answer for where. Three
// readings ask it — of the column, of the room the page keeps for a wide widget,
// and of the container that was handed a box's overflow — and the last two are
// written beside the loops that make them.
//
// The column first: content set outside the one it belongs to. The
// sideways-scroll reading is the same question asked of the window, and the
// window is the wider of the two: the gate renders at 1200px against a 720px
// column, so about 200px of margin beside it absorbs a spill that scrolls nothing.
// What is out there is the margin, where Leaf's rail and a page's notes stand, and the
// user's own window is free to be narrower than this one — so a page that passed
// here scrolls sideways on the machine it was written for.
//
// Two kinds of element answer for their own width and not to this, and both say
// so in their computed style. The margin has legitimate residents — a sidenote,
// the hidden line the paint pass writes, a page's own furniture — and
// each is out there by its own declaration: placed absolutely or fixed, or floated
// clear of the column. Where the box sits is what separates a resident from a spill,
// which crosses the column's edge rather than clearing it, having started inside
// and run out. So a float that merely overflows is still reported, and a widget's
// own float inside the column (an option's .facts rail) is never in question.
//
// A resident answers for what it holds, which is why both readings are made up the
// ancestors and not of the element alone. A sidenote is prose, so it carries the
// <code>, links and emphasis any other prose does, and each of those inherits a box
// its parent put in the margin on purpose — named, one by one, as spilling out of a
// column none of them was ever in.
//
// And a scroll container answers for what it holds: a box inside one runs on
// past the clip and is drawn only as far as its container reaches, so a wide
// table's own rows would otherwise be reported as spilling out of the table that
// is containing them. What is left is the flow, which the column is the whole
// width of. A spill is reported once, at the outermost element that has it,
// because everything inside one inherits its box and would name the same fault a
// dozen times over.
// What stands in the page's margin by its own declaration — placed absolutely or fixed,
// or floated clear of the column — for MISPLACED_BOXES, deciding whether a wide widget
// was drawn over one. A resident is whatever answered for itself out there, so a
// project hanging its own furniture in the margin is covered without declaring anything.

function marginReading(main) {
  const style = getComputedStyle(main);
  const box = main.getBoundingClientRect();
  const left = box.left + parseFloat(style.paddingLeft);
  const right = box.right - parseFloat(style.paddingRight);
  // Logical floats compute to whichever physical or logical token was written, so
  // resolve them against the element's own direction.
  const floatSide = (s) =>
    s.float === "left" || s.float === "right"
      ? s.float
      : (s.float === "inline-start") === (s.direction !== "rtl")
        ? "left"
        : "right";
  const isResident = (el, s = getComputedStyle(el), b = el.getBoundingClientRect()) => {
    // A fixed overlay that takes no presses at rest, such as the contents map, stands over
    // the page by design and reveals over it; it is a resident of the margin it starts in.
    if (s.position === "fixed" && s.pointerEvents === "none")
      return b.left < left - 1 || b.right > right + 1;
    if (s.position === "absolute" || s.position === "fixed")
      return b.right <= left + 1 || b.left >= right - 1;
    if (s.float === "none") return false;
    return floatSide(s) === "left" ? b.right <= left + 1 : b.left >= right - 1;
  };
  const residents = [...main.querySelectorAll("*")].filter((el) => {
    // A map's labels have boxes while its spine is at rest, but opacity and
    // pointer events keep them from occupying the margin until it opens.
    if (
      !el.checkVisibility({ opacityProperty: true, visibilityProperty: true }) ||
      el.hasAttribute("data-lf-space")
    )
      return false;
    const style = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    // Clipped to nothing is not standing in the margin: the words a page paints for
    // whoever is listening are a pixel wide and under a user's notice, so a widget
    // drawn across one has taken nothing from anybody.
    return box.width >= 2 && isResident(el, style, box);
  });
  return { isResident, left, residents, right };
}

// Overflow is acceptable only when the user can reach it or the box explicitly signals
// the cut. A scroll container may expose content in its scroll direction. `text-overflow`
// may signal omitted text. Plain clipping does not make content reachable.
// `misplacedBoxes`, `clippedControls`, and `coveredWords` enforce the distinct geometry,
// interaction, and text consequences.
//
// `tinyBoxes` ensures each declared widget upgrades to a usable box. `unreachableWords`
// catches rendered words outside reachable flow. `misplacedBoxes` asks each container's
// actual overflow behavior. Do not exempt a box merely because an ancestor declares
// `overflow`.
export function misplacedBoxes() {
  // shownBand is the runtime's own: what a container lets the user see of what it
  // holds, or nothing where it shows all of it. Imported rather than restated, so the
  // band a handover is refused against and the band the page paints to cannot come
  // apart — and because `overflow` is one of three ways to draw nothing past an edge.
  // (TRAPPED_MARGINS reads `contain` for the neighbouring question: which margins a
  // formatting context keeps in.)
  const main = document.querySelector("main");
  if (!main) return [];
  // The column belongs to the page. Visible Leaf chrome still has to fit it, but chrome
  // hidden with opacity or visibility has no box a user can lose. checkVisibility()
  // ignores both properties unless they are requested, which made a hidden margin label
  // look like compact-width overflow.
  const pageBox = (el) =>
    !uiInside(el, main) ||
    el.checkVisibility({ opacityProperty: true, visibilityProperty: true });
  const { isResident, left, residents, right } = marginReading(main);
  // A widget the registry declares wide is answered for out here, the way an
  // absolutely-positioned resident is: standing past the column is what it was
  // declared for. What still has to hold is the page's own box — the room the layout
  // measured is the column's leftover and the rail margin rows stand in, and an
  // exhibit over that edge is in the margin whether or not the window happened to
  // scroll for it. So the question is the same one, asked
  // against the wider bound: this gate renders at one viewport with no panel open, and
  // the user's window is free to be narrower than this one.
  const bodyStyle = getComputedStyle(document.body);
  const bodyBox = document.body.getBoundingClientRect();
  // Inside body's padding.
  const roomLeft = bodyBox.left + parseFloat(bodyStyle.paddingLeft);
  const roomRight = bodyBox.right - parseFloat(bodyStyle.paddingRight);
  // Both readings that hand a box to an ancestor ask shownBand, or a box inside a
  // container that clips without saying so in `overflow` is named for a spill it is
  // drawn nowhere near and left unnamed for the loss it did take, the walk at the foot
  // of this pass having gone straight past the container that cut it.
  const answeredFor = (el) => {
    if (isResident(el)) return true;
    for (let a = el.parentElement; a && a !== main; a = a.parentElement) {
      if (isResident(a)) return true;
      if (shownBand(a)) return true;
    }
    return false;
  };
  // The bound a descendant of a wide widget is held to. The column is the wrong one —
  // the room is exactly what the declaration granted, and several prose rows had all
  // been reported as standing out in the margin — but "answered for" is wrong too,
  // and wrong in the direction that costs: a child that paints past its own widget's
  // box does not grow that box, so exempting the subtree makes the widget's rect prove
  // something about itself alone. This read as answered while both wide widgets also
  // scrolled, `overflow-x: auto` having caught every descendant a line above.
  const insideWide = (el) => {
    for (let a = el.parentElement; a && a !== main; a = a.parentElement)
      if (a.hasAttribute("data-lf-space")) return a;
    return null;
  };
  // What a wide widget may not escape, whatever the page has room for: the nearest
  // thing between it and the column that draws a box of its own. Asked of the drawing
  // rather than of a list of tags, because the fault is visual and so is the property
  // — a widget that stands outside a frame, a tint or a fill reads as a broken page,
  // and one that grows through a transparent wrapper (a section, a tab's panel) reads
  // as the exhibit it is. A box that draws one says so where it draws it (--lf-block-frame,
  // theme.css) and the theme reads that declaration to withhold the room; this is what
  // says so when a box that draws hasn't made it. (Nothing to do with x-paints, which is
  // about words rather than boxes: an attribute rendered as paint instead of text, and
  // spoken for whoever is listening.)
  const draws = (el) => {
    const s = getComputedStyle(el);
    return (
      s.backgroundImage !== "none" ||
      !/^(transparent|rgba\(0, 0, 0, 0\))$/.test(s.backgroundColor) ||
      ["Top", "Right", "Bottom", "Left"].some(
        (side) =>
          parseFloat(s[`border${side}Width`]) > 0 && s[`border${side}Style`] !== "none",
      )
    );
  };
  const framing = (el) => {
    for (let a = el.parentElement; a && a !== main; a = a.parentElement)
      if (draws(a)) return a;
    return null;
  };
  const over = new Map();
  for (const el of main.querySelectorAll("*")) {
    const wide = el.hasAttribute("data-lf-space");
    // A wide widget is asked whatever it stands in, where everything else is excused
    // by a scroll container above it. The excuse is about the column — a box inside a
    // scroller is drawn only as far as the scroller reaches, so it cannot spill onto
    // the page — and a wide widget's question is a different one: it is measured
    // against the box that frames it, and a board scrolls, so every card on every
    // board was excused from the only reading that applies to it. A diagram in a card
    // was drawn across the neighbouring column and this said the page was clean.
    if (!pageBox(el) || !el.checkVisibility() || (!wide && answeredFor(el))) continue;
    const b = el.getBoundingClientRect();
    if (b.width < 1) continue;
    const frame = wide ? framing(el) : null;
    const host = wide ? null : insideWide(el);
    const bound = (frame || host)?.getBoundingClientRect() ?? null;
    const past =
      wide || host
        ? Math.round(
            Math.max(
              b.right - (bound ? bound.right : roomRight),
              (bound ? bound.left : roomLeft) - b.left,
            ),
          )
        : Math.round(Math.max(b.right - right, left - b.left));
    if (past > 1) over.set(el, [past, wide, frame, host]);
  }
  // Each finding carries its element's place (locate.js) and its kind beside the words,
  // so a reader that takes this pass at several widths (the gate's sweep) can tell one
  // fault met again from a new one without reading the sentence, whose pixel count
  // moves with the width.
  const found = [];
  const report = (el, kind, text) =>
    found.push({ at: at(el), place: place(el), kind, text });
  for (const [el, [past, wide, frame, host]] of over) {
    if ([...over.keys()].some((other) => other !== el && other.contains(el))) continue;
    if (host)
      report(
        el,
        "part",
        `${at(el)} stands ${past}px outside the ${at(host)} it is part of`,
      );
    else if (!wide)
      report(
        el,
        "column",
        `${at(el)} is set ${past}px past the column, out in the margin`,
      );
    else if (frame)
      report(
        el,
        "frame",
        `${at(el)} stands ${past}px outside the ${at(frame)} that frames it — ` +
          `declare --lf-block-frame: 1 in the rule that draws the frame, so the box ` +
          `holds the room in as well as the margins`,
      );
    else
      report(
        el,
        "room",
        `${at(el)} stands ${past}px past the room the page has for a wide widget`,
      );
  }
  // The room being the page's own box is not the whole of what a wide widget owes,
  // because the page hangs things in that box. A sidenote stands a gutter off the
  // column, while the strip it is reserved out of comes off the far edge of the page —
  // and those are the same place only when the column is flush against the strip, which
  // it never is, since it centres in what the strip leaves. So the reservation says
  // where the room ends and the occupancy says where the furniture is, and between them
  // is a band that is inside the page's box and already spoken for.
  //
  // The theme holds a wide widget's growth to what is free beside the page (--lf-free-l,
  // --lf-free-r), and this is what says so when a widget grows past it anyway — the same
  // bargain the framing rule above has, and the reason neither has to be a list anybody
  // maintains. A resident is whatever `marginReading` finds standing past the column, so
  // a project hanging its own furniture out there is covered without declaring anything
  // to this pass.
  for (const el of main.querySelectorAll("[data-lf-space]")) {
    if (!el.checkVisibility()) continue;
    const b = el.getBoundingClientRect();
    const hit = residents.find((r) => {
      if (el.contains(r) || r.contains(el)) return false;
      // An overlay that takes no presses at rest reveals over the page by design; the
      // room it takes at rest is what it states to the column's free room.
      const rs = getComputedStyle(r);
      if (rs.position === "fixed" && rs.pointerEvents === "none") return false;
      const c = r.getBoundingClientRect();
      return (
        b.left < c.right - 1 &&
        b.right > c.left + 1 &&
        b.top < c.bottom - 1 &&
        b.bottom > c.top + 1
      );
    });
    if (hit)
      report(
        el,
        "over",
        `${at(el)} is drawn over ${at(hit)}, which stands in the ` +
          `margin it grew into — the side that holds it gives no room`,
      );
  }
  // The other half of excusing a resident: an excuse is only good if the user can
  // see the thing. Both readings above hand a box to something else to answer for —
  // the margin it was placed in, the container that took its overflow — and the
  // second is worth exactly what the user can tell from that container. A scroller
  // answers for what ran out of it on the side it scrolls toward, scrollLeft running
  // from zero to the overflow and never the other way. A box that marks where it cut
  // answers for the rest, the mark being what says there is a rest. And a box that
  // only clips answers for nothing at all: what leaves a choose group, a board or a
  // table is drawn nowhere and said nowhere either, and every other reading here
  // calls such a page well — checkVisibility() is true of a clipped box, so screen
  // and print agree, and the copy withholds the clip and shows the words the live
  // page dropped. The user is the only party who loses them, which is why the
  // question is asked here, where the excuse was granted.
  //
  // Every box and not floats alone. A float is how a resident reaches the margin, so
  // it was the shape the failure first arrived in; the rule is about the excuse, and
  // a container grants that to whatever stands inside it. Held to floats it watched
  // one sidenote and let a question through: a row-form option 30px wider than the
  // group holding it carried every mark on it past the clip, and four of the examples
  // shipped a decision with no box to tick.
  //
  // Across the page and not down it, which is the axis every reading here takes: a
  // box cut off below its container is usually cut on purpose — a collapsed
  // disclosure, a shot's frame, a draft's box are all a height with the rest hidden —
  // where one cut off at the side never is.
  //
  // The nearest container and no further, because past it what an outer box sees is
  // that container's own edges, and the container answers the same question on its
  // own turn of the loop. The root scrollport is also where a float carried off the
  // leading edge of the window is named — the sideways reading, which reads how far
  // the page scrolls, cannot see one. Wholly inside, because a box half
  // in the clip is half unreadable: the group above leaves 7px of a 192px note
  // showing, which is nothing an "overlaps at all" reading would have objected to.
  const scrolls = (s) => /^(auto|scroll)$/.test(s.overflowX);
  const lost = new Map();
  // Up the containing blocks rather than the markup, since those are the boxes that
  // hold this one: an absolutely-placed box hangs off the nearest ancestor that
  // establishes one, and a static box it happens to be written inside clips it not at
  // all. offsetParent names that ancestor. Its own definition says positioned
  // ancestors, which reads as a gap — transform, filter, will-change, contain and
  // content-visibility each establish a containing block too — but Chrome returns
  // those as well, agreeing with where the box lands, so the property list a reader
  // reaches for here is already in the one call. A fixed box hangs off none of them.
  const holder = (el) => {
    const s = getComputedStyle(el);
    return s.position === "absolute"
      ? el.offsetParent
      : s.position === "fixed"
        ? null
        : el.parentElement;
  };
  for (const el of main.querySelectorAll("*")) {
    if (!pageBox(el) || !el.checkVisibility()) continue;
    // Nothing inside an <svg> is the page's flow: a foreignObject clips by its
    // nature, and diagram label boxes run an even 8px outside theirs on an
    // ordinary graph — the drawing's own accounting, not the page losing words.
    if (el.closest("svg")) continue;
    const b = el.getBoundingClientRect();
    if (b.width < 1) continue;
    let a = holder(el),
      band = null;
    for (; a; a = holder(a)) {
      band = shownBand(a);
      if (band) break;
    }
    if (!a) continue;
    const s = getComputedStyle(a);
    // text-overflow is the mark, declared in the rule that does the cutting, the
    // way --lf-block-frame is declared where the frame is drawn. The box itself still
    // answers here on its own turn.
    if (s.textOverflow !== "clip") continue;
    const overL = band.left - b.left,
      overR = b.right - band.right;
    // A scroller reaches its whole content on the side it scrolls toward, so only
    // its leading edge is asked — and asked from scroll position zero, since where
    // the container happens to be scrolled while the gate reads it says nothing
    // about where its content ends.
    const past = Math.round(
      !scrolls(s)
        ? Math.max(overL, overR)
        : s.direction === "rtl"
          ? overR + a.scrollLeft
          : overL - a.scrollLeft,
    );
    if (past > 1) lost.set(el, [past, a]);
  }
  for (const [el, [past, a]] of lost) {
    // Out of the same container, because that is what makes the outer box's report
    // the inner one's too. Suppressing on containment alone let a box lost 3px out
    // of one container hide the one hung off it and lost 400px out of another.
    if ([...lost].some(([o, [, its]]) => o !== el && its === a && o.contains(el)))
      continue;
    report(
      el,
      "hidden",
      `${at(el)} is drawn ${past}px outside ${at(a)}, which does not show it`,
    );
  }
  const texts = new Set();
  return found.filter(({ text }) => !texts.has(text) && texts.add(text));
}

// A table scrolling sideways with a cell in it wrapped. The theme's three cases for a
// table — take the measure only when asked, wrap the cells past that, scroll when even
// wrapping can't fit — are in order, and the third is reached through the second: a
// table scrolls once every column is at its minimum, and a column's minimum is its
// longest unbreakable run. So whatever wraps in a scrolling table wraps at a word a
// line, and the user gets both costs at once: prose a few words to the line down a
// 3174px table, and a scroller for the rest. What scrolls with nothing left to wrap
// (eight columns of single tokens) is the honest third case and passes.
//
// The finding states the widths and leaves the diagnosis to the author, because the
// widths carry it and a cause asserted here was wrong: a column of test names written
// outside <code> holds a table open at 583px beside prose at 118px, and twelve columns
// of ordinary prose hold one open at 87px each, and "squeezed by what cannot break" was
// said of both. So every column is listed with its width, and both remedies are offered.
//
// A column wraps when it stands wider with wrapping turned off, and that is the whole
// reading: every column of a scrolling table is at its longest unbreakable run, so a
// sheet turning wrapping off lets each column out to the width its content asked for,
// and the ones that move are the ones whose content had wrapped. The sheet says
// `text-wrap: nowrap` and not `white-space: nowrap`, because the shorthand also
// collapses white space and would have taken an author's newlines under a page rule
// setting cells `pre-wrap`; `flex-wrap: nowrap` beside it, because a milestone's chips
// stacked seven deep in a 114px cell with no text wrapping at all; `!important` on the
// descendants too, because a widget's own rule beats an inherited value — a draft's
// body is `pre-wrap` by the default package's sheet; and not on a text box, whose
// value wraps inside a box the table never sized. The gate reads its own page, so the
// probe changes nothing a user sees, and later readings measured the same before
// and after it.
//
// The column and not a row or a cell's glyphs, after three readings of line boxes,
// three of which glyphs are on the page, and one of row height each fell to a measured
// counterexample: an inline <code> is set at 84% and starts 3px lower on the same
// line; two lines' glyph boxes overlap at line-height 1; a closed details' body, an
// unselected tab and anything under content-visibility: hidden are laid out on demand
// and hand back real rects, so every reading of rects let some hidden line in or some
// painted line out; and a row is held tall by its tallest cell, so prose squeezed to
// a word a line beside a <br> list of names — the ordinary walkthrough table — read
// clean, and an image at width: 100% grew under the probe and hid the wrap beside it.
// None of that reaches a column's width: hidden content is size-contained and asks for
// nothing, a neighbour's height is not a width, a fixed-width block or a widget with a
// scroller of its own asks for exactly what it had, and a <br> line or a <pre> line is
// its own longest run. The remaining reach the probe lacks is stated so nobody looks
// for it here: a rule more specific than a tag name that says `!important` outranks
// it; a widget's shadow tree takes it by inheritance only, and a rule inside the tree
// beats that; a grid that flows its items onto more rows is a third kind of wrapping
// the sheet does not turn off; a cell an author caps with a max-width under its
// longest word, or fills with absolutely positioned words, asks for nothing more and
// wraps unreported. Each is a table cell holding something a leaf page has not yet
// put in one. A widget's own chrome in a cell never binds: a group's reply box sits
// inside the width its labels already ask for, measured.
//
// A column is where its cells stand rather than where they come in the row — a rowspan
// shifts the next row's cells over, a two-row header names a column twice — and a
// scrolling table's columns have edges that hold still, so cells are grouped by their
// left edge, in the table's reading direction, and named by the first column heading
// standing on it, a head's outranking a foot's; a heading's name is what it says, so
// a comment badge the mark pass put in it stays out, through the runtime's own
// `uiInside`. A cell that says `colspan`, whatever the number, belongs to no column,
// and the sheet leaves it wrapping — one predicate for both, since a `colspan="1"`
// read as a column by one and left wrapping by the other went unreported: a note
// across the whole table wraps because it is long, says nothing about a squeeze, and
// unwrapped would push every column it spans out and name them all.
// A cell in a hidden or collapsed row has no height. Read from `main`, where geometry
// is real.
//
// `squeezedTables` reports a table whose visible words stand outside its inner box with
// a cell in it wrapped. `scrollWidth` is the first reading, then the words decide it:
// Chromium can count a broken inline box a few pixels past the table even while every
// glyph fits, and that rounding artifact moves with the viewport and font metrics. In a
// genuinely scrolling table the columns are all at their longest unbreakable run, so a
// cell wrapping there wraps at a word a line — beside a name that could not break (an
// identifier written outside `<code>`, a bare URL), or because the table has more
// columns than the measure holds. A column wraps when it stands wider with wrapping
// turned off — its content asked for more than its longest run — which hidden content,
// laid out on demand but size-contained, cannot change. The finding lists the wrapping
// columns with their widths, names the widest, and leaves the diagnosis to the author.
// A table that scrolls with nothing left to wrap is the theme's honest third case.
export function squeezedTables() {
  const main = document.querySelector("main");
  if (!main) return [];
  // What a heading says, for the column's name.
  const says = (cell) => {
    let text = "";
    const walker = document.createTreeWalker(cell, NodeFilter.SHOW_TEXT);
    for (let node; (node = walker.nextNode());)
      if (!uiInside(node.parentElement, cell)) text += node.data;
    return text.trim().replace(/\s+/g, " ");
  };
  const wordsOutside = (table) => {
    const box = table.getBoundingClientRect();
    const left = box.left + table.clientLeft;
    const right = left + table.clientWidth;
    const range = document.createRange();
    for (const root of openRoots(table)) {
      const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
      for (let node; (node = walker.nextNode());) {
        const el = node.parentElement ?? node.parentNode.host;
        if (!node.data.trim() || uiInside(el, table)) continue;
        if (!el.checkVisibility({ opacityProperty: true, visibilityProperty: true }))
          continue;
        range.selectNodeContents(node);
        for (const drawn of range.getClientRects())
          if (drawn.width > 1 && (drawn.left < left - 1 || drawn.right > right + 1))
            return true;
      }
    }
    return false;
  };
  const tables = [...main.querySelectorAll("table")].filter(
    (t) => t.checkVisibility() && t.scrollWidth - t.clientWidth > 1 && wordsOutside(t),
  );
  // Each table's columns by left edge, each with its cells, before the probe.
  const read = new Map();
  for (const table of tables) {
    const columns = new Map();
    for (const cell of table.querySelectorAll("th, td")) {
      if (cell.closest("table") !== table || cell.hasAttribute("colspan")) continue;
      const box = cell.getBoundingClientRect();
      if (!box.height) continue;
      const left = Math.round(box.left);
      if (!columns.has(left))
        columns.set(left, { name: "", width: Math.round(box.width), cells: [] });
      const column = columns.get(left);
      const head = cell.closest("thead") !== null;
      if (
        cell.matches('th:not([scope="row"])') &&
        (!column.name || (head && !column.head))
      ) {
        column.name = `"${says(cell)}"`;
        column.head = head;
      }
      column.cells.push(cell);
    }
    const rtl = getComputedStyle(table).direction === "rtl";
    read.set(
      table,
      [...columns]
        .sort((a, b) => (rtl ? b[0] - a[0] : a[0] - b[0]))
        .map(([, c], i) => ({ ...c, name: c.name || `column ${i + 1}` })),
    );
  }
  const probe = document.createElement("style");
  probe.textContent =
    "th:not([colspan]), td:not([colspan])," +
    ` th:not([colspan]) *:not(${TEXT_BOX}), td:not([colspan]) *:not(${TEXT_BOX})` +
    " { text-wrap: nowrap !important; flex-wrap: nowrap !important }";
  document.head.append(probe);
  for (const columns of read.values())
    for (const column of columns)
      column.wraps = column.cells[0].getBoundingClientRect().width > column.width + 1;
  probe.remove();
  const found = [];
  for (const [table, columns] of read) {
    const wraps = columns.filter((c) => c.wraps);
    if (!wraps.length) continue;
    const short = table.scrollWidth - table.clientWidth;
    const top = Math.max(...columns.map((c) => c.width));
    const widest =
      columns.find((c) => c.width === top && c.wraps) ??
      columns.find((c) => c.width === top);
    found.push(
      `${at(table)} scrolls ${short}px sideways: ` +
        wraps.map((c) => `${c.name} wraps at ${c.width}px`).join(", ") +
        (widest.wraps ? "" : ` beside ${widest.name} at ${widest.width}px`) +
        ` — an identifier in <code> breaks inside its cell; a column fewer, or a` +
        ` shorter word in the widest, gives the rest the measure`,
    );
  }
  return found;
}

// A margin marker with nowhere to stand. The layout withholds a row whose anchor the
// browser will not take — an element behind the page's own `anchor-scope`, say — and marks
// it `data-lf-parked`, so the user has no marker for that element and the page has no
// way to show its thread or its decision beside it. Only the page can fix it: anchor the
// thread or the widget to an element in the page's flow.
export function strandedMargins() {
  return [...document.querySelectorAll(".lf-margin-cluster[data-lf-parked]")].map(
    (row) =>
      `the margin marker for ${row.lfTarget ? at(row.lfTarget) : row.dataset.lfMarginFor} ` +
      "has nowhere to stand: its element sits where a marker cannot anchor to it " +
      "(behind an anchor-scope, say), so the user sees no marker for it",
  );
}
