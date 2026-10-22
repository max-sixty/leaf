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
  createView,
  For,
  Show,
  frameFor,
  sizeObserver,
  whileConnected,
  layoutPx,
  keeps,
  keepsHidden,
  keepsText,
  pressIsKeyboardActivation,
} from "/runtime/widget-api.js";

const LABEL_GAP = 6;
const LABEL_CHROME = 12;
const TICK_SPACING = 84;
const STEPS = [1, 2, 5];
const EDGE = 12;
const CLUSTER_WIDTH = 168;

// Ruler steps: 1, 2, 5 × 10^k milliseconds, the smallest at least TICK_SPACING apart.
function tickStep(pxPerMs) {
  for (let power = 1; power < 1e9; power *= 10)
    for (const step of STEPS)
      if (step * power * pxPerMs >= TICK_SPACING) return step * power;
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
  const rowOf = new Map();
  for (const item of items.toSorted((a, b) => start(a) - start(b))) {
    let row = rows.findIndex((last) => last <= start(item));
    if (row < 0) row = rows.push(-Infinity) - 1;
    rows[row] = end(item);
    rowOf.set(item.id, row);
  }
  return rowOf;
}

// Style writes the page did not change are still mutations; skip them.
function keepVar(node, name, value) {
  if (node && node.style.getPropertyValue(name) !== value)
    node.style.setProperty(name, value);
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
  #touched = null;
  #expectedScroll = null;
  #queueRuler;
  #queueOverview;
  #observer;
  #width = 0;
  // The time at the window's left edge. Width changes rescale the track; this
  // time, not the pixel offset, is the reader's place.
  #start = 0;
  #labels = { input: [], moments: [] };
  #callRows = 1;
  #callRowOf = new Map();
  #tipAnchor = null;
  #drawing = null;
  #rulerDrawing = null;
  #rulerNode = null;

  /**
   * `host` receives the timeline. `options`: `onSeek(time, final)`, `onPick(lane,
   * id, time)`, `onUserPan()`, `onZoom()`, and `quoted` (a frozen copy takes no
   * input).
   */
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

  get scroller() {
    return this.#host.querySelector(".lf-trace-scroller");
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

  set view(view) {
    this.#zoom = view?.zoom ?? 1;
    this.#applyZoom();
    if (view) this.#scrollTo(this.#timeToPx(view.start));
  }

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
    if (!this.#host.querySelector(".lf-trace-track")) this.#draw();
    this.#layoutLabels();
    if (changed) this.#observeScroller();
    this.setTime(model.time);
  }

  setTime(time) {
    this.#time = time;
    const track = this.#host.querySelector(".lf-trace-track");
    if (!track || !this.#model) return;
    keepVar(track, "--lf-trace-time", String(this.#fraction(time)));
    keepVar(
      this.#host.querySelector(".lf-trace-overview"),
      "--lf-trace-time",
      String(this.#fraction(time)),
    );
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
    } else if (x < left + EDGE || x > left + width - EDGE)
      this.#scrollTo(x - width / 2);
  }

  zoomBy(factor, anchor = null, fit = null) {
    const scroller = this.scroller;
    if (!scroller) return;
    if (fit) {
      // Fit a time range into the middle three fifths of the window.
      const [from, to] = fit;
      const range = Math.max(10, to - from);
      this.#zoom = Math.max(
        1,
        Math.min(this.#maxZoom(), (this.#model.duration * 0.6) / range),
      );
      this.#applyZoom();
      this.#scrollTo(this.#timeToPx((from + to) / 2) - scroller.clientWidth / 2);
      return;
    }
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
  #fraction(time) {
    return Math.max(0, Math.min(1, time / Math.max(1, this.#model.duration)));
  }
  #timeToPx(time) {
    return EDGE + this.#fraction(time) * this.#span();
  }
  #pxToTime(px) {
    return Math.max(
      0,
      Math.min(
        this.#model.duration,
        ((px - EDGE) / this.#span()) * this.#model.duration,
      ),
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
    this.#start = this.#pxToTime(target);
    if (target === Math.round(scroller.scrollLeft)) return;
    this.#expectedScroll = target;
    scroller.scrollLeft = target;
  }
  #applyZoom() {
    const track = this.#host.querySelector(".lf-trace-track");
    if (!track) return;
    keepVar(track, "--lf-trace-zoom", String(this.#zoom));
    this.#layoutLabels();
    this.#drawRuler();
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
    this.#applyZoom();
    if (resized) this.#scrollTo(this.#timeToPx(this.#start));
    this.#drawRuler();
  }

  // Labels -----------------------------------------------------------------------

  // Labels are laid out in pixels, so they follow zoom and width. Every lane but
  // the calls' keeps one row, so a label never changes a lane's height.
  #layoutLabels() {
    if (!this.#model) return;
    const track = this.#host.querySelector(".lf-trace-track");
    if (!track || !this.scroller.clientWidth) return this.#draw();
    // Labels are set in the track's family at the labels' weight; their box adds
    // padding, a border and the 2px staff.
    const style = getComputedStyle(track);
    const font = `600 ${style.fontSize} ${style.fontFamily}`;
    const pxPerMs = this.#pxPerMs();
    // Marks too close to label separately share one label, which starts at the
    // first and lists them in time order; each keeps its own mark.
    const end = this.#span();
    // A crowded label lists its first mark and a count of the rest.
    const fit = (current, compact = false) => {
      const full = current.items.map((item) => item.label).join(" ");
      current.compact =
        current.items.length > 1 && (compact || measure(full, font) > CLUSTER_WIDTH);
      current.text = current.compact
        ? `${current.items[0].label} +${current.items.length - 1}`
        : full;
      current.width = measure(current.text, font) + LABEL_CHROME;
      current.flip = current.x + current.width > end;
      current.spread = current.items.at(-1).at > current.items[0].at;
    };
    const cluster = (items) => {
      const clusters = [];
      for (const item of items) {
        const x = item.at * pxPerMs;
        let current = clusters.at(-1);
        if (current && x < current.x + current.width + LABEL_GAP)
          current.items.push(item);
        else clusters.push((current = { x, items: [item] }));
        fit(current);
      }
      // A label that would run past the end of the time scale points back:
      // its staff still stands on its time, at the label's right edge. One that
      // would then meet its neighbour joins that neighbour's label instead.
      // A label near the end first shortens to its first mark and a count.
      clusters.forEach((current) => fit(current));
      for (let index = clusters.length - 1; index >= 0; index--) {
        const current = clusters[index];
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
  #labelRoom(clusters, index) {
    const cluster = clusters[index];
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
  #labelWords(cluster, lane) {
    const kind = lane === "moments" ? "moments" : "inputs";
    return html`${For({
      get each() {
        return cluster().compact ? cluster().items.slice(0, 1) : cluster().items;
      },
      keyed: (item) => item.id,
      children: (item, index) =>
        html`${() => (index() ? " " : "")}<span
            class="lf-trace-word"
            data-word=${() => item().id}
            data-tip=${() => item().title}
            data-current=${() => (item().current ? "" : undefined)}
            >${() => item().label}</span
          >`,
    })}${Show({
      get when() {
        return cluster().compact;
      },
      children: (_visible) =>
        html` <span
          class="lf-trace-more"
          data-more
          data-current=${() =>
            cluster()
              .items.slice(1)
              .some((item) => item.current)
              ? ""
              : undefined}
          data-tip=${() =>
            cluster().spread
              ? `${cluster().items.length - 1} more ${kind}: zoom to separate them`
              : `${cluster().items.length - 1} more ${kind} at this time; ${kind === "moments" ? "the Moments list" : "Shift with Left and Right"} reaches each`}
          >+${() => cluster().items.length - 1}</span
        >`,
    })}`;
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
    const mark = (item) => ({
      ...item,
      t: fraction(item.start ?? item.time),
      d: length(item.start, item.end),
      row: this.#callRowOf.get(item.id) ?? 0,
    });
    const clusters = (lane) =>
      this.#labels[lane].map((cluster, index) => ({
        ...cluster,
        index,
        t: fraction(cluster.items[0].at),
        room: this.#labelRoom(this.#labels[lane], index),
        tip: cluster.items.map((item) => item.title).join("\n"),
        current: cluster.items.some((item) => item.current),
      }));
    const props = {
      signature: model.signature,
      lanes,
      rows: this.#callRows,
      quoted,
      moments: clusters("moments"),
      inputs: clusters("input"),
      sends: model.inputs
        .filter((input) => input.send !== null)
        .map((input) => ({ ...input, t: fraction(input.send) })),
      inputBars: model.inputs.map(mark),
      calls: model.calls.map(mark),
      captures: model.captures.map(mark),
    };
    if (this.#drawing) this.#drawing.update(props);
    else this.#drawing = createView(this.#host, (read) => this.#template(read), props);
    const track = this.#host.querySelector(".lf-trace-track");
    keepVar(track, "--lf-trace-zoom", String(this.#zoom));
    keepVar(track, "--lf-trace-edge", `${EDGE}px`);
    keepVar(track, "--lf-trace-time", String(this.#fraction(this.#time)));
    this.#drawRuler();
  }

  #template(read) {
    const labels = (lane) =>
      For({
        get each() {
          return read()[lane];
        },
        keyed: (cluster) => cluster.items[0].id,
        children: (cluster) =>
          html`<span
            class=${lane === "moments" ? "lf-trace-moment-pin" : "lf-trace-input-label"}
            data-flip=${() => (cluster().flip ? "" : undefined)}
            data-pick=${lane === "moments" ? "moments" : "input"}
            data-id=${() => cluster().items[0].id}
            data-cluster=${() => cluster().index}
            data-tip=${() => cluster().tip}
            data-current=${() => (lane === "moments" && cluster().current ? "" : undefined)}
            style=${() => ({ "--t": cluster().t, "max-inline-size": cluster().room })}
          >
            ${lane === "moments" ? html`<span class="lf-trace-moment-flag">${this.#labelWords(cluster, lane)}</span>` : this.#labelWords(cluster, lane)}
          </span>`,
      });
    const bars = (lane) =>
      For({
        get each() {
          return read()[lane];
        },
        keyed: (item) => item.id,
        children: (item) =>
          html`<span
            class=${lane === "calls" ? "lf-trace-bar lf-trace-call-bar" : "lf-trace-bar lf-trace-input-bar"}
            data-pick=${lane === "calls" ? "calls" : "input"}
            data-id=${() => item().id}
            data-tip=${() => item().title}
            data-current=${() => (item().current ? "" : undefined)}
            data-active=${() => (item().active ? "" : undefined)}
            data-error=${() => (lane === "calls" && item().error ? "" : undefined)}
            style=${() => ({ "--t": item().t, "--d": item().d, "--row": String(item().row) })}
          >
            ${lane === "calls" ? html`<span class="lf-trace-call-name">${() => item().label}</span>` : undefined}
          </span>`,
      });
    return html`<div class="lf-trace-lane-names" aria-hidden="true">
        <span class="lf-trace-lane-name lf-trace-lane-name-ruler"></span>
        ${For({
          get each() {
            return read().lanes;
          },
          keyed: (lane) => lane[0],
          children: (lane) =>
            html` <span
              class=${() => `lf-trace-lane-name lf-trace-lane-name-${lane()[0]}`}
              title=${() => lane()[2]}
              style=${() => ({ "--lf-trace-rows": String(lane()[0] === "calls" ? read().rows : 1) })}
              >${() => lane()[1]}</span
            >`,
        })}
      </div>
      <div
        class="lf-trace-scroller"
        onScroll=${() => this.#scrolled()}
        onWheel=${(event) => this.#wheel(event)}
      >
        ${Show({
          get when() {
            return read().signature;
          },
          keyed: true,
          children: (_signature) =>
            html` <div
              class="lf-trace-track"
              ref=${(node) => node.addEventListener("touchstart", (event) => this.#landed(event), { passive: true })}
              onPointerDown=${(event) => this.#press(event)}
              onClick=${(event) => this.#tap(event)}
              onPointerOver=${(event) => this.#hover(event)}
              onPointerOut=${(event) => this.#hover(event, true)}
            >
              <div class="lf-trace-ruler"></div>
              ${Show({
                get when() {
                  return read().moments.length;
                },
                children: (_visible) =>
                  html` <div class="lf-trace-lane lf-trace-lane-moments">
                    ${labels("moments")}
                  </div>`,
              })}
              ${Show({
                get when() {
                  return read().inputBars.length;
                },
                children: (_visible) =>
                  html` <div class="lf-trace-lane lf-trace-lane-input">
                    ${labels("inputs")}
                    ${For({
                      get each() {
                        return read().sends;
                      },
                      keyed: (item) => item.id,
                      children: (item) =>
                        html` <span
                          class="lf-trace-input-send"
                          data-pick="input"
                          data-id=${() => item().id}
                          data-tip=${() => item().title}
                          data-current=${() => (item().current ? "" : undefined)}
                          style=${() => ({ "--t": String(item().t) })}
                        ></span>`,
                    })}
                    ${bars("inputBars")}
                  </div>`,
              })}
              ${Show({
                get when() {
                  return read().calls.length;
                },
                children: (_visible) =>
                  html` <div
                    class="lf-trace-lane lf-trace-lane-calls"
                    style=${() => ({ "--lf-trace-rows": String(read().rows) })}
                  >
                    ${bars("calls")}
                  </div>`,
              })}
              <div class="lf-trace-lane lf-trace-lane-captures">
                ${For({
                  get each() {
                    return read().captures;
                  },
                  keyed: (capture) => capture.id,
                  children: (capture) =>
                    html` <span
                      class="lf-trace-capture"
                      data-image=${() => (capture().image ? "" : undefined)}
                      data-current=${() => (capture().current ? "" : undefined)}
                      style=${() => ({ "--t": String(capture().t) })}
                    ></span>`,
                })}
              </div>
              <div class="lf-trace-playhead" aria-hidden="true">
                <span
                  class="lf-trace-playhead-handle"
                  title=${() => (read().quoted ? "Selected recorded time" : "Drag to scrub the recording")}
                ></span>
              </div>
            </div>`,
        })}
      </div>
      <div
        class="lf-trace-overview"
        title="Whole recording; drag to move the zoomed window"
        onPointerDown=${(event) => this.#overviewPress(event)}
      >
        <span class="lf-trace-overview-window"></span
        ><span class="lf-trace-overview-time"></span>
      </div>
      ${Show({
        get when() {
          return read().inputBars.length;
        },
        children: (_visible) =>
          html` <p class="lf-trace-legend">
            Input bars span each recorded call; the notch is its Action checkpoint, just
            before the input is sent. Key-down and hold times are not recorded.
          </p>`,
      })}
      <div class="lf-trace-tip" role="tooltip" hidden></div>`;
  }

  // The overview shows the visible window within the whole recording.
  #drawOverview() {
    const scroller = this.scroller;
    const overview = this.#host.querySelector(".lf-trace-overview");
    if (!scroller?.scrollWidth || !overview) return;
    keepVar(
      overview,
      "--lf-trace-window-start",
      String(scroller.scrollLeft / scroller.scrollWidth),
    );
    keepVar(
      overview,
      "--lf-trace-window-size",
      String(scroller.clientWidth / scroller.scrollWidth),
    );
    keeps(overview, "data-zoomed", this.#zoom > 1 ? "" : null);
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
    this.#queueOverview();
    const ruler = this.#host.querySelector(".lf-trace-ruler");
    const scroller = this.scroller;
    if (!ruler || !scroller?.clientWidth || !this.#model) return;
    const pxPerMs = this.#pxPerMs();
    const step = tickStep(pxPerMs);
    const minor = step / (String(step)[0] === "2" ? 4 : 5);
    const from = this.#pxToTime(scroller.scrollLeft - TICK_SPACING);
    const to = this.#pxToTime(
      scroller.scrollLeft + scroller.clientWidth + TICK_SPACING,
    );
    const ticks = [];
    for (let time = Math.floor(from / minor) * minor; time <= to; time += minor) {
      const rounded = Math.round(time * 1000) / 1000;
      if (rounded < 0 || rounded > this.#model.duration) continue;
      const major = Math.abs(rounded / step - Math.round(rounded / step)) < 1e-6;
      ticks.push({ time: rounded, major });
    }
    const props = {
      ticks: ticks.map((tick) => ({
        ...tick,
        key: `${step}:${tick.time}`,
        t: this.#fraction(tick.time),
        flip: tick.major && (this.#model.duration - tick.time) * pxPerMs < 44,
        label: tick.major ? tickLabel(tick.time, step) : "",
      })),
    };
    if (this.#rulerNode !== ruler) {
      this.#rulerDrawing?.dispose();
      this.#rulerNode = ruler;
      this.#rulerDrawing = createView(
        ruler,
        (read) =>
          html`${For({
            get each() {
              return read().ticks;
            },
            keyed: (tick) => tick.key,
            children: (tick) =>
              html`<span
                class=${() => `lf-trace-tick${tick().major ? " lf-trace-tick-major" : ""}`}
                data-flip=${() => (tick().flip ? "" : undefined)}
                style=${() => ({ "--t": String(tick().t) })}
                >${() => tick().label}</span
              >`,
          })}`,
        props,
      );
    } else this.#rulerDrawing.update(props);
  }

  // Gestures -------------------------------------------------------------------------

  #scrolled() {
    const scroller = this.scroller;
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

  #wheel(event) {
    // Pinch arrives as Ctrl+wheel; Cmd+wheel is the macOS mouse equivalent.
    if (!(event.ctrlKey || event.metaKey) || this.#options.quoted) return;
    event.preventDefault();
    const scroller = this.scroller;
    const x =
      event.clientX - scroller.getBoundingClientRect().left + scroller.scrollLeft;
    this.zoomBy(Math.exp(-event.deltaY / 200), this.#pxToTime(x));
    this.#options.onUserPan?.();
    this.#options.onZoom?.();
  }

  // Zoom until neighbouring marks stand at least a label apart, then center them.
  #separate(items) {
    const scroller = this.scroller;
    const gaps = items.slice(1).map((item, index) => item.at - items[index].at);
    const gap = Math.max(1, Math.min(...gaps.filter((value) => value > 0)));
    const perMs = this.#span() / this.#zoom / Math.max(1, this.#model.duration);
    // Enough to set them a label apart, but never so far that the cluster no
    // longer fits the window; a second press zooms further.
    const range = Math.max(1, items.at(-1).at - items[0].at);
    const whole = (0.8 * scroller.clientWidth) / (range * perMs);
    const apart = 48 / (gap * perMs);
    this.#zoom = Math.max(
      this.#zoom,
      Math.min(
        this.#maxZoom(),
        whole > this.#zoom * 1.05 ? Math.min(apart, whole) : apart,
      ),
    );
    this.#applyZoom();
    const middle = (items[0].at + items.at(-1).at) / 2;
    this.#scrollTo(this.#timeToPx(middle) - scroller.clientWidth / 2);
  }

  // Chrome adjusts a tap's target, and its pointer and click events, toward a
  // nearby larger target such as the label above a thin bar. The touch point is
  // where the finger landed, so the tap acts on the element under it.
  #landed(event) {
    const touch = event.touches[0];
    if (!touch || event.touches.length > 1) return (this.#touched = null);
    const target = document.elementFromPoint(touch.clientX, touch.clientY);
    this.#touched =
      target && this.#host.contains(target) ? { target, clientX: touch.clientX } : null;
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
    // Chrome adjusts a tap's click toward a nearby larger target, so the tap
    // keeps the element its finger landed on.
    if (event.pointerType === "touch" && !handle) return;
    if (!handle && (event.target.closest("[data-pick]") || this.#nearMark(event)))
      return;
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
    const touched = event.pointerType === "touch" ? this.#touched : null;
    this.#touched = null;
    const target = touched?.target ?? event.target;
    const at = touched ?? { target, clientX: event.clientX };
    const time = this.#eventTime(at);
    const pick = target.closest("[data-pick]") ?? this.#nearMark(at);
    if (pick) {
      const cluster =
        pick.dataset.cluster === undefined
          ? null
          : this.#labels[pick.dataset.pick][Number(pick.dataset.cluster)];
      if (cluster && target.closest("[data-more]") && cluster.spread) {
        this.#separate(cluster.items);
        this.#options.onUserPan?.();
        this.#options.onZoom?.();
        return;
      }
      // A name in a shared label is its own mark; elsewhere the label is its first.
      const id = target.closest("[data-word]")?.dataset.word ?? pick.dataset.id;
      this.#options.onPick(pick.dataset.pick, id, time);
      return;
    }
    // A mouse press already scrubbed; a tap seeks once.
    if (event.pointerType === "touch" || pressIsKeyboardActivation(event))
      this.#options.onSeek(this.#eventTime(event), true);
  }

  // A press beside a thin mark in its lane still takes that mark.
  #nearMark(event) {
    const lane = event.target.closest?.(".lf-trace-lane-input, .lf-trace-lane-calls");
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

  #hover(event, leaving = false) {
    const pick = event.target.closest?.("[data-tip]");
    if (leaving || !pick || this.#scrubbing !== null) {
      if (!leaving || !pick?.contains(event.relatedTarget)) this.#hideTip();
      return;
    }
    const tip = this.#host.querySelector(".lf-trace-tip");
    // A time keeps its unit on its line.
    keepsText(tip, pick.dataset.tip.replace(/(\d) s\b/g, "$1\u00a0s"));
    if (this.#tipAnchor !== pick) {
      if (this.#tipAnchor) keeps(this.#tipAnchor, "data-lf-trace-tip-anchor", null);
      this.#tipAnchor = pick;
      keeps(pick, "data-lf-trace-tip-anchor", "");
    }
    keepsHidden(tip, false);
  }
  #hideTip() {
    if (this.#tipAnchor) keeps(this.#tipAnchor, "data-lf-trace-tip-anchor", null);
    this.#tipAnchor = null;
    const tip = this.#host.querySelector(".lf-trace-tip");
    if (tip) keepsHidden(tip, true);
  }
}
