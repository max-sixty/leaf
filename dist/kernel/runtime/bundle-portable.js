//#region runtime/queued-work.js
const jobObservers = /* @__PURE__ */ new Set();
const jobCohorts = /* @__PURE__ */ new WeakMap();
function observeQueuedWork(observer) {
	jobObservers.add(observer);
	return () => jobObservers.delete(observer);
}
const announce = (phase, job, observers) => {
	for (const observer of observers) observer(phase, job);
};
function enqueueWork(callback) {
	const job = Object.freeze({ callback });
	const observers = [...jobObservers];
	jobCohorts.set(job, observers);
	announce("enqueue", job, observers);
	return job;
}
function claim(job) {
	const observers = jobCohorts.get(job);
	jobCohorts.delete(job);
	return observers;
}
function runWork(job, ...args) {
	const observers = claim(job);
	if (!observers) return;
	const callback = job.callback;
	try {
		announce("run", job, observers);
		return callback(...args);
	} finally {
		announce("finish", job, observers);
	}
}
function bindQueuedWork(callback) {
	const job = enqueueWork(callback);
	return (...args) => runWork(job, ...args);
}
function cancelWork(job) {
	const observers = claim(job);
	if (observers) announce("cancel", job, observers);
}

//#endregion
//#region runtime/frame-visibility.js
const child = document.documentElement.lfSample;
let admitted = false;
const observers = /* @__PURE__ */ new Set();
const readings = /* @__PURE__ */ new Map();
let readingId = 0;
function watchFrame(frame, callback) {
	let intersecting = false;
	const seen = new IntersectionObserver((entries) => {
		const { width, height } = entries.at(-1).intersectionRect;
		intersecting = width > 0 && height > 0;
		callback();
	}, { threshold: [
		0,
		Number.EPSILON,
		1
	] });
	seen.observe(frame);
	const styled = new MutationObserver((records) => {
		if (records.some(({ target }) => target === frame || target.contains(frame))) callback();
	});
	styled.observe(frame.ownerDocument, {
		subtree: true,
		attributes: true,
		attributeFilter: [
			"inert",
			"open",
			"hidden",
			"aria-hidden",
			"class",
			"style"
		]
	});
	return {
		shown: () => intersecting && frame.checkVisibility({ visibilityProperty: true }) && getComputedStyle(frame).contentVisibility !== "hidden",
		stop: () => {
			seen.disconnect();
			styled.disconnect();
		}
	};
}
const owners$1 = [];
if (!child) for (let view = window; view.frameElement; view = view.parent) owners$1.push(watchFrame(view.frameElement, publish));
function frameVisibility() {
	if (child) return { visible: admitted };
	if (owners$1.length) return { visible: owners$1.every((owner) => owner.shown()) };
	return null;
}
function onFrameVisibility(callback) {
	observers.add(callback);
	return () => observers.delete(callback);
}
function readSampleVisibility() {
	if (!child) return null;
	return new Promise((resolve, reject) => {
		const id = ++readingId;
		readings.set(id, {
			resolve,
			reject
		});
		child.send({
			type: "visibility-read",
			detail: { id }
		});
	});
}
function publish() {
	const visibility = frameVisibility();
	for (const callback of observers) callback(visibility);
}
if (child) child.receive(({ type, detail }) => {
	if (type === "visibility-reading") {
		const reading = readings.get(detail.id);
		readings.delete(detail.id);
		if (detail.error) reading?.reject(Object.assign(new Error(detail.error.message), { stack: void 0 }, detail.error));
		else reading?.resolve(detail);
		return;
	}
	if (type !== "visibility") return;
	admitted = detail.visible;
	publish();
});
addEventListener("pagehide", (event) => {
	if (!event.persisted) for (const owner of owners$1) owner.stop();
});

