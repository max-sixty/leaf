/* A recording on the page plays through Leaf's own quiet controls: a play and pause
   button, a timeline and a full-screen button, in one bar over the recording's foot.

   The page writes `<video controls>`, and that stays its readable form: a page with no
   runtime, or one that failed to start, keeps the browser's controls. Once the runtime
   runs, each video standing in the document or a widget's first shadow stage
   (arrivals.js), where the bar can anchor to it, trades `controls` for `data-lf-player`
   while it stands, and gets the attribute back when it leaves. Startup makes the
   trade before revealing the rendered page, so the browser's controls never draw
   there to give way to the bar. The browsers' own
   controls each start a recording differently, and Firefox's grow the first play's
   button to three times its size while fading it out over 400 ms, which a replay never
   shows, so the same recording looked different on its first play and in each engine.
   The bar is the same in every engine and on every play. The video's box is the page's:
   the bar takes no room and the poster stays until the browser has a frame to show.

   The bar stands in chrome over the video (block-controls.js), shown while the
   recording is paused, under the pointer or under the keyboard, and out of the way
   while it plays. The video is the recording's one tab stop. Standing on it, Space plays or
   pauses and the arrows step five seconds back or forward, as the browsers' own
   controls answer those keys, through one scope the register projects, so the hints,
   the command reference and `aria-keyshortcuts` name them. `k` stays the page's scroll
   (keyboard/AGENTS.md, "Page grammar"). A press on the picture plays or pauses, as
   Firefox's controls do, and that tap is a finger's way in; the bar's button and
   timeline take a pointer or a finger and sit outside the Tab sequence, like Copy's.
   The timeline is a native range: its arrows step it once it holds focus, and it says
   where the recording stands in minutes and seconds.

   Full screen shows a screen capture's interface text at a readable size, which a
   column about 680px wide halves. The button and `f`, standing on the video, put the
   video itself in full screen, where nothing outside it draws, the bar included. So for
   as long as it fills the screen the video has the browser's own controls back, and
   with them the browser's keys and presses on the picture: the bar's scope and the
   picture's press stand down so each press acts once. Leaving full screen, by Escape or
   the browser's own button, returns the bar. A video whose document may not go full
   screen, such as one in a frame without `allow="fullscreen"`, gets no button and no
   key, unless the video has the platform's own player instead: Safari on an iPhone
   (`webkitEnterFullscreen`), whose player brings its own controls.

   Rejected: a volume button, since a page's recordings are silent evidence clips, and
   the browser's menu on the video still offers its own controls. A widget tag for
   recordings, since every page already writes a plain `<video>`. */
import { watchArrivals } from "./arrivals.js";
import {
  aimControl,
  anchorControl,
  readInsets,
  releaseControl,
  revealControl,
  standInChrome,
  tabFromBlock,
  writeInsets,
} from "./block-controls.js";
import { headerLevels, nameable } from "./css-anchors.js";
import { focusDestination, focused } from "./focus.js";
import { actionTemplate } from "./icons.js";
import { keeps } from "./keeps.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";
import { plainPress } from "./pointer.js";
import { commandScope, projectCommandScope } from "./keyboard/scopes.js";
import { offer, offered } from "./widget-elements.js";
import { html, live, nothing, render } from "/runtime/framework.js";

const PLAYER = PAGE_PAINT_ATTRIBUTE.player;
// The key this module projects its scope under, beside the video's other owners.
const SCOPE = Symbol("recording");
const STEP_SECONDS = 5;
const players = new Map(); // video → player, while it stands

const clock = (seconds) => {
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
};
const duration = (video) => (Number.isFinite(video.duration) ? video.duration : 0);

// How `video` fills the screen here, or null where its document may not.
const fillScreen = (video) => {
  if (video.ownerDocument.fullscreenEnabled) return () => video.requestFullscreen();
  if (video.webkitEnterFullscreen) return () => video.webkitEnterFullscreen();
  return null;
};
const fills = (video) => video.getRootNode().fullscreenElement === video;

