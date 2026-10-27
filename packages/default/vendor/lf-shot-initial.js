(() => {
  // packages/default/widgets/shot-view.js
  var SHOT_VIEWS = {
    flip: "Slider",
    compare: "Pair",
    pixels: "Pixels"
  };
  var nextOptionsId = 0;
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
    const stacked = host.dataset.lfShotMode === "compare" && geometry.layout === "stack";
    for (const caption of host.querySelectorAll(".lf-shotcap"))
      document.documentElement.lfInitial.generatedElement(caption, {
        says: caption.parentElement.classList.contains("lf-shot-frame-label") === stacked || "echo"
      });
  }
  var shotBox = (tag, cls) => document.documentElement.lfInitial.generatedElement(
    Object.assign(document.createElement(tag), { className: cls }),
    { says: false }
  );
  function drawShot(host, { offer, offerAction, generatedElement, keeps }) {
    const buttons = (label, values, selected) => {
      const group = offer("div", "lf-shot-views");
      group.role = "group";
      group.ariaLabel = label;
      const choices = /* @__PURE__ */ new Map();
      for (const [value, text] of Object.entries(values)) {
        const button = offerAction("word", "", text);
        button.setAttribute("aria-pressed", String(value === selected));
        choices.set(value, button);
        group.append(button);
      }
      return { group, choices };
    };
    const checkbox = (text) => {
      const label = offer("label", "choice lf-shotchoice");
      const input = offer("input", "", void 0, "checkbox");
      const words = offer("span", "", text);
      label.append(input, words);
      return { label, input };
    };
    const toolbar = offer("div", "lf-shot-toolbar lf-ui");
    const actions = offer("div", "lf-shot-actions");
    const views = buttons("Comparison view", SHOT_VIEWS, "flip");
    views.choices.get("pixels").disabled = true;
    const tools = offer("div", "lf-shot-tools");
    const scaleTrigger = offerAction("symbol", "lf-shot-scale", "Image options");
    scaleTrigger.textContent = "\u2026";
    const options = offer("div", "lf-shotoptions");
    options.setAttribute("popover", "auto");
    options.role = "group";
    options.ariaLabel = "Image options";
    do
      options.id = `lf-shot-options-${++nextOptionsId}`;
    while (document.getElementById(options.id));
    scaleTrigger.setAttribute("aria-controls", options.id);
    scaleTrigger.setAttribute("popovertarget", options.id);
    scaleTrigger.setAttribute("aria-expanded", "false");
    const scale = buttons("Image scale", { fit: "Fit", actual: "100%" }, "fit");
    scale.group.className = "lf-shot-scale-options";
    const outlines = offerAction("word", "lf-shot-outline", "Outline");
    outlines.ariaLabel = "Outline changes";
    outlines.title = "Outline changes";
    outlines.disabled = true;
    outlines.setAttribute("aria-pressed", "false");
    const full = checkbox("Full frame");
    full.label.hidden = true;
    const key = offer("div", "lf-shot-pixel-key");
    const swatch = offer("span", "lf-shot-key-swatch");
    swatch.ariaHidden = "true";
    key.append(swatch, offer("span", "", "Changed pixels"));
    options.append(scale.group, full.label, key);
    tools.append(scaleTrigger, outlines, options);
    actions.append(views.group, tools);
    toolbar.append(actions);
    const stage = shotBox("div", "lf-shotstage");
    stage.tabIndex = 0;
    stage.role = "region";
    stage.ariaLabel = `Screenshot comparison \u2014 ${host.getAttribute("alt")}`;
    const canvas = shotBox("div", "lf-shotcanvas");
    stage.append(canvas);
    const frames = [], viewports = [], shots = [], captions = /* @__PURE__ */ new Map(), frameCaptions = /* @__PURE__ */ new Map(), openers = /* @__PURE__ */ new Map();
    for (const state of ["before", "after"]) {
      const frame = shotBox("div", "lf-shotframe lf-media-frame");
      frame.dataset.lfState = state;
      const caption = generatedElement(
        offer("span", "lf-shotcap lf-label", state === "before" ? "Before" : "After"),
        { says: true }
      );
      caption.dataset.lfState = state;
      const heading = shotBox("div", "lf-shot-frame-label");
      heading.dataset.lfState = state;
      const frameCaption = offer("span", "lf-shotcap lf-label", caption.textContent);
      frameCaption.dataset.lfState = state;
      heading.append(frameCaption);
      frameCaptions.set(state, frameCaption);
      if (state === "before") toolbar.prepend(caption);
      else toolbar.append(caption);
      const viewport = shotBox("div", "lf-shotviewport");
      viewport.role = "region";
      viewport.ariaLabel = `${state}: ${host.getAttribute("alt")}`;
      const imageBox = shotBox("a", "lf-shotimage lf-shot-open");
      imageBox.dataset.lfShotOpen = state;
      imageBox.tabIndex = -1;
      const plane = shotBox("div", "lf-shotplane");
      const image = document.createElement("img");
      image.crossOrigin = "anonymous";
      image.alt = `${state}: ${host.getAttribute("alt")}`;
      shots.push(image);
      captions.set(state, caption);
      openers.set(state, imageBox);
      plane.append(image);
      imageBox.append(plane);
      viewport.append(imageBox);
      frame.append(heading, viewport);
      frames.push(frame);
      viewports.push(viewport);
      canvas.append(frame);
    }
    keeps(host, "data-lf-shot-mode", "flip");
    keeps(host, "data-lf-shot-outlines", false);
    host.append(toolbar, stage);
    const geometry = fitShotGeometry({
      ...shotAllocation(host, stage),
      labelHeight: parseFloat(getComputedStyle(frames[0].firstElementChild).blockSize),
      sourceWidth: Number(host.dataset.lfMediaWidth),
      sourceHeight: Number(host.dataset.lfMediaHeight),
      gap: parseFloat(getComputedStyle(host).getPropertyValue("--lf-shot-gap"))
    });
    if (geometry) {
      applyShotGeometry(host, geometry, keeps);
      scale.choices.get("fit").title = `Fit \xB7 ${Math.round(geometry.scale * 100)}%`;
    }
    return {
      toolbar,
      scaleTrigger,
      options,
      views,
      outlines,
      scale,
      full,
      stage,
      canvas,
      frames,
      viewports,
      shots,
      captions,
      frameCaptions,
      openers
    };
  }

  // packages/default/initial/lf-shot.js
  document.documentElement.lfInitial.register("lf-shot", drawShot);
})();
