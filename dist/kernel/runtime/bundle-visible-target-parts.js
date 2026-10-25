import { drawn } from "./bundle-dom-move.js";
import { shownParts } from "./bundle-errors.js";

//#region runtime/visible-target-parts.js
function visibleTargetParts(target) {
	const parts = shownParts(target).filter(drawn);
	return drawn(target) ? [target, ...parts.filter((part) => part !== target)] : parts;
}

//#endregion
export { visibleTargetParts };