function toggle(video) {
  if (!video.paused) return video.pause();
  // A pause asked for before playback starts ends that start; nothing else may.
  video.play().catch((error) => {
    if (error.name !== "AbortError") throw error;
  });
}

// Native media events own the clock; synchronous Lit rendering reads it directly
// and retains the controls, including the range the reader may be scrubbing.
export function paintRecordingControls(video, bar, enterFullScreen) {
  keeps(bar, "data-playing", video.paused ? null : "");
  keeps(bar, "role", "group");
  keeps(bar, "aria-label", video.getAttribute("aria-label") || "Recording");
  render(
    html`<button
        ${offered("lf-video-play")}
        tabindex="-1"
        aria-label=${!video.paused ? "Pause recording" : "Play recording"}
      >
        ${actionTemplate("play", "lf-video-icon")}${actionTemplate(
          "pause",
          "lf-video-icon",
        )}
      </button>
      <input
        ${offered("lf-video-time")}
        type="range"
        tabindex="-1"
        min="0"
        step="any"
        max=${String(duration(video))}
        ?disabled=${!duration(video)}
        .value=${live(String(video.currentTime))}
        aria-label="Recording position"
        aria-valuetext=${`${clock(video.currentTime)} of ${clock(duration(video))}`}
        @input=${(event) => {
          video.currentTime = Number(event.currentTarget.value);
        }}
      />
      ${
        enterFullScreen
          ? html`<button
              ${offered("lf-video-full-screen")}
              tabindex="-1"
              aria-label="Full screen"
            >
              ${actionTemplate("expand", "lf-video-icon")}
            </button>`
          : nothing
      }`,
    bar,
  );
}

// A player for `video`, its bar built and its listeners wired; `trade` writes it into
// the page.
function prepare(video) {
  const bar = offer("div", "lf-video-controls");
  const enterFullScreen = fillScreen(video);
  const paint = () => paintRecordingControls(video, bar, enterFullScreen);
  paint();
  const play = bar.querySelector(".lf-video-play");
  const fullScreen = bar.querySelector(".lf-video-full-screen");
  const player = {
    video,
    bar,
    play,
    authoredTabindex: video.getAttribute("tabindex"),
    filling: false,
    events: new AbortController(),
    /** @type {ReturnType<typeof commandScope> | null} */
    scope: null,
    paint,
  };
  const { signal } = player.events;
  const on = (target, type, listener) =>
    target.addEventListener(type, listener, { signal });

  for (const type of ["play", "pause", "ended", "loadedmetadata", "durationchange"])
    on(video, type, paint);
  on(video, "seeked", paint);
  on(video, "timeupdate", paint);
  // The timeline follows each frame the browser presents rather than the few times a
  // second `timeupdate` fires, so its thumb glides instead of stepping.
  // One request stands at a time, however quickly playback stops and starts again.
  let frame = 0;
  const followFrames = () => {
    paint();
    frame =
      video.paused || signal.aborted
        ? 0
        : video.requestVideoFrameCallback(followFrames);
  };
  on(video, "playing", () => {
    if (frame) video.cancelVideoFrameCallback(frame);
    frame = video.requestVideoFrameCallback(followFrames);
  });
  on(video, "click", (event) => {
    if (plainPress(event) && !player.filling) toggle(video);
  });

  // The bar shows for a pointer over the recording, and for the current keyboard location on
  // it: focus a key brought, or a command a key ran there. A press that focused the
  // picture leaves a playing recording whole.
  const show = (flag, force) => {
    if (force) revealControl(bar, video);
    keeps(bar, `data-${flag}`, force ? "" : null);
  };
  on(video, "pointerenter", () => show("hovered", true));
  on(video, "pointerleave", () => show("hovered", false));
  on(video, "focus", () => show("keyed", video.matches(":focus-visible")));
  on(video, "blur", () => show("keyed", false));
  tabFromBlock(bar, video, signal);
  player.scope = commandScope("On a recording", [
    {
      id: "recording.play",
      keys: [" "],
      title: () => (video.paused ? "play recording" : "pause recording"),
      // The register runs the command when its control is pressed.
      control: play,
      run: () => {
        // Its control runs it too, and a pointer's press there leaves the bar to hide.
        if (focused() === video) show("keyed", true);
        toggle(video);
      },
    },
    {
      id: "recording.step",
      keys: ["ArrowLeft", "ArrowRight"],
      routes: [
        {
          id: "recording.back",
          binding: "ArrowLeft",
          title: `back ${STEP_SECONDS} seconds`,
        },
        {
          id: "recording.forward",
          binding: "ArrowRight",
          title: `forward ${STEP_SECONDS} seconds`,
        },
      ],
      title: `back / forward ${STEP_SECONDS} seconds`,
      repeat: true,
      run: (binding) => {
        show("keyed", true);
        const step = binding === "ArrowLeft" ? -STEP_SECONDS : STEP_SECONDS;
        video.currentTime = Math.min(
          duration(video),
          Math.max(0, video.currentTime + step),
        );
      },
    },
    ...(fullScreen
      ? [
          {
            id: "recording.full-screen",
            keys: ["f"],
            title: "full screen",
            control: fullScreen,
            // The browser's keys reach the video where focus is on it.
            run: () => {
              focusDestination(video, "move");
              enterFullScreen();
            },
          },
        ]
      : []),
  ]);
  // Full screen shows the video alone, so the browser's controls stand in for the bar
  // until it leaves (header).
  on(video.ownerDocument, "fullscreenchange", () => {
    if (fills(video) === player.filling) return;
    player.filling = !player.filling;
    keeps(video, "controls", player.filling ? "" : null);
    projectCommandScope(video, SCOPE, player.filling ? null : player.scope);
    show("hovered", false);
  });
  players.set(video, player);
  return player;
}

