/* The runtime paint projected onto page-owned elements and words: the readiness
   stamps on body, the layer-owned defaults that declarations make possible, and the
   words the runtime materializes or clips for a reader.

   The page has three readiness facts, all three written on `body` rather than on the
   root element. A reader waiting on the root sees an empty `dataset` forever, with every
   module loaded, nothing logged and nothing failed — which reads exactly like a page
   that never started, and sends the search to the server, the page key and the vendored
   layer in turn:

   - `data-lf-upgraded` means widget imports, asynchronous upgrades, geometry, and
     drawings have finished.
   - `data-lf-applied` is the event coverage of the last complete semantic projection
     committed to the DOM.
   - `data-lf-presented` means the initial authoritative projection, or the deliberate
     offline authored fallback, has crossed the semantic-interaction boundary.

   Do not merge these stamps. A document can finish upgrading while its first state read
   is pending, or the answer can wait unapplied while upgrades finish. A projection can
   commit while finite reconciliation animations are still settling. Any consumer that
   reads final boxes waits for upgraded, applied, presented, and no finite animation
   reported by `moving`.

   If registry declarations and the log contain enough information to implement a
   behavior, the layer implements it once. Current examples are:

   - `renderSaid` turns `x-says` values into real selectable text.
   - `renderQuiet` gives `x-paints` facts a clipped spoken reading.
   - `markDeclared` exposes the declared width model, inline run, and quoting to the
     theme.
   - `renderSettlement` (projection.js) paints the holder's authoritative settlement.
   - `renderRetired` marks slots retired by the declared holder relation.
   - The decision model (decisions/model.js) reads `x-awaits`, while the decision tray
     projects a declared `x-decision` region around that source where one exists;
     neither names a tag.
   - A holder declaring `x-request.decision` joins that same decision projection only
     while its canonical request lifecycle is `ready`. Pending and completed requests
     are the host's turn; a failed receipt returns the holder to the reader without a
     package-maintained pending flag.
   - `standingState` exposes replay winners to the render gate without naming a widget,
     the panel's own folds included: a widget an agent sent folds the way a page widget
     does and the poll replays it the same way, so the premise that every `renderState`
     is absolute binds it too.

   A module owns only its choreography and semantics that no declaration can express. For
   example, a suggestion module may animate its slots and write the visible deletion and
   insertion words. It does not own the general meaning of a settled holder.

   `renderSaid` materializes words that CSS would otherwise paint through `content:
   attr(...)`. A visible word must exist in a text node if the reader can point at it.
   Module-generated words that cannot be declared by attribute are inserted at the
   correct edge and marked `data-lf-gen`. Do not place a generated suffix after a control
   that semantically ends the row.

   The two edges are not mirror images. `after` goes inside the element's own words,
   because trailing chrome stands beside the last of them and a span past it lands on the
   far side of the apparatus. `before` goes at the element's start, because leading
   chrome is not something the words stand beside: a module puts one there to speak for
   the whole element, and stepping past it renders the element's own opening words
   underneath a summary of them.

   `renderQuiet` handles facts conveyed only by paint, such as an attribute-driven
   status. These words are clipped, unselectable, excluded from clipboard and anchor
   readings, but available to assistive technology. `quietFacts` derives them from
   `x-paints`. The paint and its quiet reading must agree.

   The runtime may inject its own words inside a widget. Comment-note buttons, for
   example, can be placed on a text block owned by that widget. A module reading its slot
   or body must call `says` so runtime words do not become authored or user content.
   Place injected lines on the block or anchored element, not on an intermediate body
   node from which a draft editor seeds its text. */

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
  applied: "data-lf-applied",
  reading: "data-lf-reading",
  dataRevision: "data-lf-data-revision",
  source: "data-lf-source",
  sourceRevision: "data-lf-source-revision",
  readerOverride: "data-lf-reader-override",
  presented: "data-lf-presented",
  reported: "data-lf-reported",
  upgraded: "data-lf-upgraded",
  inline: "data-lf-inline",
  wide: "data-lf-wide",
  exhibit: "data-lf-exhibit",
  yield: "data-lf-yield",
  holds: "data-lf-holds",
  goto: "data-lf-goto",
  traffic: "data-lf-traffic",
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

