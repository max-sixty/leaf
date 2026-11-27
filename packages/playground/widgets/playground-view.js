/* The playground's retained Lit view draws its regions around the author's form and
 * reads and writes the native fields it holds. Its live widget owns commands, working
 * state and delivery (lf-playground.js).
 *
 * The author writes the form: each `input`, `select` or `textarea` with a `name` in the
 * playground is one field, and radios that share a name are one field. An `<aside>`
 * directly inside stands in the rail beside the preview, as a sidebar page's aside
 * does, and the rest of what the playground holds is its preview. The view draws the
 * regions, presets and actions, and never a control or its label. The fields stand in
 * the one `<form>` the view draws around both, so a playground's radio groups are its
 * own, and a control that belongs to a form of its own, such as a candidate's or an
 * inspection setting's, is no field, nor is one a widget in the preview generated
 * (`data-lf-gen`), such as a motion study's transport. The browser's value sanitization decides which
 * values a field can hold. A `<select multiple>` holds the list of the values of the
 * options it selects, in their order, as its form submits each of them; the select's
 * own `value` names only the first. An `<output for="NAME">` shows field NAME's
 * value, a list's as its values separated by commas, as a sentence lists them. The
 * reflected attribute and a preset's setting separate them by spaces, as a token
 * list's attribute does, so CSS's `~=` matches one of them.
 * Rejected: Leaf's own control tags, whose kind, bounds, step and unit the view copied
 * into the native inputs it drew, and whose values it checked again itself.
 *
 * A press on the body of the box that holds one radio, and no other of its group, such
 * as a candidate's card, selects that radio, as a press on its label does; the browser
 * answers presses on the label itself and on whatever operates inside the box.
 *
 * A playground needs no field: a preview whose script declares contributor slices is
 * a whole configuration (lf-playground.js). A `<button type="submit">` written in the
 * playground is its submission, with a `<button type="reset">` as its Reset, and this
 * view then draws no bar of actions, and the instruction stays where it was written,
 * after the stage, as a quoted playground's does, for the page to show or place. This
 * view still writes the words of that submission, from the one template its own
 * submission uses, so they say what the press will do. The markup says the page draws
 * them, not a script's call, because this drawing is the first paint: a bar drawn here
 * and withdrawn once a script handed over its own would move the page as it loads.
 */
import { offeredAction } from "/runtime/lib/controls.js";
import { keeps, keepsText } from "/runtime/lib/keeps.js";

import { html, nothing, render } from "/vendor/lit.js";

/** @typedef {string | number | boolean | null | readonly string[]} FieldValue */
/** @typedef {HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement} FieldControl */
/**
 * One field: the controls that share a name, what they hold now, and what they held as
 * authored, as a form's reset restores them. `read` is undefined while a number field
 * holds no number.
 * @typedef {{
 *   name: string,
 *   controls: FieldControl[],
 *   radios: boolean,
 *   quoted: boolean,
 *   initial: FieldValue,
 *   read: () => FieldValue | undefined,
 *   holds: (value: unknown) => boolean,
 *   write: (value: FieldValue) => void,
 *   parse: (raw: string) => FieldValue,
 * }} Field
 */
/** @typedef {Readonly<Record<string, unknown>>} Configuration */

const NAME = /^[a-z0-9][a-z0-9-]*$/;
// Input types that press rather than hold a value, and a file, which no record holds.
const UNHELD = new Set(["button", "submit", "reset", "image", "file"]);
// Text the user types reaches CSS as a string, for `content`; any other value as is.
const TYPED = new Set(["text", "search", "url", "email", "tel", "password"]);

/** @param {Element} root @param {string} tag @returns {HTMLElement[]} */
const own = (root, tag) => {
  /** @type {NodeListOf<HTMLElement>} */
  const nodes = root.querySelectorAll(`:scope > ${tag}`);
  return [...nodes];
};
/** @param {Element} element @param {string} name */
function requiredAttribute(element, name) {
  const value = element.getAttribute(name);
  if (value === null) throw new Error(`${element.localName} needs ${name}`);
  return value;
}
/** @param {Element} host @param {Element} member */
const belongsTo = (host, member) =>
  member.parentElement?.closest("lf-playground, [data-lf-exhibit]") === host;
