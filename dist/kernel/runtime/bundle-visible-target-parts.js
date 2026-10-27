import { drawn } from "./bundle-dom-move.js";
import { shownParts, skipped } from "./bundle-geometry.js";

//#region runtime/visible-target-parts.js
function visibleTargetParts(target) {
	if (skipped(target)) return [];
	const parts = shownParts(target).filter(drawn);
	return drawn(target) ? [target, ...parts.filter((part) => part !== target)] : parts;
}

//#endregion
export { visibleTargetParts };