// External page links keep native link behavior but make the boundary explicit: the
// target opens beside this Leaf, the visible mark says it will leave the page, and its
// accessible word survives in a standalone copy. A URL on this page's own origin is
// still local even when the author wrote it absolutely; non-web schemes keep their
// platform meaning.
const EXTERNAL_LINK_ATTRIBUTES = ["target", "rel", "aria-describedby"];
const externalLinkState = new WeakMap();
let externalNoteSequence = 0;
export function isExternalPageLink(link) {
  if (!(link instanceof HTMLAnchorElement)) return false;
  try {
    const href = link.getAttribute("href");
    const url = href === null ? null : new URL(href, document.baseURI);
    return (
      ["http:", "https:"].includes(url?.protocol) && url.origin !== location.origin
    );
  } catch {
    return false;
  }
}
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
  for (const [name, value] of Object.entries(values)) {
    if (link.getAttribute(name) === value) continue;
    if (value === null) link.removeAttribute(name);
    else link.setAttribute(name, value);
  }
}
function rememberExternalLinkChanges(link, state) {
  if (!state.painted) return;
  const current = linkAttributes(link);
  for (const name of EXTERNAL_LINK_ATTRIBUTES) {
    if (current[name] === state.painted[name]) continue;
    let value = current[name];
    if (name === "rel" && state.addedNoopener)
      value = withoutToken(value, "noopener", true);
    if (name === "aria-describedby") value = withoutToken(value, state.noteId);
    state.baseline[name] = value;
  }
}
function clearExternalLink(link, state) {
  rememberExternalLinkChanges(link, state);
  writeLinkAttributes(link, state.baseline);
  link
    .querySelectorAll(':scope > .lf-external-mark[data-lf-gen="1"]')
    .forEach((node) => node.remove());
  state.note?.remove();
  externalLinkState.delete(link);
}
export function renderExternalLinks(root) {
  const links = [...(root.matches?.("a") ? [root] : []), ...root.querySelectorAll("a")];
  for (const link of links) {
    // SVG links share this selector but not the HTML anchor API, and they have no
    // dependable inline box in which an HTML text mark could stand.
    if (!(link instanceof HTMLAnchorElement)) continue;
    const external = isExternalPageLink(link);

    if (!external) {
      const state = externalLinkState.get(link);
      if (!state) continue;
      clearExternalLink(link, state);
      continue;
    }

    let state = externalLinkState.get(link);
    if (!state) {
      state = {
        baseline: linkAttributes(link),
        painted: null,
        noteId: `lf-external-note-${++externalNoteSequence}`,
        addedNoopener: false,
      };
      externalLinkState.set(link, state);
    } else rememberExternalLinkChanges(link, state);
    if (!link.querySelector(':scope > .lf-external-mark[data-lf-gen="1"]')) {
      const mark = document.createElementNS("http://www.w3.org/2000/svg", "svg");
      mark.setAttribute("class", "lf-ui lf-external-mark");
      mark.setAttribute("viewBox", "0 0 16 16");
      mark.dataset.lfGen = "1";
      mark.setAttribute("aria-hidden", "true");
      const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
      line.setAttribute(
        "d",
        "M6.5 3H4a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V9.5M9 3h4v4M13 3 7.5 8.5",
      );
      mark.append(line);
      link.append(mark);
    }
    if (!state.note) {
      state.note = Object.assign(document.createElement("span"), {
        className: "lf-ui lf-external-note",
        hidden: true,
        textContent: "opens in a new tab",
      });
      state.note.dataset.lfGen = "1";
      state.note.id = state.noteId;
    }
    if (link.parentNode && state.note.parentNode !== link.parentNode)
      link.after(state.note);
    state.addedNoopener = !tokens(state.baseline.rel).some(
      (value) => value.toLowerCase() === "noopener",
    );
    writeLinkAttributes(link, {
      target: "_blank",
      rel: withToken(state.baseline.rel, "noopener", true),
      "aria-describedby": state.note.parentNode
        ? withToken(state.baseline["aria-describedby"], state.noteId)
        : state.baseline["aria-describedby"],
    });
    state.painted = linkAttributes(link);
  }
}

// Widget families are open-ended, so their link-producing lifecycle cannot be a list in
// the runtime. One observer covers authored light DOM and every later widget mutation;
// shadowStage enrolls each declared shadow root in the same reading. Attribute watching
// makes a node preserved across renders lose or regain the treatment with its href.
const externalLinkRoots = new WeakSet();
const externalLinkObserver = new MutationObserver((records) => {
  const changed = new Set();
  const removed = new Set();
  for (const record of records) {
    if (record.type === "attributes") changed.add(record.target);
    else {
      if (record.target.querySelectorAll) changed.add(record.target);
      for (const node of record.addedNodes)
        if (node.nodeType === Node.ELEMENT_NODE) changed.add(node);
      for (const node of record.removedNodes) {
        if (!(node instanceof Element)) continue;
        if (node instanceof HTMLAnchorElement && externalLinkState.has(node))
          removed.add(node);
        for (const link of node.querySelectorAll("a"))
          if (link instanceof HTMLAnchorElement && externalLinkState.has(link))
            removed.add(link);
      }
    }
  }
  for (const root of changed) renderExternalLinks(root);
  for (const link of removed) {
    const root = link.getRootNode();
    const enrolled =
      (root === document &&
        externalLinkRoots.has(document.body) &&
        document.body.contains(link)) ||
      (root instanceof ShadowRoot &&
        root.host.isConnected &&
        externalLinkRoots.has(root));
    const state = externalLinkState.get(link);
    if (!enrolled && state) clearExternalLink(link, state);
  }
});
export function watchExternalLinks(root) {
  renderExternalLinks(root);
  if (externalLinkRoots.has(root)) return;
  externalLinkRoots.add(root);
  externalLinkObserver.observe(root, {
    subtree: true,
    childList: true,
    attributes: true,
    attributeFilter: ["href", ...EXTERNAL_LINK_ATTRIBUTES],
  });
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
  renderExternalLinks(root);
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
// after the first authored paint: the document is already useful, and these declarations
// progressively specialize its widget layout before those widgets upgrade. A message
// body cannot render before the registry is read. The root is marked alongside its
// descendants: a rebuild is handed a clone of the widget itself, and the fact is that
// widget's own.
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

// `markDeclared` exposes a declaration such as x-wide as paint, and CSS computes the
// room after chrome strips and claimed margins.
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
// The theme's pseudo rules stay as the no-script fallback; they stand down where this
// pass has been, asked by :has(), so the two are never both on. The span is data-lf-gen
// and not .lf-ui: the
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
// decision was undone. data-lf-reader-override and data-lf-reported are not — each marks a state
// whose substance is already in the control and receipt's visual and semantic state (a
// check, tint, and visible "Accepted") or the status this pass speaks. The outline
// identifies the state as a reader override or provisional report; work receipts
// separately state whether the agent has processed it.
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