function trade(player) {
  const { video, scope } = player;
  projectCommandScope(video, SCOPE, scope);
  keeps(video, PLAYER, "");
  keeps(video, "controls", null);
  if (player.authoredTabindex === null) keeps(video, "tabindex", "0");
  player.paint();
}

function giveBack(video) {
  const player = players.get(video);
  if (!player) return;
  players.delete(video);
  player.events.abort();
  releaseControl(player.bar);
  projectCommandScope(video, SCOPE, null);
  keeps(video, "tabindex", player.authoredTabindex);
  keeps(video, "controls", "");
  keeps(video, PLAYER, null);
}

export function watchVideos() {
  // A page whose runtime cannot start falls back to its readable form, which takes
  // `data-lf-interactive` off the root (prepaint.js). The bars give the browser its
  // controls back, and no later arrival takes one.
  const root = document.documentElement;
  const fallenBack = () => !root.hasAttribute("data-lf-interactive");
  new MutationObserver(() => {
    if (fallenBack()) for (const video of [...players.keys()]) giveBack(video);
  }).observe(root, { attributes: true, attributeFilter: ["data-lf-interactive"] });
  watchArrivals(`video[controls], video[${PLAYER}]`, [], {
    arriveBatch(videos) {
      if (fallenBack()) return;
      // Read every video before any video is written, bar connected or anchor named.
      // A bar in chrome anchors only to a video the document can name: one in the
      // document or the first shadow stage in (css-anchors.js). A video staged deeper
      // keeps the browser's controls.
      const read = videos.filter(nameable).map((video) => {
        const player = players.get(video) ?? prepare(video);
        return {
          player,
          reading: anchorControl(player.bar, video),
          levels: headerLevels(video),
          insets: readInsets(video),
        };
      });
      for (const { player, reading, levels, insets } of read) {
        aimControl(reading);
        writeInsets(player.bar, insets);
        standInChrome(player.bar, player.video, levels);
        // After the bar connects: the register reads a disconnected control as
        // unavailable, and its play command with it.
        trade(player);
      }
    },
    leave: giveBack,
  });
}
