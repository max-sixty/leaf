import { LAYOUT, afterScript, atLayoutPrecision, cancelRender, inlineStyle, keeps, layoutPx, nextRender, renderedParent, renderedUnder, sizeObserver, skipped, under, upFrom } from "./bundle-portable.js";
import { TAB_STOP, coarsePointer, hoveringPointer, move, renderedChildren } from "./bundle-layer-stack.js";
import { afterPresentation, anchorBox, anchorElement, anchorFor, anchorName, anchorReading, boundedBlockOf, carriedAnchor, containingReadingRegionFor, cutFrames, headerLevels, moveScrollerBy, nameAnchor, pageScroller, passageBoxes, pointBand, proseMeasure, proseRect, railStands, scrollAxes, scrollLimit, scrollerFor, scrollsWith, targetRange, targetSegments } from "./bundle-content-layout.js";
import { clamp, clippedContents, clippedRect, clippingAxes, overlaps, overlapsAcross, scrollsContent, shellRight, shownBand, shownExtent, shownParts, shownRect, shownWindow, union, visualViewport } from "./bundle-geometry.js";
import { inChrome, layoutBox } from "./bundle-passages.js";
import { visibleTargetParts } from "./bundle-visible-target-parts.js";

//#region runtime/annotation-overlay/margin-placement.js
function rowPlacement({ railStands, besideRail, blockRight, railInner, half, noted }) {
	if (!railStands || !besideRail || noted) return "pin";
	return blockRight - half > railInner ? "pin" : "rail";
}
function packRow({ rect, held, pushed = 0 }, gap, occupied = []) {
	const height = rect.bottom - rect.top;
	let top = rect.top + (held ? pushed : 0);
	const across = occupied.filter((box) => overlapsAcross(box, rect)).toSorted((a, b) => a.top - b.top);
	for (const box of across) if (top < box.bottom + gap && top + height > box.top - gap) top = box.bottom + gap;
	return top - rect.top;
}
function arrivals(previous, rows, pass) {
	const next = /* @__PURE__ */ new Map();
	for (const { row, at } of rows) {
		const first = previous.get(row) ?? (at === null ? void 0 : previous.get(at)) ?? pass;
		next.set(row, first);
		if (at) next.set(at, first);
	}
	return next;
}
const inSeatingOrder = (rows) => [...rows].sort((a, b) => Number(Boolean(b.held)) - Number(Boolean(a.held)) || (a.came ?? 0) - (b.came ?? 0) || a.rect.top - b.rect.top);
function seatsBy(parts, home, inline, passage, { cover, beside }, size, gap) {
	const height = home.bottom - home.top;
	const box = union(parts) ?? home;
	const end = parts.at(-1);
	const outside = (part) => {
		const seat = {
			left: part.right + gap,
			right: part.right + gap + size,
			top: part.top,
			bottom: part.top + height
		};
		return beside({
			...seat,
			bottom: Math.min(seat.bottom, part.bottom)
		}) ? null : seat;
	};
	const under = {
		left: Math.min(home.left, box.left),
		right: home.right,
		top: box.bottom + gap,
		bottom: box.bottom + gap + height
	};
	const belowClear = !cover.some((box) => overlaps(box, under));
	return {
		before: [outside(box), ...inline && end ? [outside(end)] : []],
		home: {
			...home,
			left: home.right - size
		},
		after: [{
			left: passage ? box.right : home.right - size,
			right: passage ? box.right + size : home.right,
			top: box.top - gap - height,
			bottom: box.top - gap
		}, ...belowClear ? [{
			...under,
			left: home.right - size
		}] : []]
	};
}
function seatRow(pin, { gap, occupied = [] }) {
	const open = {
		seats: pin.seats,
		bounds: pin.bounds,
		folded: false
	};
	const fold = pin.folds;
	const closed = fold && {
		seats: fold.seats,
		bounds: {
			...pin.bounds,
			left: Math.min(pin.bounds.left + fold.open - (fold.seats.home.right - fold.seats.home.left), pin.bounds.right - (fold.seats.home.right - fold.seats.home.left))
		},
		folded: true
	};
	let posture = pin.folded && closed ? closed : open;
	const held = pin.held && {
		...pin.held,
		left: posture.folded ? pin.held.right - (posture.seats.home.right - posture.seats.home.left) : pin.held.left
	};
	let rect = held && inside(held, posture.bounds) ? held : null;
	const avoiding = [...pin.cover, ...occupied];
	const pressed = [...pin.controls, ...occupied];
	const lowered = (seats) => [
		...seats.before,
		slid(seats.home, avoiding, gap, "down", pin.floor),
		...seats.after
	];
	const asideOf = (seats, bounds, past = pressed) => slid(boundedHome(seats.home, bounds), past, gap, "left", bounds.left);
	const clearAside = (seats, bounds) => pinSpot([asideOf(seats, bounds, avoiding)], [], bounds);
	const take = (next, seat) => {
		if (!seat) return false;
		posture = next;
		rect = seat;
		return true;
	};
	if (!rect && !take(open, pinSpot(lowered(open.seats), avoiding, open.bounds)) && !(closed && take(closed, pinSpot(lowered(closed.seats), avoiding, closed.bounds))) && !take(open, clearAside(open.seats, open.bounds)) && !(closed && take(closed, clearAside(closed.seats, closed.bounds)))) posture = closed ?? open;
	const { seats, bounds, folded } = posture;
	const choices = [
		...seats.before,
		seats.home,
		...seats.after
	];
	const corner = boundedHome(seats.home, bounds);
	const aside = asideOf(seats, bounds);
	rect ??= leastCovering(choices, pin.cover, pressed, bounds);
	if (!rect) {
		const push = packRow({ rect: corner }, gap, occupied);
		const below = {
			...corner,
			top: corner.top + push,
			bottom: corner.bottom + push
		};
		rect = leastCovering(below.bottom <= pin.floor + gap + (corner.bottom - corner.top) ? [aside, below] : [aside], pin.cover, pressed, bounds) ?? (inside(below, bounds) ? below : corner);
	}
	return {
		rect,
		folded
	};
}
const inside = (rect, bounds) => rect.left >= bounds.left && rect.right <= bounds.right && rect.top >= bounds.top && rect.bottom <= bounds.bottom;
function boundedHome(home, bounds) {
	const width = home.right - home.left;
	const height = home.bottom - home.top;
	const left = clamp(home.left, bounds.left, bounds.right - width);
	const top = clamp(home.top, bounds.top, bounds.bottom - height);
	return {
		left,
		right: left + width,
		top,
		bottom: top + height
	};
}
function leastCovering(seats, cover, pressed, bounds) {
	const shared = (a, b) => Math.max(0, Math.min(a.right, b.right) - Math.max(a.left, b.left)) * Math.max(0, Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top));
	let best = null;
	let least = Infinity;
	for (const seat of seats) {
		if (!seat || !inside(seat, bounds) || pressed.some((box) => overlaps(box, seat))) continue;
		const covered = cover.reduce((sum, box) => sum + shared(box, seat), 0);
		if (covered < least) [best, least] = [seat, covered];
	}
	return best;
}
function slid(seat, boxes, gap, way, limit) {
	let rect = seat;
	for (let hit; hit = boxes.find((box) => overlaps(box, rect));) {
		const width = rect.right - rect.left;
		const height = rect.bottom - rect.top;
		rect = way === "left" ? {
			...rect,
			left: hit.left - gap - width,
			right: hit.left - gap
		} : {
			...rect,
			top: hit.bottom + gap,
			bottom: hit.bottom + gap + height
		};
		if (way === "left" ? rect.left < limit : rect.bottom > limit) return null;
	}
	return rect;
}
const pinSpot = (seats, boxes, bounds) => seats.find((seat) => seat && inside(seat, bounds) && !boxes.some((box) => overlaps(box, seat))) ?? null;

