/* Reads the page after every frame it draws, for a reader that judges how the page
 * changes from one frame to the next: `leaf-dev probe --frames` and the box-motion
 * journey (tests/page_scripts/motion_frames.js).
 *
 * `lfFrames.begin(read)` calls `read()` in a task each frame posts once its frame
 * callbacks have run, so the reading shows what that frame drew. A read inside a frame
 * callback of the reader's own runs before the runtime's rendering pass for that frame
 * (browser/runtime/lib/frame-pass.js) and sees the frame before. An input the browser
 * handles between the frame and that task, as Firefox handles one ahead of other
 * tasks, changes a layout no frame has drawn yet, so that reading is dropped.
 *
 * Each reading is `{at, inputs, read}`: the frame's time in ms after the first frame,
 * how many inputs the page had handled, and what `read` returned.
 * `lfFrames.count()` says how many readings stand, `lfFrames.inputs()` how many inputs
 * the page has handled, which a reader takes before each of its own so a frame belongs
 * to the input whose events it has seen, and `lfFrames.end()` stops and returns the
 * readings.
 */
(() => {
  let inputs = 0;
  for (const type of [
    "keydown",
    "keyup",
    "beforeinput",
    "input",
    "pointerdown",
    "pointerup",
  ])
    addEventListener(type, () => inputs++, { capture: true, passive: true });
  /** @type {{frames: object[]} | null} */
  let recording = null;
  window.lfFrames = {
    /** @param {() => unknown} read */
    begin(read) {
      /** @type {object[]} */
      const frames = [];
      const channel = new MessageChannel();
      /** @type {number | null} */
      let first = null;
      recording = { frames };
      channel.port1.onmessage = ({ data: [at, seen] }) => {
        if (seen !== inputs) return;
        frames.push({ at, inputs, read: read() });
      };
      /** @param {number} time */
      const frame = (time) => {
        if (recording?.frames !== frames) return;
        first ??= time;
        channel.port2.postMessage([Math.round(time - first), inputs]);
        requestAnimationFrame(frame);
      };
      requestAnimationFrame(frame);
    },
    count: () => recording?.frames.length ?? 0,
    inputs: () => inputs,
    end() {
      const frames = recording?.frames ?? [];
      recording = null;
      return frames;
    },
  };
})();
