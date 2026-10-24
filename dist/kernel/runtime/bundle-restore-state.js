import { DESIGN_MODE_KEY, tabStore } from "./bundle-surfaces.js";

//#region runtime/restore-state.js
const ANNOTATIONS_KEY = "lf-annotations";
const USER_VIEW_RESTORE_CASES = [{
	name: "design mode on",
	...tabStore.where(DESIGN_MODE_KEY),
	value: "1"
}, {
	name: "annotations hidden",
	...tabStore.where(ANNOTATIONS_KEY),
	value: "hidden"
}];
function restoreUserView({ setDesignMode }) {
	if (tabStore.get("lf-design-mode") === "1") setDesignMode(true, { spoken: false });
}

//#endregion
export { ANNOTATIONS_KEY, USER_VIEW_RESTORE_CASES, restoreUserView };