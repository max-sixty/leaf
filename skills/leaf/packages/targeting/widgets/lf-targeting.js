/* lf-targeting: a local visual-edit draft with one structured durable action.
 *
 * The preview remains authored DOM. Core captures and resolves every selected target;
 * labels and visible context describe a reference but never participate in its identity.
 * Working changes mutate only declared box-model properties, after saving the prior
 * inline value; every repaint applies the current ordered draft and restores the saved
 * value of each property no change holds any longer. Prose carries a target key beside
 * its words. The complete target/change graph is submitted as one recordless action,
 * so replay, refusal, and undo use Leaf's ordinary projection instead of a
 * widget-owned event history. Target keys retain the native editor controls across
 * repaint; local names preserve the user's exact draft, and submission normalizes
 * whitespace and requires every target to have a nonempty name. */
import {
  captureTargetReference,
  commands,
  failSoft,
  html,
  keyed,
  keepsHidden,
  layoutChanged,
  notice,
  offer,
  offered,
  once,
  paintKeys,
  quoted,
  render,
  repeat,
  retainUserIntent,
  resolveTargetReference,
  says,
  targetCandidates,
  widgetController,
  focusDestination,
  holdFocus,
} from "/runtime/widget-api.js";
import "../vendor/webawesome.esm.js";

const STYLE_PROPERTIES = [
  ["padding", "Padding"],
  ["margin", "Margin"],
  ["gap", "Gap"],
  ["border-width", "Border width"],
  ["border-radius", "Corner radius"],
  ["width", "Width"],
  ["min-height", "Minimum height"],
];
const GENERATED = "[data-lf-gen]";
const emptyConfiguration = () => ({ targets: [], changes: [] });
const copy = (value) => structuredClone(value);
const normalizedWords = (value) => value.replace(/\s+/g, " ").trim();

function option(value, label) {
  const node = offer("wa-option", "", label);
  node.value = value;
  return node;
}

