/* One browser transport draws tab-local playback state.
 * Authored media and illustrations remain native light-DOM nodes in the body slot. */
import { html, live } from "/vendor/lit.js";
import { actionClass, actionTemplate } from "/runtime/widget-api.js";

export function render(host, { time, rate, label, playing }) {
  return html`
    <div
      class="lf-motion-controls lf-ui lf-ui-face"
      data-lf-gen="1"
      data-lf-offer=""
      role="group"
      aria-label=${host.getAttribute("aria-label")}
    >
      <button
        class=${`${actionClass("symbol", "lf-motion-play")} lf-ui lf-ui-face`}
        data-lf-gen="1"
        data-lf-offer="button"
        type="button"
        aria-label=${label}
        title=${label}
      >
        ${actionTemplate(playing ? "pause" : "play")}
      </button>
      <input
        class="lf-motion-time lf-ui lf-ui-face"
        data-lf-gen="1"
        data-lf-offer=""
        type="range"
        name="time"
        min="0"
        max=${host.getAttribute("duration")}
        step="1"
        aria-label="Time"
        aria-valuetext=${`${Math.round(time)} milliseconds`}
        .value=${live(String(time))}
      />
      <span class="lf-motion-clock lf-ui lf-ui-face" data-lf-gen="1" data-lf-offer=""
        >${Math.round(time)} ms</span
      >
      <label class="lf-motion-speed lf-ui lf-ui-face" data-lf-gen="1" data-lf-offer=""
        >Speed<select
          class="lf-ui lf-ui-face"
          data-lf-gen="1"
          data-lf-offer=""
          name="speed"
        >
          ${[1, 0.5, 0.25].map(
            (value) =>
              html`<option value=${value} .selected=${live(rate === value)}>
                ${value}×
              </option>`,
          )}
        </select></label
      >
    </div>
    <div class="lf-motion-body"><slot></slot></div>
  `;
}
