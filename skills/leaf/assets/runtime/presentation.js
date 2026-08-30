/* The runtime paint projected onto page-owned elements and words. */

import { registry, tagsDeclaring, widgetEntries } from "./registry.js";
import { highlightBlocks } from "./syntax.js";

// Attributes the runtime itself may paint onto elements the page owns. This is the
// replay signature's one exclusion vocabulary as well as the source each writer uses:
// a new kind of paint therefore has one place to join. The rest of data-lf-* is not
// implicitly ours — a widget can carry real state there, and replay must see it. The
// settlement mark (data-lf-state) is deliberately in that rest: the layer paints it
// (markSettled), but a module may paint it too as its own gesture's state, and the
// replay signature must keep seeing it — its own gate is RETIRED_SLOTS, not the sigs.
export const PAGE_PAINT_ATTRIBUTE = Object.freeze({
  class: "class",
  decision: "data-lf-decision",
  done: "data-lf-done",
  restated: "data-lf-restated",
  retired: "data-lf-retired",
  replayWrote: "data-lf-replay-wrote",
  reportWrote: "data-lf-report-wrote",
  applied: "data-lf-applied",
  reading: "data-lf-reading",
  dataRevision: "data-lf-data-revision",
  pending: "data-lf-pending",
  presented: "data-lf-presented",
  reported: "data-lf-reported",
  upgraded: "data-lf-upgraded",
  inline: "data-lf-inline",
  wide: "data-lf-wide",
  exhibit: "data-lf-exhibit",
  yield: "data-lf-yield",
  holds: "data-lf-holds",
});
export const PAGE_PAINT_ATTRIBUTES = new Set(Object.values(PAGE_PAINT_ATTRIBUTE));

// A word for a reader listening, silent on screen: real text — the one thing every
// screen reader announces in every mode — placed after the element's leading title,
// wearing .lf-ui (an invisible word is apparatus the anchor pass must not offer),
// .lf-quiet (the shared clip), and data-lf-gen (the diff looks away). One writer per
// element, and the empty word removes what stands: a fact the page has stopped painting
// must stop being said too, so a caller states the whole of what this element says
// quietly and never appends to it. lf-task and lf-milestone each hand-copied this idiom
// before it was one, and the copies had already diverged on whether a stale word was
// removed first — which is now renderQuiet's to state for every widget that declares it.
//
// Which writer an element gets follows from the declaration, and the two sets do not
// meet: renderQuiet has the elements the registry names (x-paints) and those the runtime
// paints a retraction on, and a module has only the parts it builds or the ones no
// declaration can reach — a suggestion's two slots, a code line. Declaring x-paints on a
// tag whose module also writes one here would leave both removing the other's word on
// each state application, which the reader would hear as the element re-reading itself.
export function quietWord(el, word) {
  const title = el.querySelector(":scope > strong");
  const seat = title ? title.nextSibling : el.firstChild;
  const standing = el.querySelector(":scope > .lf-quiet");
  if (standing) {
    // Nothing to say that isn't already said, in the place it belongs: a screen
    // reader rebuilds its buffer from the mutations, so a pass that finds the page
    // as it left it re-reads the element to whoever is on it for no reason. The seat
    // is part of that — a module that rebuilds its chip row between two runs of this
    // leaves the word standing behind it, and the fix is to move it, not to leave it
    // where the rebuild happened to put it.
    if (standing === seat && standing.textContent === word) return;
    standing.remove();
  }
  if (!word) return;
  const span = Object.assign(document.createElement("span"), {
    className: "lf-ui lf-quiet",
    textContent: word,
  });
  span.dataset.lfGen = "1";
  el.insertBefore(span, title ? title.nextSibling : el.firstChild);
}

// What an upgraded subtree owes beyond its module's own work: the words a widget says
// through an attribute rendered as real text, the facts it paints spoken, and its
// code — and the page's own <pre><code> blocks, alongside the widgets and for the same
// reason: the tokenizer is vendored, so a page has it exactly when it has a widget
// layer at all. Written once because it happens twice, over the page at the upgrade and
// over a widget rebuilt from the version's markup (rebuild), and a near-copy of it
// would go stale the day the vocabulary grows a fourth pass.
export function dress(root) {
  renderSaid(root);
  renderQuiet(root);
  return highlightBlocks(root);
}

