/* lf-toc: navigation derived from the headings the page already says, drawn by an Effect
 * UI component (runtime/effect-widget.js).
 *
 * The outline. `inputs` reads the document the outline covers: the view member holding
 * the widget, such as a tab's panel, or else the `main` holding it, or for contents
 * beside the page's main, that main. Scope follows document ownership, not visibility:
 * a closed disclosure still contributes headings a native fragment link can reveal. It
 * lists the h2–h6 headings outside Leaf's chrome (`.lf-chrome`) down to `max-level`, the
 * first h1 as the start row, and each row's destination (`destinationFor`), and reads
 * them again as a revision settles the page's interface (`lf-page-interface`) and as a
 * destination's id changes. Rows are keyed by their heading, so a revision that keeps a
 * heading, or replaces it with one of the same authored id or in the same identified
 * destination (`keyOf`), keeps its row's nodes, and focus on its link. Every link is a real fragment link: the browser owns its
 * navigation, history, :target state, wheel input and scroll restoration, and
 * hidden-until-found reveals a disclosure or tab containing the target. On an initial
 * load the shared arrival pass runs after all widgets settle, so it can honor a
 * generated target that did not exist during HTML parsing.
 *
 * Its forms. The box its track gives it chooses the form (toc.css): in flow, or in a
 * track stacked above or below the body, a native disclosure; beside the body with room
 * for words, an open outline; in a document's sidebar narrowed to the map's spine, a
 * reading map. The disclosure's open state is the browser's, the reader's own choice,
 * as root AGENTS.md has open disclosures: the view writes `open` only as the
 * disclosure arrives, so no draw, such as the one each step of reading starts, undoes a
 * press the Model would hear only with `toggle`, a task later. Where the form hides
 * its summary, the outline stands open (`FollowPosture` opens it through the node), and
 * returning to flow restores the reader's choice, unless a focused link needs to remain
 * reachable.
 *
 * The map (`FitMap`). Each section's marker stands at its section's place on the
 * document's scale, so the quiet spine describes the document before its labels appear
 * over the page. Crowded destinations are fitted together just enough for their labels
 * to remain distinct; destination marker, label, and viewport lens all use that one
 * fitted scale, and a route too long for its labels leaves its deepest levels off the
 * map (`fitLabels`). A marker's center is its coordinate; its label's first line is
 * centered there too, and the viewport lens reads those same coordinates. The first
 * label can extend above the track into the map's existing padding, rather than moving
 * the document's origin to make room for type. The labels keep their measure while faded
 * out, so revealing them neither moves the map nor refits it. A destination inside a
 * closed disclosure or inactive tab joins the map when it joins the displayed document.
 * The map is measured, as no CSS places a box at another box's place on a scale, and
 * only as the document, its destinations or the track change size, or a widget says its
 * layout moved (`lf-layout`): never for a scroll. The Mount writes the geometry it
 * measures onto the nodes the view drew, which the view leaves alone, in the same
 * callback that measured, so the map moves in the frame the document does.
 *
 * The darker lens is the part of the document in the viewport. The scroll moves it, as
 * a scroll-driven animation: its keyframes are the lens at each scroll position where
 * the map bends, and the browser interpolates between them as the scroller moves, so a
 * scroll writes nothing to the page.
 *
 * Where the reader is (`FollowReading`). The current section is the one whose words fill
 * most of the window. An IntersectionObserver on the headings hears each cross the
 * window's top half: the first heading in that half makes its section current, and
 * where none stands there the section above is current. A section reached by its link
 * lands at the window's top, so it is current however short it is. Of headings at one
 * position the last is current, and at the scroller's end the last one shown is. A
 * section off the map counts as the nearest one above it on the map. The user chose
 * this rule, Docusaurus's, over a line 32px below the window's top, which kept the
 * section above current while the new one filled the window. The lens and the current
 * entry follow the scroller of the document the outline covers, not the scroller of the
 * box the widget stands in: a sidebar's sticking track scrolls only its own contents and
 * usually stands at its scroll end, so an outline that read it marked the last section
 * as current at every scroll.
 *
 * Marks. Each row also marks where the page's open threads, its On Me items and, while
 * the changes view is on, its changes stand (toc-marks.js), and its link previews how
 * many of each its section holds. `inputs` reads them, so they draw again exactly when
 * those readings change. A row wears one mark, `data-lf-toc-mark`: `on-me` where its
 * section holds an On Me item, else `thread`. While the changes view is on,
 * `data-lf-toc-changed` marks a changed section. toc.css draws both on the outline's rule
 * or the map's spine; the start row's go on the outline's head too, its toggle or its
 * label, which stands where that row would where the row is left out. On the map, the
 * row's marker wears its marks instead, so they show while the labels rest faded out. A
 * section off the map starts no stretch, so its marks count in the row above it, as a
 * heading past `max-level` does. The marks are aria-hidden and take no room; what they
 * count, the row's link previews (`lfPreview`) in place of its name, which its face
 * already says, and that preview describes the link to a screen reader where focus
 * lands on it. */
