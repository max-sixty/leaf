/* A recording's time axis: one horizontal scale shared by a ruler, labeled lanes
 * and a playhead. Every mark's left edge is its recorded time. An interval is a bar
 * from its recorded start to its recorded end; an instant is a hairline. Labels
 * annotate marks and never stand for time: an input label starts at its first
 * call, and calls too close to label separately share one label listing them in
 * order, while each keeps its own bar. Lane heights depend only on the recording,
 * so zoom, playback and selection never move anything below the timeline.
 *
 * The track is a native horizontal scroller whose width is the zoom factor times
 * its box. Native scrolling pans, so wheel and touch keep their meanings: vertical
 * input scrolls the page, horizontal input pans time. Ctrl/Cmd+wheel and pinch zoom
 * about the pointer. A mouse press on the ruler or empty lane space scrubs; a tap
 * seeks; the playhead handle scrubs under any pointer. A press on a mark picks it.
 *
 * The owner supplies a model and receives time and pick callbacks. It owns which
 * capture is shown; this module owns only geometry, labels and gestures. Times are
 * milliseconds from the recording's origin.
 */
import {
  html,
  nothing,
  render,
  repeat,
  nextRender,
  cancelRender,
  sizeObserver,
  layoutPx,
} from "/runtime/widget-api.js";

const LABEL_GAP = 6;
const TICK_SPACING = 84;
const STEPS = [1, 2, 5];
const EDGE = 12;
const CLUSTER_WIDTH = 168;

// Ruler steps: 1, 2, 5 × 10^k milliseconds, the smallest at least TICK_SPACING apart.
function tickStep(pxPerMs) {
  for (let power = 1; power < 1e9; power *= 10)
    for (const step of STEPS) if (step * power * pxPerMs >= TICK_SPACING) return step * power;
  return 1e9;
}
const tickLabel = (time, step) => {
  if (time === 0) return "0 s";
  const digits = step >= 1000 ? 0 : step >= 100 ? 1 : step >= 10 ? 2 : 3;
  return `${(time / 1000).toFixed(digits)} s`;
};

// Greedy rows: an interval takes the first row whose last interval ends before it.
function assignRows(items, start, end) {
  const rows = [];
  for (const item of items.toSorted((a, b) => start(a) - start(b))) {
    let row = rows.findIndex((last) => last <= start(item));
    if (row < 0) row = rows.push(-Infinity) - 1;
    rows[row] = end(item);
    item.row = row;
  }
  return Math.max(1, rows.length);
}

let measuring = null;
function measure(text, font) {
  measuring ??= document.createElement("canvas").getContext("2d");
  measuring.font = font;
  return measuring.measureText(text).width;
}

export class RecordingTimeline {
  #host;
  #options;
  #model = null;
  #zoom = 1;
  #time = 0;
  #scrubbing = null;
  #expectedScroll = null;
  #rulerFrame = 0;
  #observer;
  #width = 0;
  #labels = { input: [], moments: [] };
  #momentRows = 1;
  #callRows = 1;

  /**
   * `host` receives the timeline. `options`: `onSeek(time, final)`, `onPick(lane,
   * id, time)`, `onUserPan()`, and `quoted` (a frozen copy takes no input).
   */
  constructor(host, options) {
    this.#host = host;
    this.#options = options;
    this.#observer = sizeObserver(() => this.#resized());
  }

  get scroller() {
    return this.#host.querySelector(".lf-trace-scroller");
  }

  get zoom() {
    return this.#zoom;
  }

  connect() {
    if (this.scroller) this.#observer.observe(this.scroller);
  }

