import { canPlaceFocus, cancelRender, closeLayer, excludedByInert, focused, handBack, isNativeLayer, move, nativeLayerHolding, nativeLayerKind, nextRender, releaseFocus, renderedParent, renderedUnder, shadowHost, sizeObserver, under, upFrom } from "./bundle-dom-move.js";
import { isElementName, runtime } from "./bundle-context.js";

//#region runtime/arrivals.js
const watches$1 = /* @__PURE__ */ new Set();
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
	watches$1.add(watch);
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
	for (const watch of watches$1) enroll(watch, stage);
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
//#region runtime/registry.js
const registry = runtime.registry;
const tokenEntry = (name) => registry.$reactions.tokens[name];
const elementDeclarations = () => Object.entries(registry).filter(([tag]) => isElementName(tag));
function adoptRegistry(declarations) {
	for (const [name, value] of Object.entries(declarations)) if (name.startsWith("$")) freeze(value);
	Object.assign(registry, declarations);
}
function freeze(value) {
	if (value === null || typeof value !== "object" || Object.isFrozen(value)) return;
	for (const child of Object.values(value)) freeze(child);
	Object.freeze(value);
}
let stateIndex;
const recordSlot = (record) => JSON.stringify([record.kind, "attr" in record ? record.attr : null]);
function indexedState() {
	const generation = registry.$layer?.generation;
	if (typeof generation !== "string" || !generation) throw new Error("leaf: state vocabulary requested before registry loaded");
	if (stateIndex?.generation === generation) return stateIndex;
	const specs = [];
	for (const [tag, entry] of elementDeclarations()) for (const [verb, spec] of Object.entries(entry["x-state"] ?? {})) specs.push({
		tag,
		verb,
		spec
	});
	const recordTags = /* @__PURE__ */ new Map();
	for (const { tag, spec } of specs) {
		if (!spec.record) continue;
		const slot = recordSlot(spec.record);
		const tags = recordTags.get(slot) ?? /* @__PURE__ */ new Set();
		tags.add(tag);
		recordTags.set(slot, tags);
	}
	stateIndex = {
		generation,
		recordSelectors: new Map([...recordTags].map(([slot, tags]) => [slot, [...tags].join(",")])),
		specs
	};
	return stateIndex;
}
const stateSpecs = () => indexedState().specs;
const recordedWidgetSelector = (record) => indexedState().recordSelectors.get(recordSlot(record)) ?? "";
const layerFact = (name) => registry[name];
const declarationFor = (el, key) => registry[el?.localName]?.[key];
const decisionFor = (tag) => registry.$decisions[tag] ?? null;
const elementsDeclaring = (root, key, { direct = false } = {}) => {
	return (direct ? [...root.children] : [...root.querySelectorAll("*")]).filter((el) => declarationFor(el, key) !== void 0);
};
const tagsDeclaring = (holds) => elementDeclarations().filter(([, entry]) => holds(entry)).map(([tag]) => tag);
const matchesWhen = (el, when) => Object.entries(when ?? {}).every(([attr, values]) => values.some((value) => typeof value === "boolean" ? el.hasAttribute(attr) === value : el.getAttribute(attr) === value));
const exhibits = (el, entry) => {
	const rule = entry?.["x-exhibit"];
	return typeof rule === "object" && rule !== null ? matchesWhen(el, rule.when) : !!rule;
};

//#endregion
//#region runtime/shadow.js
const refusedRoots = /* @__PURE__ */ new WeakSet();
const refuseShadowRoot = (root) => refusedRoots.add(root);
const declaredRoot = (host) => host.shadowRoot && registry[host.localName]?.["x-shadow"] && isStage(host.shadowRoot) && !refusedRoots.has(host.shadowRoot) ? host.shadowRoot : null;
const shadowRootsIn = (root) => liveStages().filter((stage) => root.contains(stage.host) && declaredRoot(stage.host) === stage);
const pageShadowRoots = () => shadowRootsIn(document);
const renderedChildren = (node) => node.localName === "slot" ? node.assignedNodes({ flatten: true }) : (node.shadowRoot ?? node).childNodes;
const hostIn = (node, root) => {
	let at = node;
	while (at && at.getRootNode() !== root) at = shadowHost(at.getRootNode());
	return at;
};
const overIn = (el, selector, frame) => {
	const near = el.closest(selector);
	return near && (!frame || under(near, frame)) ? near : null;
};
const SAID = "[data-lf-said]";
const UI_MARKS = `.lf-ui, ${SAID}`;
const uiInside = (el, within) => {
	const near = el && overIn(el, ".lf-ui, [data-lf-said]", within);
	return Boolean(near) && !near.matches("[data-lf-said]");
};
const inUi = (node) => uiInside(node?.nodeType === 1 ? node : node?.parentElement, null);
let shadowRules = "";
const SHADOW_LEADING_CSS = `
@layer {
  [hidden]:not([hidden="until-found"]),
  :host([hidden]:not([hidden="until-found"])) {
    display: none !important;
  }
  @media screen {
    @container style(--lf-before-presentation: 1) {
      *,
      *::before,
      *::after {
        transition: none !important;
      }
    }
    @container style(--lf-before-upgrade: 1) {
      .lf-ui {
        visibility: hidden !important;
      }
    }
  }
}`;
let loading = null;
function loadShadowRules() {
	loading ??= readShadowRules();
	return loading;
}
async function readShadowRules() {
	const { runtimeResource } = await import("./bundle-context2.js");
	const response = await fetch(runtimeResource("/shadow.css"));
	if (!response.ok) throw new Error(`leaf: shadow.css failed to load (${response.status})`);
	shadowRules = await response.text();
}

