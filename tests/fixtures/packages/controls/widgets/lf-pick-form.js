// <lf-pick-form>: a form of native radios or checkboxes, enhanced.
//
// Nothing here is written for Leaf. The browser keeps each input's `checked`, the
// label's press, Space, Tab and the form's value, and the tag's declaration names
// `checked` as the property its attribute record reads on each input
// (module-plain-elements.md, "`record.property`"). This element adds two behaviours
// a radio group lacks.
customElements.define(
  "lf-pick-form",
  class extends HTMLElement {
    #before = null;

    constructor() {
      super();
      // The radio checked before this press, read before the browser changes it.
      const remember = () => {
        this.#before = this.querySelector("input[type=radio]:checked");
      };
      this.addEventListener("pointerdown", remember, true);
      this.addEventListener("keydown", remember, true);
      this.addEventListener("click", (event) => this.#clear(event));
      this.addEventListener("keyup", (event) => {
        if (event.key === " ") this.#clear(event);
      });
      this.addEventListener("keydown", (event) => this.#walk(event));
    }

    // A second press on the picked radio clears it. A radio fires `input` and
    // `change` only when it becomes checked, so the element fires them here.
    // Space clears at its keyup, since Chromium and WebKit send a checked radio no
    // click for it. Preventing that keyup's default stops the click that would
    // check the radio again. A click keeps its default: Chromium and WebKit undo
    // what a cancelled click changed, which would put the pick back.
    #clear(event) {
      const { target } = event;
      if (!target.matches?.("input[type=radio]") || target !== this.#before) return;
      if (event.type === "keyup") event.preventDefault();
      target.checked = false;
      this.#before = null;
      target.dispatchEvent(new Event("input", { bubbles: true }));
      target.dispatchEvent(new Event("change", { bubbles: true }));
    }

    // Arrow keys move focus among the radios. Preventing the key's default stops
    // the browser from moving the pick along with the focus.
    #walk(event) {
      const step = { ArrowUp: -1, ArrowLeft: -1, ArrowDown: 1, ArrowRight: 1 }[
        event.key
      ];
      if (!step || !event.target.matches?.("input[type=radio]")) return;
      event.preventDefault();
      const radios = [...this.querySelectorAll("input[type=radio]")];
      radios[radios.indexOf(event.target) + step]?.focus();
    }
  },
);
