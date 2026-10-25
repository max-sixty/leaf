/* lf-toc's drawing: its frame and the outline of the headings in the document it
 * stands in. The initial renderer (`initial/lf-toc.js`) draws it before first paint, so
 * the widget first shows at the box it keeps, and the module redraws the outline in the
 * same nodes (`lf-toc.js`). The margin map's layout, the disclosure's posture and each
 * row's span and fitted shift, is here too, so the initial renderer lays the map out
 * once the document has parsed and the module lays it out again as the document moves;
 * the module adds the lens and the current entry.
 *
 * Before modules run, the runtime's readings of a heading are not there, so each caller
 * passes its own: `label` reads a heading's words and `chrome` whether it stands in
 * Leaf's chrome. The module reads them as the rest of the runtime does (`wrote`,
 * `inChrome`), and its first redraw rewrites any label the early reading said
 * differently. Lit retains the keyed rows, and the module restores focus through moves.
 * Only the module lends ids (`lends`): the page's markup as it parsed is
 * the source a revision compares against (version.js), so the early drawing writes
 * nothing outside its host, and a destination without an id has no link until upgrade.
 */
import { html, nothing, render, repeat } from "/vendor/lit.js";

const HEADING_SELECTOR = "h1, h2, h3, h4, h5, h6";

// The outline belongs to the nearest declared view holding it, or the page's main.
// Scope follows document ownership, not visibility: closed disclosures still contribute
// headings that a native fragment link can reveal.
export const outlineDocument = (host) => host.closest("[data-lf-views] > *, main");

// The initial drawing keeps the template call sites and root part for its lifetime.
// Upgrading calls this same closure: importing another compiled copy of a template
// would make Lit replace the early nodes instead of updating their parts.
export function drawToc(host, generatedElement) {
  const open = host.hasAttribute("open");
  const href = (destination) => (destination?.id ? `#${destination.id}` : nothing);
  const paint = (start, items) =>
    render(
      html`
        <nav class="lf-toc-nav lf-ui scroll" aria-label="On this page">
          <p class="lf-toc-heading lf-label">On this page</p>
          <details class="lf-toc-disclosure" ?open=${open}>
            <summary class="lf-toc-toggle lf-label">On this page</summary>
            <div class="lf-toc-rows">
              <span class="lf-toc-window" aria-hidden="true"></span>
              <div class="lf-toc-start" data-lf-depth="0">
                <a href=${href(start.destination)}>${start.label}</a>
              </div>
              <ol>
                ${repeat(
                  items,
                  ({ key }) => key,
                  (item) => html`
                    <li data-lf-depth=${item.depth}>
                      <a href=${href(item.destination)}>${item.label}</a>
                    </li>
                  `,
                )}
              </ol>
            </div>
          </details>
        </nav>
      `,
      host,
    );
  host.replaceChildren();
  paint({ label: "Top" }, []);
  const nav = host.querySelector("nav");
  generatedElement(nav, { says: false });
  for (const label of nav.querySelectorAll(".lf-toc-heading, .lf-toc-toggle"))
    generatedElement(label, { says: true });
  const track = nav.querySelector(".lf-toc-rows");
  const startRow = track.querySelector(".lf-toc-start");
  const list = track.querySelector("ol");
  const disclosure = nav.querySelector("details");
  const summary = disclosure.querySelector("summary");
  // The in-flow open choice, held while the margin or paper form hides the summary.
  let flowOpen;
  return {
    scope: () => outlineDocument(host),
    nav,
    track,
    lens: track.querySelector(".lf-toc-window"),
    // CSS owns the posture. A hidden summary means the links are an always-exposed
    // outline, which needs the disclosure natively open in every engine, so it opens
    // and holds the in-flow choice; returning to flow restores that choice, or keeps
    // it open where `inRows()` says the user stands in a link.
    posture(inRows = () => false) {
      if (getComputedStyle(summary).display === "none") {
        flowOpen ??= disclosure.open;
        if (!disclosure.open) disclosure.open = true;
      } else if (flowOpen !== undefined) {
        const open = flowOpen || inRows();
        if (disclosure.open !== open) disclosure.open = open;
        flowOpen = undefined;
      }
    },
    // Lays the margin map out for `sections` (`update`'s rows): each shown row takes the
    // length of the section it leads as its flex share (`--lf-toc-span`), and crowded
    // labels are fitted around their markers (`fitLabels`). Returns where each section
    // starts in the coordinates of a scroller scrolled `scrollTop`, which of them the
    // document shows, where its content starts and ends, each marker's fitted place on
    // the map and the map's height, and whether the labels overflow it (`outline`).
    // The initial renderer lays the map out once the document has parsed, so the
    // spine first paints with its markers in place; the module lays it out again
    // whenever the document moves (`lf-toc.js`).
    measure(sections, scrollTop) {
      const main = outlineDocument(host);
      const top = (element) => viewportTop(element, main) + scrollTop;
      let previous = top(sections[0].destination);
      const shown = sections.map(
        ({ destination }) => destination === main || destination.checkVisibility(),
      );
      const positions = sections.map(({ destination }, index) => {
        const position = shown[index] ? Math.max(previous, top(destination)) : previous;
        previous = position;
        return position;
      });
      const contentEnd = Math.max(
        top(main) +
          main.clientTop +
          main.scrollHeight -
          parseFloat(getComputedStyle(main).paddingBottom),
        positions.at(-1) + 1,
      );
      sections.forEach(({ row }, index) => {
        row.toggleAttribute("data-lf-toc-hidden", !shown[index]);
        const nextVisible = shown.findIndex((seen, at) => at > index && seen);
        const next = nextVisible < 0 ? contentEnd : positions[nextVisible];
        row.style.setProperty(
          "--lf-toc-span",
          shown[index] ? String(Math.max(1, next - positions[index])) : "0",
        );
      });
      const fitted = fitLabels(host, track, nav, sections, shown);
      // A row's shift moves its label and dot (a transform and an inset), never the
      // row, so the rows are measured where they stand and each shift is written once.
      sections.forEach(({ row }, index) => {
        if (fitted.shifts.has(index))
          row.style.setProperty("--lf-toc-row-shift", `${fitted.shifts.get(index)}px`);
        else row.style.removeProperty("--lf-toc-row-shift");
      });
      return {
        shown,
        positions,
        contentStart: positions[0],
        contentEnd,
        mapPositions: fitted.mapPositions,
        mapHeight: fitted.mapHeight,
        outline: fitted.outline,
      };
    },
    update(reading) {
      const { start, items } = readOutline(host, reading);
      paint(start, items);
      const rows = [...list.children];
      return items.length
        ? [
            { ...start, row: startRow, link: startRow.firstElementChild },
            ...items.map((item, index) => ({
              ...item,
              row: rows[index],
              link: rows[index].firstElementChild,
            })),
          ]
        : [];
    },
  };
}

