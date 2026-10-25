import { focusDestination, focused } from "./bundle-dom-move.js";
import { notice, offer, raiseError } from "./bundle-layer-client.js";

//#region runtime/copy-control.js
function copyThroughSelection(value) {
	if (!value) return false;
	const selection = document.getSelection();
	const ranges = selection ? Array.from({ length: selection.rangeCount }, (_, i) => selection.getRangeAt(i)) : [];
	const before = focused();
	const field = document.createElement("textarea");
	field.value = value;
	field.style.cssText = "position: fixed; left: -9999px; top: 0";
	document.body.append(field);
	try {
		focusDestination(field, "return");
		field.select();
		return document.execCommand("copy");
	} catch {
		return false;
	} finally {
		field.remove();
		selection?.removeAllRanges();
		for (const range of ranges) selection?.addRange(range);
		if (before?.isConnected) focusDestination(before, "return");
	}
}
function copyControl(className, { label = "", success, error }) {
	const copy = offer("wa-copy-button", className);
	if (label) copy.copyLabel = label;
	copy.successLabel = success;
	copy.errorLabel = error;
	copy.tooltip = "none";
	copy.addEventListener("wa-copy", () => notice(success, { announce: false }));
	copy.addEventListener("wa-error", () => raiseError(error, { announce: false }));
	queueMicrotask(() => copy.addEventListener("click", (event) => {
		if (window.isSecureContext || window !== window.top || navigator.clipboard?.writeText) return;
		event.stopPropagation();
		if (event.defaultPrevented || copy.disabled || copy.isCopying) return;
		copy.isCopying = true;
		const copied = copyThroughSelection(copy.value);
		copy.showStatus(copied ? "success" : "error");
		copy.dispatchEvent(copied ? new CustomEvent("wa-copy", {
			bubbles: true,
			composed: true,
			detail: { value: copy.value }
		}) : new Event("wa-error", {
			bubbles: true,
			composed: true
		}));
	}, { capture: true }));
	return copy;
}

//#endregion
export { copyControl };