/* One Lit lifecycle owns the timeline. The ruler column supplies its measured
 * width; measured packing is independent of the selected step.
 * Keyboard, pointer and touch all change the same tab-local step. */
import { render, timelineModel, timelineLayout } from "./timeline-view.js";
import {
  LeafElement,
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
    #model;
    #current = 0;
    #parts;

    #wiredRows = new WeakSet();

    get #rows() {
      return [...this.renderRoot.querySelectorAll(".lf-timeline-step")];
    }

    firstUpdated() {
      const root = this.renderRoot;
      commands(this, "On a timeline", [
        {
          id: "timeline.previous",
          title: "Previous step",
          keys: ["ArrowLeft"],
          repeat: true,
          control: root.querySelector(".lf-timeline-previous"),
          when: () => this.#current > 0,
          run: () => this.#go(this.#current - 1, true),
        },
        {
          id: "timeline.next",
          title: "Next step",
          keys: ["ArrowRight"],
          repeat: true,
          control: root.querySelector(".lf-timeline-next"),
          when: () => this.#current < this.#model.steps.length - 1,
          run: () => this.#go(this.#current + 1, true),
        },
        {
          id: "timeline.first",
          title: "First step",
          keys: ["Home"],
          when: () => this.#current > 0,
          run: () => this.#go(0, true),
        },
        {
          id: "timeline.last",
          title: "Last step",
          keys: ["End"],
          when: () => this.#current < this.#model.steps.length - 1,
          run: () => this.#go(this.#model.steps.length - 1, true),
        },
      ]);
      const eventById = (id) =>
        this.#model.events.find((event) => event.id === id.slice("event:".length));
      const describe = (event) =>
        `${this.#model.lanes[event.lane].label}: ${event.label}`;
      this.#parts = registerVisualParts(
        this,
        () =>
          this.#model.events.flatMap((event) => {
            const element = root.querySelector(
              `.lf-timeline-event[data-event="${CSS.escape(event.id)}"]`,
            );
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
            const event = eventById(id);
            return event ? describe(event) : null;
          },
          reveal: (id) => {
            const event = eventById(id);
            if (event) this.#go(event.step, false);
          },
        },
      );
      whileConnected(this, (signal) => {
        const observer = sizeObserver(() => this.#resize());
        observer.observe(root.querySelector(".lf-timeline-ruler"));
        document.fonts.addEventListener("loadingdone", () => this.#resize(), {
          signal,
        });
        window.addEventListener("beforeprint", () => this.#resize(), { signal });
        root.addEventListener(
          "click",
          (event) => {
            const target = /** @type {HTMLElement} */ (event.target).closest(
              "[data-step]",
            );
            if (target && root.contains(target))
              this.#go(Number(target.getAttribute("data-step")), false);
          },
          { signal },
        );
        return () => observer.disconnect();
      });
      this.requestUpdate();
      // The saved tab position changes only states and the retained playhead.
      const saved = Number(tabStore.get(`timeline:${this.id}`));
      const restored = this.#model.steps.findIndex((step) => step.time === saved);
      if (restored > 0) {
        this.#current = restored;
        this.requestUpdate();
      }
    }

    #readModel() {
      const time = this.#model?.steps[this.#current]?.time;
      this.#model = timelineModel(this);
      const retained = this.#model.steps.findIndex((step) => step.time === time);
      this.#current =
        retained >= 0
          ? retained
          : Math.max(0, Math.min(this.#current, this.#model.steps.length - 1));
    }

    render() {
      this.#readModel();
      const chart = this.renderRoot.querySelector(".lf-timeline-chart");
      const width = this.renderRoot.querySelector(".lf-timeline-ruler")?.clientWidth;
      const style = chart && getComputedStyle(chart);
      // Reserve the current label's bold width for every step, keeping rows fixed.
      const layout = width
        ? timelineLayout(
            this.#model,
            width,
            `600 ${style.fontSize} ${style.fontFamily}`,
          )
        : null;
      return render(this, this.#current, this.#model, layout);
    }

    updated(changed) {
      super.updated(changed);
      for (const row of this.#rows) {
        if (this.#wiredRows.has(row)) continue;
        this.#wiredRows.add(row);
        commands(row, "On a timeline step", [
          {
            id: "timeline.step",
            title: "Go to step",
            keys: ["Enter", " "],
            run: () => /** @type {HTMLElement} */ (row).click(),
          },
        ]);
      }
      for (const problem of this.#model.problems)
        reportFailure(this, new Error(problem));
      this.#parts?.update();
      paintKeys();
    }

    #resize() {
      this.requestUpdate();
      this.performUpdate();
    }

    #go(index, keyed) {
      const before = this.#current;
      const step = (this.#current = Math.max(
        0,
        Math.min(this.#model.steps.length - 1, index),
      ));
      if (step === before) return;
      this.requestUpdate();
      this.performUpdate();
      if (!quoted(this))
        tabStore.set(`timeline:${this.id}`, String(this.#model.steps[step].time));
      const rows = this.#rows;
      if (keyed && rows.includes(focused())) focusDestination(rows[step], "move");
      if (keyed) {
        const events = this.#model.steps[step].events
          .map((event) => `${this.#model.lanes[event.lane].label}: ${event.label}`)
          .join("; ");
        announce(`Step ${step + 1} of ${this.#model.steps.length}. ${events}`);
      }
    }
  },
);
