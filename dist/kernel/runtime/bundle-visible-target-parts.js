import { drawn, shownParts, skipped } from "./bundle-portable.js";

//#region runtime/visible-target-parts.js
const painted = (part) => drawn(part) && part.checkVisibility({ opacityProperty: true });
function visibleTargetParts(target) {
	if (skipped(target)) return [];
	const parts = shownParts(target).filter(painted);
	return painted(target) ? [target, ...parts.filter((part) => part !== target)] : parts;
}

//#endregion
export { visibleTargetParts };