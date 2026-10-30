import { __exportAll } from "./bundle-rolldown-runtime.js";
import { actionElement, atLayoutPrecision, cancelRender, iconElement, keeps, layoutPx, nativeLayerHolding, nextRender, offer, offeredActionElement, renderedParent, renderedUnder, setScroll } from "./bundle-portable.js";
import { PRESSES, carriedFrom, deepFocus, focusDestination, focused, inputCount, move, onCurrentLocation, ringBox } from "./bundle-layer-stack.js";
import { el, notice, raiseError } from "./bundle-layer-client.js";
import { anchorAt, anchorBox, anchorElement, anchorReaches, anchorReading, cutFrames, localScrollBy, nameAnchor, pageScroller, reachable, scrollAxes, scrollersOf, scrollsWith, startScroll } from "./bundle-content-layout.js";
import { clippingAxes, hasArea, headerCuts, intersect, landingBand, layoutWindow, nearObserver, nearWindow, nearestScrollBy, paintClips, placeBox, placeHolder, scrollsContent, seenRect, shownBox, shownParts, shownWindow, visibleBand } from "./bundle-geometry.js";
import { inChrome } from "./bundle-passages.js";

//#region runtime/user-intent.js
const passed = /* @__PURE__ */ new WeakMap();
const passOn = (container, target) => passed.set(target, {
	container,
	intent: inputCount()
});
const displaced = (source, at) => {
	if (!(source instanceof Node) || !at) return false;
	const via = passed.get(at);
	const carry = carriedFrom(at);
	return at.contains(source) || via?.intent === inputCount() && via.container.contains(source) || carry?.inputs === inputCount() && (carry.from === source || source.contains(carry.from));
};
function retainUserIntent({ source = focused(), available = () => true, fallback = null, since = inputCount() } = {}) {
	const retained = since;
	let held = source instanceof Node ? new WeakRef(source) : null;
	const current = () => {
		const at = focused();
		const from = held?.deref();
		const withinSource = from === document.body ? at === document.body : from?.contains(at);
		return available() && retained === inputCount() && (at === document.body || at === fallback || withinSource || displaced(from, at));
	};
	current.available = available;
	current.handoff = (move) => {
		if (!available() || retained !== inputCount()) return false;
		const moved = current();
		if (moved) move();
		const at = focused();
		held = at ? new WeakRef(at) : null;
		return moved && current();
	};
	return current;
}
function restrictUserIntent(retained, available) {
	const current = () => available() && retained();
	current.available = () => available() && retained.available();
	current.handoff = (move) => available() && retained.handoff(move);
	return current;
}

