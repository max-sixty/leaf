(() => {
  // leaf-initial-lit:lit
  var { AsyncDirective, AsyncReplaceDirective, CSSResult, Directive, LitElement, PartType, ReactiveElement, TemplateResultType, UnsafeHTMLDirective, UntilDirective, _$LE, _$LH, adoptStyles, asyncAppend, asyncReplace, cache, choose, classMap, clearPart, createRef, css, customElement, defaultConverter, directive, eventOptions, getCommittedValue, getCompatibleStyle, getDirectiveClass, guard, html, ifDefined, insertPart, isCompiledTemplateResult, isDirectiveResult, isPrimitive, isServer, isSingleExpression, isTemplateResult, join, keyed, literal, live, map, mathml, noChange, notEqual, nothing, property, query, queryAll, queryAssignedElements, queryAssignedNodes, queryAsync, range, ref, removePart, render, repeat, setChildPartValue, setCommittedValue, standardProperty, state, staticHtml, staticMathml, staticSvg, styleMap, supportsAdoptingStyleSheets, svg, templateContent, unsafeCSS, unsafeHTML, unsafeMathML, unsafeSVG, unsafeStatic, until, when, withStatic } = document.documentElement.lfInitial.lit;

  // packages/default/widgets/toc-view.js
  var HEADING_SELECTOR = "h1, h2, h3, h4, h5, h6";
  var outlineDocument = (host) => host.closest("[data-lf-views] > *, main");
  function drawToc(host, generatedElement) {
    const open = host.hasAttribute("open");
    const href = (destination) => destination?.id ? `#${destination.id}` : nothing;
    const paint = (start, items) => render(
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
                  `
      )}
              </ol>
            </div>
          </details>
        </nav>
      `,
      host
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
      update(reading2) {
        const { start, items } = readOutline(host, reading2);
        paint(start, items);
        const rows = [...list.children];
        return items.length ? [
          { ...start, row: startRow, link: startRow.firstElementChild },
          ...items.map((item, index) => ({
            ...item,
            row: rows[index],
            link: rows[index].firstElementChild
          }))
        ] : [];
      }
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
  function readOutline(host, { label, chrome, lends }) {
    const main = outlineDocument(host);
    if (!main) return { start: { label: "Top" }, items: [] };
    const maxLevel = Number(host.getAttribute("max-level") ?? 6);
    const headings = [...main.querySelectorAll(HEADING_SELECTOR)].filter(
      (heading) => heading.localName !== "h1" && !chrome(heading) && !heading.closest("lf-toc") && level(heading) <= maxLevel
    ).map((heading) => ({ heading, label: label(heading) })).filter((item) => item.label);
    const pageTitle = [...main.querySelectorAll("h1")].find(
      (candidate) => !chrome(candidate)
    );
    const start = {
      label: (pageTitle ? label(pageTitle) : "") || "Top",
      destination: pageTitle ? destinationFor(host, pageTitle, 0, lends) : lend(host, main, 0, lends)
    };
    const floor = Math.min(...headings.map(({ heading }) => level(heading)));
    const items = headings.map(({ heading, label: label2 }, index) => {
      const destination = destinationFor(host, heading, index + 1, lends);
      const key = heading.id && !heading.id.startsWith("lf-") ? heading.id : heading;
      const depth = Math.min(level(heading) - floor, 4);
      return { key, heading, label: label2, destination, depth };
    });
    return { start, items };
  }

  // packages/default/initial/lf-toc.js
  var reading = {
    label: (heading) => heading.textContent.replace(/\s+/g, " ").trim(),
    chrome: (heading) => heading.closest(".lf-chrome") !== null,
    lends: false
  };
  document.documentElement.lfInitial.register("lf-toc", (host, tools) => {
    const drawing = drawToc(host, tools.generatedElement);
    const outline = () => tools.keeps(host, "data-lf-toc-empty", drawing.update(reading).length ? null : "");
    const doc = host.ownerDocument;
    if (doc.readyState === "loading") {
      const pending = host.hasAttribute("open") && outlineDocument(host);
      if (pending) tools.keeps(pending, "data-lf-initial-pending", "");
      doc.addEventListener(
        "readystatechange",
        () => {
          outline();
          if (pending) tools.keeps(pending, "data-lf-initial-pending", null);
        },
        { once: true }
      );
    } else outline();
    return drawing;
  });
})();
