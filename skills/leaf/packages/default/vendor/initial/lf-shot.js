(() => {
  // skills/leaf/packages/default/widgets/shot-view.js
  var SHOT_VIEWS = {
    compare: "Before & after",
    flip: "Slider",
    pixels: "Pixel difference"
  };
  var CONTROL = "lf-btn lf-quiet-action lf-compact-control";
  function fitShotGeometry({
    available,
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
    const layout = width + gap + 4 <= available ? "side" : "stack";
    const columns = view === "compare" && layout === "side" ? 2 : 1;
    const scale = actual ? 1 : Math.min(1, (available - columns * 2 - (columns - 1) * gap) / (columns * width));
    return {
      layout,
      scale,
      crop,
      focus: Boolean(focus),
      vars: {
        "frame-width": width * scale,
        "frame-height": height * scale,
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
    const group = (label, options, selected) => {
      const group2 = offer("div", "lf-shotchoices");
      group2.role = "radiogroup";
      group2.ariaLabel = label;
      const buttons = /* @__PURE__ */ new Map();
      for (const [value, text] of Object.entries(options)) {
        const button = offer("button", `${CONTROL} lf-shotview`, text);
        button.role = "radio";
        button.tabIndex = value === selected ? 0 : -1;
        keeps(button, "aria-checked", value === selected);
        buttons.set(value, button);
        group2.append(button);
      }
      return { group: group2, buttons, options };
    };
    const checkbox = (text) => {
      const label = offer("label", "choice lf-shotchoice");
      const input = offer("input", "", void 0, "checkbox");
      const words = offer("span", "", text);
      label.append(input, words);
      return { label, input };
    };
    const toolbar = offer("div", "lf-shot-toolbar lf-ui");
    const views = group("Comparison view", SHOT_VIEWS, "compare");
    views.buttons.get("pixels").disabled = true;
    const outlines = checkbox("Outline changes");
    outlines.input.disabled = true;
    const scale = group("Image scale", { fit: "Fit", actual: "100%" }, "fit");
    const full = checkbox("Full frame");
    full.label.hidden = true;
    const scaleReading = offer("output", "lf-shotscale");
    scaleReading.ariaLabel = "Displayed scale";
    toolbar.append(views.group, outlines.label, scale.group, full.label, scaleReading);
    const stage = offer("div", "lf-shotstage");
    stage.tabIndex = 0;
    stage.role = "region";
    stage.ariaLabel = `Screenshot comparison \u2014 ${host.getAttribute("alt")}`;
    const canvas = offer("div", "lf-shotcanvas");
    const rail = offer("div", "lf-shotrail lf-ui");
    stage.append(canvas);
    canvas.append(rail);
    const frames = [], shots = [], captions = /* @__PURE__ */ new Map(), openers = /* @__PURE__ */ new Map();
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
      frame.append(heading, imageBox);
      frames.push(frame);
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
      sourceWidth: Number(host.dataset.lfMediaWidth),
      sourceHeight: Number(host.dataset.lfMediaHeight),
      gap: parseFloat(getComputedStyle(host).getPropertyValue("--lf-shot-gap"))
    });
    if (geometry) {
      applyShotGeometry(host, geometry, keeps);
      scaleReading.textContent = `${Math.round(geometry.scale * 100)}% \xB7 image px${geometry.layout === "stack" ? " \xB7 stacked" : ""}`;
    }
    return {
      toolbar,
      views,
      outlines,
      scale,
      full,
      scaleReading,
      stage,
      canvas,
      rail,
      frames,
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
