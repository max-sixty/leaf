/* The screenshot's retained Lit drawing and source-coordinate geometry. Initial
 * delivery and live behavior use the same template instance. Images load before
 * their sources enter the drawing; frames and controls survive capture revisions.
 * ShotView owns inspection state, retained nodes and fitting from delivery onward.
 * Live behavior fills the same owner with decoded captures and difference readings. */
import { html, nothing, ref, styleMap } from "/vendor/lit.js";
export const SHOT_VIEWS = {
  flip: "Slider",
  compare: "Pair",
  pixels: "Pixels",
};
let nextOptionsId = 0;

const differenceMark = (region, reading) =>
  html`<span
    data-lf-shot-mark=${region.kind}
    style=${styleMap({
      "--lf-shot-x": `${(100 * region.x) / reading.width}%`,
      "--lf-shot-y": `${(100 * region.y) / reading.height}%`,
      "--lf-shot-w": `${(100 * region.width) / reading.width}%`,
      "--lf-shot-h": `${(100 * region.height) / reading.height}%`,
    })}
  ></span>`;

// Fit uses the content box: the scrollport's padding keeps the image shadow visible.
// In flow nothing bounds the stage's height, so a stacked Pair takes the screen's room
// below the toolbar as its bound: the reader compares both frames in one view.
function shotAllocation(host, stage) {
  const style = getComputedStyle(stage);
  const padding = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
  return {
    available:
      stage.clientWidth -
      parseFloat(style.paddingLeft) -
      parseFloat(style.paddingRight),
    availableHeight:
      getComputedStyle(host).getPropertyValue("--lf-holds-height").trim() === "1"
        ? stage.clientHeight - padding
        : undefined,
    screenHeight:
      document.documentElement.clientHeight -
      stage.previousElementSibling.offsetHeight -
      padding,
  };
}

function fitShotGeometry({
  available,
  availableHeight,
  screenHeight,
  labelHeight,
  sourceWidth,
  sourceHeight,
  focus = undefined,
  full = false,
  actual = false,
  view = "flip",
  gap,
}) {
  const crop = Boolean(focus && !full);
  if (!available || !(crop || (sourceWidth && sourceHeight))) return null;
  const width = crop ? focus.width : sourceWidth;
  const height = crop ? focus.height : sourceHeight;
  const fit = (columns, rows, captions = 0, bound = availableHeight) =>
    Math.max(
      0,
      Math.min(
        1,
        (available - columns * 2 - (columns - 1) * gap) / (columns * width),
        bound === undefined
          ? Infinity
          : (bound - rows * (captions + 2) - (rows - 1) * gap) / (rows * height),
      ),
    );
  // Pair takes whichever arrangement draws the captures larger, so short wide
  // captures stack and tall narrow ones sit side by side. Frames side by side share
  // rows, so in flow the page's scrolling keeps them aligned; stacked frames must
  // both fit the room.
  const side = fit(2, 1);
  const stack = fit(1, 2, labelHeight, availableHeight ?? screenHeight);
  const layout = side >= stack ? "side" : "stack";
  const pairScale = layout === "side" ? side : stack;
  const fitScale = view === "compare" ? pairScale : fit(1, 1);
  const scale = actual ? 1 : fitScale;
  // An image's scale and its viewing window are different dimensions. At actual
  // size each window uses its share of the allocation while both remain visible.
  const columns = view === "compare" && layout === "side" ? 2 : 1;
  const rows = view === "compare" && layout === "stack" ? 2 : 1;
  const captionHeight = rows === 2 ? labelHeight : 0;
  const viewportWidth = Math.min(
    width * scale,
    (available - columns * 2 - (columns - 1) * gap) / columns,
  );
  const viewportHeight =
    availableHeight === undefined
      ? height * (view === "compare" ? pairScale : scale)
      : Math.min(
          height * scale,
          Math.max(
            0,
            (availableHeight - rows * (captionHeight + 2) - (rows - 1) * gap) / rows,
          ),
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
      "focus-height": focus ? focus.height * scale : 0,
    },
  };
}

