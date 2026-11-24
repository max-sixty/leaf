import { createPlayground, same } from "./playground-view.js";
/* lf-playground: one form's working configuration, with one durable decision.
 *
 * Authors write the form as native fields among the preview's own markup, with presets
 * and an instruction. The retained view draws the regions around them and reads and
 * writes the fields (playground-view.js); this module owns the live mechanics: working
 * state and its record, CSS reflection, instruction copying, commands, and the final
 * recordless action.
 * The instruction opens from its actions in a popover over the page, so reading it
 * moves nothing the user set or pressed, in any Layout; the log never records it. The
 * popover's head holds Leaf's copy control (`copyControl`). Rejected: unfolding
 * the instruction in the pane, which had to grow below the bar in a flowing page and
 * above it at the foot of a held workspace, and still moved the bar wherever a stage
 * at its floor, a resize or a short window left it no room.
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
 * answered comments on the preview without knowing what it showed.
 * Each tune records the whole configuration, so a preset or Reset is one gesture Undo
 * takes back whole; when two tabs' records cross in flight, the later one sets every
 * field. Rejected: a tune per field, which would split those gestures.
 * The submit control withdraws the current choice while its values and instruction
 * match the working configuration; editing either makes it submit a replacement. Its
 * face derives from that comparison, never from delivery timing or a separate saved
 * flag. Each draw resolves a provider's instruction once; the view, command availability,
 * copying and submission consume that same text. An external input the element cannot
 * observe requests an update, as other inputs outside its reading do. Command reads
 * never call page code that prepares its next presentation.
 *
 * A `<button type="submit">` the page writes in the playground is its submission, and a
 * `<button type="reset">` beside it its Reset. They become the controls of its commands,
 * which wire their presses and keep the digit, On Me's arrival and availability, and
 * this module writes the submission's words, as it does for its own, since the words
 * must say what the press will do. The page's CSS draws them: they are the page's
 * elements, not Leaf's controls. Their form's own submission and reset do nothing; nor
 * does any submission of a form inside the playground, which would leave the page.
 * Rejected: methods the page calls from its own handlers with a decision state to label
 * from, which would leave every page to restate when the press withdraws the choice;
 * an attribute and a script call that handed over buttons the markup could name. */
import { render } from "/vendor/lit.js";
import {
  aimedAt,
  copyControl,
  focusDestination,
  holdFocus,
  onCurrentLocation,
  onPress,
  says,
  wear,
  whileConnected,
} from "/runtime/widget-api.js";
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { sizeObserver } from "/runtime/lib/frame-pass.js";
import { under } from "/runtime/lib/shadow-tree.js";
import "./lf-playground-output.js";

/** @typedef {null | string | number | boolean | readonly JSONSnapshot[] | {readonly [name: string]: JSONSnapshot}} JSONSnapshot */
/** @typedef {Readonly<Record<string, JSONSnapshot>>} Configuration */
/** @typedef {ReturnType<typeof createPlayground>} PlaygroundView */

