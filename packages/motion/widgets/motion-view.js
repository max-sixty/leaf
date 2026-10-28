/* lf-motion's transport, one synchronous Lit drawing from before first paint through
 * playing. The initial renderer (`../initial/lf-motion.js`) bundles this module and
 * draws before first paint; the widget module (`lf-motion.js` beside this file) adopts
 * the drawing, and on a page without Leaf, where nothing drew first, draws with it
 * (`initialRender`). The authored body keeps its native nodes, media clocks and page
 * styling. */
import {
  actionOffers,
  html,
  live,
  nothing,
  ref,
  showAction,
} from "/runtime/portable-api.js";

export function drawMotion(host, tools) {
  const { offerElement, tabStore, authoredBody } = tools;
  const { offerActionElement } = actionOffers(tools);
  const saved = JSON.parse(tabStore.get(`motion:${host.id}`) || '{"time":0,"rate":1}');
  // Whether Play has anything to play before the page script assigns a renderer: a
  // video of the study's own, read before the body box below takes the authored nodes.
  const videos = [...host.querySelectorAll("video")].some(
    (video) => video.closest("lf-motion") === host,
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
    // Whether Play has anything to play: an illustration's renderer or a video.
    playable = videos,
    // A word that stands in the clock's place after a press failed, until the next,
    // short enough for the clock's box.
    failure = null,
  } = {}) => html`
    <div ${ref(controlsRef)} role="group" aria-label=${host.getAttribute("aria-label")}>
      <button
        ${ref(playRef)}
        ${ref((node) => node && showAction(node, playing ? "pause" : "play"))}
        aria-label=${label}
        title=${label}
        aria-disabled=${playable ? nothing : "true"}
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
      <span ${ref(clockRef)}>${failure ?? `${Math.round(time)} ms`}</span>
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
}
