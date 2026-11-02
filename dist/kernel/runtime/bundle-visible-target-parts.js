import { drawn, shownParts, skipped } from "./bundle-portable.js";

//#region runtime/visible-target-parts.js
function visibleTargetParts(target) {
	if (skipped(target)) return [];
	const parts = shownParts(target).filter(drawn);
	return drawn(target) ? [target, ...parts.filter((part) => part !== target)] : parts;
}

//#endregion
export { visibleTargetParts };