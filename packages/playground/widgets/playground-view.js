/* The playground's retained Lit view reads native controls and draws their values.
 * Its live widget owns commands, working state and delivery.
 *
 * A playground needs no control: a preview whose script declares contributor slices
 * is a whole configuration (lf-playground.js). With `actions="page"` the page draws
 * the submission and Reset and hands them to the playground, so this view draws no bar
 * of actions, and the instruction stays where it was written, after the stage, as a
 * quoted playground's does, for the page to show or place. This view still writes the
 * words of the page's submission, from the one template its own submission uses. The
 * markup says so, not only the page's call, because this drawing is the first paint: a
 * bar drawn here and withdrawn once the page's script registered its own would move
 * the page as it loads.
 */
import { offerElement, offeredAction, generatedElement } from "/runtime/widget-api.js";

import { html, nothing, ref, render } from "/vendor/lit.js";

/** @typedef {string | number | boolean} ControlValue */
/** @typedef {Readonly<Record<string, unknown>>} Configuration */
/** @typedef {{submit: HTMLButtonElement, reset: HTMLButtonElement}} PlaygroundActions */
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
// A control stands in the rail as a direct child, or where the preview's markup puts
// it, beside the item it changes (x-within). Nested playgrounds and quotations
// enclose their own content rather than supplying controls to this playground.
/** @param {Element} host @param {Element | undefined} preview */
const ownControls = (host, preview) => {
  /** @type {NodeListOf<HTMLElement> | undefined} */
  const nested = preview?.querySelectorAll("lf-playground-control");
  return [
    ...own(host, "lf-playground-control"),
    ...[...(nested ?? [])].filter((control) => belongsTo(host, control)),
  ];
};