import {
  Component,
  Effect,
  Equal,
  Html,
  Mount,
  Queue,
  Schema,
  Stream,
  UiSchema,
} from "/vendor/effect-ui.js";
import {
  comparisonChanges,
  landingInsets,
  named,
  readObligations,
  readThreads,
  scrollerFor,
  titledElement,
  whileConnected,
} from "/runtime/widget-api.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { cancelRender, nextRender, sizeObserver } from "/runtime/lib/frame-pass.js";
import { atLayoutPrecision, keeps, layoutPx } from "/runtime/lib/keeps.js";
import { closestAcross } from "/runtime/lib/shadow-tree.js";
import { marksWords, sectionMarks } from "./toc-marks.js";

type Marks = { threads: number; onMe: number; changes: number };
/** A row of the outline: the start row first, then each heading's. */
type Section = {
  key: string;
  label: string;
  href: string;
  depth: number;
  heading: Element | null;
  destination: Element;
};
type Row = Section & { marks: Marks };

// The lens is never shorter than this, or than 1.2% of the map, so it stays in sight.
const LENS_FLOOR = 14;
const HEADING_SELECTOR = "h1, h2, h3, h4, h5, h6";
const NO_MARKS: Marks = { threads: 0, onMe: 0, changes: 0 };

// ---------------------------------------------------------------------------
// The outline
// ---------------------------------------------------------------------------

/** The document the outline of the contents `host` covers. */
const outlineDocument = (host: HTMLElement) =>
  host.closest("[data-lf-views] > *, main") ??
  host.closest("body")?.querySelector(":scope > main") ??
  null;

// A section's destination: the outermost element its author identified above the
// heading, up to the element the heading titles (`titledElement`) and short of the
// document the outline covers, so the public fragment names the section or question the
// heading opens rather than its label; else the hgroup that owns its heading, so an
// eyebrow and title share one address and measured box, for h1 as for every level;
// else the heading. The outline's start row stands for the document it covers, so a
// heading leading a tab's view, whose document is the tab, links to its own place
// rather than to the tab. One without an id is lent an `lf-` id, which no reader of the
// page's ids takes for one its author wrote (`ADDRESSABLE`). The id goes on the
// destination rather than on an element inserted beside it, because an inserted
// element changes which child a page rule finds first or last and what an `h2 + p`
// rule finds next to the heading.
function destinationFor(
  host: HTMLElement,
  scope: Element,
  heading: Element,
  position: number,
) {
  const titled = titledElement(heading);
  let destination = heading.closest("hgroup") ?? heading;
  if (titled.contains(destination))
    for (let at = destination; at !== titled;) {
      at = at.parentElement as Element;
      if (at === scope) break;
      if (at.id && !at.id.startsWith("lf-")) destination = at;
    }
  return lend(host, destination, position);
}

function lend(host: HTMLElement, destination: Element, position: number) {
  if (destination.id) return destination;
  const stem = `lf-${host.id}-section-${position}`;
  let id = stem;
  let suffix = 2;
  while (host.ownerDocument.getElementById(id)) id = `${stem}-${suffix++}`;
  destination.id = id;
  return destination;
}

const level = (heading: Element) => Number(heading.localName.slice(1));

// A row's key, which its heading keeps for as long as it stands: the authored id of
// the heading, or else of its destination, when it first came, so a revision's new
// heading in that place, such as one of another level, takes the row of the one it
// replaces, or else a number of its own. A lent id is no key.
const keys = new WeakMap<Element, string>();
let unkeyed = 0;
const authored = (element: Element) =>
  element.id && !element.id.startsWith("lf-") ? `#${element.id}` : "";
function keyOf(heading: Element, destination: Element, taken: Set<string>) {
  let key = keys.get(heading) ?? (authored(heading) || authored(destination));
  while (!key || taken.has(key)) key = `@${unkeyed++}`;
  keys.set(heading, key);
  taken.add(key);
  return key;
}

/** The outline of the contents `host`: the document it covers and its rows, the start
 *  row first, or none where no heading below the title stands in it. `max-level`
 *  bounds it before any id is lent. */
export function readOutline(host: HTMLElement, label: (heading: Element) => string) {
  const main = outlineDocument(host);
  if (!main) return { main, sections: [] as Section[] };
  const maxLevel = Number(host.getAttribute("max-level") ?? 6);
  const chrome = (heading: Element) => closestAcross(heading, ".lf-chrome") !== null;
  const headings = [...main.querySelectorAll(HEADING_SELECTOR)]
    .filter(
      (heading) =>
        heading.localName !== "h1" &&
        !chrome(heading) &&
        !heading.closest("lf-toc") &&
        level(heading) <= maxLevel,
    )
    .map((heading) => ({ heading, label: label(heading) }))
    .filter((item) => item.label);
  if (!headings.length) return { main, sections: [] as Section[] };
  const title = [...main.querySelectorAll("h1")].find((h1) => !chrome(h1)) ?? null;
  const href = (destination: Element) => `#${destination.id}`;
  const startDestination = title
    ? destinationFor(host, main, title, 0)
    : lend(host, main, 0);
  const floor = Math.min(...headings.map(({ heading }) => level(heading)));
  const taken = new Set<string>();
  const sections: Section[] = [
    {
      key: "start",
      label: (title ? label(title) : "") || "Top",
      href: href(startDestination),
      depth: 0,
      heading: title,
      destination: startDestination,
    },
    ...headings.map(({ heading, label }, index) => {
      const destination = destinationFor(host, main, heading, index + 1);
      return {
        key: keyOf(heading, destination, taken),
        label,
        href: href(destination),
        depth: Math.min(level(heading) - floor, 4),
        heading,
        destination,
      };
    }),
  ];
  return { main, sections };
}