customElements.define(
  "lf-targeting",
  class extends HTMLElement {
    // What the Ask was answered with: the size of the submitted configuration.
    static answerWords(state) {
      const { targets, changes } = state.submit.detail;
      return `${targets.length} targets · ${changes.length} changes`;
    }

    #controller = widgetController(this);
    #preview = null;
    #editor = null;
    #arm = null;
    #status = null;
    #candidateList = null;
    #targetList = null;
    #changeList = null;
    #styleTarget = null;
    #styleProperty = null;
    #styleValue = null;
    #instructionTarget = null;
    #instructionText = null;
    #submit = null;
    #revert = null;
    #configuration = emptyConfiguration();
    #projected = emptyConfiguration();
    #projectionSignature = undefined;
    #dirty = false;
    #sending = false;
    #armed = false;
    #hovered = null;
    #candidates = [];
    #targetSequence = 0;
    #changeSequence = 0;
    #tabIndexes = new Map();
    #authoredClasses = new Map();
    #restoredStyles = new Map();
    #interactive = false;
    #ready = false;
    #resumeProjection = null;
    #targetChanges = new MutationObserver(() => this.#render());

    connectedCallback() {
      if (!once(this)) {
        if (this.#interactive) this.#applyPreview();
        this.#watchTargets();
        if (this.#interactive) {
          if (this.#dirty && !this.#resumeProjection)
            this.#resumeProjection = this.#controller.defer();
        }
        return;
      }
      try {
        const previews = [...this.querySelectorAll(":scope > lf-target-preview")];
        if (previews.length !== 1) throw new Error("needs exactly one target preview");
        this.#preview = previews[0];
        for (const element of [this.#preview, ...this.#preview.querySelectorAll("*")])
          if (!element.matches(GENERATED))
            this.#authoredClasses.set(element, [...element.classList]);
        this.#interactive = !quoted(this);
        this.classList.toggle("lf-targeting-quoted", !this.#interactive);
        if (this.#interactive) this.#build();
        this.#ready = true;
        this.#watchTargets();
        if (this.#interactive)
          this.#controller.subscribe(() => this.#paintAvailability());
        this.#render();
        // Built, so the height the page reserved for it lifts (x-height).
        this.classList.add("lf-rendered");
      } catch (error) {
        this.#restorePreview();
        failSoft(this, error);
      }
    }

    disconnectedCallback() {
      this.#targetChanges.disconnect();
      this.#resumeProjection?.();
      this.#resumeProjection = null;
      this.disarm();
      this.#restorePreview();
    }

    #watchTargets() {
      this.#targetChanges.disconnect();
      if (this.#interactive && this.#preview)
        this.#targetChanges.observe(this.#preview, {
          childList: true,
          subtree: true,
          attributes: true,
          attributeFilter: ["id"],
        });
    }

    arm() {
      if (this.#ready && this.#interactive) this.#setArmed(true);
    }

    disarm() {
      if (this.#ready && this.#interactive) this.#setArmed(false);
    }

    reset() {
      if (!this.#ready || !this.#interactive) return;
      this.#configuration = copy(this.#projected);
      this.#finishDraft();
      this.disarm();
      this.#render();
    }

    currentDraft() {
      return copy({
        armed: this.#armed,
        dirty: this.#dirty,
        configuration: this.#configuration,
        resolutions: Object.fromEntries(
          this.#configuration.targets.map((target) => [
            target.key,
            this.#resolution(target).status,
          ]),
        ),
      });
    }

    #build() {
      this.#editor = offer("section", "lf-targeting-editor");
      this.#editor.setAttribute("aria-label", "Targeted changes");

      const toolbar = offer("div", "lf-targeting-toolbar");
      this.#arm = offer("button", "lf-btn lf-targeting-arm", "Select element");
      this.#arm.setAttribute("aria-pressed", "false");
      this.#status = offer(
        "p",
        "lf-targeting-status",
        "Select an element in the preview, then choose its boundary.",
      );
      this.#status.id = `${this.id}-targeting-status`;
      toolbar.append(this.#arm, this.#status);
      this.#arm.addEventListener("click", () =>
        this.#armed ? this.disarm() : this.arm(),
      );

      this.#candidateList = offer("section", "lf-targeting-candidates");
      this.#candidateList.setAttribute("aria-label", "Target boundary choices");
      this.#candidateList.hidden = true;

      const targets = offer("section", "lf-targeting-targets");
      targets.append(offer("p", "lf-targeting-heading", "Targets"));
      this.#targetList = offer("div", "lf-targeting-target-list");
      targets.append(this.#targetList);

      const changes = offer("section", "lf-targeting-changes");
      changes.append(offer("p", "lf-targeting-heading", "Changes"));
      changes.append(this.#styleForm(), this.#instructionForm());
      this.#changeList = offer("div", "lf-targeting-change-list");
      changes.append(this.#changeList);

      const actions = offer("footer", "lf-targeting-actions");
      this.#revert = offer("button", "lf-btn lf-targeting-revert", "Revert draft");
      this.#submit = offer(
        "button",
        "lf-btn primary lf-targeting-submit",
        this.getAttribute("submit-label") ?? "Submit changes",
      );
      this.#revert.addEventListener("click", () => this.#revertDraft());
      actions.append(this.#revert, this.#submit);

      this.#editor.append(toolbar, this.#candidateList, targets, changes, actions);
      this.append(this.#editor);
      this.#preview.addEventListener("pointerover", this.#pointed);
      this.#preview.addEventListener("pointerleave", this.#leftPreview);
      this.#preview.addEventListener("click", this.#clicked, true);
      this.#commands();
    }

    #field(tag, cls, name, label) {
      const field = offer(tag, cls);
      field.name = `${this.id}-${name}`;
      field.label = label;
      field.size = "s";
      return field;
    }

    #styleForm() {
      const form = offer("section", "lf-targeting-change-form");
      form.setAttribute("aria-label", "Add box-model change");
      form.append(offer("p", "lf-targeting-change-summary", "Box model"));
      const fields = offer("div", "lf-targeting-change-fields");
      this.#styleTarget = this.#field(
        "wa-select",
        "lf-targeting-change-target",
        "style-target",
        "Style target",
      );
      this.#styleProperty = this.#field(
        "wa-select",
        "lf-targeting-property",
        "style-property",
        "Box-model property",
      );
      this.#styleProperty.append(
        ...STYLE_PROPERTIES.map(([value, label]) => option(value, label)),
      );
      this.#styleProperty.value = STYLE_PROPERTIES[0][0];
      this.#styleValue = this.#field(
        "wa-number-input",
        "lf-targeting-value",
        "style-value",
        "Pixel value",
      );
      this.#styleValue.min = 0;
      this.#styleValue.step = 1;
      this.#styleValue.value = "24";
      const add = offer("button", "lf-btn lf-targeting-add-style", "Add style");
      add.addEventListener("click", () => {
        const value = Number(this.#styleValue.value);
        if (!this.#styleTarget.value || !Number.isFinite(value) || value < 0) return;
        this.#configuration.changes.push({
          id: this.#nextChange(),
          target: this.#styleTarget.value,
          kind: "style",
          property: this.#styleProperty.value,
          value: `${value}px`,
        });
        this.#changed();
      });
      fields.append(this.#styleTarget, this.#styleProperty, this.#styleValue, add);
      form.append(fields);
      return form;
    }

    #instructionForm() {
      const form = offer("section", "lf-targeting-change-form");
      form.setAttribute("aria-label", "Add target instruction");
      form.append(offer("p", "lf-targeting-change-summary", "Prose instruction"));
      const fields = offer("div", "lf-targeting-form-row");
      this.#instructionTarget = this.#field(
        "wa-select",
        "lf-targeting-change-target",
        "instruction-target",
        "Instruction target",
      );
      this.#instructionText = this.#field(
        "wa-textarea",
        "lf-targeting-instruction",
        "instruction",
        "Target instruction",
      );
      this.#instructionText.resize = "auto";
      this.#instructionText.rows = 2;
      this.#instructionText.placeholder = "Describe the change for this target";
      const add = offer(
        "button",
        "lf-btn lf-targeting-add-instruction",
        "Add instruction",
      );
      add.addEventListener("click", () => {
        const text = normalizedWords(this.#instructionText.value);
        if (!this.#instructionTarget.value || !text) return;
        this.#configuration.changes.push({
          id: this.#nextChange(),
          target: this.#instructionTarget.value,
          kind: "instruction",
          text,
        });
        this.#instructionText.value = "";
        this.#changed();
      });
      fields.append(this.#instructionTarget, this.#instructionText, add);
      form.append(fields);
      return form;
    }

    #commands() {
      commands(this, "In visual targeting", [
        {
          id: "targeting.submit",
          contextKeys: ["1"],
          bindingBadge: null,
          control: this.#submit,
          decision: true,
          title: () => this.#submit.textContent,
          when: () => this.#canSubmit(),
          run: () => void this.#submitChanges(),
        },
        {
          id: "targeting.focused-element",
          keys: ["Enter"],
          title: "choose boundary",
          when: () =>
            this.#armed &&
            targetCandidates(this.#preview, document.activeElement).length > 0,
          run: () => this.#showCandidates(document.activeElement),
        },
        {
          id: "targeting.cancel-selection",
          keys: ["Escape"],
          title: "stop selecting",
          when: () => this.#armed,
          run: () => {
            this.disarm();
            focusDestination(this.#arm, "return");
          },
        },
      ]);
    }

    #setArmed(armed) {
      if (armed === this.#armed) return;
      this.#armed = armed;
      this.toggleAttribute("data-lf-targeting-armed", armed);
      this.#arm.setAttribute("aria-pressed", String(armed));
      this.#arm.textContent = armed ? "Stop selecting" : "Select element";
      this.#status.textContent = armed
        ? "Click an element, or focus it and press Enter."
        : "Select an element in the preview, then choose its boundary.";
      if (armed) {
        for (const element of [this.#preview, ...this.#preview.querySelectorAll("*")]) {
          if (element.matches(GENERATED) || element.tabIndex >= 0) continue;
          this.#tabIndexes.set(element, element.getAttribute("tabindex"));
          element.tabIndex = 0;
        }
        focusDestination(this.#preview, "move");
      } else {
        for (const [element, prior] of this.#tabIndexes) {
          if (prior === null) element.removeAttribute("tabindex");
          else element.setAttribute("tabindex", prior);
        }
        this.#tabIndexes.clear();
        this.#clearHovered();
        this.#candidates = [];
        keepsHidden(this.#candidateList, true);
      }
      paintKeys();
    }

    #pointed = (event) => {
      if (!this.#armed) return;
      const element = targetCandidates(this.#preview, {
        x: event.clientX,
        y: event.clientY,
      })[0];
      if (element === this.#hovered) return;
      this.#clearHovered();
      this.#hovered = element;
      this.#hovered?.classList.add("lf-targeting-candidate");
    };

    #leftPreview = () => this.#clearHovered();

    #clearHovered() {
      this.#hovered?.classList.toggle("lf-targeting-candidate", false);
      this.#hovered = null;
    }

    #clicked = (event) => {
      if (!this.#armed) return;
      if (!this.#showCandidates({ x: event.clientX, y: event.clientY })) return;
      event.preventDefault();
      event.stopImmediatePropagation();
    };

    #showCandidates(source) {
      if (!this.#armed) return false;
      this.#candidates = targetCandidates(this.#preview, source);
      if (!this.#candidates.length) return false;
      render(
        html`
          <p ${offered("lf-targeting-heading")}>Choose target boundary</p>
          ${repeat(
            this.#candidates,
            (candidate) => candidate,
            (candidate) => {
              const selection = this.#selection(candidate);
              return html`<button
                ${offered("lf-btn lf-targeting-candidate-choice")}
                @click=${() => this.#addTarget(candidate)}
              >
                <strong
                  >${this.#kind(candidate)} — ${this.#defaultName(candidate)}</strong
                >
                <span ${offered("lf-targeting-candidate-context")}
                  >${selection.label} · ${selection.text || "No visible text"}</span
                >
              </button>`;
            },
          )}
        `,
        this.#candidateList,
      );
      keepsHidden(this.#candidateList, false);
      const first = this.#candidateList.querySelector("button");
      if (first) focusDestination(first, "move");
      layoutChanged(this);
      return true;
    }

    #selection(element) {
      const classes = this.#authoredClasses.get(element) ?? [];
      const descriptor = element.id
        ? `${element.localName}#${element.id}`
        : classes.length
          ? `${element.localName}.${classes.join(".")}`
          : element.localName;
      const text = normalizedWords(says(element));
      return {
        reference: captureTargetReference(this.#preview, element),
        label: `<${descriptor}>`,
        text,
      };
    }

    #resolution(target) {
      return resolveTargetReference(this.#preview, target.reference);
    }

    #defaultName(element) {
      const words = normalizedWords(
        element.getAttribute("aria-label") ||
          element.querySelector(":scope > :is(h1, h2, h3, h4, h5, h6)")?.textContent ||
          element.querySelector(":scope > strong")?.textContent ||
          element.id ||
          says(element),
      );
      const base = words || element.id || element.localName;
      let name = base;
      let suffix = 2;
      const names = new Set(this.#configuration.targets.map((target) => target.name));
      while (names.has(name)) name = `${base} ${suffix++}`;
      return name;
    }

    #kind(element) {
      if (/^h[1-6]$/.test(element.localName)) return "Heading";
      if (element.localName === "button") return "Button";
      if (element.localName === "article") return "Article";
      if (element.localName === "section") return "Section";
      if (element.localName === "p") return "Paragraph";
      return element.localName === "lf-target-preview" ? "Preview" : "Element";
    }

    #addTarget(element) {
      const mayFocus = retainUserIntent({ available: () => this.isConnected });
      const selection = this.#selection(element);
      const signature = JSON.stringify(selection.reference);
      const existing = this.#configuration.targets.find(
        (target) => JSON.stringify(target.reference) === signature,
      );
      if (existing) {
        this.disarm();
        keepsHidden(this.#candidateList, true);
        void this.#focusName(existing.key, mayFocus);
        return;
      }
      const target = {
        key: this.#nextTarget(),
        name: this.#defaultName(element),
        scope: "element",
        className: null,
        ...selection,
      };
      this.#configuration.targets.push(target);
      keepsHidden(this.#candidateList, true);
      this.disarm();
      this.#changed();
      this.#styleTarget.value = target.key;
      this.#instructionTarget.value = target.key;
      void this.#focusName(target.key, mayFocus);
    }

    async #focusName(key, mayFocus) {
      const field = this.#targetList.querySelector(
        `[data-target-key="${key}"] .lf-targeting-name`,
      );
      await field.updateComplete;
      if (field.isConnected && mayFocus()) focusDestination(field, "move");
    }

    #nextTarget() {
      return `target-${++this.#targetSequence}`;
    }

    #nextChange() {
      return `change-${++this.#changeSequence}`;
    }

    #changed() {
      this.#beginDraft();
      this.#render();
      paintKeys();
    }

    #beginDraft() {
      this.#dirty = true;
      this.#resumeProjection ??= this.#controller.defer();
    }

    #finishDraft() {
      this.#dirty = false;
      this.#resumeProjection?.();
      this.#resumeProjection = null;
    }

    #render() {
      if (!this.#ready || !this.#interactive) {
        this.#applyPreview();
        return;
      }
      this.#renderTargets();
      this.#refreshTargetSelect(this.#styleTarget);
      this.#refreshTargetSelect(this.#instructionTarget);
      this.#renderChanges();
      this.#applyPreview();
      this.#paintAvailability();
      layoutChanged(this);
    }

    // A rebuild keeps the user in the row they stood in, or the nearest that survived it,
    // or on the control that adds one, rather than dropping them to the body when the
    // row they removed goes.
    #renderTargets() {
      const restoreFocus = holdFocus(this.#targetList, { key: "data-target-key" });
      render(
        this.#configuration.targets.length
          ? repeat(
              this.#configuration.targets,
              (target) => target.key,
              (target) => {
                const resolution = this.#resolution(target);
                const classes = this.#classesFor(target);
                return html`<section
                  ${offered("lf-targeting-target")}
                  data-target-key=${target.key}
                  data-lf-target-status=${resolution.status}
                >
                  <div ${offered("lf-targeting-form-row")}>
                    <wa-input
                      ${offered("lf-targeting-name")}
                      name=${`${this.id}-${target.key}-name`}
                      label=${`Name for ${target.label}`}
                      size="s"
                      .value=${target.name}
                      hint=${normalizedWords(target.name) ? "" : "Enter a target name before submitting."}
                      @input=${(event) => {
                        target.name = event.currentTarget.value;
                        this.#changed();
                      }}
                    ></wa-input>
                    <wa-select
                      ${offered("lf-targeting-scope")}
                      name=${`${this.id}-${target.key}-scope`}
                      label=${`Scope for ${target.name}`}
                      size="s"
                      .value=${target.scope}
                      @change=${(event) => {
                        target.scope = event.currentTarget.value;
                        target.className =
                          target.scope === "class"
                            ? (target.className ?? classes[0])
                            : null;
                        this.#changed();
                      }}
                    >
                      <wa-option ${offered()} value="element">This element</wa-option>
                      <wa-option ${offered()} value="class" ?disabled=${!classes.length}
                        >Shared class</wa-option
                      >
                    </wa-select>
                    <wa-select
                      ${offered("lf-targeting-class")}
                      name=${`${this.id}-${target.key}-class`}
                      label=${`Class for ${target.name}`}
                      size="s"
                      .value=${target.className ?? classes[0] ?? ""}
                      ?hidden=${target.scope !== "class"}
                      ?disabled=${target.scope !== "class"}
                      @change=${(event) => {
                        target.className = event.currentTarget.value;
                        this.#changed();
                      }}
                    >
                      ${repeat(
                        classes,
                        (value) => value,
                        (value) =>
                          html` <wa-option ${offered()} value=${value}
                            >.${value} · ${this.#classCount(value)} matches</wa-option
                          >`,
                      )}
                    </wa-select>
                    <button
                      ${offered("lf-btn lf-targeting-remove")}
                      aria-label=${`Remove target ${target.name}`}
                      @click=${() => {
                        this.#configuration.targets =
                          this.#configuration.targets.filter(
                            (candidate) => candidate.key !== target.key,
                          );
                        this.#configuration.changes =
                          this.#configuration.changes.filter(
                            (change) => change.target !== target.key,
                          );
                        this.#changed();
                      }}
                    >
                      Remove target
                    </button>
                  </div>
                  <p ${offered("lf-targeting-change-summary")}>
                    ${
                      resolution.status === "resolved"
                        ? target.label
                        : `${target.label} · ${resolution.status === "detached" ? "Detached" : "Ambiguous"} target`
                    }
                  </p>
                </section>`;
              },
            )
          : html`<p ${offered("lf-targeting-empty")}>No targets selected.</p>`,
        this.#targetList,
      );
      restoreFocus?.(this.#arm);
    }

    #classesFor(target) {
      const resolution = this.#resolution(target);
      return resolution.status === "resolved"
        ? (this.#authoredClasses.get(resolution.element) ?? [])
        : [];
    }

    #classCount(className) {
      return [...this.#authoredClasses.values()].filter((classes) =>
        classes.includes(className),
      ).length;
    }

    #refreshTargetSelect(select) {
      const targets = this.#configuration.targets;
      const selected = select.value;
      render(
        targets.length
          ? repeat(
              targets,
              (target) => target.key,
              (target) =>
                html` <wa-option ${offered()} value=${target.key}
                  >${keyed(target.name, target.name)}</wa-option
                >`,
            )
          : html`<wa-option ${offered()} value="">Select a target</wa-option>`,
        select,
      );
      select.toggleAttribute("disabled", !targets.length);
      select.value = targets.some((target) => target.key === selected)
        ? selected
        : (targets[0]?.key ?? "");
    }

    #renderChanges() {
      const restoreFocus = holdFocus(this.#changeList, { key: "data-change-id" });
      render(
        this.#configuration.changes.length
          ? repeat(
              this.#configuration.changes,
              (change) => change.id,
              (change) => {
                const target = this.#configuration.targets.find(
                  (candidate) => candidate.key === change.target,
                );
                return html`<div
                  ${offered("lf-targeting-change")}
                  data-change-id=${change.id}
                >
                  <span ${offered("lf-targeting-change-summary")}
                    >${
                      change.kind === "style"
                        ? `${target.name}: ${change.property} ${change.value}`
                        : `${target.name}: ${change.text}`
                    }</span
                  >
                  <button
                    ${offered("lf-btn lf-targeting-remove")}
                    aria-label=${`Remove change for ${target.name}`}
                    @click=${() => {
                      this.#configuration.changes = this.#configuration.changes.filter(
                        (candidate) => candidate.id !== change.id,
                      );
                      this.#changed();
                    }}
                  >
                    Remove
                  </button>
                </div>`;
              },
            )
          : html`<p ${offered("lf-targeting-empty")}>No changes added.</p>`,
        this.#changeList,
      );
      restoreFocus?.(this.#arm);
    }

    #elementsFor(target) {
      const resolution = this.#resolution(target);
      if (resolution.status !== "resolved") return [];
      if (target.scope !== "class" || !target.className) return [resolution.element];
      return [this.#preview, ...this.#preview.querySelectorAll("*")].filter((element) =>
        (this.#authoredClasses.get(element) ?? []).includes(target.className),
      );
    }

    #restorePreview() {
      this.#restoreStyles(new Map());
      this.#paintClasses(new Set());
    }

    // Each saved property the draft's `styles` no longer name gets its saved value back.
    #restoreStyles(styles) {
      for (const [element, properties] of this.#restoredStyles) {
        for (const [property, prior] of properties) {
          if (styles.get(element)?.has(property)) continue;
          if (prior.value)
            element.style.setProperty(property, prior.value, prior.priority);
          else element.style.removeProperty(property);
          properties.delete(property);
        }
        if (!properties.size) this.#restoredStyles.delete(element);
      }
    }

    // Each authored element carries the selection mark exactly when a target covers it,
    // and no hover mark, so a repaint writes only the elements whose marks moved.
    #paintClasses(selected) {
      for (const element of this.#authoredClasses.keys()) {
        element.classList.toggle("lf-targeting-selected", selected.has(element));
        element.classList.toggle("lf-targeting-candidate", false);
      }
    }

    // The draft's styles in change order, a later change to one property winning. A
    // property no change holds any longer gets its saved value back; one a change still
    // holds is set straight to the draft's value, never restored first and set again.
    #applyPreview() {
      if (!this.#preview) return;
      const selected = new Set();
      for (const target of this.#configuration.targets)
        for (const element of this.#elementsFor(target)) selected.add(element);
      const styles = new Map();
      for (const change of this.#configuration.changes) {
        if (change.kind !== "style") continue;
        const target = this.#configuration.targets.find(
          (candidate) => candidate.key === change.target,
        );
        if (!target) continue;
        for (const element of this.#elementsFor(target)) {
          if (!styles.has(element)) styles.set(element, new Map());
          styles.get(element).set(change.property, change.value);
        }
      }
      this.#restoreStyles(styles);
      for (const [element, wanted] of styles) {
        let properties = this.#restoredStyles.get(element);
        if (!properties) {
          properties = new Map();
          this.#restoredStyles.set(element, properties);
        }
        for (const [property, value] of wanted) {
          if (!properties.has(property))
            properties.set(property, {
              value: element.style.getPropertyValue(property),
              priority: element.style.getPropertyPriority(property),
            });
          element.style.setProperty(property, value);
        }
      }
      this.#paintClasses(selected);
    }

    #canSubmit() {
      return (
        !this.#sending &&
        this.#configuration.targets.length > 0 &&
        this.#configuration.changes.length > 0 &&
        this.#configuration.targets.every(
          (target) =>
            normalizedWords(target.name) &&
            this.#resolution(target).status === "resolved",
        ) &&
        (this.#controller.read().actions.submit?.available ?? false)
      );
    }

    #paintAvailability() {
      if (!this.#submit) return;
      this.#revert.toggleAttribute("disabled", !this.#dirty);
      paintKeys();
    }

    #revertDraft() {
      this.reset();
      notice("Draft reverted");
    }

    async #submitChanges() {
      if (!this.#canSubmit()) return;
      const detail = copy(this.#configuration);
      for (const target of detail.targets) target.name = normalizedWords(target.name);
      this.#sending = true;
      this.#finishDraft();
      this.#submit.setAttribute("aria-busy", "true");
      this.#paintAvailability();
      try {
        const accepted = await this.#controller.dispatch({
          kind: "action",
          verb: "submit",
          detail,
        })?.delivery;
        if (accepted) notice("Targeted changes submitted");
        else this.#beginDraft();
      } finally {
        this.#sending = false;
        this.#submit.removeAttribute("aria-busy");
        this.#paintAvailability();
      }
    }

    #load(configuration) {
      this.#configuration = copy(configuration);
      this.#targetSequence = Math.max(
        0,
        ...this.#configuration.targets.map((target) => Number(target.key.slice(7))),
      );
      this.#changeSequence = Math.max(
        0,
        ...this.#configuration.changes.map((change) => Number(change.id.slice(7))),
      );
      this.#finishDraft();
      this.#render();
    }

    renderState(state) {
      if (!this.#ready) return;
      const configuration = state.submit?.action
        ? state.submit.detail
        : emptyConfiguration();
      const signature = JSON.stringify(configuration);
      if (signature === this.#projectionSignature) return;
      this.#projectionSignature = signature;
      this.#projected = copy(configuration);
      this.#load(configuration);
    }
  },
);
