import { drawToc } from "./toc-view.js";
/* lf-toc: navigation derived from the headings the page already says.
 *
 * The outline, the destination of each of its links and the frame that holds them are
 * `toc-view.js`'s. The module redraws the outline in those same nodes
 * whenever the document's headings change, and measures and moves the map.
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
  inChrome,
  render,
  keeps,
  landingInsets,
  LAYOUT,
  layoutPx,
  once,
  PAGE_INTERFACE,
  PRESENTATION,
  scrollerFor,
  scrollIntoView,
  scrollLimit,
  sizeObserver,
  whileConnected,
  wrote,
  focused,
  currentLocationIn,
} from "/runtime/widget-api.js";

// The lens is never shorter than this, or than 1.2% of the map, so it stays in sight.
const LENS_FLOOR = 14;
// Firefox lacks ScrollTimeline.
const SCROLL_TIMELINE = "ScrollTimeline" in globalThis;
// Without a scroll timeline the lens's animation lasts this many milliseconds over the
// whole scroll, long enough that no browser's clamped timer precision steps it.
const LENS_DURATION = 1_000_000;

customElements.define(
  "lf-toc",
  class extends HTMLElement {
    /** @type {Element | null} */
    #main = null;
    /** @type {ReturnType<typeof drawToc> | undefined} */
    #drawingOwner;
    get #drawing() {
      return (this.#drawingOwner ??= drawToc(this, {
        label: wrote,
        chrome: inChrome,
        lends: true,
      }));
    }
    get #nav() {
      return this.#drawing.nav;
    }
    get #rows() {
      return this.#drawing.track;
    }
    get #lens() {
      return this.#drawing.lens;
    }
    /** @type {{animation: Animation, effect: KeyframeEffect} | null} */
    #lensMotion = null;
    #lensInputs = "";
    /** @type {ReturnType<ReturnType<typeof drawToc>["sections"]>} */
    #sections = [];
    /** @typedef {{section: ReturnType<ReturnType<typeof drawToc>["sections"]>[number], position: number, shown: boolean, mapPosition?: number}} MeasuredSection */
    /** @type {MeasuredSection[]} */
    #measured = [];
    #mapHeight = 1;
    #contentStart = 0;
    #contentEnd = 1;
    /** @type {HTMLAnchorElement | null} */
    #currentLink = null;
    /** @type {Element | null} */
    #scroller = null;
    /** @type {(() => void) | undefined} */
    #stopWatching;
    /** @type {{watching: ResizeObserver, renamed: MutationObserver} | null} */
    #observers = null;
    #navHeight = 0;
    /** @type {Element | null} */
    #focusedLink = null;
    #focusedVisible = false;
    /** @type {boolean | undefined} */
    #flowOpen;

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
      render(this.#drawing.render(), this, { host: this });
      const main = this.#drawing.scope();
      if (!once(this) && main === this.#main && scrollerFor(main) === this.#scroller)
        return;
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
      const held = this.#sections.find(({ link }) => link === focused());
      const restore = held && holdFocus(this.#nav);
      render(
        this.#drawing.render({
          label: wrote,
          chrome: inChrome,
          lends: true,
        }),
        this,
        { host: this },
      );
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
      matchMedia("print").addEventListener("change", this.#onPresentation, { signal });
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
      if (!this.#main || !this.#scroller || !this.#rows) return;
      const { disclosure, summary } = this.#drawing;
      // CSS already owns posture. A hidden summary means these links are an
      // always-exposed outline, which requires native open state in every engine.
      if (getComputedStyle(summary).display === "none") {
        this.#flowOpen ??= disclosure.open;
        if (!disclosure.open) disclosure.open = true;
      } else if (this.#flowOpen !== undefined) {
        const open = this.#flowOpen || currentLocationIn(this.#rows);
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
      this.#measured.forEach((measured, index) => {
        const { row } = measured.section;
        row.toggleAttribute("data-lf-toc-hidden", !measured.shown);
        const next =
          this.#measured.find((other, at) => at > index && other.shown)?.position ??
          this.#contentEnd;
        row.style.setProperty(
          "--lf-toc-span",
          measured.shown ? String(Math.max(1, next - measured.position)) : "0",
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
      for (const measured of this.#measured) delete measured.mapPosition;
      const shifts = this.#fitLabels();
      for (const measured of this.#measured) {
        const shift = shifts.get(measured);
        if (shift !== undefined)
          measured.section.row.style.setProperty("--lf-toc-row-shift", `${shift}px`);
        else measured.section.row.style.removeProperty("--lf-toc-row-shift");
      }
    }

    #rememberFocus() {
      const viewport = this.#nav.getBoundingClientRect();
      const active = focused(document);
      const shown =
        active && this.#nav.contains(active) ? active.getBoundingClientRect() : null;
      this.#navHeight = viewport.height;
      this.#focusedLink = active;
      this.#focusedVisible =
        !!shown && shown.top >= viewport.top - 1 && shown.bottom <= viewport.bottom + 1;
    }

    // Each fitted row's shift, by section index.
    #fitLabels() {
      /** @type {Map<MeasuredSection, number>} */
      const shifts = new Map();
      this.removeAttribute("data-lf-compact");
      this.removeAttribute("data-lf-outline");
      if (getComputedStyle(this.#rows).display !== "flex") return shifts;
      const track = this.#rows.getBoundingClientRect();
      this.#mapHeight = track.height;

      const readLabels = () => {
        const labels = this.#measured.flatMap((measured) => {
          const { row, link } = measured.section;
          return measured.shown
            ? [
                {
                  measured,
                  ideal: row.getBoundingClientRect().top - track.top,
                  height: link.getBoundingClientRect().height,
                  center: parseFloat(getComputedStyle(link).lineHeight) / 2,
                },
              ]
            : [];
        });
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
        layout.labelHeight +
          layout.preferredGap * Math.max(0, layout.labels.length - 1) >
        layout.availableHeight + 1
      ) {
        this.setAttribute("data-lf-compact", "");
        layout = readLabels();
      }
      if (layout.labelHeight > layout.availableHeight + 1) {
        this.removeAttribute("data-lf-compact");
        this.setAttribute("data-lf-outline", "");
        if (
          currentLocationIn(this.#nav) &&
          this.#focusedLink === focused(document) &&
          this.#focusedVisible &&
          this.#nav.getBoundingClientRect().height < this.#navHeight - 1
        )
          scrollIntoView(this.#focusedLink, { block: "nearest", within: this.#nav });
        return shifts;
      }

      let prefix = 0;
      const labels = layout.labels.map((label) => {
        const placed = { ...label, prefix };
        prefix += label.height + layout.gap;
        return placed;
      });
      const occupiedHeight = Math.max(0, prefix - layout.gap);
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

      const floor = -layout.firstCenter;
      const ceiling = track.height - occupiedHeight;
      for (const block of blocks) {
        const top = Math.max(floor, Math.min(ceiling, block.top));
        for (const label of block.labels) {
          const fitted = top + label.prefix + label.center;
          label.measured.mapPosition = fitted;
          shifts.set(label.measured, fitted - label.ideal);
        }
      }
      return shifts;
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
      if (!this.#rows || !this.#scroller) return;
      let current = this.#measured.find((measured) => measured.shown);
      if (!current) {
        this.#currentLink?.removeAttribute("aria-current");
        this.#currentLink = null;
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
      if (!SCROLL_TIMELINE && this.#lensMotion)
        this.#lensMotion.animation.currentTime =
          (LENS_DURATION * this.#scroller.scrollTop) / scrollLimit(this.#scroller);

      const threshold = visibleStart + Math.min(32, (visibleEnd - visibleStart) * 0.08);
      const end = atScrollEnd(this.#scroller);
      for (const measured of this.#measured)
        if (measured.shown && (end || measured.position <= threshold))
          current = measured;
      const link = current.section.link;
      if (link === this.#currentLink) return;
      this.#currentLink?.removeAttribute("aria-current");
      link.setAttribute("aria-current", "location");
      this.#currentLink = link;
    }

    // Keyframes are set again only when a measure has moved the map, or the scroller's
    // length or landing band has changed; a scroll alone reaches the early return.
    /** @param {{top: number, bottom: number}} clear @param {Element} scroller */
    #standLens(clear, scroller) {
      const reach = scrollLimit(scroller);
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
        const effect = new KeyframeEffect(
          this.#lens,
          frames,
          SCROLL_TIMELINE
            ? { fill: "both" }
            : { duration: LENS_DURATION, fill: "both" },
        );
        const animation = new Animation(
          effect,
          SCROLL_TIMELINE
            ? new globalThis.ScrollTimeline({ source: scroller, axis: "block" })
            : document.timeline,
        );
        this.#lensMotion = { effect, animation };
        animation.play();
        if (!SCROLL_TIMELINE) animation.pause();
      }
    }
  },
);
