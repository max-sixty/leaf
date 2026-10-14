import {
  LEAVING,
  announceRoom,
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
var SLIDE_IN_MS = 200;
var SLIDE_OUT_MS = 160;
var slides = /* @__PURE__ */ new WeakMap();
function slide(el, side, direction) {
  const running = slides.get(el);
  const at = running && { transform: getComputedStyle(el).transform };
  running?.cancel();
  const away = { transform: `translateX(${side === "left" ? "-100%" : "100%"})` };
  const home = { transform: "translateX(0)" };
  const played = direction === "in" ? motion(el, [at ?? away, home], SLIDE_IN_MS) : motion(el, [at ?? home, away], SLIDE_OUT_MS);
  const leaving = Boolean(played) && direction === "out";
  el.toggleAttribute(LEAVING, leaving);
  el.toggleAttribute("inert", leaving);
  if (!played) {
    slides.delete(el);
    return null;
  }
  slides.set(el, played);
  played.finished.then(
    () => {
      slides.delete(el);
      el.removeAttribute(LEAVING);
      el.toggleAttribute("inert", false);
      announceRoom(el);
    },
    () => {
    }
  );
  return played;
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
  slide
};
