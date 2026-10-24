import { notice, offer, raiseError } from "./bundle-layer-client.js";

//#region runtime/copy-control.js
function copyControl(className, { label = "", success, error }) {
	const copy = offer("wa-copy-button", className);
	if (label) copy.copyLabel = label;
	copy.successLabel = success;
	copy.errorLabel = error;
	copy.tooltip = "none";
	copy.addEventListener("wa-copy", () => notice(success, { announce: false }));
	copy.addEventListener("wa-error", () => raiseError(error, { announce: false }));
	return copy;
}

//#endregion
export { copyControl };