// Check pair structure and distinct registered files. Exact originals preserve
// their order here; the visual rubric judges cropped or marked captures.
const { Window } = require("happy-dom");

function pair(output, context, outlines = false) {
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
      (!outlines || shot.hasAttribute("outlines"))
    );
  });
  window.close();
  return passes;
}

exports.pair = (output, context) => pair(output, context);
exports.outlinedPair = (output, context) => pair(output, context, true);