// What `inputs` keeps for each element: the observer that hears its destinations' ids
// change, which a reading of the outline points at the destinations it read.
const renames = new WeakMap<HTMLElement, MutationObserver>();
function renamesOf(element: HTMLElement, reread: () => void) {
  let renamed = renames.get(element);
  if (renamed) return renamed;
  renamed = new MutationObserver(reread);
  renames.set(element, renamed);
  const observer = renamed;
  whileConnected(element, (signal) => {
    document.addEventListener("lf-page-interface", reread, { signal });
    return () => observer.disconnect();
  });
  return renamed;
}

// ---------------------------------------------------------------------------
// The map: where each row stands on the document's scale
// ---------------------------------------------------------------------------

type Measured = { position: number; shown: boolean; mapPosition?: number };
type Size = { height: number; center: number };

/** The map of the rows `rows` drew, measured from the document as it lays out, and the
 *  lens, which the scroll moves. It reports the rows it leaves off the map. */
class MapFit {
  #rows: HTMLElement;
  #host: HTMLElement;
  #report: (offMap: readonly number[]) => void;
  #main: Element | null = null;
  #scroller: Element | null = null;
  #destinations: readonly Element[] = [];
  #depths: readonly number[] = [];
  #measured: Measured[] = [];
  #offMap: readonly number[] = [];
  #mapHeight = 1;
  #contentStart = 0;
  #contentEnd = 1;
  #lensMotion: { animation: Animation; effect: KeyframeEffect } | null = null;
  #sizes = sizeObserver(() => this.#measure());
  #frame = 0;
  #listening = new AbortController();
  #following: AbortController | null = null;

