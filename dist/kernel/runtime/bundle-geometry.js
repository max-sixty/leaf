import { cancelRender, elementBox, excludedByInert, isNativeLayer, nextRender, renderedParent, sizeObserver, under, watchScrolls } from "./bundle-portable.js";
import { nativeModalAdmits, uiInside, watchLayerChanges } from "./bundle-layer-stack.js";

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
function shownWindow({ within = null, gap = 0, viewport = "visual", item = null, across = null } = {}) {
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
		if (!overlapsAcross(box, across ?? {
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
	for (let box = el; box && box !== scroller; box = renderedParent(box)) if (box.nodeType === 1 && scrolls(box)) at = renderedParent(box);
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
function shownBox(el) {
	if (el === document.scrollingElement) {
		const { left, top, right, bottom } = shownBand(el);
		return new DOMRect(left, top, right - left, bottom - top);
	}
	return elementBox(el);
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
const showsContents = (node, options) => node.getAttribute("hidden") !== "until-found" && node.checkVisibility(options);
function presented(node) {
	if (!showsContents(node, { visibilityProperty: true }) || excludedByInert(node) || !nativeModalAdmits(node)) return false;
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
const clippedRect = (box, item, clips, stop) => clipped(box, item, clips, false, true, stop);
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
const clippedContents = (box, holder, clips, stop) => clipped(box, holder, clips, true, true, stop);
function clipped(box, item, clips, held, inWindow = true, stop) {
	const root = item.ownerDocument.scrollingElement;
	const shown = cutBy(box, clipWalk(item, clips, held, stop).cuts, root, inWindow && !stop);
	return stop ? shown : shown && occluded(shown, item, clips);
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
function clipWalk(item, clips, held, stop) {
	let holder = item;
	let escaped = false, containing = null;
	const cuts = [];
	for (let a = item; a && a !== stop; a = renderedParent(a)) {
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
			const covered = c.band.top + (!stop && c.scrolls ? insetAt(holder, a, ...TOP) : 0);
			const footed = c.band.bottom - (!stop && c.scrolls ? insetAt(holder, a, ...FOOT) : 0);
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
		if (c.scrolls) holder = renderedParent(a);
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
function coveredShare(surface, where, landed = null) {
	const holder = placeHolder(where);
	if (!holder || !occluders.has(surface) || !standsNow(surface)) return 0;
	if (under(holder, surface) || under(surface, holder)) return 0;
	if (stackLevel(holder) >= stackLevel(surface)) return 0;
	const box = landed ?? placeBox(where);
	const { left, top, right, bottom } = landed ?? clippedPlace(where, clipsPast([surface]), box) ?? box;
	const over = restingBox(surface);
	const across = Math.max(0, Math.min(right, over.right) - Math.max(left, over.left));
	const room = shownWindow({ viewport: "layout" });
	if (over.top <= room.top + 1 && over.bottom >= room.bottom - 1) return across / (right - left || 1);
	return across * Math.max(0, Math.min(bottom, over.bottom) - Math.max(top, over.top)) / ((right - left) * (bottom - top) || 1);
}
const hides = (surface, where) => coveredShare(surface, where) > .5;
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
export { clamp, clippedContents, clippedPlace, clippedRect, clippingAxes, clipsPastSurfaces, coveredShare, declareOccluder, declareWindowChrome, frameView, growthAfterIsSeen, growthIsSeen, hasArea, headerCuts, headerInset, inWindowChrome, intersect, landingBand, landingInsets, layoutWindow, nearObserver, nearWindow, nearestScrollBy, overlaps, overlapsAcross, paintClips, placeBox, placeHolder, presented, rightCover, scrollContainer, scrollsBy, scrollsContent, seenRect, shellRight, shownBand, shownBox, shownExtent, shownParts, shownRect, shownWindow, showsContents, slotTop, stackLevel, startsAt, stuckBox, underOccluder, union, userScrollport, visibleBand, watchRoom, whenNone, windowChromeBoxes };