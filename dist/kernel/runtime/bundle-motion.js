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
var motionPlays = () => !reducedMotion() && pagePresented();
var motion = (el, keyframes, ms, pseudoElement = null) => playMotion(el, keyframes, { duration: ms, pseudoElement });
function playMotion(el, keyframes, { duration, easing = "ease", delay = 0, pseudoElement = null }) {
  if (!motionPlays()) return null;
  const played = el.animate(keyframes, {
    duration,
    delay,
    pseudoElement,
    easing,
    fill: "both"
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
var token = (property, on) => getComputedStyle(on).getPropertyValue(property).trim();
var motionTime = (property, on = document.documentElement) => {
  const value = token(property, on);
  return parseFloat(value) * (value.endsWith("ms") ? 1 : 1e3);
};
var motionEasing = (property, on = document.documentElement) => token(property, on);
var flashDuration = () => motionTime("--lf-motion-flash");
var agentArrivalDuration = () => motionTime("--lf-motion-agent-arrival");
function backgroundFlash(el, ms) {
  return motion(el, [{ backgroundColor: "var(--hi-tint)", offset: 0 }], ms);
}
var foldDuration = () => motionTime("--lf-motion-fold");
var returnDuration = () => motionTime("--lf-motion-return");
function foldBlock(el, allocation = null) {
  if (!CSS.supports("block-size", "calc-size(auto, size)")) return null;
  const adjustment = allocation ? allocation.priorSize - allocation.container.getBoundingClientRect().height : 0;
  return motion(
    el,
    [
      {
        blockSize: `calc-size(auto, size + ${adjustment}px)`,
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
  motionPlays,
  motion,
  playMotion,
  motionTime,
  motionEasing,
  flashDuration,
  agentArrivalDuration,
  backgroundFlash,
  foldDuration,
  returnDuration,
  foldBlock
};
