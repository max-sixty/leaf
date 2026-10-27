import { J, W, Z, d, x } from "./bundle-signals-core.js";
import { PRESSES, TEXT_BOX, deepFocus, drawn, focusDestination, focused, inputCount, keeps, move, nextAnimation, nextRender, onCurrentLocation, onUserInput, readCaret, renderingState, sizeObserver, typesText, under, upFrom } from "./bundle-dom-move.js";
import { LayerRefused, PAGE_PAINT_ATTRIBUTE, admitReading, reportPageError, requestJson, runtimeRootState, setRuntimeRootAttribute } from "./bundle-layer-client.js";
import { clippedPlace, decisionFor, frameFor, landingBand, placeBox, placeHolder, presented, registry, shownBox, skipped, tagsDeclaring, watchOwner } from "./bundle-geometry.js";
import { LIVE_ROOT, PRESENTATION_DOM, TEXT_BLOCK, applicationPresenter, applicationState, foldWidgetStates, layerRoot, obligationValue, offlineData, offlineInteractive, pageUrl, projectView, projectionOrigins, projectionRegionsPresented, readApplication, readPart, revisionLabel, runtime, tick, watchPresentation, whenApplicationRegionsPresented } from "./bundle-context.js";
import { PRESSABLE, ariaShortcuts, bindings, buttonCommand, commandAvailable, commandRoutes, el, holdingError, labelOf, layoutChanged, live, notice, pointerAt, pruneScopedElements, raiseError, repaint, restorePointer, reveal, savedReadingSettled, spell, word } from "./bundle-errors.js";
import { chosenSince, containingReadingRegionFor, effectiveScroller, moveScrollerBy, onReadingInput, pageScroller, placeKept, readingRegionFor, readingRegions, recentReadingRegion, regionScrollBehavior, regionsSettled, scrollChainOf, scrollChoices, scrollLimit, scrollersOf, shownRegionBounds, stopScroll, unconcealedReadingRegions, watchReadingRegionTransitions } from "./bundle-reading-regions.js";
import { PAGE_CONTROL_RANK, registerPageControl } from "./bundle-page-controls.js";
import { alignInlineText, authored, authoredScope, closestAcross, elementById, inChrome, pageDocument, pageQueryAll, pageRange, rangeOf, readingFrom, renderRetired, selectEnds, selectionBackward, textNodesUnder, wrote } from "./bundle-passages.js";
import { ADDRESSABLE, addressedElements, anchoringIsReady, fragmentTarget, livePoint, resolveAnchor, revealAddressed, sectionOf, settleMarginContentLayout, targetElement, targetPlace, targetSegments } from "./bundle-content-layout.js";
import { authoredBody, initialOrigin, restoreInitialSource, unmarkedCopy } from "./bundle-initial-render.js";
import { restrictUserIntent, retainUserIntent, scrollIntoView } from "./bundle-copy-control.js";
import { PAGE_SCOPE, blocksOnScreen, captureDraftEditing, capturePlace, draftEditingDestination, draftEditingStands, focusedInView, formatDeclaredMarkdown, hasLandmark, heldThreadId, inlineMarkdownFragment, isPagePaint, openingPassage, pageReadingBlock, pageScopes, paintMarkdown, passageBlock, patchDocument, placeNode, placeOf, placeOffset, preloadWidgets, prepareDeclaredMarkdown, rawOffsetFits, reindexPassageOwners, rememberPassageParts, renderQuiet, replyDestination, restoreDraftEditing, restorePlace, restoreReplyEditing, tabStore, textBlocks, threadNamed } from "./bundle-surfaces.js";
import { authoredStates, commitWidgetDescriptors, patchRetains, patchTree, quoted, rememberAuthoredParents, stageAuthoredStates, stageWidgetDescriptors, widgetElement } from "./bundle-abort.js";
import { backgroundFlash, flashDuration, scrollBehavior } from "./bundle-motion.js";

//#region runtime/document-identity.js
const servedRevision = document.querySelector("meta[name=\"lf-revision\"][data-lf-runtime]")?.content;
const servedStampMarker = document.querySelector("meta[name=\"lf-version\"][data-lf-runtime]");
const servedExecutable = document.querySelector("meta[name=\"lf-executable\"][data-lf-runtime]")?.content;
const documentWidgetDigests = (doc) => {
	const stated = doc.querySelector("meta[name=\"lf-widgets\"][data-lf-runtime]")?.content;
	return stated ? JSON.parse(stated) : {};
};
const servedWidgets = documentWidgetDigests(document);
function initializeServedDocument() {
	applicationState.identify(servedRevision ? parseInt(servedRevision, 10) : null, servedStampMarker ? parseInt(servedStampMarker.content, 10) : null, LIVE_ROOT);
	servedStampMarker?.remove();
}