//#endregion
//#region runtime/target-paint-geometry.js
const SVG_NS = "http://www.w3.org/2000/svg";
const SHAPE_STROKE_ROOM = 2;
const paints = (shape, property) => {
	const style = getComputedStyle(shape);
	return shape.checkVisibility({
		opacityProperty: true,
		visibilityProperty: true
	}) && style[property] !== "none" && Number.parseFloat(style[`${property}Opacity`]) !== 0 && (property !== "stroke" || Number.parseFloat(style.strokeWidth) > 0);
};
function paintGeometry(surface) {
	if (!(surface instanceof SVGElement) || !surface.ownerSVGElement) return null;
	const geometry = [surface, ...surface.querySelectorAll("*")].filter((child) => child instanceof SVGGeometryElement);
	const fill = geometry.filter((shape) => paints(shape, "fill"));
	const paintedStroke = geometry.filter((shape) => paints(shape, "stroke"));
	const outlined = /* @__PURE__ */ new Set([...fill, ...paintedStroke]);
	const stroke = geometry.filter((shape) => outlined.has(shape));
	return fill.length || stroke.length ? {
		fill,
		stroke
	} : null;
}
function geometryClone(source, left, top, property) {
	const matrix = source.getScreenCTM();
	if (!matrix) return null;
	const clone = source.cloneNode(false);
	clone.removeAttribute("id");
	clone.removeAttribute("class");
	clone.removeAttribute("opacity");
	clone.removeAttribute("fill-opacity");
	clone.removeAttribute("stroke-opacity");
	clone.style.removeProperty("transform");
	clone.style.removeProperty("opacity");
	clone.style.removeProperty("fill-opacity");
	clone.style.removeProperty("stroke-opacity");
	for (const attribute of [...clone.attributes]) {
		const length = source[attribute.localName];
		if (attribute.value.includes("%") && length instanceof SVGAnimatedLength) clone.setAttribute(attribute.name, String(length.animVal.value));
	}
	clone.setAttribute("transform", `matrix(${matrix.a} ${matrix.b} ${matrix.c} ${matrix.d} ${atLayoutPrecision(matrix.e - left)} ${atLayoutPrecision(matrix.f - top)})`);
	clone.style.setProperty("fill", property === "fill" ? "white" : "none", "important");
	clone.style.setProperty("stroke", property === "stroke" ? "var(--lf-shape-ink)" : "none", "important");
	clone.style.setProperty("stroke-width", "var(--lf-shape-stroke)", "important");
	clone.style.setProperty("stroke-dasharray", "var(--lf-shape-dash, none)", "important");
	clone.style.setProperty("stroke-linejoin", "round", "important");
	clone.style.setProperty("stroke-linecap", "round", "important");
	clone.style.setProperty("vector-effect", "non-scaling-stroke", "important");
	return clone;
}
function paintShape(host, geometry, { left, top, right, bottom }, options = {}) {
	if (!geometry) return false;
	const { maskId = "", veil = false } = options;
	const width = atLayoutPrecision(right - left);
	const height = atLayoutPrecision(bottom - top);
	const fill = veil ? geometry.fill.map((shape) => geometryClone(shape, left, top, "fill")) : [];
	const stroke = geometry.stroke.map((shape) => geometryClone(shape, left, top, "stroke"));
	if ([...fill, ...stroke].some((shape) => !shape)) return false;
	const paint = [];
	if (veil && fill.length) {
		const defs = document.createElementNS(SVG_NS, "defs");
		const mask = document.createElementNS(SVG_NS, "mask");
		mask.id = maskId;
		mask.setAttribute("maskUnits", "userSpaceOnUse");
		mask.setAttribute("x", "0");
		mask.setAttribute("y", "0");
		mask.setAttribute("width", String(width));
		mask.setAttribute("height", String(height));
		mask.style.maskType = "alpha";
		mask.append(...fill);
		defs.append(mask);
		const wash = document.createElementNS(SVG_NS, "rect");
		wash.setAttribute("width", String(width));
		wash.setAttribute("height", String(height));
		wash.setAttribute("fill", "var(--lf-shape-ink)");
		wash.setAttribute("fill-opacity", "0.08");
		wash.setAttribute("mask", `url(#${maskId})`);
		paint.push(defs, wash);
	}
	const outline = document.createElementNS(SVG_NS, "g");
	outline.append(...stroke);
	paint.push(outline);
	keeps(host, "viewBox", `0 0 ${width} ${height}`);
	keeps(host, "width", width);
	keeps(host, "height", height);
	const held = host.children;
	if (paint.length !== held.length || paint.some((node, index) => !node.isEqualNode(held[index]))) host.replaceChildren(...paint);
	return true;
}
function paintStand(box = null) {
	const root = document.createElement("div");
	root.className = "lf-ui lf-target-paint lf-paint-stand";
	root.setAttribute("aria-hidden", "true");
	root.style.position = "fixed";
	const carrier = document.createElement("div");
	carrier.className = "lf-paint-carrier";
	if (box) carrier.append(box);
	root.append(carrier);
	return {
		root,
		carrier,
		box,
		anchored: false,
		frames: []
	};
}
function anchoredBy(el, root) {
	const anchor = anchorElement(el);
	if (!anchorReaches(anchor, root)) return null;
	return anchor === el || scrollsWith(el, anchor) && !scrollsContent(anchor) || scrollsWith(anchor, el) ? anchor : null;
}
const makeFrame = () => {
	const frame = document.createElement("div");
	frame.className = "lf-paint-frame";
	return frame;
};
function standIn(stand, placed, anchored) {
	const { levels } = placed;
	const anchors = levels.map(({ holder }) => holder && anchoredBy(holder, stand.root));
	anchored &&= levels.every(({ holder }, i) => !holder || anchors[i]);
	stand.anchored = anchored;
	stand.frames = cutFrames(levels.map(({ band, axes }, i) => ({
		anchor: anchored ? anchors[i] : null,
		band,
		axes
	})), stand.frames, makeFrame);
	const [outer] = stand.frames;
	if (outer && outer.parentNode !== stand.root) move(stand.root, outer, null);
	const inner = stand.frames.at(-1) ?? stand.root;
	if (stand.carrier.parentNode !== inner) move(inner, stand.carrier, null);
	const band = levels.at(-1)?.band;
	return {
		anchored,
		origin: anchored ? null : {
			x: band?.left ?? 0,
			y: band?.top ?? 0
		}
	};
}
function standBox(box, rect, stood, anchor, at = anchor && anchorBox(anchor)) {
	if (stood.anchored) {
		anchorAt(box, anchor, rect, at, stood.visibility ?? "always");
		return;
	}
	Object.assign(box.style, {
		position: "",
		positionAnchor: "",
		positionVisibility: "",
		left: layoutPx(rect.left - stood.origin.x),
		top: layoutPx(rect.top - stood.origin.y),
		...rect.right === void 0 ? {} : {
			width: layoutPx(rect.right - rect.left),
			height: layoutPx(rect.bottom - rect.top)
		}
	});
}
function standOver(stand, placed, borderRadius) {
	const anchor = anchoredBy(placed.surface, stand.root);
	const at = anchor && anchorBox(anchor);
	const stood = standIn(stand, placed, Boolean(anchor));
	standBox(stand.box, placed.rect, stood, anchor, at);
	Object.assign(stand.box.style, {
		display: "block",
		borderRadius
	});
	const band = token("--focus-ring-w");
	const outside = markGap(placed.surface);
	const gap = cramped(placed, band + outside) ? -band : outside;
	stand.box.style.setProperty("--lf-mark-offset", layoutPx(gap));
	const room = Math.max(0, band + gap);
	for (const side of [
		"top",
		"right",
		"bottom",
		"left"
	]) stand.root.style.setProperty(`--lf-paint-outset-${side}`, layoutPx(cutsAt(placed, side) ? 0 : room));
	return {
		...stood,
		anchor,
		at,
		room
	};
}
const token = (name) => Number.parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
function markGap(surface) {
	const style = getComputedStyle(surface);
	if (style.getPropertyValue("--lf-ring-at")) return Number.parseFloat(style.outlineOffset);
	return token(surface.matches(PRESSES) ? "--focus-ring-gap" : "--focus-region-gap");
}
function cutsAt({ rect, levels }, side) {
	const axis = side === "top" || side === "bottom" ? "y" : "x";
	const low = side === "top" || side === "left";
	return levels.some(({ band, axes }) => axes[axis] && (low ? rect[side] < band[side] : rect[side] > band[side]));
}
function cramped({ rect, levels, plane }, room) {
	const short = (band, low, high) => rect[low] >= band[low] && rect[low] - room < band[low] || rect[high] <= band[high] && rect[high] + room > band[high];
	const page = pageExtent(plane);
	return short(page, "left", "right") || short(page, "top", "bottom") || levels.some(({ holder, band, axes }) => holder && (axes.x && short(band, "left", "right") || axes.y && short(band, "top", "bottom")));
}
function pageExtent(plane) {
	const shown = layoutWindow();
	const root = document.scrollingElement;
	if (plane === "window" || !root) return shown;
	const style = getComputedStyle(root);
	const fixed = (overflow) => overflow === "hidden" || overflow === "clip";
	const [x, y] = [!fixed(style.overflowX), !fixed(style.overflowY)];
	return {
		left: x ? -root.scrollLeft : shown.left,
		top: y ? -root.scrollTop : shown.top,
		right: x ? root.scrollWidth - root.scrollLeft : shown.right,
		bottom: y ? root.scrollHeight - root.scrollTop : shown.bottom
	};
}
function paintSet(root, { onNear = () => {} } = {}) {
	const stands = /* @__PURE__ */ new Map();
	const entries = /* @__PURE__ */ new Map();
	const near = /* @__PURE__ */ new Set();
	const watched = /* @__PURE__ */ new Map();
	const watching = /* @__PURE__ */ new Map();
	const nearBy = (target) => !target || near.has(target);
	const view = nearObserver((records) => {
		const moved = /* @__PURE__ */ new Set();
		for (const { target: box, isIntersecting } of records) for (const target of watching.get(box) ?? []) {
			if (isIntersecting) near.add(target);
			else near.delete(target);
			moved.add(target);
		}
		for (const stand of stands.values()) if (stand.members.some(({ target }) => moved.has(target))) seat(stand);
		onNear();
	});
	const ids = /* @__PURE__ */ new WeakMap();
	let idCount = 0;
	const idOf = (node) => ids.get(node) ?? (ids.set(node, ++idCount), idCount);
	const keyOf = ({ surface, levels }, anchor, plane, framed) => !surface ? `${plane}|window` : [
		plane,
		framed ? "cut" : "open",
		anchor ? "anchored" : "window",
		...levels.map(({ holder, band, from, axes }) => {
			const edges = [
				from.left,
				from.top,
				from.left + band.right - band.left
			];
			return `${holder ? idOf(holder) : "window"}:${[...edges, from.top + band.bottom - band.top]}:${axes.x}${axes.y}`;
		})
	].join("|");
	function seat(stand, all = false) {
		const { carrier, members } = stand;
		const seating = new Set(members.filter(({ node, target }) => nearBy(target) && (all || node.parentElement !== carrier)));
		const readings = [...seating].filter(({ entry }) => entry.anchor).map(({ entry }) => anchorReading(entry.anchor));
		for (const reading of readings) nameAnchor(reading);
		let cursor = carrier.firstElementChild;
		for (const member of members) {
			const { node, target, entry } = member;
			if (!nearBy(target)) {
				if (node.parentElement !== carrier) continue;
				if (cursor === node) cursor = node.nextElementSibling;
				node.remove();
				continue;
			}
			if (cursor === node) cursor = node.nextElementSibling;
			else move(carrier, node, cursor);
			if (seating.has(member)) standBox(node, entry.rect, entry.stood, entry.anchor, entry.at);
		}
	}
	function place(items, clips = /* @__PURE__ */ new Map()) {
		const holders = /* @__PURE__ */ new Map();
		const targets = /* @__PURE__ */ new Set();
		const read = items.map((item) => {
			const { node, target = null, rect, held = false, anchor, plane = "page" } = item;
			const { cut: framed = true } = item;
			if (!target) {
				const placed = {
					surface: null,
					levels: []
				};
				return {
					node,
					target,
					placed,
					rect,
					plane,
					framed,
					key: keyOf(placed, null, plane)
				};
			}
			targets.add(target);
			let placed = placement(target, false, false, clips, held);
			const { left, top, right, bottom } = placed.rect;
			if (!(right > left && bottom > top)) return {
				node,
				target,
				placed: null
			};
			const box = typeof rect === "function" ? rect(placed) : rect ?? placed.rect;
			if (!watched.has(target)) {
				const box = anchorElement(target);
				watched.set(target, box);
				if (!watching.has(box)) {
					watching.set(box, /* @__PURE__ */ new Set());
					view.observe(box);
				}
				watching.get(box).add(target);
				if (nearWindow(target, clips)) near.add(target);
			}
			const carriedBy = anchor === void 0 ? anchoredBy(target, root) : anchor && anchorReaches(anchor, root) ? anchor : null;
			if (!framed) placed = {
				...placed,
				levels: headerCuts(target, clips).map(({ box, band }) => ({
					holder: box === box.ownerDocument.scrollingElement ? null : box,
					band: band ?? {
						left: 0,
						top: 0,
						right: 0,
						bottom: 0
					},
					axes: {
						x: false,
						y: true
					}
				}))
			};
			for (const { holder } of placed.levels) if (holder && !holders.has(holder)) holders.set(holder, holder.getBoundingClientRect());
			placed.levels = placed.levels.map((level) => {
				const at = level.holder ? holders.get(level.holder) : {
					left: 0,
					top: 0
				};
				return {
					...level,
					from: {
						left: level.band.left - at.left,
						top: level.band.top - at.top
					}
				};
			});
			return {
				node,
				target,
				placed,
				rect: box,
				plane,
				framed,
				anchor: carriedBy,
				at: carriedBy && anchorBox(carriedBy),
				key: keyOf(placed, carriedBy, plane, framed)
			};
		});
		for (const [target, box] of watched) if (!targets.has(target)) {
			watched.delete(target);
			near.delete(target);
			watching.get(box).delete(target);
			if (watching.get(box).size) continue;
			watching.delete(box);
			view.unobserve(box);
		}
		const stood = /* @__PURE__ */ new Map();
		let previous = null;
		for (const { placed, key, anchor, plane, framed } of read) {
			if (!placed || stood.has(key)) continue;
			const stand = stands.get(key) ?? paintStand();
			stands.set(key, stand);
			keeps(stand.root, "data-lf-paint-plane", plane);
			const next = previous ? previous.root.nextElementSibling : root.firstElementChild;
			if (next !== stand.root) move(root, stand.root, next);
			const how = standIn(stand, placed, Boolean(anchor));
			stood.set(key, {
				stand,
				...how,
				visibility: framed ? "always" : "anchors-visible"
			});
			previous = stand;
		}
		for (const [key, stand] of stands) if (!stood.has(key)) {
			dropStand(stand);
			stands.delete(key);
		}
		for (const stand of stands.values()) stand.members = [];
		const placing = /* @__PURE__ */ new Set();
		for (const { node, target, placed, key, rect, anchor, at } of read) {
			placing.add(node);
			const { stand = null, ...how } = placed && stood.get(key) || {};
			const entry = entries.get(node) ?? {};
			if (entry.stand !== stand) node.remove();
			Object.assign(entry, {
				stand,
				stood: how,
				rect,
				anchor,
				at
			});
			entries.set(node, entry);
			stand?.members.push({
				node,
				target,
				entry
			});
		}
		for (const node of entries.keys()) if (!placing.has(node)) {
			node.remove();
			entries.delete(node);
		}
		for (const stand of stands.values()) seat(stand, true);
		return read.map(({ placed }) => placed);
	}
	function clear() {
		for (const stand of stands.values()) dropStand(stand);
		for (const node of entries.keys()) node.remove();
		stands.clear();
		entries.clear();
		near.clear();
		watched.clear();
		watching.clear();
		view.disconnect();
	}
	return {
		place,
		clear,
		near: nearBy,
		stands: (node) => Boolean(entries.get(node)?.stand)
	};
}
function vacate(stand) {
	if (!stand.frames.length && stand.carrier.parentElement === stand.root) return;
	stand.frames = cutFrames([], stand.frames, makeFrame);
	move(stand.root, stand.carrier, null);
}
function dropStand(stand) {
	vacate(stand);
	stand.root.remove();
}
function placement(surface, shaped, aboveSurfaces, clips = /* @__PURE__ */ new Map(), held = false) {
	const box = shownBox(surface);
	const pad = shaped ? SHAPE_STROKE_ROOM : 0;
	const rect = {
		left: box.left - pad,
		top: box.top - pad,
		right: box.right + pad,
		bottom: box.bottom + pad
	};
	const cuts = paintClips(surface, rect, clips, aboveSurfaces, held);
	const levels = [];
	if (cuts.window) levels.push({
		band: cuts.window,
		axes: {
			x: true,
			y: true
		},
		holder: null
	});
	for (const { box: holder, band, axes } of cuts.bands) levels.push({
		band,
		axes,
		holder
	});
	let shown = rect;
	for (const { band, axes } of levels) shown = intersect(shown, band, axes);
	return {
		rect,
		shown: hasArea(shown) ? shown : null,
		shapeKey: `${rect.right - rect.left}:${rect.bottom - rect.top}`,
		levels,
		surface,
		plane: cuts.plane
	};
}

