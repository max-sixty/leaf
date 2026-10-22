(() => {
  // skills/leaf/packages/default/widgets/shot-view.js
  var SHOT_VIEWS = {
    compare: "Before & after",
    flip: "Slider",
    pixels: "Pixel difference"
  };
  var CONTROL = "lf-btn lf-quiet-action lf-compact-control";
  var nextOptionsId = 0;
  function fitShotGeometry({
    available,
    availableHeight,
    labelHeight,
    sourceWidth,
    sourceHeight,
    focus = void 0,
    full = false,
    actual = false,
    view = "compare",
    gap
  }) {
    const crop = Boolean(focus && !full);
    if (!available || !(crop || sourceWidth && sourceHeight)) return null;
    const width = crop ? focus.width : sourceWidth;
    const height = crop ? focus.height : sourceHeight;
    const fit = (columns2, rows2) => Math.max(
      0,
      Math.min(
        1,
        (available - columns2 * 2 - (columns2 - 1) * gap) / (columns2 * width),
        availableHeight === void 0 ? Infinity : (availableHeight - rows2 * (labelHeight + 2) - (rows2 - 1) * gap) / (rows2 * height)
      )
    );
    const side = fit(2, 1);
    const stack = fit(1, 2);
    const layout = availableHeight === void 0 ? width + gap + 4 <= available ? "side" : "stack" : side >= stack ? "side" : "stack";
    const pairScale = layout === "side" ? side : stack;
    const fitScale = view === "compare" ? pairScale : fit(1, 1);
    const scale = actual ? 1 : fitScale;
    const columns = view === "compare" && layout === "side" ? 2 : 1;
    const rows = view === "compare" && layout === "stack" ? 2 : 1;
    const viewportWidth = Math.min(
      width * scale,
      (available - columns * 2 - (columns - 1) * gap) / columns
    );
    const viewportHeight = availableHeight === void 0 ? height * (view === "compare" ? pairScale : scale) : Math.min(
      height * scale,
      Math.max(
        0,
        (availableHeight - rows * (labelHeight + 2) - (rows - 1) * gap) / rows
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
  function drawShot(host, { offer, keeps }) {
    const select = (label, values, selected) => {
      const input = offer("select", "lf-shotselect");
      input.name = label;
      input.ariaLabel = label;
      const options2 = /* @__PURE__ */ new Map();
      for (const [value, text] of Object.entries(values)) {
        const option = document.createElement("option");
        option.value = value;
        option.textContent = text;
        option.selected = value === selected;
        options2.set(value, option);
        input.append(option);
      }
      return { input, options: options2 };
    };
    const checkbox = (text) => {
      const label = offer("label", "choice lf-shotchoice");
      const input = offer("input", "", void 0, "checkbox");
      const words = offer("span", "", text);
      label.append(input, words);
      return { label, input };
    };
    const toolbar = offer("div", "lf-shot-toolbar lf-ui");
    const views = select("Comparison view", SHOT_VIEWS, "compare");
    views.options.get("pixels").disabled = true;
    const scale = select("Image scale", { fit: "Fit", actual: "100%" }, "fit");
    scale.input.classList.add("lf-shot-scale");
    const scaleReading = scale.options.get("fit");
    const more = offer("button", `${CONTROL} lf-shotmore`);
    more.ariaLabel = "Image options";
    more.title = "Image options";
    const options = offer("div", "lf-shotoptions");
    options.setAttribute("popover", "auto");
    options.role = "group";
    options.ariaLabel = "Image options";
    do
      options.id = `lf-shot-options-${++nextOptionsId}`;
    while (document.getElementById(options.id));
    more.setAttribute("aria-controls", options.id);
    more.setAttribute("popovertarget", options.id);
    more.setAttribute("aria-expanded", "false");
    const outlines = checkbox("Outline changes");
    outlines.input.disabled = true;
    const full = checkbox("Full frame");
    full.label.hidden = true;
    options.append(outlines.label, full.label);
    toolbar.append(views.input, scale.input, more, options);
    const stage = offer("div", "lf-shotstage");
    stage.tabIndex = 0;
    stage.role = "region";
    stage.ariaLabel = `Screenshot comparison \u2014 ${host.getAttribute("alt")}`;
    const canvas = offer("div", "lf-shotcanvas");
    const rail = offer("div", "lf-shotrail lf-ui");
    stage.append(canvas);
    canvas.append(rail);
    const frames = [], viewports = [], shots = [], captions = /* @__PURE__ */ new Map(), openers = /* @__PURE__ */ new Map();
    for (const state of ["before", "after"]) {
      const frame = offer("div", "lf-shotframe");
      frame.dataset.lfState = state;
      const heading = offer("div", "lf-shot-frame-label lf-ui");
      const caption = offer(
        "span",
        "lf-shotcap lf-label",
        state === "before" ? "Before" : "After"
      );
      caption.role = "button";
      caption.tabIndex = 0;
      caption.dataset.lfOffer = "button";
      caption.dataset.lfSelectableOffer = "";
      caption.dataset.lfSaid = "";
      caption.dataset.lfState = state;
      const viewport = offer("div", "lf-shotviewport");
      viewport.role = "region";
      viewport.ariaLabel = `${state}: ${host.getAttribute("alt")}`;
      const imageBox = offer("div", "lf-shotimage");
      const plane = offer("div", "lf-shotplane");
      const image = document.createElement("img");
      image.crossOrigin = "anonymous";
      image.alt = `${state}: ${host.getAttribute("alt")}`;
      shots.push(image);
      const open = offer("a", "lf-media-open lf-shot-open");
      open.dataset.lfShotOpen = state;
      captions.set(state, caption);
      openers.set(state, open);
      heading.append(caption, open);
      plane.append(image);
      imageBox.append(plane);
      viewport.append(imageBox);
      frame.append(heading, viewport);
      frames.push(frame);
      viewports.push(viewport);
      canvas.append(frame);
    }
    const footer = offer("div", "lf-shot-footer lf-ui");
    const delta = offer("span", "lf-shotdelta");
    const legend = offer("div", "lf-shotlegend");
    for (const [side, text] of [
      ["before", "Before only"],
      ["after", "After only"],
      ["both", "Recolored"]
    ]) {
      const item = offer("span", "lf-shotlegend-item", text);
      item.dataset.lfShotSide = side;
      legend.append(item);
    }
    legend.hidden = true;
    footer.append(delta, legend);
    keeps(host, "data-lf-shot-mode", "compare");
    keeps(host, "data-lf-shot-outlines", false);
    host.append(toolbar, stage, footer);
    const geometry = fitShotGeometry({
      available: stage.clientWidth,
      availableHeight: getComputedStyle(host).getPropertyValue("--lf-holds-height").trim() === "1" ? stage.clientHeight : void 0,
      labelHeight: frames[0].firstElementChild.getBoundingClientRect().height,
      sourceWidth: Number(host.dataset.lfMediaWidth),
      sourceHeight: Number(host.dataset.lfMediaHeight),
      gap: parseFloat(getComputedStyle(host).getPropertyValue("--lf-shot-gap"))
    });
    if (geometry) {
      applyShotGeometry(host, geometry, keeps);
      scaleReading.textContent = `Fit \xB7 ${Math.round(geometry.scale * 100)}%`;
    }
    return {
      toolbar,
      more,
      options,
      views,
      outlines,
      scale,
      full,
      scaleReading,
      stage,
      canvas,
      rail,
      frames,
      viewports,
      shots,
      captions,
      openers,
      footer,
      delta,
      legend
    };
  }

  // skills/leaf/packages/default/initial/lf-shot.js
  document.documentElement.lfInitial.register("lf-shot", drawShot);
})();
