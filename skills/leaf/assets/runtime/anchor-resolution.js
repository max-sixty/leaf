/* Durable anchor interpretation.
 *
 * This module reads authored markup and resolves semantic coordinates into the current
 * document. It owns no controls, travel, paint, thread state, or command path.
 * Selection capture and file-side capture produce the same quote/context coordinate;
 * `resolveAnchor` is the only search implementation, so repeated text detaches unless
 * its context identifies one occurrence.
 */

import { anchorKey } from "./anchor-coordinate.js";
import {
  resolvedElement,
  resolvedPassage,
  targetElement,
  passageGeometry,
} from "./resolved-target.js";
import { CONTEXT } from "./passage-facts.js";
import { overlaps } from "./rect.js";
import { clippedContents } from "./geometry.js";
import { inUi, shadowHost, under, upFrom } from "./shadow.js";
import {
  registeredVisualPart,
  registeredVisualPartLabel,
  revealRegisteredVisualPart,
  revealsVisualParts,
  usableVisualPartAt,
  usableVisualParts,
  registeredVisualParts,
  visualPartAdmission,
} from "./visual-parts.js";
import {
  authoredScope,
  blockAt,
  closestAcross,
  cut,
  contextAround,
  neighbourhood,
  pageText,
  readingFrom,
  rangeOf,
  segmentsIn,
  textNodesUnder,
  quoteFrom,
  spanIn,
  DATUM,
  elementById,
  elementReading,
  findQuote,
  fileModelsPassage,
  inChrome,
  leafSurface,
  pageDocument,
  pageQueryAll,
  settledAway,
} from "./passages.js";
import { registry, tagsDeclaring } from "./registry.js";
import { PRESSABLE } from "./widget-elements.js";
import { PRESSES, WORKS } from "./control-selectors.js";
import {
  accessibleName,
  addressableLabel,
  addressableWord,
  ownName,
} from "./addressable-names.js";
import { fragmentId } from "./initial-render.js";

// Every route that mints an anchor starts after the shown document's widgets and
// selectable words have settled. Private history can still be loading: the gesture
// names the revision and coordinate the user actually saw. The entry owns the writer.
let anchoringReady = false;
export const anchoringIsReady = () => anchoringReady;
export function setAnchoringReady(ready) {
  anchoringReady = ready;
}

// Which element an anchor names, asked in one place: the element a quoteless anchor
// resolves to and the subtree a quoted candidate must occupy.
export const sectionOf = (anchor) =>
  anchor?.section ? elementById(anchor.section) : null;

function currentDatums(source, key, identity = null, dataSource = null) {
  if (!source?.id) return [];
  return pageQueryAll(DATUM).filter(
    (datum) =>
      under(datum, source) &&
      datum.dataset.lfProjection === source.id &&
      (dataSource === null || datum.dataset.lfSource === dataSource) &&
      (identity === null
        ? datum.dataset.lfDatum === key
        : datum.dataset.lfIdentity === identity),
  );
}

export const projectedDatum = (source, key) => {
  const matches = currentDatums(source, key);
  return matches.length === 1 ? matches[0] : null;
};

// What an anchor's datum is called: the label its projection gave the element drawn
// for it, found as resolution finds it, or for a datum its lazy widget has not drawn,
// what that widget calls it (`lfDatumLabel`), so a thread on a line of a closed file
// is named as its row would be.
export function datumLabel(anchor) {
  if (!anchor?.datum) return "";
  const source = sectionOf(anchor);
  const datums = currentDatums(
    source,
    anchor.datum,
    anchor.identity ?? null,
    anchor.source ?? null,
  );
  const label = datums.length
    ? datums.length === 1 && datums[0].dataset.lfDatumLabel
    : source?.lfDatumLabel?.(anchor.datum);
  return typeof label === "string" ? label.trim() : "";
}

