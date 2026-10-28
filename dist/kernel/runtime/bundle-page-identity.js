import { DELIVERY, runtime } from "./bundle-geometry.js";

//#region runtime/color-scheme.js
const darkPreference = matchMedia("(prefers-color-scheme: dark)");
function shownScheme() {
	const schemes = getComputedStyle(document.documentElement).colorScheme.split(/\s+/);
	return schemes.includes("dark") && (darkPreference.matches || !schemes.includes("light")) ? "dark" : "light";
}

//#endregion
//#region runtime/page-identity.js
function pageIdentity() {
	const state = runtime.state;
	const url = new URL(location.href);
	url.searchParams.delete("t");
	return structuredClone({
		url: String(url),
		delivery: DELIVERY,
		layer: state?.layer ?? null,
		preview: state?.preview ?? null,
		session_reference: runtime.sessionReference,
		browser: { user_agent: navigator.userAgent }
	});
}

//#endregion
export { darkPreference, pageIdentity, shownScheme };