// A section's destination: the identified section it titles, where an eyebrow and
// heading arrive as one title and the public fragment names the section rather than
// its label; else the hgroup that owns its heading, so an eyebrow and title share one
// address and measured box, for h1 as for every level; else the heading. One without an
// id is lent an `lf-` id, which no reader of the page's ids takes for one its author
// wrote (`ADDRESSABLE`). The id goes on the destination rather than on an element
// inserted beside it, because an inserted element changes which child a page rule
// finds first or last and what an `h2 + p` rule finds next to the heading.
function destinationFor(host, heading, position, lends) {
  const section = heading.closest("section[id]");
  if (section?.querySelector(HEADING_SELECTOR) === heading) return section;
  const destination = heading.closest("hgroup") ?? heading;
  return lend(host, destination, position, lends);
}

function lend(host, destination, position, lends) {
  if (destination.id || !lends) return destination;
  const doc = host.ownerDocument;
  const stem = `lf-${host.id}-section-${position}`;
  let id = stem;
  let suffix = 2;
  while (doc.getElementById(id)) id = `${stem}-${suffix++}`;
  destination.id = id;
  return destination;
}

// Each fitted row's shift, by section index, and each shown label's fitted center on
// the map. Crowded destinations are fitted together just enough for their labels to
// stay distinct. Labels that fit the map's height only at one line each compact it
// (`data-lf-compact`), and labels taller than the map even then turn it into an
// ordinary open outline (`data-lf-outline`).
function fitLabels(host, track, nav, sections, shown) {
  const shifts = new Map();
  const mapPositions = [];
  host.removeAttribute("data-lf-compact");
  host.removeAttribute("data-lf-outline");
  if (getComputedStyle(track).display !== "flex")
    return { shifts, mapPositions, mapHeight: 1, outline: false };
  const box = track.getBoundingClientRect();
  const fitted = (outline = false) => ({
    shifts,
    mapPositions,
    mapHeight: box.height,
    outline,
  });

  const readLabels = () => {
    /** @type {{index: number, ideal: number, height: number, center: number, prefix?: number}[]} */
    const labels = sections.flatMap(({ row, link }, index) =>
      shown[index]
        ? [
            {
              index,
              ideal: row.getBoundingClientRect().top - box.top,
              height: link.getBoundingClientRect().height,
              center: parseFloat(getComputedStyle(link).lineHeight) / 2,
            },
          ]
        : [],
    );
    const lineHeight = parseFloat(getComputedStyle(nav).lineHeight);
    const preferredGap = Number.isFinite(lineHeight) ? lineHeight * 0.5 : 0;
    const labelHeight = labels.reduce((sum, label) => sum + label.height, 0);
    const firstCenter = labels[0]?.center ?? 0;
    const availableHeight = box.height + firstCenter;
    const availableGap =
      labels.length > 1 ? (availableHeight - labelHeight) / (labels.length - 1) : 0;
    return {
      labels,
      labelHeight,
      firstCenter,
      availableHeight,
      preferredGap,
      gap: Math.max(0, Math.min(preferredGap, availableGap)),
    };
  };

  let layout = readLabels();
  if (!layout.labels.length) return fitted();
  if (
    layout.labelHeight + layout.preferredGap * Math.max(0, layout.labels.length - 1) >
    layout.availableHeight + 1
  ) {
    host.setAttribute("data-lf-compact", "");
    layout = readLabels();
  }
  if (layout.labelHeight > layout.availableHeight + 1) {
    host.removeAttribute("data-lf-compact");
    host.setAttribute("data-lf-outline", "");
    return fitted(true);
  }

  let prefix = 0;
  for (const label of layout.labels) {
    label.prefix = prefix;
    prefix += label.height + layout.gap;
  }
  const occupiedHeight = Math.max(0, prefix - layout.gap);

  // Fit label boxes around their marker centers. A collision-free label top is its
  // document coordinate minus its first-line center and every preceding label's
  // height. Pool adjacent violations and share their correction, so a
  // crowded group bends one monotone scale around its destinations instead of
  // accumulating displacement below them.
  const blocks = [];
  layout.labels.forEach((label, at) => {
    blocks.push({
      start: at,
      end: at,
      top: label.ideal - label.center - label.prefix,
      count: 1,
    });
    while (blocks.length > 1 && blocks.at(-2).top > blocks.at(-1).top) {
      const next = blocks.pop();
      const previous = blocks.pop();
      const count = previous.count + next.count;
      blocks.push({
        start: previous.start,
        end: next.end,
        top: (previous.top * previous.count + next.top * next.count) / count,
        count,
      });
    }
  });

  const floor = -layout.firstCenter;
  const ceiling = box.height - occupiedHeight;
  for (const block of blocks) {
    const top = Math.max(floor, Math.min(ceiling, block.top));
    for (let at = block.start; at <= block.end; at += 1) {
      const label = layout.labels[at];
      const center = top + label.prefix + label.center;
      mapPositions[label.index] = center;
      shifts.set(label.index, center - label.ideal);
    }
  }
  return fitted();
}

