(() => {
  // leaf-initial-lit:lit
  var { AsyncDirective, AsyncReplaceDirective, CSSResult, Directive, LitElement, PartType, ReactiveElement, TemplateResultType, UnsafeHTMLDirective, UntilDirective, _$LE, _$LH, adoptStyles, asyncAppend, asyncReplace, cache, choose, classMap, clearPart, createRef, css, customElement, defaultConverter, directive, eventOptions, getCommittedValue, getCompatibleStyle, getDirectiveClass, guard, html, ifDefined, insertPart, isCompiledTemplateResult, isDirectiveResult, isPrimitive, isServer, isSingleExpression, isTemplateResult, join, keyed, literal, live, map, mathml, noChange, notEqual, nothing, property, query, queryAll, queryAssignedElements, queryAssignedNodes, queryAsync, range, ref, removePart, render, repeat, setChildPartValue, setCommittedValue, standardProperty, state, staticHtml, staticMathml, staticSvg, styleMap, supportsAdoptingStyleSheets, svg, templateContent, unsafeCSS, unsafeHTML, unsafeMathML, unsafeSVG, unsafeStatic, until, when, withStatic } = document.documentElement.lfInitial.lit;

  // packages/default/widgets/toc-view.js
  var HEADING_SELECTOR = "h1, h2, h3, h4, h5, h6";
  var outlineDocument = (host) => host.closest("[data-lf-views] > *, main");
  function drawToc(host, { generatedElement, keeps }) {
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
    const disclosure = nav.querySelector("details");
    const summary = disclosure.querySelector("summary");
    let sections = [];
    let flowOpen;
    return {
      scope: () => outlineDocument(host),
      nav,
      track,
      lens: track.querySelector(".lf-toc-window"),
      update(reading2) {
        const { start, items } = readOutline(host, reading2);
        paint(start, items);
        const rows = [...list.children];
        sections = items.length ? [
          { ...start, row: startRow, link: startRow.firstElementChild },
          ...items.map((item, index) => ({
            ...item,
            row: rows[index],
            link: rows[index].firstElementChild
          }))
        ] : [];
        return sections;
      },
      // Measure the document the last update outlined and lay the map out from it.
      // Returns which destinations are displayed, where each starts and where the
      // document ends, in viewport coordinates at this moment, with each marker's fitted
      // place on the track. `keepsOpen` says whether a return to flow must leave the
      // outline open for a focused link.
      measure(keepsOpen = () => false) {
        if (getComputedStyle(summary).display === "none") {
          flowOpen ??= disclosure.open;
          if (!disclosure.open) disclosure.open = true;
        } else if (flowOpen !== void 0) {
          const open2 = flowOpen || keepsOpen();
          if (disclosure.open !== open2) disclosure.open = open2;
          flowOpen = void 0;
        }
        const main = outlineDocument(host);
        if (!main || !sections.length)
          return { shown: [], positions: [], end: 0, map: [], height: 1, outline: false };
        const top = (element) => {
          for (let candidate = element; candidate; candidate = candidate.parentElement) {
            const box = candidate.getBoundingClientRect();
            if (box.width || box.height) return box.top;
            if (candidate === main) break;
          }
          return main.getBoundingClientRect().top;
        };
        const shown = sections.map(
          ({ destination }) => destination === main || destination.checkVisibility()
        );
        let previous = top(sections[0].destination);
        const positions = sections.map(({ destination }, index) => {
          const position = shown[index] ? Math.max(previous, top(destination)) : previous;
          previous = position;
          return position;
        });
        const end = Math.max(
          top(main) + main.clientTop + main.scrollHeight - parseFloat(getComputedStyle(main).paddingBottom),
          positions.at(-1) + 1
        );
        sections.forEach(({ row }, index) => {
          row.toggleAttribute("data-lf-toc-hidden", !shown[index]);
          const nextVisible = shown.findIndex((visible, at) => at > index && visible);
          const next = nextVisible < 0 ? end : positions[nextVisible];
          row.style.setProperty(
            "--lf-toc-span",
            shown[index] ? String(Math.max(1, next - positions[index])) : "0"
          );
        });
        return {
          shown,
          positions,
          end,
          ...fitRows(host, nav, track, sections, shown, keeps)
        };
      }
    };
  }
  function fitRows(host, nav, track, sections, shown, keeps) {
    const map2 = [];
    const shifts = /* @__PURE__ */ new Map();
    const { height, outline } = fitLabels(host, nav, track, sections, shown, keeps, {
      map: map2,
      shifts
    });
    sections.forEach(({ row }, index) => {
      if (shifts.has(index))
        row.style.setProperty("--lf-toc-row-shift", `${shifts.get(index)}px`);
      else row.style.removeProperty("--lf-toc-row-shift");
    });
    return { map: map2, height, outline };
  }
  function fitLabels(host, nav, track, sections, shown, keeps, { map: map2, shifts }) {
    keeps(host, "data-lf-compact", null);
    keeps(host, "data-lf-outline", null);
    if (getComputedStyle(track).display !== "flex") return { height: 1, outline: false };
    const box = track.getBoundingClientRect();
    const readLabels = () => {
      const labels = sections.flatMap(
        ({ row, link }, index) => shown[index] ? [
          {
            index,
            ideal: row.getBoundingClientRect().top - box.top,
            height: link.getBoundingClientRect().height,
            center: parseFloat(getComputedStyle(link).lineHeight) / 2
          }
        ] : []
      );
      const lineHeight = parseFloat(getComputedStyle(nav).lineHeight);
      const preferredGap = Number.isFinite(lineHeight) ? lineHeight * 0.5 : 0;
      const labelHeight = labels.reduce((sum, label) => sum + label.height, 0);
      const firstCenter = labels[0]?.center ?? 0;
      const availableHeight = box.height + firstCenter;
      const availableGap = labels.length > 1 ? (availableHeight - labelHeight) / (labels.length - 1) : 0;
      return {
        labels,
        labelHeight,
        firstCenter,
        availableHeight,
        preferredGap,
        gap: Math.max(0, Math.min(preferredGap, availableGap))
      };
    };
    let layout = readLabels();
    if (!layout.labels.length) return { height: box.height, outline: false };
    if (layout.labelHeight + layout.preferredGap * Math.max(0, layout.labels.length - 1) > layout.availableHeight + 1) {
      keeps(host, "data-lf-compact", "");
      layout = readLabels();
    }
    if (layout.labelHeight > layout.availableHeight + 1) {
      keeps(host, "data-lf-compact", null);
      keeps(host, "data-lf-outline", "");
      return { height: box.height, outline: true };
    }
    let prefix = 0;
    for (const label of layout.labels) {
      label.prefix = prefix;
      prefix += label.height + layout.gap;
    }
    const occupiedHeight = Math.max(0, prefix - layout.gap);
    const blocks = [];
    layout.labels.forEach((label, at) => {
      blocks.push({
        start: at,
        end: at,
        top: label.ideal - label.center - label.prefix,
        count: 1
      });
      while (blocks.length > 1 && blocks.at(-2).top > blocks.at(-1).top) {
        const next = blocks.pop();
        const previous = blocks.pop();
        const count = previous.count + next.count;
        blocks.push({
          start: previous.start,
          end: next.end,
          top: (previous.top * previous.count + next.top * next.count) / count,
          count
        });
      }
    });
    const floor = -layout.firstCenter;
    const ceiling = box.height - occupiedHeight;
    for (const block of blocks) {
      const top = Math.max(floor, Math.min(ceiling, block.top));
      for (let at = block.start; at <= block.end; at += 1) {
        const label = layout.labels[at];
        const fitted = top + label.prefix + label.center;
        map2[label.index] = fitted;
        shifts.set(label.index, fitted - label.ideal);
      }
    }
    return { height: box.height, outline: false };
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
    const drawing = drawToc(host, tools);
    const outline = () => {
      tools.keeps(host, "data-lf-toc-empty", drawing.update(reading).length ? null : "");
      drawing.measure();
    };
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
