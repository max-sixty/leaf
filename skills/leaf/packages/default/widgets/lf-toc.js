/* lf-toc: navigation derived from the headings the page already says.
 *
 * The generated labels are link apparatus rather than a second copy of the page's
 * words, so the nav wears .lf-ui. When a heading titles an identified section, that
 * section is the destination: an eyebrow and heading arrive as one title, and the public
 * fragment names the section rather than its label. Otherwise the heading's id is the
 * destination, or an hgroup owns its heading's destination,
 * so an eyebrow and title share one address and measured box, for h1 as for every level.
 * A destination without an id is lent an `lf-` id, which no reader of the
 * page's ids takes for one its author wrote (`ADDRESSABLE`). The id goes on the destination
 * rather than on an element inserted beside it, because an inserted element changes
 * which child a page rule finds first or last and what an `h2 + p` rule finds next to
 * the heading.
 * max-level bounds the authored outline before the module creates links or lends ids.
 *
 * In the roomy margin the outline becomes a reading map. Each row receives the length
 * of the section it leads as its flex share, so the quiet spine describes the document
 * before its labels appear. Crowded destinations are fitted together just enough for
 * their labels to remain distinct; destination marker, label, and viewport lens all
 * use that one fitted scale. A marker's center is its coordinate; its label's first line
 * is centered there too, and the viewport lens reads those same coordinates. The first
 * label can extend above the track into the map's existing padding, rather than moving
 * the document's origin to make room for type. The map ends inside main's trailing
 * padding. Revealing the outline neither moves it nor withholds
 * its words.
 * A destination inside a closed disclosure or inactive tab joins the margin map when it
 * joins the displayed document; the ordinary outline keeps its native fragment link.
 * The darker lens is the part of the document in the viewport. The scroll moves it, as
 * a scroll-driven animation: its keyframes are the lens at each scroll position where
 * the map bends, and the browser interpolates between them as the scroller moves, so a
 * scroll writes nothing to the page. New keyframes are set only when the map or the
 * landing band changes. Where the browser has no scroll timeline (Firefox), the same
 * keyframes run as a paused animation whose time each scroll's paint sets, so the lens
 * follows a frame behind the scroll, still writing nothing to the page.
 * ResizeObserver hears late diagrams, images, disclosures, and width changes in the
 * document, and the height of the track the rows are laid into, which the page's chrome
 * can shorten without the document moving at all; a widget whose view rearranges
 * descendants without changing its own size emits the shared layout signal. The map
 * writes only to itself, never the main box it observes, and never the track either. The
 * ordinary in-flow list remains the narrow and paper form.
 * Fitting the map into a scrollable outline preserves its reading position, except
 * when a viewport change would put the focused link outside the outline's window.
 *
 * Every link is a real fragment link. The
 * browser owns its navigation, history, :target state, wheel input, and scroll
 * restoration; hidden-until-found reveals a disclosure or tab containing the target.
 * On an initial load the shared arrival pass runs after all widgets settle, so it can
 * honor a generated target that did not exist during HTML parsing. */
import {
  atLayoutPrecision,
  atScrollEnd,
  frameFor,
  holdFocus,
  html,
  inChrome,
  keeps,
  landingInsets,
  LAYOUT,
  layoutPx,
  once,
  PAGE_INTERFACE,
  PRESENTATION,
  render,
  repeat,
  scrollerFor,
  scrollLimit,
  sizeObserver,
  whileConnected,
  wrote,
} from "/runtime/widget-api.js";

const HEADING_SELECTOR = "h1, h2, h3, h4, h5, h6";
// The lens is never shorter than this, or than 1.2% of the map, so it stays in sight.
const LENS_FLOOR = 14;
const SCROLL_TIMELINE = "ScrollTimeline" in globalThis;
// Without a scroll timeline the lens's animation lasts this many milliseconds over the
// whole scroll, long enough that no browser's clamped timer precision steps it.
const LENS_DURATION = 1_000_000;

export default class extends HTMLElement {
  #main;
  #nav;
  #rows;
  #lens;
  #lensMotion = null;
  #lensInputs = "";
  #sections = [];
  #positions = [];
  #mapPositions = [];
  #mapHeight = 1;
  #shown = [];
  #contentStart = 0;
  #contentEnd = 1;
  #currentLink = null;
  #scroller;
  #stopWatching;
  #watching;
  #renamed;
  #navHeight = 0;
  #focusedLink = null;
  #focusedVisible = false;

