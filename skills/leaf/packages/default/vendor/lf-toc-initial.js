(() => {
  // skills/leaf/packages/default/widgets/toc-view.js
  var HEADING_SELECTOR = "h1, h2, h3, h4, h5, h6";
  var outlineDocument = (host) => host.closest('body > main > [data-lf-views="parts"] > *, main');
  var said = (made, className) => {
    made.className = className;
    made.dataset.lfGen = "1";
    made.setAttribute("data-lf-said", "");
    made.textContent = "On this page";
    return made;
  };
  function drawToc(host) {
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
      rows: /* @__PURE__ */ new Map()
    };
  }
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
  var level = (heading) => Number(heading.localName.slice(1));
  function drawOutline(host, drawing, { label, chrome, place, keeps, lends }) {
    const main = outlineDocument(host);
    if (!main) return [];
    const maxLevel = Number(host.getAttribute("max-level") ?? 6);
    const headings = [...main.querySelectorAll(HEADING_SELECTOR)].filter(
      (heading) => heading.localName !== "h1" && !chrome(heading) && !heading.closest("lf-toc") && level(heading) <= maxLevel
    ).map((heading) => ({ heading, label: label(heading) })).filter((item) => item.label);
    const pageTitle = [...main.querySelectorAll("h1")].find(
      (candidate) => !chrome(candidate)
    );
    const start = {
      ...drawing.start,
      destination: pageTitle ? destinationFor(host, pageTitle, 0, lends) : lend(host, main, 0, lends)
    };
    const href = ({ id }) => id ? `#${id}` : null;
    keeps(start.link, "href", href(start.destination));
    const title = (pageTitle ? label(pageTitle) : "") || "Top";
    if (start.link.textContent !== title) start.link.textContent = title;
    const floor = Math.min(...headings.map(({ heading }) => level(heading)));
    const rows = /* @__PURE__ */ new Map();
    const items = headings.map(({ heading, label: label2 }, index) => {
      const destination = destinationFor(host, heading, index + 1, lends);
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
      if (drawn.link.textContent !== label2) drawn.link.textContent = label2;
      return { heading, label: label2, destination, depth, ...drawn };
    });
    drawing.rows = rows;
    place(
      drawing.list,
      items.map(({ row }) => row)
    );
    return items.length ? [start, ...items] : [];
  }

  // skills/leaf/packages/default/initial/lf-toc.js
  var reading = {
    label: (heading) => heading.textContent.replace(/\s+/g, " ").trim(),
    chrome: (heading) => heading.closest(".lf-chrome") !== null,
    // The rows are drawn once, into an empty list.
    place: (list, rows) => list.append(...rows),
    lends: false
  };
  document.documentElement.lfInitial.register("lf-toc", (host, { keeps }) => {
    const drawing = drawToc(host);
    const outline = () => keeps(
      host,
      "data-lf-toc-empty",
      drawOutline(host, drawing, { ...reading, keeps }).length ? null : ""
    );
    const doc = host.ownerDocument;
    if (doc.readyState === "loading")
      doc.addEventListener("readystatechange", outline, { once: true });
    else outline();
    return drawing;
  });
})();
