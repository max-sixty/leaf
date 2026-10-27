(() => {
  // leaf-initial-lit:lit
  var { AsyncDirective, AsyncReplaceDirective, CSSResult, Directive, LitElement, PartType, ReactiveElement, TemplateResultType, UnsafeHTMLDirective, UntilDirective, _$LE, _$LH, adoptStyles, asyncAppend, asyncReplace, cache, choose, classMap, clearPart, createRef, css, customElement, defaultConverter, directive, eventOptions, getCommittedValue, getCompatibleStyle, getDirectiveClass, guard, html, ifDefined, insertPart, isCompiledTemplateResult, isDirectiveResult, isPrimitive, isServer, isSingleExpression, isTemplateResult, join, keyed, literal, live, map, mathml, noChange, notEqual, nothing, property, query, queryAll, queryAssignedElements, queryAssignedNodes, queryAsync, range, ref, removePart, render, repeat, setChildPartValue, setCommittedValue, standardProperty, state, staticHtml, staticMathml, staticSvg, styleMap, supportsAdoptingStyleSheets, svg, templateContent, unsafeCSS, unsafeHTML, unsafeMathML, unsafeSVG, unsafeStatic, until, when, withStatic } = document.documentElement.lfInitial.lit;

  // browser/runtime/time-axis.js
  var TICK_SPACING = 84;
  var STEPS = [1, 2, 5];
  function tickStep(pxPerMs) {
    for (let power = 1; power < 1e9; power *= 10)
      for (const step of STEPS)
        if (step * power * pxPerMs >= TICK_SPACING) return step * power;
    return 1e9;
  }
  function tickLabel(time2, step) {
    if (time2 === 0) return "0 s";
    const digits = step >= 1e3 ? 0 : step >= 100 ? 1 : step >= 10 ? 2 : 3;
    return `${(time2 / 1e3).toFixed(digits)} s`;
  }
  function axisTicks(from, to, duration, pxPerMs) {
    const step = tickStep(pxPerMs);
    const minor = step / (String(step)[0] === "2" ? 4 : 5);
    const ticks = [];
    for (let time2 = Math.floor(from / minor) * minor; time2 <= to; time2 += minor) {
      const rounded = Math.round(time2 * 1e3) / 1e3;
      if (rounded < 0 || rounded > duration) continue;
      const major = Math.abs(rounded / step - Math.round(rounded / step)) < 1e-6;
      ticks.push({
        time: rounded,
        major,
        label: major ? tickLabel(rounded, step) : null,
        step
      });
    }
    return ticks;
  }
  function assignRows(items, start, end) {
    const rows = [];
    const rowOf = /* @__PURE__ */ new Map();
    for (const item of items.toSorted((a, b) => start(a) - start(b))) {
      let row = rows.findIndex((last) => last <= start(item));
      if (row < 0) row = rows.push(-Infinity) - 1;
      rows[row] = end(item);
      rowOf.set(item.id, row);
    }
    return rowOf;
  }
  var measuring = null;
  function textWidth(text, font) {
    measuring ??= document.createElement("canvas").getContext("2d");
    measuring.font = font;
    return measuring.measureText(text).width;
  }

  // packages/timeline/initial/timeline-view.js
  var EDGE = 12;
  var LABEL_GAP = 8;
  var LABEL_CHROME = 12;
  var time = (value) => value === null || value === "" ? null : Number(value);
  var clock = (ms) => `${Number((ms / 1e3).toFixed(3))} s`;
  function readTimeline(host) {
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
          // The index of the step it starts on, once the steps are known.
          step: 0
        };
      })
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
  function stateAt(event, now) {
    if (event.at > now) return { state: "future", done: 0 };
    if (event.at === now) return { state: "current", done: 0 };
    const done = event.end === null ? 1 : Math.min(1, (now - event.at) / (event.end - event.at));
    return { state: done < 1 ? "running" : "past", done };
  }
  function layoutLabels(model, width, font) {
    const span = Math.max(1, width - 2 * EDGE);
    const x = (ms) => EDGE + ms / model.duration * span;
    const placed = /* @__PURE__ */ new Map();
    const rows = model.lanes.map((lane) => {
      const labels = lane.events.map((event) => {
        const anchor = x(event.at);
        const size = textWidth(event.label, font) + LABEL_CHROME;
        const place = anchor + size <= width ? "start" : anchor - size >= 0 ? "flip" : "end";
        const left = place === "start" ? anchor : place === "flip" ? anchor - size : width - size;
        return { id: event.id, left: Math.max(0, left), size, place };
      });
      const rowOf = assignRows(
        labels,
        (label) => label.left,
        (label) => label.left + label.size + LABEL_GAP
      );
      for (const label of labels)
        placed.set(label.id, { place: label.place, row: rowOf.get(label.id) });
      return labels.length ? 1 + Math.max(...rowOf.values()) : 1;
    });
    return { span, rows, placed, pxPerMs: span / model.duration };
  }
  var fraction = (value) => Math.round(value * 1e5) / 1e5;
  function drawTimeline(host, tools) {
    const model = readTimeline(host);
    const saved = Number(tools.tabStore.get(`timeline:${host.id}`));
    let current = Math.max(
      0,
      model.steps.findIndex((step) => step.time === saved)
    );
    let layout = null;
    const drawing = {
      model,
      rows: [],
      get current() {
        return current;
      },
      /** Paint step `index`, clamped to the steps there are. */
      show(index) {
        current = Math.max(0, Math.min(model.steps.length - 1, index));
        paint();
        return current;
      },
      /** Measure the track and lay labels out again; false while it has no width. */
      layout() {
        const ruler = drawing.chart.querySelector(".lf-timeline-ruler");
        const width = ruler?.clientWidth ?? 0;
        if (!width) return false;
        const style = getComputedStyle(drawing.chart);
        const font = `${style.getPropertyValue("--lf-timeline-label-weight").trim() || 500} ${style.fontSize} ${style.fontFamily}`;
        layout = layoutLabels(model, width, font);
        paint();
        return true;
      },
      /** The event's drawn group and its mark, for comment targets. */
      eventElement(id) {
        return drawing.chart.querySelector(
          `.lf-timeline-event[data-event="${CSS.escape(id)}"]`
        );
      }
    };
    const generated = (says) => (node) => node && tools.generatedElement(node, { says });
    const offered = (key, cls) => (node) => {
      if (node) drawing[key] = tools.offerElement(node, cls);
    };
    const viewRef = generated(false);
    const positionRef = (node) => {
      if (node)
        tools.generatedElement(tools.offerElement(node, "lf-timeline-position"), {
          says: false
        });
    };
    const controlsRef = offered("controls", "lf-timeline-controls");
    const previousRef = (node) => {
      if (node)
        drawing.previous = tools.offerActionElement(node, "word", "lf-timeline-previous");
    };
    const nextRef = (node) => {
      if (node) drawing.next = tools.offerActionElement(node, "word", "lf-timeline-next");
    };
    const chartRef = (node) => {
      if (node) drawing.chart = tools.generatedElement(node, { says: "echo" });
    };
    const listRef = generated(true);
    const rowRefs = model.steps.map((_, index) => (node) => {
      if (!node) return;
      tools.selectableOfferElement(node, "button", "lf-timeline-step");
      drawing.rows[index] = tools.generatedElement(node, { says: true });
    });
    const chartTemplate = () => {
      const now = model.steps[current]?.time ?? 0;
      const along = (ms) => fraction(ms / model.duration);
      const ticks = layout ? axisTicks(0, model.duration, model.duration, layout.pxPerMs) : [];
      return html`${model.lanes.map(
        (lane) => html`<span
            class="lf-timeline-name"
            style="grid-row: ${lane.index + 2}; --lf-timeline-rows: ${layout?.rows[lane.index] ?? 1}"
            >${lane.label}</span
          >`
      )}
      <div class="lf-timeline-ruler">
        ${repeat(
        ticks,
        (tick) => `${tick.step}:${tick.time}`,
        (tick) => html`<span
              class="lf-timeline-tick"
              ?data-major=${tick.major}
              ?data-flip=${tick.major && tick.time * layout.pxPerMs > layout.span - 36}
              style="--lf-timeline-at: ${along(tick.time)}"
              >${tick.label ?? nothing}</span
            >`
      )}
      </div>
      ${model.lanes.map(
        (lane) => html`<div
            class="lf-timeline-lane"
            style="grid-row: ${lane.index + 2}; --lf-timeline-rows: ${layout?.rows[lane.index] ?? 1}"
          >
            ${repeat(
          lane.events,
          (event) => event.id,
          (event) => {
            const label = layout?.placed.get(event.id);
            const { state: state2, done } = stateAt(event, now);
            return html`<div
                  class="lf-timeline-event"
                  data-event=${event.id}
                  data-step=${event.step}
                  data-state=${state2}
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
              event.at
            )}; --lf-timeline-span: ${along(
              (event.end ?? event.at) - event.at
            )}; --lf-timeline-done: ${done}"
                  ></span>
                </div>`;
          }
        )}
          </div>`
      )}
      <div class="lf-timeline-playhead">
        <span
          class="lf-timeline-playhead-line"
          style="--lf-timeline-at: ${along(now)}"
        ></span>
      </div>`;
    };
    const paint = () => {
      const position = model.steps.length ? `Step ${current + 1} of ${model.steps.length} \xB7 ${clock(model.steps[current].time)}` : "No events";
      render(
        html` <div class="lf-timeline-view" ${ref(viewRef)}>
        <div
          ${ref(controlsRef)}
          role="group"
          aria-label=${host.getAttribute("aria-label") ?? "Timeline"}
        >
          <button ${ref(previousRef)} aria-disabled=${current > 0 ? nothing : "true"}>
            Previous
          </button>
          <button
            ${ref(nextRef)}
            aria-disabled=${current < model.steps.length - 1 ? nothing : "true"}
          >
            Next
          </button>
          <span ${ref(positionRef)}>${position}</span>
        </div>
        <div
          class="lf-timeline-chart"
          aria-hidden="true"
          ${ref(chartRef)}
          style="--lf-timeline-lanes: ${model.lanes.length}; --lf-timeline-edge: ${EDGE}px"
        >
          ${chartTemplate()}
        </div>
        <ol class="lf-timeline-steps" ${ref(listRef)}>
          ${model.steps.map(
          (step, index) => html`<li>
                <span
                  ${ref(rowRefs[index])}
                  tabindex="0"
                  data-step=${index}
                  aria-current=${index === current ? "step" : nothing}
                  ?data-past=${index < current}
                >
                  <span class="lf-timeline-step-time">${clock(step.time)}</span>
                  ${step.events.map(
            (event) => html`<span class="lf-timeline-step-event"
                        ><span class="lf-timeline-step-lane"
                          >${model.lanes[event.lane].label}: </span
                        >${event.label}</span
                      >`
          )}
                </span>
              </li>`
        )}
        </ol>
      </div>`,
        host
      );
    };
    paint();
    drawing.layout();
    return drawing;
  }

  // packages/timeline/initial/lf-timeline.js
  document.documentElement.lfInitial.register("lf-timeline", drawTimeline);
})();
