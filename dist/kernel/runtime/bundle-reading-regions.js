import { J, Z } from "./bundle-signals-core.js";
import { LENT_REACH_STOP, TEXT_BOX, afterScript, deepFocus, keeps, nextFrame, nextRender, onCurrentLocation, pressing, renderedParent, renderedUnder, renderingState, sizeObserver, tabStops, under, upFrom, wearsLentStop } from "./bundle-dom-move.js";
import { PAGE_PAINT_ATTRIBUTE, pagePresented, reportPageError, setRuntimeRootAttribute } from "./bundle-layer-client.js";
import { landingBand, scrollsBy, shadowRootsIn, shownRect, skipped, userScrollport, watchArrivals, watchOwner, whileConnected } from "./bundle-geometry.js";
import { applicationPresented, tick } from "./bundle-context.js";
import { LAYOUT } from "./bundle-errors.js";
import { layoutBox, pageDocument } from "./bundle-passages.js";

//#region runtime/presence.js
let clockSkew = 0;
const pulse = Z(0);
const serverNow = () => Date.now() + clockSkew;
const saidNow = () => new Date(serverNow()).toISOString();
const clockValue = (read) => J(() => {
	pulse.value;
	return read(serverNow());
}).value;
async function tickClock(reportError) {
	try {
		tick(pulse);
	} catch (error) {
		reportError(error, "clock paint failed");
	}
}
const observeServerNow = (now) => {
	if (now) clockSkew = Date.parse(now) - Date.now();
};
const JUST_NOW = "just now";
const age = (ts, compact) => clockValue((now) => {
	if (!ts) return "";
	const secs = Math.max(0, (now - new Date(ts).getTime()) / 1e3);
	if (secs < 45) return compact ? "now" : JUST_NOW;
	const [count, unit] = secs < 3600 ? [Math.round(secs / 60), "m"] : secs < 86400 ? [Math.round(secs / 3600), "h"] : [Math.round(secs / 86400), "d"];
	return `${count}${unit}${compact ? "" : " ago"}`;
});
const ago = (ts) => age(ts, false);
const shortAgo = (ts) => age(ts, true);
let workingGrace = null;
const observeWorkingGrace = (ms) => {
	workingGrace = ms;
};
const quietSince = (ts) => clockValue((now) => workingGrace !== null && Boolean(ts) && now - new Date(ts).getTime() >= workingGrace);
const activityTransitionAt = (state) => Math.min(...[state?.activity, ...(state?.others ?? []).map((entry) => entry?.activity)].filter((activity) => activity?.next_transition_at).map((activity) => Date.parse(activity.next_transition_at)));
const activityTransitionDue = (state) => serverNow() >= activityTransitionAt(state);

//#endregion
//#region runtime/presentation.js
const UPGRADE = "lf-upgraded";
function markPageUpgraded() {
	setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.upgraded, "1");
	document.dispatchEvent(new Event(UPGRADE));
}
const { promise: presented, resolve: resolvePresented } = Promise.withResolvers();
function markPagePresented() {
	setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.presented, "1");
	resolvePresented();
}
const arriving = /* @__PURE__ */ new Set();
const restarts = /* @__PURE__ */ new Set();
function deferredArrival(work) {
	arriving.add(work);
	const landed = () => arriving.delete(work);
	work.then(landed, landed);
	for (const restart of restarts) restart();
	restarts.clear();
	return work;
}
async function whenArrived() {
	while (arriving.size) await Promise.allSettled(arriving);
}
const whenArriving = () => arriving.size ? Promise.resolve() : new Promise((restart) => restarts.add(restart));
const afterPresentation = (work) => deferredArrival(presented.then(work));
let appliedState = null;
function markStateApplied(state) {
	setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.reading, state.reading);
	appliedState = {
		reading: state.reading,
		taken: state.taken,
		lapses: activityTransitionAt(state)
	};
}
const stamp = (name) => document.body.getAttribute(PAGE_PAINT_ATTRIBUTE[name]);
const READINESS = [
	["upgraded", () => stamp("upgraded") === "1"],
	["log", () => stamp("applied") !== null],
	["state", (held) => !held || appliedState?.taken >= held.taken || appliedState?.reading === held.reading && held.taken * 1e3 < appliedState.lapses],
	["presented", () => pagePresented() && applicationPresented()],
	["arrived", () => arriving.size === 0],
	["rendering", () => Object.values(renderingState()).every(Boolean)]
];
const READINESS_STAGES = new Set(READINESS.map(([stage]) => stage));
function pageReadiness(held = null, through = "rendering") {
	if (!READINESS_STAGES.has(through)) throw new TypeError(`no readiness stage named ${through}`);
	for (const [stage, met] of READINESS) {
		if (!met(held)) return stage;
		if (stage === through) return null;
	}
}
const PRESENTATION = "lf-presentation";
const PAGE_INTERFACE = "lf-page-interface";
async function settlePageInterface() {
	const pending = [];
	const present = (promise) => {
		if (!promise?.then) throw new TypeError("Page interface presentation must be a promise");
		pending.push(promise);
		return promise;
	};
	document.dispatchEvent(new CustomEvent(PAGE_INTERFACE, { detail: { present } }));
	for (const result of await Promise.allSettled(pending)) if (result.status === "rejected") reportPageError(result.reason, "Page interface failed");
}
function whileInterfaceConnected(element, { declare, connect }) {
	let declared = false;
	return whileConnected(element, (signal) => {
		let connected = false;
		let cleanup;
		const start = () => {
			if (signal.aborted || connected) return;
			if (!declared) {
				declare?.();
				declared = true;
			}
			connected = true;
			cleanup = connect(signal);
		};
		document.addEventListener(PAGE_INTERFACE, (event) => event.detail.present(Promise.resolve().then(start)), { signal });
		if (declared) start();
		return () => cleanup?.();
	});
}

