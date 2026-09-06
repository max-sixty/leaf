/* lf-playground: one declarative control loop with one durable decision.
 *
 * Authors define controls, presets, real preview markup, and an instruction in light
 * DOM. This module owns the common mechanics: typed working state, native controls,
 * tab-local persistence, CSS reflection, value substitution, copying, commands, and
 * the final recordless action. Intermediate changes never enter Leaf's event log.
 *
 * The host element is the extension boundary. Its `values` getter returns a fresh
 * snapshot, and every working-state change dispatches `lf-playground-change` with the
 * same snapshot at `event.detail.values`. Simple previews need neither: they read the
 * reflected `--playground-NAME` properties and `data-playground-NAME` attributes.
 *
 * Projection is deliberately separate from working state. A repeated projection must
 * not erase local edits, while a newly chosen action or its undo must replace them.
 * The last projection signature distinguishes those cases without making the DOM or a
 * second event history authoritative. */
import {
  actionAvailable,
  commands,
  failSoft,
  keeps,
  layoutChanged,
  notice,
  offer,
  once,
  paintKeys,
  quoted,
  says,
  sendAction,
  tabStore,
} from "/runtime/widget-api.js";

const NAME = /^[a-z][a-z0-9-]*$/;
const COLOR = /^#[0-9a-f]{6}$/i;
const KINDS = new Set(["range", "toggle", "choice", "color", "text"]);
const CHANGE = "lf-playground-change";

const own = (root, tag) => [...root.querySelectorAll(`:scope > ${tag}`)];

const sameKeys = (left, right) =>
  left.length === right.length && left.every((key, index) => key === right[index]);

