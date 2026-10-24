/* lf-toc's drawing: its frame and the outline of the headings in the document it
 * stands in. The initial renderer (`initial/lf-toc.js`) draws it before first paint, so
 * the widget first shows at the box it keeps, and the module redraws the outline in the
 * same nodes, adding the map's measurement and position to them (`lf-toc.js`).
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
  return {
    scope: () => outlineDocument(host),
    nav,
    track,
    lens: track.querySelector(".lf-toc-window"),
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
