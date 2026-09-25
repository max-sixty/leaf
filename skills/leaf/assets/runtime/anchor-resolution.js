/* Durable anchor interpretation.
 *
 * This module reads authored markup and resolves semantic coordinates into the current
 * document. It owns no controls, travel, paint, conversation state, or command path.
 * Selection capture and file-side capture produce the same quote/context coordinate;
 * `resolveAnchor` is the only search implementation, so repeated text detaches unless
 * its context identifies one occurrence.
 */

import { sameAnchor } from "./anchor-coordinate.js";
import { resolvedElement, resolvedPassage } from "./resolved-target.js";
import { inUi, under, upFrom } from "./shadow.js";
import {
  revealsVisualParts,
  revealVisualPart as revealRegisteredVisualPart,
  visualPart as registeredVisualPart,
  visualPartAt as registeredVisualPartAt,
  visualPartLabel as registeredVisualPartLabel,
  visualParts as registeredVisualParts,
} from "./visual-parts.js";
import {
  authoredScope,
  blockAt,
  closestAcross,
  DATUM,
  elementById,
  findQuote,
  inChrome,
  pageDocument,
  pageQueryAll,
  quoteFrom,
  settledAway,
  textNodesUnder,
} from "./passages.js";
import { registry, tagsDeclaring } from "./registry.js";
import { PRESSABLE, PRESSES } from "./widget-elements.js";

// Anchors are durable coordinates, so every route that can mint one begins only after
// replay has reconciled the authored document. The presentation root owns the writer.
let anchoringReady = false;
export const anchoringIsReady = () => anchoringReady;
export function setAnchoringReady(ready) {
  anchoringReady = ready;
}

// Which element an anchor names, asked in one place: the element a quoteless anchor
// resolves to and the subtree a quoted candidate must occupy.
export const sectionOf = (anchor) =>
  anchor?.section ? elementById(anchor.section) : null;

function currentDatums(source, key) {
  if (!source?.id) return [];
  return pageQueryAll(DATUM).filter(
    (datum) =>
      under(datum, source) &&
      datum.dataset.lfProjection === source.id &&
      datum.dataset.lfDatum === key,
  );
}

export const currentDatum = (source, key) => {
  const matches = currentDatums(source, key);
  return matches.length === 1 ? matches[0] : null;
};

export function suppliedDatum(source, key) {
  const supplied = source?.lfDataDatum?.(key);
  return supplied instanceof Element &&
    under(supplied, source) &&
    supplied.dataset.lfProjection === source.id
    ? supplied
    : null;
}

// The verbs that follow an `x-refers` attribute (`navigateToDatum`, `indicate`) are
// handed it by package code, so an undeclared one is that code's error, thrown at the
// call rather than read as a reference to nothing.
export function requireReference(verb, owner, attribute) {
  if (!(owner instanceof Element))
    throw new TypeError(`${verb} owner must be an element`);
  if (
    typeof attribute !== "string" ||
    !Object.hasOwn(registry[owner.localName]?.["x-refers"] ?? {}, attribute)
  )
    throw new TypeError(
      `${verb} ${owner.localName} attribute ${String(attribute)} is not declared by x-refers`,
    );
}

// The element an `x-refers` attribute names: in the owner's own authored document
// first, so a widget in a message finds its message's element before a page element
// with the same id, as the server's request check does, and then in the page beside
// it, which a message's widget may name.
export function referencedProjection(owner, attribute) {
  const id = owner.getAttribute(attribute);
  if (!id) return null;
  const scope = authoredScope(owner);
  const page = pageDocument();
  return elementById(id, scope) ?? (scope === page ? null : elementById(id, page));
}

// The elements under a referenced widget that a key addresses, in the one key space
// every `x-refers` verb reads. A widget whose parts have a private address (a code
// block's line ranges) answers through `lfElementsFor(key)`; otherwise the key is a
// registered visual part's id or a projected datum's key. Only elements under the
// source count, so a hook cannot point a caller elsewhere in the page.
export function addressedElements(source, key) {
  if (typeof source.lfElementsFor === "function")
    return [...(source.lfElementsFor(key) ?? [])].filter(
      (element) => element instanceof Element && under(element, source),
    );
  const part = visualPart(source, key)?.element;
  if (part) return [part];
  const datum = currentDatum(source, key) ?? suppliedDatum(source, key);
  return datum ? [datum] : [];
}

