/* One browser transport draws tab-local playback state.
 * Authored media and illustrations remain native light-DOM siblings of the transport. */
import { html, live, nothing } from "/vendor/lit.js";
import { offered, offeredAction } from "/runtime/portable-api.js";

/** @param {HTMLElement} host
 * @param {{time: number, rate: number, label: string, playing: boolean, playable: boolean, failure: string | null}} state */
export function render(host, { time, rate, label, playing, playable, failure }) {
  return html`
    <div
      ${offered("lf-motion-controls")}
      role="group"
      aria-label=${host.getAttribute("aria-label")}
    >
      <button
        ${offeredAction("symbol", "lf-motion-play", label, { action: playing ? "pause" : "play" })}
        aria-disabled=${playable ? nothing : "true"}
      ></button>
      <input
        ${offered("lf-motion-time")}
        type="range"
        name="time"
        min="0"
        max=${host.getAttribute("duration")}
        step="1"
        aria-label="Time"
        aria-valuetext=${`${Math.round(time)} milliseconds`}
        .value=${live(String(time))}
      />
      <span ${offered("lf-motion-clock")}>${failure ?? `${Math.round(time)} ms`}</span>
      <label ${offered("lf-motion-speed")}
        >Speed<select ${offered("")} name="speed">
          ${[1, 0.5, 0.25].map(
            (value) =>
              html`<option value=${value} .selected=${live(rate === value)}>
                ${value}×
              </option>`,
          )}
        </select></label
      >
    </div>
  `;
}
