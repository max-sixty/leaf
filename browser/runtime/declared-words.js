/* The runtime paint projected onto page-owned elements and words: the layer-owned
   defaults that declarations make possible, the words the runtime materializes or
   clips for a user, and the mark an external link wears.

   If registry declarations and the log contain enough information to implement a
   behavior, the layer implements it once. Current examples are:

   - `renderSaid` turns `x-says` values into real selectable text.
   - `renderQuiet` gives state provenance a clipped spoken reading.
   - Declared marks expose the width model, inline run, quoting, own height, and
     reading role to the theme: delivery paints a page's document, and `markDeclared`
     a message.
   - `paintSettlements` (projection/presentation.js) paints every holder's
     authoritative settlement, whether or not its module renders anything.
   - `renderRetired` marks slots retired by the declared holder relation.
   - The obligation model (obligations/model.js) reads `x-awaits`, while the obligation view (obligations/view.js)
     projects the enclosing widget (`x-encloses`) around that source where one exists;
     neither names a tag.
   - the internal validation adapter exposes replay winners to the render gate,
     the panel's own folds included: a widget an agent sent folds the way a page widget
     does and the poll replays it the same way, so the premise that every widget's `render()`
     is absolute binds it too.

   A module owns only its choreography and semantics that no declaration can express. For
   example, a suggestion module may animate its slots and write the visible deletion and
   insertion words. It does not own the general meaning of a settled holder.

   `renderSaid` materializes words that CSS would otherwise paint through `content:
   attr(...)`. A visible word must exist in a text node if the user can point at it.
   Module-generated words that cannot be declared by attribute are inserted at the
   correct edge and marked `data-lf-gen`. Do not place a generated suffix after a control
   that semantically ends the row.

   The two edges are not mirror images. `after` goes inside the element's own words,
   because trailing chrome stands beside the last of them and a span past it lands on the
   far side of the apparatus. `before` goes at the element's start, because leading
   chrome is not something the words stand beside: a module puts one there to speak for
   the whole element, and stepping past it renders the element's own opening words
   underneath a summary of them.

   `renderQuiet` handles facts with no local words, such as the provenance of projected
   widget state. These words are clipped, unselectable, excluded from clipboard and
   anchor readings, but available to assistive technology. `quietFacts` derives them
   from the runtime's provenance attributes.

   The runtime may inject its own words inside a widget: a quiet word, or an attribute
   the registry says aloud. A module reading its slot or body must call `says` so
   runtime words do not become authored or user content. */

import { elementDeclarations, exhibits, registry, tagsDeclaring } from "./registry.js";
import { watchArrivals } from "./arrivals.js";
import { highlightBlocks } from "./syntax.js";
import { keeps } from "./keeps.js";
import { move } from "./dom-move.js";
import { PAGE_PAINT_ATTRIBUTE } from "./page-paint.js";
import { marks } from "./kernel-facts.js";
import { generatedElement } from "./widget-elements.js";

const PAGE_PAINT_ATTRIBUTES = new Set(Object.values(PAGE_PAINT_ATTRIBUTE));
// Whether an attribute on the page's own element is paint rather than the author's: the
// runtime's, or a declared mark, which delivery paints into the served document and
// `markDeclared` into a message. A reading of the author's attributes on the live DOM
// (`shallowSigs`) looks past it, since paint is no change the author made.
export const isPagePaint = (name) =>
  PAGE_PAINT_ATTRIBUTES.has(name) ||
  Object.values(marks).some((mark) => mark.paint === name);

// A word for a user listening, silent on screen: real text — the one thing every
// screen reader announces in every mode — placed after the element's leading title,
// wearing .lf-ui (an invisible word is apparatus the anchor pass must not offer),
// .lf-quiet (the shared clip), and data-lf-gen (no author wrote it). One writer per
// element, and the empty word removes what stands: a fact the page has stopped painting
// must stop being said too, so a caller states the whole of what this element says
// quietly and never appends to it. Content widgets once hand-copied this idiom
// before it was one, and the copies had already diverged on whether a stale word was
// removed first — which is now renderQuiet's to state for every widget that declares it.
//
// Which writer an element gets follows from what paints it, and the two sets do not
// meet: renderQuiet has the elements the runtime paints a provenance on, and a module
// has only the parts it builds — a suggestion's two slots, a code line. Two writers on
// one element would each remove the other's word on every state application, which the
// user would hear as the element re-reading itself.
function quietWord(el, word) {
  const title = el.querySelector(":scope > strong");
  const seat = title ? title.nextSibling : el.firstChild;
  const existing = el.querySelector(":scope > .lf-quiet");
  if (existing) {
    // Nothing to say that isn't already said, in the place it belongs: a screen
    // reader rebuilds its buffer from the mutations, so a pass that finds the page
    // as it left it re-reads the element to whoever is on it for no reason. The seat
    // is part of that — a module that rebuilds its chip row between two runs of this
    // leaves the word behind it, and the fix is to move it, not to leave it
    // where the rebuild happened to put it.
    if (existing === seat && existing.textContent === word) return;
    existing.remove();
  }
  if (!word) return;
  const span = Object.assign(document.createElement("span"), {
    className: "lf-ui lf-quiet",
    textContent: word,
  });
  generatedElement(span, { says: false });
  move(el, span, title ? title.nextSibling : el.firstChild);
}

