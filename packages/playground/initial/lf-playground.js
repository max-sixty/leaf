/* The playground's one initial DOM producer. It runs as the parser finishes the
 * widget and again only for an arriving widget that has no initial drawing. Native
 * fields and the viewer's tab-local values determine the actual first layout;
 * upgrade adopts these nodes and adds Leaf commands, projection and delivery.
 *
 * Every authored playground has passed validation, page source and message markup
 * alike, so what the registry states is not checked again here: control names and
 * kinds, unique control names, choice values and preset settings (x-unique), and each
 * setting's and value slot's `for` naming a control of this playground (a keyed
 * x-refers). This producer checks only what needs the values themselves, such as a
 * range value against its bounds or a choice control's value among its choices. */
import { iconElement } from "../../../browser/runtime/icon-paths.js";

const own = (root, tag) => [...root.querySelectorAll(`:scope > ${tag}`)];
const belongsTo = (host, member) =>
  member.parentElement.closest("lf-playground, [data-lf-exhibit]") === host;
// A control stands in the rail as a direct child, or where the preview's markup puts
// it, beside the item it changes (x-within). Nested playgrounds and quotations
// enclose their own content rather than supplying controls to this playground.
const ownControls = (host, preview) => [
  ...own(host, "lf-playground-control"),
  ...[...(preview?.querySelectorAll("lf-playground-control") ?? [])].filter((control) =>
    belongsTo(host, control),
  ),
];

