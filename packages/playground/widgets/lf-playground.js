/* lf-playground: one declarative control loop with one durable decision.
 *
 * Authors define controls, presets, real preview markup, and an instruction in light
 * DOM. The synchronous initial producer owns their DOM and typed control values;
 * this module adopts that drawing and owns the live mechanics: working state,
 * tab-local persistence, CSS reflection, instruction copying, commands, and
 * the final recordless action. Intermediate changes never enter Leaf's event log.
 * The instruction opens from its actions in a popover over the page, so reading it
 * moves nothing the user set or pressed, in any Layout; the log never records it. The
 * popover's head holds Leaf's copy control (`copyControl`). Rejected: unfolding
 * the instruction in the pane, which had to grow below the bar in a flowing page and
 * above it at the foot of a held workspace, and still moved the bar wherever a stage
 * at its floor, a resize or a short window left it no room (2026-10-25).
 *
 * The playground owns the complete working configuration. Contributors declare a
 * named default and get an immutable slice handle; set replaces that slice. Required
 * views subscribe to the aggregate and paint inside this LeafElement's render, so
 * local edits and canonical restoration share its failure and presentation boundary.
 * Consumers retain native editors and keep no second configuration model. The initial
 * producer draws once; this module adopts its nodes and values without rebuilding.
 * Values awaiting a contributor declaration stay pending until it joins. They are
 * restoration input, never another working model. Simple previews read reflected
 * --playground-NAME properties and data-playground-NAME attributes on the host and
 * its sample roots.
 *
 * Projection is deliberately separate from working state. Only a newly chosen action,
 * made in this tab or elsewhere, replaces the working values. A repeated projection
 * keeps them, and so does an undo, which withdraws the decision and leaves the controls
 * as the user set them, ready to adjust and resubmit; Reset returns to the authored
 * defaults. Where an undo or a refused choice makes an earlier choice current again,
 * the controls show values that differ from the decided ones, as any unsent edit does.
 * Two facts identify a new choice. Its identity differs from the last one drawn, which
 * tells it from a repeated projection, equal-valued choices included; the attempt
 * stays stable when a local gesture receives its durable event id. And it is later in
 * the log than any choice this tab has drawn, which tells it from an earlier choice an
 * undo makes current again: a pending choice is this tab's newest gesture, and a
 * durable one compares by its seq. The submit control withdraws the current choice
 * while its values and instruction match the working configuration; editing either
 * makes it submit a replacement. Its face derives from that comparison, never from
 * delivery timing or a separate saved flag. */
import {
  commands,
  compoundReadingRegionId,
  closeNativeLayer,
  copyControl,
  focusDestination,
  layoutChanged,
  initialRender,
  isNativeLayer,
  keeps,
  keepsText,
  LeafElement,
  nothing,
  paintKeys,
  registerReadingRegion,
  reachedForWords,
  says,
  sizeObserver,
  tabStore,
  wear,
  whileConnected,
  focused,
  worksInside,
} from "/runtime/widget-api.js";
import "./lf-playground-output.js";

const NAME = /^[a-z0-9][a-z0-9-]*$/;
// What one pointer press operates: a preset, Reset, and the controls whose press or
// drag is the whole gesture. Their readable labels remain ordinary selection targets.
const ONE_PRESS = [
  ".lf-playground-preset",
  ".lf-playground-reset",
  '.lf-playground-choice:not([appearance="select"])',
  ...["toggle", "range"].map((kind) => `.lf-playground-${kind}`),
].join(", ");

const sameKeys = (left, right) =>
  left.length === right.length && left.every((key, index) => key === right[index]);

