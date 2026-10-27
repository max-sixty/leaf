import { Z, cancelWork, enqueueWork, runWork } from "./bundle-signals-core.js";

//#region runtime/frame-visibility.js
const child = document.documentElement.lfSample;
let admitted = false;
const observers = /* @__PURE__ */ new Set();
const readings$1 = /* @__PURE__ */ new Map();
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
const owners = [];
if (!child) for (let view = window; view.frameElement; view = view.parent) owners.push(watchFrame(view.frameElement, publish$1));
function frameVisibility() {
	if (child) return { visible: admitted };
	if (owners.length) return { visible: owners.every((owner) => owner.shown()) };
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
		readings$1.set(id, {
			resolve,
			reject
		});
		child.send({
			type: "visibility-read",
			detail: { id }
		});
	});
}
function publish$1() {
	const visibility = frameVisibility();
	for (const callback of observers) callback(visibility);
}
if (child) child.receive(({ type, detail }) => {
	if (type === "visibility-reading") {
		const reading = readings$1.get(detail.id);
		readings$1.delete(detail.id);
		if (detail.error) reading?.reject(Object.assign(new Error(detail.error.message), { stack: void 0 }, detail.error));
		else reading?.resolve(detail);
		return;
	}
	if (type !== "visibility") return;
	admitted = detail.visible;
	publish$1();
});
addEventListener("pagehide", (event) => {
	if (!event.persisted) for (const owner of owners) owner.stop();
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
//#region runtime/keeps.js
const keeps = (...args) => document.documentElement.lfInitial.keepsAttribute(...args);
function keepsHidden(node, hidden) {
	if (node && node.hidden !== hidden) node.hidden = hidden;
}
function keepsText(node, text) {
	const said = String(text ?? "");
	if (node && node.textContent !== said) node.textContent = said;
}
const atLayoutPrecision = (length) => Math.round(length * 64) / 64;
const layoutPx = (length) => `${atLayoutPrecision(length)}px`;
const roomPx = (length) => `${Math.floor(length * 64) / 64}px`;

//#endregion
//#region runtime/control-selectors.js
const TEXT_FIELD = document.documentElement.lfInputs.textField;
const MODIFIER_KEYS = [
	"Shift",
	"Alt",
	"Control",
	"Meta"
];
const CARET_KEYS = [
	"ArrowLeft",
	"ArrowRight",
	"ArrowUp",
	"ArrowDown",
	"Home",
	"End",
	"PageUp",
	"PageDown"
];
const selectsAll = (event) => event.key.toLowerCase() === "a" && (event.metaKey || event.ctrlKey);
const TEXT_BOX = document.documentElement.lfInputs.textBox;
const TAB_STOP = `a[href], button, input, select, ${TEXT_BOX}, summary, [contenteditable]:not([contenteditable="false"]), [tabindex]:not([tabindex="-1"])`;
const PRESS_SELECTORS = [
	"a[href]",
	"audio[controls]",
	"button",
	"img[usemap]",
	"input:not([type='hidden'])",
	"label",
	"select",
	"summary",
	TEXT_BOX,
	"video[controls]",
	"video[data-lf-player]",
	"[role='button']",
	"[role='checkbox']",
	"[role='combobox']",
	"[role='link']",
	"[role='menuitem']",
	"[role='menuitemcheckbox']",
	"[role='menuitemradio']",
	"[role='option']",
	"[role='radio']",
	"[role='scrollbar']",
	"[role='searchbox']",
	"[role='separator'][tabindex]",
	"[role='slider']",
	"[role='spinbutton']",
	"[role='switch']",
	"[role='tab']",
	"[role='textbox']",
	"[role='treeitem']"
];
const LENT_REACH_STOP = "data-lf-lent-reach-stop";
const REGION_SELECTORS = [
	`[tabindex]:not([tabindex='-1']):not([${LENT_REACH_STOP}]):not([role='tabpanel'])`,
	"[contenteditable]:not([contenteditable='false'])",
	"[draggable='true']",
	"[role='application']",
	"[role='grid']",
	"[role='gridcell']",
	"[role='listbox']",
	"[role='menu']",
	"[role='menubar']",
	"[role='radiogroup']",
	"[role='tablist']",
	"[role='tree']",
	"[role='treegrid']"
];
const PRESSES = PRESS_SELECTORS.join(",");
const WORKS = [...PRESS_SELECTORS, ...REGION_SELECTORS].join(",");

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
//#region runtime/focus.js
function* renderedElements(node) {
	const children = node.localName === "slot" ? node.assignedElements({ flatten: true }) : (node.shadowRoot ?? node).children;
	for (const child of children) {
		yield child;
		if (child.shadowRoot && parseInt(child.getAttribute("tabindex")) < 0) continue;
		yield* renderedElements(child);
	}
}
const SEQUENTIAL = `${TAB_STOP}, iframe, audio[controls], video[controls]`;
const tabStops = (root) => [...renderedElements(root)].filter((node) => node.matches(SEQUENTIAL) && node.tabIndex >= 0 && !node.shadowRoot?.delegatesFocus && !node.matches(":disabled") && !node.inert && node.checkVisibility({ visibilityProperty: true }));
const canPlaceFocus = () => window === window.top || document.hasFocus();
const CAUSES = /* @__PURE__ */ new Set([
	"move",
	"step",
	"return",
	"press"
]);
function focusDestination(destination, cause, { caret = null, ...unknown } = {}) {
	if (!CAUSES.has(cause)) throw new TypeError(`focusDestination: no cause ${cause}`);
	const unexpected = Object.keys(unknown);
	if (unexpected.length) throw new TypeError(`focusDestination: unknown options ${unexpected.join(", ")}`);
	if (!canPlaceFocus()) return;
	const options = {
		preventScroll: true,
		focusVisible: pressLed() ? void 0 : true
	};
	placed(cause, () => {
		destination.focus(options);
		if (!landedOn(destination) && lendable(destination)) lendStop(destination, options);
	});
	if (caret && holdsCaret(destination)) destination.setSelectionRange(...caret);
}
let placing = null;
const placed = (cause, move) => {
	const was = placing;
	placing ??= cause;
	try {
		return move();
	} finally {
		placing = was;
	}
};
const landedOn = (node) => node === document.body ? node.matches(":focus") : node.getRootNode().activeElement === node || Boolean(node.shadowRoot?.activeElement);
const lendable = (node) => drawn(node) && !node.matches(TAB_STOP);
const lent = /* @__PURE__ */ new WeakSet();
const wearsLentStop = (element) => lent.has(element);
function whenLeft(element, leave) {
	const blur = () => {
		if (element.getRootNode().activeElement === element) return;
		element.removeEventListener("blur", blur);
		leave();
	};
	element.addEventListener("blur", blur);
}
function lendStop(destination, options) {
	if (destination.hasAttribute("tabindex")) return;
	const giveBack = () => {
		lent.delete(destination);
		if (destination.getAttribute("tabindex") === "-1") destination.removeAttribute("tabindex");
	};
	lent.add(destination);
	destination.tabIndex = -1;
	destination.focus(options);
	if (!landedOn(destination)) {
		giveBack();
		return;
	}
	whenLeft(destination, giveBack);
}
const CARETED = /* @__PURE__ */ new Set([
	"text",
	"search",
	"url",
	"tel",
	"password"
]);
const holdsCaret = (node) => node.matches(TEXT_BOX) || node.tagName === "INPUT" && CARETED.has(node.type);
function readCaret(node) {
	if (!node || !holdsCaret(node) || node.selectionStart === null) return null;
	return [
		node.selectionStart,
		node.selectionEnd,
		node.selectionDirection
	];
}
const deepFocus = (at = document.activeElement) => {
	while (at?.shadowRoot?.activeElement) at = at.shadowRoot.activeElement;
	return at;
};
let labelPress = null;
const heldByLabel = () => labelPress?.held.isConnected ? labelPress.held : null;
function finishLabelPress() {
	const press = labelPress;
	if (!press) return null;
	labelPress = null;
	return press;
}
function landLabelPress() {
	if (!finishLabelPress()) return;
	setTimeout(() => {
		if (labelPress) return;
		const at = deepFocus();
		if (at && at !== document.body) return reconcile(null, pressedPath);
		if (!drawn(published?.deref())) return;
		placements += 1;
		lastLocation = null;
		publish(null, cause(null));
	});
}
const currentLocation = Z(0);
const focusRevision = () => currentLocation.value;
const focused = (tree = null) => {
	let at = heldByLabel() ?? deepFocus();
	if (tree) while (at && at.getRootNode() !== tree) at = shadowHost(at.getRootNode());
	return at;
};
const selectionOf = (node) => {
	const root = node.getRootNode();
	const own = root;
	return root instanceof ShadowRoot && own.getSelection?.() || getSelection();
};
function currentLocationNodes() {
	const at = focused();
	const selection = getSelection();
	return [
		at && at !== document.body ? at : null,
		selection?.focusNode ?? null,
		selection?.anchorNode ?? null
	].filter(Boolean);
}
function currentLocationTouches(node) {
	if (!node) return false;
	if (currentLocationNodes().some((at) => at === node || node.contains(at))) return true;
	const selection = selectionOf(node);
	return Boolean(selection?.rangeCount && selection.getRangeAt(0).intersectsNode(node));
}
let restoring = false;
let placements = 0;
let lastLocation = null;
const readers = /* @__PURE__ */ new Set();
const onCurrentLocation = (read) => {
	readers.add(read);
	return () => readers.delete(read);
};
let published = null;
let departed = false;
let readings = 0;
let paintDestination = null;
let paintedFocus = null;
let paintedWithin = /* @__PURE__ */ new Set();
let paintedVisible = null;
let paintedVisibleWithin = /* @__PURE__ */ new Set();
const visibilityReaders = /* @__PURE__ */ new Set();
const onFocusVisibility = (read) => {
	visibilityReaders.add(read);
	return () => visibilityReaders.delete(read);
};
function markFocus(node, name, present) {
	keeps(node, `data-lf-${name}`, present ? "" : null);
	if (!present) {
		if (node.part?.contains(`lf-${name}`)) node.part.remove(`lf-${name}`);
	} else if (node.getRootNode().nodeType === Node.DOCUMENT_FRAGMENT_NODE && node.hasAttribute("part")) node.part.add(`lf-${name}`);
}
function visibleFocus(node = focused()) {
	return node && node !== document.body && node !== document.documentElement && (node.matches(":focus-visible") || node.matches(TEXT_BOX) || node.localName === "iframe" && !pressLed()) ? node : null;
}
function paintFocus(node) {
	const next = node === document.body || node === document.documentElement ? null : node;
	if (next !== paintedFocus) {
		if (paintedFocus) markFocus(paintedFocus, "focus", false);
		if (next) markFocus(next, "focus", true);
		paintedFocus = next;
	}
	const within = /* @__PURE__ */ new Set();
	for (let owner = next; owner && owner !== document.body && owner !== document.documentElement; owner = renderedParent(owner)) within.add(owner);
	for (const owner of paintedWithin) if (!within.has(owner)) markFocus(owner, "focus-within", false);
	for (const owner of within) if (!paintedWithin.has(owner)) markFocus(owner, "focus-within", true);
	paintedWithin = within;
	const visible = visibleFocus(next);
	if (visible !== paintedVisible) {
		if (paintedVisible) markFocus(paintedVisible, "focus-visible", false);
		if (visible) markFocus(visible, "focus-visible", true);
		paintedVisible = visible;
		for (const read of visibilityReaders) read();
	}
	const visibleWithin = visible ? within : /* @__PURE__ */ new Set();
	for (const owner of paintedVisibleWithin) if (!visibleWithin.has(owner)) markFocus(owner, "focus-visible-within", false);
	for (const owner of visibleWithin) if (!paintedVisibleWithin.has(owner)) markFocus(owner, "focus-visible-within", true);
	paintedVisibleWithin = visibleWithin;
}
const refreshFocusPaint = () => {
	const node = paintDestination?.deref();
	if (node?.isConnected && node !== deepFocus() && node !== heldByLabel()) return;
	if (node?.isConnected) watchCurrentLocationAround(node);
	paintFocus(node?.isConnected ? node : null);
};
let returnPaintPending = false;
const paintAfterScript = () => {
	if (!returnPaintPending) refreshFocusPaint();
};
const queueFocusPaint = () => afterScript(paintAfterScript);
const queueReturnFocusPaint = () => {
	if (returnPaintPending) return;
	returnPaintPending = true;
	nextRender(() => {
		if (!returnPaintPending) return;
		returnPaintPending = false;
		refreshFocusPaint();
	});
};
const paintRoots = /* @__PURE__ */ new WeakSet();
function watchFocusPaintIn(root) {
	if (paintRoots.has(root)) return;
	paintRoots.add(root);
	new MutationObserver(queueFocusPaint).observe(root, {
		childList: true,
		subtree: true
	});
	root.addEventListener("slotchange", queueFocusPaint);
}
function publish(node, cause) {
	watchCurrentLocationAround(node);
	paintDestination = node && new WeakRef(node);
	if (cause === "return") queueReturnFocusPaint();
	else {
		returnPaintPending = false;
		queueFocusPaint();
	}
	if (node === (published?.deref() ?? null) && !departed) return;
	departed = false;
	const left = published?.deref() ?? null;
	const reading = ++readings;
	currentLocation.value = reading;
	if (cause === "drop") departed = true;
	else published = node && new WeakRef(node);
	if (node) placeInput = "focus";
	const was = [placing, restoring];
	[placing, restoring] = [null, false];
	try {
		for (const read of readers) {
			try {
				read(node, cause, left);
			} catch (error) {
				reportError(error);
			}
			if (readings !== reading) return;
		}
	} finally {
		[placing, restoring] = was;
	}
}
let pressedPath = null;
const pressedOn = (node) => Boolean(pressedPath) && pressedPath.some((ref) => {
	const at = ref.deref();
	return at === node || at?.localName === "label" && at.control === node;
});
const pressLed = () => pressedPath !== null;
let stepping = null;
const leftClosedLayer = (left) => {
	const layer = left?.closest?.("dialog, [popover]");
	return Boolean(layer) && !(layer.open === true || isNativeLayer(layer));
};
const cause = (node, left = null) => placing ?? (leftClosedLayer(left) ? "return" : pressedOn(node) ? "press" : stepping ? "step" : "move");
const read = /* @__PURE__ */ new WeakSet();
function readFocusEvent(event) {
	if (read.has(event)) return;
	read.add(event);
	if (closing) return;
	if (heldByLabel()) {
		if (placing === null) return;
		finishLabelPress();
	}
	if (!restoring && !(placing === null && leftClosedLayer(event.relatedTarget))) placements += 1;
	const at = deepFocus();
	lastLocation = at && new WeakRef(at);
	publish(at, cause(at, event.relatedTarget));
}
function watchCurrentLocationAround(node) {
	for (let at = node; at; at = renderedParent(at)) watchCurrentLocationIn(at.getRootNode());
}
function enter(event) {
	if (read.has(event)) return;
	read.add(event);
	watchCurrentLocationAround(deepFocus());
}
function watchCurrentLocationIn(root) {
	root.addEventListener("focus", enter, true);
	root.addEventListener("focusin", readFocusEvent, true);
	watchFocusPaintIn(root);
}
watchCurrentLocationIn(document);
watchCurrentLocationAround(deepFocus());
document.addEventListener("focusout", (event) => {
	if (event.relatedTarget !== null) {
		departed = true;
		return;
	}
	const left = event.composedPath()[0];
	lastLocation = new WeakRef(left);
	if (restoring) return;
	queueMicrotask(() => {
		const at = document.activeElement;
		if (at !== null && at !== document.body) return;
		if (heldByLabel()) return;
		if (!drawn(left)) return publish(null, "drop");
		if (left !== document.body) placements += 1;
		if (lastLocation?.deref() === left) lastLocation = null;
		publish(null, cause(null));
	});
}, true);
const sequential = (event) => event.key === "Tab" && !event.altKey && !event.ctrlKey && !event.metaKey;
function reconcile(step, pressed) {
	if (heldByLabel()) return;
	const deep = deepFocus();
	const at = deep === document.body ? null : deep;
	const was = published?.deref() ?? null;
	if (at === was || !at && was?.localName !== "iframe") return;
	placements += 1;
	lastLocation = at && new WeakRef(at);
	const input = [stepping, pressedPath];
	[stepping, pressedPath] = [step, pressed];
	try {
		publish(at, cause(at));
	} finally {
		[stepping, pressedPath] = input;
	}
}
function inputInFrame(frame, type) {
	if (deepFocus() !== frame) return;
	if (type === "keydown") pressedPath = null;
	else if (type === "pointerdown" || type === "touchstart") pressedPath = [new WeakRef(frame)];
	if (published?.deref() === frame) queueFocusPaint();
	else reconcile(null, pressedPath);
}
addEventListener("click", () => {
	const pressed = pressedPath;
	setTimeout(() => {
		reconcile(null, pressed);
		queueFocusPaint();
	});
}, {
	capture: true,
	passive: true
});
const inputs = document.documentElement.lfInputs;
const inputCount = () => inputs.count;
const onUserInput = (read) => inputs.observe(read);
let keyCarets = null;
onUserInput((event) => {
	if (event.type !== "keydown") return;
	const carets = /* @__PURE__ */ new Map();
	for (const node of event.composedPath()) {
		const caret = node instanceof Element && readCaret(node);
		if (caret) carets.set(node, caret);
	}
	keyCarets = carets;
	setTimeout(() => {
		if (keyCarets === carets) keyCarets = null;
	});
});
const caretAtKey = (node) => keyCarets?.get(node) ?? null;
onUserInput((event) => {
	if (event.type !== "blur") return;
	landLabelPress();
	endPress(event, false);
});
let placeInput = "focus";
for (const type of [
	"pointermove",
	"pointerdown",
	"wheel"
]) addEventListener(type, () => placeInput = "pointer", {
	capture: true,
	passive: true
});
addEventListener("click", (event) => {
	if (event.isTrusted && event.button === 0) placeInput = focused()?.contains(event.composedPath()[0]) ? "focus" : "pointer";
}, {
	capture: true,
	passive: true
});
const recentPlaceInput = () => placeInput;
let press = null;
const pressing = () => press;
const pressReaders = /* @__PURE__ */ new Set();
const onPress = (read) => {
	pressReaders.add(read);
	return () => pressReaders.delete(read);
};
const onPressAway = (away, dismiss) => onPress((start, from) => start.button === 0 && away(from) ? (end, completed) => {
	const path = end.composedPath();
	if (completed && away(path)) dismiss(path, from);
} : null);
addEventListener("pointerdown", (event) => {
	if (!event.isPrimary) return;
	const path = event.composedPath();
	const ends = [];
	press = {
		pointerId: event.pointerId,
		path,
		ends
	};
	for (const read of pressReaders) {
		const end = read(event, path);
		if (end) ends.push(end);
	}
	if (event.button !== 0 || labelPress) return;
	const label = path.find((node) => node?.localName === "label" && node.control);
	const held = label && deepFocus();
	if (!held || held === document.body) return;
	labelPress = {
		held,
		pointerId: event.pointerId,
		label
	};
}, {
	capture: true,
	passive: true
});
function endPress(event, completed) {
	if (!press) return;
	const { ends } = press;
	press = null;
	for (const end of ends) end(event, completed);
}
for (const type of ["pointerup", "pointercancel"]) addEventListener(type, (event) => {
	if (event.pointerId === labelPress?.pointerId && (type === "pointercancel" || !event.composedPath().includes(labelPress.label))) landLabelPress();
	if (event.pointerId === press?.pointerId) endPress(event, type === "pointerup");
}, {
	capture: true,
	passive: true
});
addEventListener("contextmenu", (event) => {
	landLabelPress();
	endPress(event, false);
}, {
	capture: true,
	passive: true
});
addEventListener("click", landLabelPress, {
	capture: true,
	passive: true
});
const recoveredLabelKeys = /* @__PURE__ */ new WeakMap();
const recoveredLabelFocus = (event) => recoveredLabelKeys.get(event);
addEventListener("keydown", (event) => {
	placeInput = "focus";
	if (!labelPress || event.isComposing || MODIFIER_KEYS.includes(event.key)) return;
	const active = deepFocus();
	const { held } = finishLabelPress();
	if (active === held || !held.isConnected) return;
	focusDestination(held, "return");
	if (deepFocus() === held) recoveredLabelKeys.set(event, held);
}, true);
for (const type of [
	"keydown",
	"pointerdown",
	"wheel",
	"touchstart"
]) addEventListener(type, (event) => {
	if (type === "pointerdown") pressedPath = event.composedPath().map((node) => new WeakRef(node));
	else if (type === "keydown") pressedPath = null;
	stepping = null;
	if (type === "keydown" || type === "pointerdown") {
		const step = type === "keydown" && sequential(event) ? event : null;
		const pressed = pressedPath;
		stepping = step;
		setTimeout(() => {
			if (step && stepping === step) stepping = null;
			reconcile(step, pressed);
			queueFocusPaint();
		});
	}
	const at = deepFocus();
	if (at && at !== document.body || heldByLabel()) return;
	lastLocation = null;
	publish(null, cause(null));
}, {
	capture: true,
	passive: true
});
function ringBox(node) {
	if (!node?.matches?.(":focus, [data-lf-focus]")) return node;
	for (let box = renderedParent(node); box instanceof Element; box = renderedParent(box)) if (getComputedStyle(box).getPropertyValue("--lf-wears-ring") === "1") return box;
	return node;
}
const drawn = (node) => node?.isConnected && !excludedByInert(node) && node.checkVisibility({ visibilityProperty: true });
const dropped = () => {
	const at = deepFocus();
	if (at && at !== document.body) return null;
	const node = lastLocation?.deref();
	return node && !drawn(node) ? node : null;
};
function holdFocus(scope, { key = null } = {}) {
	const node = heldIn(scope);
	if (!node) return null;
	const restore = holdOn(node);
	if (!key) return restore;
	let item = node;
	while (item && !item.matches?.(`[${key}]`)) item = renderedParent(item);
	if (!item || item === scope || !renderedUnder(item, scope)) return restore;
	const tree = item.getRootNode() === scope.getRootNode() ? scope : item.getRootNode();
	const items = () => [...tree.querySelectorAll(`[${key}]`)].filter((item) => renderedUnder(item, scope));
	const keys = [...new Set(items().map((each) => each.getAttribute(key)))];
	const at = keys.indexOf(item.getAttribute(key));
	const order = [
		keys[at],
		...keys.slice(at + 1),
		...keys.slice(0, at).reverse()
	];
	let control = node;
	while (control.getRootNode() !== item.getRootNode()) {
		const host = shadowHost(control.getRootNode());
		if (!host) break;
		control = host;
	}
	const like = control.localName + [...control.classList].map((name) => `.${CSS.escape(name)}`).join("");
	const [same, ...rest] = order;
	return (...standIns) => {
		let byKey = null;
		const keyed = (value) => {
			if (!byKey) {
				byKey = /* @__PURE__ */ new Map();
				for (const each of items()) {
					const at = each.getAttribute(key);
					if (!byKey.has(at)) byKey.set(at, []);
					byKey.get(at).push(each);
				}
			}
			return byKey.get(value) ?? [];
		};
		const matching = (root) => {
			if (root.matches(like) && drawn(root)) return root;
			const assigned = root.localName === "slot" ? root.assignedElements({ flatten: true }) : [];
			for (const child of assigned.length ? assigned : root.children) {
				const found = matching(child);
				if (found) return found;
			}
			return null;
		};
		const find = (value) => {
			const found = keyed(value).filter(drawn);
			return (like && found.find((each) => each.matches(like))) ?? (like && found.map(matching).find(Boolean)) ?? found[0] ?? null;
		};
		const neighbour = (value) => () => {
			const place = find(value);
			if (!place || !drawn(place)) return null;
			focusDestination(place, "return");
			return landedOn(place);
		};
		return restore(() => find(same), ...rest.map(neighbour), ...standIns);
	};
}
const heldIn = (scope) => {
	const held = heldByLabel();
	if (held) return renderedUnder(held, scope) ? held : null;
	const currentLocation = deepFocus(scope.getRootNode().activeElement ?? scope.ownerDocument.activeElement);
	if (currentLocation && currentLocation !== document.body && renderedUnder(currentLocation, scope)) return currentLocation;
	const node = lastLocation?.deref();
	return node && renderedUnder(node, scope) ? dropped() : null;
};
const currentLocationIn = (scope) => {
	const at = focused();
	return Boolean(at) && at !== document.body && renderedUnder(at, scope);
};
function rove(items, stop) {
	for (const item of items) keeps(item, "tabindex", item === stop ? 0 : -1);
}
const openers = /* @__PURE__ */ new WeakMap();
function openLayer(layer, opener = focused()) {
	openers.set(layer, opener && opener !== document.body ? opener : null);
}
const openerOf = (layer) => openers.get(layer) ?? null;
let closing = 0;
let deferredLanding = null;
let landingLayer = false;
function layerLanding(land) {
	return (...args) => {
		if (!landingLayer) throw new Error("A layer's landing runs only as the layer closes");
		return land(...args);
	};
}
function closeLayer(close, land = null) {
	closing += 1;
	let deferred = null;
	const landingAround = landingLayer;
	landingLayer = false;
	try {
		close();
	} finally {
		landingLayer = landingAround;
		closing -= 1;
		if (!closing) [deferred, deferredLanding] = [deferredLanding, null];
	}
	if (closing) {
		if (land) deferredLanding ??= land;
		return;
	}
	const landing = land || deferred;
	if (landing) {
		const outer = landingLayer;
		landingLayer = true;
		try {
			landing();
		} finally {
			landingLayer = outer;
		}
	}
	const at = deepFocus();
	if (!at || at === document.body || at === published?.deref()) return;
	lastLocation = new WeakRef(at);
	publish(at, "return");
}
function holdCurrentLocation() {
	const at = focused();
	const node = at && at !== document.body ? at : dropped();
	return node ? {
		node,
		restore: holdOn(node)
	} : null;
}
const carried = /* @__PURE__ */ new WeakMap();
const carriedFrom = (node) => carried.get(node) ?? null;
function holdOn(held) {
	const caret = readCaret(held);
	const began = placements;
	return (...standIns) => {
		if (placements !== began) return false;
		for (const standIn of [held, ...standIns]) {
			if (placements !== began) return false;
			const place = typeof standIn === "function" ? standIn() : standIn;
			if (place?.then) return place.then((destination) => {
				if (!(destination instanceof Element) || !drawn(destination) || deepFocus() !== destination) return false;
				return land(() => {
					focusDestination(destination, "return", { caret });
					return landedOn(destination);
				});
			});
			if (place === true) return true;
			if (!(place instanceof Element) || !drawn(place)) continue;
			if (place === held && deepFocus() === held) return true;
			if (land(() => {
				focusDestination(place, "return", { caret });
				return landedOn(place);
			})) {
				const before = carriedFrom(held);
				if (place !== held) carried.set(place, before?.inputs === inputCount() ? before : {
					from: held,
					inputs: inputCount()
				});
				return true;
			}
		}
		return false;
	};
}
const land = (landing) => {
	const was = restoring;
	restoring = true;
	try {
		return landing();
	} finally {
		restoring = was;
	}
};
const typesText = inputs.typesText;
const takesLetters = inputs.takesLetters;
function controlNavigationKeys(node) {
	if (node?.matches("input[type=\"radio\"], [role=\"radio\"]")) return [
		"ArrowLeft",
		"ArrowRight",
		"ArrowUp",
		"ArrowDown"
	];
	if (node?.matches("input[type=\"range\"], [role=\"slider\"]")) return [
		"ArrowLeft",
		"ArrowRight",
		"ArrowUp",
		"ArrowDown",
		"Home",
		"End",
		"PageUp",
		"PageDown"
	];
	return [];
}
let readingBlock = () => null;
function declareReading(read) {
	readingBlock = read;
}
function releaseFocus() {
	focusDestination(document.body, "move");
	document.body.blur();
}
let released = () => {};
function declareRelease(release) {
	released = release;
}
let letGoes = 0;
function release() {
	const before = letGoes;
	released();
	if (letGoes === before) letGo();
}
const letGoReaders = /* @__PURE__ */ new Set();
const onLetGo = (read) => {
	letGoReaders.add(read);
	return () => letGoReaders.delete(read);
};
function letGo() {
	letGoes++;
	const from = focused();
	const block = readingBlock(from);
	if (!block?.isConnected) releaseFocus();
	else {
		focusDestination(block, "move");
		block.blur();
	}
	if (from && from !== document.body) for (const read of letGoReaders) read(from);
}
function handBack(...destinations) {
	const places = destinations.filter((node) => node && node !== document.body);
	const landed = () => {
		const at = placements;
		return places.some((node) => {
			if (placements !== at) return true;
			if (!drawn(node)) return false;
			focusDestination(node, "return");
			return landedOn(node);
		});
	};
	if (landed()) return;
	if (!places.some((node) => node.isConnected)) {
		letGo();
		return;
	}
	const yielded = !drawn(deepFocus());
	if (yielded) releaseFocus();
	const began = placements;
	const pendingInput = inputCount();
	nextRender(() => {
		if (inputCount() !== pendingInput || placements !== began || yielded && deepFocus() !== document.body || landed()) return;
		letGo();
	});
}

//#endregion
//#region runtime/dom-move.js
function move(parent, node, before) {
	if (node.parentNode === parent && (before === node || node.nextSibling === before)) return node;
	if (parent.isConnected) watchCurrentLocationIn(parent.getRootNode());
	if (parent.moveBefore && node.getRootNode({ composed: true }) === parent.getRootNode({ composed: true })) parent.moveBefore(node, before);
	else {
		const restore = node.nodeType === Node.ELEMENT_NODE ? holdFocus(node) : null;
		parent.insertBefore(node, before);
		restore?.();
	}
	return node;
}
document.documentElement.lfInitial.move = move;

//#endregion
export { CARET_KEYS, LENT_REACH_STOP, MODIFIER_KEYS, PRESSES, TAB_STOP, TEXT_BOX, TEXT_FIELD, WORKS, afterScript, afterSettling, atLayoutPrecision, byRenderedOrder, canPlaceFocus, cancelAnimation, cancelRender, caretAtKey, carriedFrom, closeLayer, composedParentNode, controlNavigationKeys, currentLocationIn, currentLocationNodes, currentLocationTouches, declareReading, declareRelease, deepFocus, drawn, excludedByInert, focusDestination, focusRevision, focused, frameVisibility, handBack, holdCurrentLocation, holdFocus, holdRendering, inputCount, inputInFrame, isNativeLayer, keeps, keepsHidden, keepsText, layerLanding, layoutPx, letGo, move, nativeLayerHolding, nativeLayerKind, nextAnimation, nextFrame, nextRender, observePreparations, onCurrentLocation, onFocusVisibility, onFrameVisibility, onLetGo, onPress, onPressAway, onUserInput, openLayer, openerOf, pressLed, pressing, readCaret, readSampleVisibility, recentPlaceInput, recoveredLabelFocus, release, releaseFocus, renderedOrder, renderedParent, renderedUnder, renderingState, ringBox, roomPx, rove, selectsAll, shadowHost, sizeObserver, tabStops, takesLetters, typesText, under, upFrom, visibleFocus, watchCurrentLocationIn, watchFrame, wearsLentStop, whenLeft };