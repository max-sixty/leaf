import { TEXT_BOX, focused, isNativeLayer } from "./bundle-dom-move.js";
import { DELIVERY, PAGE_ROOT, describeFailure, offlineInteractive, pageUrl, runtime } from "./bundle-context.js";
import { holdingError, notice } from "./bundle-errors.js";

//#region runtime/page-paint.js
const PAGE_PAINT_ATTRIBUTE = Object.freeze({
	class: "class",
	obligation: "data-lf-obligation",
	done: "data-lf-done",
	restated: "data-lf-restated",
	retired: "data-lf-retired",
	settlement: "data-lf-state",
	applied: "data-lf-applied",
	reading: "data-lf-reading",
	dataVersion: "data-lf-data-version",
	source: "data-lf-source",
	sourceRevision: "data-lf-source-revision",
	userOverride: "data-lf-user-override",
	presented: "data-lf-presented",
	reported: "data-lf-reported",
	upgraded: "data-lf-upgraded",
	scrolls: "data-lf-scrolls",
	moreBefore: "data-lf-more-before",
	moreAfter: "data-lf-more-after",
	scrollDirection: "data-lf-scroll-direction",
	moreBelow: "data-lf-more-below",
	goto: "data-lf-go-to-active",
	traffic: "data-lf-traffic",
	indicated: "data-lf-indicated",
	player: "data-lf-player",
	kept: "data-lf-kept",
	mediaWidth: "data-lf-media-width",
	mediaHeight: "data-lf-media-height"
});
const pagePresented = () => document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented);
const pageUpgraded = () => document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.upgraded);

//#endregion
//#region runtime/root-state.js
const setRuntimeRootAttribute = (...args) => document.documentElement.lfInitial.setRuntimeRootAttribute(...args);
const setRuntimeRootStyle = (...args) => document.documentElement.lfInitial.setRuntimeRootStyle(...args);
const removeRuntimeRootStyle = (...args) => document.documentElement.lfInitial.removeRuntimeRootStyle(...args);
const runtimeRootState = (root) => ({
	attributes: document.documentElement.lfInitial.runtimeRootAttributes(root),
	styles: document.documentElement.lfInitial.runtimeRootStyles(root)
});

//#endregion
//#region runtime/traffic.js
const ledger = {
	sends: 0,
	acked: 0,
	asked: 0,
	heard: 0,
	pending: []
};
function paint() {
	setRuntimeRootAttribute(document.documentElement, PAGE_PAINT_ATTRIBUTE.traffic, JSON.stringify(ledger));
}
function countTraffic(key) {
	ledger[key] += 1;
	paint();
}
function watchPendingTraffic(sending) {
	let first = true;
	return sending.subscribe((attempts) => {
		const initial = first;
		first = false;
		if (initial && !attempts.length) return;
		ledger.pending = [...attempts];
		paint();
	});
}

//#endregion
//#region runtime/ids.js
const randomId = () => Array.from(crypto.getRandomValues(/* @__PURE__ */ new Uint8Array(16)), (byte) => byte.toString(16).padStart(2, "0")).join("");

