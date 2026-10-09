/* A settled options group's tab-local disclosure. The current option projection is
 * always read from the host; the row never becomes a second record of selection. */
import {
  DISCLOSE,
  HIDDEN,
  commands,
  keeps,
  keepsText,
  relabel,
  selectableOffer,
  tabStore,
} from "/runtime/widget-api.js";

const SETTLED_KEY = "lf-settled:";

export class SettledOptions {
  #host;
  #label;
  #row = null;
  #title = null;
  #count = null;
  #isOpen = false;
  #diffEvents = null;

  constructor(host, { label }) {
    this.#host = host;
    this.#label = label;
  }

  connect() {
    if (!this.#row) this.#build();
    if (!this.#diffEvents) {
      this.#diffEvents = new AbortController();
      document.addEventListener("lf-comparison", () => this.#delta(), {
        signal: this.#diffEvents.signal,
      });
    }
  }

  disconnect() {
    this.#diffEvents?.abort();
    this.#diffEvents = null;
  }

  #build() {
    this.#row = selectableOffer("button", "lf-settled");
    this.#title = document.createElement("span");
    this.#count = document.createElement("span");
    this.#count.className = "lf-settled-count";
    this.#row.append(this.#title, this.#count);
    this.#row.setAttribute("aria-expanded", "false");
    this.#row.onclick = () => this.#open(!this.#isOpen, true);
    commands(this.#row, "In a settled ask", [
      {
        id: "option.toggle-settled",
        keys: () => DISCLOSE(this.#row),
        title: () => (this.#isOpen ? "close" : "open"),
        run: () => this.#row.click(),
      },
    ]);
    this.#host.prepend(this.#row);
    this.#host.addEventListener("beforematch", () => this.#open(true, true), true);
    this.#host.addEventListener("lf-reveal", () => this.#open(true, true), true);
    this.#host.classList.toggle("lf-rendered", true);
    this.#open(tabStore.get(SETTLED_KEY + this.#host.id) === "1", false);
  }

  #open(open, remember) {
    this.#isOpen = open;
    this.sync();
    keeps(this.#row, "aria-expanded", open);
    if (remember) tabStore.set(SETTLED_KEY + this.#host.id, open ? "1" : "0");
  }

  sync() {
    const options = [...this.#host.querySelectorAll(":scope > lf-option")];
    keepsText(
      this.#count,
      `${options.length} option${options.length === 1 ? "" : "s"}`,
    );
    keeps(this.#row, "aria-controls", options.map((option) => option.id).join(" "));
    for (const el of [
      ...options,
      ...this.#host.querySelectorAll(":scope > :is(.lf-another, lf-options-done)"),
    ])
      keeps(el, "hidden", this.#isOpen ? null : HIDDEN);

    const names = options
      .filter((option) => option.hasAttribute("chosen"))
      .map(this.#label)
      .filter(Boolean);
    relabel(this.#title, names.length ? `Settled: ${names.join(", ")}` : "Settled", {
      says: true,
    });
  }

  #delta() {
    let chip = this.#row.querySelector(".lf-settled-diff");
    const n = this.#host.querySelectorAll(".lf-ins-block").length;
    if (!n) return chip?.remove();
    if (!chip) {
      chip = document.createElement("span");
      chip.className = "lf-settled-diff";
      this.#row.append(chip);
    }
    keepsText(chip, `Δ${n}`);
  }
}
