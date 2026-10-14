import {
  fragmentId
} from "./bundle-initial-render.js";
import {
  SCROLL_SLACK,
  atScrollEnd,
  compoundReadingRegionId,
  registerReadingRegion,
  scrollToEnd
} from "./bundle-presence.js";
import {
  CONTEXT,
  DATUM,
  TEXT_BLOCK,
  authoredScope,
  blockAt,
  closestAcross,
  contextAround,
  cut,
  elementById,
  elementReading,
  excerptWords,
  fileModelsPassage,
  findQuote,
  inChrome,
  leafSurface,
  neighbourhood,
  pageDocument,
  pageQueryAll,
  pageText,
  quoteFrom,
  rangeOf,
  readingFrom,
  segmentsIn,
  settledAway,
  spanIn,
  textNodesUnder
} from "./bundle-passage-facts.js";
import {
  PRESSABLE,
  clippedContents,
  exceptionText,
  hostIn,
  inUi,
  layoutChanged,
  nearObserver,
  nearWindow,
  overlaps,
  registry,
  scrollContainer,
  scrollsContent,
  shownBox,
  shownParts,
  skipped,
  tagsDeclaring,
  uiInside,
  watchArrivals
} from "./bundle-page-paint.js";
import {
  PRESSES,
  WORKS,
  keeps,
  layoutPx,
  move,
  nativeLayerHolding,
  renderedParent,
  shadowHost,
  sizeObserver,
  under,
  upFrom
} from "./bundle-sample-visibility.js";
import {
  anchorKey,
  isElementName
} from "./bundle-queued-work.js";

// runtime/chrome.js
var chromeRoot = document.createElement("div");
chromeRoot.className = "lf-chrome";
var chromeForeground = document.createElement("dialog");

// runtime/visual-parts.js
var registrations = /* @__PURE__ */ new WeakMap();
var words = (value) => String(value ?? "").replace(/\s+/g, " ").trim();
function registerVisualParts(source, read, { reveal = null, label = null } = {}) {
  if (registrations.has(source))
    throw new TypeError("A visual source may register its parts only once");
  registrations.set(source, { read, reveal, label });
  return { update: () => layoutChanged(source) };
}
var hasVisualParts = (source) => registrations.has(source);
function visualPartAdmission(visual, declaration) {
  if (!declaration || typeof declaration !== "object") return null;
  const { prefixes } = declaration;
  if (prefixes)
    return (id) => prefixes.some((prefix) => id !== prefix && id.startsWith(prefix));
  return visual.hasAttribute(declaration.parts) ? () => true : null;
}
var revealsVisualParts = (source) => Boolean(registrations.get(source)?.reveal);
function revealRegisteredVisualPart(source, id) {
  const reveal = registrations.get(source)?.reveal;
  if (reveal) reveal(id);
  return registeredVisualPart(source, id);
}
function visualPartProblems(source, declaration) {
  if (!declaration || typeof declaration !== "object") return [];
  if (!hasVisualParts(source)) return [{ kind: "unregistered" }];
  try {
    const parts = registeredVisualParts(source);
    const admission = visualPartAdmission(source, declaration);
    const outside = declaration.prefixes ? parts.filter((part) => !admission(part.id)).map((part) => part.id) : [];
    return outside.length ? [{ kind: "unadmitted-parts", parts: outside }] : [];
  } catch (error) {
    return [{ kind: "unreadable", error: exceptionText(error) }];
  }
}
function registeredVisualParts(source) {
  const read = registrations.get(source)?.read;
  if (!read) return [];
  const seenIds = /* @__PURE__ */ new Set();
  const seenElements = /* @__PURE__ */ new Set();
  const seenSurfaces = /* @__PURE__ */ new Set();
  return [...read()].map((part, index) => {
    const number = index + 1;
    const id = words(part?.id);
    const element = part?.element;
    const label = words(part?.label);
    const surface = part?.surface ?? element;
    if (!id || /\s/.test(id))
      throw new TypeError(`Visual part ${number} has no single-token id`);
    if (!(element instanceof Element) || element === source || !under(element, source))
      throw new TypeError(`Visual part ${id} has no descendant Element`);
    if (!label) throw new TypeError(`Visual part ${id} has no label`);
    if (!(surface instanceof Element) || !under(surface, element))
      throw new TypeError(`Visual part ${id} has no descendant Element surface`);
    if (seenIds.has(id))
      throw new TypeError(`A visual source registered part ${id} twice`);
    if (seenElements.has(element))
      throw new TypeError("A visual source registered one element as two parts");
    if (seenSurfaces.has(surface))
      throw new TypeError("A visual source registered one surface for two parts");
    seenIds.add(id);
    seenElements.add(element);
    seenSurfaces.add(surface);
    return { id, element, label, surface };
  });
}
function usableVisualParts(source) {
  try {
    return registeredVisualParts(source);
  } catch {
    return [];
  }
}
var registeredVisualPart = (source, id) => registeredVisualParts(source).find((part) => part.id === id) ?? null;
var registeredVisualPartLabel = (source, id) => {
  const current = registeredVisualPart(source, id)?.label;
  if (current) return current;
  const label = registrations.get(source)?.label?.(id);
  return words(label) || null;
};
function usableVisualPartAt(source, target, admits = () => true) {
  const byElement = new Map(
    usableVisualParts(source).filter(admits).map((part) => [part.element, part])
  );
  for (let current = target; current && current !== source; current = upFrom(current)) {
    const part = byElement.get(current);
    if (part) return part;
  }
  return null;
}

