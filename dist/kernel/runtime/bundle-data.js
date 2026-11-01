import { PAGE_PAINT_ATTRIBUTE, RUNTIME_PAINT_ATTRIBUTE, actionTemplate, afterScript, backgroundFlash, bindQueuedWork, cancelRender, dataBody, describeFailure, flashDuration, foldBlock, frameFor, generatedElement, inlineStyle, isElement, isHTML, keeps, keepsHidden, keepsText, layoutChanged, layoutPx, measure, motion, motionPlays, nextAnimation, nextFrame, nextRender, offer, offerAction, offered, offeredAction, pagePresented, renderedOrder, renderedParent, renderedUnder, renderingState, roomPx, scrollBehavior, setScroll, sizeObserver, skipped, synNodes, syntax, syntaxLanguageNames, tabStore, under, upFrom, watchArrivals, watchOwner } from "./bundle-portable.js";
import { CARET_KEYS, COLLAPSE as COLLAPSE$1, J, LIVE_ROOT, PENDING, PRESENTATION_DOM, PRESSES, TEXT_BLOCK, TEXT_BOX, TEXT_FIELD, W, Z, adoptRegistry, agentName, agentSays, applicationPresenter, applicationState, attachApplicationPresentation, authoredRank, blurFocused, caretAtKey, claimReleaseClick, currentLocationIn, currentLocationNodes, currentLocationTouches, d, decisionFor, declarationFor, deepFocus, drawn as drawn$2, editable, elementDeclarations, elementsDeclaring, eventSource, exhibits, focusDestination, focused, foldWidgetStates, hasObligationSource, holdCurrentLocation, holdFocus, html, inUi, inputCount, isElementName, isReaction, keyed, lastMovedAt, layerRoot, leafSays, live, loadShadowRules, marks, messageKey, move, nativeFocusTarget, nothing, obligationValue, offlineData, offlineInteractive, onCurrentLocation, onLetGo, onPress, onPressAway, onUserInput, pageClaimed, pageUrl, plainPress, pointerAt, projectView, projectionOrigins, projectionRegionsPresented, readApplication, readCaret, readPart, recentPlaceInput, recordedWidgetSelector, ref, registry as registry$1, render as render$1, repeat, restorePointer, revisionLabel, runtime, runtimeModule, runtimeResource, sameAnchor, seatRoot, selectsAll, share, stateSpecs, tagsDeclaring, takesLetters, threadKey, threadNames, tick, tokenEntry, turns, typesText, voiced, watchPresentation, whenApplicationPresented, whenApplicationRegionsPresented, whenDocumentPresented, whenWidgetsPresented, x } from "./bundle-layer-stack.js";
import { LayerRefused, PRESS, PRESSABLE, admitReading, admitResponse, announce, ariaShortcuts, authoredBody, bindings, buttonCommand, checked, clampedRow, commandAvailable, commandRoutes, commandScope, commandsOn, cycledRow, declareCommandReadiness, declaresCommandHandler, descriptionOf, el, holdStatus, holdingError, keys, labelOf, live as live$1, notice, pageRange, paintKeys, passErrorsAt, projectCommandScope, pruneScopedElements, raiseError, randomId, repaint, reportPageError, requestJson, reveal, revealLayer, runtimeRootState, sameLayer, savedReadingSettled, selectEnds, selectionBackward, setRuntimeRootAttribute, spell, titleOf, touchPresses as touchPresses$1, watchCommandScopes, word } from "./bundle-layer-client.js";
import { ADDRESSABLE, PAGE_CONTROL_RANK, addressableWord, addressedElements, ago, aimTargetAt, aimedTop, anchorBox, anchorForPassage, anchorForRange, anchorReading, anchorView, anchoringIsReady, atScrollEnd, chosenSince, chromeForeground, chromeRoot, claimReachStop, containingReadingRegionFor, cutFrames, datumAimTarget, datumLabel, effectiveScroller, followingItsEnd, fragmentTarget, headerLevels, isAddressable, leadingTitle, livePoint, moveScrollerBy, nameAnchor, nameable, onReadingInput, pageReadingRegion, pageScroller, placeKept, projectedDatum, reachScrollers, readingRegionFor, readingRegions, recentReadingRegion, refreshAnchorView, regionScrollBehavior, regionsSettled, registerPageControl, releaseReachStop, resolveAnchor, revealAddressed, scrollChainOf, scrollChoices, scrollLimit, scrollToEnd, scrollerFor, scrollersOf, sectionLabel, sectionOf, settleDocumentLayout, shortAgo, shownRegionBounds, stopScroll, targetElement, targetPlace, targetSegments, unconcealedReadingRegions, visualPartLabel, watchReadingRegionTransitions } from "./bundle-content-layout.js";
import { clippedContents, clippedPlace, growthAfterIsSeen, growthIsSeen, headerInset, inWindowChrome, landingBand, placeBox, placeHolder, presented, seenRect, shownBox, shownRect, shownWindow, showsContents, slotTop, stuckBox, union, userScrollport, visibleBand, whenNone } from "./bundle-geometry.js";
import { alignInlineText, alignText, authored, authoredScope, blockAt, closestAcross, elementById, elementReading, excerptWords, fencePassageParts, inChrome, labelWords, leafSurface, pageBlocks, pageDocument, pageQueryAll, pageText, pageWords, pointAt as pointAt$1, quoteFrom, quotedWords, rangeOf, readingFrom, renderRetired, segmentBlock, segmentsIn, spanIn, textNodesUnder, textUnits, verbatimBoundaryIdentity, verbatimOwnerIdentity } from "./bundle-passages.js";
import { alreadyShown, copyControl, copyTrigger, fitsWhole, landedBox, passOn, restrictUserIntent, retainUserIntent, scrollIntoReadingBand, scrollIntoView } from "./bundle-copy-control.js";
import { isCanonicalMediaUrl, readAttachedMedia, scopedMediaUrl, writeAttachedMedia } from "./media.js";
import { diffArrays } from "/vendor/jsdiff.esm.js";

//#region runtime/document-identity.js
const servedRevision = document.querySelector("meta[name=\"lf-revision\"][data-lf-runtime]")?.content;
const servedStampMarker = document.querySelector("meta[name=\"lf-version\"][data-lf-runtime]");
const servedExecutable = document.querySelector("meta[name=\"lf-executable\"][data-lf-runtime]")?.content;
function initializeServedDocument() {
	applicationState.identify(servedRevision ? parseInt(servedRevision, 10) : null, servedStampMarker ? parseInt(servedStampMarker.content, 10) : null, LIVE_ROOT);
	servedStampMarker?.remove();
}

//#endregion
//#region runtime/user-place.js
function focusedInView() {
	const node = focused();
	return node && !inWindowChrome(node) && seenRect(node, /* @__PURE__ */ new Map()) && !stuckBox(node) ? node : null;
}
function placeCandidates({ inherited, named, preferred, visible }) {
	const lead = inherited || named[0] || preferred || visible[0];
	const at = lead ? visible.indexOf(lead) : -1;
	const rest = at < 0 ? visible : [...visible.slice(at + 1), ...visible.slice(0, at + 1)];
	return [...new Set([
		inherited,
		...named,
		preferred,
		lead,
		...rest
	].filter((candidate) => Boolean(candidate)))];
}
function placeCorrection({ was, now, scrollTop, limit, held, withinTask = false }) {
	const reflowed = withinTask || limit < held.limit && held.scrollTop > limit && scrollTop === limit ? scrollTop - held.scrollTop : 0;
	return now - was - reflowed;
}
const heldScrollers = /* @__PURE__ */ new WeakMap();
const sharedMovement = (moved, paid) => Math.sign(moved) === Math.sign(paid) ? Math.sign(paid) * Math.min(Math.abs(moved), Math.abs(paid)) : 0;
function placeKeeper(scroller, { items, identity, active = () => true, preferred = () => null }) {
	let current = null;
	const owner = {};
	const lease = {
		owner,
		snapshot: () => ({
			hold: current,
			references: current?.references.filter(live) ?? []
		}),
		sync: ({ hold, references }, paid) => {
			if (current !== hold || !hold) return;
			for (const reference of references) if (live(reference)) reference.contentTop += paid;
			hold.at = {
				scrollTop: scroller.scrollTop,
				limit: limit()
			};
		}
	};
	const limit = () => scrollLimit(scroller);
	const heldBox = (node) => {
		if (!node?.isConnected || !scroller.contains(node) || !node.matches(items) || !node.checkVisibility()) return null;
		const box = node.getBoundingClientRect();
		return box.width && box.height ? box : null;
	};
	const rendered = (key) => {
		if (!key) return null;
		for (const node of scroller.querySelectorAll(items)) {
			if (identity(node) !== key) continue;
			const box = heldBox(node);
			if (box) return {
				node,
				box
			};
		}
		return null;
	};
	const live = (reference) => {
		const box = heldBox(reference.node);
		if (box) return {
			reference,
			node: reference.node,
			box
		};
		const replacement = rendered(reference.key);
		if (!replacement) return null;
		reference.node = replacement.node;
		return {
			reference,
			...replacement
		};
	};
	let returning = 0;
	function claim() {
		if (current?.spans) {
			cancelRender(returning);
			returning = 0;
			inlineStyle(scroller).setProperty("overflow-anchor", "none");
		} else if (!returning && inlineStyle(scroller).getPropertyValue("overflow-anchor")) returning = nextRender(() => {
			returning = 0;
			if (!heldScrollers.has(scroller)) inlineStyle(scroller).removeProperty("overflow-anchor");
		});
	}
	function release(hold) {
		if (current !== hold) return;
		current = null;
		if (heldScrollers.get(scroller)?.owner === owner) heldScrollers.delete(scroller);
		if (hold.spans) claim();
	}
	function correct(hold) {
		if (current !== hold || !active()) return false;
		let reading = null;
		for (const reference of hold.references) {
			reading = live(reference);
			if (reading) break;
		}
		if (!reading) return false;
		const reference = reading.reference;
		const now = reading.box.top + scroller.scrollTop;
		const was = reference.contentTop;
		const scrollWas = scroller.scrollTop;
		const delta = placeCorrection({
			was,
			now,
			scrollTop: scroller.scrollTop,
			limit: limit(),
			held: hold.at,
			withinTask: !hold.spans
		});
		if (delta) {
			moveScrollerBy(scroller, aimedTop(scroller) - scroller.scrollTop + delta);
			placeKept(scroller);
		}
		for (const candidate of hold.references) {
			const geometry = live(candidate);
			if (geometry) candidate.contentTop = geometry.box.top + scroller.scrollTop;
		}
		hold.at = {
			scrollTop: scroller.scrollTop,
			limit: limit()
		};
		if (hold.borrowed) {
			hold.borrowed.lease.sync(hold.borrowed.reading, sharedMovement(now - was, scroller.scrollTop - scrollWas));
			hold.borrowed.reading = hold.borrowed.lease.snapshot();
		}
		return true;
	}
	function take({ spans = true } = {}) {
		const enclosing = heldScrollers.get(scroller);
		if (enclosing?.owner !== owner && enclosing && spans) return null;
		const prior = current;
		if (prior) correct(prior);
		current = heldPlace(prior, spans);
		if (current && enclosing?.owner !== owner && enclosing) current.borrowed = {
			lease: enclosing,
			reading: enclosing.snapshot()
		};
		else if (current) heldScrollers.set(scroller, lease);
		else if (enclosing?.owner === owner) heldScrollers.delete(scroller);
		if (spans || prior?.spans) claim();
		return current;
	}
	function heldPlace(prior, spans) {
		if (!active()) return null;
		const band = visibleBand(scroller);
		if (!band) return null;
		const nodes = [...scroller.querySelectorAll(items)].map((node) => ({
			node,
			box: node.getBoundingClientRect()
		}));
		const tops = /* @__PURE__ */ new Map();
		const topFor = (node) => {
			const prior = tops.get(node);
			if (prior !== void 0) return prior;
			const top = band.top + headerInset(node, scroller);
			tops.set(node, top);
			return top;
		};
		const { x, y } = pointerAt();
		const over = x >= band.left && x <= band.right && y >= band.top && y <= band.bottom;
		const visible = nodes.filter(({ node, box }) => {
			return node.checkVisibility() && box.width && box.height && box.bottom > topFor(node) && box.top < band.bottom;
		}).sort((a, b) => a.box.top - b.box.top);
		const beginning = visible.filter(({ node, box }) => box.top >= topFor(node)).map(({ node }) => node);
		const shown = new Set(visible.map(({ node }) => node));
		const pointer = over ? document.elementFromPoint(x, y)?.closest?.(items) : null;
		const focus = focused()?.closest?.(items);
		const named = (recentPlaceInput() === "pointer" ? [pointer, focus] : [focus, pointer]).flatMap((candidate) => beginning.filter((node) => node === candidate));
		const reading = preferred();
		const candidates = placeCandidates({
			inherited: prior?.references.find((candidate) => live(candidate) && shown.has(candidate.node))?.node,
			named,
			preferred: visible.find(({ node }) => node === reading)?.node,
			visible: beginning
		});
		const references = [.../* @__PURE__ */ new Set([...candidates, ...visible.map(({ node }) => node)])].filter((node) => scroller.contains(node)).map((node) => ({
			node,
			key: identity(node),
			contentTop: node.getBoundingClientRect().top + scroller.scrollTop
		}));
		if (!references.length) return null;
		return {
			named: named[0] ?? null,
			references,
			at: {
				scrollTop: scroller.scrollTop,
				limit: limit()
			},
			spans
		};
	}
	function follow(hold, following) {
		if (!correct(hold) || !following()) release(hold);
		else nextFrame(() => follow(hold, following));
	}
	function finish(hold, following = () => false) {
		if (!hold) return;
		correct(hold);
		if (following()) nextFrame(() => follow(hold, following));
		else release(hold);
	}
	function around(mutate) {
		const held = take({ spans: false });
		try {
			return mutate();
		} finally {
			finish(held);
		}
	}
	return {
		take,
		finish,
		around
	};
}

//#endregion
//#region runtime/reading-place.js
const FOCUSED_PLACE = Symbol("live focused place");
const focusedPlace = (reading) => {
	const place = reading?.[FOCUSED_PLACE];
	const node = place?.node.deref();
	return place && node?.isConnected && node === focused() && under(node, place.body.deref()) && containingReadingRegionFor(node)?.id === place.region && place.intent() ? node : null;
};
const READ_BOX = Symbol("box that read the offset");
const DRAWN_PLACE = Symbol("live drawn place");
const drawnPlace = (reading) => {
	const place = reading?.[DRAWN_PLACE];
	const node = place?.node.deref();
	if (!place || !node?.isConnected || !drawsLandmark(node)) return null;
	const top = () => {
		const rect = shownBox(node);
		return rect.top + place.through * rect.height;
	};
	return {
		node,
		top
	};
};
const DRAWING = "img, svg, canvas, video, picture, iframe, object, embed";
const draws = (element) => element.matches(DRAWING) || element.localName.includes("-");
const LANDMARK_CAP = 160;
const QUOTABLE = 24;
const HEADING$1 = "h1, h2, h3, h4, h5, h6";
const textBlocks = (root = pageDocument()) => pageBlocks().filter((block) => under(block, root));
const drawsLandmark = (parent) => {
	if (!parent || skipped(parent) || getComputedStyle(parent).visibility !== "visible") return false;
	let box = parent;
	while (box && getComputedStyle(box).display === "contents") box = renderedParent(box);
	return Boolean(box?.checkVisibility({ opacityProperty: true }));
};
const blockRuns = /* @__PURE__ */ new WeakMap();
const textEnvelope = (block, segments, range) => {
	if (!segments.every(({ node }) => block.contains(node)) || [...block.querySelectorAll("*")].some(skipped)) return null;
	range.selectNodeContents(block);
	return range.getBoundingClientRect();
};
function* renderedBlocks(blocks, within = null) {
	const reading = pageText();
	let groups = blockRuns.get(reading);
	if (!groups) {
		groups = [];
		for (const segment of reading.segments) {
			let group = groups.at(-1);
			if (!group || group.block !== segment.block) groups.push(group = {
				block: segment.block,
				segments: []
			});
			group.segments.push(segment);
		}
		blockRuns.set(reading, groups);
	}
	const allowed = new Set(blocks);
	const drawn = /* @__PURE__ */ new Map();
	const range = document.createRange();
	for (const { block, segments } of groups) {
		if (!block || !allowed.has(block)) continue;
		if (inChrome(block) || skipped(block)) continue;
		if (within) {
			const own = block.getBoundingClientRect();
			if (own.height && (own.bottom <= within.top || own.top >= within.bottom)) {
				const envelope = textEnvelope(block, segments, range);
				if (envelope && (envelope.bottom <= within.top || envelope.top >= within.bottom)) continue;
			}
		}
		const boxes = [];
		const runs = [];
		let run = null;
		for (const segment of segments) {
			const { node, start, end } = segment;
			const parent = renderedParent(node);
			if (!drawn.has(parent)) drawn.set(parent, drawsLandmark(parent));
			if (!drawn.get(parent)) {
				run = null;
				continue;
			}
			range.setStart(node, start);
			range.setEnd(node, end);
			const rects = [...range.getClientRects()].filter((rect) => rect.width && rect.height);
			if (!rects.length) {
				run = null;
				continue;
			}
			if (!run) runs.push(run = {
				segments: [],
				boxes: []
			});
			run.segments.push(segment);
			run.boxes.push(...rects);
			boxes.push(...rects);
		}
		const rect = union(boxes);
		if (rect) yield [
			block,
			new DOMRect(rect.left, rect.top, rect.width, rect.height),
			runs
		];
	}
}
function passageBlock(node) {
	const blocks = pageBlocks();
	for (let at = node instanceof Element ? node : node.parentElement; at; at = upFrom(at)) if (blocks.includes(at)) return at;
	return null;
}
function openingPassage(where) {
	if (where instanceof Range) return passageBlock(where.startContainer);
	if (!where) return null;
	return renderedBlocks(pageBlocks().filter((block) => under(block, where))).next().value?.[0] ?? null;
}
function readingBounds(region) {
	const shown = region ? shownRegionBounds(region) : shownWindow();
	if (!shown) return null;
	return region && effectiveScroller(region) === pageScroller ? shownWindow({ within: shown }) : shown;
}
function* blocksOnScreen(region = null, blocks = textBlocks(), band = null) {
	const bounds = readingBounds(region);
	if (!bounds) return;
	for (const [block, rect, runs] of renderedBlocks(blocks, band ?? bounds)) {
		if (region ? !under(block, region.body) : effectiveScroller(block) !== pageScroller) continue;
		const clips = /* @__PURE__ */ new Map();
		const onScreen = runs.filter(({ boxes }) => boxes.some((box) => {
			const seen = clippedContents(box, block, clips);
			return seen && seen.bottom > bounds.top && seen.top < bounds.bottom;
		}));
		if (onScreen.length) yield [
			block,
			rect,
			onScreen.map(({ segments }) => segments)
		];
	}
}
const readingBlock = (region = null) => blocksOnScreen(region, textBlocks(region?.body)).next().value?.[0] ?? null;
function pageReading({ bodies }) {
	for (let region = pageReadingRegion(); region; region = readingRegionFor(region.host.parentElement)) {
		const block = readingBlock(region);
		if (block) return block;
		if (bodies && shownRegionBounds(region)) return region.body;
	}
	return readingBlock();
}
const pageReadingBlock = () => pageReading({ bodies: false });
function landingPlace(from = null) {
	if (from && from !== document.body && !inChrome(from)) {
		const blocks = textBlocks(from);
		const own = blocks.length ? blocks : [blockAt(from)].filter((block) => block !== null);
		const shown = blocksOnScreen(readingRegionFor(from) ?? null, own).next().value?.[0];
		if (shown) return shown;
		if (!own.length && seenRect(from, /* @__PURE__ */ new Map())) return from;
	}
	return pageReading({ bodies: true });
}
function readerColumn(bounds, body) {
	if (recentPlaceInput() === "pointer") {
		const { x, y } = pointerAt();
		return x >= bounds.left && x <= bounds.right && y >= bounds.top && y <= bounds.bottom ? x : null;
	}
	const at = focusedInView();
	if (!at || !under(at, body)) return null;
	const rect = shownBox(at);
	return (rect.left + rect.right) / 2;
}
const spans = (block, rect, column) => {
	const own = block.getBoundingClientRect();
	const across = own.width ? own : rect;
	return column >= across.left && column <= across.right;
};
function lineAt(run, edge, range, whole) {
	const boxes = (node, start, end) => {
		range.setStart(node, start);
		range.setEnd(node, end);
		return [...range.getClientRects()].filter((rect) => rect.width && rect.height);
	};
	const reaches = (rect) => rect !== void 0 && (whole ? rect.bottom : (rect.top + rect.bottom) / 2) >= edge;
	for (const [at, segment] of run.entries()) {
		const { node, start, end } = segment;
		if (!reaches(boxes(node, start, end).at(-1))) continue;
		if (whole) return run;
		let low = start;
		let high = end - 1;
		while (low < high) {
			const middle = low + high >> 1;
			if (reaches(boxes(node, middle, end)[0])) high = middle;
			else low = middle + 1;
		}
		const unit = node.data.charCodeAt(low);
		if (unit >= 56320 && unit <= 57343 && low > start) low -= 1;
		return [{
			...segment,
			start: low
		}, ...run.slice(at + 1)];
	}
	return null;
}
function lineAnchor(segments) {
	const { text, units } = readingFrom(segments);
	if (!text) return null;
	const from = units[0]?.start;
	const to = units[Math.min(units.length, LANDMARK_CAP) - 1]?.end;
	if (!from || !to) return null;
	const quoted = [];
	for (const segment of segments) {
		if (!quoted.length && segment.node !== from.node) continue;
		const start = quoted.length ? segment.start : from.offset;
		const end = segment.node === to.node ? to.offset : segment.end;
		if (end > start) quoted.push({
			...segment,
			start,
			end
		});
		if (segment.node === to.node) break;
	}
	const range = rangeOf(quoted);
	const anchor = anchorForPassage(quoted, range.commonAncestorContainer);
	return anchor?.quote && !anchor.detached ? {
		anchor: {
			...anchor,
			quote: anchor.quote
		},
		range
	} : null;
}
function scrollsAlone(node, box) {
	let alone = null;
	for (let at = renderedParent(node); at?.nodeType === 1 && at !== box; at = renderedParent(at)) if (at !== document.body && userScrollport(getComputedStyle(at).overflowY) && at.scrollHeight > at.clientHeight) alone = at;
	return alone;
}
function drawnAt(body, box, x, edge, blocks) {
	const holdsText = (element) => blocks.some((block) => under(block, element));
	for (const hit of document.elementsFromPoint(x, edge + 1)) {
		if (inChrome(hit) || inUi(hit)) continue;
		if (hit === body || !under(hit, body) || effectiveScroller(hit) !== box) return null;
		let found = scrollsAlone(hit, box);
		if (!found) {
			if (passageBlock(hit) || holdsText(hit)) return null;
			let drawing = draws(hit);
			found = hit;
			for (let up = upFrom(found); up && up !== body && !holdsText(up); up = upFrom(up)) {
				found = up;
				drawing ||= draws(up);
			}
			if (!drawing) return null;
		}
		const rect = shownBox(found);
		if (!(rect.height && rect.top <= edge + 1 && rect.bottom > edge)) return null;
		return {
			box: found,
			through: Math.max(0, (edge - rect.top) / rect.height)
		};
	}
	return null;
}
function capturePlace(region = null, blocks = textBlocks()) {
	const box = region ? effectiveScroller(region) : pageScroller;
	const band = landingBand(box);
	if (!band) return null;
	const boxTop = band.top + aimedTop(box) - box.scrollTop;
	const landmarkTop = (top, block, blockTop = top) => block?.matches(HEADING$1) ? top + Math.max(0, -blockTop) : top;
	let view = {
		y: box.scrollTop,
		scroller: scrollerIdentity(box),
		width: box.clientWidth,
		revision: runtime.currentRevision,
		[READ_BOX]: new WeakRef(box)
	};
	if (box.scrollTop === 0) view.start = true;
	const currentLocation = focusedInView();
	const body = region?.body ?? pageDocument();
	if (!body) return null;
	const currentLocationBody = readingRegionFor(currentLocation)?.body ?? body;
	const focusPlace = recentPlaceInput() === "focus" && currentLocation && under(currentLocation, body) && !under(currentLocationBody, currentLocation) ? {
		node: new WeakRef(currentLocation),
		body: new WeakRef(body),
		region: containingReadingRegionFor(currentLocation)?.id,
		intent: retainUserIntent({ source: currentLocation })
	} : null;
	if (region && followingItsEnd(box)) return {
		...view,
		...focusPlace && { [FOCUSED_PLACE]: focusPlace },
		end: true
	};
	const bounds = readingBounds(region);
	const column = bounds && readerColumn(bounds, body);
	let named = null;
	const range = document.createRange();
	const lineOf = (block, rect, runs) => {
		for (const run of runs) {
			if (quoteFrom(run).length < QUOTABLE) continue;
			const segments = lineAt(run, boxTop, range, block.matches(HEADING$1));
			if (!segments) continue;
			const landmark = lineAnchor(segments);
			if (!landmark) return null;
			return {
				block,
				rect,
				landmark,
				bottom: [...landmark.range.getClientRects()].find((r) => r.width && r.height)?.bottom ?? -Infinity
			};
		}
		return null;
	};
	let sectioned = null;
	let line = null;
	for (const [block, rect, runs] of blocksOnScreen(region, blocks)) {
		if (stuckBox(block, box) || scrollsAlone(block, box)) continue;
		const section = closestAcross(block, ADDRESSABLE);
		sectioned ??= section && {
			block,
			rect,
			section
		};
		line = lineOf(block, rect, runs);
		if (line) break;
	}
	if (line && column !== null && !spans(line.block, line.rect, column)) {
		const row = {
			top: boxTop,
			bottom: line.bottom
		};
		for (const [block, rect, runs] of blocksOnScreen(region, blocks, row)) {
			if (block === line.block || stuckBox(block, box) || scrollsAlone(block, box) || !spans(block, rect, column)) continue;
			const beside = lineOf(block, rect, runs);
			if (beside && beside.landmark.range.getBoundingClientRect().top < line.bottom) {
				line = beside;
				break;
			}
		}
	}
	if (sectioned) {
		const { block, rect, section } = sectioned;
		named = block;
		view = {
			...view,
			section: section.id,
			sectionTop: landmarkTop(shownBox(section).top - boxTop, block, rect.top - boxTop)
		};
	}
	if (line) {
		const { block, rect, landmark } = line;
		named = block;
		const section = sectionOf(landmark.anchor);
		view = {
			...view,
			...landmark.anchor,
			quoteTop: landmarkTop(landmark.range.getBoundingClientRect().top - boxTop, block),
			...landmark.anchor.section ? {
				section: landmark.anchor.section,
				sectionTop: section && landmarkTop(shownBox(section).top - boxTop, block, rect.top - boxTop)
			} : {
				section: null,
				sectionTop: null
			}
		};
	}
	if (bounds) {
		const across = shownBox(body);
		const left = Math.max(across.left, bounds.left);
		const right = Math.min(across.right, bounds.right);
		const drawn = drawnAt(body, box, column !== null && column >= left && column <= right ? column : (left + right) / 2, boxTop, blocks);
		if (drawn) {
			named = drawn.box;
			view[DRAWN_PLACE] = {
				node: new WeakRef(drawn.box),
				through: drawn.through
			};
		}
	}
	if (focusPlace && !(named && under(named, currentLocation))) view[FOCUSED_PLACE] = focusPlace;
	return view;
}
const drawnQuote = (view) => {
	const segments = targetSegments(view.quote ? resolveAnchor({
		...view,
		quote: view.quote
	}) : null);
	return segments.every(({ node }) => drawsLandmark(renderedParent(node))) ? segments : [];
};
function landmarkOf(view) {
	const live = focusedPlace(view);
	if (live) return {
		node: live,
		top: () => shownBox(live).top
	};
	const drawn = drawnPlace(view);
	if (drawn) return drawn;
	const segments = drawnQuote(view);
	const [first] = segments;
	if (first) return {
		node: first.node,
		top: () => rangeOf(segments).getBoundingClientRect().top
	};
	const section = view.section && targetElement(resolveAnchor({ section: view.section }));
	return section && drawsLandmark(section) ? {
		node: section,
		top: () => shownBox(section).top
	} : null;
}
const placeNode = (view) => landmarkOf(view)?.node ?? null;
function placeOffset(view, region = null) {
	const landmark = landmarkOf(view);
	const box = region ? effectiveScroller(region) : pageScroller;
	const band = landingBand(box);
	return landmark && band ? landmark.top() - band.top : null;
}
const hasLandmark = (reading) => Boolean(focusedPlace(reading) || drawnPlace(reading) || reading?.end || reading?.quote || reading?.section);
const sameScroller = (reading, scroller) => reading.scroller !== void 0 && reading.scroller === scrollerIdentity(scroller);
const rawOffsetFits = (reading, scroller) => sameScroller(reading, scroller) && reading.width === scroller.clientWidth && (reading.revision === runtime.currentRevision || inUi(scroller) && reading[READ_BOX]?.deref() !== scroller);
function scrollerIdentity(scroller) {
	if (scroller === pageScroller) return "$page";
	return readingRegions().find(({ body }) => body === scroller)?.id;
}
function restorePlace(view, region = null, currentIntent = retainUserIntent()) {
	if (!view || !currentIntent()) return;
	const box = region ? effectiveScroller(region) : pageScroller;
	const body = region?.body ?? pageDocument();
	const destination = focusedPlace(view);
	const currentLocation = destination && under(destination, body) ? destination : null;
	if (!currentLocation || !sameScroller(view, box)) {
		if (view.end) scrollToEnd(box);
		else if (view.start && sameScroller(view, box)) setScroll(box, {
			top: 0,
			behavior: "instant"
		});
		else {
			const band = landingBand(box);
			if (!band) return;
			const boxTop = band.top;
			const drawn = drawnPlace(view);
			const segments = drawn && under(drawn.node, body) ? [] : drawnQuote(view);
			if (drawn && under(drawn.node, body)) moveScrollerBy(box, drawn.top() - boxTop);
			else if (segments.length && view.quote) moveScrollerBy(box, rangeOf(segments).getBoundingClientRect().top - boxTop - view.quoteTop);
			else if (!currentLocation) {
				const found = view.section ? targetElement(resolveAnchor({ section: view.section })) : null;
				const section = found && drawsLandmark(found) ? found : null;
				if (section && view.section) {
					if (under(box, section)) setScroll(box, {
						top: rawOffsetFits(view, box) ? view.y : 0,
						behavior: "instant"
					});
					else moveScrollerBy(box, shownBox(section).top - boxTop - Number(view.sectionTop));
				} else if (rawOffsetFits(view, box)) setScroll(box, {
					top: view.y,
					behavior: "instant"
				});
			}
		}
	}
	if (currentLocation) scrollIntoReadingBand(currentLocation, currentLocation, "nearest", "instant");
	placeKept(box, ...currentLocation ? scrollersOf(currentLocation) : []);
}

//#endregion
//#region runtime/thread/selectors.js
const THREAD = ".lf-page-thread, [data-lf-thread-view]";
const drawnThreadId = (node) => node?.getAttribute("data-thread") ?? null;
const SAYS_IN = `${THREAD}, .lf-thread-seat`;
const SAY_ROW = ".lf-thread-reply, .lf-say";
const SAY_BOX = SAY_ROW.split(", ").map((row) => `:scope > ${row} ${TEXT_FIELD}`).join(", ");
const declaredParts = /* @__PURE__ */ new WeakMap();
const declareThreadParts = (thread, parts) => declaredParts.set(thread, parts);
const ownParts = {
	reply: (thread) => thread.querySelector(SAY_BOX),
	settlement: (thread) => {
		return [...thread.querySelectorAll(".lf-resolve, .lf-reopen")].find((control) => control.closest(".lf-page-thread, [data-lf-thread-view]") === thread) ?? null;
	}
};
function* drawingsOf(thread) {
	const id = drawnThreadId(thread);
	let at = thread;
	for (; at === thread || at && id && drawnThreadId(at) === id; at = closestAcross(upFrom(at), THREAD)) yield at;
}
function wholeThread(thread) {
	let outer = thread;
	for (const drawing of drawingsOf(thread)) outer = drawing;
	return declaredParts.get(outer)?.whole(outer) ?? outer;
}
function threadPart(thread, name) {
	for (const at of drawingsOf(thread)) {
		const part = (declaredParts.get(at) ?? ownParts)[name](at);
		if (part) return part;
	}
	return null;
}

//#endregion
//#region runtime/obligations/model.js
const readObligations = readPart((root) => root.effective.obligations);
const obligationEntry = (obligation) => obligation?.source.kind === "widget" ? registry$1[obligation.source.tag]?.["x-awaits"] : void 0;
const answeredInWords = (obligation) => hasObligationSource(obligation, "message");

//#endregion
//#region runtime/obligations/place.js
const NOWHERE = Object.freeze({
	source: null,
	context: null,
	node: null
});
function obligationPlace(item, items = readObligations().all) {
	if (item?.source.kind === "todo") {
		const node = subjectPlace(item.source.subject);
		return node ? {
			source: null,
			context: node,
			node
		} : NOWHERE;
	}
	if (item?.source.kind !== "widget") return NOWHERE;
	const owner = elementById(item.source.id);
	const source = item.source.unit ? projectedDatum(owner, item.source.unit) : owner;
	const context = elementById(item.prompt.target);
	const shared = items.some((other) => other.id !== item.id && other.source.kind === "widget" && other.prompt.target === item.prompt.target);
	return {
		source,
		context,
		node: item.source.unit || shared ? source : context
	};
}
const subjectPlace = (subject) => subject.kind === "page" ? pageHead() : subject.kind === "thread" ? null : elementById(subject.id);
const HEADINGS = ["h1", "h1, h2, h3, h4, h5, h6"];
function pageHead() {
	for (const selector of HEADINGS) {
		const heading = [...document.querySelectorAll(selector)].find((candidate) => !inChrome(candidate));
		if (heading) return heading;
	}
	const content = pageDocument();
	return content?.firstElementChild ?? content ?? document.body.firstElementChild;
}
function obligationsIn(region, items = readObligations().all) {
	return items.filter((item) => {
		if (item.status === "withdrawn") return false;
		const { source } = obligationPlace(item, items);
		return Boolean(source && under(source, region));
	});
}

//#endregion
//#region runtime/current-target.js
const sides = /* @__PURE__ */ new Map();
function declareSide(bridge, { beside = false } = {}) {
	sides.set(bridge, beside);
	return () => sides.delete(bridge);
}
function obligationHolding(items, node, inventory = items) {
	if (!node) return null;
	const holds = (element) => element && under(node, element);
	let held = null;
	for (const item of items) {
		const { source, node: target } = obligationPlace(item, inventory);
		const at = holds(source) ? source : holds(target) ? target : null;
		if (at && (!held || at !== held.at && under(at, held.at))) held = {
			item,
			at
		};
	}
	return held?.item ?? null;
}
const placeOf = (node) => placeFrom(node, /* @__PURE__ */ new Set(), true);
const arrivalOf = (node) => placeFrom(node, /* @__PURE__ */ new Set(), false);
function placeFrom(node, visited, countBeside) {
	const at = node instanceof Element ? node : node?.parentElement;
	if (!at || at === document.body || visited.has(at)) return null;
	visited.add(at);
	if (obligationHolding(readObligations().all, at)) return at;
	for (const [side, beside] of sides) {
		const place = side(at);
		if (place && beside && !countBeside) return null;
		if (place) return inChrome(place) && !obligationHolding(readObligations().all, place) ? placeFrom(place, visited, countBeside) : place;
	}
	return inChrome(at) ? null : at;
}
let heldPlace = () => null;
function holdPagePlace(read) {
	heldPlace = read;
}
const heldPagePlace = () => heldPlace()?.focus?.deref() ?? null;
function currentLocationOrigin() {
	for (const [node, place] of locations()) if (place?.isConnected || closestAcross(node, ".lf-page-thread, [data-lf-thread-view]")) {
		const panel = (place?.closest("[role=\"tab\"][aria-selected=\"true\"]"))?.ariaControlsElements?.[0];
		return panel ? {
			node,
			place: panel,
			kind: "enter"
		} : {
			node,
			place,
			kind: "current-location"
		};
	}
	return null;
}
function* locations() {
	for (const at of currentLocationNodes()) {
		const node = at instanceof Element ? at : at.parentElement;
		if (!node) continue;
		yield [node, placeOf(node)];
	}
	const held = heldPlace();
	const node = held?.focus?.deref();
	if (held && node) yield [node, held.place?.deref() ?? null];
}
let letGone = null;
onLetGo((node) => {
	letGone = new WeakRef(node);
});
onCurrentLocation((node) => {
	if (node && placeOf(node)) letGone = null;
});
const LEAVING = /* @__PURE__ */ new Set([
	"pointerdown",
	"wheel",
	"touchstart"
]);
onUserInput((event) => {
	if (LEAVING.has(event.type) && !inChrome(eventSource(event))) letGone = null;
});
function walkOrigin() {
	const here = currentLocationOrigin();
	if (here) return here;
	const node = letGone?.deref();
	const left = node?.isConnected ? placeOf(node) : null;
	if (node && left && seenRect(left, /* @__PURE__ */ new Map())) return {
		node,
		place: left,
		kind: "at"
	};
	const block = pageReadingBlock();
	return {
		node: block,
		place: block,
		kind: "at"
	};
}
function stepFrom(list, { place: here, kind }, dir, placeOfItem) {
	if (!here) return cycledRow(list, null, dir);
	if (kind === "enter") {
		const inside = list.filter((item) => {
			const place = placeOfItem(item);
			return place && renderedUnder(place, here);
		});
		if (inside.length) return cycledRow(inside, null, dir);
	}
	const reach = list.filter((item) => {
		const place = placeOfItem(item);
		if (!place) return dir > 0;
		return renderedUnder(here, place) || Math.sign(renderedOrder(here, place)) === -dir;
	});
	return (dir > 0 ? reach[0] : reach.at(-1)) ?? (dir > 0 ? list[0] : list.at(-1));
}
function heldObligation(node = focused()) {
	const item = obligationHolding(readObligations().all, placeOf(node));
	return obligationPlace(item).node;
}

//#endregion
//#region runtime/history.js
const claims = /* @__PURE__ */ new Set();
const places = /* @__PURE__ */ new Map();
function readPlace(focus = deepFocus()) {
	const place = placeOf(focus);
	const selection = getSelection();
	const range = selection?.rangeCount ? pageRange(selection) : null;
	const ends = range && [[new WeakRef(range.startContainer), range.startOffset], [new WeakRef(range.endContainer), range.endOffset]];
	if (ends && selection && range && selectionBackward(selection, range)) ends.reverse();
	return {
		focus: focus && new WeakRef(focus),
		place: place && new WeakRef(place),
		caret: readCaret(focus),
		ends,
		offset: [scrollX, scrollY]
	};
}
function returnPlace(checkpoint) {
	const focus = checkpoint.focus?.deref();
	const place = checkpoint.place?.deref();
	const { caret } = checkpoint;
	if (focus !== document.body && focus?.isConnected && presented(focus)) {
		focusDestination(focus, "return", { caret });
		if (caret) return;
	} else if (place?.isConnected && presented(place)) focusDestination(place, "return");
	else blurFocused();
	const selection = getSelection();
	if (!selection) return;
	selection.removeAllRanges();
	const anchor = checkpoint.ends && returnEnd(checkpoint.ends[0]);
	const end = checkpoint.ends && returnEnd(checkpoint.ends[1]);
	if (anchor && end) selectEnds(anchor, end);
}
function returnEnd([ref, offset]) {
	const node = ref.deref();
	if (!node || !drawn$2(node instanceof Element ? node : upFrom(node))) return null;
	const length = node instanceof CharacterData ? node.length : node.childNodes.length;
	return [node, Math.min(offset, length)];
}
let writing = false;
function write(method, state, url) {
	writing = true;
	try {
		history[method](state, "", url);
	} finally {
		writing = false;
	}
}
function pushEntry(url, state = null) {
	write("pushState", state, url);
}
function replaceEntry(url, state = history.state) {
	write("replaceState", state, url);
}
function prepareEntry() {
	const key = window.navigation?.currentEntry?.key;
	const place = readPlace();
	const offset = place.offset;
	const sourceUrl = window.location.href;
	const sourceState = history.state;
	return (url, state, replace) => {
		if (replace) {
			replaceEntry(url, state);
			return;
		}
		const arrival = {
			left: scrollX,
			top: scrollY
		};
		if (window.location.href !== sourceUrl || history.state !== sourceState) replaceEntry(sourceUrl, sourceState);
		setScroll(pageScroller, {
			left: offset[0],
			top: offset[1],
			behavior: "instant"
		});
		pushEntry(url, state);
		setScroll(pageScroller, {
			...arrival,
			behavior: "instant"
		});
		if (key) places.set(key, place);
	};
}
function claimTraversals(claim, { signal } = {}) {
	claims.add(claim);
	signal?.addEventListener("abort", () => claims.delete(claim), { once: true });
}
let mounted = false;
function mountHistory({ followFragment, returnToFragment }) {
	if (mounted) return;
	mounted = true;
	const navigation = window.navigation;
	navigation?.addEventListener("navigate", (event) => {
		if (!event.destination.sameDocument || !event.canIntercept) return;
		const url = new URL(event.destination.url);
		if (event.navigationType !== "replace") {
			const live = new Set(navigation.entries().map((entry) => entry.key));
			for (const key of places.keys()) if (!live.has(key)) places.delete(key);
			const key = navigation.currentEntry?.key;
			if (key) places.set(key, readPlace());
		}
		if (event.navigationType === "traverse") {
			const handler = claimed$1(url) ?? returnToFragment(url);
			const place = places.get(event.destination.key);
			const mayReturn = retainUserIntent({ available: () => !event.signal.aborted });
			event.intercept({
				scroll: "manual",
				focusReset: "manual",
				handler: async () => {
					if (!mayReturn()) return;
					const scrollers = /* @__PURE__ */ new Set([pageScroller, ...unconcealedReadingRegions().map((region) => region.body)]);
					await stopScroll(scrollers);
					if (!mayReturn()) return;
					let work;
					mayReturn.handoff(() => {
						work = handler?.();
					});
					const placed = await work;
					if (!mayReturn()) return;
					if (!handler || placed === false) {
						if (place) setScroll(pageScroller, {
							left: place.offset[0],
							top: place.offset[1],
							behavior: "instant"
						});
						else event.scroll();
					}
					if (place) returnPlace(place);
				}
			});
			return;
		}
		if (writing || event.formData || !url.hash) return;
		const handler = followFragment(url);
		if (handler) event.intercept({
			scroll: "manual",
			focusReset: "manual",
			handler: async () => {
				await handler();
			}
		});
	});
}
function claimed$1(url) {
	for (const claim of claims) {
		const handler = claim(url);
		if (handler) return handler;
	}
	return null;
}

//#endregion
//#region runtime/storage.js
const PAGE_SCOPE = document.documentElement.dataset.lfPageScope;
const { stored } = window.lfStorage;
const memberSelector = (holder) => registry$1[holder.localName]?.["x-views"]?.members;
function viewMembers(holder) {
	return window.lfViews.members(holder, memberSelector(holder));
}
function openingView(holder, fallback = void 0) {
	return window.lfViews.opening(holder, fallback, memberSelector(holder));
}
function markViews(holder) {
	const declaration = registry$1[holder.localName]?.["x-views"];
	if (!declaration) return;
	keeps(holder, marks["x-views"].paint, declaration.parts ? "parts" : "");
	keeps(holder, PAGE_PAINT_ATTRIBUTE.viewMembers, declaration.members);
}
function keepView(holder, member, leaving = null) {
	markViews(holder);
	return window.lfViews.keep(holder, member, leaving);
}
const draftStore = stored(() => localStorage, "local", PAGE_SCOPE);
const userStore = window.lfStorage.userStore;
const userChoice = (key, values) => Object.freeze({
	read: () => {
		const value = userStore.get(key);
		return values.find((candidate) => candidate === value) ?? null;
	},
	write: (value) => userStore.set(key, value)
});

//#endregion
//#region runtime/syntax.js
const registry = runtime.registry;
const langForPath = (path) => {
	const filename = path.slice(path.lastIndexOf("/") + 1);
	const dot = filename.lastIndexOf(".");
	return dot < 0 ? void 0 : registry.$languages.paths[filename.slice(dot + 1).toLowerCase()];
};
const LANGUAGE_CLASS = /(?:^|\s)language-([\w+.#-]+)(?=\s|$)/;
const BLOCK = "pre > code[class]";
const languageOf = (code) => {
	const lang = code.getAttribute("class")?.match(LANGUAGE_CLASS)?.[1];
	if (!lang) return void 0;
	return Object.hasOwn(syntaxLanguageNames, lang) ? syntaxLanguageNames[lang] : void 0;
};
const tokenizing = /* @__PURE__ */ new WeakSet();
async function highlightBlocks(root) {
	const blocks = [];
	const found = [...root.querySelectorAll(BLOCK)];
	if (root instanceof Element && root.matches(BLOCK)) found.unshift(root);
	for (const code of found) {
		const lang = languageOf(code);
		if (lang && code.getAttribute("data-lf-syntax") !== lang && !tokenizing.has(code)) {
			tokenizing.add(code);
			blocks.push(code);
		}
	}
	if (!blocks.length) return;
	for (const code of blocks) {
		let lang = languageOf(code);
		try {
			while (lang) {
				const source = code.textContent;
				const tokens = await syntax(source, lang);
				if (code.textContent !== source || languageOf(code) !== lang) {
					lang = languageOf(code);
					continue;
				}
				if (tokens.some(({ style }) => Object.keys(style).length)) code.replaceChildren(...synNodes(tokens));
				code.setAttribute("data-lf-syntax", lang);
				break;
			}
		} catch (err) {
			reportPageError(err, `<pre><code class="language-${lang}"> failed to highlight`);
		} finally {
			tokenizing.delete(code);
		}
	}
}

//#endregion
//#region runtime/declared-words.js
const PAGE_PAINT_ATTRIBUTES = new Set(Object.values(PAGE_PAINT_ATTRIBUTE));
const isPagePaint = (name) => PAGE_PAINT_ATTRIBUTES.has(name) || Object.values(marks).some((mark) => mark.paint === name);
function quietWord(el, word) {
	const title = el.querySelector(":scope > strong");
	const seat = title ? title.nextSibling : el.firstChild;
	const existing = el.querySelector(":scope > .lf-quiet");
	if (existing) {
		if (existing === seat && existing.textContent === word) return;
		existing.remove();
	}
	if (!word) return;
	const span = Object.assign(document.createElement("span"), {
		className: "lf-ui lf-quiet",
		textContent: word
	});
	generatedElement(span, { says: false });
	move(el, span, title ? title.nextSibling : el.firstChild);
}
function watchQuietWords() {
	const { quiet } = PAGE_PAINT_ATTRIBUTE;
	watchArrivals(`[${quiet}]`, [quiet], {
		arrive: (el) => quietWord(el, el.getAttribute(quiet)),
		leave: (el) => quietWord(el, "")
	});
}
const EXTERNAL_LINK_ATTRIBUTES = [
	"target",
	"rel",
	"aria-describedby"
];
const externalLinkState = /* @__PURE__ */ new WeakMap();
let externalDescriptionSequence = 0;
const externalDescriptions = /* @__PURE__ */ new WeakMap();
const opensElsewhere = (href) => window.lfLinks.opensElsewhere(href);
const isExternalPageLink = (link) => link instanceof HTMLAnchorElement && opensElsewhere(link.getAttribute("href"));
function externalMark() {
	return Object.assign(document.createElement("span"), {
		className: "lf-ui lf-external-mark",
		ariaHidden: "true"
	});
}
function externalDescription(link) {
	const root = link.getRootNode();
	let description = externalDescriptions.get(root);
	if (!description) {
		description = generatedElement(document.createElement("span"), { says: false });
		description.id = `lf-external-description-${++externalDescriptionSequence}`;
		description.hidden = true;
		description.dataset.lfRuntime = "";
		description.textContent = "opens in a new tab";
		externalDescriptions.set(root, description);
	}
	const holder = root instanceof Document ? root.body : root;
	if (description.parentNode !== holder) move(holder, description);
	return description.id;
}
const linkAttributes = (link) => ({
	target: link.getAttribute("target"),
	rel: link.getAttribute("rel"),
	"aria-describedby": link.getAttribute("aria-describedby")
});
const tokens$2 = (value) => value?.split(/\s+/).filter(Boolean) ?? [];
function withToken(value, token, insensitive = false) {
	const values = tokens$2(value);
	const wanted = insensitive ? token.toLowerCase() : token;
	if (!values.some((value) => (insensitive ? value.toLowerCase() : value) === wanted)) values.push(token);
	return values.join(" ");
}
function withoutToken(value, token, insensitive = false) {
	if (value === null) return null;
	const unwanted = insensitive ? token?.toLowerCase() : token;
	return tokens$2(value).filter((value) => (insensitive ? value.toLowerCase() : value) !== unwanted).join(" ");
}
function writeLinkAttributes(link, values) {
	for (const [name, value] of Object.entries(values)) keeps(link, name, value);
}
function rememberExternalLinkChanges(link, state) {
	if (!state.painted) return;
	const current = linkAttributes(link);
	for (const name of EXTERNAL_LINK_ATTRIBUTES) {
		if (current[name] === state.painted[name]) continue;
		let value = current[name];
		if (name === "rel" && state.addedNoopener) value = withoutToken(value, "noopener", true);
		if (name === "aria-describedby") value = withoutToken(value, state.markId);
		state.baseline[name] = value;
	}
}
function clearExternalLink(link, state) {
	rememberExternalLinkChanges(link, state);
	writeLinkAttributes(link, state.baseline);
	link.removeAttribute(PAGE_PAINT_ATTRIBUTE.external);
	externalLinkState.delete(link);
}
function leaveExternalLink(link) {
	const state = externalLinkState.get(link);
	if (state) clearExternalLink(link, state);
}
function renderExternalLink(link) {
	if (!(link instanceof HTMLAnchorElement)) return;
	window.lfLinks.markExternalLink(link);
	if (!isExternalPageLink(link)) {
		leaveExternalLink(link);
		return;
	}
	let state = externalLinkState.get(link);
	if (!state) {
		state = {
			baseline: linkAttributes(link),
			painted: null,
			markId: null,
			addedNoopener: false
		};
		externalLinkState.set(link, state);
	} else rememberExternalLinkChanges(link, state);
	state.markId = externalDescription(link);
	state.addedNoopener = !tokens$2(state.baseline.rel).some((value) => value.toLowerCase() === "noopener");
	writeLinkAttributes(link, {
		target: "_blank",
		rel: withToken(state.baseline.rel, "noopener", true),
		"aria-describedby": withToken(state.baseline["aria-describedby"], state.markId)
	});
	state.painted = linkAttributes(link);
}
function watchNativeContent() {
	const { keepDisclosure, finishEarlyContent } = window.lfStorage;
	watchArrivals("a, details", ["href", ...EXTERNAL_LINK_ATTRIBUTES], {
		arrive: (element) => {
			if (element instanceof HTMLDetailsElement) keepDisclosure(element);
			else renderExternalLink(element);
		},
		leave: leaveExternalLink
	});
	finishEarlyContent();
}
function paintDeclaredWords(root) {
	renderSaid(root);
	renderQuiet(root);
	return highlightBlocks(root);
}
function* elementsIn(root, selector) {
	if (isElement(root) && root.matches(selector)) yield root;
	yield* root.querySelectorAll(selector);
}
function markDeclared(root) {
	for (const [key, mark] of Object.entries(marks)) {
		const { paint, authored, message } = mark;
		if (!message) continue;
		const tags = tagsDeclaring((entry) => entry[key]);
		for (const tag of tags) {
			const declared = registry$1[tag][key];
			for (const el of elementsIn(root, tag)) {
				const value = key === "x-exhibit" ? exhibits(el, registry$1[tag]) : declared;
				if (key === "x-views") {
					markViews(el);
					continue;
				}
				keeps(el, paint, !value ? null : value === true || mark.presence ? "" : value);
			}
		}
		if (authored) {
			for (const el of elementsIn(root, `[${authored}]`)) if (mark.authored_on !== "declared" || tags.includes(el.localName)) keeps(el, paint, el.getAttribute(authored));
		}
	}
}
function renderSaid(root) {
	for (const [tag, entry] of elementDeclarations()) {
		if (!entry["x-says"]) continue;
		for (const el of elementsIn(root, tag)) for (const [attr, edge] of Object.entries(entry["x-says"])) {
			const text = el.getAttribute(attr);
			const existing = el.querySelector(`:scope > [data-lf-said="${attr}"]`);
			if (existing) {
				if (text === null) existing.remove();
				else if (existing.textContent !== text) existing.textContent = text;
				continue;
			}
			if (text === null) continue;
			const span = document.createElement("span");
			span.dataset.lfSaid = attr;
			generatedElement(span, { says: true });
			span.textContent = text;
			const pastTrailingChrome = [...el.childNodes].filter((n) => !(isElement(n) && n.getAttribute("data-lf-gen")));
			const beforeLeadingChrome = [...el.childNodes].find((n) => !(isElement(n) && n.getAttribute("data-lf-said")));
			move(el, span, (edge === "before" ? beforeLeadingChrome : pastTrailingChrome.at(-1)?.nextSibling) ?? null);
		}
	}
}
function quietFacts(el) {
	const words = el.hasAttribute(PAGE_PAINT_ATTRIBUTE.restated) ? ["rewritten since the decision"] : [];
	if (el.hasAttribute(PAGE_PAINT_ATTRIBUTE.userOverride)) words.push("my change");
	if (el.hasAttribute(PAGE_PAINT_ATTRIBUTE.reported)) words.push("reported state");
	return words.join(", ");
}
function renderQuiet(root, also = []) {
	const painting = [
		`[${PAGE_PAINT_ATTRIBUTE.restated}]`,
		`[${PAGE_PAINT_ATTRIBUTE.userOverride}]`,
		`[${PAGE_PAINT_ATTRIBUTE.reported}]`
	].join(", ");
	const targets = new Set(elementsIn(root, painting));
	for (const el of also) if (el === root || root.contains(el)) targets.add(el);
	for (const el of targets) quietWord(el, quietFacts(el));
}

//#endregion
//#region runtime/block-controls.js
const home = document.createElement("div");
home.className = "lf-block-controls";
const cuts = /* @__PURE__ */ new WeakMap();
const makeCut = () => {
	const frame = document.createElement("div");
	frame.className = "lf-block-control-cut";
	return frame;
};
const placed = /* @__PURE__ */ new Map();
const wired$1 = /* @__PURE__ */ new WeakSet();
let hoveredControl = null;
let focusedControl = null;
const activeBlock = (control) => control ? placed.get(control) : void 0;
const syncActive = (block) => {
	if (block) block.toggleAttribute("data-lf-control-active", activeBlock(hoveredControl) === block || activeBlock(focusedControl) === block);
};
const setActiveControl = (kind, control) => {
	const previous = kind === "hover" ? hoveredControl : focusedControl;
	if (previous === control) return;
	if (kind === "hover") hoveredControl = control;
	else focusedControl = control;
	syncActive(activeBlock(previous));
	syncActive(activeBlock(control));
};
onCurrentLocation((node) => {
	for (let at = node; at; at = upFrom(at)) if (at instanceof HTMLElement && placed.has(at)) return setActiveControl("focus", at);
	setActiveControl("focus", null);
});
let resized = 0;
addEventListener("resize", () => {
	resized ||= nextRender(() => {
		resized = 0;
		const read = [...placed].filter(([, block]) => !skipped(block)).map(([control, block]) => ({
			control,
			block,
			levels: headerLevels(block)
		}));
		for (const { control, block, levels } of read) standInChrome(control, block, levels);
	});
});
function standInChrome(control, block, levels) {
	const previousBlock = placed.get(control);
	const frames = cutFrames(levels, (cuts.get(control) ?? []).map(({ frame }) => frame), makeCut);
	cuts.set(control, frames);
	placed.set(control, block);
	if (!wired$1.has(control)) {
		wired$1.add(control);
		control.addEventListener("pointerenter", () => setActiveControl("hover", control));
		control.addEventListener("pointerleave", () => {
			if (hoveredControl === control) setActiveControl("hover", null);
		});
	}
	if (previousBlock !== block) {
		syncActive(previousBlock);
		syncActive(block);
	}
	if (home.parentNode !== chromeRoot) move(chromeRoot, home, null);
	const outer = frames[0]?.frame;
	if (outer && outer.parentNode !== home) move(home, outer, null);
	const frame = frames.at(-1)?.frame ?? home;
	if (control.parentNode !== frame) move(frame, control, null);
}
function anchorControl(control, block) {
	const place = () => {
		keepsHidden(control, !anchorView(control, block, place));
	};
	return {
		control,
		near: anchorView(control, block, place),
		anchor: anchorReading(block)
	};
}
function aimControl({ control, near, anchor }) {
	keepsHidden(control, !near);
	const name = nameAnchor(anchor);
	if (control.style.positionAnchor !== name) control.style.positionAnchor = name;
	return control;
}
function readInsets(block) {
	const box = block.getBoundingClientRect();
	const at = anchorBox(block);
	return {
		dx: box.left - at.left,
		dy: box.top - at.top
	};
}
function writeInsets(control, { dx, dy }) {
	for (const [property, length] of Object.entries({
		"--lf-block-control-dx": dx,
		"--lf-block-control-dy": dy
	})) {
		const value = length ? layoutPx(length) : "";
		if (control.style.getPropertyValue(property) !== value) control.style.setProperty(property, value);
	}
}
function revealControl(control, block) {
	if (cuts.has(control)) standInChrome(control, block, headerLevels(block));
	writeInsets(control, readInsets(block));
	refreshAnchorView(control);
}
function tabFromBlock(control, block, signal) {
	control.addEventListener("keydown", (event) => {
		if (event.key === "Tab") focusDestination(block, "step");
	}, { signal });
}
let pressedPath = /* @__PURE__ */ new WeakSet();
addEventListener("pointerdown", (event) => pressedPath = new WeakSet(event.composedPath()), { capture: true });
const pressedElsewhere = (event, control) => event.detail > 0 && !pressedPath.has(control);
function releaseControl(control) {
	const block = placed.get(control);
	if (hoveredControl === control) hoveredControl = null;
	if (focusedControl === control) focusedControl = null;
	control.remove();
	cuts.get(control)?.[0]?.frame.remove();
	cuts.delete(control);
	placed.delete(control);
	syncActive(block);
}

//#endregion
//#region runtime/code-copy.js
const controls = /* @__PURE__ */ new WeakMap();
const wired = /* @__PURE__ */ new WeakMap();
const deferred = /* @__PURE__ */ new WeakSet();
let prepareDocumentBlocks;
const revealed = sizeObserver((entries) => {
	nextRender(() => prepareDocumentBlocks(entries.map(({ target }) => target).filter((target) => deferred.has(target))));
});
const COPY_SCOPE = Symbol("code copy");
onCurrentLocation((node) => {
	for (let at = node; at; at = upFrom(at)) {
		if (deferred.has(at) && !skipped(at)) prepareDocumentBlocks([at]);
		const copy = controls.get(at);
		if (copy) return revealControl(copy, at);
	}
});
function prepareCodeBlock(pre, source, noun) {
	let copy = controls.get(pre);
	if (!copy) {
		const control = copyControl("lf-code-copy", {
			role: "mark",
			label: `Copy ${noun}`,
			success: `${noun.charAt(0).toUpperCase()}${noun.slice(1)} copied`,
			error: `Unable to copy ${noun}`
		});
		control.addEventListener("click", (event) => {
			if (pressedElsewhere(event, control)) {
				event.preventDefault();
				event.stopImmediatePropagation();
			} else control.value = source();
		}, { capture: true });
		pre.addEventListener("pointerdown", (event) => {
			if (event instanceof PointerEvent && event.pointerType === "touch" && control.isConnected) focusDestination(pre, "move");
		});
		pre.addEventListener("pointerenter", () => revealControl(control, pre));
		controls.set(pre, control);
		copy = control;
	}
	return anchorControl(copy, pre);
}
function declareCopy(pre, copy, noun) {
	projectCommandScope(pre, COPY_SCOPE, commandScope("On a code block", [{
		id: "code.copy",
		keys: ["Enter"],
		title: `copy ${noun}`,
		get run() {
			const trigger = copyTrigger(copy);
			return trigger ? () => trigger.click() : void 0;
		}
	}]));
}
function copyBlock(block, source, noun) {
	const copy = aimControl(prepareCodeBlock(block, source, noun));
	declareCopy(block, copy, noun);
	return copy;
}
const DECLARED = "[data-lf-copy]";
function prepareDeclaredBlocks(blocks) {
	const prepared = blocks.filter((block) => controls.get(block)?.previousSibling !== block).map((block) => {
		const noun = block.getAttribute("data-lf-copy");
		if (noun === null) throw new Error("A declared copy block needs data-lf-copy");
		return {
			block,
			noun,
			pending: prepareCodeBlock(block, () => {
				if (!block.lfCopy) throw new Error("A declared copy block needs lfCopy()");
				return block.lfCopy();
			}, noun)
		};
	});
	for (const { block, noun, pending } of prepared) {
		const copy = aimControl(pending);
		const parent = block.parentNode;
		if (!parent) continue;
		move(parent, copy, block.nextSibling);
		declareCopy(block, copy, noun);
	}
}
function watchCodeBlocks() {
	watchArrivals(DECLARED, ["data-lf-copy"], {
		arriveBatch: prepareDeclaredBlocks,
		leave(block) {
			controls.get(block)?.remove();
			projectCommandScope(block, COPY_SCOPE, null);
		}
	});
	watchArrivals("pre, table:not([role='presentation']), [data-lf-content='data']:not([data-lf-verbatim])", [], {
		arrive: (block) => block.classList.toggle("scroll", true),
		leave: () => {}
	});
	prepareDocumentBlocks = (blocks) => {
		const prepared = blocks.filter((pre) => {
			if (pre.getRootNode() !== document) return false;
			if (skipped(pre)) {
				if (!wired.has(pre) && !deferred.has(pre)) {
					deferred.add(pre);
					revealed.observe(pre);
				}
				return false;
			}
			if (deferred.delete(pre)) revealed.unobserve(pre);
			return true;
		}).map((pre) => ({
			pre,
			pending: prepareCodeBlock(pre, () => {
				const code = pre.querySelector(":scope > code");
				if (!code) throw new Error("The code block no longer holds its source");
				return code.textContent;
			}, "code"),
			levels: headerLevels(pre)
		}));
		for (const { pre, pending, levels } of prepared) {
			const copy = aimControl(pending);
			const parent = pre.parentNode;
			if (!parent) continue;
			if (leafSurface(pre)) move(parent, copy, pre.nextSibling);
			else standInChrome(copy, pre, levels);
			copy.tabIndex = -1;
			claimReachStop(pre);
			if (!wired.has(pre)) {
				const events = new AbortController();
				wired.set(pre, events);
				declareCopy(pre, copy, "code");
				const options = { signal: events.signal };
				tabFromBlock(copy, pre, events.signal);
				pre.addEventListener("pointerenter", () => copy.classList.add("lf-code-copy-hover"), options);
				pre.addEventListener("pointerleave", () => copy.classList.remove("lf-code-copy-hover"), options);
				pre.addEventListener("focus", () => copy.classList.add("lf-code-copy-focused"), options);
				pre.addEventListener("blur", () => copy.classList.remove("lf-code-copy-focused"), options);
			}
		}
	};
	watchArrivals(`pre:has(> code):not(${DECLARED})`, ["style"], {
		arriveBatch: prepareDocumentBlocks,
		leave(pre) {
			if (deferred.delete(pre)) revealed.unobserve(pre);
			wired.get(pre)?.abort();
			wired.delete(pre);
			const copy = controls.get(pre);
			if (copy?.matches(".lf-code-copy-hover, .lf-code-copy-focused")) copy.classList.remove("lf-code-copy-hover", "lf-code-copy-focused");
			if (copy) releaseControl(copy);
			releaseReachStop(pre);
			projectCommandScope(pre, COPY_SCOPE, null);
		}
	});
}

//#endregion
//#region runtime/keyboard/register.js
watchCommandScopes(() => [...[...scopes.values()].flat(), { rows: [...commands.values()] }]);
const ELEMENTS = Symbol("the scopes of the focused element");
const PAGE = Symbol("the page's own keys");
const RUNGS = Symbol("Escape's fallback ladder");
const COMMAND_REFERENCE = "command.reference.open";
const GO_TO = "navigation.go-to.open";
const STACK = [
	"command reference",
	"page map",
	"go to",
	"response options",
	"reactions",
	"page search",
	"target picker",
	ELEMENTS,
	"region capture",
	"current-location",
	"versions",
	"composer",
	"text entry",
	"thread",
	"link",
	"disclosure",
	"heading",
	"draw mode",
	"design mode",
	"todo",
	PAGE,
	RUNGS
];
const RUNG_LADDER = [
	"selection",
	"margin options",
	"floating panel",
	"draw mode",
	"design mode",
	"page",
	"changes"
];
const PAGE_COMMANDS = [
	"comment.create",
	"writing.resume",
	"message.edit.restore",
	"selection.restore",
	"target.picker.open",
	"reaction.open",
	"page.search.open",
	"page.search.repeat",
	"thread.walk",
	"queue.walk",
	"change.walk",
	"change.marks.stop",
	"page.move",
	"scroll.move",
	"reading.align.top",
	"thread.unread.first",
	"navigation.panel.threads",
	"navigation.panel.queue",
	"navigation.panel.leaves",
	"navigation.page-map",
	"version.open",
	"history.undo",
	GO_TO,
	"draw.mode.enter",
	"capture.region.open",
	"design.mode.enter",
	"annotations.toggle",
	"panel.floating.fold",
	COMMAND_REFERENCE,
	"browser.caret",
	"aim.comment"
];
const scopes = /* @__PURE__ */ new Map();
const commands = /* @__PURE__ */ new Map();
const rungs = /* @__PURE__ */ new Map();
let resolved = null;
let validated = false;
const place = (where, name) => {
	if (!where.includes(name)) throw new Error(`leaf: ${String(name)} has no place in the page's keyboard`);
};
function pageScope(name, declaration) {
	place(STACK, name);
	if (declaration.ready !== void 0) declareCommandReadiness(declaration.rows, declaration.ready);
	const declarations = scopes.get(name) ?? [];
	declarations.push(declaration);
	scopes.set(name, declarations);
	resolved = null;
	validated = false;
	paintKeys();
	return () => {
		const remaining = scopes.get(name)?.filter((item) => item !== declaration) ?? [];
		if (remaining.length) scopes.set(name, remaining);
		else scopes.delete(name);
		resolved = null;
		validated = false;
		paintKeys();
	};
}
function pageCommand(row) {
	place(PAGE_COMMANDS, row.id);
	if (commands.has(row.id)) throw new Error(`leaf: ${row.id} is declared twice`);
	commands.set(row.id, row);
	resolved = null;
	validated = false;
	paintKeys();
	return row;
}
function pageRung(name, reading) {
	place(RUNG_LADDER, name);
	const readings = rungs.get(name) ?? [];
	readings.push(reading);
	rungs.set(name, readings);
	return () => {
		const remaining = rungs.get(name)?.filter((item) => item !== reading) ?? [];
		if (remaining.length) rungs.set(name, remaining);
		else rungs.delete(name);
	};
}
function rung() {
	const steps = [];
	for (const name of RUNG_LADDER) for (const reading of rungs.get(name) ?? []) {
		const step = reading();
		if (step) steps.push({
			...step,
			name
		});
	}
	const here = focused();
	let surface = null;
	for (const { root } of steps) {
		if (!root || root === document || !renderedUnder(here, root)) continue;
		if (!surface || renderedUnder(root, surface)) surface = root;
	}
	const holds = (step) => renderedUnder(step.root ?? document, surface);
	return (surface && steps.find(holds)) ?? steps[0] ?? null;
}
const BACK_OUT = {
	id: "navigation.back",
	keys: ["Escape"],
	title: () => {
		const step = rung();
		return step ? titleOf(step) : "Back";
	},
	description: () => {
		const step = rung();
		return step ? descriptionOf(step) : void 0;
	},
	when: () => Boolean(rung()),
	get run() {
		return rung()?.out;
	}
};
function assemble() {
	const rows = PAGE_COMMANDS.flatMap((id) => commands.get(id) ?? []);
	const unanswered = rows.filter((row) => row.touch === void 0).map((row) => row.id);
	if (unanswered.length) throw new Error(`leaf: ${unanswered.join(", ")} must declare \`touch\`: its words under a finger, or false where a finger reaches it directly`);
	const unreached = [...scopes.values()].flat().flatMap((scope) => scope.rows).filter((row) => (declaresCommandHandler(row, "run") || declaresCommandHandler(row, "runKey")) && !row.exit && row.touch !== false).map((row) => row.id);
	if (unreached.length) throw new Error(`leaf: ${unreached.join(", ")} must be its stance's \`exit\` or declare \`touch: false\`: only a page command takes a finger's words`);
	return STACK.flatMap((name) => {
		if (name === PAGE) return [{ rows }];
		if (name === RUNGS) return [{
			root: () => rung()?.root ?? document,
			rows: [BACK_OUT]
		}];
		if (typeof name !== "string") return [name];
		return scopes.get(name) ?? [];
	});
}
function pageScopes() {
	if (offlineInteractive) return [ELEMENTS];
	resolved ??= assemble();
	if (!validated) {
		validated = true;
		for (const scope of resolved) if (typeof scope !== "symbol") checked(scope.rows, scope.title ?? "the page's own keys");
	}
	return resolved;
}
const namedScopes = () => STACK.flatMap((name) => typeof name === "string" ? scopes.get(name) ?? [] : []);
const exitOf = (scope) => scope.rows.find((row) => row.exit) ?? null;
function touchPresses() {
	pageScopes();
	return PAGE_COMMANDS.flatMap((id) => {
		const command = commands.get(id);
		return command ? touchPresses$1(command) : [];
	});
}
function stances() {
	pageScopes();
	return namedScopes().flatMap((scope) => {
		const exit = exitOf(scope);
		return exit ? [{
			scope,
			exit
		}] : [];
	});
}
const textEntryScopes = () => scopes.get("text entry") ?? [];
const universalCommandReference = () => offlineInteractive ? void 0 : commands.get(COMMAND_REFERENCE);
const allButCommandReference = (binding) => !PAGE_COMMANDS.flatMap((id) => {
	const row = commands.get(id);
	return id === COMMAND_REFERENCE && row ? bindings(row) : [];
}).includes(binding);
const pageDoor = (binding) => [COMMAND_REFERENCE, GO_TO].some((id) => {
	const row = commands.get(id);
	return row ? bindings(row).includes(binding) : false;
});

//#endregion
//#region runtime/heading-links.js
const HEADING = "h1, h2, h3, h4, h5, h6";
const links = /* @__PURE__ */ new Map();
const owners = /* @__PURE__ */ new WeakMap();
function headingAddress(heading) {
	let address = isAddressable(heading) ? heading : null;
	for (let at = heading.parentElement; at && leadingTitle(at) === heading;) {
		if (isAddressable(at)) address = at;
		at = at.parentElement;
	}
	return address;
}
function headingAt(node) {
	const heading = (node instanceof Element ? node : node?.parentElement)?.closest(HEADING);
	return heading && heading.getRootNode() === document && !inChrome(heading) ? heading : null;
}
function headingOn(node) {
	if (!(node instanceof Element)) return null;
	if (headingAt(node) === node) return headingAddress(node) ? node : null;
	const title = leadingTitle(node);
	return title && headingAt(title) === title && headingAddress(title) === node ? title : null;
}
const linkUrl = (address) => new URL(`#${encodeURIComponent(address.id)}`, location.href).href;
function makeLink(heading) {
	const control = copyControl("lf-heading-link", {
		label: "Copy link to section",
		success: "Link copied",
		error: "Unable to copy link",
		action: "copy-link",
		role: "symbol"
	});
	control.tabIndex = -1;
	const link = {
		heading,
		control,
		shown: /* @__PURE__ */ new Set(),
		events: new AbortController(),
		stop: () => {}
	};
	control.addEventListener("click", (event) => {
		const address = headingAddress(heading);
		if (address && !pressedElsewhere(event, control)) {
			control.value = linkUrl(address);
			return;
		}
		event.preventDefault();
		event.stopImmediatePropagation();
	}, { capture: true });
	tabFromBlock(control, heading, link.events.signal);
	owners.set(control, heading);
	links.set(heading, link);
	link.stop = watchOwner(heading, { disconnect: () => retire(link) });
	const reading = anchorControl(control, heading);
	const levels = headerLevels(heading);
	const insets = readInsets(heading);
	const line = firstLine(heading);
	aimControl(reading);
	writeInsets(control, insets);
	standInChrome(control, heading, levels);
	writeLine(control, line);
	return link;
}
function firstLine(heading) {
	const box = heading.getBoundingClientRect();
	const range = document.createRange();
	range.selectNodeContents(heading);
	const line = range.getClientRects()[0];
	return line ? {
		top: line.top - box.top,
		height: line.height
	} : {
		top: 0,
		height: box.height
	};
}
function writeLine(control, { top, height }) {
	for (const [property, length] of Object.entries({
		"--lf-heading-link-top": top,
		"--lf-heading-link-line": height
	})) {
		const value = layoutPx(length);
		if (control.style.getPropertyValue(property) !== value) control.style.setProperty(property, value);
	}
}
function retire(link) {
	link.stop();
	link.events.abort();
	releaseControl(link.control);
	links.delete(link.heading);
}
function show(heading, reason, force) {
	let link = links.get(heading);
	if (force && !headingAddress(heading)) {
		if (link) retire(link);
		return null;
	}
	if (force && !link) link = makeLink(heading);
	else if (force && link) {
		revealControl(link.control, heading);
		writeLine(link.control, firstLine(heading));
	}
	if (!link) return null;
	link.shown[force ? "add" : "delete"](reason);
	link.control.classList.toggle("lf-heading-link-shown", link.shown.size > 0);
	return link;
}
function watchHeadingLinks() {
	if (document.documentElement.lfSample) return;
	let hovered = null;
	const hover = (heading) => {
		if (heading === hovered) return;
		if (hovered) show(hovered, "hover", false);
		hovered = heading;
		if (heading) show(heading, "hover", true);
	};
	addEventListener("pointerover", (event) => {
		if (event.pointerType === "touch") return;
		const target = event.target instanceof Node ? event.target : null;
		const control = target instanceof Element && target.closest(".lf-heading-link");
		hover(control ? owners.get(control) : headingAt(target));
	}, { capture: true });
	addEventListener("pointerout", (event) => {
		if (!event.relatedTarget) hover(null);
	}, { capture: true });
	addEventListener("pointerdown", (event) => {
		if (event.pointerType !== "touch") return;
		const heading = headingAt(event.target instanceof Node ? event.target : null);
		if (heading && headingAddress(heading)) focusDestination(heading, "move");
	}, { capture: true });
	let current = null;
	const stand = (heading) => {
		if (heading === current) return heading ? links.get(heading) : null;
		if (current) show(current, "current", false);
		current = heading;
		return heading && show(heading, "current", true);
	};
	onCurrentLocation((node) => stand(node?.nodeType === Node.ELEMENT_NODE ? headingAt(node) : null));
	pageScope("heading", {
		title: "On a section heading",
		root: focused,
		at: () => Boolean(headingOn(focused())),
		when: () => pageQueryAll(HEADING).some((heading) => headingOn(heading)),
		rows: [{
			id: "heading.link.copy",
			keys: ["Enter"],
			title: "copy link to section",
			touch: false,
			run: async () => {
				const link = stand(headingOn(focused()));
				if (!link) return;
				await customElements.whenDefined(link.control.localName);
				await link.control.updateComplete;
				copyTrigger(link.control)?.click();
			}
		}]
	});
}

//#endregion
//#region runtime/video-controls.js
const PLAYER = PAGE_PAINT_ATTRIBUTE.player;
const SCOPE = Symbol("recording");
const STEP_SECONDS = 5;
const players = /* @__PURE__ */ new Map();
const clock = (seconds) => {
	const whole = Math.floor(seconds);
	return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
};
const duration = (video) => Number.isFinite(video.duration) ? video.duration : 0;
const fillScreen = (video) => {
	if (video.ownerDocument.fullscreenEnabled) return () => video.requestFullscreen();
	const enter = video.webkitEnterFullscreen;
	if (enter) return () => enter.call(video);
	return null;
};
const fills = (video) => {
	const root = video.getRootNode();
	return (root instanceof Document || root instanceof ShadowRoot) && root.fullscreenElement === video;
};
function toggle(video) {
	if (!video.paused) return video.pause();
	video.play().catch((error) => {
		if (!(error instanceof Error) || error.name !== "AbortError") throw error;
	});
}
function paintRecordingControls(video, bar, enterFullScreen) {
	keeps(bar, "data-playing", video.paused ? null : "");
	keeps(bar, "role", "group");
	keeps(bar, "aria-label", video.getAttribute("aria-label") || "Recording");
	render$1(html`<button
        ${offeredAction("symbol", "lf-video-play", !video.paused ? "Pause recording" : "Play recording", { action: "play" })}
        tabindex="-1"
      >
        ${actionTemplate("pause", "lf-action-icon")}
      </button>
      <input
        ${offered("lf-video-time")}
        type="range"
        tabindex="-1"
        min="0"
        step="any"
        max=${String(duration(video))}
        ?disabled=${!duration(video)}
        .value=${live(String(video.currentTime))}
        aria-label="Recording position"
        aria-valuetext=${`${clock(video.currentTime)} of ${clock(duration(video))}`}
        @input=${(event) => {
		if (event.currentTarget instanceof HTMLInputElement) video.currentTime = Number(event.currentTarget.value);
	}}
      />
      ${enterFullScreen ? html`<button
              ${offeredAction("symbol", "lf-video-full-screen", "Full screen", { action: "expand" })}
              tabindex="-1"
            ></button>` : nothing}`, bar);
}
function prepare(video) {
	const bar = offer("div", "lf-video-controls");
	const enterFullScreen = fillScreen(video);
	const paint = () => paintRecordingControls(video, bar, enterFullScreen);
	paint();
	const play = bar.querySelector(".lf-video-play");
	const fullScreen = bar.querySelector(".lf-video-full-screen");
	const fullScreenAction = fullScreen && enterFullScreen ? {
		control: fullScreen,
		run: enterFullScreen
	} : null;
	const player = {
		video,
		bar,
		play,
		authoredTabindex: video.getAttribute("tabindex"),
		filling: false,
		events: new AbortController(),
		scope: null,
		paint
	};
	const { signal } = player.events;
	const on = (type, listener) => video.addEventListener(type, listener, { signal });
	for (const type of [
		"play",
		"pause",
		"ended",
		"loadedmetadata",
		"durationchange"
	]) video.addEventListener(type, paint, { signal });
	on("seeked", paint);
	on("timeupdate", paint);
	let frame = 0;
	const followFrames = () => {
		paint();
		frame = video.paused || signal.aborted ? 0 : video.requestVideoFrameCallback(followFrames);
	};
	on("playing", () => {
		if (frame) video.cancelVideoFrameCallback(frame);
		frame = video.requestVideoFrameCallback(followFrames);
	});
	on("click", (event) => {
		if (plainPress(event) && !player.filling) toggle(video);
	});
	const show = (flag, force) => {
		if (force) revealControl(bar, video);
		keeps(bar, `data-${flag}`, force ? "" : null);
	};
	on("pointerenter", () => show("hovered", true));
	on("pointerleave", () => show("hovered", false));
	on("focus", () => show("keyed", video.matches(":focus-visible")));
	on("blur", () => show("keyed", false));
	tabFromBlock(bar, video, signal);
	player.scope = commandScope("On a recording", [
		{
			id: "recording.play",
			keys: [" "],
			title: () => video.paused ? "play recording" : "pause recording",
			control: play,
			run: () => {
				if (focused() === video) show("keyed", true);
				toggle(video);
			}
		},
		{
			id: "recording.step",
			keys: ["ArrowLeft", "ArrowRight"],
			routes: [{
				id: "recording.back",
				binding: "ArrowLeft",
				title: `back ${STEP_SECONDS} seconds`
			}, {
				id: "recording.forward",
				binding: "ArrowRight",
				title: `forward ${STEP_SECONDS} seconds`
			}],
			title: `back / forward ${STEP_SECONDS} seconds`,
			repeat: true,
			runKey: (binding) => {
				show("keyed", true);
				const step = binding === "ArrowLeft" ? -5 : STEP_SECONDS;
				video.currentTime = Math.min(duration(video), Math.max(0, video.currentTime + step));
			}
		},
		...fullScreenAction ? [{
			id: "recording.full-screen",
			keys: ["f"],
			title: "full screen",
			control: fullScreenAction.control,
			run: () => {
				focusDestination(video, "move");
				fullScreenAction.run();
			}
		}] : []
	]);
	video.ownerDocument.addEventListener("fullscreenchange", () => {
		if (fills(video) === player.filling) return;
		player.filling = !player.filling;
		keeps(video, "controls", player.filling ? "" : null);
		projectCommandScope(video, SCOPE, player.filling ? null : player.scope);
		show("hovered", false);
	}, { signal });
	players.set(video, player);
	return player;
}
function trade(player) {
	const { video, scope } = player;
	projectCommandScope(video, SCOPE, scope);
	keeps(video, PLAYER, "");
	keeps(video, "controls", null);
	if (player.authoredTabindex === null) keeps(video, "tabindex", "0");
	player.paint();
}
function giveBack(video) {
	const player = players.get(video);
	if (!player) return;
	players.delete(video);
	player.events.abort();
	releaseControl(player.bar);
	projectCommandScope(video, SCOPE, null);
	keeps(video, "tabindex", player.authoredTabindex);
	keeps(video, "controls", "");
	keeps(video, PLAYER, null);
}
function watchVideos() {
	const root = document.documentElement;
	const fallenBack = () => !root.hasAttribute("data-lf-interactive");
	new MutationObserver(() => {
		if (fallenBack()) for (const video of [...players.keys()]) giveBack(video);
	}).observe(root, {
		attributes: true,
		attributeFilter: ["data-lf-interactive"]
	});
	watchArrivals(`video[controls], video[${PLAYER}]`, [], {
		arriveBatch(videos) {
			if (fallenBack()) return;
			const read = videos.filter((video) => video instanceof HTMLVideoElement).filter(nameable).map((video) => {
				const player = players.get(video) ?? prepare(video);
				return {
					player,
					reading: anchorControl(player.bar, video),
					levels: headerLevels(video),
					insets: readInsets(video)
				};
			});
			for (const { player, reading, levels, insets } of read) {
				aimControl(reading);
				writeInsets(player.bar, insets);
				standInChrome(player.bar, player.video, levels);
				trade(player);
			}
		},
		leave: giveBack
	});
}

//#endregion
//#region runtime/projection/authored.js
const authoredStates = readPart((root) => root.document.authored);
const authoredParents = /* @__PURE__ */ new WeakMap();
const recordedOwner = (member, record) => {
	const selector = recordedWidgetSelector(record);
	return selector ? member.parentElement?.closest(selector) ?? null : null;
};
const ownedRecordMembers = (widget, selector, record) => [...widget.querySelectorAll(selector)].filter((member) => recordedOwner(member, record) === widget);
function domValue(el, record) {
	if (record.kind === "attribute") return ownedRecordMembers(el, `[${record.attr}]`, record).map((o) => o.id).filter(Boolean).sort();
	if (record.kind === "value") return el.getAttribute(record.attr);
	if (record.kind === "position") return el.closest(record.within)?.id ?? null;
	return elementReading(el);
}
function rememberAuthoredParents(root = document, parent = root.parentElement, original = (node) => node) {
	const remember = (element) => {
		const live = original(element);
		if (authoredParents.has(live)) return;
		authoredParents.set(live, element.parentElement ? original(element.parentElement) : parent ?? live.parentElement);
	};
	if (root.nodeType === Node.ELEMENT_NODE) remember(root);
	for (const element of root.querySelectorAll("*")) remember(element);
}
function initialState(widget, spec) {
	const record = spec.record;
	if (spec.unit !== "widget") {
		const value = {};
		if (record?.kind !== "position") return {
			value,
			units: {}
		};
		const ranks = {};
		for (const container of widget.querySelectorAll(record.within)) if (container.id && recordedOwner(container, record) === widget) {
			const ids = [...container.children].filter((part) => part.id).map((part) => part.id);
			value[container.id] = ids;
			ids.forEach((id, index) => ranks[id] = authoredRank(index));
		}
		return {
			value,
			ranks,
			units: {}
		};
	}
	let value = null;
	if (record?.kind === "attribute") value = ownedRecordMembers(widget, `[${record.attr}]`, record).map((member) => member.id).filter(Boolean).sort();
	else if (record?.kind === "value") value = widget.getAttribute(record.attr);
	else if (record?.kind === "body") value = dataBody(widget);
	return {
		action: null,
		value,
		detail: record ? { value } : {}
	};
}
function stageAuthoredStates(root = document, existing = authoredStates()) {
	const captured = /* @__PURE__ */ new Map();
	const byTag = /* @__PURE__ */ new Map();
	for (const { tag, verb, spec } of stateSpecs()) {
		const specs = byTag.get(tag) ?? /* @__PURE__ */ new Map();
		specs.set(verb, spec);
		byTag.set(tag, specs);
	}
	for (const [tag, specs] of byTag) {
		const widgets = [...root.querySelectorAll(tag)];
		if (root instanceof Element && root.matches(tag)) widgets.unshift(root);
		for (const widget of widgets) {
			if (!widget.id || existing.has(widget.id)) continue;
			captured.set(widget.id, {
				tag,
				specs,
				state: Object.fromEntries([...specs].map(([verb, spec]) => [verb, initialState(widget, spec)]))
			});
		}
	}
	return captured;
}

//#endregion
//#region runtime/widget-descriptors.js
const byElement = /* @__PURE__ */ new WeakMap();
const byId = /* @__PURE__ */ new Map();
const elements = /* @__PURE__ */ new Map();
const declaredTags = () => elementDeclarations().map(([tag]) => tag);
const candidates = (root) => {
	const tags = declaredTags();
	if (!tags.length) return [];
	const selector = tags.join(",");
	const found = [...root.querySelectorAll(selector)];
	if (root instanceof Element && root.matches(selector)) found.unshift(root);
	return found;
};
const parentOf = (element) => authoredParents.has(element) ? authoredParents.get(element) : element.parentElement;
const declaredAncestors = (element) => {
	const ancestors = [];
	for (let parent = parentOf(element); parent; parent = parentOf(parent)) if (parent.id && isElementName(parent.localName) && runtime.registry[parent.localName]) ancestors.push({
		id: parent.id,
		tag: parent.localName
	});
	return ancestors;
};
const quotedBy = (element) => {
	for (let node = parentOf(element); node; node = parentOf(node)) if (exhibits(node, runtime.registry[node.localName])) return true;
	return false;
};
function stageWidgetDescriptors(root = document, documentContext = {
	kind: "page",
	revision: runtime.currentRevision
}) {
	const captured = /* @__PURE__ */ new Map();
	const bindings = [];
	for (const element of candidates(root)) {
		if (!element.id) continue;
		const existing = byElement.get(element);
		if (existing && existing.document.kind === documentContext.kind && (documentContext.kind === "thread" || existing.document.kind === "page" && existing.document.revision === documentContext.revision)) {
			captured.set(element.id, existing);
			continue;
		}
		const declaration = structuredClone(runtime.registry[element.localName]);
		const ancestors = declaredAncestors(element);
		const descriptor = {
			id: element.id,
			tag: element.localName,
			document: structuredClone(documentContext),
			declaration,
			parent: ancestors[0] ?? null,
			ancestors,
			quoted: quotedBy(element)
		};
		bindings.push({
			element,
			descriptor
		});
		captured.set(element.id, descriptor);
	}
	return Object.freeze({
		descriptors: captured,
		bindings: Object.freeze(bindings)
	});
}
function commitWidgetDescriptors(stage, retired = /* @__PURE__ */ new Set()) {
	for (const id of retired) {
		byId.delete(id);
		elements.delete(id);
	}
	for (const { element, descriptor } of stage.bindings) {
		byElement.set(element, descriptor);
		byId.set(descriptor.id, descriptor);
		elements.set(descriptor.id, element);
	}
}
const widgetElement = (id) => elementById(id) ?? elements.get(id) ?? null;
function widgetDescriptor(owner) {
	const captured = byElement.get(owner);
	if (captured) return captured;
	const replacement = byId.get(owner.id);
	if (!replacement || !descriptorStillMatches(owner, replacement)) return null;
	byElement.set(owner, replacement);
	return replacement;
}
const quoted = (element) => widgetDescriptor(element)?.quoted ?? quotedBy(element);
const descriptorStillMatches = (owner, descriptor) => owner.id === descriptor.id && owner.localName === descriptor.tag;

//#endregion
//#region runtime/markdown.js
const escapeHtml = (text) => text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
const escapedSource = (text) => escapeHtml(text);
let render = escapedSource;
let renderInline = escapedSource;
let tokenize = null;
let ready;
const renderMarkdown = (text, breaks = true) => render(text, breaks);
function renderedWords(html, imageAlt = false) {
	const parsed = document.createElement("template");
	parsed.innerHTML = html;
	return fragmentWords(parsed.content, imageAlt);
}
function fragmentWords(fragment, imageAlt = false) {
	for (const br of fragment.querySelectorAll("br")) br.replaceWith(document.createTextNode("\n"));
	if (imageAlt) for (const image of fragment.querySelectorAll("img")) image.replaceWith(document.createTextNode(image.alt));
	return fragment.textContent;
}
const markdownWords = (text) => renderedWords(renderMarkdown(text));
const renderInlineMarkdown = (text, breaks = true) => renderInline(text, breaks);
function inlineMarkdownFragment(text, breaks = true) {
	const parsed = document.createElement("template");
	parsed.innerHTML = renderInlineMarkdown(text, breaks);
	return parsed.content;
}
async function loadDeclaredMarkdown(scope) {
	if (!(isElement(scope) && declarationFor(scope, "x-text-format")) && !elementsDeclaring(scope, "x-text-format").length) return;
	let failure;
	if (!await loadMarkdown((error) => failure = error)) throw new Error(`leaf: Markdown renderer failed to load: ${describeFailure(failure)}`);
}
function formatDeclaredMarkdown(scope) {
	const elements = elementsDeclaring(scope, "x-text-format");
	if (isElement(scope) && declarationFor(scope, "x-text-format")) elements.unshift(scope);
	if (!elements.length) return;
	if (!tokenize) throw new Error("leaf: Markdown formatting requires its loaded renderer");
	for (const element of elements) {
		if (declarationFor(element, "x-text-format") === "markdown") {
			const pre = element.querySelector(":scope > pre");
			if (!pre) continue;
			const body = element.querySelector(":scope > .lf-markdown-body") ?? document.createElement("div");
			if (body.className !== "lf-markdown-body") body.className = "lf-markdown-body";
			paintMarkdown(body, dataBody(element));
			body.removeAttribute("data-lf-prepaint");
			body.removeAttribute("data-lf-gen");
			pre.replaceWith(body);
			continue;
		}
		for (const node of [...element.childNodes]) {
			if (!(node instanceof Text) || !node.data.trim()) continue;
			const parsed = inlineMarkdownFragment(node.data, false);
			if (!parsed.firstElementChild && parsed.textContent === node.data) continue;
			const words = document.createElement("span");
			words.className = "lf-markdown-words";
			words.dataset.lfMarkdownWords = "";
			words.dataset.lfSourceWords = node.data;
			words.append(parsed);
			node.replaceWith(words);
		}
	}
}
function paintMarkdown(element, source) {
	if (element.getAttribute("data-lf-source-words") === source && !element.hasAttribute("data-lf-prepaint")) return;
	const markup = renderMarkdown(source, false);
	if (element.getAttribute("data-lf-source-words") !== source) element.setAttribute("data-lf-source-words", source);
	if (element.innerHTML !== markup) element.innerHTML = markup;
}
const characters = new Intl.Segmenter(void 0, { granularity: "grapheme" });
function inlineSourcePositions(source, raw, at, limit, cell) {
	const start = at + source.slice(at, limit).trimEnd().length - raw.length;
	if (!cell && start >= at && source.startsWith(raw, start)) return Array.from({ length: raw.length + 1 }, (_, i) => start + i);
	const positions = [at];
	let sourceAt = at;
	let inlineAt = 0;
	for (const run of alignText(source.slice(at, limit), raw, characters, Infinity)) if (run.kind === "delete") sourceAt += run.text.length;
	else {
		for (let i = 0; i < run.text.length; i++) {
			positions[inlineAt++] = sourceAt;
			if (run.kind === "same") sourceAt++;
		}
		positions[inlineAt] = sourceAt;
	}
	return positions;
}
function parserItem(values, index) {
	const value = values[index];
	if (value === void 0) throw new Error(`leaf: Markdown parser index ${index} is outside its ${values.length} source positions`);
	return value;
}
const isInlineToken = (token) => token.type === "inline";
const isPositionedInline = (token) => token.type === "inline";
const hasSourceSpan = (token) => token.lfSource?.source !== void 0;
const isBeforeLinkifiedInline = (token) => token.type === "inline";
const isBeforeJoinedInline = (token) => token.type === "inline";
const isBlockPlacement = (placed, type) => placed.token.type === type;
function placedMarkdownTokens(source) {
	const tokens = markdownTokens(source);
	if (!tokens) return [];
	const starts = [0];
	for (let at = 0; at < source.length; at++) {
		if (source[at] === "\r" && source[at + 1] === "\n") at++;
		if (source[at] === "\r" || source[at] === "\n") starts.push(at + 1);
	}
	starts.push(source.length);
	const found = [];
	let inlineAt = 0;
	let previous;
	for (const token of tokens) {
		const before = previous;
		previous = token;
		const from = token.map ? parserItem(starts, token.map[0]) : 0;
		const to = token.map ? parserItem(starts, token.map[1]) : source.length;
		if (!isPositionedInline(token)) {
			if (token.map && (token.nesting === 1 || BLOCK_LEAVES.has(token.type))) {
				const placed = {
					token,
					from,
					to,
					markers: token.lfSource?.markers?.map(([line, a, b]) => [parserItem(starts, line) + a, parserItem(starts, line) + b]),
					words: token.nesting ? null : token.content
				};
				found.push(placed);
			}
			continue;
		}
		let wordsAt = Math.max(from, inlineAt);
		for (const block of found) if (isBlockPlacement(block, "blockquote_open") || isBlockPlacement(block, "list_item_open")) {
			for (const [a, b] of block.markers) if (a >= wordsAt && a < parserItem(starts, token.map[0] + 1) && b > wordsAt) wordsAt = b;
		}
		const positions = inlineSourcePositions(source, token.lfSource.sourceContent, wordsAt, to, before?.type === "td_open" || before?.type === "th_open");
		const stack = [];
		for (const child of token.children) {
			if (!hasSourceSpan(child)) continue;
			let [a, b] = child.lfSource.source;
			if (child.nesting === 1) {
				if (child.markup && child.markup !== "linkify" && child.markup !== "autolink") a = b - child.markup.length;
				const placed = {
					token: child,
					from: parserItem(positions, a),
					to: parserItem(positions, b),
					content: [parserItem(positions, b), parserItem(positions, b)]
				};
				found.push(placed);
				stack.push(placed);
			} else if (child.nesting === -1) {
				const placed = stack.pop();
				if (!placed) continue;
				if (child.markup && child.markup !== "linkify" && child.markup !== "autolink") b = a + child.markup.length;
				placed.to = parserItem(positions, b);
				placed.content[1] = parserItem(positions, a);
			} else found.push({
				token: child,
				from: parserItem(positions, a),
				to: parserItem(positions, b),
				words: child.type === "softbreak" || child.type === "hardbreak" ? "\n" : child.type === "image" ? admittedUrl(child.attrGet("src")) !== null ? "" : renderedWords(renderInlineMarkdown(source.slice(parserItem(positions, a), parserItem(positions, b)))) : child.type === "html_inline" ? "" : child.content,
				spelled: (child.lfSource.spelled ?? []).map(([from, to, shown]) => [
					parserItem(positions, from),
					parserItem(positions, to),
					shown
				])
			});
		}
		inlineAt = parserItem(positions, positions.length - 1);
	}
	return found;
}
function markdownSourceOffset(body, node, offset) {
	if (!body.contains(node)) return null;
	const range = document.createRange();
	range.selectNodeContents(body);
	const shown = fragmentWords(range.cloneContents());
	range.setEnd(node, offset);
	const aim = fragmentWords(range.cloneContents()).length;
	const source = body.dataset.lfSourceWords;
	if (source === void 0) return null;
	let shownAt = 0;
	let sourceEnd = 0;
	for (const placed of placedMarkdownTokens(source)) {
		const { token, from, to } = placed;
		if (token.nesting) continue;
		const words = placed.words;
		if (!words) continue;
		const start = shown.indexOf(words, shownAt);
		if (start < 0) continue;
		if (aim < start) return from;
		if (aim <= start + words.length) {
			let sourceAt = from;
			let tokenAt = start;
			for (const run of alignText(source.slice(from, to), words, characters, Infinity)) if (run.kind === "delete") sourceAt += run.text.length;
			else {
				if (aim <= tokenAt + run.text.length) return sourceAt + (run.kind === "same" ? aim - tokenAt : 0);
				tokenAt += run.text.length;
				if (run.kind === "same") sourceAt += run.text.length;
			}
			return to;
		}
		shownAt = start + words.length;
		sourceEnd = to;
	}
	return sourceEnd;
}
const markdownReady = () => render !== escapedSource;
const WEB_PROTOCOLS = /* @__PURE__ */ new Set([
	"http:",
	"https:",
	"mailto:"
]);
function admittedUrl(href) {
	if (href === null) return null;
	href = String(href);
	if (href.startsWith("#")) return href;
	try {
		return WEB_PROTOCOLS.has(new URL(href, location.href).protocol) ? href : null;
	} catch {
		return null;
	}
}
const probe = document.createElement("template");
function renderedElement(markup, tag) {
	probe.innerHTML = markup;
	const element = probe.content.firstElementChild;
	if (!element || element.localName !== tag) throw new Error(`leaf: Markdown renderer did not produce its ${tag} element`);
	return element;
}
const markdownTokens = (text) => tokenize?.(text) ?? null;
function sourcePositions(markdown) {
	const NativeState = markdown.inline.State;
	markdown.inline.State = class extends NativeState {
		sourcePendingFrom = null;
		pushPending() {
			const from = this.sourcePendingFrom ?? this.pos - this.pending.length;
			const to = from + this.pending.length;
			const token = super.pushPending();
			token.lfSource = {
				...token.lfSource,
				source: [from, to]
			};
			this.sourcePendingFrom = null;
			return token;
		}
		push(...args) {
			const token = super.push(...args);
			token.lfSource = {
				...token.lfSource,
				sourceAt: this.pos
			};
			return token;
		}
	};
	const nativeRules = markdown.inline.ruler.getRules.bind(markdown.inline.ruler);
	const wrapped = /* @__PURE__ */ new WeakMap();
	markdown.inline.ruler.getRules = (chain) => nativeRules(chain).map((rule) => {
		const known = wrapped.get(rule);
		if (known) return known;
		const instrumented = (state, silent) => {
			const from = state.pos;
			const pendingFrom = from - state.pending.length;
			if (!silent && !state.pending) state.sourcePendingFrom = from;
			const count = state.tokens.length;
			const ok = rule(state, silent);
			if (!ok || silent) return ok;
			const emitted = state.tokens.slice(count).filter((token) => !token.lfSource?.source);
			let delimiterAt = from;
			for (const token of emitted) {
				let span = [from, state.pos];
				if (token.type === "text" && emitted.every((item) => item.type === "text")) {
					span = [delimiterAt, delimiterAt + token.content.length];
					delimiterAt = span[1];
				} else if (token.type === "link_open") span = [from, token.lfSource.sourceAt];
				else if (token.type === "link_close") span = [token.lfSource.sourceAt, state.pos];
				if (token.markup === "linkify" || emitted.some((item) => item.markup === "linkify") && token.type === "text") {
					const start = state.tokens.slice(count).find((item) => !emitted.some((emitted) => emitted === item))?.lfSource?.source?.[1] ?? pendingFrom;
					span = token.type === "link_open" ? [start, start] : token.type === "link_close" ? [state.pos, state.pos] : [start, state.pos];
				} else if (emitted.some((item) => item.markup === "autolink")) span = token.type === "link_open" ? [from, from + 1] : token.type === "link_close" ? [state.pos - 1, state.pos] : [from + 1, state.pos - 1];
				token.lfSource = {
					...token.lfSource,
					source: span,
					spelled: token.type === "text_special" && token.content !== token.markup ? [[...span, token.content]] : token.type === "hardbreak" && state.src[span[0]] === "\\" ? [[
						span[0],
						span[0] + 1,
						""
					]] : []
				};
			}
			return ok;
		};
		wrapped.set(rule, instrumented);
		return instrumented;
	});
	const keepJoined = (before, after) => {
		const alive = new Set(after);
		let first = null;
		let spelled = [];
		for (const { token, source, spellings } of before) {
			spelled.push(...spellings);
			if (source && !first && (token.type !== "text" || token.content)) first = source;
			if (alive.has(token)) {
				if (source && first && token.type === "text") token.lfSource = {
					...token.lfSource,
					source: [first[0], source[1]]
				};
				if (token.lfSource) token.lfSource.spelled = spelled;
				first = null;
				spelled = [];
			}
		}
	};
	const snapshot = (tokens) => tokens.map((token) => ({
		token,
		source: token.lfSource?.source,
		spellings: token.lfSource?.spelled ?? []
	}));
	const secondRules = markdown.inline.ruler2.getRules.bind(markdown.inline.ruler2);
	markdown.inline.ruler2.getRules = (chain) => secondRules(chain).map((rule) => (state) => {
		const before = snapshot(state.tokens);
		rule(state);
		keepJoined(before, state.tokens);
	});
	markdown.core.ruler.after("inline", "source_content", (state) => {
		for (const token of state.tokens) if (isInlineToken(token)) token.lfSource = {
			...token.lfSource,
			sourceContent: token.content
		};
	});
	markdown.core.ruler.before("linkify", "source_before_linkify", (state) => {
		for (const token of state.tokens) if (isPositionedInline(token)) {
			let inLink = 0;
			token.lfSource.beforeLinks = token.children.map((child, index) => {
				if (child.type === "link_open") inLink++;
				else if (child.type === "link_close") inLink--;
				let source = child.lfSource?.source;
				if (!inLink && source && child.type === "text" && child.content) {
					const at = token.lfSource.sourceContent.slice(source[0], source[1]).indexOf(child.content);
					if (at < 0) throw new Error("leaf: Markdown text token lost its source");
					const box = token.children[index - 1];
					if (at && box?.type === "html_inline") box.lfSource = { source: [source[0], source[0] + at] };
					source = [source[0] + at, source[0] + at + child.content.length];
					child.lfSource = {
						...child.lfSource,
						source
					};
				}
				return {
					token: child,
					content: child.content,
					source,
					links: !inLink && child.type === "text" ? markdown.linkify.match(child.content) ?? [] : []
				};
			});
		}
	});
	markdown.core.ruler.after("linkify", "source_after_linkify", (state) => {
		for (const inline of state.tokens) if (isBeforeLinkifiedInline(inline)) {
			const before = inline.lfSource.beforeLinks;
			let at = 0;
			let textAt = 0;
			let link = null;
			for (const token of inline.children) {
				if (token.lfSource?.source || before[at]?.token === token) {
					while (at < before.length && parserItem(before, at).token !== token) at++;
					at++;
					textAt = 0;
					link = null;
					continue;
				}
				if (textAt === before[at]?.content.length && token.type !== "link_close") {
					at++;
					textAt = 0;
				}
				const original = before[at];
				if (!original?.source) continue;
				let span;
				if (token.type === "link_open") {
					link = original.links.find((match) => match.index >= textAt && markdown.normalizeLink(match.url) === token.attrGet("href")) ?? null;
					if (!link) throw new Error("leaf: Markdown autolink lost its source");
					textAt = link.index;
					span = [textAt, textAt];
				} else if (token.type === "link_close") {
					if (!link) throw new Error("leaf: Markdown autolink closed without its source");
					textAt = link.lastIndex;
					span = [textAt, textAt];
					link = null;
				} else if (link) {
					span = [link.index, link.lastIndex];
					textAt = link.lastIndex;
				} else {
					const from = original.content.indexOf(token.content, textAt);
					if (from < 0) throw new Error("leaf: Markdown linkified text lost its source");
					textAt = from + token.content.length;
					span = [from, textAt];
				}
				token.lfSource = {
					...token.lfSource,
					source: [original.source[0] + span[0], original.source[0] + span[1]]
				};
			}
			Reflect.deleteProperty(inline.lfSource, "beforeLinks");
		}
	});
	markdown.core.ruler.before("text_join", "source_before_join", (state) => {
		for (const token of state.tokens) if (isPositionedInline(token)) token.lfSource.beforeJoin = snapshot(token.children);
	});
	markdown.core.ruler.after("text_join", "source_after_join", (state) => {
		for (const token of state.tokens) if (isBeforeJoinedInline(token)) {
			keepJoined(token.lfSource.beforeJoin, token.children);
			Reflect.deleteProperty(token.lfSource, "beforeJoin");
		}
	});
}
const BLOCK_LEAVES = /* @__PURE__ */ new Set(["fence", "hr"]);
function makeMarkdown(module, breaks) {
	const markdown = new module.MarkdownIt({
		html: false,
		breaks,
		linkify: true
	}).disable(["lheading", "code"]).use(module.taskLists, { enabled: false });
	markdown.linkify.set({ fuzzyLink: false });
	markdown.core.ruler.after("block", "blank_lines", (state) => {
		const lines = state.src.split("\n");
		for (const token of state.tokens) {
			if (!token.map || !(token.nesting === 1 || BLOCK_LEAVES.has(token.type))) continue;
			let gap = 0;
			for (let at = token.map[0] - 1; at >= 0 && gap < 3; at--) {
				if (parserItem(lines, at).replace(/^[\s>]*/, "")) break;
				gap++;
			}
			token.attrSet("data-lf-gap", String(gap));
		}
	});
	markdown.renderer.rules.softbreak = (_tokens, _at, options) => options.breaks ? "<br>" : "\n";
	markdown.renderer.rules.hardbreak = () => "<br>";
	markdown.validateLink = () => true;
	const admitLinks = (tokens) => {
		const links = [];
		for (const token of tokens) {
			if (token.type === "link_open") {
				const url = admittedUrl(token.attrGet("href"));
				token.lfSource = {
					...token.lfSource,
					url
				};
				links.push(url);
			} else if (token.type === "link_close") {
				const url = links.pop();
				if (url === void 0) throw new Error("leaf: Markdown link closed without its opening");
				token.lfSource = {
					...token.lfSource,
					url
				};
			}
			if (token.children) admitLinks(token.children);
		}
	};
	markdown.core.ruler.push("safe_links", (state) => {
		for (const block of state.tokens) if (isInlineToken(block)) admitLinks(block.children);
	});
	markdown.renderer.rules.text_special = (tokens, at, options, env, renderer) => markdown.utils.escapeHtml(parserItem(tokens, at).content);
	markdown.renderer.rules.link_open = (tokens, at, options, env, renderer) => {
		const token = parserItem(tokens, at);
		const href = token.lfSource?.url;
		if (href === null || href === void 0) return "";
		if (isCanonicalMediaUrl(href)) token.attrSet("href", scopedMediaUrl(href));
		return renderer.renderToken(tokens, at, options);
	};
	markdown.renderer.rules.link_close = (tokens, at, options, env, renderer) => {
		const url = parserItem(tokens, at).lfSource?.url;
		return url !== null && url !== void 0 ? renderer.renderToken(tokens, at, options) : "";
	};
	markdown.renderer.rules.image = (tokens, at, options, env, renderer) => {
		const token = parserItem(tokens, at);
		const href = admittedUrl(token.attrGet("src"));
		if (!token.children) throw new Error("leaf: Markdown image has no parsed label");
		const alt = renderedWords(renderer.renderInline(token.children, options, env), true);
		token.attrSet("alt", alt);
		if (href === null) return escapeHtml(alt);
		const markup = renderer.renderToken(tokens, at, options);
		if (!isCanonicalMediaUrl(href)) return markup;
		const image = renderedElement(markup, "img");
		const source = scopedMediaUrl(href);
		image.setAttribute("src", source);
		const button = document.createElement("button");
		button.type = "button";
		button.className = "lf-media-open lf-message-media";
		button.setAttribute("data-lf-offer", "button");
		button.setAttribute("data-lf-said", "");
		button.setAttribute("data-lf-media-url", source);
		button.setAttribute("aria-label", `View ${alt || "Image"}`);
		button.append(image);
		return button.outerHTML;
	};
	return markdown;
}
function loadMarkdown(onError = null) {
	const attempt = ready ??= import("/vendor/markdown-it.esm.js").then((module) => {
		const markdown = makeMarkdown(module, true);
		let softBreaks;
		let positioned;
		const dialect = (breaks) => breaks ? markdown : softBreaks ??= makeMarkdown(module, false);
		render = (text, breaks) => dialect(breaks).render(text);
		renderInline = (text, breaks) => dialect(breaks).renderInline(text);
		tokenize = (text) => {
			if (!positioned) {
				positioned = makeMarkdown(module, true);
				sourcePositions(positioned);
			}
			return positioned.parse(text, {});
		};
	});
	return attempt.then(() => true).catch((error) => {
		if (ready === attempt) ready = void 0;
		onError?.(error);
		return false;
	});
}

//#endregion
//#region runtime/widget-imports.js
function registeredTags(scope, registry) {
	return [.../* @__PURE__ */ new Set([...isElement(scope) ? [scope.localName] : [], ...[...scope.querySelectorAll("*")].map((element) => element.localName)])].filter((tag) => isElementName(tag) && Object.hasOwn(registry, tag));
}
function widgetImports(scope, registry) {
	const modules = [];
	const tags = registeredTags(scope, registry);
	for (const tag of tags) if (registry[tag]?.["x-upgrade"]) modules.push(tag);
	return {
		modules,
		shadow: tags.some((tag) => registry[tag]?.["x-shadow"] || Object.values(registry[tag]?.["x-state"] ?? {}).some((state) => state.creates && registry[state.creates.child]?.["x-shadow"]))
	};
}

//#endregion
//#region runtime/widget-loader.js
const rememberedPassageRoots = /* @__PURE__ */ new WeakSet();
const within = (scope, selector) => [...isElement(scope) && scope.matches(selector) ? [scope] : [], ...scope.querySelectorAll(selector)];
function rememberPassageParts(scope = document, source = ["page", null], original = (node) => node) {
	for (const tag of tagsDeclaring((entry) => entry["x-upgrade"] && !entry["x-verbatim"])) for (const root of within(scope, tag)) {
		const live = original(root);
		if (rememberedPassageRoots.has(live)) continue;
		rememberedPassageRoots.add(live);
		fencePassageParts(live, [...root.children].map(original));
	}
	for (const [ownerIndex, root] of preservingOwners(scope).entries()) {
		const live = original(root);
		if (rememberedPassageRoots.has(live)) continue;
		rememberedPassageRoots.add(live);
		identifyPreserving(root, [...source, ownerIndex], original);
	}
}
const preservingOwners = (scope) => within(scope, "*").filter((root) => registry$1[root.localName]?.["x-verbatim"]);
function identifyPreserving(root, owner, original = (node) => node) {
	verbatimOwnerIdentity.set(original(root), owner);
	let boundaryIndex = 0;
	const visit = (parent) => {
		for (const child of parent.children) if (registry$1[child.localName]?.["x-upgrade"]) verbatimBoundaryIdentity.set(original(child), {
			owner,
			index: boundaryIndex++
		});
		else visit(child);
	};
	visit(root);
}
function reindexPassageOwners(scope = document, source = ["page", null]) {
	for (const [ownerIndex, root] of preservingOwners(scope).entries()) identifyPreserving(root, [...source, ownerIndex]);
}
const registryUrl = () => runtimeResource("/registry.json");
const widgetUrl = (tag) => offlineInteractive ? runtimeModule(`/widgets/${tag}.js`) : runtimeResource(`/widgets/${tag}.js`);
async function loadWidgetDependencies(scope) {
	await Promise.all([loadDeclaredMarkdown(scope), ...widgetImports(scope, registry$1).shadow ? [loadShadowRules()] : []]);
}
async function importWidgetModules(scope) {
	const required = widgetImports(scope, registry$1);
	await Promise.all(required.modules.map((tag) => import(widgetUrl(tag))));
}
async function preloadWidgets(scope) {
	await loadWidgetDependencies(scope);
	await importWidgetModules(scope);
}
async function importWidgets(scope) {
	await loadWidgetDependencies(scope);
	formatDeclaredMarkdown(scope);
	await importWidgetModules(scope);
}
async function installDocument(scope) {
	const presentation = attachApplicationPresentation("document:installation");
	try {
		watchNativeContent();
		watchQuietWords();
		watchCodeBlocks();
		watchHeadingLinks();
		watchVideos();
		await importWidgets(scope);
		await settle(presentation, scope, [scope], whenApplicationPresented);
	} finally {
		presentation.disconnect();
	}
}
async function patchDocument(scope, patch) {
	const presentation = attachApplicationPresentation("document:patch");
	try {
		const { roots, widgets, ...result } = patch();
		await settle(presentation, scope, roots, () => whenWidgetsPresented(widgets));
		return result;
	} finally {
		presentation.disconnect();
	}
}
async function settle(presentation, scope, arrived, presented) {
	const painted = Promise.all(arrived.map(paintDeclaredWords));
	const presenting = presentation.present();
	presenting.resolve(painted);
	await presenting.ready;
	await presented();
	reachScrollers(scope);
}
async function prepareDocument(captured) {
	const response = await fetch(registryUrl());
	if (!admitResponse(response)) return false;
	if (!response.ok) throw new Error(`leaf: registry failed to load (${response.status})`);
	adoptRegistry(await response.json());
	if (!sameLayer(registry$1.$layer.generation)) return false;
	const scope = captured.source;
	if (!scope) throw new Error("The initial document has no authored root");
	const original = (node) => captured.pairs.require(node);
	rememberPassageParts(scope, ["page", null], original);
	rememberAuthoredParents(scope, null, original);
	const descriptors = stageWidgetDescriptors(scope);
	const authored = stageAuthoredStates(scope, /* @__PURE__ */ new Map());
	const prior = readApplication().document;
	applicationState.captureDocument({
		...prior,
		registry: { ...registry$1 },
		authored: new Map([...prior.authored, ...authored]),
		descriptors: new Map([...prior.descriptors, ...descriptors.descriptors])
	});
	commitWidgetDescriptors({
		...descriptors,
		bindings: descriptors.bindings.map(({ element, descriptor }) => ({
			element: original(element),
			descriptor
		}))
	});
	return true;
}
async function upgradeWidgets({ buildReactionBar }) {
	revealLayer();
	buildReactionBar();
	await installDocument(document.body);
	return true;
}

//#endregion
//#region runtime/drafts.js
const DRAFT = "lf-draft:";
const PAGE_DRAFT = "general";
const whereDraft = (ctx) => draftStore.where(DRAFT + ctx);
const DRAFT_NEWS = "lf-drafts";
const draftCache = /* @__PURE__ */ new Map();
const tellDraft = (ctx, value, payload = void 0) => document.dispatchEvent(new CustomEvent(DRAFT_NEWS, { detail: {
	ctx,
	value,
	payload
} }));
const parseDraftRecord = (value) => {
	if (typeof value !== "string") return null;
	try {
		const record = JSON.parse(value);
		if (!record || typeof record !== "object" || typeof record.attempt !== "string" || !(record.base === null || typeof record.base === "string") || (record.settled === true ? Object.keys(record).some((key) => ![
			"attempt",
			"base",
			"settled"
		].includes(key)) : typeof record.text !== "string" || record.payload !== void 0 && (!record.payload || typeof record.payload !== "object" || Array.isArray(record.payload)) || record.held !== void 0 && typeof record.held !== "string" || Object.keys(record).some((key) => ![
			"attempt",
			"text",
			"base",
			"payload",
			"held"
		].includes(key)))) return null;
		return record;
	} catch {
		return null;
	}
};
const storedDraft = (ctx) => {
	const read = draftStore.read(DRAFT + ctx);
	return read.available ? parseDraftRecord(read.value) : null;
};
const attemptAccepted = (attempt) => runtime.receipts.some((event) => event.attempt === attempt);
const writeDraftRecord = (ctx, record) => draftStore.set(DRAFT + ctx, JSON.stringify(record));
const rawDraftRecord = (ctx) => {
	const cached = draftCache.get(ctx);
	if (cached) return cached.record;
	const read = draftStore.read(DRAFT + ctx);
	const record = read.available ? parseDraftRecord(read.value) : null;
	if (record) draftCache.set(ctx, {
		record,
		durable: true
	});
	return record;
};
const sameDraftRecord = (left, right) => left === null && right === null || left !== null && right !== null && JSON.stringify(left) === JSON.stringify(right);
const projectDraftRecord = (ctx, record) => queueMicrotask(() => {
	const current = draftCache.get(ctx)?.record ?? null;
	if (!sameDraftRecord(current, record)) return;
	const active = current && !current.settled && !attemptAccepted(current.attempt);
	tellDraft(ctx, active ? current.text : null, active ? current.payload : void 0);
});
const sharedIsBaseOf = (branch, shared) => branch.base === null ? shared === null : shared?.attempt === branch.base;
const replyContext = (key) => `reply:${key}`;
const rewriteContext = (id) => `rewrite:${id}`;
function threadDraft(ctx) {
	if (ctx.startsWith("reply:")) return {
		part: "reply",
		name: ctx.slice(6)
	};
	if (ctx.startsWith("rewrite:")) return {
		part: "rewrite",
		name: ctx.slice(8)
	};
	return null;
}
const isReply = (ctx) => threadDraft(ctx)?.part === "reply";
const refreshDraftRecord = (ctx) => {
	const cached = draftCache.get(ctx);
	const read = draftStore.read(DRAFT + ctx);
	if (!read.available) return cached?.record ?? null;
	const shared = parseDraftRecord(read.value);
	if (cached && !cached.durable) {
		if (sameDraftRecord(cached.record, shared)) {
			cached.durable = true;
			return cached.record;
		}
		if (sharedIsBaseOf(cached.record, shared)) {
			if (cached.record.settled) cached.durable = writeDraftRecord(ctx, cached.record);
			return cached.record;
		}
	}
	const changed = Boolean(cached && !sameDraftRecord(cached.record, shared));
	if (shared) draftCache.set(ctx, {
		record: shared,
		durable: true
	});
	else draftCache.delete(ctx);
	if (changed) projectDraftRecord(ctx, shared);
	return shared;
};
const sentAttempts = /* @__PURE__ */ new Map();
const unsettledDraftRecord = (ctx) => {
	const record = rawDraftRecord(ctx);
	return record && !record.settled && !attemptAccepted(record.attempt) ? record : null;
};
const activeDraftRecord = (ctx) => {
	const record = unsettledDraftRecord(ctx);
	return sentAttempts.get(ctx) === record?.attempt ? null : record;
};
const draftHasContent = (ctx) => Boolean(unsettledDraftRecord(ctx)?.text);
const settleDraft = (ctx, attempt) => {
	const current = refreshDraftRecord(ctx);
	if (!current || current.settled || current.attempt !== attempt) return null;
	const currentDurable = draftCache.get(ctx)?.durable;
	const storedRecord = {
		attempt,
		base: attempt,
		settled: true
	};
	const durable = writeDraftRecord(ctx, storedRecord);
	const record = durable ? storedRecord : {
		attempt,
		base: currentDurable ? current.attempt : current.base,
		settled: true
	};
	draftCache.set(ctx, {
		record,
		durable
	});
	return record;
};
const saveDraft = (ctx, text, payload, held = carriedHeld(ctx)) => {
	const cached = draftCache.get(ctx);
	const previous = rawDraftRecord(ctx);
	const base = cached && !cached.durable && previous ? previous.base : previous?.attempt ?? null;
	const record = {
		text,
		attempt: randomId(),
		base,
		...payload === void 0 ? {} : { payload },
		...held ? { held } : {}
	};
	const durable = writeDraftRecord(ctx, record);
	draftCache.set(ctx, {
		record,
		durable
	});
	return durable;
};
const carriedHeld = (ctx) => {
	const previous = rawDraftRecord(ctx);
	return previous && !previous.settled && sentAttempts.get(ctx) !== previous.attempt ? previous.held : void 0;
};
const holdReply = (ctx, held) => {
	const current = activeDraftRecord(ctx);
	if (!current) return false;
	const { held: _, ...rest } = current;
	const record = held ? {
		...rest,
		held
	} : rest;
	draftCache.set(ctx, {
		record,
		durable: writeDraftRecord(ctx, record)
	});
	return true;
};
const clearDraft = (ctx) => {
	const current = rawDraftRecord(ctx);
	if (!current || current.settled) {
		draftCache.delete(ctx);
		return false;
	}
	return settleDraft(ctx, current.attempt);
};
function transferDraft(from, to, text, payload) {
	const source = activeDraftRecord(from);
	if (!source || from === to) return false;
	const editor = [...draftEditors].find((view) => view.ctx === from) ?? [...draftEditors].find((view) => view.ctx === to);
	const selection = writingPlace?.context === from ? writingPlace.selection : readCaret(editor ? editorInput(editor) : null);
	const held = [carriedHeld(to), carriedHeld(from)].filter(Boolean).join("\n\n") || null;
	const durable = isReply(to) ? saveDraft(to, held ? `${text}\n\n${held}` : text, payload, null) : saveDraft(to, text, payload, held);
	const place = {
		context: to,
		selection: selection ?? [0, 0],
		generation: randomId()
	};
	keepWritingPlace(place);
	const settled = durable && settleDraft(from, source.attempt);
	if (settled) projectDraftRecord(from, settled);
	tellDraft(to, activeDraftRecord(to)?.text ?? text, payload);
	return place;
}
function restoreDraft(ctx, text, payload) {
	refreshDraftRecord(ctx);
	if (draftHasContent(ctx)) return false;
	saveDraft(ctx, text, payload);
	tellDraft(ctx, text, payload);
	return true;
}
const loadDraft = (ctx) => activeDraftRecord(ctx);
const draftContexts = () => /* @__PURE__ */ new Set([...draftCache.keys(), ...draftStore.keys().filter((key) => key.startsWith(DRAFT)).map((key) => key.slice(9))]);
function settleAcceptedDrafts() {
	for (const ctx of draftContexts()) {
		const record = refreshDraftRecord(ctx);
		if (record && !record.settled && attemptAccepted(record.attempt) && settleDraft(ctx, record.attempt)) tellDraft(ctx, null);
	}
}
function claimDraft(ctx, owns) {
	const before = activeDraftRecord(ctx);
	const refreshed = refreshDraftRecord(ctx);
	const current = refreshed && !refreshed.settled && !attemptAccepted(refreshed.attempt) ? refreshed : null;
	if (!before || !current || current.attempt !== before.attempt || current.text !== before.text || !owns()) return null;
	return current;
}
const standGesture = (ctx, current) => {
	sentAttempts.set(ctx, current.attempt);
	tellDraft(ctx, null);
	return (sent) => {
		if (sentAttempts.get(ctx) === current.attempt) sentAttempts.delete(ctx);
		if (sent) {
			if (settleDraft(ctx, current.attempt)) tellDraft(ctx, null);
			return;
		}
		if (activeDraftRecord(ctx)?.attempt !== current.attempt) return;
		tellDraft(ctx, current.text);
	};
};
async function sendDraft(ctx, owns, send) {
	const current = claimDraft(ctx, owns);
	if (!current) return null;
	const flight = send(current.attempt, current.payload);
	const answer = standGesture(ctx, current);
	const sent = await flight;
	answer(sent);
	return sent;
}
function sendMessage(ctx, owns, send) {
	const current = claimDraft(ctx, owns);
	if (!current) return null;
	const flight = send(current.attempt, current.payload);
	const answer = standGesture(ctx, current);
	if (!flight) {
		answer(null);
		return null;
	}
	if (!isReply(ctx)) {
		openedFrom.set(current.attempt, ctx);
		const under = replyContext(current.attempt);
		if (current.held && !activeDraftRecord(under)) {
			saveDraft(under, current.held);
			tellDraft(under, current.held);
		}
	}
	const previousPlace = writingPlace;
	const sentPlace = previousPlace?.context === ctx ? {
		context: isReply(ctx) ? ctx : replyContext(current.attempt),
		selection: [0, 0],
		generation: previousPlace.generation
	} : null;
	if (sentPlace) keepWritingPlace(sentPlace);
	Promise.resolve(flight).then((sent) => {
		answer(sent);
		if (sent) openedFrom.delete(current.attempt);
		if (!sent && sentPlace && writingPlace?.generation === sentPlace.generation && writingPlace.context === sentPlace.context) keepWritingPlace(previousPlace);
	});
	return {
		attempt: current.attempt,
		id: `${PENDING}${current.attempt}`
	};
}
const openedFrom = /* @__PURE__ */ new Map();
const draftEditors = /* @__PURE__ */ new Set();
const WRITING_PLACE = "lf-writing-place";
const isPlace = (place) => {
	if (place === null || typeof place !== "object" || !("context" in place) || typeof place.context !== "string" || !("generation" in place) || typeof place.generation !== "string" || !("selection" in place) || !Array.isArray(place.selection)) return false;
	const [start, end, direction] = place.selection;
	return Number.isInteger(start) && Number.isInteger(end) && (direction === void 0 || direction === "forward" || direction === "backward" || direction === "none");
};
const savedWritingPlaces = () => {
	try {
		const value = draftStore.get(WRITING_PLACE);
		if (value === null) return [null, []];
		const stored = JSON.parse(value);
		if (!isPlace(stored)) return [null, []];
		const earlier = "earlier" in stored && Array.isArray(stored.earlier) ? stored.earlier.filter(isPlace) : [];
		const { context, selection, generation } = stored;
		return [{
			context,
			selection,
			generation
		}, earlier];
	} catch {
		return [null, []];
	}
};
let [writingPlace, earlierPlaces] = savedWritingPlaces();
const writingRoutes = /* @__PURE__ */ new Map();
const writingRoute = (ctx) => [...writingRoutes].find(([prefix]) => ctx.startsWith(prefix))?.[1];
const editorInput = (editor) => typeof editor.input === "function" ? editor.input() : editor.input;
const storeWritingPlace = () => draftStore.set(WRITING_PLACE, writingPlace && JSON.stringify({
	...writingPlace,
	earlier: earlierPlaces
}));
const keepWritingPlace = (place) => {
	const previous = writingPlace;
	if (previous && place && previous.context !== place.context) earlierPlaces = [...earlierPlaces.filter(({ context }) => context !== previous.context && context !== place.context), previous].slice(-8);
	writingPlace = place;
	storeWritingPlace();
};
function forgetWritingPlace(ctx) {
	earlierPlaces = earlierPlaces.filter(({ context }) => context !== ctx);
	if (writingPlace?.context !== ctx) return storeWritingPlace();
	writingPlace = null;
	let place;
	while (!writingPlace && (place = earlierPlaces.pop())) if (draftHasContent(place.context) || writingRoute(place.context)?.(place.context)?.hasContent) writingPlace = place;
	storeWritingPlace();
}
function keepRefusedWords(attempts) {
	const atEnd = (ctx) => {
		const end = (activeDraftRecord(ctx)?.text ?? "").length;
		return [end, end];
	};
	let held = 0;
	for (const attempt of attempts) {
		const from = openedFrom.get(attempt);
		openedFrom.delete(attempt);
		const under = replyContext(attempt);
		const box = activeDraftRecord(under);
		if (from === void 0 || !box || !holdReply(from, box.text)) continue;
		const resumed = writingPlace?.context === under;
		clearDraft(under);
		if (resumed) keepWritingPlace({
			context: from,
			selection: atEnd(from),
			generation: randomId()
		});
		if (box.text) held += 1;
	}
	const returned = attempts.flatMap((attempt) => {
		const ctx = [...draftContexts()].find((context) => activeDraftRecord(context)?.attempt === attempt);
		return ctx === void 0 ? [] : [ctx];
	});
	const shownIn = (ctx) => [...draftEditors].filter((view) => view.ctx === ctx).map((view) => editorInput(view)).find((input) => input?.isConnected && input.checkVisibility()) ?? null;
	const hidden = returned.filter((ctx) => !shownIn(ctx));
	const resumes = returned.find((ctx) => ctx === writingPlace?.context);
	if (resumes !== void 0 && writingPlace) keepWritingPlace({
		...writingPlace,
		selection: atEnd(resumes)
	});
	for (const ctx of hidden.toReversed()) if (writingPlace?.context !== ctx) keepWritingPlace({
		context: ctx,
		selection: atEnd(ctx),
		generation: randomId()
	});
	const sentences = [hidden.length && "Draft kept — g i resumes writing", held && "Reply kept — it comes back once its comment is saved"].filter(Boolean);
	return {
		said: sentences.length ? sentences.join(". ") : null,
		field: returned.map(shownIn).find(Boolean) ?? null
	};
}
const writingEditor = () => [...draftEditors].find((editor) => editorInput(editor) === focused());
const keepWritingCaret = () => {
	const editor = writingEditor();
	if (editor && editor.ctx === writingPlace?.context) keepWritingPlace({
		...writingPlace,
		selection: readCaret(editorInput(editor))
	});
};
function rememberWriting(input) {
	const editor = [...draftEditors].find((view) => editorInput(view) === input);
	if (editor) keepWritingPlace({
		context: editor.ctx,
		selection: readCaret(input),
		generation: randomId()
	});
}
document.addEventListener("input", (event) => {
	const path = event.composedPath();
	const editor = [...draftEditors].find((view) => {
		const input = editorInput(view);
		return input !== null && path.includes(input);
	});
	if (editor) rememberWriting(editorInput(editor));
});
document.addEventListener("keyup", (event) => {
	if (CARET_KEYS.includes(event.key) || selectsAll(event)) keepWritingCaret();
});
document.addEventListener("pointerup", keepWritingCaret);
function registerWritingDestination(prefix, reveal) {
	writingRoutes.set(prefix, reveal);
	return () => writingRoutes.delete(prefix);
}
function moveToPage(ctx) {
	const words = loadDraft(ctx)?.text ?? "";
	const text = [loadDraft(PAGE_DRAFT)?.text, words].filter(Boolean).join("\n\n");
	const place = transferDraft(ctx, PAGE_DRAFT, text);
	if (!place) return false;
	const shift = text.length - words.length;
	const [start, end, ...direction] = place.selection;
	keepWritingPlace({
		...place,
		selection: [
			start + shift,
			end + shift,
			...direction
		]
	});
	return true;
}
function createWritingResume({ revealInThread, arriveEditor, holdsThreadDraft }) {
	const holdsBox = (ctx) => threadDraft(ctx) ? holdsThreadDraft(ctx) : Boolean(writingRoute(ctx)) || [...draftEditors].some((view) => view.ctx === ctx);
	const resume = async () => {
		const place = writingPlace;
		if (!place) return;
		const intent = retainUserIntent();
		let input;
		if (threadDraft(place.context)) input = await revealInThread(place.context, intent);
		else {
			const resolve = () => {
				const route = writingRoute(place.context);
				const editor = [...draftEditors].find((view) => view.ctx === place.context && view.resume);
				return route ? route(place.context) : editor?.resume?.();
			};
			input = await arriveEditor(resolve, {
				intent,
				caret: place.selection
			});
		}
		if (input === void 0 || !intent()) return;
		const editor = [...draftEditors].find((view) => view.ctx === place.context && editorInput(view) === input);
		const field = editor && editorInput(editor);
		if (field?.isConnected && field.checkVisibility() && !field.readOnly && !("disabled" in field && field.disabled)) {
			intent.handoff(() => {
				passErrorsAt(field);
				focusDestination(field, "move", { caret: place.selection });
			});
			return;
		}
		if (runtime.showsActive && !holdsBox(place.context) && moveToPage(place.context)) {
			notice("Its box is gone, so its words moved to a comment on the page");
			return resume();
		}
		raiseError(`That writing place is unavailable${runtime.showsActive ? "" : " on this version"}`);
	};
	return {
		id: "writing.resume",
		keys: ["i"],
		title: "Resume writing",
		touch: "Resume writing",
		menu: "keys",
		travels: true,
		when: () => writingPlace !== null,
		run: resume
	};
}
function captureDraftEditing(at = focused()) {
	for (const editor of draftEditors) {
		const input = editorInput(editor);
		if (!input || input !== at) continue;
		const scroll = [input.scrollLeft, input.scrollTop];
		return {
			context: editor.ctx,
			mirrored: editor.mirrored,
			attempt: activeDraftRecord(editor.ctx)?.attempt,
			words: input.value,
			selection: readCaret(input),
			scroll
		};
	}
	return null;
}
const draftEditingStands = (editing) => editing !== null && activeDraftRecord(editing.context)?.attempt === editing.attempt;
function draftEditingDestination(editing, handoff) {
	const shown = (view) => Boolean(editorInput(view)?.checkVisibility({ visibilityProperty: true }));
	const placed = (view) => editorInput(view)?.isConnected;
	const roots = [...draftEditors].filter((view) => view.ctx === editing.context && !view.mirrored && (placed(view) || view.resume));
	const editor = roots.find(shown) ?? roots.find(placed) ?? roots[0];
	if (!editor) return null;
	const open = shown(editor) ? null : editor.resume?.()?.open;
	if (open) handoff(open);
	return shown(editor) ? editorInput(editor) : null;
}
function restoreDraftEditing(editing, input) {
	if (!draftEditingStands(editing)) return false;
	for (const editor of draftEditors) {
		const field = editorInput(editor);
		if (!field || field !== input) continue;
		if (editor.ctx !== editing.context || !field.isConnected || !field.checkVisibility() || field.value !== editing.words || focused() !== field) return false;
		focusDestination(field, "return", { caret: editing.selection });
		[field.scrollLeft, field.scrollTop] = editing.scroll;
		return true;
	}
	return false;
}
function watchDraft(ctx, callback, { input = null, mirrored = false, resume = null } = {}) {
	const editor = input && {
		ctx,
		input,
		mirrored,
		resume
	};
	if (editor) draftEditors.add(editor);
	const update = (ev) => ev.detail.ctx === ctx && callback(ev.detail.value, ev.detail.payload);
	document.addEventListener(DRAFT_NEWS, update);
	return () => {
		document.removeEventListener(DRAFT_NEWS, update);
		if (editor) draftEditors.delete(editor);
	};
}
function watchDrafts(prefix, callback) {
	const update = (ev) => ev.detail.ctx.startsWith(prefix) && callback(ev.detail.ctx);
	document.addEventListener(DRAFT_NEWS, update);
	return () => document.removeEventListener(DRAFT_NEWS, update);
}
addEventListener("storage", (ev) => {
	const prefix = whereDraft("").key;
	if (!ev.key?.startsWith(prefix)) return;
	const ctx = ev.key.slice(prefix.length);
	const incoming = parseDraftRecord(ev.newValue);
	const cached = draftCache.get(ctx);
	const current = cached?.record;
	if (current && !cached.durable) {
		if (sameDraftRecord(current, incoming)) cached.durable = true;
		else if (sharedIsBaseOf(current, incoming)) {
			cached.durable = writeDraftRecord(ctx, current);
			return;
		}
	}
	if (incoming) draftCache.set(ctx, {
		record: incoming,
		durable: true
	});
	else draftCache.delete(ctx);
	const active = incoming && !incoming.settled && !attemptAccepted(incoming.attempt);
	tellDraft(ctx, active ? incoming.text : null, active ? incoming.payload : void 0);
});
function mirrorDraft(ta, sync, ctx, { retained = false, mirrored = false, resume = null, onChange = () => {}, blank = () => "" } = {}) {
	const off = watchDraft(ctx, (value) => {
		if (!retained && !ta.isConnected) return off();
		sync.load(value ?? blank());
		onChange(value);
	}, {
		input: ta,
		mirrored,
		resume
	});
	return off;
}

//#endregion
//#region runtime/off-flow.js
const surfaces = /* @__PURE__ */ new Map();
function offFlowSurfaceOf(node) {
	for (const [surface, { floats }] of surfaces) if (floats() && under(node, surface)) return surface;
	return null;
}
const unseen = (node, surface) => {
	const box = node.getBoundingClientRect();
	const bounds = surface.getBoundingClientRect();
	const shown = shownWindow();
	return Math.max(box.top, bounds.top) < shown.top - 1 || Math.min(box.bottom, bounds.bottom) > shown.bottom + 1;
};
function follow({ surface, floats, away, bringBack }, node, behavior) {
	if (floats() && (away() || unseen(node, surface))) bringBack(behavior);
}
function declareOffFlowSurface(surface, { floats = () => true, away = () => false, bringBack }) {
	const reading = {
		surface,
		floats,
		away,
		bringBack
	};
	surfaces.set(surface, reading);
	surface.addEventListener("lf-before-edit", (event) => {
		if (isElement(event.target)) follow(reading, event.target, scrollBehavior());
	}, { capture: true });
}
onCurrentLocation((node, cause, left) => {
	if (!node || !left || cause === "return") return;
	for (const reading of surfaces.values()) {
		const { surface } = reading;
		if (under(node, surface) && under(left, surface)) follow(reading, node, scrollBehavior());
	}
});
function bringBackSurfaceOf(node, behavior = scrollBehavior()) {
	for (const reading of surfaces.values()) if (under(node, reading.surface)) follow(reading, node, behavior);
}

//#endregion
//#region runtime/thread/reply-landing.js
const replyRowOf = (held, control) => {
	const reply = control === held ? [...held.children].find((node) => node.matches(SAY_ROW)) : control.closest(SAY_ROW);
	return reply?.parentElement === held ? reply : null;
};
const pinnedReply = (reply) => reply != null && stuckBox(reply) === reply ? reply : null;
const separateTranscript = (held) => {
	const transcript = held.querySelector(":scope > .lf-thread-transcript");
	return transcript && userScrollport(getComputedStyle(transcript).overflowY) ? transcript : null;
};
const landingTarget = (held, control) => {
	const reply = replyRowOf(held, control);
	if (control !== held && !pinnedReply(reply) && alreadyShown(control)) return { node: null };
	if (fitsWhole(held)) return { node: held };
	if (pinnedReply(reply)) return control === held ? { node: null } : {
		node: held,
		block: "end"
	};
	if (reply && fitsWhole(reply)) return { node: reply };
	if (control === held && alreadyShown(held)) return { node: null };
	return { node: control };
};
const onScreen = (node) => seenRect(node, /* @__PURE__ */ new Map()) !== null;
const returnTurn = (transcript, unread) => {
	const turns = [...transcript.querySelectorAll(":scope > :is(.lf-msg, .lf-thread-checkpoint)")];
	let start = unread ? turns.find((node) => node.getAttribute("data-message") === unread) ?? null : null;
	while (start && !showsContents(start)) start = start.previousElementSibling;
	return start ?? turns.findLast((node) => showsContents(node)) ?? null;
};
function showReturnTurn(transcript, thread) {
	const scroller = scrollerFor(transcript);
	scrollToEnd(scroller);
	const unread = thread?.unread[0]?.message;
	const start = thread?.msgs.find((message) => message.id === unread)?.key;
	const turn = returnTurn(transcript, start ?? null);
	if (!turn) return;
	const over = scroller.getBoundingClientRect().top + scroller.clientTop + slotTop(scroller) - turn.getBoundingClientRect().top;
	if (over > (turn.firstElementChild?.getBoundingClientRect().height ?? 0)) moveScrollerBy(scroller, -over);
}
function landThread(held, control, behavior, block) {
	bringBackSurfaceOf(held, behavior);
	const transcript = separateTranscript(held);
	if (transcript && control !== held && replyRowOf(held, control)) {
		scrollToEnd(transcript, behavior);
		return;
	}
	if (transcript?.contains(control)) {
		scrollIntoView(control, {
			behavior,
			block
		});
		return;
	}
	const target = landingTarget(held, control);
	scrollIntoView(target.node, {
		behavior,
		block: target.block ?? block
	});
}
const landings = /* @__PURE__ */ new WeakMap();
function keepThreadLanding(held) {
	if (!held) return;
	const landing = landings.get(held);
	if (!landing) return;
	if (!landing.mayLand()) {
		landings.delete(held);
		return;
	}
	landThread(held, landing.control, "instant", landing.block);
}
function scrollThreadIntoView(held, control, behavior = scrollBehavior(), block = "nearest") {
	const mayLand = retainUserIntent({ available: () => held.isConnected && control.isConnected && under(control, held) });
	landings.set(held, {
		control,
		block,
		mayLand
	});
	landThread(held, control, behavior, block);
}
function sendLanding(input) {
	const held = input.closest(SAYS_IN);
	if (!held) return () => {};
	const reply = replyRowOf(held, input);
	const read = (row) => ({
		foot: currentLocationAt(row, "bottom"),
		within: row.getBoundingClientRect().bottom - held.getBoundingClientRect().top
	});
	const stood = reply && !pinnedReply(reply) && !separateTranscript(held) && alreadyShown(reply) ? {
		row: reply,
		...read(reply)
	} : null;
	return (currentLocation = held) => {
		const mayLand = retainUserIntent({
			source: currentLocation,
			available: () => held.isConnected
		});
		whenDocumentPresented().then(() => {
			if (!mayLand() || !input.isConnected) return;
			if (stood === null || !held.contains(stood.row)) return scrollThreadIntoView(held, input, "instant");
			const reply = stood.row;
			returnTo(reply, "bottom", stood.foot + read(reply).within - stood.within);
			revealWritingArea(held, input, reply);
			if (currentLocationAt(reply, "bottom") < stood.foot) returnTo(reply, "bottom", stood.foot);
		}).catch(() => {});
	};
}
const rowHeights = /* @__PURE__ */ new WeakMap();
const transcriptPlaces = /* @__PURE__ */ new WeakMap();
const covered = (reply) => (reply.previousElementSibling?.getBoundingClientRect().bottom ?? -Infinity) - reply.getBoundingClientRect().top;
const revealWritingArea = (held, input, reply) => {
	bringBackSurfaceOf(held, "instant");
	const target = reply && fitsWhole(reply) ? reply : input;
	scrollIntoReadingBand(target, target, "nearest", "instant");
};
function revealEditor(message, caretLine) {
	const held = message.closest(SAYS_IN);
	if (!held) return;
	bringBackSurfaceOf(held, "instant");
	const target = fitsWhole(message) ? message : caretLine;
	scrollIntoReadingBand(target, target, "nearest", "instant");
	const reply = replyRowOf(held, held);
	const pinned = pinnedReply(reply);
	if (!pinned) return;
	const margin = parseFloat(getComputedStyle(message).scrollMarginBlockEnd) || 0;
	const over = target.getBoundingClientRect().bottom + margin - pinned.getBoundingClientRect().top;
	if (over > 0) moveScrollerBy(scrollerFor(pinned), over);
}
function followBoxGrowth(input) {
	const held = input.closest(SAYS_IN);
	if (!held) return;
	const reply = replyRowOf(held, input);
	if (!reply) return;
	const transcript = separateTranscript(held);
	if (transcript) {
		const place = transcriptPlaces.get(input);
		if (place?.transcript === transcript && place.atTail && transcript.clientHeight < place.height) scrollToEnd(transcript);
		transcriptPlaces.delete(input);
		if (!onScreen(reply)) revealWritingArea(held, input, reply);
		return;
	}
	if (!pinnedReply(reply)) return revealWritingArea(held, input, reply);
	const height = reply.getBoundingClientRect().height;
	const grew = height - (rowHeights.get(input) ?? height);
	rowHeights.set(input, height);
	const by = Math.max(0, Math.min(grew, covered(reply)));
	if (by) {
		const box = scrollerFor(reply);
		setScroll(box, { top: box.scrollTop + by });
	}
	if (!onScreen(reply)) revealWritingArea(held, input, reply);
}
function readBoxPlace(input) {
	const held = input.closest(SAYS_IN);
	const reply = held && replyRowOf(held, input);
	if (!reply) return;
	rowHeights.set(input, reply.getBoundingClientRect().height);
	const transcript = separateTranscript(held);
	if (transcript) transcriptPlaces.set(input, {
		transcript,
		height: transcript.clientHeight,
		atTail: atScrollEnd(transcript)
	});
}
const currentLocationAt = (node, edge) => {
	let at = node.getBoundingClientRect()[edge];
	for (const box of scrollersOf(node)) at += box.scrollTop - aimedTop(box);
	return at;
};
function returnTo(node, edge, at) {
	for (const box of scrollersOf(node)) {
		const moved = currentLocationAt(node, edge) - at;
		if (Math.abs(moved) < .5) return;
		moveScrollerBy(box, moved);
	}
}
function holdBox(control) {
	if (control == null || control !== focusedInView()) return () => {};
	const held = control.closest(SAYS_IN);
	if (!held) return () => {};
	const top = currentLocationAt(control, "top");
	return () => {
		if (focused() !== control || !control.isConnected || !held.contains(control)) return;
		returnTo(control, "top", top);
	};
}

//#endregion
//#region runtime/thread/message-edit.js
const OPEN_MESSAGE_EDIT = "lf-open-message-edit";
const open = /* @__PURE__ */ new Map();
const sending = /* @__PURE__ */ new Set();
let discarded = null;
function createRewriteRestore({ revealInThread, holdsThreadDraft }) {
	const restorable = () => {
		const candidate = discarded;
		return candidate && !open.has(candidate.id) && !draftHasContent(rewriteContext(candidate.id)) && holdsThreadDraft(rewriteContext(candidate.id)) ? candidate : null;
	};
	return {
		id: "message.edit.restore",
		keys: ["Shift+d"],
		title: "Restore discarded edit",
		touch: "Restore discarded edit",
		menu: "keys",
		when: () => Boolean(restorable()),
		run: async () => {
			const candidate = restorable();
			if (!candidate) return;
			const { id, text, over } = candidate;
			const ctx = rewriteContext(id);
			if (!restoreDraft(ctx, text, { over })) return;
			discarded = null;
			await revealInThread(ctx, retainUserIntent());
		}
	};
}
const drawn$1 = Z(0);
const messageDrawn = () => {
	drawn$1.value = drawn$1.peek() + 1;
};
function holdsMessageEdit(id, view) {
	const holder = open.get(id);
	if (!holder) return false;
	if (holder.view !== null && holder.view !== view) return false;
	holder.view = view;
	return true;
}
function releaseMessageEdit(id, view) {
	const holder = open.get(id);
	if (holder?.view === view) holder.view = null;
}
function openMessageEdit(id, view, thread) {
	for (const [other, holder] of [...open]) {
		if (other === id || holder.thread !== thread) continue;
		if (holder.view) holder.view.putEditAside();
		else if (!draftHasContent(rewriteContext(other))) open.delete(other);
	}
	const displaced = open.get(id)?.view;
	open.set(id, {
		view,
		thread
	});
	if (displaced && displaced !== view) displaced.closeEdit();
}
const keptRewrite = (id) => !open.has(id) && !sending.has(id) && draftHasContent(rewriteContext(id));
const watchRewrite = (id, changed) => watchDraft(rewriteContext(id), changed);
function openMessageEditIn(thread, id) {
	const message = [...thread?.querySelectorAll(".lf-msg") ?? []].find((node) => node.getAttribute("data-event") === id);
	message?.dispatchEvent(new CustomEvent(OPEN_MESSAGE_EDIT));
	return message?.querySelector(`:scope > .lf-msg-body > .lf-msg-editor ${TEXT_FIELD}`) ?? null;
}
function threadRewrites({ views, paint, box, home, opening = () => {}, landInThread, landSent }) {
	const lastEditable = (before = null) => {
		const drawn = views();
		const end = before === null ? drawn.length : drawn.findIndex(({ model }) => model?.id === before);
		const view = drawn.slice(0, Math.max(end, 0)).findLast((view) => {
			const model = view.model;
			return model?.author === "user" && model.body.kind !== "reaction" && Boolean(model.body.text);
		});
		return view?.model.editable ? view : null;
	};
	return {
		edit: {
			paint,
			land: (message) => {
				const shown = () => {
					const input = box();
					return input && seenRect(input, /* @__PURE__ */ new Map()) ? input : null;
				};
				const input = shown();
				if (input) return landInThread(input);
				landSent(home(message));
				const mayLand = retainUserIntent();
				whenDocumentPresented().then(() => {
					const drawn = shown();
					if (drawn && mayLand()) landInThread(drawn);
				});
			},
			previous: (id) => lastEditable(id),
			opening: (message, view) => {
				opening(message.id);
				openMessageEdit(message.id, view, message.thread);
			},
			reveal: (message, caretLine) => revealEditor(message, caretLine)
		},
		editLast: {
			available: () => {
				drawn$1.value;
				return Boolean(lastEditable());
			},
			open: () => lastEditable()?.openEdit()
		}
	};
}
function closeMessageEdit(id, { discard }) {
	open.delete(id);
	if (!discard) return;
	const ctx = rewriteContext(id);
	clearDraft(ctx);
	tellDraft(ctx, null);
	forgetWritingPlace(ctx);
}
var MessageEditor = class {
	#stop;
	#putAside;
	#reveal;
	#settling = null;
	#follow;
	constructor(id, view, { wireInput, said, base: currentBase, send, land, paint, previous, reveal }) {
		const ctx = rewriteContext(id);
		let base = currentBase();
		const kept = loadDraft(ctx);
		const payload = kept?.payload;
		const keptOver = payload && "over" in payload && typeof payload.over === "string" ? payload.over : null;
		if (keptOver && keptOver !== base && !keptOver.startsWith("pending:")) raiseError(`This message changed since this edit began. It now says: “${said()}”`);
		this.#reveal = reveal;
		this.node = offer("div", "lf-msg-editor lf-comment-box");
		this.input = offer(TEXT_FIELD);
		this.input.name = "edit";
		const actions = this.actions = offer("span", "lf-msg-edit-actions");
		const cancel = offerAction("symbol", "lf-msg-control lf-msg-edit-cancel", void 0, { action: "discard" });
		cancel.type = "button";
		actions.append(cancel);
		this.foot = document.createElement("span");
		this.foot.className = "lf-msg-edit-foot";
		this.node.append(this.input);
		this.input.value = kept?.text || said();
		const whole = () => sync.value();
		let opened = null;
		this.#follow = () => {
			if (base === currentBase() || draftHasContent(ctx) || whole() !== opened) return;
			base = currentBase();
			sync.load(opened = said());
		};
		const unchanged = () => {
			const now = whole();
			return !now.trim() || now === said();
		};
		const leave = (discard, { landing = true, says = null, painting = true } = {}) => {
			if (landing) land();
			this.#stop();
			closeMessageEdit(id, { discard });
			if (painting) paint();
			if (says) announce(says);
		};
		const close = () => {
			if (unchanged()) return leave(true, { says: "Stopped editing" });
			discarded = {
				id,
				text: whole(),
				over: base
			};
			leave(true);
			notice("Edit discarded; g D restores it");
		};
		const keep = () => {
			if (unchanged()) return close();
			const message = this.node.closest(".lf-msg");
			leave(false, { landing: false });
			const reopen = message?.querySelector(".lf-msg-edit");
			if (reopen) focusDestination(reopen, "return");
			notice("Edit kept");
		};
		const putAside = () => {
			if (!unchanged()) return;
			leave(true, {
				landing: false,
				painting: false
			});
			afterScript(paint);
		};
		this.#putAside = putAside;
		const sync = wireInput(this.input, {
			hint: "Edit message",
			accessibleName: () => `Edit message: ${said().slice(0, 60)}`,
			sends: "save",
			sendClass: "lf-msg-control lf-msg-edit-save",
			action: "save",
			submitIn: actions,
			sentMedia: true,
			save: (value) => {
				saveDraft(ctx, value, { over: base });
				tellDraft(ctx, value, { over: base });
			},
			send: async (_text, raw, owns) => {
				if (unchanged()) return leave(true, { says: "No change to save" });
				sending.add(id);
				const flight = sendDraft(ctx, owns, (attempt) => send(raw, {
					attempt,
					base
				}));
				leave(false, { painting: false });
				let sent;
				try {
					sent = await flight;
				} finally {
					sending.delete(id);
				}
				if (sent) forgetWritingPlace(ctx);
				paint();
			},
			rows: [{
				id: "message.edit.previous",
				keys: ["ArrowUp"],
				description: "When the box is unchanged and the caret is at its start",
				title: "edit previous message",
				when: () => {
					const [start, end] = caretAtKey(this.input) ?? [this.input.selectionStart, this.input.selectionEnd];
					return start === 0 && end === 0 && unchanged();
				},
				get run() {
					const before = previous();
					return before ? () => {
						putAside();
						before.openEdit();
					} : void 0;
				}
			}]
		});
		opened = whole();
		this.input.after(this.foot);
		for (const where of [this.node, actions]) keys(where, "Editing a message", [{
			id: "message.edit.close",
			keys: ["Escape"],
			title: "discard",
			run: () => close(),
			keep
		}], { escape: "inner" });
		cancel.addEventListener("mousedown", (event) => event.preventDefault());
		cancel.addEventListener("click", () => close());
		this.#stop = mirrorDraft(this.input, sync, ctx, {
			retained: true,
			blank: said
		});
	}
	enter() {
		const end = this.input.value.length;
		focusDestination(this.input, "move", { caret: [end, end] });
		this.#reveal(this.foot);
		this.#settling?.disconnect();
		const mayReveal = retainUserIntent();
		this.#settling = sizeObserver((entries, observer) => {
			if (!mayReveal() || !this.node.isConnected) return observer.disconnect();
			this.#reveal(this.foot);
		});
		this.#settling.observe(this.node);
	}
	follow() {
		this.#follow();
	}
	putAside() {
		this.#putAside();
	}
	dispose() {
		this.#settling?.disconnect();
		this.#stop();
	}
};

//#endregion
//#region runtime/thread/workflow.js
const widgetWorkflow = (workflow) => workflow.subject.kind === "widget";
const todoAttention = (thread) => thread.attention?.kind === "waiting" && thread.attention.reason === "todo";
const hasWorkflowLine = (workflow) => workflow.detail !== null;
const queuedFor = (agent) => leafSays(`Queued for ${agent}`);
const STAGES = Object.freeze({
	sending: queuedFor,
	sent: queuedFor,
	queued: () => leafSays("Up next"),
	picked_up: () => leafSays("Delivered"),
	working: () => agentSays("On it"),
	replying: () => agentSays("Replying"),
	answered: () => agentSays("Answered")
});
const CONDITION_WORDS = Object.freeze({
	ended: "Stopped",
	interrupted: "Interrupted",
	stale: "Gone quiet",
	failed: "Failed"
});
const NOT_ANSWERED = leafSays("Not answered");
const RESOLVED = leafSays("Resolved");
const workflowWord = (workflow, agent, { answered = false } = {}) => {
	if (!workflow) return null;
	const { condition } = workflow;
	if (condition) return condition.kind === "stale" && condition.operation === "delivery" ? leafSays(`Still queued for ${agent}`) : condition.kind === "failed" && condition.operation === "response" ? NOT_ANSWERED : leafSays(CONDITION_WORDS[condition.kind] ?? "Failed");
	if (workflow.stage === "answered" && !answered) return null;
	return STAGES[workflow.stage]?.(agent) ?? null;
};
const workflowTitle = (workflow, agent) => [workflowWord(workflow, agent, { answered: true })?.text, workflow?.detail].filter(Boolean).join(" · ");
const progressFace = (workflow) => !workflow || workflow.condition ? null : workflow.stage === "picked_up" ? "picked_up" : ["working", "replying"].includes(workflow.stage) ? "working" : null;
const isWorkflowProgress = (workflow) => progressFace(workflow) !== null;
const workflowStep = (workflow, agent) => progressFace(workflow) === "working" && workflow?.detail ? agentSays(workflow.detail) : workflowWord(workflow, agent);
const isPageWidgetWorkflow = (workflow, revision) => widgetWorkflow(workflow) && workflow.thread === null && workflow.revision <= Number(revision);
const handedBack = (workflow) => workflow.stage === "answered" || workflow.stage === "sending" && workflow.condition?.kind === "failed";
const tier = (workflow) => (handedBack(workflow) ? 0 : 2) + Number(workflow.stage === "sending");
function strongestWorkflow(workflows) {
	let strongest = null;
	for (const candidate of workflows) if (strongest === null || tier(candidate) < tier(strongest)) strongest = candidate;
	return strongest;
}
const todoWord = (running) => agentSays(running ? "On it" : "Still to do");
function threadAttention(thread, agent) {
	if (thread.resolved) return null;
	const attention = thread.attention;
	const workflow = attention?.workflow ? thread.workflows.find((candidate) => candidate.id === attention.workflow) ?? null : null;
	if (thread.attention?.kind === "needs_user") return Object.freeze({
		kind: "needs_user",
		word: thread.attention.reason === "obligation" ? agentSays("Your turn") : leafSays(workflow?.subject.kind === "thread" ? "Send it again" : "Try it again"),
		workflow
	});
	if (todoAttention(thread)) return Object.freeze({
		kind: "waiting",
		word: todoWord(thread.todos[0].running),
		workflow: null
	});
	if (thread.attention?.kind === "waiting") return Object.freeze({
		kind: "waiting",
		word: workflowWord(workflow, agent) ?? leafSays(thread.attention.reason === "uncertain" ? "Uncertain" : "Waiting"),
		workflow
	});
	return null;
}

//#endregion
//#region runtime/design-readings.js
const DESIGN_MODE_KEY = "lf-design-mode";
function designName(element) {
	const tag = element.tagName.toLowerCase();
	return `${tag.startsWith("lf-") ? tag : addressableWord(element)} · ${element.id}`;
}

//#endregion
//#region runtime/held-word.js
const HOLDS_WORD = "lf-holds-word";
const HOLDER = `.${HOLDS_WORD}`;
function holdToRead() {
	let hold = null;
	const holderIn = (event) => {
		for (const node of event.composedPath()) if (isElement(node) && node.matches(HOLDER)) return node;
		return null;
	};
	const read = (held, holder) => {
		if (held.reading === holder) return;
		held.reading?.removeAttribute("data-lf-held-word");
		held.reading = holder;
		holder?.setAttribute("data-lf-held-word", "");
	};
	const under = (held, event) => {
		const holder = holderIn(event);
		return holder?.parentElement === held.parent ? holder : null;
	};
	const end = (event, commit) => {
		if (!hold || hold.pointerId !== event.pointerId) return;
		const holder = commit && plainPress(event) ? under(hold, event) : null;
		read(hold, null);
		hold = null;
		if (!holder) return;
		claimReleaseClick();
		nativeFocusTarget(holder).focus({
			preventScroll: true,
			focusVisible: false
		});
		holder.dispatchEvent(new MouseEvent("click", {
			bubbles: true,
			cancelable: true,
			composed: true,
			detail: 1,
			clientX: event.clientX,
			clientY: event.clientY
		}));
	};
	document.addEventListener("pointerdown", (event) => {
		if (hold) read(hold, null);
		hold = null;
		if (!event.isPrimary || !plainPress(event)) return;
		const holder = holderIn(event);
		if (!holder || holder.matches(":disabled, [aria-disabled='true']")) return;
		const origin = event.composedPath()[0];
		if (isElement(origin) && origin.hasPointerCapture(event.pointerId)) origin.releasePointerCapture(event.pointerId);
		hold = {
			pointerId: event.pointerId,
			parent: holder.parentElement,
			reading: null
		};
		read(hold, holder);
	}, { capture: true });
	document.addEventListener("pointermove", (event) => {
		if (hold?.pointerId === event.pointerId) read(hold, under(hold, event));
	}, { capture: true });
	document.addEventListener("pointerup", (event) => end(event, true), { capture: true });
	document.addEventListener("pointercancel", (event) => end(event, false), { capture: true });
	document.addEventListener("contextmenu", (event) => {
		if (hold) event.preventDefault();
	}, { capture: true });
}

//#endregion
//#region runtime/thread/reaction-strips.js
let ordinal = 0;
var ReactionStripView = class {
	#commands;
	#registration = null;
	#palette;
	#paletteId = `lf-reactions-${++ordinal}`;
	constructor(commands) {
		this.#commands = commands;
		this.node = document.createElement("div");
		this.node.classList.add("lf-react-strip", "lf-react-surface");
		this.#palette = document.createElement("span");
		this.#palette.className = "lf-react-palette";
		this.#palette.id = this.#paletteId;
		this.#palette.popover = "auto";
		this.#palette.setAttribute("role", "group");
		this.#palette.setAttribute("aria-label", "Reactions for this reply");
		this.node.append(this.#palette);
	}
	present(model) {
		this.node.classList.toggle("lf-open", model.latest);
		render$1(html`
        ${repeat(model.choices, (choice) => choice.name, (choice) => html` <button
              ${offered(`lf-react ${HOLDS_WORD}`)}
              data-token=${choice.name}
              title=${choice.label}
              aria-label=${choice.label}
              aria-pressed=${String(Boolean(choice.inForce))}
              @click=${() => this.#press(model, choice)}
            >
              <span class="lf-react-glyph">${choice.glyph}</span>
            </button>`)}
      `, this.#palette);
		return this.node;
	}
	trigger = html`<button
    ${offeredAction("symbol", "lf-msg-control lf-react-trigger", void 0, { action: "react" })}
    aria-expanded="false"
    aria-controls=${this.#paletteId}
    ${ref((trigger) => {
		if (!isHTML(trigger, "button")) return;
		const registration = this.#commands.registerSurface(this.node, {
			trigger,
			palette: this.#palette
		});
		this.#registration = registration;
		trigger.addEventListener("click", () => registration.toggle());
		this.#palette.ontoggle = (event) => {
			if (event.newState === "closed") registration.close();
		};
		this.node.onclick = (event) => {
			if (!event.composedPath().some((node) => node instanceof HTMLButtonElement && node.matches(".lf-react[data-token]"))) return;
			registration.close();
			this.#commands.pressed?.();
		};
	})}
  ></button>`;
	#press(model, choice) {
		this.#commands.actions.setReaction(model.thread, model.message, choice.name, !choice.inForce);
	}
	retire() {
		this.#registration?.close();
	}
};

//#endregion
//#region runtime/thread/messages.js
const loadMessageMarkdown = () => loadMarkdown((error) => reportPageError(error, `markdown renderer failed to load`));
const renderedProse = /* @__PURE__ */ new Map();
function proseReading(message) {
	const key = message.attempt ?? message.id;
	const edited = message.edited?.id ?? null;
	const text = message.text ?? "";
	const markdown = markdownReady();
	let reading = renderedProse.get(key);
	if (!reading || reading.id !== message.id || reading.edited !== edited || reading.text !== text || reading.markdown !== markdown) {
		const pasted = readAttachedMedia(text);
		const html = renderMarkdown(pasted.text);
		const mediaHtml = renderMarkdown(writeAttachedMedia("", pasted.paths));
		reading = Object.freeze({
			id: message.id,
			edited,
			text,
			markdown,
			html,
			mediaHtml,
			plainText: renderedWords(html + mediaHtml)
		});
		renderedProse.set(key, reading);
	}
	return reading;
}
function messageText(message) {
	if (message.body?.kind === "authored") return message.body.text;
	if (message.token) return `${tokenEntry(message.token)?.glyph ?? ""} ${message.token}`.trim();
	return message.suggestion ? message.text ?? "" : proseReading(message).plainText;
}
function threadName(thread) {
	if (thread.title != null) return thread.title;
	const { root } = thread;
	return labelWords(messageText(root)) || (root.drawing ? "Drawing" : "");
}
const titlePending = (thread) => thread.title == null && thread.attention?.kind === "waiting" && thread.attention.reason === "workflow" && pageClaimed();
const threadHeading = (thread) => titlePending(thread) ? html`<span class="lf-thread-name-pending">Generating thread name…</span
        ><span class="lf-quiet"> ${threadName(thread)}</span>` : threadName(thread);
const threadSummary = (thread) => ({
	topic: threadName(thread),
	latest: lastMovedAt(thread)
});
const authoredMessages = /* @__PURE__ */ new Map();
function prepareAuthoredMessage(message, thread) {
	const key = message.attempt ?? message.id;
	if (typeof thread !== "string" || !thread) throw new TypeError("an authored message needs its thread's id");
	let prepared = authoredMessages.get(key);
	if (!prepared) {
		const template = document.createElement("template");
		template.innerHTML = message.markup ?? "";
		markDeclared(template.content);
		rememberAuthoredParents(template.content);
		const descriptors = stageWidgetDescriptors(template.content, {
			kind: "thread",
			thread,
			message: message.id
		});
		const authored = stageAuthoredStates(template.content, /* @__PURE__ */ new Map());
		rememberPassageParts(template.content, ["event", message.id]);
		const text = template.content.textContent;
		const nodes = Object.freeze([...template.content.childNodes]);
		prepared = {
			message: message.id,
			body: {
				text,
				markup: message.markup ?? "",
				document: {
					thread,
					message: message.id
				}
			},
			authored,
			descriptors,
			nodes,
			root: template.content,
			preparation: null
		};
		authoredMessages.set(key, prepared);
	}
	for (const descriptor of prepared.descriptors.descriptors.values()) if (descriptor.document.kind !== "thread" || descriptor.document.thread !== thread || descriptor.document.message !== message.id) throw new TypeError("an authored message changed its frozen document identity");
	const captured = prepared;
	return captured.preparation ??= importWidgets(captured.root).then(() => captured, (error) => {
		captured.preparation = null;
		throw error;
	});
}
const authoredMessage = (message) => {
	const prepared = authoredMessages.get(message.attempt ?? message.id);
	if (!prepared) throw new Error("authored message presentation preceded semantic preparation");
	return prepared;
};
const authoredDrawings = /* @__PURE__ */ new Map();
const authoredHolders = /* @__PURE__ */ new Map();
const shown = (view) => view.node.isConnected && showsContents(view.node);
const hidden = (view) => view.node.isConnected && !showsContents(view.node);
const outranks = (a, b) => a.model.authoredRank > b.model.authoredRank;
function settleAuthored(key) {
	const drawings = authoredDrawings.get(key) ?? /* @__PURE__ */ new Set();
	const holder = authoredHolders.get(key);
	const held = holder && drawings.has(holder) && !hidden(holder) ? holder : null;
	let best = null;
	for (const view of drawings) if (shown(view) && (!best || outranks(view, best))) best = view;
	if (!best || best === holder || held && !outranks(best, held)) return;
	authoredHolders.set(key, best);
	best.present(best.model);
	if (holder && drawings.has(holder)) holder.present(holder.model);
}
const unsettled = /* @__PURE__ */ new Set();
function settleAuthoredSoon(key) {
	if (unsettled.has(key)) return;
	unsettled.add(key);
	queueMicrotask(() => {
		unsettled.delete(key);
		settleAuthored(key);
	});
}
function releaseAuthored(key, view) {
	if (authoredHolders.get(key) !== view) return;
	authoredHolders.delete(key);
	settleAuthored(key);
}
function releaseAuthoredUnder(root) {
	for (const [key, view] of [...authoredHolders]) if (root.contains(view.node)) releaseAuthored(key, view);
}
function authoredHolder(id) {
	for (const view of authoredHolders.values()) if (view.model.id === id && shown(view)) return view.node;
	return null;
}
function messageReading(message, { authoredRank = 0, reactions, workflows, leaves = null }) {
	const workflow = strongestWorkflow(workflows);
	const token = message.token ? tokenEntry(message.token) : null;
	const kind = isReaction(message) ? "reaction" : message.suggestion ? "suggestion" : "prose";
	const prose = kind === "prose" ? proseReading(message) : null;
	return Object.freeze({
		key: messageKey(message),
		id: message.id,
		thread: message.thread,
		provisional: Boolean(message.provisional),
		progress: Boolean(message.ephemeral),
		leaves,
		version: message.content_version,
		sequence: message.seq ?? Infinity,
		unread: message.unread,
		attempt: message.attempt ?? null,
		author: message.author,
		by: message.author === "agent" ? message.agent : "Me",
		timestamp: message.ts,
		age: ago(message.ts),
		edited: message.edited ? `Edited ${ago(message.edited.ts)}. Before, it said: “${message.edited.was}”` : null,
		editable: editable(message),
		failure: message.failure ?? null,
		pending: workflow?.stage === "sending",
		base: message.content_version,
		workflow,
		workflowWord: workflowWord(workflow, agentName()),
		workflowTitle: workflowTitle(workflow, agentName()),
		body: Object.freeze({
			kind,
			text: message.text ?? "",
			html: prose?.html ?? "",
			mediaHtml: prose?.mediaHtml ?? "",
			plainText: prose?.plainText ?? message.text ?? "",
			drawing: Boolean(message.drawing),
			token: message.token ?? null,
			glyph: token?.glyph ?? "",
			authored: message.body.kind === "authored"
		}),
		markdown: kind === "reaction" ? null : [message.text, message.body.kind === "authored" ? message.body.markup : null].filter(Boolean).join("\n\n"),
		authoredRank,
		reactions
	});
}
var MessageView = class {
	#commands;
	#presentation = null;
	get #model() {
		return this.#presentation?.model ?? null;
	}
	#reaction = null;
	#copy = null;
	#authoredTake = 0;
	#dressed = false;
	#arrivalMotion = null;
	#stopRead = null;
	#editor = null;
	#kept = false;
	#stopKept = null;
	#dated = true;
	constructor(commands) {
		this.#commands = commands;
		this.node = document.createElement("div");
	}
	present(model, { arrived = false, dated = this.#dated, headerControls = nothing } = {}) {
		const prior = this.#model;
		const presentation = this.#presentation ??= {
			node: this.node,
			model,
			present: (reading) => this.present(reading)
		};
		presentation.model = model;
		this.#dated = dated;
		if (!prior) {
			this.node.classList.add("lf-msg");
			this.node.dataset.message = model.key;
			this.node.classList.add("lf-ui");
			generatedElement(this.node, { says: false });
			this.node.dataset.lfOffer = "";
			this.node.addEventListener("dblclick", (event) => {
				if (event.target instanceof Element && event.target.closest(".lf-msg-editor, .lf-msg-controls, a[href]")) return;
				if (!this.#model?.editable) return;
				window.getSelection()?.removeAllRanges();
				this.openEdit();
			});
			this.node.addEventListener(OPEN_MESSAGE_EDIT, () => this.openEdit());
		}
		const editor = model.editable && holdsMessageEdit(model.id, this) ? this.#editor ??= new MessageEditor(model.id, this, {
			wireInput: this.#commands.reply.wireInput,
			said: () => presentation.model.body.text,
			base: () => presentation.model.base,
			send: (text, options) => this.#commands.reply.actions.edit(presentation.model.thread, presentation.model.id, text, options),
			land: () => this.#commands.edit.land(this.node),
			paint: () => this.#commands.edit.paint(this.node),
			previous: () => this.#commands.edit.previous(presentation.model.id),
			reveal: (caretLine) => this.#commands.edit.reveal(this.node, caretLine)
		}) : null;
		if (!editor && this.#editor) {
			this.#editor.dispose();
			this.#editor = null;
		}
		editor?.follow();
		this.#kept = model.editable && !editor && keptRewrite(model.id);
		if (model.editable && !this.#stopKept) this.#stopKept = watchRewrite(model.id, () => {
			if (keptRewrite(presentation.model.id) !== this.#kept) this.#commands.edit.paint(this.node);
		});
		if (prior && prior.author !== model.author) this.node.classList.toggle(prior.author, false);
		this.node.classList.toggle(model.author, true);
		keeps(this.node, "data-event", model.id);
		this.node.classList.toggle("lf-unread", Boolean(model.unread));
		keeps(this.node, "data-attempt", model.attempt || null);
		keeps(this.node, "aria-busy", model.pending ? "true" : null);
		keeps(this.node, "data-failure", model.failure || null);
		const authoredKey = model.attempt ?? model.id;
		const authored = model.body.authored ? authoredMessage(model).nodes : [];
		let displaced = null;
		if (model.authoredRank && model.body.authored) {
			let drawings = authoredDrawings.get(authoredKey);
			if (!drawings) authoredDrawings.set(authoredKey, drawings = /* @__PURE__ */ new Set());
			drawings.add(presentation);
			const holder = authoredHolders.get(authoredKey);
			const holding = holder && drawings.has(holder);
			if (holder !== presentation && (holding ? shown(presentation) && (hidden(holder) || outranks(presentation, holder)) : !hidden(presentation))) {
				authoredHolders.set(authoredKey, presentation);
				if (holding) displaced = holder;
			}
			settleAuthoredSoon(authoredKey);
		}
		const holds = authoredHolders.get(authoredKey) === presentation;
		if (holds && authored.some((node) => !this.node.contains(node))) this.#authoredTake++;
		if (!model.reactions) this.#reaction?.retire();
		const strip = model.reactions ? (this.#reaction ??= new ReactionStripView(this.#commands.reaction)).present(model.reactions) : nothing;
		const rewrite = editor ? editor.actions : model.editable ? html`<button
            ${offeredAction("symbol", "lf-msg-control lf-msg-edit", "Edit message", { action: "edit" })}
            tabindex="-1"
            @click=${() => this.openEdit()}
          ></button>` : nothing;
		const react = this.#reaction && model.reactions ? this.#reaction.trigger : nothing;
		const copy = model.markdown && !editor ? this.#copyControl(model.markdown) : nothing;
		const receipt = model.workflowWord ? html`<span class="lf-msg-sending" title=${model.workflowTitle}
          >${voiced(model.workflowWord)}</span
        >` : nothing;
		const header = html`
      <div class="lf-msg-head" data-lf-reflow="text">
        <b>${model.by}</b
        ><span class="lf-msg-meta"
          >${dated ? html`<time datetime=${model.timestamp}>${model.age}</time>` : nothing}${model.unread ? html`<span class="lf-msg-new lf-unread-dot"
                  ><span class="lf-quiet">New</span></span
                >` : nothing}
          ${receipt}
          ${model.leaves ? html`<span class="lf-msg-leaves">${voiced(model.leaves)}</span>` : nothing}
          ${model.failure ? html`<span class="lf-msg-failure">${voiced(NOT_ANSWERED)}</span>` : nothing}
          ${model.body.kind === "suggestion" ? html`<span class="lf-suggest-label">Suggestion</span>` : nothing}
          ${model.edited ? html`<span class="lf-edited" title=${model.edited}>edited</span>` : nothing}
          ${this.#kept ? html`<span
                  class="lf-msg-kept"
                  title="The edit is kept; open it to save or discard"
                  >unsaved edit</span
                >` : nothing}
        </span>
        ${headerControls}<span class="lf-msg-control-room"
          ><span class="lf-msg-controls">${rewrite}${react}${copy}</span></span
        >
      </div>
    `;
		render$1(html`
        ${header}
        <div
          class=${`lf-msg-body${model.body.kind === "suggestion" ? " lf-suggest-body" : ""}`}
          ${ref((body) => {
			if (body) this.#stopRead = this.#commands.read.observeMessage(body, model);
		})}
        >
          ${editor ? editor.node : this.#body(model.body)}
          ${model.body.drawing ? html`<span class="lf-drawing-reference">Drawing comment</span>` : nothing}
          ${holds ? keyed(this.#authoredTake, authored) : nothing}
        </div>
        ${strip}
      `, this.node);
		if (model.body.authored && !this.#dressed) {
			markDeclared(this.node);
			renderSaid(this.node);
			renderQuiet(this.node);
			this.#dressed = true;
		}
		highlightBlocks(this.node);
		displaced?.present(displaced.model);
		if (!prior && (model.pending || arrived)) this.#arrivalMotion = motion(this.node, [{
			"--lf-msg-arrival": 1,
			offset: 0
		}], flashDuration());
		messageDrawn();
		return this.node;
	}
	openEdit() {
		const model = this.#model;
		if (!model?.editable) return false;
		if (!this.#editor) {
			this.#commands.edit.opening(model, this);
			this.#commands.edit.paint(this.node);
		}
		this.#editor?.enter();
		return true;
	}
	closeEdit() {
		this.#commands.edit.paint(this.node);
	}
	putEditAside() {
		this.#editor?.putAside();
	}
	get model() {
		return this.#model;
	}
	get editing() {
		return this.#editor !== null;
	}
	#copyControl(markdown) {
		if (!this.#copy) {
			this.#copy = copyControl("lf-msg-control lf-msg-copy", {
				role: "symbol",
				label: "Copy as Markdown",
				success: "Message copied as Markdown",
				error: "Message not copied · select its words to copy"
			});
			this.#copy.tabIndex = -1;
			this.#copy.title = "Copy as Markdown";
		}
		if (this.#copy.value !== markdown) this.#copy.value = markdown;
		return this.#copy;
	}
	#body(body) {
		if (body.kind === "reaction") return html`<div class="lf-msg-text">
        <span class="lf-react-said">${`${body.glyph} ${body.token}`.trim()}</span>
      </div>`;
		if (body.kind === "suggestion") return html`<div class="lf-msg-text" .textContent=${body.text}></div>`;
		return html`<div class="lf-msg-text" .innerHTML=${body.html}></div>
      ${body.mediaHtml ? html`<div class="lf-msg-media" .innerHTML=${body.mediaHtml}></div>` : nothing}`;
	}
	commit() {
		if (!this.#model?.reactions && this.#reaction) {
			this.#reaction.retire();
			this.#reaction = null;
		}
	}
	retire() {
		const presentation = this.#presentation;
		if (presentation) {
			const key = presentation.model.attempt ?? presentation.model.id;
			authoredDrawings.get(key)?.delete(presentation);
			if (!authoredDrawings.get(key)?.size) authoredDrawings.delete(key);
			releaseAuthored(key, presentation);
		}
		this.#arrivalMotion?.cancel();
		this.#reaction?.retire();
		if (this.#model) releaseMessageEdit(this.#model.id, this);
		this.#editor?.dispose();
		this.#editor = null;
		this.#stopKept?.();
		this.#stopKept = null;
		this.#stopRead?.();
	}
};
function messageHolding(id) {
	for (const { nodes, body } of authoredMessages.values()) for (const node of nodes) {
		if (!(node instanceof Element)) continue;
		const element = node;
		const kept = element.id === id ? element : element.querySelector(`[id="${CSS.escape(id)}"]`);
		if (kept) return {
			element: kept,
			...body.document
		};
	}
	return null;
}
const addressableAt = (id) => elementById(id) ?? messageHolding(id)?.element ?? null;
function coordinateLabel(anchor, about) {
	if (about === "design") {
		const addressable = anchor?.section ? addressableAt(anchor.section) : null;
		const name = addressable ? designName(addressable) : anchor?.section || "the page";
		return anchor?.quote ? `${name} · “${anchor.quote}”` : name;
	}
	const datum = datumLabel(anchor);
	if (datum) return anchor?.quote ? `${datum} · “${anchor.quote}”` : `§ ${datum}`;
	if (anchor?.quote) return `“${anchor.quote}”`;
	if (!anchor?.section) return "";
	const addressable = addressableAt(anchor.section);
	if (anchor.visual) {
		const part = visualPartLabel(addressable, anchor.visual) ?? anchor.visual;
		return `§ ${addressable ? `${addressableWord(addressable)} · ${part}` : `${anchor.section} · ${part}`}`;
	}
	return `§ ${addressable ? sectionLabel(addressable) : anchor.section}`;
}
const threadPassage = (thread) => thread.rewritten_from ?? thread.detached_from ?? thread.anchor;
function anchorLabel(anchor, about) {
	const label = coordinateLabel(anchor, about);
	return [
		about === "design" && "design",
		anchor?.part,
		label
	].filter(Boolean).join(" · ");
}

//#endregion
//#region runtime/projection/presentation.js
function paintStateOrigins(projection) {
	const userOverride = /* @__PURE__ */ new Set();
	const reported = /* @__PURE__ */ new Set();
	const marks = /* @__PURE__ */ new Map([[PAGE_PAINT_ATTRIBUTE.userOverride, userOverride], [PAGE_PAINT_ATTRIBUTE.reported, reported]]);
	for (const { origin, unit } of projectionOrigins(authoredStates(), projection)) {
		if (origin === "restated") continue;
		const target = elementById(unit);
		if (!target || inChrome(target)) continue;
		(origin === "user" ? userOverride : reported).add(target);
	}
	const touched = /* @__PURE__ */ new Set();
	for (const [attr, wanted] of marks) {
		for (const target of pageQueryAll(`[${attr}]`)) {
			touched.add(target);
			if (!wanted.has(target)) target.removeAttribute(attr);
		}
		for (const target of wanted) {
			touched.add(target);
			keeps(target, attr, "1");
		}
	}
	return touched;
}
function paintSettlements(widgets) {
	for (const [widgetId, { state }] of widgets) {
		const owner = widgetElement(widgetId);
		const decision = owner && decisionFor(owner.localName);
		if (!decision) continue;
		const wanted = state[decision.verb]?.detail?.outcome;
		const outcome = Object.keys(decision.retires).find((candidate) => candidate === wanted) ?? null;
		keeps(owner, PAGE_PAINT_ATTRIBUTE.settlement, outcome);
		renderRetired(owner, outcome);
	}
}
const answered = readPart((root) => root.authoritative !== null);
const phase = readPart((root) => root.phase);
const currentProjection = readPart((root) => root.effective.projection);
const widgetStates = readPart((root) => root.effective.widgets);
function createProjectionPresentation() {
	applicationPresenter({
		region: "projection:chrome",
		after: PRESENTATION_DOM.widgets,
		reading: () => answered() ? true : null,
		paint: paintReading
	});
	const coverage = () => {
		const root = applicationState.read();
		if (root.phase === "waiting" || root.authoritative === null || !projectionRegionsPresented([])) return;
		const projection = root.effective.projection;
		const records = root.effective.view?.coverage ?? [];
		if (records.every((record) => {
			if (record.coordinate === null) return true;
			const e = record.event;
			const target = projection.classified.get(e.kind === "undo" ? e.undoes : e.id);
			return !target || target.terminal || projectionRegionsPresented(record.coordinate.slice(0, 1));
		})) keeps(document.body, PAGE_PAINT_ATTRIBUTE.applied, String(records.length));
	};
	let coverageQueued = false;
	const updateCoverage = () => {
		if (coverageQueued) return;
		coverageQueued = true;
		queueMicrotask(() => {
			coverageQueued = false;
			coverage();
		});
	};
	watchPresentation(updateCoverage);
	function presentCurrent() {
		const projection = currentProjection();
		if (phase() === "waiting" || !answered()) return projection;
		for (const entry of projection.classified.values()) for (const id of entry.restated ?? []) keeps(elementById(id), PAGE_PAINT_ATTRIBUTE.restated, "1");
		paintSettlements(widgetStates());
		const originTargets = paintStateOrigins(projection);
		renderQuiet(document.body, originTargets);
		return projection;
	}
	function paintReading() {
		return presentCurrent();
	}
}
function shallowSigs(root) {
	const sigs = /* @__PURE__ */ new Map();
	const siblingPositions = /* @__PURE__ */ new Map();
	const isAuthored = (node) => Boolean(node.id) && authored(node)(node);
	for (const node of [root, ...root.querySelectorAll("[id]")]) {
		if (!isAuthored(node)) continue;
		const attrs = Object.fromEntries([...node.attributes].filter((attribute) => !isPagePaint(attribute.name)).map((attribute) => ({
			name: attribute.name,
			value: attribute.value
		})).sort((left, right) => left.name.localeCompare(right.name)).map(({ name, value }) => [name, value]));
		const parent = node.parentElement;
		let positions = siblingPositions.get(parent);
		if (!positions) {
			positions = /* @__PURE__ */ new Map();
			for (const sibling of parent?.children ?? []) if (isAuthored(sibling)) positions.set(sibling, positions.size);
			siblingPositions.set(parent, positions);
		}
		sigs.set(node.id, JSON.stringify({
			tag: node.tagName,
			attrs,
			parent: parent && isAuthored(parent) ? parent.id : "",
			index: positions.get(node) ?? -1
		}));
	}
	return sigs;
}

//#endregion
//#region runtime/composing/capture.js
const selectionAnchor = (sel) => anchorForRange(pageRange(sel));
const drawn = (sel) => sel !== null && sel.rangeCount > 0 && !pageRange(sel).collapsed;
const pageSelection = () => {
	const sel = getSelection();
	return drawn(sel) && pageWords(sel.anchorNode) ? sel : null;
};
function createPassageSelection({ restore }) {
	let previous = null;
	return {
		remember(selection = pageSelection()) {
			if (!anchoringIsReady() || !selection || takesLetters(focused())) return;
			const anchor = selectionAnchor(selection);
			if (anchor?.quote) previous = {
				anchor,
				backward: selectionBackward(selection)
			};
		},
		command: {
			id: "selection.restore",
			keys: ["v"],
			title: "Restore selection",
			touch: "Restore selection",
			menu: "keys",
			when: () => previous !== null,
			get run() {
				const saved = previous;
				return saved ? async () => {
					const intent = retainUserIntent();
					if (!await restore(saved.anchor, {
						backward: saved.backward,
						intent
					}) && intent()) raiseError("That selected passage is unavailable on this version");
				} : void 0;
			}
		}
	};
}
const leftThePage = (sel = getSelection()) => drawn(sel) && !pageWords(sel.focusNode);
const sameRun = (left, right) => left !== null && right !== null && segmentBlock(left.segment) === segmentBlock(right.segment) && left.segment.gen === right.segment.gen;
const sentenceUnits = new Intl.Segmenter(void 0, { granularity: "sentence" });
const edgeAt = (reading, i) => i >= 0 && i < reading.raw.length && pointAt$1(reading, i) === null;
function rawOffset(positions, at) {
	const offset = positions[at];
	if (offset === void 0) throw new Error("A snapped passage boundary left its source reading");
	return offset;
}
function snapOut(reading, at, back) {
	const { raw, fences } = reading;
	const behind = fences.filter((f) => f <= at).at(-1) ?? 0;
	const ahead = fences.find((f) => f >= at) ?? raw.length;
	const joined = (i) => {
		if (!edgeAt(reading, i)) return true;
		let a = i - 1;
		while (edgeAt(reading, a)) a--;
		let b = i + 1;
		while (edgeAt(reading, b)) b++;
		return sameRun(pointAt$1(reading, a), pointAt$1(reading, b));
	};
	const inRun = (i) => !/\s/.test(raw.charAt(i)) && joined(i);
	let lo = at;
	while (lo > behind && inRun(lo - 1)) lo--;
	let hi = at;
	while (hi < ahead && inRun(hi)) hi++;
	let run = "";
	let boundary = 0;
	const from = [];
	for (let i = lo; i < hi; i++) {
		if (edgeAt(reading, i)) continue;
		if (i < at) boundary++;
		from.push(i);
		run += raw[i];
	}
	const word = textUnits.segment(run).containing(boundary);
	if (!word || word.index >= boundary || !word.isWordLike) return at;
	return back ? rawOffset(from, word.index) : rawOffset(from, word.index + word.segment.length - 1) + 1;
}
function snapSentence(reading, lo, hi) {
	const { raw, fences } = reading;
	const point = (i) => pointAt$1(reading, i);
	const first = point(lo);
	const last = point(hi - 1);
	if (!first || !last) return [lo, hi];
	if (closestAcross(first.node, "pre,code")) return [lo, hi];
	const belongs = (part) => sameRun(first, part);
	if (!belongs(last) || fences.some((f) => f > lo && f < hi)) return [lo, hi];
	for (let at = lo; at < hi; at++) {
		const part = point(at);
		if (part && !belongs(part)) return [lo, hi];
	}
	const behind = fences.filter((f) => f <= lo).at(-1) ?? 0;
	const ahead = fences.find((f) => f >= hi) ?? raw.length;
	const inScope = (at) => {
		const part = point(at);
		if (part) return belongs(part);
		let before = at - 1;
		while (before >= behind && edgeAt(reading, before)) before--;
		let after = at + 1;
		while (after < ahead && edgeAt(reading, after)) after++;
		return belongs(point(before)) && belongs(point(after));
	};
	let start = lo;
	while (start > behind && inScope(start - 1)) start--;
	let stop = hi;
	while (stop < ahead && inScope(stop)) stop++;
	let text = "";
	let selectedStart = 0;
	let selectedStop = 0;
	const from = [];
	let inWhitespace = false;
	for (let at = start; at < stop; at++) {
		if (edgeAt(reading, at)) continue;
		const character = raw.charAt(at).replace(COLLAPSE$1, " ");
		const whitespace = character === " ";
		if (whitespace && inWhitespace) continue;
		inWhitespace = whitespace;
		if (at < lo) selectedStart++;
		if (at < hi) selectedStop++;
		from.push(at);
		text += character;
	}
	const sentences = [...sentenceUnits.segment(text)];
	const atStart = sentences.find((sentence) => sentence.index <= selectedStart && selectedStart < sentence.index + sentence.segment.length);
	const atStop = sentences.find((sentence) => sentence.index < selectedStop && selectedStop <= sentence.index + sentence.segment.length);
	const edges = (sentence) => {
		if (!sentence) return null;
		const [first, ...rest] = [...textUnits.segment(sentence.segment)].filter((part) => part.isWordLike);
		if (!first) return null;
		const last = rest.reduce((_, word) => word, first);
		const firstWord = first.index;
		const lastWord = last.index + last.segment.length;
		const leading = sentence.segment.slice(0, firstWord).match(/\p{P}+$/u)?.[0] ?? "";
		const trailing = sentence.segment.slice(lastWord).match(/^\p{P}+/u)?.[0] ?? "";
		return {
			contentStart: sentence.index + firstWord - leading.length,
			contentStop: sentence.index + lastWord + trailing.length,
			firstWord: sentence.index + firstWord,
			lastWord: sentence.index + lastWord
		};
	};
	let snappedStart = selectedStart;
	const startEdges = edges(atStart);
	if (startEdges && selectedStart >= startEdges.contentStart && selectedStart <= startEdges.firstWord) snappedStart = startEdges.contentStart;
	let snappedStop = selectedStop;
	const stopEdges = edges(atStop);
	if (stopEdges && selectedStop >= stopEdges.lastWord && selectedStop <= stopEdges.contentStop) snappedStop = stopEdges.contentStop;
	return [snappedStart === selectedStart ? lo : rawOffset(from, snappedStart), snappedStop === selectedStop ? hi : rawOffset(from, snappedStop - 1) + 1];
}
function snapSelection() {
	if (!anchoringIsReady()) return;
	const sel = pageSelection();
	if (!sel) return;
	const range = pageRange(sel);
	const segments = segmentsIn(range);
	if (!segments.length) return;
	const reading = pageText();
	const [start, stop] = spanIn(reading, segments);
	let lo = snapOut(reading, start, true);
	let hi = snapOut(reading, stop, false);
	[lo, hi] = snapSentence(reading, lo, hi);
	if (lo === start && hi === stop) return;
	const boundary = (offset, end) => {
		const point = pointAt$1(reading, offset);
		if (!point) throw new Error("A snapped passage boundary no longer names page text");
		return [point.node, point.offset + Number(end)];
	};
	const head = lo === start ? [range.startContainer, range.startOffset] : boundary(lo, false);
	const tail = hi === stop ? [range.endContainer, range.endOffset] : boundary(hi - 1, true);
	if (selectionBackward(sel, range)) selectEnds(tail, head);
	else selectEnds(head, tail);
}

//#endregion
//#region runtime/walk-position.js
const HOLD_MS = 900;
let walking = null;
function walkPositionLabel(noun, position, total, qualifier = "") {
	if (!noun && !qualifier) throw new Error("leaf: a walk position needs a noun");
	return [
		noun,
		`${position} of ${total}`,
		qualifier
	].filter(Boolean).join(" ");
}
function listWalkPosition(items, current, { identity = (item) => item, qualifier = "" } = {}) {
	if (!current) return null;
	const target = identity(current);
	const index = items.findIndex((item) => identity(item) === target);
	if (index < 0) return null;
	return {
		target,
		position: index + 1,
		total: items.length,
		qualifier
	};
}
function walkPosition() {
	if (!walking) return null;
	const position = walking.read();
	if (!position || position.target !== walking.target) {
		walking = null;
		return null;
	}
	return {
		kind: walking.key,
		target: position.target,
		position: position.position,
		total: position.total,
		text: walkPositionLabel(walking.noun, position.position, position.total, position.qualifier)
	};
}
const STEPS = Object.freeze([
	"previous",
	"next",
	"first",
	"last"
]);
const capital = (word) => word.slice(0, 1).toUpperCase() + word.slice(1);
function rowWalk({ id, noun, plural, rows, position = () => listWalkPosition(rows(), focused()), steps = STEPS, landed, scroll = true }) {
	const [up, down, home, end] = steps;
	const route = (binding, step) => ({
		id: `${id}.${step}`,
		binding,
		title: `${capital(step)} ${noun.toLowerCase()}`
	});
	const land = (pick) => {
		const was = focused();
		const row = pick(rows());
		if (!row) return;
		focusDestination(row, "move");
		if (scroll) scrollIntoView(row, { block: "nearest" });
		beginWalk(id, noun, position);
		if (row !== was) landed?.(row);
	};
	return [{
		id: `${id}.walk`,
		keys: ["ArrowUp", "ArrowDown"],
		routes: [route("ArrowUp", up), route("ArrowDown", down)],
		title: `walk the ${plural}`,
		repeat: true,
		travels: scroll,
		runKey: (binding) => land((list) => clampedRow(list, focused(), binding === "ArrowDown" ? 1 : -1, 0))
	}, {
		id: `${id}.edge`,
		keys: ["Home", "End"],
		routes: [route("Home", home), route("End", end)],
		title: `${home} / ${end}`,
		travels: scroll,
		runKey: (binding) => land((list) => binding === "Home" ? list[0] : list.at(-1))
	}];
}
function beginWalk(key, noun, read) {
	const position = read();
	if (!position) {
		walking = null;
		return null;
	}
	walkPositionLabel(noun, position.position, position.total, position.qualifier);
	walking = {
		key,
		noun,
		read,
		target: position.target
	};
	holdStatus(HOLD_MS);
	const shown = walkPosition();
	repaint();
	return shown?.text ?? null;
}

//#endregion
//#region runtime/thread/state.js
const threadState = readPart((root) => root.effective.thread);
const allThreads = () => threadState().all;
const readThreads = readPart((root) => root.effective.thread.collection);
const threadList = () => readThreads().threads;
const names = /* @__PURE__ */ new WeakMap();
function threadNamed(name) {
	const threads = allThreads();
	let index = names.get(threads);
	if (!index) names.set(threads, index = threadNames(threads));
	return index.get(name) ?? null;
}
const threadIdNamed = (name) => threadNamed(name)?.id ?? name;

//#endregion
//#region runtime/thread/replies.js
const rowCompositions = /* @__PURE__ */ new WeakMap();
const compositions = /* @__PURE__ */ new Map();
const sessions = Z(0);
function openSession(context, session) {
	compositions.set(context, session);
	tick(sessions);
	return session;
}
function closeSession(context) {
	if (compositions.delete(context)) tick(sessions);
}
const views = /* @__PURE__ */ new Set();
const available = (composition) => !!composition && [...views].some((view) => view.composition === composition) && composition.controls.input.isConnected;
function adopt(context, composition) {
	const session = compositions.get(context);
	if (session?.owner !== composition) session?.owner?.sync.cancelDictation();
	const caret = readCaret(session?.owner?.controls.input ?? null);
	if (session) session.owner = composition;
	else openSession(context, { owner: composition });
	if (caret) composition.controls.input.setSelectionRange(...caret);
	remember(composition);
}
function remember(composition) {
	const session = compositions.get(composition.context);
	if (!session || session.owner !== composition) return;
	const editing = captureDraftEditing(composition.controls.input);
	if (editing) session.editing = editing;
}
const compositionOf = (node) => {
	const row = closestAcross(node ?? null, SAY_ROW);
	return row ? rowCompositions.get(row) : void 0;
};
const replyDraftContext = (node) => compositionOf(node)?.context ?? null;
const replyThreadKey = (node) => compositionOf(node)?.key ?? null;
function holdReplyCompositions(threads, realize) {
	const current = new Map(threads.map((thread) => [replyContext(threadKey(thread)), thread]));
	const retained = [];
	const retired = [];
	for (const [context, session] of compositions) {
		const thread = current.get(context);
		if (!thread) {
			retired.push([context, session]);
			continue;
		}
		if (!session.owner || session.continuing) continue;
		const owner = session.owner;
		const editing = captureDraftEditing(owner.controls.input) ?? session.editing;
		if (!editing) continue;
		session.editing = editing;
		const intent = restrictUserIntent(retainUserIntent(), () => compositions.get(context) === session && session.owner === owner && draftEditingStands(editing));
		retained.push({
			context,
			session,
			owner,
			intent,
			id: thread.id
		});
	}
	return async (restore) => {
		for (const [context, session] of retired) if (compositions.get(context) === session) endSession(context);
		const displaced = retained.filter(({ session, owner, intent }) => !available(owner) && !session.continuing && intent());
		for (const { session } of displaced) session.continuing = true;
		try {
			await restore?.();
			for (const { context, owner, intent, id } of displaced) {
				if (available(owner) || !intent()) continue;
				const destination = await realize(id, intent);
				if (!intent.available()) continue;
				const replacement = compositionOf(destination) ?? compositionOf(destination?.querySelector(".lf-thread-reply, .lf-say"));
				if (replacement && drawn$2(replacement.controls.input)) adopt(context, carry(replacement, owner));
			}
		} finally {
			for (const { session } of displaced) session.continuing = false;
		}
	};
}
const threadHoldsDraft = (key, ids) => draftHasContent(replyContext(key)) || ids.some((id) => draftHasContent(rewriteContext(id)));
const replyDraftsHold = (retains) => [...compositions].some(([context, session]) => loadDraft(context) !== null && !retains(session.owner?.controls.input));
function endSession(context) {
	const session = compositions.get(context);
	closeSession(context);
	if (session?.owner && !session.owner.binding) session.owner.row.remove();
	return session;
}
function dismissContext(context) {
	const session = endSession(context);
	if (!session) return;
	session.owner?.sync.cancelDictation();
	session.owner?.changed();
}
const dismissReply = (key) => dismissContext(replyContext(key));
const pressContext = (target) => {
	const node = target instanceof Element ? target : null;
	const row = replyDraftContext(node);
	if (row !== null) return row;
	const thread = closestAcross(node, THREAD);
	return thread ? replyDraftContext(threadPart(thread, "reply")) : null;
};
onPressAway(([node]) => [...compositions.keys()].some((context) => context !== pressContext(node)), ([node], [from]) => {
	const kept = [pressContext(node), pressContext(from)];
	for (const context of [...compositions.keys()]) if (!kept.includes(context)) dismissContext(context);
});
const dismissReplyAt = (node) => {
	const context = replyDraftContext(node);
	if (context !== null) dismissContext(context);
};
function handOver(target, owner, binding) {
	const redrawGiver = owner.binding?.give();
	binding.take(owner);
	redrawGiver?.();
	const session = compositions.get(owner.context);
	if (session) session.owner = owner;
	return owner;
}
function carry(target, owner) {
	if (target === owner || owner.retired || !target.binding || owner.binding && drawn$2(owner.row)) return target;
	const session = compositions.get(owner.context);
	if (session && session.owner !== owner && session.owner !== target) return target;
	return handOver(target, owner, target.binding);
}
let park = null;
function parkRow(row) {
	if (!park) {
		park = el("div", "lf-reply-park");
		park.hidden = true;
	}
	if (!park.isConnected) move(chromeRoot, park, chromeForeground);
	move(park, row, null);
}
function releaseReplies(surface) {
	for (const { owner } of compositions.values()) {
		if (!owner?.binding || !surface.contains(owner.row)) continue;
		const shown = [...views].find(({ composition: view }) => view.context === owner.context && view !== owner && drawn$2(view.controls.input));
		owner.binding.give();
		if (shown) shown.binding.take(owner);
		else parkRow(owner.row);
	}
}
function replyControlDestination(node) {
	const composition = compositionOf(node);
	if (!composition) return null;
	const part = ["input", "send"].find((name) => composition.controls[name] === node);
	if (!part) return null;
	return (thread) => {
		const target = compositionOf(thread?.querySelector(SAY_ROW));
		return target ? carry(target, composition).controls[part] : null;
	};
}
function sendReply(draftCtx, key, text, owns, actions) {
	return sendMessage(draftCtx, owns, (attempt) => actions.reply(key, text, { attempt }));
}
function wireReply(key, row, input, commands, { hint, hintParts, hintLead, accessibleName, busy }) {
	row.classList.add("lf-comment-box");
	const draftCtx = replyContext(key);
	input.value = loadDraft(draftCtx)?.text ?? "";
	const sync = commands.wireInput(input, {
		hint,
		hintParts,
		hintLead,
		accessibleName,
		busy,
		sends: "send",
		sendClass: "lf-thread-send",
		save: (v) => {
			saveDraft(draftCtx, v);
			tellDraft(draftCtx, v);
			remember(composition);
		},
		send: (...args) => composition.send?.(...args),
		rows: [{
			id: "message.edit.last",
			keys: ["ArrowUp"],
			title: "edit last message",
			when: () => !sync.value() && Boolean(composition.binding?.editLast?.available()),
			run: () => composition.binding?.editLast?.open()
		}]
	});
	const composition = {
		context: draftCtx,
		key,
		row,
		controls: {
			input,
			send: sync.button
		},
		send: null,
		binding: null,
		changed: () => composition.binding?.onChange(),
		sync
	};
	rowCompositions.set(row, composition);
	sync();
	return composition;
}
function attach(composition, binding) {
	const { context, row, controls, sync } = composition;
	composition.binding = binding;
	composition.send = (_text, raw, owns) => {
		const { actions, sending, sent } = binding;
		const land = sendLanding(controls.input);
		sending?.();
		if (!sendReply(context, composition.key, raw, owns, actions)) return;
		if (sent) return sent();
		land(controls.input);
	};
	const attached = {
		composition,
		binding
	};
	views.add(attached);
	const begin = () => {
		adopt(context, composition);
		composition.changed();
	};
	sync.load(loadDraft(context)?.text ?? "");
	const stopMirror = mirrorDraft(controls.input, sync, context, {
		retained: true,
		mirrored: true,
		onChange: (value) => {
			if (value === null && !draftHasContent(context)) dismissContext(context);
			remember(composition);
			composition.changed();
		}
	});
	row.addEventListener("focusin", begin);
	return ({ handingOn = false } = {}) => {
		if (!handingOn) sync.cancelDictation();
		stopMirror();
		row.removeEventListener("focusin", begin);
		views.delete(attached);
		composition.binding = null;
		composition.send = null;
	};
}
const replyCompositionHasDraft = (node) => {
	const ctx = replyDraftContext(node);
	return ctx ? loadDraft(ctx) !== null : null;
};
const replyIsEditing = (key) => {
	sessions.value;
	return compositions.has(replyContext(key));
};
async function restoreReplyEditing(editing, land) {
	if (!editing?.mirrored || !draftEditingStands(editing)) return null;
	const context = editing.context;
	let session = compositions.get(context);
	if (!session) session = openSession(context, { owner: null });
	try {
		return await land();
	} finally {
		if (compositions.get(context) === session && !available(session.owner)) closeSession(context);
	}
}
function createReplyView(key, commands, redraw, { onChange = () => {}, editLast = null, hint = () => "Reply", hintParts = null, hintLead = () => "", accessibleName = "Reply", busy = () => false, sending = null, sent = null } = {}) {
	const fresh = () => {
		const row = offer("div", "lf-thread-reply");
		const input = offer(TEXT_FIELD);
		input.name = "reply";
		row.append(input);
		return wireReply(key, row, input, commands, {
			hint,
			hintParts,
			hintLead,
			accessibleName,
			busy
		});
	};
	let composition = fresh();
	const binding = {
		...commands,
		onChange,
		editLast,
		sending,
		sent,
		give: () => {
			detach({ handingOn: true });
			composition = fresh();
			detach = attach(composition, binding);
			return redraw;
		},
		take: (owner) => {
			if (currentLocationIn(composition.row)) blurFocused();
			detach();
			composition.retired = true;
			composition = owner;
			detach = attach(composition, binding);
			redraw();
		}
	};
	let detach = attach(composition, binding);
	return {
		get node() {
			return composition.row;
		},
		get input() {
			return composition.controls.input;
		},
		cancelDictation: () => composition.sync.cancelDictation(),
		sync: () => composition.sync(),
		claim(shown) {
			const owner = compositions.get(composition.context)?.owner;
			if (owner && owner !== composition && !owner.binding && !owner.retired && shown()) binding.take(owner);
		},
		dispose: () => detach()
	};
}

//#endregion
//#region runtime/abort.js
const aborted = (signal) => {
	const { promise, resolve } = Promise.withResolvers();
	if (signal.aborted) resolve();
	else signal.addEventListener("abort", () => resolve(), { once: true });
	return promise;
};

//#endregion
//#region runtime/dom-children.js
var SourcePairs = class extends WeakMap {
	constructor() {
		super();
	}
	get(source) {
		return super.get(source);
	}
	set(source, live) {
		return super.set(source, live);
	}
	require(source) {
		const live = this.get(source);
		if (!live) throw new Error("The authored source has no paired native node");
		return live;
	}
	pair(source, live) {
		if (source instanceof Element && live instanceof Element) return this.set(source, live);
		if (source instanceof CharacterData && live instanceof CharacterData && source.nodeType === live.nodeType) return this.set(source, live);
		throw new Error("An authored source and its live node must have the same native kind");
	}
};
function setChildren(parent, nodes) {
	setChildLists([[parent, nodes]]);
}
function setChildLists(lists) {
	for (const [parent, nodes] of lists) orderChildren(parent, nodes);
	for (const [parent, nodes] of lists) {
		const keep = new Set(nodes);
		for (const child of [...parent.childNodes]) if (!keep.has(child)) child.remove();
	}
}
function orderChildren(parent, nodes) {
	const owned = new Set(nodes);
	order(parent, nodes, (node) => !owned.has(node));
}
function setRenderedChildren(parent, nodes) {
	const after = document.createDocumentFragment();
	after.append(...nodes);
	patchChildren(parent, parent, after, {
		pairs: selfPairs(parent),
		arrive: (node) => node,
		sameValue: (held, wanted) => held === wanted,
		touched: () => {},
		declared: () => false,
		body: () => null,
		same: (held, wanted) => held.isEqualNode(wanted),
		generated: () => false,
		contains: (target, owner) => Boolean(owner?.contains(target)),
		reaches: () => false
	});
}
function selfPairs(parent) {
	const pairs = new SourcePairs();
	for (const node of sourceNodes(parent)) pairs.pair(node, node);
	return pairs;
}
function order(parent, nodes, passed = () => false) {
	const list = [...nodes];
	const stay = staying(parent, list);
	let cursor = parent.firstChild;
	for (const node of list) {
		while (cursor && passed(cursor)) cursor = cursor.nextSibling;
		if (node === cursor) cursor = cursor.nextSibling;
		else if (stay.has(node)) cursor = node.nextSibling;
		else move(parent, node, cursor);
	}
}
function staying(parent, nodes) {
	const places = new Map([...parent.childNodes].map((node, at) => [node, at + 1]));
	const size = places.size;
	const best = new Array(size + 1);
	let last = null;
	for (const node of nodes) {
		const place = places.get(node);
		if (!place) continue;
		let before = null;
		for (let i = place - 1; i > 0; i -= i & -i) {
			const candidate = best[i];
			if (candidate && (!before || candidate.weight >= before.weight)) before = candidate;
		}
		const weight = (node.nodeType === Node.ELEMENT_NODE ? nodes.length + 1 : 1) + (before?.weight ?? 0);
		const chain = {
			node,
			weight,
			previous: before
		};
		for (let i = place; i <= size; i += i & -i) {
			const held = best[i];
			if (!held || weight >= held.weight) best[i] = chain;
		}
		if (!last || weight >= last.weight) last = chain;
	}
	const stay = /* @__PURE__ */ new Set();
	for (let chain = last; chain; chain = chain.previous) stay.add(chain.node);
	return stay;
}
function patchTree(before, after, rules) {
	const live = rules.pairs.require(before);
	patchAttributes(live, before, after, rules);
	patchChildren(holder(live, rules), tree(before), tree(after), rules);
}
function patchRetains(before, after, target, rules) {
	if (!target?.isConnected) return false;
	if (!sourceOwns(before, target, rules)) return true;
	return retainedWithin(before, after, target, rules);
}
function sourceOwns(source, target, rules) {
	const owns = (node) => rules.contains(target, rules.pairs.get(node));
	if (owns(source)) return true;
	for (const node of sourceNodes(source)) if (owns(node)) return true;
	return false;
}
function retainedWithin(before, after, target, rules) {
	const live = rules.pairs.get(before);
	if (!live || !sourceOwns(before, target, rules)) return false;
	if (rules.same(before, after)) return true;
	if (live === target) return false;
	if (before.attributes.length !== after.attributes.length || [...before.attributes].some(({ name, value }) => {
		const attribute = after.getAttributeNode(name);
		return !attribute || !rules.sameValue(value, attribute.value);
	})) return false;
	const children = [...tree(before).childNodes];
	const arriving = [...tree(after).childNodes];
	const forward = matchNodes(children, arriving);
	const matches = new SourcePairs();
	for (const wanted of arriving) {
		const held = forward.get(wanted);
		if (held) matches.pair(held, wanted);
	}
	for (const held of children) {
		if (!(held instanceof Element)) continue;
		const node = rules.pairs.get(held);
		if (!node || !sourceOwns(held, target, rules)) continue;
		const wanted = matches.get(held);
		if (!wanted) return false;
		if (!(atomic(held, wanted, node, rules) ? rules.same(held, wanted) : retainedWithin(held, wanted, target, rules))) return false;
	}
	return true;
}
const tree = (node) => node instanceof HTMLTemplateElement ? node.content : node;
const holder = (live, rules) => rules.body(live) ?? tree(live);
function patchAttributes(live, before, after, rules) {
	let changed = false;
	for (const { name, value } of [...before.attributes]) {
		if (after.hasAttribute(name)) continue;
		if (name === "class") live.classList.remove(...tokens$1(value));
		else live.removeAttribute(name);
		changed = true;
	}
	for (const { name, value } of after.attributes) {
		const held = before.getAttribute(name);
		if (held !== null && rules.sameValue(held, value)) continue;
		if (name === "class") {
			live.classList.remove(...tokens$1(held ?? ""));
			live.classList.add(...tokens$1(value));
		} else live.setAttribute(name, value);
		changed = true;
	}
	if (changed) rules.touched(live);
}
const tokens$1 = (value) => value.split(/\s+/).filter(Boolean);
function writeText(node, next) {
	const held = node.data;
	if (held === next) return;
	let prefix = 0;
	while (prefix < held.length && prefix < next.length && held[prefix] === next[prefix]) prefix += 1;
	let suffix = 0;
	while (suffix < held.length - prefix && suffix < next.length - prefix && held[held.length - suffix - 1] === next[next.length - suffix - 1]) suffix += 1;
	node.replaceData(prefix, held.length - prefix - suffix, next.slice(prefix, next.length - suffix));
}
function evict(before, live, rules) {
	live.parentNode?.removeChild(live);
	for (const inner of sourceNodes(before)) {
		const stray = rules.pairs.get(inner);
		if (!stray?.parentNode || live.contains(stray)) continue;
		stray.parentNode.removeChild(stray);
	}
}
function* sourceNodes(node) {
	for (const child of tree(node).childNodes) {
		yield child;
		yield* sourceNodes(child);
	}
}
function patchChildren(liveParent, beforeParent, afterParent, rules) {
	const held = [...beforeParent.childNodes];
	const wanted = [...afterParent.childNodes];
	const matches = matchNodes(held, wanted);
	const matched = new Set(wanted.map((node) => matches.get(node)));
	for (const node of held) if (!matched.has(node)) evict(node, rules.pairs.require(node), rules);
	const placed = [];
	for (const node of wanted) {
		const pair = patchPair(node, matches, rules.pairs);
		if (!pair || !pair.live.parentNode) {
			placed.push(rules.arrive(node, liveParent));
			continue;
		}
		const { live } = pair;
		if (pair.kind === "data") {
			writeText(pair.live, pair.after.data);
			rules.pairs.set(pair.after, pair.live);
		} else {
			const { before, after } = pair;
			if (!atomic(before, after, pair.live, rules)) patchTree(before, after, rules);
			else if (!rules.same(before, after)) {
				evict(before, pair.live, rules);
				placed.push(rules.arrive(after, liveParent));
				continue;
			} else pairInterior(before, after, rules);
			rules.pairs.set(after, pair.live);
		}
		if (live.parentNode === liveParent) placed.push(live);
	}
	order(liveParent, placed, rules.generated);
}
function patchPair(after, matches, pairs) {
	if (after instanceof Element) {
		const before = matches.get(after);
		const live = before && pairs.get(before);
		return before && live ? {
			kind: "element",
			before,
			after,
			live
		} : null;
	}
	if (after instanceof CharacterData) {
		const before = matches.get(after);
		const live = before && pairs.get(before);
		return before && live ? {
			kind: "data",
			before,
			after,
			live
		} : null;
	}
	throw new Error("Authored child nodes must be elements or character data");
}
function pairInterior(before, after, rules) {
	const held = [...sourceNodes(before)];
	const wanted = [...sourceNodes(after)];
	if (held.length !== wanted.length) return;
	const originals = held[Symbol.iterator]();
	for (const node of wanted) {
		const original = originals.next().value;
		if (!original) throw new Error("An unchanged source must retain its complete node sequence");
		const live = rules.pairs.get(original);
		if (live) rules.pairs.pair(node, live);
	}
}
const atomic = (before, after, live, rules) => before.matches("style, link[rel~=\"stylesheet\" i]") || rules.declared(before) && !rules.reaches(before, after) || [...tree(before).childNodes].some((node) => rules.pairs.get(node)?.parentNode !== holder(live, rules));
function matchNodes(held, wanted) {
	const matches = new SourcePairs();
	const matched = /* @__PURE__ */ new Set();
	const byId = /* @__PURE__ */ new Map();
	for (const node of held) if (node instanceof Element && node.id && !byId.has(node.id)) byId.set(node.id, node);
	for (const node of wanted) {
		if (!(node instanceof Element) || !node.id) continue;
		const match = byId.get(node.id);
		if (!match || match.localName !== node.localName || matched.has(match)) continue;
		matches.set(node, match);
		matched.add(match);
	}
	alignRest(held.filter((node) => !matched.has(node)), wanted.filter((node) => !matches.has(node)), matches);
	return matches;
}
function diffNode(nodes, index) {
	const node = nodes[index];
	if (!node) throw new Error("A child diff named a source position outside its input");
	return node;
}
const COLLAPSE = /\s+/g;
const signature = (node) => {
	if (node instanceof CharacterData) return `${node.nodeType}:${node.data}`;
	if (!(node instanceof Element)) throw new Error("Authored child nodes must be elements or character data");
	const words = tree(node).textContent ?? "";
	return `1:${node.localName}#${node.id}:${words.replace(COLLAPSE, " ").trim()}`;
};
function alignRest(held, wanted, matches) {
	let heldAt = 0;
	let wantedAt = 0;
	let gapHeld = [];
	let gapWanted = [];
	const closeGap = () => {
		pairInGap(gapHeld, gapWanted, matches);
		gapHeld = [];
		gapWanted = [];
	};
	for (const run of diffArrays(held.map(signature), wanted.map(signature))) {
		const count = run.value.length;
		if (run.added) gapWanted.push(...wanted.slice(wantedAt, wantedAt += count));
		else if (run.removed) gapHeld.push(...held.slice(heldAt, heldAt += count));
		else {
			closeGap();
			for (let at = 0; at < count; at++) matches.pair(diffNode(wanted, wantedAt + at), diffNode(held, heldAt + at));
			heldAt += count;
			wantedAt += count;
		}
	}
	closeGap();
}
function pairInGap(held, wanted, matches) {
	let heldAt = 0;
	let wantedAt = 0;
	for (const run of diffArrays(held, wanted, { comparator: interchangeable })) {
		const count = run.value.length;
		if (run.added) wantedAt += count;
		else if (run.removed) heldAt += count;
		else {
			for (let at = 0; at < count; at++) matches.pair(diffNode(wanted, wantedAt + at), diffNode(held, heldAt + at));
			heldAt += count;
			wantedAt += count;
		}
	}
}
const interchangeable = (held, wanted) => held.nodeType === wanted.nodeType && (!(held instanceof Element) || wanted instanceof Element && held.localName === wanted.localName && !(held.id && wanted.id));

//#endregion
//#region runtime/thread/folding.js
const NAMED = 48;
function settledName(key) {
	const thread = threadNamed(key);
	if (!thread) return "the thread";
	const passage = threadPassage(thread);
	return anchorLabel(passage?.quote ? {
		...passage,
		quote: excerptWords(passage.quote, NAMED)
	} : passage, thread.root.about) || quotedWords(threadName(thread), NAMED);
}
async function settleThread({ parent, key, resolved, prepareLanding, pendingEntries, actions, landedAway, offerUndo, returnToThread }) {
	const land = prepareLanding?.();
	const since = inputCount();
	const attempt = randomId();
	const named = settledName(key);
	const answer = resolved ? actions.reopen(key, { attempt }) : actions.resolve(key, { attempt });
	if (!answer) return;
	notice(`${resolved ? "Reopened" : "Resolved"} ${named}`, { press: offerUndo(attempt) });
	if (land) landedAway(attempt);
	await landGesture({
		land,
		answer,
		pending: () => pendingEntries().some((entry) => entry.event.attempt === attempt),
		refused: async () => {
			const mayReturn = retainUserIntent({ since });
			await whenDocumentPresented();
			return returnToThread(parent(), mayReturn);
		}
	});
}
async function landGesture({ land, answer, pending, refused }) {
	const step = async (work) => {
		try {
			return Boolean(await work?.());
		} catch {
			return false;
		}
	};
	const startLanding = bindQueuedWork(() => pending() ? step(land) : false);
	const finishLanding = bindQueuedWork((accepted, landed) => {
		if (!accepted) return land && step(refused);
		if (!landed) return step(land);
	});
	const presentation = whenDocumentPresented();
	paintKeys();
	try {
		await presentation;
		const landed = await startLanding();
		await finishLanding(await answer, landed);
	} finally {
		paintKeys();
	}
}

//#endregion
//#region runtime/thread/focus.js
function focusThread(thread, cause) {
	focusDestination(thread, cause);
}
const threadReplyInput = (thread) => {
	const input = thread && threadPart(thread, "reply");
	return input && shownBox(input).height ? input : null;
};
function threadFocusDestination(thread, options = {}) {
	if (options.part === "message") return thread.querySelector(`.lf-msg[data-event="${CSS.escape(options.message)}"]`);
	return (options.part === "thread" ? thread : null) ?? threadReplyInput(thread) ?? thread;
}
function focusedThreadTarget() {
	const active = focused();
	return active?.matches?.(".lf-page-thread, [data-lf-thread-view]") ? active : null;
}
const threadIn = (node) => closestAcross(node ?? null, THREAD);
const heldThread = () => threadIn(focused());
const heldThreadId = () => drawnThreadId(heldThread());
let pressed = null;
let release = 0;
function releasePress() {
	if (!pressed || release) return;
	release = nextRender(() => {
		release = 0;
		pressed = null;
		repaint();
	});
}
onPress((start) => {
	if (start.button !== 0) return null;
	pressed = heldThreadId();
	return releasePress;
});
const currentLocationThreadId = () => heldThreadId() ?? pressed;
const mayReplyTo = (id, intent) => restrictUserIntent(intent, () => allThreads().some((candidate) => candidate.id === id));
async function replyDestination(id, open, intent, { destination = (thread) => threadPart(thread, "reply"), scroll = true } = {}) {
	const mayReply = mayReplyTo(id, intent);
	if (!mayReply()) return null;
	const shown = await open(id, {
		part: "reply",
		scroll,
		intent: mayReply
	});
	const thread = shown instanceof Element ? closestAcross(shown, THREAD) : null;
	if (!thread || focused() !== shown || !mayReply()) return null;
	const control = destination(thread);
	if (!control) return null;
	if (control !== focused()) mayReply.handoff(() => focusDestination(control, "move"));
	return focused() === control && mayReply() ? control : null;
}
async function threadDestination(id, open, may) {
	const at = focused();
	if (at && at !== document.body && drawn$2(at)) return null;
	const shown = await open(id, {
		part: "thread",
		intent: may
	});
	return shown instanceof Element && focused() === shown && may() ? shown : null;
}
const carried = /* @__PURE__ */ new WeakSet();
let carrying = null;
const carryingThreadPlace = (node) => {
	const place = carrying;
	return Boolean(place && place.node === node && (place.reply ? place.may() : place.intent() && allThreads().some((thread) => thread.id === place.id && !thread.resolved)));
};
function holdThreadPlace(open, { threadAt, seated }) {
	carrying = null;
	const held = holdCurrentLocation();
	const node = held?.node;
	if (!node || carried.has(node)) return null;
	const destination = replyControlDestination(node);
	const key = destination && replyThreadKey(node);
	const thread = !destination && closestAcross(node, ".lf-page-thread");
	const id = key ? allThreads().find((each) => threadKey(each) === key)?.id : thread ? drawnThreadId(thread) : threadAt(node);
	if (!id) return null;
	const intent = retainUserIntent({ source: node });
	const may = destination ? mayReplyTo(id, intent) : restrictUserIntent(intent, () => allThreads().some((each) => each.id === id && !each.resolved) && seated(id));
	const carry = {
		node,
		id,
		intent,
		may,
		reply: Boolean(destination)
	};
	carrying = carry;
	return async () => {
		try {
			return await held.restore(async () => {
				carried.add(node);
				const control = destination ? await replyDestination(id, open, intent, { destination }) : await threadDestination(id, open, may);
				if (control === node) carried.delete(node);
				return control;
			});
		} finally {
			if (carrying === carry) carrying = null;
		}
	};
}

//#endregion
//#region runtime/reading-continuity.js
let generation = 0;
let interrupted = document.visibilityState === "hidden";
const readingIsContinuous = () => document.visibilityState !== "hidden" && !interrupted;
const readingReturn = () => interrupted ? generation : null;
const CONTINUITY = "lf-reading-continuity";
const changed = () => document.dispatchEvent(new CustomEvent(CONTINUITY, { detail: { continuous: readingIsContinuous() } }));
function onReadingInterrupted(interrupted) {
	const listener = () => {
		if (!readingIsContinuous()) interrupted();
	};
	document.addEventListener(CONTINUITY, listener);
	return () => document.removeEventListener(CONTINUITY, listener);
}
document.addEventListener("visibilitychange", () => {
	if (document.visibilityState === "hidden") {
		generation += 1;
		interrupted = true;
	}
	changed();
});
function completeReadingReturn(returned) {
	if (returned === null || returned !== generation || document.visibilityState === "hidden" || !interrupted) return;
	interrupted = false;
	changed();
}

//#endregion
//#region runtime/thread/held-news.js
const gesturedOn = (thread) => threadState().gestured.includes(thread.id);
const gestured = (key) => {
	const thread = allThreads().find((each) => threadKey(each) === key);
	return thread !== void 0 && gesturedOn(thread);
};
const tokens = (reactions) => new Set(reactions.choices.filter(({ inForce }) => inForce).map(({ name }) => name));
const symmetric = (a, b) => [...a, ...b].filter((name) => !a.has(name) || !b.has(name));
const fold = (summary, drawn) => JSON.stringify([
	summary.id,
	summary.covers.filter((id) => drawn.has(id)),
	Boolean(summary.protected?.length)
]);
const rewritten = (message) => message.base === message.id ? null : message.base;
function messageChange(prior, message) {
	if (!prior) return "joined";
	const reworded = JSON.stringify(prior.body) !== JSON.stringify(message.body);
	if (prior.provisional) return reworded ? "joined" : null;
	if (!reworded) return null;
	return rewritten(prior) === rewritten(message) ? "grew" : "rewritten";
}
function threadChange(was, now, { progressOpen = false } = {}) {
	const drawn = new Map(was.messages.map((message) => [message.key, message]));
	const settled = Boolean(was.resolved) === Boolean(now.resolved) ? null : now.resolved ? "Resolved" : "Reopened";
	const news = {
		settled,
		working: was.working?.words !== now.working?.words,
		replies: 0,
		messages: 0,
		edits: 0,
		reactions: 0,
		summaries: 0,
		appended: false
	};
	const changed = /* @__PURE__ */ new Set();
	const joined = /* @__PURE__ */ new Set();
	const arrived = /* @__PURE__ */ new Set();
	for (const message of now.messages) {
		const prior = drawn.get(message.key);
		const change = messageChange(prior, message);
		if (change === "joined") joined.add(message.key);
		if (!prior || prior.provisional) arrived.add(message.id);
		if (change === "joined" && message.progress && !progressOpen && !now.resolved) continue;
		if (change === "joined") {
			if (message.author === "agent") news.replies += 1;
			else news.messages += 1;
			news.appended = true;
		} else if (change === "grew" || change === "rewritten") {
			news[change === "grew" ? "replies" : "edits"] += 1;
			changed.add(message.key);
		} else if (settled) changed.add(message.key);
		else if (message.reactions && prior?.reactions) {
			const turned = symmetric(tokens(prior.reactions), tokens(message.reactions));
			news.reactions += turned.length;
			if (turned.length) changed.add(message.key);
		}
	}
	const summaries = (reading) => {
		const ids = new Set(reading.messages.map(({ id }) => id));
		return new Map(reading.summaries.map((summary) => [fold(summary, ids), summary]));
	};
	const before = summaries(was);
	const after = summaries(now);
	const added = [...after].filter(([at]) => !before.has(at)).map(([, each]) => each);
	const gone = [...before].filter(([at]) => !after.has(at)).map(([, each]) => each);
	news.summaries = added.length || gone.length;
	const visible = new Set(now.messages.map(({ id }) => id));
	const retired = new Set(now.source.msgs.filter((message) => message.completed_by !== void 0 && visible.has(message.completed_by)).map(({ key }) => key));
	const removed = was.messages.filter(({ key }) => retired.has(key));
	const keys = new Map([...was.messages, ...now.messages].map(({ id, key }) => [id, key]));
	const arrivals = new Set(now.messages.filter(({ id }) => arrived.has(id)).map(({ key }) => key));
	const tail = was.messages.map(({ key }) => key).filter((key) => !arrivals.has(key));
	const footFold = removed.length > 0 && !added.length && !gone.length && tail.slice(-removed.length).every((key) => retired.has(key));
	const folds = {
		messages: [...removed.map(({ key }) => key), ...[...added, ...gone].flatMap(({ covers }) => covers.flatMap((id) => keys.get(id) ?? []))],
		summaries: gone.map(({ id }) => id)
	};
	if (!settled && [
		"working",
		"replies",
		"messages",
		"edits",
		"reactions",
		"summaries"
	].every((count) => !news[count])) return null;
	const appendedAtEnd = news.appended && was.messages.filter(({ key }) => !retired.has(key)).every((message, index) => now.messages[index]?.key === message.key);
	const turn = was.messages.findLastIndex((message) => message.author === "user" && !message.progress);
	const previousTurn = was.messages[turn];
	const asked = new Set(was.messages.slice(0, turn + 1).map(({ key }) => key));
	const currentTurn = now.messages.findIndex((message) => message.key === was.messages[turn]?.key);
	return {
		news,
		changed,
		joined,
		folds,
		appendedAtEnd,
		footFold,
		answers: previousTurn !== void 0 && currentTurn >= 0 && was.messages.slice(turn + 1).every((message) => message.progress || message.provisional) && !settled && !news.messages && !news.edits && !news.reactions && !news.summaries && !folds.summaries.length && (!news.appended || appendedAtEnd) && ![...changed, ...folds.messages].some((key) => asked.has(key)) ? Object.freeze({
			turn: previousTurn.key,
			reply: now.messages.slice(currentTurn + 1).find((message) => !message.progress)?.key ?? null
		}) : null
	};
}
function withheld(was, now) {
	const current = new Map(now.msgs.map((message) => [messageKey(message), message]));
	const msgs = was.msgs.flatMap((prior) => {
		const message = current.get(messageKey(prior));
		if (!message) return isReaction(prior) || prior.provisional ? [prior] : [];
		const { text, body, edited, content_version, provisional, reactions } = prior;
		return [Object.freeze({
			...message,
			text,
			body,
			edited,
			content_version,
			provisional,
			reactions,
			completed_by: message.completed_by ?? prior.completed_by
		})];
	});
	return Object.freeze({
		...now,
		root: msgs.find((message) => messageKey(message) === messageKey(now.root)) ?? now.root,
		resolved: was.resolved,
		msgs: Object.freeze(msgs),
		summaries: was.summaries
	});
}
const counted = (count, one, many) => count && `${count} ${count === 1 ? one : many}`;
const newsParts = ({ settled, replies, messages, edits, reactions, summaries, threads }) => [
	settled,
	counted(replies, "new reply", "new replies"),
	counted(messages, "new message", "new messages"),
	counted(edits, "message edited", "messages edited"),
	counted(reactions, "reaction changed", "reactions changed"),
	counted(summaries, "summary changed", "summaries changed"),
	counted(threads, "new thread", "new threads")
].flatMap((part) => typeof part === "string" && part.length > 0 ? [part] : []);
const newsCount = (total) => `${total} new`;
const said = (news) => {
	const { settled, replies, messages, edits, reactions, summaries, threads } = news;
	const total = [
		replies,
		messages,
		edits,
		reactions,
		summaries,
		threads
	].reduce((sum, count) => sum + (count ?? 0), settled ? 1 : 0);
	return {
		text: newsCount(total),
		label: newsParts(news).join(" · "),
		total
	};
};
function newsNotice(header = false) {
	const node = offerAction("inline", header ? "lf-thread-header-action lf-thread-news" : "lf-thread-news");
	keeps(node, "data-lf-news", "");
	const words = document.createElement("span");
	words.dataset.voice = "leaf";
	node.append(words);
	let open = () => null;
	node.addEventListener("mousedown", (event) => event.preventDefault());
	const show = () => {
		const currentLocation = focused() === node;
		const landing = open();
		if (currentLocation && landing) focusThread(landing, "move");
	};
	keys(node, "On news waiting in a thread", [{
		id: "thread.news",
		keys: PRESS,
		title: "show what is waiting",
		control: node,
		run: show
	}]);
	return {
		node,
		set(news) {
			keepsText(words, news.text);
			keeps(node, "title", news.label);
			node.classList.toggle("lf-reopen", news.reopened);
			open = news.open;
		}
	};
}
function seatNotice() {
	const notice = newsNotice();
	const node = offer("div", "lf-seat-news");
	node.append(notice.node);
	return {
		node,
		set(news, box) {
			notice.set(news);
			if (box?.isConnected) node.style.blockSize = layoutPx(box.getBoundingClientRect().height);
		}
	};
}
const holders = /* @__PURE__ */ new Set();
const showHeld = (id) => everySeat(id, (held, thread) => held.show(thread));
const showHeldThread = (id) => everySeat(id, (held, thread) => held.showThreads(thread));
function everySeat(id, show) {
	const thread = threadIdNamed(id);
	let shown = false;
	for (const held of holders) shown = show(held, thread) || shown;
	return shown;
}
let currentLocation = null;
onCurrentLocation((node, cause) => {
	if (cause === "drop") return;
	const thread = node && closestAcross(node, ".lf-page-thread, [data-lf-thread-view]");
	const id = drawnThreadId(thread);
	const arrived = id !== null && id !== currentLocation && (cause === "move" || cause === "step");
	currentLocation = id;
	if (arrived) showHeld(id);
});
var HeldNews = class {
	#seat;
	#view;
	#changed;
	#shown = null;
	#known = /* @__PURE__ */ new Set();
	#holds = /* @__PURE__ */ new Set();
	#released = /* @__PURE__ */ new Map();
	#threads = /* @__PURE__ */ new Set();
	#keys = /* @__PURE__ */ new Map();
	#stopWatching = null;
	constructor(seat, view, changed) {
		this.#seat = seat;
		this.#view = view;
		this.#changed = () => {
			if (seat.isConnected) changed();
		};
		holders.add(this);
	}
	hold(reading, { row }) {
		const candidate = this.prepare(reading, { row });
		candidate.commit();
		return candidate.reading;
	}
	prepare(reading, { row }) {
		const read = runtime.statePhase === "ready";
		if (!read || !readingIsContinuous()) this.#forget();
		const prior = read ? this.#shown : null;
		const keys = new Set(reading.threads.map(({ key }) => key));
		for (const key of this.#threads) if (!keys.has(key)) this.#threads.delete(key);
		this.#keys = new Map(reading.threads.map(({ id, key }) => [id, key]));
		if (prior) this.#arrive(prior, reading, row);
		const shown = this.#draw(prior, reading);
		const released = new Map(this.#released);
		if (this.#holding()) this.#stopWatching ??= whenNone([this.#seat], growthIsSeen, this.#all);
		else this.#stop();
		return {
			reading: shown,
			commit: () => {
				for (const [key, token] of released) if (this.#released.get(key) === token) this.#released.delete(key);
				this.#known = keys;
				this.#shown = read ? shown : null;
			}
		};
	}
	#arrive(prior, reading, row) {
		const arrived = reading.threads.filter(({ key }) => !this.#known.has(key));
		if (arrived.some(({ key }) => gestured(key))) this.#threads.clear();
		else if (arrived.length) {
			const last = prior.threads.at(-1)?.key;
			const after = last ? this.#view(last)?.node : this.#seat;
			if (readingIsContinuous() && after != null && growthAfterIsSeen(after) && (last || row)) for (const { key } of arrived) this.#threads.add(key);
			else this.#threads.clear();
		}
	}
	#draw(prior, reading) {
		this.#holds.clear();
		const drawn = new Map(prior?.threads.map((thread) => [thread.key, thread]));
		const threads = reading.threads.filter(({ key }) => !this.#threads.has(key)).map((thread) => {
			const was = drawn.get(thread.key);
			const shown = thread.visible !== false && !thread.folding;
			if (!was || !shown || this.#released.has(thread.key)) return {
				...thread,
				news: null,
				change: null
			};
			const held = threadChange(was, thread, { progressOpen: this.#view(thread.key)?.progressOpen ?? false });
			if (!held || gestured(thread.key) || !this.#view(thread.key)?.newsMoves(held)) return {
				...thread,
				news: null,
				change: held
			};
			this.#holds.add(thread.key);
			const { news } = held;
			return {
				...thread.reread(withheld(was.source, thread.source)),
				working: news.working ? was.working : thread.working,
				...news.settled === "Reopened" && { settlement: null },
				news,
				change: null
			};
		});
		const waiting = this.#threads.size;
		const host = threads.at(-1);
		if (waiting && host) host.news = {
			...host.news,
			threads: waiting
		};
		const presented = threads.map((thread) => {
			const notice = thread.news && said(thread.news);
			return {
				...thread,
				news: notice?.total ? {
					...notice,
					reopened: thread.news?.settled === "Reopened",
					open: () => {
						const node = this.#view(thread.key)?.node ?? null;
						showHeld(thread.id);
						if (thread === host && waiting) this.#open(thread.key, true);
						return node;
					}
				} : null
			};
		});
		const news = waiting && !host ? {
			...said({ threads: waiting }),
			reopened: false,
			open: () => this.#open(null, true)
		} : null;
		return Object.freeze({
			...reading,
			threads: Object.freeze(presented),
			news
		});
	}
	show(id) {
		const key = this.#keys.get(id);
		if (key === void 0) return false;
		const thread = this.#threads.has(key);
		if (!this.#holds.has(key) && !thread) return false;
		this.#open(key, thread);
		return true;
	}
	showThreads(id) {
		const key = this.#keys.get(id);
		if (key === void 0 || !this.#threads.has(key)) return false;
		this.#open(null, true);
		return true;
	}
	#open(key, threads) {
		const first = threads && [...this.#threads][0];
		let changed = false;
		if (key && this.#holds.has(key) && !this.#released.has(key)) {
			this.#released.set(key, Symbol("release"));
			changed = !gestured(key);
		}
		if (threads && this.#threads.size) {
			this.#threads.clear();
			changed = true;
		}
		if (changed) this.#changed();
		const destination = key ?? first;
		return destination ? this.#view(destination)?.node ?? null : null;
	}
	release() {
		this.#forget();
	}
	#all = () => {
		if (!this.#holding()) return;
		this.#forget();
		this.#changed();
	};
	#forget() {
		for (const thread of this.#shown?.threads ?? []) this.#released.set(thread.key, Symbol("release"));
		this.#threads.clear();
	}
	#holding() {
		return Boolean(this.#threads.size || this.#holds.size);
	}
	get settled() {
		return !this.#holding() && !this.#released.size;
	}
	#stop() {
		this.#stopWatching?.();
		this.#stopWatching = null;
	}
	dispose() {
		this.#stop();
		holders.delete(this);
	}
};
var HeldReading = class {
	#region;
	#changed;
	#shown = null;
	#released = false;
	#watch = null;
	constructor(owner, region, changed) {
		this.#region = region;
		this.#changed = changed;
		watchOwner(owner, {
			connect: () => {
				if (this.#watch && !this.#watch.stop) this.#watch.stop = whenNone(this.#watch.nodes, growthIsSeen, this.show);
			},
			disconnect: () => {
				this.#watch?.stop?.();
				if (this.#watch) this.#watch.stop = null;
			}
		});
	}
	hold(reading) {
		if (runtime.statePhase !== "ready") {
			this.#shown = null;
			this.#stop();
			return reading;
		}
		const nodes = this.#region();
		if (this.#released || this.#shown === null || this.#shown === reading || !readingIsContinuous() || !nodes.some((node) => growthIsSeen(node))) {
			this.#released = false;
			this.#shown = reading;
			this.#stop();
		} else if (!this.#watch || this.#watch.nodes.length !== nodes.length || this.#watch.nodes.some((node, at) => node !== nodes[at])) {
			this.#stop();
			this.#watch = {
				nodes,
				stop: whenNone(nodes, growthIsSeen, this.show)
			};
		}
		return this.#shown;
	}
	release() {
		this.#released = true;
	}
	show = () => {
		this.release();
		this.#changed();
	};
	#stop() {
		this.#watch?.stop?.();
		this.#watch = null;
	}
};
function heldGrowth(node, change) {
	if (!pagePresented() || !readingIsContinuous() || !growthIsSeen(node)) {
		change();
		return () => {};
	}
	let waiting = true;
	const stop = () => {
		if (!waiting) return;
		waiting = false;
		unwatch();
		uninterrupt();
	};
	const show = () => {
		stop();
		change();
	};
	const unwatch = whenNone([node], growthIsSeen, show);
	const uninterrupt = onReadingInterrupted(show);
	return stop;
}
var HeldArrivals = class {
	#changed;
	#known = null;
	#held = /* @__PURE__ */ new Map();
	#watching = /* @__PURE__ */ new Map();
	constructor(changed) {
		this.#changed = changed;
	}
	hold(threads, { drawn, all }) {
		const read = runtime.statePhase === "ready";
		if (!read) this.#held.clear();
		else if (this.#known) this.#take(threads, drawn, this.#known);
		this.#known = read ? new Set(all.map(({ key }) => key)) : null;
		this.#watch(threads);
		return new Set(this.#held.keys());
	}
	#take(threads, drawn, known) {
		if (!readingIsContinuous()) {
			this.#lapse(() => true);
			return;
		}
		const keys = new Set(threads.map(({ thread }) => thread.key));
		this.#release(({ key }) => !keys.has(key));
		for (const { thread, datum } of threads) {
			const held = this.#held.get(thread.key);
			if (!held) continue;
			held.datum = datum;
			if (gesturedOn(thread)) this.#held.delete(thread.key);
			else if (drawn.has(datum)) this.#lapse((each) => each === held);
		}
		const arrived = threads.filter(({ thread }) => !known.has(thread.key));
		const started = new Set(arrived.filter(({ thread }) => gesturedOn(thread)).map(({ datum }) => datum));
		for (const { thread, datum, node } of arrived) if (started.has(datum)) this.#release((held) => held.datum === datum);
		else if (drawn.has(datum) || !growthAfterIsSeen(node)) this.#lapse((held) => held.datum === datum);
		else this.#held.set(thread.key, {
			key: thread.key,
			id: thread.id,
			datum
		});
	}
	#lapse(which) {
		const currentLocation = new Set(currentLocationNodes().map((node) => closestAcross(node, THREAD)?.getAttribute("data-thread")));
		return this.#release((held) => which(held) && !currentLocation.has(held.id));
	}
	#watch(threads) {
		const nodes = new Map(threads.map(({ datum, node }) => [datum, node]));
		const holding = new Set([...this.#held.values()].map(({ datum }) => datum));
		for (const [datum, watch] of this.#watching) if (!holding.has(datum) || watch.node !== nodes.get(datum)) {
			watch.stop();
			this.#watching.delete(datum);
		}
		for (const [datum, node] of nodes) {
			if (!holding.has(datum) || this.#watching.has(datum)) continue;
			const leave = () => {
				if (this.#lapse((held) => held.datum === datum)) this.#changed();
			};
			this.#watching.set(datum, {
				node,
				stop: whenNone([node], growthIsSeen, leave)
			});
		}
	}
	holds(id) {
		return [...this.#held.values()].some((held) => held.id === id);
	}
	show(ids) {
		return ids.filter((id) => this.#release((held) => held.id === id));
	}
	#release(which) {
		const released = [...this.#held.values()].filter(which);
		for (const { key } of released) this.#held.delete(key);
		return released.length > 0;
	}
	dispose() {
		for (const watch of this.#watching.values()) watch.stop();
		this.#watching.clear();
	}
};

//#endregion
//#region runtime/thread/reply-continuity.js
const room = (node) => {
	if (!node.isConnected) return 0;
	const { marginBlockStart, marginBlockEnd } = getComputedStyle(node);
	return node.getBoundingClientRect().height + parseFloat(marginBlockStart) + parseFloat(marginBlockEnd);
};
var ReplyContinuity = class {
	#owner;
	#row = null;
	#departure = null;
	#space = 0;
	#presenting = [];
	gap = document.createElement("div");
	constructor(owner) {
		this.#owner = owner;
		owner.classList.add("lf-reply-continuity");
		this.gap.className = "lf-reply-space";
		this.gap.setAttribute("aria-hidden", "true");
		owner.addEventListener("toggle", () => {
			if (!this.#visible()) this.release();
		});
	}
	#visible() {
		return this.#owner.isConnected && this.#row?.isConnected && growthIsSeen(this.#row);
	}
	before(own = []) {
		this.#row = this.#owner.querySelector(":scope > .lf-thread-reply");
		this.#presenting = [];
		if (!this.#visible()) return null;
		this.#presenting = own.filter((node) => node.isConnected).map((node) => ({
			node,
			height: room(node)
		}));
		const extent = parseFloat(getComputedStyle(this.#owner).blockSize);
		const place = offFlowSurfaceOf(this.#owner) ? null : placeKeeper(scrollerFor(this.#owner), {
			items: ".lf-reply-continuity",
			identity: (node) => node.getAttribute("data-thread"),
			preferred: () => this.#owner
		});
		return {
			extent,
			place,
			held: place?.take({ spans: false })
		};
	}
	after(reading) {
		this.#row = this.#owner.querySelector(":scope > .lf-thread-reply");
		const presenting = this.#presenting;
		this.#presenting = [];
		if (!this.#row?.isConnected) return this.release();
		if (!this.#visible()) {
			reading?.place?.finish(reading.held);
			return this.release();
		}
		if (reading != null) {
			const { extent, place, held } = reading;
			const own = presenting.reduce((sum, { node, height }) => sum + room(node) - height, 0);
			const now = parseFloat(getComputedStyle(this.#owner).blockSize);
			this.#keep(Math.max(0, this.#space + extent - now + own));
			place?.finish(held);
		}
		if (!this.#visible()) return this.release();
		this.#departure?.();
		this.#departure = whenNone([this.#row], growthIsSeen, () => this.release());
	}
	#keep(space) {
		if (space === this.#space) return;
		this.#space = space;
		const value = layoutPx(space);
		if (this.gap.style.getPropertyValue("--lf-reply-space") !== value) this.gap.style.setProperty("--lf-reply-space", value);
	}
	release() {
		this.#departure?.();
		this.#departure = null;
		this.#space = 0;
		if (this.gap.style.getPropertyValue("--lf-reply-space")) this.gap.style.removeProperty("--lf-reply-space");
	}
};

//#endregion
//#region runtime/thread/summary-ranges.js
function summaryRanges(messages, summaries = []) {
	const index = new Map(messages.map((message, at) => [message.id, {
		message,
		at
	}]));
	const byStart = /* @__PURE__ */ new Map();
	const covered = /* @__PURE__ */ new Set();
	for (const summary of summaries) {
		const visible = summary.covers.flatMap((id) => index.get(id) ?? []);
		const first = visible.at(0);
		if (!first) continue;
		let last = first.message;
		for (const { message } of visible) {
			covered.add(message.id);
			last = message;
		}
		byStart.set(first.at, {
			summary,
			messages: [first.message, ...visible.slice(1).map(({ message }) => message)],
			last
		});
	}
	const ranges = [];
	let skipThrough = -1;
	for (const [at, message] of messages.entries()) {
		if (at <= skipThrough) continue;
		const range = byStart.get(at);
		if (range) {
			ranges.push(Object.freeze({
				kind: "summary",
				summary: range.summary,
				messages: Object.freeze(range.messages),
				last: range.last
			}));
			skipThrough = at + range.messages.length - 1;
		} else if (!covered.has(message.id)) ranges.push(Object.freeze({
			kind: "message",
			message
		}));
	}
	return Object.freeze(ranges);
}
function withPendingProgress(ranges) {
	const gathered = [];
	for (const range of ranges) {
		const run = gathered.at(-1);
		if (range.kind === "message" && range.message.progress) {
			if (run?.kind === "summary" && run.summary.pending) {
				const messages = [...run.messages, range.message];
				gathered[gathered.length - 1] = Object.freeze({
					kind: "summary",
					summary: Object.freeze({
						...run.summary,
						covers: Object.freeze([...run.summary.covers, range.message.id])
					}),
					messages: Object.freeze(messages),
					last: range.message
				});
			} else {
				const messages = [range.message];
				gathered.push(Object.freeze({
					kind: "summary",
					summary: Object.freeze({
						id: `progress:${range.message.id}`,
						covers: Object.freeze([range.message.id]),
						pending: true
					}),
					messages: Object.freeze(messages),
					last: range.message
				}));
			}
		} else gathered.push(range);
	}
	return Object.freeze(gathered);
}
function workingPlace(ranges, position) {
	const at = ranges.findLastIndex((range) => range.kind === "message" ? range.message.sequence <= position : range.messages.some((message) => message.sequence <= position));
	if (at < 0) throw new Error(`The working message at ${position} precedes every transcript range`);
	return at;
}

//#endregion
//#region runtime/thread/transcript.js
const MESSAGE_NAMES = [
	"data-message",
	"data-event",
	"data-attempt"
];
function workingView(working, controls = nothing, observe = null) {
	return html`<div class="lf-thread-working-head">
      ${working.who ? html`<b>${working.who}</b>` : nothing}
      ${working.timestamp || working.condition ? html`<span class="lf-msg-meta"
              >${working.timestamp ? html`<time datetime=${working.timestamp}>${working.age}</time>` : nothing}
              ${working.condition ? voiced(working.condition) : nothing}</span
            >` : nothing}
      ${controls}
    </div>
    <div class="lf-thread-working-words" ${observe ? ref(observe) : nothing}>
      ${working.words}
    </div>`;
}
const stepOf = (message) => Object.freeze({
	who: message.by,
	timestamp: message.timestamp,
	age: message.age,
	words: message.body.plainText.trim().replace(/\.$/, ""),
	live: false,
	condition: null
});
let nextTranscriptId = 0;
var Transcript = class {
	#commands;
	#messageCommands;
	#repaint;
	#home;
	#model = null;
	#rows = [];
	#messages = /* @__PURE__ */ new Map();
	#facing = /* @__PURE__ */ new Map();
	#stopWorkingExposure = null;
	#pendingCovers = /* @__PURE__ */ new Map();
	#pendingOpen = false;
	#folding = /* @__PURE__ */ new Map();
	#expandedSummaries = /* @__PURE__ */ new Set();
	#id = ++nextTranscriptId;
	#named = 0;
	constructor({ commands, messageCommands, repaint, home }) {
		this.#commands = commands;
		this.#messageCommands = messageCommands;
		this.#repaint = repaint;
		this.#home = home;
		this.node = document.createElement("div");
		this.node.className = "lf-thread-transcript";
	}
	#unfold(node) {
		const id = node.dataset.lfSummary;
		if (!id || this.#expandedSummaries.has(id)) return;
		this.#expandedSummaries.add(id);
		this.#repaint();
	}
	get views() {
		return (this.#model?.messages ?? []).flatMap(({ key }) => this.#messages.get(key) ?? []);
	}
	messageNode(key) {
		return this.#messages.get(key)?.node ?? null;
	}
	leaving(model) {
		const wanted = new Set(model.messages.map(({ key }) => key));
		return [...this.#messages].flatMap(([key, { node }]) => wanted.has(key) || !node.isConnected ? [] : [node]);
	}
	summaryNode(id) {
		return this.node.querySelector(`:scope > [data-summary-id="${CSS.escape(id)}"]`);
	}
	get foot() {
		return [...this.node.children].findLast((node) => showsContents(node)) ?? null;
	}
	get progressOpen() {
		return this.#pendingOpen;
	}
	newsMoves({ news, changed, folds }, { followed = null } = {}) {
		return [...[...changed].flatMap((key) => [this.#facing.get(key), this.messageNode(key)]), (news.appended || news.settled || news.working) && this.foot].some((node) => node && node !== followed && growthAfterIsSeen(node)) || [...folds.messages.map((key) => this.messageNode(key)), ...folds.summaries.map((id) => this.summaryNode(id))].some((node) => node && growthIsSeen(node));
	}
	expandAround(id) {
		const folded = this.#model?.summaries.find(({ covers }) => covers.includes(id));
		if (folded) this.#expandedSummaries.add(folded.id);
	}
	present(model, { arrived = false, appends = false, notice = null } = {}) {
		const prior = this.#model;
		const currentLocation = focused();
		const priorSummaries = new Set(prior?.summaries.map(({ id }) => id) ?? []);
		if (prior && model.summaries.some(({ id }) => !priorSummaries.has(id))) {
			const heldMessage = prior.messages.find(({ key }) => this.#messages.get(key)?.node.contains(currentLocation))?.id;
			const clips = /* @__PURE__ */ new Map();
			const beingRead = new Set(prior.messages.filter(({ key }) => {
				const node = this.#messages.get(key)?.node;
				return node?.isConnected && seenRect(node, clips);
			}).map(({ id }) => id));
			for (const summary of model.summaries) {
				if (priorSummaries.has(summary.id)) continue;
				if (summary.covers.some((id) => id === heldMessage) || summary.covers.some((id) => beingRead.has(id))) this.#expandedSummaries.add(summary.id);
			}
		}
		this.#model = model;
		const wanted = new Set(model.messages.map((message) => message.key));
		for (const [key, fold] of this.#folding) if (wanted.has(key)) this.#endFold(key, fold, false);
		for (const [key, view] of this.#messages) {
			if (wanted.has(key)) continue;
			const { node } = view;
			if (motionPlays() && !this.#folding.has(key) && node.parentNode === this.node && showsContents(node)) {
				const names = MESSAGE_NAMES.map((name) => [name, node.getAttribute(name)]);
				for (const [name] of names) node.removeAttribute(name);
				node.inert = true;
				this.#folding.set(key, {
					node,
					names,
					played: null
				});
			}
			view.retire();
		}
		const drawnMessages = model.messages.map((message) => {
			let view = this.#messages.get(message.key);
			if (!view) {
				view = new MessageView(this.#messageCommands);
				this.#messages.set(message.key, view);
				const { node } = view;
				node.addEventListener("beforematch", () => this.#unfold(node));
			}
			return {
				...message,
				reading: message,
				view
			};
		});
		const summarized = summaryRanges(drawnMessages, model.summaries);
		const describedRanges = model.resolved ? summarized : withPendingProgress(summarized);
		const summaries = new Set(describedRanges.flatMap((range) => range.summary ? [range.summary.id] : []));
		const successors = /* @__PURE__ */ new Map();
		for (const [id, covers] of this.#pendingCovers) successors.set(id, describedRanges.filter((range) => range.kind === "summary").filter((range) => range.summary.covers.some((covered) => covers.includes(covered))));
		for (const id of [...this.#expandedSummaries]) for (const range of successors.get(id) ?? []) this.#expandedSummaries.add(range.summary.id);
		for (const id of this.#expandedSummaries) if (!summaries.has(id)) this.#expandedSummaries.delete(id);
		this.#pendingCovers = new Map(describedRanges.filter((range) => range.kind === "summary").filter((range) => range.summary.pending).map((range) => [range.summary.id, range.summary.covers]));
		const currentLocationToggle = this.node.querySelector(".lf-summary-expand:focus");
		const rangeState = describedRanges.map((range) => {
			if (range.kind === "message") return range;
			const forced = !range.summary.pending && Boolean(range.summary.protected.length);
			return {
				...range,
				expanded: forced || this.#expandedSummaries.has(range.summary.id),
				forced,
				requiredText: "Messages kept open · current work"
			};
		});
		const pendingRanges = rangeState.filter((range) => range.kind === "summary").filter((range) => range.summary.pending);
		const spoke = model.messages.findLastIndex(({ author }) => author === "user");
		this.#pendingOpen = pendingRanges.some((range) => range.expanded);
		const lead = rangeState.find((range) => range.kind === "message")?.message ?? model.messages[0];
		const workingAt = model.working ? workingPlace(rangeState, model.working.position) : -1;
		const dated = /* @__PURE__ */ new Set();
		let above = null;
		for (const [at, range] of rangeState.entries()) {
			const shown = range.kind === "message" ? [range.message] : range.expanded ? range.messages : [];
			if (range.kind !== "message") above = null;
			for (const message of shown) {
				if (message.age !== above) dated.add(message.key);
				above = message.age;
			}
			if (range.summary?.pending || at === workingAt) above = null;
		}
		for (const message of drawnMessages) {
			const view = message.view;
			view.present(message.reading, {
				arrived,
				dated: dated.has(message.key),
				headerControls: notice && message.key === lead?.key ? notice : nothing
			});
			keeps(view.node, "data-lf-append-tail", message.provisional && message.reading === model.messages.at(-1) ? "" : null);
		}
		const placed = (message, summary = null, folded = false) => {
			const node = message.view.node;
			keeps(node, "data-lf-summary", summary);
			keepsHidden(node, folded ? "until-found" : false);
			return node;
		};
		const feet = /* @__PURE__ */ new Map();
		const transcript = [];
		const facing = /* @__PURE__ */ new Map();
		const messageRow = (node, key) => ({
			key: `message:${key}`,
			body: node
		});
		const face = (id, reading, controls, feedback = null) => {
			const row = {
				key: `face:${id}`,
				body: (tail) => html`<div
            class="lf-thread-working"
            data-face=${id}
            aria-live="polite"
            data-lf-live=${reading.live ? "" : nothing}
            data-lf-append-tail=${tail ? "" : nothing}
          >
            ${workingView(reading, controls, feedback ? (node) => {
					if (!node) return;
					this.#stopWorkingExposure = this.#commands.read.observeFeedback(node, {
						...feedback,
						presentation_kind: "working_words",
						surface: model.surface
					});
				} : null)}
          </div>`
			};
			transcript.push(row);
			return row;
		};
		for (const [at, range] of rangeState.entries()) {
			if (range.kind === "message") transcript.push(messageRow(placed(range.message), range.message.key));
			else {
				const id = range.summary.id;
				const covered = range.messages.map((message) => placed(message, id, !range.expanded));
				for (const node of covered) node.id ||= `lf-msg-${this.#id}-${++this.#named}`;
				const anchor = `--lf-fold-${this.#id}-${CSS.escape(id)}`;
				transcript.push({
					key: `summary:${id}`,
					body: this.#checkpoint(range, covered, anchor)
				}, ...range.messages.map((message) => messageRow(message.view.node, message.key)));
				feet.set(covered.at(-1), `${anchor}-foot`);
			}
			const hosted = at === workingAt ? model.working : null;
			if (range.summary?.pending) {
				const id = range.summary.id;
				const kept = range.messages.length > 1 && model.messages.indexOf(range.messages[0].reading) < spoke;
				const row = face(id, hosted ?? stepOf(range.last), kept ? this.#summaryToggle([range], true) : nothing, hosted?.feedback ?? null);
				facing.set(range.last.key, row);
			} else if (hosted) face("working", hosted, nothing, hosted.feedback);
		}
		for (const { node } of this.#messages.values()) {
			const foot = feet.get(node);
			if (foot) node.style.setProperty("--lf-fold-foot", foot);
			else node.style.removeProperty("--lf-fold-foot");
		}
		keeps(this.node, "data-lf-reflow", appends ? "append" : null);
		for (const row of transcript) row.tail = row === transcript.at(-1);
		this.#rows = this.#withFolds(transcript);
		this.#stopWorkingExposure?.();
		this.#stopWorkingExposure = null;
		this.#paint();
		const faceNode = (row) => this.node.querySelector(`:scope > [data-face="${CSS.escape(row.key.slice(5))}"]`);
		this.#facing = new Map([...facing].map(([key, row]) => [key, faceNode(row)]));
		for (const [key, fold] of this.#folding) {
			if (fold.played) continue;
			fold.played = foldBlock(fold.node);
			if (!fold.played) {
				this.#endFold(key, fold, true);
				continue;
			}
			fold.played.finished.then(() => {
				if (this.#folding.get(key) === fold) this.#endFold(key, fold, true);
			}, () => {});
		}
		if (!currentLocationToggle || currentLocationToggle.isConnected) return null;
		const toggleFor = (id) => this.node.querySelector(`.lf-summary-expand[data-summary-toggle="${CSS.escape(id)}"]`);
		const succeeded = currentLocationToggle.dataset.summaryToggle;
		return [...succeeded ? [succeeded, ...(successors.get(succeeded) ?? []).map(({ summary }) => summary.id)] : []].map(toggleFor).find(Boolean) ?? null;
	}
	#withFolds(rows) {
		if (!this.#folding.size) return rows;
		const staying = new Set(rows.map(({ key }) => key));
		const after = /* @__PURE__ */ new Map();
		let anchor = null;
		for (const row of this.#rows) if (row.key.startsWith("message:") && this.#folding.has(row.key.slice(8))) after.set(anchor, [...after.get(anchor) ?? [], row]);
		else if (staying.has(row.key)) anchor = row.key;
		return [...after.get(null) ?? [], ...rows.flatMap((row) => [row, ...after.get(row.key) ?? []])];
	}
	#endFold(key, fold, removed) {
		this.#folding.delete(key);
		if (removed) {
			this.#rows = this.#rows.filter((row) => row.key !== `message:${key}`);
			this.#paint();
		} else fold.played?.cancel();
		fold.node.inert = false;
		for (const [name, value] of fold.names) if (value !== null) fold.node.setAttribute(name, value);
	}
	#paint() {
		render$1(repeat(this.#rows, (row) => row.key, (row) => typeof row.body === "function" ? row.body(!!row.tail) : row.body), this.node);
	}
	#checkpoint(range, covered, anchor) {
		const progress = Boolean(range.summary.pending);
		return html`<section
      class="lf-thread-checkpoint"
      data-summary-id=${range.summary.id}
      data-expanded=${range.expanded}
      ?hidden=${progress && !range.expanded}
      aria-owns=${covered.map(({ id }) => id).join(" ")}
      style=${`--lf-fold-head: ${anchor}; --lf-fold-foot: ${anchor}-foot;`}
    >
      ${progress ? nothing : html`<div class="lf-summary-checkpoint">
              <div class="lf-summary-header">
                <div class="lf-summary-label">${range.summary.label}</div>
                ${range.forced ? nothing : this.#summaryToggle([range])}
              </div>
              ${range.summary.text ? html`<div
                      class="lf-summary-text"
                      .innerHTML=${renderMarkdown(range.summary.text)}
                    ></div>` : nothing}
              ${range.forced ? html`<div class="lf-summary-required">${range.requiredText}</div>` : nothing}
            </div>`}
      ${progress && range.forced ? html`<div class="lf-summary-required">${range.requiredText}</div>` : nothing}
    </section>`;
	}
	#summaryToggle(ranges, progress = false) {
		const ids = [ranges[0].summary.id, ...ranges.slice(1).map((range) => range.summary.id)];
		const expanded = ranges.every((range) => range.expanded);
		const count = ranges.reduce((total, range) => total + range.messages.length, 0);
		const subject = `${count} ${progress ? "progress" : "earlier"} message${count === 1 ? "" : "s"}`;
		const label = `${expanded ? "Hide" : "Show"} ${subject}`;
		return html`<button
      type="button"
      ${offeredAction("inline", `lf-thread-disclosure lf-disclosure-marker lf-summary-expand${progress ? " lf-progress-expand" : ""}`)}
      data-summary-toggle=${ids[0]}
      aria-expanded=${String(expanded)}
      aria-controls=${ranges.flatMap((range) => range.messages.map(({ key }) => this.messageNode(key)?.id)).filter(Boolean).join(" ")}
      @click=${() => this.#setSummaryExpanded(ids, !expanded)}
    >
      <span data-room=${`Show ${subject}`}><span>${label}</span></span>
    </button>`;
	}
	#setSummaryExpanded(ids, expanded) {
		for (const id of ids) if (expanded) this.#expandedSummaries.add(id);
		else this.#expandedSummaries.delete(id);
		this.#repaint();
		const toggle = this.node.querySelector(`.lf-summary-expand[data-summary-toggle="${CSS.escape(ids[0])}"]`);
		if (toggle) {
			focusDestination(toggle, "return");
			scrollThreadIntoView(this.#home(), toggle, "instant");
		}
	}
	commit(model) {
		const wanted = new Set(model.messages.map((message) => message.key));
		for (const [key, view] of this.#messages) if (wanted.has(key)) view.commit();
		else {
			view.retire();
			this.#messages.delete(key);
		}
	}
	retire() {
		this.#stopWorkingExposure?.();
		this.#stopWorkingExposure = null;
		for (const [key, fold] of this.#folding) {
			fold.played?.cancel();
			this.#endFold(key, fold, true);
		}
		for (const view of this.#messages.values()) view.retire();
	}
};

//#endregion
//#region runtime/thread/thread-card.js
function quoteReading(thread, anchors) {
	const placement = anchors.placedAt(thread.id);
	const rewritten = thread.rewritten_from;
	const quoted = threadPassage(thread);
	const label = anchorLabel(quoted, thread.root.about);
	if (!label) return null;
	const anchored = Boolean(thread.anchor) || Boolean(thread.detached_from);
	const found = !thread.detached_from && placement != null;
	const outdated = anchored && placement?.status === "outdated";
	const changed = Boolean(rewritten) || Boolean(quoted?.quote && placement?.datumElement && !placement.exact);
	return Object.freeze({
		label,
		words: quoted?.quote ?? null,
		anchored,
		found,
		outdated,
		changed,
		localReading: Boolean(quoted?.quote) && placement?.kind !== "passage",
		title: !anchored ? null : found ? outdated ? "This comment refers to an earlier data revision" : changed ? "These words have changed since; jump to their current item" : quoted?.quote && placement.kind !== "passage" ? "Jump to the quoted item's current location" : "Jump to this passage" : thread.detached_from ? "This passage is no longer in the version shown" : "This passage can't be identified in the version shown"
	});
}
const STOPPED = /* @__PURE__ */ new Set([
	"ended",
	"stale",
	"interrupted"
]);
const words = (header) => {
	return [...header.querySelectorAll(":scope > :not(.lf-msg-control-room)")];
};
function workingMessage(thread, messages) {
	if (thread.resolved || messages.at(-1)?.provisional) return null;
	const covered = new Set(thread.summaries.flatMap(({ covers }) => covers));
	const pending = messages.filter((message) => message.progress && !covered.has(message.id));
	const lastProgress = pending.at(-1);
	const workflows = thread.workflows;
	const running = workflows.find((workflow) => !workflow.condition && ["working", "replying"].includes(workflow.stage));
	const runningLine = running && hasWorkflowLine(running) ? running : null;
	const stopped = workflows.find((workflow) => workflow.condition !== null && STOPPED.has(workflow.condition.kind) && Boolean(workflow.detail));
	const todo = thread.todos.find((todo) => todo.running !== null);
	const progressStep = lastProgress ? {
		words: lastProgress.body.plainText,
		position: lastProgress.sequence,
		live: Boolean(running),
		condition: null,
		agent: running?.agent
	} : null;
	const step = runningLine?.detail ? {
		words: runningLine.detail,
		position: runningLine.detail_seq,
		live: true,
		condition: null,
		agent: runningLine.agent
	} : running ? progressStep : todo ? {
		words: todo.running.text,
		position: todo.running.seq,
		live: true,
		condition: null,
		agent: null
	} : stopped ? {
		words: stopped.detail,
		position: stopped.detail_seq,
		live: false,
		condition: workflowWord(stopped, agentName()),
		agent: stopped.agent
	} : progressStep;
	if (!step || !step.words || !pending.length && !step.live && !step.condition) return null;
	const { words, position, live, condition, agent } = step;
	const agentMessage = messages.findLast((message) => message.author === "agent");
	const work = runningLine?.detail ? runningLine : !running && !todo ? stopped : null;
	const progress = !work && (running || !todo && !stopped) ? pending.at(-1) : null;
	const timestamp = work?.ts ?? progress?.timestamp ?? null;
	const feedback = work?.input ? {
		input_id: work.input,
		reply_id: null,
		reply_kind: "work"
	} : progress ? {
		reply_id: progress.id,
		attempt: progress.attempt,
		reply_kind: "progress"
	} : null;
	return Object.freeze({
		who: work?.agent || progress?.by || agent || agentMessage?.by || "Agent",
		position,
		timestamp,
		age: timestamp ? ago(timestamp) : null,
		words: words.trim().replace(/\.$/, ""),
		feedback,
		live,
		condition
	});
}
function threadTodos(todos, done) {
	if (!todos.length) return nothing;
	return html`<ul class="lf-thread-todos">
    ${todos.map((todo) => html`<li class="lf-thread-todo">
          <span class="lf-thread-todo-title">To-do · ${todo.title}</span
          ><button
            ${offeredAction("symbol", "", void 0, { action: "done" })}
            @click=${() => done(todo.id)}
          ></button>
        </li>`)}
  </ul>`;
}
function threadReading(thread, surface, commands) {
	const resolved = Boolean(thread.resolved);
	const kind = resolved ? "unresolve" : "resolve";
	const word = resolved ? "Reopen" : "Resolve";
	const label = resolved ? word : "Resolve thread";
	const attention = threadAttention(thread, agentName());
	const asking = new Set(thread.obligations.filter((item) => item.next_actor === "user" && answeredInWords(item)).map((item) => item.message));
	const openTodos = new Set(thread.todos.map(({ id }) => id));
	const leaves = (message) => asking.has(message.id) ? leafSays("Waiting on me") : message.todo && openTodos.has(message.id) ? todoWord(null) : null;
	const presented = new Set(thread.msgs.map(({ id }) => id));
	const messages = turns(thread).filter((message) => message.completed_by === void 0 || !presented.has(message.completed_by)).map((message) => messageReading(message, {
		authoredRank: commands.authoredRank ?? (surface === "margin" ? 2 : 1),
		reactions: surface === "outlet" ? message.reactions : null,
		workflows: message.workflows,
		leaves: leaves(message)
	}));
	const summary = threadSummary(thread);
	return Object.freeze({
		key: threadKey(thread),
		summary,
		recency: summary.latest ? Object.freeze({
			short: shortAgo(summary.latest),
			long: ago(summary.latest)
		}) : null,
		id: thread.id,
		attempt: thread.root.attempt ?? null,
		surface,
		resolved,
		attention,
		resolvedBy: thread.resolved?.author === "agent" ? `✓ Resolved by ${thread.resolved.agent}` : "",
		settlement: Object.freeze({
			kind,
			word,
			label
		}),
		todos: Object.freeze(thread.userTodos.map(({ id, title }) => Object.freeze({
			id,
			title
		}))),
		summaries: Object.freeze(thread.summaries),
		messages: Object.freeze(messages),
		working: workingMessage(thread, messages),
		source: thread,
		reread: (held) => threadReading(held, surface, commands)
	});
}
function wordsWidth(node) {
	if (!node) return 0;
	const range = document.createRange();
	range.selectNodeContents(node);
	return range.getBoundingClientRect().width;
}
var ThreadView = class {
	#commands;
	#messageCommands;
	#rewrites;
	#shown;
	get #model() {
		return this.#shown.peek();
	}
	set #model(model) {
		this.#shown.value = model;
	}
	#transcript;
	#reply = null;
	#settlesAt = null;
	#marginControls = null;
	#news = newsNotice();
	#continuity;
	#received = null;
	#headerSlot = null;
	#observedHeader = null;
	#sizes = sizeObserver(() => this.#retainHeaderSlot());
	#marginNews = sizeObserver(() => nextRender(() => this.#fitMarginNews()));
	constructor(commands, model) {
		this.#shown = Z(model);
		this.#commands = commands;
		this.#rewrites = threadRewrites({
			views: () => this.#transcript.views,
			paint: () => this.repaint(),
			box: () => this.node.querySelector(SAY_BOX),
			home: () => this.node,
			opening: (id) => {
				this.#showNews();
				this.#transcript.expandAround(id);
			},
			landInThread: commands.reply.landInThread,
			landSent: commands.reply.landSent
		});
		this.#messageCommands = {
			...commands,
			reaction: {
				...commands.reaction,
				pressed: () => this.#showNews()
			},
			edit: this.#rewrites.edit
		};
		this.node = document.createElement("div");
		this.#transcript = new Transcript({
			commands,
			messageCommands: this.#messageCommands,
			repaint: () => this.repaint(),
			home: () => this.node
		});
		this.#continuity = new ReplyContinuity(this.node);
		this.node.tabIndex = -1;
		this.node.classList.add("lf-page-thread", "lf-ui");
		this.node.dataset.lfRuntime = "";
		generatedElement(this.node, { says: false });
		this.node.dataset.lfOffer = "";
	}
	setMarginControls(controls) {
		this.#marginControls = controls;
	}
	get model() {
		return this.#model;
	}
	repaint() {
		if (this.#received) this.#paint(this.#received);
	}
	#foldedInto = null;
	#retirement = null;
	setFoldedInto(group, retirement = null) {
		this.#foldedInto = group;
		this.#retirement = retirement;
	}
	get transcript() {
		return this.#transcript.node;
	}
	get #fold() {
		return this.#foldedInto && !this.#foldedInto.open ? this.#foldedInto : null;
	}
	setSettlesAt(place) {
		this.#settlesAt = place;
	}
	get #foot() {
		return this.#fold ? null : this.#transcript.foot;
	}
	get #settlementRow() {
		if (this.#fold) return null;
		return this.node.querySelector(":scope > .lf-thread-reply");
	}
	#messageNode(key) {
		return this.#fold ? null : this.#transcript.messageNode(key);
	}
	ownsMessage(id) {
		return this.#model?.id === id || this.#model?.messages.some((message) => message.id === id);
	}
	newsMoves({ news, changed, joined, folds, appendedAtEnd, footFold }) {
		const lands = news.settled ? this.#settlesAt?.() : null;
		if (lands && growthIsSeen(lands)) return true;
		if (this.#fold) return false;
		const pinned = pinnedReply(this.#reply?.node);
		const foot = footFold && !folds.messages.some((key) => currentLocationTouches(this.#messageNode(key)));
		if (this.#model?.surface === "margin") {
			if (news.settled) return false;
			const last = this.#model.messages.at(-1);
			const list = this.#transcript.node;
			const follows = list.scrollHeight > list.clientHeight + .5 && atScrollEnd(list);
			const atEnd = (!news.appended || appendedAtEnd) && !news.summaries && [...changed].every((key) => key === last?.key && (last.provisional || follows)) && (foot || !folds.messages.length && !folds.summaries.length);
			return growthIsSeen(this.node) && (!atEnd || Boolean(this.#marginControls?.anchor.newsMoves(joined)));
		}
		const followed = pinned && !news.settled ? this.#foot : null;
		return this.#transcript.newsMoves({
			news,
			changed,
			folds
		}, { followed }) || Boolean(news.settled && this.#settlementRow && growthIsSeen(this.#settlementRow));
	}
	#outside(model) {
		return [replyIsEditing(model.key), threadHoldsDraft(model.key, model.messages.map(({ id }) => id))];
	}
	shows(model) {
		const prior = this.#received;
		const drawnWith = this.#drawnWith;
		if (!prior || !drawnWith) return false;
		if (this.#model?.news) return false;
		const { reread: _priorReread, ...was } = prior;
		const { reread: _reread, ...now } = model;
		const outside = this.#outside(model);
		return share(was, now) === was && outside.every((part, index) => part === drawnWith[index]);
	}
	#drawnWith = null;
	present(model, options = {}) {
		return this.#paint(model, options, true);
	}
	#paint(model, _options = {}, published = false) {
		const prior = this.#received ? this.#model : null;
		this.#received = model;
		this.#drawnWith = this.#outside(model);
		if (model.news && !prior?.news) this.#retainHeaderSlot({ observe: false });
		const bodyPlace = published ? this.#continuity?.before([...this.#transcript.views.filter((view) => view.editing).map(({ node }) => node), ...this.#transcript.leaving(model)]) : null;
		const restoreFocus = holdFocus(this.node);
		this.#model = model;
		const marginControls = model.surface === "margin" ? this.#marginControls : null;
		if (marginControls && prior) marginControls.anchor.presented(threadChange(prior, model)?.joined);
		const notice = this.#news;
		if (model.news) notice.set(model.news);
		const news = model.news ? notice.node : nothing;
		keeps(this.node, "data-thread", model.id);
		keeps(this.node, "data-resolved", model.resolved);
		keeps(this.node, "data-attempt", model.attempt || null);
		keeps(this.node, "role", "group");
		keeps(this.node, "aria-label", `Thread, ${model.summary.topic}`);
		const settlement = model.settlement ? this.#settlement(model, model.settlement) : nothing;
		const threadActions = marginControls || model.settlement || model.news ? html`<span class="lf-thread-meta-actions">
            ${marginControls ? news : nothing} ${marginControls?.nav ?? nothing}
            ${marginControls?.expand ?? nothing}${settlement}
            ${marginControls?.close ?? nothing}
          </span>` : nothing;
		const handedOn = this.#transcript.present(model, {
			arrived: Boolean(prior),
			appends: model.surface === "margin"
		});
		this.#reply ??= this.#createReply(model);
		keeps(notice.node, "data-lf-reflow", marginControls ? null : "text");
		const body = html`
      ${threadTodos(model.todos, (id) => this.#commands.todos.done(id))}${this.#transcript.node}
      ${threadActions !== nothing ? marginControls ? html`<div class="lf-margin-thread-controls">${threadActions}</div>` : html`${news}
                <div class="lf-thread-controls" data-lf-reflow="text">
                  ${threadActions}
                </div>` : nothing}
    `;
		render$1(html`
        ${model.surface === "margin" ? body : html`<div class="lf-thread-content">${body}</div>`}
        ${this.#continuity?.gap ?? nothing} ${this.#reply.node}
      `, this.node);
		if (!marginControls && model.news) measure(this.node, () => this.#retainHeaderSlot());
		else this.#releaseHeaderSlot();
		if (marginControls && model.news) measure(this.node, () => this.#watchMarginNews());
		else this.#releaseMarginNews();
		this.#continuity?.after(bodyPlace);
		if (prior && Boolean(prior.resolved) !== Boolean(model.resolved)) this.#reply.sync();
		restoreFocus?.(handedOn ? () => (focusDestination(handedOn, "return"), true) : () => this.#commands.landInThread(this.node.querySelector(SAY_BOX) ?? this.node));
		return this.node;
	}
	#fitMarginNews() {
		const notice = this.#news.node;
		const heads = [];
		for (const head of this.node.querySelectorAll(".lf-thread-transcript .lf-msg-head")) {
			if (!head.checkVisibility()) continue;
			const style = getComputedStyle(head);
			const name = head.querySelector(":scope > b");
			const time = head.querySelector(":scope > .lf-msg-meta > time");
			const room = head.querySelector(":scope > .lf-msg-control-room");
			const controls = room?.querySelector(":scope > .lf-msg-controls")?.getBoundingClientRect().width ?? 0;
			const held = room && getComputedStyle(room).minInlineSize !== "0px" ? controls : 0;
			const need = parseFloat(style.paddingInlineStart) + parseFloat(style.paddingInlineEnd) + controls + wordsWidth(name) + (name && time ? parseFloat(style.columnGap) : 0) + wordsWidth(time);
			heads.push({
				name,
				need,
				spare: head.getBoundingClientRect().width - need,
				yields: controls - held + wordsWidth(time)
			});
		}
		if (!heads.length || !notice.isConnected) {
			this.#clearMarginNews();
			return;
		}
		const width = notice.getBoundingClientRect().width;
		const spare = Math.min(...heads.map((head) => head.spare));
		notice.style.setProperty("--lf-news-room", roomPx(Math.max(0, width + spare)));
		const taken = notice.getBoundingClientRect().width - width;
		for (const { name, spare, yields } of heads) {
			if (!name) continue;
			const shown = wordsWidth(name) + Math.min(0, spare - taken + yields);
			keeps(name, "data-lf-nameless", shown < parseFloat(getComputedStyle(name).fontSize) ? "" : null);
		}
	}
	#watchMarginNews() {
		this.#marginNews.disconnect();
		for (const time of this.node.querySelectorAll(".lf-thread-transcript .lf-msg-head > .lf-msg-meta > time")) this.#marginNews.observe(time);
		this.#fitMarginNews();
	}
	#releaseMarginNews() {
		this.#marginNews.disconnect();
		this.#clearMarginNews();
	}
	#clearMarginNews() {
		this.#news.node.style.removeProperty("--lf-news-room");
		for (const name of this.node.querySelectorAll(".lf-thread-transcript .lf-msg-head > b[data-lf-nameless]")) keeps(name, "data-lf-nameless", null);
	}
	#releaseHeaderSlot() {
		if (this.#observedHeader) this.#sizes.unobserve(this.#observedHeader);
		this.#observedHeader = null;
		this.#releaseHeaderItems();
		this.#news.node.removeAttribute("data-room");
		this.#news.node.style.removeProperty("--lf-thread-news-start");
		this.#news.node.style.removeProperty("--lf-thread-news-visible-end");
	}
	#releaseHeaderItems() {
		for (const { node } of this.#headerSlot?.items ?? []) {
			node.classList.toggle("lf-held-header-item", false);
			node.style.removeProperty("--lf-held-header-width");
		}
		this.#headerSlot = null;
	}
	#retainHeaderSlot({ observe = true } = {}) {
		const news = this.#model?.news;
		if (observe && !news) {
			this.#releaseHeaderSlot();
			return;
		}
		const first = this.node.querySelector(":scope > .lf-thread-content")?.querySelector(":scope > .lf-thread-transcript > :nth-child(1 of .lf-msg, .lf-thread-checkpoint)");
		const header = first?.querySelector(":scope > .lf-summary-checkpoint > .lf-summary-header") ?? first?.querySelector(":scope > .lf-msg-head");
		if (!header) {
			this.#releaseHeaderSlot();
			return;
		}
		const box = header.getBoundingClientRect();
		if (!box.width) return;
		const allocates = header.classList.contains("lf-msg-head");
		if (observe && this.#observedHeader !== header) {
			if (this.#observedHeader) this.#sizes.unobserve(this.#observedHeader);
			this.#sizes.observe(header);
			this.#observedHeader = header;
		}
		let slot = this.#headerSlot;
		if (!slot || slot.header !== header || slot.boxWidth !== box.width || !news) {
			const resizing = allocates && slot?.header === header;
			let reading = header;
			if (resizing) {
				reading = header.cloneNode(true);
				Object.assign(reading.style, {
					position: "absolute",
					visibility: "hidden",
					inlineSize: layoutPx(box.width),
					margin: "0",
					anchorName: "none"
				});
				for (const node of words(reading)) {
					node.classList.toggle("lf-held-header-item", false);
					node.style.removeProperty("--lf-held-header-width");
				}
				header.after(reading);
			} else this.#releaseHeaderItems();
			const originals = words(header)[Symbol.iterator]();
			const items = [];
			for (const measured of words(reading)) {
				const original = originals.next();
				if (original.done) break;
				items.push({
					node: original.value,
					width: measured.getBoundingClientRect().width
				});
			}
			if (resizing) reading.remove();
			slot = {
				header,
				items,
				boxWidth: box.width,
				held: observe
			};
			this.#headerSlot = slot;
			for (const { node, width } of allocates ? items : []) {
				if (!observe && node.classList.contains("lf-msg-meta")) continue;
				node.classList.toggle("lf-held-header-item", true);
				node.style.setProperty("--lf-held-header-width", layoutPx(width));
			}
		}
		if (observe && !slot.held) {
			for (const item of allocates ? slot.items : []) {
				if (item.node.classList.contains("lf-msg-meta")) item.width = Math.max(item.width, item.node.getBoundingClientRect().width);
				item.node.classList.toggle("lf-held-header-item", true);
				item.node.style.setProperty("--lf-held-header-width", layoutPx(item.width));
			}
			slot.held = true;
		}
		const notice = this.#news.node;
		const right = Math.max(box.left, ...slot.items.map(({ node }) => node.getBoundingClientRect().right));
		notice.style.setProperty("--lf-thread-news-start", layoutPx(right - box.left));
		if (news) {
			if (!notice.hasAttribute("data-room")) notice.dataset.room = news.text;
			const shown = shownRect(header, /* @__PURE__ */ new Map());
			if (shown) notice.style.setProperty("--lf-thread-news-visible-end", layoutPx(Math.max(0, shown.right - box.left)));
		} else notice.removeAttribute("data-room");
	}
	get progressOpen() {
		return this.#transcript.progressOpen;
	}
	#settlement(model, state) {
		const reopen = state.kind === "unresolve";
		const word = reopen ? "Reopen" : "Resolve";
		const label = reopen && model.resolvedBy ? `${model.resolvedBy} · ${state.label}` : state.label;
		return html`<button
      ${offeredAction("symbol", reopen ? "lf-reopen" : "lf-resolve", label, { action: reopen ? "reopen" : "resolve" })}
      ${commandsOn(`On a thread's ${word} button`, (button) => [{
			id: reopen ? "thread.reopen" : "thread.resolve",
			keys: PRESS,
			title: word.toLowerCase(),
			control: button,
			run: this.#settle
		}])}
    ></button>`;
	}
	#showNews() {
		if (!this.#model?.news) return;
		const restoreFocus = holdFocus(this.node);
		this.#model.news.open();
		restoreFocus?.(this.node);
	}
	#settle = () => {
		const model = this.#model;
		this.#showNews();
		if (!model.resolved) dismissReply(model.key);
		settleThread({
			parent: () => this.#model.id,
			key: model.key,
			resolved: model.resolved,
			prepareLanding: model.surface === "margin" && !model.resolved ? this.#marginControls?.prepareLanding ?? null : this.#prepareThreadLanding,
			...this.#commands.settlement
		}).catch(() => {});
	};
	#prepareThreadLanding = () => {
		const reopening = this.#model.resolved;
		const mayLand = retainUserIntent({
			source: this.node,
			available: () => this.node.isConnected
		});
		return async () => {
			await this.#retirement?.catch(() => {});
			const place = this.#fold?.querySelector(":scope > summary") ?? this.node;
			if (!mayLand() || !currentLocationIn(place)) return false;
			if (reopening) this.#commands.landInThread(this.node.querySelector(SAY_BOX) ?? this.node);
			const control = focused();
			if (this.#model.surface !== "margin" && control) scrollThreadIntoView(place, control);
			return true;
		};
	};
	#createReply(model) {
		const commands = this.#commands.reply;
		return createReplyView(model.key, {
			...commands,
			actions: {
				...commands.actions,
				reply: (key, text, options) => {
					const anchor = this.#marginControls?.anchor;
					anchor?.sending(options.attempt);
					const flight = commands.actions.reply(key, text, options);
					if (!flight) anchor?.writing();
					return flight;
				}
			}
		}, () => this.repaint(), {
			hint: () => this.#model?.resolved ? "Reply to reopen" : "Reply",
			editLast: this.#rewrites.editLast,
			sending: () => this.#marginControls?.sending?.()
		});
	}
	commit() {
		this.#transcript.commit(this.#model);
	}
	claimReply(shown) {
		this.#reply?.claim(shown);
	}
	retire() {
		this.#reply?.cancelDictation();
		this.#transcript.retire();
	}
	dispose() {
		this.#sizes.disconnect();
		this.#releaseHeaderSlot();
		this.#marginNews.disconnect();
		this.#continuity?.release();
		this.retire();
		this.#reply?.dispose();
		this.#reply = null;
	}
};

//#endregion
//#region runtime/thread/inline.js
const seats = /* @__PURE__ */ new WeakMap();
const activeSeats = /* @__PURE__ */ new Set();
const EMPTY = Object.freeze({
	threads: Object.freeze([]),
	response: false
});
let activeBatch = null;
var ResolvedThreads = class {
	node = document.createElement("details");
	summary = document.createElement("summary");
	#threads = [];
	constructor(opened) {
		this.node.className = "lf-resolved-threads lf-ui";
		this.node.dataset.lfRuntime = "";
		generatedElement(this.node, { says: false });
		this.node.dataset.lfOffer = "";
		this.summary.className = "lf-resolved-summary lf-disclosure-marker";
		new MutationObserver(() => {
			if (this.node.open) {
				opened();
				for (const thread of this.#threads) thread.news?.open();
			}
		}).observe(this.node, { attributeFilter: ["open"] });
	}
	present(threads, nodes) {
		this.#threads = threads;
		const held = threads.flatMap(({ news }) => news ? [news] : []);
		const total = held.reduce((sum, news) => sum + news.total, 0);
		const notice = total ? newsCount(total) : null;
		render$1(html`Resolved ·
      ${threads.length}${notice ? html` ·
              <span data-lf-news title=${held.map(({ label }) => label).join(" · ")}
                >${notice}</span
              >` : ""}`, this.summary);
		setChildren(this.node, [this.summary, ...nodes]);
	}
};
var ThreadSeat = class {
	#views = /* @__PURE__ */ new Map();
	#resolved = null;
	#folding = /* @__PURE__ */ new Map();
	#settled = /* @__PURE__ */ new Set();
	#place = () => {};
	#model = EMPTY;
	#shown = EMPTY;
	#committed = EMPTY;
	#held = null;
	#notice = null;
	#commands;
	#response = () => null;
	#connected = false;
	#marginControls = null;
	constructor(node, commands) {
		this.node = node;
		this.#commands = commands;
	}
	configure(response, marginControls = null) {
		this.#response = response;
		this.#marginControls = marginControls;
	}
	present(model, batch = activeBatch) {
		if (batch && !batch.seats.has(this)) batch.seats.set(this, holdFocus(this.node));
		const restoreFocus = holdFocus(this.node);
		const currentLocation = focused();
		const restoreBox = this.node.contains(currentLocation) ? holdBox(currentLocation) : () => {};
		const stoodIn = [...this.#views.values()].find(({ node }) => currentLocationIn(node));
		const gathered = this.#resolved && currentLocationIn(this.#resolved.summary) ? [...[...this.#resolved.node.children].slice(1), ...[...this.#folding.values()].map(({ node }) => node)] : [];
		this.#model = model;
		if (model.surface) this.#held ??= new HeldNews(this.node, (key) => this.#views.get(key) ?? null, () => this.present(this.#model));
		const prior = this.#shown;
		const box = model.surface === "page" ? this.#response() : null;
		const row = !!box && prior.response && !box.contains(currentLocation);
		const shown = this.#held ? this.#held.hold(model, { row }) : model;
		let foot = shown.response ? this.#response() : null;
		if (shown.news) {
			this.#notice ??= seatNotice();
			this.#notice.set(shown.news, box);
			foot = this.#notice.node;
		}
		this.#shown = shown;
		const added = shown.threads.filter((thread) => !prior.threads.some(({ key }) => key === thread.key));
		const wanted = new Set(shown.threads.map((thread) => thread.key));
		for (const [key, view] of this.#views) if (!wanted.has(key)) {
			releaseReplies(view.node);
			view.retire();
		}
		const settled = shown.threads.filter((thread) => thread.surface !== "margin" && thread.resolved && (!replyIsEditing(thread.key) || this.#settled.has(thread.key)));
		this.#settled = new Set(settled.map(({ key }) => key));
		if (!settled.length) this.#resolved = null;
		else this.#resolved ??= new ResolvedThreads(() => {
			if (!this.#folding.size) return;
			for (const [key, fold] of this.#folding) this.#stopFold(key, fold);
			this.present(this.#model);
		});
		for (const [key, fold] of this.#folding) if (!settled.some((thread) => thread.key === key) || this.#resolved?.node.open) this.#stopFold(key, fold);
		const resolved = this.#resolved;
		const departing = settled.filter((thread) => {
			const was = prior.threads.find(({ key }) => key === thread.key);
			return was && !was.resolved && !resolved?.node.open && this.#views.get(thread.key)?.node.parentElement === this.node;
		});
		const priorSize = departing.length ? this.node.getBoundingClientRect().height : 0;
		const drawn = shown.threads.map((descriptor) => {
			let view = this.#views.get(descriptor.key);
			if (!view) this.#views.set(descriptor.key, view = new ThreadView(this.#commands, descriptor));
			const resolved = settled.includes(descriptor);
			view.setMarginControls(this.#marginControls);
			view.present(descriptor);
			view.setFoldedInto(resolved ? this.#resolved?.node ?? null : null, this.#folding.get(descriptor.key)?.played?.finished ?? null);
			if (departing.includes(descriptor)) {
				view.node.inert = true;
				this.#folding.set(descriptor.key, {
					node: view.node,
					view,
					played: null
				});
			}
			return {
				descriptor,
				view
			};
		});
		const place = () => {
			const nodes = drawn.flatMap(({ descriptor: thread, view }) => !settled.includes(thread) || this.#folding.has(thread.key) ? [view.node] : []);
			if (resolved) {
				resolved.present(settled, drawn.filter(({ descriptor }) => settled.includes(descriptor) && !this.#folding.has(descriptor.key)).map(({ view }) => view.node));
				nodes.push(resolved.node);
			}
			setChildren(this.node, foot ? [...nodes, foot] : nodes);
		};
		this.#place = place;
		place();
		let immediate = false;
		for (const [key, retirement] of this.#folding) {
			if (retirement.played) continue;
			const played = foldBlock(retirement.node, {
				container: this.node,
				priorSize
			});
			if (!played) {
				this.#folding.delete(key);
				retirement.node.inert = false;
				immediate = true;
				continue;
			}
			retirement.played = played;
			retirement.view.setFoldedInto(resolved?.node ?? null, played.finished);
			played.finished.then(() => {
				if (this.#folding.get(key) !== retirement) return;
				this.#folding.delete(key);
				played.cancel();
				retirement.node.inert = false;
				this.#place();
			}, () => {});
		}
		if (immediate) place();
		const fold = this.#resolved;
		const joins = () => fold?.node.open ? fold.node : null;
		let next = fold?.node ?? null;
		for (const { descriptor, view } of drawn.toReversed()) if (!settled.includes(descriptor)) {
			view.setSettlesAt(joins);
			next = view.node;
		} else {
			const before = next;
			view.setSettlesAt(() => before);
		}
		this.claim();
		const own = added.filter(({ messages }) => messages[0]?.author === "user");
		const start = own.length === 1 ? own[0] : added.length === 1 ? added[0] : null;
		const started = drawn.find(({ descriptor }) => descriptor === start)?.view.node;
		restoreFocus?.(started && (() => this.#commands?.reply.landSent(started)), ...gathered);
		const now = focused();
		const foldedThread = fold && stoodIn && (fold.node.contains(stoodIn.node) || [...this.#folding.values()].some(({ node }) => node === stoodIn.node)) ? stoodIn : null;
		if (fold && foldedThread && !fold.node.open && (!now || now === document.body || currentLocationIn(foldedThread.node) || currentLocationIn(fold.node) && now !== fold.summary)) {
			focusDestination(fold.summary, "return");
			passOn(foldedThread.node, fold.summary);
		}
		restoreBox();
		if (!batch) this.commit();
		return drawn;
	}
	#stopFold(key, { node, played }) {
		this.#folding.delete(key);
		node.inert = false;
		played?.cancel();
	}
	claim() {
		const shown = () => this.node.isConnected;
		for (const [key, view] of this.#views) if (this.#shown.threads.some((thread) => thread.key === key)) view.claimReply(shown);
	}
	commit() {
		this.#committed = this.#model;
		const wanted = new Set(this.#shown.threads.map((thread) => thread.key));
		for (const [key, view] of this.#views) if (wanted.has(key)) view.commit();
		else {
			view.dispose();
			this.#views.delete(key);
		}
		this.#connected ||= this.node.isConnected;
	}
	retain(restoreFocus) {
		this.present(this.#committed);
		restoreFocus?.();
	}
	prune() {
		if (!this.#connected || this.node.isConnected) return false;
		this.#held?.dispose();
		for (const [key, fold] of this.#folding) this.#stopFold(key, fold);
		for (const view of this.#views.values()) view.dispose();
		this.#views.clear();
		return true;
	}
};
function seatFor(host, commands, response = () => null, marginControls = null) {
	let seat = seats.get(host);
	if (!seat) {
		seat = new ThreadSeat(host, commands);
		seats.set(host, seat);
		activeSeats.add(seat);
	}
	seat.configure(response, marginControls);
	return seat;
}
function seatReading(threads, surface, commands, response) {
	return Object.freeze({
		threads: Object.freeze(threads.map((thread) => threadReading(thread, surface, commands))),
		surface,
		response: Boolean(response)
	});
}
function renderThreadSurface(host, threads, commands, response = null) {
	const editor = () => commands.composition.outlet() === host ? commands.composition.node() : null;
	seatFor(host, commands, editor).present(seatReading(threads, "outlet", commands, response));
}
const claimSeatReplies = (host) => seats.get(host)?.claim();
function clearThreadSurface(host) {
	seats.get(host)?.present(EMPTY);
}
function mountFirstMessage(host, editor) {
	setChildren(host, [editor]);
}
function renderSeats(threads, commands) {
	const hosts = document.querySelectorAll(".lf-thread-seat[data-lf-thread-seat]");
	for (const host of hosts) {
		const owner = host.lfThreadSeatOwner;
		const owned = threads.filter((thread) => seatRoot(thread) === owner.id);
		const hold = registry$1[owner.localName]?.["x-thread-seat"]?.hold;
		const response = !owned.length || hold || loadDraft("say:" + owner.id) !== null;
		seatFor(host, commands, () => host.lfFirstMessage ?? null).present(seatReading(owned, "page", commands, response));
	}
}
function renderMarginThread(host, thread, commands, marginControls = null) {
	return seatFor(host, commands, () => null, marginControls).present(seatReading([thread], "margin", commands, false)).filter(({ descriptor }) => descriptor.key === threadKey(thread)).map(({ view }) => ({
		thread: view.node,
		transcript: view.transcript
	}));
}
function beginThreadSeats() {
	activeBatch = { seats: /* @__PURE__ */ new Map() };
	return activeBatch;
}
function commitThreadSeats(batch) {
	if (activeBatch !== batch) return;
	for (const seat of batch.seats.keys()) seat.commit();
	activeBatch = null;
	for (const seat of activeSeats) if (seat.prune()) {
		activeSeats.delete(seat);
		seats.delete(seat.node);
	}
}
function retainThreadSeats(batch) {
	if (activeBatch !== batch) return;
	for (const [seat, restoreFocus] of batch.seats) seat.retain(restoreFocus);
	activeBatch = null;
}

//#endregion
//#region runtime/thread/surfaces.js
const registrations = /* @__PURE__ */ new Map();
let claimedIds = /* @__PURE__ */ new Set();
let renderGeneration = 0;
const ownership = Z(0);
const sameSet = (a, b) => a.size === b.size && [...a].every((item) => b.has(item));
const holdsOut = (id) => [...registrations.values()].some(({ held }) => held?.holds(id));
function update(registration) {
	if (registration.reconcileQueued) return;
	registration.reconcileQueued = true;
	queueMicrotask(() => {
		registration.reconcileQueued = false;
		registration.invalidate();
	});
}
function watchThreadSurfaces(commands) {
	const tags = tagsDeclaring((entry) => entry["x-thread-surface"] === true);
	if (!tags.length) return;
	watchArrivals(tags.join(","), [], {
		arrive(owner) {
			if (registrations.has(owner)) return;
			if (!owner.matches(":defined")) return;
			const outlets = owner.threadOutlets;
			if (typeof outlets !== "function") throw new TypeError(`<${owner.localName}> declares x-thread-surface without threadOutlets`);
			register(owner, (targets, context) => {
				return Reflect.apply(outlets, owner, [targets, context]);
			}, commands, "widget");
		},
		leave(owner) {
			registrations.get(owner)?.handle.unregister();
		}
	});
}
const threadSurface = (owner) => Object.freeze({
	update() {
		const registration = registrations.get(owner);
		if (registration) update(registration);
	},
	open: (node) => registrations.get(owner)?.handle.open(node) ?? false
});
function placePageThreads(owner, render, options) {
	if ([...registrations.values()].some((item) => item.kind === "page")) throw new Error("The document already has a page Thread presentation");
	return register(owner, render, options, "page");
}
function register(owner, render, { invalidate, composition, reveal }, kind) {
	if (!(owner instanceof Element)) throw new TypeError("A Thread presentation needs an Element owner");
	if (registrations.has(owner)) throw new Error(`Thread surface ${owner.localName} registered twice`);
	const stopSide = declareSide((node) => {
		const outlet = [...registration.outlets].find((outlet) => under(node, outlet));
		if (!outlet) return null;
		const thread = closestAcross(node, ".lf-page-thread");
		if (thread && under(thread, outlet)) return registration.placements?.placedAt(thread.getAttribute("data-thread"))?.place ?? null;
		return outlet === composition.outlet() ? registration.placements?.pendingAt()?.place ?? null : null;
	});
	let active = true;
	const registration = {
		render,
		stopSide,
		handle: {
			read: readThreads,
			reveal(key) {
				if (!active) return false;
				const thread = readThreads().threads.find((item) => item.key === key);
				return thread ? reveal(thread.id) : false;
			},
			open(node) {
				if (!active) return false;
				const target = kind === "widget" ? datumAimTarget(node) : aimTargetAt(node);
				if (!target || kind === "widget" && (target.anchor.section !== owner.id || !under(target.element, owner))) throw new TypeError(kind === "widget" ? `Thread surface ${owner.localName} can open only its own projected datum` : "The page Thread presentation needs an addressable source target");
				composition.open(target);
				return true;
			},
			update: () => update(registration),
			unregister() {
				if (!active) return;
				active = false;
				registrations.delete(owner);
				clearRegistration(registration);
				update(registration);
			}
		},
		owner,
		kind,
		invalidate,
		composition,
		outlets: /* @__PURE__ */ new Set(),
		placements: null,
		drawn: /* @__PURE__ */ new Set(),
		held: kind === "widget" ? new HeldArrivals(() => update(registration)) : null,
		heldKeys: /* @__PURE__ */ new Set(),
		reconcileQueued: false,
		cancelRender: () => {}
	};
	registrations.set(owner, registration);
	update(registration);
	return registration.handle;
}
function clearOutlets(outlets) {
	for (const outlet of outlets) {
		clearThreadSurface(outlet);
		outlet.removeAttribute("data-lf-thread-surface");
	}
}
function reportFailure({ owner }, error) {
	reportPageError(error, `thread surface ${owner.localName}#${owner.id} failed`);
}
function releaseOutlets(node) {
	for (const { outlets, composition } of registrations.values()) {
		const outlet = composition.outlet();
		for (const candidate of outlets) if (candidate === outlet && under(candidate, node)) {
			composition.restore();
			break;
		}
	}
}
function clearRegistration(registration) {
	registration.cancelRender();
	registration.stopSide();
	registration.held?.dispose();
	registration.drawn = /* @__PURE__ */ new Set();
	if ([...registration.outlets].some((outlet) => outlet === registration.composition.outlet())) registration.composition.restore();
	clearOutlets(registration.outlets);
	registration.outlets.clear();
}
function validateOutlets({ owner }, byOutlet) {
	for (const outlet of byOutlet.keys()) if (!outlet.isConnected) byOutlet.delete(outlet);
	else if (!under(outlet, owner)) throw new Error(`Thread surface ${owner.localName} returned an outlet outside its presentation owner`);
}
function widgetTarget({ owner }, target) {
	const { anchor, placement } = target;
	return placement?.status === "exact" && !!anchor?.datum && anchor.section === owner.id && placement.datumElement instanceof Element && under(placement.datumElement, owner);
}
function pageTarget(target) {
	return target.placement?.status === "exact" && target.placement.place instanceof Element;
}
function admitTarget(registration, target) {
	return registration.kind === "page" ? pageTarget(target) ? {
		kind: "page",
		target
	} : null : widgetTarget(registration, target) ? {
		kind: "widget",
		target
	} : null;
}
function renderSurfaces(collection, placements, commands) {
	const generation = ++renderGeneration;
	const current = () => generation === renderGeneration;
	for (const registration of registrations.values()) registration.cancelRender();
	const cancel = () => {
		if (!current()) return;
		++renderGeneration;
		for (const registration of registrations.values()) registration.cancelRender();
	};
	const activeComposition = commands.composition.active();
	let prepared = null;
	return {
		completion: prepare().then((plans) => {
			prepared = plans;
		}),
		cancel,
		commit
	};
	async function prepare() {
		const plans = [];
		const ordered = [...registrations.values()].sort((a, b) => Number(a.kind === "page") - Number(b.kind === "page"));
		for (const registration of ordered) {
			const { render, owner } = registration;
			if (registrations.get(owner) !== registration) continue;
			if (!owner.isConnected) {
				registrations.delete(owner);
				clearRegistration(registration);
				continue;
			}
			registration.placements = placements;
			const byOutlet = /* @__PURE__ */ new Map();
			const abort = new AbortController();
			const cancelled = aborted(abort.signal);
			registration.cancelRender = () => abort.abort();
			let compositionOutlet = null;
			const committed = [];
			try {
				const targets = /* @__PURE__ */ new Map();
				for (const thread of collection.threads) {
					if (registration.kind === "page" ? holdsOut(thread.id) : thread.anchor?.section !== owner.id) continue;
					const placement = placements.placedAt(thread.id);
					const admitted = admitTarget(registration, {
						anchor: thread.anchor,
						placement,
						thread
					});
					if (admitted) targets.set(thread.key, admitted);
				}
				const held = registration.held?.hold([...targets.values()].flatMap(({ kind, target }) => kind === "widget" ? [{
					thread: target.thread,
					datum: target.anchor.datum,
					node: target.placement.datumElement
				}] : []), {
					drawn: registration.drawn,
					all: collection.threads
				});
				if (held && !sameSet(held, registration.heldKeys)) {
					registration.heldKeys = held;
					tick(ownership);
				}
				const anchor = activeComposition?.anchor;
				const placement = anchor && (registration.kind === "page" || anchor.datum && anchor.section === owner.id) ? placements.pendingAt() : null;
				const batch = [...targets].filter(([key]) => !held?.has(key)).map(([_key, { target }]) => Object.freeze(target));
				const compositionTarget = admitTarget(registration, {
					anchor,
					placement,
					thread: null
				});
				if (compositionTarget) batch.push(Object.freeze(compositionTarget.target));
				const rendering = render(Object.freeze(batch), {
					signal: abort.signal,
					collection,
					onCommit: (run) => committed.push(run)
				});
				const outlets = rendering != null && (typeof rendering === "object" || typeof rendering === "function") && "then" in rendering && typeof rendering.then === "function" ? await Promise.race([rendering, cancelled]) : rendering;
				if (!current()) return null;
				if (registrations.get(owner) !== registration || !owner.isConnected) {
					clearRegistration(registration);
					continue;
				}
				if (abort.signal.aborted) continue;
				if (!Array.isArray(outlets) || outlets.length !== batch.length) throw new TypeError("A Thread placement callback must return one outlet or null per target");
				const nominated = outlets;
				for (const [index, { thread }] of batch.entries()) {
					const outlet = nominated[index];
					if (outlet === null) continue;
					if (!(outlet instanceof Element)) throw new TypeError("A Thread outlet must be an Element or null");
					const threads = byOutlet.get(outlet) ?? [];
					if (thread) threads.push(thread);
					else compositionOutlet = outlet;
					byOutlet.set(outlet, threads);
				}
				validateOutlets(registration, byOutlet);
				if (compositionOutlet && (!byOutlet.has(compositionOutlet) || !sameAnchor(commands.composition.active()?.anchor, anchor))) compositionOutlet = null;
			} catch (error) {
				if (!current()) return null;
				if (abort.signal.aborted) continue;
				if (registration.kind === "page") throw error;
				plans.push({
					registration,
					byOutlet: /* @__PURE__ */ new Map(),
					compositionOutlet: null,
					committed: []
				});
				reportFailure(registration, error);
				continue;
			}
			plans.push({
				registration,
				byOutlet,
				compositionOutlet,
				committed
			});
		}
		return current() ? plans : null;
	}
	function commit() {
		if (!current() || !prepared) return;
		const plans = prepared.filter(({ registration }) => registrations.get(registration.owner) === registration && registration.owner.isConnected);
		const widgetClaims = /* @__PURE__ */ new Set();
		for (const plan of plans) {
			try {
				validateOutlets(plan.registration, plan.byOutlet);
				for (const [outlet, threads] of plan.byOutlet) plan.byOutlet.set(outlet, threads.filter((thread) => admitTarget(plan.registration, {
					anchor: thread.anchor,
					placement: placements.placedAt(thread.id),
					thread
				}) && (plan.registration.kind === "widget" || !widgetClaims.has(thread.id) && !holdsOut(thread.id))));
				if (![...plan.byOutlet.keys()].some((outlet) => outlet === plan.compositionOutlet) || !admitTarget(plan.registration, {
					anchor: activeComposition?.anchor,
					placement: placements.pendingAt(),
					thread: null
				})) plan.compositionOutlet = null;
			} catch (error) {
				if (plan.registration.kind === "page") throw error;
				reportFailure(plan.registration, error);
				plan.byOutlet.clear();
				plan.compositionOutlet = null;
			}
			if (plan.registration.kind === "widget") for (const threads of plan.byOutlet.values()) for (const thread of threads) widgetClaims.add(thread.id);
		}
		const previousComposition = commands.composition.outlet();
		let movedComposition = false;
		try {
			if (sameAnchor(activeComposition?.anchor, commands.composition.active()?.anchor)) {
				movedComposition = true;
				if (!plans.some(({ compositionOutlet }) => compositionOutlet && commands.composition.seat(compositionOutlet))) commands.composition.restore();
			}
			const nextClaimed = /* @__PURE__ */ new Set();
			for (const { registration, byOutlet } of plans) {
				for (const outlet of registration.outlets) if (!byOutlet.has(outlet)) clearThreadSurface(outlet);
				for (const [outlet, threads] of byOutlet) {
					const response = outlet === commands.composition.outlet() ? commands.composition.node() : null;
					renderThreadSurface(outlet, threads, commands, response);
					for (const thread of threads) nextClaimed.add(thread.id);
				}
			}
			for (const { registration, byOutlet } of plans) {
				for (const outlet of registration.outlets) if (!byOutlet.has(outlet)) outlet.removeAttribute("data-lf-thread-surface");
				for (const outlet of byOutlet.keys()) outlet.toggleAttribute("data-lf-thread-surface", true);
				registration.outlets = new Set(byOutlet.keys());
				registration.drawn = new Set([...byOutlet.values()].flat().flatMap((thread) => thread.anchor?.datum ? [thread.anchor.datum] : []));
			}
			if (!sameSet(claimedIds, nextClaimed)) {
				claimedIds = nextClaimed;
				tick(ownership);
			}
			prepared = null;
		} catch (error) {
			if (movedComposition) {
				if (!previousComposition?.isConnected || !commands.composition.seat(previousComposition)) commands.composition.restore();
			}
			throw error;
		}
		for (const { registration, committed } of plans) for (const run of committed) try {
			run();
		} catch (error) {
			reportFailure(registration, error);
		}
	}
}
const claimed = (id) => {
	ownership.value;
	return claimedIds.has(id);
};
const heldOut = (id) => {
	ownership.value;
	return holdsOut(id);
};
function revealHeld(ids) {
	for (const registration of registrations.values()) {
		const [id] = registration.held?.show(ids) ?? [];
		if (id) return {
			id,
			presented: (async () => {
				await registration.invalidate();
				await whenDocumentPresented();
			})()
		};
	}
	return null;
}
function surfaceFocusTarget(name, { part = "reply" } = {}) {
	const id = threadIdNamed(name);
	for (const registration of registrations.values()) {
		const thread = [...registration.outlets].map((outlet) => outlet.querySelector(`.lf-page-thread[data-thread="${CSS.escape(id)}"]`)).find(Boolean);
		if (!thread) continue;
		return threadFocusDestination(thread, {
			part,
			message: name
		});
	}
	return null;
}

//#endregion
//#region runtime/carry.js
const holdsValue = (node) => isHTML(node) && (node.matches(TEXT_BOX) || isHTML(node, "input") && node.type !== "file");
const holdsTick = (node) => isHTML(node, "input") && (node.type === "checkbox" || node.type === "radio");
function captureCarry(root, authored) {
	const active = focused(document);
	const partOwner = active?.hasAttribute("data-lf-carry") ? active.parentElement?.closest("[id]") : null;
	const records = [];
	const held = /* @__PURE__ */ new Map();
	const regionBodies = new Set(readingRegions().map(({ body }) => body));
	for (const node of root.querySelectorAll("[id]")) {
		const wrote = authored.querySelector(`#${CSS.escape(node.id)}`);
		if (wrote?.localName !== node.localName) continue;
		const record = {
			id: node.id,
			name: node.localName
		};
		const focusPart = active && node === partOwner ? active : null;
		if (node === active || focusPart) {
			record.focus = true;
			if (focusPart) {
				const part = focusPart.getAttribute("data-lf-carry");
				if (part !== null) record.part = part;
				record.partName = focusPart.localName;
			}
		}
		if (isHTML(node, "details") && isHTML(wrote, "details") && node.open !== wrote.open) record.open = node.open;
		if (!skipped(node)) {
			if (node.scrollTop && !regionBodies.has(node)) record.scrollTop = node.scrollTop;
			if (node.scrollLeft) record.scrollLeft = node.scrollLeft;
		}
		if (holdsValue(node) && holdsValue(wrote) && node.value !== wrote.value) record.value = node.value;
		if (holdsTick(node) && holdsTick(wrote) && node.checked !== wrote.checked) record.checked = node.checked;
		if (node === active || focusPart) {
			const caret = readCaret(active);
			if (caret) record.caret = caret;
		}
		if (Object.keys(record).length === 2) continue;
		records.push(record);
		held.set(record.id, node);
	}
	return {
		records,
		held
	};
}
function restoreCarry(records, held = /* @__PURE__ */ new Map(), handoffFocus = (move) => move()) {
	const positions = [];
	for (const record of records ?? []) {
		const arrived = document.getElementById(record.id);
		if (!arrived || arrived === held.get(record.id)) continue;
		if (arrived.localName !== record.name) continue;
		if (record.open !== void 0 && isHTML(arrived, "details")) arrived.open = record.open;
		if (record.value !== void 0 && holdsValue(arrived)) arrived.value = record.value;
		if (record.checked !== void 0 && holdsTick(arrived)) arrived.checked = record.checked;
		positions.push({
			arrived,
			record
		});
	}
	const restoreFocus = (parts) => handoffFocus(() => {
		for (const { arrived, record } of positions) {
			if (!record.focus || record.part !== void 0 !== parts) continue;
			const target = record.part === void 0 ? arrived : [...arrived.querySelectorAll(`[data-lf-carry="${CSS.escape(record.part)}"]`)].find((node) => node.parentElement?.closest("[id]") === arrived && node.localName === record.partName);
			if (target) focusDestination(target, "return", record.caret ? { caret: record.caret } : {});
		}
	});
	restoreFocus(false);
	return () => {
		for (const { arrived, record } of positions) {
			if (!arrived.isConnected) continue;
			if (record.scrollTop || record.scrollLeft) setScroll(arrived, {
				top: record.scrollTop || arrived.scrollTop,
				left: record.scrollLeft || arrived.scrollLeft
			});
		}
		restoreFocus(true);
	};
}

//#endregion
//#region runtime/keyboard/control-keys.js
const stepsBefore = (scope) => word(scope?.sequencePrefix ?? scope?.sequence) ?? [];
const stepsIn = (scope, row) => [...stepsBefore(scope), labelOf(row)].filter(Boolean);
function commandSteps(id) {
	for (const scope of pageScopes().filter((scope) => scope !== ELEMENTS)) for (const row of scope?.rows ?? []) if (row.id === id && bindings(row).length) return stepsIn(scope, row);
	return [];
}
function* namedControls(row) {
	if (row.control) yield {
		control: row.control,
		active: live$1(row) && bindings(row).length > 0,
		press: labelOf(row),
		shortcuts: () => ariaShortcuts([row], false)
	};
	for (const route of commandRoutes(row)) if (route.control && route.binding !== void 0) {
		const binding = route.binding;
		yield {
			control: route.control,
			active: commandAvailable(row, route) && bindings(row).includes(binding),
			press: spell(binding),
			shortcuts: () => ariaShortcuts([{
				...route,
				keys: [binding]
			}], false)
		};
	}
}
function controlRows() {
	const controls = /* @__PURE__ */ new Map();
	for (const scope of pageScopes().filter((scope) => scope !== ELEMENTS)) for (const row of scope?.rows ?? []) for (const named of namedControls(row)) {
		const control = word(named.control);
		if (!control) continue;
		const prior = controls.get(control);
		if (!prior || !prior.active && named.active) controls.set(control, {
			scope,
			...named
		});
	}
	return controls;
}
function paintCoreControls() {
	for (const [control, { scope, active, press, shortcuts }] of controlRows()) {
		let title = control.getAttribute("data-lf-key-title");
		if (title === null) {
			title = control.getAttribute("title") ?? "";
			control.setAttribute("data-lf-key-title", title);
		}
		const steps = [...stepsBefore(scope), press].filter(Boolean).join(" ");
		keeps(control, "title", title + (active ? ` (${steps})` : ""));
		if (buttonCommand(control)) continue;
		keeps(control, "aria-keyshortcuts", active && !scope.sequence ? shortcuts() : null);
	}
}

//#endregion
//#region runtime/references.js
function requireReference(verb, owner, attribute) {
	if (typeof attribute !== "string" || !Object.hasOwn(registry$1[owner.localName]?.["x-refers"] ?? {}, attribute)) throw new TypeError(`${verb} ${owner.localName} attribute ${String(attribute)} is not declared by x-refers`);
}
function referencedProjection(owner, attribute, id = owner.getAttribute(attribute)) {
	if (!id) return null;
	const { tag, key } = registry$1[owner.localName]["x-refers"][attribute];
	if (tag) {
		const within = registry$1[tag]["x-unique"][key];
		const scopeOf = (element) => element.parentElement?.closest(within) ?? null;
		const scope = scopeOf(owner);
		return [...scope?.querySelectorAll(tag) ?? []].find((member) => scopeOf(member) === scope && member.getAttribute(key) === id) ?? null;
	}
	const scope = authoredScope(owner);
	const page = pageDocument();
	return (scope ? elementById(id, scope) : null) ?? (scope === page || !page ? null : elementById(id, page));
}

//#endregion
//#region runtime/anchor-travel.js
const scrollingBoxFor = (element) => scrollersOf(element).next().value ?? null;
function scrollToFragment(element) {
	scrollIntoView(element, {
		behavior: "auto",
		block: "start"
	});
}
function createAnchorTravel({ anchors, refreshThread, focusForNavigation, threadFocusTarget, clearFor, announce }) {
	let travelIntent = 0;
	const retainTravel = (retained = retainUserIntent()) => {
		const intent = ++travelIntent;
		return restrictUserIntent(retained, () => intent === travelIntent);
	};
	const navigationGroupPrefix = `${performance.timeOrigin}:`;
	let navigationSteps = 0;
	let navigationGroup = null;
	onReadingInput((node) => {
		if (!navigationGroup || closestAcross(node, `${PRESSES},${"[data-lf-offer]:not([data-lf-offer=\"\"])"}`) || typesText(node)) return;
		const passage = passageBlock(node);
		if (!passage) return;
		if (passage !== navigationGroup.passage()) navigationGroup = null;
	});
	function stillLanded() {
		const where = navigationGroup && history.state?.lfNavigationGroup === navigationGroup.token && navigationGroup.landing();
		return Boolean(where && seenOf(where));
	}
	async function arrive(resolve, { intent, present = null, departure = null }) {
		if (!intent()) return false;
		const initial = resolve();
		if (!initial) return false;
		if (initial.scroll.length) await stopScroll(/* @__PURE__ */ new Set([pageScroller, ...unconcealedReadingRegions().map((region) => region.body)]));
		if (!intent()) return false;
		const first = resolve();
		if (!first || !intent()) return false;
		const holder = placeHolder(first.where);
		if (!holder) return false;
		const disclosures = [holder, ...first.reveal ?? []].map((target) => reveal(target, intent));
		const replacedView = disclosures.some((disclosure) => disclosure.replacedView);
		const place = (complete = false) => {
			let completed = false;
			intent.handoff(() => {
				const destination = resolve();
				if (!destination?.where) return;
				clearFor(destination, destination.scroll.length ? landedBox(destination.where) : null);
				if (destination.focus) focusForNavigation(destination.focus, "move", destination.caret === void 0 ? {} : { caret: destination.caret });
				const current = resolve();
				if (!current?.where) return;
				if (complete) departure?.commit();
				if (current.selection) {
					const { range, backward } = current.selection;
					const head = [range.startContainer, range.startOffset];
					const tail = [range.endContainer, range.endOffset];
					selectEnds(backward ? tail : head, backward ? head : tail);
				}
				for (const placement of current.scroll) placeScroll(placement, replacedView);
				completed = true;
			});
			return completed;
		};
		if (replacedView) place();
		await Promise.all(disclosures.map((disclosure) => disclosure.ready));
		if (!intent()) return false;
		if (present) await present();
		if (!intent()) return false;
		return place(true);
	}
	async function restoreSelection(anchor, { backward, intent }) {
		const mayArrive = retainTravel(intent);
		const resolve = () => {
			const target = resolveAnchor(anchor);
			const segments = targetSegments(target);
			if (!segments.length) return null;
			const range = rangeOf(segments);
			return {
				where: range,
				focus: targetPlace(target),
				selection: {
					range,
					backward
				},
				scroll: [{ at: range }]
			};
		};
		const destination = resolve();
		const datum = anchor.datum;
		const source = datum ? sectionOf(anchor) : null;
		if (!destination && !source) return false;
		const departure = prepareNavigationStep({
			intent: mayArrive,
			landing: () => resolve()?.where
		});
		departure.plan(destination?.where ?? source, { there: (readable) => Boolean(destination && readable(destination.where)) });
		if (source && datum) {
			const hydration = revealAddressed(source, datum);
			if (hydration?.then) await hydration;
			if (!mayArrive() || sectionOf(anchor) !== source) return false;
		}
		return arrive(resolve, {
			intent: mayArrive,
			departure
		});
	}
	async function arriveEditor(resolve, { intent, caret }) {
		const mayArrive = retainTravel(intent);
		const destination = resolve();
		if (!destination?.where) return null;
		const departure = prepareNavigationStep({
			intent: mayArrive,
			landing: () => resolve()?.where
		});
		departure.plan(destination.where);
		let release = () => {};
		await arrive(() => {
			const current = resolve();
			if (!current) return null;
			const input = current.input();
			return {
				where: current.where,
				focus: input,
				caret,
				scroll: input ? [{
					at: current.where,
					behavior: "instant",
					when: () => !readableDestination(current.where) || !readableDestination(input)
				}, {
					at: input,
					block: "nearest",
					behavior: "instant"
				}] : [{
					at: current.where,
					behavior: "instant"
				}]
			};
		}, {
			intent: mayArrive,
			departure,
			present: async () => {
				const current = resolve();
				if (!current) return;
				if (current.open) mayArrive.handoff(() => {
					const opened = current.open?.();
					if (opened) release = opened;
				});
				await current.present?.();
			}
		});
		release();
		return mayArrive() ? resolve()?.input() ?? null : void 0;
	}
	function prepareNavigationStep({ landing = null, url, intent }) {
		const write = prepareEntry();
		const continuing = landing && stillLanded() ? navigationGroup : null;
		const arrival = landing ? {
			landing,
			passage: () => {
				const where = landing();
				return where ? openingPassage(where) : null;
			}
		} : null;
		let moving;
		return {
			plan(where, { there } = {}) {
				moving = !(where && (there ? there(readableDestination) : readableDestination(where)));
				return moving;
			},
			commit() {
				if (moving === void 0) return;
				if (!moving) {
					if (continuing && arrival) Object.assign(continuing, arrival);
					return;
				}
				navigationGroup = arrival && {
					token: navigationGroupPrefix + ++navigationSteps,
					...arrival
				};
				write(url ?? window.location.href, navigationGroup && { lfNavigationGroup: navigationGroup.token }, Boolean(continuing));
			}
		};
	}
	function followFragment(url) {
		return fragmentTarget(url.hash) && fragmentNavigationStep(url, true);
	}
	function returnToFragment(url) {
		const where = fragmentTarget(url.hash);
		return where && !showsContents(where) ? fragmentNavigationStep(url, false) : null;
	}
	function fragmentNavigationStep(url, focus) {
		const mayArrive = retainTravel();
		return () => arrive(() => {
			const where = fragmentTarget(url.hash);
			return where && {
				where,
				focus: focus ? where : null,
				scroll: [{
					at: where,
					block: "fragment"
				}]
			};
		}, { intent: mayArrive });
	}
	async function navigateToDatum(owner, attribute, key, { success = "", missing = "", focus = true } = {}) {
		const mayArrive = retainTravel();
		requireReference("navigateToDatum", owner, attribute);
		if (typeof key !== "string" || !key) throw new TypeError("navigateToDatum key must be a non-empty string");
		let source = referencedProjection(owner, attribute);
		if (!source) {
			if (missing) notice(missing);
			return false;
		}
		const url = new URL(window.location.href);
		url.hash = source.id;
		const departure = prepareNavigationStep({
			url,
			intent: mayArrive
		});
		const hydration = revealAddressed(source, key);
		if (hydration?.then) await hydration;
		if (!mayArrive()) return false;
		source = referencedProjection(owner, attribute);
		if (!source) {
			if (missing) notice(missing);
			return false;
		}
		const destination = addressedElements(source, key)[0] ?? null;
		if (!destination) {
			if (missing) notice(missing);
			return false;
		}
		departure.plan(destination);
		const arrived = await arrive(() => {
			const source = referencedProjection(owner, attribute);
			const where = source && addressedElements(source, key)[0];
			return where && {
				where,
				focus: focus ? where : null,
				scroll: [{
					at: where,
					block: "start",
					when: () => !readableDestination(where)
				}]
			};
		}, {
			intent: mayArrive,
			departure
		});
		if (mayArrive()) {
			if (arrived && success) announce(success);
			else if (!arrived && missing) notice(missing);
		}
		return arrived;
	}
	function placeScroll({ at, align = at, block = "center", behavior = scrollBehavior(), when }, replacedView) {
		if (when && !when()) return;
		if (block === "fragment") scrollToFragment(at);
		else scrollIntoView(at, {
			alignment: align,
			behavior: replacedView ? "instant" : behavior,
			block
		});
	}
	function scrollToElement(element, behavior = scrollBehavior(), block = "center") {
		if (!element) return;
		const { replacedView } = reveal(element, retainUserIntent());
		placeScroll({
			at: element,
			behavior,
			block
		}, replacedView);
	}
	function seenOf(where) {
		const holder = placeHolder(where);
		if (!holder) return null;
		const destination = placeBox(where);
		const seen = clippedPlace(where, /* @__PURE__ */ new Map(), destination);
		return seen && {
			holder,
			destination,
			seen
		};
	}
	function readableDestination(where) {
		const shown = seenOf(where);
		if (!shown) return false;
		const { holder, destination, seen } = shown;
		const box = scrollingBoxFor(holder);
		const band = box ? landingBand(box) : shownBox(pageScroller);
		if (!band) return false;
		const close = (a, b) => Math.abs(a - b) <= .5;
		return destination.top >= band.top - .5 && destination.bottom <= band.bottom + .5 && close(seen.top, destination.top) && close(seen.right, destination.right) && close(seen.bottom, destination.bottom) && close(seen.left, destination.left);
	}
	function scrollToRange(where, behavior = scrollBehavior()) {
		const holder = placeHolder(where);
		if (!holder) return;
		const { replacedView } = reveal(holder, retainUserIntent());
		placeScroll({
			at: where,
			behavior
		}, replacedView);
	}
	const threadDestination = (id) => {
		const placement = anchors.placedAt(id);
		const segment = targetSegments(placement)[0];
		const where = segment ? rangeOf([segment]) : targetElement(placement) ?? targetPlace(placement);
		return livePoint(targetElement(placement) ?? targetPlace(placement), placement?.point) ?? where;
	};
	async function scrollToThread(id, { part = null, focus = true, presented = null, intent, history = true } = {}) {
		const mayArrive = retainTravel(intent);
		const anchor = threadNamed(id)?.anchor;
		const status = anchors.placedAt(id)?.status;
		const hydrationTarget = anchor?.visual ? {
			anchor,
			key: anchor.visual
		} : anchor?.datum && status !== "outdated" ? {
			anchor,
			key: anchor.datum
		} : null;
		const destination = threadDestination(id);
		const landing = () => threadDestination(id);
		const departure = history ? prepareNavigationStep({
			landing,
			intent: mayArrive
		}) : null;
		if (destination || hydrationTarget) departure?.plan(destination);
		if (hydrationTarget) {
			const source = sectionOf(hydrationTarget.anchor);
			const hydration = source && revealAddressed(source, hydrationTarget.key);
			if (hydration?.then) await hydration;
			if (!mayArrive() || sectionOf(hydrationTarget.anchor) !== source) return false;
			await refreshThread();
			if (!mayArrive()) return false;
		}
		return arrive(() => {
			const where = threadDestination(id);
			if (!where) return null;
			const target = focus && part ? threadFocusTarget(id, { part }) : null;
			const scroll = [];
			if (target) scroll.push({
				at: target,
				block: "nearest"
			});
			scroll.push({
				at: where,
				when: () => !readableDestination(where)
			});
			return {
				where,
				focus: target,
				scroll
			};
		}, {
			intent: mayArrive,
			departure,
			present: async () => {
				if (presented) await presented;
				if (mayArrive()) await refreshThread();
			}
		});
	}
	return {
		prepareNavigationStep,
		arrive,
		arriveEditor,
		restoreSelection,
		followFragment,
		returnToFragment,
		navigateToDatum,
		scrollToElement,
		readableDestination,
		scrollToRange,
		scrollToThread,
		threadDestination
	};
}

//#endregion
//#region runtime/version-picker.js
const LATEST_FAILED = "Latest edit couldn't be shown";
const INITIAL_LATEST = "New page available → open v999";
var VersionPicker = class {
	#activate = null;
	#compare = null;
	#latest = null;
	configure({ activate, compare, latest }) {
		this.#activate = activate;
		this.#compare = compare;
		this.#latest = latest;
	}
	activate(entry) {
		this.#activate?.(entry);
	}
	compare(version) {
		this.#compare?.(version);
	}
	latest() {
		this.#latest?.();
	}
};
const versionPicker = new VersionPicker();
const latestVersionLabel = ({ failed = false, activeLabel = null } = {}) => failed ? LATEST_FAILED : activeLabel ? `New page available → open ${activeLabel}` : INITIAL_LATEST;

//#endregion
//#region runtime/version.js
const PRIVATE_REVISION_PARAM = "_leaf-revision";
function authoredAttributes(root) {
	const attributes = /* @__PURE__ */ new Map();
	for (const { name, value } of root.attributes) {
		if (name.startsWith("data-lf-")) continue;
		if (name === "class") {
			const authoredClasses = [...root.classList].filter((token) => !token.startsWith("lf-")).join(" ");
			if (authoredClasses) attributes.set(name, authoredClasses);
		} else attributes.set(name, value);
	}
	return attributes;
}
const versionedHeadNode = (node) => !node.hasAttribute("data-lf-runtime") && (node.localName === "title" || node.localName === "style" || node.localName === "base" || node.localName === "meta" && (node.hasAttribute("name") || node.hasAttribute("property")) || node.localName === "link");
const authoredMarkup = (root) => {
	for (const member of root.querySelectorAll(`[${RUNTIME_PAINT_ATTRIBUTE.viewMember}]`)) member.removeAttribute("hidden");
	for (const name of Object.values(RUNTIME_PAINT_ATTRIBUTE)) for (const element of root.querySelectorAll(`[${name}]`)) element.removeAttribute(name);
	for (const preview of root.querySelectorAll("[data-lf-prepaint]")) preview.remove();
	return root;
};
const pairSources = (source, live, pairs) => {
	pairs.pair(source, live);
	const held = source instanceof HTMLTemplateElement ? source.content : source;
	const children = [...(live instanceof HTMLTemplateElement ? live.content : live).childNodes].filter((child) => !(child instanceof Element && child.matches("[data-lf-prepaint]")));
	for (const [at, child] of [...held.childNodes].entries()) {
		const peer = children[at];
		if (peer) pairSources(child, peer, pairs);
	}
	return pairs;
};
function captureInitialDocument() {
	const main = pageDocument();
	const inert = document.implementation.createHTMLDocument("");
	const source = main ? authoredMarkup(inert.importNode(main, true)) : null;
	for (const input of source?.querySelectorAll("input") ?? []) {
		if (![
			"file",
			"checkbox",
			"radio"
		].includes(input.type) && input.value !== input.defaultValue) input.value = input.defaultValue;
		input.checked = input.defaultChecked;
	}
	for (const textarea of source?.querySelectorAll("textarea") ?? []) textarea.value = textarea.defaultValue;
	const pairs = main && source ? pairSources(source, main, new SourcePairs()) : new SourcePairs();
	for (const disclosure of source?.querySelectorAll("details") ?? []) {
		const open = window.lfStorage.initialDisclosureOpen(pairs.require(disclosure));
		if (open !== void 0) disclosure.toggleAttribute("open", open);
	}
	return {
		authoredBodyAttributes: authoredAttributes(document.body),
		authoredHeadNodes: new Set([...document.head.children].filter(versionedHeadNode)),
		authoredHtmlAttributes: authoredAttributes(document.documentElement),
		source,
		pairs
	};
}
let initialDocument = captureInitialDocument();
function takeInitialDocument() {
	if (!initialDocument) throw new Error("The initial document capture has already been transferred");
	const captured = initialDocument;
	initialDocument = null;
	return captured;
}
const stamped = (version) => runtime.versions.find((candidate) => candidate.version === version);
const revisionBase = (entry) => Object.freeze({
	revision: entry.revision,
	url: entry.url,
	name: entry.version === null && "activated_at" in entry ? wentLive(entry.activated_at) : `v${entry.version}`
});
const wentLive = (iso) => {
	const at = new Date(iso);
	const sameDay = at.toDateString() === (/* @__PURE__ */ new Date()).toDateString();
	return at.toLocaleString(void 0, {
		...sameDay ? {} : {
			weekday: "short",
			day: "numeric",
			month: "short"
		},
		hour: "numeric",
		minute: "2-digit"
	});
};
const currentVersionToken = () => runtime.currentStamp === null ? "Draft" : `v${runtime.currentStamp}`;
const draftRevisions = () => {
	const revisions = /* @__PURE__ */ new Set();
	if (runtime.currentStamp === null && runtime.currentRevision !== null) revisions.add(runtime.currentRevision);
	if (runtime.active?.version === null) revisions.add(runtime.active.revision);
	return revisions;
};
const versionCount = () => runtime.versions.length + draftRevisions().size;
const versionsOffered = () => versionCount() > 0;
const behindCurrent = () => runtime.active !== null && runtime.currentRevision !== null && !runtime.showsActive;
const shownBehind = (active) => runtime.currentStamp === null ? "An older draft" : active.version === null ? `v${runtime.currentStamp}` : `v${runtime.currentStamp} of ${active.version}`;
function menuRows(state, notes, active) {
	const latest = state.versions.at(-1)?.version;
	const entries = state.versions.map((entry) => ({
		revision: entry.revision,
		version: entry.version,
		name: `v${entry.version}${entry.version === latest ? " (latest version)" : ""}`,
		note: notes[entry.version] ?? null,
		current: entry.version === runtime.currentStamp,
		active: false,
		comparable: comparable(entry.revision)
	}));
	for (const revision of draftRevisions()) {
		const isActive = revision === active.revision;
		entries.push({
			revision,
			version: null,
			name: `${isActive ? "Current" : "This view"} · ${revision === runtime.currentRevision ? runtime.currentLabel ?? revisionLabel(revision) : active.label}`,
			note: null,
			current: revision === runtime.currentRevision,
			active: isActive,
			comparable: false
		});
	}
	entries.sort((left, right) => right.revision - left.revision || (right.version ?? Infinity) - (left.version ?? Infinity));
	return Object.freeze(entries.map((entry) => Object.freeze(entry)));
}
function pickerModel(state) {
	const active = runtime.active;
	const base = diffOn.value ? diffBase.value : null;
	const offered = state !== null && versionsOffered();
	const behind = active !== null && behindCurrent();
	const sourceFailed = LIVE_ROOT && Boolean(state?.source_error);
	const currentLabel = runtime.currentLabel ?? "Draft";
	const newer = behind ? `; ${active.label} available` : "";
	return Object.freeze({
		picker: Object.freeze({
			offered,
			token: currentVersionToken(),
			compared: diffOn.value || diffPendingBase.value !== null,
			news: behind,
			keyTitle: offered ? diffPendingBase.value !== null ? `${currentLabel}: loading a comparison with ${diffPendingBase.value.name}${newer}` : base ? `${currentLabel}: showing what changed since ${base.name} — pick a version, or press Compare again to stop${newer}` : `${currentLabel}: versions; read one, or mark what changed since it${newer}` : currentLabel,
			ariaLabel: offered ? diffPendingBase.value !== null ? `${currentLabel}: loading comparison with ${diffPendingBase.value.name}; open versions${newer}` : base ? `${currentLabel}: comparing with ${base.name}; open versions${newer}` : `${currentLabel}: open versions${newer}` : currentLabel
		}),
		latest: Object.freeze({
			failed: sourceFailed,
			error: state && sourceFailed ? state.source_error : null,
			disabled: sourceFailed,
			keyTitle: state && sourceFailed ? state.source_error : "Open the current page",
			label: latestVersionLabel({
				failed: sourceFailed,
				activeLabel: behind ? active.label : null
			}),
			shown: behind ? shownBehind(active) : null,
			news: sourceFailed || behind
		}),
		rows: state === null || active === null ? Object.freeze([]) : menuRows(state, runtime.browser?.version_notes ?? {}, active),
		selection: Object.freeze({
			base: (diffPendingBase.value ?? (diffOn.value ? diffBase.value : null))?.revision ?? null,
			currentRevision: runtime.currentRevision,
			on: diffOn.value,
			pendingBase: diffPendingBase.value,
			baseRevision: diffBase.value?.revision ?? null
		})
	});
}
const holdFailedSave = holdingError();
function paintPicker() {
	const model = pickerModel(runtime.state);
	holdFailedSave(model.latest.failed ? "Latest edit not shown: it failed its check (see Versions)" : null);
	repaint();
}
const versionsReading = () => pickerModel(runtime.state);
registerPageControl({
	key: "versions",
	rank: PAGE_CONTROL_RANK.versions,
	label: "Versions",
	value: () => versionsReading().picker.token,
	shortcut: () => commandSteps("version.open"),
	disabled: () => !versionsReading().picker.offered,
	group: "page"
});
registerPageControl({
	key: "latest",
	rank: PAGE_CONTROL_RANK.latest,
	label: () => versionsReading().latest.label,
	offered: () => versionsReading().latest.news,
	disabled: () => versionsReading().latest.disabled,
	urgent: "new",
	press: () => versionPicker.latest(),
	group: "page"
});
const diffBlockSel = () => [
	TEXT_BLOCK,
	"aside",
	...tagsDeclaring((e) => e["x-owners"] && (e["x-content"] ?? "markup") === "markup"),
	...tagsDeclaring((e) => !e["x-inline"] && e["x-verbatim"])
].join(",");
const diffOpaqueSel = () => [
	...tagsDeclaring((e) => e["x-upgrade"] && !e["x-verbatim"] && e["x-content"] === "data"),
	...tagsDeclaring((e) => e["x-upgrade"] && e["x-data"]),
	...Object.entries(registry$1.$decisions).filter(([, { retires }]) => Object.keys(retires).length).map(([owner]) => owner),
	"svg"
].join(",");
const diffOn = Z(false);
const diffBase = Z(null);
const comparisonGeneration = Z(0);
const diffPendingBase = Z(null);
const diffMarked = /* @__PURE__ */ new Set();
const diffWordsOf = /* @__PURE__ */ new Map();
const inlineOpen = /* @__PURE__ */ new Map();
let diffRequest = 0;
const comparisonTextNodes = (root, opaque = diffOpaqueSel()) => textNodesUnder(root, "wrote", (child) => child.matches(opaque));
const comparisonWords = (root, opaque) => quoteFrom(comparisonTextNodes(root, opaque));
function diffWords(block, opaque) {
	const words = (root) => comparisonWords(root, opaque);
	if (!block.querySelector("[data-lf-source-words]")) return words(block);
	const source = block.ownerDocument.importNode(block, true);
	for (const island of source.querySelectorAll("[data-lf-source-words]")) {
		const text = new Text();
		text.textContent = island.getAttribute("data-lf-source-words");
		island.replaceWith(text);
	}
	return words(source);
}
function diffBlocks(root) {
	const pairs = [];
	const [blocks, opaque] = [diffBlockSel(), diffOpaqueSel()];
	const bodies = root.querySelectorAll(".lf-markdown-body");
	for (const body of bodies) {
		const owner = body.parentElement;
		if (!owner) throw new Error("A Markdown body must retain its containing owner");
		if (owner.closest(opaque)) continue;
		pairs.push([owner, `markdown:${body.dataset.lfSourceWords}`]);
	}
	for (const b of root.querySelectorAll(blocks)) {
		if (b.closest(opaque) || b.closest(".lf-markdown-body")) continue;
		if ([...b.querySelectorAll(blocks)].some((child) => !child.closest(opaque))) continue;
		let key = diffWords(b, opaque);
		for (const [attr, edge] of Object.entries(registry$1[b.localName]?.["x-says"] ?? {})) {
			const said = b.getAttribute(attr);
			if (said) key = edge === "before" ? `${said} ${key}` : `${key} ${said}`;
		}
		if (key) pairs.push([b, key]);
	}
	for (const w of root.querySelectorAll(opaque)) {
		if (w.parentElement?.closest(opaque)) continue;
		const entry = registry$1[w.localName] ?? {};
		const bindingAttrs = /* @__PURE__ */ new Set();
		for (const input of Object.values(entry["x-data"] ?? {})) {
			if (input.source) bindingAttrs.add(input.source);
			if (input.reference) bindingAttrs.add(input.reference);
		}
		const binding = [...bindingAttrs].sort().map((attr) => [attr, w.getAttribute(attr)]);
		pairs.push([w, ` ${w.tagName}#${w.id}${JSON.stringify(binding)}`]);
	}
	return pairs;
}
async function baseReading(baseRevision, throughSeq) {
	const params = new URLSearchParams({
		revision: String(baseRevision),
		through_seq: String(throughSeq)
	});
	const res = await fetch(pageUrl(`api/view?${params}`));
	if (!admitReading(res)) throw new LayerRefused("Leaf changed while comparing");
	if (!res.ok) throw new Error(`couldn't project revision r${baseRevision}`);
	return (await res.json()).browser;
}
function inOrder(before, after) {
	const width = after.length;
	const lengths = new Uint32Array(before.length * width);
	const at = (i, j) => j >= width ? 0 : lengths[i * width + j] ?? 0;
	for (let i = before.length - 1; i >= 0; i--) for (let j = after.length - 1; j >= 0; j--) lengths[i * width + j] = before[i] === after[j] ? at(i + 1, j + 1) + 1 : Math.max(at(i + 1, j), at(i, j + 1));
	const kept = /* @__PURE__ */ new Set();
	for (let i = 0, j = 0; i < before.length && j < after.length;) if (before[i] === after[j]) {
		kept.add(before[i]);
		i++;
		j++;
	} else if (at(i + 1, j) >= at(i, j + 1)) i++;
	else j++;
	return kept;
}
function paintBodies(doc, widgets) {
	for (const [id, { state, specs }] of widgets) for (const [verb, value] of Object.entries(state)) {
		if (specs.get(verb)?.record?.kind !== "body" || !("action" in value) || !value.action) continue;
		const body = doc.getElementById(id)?.querySelector(":scope > .lf-markdown-body");
		if (body) {
			if (typeof value.value !== "string") throw new Error("A body record requires Markdown text");
			paintMarkdown(body, value.value);
		}
	}
}
function placeCreated(doc, widgets) {
	for (const [id, { state, specs }] of widgets) for (const [verb, value] of Object.entries(state)) {
		const creates = specs.get(verb)?.creates;
		if (!creates || !("units" in value)) continue;
		const owner = doc.getElementById(id);
		if (!owner) continue;
		const { child, words } = creates;
		const markdown = registry$1[child]?.["x-text-format"] === "inline-markdown";
		for (const [unit, { detail }] of Object.entries(value.units)) {
			if (doc.getElementById(unit)) continue;
			const created = doc.createElement(child);
			created.id = unit;
			created.toggleAttribute("data-lf-added", true);
			const text = detail[words];
			if (typeof text !== "string") throw new Error("A created child requires its declared words");
			created.append(markdown ? doc.importNode(inlineMarkdownFragment(text), true) : text);
			owner.append(created);
		}
	}
}
function paintedSource(source, widgets) {
	const doc = document.implementation.createHTMLDocument("");
	const root = doc.importNode(source, true);
	const sourceOf = pairSources(root, source, new SourcePairs());
	doc.body.replaceChildren(root);
	formatDeclaredMarkdown(root);
	paintBodies(doc, widgets);
	placeCreated(doc, widgets);
	return {
		doc,
		root,
		sourceOf
	};
}
let versionSource = () => null;
const currentVersionSource = () => {
	const version = versionSource();
	if (!version?.source) throw new Error("The displayed revision has no authored source");
	return {
		source: version.source,
		pairs: version.pairs
	};
};
const currentSource = () => paintedSource(currentVersionSource().source, readApplication().effective.widgets);
function standingFor(block, current) {
	const { pairs } = currentVersionSource();
	let at = block;
	for (; at && at !== current.root; at = at.parentElement) {
		const original = current.sourceOf.get(at);
		const paired = original && pairs.get(original);
		if (paired?.isConnected) return paired;
		const named = at.id ? elementById(at.id, pageDocument()) : null;
		if (named?.isConnected) return named;
	}
	return null;
}
function changedSince(base, current = currentSource()) {
	const held = /* @__PURE__ */ new Map();
	for (const [, key] of diffBlocks(base.root)) held.set(key, (held.get(key) ?? 0) + 1);
	const changed = /* @__PURE__ */ new Set();
	for (const [block, key] of diffBlocks(current.root)) {
		const left = held.get(key) ?? 0;
		if (left > 0) held.set(key, left - 1);
		else {
			const standing = standingFor(block, current);
			if (standing) changed.add(standing);
		}
	}
	return changed;
}
function servedElements() {
	const served = /* @__PURE__ */ new Set();
	const version = versionSource();
	if (!version?.source) return served;
	const { source, pairs } = version;
	for (const node of [source, ...source.querySelectorAll("*")]) {
		const live = pairs.get(node);
		if (live) served.add(live);
	}
	return served;
}
function applyDiff(doc, baseAuthored, baseRevision, baseReading) {
	const baseView = baseReading.views[String(baseRevision.revision)];
	if (!baseView) throw new Error("The comparison answer omitted its requested revision");
	const baseProjection = projectView(baseView);
	const declaredAlike = ({ e, spec }) => {
		const current = baseAuthored.get(e.widget)?.specs.get(e.action);
		return current?.unit === spec.unit && JSON.stringify(current.record ?? null) === JSON.stringify(spec.record ?? null);
	};
	const baseWidgets = foldWidgetStates(baseAuthored, {
		...baseProjection,
		desired: new Map([...baseProjection.desired].filter(([, entry]) => declaredAlike(entry)))
	});
	const mark = (target) => {
		if (diffMarked.has(target)) return;
		target.classList.add("lf-ins-block");
		diffMarked.add(target);
	};
	const source = pageDocument(doc);
	if (!source) throw new Error("A comparison revision must contain its authored document");
	const base = paintedSource(source, baseWidgets);
	const current = currentSource();
	for (const block of changedSince(base, current)) mark(block);
	for (const [id, now] of readApplication().effective.widgets) {
		const before = baseWidgets.get(id);
		const widget = elementById(id);
		if (!before || !widget || inChrome(widget) || quoted(widget)) continue;
		for (const [verb, spec] of now.specs) {
			if (!spec.record || spec.record.kind === "body" || !before.specs.has(verb)) continue;
			if (spec.record.kind === "position") {
				const oldPosition = before.state[verb], newPosition = now.state[verb];
				if (!oldPosition || !newPosition || !("ranks" in oldPosition) || !("ranks" in newPosition)) throw new Error("A position record requires its ranked unit values");
				const was = oldPosition.value;
				const placed = Object.values(was).flat();
				for (const [container, ids] of Object.entries(newPosition.value)) {
					const stayed = was[container] ?? [];
					const kept = inOrder(stayed.filter((unit) => ids.includes(unit)), ids.filter((unit) => stayed.includes(unit)));
					for (const unit of ids) {
						if (!placed.includes(unit) || kept.has(unit)) continue;
						const moved = elementById(unit);
						if (moved) mark(moved);
					}
				}
				continue;
			}
			const { value } = obligationValue(now, verb, true);
			if (JSON.stringify(value) === JSON.stringify(obligationValue(before, verb, true).value)) continue;
			const ids = value;
			mark((spec.record.kind === "attribute" && ids.length === 1 ? elementById(ids[0]) : null) ?? widget);
		}
	}
	const opaque = diffOpaqueSel();
	for (const block of diffMarked) {
		if (!block.matches("[id]:not(.lf-ui):not([id^=\"lf-\"])") || block.closest(opaque)) continue;
		const [was, is] = [base, current].map(({ doc }) => doc.getElementById(block.id));
		diffWordsOf.set(block, {
			was: was ? comparisonWords(was, opaque) : null,
			is: is ? comparisonWords(is, opaque) : null
		});
	}
	return diffMarked.size;
}
const inlineId = (target) => `lf-version-inline-${target.id}`;
const authoredReading = (target) => {
	const segments = comparisonTextNodes(target);
	return {
		...readingFrom(segments),
		segments
	};
};
function pointAt(target, reading, offset) {
	if (!reading.units.length) return {
		node: target,
		offset: 0
	};
	const unit = offset === reading.units.length ? reading.units.at(-1) : reading.units[offset];
	if (!unit) throw new Error("An inline edit named a position outside its passage");
	return offset === reading.units.length ? unit.end : unit.start;
}
function insertAt(target, reading, offset, node) {
	const point = pointAt(target, reading, offset);
	if (point.node instanceof Element) {
		move(point.node, node, point.node.childNodes[point.offset] ?? null);
		return;
	}
	const text = point.node;
	const parent = text.parentNode;
	if (!parent) throw new Error("An inline edit requires its passage to remain in a tree");
	if (point.offset === 0) move(parent, node, text);
	else if (point.offset === text.data.length) move(parent, node, text.nextSibling);
	else move(parent, node, text.splitText(point.offset));
}
function rangesAt(reading, start, end) {
	const first = reading.units[start];
	const last = reading.units[end - 1];
	if (!first || !last) return [];
	return reading.segments.slice(reading.segments.findIndex(({ node }) => node === first.start.node), reading.segments.findIndex(({ node }) => node === last.end.node) + 1).map((segment) => ({
		...segment,
		start: segment.node === first.start.node ? first.start.offset : segment.start,
		end: segment.node === last.end.node ? last.end.offset : segment.end
	})).filter(({ start, end }) => end > start).map((segment) => rangeOf([segment]));
}
function paintInlineInsertions() {
	const ranges = [...inlineOpen.values()].flatMap((entry) => entry.ranges);
	if (ranges.length) CSS.highlights.set("lf-version-insert", new Highlight(...ranges));
	else CSS.highlights.delete("lf-version-insert");
}
function openInlineComparison(target, base, words) {
	const before = words.was;
	const reading = authoredReading(target);
	const current = currentVersionToken();
	const label = el("span", "lf-ui lf-quiet lf-version-inline-label", before === null ? `New since ${base.name}` : `${base.name} → ${current}`);
	label.id = inlineId(target);
	label.setAttribute("aria-label", before === null ? `New since ${base.name}` : `Inline comparison from ${base.name} to ${current}`);
	const nodes = [label];
	const additions = [];
	const insertions = [{
		offset: 0,
		node: label
	}];
	let afterOffset = 0;
	let hasTextChange = false;
	for (const run of before === null ? [] : alignInlineText(before, reading.text)) if (run.kind === "delete") {
		const dropped = el("span", "lf-ui lf-version-inline-deletion");
		dropped.append(el("del", "", run.text));
		nodes.push(dropped);
		insertions.push({
			offset: afterOffset,
			node: dropped
		});
		hasTextChange = true;
	} else {
		const length = [...run.text].length;
		if (run.kind === "insert") {
			additions.push([afterOffset, afterOffset + length]);
			hasTextChange = true;
		}
		afterOffset += length;
	}
	insertions.sort((left, right) => right.offset - left.offset).forEach(({ offset, node }) => insertAt(target, reading, offset, node));
	const currentReading = authoredReading(target);
	const ranges = additions.flatMap(([start, end]) => rangesAt(currentReading, start, end));
	target.classList.toggle("lf-version-inline", hasTextChange);
	inlineOpen.set(target, {
		nodes,
		ranges
	});
	paintInlineInsertions();
	layoutChanged(target);
	return before === null ? `${base.name} had nothing here` : `showing an inline diff from ${base.name}`;
}
function closeInlineComparison(target) {
	const entry = inlineOpen.get(target);
	inlineOpen.delete(target);
	target.classList.remove("lf-version-inline");
	for (const node of entry?.nodes ?? []) node.remove();
	paintInlineInsertions();
	layoutChanged(target);
}
function inlineReading(target) {
	const base = diffOn.value ? diffBase.value : null;
	const words = base ? diffWordsOf.get(target) : void 0;
	return base && words && words.was !== words.is && words.is === comparisonWords(target) ? {
		base,
		words
	} : null;
}
const inlineComparison = (target) => {
	const reading = inlineReading(target);
	return reading ? {
		id: inlineId(target),
		open: inlineOpen.has(target),
		offer: `${reading.base.name} → ${currentVersionToken()}`
	} : null;
};
function toggleInlineComparison(target) {
	const reading = inlineReading(target);
	if (!reading) return null;
	let said;
	if (inlineOpen.has(target)) {
		closeInlineComparison(target);
		said = `inline diff from ${reading.base.name} hidden`;
	} else said = openInlineComparison(target, reading.base, reading.words);
	tick(comparisonGeneration);
	return said;
}
const comparable = (revision) => runtime.currentRevision !== null && revision < runtime.currentRevision;
function setDiff(on, base = null, pendingBase = null) {
	W(() => {
		diffOn.value = on;
		diffPendingBase.value = pendingBase;
		if (on) diffBase.value = base;
		if (!on) {
			diffRequest++;
			for (const target of [...inlineOpen.keys()]) closeInlineComparison(target);
			diffWordsOf.clear();
			for (const b of diffMarked) b.classList.remove("lf-ins-block");
			diffMarked.clear();
		}
		tick(comparisonGeneration);
	});
}
async function showComparison(base, { offered = false } = {}) {
	setDiff(false, null, base);
	const mine = ++diffRequest;
	const baseRevision = base.revision;
	const documentRequest = authoredDocument(base.url);
	let doc;
	let reading;
	let baseAuthored;
	try {
		while (true) {
			const throughSeq = runtime.lastEventSeq;
			if (throughSeq === null) throw new Error("A comparison requires an accepted log reading");
			[doc, reading] = await Promise.all([documentRequest, baseReading(baseRevision, throughSeq)]);
			if (mine !== diffRequest) return;
			if (runtime.lastEventSeq === throughSeq) break;
		}
		if (mine !== diffRequest) return;
		baseAuthored = stageAuthoredStates(doc, /* @__PURE__ */ new Map());
		const source = pageDocument(doc);
		if (!source) throw new Error("A comparison revision must contain its authored document");
		await loadDeclaredMarkdown(source);
	} catch {
		if (mine === diffRequest) {
			diffPendingBase.value = null;
			raiseError(`Couldn't load ${base.name}`);
		}
		return;
	}
	if (mine !== diffRequest) return;
	const n = applyDiff(doc, baseAuthored, base, reading);
	if (offered && !n) return setDiff(false);
	setDiff(true, base);
	notice(n ? `${n} changed passage${n === 1 ? "" : "s"} since ${base.name}` : `No text changes since ${base.name}`);
}
function offerComparison(base) {
	if (selectedBase() !== null || !comparable(base.revision)) return;
	showComparison(base, { offered: true });
}
const pressComparison = (version) => {
	if (version === null) return;
	const entry = stamped(version);
	if (!entry) return;
	return selectedBase()?.revision === entry.revision ? setDiff(false) : showComparison(revisionBase(entry));
};
const stopComparison = () => setDiff(false);
const comparisonBase = () => diffOn.value ? diffBase.value : null;
const selectedBase = () => diffPendingBase.value ?? comparisonBase();
function comparisonChanges(owner = null) {
	comparisonGeneration.value;
	const changes = diffOn.value ? [...diffMarked] : [];
	return owner ? changes.filter((block) => block !== owner && under(block, owner)) : changes;
}
async function authoredDocument(url) {
	const response = await fetch(url);
	if (!response.ok) throw new Error(`couldn't load ${url} (${response.status})`);
	const doc = new DOMParser().parseFromString(await response.text(), "text/html");
	return authoredMarkup(doc);
}
const revisionDocuments = /* @__PURE__ */ new Map();
function revisionDocument(revision) {
	const saved = revisionDocuments.get(revision.revision);
	if (saved) return saved;
	const arriving = authoredDocument(revision.url).catch((error) => {
		revisionDocuments.delete(revision.revision);
		throw error;
	});
	revisionDocuments.set(revision.revision, arriving);
	return arriving;
}
function createVersionController({ initialDocument, compositionInput, openThread, refreshThread, midComposition, hasPending, readAndApply, syncLayout, captureRetainedCurrentLocation, restoreRetainedCurrentLocation, captureObligationCurrentLocation, restoreObligationCurrentLocation, versions }) {
	let { authoredBodyAttributes, authoredHeadNodes, authoredHtmlAttributes, source: authoredSource } = initialDocument;
	const sourcePairs = initialDocument.pairs;
	versionSource = () => ({
		source: authoredSource,
		pairs: sourcePairs
	});
	let authoredRoot = layerRoot(document);
	const VIEW_KEY = "lf-view";
	const HANDOFF_KEY = "lf-revision-handoff";
	const PICKER = {
		id: "version.open",
		ready: savedReadingSettled,
		keys: ["Shift+v"],
		title: "versions",
		run: () => versions.press(),
		when: versionsOffered
	};
	let forceActivation = false;
	const goVersion = (version) => {
		if (version === runtime.currentStamp) return;
		const target = stamped(version);
		if (!target) return;
		const url = new URL(target.url, location.href);
		url.searchParams.set("pin", "");
		location.href = url.href;
	};
	const goActive = () => {
		if (!runtime.active) return;
		if (LIVE_ROOT) {
			if (runtime.showsActive) return;
			forceActivation = true;
			readAndApply();
			return;
		}
		location.href = PAGE_SCOPE || "/";
	};
	function replaceAuthoredAttributes(target, source, prior) {
		const runtimeState = runtimeRootState(target);
		const next = authoredAttributes(source);
		const tokens = (value) => new Set(value?.split(" "));
		const nextTokens = tokens(next.get("class"));
		for (const token of tokens(prior.get("class"))) if (!nextTokens.has(token)) target.classList.remove(token);
		for (const token of nextTokens) if (!target.classList.contains(token)) target.classList.add(token);
		const declared = new Set(source.style);
		const priorStyle = document.createElement(target.localName).style;
		priorStyle.cssText = prior.get("style") ?? "";
		for (const property of priorStyle) if (!runtimeState.styles.has(property) && !declared.has(property)) target.style.removeProperty(property);
		const existing = new Set(target.style);
		for (const property of declared) {
			if (runtimeState.styles.has(property)) continue;
			const value = source.style.getPropertyValue(property);
			const priority = source.style.getPropertyPriority(property);
			if (!existing.has(property) || target.style.getPropertyValue(property) !== value || target.style.getPropertyPriority(property) !== priority) target.style.setProperty(property, value || " ", priority);
		}
		const plain = (name) => name !== "class" && name !== "style" && !runtimeState.attributes.has(name);
		for (const name of prior.keys()) if (plain(name) && !next.has(name)) target.removeAttribute(name);
		for (const [name, value] of next) if (plain(name)) keeps(target, name, value);
		return next;
	}
	function activateHead(doc, revision) {
		const source = [...doc.head.children].filter(versionedHeadNode);
		const current = [...document.head.children].filter((node) => authoredHeadNodes.has(node));
		if (current.length !== authoredHeadNodes.size || current.length !== source.length || current.some((node, index) => !node.isEqualNode(source[index] ?? null))) {
			for (const node of authoredHeadNodes) node.remove();
			const next = /* @__PURE__ */ new Set();
			for (const node of source) {
				const imported = document.importNode(node, true);
				document.head.append(imported);
				next.add(imported);
			}
			authoredHeadNodes = next;
		}
		let marker = document.querySelector("meta[name=\"lf-revision\"][data-lf-runtime]");
		if (!marker) {
			marker = document.createElement("meta");
			marker.name = "lf-revision";
			marker.dataset.lfRuntime = "1";
			document.head.append(marker);
		}
		marker.content = String(revision.revision);
	}
	const upgraded = (element) => Boolean(registry$1[element.localName]?.["x-upgrade"]);
	function* elementsWithin(root) {
		const inner = root instanceof HTMLTemplateElement ? root.content : root;
		for (const child of inner.children) {
			yield child;
			yield* elementsWithin(child);
		}
	}
	const deferredScript = "data:text/javascript;charset=utf-8,";
	const unrooted = (value, root) => {
		if (value.startsWith(deferredScript)) {
			value = deferredScript + value.slice(35).replace(/^(?:%0A)+/, "");
			if (root) value = value.split(encodeURIComponent(root)).join("%2F");
		}
		return root && value.includes(root) ? value.split(root).join("/") : value;
	};
	const sameValue = (held, value, arrivingRoot) => unrooted(held, authoredRoot) === unrooted(value, arrivingRoot);
	function sameAuthoredMarkup(before, after, arrivingRoot) {
		if (before.isEqualNode(after)) return true;
		const strip = (element, root) => {
			const copy = element.ownerDocument.importNode(element, true);
			if (!root) return copy;
			for (const node of [copy, ...elementsWithin(copy)]) {
				if (node.matches("style, script")) node.textContent = unrooted(node.textContent, root);
				for (const attribute of node.attributes) attribute.value = unrooted(attribute.value, root);
			}
			return copy;
		};
		return strip(before, authoredRoot).isEqualNode(strip(after, arrivingRoot));
	}
	const shell = (element, members) => {
		const copy = element.ownerDocument.importNode(element, false);
		if (members) for (const child of element.childNodes) copy.append(child.cloneNode(false));
		return copy;
	};
	const reachesMembers = (before, after, arrivingRoot) => {
		const entry = registry$1[before.localName];
		if (entry?.["x-patch"] !== "members") return false;
		const members = !authoredBody(sourcePairs.require(before)) && (entry["x-content"] === "members" || entry["x-views"] !== void 0);
		return sameAuthoredMarkup(shell(before, members), shell(after, members), arrivingRoot);
	};
	function patchRules(doc) {
		const arrivingRoot = layerRoot(doc);
		return {
			pairs: sourcePairs,
			contains: under,
			declared: upgraded,
			body: authoredBody,
			reaches: (before, after) => reachesMembers(before, after, arrivingRoot),
			same: (before, after) => sameAuthoredMarkup(before, after, arrivingRoot),
			sameValue: (held, value) => sameValue(held, value, arrivingRoot)
		};
	}
	function captureEditingContinuity() {
		const draftEditing = captureDraftEditing();
		return {
			draftEditing,
			replyThread: draftEditing?.mirrored ? heldThreadId() : null,
			replyInView: focusedInView() !== null,
			obligationCurrentLocation: draftEditing ? null : captureObligationCurrentLocation()
		};
	}
	async function landContinuity(land) {
		try {
			await land();
		} catch (error) {
			reportPageError(error, `Revision continuity failed`);
		}
	}
	async function restoreEditingContinuity(continuity, currentIntent) {
		if (!currentIntent()) return;
		const { draftEditing, replyThread, replyInView, obligationCurrentLocation } = continuity;
		restoreObligationCurrentLocation(obligationCurrentLocation);
		if (!draftEditing) return;
		const mayRestore = restrictUserIntent(currentIntent, () => draftEditingStands(draftEditing));
		if (!mayRestore()) return;
		if (restoreDraftEditing(draftEditing, focused())) return;
		const input = replyThread ? await restoreReplyEditing(draftEditing, async () => {
			await refreshThread();
			return mayRestore() ? replyDestination(replyThread, openThread, mayRestore, { scroll: replyInView }) : null;
		}) : draftEditingDestination(draftEditing, mayRestore.handoff);
		if (!replyThread && input) mayRestore.handoff(() => focusDestination(input, "return"));
		if (mayRestore()) restoreDraftEditing(draftEditing, input);
	}
	async function activateRevision(doc, target) {
		const currentIntent = retainUserIntent();
		const view = captureView();
		const retainedCurrentLocation = captureRetainedCurrentLocation();
		const editingContinuity = captureEditingContinuity();
		const comparedFrom = selectedBase();
		if (comparedFrom !== null) setDiff(false);
		const live = pageDocument();
		const outgoing = authoredSource;
		const source = pageDocument(doc);
		if (!live || !source || !outgoing) throw new Error("A revision patch requires its captured and arriving authored documents");
		const carry = captureCarry(live, outgoing);
		const arrivingRoot = layerRoot(doc);
		const rules = patchRules(doc);
		revisionDocuments.delete(target.revision);
		const isAuthored = authored(live);
		const generated = (node) => (node.nodeType === Node.ELEMENT_NODE || node.parentElement !== null) && !isAuthored(node);
		const arrived = [];
		const arrivedDescriptors = /* @__PURE__ */ new Map();
		const prior = readApplication().document;
		rememberAuthoredParents(source);
		const sourceAuthored = stageAuthoredStates(source, /* @__PURE__ */ new Map());
		const sourceDescriptors = stageWidgetDescriptors(source, {
			kind: "page",
			revision: target.revision
		});
		const touched = [];
		const arrive = (node, parent) => {
			const arriving = document.importNode(node, true);
			pairSources(node, arriving, sourcePairs);
			if (arriving instanceof Element) {
				rememberPassageParts(arriving);
				rememberAuthoredParents(arriving, parent instanceof Element ? parent : parent.parentElement);
				const bindings = [];
				for (const element of [arriving, ...arriving.querySelectorAll("[id]")]) {
					const descriptor = sourceDescriptors.descriptors.get(element.id);
					if (!descriptor) continue;
					bindings.push({
						element,
						descriptor
					});
					arrivedDescriptors.set(element.id, descriptor);
				}
				commitWidgetDescriptors({ bindings });
				formatDeclaredMarkdown(arriving);
				arrived.push(arriving);
			}
			return arriving;
		};
		const { restoreCarryScroll } = await patchDocument(live, () => {
			authoredHtmlAttributes = replaceAuthoredAttributes(document.documentElement, doc.documentElement, authoredHtmlAttributes);
			keeps(document.documentElement, "data-lf-layout", doc.documentElement.getAttribute("data-lf-layout"));
			authoredBodyAttributes = replaceAuthoredAttributes(document.body, doc.body, authoredBodyAttributes);
			activateHead(doc, target);
			sourcePairs.set(source, live);
			patchTree(outgoing, source, {
				...rules,
				arrive,
				generated,
				touched: (element) => touched.push(element)
			});
			const restoreCarryScroll = restoreCarry(carry.records, carry.held, currentIntent.handoff);
			reindexPassageOwners(live);
			pruneScopedElements();
			return {
				restoreCarryScroll,
				roots: [...arrived, ...touched],
				widgets: arrived.flatMap((root) => [root, ...elementsWithin(root)]).filter((element) => upgraded(element) && element.id).map((element) => element.id)
			};
		});
		authoredSource = source;
		authoredRoot = arrivingRoot;
		const nextAuthored = new Map([...prior.authored].filter(([id]) => prior.descriptors.get(id)?.document.kind === "thread"));
		for (const [id, value] of sourceAuthored) nextAuthored.set(id, value);
		const descriptors = /* @__PURE__ */ new Map();
		for (const [id, incoming] of sourceDescriptors.descriptors) descriptors.set(id, arrivedDescriptors.get(id) ?? prior.descriptors.get(id) ?? incoming);
		for (const [id, descriptor] of prior.descriptors) if (descriptor.document.kind === "thread") descriptors.set(id, descriptor);
		const retired = new Set([...prior.descriptors].filter(([id, descriptor]) => descriptor.document.kind === "page" && !sourceDescriptors.descriptors.has(id)).map(([id]) => id));
		commitWidgetDescriptors({ bindings: [] }, retired);
		return {
			document: {
				...prior,
				revision: target.revision,
				stamp: target.version ?? null,
				authored: nextAuthored,
				descriptors
			},
			land: () => landContinuity(async () => {
				releaseHolds();
				settleDocumentLayout();
				syncLayout();
				if (currentIntent()) {
					restoreView(view, currentIntent);
					restoreRetainedCurrentLocation(retainedCurrentLocation);
					restoreCarryScroll();
					await restoreEditingContinuity(editingContinuity, currentIntent);
				}
				if (comparedFrom !== null) showComparison(comparedFrom);
				const outgoingSource = paintedSource(outgoing, readApplication().effective.widgets);
				for (const block of changedSince(outgoingSource)) backgroundFlash(block, flashDuration());
				notice(`Updated to ${target.label}`, { background: true });
			})
		};
	}
	async function prepareActivation(state) {
		const target = state.active;
		if (!LIVE_ROOT || !target || runtime.currentRevision === null || target.revision <= runtime.currentRevision) return null;
		const activates = (retains = void 0) => runtime.currentRevision !== null && target.revision > runtime.currentRevision && !hasPending() && (!midComposition(retains) || forceActivation);
		if (!servedExecutable || target.executable !== servedExecutable) return {
			revision: target.revision,
			activates: () => activates(),
			install: reloadInto(target)
		};
		let doc;
		let source;
		const outgoing = authoredSource;
		try {
			doc = await revisionDocument(target);
			source = pageDocument(doc);
			if (!outgoing || !source) throw new Error("A revision patch requires its authored documents");
			await preloadWidgets(source);
		} catch (error) {
			reportPageError(error, `revision ${target.revision} failed to load`);
			return null;
		}
		return {
			revision: target.revision,
			activates: () => activates((node) => selectedBase() === null && patchRetains(outgoing, source, node, patchRules(doc))),
			install: () => {
				forceActivation = false;
				return activateRevision(doc, target);
			}
		};
	}
	const reloadInto = (target) => () => {
		forceActivation = false;
		const live = pageDocument();
		const source = authoredSource;
		if (!live || !source) throw new Error("A revision handoff requires its authored document");
		const view = captureView();
		const editingContinuity = captureEditingContinuity();
		tabStore.set(VIEW_KEY, JSON.stringify(view));
		tabStore.set(HANDOFF_KEY, JSON.stringify({
			revision: target.revision,
			url: location.href,
			view,
			retainedCurrentLocation: captureRetainedCurrentLocation(),
			...editingContinuity,
			carry: captureCarry(live, source).records,
			comparison: selectedBase(),
			pointer: pointerAt()
		}));
		const marked = new URL(location.href);
		marked.searchParams.set(PRIVATE_REVISION_PARAM, String(target.revision));
		replaceEntry(marked);
		location.reload();
		return new Promise(() => {});
	};
	function captureView() {
		dropGonePlaces();
		const blocks = textBlocks();
		const active = activeReadingRegion(readingRegions(), blocks);
		const view = {
			page: capturePlace(null, blocks),
			revision: runtime.currentRevision,
			activeRegion: active?.id,
			regions: Object.fromEntries([...places].flatMap(([id, { reading }]) => id === PAGE ? [] : [[id, reading]]))
		};
		for (const region of readingRegions()) {
			if (!shownRegionBounds(region)) continue;
			if (regionScrollBehavior(region) !== "bounded" && region.id !== active?.id) continue;
			const reading = capturePlace(region, blocks);
			if (reading) view.regions[region.id] = reading;
		}
		return view;
	}
	function restoreView(view, currentIntent) {
		releaseHolds();
		const regions = new Map(readingRegions().map((region) => [region.id, region]));
		const active = (view.activeRegion === void 0 ? void 0 : regions.get(view.activeRegion)) ?? containingReadingRegionFor(focusedInView()) ?? readingRegionFor(pageReadingBlock());
		if (active) reveal(active.host, currentIntent);
		const restored = /* @__PURE__ */ new Set();
		const activePlace = active ? {
			region: active,
			reading: view.regions[active.id],
			box: effectiveScroller(active)
		} : null;
		if (activePlace?.reading && (hasLandmark(activePlace.reading) || rawOffsetFits(activePlace.reading, activePlace.box) && activePlace.box !== pageScroller)) {
			restorePlace(activePlace.reading, activePlace.region, currentIntent);
			restored.add(activePlace.box);
		} else if (view.page) {
			restorePlace(view.page, null, currentIntent);
			restored.add(pageScroller);
		}
		if (view.page && !restored.has(pageScroller) && (hasLandmark(view.page) || rawOffsetFits(view.page, pageScroller))) {
			restorePlace(view.page, null, currentIntent);
			restored.add(pageScroller);
		}
		for (const [id, reading] of Object.entries(view.regions ?? {})) {
			const region = regions.get(id);
			if (!region || !shownRegionBounds(region)) continue;
			const box = effectiveScroller(region);
			if (restored.has(box)) continue;
			if (!hasLandmark(reading) && !rawOffsetFits(reading, box)) continue;
			restorePlace(reading, region, currentIntent);
			restored.add(box);
		}
	}
	const activeReadingRegion = (candidates = readingRegions(), blocks = textBlocks()) => {
		const focusedRegion = containingReadingRegionFor(focusedInView());
		if (focusedRegion && candidates.some(({ id }) => id === focusedRegion.id)) return focusedRegion;
		const recent = candidates.find(({ id }) => id === recentReadingRegion()?.id);
		if (recent) return recent;
		return candidates.flatMap((region) => {
			const measured = blocksOnScreen(region, blocks).next().value;
			return measured ? [{
				region,
				rect: measured[1]
			}] : [];
		}).sort((a, b) => a.rect.top - b.rect.top)[0]?.region;
	};
	const PAGE = "$page";
	const places = /* @__PURE__ */ new Map();
	let placeCount = 0;
	let shifting = false;
	const holds = /* @__PURE__ */ new Map();
	const subjectPlaces = /* @__PURE__ */ new Map();
	let reapply = null;
	const boxId = (box) => box === pageScroller ? PAGE : regionForBox(box)?.id;
	const held = (box) => {
		const id = boxId(box);
		return id === void 0 ? null : holdOf(id);
	};
	function holdOf(id) {
		const hold = holds.get(id);
		if (!hold) return null;
		const box = hold.box.deref();
		const region = box && boxId(box) === id ? regionForBox(box) : void 0;
		const moved = region === void 0 ? "gone" : movedAway(box, hold, region);
		const acted = box !== void 0 && inputSince(box, hold.since);
		if (!moved && !acted && hold.currentIntent()) return hold;
		holds.delete(id);
		if (moved === "carried" || !moved && acted) {
			const reading = moved ? capturePlace(region) : hold.reading;
			if (reading) places.set(id, {
				reading,
				at: ++placeCount,
				choices: scrollChoices(),
				inputs: moved ? inputCount() : hold.since
			});
		}
		return null;
	}
	const movedAway = (box, hold, region) => {
		const settling = reapply !== null;
		const node = placeNode(hold.reading);
		if (!node) return settling ? null : "gone";
		if (boxOf(node) !== box) return "gone";
		const now = placeOffset(hold.reading, region);
		if (now === null) return settling ? null : "gone";
		if (!box) return "gone";
		const scrolled = box.scrollTop - hold.top;
		const shifted = now - hold.offset;
		if (Math.abs(shifted) <= 2) {
			hold.top = box.scrollTop;
			return null;
		}
		if (Math.abs(scrolled) <= 2) return null;
		if (Math.abs(shifted + scrolled) <= 2) return "carried";
		return settling ? null : "carried";
	};
	const touched = /* @__PURE__ */ new WeakMap();
	const inputSince = (box, count) => (touched.get(box) ?? 0) > count;
	const writing = /* @__PURE__ */ new WeakMap();
	const ownEnd = /* @__PURE__ */ new WeakMap();
	const wrote = (box, from) => {
		if (box.scrollTop !== from) writing.set(box, inputCount());
	};
	const readerChose = (box, count) => chosenSince(box, Math.max(count, ownEnd.get(box) ?? 0));
	const inputBox = (element, event) => {
		if (!element) return pageScroller;
		const chain = [];
		for (const box of scrollChainOf(element)) {
			chain.push(box);
			if (getComputedStyle(box).overscrollBehaviorY !== "auto") break;
		}
		const innermost = chain[0] ?? pageScroller;
		if (!(event instanceof WheelEvent) || !event.deltaY) return innermost;
		const down = event.deltaY > 0;
		return chain.find((box) => down ? box.scrollTop < scrollLimit(box) - 2 : box.scrollTop > 2) ?? innermost;
	};
	const regionForBox = (box) => box === pageScroller ? null : readingRegions().find((region) => region.body === box && regionScrollBehavior(region) === "bounded");
	const boxOf = (node) => effectiveScroller(containingReadingRegionFor(node));
	const dropGonePlaces = () => {
		const present = new Set(readingRegions().map(({ id }) => id));
		for (const map of [places, subjectPlaces]) for (const id of map.keys()) if (id !== PAGE && !present.has(id)) map.delete(id);
	};
	function recordPlaces(boxes, { currentLocation = false } = {}) {
		if (shifting || compositionChanges.size || !regionsSettled()) return;
		dropGonePlaces();
		for (const box of boxes) {
			const region = regionForBox(box);
			if (region === void 0 || held(box)) continue;
			if (region && !(under(region.host, pageDocument()) && shownRegionBounds(region))) continue;
			const before = places.get(region ? region.id : PAGE);
			const acted = currentLocation || readerChose(box, before?.choices ?? 0) || inputSince(box, before?.inputs ?? 0);
			if (before && !acted) continue;
			const reading = capturePlace(region);
			if (!reading || reading.scroller === void 0) continue;
			places.set(reading.scroller, {
				reading,
				at: acted ? ++placeCount : 0,
				choices: scrollChoices(),
				inputs: inputCount()
			});
		}
	}
	function placeFor(box, recorded, before) {
		const region = regionForBox(box);
		if (region === void 0) return null;
		const own = region ? region.id : PAGE;
		let found = null;
		for (const [id, entry] of recorded) {
			if (!before && id !== own) continue;
			const node = placeNode(entry.reading);
			const carried = node ? boxOf(node) === box : id === own && (entry.reading.end || rawOffsetFits(entry.reading, box));
			const ranks = !found || entry.at > found.at || entry.at === found.at && id === own;
			if ((carried || id === own || before?.has(id)) && ranks) found = {
				...entry,
				lands: carried || node && under(box, node)
			};
		}
		return found?.lands ? found : null;
	}
	function restoreShifted(shifted, currentIntent, recorded) {
		shifting = false;
		if (compositionChanges.size) return;
		if (!currentIntent()) return;
		const page = shifted.find((shift) => shift.region === null);
		if (page?.band) {
			const from = pageScroller.scrollTop;
			moveScrollerBy(pageScroller, -page.band);
			placeKept(pageScroller);
			wrote(pageScroller, from);
		}
		const boxes = new Map(page ? [[pageScroller, /* @__PURE__ */ new Set()]] : []);
		const returning = /* @__PURE__ */ new Set();
		const touch = (box) => {
			let before = boxes.get(box);
			if (!before) {
				before = /* @__PURE__ */ new Set();
				boxes.set(box, before);
			}
			return before;
		};
		const idOf = (box) => box === pageScroller ? PAGE : readingRegions().find(({ body }) => body === box)?.id;
		for (const shift of shifted) {
			if (shift.region === null || !shownRegionBounds(shift.region)) continue;
			const { from, to, returned } = shift;
			if (returned) returning.add(to);
			touch(to);
			if (from && from !== to && !returned) touch(to).add(idOf(from));
		}
		for (const [box, before] of boxes) {
			const region = regionForBox(box);
			if (region === void 0) continue;
			const place = placeFor(box, recorded, returning.has(box) ? null : before);
			if (!place || readerChose(box, place.choices)) continue;
			const from = box.scrollTop;
			restorePlace(place.reading, region, currentIntent);
			wrote(box, from);
			const offset = placeOffset(place.reading, region);
			if (offset === null) continue;
			holds.set(region ? region.id : PAGE, {
				box: new WeakRef(box),
				reading: place.reading,
				since: inputCount(),
				offset,
				top: box.scrollTop,
				currentIntent
			});
		}
		watchHolds();
		for (const id of [...holds.keys()]) holdOf(id);
	}
	const SETTLING = 12;
	const SETTLING_MS = 1e3;
	let reapplyTimer;
	const stopReapplying = () => {
		reapply?.disconnect();
		clearTimeout(reapplyTimer);
		reapply = null;
	};
	const releaseHolds = () => {
		holds.clear();
		stopReapplying();
	};
	function watchHolds() {
		stopReapplying();
		if (!holds.size) return;
		const again = frameFor(document.documentElement, () => {
			for (const id of [...holds.keys()]) {
				const hold = holdOf(id);
				if (!hold) continue;
				const box = hold.box.deref();
				const region = regionForBox(box);
				if (!box || region === void 0) continue;
				const now = placeOffset(hold.reading, region);
				if (now === null || Math.abs(now - hold.offset) <= 2) continue;
				const from = box.scrollTop;
				restorePlace(hold.reading, region, hold.currentIntent);
				wrote(box, from);
				const offset = placeOffset(hold.reading, region);
				if (offset !== null) hold.offset = offset;
				hold.top = box.scrollTop;
			}
			if (!holds.size) stopReapplying();
		});
		let deliveries = 0;
		const observer = sizeObserver(() => {
			if (reapply !== observer) return;
			if (++deliveries > SETTLING) return stopReapplying();
			again();
		});
		reapply = observer;
		reapplyTimer = setTimeout(stopReapplying, SETTLING_MS);
		const settled = () => nextAnimation(() => {
			if (reapply !== observer) return;
			const { updatesSettled, preparationsSettled } = renderingState();
			if (updatesSettled && preparationsSettled && regionsSettled()) stopReapplying();
			else settled();
		});
		settled();
		const page = pageDocument();
		if (page) reapply.observe(page);
		for (const hold of holds.values()) {
			const box = hold.box.deref();
			if (box && box !== pageScroller) for (const child of box.children) reapply.observe(child);
		}
	}
	const compositionChanges = /* @__PURE__ */ new Map();
	const ownBoxes = (owner) => readingRegions().filter((region) => regionScrollBehavior(region) === "bounded" && under(region.body, owner) && shownRegionBounds(region)).map((region) => region.body);
	function ownRegion(box) {
		const region = regionForBox(box);
		if (!region) throw new Error("A bounded reading box must retain its registered region");
		return region;
	}
	function showSubject(phase, region) {
		const box = region.body;
		const own = regionForBox(box) && box.checkVisibility();
		if (phase === "leaving") {
			if (own) recordPlaces([box]);
			const place = places.get(region.id);
			if (!place) return;
			let subjects = subjectPlaces.get(region.id);
			if (!subjects) {
				subjects = /* @__PURE__ */ new Map();
				subjectPlaces.set(region.id, subjects);
			}
			subjects.set(region.subject, place.reading);
			return;
		}
		holds.delete(region.id);
		const reading = subjectPlaces.get(region.id)?.get(region.subject);
		if (!reading) {
			places.delete(region.id);
			return;
		}
		places.set(region.id, {
			reading,
			at: ++placeCount,
			choices: scrollChoices(),
			inputs: inputCount()
		});
		if (own) restorePlace(reading, regionForBox(box));
	}
	function readingRegionTransition(transition) {
		if ("region" in transition) {
			showSubject(transition.phase, transition.region);
			return;
		}
		if (transition.phase === "shift") {
			const currentIntent = retainUserIntent();
			const recorded = new Map(places);
			shifting = true;
			nextRender(() => restoreShifted(transition.shifted, currentIntent, recorded));
			return;
		}
		const { owner } = transition;
		if (transition.phase === "after" && transition.cancelled || [...compositionChanges.keys()].some((ancestor) => ancestor !== owner && under(owner, ancestor))) {
			compositionChanges.delete(owner);
			return;
		}
		if (transition.phase === "before") {
			const prior = compositionChanges.get(owner);
			if (transition.retained && prior) {
				prior.currentIntent = retainUserIntent();
				return;
			}
			const captured = /* @__PURE__ */ new Map();
			for (const box of ownBoxes(owner)) {
				const region = ownRegion(box);
				const reading = capturePlace(region);
				if (reading) captured.set(region.id, reading);
			}
			compositionChanges.set(owner, {
				currentIntent: retainUserIntent(),
				captured
			});
			return;
		}
		const change = compositionChanges.get(owner);
		compositionChanges.delete(owner);
		if (!change?.currentIntent()) return;
		for (const box of ownBoxes(owner)) {
			const region = ownRegion(box);
			const reading = change.captured.get(region.id) ?? places.get(region.id)?.reading;
			if (reading && (hasLandmark(reading) || rawOffsetFits(reading, box))) restorePlace(reading, region, change.currentIntent);
		}
	}
	function scrollEventBox(event) {
		return event.target === document ? pageScroller : event.target instanceof Element ? event.target : null;
	}
	let readingContinuityInstalled = false;
	function installReadingContinuity() {
		if (readingContinuityInstalled) return;
		readingContinuityInstalled = true;
		watchReadingRegionTransitions(readingRegionTransition);
		const moving = /* @__PURE__ */ new Set();
		let scrolls = 0;
		let resting = false;
		const rest = (seen) => nextRender(() => {
			if (seen !== scrolls) return rest(scrolls);
			resting = false;
			const boxes = [...moving];
			moving.clear();
			recordPlaces(boxes);
		});
		const scrolled = (event) => {
			const box = scrollEventBox(event);
			if (!box) return;
			moving.add(box);
			scrolls++;
			if (resting) return;
			resting = true;
			rest(scrolls);
		};
		document.addEventListener("scroll", scrolled, {
			capture: true,
			passive: true
		});
		document.addEventListener("scrollend", (event) => {
			const box = scrollEventBox(event);
			if (!box) return;
			const written = writing.get(box);
			if (written !== void 0) {
				if (!inputSince(box, written)) ownEnd.set(box, scrollChoices());
				writing.delete(box);
			}
			nextRender(() => recordPlaces([box]));
		}, {
			capture: true,
			passive: true
		});
		for (const type of ["popstate", "hashchange"]) addEventListener(type, releaseHolds);
		const recordCurrentLocation = () => {
			const at = focused();
			if (!at || !under(at, pageDocument())) return;
			const box = boxOf(at);
			recordPlaces([box], { currentLocation: true });
			nextRender(() => recordPlaces([box], { currentLocation: true }));
		};
		onCurrentLocation(recordCurrentLocation);
		onReadingInput(recordCurrentLocation);
		onUserInput((event) => {
			if (event.type === "keydown" || event.type === "input") recordCurrentLocation();
			if (![
				"wheel",
				"touchstart",
				"keydown",
				"pointerdown"
			].includes(event.type)) return;
			const at = event.type === "keydown" ? focused() : event.composedPath()[0];
			const element = at instanceof Element ? at : at instanceof Node ? at.parentElement : null;
			const box = inputBox(element, event);
			touched.set(box, inputCount());
			held(box);
		});
		nextRender(() => recordPlaces([pageScroller, ...readingRegions().filter((region) => regionScrollBehavior(region) === "bounded").map((region) => region.body)]));
	}
	function installArrival() {
		installReadingContinuity();
		const navigationType = performance.getEntriesByType("navigation")[0]?.type;
		const currentRevision = runtime.currentRevision;
		const handoff = (() => {
			const serialized = tabStore.get(HANDOFF_KEY);
			tabStore.set(HANDOFF_KEY, null);
			try {
				const value = JSON.parse(serialized || "null");
				return LIVE_ROOT && currentRevision !== null && navigationType === "reload" && value?.url === location.href && Number.isInteger(value.revision) && value.revision <= currentRevision && Number.isInteger(value.view?.revision) && value.view.revision < currentRevision ? value : null;
			} catch {
				return null;
			}
		})();
		const savedView = (() => {
			try {
				return JSON.parse(tabStore.get(VIEW_KEY) || "null");
			} catch {
				return null;
			}
		})();
		addEventListener("pagehide", () => {
			if (!anchoringIsReady()) return;
			tabStore.set(VIEW_KEY, JSON.stringify(captureView()));
		});
		const currentIntent = retainUserIntent({
			fallback: compositionInput,
			since: 0
		});
		const restoreCarryScroll = handoff && restoreCarry(handoff.carry, /* @__PURE__ */ new Map(), currentIntent.handoff);
		const landArrival = () => landContinuity(async () => {
			if (!currentIntent()) return;
			if (handoff) {
				restorePointer(handoff.pointer);
				restoreView(handoff.view, currentIntent);
				restoreRetainedCurrentLocation(handoff.retainedCurrentLocation);
				restoreCarryScroll();
				await restoreEditingContinuity(handoff, currentIntent);
				if (handoff.comparison) showComparison(handoff.comparison);
				return;
			}
			if (navigationType === "navigate" && !aimedAt && savedView && savedView.revision !== runtime.currentRevision) restoreView(savedView, currentIntent);
		});
		return {
			landArrival,
			savedView
		};
	}
	let aimedAt = null;
	function aimArrival() {
		const fresh = performance.getEntriesByType("navigation")[0]?.type === "navigate";
		const arrivedAt = location.hash;
		const currentIntent = retainUserIntent({ since: 0 });
		return function landFragment() {
			aimedAt ??= fresh && fragmentTarget(arrivedAt);
			if (!aimedAt || !currentIntent()) return;
			reveal(aimedAt, currentIntent);
			scrollToFragment(aimedAt);
		};
	}
	function mount() {
		versionPicker.configure({
			activate: (entry) => {
				if (entry.version !== null) goVersion(entry.version);
				else if (entry.active) goActive();
			},
			compare: pressComparison,
			latest: goActive
		});
		x(paintPicker);
	}
	return {
		PICKER,
		prepareActivation,
		aimArrival,
		installArrival,
		mount
	};
}

//#endregion
//#region runtime/data.js
function acceptData(candidate, taken) {
	return applicationState.acceptData(candidate, taken);
}
const joined = /* @__PURE__ */ new Set();
async function notifyDataSubscribers() {
	const version = runtime.data.version;
	tick(deliveries);
	await whenApplicationRegionsPresented([...joined], () => runtime.data.version === version);
	if (version !== null && runtime.data.version === version) setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.dataVersion, version);
}
const declaredInput = (element, input) => {
	const declaration = registry$1[element.localName]?.["x-data"]?.[input];
	if (!declaration) throw new Error(`<${element.localName}> input ${input} is not declared by this widget`);
	return declaration;
};
const outputObservers = /* @__PURE__ */ new Set();
function observeOutputs(observe) {
	outputObservers.add(observe);
	return () => outputObservers.delete(observe);
}
const outputOwners = /* @__PURE__ */ new WeakMap();
const outputKeys = /* @__PURE__ */ new WeakMap();
let outputSequence = 0;
function outputKey(element) {
	let key = outputKeys.get(element);
	if (key === void 0) {
		key = `output:${++outputSequence}`;
		outputKeys.set(element, key);
	}
	return key;
}
function publishOutput(element, output, value) {
	const declaration = registry$1[element.localName]?.["x-output"]?.[output];
	if (!declaration) throw new Error(`publishOutput(${element.localName}, ${output}) output is not declared by this widget`);
	if (!element.id) throw new Error("publishOutput requires a widget id");
	let owner = outputOwners.get(element);
	if (!owner) {
		const connectedOwner = {
			values: /* @__PURE__ */ new Map(),
			connected: false
		};
		owner = connectedOwner;
		outputOwners.set(element, owner);
		watchOwner(element, {
			connect() {
				connectedOwner.connected = true;
				for (const [name, reading] of connectedOwner.values) applicationState.publishOutput(outputKey(element), name, reading);
			},
			disconnect() {
				connectedOwner.connected = false;
				for (const name of connectedOwner.values.keys()) applicationState.publishOutput(outputKey(element), name, null);
			}
		});
	}
	const reading = value === null ? null : {
		contract: declaration.contract,
		value: structuredClone(value)
	};
	for (const observe of outputObservers) observe({
		element,
		output,
		contract: declaration.contract,
		value: reading === null ? null : reading.value
	});
	owner.values.set(output, reading);
	if (owner.connected) applicationState.publishOutput(outputKey(element), output, reading);
}
function inputBinding(element, declaration, input) {
	const source = declaration.source ? element.getAttribute(declaration.source) : null;
	const referenced = declaration.reference ? {
		attribute: declaration.reference,
		output: declaration.output,
		widget: element.getAttribute(declaration.reference)
	} : null;
	const widget = referenced?.widget;
	if (source && widget) throw new Error(`<${element.localName}> input binds both an external source and widget output`);
	if (declaration.reference) requireReference("data", element, declaration.reference);
	return {
		source,
		widget,
		selected: applicationState.select((root) => {
			if (source) {
				const reading = Object.hasOwn(root.data.sources, source) ? root.data.sources[source] : null;
				return reading ? {
					source,
					...reading,
					origin: {
						input,
						source,
						contract: declaration.contract,
						revision: reading.revision
					}
				} : null;
			}
			if (!referenced?.widget) return null;
			const producer = referencedProjection(element, referenced.attribute, referenced.widget);
			if (!producer) return null;
			const key = outputKey(producer);
			const outputs = Object.hasOwn(root.outputs, key) ? root.outputs[key] : null;
			const reading = outputs && Object.hasOwn(outputs, referenced.output) ? outputs[referenced.output] : null;
			return reading ? {
				...reading,
				origin: { derived: [{ widget: referenced.widget }] }
			} : null;
		})
	};
}
const supplied = /* @__PURE__ */ new WeakMap();
const suppliedSnapshot = (value) => supplied.get(value);
const bindsInput = (element, { source, reference }) => Boolean(source && element.getAttribute(source) || reference && element.getAttribute(reference));
const dataRead = applicationState.select((root) => root.data.version !== null || root.phase === "offline");
function awaitsData(element) {
	return Object.values(registry$1[element.localName]?.["x-data"] ?? {}).some((declaration) => declaration.source && element.getAttribute(declaration.source)) && !dataRead.read();
}
function dataReader(element, input, accepted) {
	const declaration = declaredInput(element, input);
	const { source, widget, selected } = inputBinding(element, declaration, input);
	let stopAccepted = null;
	const delivered = J(() => {
		deliveries.value;
		return d(selected.read);
	}, {
		watched() {
			let seen = d(selected.read);
			stopAccepted = selected.subscribe((now) => {
				if (now === seen) return;
				seen = now;
				accepted();
			});
		},
		unwatched() {
			stopAccepted?.();
			stopAccepted = null;
		}
	});
	let reported = null;
	let copied = null;
	return () => {
		const sourceStore = widget ? selected.read() : delivered.value;
		const incompatible = sourceStore && sourceStore.contract !== declaration.contract;
		if (incompatible && reported !== sourceStore) {
			reported = sourceStore;
			reportPageError(`${source ? `data source ${source}` : `widget output ${widget}.${declaration.output}`} carries contract ${sourceStore.contract}; <${element.localName}> input ${input} requires ${declaration.contract}`);
		}
		if (incompatible || !sourceStore || !Object.hasOwn(sourceStore, "value")) return null;
		if (sourceStore !== copied?.store) {
			copied = {
				store: sourceStore,
				value: structuredClone(sourceStore)
			};
			const { value } = copied.value;
			if (value !== null && typeof value === "object") supplied.set(value, copied.value);
		}
		return copied.value;
	};
}
const deliveries = Z(0);
function joinDataDelivery(region) {
	joined.add(region);
	return () => joined.delete(region);
}
async function loadDeferred(value, key) {
	const manifest = supplied.get(value);
	if (!manifest?.source) throw new Error(`loadDeferred(${key}) needs a source value Leaf delivered`);
	const { source, revision } = manifest;
	const current = () => {
		const reading = runtime.data.sources[source];
		return reading?.revision === revision && reading.contract === manifest.contract && Object.hasOwn(reading, "value");
	};
	if (!current()) throw new Error(`source ${source} revision ${revision} changed before loading deferred ${key}`);
	if (offlineInteractive) {
		const records = registry$1.$data.contracts[manifest.contract].records;
		const item = offlineData().sources[source].value[records.items].find((item) => item[records.key] === key);
		if (!item) throw new Error(`unknown record key '${key}' in data source '${source}'`);
		if (!Object.hasOwn(item, records.deferred)) throw new Error(`record '${key}' in data source '${source}' has no deferred field '${records.deferred}'`);
		return structuredClone(item[records.deferred]);
	}
	const params = new URLSearchParams({
		source,
		source_revision: revision,
		key
	});
	const answer = await requestJson(pageUrl(`api/deferred?${params}`), {}, "deferred value");
	if (!current()) throw new Error(`source ${source} revision ${revision} changed while loading deferred ${key}`);
	return structuredClone(answer.value);
}

//#endregion
export { DESIGN_MODE_KEY, ELEMENTS, HOLDS_WORD, HeldNews, HeldReading, MessageView, NOT_ANSWERED, PAGE_DRAFT, PAGE_SCOPE, RESOLVED, SAYS_IN, SAY_BOX, THREAD, ThreadView, Transcript, aborted, acceptData, allButCommandReference, allThreads, anchorLabel, answeredInWords, arrivalOf, authoredHolder, authoredStates, awaitsData, beginThreadSeats, beginWalk, bindsInput, blocksOnScreen, bringBackSurfaceOf, captureDraftEditing, capturePlace, carryingThreadPlace, claimSeatReplies, claimTraversals, claimed, clearDraft, commandSteps, commitThreadSeats, commitWidgetDescriptors, comparisonBase, comparisonChanges, completeReadingReturn, copyBlock, createAnchorTravel, createPassageSelection, createProjectionPresentation, createReplyView, createRewriteRestore, createVersionController, createWritingResume, currentLocationOrigin, currentLocationThreadId, dataReader, declareOffFlowSurface, declareSide, declareThreadParts, descriptorStillMatches, designName, dismissReply, dismissReplyAt, domValue, draftContexts, draftHasContent, draftStore, drawnThreadId, externalMark, focusThread, focusedThreadTarget, followBoxGrowth, gesturedOn, heldGrowth, heldObligation, heldOut, heldPagePlace, heldThread, highlightBlocks, holdPagePlace, holdReplyCompositions, holdThreadPlace, holdToRead, initializeServedDocument, inlineComparison, inlineMarkdownFragment, isBlockPlacement, isExternalPageLink, isPageWidgetWorkflow, isWorkflowProgress, joinDataDelivery, keepRefusedWords, keepThreadLanding, keepView, landingPlace, langForPath, leftThePage, listWalkPosition, loadDeferred, loadDraft, loadMarkdown, loadMessageMarkdown, markdownReady, markdownSourceOffset, markdownWords, messageHolding, messageReading, messageText, mirrorDraft, mountFirstMessage, mountHistory, newsCount, newsNotice, notifyDataSubscribers, obligationEntry, obligationHolding, obligationPlace, obligationsIn, observeOutputs, offerComparison, onReadingInterrupted, openMessageEditIn, openingView, opensElsewhere, orderChildren, pageCommand, pageDoor, pageRung, pageScope, pageScopes, pageSelection, paintCoreControls, paintMarkdown, placeKeeper, placeNode, placeOf, placePageThreads, placedMarkdownTokens, prepareAuthoredMessage, prepareDocument, progressFace, publishOutput, pushEntry, quoteReading, quoted, readBoxPlace, readObligations, readPlace, readThreads, readingBlock, readingIsContinuous, readingReturn, registerWritingDestination, releaseAuthoredUnder, releaseOutlets, releaseReplies, rememberWriting, renderMarginThread, renderMarkdown, renderSeats, renderSurfaces, replaceEntry, replyCompositionHasDraft, replyContext, replyDraftContext, replyDraftsHold, replyIsEditing, replyThreadKey, restorePlace, retainThreadSeats, returnPlace, revealHeld, revisionBase, rowWalk, saveDraft, scrollThreadIntoView, selectionAnchor, sendDraft, sendLanding, sendMessage, servedElements, setChildLists, setChildren, setRenderedChildren, settleAcceptedDrafts, settleThread, shallowSigs, showHeld, showHeldThread, showReturnTurn, snapSelection, stances, stepFrom, stopComparison, storedDraft, strongestWorkflow, subjectPlace, suppliedSnapshot, surfaceFocusTarget, takeInitialDocument, tellDraft, textEntryScopes, threadAttention, threadDraft, threadFocusDestination, threadHeading, threadIdNamed, threadIn, threadList, threadName, threadNamed, threadPart, threadReading, threadReplyInput, threadRewrites, threadState, threadSummary, threadSurface, threadTodos, titlePending, todoWord, toggleInlineComparison, touchPresses, transferDraft, universalCommandReference, upgradeWidgets, userChoice, userStore, versionPicker, versionsReading, viewMembers, walkOrigin, walkPosition, walkPositionLabel, watchDraft, watchDrafts, watchThreadSurfaces, whereDraft, wholeThread, widgetDescriptor, workflowStep, workflowWord };