/* The runtime paint projected onto page-owned elements and words: the readiness
   stamps on body, the layer-owned defaults that declarations make possible, and the
   words the runtime materializes or clips for a user.

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

   Beside them, `data-lf-reading` names the `/api/state` answer the page last applied
   (`markStateApplied`): its log, data, status, versions and presence adopted, its
   document's presentation pass finished, and every data subscriber told. A drag may
   still hold a region that pass reached; the coordinator, not this stamp, says so.

   Do not merge these stamps. A document can finish upgrading while its first state read
   is pending, or the answer can wait unapplied while upgrades finish. A later semantic
   publication or same-epoch renderer replacement leaves `data-lf-presented` set while
   the presentation coordinator reopens. A reader outside the page does not combine
   them itself: `pageReadiness` names the first of these facts, and of those below,
   still outstanding, and the entry script hands it to every such reader as
   `lfReadiness`.

   Presentation is not the end of the page's arrival. An owner may deliberately keep work
   off the presentation path — a widget's progressive upgrade, a developer surface's
   contained documents — and that work still moves boxes when it lands. `deferredArrival`
   is where such an owner says so, and the `arrived` stage of `pageReadiness` answers
   whether any of it is still outstanding. Startup waits for these arrivals before
   its final retained fragment landing, so late geometry keeps the requested place.
   A reader outside the page waits on the
   page rather than on a widget it had to know about. Without it the only thing outside
   the page that knows a deferred upgrade exists is whoever remembered to name it, which
   is a reader repeating what the page should settle.

   `afterPresentation` is the whole of that for a widget: it is the wait and the
   declaration together, so there is no way to hold work until the page has presented
   without the page counting it. A package never reaches the two halves separately.

   If registry declarations and the log contain enough information to implement a
   behavior, the layer implements it once. Current examples are:

   - `renderSaid` turns `x-says` values into real selectable text.
   - `renderQuiet` gives `x-paints` facts and state provenance a clipped spoken reading.
   - Declared marks expose the width model, inline run, quoting, own height, and
     reading role to the theme: delivery paints a page's document, and `markDeclared`
     a message.
   - `paintSettlements` (projection/presentation.js) paints every holder's
     authoritative settlement, whether or not its module renders anything.
   - `renderRetired` marks slots retired by the declared holder relation.
   - The Ask model (asks/model.js) reads `x-awaits`, while the Ask drawer
     projects a declared `x-ask-surface` region around that source where one exists;
     neither names a tag.
   - the internal validation adapter exposes replay winners to the render gate,
     the panel's own folds included: a widget an agent sent folds the way a page widget
     does and the poll replays it the same way, so the premise that every `renderState`
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

   `renderQuiet` handles facts with no local words, such as an attribute-driven status
   or the provenance of projected widget state. These words are clipped, unselectable,
   excluded from clipboard and anchor readings, but available to assistive technology.
   `quietFacts` derives them from `x-paints` and the runtime's provenance attributes.

   The runtime may inject its own words inside a widget: a quiet word, or an attribute
   the registry says aloud. A module reading its slot or body must call `says` so
   runtime words do not become authored or user content. */

import { elementDeclarations, registry, tagsDeclaring } from "./registry.js";
import {
  applicationPresented,
  attachApplicationPresentation,
  whenApplicationPresented,
} from "./semantic-state.js";
import { activityTransitionAt } from "./presence.js";
import { watchArrivals } from "./arrivals.js";
import { renderingSettled } from "./rendering.js";
import { highlightBlocks } from "./syntax.js";
import { setRuntimeRootAttribute } from "./root-state.js";
import { keeps } from "./keeps.js";

