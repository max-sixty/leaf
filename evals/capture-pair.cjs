// Check pair structure and distinct registered files. Exact originals preserve
// their order here; the visual rubric judges cropped or marked captures.
const { readFileSync } = require("node:fs");
const { Window } = require("happy-dom");

// The widest frame an lf-shot draws near its captured size: the column is about
// 720px, so a frame up to a third wider still reads at three quarters of it. Cases
// that use it capture at device scale 1, so a PNG's width is its CSS width.
const READABLE_WIDTH = 960;

function pair(output, context, accept = () => true) {
  const media = context.providerResponse.metadata.input_media;
  const before = Object.entries(media).find(([path]) =>
    path.endsWith("/before.png"),
  )?.[1];
  const after = Object.entries(media).find(([path]) =>
    path.endsWith("/after.png"),
  )?.[1];
  if (!before || !after || before === after) return false;
  const window = new Window({ settings: { disableJavaScriptEvaluation: true } });
  const document = new window.DOMParser().parseFromString(output, "text/html");
  const passes = [...document.querySelectorAll("lf-shot")].some((shot) => {
    const first = shot.getAttribute("before"),
      second = shot.getAttribute("after");
    const registered = context.providerResponse.metadata.capture_evidence?.media ?? {};
    const originals = [before, after];
    return (
      first !== second &&
      first &&
      second &&
      (first === before || first === after || Object.hasOwn(registered, first)) &&
      (second === before || second === after || Object.hasOwn(registered, second)) &&
      (!(originals.includes(first) && originals.includes(second)) ||
        (first === before && second === after)) &&
      accept(shot, registered)
    );
  });
  window.close();
  return passes;
}

const pngWidth = (path) => readFileSync(path).readUInt32BE(16);

exports.pair = (output, context) => pair(output, context);
exports.outlinedPair = (output, context) =>
  pair(output, context, (shot) => shot.hasAttribute("outlines"));
exports.readablePair = (output, context) =>
  pair(output, context, (shot, registered) =>
    ["before", "after"].every((side) => {
      const path = registered[shot.getAttribute(side)];
      return path !== undefined && pngWidth(path) <= READABLE_WIDTH;
    }),
  );
