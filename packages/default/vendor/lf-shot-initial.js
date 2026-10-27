(() => {
  // leaf-initial-lit:lit
  var { AsyncDirective, AsyncReplaceDirective, CSSResult, Directive, LitElement, PartType, ReactiveElement, TemplateResultType, UnsafeHTMLDirective, UntilDirective, _$LE, _$LH, adoptStyles, asyncAppend, asyncReplace, cache, choose, classMap, clearPart, createRef, css, customElement, defaultConverter, directive, eventOptions, getCommittedValue, getCompatibleStyle, getDirectiveClass, guard, html, ifDefined, insertPart, isCompiledTemplateResult, isDirectiveResult, isPrimitive, isServer, isSingleExpression, isTemplateResult, join, keyed, literal, live, map, mathml, noChange, notEqual, nothing, property, query, queryAll, queryAssignedElements, queryAssignedNodes, queryAsync, range, ref, removePart, render, repeat, setChildPartValue, setCommittedValue, standardProperty, state, staticHtml, staticMathml, staticSvg, styleMap, supportsAdoptingStyleSheets, svg, templateContent, unsafeCSS, unsafeHTML, unsafeMathML, unsafeSVG, unsafeStatic, until, when, withStatic } = document.documentElement.lfInitial.lit;

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
      this.paint();
      if (this.fit()) this.paint();
    }
    paint() {
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
      render(
        html`
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
                …
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
                <label
                  ${offered("choice lf-shotchoice")}
                  ?hidden=${!this.metadata.focus}
                >
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
      `,
        host
      );
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
  document.documentElement.lfInitial.register(
    "lf-shot",
    (host, tools) => new ShotView(host, tools)
  );
})();