//#endregion
//#region runtime/annotation-overlay/margin-layout.js
const shownRead = (read) => read.shown;
const rows = /* @__PURE__ */ new Map();
const anchors = /* @__PURE__ */ new WeakMap();
const targetBox = (target) => shownParts(target)[0] ?? target;
let observedGeometry = /* @__PURE__ */ new Set();
let geometryObservation = 0;
let wantedGeometry = /* @__PURE__ */ new Set();
function watchGeometry(geometry, layer) {
	wantedGeometry = geometry;
	if (geometryObservation) return;
	if (geometry.size === observedGeometry.size && [...geometry].every((node) => observedGeometry.has(node))) return;
	geometryObservation = nextRender(() => {
		geometryObservation = 0;
		for (const node of observedGeometry) if (!wantedGeometry.has(node)) layer.sizes.unobserve(node);
		for (const node of wantedGeometry) if (!observedGeometry.has(node)) layer.sizes.observe(node);
		observedGeometry = wantedGeometry;
	});
}
const GAP = 4;
const THREAD_CARD = "lf-margin-preview";
const HELD = `:hover, :focus-within, :has([data-lf-held-word]), [data-lf-options-expanded], :has([aria-controls="${THREAD_CARD}"][aria-expanded="true"])`;
let pending = 0;
let observer = null;
let observedColumn = null;
let layer = null;
const carriers = /* @__PURE__ */ new Map();
const carrierDirections = ["xy", "y"];
const carrierAxes = /* @__PURE__ */ new WeakMap();
function carrierFor(holder, anchor, axes, run) {
	let byAnchor = carriers.get(holder);
	if (!byAnchor) carriers.set(holder, byAnchor = /* @__PURE__ */ new Map());
	let held = byAnchor.get(anchor);
	if (!held) byAnchor.set(anchor, held = {
		xy: [],
		y: []
	});
	let carrier = held[axes][run];
	if (!carrier) {
		carrier = document.createElement("div");
		carrier.className = "lf-ui lf-margin-carrier";
		carrierAxes.set(carrier, axes);
		held[axes][run] = carrier;
	}
	return carrier;
}
const isCarrier = (node) => node?.classList.contains("lf-margin-carrier");
const ids = /* @__PURE__ */ new WeakMap();
let idCount = 0;
const idOf = (node) => ids.get(node) ?? (ids.set(node, ++idCount), idCount);
const cutFramesByKey = /* @__PURE__ */ new Map();
const chains = /* @__PURE__ */ new WeakMap();
const outerFrame = /* @__PURE__ */ new WeakMap();
const makeCutFrame = () => {
	const frame = document.createElement("div");
	frame.className = "lf-margin-cut";
	return frame;
};
function cutRun(lane, read, run) {
	const key = `${idOf(lane)}|${read.cutKey}`;
	let held = cutFramesByKey.get(key);
	if (!held) cutFramesByKey.set(key, held = []);
	const prior = held[run];
	const chain = cutFrames(read.cuts, (prior ? chains.get(prior) ?? [] : []).map(({ frame }) => frame), makeCutFrame);
	let inner = chain[0].frame;
	for (const pair of chain) inner = pair.frame;
	if (prior && prior !== inner) chains.delete(prior);
	held[run] = inner;
	chains.set(inner, chain);
	outerFrame.set(inner, chain[0].frame);
	return inner;
}
const laneOf = (box, layer) => {
	for (let at = box; at; at = at.parentElement) {
		if (at === layer.root) return layer.root;
		for (const lane of layer.lanes.values()) if (at === lane) return lane;
	}
	return layer.root;
};
let laidOutScrollX = 0;
const standsBy = /* @__PURE__ */ new WeakMap();
function scrollSources(node) {
	const sources = [];
	for (let at = renderedParent(node); at && at !== pageScroller; at = renderedParent(at)) if (scrollsContent(at)) sources.push(at);
	return sources;
}
const stuckOrFixed = (node) => {
	let at = node;
	for (; at instanceof Element; at = renderedParent(at)) if (/^(sticky|fixed)$/.test(getComputedStyle(at).position)) return true;
	return false;
};
function carrierAnchor(subject, sources, scroller) {
	const inner = sources[0] ?? (scroller === pageScroller ? null : scroller);
	const own = () => anchorElement(targetBox(subject));
	if (!inner) return stuckOrFixed(subject) ? own() : null;
	if (!scrollsWith(subject, inner)) return own();
	return carriedAnchor(inner) ?? own();
}
const marginColumn = () => layoutBox() || document.body;
const flowOf = (scroller) => {
	const blocks = [];
	for (let block; block = boundedBlockOf(scroller);) {
		blocks.push(scroller);
		scroller = scrollerFor(upFrom(block));
	}
	return {
		blocks,
		flow: scroller
	};
};
const railBeside = (scroller) => flowOf(scroller).flow === pageScroller;
const railMeasureRow = document.createElement("div");
railMeasureRow.className = "lf-margin-cluster";
railMeasureRow.dataset.lfPlace = "rail";
railMeasureRow.inert = true;
railMeasureRow.setAttribute("aria-hidden", "true");
railMeasureRow.style.visibility = "hidden";
const railMeasureEntry = document.createElement("button");
railMeasureEntry.className = "lf-margin-entry";
railMeasureEntry.type = "button";
railMeasureEntry.dataset.lfBehavior = "disclosure";
railMeasureRow.append(railMeasureEntry);
function restingRail(layer) {
	const liveRows = layer.projection.querySelectorAll(".lf-margin-cluster[data-lf-place=\"rail\"]");
	for (const row of liveRows) {
		if (!row.checkVisibility()) continue;
		const children = [...row.querySelectorAll(":scope > *")].filter((child) => child.checkVisibility());
		const [only] = children;
		if (only && children.length === 1 && only.matches(".lf-margin-entry")) return {
			entry: only.offsetWidth,
			row: row.getBoundingClientRect().width
		};
	}
	const projection = layer.projection.cloneNode(false);
	projection.hidden = false;
	projection.inert = true;
	projection.setAttribute("aria-hidden", "true");
	const lane = layer.root.cloneNode(false);
	lane.append(railMeasureRow);
	projection.append(lane);
	layer.projection.after(projection);
	const entry = railMeasureEntry.offsetWidth;
	const row = railMeasureRow.getBoundingClientRect().width;
	projection.remove();
	return {
		entry,
		row
	};
}
function marginSpot(target, point = null, passage = null) {
	for (const [row, options] of rows) if (options.anchor?.() === target && (options.point?.() ?? null) === point && samePassage(options.passage?.() ?? null, passage) && row.checkVisibility()) {
		const { left, right } = row.getBoundingClientRect();
		return {
			left,
			right
		};
	}
	const main = marginColumn();
	if (!layer || !railStands(main) || !railBeside(scrollerFor(target))) return null;
	const hang = parseFloat(getComputedStyle(document.documentElement).getPropertyValue("--rail-hang")) || 0;
	const left = proseRect(main).right + hang;
	return {
		left,
		right: left + restingRail(layer).row
	};
}
function quotedBoxes(options) {
	if (options.point?.()) return [];
	return passageBoxes(options.passage?.() ?? null);
}
function samePassage(passage, words) {
	const range = passage && targetRange(passage);
	if (!range || !words) return !passage && !words;
	return range.startContainer === words.startContainer && range.startOffset === words.startOffset && range.endContainer === words.endContainer && range.endOffset === words.endOffset;
}
function syncMarginContentLayout(changed) {
	if (changed) scheduleMarginLayout();
}
const labelRect = (name, left, top, label) => ({
	name,
	rect: {
		left,
		right: left + label.width,
		top,
		bottom: top + label.height
	}
});
function placeMarginEntryLabel(control) {
	const label = control.querySelector(":scope > .lf-margin-entry-label");
	if (!label || !control.checkVisibility()) {
		keeps(control, "data-lf-label-side", null);
		return;
	}
	const marginEntryBox = control.getBoundingClientRect();
	const labelBox = label.getBoundingClientRect();
	const room = shownWindow({ gap: 4 });
	const edgeAligned = Math.max(room.left, Math.min(marginEntryBox.right - labelBox.width, room.right - labelBox.width));
	const clusterMarginEntries = [...(control.closest(".lf-margin-cluster") ?? control.parentElement)?.querySelectorAll(".lf-margin-entry") ?? []].filter((candidate) => candidate.checkVisibility()).map((candidate) => candidate.getBoundingClientRect());
	const clusterLeft = Math.min(...clusterMarginEntries.map((box) => box.left));
	const clusterRight = Math.max(...clusterMarginEntries.map((box) => box.right));
	const centered = (marginEntryBox.top + marginEntryBox.bottom - labelBox.height) / 2;
	const below = labelRect("below", edgeAligned, marginEntryBox.bottom + 6, labelBox);
	const above = labelRect("above", edgeAligned, marginEntryBox.top - 6 - labelBox.height, labelBox);
	const after = labelRect("after", clusterRight + 6, centered, labelBox);
	const before = labelRect("before", clusterLeft - 6 - labelBox.width, centered, labelBox);
	const candidates = coarsePointer.matches ? [
		above,
		before,
		after,
		below
	] : [
		below,
		above,
		after,
		before
	];
	const blockers = [...document.querySelectorAll(".lf-margin-projection .lf-margin-entry")].filter((candidate) => candidate !== control && candidate.checkVisibility()).map((candidate) => candidate.getBoundingClientRect());
	const fits = ({ rect }) => rect.left >= room.left && rect.right <= room.right && rect.top >= room.top && rect.bottom <= room.bottom;
	const choice = candidates.find((candidate) => fits(candidate) && !blockers.some((blocker) => overlaps(candidate.rect, blocker))) ?? candidates.find(fits) ?? (coarsePointer.matches ? above : below);
	setStyle(label, "--lf-label-x", layoutPx(choice.rect.left - marginEntryBox.left - control.clientLeft));
	setStyle(label, "--lf-label-y", layoutPx(choice.rect.top - marginEntryBox.top - control.clientTop));
	keeps(control, "data-lf-label-side", choice.name);
}
const revealsLabel = () => hoveringPointer.matches ? ":is(:hover, [data-lf-focus]):not([aria-expanded=\"true\"]), [data-lf-held-word]" : "[data-lf-focus]:focus-visible:not([aria-expanded=\"true\"]), [data-lf-held-word]";
function heldLabelBoxes(row) {
	return [...row.querySelectorAll(".lf-margin-entry[data-lf-label-side]")].filter((control) => control.matches(revealsLabel())).flatMap((control) => {
		const label = control.querySelector(":scope > .lf-margin-entry-label");
		return label ? [label.getBoundingClientRect()] : [];
	});
}
let labelPlacementFrame = 0;
function scheduleMarginEntryLabels() {
	if (labelPlacementFrame) return;
	labelPlacementFrame = nextRender(() => {
		labelPlacementFrame = 0;
		const controls = document.querySelectorAll(`.lf-margin-projection .lf-margin-entry:is(${revealsLabel()}, [data-lf-label-side])`);
		for (const control of controls) if (control.matches(revealsLabel())) placeMarginEntryLabel(control);
		else keeps(control, "data-lf-label-side", null);
	});
}
function mountMarginLayer(root, projection) {
	layer = {
		root,
		projection,
		lanes: /* @__PURE__ */ new Map(),
		sizes: sizeObserver(layoutMarginRows)
	};
	hearTargetChanges(document);
}
const heard = /* @__PURE__ */ new WeakSet();
function hearTargetChanges(root) {
	if (heard.has(root)) return;
	heard.add(root);
	root.addEventListener(LAYOUT, scheduleMarginLayout);
	root.addEventListener("slotchange", scheduleMarginLayout);
	new MutationObserver((records) => {
		if (records.some((record) => !inChrome(record.target) && (record.type === "attributes" || record.type === "childList" && record.target instanceof Element && wantedGeometry.has(record.target)))) afterScript(layoutMarginRows);
		const moved = records.flatMap((record) => [...record.removedNodes, ...record.addedNodes]).filter((node) => node instanceof Element);
		for (const [row, options] of rows) {
			const target = options.anchor();
			const anchor = anchors.get(row);
			if (!moved.some((node) => under(target, node) || under(anchor, node))) continue;
			if (!target?.isConnected || anchor && !anchor.isConnected) row.classList.toggle("lf-withheld", true);
			scheduleMarginLayout();
		}
	}).observe(root, {
		childList: true,
		subtree: true,
		attributes: true,
		attributeFilter: [
			"style",
			"class",
			"hidden",
			"open"
		]
	});
	root.addEventListener("scroll", (event) => {
		const source = event.target === document ? pageScroller : event.target;
		if (!(source instanceof Element)) return;
		scrolled.add(source);
		scheduleScrollReading();
	}, {
		capture: true,
		passive: true
	});
}
const laneFrames = /* @__PURE__ */ new Map();
const makeLaneFrame = () => {
	const frame = document.createElement("div");
	frame.className = "lf-margin-lane";
	return frame;
};
function laneFor(scroller, layer) {
	if (scroller === pageScroller) return layer.root;
	let lane = layer.lanes.get(scroller);
	if (!lane) {
		lane = makeLaneFrame();
		layer.root.after(lane);
		layer.lanes.set(scroller, lane);
		layer.sizes.observe(scroller);
	}
	return lane;
}
const EVERYWHERE = {
	left: -Infinity,
	top: -Infinity,
	right: Infinity,
	bottom: Infinity
};
function reach(anchor, box, main, reaches) {
	let right = box.right;
	for (let el = renderedParent(anchor); el && el !== main; el = renderedParent(el)) {
		let edge = reaches.get(el);
		if (edge === void 0) {
			const b = el.getBoundingClientRect();
			const style = getComputedStyle(el);
			edge = {
				right: proseMeasure(el) > 0 ? -Infinity : b.right,
				clip: style.overflowX === "visible" ? null : b.left + el.clientLeft + el.clientWidth
			};
			reaches.set(el, edge);
		}
		if (edge.clip !== null) right = Math.min(right, edge.clip);
		right = Math.max(right, edge.right);
	}
	return right;
}
function partsOf(target) {
	return shownParts(target).flatMap((part) => [...part.getClientRects()]).filter((box) => box.width && box.height);
}
const OPAQUE = "img, svg, canvas, video, iframe, object, embed";
function controlsIn(host) {
	const found = [];
	const visit = (el) => {
		for (const node of renderedChildren(el)) {
			if (!(node instanceof Element)) continue;
			if (node.matches(TAB_STOP)) found.push(node);
			visit(node);
		}
	};
	visit(host);
	return found;
}
function coverIn(root, band, target, bands, stop) {
	const cover = [];
	const controls = [];
	const boxes = [];
	const meets = (box) => box.bottom > band.top && box.top < band.bottom;
	const visit = (parent, children) => {
		for (const node of children) {
			if (node instanceof Text) {
				if (!node.data.trim()) continue;
				const words = document.createRange();
				words.selectNodeContents(node);
				for (const box of words.getClientRects()) {
					if (!meets(box)) continue;
					const shown = clippedContents(box, parent, bands, stop);
					if (shown && shown.right - shown.left > 1 && shown.bottom - shown.top > 1) cover.push(shown);
				}
				continue;
			}
			if (!(node instanceof Element) || node.closest(".lf-chrome")) continue;
			if (skipped(node)) continue;
			const box = node.getBoundingClientRect();
			const boxless = !box.width && !box.height;
			if (!boxless && !meets(box)) continue;
			const holds = node !== target && renderedUnder(target, node);
			if (!boxless && !holds && node !== target) boxes.push({
				node,
				box
			});
			const control = node.matches(TAB_STOP);
			if (!boxless && !holds && (node.shadowRoot || node.matches(OPAQUE) || control) && node.checkVisibility()) {
				const shown = clippedRect(box, node, bands, stop);
				if (shown) cover.push(shown);
				if (shown && control) controls.push(shown);
				for (const inner of node.shadowRoot ? controlsIn(node) : []) {
					if (!inner.checkVisibility()) continue;
					const part = clippedRect(inner.getBoundingClientRect(), inner, bands, stop);
					if (part) controls.push(part);
				}
				continue;
			}
			if (node instanceof SVGElement) continue;
			if (getComputedStyle(node).contentVisibility === "hidden") continue;
			if (node instanceof HTMLDetailsElement && !node.open) {
				const summary = node.querySelector(":scope > summary");
				if (summary) visit(node, [summary]);
				continue;
			}
			visit(node, renderedChildren(node));
		}
	};
	visit(root, renderedChildren(root));
	const beside = (seat) => boxes.some(({ node, box }) => {
		if (!overlaps(box, seat) || getComputedStyle(node).display === "inline") return false;
		if (renderedUnder(node, target) || !node.checkVisibility()) return false;
		const shown = clippedRect(box, node, bands, stop);
		return shown !== null && overlaps(shown, seat);
	});
	return {
		cover,
		controls,
		beside
	};
}
function contentBox(scroller) {
	const box = scroller.getBoundingClientRect();
	const left = box.left + scroller.clientLeft - scroller.scrollLeft;
	const top = box.top + scroller.clientTop - scroller.scrollTop;
	return {
		left,
		top,
		right: left + Math.max(scroller.scrollWidth, scroller.clientWidth),
		bottom: top + Math.max(scroller.scrollHeight, scroller.clientHeight)
	};
}
const seats = /* @__PURE__ */ new WeakMap();
const folded = /* @__PURE__ */ new WeakSet();
const standsFolded = (row) => folded.has(row);
function paintedBox(part, row) {
	const box = part.getBoundingClientRect();
	if (!row) return box;
	const by = standsBy.get(row);
	const target = by && isCarrier(row.parentElement) ? rows.get(row)?.anchor() : null;
	if (!target?.isConnected || skipped(target)) return box;
	const whole = shownExtent(target);
	if (!whole) return box;
	const own = part === row ? box : row.getBoundingClientRect();
	const across = row.dataset.lfPlace === "pin" ? whole.right + by.right - own.right : 0;
	return new DOMRect(box.x + across, box.y + whole.top + by.top - own.top, box.width, box.height);
}
function standFolded(row, fold, on) {
	if (folded.has(row) === on) return;
	if (on) folded.add(row);
	else folded.delete(row);
	fold?.changed();
}
function pinSeating(rows, { bands, shell, pinInset }) {
	const main = marginColumn();
	const rootBounds = /^(hidden|clip)$/.test(getComputedStyle(pageScroller).overflowY) ? shownWindow({ viewport: "layout" }) : { top: pageScroller.getBoundingClientRect().top };
	return rows.map((entry) => {
		const { read } = entry;
		if (read.place !== "pin") {
			seats.delete(read.row);
			standFolded(read.row, read.options.fold, false);
			return Object.assign(entry, { seat: null });
		}
		const { target, point, words, row } = read;
		const home = entry.rect;
		const height = home.bottom - home.top;
		const width = home.right - home.left;
		const fold = read.options.fold?.able() ? read.options.fold : null;
		if (!fold) standFolded(row, read.options.fold, false);
		entry.fold = fold;
		const dimensions = fold ? {
			fold,
			style: getComputedStyle(row)
		} : null;
		const across = (count, style) => count * height + (count - 1) * parseFloat(style.columnGap) + parseFloat(style.paddingRight);
		const wide = dimensions ? across(2, dimensions.style) : width;
		const parts = words ?? partsOf(point ?? target);
		const blockBox = read.block;
		const blockParts = words && blockBox ? partsOf(target) : [];
		const block = blockBox && blockParts.length > 0 && {
			parts: blockParts,
			home: {
				left: blockBox.right - pinInset - width,
				right: blockBox.right - pinInset,
				top: blockBox.top,
				bottom: blockBox.top + height
			}
		};
		const spans = [
			home,
			...parts,
			...block ? [block.home, ...block.parts] : []
		];
		const around = height + GAP;
		const band = {
			top: Math.min(...spans.map((box) => box.top)) - around,
			bottom: Math.max(...spans.map((box) => box.bottom)) + around
		};
		const stop = read.scroller;
		const room = coverIn(stop === pageScroller ? main : stop, band, target, bands, stop);
		const { cover, controls } = room;
		const end = parts.at(-1);
		const inline = Boolean(words) || !point && end !== void 0 && target instanceof HTMLElement && getComputedStyle(target).display.startsWith("inline");
		const floor = Math.max(home.bottom, ...parts.map((part) => part.bottom));
		const reach = (stop === pageScroller ? innerHeight : stop.clientHeight) / 2;
		const near = (seat) => seat.top >= Math.min(...parts.map((part) => part.top)) - reach && seat.bottom <= Math.max(...parts.map((part) => part.bottom)) + reach;
		const seatsAt = (size) => {
			const seats = seatsBy(parts, home, inline, Boolean(words), room, size, GAP);
			if (!block) return seats;
			const extra = seatsBy(block.parts, block.home, false, false, room, size, GAP);
			return {
				...seats,
				after: [...seats.after, ...[
					...extra.before,
					extra.home,
					...extra.after
				].filter((seat) => seat && near(seat))]
			};
		};
		const within = stop === pageScroller ? rootBounds : contentBox(stop);
		const clipped = clippedRect(EVERYWHERE, target, bands, stop);
		const pin = {
			held: entry.holding ?? null,
			came: entry.came,
			seats: seatsAt(wide),
			floor,
			cover: words ? [...cover, ...words] : cover,
			controls,
			folds: dimensions && {
				seats: seatsAt(across(1, dimensions.style)),
				open: across(dimensions.fold.controls(), dimensions.style)
			},
			folded: folded.has(row),
			bounds: {
				left: Math.max(within?.left ?? 0, clipped?.left ?? 0) + pinInset,
				right: Math.min(within?.right ?? shell, clipped?.right ?? shell) - pinInset,
				top: Math.max(within?.top ?? -Infinity, clipped?.top ?? -Infinity),
				bottom: Math.min(within?.bottom ?? Infinity, clipped?.bottom ?? Infinity)
			}
		};
		const seat = (occupied) => {
			const { rect, folded: on } = seatRow(pin, {
				gap: GAP,
				occupied
			});
			entry.visualLeft = on && fold?.open() ? rect.right - (entry.rect.right - entry.rect.left) : rect.left;
			entry.rect = rect;
			if (entry.fold) standFolded(entry.read.row, entry.fold, on);
			const attached = targetBox(entry.read.target).getBoundingClientRect();
			seats.set(entry.read.row, {
				top: rect.top - attached.top,
				right: attached.right - rect.right
			});
		};
		return Object.assign(entry, { seat });
	});
}
function scheduleMarginLayout() {
	if (pending) return;
	pending = nextRender(layoutMarginRows);
}
function observeLayout() {
	const column = marginColumn();
	if (!observer) {
		observer = sizeObserver(layoutMarginRows);
		observer.observe(document.body);
	}
	if (observedColumn === column) return;
	if (observedColumn) observer.unobserve(observedColumn);
	observedColumn = column;
	observer.observe(observedColumn);
}
function registerMarginRow(row, options) {
	rows.set(row, options);
	observeLayout();
	scheduleMarginLayout();
}
function unregisterMarginRow(row) {
	rows.delete(row);
	anchors.delete(row);
	pushes.delete(row);
	folded.delete(row);
	if (!rows.size) {
		observer?.disconnect();
		observer = null;
		observedColumn = null;
	}
	scheduleMarginLayout();
}
function setStyle(row, property, value) {
	if (value === null) inlineStyle(row).removeProperty(property);
	else inlineStyle(row).setProperty(property, value);
}
function targetShown(target, extent, stands, bands) {
	const shown = (part) => part.checkVisibility() && clippedRect(part.getBoundingClientRect(), part, bands, pageScroller);
	if (!visibleTargetParts(target).some(shown)) return false;
	const view = clippedRect(EVERYWHERE, target, bands, pageScroller);
	if (!extent || !view || !overlaps(extent, view)) return false;
	if (!stands) return true;
	return Number(stands.top) >= view.top - 1 && (stands.right === void 0 || stands.right <= view.right + 1);
}
const pushes = /* @__PURE__ */ new Map();
let pass = 0;
let came = /* @__PURE__ */ new Map();
const scrolled = /* @__PURE__ */ new Set();
let scrollReading = 0;
function scheduleScrollReading() {
	if (scrollReading) return;
	scrollReading = nextRender(() => {
		scrollReading = 0;
		const boxes = [...scrolled];
		scrolled.clear();
		if (boxes.includes(pageScroller) && scrollX !== laidOutScrollX && [...carriers.values()].some((byAnchor) => [...byAnchor.values()].some((held) => held.y.length))) {
			scheduleMarginLayout();
			return;
		}
		const bands = /* @__PURE__ */ new Map();
		for (const [row, options] of rows) {
			const target = options.anchor();
			if (!target?.isConnected) continue;
			if (!boxes.some((box) => {
				let at = target;
				for (; at; at = renderedParent(at)) if (at === box) return true;
				return false;
			})) continue;
			if (!row.classList.contains("lf-withheld") && boxes.every((box) => box === pageScroller)) continue;
			const whole = shownExtent(target);
			const words = quotedBoxes(options);
			const by = standsBy.get(row);
			const stands = row.classList.contains("lf-withheld") || !whole || !by ? null : row.dataset.lfPlace === "pin" ? {
				top: whole.top + by.top,
				right: whole.right + by.right
			} : { top: whole.top + by.top };
			if (targetShown(target, words.length ? union(words) : whole, stands, bands) === row.classList.contains("lf-withheld")) {
				scheduleMarginLayout();
				return;
			}
		}
	});
}
function layoutMarginRows() {
	cancelRender(pending);
	pending = 0;
	const mounted = layer;
	if (!mounted) return;
	layoutMountedRows(mounted);
}
function layoutMountedRows(layer) {
	pass += 1;
	laidOutScrollX = scrollX;
	const present = [];
	const main = marginColumn();
	const columnRect = proseRect(main);
	const columnHeight = main.scrollHeight;
	const shell = shellRight();
	const stands = railStands(main);
	const rootStyle = getComputedStyle(document.documentElement);
	const hang = parseFloat(rootStyle.getPropertyValue("--rail-hang")) || 0;
	const pinInset = parseFloat(rootStyle.getPropertyValue("--pin-inset")) || 0;
	const railInner = columnRect.right + hang;
	let railEntry;
	const railEntrySize = () => {
		const nativeEntry = layer.projection.querySelector(".lf-margin-cluster:not([data-lf-place=\"pin\"]) .lf-margin-entry:not([hidden])");
		return railEntry ??= nativeEntry?.offsetWidth || restingRail(layer).entry;
	};
	const notes = [...main.querySelectorAll(".layout-note > aside")].filter((note) => !skipped(note)).map((note) => note.getBoundingClientRect()).filter((note) => note.width && note.left >= columnRect.right - 1);
	const bands = /* @__PURE__ */ new Map();
	const reaches = /* @__PURE__ */ new Map();
	const reads = [];
	const geometry = /* @__PURE__ */ new Set();
	const parents = /* @__PURE__ */ new Set();
	function observeGeometry(target) {
		let at = target;
		for (; at && at !== pageScroller; at = renderedParent(at)) {
			if (at instanceof Element) {
				geometry.add(at);
				const root = at.getRootNode();
				if (root instanceof ShadowRoot) hearTargetChanges(root);
			}
			const parent = at.parentNode;
			if (!parent || parents.has(parent)) continue;
			parents.add(parent);
			for (const sibling of parent.children ?? []) if (!inChrome(sibling)) geometry.add(sibling);
		}
	}
	const carrierNames = /* @__PURE__ */ new Map();
	const cutClips = /* @__PURE__ */ new Map();
	for (const [row, options] of rows) {
		const target = options.anchor();
		if (!target?.isConnected) {
			present.push({
				row,
				at: null
			});
			reads.push({
				row,
				options,
				lane: layer.root,
				shown: false
			});
			continue;
		}
		if (skipped(target)) {
			present.push({
				row,
				at: null
			});
			const home = row.parentElement ?? layer.root;
			const container = isCarrier(home) ? home.parentElement : home;
			reads.push({
				row,
				options,
				lane: laneOf(container, layer),
				container,
				home,
				shown: false
			});
			continue;
		}
		const anchor = targetBox(target);
		anchors.set(row, anchor);
		const point = options.point?.() ?? null;
		const words = quotedBoxes(options);
		const [firstWord, ...otherWords] = words;
		const passageNode = firstWord ? targetSegments(options.passage?.())[0]?.node : null;
		observeGeometry(point ?? target);
		present.push({
			row,
			at: point ?? passageNode ?? target
		});
		const scroller = scrollerFor(target);
		const rootLane = scroller === pageScroller;
		const box = anchor.getBoundingClientRect();
		const whole = shownExtent(target);
		const block = whole && clippedRect(whole, target, bands, scroller);
		const extent = firstWord ? whole && clippedRect(union([firstWord, ...otherWords]), target, bands, scroller) : block;
		const line = point?.getBoundingClientRect() ?? words[0];
		const top = extent && line ? clamp(line.top, extent.top, extent.bottom) : extent?.top;
		const level = line ? top : box.top;
		const besideRail = railBeside(scroller);
		const size = stands && besideRail ? railEntrySize() : 0;
		const place = rowPlacement({
			railStands: stands,
			besideRail,
			blockRight: reach(anchor, box, main, reaches),
			railInner,
			half: size / 2,
			noted: notes.some((note) => note.top < Number(level) + size && note.bottom > Number(level))
		});
		const shown = targetShown(target, extent, place === "pin" ? null : { top }, bands);
		reads.push({
			row,
			options,
			target,
			point,
			words: words.length ? words : null,
			passageNode,
			block,
			anchor,
			whole,
			scroller,
			lane: rootLane ? layer.root : null,
			shown,
			place,
			box,
			extent,
			top,
			carrier: null,
			cuts: [],
			cutKey: "",
			carrierStand: null,
			carrierPaint: null
		});
	}
	came = arrivals(came, present, pass);
	for (const { row, target, shown, place } of reads) {
		row.classList.toggle("lf-withheld", !shown);
		if (!target) continue;
		if (row.dataset.lfPlace !== place) {
			pushes.delete(row);
			row.dataset.lfPlace = place;
		}
	}
	const placed = reads.filter(shownRead).map((read) => {
		const box = read.row.getBoundingClientRect();
		return {
			key: read.row,
			rect: {
				left: read.place === "pin" ? read.extent.right - pinInset - box.width : railInner,
				right: read.place === "pin" ? read.extent.right - pinInset : railInner + box.width,
				top: read.top,
				bottom: read.top + box.height
			},
			held: pushes.has(read.row) && read.row.matches(HELD),
			came: came.get(read.row),
			pushed: pushes.get(read.row),
			read
		};
	});
	for (const entry of placed) {
		const seat = seats.get(entry.read.row);
		if (entry.read.place !== "pin" || !seat || !entry.held) continue;
		const heldBox = targetBox(entry.read.target).getBoundingClientRect();
		const width = entry.rect.right - entry.rect.left;
		const height = entry.rect.bottom - entry.rect.top;
		entry.holding = {
			left: heldBox.right - seat.right - width,
			right: heldBox.right - seat.right,
			top: heldBox.top + seat.top,
			bottom: heldBox.top + seat.top + height
		};
	}
	const prepared = pinSeating(placed, {
		bands,
		shell,
		pinInset
	});
	const occupied = [];
	const packed = /* @__PURE__ */ new Map();
	for (const entry of inSeatingOrder(prepared)) {
		if (!entry.seat) {
			entry.step = Math.min(0, shell - entry.rect.right);
			const rect = {
				...entry.rect,
				left: entry.rect.left + entry.step,
				right: entry.rect.right + entry.step
			};
			const push = packRow({
				...entry,
				rect
			}, GAP, occupied);
			packed.set(entry.key, push);
			occupied.push({
				...rect,
				top: rect.top + push,
				bottom: rect.bottom + push
			});
		} else {
			entry.seat(occupied);
			packed.set(entry.key, 0);
			occupied.push(entry.rect);
		}
		if (entry.held) occupied.push(...heldLabelBoxes(entry.read.row));
	}
	for (const read of reads) {
		if (!read.target) continue;
		const subject = read.point ?? read.target;
		read.carrier = (read.passageNode && anchorFor(read.passageNode)) ?? carrierAnchor(subject, scrollSources(subject), read.scroller);
		read.cuts = headerLevels(subject, cutClips);
		read.cutKey = read.cuts.map(({ anchor, band, at }) => anchor ? `${idOf(anchor)}:${band.top - at.top}:${band.bottom - at.top}` : `window:${band.top}:${band.bottom}`).join("|");
		if (read.cuts.length) read.carrier ??= carriedAnchor(pageScroller) ?? anchorElement(targetBox(subject));
		read.lane = read.scroller === pageScroller ? layer.root : null;
		if (read.carrier) {
			const reading = carrierNames.get(read.carrier) ?? anchorReading(read.carrier);
			carrierNames.set(read.carrier, reading);
			read.carrierStand = {
				box: anchorBox(read.carrier),
				reading
			};
		}
	}
	const regions = /* @__PURE__ */ new Map();
	const ring = 6;
	for (const read of reads) if (read.scroller && read.scroller !== pageScroller && !regions.has(read.scroller)) {
		const holders = [read.scroller, ...scrollSources(read.scroller)];
		const rail = stands && railBeside(read.scroller);
		const levels = holders.map((holder, i) => {
			const band = clippedRect(shownBand(holder) ?? holder.getBoundingClientRect(), holder, bands, holders[i + 1] ?? pageScroller);
			const anchor = anchorElement(holder);
			const axes = i ? clippingAxes(getComputedStyle(holder)) : {
				x: true,
				y: true
			};
			return {
				anchor,
				reading: anchorReading(anchor),
				at: anchorBox(anchor),
				band: !band ? null : i ? band : {
					...band,
					left: band.left - ring,
					right: (rail ? shell : band.right) + ring
				},
				axes: rail && i !== 0 ? {
					...axes,
					x: false
				} : axes
			};
		}).reverse();
		if (rail) for (const level of levels.slice(-1)) level.axes = {
			x: true,
			y: true
		};
		regions.set(read.scroller, levels);
	}
	watchGeometry(geometry, layer);
	for (const read of reads) if (read.target) read.lane ??= laneFor(read.scroller, layer);
	const orderedReads = [...reads].sort((a, b) => (a.options.order ?? 0) - (b.options.order ?? 0));
	for (const [scroller, lane] of layer.lanes) {
		const levels = regions.get(scroller);
		const hidden = {
			left: 0,
			top: 0,
			right: 0,
			bottom: 0
		};
		const [first, ...more] = (levels ?? []).map((level) => ({
			...level,
			band: level.band ?? hidden
		}));
		if (!first) continue;
		const frames = cutFrames([first, ...more], laneFrames.get(lane)?.frames.map(({ frame }) => frame) ?? [lane], makeLaneFrame);
		laneFrames.set(lane, {
			root: frames[0].frame,
			frames
		});
	}
	const byLane = [{
		lane: layer.root,
		root: layer.root
	}, ...[...laneFrames].map(([lane, { root }]) => ({
		lane,
		root
	}))].map(({ lane, root }) => ({
		lane,
		root,
		members: orderedReads.filter((read) => read.lane === lane),
		order: orderedReads.findIndex((read) => read.lane === lane)
	})).filter(({ order }) => order >= 0).sort((a, b) => a.order - b.order);
	let lastLane = layer.root;
	for (const { lane, root, members } of byLane) {
		if (lane !== layer.root) {
			if (lastLane.nextElementSibling !== root) move(layer.projection, root, lastLane.nextSibling);
			lastLane = root;
		}
		const cursors = /* @__PURE__ */ new Map([[lane, lane.firstElementChild]]);
		const place = (holder, node, before) => {
			const oldHome = node.parentElement;
			if (oldHome && cursors.get(oldHome) === node) cursors.set(oldHome, node.nextElementSibling);
			move(holder, node, before ?? null);
		};
		const runs = /* @__PURE__ */ new Map();
		const cutRuns = /* @__PURE__ */ new Map();
		const kept = new Set(members.filter((read) => !read.target).flatMap(({ home, container }) => [home, container]).filter(Boolean));
		const previous = {
			cutKey: null,
			carrier: null,
			axes: void 0,
			container: lane,
			home: lane
		};
		for (const read of members) {
			const { row } = read;
			if (read.target) {
				const [firstCut, ...moreCuts] = read.cuts;
				if (!firstCut) read.container = lane;
				else if (previous.cutKey === read.cutKey && previous.container !== lane) read.container = previous.container;
				else {
					const held = cutFramesByKey.get(`${idOf(lane)}|${read.cutKey}`) ?? [];
					let run = cutRuns.get(read.cutKey) ?? 0;
					while (kept.has(held[run])) run += 1;
					cutRuns.set(read.cutKey, run + 1);
					read.container = cutRun(lane, {
						cutKey: read.cutKey,
						cuts: [firstCut, ...moreCuts]
					}, run);
				}
				const container = read.container;
				const axes = read.place === "rail" ? "y" : "xy";
				if (!read.carrier) read.home = lane;
				else if (previous.carrier === read.carrier && previous.axes === axes && previous.container === read.container) read.home = previous.home;
				else {
					const key = carrierFor(container, read.carrier, axes, 0);
					let run = runs.get(key) ?? 0;
					while (kept.has(carrierFor(container, read.carrier, axes, run))) run += 1;
					runs.set(key, run + 1);
					read.home = carrierFor(container, read.carrier, axes, run);
				}
				read.axes = axes;
			}
			const container = read.container ?? lane;
			const home = read.home ?? lane;
			Object.assign(previous, {
				cutKey: read.cutKey,
				carrier: read.carrier,
				axes: read.axes,
				container,
				home
			});
			if (read.target && read.carrierStand) read.carrierPaint = {
				node: home,
				box: read.carrierStand.box,
				reading: read.carrierStand.reading
			};
			const seat = (holder, box, outer = box) => {
				if (cursors.has(box)) return;
				let at = cursors.get(holder);
				if (at && at.parentElement !== holder) at = null;
				if (at === outer) cursors.set(holder, outer.nextElementSibling);
				else place(holder, outer, at);
				cursors.set(box, box.firstElementChild);
			};
			if (container !== lane) seat(lane, container, outerFrame.get(container));
			if (home !== container) seat(container, home);
			let before = cursors.get(home);
			if (before && before.parentElement !== home) before = null;
			if (before === row) {
				cursors.set(home, row.nextElementSibling);
				continue;
			}
			place(home, row, before);
			cursors.set(home, before);
		}
	}
	for (const [holder, byAnchor] of carriers) {
		for (const [anchor, held] of byAnchor) {
			for (const axes of carrierDirections) held[axes] = held[axes].filter((carrier) => {
				if (carrier.isConnected && carrier.childElementCount) return true;
				carrier.remove();
				return false;
			});
			if (!held.xy.length && !held.y.length) byAnchor.delete(anchor);
		}
		if (!byAnchor.size) carriers.delete(holder);
	}
	for (const [key, held] of cutFramesByKey) {
		const kept = held.filter((inner) => inner.isConnected && inner.childElementCount);
		for (const inner of held) if (!kept.includes(inner)) {
			outerFrame.get(inner)?.remove();
			outerFrame.delete(inner);
			chains.delete(inner);
		}
		if (kept.length) cutFramesByKey.set(key, kept);
		else cutFramesByKey.delete(key);
	}
	for (const [lane, { root }] of laneFrames) if (!byLane.some((group) => group.lane === lane)) {
		root.remove();
		laneFrames.delete(lane);
		for (const [scroller, owned] of layer.lanes) if (owned === lane) {
			layer.lanes.delete(scroller);
			layer.sizes.unobserve(scroller);
		}
	}
	for (const row of pushes.keys()) if (!packed.has(row)) pushes.delete(row);
	for (const { key: row, rect, read, visualLeft, step = 0 } of placed) {
		const push = packed.get(row) ?? 0;
		pushes.set(row, push);
		if (read.place === "pin") row.classList.toggle("lf-withheld", !targetShown(read.target, read.extent, {
			top: rect.top + push,
			right: rect.right
		}, bands));
		const left = (visualLeft ?? rect.left) + step;
		const top = rect.top + push;
		standsBy.set(row, {
			top: top - read.whole.top,
			right: rect.right - read.whole.right
		});
		if (read.carrierPaint) {
			const { node: carrier, box: carrierBox, reading } = read.carrierPaint;
			const from = (side, at) => `calc(anchor(${side}, -9999px) - ${layoutPx(at)})`;
			if (reading.write) {
				nameAnchor(reading);
				delete reading.write;
			}
			setStyle(carrier, "position-anchor", reading.name);
			setStyle(carrier, "top", from("top", carrierBox.top));
			setStyle(carrier, "left", carrierAxes.get(carrier) === "xy" ? from("left", carrierBox.left) : "0px");
			setStyle(row, "--lf-margin-x", layoutPx(left));
			setStyle(row, "--lf-margin-y", layoutPx(top));
			continue;
		}
		setStyle(row, "--lf-margin-x", layoutPx(left + scrollX));
		setStyle(row, "--lf-margin-y", layoutPx(top + scrollY));
	}
	document.dispatchEvent(new CustomEvent("lf-margin-layout", { detail: {
		column: columnRect,
		height: columnHeight
	} }));
}

