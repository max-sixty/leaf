/* Step through an authored sequence of events. The drawing, its layout and what each
 * step shows belong to `initial/timeline-view.js`, which delivery runs before first
 * paint; this module adopts that drawing and adds the routes that move between steps,
 * the comment targets and relayout on resize.
 *
 * Previous and Next, the Left and Right arrows, Home and End, a row of the step list
 * and a press on a mark all set the step. The step is tab-local view state, never a
 * page event: two readers stepping the same page don't disagree about anything Leaf
 * records. A step moves only the playhead, which glides to its new time unless the
 * reader asked for less motion; every other box keeps its place.
 *
 * Each event is a visual part `event:<id>`, so a comment names the event however the
 * layout changes. Following a comment to an event steps to it.
 */
import {
  LeafElement,
  noChange,
  initialRender,
  commands,
  whileConnected,
  sizeObserver,
  registerVisualParts,
  reportFailure,
  focusDestination,
  focused,
  announce,
  tabStore,
  quoted,
  paintKeys,
} from "/runtime/widget-api.js";

customElements.define(
  "lf-timeline",
  class extends LeafElement {
    #drawing;
    #parts;
    // Labels are laid out against the ruler's width, so they follow it in the same
    // frame: a timeline first shown in a closed tab places them before it paints.
    // The ruler's own size doesn't change with the layout, so this never loops.
    #relayout = () => {
      if (this.#drawing.layout()) this.#parts?.update();
    };

    setup() {
      const drawing = (this.#drawing = initialRender(this));
      const { model } = drawing;
      for (const problem of model.problems) reportFailure(this, new Error(problem));
      const steps = model.steps.length;
      commands(this, "On a timeline", [
        {
          id: "timeline.previous",
          title: "Previous step",
          keys: ["ArrowLeft"],
          repeat: true,
          control: drawing.previous,
          when: () => drawing.current > 0,
          run: () => this.#go(drawing.current - 1, true),
        },
        {
          id: "timeline.next",
          title: "Next step",
          keys: ["ArrowRight"],
          repeat: true,
          control: drawing.next,
          when: () => drawing.current < steps - 1,
          run: () => this.#go(drawing.current + 1, true),
        },
        {
          id: "timeline.first",
          title: "First step",
          keys: ["Home"],
          when: () => drawing.current > 0,
          run: () => this.#go(0, true),
        },
        {
          id: "timeline.last",
          title: "Last step",
          keys: ["End"],
          when: () => drawing.current < steps - 1,
          run: () => this.#go(steps - 1, true),
        },
      ]);
      for (const row of drawing.rows)
        commands(row, "On a timeline step", [
          {
            id: "timeline.step",
            title: "Go to step",
            keys: ["Enter", " "],
            run: () => row.click(),
          },
        ]);
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

    // The drawing is retained from first paint, not template-owned.
    render() {
      return noChange;
    }

    #go(index, keyed) {
      const drawing = this.#drawing;
      const before = drawing.current;
      const step = drawing.show(index);
      if (step === before) return;
      if (!quoted(this))
        tabStore.set(`timeline:${this.id}`, String(drawing.model.steps[step].time));
      this.#parts.update();
      paintKeys();
      const row = drawing.rows[step];
      if (keyed && drawing.rows.includes(focused())) focusDestination(row, "move");
      if (keyed) {
        const { model } = drawing;
        const events = model.steps[step].events
          .map((event) => `${model.lanes[event.lane].label}: ${event.label}`)
          .join("; ");
        announce(`Step ${step + 1} of ${model.steps.length}. ${events}`);
      }
    }
  },
);
