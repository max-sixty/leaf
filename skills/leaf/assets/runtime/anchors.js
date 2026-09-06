/* This module owns anchor resolution, anchor paint, anchor-specific travel, and
 * cross-widget projected-datum travel. `sameAnchor` is the one shared reading of
 * whether two anchors name the same place. */
import { inUi, under } from "./shadow.js";
import {
  clippedRect,
  documentPoint,
  shownBand,
  shownBox,
  shownRect,
} from "./geometry.js";
import { marginButton, openPageThread, registerMarginItem } from "./living-margin.js";
import { scheduleMarginLayout } from "./margin-layout.js";
import {
  resolvedElement,
  resolvedPassage,
  targetElement,
  targetParts,
  targetSegments,
  targetSurface,
} from "./resolved-target.js";
import { moveScrollerBy, pageScroller } from "./scrolling.js";
import { focused } from "./keyboard/scopes.js";

import {
  visualPart as registeredVisualPart,
  visualPartAt as registeredVisualPartAt,
} from "./visual-parts.js";
import {
  composerOpen,
  composerQuote,
  pendingAbout,
  pendingAnchor,
  pendingDrawing,
} from "./composing/selection.js";
import { drawingShifted } from "./composing/drawing.js";
import {
  designName,
  designOn,
  designTarget,
  inspectEl,
  queueLegend,
} from "./design.js";
import {
  blockAt,
  closestAcross,
  containsAcross,
  cut,
  DATUM,
  elementById,
  elementFromPointAcross,
  findQuote,
  inChrome,
  pageQueryAll,
  pageText,
  pageWords,
  quoteFrom,
  rangeOf,
  settledAway,
  textNodesUnder,
} from "./passages.js";
import { registry, tagsDeclaring } from "./registry.js";
import { announce } from "./notifications.js";
import { scrollBehavior } from "./motion.js";
import { el, offer, reveal, WORKS_WITHOUT_TAB_STOP } from "./widget-elements.js";
import { runtimeOwnsScrollerStop } from "./reach.js";
import { renderPanel } from "./conversation/reconcile.js";
import { commentOnTarget, fabAnchorAt, refreshFab } from "./composing/surface.js";
import { aimedTarget, aimIsOn } from "./composing/aim.js";
import { pointerAt } from "./pointer.js";
import { panel, threadsBox } from "./conversation/panel.js";
import { withdraw } from "./projection.js";
import { scrollerFor } from "./navigation.js";
import { focusedThreadOf } from "./keyboard/page.js";
import {
  clearAim,
  geometryChanged,
  paintAim,
  setTargets,
  shifted,
  paintTrace,
} from "./target-paint.js";
import { anchorLabel } from "./conversation/messages.js";
import { bareReaction, buildThreads } from "./conversation/model.js";
import { paintThreadQuotes } from "./conversation/thread-card.js";

// Anchors are durable coordinates, so their pass and every route that can mint one begin
// only after replay has reconciled the authored document; presentPage says when.
let anchoringReady = false;
export const anchoringIsReady = () => anchoringReady;
export function setAnchoringReady(ready) {
  anchoringReady = ready;
}

/* Anchor resolution, painting, and anchor-specific travel.

   `selectionAnchor` (composing/capture.js) and the file-side comment capture produce
   the same collapsed quote, surrounding context, and section identity. `resolveAnchor`
   is the only search implementation. It accepts an occurrence only when full context
   confirms one candidate. A quote that occurs once may stand without context; a
   repeated quote with no unique context detaches instead of using document order or an
   old offset.

   An element anchor has no text range. `sectionOf` resolves its id and marking uses
   visible element parts. Text anchors use passages.js's `segmentsIn`, `spanIn`, and
   `rangeOf`. `itemSays` labels a compact view from an item's own opening words. A
   decision that needs a useful row label states it on itself, commonly through an
   `x-says` attribute; the row does not infer a heading from surrounding layout.

   `paintAnchors` is the only anchor writer. One pass decides thread marks, element
   outlines, and the open composer's pending mark. It clears and paints through the
   same composed-tree helpers, then records exactly what it drew in `marked`,
   `pendingMarks`, and `pendingOutline`. Other features consult those records rather
   than looking for arbitrary DOM paint. The anchor runtime exposes only the questions
   other features ask — `isMarked` and `placedAt` — so the pass-owned maps and arrays
   cannot acquire a second writer through the entrypoint.

   The same pass answers a second question and records it apart. `placed` records at
   least `{element, datumElement, exact, status}` for each thread; `status` is `exact`,
   `fallback`, or `outdated`. `marked` is what was drawn for it. They differ for a
   resolved thread, which has a place and no paint, and for an element anchor, whose
   paint is the boxes its contents show through rather than the element the anchor
   named. The panel's order reads `placed`, so the list and the page cannot disagree
   about which of two threads comes first, and one walk of the document's text answers
   both. `renderPanel` therefore paints before it renders the list. Do not resolve a
   thread's anchor a second time to sort it.

   `paintStanding` is the second reading of that record: the thread holding the panel's
   focus paints its own passage apart from every other mark, as `lf-mark-here` over its
   ranges and as a class of the same name over its element parts. It reads the focus,
   through `closest`, rather than being written where a travel left the reader — the
   argument `markHere` makes for the decision ring, and for the same reason. Every route
   that puts the reader in a thread therefore paints it: the quote's press, the `t`/`T`
   walk, a click on the card, a reply box. A press on a page mark reaches `showThread`,
   which focuses the reply box before its deliberate reveal. Escape returns to the
   card; `t`/`T` then walk the threads. `paintHere` repaints it beside the decision
   ring, and `paintAnchors` repaints it after rebuilding the ranges it holds.

   The panel paints the same fact on the card, through `.lf-thread:focus-within` — the
   same predicate, so the two halves cannot disagree about which comment the reader is
   in. `:focus-visible` instead answers which input modality should draw the browser's
   focus indicator. While typing, the reply box carries the strong focus ring and the
   enclosing thread keeps a subdued outline.

   `lf-mark-hover` answers a different question — which thread the pointer is
   indicating — and reads both surfaces in one frame. A card is the thread's view in
   the list the way a mark is its view in the prose, so resting on the card lights the
   passage exactly as resting on the passage lights its bounded quote, and a reader
   sweeping a full panel is told what each comment is about without pressing anything.
   The semantic class stays on the card while its quote takes the wash: a long thread
   can span several viewports, while the clamped quote is the panel's compact
   representation of the passage. There is one answer rather than two because the
   pointer is in one place: `markAt` refuses a point that lands in the chrome, so
   `hoveredThreadOf` and the page's hit test cannot both name a thread. Both are read
   inside `refreshHover`'s frame, which is also what settles `:hover` — asking for it
   from inside the pointer event that moves it asks mid-move — and a second writer to
   this highlight would be overwritten by whichever frame ran last.

   `body.lf-over-mark` stays with the page's own reading: it is the promise that a
   press here opens something, and over a card the press on offer is the card's, which
   `.lf-quote` states for itself. `setPanel` asks the question again on the way out as
   well as in, because the panel is one of the two surfaces this reads: closing it from
   the keyboard, with a hand resting on a card, takes that card out from under a
   pointer that never moved.

   Hover state keeps both the semantic id and painted card node because reconciliation
   can replace one without changing the other. `paintAnchors` rebinds replaced ranges
   and element parts; `renderThreads`, page movement, and a version transition's end
   refresh the reading when content moves under a stationary pointer.

   `paintHover` paints both kinds of anchor, as `paintStanding` does. `::highlight`
   paints glyphs, so a box wears the posted wash as a background image instead
   (`.lf-mark-el`) and says the hover rank in the property it has, one weight up from
   the posted hairline (`.lf-mark-el.lf-mark-hover`).
   Without that, an element-anchored comment answered the pointer with nothing at all —
   which from the panel, where there is no page cursor to change, reads as a broken
   hover rather than as a passage with no words.

   A bare reaction — a token comment nobody has replied to — is paint, not a thread.
   `paintAnchors` resolves its anchor like any comment's and records it in `reacted`
   rather than `marked`: a wash through the `lf-react` highlight on a passage,
   `lf-react-el` on an element's shown parts, and a glyph reconciled by `seatReactions`.
   Its `.lf-reacts` span is an unpositioned contribution to the target's Button
   cluster; the pill inside is the reaction's own eraser, posting the ordinary `undo`
   through `withdraw`. It wears `lf-ui` and `data-lf-gen`, so no reading takes it for
   the page's words. `markAt` does not see it: a reaction takes no press to a card and
   has no hover. Export keeps the glyph with its press taken off and writes the wash
   into the words as a `<mark>` (the bake), the highlight registry being script state
   no file can hold.

   `scrollToThread` is the one travel every "show me that comment's passage" ends in.
   Each nested scrollport first reveals the exact range instantly on both axes without
   writing the document's position, then `moveScrollerBy` glides that range to its
   final position in the region that holds it. The travel owns no standing or arrival
   state. Focus already supplies the durable answer through `paintStanding`, and a
   transient page effect does not observe, restart, or reconcile across the browser's
   scrolling operation.

   Use the CSS custom highlight registry for text marks. Wrapping ranges mutates and
   splits authored text nodes, can cancel a click between pointer down and pointer up,
   and creates a second DOM representation for the passage. `markAt` performs geometric
   hit testing over the ranges recorded by `paintAnchors`.

   Custom highlights create no accessibility nodes. `noteMarks` adds one hidden,
   unselectable button to each block that contains comments and states the comment
   count. It names the block rather than copying the selected words. Keep that line
   outside selection, quote capture, widget word readings, and clipboard output. */
