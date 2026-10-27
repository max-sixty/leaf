import { __exportAll } from "./bundle-rolldown-runtime.js";
import { TEXT_FIELD, afterSettling, atLayoutPrecision, cancelRender, keeps, layoutPx, move, nextRender, onUserInput } from "./bundle-dom-move.js";
import { el } from "./bundle-layer-client.js";
import { hasArea, headerCuts, intersect, nearObserver, nearWindow, paintClips, scrollsContent, shownBox } from "./bundle-geometry.js";
import { anchorAt, anchorBox, anchorElement, anchorReaches, anchorReading, contentRides, cutFrames, nameAnchor, scrollsWith } from "./bundle-content-layout.js";
import { inChrome } from "./bundle-passages.js";
import { motionEasing, motionPlays, motionTime, playMotion } from "./bundle-media.js";

//#region runtime/target-paint-geometry.js
const SVG_NS = "http://www.w3.org/2000/svg";
const SHAPE_STROKE_ROOM = 2;
const paints$1 = (shape, property) => {
	const style = getComputedStyle(shape);
	return shape.checkVisibility({
		opacityProperty: true,
		visibilityProperty: true
	}) && style[property] !== "none" && Number.parseFloat(style[`${property}Opacity`]) !== 0 && (property !== "stroke" || Number.parseFloat(style.strokeWidth) > 0);
};
function paintGeometry(surface) {
	if (!(surface instanceof SVGElement)) return null;
	const geometry = [surface, ...surface.querySelectorAll("*")].filter((child) => child instanceof SVGGeometryElement);
	const fill = geometry.filter((shape) => paints$1(shape, "fill"));
	const paintedStroke = geometry.filter((shape) => paints$1(shape, "stroke"));
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
	if (box) root.style.setProperty("--lf-paint-outset", "var(--focus-ring-w)");
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
	shifted: () => shifted$1,
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
	aimStood = standOver(aimStand, placed, shaped ? "0" : getComputedStyle(surface ?? element).borderRadius);
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
function shifted$1() {
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
//#region runtime/box-motion.js
let gesture = null;
let gestures = 0;
function beginGesture(event) {
	if (![
		"keydown",
		"pointerdown",
		"input",
		"touchstart",
		"click"
	].includes(event.type)) return;
	gesture = event.type === "input" ? "typing" : "press";
	const own = ++gestures;
	afterSettling(() => {
		if (gestures === own) gesture = null;
	});
}
let listening = false;
function listen() {
	if (listening) return;
	listening = true;
	onUserInput(beginGesture);
	window.addEventListener("click", beginGesture, {
		capture: true,
		passive: true
	});
}
const liftReach = (element, level) => {
	const lift = getComputedStyle(element);
	const [drop, blur] = ["drop", "blur"].map((part) => Number.parseFloat(lift.getPropertyValue(`--raise-${level}-${part}`)));
	return drop + 2 * blur;
};
const near = (a, b) => Math.abs(a - b) < .5;
const boxOf = (rect) => ({
	left: rect.left,
	top: rect.top,
	right: rect.right,
	bottom: rect.bottom
});
const width = (box) => box.right - box.left;
const height = (box) => box.bottom - box.top;
const same = (a, b) => [
	"left",
	"top",
	"right",
	"bottom"
].every((side) => near(a[side], b[side]));
const between = (from, to, progress) => Object.fromEntries(Object.keys(to).map((side) => [side, from[side] + (to[side] - from[side]) * progress]));
const shifted = (box, dx, dy) => ({
	left: box.left + dx,
	top: box.top + dy,
	right: box.right + dx,
	bottom: box.bottom + dy
});
const insetOf = ([top, right, bottom, left], radius = 0) => `inset(${top}px ${right}px ${bottom}px ${left}px round ${radius}px)`;
const clipFrame = (sides, radius = 0) => ({
	clipPath: `inset(var(--lf-box-cut) round ${radius}px)`,
	"--lf-box-cut": sides.map((side) => `${side}px`).join(" ")
});
const radiusOf = (style) => Number.parseFloat(style.borderTopLeftRadius) || 0;
const seeThrough = (color) => /^(transparent|rgba\(.*,\s*0\))$/.test(color);
const paints = (style) => !seeThrough(style.backgroundColor) || style.backgroundImage !== "none" || style.boxShadow !== "none" || [
	"Top",
	"Right",
	"Bottom",
	"Left"
].some((side) => Number.parseFloat(style[`border${side}Width`]) > 0);
const rings = (style) => style.outlineStyle !== "none" && Number.parseFloat(style.outlineWidth) > 0;
function boxMotion({ root, box, surface: surfaceClass, lift, outset, observer, held = () => null }) {
	listen();
	const layer = (name) => {
		const node = document.createElement("div");
		node.className = name;
		return node;
	};
	const room = layer(`lf-box-ground ${surfaceClass}`);
	room.setAttribute("aria-hidden", "true");
	const [ring, fill, ringLayer, ringFill] = [
		"lf-box-ring",
		"lf-box-fill",
		"lf-box-moving-ring",
		"lf-box-fill"
	].map(layer);
	room.append(ring, fill, ringLayer, ringFill);
	const shadowReach = () => liftReach(room, lift);
	const surface = () => [
		[
			room,
			shadowReach(),
			`filter: drop-shadow(var(--raise-${lift})); `
		],
		[
			ring,
			outset,
			""
		],
		[
			fill,
			outset - 1,
			""
		]
	];
	let sent = -1;
	const theirs = () => gesture !== null && sent === gestures ? "send" : gesture;
	let rests = null;
	let frame = null;
	let timing = null;
	let motions = /* @__PURE__ */ new Map();
	let running = [];
	let shapeUntil = 1;
	let rtl = false;
	let streamFrom = /* @__PURE__ */ new Map();
	let streams = /* @__PURE__ */ new Map();
	let stopStreaming = new AbortController();
	let fieldScrolls = /* @__PURE__ */ new Map();
	const noteFieldScrolls = () => {
		for (const field of fieldScrolls.keys()) fieldScrolls.set(field, field.scrollTop);
	};
	onUserInput((event) => {
		if (event.type !== "input") noteFieldScrolls();
	});
	root.addEventListener("lf-before-edit", noteFieldScrolls, { passive: true });
	const forget = () => {
		rests = null;
	};
	addEventListener("resize", forget);
	function rebase() {
		const at = boxOf(root.getBoundingClientRect());
		const edges = held();
		const dx = frame && edges ? at[edges.x] - frame[edges.x] : 0;
		const dy = frame && edges ? at[edges.y] - frame[edges.y] : 0;
		frame = at;
		if (near(dx, 0) && near(dy, 0)) return;
		if (rests) rests = new Map([...rests].map(([element, rest]) => [element, shifted(rest, dx, dy)]));
		for (const moving of motions.values()) {
			moving.from = shifted(moving.from, dx, dy);
			moving.to = shifted(moving.to, dx, dy);
		}
		for (const then of streamFrom.values()) then.top += dy;
		for (const riding of streams.values()) {
			riding.from += dy;
			riding.to += dy;
		}
	}
	const interpolate = (from, to, progress) => {
		const rect = between(from, to, progress);
		const shape = Math.min(1, progress / shapeUntil);
		const w = width(from) + (width(to) - width(from)) * shape;
		const h = height(from) + (height(to) - height(from)) * shape;
		if (rtl) rect.left = rect.right - w;
		else rect.right = rect.left + w;
		rect.top = rect.bottom - h;
		return rect;
	};
	const translations = /* @__PURE__ */ new Map();
	const restoreTranslations = (keep = /* @__PURE__ */ new Set()) => {
		for (const [element, { value, priority }] of translations) {
			if (keep.has(element)) continue;
			element.style.setProperty("translate", value, priority);
			translations.delete(element);
		}
	};
	let observed = /* @__PURE__ */ new Set();
	let wholes = /* @__PURE__ */ new WeakSet();
	const insideWhole = (node) => {
		for (let up = node.parentElement; up && up !== root; up = up.parentElement) if (wholes.has(up)) return true;
		return false;
	};
	function carriedBy(progress) {
		const offsets = /* @__PURE__ */ new Map();
		const offset = (carrier) => {
			if (!offsets.has(carrier)) {
				const { from, to, carries } = motions.get(carrier);
				const now = between(from, to, progress);
				offsets.set(carrier, carries.map((edge) => now[edge] - to[edge]));
			}
			return offsets.get(carrier);
		};
		return (element) => {
			for (let up = element; up && up !== root; up = up.parentElement) if (motions.get(up)?.carries) return offset(up);
			return [0, 0];
		};
	}
	function read(element, into, carried) {
		if (element === room) return;
		const style = getComputedStyle(element);
		if (style.display === "contents") {
			for (const child of element.children) read(child, into, carried);
			return;
		}
		if (!element.checkVisibility()) return;
		if (style.positionAnchor.startsWith("--")) return;
		const [dx, dy] = carried(element);
		const part = {
			element,
			style,
			box: shifted(boxOf(element.getBoundingClientRect()), -dx, -dy),
			window: style.position === "fixed",
			parts: []
		};
		part.scrolls = /auto|scroll/.test(`${style.overflowX} ${style.overflowY}`);
		part.whole = element !== root && element.localName.includes("-") || element instanceof SVGElement || part.scrolls || element.childElementCount === 0 || [...element.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.data.trim());
		if (!part.whole) for (const child of element.children) read(child, part.parts, carried);
		part.holdsWindow = part.parts.some((inner) => inner.window || inner.holdsWindow);
		if (part.whole) wholes.add(element);
		into.push(part);
	}
	function drawn(progress, carried) {
		const at = /* @__PURE__ */ new Map();
		for (const [element, rest] of rests) {
			const moving = motions.get(element);
			if (moving?.revealed && progress < 1) continue;
			at.set(element, moving ? (element === box ? interpolate : between)(moving.from, moving.to, progress) : shifted(rest, ...carried(element)));
		}
		return at;
	}
	const arrived = /* @__PURE__ */ new Set();
	let watching = 0;
	const watch = () => {
		watching ||= nextRender(() => {
			watching = 0;
			const parts = /* @__PURE__ */ new Set([
				box,
				...rests?.keys() ?? [],
				...arrived
			]);
			arrived.clear();
			for (const element of observed) if (!parts.has(element)) observer.unobserve(element);
			for (const element of parts) if (!observed.has(element)) observer.observe(element);
			observed = parts;
		});
	};
	new MutationObserver((records) => {
		for (const record of records) for (const node of record.type === "childList" ? record.addedNodes : [record.target]) if (node instanceof Element && !insideWhole(node)) arrived.add(node);
		watch();
	}).observe(root, {
		subtree: true,
		childList: true,
		attributeFilter: ["hidden"]
	});
	function follow({ duration = motionTime("--lf-motion-box-resize", box), easing = motionEasing("--lf-motion-box-ease", box) } = {}, compact = false) {
		timing = {
			duration,
			easing
		};
		rebase();
		const progress = running[0]?.effect.getComputedTiming().progress ?? 1;
		const carried = carriedBy(progress);
		const parts = [];
		wholes = /* @__PURE__ */ new WeakSet();
		read(root, parts, carried);
		const next = /* @__PURE__ */ new Map();
		const note = (part) => {
			next.set(part.element, part.box);
			part.parts.forEach(note);
		};
		parts.forEach(note);
		watch();
		if (!(theirs() === "send" && [...streamFrom].some(([scroller, then]) => !(streams.has(scroller) && progress < 1) && scroller.contains(then.child) && !near(then.child.getBoundingClientRect().top, then.top))) && rests?.size === next.size && [...next].every(([element, at]) => rests.has(element) && same(rests.get(element), at))) return;
		for (const scroller of streams.keys()) contentRides(scroller, false);
		for (const animation of running) animation.cancel();
		running = [];
		if (!next.has(box)) {
			restoreTranslations();
			rests = null;
			motions = /* @__PURE__ */ new Map();
			streams = /* @__PURE__ */ new Map();
			return;
		}
		const was = motionPlays() && rests ? drawn(progress, carried) : null;
		const gesture = theirs();
		const framed = new Set([...motions].filter(([, moving]) => moving.frames).map(([element]) => element));
		const before = rests;
		const streamed = /* @__PURE__ */ new Map();
		if (progress < 1) for (const [scroller, { child, from, to }] of streams) streamed.set(scroller, {
			child,
			top: from + (to - from) * progress
		});
		streams = /* @__PURE__ */ new Map();
		const moved = motions;
		motions = /* @__PURE__ */ new Map();
		rests = next;
		const scrolledFrom = fieldScrolls;
		fieldScrolls = new Map([...rests.keys()].filter((element) => element.matches(TEXT_FIELD)).map((element) => [element, element.scrollTop]));
		const space = boxOf(room.getBoundingClientRect());
		const outline = (at, grow, radius) => [[
			at.top - space.top - grow,
			space.right - at.right - grow,
			space.bottom - at.bottom - grow,
			at.left - space.left - grow
		], radius + grow];
		const boxAt = rests.get(box);
		const boxStyle = getComputedStyle(box);
		const boxRadius = radiusOf(boxStyle);
		for (const [layer, reach, paint] of surface()) keeps(layer, "style", `${paint}clip-path: ${insetOf(...outline(boxAt, reach, boxRadius))}`);
		if (!was?.has(box)) {
			restoreTranslations();
			return;
		}
		const boxFrom = was.get(box);
		shapeUntil = compact ? .55 : 1;
		rtl = getComputedStyle(box).direction === "rtl";
		const start = (element, keyframes) => running.push(playMotion(element, keyframes, {
			duration,
			easing
		}));
		const contour = (from, to, grow, radius, compact = false) => {
			const frames = [clipFrame(...outline(from, grow, radius))];
			if (compact) frames.push({
				...clipFrame(...outline(interpolate(from, to, shapeUntil), grow, radius)),
				offset: shapeUntil
			});
			frames.push(clipFrame(...outline(to, grow, radius)));
			return frames;
		};
		const hold = (element, property, value) => start(element, [{ [property]: value }, { [property]: value }]);
		const translated = /* @__PURE__ */ new Set();
		const move = (element, dx, dy) => {
			const [carriedX, carriedY] = carriedBy(0)(element.parentElement);
			dx -= carriedX;
			dy -= carriedY;
			if (!translations.has(element)) translations.set(element, {
				value: element.style.getPropertyValue("translate"),
				priority: element.style.getPropertyPriority("translate")
			});
			translated.add(element);
			element.style.setProperty("translate", "var(--lf-box-carry)");
			start(element, [{ "--lf-box-carry": `${dx}px ${dy}px` }, { "--lf-box-carry": "0px 0px" }]);
		};
		const cutFrom = (element, cut, radius = 0) => start(element, [clipFrame(cut, radius), clipFrame([
			0,
			0,
			0,
			0
		], radius)]);
		function carry(part, from) {
			const dx = from.left - part.box.left;
			const dy = from.top - part.box.top;
			const [carriedX, carriedY] = carriedBy(0)(part.element.parentElement);
			if (near(dx, carriedX) && near(dy, carriedY)) return;
			motions.set(part.element, {
				from,
				to: part.box,
				carries: ["left", "top"]
			});
			move(part.element, dx, dy);
		}
		function carryContent(part, from) {
			const to = part.box;
			if (part.scrolls && !part.element.matches(TEXT_FIELD)) {
				grow(part, from);
				if (gesture === "send") streamContent(part);
				return;
			}
			const emptied = gesture === "send" || part.element.matches(":state(placeholder-shown)");
			const edgeBy = (start, end, length) => emptied && length(to) < length(from) - .5 && near(from[end], to[end]) && !near(from[start], to[start]) ? end : start;
			const carries = [rtl ? edgeBy("right", "left", width) : edgeBy("left", "right", width), edgeBy("top", "bottom", height)];
			const dx = from[carries[0]] - to[carries[0]];
			let dy = from[carries[1]] - to[carries[1]];
			const cut = () => [
				from.top - (to.top + dy),
				to.right + dx - from.right,
				to.bottom + dy - from.bottom,
				from.left - (to.left + dx)
			];
			if (!part.element.matches(TEXT_FIELD) || !((rtl ? dx <= 0 : dx >= 0) && dy >= 0) && gesture !== "typing") {
				motions.set(part.element, {
					from,
					to,
					carries
				});
				move(part.element, dx, dy);
				cutFrom(part.element, cut(), radiusOf(part.style));
				return;
			}
			const gaveUp = part.element.scrollHeight <= part.element.clientHeight && !emptied ? scrolledFrom.get(part.element) ?? 0 : 0;
			const left = (moved.get(part.element)?.gaveUp ?? 0) * (1 - progress);
			dy -= gaveUp + left;
			motions.set(part.element, {
				from,
				to,
				gaveUp: gaveUp + left
			});
			const reach = Math.max(0, rtl ? dx : -dx, -dy);
			if (reach > 0) hold(part.element, "overflow", "visible");
			start(part.element, [{
				"--lf-field-carry": `${dx}px ${dy}px`,
				"--lf-field-cut": cut().map((side) => `${side}px`).join(" "),
				"--lf-field-reach": `${reach}px`
			}, {
				"--lf-field-carry": "0px 0px",
				"--lf-field-cut": "0px 0px 0px 0px",
				"--lf-field-reach": `${reach}px`
			}]);
		}
		function grow(part, from) {
			const to = part.box;
			motions.set(part.element, {
				from,
				to
			});
			const drawnTo = shifted(to, ...carriedBy(0)(part.element.parentElement));
			cutFrom(part.element, [
				from.top - drawnTo.top,
				drawnTo.right - from.right,
				drawnTo.bottom - from.bottom,
				from.left - drawnTo.left
			].map((inset) => Math.max(0, inset)), radiusOf(part.style));
		}
		function reveal(part, frame, siblings) {
			const to = part.box;
			if (part.holdsWindow) {
				motions.set(part.element, {
					from: to,
					to,
					revealed: true
				});
				for (const inner of part.parts) reveal(inner, frame, siblings);
				return;
			}
			const carriedTo = shifted(to, ...carriedBy(0)(part.element.parentElement));
			const side = (inset, beyond) => beyond ? 0 : Math.max(0, inset);
			const from = [
				side(frame.from.top - carriedTo.top, to.top < frame.to.top - .5),
				side(carriedTo.right - frame.from.right, to.right > frame.to.right + .5),
				side(carriedTo.bottom - frame.from.bottom, to.bottom > frame.to.bottom + .5),
				side(frame.from.left - carriedTo.left, to.left < frame.to.left - .5)
			];
			const end = [
				0,
				0,
				0,
				0
			];
			const overlaps = (a, b, low, high) => a[low] < b[high] && b[low] < a[high];
			for (const sibling of siblings) {
				const moving = motions.get(sibling.element);
				if (!moving || moving.revealed) continue;
				const { from: then, to: at } = moving;
				const across = overlaps(at, to, "top", "bottom");
				const along = overlaps(at, to, "left", "right");
				[
					along && {
						then: then.bottom - carriedTo.top,
						rest: at.bottom - to.top
					},
					across && {
						then: carriedTo.right - then.left,
						rest: to.right - at.left
					},
					along && {
						then: carriedTo.bottom - then.top,
						rest: to.bottom - at.top
					},
					across && {
						then: then.right - carriedTo.left,
						rest: at.right - to.left
					}
				].forEach((reach, index) => {
					if (reach && reach.rest <= .5 && reach.then > from[index]) {
						from[index] = reach.then;
						end[index] = reach.rest;
					}
				});
			}
			if (from.every((inset) => near(inset, 0))) return;
			motions.set(part.element, {
				from: to,
				to,
				revealed: true
			});
			start(part.element, [clipFrame(from), clipFrame(end)]);
		}
		function rise(part, frame, siblings) {
			const to = part.box;
			const dy = boxFrom.top - boxAt.top;
			if (dy < .5 || to.top >= boxFrom.top - .5) return reveal(part, frame, siblings);
			motions.set(part.element, {
				from: shifted(to, 0, dy),
				to,
				carries: ["left", "top"]
			});
			move(part.element, 0, dy);
			const first = Math.max(0, to.bottom + dy - boxFrom.top);
			if (first < .5) return;
			const clear = 1 - Math.max(0, boxFrom.top - to.bottom) / dy;
			const frames = [clipFrame([
				0,
				0,
				first,
				0
			])];
			if (clear > 0 && clear < 1) frames.push({
				...clipFrame([
					0,
					0,
					0,
					0
				]),
				offset: clear
			});
			frames.push(clipFrame([
				0,
				0,
				0,
				0
			]));
			start(part.element, frames);
		}
		function streamContent(part) {
			const scroller = part.element;
			const then = streamed.get(scroller) ?? streamFrom.get(scroller);
			if (!then || !scroller.contains(then.child)) return;
			const to = then.child.getBoundingClientRect().top - carriedBy(0)(then.child)[1];
			const dy = then.top - to;
			if (Math.abs(dy) < .5) return;
			contentRides(scroller, true);
			hold(scroller, "overflowAnchor", "none");
			streams.set(scroller, {
				child: then.child,
				from: then.top,
				to
			});
			for (const child of scroller.children) if (child.checkVisibility()) move(child, 0, dy);
			for (const stuck of scroller.querySelectorAll("*")) {
				const style = getComputedStyle(stuck);
				if (style.position !== "sticky") continue;
				for (const [side, against] of [["top", -dy], ["bottom", dy]]) if (style[side] !== "auto") {
					const at = Number.parseFloat(style[side]);
					start(stuck, [{ [side]: `${at + against}px` }, { [side]: `${at}px` }]);
				}
			}
		}
		function drawRing(element, style, from, to, compact = false) {
			const offset = Number.parseFloat(style.outlineOffset);
			const reach = Number.parseFloat(style.outlineWidth) + offset;
			const radius = radiusOf(style);
			const colour = seeThrough(style.backgroundColor) ? null : style.backgroundColor;
			keeps(ringLayer, "style", `background: ${style.outlineColor}`);
			keeps(ringFill, "style", colour && `background: ${colour}`);
			hold(element, "outlineColor", "transparent");
			if (colour) hold(element, "backgroundColor", "transparent");
			for (const [layer, grown] of [[ringLayer, reach], [ringFill, offset]]) start(layer, contour(from, to, grown, radius, compact));
		}
		function streamWithin(part) {
			if (part.scrolls) streamContent(part);
			else part.parts.forEach(streamWithin);
		}
		function place(part, frame, siblings = []) {
			const { element, style, box: to } = part;
			const from = was.get(element);
			if (!from) return gesture === "send" ? rise(part, frame, siblings) : reveal(part, frame, siblings);
			const rest = before.get(element);
			const sized = !framed.has(element) && near(width(rest), width(to)) && near(height(rest), height(to));
			let within = frame;
			if (element !== box && element !== root) {
				const carries = gesture !== null;
				if (sized && !part.holdsWindow) {
					if (!carries) return reveal(part, frame, siblings);
					carry(part, from);
					if (gesture === "send") streamWithin(part);
					return;
				}
				if (part.whole) return carries ? carryContent(part, from) : grow(part, from);
				if (!same(from, to)) within = {
					from,
					to
				};
				if (!sized && rings(style)) drawRing(element, style, from, to);
				else if (!sized && paints(style) && !part.holdsWindow) carries ? carryContent(part, from) : grow(part, from);
				if (!same(from, to)) motions.set(element, {
					...motions.get(element),
					from,
					to,
					frames: true
				});
			}
			const placed = [...part.parts].sort((a, b) => Number(!was.has(a.element)) - Number(!was.has(b.element)));
			for (const inner of placed) place(inner, within, part.parts);
		}
		for (const part of parts) place(part, {
			from: boxFrom,
			to: boxAt
		});
		for (const scroller of streamed.keys()) if (!streams.has(scroller) && rests.has(scroller)) streamContent({ element: scroller });
		restoreTranslations(translated);
		if (running.length === 0 && same(boxFrom, boxAt)) return;
		motions.set(box, {
			from: boxFrom,
			to: boxAt
		});
		for (const [layer, reach] of surface()) start(layer, contour(boxFrom, boxAt, reach, boxRadius, compact));
		if (rings(boxStyle)) drawRing(box, boxStyle, boxFrom, boxAt, compact);
		else hold(box, "outlineColor", "transparent");
		hold(box, "backgroundColor", "transparent");
		hold(box, "overflow", "visible");
		const animations = running;
		animations.at(-1).onfinish = () => {
			if (running !== animations) return;
			restoreTranslations();
			for (const scroller of streams.keys()) contentRides(scroller, false);
		};
	}
	return {
		ground: room,
		shadowReach,
		follow,
		theirs,
		stream() {
			if (gesture === null) return;
			sent = gestures;
			rebase();
			streamFrom = /* @__PURE__ */ new Map();
			stopStreaming.abort();
			stopStreaming = new AbortController();
			const { signal } = stopStreaming;
			for (const element of rests?.keys() ?? []) {
				if (element.matches(TEXT_FIELD) || !/auto|scroll/.test(getComputedStyle(element).overflowY)) continue;
				const child = [...element.children].find((node) => node.checkVisibility());
				if (!child) continue;
				streamFrom.set(element, {
					child,
					top: child.getBoundingClientRect().top
				});
				element.addEventListener("scroll", () => {
					if (theirs() === "send" && timing) follow(timing);
					else stopStreaming.abort();
				}, {
					signal,
					passive: true
				});
				for (const type of ["wheel", "touchstart"]) element.addEventListener(type, () => stopStreaming.abort(), {
					signal,
					passive: true
				});
			}
		},
		placed(place) {
			rebase();
			place();
			frame = boxOf(root.getBoundingClientRect());
		},
		outline() {
			const moving = motions.get(box);
			const progress = running[0]?.effect.getComputedTiming().progress ?? 1;
			if (moving && progress < 1) return interpolate(moving.from, moving.to, progress);
			return boxOf(box.getBoundingClientRect());
		},
		drawnAt(rect) {
			frame = boxOf(root.getBoundingClientRect());
			motions = /* @__PURE__ */ new Map();
			rests = /* @__PURE__ */ new Map([[box, boxOf(rect)]]);
		},
		forget
	};
}

//#endregion
export { SVG_NS, aimLayer, boxMotion, dropStand, mountTargetPaint, paintGeometry, paintSet, paintShape, paintStand, paintTrace, placement, standOver, targetTraceLayer, target_paint_exports };