// Attributes the runtime may paint onto elements the page owns: the source each runtime
// writer uses, and with the declared marks (`$marks`) the replay signature's exclusion
// vocabulary (`isPagePaint`), so a new kind of paint has one place to join. The rest of
// data-lf-* is not implicitly ours — a widget can carry real state there, and replay
// must see it.
export const PAGE_PAINT_ATTRIBUTE = Object.freeze({
  class: "class",
  ask: "data-lf-ask",
  done: "data-lf-done",
  restated: "data-lf-restated",
  retired: "data-lf-retired",
  settlement: "data-lf-state",
  applied: "data-lf-applied",
  reading: "data-lf-reading",
  dataVersion: "data-lf-data-version",
  source: "data-lf-source",
  sourceRevision: "data-lf-source-revision",
  userOverride: "data-lf-user-override",
  presented: "data-lf-presented",
  reported: "data-lf-reported",
  upgraded: "data-lf-upgraded",
  holds: "data-lf-holds",
  moreBefore: "data-lf-more-before",
  moreAfter: "data-lf-more-after",
  scrollDirection: "data-lf-scroll-direction",
  moreBelow: "data-lf-more-below",
  goto: "data-lf-go-to-active",
  traffic: "data-lf-traffic",
  indicated: "data-lf-indicated",
  // Delivery's, not a runtime writer's: the size of the page media an element names
  // (revision_delivery.py, `mark_declared`).
  mediaWidth: "data-lf-media-width",
  mediaHeight: "data-lf-media-height",
});
const PAGE_PAINT_ATTRIBUTES = new Set(Object.values(PAGE_PAINT_ATTRIBUTE));
// Whether an attribute on the page's own element is paint rather than the author's: the
// runtime's, or a declared mark, which delivery paints into the served document and
// `markDeclared` into a message. The version diff reads the live DOM against a file
// nothing has painted, and paint it did not look past is a change the author never made.
export const isPagePaint = (name) =>
  PAGE_PAINT_ATTRIBUTES.has(name) ||
  Object.values(registry.$marks).some((mark) => mark.paint === name);
export const pagePresented = () =>
  document.body.hasAttribute(PAGE_PAINT_ATTRIBUTE.presented);
// The stamp is written here and nowhere else, and never taken back, so the promise it
// resolves answers every later waiter too.
const { promise: presented, resolve: resolvePresented } = Promise.withResolvers();
export function markPagePresented() {
  setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.presented, "1");
  resolvePresented();
}

// The arrivals their owners placed after presentation and that have not landed yet.
// Registration is synchronous at the point the owner decides to defer — before
// presentation for anything a page starts with — so the page never reads as arrived in
// the window between presenting and its first deferred upgrade taking hold.
const arriving = new Set();

/** Declare work this page finishes after presenting, and hand back its promise. */
export function deferredArrival(work) {
  arriving.add(work);
  const landed = () => arriving.delete(work);
  work.then(landed, landed);
  return work;
}

/** Wait for declared arrivals, including any they introduce while settling. */
export async function whenArrived() {
  while (arriving.size) await Promise.allSettled(arriving);
}

/** Run `work` once the page has presented, as an arrival the page answers for. */
export const afterPresentation = (work) => deferredArrival(presented.then(work));

// The `/api/state` answer this page last applied: the reading that names it, the moment
// the server took it, and the moment its activity could next change with no file
// moving (`activityTransitionAt`), all on the server's clock. The `state` stage below
// compares these with the answer a reader holds.
let appliedState = null;

/** Record `state` as applied. Called once per answer, after its document's presentation
    pass and every data subscriber it told have finished. */
export function markStateApplied(state) {
  setRuntimeRootAttribute(document.body, PAGE_PAINT_ATTRIBUTE.reading, state.reading);
  appliedState = {
    reading: state.reading,
    taken: state.taken,
    lapses: activityTransitionAt(state),
  };
}

const stamp = (name) => document.body.getAttribute(PAGE_PAINT_ATTRIBUTE[name]);
// In the order a page reaches them. `held` is the `/api/state` answer a reader holds
// (`{reading, taken}`), or null for a reader holding none, which skips `state`.
const READINESS = [
  ["upgraded", () => stamp("upgraded") === "1"],
  ["log", () => stamp("applied") !== null],
  [
    "state",
    (held) =>
      !held ||
      appliedState?.taken >= held.taken ||
      (appliedState?.reading === held.reading &&
        held.taken * 1000 < appliedState.lapses),
  ],
  ["presented", () => pagePresented() && applicationPresented()],
  ["arrived", () => arriving.size === 0],
  ["rendering", () => renderingSettled()],
];
const READINESS_STAGES = new Set(READINESS.map(([stage]) => stage));

/** The first readiness fact this page has yet to state, or null once a reader outside
    it may read its final boxes and press its keys.

    The stages: `upgraded`; `log`, some log coverage applied; `state`, the answer the
    reader holds applied; `presented`, the initial milestone and the coordinator's
    current reading; `arrived`, nothing deferred past presentation still outstanding;
    `rendering`, nothing queued for a rendering update. A reading is a digest with no
    order, and the server may move past the answer held — a source rewritten, a claim
    aged, a neighbour started — so a page that applied an answer the server took later
    has caught up with it too. A reading names files and presence, not the activity the
    server folds from them against its clock, so an applied answer with the held
    reading has caught up only if the held one was taken before that activity could
    change; after it, the page asks again at that moment and catches up by `taken`.

    `through` names the last stage the reader needs. A test that writes behind a page
    in the middle of a gesture — a drag holding the projection, a fold still animating
    — asks only that the page has taken the write in, which is `state`.

    Finite animation is not a stage: the render gate's `pageSettled` asks that
    separately. */