  constructor(rows: HTMLElement, report: (offMap: readonly number[]) => void) {
    this.#rows = rows;
    this.#host = rows.closest("lf-toc") as HTMLElement;
    this.#report = report;
    const signal = this.#listening.signal;
    // Presentation replaces the startup reading in its own turn, so the map it shows
    // has the replayed page's geometry.
    document.addEventListener("lf-presentation", () => this.#measure(), { signal });
    addEventListener("resize", this.#schedule, { signal });
  }

  follow(args: {
    main: Element | null;
    destinations: readonly Element[];
    depths: readonly number[];
  }) {
    this.#main = args.main;
    this.#scroller = args.main && scrollerFor(args.main);
    this.#destinations = args.destinations;
    this.#depths = args.depths;
    this.#following?.abort();
    this.#following = new AbortController();
    this.#sizes.disconnect();
    if (!args.main) return;
    // The complete destination reports section growth and title-group layout,
    // including an eyebrow changing size while its heading stays the same, and the
    // track the height the page's chrome can shorten without the document moving.
    for (const node of new Set([args.main, this.#rows, ...args.destinations]))
      this.#sizes.observe(node);
    const signal = this.#following.signal;
    args.main.addEventListener("toggle", this.#schedule, { capture: true, signal });
    args.main.addEventListener("lf-layout", this.#schedule, { signal });
  }

  close() {
    this.#listening.abort();
    this.#following?.abort();
    this.#sizes.disconnect();
    cancelRender(this.#frame);
    this.#lensMotion?.animation.cancel();
  }

  #schedule = () => {
    if (this.#frame) return;
    this.#frame = nextRender(() => {
      this.#frame = 0;
      this.#measure();
    });
  };

  #measure() {
    const main = this.#main,
      scroller = this.#scroller;
    if (!main || !scroller || !this.#rows.isConnected) return;
    const markers = this.#rows.querySelector(".lf-toc-markers") as HTMLElement;
    const [first] = this.#destinations;
    if (!first || getComputedStyle(markers).display === "none") {
      this.#host.removeAttribute("data-lf-compact");
      this.#measured = [];
      this.#write();
      this.#standLens();
      return;
    }
    const mainTop = documentTop(main, scroller, main);
    const start = documentTop(first, scroller, main);
    let previous = start;
    this.#measured = this.#destinations.map((destination) => {
      const shown = destination === main || destination.checkVisibility();
      const position = shown
        ? Math.max(previous, documentTop(destination, scroller, main))
        : previous;
      previous = position;
      return { shown, position };
    });
    this.#contentStart = start;
    this.#contentEnd = Math.max(
      mainTop +
        main.clientTop +
        main.scrollHeight -
        parseFloat(getComputedStyle(main).paddingBottom),
      previous + 1,
    );
    this.#fitLabels();
    this.#write();
    this.#standLens();
  }

  // The rows' nodes, in the outline's order: each one's label row, link and marker.
  #nodes() {
    const rows = this.#rows.querySelectorAll<HTMLElement>(
      ".lf-toc-start, .lf-toc-labels li",
    );
    const markers = this.#rows.querySelectorAll<HTMLElement>(".lf-toc-marker");
    return [...rows].map((row, index) => ({
      row,
      link: row.querySelector<HTMLElement>(":scope > a"),
      marker: markers.item(index),
    }));
  }

  // Each fitted row's place on the map, written once on its label and its marker, and
  // its marker's stretch of the spine, from it to the next marker or the map's end, on
  // the scale the lens shares, where a changed section is drawn (toc.css). A row off
  // the map wears `data-lf-toc-off`, which keeps its label's measure, hidden, so the
  // next fit reads it as it reads the rest.
  #write() {
    const nodes = this.#nodes();
    const offMap: number[] = [];
    let next = this.#mapHeight;
    for (let index = nodes.length - 1; index >= 0; index--) {
      const { row, link, marker } = nodes[index]!;
      const measured = this.#measured[index];
      const off = Boolean(measured && !measured.shown);
      if (off) offMap.unshift(index);
      for (const node of [link, marker])
        if (node) keeps(node, "data-lf-toc-off", off ? "" : null);
      const at = measured?.mapPosition;
      if (at === undefined) {
        for (const node of [row, marker]) node?.style.removeProperty("--lf-toc-at");
        marker?.style.removeProperty("--lf-toc-reach");
      } else {
        for (const node of [row, marker])
          node?.style.setProperty("--lf-toc-at", `${at}px`);
        marker?.style.setProperty("--lf-toc-reach", `${Math.max(0, next - at)}px`);
        next = at;
      }
    }
    if (
      offMap.length !== this.#offMap.length ||
      offMap.some((index, at) => index !== this.#offMap[at])
    ) {
      this.#offMap = offMap;
      this.#report(offMap);
    }
  }

  // Sets the place on the map, `mapPosition`, of each row that stands on it. A row's
  // place is its section's place on the document's scale, moved just enough to keep
  // the labels distinct. Labels that don't fit down the track at full size take a line
  // each in a smaller face. Where they don't fit even so, the deepest level of sections
  // leaves the map, then the next, each level trying both sizes again, until the rest
  // fit; where even the top level doesn't, as many of its sections stay as fit, spread
  // evenly from its first to its last. A section left out for room is off the map as
  // one whose heading is hidden is, so the current section is the nearest one above it
  // on the map, and its marks count in that row. The user chose this for a long route
  // over a list of every label scrolling over the map, at rest or following the
  // pointer, and over labels for the levels that fit with the other sections' labels
  // shown on hover: each kept every section on the map but showed its labels a second
  // way.
  #fitLabels() {
    const host = this.#host;
    host.removeAttribute("data-lf-compact");
    const track = this.#rows.getBoundingClientRect();
    this.#mapHeight = track.height;
    const links = this.#nodes().map(({ link }) => link);
    const rows = this.#measured
      .map((measured, index) => ({ measured, index }))
      .filter(({ measured, index }) => measured.shown && links[index])
      .map(({ measured, index }) => {
        const full = sizeOf(links[index]!);
        return {
          measured,
          depth: this.#depths[index] ?? 0,
          index,
          full,
          compact: full,
        };
      });
    if (!rows.length) return;
    const scale = track.height / Math.max(1, this.#contentEnd - this.#contentStart);
    const nav = this.#rows.closest("nav") as HTMLElement;
    const lineHeight = parseFloat(getComputedStyle(nav).lineHeight);
    const preferredGap = Number.isFinite(lineHeight) ? lineHeight * 0.5 : 0;
    let compactRead = false;
    // Whether these rows' labels fit down the track: at full size with the preferred
    // gap between them, or a line each with whatever gap is left.
    const fits = (kept: typeof rows, size: "full" | "compact") => {
      const gap = size === "full" ? preferredGap : 0;
      const height = kept.reduce((sum, row) => sum + row[size].height + gap, -gap);
      return height <= track.height + (kept[0]?.[size].center ?? 0) + 1;
    };
    // A label wraps by its own words alone, so one reading of each size serves every
    // set of rows.
    const sized = (kept: typeof rows): "full" | "compact" | undefined => {
      if (fits(kept, "full")) return "full";
      if (!compactRead) {
        host.setAttribute("data-lf-compact", "");
        for (const row of rows) row.compact = sizeOf(links[row.index]!);
        compactRead = true;
      }
      return fits(kept, "compact") ? "compact" : undefined;
    };
    const levels = [...new Set(rows.map((row) => row.depth))].sort((a, b) => b - a);
    let kept = rows;
    let size = sized(kept);
    for (const deepest of levels.slice(1)) {
      if (size) break;
      kept = rows.filter((row) => row.depth <= deepest);
      size = sized(kept);
    }
    if (!size) {
      const top = kept;
      // `count` of the top level's sections, spread evenly from its first to its last.
      const spread = (count: number) => {
        const picked = new Set(
          Array.from({ length: count }, (_, index) =>
            Math.round((index * (top.length - 1)) / Math.max(1, count - 1)),
          ),
        );
        return top.filter((_, index) => picked.has(index));
      };
      // The most that fit, found by halving: the first and last stay whatever the room.
      let fit = Math.min(2, top.length);
      let over = top.length;
      while (over - fit > 1) {
        const count = Math.floor((fit + over) / 2);
        if (sized(spread(count))) fit = count;
        else over = count;
      }
      kept = spread(fit);
      size = sized(kept) ?? "compact";
    }
    host.toggleAttribute("data-lf-compact", size === "compact");
    const standing = new Set(kept);
    for (const row of rows) if (!standing.has(row)) row.measured.shown = false;
    const fitted = size;
    const placing = kept.map((row) => ({
      measured: row.measured,
      ideal: (row.measured.position - this.#contentStart) * scale,
      ...row[fitted],
    }));
    const labelHeight = placing.reduce((sum, label) => sum + label.height, 0);
    const firstCenter = placing[0]?.center ?? 0;
    const gap =
      placing.length > 1
        ? Math.max(
            0,
            Math.min(
              preferredGap,
              (track.height + firstCenter - labelHeight) / (placing.length - 1),
            ),
          )
        : 0;
    let prefix = 0;
    const labels = placing.map((label) => {
      const placed = { ...label, prefix };
      prefix += label.height + gap;
      return placed;
    });
    const occupiedHeight = Math.max(0, prefix - gap);
    // Pool adjacent labels that overlap into one weighted block. Each block retains
    // its labels directly, so fitting needs no parallel index ranges.
    const blocks: { labels: typeof labels; top: number; count: number }[] = [];
    for (const label of labels) {
      let block = {
        labels: [label],
        top: label.ideal - label.center - label.prefix,
        count: 1,
      };
      let previous = blocks.at(-1);
      while (previous && previous.top > block.top) {
        blocks.pop();
        const count = previous.count + block.count;
        block = {
          labels: [...previous.labels, ...block.labels],
          top: (previous.top * previous.count + block.top * block.count) / count,
          count,
        };
        previous = blocks.at(-1);
      }
      blocks.push(block);
    }
    const floor = -firstCenter;
    const ceiling = track.height - occupiedHeight;
    for (const block of blocks) {
      const top = Math.max(floor, Math.min(ceiling, block.top));
      for (const label of block.labels)
        label.measured.mapPosition = top + label.prefix + label.center;
    }
  }

  #mapPosition(position: number) {
    const anchors: { documentPosition: number; mapPosition: number }[] = [];
    for (const { shown, position: documentPosition, mapPosition } of this.#measured) {
      if (!shown || mapPosition === undefined || !Number.isFinite(mapPosition))
        continue;
      if (anchors.at(-1)?.documentPosition === documentPosition) anchors.pop();
      anchors.push({ documentPosition, mapPosition });
    }
    const [first, ...rest] = anchors;
    if (!first) {
      const total = Math.max(1, this.#contentEnd - this.#contentStart);
      return (
        Math.max(0, Math.min(1, (position - this.#contentStart) / total)) *
        this.#mapHeight
      );
    }
    if (position <= first.documentPosition) return first.mapPosition;
    let previous = first;
    for (const next of rest) {
      if (position > next.documentPosition) {
        previous = next;
        continue;
      }
      const distance = Math.max(1, next.documentPosition - previous.documentPosition);
      const progress = (position - previous.documentPosition) / distance;
      return (
        previous.mapPosition + progress * (next.mapPosition - previous.mapPosition)
      );
    }
    const distance = Math.max(1, this.#contentEnd - previous.documentPosition);
    const progress = Math.max(
      0,
      Math.min(1, (position - previous.documentPosition) / distance),
    );
    return previous.mapPosition + progress * (this.#mapHeight - previous.mapPosition);
  }

  // The lens over the scroller's landing band, clear of whatever stands over its top
  // and the floating panel's row over its bottom: the scroll-driven keyframes between
  // the scroll positions where the map bends.
  #standLens() {
    const lens = this.#rows.querySelector(".lf-toc-window") as HTMLElement;
    const scroller = this.#scroller;
    if (!scroller || !this.#measured.some(({ shown }) => shown)) {
      this.#lensMotion?.animation.cancel();
      this.#lensMotion = null;
      keeps(lens, "style", "display: none;");
      return;
    }
    const clear = landingInsets(scroller);
    const reach = scroller.scrollHeight - scroller.clientHeight;
    const band = scroller.clientHeight - clear.top - clear.bottom;
    const floor = Math.max(LENS_FLOOR, this.#mapHeight * 0.012);
    const span = (scrolled: number) => {
      const start = this.#mapPosition(scrolled + clear.top);
      return {
        start,
        size: Math.max(start, this.#mapPosition(scrolled + clear.top + band)) - start,
      };
    };
    // Both at layout's 1/64px, so a measure that jitters below it writes nothing new.
    const transform = ({ start, size }: { start: number; size: number }) =>
      `translateY(${layoutPx(start)}) scaleY(${atLayoutPrecision(Math.max(floor, size))})`;
    if (reach <= 0) {
      this.#lensMotion?.animation.cancel();
      this.#lensMotion = null;
      keeps(lens, "style", `transform: ${transform(span(0))};`);
      return;
    }
    // The map is linear between the scroll positions where the band's top or foot
    // meets a destination or the document's ends, and where the lens meets its floor.
    const bends = [
      this.#contentStart,
      this.#contentEnd,
      ...this.#measured.map(({ position }) => position),
    ]
      .flatMap((position) => [position - clear.top, position - clear.top - band])
      .filter((scrolled) => scrolled > 0 && scrolled < reach);
    const stops = [...new Set([0, reach, ...bends])].sort((a, b) => a - b);
    const floored = stops.flatMap((scrolled, index) => {
      const next = stops[index + 1];
      if (next === undefined) return [scrolled];
      const [from, to] = [span(scrolled).size, span(next).size];
      if ((from - floor) * (to - floor) >= 0) return [scrolled];
      return [scrolled, scrolled + ((floor - from) / (to - from)) * (next - scrolled)];
    });
    const frames = floored.map((scrolled) => ({
      offset: scrolled / reach,
      transform: transform(span(scrolled)),
    }));
    keeps(lens, "style", null);
    if (this.#lensMotion) this.#lensMotion.effect.setKeyframes(frames);
    else {
      const effect = new KeyframeEffect(lens, frames, { fill: "both" });
      const animation = new Animation(
        effect,
        new ScrollTimeline({ source: scroller, axis: "block" }),
      );
      this.#lensMotion = { effect, animation };
      animation.play();
    }
  }
}

// A label's height and the middle of its first line in the face the map shows it in.
const sizeOf = (link: HTMLElement): Size => ({
  height: link.getBoundingClientRect().height,
  center: parseFloat(getComputedStyle(link).lineHeight) / 2,
});

// Where `element` stands in the scroller's document, or the nearest ancestor that has
// a box, up to `main`.
function documentTop(element: Element, scroller: Element, main: Element) {
  for (let at: Element | null = element; at; at = at.parentElement) {
    const box = at.getBoundingClientRect();
    if (box.width || box.height) return box.top + scroller.scrollTop;
    if (at === main) break;
  }
  return main.getBoundingClientRect().top + scroller.scrollTop;
}

// ---------------------------------------------------------------------------
// Where the reader is
// ---------------------------------------------------------------------------

type Place = { shown: boolean; top: number; above: boolean; inHalf: boolean };

/** Which row the reader is in, heard from the headings crossing the window's top half
 *  and from the scroller reaching its end. It reports the row's index. */
class Reading {
  #report: (current: number) => void;
  #headings: readonly (Element | null)[] = [];
  #places = new Map<Element, Place>();
  #observer: IntersectionObserver | null = null;
  #scroller: Element | null = null;
  #atEnd = false;
  #current = -1;
  #following: AbortController | null = null;

  constructor(report: (current: number) => void) {
    this.#report = report;
  }

  follow({
    main,
    headings,
  }: {
    main: Element | null;
    headings: readonly (Element | null)[];
  }) {
    this.#headings = headings;
    // What the observer last heard of each heading stands until it hears it again.
    const kept = new Set(headings);
    for (const heading of this.#places.keys())
      if (!kept.has(heading)) this.#places.delete(heading);
    this.#following?.abort();
    this.#following = new AbortController();
    this.#scroller = main && scrollerFor(main);
    if (!main || !this.#scroller) return;
    const scroller = this.#scroller;
    const signal = this.#following.signal;
    // Root scrolling is reported on Document; nested scrollports report on the element
    // itself. The root is this document, not the top window a framed page stands in.
    const root = scroller === document.scrollingElement ? document : scroller;
    root.addEventListener("scroll", this.#scrolled, {
      passive: true,
      signal,
    });
    // A disclosure or a tab that shows or hides a heading moves no heading across the
    // window's half, so the observer hears every heading again.
    const observe = () => {
      this.#observer?.disconnect();
      this.#observer = new IntersectionObserver((entries) => this.#heard(entries), {
        root,
        rootMargin: "0px 0px -50% 0px",
        threshold: [0, 1],
      });
      for (const heading of headings) if (heading) this.#observer.observe(heading);
    };
    main.addEventListener("toggle", observe, { capture: true, signal });
    main.addEventListener("lf-layout", observe, { signal });
    signal.addEventListener("abort", () => this.#observer?.disconnect());
    observe();
  }

  close() {
    this.#following?.abort();
  }

  #heard(entries: IntersectionObserverEntry[]) {
    const scrollTop = this.#scroller?.scrollTop ?? 0;
    for (const entry of entries) {
      const box = entry.boundingClientRect;
      const half = entry.rootBounds ?? { top: 0 };
      const shown = Boolean(box.width || box.height) && entry.target.checkVisibility();
      // Within two pixels of the window's top counts as there, since fractional layout
      // and scaled displays can stop a scroll that far short.
      const above = box.top < half.top - 2;
      this.#places.set(entry.target, {
        shown,
        top: box.top - half.top + scrollTop,
        above,
        inHalf: entry.isIntersecting && !above,
      });
    }
    this.#decide();
  }

  // Whether the scroller stands at its end, within two pixels.
  #end() {
    const scroller = this.#scroller;
    return Boolean(
      scroller &&
      scroller.scrollHeight - scroller.clientHeight - scroller.scrollTop <= 2,
    );
  }

  #scrolled = () => {
    if (this.#end() !== this.#atEnd) this.#decide();
  };

  #decide() {
    this.#atEnd = this.#end();
    const placed = this.#headings.map((heading, index) => ({
      index,
      place: heading ? this.#places.get(heading) : undefined,
    }));
    const shown = placed.filter(({ place }) => place?.shown);
    const inHalf = shown.filter(({ place }) => place?.inHalf);
    const [first] = inHalf;
    const current = this.#atEnd
      ? (shown.at(-1)?.index ?? 0)
      : first
        ? inHalf
            .filter(({ place }) => Math.abs(place!.top - first.place!.top) < 1)
            .at(-1)!.index
        : (shown.filter(({ place }) => place?.above).at(-1)?.index ?? 0);
    if (current === this.#current) return;
    this.#current = current;
    this.#report(current);
  }
}

// ---------------------------------------------------------------------------
// The component
// ---------------------------------------------------------------------------

const MarksSchema = Schema.Struct({
  threads: Schema.Number,
  onMe: Schema.Number,
  changes: Schema.Number,
});
const TocProps = Schema.Struct({
  ...widgetProps,
  main: Schema.NullOr(Schema.instanceOf(Element)),
  open: Schema.Boolean,
  sections: Schema.Array(
    Schema.Struct({
      key: Schema.String,
      label: Schema.String,
      href: Schema.String,
      depth: Schema.Number,
      heading: Schema.NullOr(Schema.instanceOf(Element)),
      destination: Schema.instanceOf(Element),
      marks: MarksSchema,
    }),
  ),
});

const TocModel = Schema.Struct({
  // Whether the author opened the disclosure, read once, as it arrives: from then on
  // its fold is the browser's.
  open: Schema.Boolean,
  // The row the reader is in, and the rows the map leaves off, by index.
  current: Schema.Number,
  offMap: Schema.Array(Schema.Number),
});

export const TocMessage = UiSchema.TaggedEnum({
  Read: { current: Schema.Number },
  Fitted: { offMap: Schema.Array(Schema.Number) },
});

// The summary's box coming and going, heard as the form hides it, so the outline stands
// open, and shows it again. As it hides, the disclosure's own state is the reader's
// last choice, kept for its return; while it stays hidden, a fold made from outside,
// as by a script, is that choice, and the outline stands open still; as it returns,
// that choice comes back, or the outline stays open where focus is on a link in it.
const FollowPosture = Mount.make("FollowPosture", {}, (summary: HTMLElement) =>
  Effect.gen(function* () {
    let exposed: boolean | undefined;
    let chosen = false;
    const details = summary.parentElement as HTMLDetailsElement;
    const folded = () => {
      if (!exposed || details.open) return;
      chosen = false;
      details.open = true;
    };
    details.addEventListener("toggle", folded);
    const sizes = sizeObserver(() => {
      const now = getComputedStyle(summary).display === "none";
      if (now === exposed) return;
      const was = exposed;
      exposed = now;
      let open = details.open;
      if (now) {
        chosen = details.open;
        open = true;
      } else if (was) {
        // A fold from outside whose `toggle` hasn't arrived is the reader's choice too.
        if (!details.open) chosen = false;
        const rows = details.querySelector(".lf-toc-rows");
        const focused = (summary.getRootNode() as Document | ShadowRoot).activeElement;
        open = chosen || Boolean(focused && rows?.contains(focused));
      }
      if (details.open !== open) details.open = open;
    });
    sizes.observe(summary);
    yield* Effect.addFinalizer(() =>
      Effect.sync(() => {
        sizes.disconnect();
        details.removeEventListener("toggle", folded);
      }),
    );
    return Component.noop;
  }),
);

const FitMap = Mount.makeStream(
  "FitMap",
  {
    args: {
      main: Schema.Unknown,
      destinations: Schema.Unknown,
      depths: Schema.Array(Schema.Number),
    },
  },
  (rows: HTMLElement, _args, changes) =>
    Stream.callback<readonly number[]>((queue) =>
      Effect.gen(function* () {
        const map = new MapFit(rows, (offMap) => Queue.offerUnsafe(queue, offMap));
        yield* Effect.addFinalizer(() => Effect.sync(() => map.close()));
        yield* Effect.forkScoped(
          Stream.runForEach(changes, (args: any) =>
            Effect.sync(() => map.follow(args)),
          ),
        );
      }),
    ),
);

const FollowReading = Mount.makeStream(
  "FollowReading",
  { args: { main: Schema.Unknown, headings: Schema.Unknown } },
  (_nav: HTMLElement, _args, changes) =>
    Stream.callback<number>((queue) =>
      Effect.gen(function* () {
        const reading = new Reading((current) => Queue.offerUnsafe(queue, current));
        yield* Effect.addFinalizer(() => Effect.sync(() => reading.close()));
        yield* Effect.forkScoped(
          Stream.runForEach(changes, (args: any) =>
            Effect.sync(() => reading.follow(args)),
          ),
        );
      }),
    ),
);

// The one mark a row wears, an On Me item outranking a thread.
const markKind = (marks: Marks) =>
  marks.onMe ? "on-me" : marks.threads ? "thread" : undefined;

// Each row's marks, with those of a row off the map counted in the nearest row above it
// on the map.
function standingMarks(rows: readonly Row[], offMap: ReadonlySet<number>) {
  const marks = rows.map(() => ({ ...NO_MARKS }));
  let standing = 0;
  rows.forEach((row, index) => {
    if (!offMap.has(index)) standing = index;
    const held = marks[standing]!;
    held.threads += row.marks.threads;
    held.onMe += row.marks.onMe;
    held.changes += row.marks.changes;
  });
  return marks;
}

export const Toc = Html.component({
  name: "Toc",
  props: TocProps,
  model: TocModel,
  message: TocMessage,
}).make({
  init: ($: any) => ({ open: $.props.open, current: 0, offMap: [] }),
  update: {
    Read: ($: any, { current }: { current: number }) => $.evolve({ current }),
    Fitted: ($: any, { offMap }: { offMap: readonly number[] }) => $.evolve({ offMap }),
  },
  view: (h: any, model: typeof TocModel.Type) => {
    const rows = h.props.sections as readonly Row[];
    const offMap = new Set(model.offMap);
    const marks = standingMarks(rows, offMap);
    let current = rows.length ? Math.min(model.current, rows.length - 1) : -1;
    while (current > 0 && offMap.has(current)) current--;
    const first = marks[0] ?? NO_MARKS;
    const changed = (held: Marks) => (held.changes ? "" : undefined);
    const markView = (held: Marks) =>
      markKind(held) ? h.span.class("lf-toc-mark").attr("aria-hidden", "true") : null;
    // A row's link previews its marks' counts alone, in place of the name its face
    // already says, so a room holding one line holds the counts, and a screen reader
    // hears them after the link's name; none where the row has none.
    const preview = (held: Marks) => () => {
      const words = marksWords(held);
      return words ? { name: words } : null;
    };
    // The disclosure and the outline beside the body leave the start row out, since
    // the page's title stands just above, below or beside them, so their head, the
    // toggle or the "On this page" label standing where that row would, carries its
    // marks and previews them while they show (toc.css), named for the place they
    // stand for, which its face doesn't say. The label takes no focus: the walks and
    // the Page Map reach what it counts by keyboard.
    const words = marksWords(first);
    function beforeFirst(this: Element) {
      return words && this.querySelector(":scope > .lf-toc-mark")?.checkVisibility()
        ? { name: "Before the first section", detail: [words] }
        : null;
    }
    const head = (node: any) =>
      node
        .attr("data-lf-gen", "1")
        .attr("data-lf-said", "")
        .attr("data-lf-toc-changed", changed(first))
        .attr("data-lf-toc-mark", markKind(first))
        .prop("lfPreview", beforeFirst)
        .children("On this page", markView(first));
    const link = (row: Row, index: number) =>
      h.a
        .class("lf-toc-link")
        .attr("href", row.href)
        .attr("aria-current", index === current ? "location" : undefined)
        .prop("lfPreview", preview(marks[index]!))
        .children(row.label);
    const [start, ...items] = rows;
    return h.nav
      .class("lf-toc-nav lf-ui")
      .attr("aria-label", "On this page")
      .attr("data-lf-gen", "1")
      .attr("data-lf-toc-empty", rows.length ? undefined : "")
      .onMount(
        FollowReading({
          main: h.props.main,
          headings: rows.map((row) => row.heading),
        }).pipe(Mount.map((current: number) => TocMessage.Read({ current }))),
      )
      .children(
        head(h.p.class("lf-toc-heading lf-label")),
        h.details
          .class("lf-toc-disclosure")
          .attr("open", model.open ? "" : undefined)
          .children(
            head(
              h.summary.class("lf-toc-toggle lf-label lf-disclosure-marker"),
            ).onMount(FollowPosture()),
            h.div
              .class("lf-toc-rows")
              .onMount(
                FitMap({
                  main: h.props.main,
                  destinations: rows.map((row) => row.destination),
                  depths: rows.map((row) => row.depth),
                }).pipe(
                  Mount.map((offMap: readonly number[]) =>
                    TocMessage.Fitted({ offMap }),
                  ),
                ),
              )
              .children(
                h.span.class("lf-toc-window").attr("aria-hidden", "true"),
                // A section's marker on the map's spine, which stands apart from its
                // label so the labels reveal as one layer: its depth sets its size, and
                // its marks ring it. The markers draw by position, so a heading whose
                // key changes keeps its marker.
                h.div
                  .class("lf-toc-markers")
                  .attr("aria-hidden", "true")
                  .children(
                    ...rows.map((row, index) =>
                      h.span
                        .class("lf-toc-marker")
                        .attr("data-lf-depth", String(row.depth))
                        .attr("data-lf-toc-changed", changed(marks[index]!))
                        .attr("data-lf-toc-mark", markKind(marks[index]!))
                        .attr("data-lf-current", index === current ? "" : undefined),
                    ),
                  ),
                h.div.class("lf-toc-labels").children(
                  start
                    ? h.div
                        .class("lf-toc-start")
                        .attr("data-lf-depth", "0")
                        .attr("data-lf-toc-changed", changed(first))
                        .attr("data-lf-toc-mark", markKind(first))
                        .children(link(start, 0), markView(first))
                    : null,
                  h.ol.children(
                    ...items.map((row, at) =>
                      h.li
                        .key(row.key)
                        .attr("data-lf-depth", String(row.depth))
                        .attr("data-lf-toc-changed", changed(marks[at + 1]!))
                        .attr("data-lf-toc-mark", markKind(marks[at + 1]!))
                        .children(link(row, at + 1), markView(marks[at + 1]!)),
                    ),
                  ),
                ),
              ),
          ),
      );
  },
});

defineWidget("lf-toc", Toc, {
  inputs: (element, reread) => {
    const renamed = renamesOf(element, reread);
    const { main, sections } = readOutline(element, named);
    // A node is the same input only as itself (effect-widget.js).
    for (const { heading, destination } of sections) {
      if (heading) Equal.byReferenceUnsafe(heading);
      Equal.byReferenceUnsafe(destination);
    }
    // Each row's link follows its destination's id, lent or authored.
    renamed.disconnect();
    for (const { destination } of sections)
      renamed.observe(destination, { attributeFilter: ["id"] });
    const marks =
      main && sections.length
        ? sectionMarks(main, sections, {
            threads: readThreads().threads,
            onMe: readObligations(main).user,
            changes: comparisonChanges(main),
          })
        : new Map();
    return {
      main,
      open: element.hasAttribute("open"),
      sections: sections.map((section) => ({
        ...section,
        marks: marks.get(section.heading) ?? NO_MARKS,
      })),
    };
  },
});