function render(host, { tabStore, offer, offerAction, generatedElement, keeps }) {
  const presets = own(host, "lf-playground-preset");
  const outputs = own(host, "lf-playground-output");
  const previews = own(host, "lf-playground-preview");
  const controls = ownControls(host, previews[0]);
  if (!controls.length || outputs.length !== 1 || previews.length !== 1)
    throw new Error("playground needs controls, one preview and one output");
  const output = outputs[0],
    preview = previews[0];
  const controlByName = new Map();
  const choicesByName = new Map();
  for (const control of controls) {
    const name = control.getAttribute("name"),
      kind = control.getAttribute("kind");
    const choices = own(control, "lf-playground-choice");
    if ((kind === "choice") !== Boolean(choices.length))
      throw new Error(`control ${name} needs choices only for kind choice`);
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
      if (!Number.isFinite(value) || min >= max || value < min || value > max)
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
      generatedElement(element, { says: false });
      element.textContent = text;
    }
    return element;
  };
  const interactive = !host.closest("[data-lf-exhibit]");
  host.classList.toggle("lf-playground-quoted", !interactive);
  // A choice can be the candidate itself. Its content stays outside the native
  // radio's label so operating a preview never also chooses that candidate.
  for (const control of controls) {
    const choices = choicesByName.get(control.getAttribute("name"));
    if (
      !choices.some((choice) =>
        [...choice.childNodes].some(
          (child) =>
            child.nodeType === Node.ELEMENT_NODE ||
            (child.nodeType === Node.TEXT_NODE && child.data.trim()),
        ),
      )
    )
      continue;
    control.classList.add("lf-playground-candidates");
    for (const choice of choices) {
      const body = node("div", "lf-playground-choice-preview");
      body.append(...choice.childNodes);
      choice.append(body);
      if (!interactive)
        choice.prepend(
          node("p", "lf-playground-choice-heading", choice.getAttribute("label")),
        );
    }
  }
  // A quotation draws no controls or presets, so they are hidden, which outranks
  // whatever display the page's own stylesheet gives them (theme.css, `[hidden]`). A
  // box the preview wrote around controls alone, at any depth, would stand empty, so
  // it is hidden with them. A box that also holds words or another element keeps them.
  if (!interactive) {
    const bare = new Set(
      controls.filter(
        (control) => !control.classList.contains("lf-playground-candidates"),
      ),
    );
    const holdsOnlyBare = (box) =>
      [...box.childNodes].every((child) =>
        child.nodeType === Node.TEXT_NODE
          ? !child.data.trim()
          : child.nodeType === Node.COMMENT_NODE || bare.has(child),
      );
    for (const control of bare)
      for (
        let box = control.parentElement;
        box !== preview && box !== host && !bare.has(box) && holdsOnlyBare(box);
        box = box.parentElement
      ) {
        bare.add(box);
      }
    for (const hidden of [...bare, ...presets]) hidden.hidden = true;
  }
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
        next[name] = parse(controlByName.get(name), setting.getAttribute("value"));
      }
      return [preset, Object.freeze(next)];
    }),
  );
  let submit = null,
    reset = null,
    reveal = null,
    instruction = null;
  if (interactive) {
    const railed = controls.filter((control) => control.parentElement === host);
    // The box of controls evidently is one, and each control carries its own label, so
    // its name is for assistive tech alone.
    const panel = node("div", "lf-playground-controls");
    panel.setAttribute("role", "group");
    panel.setAttribute("aria-label", "Controls");
    panel.append(...railed);
    for (const control of controls) {
      const name = control.getAttribute("name"),
        kind = control.getAttribute("kind"),
        label = control.getAttribute("label");
      control.classList.add(`lf-playground-${kind}`);
      const heading = node("span", "lf-playground-control-label", label);
      control.prepend(heading);
      if (kind === "choice" && control.getAttribute("appearance") === "select") {
        const input = offer("select", "lf-playground-input");
        input.name = `${host.id}-${name}`;
        input.setAttribute("aria-label", label);
        for (const choice of choicesByName.get(name)) {
          const option = node("option", "", choice.getAttribute("label"));
          option.value = choice.getAttribute("value");
          input.append(option);
          choice.remove();
        }
        inputs.set(name, input);
        control.append(input);
      } else if (kind === "choice") {
        const group = node("div", "lf-playground-input lf-playground-choices");
        group.setAttribute("role", "radiogroup");
        group.setAttribute("aria-label", label);
        const radios = [];
        for (const choice of choicesByName.get(name)) {
          const face = generatedElement(node("label", "choice"), { says: false });
          const input = offer("input", "", undefined, "radio");
          input.name = `${host.id}-${name}`;
          input.value = choice.getAttribute("value");
          face.append(
            input,
            node("span", "lf-playground-choice-label", choice.getAttribute("label")),
          );
          choice.prepend(face);
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
        if (kind === "toggle") {
          const face = generatedElement(node("label", "choice"), { says: false });
          face.append(input);
          control.append(face);
        } else control.append(input);
        if (kind === "range") control.append(node("output", "lf-playground-reading"));
      }
    }
    let presetBar = null;
    if (presets.length) {
      // The presets head the rail's controls, or are the whole pane when every
      // control stands in the preview. The buttons stand alone, with "Starting
      // points" only as the group's accessible name: the user chose this on
      // 2026-10-26 over a visible label before them.
      presetBar = node(railed.length ? "header" : "div", "lf-playground-presets");
      presetBar.setAttribute("role", "group");
      presetBar.setAttribute("aria-label", "Starting points");
      presetBar.append(...presets);
    }
    for (const preset of presets) {
      const button = offerAction(
        "word",
        "lf-playground-preset",
        preset.getAttribute("label"),
      );
      button.setAttribute("aria-pressed", "false");
      preset.append(button);
      presetButtons.set(preset, button);
    }
    // The instruction pane is a bar of its actions: Reset and the instruction's
    // reveal as symbols, and the one worded action, the submission. The instruction
    // opens over the page in a popover (lf-playground.js); its words also reach the
    // agent's thread once sent. Shown at rest, a long instruction took more of the
    // playground's room than the controls that wrote it (2026-10-25).
    const actions = node("div", "lf-playground-actions");
    reset = offerAction("symbol", "lf-playground-reset", "Reset");
    reset.append(iconElement("retry", "lf-action-icon"));
    instruction = node("div", "lf-playground-instruction");
    instruction.id = `${host.id}-instruction`;
    instruction.popover = "auto";
    instruction.setAttribute("role", "dialog");
    const instructionTitle = node(
      "p",
      "lf-playground-instruction-title lf-label",
      "Instruction to agent",
    );
    instructionTitle.id = `${host.id}-instruction-title`;
    instruction.setAttribute("aria-labelledby", instructionTitle.id);
    const instructionHead = node("div", "lf-playground-instruction-head");
    instructionHead.append(instructionTitle);
    const instructionBody = node("div", "lf-playground-instruction-body");
    instructionBody.append(output);
    instruction.append(instructionHead, instructionBody);
    reveal = offerAction("symbol", "lf-playground-reveal", "Show instruction");
    reveal.popoverTargetElement = instruction;
    // Leaf's disclosure keys and Go-to routes read this explicit relation.
    reveal.setAttribute("aria-controls", instruction.id);
    reveal.setAttribute("aria-expanded", "false");
    reveal.append(iconElement("more", "lf-action-icon"));
    submit = offerAction("commit", "lf-playground-submit");
    const submitLabel = host.getAttribute("submit-label") ?? "Use these settings";
    submit.dataset.room = `${submitLabel}\nUndo choice`;
    submit.append(node("span", "", submitLabel));
    actions.append(reset, reveal, submit, instruction);
    if (document.querySelector("script[data-lf-offline]"))
      actions.append(
        node(
          "span",
          "lf-playground-unavailable",
          "Submission unavailable: no agent or server is available.",
        ),
      );
    const pane = (name, label, header, body) => {
      const element = node("div", `lf-playground-${name}-region`);
      element.dataset.lfReadingRole = "pane";
      element.dataset.lfGenerated = "";
      element.setAttribute("role", "region");
      element.setAttribute("aria-label", label);
      if (header) element.append(header);
      element.append(body);
      regions.push({ name, host: element, body });
      return element;
    };
    const previewBody = node("div", "lf-playground-preview-body");
    previewBody.append(preview);
    const split = node("div", "lf-playground-split");
    // The rail's controls pane holds the controls written there and the presets; a
    // playground whose every control stands in its preview and that offers no preset
    // has none. The rail is the Layout's track (`data-lf-track`, layouts.css) wherever
    // the theme stands it beside the stage, so it scrolls as a region of its own.
    if (!railed.length && presetBar)
      split.append(pane("controls", "Controls", null, presetBar));
    const rail = node("div", "lf-playground-rail");
    rail.dataset.lfTrack = "";
    rail.append(
      ...(railed.length ? [pane("controls", "Controls", presetBar, panel)] : []),
      pane("instruction", "Instruction to agent", null, actions),
    );
    regions.push({ name: "rail", host: rail, body: rail });
    split.append(pane("preview", "Preview", null, previewBody), rail);
    host.append(split);
  }
  const setInput = (control, value) => {
    const name = control.getAttribute("name"),
      kind = control.getAttribute("kind"),
      input = inputs.get(name);
    if (!input) return;
    if (Array.isArray(input))
      for (const radio of input) radio.checked = radio.value === value;
    else if (kind === "toggle") input.checked = value;
    else input.value = value;
    if (kind === "range")
      text(control.querySelector(":scope > output"), formatted(control, value));
  };
  const readInput = (control) => {
    const kind = control.getAttribute("kind"),
      input = inputs.get(control.getAttribute("name"));
    return Array.isArray(input)
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
  // A slot's value is the configuration's, not the author's, so it is generated, apart
  // from the instruction around it; the user can still quote the value.
  const renderValues = (next) => {
    for (const slot of output.querySelectorAll("lf-playground-value")) {
      if (!belongsTo(host, slot)) continue;
      const name = slot.getAttribute("for");
      generatedElement(slot, { says: true });
      text(slot, formatted(controlByName.get(name), next[name]));
    }
  };
  const paintPresets = (next) => {
    for (const [preset, button] of presetButtons) {
      const active = Object.entries(presetSettings.get(preset)).every(([name, value]) =>
        Object.is(next[name], value),
      );
      keeps(button, "aria-pressed", active);
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
    reset,
    reveal,
    instruction,
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