export function pageReadiness(held = null, through = "rendering") {
  if (!READINESS_STAGES.has(through))
    throw new TypeError(`no readiness stage named ${through}`);
  for (const [stage, met] of READINESS) {
    if (!met(held)) return stage;
    if (stage === through) return null;
  }
}

// The one initial turn in which box-derived page apparatus can read the complete
// authoritative layout before semantic interaction opens. Widget upgrade gives
// components enough geometry to build and paint from authored state, while presentation
// adds replay, restored chrome, and fragment reveal. Components keep observing later
// real layout changes through their ordinary ResizeObserver or layout signal; this event
// exists only to replace a provisional startup reading synchronously.
export const PRESENTATION = "lf-presentation";

// Optional runtime-owned page interface joins the same settlement boundary as the
// widget modules it composes. Initial startup and an in-place version activation both
// pass here, so a dynamically imported surface cannot appear after either page is
// already in front of the user.
export const PAGE_INTERFACE = "lf-page-interface";
// `presented` is the wait the caller owes once the interface has settled: the whole
// application at startup, and for a live revision patched in place only this region,
// since that install runs inside the state turn whose answer may still owe a standing
// widget its data — a wait on the whole application there is a wait on itself.
export async function settlePageInterface(presented = whenApplicationPresented) {
  const pending = [];
  const presentation = attachApplicationPresentation("page-interface", document);
  const present = (promise) => {
    if (!promise?.then)
      throw new TypeError("Page interface presentation must be a promise");
    pending.push(promise);
    return promise;
  };
  try {
    document.dispatchEvent(new CustomEvent(PAGE_INTERFACE, { detail: { present } }));
    // Each optional owner reports its own failure. One rejected surface must not keep
    // every generated control on the page behind the upgrade boundary.
    await presentation.present(pending, Promise.allSettled(pending));
    await presented();
  } finally {
    presentation.disconnect();
  }
}