// A generated visual part keeps a semantic id the provider declaration bounds: a token
// authored in its `parts` attribute, or any longer id one of its `prefixes` begins.
// Element ids never escape into the event log; the declaration bounds the inventory
// core will trust. The rank is an id's place in that declaration, which orders the
// visual's targets: its authored token's index, 0 for every prefixed id so they keep
// registration order, and -1 for an id it does not admit. Null when the visual
// declares no parts at all.
const visualPartRank = (visual) => {
  const declaration = registry[visual?.localName]?.["x-visual"];
  if (!declaration || typeof declaration !== "object") return null;
  if (declaration.prefixes)
    return (id) =>
      declaration.prefixes.some((prefix) => id !== prefix && id.startsWith(prefix))
        ? 0
        : -1;
  const tokens =
    visual.getAttribute(declaration.parts)?.trim().split(/\s+/).filter(Boolean) ?? [];
  return (id) => tokens.indexOf(id);
};

const wholeVisualSurface = (element) =>
  registry[element?.localName]?.["x-visual"] ? element : null;

/** The registered parts a visual's declaration admits, in declaration order. */
export function visualParts(visual) {
  const rank = visualPartRank(visual);
  if (!rank) return [];
  return registeredVisualParts(visual)
    .filter((part) => rank(part.id) >= 0)
    .sort((a, b) => rank(a.id) - rank(b.id));
}

const admitsVisualPart = (visual, part) => visualPartRank(visual)?.(part) >= 0;

export function visualPart(visual, part) {
  return admitsVisualPart(visual, part) ? registeredVisualPart(visual, part) : null;
}

export function revealVisualPart(visual, part) {
  return admitsVisualPart(visual, part)
    ? revealRegisteredVisualPart(visual, part)
    : null;
}

export function visualPartAt(visual, target) {
  const rank = visualPartRank(visual);
  return rank
    ? registeredVisualPartAt(visual, target, (part) => rank(part.id) >= 0)
    : null;
}

export const visualPartLabel = (visual, part) =>
  admitsVisualPart(visual, part) ? registeredVisualPartLabel(visual, part) : null;

const declaredVisualSelector = () =>
  [...tagsDeclaring((entry) => entry["x-visual"])].join(",");

const genericVisualSelector = "svg, img, figure";
export const visualSelector = () =>
  [declaredVisualSelector(), genericVisualSelector].filter(Boolean).join(",");

const outermostAcross = (element, selector) => {
  for (let parent = upFrom(element); parent;) {
    const outer = closestAcross(parent, selector);
    if (!outer) break;
    element = outer;
    parent = upFrom(element);
  }
  return element;
};

// A picture inside a press is that control's rendering, so the control keeps the
// gesture and no visual reading is offered for it. A region that holds content — a tab
// panel, a scroll region, a stage that takes keys, a grid — leaves its pictures
// pictures (widget-elements.js, PRESSES).
const claimsVisualGesture = (element) => element.matches(`${PRESSES},${PRESSABLE}`);

export const unclaimedVisualGesture = (target) => {
  if (inChrome(target) || inUi(target)) return false;
  for (let element = target; element; element = upFrom(element))
    if (claimsVisualGesture(element)) return false;
  return true;
};

// A declared provider owns every hit inside it. Outside one, the outermost ordinary
// picture is the visual reading. The nearest authored id remains the durable seat.
export function visualAt(target, { unclaimed = true } = {}) {
  if (unclaimed && !unclaimedVisualGesture(target)) return null;
  const declared = declaredVisualSelector();
  let element = declared ? closestAcross(target, declared) : null;
  if (element) element = outermostAcross(element, declared);
  else {
    element = closestAcross(target, genericVisualSelector);
    if (element) element = outermostAcross(element, genericVisualSelector);
  }
  if (!element) return null;
  const seat = closestAcross(element, '[id]:not(.lf-ui):not([id^="lf-"])');
  return seat ? { element, id: seat.id, part: visualPartAt(element, target) } : null;
}

export const ADDRESSABLE = '[id]:not(.lf-ui):not([id^="lf-"])';

// Generated visual descendants are not authored addressables even when their renderer minted
// ids. Only the registered visual-part route may turn them into durable coordinates.
export function isAddressable(at) {
  if (!at.matches(ADDRESSABLE) || inChrome(at) || inUi(at) || settledAway(at))
    return false;
  const visual = tagsDeclaring((entry) => entry["x-visual"]).join(",");
  return !(visual && at.parentElement && closestAcross(at.parentElement, visual));
}

export function addressableAt(node) {
  let at = node?.nodeType === 1 ? node : node?.parentElement;
  for (; at; at = upFrom(at)) if (isAddressable(at)) return at;
  return null;
}