//#endregion
//#region runtime/scrolling.js
const pageScroller = document.scrollingElement;
const moving = /* @__PURE__ */ new WeakMap();
const scrollSteps = /* @__PURE__ */ new WeakMap();
const layoutMoved = /* @__PURE__ */ new WeakSet();
const watchedLayout = /* @__PURE__ */ new WeakSet();
const lastTop = /* @__PURE__ */ new WeakMap();
const extents = /* @__PURE__ */ new WeakMap();
const extentOf = (box) => [
	box.scrollHeight,
	box.clientWidth,
	box.clientHeight
];
const changedExtent = (before, after) => before?.some((value, index) => value !== after[index]);
function watchLayout(box) {
	if (watchedLayout.has(box)) return;
	watchedLayout.add(box);
	lastTop.set(box, box.scrollTop);
	extents.set(box, extentOf(box));
	const root = box === pageScroller ? document.documentElement : box;
	const sizes = /* @__PURE__ */ new WeakMap();
	const measure = (node) => [
		node.clientWidth,
		node.clientHeight,
		node.scrollHeight
	];
	const observer = sizeObserver((entries) => {
		let changed = false;
		for (const { target } of entries) {
			const next = measure(target);
			const before = sizes.get(target);
			sizes.set(target, next);
			if (before?.some((value, index) => value !== next[index])) changed = true;
		}
		if (changed) {
			if (box.scrollTop !== lastTop.get(box)) layoutMoved.add(box);
			else extents.set(box, extentOf(box));
		}
	}, { counted: false });
	const observe = (node) => {
		sizes.set(node, measure(node));
		observer.observe(node);
	};
	observe(root);
	if (box !== pageScroller) {
		for (const child of box.children) observe(child);
		const mutation = new MutationObserver((entries) => {
			for (const entry of entries) {
				for (const node of entry.addedNodes) if (node instanceof Element) observe(node);
				for (const node of entry.removedNodes) if (node instanceof Element) observer.unobserve(node);
			}
		});
		mutation.observe(box, { childList: true });
		watchOwner(box, { disconnect() {
			observer.disconnect();
			mutation.disconnect();
			watchedLayout.delete(box);
		} });
	}
}
watchLayout(pageScroller);
function stopScroll(boxes) {
	const stopped = [...boxes].filter((box) => moving.has(box)).map((box) => [box, moving.get(box)]);
	if (!stopped.length) return null;
	for (const [box] of stopped) box.scrollTo({
		left: box.scrollLeft,
		top: box.scrollTop,
		behavior: "instant"
	});
	return new Promise((resolve) => nextFrame(() => nextFrame(() => {
		for (const [box, sequence] of stopped) if (moving.get(box) === sequence) moving.delete(box);
		resolve(void 0);
	})));
}
let choices = 0;
const chosen = /* @__PURE__ */ new WeakMap();
const kept = /* @__PURE__ */ new WeakMap();
const scrollChoices = () => choices;
const chosenSince = (box, count) => (chosen.get(box) ?? 0) > count;
const chooseScroll = (box) => chosen.set(box, ++choices);
function startScroll(box) {
	moving.set(box, { glide: true });
	chooseScroll(box);
}
const eventScroller = (target) => target === document ? pageScroller : target;
document.addEventListener("scroll", ({ target }) => {
	const box = eventScroller(target);
	watchLayout(box);
	scrollSteps.set(box, (scrollSteps.get(box) ?? 0) + 1);
	if (moving.get(box)?.glide) return;
	const sequence = { glide: false };
	moving.set(box, sequence);
	nextFrame(() => nextFrame(() => {
		if (moving.get(box) === sequence) moving.delete(box);
	}));
}, {
	capture: true,
	passive: true
});
function placeKept(...boxes) {
	for (const box of boxes) kept.set(box, box.scrollTop);
}
document.addEventListener("scrollend", ({ target }) => {
	const box = eventScroller(target);
	watchLayout(box);
	const wasMoving = moving.get(box);
	moving.delete(box);
	const extent = extentOf(box);
	const repeated = (scrollSteps.get(box) ?? 0) > 1;
	scrollSteps.delete(box);
	if ((wasMoving?.glide || repeated || !layoutMoved.has(box) && !changedExtent(extents.get(box), extent)) && kept.get(box) !== box.scrollTop) chooseScroll(box);
	layoutMoved.delete(box);
	lastTop.set(box, box.scrollTop);
	extents.set(box, extent);
	kept.delete(box);
}, {
	capture: true,
	passive: true
});
const riding = /* @__PURE__ */ new WeakSet();
const contentRides = (box, rides) => rides ? riding.add(box) : riding.delete(box);
function laidOutHeight(box) {
	let end = 0;
	for (const child of box.children) {
		if (!child.checkVisibility()) continue;
		if (child.offsetParent !== box) return box.scrollHeight;
		end = Math.max(end, child.offsetTop + child.offsetHeight + Number.parseFloat(getComputedStyle(child).marginBottom));
	}
	const padding = Number.parseFloat(getComputedStyle(box).paddingBottom);
	return Math.min(box.scrollHeight, end + padding);
}
const scrollLimit = (box) => Math.max(0, (riding.has(box) ? laidOutHeight(box) : box.scrollHeight) - box.clientHeight);
const SCROLL_SLACK = 2;
const atScrollEnd = (box) => scrollLimit(box) - box.scrollTop <= 2;
const scrollToEnd = (box, behavior = "instant") => {
	if (behavior !== "instant" && !atScrollEnd(box)) startScroll(box);
	box.scrollTo({
		top: scrollLimit(box),
		behavior
	});
};
const aims = /* @__PURE__ */ new WeakMap();
const moveScrollerBy = (box, top, behavior = "instant") => {
	const aim = box.scrollTop + top;
	if (Math.abs(top) >= .5) {
		if (behavior !== "instant" && reachable(box, top)) startScroll(box);
		box.scrollBy({
			top,
			behavior
		});
	}
	if (behavior === "instant" && Math.abs(aim - box.scrollTop) < 1) aims.set(box, {
		aim,
		at: box.scrollTop
	});
	else aims.delete(box);
};
const aimedTop = (box) => {
	const kept = aims.get(box);
	return kept?.at === box.scrollTop ? kept.aim : box.scrollTop;
};
const reachable = (box, top) => Math.max(-box.scrollTop, Math.min(scrollLimit(box) - box.scrollTop, top));