/** @param {FieldValue} value @param {string} [between] what separates a list's values */
const words = (value, between = " ") =>
  value === null ? "" : typeof value === "object" ? value.join(between) : String(value);

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

/** Whether two configurations, or two of their values, are the same: a list holds the
 * same items in the same order, and an object the same entries in any order.
 * @param {unknown} left @param {unknown} right */
export const same = (left, right) =>
  configurationJSON(left) === configurationJSON(right);

/** @param {HTMLInputElement} input */
const number = (input) =>
  Number.isFinite(input.valueAsNumber) ? input.valueAsNumber : null;

/** A detached copy that sanitizes a value as its control does, leaving the control be.
 * @template {HTMLInputElement} T @param {T} control @param {string} value */
function probe(control, value) {
  const copy = /** @type {T} */ (control.cloneNode());
  copy.value = value;
  return copy;
}

/** @param {string} name @param {FieldControl[]} controls @returns {Field} */
function field(name, controls) {
  const [control, ...others] = controls;
  if (!control) throw new Error(`field ${name} has no control`);
  const radios = controls.filter(
    /** @returns {each is HTMLInputElement} */
    (each) => each instanceof HTMLInputElement && each.type === "radio",
  );
  if (radios.length === controls.length) {
    return {
      name,
      controls,
      radios: true,
      quoted: false,
      initial: radios.findLast((radio) => radio.defaultChecked)?.value ?? null,
      read: () => radios.find((radio) => radio.checked)?.value ?? null,
      holds: (value) => value === null || radios.some((radio) => radio.value === value),
      write: (value) => {
        for (const radio of radios) radio.checked = radio.value === value;
      },
      parse: (raw) => raw,
    };
  }
  if (others.length)
    throw new Error(`field ${name} names more than one control that isn't a radio`);
  const base = { name, controls, radios: false, quoted: false };
  if (control instanceof HTMLInputElement && control.type === "checkbox")
    return {
      ...base,
      initial: control.defaultChecked,
      read: () => control.checked,
      holds: (value) => typeof value === "boolean",
      write: (value) => {
        control.checked = value === true;
      },
      parse: (raw) => {
        if (raw !== "true" && raw !== "false")
          throw new Error(`checkbox ${name} takes true or false, not ${raw}`);
        return raw === "true";
      },
    };
  if (control instanceof HTMLInputElement && ["range", "number"].includes(control.type))
    return {
      ...base,
      initial: number(probe(control, control.defaultValue)),
      read: () => number(control) ?? undefined,
      holds: (value) => {
        if (typeof value !== "number") return false;
        const copy = probe(control, String(value));
        return number(copy) === value && copy.validity.valid;
      },
      write: (value) => {
        control.value = words(value);
      },
      parse: (raw) => Number(raw.trim() || NaN),
    };
  if (control instanceof HTMLSelectElement && control.multiple) {
    const options = [...control.options];
    const order = options.map((option) => option.value);
    /** @param {(option: HTMLOptionElement) => boolean} picked */
    const selection = (picked) =>
      Object.freeze(options.filter(picked).map((option) => option.value));
    return {
      ...base,
      initial: selection((option) => option.defaultSelected),
      read: () => selection((option) => option.selected),
      holds: (value) =>
        Array.isArray(value) && value.every((item) => order.includes(item)),
      write: (value) => {
        const picked = typeof value === "object" && value !== null ? value : [];
        for (const option of options) {
          const selected = picked.includes(option.value);
          if (option.selected !== selected) option.selected = selected;
        }
      },
      // A setting names the options it selects in any order, and the field holds them
      // in the options' order, as a press on them reads.
      parse: (raw) =>
        Object.freeze(
          [...new Set(raw.split(/\s+/).filter(Boolean))].sort(
            (left, right) => order.indexOf(left) - order.indexOf(right),
          ),
        ),
    };
  }
  const options = control instanceof HTMLSelectElement ? [...control.options] : null;
  return {
    ...base,
    quoted:
      control.localName === "textarea" ||
      (control instanceof HTMLInputElement && TYPED.has(control.type)),
    initial: options
      ? ((options.findLast((option) => option.defaultSelected) ?? options[0])?.value ??
        "")
      : control instanceof HTMLInputElement
        ? probe(control, control.defaultValue).value
        : /** @type {HTMLTextAreaElement} */ (control).defaultValue,
    read: () => control.value,
    holds: (value) =>
      typeof value === "string" &&
      (options
        ? options.some((option) => option.value === value)
        : !(control instanceof HTMLInputElement) ||
          probe(control, value).value === value),
    write: (value) => {
      control.value = words(value);
    },
    // A colour reads the same in either case, and its field holds it lowercase.
    parse: (raw) =>
      control instanceof HTMLInputElement && control.type === "color"
        ? raw.toLowerCase()
        : raw,
  };
}

