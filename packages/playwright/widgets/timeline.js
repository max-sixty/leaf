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
import { html, keyed, nothing, render, repeat } from "/vendor/lit.js";
import {
  setScroll,
  frameFor,
  sizeObserver,
  whileConnected,
  layoutPx,
  keeps,
  pressIsKeyboardActivation,
  assignRows,
  axisTicks,
  textWidth as measure,
  AXIS_EDGE as EDGE,
  AXIS_LABEL_CHROME as LABEL_CHROME,
  AXIS_LABEL_GAP as LABEL_GAP,
  AXIS_TICK_SPACING as TICK_SPACING,
} from "/runtime/widget-api.js";

/** @typedef {{name: string, detail: string[]}} Tip */
/** @typedef {{id: string, label: string, tip: Tip, current: boolean}} NamedMark */
/** @typedef {NamedMark & {start: number, end: number, active: boolean}} CallMark */
/** @typedef {CallMark & ({send: number} | {send: null})} InputMark */
/** @typedef {CallMark & {error: boolean}} OtherCallMark */
/** @typedef {{id: string, number: number, time: number, tip: Tip, current: boolean}} MomentMark */
/** @typedef {{id: string, time: number, image: boolean, current: boolean}} CaptureMark */
/** @typedef {{signature: string, duration: number, time: number, moments: MomentMark[], inputs: InputMark[], calls: OtherCallMark[], captures: CaptureMark[]}} TimelineModel */
/** @typedef {NamedMark & {at: number}} LabelItem */
/** @typedef {{x: number, items: [LabelItem, ...LabelItem[]], from: number, to: number, compact: boolean, text: string, width: number, flip: boolean, spread: boolean}} LabelCluster */
/** @typedef {{onSeek: (time: number, final: boolean) => void, onPick: (lane: "input" | "moments" | "calls", id: string, time: number) => void, onUserPan?: () => void, onZoom?: () => void, quoted: boolean}} TimelineOptions */
/** @typedef {{zoom: number, start: number}} TimelineView */
/** @typedef {{target: Element, clientX: number}} MarkPoint */

const CLUSTER_WIDTH = 168;

// What a mark says to a pointer resting on it or a finger holding it, as its preview
// (`lfPreview`, module-input.md, "Previews"): its name, then its time and what else the
// recording says of it. A time keeps its unit on its line. It is about the lane the mark
// stands in, which the user reads along, so the preview keeps clear of the whole lane.
// The lane's marks are thinner than the preview owner's hit tests are apart, so naming
// the lane is what keeps the preview off the mark's neighbours.
/** @param {string} text */
const kept = (text) => text.replace(/(\d) s\b/g, "$1\u00a0s");
/** @param {Element} mark */
const laneOf = (mark) => mark.closest(".lf-trace-lane");
/** @param {Tip} tip */
const said = (tip) =>
  /** @this {Element} */
  function () {
    return { name: kept(tip.name), detail: tip.detail.map(kept), about: laneOf(this) };
  };
// The marks one label holds: how many, then each one's words on a line of its own.
/** @param {readonly {tip: Tip}[]} items @param {string} kind */
const saidOfAll = (items, kind) =>
  items.length === 1 && items[0]
    ? said(items[0].tip)
    : /** @this {Element} */
      function () {
        return {
          name: `${items.length} ${kind}`,
          detail: items.map(({ tip }) => kept([tip.name, ...tip.detail].join(" · "))),
          about: laneOf(this),
        };
      };

export class RecordingTimeline {
  #host;
  #options;
  /** @type {TimelineModel | null} */
  #model = null;
  get #recording() {
    if (!this.#model) throw new Error("Recording timeline has no model");
    return this.#model;
  }
  #zoom = 1;
  #time = 0;
  /** @type {number | null} */
  #scrubbing = null;
  /** @type {MarkPoint | null} */
  #touched = null;
  /** @type {number | null} */
  #expectedScroll = null;
  #queueRuler;
  #queueOverview;
  #observer;
  #width = 0;
  // The time at the window's left edge. Width changes rescale the track; this
  // time, not the pixel offset, is the reader's place.
  #start = 0;
  /** @type {{input: LabelCluster[], moments: LabelCluster[]}} */
  #labels = { input: [], moments: [] };
  #callRows = 1;
  /** @type {Map<string, number>} */
  #callRowOf = new Map();

