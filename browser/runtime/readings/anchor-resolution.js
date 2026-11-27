/* Durable anchor interpretation.
 *
 * This module reads authored markup and resolves semantic coordinates into the current
 * document. It owns no controls, travel, paint, thread state, or command path.
 * `resolveAnchor` is the only reader of a stored quote's words: selection capture
 * stores a quote with the context that tells its occurrence apart, and an agent's
 * capture stores the context of the one copy the page's files hold, or none where they
 * hold the words zero or several times (`anchor_capture.py`). Words it can't
 * place once, repeated text whose context identifies no one occurrence included, stand
 * on their section as a fallback, or nowhere without one.
 */

import { excerptWords, labelWords, lastWords } from "../lib/words.js";
import { anchorKey, fragmentId, fragmentKey } from "../base/anchor-coordinate.js";
import { documentChanged } from "../state/semantic-state.js";
import {
  resolvedElement,
  resolvedPassage,
  targetElement,
  passageGeometry,
} from "./resolved-target.js";
import { overlaps } from "../dom/rect.js";
import { clippedContents } from "../dom/geometry.js";
import { declaredRoot, queryAllUnder } from "../dom/shadow.js";
import { shadowHost, under, upFrom, closestAcross } from "../lib/shadow-tree.js";
import { inUi, inChrome } from "../base/ui-marks.js";
import {
  registeredVisualPart,
  registeredVisualPartLabel,
  revealRegisteredVisualPart,
  drawsAbsentParts,
  registeredVisualPartAt,
  registeredVisualParts,
  focusedVisualPart,
  visualPartFocus,
  visualPartAdmission,
  declaredVisuals,
  layoutsChanged,
} from "../state/visual-parts.js";
import {
  blockAt,
  AROUND,
  contextAround,
  pageText,
  passageContext,
  readingPart,
  readingFrom,
  runReading,
  readingHolding,
  rangeOf,
  segmentsIn,
  textNodesUnder,
  quoteFrom,
  DATUM,
  elementById,
  excerpt,
  findQuote,
  quoteCopies,
  holdsEditedValue,
  leafSurface,
  pageDocument,
  pageQueryAll,
  settledAway,
} from "./passages.js";
import { registry, tagsDeclaring } from "../state/registry.js";
import { authoredElement } from "./references.js";
import { PAGE_PAINT_ATTRIBUTE } from "../base/page-paint.js";
import { PRESSABLE } from "../dom/widget-elements.js";
import { PRESSES, WORKS } from "../dom/control-selectors.js";
import {
  accessibleName,
  addressableLabel,
  LABEL_WORDS,
  ownName,
} from "./addressable-names.js";
import { addressableWord } from "../lib/element-word.js";

/** @typedef {import("../../types/domain.js").Anchor} Anchor */

/** @typedef {{element: Element, anchor: Anchor, label: string, surface?: Element | null,
 * controlElement?: Element, controlFaces?: Element[], capture?: () => AimTarget}} AimTarget
 * @typedef {{design?: boolean, marginTargetAt?: (element: Element) => Element | null}} AimOptions */

// Every route that mints an anchor starts after the shown document's widgets and
// selectable words have settled. Private history can still be loading: the gesture
// names the revision and coordinate the user actually saw. The entry owns the writer.
let anchoringReady = false;
export const anchoringIsReady = () => anchoringReady;
/** @param {boolean} ready */
export function setAnchoringReady(ready) {
  anchoringReady = ready;
}

// Which element an anchor names, asked in one place: the element a quoteless anchor
// resolves to and the subtree a quoted candidate must occupy.
/** @param {{section?: string | null} | null | undefined} anchor */
export const sectionOf = (anchor) =>
  anchor?.section ? elementById(anchor.section) : null;

// The data a widget drew for `key`. What says which they are, their source and
// identity among it, is not what the page's reading hears, so a reader follows the
// document changing (`documentChanged`), and so does whatever it reads of them after.
/** @param {Element | null} source @param {string} key @param {string | null} [identity] @param {string | null} [dataSource] */
function currentDatums(source, key, identity = null, dataSource = null) {
  documentChanged();
  if (!source?.id) return [];
  return pageQueryAll(DATUM).filter(
    (datum) =>
      under(datum, source) &&
      datum.getAttribute("data-lf-projection") === source.id &&
      (dataSource === null || datum.getAttribute("data-lf-source") === dataSource) &&
      (identity === null
        ? datum.getAttribute("data-lf-datum") === key
        : datum.getAttribute("data-lf-identity") === identity),
  );
}

/** @param {Element | null} source @param {string} key */
const projectedDatum = (source, key) => {
  const matches = currentDatums(source, key);
  return matches.length === 1 ? (matches[0] ?? null) : null;
};