//#endregion
//#region runtime/history.js
const claims = /* @__PURE__ */ new Set();
const places = /* @__PURE__ */ new Map();
function readPlace(focus = deepFocus()) {
	const place = placeOf(focus);
	const selection = getSelection();
	const range = selection.rangeCount ? pageRange(selection) : null;
	const ends = range && [[new WeakRef(range.startContainer), range.startOffset], [new WeakRef(range.endContainer), range.endOffset]];
	if (ends && selectionBackward(selection, range)) ends.reverse();
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
	const ends = checkpoint.ends?.map(([ref, offset]) => {
		const node = ref.deref();
		const length = node?.nodeType === 3 ? node.length : node?.childNodes.length;
		return [node, Math.min(offset, length ?? offset)];
	});
	if (focus !== document.body && focus?.isConnected && presented(focus)) {
		focusDestination(focus, "return", { caret });
		if (caret) return;
	} else if (place?.isConnected && presented(place)) focusDestination(place, "return");
	else deepFocus()?.blur();
	getSelection().removeAllRanges();
	if (ends?.every(([node]) => node && drawn(node.nodeType === 1 ? node : upFrom(node)))) selectEnds(...ends);
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
		const arrival = [scrollX, scrollY];
		if (window.location.href !== sourceUrl || history.state !== sourceState) replaceEntry(sourceUrl, sourceState);
		window.scrollTo({
			left: offset[0],
			top: offset[1],
			behavior: "instant"
		});
		pushEntry(url, state);
		window.scrollTo({
			left: arrival[0],
			top: arrival[1],
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
	window.navigation?.addEventListener("navigate", (event) => {
		if (!event.destination.sameDocument || !event.canIntercept) return;
		const url = new URL(event.destination.url);
		if (event.navigationType !== "replace") {
			const live = new Set(window.navigation.entries().map((entry) => entry.key));
			for (const key of places.keys()) if (!live.has(key)) places.delete(key);
			const key = window.navigation.currentEntry?.key;
			if (key) places.set(key, readPlace());
		}
		if (event.navigationType === "traverse") {
			const handler = claimed(url) ?? returnToFragment(url);
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
						if (place) window.scrollTo({
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
			handler
		});
	});
}
function claimed(url) {
	for (const claim of claims) {
		const handler = claim(url);
		if (handler) return handler;
	}
	return null;
}

//#endregion
//#region runtime/page-sheets.js
const APPARATUS = ":not(:where(.lf-chrome, .lf-chrome *, .lf-ui, .lf-ui *))";
const narrowed = /* @__PURE__ */ new WeakSet();
function members(text) {
	const found = [];
	let depth = 0;
	let quote = null;
	let start = 0;
	let pseudo = -1;
	for (let at = 0; at < text.length; at++) {
		const ch = text[at];
		if (quote) {
			if (ch === "\\") at++;
			else if (ch === quote) quote = null;
		} else if (ch === "\"" || ch === "'") quote = ch;
		else if (ch === "\\") at++;
		else if (ch === "(" || ch === "[") depth++;
		else if (ch === ")" || ch === "]") depth--;
		else if (depth === 0 && ch === ",") {
			found.push([text.slice(start, at), pseudo < 0 ? -1 : pseudo - start]);
			start = at + 1;
			pseudo = -1;
		} else if (depth === 0 && pseudo < 0 && ch === ":" && text[at + 1] === ":") pseudo = at;
	}
	found.push([text.slice(start), pseudo < 0 ? -1 : pseudo - start]);
	return found;
}
function narrow(member, pseudo) {
	const selector = pseudo < 0 ? member.trimEnd() : member.slice(0, pseudo);
	const rest = pseudo < 0 ? "" : member.slice(pseudo);
	return selector + APPARATUS + rest;
}
function narrowRules(rules) {
	for (const rule of rules) {
		if (rule instanceof CSSKeyframesRule || rule instanceof CSSImportRule) continue;
		if (rule instanceof CSSStyleRule) {
			const next = members(rule.selectorText).map(([member, pseudo]) => narrow(member, pseudo)).join(", ");
			if (next !== rule.selectorText) rule.selectorText = next;
		}
		if (rule.cssRules) narrowRules(rule.cssRules);
	}
}
function narrowSheet(sheet, runtime) {
	const owner = sheet.ownerNode;
	if (owner?.hasAttribute?.("data-controls")) return;
	if (sheet.href && new URL(sheet.href).origin !== window.origin && !owner?.hasAttribute?.("crossorigin")) return;
	if (!narrowed.has(sheet)) {
		narrowed.add(sheet);
		if (!runtime) narrowRules(sheet.cssRules);
		else for (const rule of sheet.cssRules) if (rule instanceof CSSLayerBlockRule && rule.name === "lf-theme") narrowRules(rule.cssRules);
	}
	for (const rule of sheet.cssRules) if (rule instanceof CSSImportRule && rule.styleSheet) narrowSheet(rule.styleSheet, runtime);
}
let watching = false;
function keepPageRulesOffLayer() {
	for (const sheet of document.styleSheets) {
		const owner = sheet.ownerNode;
		if (owner) narrowSheet(sheet, owner.hasAttribute("data-lf-runtime"));
	}
	if (watching) return;
	watching = true;
	document.addEventListener("load", (event) => {
		if (event.target instanceof Element && event.target.matches("link[rel~=\"stylesheet\" i], style")) keepPageRulesOffLayer();
	}, true);
	new MutationObserver(keepPageRulesOffLayer).observe(document.head, {
		childList: true,
		subtree: true,
		characterData: true
	});
}

//#endregion
//#region runtime/projection/presentation.js
function paintStateOrigins(projection) {
	const marks = new Map([PAGE_PAINT_ATTRIBUTE.userOverride, PAGE_PAINT_ATTRIBUTE.reported].map((attr) => [attr, /* @__PURE__ */ new Set()]));
	for (const { origin, unit } of projectionOrigins(authoredStates(), projection)) {
		if (origin === "restated") continue;
		const target = elementById(unit);
		if (!target || inChrome(target)) continue;
		const attr = origin === "user" ? PAGE_PAINT_ATTRIBUTE.userOverride : PAGE_PAINT_ATTRIBUTE.reported;
		marks.get(attr).add(target);
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
		const outcome = state[decision.verb]?.detail?.outcome ?? null;
		keeps(owner, PAGE_PAINT_ATTRIBUTE.settlement, decision.retires[outcome] ? outcome : null);
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
			return !target || target.terminal || projectionRegionsPresented([target.e.widget]);
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
		const attrs = Object.fromEntries([...node.attributes].filter((attribute) => !isPagePaint(attribute.name)).map((attribute) => [attribute.name, attribute.value]).sort(([left], [right]) => left.localeCompare(right)));
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
//#region runtime/carry.js
const holdsValue = (node) => node.matches(TEXT_BOX) || node.tagName === "INPUT" && node.type !== "file";
const holdsTick = (node) => node.tagName === "INPUT" && (node.type === "checkbox" || node.type === "radio");
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
		const focusPart = node === partOwner;
		if (node === active || focusPart) {
			record.focus = true;
			if (focusPart) {
				record.part = active.getAttribute("data-lf-carry");
				record.partName = active.localName;
			}
		}
		if (node.localName === "details" && node.open !== wrote.open) record.open = node.open;
		if (!skipped(node)) {
			if (node.scrollTop && !regionBodies.has(node)) record.scrollTop = node.scrollTop;
			if (node.scrollLeft) record.scrollLeft = node.scrollLeft;
		}
		if (holdsValue(node) && node.value !== wrote.value) record.value = node.value;
		if (holdsTick(node) && node.checked !== wrote.checked) record.checked = node.checked;
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
		if (record.open !== void 0) arrived.open = record.open;
		if (record.value !== void 0 && holdsValue(arrived)) arrived.value = record.value;
		if (record.checked !== void 0 && holdsTick(arrived)) arrived.checked = record.checked;
		positions.push([arrived, record]);
	}
	const restoreFocus = (parts) => handoffFocus(() => {
		for (const [arrived, record] of positions) {
			if (!record.focus || record.part !== void 0 !== parts) continue;
			const target = record.part === void 0 ? arrived : [...arrived.querySelectorAll(`[data-lf-carry="${CSS.escape(record.part)}"]`)].find((node) => node.parentElement?.closest("[id]") === arrived && node.localName === record.partName);
			if (target) focusDestination(target, "return", { caret: record.caret });
		}
	});
	restoreFocus(false);
	return () => {
		for (const [arrived, record] of positions) {
			if (!arrived.isConnected) continue;
			if (record.scrollTop) arrived.scrollTop = record.scrollTop;
			if (record.scrollLeft) arrived.scrollLeft = record.scrollLeft;
		}
		restoreFocus(true);
	};
}

//#endregion
//#region runtime/keyboard/control-keys.js
const stepsBefore = (scope) => word(scope?.sequencePrefix ?? scope?.sequence) ?? [];
const stepsIn = (scope, row) => [...stepsBefore(scope), labelOf(row)].filter(Boolean);
function commandSteps(id) {
	for (const scope of pageScopes()) for (const row of scope?.rows ?? []) if (row.id === id && bindings(row).length) return stepsIn(scope, row);
	return [];
}
function* namedControls(row) {
	if (row.control) yield {
		control: row.control,
		active: live(row) && bindings(row).length > 0,
		press: labelOf(row),
		shortcuts: () => ariaShortcuts([row], false)
	};
	for (const route of commandRoutes(row)) if (route.control) yield {
		control: route.control,
		active: commandAvailable(row, route) && bindings(row).includes(route.binding),
		press: spell(route.binding),
		shortcuts: () => ariaShortcuts([{ keys: [route.binding] }], false)
	};
}
function controlRows() {
	const controls = /* @__PURE__ */ new Map();
	for (const scope of pageScopes()) for (const row of scope?.rows ?? []) for (const named of namedControls(row)) {
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
		if (!("lfKeyTitle" in control.dataset)) control.dataset.lfKeyTitle = control.title;
		const steps = [...stepsBefore(scope), press].filter(Boolean).join(" ");
		keeps(control, "title", control.dataset.lfKeyTitle + (active ? ` (${steps})` : ""));
		if (buttonCommand(control)) continue;
		keeps(control, "aria-keyshortcuts", active && !scope.sequence ? shortcuts() : null);
	}
}

//#endregion
//#region runtime/references.js
function requireReference(verb, owner, attribute) {
	if (typeof attribute !== "string" || !Object.hasOwn(registry[owner.localName]?.["x-refers"] ?? {}, attribute)) throw new TypeError(`${verb} ${owner.localName} attribute ${String(attribute)} is not declared by x-refers`);
}
function referencedProjection(owner, attribute, id = owner.getAttribute(attribute)) {
	if (!id) return null;
	const { tag, key } = registry[owner.localName]["x-refers"][attribute];
	if (tag) {
		const within = registry[tag]["x-unique"][key];
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
function createAnchorTravel({ anchors, refreshThread, focusForNavigation, threadFocusTarget, announce }) {
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
		const initial = intent() && resolve();
		if (!initial?.where) return false;
		if (initial.scroll.length) await stopScroll(/* @__PURE__ */ new Set([pageScroller, ...unconcealedReadingRegions().map((region) => region.body)]));
		if (!intent()) return false;
		const first = resolve();
		const holder = first && placeHolder(first.where);
		if (!holder || !intent()) return false;
		const disclosures = [holder, ...first.reveal ?? []].map((target) => reveal(target, intent));
		const replacedView = disclosures.some((disclosure) => disclosure.replacedView);
		const place = (complete = false) => {
			let completed = false;
			intent.handoff(() => {
				const destination = resolve();
				if (!destination?.where) return;
				if (destination.focus) focusForNavigation(destination.focus, "move", { caret: destination.caret });
				const current = resolve();
				if (!current?.where) return;
				if (complete) departure?.commit();
				if (current.selection) {
					const { range, backward } = current.selection;
					const head = [range.startContainer, range.startOffset];
					const tail = [range.endContainer, range.endOffset];
					selectEnds(...backward ? [tail, head] : [head, tail]);
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
		const source = anchor.datum && sectionOf(anchor);
		if (!destination && !source) return false;
		const departure = prepareNavigationStep({
			intent: mayArrive,
			landing: () => resolve()?.where
		});
		departure.plan(destination?.where ?? source, { there: (readable) => Boolean(destination && readable(destination.where)) });
		if (source) {
			const hydration = revealAddressed(source, anchor.datum);
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
		let release = null;
		await arrive(() => {
			const current = resolve();
			const input = current?.input();
			return current && {
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
					release = current.open();
				});
				await current.present?.();
			}
		});
		if (typeof release === "function") release();
		return mayArrive() ? resolve()?.input() ?? null : void 0;
	}
	function prepareNavigationStep({ landing = null, url, intent }) {
		const write = prepareEntry();
		const continuing = landing && stillLanded();
		const arrival = landing && {
			landing,
			passage: () => openingPassage(landing())
		};
		let moving;
		return {
			plan(where, { there = (readable) => readable(where) } = {}) {
				moving = !(where && there(readableDestination));
				return moving;
			},
			commit() {
				if (moving === void 0) return;
				if (!moving) {
					if (continuing) Object.assign(navigationGroup, arrival);
					return;
				}
				navigationGroup = arrival && {
					token: navigationGroupPrefix + ++navigationSteps,
					...arrival
				};
				write(url ?? window.location.href, navigationGroup && { lfNavigationGroup: navigationGroup.token }, continuing);
			}
		};
	}
	function followFragment(url) {
		return fragmentTarget(url.hash) && fragmentNavigationStep(url, true);
	}
	function returnToFragment(url) {
		const where = fragmentTarget(url.hash);
		return where && !where.checkVisibility() ? fragmentNavigationStep(url, false) : null;
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
			if (missing) announce(missing);
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
			if (missing) announce(missing);
			return false;
		}
		const destination = addressedElements(source, key)[0] ?? null;
		departure.plan(destination);
		if (!destination) {
			await arrive(() => {
				const where = referencedProjection(owner, attribute);
				return where && {
					where,
					focus: null,
					scroll: [{
						at: where,
						block: "start"
					}]
				};
			}, {
				intent: mayArrive,
				departure
			});
			if (mayArrive() && missing) announce(missing);
			return false;
		}
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
		if (mayArrive() && (arrived ? success : missing)) announce(arrived ? success : missing);
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
		const hydrating = anchor?.datum && status !== "outdated" || anchor?.visual;
		const destination = threadDestination(id);
		const landing = () => threadDestination(id);
		const departure = history ? prepareNavigationStep({
			landing,
			intent: mayArrive
		}) : null;
		if (destination || hydrating) departure?.plan(destination);
		if (hydrating) {
			const source = sectionOf(anchor);
			const hydration = source && revealAddressed(source, anchor.visual ?? anchor.datum);
			if (hydration?.then) await hydration;
			if (!mayArrive() || sectionOf(anchor) !== source) return false;
			await refreshThread();
			if (!mayArrive()) return false;
		}
		return arrive(() => {
			const where = threadDestination(id);
			if (!where) return null;
			const target = focus && part && threadFocusTarget(id, { part });
			return {
				where,
				focus: target,
				scroll: [...target ? [{
					at: target,
					block: "nearest"
				}] : [], {
					at: where,
					when: () => !readableDestination(where)
				}]
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
	root = document.documentElement.lfInitial.authoredShell(root);
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
const pairSources = (source, live, pairs) => {
	live = initialOrigin(source) === source ? live : initialOrigin(source);
	pairs.set(source, live);
	const held = source.localName === "template" ? source.content : source;
	const children = [...(live.localName === "template" ? live.content : live).childNodes].filter((child) => !child.matches?.("[data-lf-prepaint], script[data-lf-initial]"));
	for (const [at, child] of [...held.childNodes].entries()) {
		const original = initialOrigin(child);
		const peer = original === child ? children[at] : original;
		if (peer) pairSources(child, peer, pairs);
	}
	return pairs;
};
let initialDocument = (() => {
	const main = pageDocument();
	const source = main ? unmarkedCopy(main) : null;
	return {
		authoredBodyAttributes: authoredAttributes(document.body),
		authoredHeadNodes: new Set([...document.head.children].filter(versionedHeadNode)),
		authoredHtmlAttributes: authoredAttributes(document.documentElement),
		source,
		pairs: main ? pairSources(source, main, /* @__PURE__ */ new WeakMap()) : /* @__PURE__ */ new WeakMap()
	};
})();
const stamped = (version) => runtime.versions.find((candidate) => candidate.version === version);
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
const shownBehind = () => runtime.currentStamp === null ? "An older draft" : runtime.active.version === null ? `v${runtime.currentStamp}` : `v${runtime.currentStamp} of ${runtime.active.version}`;
function menuRows(state, notes) {
	const latest = state.versions.at(-1)?.version;
	const entries = state.versions.map((entry) => ({
		revision: entry.revision,
		version: entry.version,
		name: `v${entry.version}${entry.version === latest ? " (latest version)" : ""}`,
		note: notes[entry.version] ?? null,
		current: entry.version === runtime.currentStamp,
		active: false,
		comparable: comparable(entry.version)
	}));
	for (const revision of draftRevisions()) {
		const active = revision === state.active.revision;
		entries.push({
			revision,
			version: null,
			name: `${active ? "Current" : "This view"} · ${revision === runtime.currentRevision ? runtime.currentLabel ?? revisionLabel(revision) : state.active.label}`,
			note: null,
			current: revision === runtime.currentRevision,
			active,
			comparable: false
		});
	}
	entries.sort((left, right) => right.revision - left.revision || (right.version ?? Infinity) - (left.version ?? Infinity));
	return Object.freeze(entries.map((entry) => Object.freeze(entry)));
}
function pickerModel(state) {
	const offered = state !== null && versionsOffered();
	const behind = behindCurrent();
	const sourceFailed = LIVE_ROOT && Boolean(state?.source_error);
	const currentLabel = runtime.currentLabel ?? "Draft";
	const newer = behind ? `; ${runtime.active.label} available` : "";
	return Object.freeze({
		picker: Object.freeze({
			offered,
			token: currentVersionToken(),
			compared: diffOn.value || diffPendingBase.value !== null,
			news: behind,
			keyTitle: offered ? diffPendingBase.value !== null ? `${currentLabel}: loading a comparison with v${diffPendingBase.value}${newer}` : diffOn.value ? `${currentLabel}: showing what changed since v${diffBase.value} — pick a version, or press Compare again to stop${newer}` : `${currentLabel}: versions; read one, or mark what changed since it${newer}` : currentLabel,
			ariaLabel: offered ? diffPendingBase.value !== null ? `${currentLabel}: loading comparison with v${diffPendingBase.value}; open versions${newer}` : diffOn.value ? `${currentLabel}: comparing with v${diffBase.value}; open versions${newer}` : `${currentLabel}: open versions${newer}` : currentLabel
		}),
		latest: Object.freeze({
			failed: sourceFailed,
			error: sourceFailed ? state.source_error : null,
			disabled: sourceFailed,
			keyTitle: sourceFailed ? state.source_error : "Open the current page",
			label: latestVersionLabel({
				failed: sourceFailed,
				activeLabel: behind ? runtime.active.label : null
			}),
			shown: behind ? shownBehind() : null,
			news: sourceFailed || behind
		}),
		rows: state === null || runtime.active === null ? Object.freeze([]) : menuRows(state, runtime.browser?.version_notes ?? {}),
		selection: Object.freeze({
			base: diffPendingBase.value ?? (diffOn.value ? diffBase.value : null),
			currentRevision: runtime.currentRevision,
			on: diffOn.value,
			pendingBase: diffPendingBase.value,
			baseRevision: stamped(diffBase.value)?.revision ?? null
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
	...tagsDeclaring((e) => e["x-verbatim"])
].join(",");
const diffOpaqueSel = () => [
	...tagsDeclaring((e) => e["x-upgrade"] && !e["x-verbatim"] && e["x-content"] === "data"),
	...tagsDeclaring((e) => e["x-upgrade"] && e["x-data"]),
	...Object.entries(registry.$decisions).filter(([, { retires }]) => Object.keys(retires).length).map(([owner]) => owner),
	"svg"
].join(",");
const diffOn = Z(false);
const diffBase = Z(null);
const comparisonGeneration = Z(0);
const diffPendingBase = Z(null);
const diffMarked = /* @__PURE__ */ new Set();
const diffBefore = /* @__PURE__ */ new Map();
const inlineOpen = /* @__PURE__ */ new Map();
let diffRequest = 0;
function diffWords(block) {
	if (!block.querySelector("[data-lf-source-words]")) return wrote(block);
	const source = block.cloneNode(true);
	for (const island of source.querySelectorAll("[data-lf-source-words]")) island.replaceWith(document.createTextNode(island.dataset.lfSourceWords));
	return wrote(source);
}
function diffBlocks(root) {
	const pairs = [];
	const [blocks, opaque] = [diffBlockSel(), diffOpaqueSel()];
	const authoredHere = authored(root);
	for (const body of root.querySelectorAll(".lf-markdown-body")) {
		const owner = body.parentElement;
		if (inChrome(owner) || owner.closest(opaque)) continue;
		pairs.push([owner, `markdown:${body.dataset.lfSourceWords}`]);
	}
	for (const b of root.querySelectorAll(blocks)) {
		if (inChrome(b) || b.closest(opaque) || b.closest(".lf-markdown-body")) continue;
		if (b.querySelector(blocks)) continue;
		let key = diffWords(b);
		for (const [attr, edge] of Object.entries(registry[b.localName]?.["x-says"] ?? {})) {
			const said = b.getAttribute(attr);
			if (said) key = edge === "before" ? `${said} ${key}` : `${key} ${said}`;
		}
		if (key) pairs.push([b, key]);
	}
	for (const w of root.querySelectorAll(opaque)) {
		if (!authoredHere(w) || inChrome(w) || w.parentElement?.closest(opaque)) continue;
		const entry = registry[w.localName] ?? {};
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
	const lengths = before.map(() => after.map(() => 0));
	const at = (i, j) => lengths[i]?.[j] ?? 0;
	for (let i = before.length - 1; i >= 0; i--) for (let j = after.length - 1; j >= 0; j--) lengths[i][j] = before[i] === after[j] ? at(i + 1, j + 1) + 1 : Math.max(at(i + 1, j), at(i, j + 1));
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
	for (const [id, { state, specs }] of widgets) for (const [verb, spec] of specs) {
		if (spec.record?.kind !== "body" || !state[verb].action) continue;
		const body = doc.getElementById(id)?.querySelector(":scope > .lf-markdown-body");
		if (body) paintMarkdown(body, state[verb].value);
	}
}
function placeCreated(doc, widgets) {
	for (const [id, { state, specs }] of widgets) for (const [verb, spec] of specs) {
		const owner = spec.creates && doc.getElementById(id);
		if (!owner) continue;
		const { child, words } = spec.creates;
		const markdown = registry[child]?.["x-text-format"] === "inline-markdown";
		for (const [unit, { detail }] of Object.entries(state[verb].units ?? {})) {
			if (doc.getElementById(unit)) continue;
			const created = doc.createElement(child);
			created.id = unit;
			created.toggleAttribute("data-lf-added", true);
			const text = detail[words];
			created.append(markdown ? doc.importNode(inlineMarkdownFragment(text), true) : text);
			owner.append(created);
		}
	}
}
function blocksWithoutTwin(doc, live = document.body) {
	const base = /* @__PURE__ */ new Map();
	for (const [, key] of diffBlocks(doc)) base.set(key, (base.get(key) ?? 0) + 1);
	const without = [];
	for (const [b, key] of diffBlocks(live)) {
		const left = base.get(key) ?? 0;
		if (left > 0) base.set(key, left - 1);
		else without.push([b, key]);
	}
	return without;
}
let versionSource = () => null;
function selfComparison() {
	const source = versionSource()?.source;
	return source ? blocksNewSince(source) : [];
}
function blocksNewSince(source) {
	const doc = document.implementation.createHTMLDocument("");
	doc.body.replaceChildren(doc.importNode(source, true));
	formatDeclaredMarkdown(doc);
	const { widgets } = readApplication().effective;
	paintBodies(doc, widgets);
	placeCreated(doc, widgets);
	return blocksWithoutTwin(doc, pageDocument());
}
function servedElements() {
	const { source, pairs } = versionSource() ?? {
		source: null,
		pairs: /* @__PURE__ */ new WeakMap()
	};
	const served = /* @__PURE__ */ new Set();
	if (!source) return served;
	for (const node of [source, ...source.querySelectorAll("*")]) {
		const live = pairs.get(node);
		if (live) served.add(live);
	}
	return served;
}
function applyDiff(doc, baseAuthored, baseVersion, baseReading) {
	const baseView = baseReading.views[String(stamped(baseVersion).revision)];
	const baseProjection = projectView(baseView);
	const declaredAlike = ({ e, spec }) => {
		const current = baseAuthored.get(e.widget)?.specs.get(e.action);
		return current?.unit === spec.unit && JSON.stringify(current.record ?? null) === JSON.stringify(spec.record ?? null);
	};
	const baseWidgets = foldWidgetStates(baseAuthored, {
		...baseProjection,
		desired: new Map([...baseProjection.desired].filter(([, entry]) => declaredAlike(entry)))
	});
	paintBodies(doc, baseWidgets);
	placeCreated(doc, baseWidgets);
	for (const [b] of blocksWithoutTwin(doc)) {
		b.classList.add("lf-ins-block");
		diffMarked.add(b);
	}
	const mark = (target) => {
		if (diffMarked.has(target)) return;
		target.classList.add("lf-ins-block");
		diffMarked.add(target);
	};
	for (const [id, now] of readApplication().effective.widgets) {
		const before = baseWidgets.get(id);
		const widget = elementById(id);
		if (!before || !widget || inChrome(widget) || quoted(widget)) continue;
		for (const [verb, spec] of now.specs) {
			if (!spec.record || spec.record.kind === "body" || !before.specs.has(verb)) continue;
			if (spec.record.kind === "position") {
				const was = before.state[verb].value;
				const placed = Object.values(was).flat();
				for (const [container, ids] of Object.entries(now.state[verb].value)) {
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
		const baseBlock = doc.getElementById(block.id);
		diffBefore.set(block, baseBlock ? wrote(baseBlock) : null);
	}
	return diffMarked.size;
}
const inlineId = (target) => `lf-version-inline-${target.id}`;
const authoredReading = (target) => readingFrom(textNodesUnder(target, "wrote"));
function pointAt(target, reading, offset) {
	if (!reading.units.length) return {
		node: target,
		offset: 0
	};
	return offset === reading.units.length ? reading.units.at(-1).end : reading.units[offset].start;
}
function insertAt(target, reading, offset, node) {
	const point = pointAt(target, reading, offset);
	if (point.node.nodeType === Node.ELEMENT_NODE) {
		move(point.node, node, point.node.childNodes[point.offset] ?? null);
		return;
	}
	const text = point.node;
	if (point.offset === 0) move(text.parentNode, node, text);
	else if (point.offset === text.data.length) move(text.parentNode, node, text.nextSibling);
	else move(text.parentNode, node, text.splitText(point.offset));
}
function rangeAt(reading, start, end) {
	const first = reading.units[start];
	const last = reading.units[end - 1];
	if (!first || !last) return null;
	const range = document.createRange();
	range.setStart(first.start.node, first.start.offset);
	range.setEnd(last.end.node, last.end.offset);
	return range;
}
function paintInlineInsertions() {
	const ranges = [...inlineOpen.values()].flatMap((entry) => entry.ranges);
	if (ranges.length) CSS.highlights.set("lf-version-insert", new Highlight(...ranges));
	else CSS.highlights.delete("lf-version-insert");
}
function openInlineComparison(target) {
	const before = diffBefore.get(target);
	const reading = authoredReading(target);
	const current = currentVersionToken();
	const label = el("span", "lf-ui lf-quiet lf-version-inline-label", before === null ? `New since v${diffBase.value}` : `v${diffBase.value} → ${current}`);
	label.id = inlineId(target);
	label.setAttribute("aria-label", before === null ? `New since version ${diffBase.value}` : `Inline comparison from version ${diffBase.value} to ${current}`);
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
	const ranges = additions.map(([start, end]) => rangeAt(currentReading, start, end)).filter(Boolean);
	target.classList.toggle("lf-version-inline", hasTextChange);
	inlineOpen.set(target, {
		nodes,
		ranges
	});
	paintInlineInsertions();
	layoutChanged(target);
	return before === null ? `v${diffBase.value} had nothing here` : `showing an inline diff from v${diffBase.value}`;
}
function closeInlineComparison(target) {
	const entry = inlineOpen.get(target);
	inlineOpen.delete(target);
	target.classList.remove("lf-version-inline");
	for (const node of entry?.nodes ?? []) node.remove();
	paintInlineInsertions();
	layoutChanged(target);
	return `inline diff from v${diffBase.value} hidden`;
}
const inlineComparison = (target) => diffOn.value && diffBefore.has(target) && (diffBefore.get(target) === null || diffBefore.get(target) !== wrote(target)) ? {
	id: inlineId(target),
	open: inlineOpen.has(target),
	offer: `v${diffBase.value} → ${currentVersionToken()}`
} : null;
function toggleInlineComparison(target) {
	if (!inlineComparison(target)) return null;
	const said = inlineOpen.has(target) ? closeInlineComparison(target) : openInlineComparison(target);
	tick(comparisonGeneration);
	return said;
}
const comparable = (version) => {
	const base = stamped(version);
	return runtime.currentRevision !== null && base !== void 0 && base.revision < runtime.currentRevision;
};
function setDiff(on, base, pendingBase = null) {
	W(() => {
		diffOn.value = on;
		diffPendingBase.value = pendingBase;
		if (on) diffBase.value = base;
		if (!on) {
			diffRequest++;
			for (const target of [...inlineOpen.keys()]) closeInlineComparison(target);
			diffBefore.clear();
			for (const b of diffMarked) b.classList.remove("lf-ins-block");
			diffMarked.clear();
		}
		tick(comparisonGeneration);
	});
}
async function showComparison(base) {
	setDiff(false, null, base);
	const mine = ++diffRequest;
	const baseVersion = stamped(base);
	const baseRevision = baseVersion?.revision;
	if (baseRevision == null) {
		diffPendingBase.value = null;
		raiseError(`Couldn't load v${base}`);
		return;
	}
	const documentRequest = authoredDocument(baseVersion.url);
	let doc;
	let reading;
	let baseAuthored;
	try {
		while (mine === diffRequest) {
			const throughSeq = runtime.lastEventSeq;
			[doc, reading] = await Promise.all([documentRequest, baseReading(baseRevision, throughSeq)]);
			if (mine !== diffRequest) return;
			if (runtime.lastEventSeq === throughSeq) break;
		}
		if (mine !== diffRequest) return;
		baseAuthored = stageAuthoredStates(doc, /* @__PURE__ */ new Map());
		await prepareDeclaredMarkdown(doc);
	} catch {
		if (mine === diffRequest) {
			diffPendingBase.value = null;
			raiseError(`Couldn't load v${base}`);
		}
		return;
	}
	if (mine !== diffRequest) return;
	const n = applyDiff(doc, baseAuthored, base, reading);
	setDiff(true, base);
	notice(n ? `${n} changed passage${n === 1 ? "" : "s"} since v${base}` : `No text changes since v${base}`);
}
const pressComparison = (base) => diffOn.value && base === diffBase.value || diffPendingBase.value === base ? setDiff(false) : showComparison(base);
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
	return restoreInitialSource(doc);
}
const revisionDocuments = /* @__PURE__ */ new Map();
function revisionDocument(revision) {
	if (!revisionDocuments.has(revision.revision)) revisionDocuments.set(revision.revision, authoredDocument(revision.url).catch((error) => {
		revisionDocuments.delete(revision.revision);
		throw error;
	}));
	return revisionDocuments.get(revision.revision);
}
function createVersionController({ compositionInput, openThread, refreshThread, midComposition, hasPending, readAndApply, syncLayout, captureRetainedCurrentLocation = () => null, restoreRetainedCurrentLocation = () => false, captureObligationCurrentLocation = () => null, restoreObligationCurrentLocation = () => {}, versions }) {
	let { authoredBodyAttributes, authoredHeadNodes, authoredHtmlAttributes, source: authoredSource } = initialDocument;
	const sourcePairs = initialDocument.pairs;
	initialDocument = null;
	versionSource = () => ({
		source: authoredSource,
		pairs: sourcePairs
	});
	let authoredWidgets = servedWidgets;
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
		if (current.length !== authoredHeadNodes.size || current.length !== source.length || current.some((node, index) => !node.isEqualNode(source[index]))) {
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
	const upgraded = (element) => Boolean(registry[element.localName]?.["x-upgrade"]);
	function widgetKeys(source) {
		const keys = /* @__PURE__ */ new Map();
		const counts = /* @__PURE__ */ new Map();
		for (const element of elementsWithin(source)) {
			if (!upgraded(element)) continue;
			if (element.id) keys.set(element, element.id);
			else {
				const seen = counts.get(element.localName) ?? 0;
				counts.set(element.localName, seen + 1);
				keys.set(element, `${element.localName}#${seen}`);
			}
		}
		return keys;
	}
	function* elementsWithin(root) {
		const inner = root.localName === "template" ? root.content : root;
		for (const child of inner.children) {
			yield child;
			yield* elementsWithin(child);
		}
	}
	const RESOURCE_ATTRIBUTES = [
		"src",
		"href",
		"srcset",
		"poster",
		"data",
		"style"
	];
	const unrooted = (value, root) => root && value.includes(root) ? value.split(root).join("/") : value;
	const sameValue = (name, held, value, arrivingRoot) => RESOURCE_ATTRIBUTES.includes(name) ? unrooted(held, authoredRoot) === unrooted(value, arrivingRoot) : held === value;
	function sameAuthoredMarkup(before, after, arrivingRoot) {
		const strip = (element, root) => {
			const copy = element.cloneNode(true);
			if (!root) return copy;
			for (const node of [copy, ...elementsWithin(copy)]) for (const name of RESOURCE_ATTRIBUTES) {
				const value = node.getAttribute(name);
				if (value?.includes(root)) node.setAttribute(name, unrooted(value, root));
			}
			return copy;
		};
		return strip(before, authoredRoot).isEqualNode(strip(after, arrivingRoot));
	}
	const shell = (element, members) => {
		const copy = element.cloneNode(false);
		if (members) for (const child of element.childNodes) copy.append(child.cloneNode(false));
		return copy;
	};
	const reachesMembers = (before, after, arrivingRoot) => {
		if (registry[before.localName]?.["x-patch"] !== "members") return false;
		const members = !authoredBody(sourcePairs.get(before));
		return sameAuthoredMarkup(shell(before, members), shell(after, members), arrivingRoot);
	};
	function patchRules(doc) {
		const source = pageDocument(doc);
		const arrivingWidgets = documentWidgetDigests(doc);
		const arrivingRoot = layerRoot(doc);
		const heldKeys = widgetKeys(authoredSource);
		const arrivingKeys = widgetKeys(source);
		return {
			pairs: sourcePairs,
			contains: under,
			declared: upgraded,
			body: authoredBody,
			reaches: (before, after) => reachesMembers(before, after, arrivingRoot),
			unchanged: (before, after) => {
				const digest = authoredWidgets[heldKeys.get(before)];
				return Boolean(digest) && arrivingWidgets[arrivingKeys.get(after)] === digest;
			},
			same: (before, after) => sameAuthoredMarkup(before, after, arrivingRoot),
			sameValue: (name, held, value) => sameValue(name, held, value, arrivingRoot)
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
		const carry = captureCarry(live, authoredSource);
		const source = pageDocument(doc);
		const arrivingWidgets = documentWidgetDigests(doc);
		const arrivingRoot = layerRoot(doc);
		const rules = patchRules(doc);
		revisionDocuments.delete(target.revision);
		const isAuthored = authored(live);
		const generated = (node) => (node.nodeType === Node.ELEMENT_NODE || node.parentElement !== null) && !isAuthored(node);
		const arrived = [];
		const descriptorStages = [];
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
			if (arriving.nodeType === Node.ELEMENT_NODE) {
				rememberPassageParts(arriving);
				rememberAuthoredParents(arriving, parent);
				const descriptors = stageWidgetDescriptors(arriving, {
					kind: "page",
					revision: target.revision
				});
				descriptorStages.push(descriptors);
				commitWidgetDescriptors(descriptors);
				formatDeclaredMarkdown(arriving);
				arrived.push(arriving);
			}
			return arriving;
		};
		let restoreCarryScroll;
		await patchDocument(live, () => {
			authoredHtmlAttributes = replaceAuthoredAttributes(document.documentElement, doc.documentElement, authoredHtmlAttributes);
			keeps(document.documentElement, "data-lf-layout", doc.documentElement.getAttribute("data-lf-layout"));
			authoredBodyAttributes = replaceAuthoredAttributes(document.body, doc.body, authoredBodyAttributes);
			activateHead(doc, target);
			sourcePairs.set(source, live);
			patchTree(authoredSource, source, {
				...rules,
				arrive,
				generated,
				touched: (element) => touched.push(element)
			});
			keepPageRulesOffLayer();
			restoreCarryScroll = restoreCarry(carry.records, carry.held, currentIntent.handoff);
			reindexPassageOwners(live);
			pruneScopedElements();
			return {
				roots: [...arrived, ...touched],
				widgets: arrived.flatMap((root) => [root, ...elementsWithin(root)]).filter((element) => upgraded(element) && element.id).map((element) => element.id)
			};
		});
		authoredWidgets = arrivingWidgets;
		authoredSource = source;
		authoredRoot = arrivingRoot;
		const nextAuthored = new Map([...prior.authored].filter(([id]) => prior.descriptors.get(id)?.document.kind === "thread"));
		for (const [id, value] of sourceAuthored) nextAuthored.set(id, value);
		const arrivedDescriptors = /* @__PURE__ */ new Map();
		for (const stage of descriptorStages) for (const [id, value] of stage.descriptors) arrivedDescriptors.set(id, value);
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
				settleMarginContentLayout();
				syncLayout();
				if (currentIntent()) {
					restoreView(view, currentIntent);
					restoreRetainedCurrentLocation(retainedCurrentLocation);
					restoreCarryScroll();
					await restoreEditingContinuity(editingContinuity, currentIntent);
				}
				if (comparedFrom !== null) showComparison(comparedFrom);
				for (const [block] of blocksNewSince(outgoing)) backgroundFlash(block, flashDuration());
				notice(`Updated to ${target.label}`, { background: true });
			})
		};
	}
	async function prepareActivation(state) {
		const target = state.active;
		if (!LIVE_ROOT || runtime.currentRevision === null || target.revision <= runtime.currentRevision) return null;
		const activates = (retains) => target.revision > runtime.currentRevision && !hasPending() && (!midComposition(retains) || forceActivation);
		if (!servedExecutable || target.executable !== servedExecutable) return {
			revision: target.revision,
			activates: () => activates(),
			install: reloadInto(target)
		};
		let doc;
		try {
			doc = await revisionDocument(target);
			await preloadWidgets(pageDocument(doc));
		} catch (error) {
			reportPageError(error, `revision ${target.revision} failed to load`);
			return null;
		}
		return {
			revision: target.revision,
			activates: () => activates((node) => selectedBase() === null && patchRetains(authoredSource, pageDocument(doc), node, patchRules(doc))),
			install: () => {
				forceActivation = false;
				return activateRevision(doc, target);
			}
		};
	}
	const reloadInto = (target) => () => {
		forceActivation = false;
		const view = captureView();
		const editingContinuity = captureEditingContinuity();
		tabStore.set(VIEW_KEY, JSON.stringify(view));
		tabStore.set(HANDOFF_KEY, JSON.stringify({
			revision: target.revision,
			url: location.href,
			view,
			retainedCurrentLocation: captureRetainedCurrentLocation(),
			...editingContinuity,
			carry: captureCarry(pageDocument(), authoredSource).records,
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
		const view = Object.assign(capturePlace(null, blocks), {
			revision: runtime.currentRevision,
			activeRegion: active?.id,
			regions: Object.fromEntries([...places].flatMap(([id, { reading }]) => id === PAGE ? [] : [[id, reading]]))
		});
		for (const region of readingRegions()) {
			if (!shownRegionBounds(region)) continue;
			if (regionScrollBehavior(region) === "bounded" || region.id === active?.id) view.regions[region.id] = capturePlace(region, blocks);
		}
		return view;
	}
	function restoreView(view, currentIntent) {
		releaseHolds();
		const regions = new Map(readingRegions().map((region) => [region.id, region]));
		const active = regions.get(view.activeRegion) ?? containingReadingRegionFor(focusedInView()) ?? readingRegionFor(pageReadingBlock());
		if (active) reveal(active.host, currentIntent);
		const restored = /* @__PURE__ */ new Set();
		const activeReading = active && view.regions?.[active.id];
		const activeScroller = active && effectiveScroller(regions.get(active.id));
		if (activeReading && (hasLandmark(activeReading) || rawOffsetFits(activeReading, activeScroller) && activeScroller !== pageScroller)) {
			restorePlace(activeReading, regions.get(active.id), currentIntent);
			restored.add(activeScroller);
		} else {
			restorePlace(view, null, currentIntent);
			restored.add(pageScroller);
		}
		if (!restored.has(pageScroller) && (hasLandmark(view) || rawOffsetFits(view, pageScroller))) {
			restorePlace(view, null, currentIntent);
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
		return candidates.map((region) => [region, blocksOnScreen(region, blocks).next().value?.[1]]).filter(([, rect]) => rect).sort(([, a], [, b]) => a.top - b.top)[0]?.[0];
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
		const acted = Boolean(box) && inputSince(box, hold.since);
		if (!moved && !acted && hold.currentIntent()) return hold;
		holds.delete(id);
		if (moved === "carried" || !moved && acted) places.set(id, {
			reading: moved ? capturePlace(region) : hold.reading,
			at: ++placeCount,
			choices: scrollChoices(),
			inputs: moved ? inputCount() : hold.since
		});
		return null;
	}
	const movedAway = (box, hold, region) => {
		const settling = reapply !== null;
		const node = placeNode(hold.reading);
		if (!node) return settling ? null : "gone";
		if (boxOf(node) !== box) return "gone";
		const now = placeOffset(hold.reading, region);
		if (now === null) return settling ? null : "gone";
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
		if (event.type !== "wheel" || !event.deltaY) return innermost;
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
			places.set(reading.scroller, {
				reading,
				at: acted ? ++placeCount : 0,
				choices: scrollChoices(),
				inputs: inputCount()
			});
		}
	}
	function placeFor(box, recorded, before) {
		const own = box === pageScroller ? PAGE : regionForBox(box).id;
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
		const page = shifted.find(({ region }) => !region);
		if (page?.band) {
			const from = pageScroller.scrollTop;
			moveScrollerBy(pageScroller, -page.band);
			placeKept(pageScroller);
			wrote(pageScroller, from);
		}
		const boxes = new Map(page ? [[pageScroller, /* @__PURE__ */ new Set()]] : []);
		const returning = /* @__PURE__ */ new Set();
		const touch = (box) => boxes.get(box) ?? boxes.set(box, /* @__PURE__ */ new Set()).get(box);
		const idOf = (box) => box === pageScroller ? PAGE : readingRegions().find(({ body }) => body === box)?.id;
		for (const { region, from, to, returned } of shifted) {
			if (!region || !shownRegionBounds(region)) continue;
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
			holds.set(region ? region.id : PAGE, {
				box: new WeakRef(box),
				reading: place.reading,
				since: inputCount(),
				offset: placeOffset(place.reading, region),
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
				const now = placeOffset(hold.reading, region);
				if (now === null || Math.abs(now - hold.offset) <= 2) continue;
				const from = box.scrollTop;
				restorePlace(hold.reading, region, hold.currentIntent);
				wrote(box, from);
				hold.offset = placeOffset(hold.reading, region);
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
		reapply.observe(pageDocument());
		for (const hold of holds.values()) {
			const box = hold.box.deref();
			if (box && box !== pageScroller) for (const child of box.children) reapply.observe(child);
		}
	}
	const compositionChanges = /* @__PURE__ */ new Map();
	const ownBoxes = (owner) => readingRegions().filter((region) => regionScrollBehavior(region) === "bounded" && under(region.body, owner) && shownRegionBounds(region)).map((region) => region.body);
	function showSubject(phase, region) {
		const box = region.body;
		const own = regionForBox(box) && box.checkVisibility();
		if (phase === "leaving") {
			if (own) recordPlaces([box]);
			const place = places.get(region.id);
			if (!place) return;
			if (!subjectPlaces.has(region.id)) subjectPlaces.set(region.id, /* @__PURE__ */ new Map());
			subjectPlaces.get(region.id).set(region.subject, place.reading);
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
	function readingRegionTransition({ phase, owner, region, cancelled, retained, shifted }) {
		if (phase === "leaving" || phase === "showing") {
			showSubject(phase, region);
			return;
		}
		if (phase === "shift") {
			const currentIntent = retainUserIntent();
			const recorded = new Map(places);
			shifting = true;
			nextRender(() => restoreShifted(shifted, currentIntent, recorded));
			return;
		}
		if (cancelled || [...compositionChanges.keys()].some((ancestor) => ancestor !== owner && under(owner, ancestor))) {
			compositionChanges.delete(owner);
			return;
		}
		if (phase === "before") {
			if (retained && compositionChanges.has(owner)) {
				compositionChanges.get(owner).currentIntent = retainUserIntent();
				return;
			}
			const captured = new Map(ownBoxes(owner).map((box) => {
				const region = regionForBox(box);
				return [region.id, capturePlace(region)];
			}));
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
			const region = regionForBox(box);
			const reading = change.captured.get(region.id) ?? places.get(region.id)?.reading;
			if (reading && (hasLandmark(reading) || rawOffsetFits(reading, box))) restorePlace(reading, region, change.currentIntent);
		}
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
			moving.add(event.target === document ? pageScroller : event.target);
			scrolls++;
			if (resting) return;
			resting = true;
			rest(scrolls);
		};
		document.addEventListener("scroll", scrolled, {
			capture: true,
			passive: true
		});
		document.addEventListener("scrollend", ({ target }) => {
			const box = target === document ? pageScroller : target;
			if (writing.has(box)) {
				if (!inputSince(box, writing.get(box))) ownEnd.set(box, scrollChoices());
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
			const element = at instanceof Element ? at : at?.parentElement;
			const box = inputBox(element, event);
			touched.set(box, inputCount());
			held(box);
		});
		nextRender(() => recordPlaces([pageScroller, ...readingRegions().filter((region) => regionScrollBehavior(region) === "bounded").map((region) => region.body)]));
	}
	function installArrival() {
		installReadingContinuity();
		const navigationType = performance.getEntriesByType("navigation")[0]?.type;
		const handoff = (() => {
			const serialized = tabStore.get(HANDOFF_KEY);
			tabStore.set(HANDOFF_KEY, null);
			try {
				const value = JSON.parse(serialized || "null");
				return LIVE_ROOT && navigationType === "reload" && value?.url === location.href && Number.isInteger(value.revision) && value.revision <= runtime.currentRevision && Number.isInteger(value.view?.revision) && value.view.revision < runtime.currentRevision ? value : null;
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
				if (handoff.comparison !== null && stamped(handoff.comparison)) showComparison(handoff.comparison);
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
	const declaration = registry[element.localName]?.["x-data"]?.[input];
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
	if (!outputKeys.has(element)) outputKeys.set(element, `output:${++outputSequence}`);
	return outputKeys.get(element);
}
function publishOutput(element, output, value) {
	const declaration = registry[element.localName]?.["x-output"]?.[output];
	if (!declaration) throw new Error(`publishOutput(${element.localName}, ${output}) output is not declared by this widget`);
	if (!element.id) throw new Error("publishOutput requires a widget id");
	let owner = outputOwners.get(element);
	if (!owner) {
		owner = {
			values: /* @__PURE__ */ new Map(),
			connected: false
		};
		outputOwners.set(element, owner);
		watchOwner(element, {
			connect() {
				owner.connected = true;
				for (const [name, reading] of owner.values) applicationState.publishOutput(outputKey(element), name, reading);
			},
			disconnect() {
				owner.connected = false;
				for (const name of owner.values.keys()) applicationState.publishOutput(outputKey(element), name, null);
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
function inputBinding(element, declaration) {
	const source = declaration.source ? element.getAttribute(declaration.source) : null;
	const widget = declaration.reference && element.getAttribute(declaration.reference);
	if (source && widget) throw new Error(`<${element.localName}> input binds both an external source and widget output`);
	if (declaration.reference) requireReference("data", element, declaration.reference);
	const selected = applicationState.select((root) => {
		if (source) return Object.hasOwn(root.data.sources, source) ? root.data.sources[source] : null;
		if (!widget) return null;
		const producer = referencedProjection(element, declaration.reference, widget);
		if (!producer) return null;
		const key = outputKey(producer);
		const outputs = Object.hasOwn(root.outputs, key) ? root.outputs[key] : null;
		return outputs && Object.hasOwn(outputs, declaration.output) ? outputs[declaration.output] : null;
	});
	const snapshot = (reading, input) => source ? {
		source,
		...reading,
		origin: {
			input,
			source,
			contract: declaration.contract,
			revision: reading.revision
		}
	} : {
		...reading,
		origin: { derived: [{ widget }] }
	};
	return {
		source,
		widget,
		selected,
		snapshot
	};
}
const supplied = /* @__PURE__ */ new WeakMap();
const suppliedSnapshot = (value) => supplied.get(value);
const bindsInput = (element, { source, reference }) => Boolean(source && element.getAttribute(source) || reference && element.getAttribute(reference));
const dataRead = applicationState.select((root) => root.data.version !== null || root.phase === "offline");
function awaitsData(element) {
	return Object.values(registry[element.localName]?.["x-data"] ?? {}).some((declaration) => declaration.source && element.getAttribute(declaration.source)) && !dataRead.read();
}
function dataReader(element, input, accepted) {
	const declaration = declaredInput(element, input);
	const { source, widget, selected, snapshot } = inputBinding(element, declaration);
	let stopAccepted;
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
	let copied = {
		store: null,
		value: null
	};
	return () => {
		const sourceStore = widget ? selected.read() : delivered.value;
		const incompatible = sourceStore && sourceStore.contract !== declaration.contract;
		if (incompatible && reported !== sourceStore) {
			reported = sourceStore;
			reportPageError(`${source ? `data source ${source}` : `widget output ${widget}.${declaration.output}`} carries contract ${sourceStore.contract}; <${element.localName}> input ${input} requires ${declaration.contract}`);
		}
		if (incompatible || !sourceStore || !Object.hasOwn(sourceStore, "value")) return null;
		if (sourceStore !== copied.store) {
			copied = {
				store: sourceStore,
				value: structuredClone(snapshot(sourceStore, input))
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
		const records = registry.$data.contracts[manifest.contract].records;
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
export { acceptData, awaitsData, bindsInput, claimTraversals, commandSteps, comparisonBase, comparisonChanges, createAnchorTravel, createProjectionPresentation, createVersionController, dataReader, initializeServedDocument, inlineComparison, joinDataDelivery, keepPageRulesOffLayer, loadDeferred, mountHistory, notifyDataSubscribers, observeOutputs, paintCoreControls, publishOutput, pushEntry, readPlace, replaceEntry, returnPlace, selfComparison, servedElements, shallowSigs, suppliedSnapshot, toggleInlineComparison, versionPicker, versionsReading };