//#endregion
//#region runtime/annotation-overlay/floating.js
let floatingUiModule = null;
const floatingUi = () => floatingUiModule ??= import("/vendor/floating-ui.esm.js");
afterPresentation(floatingUi);
async function positioningScale({ elements, platform, strategy }) {
	const unit = await platform.convertOffsetParentRelativeRectToViewportRelativeRect({
		elements,
		offsetParent: await platform.getOffsetParent(elements.floating),
		strategy,
		rect: {
			x: 0,
			y: 0,
			width: 1,
			height: 1
		}
	});
	return {
		x: unit.width,
		y: unit.height
	};
}
const anchorAt = (reference) => ({
	name: "anchorAt",
	async fn(state) {
		const { rects, elements, platform } = state;
		if (await platform.getOffsetParent(elements.floating) !== window) return { data: { offset: null } };
		const client = reference.getBoundingClientRect();
		const scale = await positioningScale(state);
		return { data: {
			scale,
			offset: {
				x: rects.reference.x - client.left / scale.x,
				y: rects.reference.y - client.top / scale.y
			}
		} };
	}
});
function holderOf({ edge, at }, context, overflowAncestors) {
	const candidates = overflowAncestors.filter((source) => source instanceof Element && source !== document.scrollingElement);
	let region = containingReadingRegionFor(context);
	while (region) {
		if (!candidates.includes(region.body)) candidates.push(region.body);
		region = upFrom(region.host) && containingReadingRegionFor(upFrom(region.host));
	}
	return candidates.find((box) => [box.getBoundingClientRect(), shownBand(box)].some((rect) => rect && Math.abs(rect[edge] - at) < 1)) ?? null;
}
const held = {
	name: "held",
	async fn(state) {
		const { placement, rects, middlewareData, elements, platform } = state;
		const [side, alignment] = placement.split("-");
		const aligned = (start, end) => alignment === "end" ? end : start;
		const edges = side === "top" || side === "bottom" ? {
			x: aligned("left", "right"),
			y: side === "top" ? "bottom" : "top"
		} : {
			x: side === "left" ? "right" : "left",
			y: aligned("top", "bottom")
		};
		edges.y = middlewareData.hold?.edge ?? edges.y;
		edges.x = middlewareData.hold?.inline ?? edges.x;
		const shiftX = middlewareData.shift?.x ?? 0;
		const shiftY = middlewareData.shift?.y ?? 0;
		if (Math.abs(shiftX) >= .5) edges.x = shiftX < 0 ? "right" : "left";
		if (Math.abs(shiftY) >= .5) edges.y = shiftY < 0 ? "bottom" : "top";
		const parent = await platform.getOffsetParent(elements.floating);
		const block = parent instanceof Element ? parent : document.documentElement;
		const scale = await positioningScale(state);
		const blockScale = parent === window ? {
			x: 1,
			y: 1
		} : await platform.getScale(parent);
		return { data: {
			edges,
			width: rects.floating.width,
			height: rects.floating.height,
			block: {
				width: block.clientWidth * blockScale.x / scale.x,
				height: block.clientHeight * blockScale.y / scale.y
			}
		} };
	}
};
const INSETS = [
	"left",
	"right",
	"top",
	"bottom"
];
const stood = /* @__PURE__ */ new Map();
const floatingSelections = () => [...stood.values()];
const heldEdges = (floating) => {
	const edges = stood.get(floating)?.edges;
	return edges ? {
		x: edges.left,
		y: edges.top
	} : null;
};
const physicalContext = (context) => context instanceof Element ? context : context?.parentElement;
function floatingGeometry(contexts) {
	const anchors = /* @__PURE__ */ new Map();
	for (const context of contexts) {
		const anchor = anchorFor(context ?? null);
		if (anchor) anchors.set(anchor, anchorBox(anchor));
	}
	return { anchors };
}
function floatingPlacement({ floating, update }) {
	let epoch = 0;
	let watched = null;
	let observer = null;
	let tenure = Object.freeze({});
	let stopWatching = null;
	let lastAnchorStand = null;
	const inset = (insets) => {
		for (const edge of INSETS) if (insets[edge] === void 0) floating.style.removeProperty(edge);
		else floating.style.setProperty(edge, insets[edge]);
	};
	const placedAt = ({ x, y, middlewareData }) => {
		lastAnchorStand = null;
		const { edges, width, height, block } = middlewareData.held;
		floating.style.removeProperty("position-anchor");
		inset({
			[edges.x]: layoutPx(edges.x === "left" ? x : block.width - x - width),
			[edges.y]: layoutPx(edges.y === "top" ? y : block.height - y - height)
		});
	};
	const anchoredAt = (anchor, at) => ({ x, y, middlewareData }) => {
		const { edges, width, height, block } = middlewareData.held;
		const lengthX = atLayoutPrecision(edges.x === "left" ? x - at.x : at.x - x - width);
		const lengthY = atLayoutPrecision(edges.y === "top" ? y - at.y : at.y - y - height);
		if (lastAnchorStand && lastAnchorStand.anchor === anchor && lastAnchorStand.edgeX === edges.x && lastAnchorStand.edgeY === edges.y && lastAnchorStand.lengthX === lengthX && lastAnchorStand.lengthY === lengthY) return;
		const from = (side, length, fallback) => `calc(anchor(${side}, ${layoutPx(fallback)}) + ${layoutPx(length)})`;
		floating.style.positionAnchor = anchorName(anchor);
		inset({
			[edges.x]: from("left", lengthX, edges.x === "left" ? at.x : block.width - at.x),
			[edges.y]: from("top", lengthY, edges.y === "top" ? at.y : block.height - at.y)
		});
		lastAnchorStand = {
			anchor,
			edgeX: edges.x,
			edgeY: edges.y,
			lengthX,
			lengthY
		};
	};
	let stand = placedAt;
	let placementProof = null;
	let stopScrollInvalidation = null;
	return {
		watch(element, reference, autoUpdate) {
			if (element === watched && autoUpdate === observer) return;
			stopWatching?.();
			watched = element;
			observer = autoUpdate;
			tenure = Object.freeze({});
			const stopGeometry = autoUpdate(reference, floating, update);
			let visible = visibleTargetParts(element).length > 0;
			let observesParts = null;
			const visibility = new MutationObserver(() => {
				observeVisibility();
				const next = visibleTargetParts(element).length > 0;
				if (next === visible) return;
				visible = next;
				update();
			});
			const observeVisibility = () => {
				const parts = getComputedStyle(element).display === "contents";
				if (parts === observesParts) return;
				visibility.disconnect();
				visibility.observe(element, {
					attributes: true,
					subtree: parts,
					childList: parts
				});
				for (let at = renderedParent(element); at; at = renderedParent(at)) if (at instanceof Element) visibility.observe(at, { attributes: true });
				observesParts = parts;
			};
			observeVisibility();
			stopWatching = () => {
				visibility.disconnect();
				stopGeometry();
			};
		},
		follows: () => placementProof?.plane === "page",
		begin: () => ++epoch,
		current: (placement) => placement === epoch,
		async position(computePosition, reference, options, planeOf, beside) {
			const placement = epoch;
			const context = reference.contextNode ?? beside;
			const physical = physicalContext(context);
			const anchor = anchorFor(context ?? null);
			const client = reference.getBoundingClientRect();
			const anchorStood = (reference.geometry ?? floatingGeometry([context])).anchors.get(anchor);
			const { getOverflowAncestors } = await floatingUi();
			if (placement !== epoch) return null;
			const measured = {
				contextElement: reference.contextElement ?? beside,
				getBoundingClientRect: () => client
			};
			const answer = await computePosition(measured, floating, {
				...options,
				strategy: "fixed",
				middleware: [
					...options.middleware,
					held,
					anchorAt(measured)
				]
			});
			if (placement !== epoch) return null;
			const { offset, scale } = answer.middlewareData.anchorAt;
			const wanted = planeOf(answer);
			const holder = offset && physical && typeof wanted === "object" ? holderOf(wanted, physical, getOverflowAncestors(physical)) : null;
			const plane = wanted === "page" && anchorStood && offset ? "page" : holder ? "region" : "window";
			const frameAnchor = plane === "page" ? anchor : holder ? anchorElement(holder) : null;
			const frameBox = plane === "page" ? anchorStood : frameAnchor && anchorBox(frameAnchor);
			const at = offset && {
				x: offset.x + (frameBox?.left ?? 0) / scale.x,
				y: offset.y + (frameBox?.top ?? 0) / scale.y
			};
			keeps(floating, "data-lf-plane", plane);
			stopScrollInvalidation?.();
			stopScrollInvalidation = null;
			if (plane !== "page") {
				const sources = context ? [...new Set(getOverflowAncestors(context))] : [];
				for (const source of sources) source.addEventListener("scroll", update, { passive: true });
				stopScrollInvalidation = () => {
					for (const source of sources) source.removeEventListener("scroll", update);
				};
			}
			stand = frameAnchor ? anchoredAt(frameAnchor, at) : placedAt;
			placementProof = at ? {
				subject: watched,
				anchor,
				frame: frameAnchor,
				plane,
				at
			} : null;
			return answer;
		},
		stand(answer) {
			stand(answer);
			if (!placementProof) {
				stood.delete(floating);
				tenure = Object.freeze({});
				return;
			}
			const { edges, width, height, block } = answer.middlewareData.held;
			const { offset, scale } = answer.middlewareData.anchorAt;
			const { subject, anchor, frame: frameAnchor, plane, at } = placementProof;
			const axisPoint = (coordinate, start, length, extent) => {
				const fromStart = edges[coordinate] === start;
				const spot = answer[coordinate];
				return ((frameAnchor ? fromStart ? atLayoutPrecision(spot - at[coordinate]) : -atLayoutPrecision(at[coordinate] - spot - length) : fromStart ? atLayoutPrecision(spot) : extent - atLayoutPrecision(extent - spot - length)) - (frameAnchor ? 0 : offset[coordinate])) * scale[coordinate];
			};
			const point = {
				left: axisPoint("x", "left", width, block.width),
				top: axisPoint("y", "top", height, block.height)
			};
			stood.set(floating, Object.freeze({
				floating,
				subject,
				anchor,
				frame: frameAnchor,
				plane,
				tenure,
				edges: Object.freeze({
					left: edges.x,
					top: edges.y
				}),
				point: Object.freeze(point),
				size: Object.freeze({
					width: width * scale.x,
					height: height * scale.y
				})
			}));
		},
		clientBox(answer) {
			const { offset, scale } = answer.middlewareData.anchorAt;
			const { width, height } = answer.middlewareData.held;
			return offset ? new DOMRect((answer.x - offset.x) * scale.x, (answer.y - offset.y) * scale.y, width * scale.x, height * scale.y) : floating.getBoundingClientRect();
		},
		supersede() {
			epoch += 1;
		},
		stop() {
			epoch += 1;
			lastAnchorStand = null;
			stopWatching?.();
			stopScrollInvalidation?.();
			stopScrollInvalidation = null;
			stopWatching = null;
			watched = null;
			observer = null;
			tenure = Object.freeze({});
			placementProof = null;
			stood.delete(floating);
			delete floating.dataset.lfPlane;
			for (const property of ["position-anchor", ...INSETS]) floating.style.removeProperty(property);
		}
	};
}