//#endregion
//#region runtime/reach.js
const SCROLL_SURFACE = ".scroll";
const seenDeclarations = /* @__PURE__ */ new WeakMap();
const scrollAncestors = /* @__PURE__ */ new WeakSet();
const styleRoots = /* @__PURE__ */ new WeakSet();
const ancestorStyles = new MutationObserver((records) => {
	for (const { target } of records) if (scrollAncestors.has(target)) reread(target);
});
function watchAncestorStyles(scope) {
	const tree = scope.getRootNode();
	const root = tree.nodeType === Node.DOCUMENT_NODE ? tree.documentElement : tree;
	if (!root || styleRoots.has(root) || !root.isConnected) return;
	styleRoots.add(root);
	ancestorStyles.observe(root, {
		subtree: true,
		attributes: true,
		attributeFilter: [
			"class",
			"style",
			"dir"
		]
	});
}
let watchingSurfaces = false;
const overflows = (el) => !el.hasAttribute("hidden") && (el.scrollWidth > el.clientWidth || el.scrollHeight > el.clientHeight);
const holdsOwnStop = (el) => tabStops(el).length > 0;
const mayScroll = /* @__PURE__ */ new Map();
const claimedStops = /* @__PURE__ */ new WeakSet();
function lendStop(el) {
	keeps(el, LENT_REACH_STOP, "");
	keeps(el, "tabindex", 0);
}
function claimReachStop(el) {
	if (claimedStops.has(el)) return;
	if ((mayScroll.has(el) ? mayScroll.get(el) : el.getAttribute("tabindex")) !== null) return;
	claimedStops.add(el);
	lendStop(el);
}
function releaseReachStop(el) {
	if (!claimedStops.has(el)) return;
	claimedStops.delete(el);
	if (el.getAttribute("tabindex") !== "0") {
		keeps(el, LENT_REACH_STOP, null);
		return;
	}
	if (mayScroll.has(el) && overflows(el) && !holdsOwnStop(el)) lendStop(el);
	else returnStop(el, null);
}
function returnStop(el, authored) {
	keeps(el, LENT_REACH_STOP, null);
	if (el.getAttribute("tabindex") === "0") keeps(el, "tabindex", wearsLentStop(el) ? -1 : authored);
}
const sideways = /* @__PURE__ */ new Map();
const downwards = /* @__PURE__ */ new Map();
const readingScrolled = (event) => paintReadingReach(event.currentTarget);
const sidewaysScrolled = (event) => paintSidewaysReach(event.currentTarget, true);
function reachReadingScroller(el, paintContinuation) {
	el.classList.toggle("scroll", true);
	downwards.set(el, paintContinuation);
	sweep(el);
	paintReach();
	watchReach(el);
	el.addEventListener("scroll", readingScrolled, { passive: true });
	paintReadingReach(el);
	return () => {
		downwards.delete(el);
		if (!watched(el)) unwatchReach(el);
		el.removeEventListener("scroll", readingScrolled);
		afterScript(() => {
			if (!downwards.has(el)) {
				keeps(el, PAGE_PAINT_ATTRIBUTE.moreBelow, null);
				paintContinuation?.(false);
			}
		});
	};
}
const readingPaints = /* @__PURE__ */ new Set();
let readingPaintQueued = false;
function paintReadingReach(el) {
	readingPaints.add(el);
	if (readingPaintQueued) return;
	readingPaintQueued = true;
	nextRender(paintReadingReachNow);
}
function paintReadingReachNow() {
	readingPaintQueued = false;
	const pending = [...readingPaints];
	readingPaints.clear();
	for (const el of pending) {
		if (!downwards.has(el) || unpainted(el)) continue;
		const style = getComputedStyle(el);
		const scrolling = userScrollport(style.overflowY);
		downwards.get(el)?.(scrolling && el.scrollTop > 2);
		keeps(el, PAGE_PAINT_ATTRIBUTE.moreBelow, scrolling && !atScrollEnd(el) ? "" : null);
	}
}
const waiting = /* @__PURE__ */ new Set();
function reachScrollers(root) {
	sweep(root);
	paintReach();
	if (watchingSurfaces) return;
	watchingSurfaces = true;
	watchArrivals(SCROLL_SURFACE, ["class", "style"], {
		arriveBatch(surfaces) {
			for (const el of surfaces) {
				const classes = el.getAttribute("class");
				const style = el.getAttribute("style");
				const previous = seenDeclarations.get(el);
				if (previous?.classes === classes && previous?.style === style) continue;
				seenDeclarations.set(el, {
					classes,
					style
				});
				reread(el);
			}
		},
		leave: forgetSurface
	});
}
const wait = (el) => {
	waiting.add(el);
	reachSizes.observe(el);
};
function sweep(root) {
	const scopes = [root];
	for (const scope of scopes) scopes.push(...shadowRootsIn(scope));
	for (const scope of scopes) watchAncestorStyles(scope);
	const surfaces = scopes.flatMap((scope) => [...scope.nodeType === Node.ELEMENT_NODE && scope.matches(SCROLL_SURFACE) ? [scope] : [], ...scope.querySelectorAll(SCROLL_SURFACE)]);
	const read = [];
	const containers = /* @__PURE__ */ new Set();
	for (const el of surfaces) {
		seenDeclarations.set(el, {
			classes: el.getAttribute("class"),
			style: el.getAttribute("style")
		});
		if (skipped(el)) {
			wait(el);
			continue;
		}
		const style = getComputedStyle(el);
		read.push([el, {
			overflowX: style.overflowX,
			overflowY: style.overflowY,
			position: style.position,
			direction: style.direction
		}]);
		for (let node = el; node?.nodeType === Node.ELEMENT_NODE; node = upFrom(node)) {
			scrollAncestors.add(node);
			if (containers.has(node)) break;
			containers.add(node);
		}
	}
	const queriesRead = [...containers].map((el) => [el, { containerType: getComputedStyle(el).containerType }]);
	for (const [el, style] of queriesRead) noteQueries(el, style);
	for (const [el, style] of read) {
		const waited = waiting.delete(el);
		classify(el, style);
		if (waited) release(el);
	}
	asked.add(root);
}
function forgetSurface(el) {
	seenDeclarations.delete(el);
	if (mayScroll.has(el)) {
		const authored = mayScroll.get(el);
		mayScroll.delete(el);
		if (!claimedStops.has(el)) returnStop(el, authored);
	}
	if (sideways.delete(el)) el.removeEventListener("scroll", sidewaysScrolled);
	waiting.delete(el);
	keeps(el, PAGE_PAINT_ATTRIBUTE.scrolls, null);
	keeps(el, PAGE_PAINT_ATTRIBUTE.scrollDirection, null);
	keeps(el, PAGE_PAINT_ATTRIBUTE.moreBefore, null);
	keeps(el, PAGE_PAINT_ATTRIBUTE.moreAfter, null);
	if (!watched(el)) unwatchReach(el);
}
function paintSlot(el, style) {
	const sticks = style.position === "sticky";
	const scrolls = scrollsBy(style) && !sticks && !el.matches(TEXT_BOX);
	const across = userScrollport(style.overflowX) && !userScrollport(style.overflowY);
	keeps(el, PAGE_PAINT_ATTRIBUTE.scrolls, scrolls ? across ? "across" : "" : null);
}
function classify(el, style) {
	asked.add(el);
	paintSlot(el, style);
	if (!userScrollport(style.overflowX) && sideways.delete(el)) {
		el.removeEventListener("scroll", sidewaysScrolled);
		keeps(el, PAGE_PAINT_ATTRIBUTE.scrollDirection, null);
		keeps(el, PAGE_PAINT_ATTRIBUTE.moreBefore, null);
		keeps(el, PAGE_PAINT_ATTRIBUTE.moreAfter, null);
	}
	if (el.hasAttribute("hidden") || !userScrollport(style.overflowX) && !userScrollport(style.overflowY)) {
		if (!mayScroll.has(el)) return;
		const authored = mayScroll.get(el);
		mayScroll.delete(el);
		if (!claimedStops.has(el)) returnStop(el, authored);
		if (!watched(el)) unwatchReach(el);
		return;
	}
	if (userScrollport(style.overflowX) && !el.matches(TEXT_BOX)) {
		if (!sideways.has(el)) {
			watchReach(el);
			el.addEventListener("scroll", sidewaysScrolled, { passive: true });
		}
		sideways.set(el, style.direction);
	}
	if (!mayScroll.has(el)) {
		if (el.tabIndex >= 0 && !claimedStops.has(el)) return;
		mayScroll.set(el, wearsLentStop(el) || claimedStops.has(el) ? null : el.getAttribute("tabindex"));
	}
	watchReach(el);
}
const childrenWatched = /* @__PURE__ */ new WeakSet();
const childLists = new MutationObserver((records) => {
	for (const { target, addedNodes, removedNodes } of records) {
		if (!childrenWatched.has(target)) continue;
		for (const node of removedNodes) if (node.nodeType === Node.ELEMENT_NODE) release(node);
		for (const node of addedNodes) if (node.nodeType === Node.ELEMENT_NODE) reachSizes.observe(node);
	}
});
function watchReach(el) {
	reachSizes.observe(el);
	if (childrenWatched.has(el)) return;
	childrenWatched.add(el);
	for (const child of el.children) reachSizes.observe(child);
	childLists.observe(el, { childList: true });
}
function unwatchReach(el) {
	const heldChildren = childrenWatched.delete(el);
	release(el);
	if (heldChildren) for (const child of el.children) release(child);
}
function release(node) {
	if (!watched(node) && !childrenWatched.has(node.parentElement)) reachSizes.unobserve(node);
}
const depth = (el) => {
	let levels = 0;
	for (let node = el; node; node = upFrom(node)) levels++;
	return levels;
};
const watched = (el) => mayScroll.has(el) || sideways.has(el) || downwards.has(el) || waiting.has(el);
const reachSizes = sizeObserver(() => paintReach());
function paintSidewaysReach(el, readStyle = false) {
	afterScript(() => {
		if (!sideways.has(el) || unpainted(el)) return;
		const direction = readStyle ? getComputedStyle(el).direction : sideways.get(el);
		if (readStyle) sideways.set(el, direction);
		const scrolling = el.scrollWidth > el.clientWidth + 1;
		const maximum = Math.max(0, el.scrollWidth - el.clientWidth);
		const raw = Math.abs(el.scrollLeft);
		const position = Math.min(maximum, Math.max(0, raw));
		keeps(el, PAGE_PAINT_ATTRIBUTE.scrollDirection, scrolling ? direction : null);
		el.toggleAttribute(PAGE_PAINT_ATTRIBUTE.moreBefore, scrolling && position > 2);
		el.toggleAttribute(PAGE_PAINT_ATTRIBUTE.moreAfter, scrolling && position < maximum - 2);
	});
}
function gone(el) {
	if (el.isConnected) return false;
	mayScroll.delete(el);
	if (sideways.delete(el)) el.removeEventListener("scroll", sidewaysScrolled);
	downwards.delete(el);
	waiting.delete(el);
	if (queried.delete(el)) queries.unobserve(el);
	unwatchReach(el);
	return true;
}
const unpainted = (el) => gone(el) || skipped(el);
function paintReach() {
	afterScript(paintReachNow);
}
function paintReachNow() {
	for (const el of waiting) if (!unpainted(el)) sweep(el);
	const levels = new Map([...mayScroll.keys()].map((el) => [el, depth(el)]));
	for (const [el, authored] of [...mayScroll].sort(([a], [b]) => levels.get(b) - levels.get(a))) {
		if (unpainted(el)) continue;
		if (claimedStops.has(el)) continue;
		if (overflows(el) && !holdsOwnStop(el)) lendStop(el);
		else returnStop(el, authored);
	}
	for (const el of sideways.keys()) paintSidewaysReach(el);
	for (const el of downwards.keys()) paintReadingReach(el);
}
const rereads = /* @__PURE__ */ new Set();
let rereadQueued = false;
function reread(root) {
	rereads.add(root);
	if (rereadQueued) return;
	rereadQueued = true;
	nextRender(() => {
		rereadQueued = false;
		const roots = [...rereads];
		rereads.clear();
		const due = new Set(roots);
		for (const root of roots) {
			if (!root.isConnected) continue;
			let covered = false;
			for (let ancestor = upFrom(root); ancestor; ancestor = upFrom(ancestor)) if (due.has(ancestor)) {
				covered = true;
				break;
			}
			if (covered) continue;
			sweep(root);
		}
		paintReach();
	});
}
const queried = /* @__PURE__ */ new Map();
const unobserved = /* @__PURE__ */ new Set();
function noteQueries(el, { containerType }) {
	const kinds = containerType.split(" ");
	const both = kinds.includes("size");
	if (!both && !kinds.includes("inline-size")) {
		if (queried.delete(el)) queries.unobserve(el);
		return;
	}
	if (queried.get(el)?.both === both) return;
	queried.set(el, {
		both,
		size: null
	});
	if (!unobserved.size) nextRender(observeQueried);
	unobserved.add(el);
}
function observeQueried() {
	for (const el of unobserved) if (queried.has(el)) queries.observe(el);
	unobserved.clear();
}
const queries = sizeObserver((entries) => {
	for (const { target, contentBoxSize } of entries) {
		const query = queried.get(target);
		if (!query || gone(target)) continue;
		const [{ inlineSize, blockSize }] = contentBoxSize;
		const size = query.both ? `${inlineSize} ${blockSize}` : `${inlineSize}`;
		if (query.size !== null && query.size !== size) reread(target);
		query.size = size;
	}
}, { counted: false });
addEventListener("resize", () => reread(document.body));
const asked = /* @__PURE__ */ new WeakSet();
const reached = (el) => {
	for (let node = el; node; node = upFrom(node)) if (asked.has(node)) return true;
	return false;
};
document.addEventListener(LAYOUT, (event) => {
	const [changed] = event.composedPath();
	if (changed?.nodeType === Node.ELEMENT_NODE && reached(changed)) reread(changed);
	paintReach();
});