// What an anchor's datum is called: the label its projection gave the element drawn
// for it, found as resolution finds it, or for a datum its lazy widget has not drawn,
// what that widget calls it (`lfDatumLabel`), so a thread on a line of a closed file
// is named as its row would be. A passage across data is named by its first datum and
// its last. It reads the page's nodes (`currentDatums`), so a paint that draws it
// follows the document changing, as a projection relabelling it does.
/** @param {Anchor | null | undefined} anchor */
export function datumLabel(anchor) {
  if (!anchor?.datum) return "";
  const source = sectionOf(anchor);
  /** @param {string} key @param {string | null} identity */
  const labelOf = (key, identity) => {
    const datums = currentDatums(source, key, identity, anchor.source ?? null);
    const [datum] = datums;
    const label = datum
      ? datums.length === 1 && datum.getAttribute("data-lf-datum-label")
      : source?.lfDatumLabel?.(key);
    return typeof label === "string" ? label.trim() : "";
  };
  const last = labelOf(anchor.datum, anchor.identity ?? null);
  const first = anchor.from ? labelOf(anchor.from, null) : "";
  return first && last ? `${first} – ${last}` : last;
}

/** @param {Element} source @param {string} key */
function suppliedDatum(source, key) {
  const supplied = source.lfDataDatum?.(key);
  return supplied instanceof Element &&
    under(supplied, source) &&
    supplied.getAttribute("data-lf-projection") === source.id
    ? supplied
    : null;
}

// The elements under a referenced widget that a key addresses, in the one key space
// every `refers` verb reads. A widget whose parts have a private address (a code
// block's line ranges) answers through `lfElementsFor(key)`; otherwise the key is a
// visual part's id or a projected datum's key. Only elements under the
// source count, so a hook cannot point a caller elsewhere in the page.
/** @param {Element} source @param {string} key */
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

// Where focus goes for what a key addresses under a widget: a visual part's destination
// (`visualPartFocus`), which a chart settles on its point only as focus is placed, else
// the first element the key addresses. Naming it changes nothing.
/** @param {Element} source @param {string} key */
export const addressedFocus = (source, key) =>
  (admitsVisualPart(source, key) ? visualPartFocus(source, key) : null) ??
  addressedElements(source, key)[0] ??
  null;

// Travel's half of that key space: ask the widget to draw what a key addresses before
// anything reads it. A visual part drawn only in another state is drawn now, as
// a visual's `lfParts.reveal` promises; a lazy datum answers with its hydration promise. Every
// travel to a part of a widget asks this, for a thread's anchor (`revealAnchor`) and a
// module's `navigateToDatum` key alike, so neither route reaches a part the other
// cannot.
/** @param {Element} source @param {string} key */
export function revealAddressed(source, key) {
  if (revealVisualPart(source, key)) return null;
  return source.lfRevealDatum?.(key) ?? null;
}

// The same for each part of a widget an anchor names: its visual part, or each datum,
// the one a passage across data starts in (`from`) as well as `datum`.
/** @param {Element} source @param {Anchor} anchor */
export function revealAnchor(source, anchor) {
  const asked = [anchor.visual, anchor.from, anchor.datum].flatMap((key) =>
    key ? [revealAddressed(source, key)] : [],
  );
  return asked.some((hydration) => hydration?.then) ? Promise.all(asked) : null;
}

// Whether a thread stands on what its widget gives in place of a part it hasn't drawn,
// such as a closed diff file's row for a line in it, or for a line of earlier data
// (`resolveAnchor`'s `fallback` and `outdated` with no drawn datum).
/** @param {Anchor | null | undefined} anchor @param {import("./resolved-target.js").ResolvedTarget | null | undefined} placement */
export const standsIn = (anchor, placement) =>
  Boolean(
    (anchor?.datum || anchor?.visual) &&
    placement &&
    placement.status !== "exact" &&
    !placement.datumElement,
  );

// Whether the page shows a quote's words more than once where its anchor looks for
// them, so where no context picks a copy, the words are on the page but no passage of
// them is the thread's (`resolveAnchor`).
/** @param {Anchor | null | undefined} anchor */
export function quoteRepeats(anchor) {
  if (!anchor?.quote || anchor.datum || anchor.visual) return false;
  const section = sectionOf(anchor);
  if (anchor.section && !section) return false;
  return quoteCopies(pageText(), anchor.quote, section) > 1;
}

// Whether the part a thread stands in for is yet to be drawn, so drawing it moves the
// thread there, or gives it a seat beside it. A thread on earlier data stays on the
// place its widget gives it.
/** @param {Anchor | null | undefined} anchor @param {import("./resolved-target.js").ResolvedTarget | null | undefined} placement */
export const awaitsDrawing = (anchor, placement) =>
  standsIn(anchor, placement) && placement?.status === "fallback";

