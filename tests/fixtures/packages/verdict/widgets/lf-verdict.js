// <lf-verdict>: a ship-or-hold decision, written on plain HTMLElement.
//
// The module imports nothing. Leaf sets `state` as the decision's reading moves and
// `notes`, a line for each choice, as the source its `source` names delivers. A press
// dispatches `lf-action`, which Leaf records, and each choice carries `data-lf-part`,
// which makes it a comment target. On a page without Leaf nobody sets `state`, and
// the choices stay unavailable.

const CHOICES = [
  ["ship", "Ship"],
  ["hold", "Hold"],
];

// Write an attribute only where it would read back differently.
const keep = (node, name, value) => {
  if (node.getAttribute(name) === value) return;
  if (value === null) node.removeAttribute(name);
  else node.setAttribute(name, value);
};

customElements.define(
  "lf-verdict",
  class extends HTMLElement {
    // The words On Me shows for the answer.
    static answerWords(value) {
      return CHOICES.find(([choice]) => choice === value)?.[1] ?? "";
    }

    #state = null;
    #notes = null;

    get state() {
      return this.#state;
    }
    set state(next) {
      this.#state = next;
      this.#draw();
    }

    get notes() {
      return this.#notes;
    }
    set notes(next) {
      this.#notes = next;
      this.#draw();
    }

    connectedCallback() {
      if (this.childElementCount) return;
      for (const [value, label] of CHOICES) {
        const button = document.createElement("button");
        button.type = "button";
        button.value = value;
        button.textContent = label;
        button.dataset.lfPart = `choice:${value}`;
        button.addEventListener("click", () => this.#decide(value, label));
        this.append(button);
      }
      this.#draw();
    }

    #decide(value, label) {
      if (!this.#state?.decide.available) return;
      this.dispatchEvent(
        new CustomEvent("lf-action", {
          detail: { verb: "decide", detail: { value }, says: `Chose “${label}”` },
        }),
      );
    }

    #draw() {
      const decide = this.#state?.decide;
      for (const button of this.querySelectorAll("button")) {
        keep(button, "aria-pressed", String(decide?.value === button.value));
        keep(button, "aria-disabled", String(!decide?.available));
        keep(button, "title", this.#notes?.[button.value] ?? null);
      }
    }
  },
);
