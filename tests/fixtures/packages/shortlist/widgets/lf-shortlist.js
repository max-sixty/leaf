// <lf-shortlist>: candidates the user picks from, each pick its own recorded action.
//
// Every change comes in one way, a `--toggle` command whose button's value names a
// candidate: the authored buttons here send it, and so may any other widget. The
// element imports nothing. On a Leaf page, Leaf sets its `state` and the pick is an
// `lf-action` event Leaf records, so Undo takes one pick back; on a page without Leaf
// nobody sets `state` and the element keeps the picks itself. Either way it holds the
// list and its picks as its `shortlist` output and says `change`, which is all another
// widget reads.

customElements.define(
  "lf-shortlist",
  class extends HTMLElement {
    // The reading a Leaf page sets; a plain host sets none.
    #state = null;
    #kept = new Set();
    /** @type {HTMLButtonElement[] | null} */
    #buttons = null;

    get state() {
      return this.#state;
    }
    set state(next) {
      this.#state = next;
      this.#draw();
    }

    connectedCallback() {
      if (this.#buttons) return;
      this.#buttons = [...this.querySelectorAll("button[value]")];
      this.addEventListener("command", (event) => {
        if (event.command === "--toggle") this.toggle(event.source?.value);
      });
      this.#draw();
    }

    picked(key) {
      return this.#state
        ? Boolean(this.#state.pick.units[key]?.detail.picked)
        : this.#kept.has(key);
    }

    toggle(key) {
      const button = this.#buttons.find((candidate) => candidate.value === key);
      if (!button) return;
      const picked = !this.picked(key);
      if (this.#state)
        this.dispatchEvent(
          new CustomEvent("lf-action", {
            detail: {
              verb: "pick",
              detail: { candidate: key, picked },
              says: `${picked ? "Picked" : "Dropped"} ${button.textContent.trim()}`,
            },
          }),
        );
      else {
        if (picked) this.#kept.add(key);
        else this.#kept.delete(key);
        this.#draw();
      }
    }

    #draw() {
      if (!this.#buttons) return;
      const candidates = this.#buttons.map((button) => ({
        key: button.value,
        name: button.textContent.trim(),
        picked: this.picked(button.value),
      }));
      for (const [index, button] of this.#buttons.entries()) {
        const pressed = String(candidates[index].picked);
        if (button.getAttribute("aria-pressed") !== pressed)
          button.setAttribute("aria-pressed", pressed);
      }
      this.shortlist = { candidates };
      this.dispatchEvent(new Event("change"));
    }
  },
);
