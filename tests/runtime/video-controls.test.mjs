/* Recording chrome retains its controls and follows the native media clock.
 * Playback itself is the browser's boundary, covered by the recording-bar cases. */
import assert from "node:assert/strict";
import test from "node:test";
import { paintRecordingControls } from "/runtime/video-controls.js";

test("a recording redraw retains native media and controls, including a range the user moved", (t) => {
  const video = document.createElement("video");
  // happy-dom has no decoder: these are the native readings the renderer consumes.
  Object.defineProperties(video, {
    duration: { configurable: true, writable: true, value: 125 },
    currentTime: { configurable: true, writable: true, value: 12 },
    paused: { configurable: true, writable: true, value: true },
  });
  video.setAttribute("aria-label", "Test recording");
  const bar = document.createElement("div");
  bar.className = "lf-video-controls";
  const paint = () => paintRecordingControls(video, bar, () => {});
  paint();
  document.body.append(video, bar);
  t.after(() => {
    video.remove();
    bar.remove();
  });
  const play = bar.querySelector(".lf-video-play");
  const timeline = bar.querySelector(".lf-video-time");
  const fullScreen = bar.querySelector(".lf-video-full-screen");
  assert.equal(bar.getAttribute("aria-label"), "Test recording");
  assert.equal(play.getAttribute("aria-label"), "Play recording");
  assert.equal(bar.hasAttribute("data-playing"), false);
  assert.equal(timeline.value, "12");
  assert.equal(timeline.getAttribute("aria-valuetext"), "0:12 of 2:05");
  timeline.value = "90";
  // A redraw follows the video's clock even when a native input changed its own value.
  paint();
  assert.equal(timeline.value, "12");
  timeline.value = "55";
  timeline.dispatchEvent(new Event("input"));
  assert.equal(video.currentTime, 55);
  video.paused = false;
  paint();
  assert.equal(bar.hasAttribute("data-playing"), true);
  assert.equal(play.getAttribute("aria-label"), "Pause recording");
  assert.equal(timeline.getAttribute("aria-valuetext"), "0:55 of 2:05");
  assert.equal(bar.querySelector(".lf-video-play"), play);
  assert.equal(bar.querySelector(".lf-video-time"), timeline);
  assert.equal(bar.querySelector(".lf-video-full-screen"), fullScreen);
  video.duration = Infinity;
  paint();
  assert.equal(timeline.disabled, true);
});
