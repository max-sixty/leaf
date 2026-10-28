/* The playground's shared Lit view, drawn before first paint and on every live
 * update. Native fields and the viewer's tab-local values determine the first
 * layout; upgrade keeps this view and adds commands, projection and delivery.
 *
 * Every authored playground has passed validation, page source and message markup
 * alike, so what the registry states is not checked again here: control names and
 * kinds, unique control names, choice values and preset settings (x-unique), and each
 * setting's and value slot's `for` naming a control of this playground (a keyed
 * x-refers). This producer checks only what needs the values themselves, such as a
 * range value against its bounds or a choice control's value among its choices. */
import { html, nothing, ref, render } from "/vendor/lit.js";
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

function createPlayground(
  host,
  { tabStore, offerElement, offerActionElement, generatedElement },
) {
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
  const interactive = !host.closest("[data-lf-exhibit]");
  const authored = [...host.childNodes];
  const railed = controls.filter((control) => control.parentElement === host);
  const candidates = new Set();
  const bodies = new Map();
  for (const [name, choices] of choicesByName) {
    if (
      choices.some((choice) =>
        [...choice.childNodes].some(
          (child) =>
            child.nodeType === Node.ELEMENT_NODE ||
            (child.nodeType === Node.TEXT_NODE && child.data.trim()),
        ),
      )
    )
      candidates.add(controlByName.get(name));
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
              const name = setting.getAttribute("for");
              return [
                name,
                parse(controlByName.get(name), setting.getAttribute("value")),
              ];
            }),
          ),
        ),
      ];
    }),
  );
  const formatted = (control, value) => `${value}${control.getAttribute("unit") ?? ""}`;
  // Each value is generated separately from the authored instruction around it,
  // and remains quotable as the configuration's words.
  const slots = [...output.querySelectorAll("lf-playground-value")].filter((slot) =>
    belongsTo(host, slot),
  );
  for (const slot of slots) generatedElement(slot, { says: true });
  const presetWords = new Map(
    presets.map((preset) => [preset, [...preset.childNodes]]),
  );
  // These are independent authored roots, including controls inside arbitrary preview
  // markup. Each retains its node and has one Lit template, on delivery and live updates.
  for (const root of [...controls, ...bodies.keys(), ...presets, ...slots])
    root.replaceChildren();
  host.replaceChildren();
  const offered = (apply) =>
    ref((element) => {
      if (element) apply(element);
    });
  const inputOffer = offered((element) => offerElement(element, "lf-playground-input"));
  const radioOffer = offered((element) => offerElement(element, ""));
  const action = (role, cls, label) =>
    offered((element) => offerActionElement(element, role, cls, label));
  const resetOffer = action("symbol", "lf-playground-reset", "Reset");
  const revealOffer = action("symbol", "lf-playground-reveal", "Show instruction");
  const submitOffer = action("commit", "lf-playground-submit");
  const presetOffer = action("word", "lf-playground-preset");
  const nativeInputs = (control) => [
    ...control.querySelectorAll(
      ":scope > input, :scope > select, :scope > .choice > input, :scope > .lf-playground-choices > lf-playground-choice > .choice > input",
    ),
  ];
  const split = () => host.querySelector(":scope > .lf-playground-split");
  const actions = () =>
    split()?.querySelector(
      ":scope > .lf-playground-rail > .lf-playground-instruction-region > .lf-playground-actions",
    );
  const instructionId = `${host.id}-instruction`;
  const submitLabel = host.getAttribute("submit-label") ?? "Use these settings";
  const retryIcon = iconElement("retry", "lf-action-icon");
  const moreIcon = iconElement("more", "lf-action-icon");
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
    values,
    storedCandidate,
    output,
    preview,
    parse,
    typed,
    copy: null,
    get submit() {
      return actions()?.querySelector(":scope > .lf-playground-submit") ?? null;
    },
    get reset() {
      return actions()?.querySelector(":scope > .lf-playground-reset") ?? null;
    },
    get reveal() {
      return actions()?.querySelector(":scope > .lf-playground-reveal") ?? null;
    },
    get instruction() {
      return actions()?.querySelector(":scope > .lf-playground-instruction") ?? null;
    },
    get presetButtons() {
      return new Map(
        presets.map((preset) => [preset, preset.querySelector(":scope > button")]),
      );
    },
    get regions() {
      return [
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
      ].flatMap(([name, selector, body]) => {
        const region = split()?.querySelector(selector);
        return region
          ? [{ name, host: region, body: body ? region.querySelector(body) : region }]
          : [];
      });
    },
    isInput(control, target) {
      return nativeInputs(control).includes(target);
    },
    readInput(control) {
      const inputs = nativeInputs(control),
        input = inputs[0];
      return input.type === "radio"
        ? inputs.find((radio) => radio.checked)?.value
        : control.getAttribute("kind") === "toggle"
          ? input.checked
          : input.value;
    },
    reflection(next) {
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
    },
    render({ values: next = values, instruction = null, chosen = () => false } = {}) {
      if (instruction === null) {
        for (const slot of slots)
          render(
            html`${formatted(
              controlByName.get(slot.getAttribute("for")),
              next[slot.getAttribute("for")],
            )}`,
            slot,
          );
      } else {
        if (!output.hasAttribute("data-lf-gen")) {
          output.replaceChildren();
          generatedElement(output, { says: true });
        }
        render(html`${instruction}`, output);
      }
      for (const control of controls) {
        const name = control.getAttribute("name"),
          kind = control.getAttribute("kind"),
          label = control.getAttribute("label");
        const choices = choicesByName.get(name);
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
      for (const preset of presets)
        render(
          html`${presetWords.get(preset)}<button
              ${presetOffer}
              aria-pressed=${Object.entries(presetSettings.get(preset)).every(
                ([name, value]) => Object.is(next[name], value),
              )}
            >
              ${preset.getAttribute("label")}
            </button>`,
          preset,
        );
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
        <div class="lf-playground-rail" data-lf-track>
          ${railed.length ? controlsPane() : nothing}
          <div
            class="lf-playground-instruction-region"
            data-lf-reading-role="pane"
            data-lf-generated
            role="region"
            aria-label="Instruction to agent"
          >
            <div class="lf-playground-actions">
              <button ${resetOffer}>${retryIcon}</button>
              <button
                ${revealOffer}
                popovertarget=${instructionId}
                aria-controls=${instructionId}
                aria-expanded="false"
              >
                ${moreIcon}
              </button>
              <button ${submitOffer} data-room=${`${submitLabel}\nUndo choice`}>
                <span data-lf-gen="1">${chosen() ? "Undo choice" : submitLabel}</span>
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
            </div>
          </div>
        </div>
      </div>`;
    },
  };
  const initialReflection = view.reflection(values);
  for (const [name, value] of Object.entries(initialReflection.properties))
    host.style.setProperty(name, value);
  for (const [name, value] of Object.entries(initialReflection.attributes))
    host.setAttribute(name, value);
  host.classList.add("lf-rendered");
  return view;
}
document.documentElement.lfInitial.register("lf-playground", createPlayground);