  #onInterface = () => {
    this.#reconcile();
    this.#measure();
  };
  #onPresentation = () => this.#measure();
  #onNavScroll = () => {
    // A resize may clamp scrollTop before the measurement that restores focus.
    if (this.#nav.getBoundingClientRect().height === this.#navHeight)
      this.#rememberFocus();
  };

  connectedCallback() {
    const main = this.closest("main");
    if (!once(this) && main === this.#main && scrollerFor(this) === this.#scroller)
      return;
    // Moving to another reading region changes the resources, even if the
    // arrival batch keeps this element connected throughout the move.
    this.#stopWatching?.();
    this.#main = main;
    if (!main) return;
    this.#reconcile();
    this.#stopWatching = whileConnected(this, (signal) => this.#watch(signal));
  }

  // Authored revisions retain this widget when its own markup did not change.
  // Lit retains rows by the heading's authored id or node identity. A destination
  // may serve several headings, and grouping can change it without changing a row.
  #reconcile() {
    const maxLevel = Number(this.getAttribute("max-level") ?? 6);
    const headings = [...this.#main.querySelectorAll(HEADING_SELECTOR)]
      .filter((heading) => heading.localName !== "h1")
      .filter((heading) => !inChrome(heading) && !heading.closest("lf-toc"))
      .filter((heading) => Number(heading.localName.slice(1)) <= maxLevel)
      .map((heading) => ({ heading, label: wrote(heading).trim() }))
      .filter(({ label }) => label);

    const pageTitle = [...this.#main.querySelectorAll("h1")].find(
      (candidate) => !inChrome(candidate),
    );
    const startDestination = pageTitle
      ? this.#destinationFor(pageTitle, 0)
      : this.#main.id
        ? this.#main
        : this.#targetFor(this.#main, 0);
    const previous = this.#sections.map(({ destination }) => destination);
    const floor = Math.min(
      ...headings.map(({ heading }) => Number(heading.localName.slice(1))),
    );
    const items = headings.map(({ heading, label }, index) => ({
      heading,
      label,
      destination: this.#destinationFor(heading, index + 1),
      depth: Math.min(Number(heading.localName.slice(1)) - floor, 4),
    }));
    const title = (pageTitle ? wrote(pageTitle).trim() : "") || "Top";
    const focused = this.#sections.find(({ link }) => link === document.activeElement);
    const restore = focused && holdFocus(this.#nav);
    const outline = repeat(
      items,
      ({ heading }) => heading.id || heading,
      ({ label, destination, depth }) => html`
        <li data-lf-depth=${depth}>
          <a href=${`#${destination.id}`}>${label}</a>
        </li>
      `,
    );
    render(
      html`
        <nav class="lf-toc-nav lf-ui" data-lf-gen="1" aria-label="On this page">
          <p class="lf-toc-heading" data-lf-gen="1" data-lf-said>On this page</p>
          <div class="lf-toc-rows">
            <span class="lf-toc-window" aria-hidden="true"></span>
            <div class="lf-toc-start" data-lf-depth="0">
              <a href=${`#${startDestination.id}`}>${title}</a>
            </div>
            <ol>
              ${outline}
            </ol>
          </div>
        </nav>
      `,
      this,
    );
    this.#nav = this.querySelector(".lf-toc-nav");
    this.#rows = this.#nav.querySelector(".lf-toc-rows");
    this.#lens = this.#rows.querySelector(".lf-toc-window");
    const rows = [...this.#rows.querySelectorAll(".lf-toc-start, ol > li")];
    this.#sections = headings.length
      ? [{ destination: startDestination }, ...items].map((item, index) => ({
          ...item,
          row: rows[index],
          link: rows[index].querySelector("a"),
        }))
      : [];
    // A new key still represents the user's place when its heading or destination
    // survives. The template renderer already retains focus through keyed moves.
    if (restore) {
      const continuation =
        this.#sections.find(({ heading }) => heading === focused.heading) ??
        this.#sections.find(
          ({ destination }) => destination.id === focused.destination.id,
        );
      restore(continuation?.link);
    }
    this.toggleAttribute("data-lf-toc-empty", !headings.length);
    this.#observeDestinations(previous);
  }

  #observeDestinations(previous = []) {
    if (!this.#watching) return;
    for (const destination of previous)
      if (destination !== this.#main) this.#watching.unobserve(destination);
    this.#renamed.disconnect();
    // The complete destination reports section growth and title-group layout,
    // including an eyebrow changing size while its heading stays the same.
    for (const { destination } of this.#sections) {
      if (destination !== this.#main) this.#watching.observe(destination);
      this.#renamed.observe(destination, { attributeFilter: ["id"] });
    }
  }

  #watch(signal) {
    this.#main = this.closest("main");
    if (!this.#main) return;
    this.#scroller = scrollerFor(this);
    // Root scrolling is reported on Document; nested scrollports report on the
    // element itself. Keep one paint path while using the platform's event target for
    // each kind of scroller.
    const scrollSource =
      this.#scroller === document.scrollingElement ? document : this.#scroller;
    this.#watching = sizeObserver(() => this.#scheduleMeasure());
    this.#watching.observe(this.#main);
    this.#renamed = new MutationObserver(() => {
      this.#reconcile();
      this.#scheduleMeasure();
    });
    this.#observeDestinations();
    const passive = { passive: true, signal };
    scrollSource.addEventListener("scroll", this.#schedulePaint, passive);
    this.#nav.addEventListener("scroll", this.#onNavScroll, passive);
    this.#nav.addEventListener("focusin", () => this.#rememberFocus(), { signal });
    for (const type of ["toggle", "load"])
      this.#main.addEventListener(type, this.#scheduleMeasure, {
        capture: true,
        signal,
      });
    this.#main.addEventListener(LAYOUT, this.#scheduleMeasure, { signal });
    document.addEventListener(PRESENTATION, this.#onPresentation, { signal });
    document.addEventListener(PAGE_INTERFACE, this.#onInterface, { signal });
    window.addEventListener("resize", this.#scheduleMeasure, { signal });
    this.#scheduleMeasure();
    return () => {
      this.#watching.disconnect();
      this.#watching = null;
      this.#renamed.disconnect();
      this.#renamed = null;
      this.#lensMotion?.cancel();
      this.#lensMotion = null;
      this.#lensInputs = "";
    };
  }

  #scheduleMeasure = frameFor(this, () => this.#measure());

  #measure() {
    if (!this.#main || !this.#scroller || !this.#rows) return;
    if (!this.#sections.length) {
      this.#positions = [];
      this.#shown = [];
      this.#paint();
      return;
    }
    const mainTop = this.#documentTop(this.#main);
    let previous = this.#documentTop(this.#sections[0].destination);
    this.#shown = this.#sections.map(
      ({ destination }) => destination === this.#main || destination.checkVisibility(),
    );
    this.#positions = this.#sections.map(({ destination }, index) => {
      const position = this.#shown[index]
        ? Math.max(previous, this.#documentTop(destination))
        : previous;
      previous = position;
      return position;
    });
    this.#contentStart = this.#positions[0];
    this.#contentEnd = Math.max(
      mainTop +
        this.#main.clientTop +
        this.#main.scrollHeight -
        parseFloat(getComputedStyle(this.#main).paddingBottom),
      this.#positions.at(-1) + 1,
    );
    this.#sections.forEach(({ row }, index) => {
      row.toggleAttribute("data-lf-toc-hidden", !this.#shown[index]);
      const nextVisible = this.#shown.findIndex((shown, at) => at > index && shown);
      const next = nextVisible < 0 ? this.#contentEnd : this.#positions[nextVisible];
      row.style.setProperty(
        "--lf-toc-span",
        this.#shown[index] ? String(Math.max(1, next - this.#positions[index])) : "0",
      );
    });
    this.#fitRows();
    this.#rememberFocus();
    this.#lensInputs = "";
    this.#paint();
  }

  // A row's shift moves its label and dot (a transform and an inset), never the row, so
  // the rows are measured where they stand and each shift is written once, as fitted.
  #fitRows() {
    this.#mapPositions = [];
    const shifts = this.#fitLabels();
    this.#sections.forEach(({ row }, index) => {
      if (shifts.has(index))
        row.style.setProperty("--lf-toc-row-shift", `${shifts.get(index)}px`);
      else row.style.removeProperty("--lf-toc-row-shift");
    });
  }

  #rememberFocus() {
    const viewport = this.#nav.getBoundingClientRect();
    const active = document.activeElement;
    const focused = this.#nav.contains(active) ? active.getBoundingClientRect() : null;
    this.#navHeight = viewport.height;
    this.#focusedLink = active;
    this.#focusedVisible =
      !!focused &&
      focused.top >= viewport.top - 1 &&
      focused.bottom <= viewport.bottom + 1;
  }

  // Each fitted row's shift, by section index.
  #fitLabels() {
    const shifts = new Map();
    this.removeAttribute("data-lf-compact");
    this.removeAttribute("data-lf-outline");
    if (getComputedStyle(this.#rows).display !== "flex") return shifts;
    const track = this.#rows.getBoundingClientRect();
    this.#mapHeight = track.height;

    const readLabels = () => {
      const labels = this.#sections.flatMap(({ row, link }, index) =>
        this.#shown[index]
          ? [
              {
                index,
                ideal: row.getBoundingClientRect().top - track.top,
                height: link.getBoundingClientRect().height,
                center: parseFloat(getComputedStyle(link).lineHeight) / 2,
              },
            ]
          : [],
      );
      const lineHeight = parseFloat(getComputedStyle(this.#nav).lineHeight);
      const preferredGap = Number.isFinite(lineHeight) ? lineHeight * 0.5 : 0;
      const labelHeight = labels.reduce((sum, label) => sum + label.height, 0);
      const firstCenter = labels[0]?.center ?? 0;
      const availableHeight = track.height + firstCenter;
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
    if (!layout.labels.length) return shifts;
    if (
      layout.labelHeight + layout.preferredGap * Math.max(0, layout.labels.length - 1) >
      layout.availableHeight + 1
    ) {
      this.setAttribute("data-lf-compact", "");
      layout = readLabels();
    }
    if (layout.labelHeight > layout.availableHeight + 1) {
      this.removeAttribute("data-lf-compact");
      this.setAttribute("data-lf-outline", "");
      if (
        this.#nav.contains(document.activeElement) &&
        this.#focusedLink === document.activeElement &&
        this.#focusedVisible &&
        this.#nav.getBoundingClientRect().height < this.#navHeight - 1
      ) {
        const focused = document.activeElement.getBoundingClientRect();
        const viewport = this.#nav.getBoundingClientRect();
        if (focused.bottom > viewport.bottom)
          this.#nav.scrollTop += focused.bottom - viewport.bottom;
        else if (focused.top < viewport.top)
          this.#nav.scrollTop += focused.top - viewport.top;
      }
      return shifts;
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
    const ceiling = track.height - occupiedHeight;
    for (const block of blocks) {
      const top = Math.max(floor, Math.min(ceiling, block.top));
      for (let at = block.start; at <= block.end; at += 1) {
        const label = layout.labels[at];
        const fitted = top + label.prefix + label.center;
        this.#mapPositions[label.index] = fitted;
        shifts.set(label.index, fitted - label.ideal);
      }
    }
    return shifts;
  }

  #mapPosition(position) {
    const anchors = [];
    this.#positions.forEach((documentPosition, index) => {
      if (!this.#shown[index] || !Number.isFinite(this.#mapPositions[index])) return;
      const anchor = { documentPosition, mapPosition: this.#mapPositions[index] };
      // Several outline entries can name the same rendered position. Current-section
      // selection walks forward through that run, so the lens must use its last entry
      // too; retaining the first put the lens beside a different title.
      if (anchors.at(-1)?.documentPosition === documentPosition) anchors.pop();
      anchors.push(anchor);
    });
    if (!anchors.length) {
      const total = Math.max(1, this.#contentEnd - this.#contentStart);
      return (
        Math.max(0, Math.min(1, (position - this.#contentStart) / total)) *
        this.#mapHeight
      );
    }
    if (position <= anchors[0].documentPosition) return anchors[0].mapPosition;
    for (let index = 1; index < anchors.length; index += 1) {
      const previous = anchors[index - 1];
      const next = anchors[index];
      if (position > next.documentPosition) continue;
      const distance = Math.max(1, next.documentPosition - previous.documentPosition);
      const progress = (position - previous.documentPosition) / distance;
      return (
        previous.mapPosition + progress * (next.mapPosition - previous.mapPosition)
      );
    }
    const last = anchors.at(-1);
    const distance = Math.max(1, this.#contentEnd - last.documentPosition);
    const progress = Math.max(
      0,
      Math.min(1, (position - last.documentPosition) / distance),
    );
    return last.mapPosition + progress * (this.#mapHeight - last.mapPosition);
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

  #schedulePaint = frameFor(this, () => this.#paint());

  #paint() {
    if (!this.#rows || !this.#scroller) return;
    let current = this.#shown.findIndex(Boolean);
    if (current < 0) {
      this.#currentLink?.removeAttribute("aria-current");
      this.#currentLink = null;
      this.#lensMotion?.cancel();
      this.#lensMotion = null;
      this.#lensInputs = "";
      keeps(this.#lens, "style", "display: none;");
      return;
    }
    // What the user can read is the scroller's landing band, clear of the banner over
    // its top and the bottom bar over its bottom.
    const clear = landingInsets(this.#scroller);
    const visibleStart = this.#scroller.scrollTop + clear.top;
    const visibleEnd =
      this.#scroller.scrollTop + this.#scroller.clientHeight - clear.bottom;
    this.#standLens(clear);
    if (!SCROLL_TIMELINE && this.#lensMotion)
      this.#lensMotion.currentTime =
        (LENS_DURATION * this.#scroller.scrollTop) / scrollLimit(this.#scroller);

    const threshold = visibleStart + Math.min(32, (visibleEnd - visibleStart) * 0.08);
    this.#positions.forEach((position, index) => {
      if (this.#shown[index] && position <= threshold) current = index;
    });
    if (atScrollEnd(this.#scroller)) current = this.#shown.findLastIndex(Boolean);
    const link = this.#sections[current].link;
    if (link === this.#currentLink) return;
    this.#currentLink?.removeAttribute("aria-current");
    link.setAttribute("aria-current", "location");
    this.#currentLink = link;
  }

  // Keyframes are set again only when a measure has moved the map, or the scroller's
  // length or landing band has changed; a scroll alone reaches the early return.
  #standLens(clear) {
    const scroller = this.#scroller;
    const reach = scrollLimit(scroller);
    const band = scroller.clientHeight - clear.top - clear.bottom;
    const inputs = `${reach} ${band} ${clear.top}`;
    if (inputs === this.#lensInputs) return;
    this.#lensInputs = inputs;
    const floor = Math.max(LENS_FLOOR, this.#mapHeight * 0.012);
    const span = (scrolled) => {
      const start = this.#mapPosition(scrolled + clear.top);
      return {
        start,
        size: Math.max(start, this.#mapPosition(scrolled + clear.top + band)) - start,
      };
    };
    const transform = ({ start, size }) =>
      `translateY(${layoutPx(start)}) scaleY(${atLayoutPrecision(Math.max(floor, size))})`;
    if (reach <= 0) {
      this.#lensMotion?.cancel();
      this.#lensMotion = null;
      keeps(this.#lens, "style", `transform: ${transform(span(0))};`);
      return;
    }
    // The map is linear between the scroll positions where the band's top or foot
    // meets a destination or the document's ends, and where the lens meets its floor.
    const bends = [this.#contentStart, this.#contentEnd, ...this.#positions]
      .flatMap((position) => [position - clear.top, position - clear.top - band])
      .filter((scrolled) => scrolled > 0 && scrolled < reach);
    const stops = [...new Set([0, reach, ...bends])].sort((a, b) => a - b);
    const floored = stops.flatMap((scrolled, index) => {
      const next = stops[index + 1];
      if (next === undefined) return [scrolled];
      const [from, to] = [span(scrolled).size, span(next).size];
      if ((from - floor) * (to - floor) >= 0) return [scrolled];
      return [scrolled, scrolled + ((floor - from) / (to - from)) * (next - scrolled)];
    });
    const frames = floored.map((scrolled) => ({
      offset: scrolled / reach,
      transform: transform(span(scrolled)),
    }));
    this.#lens.removeAttribute("style");
    if (this.#lensMotion) this.#lensMotion.effect.setKeyframes(frames);
    else if (SCROLL_TIMELINE)
      this.#lensMotion = this.#lens.animate(frames, {
        timeline: new globalThis.ScrollTimeline({ source: scroller, axis: "block" }),
        fill: "both",
      });
    else {
      // #paint sets the time as the scroller scrolls.
      this.#lensMotion = this.#lens.animate(frames, {
        duration: LENS_DURATION,
        fill: "both",
      });
      this.#lensMotion.pause();
    }
  }

  #destinationFor(heading, position) {
    const section = heading.closest("section[id]");
    if (section?.querySelector(HEADING_SELECTOR) === heading) return section;
    const destination = heading.closest("hgroup") ?? heading;
    return destination.id ? destination : this.#targetFor(destination, position);
  }

  #targetFor(heading, position) {
    const stem = `lf-${this.id}-section-${position}`;
    let id = stem;
    let suffix = 2;
    while (document.getElementById(id)) id = `${stem}-${suffix++}`;
    heading.id = id;
    return heading;
  }
}
