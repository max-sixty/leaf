import { drawToc } from "./toc-view.js";
import { sectionMarks } from "./toc-marks.js";
/* lf-toc: navigation derived from the headings the page already says.
 *
 * The outline, the destination of each of its links and the frame that holds them are
 * `toc-view.js`'s. The module redraws the outline in those same nodes
 * whenever the document's headings change, and measures and moves the map.
 *
 * In a track beside the body too narrow for words, a document's sidebar narrowed to
 * the map's spine, the outline becomes a reading map. Each section's marker stands at
 * its section's place on the document's scale, so the quiet spine describes the
 * document before its labels appear over the page. Crowded destinations are fitted
 * together just enough for their labels to remain distinct; destination marker, label,
 * and viewport lens all use that one fitted scale, and a route too long for its labels
 * leaves its deepest levels off the map (`#fitLabels`). A marker's center is its
 * coordinate; its label's first line is centered there too, and the viewport lens reads
 * those same coordinates. The first
 * label can extend above the track into the map's existing padding, rather than moving
 * the document's origin to make room for type. The map fills its stuck track
 * (toc.css). The labels keep their measure while faded out, so revealing them neither
 * moves the map nor refits it.
 * A destination inside a closed disclosure or inactive tab joins the margin map when it
 * joins the displayed document; the ordinary outline keeps its native fragment link.
 * The darker lens is the part of the document in the viewport. The scroll moves it, as
 * a scroll-driven animation: its keyframes are the lens at each scroll position where
 * the map bends, and the browser interpolates between them as the scroller moves, so a
 * scroll writes nothing to the page. New keyframes are set only when the map or the
 * landing band changes.
 * The lens and the current entry follow the scroller of the document the outline
 * covers, not the scroller of the box the widget stands in. A sidebar's sticking track
 * scrolls only its own contents and usually stands at its scroll end, so an outline
 * that read it marked the last section as current at every scroll.
 * ResizeObserver hears late diagrams, images, disclosures, and width changes in the
 * document, and the height of the track the rows are laid into, which the page's chrome
 * can shorten without the document moving at all; a widget whose view rearranges
 * descendants without changing its own size emits the shared layout signal. The map
 * writes only to itself, never the main box it observes, and never the track either. The
 * in-flow outline is a native disclosure; paper and the margin expose the same links.
 * The native node owns the in-flow open choice. While margin or paper hides its
 * summary, the disclosure opens semantically and temporarily remembers that choice.
 * Returning to flow restores it, unless a focused link needs to remain reachable.
 * Keyed revisions keep the same disclosure and links.
 *
 * Each row also marks where the page's open threads, its On Me items and, while the
 * changes view is on, its changes stand (toc-marks.js), and its link previews how many
 * of each its section holds. The element is a `LeafElement` for this alone: its
 * `render()` reads those readings, so it draws again exactly when they change, in the
 * nodes the outline already has; the frame, the outline and the map's geometry stay
 * this module's own work, which no reading starts. The marks move nothing: a row's
 * mark stands out of flow on the outline's rule or is the map's marker for the row,
 * and a changed section is drawn as its stretch of that rule or spine (toc.css).
 *
 * Every link is a real fragment link. The
 * browser owns its navigation, history, :target state, wheel input, and scroll
 * restoration; hidden-until-found reveals a disclosure or tab containing the target.
 * On an initial load the shared arrival pass runs after all widgets settle, so it can
 * honor a generated target that did not exist during HTML parsing. */
import { render } from "/vendor/lit.js";
import {
  comparisonChanges,
  frameFor,
  holdFocus,
  landingInsets,
  readObligations,
  readThreads,
  scrollerFor,
  whileConnected,
  named,
} from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { sizeObserver } from "/runtime/lib/frame-pass.js";
import { atLayoutPrecision, keeps, layoutPx } from "/runtime/lib/keeps.js";

// The lens is never shorter than this, or than 1.2% of the map, so it stays in sight.
const LENS_FLOOR = 14;

