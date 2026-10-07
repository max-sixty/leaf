/* lf-playground: one declarative control loop with one durable decision.
 *
 * Authors define controls, presets, real preview markup, and an instruction in light
 * DOM. The synchronous initial producer owns their DOM and typed control values;
 * this module adopts that drawing and owns the live mechanics: working state,
 * tab-local persistence, CSS reflection, instruction copying, commands, and
 * the final recordless action. Intermediate changes never enter Leaf's event log.
 *
 * The host element is the extension boundary. Its `values` getter returns a fresh
 * snapshot. Page modules register structured contributors through one read/apply pair
 * and call the returned notifier after a gesture. Every working-state change then
 * dispatches `lf-playground-change` with the same aggregate snapshot at
 * `event.detail.values`. Simple previews need neither: they read the reflected
 * `--playground-NAME` properties and `data-playground-NAME` attributes, which this
 * element carries and the root of each sample child under it wears (`dressSamples`).
 *
 * Projection is deliberately separate from working state. A repeated projection must
 * not erase local edits, while a newly chosen action or its undo must replace them.
 * The last projection signature distinguishes those cases without making the DOM or a
 * second event history authoritative. */
import {
  commands,
  compoundReadingRegionId,
  dressSamples,
  failSoft,
  layoutChanged,
  notice,
  once,
  initialRender,
  paintKeys,
  registerReadingRegion,
  says,
  tabStore,
  wear,
  widgetController,
} from "/runtime/widget-api.js";
import "./lf-playground-output.js";

const NAME = /^[a-z][a-z0-9-]*$/;
const CHANGE = "lf-playground-change";
// What one pointer press operates: a preset, Reset, and the controls whose press or
// drag is the whole gesture. Their readable labels remain ordinary selection targets.
const ONE_PRESS = [
  ".lf-playground-preset",
  ".lf-playground-reset",
  ...["choice", "toggle", "range"].map((kind) => `.lf-playground-${kind}`),
].join(", ");

const sameKeys = (left, right) =>
  left.length === right.length && left.every((key, index) => key === right[index]);

function jsonSnapshot(value, path = "configuration") {
  if (value === null || typeof value === "string" || typeof value === "boolean")
    return value;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error(`${path} needs finite numbers`);
    return value;
  }
  if (Array.isArray(value))
    return Object.freeze(
      Array.from(value, (item, index) => jsonSnapshot(item, `${path}[${index}]`)),
    );
  if (
    typeof value !== "object" ||
    ![Object.prototype, null].includes(Object.getPrototypeOf(value))
  )
    throw new Error(`${path} must be JSON-safe`);
  return Object.freeze(
    Object.fromEntries(
      Object.entries(value).map(([key, item]) => [
        key,
        jsonSnapshot(item, `${path}.${key}`),
      ]),
    ),
  );
}

