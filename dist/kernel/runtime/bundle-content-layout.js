import { LAYOUT, PAGE_PAINT_ATTRIBUTE, afterScript, inlineStyle, isElement, isHTML, isText, keeps, layoutChanged, layoutPx, nativeLayerHolding, nextFrame, nextRender, pagePresented, registeredVisualPart, registeredVisualPartAt, registeredVisualPartLabel, registeredVisualParts, renderedParent, renderedUnder, renderingState, revealRegisteredVisualPart, revealsVisualParts, setScroll, shadowHost, sizeObserver, skipped, under, upFrom, visualPartAdmission, watchArrivals, watchOwner, watchScrolls, whileConnected } from "./bundle-portable.js";
import { J, LENT_REACH_STOP, PRESSES, TEXT_BLOCK, TEXT_BOX, WORKS, Z, anchorKey, applicationPresented, deepFocus, documentChanged, eventSource, fragmentId, hostIn, inUi, isElementName, marks, move, onCurrentLocation, pressing, registry, shadowRootsIn, tabStops, tagsDeclaring, tick, uiInside, wearsLentStop } from "./bundle-layer-stack.js";
import { PRESSABLE, removeRuntimeRootStyle, repaintPage, reportPageError, setRuntimeRootAttribute, setRuntimeRootStyle } from "./bundle-layer-client.js";
import { clamp, clippedContents, headerCuts, landingBand, nearObserver, nearWindow, overlaps, scrollContainer, scrollsBy, scrollsContent, shellRight, shownBox, shownParts, shownRect, union, userScrollport } from "./bundle-geometry.js";
import { DATUM, authoredScope, blockAt, closestAcross, contextAround, cut, elementById, elementReading, excerptWords, fileModelsPassage, findQuote, inChrome, layoutBox, leafSurface, neighbourhood, pageDocument, pageQueryAll, pageText, quoteFrom, rangeOf, readingFrom, segmentsIn, settledAway, spanIn, textNodesUnder } from "./bundle-passages.js";

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
const age = (ts, compact) => clockValue((now) => {
	if (!ts) return "";
	const secs = Math.max(0, (now - new Date(ts).getTime()) / 1e3);
	if (secs < 45) return compact ? "now" : "just now";
	const [count, unit] = secs < 3600 ? [Math.round(secs / 60), "m"] : secs < 86400 ? [Math.round(secs / 3600), "h"] : [Math.round(secs / 86400), "d"];
	return `${count}${unit}${compact ? "" : " ago"}`;
});
const ago = (ts) => age(ts, false);
const shortAgo = (ts) => age(ts, true);
let workingGrace = null;
const observeWorkingGrace = (ms) => {
	workingGrace = ms;
};
const quietSince = (ts) => clockValue((now) => workingGrace !== null && !!ts && now - new Date(ts).getTime() >= workingGrace);
const activityTransitionAt = (state) => Math.min(...[state?.activity, ...(state?.others ?? []).map((entry) => entry?.activity)].flatMap((activity) => activity?.next_transition_at ? [Date.parse(activity.next_transition_at)] : []));
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
function deferredArrival(work) {
	arriving.add(work);
	const landed = () => arriving.delete(work);
	work.then(landed, landed);
	return work;
}
async function whenArrived() {
	while (arriving.size) await Promise.allSettled(arriving);
}
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
	["state", (held) => !held || appliedState !== null && (appliedState.taken >= held.taken || appliedState.reading === held.reading && held.taken * 1e3 < appliedState.lapses)],
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
//#region runtime/chrome.js
const chromeRoot = document.createElement("div");
chromeRoot.className = "lf-chrome";
const chromeForeground = document.createElement("dialog");
chromeForeground.className = "lf-ui lf-foreground";
chromeForeground.setAttribute("open", "");
chromeForeground.setAttribute("role", "presentation");
chromeForeground.tabIndex = -1;

//#endregion
//#region runtime/resolved-target.js
const resolvedElement = ({ element, place = element, surface = null }) => ({
	exact: true,
	status: "exact",
	datumElement: null,
	kind: "element",
	element,
	place,
	surface
});
const resolvedPassage = ({ place, segments }) => ({
	exact: true,
	status: "exact",
	datumElement: null,
	kind: "passage",
	place,
	segments
});
const resolvedInMessage = ({ message }) => ({
	exact: true,
	status: "exact",
	datumElement: null,
	kind: "message",
	message,
	place: null
});
const targetElement = (resolved) => resolved?.kind === "element" ? resolved.element : null;
const targetSegments = (resolved) => resolved?.kind === "passage" ? resolved.segments : [];
const targetPlace = (resolved) => resolved?.place ?? null;
const exactTarget = (resolved) => resolved?.exact ? targetElement(resolved) ?? targetPlace(resolved) : null;
const targetRange = (resolved) => {
	const segments = targetSegments(resolved);
	if (!segments.length || segments.some(({ node, start, end }) => !node.isConnected || start > node.length || end > node.length)) return null;
	return rangeOf(segments);
};
function rangeGeometry(range) {
	return {
		range,
		contextNode: range.startContainer.nodeType === Node.TEXT_NODE ? range.startContainer : range.startContainer.childNodes[range.startOffset] ?? range.startContainer,
		box: range.getBoundingClientRect(),
		attachment: [...range.getClientRects()].find((rect) => rect.width > 0 && rect.height > 0) ?? null
	};
}
const passageBoxes = (resolved) => targetRange(resolved) ? targetSegments(resolved).flatMap((segment) => [...rangeOf([segment]).getClientRects()]).filter((box) => box.width && box.height) : [];
function passageGeometry(resolved) {
	const range = targetRange(resolved);
	return range && rangeGeometry(range);
}
const targetSurface = (resolved) => resolved?.kind === "element" ? resolved.surface : null;
const targetParts = (resolved) => {
	const element = targetElement(resolved);
	if (!element) return [];
	return targetSurface(resolved) ? [element] : shownParts(element);
};

//#endregion
//#region runtime/addressable-names.js
const HTML_WORDS = {
	input: "control",
	select: "control",
	button: "control",
	p: "paragraph",
	li: "item",
	tr: "row",
	td: "cell",
	th: "cell",
	figure: "figure",
	blockquote: "quote",
	pre: "block",
	section: "section",
	article: "section",
	aside: "aside",
	ul: "list",
	ol: "list",
	dl: "list",
	table: "table",
	details: "note",
	h1: "heading",
	h2: "heading",
	h3: "heading",
	h4: "heading",
	h5: "heading",
	h6: "heading"
};
function addressableWord(addressable) {
	if (!addressable) return "";
	const tag = addressable.tagName.toLowerCase();
	const word = widgetWord(tag, addressable);
	if (word) return word;
	if (tag === "pre") return addressable.querySelector(":scope > code") ? "code" : "block";
	return HTML_WORDS[tag] ?? tag;
}
function widgetWord(tag, element = null) {
	const declared = registry[tag]?.["x-word"];
	return (declared === "module" ? element?.lfWord?.() : declared) || (tag.startsWith("lf-") ? tag.slice(3) : "");
}
function addressableSays(addressable) {
	if (!addressable) return "";
	return (registry[addressable.localName]?.["x-word"] === "module" ? addressable.lfSays?.() : "") || elementReading(addressable);
}
const TITLES = "summary, h1, h2, h3, h4, h5, h6, strong";
function leadingTitle(container) {
	for (const node of container.childNodes) {
		if (node.nodeType === Node.TEXT_NODE && node.textContent?.trim()) return null;
		if (!(node instanceof Element) || uiInside(node, container)) continue;
		if (node.matches(TITLES)) return node;
		if (["header", "hgroup"].includes(node.localName)) return leadingTitle(node);
	}
	return null;
}
function declaredName(element) {
	const attribute = registry[element.localName]?.["x-name"];
	return attribute && element.getAttribute(attribute)?.trim() || "";
}
function addressableName(element) {
	if (!element) return "";
	const declared = declaredName(element);
	if (declared) return declared;
	const title = leadingTitle(element);
	return title ? elementReading(title, "wrote") : "";
}
const LABEL_WORDS = 60;
const captionOf = (element) => {
	const caption = [...element.children].find((child) => child.matches("figcaption, caption") && !uiInside(child, element));
	return caption ? elementReading(caption) : "";
};
const accessibleName = (element) => element.getAttribute("aria-label")?.trim() || (element.labels?.[0] ? elementReading(element.labels[0]) : "") || element.alt?.trim() || "";
const ownName = (element) => addressableName(element) || captionOf(element) || accessibleName(element);
const saysItself = (element) => element.matches("p,li,h1,h2,h3,h4,h5,h6,td,th,pre,blockquote,dd,dt,figcaption,summary") || registry[element.localName]?.["x-word"] === "module" && element.lfSays?.() || [...element.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.textContent?.trim());
function addressableLabel(element) {
	if (!element) return "";
	const own = ownName(element);
	if (own) return own;
	if (saysItself(element)) return excerptWords(addressableSays(element), LABEL_WORDS);
	const scope = authoredScope(element);
	for (let at = upFrom(element); at && at !== scope; at = upFrom(at)) {
		const name = ownName(at);
		if (name) return name;
	}
	if (isElementName(element.localName) && registry[element.localName]) return "";
	return excerptWords(addressableSays(element) || element.querySelector("[aria-label]")?.getAttribute("aria-label"), LABEL_WORDS);
}
const sectionLabel = (addressable) => [addressableWord(addressable), addressableLabel(addressable)].filter(Boolean).join(" · ");