// Which elements are visuals of their own, for the reader of a visual's marks.
declaredVisuals((element) => Boolean(registry[element.localName]?.visual));

// A generated visual part keeps an id its provider's declaration admits.
/** @param {Element | null} visual */
const visualAdmission = (visual) =>
  visual ? visualPartAdmission(registry[visual.localName]?.visual ?? null) : null;

/** @param {Element | null} element */
const wholeVisualSurface = (element) =>
  element && registry[element.localName]?.visual ? element : null;

/** The admitted parts in their registered inventory order. */
/** @param {Element} visual */
export function visualParts(visual) {
  const admits = visualAdmission(visual);
  if (!admits) return [];
  return registeredVisualParts(visual).filter((part) => admits(part.id));
}

/** @param {Element} visual @param {string} part */
const admitsVisualPart = (visual, part) => visualAdmission(visual)?.(part) ?? false;

/** @param {Element} visual @param {string} part */
function visualPart(visual, part) {
  return admitsVisualPart(visual, part) ? registeredVisualPart(visual, part) : null;
}

/** @param {Element} visual @param {string} part */
function revealVisualPart(visual, part) {
  return admitsVisualPart(visual, part)
    ? revealRegisteredVisualPart(visual, part)
    : null;
}

/** @param {Element} visual @param {Node | null} target */
function visualPartAt(visual, target) {
  const admits = visualAdmission(visual);
  return admits
    ? registeredVisualPartAt(
        visual,
        target instanceof Element ? target : (target?.parentElement ?? null),
        (part) => admits(part.id),
      )
    : null;
}

/** @param {Element | null} visual @param {string} part */
export const visualPartLabel = (visual, part) =>
  visual && admitsVisualPart(visual, part)
    ? registeredVisualPartLabel(visual, part)
    : null;

const declaredVisualTags = () => tagsDeclaring((entry) => entry.visual);
const declaredVisualSelector = () => declaredVisualTags().join(",");

const GENERIC_VISUALS = ["svg", "img", "figure"];
const genericVisualSelector = GENERIC_VISUALS.join(", ");
// The tags a picture's element has: a widget that declares `visual`, or a plain
// one.
export const visualTags = () => [...declaredVisualTags(), ...GENERIC_VISUALS];

/** @param {Element} element @param {string} selector */
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
// pictures (dom/widget-elements.js, PRESSES). What makes a press, such as a role, is not
// what the page's reading hears, so it follows the document changing
// (`documentChanged`) and a widget's layout (state/visual-parts.js, `layoutsChanged`).
/** @param {Element} element */
const claimsVisualGesture = (element) => {
  documentChanged();
  layoutsChanged();
  return element.matches(`${PRESSES},${PRESSABLE}`);
};

/** @param {Node | null} target */
export const unclaimedVisualGesture = (target) => {
  if (inChrome(target) || inUi(target)) return false;
  for (
    let element = target instanceof Element ? target : target?.parentElement;
    element;
    element = upFrom(element)
  )
    if (claimsVisualGesture(element)) return false;
  return true;
};

// A declared provider owns every hit inside it. Outside one, the outermost ordinary
// picture is the visual reading. The nearest authored id remains the durable seat.
/** @param {Node | null} target @param {{unclaimed?: boolean}} [options] */
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
  return seat
    ? { element, seat, id: seat.id, part: visualPartAt(element, target) }
    : null;
}

// One candidate reading serves Design interception, direct aim and the picker.
// A press keeps its picture; content-holding regions leave pictures independent.
// The visual reader already gives generated drawings back to their declared provider.
const designCandidates = () =>
  [...tagsDeclaring(() => true), WORKS, "[data-lf-offer]", genericVisualSelector].join(
    ",",
  );
/** @param {Node | null} target */
export function designPressAt(target) {
  const at = target instanceof Element ? target : target?.parentElement;
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
/** @param {Element} at */
export function isAddressable(at) {
  if (!at.matches(ADDRESSABLE) || inChrome(at) || inUi(at) || settledAway(at))
    return false;
  const visual = declaredVisualSelector();
  return !(visual && at.parentElement && closestAcross(at.parentElement, visual));
}

/** @param {Node | null} node @returns {Element | null} */
function addressableAt(node) {
  let at = node instanceof Element ? node : node?.parentElement;
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
/** @param {Node} node @param {(node: Node) => Element | null} [fallback] */
export function annotationAt(node, fallback = addressableAt) {
  const formatted = tagsDeclaring((entry) => entry.content === "markdown").join(",");
  return (
    (formatted && closestAcross(node, formatted)) || blockAt(node) || fallback(node)
  );
}

// A seat inside a shadow root stands at its host, where light-DOM chrome can sit.
/** @param {Element | null} seat */
export const lightSeat = (seat) => (seat && shadowHost(seat.getRootNode())) ?? seat;

/** @param {Element} addressable @param {string} [says] */
const aimLabel = (addressable, says = addressableLabel(addressable)) =>
  [addressableWord(addressable), says].filter(Boolean).join(": ");

/** @param {Element} addressable @returns {AimTarget} */
const addressableAimTarget = (addressable) => ({
  anchor: { section: addressable.id },
  element: addressable,
  label: aimLabel(addressable),
  surface: wholeVisualSurface(addressable),
});

// The one coordinate minted from a projected datum. Pointer aim, passage capture, and
// widget-local comment affordances all pass through this function so source provenance
// cannot disappear merely because the gesture began in generated UI rather than text.
/** @param {Element} datum @param {{quote?: string, from?: string}} [fields] @returns {Anchor | null} */
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
    ...(source && sourceRevision ? { source, source_revision: sourceRevision } : {}),
    ...(identity ? { identity } : {}),
  };
};

