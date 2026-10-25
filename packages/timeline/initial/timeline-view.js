/* lf-timeline's drawing: transport, chart and step list. The initial renderer
 * (`lf-timeline.js` beside this file) bundles this module and draws before first
 * paint, so the widget first shows whole; the widget module
 * (`../widgets/lf-timeline.js`) adopts the returned drawing and only adds behavior
 * to it, and a widget arriving later is drawn by the same bundle. Nothing loads this
 * file at run time, so its imports resolve at build time: Lit binds to the
 * initialized instance, and the axis geometry is the kernel's `time-axis.js`, the
 * one the Playwright timeline also draws with.
 *
 * The model is the event: each instant and each span's start is one step, events
 * that start together share it, and a span's end is not a step. The playhead stands
 * at the current step's time. Everything is drawn at every step, so the layout never
 * depends on the step: events before the playhead are drawn as done, a span the
 * playhead is inside is done up to it, and later events are drawn faint. Stepping
 * therefore repaints states and moves the playhead, and moves nothing else.
 *
 * Labels sit in label rows above their lane's bar row, never on a bar. Within a lane
 * they take greedy rows by their measured extent, so no two overlap, and a label that
 * would run past the axis end reads back from its mark instead. Labels stand in
 * front of the playhead on the chart's ground, so at any step the line passes behind
 * words, never through them, and stays whole across the ruler and every bar row. Labels depend on the track's width, so a resize lays
 * them out again; the lane count and the label rows that width allows set the height.
 */
import { html, nothing, render, repeat } from "/vendor/lit.js";
import {
  assignRows,
  axisTicks,
  textWidth,
} from "../../../browser/runtime/time-axis.js";

const EDGE = 12;
const LABEL_GAP = 8;
// A label's padding and the 2px staff on its anchored edge.
const LABEL_CHROME = 12;

const time = (value) => (value === null || value === "" ? null : Number(value));

/** Seconds, with only the decimals the value needs. */
export const clock = (ms) => `${Number((ms / 1000).toFixed(3))} s`;

/** The authored lanes and events, and the steps they make. */
export function readTimeline(host) {
  const problems = [];
  const lanes = [...host.querySelectorAll(":scope > lf-lane")].map((lane, index) => ({
    index,
    label: lane.getAttribute("label") ?? "",
    events: [...lane.querySelectorAll(":scope > lf-event")].map((event) => {
      const at = time(event.getAttribute("at")) ?? 0;
      let end = time(event.getAttribute("end"));
      if (end !== null && end < at) {
        problems.push(`lf-event #${event.id} ends (${end}) before it starts (${at})`);
        end = null;
      }
      return {
        id: event.id,
        label: event.getAttribute("label") ?? "",
        lane: index,
        at,
        end: end === at ? null : end,
      };
    }),
  }));
  const events = lanes.flatMap((lane) => lane.events);
  const steps = [];
  for (const event of events.toSorted((a, b) => a.at - b.at || a.lane - b.lane)) {
    if (steps.at(-1)?.time === event.at) steps.at(-1).events.push(event);
    else steps.push({ time: event.at, events: [event] });
  }
  steps.forEach((step, index) => {
    for (const event of step.events) event.step = index;
  });
  const duration = Math.max(1, ...events.map((event) => event.end ?? event.at));
  return { lanes, events, steps, duration, problems };
}

// Each event's state at a step, and how much of a span is done.
function stateAt(event, now) {
  if (event.at > now) return { state: "future", done: 0 };
  if (event.at === now) return { state: "current", done: 0 };
  const done =
    event.end === null ? 1 : Math.min(1, (now - event.at) / (event.end - event.at));
  return { state: done < 1 ? "running" : "past", done };
}

/** Lay out labels for a track `width` pixels wide, in the font `font`. */
export function layoutLabels(model, width, font) {
  const span = Math.max(1, width - 2 * EDGE);
  const x = (ms) => EDGE + (ms / model.duration) * span;
  const placed = new Map();
  const rows = model.lanes.map((lane) => {
    const labels = lane.events.map((event) => {
      const anchor = x(event.at);
      const size = textWidth(event.label, font) + LABEL_CHROME;
      // A label that would pass the axis end reads back from its mark.
      const flip = anchor + size > width && anchor - size >= 0;
      const left = flip ? anchor - size : Math.min(anchor, Math.max(0, width - size));
      return { id: event.id, left, size, flip };
    });
    const rowOf = assignRows(
      labels,
      (label) => label.left,
      (label) => label.left + label.size + LABEL_GAP,
    );
    for (const label of labels)
      placed.set(label.id, { ...label, row: rowOf.get(label.id) });
    return labels.length ? 1 + Math.max(...rowOf.values()) : 1;
  });
  return { x, span, rows, placed, pxPerMs: span / model.duration };
}

const px = (value) => `${Math.round(value * 64) / 64}px`;

/**
 * Draw the timeline into `host` with the initial renderer's `tools`. Returns the
 * retained controls and `show(index)`, which paints a step, and `layout()`, which
 * measures the track and lays the labels out again.
 */