//#endregion
//#region runtime/stylesheets.js
const sheets = JSON.parse(document.querySelector("script[type=\"application/json\"][data-lf-runtime][data-lf-sheets]").textContent);
const inBaseLayer = (text) => `@layer lf-base {\n${text}\n}`;
function constructSheet(text) {
	const sheet = new CSSStyleSheet();
	sheet.replaceSync(text);
	return sheet;
}
const chromeSheet = constructSheet(sheets.chrome);
const chromeSharedClasses = Object.freeze([
	"lf-aiming",
	"lf-ins-block",
	"lf-over-item",
	"lf-react-mark",
	"lf-mark-note",
	"lf-ui",
	"lf-version-inline",
	"lf-version-inline-deletion",
	"lf-visual-action"
]);
const marksSheet = constructSheet(sheets.marks);
const annotationMarkSheets = sheets.annotations ? [constructSheet(sheets.annotations.marks)] : [];
const annotationSheets = sheets.annotations ? [constructSheet(sheets.annotations.chrome), ...annotationMarkSheets] : [];

//#endregion
//#region runtime/keyboard/layer-stack.js
const entries = [];
const watchedRoots = /* @__PURE__ */ new WeakSet();
const nativeDialogShowModal = HTMLDialogElement.prototype.showModal;
const nativePopoverShow = HTMLElement.prototype.showPopover;
function prune() {
	for (let index = entries.length - 1; index >= 0; index -= 1) if (!entries[index].active()) entries.splice(index, 1);
}
function pushNativeLayer(node, source = null) {
	const at = entries.findIndex((entry) => entry.root === node);
	const existing = at < 0 ? null : entries[at];
	if (existing?.active()) return existing;
	prune();
	const holding = focused();
	const entry = {
		root: node,
		opening: !isNativeLayer(node),
		get kind() {
			return nativeLayerKind(node);
		},
		active() {
			return this.opening || isNativeLayer(node);
		},
		fromNowhere: !holding || holding === document.body,
		opener: holding && holding !== document.body ? holding : null,
		source
	};
	if (entry.opening) queueMicrotask(() => {
		entry.opening = false;
	});
	entries.push(entry);
	return entry;
}
function closing(event) {
	if (event.newState !== "closed") return;
	const entry = entries.find((candidate) => candidate.root === event.target);
	if (entry) entry.opening = false;
	if (entry?.kind === "popover") {
		for (const layer of nativeLayers().toReversed()) if (layer.kind === "modal" && renderedUnder(layer.root, event.target)) closeNativeLayer(layer.root);
	}
	if (entry?.kind === "popover" && entry.fromNowhere && !document.documentElement.inert && canPlaceFocus() && renderedUnder(focused(), event.target)) releaseFocus();
}
HTMLDialogElement.prototype.showModal = function() {
	const entry = nativeLayerKind(this) !== "modal" ? pushNativeLayer(this) : null;
	try {
		return nativeDialogShowModal.call(this);
	} finally {
		if (entry) entry.opening = false;
	}
};
HTMLElement.prototype.showPopover = function(options) {
	const entry = nativeLayerKind(this) !== "popover" ? pushNativeLayer(this) : null;
	try {
		nativePopoverShow.call(this, options);
	} finally {
		if (entry) entry.opening = false;
	}
	if (entry && options?.source) entry.source = options.source;
};
function showNativeLayer(layer, { source, modal = true } = {}) {
	const withholdFocus = Boolean(document.documentElement.lfSample) && !layer.inert;
	if (withholdFocus) layer.inert = true;
	try {
		if (layer instanceof HTMLDialogElement) {
			if (modal) {
				if (source) seatModal(layer, source);
				layer.showModal();
			} else layer.show();
		} else layer.showPopover(source ? { source } : void 0);
	} finally {
		if (withholdFocus) layer.inert = false;
	}
}
const modalHomes = /* @__PURE__ */ new WeakMap();
function seatModal(dialog, source) {
	let place = modalHomes.get(dialog);
	if (!place) {
		place = {
			home: dialog.parentNode,
			chrome: Boolean(dialog.closest(".lf-chrome")),
			scope: null
		};
		modalHomes.set(dialog, place);
		const restore = () => {
			if (dialog.parentNode !== place.home) move(place.home, dialog);
			place.scope?.remove();
		};
		dialog.addEventListener("close", () => {
			if (!dialog.open) restore();
		});
		watchOwner(dialog, { disconnect() {
			if (dialog.parentNode === place.home) return;
			closeNativeLayer(dialog);
			restore();
		} });
	}
	const holder = nativeLayerHolding(source);
	let seat = place.home;
	if (nativeLayerKind(holder) === "popover") {
		if (renderedUnder(holder, place.home)) seat = holder;
		else if (place.chrome) {
			if (!place.scope) {
				place.scope = document.createElement("div");
				place.scope.className = "lf-chrome";
			}
			const root = holder.getRootNode();
			if (root instanceof ShadowRoot && !root.adoptedStyleSheets.includes(chromeSheet)) root.adoptedStyleSheets = [...root.adoptedStyleSheets, chromeSheet];
			if (place.scope.parentNode !== holder) move(holder, place.scope);
			seat = place.scope;
		}
	}
	if (dialog.parentNode !== seat) move(seat, dialog);
}
function closeNativeLayer(layer) {
	const dialog = layer instanceof HTMLDialogElement;
	if (dialog ? !layer.open : !isNativeLayer(layer)) return;
	const currentLocation = focused();
	const returnTo = entries.find((entry) => entry.root === layer)?.opener;
	const returnLocally = document.documentElement.lfSample && currentLocation && renderedUnder(currentLocation, layer);
	const inhibited = document.documentElement.lfSample ? [document.documentElement, ...nativeLayers().filter((entry) => entry.kind === "modal").map((entry) => entry.root)].filter((node) => !node.inert) : [];
	closeLayer(() => {
		for (const node of inhibited) node.inert = true;
		try {
			if (dialog) layer.close();
			else layer.hidePopover();
		} finally {
			for (const node of inhibited) node.inert = false;
		}
	}, returnLocally && (() => {
		if (!canPlaceFocus()) return;
		if (returnTo) handBack(returnTo);
		else releaseFocus();
	}));
}
const changeListeners = /* @__PURE__ */ new Set();
function watchLayerChanges(listener) {
	changeListeners.add(listener);
	return () => changeListeners.delete(listener);
}
const changed = (event) => {
	if (!event.target?.matches?.("[popover], dialog")) return;
	for (const listener of changeListeners) listener(event);
};
function watchLayers(root) {
	if (watchedRoots.has(root)) return;
	watchedRoots.add(root);
	const opened = (event) => {
		if (event.newState === "open" && event.target?.matches?.("[popover], dialog")) pushNativeLayer(event.target, event.source);
	};
	root.addEventListener("beforetoggle", opened, true);
	root.addEventListener("beforetoggle", closing, true);
	root.addEventListener("toggle", opened, true);
	root.addEventListener("toggle", changed, true);
}
watchLayers(document);
function nativeLayers() {
	prune();
	return entries.filter((entry) => entry.active());
}
const NATIVE_LAYERS = Symbol.for("leaf.nativeLayers");
Object.defineProperty(document, NATIVE_LAYERS, { value: nativeLayers });
function nativeModalAdmits(node) {
	const owner = node.ownerDocument;
	const reading = owner[NATIVE_LAYERS];
	if (reading) {
		const modal = reading().findLast((layer) => layer.kind === "modal")?.root;
		return !modal || renderedUnder(node, modal);
	}
	return [...owner.querySelectorAll("dialog")].filter((dialog) => nativeLayerKind(dialog) === "modal").every((modal) => renderedUnder(node, modal));
}
function dismissPopoversOutside(root) {
	for (const entry of nativeLayers().toReversed()) if (entry.kind === "popover" && entry.root.popover !== "manual" && !renderedUnder(entry.root, root)) closeNativeLayer(entry.root);
}

