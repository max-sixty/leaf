/* The thread panel's complete narrowing surface.
 *
 * `narrowing.js` supplies one frozen presentation reading and stable commands. This
 * synchronous light-DOM Lit owner retains the native search input and local Filters
 * disclosure while rendering the summary, Reset, and declared facet controls. It
 * never reads its rendering back into reader intent.
 */
import { html, nothing, render, repeat } from "../../vendor/browser-runtime.js";

// `lf-*` is reserved for authored widgets. This is generated runtime chrome.
const TAG = "leaf-thread-narrowing";

class ThreadNarrowingView extends HTMLElement {
  #changeWords = null;
  #chooseFacet = null;
  #disclosed = false;
  #model = null;
  #reset = null;
  #searchInput = document.createElement("input");

  constructor() {
    super();
    this.#searchInput.type = "search";
    this.#searchInput.name = "thread-search";
    this.#searchInput.className = "lf-find-box";
    this.#searchInput.placeholder = "Find in threads";
    this.#searchInput.setAttribute("aria-label", "Find in threads");
    this.#searchInput.title = "Find in threads";
    this.#searchInput.addEventListener("input", () =>
      this.#changeWords?.(this.#searchInput.value),
    );
  }

  configure({ changeWords, chooseFacet, initial, reset }) {
    if (this.#changeWords)
      throw new Error("The thread narrowing view is already configured");
    this.#changeWords = changeWords;
    this.#chooseFacet = chooseFacet;
    this.#reset = reset;
    this.present(initial);
  }

  get readerControl() {
    return this.querySelector('[data-filter-kind="state"][data-filter-value="reader"]');
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
    const classes = ["lf-btn", "lf-thread-filter"];
    if (choice.className) classes.push(choice.className);
    if (choice.selected) classes.push("on");
    const keyTitle = choice.kind === "state" && choice.value === "reader";
    return html`<button
      type="button"
      class=${classes.join(" ")}
      data-filter-kind=${choice.kind}
      data-filter-value=${choice.value}
      data-lf-key-title=${keyTitle ? this.#model.readerTitle : nothing}
      aria-pressed=${String(choice.selected)}
      title=${keyTitle ? this.#model.readerTitle : nothing}
      ?hidden=${choice.hidden}
      .disabled=${choice.disabled}
      @click=${() => this.#chooseFacet(choice.kind, choice.value)}
    >
      ${choice.label}${choice.amount ? ` (${choice.amount})` : nothing}
    </button>`;
  }

  #group(group) {
    return html`<div
      class="lf-thread-filter-group"
      role="group"
      aria-label=${group.label}
    >
      ${repeat(
        group.choices,
        (choice) => `${choice.kind}:${choice.value}`,
        (choice) => this.#choice(choice),
      )}
    </div>`;
  }

  #template() {
    if (!this.#model) return nothing;
    const [state, ...facets] = this.#model.groups;
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
        ${this.#group(state)}
        <div class="lf-thread-filter-facets">
          ${repeat(
            facets,
            (group) => group.kind,
            (group) => this.#group(group),
          )}
        </div>
      </div>
    `;
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, ThreadNarrowingView);

export const createThreadNarrowingView = () => document.createElement(TAG);