//#endregion
//#region runtime/rendering.js
const ROUNDS = 8;
let queued = /* @__PURE__ */ new Map();
let running = null;
let afterPaint = /* @__PURE__ */ new Map();
let lastId = 0;
let frame = 0;
let heard = false;
let quiet = false;
let checking = false;
let preparations = 0;
const preparationObservers = /* @__PURE__ */ new Set();
function observePreparations(observer) {
	preparationObservers.add(observer);
	return () => preparationObservers.delete(observer);
}
function holdRendering() {
	preparations++;
	const serial = ++begun;
	pending.add(serial);
	unsettle();
	const identity = Object.freeze({});
	const observers = [...preparationObservers];
	for (const observer of observers) observer("begin", identity);
	let released = false;
	return (phase = "settle") => {
		if (released) return;
		released = true;
		preparations--;
		pending.delete(serial);
		if (updateChecking) heard = true;
		unsettle();
		for (const observer of observers) observer(phase, identity);
	};
}
function request(into, callback) {
	const id = ++lastId;
	into.set(id, enqueueWork(callback));
	if (!running && !frame) frame = requestAnimationFrame(pass);
	unsettle();
	return id;
}
const nextRender = (callback) => request(queued, callback);
const nextFrame = (callback) => request(running ? afterPaint : queued, callback);
const nextAnimation = (callback) => requestAnimationFrame(callback);
const cancelAnimation = (id) => cancelAnimationFrame(id);
function cancelRender(id) {
	for (const queue of [
		queued,
		afterPaint,
		running
	]) {
		const job = queue?.get(id);
		if (!job) continue;
		queue.delete(id);
		cancelWork(job);
		return;
	}
}
async function pass(time) {
	frame = 0;
	for (let round = 0; queued.size && round < ROUNDS; round++) {
		running = queued;
		queued = /* @__PURE__ */ new Map();
		for (const [id, job] of running) {
			running.delete(id);
			try {
				runWork(job, time);
			} catch (error) {
				reportError(error);
			}
			await null;
		}
	}
	running = null;
	for (const entry of afterPaint) queued.set(...entry);
	afterPaint = /* @__PURE__ */ new Map();
	if (queued.size) frame = requestAnimationFrame(pass);
}
const owedThisScript = /* @__PURE__ */ new Map();
function settleScript() {
	for (const [callback, job] of owedThisScript) {
		owedThisScript.delete(callback);
		try {
			runWork(job);
		} catch (error) {
			reportError(error);
		}
	}
}
function afterScript(callback) {
	if (!owedThisScript.size) queueMicrotask(settleScript);
	if (!owedThisScript.has(callback)) owedThisScript.set(callback, enqueueWork(callback));
}
let deliveringSizes = 0;
function sizeObserver(callback, { counted = true } = {}) {
	const pending = /* @__PURE__ */ new Map();
	let installation = null;
	const observer = new ResizeObserver((entries, observer) => {
		if (counted) {
			heard = true;
			unsettle();
		}
		deliveringSizes++;
		try {
			callback(entries, observer);
		} finally {
			deliveringSizes--;
		}
	});
	const observe = observer.observe.bind(observer);
	const unobserve = observer.unobserve.bind(observer);
	const disconnect = observer.disconnect.bind(observer);
	const install = () => {
		installation = null;
		for (const [target, options] of pending) observe(target, options);
		pending.clear();
	};
	const retireInstallation = () => {
		if (pending.size || installation === null) return;
		(counted ? cancelRender : cancelAnimation)(installation);
		installation = null;
	};
	observer.observe = (target, options) => {
		if (!deliveringSizes) {
			pending.delete(target);
			retireInstallation();
			return observe(target, options);
		}
		pending.set(target, options);
		if (installation === null) installation = (counted ? nextRender : nextAnimation)(install);
	};
	observer.unobserve = (target) => {
		pending.delete(target);
		retireInstallation();
		unobserve(target);
	};
	observer.disconnect = () => {
		pending.clear();
		retireInstallation();
		disconnect();
	};
	return observer;
}
const renderingState = () => {
	const visible = rendered();
	return {
		updatesSettled: quiet || !visible,
		preparationsSettled: preparations === 0 || !visible
	};
};
const rendered = () => !document.hidden && frameVisibility()?.visible !== false;
function unsettle() {
	quiet = false;
	if (checking) return;
	checking = true;
	requestAnimationFrame(afterUpdate);
}
let updateChecking = false;
const afterUpdate = () => {
	updateChecking = true;
	setTimeout(check);
};
function check() {
	updateChecking = false;
	if (queued.size || heard) {
		heard = false;
		requestAnimationFrame(afterUpdate);
		return;
	}
	checking = false;
	quiet = true;
	const waiting = settling;
	settling = [];
	for (const waiter of waiting) if ([...pending].some((serial) => serial > waiter.since)) settling.push(waiter);
	else waiter.settled();
}
let settling = [];
let begun = 0;
const pending = /* @__PURE__ */ new Set();
const owed = () => {};
function afterSettling(settled) {
	settling.push({
		settled,
		since: begun
	});
	nextFrame(owed);
}
onFrameVisibility((visibility) => {
	if (visibility.visible) unsettle();
});
unsettle();

