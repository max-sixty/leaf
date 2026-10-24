import { pagePresented } from "./bundle-layer-client.js";

//#region runtime/motion.js
const preference = matchMedia("(prefers-reduced-motion: reduce)");
const active = /* @__PURE__ */ new Set();
const reducedMotion = () => preference.matches;
const scrollBehavior = () => preference.matches ? "instant" : "smooth";
function onMotionPreferenceChange(listener) {
	const changed = (event) => listener(event.matches);
	preference.addEventListener("change", changed);
	return () => preference.removeEventListener("change", changed);
}
preference.addEventListener("change", (event) => {
	if (event.matches) for (const played of [...active]) played.finish();
});
const motionPlays = () => !reducedMotion() && pagePresented();
const motion = (el, keyframes, ms, pseudoElement = null) => playMotion(el, keyframes, {
	duration: ms,
	pseudoElement
});
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
	played.finished.then(() => queueMicrotask(() => {
		active.delete(played);
		played.cancel();
	}), () => active.delete(played));
	return played;
}
const token = (property, on) => getComputedStyle(on).getPropertyValue(property).trim();
const motionTime = (property, on = document.documentElement) => {
	const value = token(property, on);
	return parseFloat(value) * (value.endsWith("ms") ? 1 : 1e3);
};
const motionEasing = (property, on = document.documentElement) => token(property, on);
const flashDuration = () => motionTime("--lf-motion-flash");
const agentArrivalDuration = () => motionTime("--lf-motion-agent-arrival");
function backgroundFlash(el, ms) {
	return motion(el, [{
		backgroundColor: "var(--hi-tint)",
		offset: 0
	}], ms);
}
const foldDuration = () => motionTime("--lf-motion-fold");
const returnDuration = () => motionTime("--lf-motion-return");
function foldBlock(el, allocation = null) {
	if (!CSS.supports("block-size", "calc-size(auto, size)")) return null;
	const adjustment = allocation ? allocation.priorSize - allocation.container.getBoundingClientRect().height : 0;
	return motion(el, [{
		blockSize: `calc-size(auto, size + ${adjustment}px)`,
		display: "block",
		overflow: "clip",
		opacity: 1
	}, {
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
	}], foldDuration());
}

//#endregion
export { agentArrivalDuration, backgroundFlash, flashDuration, foldBlock, foldDuration, motion, motionEasing, motionPlays, motionTime, onMotionPreferenceChange, playMotion, reducedMotion, returnDuration, scrollBehavior };