// Anchors are shallow records of primitive coordinates. Compare the complete records:
// reading only the left operand's keys made a whole-visual anchor equal the part anchor
// that extended it, but not the other way around.
export const sameAnchor = (a, b) => {
  if (a === b) return true;
  if (!a || !b) return false;
  const left = Object.keys(a).sort();
  const right = Object.keys(b).sort();
  return (
    left.length === right.length &&
    left.every((key, index) => key === right[index] && a[key] === b[key])
  );
};

// ---------- anchors ----------
// An anchor names a passage: a section id, a quote, or both. Resolving one is the only
// place the page is searched, so the three things that read a passage back — a thread's
// mark, the composer's own, and the reading position a version change rides on — cannot
// disagree about where to look. A quoteless anchor has no text to paint and resolves to
// its element instead.
// The search always reads the whole document — the same text the capture wrote the
// neighbours from — and the section the anchor names filters where a candidate may sit.
// A section the page no longer has filters nothing, so the quote is still looked for
// everywhere, which is all a stale section ever meant.
// Which element an anchor names, asked in one place: the element it resolves to when it
// carries no quote and the subtree a candidate has to sit inside when it does.
export const sectionOf = (anchor) =>
  anchor.section ? elementById(anchor.section) : null;

function currentDatums(source, key) {
  if (!source?.id) return [];
  return pageQueryAll(DATUM).filter(
    (datum) =>
      containsAcross(source, datum) &&
      datum.dataset.lfProjection === source.id &&
      datum.dataset.lfDatum === key,
  );
}

const currentDatum = (source, key) => {
  const matches = currentDatums(source, key);
  return matches.length === 1 ? matches[0] : null;
};

function suppliedDatum(source, key) {
  const supplied = source?.lfDataDatum?.(key);
  return supplied instanceof Element &&
    containsAcross(source, supplied) &&
    supplied.dataset.lfProjection === source.id
    ? supplied
    : null;
}

function referencedProjection(owner, attribute) {
  if (!(owner instanceof Element))
    throw new TypeError("navigateToDatum owner must be an element");
  if (
    typeof attribute !== "string" ||
    !Object.hasOwn(registry[owner.localName]?.["x-refers"] ?? {}, attribute)
  )
    throw new TypeError(
      `navigateToDatum ${owner.localName} attribute ${String(attribute)} is not declared by x-refers`,
    );
  const id = owner.getAttribute(attribute);
  return id ? elementById(id) : null;
}

export async function navigateToDatum(
  owner,
  attribute,
  key,
  { success = "", missing = "" } = {},
) {
  if (typeof key !== "string" || !key)
    throw new TypeError("navigateToDatum key must be a non-empty string");
  let source = referencedProjection(owner, attribute);
  if (!source) {
    if (missing) announce(missing);
    return false;
  }

  // Give a lazy or filtered projection the first chance to make this key reachable.
  // A datum may already exist in a subtree hidden by a widget-owned filter, which core
  // cannot infer from DOM geometry without taking ownership of that widget's state.
  const hydration = source.lfRevealDatum?.(key);
  if (hydration?.then) await hydration;
  source = referencedProjection(owner, attribute);
  if (!source) {
    if (missing) announce(missing);
    return false;
  }
  const destination = currentDatum(source, key) ?? suppliedDatum(source, key);

  const url = new URL(window.location.href);
  url.hash = source.id;
  history.pushState(null, "", url);
  if (!destination) {
    scrollToElement(source, scrollBehavior(), "start");
    if (missing) announce(missing);
    return false;
  }

  reveal(destination);
  const disclosure = closestAcross(destination, "details");
  disclosure?.querySelector(":scope > summary")?.focus({ preventScroll: true });
  scrollToElement(destination);
  if (success) announce(success);
  return true;
}

// A generated picture part keeps two identities. The authored widget is its semantic
// seat; the package registers the current rendering behind each stable authored token.
// Core verifies the token against the declaration before trusting the inventory, so a
// renderer's generated id never escapes into the event log.
const visualPartAttribute = (visual) => {
  const declaration = registry[visual?.localName]?.["x-visual"];
  return declaration && typeof declaration === "object" ? declaration.parts : null;
};
const wholeVisualSurface = (element) =>
  registry[element?.localName]?.["x-visual"] ? element : null;
const declaredVisualParts = (visual) => {
  const attribute = visualPartAttribute(visual);
  const value = attribute ? visual?.getAttribute(attribute) : "";
  return new Set(value?.trim().split(/\s+/).filter(Boolean) ?? []);
};
function visualPart(visual, part) {
  if (!declaredVisualParts(visual).has(part)) return null;
  return registeredVisualPart(visual, part);
}
function visualPartAt(visual, target) {
  const declared = declaredVisualParts(visual);
  return registeredVisualPartAt(visual, target, (part) => declared.has(part.id));
}
export const visualPartLabel = (visual, part) =>
  visualPart(visual, part)?.label ?? null;
const declaredVisualSelector = () =>
  [...tagsDeclaring((entry) => entry["x-visual"])].join(",");
const genericVisualSelector = "svg, img, figure";
const visualSelector = () =>
  [declaredVisualSelector(), genericVisualSelector].filter(Boolean).join(",");
// Asked at use: widget-elements.js's selector reaches this module back, so it is not
// readable as this module evaluates.
const interactiveWithoutTabStopSelector = () =>
  `${WORKS_WITHOUT_TAB_STOP},[data-lf-offer]`;
const parentAcross = (element) =>
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
const unclaimedVisualGesture = (target) => {
  if (inChrome(target) || inUi(target)) return false;
  for (let element = target; element; element = parentAcross(element))
    if (claimsVisualGesture(element)) return false;
  return true;
};
// A declared provider owns every hit inside it, including its inner svg. Outside one,
// the outermost ordinary picture is the visual reading. A wrapping figure and a
// provider inside it remain separate authored items: explicit aim can name the
// figure's caption or frame, while a hit inside the provider names its own target.
// Generated ids remain implementation details; the nearest authored id is the durable
// seat.
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

// Explicit pointer targeting may use the picture itself. Keyboard activation uses
// controls the runtime owns beside it, so generated provider markup keeps its own roles
// and remains clean when the live layer is removed from an exported copy. Each visual
// exposes its whole target and, when declared, each stable part.
const visualActionHolders = new WeakMap();
export const visualActionAnchor = (anchor) =>
  pageQueryAll(".lf-visual-action").find((control) =>
    sameAnchor(control.lfAnchor, anchor),
  ) ?? null;
// A proxy stands after the thing whose visibility controls the picture. In particular,
// putting it inside a closed details makes the control impossible to focus, so the
// disclosure is the stable seat and focusing the proxy can reveal the target inside it.
// Shadow renderers share their host as a seat; one holder there avoids moving several
// sibling holders past one another on every paint.
function visualActionSeat(candidate) {
  let seat =
    candidate.getRootNode() instanceof ShadowRoot
      ? candidate.getRootNode().host
      : candidate;
  for (let current = seat; current; current = parentAcross(current))
    if (current.matches?.("details")) seat = current;
  return seat;
}
function prepareVisualActions() {
  const groups = new Map();
  const claimed = [];
  const kept = new Set();
  for (const candidate of pageQueryAll(visualSelector())) {
    const found = visualAt(candidate);
    if (!found || found.element !== candidate) continue;
    const targets = [
      {
        anchor: { section: found.id },
        label: anchorLabel({ section: found.id }).replace(/^§\s*/, "") || found.id,
      },
      ...[...declaredVisualParts(candidate)].flatMap((token) => {
        const part = visualPart(candidate, token);
        return part && unclaimedVisualGesture(part.element)
          ? [
              {
                anchor: { section: found.id, visual: part.id },
                label: part.label,
              },
            ]
          : [];
      }),
    ];
    const seat = visualActionSeat(candidate);
    let group = groups.get(seat);
    if (!group) {
      group = [];
      groups.set(seat, group);
    }
    for (const target of targets)
      if (!claimed.some((anchor) => sameAnchor(anchor, target.anchor))) {
        claimed.push(target.anchor);
        group.push(target);
      }
  }
  for (const [seat, targets] of groups) {
    if (!targets.length) continue;
    let record = visualActionHolders.get(seat);
    if (!record?.holder.isConnected) {
      record = { holder: offer("span", "lf-visual-actions") };
      visualActionHolders.set(seat, record);
    }
    const { holder } = record;
    const unused = new Set(holder.children);
    const controls = targets.map(({ anchor, label }) => {
      let control = [...unused].find((child) => sameAnchor(child.lfAnchor, anchor));
      if (!control) {
        control = offer("button", "lf-visual-action lf-quiet");
        control.onfocus = () => {
          let current = resolveAnchor(control.lfAnchor, pageText());
          let element = targetParts(current)[0] ?? targetElement(current);
          if (!element) return;
          reveal(element);
          current = resolveAnchor(control.lfAnchor, pageText());
          element = targetParts(current)[0] ?? targetElement(current);
          element?.scrollIntoView({
            behavior: "instant",
            block: "nearest",
            inline: "nearest",
          });
        };
        control.onclick = () =>
          commentOnTarget({ anchor: control.lfAnchor }, { origin: control });
      }
      unused.delete(control);
      control.lfAnchor = anchor;
      const name = `Respond to ${label}`;
      if (control.textContent !== name) control.textContent = name;
      return control;
    });
    for (const control of unused) control.remove();
    controls.forEach((control, index) => {
      if (holder.children[index] !== control)
        holder.insertBefore(control, holder.children[index] ?? null);
    });
    if (seat.nextSibling !== holder) seat.after(holder);
    kept.add(holder);
  }
  for (const holder of pageQueryAll(".lf-visual-actions"))
    if (!kept.has(holder)) holder.remove();
}