//#endregion
//#region runtime/target-paint.js
var target_paint_exports = /* @__PURE__ */ __exportAll({
	aimLayer: () => aimLayer,
	clearAim: () => clearAim,
	geometryChanged: () => geometryChanged,
	labelAim: () => labelAim,
	locationLayer: () => locationLayer,
	locationStandsDown: () => locationStandsDown,
	mountTargetPaint: () => mountTargetPaint,
	paintAim: () => paintAim,
	paintLocation: () => paintLocation,
	paintTrace: () => paintTrace,
	shifted: () => shifted,
	targetTraceLayer: () => targetTraceLayer
});
const targetTraceBox = el("div", "lf-ui lf-target-trace");
const aimBox = el("div", "lf-ui lf-aim");
const locationBox = el("div", "lf-ui lf-location");
const traceStand = paintStand(targetTraceBox);
const aimStand = paintStand(aimBox);
const locationStand = paintStand(locationBox);
const targetTraceLayer = traceStand.root;
const aimLayer = aimStand.root;
const locationLayer = locationStand.root;
const aimShape = document.createElementNS(SVG_NS, "svg");
aimShape.classList.add("lf-aim-shape");
aimShape.setAttribute("aria-hidden", "true");
const aimMaskId = "lf-runtime-aim-shape-mask";
const targetTraceShape = document.createElementNS(SVG_NS, "svg");
targetTraceShape.classList.add("lf-target-trace-shape");
targetTraceShape.setAttribute("aria-hidden", "true");
let aimPlaced = null;
let aimStood = null;
let traceElement = null;
let traceSurface = null;
let traceGeometry = null;
let traceShapeKey = "";
let placementFrame = 0;
let geometryFrame = 0;
let geometryDirty = false;
let locationElement = null;
let locationFrame = 0;
let locationProjected = [];
const PROJECTED_LOCATION = "lf-projected-location";
function clearAim() {
	aimPlaced = aimStood = null;
	vacate(aimStand);
	aimBox.style.display = "none";
	aimBox.classList.toggle("lf-shaped", false);
	aimShape.replaceChildren();
	aimBox.removeAttribute("data-for");
	delete aimStand.root.dataset.lfPaintPlane;
}
function paintAim(element, surface) {
	surface ??= element;
	const geometry = surface && paintGeometry(surface);
	const placed = element && placement(surface, Boolean(geometry), inChrome(element));
	if (!placed?.shown) {
		clearAim();
		return null;
	}
	const shaped = paintShape(aimShape, geometry, placed.rect, {
		maskId: aimMaskId,
		veil: true
	});
	aimBox.classList.toggle("lf-shaped", shaped);
	if (!shaped) aimShape.replaceChildren();
	keeps(aimBox, "data-for", element.id);
	keeps(aimStand.root, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
	aimStood = standOver(aimStand, placed, shaped ? "0" : getComputedStyle(surface).borderRadius);
	aimPlaced = placed;
	return placed.shown;
}
function labelAim(node) {
	if (!aimPlaced) return;
	const { rect, shown, levels } = aimPlaced;
	const above = shown.top - node.offsetHeight - aimStood.room;
	const room = Math.max(0, ...levels.filter(({ axes }) => axes.y).map(({ band }) => band.top));
	const cutTop = shown.top > rect.top;
	const at = {
		left: Math.max(2, shown.left),
		top: !cutTop && above >= room ? above : shown.top + 2
	};
	const index = cutTop ? levels.findLastIndex(({ axes, band }) => axes.y && band.top === shown.top) : shown.left > rect.left ? levels.findLastIndex(({ axes, band }) => axes.x && band.left === shown.left) : -1;
	if (index >= 0) {
		const home = aimStand.frames[index];
		if (node.parentElement !== home) move(home, node, null);
		const { band } = levels[index];
		standBox(node, at, {
			anchored: false,
			origin: {
				x: band.left,
				y: band.top
			}
		});
		return;
	}
	if (node.parentElement !== aimStand.carrier) move(aimStand.carrier, node, null);
	standBox(node, at, aimStood, aimStood.anchor, aimStood.at);
}
function clearTrace() {
	traceElement = null;
	traceSurface = null;
	traceGeometry = null;
	traceShapeKey = "";
	vacate(traceStand);
	targetTraceBox.style.display = "none";
	targetTraceBox.classList.toggle("lf-shaped", false);
	targetTraceShape.replaceChildren();
	targetTraceBox.removeAttribute("data-for");
	delete traceStand.root.dataset.lfPaintPlane;
}
function drawTrace(element = traceElement, surface = traceSurface, rebuildGeometry = true) {
	if (!(element instanceof Element) || !(surface instanceof Element) || !element.isConnected || !surface.isConnected) {
		clearTrace();
		return;
	}
	const changed = element !== traceElement || surface !== traceSurface;
	const geometry = changed || rebuildGeometry ? paintGeometry(surface) : traceGeometry;
	const placed = placement(surface, Boolean(geometry), inChrome(element));
	traceElement = element;
	traceSurface = surface;
	traceGeometry = geometry;
	if (!placed.shown) {
		targetTraceBox.style.display = "none";
		return;
	}
	const { rect, shapeKey } = placed;
	let shaped = Boolean(geometry);
	if (shaped && (changed || rebuildGeometry || shapeKey !== traceShapeKey)) shaped = paintShape(targetTraceShape, geometry, rect);
	if (!shaped) targetTraceShape.replaceChildren();
	traceShapeKey = shaped ? shapeKey : "";
	targetTraceBox.classList.toggle("lf-shaped", shaped);
	keeps(targetTraceBox, "data-for", element.id || null);
	keeps(traceStand.root, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
	standOver(traceStand, placed, shaped ? "0" : getComputedStyle(surface).borderRadius);
}
function paintTrace(element, surface = element) {
	if (!element) {
		clearTrace();
		return;
	}
	const rebuild = geometryDirty || element !== traceElement || surface !== traceSurface;
	if (geometryDirty) {
		if (geometryFrame) cancelRender(geometryFrame);
		if (placementFrame) cancelRender(placementFrame);
		geometryFrame = placementFrame = 0;
		geometryDirty = false;
	}
	drawTrace(element, surface, rebuild);
}
function shifted() {
	relocate();
	if (placementFrame || geometryFrame || !traceElement) return;
	placementFrame = nextRender(() => {
		placementFrame = 0;
		if (traceElement) drawTrace(traceElement, traceSurface, false);
	});
}
function geometryChanged() {
	relocate();
	geometryDirty = true;
	if (placementFrame) cancelRender(placementFrame);
	placementFrame = 0;
	if (geometryFrame || !traceElement) return;
	geometryFrame = nextRender(() => {
		geometryFrame = 0;
		if (!geometryDirty) return;
		geometryDirty = false;
		if (traceElement) drawTrace(traceElement, traceSurface, true);
	});
}
function paintLocation(element) {
	locationElement = element;
	drawLocation();
}
const locationStandsDown = (element) => getComputedStyle(element).getPropertyValue("--lf-obligation-ring").trim() === "none";
const paintsOver = (element) => {
	const layer = nativeLayerHolding(element);
	return !layer || layer === nativeLayerHolding(locationStand.root);
};
function drawLocation() {
	const element = locationElement;
	const placed = element?.isConnected && !locationStandsDown(element) && paintsOver(element) && placement(element, false, inChrome(element));
	if (!placed?.shown) {
		projectLocation([]);
		vacate(locationStand);
		locationBox.style.display = "none";
		locationBox.removeAttribute("data-for");
		delete locationStand.root.dataset.lfPaintPlane;
		return;
	}
	projectLocation([element, ...shownParts(element)]);
	keeps(locationBox, "data-for", element.id || null);
	keeps(locationStand.root, "data-lf-paint-plane", inChrome(element) ? "chrome" : "page");
	standOver(locationStand, placed, getComputedStyle(element).borderRadius);
}
function projectLocation(boxes) {
	for (const box of locationProjected) if (!boxes.includes(box)) box.classList.toggle(PROJECTED_LOCATION, false);
	for (const box of boxes) box.classList.toggle(PROJECTED_LOCATION, true);
	locationProjected = boxes;
}
function relocate() {
	if (locationFrame || !locationElement) return;
	locationFrame = nextRender(() => {
		locationFrame = 0;
		drawLocation();
	});
}
function mountTargetPaint() {
	aimBox.append(aimShape);
	targetTraceBox.append(targetTraceShape);
}

//#endregion
//#region runtime/landing-scroll.js
const land = (box, by, behavior) => {
	startScroll(box);
	setScroll(box, {
		top: box.scrollTop + (by.top ?? 0),
		left: box.scrollLeft + (by.left ?? 0),
		behavior
	});
};
function scrollMargin(where, side = "Top") {
	if (!(where instanceof Range)) return Number.parseFloat(getComputedStyle(where)[`scrollMargin${side}`]) || 0;
	const edges = [where.startContainer.childNodes[where.startOffset], where.endContainer.childNodes[where.endOffset - 1]].filter((edge) => edge instanceof Element);
	return edges.length ? Math.max(...edges.map((edge) => scrollMargin(edge, side))) : 0;
}
function shownFor(where) {
	const ring = ringBox(where);
	if (ring === where) return where;
	const box = placeBox(ring);
	const room = roomAround(ring, where);
	return box.height <= room.height && box.width <= room.width ? ring : where;
}
const destinationBox = (where) => placeBox(shownFor(where));
const holderOf = (where) => placeHolder(shownFor(where));
const readingTop = (holder, box) => visibleBand(box, holder)?.top ?? landingBand(box).top;
function topMargin(where, box, holder = holderOf(where)) {
	const band = landingBand(box);
	return Math.max(scrollMargin(where), readingTop(holder, box) - band.top);
}
const landingRoom = (where, until = where) => roomAround(shownFor(where), where, until);
function roomAround(shown, where, until = where) {
	const holder = placeHolder(shown);
	const regions = [...scrollersOf(holder)];
	let { width, height } = shownWindow();
	for (let box = shown instanceof Range ? holder : renderedParent(shown); box instanceof Element; box = renderedParent(box)) {
		const band = (until === where || renderedUnder(until, box)) && landingBand(box);
		if (band) {
			const axes = box === pageScroller ? {
				x: true,
				y: true
			} : clippingAxes(getComputedStyle(box));
			const at = regions.indexOf(box);
			const clearance = at === 0 ? topMargin(where, box, holder) + scrollMargin(until, "Bottom") : at > 0 ? Math.max(0, readingTop(regions[at - 1], box) - band.top) : 0;
			if (axes.x) width = Math.min(width, band.right - band.left);
			if (axes.y) height = Math.min(height, band.bottom - band.top - clearance);
		}
		if (box === pageScroller || getComputedStyle(box).position === "fixed") break;
	}
	return {
		width,
		height
	};
}
function fitsWhole(where) {
	const box = destinationBox(where);
	const room = landingRoom(where);
	return box.height <= room.height && box.width <= room.width;
}
function seesWhole(where, box, out) {
	const seen = seenRect(shownFor(where), /* @__PURE__ */ new Map(), out);
	if (!seen) return false;
	const room = landingRoom(where);
	return (box.height > room.height || seen.top <= out.top && seen.bottom >= out.bottom) && (box.width > room.width || seen.left <= out.left && seen.right >= out.right);
}
function alreadyShown(where) {
	const box = destinationBox(where);
	return seesWhole(where, box, box);
}
function ringShown(where) {
	const box = destinationBox(where);
	const [top, right, bottom, left] = [
		"Top",
		"Right",
		"Bottom",
		"Left"
	].map((side) => scrollMargin(where, side));
	return seesWhole(where, box, new DOMRect(box.left - left, box.top - top, box.width + left + right, box.height + top + bottom));
}
function placementBy(where, block, box, margin) {
	const rect = destinationBox(where);
	const band = landingBand(box);
	const room = band.bottom - band.top;
	const place = block === "start" ? margin : block === "end" ? room - rect.height - scrollMargin(where, "Bottom") : Math.max((room - rect.height) / 2, margin);
	return block === "nearest" ? nearestScrollBy(rect.top - margin, rect.bottom + scrollMargin(where, "Bottom"), band.top, band.bottom) : rect.top - band.top - place;
}
function verticalTravel(box, movement) {
	const scale = scrollAxes(box).y.y;
	const local = scale === 0 ? 0 : reachable(box, movement / scale);
	return {
		local,
		moved: local * scale
	};
}
function readingBandMoves(where, holder, block) {
	const [box, ...around] = scrollersOf(holder);
	if (!box) return {
		moves: [],
		moved: 0
	};
	const rect = destinationBox(where);
	const margin = topMargin(where, box);
	let { top, bottom } = rect;
	if (block === "start") top -= margin;
	else if (block === "end") {
		top = bottom - 1;
		bottom += scrollMargin(where, "Bottom");
	}
	let { local, moved } = verticalTravel(box, placementBy(where, block, box, margin));
	const moves = [{
		box,
		local,
		moved
	}];
	let inner = box;
	for (const outer of around) {
		top -= moved;
		bottom -= moved;
		const band = landingBand(outer);
		if (!band) break;
		band.top = Math.max(band.top, readingTop(inner, outer));
		if (block === "start") bottom = Math.min(bottom, top + band.bottom - band.top);
		({local, moved} = verticalTravel(outer, nearestScrollBy(top, bottom, band.top, band.bottom)));
		moves.push({
			box: outer,
			local,
			moved
		});
		inner = outer;
	}
	return {
		moves,
		moved: moves.reduce((sum, move) => sum + move.moved, 0)
	};
}
function landedBox(where) {
	const rect = destinationBox(where);
	const { moved } = readingBandMoves(where, holderOf(where), "center");
	return new DOMRect(rect.x, rect.y - moved, rect.width, rect.height);
}
function scrollIntoReadingBand(where, holder, block, behavior) {
	for (const { box, local, moved } of readingBandMoves(where, holder, block).moves) if (Math.abs(moved) >= 1) land(box, { top: local }, behavior);
}
function scrollIntoView(where, { alignment = where, behavior = "auto", block = "start", within = null } = {}) {
	if (!where) return;
	const holder = holderOf(alignment);
	if (!holder) return;
	const targetScroller = within ? null : scrollersOf(holder).next().value;
	let inside = true;
	const start = holderOf(where);
	for (let box = start; box instanceof Element; box = renderedParent(box)) {
		if (box === targetScroller) inside = false;
		const band = landingBand(box);
		if (band) {
			const { left, right } = band;
			const destination = destinationBox(where);
			const byX = nearestScrollBy(destination.left - scrollMargin(where, "Left"), destination.right + scrollMargin(where, "Right"), left, right);
			const byY = inside ? placementBy(where, "nearest", box, topMargin(where, box, start)) : 0;
			const by = localScrollBy(box, {
				x: byX,
				y: byY
			});
			if (by.left || by.top) land(box, by, "instant");
		}
		if (box === within || box === pageScroller || getComputedStyle(box).position === "fixed") break;
	}
	if (targetScroller) scrollIntoReadingBand(alignment, holder, block, behavior);
}
onCurrentLocation((node, cause) => {
	if (cause !== "step" || !node) return;
	nextRender(() => {
		if (deepFocus() !== node) return;
		if (!ringShown(node)) scrollIntoView(node, { block: "nearest" });
		for (let box = node; box instanceof Element; box = renderedParent(box)) {
			if (!box.matches("[data-lf-obligation]")) continue;
			if (locationStandsDown(box)) continue;
			if (!ringShown(box)) scrollIntoView(box, { block: "nearest" });
			break;
		}
	});
});

//#endregion
//#region runtime/copy-control.js
function copyThroughSelection(value, trigger) {
	if (!value) return false;
	const selection = document.getSelection();
	const ranges = selection ? Array.from({ length: selection.rangeCount }, (_, i) => selection.getRangeAt(i)) : [];
	const before = focused();
	const field = document.createElement("textarea");
	field.value = value;
	field.style.cssText = "position: fixed; left: -9999px; top: 0";
	(nativeLayerHolding(trigger) ?? document.body).append(field);
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
function copyControl(className, { label = "", success, error, action = "copy", role = void 0 }) {
	const copy = role ? offeredActionElement(document.createElement("wa-copy-button"), role, className, void 0, { action }) : offer("wa-copy-button", className);
	const symbol = copy.querySelector(":scope > svg[data-lf-icon]") ?? actionElement(action, "lf-copy-icon");
	for (const [icon, slot] of [
		[symbol, "copy-icon"],
		[iconElement("check", "lf-copy-icon"), "success-icon"],
		[iconElement("cross", "lf-copy-icon"), "error-icon"]
	]) copy.append(Object.assign(icon, { slot }));
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
		const copied = copyThroughSelection(copy.value, copy);
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
export { SVG_NS, aimLayer, alreadyShown, copyControl, dropStand, fitsWhole, landedBox, landingRoom, locationLayer, mountTargetPaint, paintGeometry, paintLocation, paintSet, paintShape, paintStand, paintTrace, passOn, placement, restrictUserIntent, retainUserIntent, scrollIntoReadingBand, scrollIntoView, standOver, targetTraceLayer, target_paint_exports };