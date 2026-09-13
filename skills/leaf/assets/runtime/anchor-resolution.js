/* Durable anchor interpretation.
 *
 * This module reads authored markup and resolves semantic coordinates into the current
 * document. It owns no controls, travel, paint, conversation state, or command path.
 * Selection capture and file-side capture produce the same quote/context coordinate;
 * `resolveAnchor` is the only search implementation, so repeated text detaches unless
 * its context identifies one occurrence.
 */

import { sameAnchor } from "./anchor-coordinate.js";
import { runtimeOwnsScrollerStop } from "./reach.js";
import { resolvedElement, resolvedPassage } from "./resolved-target.js";
import { inUi } from "./shadow.js";
import {
  visualPart as registeredVisualPart,
  visualPartAt as registeredVisualPartAt,
} from "./visual-parts.js";
import {
  blockAt,
  closestAcross,
  containsAcross,
  cut,
  DATUM,
  elementById,
  findQuote,
  inChrome,
  pageQueryAll,
  quoteFrom,
  settledAway,
  textNodesUnder,
} from "./passages.js";
import { registry, tagsDeclaring } from "./registry.js";
import { WORKS_WITHOUT_TAB_STOP } from "./widget-elements.js";

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
      containsAcross(source, datum) &&
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
    containsAcross(source, supplied) &&
    supplied.dataset.lfProjection === source.id
    ? supplied
    : null;
}

export const projectionReferenceDeclared = (owner, attribute) =>
  owner instanceof Element &&
  typeof attribute === "string" &&
  Object.hasOwn(registry[owner.localName]?.["x-refers"] ?? {}, attribute);

// The declaration is interpretation; deciding that a bad command argument is an error
// belongs to anchor-travel.
export function referencedProjection(owner, attribute) {
  if (!projectionReferenceDeclared(owner, attribute)) return null;
  const id = owner.getAttribute(attribute);
  return id ? elementById(id) : null;
}

// A generated visual part keeps an authored semantic token. Generated ids never escape
// into the event log; the provider declaration bounds the inventory core will trust.
const visualPartAttribute = (visual) => {
  const declaration = registry[visual?.localName]?.["x-visual"];
  return declaration && typeof declaration === "object" ? declaration.parts : null;
};

const wholeVisualSurface = (element) =>
  registry[element?.localName]?.["x-visual"] ? element : null;

export const declaredVisualParts = (visual) => {
  const attribute = visualPartAttribute(visual);
  const value = attribute ? visual?.getAttribute(attribute) : "";
  return new Set(value?.trim().split(/\s+/).filter(Boolean) ?? []);
};

export function visualPart(visual, part) {
  if (!declaredVisualParts(visual).has(part)) return null;
  return registeredVisualPart(visual, part);
}

export function visualPartAt(visual, target) {
  const declared = declaredVisualParts(visual);
  return registeredVisualPartAt(visual, target, (part) => declared.has(part.id));
}

export const visualPartLabel = (visual, part) =>
  visualPart(visual, part)?.label ?? null;

const declaredVisualSelector = () =>
  [...tagsDeclaring((entry) => entry["x-visual"])].join(",");

const genericVisualSelector = "svg, img, figure";
export const visualSelector = () =>
  [declaredVisualSelector(), genericVisualSelector].filter(Boolean).join(",");

const interactiveWithoutTabStopSelector = () =>
  `${WORKS_WITHOUT_TAB_STOP},[data-lf-offer]`;

export const parentAcross = (element) =>
  element?.parentElement ?? element?.getRootNode()?.host ?? null;

const outermostAcross = (element, selector) => {
  for (let parent = parentAcross(element); parent;) {
    const outer = closestAcross(parent, selector);
    if (!outer) break;
    element = outer;
    parent = parentAcross(element);
  }
  return element;
};

const claimsVisualGesture = (element) =>
  element.matches(interactiveWithoutTabStopSelector()) ||
  (element.hasAttribute("tabindex") &&
    element.tabIndex >= 0 &&
    !runtimeOwnsScrollerStop(element));

export const unclaimedVisualGesture = (target) => {
  if (inChrome(target) || inUi(target)) return false;
  for (let element = target; element; element = parentAcross(element))
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
  for (; at; at = parentAcross(at)) if (isAddressable(at)) return at;
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

const ADDRESSABLE_SAYS_CAP = 52;
// The label is rooted at the addressable and reads its authored words. Generated annotation
// chrome is excluded by the same passage reader used for anchor resolution.
export function addressableSays(addressable, omitted = null) {
  if (!addressable) return "";
  const subtracts = Boolean(omitted && addressable.contains(omitted));
  const own =
    !subtracts && registry[addressable.localName]?.["x-word"] === "module"
      ? addressable.lfSays?.()
      : "";
  const whole =
    own ||
    quoteFrom(
      textNodesUnder(addressable).filter(
        (segment) => !subtracts || !omitted.contains(segment.node),
      ),
    );
  if ([...whole].length <= ADDRESSABLE_SAYS_CAP) return whole;
  const short = cut(whole, 0, ADDRESSABLE_SAYS_CAP);
  const at = short.lastIndexOf(" ");
  return (at > ADDRESSABLE_SAYS_CAP / 2 ? short.slice(0, at) : short).trimEnd() + "…";
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
  const dataRevision = Number(datum.dataset.lfSourceRevision);
  return {
    section: datum.dataset.lfProjection,
    datum: datum.dataset.lfDatum,
    ...fields,
    ...(datum.dataset.lfSource && Number.isInteger(dataRevision)
      ? { source: datum.dataset.lfSource, data_revision: dataRevision }
      : {}),
  };
};

export function datumAimTarget(datum) {
  if (!(datum instanceof Element) || !datum.matches(DATUM)) return null;
  const anchor = anchorForDatum(datum);
  const owner = sectionOf(anchor);
  if (!owner || !containsAcross(owner, datum)) return null;
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
      [...declaredVisualParts(visual)].flatMap((token) => {
        const part = visualPart(visual, token);
        return part ? [part.element] : [];
      }),
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
    const anchoredToData =
      typeof anchor.source === "string" && Number.isInteger(anchor.data_revision);
    const basis = datums[0] ?? source;
    const basisMatches =
      !anchoredToData ||
      (basis?.dataset.lfSource === anchor.source &&
        Number(basis.dataset.lfSourceRevision) === anchor.data_revision);
    if (!basisMatches) {
      const contextual = source?.lfDataDatum?.(anchor.datum, { outdated: true });
      const fallback =
        contextual instanceof Element && containsAcross(source, contextual)
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
    if (datums.length > 1) return null;
    if (!datums.length) {
      const virtual = source?.lfDataDatum?.(anchor.datum);
      if (!(virtual instanceof Element) || !containsAcross(source, virtual))
        return null;
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
    if (!section || !visualPartAttribute(section) || settledAway(section)) return null;
    const found = visualPart(section, anchor.visual);
    return found
      ? resolvedElement({
          element: found.element,
          place: section,
          surface: found.surface,
        })
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
