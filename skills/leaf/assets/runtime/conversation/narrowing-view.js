/* The thread panel's complete narrowing surface.
 *
 * `narrowing.js` supplies one frozen presentation reading and stable commands. This
 * synchronous light-DOM Lit owner retains the search control and local Filters
 * disclosure while rendering the summary, Reset, and declared facet controls. It
 * never reads its rendering back into reader intent.
 */
import { html, nothing, render, repeat } from "../../vendor/browser-runtime.js";
import { offer } from "../widget-elements.js";

// `lf-*` is reserved for authored widgets. This is generated runtime chrome.
const TAG = "leaf-thread-narrowing";

class ThreadNarrowingView extends HTMLElement {
  #changeWords = null;
  #chooseFacet = null;
  #disclosed = false;
  #model = null;
  #reset = null;
  #toggleReader = null;
  #searchInput = offer("wa-input", "lf-find-box lf-label-hidden");

  constructor() {
    super();
    this.#searchInput.type = "search";
    this.#searchInput.size = "s";
    this.#searchInput.name = "thread-search";
    this.#searchInput.placeholder = "Find in threads";
    this.#searchInput.label = "Find in threads";
    this.#searchInput.title = "Find in threads";
    this.#searchInput.addEventListener("input", () =>
      this.#changeWords?.(this.#searchInput.value),
    );
  }

  configure({ changeWords, chooseFacet, initial, reset, toggleReader }) {
    if (this.#changeWords)
      throw new Error("The thread narrowing view is already configured");
    this.#changeWords = changeWords;
    this.#chooseFacet = chooseFacet;
    this.#reset = reset;
    this.#toggleReader = toggleReader;
    this.present(initial);
  }

  get readerControl() {
    return this.querySelector(
      '[data-filter-kind="waiting"][data-filter-value="reader"]',
    );
  }

  toggleReader() {
    this.#toggleReader();
  }

  get canToggleReader() {
    return this.#model?.readerAvailable ?? false;
  }

  get searchInput() {
    return this.#searchInput;
  }

  setSearchWords(words) {
    if (this.#searchInput.value !== words) this.#searchInput.value = words;
  }

  present(model) {
    if (!Object.isFrozen(model))
      throw new Error("Thread narrowing presentation models must be immutable");
    this.#model = model;
    render(this.#template(), this);
  }

  #toggleFilters() {
    this.#disclosed = !this.#disclosed;
    render(this.#template(), this);
  }

  #resetFilters(event) {
    // Reset retires its own control; keep the reader at the surviving disclosure.
    if (document.activeElement === event.currentTarget)
      this.querySelector(".lf-thread-filter-toggle")?.focus();
    this.#reset();
  }

  #choice(choice) {
    const keyTitle = choice.kind === "waiting" && choice.value === "reader";
    const classes = [
      "lf-btn",
      "lf-thread-filter",
      choice.className,
      choice.selected ? "on" : "",
    ]
      .filter(Boolean)
      .join(" ");
    return html`<button
      type="button"
      data-lf-gen="1"
      class=${classes}
      data-filter-kind=${choice.kind}
      data-filter-value=${choice.value}
      aria-pressed=${String(choice.selected)}
      data-lf-key-title=${keyTitle ? this.#model.readerTitle : nothing}
      title=${keyTitle ? this.#model.readerTitle : nothing}
      ?hidden=${choice.hidden}
      ?disabled=${choice.disabled}
      @click=${() => this.#chooseFacet(choice.kind, choice.kind === "gone" ? !choice.selected : choice.value)}
    >
      ${choice.label} (${choice.amount})
    </button>`;
  }

  #group(group) {
    return html`<div
      class="lf-thread-filter-group"
      role="group"
      aria-label=${group.label}
      ?hidden=${group.hidden}
    >
      <span class="lf-thread-filter-label" aria-hidden="true">${group.label}</span>
      <div class="lf-thread-filter-choices">
        ${repeat(
          group.choices,
          (choice) => choice.value,
          (choice) => this.#choice(choice),
        )}
      </div>
    </div>`;
  }

  #template() {
    if (!this.#model) return nothing;
    return html`
      <div class="lf-find">
        ${this.#searchInput}
        <button
          type="button"
          class="lf-btn lf-thread-filter-toggle"
          aria-expanded=${String(this.#disclosed)}
          aria-controls="lf-thread-filters"
          @click=${() => this.#toggleFilters()}
        >
          Filters
        </button>
      </div>
      <div class="lf-thread-view" ?hidden=${this.#model.hidden}>
        <span class="lf-thread-view-summary">${this.#model.summary}</span>
        <button
          type="button"
          class="lf-btn lf-thread-filter-reset"
          aria-label="Reset thread filters"
          @click=${(event) => this.#resetFilters(event)}
        >
          Reset
        </button>
      </div>
      <div
        class="lf-thread-filters"
        id="lf-thread-filters"
        aria-label="Filter threads"
        ?hidden=${!this.#disclosed}
      >
        ${repeat(
          this.#model.groups,
          (group) => group.kind,
          (group) => this.#group(group),
        )}
      </div>
    `;
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, ThreadNarrowingView);

export const createThreadNarrowingView = () => document.createElement(TAG);
