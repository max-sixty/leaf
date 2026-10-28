(() => {
  // leaf-initial-lit:lit
  var { AsyncDirective, AsyncReplaceDirective, CSSResult, Directive, LitElement, PartType, ReactiveElement, TemplateResultType, UnsafeHTMLDirective, UntilDirective, _$LE, _$LH, adoptStyles, asyncAppend, asyncReplace, cache, choose, classMap, clearPart, createRef, css, customElement, defaultConverter, directive, eventOptions, getCommittedValue, getCompatibleStyle, getDirectiveClass, guard, html, ifDefined, insertPart, isCompiledTemplateResult, isDirectiveResult, isPrimitive, isServer, isSingleExpression, isTemplateResult, join, keyed, literal, live, map, mathml, noChange, notEqual, nothing, property, query, queryAll, queryAssignedElements, queryAssignedNodes, queryAsync, range, ref, removePart, render, repeat, setChildPartValue, setCommittedValue, standardProperty, state, staticHtml, staticMathml, staticSvg, styleMap, supportsAdoptingStyleSheets, svg, templateContent, unsafeCSS, unsafeHTML, unsafeMathML, unsafeSVG, unsafeStatic, until, when, withStatic } = document.documentElement.lfInitial.lit;

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

  // packages/default/widgets/shot-view.js
  var SHOT_VIEWS = {
    flip: "Slider",
    compare: "Pair",
    pixels: "Pixels"
  };
  var nextOptionsId = 0;
  var differenceMark = (region, reading) => html`<span
    data-lf-shot-mark=${region.kind}
    style=${styleMap({
    "--lf-shot-x": `${100 * region.x / reading.width}%`,
    "--lf-shot-y": `${100 * region.y / reading.height}%`,
    "--lf-shot-w": `${100 * region.width / reading.width}%`,
    "--lf-shot-h": `${100 * region.height / reading.height}%`
  })}
  ></span>`;
  function shotAllocation(host, stage) {
    const style = getComputedStyle(stage);
    const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
    return {
      available: stage.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
      availableHeight: getComputedStyle(host).getPropertyValue("--lf-holds-height").trim() === "1" ? stage.clientHeight - padding : void 0,
      screenHeight: document.documentElement.clientHeight - stage.previousElementSibling.offsetHeight - padding
    };
  }
  function fitShotGeometry({
    available,
    availableHeight,
    screenHeight,
    labelHeight,
    sourceWidth,
    sourceHeight,
    focus = void 0,
    full = false,
    actual = false,
    view = "flip",
    gap
  }) {
    const crop = Boolean(focus && !full);
    if (!available || !(crop || sourceWidth && sourceHeight)) return null;
    const width = crop ? focus.width : sourceWidth;
    const height = crop ? focus.height : sourceHeight;
    const fit = (columns2, rows2, captions = 0, bound = availableHeight) => Math.max(
      0,
      Math.min(
        1,
        (available - columns2 * 2 - (columns2 - 1) * gap) / (columns2 * width),
        bound === void 0 ? Infinity : (bound - rows2 * (captions + 2) - (rows2 - 1) * gap) / (rows2 * height)
      )
    );
    const side = fit(2, 1);
    const stack = fit(1, 2, labelHeight, availableHeight ?? screenHeight);
    const layout = side >= stack ? "side" : "stack";
    const pairScale = layout === "side" ? side : stack;
    const fitScale = view === "compare" ? pairScale : fit(1, 1);
    const scale = actual ? 1 : fitScale;
    const columns = view === "compare" && layout === "side" ? 2 : 1;
    const rows = view === "compare" && layout === "stack" ? 2 : 1;
    const captionHeight = rows === 2 ? labelHeight : 0;
    const viewportWidth = Math.min(
      width * scale,
      (available - columns * 2 - (columns - 1) * gap) / columns
    );
    const viewportHeight = availableHeight === void 0 ? height * (view === "compare" ? pairScale : scale) : Math.min(
      height * scale,
      Math.max(
        0,
        (availableHeight - rows * (captionHeight + 2) - (rows - 1) * gap) / rows
      )
    );
    return {
      layout,
      scale,
      fitScale,
      crop,
      focus: Boolean(focus),
      vars: {
        "frame-width": width * scale,
        "frame-height": height * scale,
        "viewport-width": viewportWidth,
        "viewport-height": viewportHeight,
        "source-width": (sourceWidth || focus.x + focus.width) * scale,
        "source-height": (sourceHeight || focus.y + focus.height) * scale,
        "crop-x": crop ? focus.x * scale : 0,
        "crop-y": crop ? focus.y * scale : 0,
        "focus-x": focus ? focus.x * scale : 0,
        "focus-y": focus ? focus.y * scale : 0,
        "focus-width": focus ? focus.width * scale : 0,
        "focus-height": focus ? focus.height * scale : 0
      }
    };
  }
  function applyShotGeometry(host, geometry, keeps) {
    for (const [name, value] of Object.entries(geometry.vars))
      host.style.setProperty(`--lf-shot-${name}`, `${Math.round(value * 64) / 64}px`);
    keeps(host, "data-lf-shot-layout", geometry.layout);
    keeps(host, "data-lf-shot-crop", geometry.crop);
    keeps(host, "data-lf-shot-focus", geometry.focus);
  }
  var ShotView = class {
    view = "flip";
    position = 50;
    actual = false;
    full = false;
    outlines = false;
    metadata = {};
    reading = null;
    description = null;
    geometry = null;
    images = [];
    pixels = false;
    pixelUrl = null;
    frames = [];
    viewports = [];
    /** @type {((view: string) => void) | undefined} */
    chooseView;
    /** @type {((scale: string) => void) | undefined} */
    chooseScale;
    /** @type {((event: MouseEvent) => void) | undefined} */
    toggleOptions;
    /** @type {(() => void) | undefined} */
    toggleOutlines;
    /** @type {((event: Event) => void) | undefined} */
    changeFull;
    constructor(host, tools) {
      this.host = host;
      this.tools = tools;
      this.choiceRef = (node) => node && tools.offerActionElement(node, "word");
      this.outlineRef = (node) => node && tools.offerActionElement(node, "word", "lf-shot-outline");
      this.scaleRef = (node) => {
        if (node)
          this.scaleTrigger = tools.offerActionElement(node, "symbol", "lf-shot-scale");
      };
      let optionsId;
      do
        optionsId = `lf-shot-options-${++nextOptionsId}`;
      while (document.getElementById(optionsId));
      this.optionsId = optionsId;
      host.replaceChildren();
    }
    render() {
      const { host, tools, optionsId } = this;
      const { offerElement, generatedElement, keeps } = tools;
      const offered = (cls, save = void 0) => ref((node) => {
        if (!node) return;
        offerElement(node, cls);
        save?.(node);
      });
      const box = (save = void 0) => ref((node) => {
        if (!node) return;
        generatedElement(node, { says: false });
        save?.(node);
      });
      const caption = (state2, frame2 = false) => {
        const label = (this.metadata.labels ?? { before: "Before", after: "After" })[state2];
        const stacked = this.view === "compare" && this.geometry?.layout === "stack";
        return html`<span
        ${ref(
          (node) => node && generatedElement(offerElement(node, "lf-shotcap lf-label"), {
            says: frame2 === stacked || "echo"
          })
        )}
        data-lf-state=${state2}
        title=${label}
        aria-label=${frame2 ? nothing : `${label} \u2014 ${host.getAttribute("alt")}`}
        ?data-lf-shot-hidden=${!frame2 && this.view === "flip" && (state2 === "before" ? this.position === 0 : this.position === 100)}
        >${label}</span
      >`;
      };
      const choices = (label, values, selected, choose2, cls = "lf-shot-views") => html`<div ${offered(cls)} role="group" aria-label=${label}>
        ${Object.entries(values).map(
        ([value, text]) => html`<button
              ${ref(this.choiceRef)}
              type="button"
              aria-pressed=${String(value === selected)}
              ?disabled=${value === "pixels" && !this.reading}
              title=${value === "fit" ? this.geometry ? `Fit \xB7 ${Math.round(this.geometry.fitScale * 100)}%` : nothing : value === "actual" ? this.metadata.pixelRatio ? "Captured CSS size" : "One image pixel per CSS pixel" : nothing}
              @click=${() => choose2?.(value)}
            >
              ${text}
            </button>`
      )}
      </div>`;
      const frame = (state2, index) => {
        const alt = host.getAttribute("alt");
        const label = (this.metadata.labels ?? { before: "Before", after: "After" })[state2];
        const pair = this.view === "compare";
        const reading = this.reading;
        const regions = reading?.regions.filter((region) => region.side === state2).map((region) => differenceMark(region, reading));
        return html`<div
        class="lf-shotframe lf-media-frame"
        data-lf-state=${state2}
        ${box((node) => this.frames[index] = node)}
      >
        <div class="lf-shot-frame-label" data-lf-state=${state2} ${box()}>
          ${caption(state2, true)}
        </div>
        <div
          class="lf-shotviewport"
          role="region"
          aria-label=${`${label} \u2014 ${alt}`}
          ${box((node) => this.viewports[index] = node)}
        >
          <a
            class="lf-shotimage lf-shot-open"
            data-lf-shot-open=${state2}
            data-lf-media-caption=${`${state2}: ${alt}`}
            aria-label=${`Open ${state2} image \u2014 ${alt}`}
            href=${pair ? this.images[index]?.src || nothing : nothing}
            tabindex=${pair ? nothing : "-1"}
            title=${pair ? `Open ${state2} image` : nothing}
            ${box()}
            ><div class="lf-shotplane" ${box()}>
              <img
                crossorigin="anonymous"
                alt=${`${state2}: ${alt}`}
                src=${this.images[index]?.getAttribute("src") || nothing}
              />
              ${reading ? html`<div ${offered("lf-shotdiff")} aria-hidden="true">
                      ${regions}
                    </div>` : nothing}
            </div></a
          >
        </div>
      </div>`;
      };
      const pixelStyle = styleMap({
        "--lf-shot-pixels": this.pixelUrl ? `url("${this.pixelUrl}")` : void 0
      });
      keeps(host, "data-lf-shot-mode", this.view);
      keeps(host, "data-lf-shot-outlines", this.outlines);
      return html`
      <div ${offered("lf-shot-toolbar lf-ui", (node) => this.toolbar = node)}>
        ${caption("before")}
        <div ${offered("lf-shot-actions")}>
          ${choices("Comparison view", SHOT_VIEWS, this.view, this.chooseView)}
          <div ${offered("lf-shot-tools")}>
            <button
              ${ref(this.scaleRef)}
              type="button"
              aria-label="Image options"
              popovertarget=${optionsId}
              @click=${this.toggleOptions ?? null}
            >
              <svg
                viewBox="0 0 16 16"
                focusable="false"
                aria-hidden="true"
                class="lf-action-icon"
                data-lf-icon="more"
                .innerHTML=${this.tools.iconMarkup("more")}
              ></svg>
            </button>
            <button
              ${ref(this.outlineRef)}
              type="button"
              aria-label="Outline changes"
              title="Outline changes"
              aria-pressed=${String(this.outlines)}
              aria-description=${this.description ?? nothing}
              ?disabled=${this.view === "pixels" || !this.reading?.regions.length}
              @click=${this.toggleOutlines ?? null}
            >
              Outline
            </button>
            <div
              ${offered("lf-shotoptions", (node) => this.options = node)}
              id=${optionsId}
              popover="auto"
              role="group"
              aria-label="Image options"
            >
              ${choices(
        "Image scale",
        { fit: "Fit", actual: "100%" },
        this.actual ? "actual" : "fit",
        this.chooseScale,
        "lf-shot-scale-options"
      )}
              <label ${offered("choice lf-shotchoice")} ?hidden=${!this.metadata.focus}>
                <input
                  ${offered("")}
                  type="checkbox"
                  .checked=${this.full}
                  @change=${this.changeFull ?? null}
                />
                <span ${offered("")}>Full frame</span>
              </label>
              <div ${offered("lf-shot-pixel-key")}>
                <span ${offered("lf-shot-key-swatch")} aria-hidden="true"></span>
                <span ${offered("")}>Changed pixels</span>
              </div>
            </div>
          </div>
        </div>
        ${caption("after")}
      </div>
      <div
        class="lf-shotstage"
        tabindex="0"
        role="region"
        aria-label=${`Screenshot comparison \u2014 ${host.getAttribute("alt")}`}
        ${box((node) => this.stage = node)}
      >
        <div class="lf-shotcanvas" ${box((node) => this.canvas = node)}>
          ${["before", "after"].map(frame)}
          ${this.pixels ? html`<div
                  class="lf-shotpixels lf-shotimage lf-media-frame"
                  role="img"
                  aria-label=${`changed pixels: ${host.getAttribute("alt")}`}
                  ${box()}
                >
                  <div class="lf-shotplane" ${box()}>
                    <img alt="" src=${this.images[1]?.src || nothing} />
                    <span class="lf-shot-pixel-mask" style=${pixelStyle}></span>
                  </div>
                </div>` : nothing}
        </div>
      </div>
    `;
    }
    fit() {
      const { host, stage, metadata, images, frames } = this;
      const allocation = shotAllocation(host, stage);
      if (allocation.available <= 0) return null;
      const ratio = metadata.pixelRatio ?? 1;
      const geometry = fitShotGeometry({
        ...allocation,
        labelHeight: parseFloat(getComputedStyle(frames[0].firstElementChild).blockSize),
        sourceWidth: images[0]?.naturalWidth / ratio || Number(host.dataset.lfMediaWidth) / ratio || metadata.captureWidth,
        sourceHeight: Math.max(0, ...images.map((image) => image.naturalHeight)) / ratio || Number(host.dataset.lfMediaHeight) / ratio,
        focus: metadata.focus,
        full: this.full,
        actual: this.actual,
        view: this.view,
        gap: parseFloat(getComputedStyle(host).getPropertyValue("--lf-shot-gap"))
      });
      if (geometry) {
        this.geometry = geometry;
        applyShotGeometry(host, geometry, this.tools.keeps);
      }
      return geometry;
    }
  };

  // packages/default/initial/lf-shot.js
  document.documentElement.lfInitial.register("lf-shot", (host, tools) => {
    const view = new ShotView(host, { ...tools, iconMarkup });
    render(view.render(), host, { host });
    view.fit();
    return view;
  });
})();
