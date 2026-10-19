import {
  pagePresented
} from "./bundle-page-paint.js";

// runtime/motion.js
var preference = matchMedia("(prefers-reduced-motion: reduce)");
var active = /* @__PURE__ */ new Set();
var reducedMotion = () => preference.matches;
var scrollBehavior = () => preference.matches ? "instant" : "smooth";
function onMotionPreferenceChange(listener) {
  const changed = (event) => listener(event.matches);
  preference.addEventListener("change", changed);
  return () => preference.removeEventListener("change", changed);
}
preference.addEventListener("change", (event) => {
  if (event.matches) for (const played of [...active]) played.finish();
});
function motion(el, keyframes, ms) {
  if (reducedMotion() || !pagePresented()) return null;
  const played = el.animate(keyframes, {
    duration: ms,
    easing: "ease",
    fill: "forwards"
  });
  active.add(played);
  played.finished.then(
    () => queueMicrotask(() => {
      active.delete(played);
      played.cancel();
    }),
    () => active.delete(played)
  );
  return played;
}
var time = (property) => {
  const value = getComputedStyle(document.documentElement).getPropertyValue(property).trim();
  return parseFloat(value) * (value.endsWith("ms") ? 1 : 1e3);
};
var flashDuration = () => time("--lf-motion-flash");
var agentArrivalDuration = () => time("--lf-motion-agent-arrival");
function backgroundFlash(el, ms) {
  return motion(el, [{ backgroundColor: "var(--hi-tint)", offset: 0 }], ms);
}
var foldDuration = () => time("--lf-motion-fold");
function foldBlock(el) {
  if (!CSS.supports("block-size", "calc-size(auto, size)")) return null;
  return motion(
    el,
    [
      {
        blockSize: "calc-size(auto, size)",
        display: "block",
        overflow: "clip",
        opacity: 1
      },
      {
        blockSize: "0px",
        minBlockSize: "0px",
        marginBlockStart: "0px",
        marginBlockEnd: "0px",
        paddingBlockStart: "0px",
        paddingBlockEnd: "0px",
        borderBlockStartWidth: "0px",
        borderBlockEndWidth: "0px",
        display: "block",
        overflow: "clip",
        opacity: 0
      }
    ],
    foldDuration()
  );
}

export {
  reducedMotion,
  scrollBehavior,
  onMotionPreferenceChange,
  motion,
  flashDuration,
  agentArrivalDuration,
  backgroundFlash,
  foldDuration,
  foldBlock
};