//#endregion
//#region runtime/shadow-tree.js
const shadowHost = (root) => root?.nodeType === Node.DOCUMENT_FRAGMENT_NODE ? root.host ?? null : null;
const upFrom = (node) => node?.parentElement ?? shadowHost(node?.getRootNode());
const renderedParent = (node) => node?.assignedSlot ?? upFrom(node);
const composedParentNode = (node) => node.parentNode ?? shadowHost(node);
const renderedParentNode = (node) => node.assignedSlot ?? composedParentNode(node);
const under = (node, root) => {
	for (let at = node; at; at = composedParentNode(at)) if (at === root) return true;
	return false;
};
const renderedUnder = (node, root) => {
	for (let at = node; at; at = renderedParentNode(at)) if (at === root) return true;
	return false;
};
const renderedChain = (node) => {
	const chain = [];
	for (let at = node; at; at = renderedParent(at)) chain.push(at);
	return chain.reverse();
};
function renderedOrder(a, b) {
	if (a === b) return 0;
	const left = renderedChain(a);
	const right = renderedChain(b);
	let index = 0;
	while (index < left.length && index < right.length && left[index] === right[index]) index += 1;
	if (index === left.length || index === right.length) return left.length - right.length;
	return left[index].compareDocumentPosition(right[index]) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1;
}
const byRenderedOrder = (items, placeOfItem) => {
	const placed = items.map((item) => ({
		item,
		place: placeOfItem(item)
	}));
	return [...placed.filter(({ place }) => place).sort((a, b) => renderedOrder(a.place, b.place)), ...placed.filter(({ place }) => !place)].map(({ item }) => item);
};
const nativeLayerKind = (node) => {
	if (node?.nodeType !== Node.ELEMENT_NODE || !node.isConnected) return null;
	if (node.matches("dialog:modal")) return "modal";
	return node.matches(":popover-open") ? "popover" : null;
};
const isNativeLayer = (node) => nativeLayerKind(node) !== null;
function nativeLayerHolding(node) {
	for (let at = node; at; at = renderedParent(at)) if (isNativeLayer(at)) return at;
	return null;
}
function excludedByInert(node) {
	for (let owner = node; owner; owner = renderedParent(owner)) {
		if (owner.inert) return true;
		if (nativeLayerKind(owner) === "modal") break;
	}
	return false;
}

//#endregion
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
	player: "data-lf-player",
	kept: "data-lf-kept",
	mediaWidth: "data-lf-media-width",
	mediaHeight: "data-lf-media-height"
});
const pagePresented = () => document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented);
const pageUpgraded = () => document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.upgraded);