/** @param {HTMLElement} host */
export function createPlayground(host) {
  const presets = own(host, "lf-playground-preset");
  const [output, extraOutput] = own(host, "lf-playground-output");
  if (!output || extraOutput)
    throw new Error("playground needs one lf-playground-output");
  const asides = own(host, "aside");
  // A control that belongs to a form of its own, one inside the playground or one its
  // `form` attribute names, is that form's; one in no form, or in a form around the
  // whole playground, joins the playground's form (render).
  /** @param {FieldControl | HTMLOutputElement | HTMLButtonElement} control */
  const member = (control) =>
    belongsTo(host, control) &&
    !control.hasAttribute("form") &&
    !(control.form && host.contains(control.form));
  /** @type {Map<string, FieldControl[]>} */
  const named = new Map();
  /** @type {NodeListOf<FieldControl>} */
  const controls = host.querySelectorAll("input[name], select[name], textarea[name]");
  for (const control of controls) {
    // A field control a widget in the preview generated, such as a motion study's
    // scrubber, is that widget's inspection and no field, though it stands in the
    // playground's form. A page's own submit or reset button, or an output, stays the
    // page's wherever a script moves it, so the mark excludes only fields.
    if (!member(control) || host.contains(control.closest("[data-lf-gen]"))) continue;
    if (control instanceof HTMLInputElement && UNHELD.has(control.type)) continue;
    if (!NAME.test(control.name))
      throw new Error(
        `field name ${control.name} needs lowercase letters, digits and hyphens`,
      );
    named.set(control.name, [...(named.get(control.name) ?? []), control]);
  }
  /** @type {Map<string, Field>} */
  const fields = new Map(
    [...named].map(([name, members]) => [name, field(name, members)]),
  );
  /** @type {Map<Element, Field>} */
  const fieldByControl = new Map(
    [...fields.values()].flatMap((each) =>
      each.controls.map((control) => [control, each]),
    ),
  );
  const defaults = Object.freeze(
    Object.fromEntries([...fields].map(([name, each]) => [name, each.initial])),
  );
  // The fields are live from the first paint, before this view is built, so what each
  // shows now may differ from its authored value: the user's edit before the upgrade,
  // or the browser's restoration of their last one. The drawing leaves those in place,
  // and the live widget takes them as edits (lf-playground.js). Until the drawing puts
  // them in this playground's form, its radios share a group with every radio of their
  // name on the page that no form holds either, so one reading none checked lost its
  // check to that other group, as no press can clear a group: the drawing restores it.
  // So is a number field holding no number.
  /** @type {Map<string, FieldValue>} */
  const shown = new Map();
  for (const [name, each] of fields) {
    const value = each.read();
    if (value !== undefined && !(each.radios && value === null)) shown.set(name, value);
  }
  const edited = Object.freeze(
    Object.fromEntries(
      [...shown].filter(([name, value]) => !same(value, defaults[name])),
    ),
  );
  /** @param {string} type @returns {HTMLButtonElement | null} */
  const pageButton = (type) => {
    /** @type {NodeListOf<HTMLButtonElement>} */
    const buttons = host.querySelectorAll(`button[type="${type}"]`);
    return [...buttons].find(member) ?? null;
  };
  const pageSubmit = pageButton("submit"),
    pageReset = pageButton("reset");
  if (pageReset && !pageSubmit)
    throw new Error(
      "a playground whose page writes its reset button needs its submit button",
    );
  const pageActions = Boolean(pageSubmit);
  const interactive = !host.closest("[data-lf-exhibit]");
  // Each pane hosts a reading region, whose body is the box in it that may scroll. The
  // controls pane's is the author's first aside, or the presets where they wrote none.
  if (interactive) keeps(asides[0], "data-lf-scroll", "controls");
  const authored = [...host.childNodes];
  const kept = new Set([...presets, output, ...asides]);
  const stage = authored.filter((node) => !kept.has(/** @type {HTMLElement} */ (node)));
  // The box around each radio that holds no other radio of its group, past the radio's
  // own label, up to its fieldset, the rail or the playground (the header says why).
  /** @type {Map<Element, HTMLInputElement>} */
  const candidates = new Map();
  for (const each of fields.values()) {
    if (!each.radios) continue;
    for (const radio of /** @type {HTMLInputElement[]} */ (each.controls)) {
      /** @type {Element} */
      let box = radio.closest("label") ?? radio;
      for (
        let up = box.parentElement;
        up &&
        up !== host &&
        !up.matches("fieldset, aside") &&
        each.controls.every((other) => other === radio || !up?.contains(other));
        up = up.parentElement
      )
        box = up;
      if (box !== radio && box.localName !== "label") candidates.set(box, radio);
    }
  }
  // A quotation takes no input and sends nothing: its fields show the values it quotes,
  // and its own submission and Reset are gone.
  if (!interactive) {
    for (const control of fieldByControl.keys())
      /** @type {FieldControl} */ (control).disabled = true;
    for (const button of [pageSubmit, pageReset]) if (button) button.hidden = true;
  }
  const presetSettings = new Map(
    presets.map((preset) => {
      const label = preset.getAttribute("label");
      const settings = own(preset, "lf-playground-setting");
      if (!settings.length) throw new Error(`preset ${label} is empty`);
      return [
        preset,
        Object.freeze(
          Object.fromEntries(
            settings.map((setting) => {
              const name = requiredAttribute(setting, "for");
              const target = fields.get(name);
              if (!target) throw new Error(`preset ${label} names no field ${name}`);
              const raw = requiredAttribute(setting, "value");
              const value = target.parse(raw);
              if (!target.holds(value))
                throw new Error(
                  `preset ${label} sets ${name} to ${raw}, which it can't hold`,
                );
              return [name, value];
            }),
          ),
        ),
      ];
    }),
  );
  // Each value is generated separately from the authored words around it, and remains
  // quotable as the configuration's words.
  /** @type {NodeListOf<HTMLOutputElement>} */
  const outputs = host.querySelectorAll("output[for]");
  const slots = [...outputs].filter(member).map((slot) => {
    const name = requiredAttribute(slot, "for").trim();
    if (!fields.has(name)) throw new Error(`<output for="${name}"> names no field`);
    keeps(slot, "data-lf-gen", "1");
    slot.toggleAttribute("data-lf-said", true);
    return { slot, name };
  });
  const presetWords = new Map(
    presets.map((preset) => [preset, [...preset.childNodes]]),
  );
  // Each preset retains its node and has one Lit template, on delivery and live
  // updates; the controls and outputs keep theirs and take their values in place. A
  // preset is a group of its words and its press, named by its label, and a screen
  // reader and Leaf's chrome both call it a preset unless its author named its kind.
  for (const preset of presets) {
    preset.replaceChildren();
    keeps(preset, "role", "group");
    keeps(preset, "aria-label", preset.getAttribute("label"));
    if (!preset.hasAttribute("aria-roledescription"))
      preset.setAttribute("aria-roledescription", "preset");
  }
  host.replaceChildren();
  const resetOffer = offeredAction("symbol", "lf-playground-reset", undefined, {
    action: "reset",
  });
  const revealOffer = offeredAction(
    "symbol",
    "lf-playground-reveal",
    "Show instruction",
    {
      action: "more",
    },
  );
  const submitOffer = offeredAction("commit", "lf-playground-submit");
  const presetOffer = offeredAction("word", "lf-playground-preset");
  const split = () => host.querySelector(":scope > .lf-playground-split");
  const actions = () =>
    split()?.querySelector(
      ":scope > .lf-playground-rail > .lf-playground-instruction-region > .lf-playground-actions",
    );
  const instructionId = `${host.id}-instruction`;
  const submitLabel =
    pageSubmit?.textContent.trim() ||
    host.getAttribute("submit-label") ||
    "Use these settings";
  // The submission says what pressing it does: send the working values, or withdraw
  // the choice they match (lf-playground.js). One room holds both words.
  const submitRoom = `${submitLabel}\nUndo choice`;
  /** @param {boolean} chosen */
  const submitWords = (chosen) =>
    html`<span data-lf-gen="1">${chosen ? "Undo choice" : submitLabel}</span>`;
  if (pageSubmit && interactive) {
    pageSubmit.replaceChildren();
    pageSubmit.dataset.lfRoom = submitRoom;
  }
  const presetBar = () =>
    !presets.length
      ? nothing
      : asides.length
        ? html`<header
            class="lf-playground-presets"
            role="group"
            aria-label="Starting points"
          >
            ${presets}
          </header>`
        : html`<div
            class="lf-playground-presets"
            role="group"
            aria-label="Starting points"
            data-lf-scroll="controls"
          >
            ${presets}
          </div>`;
  const controlsPane = () =>
    html` <div
      class="lf-playground-controls-region"
      data-lf-reading-role="pane"
      data-lf-scroll-host="controls"
      data-lf-generated
      role="region"
      aria-label="Controls"
    >
      ${presetBar()}${asides}
    </div>`;
  const view = {
    fields,
    presets,
    presetSettings,
    defaults,
    edited,
    output,
    interactive,
    pageActions,
    /** @type {ReturnType<typeof import("/runtime/widget-api.js").copyControl> | null} */
    copy: null,
    /** @returns {HTMLElement | null} */
    get preview() {
      return split()?.querySelector(".lf-playground-stage") ?? null;
    },
    /** @returns {HTMLButtonElement | null} */
    get submit() {
      return pageActions
        ? pageSubmit
        : (actions()?.querySelector(":scope > .lf-playground-submit") ?? null);
    },
    /** @returns {HTMLButtonElement | null} */
    get reset() {
      return pageActions
        ? pageReset
        : (actions()?.querySelector(":scope > .lf-playground-reset") ?? null);
    },
    /** @returns {HTMLElement | null} */
    get instruction() {
      return actions()?.querySelector(":scope > .lf-playground-instruction") ?? null;
    },
    get presetButtons() {
      return new Map(
        presets.map((preset) => [preset, preset.querySelector(":scope > button")]),
      );
    },
    /** @returns {HTMLElement | null} */
    get controls() {
      return (
        split()?.querySelector(
          ":scope > .lf-playground-controls-region, :scope > .lf-playground-rail > .lf-playground-controls-region",
        ) ?? null
      );
    },
    /** @param {Element | null} element */
    isField: (element) => Boolean(element && fieldByControl.has(element)),
    // The next drawing writes these fields, or all of them, as a gesture that sets them
    // from outside (Reset, a preset) requires: a field may show what the configuration
    // doesn't hold, such as a number field the user cleared.
    /** @param {Iterable<string>} [names] */
    forget: (names = fields.keys()) => {
      for (const name of names) shown.delete(name);
    },
    // The field a control the user changed belongs to, with the value it now holds,
    // which the drawing then leaves in place; null for any other control, and while a
    // number field holds no number.
    /** @param {EventTarget | null} target */
    input(target) {
      const changed = target instanceof Element ? fieldByControl.get(target) : null;
      const value = changed?.read();
      if (!changed || value === undefined) return null;
      shown.set(changed.name, value);
      return { name: changed.name, value };
    },
    /** The radio a press on `target` selects: one whose box holds it, outside a label.
     * @param {Element} target */
    candidate(target) {
      for (
        let at = /** @type {Element | null} */ (target);
        at && at !== host;
        at = at.parentElement
      ) {
        if (at.localName === "label") return null;
        const radio = candidates.get(at);
        if (radio) return { box: at, radio };
      }
      return null;
    },
    /** @param {Configuration} next */
    reflection(next) {
      /** @type {Record<string, string>} */
      const attributes = {};
      /** @type {Record<string, string>} */
      const properties = {};
      for (const [name, value] of Object.entries(next)) {
        const each = fields.get(name);
        if (!each) continue;
        const text = words(/** @type {FieldValue} */ (value));
        attributes[`data-playground-${name}`] = text;
        properties[`--playground-${name}`] = each.quoted ? JSON.stringify(text) : text;
      }
      return { attributes, properties };
    },
    /** @param {{values?: Configuration, instruction?: string | null, chosen?: () => boolean, unavailable?: string | null}} [options] */
    render({
      values: next = defaults,
      instruction = null,
      chosen = () => false,
      unavailable = null,
    } = {}) {
      // A field takes a value only where it differs from what the field last showed,
      // so the words being typed and a number being cleared stay as they are.
      for (const [name, each] of fields) {
        const value = /** @type {FieldValue} */ (next[name] ?? null);
        if (shown.has(name) && same(shown.get(name), value)) continue;
        shown.set(name, value);
        each.write(value);
      }
      for (const { slot, name } of slots)
        keepsText(slot, words(/** @type {FieldValue} */ (next[name] ?? null), ", "));
      // A script's instruction takes the place of the output's words, readings
      // included; a reading anywhere else in the playground stays and follows its field.
      if (instruction !== null) {
        if (!output.hasAttribute("data-lf-gen")) {
          output.replaceChildren();
          keeps(output, "data-lf-gen", "1");
          output.toggleAttribute("data-lf-said", true);
        }
        render(html`${instruction}`, output);
      }
      if (!interactive) return html`${authored}`;
      for (const [preset, settings] of presetSettings)
        render(
          html`${presetWords.get(preset)}<button
              ${presetOffer}
              aria-pressed=${Object.entries(settings).every(([name, value]) =>
                same(next[name], value),
              )}
            >
              ${preset.getAttribute("label")}
            </button>`,
          preset,
        );
      if (pageSubmit) render(submitWords(chosen()), pageSubmit);
      const instructionPane = html`<div
        class="lf-playground-instruction-region"
        data-lf-reading-role="pane"
        data-lf-scroll-host="instruction"
        data-lf-generated
        role="region"
        aria-label="Instruction to agent"
      >
        <footer class="lf-playground-actions" data-lf-scroll="instruction">
          <button ${resetOffer}></button>
          <button
            ${revealOffer}
            popovertarget=${instructionId}
            aria-controls=${instructionId}
            aria-expanded="false"
          ></button>
          <button ${submitOffer} data-lf-room=${submitRoom}>
            ${submitWords(chosen())}
          </button>
          <div
            class="lf-playground-instruction lf-popover"
            id=${instructionId}
            popover="auto"
            role="dialog"
            aria-labelledby=${`${instructionId}-title`}
          >
            <div class="lf-playground-instruction-head">
              <p
                class="lf-playground-instruction-title lf-label"
                id=${`${instructionId}-title`}
                data-lf-gen="1"
              >
                Instruction to agent
              </p>
              ${view.copy ?? nothing}
            </div>
            <div class="lf-playground-instruction-body">${output}</div>
          </div>
          ${
            unavailable
              ? html`<span class="lf-playground-unavailable" data-lf-gen="1"
                  >Submission unavailable: ${unavailable}.</span
                >`
              : nothing
          }
        </footer>
      </div>`;
      // The rail holds the aside and the bar of actions; a page that draws its own
      // actions and writes no aside leaves it out.
      const rail =
        asides.length || !pageActions
          ? html`<div class="lf-playground-rail" data-lf-track data-lf-scroll="rail">
              ${asides.length ? controlsPane() : nothing}
              ${pageActions ? nothing : instructionPane}
            </div>`
          : nothing;
      return html`<form class="lf-playground-split">
          ${!asides.length && presets.length ? controlsPane() : nothing}
          <div
            class="lf-playground-preview-region"
            data-lf-reading-role="pane"
            data-lf-scroll-host="preview"
            data-lf-generated
            role="region"
            aria-label="Preview"
          >
            <div class="lf-playground-preview-body" data-lf-scroll="preview">
              <div class="lf-playground-stage">${stage}</div>
            </div>
          </div>
          ${rail}
        </form>
        ${pageActions ? output : nothing}`;
    },
  };
  const initialReflection = view.reflection(defaults);
  for (const [name, value] of Object.entries(initialReflection.properties))
    host.style.setProperty(name, value);
  for (const [name, value] of Object.entries(initialReflection.attributes))
    host.setAttribute(name, value);
  host.classList.add("lf-rendered");
  return view;
}