//#endregion
//#region runtime/rect.js
const overlaps = (a, b) => a.left < b.right && b.left < a.right && a.top < b.bottom && b.top < a.bottom;
const overlapsAcross = (a, b) => a.left < b.right && b.left < a.right;
const BOTH = {
	x: true,
	y: true
};
const intersect = (a, b, axes = BOTH) => ({
	left: axes.x ? Math.max(a.left, b.left) : a.left,
	top: axes.y ? Math.max(a.top, b.top) : a.top,
	right: axes.x ? Math.min(a.right, b.right) : a.right,
	bottom: axes.y ? Math.min(a.bottom, b.bottom) : a.bottom
});
const hasArea = (box) => box.right > box.left && box.bottom > box.top;
function union(boxes) {
	if (!boxes.length) return null;
	const left = Math.min(...boxes.map((box) => box.left));
	const top = Math.min(...boxes.map((box) => box.top));
	const right = Math.max(...boxes.map((box) => box.right));
	const bottom = Math.max(...boxes.map((box) => box.bottom));
	return {
		left,
		top,
		right,
		bottom,
		width: right - left,
		height: bottom - top
	};
}
const clamp = (value, low, high) => Math.max(low, Math.min(high, value));
function nearestScrollBy(start, end, low, high) {
	if (start < low && end > high) return 0;
	const oversized = end - start > high - low;
	if (start < low) return oversized ? end - high : start - low;
	if (end > high) return oversized ? start - low : end - high;
	return 0;
}
const clippingAxes = (style) => {
	const clips = /^(hidden|clip|scroll|auto)$/;
	const both = /paint|strict|content/.test(style.contain) || /^(auto|hidden)$/.test(style.contentVisibility);
	return {
		x: both || clips.test(style.overflowX),
		y: both || clips.test(style.overflowY)
	};
};