  /**
   * `host` receives the timeline. `options`: `onSeek(time, final)`, `onPick(lane,
   * id, time)`, `onUserPan()`, `onZoom()`, and `quoted` (a frozen copy takes no
   * input).
   */
  /** @param {HTMLElement} host @param {TimelineOptions} options */
  constructor(host, options) {
    this.#host = host;
    this.#options = options;
    this.#observer = sizeObserver(() => this.#resized());
    this.#queueRuler = frameFor(host, () => this.#drawRuler());
    // Several geometry steps can run in one task; the overview reads their end.
    this.#queueOverview = frameFor(host, () => this.#drawOverview());
    whileConnected(host, () => {
      this.#observeScroller();
      return () => this.#observer.disconnect();
    });
  }

  /** @param {string} selector @returns {HTMLElement | null} */
  #part(selector) {
    return this.#host.querySelector(selector);
  }
  get scroller() {
    return this.#part(".lf-trace-scroller");
  }
  get #drawnScroller() {
    const scroller = this.scroller;
    if (!scroller) throw new Error("Recording timeline did not draw its scroller");
    return scroller;
  }

  get zoom() {
    return this.#zoom;
  }

  // The scroller arrives with the first drawing, which can follow the connection.
  #observeScroller() {
    if (this.scroller && this.#host.isConnected) this.#observer.observe(this.scroller);
  }

  /** The visible window, in recording time, for restoring a scope's view. */
  get view() {
    const scroller = this.scroller;
    if (!scroller || !this.#model) return null;
    return { zoom: this.#zoom, start: this.#start };
  }

  /** @param {TimelineView | null} view */
  set view(view) {
    this.#zoom = view?.zoom ?? 1;
    this.#applyZoom(view ? this.#timeToPx(view.start) : null);
  }

  /** @param {TimelineModel} model */
  update(model) {
    const changed = model.signature !== this.#model?.signature;
    this.#model = model;
    if (changed) {
      // Rows depend only on the recording, so models rebuilt on every draw
      // share them by call id.
      this.#callRowOf = assignRows(
        model.calls,
        (call) => call.start,
        (call) => call.end,
      );
      this.#callRows = 1 + Math.max(0, ...this.#callRowOf.values());
      this.#zoom = Math.min(this.#zoom, this.#maxZoom());
    }
    // Labels carry each mark's selection state, so they follow every update.
    if (!this.#part(".lf-trace-track")) this.#draw();
    this.#layoutLabels();
    if (changed) this.#observeScroller();
    this.setTime(model.time);
  }

  /** @param {number} time */
  setTime(time) {
    this.#time = time;
    const playhead = this.#part(".lf-trace-playhead");
    if (!playhead || !this.#model) return;
    playhead.style.setProperty("--lf-axis-at", String(this.#fraction(time)));
    this.#part(".lf-trace-overview")?.style.setProperty(
      "--lf-trace-time",
      String(this.#fraction(time)),
    );
  }

  /** Bring `time` into view: `center` for navigation, `page` for playback. */
  /** @param {number} time @param {string} [mode] */
  reveal(time, mode = "center") {
    const scroller = this.scroller;
    if (!scroller || this.#zoom === 1) return;
    const x = this.#timeToPx(time);
    const left = scroller.scrollLeft;
    const width = scroller.clientWidth;
    if (mode === "page") {
      if (x < left || x > left + width * 0.9) this.#scrollTo(x - width * 0.1);
    } else if (x < left + EDGE || x > left + width - EDGE)
      this.#scrollTo(x - width / 2);
  }

  /** @param {number} factor @param {number | null} [anchor] @param {[number, number] | null} [fit] */
  zoomBy(factor, anchor = null, fit = null) {
    const scroller = this.scroller;
    if (!scroller) return;
    if (fit) {
      // Fit a time range into the middle three fifths of the window.
      const [from, to] = fit;
      const range = Math.max(10, to - from);
      this.#zoom = Math.max(
        1,
        Math.min(this.#maxZoom(), (this.#recording.duration * 0.6) / range),
      );
      this.#applyZoom(this.#timeToPx((from + to) / 2) - scroller.clientWidth / 2);
      return;
    }
    const time =
      anchor ??
      (this.#visible(this.#time)
        ? this.#time
        : this.#pxToTime(scroller.scrollLeft + scroller.clientWidth / 2));
    const offset = this.#timeToPx(time) - scroller.scrollLeft;
    this.#zoom = Math.max(1, Math.min(this.#maxZoom(), this.#zoom * factor));
    this.#applyZoom(this.#timeToPx(time) - offset);
  }

  fit() {
    this.#zoom = 1;
    this.#applyZoom(0);
  }

  get canZoomIn() {
    return this.#zoom < this.#maxZoom();
  }

  get canZoomOut() {
    return this.#zoom > 1;
  }

  // Geometry -------------------------------------------------------------------

  #maxZoom() {
    // The narrowest window spans 10 ms of recording, within the widest box
    // Chrome lays out (33.5M px). The width is the one the size observer last
    // reported (`#resized`), so asking whether the timeline can zoom in, as its
    // command's liveness does, forces no layout. A timeline not yet laid out with a
    // width, such as one in a closed disclosure, is bounded by its recording alone
    // until the observer's first report clamps the zoom to its box.
    const width = Math.max(1, this.#width);
    return Math.max(1, Math.min((this.#model?.duration ?? 0) / 10, 16e6 / width));
  }
  #trackWidth() {
    return (this.scroller?.clientWidth ?? 0) * this.#zoom;
  }
  #span() {
    return Math.max(1, this.#trackWidth() - 2 * EDGE);
  }
  /** @param {number} time */
  #fraction(time) {
    return Math.max(0, Math.min(1, time / Math.max(1, this.#recording.duration)));
  }
  /** @param {number} time */
  #timeToPx(time) {
    return EDGE + this.#fraction(time) * this.#span();
  }
  /** @param {number} px */
  #pxToTime(px) {
    return Math.max(
      0,
      Math.min(
        this.#recording.duration,
        ((px - EDGE) / this.#span()) * this.#recording.duration,
      ),
    );
  }
  #pxPerMs() {
    return this.#span() / Math.max(1, this.#recording.duration);
  }
  /** @param {number} time */
  #visible(time) {
    const scroller = this.#drawnScroller;
    const x = this.#timeToPx(time) - scroller.scrollLeft;
    return x >= 0 && x <= scroller.clientWidth;
  }
  /** @param {number} left */
  #scrollTo(left) {
    const scroller = this.#drawnScroller;
    const max = scroller.scrollWidth - scroller.clientWidth;
    const target = Math.round(Math.max(0, Math.min(max, left)));
    this.#start = this.#pxToTime(target);
    if (target === Math.round(scroller.scrollLeft)) return;
    this.#expectedScroll = target;
    setScroll(scroller, { left: target });
  }
  // A new zoom or width moves the window, so the scroll goes to `left`, a pixel offset
  // on the new track, before anything is drawn: the marks, the ruler and its grid are
  // then drawn once (`#draw`), for the window they show. Drawn before the scroll as
  // well, the ruler and grid were first drawn for a window the scroll then left, and
  // drawn again in the same task, where a window that returned to the one before put
  // back lines equal to those the first drawing took out.
  /** @param {number | null} [left] */
  #applyZoom(left = null) {
    const track = this.#part(".lf-trace-track");
    if (!track) return;
    track.style.setProperty("--lf-trace-zoom", String(this.#zoom));
    if (left !== null) this.#scrollTo(left);
    this.#layoutLabels();
  }
  #resized() {
    const width = this.scroller?.clientWidth ?? 0;
    if (!width || width === this.#width || !this.#model) return;
    // A width change rescales the track. Keep the window's left time in place.
    const resized = this.#width !== 0;
    this.#width = width;
    if (this.#zoom > this.#maxZoom()) {
      this.#zoom = this.#maxZoom();
      this.#options.onZoom?.();
    }
    this.#applyZoom(resized ? this.#timeToPx(this.#start) : null);
  }

  // Labels -----------------------------------------------------------------------

  // Labels are laid out in pixels, so they follow zoom and width. Every lane but
  // the calls' keeps one row, so a label never changes a lane's height.
  #layoutLabels() {
    if (!this.#model) return;
    const track = this.#part(".lf-trace-track");
    if (!track || !this.scroller?.clientWidth) return this.#draw();
    // Labels are set in the track's family at the labels' weight; their box adds
    // padding, a border and the 2px staff.
    const style = getComputedStyle(track);
    const font = `600 ${style.fontSize} ${style.fontFamily}`;
    const pxPerMs = this.#pxPerMs();
    // Marks too close to label separately share one label, which starts at the
    // first and lists them in time order; each keeps its own mark.
    const end = this.#span();
    // A crowded label lists its first mark and a count of the rest.
    /** @param {LabelCluster} current @param {boolean} [compact] */
    const fit = (current, compact = false) => {
      const full = current.items.map((item) => item.label).join(" ");
      current.compact =
        current.items.length > 1 && (compact || measure(full, font) > CLUSTER_WIDTH);
      current.text = current.compact
        ? `${current.items[0].label} +${current.items.length - 1}`
        : full;
      current.width = measure(current.text, font) + LABEL_CHROME;
      current.flip = current.x + current.width > end;
      current.spread = current.to > current.from;
    };
    /** @param {LabelItem[]} items */
    const cluster = (items) => {
      /** @type {LabelCluster[]} */
      const clusters = [];
      for (const item of items) {
        const x = item.at * pxPerMs;
        let current = clusters.at(-1);
        if (current && x < current.x + current.width + LABEL_GAP) {
          current.items.push(item);
          current.to = item.at;
        } else
          clusters.push(
            (current = {
              x,
              items: [item],
              from: item.at,
              to: item.at,
              compact: false,
              text: "",
              width: 0,
              flip: false,
              spread: false,
            }),
          );
        fit(current);
      }
      // A label that would run past the end of the time scale points back:
      // its staff still stands on its time, at the label's right edge. One that
      // would then meet its neighbour joins that neighbour's label instead.
      // A label near the end first shortens to its first mark and a count.
      clusters.forEach((current) => fit(current));
      for (const current of [...clusters].reverse()) {
        const index = clusters.indexOf(current);
        if (current.flip && current.items.length > 1) {
          const full = current.width;
          fit(current, true);
          if (current.width >= full) fit(current);
        }
        const previous = clusters[index - 1];
        if (!current.flip || !previous) continue;
        const previousEnd = previous.flip ? previous.x : previous.x + previous.width;
        if (current.x - current.width >= previousEnd + LABEL_GAP) continue;
        previous.items.push(...current.items);
        previous.to = current.to;
        clusters.splice(index, 1);
        fit(previous);
      }
      return clusters;
    };
    this.#labels.input = cluster(
      this.#model.inputs.map((input) => ({ ...input, at: input.start })),
    );
    this.#labels.moments = cluster(
      this.#model.moments
        .map((moment) => ({ ...moment, at: moment.time, label: String(moment.number) }))
        .toSorted((a, b) => a.at - b.at),
    );
    this.#draw();
  }
  // A label may run until the next label in its lane begins.
  /** @param {LabelCluster[]} clusters @param {number} index @param {LabelCluster} cluster */
  #labelRoom(clusters, index, cluster) {
    if (cluster.flip) {
      const previous = clusters[index - 1];
      if (!previous) return "none";
      const previousEnd = previous.flip ? previous.x : previous.x + previous.width;
      return layoutPx(Math.max(12, cluster.x - previousEnd - LABEL_GAP));
    }
    const next = clusters[index + 1];
    if (!next) return "none";
    const nextStart = next.flip ? next.x - next.width : next.x;
    return layoutPx(Math.max(12, nextStart - cluster.x - LABEL_GAP));
  }
  // Each name in a label is its own mark's target; a count zooms to its marks.
  /** @param {LabelCluster} cluster @param {string} lane */
  #labelWords(cluster, lane) {
    const word = (/** @type {LabelItem} */ item) =>
      html`<span
        class="lf-trace-word"
        data-lf-word=${item.id}
        .lfPreview=${said(item.tip)}
        ?data-lf-current=${item.current}
        >${item.label}</span
      >`;
    const kind = lane === "moments" ? "moments" : "inputs";
    if (cluster.compact)
      return html`${word(cluster.items[0])}
        <span
          class="lf-trace-more"
          data-lf-more
          ?data-lf-current=${cluster.items.slice(1).some((item) => item.current)}
          .lfPreview=${() => ({
            name: `${cluster.items.length - 1} more ${kind}`,
            detail: [
              cluster.spread
                ? "Zoom to separate them"
                : `At this time; ${kind === "moments" ? "the Moments list" : "Shift with Left and Right"} reaches each`,
            ],
          })}
          >+${cluster.items.length - 1}</span
        >`;
    return cluster.items.map((item, index) => html`${index ? " " : ""}${word(item)}`);
  }

  // Drawing ------------------------------------------------------------------------

  #draw() {
    const model = this.#model;
    if (!model) return;
    const fraction = (/** @type {number} */ time) => String(this.#fraction(time));
    const length = (/** @type {number} */ start, /** @type {number | null} */ end) =>
      String(Math.max(0, this.#fraction(end ?? start) - this.#fraction(start)));
    const quoted = this.#options.quoted;
    const lanes = [
      ...(model.moments.length
        ? [["moments", "Moments", "Authored results, at their capture times"]]
        : []),
      ...(model.inputs.length
        ? [
            [
              "input",
              "Input",
              "Each bar is the recorded input call; its notch is the Action checkpoint, taken just before the input is sent. Key-down and hold times are not recorded.",
            ],
          ]
        : []),
      ...(model.calls.length
        ? [["calls", "Calls", "Other recorded calls, start to end"]]
        : []),
      [
        "captures",
        "Captures",
        "Dark ticks have an image; light ticks are checkpoints without one",
      ],
    ];
    render(
      html`<div class="lf-trace-lane-names" aria-hidden="true">
          <span class="lf-trace-lane-name lf-trace-lane-name-ruler"></span>
          ${lanes.map(
            ([lane, name, about]) =>
              html`<span
                class="lf-trace-lane-name lf-trace-lane-name-${lane}"
                title=${about}
                style="--lf-trace-rows: ${lane === "calls" ? this.#callRows : 1}"
                >${name}</span
              >`,
          )}
        </div>
        <div
          class="lf-trace-scroller"
          data-lf-scroll
          @scroll=${() => this.#scrolled()}
          @wheel=${(/** @type {WheelEvent} */ event) => this.#wheel(event)}
        >
          ${keyed(
            // A different recording, scope or time scale is a new drawing: its
            // marks are replaced rather than carried to new positions.
            model.signature,
            html`<div
              class="lf-trace-track"
              @touchstart=${{
                handleEvent: (/** @type {TouchEvent} */ event) => this.#landed(event),
                passive: true,
              }}
              @pointerdown=${(/** @type {PointerEvent} */ event) => this.#press(event)}
              @click=${(/** @type {PointerEvent} */ event) => this.#tap(event)}
            >
              <div class="lf-trace-ruler lf-axis-ruler"></div>
              <div class="lf-trace-grid lf-axis-grid" aria-hidden="true"></div>
              ${
                model.moments.length
                  ? html`<div class="lf-trace-lane lf-trace-lane-moments">
                      ${this.#labels.moments.map(
                        (cluster, index) =>
                          html`<span
                            class="lf-trace-moment-pin lf-on-axis"
                            ?data-lf-flip=${cluster.flip}
                            data-lf-pick="moments"
                            data-lf-id=${cluster.items[0].id}
                            data-lf-cluster=${index}
                            .lfPreview=${saidOfAll(cluster.items, "moments")}
                            ?data-lf-current=${cluster.items.some((item) => item.current)}
                            style="--lf-axis-at: ${fraction(cluster.items[0].at)}; max-inline-size: ${this.#labelRoom(
                              this.#labels.moments,
                              index,
                              cluster,
                            )}"
                            ><span class="lf-trace-moment-flag"
                              >${this.#labelWords(cluster, "moments")}</span
                            ></span
                          >`,
                      )}
                    </div>`
                  : nothing
              }
              ${
                model.inputs.length
                  ? html`<div class="lf-trace-lane lf-trace-lane-input">
                      ${this.#labels.input.map(
                        (cluster, index) =>
                          html`<span
                            class="lf-trace-input-label lf-on-axis"
                            ?data-lf-flip=${cluster.flip}
                            data-lf-pick="input"
                            data-lf-id=${cluster.items[0].id}
                            data-lf-cluster=${index}
                            .lfPreview=${saidOfAll(cluster.items, "inputs")}
                            style="--lf-axis-at: ${fraction(cluster.items[0].at)}; max-inline-size: ${this.#labelRoom(
                              this.#labels.input,
                              index,
                              cluster,
                            )}"
                            >${this.#labelWords(cluster, "input")}</span
                          >`,
                      )}
                      ${repeat(
                        model.inputs.filter((input) => input.send !== null),
                        (input) => input.id,
                        (input) =>
                          html`<span
                            class="lf-trace-input-send lf-on-axis"
                            data-lf-pick="input"
                            data-lf-id=${input.id}
                            .lfPreview=${said(input.tip)}
                            ?data-lf-current=${input.current}
                            style="--lf-axis-at: ${fraction(input.send)}"
                          ></span>`,
                      )}
                      ${repeat(
                        model.inputs,
                        (input) => input.id,
                        (input) =>
                          html`<span
                            class="lf-trace-bar lf-trace-input-bar lf-on-axis"
                            data-lf-pick="input"
                            data-lf-id=${input.id}
                            .lfPreview=${said(input.tip)}
                            ?data-lf-current=${input.current}
                            ?data-lf-active=${input.active}
                            style="--lf-axis-at: ${fraction(input.start)}; --d: ${length(
                              input.start,
                              input.end,
                            )}"
                          ></span>`,
                      )}
                    </div>`
                  : nothing
              }
              ${
                model.calls.length
                  ? html`<div
                      class="lf-trace-lane lf-trace-lane-calls"
                      style="--lf-trace-rows: ${this.#callRows}"
                    >
                      ${repeat(
                        model.calls,
                        (call) => call.id,
                        (call) =>
                          html`<span
                            class="lf-trace-bar lf-trace-call-bar lf-on-axis"
                            data-lf-pick="calls"
                            data-lf-id=${call.id}
                            .lfPreview=${said(call.tip)}
                            ?data-lf-current=${call.current}
                            ?data-lf-active=${call.active}
                            ?data-lf-error=${call.error}
                            style="--lf-axis-at: ${fraction(call.start)}; --d: ${length(
                              call.start,
                              call.end,
                            )}; --row: ${this.#callRowOf.get(call.id) ?? 0}"
                            ><span class="lf-trace-call-name">${call.label}</span></span
                          >`,
                      )}
                    </div>`
                  : nothing
              }
              <div class="lf-trace-lane lf-trace-lane-captures">
                ${repeat(
                  model.captures,
                  (capture) => capture.id,
                  (capture) =>
                    html`<span
                      class="lf-trace-capture lf-on-axis"
                      ?data-lf-image=${capture.image}
                      ?data-lf-current=${capture.current}
                      style="--lf-axis-at: ${fraction(capture.time)}"
                    ></span>`,
                )}
              </div>
              <div class="lf-trace-playhead lf-on-axis" aria-hidden="true">
                <span
                  class="lf-trace-playhead-handle"
                  title=${quoted ? "Selected recorded time" : "Drag to scrub the recording"}
                ></span>
              </div>
            </div>`,
          )}
        </div>
        <div
          class="lf-trace-overview"
          title="Whole recording; drag to move the zoomed window"
          @pointerdown=${(/** @type {PointerEvent} */ event) => this.#overviewPress(event)}
        >
          <span class="lf-trace-overview-window"></span>
          <span class="lf-trace-overview-time"></span>
        </div>`,
      this.#host,
    );
    const track = this.#part(".lf-trace-track");
    track?.style.setProperty("--lf-trace-zoom", String(this.#zoom));
    track?.style.setProperty("--lf-axis-edge", `${EDGE}px`);
    this.#part(".lf-trace-playhead")?.style.setProperty(
      "--lf-axis-at",
      String(this.#fraction(this.#time)),
    );
    this.#drawRuler();
  }

  // The overview shows the visible window within the whole recording. Its geometry is
  // read whole before either edge is written: reading the scroller between the two
  // writes laid out a window with the new start and the old size, which ran past the
  // overview's end and scrolled the page under the user's press.
  #drawOverview() {
    const scroller = this.scroller;
    const overview = this.#part(".lf-trace-overview");
    if (!scroller?.scrollWidth || !overview) return;
    const { scrollLeft, scrollWidth, clientWidth } = scroller;
    overview.style.setProperty(
      "--lf-trace-window-start",
      String(scrollLeft / scrollWidth),
    );
    overview.style.setProperty(
      "--lf-trace-window-size",
      String(clientWidth / scrollWidth),
    );
    keeps(overview, "data-lf-zoomed", this.#zoom > 1 ? "" : null);
  }

  /** @param {PointerEvent} event */
  #overviewPress(event) {
    if (event.button !== 0 || this.#zoom === 1) return;
    event.preventDefault();
    const overview = event.currentTarget;
    if (!(overview instanceof HTMLElement)) return;
    overview.setPointerCapture(event.pointerId);
    const pan = (/** @type {PointerEvent} */ moved) => {
      const box = overview.getBoundingClientRect();
      const scroller = this.#drawnScroller;
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

  // The ruler draws only ticks near the visible window, so deep zoom stays cheap; the
  // grid below it, a line at each of their major times.
  #drawRuler() {
    this.#queueOverview();
    const ruler = this.#part(".lf-trace-ruler");
    const grid = this.#part(".lf-trace-grid");
    const scroller = this.scroller;
    if (!ruler || !grid || !scroller?.clientWidth || !this.#model) return;
    const ticks = axisTicks(
      this.#pxToTime(scroller.scrollLeft - TICK_SPACING),
      this.#pxToTime(scroller.scrollLeft + scroller.clientWidth + TICK_SPACING),
      this.#recording.duration,
      this.#pxPerMs(),
    );
    render(
      repeat(
        ticks,
        (tick) => `${tick.step}:${tick.time}`,
        (tick) =>
          html`<span
            class="lf-axis-tick"
            ?data-lf-major=${tick.major}
            ?data-lf-flip=${tick.flip}
            style="--lf-axis-at: ${this.#fraction(tick.time)}"
            >${tick.label ?? nothing}</span
          >`,
      ),
      ruler,
    );
    render(
      repeat(
        ticks.filter((tick) => tick.major),
        (tick) => `${tick.step}:${tick.time}`,
        (tick) =>
          html`<span
            class="lf-axis-gridline"
            ?data-lf-flip=${tick.flip}
            style="--lf-axis-at: ${this.#fraction(tick.time)}"
          ></span>`,
      ),
      grid,
    );
  }

  // Gestures -------------------------------------------------------------------------

  #scrolled() {
    const scroller = this.#drawnScroller;
    // A clamp from a width change waits for the resize to restore the place.
    if (scroller.clientWidth !== this.#width) return;
    if (this.#expectedScroll !== null) {
      const expected = this.#expectedScroll;
      if (Math.abs(scroller.scrollLeft - expected) < 1.5) {
        this.#expectedScroll = null;
        this.#queueRuler();
        return;
      }
    }
    this.#start = this.#pxToTime(scroller.scrollLeft);
    this.#options.onUserPan?.();
    this.#queueRuler();
  }

  /** @param {WheelEvent} event */
  #wheel(event) {
    // Pinch arrives as Ctrl+wheel; Cmd+wheel is the macOS mouse equivalent.
    if (!(event.ctrlKey || event.metaKey) || this.#options.quoted) return;
    event.preventDefault();
    const scroller = this.#drawnScroller;
    const x =
      event.clientX - scroller.getBoundingClientRect().left + scroller.scrollLeft;
    this.zoomBy(Math.exp(-event.deltaY / 200), this.#pxToTime(x));
    this.#options.onUserPan?.();
    this.#options.onZoom?.();
  }

  // Zoom until neighbouring marks stand at least a label apart, then center them.
  /** @param {LabelCluster} cluster */
  #separate(cluster) {
    const { items, from, to } = cluster;
    const scroller = this.#drawnScroller;
    let previous = from;
    const gaps = items.slice(1).map((item) => {
      const gap = item.at - previous;
      previous = item.at;
      return gap;
    });
    const gap = Math.max(1, Math.min(...gaps.filter((value) => value > 0)));
    const perMs = this.#span() / this.#zoom / Math.max(1, this.#recording.duration);
    // Enough to set them a label apart, but never so far that the cluster no
    // longer fits the window; a second press zooms further.
    const range = Math.max(1, to - from);
    const whole = (0.8 * scroller.clientWidth) / (range * perMs);
    const apart = 48 / (gap * perMs);
    this.#zoom = Math.max(
      this.#zoom,
      Math.min(
        this.#maxZoom(),
        whole > this.#zoom * 1.05 ? Math.min(apart, whole) : apart,
      ),
    );
    const middle = (from + to) / 2;
    this.#applyZoom(this.#timeToPx(middle) - scroller.clientWidth / 2);
  }

  // Chrome adjusts a tap's target, and its pointer and click events, toward a
  // nearby larger target such as the label above a thin bar. The touch point is
  // where the finger landed, so the tap acts on the element under it.
  /** @param {TouchEvent} event */
  #landed(event) {
    const touch = event.touches[0];
    if (!touch || event.touches.length > 1) return (this.#touched = null);
    const target = document.elementFromPoint(touch.clientX, touch.clientY);
    this.#touched =
      target && this.#host.contains(target) ? { target, clientX: touch.clientX } : null;
  }

  /** @param {{clientX: number}} event */
  #eventTime(event) {
    const scroller = this.#drawnScroller;
    return this.#pxToTime(
      event.clientX - scroller.getBoundingClientRect().left + scroller.scrollLeft,
    );
  }

  /** @param {PointerEvent} event */
  #press(event) {
    if (this.#options.quoted || event.button !== 0) return;
    const target = event.target;
    if (!(target instanceof Element)) return;
    const handle = target.closest(".lf-trace-playhead-handle");
    // A finger pans the track natively; only the handle scrubs under touch.
    // Chrome adjusts a tap's click toward a nearby larger target, so the tap
    // keeps the element its finger landed on.
    if (event.pointerType === "touch" && !handle) return;
    if (
      !handle &&
      (target.closest("[data-lf-pick]") ||
        this.#nearMark({ target, clientX: event.clientX }))
    )
      return;
    event.preventDefault();
    const track = event.currentTarget;
    if (!(track instanceof HTMLElement)) return;
    track.setPointerCapture(event.pointerId);
    this.#scrubbing = event.pointerId;
    this.#options.onSeek(this.#eventTime(event), false);
    const move = (/** @type {PointerEvent} */ moved) => {
      if (moved.pointerId === this.#scrubbing)
        this.#options.onSeek(this.#eventTime(moved), false);
    };
    const end = (/** @type {PointerEvent} */ ended) => {
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

  /** @param {PointerEvent} event */
  #tap(event) {
    if (this.#options.quoted) return;
    const touched = event.pointerType === "touch" ? this.#touched : null;
    this.#touched = null;
    const target = touched?.target ?? event.target;
    if (!(target instanceof Element)) return;
    const at = touched ?? { target, clientX: event.clientX };
    const time = this.#eventTime(at);
    const pick = target.closest("[data-lf-pick]") ?? this.#nearMark(at);
    if (pick) {
      const lane = pick.getAttribute("data-lf-pick");
      if (lane !== "input" && lane !== "moments" && lane !== "calls") return;
      const labels = lane === "calls" ? null : this.#labels[lane];
      const index = pick.getAttribute("data-lf-cluster");
      const cluster = index === null ? null : labels?.[Number(index)];
      if (cluster && target.closest("[data-lf-more]") && cluster.spread) {
        this.#separate(cluster);
        this.#options.onUserPan?.();
        this.#options.onZoom?.();
        return;
      }
      const id =
        target.closest("[data-lf-word]")?.getAttribute("data-lf-word") ??
        pick.getAttribute("data-lf-id");
      if (id !== null) this.#options.onPick(lane, id, time);
      return;
    }
    // A mouse press already scrubbed; a tap seeks once.
    if (event.pointerType === "touch" || pressIsKeyboardActivation(event))
      this.#options.onSeek(this.#eventTime(event), true);
  }

  // A press beside a thin mark in its lane still takes that mark.
  /** @param {MarkPoint} event */
  #nearMark(event) {
    const lane = event.target.closest(".lf-trace-lane-input, .lf-trace-lane-calls");
    if (!lane) return null;
    let best = null;
    let distance = 8;
    for (const mark of lane.querySelectorAll(".lf-trace-bar")) {
      const box = mark.getBoundingClientRect();
      const away = Math.max(box.left - event.clientX, event.clientX - box.right, 0);
      if (away < distance) [best, distance] = [mark, away];
    }
    return best;
  }
}