// Whether a widget drew two datums from one value: the same projection, source and
// revision, which both ends of a passage across its data share.
const DRAWN = ["data-lf-projection", "data-lf-source", "data-lf-source-revision"];
/** @param {Element} a @param {Element} b */
const drawnTogether = (a, b) =>
  DRAWN.every((name) => a.getAttribute(name) === b.getAttribute(name));

/** @param {Node | null} datum @returns {AimTarget | null} */
export function datumAimTarget(datum) {
  if (!(datum instanceof Element) || !datum.matches(DATUM)) return null;
  const anchor = anchorForDatum(datum);
  if (!anchor) return null;
  const owner = sectionOf(anchor);
  if (!owner || !under(datum, owner)) return null;
  return {
    anchor,
    element: datum,
    label: datum.getAttribute("data-lf-datum-label")?.trim() || aimLabel(datum),
  };
}

// Capture enough context to identify the selected span, stopping at the reading’s
// semantic fences. A short unique quote keeps the initial context (`$passages.context`);
// repeated words grow their context until the shared resolver finds this exact span
// or the real boundary is exhausted. An unresolved passage remains unresolved.
// `anchorForPassage` captures segments already taken from the page reading, under
// `node`, without walking the reading again to find them.
/** @typedef {Anchor} CapturedAnchor */
/** @param {Range} range */
export const anchorForRange = (range) =>
  anchorForPassage(segmentsIn(range), range.commonAncestorContainer);
// The passage is the selection's words: a drag from a paragraph's end into a
// document's first line holds the newline between them, which is neither's word.
/** @param {import("./passages.js").Segment} segment */
const says = ({ node: text, start, end }) => /\S/.test(text.data.slice(start, end));
// Whether a capture of the range quotes words, answered without reading the context
// a capture reads around them.
/** @param {Range} range */
export const rangeHoldsWords = (range) => segmentsIn(range).some(says);
/** @param {import("./passages.js").Segment[]} selected @param {Node} node @returns {CapturedAnchor | null} */
export function anchorForPassage(selected, node) {
  const from = selected.findIndex(says);
  const to = selected.findLastIndex(says);
  const segments = from < 0 ? [] : selected.slice(from, to + 1);
  // The words, not the range, say which element holds the passage: a triple-click in
  // Chromium, or a drag past an item's last word, ends the range at the next item's
  // start, whose common ancestor is the list. Named by the list, a passage a revision
  // rewrites falls back to the whole list rather than the item that still stands.
  const firstText = segments[0]?.node;
  const lastText = segments.at(-1)?.node;
  let holder = firstText
    ? upFrom(firstText)
    : node.nodeType === Node.ELEMENT_NODE
      ? node
      : upFrom(node);
  while (holder && lastText && !under(lastText, holder)) holder = upFrom(holder);
  // The neighbours come from the same indexed reading the search uses and stop at its
  // fences, so a selection's context holds none of the words a module draws beside it,
  // which the module may rewrite or rearrange.
  const { text: quote, units } = readingFrom(segments);
  /** @param {import("./passages.js").Segment | undefined} seg */
  const datumOf = (seg) => (seg ? closestAcross(seg.node, DATUM) : null);
  const first = datumOf(segments[0]);
  const last = datumOf(segments.at(-1));
  const datum =
    first && first === last && segments.every((seg) => datumOf(seg) === first)
      ? first
      : null;
  // Words that start in one datum and end in a later one its widget drew from the same
  // value, as a drag across two lines of a diff holds, name both: `datum` the last, which
  // the thread stands beside as it would for a comment on that datum alone, and `from`
  // the first.
  const projected = datum
    ? anchorForDatum(datum)
    : first && last && first !== last && drawnTogether(first, last)
      ? anchorForDatum(last, { from: first.getAttribute("data-lf-datum") ?? "" })
      : null;
  if (projected && !quote) return projected;
  const section = closestAcross(holder, ADDRESSABLE)?.id ?? null;
  if (!quote) return section === null ? null : { section };
  // Other words on both sides of a part's edge stand in no one reading, and no copy of
  // them is found again, since every part is a passage cell of its own (passages.js,
  // `pageText`).
  if (!projected && segments.some((seg) => readingPart(seg.node)))
    return { section, quote, detached: true };
  // Identity is the context for projected data: the display values beside a datum may
  // reorder or repeat, so their words would make incidental layout a second,
  // conflicting answer to which datum the user selected. Its own words still tell
  // repeats within it apart, as the lines around each copy tell apart a line a text
  // document holds twice, so a datum's context is read from its words alone, and a
  // run's from the words of the data it runs across (`runReading`): the reading
  // `resolveAnchor` searches.
  const reading = datum
    ? pageText(datum)
    : projected && first && last
      ? runReading(first, last)
      : pageText();
  const base = projected || { section };
  const context = passageContext(reading, segments, units, (context) => {
    const resolved = resolveAnchor({ ...base, quote, ...context });
    return resolved?.exact && resolved.kind === "passage" ? resolved.segments : [];
  });
  return { ...base, quote, ...context };
}