/** @param {HTMLElement} host */
export function createPlayground(host) {
  const presets = own(host, "lf-playground-preset");
  const outputs = own(host, "lf-playground-output");
  const previews = own(host, "lf-playground-preview");
  const controls = ownControls(host, previews[0]);
  const [output, extraOutput] = outputs,
    [preview, extraPreview] = previews;
  if (!output || extraOutput || !preview || extraPreview)
    throw new Error("playground needs one preview and one output");
  /** @type {Map<string, HTMLElement>} */
  const controlByName = new Map();
  /** @type {Map<HTMLElement, {name: string, kind: string, choices: HTMLElement[]}>} */
  const readings = new Map();
  /** @type {Map<string, HTMLElement[]>} */
  const choicesByName = new Map();
  for (const control of controls) {
    const name = requiredAttribute(control, "name"),
      kind = requiredAttribute(control, "kind");
    const choices = own(control, "lf-playground-choice");
    if ((kind === "choice") !== Boolean(choices.length))
      throw new Error(`control ${name} needs choices only for kind choice`);
    readings.set(control, { name, kind, choices });
    choicesByName.set(name, choices);
    controlByName.set(name, control);
  }
  /** @param {HTMLElement} control */
  const reading = (control) => {
    const record = readings.get(control);
    if (!record) throw new Error("A playground value needs its declared control");
    return record;
  };
  /** @param {HTMLElement} control @param {unknown} raw @returns {ControlValue} */
  const parse = (control, raw) => {
    const { name, kind, choices } = reading(control);
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
      if (raw !== "true" && raw !== "false")
        throw new Error(`toggle control ${name} needs true or false`);
      return raw === "true";
    }
    if (typeof raw !== "string") throw new Error(`control ${name} needs text`);
    if (
      kind === "choice" &&
      !choices.some((choice) => choice.getAttribute("value") === raw)
    )
      throw new Error(`control ${name} has no choice ${raw}`);
    if (kind === "color") {
      if (!/^#[0-9a-f]{6}$/i.test(raw))
        throw new Error(`color control ${name} needs #rrggbb`);
      return raw.toLowerCase();
    }
    return raw;
  };
  /** @param {HTMLElement} control @param {unknown} value */
  const typed = (control, value) => {
    const { name, kind } = reading(control);
    const type = kind === "range" ? "number" : kind === "toggle" ? "boolean" : "string";
    if (typeof value !== type) throw new Error(`control ${name} needs a ${type}`);
    return parse(control, String(value));
  };
  const defaults = Object.freeze(
    Object.fromEntries(
      controls.map((control) => [
        reading(control).name,
        parse(control, control.getAttribute("value")),
      ]),
    ),
  );
  const interactive = !host.closest("[data-lf-exhibit]");
  const authored = [...host.childNodes];
  const railed = controls.filter((control) => control.parentElement === host);
  /** @type {Set<HTMLElement>} */
  const candidates = new Set();
  /** @type {Map<HTMLElement, ChildNode[]>} */
  const bodies = new Map();
  for (const [name, choices] of choicesByName) {
    if (
      choices.some((choice) =>
        [...choice.childNodes].some(
          (child) =>
            child.nodeType === Node.ELEMENT_NODE ||
            (child instanceof Text && child.data.trim()),
        ),
      )
    ) {
      const control = controlByName.get(name);
      if (control) candidates.add(control);
    }
    for (const choice of choices) bodies.set(choice, [...choice.childNodes]);
  }
  host.classList.toggle("lf-playground-quoted", !interactive);
  for (const control of controls) {
    if (candidates.has(control)) control.classList.add("lf-playground-candidates");
    if (interactive)
      control.classList.add(`lf-playground-${control.getAttribute("kind")}`);
  }
  if (!interactive) {
    const bare = new Set(controls.filter((control) => !candidates.has(control)));
    /** @param {Element} box */
    const holdsOnlyBare = (box) =>
      [...box.childNodes].every((child) =>
        child instanceof Text
          ? !child.data.trim()
          : child.nodeType === Node.COMMENT_NODE ||
            (child instanceof HTMLElement && bare.has(child)),
      );
    for (const control of bare)
      for (
        let box = control.parentElement;
        box && box !== preview && box !== host && !bare.has(box) && holdsOnlyBare(box);
        box = box.parentElement
      )
        bare.add(box);
    for (const hidden of [...bare, ...presets]) hidden.hidden = true;
  }
  const presetSettings = new Map(
    presets.map((preset) => {
      const settings = own(preset, "lf-playground-setting");
      if (!settings.length)
        throw new Error(`preset ${preset.getAttribute("label")} is empty`);
      return [
        preset,
        Object.freeze(
          Object.fromEntries(
            settings.map((setting) => {
              const name = requiredAttribute(setting, "for");
              const control = controlByName.get(name);
              if (!control) throw new Error(`Preset names unknown control ${name}`);
              return [name, parse(control, setting.getAttribute("value"))];
            }),
          ),
        ),
      ];
    }),
  );
  /** @param {HTMLElement} control @param {unknown} value */
  const formatted = (control, value) => `${value}${control.getAttribute("unit") ?? ""}`;
  // Each value is generated separately from the authored instruction around it,
  // and remains quotable as the configuration's words.
  /** @type {NodeListOf<HTMLElement>} */
  const outputSlots = output.querySelectorAll("lf-playground-value");
  const slots = [...outputSlots].filter((slot) => belongsTo(host, slot));
  const slotReadings = slots.map((slot) => {
    const name = requiredAttribute(slot, "for");
    const control = controlByName.get(name);
    if (!control) throw new Error(`Playground output names unknown control ${name}`);
    generatedElement(slot, { says: true });
    return { slot, name, control };
  });
  const presetWords = new Map(
    presets.map((preset) => [preset, [...preset.childNodes]]),
  );
  // These are independent authored roots, including controls inside arbitrary preview
  // markup. Each retains its node and has one Lit template, on delivery and live updates.
  for (const root of [...controls, ...bodies.keys(), ...presets, ...slots])
    root.replaceChildren();
  host.replaceChildren();
  /** @param {(element: Element) => void} apply */
  const offered = (apply) =>
    ref((element) => {
      if (element) apply(element);
    });
  const inputOffer = offered((element) => offerElement(element, "lf-playground-input"));
  const radioOffer = offered((element) => offerElement(element, ""));
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
  /** @param {HTMLElement} control @returns {(HTMLInputElement | HTMLSelectElement)[]} */
  const nativeInputs = (control) => {
    /** @type {NodeListOf<HTMLInputElement | HTMLSelectElement>} */
    const inputs = control.querySelectorAll(
      ":scope > input, :scope > select, :scope > .choice > input, :scope > .lf-playground-choices > lf-playground-choice > .choice > input",
    );
    return [...inputs];
  };
  const split = () => host.querySelector(":scope > .lf-playground-split");
  const actions = () =>
    split()?.querySelector(
      ":scope > .lf-playground-rail > .lf-playground-instruction-region > .lf-playground-actions",
    );
  const instructionId = `${host.id}-instruction`;
  const submitLabel = host.getAttribute("submit-label") ?? "Use these settings";
  // The submission says what pressing it does: send the working values, or withdraw
  // the choice they match (lf-playground.js). One room holds both words.
  const submitRoom = `${submitLabel}\nUndo choice`;
  /** @param {boolean} chosen */
  const submitWords = (chosen) =>
    html`<span data-lf-gen="1">${chosen ? "Undo choice" : submitLabel}</span>`;
  const pageActions = host.getAttribute("actions") === "page";
  const offline = Boolean(document.querySelector("script[data-lf-offline]"));
  const presetBar = () =>
    !presets.length
      ? nothing
      : railed.length
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
          >
            ${presets}
          </div>`;
  const controlsPane = () =>
    html` <div
      class="lf-playground-controls-region"
      data-lf-reading-role="pane"
      data-lf-generated
      role="region"
      aria-label="Controls"
    >
      ${presetBar()}${
        railed.length
          ? html`<div class="lf-playground-controls" role="group" aria-label="Controls">
              ${railed}
            </div>`
          : nothing
      }
    </div>`;
  const view = {
    controls,
    controlByName,
    presets,
    presetSettings,
    defaults,
    output,
    preview,
    parse,
    controlName: (/** @type {HTMLElement} */ control) => reading(control).name,
    typed,
    interactive,
    pageActions,
    /** @type {ReturnType<typeof import("/runtime/widget-api.js").copyControl> | null} */
    copy: null,
    // Under `actions="page"`, the page's own two buttons once it registers them.
    /** @type {PlaygroundActions | null} */
    given: null,
    /** @returns {HTMLButtonElement | null} */
    get submit() {
      return pageActions
        ? (view.given?.submit ?? null)
        : (actions()?.querySelector(":scope > .lf-playground-submit") ?? null);
    },
    /** @returns {HTMLButtonElement | null} */
    get reset() {
      return pageActions
        ? (view.given?.reset ?? null)
        : (actions()?.querySelector(":scope > .lf-playground-reset") ?? null);
    },
    get reveal() {
      return actions()?.querySelector(":scope > .lf-playground-reveal") ?? null;
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
    get regions() {
      /** @type {[string, string, string | null][]} */
      const regions = [
        [
          "controls",
          ":scope > .lf-playground-controls-region, :scope > .lf-playground-rail > .lf-playground-controls-region",
          railed.length ? ".lf-playground-controls" : ".lf-playground-presets",
        ],
        [
          "instruction",
          ":scope > .lf-playground-rail > .lf-playground-instruction-region",
          ".lf-playground-actions",
        ],
        ["rail", ":scope > .lf-playground-rail", null],
        [
          "preview",
          ":scope > .lf-playground-preview-region",
          ".lf-playground-preview-body",
        ],
      ];
      return regions.flatMap(([name, selector, body]) => {
        const region = split()?.querySelector(selector);
        if (!region) return [];
        const readingBody = body ? region.querySelector(body) : region;
        if (!readingBody)
          throw new Error(`The playground ${name} region needs its reading body`);
        return [{ name, host: region, body: readingBody }];
      });
    },
    // The page's buttons under `actions="page"`; render writes the submission's words.
    /** @param {PlaygroundActions} given */
    give(given) {
      view.given = given;
      given.submit.replaceChildren();
      given.submit.dataset.room = submitRoom;
    },
    /** @param {HTMLElement} control @param {EventTarget | null} target */
    isInput(control, target) {
      return nativeInputs(control).some((input) => input === target);
    },
    /** @param {HTMLElement} control */
    readInput(control) {
      const inputs = nativeInputs(control),
        input = inputs[0];
      if (!input)
        throw new Error("A rendered playground control needs its native input");
      return input instanceof HTMLInputElement && input.type === "radio"
        ? inputs.find((radio) => radio instanceof HTMLInputElement && radio.checked)
            ?.value
        : control.getAttribute("kind") === "toggle"
          ? input instanceof HTMLInputElement && input.checked
          : input.value;
    },
    /** @param {Configuration} next */
    reflection(next) {
      /** @type {Record<string, string>} */
      const attributes = {};
      /** @type {Record<string, string>} */
      const properties = {};
      for (const [name, value] of Object.entries(next)) {
        const control = controlByName.get(name);
        if (!control) continue;
        attributes[`data-playground-${name}`] = String(value);
        const content = formatted(control, value);
        properties[`--playground-${name}`] =
          control.getAttribute("kind") === "text" ? JSON.stringify(content) : content;
      }
      return { attributes, properties };
    },
    /** @param {{values?: Configuration, instruction?: string | null, chosen?: () => boolean}} [options] */
    render({ values: next = defaults, instruction = null, chosen = () => false } = {}) {
      if (instruction === null) {
        for (const { slot, control, name } of slotReadings)
          render(html`${formatted(control, next[name])}`, slot);
      } else {
        if (!output.hasAttribute("data-lf-gen")) {
          output.replaceChildren();
          generatedElement(output, { says: true });
        }
        render(html`${instruction}`, output);
      }
      for (const control of controls) {
        const { name, kind, choices } = reading(control);
        const label = control.getAttribute("label");
        const select =
          kind === "choice" && control.getAttribute("appearance") === "select";
        if (!select)
          for (const choice of choices)
            render(
              html`
                ${
                  interactive
                    ? html`<label class="choice" data-lf-gen="1"
                        ><input
                          ${radioOffer}
                          type="radio"
                          name=${`${host.id}-${name}`}
                          value=${choice.getAttribute("value")}
                          .checked=${next[name] === choice.getAttribute("value")}
                        /><span class="lf-playground-choice-label" data-lf-gen="1"
                          >${choice.getAttribute("label")}</span
                        ></label
                      >`
                    : html`<p class="lf-playground-choice-heading" data-lf-gen="1">
                        ${choice.getAttribute("label")}
                      </p>`
                }
                ${
                  candidates.has(control)
                    ? html`<div class="lf-playground-choice-preview">
                        ${bodies.get(choice)}
                      </div>`
                    : nothing
                }
              `,
              choice,
            );
        if (!interactive) {
          render(html`${choices}`, control);
          continue;
        }
        const field = html`<input
          type=${kind === "toggle" ? "checkbox" : kind}
          ${inputOffer}
          id=${`${host.id}-${name}-input`}
          name=${`${host.id}-${name}`}
          aria-label=${label}
          role=${kind === "toggle" ? "switch" : nothing}
          min=${control.getAttribute("min") ?? nothing}
          max=${control.getAttribute("max") ?? nothing}
          step=${control.getAttribute("step") ?? nothing}
          placeholder=${control.getAttribute("placeholder") ?? nothing}
          .checked=${kind === "toggle" ? next[name] : false}
          .value=${kind === "toggle" ? "on" : next[name]}
        />`;
        render(
          html`<span class="lf-playground-control-label" data-lf-gen="1">${label}</span>
            ${
              select
                ? html`<select
                    ${inputOffer}
                    name=${`${host.id}-${name}`}
                    aria-label=${label}
                    .value=${next[name]}
                  >
                    ${choices.map(
                      (choice) =>
                        html`<option
                          value=${choice.getAttribute("value")}
                          .selected=${next[name] === choice.getAttribute("value")}
                        >
                          ${choice.getAttribute("label")}
                        </option>`,
                    )}
                  </select>`
                : kind === "choice"
                  ? html`<div
                      class="lf-playground-input lf-playground-choices"
                      role="radiogroup"
                      aria-label=${label}
                    >
                      ${choices}
                    </div>`
                  : kind === "toggle"
                    ? html`<label class="choice" data-lf-gen="1">${field}</label>`
                    : field
            }
            ${
              kind === "range"
                ? html`<output class="lf-playground-reading"
                    >${formatted(control, next[name])}</output
                  >`
                : nothing
            } `,
          control,
        );
      }
      if (!interactive) return html`${authored}`;
      for (const [preset, settings] of presetSettings)
        render(
          html`${presetWords.get(preset)}<button
              ${presetOffer}
              aria-pressed=${Object.entries(settings).every(([name, value]) =>
                Object.is(next[name], value),
              )}
            >
              ${preset.getAttribute("label")}
            </button>`,
          preset,
        );
      if (view.given) render(submitWords(chosen()), view.given.submit);
      const instructionPane = html`<div
        class="lf-playground-instruction-region"
        data-lf-reading-role="pane"
        data-lf-generated
        role="region"
        aria-label="Instruction to agent"
      >
        <footer class="lf-playground-actions">
          <button ${resetOffer}></button>
          <button
            ${revealOffer}
            popovertarget=${instructionId}
            aria-controls=${instructionId}
            aria-expanded="false"
          ></button>
          <button ${submitOffer} data-room=${submitRoom}>
            ${submitWords(chosen())}
          </button>
          <div
            class="lf-playground-instruction"
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
            offline
              ? html`<span class="lf-playground-unavailable" data-lf-gen="1"
                  >Submission unavailable: no agent or server is available.</span
                >`
              : nothing
          }
        </footer>
      </div>`;
      // The rail holds the controls written there and the bar of actions; a page that
      // draws its own actions and writes no control there leaves it out.
      const rail =
        railed.length || !pageActions
          ? html`<div class="lf-playground-rail" data-lf-track>
              ${railed.length ? controlsPane() : nothing}
              ${pageActions ? nothing : instructionPane}
            </div>`
          : nothing;
      return html`<div class="lf-playground-split">
          ${!railed.length && presets.length ? controlsPane() : nothing}
          <div
            class="lf-playground-preview-region"
            data-lf-reading-role="pane"
            data-lf-generated
            role="region"
            aria-label="Preview"
          >
            <div class="lf-playground-preview-body">${preview}</div>
          </div>
          ${rail}
        </div>
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