//#endregion
//#region runtime/arrivals.js
const watches = /* @__PURE__ */ new Set();
const stages = /* @__PURE__ */ new WeakSet();
const stageRefs = /* @__PURE__ */ new Set();
const owners = /* @__PURE__ */ new WeakMap();
let offerOwner;
function watchOwner(owner, lifecycle) {
	let connected = false;
	const subscription = {
		connect() {
			if (connected || !owner.isConnected) return;
			connected = true;
			try {
				lifecycle.connect?.();
			} catch (error) {
				subscriptions.delete(subscription);
				subscription.disconnect();
				throw error;
			}
		},
		disconnect() {
			if (!connected) return;
			connected = false;
			lifecycle.disconnect?.();
		}
	};
	let subscriptions = owners.get(owner);
	if (!subscriptions) owners.set(owner, subscriptions = /* @__PURE__ */ new Set());
	if (!offerOwner) {
		const notify = (element, method) => {
			for (const subscription of owners.get(element) ?? []) try {
				subscription[method]();
			} catch (error) {
				queueMicrotask(() => {
					throw error;
				});
			}
		};
		offerOwner = watchArrivals("*", [], {
			arrive: (element) => notify(element, "connect"),
			leave: (element) => notify(element, "disconnect")
		});
	}
	if (owner.isConnected) offerOwner(owner);
	subscriptions.add(subscription);
	const stop = () => {
		subscriptions.delete(subscription);
		subscription.disconnect();
	};
	subscription.connect();
	return stop;
}
function whileConnected(owner, start) {
	let held;
	return watchOwner(owner, {
		connect() {
			const controller = new AbortController();
			held = {
				controller,
				cleanup: null
			};
			held.cleanup = start(controller.signal);
		},
		disconnect() {
			const current = held;
			held = null;
			current.controller.abort();
			current.cleanup?.();
		}
	});
}
function frameFor(owner, run) {
	let frame = 0;
	watchOwner(owner, { disconnect() {
		cancelRender(frame);
		frame = 0;
	} });
	return () => {
		if (frame || !owner.isConnected) return;
		frame = nextRender(() => {
			frame = 0;
			if (owner.isConnected) run();
		});
	};
}
function liveStages() {
	const live = [];
	for (const ref of stageRefs) {
		const root = ref.deref();
		if (root) live.push(root);
		else stageRefs.delete(ref);
	}
	return live;
}
const isStage = (root) => stages.has(root);
const stands = (el) => {
	const root = el.getRootNode();
	return root === document ? document.body.contains(el) : stages.has(root) && root.host.isConnected;
};
function* matching(node, selector) {
	if (node?.nodeType !== Node.ELEMENT_NODE) return;
	if (node.matches(selector)) yield node;
	yield* node.querySelectorAll(selector);
	for (const stage of liveStages()) if (under(stage.host, node)) yield* stage.querySelectorAll(selector);
}
function watchArrivals(selector, attributes, { arrive, arriveBatch, leave }) {
	const arrived = /* @__PURE__ */ new WeakSet();
	const offerMany = (elements) => {
		const present = [];
		for (const el of elements) if (stands(el) && el.matches(selector)) present.push(el);
		else if (arrived.delete(el)) leave(el);
		if (!arriveBatch) for (const el of present) offer(el);
		else if (present.length) {
			for (const el of present) arrived.add(el);
			arriveBatch(present);
		}
	};
	const offer = (el) => {
		if (stands(el) && el.matches(selector)) {
			arrived.add(el);
			if (arriveBatch) arriveBatch([el]);
			else arrive(el);
		} else if (arrived.delete(el)) leave(el);
	};
	const beside = (node) => node?.nodeType === Node.ELEMENT_NODE && (arrived.has(node) || node.matches(selector)) ? [node] : [];
	const read = (records) => {
		const offered = /* @__PURE__ */ new Set();
		for (const record of records) {
			if (record.type === "attributes") {
				offered.add(record.target);
				continue;
			}
			for (const el of [
				...beside(record.target),
				...beside(record.previousSibling),
				...beside(record.nextSibling)
			]) offered.add(el);
			for (const node of record.addedNodes) for (const el of matching(node, selector)) offered.add(el);
			for (const node of record.removedNodes) for (const el of matching(node, selector)) if (arrived.has(el)) offered.add(el);
		}
		offerMany(offered);
	};
	const observer = new MutationObserver(read);
	const watch = {
		selector,
		attributes,
		observer,
		offerMany
	};
	watches.add(watch);
	for (const root of [document.body, ...liveStages()]) enroll(watch, root);
	return (el) => {
		read(observer.takeRecords());
		offer(el);
	};
}
function enroll({ selector, attributes, observer, offerMany }, root) {
	observer.observe(root, {
		childList: true,
		subtree: true,
		attributes: true,
		attributeFilter: attributes
	});
	offerMany(root.querySelectorAll(selector));
}
function watchArrivalsIn(stage) {
	if (stages.has(stage)) return;
	stages.add(stage);
	stageRefs.add(new WeakRef(stage));
	for (const watch of watches) enroll(watch, stage);
	stage.addEventListener("scroll", heardIn(stage), SCROLL);
}
const scrollListeners = /* @__PURE__ */ new Set();
const SCROLL = {
	capture: true,
	passive: true
};
const heardIn = (stage) => (event) => {
	if (event.target.getRootNode() !== stage) return;
	for (const listener of scrollListeners) listener(event);
};
function watchScrolls(listener) {
	scrollListeners.add(listener);
	document.addEventListener("scroll", listener, SCROLL);
	return () => {
		scrollListeners.delete(listener);
		document.removeEventListener("scroll", listener, SCROLL);
	};
}
const SETTLE_MS = 80;
const settleListeners = /* @__PURE__ */ new Set();
let inFlight = false;
let gliding = false;
let settleTimer = 0;
let trackingScrolls = false;
function settle() {
	if (!inFlight || gliding) return;
	inFlight = false;
	clearTimeout(settleTimer);
	for (const listener of settleListeners) listener();
}
function trackScrolls() {
	if (trackingScrolls) return;
	trackingScrolls = true;
	watchScrolls(() => {
		inFlight = true;
		clearTimeout(settleTimer);
		settleTimer = setTimeout(settle, SETTLE_MS);
	});
	document.addEventListener("scrollend", settle, SCROLL);
}
function scrollGlides(on) {
	trackScrolls();
	gliding = on;
	if (on) inFlight = true;
	else if (inFlight) {
		clearTimeout(settleTimer);
		settleTimer = setTimeout(settle, SETTLE_MS);
	}
}
function scrolling() {
	trackScrolls();
	return inFlight;
}
function watchScrollEnds(listener) {
	trackScrolls();
	settleListeners.add(listener);
	return () => settleListeners.delete(listener);
}