export const annotationAt = (node) => blockAt(node) ?? addressableAt(node);

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
  h6: "heading",
};

export function addressableWord(addressable) {
  if (!addressable) return "";
  const tag = addressable.tagName.toLowerCase();
  if (registry[tag]?.["x-word"] === "module") {
    const own = addressable.lfWord?.();
    if (own) return own;
  }
  if (tag.startsWith("lf-")) return tag.slice(3);
  if (tag === "pre")
    return addressable.querySelector(":scope > code") ? "code" : "block";
  return HTML_WORDS[tag] ?? tag;
}

// The label is rooted at the addressable and reads its authored words. Generated annotation
// chrome is excluded by the same passage reader used for anchor resolution. Display
// surfaces constrain these complete words to their available space.
export function addressableSays(addressable, omitted = null) {
  if (!addressable) return "";
  const subtracts = Boolean(omitted && addressable.contains(omitted));
  const own =
    !subtracts && registry[addressable.localName]?.["x-word"] === "module"
      ? addressable.lfSays?.()
      : "";
  return (
    own ||
    quoteFrom(
      textNodesUnder(addressable).filter(
        (segment) => !subtracts || !omitted.contains(segment.node),
      ),
    )
  );
}

// What names an element, where the authoring contract gives it a name
// (`../../references/page-authoring.md`): the attribute its registry entry declares
// with `x-name`, else a leading disclosure summary, heading, or titled member's
// <strong>, looked for inside a leading <header> too. Leading means no words come
// before it; elements may, as a titled member's comparison chips stand in the band
// above its title and an eyebrow above a header's heading. The words are read the way
// `addressableSays` reads them, and generated chrome is skipped, so it never names
// anything. An element the contract gives no name answers "", and a caller that
// needs words for it takes `addressableSays`.
const TITLES = "summary, h1, h2, h3, h4, h5, h6, strong";
function leadingTitle(container) {
  for (const node of container.childNodes) {
    if (node.nodeType === Node.TEXT_NODE && node.data.trim()) return "";
    if (node.nodeType !== Node.ELEMENT_NODE || inUi(node)) continue;
    if (node.matches(TITLES)) return quoteFrom(textNodesUnder(node));
    if (node.localName === "header") return leadingTitle(node);
  }
  return "";
}
export function addressableName(element) {
  if (!element) return "";
  const attribute = registry[element.localName]?.["x-name"];
  const declared = attribute && element.getAttribute(attribute)?.trim();
  return declared || leadingTitle(element);
}

const aimLabel = (
  addressable,
  says = addressableSays(addressable) ||
    addressable?.getAttribute("aria-label") ||
    addressable?.querySelector("[aria-label]")?.getAttribute("aria-label"),
) => [addressableWord(addressable), says].filter(Boolean).join(": ");

const addressableAimTarget = (addressable) => ({
  anchor: { section: addressable.id },
  element: addressable,
  label: aimLabel(addressable),
  surface: wholeVisualSurface(addressable),
});

// The one coordinate minted from a projected datum. Pointer aim, passage capture, and
// widget-local comment affordances all pass through this function so source provenance
// cannot disappear merely because the gesture began in generated UI rather than text.
export const anchorForDatum = (datum, fields = {}) => {
  const sourceRevision = datum.dataset.lfSourceRevision;
  const recordContract = datum.dataset.lfRecordContract;
  const recordKeyField = datum.dataset.lfRecordKeyField;
  return {
    section: datum.dataset.lfProjection,
    datum: datum.dataset.lfDatum,
    ...fields,
    ...(datum.dataset.lfSource && sourceRevision
      ? { source: datum.dataset.lfSource, source_revision: sourceRevision }
      : {}),
    ...(recordContract && recordKeyField
      ? { record_contract: recordContract, record_key_field: recordKeyField }
      : {}),
  };
};

export function datumAimTarget(datum) {
  if (!(datum instanceof Element) || !datum.matches(DATUM)) return null;
  const anchor = anchorForDatum(datum);
  const owner = sectionOf(anchor);
  if (!owner || !under(datum, owner)) return null;
  return {
    anchor,
    element: datum,
    label: datum.dataset.lfDatumLabel?.trim() || aimLabel(datum),
  };
}

// Pointer aim and target-chooser hints share this reading. The returned element is the
// element the coordinate resolves to, so the promise and eventual mark agree.
export function aimTargetAt(node) {
  const visual = visualAt(node, { unclaimed: false });
  if (visual?.part)
    return {
      anchor: { section: visual.id, visual: visual.part.id },
      element: visual.part.element,
      label: aimLabel(sectionOf({ section: visual.id }), visual.part.label),
      surface: visual.part.surface,
    };
  const datum = closestAcross(node, DATUM);
  if (datum) return datumAimTarget(datum);
  const addressable = addressableAt(node);
  return addressable ? addressableAimTarget(addressable) : null;
}