customElements.define(
  "lf-playground",
  class extends HTMLElement {
    // What the Ask was answered with: the instruction the chosen configuration sent.
    static answerWords(state) {
      return state.choose.detail.instruction;
    }

    #controller = widgetController(this);
    #initial = null;
    #controls = [];
    #controlByName = new Map();
    #contributors = new Map();
    #presetSettings = new Map();
    #presetButtons = new Map();
    #defaults = Object.freeze({});
    #values = Object.freeze({});
    #storedCandidate = null;
    #instructionProvider = null;
    #output = null;
    #preview = null;
    #submit = null;
    #copy = null;
    #copyTimer = null;
    #reset = null;
    #choosing = false;
    #projected = undefined;
    #ready = false;
    #interactive = false;
    #regions = [];
    #unregister = [];

    connectedCallback() {
      if (!once(this)) {
        this.#registerRegions();
        this.#paintAvailability();
        return;
      }
      try {
        this.#build();
        this.#ready = true;
        if (this.#interactive)
          this.#controller.subscribe(() => this.#paintAvailability());
      } catch (error) {
        this.#unregisterRegions();
        failSoft(this, error);
      }
    }

    disconnectedCallback() {
      clearTimeout(this.#copyTimer);
      this.#unregisterRegions();
    }

    get values() {
      return structuredClone(this.#values);
    }

    registerContributor(name, defaultSnapshot, operations) {
      if (!this.#ready) throw new Error("playground is not ready");
      if (!NAME.test(name ?? "")) throw new Error(`invalid contributor name ${name}`);
      if (this.#controlByName.has(name))
        throw new Error(`contributor ${name} collides with a control`);
      if (this.#contributors.has(name)) throw new Error(`repeats contributor ${name}`);
      if (
        !operations ||
        typeof operations.read !== "function" ||
        typeof operations.apply !== "function"
      )
        throw new Error(`contributor ${name} needs read and apply operations`);

      const initial = jsonSnapshot(defaultSnapshot, `contributor ${name}`);
      this.#contributors.set(name, { ...operations, defaultSnapshot: initial });
      this.#defaults = Object.freeze({ ...this.#defaults, [name]: initial });
      const restored = Object.hasOwn(this.#storedCandidate ?? {}, name)
        ? this.#storedCandidate[name]
        : initial;
      try {
        this.#apply({ ...this.#values, [name]: restored }, { remember: false });
      } catch (error) {
        this.#contributors.delete(name);
        const { [name]: _discarded, ...defaults } = this.#defaults;
        this.#defaults = Object.freeze(defaults);
        throw error;
      }

      return () => {
        const contributor = this.#contributors.get(name);
        if (!contributor) return;
        const snapshot = jsonSnapshot(contributor.read(), `contributor ${name}`);
        this.#apply({ ...this.#values, [name]: snapshot });
      };
    }

    registerInstructionProvider(provider) {
      if (!this.#ready) throw new Error("playground is not ready");
      if (typeof provider !== "function")
        throw new Error("instruction provider must be a function");
      if (this.#instructionProvider)
        throw new Error("playground already has an instruction provider");
      this.#instructionProvider = provider;
      this.#renderOutput();
      this.#syncCopy();
    }

    #build() {
      this.#initial = initialRender(this);
      const initial = this.#initial;
      this.#controls = initial.controls;
      this.#controlByName = initial.controlByName;
      this.#defaults = initial.defaults;
      this.#values = initial.values;
      this.#storedCandidate = initial.storedCandidate;
      this.#output = initial.output;
      this.#preview = initial.preview;
      this.#interactive = Boolean(initial.submit);
      this.#submit = initial.submit;
      this.#copy = initial.copy;
      this.#reset = initial.reset;
      this.#presetButtons = initial.presetButtons;
      this.#regions = initial.regions.map((region) => ({
        ...region,
        id: compoundReadingRegionId(this, region.name),
      }));
      this.#presetSettings = initial.presetSettings;
      this.#initial.renderValues(this.#values);
      const reflection = this.#reflection();
      wear(this, reflection);
      this.#syncCopy();
      dressSamples(this, reflection);
      if (this.#interactive) {
        for (const control of this.#controls)
          control.addEventListener("input", () => this.#takeInputs());
        for (const [preset, button] of this.#presetButtons)
          button.addEventListener("click", () => {
            const next = { ...this.#values, ...this.#presetSettings.get(preset) };
            this.#apply(next);
          });
        this.#copy.addEventListener("click", () => this.#copyInstruction());
        this.addEventListener("mousedown", (event) => {
          if (event.target.closest(".lf-playground-control-label")) return;
          const pressed = event.target.closest(ONE_PRESS);
          if (pressed?.closest("lf-playground") === this && this.#standsInPreview()) {
            const selection = getSelection();
            if (selection && !this.#preview.contains(selection.focusNode))
              selection.removeAllRanges();
            const range = event.target.closest('input[type="range"]');
            if (range) {
              // Native range focus and track operation share a browser default.
              // Return focus synchronously after that default takes it, so dragging
              // remains native while the preview keeps showing its focused state.
              let standing = document.activeElement;
              while (standing?.contentDocument)
                standing = standing.contentDocument.activeElement;
              range.addEventListener(
                "focus",
                () => standing.focus({ preventScroll: true }),
                { once: true },
              );
            } else event.preventDefault();
          }
        });
        this.#commands();
      }
      this.#registerRegions();
      this.#paintPresets();
      this.#paintAvailability();
    }

    #parse(control, raw) {
      return this.#initial.parse(control, raw);
    }

    #normalize(candidate) {
      if (!candidate || typeof candidate !== "object" || Array.isArray(candidate))
        throw new Error("configuration values must be an object");
      const names = [
        ...this.#controlByName.keys(),
        ...this.#contributors.keys(),
      ].sort();
      const keys = Object.keys(candidate).sort();
      if (!sameKeys(names, keys))
        throw new Error(
          `configuration needs exactly these fields: ${names.join(", ")}`,
        );
      return Object.freeze(
        Object.fromEntries(
          names.map((name) => {
            const control = this.#controlByName.get(name);
            const value = candidate[name];
            if (!control) return [name, jsonSnapshot(value, `contributor ${name}`)];
            return [name, this.#initial.typed(control, value)];
          }),
        ),
      );
    }

    #paintPresets() {
      this.#initial.paintPresets(this.#values);
    }

    // Whether the user stands in the preview, where a candidate can draw on the element
    // they stand at: a sample child's focus treatment, for one. Pressing a control face
    // that changes the candidate in one gesture leaves them standing there: taking focus
    // to the control would put that state away as the candidate changed.
    // Readable labels allow the browser's selection gesture. Text and colour controls
    // take focus to be operated, and a key reaches any control by moving focus onto it
    // first, so the keyboard still acts where it stands.
    #standsInPreview() {
      let at = document.activeElement;
      if (!this.#preview.contains(at)) return false;
      // A sample's frame holds focus for its child page, which may stand on nothing.
      while (at?.contentDocument) at = at.contentDocument.activeElement;
      return Boolean(at) && at !== at.ownerDocument.body;
    }

    #registerRegions() {
      this.#unregister = this.#regions.map((region) => registerReadingRegion(region));
    }

    #unregisterRegions() {
      for (const stop of this.#unregister) stop();
      this.#unregister = [];
    }

    #commands() {
      commands(this, "In a playground", [
        {
          id: "playground.choose",
          contextKeys: ["1"],
          bindingBadge: null,
          control: this.#submit,
          decision: true,
          title: () => this.#submit.textContent,
          when: () => !this.#choosing && this.#available(),
          run: () => this.#choose(),
        },
        {
          id: "playground.reset",
          keys: ["Alt+0"],
          control: this.#reset,
          title: "reset controls",
          run: () => this.#apply(this.#defaults),
        },
      ]);
    }

    #readInput(control) {
      return this.#initial.readInput(control);
    }

    #takeInputs() {
      const next = {
        ...this.#values,
        ...Object.fromEntries(
          this.#controls.map((control) => [
            control.getAttribute("name"),
            this.#parse(control, String(this.#readInput(control))),
          ]),
        ),
      };
      this.#apply(next);
    }

    #setInput(control, value) {
      this.#initial.setInput(control, value);
    }

    // The same reflection dresses the host and each live sample below its preview.
    #reflection() {
      return this.#initial.reflection(this.#values);
    }

    #apply(candidate, { remember = true } = {}) {
      const values = this.#normalize(candidate);
      // Contributors may read sibling controls through the public aggregate while
      // applying their own slice. Publish the complete input before invoking them.
      this.#values = values;
      for (const [name, contributor] of this.#contributors)
        contributor.apply(structuredClone(values[name]));
      for (const [name, value] of Object.entries(values)) {
        const control = this.#controlByName.get(name);
        if (control) this.#setInput(control, value);
      }
      const reflection = this.#reflection();
      wear(this, reflection);
      dressSamples(this, reflection);
      this.#renderOutput();
      this.#syncCopy();
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

    #renderOutput() {
      if (!this.#instructionProvider) {
        this.#initial.renderValues(this.#values);
        return;
      }
      const instruction = this.#instructionProvider(this.values);
      if (typeof instruction !== "string" || !instruction.trim())
        throw new Error("instruction provider must return non-empty text");
      this.#output.renderInstruction(instruction.trim());
    }

    #instruction() {
      return says(this.#output)
        .replace(/\s+/g, " ")
        .replace(/\s+([,.;:!?])/g, "$1")
        .trim();
    }

    #syncCopy() {
      if (!this.#copy) return;
      const instruction = this.#instruction();
      if (this.#copy.dataset.instruction === instruction) return;
      clearTimeout(this.#copyTimer);
      this.#copy.dataset.instruction = instruction;
      if (this.#copy.dataset.copyState !== "rest")
        this.#copy.dataset.copyState = "rest";
    }

    async #copyInstruction() {
      const instruction = this.#instruction();
      let feedback;
      try {
        await navigator.clipboard.writeText(instruction);
        feedback = "success";
      } catch {
        feedback = "error";
      }
      if (this.#instruction() !== instruction || !this.isConnected) return;
      clearTimeout(this.#copyTimer);
      this.#copy.dataset.copyState = feedback;
      this.#copyTimer = setTimeout(() => {
        this.#copy.dataset.copyState = "rest";
      }, 2000);
    }

    async #choose() {
      if (this.#choosing || !this.#available()) return;
      this.#choosing = true;
      this.#paintAvailability();
      this.#submit.setAttribute("aria-busy", "true");
      try {
        const event = await this.#controller.dispatch({
          kind: "action",
          verb: "choose",
          detail: { values: this.values, instruction: this.#instruction() },
        })?.delivery;
        if (event) notice("Playground settings sent");
      } finally {
        this.#choosing = false;
        this.#submit.removeAttribute("aria-busy");
        this.#paintAvailability();
      }
    }

    #paintAvailability() {
      if (!this.#submit) return;
      paintKeys();
    }

    #available() {
      return this.#controller.read().actions.choose?.available ?? false;
    }

    renderState(state) {
      if (!this.#ready) return true;
      const configuration = state.choose;
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