//#endregion
//#region runtime/shown-box.js
const skipped = (el) => document.documentElement.lfInitial?.skipped(el, renderedParent) ?? false;
function elementBox(el) {
	const r = el.getBoundingClientRect();
	if (r.width || r.height || skipped(el) || getComputedStyle(el).display !== "contents") return r;
	const contents = document.createRange();
	contents.selectNodeContents(el);
	return contents.getBoundingClientRect();
}
const measurements = /* @__PURE__ */ new WeakMap();
const drawn = (el) => {
	const box = elementBox(el);
	return Boolean(box.width || box.height);
};
const unmeasured = sizeObserver((entries) => {
	const taking = [];
	for (const { target } of entries) {
		if (!drawn(target)) continue;
		unmeasured.unobserve(target);
		taking.push(measurements.get(target));
		measurements.delete(target);
	}
	for (const take of taking) take();
});
function measure(el, take) {
	if (drawn(el)) {
		if (measurements.delete(el)) unmeasured.unobserve(el);
		return take();
	}
	measurements.set(el, take);
	unmeasured.observe(el);
}

//#endregion
//#region runtime/widget-upgrade.js
const initialized = /* @__PURE__ */ new WeakSet();
function once(el) {
	if (initialized.has(el)) return false;
	initialized.add(el);
	if (!el.hasAttribute(PAGE_PAINT_ATTRIBUTE.done)) el.setAttribute(PAGE_PAINT_ATTRIBUTE.done, "1");
	return true;
}
const dataBody = (el) => el.querySelector(":scope > pre").textContent;
const bodyText = (el) => dataBody(el).replace(/^\n+/, "").trimEnd();
const PENDING_TASK = "pending-task";
var PendingTaskEvent = class extends Event {
	constructor(complete) {
		super(PENDING_TASK, {
			bubbles: true,
			composed: true
		});
		this.complete = complete;
	}
};
function failSoft(el, err, source) {
	reportFailure(el, err);
	showFailure(el, `<${widgetOf(el).localName}> failed: ${err?.message || err}`, source);
}
function reportFailure(el, err) {
	el.dispatchEvent(new ErrorEvent("error", {
		error: err,
		message: err?.message ?? String(err),
		bubbles: true,
		composed: true
	}));
}
function failureContext(el) {
	const owner = widgetOf(el);
	return `<${owner.localName}${owner.id ? ` id="${owner.id}"` : ""}> failed`;
}
function failSoftUnreported(el, err) {
	showFailure(el, `<${widgetOf(el).localName}> failed: ${err?.message || err}`);
}
const widgetOf = (el) => {
	let owner = el;
	while (owner.parentElement && !owner.localName.includes("-")) owner = owner.parentElement;
	return owner.localName.includes("-") ? owner : el;
};
const placers = /* @__PURE__ */ new WeakMap();
const placesFailure = (el, place) => placers.set(el, [...placers.get(el) ?? [], place]);
function showFailure(el, text, source) {
	const box = document.createElement("div");
	box.className = "lf-error";
	box.textContent = text;
	if (source) {
		const pre = document.createElement("pre");
		pre.textContent = source;
		box.append(pre);
	}
	if (placers.get(el)?.some((place) => place(box))) return;
	releaseTemplate(el);
	el.replaceChildren(box);
}
function releaseTemplate(el) {
	const part = el._$litPart$;
	if (!part) return;
	part.setConnected(false);
	delete el._$litPart$;
}

//#endregion
//#region runtime/base-layer.js
const inBaseLayer = (text) => `@layer lf-base {\n${text}\n}`;

//#endregion
export { PAGE_PAINT_ATTRIBUTE, PENDING_TASK, PendingTaskEvent, afterScript, afterSettling, bindQueuedWork, bodyText, byRenderedOrder, cancelAnimation, cancelRender, composedParentNode, dataBody, elementBox, excludedByInert, failSoft, failSoftUnreported, failureContext, frameFor, frameVisibility, holdRendering, inBaseLayer, isNativeLayer, isStage, liveStages, measure, nativeLayerHolding, nativeLayerKind, nextAnimation, nextFrame, nextRender, observePreparations, observeQueuedWork, onFrameVisibility, once, pagePresented, pageUpgraded, placesFailure, readSampleVisibility, renderedOrder, renderedParent, renderedUnder, renderingState, reportFailure, scrollGlides, scrolling, shadowHost, sizeObserver, skipped, under, upFrom, watchArrivals, watchArrivalsIn, watchFrame, watchOwner, watchScrollEnds, watchScrolls, whileConnected };