//#endregion
//#region runtime/interaction-log.js
const enabled = PAGE_ROOT !== null;
const url = enabled ? new URL("api/interaction", PAGE_ROOT).href : null;
const root = enabled ? new URL(PAGE_ROOT).pathname.replace(/\/$/, "") : "";
const session = randomId();
const queue = [];
const MAX_PENDING_ENTRIES = 512;
const repetitive = /* @__PURE__ */ new Set([
	"resource",
	"pointermove",
	"pointerover",
	"pointerout",
	"pointerenter",
	"pointerleave",
	"wheel",
	"scroll",
	"selectionchange",
	"drag",
	"dragover",
	"touchmove",
	"compositionupdate"
]);
const encoder = new window.TextEncoder();
const nodeIds = /* @__PURE__ */ new WeakMap();
let nextSequence = 0;
let nextNodeId = 0;
let sending = false;
let inFlightCount = 0;
let scheduled = null;
const timestamp = () => (/* @__PURE__ */ new Date()).toISOString();
const pagePath = (pathname) => pathname === root || pathname === `${root}/` ? "/" : pathname.startsWith(`${root}/`) ? pathname.slice(root.length) : pathname;
function locator(node) {
	const id = node.id ? `#${node.id}` : "";
	const name = node.getAttribute("name");
	const named = name ? `[name=${JSON.stringify(name)}]` : "";
	return `${node.localName}${id}${named}`;
}
function nodeIdentity(node) {
	if (!nodeIds.has(node)) nodeIds.set(node, ++nextNodeId);
	return nodeIds.get(node);
}
function targetValue(target) {
	if (target instanceof window.HTMLInputElement) {
		if (target.type === "checkbox" || target.type === "radio") return {
			checked: target.checked,
			value: target.value
		};
		return { value: target.value };
	}
	if (target instanceof Element && target.matches(`${TEXT_BOX}, select`)) return { value: target.value };
	if (target instanceof HTMLElement && target.isContentEditable) return { value: target.textContent };
	return {};
}
function describe(event) {
	const path = event.composedPath();
	const elements = path.filter((node) => node instanceof Element).slice(0, 8);
	const entry = {
		type: event.type,
		target: elements.map(locator),
		nodes: elements.map(nodeIdentity),
		trusted: event.isTrusted
	};
	const target = path[0];
	const control = path.find((node) => node instanceof Element && node.matches(`button, a, summary, input, select, ${TEXT_BOX}, [role=button]`));
	if (control) {
		entry.control = locator(control);
		entry.controlNode = nodeIdentity(control);
	}
	const labelTarget = control ?? target;
	if (labelTarget instanceof Element) {
		const label = labelTarget.getAttribute("aria-label") || labelTarget.getAttribute("title");
		if (label) entry.label = label;
		else if (control) entry.label = control.textContent?.trim().slice(0, 200);
	}
	if (event instanceof window.KeyboardEvent) {
		entry.key = event.key;
		entry.code = event.code;
		entry.repeat = event.repeat;
		entry.modifiers = [
			"Alt",
			"Control",
			"Meta",
			"Shift"
		].filter((name) => event.getModifierState(name));
	} else if (event instanceof window.PointerEvent) entry.pointer = {
		id: event.pointerId,
		type: event.pointerType,
		button: event.button,
		buttons: event.buttons,
		x: event.clientX,
		y: event.clientY
	};
	else if (event instanceof window.WheelEvent) entry.delta = [
		event.deltaX,
		event.deltaY,
		event.deltaMode
	];
	else if (event instanceof window.MouseEvent) entry.pointer = {
		button: event.button,
		x: event.clientX,
		y: event.clientY
	};
	if (event instanceof window.InputEvent) {
		entry.inputType = event.inputType;
		entry.data = event.data;
	}
	if (event instanceof window.CompositionEvent) entry.data = event.data;
	if (event instanceof window.ClipboardEvent) entry.clipboard = event.clipboardData?.getData("text/plain") ?? "";
	if (event.changedTouches) entry.touches = [...event.changedTouches].map((touch) => ({
		id: touch.identifier,
		x: touch.clientX,
		y: touch.clientY
	}));
	if (event instanceof window.DragEvent && event.dataTransfer?.files.length) entry.files = [...event.dataTransfer.files].map((file) => ({
		name: file.name,
		size: file.size,
		type: file.type
	}));
	if ([
		"beforeinput",
		"input",
		"change"
	].includes(event.type)) Object.assign(entry, targetValue(target));
	if (event.type === "scroll") {
		const scroller = target === document ? document.scrollingElement : target;
		if (scroller instanceof Element) entry.scroll = [scroller.scrollLeft, scroller.scrollTop];
	}
	if (event.type === "selectionchange") entry.selection = document.getSelection()?.toString() ?? "";
	if ([
		"hashchange",
		"popstate",
		"pageshow",
		"pagehide"
	].includes(event.type)) entry.location = `${pagePath(location.pathname)}${location.hash}`;
	if (event.type === "resize") entry.viewport = [window.innerWidth, window.innerHeight];
	if (event.type === "visibilitychange") entry.visibility = document.visibilityState;
	if (["beforetoggle", "toggle"].includes(event.type) && target instanceof Element) entry.open = target.open === true || isNativeLayer(target);
	if (event.type === "fullscreenchange") entry.fullscreen = document.fullscreenElement ? {
		target: locator(document.fullscreenElement),
		node: nodeIdentity(document.fullscreenElement)
	} : null;
	return entry;
}
function schedule(delay = 250) {
	if (scheduled !== null || sending || !queue.length) return;
	scheduled = setTimeout(() => {
		scheduled = null;
		flush();
	}, delay);
}
function append(row) {
	if (queue.length >= MAX_PENDING_ENTRIES) {
		let evict = queue.findIndex((entry, index) => index >= inFlightCount && entry.repetitive);
		if (evict < 0) {
			if (row.repetitive) return;
			evict = inFlightCount;
			if (evict >= queue.length) return;
		}
		queue.splice(evict, 1);
	}
	queue.push(row);
}
function enqueue(entry) {
	if (!enabled) return;
	const common = {
		observed_at: timestamp(),
		monotonic_ms: performance.now(),
		visibility: document.visibilityState,
		sequence: ++nextSequence
	};
	let body = JSON.stringify({
		...entry,
		...common
	});
	let bytes = encoder.encode(body).length;
	if (bytes > 4e4) {
		body = JSON.stringify({
			...common,
			type: "interaction_omitted",
			originalType: entry.type,
			bytes,
			reason: "record_exceeds_limit"
		});
		bytes = encoder.encode(body).length;
	}
	append({
		body,
		bytes,
		repetitive: repetitive.has(entry.type)
	});
	schedule();
}
function batch(start, maxBytes) {
	const prefix = `{"session":${JSON.stringify(session)},"entries":[`;
	let bytes = encoder.encode(prefix).length + 2;
	let count = 0;
	while (start + count < queue.length && count < 100) {
		const size = queue[start + count].bytes + (count ? 1 : 0);
		if (count && bytes + size > maxBytes) break;
		bytes += size;
		count++;
	}
	return {
		count,
		body: `${prefix}${queue.slice(start, start + count).map((row) => row.body).join(",")}]}`
	};
}
function post(body) {
	return fetch(url, {
		method: "POST",
		headers: { "Content-Type": "application/json" },
		body,
		credentials: "same-origin",
		keepalive: encoder.encode(body).length < 6e4
	});
}
async function flush() {
	if (sending || !queue.length) return;
	sending = true;
	const { count, body } = batch(0, 1e5);
	inFlightCount = count;
	let delay = 250;
	try {
		const response = await post(body);
		if (response.status >= 400 && response.status < 500) {
			console.error(`Leaf interaction log rejected ${count} records: ${response.status}`);
			queue.splice(0, count);
			return;
		}
		if (!response.ok) throw new Error(`interaction log returned ${response.status}`);
		queue.splice(0, count);
	} catch {
		delay = 2e3;
	} finally {
		inFlightCount = 0;
		sending = false;
		schedule(delay);
	}
}
function recordInteraction(type, detail = {}) {
	enqueue({
		type,
		...detail
	});
}
if (enabled) {
	for (const type of [
		"pointerdown",
		"pointerup",
		"pointermove",
		"pointerover",
		"pointerout",
		"pointerenter",
		"pointerleave",
		"pointercancel",
		"click",
		"auxclick",
		"dblclick",
		"contextmenu",
		"wheel",
		"keydown",
		"keyup",
		"beforeinput",
		"input",
		"compositionstart",
		"compositionupdate",
		"compositionend",
		"change",
		"copy",
		"cut",
		"paste",
		"submit",
		"reset",
		"invalid",
		"focusin",
		"focusout",
		"scroll",
		"selectionchange",
		"visibilitychange",
		"dragstart",
		"drag",
		"dragend",
		"dragenter",
		"dragover",
		"dragleave",
		"drop",
		"touchstart",
		"touchmove",
		"touchend",
		"touchcancel",
		"beforetoggle",
		"toggle",
		"cancel",
		"close"
	]) document.addEventListener(type, (event) => enqueue(describe(event)), true);
	for (const type of [
		"pageshow",
		"pagehide",
		"hashchange",
		"popstate",
		"resize",
		"online",
		"offline",
		"fullscreenchange"
	]) window.addEventListener(type, (event) => enqueue(describe(event)), true);
	document.addEventListener("lf-command-invoked", (event) => {
		const active = focused();
		enqueue({
			type: "command",
			...event.detail,
			focus: active ? {
				target: locator(active),
				node: nodeIdentity(active)
			} : null,
			scroll: [window.scrollX, window.scrollY]
		});
	});
	new window.PerformanceObserver((list) => {
		for (const resource of list.getEntries()) {
			if (resource.name.startsWith(url)) continue;
			const resourceUrl = new URL(resource.name);
			if (pagePath(resourceUrl.pathname) === "/api/news") continue;
			enqueue({
				type: "resource",
				path: pagePath(resourceUrl.pathname),
				initiator: resource.initiatorType,
				durationMs: resource.duration,
				responseStatus: resource.responseStatus ?? null,
				transferSize: resource.transferSize
			});
		}
	}).observe({
		type: "resource",
		buffered: true
	});
	enqueue({
		type: "session_start",
		location: `${pagePath(location.pathname)}${location.hash}`,
		viewport: [window.innerWidth, window.innerHeight],
		userAgent: navigator.userAgent
	});
	window.addEventListener("pagehide", () => {
		for (let start = 0; start < queue.length;) {
			const { count, body } = batch(start, 48e3);
			start += count;
			post(body).catch(() => {});
		}
	}, true);
}

