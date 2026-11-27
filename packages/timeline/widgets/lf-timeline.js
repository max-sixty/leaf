/* Step through an authored sequence of events, drawn by an Effect UI component
 * (runtime/effect-widget.js) from the authored lanes, which stay where the author put
 * them, hidden by the stylesheet while the drawing shows them in their place.
 *
 * Previous and Next, the Left and Right arrows, Home and End, a row of the step list
 * and a press on a mark all set the step. The step is tab-local view state, the
 * Model's `current`, never a page event: two readers stepping the same page don't
 * disagree about anything Leaf records. It is kept for the tab (`KeepInTab`) by the
 * time it stands at, so a revision that adds a step before it keeps the reader at
 * the same moment. A step moves only the playhead, which glides to its new time
 * unless the reader asked for less motion; every other box keeps its place. A step
 * by Previous, Next, Home or End is said aloud (`Announce`).
 *
 * Each event is a visual part `event:<id>`, so a comment names the event however the
 * layout changes. Following a comment to an event steps to it.
 *
 * It imports only what loads in any document, so a plain HTML page that maps
 * `/runtime/` and `/vendor/` draws it too, and steps it by its buttons, rows and marks,
 * which are the widget's own presses, by pointer or by Enter and Space. What Leaf adds
 * it reads from outside: the keys as `lfCommands`, the step a key reached as words for
 * a listener, where a key from a row of the step list leaves the user (`lands`), and
 * the events as visual parts (`lfParts`). The view's root declares these once it is
 * in the document (`DeclareTimeline`), and says again after each draw that moves the
 * step or the layout that what they read may have changed.
 *
 * Labels are laid out against the ruler's width and the labels' font, which the
 * ruler reports as it connects and whenever its width or the page's fonts change
 * (`MeasureRuler`); stepping changes states and the playhead, never geometry. */
import {
  Component,
  Effect,
  Html,
  Mount,
  Queue,
  Schema,
  Stream,
  UiSchema,
} from "/vendor/effect-ui.js";
import { defineWidget, widgetProps } from "/runtime/effect-widget.js";
import { Announce, KeepInTab } from "/runtime/widget-services.js";
import { tabStore } from "/runtime/portable-api.js";
import {
  offerActionElement,
  offerAttributes,
  selectableAttributes,
} from "/runtime/lib/controls.js";
import { sizeObserver } from "/runtime/lib/frame-pass.js";
import { textWidth } from "/runtime/lib/text-width.js";
import { COMMANDS, layoutChanged } from "/runtime/lib/widget-events.js";
import {
  assignRows,
  axisTicks,
  elapsed,
  onCalendar,
  AXIS_EDGE as EDGE,
  AXIS_LABEL_GAP as LABEL_GAP,
  AXIS_LABEL_CHROME as LABEL_CHROME,
} from "/runtime/lib/time-axis.js";

const Named = { label: Schema.String, abbr: Schema.NullOr(Schema.String) };
// Runs, lanes and events refer to one another by their index in the reading, so it is
// plain data that compares by value.
const TimelineReading = Schema.Struct({
  runs: Schema.Array(Schema.Struct({ ...Named, row: Schema.Number })),
  lanes: Schema.Array(
    Schema.Struct({
      ...Named,
      run: Schema.NullOr(Schema.Number),
      name: Schema.String,
      row: Schema.Number,
      events: Schema.Array(Schema.Number),
    }),
  ),
  events: Schema.Array(
    Schema.Struct({
      id: Schema.String,
      label: Schema.String,
      lane: Schema.Number,
      at: Schema.Number,
      end: Schema.NullOr(Schema.Number),
      step: Schema.Number,
    }),
  ),
  steps: Schema.Array(
    Schema.Struct({ time: Schema.Number, events: Schema.Array(Schema.Number) }),
  ),
  bands: Schema.Number,
  start: Schema.NullOr(Schema.String),
  duration: Schema.Number,
  problems: Schema.Array(Schema.String),
});
/** @typedef {typeof TimelineReading.Type} TimelineReading */

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
 * and would each keep a playhead of their own.
 * @param {Element} host @returns {TimelineReading} */
