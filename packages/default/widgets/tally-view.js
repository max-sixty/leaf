/* The count keeps its room while the server reading changes. */
import { html, nothing } from "/vendor/lit.js";
import { offeredAction } from "/runtime/lib/controls.js";

/**
 * @param {HTMLElement} host
 * @param {{ready?: boolean, done?: boolean, widest?: string, words?: string, onUser?: number | boolean}} [state]
 * @param {(() => void) | null} [onNext]
 */
export function render(
  host,
  {
    ready = false,
    done = false,
    widest = "00 left to answer · 00 on the agent",
    words = "",
    onUser = false,
  } = {},
  onNext = null,
) {
  return html`<span class="lf-tally-face" data-lf-gen="1" ?data-lf-ready=${ready}>
    <span class="lf-tally-count lf-chip" data-lf-tone=${done ? "ok" : nothing}>
      <span class="lf-tally-room" aria-hidden="true">${widest}</span>
      <span class="lf-tally-words">${words}</span>
    </span>
    ${
      host.hasAttribute("next")
        ? html`<button
            ${offeredAction("word", "lf-tally-next")}
            ?disabled=${!ready || !onUser}
            @mousedown=${(/** @type {MouseEvent} */ event) => event.preventDefault()}
            @click=${onNext}
          >
            Next On Me
          </button>`
        : nothing
    }
  </span>`;
}