//#endregion
//#region runtime/anchor-resolution.js
let anchoringReady = false;
const anchoringIsReady = () => anchoringReady;
function setAnchoringReady(ready) {
	anchoringReady = ready;
}
const sectionOf = (anchor) => anchor?.section ? elementById(anchor.section) : null;
function currentDatums(source, key, identity = null, dataSource = null) {
	if (!source?.id) return [];
	return pageQueryAll(DATUM).filter((datum) => under(datum, source) && datum.getAttribute("data-lf-projection") === source.id && (dataSource === null || datum.getAttribute("data-lf-source") === dataSource) && (identity === null ? datum.getAttribute("data-lf-datum") === key : datum.getAttribute("data-lf-identity") === identity));
}
const projectedDatum = (source, key) => {
	const matches = currentDatums(source, key);
	return matches.length === 1 ? matches[0] ?? null : null;
};
function datumLabel(anchor) {
	if (!anchor?.datum) return "";
	documentChanged();
	const source = sectionOf(anchor);
	const datums = currentDatums(source, anchor.datum, anchor.identity ?? null, anchor.source ?? null);
	const [datum] = datums;
	const label = datum ? datums.length === 1 && datum.getAttribute("data-lf-datum-label") : source?.lfDatumLabel?.(anchor.datum);
	return typeof label === "string" ? label.trim() : "";
}
function suppliedDatum(source, key) {
	const supplied = source?.lfDataDatum?.(key);
	return supplied instanceof Element && under(supplied, source) && supplied.getAttribute("data-lf-projection") === source.id ? supplied : null;
}
function addressedElements(source, key) {
	if (typeof source.lfElementsFor === "function") return [...source.lfElementsFor(key) ?? []].filter((element) => element instanceof Element && under(element, source));
	const part = visualPart(source, key)?.element;
	if (part) return [part];
	const datum = projectedDatum(source, key) ?? suppliedDatum(source, key);
	return datum ? [datum] : [];
}
function revealAddressed(source, key) {
	if (revealVisualPart(source, key)) return null;
	return source.lfRevealDatum?.(key) ?? null;
}
const visualAdmission = (visual) => visual ? visualPartAdmission(visual, registry[visual.localName]?.["x-visual"] ?? null) : null;
const wholeVisualSurface = (element) => element && registry[element.localName]?.["x-visual"] ? element : null;
function visualParts(visual) {
	const admits = visualAdmission(visual);
	if (!admits) return [];
	return registeredVisualParts(visual).filter((part) => admits(part.id));
}
const admitsVisualPart = (visual, part) => visualAdmission(visual)?.(part) ?? false;
function visualPart(visual, part) {
	return admitsVisualPart(visual, part) ? registeredVisualPart(visual, part) : null;
}
function revealVisualPart(visual, part) {
	return admitsVisualPart(visual, part) ? revealRegisteredVisualPart(visual, part) : null;
}
function visualPartAt(visual, target) {
	const admits = visualAdmission(visual);
	return admits ? registeredVisualPartAt(visual, target instanceof Element ? target : target?.parentElement ?? null, (part) => admits(part.id)) : null;
}
const visualPartLabel = (visual, part) => visual && admitsVisualPart(visual, part) ? registeredVisualPartLabel(visual, part) : null;
const declaredVisualSelector = () => [...tagsDeclaring((entry) => entry["x-visual"])].join(",");
const genericVisualSelector = "svg, img, figure";
const visualSelector = () => [declaredVisualSelector(), genericVisualSelector].filter(Boolean).join(",");
const outermostAcross = (element, selector) => {
	for (let parent = upFrom(element); parent;) {
		const outer = closestAcross(parent, selector);
		if (!outer) break;
		element = outer;
		parent = upFrom(element);
	}
	return element;
};
const claimsVisualGesture = (element) => element.matches(`${PRESSES},${PRESSABLE}`);
const unclaimedVisualGesture = (target) => {
	if (inChrome(target) || inUi(target)) return false;
	for (let element = target instanceof Element ? target : target?.parentElement; element; element = upFrom(element)) if (claimsVisualGesture(element)) return false;
	return true;
};
function visualAt(target, { unclaimed = true } = {}) {
	if (unclaimed && !unclaimedVisualGesture(target)) return null;
	const declared = declaredVisualSelector();
	let element = declared ? closestAcross(target, declared) : null;
	if (element) element = outermostAcross(element, declared);
	else {
		element = closestAcross(target, genericVisualSelector);
		if (element) element = outermostAcross(element, genericVisualSelector);
	}
	if (!element) return null;
	const seat = closestAcross(element, ADDRESSABLE);
	return seat ? {
		element,
		seat,
		id: seat.id,
		part: visualPartAt(element, target)
	} : null;
}
const designCandidates = () => [
	...tagsDeclaring(() => true),
	WORKS,
	"[data-lf-offer]",
	genericVisualSelector
].join(",");
function designPressAt(target) {
	const at = target instanceof Element ? target : target?.parentElement;
	const hit = at && closestAcross(at, designCandidates());
	if (!hit || !hit.matches(genericVisualSelector)) return hit;
	return closestAcross(hit, `${PRESSES},${"[data-lf-offer]:not([data-lf-offer=\"\"])"}`) || visualAt(at, { unclaimed: false })?.element || hit;
}
const ADDRESSABLE = "[id]:not(.lf-ui):not([id^=\"lf-\"])";
function isAddressable(at) {
	if (!at.matches("[id]:not(.lf-ui):not([id^=\"lf-\"])") || inChrome(at) || inUi(at) || settledAway(at)) return false;
	const visual = tagsDeclaring((entry) => entry["x-visual"]).join(",");
	return !(visual && at.parentElement && closestAcross(at.parentElement, visual));
}
function addressableAt(node) {
	let at = node instanceof Element ? node : node?.parentElement;
	for (; at; at = upFrom(at)) if (isAddressable(at)) return at;
	return null;
}
function annotationAt(node, fallback = addressableAt) {
	const formatted = tagsDeclaring((entry) => entry["x-text-format"] === "markdown").join(",");
	return formatted && closestAcross(node, formatted) || blockAt(node) || fallback(node);
}
const lightSeat = (seat) => (seat && shadowHost(seat.getRootNode())) ?? seat;
const aimLabel = (addressable, says = addressableLabel(addressable)) => [addressableWord(addressable), says].filter(Boolean).join(": ");
const addressableAimTarget = (addressable) => ({
	anchor: { section: addressable.id },
	element: addressable,
	label: aimLabel(addressable),
	surface: wholeVisualSurface(addressable)
});
const anchorForDatum = (datum, fields = {}) => {
	const section = datum.getAttribute("data-lf-projection");
	const key = datum.getAttribute("data-lf-datum");
	if (section === null || key === null) return null;
	const sourceRevision = datum.getAttribute("data-lf-source-revision");
	const source = datum.getAttribute("data-lf-source");
	const identity = datum.getAttribute("data-lf-identity");
	return {
		section,
		datum: key,
		...fields,
		...source && sourceRevision ? {
			source,
			source_revision: sourceRevision
		} : {},
		...identity ? { identity } : {}
	};
};
function datumAimTarget(datum) {
	if (!(datum instanceof Element) || !datum.matches("[data-lf-projection][data-lf-datum]")) return null;
	const anchor = anchorForDatum(datum);
	if (!anchor) return null;
	const owner = sectionOf(anchor);
	if (!owner || !under(datum, owner)) return null;
	return {
		anchor,
		element: datum,
		label: datum.getAttribute("data-lf-datum-label")?.trim() || aimLabel(datum)
	};
}
const anchorForRange = (range) => anchorForPassage(segmentsIn(range), range.commonAncestorContainer);
function anchorForPassage(segments, node) {
	const holder = node.nodeType === Node.ELEMENT_NODE ? node : upFrom(node);
	const { text: quote, units } = readingFrom(segments);
	const dataNodes = new Set(segments.map((seg) => closestAcross(seg.node, DATUM)).filter(Boolean));
	const [onlyDatum] = dataNodes;
	const datum = dataNodes.size === 1 && segments.every((seg) => closestAcross(seg.node, "[data-lf-projection][data-lf-datum]") === onlyDatum) ? onlyDatum : null;
	if (datum) {
		const anchor = anchorForDatum(datum, quote ? { quote } : {});
		if (anchor) return anchor;
	}
	const section = closestAcross(holder, "[id]:not(.lf-ui):not([id^=\"lf-\"])")?.id ?? null;
	if (!quote) return section === null ? null : { section };
	const reading = pageText();
	const [start, stop] = spanIn(reading, segments);
	for (let width = 24;; width *= 2) {
		const prefix = cut(neighbourhood(reading, start, width, true), -width, Infinity);
		const suffix = cut(neighbourhood(reading, stop, width, false), 0, width);
		const anchor = {
			section,
			quote,
			...prefix && { prefix },
			...suffix && { suffix }
		};
		const resolved = resolveAnchor(anchor);
		if (resolved?.exact && resolved.kind === "passage") {
			const first = resolved.segments[0];
			const last = resolved.segments.at(-1);
			const from = units[0]?.start;
			const to = units.at(-1)?.end;
			if (first && last && from && to && first.node === from.node && first.start === from.offset && last.node === to.node && last.end === to.offset) return anchor;
		}
		if ([...prefix].length < width && [...suffix].length < width) return {
			...anchor,
			detached: true
		};
	}
}
const controlName = (control) => control instanceof HTMLElement && control.isContentEditable ? accessibleName(control) : ownName(control) || (control.matches(PRESSES) ? (control instanceof HTMLElement ? control.innerText : "")?.trim().replace(/\s+/g, " ") || addressableWord(control) : "");
const controlFaces = (control) => [control, ...control.labels ?? []];
const controlIdentity = (control) => (control instanceof HTMLLabelElement ? control.control : null) ?? control;
const namedParts = (owner, name) => [...new Set(pageQueryAll(WORKS).map(controlIdentity))].filter((control) => control !== owner && under(control, owner) && addressableAt(control) === owner && controlName(control) === name);
function controlContext(control, contexts) {
	const block = blockAt(control);
	if (!block) return "";
	if (!contexts.has(block)) contexts.set(block, quoteFrom(textNodesUnder(block).filter(({ node }) => !closestAcross(node, WORKS))));
	return [contexts.get(block), elementReading(control)].filter(Boolean).join(" ");
}
function controlPassages(face, control) {
	const words = textNodesUnder(face);
	const barriers = face === control ? pageQueryAll(WORKS).filter((other) => other !== control && under(other, face)) : [control];
	const passages = [];
	let run = [];
	const finish = () => {
		if (run.length) passages.push(run);
		run = [];
	};
	for (const word of words) {
		if (face === control ? closestAcross(word.node, WORKS) !== control : under(word.node, control)) {
			finish();
			continue;
		}
		if (run.length && barriers.some((barrier) => rangeOf([...run, word]).intersectsNode(barrier))) finish();
		run.push(word);
	}
	finish();
	return passages;
}
function visiblePassage(segments) {
	const clips = /* @__PURE__ */ new Map();
	return segments.every((segment) => {
		const holder = segment.node.parentElement;
		if (!holder || !holder.checkVisibility({
			opacityProperty: true,
			visibilityProperty: true
		})) return false;
		return [...rangeOf([segment]).getClientRects()].some((rect) => rect.width > 0 && rect.height > 0 && clippedContents(rect, holder, clips));
	});
}
function designTargetAt(node, marginTargetAt, reading = {
	owners: /* @__PURE__ */ new Map(),
	contexts: /* @__PURE__ */ new Map()
}) {
	const { owners, contexts } = reading;
	let at = node instanceof Element ? node : node?.parentElement;
	if (!at) return null;
	const pressed = designPressAt(at);
	const control = pressed?.matches(`${WORKS},${genericVisualSelector}`) ? controlIdentity(pressed) : null;
	const visual = visualAt(at, { unclaimed: false });
	const declared = declaredVisualSelector();
	if (declared && visual?.element.matches(declared)) at = visual.element;
	else if (control && (pressed instanceof HTMLLabelElement && pressed.control || visual && control.matches(PRESSES) && under(visual.element, control))) at = control;
	const surface = leafSurface(at);
	const margin = closestAcross(at, ".lf-margin-entry, [data-lf-margin-for]");
	const marginTarget = marginTargetAt?.(at);
	const standsFor = margin && (!surface || under(margin, surface)) && marginTarget;
	const authored = surface && closestAcross(at, "[id]:not([id^=\"lf-\"])");
	const element = standsFor || (surface ? authored && under(authored, surface) && authored : addressableAt(at));
	if (!element) return null;
	const partElement = control && control !== element && (marginTarget === element || under(control, element)) ? control : null;
	const part = partElement && controlName(partElement);
	let target = owners.get(element);
	if (!target) {
		target = addressableAimTarget(element);
		owners.set(element, target);
	}
	if (!partElement || !part) return control === element ? {
		...target,
		controlElement: control,
		controlFaces: controlFaces(control)
	} : target;
	const faces = controlFaces(partElement);
	const detail = [.../* @__PURE__ */ new Set([controlContext(partElement, contexts), ...faces.filter((face) => face !== partElement).map((label) => quoteFrom(textNodesUnder(label).filter(({ node }) => !under(node, partElement))))])].filter((text) => text && text !== part).join(" · ");
	const named = {
		...target,
		anchor: {
			...target.anchor,
			part
		},
		label: `${part}${detail ? ` · ${detail}` : ""} · ${target.label}`,
		controlElement: partElement,
		controlFaces: faces
	};
	if (partElement.matches(genericVisualSelector) && !claimsVisualGesture(partElement)) return named;
	return {
		...named,
		capture() {
			const repeatedName = namedParts(element, part).length > 1;
			for (const face of faces) for (const passage of controlPassages(face, partElement)) {
				if (!passage.length || !fileModelsPassage(passage)) continue;
				const captured = anchorForRange(rangeOf(passage));
				if (!captured) continue;
				const resolved = captured.quote ? resolveAnchor({
					...captured,
					quote: captured.quote
				}) : null;
				const attachment = resolved?.kind === "passage" && passageGeometry(resolved)?.attachment;
				if (resolved?.kind === "passage" && resolved.exact && attachment && resolved.segments.every(({ node }) => under(node, face)) && overlaps(attachment, face.getBoundingClientRect()) && visiblePassage(resolved.segments)) {
					const context = contextAround(pageText(), resolved.segments, {
						before: [...captured.prefix ?? ""].length,
						after: [...captured.suffix ?? ""].length
					});
					const phrase = [
						part === captured.quote ? part : `${part} · “${captured.quote}”`,
						context.before && `after …${context.before}`,
						context.after && `before ${context.after}…`,
						target.label
					].filter(Boolean).join(" · ");
					return {
						...named,
						anchor: {
							...target.anchor,
							...captured,
							part
						},
						label: repeatedName ? phrase : named.label
					};
				}
			}
			return named;
		}
	};
}
function aimTargetAt(node, { design = false, marginTargetAt } = {}) {
	if (design) {
		const target = designTargetAt(node, marginTargetAt);
		return target?.capture ? target.capture() : target;
	}
	const visual = visualAt(node, { unclaimed: false });
	if (visual?.part) return {
		anchor: {
			section: visual.id,
			visual: visual.part.id
		},
		element: visual.part.element,
		label: aimLabel(visual.seat, visual.part.label),
		surface: visual.part.surface
	};
	const datum = closestAcross(node, DATUM);
	if (datum) return datumAimTarget(datum);
	const addressable = addressableAt(node);
	return addressable ? addressableAimTarget(addressable) : null;
}
function aimTargets(options = {}) {
	const candidates = [
		...pageQueryAll(ADDRESSABLE).filter(isAddressable),
		...pageQueryAll(DATUM),
		...options.design ? pageQueryAll(designCandidates()) : [],
		...pageQueryAll(declaredVisualSelector()).flatMap((visual) => visualParts(visual).map((part) => part.element))
	];
	const reading = {
		owners: /* @__PURE__ */ new Map(),
		contexts: /* @__PURE__ */ new Map()
	};
	const targets = candidates.map((node) => options.design ? designTargetAt(node, options.marginTargetAt, reading) : aimTargetAt(node, options)).filter((target) => target !== null);
	if (options.design) {
		const seen = /* @__PURE__ */ new Set();
		return targets.filter((target) => {
			const identity = target.controlElement ?? target.element;
			if (seen.has(identity)) return false;
			seen.add(identity);
			return true;
		});
	}
	const keys = /* @__PURE__ */ new Set();
	return targets.filter((target) => {
		const key = anchorKey(target.anchor);
		if (keys.has(key)) return false;
		keys.add(key);
		return true;
	});
}
function resolveAnchor(anchor) {
	if (anchor.detached) return null;
	if (anchor.datum) {
		const source = sectionOf(anchor);
		const datums = currentDatums(source, anchor.datum, anchor.identity ?? null, anchor.source ?? null);
		const anchoredToData = typeof anchor.source === "string" && typeof anchor.source_revision === "string";
		const basis = datums[0] ?? source;
		if (!(!anchoredToData || basis !== null && basis.getAttribute("data-lf-source") === anchor.source && (anchor.identity ? datums.length > 0 && basis.getAttribute("data-lf-identity") === anchor.identity : basis.getAttribute("data-lf-source-revision") === anchor.source_revision))) {
			const contextual = source?.lfDataDatum?.(anchor.datum, { outdated: true });
			const fallback = contextual instanceof Element && under(contextual, source) ? contextual : source;
			if (!(fallback instanceof Element)) return null;
			return {
				...resolvedElement({ element: fallback }),
				datumElement: null,
				exact: false,
				status: "outdated"
			};
		}
		if (datums.length > 1) return null;
		const [datum] = datums;
		if (!datum) {
			const virtual = source?.lfDataDatum?.(anchor.datum);
			if (!(virtual instanceof Element) || !under(virtual, source)) return null;
			return {
				...resolvedElement({ element: virtual }),
				datumElement: null,
				exact: false,
				status: "fallback"
			};
		}
		if (!anchor.quote) return {
			...resolvedElement({ element: datum }),
			datumElement: datum,
			exact: true,
			status: "exact"
		};
		const segments = findQuote(pageText(), anchor.quote, anchor, datum);
		const [first] = segments;
		return first ? {
			...resolvedPassage({
				place: annotationAt(first.node, () => datum),
				segments
			}),
			datumElement: datum,
			exact: true,
			status: "exact"
		} : {
			...resolvedElement({ element: datum }),
			datumElement: datum,
			exact: false,
			status: "fallback"
		};
	}
	if (anchor.visual) {
		const section = sectionOf(anchor);
		if (!section || settledAway(section)) return null;
		const found = visualPart(section, anchor.visual);
		if (found) return resolvedElement({
			element: found.element,
			place: section,
			surface: found.surface
		});
		return admitsVisualPart(section, anchor.visual) && revealsVisualParts(section) ? {
			...resolvedElement({
				element: section,
				surface: wholeVisualSurface(section)
			}),
			exact: false,
			status: "fallback"
		} : null;
	}
	if (!anchor.quote) {
		const section = sectionOf(anchor);
		if (!section || settledAway(section)) return null;
		const target = resolvedElement({
			element: section,
			surface: wholeVisualSurface(section)
		});
		return anchor.part ? {
			...target,
			exact: false,
			status: "fallback"
		} : target;
	}
	const segments = findQuote(pageText(), anchor.quote, anchor, sectionOf(anchor));
	const [first] = segments;
	if (!first) return null;
	const face = anchor.part && closestAcross(first.node, WORKS);
	const controlFace = face && segments.every(({ node }) => closestAcross(node, WORKS) === face);
	return resolvedPassage({
		place: controlFace ? face : annotationAt(first.node),
		segments
	});
}
const fragmentTarget = (fragment) => fragment ? targetElement(resolveAnchor({ section: fragmentId(fragment) })) : null;