// Configuration objects have no meaningful key order, including contributor slices.
const configurationJSON = (value) =>
  JSON.stringify(value, (_key, item) =>
    item && typeof item === "object" && !Array.isArray(item)
      ? Object.fromEntries(
          Object.keys(item)
            .sort()
            .map((key) => [key, item[key]]),
        )
      : item,
  );

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
  class extends LeafElement {
    // What the obligation was answered with: the instruction the chosen configuration sent.
    static answerWords(value) {
      return value.instruction;
    }

    #initial = null;
    #controls = [];
    #controlByName = new Map();
    #views = new Set();
    #presetSettings = new Map();
    #presetButtons = new Map();
    /** @type {Readonly<Record<string, unknown>>} */
    #defaults = Object.freeze({});
    #values = Object.freeze({});
    #pendingValues = {};
    #instructionProvider = null;
    #output = null;
    #preview = null;
    #submit = null;
    #reset = null;
    #projected = undefined;
    #drawnThrough = -Infinity;
    #ready = false;
    #interactive = false;
    #regions = [];

    // A build that throws leaves the playground showing its failure (LeafElement).
    setup() {
      this.#build();
      this.#ready = true;
      whileConnected(this, (signal) => {
        const stops = this.#regions.map((region) => registerReadingRegion(region));
        // The narrow layout places shared controls above the stage. Their actual
        // height is also the landing inset for its content and any sticky toolbar.
        const controls = this.#regions.find((region) => region.name === "controls");
        const split = /** @type {HTMLElement} */ (
          this.querySelector(":scope > .lf-playground-split")
        );
        const observer = sizeObserver((entries) => {
          split.style.setProperty(
            "--playground-controls-height",
            `${entries[0].borderBoxSize[0].blockSize}px`,
          );
        });
        if (controls) observer.observe(controls.host);
        // The instruction is a glance at the window's middle; a window changing width
        // puts it away rather than reflowing it under the user, which also kept Web
        // Awesome's copy icon re-measuring through the resize (a ResizeObserver loop).
        // Height alone changes as a phone's toolbars come and go, which keeps it.
        let width = innerWidth;
        const putAway = () => {
          const instruction = this.#initial.instruction;
          if (innerWidth !== width && instruction && isNativeLayer(instruction))
            closeNativeLayer(instruction);
          width = innerWidth;
        };
        window.addEventListener("resize", putAway, { signal });
        this.#paintAvailability();
        return () => {
          observer.disconnect();
          for (const stop of stops) stop();
        };
      });
    }

    get values() {
      return this.#values;
    }

    registerContributor(name, defaultSnapshot) {
      if (!this.#ready) throw new Error("playground is not ready");
      if (!NAME.test(name ?? "")) throw new Error(`invalid contributor name ${name}`);
      if (this.#controlByName.has(name))
        throw new Error(`contributor ${name} collides with a control`);
      if (Object.hasOwn(this.#defaults, name))
        throw new Error(`repeats contributor ${name}`);
      const initial = jsonSnapshot(defaultSnapshot, `contributor ${name}`);
      const restored = Object.hasOwn(this.#pendingValues, name)
        ? jsonSnapshot(this.#pendingValues[name], `contributor ${name}`)
        : initial;
      this.#defaults = Object.freeze({ ...this.#defaults, [name]: initial });
      this.#values = Object.freeze({ ...this.#values, [name]: restored });
      delete this.#pendingValues[name];
      this.#draw();
      return Object.freeze({
        get: () => this.#values[name],
        set: (value) => this.#set(name, jsonSnapshot(value, `contributor ${name}`)),
      });
    }

    // Views belong to the subscribing component's connection. Declared slices belong
    // to this playground's lifetime; reconnecting keeps their handles and values.
    subscribe(paint) {
      this.#views.add(paint);
      this.#draw();
      return () => this.#views.delete(paint);
    }

    registerInstructionProvider(provider) {
      if (!this.#ready) throw new Error("playground is not ready");
      if (this.#instructionProvider)
        throw new Error("playground already has an instruction provider");
      this.#instructionProvider = provider;
      this.#draw();
    }

    #build() {
      this.#initial = initialRender(this);
      const initial = this.#initial;
      this.#controls = initial.controls;
      this.#controlByName = initial.controlByName;
      this.#defaults = initial.defaults;
      this.#values = initial.values;
      this.#pendingValues = Object.fromEntries(
        Object.entries(initial.storedCandidate ?? {}).filter(
          ([name]) => !Object.hasOwn(this.#defaults, name),
        ),
      );
      this.#output = initial.output;
      this.#preview = initial.preview;
      this.#interactive = Boolean(initial.submit);
      this.#submit = initial.submit;
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
      if (this.#interactive) {
        this.addEventListener("click", (event) => {
          const target = /** @type {Element} */ (event.target);
          const choice = target.closest("lf-playground-choice");
          if (!choice || choice.closest("lf-playground") !== this) return;
          if (reachedForWords(choice) || worksInside(target, choice)) return;
          const radio = /** @type {HTMLInputElement} */ (
            choice.querySelector(":scope > .choice > input")
          );
          focusDestination(radio, "press");
          radio.click();
        });
        for (const control of this.#controls)
          control.addEventListener("input", (event) => {
            const input = initial.inputs.get(control.getAttribute("name"));
            if (
              !(Array.isArray(input)
                ? input.includes(event.target)
                : input === event.target)
            )
              return;
            this.#set(
              control.getAttribute("name"),
              this.#parse(control, String(this.#initial.readInput(control))),
            );
          });
        for (const [preset, button] of this.#presetButtons)
          button.addEventListener("click", () => {
            this.#values = this.#normalize({
              ...this.#values,
              ...this.#presetSettings.get(preset),
            });
            this.#draw();
          });
        const { reveal, instruction } = initial;
        // Leaf's copy control in the popover's head. A code block's (`copyBlock`) hides
        // while its block is away and came back a frame or more after the popover
        // opened, after a Tab had passed it by.
        const copy = copyControl("lf-quiet-action lf-playground-copy", {
          label: "Copy instruction",
          success: "Instruction copied",
          error: "Unable to copy instruction",
        });
        copy.addEventListener(
          "click",
          () => {
            copy.value = this.#instruction();
          },
          { capture: true },
        );
        instruction.firstElementChild.append(copy);
        instruction.addEventListener("toggle", (event) => {
          keeps(reveal, "aria-expanded", event.newState === "open");
          paintKeys();
        });
        this.addEventListener("mousedown", (event) => {
          const target = /** @type {Element} */ (event.target);
          if (target.closest(".lf-playground-control-label")) return;
          const pressed = target.closest(ONE_PRESS);
          if (
            pressed?.closest("lf-playground") === this &&
            !this.#preview.contains(pressed) &&
            this.#standsInPreview()
          ) {
            const selection = getSelection();
            if (selection && !this.#preview.contains(selection.focusNode))
              selection.removeAllRanges();
            const range = target.closest('input[type="range"]');
            if (range) {
              // Native range focus and track operation share a browser default.
              // Return focus after that default takes it, so dragging remains native
              // while the preview keeps showing its focused state. An opaque sample
              // restores its current location through its private port.
              let currentLocation = focused(document);
              while (currentLocation?.contentDocument)
                currentLocation = currentLocation.contentDocument.activeElement;
              range.addEventListener(
                "focus",
                () => {
                  const sample = currentLocation?.closest?.("lf-sample");
                  focusDestination(currentLocation, "return");
                  if (sample && currentLocation?.localName === "iframe")
                    void sample.restoreCurrentLocation()?.catch(() => {});
                },
                { once: true },
              );
            } else event.preventDefault();
          }
        });
        this.#commands();
      }
      this.#paintPresets();
    }

    #parse(control, raw) {
      return this.#initial.parse(control, raw);
    }

    #normalize(candidate) {
      const names = Object.keys(this.#defaults).sort();
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

    // Whether the user is in the preview, where a candidate can draw on the element
    // they stand at: a sample child's focus treatment, for one. Pressing a control face
    // that changes the candidate in one gesture leaves them there: taking focus
    // to the control would put that state away as the candidate changed.
    // Readable labels allow the browser's selection gesture. Text, colour and select
    // controls take focus to be operated, and a key reaches any control by moving focus onto it
    // first, so the keyboard still acts where it stands.
    // A control written in the preview is not a candidate: standing on one is standing
    // on a control.
    #standsInPreview() {
      let at = focused(document);
      if (!this.#preview.contains(at) || at.closest("lf-playground-control"))
        return false;
      // A sample's frame holds focus for its child page, which may stand on nothing.
      while (at?.contentDocument) at = at.contentDocument.activeElement;
      if (at?.localName === "iframe")
        return Boolean(at.closest("lf-sample")?.focusedContent);
      return Boolean(at) && at !== at.ownerDocument.body;
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
          when: () => (this.#chosen() ? Boolean(this.#undo()) : this.#available()),
          run: () => this.#choose(),
        },
        {
          id: "playground.reset",
          keys: ["Alt+0"],
          control: this.#reset,
          title: "reset controls",
          run: () => {
            this.#restore(this.#defaults);
            this.#draw();
          },
        },
      ]);
    }

    #set(name, value) {
      this.#values = Object.freeze({ ...this.#values, [name]: value });
      this.#draw();
    }

    #draw() {
      this.requestUpdate();
      this.performUpdate();
    }

    #setInput(control, value) {
      this.#initial.setInput(control, value);
    }

    // The same reflection dresses the host and each live sample below its preview.
    #reflection() {
      return this.#initial.reflection(this.#values);
    }

    #restore(candidate) {
      // A chosen snapshot can arrive before its structured editor declares its slice.
      const known = Object.entries(candidate).filter(([name]) =>
        Object.hasOwn(this.#defaults, name),
      );
      this.#values = this.#normalize(Object.fromEntries(known));
      this.#pendingValues = Object.fromEntries(
        Object.entries(candidate).filter(
          ([name]) => !Object.hasOwn(this.#defaults, name),
        ),
      );
    }

    #paint() {
      for (const [name, control] of this.#controlByName)
        this.#setInput(control, this.#values[name]);
      const reflection = this.#reflection();
      wear(this, reflection);
      this.#renderOutput();
      this.#paintPresets();
      // Keep not-yet-declared tab values without another copy of known working slices.
      tabStore.set(
        this.#storeKey(),
        JSON.stringify({ ...this.#pendingValues, ...this.#values }),
      );
      for (const paint of this.#views) paint(this.#values);
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
      if (!instruction.trim())
        throw new Error("instruction provider must return non-empty text");
      this.#output.renderInstruction(instruction.trim());
    }

    #instruction() {
      return says(this.#output)
        .replace(/\s+/g, " ")
        .replace(/\s+([,.;:!?])(?=\s|$)/g, "$1")
        .trim();
    }

    #choose() {
      const chosen = this.#chosen();
      const undo = chosen ? this.#undo() : null;
      if (chosen ? !undo : !this.#available()) return;
      this.controller.dispatch(
        chosen
          ? { kind: "undo", target: undo.attempt ?? undo.id }
          : {
              kind: "action",
              verb: "choose",
              detail: { values: this.values, instruction: this.#instruction() },
              says: "Playground settings",
            },
      );
    }

    #paintAvailability() {
      if (!this.#submit) return;
      keepsText(
        this.#submit.firstElementChild,
        this.#chosen()
          ? "Undo choice"
          : (this.getAttribute("submit-label") ?? "Use these settings"),
      );
      paintKeys();
    }

    #chosen() {
      const choice = this.state?.choose;
      return Boolean(
        choice?.action &&
        choice.detail.instruction === this.#instruction() &&
        configurationJSON(choice.detail.values) ===
          configurationJSON({ ...this.#pendingValues, ...this.values }),
      );
    }

    #undo() {
      const action = this.reading.actions.choose;
      const latest = action.inForce[0]?.event;
      return action.undo.find((event) => event.id === latest?.id) ?? null;
    }

    #available() {
      return this.reading.actions.choose?.available ?? false;
    }

    // Only a new choice replaces local edits (the header says why). A change to the
    // reading's availability draws again too, and paints the keys.
    render() {
      const configuration = this.state.choose;
      const choice = Object.values(this.reading.provenance).find(
        ({ event }) => event.action === "choose",
      )?.event;
      const projected = choice ? (choice.attempt ?? choice.id) : null;
      if (this.#projected !== projected) {
        this.#projected = projected;
        if (choice && !(choice.seq <= this.#drawnThrough))
          this.#restore(configuration.detail.values);
      }
      if (Number.isInteger(choice?.seq))
        this.#drawnThrough = Math.max(this.#drawnThrough, choice.seq);
      this.#paint();
      this.#paintAvailability();
      return nothing;
    }
  },
);