// The quiet word a module declares on a part it builds, as `data-lf-quiet`, such as a
// code line's "highlighted" or a suggestion slot's "proposed deletion": Leaf writes it
// there while the part stands and declares it. Declared rather than written by the
// module, because the word is only quiet where Leaf's theme clips it, so a widget that
// also runs off Leaf (portable-api.js) must not write it there, and on a page without
// Leaf nothing reads the declaration.
export function watchQuietWords() {
  const { quiet } = PAGE_PAINT_ATTRIBUTE;
  watchArrivals(`[${quiet}]`, [quiet], {
    arrive: (el) => quietWord(el, el.getAttribute(quiet)),
    leave: (el) => quietWord(el, ""),
  });
}

// Parser paint and later arrivals share one treatment and its per-link ownership.
// Prepaint seats the mark before authored prose first paints; this watch carries the
// same owner through revisions, generated content and declared shadow stages.
const EXTERNAL_LINK_ATTRIBUTES = ["target", "rel", "aria-describedby"];
const externalLinkState = new WeakMap();
let externalDescriptionSequence = 0;
const externalDescriptions = new WeakMap();
export const opensElsewhere = (href) =>
  document.documentElement.lfLinks.opensElsewhere(href);
export const isExternalPageLink = (link) =>
  link instanceof HTMLAnchorElement && opensElsewhere(link.getAttribute("href"));
