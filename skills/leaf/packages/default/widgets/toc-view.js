/* lf-toc's drawing: its frame and the outline of the headings in the document it
 * stands in. The initial renderer (`initial/lf-toc.js`) draws it before first paint, so
 * the widget first shows at the box it keeps, and the module redraws the outline in the
 * same nodes, adding the map's measurement and position to them (`lf-toc.js`).
 *
 * Before modules run, the runtime's readings of a heading are not there, so each caller
 * passes its own: `label` reads a heading's words and `chrome` whether it stands in
 * Leaf's chrome. The module reads them as the rest of the runtime does (`wrote`,
 * `inChrome`), and its first redraw rewrites any label the early reading said
 * differently. `place` puts the rows in order: the module's keeps the user standing in a
 * row that moves. Only the module lends ids (`lends`): the page's markup as it parsed is
 * the source a revision compares against (version.js), so the early drawing writes
 * nothing outside its host, and a destination without an id has no link until upgrade.
 */
export const HEADING_SELECTOR = "h1, h2, h3, h4, h5, h6";

// The outline is of the document it stands in: the page's `main`, or the part of a
// page made of parts that holds it (`data-lf-views="parts"`, lf-tabs.js).
export const outlineDocument = (host) =>
  host.closest('body > main > [data-lf-views="parts"] > *, main');

const said = (made, className) => {
  made.className = className;
  made.dataset.lfGen = "1";
  made.setAttribute("data-lf-said", "");
  made.textContent = "On this page";
  return made;
};

// The frame: a nav whose native disclosure holds the rows, the lens over their spine
// and the start row, which repeats the page title. Its labels are link apparatus
// rather than a second copy of the page's words, so the nav wears .lf-ui.
export function drawToc(host) {
  const doc = host.ownerDocument;
  const make = (tag, className) => {
    const made = doc.createElement(tag);
    if (className) made.className = className;
    return made;
  };
  const nav = make("nav", "lf-toc-nav lf-ui");
  nav.dataset.lfGen = "1";
  nav.setAttribute("aria-label", "On this page");
  const disclosure = make("details", "lf-toc-disclosure");
  const track = make("div", "lf-toc-rows");
  const lens = make("span", "lf-toc-window");
  lens.setAttribute("aria-hidden", "true");
  const start = make("div", "lf-toc-start");
  start.dataset.lfDepth = "0";
  const startLink = make("a");
  start.append(startLink);
  const list = make("ol");
  track.append(lens, start, list);
  disclosure.append(said(make("summary"), "lf-toc-toggle lf-label"), track);
  nav.append(said(make("p"), "lf-toc-heading lf-label"), disclosure);
  host.replaceChildren(nav);
  return {
    nav,
    track,
    lens,
    start: { row: start, link: startLink },
    list,
    rows: new Map(),
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

const level = (heading) => Number(heading.localName.slice(1));

/** Draw the outline into `drawing`, retaining each row by its heading's authored id or
 * node, and return its sections, the start first, or none where no heading qualifies.
 * max-level bounds the outline before any row is drawn or id lent.
 * @returns {{heading?: Element, label?: string, destination: Element, depth?: number, row: Element, link: Element}[]} */
export function drawOutline(host, drawing, { label, chrome, place, keeps, lends }) {
  const main = outlineDocument(host);
  if (!main) return [];
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
    ...drawing.start,
    destination: pageTitle
      ? destinationFor(host, pageTitle, 0, lends)
      : lend(host, main, 0, lends),
  };
  const href = ({ id }) => (id ? `#${id}` : null);
  keeps(start.link, "href", href(start.destination));
  const title = (pageTitle ? label(pageTitle) : "") || "Top";
  if (start.link.textContent !== title) start.link.textContent = title;

  const floor = Math.min(...headings.map(({ heading }) => level(heading)));
  const rows = new Map();
  const items = headings.map(({ heading, label }, index) => {
    const destination = destinationFor(host, heading, index + 1, lends);
    // A lent id is no key: the early drawing lent none, and the module adopts its rows.
    const key = heading.id && !heading.id.startsWith("lf-") ? heading.id : heading;
    let drawn = rows.has(key) ? null : drawing.rows.get(key);
    if (!drawn) {
      const row = host.ownerDocument.createElement("li");
      drawn = { row, link: row.appendChild(host.ownerDocument.createElement("a")) };
    }
    rows.set(key, drawn);
    const depth = Math.min(level(heading) - floor, 4);
    keeps(drawn.row, "data-lf-depth", depth);
    keeps(drawn.link, "href", href(destination));
    if (drawn.link.textContent !== label) drawn.link.textContent = label;
    return { heading, label, destination, depth, ...drawn };
  });
  drawing.rows = rows;
  place(
    drawing.list,
    items.map(({ row }) => row),
  );
  return items.length ? [start, ...items] : [];
}
