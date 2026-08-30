/* lf-toc: navigation derived from the headings the page already says.
 *
 * The generated labels are link apparatus rather than a second copy of the page's
 * words, so the nav wears .lf-ui. An authored heading keeps its own attributes. When one
 * has no id, a generated sibling supplies a native fragment target instead; that target
 * remains useful after export removes this module.
 *
 * In the roomy margin the outline becomes a reading map. Each row receives the length
 * of the section it leads as its flex share, so the quiet spine describes the document
 * before its labels appear. The darker lens is the part of the document in the viewport.
 * ResizeObserver hears late diagrams, images, disclosures, and width changes; a widget
 * whose view rearranges descendants without changing its own size emits the shared layout
 * signal. The map writes only to itself, never the main box it observes. The ordinary
 * in-flow list remains the script-free, narrow, and paper form.
 *
 * Every link keeps a real href for standalone copies. In a live page the shared fragment
 * travel preserves history and :target, reveals a disclosure or tab, and gives the move
 * the same short glide as Leaf's reading keys. On an initial load the shared arrival pass
 * runs after all widgets settle, so it can honor a generated target that did not exist
 * during HTML parsing. */
import {
  LAYOUT,
  followFragment,
  inChrome,
  moveScrollerFromWheel,
  once,
  relabel,
  scrollerFor,
  wrote,
} from "/runtime/widget-api.js";

const HEADING_SELECTOR = "h2, h3, h4, h5, h6";

