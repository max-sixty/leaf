import { titledElement } from "/runtime/widget-api.js";
import { keeps } from "/runtime/lib/keeps.js";
import { closestAcross } from "/runtime/lib/shadow-tree.js";
/* The contents view draws its frame and outline from the complete document, less the
 * headings in Leaf's chrome (`.lf-chrome`). The live widget supplies the canonical
 * heading reading, and each section's marks (toc-marks.js). A row wears one mark, `data-lf-toc-mark`: `on-me`
 * where its section holds an On Me item, else `thread` where it holds an open thread.
 * While the changes view is on, `data-lf-toc-changed` marks a changed section. toc.css
 * draws both on the outline's rule or the contents spine; the start row's go on the
 * outline's head too, its toggle or its label, which stands where that row would where
 * the row is left out. On the map, the row's marker wears its marks instead, so they
 * show while the labels rest faded out. The marks are aria-hidden
 * and take no room; what they count, threads and On Me items alike, the row's link
 * previews (`lfPreview`) in place of its name, which its face already says, and that
 * preview describes the link to a screen reader where focus lands on it. */
import { html, nothing, repeat } from "/vendor/lit.js";
import { marksWords } from "./toc-marks.js";

/** @typedef {{label: (heading: Element) => string}} HeadingReading */
/** @typedef {{key: string | Element, heading: Element, label: string, destination: Element, depth: number}} OutlineItem */
/** @typedef {{start: {label: string, destination: Element, heading: Element | null} | null, items: OutlineItem[]}} Outline */
/** @typedef {import("./toc-marks.js").SectionMarks} SectionMarks */
const HEADING_SELECTOR = "h1, h2, h3, h4, h5, h6";

// The one mark a row wears, an On Me item outranking a thread, and the dot the outline
// draws it with on its rule (toc.css), where the map draws it round the row's marker.
/** @param {SectionMarks | undefined} marks */
const markKind = (marks) =>
  marks?.onMe ? "on-me" : marks?.threads ? "thread" : nothing;
// A section's marker on the map's spine (toc.css), which stands apart from its label so
// the labels reveal as one layer: its depth sets its size, and its marks ring it. Lit
// draws only those, and the widget writes a marker's place and state by its index at
// each measure (lf-toc.js), so the markers render by position: a heading whose key
// changes keeps its marker rather than taking an equal new one. A marker and a link
// are drawn `data-lf-toc-shown`, which the widget takes off a section it leaves off the
// map at each measure, so a new row shows, and its link takes focus, before the map has
// measured it.
/** @param {SectionMarks | undefined} marks @param {number} depth */
const markerView = (marks, depth) =>
  html`<span
    class="lf-toc-marker"
    data-lf-toc-shown
    data-lf-depth=${depth}
    ?data-lf-toc-changed=${Boolean(marks?.changes)}
    data-lf-toc-mark=${markKind(marks)}
  ></span>`;
/** @param {SectionMarks | undefined} marks */
const markView = (marks) =>
  markKind(marks) === nothing
    ? nothing
    : html`<span class="lf-toc-mark" aria-hidden="true"></span>`;

// The outline belongs to the document holding it: the view member holding it, such as
// a tab's panel, or else the `main` holding it. For contents standing beside the page's
// main, it is that main. Scope follows document ownership, not visibility: closed
// disclosures still contribute headings that a native fragment link can reveal.
/** @param {HTMLElement} host */
const outlineDocument = (host) =>
  host.closest("[data-lf-views] > *, main") ??
  host.closest("body")?.querySelector(":scope > main") ??
  null;