  disconnect() {
    this.#observer.disconnect();
    if (this.#rulerFrame) cancelRender(this.#rulerFrame);
    this.#rulerFrame = 0;
  }

  /** The visible window, in recording time, for restoring a scope's view. */
  get view() {
    const scroller = this.scroller;
    if (!scroller || !this.#model) return null;
    return { zoom: this.#zoom, start: this.#pxToTime(scroller.scrollLeft) };
  }

  set view(view) {
    this.#zoom = view?.zoom ?? 1;
    this.#applyZoom();
    if (view) this.#scrollTo(this.#timeToPx(view.start));
  }

  update(model) {
    const changed = model.signature !== this.#model?.signature;
    this.#model = model;
    if (changed) {
      this.#callRows = assignRows(
        model.calls,
        (call) => call.start,
        (call) => call.end,
      );
      this.#zoom = Math.min(this.#zoom, this.#maxZoom());
    }
    this.#draw();
    if (changed) {
      this.connect();
      this.#layoutLabels(true);
    }
    this.setTime(model.time);
  }

  setTime(time) {
    this.#time = time;
    const track = this.#host.querySelector(".lf-trace-track");
    if (!track || !this.#model) return;
    track.style.setProperty("--lf-trace-time", String(this.#fraction(time)));
    this.#host
      .querySelector(".lf-trace-overview")
      ?.style.setProperty("--lf-trace-time", String(this.#fraction(time)));
  }

  /** Bring `time` into view: `center` for navigation, `page` for playback. */
  reveal(time, mode = "center") {
    const scroller = this.scroller;
    if (!scroller || this.#zoom === 1) return;
    const x = this.#timeToPx(time);
    const left = scroller.scrollLeft;
    const width = scroller.clientWidth;
    if (mode === "page") {
      if (x < left || x > left + width * 0.9) this.#scrollTo(x - width * 0.1);
    } else if (x < left + EDGE || x > left + width - EDGE) this.#scrollTo(x - width / 2);
  }

  zoomBy(factor, anchor = null) {
    const scroller = this.scroller;
    if (!scroller) return;
    const time =
      anchor ??
      (this.#visible(this.#time)
        ? this.#time
        : this.#pxToTime(scroller.scrollLeft + scroller.clientWidth / 2));
    const offset = this.#timeToPx(time) - scroller.scrollLeft;
    this.#zoom = Math.max(1, Math.min(this.#maxZoom(), this.#zoom * factor));
    this.#applyZoom();
    this.#scrollTo(this.#timeToPx(time) - offset);
  }

  fit() {
    this.#zoom = 1;
    this.#applyZoom();
    this.#scrollTo(0);
  }

  get canZoomIn() {
    return this.#zoom < this.#maxZoom();
  }

  get canZoomOut() {
    return this.#zoom > 1;
  }

  // Geometry -------------------------------------------------------------------

  #maxZoom() {
    // The narrowest window still spans 10 ms of recording.
    return Math.max(1, (this.#model?.duration ?? 0) / 10);
  }
  #trackWidth() {
    return (this.scroller?.clientWidth ?? 0) * this.#zoom;
  }
  #span() {
    return Math.max(1, this.#trackWidth() - 2 * EDGE);
  }
  #fraction(time) {
    return Math.max(0, Math.min(1, time / Math.max(1, this.#model.duration)));
  }
  #timeToPx(time) {
    return EDGE + this.#fraction(time) * this.#span();
  }
  #pxToTime(px) {
    return Math.max(
      0,
      Math.min(this.#model.duration, ((px - EDGE) / this.#span()) * this.#model.duration),
    );
  }
  #pxPerMs() {
    return this.#span() / Math.max(1, this.#model.duration);
  }
  #visible(time) {
    const scroller = this.scroller;
    const x = this.#timeToPx(time) - scroller.scrollLeft;
    return x >= 0 && x <= scroller.clientWidth;
  }
  #scrollTo(left) {
    const scroller = this.scroller;
    const max = scroller.scrollWidth - scroller.clientWidth;
    const target = Math.round(Math.max(0, Math.min(max, left)));
    if (target === Math.round(scroller.scrollLeft)) return;
    this.#expectedScroll = target;
    scroller.scrollLeft = target;
  }
  #applyZoom() {
    const track = this.#host.querySelector(".lf-trace-track");
    if (!track) return;
    track.style.setProperty("--lf-trace-zoom", String(this.#zoom));
    this.#layoutLabels(false);
    this.#drawRuler();
  }
  #resized() {
    const width = this.scroller?.clientWidth ?? 0;
    if (!width || width === this.#width || !this.#model) return;
    // A width change rescales the track. Keep the window's left time in place.
    const start = this.#width ? this.view?.start : null;
    this.#width = width;
    this.#layoutLabels(false);
    this.#drawRuler();
    if (start !== null && start !== undefined) this.#scrollTo(this.#timeToPx(start));
  }

  // Labels -----------------------------------------------------------------------

  // Labels are laid out in pixels, so they follow zoom and width. Lane heights are
  // fixed by the overview layout, which has the most collisions.
  #layoutLabels(fixHeights) {
    if (!this.#model) return;
    const track = this.#host.querySelector(".lf-trace-track");
    if (!track || !this.scroller.clientWidth) return;
    const font = getComputedStyle(track).font;
    const pxPerMs = this.#pxPerMs();
    const clusters = [];
    for (const input of this.#model.inputs) {
      const x = input.start * pxPerMs;
      const last = clusters.at(-1);
      if (last && x < last.x + last.width + LABEL_GAP) {
        last.items.push(input);
        last.text = this.#clusterText(last.items, font);
        last.width = measure(last.text, font) + 2 * 4;
      } else {
        clusters.push({ x, items: [input], text: input.label });
        clusters.at(-1).width = measure(input.label, font) + 2 * 4;
      }
    }
    this.#labels.input = clusters;
    if (fixHeights) {
      const moments = this.#model.moments.map((moment) => ({ ...moment }));
      const badge = 26;
      this.#momentRows = assignRows(
        moments,
        (moment) => moment.time * pxPerMs,
        (moment) => moment.time * pxPerMs + badge + LABEL_GAP,
      );
      this.#momentRowOf = new Map(moments.map((moment) => [moment.id, moment.row]));
    }
    this.#draw();
  }
  #momentRowOf = new Map();
  #clusterText(items, font) {
    const text = items.map((item) => item.label).join(" ");
    if (measure(text, font) <= CLUSTER_WIDTH) return text;
    return `${items[0].label} +${items.length - 1}`;
  }

  // Drawing ------------------------------------------------------------------------

  #draw() {
    const model = this.#model;
    if (!model) return;
    const fraction = (time) => String(this.#fraction(time));
    const length = (start, end) =>
      String(Math.max(0, this.#fraction(end ?? start) - this.#fraction(start)));
    const quoted = this.#options.quoted;
    const lanes = [
      ...(model.moments.length ? [["moments", "Moments"]] : []),
      ...(model.inputs.length ? [["input", "Input"]] : []),
      ...(model.calls.length ? [["calls", "Calls"]] : []),
      ["captures", "Captures"],
    ];
    render(
      html`<div class="lf-trace-lane-names" aria-hidden="true">
          <span class="lf-trace-lane-name lf-trace-lane-name-ruler"></span>
          ${lanes.map(
            ([lane, name]) =>
              html`<span
                class="lf-trace-lane-name lf-trace-lane-name-${lane}"
                style="--lf-trace-rows: ${lane === "calls"
                  ? this.#callRows
                  : lane === "moments"
                    ? this.#momentRows
                    : 1}"
                >${name}</span
              >`,
          )}
        </div>
        <div
          class="lf-trace-scroller"
          @scroll=${() => this.#scrolled()}
          @wheel=${(event) => this.#wheel(event)}
        >
          <div
            class="lf-trace-track"
            @pointerdown=${(event) => this.#press(event)}
            @click=${(event) => this.#tap(event)}
            @pointerover=${(event) => this.#hover(event)}
            @pointerout=${(event) => this.#hover(event, true)}
          >
            <div class="lf-trace-ruler"></div>
            ${model.moments.length
              ? html`<div
                  class="lf-trace-lane lf-trace-lane-moments"
                  style="--lf-trace-rows: ${this.#momentRows}"
                >
                  ${repeat(
                    model.moments,
                    (moment) => moment.id,
                    (moment) =>
                      html`<span
                        class="lf-trace-moment-pin"
                        data-pick="moments"
                        data-id=${moment.id}
                        data-tip=${moment.title}
                        ?data-current=${moment.current}
                        style="--t: ${fraction(moment.time)}; --row: ${this.#momentRowOf.get(
                          moment.id,
                        ) ?? 0}"
                        ><span class="lf-trace-moment-flag">${moment.number}</span></span
                      >`,
                  )}
                </div>`
              : nothing}
            ${model.inputs.length
              ? html`<div class="lf-trace-lane lf-trace-lane-input">
                  ${this.#labels.input.map(
                    (cluster, index) =>
                      html`<span
                        class="lf-trace-input-label"
                        data-pick="input"
                        data-id=${cluster.items[0].id}
                        data-cluster=${index}
                        data-tip=${cluster.items.map((item) => item.title).join("\n")}
                        ?data-current=${cluster.items.some((item) => item.current)}
                        style="--t: ${fraction(cluster.items[0].start)}; max-inline-size: ${layoutPx(
                          Math.max(
                            12,
                            (this.#labels.input[index + 1]?.x ?? Infinity) -
                              cluster.x -
                              LABEL_GAP,
                          ),
                        )}"
                        >${cluster.text}</span
                      >`,
                  )}
                  ${repeat(
                    model.inputs,
                    (input) => input.id,
                    (input) =>
                      html`<span
                        class="lf-trace-bar lf-trace-input-bar"
                        data-pick="input"
                        data-id=${input.id}
                        data-tip=${input.title}
                        ?data-current=${input.current}
                        ?data-active=${input.active}
                        style="--t: ${fraction(input.start)}; --d: ${length(
                          input.start,
                          input.end,
                        )}"
                      ></span>`,
                  )}
                </div>`
              : nothing}
            ${model.calls.length
              ? html`<div
                  class="lf-trace-lane lf-trace-lane-calls"
                  style="--lf-trace-rows: ${this.#callRows}"
                >
                  ${repeat(
                    model.calls,
                    (call) => call.id,
                    (call) =>
                      html`<span
                        class="lf-trace-bar lf-trace-call-bar"
                        data-pick="calls"
                        data-id=${call.id}
                        data-tip=${call.title}
                        ?data-current=${call.current}
                        ?data-active=${call.active}
                        ?data-error=${call.error}
                        style="--t: ${fraction(call.start)}; --d: ${length(
                          call.start,
                          call.end,
                        )}; --row: ${call.row ?? 0}"
                        ><span class="lf-trace-call-name">${call.label}</span></span
                      >`,
                  )}
                </div>`
              : nothing}
            <div class="lf-trace-lane lf-trace-lane-captures">
              ${repeat(
                model.captures,
                (capture) => capture.id,
                (capture) =>
                  html`<span
                    class="lf-trace-capture lf-trace-capture-${capture.kind}"
                    ?data-current=${capture.current}
                    style="--t: ${fraction(capture.time)}"
                  ></span>`,
              )}
            </div>
            <div class="lf-trace-playhead" aria-hidden="true">
              <span
                class="lf-trace-playhead-handle"
                title=${quoted ? "Selected recorded time" : "Drag to scrub the recording"}
              ></span>
            </div>
          </div>
        </div>
        <div
          class="lf-trace-overview"
          title="Whole recording; drag to move the zoomed window"
          @pointerdown=${(event) => this.#overviewPress(event)}
        >
          <span class="lf-trace-overview-window"></span>
          <span class="lf-trace-overview-time"></span>
        </div>
        <div class="lf-trace-tip" role="tooltip" hidden></div>`,
      this.#host,
    );
    const track = this.#host.querySelector(".lf-trace-track");
    track.style.setProperty("--lf-trace-zoom", String(this.#zoom));
    track.style.setProperty("--lf-trace-edge", `${EDGE}px`);
    track.style.setProperty("--lf-trace-time", String(this.#fraction(this.#time)));
    this.#drawRuler();
  }

  // The overview shows the visible window within the whole recording.
  #drawOverview() {
    const scroller = this.scroller;
    const overview = this.#host.querySelector(".lf-trace-overview");
    if (!scroller?.scrollWidth || !overview) return;
    overview.style.setProperty(
      "--lf-trace-window-start",
      String(scroller.scrollLeft / scroller.scrollWidth),
    );
    overview.style.setProperty(
      "--lf-trace-window-size",
      String(scroller.clientWidth / scroller.scrollWidth),
    );
    overview.toggleAttribute("data-zoomed", this.#zoom > 1);
  }

  #overviewPress(event) {
    if (event.button !== 0 || this.#zoom === 1) return;
    event.preventDefault();
    const overview = event.currentTarget;
    overview.setPointerCapture(event.pointerId);
    const pan = (moved) => {
      const box = overview.getBoundingClientRect();
      const scroller = this.scroller;
      const fraction = (moved.clientX - box.left) / box.width;
      this.#options.onUserPan?.();
      this.#scrollTo(fraction * scroller.scrollWidth - scroller.clientWidth / 2);
      this.#drawOverview();
    };
    pan(event);
    const end = () => {
      overview.removeEventListener("pointermove", pan);
      overview.removeEventListener("pointerup", end);
      overview.removeEventListener("pointercancel", end);
    };
    overview.addEventListener("pointermove", pan);
    overview.addEventListener("pointerup", end);
    overview.addEventListener("pointercancel", end);
  }

  // The ruler draws only ticks near the visible window, so deep zoom stays cheap.
  #drawRuler() {
    this.#drawOverview();
    const ruler = this.#host.querySelector(".lf-trace-ruler");
    const scroller = this.scroller;
    if (!ruler || !scroller?.clientWidth || !this.#model) return;
    const pxPerMs = this.#pxPerMs();
    const step = tickStep(pxPerMs);
    const minor = step / (String(step)[0] === "2" ? 4 : 5);
    const from = this.#pxToTime(scroller.scrollLeft - TICK_SPACING);
    const to = this.#pxToTime(scroller.scrollLeft + scroller.clientWidth + TICK_SPACING);
    const ticks = [];
    for (let time = Math.floor(from / minor) * minor; time <= to; time += minor) {
      const rounded = Math.round(time * 1000) / 1000;
      if (rounded < 0 || rounded > this.#model.duration) continue;
      const major = Math.abs(rounded / step - Math.round(rounded / step)) < 1e-6;
      ticks.push({ time: rounded, major });
    }
    render(
      repeat(
        ticks,
        (tick) => `${step}:${tick.time}`,
        (tick) =>
          html`<span
            class="lf-trace-tick ${tick.major ? "lf-trace-tick-major" : ""}"
            style="--t: ${this.#fraction(tick.time)}"
            >${tick.major ? tickLabel(tick.time, step) : nothing}</span
          >`,
      ),
      ruler,
    );
  }

  // Gestures -------------------------------------------------------------------------

  #scrolled() {
    const scroller = this.scroller;
    if (this.#expectedScroll !== null) {
      const expected = this.#expectedScroll;
      if (Math.abs(scroller.scrollLeft - expected) < 1.5) {
        this.#expectedScroll = null;
        this.#queueRuler();
        return;
      }
    }
    this.#options.onUserPan?.();
    this.#queueRuler();
  }
  #queueRuler() {
    this.#rulerFrame ||= nextRender(() => {
      this.#rulerFrame = 0;
      this.#drawRuler();
    });
  }

  #wheel(event) {
    // Pinch arrives as Ctrl+wheel; Cmd+wheel is the macOS mouse equivalent.
    if (!(event.ctrlKey || event.metaKey) || this.#options.quoted) return;
    event.preventDefault();
    const scroller = this.scroller;
    const x = event.clientX - scroller.getBoundingClientRect().left + scroller.scrollLeft;
    this.zoomBy(Math.exp(-event.deltaY / 200), this.#pxToTime(x));
    this.#options.onUserPan?.();
  }

  #eventTime(event) {
    const scroller = this.scroller;
    return this.#pxToTime(
      event.clientX - scroller.getBoundingClientRect().left + scroller.scrollLeft,
    );
  }

  #press(event) {
    if (this.#options.quoted || event.button !== 0) return;
    const handle = event.target.closest(".lf-trace-playhead-handle");
    // A finger pans the track natively; only the handle scrubs under touch.
    if (event.pointerType === "touch" && !handle) return;
    if (!handle && event.target.closest("[data-pick]")) return;
    event.preventDefault();
    const track = event.currentTarget;
    track.setPointerCapture(event.pointerId);
    this.#scrubbing = event.pointerId;
    this.#hideTip();
    this.#options.onSeek(this.#eventTime(event), false);
    const move = (moved) => {
      if (moved.pointerId === this.#scrubbing)
        this.#options.onSeek(this.#eventTime(moved), false);
    };
    const end = (ended) => {
      if (ended.pointerId !== this.#scrubbing) return;
      this.#scrubbing = null;
      track.removeEventListener("pointermove", move);
      track.removeEventListener("pointerup", end);
      track.removeEventListener("pointercancel", end);
      this.#options.onSeek(this.#eventTime(ended), true);
    };
    track.addEventListener("pointermove", move);
    track.addEventListener("pointerup", end);
    track.addEventListener("pointercancel", end);
  }

  #tap(event) {
    if (this.#options.quoted) return;
    const pick = event.target.closest("[data-pick]");
    if (pick) {
      let id = pick.dataset.id;
      const time = this.#eventTime(event);
      // A shared label picks the call nearest the press.
      if (pick.dataset.cluster !== undefined) {
        const items = this.#labels.input[Number(pick.dataset.cluster)].items;
        id = items.reduce((best, item) =>
          Math.abs(item.start - time) < Math.abs(best.start - time) ? item : best,
        ).id;
      }
      this.#options.onPick(pick.dataset.pick, id, time);
      return;
    }
    // A mouse press already scrubbed; a tap seeks once.
    if (event.pointerType === "touch" || event.detail === 0)
      this.#options.onSeek(this.#eventTime(event), true);
  }

  #hover(event, leaving = false) {
    const pick = event.target.closest?.("[data-pick]");
    if (leaving || !pick || this.#scrubbing !== null) {
      if (!leaving || !pick?.contains(event.relatedTarget)) this.#hideTip();
      return;
    }
    const tip = this.#host.querySelector(".lf-trace-tip");
    tip.textContent = pick.dataset.tip;
    tip.hidden = false;
    const host = this.#host.getBoundingClientRect();
    const box = pick.getBoundingClientRect();
    const width = tip.offsetWidth;
    tip.style.left = layoutPx(
      Math.max(0, Math.min(host.width - width, box.left - host.left)),
    );
    tip.style.top = layoutPx(box.top - host.top - tip.offsetHeight - 4);
  }
  #hideTip() {
    const tip = this.#host.querySelector(".lf-trace-tip");
    if (tip) tip.hidden = true;
  }
}
