import { exceptionRecord, frameVisibility, keeps, move, nextRender, onFrameVisibility, readSampleVisibility, sizeObserver, watchFrame } from "./bundle-portable.js";
import { inputInFrame, pageUrl, runtime } from "./bundle-layer-stack.js";
import { RequestError, recordInteraction, requestJson } from "./bundle-layer-client.js";
import { aborted, widgetDescriptor } from "./bundle-abort.js";
import { frameView, layoutWindow, presented, watchRoom } from "./bundle-geometry.js";
import { dressFor, registerSampleDress } from "./bundle-dress.js";

//#region runtime/sample.js
const MAX_LOADING_SAMPLES = 3;
let loadingSamples = 0;
const loadWaiters = [];
let nextHost = 0;
async function loadWithinLimit(work, signal) {
	signal.throwIfAborted();
	if (loadingSamples === MAX_LOADING_SAMPLES) {
		const { promise: turn, resolve: proceed } = Promise.withResolvers();
		loadWaiters.push(proceed);
		await Promise.race([turn, aborted(signal)]);
		const waiting = loadWaiters.indexOf(proceed);
		if (waiting !== -1) {
			loadWaiters.splice(waiting, 1);
			throw signal.reason;
		}
	} else loadingSamples++;
	let released = false;
	const release = () => {
		if (released) return;
		released = true;
		const next = loadWaiters.shift();
		if (next) next();
		else loadingSamples--;
	};
	try {
		return await work(release);
	} finally {
		release();
	}
}
const departure = (message) => new DOMException(message, "SampleDepartedError");
const mounted = /* @__PURE__ */ new Map();
const isSampleFrame = (node) => mounted.has(node);
function sampleFrameImage(frame, crop) {
	const call = mounted.get(frame);
	if (!call) throw departure("Sample frame has departed");
	return call("image", crop);
}
const request = (url, body, headers = {}) => requestJson(String(url), {
	method: "POST",
	headers: {
		"Content-Type": "application/json",
		...headers
	},
	body: JSON.stringify(body),
	keepalive: true
}, "sample");
function connectionMessage(value) {
	return value !== null && typeof value === "object" && "type" in value && value.type === "leaf-sample-connect" && "sample" in value && typeof value.sample === "string" && "nonce" in value && typeof value.nonce === "string";
}
function mountSample(frame, { template, source, window: asWindow = false }) {
	if (template == null === (source == null)) throw new Error("a sample needs either an authored template id or source document");
	let revision = runtime.currentRevision;
	let message;
	for (let owner = frame.parentElement; owner; owner = owner.parentElement) {
		const descriptor = widgetDescriptor(owner);
		if (!descriptor) continue;
		if (descriptor.document.kind === "page") revision = descriptor.document.revision;
		else if (source == null) message = descriptor.document.message;
		break;
	}
	let current = null;
	let samplePage = null;
	let destroyed = false;
	let operation = null;
	let closing = null;
	let channel = null;
	let lost;
	let nextId = 0;
	let pendingInterface = null;
	let hasConnected = false;
	let connectedNonce = null;
	const hostId = ++nextHost;
	const started = performance.now();
	let allocation = 0;
	const record = (phase, detail = {}) => recordInteraction("sample", {
		host: hostId,
		template,
		revision,
		allocation,
		sample: samplePage,
		document: connectedNonce,
		elapsed: performance.now() - started,
		phase,
		...detail
	});
	const recordFailure = (error, detail = {}) => record("failed", {
		error: {
			...exceptionRecord(error),
			...error instanceof RequestError && {
				status: error.status,
				body: error.body
			}
		},
		...detail
	});
	const lifetimeController = new AbortController();
	const candidates = /* @__PURE__ */ new Set();
	const pending = /* @__PURE__ */ new Map();
	const listeners = {
		height: /* @__PURE__ */ new Set(),
		input: /* @__PURE__ */ new Set(),
		"current-location": /* @__PURE__ */ new Set(),
		arrived: /* @__PURE__ */ new Set(),
		loading: /* @__PURE__ */ new Set(),
		departed: /* @__PURE__ */ new Set()
	};
	const notify = (type, detail) => {
		for (const callback of listeners[type] ?? []) callback(detail);
	};
	keeps(frame, "sandbox", "allow-scripts allow-forms allow-popups allow-popups-to-escape-sandbox allow-modals allow-downloads allow-pointer-lock");
	frame.toggleAttribute("data-lf-contained", true);
	function admitted() {
		return document.visibilityState === "visible" && presented(frame) && seen.shown() && frameVisibility()?.visible !== false;
	}
	function visibility() {
		channel?.postMessage({
			type: "visibility",
			detail: { visible: admitted() }
		});
	}
	async function readVisibility(port, id) {
		try {
			const outer = await readSampleVisibility();
			if (channel !== port) return;
			const within = outer ? outer.visible && outer : layoutWindow();
			const view = admitted() && within && frameView(frame, within);
			port.postMessage({
				type: "visibility-reading",
				detail: {
					id,
					visible: Boolean(view),
					...view
				}
			});
		} catch (error) {
			if (channel !== port) return;
			port.postMessage({
				type: "visibility-reading",
				detail: {
					id,
					error: exceptionRecord(error)
				}
			});
			reportError(error);
		}
	}
	function disconnect(reason) {
		channel?.close();
		channel = null;
		lost = reason;
		connectedNonce = null;
		for (const { reject } of pending.values()) reject(reason);
		pending.clear();
	}
	function begin(work) {
		const active = work;
		operation = active;
		host.ready = active;
		const settled = () => {
			if (operation === active) operation = null;
		};
		active.then(settled, settled);
		return active;
	}
	async function settle(work) {
		try {
			return await work;
		} catch (error) {
			if (exceptionRecord(error).name !== "AbortError") {
				recordFailure(error);
				await retire("failure", error);
			}
			throw error;
		}
	}
	function interfaceReady() {
		const completion = Promise.withResolvers();
		pendingInterface = completion;
		return completion.promise;
	}
	function awaitNext() {
		if (pendingInterface) return;
		host.ready = settle(interfaceReady());
		host.ready.catch(() => {});
	}
	function failure(error) {
		if (pendingInterface) {
			const completion = pendingInterface;
			pendingInterface = null;
			completion.reject(error);
		} else {
			begin(settle(Promise.reject(error)));
			notify("loading", void 0);
		}
	}
	function connect(event) {
		const data = event.data;
		if (!current || event.source !== frame.contentWindow || !connectionMessage(data) || data.sample !== new URL(current).pathname || data.nonce === connectedNonce) return;
		const nonce = data.nonce;
		const owned = current;
		const pair = new MessageChannel();
		const port = pair.port1;
		const entry = document.querySelector("script[data-lf-entry]");
		if (!entry) throw new Error("A sample host needs the Leaf bootstrap entry");
		entry.lfDocumentPort = port;
		candidates.add(port);
		port.onmessage = ({ data }) => {
			if (data.type === "connected") {
				if (!candidates.has(port) || current !== owned || data.nonce !== nonce) return;
				candidates.delete(port);
				for (const candidate of candidates) candidate.close();
				candidates.clear();
				const reloading = hasConnected;
				disconnect(departure("sample document replaced"));
				channel = port;
				connectedNonce = nonce;
				hasConnected = true;
				record("connected", { reloading });
				if (reloading) {
					awaitNext();
					notify("loading", void 0);
				}
				visibility();
				return;
			}
			if (channel !== port) return;
			if (data.type === "departed") {
				record("departed");
				disconnect(departure("sample document navigated"));
				operation = null;
				awaitNext();
				notify("departed", void 0);
				return;
			}
			if (data.type === "visibility-read") {
				readVisibility(port, data.detail.id);
				return;
			}
			if (data.type === void 0) {
				const completion = pending.get(data.id);
				if (!completion) return;
				const { resolve, reject } = completion;
				pending.delete(data.id);
				if (data.error) reject(Object.assign(new Error(data.error.message), { stack: void 0 }, data.error));
				else resolve(data.result);
			} else if (data.type === "ready") {
				record("upgraded");
				const completion = pendingInterface;
				pendingInterface = null;
				completion?.resolve(data.detail);
				visibility();
			} else if (data.type === "error") failure(Object.assign(new Error(data.detail.message), { stack: void 0 }, data.detail));
			else if (data.type === "return") frame.dispatchEvent(new Event("lf-sample-return"));
			else if (data.type === "step") frame.dispatchEvent(new CustomEvent("lf-sample-step", {
				bubbles: true,
				composed: true,
				detail: data.detail
			}));
			else if (data.type === "input") {
				inputInFrame(frame, data.detail.type);
				notify("input", data.detail);
			} else if (data.type === "height") notify("height", data.detail);
			else if (data.type === "current-location") notify("current-location", data.detail);
			else if (data.type === "arrived") notify("arrived", void 0);
		};
		frame.contentWindow?.postMessage({
			sample: data.sample,
			nonce,
			settings: {
				window: asWindow,
				dress: dressFor(frame) ?? void 0
			}
		}, "*", [pair.port2]);
	}
	window.addEventListener("message", connect);
	const loaded = () => {
		if (current && frame.hasAttribute("src")) record("loaded");
	};
	frame.addEventListener("load", loaded);
	const room = watchRoom(visibility);
	document.addEventListener("visibilitychange", visibility);
	const seen = watchFrame(frame, visibility);
	const size = sizeObserver(visibility);
	size.observe(frame);
	const nativeTransition = () => nextRender(visibility);
	for (const type of ["beforetoggle"]) document.addEventListener(type, nativeTransition, true);
	const unwatch = onFrameVisibility(visibility);
	const undress = registerSampleDress(frame, (dress) => channel?.postMessage({
		type: "dress",
		detail: dress
	}));
	const lifetime = new MutationObserver(() => {
		if (!frame.isConnected) host.destroy();
	});
	lifetime.observe(document, {
		childList: true,
		subtree: true
	});
	function retire(reason, cause = new DOMException("sample replaced", "AbortError")) {
		if (!current) return;
		const retiringDocument = connectedNonce;
		const previous = current;
		const sample = samplePage;
		current = null;
		samplePage = null;
		hasConnected = false;
		disconnect(cause);
		for (const port of candidates) port.close();
		candidates.clear();
		const completion = pendingInterface;
		pendingInterface = null;
		completion?.reject(cause);
		const parent = frame.parentNode;
		const next = frame.nextSibling;
		frame.remove();
		frame.removeAttribute("src");
		if (parent) move(parent, frame, next);
		record("retired", {
			reason,
			document: retiringDocument,
			sample
		});
		return request(new URL("api/release", previous), {}).catch((error) => {
			recordFailure(error, {
				operation: "release",
				document: retiringDocument,
				sample
			});
			throw error;
		});
	}
	async function replace() {
		await retire("reset");
		allocation++;
		record("queued");
		return settle(loadWithinLimit(async (release) => {
			if (destroyed) throw new DOMException("sample destroyed", "AbortError");
			record("allocating");
			const { url, page } = await request(pageUrl("api/samples"), {
				template,
				source,
				message
			}, revision ? { "Leaf-View-Revision": String(revision) } : {});
			current = new URL(url, location.href).href;
			samplePage = page;
			record("allocated");
			try {
				if (destroyed) {
					await retire("destroyed");
					throw new DOMException("sample destroyed", "AbortError");
				}
				const admission = await fetch(current, {
					method: "HEAD",
					credentials: "omit",
					signal: lifetimeController.signal
				});
				record("admission", {
					status: admission.status,
					leafDocument: admission.headers.get("Leaf-Document")
				});
				if (!admission.ok || !admission.headers.has("Leaf-Document")) throw new Error("The sample document did not start Leaf");
				if (destroyed) {
					await retire("destroyed");
					throw new DOMException("sample destroyed", "AbortError");
				}
				const upgraded = interfaceReady();
				frame.addEventListener("load", release, { once: true });
				record("loading");
				frame.src = current;
				return await upgraded;
			} finally {
				frame.removeEventListener("load", release);
			}
		}, lifetimeController.signal));
	}
	function reset() {
		if (destroyed) return Promise.reject(/* @__PURE__ */ new Error("the sample host has been destroyed"));
		return operation ?? begin(replace());
	}
	function call(method, detail) {
		const ready = host.ready;
		return ready.then(() => {
			if (ready !== host.ready || !channel) throw lost;
			const port = channel;
			const id = ++nextId;
			return new Promise((resolve, reject) => {
				pending.set(id, {
					resolve,
					reject
				});
				port.postMessage({
					id,
					method,
					detail
				});
			});
		});
	}
	const host = {
		ready: replace(),
		reset,
		setWindow(value) {
			asWindow = value;
			return call("window", { window: value });
		},
		on(type, callback) {
			const callbacks = listeners[type];
			callbacks.add(callback);
			return () => {
				callbacks.delete(callback);
			};
		},
		restoreCurrentLocation: () => call("restore-current-location", {}),
		showThread(id, { signal, ...options }) {
			if (signal.aborted) return Promise.resolve(false);
			const cancel = () => channel?.postMessage({ type: "cancel-view" });
			signal.addEventListener("abort", cancel, { once: true });
			return call("thread", {
				id,
				...options
			}).finally(() => signal.removeEventListener("abort", cancel));
		},
		destroy() {
			if (closing) return closing;
			destroyed = true;
			record("destroyed");
			lifetimeController.abort(new DOMException("sample destroyed", "AbortError"));
			mounted.delete(frame);
			window.removeEventListener("message", connect);
			frame.removeEventListener("load", loaded);
			window.removeEventListener("pagehide", departing);
			room();
			document.removeEventListener("visibilitychange", visibility);
			seen.stop();
			size.disconnect();
			for (const type of ["beforetoggle"]) document.removeEventListener(type, nativeTransition, true);
			lifetime.disconnect();
			unwatch();
			undress();
			closing = Promise.all([retire("destroyed"), operation?.catch(() => {})]);
			return closing;
		}
	};
	const departing = (event) => {
		if (!event.persisted) host.destroy();
	};
	window.addEventListener("pagehide", departing);
	mounted.set(frame, call);
	begin(host.ready);
	return host;
}

//#endregion
export { isSampleFrame, mountSample, sampleFrameImage };