// The template keeps its native disclosure and keyed links. Geometry readers collect
// the nodes only after it renders.
/** @param {HTMLElement} host @param {HeadingReading} [headingReading] */
export function drawToc(host, headingReading) {
  const open = host.hasAttribute("open");
  /** @type {Outline} */
  let outline = { start: null, items: [] };
  const href = (/** @type {Element | undefined} */ destination) =>
    destination?.id ? `#${destination.id}` : nothing;
  /** @type {ReadonlyMap<Element | null, SectionMarks>} */
  let marks = new Map();
  // One preview for each row's link, kept as long as its heading, which reads the row's
  // marks as it shows: their counts alone, in place of the name the link's face already
  // says, so a room holding one line holds the counts, and a screen reader hears them
  // after the link's name; none where the row has none, so the link previews nothing.
  /** @param {Element | null} heading */
  const preview = (heading) => () => {
    const words = marksWords(marks.get(heading));
    return words ? { name: words } : null;
  };
  /** @type {WeakMap<Element, ReturnType<typeof preview>>} */
  const previews = new WeakMap();
  const untitled = preview(null);
  /** @param {Element | null} heading */
  const previewOf = (heading) => {
    if (!heading) return untitled;
    let kept = previews.get(heading);
    if (!kept) previews.set(heading, (kept = preview(heading)));
    return kept;
  };
  // The disclosure and the outline beside the body leave the start row out, since the
  // page's title stands just above, below or beside them, so their head, the toggle or
  // the "On this page" label standing where that row would, carries its marks and
  // previews them while they show (toc.css), named for the place they stand for, which
  // its face doesn't say. The label takes no focus: the walks and the Page Map reach
  // what it counts by keyboard.
  /** @this {Element} */
  function beforeFirst() {
    const words = marksWords(marks.get(outline.start?.heading ?? null));
    return words && this.querySelector(":scope > .lf-toc-mark")?.checkVisibility()
      ? { name: "Before the first section", detail: [words] }
      : null;
  }
  host.replaceChildren();
  /** @type {ReturnType<typeof readFrame> | undefined} */
  let frame;
  const readFrame = () => {
    const nav = host.querySelector("nav");
    /** @type {HTMLElement | null} */
    const track = host.querySelector(".lf-toc-rows");
    /** @type {HTMLElement | null} */
    const lens = host.querySelector(".lf-toc-window");
    /** @type {HTMLElement | null} */
    const markers = host.querySelector(".lf-toc-markers");
    const disclosure = nav?.querySelector("details");
    const summary = disclosure?.querySelector("summary");
    if (!nav || !track || !lens || !markers || !disclosure || !summary)
      throw new Error("Contents did not draw its frame");
    return { nav, track, lens, markers, disclosure, summary };
  };
  const native = () => (frame ??= readFrame());
  return {
    scope: () => outlineDocument(host),
    get nav() {
      return native().nav;
    },
    get track() {
      return native().track;
    },
    get lens() {
      return native().lens;
    },
    get markers() {
      return native().markers;
    },
    get disclosure() {
      return native().disclosure;
    },
    get summary() {
      return native().summary;
    },
    /** Each section's marks, by its heading, which the next render draws.
     * @param {ReadonlyMap<Element | null, SectionMarks>} next */
    mark(next) {
      marks = next;
    },
    /** The frame and outline, read again from the document with `reading`, or as last
     *  read with null.
     * @param {HeadingReading | null} [reading] */
    render(reading = headingReading) {
      if (reading) {
        outline = readOutline(host, reading);
        keeps(host, "data-lf-toc-empty", outline.items.length ? null : "");
      }
      const { start, items } = outline;
      const first = marks.get(start?.heading ?? null);
      return html`
        <nav class="lf-toc-nav lf-ui" aria-label="On this page" data-lf-gen="1">
          <p
            class="lf-toc-heading lf-label"
            data-lf-gen="1"
            data-lf-said
            ?data-lf-toc-changed=${Boolean(first?.changes)}
            data-lf-toc-mark=${markKind(first)}
            .lfPreview=${beforeFirst}
          >
            On this page${markView(first)}
          </p>
          <details class="lf-toc-disclosure" ?open=${open}>
            <summary
              class="lf-toc-toggle lf-label lf-disclosure-marker"
              data-lf-gen="1"
              data-lf-said
              ?data-lf-toc-changed=${Boolean(first?.changes)}
              data-lf-toc-mark=${markKind(first)}
              .lfPreview=${beforeFirst}
            >
              On this page${markView(first)}
            </summary>
            <div class="lf-toc-rows">
              <span class="lf-toc-window" aria-hidden="true"></span>
              <div class="lf-toc-markers" aria-hidden="true">
                ${markerView(first, 0)}${items.map((item) =>
                  markerView(marks.get(item.heading), item.depth),
                )}
              </div>
              <div class="lf-toc-labels">
                <div
                  class="lf-toc-start"
                  data-lf-depth="0"
                  ?data-lf-toc-changed=${Boolean(first?.changes)}
                  data-lf-toc-mark=${markKind(first)}
                >
                  <a
                    class="lf-toc-link"
                    data-lf-toc-shown
                    href=${href(start?.destination)}
                    .lfPreview=${previewOf(start?.heading ?? null)}
                    >${start?.label ?? "Top"}</a
                  >${markView(first)}
                </div>
                <ol>
                  ${repeat(
                    items,
                    ({ key }) => key,
                    (item) => html`
                      <li
                        data-lf-depth=${item.depth}
                        ?data-lf-toc-changed=${Boolean(
                          marks.get(item.heading)?.changes,
                        )}
                        data-lf-toc-mark=${markKind(marks.get(item.heading))}
                      >
                        <a
                          class="lf-toc-link"
                          data-lf-toc-shown
                          href=${href(item.destination)}
                          .lfPreview=${previewOf(item.heading)}
                          >${item.label}</a
                        >${markView(marks.get(item.heading))}
                      </li>
                    `,
                  )}
                </ol>
              </div>
            </div>
          </details>
        </nav>
      `;
    },
    sections() {
      const { start, items } = outline;
      if (!start || !items.length) return [];
      /** @type {HTMLElement | null} */
      const startRow = host.querySelector(".lf-toc-start");
      const list = host.querySelector("ol");
      if (!list) throw new Error("Contents did not draw its outline");
      /** @type {NodeListOf<HTMLLIElement>} */
      const rows = list.querySelectorAll(":scope > li");
      /** @type {NodeListOf<HTMLElement>} */
      const markers = host.querySelectorAll(".lf-toc-marker");
      /** @param {HTMLElement | null | undefined} row @param {number} index */
      const parts = (row, index) => {
        const link = row?.querySelector("a");
        const marker = markers.item(index);
        if (!row || !link || !marker)
          throw new Error("Contents did not draw a section link");
        return { row, link, marker };
      };
      return [
        { ...start, ...parts(startRow, 0) },
        ...items.map((item, index) => ({
          ...item,
          ...parts(rows.item(index), index + 1),
        })),
      ];
    },
  };
}

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
/** @param {HTMLElement} host @param {Element} scope the document the outline covers
 * @param {Element} heading @param {number} position */