//#endregion
//#region runtime/annotation-overlay/comment-placement.js
function commentAttachment({ target, point = null, passage = null, boundary = null }) {
	if (!target) {
		const element = document.documentElement;
		const extent = boundary ?? commentBoundary();
		return {
			element,
			contextNode: element,
			geometry: floatingGeometry([element]),
			clear: null,
			extent,
			row: extent.top,
			lastRow: extent.top,
			column: null,
			margin: null,
			scroller: pageScroller
		};
	}
	if (!visibleTargetParts(target).length) return null;
	const margin = marginSpot(target, point, passage?.range);
	const context = point ?? passage?.contextNode ?? target;
	const element = point ?? target;
	const geometry = floatingGeometry([element, context]);
	const clips = /* @__PURE__ */ new Map();
	const shown = union(shownParts(target).map((part) => shownRect(part, clips)).filter((box) => box !== null));
	const whole = shownExtent(target) ?? target.getBoundingClientRect();
	const extent = point ? pointBand(whole, point) : whole;
	return {
		element,
		contextNode: context,
		geometry,
		clear: point ? extent : shown ?? whole,
		extent,
		row: (passage?.attachment ?? extent).top,
		lastRow: passage?.attachment ? passage.attachment.top : extent.bottom,
		column: passage?.attachment?.left ?? null,
		margin,
		scroller: scrollerFor(element)
	};
}
function commentReference(place, reference) {
	return {
		contextElement: place.element,
		contextNode: place.contextNode,
		geometry: place.geometry,
		getBoundingClientRect: () => reference
	};
}
const COMMENT_GAP = 8;
const LEAST_HEIGHT = 96;
const AXES = ["x", "y"];
function commentBoundary({ scroller = pageScroller, at = null, right = Infinity } = {}) {
	const room = (within) => {
		const across = (columns) => shownWindow({
			within,
			gap: 8,
			across: columns
		});
		return Object.assign(across(null), { across });
	};
	const { blocks, flow } = flowOf(scroller);
	const bounds = flow !== pageScroller ? shownRect(flow, /* @__PURE__ */ new Map()) : null;
	const region = bounds ? {
		bounds,
		room: room(bounds)
	} : null;
	const inRegion = region && Math.ceil(region.room.width) >= Math.ceil(cardMinimum()) && region.room.height >= 96 ? region : null;
	const cut = inRegion ? {
		left: inRegion.bounds.left,
		top: inRegion.bounds.top,
		right: inRegion.bounds.right,
		bottom: inRegion.bounds.bottom
	} : {
		left: -Infinity,
		top: -Infinity,
		right: Infinity,
		bottom: Infinity
	};
	if (at) for (const block of blocks) {
		const shown = shownRect(block, /* @__PURE__ */ new Map());
		if (!shown) continue;
		if (at.y - 8 < shown.top) cut.top = Math.max(cut.top, shown.top);
		if (at.y > shown.bottom) cut.bottom = Math.min(cut.bottom, shown.bottom);
		if (at.x < shown.left) cut.left = Math.max(cut.left, shown.left);
		if (at.x > shown.right) cut.right = Math.min(cut.right, shown.right);
	}
	const shell = inRegion ? inRegion.room : room({ right: Math.min(shellRight(), right) });
	const whole = inRegion ? flow.getBoundingClientRect() : shell;
	const key = inRegion ? [
		whole.width,
		whole.height,
		visualViewport.width,
		visualViewport.height
	] : [
		whole.left,
		whole.top,
		whole.right,
		whole.bottom
	];
	return Object.assign(shell, {
		cut: inRegion || Object.values(cut).some(Number.isFinite) ? cut : null,
		scroller: flow,
		key
	});
}
const sameBoundary = (a, b) => Math.abs(a[0] - b[0]) <= .5 && Math.abs(a[1] - b[1]) <= .5 && Math.abs(a[2] - b[2]) <= .5 && Math.abs(a[3] - b[3]) <= .5;
const vertical = (side) => side === "top" || side === "bottom";
function roomTravel(side, scroller) {
	const projection = scrollAxes(scroller).y.y;
	const direction = side === "top" ? -1 : 1;
	return {
		projection,
		direction,
		available: (direction * Math.sign(projection) < 0 ? scroller.scrollTop : Math.max(0, scrollLimit(scroller) - scroller.scrollTop)) * Math.abs(projection)
	};
}
function reachableRoom(side, extent, boundary, scroller) {
	const shown = side === "top" ? extent.top - boundary.top - 8 : boundary.bottom - extent.bottom - 8;
	const { available: travel } = roomTravel(side, scroller);
	return {
		shown,
		reachable: Math.max(0, Math.min(boundary.height - extent.height - 8, shown + travel))
	};
}
function makeRoom(side, clear, extent, height, boundary, scroller) {
	if (extent.height + 8 + height > boundary.height) return false;
	const overflow = side === "top" ? boundary.top - (clear.top - 8 - height) : clear.bottom + 8 + height - boundary.bottom;
	const { available: travel, projection, direction } = roomTravel(side, scroller);
	const movement = Math.max(0, Math.min(overflow, travel));
	if (movement <= .5) return false;
	const before = scroller.scrollTop;
	moveScrollerBy(scroller, direction * movement / projection);
	return Math.abs((scroller.scrollTop - before) * projection) > .5;
}
function commentSide({ clear, extent, boundary, width, scroller, coarse }) {
	const fits = (room) => Math.ceil(room) >= Math.ceil(width);
	if (fits(boundary.right - clear.right - 8)) return "right";
	if (fits(clear.left - boundary.left - 8)) return "left";
	const below = reachableRoom("bottom", extent, boundary, scroller);
	const above = reachableRoom("top", extent, boundary, scroller);
	const fitsBelow = below.shown >= 96;
	if (fitsBelow !== above.shown >= 96) return fitsBelow ? "bottom" : "top";
	if (coarse && below.reachable >= 96) return "bottom";
	return below.reachable > above.reachable || below.reachable === above.reachable && below.shown > above.shown ? "bottom" : "top";
}
const rootLength = (name) => parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name));
const cardMinimum = () => rootLength("--thread-card-min");
const cardMeasure = () => rootLength("--thread-card");
function commentPlacement() {
	let side = null;
	let inline = null;
	let input = null;
	let pending = null;
	let carriedInline = null;
	let initialHold = null;
	let moved = false;
	let held = null;
	let tallest = null;
	const forget = () => {
		side = null;
		inline = null;
		input = null;
		pending = null;
		carriedInline = null;
		initialHold = null;
		moved = false;
		held = null;
		tallest = null;
	};
	function options(side, ui, { clear, row, lastRow = row, column = null, margin = null, boundary, fit, edge = side === "top" ? "foot" : "top", rises = false }) {
		const minimumWidth = cardMinimum();
		const across = vertical(side);
		const unanchored = !clear;
		clear ??= new DOMRect(boundary.left, boundary.top, minimumWidth, 0);
		const past = (scale) => side === "right" && margin && margin.right > clear.right + .5 && boundary.right - margin.right - 8 >= cardMeasure() * scale.x ? margin.right : null;
		const box = new DOMRect(clear.left, clear.top, (past({ x: 1 }) ?? clear.right) - clear.left, clear.height);
		const inlineStart = unanchored ? boundary.left : clamp(column ?? box.right - minimumWidth, boundary.left, boundary.right - Math.min(minimumWidth, boundary.width));
		let heldIn = false;
		const attachment = ui.limitShift(() => ({
			mainAxis: !across,
			crossAxis: across
		}));
		const scaled = {
			name: "scaled",
			async fn(state) {
				const { rects } = state;
				const scale = await positioningScale(state);
				const right = past(scale) ?? clear.right;
				if (box.right !== right) {
					box.width = right - box.left;
					return { reset: { rects: true } };
				}
				return { data: {
					scale,
					column: rects.reference.x + (inlineStart - box.left) / scale.x,
					attachmentInline: rects.reference.x + ((column ?? clear.left) - box.left) / scale.x,
					line: column !== null ? rects.reference.y + (row - box.top) / scale.y : side === "bottom" ? rects.reference.y + rects.reference.height : side === "top" ? rects.reference.y : rects.reference.y + (row - box.top) / scale.y,
					last: rects.reference.y + (lastRow - box.top) / scale.y
				} };
			}
		};
		const measure = (state) => state.middlewareData.scaled;
		let shown = boundary;
		const overflow = (state) => {
			const { scale } = measure(state);
			const width = state.rects.floating.width * scale.x;
			const left = clamp(box.left + (state.x - state.rects.reference.x) * scale.x, boundary.left, boundary.right - width);
			shown = boundary.across({
				left,
				right: left + width
			});
			return {
				boundary: [],
				rootBoundary: shown,
				padding: 0
			};
		};
		const spot = held ?? initialHold;
		const heldEdge = spot && (edge === "foot" ? { foot: spot.foot } : { top: spot.top });
		const holding = (heldEdge || carriedInline !== null) && {
			name: "hold",
			fn(state) {
				const edge = !across && heldEdge;
				const data = {
					edge: heldEdge && ("foot" in heldEdge ? "bottom" : "top"),
					inline: carriedInline !== null ? "left" : null
				};
				const { line, attachmentInline, scale } = measure(state);
				const position = {};
				if (carriedInline !== null) position.x = attachmentInline + carriedInline / scale.x;
				if (edge) position.y = "foot" in edge ? line + edge.foot / scale.y - state.rects.floating.height : line + edge.top / scale.y;
				const spot = Object.assign({
					x: state.x,
					y: state.y
				}, position);
				return {
					...position,
					data: {
						...data,
						spot
					}
				};
			}
		};
		const size = ui.size((state) => ({
			...overflow(state),
			apply(state) {
				const { scale, line } = measure(state);
				const stood = held ? Math.max(held.foot - held.top, tallest && Math.abs(tallest.line - line) < .5 ? tallest.height : 0) / scale.y : 0;
				const lane = carriedInline !== null ? boundary.right - (column ?? clear.left) - carriedInline : across ? boundary.right - (inlineStart + (inline ?? 0) * scale.x) : side === "right" ? boundary.right - box.right - 8 : clear.left - boundary.left - 8;
				fit({
					side,
					width: Math.max(Math.min(minimumWidth, boundary.width) / scale.x, Math.min(state.availableWidth, lane / scale.x)),
					height: rises ? shown.height / scale.y : state.availableHeight,
					room: shown,
					stationary: Boolean(tallest && Math.abs(tallest.line - line) < .5),
					stood,
					scale
				});
			}
		}));
		const sizing = heldEdge ? {
			...size,
			fn(state) {
				const { shift, ...middlewareData } = state.middlewareData;
				const foot = "foot" in heldEdge;
				return size.fn({
					...state,
					placement: across ? `${foot ? "top" : "bottom"}-start` : `${side}-${foot ? "end" : "start"}`,
					middlewareData
				});
			}
		} : size;
		const middleware = [
			scaled,
			ui.offset((state) => {
				const { scale } = measure(state);
				const edge = across && heldEdge;
				let mainAxis = 8 / (across ? scale.y : scale.x);
				if (edge) {
					const top = measure(state).line - state.rects.reference.y + ("foot" in edge ? edge.foot / scale.y - state.rects.floating.height : edge.top / scale.y);
					mainAxis = side === "top" ? -top - state.rects.floating.height : top - state.rects.reference.height;
				}
				return {
					mainAxis,
					crossAxis: across ? measure(state).column - state.rects.reference.x + (inline ?? 0) : (row - 8 - box.top) / scale.y
				};
			}),
			holding,
			heldEdge && sizing,
			ui.shift((state) => ({
				...overflow(state),
				mainAxis: true,
				crossAxis: true,
				limiter: {
					...attachment,
					fn(state) {
						if (unanchored) {
							heldIn = true;
							return {
								x: state.x,
								y: state.y
							};
						}
						const limited = across ? attachment.fn(state) : {
							x: state.x,
							y: clamp(state.y, measure(state).line - state.rects.floating.height, measure(state).last)
						};
						if (moved) for (const axis of AXES) {
							const own = state.middlewareData.hold.spot[axis];
							limited[axis] = clamp(state[axis], Math.min(limited[axis], own), Math.max(limited[axis], own));
						}
						heldIn = Math.abs(limited.y - state.y) < .5;
						return limited;
					}
				}
			})),
			!heldEdge && sizing
		].filter((middleware) => !!middleware);
		return {
			reference: box,
			placement: `${side}-start`,
			middleware,
			plane: ({ middlewareData }) => {
				if (unanchored) return "window";
				const shift = middlewareData.shift?.y ?? 0;
				if (!heldIn || Math.abs(shift) < .5) return "page";
				return shift > 0 ? {
					edge: "top",
					at: shown.top - 8
				} : {
					edge: "bottom",
					at: shown.bottom + 8
				};
			}
		};
	}
	return {
		capture() {
			return {
				side,
				boundary: input?.boundary ?? null,
				moved
			};
		},
		adopt(frame) {
			forget();
			pending = frame;
		},
		forget,
		scrolled() {
			input = null;
		},
		choose({ clear, extent = clear, boundary, row = clear?.top ?? boundary.top, column = null, scroller, coarse }) {
			const unanchored = !clear;
			extent ??= boundary;
			const key = {
				unanchored,
				boundary: boundary.key,
				left: extent.left,
				right: extent.right
			};
			const frame = pending;
			pending = null;
			if (frame?.placement.boundary && sameBoundary(boundary.key, frame.placement.boundary)) {
				({side, moved} = frame.placement);
				if (side !== "left" || moved) carriedInline = frame.box.left - (column ?? clear?.left ?? boundary.left);
				const line = column !== null ? row : side === "bottom" ? clear?.bottom ?? row : side === "top" ? clear?.top ?? row : row;
				const top = frame.box.top - line;
				initialHold = {
					top,
					foot: top + frame.box.height
				};
			} else if (input && (key.unanchored !== input.unanchored || !sameBoundary(key.boundary, input.boundary) || Math.abs(key.left - input.left) > .5 || Math.abs(key.right - input.right) > .5)) forget();
			input = key;
			const fresh = side === null;
			const opening = held === null && initialHold === null;
			side ??= unanchored ? "bottom" : commentSide({
				clear,
				extent,
				boundary,
				width: cardMinimum(),
				scroller,
				coarse
			});
			return {
				side,
				fresh,
				opening,
				adopted: initialHold !== null,
				options: options.bind(null, side)
			};
		},
		landed({ x, y, middlewareData }) {
			initialHold = null;
			const { scale, column, attachmentInline, line } = middlewareData.scaled;
			if (vertical(side)) inline ??= x - column;
			else if (side !== "left") carriedInline ??= (x - attachmentInline) * scale.x;
			const top = (y - (middlewareData.shift?.y ?? 0) - line) * scale.y;
			const height = middlewareData.held.height * scale.y;
			tallest = {
				height: tallest && Math.abs(tallest.line - line) < .5 ? Math.max(tallest.height, height) : height,
				line
			};
			held = {
				top,
				foot: top + height
			};
			return { scale };
		}
	};
}

//#endregion
export { COMMENT_GAP, THREAD_CARD, cardMeasure, cardMinimum, commentAttachment, commentBoundary, commentPlacement, commentReference, floatingGeometry, floatingPlacement, floatingSelections, floatingUi, heldEdges, layoutMarginRows, makeRoom, marginColumn, marginSpot, mountMarginLayer, paintedBox, registerMarginRow, scheduleMarginEntryLabels, scheduleMarginLayout, standsFolded, syncMarginContentLayout, unregisterMarginRow };