// runtime/addressable-names.js
var HTML_WORDS = {
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
  if (registry[tag]?.["x-word"] === "module") {
    const own = addressable.lfWord?.();
    if (own) return own;
  }
  if (registry[tag]?.["x-ask-context"]) return "ask";
  if (tag.startsWith("lf-")) return tag.slice(3);
  if (tag === "pre")
    return addressable.querySelector(":scope > code") ? "code" : "block";
  return HTML_WORDS[tag] ?? tag;
}
function addressableSays(addressable) {
  if (!addressable) return "";
  const own = registry[addressable.localName]?.["x-word"] === "module" ? addressable.lfSays?.() : "";
  return own || elementReading(addressable);
}
var TITLES = "summary, h1, h2, h3, h4, h5, h6, strong";
function leadingTitle(container) {
  for (const node of container.childNodes) {
    if (node.nodeType === Node.TEXT_NODE && node.data.trim()) return "";
    if (node.nodeType !== Node.ELEMENT_NODE || uiInside(node, container)) continue;
    if (node.matches(TITLES)) return elementReading(node, "wrote");
    if (["header", "hgroup"].includes(node.localName)) return leadingTitle(node);
  }
  return "";
}
function addressableName(element) {
  if (!element) return "";
  const attribute = registry[element.localName]?.["x-name"];
  const declared2 = attribute && element.getAttribute(attribute)?.trim();
  return declared2 || leadingTitle(element);
}
var LABEL_WORDS = 60;
var captionOf = (element) => {
  const caption = [...element.children].find(
    (child) => child.matches("figcaption, caption") && !uiInside(child, element)
  );
  return caption ? elementReading(caption) : "";
};
var accessibleName = (element) => element.getAttribute("aria-label")?.trim() || (element.labels?.[0] ? elementReading(element.labels[0]) : "") || element.alt?.trim() || "";
var ownName = (element) => addressableName(element) || captionOf(element) || accessibleName(element);
var saysItself = (element) => element.matches(TEXT_BLOCK) || registry[element.localName]?.["x-word"] === "module" && element.lfSays?.() || [...element.childNodes].some(
  (node) => node.nodeType === Node.TEXT_NODE && node.data.trim()
);
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
  return excerptWords(
    addressableSays(element) || element.querySelector("[aria-label]")?.getAttribute("aria-label"),
    LABEL_WORDS
  );
}
var sectionLabel = (addressable) => [addressableWord(addressable), addressableLabel(addressable)].filter(Boolean).join(" \xB7 ");

// runtime/resolved-target.js
var resolvedElement = ({ element, place = element, surface = null }) => ({
  exact: true,
  status: "exact",
  datumElement: null,
  kind: "element",
  element,
  place,
  surface
});
var resolvedPassage = ({ place, segments }) => ({
  exact: true,
  status: "exact",
  datumElement: null,
  kind: "passage",
  place,
  segments
});
var targetElement = (resolved) => resolved?.kind === "element" ? resolved.element : null;
var targetSegments = (resolved) => resolved?.kind === "passage" ? resolved.segments : [];
var targetPlace = (resolved) => resolved?.place ?? null;
var exactTarget = (resolved) => resolved?.exact ? targetElement(resolved) ?? targetPlace(resolved) : null;
var targetRange = (resolved) => {
  const segments = targetSegments(resolved);
  if (!segments.length || segments.some(
    ({ node, start, end }) => !node.isConnected || start > node.length || end > node.length
  ))
    return null;
  return rangeOf(segments);
};
function rangeGeometry(range) {
  return {
    contextNode: range.startContainer.nodeType === Node.TEXT_NODE ? range.startContainer : range.startContainer.childNodes[range.startOffset] ?? range.startContainer,
    box: range.getBoundingClientRect(),
    attachment: [...range.getClientRects()].find((rect) => rect.width > 0 && rect.height > 0) ?? null
  };
}
function passageGeometry(resolved) {
  const range = targetRange(resolved);
  return range && rangeGeometry(range);
}
var targetSurface = (resolved) => resolved?.kind === "element" ? resolved.surface : null;
var targetParts = (resolved) => {
  const element = targetElement(resolved);
  if (!element) return [];
  const surface = targetSurface(resolved);
  return surface ? [element] : shownParts(element);
};

