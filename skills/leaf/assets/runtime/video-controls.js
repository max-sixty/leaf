/* A recording on the page plays through Leaf's own quiet controls: a play and pause
   button and a timeline, in one bar over the recording's foot.

   The page writes `<video controls>`, and that stays its readable form: a page with no
   runtime, or one that failed to start, keeps the browser's controls. Once the runtime
   runs, each video standing in the document or a widget's first shadow stage
   (arrivals.js), where the bar can anchor to it, trades `controls` for `data-lf-player`
   while it stands, and gets the attribute back when it leaves. prepaint.js makes the
   trade for the served document's videos before their first paint, so the browser's
   controls never draw there to give way to the bar. The browsers' own
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

   Rejected: volume and fullscreen buttons, since a page's recordings are evidence
   clips, and the browser's menu on the video still offers its own controls. A widget
   tag for recordings, since every page already writes a plain `<video>`. */
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
import { focused } from "./focus.js";
import { iconElement } from "./icons.js";
import { keeps } from "./keeps.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";
import { plainPress } from "./pointer.js";
import { commandScope, projectCommandScope } from "./keyboard/scopes.js";
import { offer } from "./widget-elements.js";

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

function toggle(video) {
  if (!video.paused) return video.pause();
  // A pause asked for before playback starts ends that start; nothing else may.
  video.play().catch((error) => {
    if (error.name !== "AbortError") throw error;
  });
}

function paintTime({ video, time }) {
  const at = String(video.currentTime);
  if (time.value !== at) time.value = at;
  keeps(
    time,
    "aria-valuetext",
    `${clock(video.currentTime)} of ${clock(duration(video))}`,
  );
}

function paint(player) {
  const { video, bar, play, time } = player;
  const playing = !video.paused;
  bar.classList.toggle("lf-video-playing", playing);
  keeps(play, "aria-label", playing ? "Pause recording" : "Play recording");
  keeps(time, "max", String(duration(video)));
  // A recording that loads nothing until it plays has no length to scrub yet.
  keeps(time, "disabled", duration(video) ? null : "");
  paintTime(player);
}

// A player for `video`, its bar built and its listeners wired; `trade` writes it into
// the page.
function prepare(video) {
  const bar = offer("div", "lf-video-controls");
  const play = offer("button", "lf-video-play");
  play.tabIndex = -1;
  play.append(
    iconElement("play", "lf-video-icon"),
    iconElement("pause", "lf-video-icon"),
  );
  const time = offer("input", "lf-video-time", undefined, "range");
  time.tabIndex = -1;
  time.min = "0";
  time.step = "any";
  keeps(time, "aria-label", "Recording position");
  bar.append(play, time);
  // The bar stands in chrome, far from its video in the document, so it carries the
  // video's name for whoever reaches it by reading rather than by the picture.
  keeps(bar, "role", "group");
  keeps(bar, "aria-label", video.getAttribute("aria-label") || "Recording");
  const player = {
    video,
    bar,
    play,
    time,
    authoredTabindex: video.getAttribute("tabindex"),
    events: new AbortController(),
    /** @type {ReturnType<typeof commandScope> | null} */
    scope: null,
  };
  const { signal } = player.events;
  const on = (target, type, listener) =>
    target.addEventListener(type, listener, { signal });

  for (const type of ["play", "pause", "ended", "loadedmetadata", "durationchange"])
    on(video, type, () => paint(player));
  on(video, "seeked", () => paintTime(player));
  on(video, "timeupdate", () => paintTime(player));
  // The timeline follows each frame the browser presents rather than the few times a
  // second `timeupdate` fires, so its thumb glides instead of stepping.
  // One request stands at a time, however quickly playback stops and starts again.
  let frame = 0;
  const followFrames = () => {
    paintTime(player);
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
    if (plainPress(event)) toggle(video);
  });
  on(time, "input", () => (video.currentTime = Number(time.value)));

  // The bar shows for a pointer over the recording, and for the keyboard standing on
  // it: focus a key brought, or a command a key ran there. A press that focused the
  // picture leaves a playing recording whole.
  const show = (flag, force) => {
    if (force) revealControl(bar, video);
    bar.classList.toggle(flag, force);
  };
  on(video, "pointerenter", () => show("lf-video-hover", true));
  on(video, "pointerleave", () => show("lf-video-hover", false));
  on(video, "focus", () => show("lf-video-keyed", video.matches(":focus-visible")));
  on(video, "blur", () => show("lf-video-keyed", false));
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
        if (focused() === video) show("lf-video-keyed", true);
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
        show("lf-video-keyed", true);
        const step = binding === "ArrowLeft" ? -STEP_SECONDS : STEP_SECONDS;
        video.currentTime = Math.min(
          duration(video),
          Math.max(0, video.currentTime + step),
        );
      },
    },
  ]);
  players.set(video, player);
  return player;
}

function trade(player) {
  const { video, scope } = player;
  projectCommandScope(video, SCOPE, scope);
  keeps(video, PLAYER, "");
  keeps(video, "controls", null);
  if (player.authoredTabindex === null) keeps(video, "tabindex", "0");
  paint(player);
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
  // `data-lf-interactive` off the root and gives every video its `controls` back
  // (prepaint.js). The bars stand down with it, and no later arrival takes one.
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
