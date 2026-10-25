import { atLayoutPrecision, cancelRender, keeps, layoutPx, move, nextRender } from "./bundle-dom-move.js";
import { el, hasArea, headerCuts, intersect, nearObserver, nearWindow, paintClips, scrollsContent, shownBox } from "./bundle-layer-client.js";
import { inChrome } from "./bundle-passages.js";
import { anchorAt, anchorBox, anchorElement, anchorReaches, anchorReading, cutFrames, nameAnchor, scrollsWith } from "./bundle-content-layout.js";

//#region \0rolldown/runtime.js
var __defProp = Object.defineProperty;
var __exportAll = (all, no_symbols) => {
	let target = {};
	for (var name in all) {
		__defProp(target, name, {
			get: all[name],
			enumerable: true
		});
	}
	if (!no_symbols) {
		__defProp(target, Symbol.toStringTag, { value: "Module" });
	}
	return target;
};

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
	if (!(surface instanceof SVGElement)) return null;
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
	return {
		...stood,
		anchor,
		at
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
	mountTargetPaint: () => mountTargetPaint,
	paintAim: () => paintAim,
	paintTrace: () => paintTrace,
	shifted: () => shifted,
	targetTraceLayer: () => targetTraceLayer
});
const targetTraceBox = el("div", "lf-ui lf-target-trace");
const aimBox = el("div", "lf-ui lf-aim");
const traceStand = paintStand(targetTraceBox);
const aimStand = paintStand(aimBox);
const targetTraceLayer = traceStand.root;
const aimLayer = aimStand.root;
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
function clearAim() {
	aimPlaced = aimStood = null;
	vacate(aimStand);
	aimBox.style.display = "none";
	aimBox.classList.toggle("lf-shaped", false);
	aimShape.replaceChildren();
	aimBox.removeAttribute("data-for");
	delete aimStand.root.dataset.lfPaintPlane;
}
function paintAim(element, surface = null) {
	const geometry = surface ? paintGeometry(surface) : null;
	const placed = element && placement(surface ?? element, Boolean(geometry), inChrome(element));
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
	aimStood = standOver(aimStand, placed, getComputedStyle(surface ?? element).borderRadius);
	aimPlaced = placed;
	return placed.shown;
}
function labelAim(node) {
	if (!aimPlaced) return;
	const { rect, shown, levels } = aimPlaced;
	const above = shown.top - node.offsetHeight - 2;
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
	if (placementFrame || geometryFrame || !traceElement) return;
	placementFrame = nextRender(() => {
		placementFrame = 0;
		if (traceElement) drawTrace(traceElement, traceSurface, false);
	});
}
function geometryChanged() {
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
function mountTargetPaint() {
	aimBox.append(aimShape);
	targetTraceBox.append(targetTraceShape);
}

//#endregion
export { SVG_NS, aimLayer, dropStand, mountTargetPaint, paintGeometry, paintSet, paintShape, paintStand, paintTrace, placement, standOver, targetTraceLayer, target_paint_exports };