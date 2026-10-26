import { PRESSES, WORKS, keeps, layoutPx, move, nativeLayerHolding, nextFrame, nextRender, renderedParent, shadowHost, sizeObserver, under, upFrom } from "./bundle-dom-move.js";
import { clamp, clippedContents, headerCuts, hostIn, inUi, nearObserver, nearWindow, overlaps, registry, scrollContainer, scrollsContent, shownParts, skipped, tagsDeclaring, uiInside, watchArrivals } from "./bundle-geometry.js";
import { TEXT_BLOCK, anchorKey, documentChanged, isElementName, marks } from "./bundle-context.js";
import { PRESSABLE, layoutChanged, repaintPage } from "./bundle-errors.js";
import { atScrollEnd, compoundReadingRegionId, registerReadingRegion, scrollToEnd } from "./bundle-reading-regions.js";
import { chromeRoot, pageControlsChanged } from "./bundle-page-controls.js";
import { DATUM, authoredScope, blockAt, closestAcross, contextAround, cut, elementById, elementReading, excerptWords, fileModelsPassage, findQuote, inChrome, layoutBox, leafSurface, neighbourhood, pageDocument, pageQueryAll, pageText, quoteFrom, rangeOf, readingFrom, segmentsIn, settledAway, spanIn, textNodesUnder } from "./bundle-passages.js";
import { fragmentId } from "./bundle-initial-render.js";

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
//#region runtime/visual-parts.js
const registrations = /* @__PURE__ */ new WeakMap();
const words = (value) => String(value ?? "").replace(/\s+/g, " ").trim();
function registerVisualParts(source, read, { reveal = null, label = null } = {}) {
	if (registrations.has(source)) throw new TypeError("A visual source may register its parts only once");
	registrations.set(source, {
		read,
		reveal,
		label
	});
	return { update: () => layoutChanged(source) };
}
function visualPartAdmission(visual, declaration) {
	if (!declaration || typeof declaration !== "object") return null;
	const { prefixes } = declaration;
	if (prefixes) return (id) => prefixes.some((prefix) => id !== prefix && id.startsWith(prefix));
	return visual.hasAttribute(declaration.parts) ? () => true : null;
}
const revealsVisualParts = (source) => Boolean(registrations.get(source)?.reveal);
function revealRegisteredVisualPart(source, id) {
	const reveal = registrations.get(source)?.reveal;
	if (reveal) reveal(id);
	return registeredVisualPart(source, id);
}
function visualPartProblems(source, declaration) {
	if (!declaration || typeof declaration !== "object") return [];
	if (!registrations.has(source)) return [{ kind: "unregistered" }];
	const parts = registeredVisualParts(source);
	const admission = visualPartAdmission(source, declaration);
	const outside = declaration.prefixes ? parts.filter((part) => !admission(part.id)).map((part) => part.id) : [];
	return outside.length ? [{
		kind: "unadmitted-parts",
		parts: outside
	}] : [];
}
function registeredVisualParts(source) {
	const read = registrations.get(source)?.read;
	if (!read) return [];
	const seenIds = /* @__PURE__ */ new Set();
	const seenElements = /* @__PURE__ */ new Set();
	const seenSurfaces = /* @__PURE__ */ new Set();
	return [...read()].map((part, index) => {
		const number = index + 1;
		const id = part.id;
		const element = part.element;
		const label = words(part.label);
		const surface = part.surface ?? element;
		if (typeof id !== "string" || !id || /\s/.test(id)) throw new TypeError(`Visual part ${number} has no single-token id`);
		if (!(element instanceof Element) || element === source || !under(element, source)) throw new TypeError(`Visual part ${id} has no descendant Element`);
		if (!label) throw new TypeError(`Visual part ${id} has no label`);
		if (!(surface instanceof Element) || !under(surface, element)) throw new TypeError(`Visual part ${id} has no descendant Element surface`);
		if (seenIds.has(id)) throw new TypeError(`A visual source registered part ${id} twice`);
		if (seenElements.has(element)) throw new TypeError("A visual source registered one element as two parts");
		if (seenSurfaces.has(surface)) throw new TypeError("A visual source registered one surface for two parts");
		seenIds.add(id);
		seenElements.add(element);
		seenSurfaces.add(surface);
		return {
			id,
			element,
			label,
			surface
		};
	});
}
const registeredVisualPart = (source, id) => registeredVisualParts(source).find((part) => part.id === id) ?? null;
const registeredVisualPartLabel = (source, id) => {
	const current = registeredVisualPart(source, id)?.label;
	if (current) return current;
	const label = registrations.get(source)?.label?.(id);
	return words(label) || null;
};
function registeredVisualPartAt(source, target, admits = () => true) {
	const byElement = new Map(registeredVisualParts(source).filter(admits).map((part) => [part.element, part]));
	for (let current = target; current && current !== source; current = upFrom(current)) {
		const part = byElement.get(current);
		if (part) return part;
	}
	return null;
}

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
		if (node.nodeType === Node.TEXT_NODE && node.data.trim()) return null;
		if (node.nodeType !== Node.ELEMENT_NODE || uiInside(node, container)) continue;
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
const saysItself = (element) => element.matches("p,li,h1,h2,h3,h4,h5,h6,td,th,pre,blockquote,dd,dt,figcaption,summary") || registry[element.localName]?.["x-word"] === "module" && element.lfSays?.() || [...element.childNodes].some((node) => node.nodeType === Node.TEXT_NODE && node.data.trim());
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
	return pageQueryAll(DATUM).filter((datum) => under(datum, source) && datum.dataset.lfProjection === source.id && (dataSource === null || datum.dataset.lfSource === dataSource) && (identity === null ? datum.dataset.lfDatum === key : datum.dataset.lfIdentity === identity));
}
const projectedDatum = (source, key) => {
	const matches = currentDatums(source, key);
	return matches.length === 1 ? matches[0] : null;
};
function datumLabel(anchor) {
	if (!anchor?.datum) return "";
	documentChanged();
	const source = sectionOf(anchor);
	const datums = currentDatums(source, anchor.datum, anchor.identity ?? null, anchor.source ?? null);
	const label = datums.length ? datums.length === 1 && datums[0].dataset.lfDatumLabel : source?.lfDatumLabel?.(anchor.datum);
	return typeof label === "string" ? label.trim() : "";
}
function suppliedDatum(source, key) {
	const supplied = source?.lfDataDatum?.(key);
	return supplied instanceof Element && under(supplied, source) && supplied.dataset.lfProjection === source.id ? supplied : null;
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
const visualAdmission = (visual) => visual ? visualPartAdmission(visual, registry[visual.localName]?.["x-visual"]) : null;
const wholeVisualSurface = (element) => registry[element?.localName]?.["x-visual"] ? element : null;
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
	return admits ? registeredVisualPartAt(visual, target, (part) => admits(part.id)) : null;
}
const visualPartLabel = (visual, part) => admitsVisualPart(visual, part) ? registeredVisualPartLabel(visual, part) : null;
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
	for (let element = target; element; element = upFrom(element)) if (claimsVisualGesture(element)) return false;
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
	const at = target?.nodeType === 1 ? target : target?.parentElement;
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
	let at = node?.nodeType === 1 ? node : node?.parentElement;
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
	const sourceRevision = datum.dataset.lfSourceRevision;
	return {
		section: datum.dataset.lfProjection,
		datum: datum.dataset.lfDatum,
		...fields,
		...datum.dataset.lfSource && sourceRevision ? {
			source: datum.dataset.lfSource,
			source_revision: sourceRevision
		} : {},
		...datum.dataset.lfIdentity ? { identity: datum.dataset.lfIdentity } : {}
	};
};
function datumAimTarget(datum) {
	if (!(datum instanceof Element) || !datum.matches("[data-lf-projection][data-lf-datum]")) return null;
	const anchor = anchorForDatum(datum);
	const owner = sectionOf(anchor);
	if (!owner || !under(datum, owner)) return null;
	return {
		anchor,
		element: datum,
		label: datum.dataset.lfDatumLabel?.trim() || aimLabel(datum)
	};
}
const anchorForRange = (range) => anchorForPassage(segmentsIn(range), range.commonAncestorContainer);
function anchorForPassage(segments, node) {
	const holder = node.nodeType === Node.ELEMENT_NODE ? node : upFrom(node);
	const { text: quote, units } = readingFrom(segments);
	const dataNodes = new Set(segments.map((seg) => closestAcross(seg.node, DATUM)).filter(Boolean));
	const [onlyDatum] = dataNodes;
	const datum = dataNodes.size === 1 && segments.every((seg) => closestAcross(seg.node, "[data-lf-projection][data-lf-datum]") === onlyDatum) ? onlyDatum : null;
	if (datum) return anchorForDatum(datum, quote ? { quote } : {});
	const section = closestAcross(holder, "[id]:not(.lf-ui):not([id^=\"lf-\"])")?.id ?? null;
	if (!quote) return { section };
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
		const resolved = quote && resolveAnchor(anchor);
		if (resolved?.exact && resolved.kind === "passage") {
			const first = resolved.segments[0];
			const last = resolved.segments.at(-1);
			const from = units[0].start;
			const to = units.at(-1).end;
			if (first.node === from.node && first.start === from.offset && last.node === to.node && last.end === to.offset) return anchor;
		}
		if ([...prefix].length < width && [...suffix].length < width) return {
			...anchor,
			detached: true
		};
	}
}
const controlName = (control) => control.isContentEditable ? accessibleName(control) : ownName(control) || (control.matches(PRESSES) ? control.innerText?.trim().replace(/\s+/g, " ") || addressableWord(control) : "");
const controlIdentity = (control) => control.control ?? control;
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
		if (!holder.checkVisibility({
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
	let at = node?.nodeType === 1 ? node : node?.parentElement;
	if (!at) return null;
	const pressed = designPressAt(at);
	const control = pressed?.matches(`${WORKS},${genericVisualSelector}`) && controlIdentity(pressed);
	const visual = visualAt(at, { unclaimed: false });
	const declared = declaredVisualSelector();
	if (declared && visual?.element.matches(declared)) at = visual.element;
	else if (pressed?.control || visual && control?.matches(PRESSES) && under(visual.element, control)) at = control;
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
	if (!part) return control === element ? {
		...target,
		controlElement: control,
		controlFaces: [control, ...control.labels ?? []]
	} : target;
	const faces = [partElement, ...partElement.labels ?? []];
	const detail = [.../* @__PURE__ */ new Set([controlContext(partElement, contexts), ...[...partElement.labels ?? []].map((label) => quoteFrom(textNodesUnder(label).filter(({ node }) => !under(node, partElement))))])].filter((text) => text && text !== part).join(" · ");
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
				const resolved = captured.quote && resolveAnchor(captured);
				const attachment = resolved?.kind === "passage" && passageGeometry(resolved)?.attachment;
				if (resolved?.exact && attachment && resolved.segments.every(({ node }) => under(node, face)) && overlaps(attachment, face.getBoundingClientRect()) && visiblePassage(resolved.segments)) {
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
		label: aimLabel(sectionOf({ section: visual.id }), visual.part.label),
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
	const targets = candidates.map((node) => options.design ? designTargetAt(node, options.marginTargetAt, reading) : aimTargetAt(node, options)).filter(Boolean);
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
		if (!(!anchoredToData || basis?.dataset.lfSource === anchor.source && (anchor.identity ? datums.length > 0 && basis.dataset.lfIdentity === anchor.identity : basis.dataset.lfSourceRevision === anchor.source_revision))) {
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
		if (!datums.length) {
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
			...resolvedElement({ element: datums[0] }),
			datumElement: datums[0],
			exact: true,
			status: "exact"
		};
		const segments = findQuote(pageText(), anchor.quote, anchor, datums[0]);
		return segments.length ? {
			...resolvedPassage({
				place: annotationAt(segments[0].node, () => datums[0]),
				segments
			}),
			datumElement: datums[0],
			exact: true,
			status: "exact"
		} : {
			...resolvedElement({ element: datums[0] }),
			datumElement: datums[0],
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
	if (!segments.length) return null;
	const face = anchor.part && closestAcross(segments[0].node, WORKS);
	const controlFace = face && segments.every(({ node }) => closestAcross(node, WORKS) === face);
	return resolvedPassage({
		place: controlFace ? face : annotationAt(segments[0].node),
		segments
	});
}
const fragmentTarget = (fragment) => fragment ? targetElement(resolveAnchor({ section: fragmentId(fragment) })) : null;

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
const following = (hold) => hold.bounded.matches(FOLLOWING) && !hold.left && !(hold.pinned !== null && hold.box.scrollTop < hold.pinned - 2 && !atScrollEnd(hold.box));
const heldBy = (box) => {
	const hold = byBox.get(box);
	return hold?.box === box && registered.has(hold) ? hold : null;
};
const followingItsEnd = (box) => {
	const hold = heldBy(box);
	return Boolean(hold && following(hold));
};
const boundedBlockOf = (box) => heldBy(box)?.bounded ?? null;
function holdBlock(bounded) {
	const hold = {
		bounded,
		id: regionId(bounded),
		bound: null,
		box: null,
		pinned: null,
		left: false
	};
	let stopRegion = null;
	const onScroll = () => {
		if (bounded.hasAttribute("hidden")) return;
		hold.left = !atScrollEnd(hold.box);
		if (!hold.left) hold.pinned = hold.box.scrollTop;
	};
	const letGo = () => {
		hold.box?.removeEventListener("scroll", onScroll);
		if (hold.box && hold.box !== bounded) resize.unobserve(hold.box);
		stopRegion?.();
		stopRegion = null;
		hold.box = null;
		registered.delete(hold);
	};
	const adopt = (box) => {
		if (box === hold.box) return;
		letGo();
		box.addEventListener("scroll", onScroll, { passive: true });
		resize.observe(box);
		byBox.set(box, hold);
		hold.box = box;
		hold.left = false;
		hold.pinned = null;
		stopRegion = registerReadingRegion({
			id: hold.id,
			host: bounded,
			body: box
		});
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
		adopt(scrollerOf(bounded));
		if (!bounded.matches(FOLLOWING)) return;
		if (!following(hold)) {
			hold.left = true;
			return;
		}
		scrollToEnd(hold.box);
		hold.pinned = hold.box.scrollTop;
	};
	hold.sync = () => sync(false);
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
			if (!holds.has(el)) holds.set(el, holdBlock(el));
			const hold = holds.get(el);
			if (!registered.has(hold) || hold.bound !== el.getAttribute(BOUND)) hold.sync();
		},
		leave: (el) => holds.get(el)?.sync()
	});
}

//#endregion
//#region runtime/css-anchors.js
const anchorNames = /* @__PURE__ */ new WeakMap();
let anchorOrdinal = 0;
const nextName = () => `--lf-a${++anchorOrdinal}`;
const partOf = (name) => name.slice(2);
const partNamed = (el) => el.part.contains(partOf(anchorNames.get(el)));
let partRules = null;
const declared = /* @__PURE__ */ new Set();
const given = /* @__PURE__ */ new WeakMap();
const watchedTrees = /* @__PURE__ */ new WeakSet();
const restoreParts = (el) => {
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
function anchorReading(el, name = anchorNames.get(el) ?? nextName()) {
	const start = contentStarts.get(el);
	if (start) return {
		el,
		name: start.name
	};
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
	const written = el.style.anchorName;
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
	} else if (write) el.style.anchorName = write;
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
	for (let at = target; at instanceof Element; at = renderedParent(at)) if (at.getRootNode() === document && !at.contains(chromeRoot) && getComputedStyle(at).anchorScope === "all") el = renderedParent(at) ?? at;
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
	const layer = nativeLayerHolding(holder);
	if (layer !== nativeLayerHolding(box)) return !layer;
	const order = hostIn(holder, document).compareDocumentPosition(box);
	return Boolean(order & Node.DOCUMENT_POSITION_FOLLOWING) && !(order & Node.DOCUMENT_POSITION_CONTAINED_BY);
}
function scrollsWith(node, box) {
	for (let at = node; at !== box; at = renderedParent(at)) {
		if (!at) return false;
		if (at instanceof Element && (!/^(static|relative)$/.test(getComputedStyle(at).position) || at !== node && scrollsContent(at))) return false;
	}
	return true;
}
function carriedAnchor(scroller, near = null) {
	if (anchorElement(scroller) !== scroller || nativeLayerHolding(scroller)) return null;
	const carried = (node) => node instanceof Element && !/^(br|wbr)$/.test(node.localName) && anchorElement(node) === node && node.getClientRects().length > 0 && /^(static|relative)$/.test(getComputedStyle(node).position);
	if (!near) {
		for (const child of scroller.children) if (carried(child)) return child;
		return contentStart(scroller);
	}
	for (let before = near.previousSibling, after = near.nextSibling; before || after; before = before?.previousSibling, after = after?.nextSibling) for (const node of [before, after]) if (carried(node)) return node;
	return contentStart(scroller);
}
function anchorFor(context) {
	const physical = context instanceof Element ? context : context?.parentElement;
	if (!physical) return null;
	const anchor = anchorElement(physical);
	if (context === physical || anchor !== physical || !scrollContainer(physical)) return anchor;
	return carriedAnchor(physical, context) ?? anchor;
}
const contentStarts = /* @__PURE__ */ new WeakMap();
const starts = /* @__PURE__ */ new WeakMap();
const START = "data-lf-content-start";
function contentStart(scroller) {
	if (!scroller.firstChild || [...scroller.childNodes].some((node) => node.nodeType !== Node.TEXT_NODE && !(node instanceof Element && /^(br|wbr)$/.test(node.localName)))) return null;
	let handle = starts.get(scroller);
	if (!handle) {
		if (!CSS.supports("anchor-name", "attr(data-lf-content-start type(<custom-ident>))") || !/^(block|inline-block|flow-root|list-item)$/.test(getComputedStyle(scroller).display) || !/^(none|normal)$/.test(getComputedStyle(scroller, "::before").content) || getComputedStyle(scroller, "::first-letter").float !== "none") return null;
		handle = { getBoundingClientRect() {
			const range = document.createRange();
			for (const lead of scroller.childNodes) {
				if (lead.nodeType === Node.TEXT_NODE) {
					range.setStart(lead, 0);
					range.setEnd(lead, Math.min(1, lead.length));
				} else range.selectNode(lead);
				const [rect] = range.getClientRects();
				if (rect) return rect;
			}
			return range.getBoundingClientRect();
		} };
		starts.set(scroller, handle);
		contentStarts.set(handle, {
			scroller,
			name: nextName()
		});
	}
	const { name } = contentStarts.get(handle);
	if (scroller.getRootNode() === document) keeps(scroller, START, name);
	else namePart(scroller, name, "::before");
	return handle;
}
const anchorHolder = (anchor) => contentStarts.get(anchor)?.scroller ?? anchor;
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
		if (!(box instanceof Element)) return null;
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
	for (let at = el; at instanceof Element; at = renderedParent(at)) {
		const { moves, slides } = movement(getComputedStyle(at));
		if (!moves) continue;
		if (!slides || !(at instanceof HTMLElement) || at.currentCSSZoom !== 1) return null;
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
	const edge = (value) => `calc(${layoutPx(value)} - var(--lf-paint-outset, 0px))`;
	return `inset(${edge(y ? 0 : -1e5)} ${edge(-width - (x ? 0 : open))} ${edge(-height - (y ? 0 : open))} ${edge(x ? 0 : -1e5)})`;
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
		return {
			anchor,
			reading: anchor && anchorReading(anchor),
			at: anchor && anchorBox(anchor),
			band: band ?? nowhere,
			axes: {
				x: false,
				y: true
			}
		};
	});
}
function cutFrames(levels, frames, make) {
	const kept = frames.slice(Math.max(0, frames.length - levels.length));
	const chain = [...Array.from({ length: levels.length - kept.length }, make), ...kept];
	const was = frames[0];
	if (chain[0] && was && chain[0] !== was && was.parentNode) move(was.parentNode, chain[0], was);
	for (let i = 1; i < chain.length; i++) if (chain[i].parentNode !== chain[i - 1]) move(chain[i - 1], chain[i], null);
	for (const dropped of frames.slice(0, frames.length - kept.length)) dropped.remove();
	levels.forEach(({ anchor, band, axes, at, reading }, i) => {
		if (reading) nameAnchor(reading);
		anchorAt(chain[i], anchor, {
			left: band.left,
			top: band.top,
			right: band.left,
			bottom: band.top
		}, at);
		chain[i].style.clipPath = cutPath(axes, band);
	});
	return chain;
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
		viewObserver.unobserve(view.target);
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
			nodes: /* @__PURE__ */ new Map()
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
	let at = node?.nodeType === Node.ELEMENT_NODE ? node : node?.parentElement ?? null;
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
	for (let at = line; at && at !== target; at = upFrom(at)) for (let before = at.previousSibling; before; before = before.previousSibling) if (drawn(before)) return false;
	return true;
}
const drawn = (node) => node.nodeType === Node.TEXT_NODE ? Boolean(node.data.trim()) && Boolean(node.parentElement?.checkVisibility()) : node.nodeType === Node.ELEMENT_NODE && !inChrome(node) && node.checkVisibility() && [...node.getClientRects()].some((box) => box.width && box.height);
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
//#region runtime/content-layout.js
let marginContentLayoutOpen = false;
let readFinished = null;
let marginContentLayoutPending = 0;
let marginContentLayoutRead = -1;
function marginContentLayoutPass(time) {
	marginContentLayoutPending = 0;
	if (time === marginContentLayoutRead) {
		marginContentLayoutPending = nextFrame(marginContentLayoutPass);
		return;
	}
	marginContentLayoutRead = time;
	readMarginContentLayout();
}
let headSizes = null;
let watchedHead = null;
function watchHead() {
	const header = document.documentElement.lfInitial.layoutBox()?.querySelector(":scope > header") ?? null;
	if (header === watchedHead) return;
	headSizes ??= sizeObserver(() => scheduleMarginContentLayout());
	if (watchedHead) headSizes.unobserve(watchedHead);
	if (header) headSizes.observe(header);
	watchedHead = header;
}
function readMarginContentLayout() {
	const { changed } = document.documentElement.lfInitial.marginContentLayout();
	watchHead();
	if (changed) layoutChanged(pageDocument());
	readFinished?.(changed);
	if (!changed) return;
	repaintPage();
	pageControlsChanged();
}
const railStands = (main = layoutBox()) => (main?.getAttribute("data-lf-margin") ?? "").split(" ").includes("rail");
function scheduleMarginContentLayout() {
	if (marginContentLayoutOpen) marginContentLayoutPending ||= nextRender(marginContentLayoutPass);
}
function settleMarginContentLayout() {
	if (marginContentLayoutOpen) readMarginContentLayout();
}
const ROOM = marks["x-space"].paint;
const BREAKOUT = `[${ROOM}]`;
const bringsBreakout = (node) => node.nodeType === Node.ELEMENT_NODE && (node.matches(BREAKOUT) || node.querySelector(BREAKOUT) !== null);
function readBreakouts() {
	const { changed } = document.documentElement.lfInitial.breakouts();
	if (!changed) return;
	layoutChanged(pageDocument());
	repaintPage();
}
const mayChangeMarginContentLayout = (node) => node.matches("body > main > *, body > main > [data-lf-views=\"parts\"] > *, [data-lf-views-flow=\"page\"] > *");
function openMarginContentLayout({ onRead }) {
	readFinished = onRead;
	marginContentLayoutOpen = true;
	document.addEventListener("toggle", scheduleMarginContentLayout, { capture: true });
	window.addEventListener("resize", scheduleMarginContentLayout);
	const main = pageDocument();
	if (main) new MutationObserver((records) => {
		if (records.some((record) => record.type === "attributes" && record.attributeName === "hidden" && mayChangeMarginContentLayout(record.target))) readMarginContentLayout();
		else if (records.some((record) => record.type === "attributes" ? bringsBreakout(record.target) : [...record.addedNodes].some(bringsBreakout))) readBreakouts();
	}).observe(main, {
		childList: true,
		subtree: true,
		attributes: true,
		attributeFilter: [
			ROOM,
			"hidden",
			"open"
		]
	});
	readMarginContentLayout();
}

//#endregion
export { ADDRESSABLE, addressableLabel, addressableName, addressableSays, addressableWord, addressedElements, aimTargetAt, aimTargets, anchorAt, anchorBox, anchorElement, anchorFor, anchorForPassage, anchorForRange, anchorName, anchorReaches, anchorReading, anchorView, anchoringIsReady, annotationAt, boundedBlockOf, carriedAnchor, commitPoint, cutFrames, datumAimTarget, datumLabel, declaredName, designPressAt, exactTarget, followingItsEnd, fragmentTarget, headerLevels, holdArrivingBounds, isAddressable, leadingTitle, lightSeat, livePoint, nameAnchor, nameable, openMarginContentLayout, passageBoxes, passageGeometry, placePoints, pointBand, pointInto, projectedDatum, railStands, rangeGeometry, refreshAnchorView, registerVisualParts, resolveAnchor, resolvedInMessage, revealAddressed, scheduleMarginContentLayout, scrollsWith, sectionLabel, sectionOf, setAnchoringReady, settleMarginContentLayout, targetElement, targetParts, targetPlace, targetRange, targetSegments, targetSurface, unclaimedVisualGesture, visualAt, visualPartLabel, visualPartProblems, visualParts, visualSelector, widgetWord };