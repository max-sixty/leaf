import {
  render as timelineTemplate,
  timelineModel,
  timelineLayout,
} from "./timeline-view.js";
/* Step through an authored sequence of events. One Lit template draws in this
 * element throughout its lifetime, with native authored lanes as its source.
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
 * which are the widget's own presses, by pointer or by Enter and Space. What Leaf adds
 * it reads from outside: the keys as `lfCommands`, the step a key reached as words for
 * a listener (`announce`), where a key from a row of the step list leaves the user
 * (`lands`), and the events as visual parts.
 * The element draws the drawing's template itself, in the task that changes the step or
 * the layout, so nothing waits on it, and a failure shows where it happened
 * (`failSoft`). Its step is kept under its id, which no other widget on the page or in
 * a reply shares. */
import {
  announce,
  commandsChanged,
  failSoft,
  once,
  registerVisualParts,
  render,
  reportFailure,
  sizeObserver,
  tabStore,
  whileConnected,
} from "/runtime/portable-api.js";

/** @param {HTMLElement} host */
function drawingFor(host) {
  const model = timelineModel(host);
  const saved = Number(tabStore.get(`timeline:${host.id}`));
  return {
    model,
    current: Math.max(
      0,
      model.steps.findIndex((step) => step.time === saved),
    ),
    get chart() {
      return host.querySelector(".lf-timeline-chart");
    },
    get rows() {
      /** @type {NodeListOf<HTMLElement>} */
      const rows = host.querySelectorAll(".lf-timeline-step");
      return [...rows];
    },
    get previous() {
      return host.querySelector(".lf-timeline-previous");
    },
    get next() {
      return host.querySelector(".lf-timeline-next");
    },
    /** @param {string} id @returns {HTMLElement | null} */
    eventElement(id) {
      return host.querySelector(`.lf-timeline-event[data-event="${CSS.escape(id)}"]`);
    },
  };
}

class Timeline extends HTMLElement {
  /** @type {ReturnType<typeof drawingFor> | undefined} */
  #reading;
  get #drawing() {
    return (this.#reading ??= drawingFor(this));
  }
  /** @type {ReturnType<typeof timelineLayout> | undefined} */
  #layout;
  /** @type {ReturnType<typeof registerVisualParts> | undefined} */
  #parts;
  // Labels are laid out against the ruler's width, so they follow it in the same
  // frame: a timeline first shown in a closed tab places them before it paints.
  // The ruler's own size doesn't change with the layout, so this never loops.
  #relayout = () => {
    const ruler = this.querySelector(".lf-timeline-ruler");
    if (ruler?.clientWidth) {
      const style = getComputedStyle(ruler);
      this.#layout = timelineLayout(
        this.#drawing.model,
        ruler.clientWidth,
        `600 ${style.fontSize} ${style.fontFamily}`,
      );
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
      render(
        timelineTemplate(
          this,
          this.#drawing.current,
          this.#drawing.model,
          this.#layout,
        ),
        this,
        { host: this },
      );
    } catch (error) {
      failSoft(this, error);
    }
  }

  #setup() {
    const drawing = this.#drawing;
    const { model } = drawing;
    this.#draw();
    const chart = drawing.chart,
      previous = drawing.previous,
      next = drawing.next;
    const ruler = chart?.querySelector(".lf-timeline-ruler");
    if (!chart || !previous || !next || !ruler)
      throw new Error("Timeline did not draw its controls");
    for (const authored of this.querySelectorAll(":scope > :is(lf-lane, lf-run)"))
      authored.setAttribute("hidden", "");
    for (const problem of model.problems) reportFailure(this, new Error(problem));
    const steps = model.steps.length;
    // A key pressed on a row of the step list carries the user to the step's row.
    const lands = (/** @type {Element | null} */ from) =>
      from !== null && drawing.rows.some((row) => row === from)
        ? drawing.rows[drawing.current]
        : null;
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
          control: previous,
          lands,
        },
        {
          id: "timeline.next",
          title: "Next step",
          keys: ["ArrowRight"],
          repeat: true,
          control: next,
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
    previous.addEventListener("click", () => this.#go(drawing.current - 1, true));
    next.addEventListener("click", () => this.#go(drawing.current + 1, true));
    const events = new Map(model.events.map((event) => [event.id, event]));
    const describe = (
      /** @type {import("./timeline-view.js").TimelineEvent} */ event,
    ) => `${event.lane.name}: ${event.label}`;
    this.#parts = registerVisualParts(
      this,
      () =>
        model.events.flatMap((event) => {
          const element = drawing.eventElement(event.id);
          if (!element) return [];
          /** @type {HTMLElement | null} */
          const surface = element.querySelector(
            event.end === null ? ".lf-timeline-label" : ".lf-timeline-mark",
          );
          return [
            { id: `event:${event.id}`, element, surface, label: describe(event) },
          ];
        }),
      {
        label: (/** @type {string} */ id) => {
          const event = events.get(id.slice("event:".length));
          return event ? describe(event) : null;
        },
        reveal: (/** @type {string} */ id) => {
          const event = events.get(id.slice("event:".length));
          if (event) this.#go(event.step, false);
        },
      },
    );
    whileConnected(this, (signal) => {
      const pick = (/** @type {Event} */ event) => {
        if (!(event.target instanceof Element)) return;
        const target = event.target.closest("[data-step]");
        if (target && this.contains(target))
          this.#go(Number(target.getAttribute("data-step")), false);
      };
      // The step list's rows are its buttons, which Enter and Space press as they do a
      // native button's (`selectableOffered`); a press on a mark is the pointer's
      // shortcut to the same step.
      for (const region of [chart, ...drawing.rows])
        region.addEventListener("click", pick, { signal });
      document.fonts.addEventListener("loadingdone", this.#relayout, { signal });
      const sizes = sizeObserver(this.#relayout);
      sizes.observe(ruler);
      // Chromium lays the page out for paper before it prints but runs no size
      // observer there; it does report the print media change, at the paper's width.
      matchMedia("print").addEventListener("change", this.#relayout, { signal });
      this.#relayout();
      return () => sizes.disconnect();
    });
  }

  /** @param {number} index @param {boolean} keyed */
  #go(index, keyed) {
    const drawing = this.#drawing;
    const before = drawing.current;
    drawing.current = Math.max(0, Math.min(drawing.model.steps.length - 1, index));
    const step = drawing.current;
    if (step === before) return;
    this.#draw();
    const selected = drawing.model.steps[step];
    if (!selected) throw new Error(`Timeline has no step ${step}`);
    tabStore.set(`timeline:${this.id}`, String(selected.time));
    this.#parts?.update();
    commandsChanged(this);
    if (!keyed) return;
    const { model } = drawing;
    const events = selected.events
      .map((event) => `${event.lane.name}: ${event.label}`)
      .join("; ");
    announce(`Step ${step + 1} of ${model.steps.length}. ${events}`);
  }
}

customElements.define("lf-timeline", Timeline);