// The declarations a stylesheet has to read and cannot. Three of them today: two about
// the box a widget is given and one about what may be offered inside it, and none of the
// three is something a selector can derive from the element in hand or look up.
//
// Which widgets may stand wider than the column is the first. Prose is set to a measure
// and stays at it; a board's columns and a diagram's graph are as wide as what they hold,
// and a page carrying one had to be either a cramped board or a page whose every
// paragraph was widened to suit it. Neither is a choice a page should have to make, so
// the widget kind says which it is (x-wide) and the theme spends the room the layout
// resolved by the CSS shell (--lf-room). The value is the kind the entry declares, and the
// theme's `[data-lf-wide="box"]` and `[data-lf-wide="drawing"]` rules read it.
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
// exhibit and the rules exclude what stands under it. That is the descendant half of the
// question — quoted() answers for the element itself as well — and it is the half these
// rules need while the tag they key on, lf-options, is not itself an exhibit. A layer
// that declared one to be would have to say so in its own rules. Ten of those rules spelled lf-specimen before: a bundled
// tag, saying nothing about a project's own exhibit. quoted() still asks the registry
// rather than this paint, which is the arrangement and not an oversight — the
// declaration is the one representation, and the mark is how a stylesheet, which cannot
// read a registry, asks it the same thing.
//
// An attribute, because the theme cannot read the registry — the same arrangement x-says
// already has with data-lf-said, and what carries the two box facts into an exported
// copy, which runs no script but keeps the markup. The exhibit's rules are the live
// page's alone (html:not(.lf-copy)), so its mark rides into a copy unread. It is the
// runtime's paint on the page's own element, so it joins PAGE_PAINT_ATTRIBUTES: the
// version diff reads the live DOM against a file nothing has painted, and an attribute
// missing from that exclusion list is a change the author never made. Written before the
// modules import, because the first two decide the box each module renders into and the
// third decides what may be drawn as pressable while they do. It lands a registry fetch
// after the first paint, and nothing is on screen in between to get wrong: the document
// waits behind the presentation gate (theme.css) and a message body cannot render before
// the registry is read. The root is marked alongside its descendants: a rebuild is handed a clone of the widget itself, and
// the fact is that widget's own.
//
// What separates the two tables is where each fact holds. x-inline is true of the element
// wherever it renders, a thread's message included, or a chip-led comparison quoted into
// a reply would stack there and nowhere else. So is x-exhibit: quoting is the element's
// own fact, and a specimen carried into a reply is quoted there too. A page's widget
// renders in both places, and only one of the three changes meaning when it moves. The
// room x-wide hands out is the document's, and a message is the one place a
// widget of the page's vocabulary renders outside the document, where the room is the
// panel's (see msgNode).
export const MARKED_ANYWHERE = Object.freeze({
  "x-inline": PAGE_PAINT_ATTRIBUTE.inline,
  "x-exhibit": PAGE_PAINT_ATTRIBUTE.exhibit,
});
export const MARKED_IN_PAGE = Object.freeze({
  ...MARKED_ANYWHERE,
  "x-wide": PAGE_PAINT_ATTRIBUTE.wide,
});

function* elementsIn(root, selector) {
  if (root.matches?.(selector)) yield root;
  yield* root.querySelectorAll(selector);
}

export function markDeclared(root, painted) {
  for (const [key, attr] of Object.entries(painted))
    for (const tag of tagsDeclaring((entry) => entry[key])) {
      const declared = registry[tag][key];
      for (const el of elementsIn(root, tag))
        el.setAttribute(attr, declared === true ? "" : declared);
    }
}

