import { createPlayground } from "./playground-view.js";
/* lf-playground: one declarative control loop with one durable decision.
 *
 * Authors define controls, presets, real preview markup, and an instruction in light
 * DOM. The retained view owns their DOM and typed control values;
 * this module owns the live mechanics: working state and its record,
 * CSS reflection, instruction copying, commands, and the final recordless action.
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
 * The working configuration is page state: the `tune` verb records it, and declares
 * `unsent`, since it is what the user hasn't sent. So a reload, every tab,
 * another browser and the agent's page state all read the same settings, and a comment
 * on the preview names a configuration the log holds. The controls draw
 * `#values` at once and record them when a gesture ends: a press, a committed edit
 * (`change`), or a second without input, which catches typing a field hasn't
 * committed and a contributor's editor whose events never reach the host. So a drag or
 * a word being typed records once, and submitting records them first. Only a tune the controls haven't drawn replaces `#values`: another tab's,
 * or one an undo makes current, which steps the controls back a gesture. It leaves the
 * edits this tab hasn't recorded yet (`#unsent`), so words being typed stay put. Choosing
 * never changes them, so undoing a choice leaves the controls as the user set them,
 * ready to adjust and resubmit; Reset records the authored defaults. Rejected: tab-local
 * storage, which lost the settings with the tab and kept them from the agent, who
 * answered comments on the preview without knowing what it showed (2026-10-30).
 * Each tune records the whole configuration, so a preset or Reset is one gesture Undo
 * takes back whole; when two tabs' records cross in flight, the later one sets every
 * field. Rejected: a tune per field, which would split those gestures (2026-10-31).
 * The submit control withdraws the current choice while its values and instruction
 * match the working configuration; editing either makes it submit a replacement. Its
 * face derives from that comparison, never from delivery timing or a separate saved
 * flag.
 *
 * Under `actions="page"` the page draws the submission and Reset, and
 * `registerActions` hands this playground the two buttons. They become the controls of
 * its commands, which wire their presses and keep the digit, On me's arrival and
 * availability, and this module writes the submission's words, as it does for its own,
 * since the words must say what the press will do. The page's CSS draws them: they are
 * the page's elements, not Leaf's controls. Rejected: methods the page calls from its
 * own handlers with a decision state to label from, which would leave every page to
 * restate when the press withdraws the choice. */
import {
  afterPresentation,
  compoundReadingRegionId,
  closeNativeLayer,
  copyControl,
  failSoft,
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
  wear,
  whileConnected,
  focused,
  under,
  worksInside,
  commandsChanged,
} from "/runtime/widget-api.js";
import "./lf-playground-output.js";

/** @typedef {null | string | number | boolean | readonly JSONSnapshot[] | {readonly [name: string]: JSONSnapshot}} JSONSnapshot */
/** @typedef {Readonly<Record<string, JSONSnapshot>>} Configuration */
/** @typedef {ReturnType<typeof createPlayground>} PlaygroundView */

const NAME = /^[a-z0-9][a-z0-9-]*$/;
// How long the settings wait without input before an edit no event ended is recorded.
const PAUSE_MS = 1000;
// What one pointer press operates: a preset, Reset, and the controls whose press or
// drag is the whole gesture. Their readable labels remain ordinary selection targets.
const ONE_PRESS = [
  ".lf-playground-preset",
  ".lf-playground-reset",
  '.lf-playground-choice:not([appearance="select"])',
  ...["toggle", "range"].map((kind) => `.lf-playground-${kind}`),
].join(", ");

/** @param {readonly string[]} left @param {readonly string[]} right */
const sameKeys = (left, right) =>
  left.length === right.length && left.every((key, index) => key === right[index]);

// Configuration objects have no meaningful key order, including contributor slices.
/** @param {unknown} value */
const configurationJSON = (value) =>
  JSON.stringify(value, (_key, /** @type {unknown} */ item) =>
    item && typeof item === "object" && !Array.isArray(item)
      ? Object.fromEntries(
          Object.entries(item).sort(([left], [right]) =>
            left < right ? -1 : left > right ? 1 : 0,
          ),
        )
      : item,
  );