function suppliedDatum(source, key) {
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
  if (
    typeof attribute !== "string" ||
    !Object.hasOwn(registry[owner.localName]?.["x-refers"] ?? {}, attribute)
  )
    throw new TypeError(
      `${verb} ${owner.localName} attribute ${String(attribute)} is not declared by x-refers`,
    );
}

// The element an `x-refers` attribute names. A keyed contract names the member whose
// key holds the value inside the owner's nearest enclosing scope, the scope the
// member's x-unique declares for that key. Any other names an id: in the owner's own
// authored document first, so a widget in a message finds its message's element before
// a page element with the same id, as the server's request check does, and then in the
// page beside it, which a message's widget may name.
export function referencedProjection(owner, attribute) {
  const id = owner.getAttribute(attribute);
  if (!id) return null;
  const { tag, key } = registry[owner.localName]["x-refers"][attribute];
  if (tag) {
    const within = registry[tag]["x-unique"][key];
    const scopeOf = (element) => element.parentElement?.closest(within) ?? null;
    const scope = scopeOf(owner);
    return (
      [...(scope?.querySelectorAll(tag) ?? [])].find(
        (member) => scopeOf(member) === scope && member.getAttribute(key) === id,
      ) ?? null
    );
  }
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
  const datum = projectedDatum(source, key) ?? suppliedDatum(source, key);
  return datum ? [datum] : [];
}

// Travel's half of that key space: ask the widget to draw what a key addresses before
// anything reads it. A visual part drawn only in another state is drawn now, as
// `registerVisualParts` promises; a lazy datum answers with its hydration promise. Every
// travel to a part of a widget asks this, a thread's anchor (`anchor.visual` or
// `anchor.datum`) and a module's `navigateToDatum` key alike, so neither route reaches a
// part the other cannot.
export function revealAddressed(source, key) {
  if (revealVisualPart(source, key)) return null;
  return source.lfRevealDatum?.(key) ?? null;
}

// A generated visual part keeps a semantic id its provider's declaration admits
// (`visualPartAdmission`). Element ids never escape into the event log; the
// declaration bounds the inventory core will trust. No rank when the visual declares
// no parts at all.
const visualPartRank = (visual) =>
  visual
    ? visualPartAdmission(visual, registry[visual.localName]?.["x-visual"])?.rank
    : null;

const wholeVisualSurface = (element) =>
  registry[element?.localName]?.["x-visual"] ? element : null;

/** The registered parts a visual's declaration admits, in declaration order. */
export function visualParts(visual, { strict = false } = {}) {
  const rank = visualPartRank(visual);
  if (!rank) return [];
  return (strict ? registeredVisualParts(visual) : usableVisualParts(visual))
    .filter((part) => rank(part.id) >= 0)
    .sort((a, b) => rank(a.id) - rank(b.id));
}

const admitsVisualPart = (visual, part) => visualPartRank(visual)?.(part) >= 0;

function visualPart(visual, part) {
  return admitsVisualPart(visual, part) ? registeredVisualPart(visual, part) : null;
}

function revealVisualPart(visual, part) {
  return admitsVisualPart(visual, part)
    ? revealRegisteredVisualPart(visual, part)
    : null;
}

function visualPartAt(visual, target) {
  const rank = visualPartRank(visual);
  return rank ? usableVisualPartAt(visual, target, (part) => rank(part.id) >= 0) : null;
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
  const seat = closestAcross(element, ADDRESSABLE);
  return seat ? { element, id: seat.id, part: visualPartAt(element, target) } : null;
}

// One candidate reading serves Design interception, direct aim and the picker.
// A press keeps its picture; content-holding regions leave pictures independent.
// The visual reader already gives generated drawings back to their declared provider.
const designCandidates = () =>
  [...tagsDeclaring(() => true), WORKS, "[data-lf-offer]", genericVisualSelector].join(
    ",",
  );
