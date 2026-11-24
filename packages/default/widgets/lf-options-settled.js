/* A settled options group's tab-local disclosure. The current option projection is
 * always read from the host; the row never becomes a second record of selection.
 * Options remain the host's direct children, the boundary its selection, replay and
 * page-authored layout selectors read. A native details wrapper would reparent them,
 * so this disclosure owns their hidden state without changing that boundary. */
import { html, nothing, render } from "/vendor/lit.js";
import { comparisonChanges, tabStore } from "/runtime/widget-api.js";
import { selectableOffer } from "/runtime/lib/controls.js";
import { keeps } from "/runtime/lib/keeps.js";

const SETTLED_KEY = "lf-settled:";

export class SettledOptions {
  #host;
  #label;
  #row = selectableOffer(
    "button",
    "lf-settled lf-disclosure-marker",
    undefined,
    "fold",
  );
  #isOpen = false;

  /** @param {HTMLElement} host @param {{label: (option: Element) => string}} options */
  constructor(host, { label }) {
    this.#host = host;
    this.#label = label;
  }

  connect() {
    if (this.#row.parentElement === this.#host) return;
    this.#build();
  }

  #build() {
    this.#row.setAttribute("aria-expanded", "false");
    // The row wears a button's role and `aria-expanded`, so Leaf answers its keys as it
    // does every disclosure's (module-input.md, "How scopes compose").
    this.#row.onclick = () => this.#open(!this.#isOpen, true);
    this.#host.prepend(this.#row);
    this.#host.addEventListener("beforematch", () => this.#open(true, true), true);
    this.#host.classList.toggle("lf-rendered", true);
    this.#open(tabStore.get(SETTLED_KEY + this.#host.id) === "1", false);
  }

  /** @param {boolean} open @param {boolean} remember */
  #open(open, remember) {
    this.#isOpen = open;
    this.sync();
    keeps(this.#row, "aria-expanded", open);
    if (remember) tabStore.set(SETTLED_KEY + this.#host.id, open ? "1" : "0");
  }

  sync() {
    const options = [...this.#host.querySelectorAll(":scope > lf-option")];
    keeps(this.#row, "aria-controls", options.map((option) => option.id).join(" "));
    for (const el of [
      ...options,
      ...this.#host.querySelectorAll(":scope > :is(.lf-another, lf-options-done)"),
    ])
      keeps(el, "hidden", this.#isOpen ? null : "until-found");

    const names = options
      .filter((option) => option.hasAttribute("selected"))
      .map(this.#label)
      .filter(Boolean);
    const changes = comparisonChanges(this.#host).length;
    // The row names only the outcome: its disclosure marker already says the
    // alternatives are inside. The user chose this over a right-aligned
    // count of the options.
    render(
      html`<span data-lf-gen="1" data-lf-said
          >${names.length ? `Settled: ${names.join(", ")}` : "Settled"}</span
        >${changes ? html`<span class="lf-settled-diff lf-chip lf-change-count">Δ${changes}</span>` : nothing}`,
      this.#row,
    );
  }
}