//#endregion
//#region runtime/reading-regions.js
const regions = /* @__PURE__ */ new Map();
const transitionWatchers = /* @__PURE__ */ new Set();
const depthOf = (node) => {
	let depth = 0;
	for (let current = node; current; current = renderedParent(current)) depth += 1;
	return depth;
};
const live = (region) => region?.host?.isConnected && region.body?.isConnected;
const concealed = (region) => region.host.hidden || region.host.closest?.("[hidden], [aria-hidden='true']") !== null || region.body.matches("details:not([open])");
const hidden = (region) => !live(region) || concealed(region) || shownRect(region.host, /* @__PURE__ */ new Map()) === null;
const regionRecord = (region) => ({
	id: region.id,
	host: region.host,
	body: region.body,
	subject: region.subject
});
function compoundReadingRegionId(owner, localName) {
	if (!owner?.id || !/^[a-z][a-z0-9-]*$/.test(localName ?? "")) throw new Error("leaf: a compound reading region needs an owner id and local name");
	return `lf-region:${owner.id}:${localName}`;
}
function registerReadingRegion({ id, host, body, paintContinuation = void 0 }) {
	if (typeof id !== "string" || !id || !host || !body) throw new Error("leaf: a reading region needs id, host, and body");
	if (live(regions.get(id))) throw new Error(`leaf: reading region ${id} is already live`);
	const region = {
		id,
		host,
		body,
		subject: void 0,
		scroller: null,
		width: null,
		away: false
	};
	const stopReaching = reachReadingScroller(body, paintContinuation);
	regions.set(id, region);
	sizes.observe(host);
	return () => {
		if (regions.get(id) === region) regions.delete(id);
		sizes.unobserve(host);
		stopReaching();
	};
}
const layoutRegions = /* @__PURE__ */ new Map();
const marked = (box) => box.checkVisibility() && getComputedStyle(box).getPropertyValue("--lf-reading-region").trim() === "layout";
function syncLayoutRegion() {
	const main = layoutBox();
	const bodies = main ? [...main.children].flatMap((child) => {
		if (marked(child)) return [[child, child.id]];
		const only = child.childElementCount === 1 ? child.firstElementChild : null;
		return only && marked(only) ? [[only, only.id || child.id]] : [];
	}) : [];
	let unnamed = 0;
	const ids = new Map(bodies.map(([body, name]) => [body, name ? `lf-region:layout#${name}` : `lf-region:layout@${unnamed++}`]));
	for (const [body, region] of layoutRegions) if (ids.get(body) !== region.id) {
		region.stop();
		layoutRegions.delete(body);
	}
	for (const [body, id] of ids) if (!layoutRegions.has(body)) layoutRegions.set(body, {
		id,
		stop: registerReadingRegion({
			id,
			host: body,
			body
		})
	});
}
function showReadingSubject(id, subject, render) {
	const region = regions.get(id);
	if (!live(region) || region.subject === subject) {
		if (region) region.subject = subject;
		return render();
	}
	notify({
		phase: "leaving",
		region: regionRecord(region)
	});
	region.subject = subject;
	const rendered = render();
	notify({
		phase: "showing",
		region: regionRecord(region)
	});
	return rendered;
}
const readingRegion = (id) => {
	const region = regions.get(id);
	return live(region) ? regionRecord(region) : void 0;
};
const readingRegions = () => [...regions.values()].filter(live).map(regionRecord);
const unconcealedReadingRegions = () => [...regions.values()].filter((region) => live(region) && !concealed(region) && !skipped(region.body)).map(regionRecord);
const regionAt = (node) => {
	return [...regions.values()].filter((candidate) => live(candidate) && renderedUnder(node, candidate.host)).sort((a, b) => depthOf(b.host) - depthOf(a.host))[0];
};
const readingRegionFor = (node) => {
	const region = regionAt(node);
	return region && regionRecord(region);
};
let recentRegionId = null;
let pageRegionId = null;
const readingInputReaders = /* @__PURE__ */ new Set();
const onReadingInput = (read) => readingInputReaders.add(read);
const readingInput = (node) => {
	for (const read of readingInputReaders) read(node);
};
const actedAt = (at, arriving) => {
	const region = readingRegionFor(at);
	if (region) {
		recentRegionId = region.id;
		if (under(region.host, pageDocument())) pageRegionId = region.id;
	} else if ((at === document.body || under(at, pageDocument())) && !(arriving && at === document.body && pressing())) recentRegionId = pageRegionId = null;
};
for (const type of [
	"pointerdown",
	"wheel",
	"touchstart",
	"click"
]) addEventListener(type, (event) => {
	const at = event.composedPath()[0];
	if (type !== "click") actedAt(at, false);
	else if (event.isTrusted && event.button === 0) readingInput(at);
}, {
	capture: true,
	passive: true
});
onCurrentLocation((node, cause) => {
	if (node) actedAt(node, true);
	if (node && cause === "step") readingInput(node);
});
const recentReadingRegion = () => readingRegion(recentRegionId);
const shown = (region) => region?.host.checkVisibility() ? region : void 0;
const pageReadingRegion = () => {
	const at = deepFocus();
	if (under(at, pageDocument())) return readingRegionFor(at);
	return shown(readingRegion(pageRegionId));
};
const userReadingRegion = () => {
	const at = deepFocus();
	const region = readingRegionFor(at);
	if (region || under(at, pageDocument())) return region;
	return shown(recentReadingRegion()) ?? pageReadingRegion();
};
const containingReadingRegionFor = (node) => {
	let region = regionAt(node);
	while (region) {
		if (renderedUnder(node, region.body)) return regionRecord(region);
		region = regionAt(renderedParent(region.host));
	}
};
const asRegion = (regionOrNode) => typeof regionOrNode === "string" ? regions.get(regionOrNode) : regions.get(regionOrNode?.id) ?? regions.get(readingRegionFor(regionOrNode)?.id);
const scrolls = (box) => userScrollport(getComputedStyle(box).overflowY);
const regionScrollBehavior = (regionOrNode) => {
	const region = asRegion(regionOrNode);
	return region && live(region) && scrolls(region.body) ? "bounded" : "flow";
};
function effectiveScroller(regionOrNode) {
	const region = asRegion(regionOrNode);
	if (!region) return pageScroller;
	if (regionScrollBehavior(region) === "bounded") return region.body;
	const containing = [...regions.values()].filter((candidate) => candidate !== region && live(candidate) && renderedUnder(region.host, candidate.body)).sort((a, b) => depthOf(b.host) - depthOf(a.host))[0];
	return containing ? effectiveScroller(containing) : pageScroller;
}
const scrollerFor = (el) => {
	const region = containingReadingRegionFor(el);
	return region ? effectiveScroller(region) : pageScroller;
};
function* scrollersOf(node) {
	for (let box = scrollerFor(node);; box = scrollerFor(renderedParent(box))) {
		for (let at = node; at !== box; at = renderedParent(at)) if (!at || getComputedStyle(at).position === "fixed") return;
		yield box;
		if (box === pageScroller) return;
		node = box;
	}
}
function* scrollChainOf(node) {
	let last = null;
	for (last of scrollersOf(node)) yield last;
	if (last !== pageScroller) yield pageScroller;
}
function shownRegionBounds(regionOrNode) {
	const region = asRegion(regionOrNode);
	if (!region || hidden(region)) return null;
	return shownRect(region.body, /* @__PURE__ */ new Map());
}
function watchReadingRegionTransitions(listener) {
	transitionWatchers.add(listener);
	return () => transitionWatchers.delete(listener);
}
const notify = (detail) => {
	for (const listener of transitionWatchers) listener(detail);
};
const compositionTransitions = /* @__PURE__ */ new Map();
async function preserveReadingRegions(owner, change) {
	const transition = {
		owner,
		regions: readingRegions().filter((region) => under(region.host, owner))
	};
	notify({
		...transition,
		phase: "before",
		retained: compositionTransitions.has(owner)
	});
	compositionTransitions.set(owner, transition);
	let completed = false;
	try {
		await change();
		completed = true;
	} finally {
		if (compositionTransitions.get(owner) === transition) {
			compositionTransitions.delete(owner);
			notify({
				...transition,
				phase: "after",
				cancelled: !completed || !owner.isConnected
			});
		}
	}
}
const asSeen = (region, scroller, width) => region.scroller === scroller && region.width === width;
let viewportHeight = innerHeight;
let pageSeen = null;
const pageGeometry = () => ({
	width: pageScroller.clientWidth,
	band: landingBand(pageScroller)?.top ?? 0
});
const pageMoved = (now = pageGeometry()) => {
	if (pageSeen === null) return false;
	if (now.width !== pageSeen.width) return true;
	pageSeen = now;
	return false;
};
const regionsSettled = () => viewportHeight === innerHeight && !pageMoved() && [...regions.values()].every((region) => !live(region) || !region.scroller || !shown(region) || asSeen(region, effectiveScroller(region), region.host.offsetWidth));
function measureRegions() {
	const viewportChanged = viewportHeight !== innerHeight;
	viewportHeight = innerHeight;
	const shifted = [];
	for (const region of regions.values()) {
		if (!live(region) || !shown(region)) continue;
		const scroller = effectiveScroller(region);
		const width = region.host.offsetWidth;
		const away = concealed(region);
		if (region.scroller && (viewportChanged || !asSeen(region, scroller, width))) shifted.push({
			region: regionRecord(region),
			from: region.scroller,
			to: scroller,
			returned: Boolean(region.away) && !away
		});
		region.scroller = scroller;
		region.width = width;
		region.away = away;
	}
	const now = pageGeometry();
	if (pageMoved(now)) shifted.push({
		region: null,
		band: now.band - pageSeen.band
	});
	pageSeen = now;
	if (shifted.length) notify({
		phase: "shift",
		shifted
	});
}
const sizes = sizeObserver(measureRegions);
sizes.observe(pageScroller);
addEventListener("resize", () => nextRender(measureRegions), { passive: true });

//#endregion
export { JUST_NOW, PAGE_INTERFACE, PRESENTATION, UPGRADE, activityTransitionDue, afterPresentation, ago, aimedTop, atScrollEnd, chosenSince, claimReachStop, clockValue, compoundReadingRegionId, containingReadingRegionFor, contentRides, deferredArrival, effectiveScroller, markPagePresented, markPageUpgraded, markStateApplied, moveScrollerBy, observeServerNow, observeWorkingGrace, onReadingInput, pageReadiness, pageReadingRegion, pageScroller, placeKept, preserveReadingRegions, quietSince, reachScrollers, reachable, readingRegion, readingRegionFor, readingRegions, recentReadingRegion, regionScrollBehavior, regionsSettled, registerReadingRegion, releaseReachStop, saidNow, scrollChainOf, scrollChoices, scrollLimit, scrollToEnd, scrollerFor, scrollersOf, settlePageInterface, shortAgo, showReadingSubject, shownRegionBounds, startScroll, stopScroll, syncLayoutRegion, tickClock, unconcealedReadingRegions, userReadingRegion, watchReadingRegionTransitions, whenArrived, whenArriving, whileInterfaceConnected };