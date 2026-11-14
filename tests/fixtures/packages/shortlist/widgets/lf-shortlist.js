// <lf-shortlist>: candidates the user picks from, each pick its own recorded action.
//
// Every change comes in one way, a `--toggle` command whose button's value names a
// candidate: the authored buttons here send it, and so may any other widget. On a Leaf
// page the pick is recorded through the widget's controller, so Undo takes one pick
// back; on a page without Leaf the element keeps the picks itself. Either way it holds
// the list and its picks as its `shortlist` output and says `change`, which is all
// another widget reads.

import { LeafElement, keeps, nothing } from "/runtime/portable-api.js";

customElements.define(
  "lf-shortlist",
  class extends LeafElement {
    static properties = { kept: { state: true } };

    setup() {
      this.kept = new Set();
      this.buttons = [...this.querySelectorAll("button[value]")];
      this.addEventListener("command", (event) => {
        if (event.command === "--toggle") this.toggle(event.source?.value);
      });
    }

    // Leaf hands a recorded widget its reading; a plain host hands it none.
    picked(key) {
      return this.reading
        ? Boolean(this.state.pick.units[key]?.detail.picked)
        : this.kept.has(key);
    }

    toggle(key) {
      const button = this.buttons.find((candidate) => candidate.value === key);
      if (!button) return;
      const picked = !this.picked(key);
      if (this.reading)
        this.controller.dispatch({
          kind: "action",
          verb: "pick",
          detail: { candidate: key, picked },
          says: `${picked ? "Picked" : "Dropped"} ${button.textContent.trim()}`,
        });
      else {
        const kept = new Set(this.kept);
        if (picked) kept.add(key);
        else kept.delete(key);
        this.kept = kept;
      }
    }

    render() {
      this.candidates = this.buttons.map((button) => ({
        key: button.value,
        name: button.textContent.trim(),
        picked: this.picked(button.value),
      }));
      return nothing;
    }

    updated(changed) {
      super.updated(changed);
      for (const [index, button] of this.buttons.entries())
        keeps(button, "aria-pressed", String(this.candidates[index].picked));
      this.shortlist = { candidates: this.candidates };
      this.dispatchEvent(new Event("change"));
    }
  },
);
