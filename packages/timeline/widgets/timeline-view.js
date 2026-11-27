/* The timeline has one browser view. Labels pack by their measured extents in the
 * actual ruler column; stepping changes states and the playhead, never geometry. */
import { html, nothing, repeat } from "/vendor/lit.js";
import { offered, offeredAction, selectableOffered } from "/runtime/lib/controls.js";
import { textWidth } from "/runtime/lib/text-width.js";
import {
  assignRows,
  timeAxis,
  elapsed,
  onCalendar,
  AXIS_EDGE as EDGE,
  AXIS_LABEL_GAP as LABEL_GAP,
  AXIS_LABEL_CHROME as LABEL_CHROME,
} from "/runtime/lib/time-axis.js";

/** @typedef {{label: string, abbr: string | null, row: number}} TimelineRun */
/** @typedef {{id: string, label: string, lane: TimelineLane, at: number, end: number | null, step: number}} TimelineEvent */
/** @typedef {{index: number, label: string, abbr: string | null, run: TimelineRun | null, name: string, row: number, events: TimelineEvent[]}} TimelineLane */
/** @typedef {{time: number, events: TimelineEvent[]}} TimelineStep */
/** @param {string | null} value */
const time = (value) => (value == null || value === "" ? null : Number(value));

/** Authored runs, lanes and events become the timeline's one ordered reading. Every
 * run shares the one axis, scaled to the longest, and the one playhead, so a moment
 * lines up down all of them. A timeline holds either runs or bare lanes: a bare lane
 * beside runs would draw as part of the run above it, so it is reported.
 *
 * Compared runs live in one timeline rather than in separate timelines linked to a
 * shared axis: one widget shares the axis and the playhead by construction, where
 * linked widgets would need code to agree on an axis as each appeared or changed,
 * and would each keep a playhead of their own. */
/** @param {HTMLElement} host */
export function timelineModel(host) {
  /** @type {string[]} */
  const problems = [];
  /** @type {TimelineRun[]} */
  const runs = [];
  /** @type {TimelineLane[]} */
  const lanes = [];
  // Grid row 1 holds the ruler; a run's name takes the row above its lanes.
  let row = 1;
  /** @param {Element} lane @param {TimelineRun | null} run */
  const readLane = (lane, run) => {
    const index = lanes.length;
    const label = lane.getAttribute("label") ?? "";
    /** @type {TimelineLane} */
    const reading = {
      index,
      label,
      abbr: lane.getAttribute("abbr"),
      run,
      name: run ? `${run.label} · ${label}` : label,
      row: ++row,
      events: [],
    };
    reading.events = [...lane.children]
      .filter((child) => child.localName === "lf-event")
      .map((event) => {
        const at = time(event.getAttribute("at")) ?? 0;
        let end = time(event.getAttribute("end"));
        if (end !== null && end < at) {
          problems.push(`lf-event #${event.id} ends (${end}) before it starts (${at})`);
          end = null;
        }
        return {
          id: event.id,
          label: event.getAttribute("label") ?? "",
          lane: reading,
          at,
          end: end === at ? null : end,
          step: 0,
        };
      });
    lanes.push(reading);
  };
  let bare = null;
  for (const child of host.children) {
    if (child.localName === "lf-lane") {
      readLane(child, null);
      bare ??= child;
    }
    if (child.localName !== "lf-run") continue;
    const run = {
      label: child.getAttribute("label") ?? "",
      abbr: child.getAttribute("abbr"),
      row: ++row,
    };
    runs.push(run);
    for (const lane of child.children)
      if (lane.localName === "lf-lane") readLane(lane, run);
  }
  if (runs.length && bare)
    problems.push(
      `lf-lane "${bare.getAttribute("label")}" stands beside lf-run elements; put it in a run`,
    );
  // A start off the calendar is reported, and the timeline reads elapsed time.
  let start = host.getAttribute("start");
  if (start !== null && !onCalendar(start)) {
    problems.push(
      `lf-timeline start "${start}" is not a date and time on the calendar`,
    );
    start = null;
  }
  const events = lanes.flatMap((lane) => lane.events);
  /** @type {TimelineStep[]} */
  const steps = [];
  for (const event of events.toSorted(
    (a, b) => a.at - b.at || a.lane.index - b.lane.index,
  )) {
    const previous = steps.at(-1);
    if (previous?.time === event.at) previous.events.push(event);
    else steps.push({ time: event.at, events: [event] });
  }
  steps.forEach((step, index) => {
    for (const event of step.events) event.step = index;
  });
  return {
    runs,
    lanes,
    bands: row - 1,
    events,
    steps,
    problems,
    start,
    duration: Math.max(1, ...events.map((event) => event.end ?? event.at)),
  };
}