// Words a widget says through an attribute — a metric's number, an event's time, an
// option's chip band — rendered as text the user can reach. The theme renders the same
// words with `content: attr()`, and a pseudo-element's glyphs are in no text node: no
// selection can cover them, so no comment can be anchored on them, and the page shows
// text you can read and can't point at. Not the widget author's to remember, either: the
// registry names the attributes (x-says) and one pass renders them, so a widget cannot
// render a word the user can't quote.
//
// Each value goes at the edge its pseudo-element occupied (before = first child, after =
// last) — the only placement a pseudo could ever have had, and so the line past which a
// widget writes its own (lf-milestone's chips are a list and sit mid-element;
// lf-column's heading is its list's accessible name, which this pass knows nothing
// about). Those write the same data-lf-said span, and the guard below means the two
// compose rather than race. The pass runs after the upgrades, so a module that rebuilds
// its own body can't wipe a span put there first.
//
// The theme's pseudo rules stay, as the rendering a page carrying no script at all still
// gets (docs/how-it-works.html is one); they stand down where this pass has been, asked
// by :has(), so the two are never both on. The span is data-lf-gen and not .lf-ui: the
// diff parses the base version unupgraded and must not read it as text that version
// lacked, and the user must be able to quote it.
//
// data-lf-said names the attribute here and stands bare on a label relabel wrote, because
// the two are one claim — these words are the page's, whoever rendered them. The anchor
// pass reads the marker alone; the value is for whoever means one attribute in
// particular, which is this pass (so it writes no second span over its own) and the
// theme, whose every rule names the attribute it styles rather than matching the bare
// marker.
export function renderSaid(root) {
  for (const [tag, entry] of widgetEntries()) {
    if (!entry["x-says"]) continue;
    for (const el of elementsIn(root, tag))
      for (const [attr, edge] of Object.entries(entry["x-says"])) {
        const text = el.getAttribute(attr);
        if (text === null || el.querySelector(`:scope > [data-lf-said="${attr}"]`))
          continue;
        const span = document.createElement("span");
        span.dataset.lfSaid = attr;
        span.dataset.lfGen = "1";
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
        // though no shipped entry declares two.
        const pastTrailingChrome = [...el.childNodes].filter(
          (n) => !(n.nodeType === 1 && n.dataset.lfGen),
        );
        const beforeLeadingChrome = [...el.childNodes].find(
          (n) => !(n.nodeType === 1 && n.dataset.lfSaid),
        );
        el.insertBefore(
          span,
          (edge === "before"
            ? beforeLeadingChrome
            : pastTrailingChrome.at(-1)?.nextSibling) ?? null,
        );
      }
  }
}

// What a widget paints and never words. A task's status marker, a milestone's dot, an
// event's kind band: each is a fact the eye reads off paint alone, so a reader listening
// is handed every word around it and nothing of the fact itself — done sounded exactly
// like blocked. Same reasoning as renderSaid, one rung quieter: the registry names the
// attributes (x-paints) and one pass speaks them, because left to each module it is a
// thing to remember, and lf-event, which has no module at all, could never remember it.
//
// The value is the word, or the attribute's own name where the value is empty: an enum
// means what it says (`blocked`), and a flag attribute means what it is called.
//
// The runtime's own restatement paint is said here too — the same failure under a
// different owner, and the one the code that paints it already calls a debt: a decision
// undone looks exactly like one never made, and the outline stating the difference states
// it in ink alone. It composes into the element's one quiet span rather than taking a
// second, so the two cannot fight over the place, and every quiet word on the page is
// written by one call whichever facts it is carrying.
//
// Its two neighbours in that vocabulary stay silent, and the line between them is what
// the paint is the only copy of. A retraction is one: nothing else on the page says the
// decision was undone. data-lf-pending and data-lf-reported are not — each marks a state
// whose substance is already in words, the control's own ("✓ Accepted", "your pick") or
// the status this pass speaks, and adds only that no version carries it yet. Saying that
// on every decided element for the rest of the session would be a second sentence about
// every one of them, for a fact no reader is owed the way they are owed a retraction.
function quietFacts(el) {
  const words = el.hasAttribute(PAGE_PAINT_ATTRIBUTE.restated)
    ? ["rewritten since your decision"]
    : [];
  for (const attr of registry[el.localName]?.["x-paints"] ?? [])
    if (el.hasAttribute(attr)) words.push(el.getAttribute(attr) || attr);
  return words.join(", ");
}

export function renderQuiet(root) {
  const painting = [
    ...tagsDeclaring((entry) => entry["x-paints"]),
    `[${PAGE_PAINT_ATTRIBUTE.restated}]`,
  ].join(", ");
  for (const el of elementsIn(root, painting)) quietWord(el, quietFacts(el));
}