//#endregion
//#region runtime/scrolling.js
const nativeScroller = document.scrollingElement;
if (!(nativeScroller instanceof HTMLElement)) throw new Error("Leaf requires an active HTML document scrollport");
const pageScroller = nativeScroller;
const moving = /* @__PURE__ */ new WeakMap();
const ended = /* @__PURE__ */ new WeakMap();
const scrollSteps = /* @__PURE__ */ new WeakMap();
const layoutMoved = /* @__PURE__ */ new WeakSet();
const watchedLayout = /* @__PURE__ */ new WeakSet();
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
	extents.set(box, extentOf(box));
	const root = box === pageScroller ? document.documentElement : box;
	const sizes = /* @__PURE__ */ new WeakMap();
	const measure = (node) => skipped(node) ? null : [
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
			if (next && (!before || before.some((value, index) => value !== next[index]))) changed = true;
		}
		if (changed) {
			if (ended.has(box) && box.scrollTop !== ended.get(box)) layoutMoved.add(box);
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
ended.set(pageScroller, pageScroller.scrollTop);
function stopScroll(boxes) {
	const stopped = [...boxes].flatMap((box) => {
		const sequence = moving.get(box);
		return sequence ? [{
			box,
			sequence
		}] : [];
	});
	if (!stopped.length) return null;
	for (const { box } of stopped) setScroll(box, {
		left: box.scrollLeft,
		top: box.scrollTop,
		behavior: "instant"
	});
	return new Promise((resolve) => nextFrame(() => nextFrame(() => {
		for (const { box, sequence } of stopped) if (moving.get(box) === sequence) moving.delete(box);
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
let travel = null;
document.addEventListener("beforematch", () => {
	const mark = travel = {};
	nextFrame(() => nextFrame(() => {
		if (travel === mark) travel = null;
	}));
}, { capture: true });
const eventScroller = (target) => target === document ? pageScroller : target instanceof Element ? target : null;
document.addEventListener("scroll", ({ target }) => {
	const box = eventScroller(target);
	if (!box) return;
	if (skipped(box)) return;
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
	if (!box) return;
	if (skipped(box)) {
		moving.delete(box);
		scrollSteps.delete(box);
		layoutMoved.delete(box);
		return;
	}
	watchLayout(box);
	const wasMoving = moving.get(box);
	moving.delete(box);
	const extent = extentOf(box);
	const repeated = (scrollSteps.get(box) ?? 0) > 1;
	scrollSteps.delete(box);
	if ((wasMoving?.glide || repeated || travel !== null || ended.get(box) !== box.scrollTop && !layoutMoved.has(box) && !changedExtent(extents.get(box), extent)) && kept.get(box) !== box.scrollTop) chooseScroll(box);
	ended.set(box, box.scrollTop);
	layoutMoved.delete(box);
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
		if (!(child instanceof HTMLElement) || child.offsetParent !== box) return box.scrollHeight;
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
	setScroll(box, {
		top: scrollLimit(box),
		behavior
	});
};
const aims = /* @__PURE__ */ new WeakMap();
const moveScrollerBy = (box, top, behavior = "instant") => {
	const aim = box.scrollTop + top;
	if (Math.abs(top) >= .5) {
		if (behavior !== "instant" && reachable(box, top)) startScroll(box);
		setScroll(box, {
			top: aim,
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
	for (const { target } of records) if (isElement(target) && scrollAncestors.has(target)) reread(target);
});
function watchAncestorStyles(scope) {
	const tree = scope.getRootNode();
	const root = "documentElement" in tree ? tree.documentElement : tree;
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
	const prior = mayScroll.get(el);
	if ((prior === void 0 ? el.getAttribute("tabindex") : prior) !== null) return;
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
watchScrolls((box) => {
	if (!box) return;
	if (downwards.has(box)) paintReadingReach(box);
	if (sideways.has(box)) paintSidewaysReach(box, true);
});
function reachReadingScroller(el, paintContinuation) {
	el.classList.toggle("scroll", true);
	downwards.set(el, paintContinuation);
	sweep(el);
	paintReach();
	watchReach(el);
	paintReadingReach(el);
	return () => {
		downwards.delete(el);
		if (!watched(el)) unwatchReach(el);
		afterScript(() => {
			if (!downwards.has(el)) {
				keeps(el, PAGE_PAINT_ATTRIBUTE.moreBelow, null);
				paintContinuation?.(false);
			}
		});
	};
}
const readingPaints = /* @__PURE__ */ new Set();
function paintReadingReach(el) {
	readingPaints.add(el);
	afterScript(paintReadingReachNow);
}
function paintReadingReachNow() {
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
	const surfaces = scopes.flatMap((scope) => [...isElement(scope) && scope.matches(SCROLL_SURFACE) ? [scope] : [], ...scope.querySelectorAll(SCROLL_SURFACE)]);
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
		read.push({
			el,
			style: {
				overflowX: style.overflowX,
				overflowY: style.overflowY,
				position: style.position,
				direction: style.direction
			}
		});
		let node = el;
		for (; node; node = upFrom(node)) {
			scrollAncestors.add(node);
			if (containers.has(node)) break;
			containers.add(node);
		}
	}
	const queriesRead = [...containers].map((el) => ({
		el,
		containerType: getComputedStyle(el).containerType
	}));
	for (const reading of queriesRead) noteQueries(reading.el, reading);
	for (const { el, style } of read) {
		const waited = waiting.delete(el);
		classify(el, style);
		if (waited) release(el);
	}
	asked.add(root);
}
function forgetSurface(el) {
	seenDeclarations.delete(el);
	const authored = mayScroll.get(el);
	if (authored !== void 0) {
		mayScroll.delete(el);
		if (!claimedStops.has(el)) returnStop(el, authored);
	}
	sideways.delete(el);
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
		keeps(el, PAGE_PAINT_ATTRIBUTE.scrollDirection, null);
		keeps(el, PAGE_PAINT_ATTRIBUTE.moreBefore, null);
		keeps(el, PAGE_PAINT_ATTRIBUTE.moreAfter, null);
	}
	if (el.hasAttribute("hidden") || !userScrollport(style.overflowX) && !userScrollport(style.overflowY)) {
		const authored = mayScroll.get(el);
		if (authored === void 0) return;
		mayScroll.delete(el);
		if (!claimedStops.has(el)) returnStop(el, authored);
		if (!watched(el)) unwatchReach(el);
		return;
	}
	if (userScrollport(style.overflowX) && !el.matches(TEXT_BOX)) {
		if (!sideways.has(el)) watchReach(el);
		sideways.set(el, style.direction);
	}
	if (!mayScroll.has(el)) {
		if ("tabIndex" in el && typeof el.tabIndex === "number" && el.tabIndex >= 0 && !claimedStops.has(el)) return;
		mayScroll.set(el, wearsLentStop(el) || claimedStops.has(el) ? null : el.getAttribute("tabindex"));
	}
	watchReach(el);
}
const childrenWatched = /* @__PURE__ */ new WeakSet();
const childLists = new MutationObserver((records) => {
	for (const { target, addedNodes, removedNodes } of records) {
		if (!childrenWatched.has(target)) continue;
		for (const node of removedNodes) if (isElement(node)) release(node);
		for (const node of addedNodes) if (isElement(node)) reachSizes.observe(node);
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
	if (!watched(node) && !(node.parentElement && childrenWatched.has(node.parentElement))) reachSizes.unobserve(node);
}
const depth = (el) => {
	let levels = 0;
	let node = el;
	for (; node; node = upFrom(node)) levels++;
	return levels;
};
const watched = (el) => mayScroll.has(el) || sideways.has(el) || downwards.has(el) || waiting.has(el);
const reachSizes = sizeObserver(() => paintReach());
function paintSidewaysReach(el, readStyle = false) {
	afterScript(() => {
		const prior = sideways.get(el);
		if (prior === void 0 || unpainted(el)) return;
		const direction = readStyle ? getComputedStyle(el).direction : prior;
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
	sideways.delete(el);
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
	const candidates = [...mayScroll].map(([el, authored]) => ({
		el,
		authored,
		depth: depth(el)
	}));
	for (const { el, authored } of candidates.sort((a, b) => b.depth - a.depth)) {
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
		const sizeReading = contentBoxSize[0];
		if (!sizeReading) continue;
		const { inlineSize, blockSize } = sizeReading;
		const size = query.both ? `${inlineSize} ${blockSize}` : `${inlineSize}`;
		if (query.size !== null && query.size !== size) reread(target);
		query.size = size;
	}
}, { counted: false });
addEventListener("resize", () => reread(document.body));
const asked = /* @__PURE__ */ new WeakSet();
const reached = (el) => {
	let node = el;
	for (; node; node = upFrom(node)) if (asked.has(node)) return true;
	return false;
};
document.addEventListener(LAYOUT, (event) => {
	const changed = eventSource(event);
	if (isElement(changed) && reached(changed)) reread(changed);
	paintReach();
});

//#endregion
//#region runtime/reading-regions.js
const regions = /* @__PURE__ */ new Map();
const transitionWatchers = /* @__PURE__ */ new Set();
const depthOf = (node) => {
	let depth = 0;
	for (let current = node instanceof Element ? node : node.parentElement; current; current = renderedParent(current)) depth += 1;
	return depth;
};
const live = (region) => Boolean(region?.host.isConnected && region.body.isConnected);
const concealed = (region) => region.host.closest?.("[hidden], [aria-hidden='true']") !== null || region.body.matches("details:not([open])");
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
		if (marked(child)) return [{
			body: child,
			name: child.id
		}];
		const only = child.childElementCount === 1 ? child.firstElementChild : null;
		return only && marked(only) ? [{
			body: only,
			name: only.id || child.id
		}] : [];
	}) : [];
	let unnamed = 0;
	const ids = new Map(bodies.map(({ body, name }) => [body, name ? `lf-region:layout#${name}` : `lf-region:layout@${unnamed++}`]));
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
	const region = id == null ? void 0 : regions.get(id);
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
	} else if ((at === document.body || under(at, pageDocument())) && !(arriving && at === document.body && pressing()?.released === false)) recentRegionId = pageRegionId = null;
};
for (const type of [
	"pointerdown",
	"wheel",
	"touchstart",
	"click"
]) addEventListener(type, (event) => {
	const at = event.composedPath()[0];
	if (!(at instanceof Node)) return;
	if (type !== "click") actedAt(at, false);
	else if (event.isTrusted && event instanceof MouseEvent && event.button === 0) readingInput(at);
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
const asRegion = (regionOrNode) => {
	if (typeof regionOrNode === "string") return regions.get(regionOrNode);
	if (!regionOrNode) return void 0;
	const named = regions.get(regionOrNode.id);
	if (named || !(regionOrNode instanceof Element)) return named;
	const containing = readingRegionFor(regionOrNode);
	return containing ? regions.get(containing.id) : void 0;
};
const scrolls = (box) => userScrollport(getComputedStyle(box).overflowY);
const regionScrollBehavior = (regionOrNode) => {
	const region = asRegion(regionOrNode);
	return region && live(region) && !concealed(region) && !skipped(region.body) && scrolls(region.body) ? "bounded" : "flow";
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
	const previousPage = pageSeen;
	if (pageMoved(now) && previousPage) shifted.push({
		region: null,
		band: now.band - previousPage.band
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
//#region runtime/bounds.js
const BOUND = marks["x-bound"].paint;
const BOUNDED = `[${BOUND}]`;
const FOLLOWING = `[${BOUND}="end"]`;
const holds = /* @__PURE__ */ new WeakMap();
const registered = /* @__PURE__ */ new Set();
const byBox = /* @__PURE__ */ new WeakMap();
const THIS_DOCUMENT = `lf-region:bound:${performance.timeOrigin}`;
let unnamed = 0;
function scrollerOf(bounded) {
	const selector = getComputedStyle(bounded).getPropertyValue("--lf-bound-box").trim();
	if (!selector) return bounded;
	for (const box of bounded.querySelectorAll(selector)) if (box.closest(BOUNDED) === bounded) return box;
	return bounded;
}
const regionId = (bounded) => bounded.id && authoredScope(bounded) === pageDocument() ? compoundReadingRegionId(bounded, "bound") : `${THIS_DOCUMENT}:${unnamed += 1}`;
const following = (hold, box) => hold.bounded.matches(FOLLOWING) && !hold.left && !(hold.pinned !== null && box.scrollTop < hold.pinned - 2 && !atScrollEnd(box));
const heldBy = (box) => {
	const hold = byBox.get(box);
	return hold?.box === box && registered.has(hold) ? hold : null;
};
const followingItsEnd = (box) => {
	const hold = heldBy(box);
	return Boolean(hold && following(hold, box));
};
const boundedBlockOf = (box) => heldBy(box)?.bounded ?? null;
function holdBlock(bounded) {
	const hold = {
		bounded,
		id: regionId(bounded),
		bound: null,
		box: null,
		pinned: null,
		left: false,
		sync: () => sync(false)
	};
	let stopRegion = null;
	const letGo = () => {
		if (hold.box && hold.box !== bounded) resize.unobserve(hold.box);
		stopRegion?.();
		stopRegion = null;
		hold.box = null;
		registered.delete(hold);
	};
	const adopt = (box) => {
		if (box === hold.box) return;
		letGo();
		const onScroll = () => {
			if (bounded.hasAttribute("hidden") || skipped(bounded)) return;
			hold.left = !atScrollEnd(box);
			if (!hold.left) hold.pinned = box.scrollTop;
		};
		box.addEventListener("scroll", onScroll, { passive: true });
		resize.observe(box);
		byBox.set(box, hold);
		hold.box = box;
		hold.left = false;
		hold.pinned = null;
		const release = registerReadingRegion({
			id: hold.id,
			host: bounded,
			body: box
		});
		stopRegion = () => {
			box.removeEventListener("scroll", onScroll);
			release();
		};
		registered.add(hold);
	};
	const sync = (observed) => {
		hold.bound = bounded.getAttribute(BOUND);
		if (!bounded.isConnected || hold.bound === null) return letGo();
		if (bounded.hasAttribute("hidden") || skipped(bounded)) {
			if (!hold.box) adopt(bounded);
			hold.pinned = null;
			if (!observed) {
				resize.unobserve(bounded);
				resize.observe(bounded);
			}
			return;
		}
		const box = scrollerOf(bounded);
		adopt(box);
		if (!bounded.matches(FOLLOWING)) return;
		if (!following(hold, box)) {
			hold.left = true;
			return;
		}
		scrollToEnd(box);
		hold.pinned = box.scrollTop;
	};
	const resize = sizeObserver(() => sync(true));
	resize.observe(bounded);
	new MutationObserver((records) => {
		if (records.some((record) => record.type !== "attributes" || record.target === bounded)) hold.sync();
	}).observe(bounded, {
		attributes: true,
		attributeFilter: ["hidden"],
		childList: true,
		characterData: true,
		subtree: true
	});
	return hold;
}
function holdArrivingBounds() {
	watchArrivals(BOUNDED, [BOUND], {
		arrive: (el) => {
			let hold = holds.get(el);
			if (!hold) {
				hold = holdBlock(el);
				holds.set(el, hold);
			}
			if (!registered.has(hold) || hold.bound !== el.getAttribute(BOUND)) hold.sync();
		},
		leave: (el) => holds.get(el)?.sync()
	});
}

//#endregion
//#region runtime/element-axes.js
function elementAxes(source) {
	let matrix = new window.DOMMatrix();
	let node = source;
	for (; isElement(node); node = renderedParent(node)) {
		const style = getComputedStyle(node);
		let local = new window.DOMMatrix();
		if (style.rotate !== "none") {
			const split = style.rotate.lastIndexOf(" ");
			const angle = style.rotate.slice(split + 1);
			const parts = style.rotate.slice(0, split + 1).trim().split(" ");
			const degrees = parseFloat(angle) * (angle.endsWith("turn") ? 360 : angle.endsWith("grad") ? .9 : angle.endsWith("rad") ? 180 / Math.PI : 1);
			const axis = parts.length === 3 ? [
				Number(parts[0]),
				Number(parts[1]),
				Number(parts[2])
			] : parts[0] === "x" ? [
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

//#endregion
//#region runtime/element-frame.js
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
	let depth = 0;
	let split = -1;
	for (let at = 0; at < position.length; at++) {
		const character = position[at];
		if (character === "(") depth++;
		if (character === ")") depth--;
		if (character === " " && !depth) {
			split = at;
			break;
		}
	}
	if (split < 0) throw new TypeError(`Computed object-position has no second component: ${position}`);
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
	point.style.left = pixels(position.slice(0, split), horizontal);
	point.style.top = pixels(position.slice(split + 1), vertical);
	document.body.append(measure);
	const resolved = getComputedStyle(point);
	const offset = {
		x: Number.parseFloat(resolved.left),
		y: Number.parseFloat(resolved.top)
	};
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
		const local = source instanceof window.SVGSVGElement ? source.viewBox.baseVal.width && source.viewBox.baseVal.height ? source.viewBox.baseVal : {
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
	const native = source instanceof window.HTMLImageElement ? {
		width: source.naturalWidth,
		height: source.naturalHeight
	} : source instanceof window.HTMLCanvasElement ? {
		width: source.width,
		height: source.height
	} : source instanceof window.HTMLVideoElement ? {
		width: source.videoWidth,
		height: source.videoHeight
	} : null;
	if (native) {
		if (!native.width || !native.height) return null;
		const edge = (side) => Number.parseFloat(style[`border${side}Width`]) + Number.parseFloat(style[`padding${side}`]);
		const contentWidth = width - edge("Left") - edge("Right");
		const contentHeight = height - edge("Top") - edge("Bottom");
		let sx = contentWidth / native.width;
		let sy = contentHeight / native.height;
		if (style.objectFit !== "fill") sx = sy = style.objectFit === "cover" ? Math.max(sx, sy) : style.objectFit === "none" ? 1 : Math.min(sx, sy, style.objectFit === "scale-down" ? 1 : Infinity);
		const { x: dx, y: dy } = nativePosition(source, style.objectPosition, contentWidth - native.width * sx, contentHeight - native.height * sy);
		if (![
			sx,
			sy,
			dx,
			dy
		].every(Number.isFinite) || !sx || !sy) return null;
		return {
			box,
			width: native.width,
			height: native.height,
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
	const width = borderSize("width", ["Left", "Right"], isHTML(source) ? source.offsetWidth : void 0);
	const height = borderSize("height", ["Top", "Bottom"], isHTML(source) ? source.offsetHeight : void 0);
	if (width === void 0 || height === void 0) return null;
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
//#region runtime/css-anchors.js
const anchorNames = /* @__PURE__ */ new WeakMap();
let anchorOrdinal = 0;
const nextName = () => `--lf-a${++anchorOrdinal}`;
const partOf = (name) => name.slice(2);
const partNamed = (el) => {
	const name = anchorNames.get(el);
	return name !== void 0 && el.part.contains(partOf(name));
};
let partRules = null;
const declared = /* @__PURE__ */ new Set();
const given = /* @__PURE__ */ new WeakMap();
const watchedTrees = /* @__PURE__ */ new WeakSet();
const restoreParts = (el) => {
	if (!isElement(el)) return;
	for (const part of given.get(el) ?? []) if (!el.part.contains(part)) el.part.add(part);
};
function keepParts(root) {
	if (watchedTrees.has(root)) return;
	watchedTrees.add(root);
	new MutationObserver((records) => {
		for (const { target } of records) restoreParts(target);
	}).observe(root, {
		subtree: true,
		attributes: true,
		attributeFilter: ["part"]
	});
}
function namePart(el, name, pseudo = "") {
	if (!partRules) {
		partRules = new CSSStyleSheet();
		document.adoptedStyleSheets = [...document.adoptedStyleSheets, partRules];
	}
	if (!declared.has(name)) {
		const content = pseudo ? "content: \"\";" : "";
		partRules.insertRule(`::part(${partOf(name)})${pseudo} { ${content} anchor-name: ${name}; }`, partRules.cssRules.length);
		declared.add(name);
	}
	given.set(el, /* @__PURE__ */ new Set([...given.get(el) ?? [], partOf(name)]));
	keepParts(el.getRootNode());
	restoreParts(el);
}
function anchorReading(el, name) {
	if (!isElement(el)) return { name: el.name };
	name ??= anchorNames.get(el) ?? nextName();
	anchorNames.set(el, name);
	if (el.getRootNode() !== document) return partNamed(el) ? {
		el,
		name
	} : {
		el,
		name,
		write: name,
		part: true
	};
	const written = inlineStyle(el).anchorName;
	if (written.split(",").some((part) => part.trim() === name)) return {
		el,
		name
	};
	const authored = written || getComputedStyle(el).anchorName;
	return {
		el,
		name,
		write: !authored || authored === "none" ? name : `${authored}, ${name}`
	};
}
function nameAnchor({ el, name, write, part }) {
	if (write && part) {
		if (!partNamed(el)) namePart(el, name);
	} else if (write) inlineStyle(el).anchorName = write;
	return name;
}
function nameable(el) {
	const root = el.getRootNode();
	if (root === document) return true;
	if (shadowHost(root)?.getRootNode() !== document) return false;
	if (anchorNames.has(el) && partNamed(el)) return true;
	const authored = getComputedStyle(el).anchorName;
	return !authored || authored === "none";
}
function outsideScopes(target) {
	let el = target;
	let at = target;
	for (; isElement(at); at = renderedParent(at)) if (at.getRootNode() === document && !at.contains(chromeRoot) && getComputedStyle(at).anchorScope === "all") el = renderedParent(at) ?? at;
	return el;
}
function anchorElement(target) {
	let el = outsideScopes(target);
	for (let host; !nameable(el) && (host = shadowHost(el.getRootNode()));) el = host;
	while (el instanceof SVGElement && el.ownerSVGElement) el = el.ownerSVGElement;
	if (el !== target) return el;
	const [part] = shownParts(target);
	return part && part !== target ? part : target;
}
function anchorReaches(anchor, box) {
	const holder = anchorHolder(anchor);
	const host = hostIn(holder, document);
	if (!host) return false;
	const layer = nativeLayerHolding(holder);
	if (layer !== nativeLayerHolding(box)) return !layer;
	const order = host.compareDocumentPosition(box);
	return Boolean(order & Node.DOCUMENT_POSITION_FOLLOWING) && !(order & Node.DOCUMENT_POSITION_CONTAINED_BY);
}
function scrollsWith(node, box) {
	let at = node;
	for (; at !== box; at = renderedParent(at)) {
		if (!at) return false;
		if (isElement(at) && (!/^(static|relative)$/.test(getComputedStyle(at).position) || at !== node && scrollsContent(at))) return false;
	}
	return true;
}
function carriedAnchor(scroller, near = null) {
	if (anchorElement(scroller) !== scroller || nativeLayerHolding(scroller)) return null;
	const carried = (node) => isElement(node) && !/^(br|wbr)$/.test(node.localName) && anchorElement(node) === node && node.getClientRects().length > 0 && /^(static|relative)$/.test(getComputedStyle(node).position);
	if (!near) {
		for (const child of scroller.children) if (carried(child)) return child;
		return contentStart(scroller);
	}
	for (let before = near.previousSibling, after = near.nextSibling; before || after; before = before?.previousSibling ?? null, after = after?.nextSibling ?? null) for (const node of [before, after]) if (carried(node)) return node;
	return contentStart(scroller);
}
function anchorFor(context) {
	const physical = isElement(context) ? context : context?.parentElement;
	if (!physical) return null;
	const anchor = anchorElement(physical);
	if (context === physical || anchor !== physical || !scrollContainer(physical)) return anchor;
	return carriedAnchor(physical, context) ?? anchor;
}
const starts = /* @__PURE__ */ new WeakMap();
const START = "data-lf-content-start";
function contentStart(scroller) {
	if (!scroller.firstChild || [...scroller.childNodes].some((node) => node.nodeType !== Node.TEXT_NODE && !(isElement(node) && /^(br|wbr)$/.test(node.localName)))) return null;
	let handle = starts.get(scroller);
	if (!handle) {
		if (!CSS.supports("anchor-name", "attr(data-lf-content-start type(<custom-ident>))") || !/^(block|inline-block|flow-root|list-item)$/.test(getComputedStyle(scroller).display) || !/^(none|normal)$/.test(getComputedStyle(scroller, "::before").content) || getComputedStyle(scroller, "::first-letter").float !== "none") return null;
		handle = {
			scroller,
			name: nextName(),
			getBoundingClientRect() {
				const range = document.createRange();
				for (const lead of scroller.childNodes) {
					if (isText(lead)) {
						range.setStart(lead, 0);
						range.setEnd(lead, Math.min(1, lead.length));
					} else range.selectNode(lead);
					const [rect] = range.getClientRects();
					if (rect) return rect;
				}
				return range.getBoundingClientRect();
			}
		};
		starts.set(scroller, handle);
	}
	const { name } = handle;
	if (scroller.getRootNode() === document) keeps(scroller, START, name);
	else namePart(scroller, name, "::before");
	return handle;
}
const anchorHolder = (anchor) => isElement(anchor) ? anchor : anchor.scroller;
const anchorName = (el) => nameAnchor(anchorReading(el));
let dropsTransforms;
function anchorDropsTransforms() {
	if (dropsTransforms !== void 0) return dropsTransforms;
	const moved = document.createElement("div");
	const anchored = document.createElement("div");
	moved.style.cssText = "position: fixed; left: 0; top: 0; translate: 8px 0; anchor-name: --lf-moved";
	anchored.style.cssText = "position: fixed; top: 0; position-anchor: --lf-moved; left: anchor(left, 8px)";
	chromeRoot.append(moved, anchored);
	dropsTransforms = anchored.getBoundingClientRect().left < 4;
	moved.remove();
	anchored.remove();
	return dropsTransforms;
}
function laidOut(el) {
	const parent = el.offsetParent;
	let left = el.offsetLeft;
	let top = el.offsetTop;
	if (!parent) {
		if (getComputedStyle(el).position !== "fixed") return null;
		return {
			left,
			top
		};
	}
	if (parent === document.body && getComputedStyle(parent).position === "static") {
		left -= scrollX;
		top -= scrollY;
	} else {
		const from = parent.getBoundingClientRect();
		left += from.left + parent.clientLeft - parent.scrollLeft;
		top += from.top + parent.clientTop - parent.scrollTop;
	}
	for (let box = renderedParent(el); box !== parent; box = renderedParent(box)) {
		if (!isElement(box)) return null;
		left -= box.scrollLeft;
		top -= box.scrollTop;
	}
	return {
		left,
		top
	};
}
function movement(style) {
	const matrix = style.transform === "none" ? null : new window.DOMMatrixReadOnly(style.transform);
	return {
		moves: Boolean(matrix) || style.translate !== "none" || style.rotate !== "none" || style.scale !== "none" || style.offsetPath !== "none",
		slides: style.rotate === "none" && style.scale === "none" && (style.offsetPath === "none" || style.offsetRotate === "0deg") && (!matrix || matrix.is2D && matrix.a === 1 && matrix.b === 0 && matrix.c === 0 && matrix.d === 1)
	};
}
function translationOf(el) {
	let x = 0;
	let y = 0;
	let at = el;
	for (; isElement(at); at = renderedParent(at)) {
		const { moves, slides } = movement(getComputedStyle(at));
		if (!moves) continue;
		if (!slides || !isHTML(at) || at.currentCSSZoom !== 1) return null;
		const layout = laidOut(at);
		if (!layout) return null;
		const shown = at.getBoundingClientRect();
		x += shown.left - layout.left;
		y += shown.top - layout.top;
	}
	return {
		x,
		y
	};
}
function anchorBox(anchor) {
	const box = anchor.getBoundingClientRect();
	if (!anchorDropsTransforms()) return box;
	const shift = translationOf(anchorHolder(anchor));
	return shift && (shift.x || shift.y) ? new DOMRect(box.left - shift.x, box.top - shift.y, box.width, box.height) : box;
}
function anchorAt(node, anchor, box, at = anchor && anchorBox(anchor), visibility = "always") {
	const from = (side, length) => anchor ? `calc(anchor(${side}, -9999px) + ${layoutPx(length)})` : layoutPx(length);
	Object.assign(node.style, {
		position: "fixed",
		positionAnchor: anchor ? anchorName(anchor) : "",
		positionVisibility: anchor ? visibility : "",
		left: from("left", box.left - (at?.left ?? 0)),
		top: from("top", box.top - (at?.top ?? 0)),
		...box.right === void 0 ? {} : {
			width: layoutPx(box.right - box.left),
			height: layoutPx(box.bottom - box.top)
		}
	});
}
const cutPath = ({ x, y }, band) => {
	const open = 1e5;
	const width = band.right - band.left;
	const height = band.bottom - band.top;
	const edge = (value, side) => `calc(${layoutPx(value)} - var(--lf-paint-outset-${side}, 0px))`;
	return `inset(${edge(y ? 0 : -1e5, "top")} ${edge(-width - (x ? 0 : open), "right")} ${edge(-height - (y ? 0 : open), "bottom")} ${edge(x ? 0 : -1e5, "left")})`;
};
const nowhere = {
	left: 0,
	top: 0,
	right: 0,
	bottom: 0
};
function headerLevels(item, clips = /* @__PURE__ */ new Map()) {
	return headerCuts(item, clips).map(({ box, band }) => {
		const anchor = box === box.ownerDocument.scrollingElement ? null : anchorElement(box);
		const cut = {
			band: band ?? nowhere,
			axes: {
				x: false,
				y: true
			}
		};
		return anchor ? {
			...cut,
			anchor,
			reading: anchorReading(anchor),
			at: anchorBox(anchor)
		} : {
			...cut,
			anchor: null,
			reading: null,
			at: null
		};
	});
}
function cutFrames(levels, frames, make) {
	const remaining = [...frames];
	const placed = levels.toReversed().map((level) => ({
		level,
		frame: remaining.pop() ?? make()
	})).reverse();
	const chain = placed.map(({ frame }) => frame);
	const first = chain[0];
	const was = frames[0];
	if (first && was && first !== was && was.parentNode) move(was.parentNode, first, was);
	let parent = null;
	for (const frame of chain) {
		if (parent && frame.parentNode !== parent) move(parent, frame, null);
		parent = frame;
	}
	for (const dropped of remaining) dropped.remove();
	for (const { level: { anchor, band, axes, at, reading }, frame } of placed) {
		if (reading) nameAnchor(reading);
		anchorAt(frame, anchor, {
			left: band.left,
			top: band.top,
			right: band.left,
			bottom: band.top
		}, at);
		frame.style.clipPath = cutPath(axes, band);
	}
	return placed;
}
const views = /* @__PURE__ */ new Map();
const viewedNodes = /* @__PURE__ */ new WeakMap();
let viewObserver;
function refreshAnchorView(node) {
	const binding = viewedNodes.get(node);
	if (!binding) return;
	if (!binding.view) {
		resumeAnchorView(node);
		return;
	}
	const view = binding.view;
	const near = nearWindow(view.target);
	if (view.near === near) return;
	view.near = near;
	for (const notify of view.nodes.values()) notify();
}
function releaseAnchorView(node) {
	const binding = viewedNodes.get(node);
	const view = binding?.view;
	if (!view) return;
	binding.view = null;
	view.nodes.delete(node);
	if (!view.nodes.size) {
		view.observer.unobserve(view.target);
		views.delete(view.target);
	}
}
function resumeAnchorView(node) {
	const binding = viewedNodes.get(node);
	if (!binding || binding.view || !node.isConnected || !binding.target.isConnected) return;
	anchorView(node, binding.target, binding.changed);
	binding.changed();
}
function anchorView(node, target, changed) {
	let view = viewedNodes.get(node)?.view;
	if (view?.target === target) return view.near;
	releaseAnchorView(node);
	if (!target) return false;
	if (!viewObserver) {
		watchArrivals(".lf-anchor-view", ["class"], {
			arrive: resumeAnchorView,
			leave: releaseAnchorView
		});
		viewObserver = nearObserver((entries) => {
			for (const entry of entries) {
				const view = views.get(entry.target);
				if (!view) continue;
				const near = entry.isIntersecting && entry.target.checkVisibility();
				const changed = view.near !== near;
				view.near = near;
				for (const [node, notify] of view.nodes) {
					if (!node.isConnected || !entry.target.isConnected) {
						releaseAnchorView(node);
						continue;
					}
					if (changed) notify();
				}
			}
		});
	}
	view = views.get(target);
	if (!view) {
		view = {
			target,
			near: nearWindow(target),
			nodes: /* @__PURE__ */ new Map(),
			observer: viewObserver
		};
		views.set(target, view);
		viewObserver.observe(target);
	}
	view.nodes.set(node, changed);
	viewedNodes.set(node, {
		target,
		changed,
		view
	});
	if (!node.classList.contains("lf-anchor-view")) node.classList.add("lf-anchor-view");
	return view.near;
}

//#endregion
//#region runtime/pointed-place.js
const points = /* @__PURE__ */ new Map();
const handed = /* @__PURE__ */ new Map();
const WITHIN_A_LINE = /^(inline|contents$)/;
function pointInto(target, node) {
	let at = isElement(node) ? node : node?.parentElement ?? null;
	if (!target || target instanceof SVGElement || !at || !under(at, target)) return null;
	let line = null;
	for (; at && at !== target; at = upFrom(at)) {
		if (at instanceof SVGElement) continue;
		const display = getComputedStyle(at).display;
		if (display === "table-row") {
			line = at;
			break;
		}
		if (display === "table-cell") line = null;
		else if (!line && !WITHIN_A_LINE.test(display)) line = at;
	}
	return line && !opens(target, line) ? line : null;
}
function opens(target, line) {
	let at = line;
	for (; at && at !== target; at = upFrom(at)) for (let before = at.previousSibling; before; before = before.previousSibling) if (drawn(before)) return false;
	return true;
}
const drawn = (node) => isText(node) ? Boolean(node.data.trim()) && Boolean(node.parentElement?.checkVisibility()) : isElement(node) && !inChrome(node) && node.checkVisibility() && [...node.getClientRects()].some((box) => box.width && box.height);
function livePoint(target, point) {
	return target && point?.isConnected && point !== target && under(point, target) && point.getClientRects().length ? point : null;
}
function commitPoint(key, element, passage) {
	handed.set(key, {
		element,
		passage
	});
}
function placePoints(threads, known) {
	const text = pageText();
	for (const [key, { element, passage }] of handed) {
		if (!known.has(key)) continue;
		handed.delete(key);
		const beside = [...points.values()].find((held) => held.element === element && element.isConnected);
		points.set(key, {
			element,
			passage,
			row: beside?.row ?? key,
			readFor: null
		});
	}
	const placed = /* @__PURE__ */ new Map();
	for (const { key, target } of threads) {
		const point = points.get(key);
		if (!point) continue;
		let element = livePoint(target, point.element);
		if (!element && point.passage && point.readFor !== text) {
			point.readFor = text;
			const found = resolveAnchor(point.passage);
			element = livePoint(target, pointInto(target, targetSegments(found)[0]?.node));
			if (element) point.element = element;
		}
		if (element) placed.set(key, {
			element,
			row: point.row,
			words: point.passage?.quote ?? null
		});
	}
	if (known.size) {
		for (const store of [points, handed]) for (const key of store.keys()) if (!known.has(key)) store.delete(key);
	}
	return placed;
}
function pointBand(box, point) {
	const row = point.getBoundingClientRect();
	const top = clamp(row.top, box.top, box.bottom);
	const bottom = clamp(row.bottom, top, box.bottom);
	const { left, right } = box;
	return {
		left,
		top,
		right,
		bottom,
		width: right - left,
		height: bottom - top
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
	return [...rows.values()].sort((a, b) => a.rank - b.rank || a.sequence - b.sequence).filter((row) => read(row.offered) ?? true).map((row) => Object.freeze({
		key: row.key,
		label: read(row.label),
		value: read(row.value) ?? "",
		title: read(row.title) ?? "",
		shortcut: read(row.shortcut) ?? EMPTY,
		group: read(row.group),
		copies: read(row.copies) ?? "",
		urgent: read(row.urgent) ?? null,
		exit: Boolean(row.exit),
		action: read(row.action) ?? null,
		disabled: Boolean(read(row.disabled)),
		press: row.press ?? null
	}));
}
const pageControlsChanged = () => afterScript(tell);
function tell() {
	revision.value = revision.peek() + 1;
}

//#endregion
//#region runtime/content-layout.js
let documentLayoutOpen = false;
let readFinished = null;
let pending = 0;
let lastRead = -1;
let headSizes = null;
let watchedHead = null;
let railAvailable = null;
function readDocumentLayout() {
	const { changed } = readDocumentHeaders();
	syncLayoutRegion();
	const header = layoutBox()?.querySelector(":scope > header") ?? null;
	if (header !== watchedHead) {
		headSizes ??= sizeObserver(scheduleDocumentLayout);
		if (watchedHead) headSizes.unobserve(watchedHead);
		if (header) headSizes.observe(header);
		watchedHead = header;
	}
	readFinished?.(changed);
	const available = railStands();
	if (available !== railAvailable) {
		railAvailable = available;
		pageControlsChanged();
	}
	if (changed) {
		const main = pageDocument();
		if (main) layoutChanged(main);
		repaintPage();
	}
}
function readFrame(time) {
	pending = 0;
	if (time === lastRead) {
		pending = nextFrame(readFrame);
		return;
	}
	lastRead = time;
	readDocumentLayout();
}
function scheduleDocumentLayout() {
	if (documentLayoutOpen) pending ||= nextRender(readFrame);
}
function settleDocumentLayout() {
	if (documentLayoutOpen) readDocumentLayout();
}
function openDocumentLayout({ onRead }) {
	readFinished = onRead;
	documentLayoutOpen = true;
	document.addEventListener("toggle", scheduleDocumentLayout, { capture: true });
	window.addEventListener("resize", scheduleDocumentLayout);
	readDocumentLayout();
}
function proseRect(main = layoutBox()) {
	if (!main) return null;
	const grid = [main, ...main.children].find((node) => getComputedStyle(node).gridTemplateColumns.includes("prose-start"));
	if (!grid) return main.getBoundingClientRect();
	const style = getComputedStyle(grid);
	const frame = elementFrame(grid);
	if (!frame) return grid.getBoundingClientRect();
	const gap = parseFloat(style.columnGap) || 0;
	let offset = 0;
	let start;
	let end;
	for (const match of style.gridTemplateColumns.matchAll(/\[([^\]]*)\]|(-?[\d.]+)px/g)) if (match[1] !== void 0) {
		const names = match[1].split(/\s+/);
		if (names.includes("prose-start")) start = offset;
		if (names.includes("prose-end")) end = offset - gap;
	} else offset += Number(match[2]) + gap;
	if (start === void 0 || end === void 0) return grid.getBoundingClientRect();
	const edge = (side) => parseFloat(style[`border${side}Width`]) + parseFloat(style[`padding${side}`]);
	const left = style.direction === "rtl" ? frame.width - edge("Right") - end : edge("Left") + start;
	const right = style.direction === "rtl" ? frame.width - edge("Right") - start : edge("Left") + end;
	const corner = (x, y) => {
		const point = frame.matrix.transformPoint({
			x,
			y
		});
		return {
			left: point.x,
			right: point.x,
			top: point.y,
			bottom: point.y
		};
	};
	return union([
		corner(left, 0),
		corner(right, 0),
		corner(left, frame.height),
		corner(right, frame.height)
	]);
}
const railStands = (main = layoutBox()) => {
	if (!main || (document.body.dataset.annotations ?? "overlay") !== "overlay" || document.body.dataset.rail === "none") return false;
	const width = parseFloat(getComputedStyle(main).getPropertyValue("--rail")) || 0;
	return shellRight() - proseRect(main).right >= width;
};
const windowHoldsRail = (main = layoutBox() ?? document.body) => {
	const style = getComputedStyle(main);
	const length = (name) => parseFloat(style.getPropertyValue(name)) || 0;
	return document.body.getBoundingClientRect().width >= length("--col") + 2 * length("--rail");
};
const title = () => {
	const main = document.querySelector("body > main");
	const parts = main && getComputedStyle(main).getPropertyValue("--lf-layout-box").trim() !== "1" ? main.querySelector(":scope > [data-lf-views=\"parts\"]") : null;
	let marked = false;
	for (let node = parts?.previousElementSibling; node; node = node.previousElementSibling) if (!node.classList.contains("scroll")) {
		node.classList.add("scroll");
		marked = true;
	}
	return marked;
};
const HEAD = "--lf-layout-head-h";
const head = () => {
	const body = document.body;
	if (!body) return false;
	const header = layoutBox()?.querySelector(":scope > header");
	const value = header && getComputedStyle(header).position === "sticky" ? `${Math.ceil(header.getBoundingClientRect().height)}px` : "";
	if (body.style.getPropertyValue(HEAD) === value) return false;
	if (value) setRuntimeRootStyle(body, HEAD, value);
	else removeRuntimeRootStyle(body, HEAD);
	return true;
};
const readDocumentHeaders = () => {
	const titled = title();
	const headed = head();
	return { changed: titled || headed };
};

//#endregion
export { ADDRESSABLE, PAGE_CONTROL_RANK, PAGE_INTERFACE, PRESENTATION, UPGRADE, activityTransitionDue, addressableLabel, addressableName, addressableSays, addressableWord, addressedElements, afterPresentation, ago, aimTargetAt, aimTargets, aimedTop, anchorAt, anchorBox, anchorElement, anchorFor, anchorForPassage, anchorForRange, anchorName, anchorReaches, anchorReading, anchorView, anchoringIsReady, annotationAt, atScrollEnd, boundedBlockOf, carriedAnchor, chosenSince, chromeForeground, chromeRoot, claimReachStop, clockValue, commitPoint, compoundReadingRegionId, containingReadingRegionFor, contentRides, cutFrames, datumAimTarget, datumLabel, declaredName, deferredArrival, designPressAt, effectiveScroller, elementFrame, exactTarget, followingItsEnd, fragmentTarget, headerLevels, holdArrivingBounds, isAddressable, leadingTitle, lightSeat, livePoint, localScrollBy, markPagePresented, markPageUpgraded, markStateApplied, moveScrollerBy, nameAnchor, nameable, observeServerNow, observeWorkingGrace, onReadingInput, openDocumentLayout, pageControls, pageControlsChanged, pageReadiness, pageReadingRegion, pageScroller, passageBoxes, passageGeometry, placeKept, placePoints, pointBand, pointInto, preserveReadingRegions, projectedDatum, proseRect, quietSince, railStands, rangeGeometry, reachScrollers, reachable, readingRegion, readingRegionFor, readingRegions, recentReadingRegion, refreshAnchorView, regionScrollBehavior, regionsSettled, registerPageControl, registerReadingRegion, releaseReachStop, resolveAnchor, resolvedInMessage, revealAddressed, saidNow, scheduleDocumentLayout, scrollAxes, scrollChainOf, scrollChoices, scrollLimit, scrollToEnd, scrollerFor, scrollersOf, scrollsWith, sectionLabel, sectionOf, setAnchoringReady, settleDocumentLayout, settlePageInterface, shortAgo, showReadingSubject, shownRegionBounds, startScroll, stopScroll, targetElement, targetParts, targetPlace, targetRange, targetSegments, targetSurface, tickClock, unclaimedVisualGesture, unconcealedReadingRegions, userReadingRegion, visualAt, visualPartLabel, visualParts, visualSelector, watchReadingRegionTransitions, whenArrived, whileInterfaceConnected, widgetWord, windowHoldsRail };