//#endregion
//#region runtime/geometry.js
const shellRight = () => document.body.getBoundingClientRect().right;
const windowChrome = /* @__PURE__ */ new Map();
const chromeSizes = sizeObserver(() => announceRoom(document));
const watchChrome = (element) => chromeSizes.observe(element, { box: "border-box" });
const declareWindowChrome = (boxes, elements) => {
	windowChrome.set(boxes, elements);
	elements.forEach(watchChrome);
};
const standsIn = (node, elements) => Boolean(node) && elements.some((element) => under(node, element));
const inWindowChrome = (node) => [...windowChrome.values()].some((elements) => standsIn(node, elements));
const windowChromeBoxes = (item = null) => [...windowChrome].filter(([, elements]) => !standsIn(item, elements)).flatMap(([boxes]) => boxes());
const layoutWindow = (doc = document) => ({
	left: 0,
	top: 0,
	right: doc.documentElement.clientWidth,
	bottom: doc.documentElement.clientHeight
});
function shownWindow({ within = null, gap = 0, viewport = "visual", item = null } = {}) {
	const layout = layoutWindow();
	const { offsetLeft, offsetTop, width, height } = viewport === "visual" ? window.visualViewport : {
		offsetLeft: 0,
		offsetTop: 0,
		width: layout.right,
		height: layout.bottom
	};
	const left = Math.max(offsetLeft, within?.left ?? -Infinity) + gap;
	const right = Math.min(offsetLeft + width, within?.right ?? Infinity) - gap;
	let top = Math.max(offsetTop, within?.top ?? -Infinity);
	let bottom = Math.min(offsetTop + height, within?.bottom ?? Infinity);
	const middle = offsetTop + height / 2;
	for (const box of windowChromeBoxes(item)) {
		if (!overlapsAcross(box, {
			left,
			right
		})) continue;
		if (box.top + box.bottom < 2 * middle) top = Math.max(top, box.bottom);
		else bottom = Math.min(bottom, box.top);
	}
	top += gap;
	bottom -= gap;
	return new DOMRect(left, top, Math.max(0, right - left), Math.max(0, bottom - top));
}
function shownBand(el) {
	const doc = el.ownerDocument;
	if (el === doc.scrollingElement) return layoutWindow(doc);
	const s = doc.defaultView.getComputedStyle(el);
	const axes = clippingAxes(s);
	if (!axes.x && !axes.y) return null;
	const b = el.getBoundingClientRect();
	const scaleX = el.offsetWidth ? b.width / el.offsetWidth : 1;
	const scaleY = el.offsetHeight ? b.height / el.offsetHeight : 1;
	const left = b.left + el.clientLeft * scaleX, top = b.top + el.clientTop * scaleY;
	return {
		left,
		top,
		right: left + el.clientWidth * scaleX,
		bottom: top + el.clientHeight * scaleY
	};
}
const scrollport = (overflow) => /^(auto|scroll|hidden)$/.test(overflow);
const userScrollport = (overflow) => /^(auto|scroll)$/.test(overflow);
const scrollsBy = ({ overflowX, overflowY }) => scrollport(overflowX) || scrollport(overflowY);
const scrolls = (el) => scrollsBy(getComputedStyle(el));
const scrollContainer = (box) => box === box.ownerDocument.scrollingElement || scrolls(box);
function scrollsContent(box) {
	if (!(box instanceof Element) || box instanceof SVGElement) return false;
	const style = getComputedStyle(box);
	return scrollport(style.overflowX) && box.scrollWidth > box.clientWidth || scrollport(style.overflowY) && box.scrollHeight > box.clientHeight;
}
const slotHolder = (el, scroller) => {
	let at = el;
	for (let box = el; box && box !== scroller; box = upFrom(box)) if (box.nodeType === 1 && scrolls(box)) at = upFrom(box);
	return at;
};
const insetAt = (at, scroller, slot, padding) => {
	const read = (box) => Number.parseFloat(getComputedStyle(box).getPropertyValue(slot)) || 0;
	const inset = at?.nodeType === 1 ? read(at) : 0;
	if (inset <= read(scroller)) return 0;
	return (Number.parseFloat(getComputedStyle(scroller)[padding]) || 0) + inset;
};
const TOP = ["--lf-top", "paddingTop"];
function slotTop(scroller) {
	const style = getComputedStyle(scroller);
	return (Number.parseFloat(style.paddingTop) || 0) + (Number.parseFloat(style.getPropertyValue("--lf-top")) || 0);
}
const FOOT = ["--lf-bottom", "paddingBottom"];
const edgeInset = (el, scroller, edge) => !scrollContainer(scroller) || el === scroller ? 0 : insetAt(slotHolder(el, scroller), scroller, ...edge);
const headerInset = (el, scroller) => edgeInset(el, scroller, TOP);
const footerInset = (el, scroller) => edgeInset(el, scroller, FOOT);
function visibleBand(scroller, item = null) {
	const band = shownBand(scroller);
	if (!band || !item) return band;
	const top = band.top + headerInset(item, scroller);
	const bottom = band.bottom - footerInset(item, scroller);
	return bottom > top ? {
		...band,
		top,
		bottom
	} : null;
}
const OPEN = 1e5;
function headerCuts(item, clips = /* @__PURE__ */ new Map()) {
	return clipWalk(item, clips, false).cuts.filter(({ covered, footed }) => covered || footed).reverse().map(({ box, band, covered, footed }) => ({
		box,
		band: band && {
			left: band.left - OPEN,
			right: band.right + OPEN,
			top: covered ? band.top : band.top - OPEN,
			bottom: footed ? band.bottom : band.bottom + OPEN
		}
	}));
}
function stuckBox(node, within = null) {
	for (let el = node; el?.nodeType === 1 && el !== within; el = renderedParent(el)) {
		const style = getComputedStyle(el);
		if (style.position === "sticky" ? sticks(el) : inWindow(el, style)) return el;
	}
	return null;
}
const inWindow = (el, style) => style.position === "fixed" && el.offsetParent === null && !style.positionAnchor.startsWith("--");
function sticks(sticky) {
	let scroller = renderedParent(sticky);
	while (scroller?.nodeType === 1 && !scrollContainer(scroller)) scroller = renderedParent(scroller);
	if (scroller?.nodeType !== 1) return false;
	const band = shownBand(scroller);
	if (!band) return false;
	const style = getComputedStyle(sticky);
	const room = getComputedStyle(scroller);
	const padTop = Number.parseFloat(room.paddingTop) || 0;
	const padBottom = Number.parseFloat(room.paddingBottom) || 0;
	const box = sticky.getBoundingClientRect();
	let parent = renderedParent(sticky);
	while (parent !== scroller && getComputedStyle(parent).display === "contents") parent = renderedParent(parent);
	const content = band.top - scroller.scrollTop;
	const holder = parent === scroller ? {
		top: content + padTop,
		bottom: content + scroller.scrollHeight - padBottom
	} : shownBox(parent);
	const topLine = band.top + padTop + Number.parseFloat(style.top);
	const footLine = band.bottom - padBottom - Number.parseFloat(style.bottom);
	if (box.top <= topLine + 1 && holder.top < box.top - 1) return true;
	if (Math.abs(box.bottom - footLine) <= 1) return true;
	return box.bottom > footLine && holder.bottom > box.bottom + 1;
}
function landingBand(scroller) {
	const band = shownBand(scroller);
	if (!band) return null;
	const inset = landingInsets(scroller);
	return {
		left: band.left + inset.left,
		top: band.top + inset.top,
		right: band.right - inset.right,
		bottom: band.bottom - inset.bottom
	};
}
function landingInsets(scroller) {
	const style = getComputedStyle(scroller);
	const inset = (side) => Number.parseFloat(style[`scrollPadding${side}`]) || 0;
	return {
		top: inset("Top"),
		right: inset("Right"),
		bottom: inset("Bottom"),
		left: inset("Left")
	};
}
const skipped = (el) => document.documentElement.lfInitial.skipped(el, renderedParent);
function shownBox(el) {
	if (el === document.scrollingElement) {
		const { left, top, right, bottom } = shownBand(el);
		return new DOMRect(left, top, right - left, bottom - top);
	}
	const r = el.getBoundingClientRect();
	if (r.width || r.height) return r;
	const contents = document.createRange();
	contents.selectNodeContents(el);
	return contents.getBoundingClientRect();
}
function shownParts(el) {
	const r = el.getBoundingClientRect();
	if (r.width && r.height) return [el];
	return [...el.children].filter((child) => !uiInside(child, el)).flatMap((child) => shownParts(child));
}
const shownExtent = (el) => union(shownParts(el).map((part) => part.getBoundingClientRect()));
function shownRect(item, clips) {
	return clippedRect(shownBox(item), item, clips);
}
function seenRect(item, clips, box = shownBox(item)) {
	const shown = clippedRect(box, item, clips);
	if (!shown) return null;
	const room = shownWindow({
		within: shown,
		item
	});
	return room.width > 0 && room.height > 0 ? {
		left: shown.left,
		top: room.top,
		right: shown.right,
		bottom: room.bottom
	} : null;
}
function presented(node) {
	if (!node.checkVisibility({ visibilityProperty: true }) || excludedByInert(node) || !nativeModalAdmits(node)) return false;
	for (let at = node; at; at = renderedParent(at)) if (at.getAttribute?.("aria-hidden") === "true") return false;
	return true;
}
function frameView(frame, within) {
	const seen = seenRect(frame, /* @__PURE__ */ new Map());
	const shown = seen && intersect(seen, within);
	if (!shown || !hasArea(shown)) return null;
	const rect = frame.getBoundingClientRect();
	const scaleX = rect.width / frame.offsetWidth || 1;
	const scaleY = rect.height / frame.offsetHeight || 1;
	const x = (at) => (at - rect.left) / scaleX - frame.clientLeft;
	const y = (at) => (at - rect.top) / scaleY - frame.clientTop;
	return {
		left: x(shown.left),
		top: y(shown.top),
		right: x(shown.right),
		bottom: y(shown.bottom)
	};
}
const ROOM_MOVED = "lf-room-moved";
const announceRoom = (target) => target.dispatchEvent(new Event(ROOM_MOVED, {
	bubbles: true,
	composed: true
}));
function watchRoom(callback) {
	const viewport = window.visualViewport;
	const listening = [
		[window, "resize"],
		[viewport, "scroll"],
		[viewport, "resize"],
		[
			document,
			ROOM_MOVED,
			true
		]
	];
	for (const [target, type, capture] of listening) target.addEventListener(type, callback, capture);
	const stops = [
		watchScrolls(callback),
		watchLayerChanges(callback),
		() => {
			for (const [target, type, capture] of listening) target.removeEventListener(type, callback, capture);
		}
	];
	return () => {
		for (const stop of stops) stop();
	};
}
function motionBand(item, clips) {
	const walk = clipWalk(item, clips, false);
	const cut = cutBy({
		left: -Infinity,
		top: -Infinity,
		right: Infinity,
		bottom: Infinity
	}, walk.cuts.map((each) => ({
		...each,
		axes: {
			...each.axes,
			x: false
		}
	})), item.ownerDocument.scrollingElement, true);
	if (!cut) return null;
	const room = shownWindow({ within: cut });
	if (room.height <= 0) return null;
	const scroller = walk.cuts.find(({ box, scrolls }) => scrolls && box.scrollHeight > box.clientHeight)?.box;
	const anchors = !scroller ? cut.top : scroller.scrollTop > 0 ? landingBand(scroller).top : shownBand(scroller).top;
	return anchors < room.bottom ? {
		top: anchors,
		bottom: room.bottom
	} : null;
}
function growthIsSeen(node, clips = /* @__PURE__ */ new Map()) {
	const { top, bottom, height } = node.getBoundingClientRect();
	if (!height) return false;
	const band = motionBand(node, clips);
	return Boolean(band) && bottom > band.top && top < band.bottom;
}
function growthAfterIsSeen(node, clips = /* @__PURE__ */ new Map()) {
	const { bottom, height } = node.getBoundingClientRect();
	if (!height) return false;
	const band = motionBand(node, clips);
	return Boolean(band) && bottom > band.top && bottom < band.bottom;
}
const watches = /* @__PURE__ */ new Set();
let watchPass = null;
let unlisten = null;
const readWatches = () => {
	watchPass = null;
	const clips = /* @__PURE__ */ new Map();
	const left = [...watches].filter((watch) => watch.read(clips));
	for (const watch of left) if (watches.has(watch)) watch.leave();
};
const rereadWatches = () => {
	watchPass ??= nextRender(readWatches);
};
function whenNone(nodes, holds, leave) {
	let held = null;
	const watch = {
		leave,
		read(clips) {
			const now = nodes.some((node) => node.isConnected && Boolean(holds(node, clips)));
			const stopped = !now && held !== false;
			held = now;
			return stopped;
		}
	};
	watches.add(watch);
	unlisten ??= watchRoom(rereadWatches);
	const observer = new IntersectionObserver(rereadWatches);
	for (const node of nodes) observer.observe(node);
	return () => {
		observer.disconnect();
		watches.delete(watch);
		if (watches.size) return;
		unlisten();
		unlisten = null;
		if (watchPass !== null) cancelRender(watchPass);
		watchPass = null;
	};
}
const startsAt = (item, clips) => {
	const fragments = item.getClientRects();
	return (fragments.length ? [...fragments] : [shownBox(item)]).map((box) => clippedRect(box, item, clips)).find(Boolean);
};
const clippedRect = (box, item, clips) => clipped(box, item, clips, false);
function paintClips(item, box, clips, aboveSurfaces, held = false) {
	const walk = clipWalk(item, clips, held);
	const plane = walk.fixed ? "window" : "page";
	const root = item.ownerDocument.scrollingElement;
	const hidden = {
		plane,
		window: {
			left: 0,
			top: 0,
			right: 0,
			bottom: 0
		},
		bands: []
	};
	let window = walk.cuts.find(({ box: cut, covered }) => cut === root && covered)?.band;
	const bands = walk.cuts.filter(({ box: cut }) => cut !== root).reverse();
	let shown = cutBy(box, walk.cuts, root, false);
	if (!shown) return walk.cuts.some(({ band }) => !band) ? hidden : {
		plane,
		window: window ?? null,
		bands
	};
	for (const { surface, box: over, level } of aboveSurfaces ? openOccluders(clips) : []) {
		if (!overlaps(shown, over) || under(item, surface) || stackLevel(item) >= level) continue;
		const left = uncovered(shown, over);
		if (!left) return hidden;
		window ??= shownBand(root);
		window = {
			left: left.left > shown.left ? Math.max(window.left, over.right) : window.left,
			top: left.top > shown.top ? Math.max(window.top, over.bottom) : window.top,
			right: left.right < shown.right ? Math.min(window.right, over.left) : window.right,
			bottom: left.bottom < shown.bottom ? Math.min(window.bottom, over.top) : window.bottom
		};
		shown = left;
	}
	return {
		plane,
		window: window ?? null,
		bands
	};
}
const pagePlaneRect = (box, item, clips) => clipped(box, item, clips, false, false);
const nearObserver = (callback) => new IntersectionObserver(callback, {
	rootMargin: "100%",
	scrollMargin: "600px"
});
function nearWindow(target, clips = /* @__PURE__ */ new Map()) {
	if (!target.checkVisibility()) return false;
	const box = pagePlaneRect(shownBox(target), target, clips);
	const { right: width, bottom: height } = layoutWindow();
	return Boolean(box) && box.bottom >= -height && box.top <= 2 * height && box.right >= -width && box.left <= 2 * width;
}
const clippedContents = (box, holder, clips) => clipped(box, holder, clips, true);
function clipped(box, item, clips, held, inWindow = true) {
	const root = item.ownerDocument.scrollingElement;
	const shown = cutBy(box, clipWalk(item, clips, held).cuts, root, inWindow);
	return shown && occluded(shown, item, clips);
}
function cutBy(box, cuts, root, inWindow) {
	let shown = inWindow ? intersect(box, layoutWindow()) : box;
	for (const { box: cut, band, axes, covered } of cuts) {
		if (!band) return null;
		const edges = !inWindow && cut === root ? {
			left: -Infinity,
			top: covered ? band.top : -Infinity,
			right: Infinity,
			bottom: Infinity
		} : band;
		shown = intersect(shown, edges, axes);
	}
	const { left, top, right, bottom } = shown;
	return hasArea(shown) ? {
		left,
		top,
		right,
		bottom
	} : null;
}
function clipWalk(item, clips, held) {
	let holder = item;
	let escaped = false, containing = null;
	const cuts = [];
	for (let a = item; a; a = upFrom(a)) {
		let c = clips.get(a);
		if (c === void 0) clips.set(a, c = {
			band: shownBand(a),
			axes: a === a.ownerDocument.scrollingElement ? {
				x: true,
				y: true
			} : clippingAxes(getComputedStyle(a)),
			positioned: a.offsetParent !== void 0 && ["fixed", "absolute"].includes(getComputedStyle(a).position),
			block: a.offsetParent,
			scrolls: scrollContainer(a)
		});
		if (escaped && a === containing) escaped = false;
		if (!escaped && (held || a !== item) && c.band) {
			const covered = c.band.top + (c.scrolls ? insetAt(holder, a, ...TOP) : 0);
			const footed = c.band.bottom - (c.scrolls ? insetAt(holder, a, ...FOOT) : 0);
			cuts.push({
				box: a,
				axes: c.axes,
				scrolls: c.scrolls,
				covered: c.axes.y && covered > c.band.top,
				footed: c.axes.y && footed < c.band.bottom,
				band: c.axes.y && covered >= footed ? null : c.axes.y ? {
					...c.band,
					top: covered,
					bottom: footed
				} : c.band
			});
		}
		if (c.scrolls) holder = upFrom(a);
		if (!escaped && c.positioned) {
			escaped = true;
			containing = c.block;
		}
	}
	return {
		cuts,
		fixed: escaped && !containing
	};
}
const occluders = /* @__PURE__ */ new Set();
const standsNow = (surface) => surface.checkVisibility();
function restingBox(surface) {
	let left = 0, top = 0;
	for (let at = surface; at; at = at.offsetParent) {
		left += at.offsetLeft + (at === surface ? 0 : at.clientLeft);
		top += at.offsetTop + (at === surface ? 0 : at.clientTop);
	}
	return {
		left,
		top,
		right: left + surface.offsetWidth,
		bottom: top + surface.offsetHeight
	};
}
const declareOccluder = (surface) => {
	occluders.add(surface);
	watchChrome(surface);
	return () => {
		occluders.delete(surface);
		chromeSizes.unobserve(surface);
		announceRoom(document);
	};
};
function rightCover() {
	const edge = layoutWindow().right;
	let left = Infinity;
	for (const surface of occluders) {
		if (!standsNow(surface)) continue;
		const box = restingBox(surface);
		if (box.left > 0 && box.right >= edge - 1) left = Math.min(left, box.left);
	}
	return left;
}
const PAST = Symbol("past");
const clipsPast = (surfaces) => /* @__PURE__ */ new Map([[PAST, new Set(surfaces)]]);
const clipsPastSurfaces = () => clipsPast(occluders);
function hides(surface, where) {
	const holder = placeHolder(where);
	if (!holder || !occluders.has(surface) || !standsNow(surface)) return false;
	if (under(holder, surface) || stackLevel(holder) >= stackLevel(surface)) return false;
	const box = placeBox(where);
	const { left, top, right, bottom } = clippedPlace(where, clipsPast([surface]), box) ?? box;
	const over = restingBox(surface);
	const across = Math.min(right, over.right) - Math.max(left, over.left);
	const room = shownWindow({ viewport: "layout" });
	if (over.top <= room.top + 1 && over.bottom >= room.bottom - 1) return across > (right - left) / 2;
	const down = Math.min(bottom, over.bottom) - Math.max(top, over.top);
	return across > 0 && down > 0 && across * down > (right - left) * (bottom - top) / 2;
}
const underOccluder = (where) => [...occluders].some((surface) => hides(surface, where));
const placeHolder = (where) => where instanceof Range ? where.startContainer instanceof Element ? where.startContainer : where.startContainer.parentElement : where;
const placeBox = (where) => where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
const clippedPlace = (where, clips, box = placeBox(where)) => where instanceof Range ? clippedContents(box, placeHolder(where), clips) : clippedRect(box, where, clips);
function stackLevel(node) {
	let level = 0;
	for (let a = node; a; a = renderedParent(a)) {
		if (isNativeLayer(a)) return Infinity;
		const { position, zIndex } = getComputedStyle(a);
		if (position !== "static" && zIndex !== "auto") level = Number(zIndex);
	}
	return level;
}
const OCCLUDERS = Symbol("occluders");
function openOccluders(clips) {
	let open = clips.get(OCCLUDERS);
	if (open) return open;
	const past = clips.get(PAST);
	open = [...occluders].filter(standsNow).filter((surface) => !past?.has(surface)).map((surface) => ({
		surface,
		box: restingBox(surface),
		level: stackLevel(surface)
	}));
	clips.set(OCCLUDERS, open);
	return open;
}
const area = (box) => (box.right - box.left) * (box.bottom - box.top);
function occluded(rect, item, clips) {
	for (const { surface, box, level } of openOccluders(clips)) {
		if (!overlaps(rect, box) || under(item, surface) || stackLevel(item) >= level) continue;
		rect = uncovered(rect, box);
		if (!rect) return null;
	}
	return rect;
}
function uncovered(rect, box) {
	if (!overlaps(rect, box)) return rect;
	const sides = [
		{
			...rect,
			right: Math.min(rect.right, box.left)
		},
		{
			...rect,
			left: Math.max(rect.left, box.right)
		},
		{
			...rect,
			bottom: Math.min(rect.bottom, box.top)
		},
		{
			...rect,
			top: Math.max(rect.top, box.bottom)
		}
	].filter((side) => side.right > side.left && side.bottom > side.top);
	return sides.length ? sides.reduce((most, side) => area(side) > area(most) ? side : most) : null;
}