export function aimTargets() {
  const candidates = [
    ...pageQueryAll(ADDRESSABLE).filter(isAddressable),
    ...pageQueryAll(DATUM),
    ...pageQueryAll(declaredVisualSelector()).flatMap((visual) =>
      visualParts(visual).map((part) => part.element),
    ),
  ];
  const targets = candidates.map(aimTargetAt).filter(Boolean);
  return targets.filter(
    (target, index) =>
      !targets.slice(0, index).some(({ anchor }) => sameAnchor(anchor, target.anchor)),
  );
}

export function resolveAnchor(anchor, text = "") {
  if (anchor.datum) {
    const source = sectionOf(anchor);
    const datums = currentDatums(source, anchor.datum);
    if (datums.length > 1) return null;
    const anchoredToData =
      typeof anchor.source === "string" && typeof anchor.source_revision === "string";
    const basis = datums[0] ?? source;
    const sameRecord =
      Boolean(anchor.record_contract && anchor.record_key_field) &&
      datums.length === 1 &&
      anchor.record_contract === basis.dataset.lfRecordContract &&
      anchor.record_key_field === basis.dataset.lfRecordKeyField;
    const basisMatches =
      !anchoredToData ||
      (basis?.dataset.lfSource === anchor.source &&
        (basis.dataset.lfSourceRevision === anchor.source_revision || sameRecord));
    if (!basisMatches) {
      const contextual = source?.lfDataDatum?.(anchor.datum, { outdated: true });
      const fallback =
        contextual instanceof Element && under(contextual, source)
          ? contextual
          : source;
      if (!(fallback instanceof Element)) return null;
      return {
        ...resolvedElement({ element: fallback }),
        datumElement: null,
        exact: false,
        status: "outdated",
      };
    }
    // A projection/key pair identifies exactly one current fact. Disappearance detaches
    // and duplicates refuse to guess. Changed text falls back to the same datum element.
    if (!datums.length) {
      const virtual = source?.lfDataDatum?.(anchor.datum);
      if (!(virtual instanceof Element) || !under(virtual, source)) return null;
      return {
        ...resolvedElement({ element: virtual }),
        datumElement: null,
        exact: false,
        status: "fallback",
      };
    }
    if (!anchor.quote)
      return {
        ...resolvedElement({ element: datums[0] }),
        datumElement: datums[0],
        exact: true,
        status: "exact",
      };
    const segments = findQuote(text, anchor.quote, anchor, datums[0]);
    return segments.length
      ? {
          ...resolvedPassage({
            place: blockAt(segments[0].node) ?? datums[0],
            segments,
          }),
          datumElement: datums[0],
          exact: true,
          status: "exact",
        }
      : {
          ...resolvedElement({ element: datums[0] }),
          datumElement: datums[0],
          exact: true,
          status: "exact",
        };
  }

  if (anchor.visual) {
    const section = sectionOf(anchor);
    // A missing declaration or provider detaches instead of silently widening a visual
    // part coordinate to the containing widget.
    if (!section || settledAway(section)) return null;
    const found = visualPart(section, anchor.visual);
    if (found)
      return resolvedElement({
        element: found.element,
        place: section,
        surface: found.surface,
      });
    // A declared part the visual draws only in another state stands in for the whole
    // visual, as a lazy datum does, until travel reveals it.
    return admitsVisualPart(section, anchor.visual) && revealsVisualParts(section)
      ? {
          ...resolvedElement({
            element: section,
            surface: wholeVisualSurface(section),
          }),
          exact: false,
          status: "fallback",
        }
      : null;
  }

  if (!anchor.quote) {
    const section = sectionOf(anchor);
    return section && !settledAway(section)
      ? resolvedElement({ element: section, surface: wholeVisualSurface(section) })
      : null;
  }

  const segments = findQuote(text, anchor.quote, anchor, sectionOf(anchor));
  return segments.length
    ? resolvedPassage({
        // Attached chrome belongs beside the passage's readable block or authored item.
        place: blockAt(segments[0].node) ?? addressableAt(segments[0].node),
        segments,
      })
    : null;
}

// One fragment reading serves message hrefs and location.hash. Malformed escapes retain
// their literal characters rather than making a durable reference unreadable.
export function fragmentId(fragment) {
  const raw = fragment.slice(1);
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}