export function drawTimeline(host, tools) {
  const model = readTimeline(host);
  const saved = Number(tools.tabStore.get(`timeline:${host.id}`));
  let current = Math.max(
    0,
    model.steps.findIndex((step) => step.time === saved),
  );
  let layout = null;

  const view = tools.offer("div", "lf-timeline-view");
  const controls = tools.offer("div", "lf-timeline-controls");
  controls.setAttribute("role", "group");
  controls.setAttribute("aria-label", host.getAttribute("aria-label") ?? "Timeline");
  const previous = tools.offer("button", "lf-btn lf-timeline-previous", "Previous");
  const position = tools.offer("span", "lf-timeline-position");
  tools.generatedElement(position, { says: false });
  const next = tools.offer("button", "lf-btn lf-timeline-next", "Next");
  controls.append(previous, position, next);

  // The chart repeats the step list's words, which assistive technology reads there.
  const chart = document.createElement("div");
  chart.className = "lf-timeline-chart";
  chart.setAttribute("aria-hidden", "true");
  tools.generatedElement(chart, { says: "echo" });

  const list = document.createElement("ol");
  list.className = "lf-timeline-steps";
  tools.generatedElement(list, { says: true });
  const rows = model.steps.map((step, index) => {
    const item = document.createElement("li");
    const button = tools.offer("button", "lf-timeline-step");
    button.dataset.step = String(index);
    const at = document.createElement("span");
    at.className = "lf-timeline-step-time";
    at.textContent = clock(step.time);
    button.append(at);
    for (const event of step.events) {
      const line = document.createElement("span");
      line.className = "lf-timeline-step-event";
      const lane = document.createElement("span");
      lane.className = "lf-timeline-step-lane";
      lane.textContent = `${model.lanes[event.lane].label}: `;
      line.append(lane, event.label);
      button.append(line);
    }
    item.append(button);
    list.append(item);
    return button;
  });

  view.append(controls, chart, list);
  host.append(view);

  const paintChart = () => {
    const now = model.steps[current]?.time ?? 0;
    const ticks = layout
      ? axisTicks(0, model.duration, model.duration, layout.pxPerMs)
      : [];
    render(
      html`${model.lanes.map(
          (lane) =>
            html`<span
              class="lf-timeline-name"
              style="grid-row: ${lane.index + 2}; --lf-timeline-rows: ${layout?.rows[lane.index] ?? 1}"
              >${lane.label}</span
            >`,
        )}
        <div class="lf-timeline-ruler">
          ${repeat(
            ticks,
            (tick) => `${tick.step}:${tick.time}`,
            (tick) =>
              html`<span
                class="lf-timeline-tick"
                ?data-major=${tick.major}
                ?data-flip=${tick.major && tick.time * layout.pxPerMs > layout.span - 36}
                style="left: ${px(layout.x(tick.time))}"
                >${tick.label ?? nothing}</span
              >`,
          )}
        </div>
        ${model.lanes.map(
          (lane) =>
            html`<div
              class="lf-timeline-lane"
              style="grid-row: ${lane.index + 2}; --lf-timeline-rows: ${layout?.rows[lane.index] ?? 1}"
            >
              ${repeat(
                lane.events,
                (event) => event.id,
                (event) => {
                  const label = layout?.placed.get(event.id);
                  const { state, done } = stateAt(event, now);
                  const start = layout ? layout.x(event.at) : 0;
                  const end =
                    layout && event.end !== null ? layout.x(event.end) : start;
                  return html`<div
                    class="lf-timeline-event"
                    data-event=${event.id}
                    data-step=${event.step}
                    data-state=${state}
                  >
                    <span
                      class="lf-timeline-label"
                      ?data-flip=${label?.flip}
                      style="--lf-timeline-row-index: ${label?.row ?? 0}; left: ${px(label?.left ?? 0)}"
                      >${event.label}</span
                    >
                    <span
                      class="lf-timeline-mark"
                      data-kind=${event.end === null ? "instant" : "span"}
                      style="left: ${px(start)}; --lf-timeline-length: ${px(end - start)}; --lf-timeline-done: ${done}"
                    ></span>
                  </div>`;
                },
              )}
            </div>`,
        )}
        <div class="lf-timeline-playhead">
          <span
            class="lf-timeline-playhead-line"
            style="left: ${px(layout ? layout.x(now) : 0)}"
          ></span>
        </div>`,
      chart,
    );
    chart.style.setProperty("--lf-timeline-lanes", String(model.lanes.length));
  };

  const paintTransport = () => {
    tools.keeps(previous, "aria-disabled", current > 0 ? null : "true");
    tools.keeps(
      next,
      "aria-disabled",
      current < model.steps.length - 1 ? null : "true",
    );
    const text = model.steps.length
      ? `Step ${current + 1} of ${model.steps.length} · ${clock(model.steps[current].time)}`
      : "No events";
    if (position.textContent !== text) position.textContent = text;
    rows.forEach((row, index) => {
      tools.keeps(row, "aria-current", index === current ? "step" : null);
      tools.keeps(row, "data-past", index < current ? "" : null);
    });
  };

  const drawing = {
    model,
    controls,
    previous,
    next,
    chart,
    rows,
    get current() {
      return current;
    },
    /** Paint step `index`, clamped to the steps there are. */
    show(index) {
      current = Math.max(0, Math.min(model.steps.length - 1, index));
      paintTransport();
      paintChart();
      return current;
    },
    /** Measure the track and lay labels out again; false while it has no width. */
    layout() {
      const ruler = chart.querySelector(".lf-timeline-ruler");
      const width = ruler?.clientWidth ?? 0;
      if (!width) return false;
      const style = getComputedStyle(chart);
      const font = `${style.getPropertyValue("--lf-timeline-label-weight").trim() || 500} ${style.fontSize} ${style.fontFamily}`;
      layout = layoutLabels(model, width, font);
      paintChart();
      return true;
    },
    /** The event's drawn group and its mark, for comment targets. */
    eventElement(id) {
      return chart.querySelector(`.lf-timeline-event[data-event="${CSS.escape(id)}"]`);
    },
  };
  paintTransport();
  paintChart();
  drawing.layout();
  return drawing;
}
