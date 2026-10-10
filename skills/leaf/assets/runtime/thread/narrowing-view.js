/* The thread panel's complete narrowing surface.
 *
 * `narrowing.js` supplies one frozen presentation reading and stable commands. This
 * synchronous light-DOM Lit owner retains the search control and local View
 * disclosure while rendering the order, declared facet controls, summary, and Reset. The
 * summary follows the choices so that a change to it never moves a choice under the press
 * that caused it, and the disclosure's label never changes with what is chosen. The
 * summary stands in every view, the default's included, and Reset keeps its box where it
 * has nothing to put back, so the first letter typed into the find box or the first
 * choice pressed never inserts a row that pushes the list down under the user. It never
 * reads its rendering back into user intent.
 */
import { scrollIntoView } from "../landing-scroll.js";
import {
  html,
  noChange,
  nothing,
  render,
  repeat,
} from "../../vendor/browser-runtime.js";
import { searchField, reserve } from "../widget-elements.js";
import { focusDestination } from "../focus.js";

// `lf-*` is reserved for authored widgets. This is generated runtime chrome.
const TAG = "leaf-thread-narrowing";

class ThreadNarrowingView extends HTMLElement {
  #changeWords = null;
  #chooseFacet = null;
  #disclosed = false;
  #model = null;
  #countDigits = 2;
  #reservedCounts = new WeakMap();
  #reset = null;
  #toggleUser = null;
  #searchInput = searchField("lf-find-box", {
    name: "thread-search",
    label: "Find in threads",
  });

  constructor() {
    super();
    this.#searchInput.title = "Find in threads";
    this.#searchInput.addEventListener("input", () =>
      this.#changeWords?.(this.#searchInput.value),
    );
  }

  configure({ changeWords, chooseFacet, initial, reset, toggleUser }) {
    if (this.#changeWords)
      throw new Error("The thread narrowing view is already configured");
    this.#changeWords = changeWords;
    this.#chooseFacet = chooseFacet;
    this.#reset = reset;
    this.#toggleUser = toggleUser;
    this.present(initial);
  }

  get userControl() {
    return this.querySelector('[data-filter-kind="waiting"][data-filter-value="user"]');
  }

  toggleUser() {
    this.#toggleUser();
  }

  get canToggleUser() {
    return this.#model?.userAvailable ?? false;
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
    this.#reserveCounts();
  }

  // Each counted choice reserves the width of the widest count it could show, so a
  // count changing with the view, a refusal's return included, moves no choice after
  // it. Its words keep the leading edge (chrome.css). The room only grows, from two
  // digits, so threads arriving or leaving move the choices at most once per digit.
  #reserveCounts() {
    this.#countDigits = Math.max(this.#countDigits, this.#model.countDigits);
    const room = "0".repeat(this.#countDigits);
    for (const group of this.#model.groups)
      for (const choice of group.choices) {
        if (choice.amount === null) continue;
        const button = this.querySelector(
          `[data-filter-kind="${choice.kind}"][data-filter-value="${choice.value}"]`,
        );
        const widest = `${choice.label} (${room})`;
        if (this.#reservedCounts.get(button) === widest) continue;
        this.#reservedCounts.set(button, widest);
        reserve(button, [widest]);
      }
  }

  #toggleFilters() {
    this.#disclosed = !this.#disclosed;
    render(this.#template(), this);
  }

  #resetFilters(event) {
    // Reset retires its own control; keep the user at the surviving disclosure.
    const toggle =
      document.activeElement === event.currentTarget &&
      this.querySelector(".lf-thread-filter-toggle");
    if (toggle) {
      focusDestination(toggle, "return");
      scrollIntoView(toggle, { block: "nearest" });
    }
    this.#reset();
  }

  #choice(choice) {
    const keyTitle = choice.kind === "waiting" && choice.value === "user";
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
      data-lf-key-title=${keyTitle ? this.#model.userTitle : nothing}
      title=${keyTitle ? this.#model.userTitle : nothing}
      ?hidden=${choice.hidden}
      ?disabled=${keyTitle ? noChange : choice.disabled}
      @click=${keyTitle ? nothing : () => this.#chooseFacet(choice.kind, choice.kind === "gone" ? !choice.selected : choice.value)}
    >
      ${choice.amount === null ? choice.label : `${choice.label} (${choice.amount})`}
    </button>`;
  }

  #group(group) {
    return html`<div
      class="lf-thread-filter-group"
      role="group"
      aria-label=${group.label}
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
          View
        </button>
      </div>
      <div
        class="lf-thread-filters"
        id="lf-thread-filters"
        aria-label="Thread view"
        ?hidden=${!this.#disclosed}
      >
        ${repeat(
          this.#model.groups,
          (group) => group.kind,
          (group) => this.#group(group),
        )}
      </div>
      <div class="lf-thread-view">
        <span class="lf-thread-view-summary">${this.#model.summary}</span>
        <button
          type="button"
          class="lf-btn lf-thread-filter-reset"
          aria-label="Reset thread filters"
          ?data-lf-unoffered=${!this.#model.resettable}
          @click=${(event) => this.#resetFilters(event)}
        >
          Reset
        </button>
      </div>
    `;
  }
}

if (!customElements.get(TAG)) customElements.define(TAG, ThreadNarrowingView);

export const createThreadNarrowingView = () => document.createElement(TAG);
