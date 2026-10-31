import { generatedElement, keeps } from "/runtime/widget-api.js";
/* The contents view draws its frame and outline from the complete document.
 * The live widget supplies the canonical heading and chrome readings. */
import { html, nothing, ref, repeat } from "/vendor/lit.js";

const HEADING_SELECTOR = "h1, h2, h3, h4, h5, h6";

// The outline belongs to the nearest declared view holding it, or the page's main.
// Scope follows document ownership, not visibility: closed disclosures still contribute
// headings that a native fragment link can reveal.
export const outlineDocument = (host) => host.closest("[data-lf-views] > *, main");

// Delivery and live behavior call this same template, retaining its native disclosure
// and keyed links. Geometry readers collect the nodes only after its shared render.
export function drawToc(host, headingReading) {
  const open = host.hasAttribute("open");
  let outline = { start: { label: "Top" }, items: [] };
  const href = (destination) => (destination?.id ? `#${destination.id}` : nothing);
  const generated = (says) => ref((node) => node && generatedElement(node, { says }));
  host.replaceChildren();
  return {
    scope: () => outlineDocument(host),
    get nav() {
      return host.querySelector("nav");
    },
    get track() {
      return host.querySelector(".lf-toc-rows");
    },
    get lens() {
      return host.querySelector(".lf-toc-window");
    },
    render(reading = headingReading) {
      if (reading) {
        outline = readOutline(host, reading);
        keeps(host, "data-lf-toc-empty", outline.items.length ? null : "");
      }
      const { start, items } = outline;
      return html`
        <nav
          class="lf-toc-nav lf-ui scroll"
          aria-label="On this page"
          ${generated(false)}
        >
          <p class="lf-toc-heading lf-label" ${generated(true)}>On this page</p>
          <details class="lf-toc-disclosure" ?open=${open}>
            <summary class="lf-toc-toggle lf-label" ${generated(true)}>
              On this page
            </summary>
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
      `;
    },
    sections() {
      const { start, items } = outline;
      const startRow = host.querySelector(".lf-toc-start");
      const rows = [...host.querySelector("ol").children];
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
    // A lent id is no key: row identity follows the authored heading.
    const key = heading.id && !heading.id.startsWith("lf-") ? heading.id : heading;
    const depth = Math.min(level(heading) - floor, 4);
    return { key, heading, label, destination, depth };
  });
  return { start, items };
}