// runtime/anchor-resolution.js
var anchoringReady = false;
var anchoringIsReady = () => anchoringReady;
function setAnchoringReady(ready) {
  anchoringReady = ready;
}
var sectionOf = (anchor) => anchor?.section ? elementById(anchor.section) : null;
function currentDatums(source, key, identity = null, dataSource = null) {
  if (!source?.id) return [];
  return pageQueryAll(DATUM).filter(
    (datum) => under(datum, source) && datum.dataset.lfProjection === source.id && (dataSource === null || datum.dataset.lfSource === dataSource) && (identity === null ? datum.dataset.lfDatum === key : datum.dataset.lfIdentity === identity)
  );
}
var projectedDatum = (source, key) => {
  const matches = currentDatums(source, key);
  return matches.length === 1 ? matches[0] : null;
};
function datumLabel(anchor) {
  if (!anchor?.datum) return "";
  const source = sectionOf(anchor);
  const datums = currentDatums(
    source,
    anchor.datum,
    anchor.identity ?? null,
    anchor.source ?? null
  );
  const label = datums.length ? datums.length === 1 && datums[0].dataset.lfDatumLabel : source?.lfDatumLabel?.(anchor.datum);
  return typeof label === "string" ? label.trim() : "";
}
function suppliedDatum(source, key) {
  const supplied = source?.lfDataDatum?.(key);
  return supplied instanceof Element && under(supplied, source) && /** @type {HTMLElement | SVGElement} */
  supplied.dataset.lfProjection === source.id ? supplied : null;
}
function requireReference(verb, owner, attribute) {
  if (typeof attribute !== "string" || !Object.hasOwn(registry[owner.localName]?.["x-refers"] ?? {}, attribute))
    throw new TypeError(
      `${verb} ${owner.localName} attribute ${String(attribute)} is not declared by x-refers`
    );
}
function referencedProjection(owner, attribute) {
  const id = owner.getAttribute(attribute);
  if (!id) return null;
  const { tag, key } = registry[owner.localName]["x-refers"][attribute];
  if (tag) {
    const within = registry[tag]["x-unique"][key];
    const scopeOf = (element) => element.parentElement?.closest(within) ?? null;
    const scope2 = scopeOf(owner);
    return [...scope2?.querySelectorAll(tag) ?? []].find(
      (member) => scopeOf(member) === scope2 && member.getAttribute(key) === id
    ) ?? null;
  }
  const scope = authoredScope(owner);
  const page = pageDocument();
  return elementById(id, scope) ?? (scope === page ? null : elementById(id, page));
}
function addressedElements(source, key) {
  if (typeof source.lfElementsFor === "function")
    return [...source.lfElementsFor(key) ?? []].filter(
      (element) => element instanceof Element && under(element, source)
    );
  const part = visualPart(source, key)?.element;
  if (part) return [part];
  const datum = projectedDatum(source, key) ?? suppliedDatum(source, key);
  return datum ? [datum] : [];
}
function revealAddressed(source, key) {
  if (revealVisualPart(source, key)) return null;
  return source.lfRevealDatum?.(key) ?? null;
}
var visualAdmission = (visual) => visual ? visualPartAdmission(visual, registry[visual.localName]?.["x-visual"]) : null;
var wholeVisualSurface = (element) => registry[element?.localName]?.["x-visual"] ? element : null;
function visualParts(visual, { strict = false } = {}) {
  const admits = visualAdmission(visual);
  if (!admits) return [];
  return (strict ? registeredVisualParts(visual) : usableVisualParts(visual)).filter(
    (part) => admits(part.id)
  );
}
var admitsVisualPart = (visual, part) => visualAdmission(visual)?.(part) ?? false;
function visualPart(visual, part) {
  return admitsVisualPart(visual, part) ? registeredVisualPart(visual, part) : null;
}
function revealVisualPart(visual, part) {
  return admitsVisualPart(visual, part) ? revealRegisteredVisualPart(visual, part) : null;
}
function visualPartAt(visual, target) {
  const admits = visualAdmission(visual);
  return admits ? usableVisualPartAt(visual, target, (part) => admits(part.id)) : null;
}
var visualPartLabel = (visual, part) => admitsVisualPart(visual, part) ? registeredVisualPartLabel(visual, part) : null;
var declaredVisualSelector = () => [...tagsDeclaring((entry) => entry["x-visual"])].join(",");
var genericVisualSelector = "svg, img, figure";
var visualSelector = () => [declaredVisualSelector(), genericVisualSelector].filter(Boolean).join(",");
var outermostAcross = (element, selector) => {
  for (let parent = upFrom(element); parent; ) {
    const outer = closestAcross(parent, selector);
    if (!outer) break;
    element = outer;
    parent = upFrom(element);
  }
  return element;
};
var claimsVisualGesture = (element) => element.matches(`${PRESSES},${PRESSABLE}`);
var unclaimedVisualGesture = (target) => {
  if (inChrome(target) || inUi(target)) return false;
  for (let element = target; element; element = upFrom(element))
    if (claimsVisualGesture(element)) return false;
  return true;
};
function visualAt(target, { unclaimed = true } = {}) {
  if (unclaimed && !unclaimedVisualGesture(target)) return null;
  const declared2 = declaredVisualSelector();
  let element = declared2 ? closestAcross(target, declared2) : null;
  if (element) element = outermostAcross(element, declared2);
  else {
    element = closestAcross(target, genericVisualSelector);
    if (element) element = outermostAcross(element, genericVisualSelector);
  }
  if (!element) return null;
  const seat = closestAcross(element, ADDRESSABLE);
  return seat ? { element, id: seat.id, part: visualPartAt(element, target) } : null;
}
var designCandidates = () => [...tagsDeclaring(() => true), WORKS, "[data-lf-offer]", genericVisualSelector].join(
  ","
);
function designPressAt(target) {
  const at = target?.nodeType === 1 ? target : target?.parentElement;
  const hit = at && closestAcross(at, designCandidates());
  if (!hit || !hit.matches(genericVisualSelector)) return hit;
  return closestAcross(hit, `${PRESSES},${PRESSABLE}`) || visualAt(at, { unclaimed: false })?.element || hit;
}
var ADDRESSABLE = '[id]:not(.lf-ui):not([id^="lf-"])';
function isAddressable(at) {
  if (!at.matches(ADDRESSABLE) || inChrome(at) || inUi(at) || settledAway(at))
    return false;
  const visual = tagsDeclaring((entry) => entry["x-visual"]).join(",");
  return !(visual && at.parentElement && closestAcross(at.parentElement, visual));
}
function addressableAt(node) {
  let at = node?.nodeType === 1 ? node : node?.parentElement;
  for (; at; at = upFrom(at)) if (isAddressable(at)) return at;
  return null;
}
function annotationAt(node, fallback = addressableAt) {
  const formatted = tagsDeclaring(
    (entry) => entry["x-text-format"] === "markdown"
  ).join(",");
  return formatted && closestAcross(node, formatted) || blockAt(node) || fallback(node);
}
var lightSeat = (seat) => (seat && shadowHost(seat.getRootNode())) ?? seat;
var aimLabel = (addressable, says = addressableLabel(addressable)) => [addressableWord(addressable), says].filter(Boolean).join(": ");
var addressableAimTarget = (addressable) => ({
  anchor: { section: addressable.id },
  element: addressable,
  label: aimLabel(addressable),
  surface: wholeVisualSurface(addressable)
});
var anchorForDatum = (datum, fields = {}) => {
  const sourceRevision = datum.dataset.lfSourceRevision;
  return {
    section: datum.dataset.lfProjection,
    datum: datum.dataset.lfDatum,
    ...fields,
    ...datum.dataset.lfSource && sourceRevision ? { source: datum.dataset.lfSource, source_revision: sourceRevision } : {},
    ...datum.dataset.lfIdentity ? { identity: datum.dataset.lfIdentity } : {}
  };
};
function datumAimTarget(datum) {
  if (!(datum instanceof Element) || !datum.matches(DATUM)) return null;
  const anchor = anchorForDatum(datum);
  const owner = sectionOf(anchor);
  if (!owner || !under(datum, owner)) return null;
  return {
    anchor,
    element: datum,
    label: (
      /** @type {HTMLElement | SVGElement} */
      datum.dataset.lfDatumLabel?.trim() || aimLabel(datum)
    )
  };
}
var anchorForRange = (range) => anchorForPassage(segmentsIn(range), range.commonAncestorContainer);
function anchorForPassage(segments, node) {
  const holder = node.nodeType === Node.ELEMENT_NODE ? node : upFrom(node);
  const { text: quote, units } = readingFrom(segments);
  const dataNodes = new Set(
    segments.map((seg) => closestAcross(seg.node, DATUM)).filter(Boolean)
  );
  const [onlyDatum] = dataNodes;
  const datum = dataNodes.size === 1 && segments.every((seg) => closestAcross(seg.node, DATUM) === onlyDatum) ? onlyDatum : null;
  if (datum) return anchorForDatum(datum, quote ? { quote } : {});
  const section = closestAcross(holder, ADDRESSABLE)?.id ?? null;
  if (!quote) return { section };
  const reading = pageText();
  const [start, stop] = spanIn(reading, segments);
  for (let width = CONTEXT; ; width *= 2) {
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
      if (first.node === from.node && first.start === from.offset && last.node === to.node && last.end === to.offset)
        return anchor;
    }
    if ([...prefix].length < width && [...suffix].length < width)
      return { ...anchor, detached: true };
  }
}
var controlName = (control) => control.isContentEditable ? accessibleName(control) : ownName(control) || (control.matches(PRESSES) ? control.innerText?.trim().replace(/\s+/g, " ") || addressableWord(control) : "");
var controlIdentity = (control) => control.control ?? control;
var namedParts = (owner, name) => [...new Set(pageQueryAll(WORKS).map(controlIdentity))].filter(
  (control) => control !== owner && under(control, owner) && addressableAt(control) === owner && controlName(control) === name
);
function controlContext(control, contexts) {
  const block = blockAt(control);
  if (!block) return "";
  if (!contexts.has(block))
    contexts.set(
      block,
      quoteFrom(
        textNodesUnder(block).filter(({ node }) => !closestAcross(node, WORKS))
      )
    );
  return [contexts.get(block), elementReading(control)].filter(Boolean).join(" ");
}
function controlPassages(face, control) {
  const words2 = textNodesUnder(face);
  const barriers = face === control ? pageQueryAll(WORKS).filter((other) => other !== control && under(other, face)) : [control];
  const passages = [];
  let run = [];
  const finish = () => {
    if (run.length) passages.push(run);
    run = [];
  };
  for (const word of words2) {
    if (face === control ? closestAcross(word.node, WORKS) !== control : under(word.node, control)) {
      finish();
      continue;
    }
    if (run.length && barriers.some((barrier) => rangeOf([...run, word]).intersectsNode(barrier)))
      finish();
    run.push(word);
  }
  finish();
  return passages;
}
function visiblePassage(segments) {
  const clips = /* @__PURE__ */ new Map();
  return segments.every((segment) => {
    const holder = segment.node.parentElement;
    if (!holder.checkVisibility({ opacityProperty: true, visibilityProperty: true }))
      return false;
    return [...rangeOf([segment]).getClientRects()].some(
      (rect) => rect.width > 0 && rect.height > 0 && clippedContents(rect, holder, clips)
    );
  });
}
function designTargetAt(node, marginTargetAt, reading = { owners: /* @__PURE__ */ new Map(), contexts: /* @__PURE__ */ new Map() }) {
  const { owners, contexts } = reading;
  let at = node?.nodeType === 1 ? node : node?.parentElement;
  if (!at) return null;
  const pressed = designPressAt(at);
  const control = pressed?.matches(`${WORKS},${genericVisualSelector}`) && controlIdentity(pressed);
  const visual = visualAt(at, { unclaimed: false });
  const declared2 = declaredVisualSelector();
  if (declared2 && visual?.element.matches(declared2)) at = visual.element;
  else if (pressed?.control || visual && control?.matches(PRESSES) && under(visual.element, control))
    at = control;
  const surface = leafSurface(at);
  const margin = closestAcross(at, ".lf-margin-entry, [data-lf-margin-for]");
  const marginTarget = marginTargetAt?.(at);
  const standsFor = margin && (!surface || under(margin, surface)) && marginTarget;
  const authored = surface && closestAcross(at, '[id]:not([id^="lf-"])');
  const element = standsFor || (surface ? authored && under(authored, surface) && authored : addressableAt(at));
  if (!element) return null;
  const partElement = control && control !== element && (marginTarget === element || under(control, element)) ? control : null;
  const part = partElement && controlName(partElement);
  let target = owners.get(element);
  if (!target) {
    target = addressableAimTarget(element);
    owners.set(element, target);
  }
  if (!part)
    return control === element ? {
      ...target,
      controlElement: control,
      controlFaces: [control, ...control.labels ?? []]
    } : target;
  const faces = [partElement, ...partElement.labels ?? []];
  const detail = [
    .../* @__PURE__ */ new Set([
      controlContext(partElement, contexts),
      ...[...partElement.labels ?? []].map(
        (label) => quoteFrom(
          textNodesUnder(label).filter(({ node: node2 }) => !under(node2, partElement))
        )
      )
    ])
  ].filter((text) => text && text !== part).join(" \xB7 ");
  const named = {
    ...target,
    anchor: { ...target.anchor, part },
    label: `${part}${detail ? ` \xB7 ${detail}` : ""} \xB7 ${target.label}`,
    controlElement: partElement,
    controlFaces: faces
  };
  if (partElement.matches(genericVisualSelector) && !claimsVisualGesture(partElement))
    return named;
  return {
    ...named,
    capture() {
      const repeatedName = namedParts(element, part).length > 1;
      for (const face of faces) {
        for (const passage of controlPassages(face, partElement)) {
          if (!passage.length || !fileModelsPassage(passage)) continue;
          const captured = anchorForRange(rangeOf(passage));
          const resolved = captured.quote && resolveAnchor(captured);
          const attachment = resolved?.kind === "passage" && passageGeometry(resolved)?.attachment;
          if (resolved?.exact && attachment && resolved.segments.every(({ node: node2 }) => under(node2, face)) && overlaps(attachment, face.getBoundingClientRect()) && visiblePassage(resolved.segments)) {
            const context = contextAround(pageText(), resolved.segments, {
              before: [...captured.prefix ?? ""].length,
              after: [...captured.suffix ?? ""].length
            });
            const phrase = [
              part === captured.quote ? part : `${part} \xB7 \u201C${captured.quote}\u201D`,
              context.before && `after \u2026${context.before}`,
              context.after && `before ${context.after}\u2026`,
              target.label
            ].filter(Boolean).join(" \xB7 ");
            return {
              ...named,
              anchor: { ...target.anchor, ...captured, part },
              label: repeatedName ? phrase : named.label
            };
          }
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
  if (visual?.part)
    return {
      anchor: { section: visual.id, visual: visual.part.id },
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
    ...pageQueryAll(declaredVisualSelector()).flatMap(
      (visual) => visualParts(visual).map((part) => part.element)
    )
  ];
  const reading = { owners: /* @__PURE__ */ new Map(), contexts: /* @__PURE__ */ new Map() };
  const targets = candidates.map(
    (node) => options.design ? designTargetAt(node, options.marginTargetAt, reading) : aimTargetAt(node, options)
  ).filter(Boolean);
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
    const datums = currentDatums(
      source,
      anchor.datum,
      anchor.identity ?? null,
      anchor.source ?? null
    );
    const anchoredToData = typeof anchor.source === "string" && typeof anchor.source_revision === "string";
    const basis = datums[0] ?? source;
    const basisMatches = !anchoredToData || basis?.dataset.lfSource === anchor.source && (anchor.identity ? datums.length > 0 && basis.dataset.lfIdentity === anchor.identity : basis.dataset.lfSourceRevision === anchor.source_revision);
    if (!basisMatches) {
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
    if (!anchor.quote)
      return {
        ...resolvedElement({ element: datums[0] }),
        datumElement: datums[0],
        exact: true,
        status: "exact"
      };
    const segments2 = findQuote(pageText(), anchor.quote, anchor, datums[0]);
    return segments2.length ? {
      ...resolvedPassage({
        place: annotationAt(segments2[0].node, () => datums[0]),
        segments: segments2
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
    if (found)
      return resolvedElement({
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
    return anchor.part ? { ...target, exact: false, status: "fallback" } : target;
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
var fragmentTarget = (fragment) => fragment ? targetElement(resolveAnchor({ section: fragmentId(fragment) })) : null;

// runtime/bounds.js
var BOUND = "data-lf-bound";
var BOUNDED = `[${BOUND}]`;
var FOLLOWING = `[${BOUND}="end"]`;
var holds = /* @__PURE__ */ new WeakMap();
var registered = /* @__PURE__ */ new Set();
var byBox = /* @__PURE__ */ new WeakMap();
var THIS_DOCUMENT = `lf-region:bound:${performance.timeOrigin}`;
var unnamed = 0;
var declaresBound = (box) => getComputedStyle(box).getPropertyValue("--lf-bound-box").trim() === "1";
function scrollerOf(bounded) {
  for (const box of bounded.querySelectorAll("*"))
    if (declaresBound(box) && box.closest(BOUNDED) === bounded) return box;
  return bounded;
}
var regionId = (bounded) => bounded.id && authoredScope(bounded) === pageDocument() ? compoundReadingRegionId(bounded, "bound") : `${THIS_DOCUMENT}:${unnamed += 1}`;
var following = (hold) => hold.bounded.matches(FOLLOWING) && !hold.left && !(hold.pinned !== null && hold.box.scrollTop < hold.pinned - SCROLL_SLACK && !atScrollEnd(hold.box));
var heldBy = (box) => {
  const hold = byBox.get(box);
  return hold?.box === box && registered.has(hold) ? hold : null;
};
var followingItsEnd = (box) => {
  const hold = heldBy(box);
  return Boolean(hold && following(hold));
};
var boundedBlockOf = (box) => heldBy(box)?.bounded ?? null;
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
    stopRegion = registerReadingRegion({ id: hold.id, host: bounded, body: box });
    registered.add(hold);
  };
  const sync = (observed) => {
    hold.bound = bounded.getAttribute(BOUND);
    if (!bounded.isConnected || hold.bound === null) return letGo();
    if (skipped(bounded)) {
      if (!hold.box) adopt(bounded);
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
  new MutationObserver(hold.sync).observe(bounded, {
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

// runtime/element-frame.js
function elementAxes(source) {
  let matrix = new window.DOMMatrix();
  for (let node = source; node instanceof Element; node = renderedParent(node)) {
    const style = getComputedStyle(node);
    let local = new window.DOMMatrix();
    if (style.rotate !== "none") {
      const parts = style.rotate.split(" ");
      const angle = parts.pop();
      const degrees = parseFloat(angle) * (angle.endsWith("turn") ? 360 : angle.endsWith("grad") ? 0.9 : angle.endsWith("rad") ? 180 / Math.PI : 1);
      const axis = parts.length === 3 ? parts.map(Number) : parts[0] === "x" ? [1, 0, 0] : parts[0] === "y" ? [0, 1, 0] : [0, 0, 1];
      local = local.rotateAxisAngle(...axis, degrees);
    }
    if (style.scale !== "none") {
      const scale = style.scale.split(" ").map(Number);
      local = local.scale(scale[0], scale[1] ?? scale[0], scale[2] ?? 1);
    }
    if (style.transform !== "none")
      local = local.multiply(new window.DOMMatrix(style.transform));
    const zoom = Number(style.zoom);
    local = local.scale(zoom, zoom);
    matrix = local.multiply(matrix);
  }
  return { x: { x: matrix.a, y: matrix.b }, y: { x: matrix.c, y: matrix.d } };
}
var nativePositions = /* @__PURE__ */ new WeakMap();
var positionProbe;
function nativePosition(source, position, horizontal, vertical) {
  const key = JSON.stringify([position, horizontal, vertical]);
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
  const pixels = (value, space) => value.replace(
    /([-+]?(?:\d*\.)?\d+(?:e[-+]?\d+)?)%/gi,
    (_unit, percent) => `${Number(percent) * space / 100}px`
  );
  if (!positionProbe) {
    const measure2 = document.createElement("div");
    measure2.className = "lf-ui";
    measure2.dataset.lfRuntime = "";
    measure2.inert = true;
    measure2.style.cssText = "all:initial;position:fixed;visibility:hidden;contain:strict;width:0;height:0;left:0;top:0;pointer-events:none";
    const point2 = document.createElement("div");
    point2.style.cssText = "all:initial;position:absolute;width:0;height:0";
    measure2.append(point2);
    positionProbe = { measure: measure2, point: point2 };
  }
  const { measure, point } = positionProbe;
  point.style.left = pixels(components[0], horizontal);
  point.style.top = pixels(components[1], vertical);
  document.body.append(measure);
  const resolved = getComputedStyle(point);
  const offset = [Number.parseFloat(resolved.left), Number.parseFloat(resolved.top)];
  measure.remove();
  nativePositions.set(source, { key, offset });
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
    if (style.objectFit !== "fill") {
      const scale = style.objectFit === "cover" ? Math.max(sx, sy) : style.objectFit === "none" ? 1 : Math.min(sx, sy, style.objectFit === "scale-down" ? 1 : Infinity);
      sx = sy = scale;
    }
    const [dx, dy] = nativePosition(
      source,
      style.objectPosition,
      contentWidth - native[0] * sx,
      contentHeight - native[1] * sy
    );
    if (![sx, sy, dx, dy].every(Number.isFinite) || !sx || !sy) return null;
    return {
      box,
      width: native[0],
      height: native[1],
      matrix: matrix.translate(edge("Left") + dx, edge("Top") + dy).scale(sx, sy)
    };
  }
  return { box, width, height, matrix };
}
function elementBorderFrame(source) {
  const box = shownBox(source);
  if (!box?.width || !box?.height) return null;
  const style = getComputedStyle(source);
  if (style.display === "contents")
    return {
      box,
      width: box.width,
      height: box.height,
      matrix: new window.DOMMatrix().translate(box.left, box.top)
    };
  const borderSize = (side, edges, fallback) => {
    const size = Number.parseFloat(style[side]);
    if (!Number.isFinite(size)) return fallback;
    return style.boxSizing === "border-box" ? size : size + edges.reduce(
      (sum, edge) => sum + Number.parseFloat(style[`padding${edge}`]) + Number.parseFloat(style[`border${edge}Width`]),
      0
    );
  };
  const width = borderSize("width", ["Left", "Right"], source.offsetWidth);
  const height = borderSize("height", ["Top", "Bottom"], source.offsetHeight);
  const { x, y } = elementAxes(source);
  const left = box.left - Math.min(0, width * x.x, height * y.x, width * x.x + height * y.x);
  const top = box.top - Math.min(0, width * x.y, height * y.y, width * x.y + height * y.y);
  const matrix = new window.DOMMatrix([x.x, x.y, y.x, y.y, left, top]);
  return { box, width, height, matrix };
}
function scrollAxes(source) {
  return source === source.ownerDocument.scrollingElement ? { x: { x: 1, y: 0 }, y: { x: 0, y: 1 } } : elementAxes(source);
}
function localScrollBy(source, { x, y }) {
  const axes = scrollAxes(source);
  const horizontal = source.scrollWidth > source.clientWidth;
  const vertical = source.scrollHeight > source.clientHeight;
  const along = (axis) => {
    const amounts = [
      ...x && axis.x ? [x / axis.x] : [],
      ...y && axis.y ? [y / axis.y] : []
    ];
    return amounts.reduce(
      (move2, amount) => Math.abs(amount) > Math.abs(move2) ? amount : move2,
      0
    );
  };
  if (!horizontal) return { left: 0, top: vertical ? along(axes.y) : 0 };
  if (!vertical) return { left: along(axes.x), top: 0 };
  const determinant = axes.x.x * axes.y.y - axes.x.y * axes.y.x;
  return {
    left: (x * axes.y.y - y * axes.y.x) / determinant,
    top: (y * axes.x.x - x * axes.x.y) / determinant
  };
}

// runtime/css-anchors.js
var anchorNames = /* @__PURE__ */ new WeakMap();
var anchorOrdinal = 0;
var nextName = () => `--lf-a${++anchorOrdinal}`;
var partOf = (name) => name.slice(2);
var partNamed = (el) => el.part.contains(partOf(anchorNames.get(el)));
var partRules = null;
var declared = /* @__PURE__ */ new Set();
var given = /* @__PURE__ */ new WeakMap();
var watchedTrees = /* @__PURE__ */ new WeakSet();
var restoreParts = (el) => {
  for (const part of given.get(el) ?? [])
    if (!el.part.contains(part)) el.part.add(part);
};
function keepParts(root) {
  if (watchedTrees.has(root)) return;
  watchedTrees.add(root);
  new MutationObserver((records) => {
    for (const { target } of records) restoreParts(target);
  }).observe(root, { subtree: true, attributes: true, attributeFilter: ["part"] });
}
function namePart(el, name, pseudo = "") {
  if (!partRules) {
    partRules = new CSSStyleSheet();
    document.adoptedStyleSheets = [...document.adoptedStyleSheets, partRules];
  }
  if (!declared.has(name)) {
    const content = pseudo ? 'content: "";' : "";
    partRules.insertRule(
      `::part(${partOf(name)})${pseudo} { ${content} anchor-name: ${name}; }`,
      partRules.cssRules.length
    );
    declared.add(name);
  }
  given.set(el, /* @__PURE__ */ new Set([...given.get(el) ?? [], partOf(name)]));
  keepParts(el.getRootNode());
  restoreParts(el);
}
function anchorReading(el, name = anchorNames.get(el) ?? nextName()) {
  const start = contentStarts.get(el);
  if (start) return { el, name: start.name };
  anchorNames.set(el, name);
  if (el.getRootNode() !== document)
    return partNamed(el) ? { el, name } : { el, name, write: name, part: true };
  const written = el.style.anchorName;
  if (written.split(",").some((part) => part.trim() === name)) return { el, name };
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
var SCOPES = CSS.supports("anchor-scope", "all");
function outsideScopes(target) {
  let el = target;
  if (SCOPES) {
    for (let at = target; at instanceof Element; at = renderedParent(at))
      if (at.getRootNode() === document && !at.contains(chromeRoot) && getComputedStyle(at).anchorScope === "all")
        el = renderedParent(at) ?? at;
  }
  return el;
}
function anchorElement(target) {
  let el = outsideScopes(target);
  for (let host; !nameable(el) && (host = shadowHost(el.getRootNode())); ) el = host;
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
    if (at instanceof Element && (!/^(static|relative)$/.test(getComputedStyle(at).position) || at !== node && scrollsContent(at)))
      return false;
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
  for (let before = near.previousSibling, after = near.nextSibling; before || after; before = before?.previousSibling, after = after?.nextSibling)
    for (const node of [before, after]) if (carried(node)) return node;
  return contentStart(scroller);
}
function anchorFor(context) {
  const physical = context instanceof Element ? context : context?.parentElement;
  if (!physical) return null;
  const anchor = anchorElement(physical);
  if (context === physical || anchor !== physical || !scrollContainer(physical))
    return anchor;
  return carriedAnchor(physical, context) ?? anchor;
}
var contentStarts = /* @__PURE__ */ new WeakMap();
var starts = /* @__PURE__ */ new WeakMap();
var START = "data-lf-content-start";
function contentStart(scroller) {
  const first = scroller.firstChild;
  if (!first || [...scroller.childNodes].some(
    (node) => node.nodeType !== Node.TEXT_NODE && !(node instanceof Element && /^(br|wbr)$/.test(node.localName))
  ))
    return null;
  let handle = starts.get(scroller);
  if (!handle) {
    if (!CSS.supports(
      "anchor-name",
      "attr(data-lf-content-start type(<custom-ident>))"
    ) || !/^(block|inline-block|flow-root|list-item)$/.test(
      getComputedStyle(scroller).display
    ) || !/^(none|normal)$/.test(getComputedStyle(scroller, "::before").content) || getComputedStyle(scroller, "::first-letter").float !== "none")
      return null;
    handle = {
      // The first node that paints: white space collapsed away paints nothing, and
      // the start stands where what follows it does.
      getBoundingClientRect() {
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
      }
    };
    starts.set(scroller, handle);
    contentStarts.set(handle, { scroller, name: nextName() });
  }
  const { name } = contentStarts.get(handle);
  if (scroller.getRootNode() === document) keeps(scroller, START, name);
  else namePart(scroller, name, "::before");
  return handle;
}
var anchorHolder = (anchor) => contentStarts.get(anchor)?.scroller ?? anchor;
var anchorName = (el) => nameAnchor(anchorReading(el));
function anchorAt(node, anchor, box, at = anchor?.getBoundingClientRect(), visibility = "always") {
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
var cutPath = ({ x, y }) => {
  const open = (clips) => clips ? "0" : "-100000px";
  return `inset(${open(y)} ${open(x)})`;
};
function cutFrames(levels, frames, make) {
  const kept = frames.slice(Math.max(0, frames.length - levels.length));
  const chain = [...Array.from({ length: levels.length - kept.length }, make), ...kept];
  const was = frames[0];
  if (chain[0] && was && chain[0] !== was && was.parentNode)
    move(was.parentNode, chain[0], was);
  for (let i = 1; i < chain.length; i++)
    if (chain[i].parentNode !== chain[i - 1]) move(chain[i - 1], chain[i], null);
  for (const dropped of frames.slice(0, frames.length - kept.length)) dropped.remove();
  levels.forEach(({ anchor, band, axes, at }, i) => {
    anchorAt(chain[i], anchor, band, at);
    chain[i].style.clipPath = cutPath(axes);
  });
  return chain;
}
var views = /* @__PURE__ */ new Map();
var viewedNodes = /* @__PURE__ */ new WeakMap();
var viewObserver;
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
  if (!binding || binding.view || !node.isConnected || !binding.target.isConnected)
    return;
  anchorView(node, binding.target, binding.changed);
  binding.changed();
}
function anchorView(node, target, changed) {
  const binding = viewedNodes.get(node);
  let view = binding?.view;
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
        const view2 = views.get(entry.target);
        if (!view2) continue;
        const near = entry.isIntersecting && entry.target.checkVisibility();
        const changed2 = view2.near !== near;
        view2.near = near;
        for (const [node2, notify] of view2.nodes) {
          if (!node2.isConnected || !entry.target.isConnected) {
            releaseAnchorView(node2);
            continue;
          }
          if (changed2) notify();
        }
      }
    });
  }
  view = views.get(target);
  if (!view) {
    view = { target, near: nearWindow(target), nodes: /* @__PURE__ */ new Map() };
    views.set(target, view);
    viewObserver.observe(target);
  }
  view.nodes.set(node, changed);
  viewedNodes.set(node, { target, changed, view });
  if (!node.classList.contains("lf-anchor-view")) node.classList.add("lf-anchor-view");
  return view.near;
}

export {
  chromeRoot,
  chromeForeground,
  targetElement,
  targetSegments,
  targetPlace,
  exactTarget,
  targetRange,
  rangeGeometry,
  passageGeometry,
  targetSurface,
  targetParts,
  registerVisualParts,
  visualPartProblems,
  addressableWord,
  addressableSays,
  addressableName,
  addressableLabel,
  sectionLabel,
  anchoringIsReady,
  setAnchoringReady,
  sectionOf,
  projectedDatum,
  datumLabel,
  requireReference,
  referencedProjection,
  addressedElements,
  revealAddressed,
  visualParts,
  visualPartLabel,
  visualSelector,
  unclaimedVisualGesture,
  visualAt,
  designPressAt,
  ADDRESSABLE,
  isAddressable,
  annotationAt,
  lightSeat,
  datumAimTarget,
  anchorForRange,
  anchorForPassage,
  aimTargetAt,
  aimTargets,
  resolveAnchor,
  fragmentTarget,
  followingItsEnd,
  boundedBlockOf,
  holdArrivingBounds,
  elementFrame,
  elementBorderFrame,
  scrollAxes,
  localScrollBy,
  anchorReading,
  nameAnchor,
  anchorElement,
  anchorReaches,
  scrollsWith,
  carriedAnchor,
  anchorFor,
  anchorName,
  anchorAt,
  cutFrames,
  refreshAnchorView,
  anchorView
};