// Design names the authored interface, including an agent-authored widget in a Leaf
// surface or the item a margin entry represents. Content aim names semantic data and
// visual parts instead. Both direct presses and the picker use this one target reading;
// choosing a route must never change a control's part coordinate.
// Press faces may name themselves by visible words; content-holding regions use
// their declared names. A native editor never derives identity from its mutable value.
/** @param {Element} control */
const controlName = (control) =>
  control instanceof HTMLElement && control.isContentEditable
    ? accessibleName(control)
    : ownName(control) ||
      (control.matches(PRESSES)
        ? labelWords(control instanceof HTMLElement ? control.innerText : "") ||
          addressableWord(control)
        : "");
/** @param {Element & Partial<Pick<HTMLInputElement, "labels">>} control */
const controlFaces = (control) => [control, ...(control.labels ?? [])];
// A native label is a route into its control, not a second control identity.
/** @param {Element} control */
const controlIdentity = (control) =>
  (control instanceof HTMLLabelElement ? control.control : null) ?? control;
// The owner's parts named `name`: the controls whose nearest addressable is `owner`.
// The walk comes down the trees `upFrom` climbs back out of, `owner`'s own and the
// declared roots in it, and steps over each addressable it meets with all that one
// holds, whose controls are that addressable's own parts. So naming a part costs what
// its owner holds as its own, not what its members hold: a side tab's owner, the tabs
// widget, holds every tab's document, which a query of the owner read in full on each
// press on a tab and each picker hint that announced one (#4781).
/** @param {Element} owner @param {string} name */
function namedParts(owner, name) {
  /** @type {Set<Element>} */
  const controls = new Set();
  /** @param {Element} element */
  const visit = (element) => {
    const root = declaredRoot(element);
    for (const scope of root ? [element, root] : [element])
      for (let child = scope.firstElementChild; child; child = child.nextElementSibling)
        if (!isAddressable(child)) {
          if (child.matches(WORKS)) controls.add(controlIdentity(child));
          visit(child);
        }
  };
  visit(owner);
  return [...controls].filter(
    (control) =>
      control !== owner &&
      under(control, owner) &&
      addressableAt(control) === owner &&
      controlName(control) === name,
  );
}
// What a press in Design mode can take as a part: a control, or a picture.
const DESIGN_PARTS = `${WORKS},${genericVisualSelector}`;
/** @typedef {{segments: import("./passages.js").Segment[], at: Map<Element, number>}} BlockWords */
// A control's spoken words: its block's words on each side of it, at most `AROUND`
// characters a side as every description of what stands around something reads them
// (`contextAround`), with its own between. Every part's words are left out of its
// block's, so a neighbour's label never names this one, and a picture says none of its
// own, since its name describes it: a text document's view is a picture of the whole
// document, whose words would be read whole twice for every move of the pointer over it
// in Design mode. Other controls say their own words
// as a label does (`LABEL_WORDS`), less the `part` name the spoken name says before
// them, as a tab whose words start with its name and go on to a count. A block is read
// once per inventory, noting where each part stands in it; chosen capture stays lazy.
/** @param {Element} control @param {Map<Element, BlockWords>} contexts @param {string} part */
function controlContext(control, contexts, part) {
  const said = control.matches(genericVisualSelector)
    ? ""
    : excerptWords(excerpt(control, { upTo: LABEL_WORDS + 1 }).text, LABEL_WORDS);
  const own = said.startsWith(`${part} `) ? said.slice(part.length + 1) : said;
  const block = blockAt(control);
  if (!block || block === control || closestAcross(block, WORKS)) return own;
  let words = contexts.get(block);
  if (!words) {
    /** @type {Map<Element, number>} */
    const at = new Map();
    const segments = textNodesUnder(block, "says", (element, count) => {
      if (!element.matches(DESIGN_PARTS)) return false;
      at.set(element, count);
      return true;
    });
    contexts.set(block, (words = { segments, at }));
  }
  const split = words.at.get(control);
  if (split === undefined) return own;
  return [
    lastWords(quoteFrom(words.segments.slice(0, split)), AROUND),
    own,
    excerptWords(quoteFrom(words.segments.slice(split)), AROUND),
  ]
    .filter(Boolean)
    .join(" ");
}
// Keep inline emphasis in one label passage, but never cross the nested field's
// words or native box to pretend its options are part of the visible label.
/** @param {Element} face @param {Element} control */
function controlPassages(face, control) {
  const words = textNodesUnder(face);
  const barriers = face === control ? queryAllUnder(face, WORKS) : [control];
  /** @type {import("./passages.js").Segment[][]} */
  const passages = [];
  /** @type {import("./passages.js").Segment[]} */
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

/** @param {import("./passages.js").Segment[]} segments */
function visiblePassage(segments) {
  const clips = new Map();
  return segments.every((segment) => {
    const holder = segment.node.parentElement;
    if (
      !holder ||
      !holder.checkVisibility({
        opacityProperty: true,
        visibilityProperty: true,
      })
    )
      return false;
    return [...rangeOf([segment]).getClientRects()].some(
      (rect) =>
        rect.width > 0 && rect.height > 0 && clippedContents(rect, holder, clips),
    );
  });
}

/** @param {Node | null} node @param {AimOptions["marginTargetAt"]} marginTargetAt
 * @param {{owners: Map<Element, AimTarget>, contexts: Map<Element, BlockWords>}} [reading] @returns {AimTarget | null} */
function designTargetAt(
  node,
  marginTargetAt,
  reading = { owners: new Map(), contexts: new Map() },
) {
  const { owners, contexts } = reading;
  let at = node instanceof Element ? node : node?.parentElement;
  if (!at) return null;
  const pressed = designPressAt(at);
  const control = pressed?.matches(DESIGN_PARTS) ? controlIdentity(pressed) : null;
  const visual = visualAt(at, { unclaimed: false });
  const declared = declaredVisualSelector();
  if (declared && visual?.element.matches(declared)) at = visual.element;
  else if (
    control &&
    ((pressed instanceof HTMLLabelElement && pressed.control) ||
      (visual && control.matches(PRESSES) && under(visual.element, control)))
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
  if (!partElement || !part)
    return control === element
      ? {
          ...target,
          controlElement: control,
          controlFaces: controlFaces(control),
        }
      : target;
  const faces = controlFaces(partElement);
  const detail = [
    ...new Set([
      controlContext(partElement, contexts, part),
      ...faces
        .filter((face) => face !== partElement)
        .map((label) =>
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
  // Inventory reads names and faces only, which is all the box and name a hovering
  // pointer paints need. The control's passage is captured once, when a press or a
  // picker choice commits the target and needs its durable coordinate (`captured`).
  return {
    ...named,
    capture() {
      const repeatedName = namedParts(element, part).length > 1;
      // Native associated labels are physical faces of the same control. Try the
      // visible words on each face without inventing quote text from an ARIA name.
      for (const face of faces) {
        for (const passage of controlPassages(face, partElement)) {
          if (!passage.length || holdsEditedValue(passage)) continue;
          const captured = anchorForRange(rangeOf(passage));
          if (!captured) continue;
          const resolved = captured.quote
            ? resolveAnchor({ ...captured, quote: captured.quote })
            : null;
          const attachment =
            resolved?.kind === "passage" && passageGeometry(resolved)?.attachment;
          // Hidden option words and repeated passages cannot establish an exact face.
          if (
            resolved?.kind === "passage" &&
            resolved.exact &&
            attachment &&
            resolved.segments.every(({ node }) => under(node, face)) &&
            overlaps(attachment, face.getBoundingClientRect()) &&
            visiblePassage(resolved.segments)
          ) {
            // A repeated control’s announcement and its durable anchor share the same
            // distinguishing context, including neighbouring table cells.
            const at = resolved.segments[0]?.node ?? face;
            const context = contextAround(readingHolding(at), resolved.segments, {
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
// A Design mode target is its inventory reading, as `aimTargets` gives the picker: a
// control part's quoted passage waits for whoever commits it (`captured`).
/** @param {Node | null} node @param {AimOptions} [options] @returns {AimTarget | null} */
export function aimTargetAt(node, { design = false, marginTargetAt } = {}) {
  if (design) return designTargetAt(node, marginTargetAt);
  const visual = visualAt(node, { unclaimed: false });
  if (visual?.part) return partTarget(visual, visual.part);
  const datum = closestAcross(node, DATUM);
  if (datum) return datumAimTarget(datum);
  const addressable = addressableAt(node);
  return addressable ? addressableAimTarget(addressable) : null;
}

/** @param {NonNullable<ReturnType<typeof visualAt>>} visual
 * @param {import("../state/visual-parts.js").VisualPart} part @returns {AimTarget} */
const partTarget = (visual, part) => ({
  anchor: { section: visual.id, visual: part.id },
  element: part.element,
  label: aimLabel(visual.seat, part.label),
  surface: part.surface ?? null,
});

// The target focus on `node` names: the part a visual holding focus stands on, as a
// chart on the point its keys reached (`focusedVisualPart`), else the target a press
// on `node` takes. Only focus asks the visual itself, so a reading of the picture as
// a whole, as the target picker's, keeps it whole.
/** @param {Element} node @returns {AimTarget | null} */
export function focusTargetAt(node) {
  const visual = visualAt(node, { unclaimed: false });
  const admits = visual?.element === node ? visualAdmission(node) : null;
  const part = admits && focusedVisualPart(node, (found) => admits(found.id));
  return visual && part ? partTarget(visual, part) : aimTargetAt(node);
}

// A target as a comment takes it: a Design mode control part with its passage
// captured (`designTargetAt`), and any other target as it is. What a caller added to
// the target, such as the point a press landed on (pointed-place.js), stays with it.
/** @template {AimTarget | null | undefined} T @param {T} target @returns {T} */
export const captured = (target) => {
  if (!target?.capture) return target;
  const { capture, ...added } = target;
  return /** @type {T} */ ({ ...added, ...capture() });
};

/** @param {AimOptions} [options] @returns {AimTarget[]} */
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
    .filter((target) => target !== null);
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

// The datum a passage across data starts in: the one drawn for `key` from the value
// `last` was drawn from, or null where none or several are.
/** @param {Element | null} source @param {string} key @param {Element} last */
function runStart(source, key, last) {
  const first = projectedDatum(source, key);
  return first && first !== last && drawnTogether(first, last) ? first : null;
}

/** @param {Anchor} anchor @returns {import("./resolved-target.js").ElementTarget | import("./resolved-target.js").PassageTarget | null} */
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
      (basis !== null &&
        basis.getAttribute("data-lf-source") === anchor.source &&
        (anchor.identity
          ? datums.length > 0 &&
            basis.getAttribute("data-lf-identity") === anchor.identity
          : basis.getAttribute("data-lf-source-revision") === anchor.source_revision));
    // A widget that has yet to report a draw shows no revision at all, as a closed tab's
    // document does until it draws after presentation (lf-text-document.js,
    // `drawLater`), so an anchor on its data stands on the widget, not on earlier data.
    if (
      !basisMatches &&
      source &&
      !source.hasAttribute(PAGE_PAINT_ATTRIBUTE.drawReported)
    )
      return {
        ...resolvedElement({ element: source }),
        datumElement: null,
        exact: false,
        status: "fallback",
      };
    if (!basisMatches) {
      const contextual = source?.lfDataDatum?.(anchor.datum, {
        outdated: true,
      });
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
    // and duplicates refuse to guess. Changed text falls back to the same datum element
    // where the quote was all of the datum's words, so it named the datum, as a row's
    // label does. A quote with datum words around it named a passage in the datum, such
    // as a line of a text document, and once its words are gone it stands nowhere on the
    // page, rather than at the top of the datum. The quote is searched for in the datum's
    // words alone, the reading its context was captured from (`anchorForPassage`), so
    // finding it costs what the datum holds rather than what the page does.
    if (datums.length > 1) return null;
    const [datum] = datums;
    if (!datum) {
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
        ...resolvedElement({ element: datum }),
        datumElement: datum,
        exact: true,
        status: "exact",
      };
    // A passage across data is found in the words from the datum it starts in to this
    // one, the last. While its widget hasn't drawn its first datum, as in a file the
    // user closed, the passage stands on its last, as a datum not drawn stands on its
    // widget; once that datum is gone, the passage is too.
    const start = anchor.from ? runStart(source, anchor.from, datum) : datum;
    if (!start) {
      const virtual = anchor.from ? source?.lfDataDatum?.(anchor.from) : null;
      if (!(virtual instanceof Element) || !under(virtual, source)) return null;
      return {
        ...resolvedElement({ element: datum }),
        datumElement: null,
        exact: false,
        status: "fallback",
      };
    }
    const segments =
      start === datum
        ? findQuote(pageText(datum), anchor.quote, anchor, datum)
        : findQuote(runReading(start, datum), anchor.quote, anchor);
    const [first] = segments;
    if (!first && (anchor.prefix || anchor.suffix)) return null;
    return first
      ? {
          ...resolvedPassage({
            place: annotationAt(first.node, () => datum),
            segments,
          }),
          datumElement: datum,
          exact: true,
          status: "exact",
        }
      : {
          ...resolvedElement({ element: datum }),
          datumElement: datum,
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
        label: found.label,
      });
    // A declared part the visual draws only in another state stands in for the whole
    // visual, as a lazy datum does, until travel reveals it or the visual draws it. It
    // keeps the name its visual gives it there.
    return admitsVisualPart(section, anchor.visual) && drawsAbsentParts(section)
      ? {
          ...resolvedElement({
            element: section,
            surface: wholeVisualSurface(section),
            label: visualPartLabel(section, anchor.visual),
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

  const section = sectionOf(anchor);
  // A section the page doesn't hold, as one a revision dropped, leaves its words
  // nowhere to be looked for.
  if (anchor.section && !section) return null;
  const segments = findQuote(pageText(), anchor.quote, anchor, section);
  const [first] = segments;
  // Words the page doesn't show once, and no context picks a copy of, stand on their
  // section, as a dropped part stands on its visual, until they stand there once
  // again: a revision rewrote them, or the agent quoted words the page draws twice or
  // not at all. A quote with no section has nowhere to stand.
  if (!first)
    return section && !settledAway(section)
      ? {
          ...resolvedElement({
            element: section,
            surface: wholeVisualSurface(section),
          }),
          exact: false,
          status: "fallback",
        }
      : null;
  // An exact named-control quote identifies its actual readable face, so both the
  // editor and sent thread clear that face. Ordinary prose still clears its block.
  const face = anchor.part && closestAcross(first.node, WORKS);
  const controlFace =
    face && segments.every(({ node }) => closestAcross(node, WORKS) === face);
  return resolvedPassage({
    place: controlFace ? face : annotationAt(first.node),
    segments,
  });
}

/** @param {string} id */
const pageElement = (id) => targetElement(resolveAnchor({ section: id }));

// What a fragment names (base/anchor-coordinate.js, `fragmentKey`): the element whose id it
// spells, as `named` finds one, which by default reads the id as the anchor `{section}`
// is, so content a revision settled away names nothing. Failing that, a widget and a
// key, whose `place` is the element the key addresses under the widget
// (`addressedElements`) or null until the widget draws it (`revealAddressed`). A fresh
// load's arrival, a followed link, Back and Forward, and a reply's reference all read
// their destination through this.
/** @param {string | null | undefined} fragment
 * @param {(id: string) => Element | null} [named]
 * @returns {{element: Element, key: string | null, place: Element | null} | null} */
export function fragmentAddress(fragment, named = pageElement) {
  if (!fragment) return null;
  const whole = named(fragmentId(fragment));
  if (whole) return { element: whole, key: null, place: whole };
  const keyed = fragmentKey(fragment);
  const element = keyed && named(keyed.id);
  if (!keyed || !element) return null;
  return {
    element,
    key: keyed.key,
    place: addressedElements(element, keyed.key)[0] ?? null,
  };
}

// The page element a fragment names: for a widget's key, the part the widget has drawn
// for it, else the widget itself, so a reader that needs only an element lands on the
// widget.
/** @param {string | null | undefined} fragment */
export function fragmentTarget(fragment) {
  const address = fragmentAddress(fragment);
  return address ? (address.place ?? address.element) : null;
}

// The element an address a package module holds names (widget-api.js, `elementById`):
// an id, or a widget's id and key, spelled as a fragment (`#…`, encoded as a URL holds
// it) or bare, as `fragmentTarget` reads it. Each id is looked up as `from` gives it
// (references.js, `authoredElement`), in `from`'s own message first and then the page,
// so a copy of a page id that Leaf draws in a reply never answers for the page's own.
// An id neither holds names what the whole document holds, as a fragment's arrival
// reads it: a widget in a reply Leaf draws, which every count of a region's
// obligations places where the reply stands (records/obligations/place.js). Content a
// revision settled away names nothing, as for a fragment.
/** @param {string | null | undefined} address @param {Node | null} [from] */
export function elementNamed(address, from = null) {
  if (!address) return null;
  // A bare address is read as the fragment that spells it, each `%` kept.
  const fragment = address.startsWith("#")
    ? address
    : `#${address.replaceAll("%", "%25")}`;
  const found = fragmentAddress(fragment, (id) => {
    const element = authoredElement(id, from ?? pageDocument()) ?? elementById(id);
    return element && !settledAway(element) ? element : null;
  });
  return found ? (found.place ?? found.element) : null;
}