export function readTimeline(host) {
  /** @type {string[]} */
  const problems = [];
  /** @type {TimelineReading["runs"][number][]} */
  const runs = [];
  /** @type {TimelineReading["lanes"][number][]} */
  const lanes = [];
  /** @type {(Omit<TimelineReading["events"][number], "step"> & {step: number})[]} */
  const events = [];
  // Grid row 1 holds the ruler; a run's name takes the row above its lanes.
  let row = 1;
  /** @param {Element} lane @param {number | null} run */
  const readLane = (lane, run) => {
    const index = lanes.length;
    const label = lane.getAttribute("label") ?? "";
    /** @type {number[]} */
    const held = [];
    for (const event of lane.children) {
      if (event.localName !== "lf-event") continue;
      const at = time(event.getAttribute("at")) ?? 0;
      let end = time(event.getAttribute("end"));
      if (end !== null && end < at) {
        problems.push(`lf-event #${event.id} ends (${end}) before it starts (${at})`);
        end = null;
      }
      held.push(events.length);
      events.push({
        id: event.id,
        label: event.getAttribute("label") ?? "",
        lane: index,
        at,
        end: end === at ? null : end,
        step: 0,
      });
    }
    lanes.push({
      label,
      abbr: lane.getAttribute("abbr"),
      run,
      name: run === null ? label : `${runs[run]?.label} · ${label}`,
      row: ++row,
      events: held,
    });
  };
  /** @type {Element | null} */
  let bare = null;
  for (const child of host.children) {
    if (child.localName === "lf-lane") {
      readLane(child, null);
      bare ??= child;
    }
    if (child.localName !== "lf-run") continue;
    const run = runs.length;
    runs.push({
      label: child.getAttribute("label") ?? "",
      abbr: child.getAttribute("abbr"),
      row: ++row,
    });
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
  /** @type {{time: number, events: number[]}[]} */
  const steps = [];
  const order = events
    .map((_, index) => index)
    .toSorted(
      (a, b) =>
        /** @type {typeof events[number]} */ (events[a]).at -
          /** @type {typeof events[number]} */ (events[b]).at ||
        /** @type {typeof events[number]} */ (events[a]).lane -
          /** @type {typeof events[number]} */ (events[b]).lane,
    );
  for (const index of order) {
    const event = /** @type {typeof events[number]} */ (events[index]);
    const previous = steps.at(-1);
    if (previous?.time === event.at) previous.events.push(index);
    else steps.push({ time: event.at, events: [index] });
    event.step = steps.length - 1;
  }
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
 * whole.
 * @param {TimelineReading} reading @param {number} width @param {string} font */
export function timelineLayout(reading, width, font) {
  const span = Math.max(1, width - 2 * EDGE);
  /** @type {Map<string, {place: "start" | "flip", row: number}>} */
  const placed = new Map();
  const rows = reading.lanes.map((lane) => {
    const labels = lane.events.map((index) => {
      const event = /** @type {TimelineReading["events"][number]} */ (
        reading.events[index]
      );
      const anchor = EDGE + (event.at / reading.duration) * span;
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
      placed.set(label.id, {
        place: /** @type {"start" | "flip"} */ (label.place),
        row: rowOf.get(label.id),
      });
    return 1 + Math.max(0, ...rowOf.values());
  });
  const ticks = axisTicks(
    0,
    reading.duration,
    reading.duration,
    span / reading.duration,
    reading.start,
  );
  return { rows, placed, ticks };
}

/** @param {TimelineReading["events"][number]} event @param {number} now */
function stateAt(event, now) {
  if (event.at > now) return { state: "future", done: 0 };
  if (event.at === now) return { state: "current", done: 0 };
  const done =
    event.end === null ? 1 : Math.min(1, (now - event.at) / (event.end - event.at));
  return { state: done < 1 ? "running" : "past", done };
}

/** A step's index, kept within the steps there are.
 * @param {number} step @param {TimelineReading} reading */
const clamp = (step, reading) => Math.max(0, Math.min(reading.steps.length - 1, step));

/** What listeners hear of a step's events, and what names an event as a part.
 * @param {TimelineReading} reading @param {TimelineReading["events"][number]} event */
const describe = (reading, event) =>
  `${reading.lanes[event.lane]?.name}: ${event.label}`;

/** What a short form stands for, as its preview (`lfPreview`) reads it to a pointer
 * resting on the short form or a finger holding it. The user chose this over a key
 * beside each label in the chart, the alternative that shows before anyone points.
 * @param {string} label */
const spelledOut = (label) => () => ({ name: label });

/** A step row's preview (`lfPreview`). Its quiet words name what the timeline shows
 * elsewhere, each cell's run in the head above its column and a lane's full name in
 * the chart, so a pointer or a finger on the row previews nothing but the short form
 * it rests on. Focus, which reaches the row and none of its short forms, previews what
 * each lane's short form in the row stands for. No key reaches a row.
 * @param {TimelineReading} reading @param {TimelineReading["steps"][number]} step */
const stepPreview = (reading, step) => {
  const forms = [
    ...new Set(
      step.events.flatMap((index) => {
        const lane = reading.lanes[/** @type {any} */ (reading.events[index]).lane];
        return lane?.abbr ? [`${lane.abbr} = ${lane.label}`] : [];
      }),
    ),
  ];
  return (/** @type {string} */ route) =>
    route === "focus" && forms.length
      ? { name: forms[0], detail: forms.slice(1) }
      : false;
};

const TimelineProps = Schema.Struct({
  ...widgetProps,
  id: Schema.String,
  label: Schema.String,
  reading: TimelineReading,
  // The time of the step the tab last stood at, if it kept one.
  saved: Schema.NullOr(Schema.Number),
});
const TimelineModel = Schema.Struct({
  current: Schema.Number,
  ruler: Schema.NullOr(Schema.Struct({ width: Schema.Number, font: Schema.String })),
});
// Previous, Next, Home and End are the presses whose step is said aloud; a row or a
// mark is pressed where the reader already sees the step, and Leaf following a
// comment says where it went itself.
export const TimelineMessage = UiSchema.TaggedEnum({
  PressedStepControl: { step: Schema.Number },
  PickedStep: { step: Schema.Number },
  RevealedEvent: { step: Schema.Number },
  MeasuredRuler: { width: Schema.Number, font: Schema.String },
});

/** Previous and Next draw their action's symbol, which a view's attributes can't
 * write (controls.js, `pressAttributes`). */
const OfferSymbol = Mount.make(
  "OfferSymbol",
  { args: { className: Schema.String, action: Schema.String } },
  (/** @type {HTMLButtonElement} */ node, { className, action }) =>
    Effect.sync(() => {
      offerActionElement(node, "symbol", className, undefined, { action });
      return Component.noop;
    }),
);

/** Reports the ruler's width and the labels' font as the ruler connects and whenever
 * they change. Labels follow it in the same frame, so a timeline first shown in a
 * closed tab places them before it paints. Chromium lays the page out for paper
 * before it prints but runs no size observer there; it does report the print media
 * change, at the paper's width. */
const MeasureRuler = Mount.makeStream(
  "MeasureRuler",
  {},
  (/** @type {HTMLElement} */ node) =>
    Stream.callback((queue) =>
      Effect.acquireRelease(
        Effect.sync(() => {
          const measure = () => {
            if (!node.clientWidth) return;
            const style = getComputedStyle(node);
            Queue.offerUnsafe(
              queue,
              TimelineMessage.MeasuredRuler({
                width: node.clientWidth,
                font: `600 ${style.fontSize} ${style.fontFamily}`,
              }),
            );
          };
          const listening = new AbortController();
          const { signal } = listening;
          document.fonts.addEventListener("loadingdone", measure, { signal });
          matchMedia("print").addEventListener("change", measure, { signal });
          const sizes = sizeObserver(measure);
          sizes.observe(node);
          measure();
          return () => {
            listening.abort();
            sizes.disconnect();
          };
        }),
        (stop) => Effect.sync(stop),
      ),
    ),
);

/** The timeline's declarations to Leaf, on the element that holds the view: its keys
 * (`lfCommands`) and its events as visual parts (`lfParts`), and the reading's
 * problems as the element's `error`s. Each draw that moves the step or the layout
 * says so (`lf-layout`, `lf-commands`).
 *
 * A key's row reads the step as last drawn. Leaf asks where a key from a row of the
 * step list leaves the user (`lands`) synchronously after the press, before the
 * press's step is drawn, so a row names the step its press goes to from the drawn
 * one. Previous and Next are the widget's own buttons: each row names the press its
 * button makes and has no run (dom/keyboard/bindings.js), and the view marks a button
 * `aria-disabled` at its end, which is the availability Leaf reads. */
const DeclareTimeline = Mount.makeStream(
  "DeclareTimeline",
  {
    args: {
      reading: TimelineReading,
      current: Schema.Number,
      ruler: TimelineModel.fields.ruler,
    },
  },
  (/** @type {HTMLElement} */ node, { reading }, changes) =>
    Stream.callback((queue) =>
      Effect.gen(function* () {
        const host =
          /** @type {HTMLElement & {lfCommands?: unknown, lfParts?: unknown}} */ (
            node.closest("lf-timeline")
          );
        const last = reading.steps.length - 1;
        let drawn = 0;
        const rows = () => [
          .../** @type {NodeListOf<HTMLElement>} */ (
            node.querySelectorAll(".lf-timeline-step")
          ),
        ];
        /** A key pressed on a row of the step list carries the user to the step's row.
         * @param {() => number} step */
        const landsOn = (step) => (/** @type {Element | null} */ from) =>
          rows().some((row) => row === from) ? (rows()[step()] ?? null) : null;
        /** @param {number} step */
        const press = (step) => () =>
          Queue.offerUnsafe(queue, TimelineMessage.PressedStepControl({ step }));
        host.lfCommands = {
          title: "On a timeline",
          rows: [
            {
              id: "timeline.previous",
              title: "Previous step",
              keys: ["ArrowLeft"],
              repeat: true,
              control: node.querySelector(".lf-timeline-previous"),
              lands: landsOn(() => Math.max(0, drawn - 1)),
            },
            {
              id: "timeline.next",
              title: "Next step",
              keys: ["ArrowRight"],
              repeat: true,
              control: node.querySelector(".lf-timeline-next"),
              lands: landsOn(() => Math.min(last, drawn + 1)),
            },
            {
              id: "timeline.first",
              title: "First step",
              keys: ["Home"],
              when: () => drawn > 0,
              run: press(0),
              lands: landsOn(() => 0),
            },
            {
              id: "timeline.last",
              title: "Last step",
              keys: ["End"],
              when: () => drawn < last,
              run: press(last),
              lands: landsOn(() => last),
            },
          ],
        };
        const byId = new Map(reading.events.map((event) => [event.id, event]));
        const eventOf = (/** @type {string} */ id) =>
          byId.get(id.slice("event:".length));
        host.lfParts = {
          read: () =>
            reading.events.flatMap((event) => {
              const element = node.querySelector(
                `.lf-timeline-event[data-lf-event="${CSS.escape(event.id)}"]`,
              );
              if (!element) return [];
              const surface = element.querySelector(
                event.end === null ? ".lf-timeline-label" : ".lf-timeline-mark",
              );
              return [
                {
                  id: `event:${event.id}`,
                  element,
                  surface,
                  label: describe(reading, event),
                },
              ];
            }),
          label: (/** @type {string} */ id) => {
            const event = eventOf(id);
            return event ? describe(reading, event) : null;
          },
          reveal: (/** @type {string} */ id) => {
            const event = eventOf(id);
            if (event)
              Queue.offerUnsafe(
                queue,
                TimelineMessage.RevealedEvent({ step: event.step }),
              );
          },
        };
        for (const problem of reading.problems)
          host.dispatchEvent(
            new ErrorEvent("error", {
              error: new Error(problem),
              bubbles: true,
              composed: true,
            }),
          );
        // `changes` starts with the args the view first drew.
        yield* Stream.runForEach(changes, ({ current }) =>
          Effect.sync(() => {
            drawn = current;
            layoutChanged(host);
            host.dispatchEvent(
              new CustomEvent(COMMANDS, { bubbles: true, composed: true }),
            );
          }),
        ).pipe(Effect.forkScoped);
      }),
    ),
);

export const Timeline = Html.component({
  name: "Timeline",
  props: TimelineProps,
  model: TimelineModel,
  message: TimelineMessage,
}).make({
  init: ($) => ({
    current: Math.max(
      0,
      $.props.reading.steps.findIndex((step) => step.time === $.props.saved),
    ),
    ruler: null,
  }),
  update: ($, message) => {
    if (message._tag === "MeasuredRuler") {
      const { width, font } = message;
      const ruler = $.model.ruler;
      return ruler?.width === width && ruler.font === font
        ? $.model
        : $.evolve({ ruler: { width, font } });
    }
    const { reading, id } = $.props;
    const current = clamp(message.step, reading);
    const selected = reading.steps[current];
    if (current === $.model.current || !selected) return $.model;
    const step = $.evolve({ current }).run(
      KeepInTab.make({ key: `timeline:${id}`, value: String(selected.time) }),
    );
    if (message._tag !== "PressedStepControl") return step;
    const events = selected.events
      .map((index) => describe(reading, /** @type {any} */ (reading.events[index])))
      .join("; ");
    return step.run(
      Announce.make({
        words: `Step ${current + 1} of ${reading.steps.length}. ${events}`,
      }),
    );
  },
  view: (h, model) => {
    const { reading, label } = h.props;
    const current = clamp(model.current, reading);
    const now = reading.steps[current]?.time ?? 0;
    const along = (/** @type {number} */ ms) => String(ms / reading.duration);
    const layout = model.ruler
      ? timelineLayout(reading, model.ruler.width, model.ruler.font)
      : null;
    const position = reading.steps.length
      ? `Step ${current + 1} of ${reading.steps.length} · ${elapsed(now, reading.start)}`
      : "No events";
    /** @param {"previous" | "next"} action @param {number} step @param {boolean} available */
    const stepButton = (action, step, available) =>
      h.button
        .class(`lf-timeline-${action}`)
        .attr("aria-disabled", available ? undefined : "true")
        .onMount(OfferSymbol({ className: `lf-timeline-${action}`, action }))
        .on("click", TimelineMessage.PressedStepControl({ step }));
    // Compared runs each take a column of the step list, named once in the list's
    // head, so a row shows every run at its moment without repeating a run's name. A
    // run number on each row would keep one column at any width, but the reader
    // would look each number up in the chart. A timeline of bare lanes has one column.
    // The head is hidden from listeners, who hear each cell's run as its quiet word.
    // The list names a run or lane by its short form (`abbr`) where the author gives
    // one, since the chart above names it in full; listeners hear the full name. The
    // author declares the short form because letters taken from labels collide, as
    // Job A's and Job B's would.
    const columns = reading.runs.length ? reading.runs.map((_, run) => run) : [null];
    /** A step's lane name. A short form is hidden from listeners, who hear the label
     * as its quiet word.
     * @param {TimelineReading["lanes"][number]} lane */
    const laneName = (lane) =>
      h.span
        .class("lf-timeline-step-lane")
        .attr("data-lf-quiet", lane.abbr ? lane.label : undefined)
        .children(
          lane.abbr
            ? h.span
                .attr("aria-hidden", "true")
                .prop("lfPreview", spelledOut(lane.label))
                .children(lane.abbr)
            : lane.label,
          ": ",
        );
    return h.div
      .class("lf-timeline-view")
      .attr("data-lf-gen", "1")
      .onMount(DeclareTimeline({ reading, current, ruler: model.ruler }))
      .children(
        h.div
          .attrs(offerAttributes("div", "lf-timeline-controls"))
          .attr("role", "group")
          .attr("aria-label", label)
          .children(
            stepButton("previous", current - 1, current > 0),
            stepButton("next", current + 1, current < reading.steps.length - 1),
            h.span
              .attrs(offerAttributes("span", "lf-timeline-position"))
              .children(position),
          ),
        h.div
          .class("lf-timeline-chart")
          .attr("aria-hidden", "true")
          .attr("data-lf-gen", "1")
          .attr("data-lf-echo", "")
          .style({
            "--lf-timeline-bands": String(reading.bands),
            "--lf-axis-edge": `${EDGE}px`,
          })
          .children(
            ...reading.runs.map((run) =>
              h.span
                .class("lf-timeline-run", "lf-label")
                .style({ gridRow: String(run.row) })
                .children(run.label),
            ),
            ...reading.lanes.map((lane, index) =>
              h.span
                .class("lf-timeline-name")
                .style({
                  gridRow: String(lane.row),
                  "--lf-timeline-rows": String(layout?.rows[index] ?? 1),
                })
                .children(lane.label),
            ),
            h.div
              .class("lf-timeline-ruler")
              .onMount(MeasureRuler())
              .children(
                ...(layout?.ticks ?? []).map((tick) =>
                  h.span
                    .key(`${tick.step}:${tick.time}`)
                    .class("lf-axis-tick")
                    .attr("data-lf-major", tick.major ? "" : undefined)
                    .attr("data-lf-flip", tick.flip ? "" : undefined)
                    .style({ "--lf-axis-at": along(tick.time) })
                    .children(tick.label ?? null),
                ),
              ),
            h.div.class("lf-timeline-grid").children(
              ...(layout?.ticks ?? [])
                .filter((tick) => tick.major)
                .map((tick) =>
                  h.span
                    .key(`${tick.step}:${tick.time}`)
                    .class("lf-axis-gridline")
                    .attr("data-lf-flip", tick.flip ? "" : undefined)
                    .style({ "--lf-axis-at": along(tick.time) }),
                ),
            ),
            ...reading.lanes.map((lane, index) =>
              h.div
                .class("lf-timeline-lane")
                .style({
                  gridRow: String(lane.row),
                  "--lf-timeline-rows": String(layout?.rows[index] ?? 1),
                })
                .children(
                  ...lane.events.map((at) => {
                    const event = /** @type {TimelineReading["events"][number]} */ (
                      reading.events[at]
                    );
                    const placed = layout?.placed.get(event.id);
                    const { state, done } = stateAt(event, now);
                    return h.div
                      .key(event.id)
                      .class("lf-timeline-event")
                      .attr("data-lf-event", event.id)
                      .attr("data-lf-state", state)
                      .on("click", TimelineMessage.PickedStep({ step: event.step }), {
                        preventDefault: "always",
                      })
                      .children(
                        h.span
                          .class("lf-timeline-label", "lf-on-axis")
                          .attr("data-lf-place", placed?.place ?? "start")
                          .style({
                            "--lf-timeline-row-index": String(placed?.row ?? 0),
                            "--lf-axis-at": along(event.at),
                          })
                          .children(event.label),
                        h.span
                          .class("lf-timeline-mark", "lf-on-axis")
                          .attr("data-lf-kind", event.end === null ? "instant" : "span")
                          .style({
                            "--lf-axis-at": along(event.at),
                            "--lf-timeline-span": along(
                              (event.end ?? event.at) - event.at,
                            ),
                            "--lf-timeline-done": String(done),
                          }),
                      );
                  }),
                ),
            ),
            h.div
              .class("lf-timeline-playhead")
              .children(
                h.span
                  .class("lf-timeline-playhead-line", "lf-on-axis")
                  .style({ "--lf-axis-at": along(now) }),
              ),
          ),
        h.ol
          .class("lf-timeline-steps", "lf-rows")
          .attr("data-lf-gen", "1")
          .attr("data-lf-said", "")
          .style({ "--lf-timeline-columns": String(columns.length) })
          .children(
            reading.runs.length
              ? h.li
                  .class("lf-timeline-steps-head")
                  .attr("aria-hidden", "true")
                  .children(
                    ...reading.runs.map((run, column) =>
                      h.span
                        .class("lf-timeline-steps-run", "lf-label")
                        .style({ gridColumn: String(column + 2) })
                        .prop("lfPreview", run.abbr ? spelledOut(run.label) : undefined)
                        .children(run.abbr ?? run.label),
                    ),
                  )
              : null,
            ...reading.steps.map((step, index) =>
              h.li.key(String(step.time)).children(
                h.span
                  .attrs(selectableAttributes("button", "lf-timeline-step", "row"))
                  .attr("data-lf-said", "")
                  .attr("tabindex", "0")
                  .attr("aria-current", index === current ? "step" : undefined)
                  .attr("data-lf-ahead", index > current ? "" : undefined)
                  .prop("lfPreview", stepPreview(reading, step))
                  .on("click", TimelineMessage.PickedStep({ step: index }), {
                    preventDefault: "always",
                  })
                  .children(
                    h.span
                      .class("lf-timeline-step-time", "lf-row-lead")
                      .children(elapsed(step.time, reading.start)),
                    ...columns.map((run, column) => {
                      const events = step.events
                        .map(
                          (at) =>
                            /** @type {TimelineReading["events"][number]} */ (
                              reading.events[at]
                            ),
                        )
                        .filter((event) => reading.lanes[event.lane]?.run === run);
                      return events.length
                        ? h.span
                            .class("lf-timeline-step-cell", "lf-row-main")
                            .style(
                              run === null ? {} : { gridColumn: String(column + 2) },
                            )
                            .attr(
                              "data-lf-quiet",
                              run === null ? undefined : reading.runs[run]?.label,
                            )
                            .children(
                              ...events.map((event) =>
                                h.span
                                  .class("lf-timeline-step-event")
                                  .children(
                                    laneName(
                                      /** @type {TimelineReading["lanes"][number]} */ (
                                        reading.lanes[event.lane]
                                      ),
                                    ),
                                    event.label,
                                  ),
                              ),
                            )
                        : null;
                    }),
                  ),
              ),
            ),
          ),
      );
  },
});

defineWidget("lf-timeline", Timeline, {
  inputs: (element) => ({
    id: element.id,
    label: element.getAttribute("aria-label") ?? "Timeline",
    reading: readTimeline(element),
    saved: time(tabStore.get(`timeline:${element.id}`)),
  }),
});
