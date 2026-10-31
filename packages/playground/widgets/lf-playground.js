import { createPlayground } from "./playground-view.js";
/* lf-playground: one declarative control loop with one durable decision.
 *
 * Authors define controls, presets, real preview markup, and an instruction in light
 * DOM. The retained view owns their DOM and typed control values;
 * this module owns the live mechanics: working state,
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
 * named default and its editor root, and get an immutable slice handle; set replaces
 * that slice. After editing, pressing another control follows the browser's native
 * focus behavior; the rest of the preview keeps the focus state a candidate may
 * demonstrate. Required views subscribe to the aggregate and paint inside this
 * LeafElement's render, so local edits and canonical restoration share its failure
 * and presentation boundary.
 * Consumers retain native editors and keep no second configuration model. The view
 * retains their nodes and values across working configuration changes.
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
  compoundReadingRegionId,
  closeNativeLayer,
  copyControl,
  focusDestination,
  holdFocus,
  layoutChanged,
  onCurrentLocation,
  onPress,
  isNativeLayer,
  keeps,
  LeafElement,
  render,
  registerReadingRegion,
  reachedForWords,
  says,
  sizeObserver,
  tabStore,
  wear,
  whileConnected,
  focused,
  under,
  worksInside,
  commandsChanged,
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

    #view = null;
    #controlByName = new Map();
    #views = new Set();
    #contributorEditors = new Set();
    /** @type {Readonly<Record<string, unknown>>} */
    #defaults = Object.freeze({});
    #values = Object.freeze({});
    #pendingValues = {};
    #instructionProvider = null;
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
        stops.push(onPress((start) => this.#holdRangePreview(start, signal)));
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
          const instruction = this.#view.instruction;
          if (innerWidth !== width && instruction && isNativeLayer(instruction))
            closeNativeLayer(instruction);
          width = innerWidth;
        };
        window.addEventListener("resize", putAway, { signal });
        this.#draw();
        return () => {
          observer.disconnect();
          for (const stop of stops) stop();
        };
      });
    }

    get values() {
      return this.#values;
    }

    registerContributor(name, defaultSnapshot, editor) {
      if (!this.#ready) throw new Error("playground is not ready");
      if (!NAME.test(name ?? "")) throw new Error(`invalid contributor name ${name}`);
      if (this.#controlByName.has(name))
        throw new Error(`contributor ${name} collides with a control`);
      if (Object.hasOwn(this.#defaults, name))
        throw new Error(`repeats contributor ${name}`);
      if (!under(editor, this))
        throw new Error(`contributor ${name} needs an editor in its playground`);
      const initial = jsonSnapshot(defaultSnapshot, `contributor ${name}`);
      const restored = Object.hasOwn(this.#pendingValues, name)
        ? jsonSnapshot(this.#pendingValues[name], `contributor ${name}`)
        : initial;
      this.#defaults = Object.freeze({ ...this.#defaults, [name]: initial });
      this.#values = Object.freeze({ ...this.#values, [name]: restored });
      this.#contributorEditors.add(editor);
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
      const restore = holdFocus(this);
      this.#view = createPlayground(this);
      render(this.#view.render(), this.#view.root ?? this, { host: this });
      restore?.();
      const initial = this.#view;
      this.#controlByName = initial.controlByName;
      this.#defaults = initial.defaults;
      this.#values = initial.values;
      this.#pendingValues = Object.fromEntries(
        Object.entries(initial.storedCandidate ?? {}).filter(
          ([name]) => !Object.hasOwn(this.#defaults, name),
        ),
      );
      this.#preview = initial.preview;
      this.#interactive = Boolean(initial.submit);
      this.#submit = initial.submit;
      this.#reset = initial.reset;
      this.#regions = initial.regions.map((region) => ({
        ...region,
        id: compoundReadingRegionId(this, region.name),
      }));
      const reflection = this.#view.reflection(this.#values);
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
        for (const control of initial.controls)
          control.addEventListener("input", (event) => {
            if (!initial.isInput(control, event.target)) return;
            this.#set(
              control.getAttribute("name"),
              initial.parse(control, String(initial.readInput(control))),
            );
          });
        for (const [preset, button] of initial.presetButtons)
          button.addEventListener("click", () => {
            this.#values = this.#normalize({
              ...this.#values,
              ...initial.presetSettings.get(preset),
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
        initial.copy = copy;
        instruction.addEventListener("toggle", (event) => {
          keeps(reveal, "aria-expanded", event.newState === "open");
          commandsChanged(this);
        });
        this.addEventListener("mousedown", (event) => {
          const target = /** @type {Element} */ (event.target);
          if (target.closest(".lf-playground-control-label")) return;
          const pressed = target.closest(ONE_PRESS);
          if (
            pressed?.closest("lf-playground") === this &&
            !this.#preview.contains(pressed)
          ) {
            const currentLocation = this.#previewLocation();
            if (!currentLocation) return;
            const selection = getSelection();
            if (selection && !this.#preview.contains(selection.focusNode))
              selection.removeAllRanges();
            const range = target.closest('input[type="range"]');
            if (!range) event.preventDefault();
          }
        });
        this.#commands();
      }
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
            return [name, this.#view.typed(control, value)];
          }),
        ),
      );
    }

    // Native range focus and dragging share a default: cancelling it cancels the
    // drag. Return at departure, early enough that Firefox never lends focus to
    // the range, and keep the return through WebKit's later native focus steps.
    // The canonical press owns this closure until its compatibility events finish.
    #holdRangePreview(start, connected) {
      if (start.button !== 0) return;
      const target = /** @type {Element} */ (start.composedPath()[0]);
      const range = target.closest('input[type="range"]');
      const pressed = target.closest(ONE_PRESS);
      if (
        !range ||
        pressed?.closest("lf-playground") !== this ||
        this.#preview.contains(pressed)
      )
        return;
      const currentLocation = this.#previewLocation();
      if (!currentLocation) return;
      const hold = new AbortController();
      const signal = AbortSignal.any([connected, hold.signal]);
      const close = () => hold.abort();
      const restore = (at) => {
        if (signal.aborted) return;
        if (at && at !== document.body && at !== range && at !== currentLocation) {
          close();
          return;
        }
        focusDestination(currentLocation, "return");
        const sample = currentLocation.closest("lf-sample");
        if (sample && currentLocation.localName === "iframe")
          void sample.restoreCurrentLocation()?.catch(() => {});
      };
      const stop = onCurrentLocation((at, cause) => {
        if (cause === "step") close();
        else if (at !== currentLocation) restore(at);
      });
      signal.addEventListener("abort", stop, { once: true });
      if (currentLocation.localName === "iframe") {
        // The parent window activates before the range receives element focus.
        window.addEventListener("focus", () => restore(null), { signal });
      } else {
        currentLocation.addEventListener(
          "blur",
          (event) => restore(event.relatedTarget),
          {
            once: true,
            signal,
          },
        );
      }
      return (_end, completed) => {
        if (completed) restore(focused());
        else close();
        return close;
      };
    }

    // Whether the user is in the preview, where a candidate can draw on the element
    // they stand at: a sample child's focus treatment, for one. Pressing a control face
    // that changes the candidate in one gesture leaves them there: taking focus
    // to the control would put that state away as the candidate changed.
    // Readable labels allow the browser's selection gesture. Text, colour and select
    // controls take focus to be operated, and a key reaches any control by moving focus onto it
    // first, so the keyboard still acts where it stands.
    // Contributors declare which DOM edits their values. The rest of the preview
    // can demonstrate any focused element, including an input, so its element type
    // cannot tell an editor from a candidate whose focus is being compared.
    #previewLocation() {
      let at = focused(document);
      if (
        !under(at, this.#preview) ||
        at.closest("lf-playground-control") ||
        [...this.#contributorEditors].some((editor) => under(at, editor))
      )
        return null;
      while (at?.localName === "iframe") {
        // The sample owns its opaque child's location; do not inspect its document.
        const sample = at.closest("lf-sample");
        if (sample) return sample.focusedContent ? at : null;
        at = at.contentDocument?.activeElement;
      }
      return at && at !== at.ownerDocument.body ? at : null;
    }

    #commands() {
      this.lfCommands = {
        title: "In a playground",
        rows: [
          {
            id: "playground.choose",
            contextKeys: ["1"],
            bindingBadge: null,
            control: this.#submit,
            decision: true,
            commits: true,
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
        ],
      };
      commandsChanged(this);
    }

    #set(name, value) {
      this.#values = Object.freeze({ ...this.#values, [name]: value });
      this.#draw();
    }

    #draw() {
      this.requestUpdate();
      this.performUpdate();
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
      const reflection = this.#view.reflection(this.#values);
      wear(this, reflection);
      // Keep not-yet-declared tab values without another copy of known working slices.
      tabStore.set(
        `lf-playground:${this.id}`,
        JSON.stringify({ ...this.#pendingValues, ...this.#values }),
      );
      for (const paint of this.#views) paint(this.#values);
      layoutChanged(this);
      commandsChanged(this);
    }

    #providedInstruction() {
      if (!this.#instructionProvider) return null;
      const instruction = this.#instructionProvider(this.values);
      if (!instruction.trim())
        throw new Error("instruction provider must return non-empty text");
      return instruction.trim();
    }

    #instruction() {
      const provided = this.#providedInstruction();
      if (provided !== null) return provided;
      return says(this.#view.output, { format: "lines" }).trim();
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
      const template = this.#view.render({
        values: this.#values,
        instruction: this.#providedInstruction(),
        chosen: () => this.#chosen(),
      });
      this.#paint();
      return template;
    }
  },
);