// A word for a user listening, silent on screen: real text — the one thing every
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
// each state application, which the user would hear as the element re-reading itself.
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
// target opens beside this Leaf, and the visible mark says it will leave the page. A URL
// on this page's own origin is still local even when the author wrote it absolutely;
// non-web schemes keep their platform meaning.
//
// The mark is also what a screen reader is told: the link's description names it, and it
// carries the words as its label. It stays hidden, so the words are not part of the
// link's name, and a description may name a hidden element. Everything the treatment adds
// stands inside the link, so the page's own rules about which of a block's children
// comes last, or what follows a link, match what the page wrote.
const EXTERNAL_LINK_ATTRIBUTES = ["target", "rel", "aria-describedby"];
const externalLinkState = new WeakMap();
let externalMarkSequence = 0;
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
    if (name === "aria-describedby") value = withoutToken(value, state.markId);
    state.baseline[name] = value;
  }
}
function clearExternalLink(link, state) {
  rememberExternalLinkChanges(link, state);
  writeLinkAttributes(link, state.baseline);
  link
    .querySelectorAll(':scope > .lf-external-mark[data-lf-gen="1"]')
    .forEach((node) => node.remove());
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
  if (!isExternalPageLink(link)) {
    leaveExternalLink(link);
    return;
  }
  let state = externalLinkState.get(link);
  if (!state) {
    state = {
      baseline: linkAttributes(link),
      painted: null,
      markId: `lf-external-mark-${++externalMarkSequence}`,
      addedNoopener: false,
    };
    externalLinkState.set(link, state);
  } else rememberExternalLinkChanges(link, state);
  let mark = link.querySelector(':scope > .lf-external-mark[data-lf-gen="1"]');
  if (!mark) {
    mark = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    mark.setAttribute("class", "lf-ui lf-external-mark");
    mark.setAttribute("viewBox", "0 0 16 16");
    mark.dataset.lfGen = "1";
    mark.setAttribute("aria-hidden", "true");
    mark.setAttribute("aria-label", "opens in a new tab");
    const line = document.createElementNS("http://www.w3.org/2000/svg", "path");
    line.setAttribute(
      "d",
      "M6.5 3H4a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h8a1 1 0 0 0 1-1V9.5M9 3h4v4M13 3 7.5 8.5",
    );
    mark.append(line);
    link.append(mark);
  }
  // Written on a mark found as well as on one made: a link cloned with its mark, ids
  // stripped, is a new link to this pass, and its description must name its own mark.
  keeps(mark, "id", state.markId);
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

// Widget families are open-ended, so their link-producing lifecycle cannot be a list in
// the runtime: a link is marked while it stands in the page or a declared shadow root,
// whoever put it there (arrivals.js). Attribute watching makes a node preserved across
// renders lose or regain the treatment with its href. Started with the page's install.
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
export function dress(root) {
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
// resolved by the CSS shell (--lf-room). `wide` uses the shared evidence cap;
// `available` uses all remaining room. Internal arrangement remains package-owned.
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
// that declared one to be would have to say so in its own rules. Ten of those rules spelled lf-sample before: a bundled
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
// message are one table, Python's `schema.DECLARED_MARKS`, which composition stamps into
// the vocabulary as `$marks`. A page's document arrives painted from it: delivery writes
// the marks into the served source (revision_delivery.py, `mark_declared`), so the first
// paint already gives a board its room and a workspace its panes, before any module or
// the registry loads, and a revision the page patches in arrives painted the same way. A
// message is the runtime's to render, so `markDeclared` paints it from `$marks` as it
// renders, with the marks that hold there: every one but the room, which is the
// document's to hand out, while a message renders in the panel's.

function* elementsIn(root, selector) {
  if (root.matches?.(selector)) yield root;
  yield* root.querySelectorAll(selector);
}

// Paint a message's declared marks, the root alongside its descendants: each tag's
// declaration, and an occurrence's authored override over it.
export function markDeclared(root) {
  for (const [key, { paint, authored, message }] of Object.entries(registry.$marks)) {
    if (!message) continue;
    for (const tag of tagsDeclaring((entry) => entry[key])) {
      const declared = registry[tag][key];
      for (const el of elementsIn(root, tag))
        keeps(el, paint, declared === true ? "" : declared);
    }
    if (authored)
      for (const el of elementsIn(root, `[${authored}]`))
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
  for (const [tag, entry] of elementDeclarations()) {
    if (!entry["x-says"]) continue;
    for (const el of elementsIn(root, tag))
      for (const [attr, edge] of Object.entries(entry["x-says"])) {
        const text = el.getAttribute(attr);
        const standing = el.querySelector(`:scope > [data-lf-said="${attr}"]`);
        // A live revision may change or drop the attribute under a span already
        // standing for it; the span follows the attribute rather than the first word
        // it ever said.
        if (standing) {
          if (text === null) standing.remove();
          else if (standing.textContent !== text) standing.textContent = text;
          continue;
        }
        if (text === null) continue;
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
        // though no shipped declaration names two.
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

// What a widget states without local words. A task's status marker, a milestone's dot, an
// entry's kind band: each is a fact the eye reads off paint alone, so a user listening
// is handed every word around it and nothing of the fact itself — done sounded exactly
// like blocked. Same reasoning as renderSaid, one rung quieter: the registry names the
// attributes (x-paints) and one pass speaks them, because left to each module it is a
// thing to remember, and lf-chronology-entry, which has no module at all, could never remember it.
//
// The value is the word, or the attribute's own name where the value is empty: an enum
// means what it says (`blocked`), and a flag attribute means what it is called.
//
// The runtime's three provenance states are said here too. Page Map makes them visible
// and navigable in a live page, while this quiet word keeps each one attached to its
// target for assistive technology.
// They compose into the element's one quiet span, so independent verbs can name user,
// report, and restatement origins without three writers fighting over the same seat.
function quietFacts(el) {
  const words = el.hasAttribute(PAGE_PAINT_ATTRIBUTE.restated)
    ? ["rewritten since your decision"]
    : [];
  if (el.hasAttribute(PAGE_PAINT_ATTRIBUTE.userOverride)) words.push("your change");
  if (el.hasAttribute(PAGE_PAINT_ATTRIBUTE.reported)) words.push("reported update");
  for (const attr of registry[el.localName]?.["x-paints"] ?? [])
    if (el.hasAttribute(attr)) words.push(el.getAttribute(attr) || attr);
  return words.join(", ");
}

export function renderQuiet(root, also = []) {
  const painting = [
    ...tagsDeclaring((entry) => entry["x-paints"]),
    `[${PAGE_PAINT_ATTRIBUTE.restated}]`,
    `[${PAGE_PAINT_ATTRIBUTE.userOverride}]`,
    `[${PAGE_PAINT_ATTRIBUTE.reported}]`,
  ].join(", ");
  const targets = new Set(elementsIn(root, painting));
  for (const el of also) if (el === root || root.contains(el)) targets.add(el);
  for (const el of targets) quietWord(el, quietFacts(el));
}
