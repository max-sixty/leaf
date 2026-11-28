/* The runtime paint projected onto page-owned elements and words: the layer-owned
   defaults that declarations make possible, the words the runtime clips for a user,
   and the mark an external link wears.

   If registry declarations and the log contain enough information to implement a
   behavior, the layer implements it once. Current examples are:

   - `renderQuiet` gives state provenance a clipped spoken reading.
   - Declared marks expose the width model, inline run, quoting, own height, and
     reading role to the theme, and a reading role's ARIA role and name to assistive
     technology: delivery paints a page's document, and `markDeclared` a message.
   - `watchPanes` marks each pane's body as its reading region.
   - `paintSettlements` (projection/presentation.js) paints every holder's
     authoritative settlement, whether or not its module renders anything.
   - `renderRetired` marks slots retired by the declared holder relation.
   - The obligation model (obligations/model.js) reads `awaits`, while the obligation
     view (obligations/view.js) starts an arrival at the group the author declares
     round that source where one does; neither names a tag.
   - the internal validation adapter exposes replay winners to the render gate,
     the panel's own folds included: a widget an agent sent folds the way a page widget
     does and the poll replays it the same way, so the premise that every widget's `render()`
     is absolute binds it too.

   A module owns only its choreography and semantics that no declaration can express. For
   example, a suggestion module may animate its slots and write the visible deletion and
   insertion words. It does not own the general meaning of a settled holder.

   `renderQuiet` handles facts with no local words, such as the provenance of projected
   widget state. These words are clipped, unselectable, excluded from clipboard and
   anchor readings, but available to assistive technology. `quietFacts` derives them
   from the runtime's provenance attributes.

   The runtime may inject its own words inside a widget, such as a quiet word. A module
   reading its slot or body must call `says` so runtime words do not become authored or
   user content. */
import { isElement } from "../lib/shadow-tree.js";

import { markViews } from "./views.js";
import { holdsFor, registry, tagsDeclaring } from "../state/registry.js";
import { watchArrivals } from "../dom/arrivals.js";
import { dressCode } from "../readings/code-dressing.js";
import { keeps } from "../lib/keeps.js";
import { move } from "../dom/dom-move.js";
import { PAGE_PAINT_ATTRIBUTE } from "../base/page-paint.js";
import { marks } from "../state/kernel-facts.js";
import { generatedElement } from "../dom/widget-elements.js";
import type { WidgetDeclaration } from "../../types/contract.js";

type Scope = Document | DocumentFragment | Element;
const PAGE_PAINT_ATTRIBUTES: Set<string> = new Set(Object.values(PAGE_PAINT_ATTRIBUTE));
// Whether an attribute on the page's own element is paint rather than the author's: the
// runtime's, or a declared mark, which delivery paints into the served document and
// `markDeclared` into a message. A reading of the author's attributes on the live DOM
// (`shallowSigs`) looks past it, since paint is no change the author made.
export const isPagePaint = (name: string) =>
  PAGE_PAINT_ATTRIBUTES.has(name) ||
  Object.values(marks).some((mark) => mark.attribute === name);

