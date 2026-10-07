/* The playground's one initial DOM producer. It runs as the parser finishes the
 * widget and again only for an arriving widget that has no initial drawing. Native
 * fields and the viewer's tab-local values determine the actual first layout;
 * upgrade adopts these nodes and adds Leaf commands, projection and delivery. */
const own = (root, tag) => [...root.querySelectorAll(`:scope > ${tag}`)];
const KINDS = new Set(["range", "toggle", "choice", "color", "text"]);
const NAME = /^[a-z][a-z0-9-]*$/;
const COPY_LABELS = [
  ["rest", "Copy instruction"],
  ["success", "Copied"],
  ["error", "Copy failed"],
];

function render(host, { tabStore, offer }) {
  const controls = own(host, "lf-playground-control");
  const presets = own(host, "lf-playground-preset");
  const outputs = own(host, "lf-playground-output");
  const previews = own(host, "lf-playground-preview");
  if (!controls.length || outputs.length !== 1 || previews.length !== 1)
    throw new Error("playground needs controls, one preview and one output");
  const output = outputs[0],
    preview = previews[0];
  const controlByName = new Map();
  const choicesByName = new Map();
  for (const control of controls) {
    const name = control.getAttribute("name"),
      kind = control.getAttribute("kind");
    if (!NAME.test(name ?? "") || controlByName.has(name) || !KINDS.has(kind))
      throw new Error(`invalid or repeated playground control ${name}`);
    const choices = own(control, "lf-playground-choice");
    if ((kind === "choice") !== Boolean(choices.length))
      throw new Error(`control ${name} needs choices only for kind choice`);
    const choicesValues = choices.map((choice) => choice.getAttribute("value"));
    if (new Set(choicesValues).size !== choicesValues.length)
      throw new Error(`control ${name} repeats a choice`);
    choicesByName.set(name, choices);
    controlByName.set(name, control);
  }
  const parse = (control, raw) => {
    const name = control.getAttribute("name"),
      kind = control.getAttribute("kind");
    if (kind === "range") {
      const value = Number(raw),
        min = Number(control.getAttribute("min"));
      const max = Number(control.getAttribute("max")),
        step = Number(control.getAttribute("step") ?? "1");
      if (
        ![value, min, max, step].every(Number.isFinite) ||
        min >= max ||
        step <= 0 ||
        value < min ||
        value > max
      )
        throw new Error(`control ${name} has a value outside its range`);
      if (Math.abs((value - min) / step - Math.round((value - min) / step)) > 1e-9)
        throw new Error(`control ${name} has a value off its step`);
      return value;
    }
    if (kind === "toggle") {
      if (!["true", "false"].includes(raw))
        throw new Error(`toggle control ${name} needs true or false`);
      return raw === "true";
    }
    if (typeof raw !== "string") throw new Error(`control ${name} needs text`);
    if (
      kind === "choice" &&
      !choicesByName.get(name).some((choice) => choice.getAttribute("value") === raw)
    )
      throw new Error(`control ${name} has no choice ${raw}`);
    if (kind === "color") {
      if (!/^#[0-9a-f]{6}$/i.test(raw))
        throw new Error(`color control ${name} needs #rrggbb`);
      return raw.toLowerCase();
    }
    return raw;
  };
  const typed = (control, value) => {
    const name = control.getAttribute("name"),
      kind = control.getAttribute("kind");
    const type = kind === "range" ? "number" : kind === "toggle" ? "boolean" : "string";
    if (typeof value !== type) throw new Error(`control ${name} needs a ${type}`);
    return parse(control, String(value));
  };
  const defaults = Object.freeze(
    Object.fromEntries(
      controls.map((control) => [
        control.getAttribute("name"),
        parse(control, control.getAttribute("value")),
      ]),
    ),
  );
  const key = `lf-playground:${host.id}`;
  let storedCandidate = null;
  try {
    const stored = tabStore.get(key);
    if (stored !== null) {
      storedCandidate = JSON.parse(stored);
      if (
        !storedCandidate ||
        typeof storedCandidate !== "object" ||
        Array.isArray(storedCandidate)
      )
        throw new Error("invalid stored configuration");
    }
  } catch {
    storedCandidate = null;
    tabStore.set(key, null);
  }
  let values;
  try {
    values = Object.freeze(
      Object.fromEntries(
        controls.map((control) => {
          const name = control.getAttribute("name");
          const value = Object.hasOwn(storedCandidate ?? {}, name)
            ? storedCandidate[name]
            : defaults[name];
          return [name, typed(control, value)];
        }),
      ),
    );
  } catch {
    storedCandidate = null;
    tabStore.set(key, null);
    values = defaults;
  }
  const node = (tag, cls, text) => {
    const element = document.createElement(tag);
    element.className = cls;
    if (text !== undefined) {
      element.dataset.lfGen = "1";
      element.textContent = text;
    }
    return element;
  };
  const interactive = !host.closest("[data-lf-exhibit]");
  host.classList.toggle("lf-playground-quoted", !interactive);
  const inputs = new Map(),
    presetButtons = new Map(),
    regions = [];
  const presetSettings = new Map(
    presets.map((preset) => {
      const settings = own(preset, "lf-playground-setting");
      if (!settings.length)
        throw new Error(`preset ${preset.getAttribute("label")} is empty`);
      const next = {};
      for (const setting of settings) {
        const name = setting.getAttribute("for");
        if (!controlByName.has(name))
          throw new Error(`preset names unknown control ${name}`);
        if (Object.hasOwn(next, name))
          throw new Error(`preset repeats control ${name}`);
        next[name] = parse(controlByName.get(name), setting.getAttribute("value"));
      }
      return [preset, Object.freeze(next)];
    }),
  );
  let submit = null,
    copy = null,
    reset = null;
  if (interactive) {
    const panel = node("div", "lf-playground-controls");
    const panelTitle = node("p", "lf-playground-controls-title", "Controls");
    panelTitle.id = `${host.id}-controls-title`;
    panel.setAttribute("role", "group");
    panel.setAttribute("aria-labelledby", panelTitle.id);
    panel.append(panelTitle, ...controls);
    for (const control of controls) {
      const name = control.getAttribute("name"),
        kind = control.getAttribute("kind"),
        label = control.getAttribute("label");
      control.classList.add(`lf-playground-${kind}`);
      const heading = node("span", "lf-playground-control-label", label);
      control.prepend(heading);
      if (kind === "choice") {
        const group = node("div", "lf-playground-input lf-playground-choices");
        group.setAttribute("role", "radiogroup");
        group.setAttribute("aria-label", label);
        const radios = [];
        for (const choice of choicesByName.get(name)) {
          const face = node("label", "lf-playground-choice-face");
          const input = offer("input", "lf-playground-radio", undefined, "radio");
          input.name = `${host.id}-${name}`;
          input.value = choice.getAttribute("value");
          face.append(
            input,
            node("span", "lf-playground-choice-label", choice.getAttribute("label")),
          );
          choice.append(face);
          group.append(choice);
          radios.push(input);
        }
        inputs.set(name, radios);
        control.append(group);
      } else {
        const input = offer(
          "input",
          "lf-playground-input",
          undefined,
          kind === "toggle" ? "checkbox" : kind === "text" ? "text" : kind,
        );
        input.id = `${host.id}-${name}-input`;
        input.name = `${host.id}-${name}`;
        input.setAttribute("aria-label", label);
        if (kind === "toggle") input.setAttribute("role", "switch");
        for (const attr of ["min", "max", "step", "placeholder"])
          if (control.hasAttribute(attr))
            input.setAttribute(attr, control.getAttribute(attr));
        inputs.set(name, input);
        control.append(input);
        if (kind === "range") control.append(node("output", "lf-playground-reading"));
      }
    }
    let presetBar = null;
    if (presets.length) {
      presetBar = node("header", "lf-playground-presets");
      const title = node("span", "lf-playground-presets-title", "Starting points");
      title.id = `${host.id}-presets-title`;
      presetBar.setAttribute("role", "group");
      presetBar.setAttribute("aria-labelledby", title.id);
      presetBar.append(title, ...presets);
    }
    for (const preset of presets) {
      const button = offer(
        "button",
        "lf-btn lf-playground-preset",
        preset.getAttribute("label"),
      );
      button.setAttribute("aria-pressed", "false");
      preset.append(button);
      presetButtons.set(preset, button);
    }
    const actions = node("footer", "lf-playground-actions");
    reset = offer("button", "lf-btn lf-playground-reset", "Reset");
    copy = offer("button", "lf-btn lf-playground-copy-trigger");
    copy.id = `${host.id}-copy`;
    copy.dataset.copyState = "rest";
    for (const [state, text] of COPY_LABELS)
      copy.append(node("span", `lf-playground-copy-label ${state}`, text));
    submit = offer(
      "button",
      "lf-btn primary lf-playground-submit",
      host.getAttribute("submit-label") ?? "Use these settings",
    );
    actions.append(reset, copy, submit);
    if (document.querySelector("script[data-lf-offline]"))
      actions.append(
        node(
          "span",
          "lf-playground-unavailable",
          "Submission unavailable: no agent or server is available.",
        ),
      );
    const pane = (name, label, header, body, footer) => {
      const element = node("div", `lf-playground-${name}-region`);
      element.dataset.lfReadingRole = "pane";
      element.dataset.lfGenerated = "";
      element.setAttribute("role", "region");
      element.setAttribute("aria-label", label);
      if (header) element.append(header);
      element.append(body);
      if (footer) element.append(footer);
      regions.push({ name, host: element, body });
      return element;
    };
    const previewBody = node("div", "lf-playground-preview-body");
    previewBody.append(preview);
    const split = node("div", "lf-playground-split");
    split.append(
      pane("preview", "Preview", null, previewBody),
      pane("controls", "Controls", presetBar, panel),
      pane(
        "instruction",
        "Instruction to agent",
        node("header", "lf-playground-instruction-title", "Instruction to agent"),
        output,
        actions,
      ),
    );
    host.append(split);
  }
  const setInput = (control, value) => {
    const name = control.getAttribute("name"),
      kind = control.getAttribute("kind"),
      input = inputs.get(name);
    if (!input) return;
    if (kind === "choice")
      for (const radio of input) radio.checked = radio.value === value;
    else if (kind === "toggle") input.checked = value;
    else input.value = value;
    if (kind === "range")
      text(control.querySelector(":scope > output"), formatted(control, value));
  };
  const readInput = (control) => {
    const kind = control.getAttribute("kind"),
      input = inputs.get(control.getAttribute("name"));
    return kind === "choice"
      ? input.find((radio) => radio.checked)?.value
      : kind === "toggle"
        ? input.checked
        : input.value;
  };
  const text = (element, value) => {
    if (element.textContent !== value) element.textContent = value;
  };
  const formatted = (control, value) => `${value}${control.getAttribute("unit") ?? ""}`;
  const reflection = (next) => {
    const attributes = {},
      properties = {};
    for (const [name, value] of Object.entries(next)) {
      const control = controlByName.get(name);
      if (!control) continue;
      attributes[`data-playground-${name}`] = String(value);
      const content = formatted(control, value);
      properties[`--playground-${name}`] =
        control.getAttribute("kind") === "text" ? JSON.stringify(content) : content;
    }
    return { attributes, properties };
  };
  const renderValues = (next) => {
    for (const slot of output.querySelectorAll("lf-playground-value")) {
      const name = slot.getAttribute("for"),
        control = controlByName.get(name);
      if (!control) throw new Error(`output names unknown control ${name}`);
      text(slot, formatted(control, next[name]));
    }
  };
  const paintPresets = (next) => {
    for (const [preset, button] of presetButtons) {
      const active = Object.entries(presetSettings.get(preset)).every(([name, value]) =>
        Object.is(next[name], value),
      );
      button.classList.toggle("on", active);
      if (button.getAttribute("aria-pressed") !== String(active))
        button.setAttribute("aria-pressed", String(active));
    }
  };
  for (const control of controls)
    setInput(control, values[control.getAttribute("name")]);
  renderValues(values);
  paintPresets(values);
  const initialReflection = reflection(values);
  for (const [name, value] of Object.entries(initialReflection.properties))
    host.style.setProperty(name, value);
  for (const [name, value] of Object.entries(initialReflection.attributes))
    host.setAttribute(name, value);
  host.classList.add("lf-rendered");
  return {
    controls,
    controlByName,
    presets,
    presetSettings,
    defaults,
    values,
    storedCandidate,
    output,
    preview,
    submit,
    copy,
    reset,
    regions,
    presetButtons,
    inputs,
    parse,
    typed,
    readInput,
    setInput,
    renderValues,
    reflection,
    paintPresets,
  };
}
document.documentElement.lfInitial.register("lf-playground", render);
