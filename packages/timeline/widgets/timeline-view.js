/* The timeline has one browser view. Labels pack by their measured extents in the
 * actual ruler column; stepping changes states and the playhead, never geometry. */
import { html, nothing, repeat } from "/vendor/lit.js";
import {
  actionClass,
  actionName,
  actionTemplate,
  assignRows,
  axisTicks,
  textWidth,
} from "/runtime/widget-api.js";

const EDGE = 12;
const LABEL_GAP = 8;
const LABEL_CHROME = 12;

const time = (value) => (value == null || value === "" ? null : Number(value));
export const clock = (ms) => `${Number((ms / 1000).toFixed(3))} s`;
const fraction = (value) => Math.round(value * 1e5) / 1e5;

/** Authored lane/event records become the timeline's one ordered reading. */
export function timelineModel(host) {
  const problems = [];
  const lanes = [...host.children]
    .filter((child) => child.localName === "lf-lane")
    .map((lane, index) => ({
      index,
      label: lane.getAttribute("label") ?? "",
      events: [...lane.children]
        .filter((child) => child.localName === "lf-event")
        .map((event) => {
          const at = time(event.getAttribute("at")) ?? 0;
          let end = time(event.getAttribute("end"));
          if (end !== null && end < at) {
            problems.push(
              `lf-event #${event.id} ends (${end}) before it starts (${at})`,
            );
            end = null;
          }
          return {
            id: event.id,
            label: event.getAttribute("label") ?? "",
            lane: index,
            at,
            end: end === at ? null : end,
            step: 0,
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
  return {
    lanes,
    events,
    steps,
    problems,
    duration: Math.max(1, ...events.map((event) => event.end ?? event.at)),
  };
}

/** The ruler's width and the labels' widest font determine geometry, independently
 * of the selected step. End labels read back from their mark when they fit. */
export function timelineLayout(model, width, font) {
  const span = Math.max(1, width - 2 * EDGE);
  const placed = new Map();
  const rows = model.lanes.map((lane) => {
    const labels = lane.events.map((event) => {
      const anchor = EDGE + (event.at / model.duration) * span;
      const size = Math.min(width, textWidth(event.label, font) + LABEL_CHROME);
      const place =
        anchor + size <= width ? "start" : anchor - size >= 0 ? "flip" : "end";
      const left =
        place === "start" ? anchor : place === "flip" ? anchor - size : width - size;
      return { id: event.id, left, size, place };
    });
    const rowOf = assignRows(
      labels,
      (label) => label.left,
      (label) => label.left + label.size + LABEL_GAP,
    );
    for (const label of labels)
      placed.set(label.id, { place: label.place, row: rowOf.get(label.id) });
    return 1 + Math.max(0, ...rowOf.values());
  });
  const ticks = axisTicks(0, model.duration, model.duration, span / model.duration);
  return { rows, placed, ticks, span };
}

function stateAt(event, now) {
  if (event.at > now) return { state: "future", done: 0 };
  if (event.at === now) return { state: "current", done: 0 };
  const done =
    event.end === null ? 1 : Math.min(1, (now - event.at) / (event.end - event.at));
  return { state: done < 1 ? "running" : "past", done };
}

const stepButton = (action, available) => {
  const name = actionName("symbol", undefined, action);
  return html`<button
    type="button"
    class=${`${actionClass("symbol", `lf-timeline-${action}`)} lf-ui lf-ui-face`}
    data-lf-gen="1"
    data-lf-offer="button"
    aria-label=${name}
    title=${name}
    aria-disabled=${available ? nothing : "true"}
  >
    ${actionTemplate(action, "lf-action-icon")}
  </button>`;
};

/** One retained template for connection, revision, resizing and stepping. */
export function render(host, current, model, layout) {
  current = Math.max(0, Math.min(model.steps.length - 1, current));
  const now = model.steps[current]?.time ?? 0;
  const along = (ms) => fraction(ms / model.duration);
  const position = model.steps.length
    ? `Step ${current + 1} of ${model.steps.length} · ${clock(now)}`
    : "No events";
  return html`<div class="lf-timeline-view" data-lf-gen="1">
    <div
      class="lf-timeline-controls lf-ui lf-ui-face"
      data-lf-gen="1"
      data-lf-offer=""
      role="group"
      aria-label=${host.getAttribute("aria-label") ?? "Timeline"}
    >
      ${stepButton("previous", current > 0)}
      ${stepButton("next", current < model.steps.length - 1)}
      <span
        class="lf-timeline-position lf-ui lf-ui-face"
        data-lf-gen="1"
        data-lf-offer=""
        >${position}</span
      >
    </div>
    <div
      class="lf-timeline-chart"
      aria-hidden="true"
      data-lf-gen="1"
      data-lf-echo
      style="--lf-timeline-lanes: ${model.lanes.length}; --lf-timeline-edge: ${EDGE}px"
    >
      ${model.lanes.map(
        (lane) =>
          html`<span
            class="lf-timeline-name"
            style="grid-row: ${lane.index + 2}; --lf-timeline-rows: ${layout?.rows[lane.index] ?? 1}"
            >${lane.label}</span
          >`,
      )}
      <div class="lf-timeline-ruler">
        ${repeat(
          layout?.ticks ?? [],
          (tick) => `${tick.step}:${tick.time}`,
          (tick) =>
            html`<span
              class="lf-timeline-tick"
              ?data-major=${tick.major}
              ?data-flip=${tick.major && (tick.time / model.duration) * layout.span > layout.span - 36}
              style="--lf-timeline-at: ${along(tick.time)}"
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
                return html`<div
                  class="lf-timeline-event"
                  data-event=${event.id}
                  data-step=${event.step}
                  data-state=${state}
                >
                  <span
                    class="lf-timeline-label"
                    data-place=${label?.place ?? "start"}
                    style="--lf-timeline-row-index: ${label?.row ?? 0}; --lf-timeline-at: ${along(event.at)}"
                    >${event.label}</span
                  >
                  <span
                    class="lf-timeline-mark"
                    data-kind=${event.end === null ? "instant" : "span"}
                    style="--lf-timeline-at: ${along(
                      event.at,
                    )}; --lf-timeline-span: ${along(
                      (event.end ?? event.at) - event.at,
                    )}; --lf-timeline-done: ${done}"
                  ></span>
                </div>`;
              },
            )}
          </div>`,
      )}
      <div class="lf-timeline-playhead">
        <span
          class="lf-timeline-playhead-line"
          style="--lf-timeline-at: ${along(now)}"
        ></span>
      </div>
    </div>
    <ol class="lf-timeline-steps" data-lf-gen="1" data-lf-said>
      ${repeat(
        model.steps,
        (step) => step.time,
        (step, index) =>
          html`<li>
            <span
              class="lf-timeline-step lf-ui lf-ui-face"
              role="button"
              data-lf-gen="1"
              data-lf-offer="button"
              data-lf-selectable-offer
              data-lf-said
              tabindex="0"
              data-step=${index}
              aria-current=${index === current ? "step" : nothing}
              ?data-past=${index < current}
            >
              <span class="lf-timeline-step-time">${clock(step.time)}</span>
              ${step.events.map(
                (event) =>
                  html`<span class="lf-timeline-step-event"
                    ><span class="lf-timeline-step-lane"
                      >${model.lanes[event.lane].label}: </span
                    >${event.label}</span
                  >`,
              )}
            </span>
          </li>`,
      )}
    </ol>
  </div>`;
}
