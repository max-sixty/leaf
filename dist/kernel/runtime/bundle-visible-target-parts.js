import { skipped } from "./bundle-portable.js";
import { drawn } from "./bundle-layer-stack.js";
import { shownParts } from "./bundle-geometry.js";

//#region runtime/visible-target-parts.js
function visibleTargetParts(target) {
	if (skipped(target)) return [];
	const parts = shownParts(target).filter(drawn);
	return drawn(target) ? [target, ...parts.filter((part) => part !== target)] : parts;
}

//#endregion
export { visibleTargetParts };