function destinationFor(host, scope, heading, position) {
  const titled = titledElement(heading);
  let destination = heading.closest("hgroup") ?? heading;
  if (titled.contains(destination))
    for (let at = destination; at !== titled;) {
      at = /** @type {Element} */ (at.parentElement);
      if (at === scope) break;
      if (at.id && !at.id.startsWith("lf-")) destination = at;
    }
  return lend(host, destination, position);
}

/** @param {HTMLElement} host @param {Element} destination @param {number} position */
function lend(host, destination, position) {
  if (destination.id) return destination;
  const doc = host.ownerDocument;
  const stem = `lf-${host.id}-section-${position}`;
  let id = stem;
  let suffix = 2;
  while (doc.getElementById(id)) id = `${stem}-${suffix++}`;
  destination.id = id;
  return destination;
}

/** @param {Element} heading */
const level = (heading) => Number(heading.localName.slice(1));

// Read the complete outline before rendering; max-level bounds it before any id is lent.
/** @param {HTMLElement} host @param {HeadingReading} reading @returns {Outline} */
function readOutline(host, { label }) {
  const main = outlineDocument(host);
  if (!main) return { start: null, items: [] };
  const maxLevel = Number(host.getAttribute("max-level") ?? 6);
  /** @param {Element} heading */
  const chrome = (heading) => closestAcross(heading, ".lf-chrome") !== null;
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
  const pageTitle = [...main.querySelectorAll("h1")].find(
    (candidate) => !chrome(candidate),
  );
  const start = {
    heading: pageTitle ?? null,
    label: (pageTitle ? label(pageTitle) : "") || "Top",
    destination: pageTitle
      ? destinationFor(host, main, pageTitle, 0)
      : lend(host, main, 0),
  };
  const floor = Math.min(...headings.map(({ heading }) => level(heading)));
  const items = headings.map(({ heading, label }, index) => {
    const destination = destinationFor(host, main, heading, index + 1);
    // A lent id is no key: row identity follows the authored heading.
    const key = heading.id && !heading.id.startsWith("lf-") ? heading.id : heading;
    const depth = Math.min(level(heading) - floor, 4);
    return { key, heading, label, destination, depth };
  });
  return { start, items };
}
