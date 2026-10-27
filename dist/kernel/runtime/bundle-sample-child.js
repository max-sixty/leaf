import { afterSettling, canPlaceFocus, focusDestination, onCurrentLocation, onUserInput, sizeObserver } from "./bundle-dom-move.js";
import { pagePresented, pageUpgraded } from "./bundle-layer-client.js";
import { whenArrived, whenArriving } from "./bundle-reading-regions.js";

//#region runtime/sample-child.js
const child = document.documentElement.lfSample;
const commands = /* @__PURE__ */ new Map();
const observers = /* @__PURE__ */ new Map();
function onSampleNotice(type, callback) {
	if (!observers.has(type)) observers.set(type, /* @__PURE__ */ new Set());
	observers.get(type).add(callback);
	return () => observers.get(type).delete(callback);
}
function registerSampleCommand(name, callback) {
	commands.set(name, callback);
	return () => commands.delete(name);
}
function sampleNotice(type, detail = {}) {
	child?.send({
		type,
		detail
	});
}
if (child) child.receive(async ({ id, method, type, detail }) => {
	if (type) {
		for (const callback of observers.get(type) ?? []) callback(detail);
		return;
	}
	try {
		if (!commands.has(method)) throw new Error(`Unknown sample command: ${method}`);
		const result = await commands.get(method)(detail);
		child.send({
			id,
			result
		});
	} catch (error) {
		child.send({
			id,
			error: {
				name: error.name,
				message: error.message,
				stack: error.stack
			}
		});
	}
});
if (child) {
	let upgraded = false;
	let arriving = false;
	let height = null;
	let currentLocation = null;
	onCurrentLocation((node) => {
		if (node && node !== document.body) currentLocation = node;
		sampleNotice("current-location", { focused: Boolean(node && node !== document.body) });
	});
	let gestures = 0;
	const input = (event) => {
		if (!event.isTrusted || event.type === "blur") return;
		gestures++;
		afterSettling(() => gestures--);
		sampleNotice("input", { type: event.type });
	};
	onUserInput(input);
	window.addEventListener("click", input, {
		capture: true,
		passive: true
	});
	registerSampleCommand("restore-current-location", () => {
		if (!currentLocation?.isConnected || !canPlaceFocus()) return false;
		focusDestination(currentLocation, "return");
		return document.hasFocus();
	});
	const measure = () => {
		if (!document.body) return;
		const next = Math.ceil(document.body.getBoundingClientRect().height);
		if (next !== height) {
			height = next;
			sampleNotice("height", {
				height,
				gesture: gestures > 0
			});
		}
	};
	registerSampleCommand("image", async ({ x, y, width, height }) => {
		const { pageImage } = await import("./bundle-page-image.js");
		return pageImage({
			x: scrollX + x,
			y: scrollY + y,
			width,
			height
		});
	});
	registerSampleCommand("window", async ({ window: asWindow }) => {
		child.settings.window = asWindow;
		document.documentElement.lfInitial.setRuntimeRootAttribute(document.documentElement, "data-lf-sample-block", asWindow ? null : "");
		measure();
		return { height };
	});
	const inspect = () => {
		const error = document.documentElement.dataset.lfStartupError;
		if (error) sampleNotice("error", document.documentElement.lfStartupException ?? { message: error });
		if (upgraded && !arriving && pagePresented()) {
			arriving = true;
			(async () => {
				await whenArrived();
				sampleNotice("arrived");
				for (;;) {
					await whenArriving();
					sampleNotice("arriving");
					await whenArrived();
					sampleNotice("arrived");
				}
			})();
		}
		if (upgraded || !(document.body && pageUpgraded())) return;
		upgraded = true;
		child.present();
		measure();
		sizeObserver(measure, { counted: false }).observe(document.body);
		sampleNotice("ready", {
			height,
			block: document.documentElement.hasAttribute("data-lf-sample-block")
		});
		inspect();
	};
	new MutationObserver(inspect).observe(document, {
		childList: true,
		subtree: true,
		attributes: true,
		attributeFilter: [
			"data-lf-upgraded",
			"data-lf-presented",
			"data-lf-startup-error"
		]
	});
	inspect();
}

//#endregion
export { onSampleNotice, registerSampleCommand, sampleNotice };