export function designPressAt(target) {
  const at = target?.nodeType === 1 ? target : target?.parentElement;
  const hit = at && closestAcross(at, designCandidates());
  if (!hit || !hit.matches(genericVisualSelector)) return hit;
  return (
    closestAcross(hit, `${PRESSES},${PRESSABLE}`) ||
    visualAt(at, { unclaimed: false })?.element ||
    hit
  );
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

function addressableAt(node) {
  let at = node?.nodeType === 1 ? node : node?.parentElement;
  for (; at; at = upFrom(at)) if (isAddressable(at)) return at;
  return null;
}

// The seat of a node: the element its margin row, response bar, note and reaction
// receipt stand at. Markdown block structure is reading geometry, not authored
// annotation identity. A whole-body formatter replaces one authored data record with
// paragraphs/lists; its declared host remains the seat that comments and reactions can
// name durably. A resolved passage's `place` is its first segment's seat; a passage in
// a datum falls back to the datum, where other text falls back to the nearest
// addressable element.
export function annotationAt(node, fallback = addressableAt) {
  const formatted = tagsDeclaring(
    (entry) => entry["x-text-format"] === "markdown",
  ).join(",");
  return (
    (formatted && closestAcross(node, formatted)) || blockAt(node) || fallback(node)
  );
}

// A seat inside a shadow root stands at its host, where light-DOM chrome can sit.
export const lightSeat = (seat) => (seat && shadowHost(seat.getRootNode())) ?? seat;

const aimLabel = (addressable, says = addressableLabel(addressable)) =>
  [addressableWord(addressable), says].filter(Boolean).join(": ");

const addressableAimTarget = (addressable) => ({
  anchor: { section: addressable.id },
  element: addressable,
  label: aimLabel(addressable),
  surface: wholeVisualSurface(addressable),
});

// The one coordinate minted from a projected datum. Pointer aim, passage capture, and
// widget-local comment affordances all pass through this function so source provenance
// cannot disappear merely because the gesture began in generated UI rather than text.
const anchorForDatum = (datum, fields = {}) => {
  const sourceRevision = datum.dataset.lfSourceRevision;
  return {
    section: datum.dataset.lfProjection,
    datum: datum.dataset.lfDatum,
    ...fields,
    ...(datum.dataset.lfSource && sourceRevision
      ? { source: datum.dataset.lfSource, source_revision: sourceRevision }
      : {}),
    ...(datum.dataset.lfIdentity ? { identity: datum.dataset.lfIdentity } : {}),
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

// Capture enough context to identify the selected span, stopping at the reading’s
// semantic fences. A short unique quote keeps the file capture’s initial context;
// repeated words grow their context until the shared resolver finds this exact span
// or the real boundary is exhausted. An unresolved passage remains unresolved.
// `anchorForPassage` captures segments already taken from the page reading, under
// `node`, without walking the reading again to find them.
export const anchorForRange = (range) =>
  anchorForPassage(segmentsIn(range), range.commonAncestorContainer);
export function anchorForPassage(segments, node) {
  const holder = node.nodeType === Node.ELEMENT_NODE ? node : upFrom(node);
  // The neighbours come from the same indexed reading the search uses and stop at
  // the same opaque-widget fences as the file-side capture. The browser knows words
  // a module generated and may quote them; it does not pretend the file can confirm
  // context across their seam.
  const { text: quote, units } = readingFrom(segments);
  const dataNodes = new Set(
    segments.map((seg) => closestAcross(seg.node, DATUM)).filter(Boolean),
  );
  const [onlyDatum] = dataNodes;
  const datum =
    dataNodes.size === 1 &&
    segments.every((seg) => closestAcross(seg.node, DATUM) === onlyDatum)
      ? onlyDatum
      : null;
  // Identity is the context for projected data. Neighbouring display values may reorder
  // or repeat, so storing their words as prefix/suffix would make incidental layout a
  // second, conflicting answer to which datum the user selected.
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
      ...(prefix && { prefix }),
      ...(suffix && { suffix }),
    };
    const resolved = quote && resolveAnchor(anchor);
    if (resolved?.exact && resolved.kind === "passage") {
      // Quotes discard boundary whitespace. Compare the characters the passage
      // reader retained, rather than demanding the drag's cosmetic spaces survive.
      const first = resolved.segments[0];
      const last = resolved.segments.at(-1);
      const from = units[0].start;
      const to = units.at(-1).end;
      if (
        first.node === from.node &&
        first.start === from.offset &&
        last.node === to.node &&
        last.end === to.offset
      )
        return anchor;
    }
    if ([...prefix].length < width && [...suffix].length < width)
      return { ...anchor, detached: true };
  }
}

// Design names the authored interface, including an agent-authored widget in a Leaf
// surface or the item a margin entry represents. Content aim names semantic data and
// visual parts instead. Both direct presses and the picker use this one target reading;
// choosing a route must never change a control's part coordinate.
// Press faces may name themselves by visible words; content-holding regions use
// their declared names. A native editor never derives identity from its mutable value.
const controlName = (control) =>
  control.isContentEditable
    ? accessibleName(control)
    : ownName(control) ||
      (control.matches(PRESSES)
        ? control.innerText?.trim().replace(/\s+/g, " ") || addressableWord(control)
        : "");
// A native label is a route into its control, not a second control identity.
const controlIdentity = (control) => control.control ?? control;
const namedParts = (owner, name) =>
  [...new Set(pageQueryAll(WORKS).map(controlIdentity))].filter(
    (control) =>
      control !== owner &&
      under(control, owner) &&
      addressableAt(control) === owner &&
      controlName(control) === name,
  );
// Spoken context includes prose and this control's visible face, never a neighbour's
// label. The shared block prose is read once per inventory; chosen capture stays lazy.
function controlContext(control, contexts) {
  const block = blockAt(control);
  if (!block) return "";
  if (!contexts.has(block))
    contexts.set(
      block,
      quoteFrom(
        textNodesUnder(block).filter(({ node }) => !closestAcross(node, WORKS)),
      ),
    );
  return [contexts.get(block), elementReading(control)].filter(Boolean).join(" ");
}
// Keep inline emphasis in one label passage, but never cross the nested field's
// words or native box to pretend its options are part of the visible label.
function controlPassages(face, control) {
  const words = textNodesUnder(face);
  const barriers =
    face === control
      ? pageQueryAll(WORKS).filter((other) => other !== control && under(other, face))
      : [control];
  const passages = [];
  let run = [];
  const finish = () => {
    if (run.length) passages.push(run);
    run = [];
  };
  for (const word of words) {
    if (
      face === control
        ? closestAcross(word.node, WORKS) !== control
        : under(word.node, control)
    ) {
      finish();
      continue;
    }
    if (
      run.length &&
      barriers.some((barrier) => rangeOf([...run, word]).intersectsNode(barrier))
    )
      finish();
    run.push(word);
  }
  finish();
  return passages;
}

function visiblePassage(segments) {
  const clips = new Map();
  return segments.every((segment) => {
    const holder = segment.node.parentElement;
    if (!holder.checkVisibility({ opacityProperty: true, visibilityProperty: true }))
      return false;
    return [...rangeOf([segment]).getClientRects()].some(
      (rect) =>
        rect.width > 0 && rect.height > 0 && clippedContents(rect, holder, clips),
    );
  });
}

function designTargetAt(
  node,
  marginTargetAt,
  reading = { owners: new Map(), contexts: new Map() },
) {
  const { owners, contexts } = reading;
  let at = node?.nodeType === 1 ? node : node?.parentElement;
  if (!at) return null;
  const pressed = designPressAt(at);
  const control =
    pressed?.matches(`${WORKS},${genericVisualSelector}`) && controlIdentity(pressed);
  const visual = visualAt(at, { unclaimed: false });
  const declared = declaredVisualSelector();
  if (declared && visual?.element.matches(declared)) at = visual.element;
  else if (
    pressed?.control ||
    (visual && control?.matches(PRESSES) && under(visual.element, control))
  )
    at = control;
  const surface = leafSurface(at);
  const margin = closestAcross(at, ".lf-margin-entry, [data-lf-margin-for]");
  const marginTarget = marginTargetAt?.(at);
  const standsFor = margin && (!surface || under(margin, surface)) && marginTarget;
  const authored = surface && closestAcross(at, '[id]:not([id^="lf-"])');
  const element =
    standsFor ||
    (surface ? authored && under(authored, surface) && authored : addressableAt(at));
  if (!element) return null;
  const partElement =
    control &&
    control !== element &&
    (marginTarget === element || under(control, element))
      ? control
      : null;
  const part = partElement && controlName(partElement);
  let target = owners.get(element);
  if (!target) {
    target = addressableAimTarget(element);
    owners.set(element, target);
  }
  if (!part)
    return control === element
      ? {
          ...target,
          controlElement: control,
          controlFaces: [control, ...(control.labels ?? [])],
        }
      : target;
  const faces = [partElement, ...(partElement.labels ?? [])];
  const detail = [
    ...new Set([
      controlContext(partElement, contexts),
      ...[...(partElement.labels ?? [])].map((label) =>
        quoteFrom(
          textNodesUnder(label).filter(({ node }) => !under(node, partElement)),
        ),
      ),
    ]),
  ]
    .filter((text) => text && text !== part)
    .join(" · ");
  const named = {
    ...target,
    anchor: { ...target.anchor, part },
    label: `${part}${detail ? ` · ${detail}` : ""} · ${target.label}`,
    controlElement: partElement,
    controlFaces: faces,
  };
  // A picture's name describes a face; it is not a quotation of its pixels.
  if (partElement.matches(genericVisualSelector) && !claimsVisualGesture(partElement))
    return named;
  // Inventory reads names and faces only. Capture the chosen control's passage once,
  // when direct aim or a picker choice actually needs its durable coordinate.
  return {
    ...named,
    capture() {
      const repeatedName = namedParts(element, part).length > 1;
      // Native associated labels are physical faces of the same control. Try the
      // visible words on each face without inventing quote text from an ARIA name.
      for (const face of faces) {
        for (const passage of controlPassages(face, partElement)) {
          if (!passage.length || !fileModelsPassage(passage)) continue;
          const captured = anchorForRange(rangeOf(passage));
          const resolved = captured.quote && resolveAnchor(captured);
          const attachment =
            resolved?.kind === "passage" && passageGeometry(resolved)?.attachment;
          // Hidden option words and repeated passages cannot establish an exact face.
          if (
            resolved?.exact &&
            attachment &&
            resolved.segments.every(({ node }) => under(node, face)) &&
            overlaps(attachment, face.getBoundingClientRect()) &&
            visiblePassage(resolved.segments)
          ) {
            // A repeated control’s announcement and its durable anchor share the same
            // distinguishing context, including neighbouring table cells.
            const context = contextAround(pageText(), resolved.segments, {
              before: [...(captured.prefix ?? "")].length,
              after: [...(captured.suffix ?? "")].length,
            });
            const phrase = [
              part === captured.quote ? part : `${part} · “${captured.quote}”`,
              context.before && `after …${context.before}`,
              context.after && `before ${context.after}…`,
              target.label,
            ]
              .filter(Boolean)
              .join(" · ");
            return {
              ...named,
              anchor: { ...target.anchor, ...captured, part },
              label: repeatedName ? phrase : named.label,
            };
          }
        }
      }
      return named;
    },
  };
}

// The returned element is the coordinate's durable owner. A named control part also
// supplies its own hint seat, so several controls in one owner keep separate identities.
export function aimTargetAt(node, { design = false, marginTargetAt } = {}) {
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
      surface: visual.part.surface,
    };
  const datum = closestAcross(node, DATUM);
  if (datum) return datumAimTarget(datum);
  const addressable = addressableAt(node);
  return addressable ? addressableAimTarget(addressable) : null;
}