// A word for a user listening, silent on screen: real text — the one thing every
// screen reader announces in every mode — placed at the element's start, wearing .lf-ui
// (an invisible word is apparatus the anchor pass must not offer), .lf-quiet (the
// shared clip), and data-lf-gen (no author wrote it). One writer per element, and the
// empty word removes what stands: a fact the page has stopped painting must stop being
// said too, so a caller states the whole of what this element says quietly and never
// appends to it.
//
// Which writer an element gets follows from what paints it, and the two sets do not
// meet: renderQuiet has the elements the runtime paints a provenance on, and a module
// has only the parts it builds — a suggestion's two slots, a code line. Two writers on
// one element would each remove the other's word on every state application, which the
// user would hear as the element re-reading itself.
function quietWord(el: Element, word: string | null) {
  const seat = el.firstChild;
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
  generatedElement(span);
  move(el, span, el.firstChild);
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

// A pane (`reading-role: pane`) is one reading region: its body, the one child that is
// neither its `header` nor its `footer`, is the region's box, and the pane its host,
// so focus in the header counts as in the region (module-scroll-and-motion.md,
// "Reading regions"). The pane's stylesheet finds the body the same way (elements.css).
// These marks are the runtime's paint, which a revision's source leaves out
// (features/version.js, `authoredMarkup`), so they are written as a pane arrives rather
// than delivered with the role: a body a revision brings in, or a pane in a message,
// takes the region too. A box a module generates in the pane role marks its own regions
// under its own names, so only a tag that declares the role is a pane here.
export function watchPanes() {
  const { scrollSurface, scrollHost } = PAGE_PAINT_ATTRIBUTE;
  const panes = tagsDeclaring((entry) => entry["reading-role"] === "pane");
  if (!panes.length) return;
  watchArrivals(panes.join(","), [], {
    arrive: (pane) => {
      keeps(pane, scrollHost, "body");
      const body = [...pane.children].find((child) => !child.matches("header, footer"));
      keeps(body, scrollSurface, "body");
    },
    leave: () => {},
  });
}

// The mark after a link that leaves the page (prepaint.js, `markExternalLink`).
// Prepaint seats it before authored prose first paints; this watch carries it through
// revisions, generated content and declared shadow stages.
export const opensElsewhere = (href: string | null) =>
  window.lfLinks.opensElsewhere(href);

export function watchNativeContent() {
  const { keepDisclosure, finishEarlyContent } = window.lfStorage;
  watchArrivals("a, details", ["href"], {
    arrive: (element) => {
      if (element instanceof HTMLDetailsElement) keepDisclosure(element);
      else window.lfLinks.markExternalLink(element);
    },
    leave: (element) => element.removeAttribute(PAGE_PAINT_ATTRIBUTE.external),
  });
  finishEarlyContent();
}

// What an upgraded subtree owes beyond its module's own work: the facts it paints
// spoken, and its code — and the page's own <pre><code> blocks and formulas, alongside
// the widgets and for the same reason: the tokenizer and the typesetter are vendored, so
// a page has them exactly when it has a widget layer at all. Written once because it
// happens twice, over the page at the upgrade and over each root a live revision brings
// into it, and a near-copy of it would go stale the day the vocabulary grows a third
// pass. A link's mark is not among them: it
// is the link's for as long as it stands, whoever rendered it (`watchNativeContent`).
export function paintDeclaredWords(root: Scope) {
  renderQuiet(root);
  return dressCode(root);
}

// The declarations a stylesheet has to read and cannot. Three of them first: one about
// the space a widget is given and two about how it participates in content, and none of
// them is something a selector can derive from the element in hand or look up.
//
// Which widgets may stand wider than the column is the first. Prose is set to a measure
// and stays at it; a board's columns and a diagram's graph are as wide as what they hold,
// and a page carrying one had to be either a cramped board or a page whose every
// paragraph was widened to suit it. Neither is a choice a page should have to make, so
// the widget declares its capacity (`space`) and the Layout gives it the room:
// `wide` uses the shared evidence cap, and `available` uses all remaining room.
// Internal arrangement remains package-owned.
//
// Whether the widget is set among the words around it is the second (`inline`).
// What reads it is the pair of selectors asking whether a suggestion slot or a variant
// holds block content, which is HTML's phrasing content inverted: a custom element is
// in no closed platform set, so any widget in one of those makes it a block — an inline
// widget included, which is the one wrong answer the inversion gives. The exclusion
// that fixed it was four widget names, and a bundled chip's tag therefore stood in the
// integrated theme, saying nothing at all about the next layer's inline widget. It is
// one marker now, data-lf-inline, and an inline widget from any layer joins by
// declaring.
//
// Whether the widget quotes what it holds is the third (`exhibit`). An exhibit is
// a mention, not a use, so every rule saying "this takes input" — the hand, the lift,
// the joined shape, the reserved strips, the hover wash — stands down inside one. The
// declaration is the tag's and the question is the occurrence's: whether this element
// sits inside an exhibit. So the mark goes on the exhibit and the rules exclude what
// stands under it, strictly within, as a widget's descriptor does: the exhibit itself
// is no mention. Ten of those rules spelled lf-sample before: a bundled tag, saying
// nothing about a project's own exhibit. A module asks the same of the mark
// (`[data-lf-exhibit] *`), as a stylesheet does, since neither reads a registry.
//
// Two more complete the set: `bound`, a block that holds its own height and scrolls
// inside it (`readings/bounds.js` holds each bounded block that arrives as a reading region, and
// keeps an `end` bound on its newest entry), and `reading-role`, the structure the
// theme and the workspace Layout lay out, so every package's pane takes the same rules.
//
// An attribute, because the theme cannot read the registry. Which declarations are marks, the attribute
// each is painted as, the attribute an occurrence overrides it with, and whether it
// holds in a message are one table, the kernel registry's `$marks`, which this runtime
// imports from `state/kernel-facts.js`. A page's document arrives painted from it: delivery
// writes the marks into the served source (revision_delivery.py, `mark_declared`), so
// the first paint already gives a board its room and a workspace its panes, before any
// module or the registry loads, and a revision the page patches in arrives painted the
// same way. A message is the runtime's to render, so `markDeclared` paints it from
// `marks` as it renders, with the marks that hold there: every one but the room, which
// is the document's to hand out, while a message renders in the panel's.

function* elementsIn(root: Scope, selector: string) {
  if (isElement(root) && root.matches(selector)) yield root;
  yield* root.querySelectorAll(selector);
}

// Paint a message's declared marks, the root alongside its descendants: each tag's
// declaration as it holds for the occurrence, and an occurrence's authored override
// over it.
export function markDeclared(root: Scope) {
  for (const [key, mark] of Object.entries(marks)) {
    const { attribute, authored, message } = mark;
    if (!message) continue;
    // `$marks` keys each mark by the name of the fact it paints.
    const fact = key as keyof WidgetDeclaration;
    const tags = tagsDeclaring((entry) => entry[fact]);
    for (const tag of tags) {
      const declared = registry[tag]?.[fact];
      for (const el of elementsIn(root, tag)) {
        const value = holdsFor(el, declared);
        if (key === "views") {
          markViews(el);
          continue;
        }
        keeps(
          el,
          attribute,
          !value ? null : value === true || mark.presence ? "" : String(value),
        );
        const role = mark.role?.[String(value)];
        if (role && !el.hasAttribute("role")) keeps(el, "role", role);
        if (role && !el.hasAttribute("aria-label"))
          keeps(el, "aria-label", el.getAttribute("label"));
      }
    }
    // Message markup is all content (`authored_on`, `$marks`), so only a
    // mark held to declaring tags asks which tag an occurrence is.
    if (authored)
      for (const el of elementsIn(root, `[${authored}]`))
        if (mark.authored_on !== "declared" || tags.includes(el.localName))
          keeps(el, attribute, el.getAttribute(authored));
  }
}

// What a widget states without local words: the runtime's three provenance states, a
// fact the eye reads off paint alone. Page Map makes them visible and navigable in a
// live page, while this quiet word keeps each one attached to its target for assistive
// technology.
// They compose into the element's one quiet span, so independent verbs can name user,
// report, and restatement origins without three writers fighting over the same seat.
function quietFacts(el: Element) {
  const words = el.hasAttribute(PAGE_PAINT_ATTRIBUTE.restated)
    ? ["rewritten since the decision"]
    : [];
  if (el.hasAttribute(PAGE_PAINT_ATTRIBUTE.userOverride)) words.push("my change");
  if (el.hasAttribute(PAGE_PAINT_ATTRIBUTE.reported)) words.push("reported state");
  return words.join(", ");
}

// Say each element's provenance quietly, or take the word away where it has none.
export function sayQuietFacts(elements: Iterable<Element>) {
  for (const el of elements) quietWord(el, quietFacts(el));
}

// Say the provenance of every element under `root` that wears a mark, as markup arrives:
// the page at upgrade, a revision's roots, a message.
export function renderQuiet(root: Scope) {
  // One query a mark: a single attribute's query is answered far faster than one for the
  // three as a selector list, which tests every element against each.
  const targets = new Set<Element>();
  for (const mark of [
    PAGE_PAINT_ATTRIBUTE.restated,
    PAGE_PAINT_ATTRIBUTE.userOverride,
    PAGE_PAINT_ATTRIBUTE.reported,
  ])
    for (const el of elementsIn(root, `[${mark}]`)) targets.add(el);
  sayQuietFacts(targets);
}