export function externalMark() {
  return Object.assign(document.createElement("span"), {
    className: "lf-ui lf-external-mark",
    ariaHidden: "true",
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
// The text field draws the same mark after a link it shows (composing/text-field.js).
const linkAttributes = (link) =>
  Object.fromEntries(
    EXTERNAL_LINK_ATTRIBUTES.map((name) => [name, link.getAttribute(name)]),
  );
const tokens = (value) => value?.split(/\s+/).filter(Boolean) ?? [];
function withToken(value, token, insensitive = false) {
  const values = tokens(value);
  const wanted = insensitive ? token.toLowerCase() : token;
  if (!values.some((value) => (insensitive ? value.toLowerCase() : value) === wanted))
    values.push(token);
  return values.join(" ");
}
function withoutToken(value, token, insensitive = false) {
  if (value === null) return null;
  const unwanted = insensitive ? token.toLowerCase() : token;
  return tokens(value)
    .filter((value) => (insensitive ? value.toLowerCase() : value) !== unwanted)
    .join(" ");
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
    if (name === "rel" && state.addedNoopener)
      value = withoutToken(value, "noopener", true);
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
  // SVG links share this selector but not the HTML anchor API, and they have no
  // dependable inline box in which an HTML text mark could stand.
  if (!(link instanceof HTMLAnchorElement)) return;
  document.documentElement.lfLinks.markExternalLink(link);
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
      addedNoopener: false,
    };
    externalLinkState.set(link, state);
  } else rememberExternalLinkChanges(link, state);
  state.markId = externalDescription(link);
  state.addedNoopener = !tokens(state.baseline.rel).some(
    (value) => value.toLowerCase() === "noopener",
  );
  writeLinkAttributes(link, {
    target: "_blank",
    rel: withToken(state.baseline.rel, "noopener", true),
    "aria-describedby": withToken(state.baseline["aria-describedby"], state.markId),
  });
  state.painted = linkAttributes(link);
}

export function watchExternalLinks() {
  watchArrivals("a", ["href", ...EXTERNAL_LINK_ATTRIBUTES], {
    arrive: renderExternalLink,
    leave: leaveExternalLink,
  });
}

// What an upgraded subtree owes beyond its module's own work: the words a widget says
// through an attribute rendered as real text, the facts it paints spoken, and its
// code — and the page's own <pre><code> blocks, alongside the widgets and for the same
// reason: the tokenizer is vendored, so a page has it exactly when it has a widget
// layer at all. Written once because it happens twice, over the page at the upgrade and
// over each root a live revision brings into it, and a near-copy of it would go stale
// the day the vocabulary grows a fourth pass. A link's treatment is not among them: it
// is the link's for as long as it stands, whoever rendered it (`watchExternalLinks`).
export function paintDeclaredWords(root) {
  renderSaid(root);
  renderQuiet(root);
  return highlightBlocks(root);
}

// The declarations a stylesheet has to read and cannot. Three of them first: one about
// the space a widget is given and two about how it participates in content, and none of
// them is something a selector can derive from the element in hand or look up.
//
// Which widgets may stand wider than the column is the first. Prose is set to a measure
// and stays at it; a board's columns and a diagram's graph are as wide as what they hold,
// and a page carrying one had to be either a cramped board or a page whose every
// paragraph was widened to suit it. Neither is a choice a page should have to make, so
// the widget declares its capacity (x-space) and the theme spends the room the layout
// resolved by the CSS shell (--lf-room): `wide` uses the shared evidence cap, and
// `available` uses all remaining room.
// Internal arrangement remains package-owned.
//
// Whether the widget is set among the words around it is the second (x-inline). What
// reads it is the pair of selectors asking whether a suggestion slot or a variant holds
// block content, which is HTML's phrasing content inverted: a custom element is in no
// closed platform set, so any widget in one of those makes it a block — an inline widget
// included, which is the one wrong answer the inversion gives. The exclusion that fixed
// it was four widget names, and a bundled chip's tag therefore stood in the integrated
// theme, saying nothing at all about the next layer's inline widget. It is one marker
// now, data-lf-inline, and an inline widget from any layer joins by declaring.
//
// Whether the widget quotes what it holds is the third (x-exhibit). An exhibit is a
// mention, not a use, so every rule saying "this takes input" — the hand, the lift, the
// joined shape, the reserved strips, the hover wash — stands down inside one. The
// declaration is the tag's and the question is the occurrence's, which is the shape
// quoted() has too: whether this element sits inside an exhibit. So the mark goes on the
// exhibit and the rules exclude what stands under it, strictly within, as quoted()
// does: the exhibit itself is no mention. Ten of those rules spelled lf-sample before: a bundled
// tag, saying nothing about a project's own exhibit. quoted() still asks the registry
// rather than this paint, which is the arrangement and not an oversight — the
// declaration is the one representation, and the mark is how a stylesheet, which cannot
// read a registry, asks it the same thing.
//
// Two more complete the set: x-bound, a block that holds its own height and scrolls
// inside it (`bounds.js` holds each bounded block that arrives as a reading region, and
// keeps an `end` bound on its newest entry), and x-reading-role, the structure the theme
// and the workspace Layout lay out, so every package's pane takes the same rules.
//
// An attribute, because the theme cannot read the registry — the same arrangement x-says
// already has with data-lf-said. Which declarations are marks, the attribute each is
// painted as, the attribute an occurrence overrides it with, and whether it holds in a
// message are one table, the kernel registry's `$marks`, which this runtime imports from
// `kernel-facts.js`. A page's document arrives painted from it: delivery writes
// the marks into the served source (revision_delivery.py, `mark_declared`), so the first
// paint already gives a board its room and a workspace its panes, before any module or
// the registry loads, and a revision the page patches in arrives painted the same way. A
// message is the runtime's to render, so `markDeclared` paints it from `marks` as it
// renders, with the marks that hold there: every one but the room, which is the
// document's to hand out, while a message renders in the panel's.

function* elementsIn(root, selector) {
  if (root.matches?.(selector)) yield root;
  yield* root.querySelectorAll(selector);
}

// Paint a message's declared marks, the root alongside its descendants: each tag's
// declaration, and an occurrence's authored override over it.
export function markDeclared(root) {
  for (const [key, mark] of Object.entries(marks)) {
    const { paint, authored, message } = mark;
    if (!message) continue;
    const tags = tagsDeclaring((entry) => entry[key]);
    for (const tag of tags) {
      const declared = registry[tag][key];
      for (const el of elementsIn(root, tag)) {
        const value = key === "x-exhibit" ? exhibits(el, registry[tag]) : declared;
        if (key === "x-views") {
          keeps(el, paint, declared.parts ? "parts" : "");
          for (const child of el.children)
            child.toggleAttribute(
              "data-lf-view",
              !child.hasAttribute("data-lf-gen") && child.matches(declared.members),
            );
          continue;
        }
        keeps(el, paint, !value ? null : value === true || mark.presence ? "" : value);
      }
    }
    // Message markup is all content (`authored_on`, `$marks`), so only a
    // mark held to declaring tags asks which tag an occurrence is.
    if (authored)
      for (const el of elementsIn(root, `[${authored}]`))
        if (mark.authored_on !== "declared" || tags.includes(el.localName))
          keeps(el, paint, el.getAttribute(authored));
  }
}

// Words a widget says through an attribute — a metric's number, a chronology entry's time, an
// option's chip band — rendered as text the user can reach. The theme renders the same
// words with `content: attr()`, and a pseudo-element's glyphs are in no text node: no
// selection can cover them, so no comment can be anchored on them, and the page shows
// text you can read and can't point at. Not the widget author's to remember, either: the
// registry names the attributes (x-says) and one pass renders them, so a widget cannot
// render a word the user can't quote.
//
// Each value goes at the edge its pseudo-element occupied (before = first child, after =
// last) — the only placement a pseudo could ever have had, and so the line past which a
// widget writes its own (a dashboard's labels may form a list mid-element;
// lf-column's heading is its list's accessible name, which this pass knows nothing
// about). Those write the same data-lf-said span, and the guard below means the two
// compose rather than race. The pass runs after the upgrades, so a module that rebuilds
// its own body can't wipe a span put there first.
//
// The theme's pseudo rules stay as the no-script fallback; they stand down where this
// pass has been, asked by :has(), so the two are never both on. The span is data-lf-gen
// and not .lf-ui: no source holds it, so the authored reading leaves it out, and the
// user must be able to quote it.
//
// data-lf-said names the attribute here and stands bare on a label generatedElement
// wrote, because the two are one claim — these words are the page's, whoever rendered
// them. The anchor pass reads the marker alone; the value is for whoever means one
// attribute in particular, which is this pass (so it writes no second span over its
// own) and the theme, whose every rule names the attribute it styles rather than
// matching the bare marker.
export function renderSaid(root) {
  for (const [tag, entry] of elementDeclarations()) {
    if (!entry["x-says"]) continue;
    for (const el of elementsIn(root, tag))
      for (const [attr, edge] of Object.entries(entry["x-says"])) {
        const text = el.getAttribute(attr);
        const existing = el.querySelector(`:scope > [data-lf-said="${attr}"]`);
        // A live revision may change or drop the attribute under a span already
        // standing for it; the span follows the attribute rather than the first word
        // it ever said.
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
        // The two edges are not mirror images, because the chrome at them is not the same
        // kind of thing.
        //
        // After: inside the element's own words rather than past them. Trailing chrome
        // stands *beside* the last of them and runs to the line's end, so a span placed
        // at the element's true end lands on the far side of it — an option's risk chip
        // came out past the pick mark that ends a compact row, and on the far side of it
        // from where the file's reading of that same version has it.
        //
        // Before: the element's own start. Leading chrome is not something the words
        // stand beside; a module puts it there to speak *for* the whole element, so an
        // authored attribute declared at this edge must precede it.
        //
        // Each edge skips what the other keeps, which is the whole of the difference:
        // trailing chrome is passed over by looking for the last authored node, leading
        // chrome by looking for the first node this pass has not already written. The
        // second reading also settles the order of two attributes declared at this edge,
        // though no shipped declaration names two.
        const pastTrailingChrome = [...el.childNodes].filter(
          (n) => !(n.nodeType === 1 && n.dataset.lfGen),
        );
        const beforeLeadingChrome = [...el.childNodes].find(
          (n) => !(n.nodeType === 1 && n.dataset.lfSaid),
        );
        move(
          el,
          span,
          (edge === "before"
            ? beforeLeadingChrome
            : pastTrailingChrome.at(-1)?.nextSibling) ?? null,
        );
      }
  }
}

// What a widget states without local words: the runtime's three provenance states, a
// fact the eye reads off paint alone. Page Map makes them visible and navigable in a
// live page, while this quiet word keeps each one attached to its target for assistive
// technology.
// They compose into the element's one quiet span, so independent verbs can name user,
// report, and restatement origins without three writers fighting over the same seat.
function quietFacts(el) {
  const words = el.hasAttribute(PAGE_PAINT_ATTRIBUTE.restated)
    ? ["rewritten since the decision"]
    : [];
  if (el.hasAttribute(PAGE_PAINT_ATTRIBUTE.userOverride)) words.push("my change");
  if (el.hasAttribute(PAGE_PAINT_ATTRIBUTE.reported)) words.push("reported state");
  return words.join(", ");
}

/** @param {Element} root @param {Iterable<Element>} [also] */
export function renderQuiet(root, also = []) {
  const painting = [
    `[${PAGE_PAINT_ATTRIBUTE.restated}]`,
    `[${PAGE_PAINT_ATTRIBUTE.userOverride}]`,
    `[${PAGE_PAINT_ATTRIBUTE.reported}]`,
  ].join(", ");
  const targets = new Set(elementsIn(root, painting));
  for (const el of also) if (el === root || root.contains(el)) targets.add(el);
  for (const el of targets) quietWord(el, quietFacts(el));
}
