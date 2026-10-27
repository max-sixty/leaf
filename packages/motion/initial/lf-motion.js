/* The same synchronous Lit drawing owns the transport before first paint and while
 * playing. The authored body keeps its native nodes, media clocks and page styling. */
import { html, live, ref, render, unsafeSVG } from "/vendor/lit.js";
import { ICONS } from "../../../browser/runtime/icon-paths.js";

document.documentElement.lfInitial.register(
  "lf-motion",
  (host, { offerElement, tabStore, authoredBody }) => {
    const saved = JSON.parse(
      tabStore.get(`motion:${host.id}`) || '{"time":0,"rate":1}',
    );
    // The coordinator moves and records authored nodes before Lit mounts apparatus.
    // This wrapper is authored content, so it must not receive offer markers.
    const body = document.createElement("div");
    body.className = "lf-motion-body";
    authoredBody(body);
    const drawing = {};
    const offered = (key, cls) => (node) => {
      if (node) drawing[key] = offerElement(node, cls);
    };
    const controlsRef = offered("controls", "lf-motion-controls");
    const playRef = offered("play", "lf-btn lf-motion-play");
    const timeRef = offered("time", "lf-motion-time");
    const clockRef = offered("clock", "lf-motion-clock");
    const speedLabelRef = offered("speedLabel", "lf-motion-speed");
    const speedRef = offered("speed", "");
    const paint = ({ time, rate, label, playing }) => {
      render(
        html`
          <div
            ${ref(controlsRef)}
            role="group"
            aria-label=${host.getAttribute("aria-label")}
          >
            <button ${ref(playRef)} aria-label=${label} title=${label}>
              <svg viewBox="0 0 16 16" aria-hidden="true" focusable="false">
                ${unsafeSVG(playing ? ICONS.pause : ICONS.play)}
              </svg>
            </button>
            <input
              ${ref(timeRef)}
              type="range"
              name="time"
              min="0"
              max=${host.getAttribute("duration")}
              step="1"
              aria-label="Time"
              aria-valuetext=${`${Math.round(time)} milliseconds`}
              .value=${live(String(time))}
            />
            <span ${ref(clockRef)}>${Math.round(time)} ms</span>
            <label ${ref(speedLabelRef)}
              >Speed<select ${ref(speedRef)} name="speed">
                ${[1, 0.5, 0.25].map(
                  (value) =>
                    html`<option value=${value} .selected=${live(rate === value)}>
                      ${value}×
                    </option>`,
                )}
              </select></label
            >
          </div>
          ${body}
        `,
        host,
      );
    };
    paint({
      time: Math.min(Number(host.getAttribute("duration")), saved.time),
      rate: saved.rate,
      label: "Play",
      playing: false,
    });
    return Object.assign(drawing, { paint });
  },
);
