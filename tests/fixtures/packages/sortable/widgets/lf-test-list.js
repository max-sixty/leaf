// A list the user reorders, which is its own position container: a pointer drag or
// Alt+ArrowUp/Down on the focused entry records `move` with the list's own id as the
// destination, and render() places the entries in the recorded order.
import { LeafElement } from "/runtime/lib/leaf-element.js";
import { rankAt } from "/runtime/lib/rank.js";
import { move } from "/runtime/widget-api.js";

const ENTRY = "lf-test-entry";

customElements.define(
  "lf-test-list",
  class extends LeafElement {
    setup() {
      this.addEventListener("pointerdown", (event) => this.#press(event));
      this.lfCommands = {
        title: "In a list",
        rows: [
          {
            id: "list.up",
            keys: ["Alt+ArrowUp"],
            title: "move entry up",
            run: () => this.#step(-1),
          },
          {
            id: "list.down",
            keys: ["Alt+ArrowDown"],
            title: "move entry down",
            run: () => this.#step(1),
          },
        ],
      };
    }

    get #entries() {
      return [...this.children].filter((el) => el.matches(ENTRY));
    }

    render() {
      const recorded = this.state.move.value[this.id] ?? [];
      const entries = this.#entries;
      const want = recorded
        .map((id) => entries.find((el) => el.id === id))
        .filter(Boolean);
      for (const el of entries) if (!want.includes(el)) want.push(el);
      want.forEach((el, i) => {
        if (this.children[i] !== el) move(this, el, this.children[i] ?? null);
        if (el.getAttribute("tabindex") !== "0") el.setAttribute("tabindex", "0");
      });
    }

    #place(entry, index) {
      move(this, entry, this.#entries.filter((el) => el !== entry)[index] ?? null);
    }

    #commit(entry) {
      const index = this.#entries.indexOf(entry);
      this.record("move", {
        unit: entry.id,
        value: this.id,
        rank: rankAt(this.state.move, this.id, index, entry.id),
      });
    }

    #step(delta) {
      const entry = document.activeElement?.closest(ENTRY);
      if (!entry || entry.parentElement !== this) return;
      const to = this.#entries.indexOf(entry) + delta;
      if (to < 0 || to >= this.#entries.length) return;
      this.#place(entry, to);
      this.#commit(entry);
      entry.focus();
    }

    #press(event) {
      const entry = event.target.closest?.(ENTRY);
      if (event.button !== 0 || !entry || entry.parentElement !== this) return;
      const start = this.#entries.indexOf(entry);
      const release = this.defer();
      entry.setPointerCapture(event.pointerId);
      const follow = (moved) => {
        const others = this.#entries.filter((el) => el !== entry);
        const at = others.findIndex((el) => {
          const box = el.getBoundingClientRect();
          return moved.clientY < box.top + box.height / 2;
        });
        this.#place(entry, at < 0 ? others.length : at);
      };
      const gesture = new AbortController();
      const finish = () => {
        gesture.abort();
        if (this.#entries.indexOf(entry) !== start) this.#commit(entry);
        release();
      };
      const { signal } = gesture;
      entry.addEventListener("pointermove", follow, { signal });
      entry.addEventListener("pointerup", finish, { signal });
      entry.addEventListener("pointercancel", finish, { signal });
    }
  },
);
