import { Z } from "./bundle-signals-core.js";
import { afterScript, renderedParent } from "./bundle-dom-move.js";
import { shownBox } from "./bundle-geometry.js";
import "./bundle-context.js";

//#region runtime/chrome.js
const chromeRoot = document.createElement("div");
chromeRoot.className = "lf-chrome";
const chromeForeground = document.createElement("dialog");
chromeForeground.className = "lf-ui lf-foreground";
chromeForeground.setAttribute("open", "");
chromeForeground.setAttribute("role", "presentation");

//#endregion
//#region runtime/element-frame.js
function elementAxes(source) {
	let matrix = new window.DOMMatrix();
	for (let node = source; node instanceof Element; node = renderedParent(node)) {
		const style = getComputedStyle(node);
		let local = new window.DOMMatrix();
		if (style.rotate !== "none") {
			const parts = style.rotate.split(" ");
			const angle = parts.pop();
			const degrees = parseFloat(angle) * (angle.endsWith("turn") ? 360 : angle.endsWith("grad") ? .9 : angle.endsWith("rad") ? 180 / Math.PI : 1);
			const axis = parts.length === 3 ? parts.map(Number) : parts[0] === "x" ? [
				1,
				0,
				0
			] : parts[0] === "y" ? [
				0,
				1,
				0
			] : [
				0,
				0,
				1
			];
			local = local.rotateAxisAngle(...axis, degrees);
		}
		if (style.scale !== "none") {
			const scale = style.scale.split(" ").map(Number);
			local = local.scale(scale[0], scale[1] ?? scale[0], scale[2] ?? 1);
		}
		if (style.transform !== "none") local = local.multiply(new window.DOMMatrix(style.transform));
		const zoom = Number(style.zoom);
		local = local.scale(zoom, zoom);
		matrix = local.multiply(matrix);
	}
	return {
		x: {
			x: matrix.a,
			y: matrix.b
		},
		y: {
			x: matrix.c,
			y: matrix.d
		}
	};
}
const nativePositions = /* @__PURE__ */ new WeakMap();
let positionProbe;
function nativePosition(source, position, horizontal, vertical) {
	const key = JSON.stringify([
		position,
		horizontal,
		vertical
	]);
	const prior = nativePositions.get(source);
	if (prior?.key === key) return prior.offset;
	const components = [];
	let depth = 0;
	let start = 0;
	for (let at = 0; at <= position.length; at++) {
		const character = position[at];
		if (character === "(") depth++;
		if (character === ")") depth--;
		if (at === position.length || character === " " && !depth) {
			if (at > start) components.push(position.slice(start, at));
			start = at + 1;
		}
	}
	const pixels = (value, space) => value.replace(/([-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?)%/gi, (_unit, percent) => `${Number(percent) * space / 100}px`);
	if (!positionProbe) {
		const measure = document.createElement("div");
		measure.className = "lf-ui";
		measure.dataset.lfRuntime = "";
		measure.inert = true;
		measure.style.cssText = "all:initial;position:fixed;visibility:hidden;contain:strict;width:0;height:0;left:0;top:0;pointer-events:none";
		const point = document.createElement("div");
		point.style.cssText = "all:initial;position:absolute;width:0;height:0";
		measure.append(point);
		positionProbe = {
			measure,
			point
		};
	}
	const { measure, point } = positionProbe;
	point.style.left = pixels(components[0], horizontal);
	point.style.top = pixels(components[1], vertical);
	document.body.append(measure);
	const resolved = getComputedStyle(point);
	const offset = [Number.parseFloat(resolved.left), Number.parseFloat(resolved.top)];
	measure.remove();
	nativePositions.set(source, {
		key,
		offset
	});
	return offset;
}
function elementFrame(source) {
	const box = shownBox(source);
	if (!box?.width || !box?.height) return null;
	if (source instanceof window.SVGGraphicsElement) {
		const view = source instanceof window.SVGSVGElement && source.viewBox.baseVal;
		const local = source instanceof window.SVGSVGElement ? view.width && view.height ? view : {
			x: 0,
			y: 0,
			width: Number.parseFloat(getComputedStyle(source).width),
			height: Number.parseFloat(getComputedStyle(source).height)
		} : source.getBBox();
		const screen = source.getScreenCTM();
		if (!screen) return null;
		return {
			box,
			width: local.width,
			height: local.height,
			matrix: new window.DOMMatrix([
				screen.a,
				screen.b,
				screen.c,
				screen.d,
				screen.e,
				screen.f
			])
		};
	}
	const layout = elementBorderFrame(source);
	if (!layout) return null;
	const { width, height, matrix } = layout;
	const style = getComputedStyle(source);
	const native = source instanceof window.HTMLImageElement ? [source.naturalWidth, source.naturalHeight] : source instanceof window.HTMLCanvasElement ? [source.width, source.height] : source instanceof window.HTMLVideoElement ? [source.videoWidth, source.videoHeight] : null;
	if (native) {
		if (!native[0] || !native[1]) return null;
		const edge = (side) => Number.parseFloat(style[`border${side}Width`]) + Number.parseFloat(style[`padding${side}`]);
		const contentWidth = width - edge("Left") - edge("Right");
		const contentHeight = height - edge("Top") - edge("Bottom");
		let sx = contentWidth / native[0];
		let sy = contentHeight / native[1];
		if (style.objectFit !== "fill") sx = sy = style.objectFit === "cover" ? Math.max(sx, sy) : style.objectFit === "none" ? 1 : Math.min(sx, sy, style.objectFit === "scale-down" ? 1 : Infinity);
		const [dx, dy] = nativePosition(source, style.objectPosition, contentWidth - native[0] * sx, contentHeight - native[1] * sy);
		if (![
			sx,
			sy,
			dx,
			dy
		].every(Number.isFinite) || !sx || !sy) return null;
		return {
			box,
			width: native[0],
			height: native[1],
			matrix: matrix.translate(edge("Left") + dx, edge("Top") + dy).scale(sx, sy)
		};
	}
	return {
		box,
		width,
		height,
		matrix
	};
}
function elementBorderFrame(source) {
	const box = shownBox(source);
	if (!box?.width || !box?.height) return null;
	const style = getComputedStyle(source);
	if (style.display === "contents") return {
		box,
		width: box.width,
		height: box.height,
		matrix: new window.DOMMatrix().translate(box.left, box.top)
	};
	const borderSize = (side, edges, fallback) => {
		const size = Number.parseFloat(style[side]);
		if (!Number.isFinite(size)) return fallback;
		return style.boxSizing === "border-box" ? size : size + edges.reduce((sum, edge) => sum + Number.parseFloat(style[`padding${edge}`]) + Number.parseFloat(style[`border${edge}Width`]), 0);
	};
	const width = borderSize("width", ["Left", "Right"], source.offsetWidth);
	const height = borderSize("height", ["Top", "Bottom"], source.offsetHeight);
	const { x, y } = elementAxes(source);
	const left = box.left - Math.min(0, width * x.x, height * y.x, width * x.x + height * y.x);
	const top = box.top - Math.min(0, width * x.y, height * y.y, width * x.y + height * y.y);
	return {
		box,
		width,
		height,
		matrix: new window.DOMMatrix([
			x.x,
			x.y,
			y.x,
			y.y,
			left,
			top
		])
	};
}
function scrollAxes(source) {
	return source === source.ownerDocument.scrollingElement ? {
		x: {
			x: 1,
			y: 0
		},
		y: {
			x: 0,
			y: 1
		}
	} : elementAxes(source);
}
function localScrollBy(source, { x, y }) {
	const axes = scrollAxes(source);
	const horizontal = source.scrollWidth > source.clientWidth;
	const vertical = source.scrollHeight > source.clientHeight;
	const along = (axis) => {
		return [...x && axis.x ? [x / axis.x] : [], ...y && axis.y ? [y / axis.y] : []].reduce((move, amount) => Math.abs(amount) > Math.abs(move) ? amount : move, 0);
	};
	const reach = (offset, current, minimum, maximum) => Math.max(minimum - current, Math.min(maximum - current, offset));
	const horizontalLimit = source.scrollWidth - source.clientWidth;
	const rtl = getComputedStyle(source).direction === "rtl";
	const reachLeft = (offset) => reach(offset, source.scrollLeft, rtl ? -horizontalLimit : 0, rtl ? 0 : horizontalLimit);
	const reachTop = (offset) => reach(offset, source.scrollTop, 0, source.scrollHeight - source.clientHeight);
	if (!horizontal) return {
		left: 0,
		top: vertical ? reachTop(along(axes.y)) : 0
	};
	if (!vertical) return {
		left: reachLeft(along(axes.x)),
		top: 0
	};
	const determinant = axes.x.x * axes.y.y - axes.x.y * axes.y.x;
	const left = (x * axes.y.y - y * axes.y.x) / determinant;
	const top = (y * axes.x.x - x * axes.x.y) / determinant;
	const reachableLeft = reachLeft(left);
	const reachableTop = reachTop(top);
	if (reachableLeft !== left && axes.y.y) return {
		left: reachableLeft,
		top: reachTop((y - reachableLeft * axes.x.y) / axes.y.y)
	};
	if (reachableTop !== top && axes.x.x) return {
		left: reachLeft((x - reachableTop * axes.y.x) / axes.x.x),
		top: reachableTop
	};
	return {
		left,
		top
	};
}

//#endregion
//#region runtime/page-controls.js
const EMPTY = Object.freeze([]);
const PAGE_CONTROL_RANK = Object.freeze({
	session: 10,
	claimant: 15,
	preview: 20,
	layer: 30,
	inspection: 32,
	share: 35,
	leaves: 40,
	latest: 50,
	map: 70,
	commands: 75,
	blanket: 80,
	versions: 90,
	keyboard: 95,
	exit: 120
});
const GROUPS = Object.freeze([
	"page",
	"navigate",
	"annotate",
	"keys"
]);
const rows = /* @__PURE__ */ new Map();
let sequence = 0;
const revision = Z(0);
const read = (value) => typeof value === "function" ? value() : value;
function registerPageControl(row) {
	if (!row.key || !Number.isFinite(row.rank) || !row.label || !row.group) throw new TypeError(`Page control ${row.key} needs a key, a numeric rank, a label and a group`);
	if (rows.has(row.key)) throw new TypeError(`Page control ${row.key} is registered`);
	rows.set(row.key, Object.freeze({
		...row,
		sequence: sequence++
	}));
	pageControlsChanged();
}
function pageControls() {
	revision.value;
	return [...rows.values()].sort((a, b) => a.rank - b.rank || a.sequence - b.sequence).filter((row) => read(row.offered) ?? true).map((row) => {
		const group = read(row.group);
		if (!GROUPS.includes(group)) throw new TypeError(`Page control ${row.key} is in group ${group}, not one of ${GROUPS.join(", ")}`);
		return Object.freeze({
			key: row.key,
			label: read(row.label),
			value: read(row.value) ?? "",
			title: read(row.title) ?? "",
			shortcut: read(row.shortcut) ?? EMPTY,
			group,
			copies: read(row.copies) ?? "",
			urgent: read(row.urgent) ?? null,
			exit: Boolean(row.exit),
			icon: read(row.icon) ?? null,
			disabled: Boolean(read(row.disabled)),
			press: row.press ?? null
		});
	});
}
const pageControlsChanged = () => afterScript(tell);
function tell() {
	revision.value = revision.peek() + 1;
}

//#endregion
export { PAGE_CONTROL_RANK, chromeForeground, chromeRoot, elementFrame, localScrollBy, pageControls, pageControlsChanged, registerPageControl, scrollAxes };