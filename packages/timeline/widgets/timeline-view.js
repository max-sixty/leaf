/* The timeline has one browser view. Labels pack by their measured extents in the
 * actual ruler column; stepping changes states and the playhead, never geometry. */
import { html, nothing, repeat } from "/vendor/lit.js";
import {
  offered,
  offeredAction,
  selectableOffered,
  generated,
  assignRows,
  axisTicks,
  textWidth,
} from "/runtime/portable-api.js";

const EDGE = 12;
const LABEL_GAP = 8;
const LABEL_CHROME = 12;

const time = (value) => (value == null || value === "" ? null : Number(value));
export const clock = (ms) => `${Number((ms / 1000).toFixed(3))} s`;
const fraction = (value) => Math.round(value * 1e5) / 1e5;

/** Authored runs, lanes and events become the timeline's one ordered reading. Every
 * run shares the one axis, scaled to the longest, and the one playhead, so a moment
 * lines up down all of them. A lane written directly in the timeline is in no run. */
export function timelineModel(host) {
  const problems = [];
  const runs = new Map(
    [...host.children]
      .filter((child) => child.localName === "lf-run")
      .map((run) => [run, { label: run.getAttribute("label") ?? "", row: null }]),
  );
  // Grid row 1 holds the ruler; a run's name takes the row above its first lane.
  let row = 1;
  const lanes = [
    ...host.querySelectorAll(":scope > lf-lane, :scope > lf-run > lf-lane"),
  ].map((lane, index) => {
    const run = runs.get(lane.parentElement) ?? null;
    if (run && run.row === null) run.row = ++row;
    const label = lane.getAttribute("label") ?? "";
    return {
      index,
      label,
      name: run ? `${run.label} · ${label}` : label,
      row: ++row,
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
    };
  });
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
    runs: [...runs.values()].filter((run) => run.row !== null),
    lanes,
    bands: row - 1,
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

const stepButton = (action, available) =>
  html`<button
    ${offeredAction("symbol", `lf-timeline-${action}`, undefined, { action })}
    aria-disabled=${available ? nothing : "true"}
  ></button>`;

/** One retained template for connection, revision, resizing and stepping. */
export function render(host, current, model, layout) {
  current = Math.max(0, Math.min(model.steps.length - 1, current));
  const now = model.steps[current]?.time ?? 0;
  const along = (ms) => fraction(ms / model.duration);
  const position = model.steps.length
    ? `Step ${current + 1} of ${model.steps.length} · ${clock(now)}`
    : "No events";
  return html`<div class="lf-timeline-view" ${generated({ says: false })}>
    <div
      ${offered("lf-timeline-controls")}
      role="group"
      aria-label=${host.getAttribute("aria-label") ?? "Timeline"}
    >
      ${stepButton("previous", current > 0)}
      ${stepButton("next", current < model.steps.length - 1)}
      <span ${offered("lf-timeline-position")}>${position}</span>
    </div>
    <div
      class="lf-timeline-chart"
      aria-hidden="true"
      ${generated({ says: "echo" })}
      style="--lf-timeline-bands: ${model.bands}; --lf-timeline-edge: ${EDGE}px"
    >
      ${model.runs.map(
        (run) =>
          html`<span class="lf-timeline-run lf-label" style="grid-row: ${run.row}"
            >${run.label}</span
          >`,
      )}
      ${model.lanes.map(
        (lane) =>
          html`<span
            class="lf-timeline-name"
            style="grid-row: ${lane.row}; --lf-timeline-rows: ${layout?.rows[lane.index] ?? 1}"
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
            style="grid-row: ${lane.row}; --lf-timeline-rows: ${layout?.rows[lane.index] ?? 1}"
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
    <ol class="lf-timeline-steps lf-rows" ${generated({ says: true })}>
      ${repeat(
        model.steps,
        (step) => step.time,
        (step, index) =>
          html`<li>
            <span
              ${selectableOffered("button", "lf-timeline-step", "row")}
              ${generated({ says: true })}
              tabindex="0"
              data-step=${index}
              aria-current=${index === current ? "step" : nothing}
              ?data-past=${index < current}
            >
              <span class="lf-timeline-step-time lf-row-lead">${clock(step.time)}</span>
              ${step.events.map(
                (event) =>
                  html`<span class="lf-timeline-step-event lf-row-main"
                    ><span class="lf-timeline-step-lane"
                      >${model.lanes[event.lane].name}: </span
                    >${event.label}</span
                  >`,
              )}
            </span>
          </li>`,
      )}
    </ol>
  </div>`;
}