export function aimTargets(options = {}) {
  const candidates = [
    ...pageQueryAll(ADDRESSABLE).filter(isAddressable),
    ...pageQueryAll(DATUM),
    ...(options.design ? pageQueryAll(designCandidates()) : []),
    ...pageQueryAll(declaredVisualSelector()).flatMap((visual) =>
      visualParts(visual).map((part) => part.element),
    ),
  ];
  const reading = { owners: new Map(), contexts: new Map() };
  const targets = candidates
    .map((node) =>
      options.design
        ? designTargetAt(node, options.marginTargetAt, reading)
        : aimTargetAt(node, options),
    )
    .filter(Boolean);
  if (options.design) {
    const seen = new Set();
    return targets.filter((target) => {
      const identity = target.controlElement ?? target.element;
      if (seen.has(identity)) return false;
      seen.add(identity);
      return true;
    });
  }
  const keys = new Set();
  return targets.filter((target) => {
    const key = anchorKey(target.anchor);
    if (keys.has(key)) return false;
    keys.add(key);
    return true;
  });
}

export function resolveAnchor(anchor) {
  // Capture exhausted the selected occurrence's real fences without identifying it.
  // Later uniqueness cannot prove that the survivor was the user's occurrence.
  if (anchor.detached) return null;
  if (anchor.datum) {
    const source = sectionOf(anchor);
    const datums = currentDatums(
      source,
      anchor.datum,
      anchor.identity ?? null,
      anchor.source ?? null,
    );
    // The emitter's subject identity follows replacements. Other projected keys can
    // name a location within one value (such as a diff line), so those remain pinned
    // to the value the user saw.
    const anchoredToData =
      typeof anchor.source === "string" && typeof anchor.source_revision === "string";
    const basis = datums[0] ?? source;
    const basisMatches =
      !anchoredToData ||
      (basis?.dataset.lfSource === anchor.source &&
        (anchor.identity
          ? datums.length > 0 && basis.dataset.lfIdentity === anchor.identity
          : basis.dataset.lfSourceRevision === anchor.source_revision));
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
    if (datums.length > 1) return null;
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
    const segments = findQuote(pageText(), anchor.quote, anchor, datums[0]);
    return segments.length
      ? {
          ...resolvedPassage({
            place: annotationAt(segments[0].node, () => datums[0]),
            segments,
          }),
          datumElement: datums[0],
          exact: true,
          status: "exact",
        }
      : {
          ...resolvedElement({ element: datums[0] }),
          datumElement: datums[0],
          exact: false,
          status: "fallback",
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
    if (!section || settledAway(section)) return null;
    const target = resolvedElement({
      element: section,
      surface: wholeVisualSurface(section),
    });
    // A named part describes a control, region or picture, not a durable id. Without
    // captured words, only its owner is known. A later revision leaving one control
    // never promotes an earlier ambiguous gesture into an exact one.
    return anchor.part ? { ...target, exact: false, status: "fallback" } : target;
  }

  const segments = findQuote(pageText(), anchor.quote, anchor, sectionOf(anchor));
  if (!segments.length) return null;
  // An exact named-control quote identifies its actual readable face, so both the
  // editor and sent thread clear that face. Ordinary prose still clears its block.
  const face = anchor.part && closestAcross(segments[0].node, WORKS);
  const controlFace =
    face && segments.every(({ node }) => closestAcross(node, WORKS) === face);
  return resolvedPassage({
    place: controlFace ? face : annotationAt(segments[0].node),
    segments,
  });
}

// The page element a fragment names: the anchor `{section}` it spells, resolved as every
// other anchor is, so an id in chrome, in a message's own markup, or on content a
// revision settled away names nothing here. A fresh load's arrival, a followed link, and
// a reply's reference all read their destination through this.
export const fragmentTarget = (fragment) =>
  fragment ? targetElement(resolveAnchor({ section: fragmentId(fragment) })) : null;
