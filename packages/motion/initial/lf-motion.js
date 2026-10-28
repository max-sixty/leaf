/* The same synchronous Lit drawing owns the transport before first paint and while
 * playing. The authored body keeps its native nodes, media clocks and page styling. */
import { html, live, ref } from "/vendor/lit.js";
import { actionOffers, showAction } from "../../../browser/runtime/icon-paths.js";

document.documentElement.lfInitial.register("lf-motion", (host, tools) => {
  const { offerElement, tabStore, authoredBody } = tools;
  const { offerActionElement } = actionOffers(tools);
  const saved = JSON.parse(tabStore.get(`motion:${host.id}`) || '{"time":0,"rate":1}');
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
  // The press is a symbol whose action follows the clock, Play's or Pause's, and
  // which says the clock's words as its name.
  const playRef = (node) => {
    if (node)
      drawing.play = offerActionElement(node, "symbol", "lf-motion-play", undefined, {
        action: "play",
      });
  };
  const timeRef = offered("time", "lf-motion-time");
  const clockRef = offered("clock", "lf-motion-clock");
  const speedLabelRef = offered("speedLabel", "lf-motion-speed");
  const speedRef = offered("speed", "");
  const template = ({
    time = Math.min(Number(host.getAttribute("duration")), saved.time),
    rate = saved.rate,
    label = "Play",
    playing = false,
  } = {}) => html`
    <div ${ref(controlsRef)} role="group" aria-label=${host.getAttribute("aria-label")}>
      <button
        ${ref(playRef)}
        ${ref((node) => node && showAction(node, playing ? "pause" : "play"))}
        aria-label=${label}
        title=${label}
      ></button>
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
  `;
  return Object.assign(drawing, { render: template });
});