/** @param {unknown} value @param {string} [path] @returns {JSONSnapshot} */
function jsonSnapshot(value, path = "configuration") {
  if (value === null || typeof value === "string" || typeof value === "boolean")
    return value;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new Error(`${path} needs finite numbers`);
    return value;
  }
  if (Array.isArray(value)) {
    /** @type {unknown[]} */
    const items = value;
    return Object.freeze(
      Array.from(items, (item, index) => jsonSnapshot(item, `${path}[${index}]`)),
    );
  }
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
    /** @param {unknown} value */
    static answerWords(value) {
      if (
        !value ||
        typeof value !== "object" ||
        !("instruction" in value) ||
        typeof value.instruction !== "string"
      )
        throw new Error("A playground answer must contain its instruction");
      return value.instruction;
    }

    /** @type {PlaygroundView | null} */
    #renderedView = null;
    get #view() {
      if (!this.#renderedView) throw new Error("The playground has not built its view");
      return this.#renderedView;
    }
    /** @type {Map<string, HTMLElement>} */
    #controlByName = new Map();
    /** @type {Set<(configuration: Configuration) => void>} */
    #views = new Set();
    /** @type {Set<Element>} */
    #contributorEditors = new Set();
    /** @type {Configuration} */
    #defaults = Object.freeze({});
    /** @type {Configuration} */
    #values = Object.freeze({});
    /** @type {Record<string, JSONSnapshot>} */
    #pendingValues = {};
    /** @type {Set<string>} */
    #unsent = new Set();
    #pause = 0;
    /** @type {((configuration: Configuration) => string) | null} */
    #instructionProvider = null;
    get #preview() {
      return this.#view.preview;
    }
    /** @type {HTMLButtonElement | null} */
    #submit = null;
    /** @type {HTMLButtonElement | null} */
    #reset = null;
    /** @type {string | null | undefined} */
    #drawn = undefined;
    #ready = false;
    #interactive = false;
    /** @type {(PlaygroundView["regions"][number] & {id: string})[]} */
    #regions = [];

    // A build that throws leaves the playground showing its failure (LeafElement).
    setup() {
      this.#build();
      this.#ready = true;
      // A page that draws the actions hands them over in its view's `declare`, which
      // the page's first presentation waits for (`whileInterfaceConnected`). Missing
      // then, nothing would let the user answer, so the playground fails where `page
      // check` reads it. A playground arriving after that presentation, in a revision
      // applied in place or a message, has no settled point of its own to wait for, so
      // only the page's first presentation is checked.
      if (
        this.#view.pageActions &&
        this.#interactive &&
        !document.body.hasAttribute("data-lf-presented")
      )
        afterPresentation(() => {
          if (this.isConnected && !this.#submit)
            failSoft(
              this,
              new Error(
                'actions="page" needs the page script to pass its Save and Reset ' +
                  "buttons to playground.registerActions({submit, reset}) in declare",
              ),
            );
        });
      whileConnected(this, (signal) => {
        const stops = this.#regions.map((region) => registerReadingRegion(region));
        stops.push(onPress((start) => this.#holdRangePreview(start, signal)));
        // The narrow layout places shared controls above the stage. Their actual
        // height is also the landing inset for its content and any sticky toolbar.
        const controls = this.#regions.find((region) => region.name === "controls");
        /** @type {HTMLElement | null} */
        const split = this.querySelector(":scope > .lf-playground-split");
        if (!split) throw new Error("The playground needs its rendered split view");
        const observer = sizeObserver((entries) => {
          for (const entry of entries) {
            const box = entry.borderBoxSize[0];
            if (!box) continue;
            split.style.setProperty(
              "--playground-controls-height",
              `${box.blockSize}px`,
            );
            return;
          }
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
        // Leaving the page records edits the pause hasn't yet, and nothing else: a
        // value the controls can't hold draws as its default without being an edit.
        const leave = () => this.#unsent.size && this.#commit();
        document.addEventListener(
          "visibilitychange",
          () => document.visibilityState === "hidden" && leave(),
          { signal },
        );
        window.addEventListener("pagehide", leave, { signal });
        this.#draw();
        // An edit left unrecorded across a disconnection records once input pauses.
        if (this.#unsent.size) this.#recordLater();
        return () => {
          observer.disconnect();
          for (const stop of stops) stop();
          clearTimeout(this.#pause);
        };
      });
    }

    get values() {
      return this.#values;
    }

    /** @param {string} name @param {unknown} defaultSnapshot @param {Element} editor */
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
        set: (/** @type {unknown} */ value) =>
          this.#set(name, jsonSnapshot(value, `contributor ${name}`)),
      });
    }

    // Views belong to the subscribing component's connection. Declared slices belong
    // to this playground's lifetime; reconnecting keeps their handles and values.
    /** @param {(configuration: Configuration) => void} paint */
    subscribe(paint) {
      this.#views.add(paint);
      this.#draw();
      return () => this.#views.delete(paint);
    }

    /** @param {(configuration: Configuration) => string} provider */
    registerInstructionProvider(provider) {
      if (!this.#ready) throw new Error("playground is not ready");
      if (this.#instructionProvider)
        throw new Error("playground already has an instruction provider");
      this.#instructionProvider = provider;
      this.#draw();
    }

    // The page's own submission and Reset, under `actions="page"` (the header says why
    // this module labels the submission).
    /** @param {import("./playground-view.js").PlaygroundActions} actions */
    registerActions({ submit, reset }) {
      if (!this.#ready) throw new Error("playground is not ready");
      if (!this.#view.pageActions)
        throw new Error('playground draws its own actions; set actions="page"');
      if (this.#submit) throw new Error("playground already has its actions");
      for (const [name, button] of [
        ["submit", submit],
        ["reset", reset],
      ])
        if (!(button instanceof HTMLButtonElement))
          throw new Error(`registerActions needs a ${name} button`);
      // A quotation sends nothing, so it shows neither.
      if (!this.#interactive) {
        submit.hidden = reset.hidden = true;
        return;
      }
      this.#view.give({ submit, reset });
      this.#submit = submit;
      this.#reset = reset;
      this.#commands();
      this.#draw();
    }

    #build() {
      const restore = holdFocus(this);
      this.#renderedView = createPlayground(this);
      render(this.#view.render(), this, { host: this });
      restore?.();
      const initial = this.#view;
      this.#controlByName = initial.controlByName;
      this.#defaults = initial.defaults;
      this.#values = initial.defaults;
      this.#interactive = initial.interactive;
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
          const target = event.target;
          if (!(target instanceof Element)) return;
          const choice = target.closest("lf-playground-choice");
          if (!choice || choice.closest("lf-playground") !== this) return;
          if (reachedForWords(choice) || worksInside(target, choice)) return;
          /** @type {HTMLInputElement | null} */
          const radio = choice.querySelector(":scope > .choice > input");
          if (!radio) throw new Error("A playground choice needs its rendered radio");
          focusDestination(radio, "press");
          radio.click();
        });
        // A gesture records the settings when it ends (the header says why). These
        // reach the host after the handlers inside it, a contributor's included.
        for (const type of ["change", "click"])
          this.addEventListener(type, () => this.#commit());
        for (const control of initial.controls)
          control.addEventListener("input", (event) => {
            if (!initial.isInput(control, event.target)) return;
            this.#set(
              initial.controlName(control),
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
        // opened, after a Tab had passed it by. A page that draws its own actions
        // shows the instruction where it was written, with no popover to copy from.
        if (instruction) {
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
            keeps(
              reveal,
              "aria-expanded",
              event instanceof ToggleEvent && event.newState === "open",
            );
            commandsChanged(this);
          });
        }
        this.addEventListener("mousedown", (event) => {
          const target = event.target;
          if (!(target instanceof Element)) return;
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

    /** @param {Configuration} candidate */
    #normalize(candidate) {
      const names = Object.keys(this.#defaults).sort();
      const keys = Object.keys(candidate).sort();
      if (!sameKeys(names, keys))
        throw new Error(
          `configuration needs exactly these fields: ${names.join(", ")}`,
        );
      return Object.freeze(
        Object.fromEntries(
          names.map((name) => [name, this.#typed(name, candidate[name])]),
        ),
      );
    }

    /** @param {string} name @param {unknown} value */
    #typed(name, value) {
      const control = this.#controlByName.get(name);
      if (!control) return jsonSnapshot(value, `contributor ${name}`);
      return this.#view.typed(control, value);
    }

    // Native range focus and dragging share a default: cancelling it cancels the
    // drag. Return at departure, early enough that Firefox never lends focus to
    // the range, and keep the return through WebKit's later native focus steps.
    // The canonical press owns this closure until its compatibility events finish.
    /** @param {PointerEvent} start @param {AbortSignal} connected */
    #holdRangePreview(start, connected) {
      if (start.button !== 0) return;
      const target = start.composedPath()[0];
      if (!(target instanceof Element)) return;
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
      const restore = (/** @type {EventTarget | null} */ at) => {
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
          (event) => restore(event instanceof FocusEvent ? event.relatedTarget : null),
          {
            once: true,
            signal,
          },
        );
      }
      return (/** @type {Event} */ _end, /** @type {boolean} */ completed) => {
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
        at?.closest("lf-playground-control") ||
        [...this.#contributorEditors].some((editor) => under(at, editor))
      )
        return null;
      while (at instanceof HTMLIFrameElement) {
        // The sample owns its opaque child's location; do not inspect its document.
        const sample = at.closest("lf-sample");
        if (sample) return sample.focusedContent ? at : null;
        at = at.contentDocument?.activeElement ?? null;
      }
      return at && at !== at.ownerDocument.body ? at : null;
    }

    // A page that draws its own actions has commands once it hands over their controls.
    #commands() {
      const submit = this.#submit;
      if (!submit) return;
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
            title: () => submit.textContent,
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
              this.#commit();
            },
          },
        ],
      };
      commandsChanged(this);
    }

    /** @param {string} name @param {JSONSnapshot} value */
    #set(name, value) {
      this.#values = Object.freeze({ ...this.#values, [name]: value });
      this.#unsent.add(name);
      this.#draw();
      this.#recordLater();
    }

    #recordLater() {
      clearTimeout(this.#pause);
      this.#pause = setTimeout(() => this.#commit(), PAUSE_MS);
    }

    #draw() {
      this.requestUpdate();
      this.performUpdate();
    }

    /** @param {Configuration} candidate */
    #restore(candidate) {
      // A recorded snapshot can arrive before its structured editor declares its slice,
      // and can predate a revision that added a control or dropped a choice: those
      // controls show their authored default.
      this.#values = Object.freeze(
        Object.fromEntries(
          Object.entries(this.#defaults).map(([name, authored]) => {
            if (!Object.hasOwn(candidate, name)) return [name, authored];
            try {
              return [name, this.#typed(name, candidate[name])];
            } catch {
              return [name, authored];
            }
          }),
        ),
      );
      this.#pendingValues = Object.fromEntries(
        Object.entries(candidate).filter(
          ([name]) => !Object.hasOwn(this.#defaults, name),
        ),
      );
    }

    // The tune in force, whose values are the settings the log holds; without one, it
    // holds the authored defaults.
    #tune() {
      return (
        Object.values(this.controller.read().provenance).find(
          ({ event }) => event.action === "tune",
        )?.event ?? null
      );
    }

    #commit() {
      clearTimeout(this.#pause);
      const values = { ...this.#pendingValues, ...this.#values };
      const recorded = this.#tune()?.detail.values ?? this.#defaults;
      if (!this.controller.read().actions.tune?.available) return;
      this.#unsent.clear();
      if (configurationJSON(values) === configurationJSON(recorded)) return;
      this.controller.dispatch({
        kind: "action",
        verb: "tune",
        detail: { values },
        says: "Changed the playground's settings",
      });
    }

    #paint() {
      const reflection = this.#view.reflection(this.#values);
      wear(this, reflection);
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
      if (!chosen) this.#commit();
      if (chosen) {
        if (!undo) return;
        this.controller.dispatch({
          kind: "undo",
          target: ("attempt" in undo ? undo.attempt : null) ?? undo.id,
        });
      } else {
        this.controller.dispatch({
          kind: "action",
          verb: "choose",
          detail: { values: this.values, instruction: this.#instruction() },
          says: "Playground settings",
        });
      }
    }

    #chosen() {
      const choice = this.state?.choose;
      return Boolean(
        choice &&
        "action" in choice &&
        choice.action &&
        choice.detail.instruction === this.#instruction() &&
        configurationJSON(choice.detail.values) ===
          configurationJSON({ ...this.#pendingValues, ...this.values }),
      );
    }

    #undo() {
      const action = this.controller.read().actions.choose;
      const latest = action?.inForce[0]?.event;
      return action?.undo.find((event) => event.id === latest?.id) ?? null;
    }

    #available() {
      return this.controller.read().actions.choose?.available ?? false;
    }

    // Only a tune the controls haven't drawn replaces their values (the header says
    // why); its attempt stays its identity once the server gives it an id. A change to
    // the reading's availability draws again too, and paints the keys.
    render() {
      const tune = this.#tune();
      const drawn = tune
        ? (("attempt" in tune ? tune.attempt : null) ?? tune.id)
        : null;
      if (this.#drawn !== drawn) {
        this.#drawn = drawn;
        const unsent = [...this.#unsent].map((name) => [name, this.#values[name]]);
        this.#restore({
          ...(tune?.detail.values ?? this.#defaults),
          ...Object.fromEntries(unsent),
        });
      }
      const template = this.#view.render({
        values: this.#values,
        instruction: this.#providedInstruction(),
        chosen: () => this.#chosen(),
      });
      this.#paint();
      return template;
    }

    // Edits made before the page could record them, such as while its state loads,
    // record once it can.
    /** @param {import("lit").PropertyValues} changed */
    updated(changed) {
      super.updated(changed);
      if (this.#unsent.size && this.controller.read().actions.tune?.available)
        this.#recordLater();
    }
  },
);
