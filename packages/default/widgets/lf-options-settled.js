/* A settled options group's tab-local disclosure. The current option projection is
 * always read from the host; the row never becomes a second record of selection.
 * Options remain the host's direct children, the boundary its selection, replay and
 * page-authored layout selectors read. A native details wrapper would reparent them,
 * so this disclosure owns their hidden state without changing that boundary. */
import {
  DISCLOSE,
  comparisonChanges,
  keeps,
  generated,
  html,
  nothing,
  render,
  selectableOffer,
  tabStore,
  commandsChanged,
} from "/runtime/widget-api.js";

const SETTLED_KEY = "lf-settled:";

export class SettledOptions {
  #host;
  #label;
  #row = null;
  #isOpen = false;

  constructor(host, { label }) {
    this.#host = host;
    this.#label = label;
  }

  connect() {
    if (this.#row) return;
    this.#build();
  }

  #build() {
    this.#row = selectableOffer("button", "lf-settled lf-disclosure-marker");
    this.#row.setAttribute("aria-expanded", "false");
    this.#row.onclick = () => this.#open(!this.#isOpen, true);
    // This row only names the row's keys, in the group's words, as a diff's file row
    // does; it runs nothing. On a page the disclosure scope's `disclosure.toggle`
    // (keyboard/page.js) answers Enter, Space and the arrows; in a message, where that
    // scope does not reach, Enter and Space press the span as a button
    // (role-button-press.js).
    this.#row.lfCommands = {
      title: "In settled options",
      rows: [
        {
          id: "option.toggle-settled",
          keys: () => DISCLOSE(this.#row),
          title: () => (this.#isOpen ? "close" : "open"),
        },
      ],
    };
    commandsChanged(this.#row);
    this.#host.prepend(this.#row);
    this.#host.addEventListener("beforematch", () => this.#open(true, true), true);
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
    keeps(this.#row, "aria-controls", options.map((option) => option.id).join(" "));
    for (const el of [
      ...options,
      ...this.#host.querySelectorAll(":scope > :is(.lf-another, lf-options-done)"),
    ])
      keeps(el, "hidden", this.#isOpen ? null : "until-found");

    const names = options
      .filter((option) => option.hasAttribute("chosen"))
      .map(this.#label)
      .filter(Boolean);
    const changes = comparisonChanges(this.#host).length;
    // The row names only the outcome: its disclosure marker already says the
    // alternatives are inside. The user chose this on 2026-10-26 over a right-aligned
    // count of the options.
    render(
      html`<span ${generated({ says: true })}
          >${names.length ? `Settled: ${names.join(", ")}` : "Settled"}</span
        >${changes ? html`<span class="lf-settled-diff lf-chip lf-change-count">Δ${changes}</span>` : nothing}`,
      this.#row,
    );
  }
}