/** The ruler's width and the labels' widest font determine geometry, independently
 * of the selected step. A label's stroke stands at its event's moment, so the label
 * reads on from its mark where it fits, back from it where it fits, and otherwise
 * toward the roomier side, its words cut short at the ruler's edge. A label moved
 * clear of its mark to show every word would leave its stroke at a time the event
 * isn't, or no stroke at all; the step list below the chart gives every label
 * whole. */
/** @param {ReturnType<typeof timelineModel>} model @param {number} width @param {string} font */
export function timelineLayout(model, width, font) {
  const span = Math.max(1, width - 2 * EDGE);
  const placed = new Map();
  const rows = model.lanes.map((lane) => {
    const labels = lane.events.map((event) => {
      const anchor = EDGE + (event.at / model.duration) * span;
      const wanted = textWidth(event.label, font) + LABEL_CHROME;
      const ahead = width - anchor;
      const place = wanted <= ahead || ahead >= anchor ? "start" : "flip";
      const size = Math.min(wanted, place === "start" ? ahead : anchor);
      const left = place === "start" ? anchor : anchor - size;
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
  const axis = timeAxis(
    0,
    model.duration,
    model.duration,
    span / model.duration,
    model.start,
  );
  return { rows, placed, axis };
}

/** @param {TimelineEvent} event @param {number} now */
function stateAt(event, now) {
  if (event.at > now) return { state: "future", done: 0 };
  if (event.at === now) return { state: "current", done: 0 };
  const done =
    event.end === null ? 1 : Math.min(1, (now - event.at) / (event.end - event.at));
  return { state: done < 1 ? "running" : "past", done };
}

/** @param {string} action @param {boolean} available */
const stepButton = (action, available) =>
  html`<button
    ${offeredAction("symbol", `lf-timeline-${action}`, undefined, { action })}
    aria-disabled=${available ? nothing : "true"}
  ></button>`;

/** What a short form stands for, as its preview (`lfPreview`) reads it to a pointer
 * resting on the short form or a finger holding it. The user chose this over a key
 * beside each label in the chart, the alternative that shows before anyone points.
 * @param {string} label */
const spelledOut = (label) => () => ({ name: label });

/** A step's lane name. A short form is hidden from listeners, who hear the label as
 * its quiet word.
 * @param {TimelineLane} lane */
const laneName = (lane) =>
  html`<span
    class="lf-timeline-step-lane"
    data-lf-quiet=${lane.abbr ? lane.label : nothing}
    >${
      lane.abbr
        ? html`<span aria-hidden="true" .lfPreview=${spelledOut(lane.label)}
            >${lane.abbr}</span
          >`
        : lane.label
    }${": "}</span
  >`;

/** A step row's preview (`lfPreview`). Its quiet words name what the timeline shows
 * elsewhere, each cell's run in the head above its column and a lane's full name in
 * the chart, so a pointer or a finger on the row previews nothing but the short form
 * it rests on. Focus, which reaches the row and none of its short forms, previews what
 * each lane's short form in the row stands for. No key reaches a row.
 * @param {TimelineStep} step */
const stepPreview = (step) => {
  const forms = [
    ...new Set(
      step.events.flatMap(({ lane }) =>
        lane.abbr ? [`${lane.abbr} = ${lane.label}`] : [],
      ),
    ),
  ];
  return (/** @type {string} */ route) =>
    route === "focus" && forms.length
      ? { name: forms[0], detail: forms.slice(1) }
      : false;
};

/** One retained template for connection, revision, resizing and stepping. */
/** @param {HTMLElement} host @param {number} current
 * @param {ReturnType<typeof timelineModel>} model @param {ReturnType<typeof timelineLayout> | null | undefined} layout */
export function render(host, current, model, layout) {
  current = Math.max(0, Math.min(model.steps.length - 1, current));
  const now = model.steps[current]?.time ?? 0;
  const along = (/** @type {number} */ ms) => ms / model.duration;
  // Compared runs each take a column of the step list, named once in the list's head,
  // so a row shows every run at its moment without repeating a run's name. A run
  // number on each row would keep one column at any width, but the reader would look
  // each number up in the chart. A timeline of bare lanes has one column. The head is
  // hidden from listeners, who hear each cell's run as its quiet word. The list names a
  // run or lane by its short form (`abbr`) where the author gives one, since the chart
  // above names it in full; listeners hear the full name. The author declares the short
  // form because letters taken from labels collide, as Job A's and Job B's would.
  /** @type {(TimelineRun | null)[]} */
  const columns = model.runs.length ? model.runs : [null];
  const position = model.steps.length
    ? `Step ${current + 1} of ${model.steps.length} · ${elapsed(now, model.start)}`
    : "No events";
  return html`<div class="lf-timeline-view" data-lf-gen="1">
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
      data-lf-gen="1"
      data-lf-echo
      style="--lf-timeline-bands: ${model.bands}; --lf-axis-edge: ${EDGE}px"
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
      <div class="lf-timeline-ruler">${layout?.axis.ruler}</div>
      <div class="lf-timeline-grid">${layout?.axis.grid}</div>
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
                  data-lf-event=${event.id}
                  data-lf-step=${event.step}
                  data-lf-state=${state}
                >
                  <span
                    class="lf-timeline-label lf-on-axis"
                    data-lf-place=${label?.place ?? "start"}
                    style="--lf-timeline-row-index: ${label?.row ?? 0}; --lf-axis-at: ${along(event.at)}"
                    >${event.label}</span
                  >
                  <span
                    class="lf-timeline-mark lf-on-axis"
                    data-lf-kind=${event.end === null ? "instant" : "span"}
                    style="--lf-axis-at: ${along(
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
          class="lf-timeline-playhead-line lf-on-axis"
          style="--lf-axis-at: ${along(now)}"
        ></span>
      </div>
    </div>
    <ol
      class="lf-timeline-steps lf-rows"
      data-lf-gen="1"
      data-lf-said
      style="--lf-timeline-columns: ${columns.length}"
    >
      ${
        model.runs.length
          ? html`<li class="lf-timeline-steps-head" aria-hidden="true">
              ${model.runs.map(
                (run, column) =>
                  html`<span
                    class="lf-timeline-steps-run lf-label"
                    style="grid-column: ${column + 2}"
                    .lfPreview=${run.abbr ? spelledOut(run.label) : nothing}
                    >${run.abbr ?? run.label}</span
                  >`,
              )}
            </li>`
          : nothing
      }
      ${repeat(
        model.steps,
        (step) => step.time,
        (step, index) =>
          html`<li>
            <span
              ${selectableOffered("button", "lf-timeline-step", "row")}
              data-lf-said
              tabindex="0"
              data-lf-step=${index}
              aria-current=${index === current ? "step" : nothing}
              ?data-lf-ahead=${index > current}
              .lfPreview=${stepPreview(step)}
            >
              <span class="lf-timeline-step-time lf-row-lead"
                >${elapsed(step.time, model.start)}</span
              >
              ${columns.map((run, column) => {
                const events = step.events.filter((event) => event.lane.run === run);
                return events.length
                  ? html`<span
                      class="lf-timeline-step-cell lf-row-main"
                      style=${run ? `grid-column: ${column + 2}` : nothing}
                      data-lf-quiet=${run?.label ?? nothing}
                      >${events.map(
                        (event) =>
                          html`<span class="lf-timeline-step-event"
                            >${laneName(event.lane)}${event.label}</span
                          >`,
                      )}</span
                    >`
                  : nothing;
              })}
            </span>
          </li>`,
      )}
    </ol>
  </div>`;
}