function applyShotGeometry(host, geometry, keeps) {
  for (const [name, value] of Object.entries(geometry.vars))
    host.style.setProperty(`--lf-shot-${name}`, `${Math.round(value * 64) / 64}px`);
  keeps(host, "data-lf-shot-layout", geometry.layout);
  keeps(host, "data-lf-shot-crop", geometry.crop);
  keeps(host, "data-lf-shot-focus", geometry.focus);
}

// The third-party comparison owns its frame slots; its shell is generated page
// drawing, so paper prints its images while dropping the toolbar's offered chrome.
export const shotBox = (tag, cls) =>
  document.documentElement.lfInitial.generatedElement(
    Object.assign(document.createElement(tag), { className: cls }),
    { says: false },
  );

export class ShotView {
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
    this.outlineRef = (node) =>
      node && tools.offerActionElement(node, "word", "lf-shot-outline");
    this.scaleRef = (node) => {
      if (node)
        this.scaleTrigger = tools.offerActionElement(
          node,
          "symbol",
          "lf-shot-scale",
          "Image options",
          { action: "more" },
        );
    };
    let optionsId;
    do optionsId = `lf-shot-options-${++nextOptionsId}`;
    while (document.getElementById(optionsId));
    this.optionsId = optionsId;
    host.replaceChildren();
  }

  render() {
    const { host, tools, optionsId } = this;
    const { offerElement, generatedElement, keeps } = tools;
    const offered = (cls, save = undefined) =>
      ref((node) => {
        if (!node) return;
        offerElement(node, cls);
        save?.(node);
      });
    const box = (save = undefined) =>
      ref((node) => {
        if (!node) return;
        generatedElement(node, { says: false });
        save?.(node);
      });
    const caption = (state, frame = false) => {
      const label = (this.metadata.labels ?? { before: "Before", after: "After" })[
        state
      ];
      const stacked = this.view === "compare" && this.geometry?.layout === "stack";
      return html`<span
        ${ref(
          (node) =>
            node &&
            generatedElement(offerElement(node, "lf-shotcap lf-label"), {
              says: frame === stacked || "echo",
            }),
        )}
        data-lf-state=${state}
        title=${label}
        aria-label=${frame ? nothing : `${label} — ${host.getAttribute("alt")}`}
        ?data-lf-shot-hidden=${
          !frame &&
          this.view === "flip" &&
          (state === "before" ? this.position === 0 : this.position === 100)
        }
        >${label}</span
      >`;
    };
    const choices = (label, values, selected, choose, cls = "lf-shot-views") =>
      html`<div ${offered(cls)} role="group" aria-label=${label}>
        ${Object.entries(values).map(
          ([value, text]) =>
            html`<button
              ${ref(this.choiceRef)}
              type="button"
              aria-pressed=${String(value === selected)}
              ?disabled=${value === "pixels" && !this.reading}
              title=${
                value === "fit"
                  ? this.geometry
                    ? `Fit · ${Math.round(this.geometry.fitScale * 100)}%`
                    : nothing
                  : value === "actual"
                    ? this.metadata.pixelRatio
                      ? "Captured CSS size"
                      : "One image pixel per CSS pixel"
                    : nothing
              }
              @click=${() => choose?.(value)}
            >
              ${text}
            </button>`,
        )}
      </div>`;
    const frame = (state, index) => {
      const alt = host.getAttribute("alt");
      const label = (this.metadata.labels ?? { before: "Before", after: "After" })[
        state
      ];
      const pair = this.view === "compare";
      const reading = this.reading;
      const regions = reading?.regions
        .filter((region) => region.side === state)
        .map((region) => differenceMark(region, reading));
      return html`<div
        class="lf-shotframe lf-media-frame"
        data-lf-state=${state}
        ${box((node) => (this.frames[index] = node))}
      >
        <div class="lf-shot-frame-label" data-lf-state=${state} ${box()}>
          ${caption(state, true)}
        </div>
        <div
          class="lf-shotviewport"
          role="region"
          aria-label=${`${label} — ${alt}`}
          ${box((node) => (this.viewports[index] = node))}
        >
          <a
            class="lf-shotimage lf-shot-open"
            data-lf-shot-open=${state}
            data-lf-media-caption=${`${state}: ${alt}`}
            aria-label=${`Open ${state} image — ${alt}`}
            href=${pair ? this.images[index]?.src || nothing : nothing}
            tabindex=${pair ? nothing : "-1"}
            title=${pair ? `Open ${state} image` : nothing}
            ${box()}
            ><div class="lf-shotplane" ${box()}>
              <img
                crossorigin="anonymous"
                alt=${`${state}: ${alt}`}
                src=${this.images[index]?.getAttribute("src") || nothing}
              />
              ${
                reading
                  ? html`<div ${offered("lf-shotdiff")} aria-hidden="true">
                      ${regions}
                    </div>`
                  : nothing
              }
            </div></a
          >
        </div>
      </div>`;
    };

    const pixelStyle = styleMap({
      "--lf-shot-pixels": this.pixelUrl ? `url("${this.pixelUrl}")` : undefined,
    });
    keeps(host, "data-lf-shot-mode", this.view);
    keeps(host, "data-lf-shot-outlines", this.outlines);
    return html`
      <div ${offered("lf-shot-toolbar lf-ui", (node) => (this.toolbar = node))}>
        ${caption("before")}
        <div ${offered("lf-shot-actions")}>
          ${choices("Comparison view", SHOT_VIEWS, this.view, this.chooseView)}
          <div ${offered("lf-shot-tools")}>
            <button
              ${ref(this.scaleRef)}
              type="button"
              popovertarget=${optionsId}
              @click=${this.toggleOptions ?? null}
            ></button>
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
              ${offered("lf-shotoptions", (node) => (this.options = node))}
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
                "lf-shot-scale-options",
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
        aria-label=${`Screenshot comparison — ${host.getAttribute("alt")}`}
        ${box((node) => (this.stage = node))}
      >
        <div class="lf-shotcanvas" ${box((node) => (this.canvas = node))}>
          ${["before", "after"].map(frame)}
          ${
            this.pixels
              ? html`<div
                  class="lf-shotpixels lf-shotimage lf-media-frame"
                  role="img"
                  aria-label=${`changed pixels: ${host.getAttribute("alt")}`}
                  ${box()}
                >
                  <div class="lf-shotplane" ${box()}>
                    <img alt="" src=${this.images[1]?.src || nothing} />
                    <span class="lf-shot-pixel-mask" style=${pixelStyle}></span>
                  </div>
                </div>`
              : nothing
          }
        </div>
      </div>
    `;
  }

  fit() {
    const { host, stage, metadata, images, frames } = this;
    const allocation = shotAllocation(host, stage);
    // Hidden cases retain their last geometry until shown.
    if (allocation.available <= 0) return null;
    const ratio = metadata.pixelRatio ?? 1;
    const geometry = fitShotGeometry({
      ...allocation,
      labelHeight: parseFloat(getComputedStyle(frames[0].firstElementChild).blockSize),
      sourceWidth:
        images[0]?.naturalWidth / ratio ||
        Number(host.dataset.lfMediaWidth) / ratio ||
        metadata.captureWidth,
      sourceHeight:
        Math.max(0, ...images.map((image) => image.naturalHeight)) / ratio ||
        Number(host.dataset.lfMediaHeight) / ratio,
      focus: metadata.focus,
      full: this.full,
      actual: this.actual,
      view: this.view,
      gap: parseFloat(getComputedStyle(host).getPropertyValue("--lf-shot-gap")),
    });
    if (geometry) {
      this.geometry = geometry;
      applyShotGeometry(host, geometry, this.tools.keeps);
    }
    return geometry;
  }
}
