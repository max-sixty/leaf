(() => {
  // leaf-initial-solid:solid
  var { createSignal, createMemo, createRoot, createReaction, getObserver, runWithOwner, createEffect, createTrackedEffect, createProjection, flush, untrack, For, Show, onCleanup, render, insert, spread, html } = document.documentElement.lfInitial.solid;

  // skills/leaf/packages/default/widgets/toc-view.js
  var HEADING_SELECTOR = "h1, h2, h3, h4, h5, h6";
  var outlineDocument = (host) => host.closest("[data-lf-views] > *, main");
  function drawToc(host) {
    const open = host.hasAttribute("open");
    const [state, setState] = createSignal(
      { start: { label: "Top" }, items: [] },
      { ownedWrite: true }
    );
    const href = (destination) => destination?.id ? `#${destination.id}` : null;
    host.replaceChildren();
    runWithOwner(
      null,
      () => render(
        () => html` <nav class="lf-toc-nav lf-ui" data-lf-gen="1" aria-label="On this page">
          <p class="lf-toc-heading lf-label" data-lf-gen="1" data-lf-said>
            On this page
          </p>
          <details class="lf-toc-disclosure" open=${open}>
            <summary class="lf-toc-toggle lf-label" data-lf-gen="1" data-lf-said>
              On this page
            </summary>
            <div class="lf-toc-rows">
              <span class="lf-toc-window" aria-hidden="true"></span>
              <div class="lf-toc-start" data-lf-depth="0">
                <a href=${() => href(state().start.destination)}
                  >${() => state().start.label}</a
                >
              </div>
              <ol>
                ${For({
          get each() {
            return state().items;
          },
          keyed: (item) => item.key,
          children: (item) => html`<li data-lf-depth=${() => item().depth}>
                      <a href=${() => href(item().destination)}
                        >${() => item().label}</a
                      >
                    </li>`
        })}
              </ol>
            </div>
          </details>
        </nav>`,
        host
      )
    );
    const nav = host.querySelector("nav");
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
        flush(() => setState({ start, items }));
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

  // skills/leaf/packages/default/initial/lf-toc.js
  var reading = {
    label: (heading) => heading.textContent.replace(/\s+/g, " ").trim(),
    chrome: (heading) => heading.closest(".lf-chrome") !== null,
    lends: false
  };
  document.documentElement.lfInitial.register("lf-toc", (host, { keeps }) => {
    const drawing = drawToc(host);
    const outline = () => keeps(host, "data-lf-toc-empty", drawing.update(reading).length ? null : "");
    const doc = host.ownerDocument;
    if (doc.readyState === "loading") {
      const pending = host.hasAttribute("open") && outlineDocument(host);
      if (pending) keeps(pending, "data-lf-initial-pending", "");
      doc.addEventListener(
        "readystatechange",
        () => {
          outline();
          if (pending) keeps(pending, "data-lf-initial-pending", null);
        },
        { once: true }
      );
    } else outline();
    return drawing;
  });
})();