customElements.define(
  "lf-toc",
  class extends HTMLElement {
    #main;
    #nav;
    #rows;
    #sections = [];
    #positions = [];
    #shown = [];
    #destinations = new Map();
    #contentStart = 0;
    #contentEnd = 1;
    #currentLink = null;
    #scroller;
    #watching;
    #measureFrame = 0;
    #paintFrame = 0;

    #onScroll = () => this.#schedulePaint();
    #onResize = () => this.#scheduleMeasure();
    #onToggle = () => this.#scheduleMeasure();
    #onLoad = () => this.#scheduleMeasure();
    #onLayout = () => this.#scheduleMeasure();
    #onWheel = (event) => {
      if (getComputedStyle(this).position !== "fixed") return;
      if (moveScrollerFromWheel(this.#scroller, event)) event.preventDefault();
    };
    #onClick = (event) => {
      const link = event.target.closest("a");
      const destination = this.#destinations.get(link);
      if (
        !destination ||
        event.defaultPrevented ||
        event.button !== 0 ||
        event.altKey ||
        event.ctrlKey ||
        event.metaKey ||
        event.shiftKey
      )
        return;
      event.preventDefault();
      followFragment(destination, link.hash, "start");
    };

    connectedCallback() {
      if (once(this)) this.#build();
      if (!this.#nav || !this.#sections.length) return;
      this.#watch();
    }

    disconnectedCallback() {
      this.#watching?.disconnect();
      this.#watching = null;
      this.#scroller?.removeEventListener("scroll", this.#onScroll);
      this.#nav?.removeEventListener("wheel", this.#onWheel);
      this.#main?.removeEventListener("toggle", this.#onToggle, true);
      this.#main?.removeEventListener("load", this.#onLoad, true);
      this.#main?.removeEventListener(LAYOUT, this.#onLayout);
      window.removeEventListener("resize", this.#onResize);
      cancelAnimationFrame(this.#measureFrame);
      cancelAnimationFrame(this.#paintFrame);
      this.#measureFrame = 0;
      this.#paintFrame = 0;
    }

    #build() {
      this.#main = this.closest("main");
      if (!this.#main) return;

      const headings = [...this.#main.querySelectorAll(HEADING_SELECTOR)]
        .filter((heading) => !inChrome(heading) && !heading.closest("lf-toc"))
        .map((heading) => ({ heading, label: wrote(heading).trim() }))
        .filter(({ label }) => label);
      if (!headings.length) return;

      this.#nav = document.createElement("nav");
      this.#nav.className = "lf-toc-nav lf-ui";
      this.#nav.dataset.lfGen = "1";
      this.#nav.setAttribute("aria-label", "On this page");

      const heading = document.createElement("p");
      heading.className = "lf-toc-heading";
      relabel(heading, "On this page", { says: true });

      this.#rows = document.createElement("div");
      this.#rows.className = "lf-toc-rows";
      const lens = document.createElement("span");
      lens.className = "lf-toc-window";
      lens.setAttribute("aria-hidden", "true");

      const pageTitle = [...this.#main.querySelectorAll("h1")].find(
        (candidate) => !inChrome(candidate),
      );
      const start = document.createElement("div");
      start.className = "lf-toc-start";
      start.dataset.lfDepth = "0";
      const startLink = document.createElement("a");
      const startTarget = pageTitle
        ? pageTitle.id || this.#targetFor(pageTitle, 0)
        : this.#main.id || this.#targetFor(this.#main, 0);
      startLink.href = `#${startTarget}`;
      this.#destinations.set(startLink, document.getElementById(startTarget));
      const startLabel = pageTitle ? wrote(pageTitle).trim() : "Top";
      startLink.dataset.lfLabel = startLabel;
      startLink.setAttribute("aria-label", startLabel);
      start.append(startLink);

      const list = document.createElement("ol");
      const floor = Math.min(
        ...headings.map(({ heading: item }) => Number(item.localName.slice(1))),
      );
      const items = headings.map(({ heading: item, label }, index) => {
        const target = item.id || this.#targetFor(item, index + 1);
        const row = document.createElement("li");
        row.dataset.lfDepth = String(
          Math.min(Number(item.localName.slice(1)) - floor, 4),
        );
        const link = document.createElement("a");
        link.href = `#${target}`;
        this.#destinations.set(link, document.getElementById(target));
        link.textContent = label;
        row.append(link);
        list.append(row);
        return { heading: item, row, link };
      });

      this.#sections = [
        { heading: pageTitle ?? this.#main, row: start, link: startLink },
        ...items,
      ];
      this.#rows.append(lens, start, list);
      this.#nav.append(heading, this.#rows);
      this.#nav.addEventListener("click", this.#onClick);
      this.append(this.#nav);
    }

    #watch() {
      if (this.#watching) return;
      this.#main = this.closest("main");
      if (!this.#main) return;
      this.#scroller = scrollerFor(this);
      this.#watching = new ResizeObserver(() => this.#scheduleMeasure());
      this.#watching.observe(this.#main);
      for (const { heading } of this.#sections)
        if (heading !== this.#main) this.#watching.observe(heading);
      this.#scroller.addEventListener("scroll", this.#onScroll, { passive: true });
      this.#nav.addEventListener("wheel", this.#onWheel, { passive: false });
      this.#main.addEventListener("toggle", this.#onToggle, true);
      this.#main.addEventListener("load", this.#onLoad, true);
      this.#main.addEventListener(LAYOUT, this.#onLayout);
      window.addEventListener("resize", this.#onResize);
      this.#scheduleMeasure();
    }

    #scheduleMeasure() {
      if (this.#measureFrame || !this.isConnected) return;
      this.#measureFrame = requestAnimationFrame(() => {
        this.#measureFrame = 0;
        this.#measure();
      });
    }

    #measure() {
      if (!this.#main || !this.#scroller || !this.#rows) return;
      const mainTop = this.#documentTop(this.#main);
      let previous = this.#documentTop(this.#sections[0].heading);
      this.#shown = this.#sections.map(
        ({ heading }) => heading === this.#main || heading.checkVisibility(),
      );
      this.#positions = this.#sections.map(({ heading }, index) => {
        const position = this.#shown[index]
          ? Math.max(previous, this.#documentTop(heading))
          : previous;
        previous = position;
        return position;
      });
      this.#contentStart = this.#positions[0];
      this.#contentEnd = Math.max(
        mainTop + this.#main.scrollHeight,
        this.#positions.at(-1) + 1,
      );
      this.#sections.forEach(({ row }, index) => {
        const nextVisible = this.#shown.findIndex((shown, at) => at > index && shown);
        const next = nextVisible < 0 ? this.#contentEnd : this.#positions[nextVisible];
        row.style.setProperty(
          "--lf-toc-span",
          this.#shown[index] ? String(Math.max(1, next - this.#positions[index])) : "0",
        );
      });
      this.removeAttribute("data-lf-dense");
      this.toggleAttribute(
        "data-lf-dense",
        this.#nav.scrollHeight > this.#nav.clientHeight + 1,
      );
      this.#paint();
    }

    #documentTop(element) {
      for (let candidate = element; candidate; candidate = candidate.parentElement) {
        const box = candidate.getBoundingClientRect();
        if (box.width || box.height) return box.top + this.#scroller.scrollTop;
        if (candidate === this.#main) break;
      }
      const mainBox = this.#main.getBoundingClientRect();
      return mainBox.top + this.#scroller.scrollTop;
    }

    #schedulePaint() {
      if (this.#paintFrame || !this.isConnected) return;
      this.#paintFrame = requestAnimationFrame(() => {
        this.#paintFrame = 0;
        this.#paint();
      });
    }

    #paint() {
      if (!this.#rows || !this.#scroller || !this.#positions.length) return;
      const total = Math.max(1, this.#contentEnd - this.#contentStart);
      const clear = parseFloat(getComputedStyle(this.#scroller).scrollPaddingTop) || 0;
      const visibleStart = this.#scroller.scrollTop + clear;
      const visibleEnd = this.#scroller.scrollTop + this.#scroller.clientHeight;
      const start = Math.max(
        0,
        Math.min(1, (visibleStart - this.#contentStart) / total),
      );
      const end = Math.max(
        start,
        Math.min(1, (visibleEnd - this.#contentStart) / total),
      );
      this.#rows.style.setProperty("--lf-toc-window-start", `${start * 100}%`);
      this.#rows.style.setProperty(
        "--lf-toc-window-size",
        `${Math.max(0.012, end - start) * 100}%`,
      );

      const threshold = visibleStart + Math.min(32, (visibleEnd - visibleStart) * 0.08);
      let current = 0;
      this.#positions.forEach((position, index) => {
        if (this.#shown[index] && position <= threshold) current = index;
      });
      if (
        this.#scroller.scrollTop >=
        this.#scroller.scrollHeight - this.#scroller.clientHeight - 1
      )
        current = this.#shown.findLastIndex(Boolean);
      const link = this.#sections[current].link;
      if (link === this.#currentLink) return;
      this.#currentLink?.removeAttribute("aria-current");
      link.setAttribute("aria-current", "location");
      this.#currentLink = link;
    }

    #targetFor(heading, position) {
      const stem = `lf-${this.id}-section-${position}`;
      let id = stem;
      let suffix = 2;
      while (document.getElementById(id)) id = `${stem}-${suffix++}`;

      const target = document.createElement("span");
      target.id = id;
      target.className = "lf-toc-target lf-ui";
      target.dataset.lfGen = "1";
      target.setAttribute("aria-hidden", "true");
      heading.before(target);
      return id;
    }
  },
);