// An element's top in the viewport: its own box, or the nearest ancestor's that has
// one, since a heading inside a collapsed box has none; else the main's.
function viewportTop(element, main) {
  for (let candidate = element; candidate; candidate = candidate.parentElement) {
    const box = candidate.getBoundingClientRect();
    if (box.width || box.height) return box.top;
    if (candidate === main) break;
  }
  return main.getBoundingClientRect().top;
}

const level = (heading) => Number(heading.localName.slice(1));

// Read the complete outline before rendering; max-level bounds it before any id is lent.
function readOutline(host, { label, chrome, lends }) {
  const main = outlineDocument(host);
  if (!main) return { start: { label: "Top" }, items: [] };
  const maxLevel = Number(host.getAttribute("max-level") ?? 6);
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
    label: (pageTitle ? label(pageTitle) : "") || "Top",
    destination: pageTitle
      ? destinationFor(host, pageTitle, 0, lends)
      : lend(host, main, 0, lends),
  };
  const floor = Math.min(...headings.map(({ heading }) => level(heading)));
  const items = headings.map(({ heading, label }, index) => {
    const destination = destinationFor(host, heading, index + 1, lends);
    // A lent id is no key: the early drawing lent none, and the module adopts its rows.
    const key = heading.id && !heading.id.startsWith("lf-") ? heading.id : heading;
    const depth = Math.min(level(heading) - floor, 4);
    return { key, heading, label, destination, depth };
  });
  return { start, items };
}
