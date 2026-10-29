/* Step through an authored sequence of events. The drawing, its layout and what each
 * step shows belong to `timeline-view.js` beside this file, which delivery runs before
 * first paint; this module adopts that drawing and adds the routes that move between
 * steps, the comment targets and relayout on resize.
 *
 * Previous and Next, the Left and Right arrows, Home and End, a row of the step list
 * and a press on a mark all set the step. The step is tab-local view state, never a
 * page event: two readers stepping the same page don't disagree about anything Leaf
 * records. A step moves only the playhead, which glides to its new time unless the
 * reader asked for less motion; every other box keeps its place.
 *
 * Each event is a visual part `event:<id>`, so a comment names the event however the
 * layout changes. Following a comment to an event steps to it.
 *
 * It imports only the helpers that load in any document, so a plain HTML page that maps
 * `/runtime/` and `/vendor/` draws it too, and steps it by its buttons, rows and marks,
 * which are the widget's own presses. What Leaf adds it reads from outside: the keys as
 * `lfCommands`, the step a key reached as words for a listener (`announce`), where a key
 * from a row of the step list leaves the user (`lands`), and the events as visual parts.
 * The element draws the drawing's template itself, in the task that changes the step or
 * the layout, so nothing waits on it, and a failure shows where it happened
 * (`failSoft`). Its step is kept under its id, which no other widget on the page or in
 * a reply shares. */
import {
  announce,
  commandsChanged,
  drawsFirst,
  failSoft,
  initialRender,
  once,
  registerVisualParts,
  render,
  reportFailure,
  sizeObserver,
  tabStore,
  whileConnected,
} from "/runtime/portable-api.js";

// The drawing's producer, which this module draws with only where nothing drew before
// the first paint (below).
let drawTimeline;

class Timeline extends HTMLElement {
  #drawing;
  #parts;
  // Labels are laid out against the ruler's width, so they follow it in the same
  // frame: a timeline first shown in a closed tab places them before it paints.
  // The ruler's own size doesn't change with the layout, so this never loops.
  #relayout = () => {
    if (this.#drawing.layout()) {
      this.#draw();
      this.#parts?.update();
    }
  };

  connectedCallback() {
    if (!once(this)) return;
    try {
      this.#setup();
    } catch (error) {
      failSoft(this, error);
    }
  }

  #draw() {
    try {
      render(this.#drawing.render(), this, { host: this });
    } catch (error) {
      failSoft(this, error);
    }
  }

  #setup() {
    const drawing = (this.#drawing = initialRender(this, drawTimeline));
    const { model } = drawing;
    for (const problem of model.problems) reportFailure(this, new Error(problem));
    const steps = model.steps.length;
    // A key pressed on a row of the step list carries the user to the step's row.
    const lands = (from) =>
      drawing.rows.includes(from) ? drawing.rows[drawing.current] : null;
    // Previous and Next are the widget's own buttons: each row names the press its
    // button makes and has no run (keyboard/bindings.js), and the drawing marks a
    // button `aria-disabled` at its end, which is the availability Leaf reads.
    this.lfCommands = {
      title: "On a timeline",
      rows: [
        {
          id: "timeline.previous",
          title: "Previous step",
          keys: ["ArrowLeft"],
          repeat: true,
          control: drawing.previous,
          lands,
        },
        {
          id: "timeline.next",
          title: "Next step",
          keys: ["ArrowRight"],
          repeat: true,
          control: drawing.next,
          lands,
        },
        {
          id: "timeline.first",
          title: "First step",
          keys: ["Home"],
          when: () => drawing.current > 0,
          run: () => this.#go(0, true),
          lands,
        },
        {
          id: "timeline.last",
          title: "Last step",
          keys: ["End"],
          when: () => drawing.current < steps - 1,
          run: () => this.#go(steps - 1, true),
          lands,
        },
      ],
    };
    commandsChanged(this);
    drawing.previous.addEventListener("click", () =>
      this.#go(drawing.current - 1, true),
    );
    drawing.next.addEventListener("click", () => this.#go(drawing.current + 1, true));
    for (const row of drawing.rows) {
      row.lfCommands = {
        title: "On a timeline step",
        rows: [
          {
            id: "timeline.step",
            title: "Go to step",
            keys: ["Enter", " "],
            run: () => row.click(),
          },
        ],
      };
      commandsChanged(row);
    }
    const events = new Map(model.events.map((event) => [event.id, event]));
    const describe = (event) => `${model.lanes[event.lane].label}: ${event.label}`;
    this.#parts = registerVisualParts(
      this,
      () =>
        model.events.flatMap((event) => {
          const element = drawing.eventElement(event.id);
          if (!element) return [];
          const surface = element.querySelector(
            event.end === null ? ".lf-timeline-label" : ".lf-timeline-mark",
          );
          return [
            { id: `event:${event.id}`, element, surface, label: describe(event) },
          ];
        }),
      {
        label: (id) => {
          const event = events.get(id.slice("event:".length));
          return event ? describe(event) : null;
        },
        reveal: (id) => {
          const event = events.get(id.slice("event:".length));
          if (event) this.#go(event.step, false);
        },
      },
    );
    whileConnected(this, (signal) => {
      const pick = (event) => {
        const target = event.target.closest?.("[data-step]");
        if (target && this.contains(target))
          this.#go(Number(target.dataset.step), false);
      };
      // The step list's rows are its buttons; a press on a mark is the pointer's
      // shortcut to the same step.
      for (const region of [drawing.chart, ...drawing.rows])
        region.addEventListener("click", pick, { signal });
      const sizes = sizeObserver(this.#relayout);
      sizes.observe(drawing.chart.querySelector(".lf-timeline-ruler"));
      // Chromium lays the page out for paper before it prints but runs no size
      // observer there; it does report the print media change, at the paper's width.
      matchMedia("print").addEventListener("change", this.#relayout, { signal });
      this.#relayout();
      return () => sizes.disconnect();
    });
  }

  #go(index, keyed) {
    const drawing = this.#drawing;
    const before = drawing.current;
    drawing.current = index;
    const step = drawing.current;
    if (step === before) return;
    this.#draw();
    tabStore.set(`timeline:${this.id}`, String(drawing.model.steps[step].time));
    this.#parts.update();
    commandsChanged(this);
    if (!keyed) return;
    const { model } = drawing;
    const events = model.steps[step].events
      .map((event) => `${model.lanes[event.lane].label}: ${event.label}`)
      .join("; ");
    announce(`Step ${step + 1} of ${model.steps.length}. ${events}`);
  }
}

const define = () => customElements.define("lf-timeline", Timeline);

// Delivery draws the timeline before first paint on a Leaf page, so the element is
// defined at once and fetches nothing it doesn't run. Elsewhere it is defined once its
// producer arrives, so every timeline upgrades with the producer in hand and draws in
// the task that upgrades it, on either kind of page.
if (drawsFirst()) define();
else
  import("./timeline-view.js").then((module) => {
    drawTimeline = module.drawTimeline;
    define();
  });
