// <lf-level>: a level on a scale, a native range input behind a `value` property.
//
// Nothing here is written for Leaf. Like a control whose property notifies, it says
// `level-change` at every change of its value, a script's set included, and the range
// keeps a value it is set within its scale, so what it says after a set can be
// another value than the set gave it. Its declaration's `record` names `value` and
// that event (module-plain-elements.md, "`record.property`").
customElements.define(
  "lf-level",
  class extends HTMLElement {
    #range = Object.assign(document.createElement("input"), { type: "range" });

    connectedCallback() {
      if (this.#range.isConnected) return;
      for (const name of ["min", "max", "value"])
        if (this.hasAttribute(name)) this.#range[name] = this.getAttribute(name);
      this.#range.setAttribute("aria-label", this.getAttribute("label") ?? "");
      this.#range.addEventListener("input", () => this.#say());
      this.append(this.#range);
    }

    get value() {
      return this.#range.value;
    }
    set value(next) {
      const before = this.#range.value;
      this.#range.value = next;
      if (this.#range.value !== before) this.#say();
    }

    #say() {
      this.dispatchEvent(new Event("level-change"));
    }
  },
);