const NAME = /^[a-z0-9][a-z0-9-]*$/;
// How long the settings wait without input before an edit no event ended is recorded.
const PAUSE_MS = 1000;
// What one pointer press operates: a preset, Reset, and the controls whose press or
// drag is the whole gesture, with the labels that hold a box or radio.
const ONE_PRESS = [
  ".lf-playground-preset",
  ".lf-playground-reset",
  'label:has(> input:is([type="checkbox"], [type="radio"]))',
  'input:is([type="checkbox"], [type="radio"], [type="range"])',
].join(", ");

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
    /** @type {PlaygroundView["fields"]} */
    #fields = new Map();
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
    /** @type {{value: string | null} | {error: unknown}} */
    #renderedInstruction = { value: null };
    get #preview() {
      const preview = this.#view.preview;
      if (!preview) throw new Error("The playground has not drawn its preview");
      return preview;
    }
    /** @type {HTMLButtonElement | null} */
    #submit = null;
    /** @type {HTMLButtonElement | null} */
    #reset = null;
    /** @type {unknown} */
    #drawn = undefined;
    #ready = false;
    #interactive = false;

    // A build that throws leaves the playground showing its failure (LeafElement).
    setup() {
      this.#build();
      this.#ready = true;
      whileConnected(this, (signal) => {
        const stopPress = onPress((start) => this.#holdRangePreview(start, signal));
        // The narrow layout places shared controls above the stage. Their actual
        // height is also the landing inset for its content and any sticky toolbar. A
        // quoted playground draws only its authored markup, with neither.
        const controls = this.#view.controls;
        /** @type {HTMLElement | null} */
        const split = this.querySelector(":scope > .lf-playground-split");
        const observer = sizeObserver((entries) => {
          for (const entry of entries) {
            const box = entry.borderBoxSize[0];
            if (!box) continue;
            split?.style.setProperty(
              "--lf-playground-controls-height",
              `${box.blockSize}px`,
            );
            return;
          }
        });
        if (controls) observer.observe(controls);
        // The instruction is a glance at the window's middle; a window changing width
        // puts it away rather than reflowing it under the user, which also kept Web
        // Awesome's copy icon re-measuring through the resize (a ResizeObserver loop).
        // Height alone changes as a phone's toolbars come and go, which keeps it.
        let width = innerWidth;
        const putAway = () => {
          const instruction = this.#view.instruction;
          if (innerWidth !== width && instruction) instruction.hidePopover();
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
          stopPress();
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
      if (this.#fields.has(name))
        throw new Error(`contributor ${name} collides with a field`);
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

    #build() {
      const restore = holdFocus(this);
      this.#renderedView = createPlayground(this);
      const initial = this.#view;
      this.#fields = initial.fields;
      this.#defaults = initial.defaults;
      // What the fields showed before the upgrade are edits, recorded once the page
      // can record them (playground-view.js says how they arise).
      this.#values = Object.freeze({ ...initial.defaults, ...initial.edited });
      for (const name of Object.keys(initial.edited)) this.#unsent.add(name);
      render(this.#view.render({ values: this.#values }), this, { host: this });
      restore?.();
      this.#interactive = initial.interactive;
      this.#submit = initial.submit;
      this.#reset = initial.reset;
      const reflection = this.#view.reflection(this.#values);
      wear(this, reflection);
      if (this.#interactive) {
        // A press on a candidate's body selects its radio (playground-view.js).
        this.addEventListener("click", (event) => {
          const target = event.target;
          if (!(target instanceof Element)) return;
          const pick = initial.candidate(target);
          if (!pick) return;
          if (aimedAt(event, pick.box) !== pick.box) return;
          event.preventDefault();
          focusDestination(pick.radio, "press");
          pick.radio.click();
        });
        // A gesture records the settings when it ends (the header says why). These
        // reach the host after the handlers inside it, a contributor's included.
        for (const type of ["change", "click"])
          this.addEventListener(type, () => this.#commit());
        this.addEventListener("input", (event) => {
          const changed = initial.input(event.target);
          if (changed) this.#set(changed.name, changed.value);
        });
        // The commands answer the submission and Reset (the header says why).
        this.addEventListener("submit", (event) => event.preventDefault());
        this.addEventListener("reset", (event) => {
          if (event.target === this.querySelector(":scope > .lf-playground-split"))
            event.preventDefault();
        });
        for (const [preset, button] of initial.presetButtons)
          button.addEventListener("click", () => {
            const settings = initial.presetSettings.get(preset) ?? {};
            initial.forget(Object.keys(settings));
            this.#values = this.#normalize({ ...this.#values, ...settings });
            this.#draw();
          });
        const { instruction } = initial;
        // Leaf's copy control in the popover's head. A code block's Copy hides
        // while its block is away and came back a frame or more after the popover
        // opened, after a Tab had passed it by. A page that draws its own actions
        // shows the instruction where it was written, with no popover to copy from.
        if (instruction) {
          const copy = copyControl("lf-playground-copy", {
            label: "Copy instruction",
            success: "Instruction copied",
            error: "Unable to copy instruction",
            role: "symbol",
          });
          copy.addEventListener(
            "click",
            () => {
              copy.value = this.#instruction();
            },
            { capture: true },
          );
          initial.copy = copy;
          instruction.addEventListener("toggle", () =>
            this.dispatchEvent(
              new CustomEvent("lf-commands", { bubbles: true, composed: true }),
            ),
          );
        }
        this.addEventListener("mousedown", (event) => {
          const target = event.target;
          if (!(target instanceof Element)) return;
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
      if (!same(names, keys))
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
      const field = this.#fields.get(name);
      if (!field) return jsonSnapshot(value, `contributor ${name}`);
      if (!field.holds(value)) throw new Error(`field ${name} can't hold ${value}`);
      // A multiple select's list, read from the log, freezes as a slice's does.
      return jsonSnapshot(value, `field ${name}`);
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
        if (completed) restore(document.activeElement);
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
      let at = document.activeElement;
      if (
        !under(at, this.#preview) ||
        this.#view.isField(at) ||
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
              this.#view.forget();
              this.#restore(this.#defaults);
              this.#draw();
              this.#commit();
            },
          },
        ],
      };
      this.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
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
      const tune = this.state?.tune;
      return tune && "action" in tune && tune.action ? tune : null;
    }

    #commit() {
      clearTimeout(this.#pause);
      const values = { ...this.#pendingValues, ...this.#values };
      const recorded = this.#tune()?.detail.values ?? this.#defaults;
      if (!this.state?.tune?.available) return;
      this.#unsent.clear();
      if (same(values, recorded)) return;
      this.record("tune", { values }, { says: "Changed the playground's settings" });
    }

    #paint() {
      const reflection = this.#view.reflection(this.#values);
      wear(this, reflection);
      for (const paint of this.#views) paint(this.#values);
      this.dispatchEvent(
        new CustomEvent("lf-layout", { bubbles: true, composed: true }),
      );
      this.dispatchEvent(
        new CustomEvent("lf-commands", { bubbles: true, composed: true }),
      );
    }

    #providedInstruction() {
      if (!this.#instructionProvider) return null;
      const instruction = this.#instructionProvider(this.values);
      if (!instruction.trim())
        throw new Error("instruction provider must return non-empty text");
      return instruction.trim();
    }

    #instruction() {
      if ("error" in this.#renderedInstruction) throw this.#renderedInstruction.error;
      if (this.#renderedInstruction.value !== null)
        return this.#renderedInstruction.value;
      return says(this.#view.output, { format: "lines" }).trim();
    }

    #choose() {
      const chosen = this.#chosen();
      const undo = chosen ? this.#undo() : null;
      if (chosen ? !undo : !this.#available()) return;
      if (!chosen) this.#commit();
      if (chosen) this.takeBack("choose");
      else
        this.record(
          "choose",
          { values: this.values, instruction: this.#instruction() },
          { says: "Playground settings" },
        );
    }

    // A choice records the controls' values. It still matches when a reload restored
    // one of its values before that contributor registered, and ignores a name the
    // settings hold that neither the choice nor any control does, such as a field an
    // earlier revision had.
    #chosen() {
      const choice = this.state?.choose;
      if (!choice || !("action" in choice) || !choice.action) return false;
      const recorded = /** @type {Configuration} */ (choice.detail.values);
      const waiting = Object.entries(this.#pendingValues).filter(([name]) =>
        Object.hasOwn(recorded, name),
      );
      return (
        choice.detail.instruction === this.#instruction() &&
        same(recorded, { ...Object.fromEntries(waiting), ...this.#values })
      );
    }

    #undo() {
      const choose = this.state?.choose;
      return Boolean(choose && "undoable" in choose && choose.undoable);
    }

    #available() {
      return this.state?.choose?.available ?? false;
    }

    // Only a tune the controls haven't drawn replaces their values (the header says
    // why). The reading names no event, so a tune is told from the one drawn by the
    // values it records. A change to the reading's availability draws again too, and
    // paints the keys.
    render() {
      const tune = this.#tune();
      const drawn = tune ? tune.detail.values : null;
      if (!same(this.#drawn, drawn)) {
        this.#drawn = drawn;
        // An edit the tune in force already holds, such as a value the browser restored
        // on a reload, is recorded already.
        const recorded = /** @type {Configuration} */ (
          tune?.detail.values ?? this.#defaults
        );
        for (const name of this.#unsent)
          if (same(recorded[name], this.#values[name])) this.#unsent.delete(name);
        const unsent = [...this.#unsent].map((name) => [name, this.#values[name]]);
        this.#restore({
          ...recorded,
          ...Object.fromEntries(unsent),
        });
      }
      try {
        this.#renderedInstruction = { value: this.#providedInstruction() };
      } catch (error) {
        this.#renderedInstruction = { error };
        throw error;
      }
      const template = this.#view.render({
        values: this.#values,
        instruction: this.#renderedInstruction.value,
        chosen: () => this.#chosen(),
        // The submission's state says why it can't be sent, so the bar keeps no rule
        // of its own about delivery.
        unavailable: this.state?.choose?.unavailable ?? null,
      });
      this.#paint();
      return template;
    }

    // Edits made before the page could record them, such as while its state loads,
    // record once it can.
    /** @param {import("lit").PropertyValues} changed */
    updated(changed) {
      super.updated(changed);
      if (this.#unsent.size && this.state?.tune?.available) this.#recordLater();
    }
  },
);