//#endregion
export { SAID, SHADOW_LEADING_CSS, UI_MARKS, adoptRegistry, annotationMarkSheets, annotationSheets, chromeSharedClasses, chromeSheet, clamp, clippedContents, clippedPlace, clippingAxes, clipsPastSurfaces, closeNativeLayer, decisionFor, declarationFor, declareOccluder, declareWindowChrome, declaredRoot, dismissPopoversOutside, elementDeclarations, elementsDeclaring, exhibits, frameFor, frameView, growthAfterIsSeen, growthIsSeen, hasArea, headerCuts, headerInset, hostIn, inBaseLayer, inUi, inWindowChrome, intersect, landingBand, landingInsets, layerFact, layoutWindow, loadShadowRules, marksSheet, matchesWhen, nativeLayers, nativeModalAdmits, nearObserver, nearWindow, nearestScrollBy, overIn, overlaps, overlapsAcross, pageShadowRoots, paintClips, placeBox, placeHolder, presented, recordedWidgetSelector, refuseShadowRoot, registry, renderedChildren, rightCover, scrollContainer, scrollGlides, scrolling, scrollsBy, scrollsContent, seenRect, shadowRootsIn, shadowRules, shellRight, showNativeLayer, shownBand, shownBox, shownExtent, shownParts, shownRect, shownWindow, skipped, slotTop, stackLevel, startsAt, stateSpecs, stuckBox, tagsDeclaring, tokenEntry, uiInside, underOccluder, union, userScrollport, visibleBand, watchArrivals, watchArrivalsIn, watchLayerChanges, watchLayers, watchOwner, watchRoom, watchScrollEnds, watchScrolls, whenNone, whileConnected, windowChromeBoxes };