customElements.define(
  "lf-toc",
  class extends LeafElement {
    /** @type {Element | null} */
    #main = null;
    #connectedBefore = false;
    /** @type {ReturnType<typeof drawToc> | undefined} */
    #drawingOwner;
    get #drawing() {
      return (this.#drawingOwner ??= drawToc(this, { label: named }));
    }
    get #nav() {
      return this.#drawing.nav;
    }
    get #rows() {
      return this.#drawing.track;
    }
    // The element focus is on, in the tree this map stands in.
    get #focused() {
      return /** @type {Document | ShadowRoot} */ (this.getRootNode()).activeElement;
    }
    get #lens() {
      return this.#drawing.lens;
    }
    /** @type {{animation: Animation, effect: KeyframeEffect} | null} */
    #lensMotion = null;
    #lensInputs = "";
    /** @type {ReturnType<ReturnType<typeof drawToc>["sections"]>} */
    #sections = [];
    // `shown`: whether the row stands on the map, its heading shown and its section not
    // left out for room.
    /** @typedef {{section: ReturnType<ReturnType<typeof drawToc>["sections"]>[number], position: number, shown: boolean, mapPosition?: number}} MeasuredSection */
    /** @type {MeasuredSection[]} */
    #measured = [];
    // The headings of the sections off the map, their heading hidden or no room left
    // for them (`#fitLabels`); empty where the outline isn't a map.
    /** @type {Set<Element | null>} */
    #offMap = new Set();
    #mapHeight = 1;
    #contentStart = 0;
    #contentEnd = 1;
    /** @type {HTMLAnchorElement | null} */
    #currentLink = null;
    /** @type {HTMLElement | null} */
    #currentMarker = null;
    /** @type {Element | null} */
    #scroller = null;
    /** @type {(() => void) | undefined} */
    #stopWatching;
    /** @type {{watching: ResizeObserver, renamed: MutationObserver} | null} */
    #observers = null;
    /** @type {boolean | undefined} */
    #flowOpen;

    #onInterface = () => {
      this.#reconcile();
      this.#measure();
    };
    #onPresentation = () => this.#measure();

    connectedCallback() {
      super.connectedCallback();
      render(this.#drawing.render(), this, { host: this });
      const main = this.#drawing.scope();
      const again = this.#connectedBefore;
      this.#connectedBefore = true;
      if (again && main === this.#main && scrollerFor(main) === this.#scroller) return;
      // Moving to another reading region changes the resources, even if the
      // arrival batch keeps this element connected throughout the move.
      this.#stopWatching?.();
      this.#main = main;
      if (!main) return;
      this.#reconcile();
      this.#stopWatching = whileConnected(this, (signal) => this.#watch(signal));
    }

    // Authored revisions retain this widget when its own markup did not change, and
    // the outline retains rows by the heading's authored id or node identity. A
    // destination may serve several headings, and grouping can change it without
    // changing a row.
    #reconcile() {
      const previous = this.#sections.map(({ destination }) => destination);
      const held = this.#sections.find(({ link }) => link === this.#focused);
      const restore = held && holdFocus(this.#nav);
      render(this.#drawing.render(), this, { host: this });
      this.#sections = this.#drawing.sections();
      // A new key still represents the user's place when its heading or destination
      // survives. Restore focus if Lit moved a retained row through the DOM.
      if (restore) {
        const continuation =
          this.#sections.find(({ heading }) => heading === held.heading) ??
          this.#sections.find(
            ({ destination }) => destination.id === held.destination.id,
          );
        restore(continuation?.link);
      }
      this.#observeDestinations(previous);
      // Rows for new headings take their marks from the next render.
      this.requestUpdate();
    }

    // The drawing as it stands with each section's marks, read again whenever the page's
    // threads, the obligations waiting on the user or the version comparison change
    // (toc-marks.js), or other sections leave the map, and not for a scroll or a
    // pointer. A section off the map starts no stretch, so its marks count in the row
    // above it, as a heading past `max-level` does. It draws the outline `#reconcile`
    // last read, in the same nodes.
    render() {
      const main = this.#main;
      const standing = this.#sections.filter(
        (section) => !this.#offMap.has(section.heading),
      );
      this.#drawing.mark(
        main
          ? sectionMarks(main, standing, {
              threads: readThreads().threads,
              onMe: readObligations(main).user,
              changes: comparisonChanges(main),
            })
          : new Map(),
      );
      return this.#drawing.render(null);
    }

    /** @param {Element[]} [previous] */
    #observeDestinations(previous = []) {
      const observers = this.#observers;
      if (!observers) return;
      for (const destination of previous)
        if (destination !== this.#main) observers.watching.unobserve(destination);
      observers.renamed.disconnect();
      // The complete destination reports section growth and title-group layout,
      // including an eyebrow changing size while its heading stays the same.
      for (const { destination } of this.#sections) {
        if (destination !== this.#main) observers.watching.observe(destination);
        observers.renamed.observe(destination, { attributeFilter: ["id"] });
      }
    }

    /** @param {AbortSignal} signal */
    #watch(signal) {
      this.#main = this.#drawing.scope();
      if (!this.#main) return;
      this.#scroller = scrollerFor(this.#main);
      // Root scrolling is reported on Document; nested scrollports report on the
      // element itself. Keep one paint path while using the platform's event target for
      // each kind of scroller.
      const scrollSource =
        this.#scroller === document.scrollingElement ? document : this.#scroller;
      // The map writes only its own geometry. Measure during size delivery so
      // the document and its section lengths paint together.
      const watching = sizeObserver(() => this.#measure());
      watching.observe(this.#main);
      const renamed = new MutationObserver(() => {
        this.#reconcile();
        this.#scheduleMeasure();
      });
      this.#observers = { watching, renamed };
      this.#observeDestinations();
      const passive = { passive: true, signal };
      scrollSource.addEventListener("scroll", this.#schedulePaint, passive);
      for (const type of ["toggle", "load"])
        this.#main.addEventListener(type, this.#scheduleMeasure, {
          capture: true,
          signal,
        });
      this.#main.addEventListener("lf-layout", this.#scheduleMeasure, { signal });
      document.addEventListener("lf-presentation", this.#onPresentation, { signal });
      document.addEventListener("lf-page-interface", this.#onInterface, { signal });
      window.addEventListener("resize", this.#scheduleMeasure, { signal });
      matchMedia("print").addEventListener("change", this.#onPresentation, {
        signal,
      });
      this.#scheduleMeasure();
      return () => {
        watching.disconnect();
        renamed.disconnect();
        this.#observers = null;
        this.#lensMotion?.animation.cancel();
        this.#lensMotion = null;
        this.#lensInputs = "";
      };
    }

    #scheduleMeasure = frameFor(this, () => this.#measure());

    #measure() {
      if (!this.#main || !this.#scroller) return;
      const { disclosure, summary } = this.#drawing;
      // CSS already owns posture. A hidden summary means these links are an
      // always-exposed outline, which requires native open state in every engine.
      if (getComputedStyle(summary).display === "none") {
        this.#flowOpen ??= disclosure.open;
        if (!disclosure.open) disclosure.open = true;
      } else if (this.#flowOpen !== undefined) {
        const open = this.#flowOpen || this.#rows.contains(this.#focused);
        if (disclosure.open !== open) disclosure.open = open;
        this.#flowOpen = undefined;
      }
      const [first] = this.#sections;
      if (!first) {
        this.#measured = [];
        this.#paint();
        return;
      }
      const main = this.#main,
        scroller = this.#scroller;
      const mainTop = this.#documentTop(main, scroller, main);
      const start = this.#documentTop(first.destination, scroller, main);
      let previous = start;
      this.#measured = this.#sections.map((section) => {
        const shown =
          section.destination === main || section.destination.checkVisibility();
        const position = shown
          ? Math.max(previous, this.#documentTop(section.destination, scroller, main))
          : previous;
        previous = position;
        return { section, shown, position };
      });
      this.#contentStart = start;
      this.#contentEnd = Math.max(
        mainTop +
          main.clientTop +
          main.scrollHeight -
          parseFloat(getComputedStyle(main).paddingBottom),
        previous + 1,
      );
      this.#fitRows();
      this.#lensInputs = "";
      this.#paint();
    }

    // Each fitted row's place on the map, written once on its label and its marker, and
    // its marker's stretch of the spine, from it to the next marker or the map's end, on
    // the scale the lens shares, where a changed section is drawn (toc.css).
    #fitRows() {
      for (const measured of this.#measured) delete measured.mapPosition;
      const offMap = this.#fitLabels();
      if (
        offMap.size !== this.#offMap.size ||
        [...offMap].some((heading) => !this.#offMap.has(heading))
      ) {
        this.#offMap = offMap;
        this.requestUpdate();
      }
      let next = this.#mapHeight;
      for (const measured of this.#measured.toReversed()) {
        const { row, link, marker } = measured.section;
        const at = measured.mapPosition;
        // A section off the map keeps its label's measure, hidden (toc.css), so the
        // next fit reads it as it reads the rest.
        for (const node of [link, marker])
          node.toggleAttribute("data-lf-toc-shown", measured.shown);
        if (at === undefined) {
          for (const node of [row, marker]) node.style.removeProperty("--lf-toc-at");
          marker.style.removeProperty("--lf-toc-reach");
        } else {
          for (const node of [row, marker])
            node.style.setProperty("--lf-toc-at", `${at}px`);
          marker.style.setProperty("--lf-toc-reach", `${Math.max(0, next - at)}px`);
          next = at;
        }
      }
    }

    // Sets the place on the map, `mapPosition`, of each row that stands on it, and
    // returns the headings of the sections off the map. A row's place is its section's
    // place on the document's scale, moved just enough to keep the labels distinct.
    // Labels that don't fit down the track at full size take a line each in a smaller
    // face. Where they don't fit even so, the deepest level of sections leaves the map,
    // then the next, each level trying both sizes again, until the rest fit; where even
    // the top level doesn't, as many of its sections stay as fit, spread evenly from
    // its first to its last. A section left out for room is off the map as one whose
    // heading is hidden is, so the current section is the nearest one above it on the
    // map, and its marks count in that row (`render`). The user chose this for a long
    // route over a list of every label scrolling over the map, at rest or following the
    // pointer, and over labels for the levels that fit with the other sections' labels
    // shown on hover: each kept every section on the map but showed its labels a
    // second way.
    /** @returns {Set<Element | null>} */
    #fitLabels() {
      this.removeAttribute("data-lf-compact");
      if (getComputedStyle(this.#drawing.markers).display === "none") return new Set();
      const offMap = () =>
        new Set(
          this.#measured
            .filter((measured) => !measured.shown)
            .map((measured) => measured.section.heading),
        );
      const track = this.#rows.getBoundingClientRect();
      this.#mapHeight = track.height;
      const shown = this.#measured.filter((measured) => measured.shown);
      if (!shown.length) return offMap();
      const scale = track.height / Math.max(1, this.#contentEnd - this.#contentStart);
      const lineHeight = parseFloat(getComputedStyle(this.#nav).lineHeight);
      const preferredGap = Number.isFinite(lineHeight) ? lineHeight * 0.5 : 0;

      // Each label's height and the middle of its first line in the size the map shows.
      // A label wraps by its own words alone, so one reading of each size serves every
      // set of rows.
      /** @param {MeasuredSection} measured */
      const sizeOf = ({ section: { link } }) => ({
        height: link.getBoundingClientRect().height,
        center: parseFloat(getComputedStyle(link).lineHeight) / 2,
      });
      const rows = shown.map((measured) => {
        const full = sizeOf(measured);
        return { measured, full, compact: full };
      });
      let compactRead = false;
      // Whether these rows' labels fit down the track: at full size with the preferred
      // gap between them, or a line each with whatever gap is left.
      /** @param {typeof rows} kept @param {"full" | "compact"} size */
      const fits = (kept, size) => {
        const gap = size === "full" ? preferredGap : 0;
        const height = kept.reduce((sum, row) => sum + row[size].height + gap, -gap);
        return height <= track.height + (kept[0]?.[size].center ?? 0) + 1;
      };
      /** @param {typeof rows} kept @returns {"full" | "compact" | undefined} */
      const sized = (kept) => {
        if (fits(kept, "full")) return "full";
        if (!compactRead) {
          this.setAttribute("data-lf-compact", "");
          for (const row of rows) row.compact = sizeOf(row.measured);
          compactRead = true;
        }
        return fits(kept, "compact") ? "compact" : undefined;
      };
      const depth = (/** @type {typeof rows[number]} */ { measured: { section } }) =>
        "depth" in section ? section.depth : 0;
      const levels = [...new Set(rows.map(depth))].sort((a, b) => b - a);
      let kept = rows;
      let size = sized(kept);
      for (const level of levels.slice(1)) {
        if (size) break;
        kept = rows.filter((row) => depth(row) <= level);
        size = sized(kept);
      }
      if (!size) {
        const top = kept;
        // `count` of the top level's sections, spread evenly from its first to its last.
        /** @param {number} count */
        const spread = (count) => {
          const picked = new Set(
            Array.from({ length: count }, (_, index) =>
              Math.round((index * (top.length - 1)) / Math.max(1, count - 1)),
            ),
          );
          return top.filter((_, index) => picked.has(index));
        };
        // The most that fit, found by halving: the first and last stay whatever the room.
        let fit = Math.min(2, top.length);
        let over = top.length;
        while (over - fit > 1) {
          const count = Math.floor((fit + over) / 2);
          if (sized(spread(count))) fit = count;
          else over = count;
        }
        kept = spread(fit);
        size = sized(kept) ?? "compact";
      }
      this.toggleAttribute("data-lf-compact", size === "compact");
      const standing = new Set(kept);
      for (const row of rows) if (!standing.has(row)) row.measured.shown = false;
      const placing = kept.map((row) => ({
        measured: row.measured,
        ideal: (row.measured.position - this.#contentStart) * scale,
        ...row[size],
      }));
      const labelHeight = placing.reduce((sum, label) => sum + label.height, 0);
      const firstCenter = placing[0]?.center ?? 0;
      const gap =
        placing.length > 1
          ? Math.max(
              0,
              Math.min(
                preferredGap,
                (track.height + firstCenter - labelHeight) / (placing.length - 1),
              ),
            )
          : 0;

      let prefix = 0;
      const labels = placing.map((label) => {
        const placed = { ...label, prefix };
        prefix += label.height + gap;
        return placed;
      });
      const occupiedHeight = Math.max(0, prefix - gap);
      // Pool adjacent labels that overlap into one weighted block. Each block
      // retains its labels directly, so fitting needs no parallel index ranges.
      /** @type {{labels: typeof labels, top: number, count: number}[]} */
      const blocks = [];
      for (const label of labels) {
        let block = {
          labels: [label],
          top: label.ideal - label.center - label.prefix,
          count: 1,
        };
        let previous = blocks.at(-1);
        while (previous && previous.top > block.top) {
          blocks.pop();
          const count = previous.count + block.count;
          block = {
            labels: [...previous.labels, ...block.labels],
            top: (previous.top * previous.count + block.top * block.count) / count,
            count,
          };
          previous = blocks.at(-1);
        }
        blocks.push(block);
      }

      const floor = -firstCenter;
      const ceiling = track.height - occupiedHeight;
      for (const block of blocks) {
        const top = Math.max(floor, Math.min(ceiling, block.top));
        for (const label of block.labels)
          label.measured.mapPosition = top + label.prefix + label.center;
      }
      return offMap();
    }

    /** @param {number} position */
    #mapPosition(position) {
      /** @type {{documentPosition: number, mapPosition: number}[]} */
      const anchors = [];
      for (const measured of this.#measured) {
        const { shown, position: documentPosition, mapPosition } = measured;
        if (!shown || mapPosition === undefined || !Number.isFinite(mapPosition))
          continue;
        const anchor = { documentPosition, mapPosition };
        if (anchors.at(-1)?.documentPosition === documentPosition) anchors.pop();
        anchors.push(anchor);
      }
      const [first, ...rest] = anchors;
      if (!first) {
        const total = Math.max(1, this.#contentEnd - this.#contentStart);
        return (
          Math.max(0, Math.min(1, (position - this.#contentStart) / total)) *
          this.#mapHeight
        );
      }
      if (position <= first.documentPosition) return first.mapPosition;
      let previous = first;
      for (const next of rest) {
        if (position > next.documentPosition) {
          previous = next;
          continue;
        }
        const distance = Math.max(1, next.documentPosition - previous.documentPosition);
        const progress = (position - previous.documentPosition) / distance;
        return (
          previous.mapPosition + progress * (next.mapPosition - previous.mapPosition)
        );
      }
      const distance = Math.max(1, this.#contentEnd - previous.documentPosition);
      const progress = Math.max(
        0,
        Math.min(1, (position - previous.documentPosition) / distance),
      );
      return previous.mapPosition + progress * (this.#mapHeight - previous.mapPosition);
    }

    /** @param {Element} element @param {Element} scroller @param {Element} main */
    #documentTop(element, scroller, main) {
      /** @type {Element | null} */
      let candidate = element;
      for (; candidate; candidate = candidate.parentElement) {
        const box = candidate.getBoundingClientRect();
        if (box.width || box.height) return box.top + scroller.scrollTop;
        if (candidate === main) break;
      }
      const mainBox = main.getBoundingClientRect();
      return mainBox.top + scroller.scrollTop;
    }

    #schedulePaint = frameFor(this, () => this.#paint());

    #paint() {
      if (!this.#scroller) return;
      let current = this.#measured.find((measured) => measured.shown);
      if (!current) {
        this.#currentLink?.removeAttribute("aria-current");
        this.#currentMarker?.removeAttribute("data-lf-current");
        this.#currentLink = null;
        this.#currentMarker = null;
        this.#lensMotion?.animation.cancel();
        this.#lensMotion = null;
        this.#lensInputs = "";
        keeps(this.#lens, "style", "display: none;");
        return;
      }
      // What the user can read is the scroller's landing band, clear of whatever stands
      // over its top and the floating panel's row over its bottom.
      const clear = landingInsets(this.#scroller);
      const visibleStart = this.#scroller.scrollTop + clear.top;
      const visibleEnd =
        this.#scroller.scrollTop + this.#scroller.clientHeight - clear.bottom;
      this.#standLens(clear, this.#scroller);

      const threshold = visibleStart + Math.min(32, (visibleEnd - visibleStart) * 0.08);
      // At the scroller's end the last section shown is current, though its heading
      // stands below the threshold. Fractional layout and scaled displays can leave a
      // scroll a pixel or so short of the end, so within two pixels counts as there.
      const { scrollHeight, clientHeight, scrollTop } = this.#scroller;
      const end = scrollHeight - clientHeight - scrollTop <= 2;
      for (const measured of this.#measured)
        if (measured.shown && (end || measured.position <= threshold))
          current = measured;
      // A revision can give the current section a new link and keep its marker, which
      // the markers' positional rendering reuses (toc-view.js).
      const { link, marker } = current.section;
      if (link !== this.#currentLink) {
        this.#currentLink?.removeAttribute("aria-current");
        link.setAttribute("aria-current", "location");
        this.#currentLink = link;
      }
      if (marker !== this.#currentMarker) {
        this.#currentMarker?.removeAttribute("data-lf-current");
        marker.setAttribute("data-lf-current", "");
        this.#currentMarker = marker;
      }
    }

    // Keyframes are set again only when a measure has moved the map, or the scroller's
    // length or landing band has changed; a scroll alone reaches the early return.
    /** @param {{top: number, bottom: number}} clear @param {Element} scroller */
    #standLens(clear, scroller) {
      const reach = scroller.scrollHeight - scroller.clientHeight;
      const band = scroller.clientHeight - clear.top - clear.bottom;
      const inputs = `${reach} ${band} ${clear.top}`;
      if (inputs === this.#lensInputs) return;
      this.#lensInputs = inputs;
      const floor = Math.max(LENS_FLOOR, this.#mapHeight * 0.012);
      const span = (/** @type {number} */ scrolled) => {
        const start = this.#mapPosition(scrolled + clear.top);
        return {
          start,
          size: Math.max(start, this.#mapPosition(scrolled + clear.top + band)) - start,
        };
      };
      // Both at layout's 1/64px, so a measure that jitters below it writes nothing new.
      const transform = (
        /** @type {{start: number, size: number}} */ { start, size },
      ) =>
        `translateY(${layoutPx(start)}) scaleY(${atLayoutPrecision(Math.max(floor, size))})`;
      if (reach <= 0) {
        this.#lensMotion?.animation.cancel();
        this.#lensMotion = null;
        keeps(this.#lens, "style", `transform: ${transform(span(0))};`);
        return;
      }
      // The map is linear between the scroll positions where the band's top or foot
      // meets a destination or the document's ends, and where the lens meets its floor.
      const bends = [
        this.#contentStart,
        this.#contentEnd,
        ...this.#measured.map(({ position }) => position),
      ]
        .flatMap((position) => [position - clear.top, position - clear.top - band])
        .filter((scrolled) => scrolled > 0 && scrolled < reach);
      const stops = [...new Set([0, reach, ...bends])].sort((a, b) => a - b);
      const floored = stops.flatMap((scrolled, index) => {
        const next = stops[index + 1];
        if (next === undefined) return [scrolled];
        const [from, to] = [span(scrolled).size, span(next).size];
        if ((from - floor) * (to - floor) >= 0) return [scrolled];
        return [
          scrolled,
          scrolled + ((floor - from) / (to - from)) * (next - scrolled),
        ];
      });
      const frames = floored.map((scrolled) => ({
        offset: scrolled / reach,
        transform: transform(span(scrolled)),
      }));
      this.#lens.removeAttribute("style");
      if (this.#lensMotion) this.#lensMotion.effect.setKeyframes(frames);
      else {
        const effect = new KeyframeEffect(this.#lens, frames, { fill: "both" });
        const animation = new Animation(
          effect,
          new ScrollTimeline({ source: scroller, axis: "block" }),
        );
        this.#lensMotion = { effect, animation };
        animation.play();
      }
    }
  },
);