//#endregion
//#region runtime/layer-client.js
const { layer: layerGeneration, release, probe, runtime: runtimeIdentity } = DELIVERY;
async function sourceMovedOn() {
	if (!probe) return true;
	let response;
	try {
		response = await fetch(probe, { cache: "no-store" });
	} catch {
		return;
	}
	if (response.status === 404) return Boolean(release);
	if (!response.ok) return void 0;
	const servedRelease = response.headers.get("Leaf-Release");
	if (release && servedRelease) return servedRelease !== release;
	if (!sameRuntime(response)) return true;
	const generation = response.headers.get("Leaf-Layer");
	return generation ? generation !== layerGeneration : void 0;
}
let layerReloading = false;
function reloadNow(message) {
	if (layerReloading) return;
	layerReloading = true;
	notice(message);
	location.reload();
}
let asking = false;
const holdWaiting = holdingError();
function reloadDelivery(message) {
	if (layerReloading || asking) return;
	asking = true;
	(async () => {
		try {
			const moved = await sourceMovedOn();
			if (moved === void 0) return;
			if (!moved) {
				holdWaiting("Waiting for Leaf to finish updating.");
				return;
			}
			reloadNow(message);
		} finally {
			asking = false;
		}
	})();
}
const sameRuntime = (response) => {
	const served = response.headers.get("Leaf-Runtime");
	return !runtimeIdentity || !served || served === runtimeIdentity;
};
function layerHeaders(headers = {}) {
	return {
		"Leaf-Layer": layerGeneration,
		...runtimeIdentity && { "Leaf-Runtime": runtimeIdentity },
		...runtime.currentRevision && { "Leaf-View-Revision": String(runtime.currentRevision) },
		...release && { "Leaf-Release": release },
		...headers
	};
}
const dataHeaders = (held) => held.version === null ? {} : { "Leaf-Data-Version": held.version };
const completeData = (state, held) => state && !state.data.sources ? {
	...state,
	data: held
} : state;
var LayerRefused = class extends Error {};
async function requestJson(url, init, what) {
	const response = await fetch(url, {
		...init,
		headers: layerHeaders(init.headers)
	});
	if (!admitResponse(response)) throw new LayerRefused(`Leaf's layer changed while requesting ${what}`);
	const text = await response.text();
	const failed = (message, cause) => Object.assign(new Error(message, { cause }), {
		status: response.status,
		body: text
	});
	let answer = null;
	if (response.ok || response.headers.get("Content-Type")?.split(";")[0].trim() === "application/json") try {
		answer = JSON.parse(text);
	} catch (error) {
		throw failed(`${what}: HTTP ${response.status}`, error);
	}
	if (!response.ok) {
		const refusal = answer;
		throw Object.assign(failed(refusal?.error ?? `${what}: HTTP ${response.status}`), {
			current: refusal && "current" in refusal ? refusal.current : void 0,
			said: refusal?.error
		});
	}
	return answer;
}
function sameLayer(generation) {
	if (generation === layerGeneration) return true;
	reloadDelivery("Leaf has been updated — reloading this page.");
	return false;
}
const admitResponse = (response) => admitted(response, true);
const admitReading = (response) => admitted(response, false);
function admitted(response, ofThisLayer) {
	observeSession(response);
	observeKey(response);
	if (!response.ok) return true;
	if (layerReloading) return false;
	const generation = response.headers.get("Leaf-Layer");
	const responseRelease = response.headers.get("Leaf-Release");
	if (ofThisLayer && generation && !sameLayer(generation)) return false;
	if (!sameRuntime(response)) {
		reloadDelivery("Leaf has been updated — reloading this page.");
		return false;
	}
	if (release && responseRelease && responseRelease !== release) {
		reloadDelivery("Leaf has been updated — reloading this page.");
		return false;
	}
	holdWaiting(null);
	return true;
}
let sessionMode = release ? "unknown" : "active";
const sessionChannel = release && !document.documentElement.lfSample ? new window.BroadcastChannel(`leaf-session:${release}:${pageUrl("")}`) : null;
function activateSession(broadcast) {
	const activated = sessionMode !== "active";
	sessionMode = "active";
	if (activated) document.dispatchEvent(new Event("lf-session-active"));
	if (broadcast && activated) sessionChannel?.postMessage({ active: true });
}
sessionChannel?.addEventListener("message", (event) => {
	if (event.data?.active === true) activateSession(false);
});
function observeSession(response) {
	const reference = response.headers.get("Leaf-Session-Reference");
	if (/^\d{12}$/.test(reference)) runtime.sessionReference = reference;
	const mode = response.headers.get("Leaf-Session");
	if (mode === "active") activateSession(true);
	else if (mode === "passive" && sessionMode !== "active") sessionMode = "passive";
}
const sessionIsActive = () => sessionMode === "active";
const KEY_REFUSED = 401;
function observeKey(response) {
	runtime.keyRefused = response.status === KEY_REFUSED;
}
const { promise: layerReady, resolve: layerRevealed } = Promise.withResolvers();
let layerKnown = false;
const revealLayer = () => {
	layerKnown = true;
	layerRevealed();
};
const postEvent = async (event, held = runtime.data) => {
	if (offlineInteractive) throw new Error("no agent or server is available in an interactive export");
	if (!layerKnown) await layerReady;
	countTraffic("sends");
	recordInteraction("event_post", {
		kind: event.kind,
		attempt: event.attempt ?? null
	});
	let response;
	try {
		response = await fetch(pageUrl("api/event"), {
			method: "POST",
			headers: layerHeaders({
				"Content-Type": "application/json",
				...dataHeaders(held)
			}),
			body: JSON.stringify(event)
		});
		recordInteraction("event_response", {
			kind: event.kind,
			attempt: event.attempt ?? null,
			status: response.status
		});
	} catch (error) {
		recordInteraction("event_response", {
			kind: event.kind,
			attempt: event.attempt ?? null,
			error: String(error)
		});
		throw error;
	} finally {
		countTraffic("acked");
	}
	if (!admitResponse(response)) return null;
	if (response.status === KEY_REFUSED) throw new Error("the server refused this page's key");
	return response;
};
const uploadMedia = async (file) => {
	if (offlineInteractive) throw new Error("no agent or server is available in an interactive export");
	await layerReady;
	countTraffic("sends");
	let answer;
	try {
		answer = await requestJson(pageUrl("api/media"), {
			method: "POST",
			headers: { "Content-Type": file.type },
			body: file
		}, "image upload");
	} catch (error) {
		if (error instanceof LayerRefused) return null;
		throw error;
	} finally {
		countTraffic("acked");
	}
	return answer.path;
};
const reportedReasons = /* @__PURE__ */ new WeakSet();
const reportedPrimitives = /* @__PURE__ */ new Set();
const reportedErrors = /* @__PURE__ */ new Set();
function reportPageError(reason, context = "") {
	if (typeof reason === "object" && reason !== null) reportedReasons.add(reason);
	else reportedPrimitives.add(String(reason));
	const text = exceptionText(reason, context);
	document.documentElement.lfDocumentLifetime.whenActive(`report ${text}`, () => {
		console.error(`leaf: ${text}`);
		if (offlineInteractive) return;
		if (reportedErrors.has(text) || reportedErrors.size >= 20) return;
		reportedErrors.add(text);
		postEvent({
			kind: "error",
			text,
			...runtime.currentRevision != null && { revision: runtime.currentRevision }
		}).catch(() => {});
	});
}
function reportCarried(reason, context = "") {
	if (!(typeof reason === "object" && reason !== null ? reportedReasons.has(reason) : reportedPrimitives.has(String(reason)))) reportPageError(reason, context);
}
function exceptionText(reason, context = "") {
	const message = reason?.message;
	const text = message === void 0 ? String(reason) : `${reason.name || "Error"}: ${message}`;
	const stack = reason?.stack;
	let evidence = !stack ? text : stack.includes(text) ? stack : `${text}\n${stack}`;
	if (reason instanceof AggregateError) evidence += reason.errors.map((error) => `\n${exceptionText(error)}`).join("");
	if (reason?.cause !== void 0) evidence += `\nCaused by: ${exceptionText(reason.cause)}`;
	if (!context) return evidence;
	return `${context}: ${reason instanceof Error ? describeFailure(reason) : message ?? String(reason)}${message === void 0 ? "" : `\n${evidence}`}`;
}
window.addEventListener("error", (e) => {
	if (e.message?.startsWith("ResizeObserver loop")) return;
	reportPageError(e.error?.stack ? e.error : `${e.message} (${e.filename}:${e.lineno})`);
});
window.addEventListener("unhandledrejection", (e) => {
	reportPageError(e.reason);
});

//#endregion
export { LayerRefused, PAGE_PAINT_ATTRIBUTE, admitReading, admitResponse, completeData, countTraffic, dataHeaders, exceptionText, layerHeaders, pagePresented, pageUpgraded, postEvent, randomId, recordInteraction, removeRuntimeRootStyle, reportCarried, reportPageError, requestJson, revealLayer, runtimeRootState, sameLayer, sessionIsActive, setRuntimeRootAttribute, setRuntimeRootStyle, uploadMedia, watchPendingTraffic };