customElements.define(
  "lf-playground",
  class extends HTMLElement {
    #controls = [];
    #controlByName = new Map();
    #presetSettings = new Map();
    #presetButtons = new Map();
    #defaults = Object.freeze({});
    #values = Object.freeze({});
    #output = null;
    #submit = null;
    #copy = null;
    #reset = null;
    #projected = undefined;
    #ready = false;
    #interactive = false;

    connectedCallback() {
      if (!once(this)) {
        this.#paintAvailability();
        return;
      }
      try {
        this.#build();
        this.#ready = true;
      } catch (error) {
        failSoft(this, error);
      }
    }

    get values() {
      return structuredClone(this.#values);
    }

    #build() {
      this.#controls = own(this, "lf-playground-control");
      const presets = own(this, "lf-playground-preset");
      const previews = own(this, "lf-playground-preview");
      const outputs = own(this, "lf-playground-output");
      if (!this.#controls.length) throw new Error("needs at least one control");
      if (previews.length !== 1) throw new Error("needs exactly one preview");
      if (outputs.length !== 1) throw new Error("needs exactly one output");
      this.#output = outputs[0];
      this.#interactive = !quoted(this);
      this.classList.toggle("lf-playground-quoted", !this.#interactive);

      for (const control of this.#controls) this.#declareControl(control);
      this.#defaults = Object.freeze(
        Object.fromEntries(
          this.#controls.map((control) => [
            control.getAttribute("name"),
            this.#parse(control, control.getAttribute("value")),
          ]),
        ),
      );
      this.#validateValueSlots();
      for (const preset of presets)
        this.#presetSettings.set(preset, this.#validatePreset(preset));

      if (this.#interactive) {
        const panel = offer("div", "lf-playground-controls");
        const panelTitle = offer("p", "lf-playground-controls-title", "Controls");
        panelTitle.id = `${this.id}-controls-title`;
        panel.setAttribute("role", "group");
        panel.setAttribute("aria-labelledby", panelTitle.id);
        panel.append(panelTitle, ...this.#controls);
        this.prepend(panel);
        if (presets.length) {
          const presetBar = offer("div", "lf-playground-presets");
          const presetTitle = offer(
            "span",
            "lf-playground-presets-title",
            "Starting points",
          );
          presetTitle.id = `${this.id}-presets-title`;
          presetBar.setAttribute("role", "group");
          presetBar.setAttribute("aria-labelledby", presetTitle.id);
          presetBar.append(presetTitle, ...presets);
          this.prepend(presetBar);
        }

        for (const control of this.#controls) this.#buildControl(control);
        for (const preset of presets) this.#buildPreset(preset);
        this.#buildActions();
      }

      const stored = this.#storedValues();
      this.#apply(stored ?? this.#defaults, { remember: false });
      if (this.#interactive) this.#commands();
      this.#paintAvailability();
    }

    #declareControl(control) {
      const name = control.getAttribute("name");
      const kind = control.getAttribute("kind");
      if (!NAME.test(name ?? "")) throw new Error(`invalid control name ${name}`);
      if (this.#controlByName.has(name)) throw new Error(`repeats control ${name}`);
      if (!KINDS.has(kind)) throw new Error(`control ${name} has unknown kind ${kind}`);

      const choices = own(control, "lf-playground-choice");
      if (kind === "choice") {
        if (!choices.length) throw new Error(`choice control ${name} has no choices`);
        const values = choices.map((choice) => choice.getAttribute("value"));
        if (new Set(values).size !== values.length)
          throw new Error(`choice control ${name} repeats a value`);
      } else if (choices.length) {
        throw new Error(`${kind} control ${name} cannot contain choices`);
      }

      if (kind === "range") {
        const min = Number(control.getAttribute("min"));
        const max = Number(control.getAttribute("max"));
        const step = Number(control.getAttribute("step") ?? "1");
        if (![min, max, step].every(Number.isFinite) || min >= max || step <= 0)
          throw new Error(`range control ${name} needs min < max and step > 0`);
      }
      this.#controlByName.set(name, control);
    }

    #validateValueSlots() {
      for (const slot of this.#output.querySelectorAll("lf-playground-value")) {
        const name = slot.getAttribute("for");
        if (!this.#controlByName.has(name))
          throw new Error(`output names unknown control ${name}`);
      }
    }

    #parse(control, raw) {
      const name = control.getAttribute("name");
      const kind = control.getAttribute("kind");
      if (kind === "range") {
        const value = Number(raw);
        const min = Number(control.getAttribute("min"));
        const max = Number(control.getAttribute("max"));
        const step = Number(control.getAttribute("step") ?? "1");
        if (!Number.isFinite(value) || value < min || value > max)
          throw new Error(`control ${name} has a value outside its range`);
        const steps = (value - min) / step;
        if (Math.abs(steps - Math.round(steps)) > 1e-9)
          throw new Error(`control ${name} has a value off its step`);
        return value;
      }
      if (kind === "toggle") {
        if (raw !== "true" && raw !== "false")
          throw new Error(`toggle control ${name} needs true or false`);
        return raw === "true";
      }
      if (typeof raw !== "string") throw new Error(`control ${name} needs text`);
      if (kind === "choice") {
        const choices = [...control.querySelectorAll("lf-playground-choice")].map(
          (choice) => choice.getAttribute("value"),
        );
        if (!choices.includes(raw))
          throw new Error(`control ${name} has no choice ${raw}`);
      }
      if (kind === "color") {
        if (!COLOR.test(raw)) throw new Error(`color control ${name} needs #rrggbb`);
        return raw.toLowerCase();
      }
      return raw;
    }

    #normalize(candidate) {
      if (!candidate || typeof candidate !== "object" || Array.isArray(candidate))
        throw new Error("configuration values must be an object");
      const names = [...this.#controlByName.keys()].sort();
      const keys = Object.keys(candidate).sort();
      if (!sameKeys(names, keys))
        throw new Error(
          `configuration needs exactly these controls: ${names.join(", ")}`,
        );
      return Object.freeze(
        Object.fromEntries(
          names.map((name) => {
            const control = this.#controlByName.get(name);
            const value = candidate[name];
            const kind = control.getAttribute("kind");
            if (kind === "range" && typeof value !== "number")
              throw new Error(`control ${name} needs a number`);
            if (kind === "toggle" && typeof value !== "boolean")
              throw new Error(`control ${name} needs a boolean`);
            if (!["range", "toggle"].includes(kind) && typeof value !== "string")
              throw new Error(`control ${name} needs a string`);
            return [name, this.#parse(control, String(value))];
          }),
        ),
      );
    }

    #buildControl(control) {
      const name = control.getAttribute("name");
      const kind = control.getAttribute("kind");
      const label = control.getAttribute("label");
      control.classList.add(`lf-playground-${kind}`);

      const heading = offer("span", "lf-playground-control-label", label);
      control.prepend(heading);
      if (kind === "choice") {
        const group = offer("div", "lf-playground-choices");
        group.setAttribute("role", "radiogroup");
        group.setAttribute("aria-label", label);
        for (const choice of own(control, "lf-playground-choice")) {
          const input = offer("input", "lf-playground-input");
          input.type = "radio";
          input.name = `${this.id}-${name}`;
          input.value = choice.getAttribute("value");
          input.setAttribute("aria-label", choice.getAttribute("label"));
          input.addEventListener("change", () => this.#takeInputs());
          const words = offer(
            "span",
            "lf-playground-choice-label",
            choice.getAttribute("label"),
          );
          choice.append(input, words);
          choice.addEventListener("click", (event) => {
            if (event.target !== input) input.click();
          });
          group.append(choice);
        }
        control.append(group);
        return;
      }

      const input = offer("input", "lf-playground-input");
      input.setAttribute("aria-label", label);
      if (kind === "toggle") {
        input.type = "checkbox";
        input.addEventListener("change", () => this.#takeInputs());
      } else {
        input.type = kind;
        for (const attr of ["min", "max", "step", "placeholder"])
          if (control.hasAttribute(attr))
            input.setAttribute(attr, control.getAttribute(attr));
        input.addEventListener("input", () => this.#takeInputs());
      }
      control.append(input);
      if (kind === "range") {
        const reading = offer("output", "lf-playground-reading");
        control.append(reading);
      }
    }

    #validatePreset(preset) {
      const settings = own(preset, "lf-playground-setting");
      if (!settings.length)
        throw new Error(`preset ${preset.getAttribute("label")} is empty`);
      const seen = new Set();
      const values = {};
      for (const setting of settings) {
        const name = setting.getAttribute("for");
        if (!this.#controlByName.has(name))
          throw new Error(`preset names unknown control ${name}`);
        if (seen.has(name)) throw new Error(`preset repeats control ${name}`);
        values[name] = this.#parse(
          this.#controlByName.get(name),
          setting.getAttribute("value"),
        );
        seen.add(name);
      }
      return Object.freeze(values);
    }

    #buildPreset(preset) {
      const settings = this.#presetSettings.get(preset);
      const button = offer(
        "button",
        "lf-btn lf-playground-preset",
        preset.getAttribute("label"),
      );
      button.setAttribute("aria-pressed", "false");
      button.addEventListener("click", () => {
        const next = { ...this.#values };
        for (const [name, value] of Object.entries(settings)) next[name] = value;
        this.#apply(next);
      });
      this.#presetButtons.set(preset, button);
      preset.append(button);
    }

    #paintPresets() {
      for (const [preset, button] of this.#presetButtons) {
        const active = Object.entries(this.#presetSettings.get(preset)).every(
          ([name, value]) => Object.is(this.#values[name], value),
        );
        button.classList.toggle("on", active);
        button.setAttribute("aria-pressed", String(active));
      }
    }

    #buildActions() {
      const actions = offer("div", "lf-playground-actions");
      this.#reset = offer("button", "lf-btn lf-playground-reset", "Reset");
      this.#copy = offer("button", "lf-btn lf-playground-copy", "Copy instruction");
      this.#submit = offer(
        "button",
        "lf-btn primary lf-playground-submit",
        this.getAttribute("submit-label") ?? "Use these settings",
      );
      this.#reset.addEventListener("click", () => this.#apply(this.#defaults));
      this.#copy.addEventListener("click", () => this.#copyInstruction());
      this.#submit.addEventListener("click", () => this.#choose());
      actions.append(this.#reset, this.#copy, this.#submit);
      this.append(actions);
    }

    #commands() {
      commands(
        this,
        "In a playground",
        [
          {
            id: "playground.choose",
            control: this.#submit,
            decision: () => this.#submit.textContent,
            does: () => this.#submit.textContent,
            line: () => this.#submit.textContent.toLowerCase(),
            when: () => actionAvailable(this, "choose"),
            run: () => this.#submit.click(),
          },
          {
            id: "playground.reset",
            keys: ["Alt+0"],
            control: this.#reset,
            does: "Reset the playground",
            line: "reset controls",
            run: () => this.#reset.click(),
          },
        ],
        { answer: () => this.#instruction() },
      );
    }

    #readInput(control) {
      const kind = control.getAttribute("kind");
      if (kind === "choice") {
        const selected = control.querySelector(':scope input[type="radio"]:checked');
        return selected?.value;
      }
      const input = control.querySelector(":scope > input");
      return kind === "toggle" ? input.checked : input.value;
    }

    #takeInputs() {
      const next = Object.fromEntries(
        this.#controls.map((control) => [
          control.getAttribute("name"),
          this.#parse(control, String(this.#readInput(control))),
        ]),
      );
      this.#apply(next);
    }

    #setInput(control, value) {
      const kind = control.getAttribute("kind");
      if (kind === "choice") {
        for (const input of control.querySelectorAll(':scope input[type="radio"]'))
          input.checked = input.value === value;
        return;
      }
      const input = control.querySelector(":scope > input");
      if (!input) return;
      if (kind === "toggle") input.checked = value;
      else input.value = String(value);
      input.setAttribute("value", String(value));
      if (kind === "toggle") input.toggleAttribute("checked", value);
      if (kind === "range") {
        const reading = control.querySelector(":scope > output");
        keeps(reading, "value", String(value));
        reading.textContent = this.#formatted(control, value);
      }
    }

    #formatted(control, value) {
      return `${value}${control.getAttribute("unit") ?? ""}`;
    }

    #apply(candidate, { remember = true } = {}) {
      const values = this.#normalize(candidate);
      this.#values = values;
      for (const [name, value] of Object.entries(values)) {
        const control = this.#controlByName.get(name);
        this.#setInput(control, value);
        this.style.setProperty(`--playground-${name}`, this.#formatted(control, value));
        keeps(this, `data-playground-${name}`, value);
      }
      for (const slot of this.#output.querySelectorAll("lf-playground-value")) {
        const name = slot.getAttribute("for");
        slot.textContent = this.#formatted(this.#controlByName.get(name), values[name]);
      }
      if (this.#copy) this.#copy.textContent = "Copy instruction";
      this.#paintPresets();
      if (remember) tabStore.set(this.#storeKey(), JSON.stringify(values));
      this.dispatchEvent(
        new CustomEvent(CHANGE, {
          bubbles: true,
          composed: true,
          detail: { values: this.values },
        }),
      );
      layoutChanged(this);
      paintKeys();
    }

    #storeKey() {
      return `lf-playground:${this.id}`;
    }

    #storedValues() {
      const stored = tabStore.get(this.#storeKey());
      if (stored === null) return null;
      try {
        return this.#normalize(JSON.parse(stored));
      } catch {
        tabStore.set(this.#storeKey(), null);
        return null;
      }
    }

    #instruction() {
      return says(this.#output)
        .replace(/\s+/g, " ")
        .replace(/\s+([,.;:!?])/g, "$1")
        .trim();
    }

    async #copyInstruction() {
      try {
        await navigator.clipboard.writeText(this.#instruction());
        this.#copy.textContent = "Copied";
        notice("Instruction copied");
      } catch (error) {
        notice(`Could not copy: ${error.message}`);
      }
    }

    async #choose() {
      if (!actionAvailable(this, "choose")) return;
      this.#submit.setAttribute("aria-busy", "true");
      try {
        const event = await sendAction(this, "choose", {
          values: this.values,
          instruction: this.#instruction(),
        });
        if (event) notice("Playground settings sent");
      } finally {
        this.#submit.removeAttribute("aria-busy");
        this.#paintAvailability();
      }
    }

    #paintAvailability() {
      if (!this.#submit) return;
      this.#submit.disabled = !actionAvailable(this, "choose");
      paintKeys();
    }

    renderState(state) {
      if (!this.#ready) return true;
      const configuration = state.configuration;
      const projected =
        configuration?.action === "choose"
          ? JSON.stringify(configuration.detail.values)
          : null;
      if (this.#projected === projected) return true;
      const firstProjection = this.#projected === undefined;
      this.#projected = projected;
      if (projected !== null) this.#apply(configuration.detail.values);
      else if (!firstProjection) this.#apply(this.#defaults);
      this.#paintAvailability();
      return true;
    }
  },
);
