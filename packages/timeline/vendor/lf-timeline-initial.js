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

  // browser/runtime/icon-paths.js
  var SEND = '<path d="M8 13V3M4 7l4-4 4 4"/>';
  var ICONS = {
    activity: '<circle cx="8" cy="8" r="3" fill="currentColor" stroke="none"/>',
    add: '<path d="M8 3v10M3 8h10"/>',
    change: '<path d="M3 5.25h8.5M9.25 3l2.25 2.25L9.25 7.5M13 10.75H4.5M6.75 8.5 4.5 10.75 6.75 13"/>',
    check: '<path d="m3 8.25 3.15 3.15L13 4.75"/>',
    comment: '<path d="M3 3.25h10v7H7.25L4 12.75v-2H3z"/>',
    // The common copy glyph: the front sheet at the bottom right. Mirrored, with the front
    // sheet at the bottom left, two squares read as a window's Restore button.
    copy: '<rect x="6" y="6" width="7" height="7" rx="1.25"/><path d="M10 6V4.25C10 3.56 9.44 3 8.75 3h-4.5C3.56 3 3 3.56 3 4.25v4.5C3 9.44 3.56 10 4.25 10H6"/>',
    cross: '<path d="m4 4 8 8M12 4l-8 8"/>',
    dot: '<circle cx="8" cy="8" r="1.5" fill="currentColor" stroke="none"/>',
    down: '<path d="m4 6.25 4 4 4-4"/>',
    edit: '<path d="m3.25 10.75-.5 2.5 2.5-.5 6.9-6.9-2-2zM9.25 4.75l2 2"/>',
    expand: '<path d="M9.5 3H13v3.5M13 3 9.25 6.75M6.5 13H3V9.5M3 13l3.75-3.75"/>',
    collapse: '<path d="M13 3 9.25 6.75M9.25 3.25v3.5h3.5M3 13l3.75-3.75M3.25 9.25h3.5v3.5"/>',
    fit: '<path d="M6 3H3v3M10 3h3v3M3 10v3h3M13 10v3h-3"/>',
    fold: '<path d="M3 8h10M5.5 2.75 8 5.25l2.5-2.5M5.5 13.25 8 10.75l2.5 2.5"/>',
    more: '<circle cx="3.5" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="8" cy="8" r="1" fill="currentColor" stroke="none"/><circle cx="12.5" cy="8" r="1" fill="currentColor" stroke="none"/>',
    // What waits on the user, an inbox's tray: the On me mark. The question mark stays
    // with an obligation and with help (`?`).
    inbox: '<path d="M2.75 9.25h2.9l1 1.6h2.7l1-1.6h2.9M2.75 9.25 4.4 4h7.2l1.65 5.25v2.75H2.75z"/>',
    link: '<path d="M6.67 8.67a3.33 3.33 0 0 0 5.03.36l2-2a3.33 3.33 0 0 0-4.71-4.71l-1.15 1.14M9.33 7.33a3.33 3.33 0 0 0-5.03-.36l-2 2a3.33 3.33 0 0 0 4.71 4.71l1.14-1.14"/>',
    // A map's locate mark, for the way from a thread to where its words stand.
    locate: '<circle cx="8" cy="8" r="4"/><path d="M8 1.75v2.5M8 11.75v2.5M1.75 8h2.5M11.75 8h2.5"/><circle cx="8" cy="8" r="1" fill="currentColor" stroke="none"/>',
    microphone: '<rect x="6" y="2" width="4" height="7" rx="2"/><path d="M4 7.5v.75a4 4 0 0 0 8 0V7.5M8 12.25V14M6 14h4"/><path class="lf-mic-slash" d="M2.5 2.5l11 11"/>',
    next: '<path d="m6 3.5 4.5 4.5L6 12.5"/>',
    pause: '<path d="M5 3v10M11 3v10"/>',
    play: '<path d="m5 3 7 5-7 5z"/>',
    previous: '<path d="m10 3.5-4.5 4.5 4.5 4.5"/>',
    // How a list is arranged: its lines, shortening, the choosers' symbol.
    arrange: '<path d="M3 4.5h10M3 8h7M3 11.5h4"/>',
    all: '<path d="M3 4h6M3 8h6M3 12h6M12 8v4M10 10h4"/>',
    pickup: '<path d="M8 2.75v6.5M5.5 6.75 8 9.25l2.5-2.5M3 10.5v2h10v-2"/>',
    question: '<path d="M5.6 6.1a2.5 2.5 0 1 1 3.1 2.45c-.7.2-.7.8-.7 1.2"/><circle cx="8" cy="12.35" r=".7" fill="currentColor" stroke="none"/>',
    reaction: '<circle cx="6.5" cy="8.25" r="4.25"/><circle cx="5" cy="7.25" r=".55" fill="currentColor" stroke="none"/><circle cx="8" cy="7.25" r=".55" fill="currentColor" stroke="none"/><path d="M4.75 9.25c.5.75 1.08 1.1 1.75 1.1s1.25-.35 1.75-1.1M11 4h4M13 2v4"/>',
    retry: '<path d="M12.5 5.25V2.75M12.5 2.75H10M12.35 3.1A5 5 0 1 0 13 9"/>',
    save: '<path d="M3 4.25A1.25 1.25 0 0 1 4.25 3h6.5L13 5.25v6.5A1.25 1.25 0 0 1 11.75 13h-7.5A1.25 1.25 0 0 1 3 11.75zM5.5 3v2.5h4V3"/>',
    search: '<circle cx="7" cy="7" r="3.75"/><path d="m10 10 3 3"/>',
    send: SEND,
    sent: SEND,
    start: '<path d="M3.5 3v10M12.5 3.5 6 8l6.5 4.5z"/>',
    subtract: '<path d="M3 8h10"/>',
    unfold: '<path d="M3 8h10M5.5 5.25 8 2.75l2.5 2.5M5.5 10.75 8 13.25l2.5-2.5"/>',
    undo: '<path d="M5.25 4.25 2.75 6.5 5.25 8.75M3 6.5h5.5a4 4 0 0 1 4 4v1"/>',
    up: '<path d="m4 9.75 4-4 4 4"/>',
    waiting: '<circle cx="8" cy="8" r="5"/><path d="M8 5v3.25l2 1.25"/>'
  };
  var iconMarkup = (icon) => {
    const markup = ICONS[icon];
    if (!markup) throw new TypeError(`Unknown Leaf icon: ${icon}`);
    return markup;
  };

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
        drawing.previous = tools.offerActionElement(
          node,
          "symbol",
          "lf-timeline-previous",
          "Previous"
        );
    };
    const nextRef = (node) => {
      if (node)
        drawing.next = tools.offerActionElement(
          node,
          "symbol",
          "lf-timeline-next",
          "Next"
        );
    };
    const icon = (name) => html`<svg
      viewBox="0 0 16 16"
      focusable="false"
      aria-hidden="true"
      class="lf-action-icon"
      data-lf-icon=${name}
      .innerHTML=${iconMarkup(name)}
    ></svg>`;
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
            ${icon("previous")}
          </button>
          <button
            ${ref(nextRef)}
            aria-disabled=${current < model.steps.length - 1 ? nothing : "true"}
          >
            ${icon("next")}
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