// ---------- pointing at an item ----------
// One pointer gesture reaches any item: ⌥-click — direct aim, no selection, no chrome,
// and the only route to an item whose words are all inside controls. Plain click keeps
// its native meaning. Two more routes were tried and cut. A margin rule raised by
// hovering was too strong for what it offered and sat at
// the item's own left edge, which is the page's margin only when that item happens to
// be left-aligned. A row of chips beside the 💬 offered the selection's enclosing chain
// ("⬚ paragraph", "⬚ section") — a correction nobody had asked for, paid in chrome
// beside every selection a user made.
//
// A whole item writes {section: <id>} with no quote. A declared picture part adds its
// authored `visual` token; the section remains the durable seat. Both coordinates come
// from markup rather than from whatever ids a renderer generated for this load.
//
// An item is an element the author gave an id, outside the runtime's own layer and
// outside the panel (a reply's frozen widget markup carries ids of its own). `version
// check` holds every id across versions, which is exactly why an anchor naming one
// survives a rewrite that takes a quote down with it. An id under the runtime's own
// prefix is not the author's — a module coins one for what it draws (a diagram's svg
// wears `lf-diagram-N`, numbered by draw order) — so an anchor on it names nothing a
// version holds and something the next load may number differently. The item is the
// element around it unless its declaration maps the generated box to an authored token.
export const ITEM = '[id]:not(.lf-ui):not([id^="lf-"])';
// Whether an element is an item: what the aim walks up to, and what the legend draws a
// box for — one predicate, so the two cannot disagree about what is on the page. Never
// one the user's decision settled off the page: the aim's paint already refused those,
// and a press answered by a different predicate anchored a composer to a retired
// element — a box about nothing, promised by nothing. And never one inside a widget
// that renders as a picture (x-visual): a diagram's nodes carry the ids its renderer
// coined — `root-1`, `actor0`, under no prefix of ours — and `itemAt` must never return
// one. The visual-part provider is the only route that may turn that generated box
// into an authored coordinate.
export function isItem(at) {
  if (!at.matches(ITEM) || inChrome(at) || inUi(at) || settledAway(at)) return false;
  const visual = tagsDeclaring((e) => e["x-visual"]).join(",");
  return !(visual && at.parentElement && closestAcross(at.parentElement, visual));
}
// The innermost item: a card rather than its column, the column rather than the board —
// the smallest thing under the pointer is the thing pointed at. The walk continues
// upward past what is not one, because the enclosing item is what is on screen.
export function itemAt(node) {
  let at = node?.nodeType === 1 ? node : node?.parentElement;
  for (; at; at = at.parentElement ?? at.getRootNode()?.host ?? null)
    if (isItem(at)) return at;
  return null;
}
// Notes and reaction controls belong beside authored content, never inside the
// generated text container a widget reads back into an editor.
const annotationAt = (node) => blockAt(node) ?? itemAt(node);
// What to call an item, in a word the user reads beside a thread's § label. A widget
// names itself: its tag minus the prefix is already the word the vocabulary chose
// ("card", "option", "column"), so the twelfth widget gets a name here without core
// hearing about it.
//
// The page's own elements have no such word. A tag is markup rather than English, and a
// label reading "§ p · …" over ordinary prose names the thing to a browser and to nobody
// else. So HTML's tags get the nouns a reader would use, and an unlisted one falls back
// to its tag, which is worse than a word and better than nothing.
const HTML_WORDS = {
  // Every one of these is a control the platform gives keys to and no letters — a radio,
  // a checkbox, a slider, a colour or file button. The ones that take letters never reach
  // this reading, the typing scope having claimed the key before the page is asked, so
  // there is no field here for "control" to misname. Worth a word at all because `c` names
  // what it is about, and a reader standing on a toggle was told "the input".
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
export function itemWord(item) {
  if (!item) return "";
  const tag = item.tagName.toLowerCase();
  // A widget whose kind is not its tag says which it is. Three shapes of change are all
  // <lf-suggestion>, and naming each of them by the tag put a deletion in the Asks tray
  // under the words it proposed to remove, reading exactly like the insertion above it.
  // Asked only where an entry says there is something to ask, and answered only by an
  // element that has upgraded — before that, and for every widget that declares nothing,
  // the tag is the word.
  if (registry[tag]?.["x-word"] === "module") {
    const own = item.lfWord?.();
    if (own) return own;
  }
  if (tag.startsWith("lf-")) return tag.slice(3);
  // A <pre> is a block of something and the something is in the markup: the documented
  // shape for source is <pre><code class="language-*">, and a <pre> without the <code> is
  // the shape for what isn't source — a transcript, a stack trace, command output. So the
  // word is read rather than assumed, and a user who calls it a code block is offered
  // one.
  if (tag === "pre") return item.querySelector(":scope > code") ? "code" : "block";
  return HTML_WORDS[tag] ?? tag;
}
// The item's own opening words, read the way anchoring reads everything else — so a label
// a widget declared as the page speaking is in it and the runtime's own chrome (the hidden
// "2 comments" line) is not. Cut back to a word boundary and marked as cut, because a label
// ending mid-word reads as a quote that lost its tail rather than as a name for the thing.
const ITEM_SAYS_CAP = 52;
// The reading is the whole answer, and it is the answer wherever the item stands. An
// decision carried by a message is still a decision, and it is read here exactly as one on
// the page is: rooted at the item, so the panel around it is nobody's chrome (see the
// note on `overIn`) while the item's own marks and offers still are. A veto on
// `inChrome` stood in front of this, from the days only an anchor's section reached it:
// it threw the reading away and left the Asks tray naming the question by its raw id.
export function itemSays(item) {
  if (!item) return "";
  // A module that names its own kind (x-word) may name its own words too: a rewrite's
  // slots read `courtyardcovered terrace` as text nodes, and `courtyard → covered
  // terrace` is what the page shows. Asked the same way as the word, and falling
  // back the same way for a tag that has not upgraded or answers nothing.
  const own = registry[item.localName]?.["x-word"] === "module" ? item.lfSays?.() : "";
  const whole = own || quoteFrom(textNodesUnder(item));
  if ([...whole].length <= ITEM_SAYS_CAP) return whole;
  const short = cut(whole, 0, ITEM_SAYS_CAP);
  const at = short.lastIndexOf(" ");
  return (at > ITEM_SAYS_CAP / 2 ? short.slice(0, at) : short).trimEnd() + "…";
}
const aimLabel = (
  item,
  says = itemSays(item) ||
    item?.getAttribute("aria-label") ||
    item?.querySelector("[aria-label]")?.getAttribute("aria-label"),
) => [itemWord(item), says].filter(Boolean).join(": ");
const itemAimTarget = (item) => ({
  anchor: { section: item.id },
  element: item,
  label: aimLabel(item),
  surface: wholeVisualSurface(item),
});
const datumAimTarget = (datum) => {
  const dataRevision = Number(datum.dataset.lfSourceRevision);
  return {
    anchor: {
      section: datum.dataset.lfProjection,
      datum: datum.dataset.lfDatum,
      ...(datum.dataset.lfSource && Number.isInteger(dataRevision)
        ? {
            source: datum.dataset.lfSource,
            data_revision: dataRevision,
          }
        : {}),
    },
    element: datum,
    label: datum.dataset.lfDatumLabel?.trim() || aimLabel(datum),
  };
};
// One reading for the pointer aim and the keyboard's item hints. A provider's declared
// part is the narrowest picture target, then a projected datum, then the innermost
// stable authored item. The returned element is always the element that anchor resolves
// to, so the aim's box and the eventual mark make the same promise.
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
  const item = itemAt(node);
  return item ? itemAimTarget(item) : null;
}
export function aimTargets() {
  const candidates = [
    ...pageQueryAll(ITEM).filter(isItem),
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
export function resolveAnchor(anchor, text) {
  // An element anchor asks a different question — whether the section is still on the
  // user's page — and the whole page is not an answer to it. Existence alone isn't
  // either: a decided element whose markup settles to nothing is present in the
  // document and absent from the screen, and an anchor held to it read as attached
  // while outlining nothing.
  if (anchor.datum) {
    const source = sectionOf(anchor);
    const datum = currentDatums(source, anchor.datum);
    const anchoredToData =
      typeof anchor.source === "string" && Number.isInteger(anchor.data_revision);
    const basis = datum[0] ?? source;
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
    // A projection/key pair identifies exactly one current fact. Disappearance detaches;
    // duplicates refuse to guess. Where its old display text still stands, mark those
    // exact words. Where the value changed, outline the same datum whole instead of
    // silently following the old string to some other fact.
    if (datum.length > 1) return null;
    if (!datum.length) {
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
        ...resolvedElement({ element: datum[0] }),
        datumElement: datum[0],
        exact: true,
        status: "exact",
      };
    const segments = findQuote(text, anchor.quote, anchor, datum[0]);
    return segments.length
      ? {
          ...resolvedPassage({
            place: blockAt(segments[0].node) ?? datum[0],
            segments,
          }),
          datumElement: datum[0],
          exact: true,
          status: "exact",
        }
      : {
          ...resolvedElement({ element: datum[0] }),
          datumElement: datum[0],
          exact: true,
          status: "exact",
        };
  }
  if (anchor.visual) {
    const section = sectionOf(anchor);
    // A semantic visual coordinate is deliberately distinct from `part`, the
    // free-form control label design mode records. Losing either the declaration or
    // its provider therefore detaches instead of silently widening to the widget.
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
      ? resolvedElement({
          element: section,
          surface: wholeVisualSurface(section),
        })
      : null;
  }
  const segments = findQuote(text, anchor.quote, anchor, sectionOf(anchor));
  return segments.length
    ? resolvedPassage({
        // Attached chrome belongs beside a widget's readable body, never inside
        // that body. A block is the passage seat; otherwise use its authored item.
        place: blockAt(segments[0].node) ?? itemAt(segments[0].node),
        segments,
      })
    : null;
}

// Every mark the page wears, drawn by one pass, so ownership of an element both a thread
// and the open composer point at is a branch inside a loop rather than an agreement
// between functions ("One writer per thing" in CLAUDE.md, and why).
//
// One range per segment, never one spanning the passage: a single range would paint back
// over everything the search stepped around on the way — a widget's Choose button, a drag
// grip, a diagram's generated stylesheet.
//
// Keyed by thread, not by mark: a passage is several segments and two comments may land on
// the same element, so mark → thread loses one of them — and losing it told the panel the
// passage wasn't in this version while it sat outlined on screen. Every consumer but the
// hit-test asks "where is thread X", and that is now the direction the map runs.
const MARK = "lf-mark";
const PENDING = "lf-pending";
export const NOTE = "lf-mark-note";
// A standing reaction's paint: a wash fainter than a comment's on the passage (the
// same highlight registry), a dashed hairline on an element, and a glyph in the margin
// level with the block the passage starts in. Nothing enters the text flow, so no line
// reflows when one lands; the glyph is the withdraw control, so the record and the
// eraser are one surface. Recorded apart from `marked` because it answers a different
// question — a reaction is not a thread, takes no press to a card, and has no hover.
const REACT = "lf-react";
const SEAT = "lf-reacts";
const reacted = new Map(); // thread id -> the ranges or element parts painted for it
const marked = new Map(); // thread id -> (Range | Element)[]: the pass's record of what it drew
// thread id -> the element its passage lands in. A different question from `marked`, and
// the one the panel's order asks: where a thread is, rather than what was drawn for it. A
// resolved thread has a place and no paint, and an element anchor's paint is the boxes its
// contents show through (shownParts) rather than the element the anchor named — so neither
// record answers for the other. Written only by the pass that resolves the anchors, so the
// two readings can never come from different resolutions.
const placed = new Map();
let pendingPlaced = null;
let pendingMarks = []; // the same record for the open composer's own passage
let pendingOutline = []; // the elements the open draft outlines, owned by nobody else
let actionOutline = []; // the visual target whose action bar is standing
const visualTargets = new Map();
// What the pointer would take, in whichever arming stands — the ⌥ aim's item, or design
// mode's target: the element, and the control's word where the pointer is on one — and
// null when neither is armed. One answer for the box, the cursor and the name.
function aimTarget() {
  if (aimIsOn()) {
    const target = aimedTarget();
    return target
      ? {
          el: target.element,
          part: "",
          surface: target.surface ?? null,
        }
      : null;
  }
  const pointer = pointerAt();
  if (designOn && pointer.x >= 0)
    return designTarget(document.elementFromPoint(pointer.x, pointer.y));
  return null;
}
// The aim's one writer, and the whole of its paint: the box in the chrome's layer
// (aimBox), the cursor's half of the same promise, and in design mode the name of what
// the box is on. Everything is derived fresh on every ask — the aimed item, lf-over-item,
// the box's geometry — because a latch here was a second answer to the question the
// press asks fresh, and a replay repainted it stale. Synchronous, not coalesced to a
// frame the way refreshHover is: the keydown that arms the page is followed by the press
// in the same gesture, and a promise a frame behind the arm is one the press can outrun.
// Ordinary items cost one hit-test and one rect walk, which is what the repaint gate
// this replaced already spent per event on deciding whether to run a far dearer pass.
export function refreshAim() {
  const target = aimTarget();
  const aimed = target?.el ?? null;
  // The cursor's half, written where the box's half is decided, so the hand cannot
  // stand over a press the paint knows takes nothing. `aiming` alone says the page
  // is armed; this says the aim has landed on something.
  document.body.classList.toggle("lf-over-item", Boolean(aimed));
  const r = aimed && paintAim(aimed, target.surface);
  if (!r) {
    clearAim();
    paintInspect(null);
    return;
  }
  paintInspect(designOn ? target : null, { left: r.left, top: r.top });
}
// The name of what design mode is aimed at, at the box's top-left corner — above it
// where there is room, inside it where there isn't (the banner sits at the top edge).
// Document-anchored like the box, so a scroll moves the two together between the events
// that re-derive them.
function paintInspect(target, corner) {
  inspectEl.classList.toggle("lf-shown", Boolean(target));
  if (!target) {
    delete inspectEl.dataset.lfPaintPlane;
    return;
  }
  inspectEl.dataset.lfPaintPlane = inChrome(target.el) ? "chrome" : "page";
  const name = target.part
    ? `${target.part} · ${designName(target.el)}`
    : designName(target.el);
  if (inspectEl.textContent !== name) inspectEl.textContent = name;
  const above = corner.top - inspectEl.offsetHeight - 2;
  const at = documentPoint(
    Math.max(2, corner.left),
    above >= 0 ? above : corner.top + 2,
  );
  inspectEl.style.left = `${at.left}px`;
  inspectEl.style.top = `${at.top}px`;
}
let hovering = null;
let hoverQueued = false;
const marksOf = (id) => marked.get(id) ?? [];
const allMarks = () => [...marked.values()].flat();
const elementMarks = (where) =>
  [...where].flat().filter((mark) => mark instanceof Element);
const rememberVisual = (resolved) => {
  const element = targetElement(resolved);
  const surface = targetSurface(resolved);
  if (element && surface) visualTargets.set(element, surface);
};
function paintVisualStates() {
  const comments = new Set(elementMarks(marked.values()));
  const reactions = new Set(elementMarks(reacted.values()));
  const pending = new Set(pendingOutline);
  const action = new Set(actionOutline);
  const hover = new Set(hoverParts);
  const focus = new Set(
    [...visualTargets.keys()].filter((element) =>
      element.matches(":focus-visible, .lf-focus-visible"),
    ),
  );
  const here = new Set(hereParts);
  const stateSources = [
    ["comment", comments],
    ["reaction", reactions],
    ["pending", pending],
    ["action", action],
    ["hover", hover],
    ["focus", focus],
    ["here", here],
  ];
  setTargets(
    [...visualTargets].map(([element, surface]) => ({
      element,
      surface,
      states: new Set(
        stateSources
          .filter(([, elements]) => elements.has(element))
          .map(([state]) => state),
      ),
    })),
  );
}
// What a reader who cannot see the paint is told. A highlight is glyphs, not an element, so
// it builds no accessibility node — where a <mark> wrapper was a `mark` node, the paint is
// nothing at all, and a passage carrying a comment reads exactly like one that doesn't.
// Neither relation ARIA offers brings it back on something not focusable: NVDA ignores
// aria-describedby there in browse mode and reports none of the labelling attributes on a
// bare p or div at all, VoiceOver reads it only on an interactive, image or landmark role,
// and aria-details is supported unevenly and says only that details exist. What every
// screen reader announces in every mode is text, so the fact is carried as text — one
// hidden, unselectable line inside whatever holds the mark, saying how many comments are
// on it.
//
// Coarser than the mark, and deliberately: it names the block a passage sits in rather than
// the passage, because naming the passage means wrapping it, and wrapping is what a redraw
// between a mousedown and its mouseup turns into a swallowed click. The panel still carries
// each thread's own quote. Written only where the text differs from what is already there,
// because a screen reader rebuilds its buffer on every mutation and this pass runs on every
// poll.
function noteMarks(noted) {
  for (const [holder, threadIds] of noted) {
    const note =
      holder.querySelector(`:scope > .${NOTE}`) ??
      holder.appendChild(offer("button", NOTE));
    note.lfThreads = threadIds;
    note.onclick = () => {
      const id = note.lfThreads[0];
      if (id) openPageThread(id, { focus: "thread" });
    };
    const n = threadIds.length;
    const said = `${n} comment${n === 1 ? "" : "s"}`;
    if (note.textContent !== said) note.textContent = said;
  }
  for (const note of pageQueryAll(`.${NOTE}`))
    if (!noted.has(note.parentElement)) note.remove();
}

export function paintAnchors(threads = buildThreads()) {
  if (!anchoringIsReady()) return;
  prepareVisualActions();
  for (const where of allMarks())
    if (where instanceof Element) where.classList.remove("lf-mark-el");
  for (const where of [...reacted.values()].flat())
    if (where instanceof Element) where.classList.remove("lf-react-el");
  for (const el of pendingOutline) el.classList.remove("lf-mark-el", PENDING);
  for (const el of actionOutline) el.classList.remove("lf-action-target");
  marked.clear();
  reacted.clear();
  placed.clear();
  pendingOutline = [];
  actionOutline = [];
  visualTargets.clear();

  const text = pageText(); // read once, for every anchor this pass places
  const posted = [];
  const reactions = [];
  const seats = new Map(); // block -> the reactions whose passage starts in it
  const noted = new Map(); // element -> ordered thread ids marking something inside it
  for (const t of threads) {
    if (!t.anchor) continue;
    const found = resolveAnchor(t.anchor, text);
    if (!found) continue;
    // Where the thread's passage lands in this version, recorded for every thread the
    // page still holds — the resolved ones too, which take no paint but do take a place
    // in the panel's order and keep the one they had while they fold out of it.
    placed.set(t.root.id, {
      datumElement: null,
      exact: true,
      status: "exact",
      ...found,
      target: targetElement(found) ?? found.place,
      element: found.place,
    });
    if (found.status === "outdated") continue;
    if (t.resolved) continue;
    // A reaction nobody has answered: its own paint, and no line for the note — the
    // glyph is a real control that says what it is. Answered, it is a thread and takes
    // a thread's mark below; resolved, nothing, resolve being its floor.
    if (bareReaction(t)) {
      // The seat: the block a passage starts in, entered at its start; or, for a
      // whole element, the element itself, stood before — an element may render into
      // a shadow tree or rebuild its own children, and a seat before it is level with
      // its top either way. A block inside a shadow tree is the host's, seated the
      // element's way: the document's rules do not reach in there to dress a seat.
      let at;
      let before;
      if (targetElement(found)) {
        const parts = targetParts(found);
        for (const part of parts) part.classList.add("lf-react-el");
        rememberVisual(found);
        reacted.set(t.root.id, parts);
        [at, before] = [found.place, true];
      } else {
        const segments = targetSegments(found);
        const ranges = segments.map((seg) => rangeOf([seg]));
        reacted.set(t.root.id, ranges);
        reactions.push(...ranges);
        const block = annotationAt(segments[0].node);
        const root = block?.getRootNode();
        [at, before] = root instanceof ShadowRoot ? [root.host, true] : [block, false];
      }
      // One entry per element, holding both placements: a reaction on a whole
      // paragraph and one on a passage inside it are two seats on one element.
      if (at && !inChrome(at)) {
        const held = seats.get(at) ?? { before: [], inside: [] };
        held[before ? "before" : "inside"].push(t.root);
        seats.set(at, held);
      }
      continue;
    }
    if (targetElement(found)) {
      // The boxes the element shows through, for the same reason the Ask ring hangs on
      // those: an outline needs a box, and a wrapper that generates none took its ring
      // to the document's origin and drew nothing there. The record is what the pass
      // clears, what the pointer hit-tests, and what the composer stands off, so all
      // three follow the paint by holding the parts rather than the element.
      rememberVisual(found);
      if (!t.root.drawing) {
        const parts = targetParts(found);
        for (const part of parts) part.classList.add("lf-mark-el");
        marked.set(t.root.id, parts);
      }
    } else if (!t.root.drawing) {
      const ranges = targetSegments(found).map((seg) => rangeOf([seg]));
      marked.set(t.root.id, ranges);
      posted.push(...ranges);
    }
    // Annotate every block or authored item the resolved passage crosses. A widget's
    // generated body is excluded: its editor reads that container back as user text.
    const blocks = targetElement(found)
      ? [found.place]
      : [...new Set(targetSegments(found).map((seg) => annotationAt(seg.node)))].filter(
          Boolean,
        );
    // Not inside the chrome: the line is the runtime's word inside the page's own
    // blocks, and a design comment on a runtime part is on chrome the panel already
    // reads out — an aria-hidden injected note button would be focusable content nobody
    // is told about.
    for (const holder of blocks.length ? blocks : [sectionOf(t.anchor)])
      if (holder && !inChrome(holder))
        noted.set(holder, [...(noted.get(holder) ?? []), t.root.id]);
  }

  // The composer's own passage, in the accent rather than the mark's own ink, so a draft
  // never reads as a posted comment. An element a thread already outlines keeps the posted
  // colour: there is one outline to give, and the thread's is the clickable one.
  //
  // The ⌥ aim does not wear this paint, though it is the same fact one step earlier:
  // a promise has to interrupt where an annotation may whisper, so the aim has a box
  // of its own in the chrome's layer (refreshAim, and the .lf-aim rule's account of
  // why). An open composer doesn't stand the aim down — a press while the box is up
  // moves the draft onto another target — so the two can show at once, which is the
  // true state: where the draft stands, and where the next comment would land.
  const draft =
    composerOpen && pendingAnchor ? resolveAnchor(pendingAnchor, text) : null;
  pendingPlaced = draft
    ? {
        ...draft,
        target: targetElement(draft) ?? draft.place,
        element: draft.place,
      }
    : null;
  // Where the draft's passage is, recorded the way the threads' is. An element a thread
  // already outlines belongs in the record too — it is marked, just in the posted colour
  // rather than the accent.
  const draftMarked = Boolean(draft && draft.status !== "outdated");
  pendingMarks =
    draftMarked && !pendingDrawing
      ? targetElement(draft)
        ? targetParts(draft)
        : targetSegments(draft).map((seg) => rangeOf([seg]))
      : [];
  if (draft) rememberVisual(draft);
  const pending = [];
  if (targetElement(draft)) {
    // Part by part, because a thread's outline is claimed the same way: the draft takes
    // whichever boxes are still free and leaves the rest in the posted colour. The record
    // above records the same shown parts rather than a wrapper whose rect may sit at the
    // top of the document.
    const taken = allMarks();
    for (const part of pendingMarks)
      if (!taken.includes(part)) {
        part.classList.add("lf-mark-el", PENDING);
        pendingOutline.push(part);
      }
  }
  if (targetSegments(draft).length) pending.push(...pendingMarks);

  const active = composerOpen ? null : fabAnchorAt();
  const action = active && !active.quote ? resolveAnchor(active, text) : null;
  actionOutline = targetElement(action) ? targetParts(action) : [];
  if (action) rememberVisual(action);
  for (const part of actionOutline) part.classList.add("lf-action-target");

  // The composer's echo of its own passage, decided here because here is where it is known
  // whether the page is showing that passage. Usually it is — the box opens beside the words
  // it just marked, and printing them inside it says the same sentence twice, side by side.
  // So the quote is the fallback rather than the statement: it shows where the mark can't,
  // which is where this version no longer holds the passage — a draft the user carried
  // onto a newer version, whose text survived the trip when its passage didn't. Dashed and
  // muted, the panel's detached treatment, for the same fact.
  //
  // Scrolled out of view looks like that case and is not: the passage is still there, one
  // scroll back, and the reader put it there seconds ago. A quote coming and going with the
  // scroll position would resize the box under the hands typing in it.
  //
  // Out of sight is not gone: a painted mark has no accessibility exposure at all, so the
  // quote stays in the tree as the box's description whichever way it renders. Written only
  // when it changes, because assigning textContent replaces the node even with the same
  // string, and this pass reruns whenever a comment arrives — a stranded quote is the only
  // copy of that passage left, so it is text a user may be selecting to keep.
  const label = composerOpen ? anchorLabel(pendingAnchor, pendingAbout) : "";
  if (composerQuote.textContent !== label) composerQuote.textContent = label;
  // A design comment's label stays: the outline says which element, and only the words
  // say the comment is about the layer and which control the press landed on.
  composerQuote.classList.toggle("lf-unseen", !label || (draftMarked && !pendingAbout));

  // Ranked so each reading survives the ones under it: a posted mark, the hover over it,
  // the standing comment's own mark, and the draft above all three. A higher highlight
  // supplies only the properties it states, so the standing mark under the pointer takes
  // the hover's wash and keeps its own ink. The
  // passage under the pointer answers the pointer.
  CSS.highlights.set(MARK, new Highlight(...posted));
  CSS.highlights.set(REACT, new Highlight(...reactions));
  CSS.highlights.set(
    PENDING,
    Object.assign(new Highlight(...pending), { priority: 3 }),
  );
  seatReactions(seats);
  noteMarks(noted); // and the same fact for a reader who can't see any of it
  paintStanding(false); // the ranges are new objects and the element classes were just cleared
  // The semantic thread may be unchanged while this pass replaced every Range or
  // element part that paints its hover. Rebind the projection before geometry decides
  // whether the parked pointer still indicates that thread at all.
  if (hovering || hoverThread || hoverParts.length) paintHover(hovering, false);
  paintVisualStates();
  pageShifted(); // the content moved: the hover, a held aim's promise, the legend ask again

  paintThreadQuotes();

  // A message pointing at the page — [the group](#d-channel) — travels by the
  // browser's own fragment navigation, which is already the whole feature within one
  // document: collapsed content wears hidden="until-found", so the jump fires
  // beforematch and the owning tab or settled group opens itself. Opened in a new tab
  // it is an arrival rather than a jump, and landArrival is what answers it there.
  // What the browser has no answer for is the id
  // this version hasn't got. A comment outlives the version it was written on, so
  // that happens without anyone doing anything wrong — and unmarked, the reference
  // reads live, moves nothing on the press, and leaves a fragment nobody holds in the
  // URL for the next load to honor. So it wears the same detached face a quote whose
  // passage left the page wears, asked of the same resolveAnchor, and its press is
  // taken rather than spent. aria-disabled because the title only reaches a pointer.
  for (const a of panel.querySelectorAll(MSG_REF)) {
    const id = fragmentId(a.getAttribute("href"));
    const alive = Boolean(resolveAnchor({ section: id }));
    a.classList.toggle("detached", !alive);
    if (alive) a.removeAttribute("aria-disabled");
    else a.setAttribute("aria-disabled", "true");
    a.title = alive ? `Jump to § ${id}` : `§ ${id} isn't in the version you're viewing`;
  }
}

// The margin glyphs: one contribution per target, holding a pill per reaction whose
// passage starts there, in log order. The living margin seats that contribution beside
// the same target's decisions and available actions, so adding a committed reaction
// cannot grow a second RHS row. Two reactions on one target share the contribution
// rather than stacking on one point. The pill is the reaction's own eraser — its press
// is the ordinary undo naming the event — and wears the token's glyph, the token being
// the runtime's word for what it means.
//
// Reconciled rather than rebuilt, so a pill whose press is in flight is the node the
// reader pressed; stale seats are swept the way note lines are. The seat wears lf-ui
// and data-lf-gen: an account of the passage, not words of the page, so selection,
// quote capture and the diff readings skip it. Keep the target-to-contribution record
// here rather than rediscovering it from DOM position: the shared margin owns where
// the seat lives and may move it whenever another module joins the target.
const reactionSeats = new Map();
function seatReactions(seats) {
  const kept = new Set();
  for (const [at, held] of seats) {
    const roots = [...held.before, ...held.inside];
    let record = reactionSeats.get(at);
    const changed =
      !record ||
      record.roots.length !== roots.length ||
      roots.some(
        (root, index) =>
          root.id !== record.roots[index]?.id ||
          root.token !== record.roots[index]?.token,
      );
    if (!record) {
      const seat = el("span", `lf-ui ${SEAT}`);
      seat.dataset.lfGen = "1";
      record = { seat, roots, margin: null };
      reactionSeats.set(at, record);
    }
    const { seat } = record;
    record.roots = roots;
    kept.add(at);
    // What it stands for, for anyone reading the page: the element's id where it
    // has one, the way a suggestion's row names the change it decides.
    if (at.id) seat.dataset.lfFor = at.id;
    else seat.removeAttribute("data-lf-for");
    const wanted = roots.map((root) => {
      let mark = seat.querySelector(`:scope > [data-event="${root.id}"]`);
      if (!mark) {
        const entry = registry.$reactions.tokens[root.token];
        mark = marginButton(offer("button", "lf-react-mark"), {
          key: `take-back:${root.id}`,
          glyph: entry?.glyph ?? root.token,
          label: root.token,
          role: "secondary",
          state: "settled",
        });
        mark.dataset.event = root.id;
        mark.dataset.token = root.token;
        mark.setAttribute("aria-label", `${root.token} — take it back`);
        mark.onclick = () => withdraw(root);
      }
      return mark;
    });
    for (const child of [...seat.children]) if (!wanted.includes(child)) child.remove();
    wanted.forEach((mark, i) => {
      if (seat.children[i] !== mark) seat.insertBefore(mark, seat.children[i] ?? null);
    });
    if (!record.margin)
      record.margin = registerMarginItem({
        key: "standing-reactions",
        target: at,
        controls: seat,
        items: () =>
          record.roots.map((root) => ({
            id: `reaction:${root.id}`,
            text: `Take back ${root.token}`,
            activate: () =>
              record.seat
                .querySelector(`[data-event="${CSS.escape(root.id)}"]`)
                ?.focus({ preventScroll: true }),
          })),
        side: "after",
        claim: false,
      });
    else if (changed) {
      // Anchor repainting replaces Range objects even when the standing reactions
      // have not changed. A margin update rebuilds every page-map entry, so telling
      // it about that no-op once per seat made a composed gallery spend whole frames
      // rebuilding the same map. Only the ids and tokens affect this contribution.
      record.margin.update();
    }
  }
  for (const [at, record] of reactionSeats)
    if (!kept.has(at)) {
      record.margin.unregister();
      reactionSeats.delete(at);
    }
}
// The anchor runtime's layout hook: the chrome moved, so the rows a seat hangs in
// have to be packed again. Callers do not need to know that a seat is a contribution
// to the shared target item rather than a row of its own.
//
// A layout pass repacks; it does not restate what the seats offer. Saying `update()`
// here restated them, and a margin render ends in `paintKeys`, which ends in
// `paintHere` — the frame this hook is called from. On a page carrying a standing
// reaction that closed a cycle: chrome layout, margin render, paint, chrome layout,
// a whole margin render every frame with nothing dispatched and nothing moving.
// Measured on the feature gallery, ~350ms of main thread a frame, which is also what
// made every read of that page wait on it.
export function dockSeats() {
  if (reactionSeats.size) scheduleMarginLayout();
}

// Re-resolve marks after replay or a package-owned layout replaces their derived
// elements. Both signals describe the same invalidation and share one microtask.
let anchorPaintQueued = false;
function queueAnchorPaint() {
  if (anchorPaintQueued) return;
  anchorPaintQueued = true;
  queueMicrotask(() => {
    anchorPaintQueued = false;
    renderPanel();
  });
}
document.addEventListener("lf-projection", queueAnchorPaint);
document.addEventListener("lf-layout", () => {
  geometryChanged();
  queueAnchorPaint();
});

// A reference a message makes into the page: its own Markdown link, or one a widget
// in its frozen markup writes (a lf-option's `for`). One selector, so what the paint
// above dresses and what the press below refuses are the same set.
const MSG_REF = '.lf-msg-body a[href^="#"]';
// The id a fragment names. An href holds it as the renderer percent-encoded it and
// location.hash as the browser did; the document holds it as written. A malformed
// escape ("#100%") keeps its own characters. One reading for both, because a reference
// the panel paints and a URL the page arrived at name their element the same way.
export function fragmentId(fragment) {
  const raw = fragment.slice(1);
  try {
    return decodeURIComponent(raw);
  } catch {
    return raw;
  }
}
// The only press this layer takes from the browser: a reference this version can't
// follow. Everything else — the travel, the reveal, the back button — is the
// platform's, and an exported copy keeps it by having a real href to jump through.
// Wired once the chrome is mounted (chrome.js): the panel is another owner's part.
export function mountAnchors() {
  panel.addEventListener("click", (ev) => {
    const a = ev.target.closest(MSG_REF);
    if (a && !resolveAnchor({ section: fragmentId(a.getAttribute("href")) }))
      ev.preventDefault();
  });
}

// Which thread's mark is under a point. A painted range is not an element, so the pointer
// finds it by the boxes the range occupies rather than by hit-testing the DOM — asking for
// the caret position instead would claim the empty space past the end of a short line.
export function markAt(x, y) {
  const over = document.elementFromPoint(x, y);
  if (!pageWords(over)) return null;
  // The retargeted element answers the chrome question, whose subject is which layer the
  // pointer is in; an element mark needs the tree's own answer, because a host contains
  // every mark staged inside it and so tells none of them apart.
  const deep = elementFromPointAcross(x, y);
  for (const [id, marks] of marked)
    for (const where of marks) {
      const hit =
        where instanceof Range
          ? [...where.getClientRects()].some(
              (r) => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom,
            )
          : containsAcross(where, deep);
      if (hit) return id;
    }
  return null;
}

// Bring an element in the document to the position its caller names. A thread's element
// anchor takes the middle; an Ask takes the readable start so its context comes before
// its control. Which box does the travelling is scrollerFor's answer, asked here rather
// than assumed: the document's scroller was written into this twice, so an element
// standing in the panel's list was taken into view by the platform and then had this
// travel spent on the page behind it, moving a reader who had asked for nothing there.
// Reveal first, since opening a tab or settled group moves
// everything below it. For a centred destination, "the middle" means the viewport's:
// scrollIntoView measures against the scroller's own
// scroll-padding-top — declared so a native fragment jump clears the banner — and every
// "center" through it therefore landed 27px low. An element taller than the viewport has
// no middle to show, and centring one puts its opening words above the top edge, so it
// takes that same banner clearance instead and the reader starts at the start.
//
// The viewport is the scroller's own box: the browser viewport for the root, and the
// panel's list where that is what scrolls.
//
// It glides, because a page the reader is already holding is one the motion keeps their
// place in — the same reason a restore doesn't (moveScrollerBy). An arrival passes
// "instant" for
// exactly that reason: a document that appeared a moment ago holds no place to keep, so
// the glide would be animating from nowhere.
function centreBy(where, block = "center", box = pageScroller) {
  const rect = where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
  // The scroller's own box: the viewport for the document root, and the list's own where
  // the list is what scrolls.
  const view = shownBox(box);
  const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
  const place =
    where instanceof Range
      ? (view.height - rect.height) / 2
      : block === "start"
        ? clear
        : Math.max((view.height - rect.height) / 2, clear);
  return rect.top - view.top - place;
}
export function scrollToElement(el, behavior = scrollBehavior(), block = "center") {
  reveal(el);
  el.scrollIntoView({
    block: "nearest",
    inline: "nearest",
    behavior: block === "nearest" ? behavior : "instant",
  });
  // `nearest` is a request to reveal only. Once the platform has done that, a
  // second centring move would turn a small correction into a page jump.
  if (block === "nearest") return;
  const box = scrollerFor(el);
  if (!under(el, box)) return;
  moveScrollerBy(box, centreBy(el, block, box), behavior);
}

// A destination already fully visible in its own scroller needs no travel. Compare its
// unclipped geometry with what every clipping ancestor actually exposes; an element can
// be in the viewport while still hidden behind a nested scroller edge.
//
// Named for the question rather than for a caller: the ask walk asks it of a decision
// before deciding whether to travel, exactly as thread travel asks it of a passage. A
// second copy of it went out with three of these four edges missing, which is a
// difference nothing on the page would have shown — a half-cut card reads as readable
// when only its foot is compared.
export function readableDestination(where) {
  const holder =
    where instanceof Range
      ? where.startContainer instanceof Element
        ? where.startContainer
        : where.startContainer.parentElement
      : where;
  if (!holder) return false;
  const destination =
    where instanceof Range ? where.getBoundingClientRect() : shownBox(where);
  const seen =
    where instanceof Range
      ? clippedRect(destination, holder, new Map())
      : shownRect(where, new Map());
  if (!seen) return false;
  const box = scrollerFor(holder);
  const view = shownBox(box);
  const clear = parseFloat(getComputedStyle(box).scrollPaddingTop) || 0;
  const close = (a, b) => Math.abs(a - b) <= 0.5;
  return (
    destination.top >= view.top + clear - 0.5 &&
    destination.bottom <= view.bottom + 0.5 &&
    close(seen.top, destination.top) &&
    close(seen.right, destination.right) &&
    close(seen.bottom, destination.bottom) &&
    close(seen.left, destination.left)
  );
}

export function scrollToRange(where, behavior = scrollBehavior()) {
  const holder =
    where.startContainer instanceof Element
      ? where.startContainer
      : where.startContainer.parentElement;
  if (!holder) return;
  reveal(holder);
  // Reveal every nested scrollport here, but stop before the document's. Using
  // `scrollIntoView` as the prelude to the centred page trip wrote that last box too:
  // it jumped the document to the holder's nearest edge, then glided it somewhere
  // else. A range inside a clipped widget or wide pre still needs both local axes
  // revealed before its final box can be read.
  for (
    let box = holder;
    box && box !== pageScroller;
    box = box.assignedSlot ?? parentAcross(box)
  ) {
    if (box.scrollWidth <= box.clientWidth && box.scrollHeight <= box.clientHeight)
      continue;
    const band = shownBand(box);
    if (!band) continue;
    const style = getComputedStyle(box);
    const left = band.left + (parseFloat(style.scrollPaddingLeft) || 0);
    const right = band.right - (parseFloat(style.scrollPaddingRight) || 0);
    const top = band.top + (parseFloat(style.scrollPaddingTop) || 0);
    const bottom = band.bottom - (parseFloat(style.scrollPaddingBottom) || 0);
    const destination = where.getBoundingClientRect();
    let byX = 0;
    if (destination.left < left && destination.right <= right)
      byX = destination.left - left;
    else if (destination.right > right && destination.left >= left)
      byX = destination.right - right;
    let byY = 0;
    if (destination.top < top && destination.bottom <= bottom)
      byY = destination.top - top;
    else if (destination.bottom > bottom && destination.top >= top)
      byY = destination.bottom - bottom;
    if (byX || byY) box.scrollBy({ left: byX, top: byY, behavior: "instant" });
  }
  moveScrollerBy(pageScroller, centreBy(where), behavior);
}

// Move to where a thread is painted, if it still is — asked of the pass's own record, so the
// panel and the page can't disagree about whether the passage survived. A painted range has
// no element to scroll into view, so its own box does the work.
//
// Hydration may outlive the gesture that requested it. A newer gesture or thread
// destination withdraws its pending scroll and focus, while the data still loads.
let threadTravelIntent = 0;
const leaveThreadTravel = () => threadTravelIntent++;
for (const type of ["pointerdown", "keydown", "input", "wheel"])
  addEventListener(type, leaveThreadTravel, { capture: true, passive: true });
addEventListener("blur", leaveThreadTravel);

// Reveal and reconcile before the caller's focus landing: a widget outlet may not
// exist until its file opens. Focus lands before scrolling so it cannot cancel the
// passage's normal travel. Completion means the destination exists, not that a smooth
// scroll animation has finished.
export async function scrollToThread(id, { land = null } = {}) {
  const intent = ++threadTravelIntent;
  const startingFocus = focused();
  const thread = buildThreads().find((candidate) => candidate.root.id === id);
  const anchor = thread?.anchor;
  if (anchor?.datum && placed.get(id)?.status !== "outdated") {
    const source = sectionOf(anchor);
    // The line may already exist under a widget-owned filter. Core asks the owner to
    // reveal the semantic key before it reads the painted mark, just as cross-widget
    // datum travel does; DOM presence alone cannot prove reachability.
    const hydration = source?.lfRevealDatum?.(anchor.datum);
    if (hydration?.then) {
      await hydration;
      if (
        intent !== threadTravelIntent ||
        sectionOf(anchor) !== source ||
        (focused() !== startingFocus && focused() !== document.body)
      )
        return false;
      renderPanel();
    }
  }
  let where = marksOf(id)[0] ?? placed.get(id)?.element;
  if (!where) return false;
  const holder =
    where instanceof Range
      ? where.startContainer instanceof Element
        ? where.startContainer
        : where.startContainer.parentElement
      : where;
  if (!holder) return false;
  reveal(holder);
  if (anchor?.datum || (!(where instanceof Range) && !marksOf(id).length)) {
    renderPanel();
    where = marksOf(id)[0] ?? placed.get(id)?.element ?? where;
  }
  land?.();
  if (readableDestination(where)) return true;
  if (!(where instanceof Range)) {
    scrollToElement(where);
    return true;
  }
  // Sideways first, and only as far as it takes: a passage inside a wide `pre` or a
  // rendered diagram sits in a box with its own horizontal scroll, which the vertical
  // jump below cannot reach — scrolling to it in one axis leaves it off-screen in the other.
  scrollToRange(where);
  return true;
}

// Pointer feedback a wrapped <mark> got from :hover and cursor: pointer, neither of which
// ::highlight() can carry — it styles glyphs, not boxes. Same hit-test as the click, so
// what lights up is what would open. It is a function of where the pointer is and what the
// page's geometry is, so everything that moves either asks again: the pointer moving, the
// page scrolling under a still pointer, and the pass redrawing the ranges themselves.
//
// The pointer can indicate a thread from either surface, and the panel is the other one.
// A card is the thread's view in the list the way a mark is its view in the prose, so
// resting on the card lights the passage exactly as resting on the passage lights its
// bounded quote — the same wash, because it is the same fact, and a second strength
// would be a third thing to learn on a page that already asks the reader to tell a mark
// from a standing mark. It answers the question a reader scanning a full list keeps
// asking, which of these is about what, without a press and without a travel they may
// not want; the standing mark answers it for the one comment they chose, and this
// answers it for the one under their hand.
//
// One answer rather than two, because the pointer is in one place: markAt refuses a point
// that lands in the chrome, so the panel's reading and the page's cannot both name a
// thread. That is also why the two are read here rather than painted by separate hands —
// a second writer to this highlight would be overwritten by whichever frame ran last, and
// the hit-test runs on every pointer move.
//
// The semantic id stays on the card; paint can then name the bounded quote representing
// its passage instead of washing an arbitrarily long conversation.
const HOVER = "lf-mark-hover";
const hoveredThreadOf = () => threadsBox.querySelector(".lf-thread:hover");
let hoverParts = [];
let hoverThread = null;
const hoverCardOf = (id) =>
  id ? threadsBox.querySelector(`:scope > .lf-thread[data-id="${id}"]`) : null;
function paintHover(id, repaintVisuals = true) {
  hovering = id;
  // The page and panel are reciprocal views of the thread. The highlight paints the
  // passage when the pointer is on its card; this class paints the card's quote when the
  // pointer is on its passage. One writer keeps them on the same id, and keeping the node
  // lets a sweep touch only the two cards whose answer changed.
  const thread = hoverCardOf(id);
  if (hoverThread !== thread) {
    hoverThread?.classList.remove(HOVER);
    thread?.classList.add(HOVER);
    hoverThread = thread;
  }
  const where = marksOf(id);
  // Both kinds of anchor, for the reason paintStanding takes both: one question about one
  // thread, and a reading that answered only the passages with words left an element
  // anchor saying nothing back. Only what changed, and guarded on each side, for the
  // reason spelled out there — this runs on every frame of a pointer sweep.
  const parts = where.filter((mark) => mark instanceof Element);
  for (const part of hoverParts)
    if (!parts.includes(part)) part.classList.remove(HOVER);
  for (const part of parts)
    if (!part.classList.contains(HOVER)) part.classList.add(HOVER);
  hoverParts = parts;
  CSS.highlights.set(
    HOVER,
    Object.assign(new Highlight(...where.filter((mark) => mark instanceof Range)), {
      priority: 1,
    }),
  );
  if (repaintVisuals) paintVisualStates();
}
// Which comment the reader is standing in, said out on the page. The conversation card
// answers it on its own surface — the thread holds the focus, and a press on a mark
// flashes the bounded target it opens — while the page answered nothing back: every
// posted mark wears one wash, so a reader sent from a comment to its passage arrived
// among a dozen identical marks with no way to tell which one they had asked to see.
// The thread surface and the page are two views of the same thread; this is the view that
// was missing.
//
// Derived from the focus rather than written where the travel put the reader, for the
// reason markHere gives about the decision ring: a mark written at the arrival says where the
// reader was *sent*, and goes on saying it after they have clicked away, read on down the
// page and come back tomorrow. Every way into a thread then paints it — the quote's press,
// t/T, a plain click on the card — because they all end in the same focus, and no
// way in has to be taught to paint.
//
// Read through `closest` rather than off the thread itself, so a reader typing a reply is
// still standing in the comment they are replying to; that is exactly when knowing which
// passage it is on is worth most.
//
// Above the hover and below the draft. A pointer resting on the standing mark supplies
// the middle wash, while this higher paint keeps the strongest wash and its accent ink:
// the cursor promises the press, and the ink answers "which one".
const HERE = "lf-mark-here";
let hereParts = [];
export function paintStanding(repaintVisuals = true) {
  const localThread = focused()?.closest(".lf-conversation-thread");
  const where = marksOf(localThread?.dataset.thread ?? focusedThreadOf()?.dataset.id);
  const parts = where.filter((mark) => mark instanceof Element);
  // Only what changed, because the anchor pass calls this and the anchor pass runs on
  // every poll: an element that keeps the class would otherwise have it taken off and put
  // straight back, writing the page's own attribute twice a poll for as long as the
  // reader stands there, and a mutation on an authored element is something this page's
  // observers hear. Both sides are guarded, because Chrome records a mutation for a
  // classList.add of a token already in the list — the same reason noteMarks writes its
  // line only when the words differ.
  for (const part of hereParts) if (!parts.includes(part)) part.classList.remove(HERE);
  for (const part of parts)
    if (!part.classList.contains(HERE)) part.classList.add(HERE);
  hereParts = parts;
  CSS.highlights.set(
    HERE,
    Object.assign(new Highlight(...where.filter((mark) => mark instanceof Range)), {
      priority: 2,
    }),
  );
  if (repaintVisuals) paintVisualStates();
}
// Coalesced to a frame: scroll outruns layout, the hit-test reads layout, and a repaint
// asks from inside a pass that must stay cheap enough to run from a mousedown. The frame
// is what settles the panel's half too — that reading is the browser's own :hover state,
// and asking for it from inside the pointer event that is moving it asks mid-move.
export function refreshHover() {
  if (hoverQueued || (!marked.size && !hovering && !hoverThread)) return;
  hoverQueued = true;
  requestAnimationFrame(() => {
    hoverQueued = false;
    // The cursor stays with the page's own reading. It is the promise that a press here
    // opens something, and over a card the press on offer is the card's own — which the
    // panel already says for itself, on the quote that makes it. Unconditional because
    // toggle runs no update step when the answer has not changed, unlike the add that
    // noteMarks and the standing paint have to guard.
    const pointer = pointerAt();
    const onMark = markAt(pointer.x, pointer.y);
    document.body.classList.toggle("lf-over-mark", Boolean(onMark));
    const id = hoveredThreadOf()?.dataset.id ?? onMark;
    // A reconcile normally keeps a thread node, but settlement replaces it. If the
    // pointer stayed over the same semantic thread, repaint the reciprocal class onto
    // that new card even though the id did not change.
    if (id !== hovering || hoverCardOf(id) !== hoverThread) paintHover(id);
  });
}
// The shared pointer recorder is installed before this listener, so the hover reads the
// same unrounded point the browser used for the event's hit test.
document.addEventListener("pointermove", refreshHover);
// The page moving under a parked pointer is the pointer moving over the page: what a
// press would take, whether a mark is under the hand, and where every legend box
// stands can all change with no mouse event to say so, and a box left over the old
// item promises a press the click no longer makes. One repaint set for every door
// that says so — a scroll, a window resize, a replay's marks landing (paintAnchors),
// a widget's FLIP settling, and the reflows only the legend's observers hear, the
// panel opening re-centring the column among them.
let actionFrame = 0;
function queueActionPlacement() {
  if (actionFrame) return;
  actionFrame = requestAnimationFrame(() => {
    actionFrame = 0;
    refreshFab();
  });
}
export function pageShifted() {
  refreshHover();
  refreshAim();
  shifted();
  drawingShifted();
  // A board scrolled sideways carries its cards out from under their boxes, and the
  // page scrolled brings items into view that had no box yet (shownRect).
  queueLegend();
  if (fabAnchorAt()) queueActionPlacement();
}
// At the document and at capture, because scroll does not bubble and the root is not the
// page's only scroller: a board scrolls its columns sideways, and a card carried under a
// parked pointer that way is the same fact as the page scrolling under it. Capture is
// the one place every scroller's event passes.
document.addEventListener("scroll", pageShifted, { capture: true, passive: true });
addEventListener(
  "resize",
  () => {
    geometryChanged();
    pageShifted();
  },
  { passive: true },
);

export const isMarked = (id) => marked.has(id);
export function pendingAt() {
  return pendingPlaced;
}
export const placedAt = (id) => placed.get(id);
export const traceTarget = (target) => {
  const part = target ? visualAt(target, { unclaimed: false })?.part : null;
  paintTrace(target, part?.element === target ? part.surface : target);
};
