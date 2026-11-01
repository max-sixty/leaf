/* The count keeps its room while the server reading changes. */
import { html, nothing } from "/vendor/lit.js";
import { actionClass } from "/runtime/widget-api.js";

/**
 * @param {HTMLElement} host
 * @param {{ready?: boolean, done?: boolean, generic?: string, named?: string, words?: string, onUser?: number | boolean}} [state]
 * @param {(() => void) | null} [onNext]
 */
export function render(
  host,
  {
    ready = false,
    done = false,
    generic = "00 left to answer · 00 on the agent",
    named = generic,
    words = "",
    onUser = false,
  } = {},
  onNext = null,
) {
  return html`<span class="lf-tally-face" data-lf-gen="1" ?data-lf-ready=${ready}>
    <span class=${done ? "lf-tally-count lf-chip ok" : "lf-tally-count lf-chip"}>
      <span class="lf-tally-room" aria-hidden="true">${generic}</span>
      <span class="lf-tally-room" aria-hidden="true">${named}</span>
      <span class="lf-tally-words">${words}</span>
    </span>
    ${
      host.hasAttribute("next")
        ? html`<button
            class=${`${actionClass("word", "lf-tally-next")} lf-ui lf-ui-face`}
            data-lf-gen="1"
            data-lf-offer="button"
            type="button"
            title="Next on me here"
            aria-controls=${host.getAttribute("for")}
            ?disabled=${!ready || !onUser}
            @mousedown=${(/** @type {MouseEvent} */ event) => event.preventDefault()}
            @click=${onNext}
          >
            Next on me
          </button>`
        : nothing
    }
  </span>`;
}
