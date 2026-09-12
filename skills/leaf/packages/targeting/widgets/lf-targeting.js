/* lf-targeting: a local visual-edit draft with one structured durable action.
 *
 * The preview remains authored light DOM. Selection records an authored id when one
 * exists and otherwise an exact element path plus visible context. Working changes
 * mutate only declared box-model properties, after saving the prior inline value;
 * every repaint restores those values before applying the current ordered draft.
 * Prose carries a target key beside its words. The complete target/change graph is
 * submitted as one recordless action, so replay, refusal, and undo use Leaf's ordinary
 * projection instead of a widget-owned event history. */
import {
  actionAvailable,
  commands,
  failSoft,
  layoutChanged,
  notice,
  offer,
  once,
  paintKeys,
  projectionChanged,
  quoted,
  says,
  sendAction,
} from "/runtime/widget-api.js";

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
  const node = document.createElement("option");
  node.value = value;
  node.textContent = label;
  return node;
}

customElements.define(
  "lf-targeting",
  class extends HTMLElement {
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

    connectedCallback() {
      if (!once(this)) {
        if (this.#interactive) this.#applyPreview();
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
        this.#render();
      } catch (error) {
        this.#restorePreview();
        failSoft(this, error);
      }
    }

    disconnectedCallback() {
      this.#disarm();
      this.#restorePreview();
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
      this.#arm.addEventListener("click", () => this.#setArmed(!this.#armed));

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
      this.#submit.addEventListener("click", () => void this.#submitChanges());
      actions.append(this.#revert, this.#submit);

      this.#editor.append(toolbar, this.#candidateList, targets, changes, actions);
      this.append(this.#editor);
      this.#preview.addEventListener("pointerover", this.#pointed);
      this.#preview.addEventListener("pointerleave", this.#leftPreview);
      this.#preview.addEventListener("click", this.#clicked, true);
      this.#commands();
    }

    #styleForm() {
      const form = offer("section", "lf-targeting-change-form");
      form.setAttribute("aria-label", "Add box-model change");
      form.append(offer("p", "lf-targeting-change-summary", "Box model"));
      const fields = offer("div", "lf-targeting-change-fields");
      this.#styleTarget = offer("select", "lf-targeting-change-target");
      this.#styleTarget.name = `${this.id}-style-target`;
      this.#styleTarget.setAttribute("aria-label", "Style target");
      this.#styleProperty = offer("select", "lf-targeting-property");
      this.#styleProperty.name = `${this.id}-style-property`;
      this.#styleProperty.setAttribute("aria-label", "Box-model property");
      this.#styleProperty.append(
        ...STYLE_PROPERTIES.map(([value, label]) => option(value, label)),
      );
      this.#styleValue = offer("input", "lf-targeting-value", undefined, "number");
      this.#styleValue.name = `${this.id}-style-value`;
      this.#styleValue.min = "0";
      this.#styleValue.step = "1";
      this.#styleValue.value = "24";
      this.#styleValue.setAttribute("aria-label", "Pixel value");
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
      this.#instructionTarget = offer("select", "lf-targeting-change-target");
      this.#instructionTarget.name = `${this.id}-instruction-target`;
      this.#instructionTarget.setAttribute("aria-label", "Instruction target");
      this.#instructionText = offer("textarea", "lf-targeting-instruction");
      this.#instructionText.name = `${this.id}-instruction`;
      this.#instructionText.placeholder = "Describe the change for this target";
      this.#instructionText.setAttribute("aria-label", "Target instruction");
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
      commands(
        this,
        "In visual targeting",
        [
          {
            id: "targeting.submit",
            control: this.#submit,
            decision: () => this.#submit.textContent,
            does: () => this.#submit.textContent,
            line: () => this.#submit.textContent.toLowerCase(),
            when: () => this.#canSubmit(),
            run: () => this.#submit.click(),
          },
          {
            id: "targeting.focused-element",
            keys: ["Enter"],
            does: "Choose the focused preview element",
            line: "choose this element",
            when: () => this.#armed && this.#preview.contains(document.activeElement),
            run: () => this.#showCandidates(document.activeElement),
          },
          {
            id: "targeting.cancel-selection",
            keys: ["Escape"],
            does: "Stop selecting elements",
            line: "stop selecting",
            when: () => this.#armed,
            run: () => this.#disarm(true),
          },
        ],
        {
          answer: () =>
            `${this.#configuration.targets.length} targets · ${this.#configuration.changes.length} changes`,
        },
      );
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
        this.#preview.focus({ preventScroll: true });
      } else {
        for (const [element, prior] of this.#tabIndexes) {
          if (prior === null) element.removeAttribute("tabindex");
          else element.setAttribute("tabindex", prior);
        }
        this.#tabIndexes.clear();
        this.#clearHovered();
        this.#candidates = [];
        if (this.#candidateList) this.#candidateList.hidden = true;
      }
      paintKeys();
    }

    #disarm(refocus = false) {
      if (!this.#armed) return;
      this.#setArmed(false);
      if (refocus && this.#arm?.isConnected) this.#arm.focus({ preventScroll: true });
    }

    #authoredElement(start) {
      let element = start instanceof Element ? start : null;
      while (element && element !== this.#preview && element.matches(GENERATED))
        element = element.parentElement;
      return element && (element === this.#preview || this.#preview.contains(element))
        ? element
        : null;
    }

    #pointed = (event) => {
      if (!this.#armed) return;
      const element = this.#authoredElement(event.target);
      if (element === this.#hovered) return;
      this.#clearHovered();
      this.#hovered = element;
      this.#hovered?.classList.add("lf-targeting-candidate");
    };

    #leftPreview = () => this.#clearHovered();

    #clearHovered() {
      this.#hovered?.classList.remove("lf-targeting-candidate");
      this.#hovered = null;
    }

    #clicked = (event) => {
      if (!this.#armed) return;
      const element = this.#authoredElement(event.target);
      if (!element) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      this.#showCandidates(element);
    };

    #showCandidates(element) {
      if (!this.#armed) return;
      this.#candidates = [];
      for (
        let current = this.#authoredElement(element);
        current;
        current = current.parentElement
      ) {
        if (!current.matches(GENERATED)) this.#candidates.push(current);
        if (current === this.#preview || this.#candidates.length === 4) break;
      }
      this.#candidateList.replaceChildren(
        offer("p", "lf-targeting-heading", "Choose target boundary"),
      );
      for (const candidate of this.#candidates) {
        const selector = this.#selector(candidate);
        const button = offer("button", "lf-btn lf-targeting-candidate-choice");
        const title = document.createElement("strong");
        title.textContent = `${this.#kind(candidate)} — ${this.#defaultName(candidate)}`;
        const context = offer(
          "span",
          "lf-targeting-candidate-context",
          `${selector.label} · ${selector.text || "No visible text"}`,
        );
        button.append(title, context);
        button.addEventListener("click", () => this.#addTarget(candidate));
        this.#candidateList.append(button);
      }
      this.#candidateList.hidden = false;
      this.#candidateList.querySelector("button")?.focus({ preventScroll: true });
      layoutChanged(this);
    }

    #selector(element) {
      const path = [];
      for (let current = element; current && current !== this.#preview;) {
        const parent = current.parentElement;
        const siblings = [...parent.children].filter(
          (node) => !node.matches(GENERATED) && node.localName === current.localName,
        );
        path.unshift({ tag: current.localName, index: siblings.indexOf(current) });
        current = parent;
      }
      const classes = this.#authoredClasses.get(element) ?? [];
      const descriptor = element.id
        ? `${element.localName}#${element.id}`
        : classes.length
          ? `${element.localName}.${classes.join(".")}`
          : element.localName;
      const text = normalizedWords(says(element)).slice(0, 100);
      return {
        ...(element.id ? { authoredId: element.id } : {}),
        path,
        label: `<${descriptor}>`,
        text,
      };
    }

    #resolve(selector) {
      if (selector.authoredId) {
        const element = document.getElementById(selector.authoredId);
        if (element === this.#preview || this.#preview.contains(element))
          return element;
        return null;
      }
      let element = this.#preview;
      for (const step of selector.path) {
        const matches = [...element.children].filter(
          (child) => !child.matches(GENERATED) && child.localName === step.tag,
        );
        element = matches[step.index];
        if (!element) return null;
      }
      return element;
    }

    #defaultName(element) {
      const words = normalizedWords(
        element.getAttribute("aria-label") ||
          element.querySelector(":scope > :is(h1, h2, h3, h4, h5, h6)")?.textContent ||
          element.querySelector(":scope > strong")?.textContent ||
          element.id ||
          says(element),
      );
      const base = words.slice(0, 36) || element.id || element.localName;
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
      const selector = this.#selector(element);
      const signature = JSON.stringify({
        authoredId: selector.authoredId ?? null,
        path: selector.path,
      });
      const existing = this.#configuration.targets.find(
        (target) =>
          JSON.stringify({
            authoredId: target.selector.authoredId ?? null,
            path: target.selector.path,
          }) === signature,
      );
      if (existing) {
        this.#disarm();
        this.#candidateList.hidden = true;
        this.#targetList
          .querySelector(`[data-target-key="${existing.key}"] input`)
          ?.focus({ preventScroll: true });
        return;
      }
      const target = {
        key: this.#nextTarget(),
        name: this.#defaultName(element),
        scope: "element",
        className: null,
        selector,
      };
      this.#configuration.targets.push(target);
      this.#candidateList.hidden = true;
      this.#disarm();
      this.#changed();
      this.#styleTarget.value = target.key;
      this.#instructionTarget.value = target.key;
      this.#targetList.lastElementChild
        ?.querySelector("input")
        ?.focus({ preventScroll: true });
    }

    #nextTarget() {
      return `target-${++this.#targetSequence}`;
    }

    #nextChange() {
      return `change-${++this.#changeSequence}`;
    }

    #changed() {
      this.#dirty = true;
      this.#render();
      paintKeys();
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

    #renderTargets() {
      this.#targetList.replaceChildren();
      if (!this.#configuration.targets.length) {
        this.#targetList.append(
          offer("p", "lf-targeting-empty", "No targets selected."),
        );
        return;
      }
      for (const target of this.#configuration.targets) {
        const row = offer("section", "lf-targeting-target");
        row.dataset.targetKey = target.key;
        const fields = offer("div", "lf-targeting-form-row");
        const name = offer("input", "lf-targeting-name", undefined, "text");
        name.name = `${this.id}-${target.key}-name`;
        name.value = target.name;
        name.setAttribute("aria-label", `Name for ${target.selector.label}`);
        const priorName = target.name;
        name.addEventListener("input", () => {
          const value = normalizedWords(name.value);
          if (!value) return;
          target.name = value;
          for (const select of [this.#styleTarget, this.#instructionTarget]) {
            const targetOption = select.querySelector(`option[value="${target.key}"]`);
            if (targetOption) targetOption.textContent = value;
          }
          this.#dirty = true;
          this.#paintAvailability();
        });
        name.addEventListener("change", () => {
          const value = normalizedWords(name.value);
          if (!value) {
            target.name = priorName;
            name.value = priorName;
            this.#changed();
            return;
          }
          target.name = value;
          this.#changed();
        });
        const scope = offer("select", "lf-targeting-scope");
        scope.name = `${this.id}-${target.key}-scope`;
        scope.setAttribute("aria-label", `Scope for ${target.name}`);
        scope.append(
          option("element", "This element"),
          option("class", "Shared class"),
        );
        scope.value = target.scope;
        const classes = this.#classesFor(target);
        scope.querySelector('option[value="class"]').disabled = !classes.length;
        const className = offer("select", "lf-targeting-class");
        className.name = `${this.id}-${target.key}-class`;
        className.setAttribute("aria-label", `Class for ${target.name}`);
        className.append(
          ...classes.map((value) =>
            option(value, `.${value} · ${this.#classCount(value)} matches`),
          ),
        );
        className.value = target.className ?? classes[0] ?? "";
        className.hidden = target.scope !== "class";
        className.disabled = target.scope !== "class";
        scope.addEventListener("change", () => {
          target.scope = scope.value;
          target.className = scope.value === "class" ? className.value : null;
          this.#changed();
        });
        className.addEventListener("change", () => {
          target.className = className.value;
          this.#changed();
        });
        const remove = offer("button", "lf-btn lf-targeting-remove", "Remove target");
        remove.setAttribute("aria-label", `Remove target ${target.name}`);
        remove.addEventListener("click", () => {
          this.#configuration.targets = this.#configuration.targets.filter(
            (candidate) => candidate.key !== target.key,
          );
          this.#configuration.changes = this.#configuration.changes.filter(
            (change) => change.target !== target.key,
          );
          this.#changed();
        });
        fields.append(name, scope, className, remove);
        row.append(
          fields,
          offer("p", "lf-targeting-change-summary", target.selector.label),
        );
        this.#targetList.append(row);
      }
    }

    #classesFor(target) {
      const element = this.#resolve(target.selector);
      return element ? (this.#authoredClasses.get(element) ?? []) : [];
    }

    #classCount(className) {
      return [...this.#authoredClasses.values()].filter((classes) =>
        classes.includes(className),
      ).length;
    }

    #refreshTargetSelect(select) {
      const selected = select.value;
      select.replaceChildren();
      if (!this.#configuration.targets.length) {
        select.append(option("", "Select a target"));
        select.disabled = true;
        return;
      }
      select.disabled = false;
      select.append(
        ...this.#configuration.targets.map((target) => option(target.key, target.name)),
      );
      if (this.#configuration.targets.some((target) => target.key === selected))
        select.value = selected;
    }

    #renderChanges() {
      this.#changeList.replaceChildren();
      if (!this.#configuration.changes.length) {
        this.#changeList.append(offer("p", "lf-targeting-empty", "No changes added."));
        return;
      }
      for (const change of this.#configuration.changes) {
        const target = this.#configuration.targets.find(
          (candidate) => candidate.key === change.target,
        );
        const summary =
          change.kind === "style"
            ? `${target?.name}: ${change.property} ${change.value}`
            : `${target?.name}: ${change.text}`;
        const row = offer("div", "lf-targeting-change");
        row.append(offer("span", "lf-targeting-change-summary", summary));
        const remove = offer("button", "lf-btn lf-targeting-remove", "Remove");
        remove.setAttribute("aria-label", `Remove change for ${target?.name}`);
        remove.addEventListener("click", () => {
          this.#configuration.changes = this.#configuration.changes.filter(
            (candidate) => candidate.id !== change.id,
          );
          this.#changed();
        });
        row.append(remove);
        this.#changeList.append(row);
      }
    }

    #elementsFor(target) {
      const representative = this.#resolve(target.selector);
      if (!representative) return [];
      if (target.scope !== "class" || !target.className) return [representative];
      return [this.#preview, ...this.#preview.querySelectorAll("*")].filter((element) =>
        (this.#authoredClasses.get(element) ?? []).includes(target.className),
      );
    }

    #restorePreview() {
      for (const [element, properties] of this.#restoredStyles)
        for (const [property, prior] of properties) {
          if (prior.value)
            element.style.setProperty(property, prior.value, prior.priority);
          else element.style.removeProperty(property);
        }
      this.#restoredStyles.clear();
      for (const element of this.#authoredClasses.keys())
        element.classList.remove("lf-targeting-selected", "lf-targeting-candidate");
    }

    #applyPreview() {
      if (!this.#preview) return;
      this.#restorePreview();
      for (const target of this.#configuration.targets)
        for (const element of this.#elementsFor(target))
          element.classList.add("lf-targeting-selected");
      for (const change of this.#configuration.changes) {
        if (change.kind !== "style") continue;
        const target = this.#configuration.targets.find(
          (candidate) => candidate.key === change.target,
        );
        if (!target) continue;
        for (const element of this.#elementsFor(target)) {
          let properties = this.#restoredStyles.get(element);
          if (!properties) {
            properties = new Map();
            this.#restoredStyles.set(element, properties);
          }
          if (!properties.has(change.property))
            properties.set(change.property, {
              value: element.style.getPropertyValue(change.property),
              priority: element.style.getPropertyPriority(change.property),
            });
          element.style.setProperty(change.property, change.value);
        }
      }
    }

    #canSubmit() {
      return (
        !this.#sending &&
        this.#configuration.targets.length > 0 &&
        this.#configuration.changes.length > 0 &&
        actionAvailable(this, "submit")
      );
    }

    #paintAvailability() {
      if (!this.#submit) return;
      this.#submit.disabled = !this.#canSubmit();
      this.#revert.disabled = !this.#dirty;
      paintKeys();
    }

    #revertDraft() {
      this.#configuration = copy(this.#projected);
      this.#dirty = false;
      this.#render();
      projectionChanged();
      notice("Draft reverted");
    }

    async #submitChanges() {
      if (!this.#canSubmit()) return;
      const detail = copy(this.#configuration);
      this.#sending = true;
      this.#dirty = false;
      this.#submit.setAttribute("aria-busy", "true");
      this.#paintAvailability();
      try {
        const accepted = await sendAction(this, "submit", detail);
        if (accepted) notice("Targeted changes submitted");
        else this.#dirty = true;
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
      this.#dirty = false;
      this.#render();
    }

    renderState(state) {
      if (!this.#ready) return true;
      const configuration =
        state.configuration?.action === "submit"
          ? state.configuration.detail
          : emptyConfiguration();
      const signature = JSON.stringify(configuration);
      if (signature === this.#projectionSignature) return true;
      if (this.#dirty) return false;
      this.#projectionSignature = signature;
      this.#projected = copy(configuration);
      this.#load(configuration);
      return true;
    }
  },
);
