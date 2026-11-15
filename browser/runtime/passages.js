/* The page's one DOM reading and quote resolver.

   Passages use one representation: ordered segments `{node, start, end}` over composed
   text. `textNodesUnder` produces the segments, and quote capture, quote resolution,
   reading position, element labels, and version-comparison readings all use them. Never
   introduce another text walk for one of those jobs: the page's words are `pageText()`
   (its `segments`, and its blocks `pageRuns()`), the part of them under one element is
   `pageText(el)`, and one element's own words are `elementReading(el, "says" |
   "wrote")`; each is kept until what it was read from changes. Each segment also
   carries the `block` its words read in, their typographic `textBlock`, and the
   generated element (`gen`) they stand in, which the walk knew on its way down. A datum
   starts a reading block without inserting whitespace into inline text; a cut segment
   keeps these facts.

   Two readings are intentionally different:

   - `says` is what the rendered page tells the user. It includes registry or
     module-generated words declared as part of the page. A behavior module reads
     authored or user-facing words with `says`, never raw `textContent`.
   - `wrote` is what the author placed in the version. It excludes generated runtime
     and widget words and is appropriate for version comparison.

   Both are bounded by the root they are handed. `.lf-ui` says the runtime built a node
   rather than the author, and a reading rooted at the document takes that straight.
   Rooted at an element it is a different sentence, and the difference is the whole of
   what a widget in a message needs: such a widget stands inside the floating panel, so
   the panel is `.lf-ui` over every word it says, and an unbounded reading has it saying
   nothing at all. Chrome above the root is not the root's apparatus; chrome inside it
   still is. A page-rooted walk does not move.

   Keep them as named readings. A boolean passed to one ambiguous reader makes callers
   choose semantics at each call site.

   The page's reading is kept in pieces, the frame and each datum that is a part
   (`Piece`), and every caller shares each piece until it changes underneath, so a change
   walks again only the piece it lands in, and a reader reads only the pieces it needs:
   `pageText()` is the frame's, where prose stands, `pageText(part)` a part's, and the
   reading place reads the parts in view. The document reports its own changes, so
   anything else the reading is built out of has to say so here: `fencePassageParts` for
   the widget parts the cell walk fences on, `watchPassageRoot` for a declared shadow
   stage the walk crosses into, and the registry generation, which `pageText` reads each
   time. A new input with no door is a reading that goes stale silently — the mark lands
   on the words the page used to say. The reverse holds too: a change lands where the walk
   reads or it is no change to the reading, by the walk's own rules (`contextAt`), so
   the runtime repainting its chrome does not cost the page a walk. A message's body is a
   document of its own (`authoredScope`) with a reading of its own, and a change, a
   fence or a stage registered there forgets that reading and leaves the page's.

   Native editing hosts and readonly islands inside them are passage cells. Context
   outside a field never borrows its mutable value; an actual native selection inside
   remains readable. File and browser readings share these ownership fences.
   Native textarea children initialize its value; they are never visible document
   words or surrounding quote context, before or after that value is edited.

   The walk carries its context down (`enter`): each element states once whether it
   starts chrome, silence, generated words, a block or a passage cell, rather than each
   text node climbing to ask. `pageText` indexes back from its string by segment
   (`rawStart`), and `pointAt` is the one way from a position in `raw` to a node and
   offset.

   `GENERATED` is `.lf-ui, [data-lf-gen]`. It marks words that are not authored.
   `data-lf-said` is nearer than `.lf-ui` and declares that a label inside
   chrome-looking structure is still one of the page's words. This lets a tab label or
   draft heading remain quotable while runtime controls stay outside the passage.
   `generatedElement` writes the said marker; `offer` writes the control marker. They
   are independent facts and neither clears the other.

   A label copied off another element on the page is a route to those words rather
   than a second place the page says them. Say it once: a contents link, a roster row
   naming a worker, any generated index entry stays chrome, and the passage lives where
   the page speaks it. Two copies of one label carry the same text and, being fenced,
   the same empty context, so neither can be told from the other and a drag across
   either detaches. (The third answer of `says`, `"echo"`, is what such a route
   declares; widget-elements.js says how.)

   Use `inChrome` when the question is whether an element belongs to the runtime's
   document layer. Use `.lf-ui` when the question is whether words or styling are
   runtime apparatus. Use `data-lf-offer` when the question is whether something is an
   injected control. These markers are not interchangeable; `pageWords` excludes
   runtime-owned surfaces and widget apparatus, and its comment says which hole
   each half alone leaves.

   A quote's copies are found in the reading's letters (`spell`, `scan`), kept with the
   reading: a few quotes by the platform's string search, many by one automaton over
   every quote's spelling, in time with the page however long or many the quotes, so the
   stored quote is never truncated: it is the passage the user selected. The copies of
   the quotes anchor placement keeps are carried from one reading to the next through
   the span the two differ in (`carry`), so a change to the page is searched only around
   it. An anchor asked of a reading again has the answer it had (`findQuote`).

   Shadow trees: only open roots declared through `x-shadow` join the page reading;
   any other root is opaque, and its host reads by its light children (`walk`).
   `pageShadowRoots` (shadow.js) enumerates the declared ones. `textNodesUnder` crosses those roots,
   `pageRange` requests them from `getComposedRanges`, and `upFrom`, `under` (shadow.js),
   and `closestAcross` cross back to the host.

   Identity crosses the same boundary. `elementById` searches the document and declared
   open roots. `pageQueryAll` clears or queries marks everywhere the runtime may write.
   `focused` (focus.js) descends through retargeted `document.activeElement`
   until it finds the actual control.

   Hit testing asks two different questions. `elementFromPointAcross` and `markAt`
   (anchor-resolution.js) may descend into a declared shadow root when the exact marked
   text matters.
   `aimedTarget` (composing/aim.js) may keep document retargeting when the host is the
   addressable element. Choose the reading by the question, not by convenience.

   The page's widget inventory remains the document's declared inventory. Do not
   silently discover nested widget families inside shadow roots as new top-level
   content. A module that stages a declared widget inside a shadow tree still owes the
   visible words promised by that widget's entry. `silentWords`, in the render checks,
   examines open roots and catches promised words that are absent, clipped, or hidden.
   It also catches a module that replaces declared words after the shared render
   passes. */

import { isNode, closestAcross } from "./shadow-tree.js";
import { liveStages } from "./arrivals.js";
export { closestAcross, inChrome } from "./shadow-tree.js";
import {
  SAID,
  declaredRoot,
  UI_MARKS,
  inUi,
  overIn,
  refuseShadowRoot,
  pageShadowRoots,
  shadowHost,
  shadowRootsIn,
  uiInside,
  under,
  upFrom,
} from "./shadow.js";
import {
  alongClimb,
  composedParentNode,
  isElement,
  isShadowRoot,
  isText,
  isHTML,
  renderedParent,
  skipper,
} from "./shadow-tree.js";
import { decisionFor, registry } from "./registry.js";
import { PAGE_PAINT_ATTRIBUTE, pagePresented, pageUpgraded } from "./page-paint.js";
import { reportPageError } from "./layer-client.js";
import { presentDocument, readPart } from "./semantic-state.js";
import { COLLAPSE, COLLAPSE_CHARS, PHRASING, TEXT_BLOCK } from "./kernel-facts.js";
import { textUnits } from "./text-alignment.js";
import { excerptWords } from "./words.js";
import { union } from "./rect.js";

/** @typedef {{el: Element, editing: boolean, up: CellChain | null}} CellChain
 * @typedef {{chrome: boolean, silenced: boolean, generated: boolean,
 * gen: Element | null, block: Element | null, textBlock: Element | null,
 * words: Element | null, island: Element | null, cells: CellChain | null}} ReadingContext
 * @typedef {{node: Text, start: number, end: number, block: Element | null,
 * textBlock: Element | null, words: Element | null, gen: Element | null,
 * breakBefore?: boolean, lineBefore?: string, whiteSpace?: string, cut?: boolean}} Segment
 * @typedef {Segment & {rawStart: number}} IndexedSegment
 * @typedef {{raw: string, positions: WeakMap<Text, number>,
 * fences: number[], segments: IndexedSegment[]}} PageReading
 * @typedef {{container: Element, heading: Element | null, up: Over | null}} Over
 * @typedef {{outline: readonly Element[], at: Map<Element, number>,
 * over: Pick<Map<Element, Over | null>, "get">,
 * above: Pick<Map<Element, Element | null>, "get" | "has">}} OutlineReading
 * @typedef {OutlineReading & {over: Map<Element, Over | null>,
 * above: Map<Element, Element | null>}} WalkedOutline
 * @typedef {{node: Text, offset: number, segment: Segment}} Point
 * @typedef {keyof typeof READINGS} Reading */

// Opaque widgets and their original direct children: each is a passage cell of its own.
const passageFences = new WeakSet();
export const verbatimOwnerIdentity = new WeakMap();
export const verbatimBoundaryIdentity = new WeakMap();

// ---------- passages ----------
// A passage is a list of {node, start, end} segments, and everything that reads the page's
// text speaks in them: the search for a quote, the capture of one, the landmark a version
// change rides on, the version comparison's block keys. One shape means one answer to what the
// page says. The bugs this layer kept having were all a second answer disagreeing with the
// first — what a selection rendered as versus what the document holds — and a second
// answer is what there is now no room for.
//
// Two skip lists, because two jobs genuinely differ, and the difference is the whole
// reason .lf-ui and data-lf-gen are two markers rather than one. Anchoring skips the
// runtime's own words, inline scripts, and the stylesheet a rendered diagram carries
// inside its <svg>: a quote holding text the search skips is a quote nothing can find
// again. The authored reading additionally skips content an upgrade generated, so it
// reads a live block as the block's source does: a version comparison paints a source's
// words onto the live block standing for it (version.js), and a module reads its own
// authored words. So generated text the page authored — a widget's label, an attribute
// renderSaid rendered — is quotable and outside the authored reading.
//
// A decided suggestion's retired slot goes with them. Its markup is still in the
// document — the honoring version is what finally drops it — but the user has
// removed it, and the live view is the version plus their decisions. Text nobody can
// see is text nobody can mean: without this a comment made on a passage then accepted
// away kept reading as attached in the panel and jumped nowhere, and a quote from
// elsewhere could match inside the invisible half of a replacement.
//
// Which slots retire is the registry's to say, so this and passages.py's reading of the
// same page follow one declaration: x-retired-when names the decision that removes the
// element, x-owners the wrapper the decision is recorded on. Composition stamps that
// relation, owner by owner, into `$decisions` (Python's `registry.contract.stamp_decisions`).
// Which outcome stands is the application's reading of the log and this tab's own
// gestures, so the readings take it from the publisher, as `paintSettlements` does,
// and never back from the mark that paint leaves: a mark a module wrote where the log
// decided nothing silences no words.
//
// `settlements` is that reading per holder id: its tag, and the tags its outcome
// in force retires.
// It is a selection of the publication, one per registry, so it moves only when a
// settlement does, and a paint that reads a passage's words repaints for a decision
// rather than for every widget's state. `settledKey` names it, so the page reading is
// forgotten exactly when it changes (`catchUpReading`).
/** @typedef {ReadonlyMap<string, {tag: string, retires: readonly string[]}>} Settlements */
/** @type {(() => Settlements) | null} */
let settledReading = null;
/** @type {Record<string, import('./registry.js').Decision> | undefined} */
let settledDecisions;
/** @type {Settlements | null} */
let settled = null;
let settledKey = "[]";
function settlements() {
  if (settledDecisions !== registry.$decisions || !settledReading) {
    const decisions = (settledDecisions = registry.$decisions);
    settledReading = readPart((root) => {
      /** @type {Map<string, {tag: string, retires: readonly string[]}>} */
      const holders = new Map();
      for (const [id, { state }] of root.effective.widgets) {
        const tag = root.document.authored.get(id)?.tag;
        const decision = tag === undefined ? undefined : decisions?.[tag];
        // A decision verb's state is an action value, which carries the detail.
        const outcome =
          decision &&
          /** @type {{detail?: {outcome?: string}} | undefined} */ (
            state[decision.verb]
          )?.detail?.outcome;
        const retires = outcome ? decision.retires[outcome] : null;
        if (tag !== undefined && retires?.length)
          holders.set(id, { tag, retires: [...retires] });
      }
      return holders;
    });
  }
  const next = settledReading();
  if (next !== settled) {
    settled = next;
    settledKey = JSON.stringify([...settled]);
  }
  return settled;
}
// A slot its holder's decision took off the page: a child of the holder, in its light
// tree or its shadow root, whose tag the outcome in force retires. Only this
// document's holders are settled; a parsed revision's elements share their ids.
/** @param {Element} el */
function retiredSlot(el) {
  const holder = upFrom(el);
  if (!holder?.id || el.ownerDocument !== document) return false;
  const settlement = settlements().get(holder.id);
  return (
    settlement?.tag === holder.localName && settlement.retires.includes(el.localName)
  );
}

// The rendering of a settlement, in one place for the two occasions that paint it —
// replay and a module saying its own gesture (lf-suggestion's #settle). The semantic
// outcome is passed in from the application reading; the owner's data-lf-state is only
// corresponding paint and is never read back. The shared state.css tier hides marked
// slots in the document and declared shadow stages, above package display defaults.
/** @param {Element} el @param {string | null} outcome */
export function renderRetired(el, outcome) {
  const outcomes = decisionFor(el.localName)?.retires;
  if (!outcomes) return;
  for (const [candidate, tags] of Object.entries(outcomes))
    for (const tag of tags)
      for (const root of [el, ...(el.shadowRoot ? [el.shadowRoot] : [])])
        for (const slot of root.children)
          if (slot.localName === tag)
            slot.toggleAttribute(PAGE_PAINT_ATTRIBUTE.retired, candidate === outcome);
}

// An element the user's decision took off the page, asked of an element rather
// than of text: a retired slot (or anything inside one), or a decided element the
// retirement emptied — a deletion accepted, an insertion refused — whose every child
// is now a retired slot or the runtime's own chrome, with no text of its own. The
// same declaration the anchor pass skips text by answers both (a declared label
// counts as words still showing), and so an element anchor and a quote cannot
// disagree about what left the page.
//
// The chrome question is bounded at the element, because the answer is about what this
// element has left rather than about where it is standing. A suggestion an agent sent
// in a reply stands inside the panel, which is chrome, so asked the unbounded way its
// surviving half counted as apparatus too: one accepted slot emptied it, the anchor a
// user had put on it detached, and the mark went out from under a thread that was
// still open. The same suggestion on the page kept both.
/** @param {Element} el */
export function settledAway(el) {
  /** @type {Element | null} */
  let at = el;
  for (; at; at = at.parentElement) if (retiredSlot(at)) return true;
  const nodes = [...el.childNodes];
  return (
    nodes.some((n) => isElement(n) && retiredSlot(n)) &&
    nodes.every((n) =>
      isElement(n) ? retiredSlot(n) || uiInside(n, el) : !isText(n) || !n.data.trim(),
    )
  );
}
export const GENERATED = ".lf-ui, [data-lf-gen]";
// A message's body: the markup its writer sent, and the text the runtime renders from
// their words beside that markup.
const MESSAGE_BODY = ".lf-msg-body";
// Every heading, which names the part of the page under it.
export const HEADING = "h1, h2, h3, h4, h5, h6";
// What a heading in it heads, as a page's title in its header heads the page (`headed`).
const HEADERS = "header, hgroup";
export const DATUM = "[data-lf-projection][data-lf-datum]";
// A part of the page's reading, kept apart from the rest (`Piece`): a datum whose words
// are parted from those around it, and which heads nothing outside it.
const PART = `${DATUM}:not(${HEADING}, ${HEADERS})`;
/** @param {Element} element */
const isPart = (element) => element.matches(PART) && !phrasing(element);
// Whether the user can see a block's words, for a reading or a landing chosen among the
// page's blocks. A box is no answer: what content-visibility hides keeps its boxes where
// it would stand shown, both an inactive tab's panel (hidden="until-found") and a closed
// <details>' contents, and a `visibility: hidden` block keeps its box too. Focus can land
// on none of them.
/** @param {Element} block */
export const showsWords = (block) =>
  block.checkVisibility({ visibilityProperty: true });
// The Leaf surface a node stands in, wherever it is seated: the chrome root, or a
// surface of the runtime's own that its owner seats inside page content — the response
// bar in a widget's outlet, a thread a widget places beside its lines. Each such surface
// marks itself `data-lf-runtime`, so the reading travels with the node rather than with
// the place it stands. A press mode that comments on or chooses the page leaves these
// working.
export const LEAF_SURFACE = ".lf-chrome, [data-lf-runtime]";
/** @param {EventTarget | null | undefined} node */
export const leafSurface = (node) =>
  isNode(node) ? closestAcross(node, LEAF_SURFACE) : null;
// The two together, which is what an affordance acting on where the pointer or the caret
// is actually needs: the page's own words, as against the layer over them and as against
// the apparatus inside them. Either half alone leaves a hole, and the hole `.lf-ui` left
// was this one — a declared label is nearer than the panel and answers for itself, so a
// drag across a question an agent asked in a reply read as a passage of the page. It
// raised the page's 💬 and wrote an anchor onto a thread's own id, into an append-only
// log, naming a section no version holds. `leaf thread create --section` refuses exactly that
// from the file side, and file capture is the reading that is supposed to promise less.
/** @param {Node | null} node */
export const pageWords = (node) => inPage(node) && !inUi(node);
// The two readings, each one predicate over a text node and named for the question it
// answers. Anchoring reads what the user can point at: not the runtime's own words —
// `inUi`, which a declared label answers for itself — and nothing behind a wall no label
// speaks through, so a pick mark inside a slot the user accepted away is gone with
// the slot, its marker notwithstanding. The authored reading keeps what a source holds,
// so everything an upgrade generated goes, a declared label included: no source has one.
//
// A text node's parent is an element, and every reading of these nodes says so: the
// walk asks it of a shadow root's own text and of a slotted node's place, and
// `authored` of a node it is handed. Written once per reading it was several answers to
// one question, one of them quietly admitting a node without a parent — which is a
// claim about the page nothing backs: what a widget
// stages into a shadow root is the only text these walks reach with no element over it,
// and a module staging a bare text node would be handing the page words no cell, no
// fence and no block. So the assertion is one function, and refusing is what it does.
//
// It refuses in the words of the mistake, which is the half that was missing. Throwing
// out of the pass the render gate reads the console for is the loud direction, and the
// throw was `Cannot read properties of null (reading 'closest')` on a page showing
// nothing at all — naming neither the widget that staged the text nor what was wrong
// with it. A refusal whose message is a property name reaches its author as the runtime
// being broken, which is the one thing it isn't.
/** @param {Text} n */
const bareTextRefusal = (n) => {
  const host = shadowHost(n.getRootNode());
  const at = host
    ? `<${host.localName}${host.id ? ` id="${host.id}"` : ""}>`
    : "a module";
  return new Error(
    `${at} staged bare text into a shadow root: ` +
      `${JSON.stringify(n.data.trim().slice(0, 40).trim())} has no element over it, ` +
      `so the page holds no block, cell or fence for it. Give a module's rendered ` +
      `words an element to sit in.`,
  );
};
/** @param {Node} n @returns {Element} */
export const elementOver = (n) => {
  if (n.parentElement) return n.parentElement;
  if (isText(n)) throw bareTextRefusal(n);
  throw new Error("A passage node has no element over it");
};
// The walk asks it of a declared root before crossing in, and the refusal is final: the
// root is refused for good (`refuseShadowRoot`, shadow.js), and from then on every walk,
// this one included, reads its host as it reads a host whose root the registry does not
// declare, by the host's own children, which are the words the file holds. So the page
// refuses the text once, here, whichever reader reaches it first, and no reader meets it
// again. Thrown out of each reader instead, it was refused again on every repaint frame,
// key and selection, each an uncaught error and each a report. The one refusal is
// reported to the agent here, and before the page upgrades it is also the page's
// startup failure, its own fault, which no server update fixes: it is declared
// (`lf-startup-failed`, `page`), so the readable fallback shows at once, the notice says
// the page has a problem, and the page never presents (leaf.js). A page already
// upgraded keeps running without those words, and without the root: a mark or a
// projection painted into it is never cleared, and an id inside it stops resolving,
// since every sweep of declared roots (`shadowRootsIn`) has dropped it.
/** @param {ShadowRoot} root */
function refusesBareText(root) {
  const bare = [...root.childNodes].filter(isText).find((node) => node.data.trim());
  if (!bare) return false;
  refuseShadowRoot(root);
  const refusal = bareTextRefusal(bare);
  reportPageError(refusal);
  if (!pageUpgraded())
    window.dispatchEvent(
      new CustomEvent("lf-startup-failed", {
        detail: { reason: refusal.message, error: refusal, page: true },
      }),
    );
  return true;
}
// Startup asks every declared root the page reading would cross into before the page
// upgrades, so a page whose module staged bare text never presents even when nothing
// has read the page's words yet: a reading is taken only when something needs one, and
// a page with no comment to find again presents without one. Like the walk, it crosses
// into a root only once every root over it is admitted, outer first; a refused root's
// host reads by its light children, so the stages inside that root are never asked.
// One pass over the stages, each root's answer kept, so startup stays linear in them.
export function refuseBareText() {
  /** @type {Map<Node, boolean>} */
  const admitted = new Map();
  /** @param {Element} host */
  const reached = (host) => {
    const over = host.getRootNode();
    return over === document ? document.body.contains(host) : admits(over);
  };
  /** @param {Node} tree @returns {boolean} */
  const admits = (tree) => {
    let answer = admitted.get(tree);
    if (answer === undefined) {
      const host = shadowHost(tree);
      answer =
        host !== null &&
        declaredRoot(host) === tree &&
        reached(host) &&
        !leafSurface(host) &&
        !refusesBareText(/** @type {ShadowRoot} */ (tree));
      admitted.set(tree, answer);
    }
    return answer;
  };
  for (const stage of liveStages()) admits(stage);
}
// The widget a reading belongs to. `.lf-ui` says the runtime built this rather than the
// author, and a reading rooted at the document takes that straight: everything the layer
// holds is the layer's, which is the whole of what the anchor pass and the authored
// reading need. Inside a widget it is a different sentence, and the widget is where it changes.
//
// A widget riding a message stands inside the floating panel, so the panel is `.lf-ui`
// over every word it says — and read straight, a question an agent asked in a reply says
// nothing whatever. That silence did not read as one: it read as an empty slot, so the
// group named its options by their ids in the accessibility tree, On Me named the
// question by its id, and every widget reading its own words in a message got "" and fell
// back to something else.
//
// So chrome between the words and their widget is that widget's own apparatus, and chrome
// above the widget is somebody else's. Rooting the search at the element handed in says
// almost the same thing and is wrong in one case that matters: a reading can start
// *inside* generated chrome, and everything generated over it would read as authored.
//
// A message is the other frame. Its body, the markup its writer sent and the text the
// runtime renders from their words, is a document of its own (`authoredScope`) standing
// inside the chrome that draws the message, so the body frames a reading there as a
// widget does, and the words read as their writer's: a heading in a reply names what
// follows it there. The version diff once read every block on the live page, a
// conversation's paragraphs among them, and so took a reader's comments for the page's
// words; it compares versions' sources now (version.js, `paintedSource`) and reads no
// message.
/** @param {Node | null} node */
const frameOf = (node) => {
  for (let a = isElement(node) ? node : upFrom(node); a; a = upFrom(a))
    if (a.localName?.startsWith("lf-") || a.matches(MESSAGE_BODY)) return a;
  return null;
};
// What a reading carries down to the text under an element. Every question the walk
// asks of a text node is a question about the elements over it, and each is one rule
// read at one element (`enter`): whether it is chrome or a declared label, the nearer
// deciding (`uiInside`'s rule); whether it silences what it holds (`silences`); whether
// an upgrade generated it (`GENERATED`); which generated element and which text block
// the words stand in, and which element they are read in (`words`); and whether it is
// one of the passage cells `pageText` fences on.
// Carried down, each element answers once for everything under it; asked per text node,
// the same answers came from a climb apiece, most of them to the body.
//
// Three of the facts stop at a shadow boundary and the rest cross it, because that is
// how the readings they carry are defined: `closest` for chrome, silence and the
// generated marks, the climb through hosts (`closestAcross`, `upFrom`) for blocks, the
// element words are read in and cells. A declared root therefore starts its tree-local facts over (`crossed`).
//
// The same rules asked of one element are `contextAt`: the element's ancestors folded
// through `enter` from the top. A walk starts from it at its root, and the reading
// watcher asks it where a change landed (`readsIn`), so what the reading skips and what
// it ignores changing are one rule, run in two directions.
/** @type {ReadingContext} */
const NO_CONTEXT = Object.freeze({
  chrome: false,
  silenced: false,
  generated: false,
  gen: null,
  block: null,
  textBlock: null,
  words: null,
  island: null,
  cells: null,
});
// The markers are the selectors the point readings climb with — `UI_MARKS` and `SAID`
// (shadow.js, `uiInside`), `GENERATED` (`authored`), `GEN`, `ISLAND`, `TEXT_BLOCK` — and
// the walk asks each of one element with `matches`, so a marker added to a selector
// reaches both. `MARKS` joins the attribute markers, so an element whose attributes are
// only a class or an id is settled by one match.
const GEN = "[data-lf-gen]";
const ISLAND = "[data-lf-markdown-words]";
const MARKS = [UI_MARKS, GENERATED, ISLAND].join(", ");
const BLOCK_TAGS = new Set(TEXT_BLOCK.split(","));
// A projected datum is independently addressable, even when its rows share one pre.
// A closer paragraph or other text block still supplies the datum's reading grain.
const BLOCKS = `${TEXT_BLOCK}, ${DATUM}`;
// `uiInside`'s rule at one element: true where it starts chrome, false where a declared
// label starts the page's words again inside chrome, null where it starts neither.
/** @param {Element} el */
const chromeMark = (el) => (el.matches(UI_MARKS) ? !el.matches(SAID) : null);
// What no label can speak through, however it is marked: an inline script, the
// stylesheet a rendered diagram carries inside its <svg>, and a slot the user's
// decision took off the page, or a native field's default-value markup. Chrome is the rest of what the anchor pass skips and
// the one part a label yields — it is a look, and a look cannot make a word the
// runtime's.
const SILENT_TAGS = new Set(["script", "style", "textarea"]);
/** @param {Element} el */
const silences = (el) => SILENT_TAGS.has(el.localName) || retiredSlot(el);
// A generated element whose words the file cannot model: one the registry does not
// declare as an `x-says` edge of the element holding it. Controls and the hidden comment
// count hold no accepted text, and x-says spans are already in the file-side reading.
/** @param {Element} el */
const unmodelled = (el) => {
  const attr = el.getAttribute("data-lf-said");
  const parent = el.parentElement;
  return !(attr && parent && registry[parent.localName]?.["x-says"]?.[attr]);
};
// Automatic control capture uses authored or registry-declared words, never the
// mutable value of a native editing host. A user's actual Range remains readable.
/** @param {readonly Segment[]} segments */
export const fileModelsPassage = (segments) =>
  segments.every(
    ({ node, gen }) => !isEditing(elementOver(node)) && (!gen || !unmodelled(gen)),
  );
// A cell candidate: an opaque widget or one of its original direct children, which
// always fence, or an unmodelled generated element, which fences once a word of the
// page's reading is its own (`indexed`).
/** @param {Element} el */
const opaque = (el) => passageFences.has(el);
// Editing values and readonly islands inside them are separate passage cells.
// Capture and resolution both stop context at those native ownership boundaries.
/** @param {Element} el */
const editingBoundary = (el) => isEditing(el) !== isEditing(el.parentElement);
/** @param {Element | null} el */
const isEditing = (el) => el !== null && isHTML(el) && el.isContentEditable;
// Whether an element stands within a line of words: HTML's phrasing content
// (`$passages.phrasing`), or a widget declared to stand among the words around it
// (x-inline). Every other element, a widget included, starts a block of its own, its
// words parted from those around it (`enter`), and ends a run-in title's line
// (`runsIntoLine`).
/** @param {Element} element */
const phrasing = (element) =>
  PHRASING.has(element.localName) || Boolean(registry[element.localName]?.["x-inline"]);
// One element's rules applied to the context over it. `inFrame` is false only for a
// point query's ancestors above the reading's frame, where chrome and the generated
// marks are somebody else's (`frameOf`). An element that starts nothing — most spans,
// links and wrappers — hands its parent's context down unchanged.
//
// `words` is the element the words under it are read in: the nearest one whose words
// are not the words beside it, which every element is but those a line of words runs
// through (`phrasing`). Two runs of words read in
// different elements are parted by a space, so two widgets side by side read apart,
// whatever tree their words are drawn in. Two read in one meet at an edge, a place a
// word may end (`scan`): only the page's CSS says whether `<span>one</span><span>two</span>`
// shows one word or two, so a quote finds it either way.
/** @param {ReadingContext} ctx @param {Element} el @param {boolean} [inFrame] @returns {ReadingContext} */
function enter(ctx, el, inFrame = true) {
  const marked = el.hasAttributes() && el.matches(MARKS);
  const textBlock = BLOCK_TAGS.has(el.localName);
  const block = textBlock || el.matches(DATUM);
  const editing = editingBoundary(el);
  const cell = opaque(el) || editing || (marked && el.matches(GEN) && unmodelled(el));
  const silent = !ctx.silenced && silences(el);
  const apart = !phrasing(el);
  if (!marked && !block && !cell && !silent && !apart) return ctx;
  const chrome = (marked && inFrame ? chromeMark(el) : null) ?? ctx.chrome;
  const generated = ctx.generated || (marked && inFrame && el.matches(GENERATED));
  return {
    chrome,
    silenced: ctx.silenced || silent,
    generated,
    gen: marked && el.matches(GEN) ? el : ctx.gen,
    block: block ? el : ctx.block,
    textBlock: textBlock ? el : ctx.textBlock,
    words: apart ? el : ctx.words,
    island: marked && el.matches(ISLAND) ? el : ctx.island,
    cells: cell ? { el, editing, up: ctx.cells } : ctx.cells,
  };
}
// The tree-local facts start over inside a declared shadow root, as `closest` does.
/** @param {ReadingContext} ctx @returns {ReadingContext} */
const crossed = (ctx) => ({
  ...ctx,
  chrome: false,
  silenced: false,
  generated: false,
  gen: null,
});
// Every fact at one element, climbing rather than carrying: its ancestors, host by host,
// folded through `enter` from the top, the tree-local facts starting over at each shadow
// root. Chrome and the generated marks count from `frame` down.
/** @param {Element | null} el @param {Element | null} frame @returns {ReadingContext} */
function contextAt(el, frame) {
  const over = [];
  for (let a = el; a; a = upFrom(a)) over.push(a);
  let ctx = NO_CONTEXT;
  let inFrame = !frame;
  for (const a of over.reverse()) {
    if (a === frame) inFrame = true;
    if (a.parentNode?.nodeType === Node.DOCUMENT_FRAGMENT_NODE) ctx = crossed(ctx);
    ctx = enter(ctx, a, inFrame);
  }
  return ctx;
}
// A whole text node as a segment of the context it stands in. Its block is `blockAt`'s
// answer, carried.
/** @param {Text} node @param {ReadingContext} ctx @returns {Segment} */
const segmentIn = (node, ctx) => ({
  node,
  start: 0,
  end: node.data.length,
  block: ctx.block ?? (ctx.island ? upFrom(ctx.island) : null),
  textBlock: ctx.textBlock ?? (ctx.island ? upFrom(ctx.island) : null),
  words: ctx.words,
  gen: ctx.gen,
});
// Which text each named reading keeps. `says` skips the runtime's own words and whatever
// is silenced; `wrote` skips everything an upgrade generated, a declared label included.
// `unsilenced` is `says` with nothing silenced, for the one reader asking whether words
// the page silences are still on screen (render-checks, `retiredSlots`). Like every
// reading its chrome is bounded at the root's frame, so chrome above that widget is not
// its apparatus: a settled slot under a bare `.lf-ui` ancestor still shows its words.
/** @satisfies {Record<string, (ctx: ReadingContext) => boolean>} */
const READINGS = {
  says: (ctx) => !ctx.chrome && !ctx.silenced,
  wrote: (ctx) => !ctx.generated,
  unsilenced: (ctx) => !ctx.chrome,
};
// The `wrote` reading asked of one node: whether it is authored, within the frame `root`
// stands in. Revision installs ask it of every node they place, so it climbs natively
// with the selector `enter`'s generated test is the element form of.
/** @param {Node} root */
export const authored = (root) => {
  const frame = frameOf(root);
  return (/** @type {Node} */ n) =>
    !overIn(isElement(n) ? n : elementOver(n), GENERATED, frame);
};
// The composed tree, not the light one: a widget that renders the page's words into an
// open shadow root (x-shadow) shows the user what its shadow tree holds, and a host's
// own children stop rendering the moment it has one. A TreeWalker sees none of that — it
// stops dead at the boundary — so the walk is written out, and it is the same walk in
// both directions: a host's shadow root stands in for its children, a <slot> in a shadow
// tree stands for what was assigned to it, and everything else is the light DOM it
// always was. Nothing
// here asks which widget it is looking at; a document with no shadow roots in it walks
// exactly as it did before.
//
// The order is what earns the recursion. `pageText` builds one string in reading order
// and indexes every position into it, so shadow text has to arrive at the host's own
// place in that string — not appended from a second walk, which would put a diff's lines
// after the page's last paragraph and every neighbour of theirs a lie.
//
// A slotted node reads in its light context, which is its host's: the hosts and slots the
// walk passed keep the context they carried, and a node assigned from anywhere else (a
// flattened fallback, a host above the root) is asked where it stands.
// A visible <br> contributes a separator even though it has no text node of its own.
//
// `readingParent`, below, climbs the tree this walk comes down, so a root or a slot this
// walk treats differently changes there too.
//
// `skip` answering true leaves an element out. It is handed the context the element
// stands in, so a reader that leaves an element out by what the reading counts there
// asks the walk's own answer, the context the element opens (`enter`).
//
// `frame` is where chrome and the generated marks start counting (`frameOf`). The page
// reading counts them from the top whatever root it reads, so a part of it read alone
// says what the whole says there.
/** @param {Node} root
 * @param {(node: Text, ctx: ReadingContext) => void} onText
 * @param {((element: Element, ctx: ReadingContext) => boolean) | null} [skip]
 * @param {((ctx: ReadingContext, br: Element) => void) | null} [onBreak]
 * @param {((element: Element, ctx: ReadingContext, entering: boolean) => void) | null} [onElement]
 * @param {Element | null} [frame] */
function walk(
  root,
  onText,
  skip = null,
  onBreak = null,
  onElement = null,
  frame = frameOf(root),
) {
  /** @type {Map<Element, ReadingContext>} */
  const passed = new Map();
  /** @param {Node} node */
  const contextOver = (node) => {
    const over = elementOver(node);
    return passed.get(over) ?? contextAt(over, frame);
  };
  /** @param {Element} child @param {ReadingContext} ctx */
  const visitElement = (child, ctx) => {
    if (!skip?.(child, ctx)) enterElement(child, enter(ctx, child));
  };
  // An element entered with the context it opens. A root handed in is entered exactly
  // as a descendant is, so a slot reads what is assigned to it, not its fallback, and a
  // host its declared tree.
  /** @param {Element} child @param {ReadingContext} inner */
  const enterElement = (child, inner) => {
    if (child.localName === "br") {
      onBreak?.(inner, child);
    } else if (isHTML(child, "slot") && shadowHost(child.getRootNode())) {
      // A slot draws what is assigned to it only in a shadow tree; anywhere else it is
      // an ordinary element, and its children are what it draws.
      passed.set(child, inner);
      onElement?.(child, inner, true);
      // In its light context, but read among the words where the slot draws it.
      /** @param {Node} node */
      const drawn = (node) => ({ ...contextOver(node), words: inner.words });
      for (const assigned of child.assignedNodes({ flatten: true }))
        isText(assigned)
          ? onText(assigned, drawn(assigned))
          : isElement(assigned) && visitElement(assigned, drawn(assigned));
      onElement?.(child, inner, false);
    } else {
      // Assigned elements enter their own declared root exactly as ordinary
      // children do. An undeclared root remains opaque to the page reading.
      const declared = declaredRoot(child);
      if (declared && !refusesBareText(declared)) {
        passed.set(child, inner);
        visit(declared, crossed(inner), child);
      } else visit(child, inner);
    }
  };
  /** @param {Node} node @param {ReadingContext} ctx @param {Element | null} [host] */
  const visit = (node, ctx, host = null) => {
    const element = host ?? (isElement(node) ? node : null);
    if (element) onElement?.(element, ctx, true);
    for (let child = node.firstChild; child; child = child.nextSibling) {
      if (isText(child)) {
        if (node.nodeType !== Node.ELEMENT_NODE && !child.data.trim()) continue;
        // A shadow root's own text has no element over it, which elementOver refuses:
        // a root the walk crosses into was asked first, so this is a root handed in.
        if (node.nodeType !== Node.ELEMENT_NODE) elementOver(child);
        onText(child, ctx);
      } else if (isElement(child)) visitElement(child, ctx);
    }
    if (element) onElement?.(element, ctx, false);
  };
  // A declared tree handed in as the root reads where its host stands, its tree-local
  // facts starting over as they do when the walk crosses into it; the document starts
  // with nothing over it.
  const host = shadowHost(root);
  if (isElement(root)) enterElement(root, contextAt(root, frame));
  else visit(root, host ? crossed(contextAt(host, frame)) : NO_CONTEXT);
}
// The step up the tree `walk` comes down, from any node, read or not. A slot is that step
// only in a declared root, the one kind of root `walk` crosses into. Another root's slots
// can show its host's children out of their light order, and `walk` and a native Range
// both still take them in light order, so the reading's segments are in `readingOrder`
// where they need not be in `renderedOrder`. A boundary point inside such a root, where
// Firefox puts a selection of words only that root shows, comes before all its host's
// children (`alongClimb`), so a range with both ends in it covers none of them.
/** @param {Node} node @returns {Node | null} */
export const readingParent = (node) => {
  const slot = isElement(node) || isText(node) ? node.assignedSlot : null;
  const host = slot && shadowHost(slot.getRootNode());
  return host && declaredRoot(host) ? slot : composedParentNode(node);
};
// The same step down, element by element, as `walk` takes it: a slot's assigned
// elements where it stands in a shadow tree, a host's declared tree in place of its
// children, and an element's own.
/** @param {Element} element @returns {Element[]} */
export const readingChildren = (element) =>
  isHTML(element, "slot") && shadowHost(element.getRootNode())
    ? /** @type {HTMLSlotElement} */ (element).assignedElements({ flatten: true })
    : [...(declaredRoot(element) ?? element).children];
const { order: readingOrder, under: readingUnder } = alongClimb(readingParent);
// Whether a node is inside another, or is it, in the tree the walk reads: a slot holds
// what is assigned to it, and a declared root's host what the root holds. Native
// `contains` stops at the first and is wrong for the second.
export { readingUnder };
// One named reading's segments under `root`, carrying their reading block (`blockAt`),
// typographic text block and generated element (`gen`, the nearest `[data-lf-gen]`
// in their tree).
// `boundary(element, segmentsSoFar)` answering true leaves that element's words out of
// the walk, for a reader that stands something else in their place (render-checks,
// `shownVerbatim`). The lines format also carries computed block boundaries and
// whitespace; ordinary passage readings never ask the browser for these styles.
// `drawn` keeps only the words the page draws now (`drawsWithin`), asked of each word and
// break as the walk meets it, so a break before a word left out still stands before the
// next; `until` ends the reading where that element starts. A reader that shows no more
// than the start of what it reads bounds it (`excerpt`): `upTo` characters other than
// whitespace, and in the lines format `lines` line breaks. The reading ends where either is
// met, cutting the text it ends in there, so a long block costs what the reader shows
// rather than what the block holds; and where a word still follows, the segment it ended
// in says so (`cut`), found by reading on to that one word.
/** @param {Node} root @param {Reading} [reading]
 * @param {((element: Element, count: number) => boolean) | null} [boundary]
 * @param {"prose" | "lines"} [format]
 * @param {{drawn?: boolean, until?: Element | null, upTo?: number, lines?: number}} [only]
 * @returns {Segment[]} */
export function textNodesUnder(
  root,
  reading = "says",
  boundary = null,
  format = "prose",
  only = {},
) {
  const keeps = READINGS[reading];
  const draws = only.drawn ? drawnHere() : null;
  let ended = false;
  // What the reader's bounds still allow: characters other than whitespace, and line
  // breaks; and whether one was met, after which the next word says the reading was cut.
  let wanted = only.upTo ?? Infinity;
  let breaks = format === "lines" ? (only.lines ?? Infinity) : Infinity;
  let met = false;
  /** @type {Segment[]} */
  const segments = [];
  // A word after `from` in `text`, which says a bound met there cut the reading short.
  /** @param {string} text @param {number} from */
  const wordAfter = (text, from) => {
    const word = /\S/gu;
    word.lastIndex = from;
    return word.test(text);
  };
  const cutShort = () => {
    const last = segments.at(-1);
    if (last) last.cut = true;
    ended = true;
  };
  let breakBefore = false;
  let lineBefore = "";
  const styles = new Map();
  /** @param {Element} element */
  const style = (element) => {
    let value = styles.get(element);
    if (!value) styles.set(element, (value = getComputedStyle(element)));
    return value;
  };
  walk(
    root,
    (node, ctx) => {
      if (ended || !keeps(ctx) || (draws && !draws(node))) return;
      // Read once: an engine may copy a long node's text on every read of `data`.
      const text = node.data;
      if (met) {
        if (wordAfter(text, 0)) cutShort();
        return;
      }
      const whiteSpace =
        format === "lines"
          ? style(node.assignedSlot ?? elementOver(node)).whiteSpaceCollapse
          : "";
      let end = text.length;
      if (
        breaks !== Infinity &&
        lineBefore === "\n" &&
        segments.length &&
        --breaks === 0
      ) {
        met = true;
        if (wordAfter(text, 0)) cutShort();
        return;
      }
      const newlines =
        breaks !== Infinity &&
        ["preserve", "break-spaces", "preserve-breaks"].includes(whiteSpace);
      if (wanted !== Infinity || newlines) {
        const marks = newlines ? /\S|\n/gu : /\S/gu;
        for (let mark; (mark = marks.exec(text));) {
          const line = mark[0] === "\n";
          if (line ? --breaks > 0 : --wanted > 0) continue;
          end = line ? mark.index : marks.lastIndex;
          met = true;
          break;
        }
      }
      segments.push({
        ...segmentIn(node, ctx),
        end,
        breakBefore,
        ...(format === "lines" && { lineBefore, whiteSpace }),
      });
      breakBefore = false;
      lineBefore = "";
      if (met && wordAfter(text, end)) cutShort();
    },
    (child) =>
      (ended ||= child === only.until) ||
      ((root === document || root === root.ownerDocument?.body) &&
        child.matches(LEAF_SURFACE)) ||
      (boundary?.(child, segments.length) ?? false),
    (ctx, br) => {
      if (!ended && keeps(ctx) && (!draws || draws(br))) {
        breakBefore = true;
        lineBefore = "\n";
      }
    },
    format === "lines"
      ? (element, ctx, entering) => {
          if (!keeps(ctx)) return;
          const display = style(element).display;
          if (display === "table-cell") {
            if (!entering && lineBefore !== "\n") lineBefore = "\t";
          } else if (
            /^(block|flow-root|list-item|flex|grid|table|-webkit-box)/.test(display)
          ) {
            lineBefore = "\n";
          }
        }
      : null,
  );
  return segments;
}

// getElementById searches the document tree alone, which is the same boundary again and
// the one every question the runtime asks by id runs into: which element an anchor names,
// what an action rests on, which unit a fold paints, which obligation a key steps to. A widget
// that stages its authored children into a shadow tree takes their ids in there with it,
// and each of those answers would come back null and quietly do nothing — the anchor
// captured, the mark never painted, no error anywhere. The document first, because that
// is where everything but a staged widget's own parts lives, and only the roots the
// registry declares after it, so the walk sees what the capture saw.
//
// `root` narrows the search to one authored document (`authoredScope`), with the roots
// declared inside it.
/** @param {string | null | undefined} id @param {Document | Element | null} [root] */
export const elementById = (id, root = document) => {
  if (id == null || root === null) return null;
  const page = root === root.ownerDocument?.body;
  /** @param {Element | null | undefined} node */
  const accepts = (node) =>
    node && (!page || (!leafSurface(node) && authoredScope(node) === root));
  const found =
    root === document
      ? document.getElementById(id)
      : [...root.querySelectorAll(`[id="${CSS.escape(id)}"]`)].find(accepts);
  if (found && accepts(found)) return found;
  for (const shadow of shadowRootsIn(root)) {
    const inside = shadow.getElementById(id);
    if (accepts(inside)) return inside;
  }
  return null;
};

// The root of the authored document a node stands in. A message's widget markup is a
// document of its own, placed in that message's body; the page owns the authored body.
// Runtime surfaces share that body, so page-scoped identity and membership exclude
// LEAF_SURFACE. Geometry separately reads `layoutBox`, the semantic main's Layout.
// `doc` may be a parsed revision whose body holds its authored source.
export const pageDocument = (doc = document) => doc.body;
/** @param {Node | null | undefined} node */
export const inPage = (node) => under(node, pageDocument()) && !leafSurface(node);
// Whether focus, standing at `at`, names the page: only on something in it. The body is
// in the page, yet it is where a click on words and a let-go leave focus, which leaves
// the answer to the place the user last acted in. A Leaf surface stands where its owner
// seated it: a comment editor in a widget's outlet stands in the widget, so it is in the
// page; the field Copy appends to the body stands on the body, and the chrome after it on
// `html`, so neither is.
/** @param {Element | null} at */
export const focusInPage = (at) => {
  /** @type {Node | null} */
  let seat = at;
  for (let surface = leafSurface(seat); surface; surface = leafSurface(seat))
    seat = composedParentNode(surface);
  return seat !== document.body && inPage(seat);
};
// The box the page's Layout arranges: `main`, or the shown child of a `main` that carries
// no Layout itself (layouts.css, `--lf-layout-box`). The margin, the rail and the
// Layout's regions read this box; the authored content is still `pageDocument`.
/** @param {Element} box */
const isLayoutBox = (box) =>
  getComputedStyle(box).getPropertyValue("--lf-layout-box").trim() === "1";
/** @param {Element} box */
const isLayoutShell = (box) =>
  getComputedStyle(box).getPropertyValue("--lf-layout-shell").trim() === "1";
// Read off `main`'s children rather than by `:scope >`, which walks every element under
// `main` to find one of its children, several times for each keystroke.
/** @param {Element} main */
const partsOf = (main) =>
  [...main.children].find((child) => child.matches('[data-lf-views="parts"]')) ?? null;
export const layoutBox = () => {
  const main = document.querySelector("body > main");
  if (!main || isLayoutBox(main)) return main;
  const parts = partsOf(main);
  // Only a shell holds a layout box, so a `main` of plain sections is read once, not once
  // for each section (layouts.css, `--lf-layout-shell`).
  const boxes = [main, ...(parts?.children ?? [])]
    .filter(isLayoutShell)
    .flatMap((shell) => [...shell.children]);
  return boxes.find((box) => box.checkVisibility() && isLayoutBox(box)) ?? main;
};
// A page of parts' views: the parts a `main` with no Layout of its own shows one at a
// time (layouts.css, "A page of parts"), or null on any other page.
export const layoutParts = () => {
  const main = document.querySelector("body > main");
  return main && !isLayoutBox(main) ? partsOf(main) : null;
};

/** @param {Node} node */
export const authoredScope = (node) =>
  closestAcross(node, MESSAGE_BODY) ?? pageDocument(node?.ownerDocument ?? document);

// elementFromPoint retargets to the host for a point over a shadow tree, so it names the
// widget rather than the thing in it, and each root answers for its own. Mark hit testing
// and item aim both use this exact reading, so a projected datum inside a declared shadow
// tree can outrank its host. Only a declared root is entered: another library's tree is
// its control's insides, whose ids (Web Awesome Copy's `#copy-button`) the page never
// authored, so the hit stays at the control.
/** @param {number} x @param {number} y */
export const elementFromPointAcross = (x, y) => {
  let el = document.elementFromPoint(x, y);
  for (let root; el && (root = declaredRoot(el));) {
    const inner = root.elementFromPoint(x, y);
    if (!inner || inner === el) break;
    el = inner;
  }
  return el;
};

// A pass that clears its own marks before repainting has to sweep everywhere it can
// write, and `elementById` above is what widened that: a mark placed on a staged element
// sits in a tree `document.querySelectorAll` never enters, so the clear would miss it and
// the mark outlive the reason for it. The runtime's own marks are read back this way, and
// so is a control the user can focus, for the same reason: both are wherever the
// markup ended up. Which widgets the page holds is a different question and still the
// document's:
// a widget staged inside another's tree is a nesting the registry's x-owners contract
// does not model, and answering it here would be inventing that contract in a sweep.
/** @template {Element} [E=Element] @param {string} selector @returns {E[]} */
export const pageQueryAll = (selector) =>
  [document, ...pageShadowRoots()].flatMap((root) => {
    /** @type {NodeListOf<E>} */
    const elements = root.querySelectorAll(selector);
    return [...elements];
  });

// A native Range compares one DOM tree. Its light-DOM endpoints can sit inside a declared
// root's slots, where retargeting every shadow word to its host also selects the host's
// unrelated header. Compare boundary points in the reading's order instead, the order
// `segmentsIn` searches.
/** @param {Node} node @param {Node} container @param {number} offset */
const beforePoint = (node, container, offset) => {
  if (node === container) return false;
  if (container.nodeType === Node.TEXT_NODE || offset === 0)
    return readingOrder(node, container) < 0;
  const next = container.childNodes[offset];
  return next
    ? readingOrder(node, next) < 0
    : readingUnder(node, container) || readingOrder(node, container) < 0;
};
// The first index from `from` whose item passes `test`, where `test` fails for every
// item before that index and passes for every one after it. The reading holds its
// segments, and the frame its marks, in `readingOrder`, so a test of whether one falls
// after a point in that order has this form, and a binary search answers it in about
// twenty comparisons on a page of two million segments.
/** @template T @param {readonly T[]} items @param {(item: T) => boolean} test
 * @param {number} [from] */
function firstPassing(items, test, from = 0) {
  let lo = from;
  let hi = items.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (test(/** @type {T} */ (items[mid]))) hi = mid;
    else lo = mid + 1;
  }
  return lo;
}

// The page reading's segments a range covers, in reading order, clipped to where it
// starts and ends: in each piece it touches, from the first segment that is not before
// its start up to the first that is not before its end, and that one too where it is the
// end's own text node. A range with both ends in one part touches that part alone, as a
// passage in a datum is captured in its datum's words (anchor-resolution.js), so
// selecting a line of one document reads that document. Any other touches the frame and
// the parts it covers, with the part its start stands in. The frame's marks are in
// reading order, so the parts it covers run from the first mark not before its start to
// the first not before its end, with the start's part just before them, and finding them
// costs a binary search however many parts the page holds. A walk from the range's own
// root reads whatever that root holds: select-all beside an x-shadow widget composes a
// range over <html>, and the reading has no position for its <title>.
/** @param {AbstractRange} range */
export function segmentsIn(range) {
  catchUpReading();
  const { startContainer, startOffset, endContainer, endOffset } = range;
  /** @param {Node} node */
  const fromStart = (node) => !beforePoint(node, startContainer, startOffset);
  /** @param {Node} node */
  const fromEnd = (node) => !beforePoint(node, endContainer, endOffset);
  /** @param {readonly Segment[]} segments @returns {[number, number]} */
  const spanOf = (segments) => {
    const first = firstPassing(segments, ({ node }) => fromStart(node));
    const stop = firstPassing(segments, ({ node }) => fromEnd(node), first);
    return [first, segments[stop]?.node === endContainer ? stop + 1 : stop];
  };
  /** @param {readonly Segment[]} segments */
  const clipped = (segments) => segments.slice(...spanOf(segments));
  const head = inPage(startContainer) ? readingPart(startContainer) : null;
  const tail = inPage(endContainer) ? readingPart(endContainer) : null;
  /** @type {Segment[]} */
  let segments;
  if (head && head === tail) segments = clipped(partCollected(head).segments);
  else {
    const { segments: own, marks } = frameCollected();
    const lo = firstPassing(marks, ({ root }) => fromStart(root));
    const hi = firstPassing(marks, ({ root }) => fromEnd(root), lo);
    const [first, stop] = spanOf(own);
    const runs = [];
    let at = first;
    for (const mark of marks.slice(marks[lo - 1]?.root === head ? lo - 1 : lo, hi)) {
      runs.push(own.slice(at, mark.at), clipped(partCollected(mark.root).segments));
      at = Math.max(at, mark.at);
    }
    runs.push(own.slice(at, stop));
    segments = runs.flat();
  }
  const covered = [];
  for (const segment of segments) {
    const { node } = segment;
    const start = node === startContainer ? startOffset : 0;
    const end = node === endContainer ? endOffset : segment.end;
    if (end > start) covered.push({ ...segment, start, end });
  }
  return covered;
}

// Segments as prose — what a comment stores as its quote, and what a reading position
// remembers. A space goes in wherever a block boundary falls between two segments, so a
// passage crossing two paragraphs doesn't read as one run-on word. Whitespace collapses,
// since the same passage carries the author's line wraps in the source and the rendering's
// on screen. Sliced by code point, because half a surrogate pair is a character no UTF-8
// file can hold. Where the spaces landed is cosmetic to the search: a quote's own
// whitespace is elastic to findQuote, so nothing downstream depends on this.
// The block a node reads as part of, and null where it belongs to no block of its own —
// which is a different answer from "its parent", and the two callers want different ones.
/** @param {Node | null} node */
export const blockAt = (node) => {
  const block = closestAcross(node, BLOCKS);
  if (block) return block;
  // A parsed Markdown island stands where one direct source text node stood.
  // Its nested emphasis and links must inherit that text node's parent, while
  // authored sibling elements keep their own boundaries.
  const island = closestAcross(node, ISLAND);
  return island ? upFrom(island) : null;
};
// The unit a segment's words are read as part of: its block as the walk carried it,
// else the element holding the text (the walk refuses text with none).
/** @param {Segment} segment */
export const segmentBlock = (segment) => segment.block ?? segment.node.parentElement;
// Whether the reading reads a space between two runs of words: a line break between
// them, or their being read in different elements (`enter`, `words`). passages.py reads
// the same.
/** @param {Segment} segment @param {Segment} previous */
const spacedFrom = (segment, previous) =>
  Boolean(segment.breakBefore) || segment.words !== previous.words;
// Whether the words the reading shows have a space between two runs: where it reads one
// (`spacedFrom`), and at an edge where two elements outside any text block meet, as a
// chip meets its title or a label its value, which a page most often draws apart; an
// edge inside a text block shows as nothing, as `set<em>up</em>` reads "setup". A quote
// of either spelling resolves the same (`scan`), and passages.py shows the same
// (`_write`).
/** @param {Segment} segment @param {Segment} previous */
const shownApart = (segment, previous) =>
  spacedFrom(segment, previous) ||
  (segment.textBlock ?? segment.node.parentElement) !==
    (previous.textBlock ?? previous.node.parentElement);
const COLLAPSIBLE = new RegExp(`^(?:${COLLAPSE.source})$`, "u");

// The normalized reading and, when requested, one DOM span for each character in it.
// A block boundary or explicit line break contributes the same collapsed space as
// authored whitespace, mapped to the start of the segment after it. Text and its DOM
// route come from this one walk,
// so a consumer that paints a reading cannot disagree with `quoteFrom` about its words.
// `visit` hears where each character stands and how much text precedes it, before the
// character is read: a space a collapsed run or a block's edge leaves goes in ahead of the
// next word, so it falls after that word's place. `after` continues a reading past the
// segment it names: the first segment's edge is weighed against it, and whitespace at the
// start owes a space as it would with words behind it. Where none stand behind, that space
// is at the reading's start, which a reader of a span drops.
/** @typedef {{node: Text, offset: number}} TextPoint
 * @typedef {{text: string, start: TextPoint, end: TextPoint}} TextUnit
 * @typedef {(node: Text, offset: number, length: number) => void} Visit */
/** @overload @param {readonly Segment[]} segments @param {false} mapCharacters @param {Visit} [visit] @param {Segment} [after] @returns {string} */
/** @overload @param {readonly Segment[]} segments @param {true} mapCharacters @returns {{text: string, units: TextUnit[]}} */
/** @param {readonly Segment[]} segments @param {boolean} mapCharacters @param {Visit} [visit] @param {Segment} [after] */
function readSegments(segments, mapCharacters, visit, after) {
  let text = "";
  /** @type {TextUnit[]} */
  const units = [];
  /** @type {{start: TextPoint, end: TextPoint} | null} */
  let pendingSpace = null;
  /** @param {string} character @param {TextPoint} start @param {TextPoint} end */
  const push = (character, start, end) => {
    if (COLLAPSIBLE.test(character)) {
      if (text || after)
        pendingSpace = pendingSpace
          ? { start: pendingSpace.start, end }
          : { start, end };
      return;
    }
    if (pendingSpace) {
      text += " ";
      if (mapCharacters) units.push({ text: " ", ...pendingSpace });
      pendingSpace = null;
    }
    text += character;
    if (mapCharacters) units.push({ text: character, start, end });
  };
  let previous = after;
  for (const seg of segments) {
    if (previous && shownApart(seg, previous)) {
      const point = { node: seg.node, offset: seg.start };
      push(" ", point, point);
    }
    let offset = seg.start;
    for (const character of seg.node.data.slice(seg.start, seg.end)) {
      const end = offset + character.length;
      visit?.(seg.node, offset, text.length);
      push(character, { node: seg.node, offset }, { node: seg.node, offset: end });
      offset = end;
    }
    previous = seg;
  }
  return mapCharacters ? { text, units } : text;
}
/** @param {readonly Segment[]} segments @param {Visit} [visit] */
export const quoteFrom = (segments, visit) => readSegments(segments, false, visit);
/** @param {readonly Segment[]} segments */
export const readingFrom = (segments) => readSegments(segments, true);
// Cutting one to length is the caller's business and always by code point: half a surrogate
// pair is a character no UTF-8 file can hold, and a quote is written to one.
/** @param {string} text @param {number} from @param {number} to */
export const cut = (text, from, to) => [...text].slice(from, to).join("");

// Copyable words use the same segments as prose, with the walk's computed line
// boundaries and whitespace. They need no DOM-coordinate map; quote readings above
// keep their own normalization unchanged.
/** @param {readonly Segment[]} segments */
function linesFrom(segments) {
  let text = "";
  let separator = "";
  for (const segment of segments) {
    if (segment.lineBefore && text)
      separator = segment.lineBefore === "\n" || separator === "\n" ? "\n" : "\t";
    const { whiteSpace } = segment;
    const collapses =
      whiteSpace === "preserve" || whiteSpace === "break-spaces"
        ? null
        : whiteSpace === "preserve-breaks"
          ? /[\t\r\f ]/
          : /[\t\n\r\f ]/;
    for (const character of segment.node.data.slice(segment.start, segment.end)) {
      if (collapses?.test(character)) {
        if (text && !text.endsWith("\n")) separator ||= " ";
        continue;
      }
      if (whiteSpace === "preserve-breaks" && character === "\n" && separator === " ")
        separator = "";
      text += separator + character;
      separator = "";
    }
  }
  return text;
}

// What an element says, read the way this file reads the page everywhere else. A widget
// wanting the words in one of its own slots asks for them here rather than through
// `textContent`, because the two differ: the paint pass writes a hidden line into any text
// block that carries a comment, including blocks inside a widget, and `textContent` returns
// it. A suggestion labelled that way offered to accept “Retry three times. 1 comment”.
// The lines format takes block boundaries and preserved whitespace from computed
// styles while the same composed walk determines which words belong to the page.
// `drawn` keeps only the words the page draws now, for a reader that shows them
// somewhere else, as a link's preview does, and `until` stops at an element
// (`textNodesUnder`).
/** @param {Node} el
 * @param {{format?: "prose" | "lines", drawn?: boolean, until?: Element | null}} [options] */
export const says = (el, options = {}) => {
  const segments = textNodesUnder(el, "says", null, options.format, options);
  return options.format === "lines" ? linesFrom(segments) : quoteFrom(segments);
};
/** The start of what an element says, as `says` reads it, for a reader that shows no
 * more than that: read no further than `upTo` characters other than whitespace and, in
 * the lines format, `lines` line breaks (`textNodesUnder`). `cut` is whether a bound ended
 * it with words still to follow, so the reader can say the place runs on.
 * @param {Node} el
 * @param {{format?: "prose" | "lines", drawn?: boolean, until?: Element | null, upTo?: number, lines?: number}} options
 * @returns {{text: string, cut: boolean}} */
export function excerpt(el, options) {
  const segments = textNodesUnder(el, "says", null, options.format, options);
  return {
    text: options.format === "lines" ? linesFrom(segments) : quoteFrom(segments),
    cut: segments.at(-1)?.cut === true,
  };
}
/** Whether authored words follow `title` on its line inside `container`, by the markup
 * alone: words its author wrote after it, before a `<br>`, an element outside phrasing
 * content (`phrasing`), or the end of a block holding the title. It is the walk's
 * reading throughout: its tree (a widget's declared tree, a slot's assignment, climbed
 * by `readingParent`), and what its `wrote` reading counts, so Leaf's own apparatus in a
 * widget's tree neither runs on nor ends the line. No style is read, so a line is the
 * same whatever the reader opens, hides or resizes.
 * @param {Element} title @param {Element} container */
export function runsIntoLine(title, container) {
  const counts = READINGS.wrote;
  let past = false;
  let ended = false;
  let follows = false;
  walk(
    container,
    (node, ctx) => {
      if (past && !ended && counts(ctx) && node.data.trim()) follows = ended = true;
    },
    (child, ctx) => {
      if (ended) return true;
      if (!past) {
        // What comes before the title holds none of its line, and its own words are no
        // part of it.
        if (child !== title) return !readingUnder(title, child);
        past = true;
        return true;
      }
      if (counts(enter(ctx, child)) && (isHTML(child, "br") || !phrasing(child)))
        ended = true;
      return ended;
    },
    null,
    (element, ctx, entering) => {
      if (
        !entering &&
        past &&
        element !== container &&
        counts(ctx) &&
        !phrasing(element) &&
        readingUnder(title, element)
      )
        ended = true;
    },
  );
  return follows;
}
// What the page draws now, by what the browser computes for the element each word is
// drawn in (its slot, its parent, or a shadow root's host), and for each break, the
// `<br>` itself, which `hidden` or `display: none` takes off the line while its parent
// stands; not by pruning the elements over it, since a word can be drawn where its
// parent is not. A closed
// disclosure's own words beside its summary are drawn in a tree the page can't see,
// which draws only the summary, so the disclosure answers for them. No primitive gives
// this reading: in Chromium and Firefox `innerText` keeps Leaf's own controls, reads a
// host's light children in their light order rather than its declared tree, and reads an
// unchosen tab's panel as nothing rather than whole; a Range's text keeps everything.
// Each element is asked once a reading.
const drawnHere = () => {
  /** @type {Map<Element, boolean>} */
  const asked = new Map();
  /** @param {Node} node */
  return (node) => {
    const holder = isElement(node) ? node : renderedParent(node);
    if (!holder) return false;
    let drawn = asked.get(holder);
    if (drawn === undefined)
      asked.set(
        holder,
        (drawn = !(isHTML(holder, "details") && !holder.open) && drawsWithin(holder)),
      );
    return drawn;
  };
};
/** Whether the page draws what `element` holds now, by what the browser computes: the
 * nearest box at or over it (`display: contents` makes none) is drawn
 * (`checkVisibility`) and shows what it holds rather than skipping it
 * (`content-visibility: hidden`, as an unchosen tab's `hidden="until-found"` panel and a
 * closed disclosure's body are), and, with `visibility`, `element` inherits
 * `visibility: visible`. What a `content-visibility: auto` box skips off screen is drawn
 * once scrolled to, by the same rules, so it is asked as it is, which styles what is
 * asked; what `hidden` skips is answered without styling it (shadow-tree.js, `skipper`).
 * @param {Element} element @param {boolean} [visibility] */
export function drawsWithin(element, visibility = true) {
  for (
    let box = /** @type {Element | null} */ (element);
    box;
    box = renderedParent(box)
  ) {
    if (box.checkVisibility())
      return (
        getComputedStyle(box).contentVisibility !== "hidden" &&
        (!visibility ||
          !/^(hidden|collapse)$/.test(getComputedStyle(element).visibility))
      );
    const skipping = skipper(box);
    if (skipping && getComputedStyle(skipping).contentVisibility !== "auto")
      return false;
    if (getComputedStyle(box).display !== "contents") return false;
  }
  return false;
}
// The other question, and a different answer: what the *author* wrote here, with
// everything an upgrade generated left out. A version comparison keys sources by it and
// paints a source's words onto the live block that reads the same; a widget asks it to name
// one of its own parts, where `says` would hand back the widget's own declared labels
// along with the words — a picked row's mark is the page speaking, so it is in the
// reading a user points at and out of the row's name.
/** @param {Node} el */
export const wrote = (el) => quoteFrom(textNodesUnder(el, "wrote"));

// A passage as one Range: what selects it, and what tells two passages' bounds apart.
// Both ends of a Range stand in one tree, so a passage that runs into a shadow tree, as
// the words of a declared stage stand at their host's place in the page's string, makes
// a range that collapses onto its end (DOM, "set the start or end"). What a passage's
// words are drawn in is its segments' own lines (`segmentLines`).
/** @param {readonly Segment[]} segments */
export function rangeOf(segments) {
  const first = segments[0];
  const last = segments.at(-1);
  if (!first || !last)
    throw new RangeError("A passage range needs at least one segment");
  const range = document.createRange();
  range.setStart(first.node, first.start);
  range.setEnd(last.node, last.end);
  return range;
}
// A passage's pieces in order: each segment, the block holding its words
// (`segmentBlock`) and the lines it is drawn in, wherever it stands, in the page's tree
// or a shadow tree. What clips a passage's lines, stands a mark over them or tells
// whether a point is on them reads each piece against its own block, since a passage
// runs across blocks and into shadow trees.
/** @param {readonly Segment[]} segments */
export const segmentPieces = (segments) =>
  segments.map((segment) => ({
    segment,
    block: segmentBlock(segment),
    lines: [...rangeOf([segment]).getClientRects()],
  }));
// Whether a character's box stands on a line after `line`, as lines follow one another
// along the block axis of the writing mode they are set in: down the page, or across
// it from the right or from the left.
/** @param {DOMRect} box @param {DOMRect} line */
const lineBelow = (box, line) => box.top >= line.bottom;
/** @param {DOMRect} box @param {DOMRect} line */
const lineLeft = (box, line) => box.right <= line.left;
/** @param {DOMRect} box @param {DOMRect} line */
const lineRight = (box, line) => box.left >= line.right;
/** @type {Record<string, typeof lineBelow>} */
const LINE_AFTER = {
  "vertical-rl": lineLeft,
  "sideways-rl": lineLeft,
  "vertical-lr": lineRight,
  "sideways-lr": lineRight,
};
// Where a passage starts: the first line the browser draws it on, which a passage is
// travelled to and asked whether it shows by, so a passage taller than the window, or
// one whose end alone shows, as one running into a shadow stage far below its start, is
// brought to where it is read from, and the whole of that line, a panel covering part
// of it included. Search, thread travel and the comment box all go there. Words the
// page draws no box for, as hidden ones, start no line. The line runs on through the
// segments after the first drawn one, as one set in an inline element of its own, until
// a character stands on a line after it, found in each segment by halving it a
// character's box at a time; it stops at a shadow root's edge, since a range is one
// tree's.
/** @param {readonly Segment[]} segments @returns {Segment[]} */
export function passageStart(segments) {
  const drawn = segments.findIndex((segment) =>
    [...rangeOf([segment]).getClientRects()].some((box) => box.width || box.height),
  );
  const at = Math.max(0, drawn);
  const first = segments[at];
  if (!first) return [];
  /** @param {Segment} segment @param {number} offset */
  const character = (segment, offset) =>
    rangeOf([{ ...segment, start: offset, end: offset + 1 }]).getBoundingClientRect();
  const mode = first.node.parentElement
    ? getComputedStyle(first.node.parentElement).writingMode
    : "horizontal-tb";
  const below = LINE_AFTER[mode] ?? lineBelow;
  const line = character(first, first.start);
  // A character the page draws no box for, as a hidden one, stands on no later line.
  /** @param {DOMRect} box */
  const after = (box) => Boolean(box.width || box.height) && below(box, line);
  const root = first.node.getRootNode();
  /** @type {Segment[]} */
  const start = [];
  for (const segment of segments.slice(at)) {
    const opening = segment === first;
    if (!opening && segment.node.getRootNode() !== root) break;
    if (!opening && segment.end > segment.start)
      if (after(character(segment, segment.start))) break;
    let low = opening ? segment.start + 1 : segment.start;
    for (let high = segment.end; low < high;) {
      const mid = (low + high) >> 1;
      if (after(character(segment, mid))) high = mid;
      else low = mid + 1;
    }
    start.push({ ...segment, end: low });
    if (low < segment.end) break;
  }
  return start;
}
// The lines a passage's words are drawn in, all its pieces' in order.
/** @param {readonly Segment[]} segments */
export const segmentLines = (segments) =>
  segmentPieces(segments).flatMap((piece) => piece.lines);
// The box around them, as `Range.getBoundingClientRect` gives one tree's range: around
// the lines with an area, else the first.
/** @param {readonly Segment[]} segments */
export function segmentsBox(segments) {
  const lines = segmentLines(segments);
  const drawn = lines.filter((line) => line.width || line.height);
  const box = union(drawn.length ? drawn : lines.slice(0, 1));
  return box ? new DOMRect(box.left, box.top, box.width, box.height) : new DOMRect();
}

// Find `quote` among `segments`; returns the segments it covers, or none. The quote's own
// whitespace is treated as elastic and the page's is not, which is the asymmetry the
// problem actually has. The same passage gets written down with a break where the source
// wrapped it, with one where the rendering broke a block, and with none where two blocks
// abut, so a gap in the quote has to match any gap in the page or none at all — otherwise
// every producer has to agree on whitespace, and that agreement is the one this file kept
// getting wrong. The converse is not true: where the quote runs two words together the
// page may not, or a short quote starts matching inside longer words — "never" finding the
// tail of "on every", in a different paragraph.
// So a gap has to match whitespace: the page's own, or the space the reading reads
// where a block ends or a line breaks (`quoteFrom`), which the raw text holds as one.
// An inline element's boundary is not a gap — `<span>one</span><span>two</span>` reads
// `onetwo`, as the file's reading does — but it leaves no character behind and may fall
// anywhere, so the raw text holds an edge for it, which a gap may run through and which
// may fall between the characters of a single word: `<strong>bold</strong>text` reads as
// one word and is quoted as one. Without that floor a gap could match nothing at all,
// so "set up" would find "setup" in an earlier sentence and anchor there for good.
const EDGE = "\u0000"; // no document holds one, so it can't collide with page text
// A quote names text, not a place, and a page is free to say the same thing twice. Where it
// does, the words on either side decide which occurrence was meant. A unified diff holds
// the same line on both sides by construction, so without this, commenting on a fixed line
// marked the broken one — the user's objection attached to the code they were objecting
// to, and stored that way. Section scoping cannot reach it, because both sides of a diff
// live under one id. Context rather than an offset: an offset goes stale silently when the
// page is revised, while neighbours can be checked against the page as it now stands — see
// `holds` for what checking them means, and what it deliberately refuses to do.
// Anchors written before this carry none: their quote resolves only when it has a
// single candidate, since there is no evidence that can identify one repeated copy.
// The way back from the reading to the page is its segments and where each one starts in
// `raw`: each segment carries its `rawStart` alongside its DOM coordinates,
// and the one raw character after each segment but the last is an EDGE. Every question
// of the form "which node and offset is raw[i]" goes through `segmentAt`.
//
// The last segment starting at or before `i`, or -1 before the first.
/** @param {PageReading} reading @param {number} i */
function segmentAt({ segments }, i) {
  return firstPassing(segments, (segment) => segment.rawStart > i) - 1;
}
// Where raw[i] came from, as `{node, offset, segment}`, or null for an EDGE or a position
// outside the reading.
/** @param {PageReading} reading @param {number} i @returns {Point | null} */
export function pointAt(reading, i) {
  const segment = reading.segments[segmentAt(reading, i)];
  if (!segment) return null;
  const offset = i - segment.rawStart;
  return offset < segment.end - segment.start
    ? { node: segment.node, offset: segment.start + offset, segment }
    : null;
}
// The characters of raw[lo..hi) as segments, so a neighbourhood can be read back with the
// same function that wrote it down. Edges hold no character and are simply absent.
/** @param {PageReading} reading @param {number} lo @param {number} hi @returns {Segment[]} */
function spanOf(reading, lo, hi) {
  const { segments } = reading;
  const out = [];
  let seg;
  for (let k = Math.max(0, segmentAt(reading, lo)); (seg = segments[k]); k++) {
    const from = seg.rawStart;
    if (from >= hi) break;
    const a = Math.max(lo, from);
    const b = Math.min(hi, from + seg.end - seg.start);
    if (b > a)
      out.push({
        ...seg,
        start: seg.start + a - from,
        end: seg.start + b - from,
        breakBefore: Boolean(seg.breakBefore && a === from),
      });
  }
  return out;
}
// Context identifies a passage only when its neighbours are still exactly what they were.
// A partial match is not weak evidence for the right copy — it is evidence the page moved
// on, and acting on it is how a comment ends up somewhere it was never made: a version that
// rewrote the sentence beside the anchored copy left an untouched copy elsewhere matching
// better, and the comment followed it there. Demanding the whole stored context prevents
// that: without one exact contextual match, only a quote with a sole candidate resolves;
// repeated candidates detach rather than inheriting document order.
//
// Rare, not impossible. The bar is however much was stored, and the capture reads the
// neighbours out of the reading the search uses: the whole document, where a section is a
// filter on where a passage may sit, not on what surrounds it, or a datum's own words
// (`pageText`). So both sides are full except against that reading's ends. Anchors written
// before context reached past the section carry a side clipped at that edge; they confirm
// at that shorter bar, which is the bar they were stored under.
//
// The bar is what the capture actually produces, not a number picked to fit: across every
// selection in the shipped examples, an unmodified page confirms its stored context in full.
//
// An empty side is the case worth stating, because reading it as an absent constraint is
// what sends a comment to a copy it was never made on. The capture reads the reading the
// search reads, so a side comes out empty only where the passage had nothing at all beside
// it there: the top or bottom of the page or of the datum, the one place no capture can
// give two sides to. That is not a missing constraint but the tightest one there is, and
// it is checkable — a candidate confirms it by also having nothing there, which exactly
// one occurrence does. Refusing to read it that way handed the last copy's mark to the
// first.
//
// A side is read from the words the reading keeps (`wordsBetween`), the words a fresh read
// of the span gives, until it holds as many code units as `want` — the unit endsWith
// compares in. Only copies that need telling apart are asked about, but a capture asks
// about every copy at each width it tries, and the copies of a repeated paragraph agree
// for thousands of characters before one differs.
//
// What a copy's sides were read from is kept on it (`near`), so the index of quotes
// asks them again only once a change lands there (`carry`).
//
// A side's letters (`letters`, `want` less its spaces) are compared first, outward from
// the copy through raw, and a letter that differs refutes it: the side's words hold the
// reading's letters there in order and nothing else but spaces, so no read of words can
// spell `want` past it, and only a change from that letter to the copy can make it. The
// copies of a word the user selected mostly differ in the letter beside them, so telling
// 17,000 of them apart costs about as many comparisons rather than reading every word
// around them.
/** @param {PageReading} reading @param {number} at @param {string} want @param {string} letters
 * @param {boolean} before @param {Copy} [copy] */
const holds = (reading, at, want, letters, before, copy) => {
  /** @param {number} lo @param {number} hi */
  const read = (lo, hi) => {
    if (copy)
      copy.near = copy.near
        ? [Math.min(copy.near[0], lo), Math.max(copy.near[1], hi)]
        : [lo, hi];
  };
  const differs = lettersDiffer(reading.raw, at, letters, before);
  if (differs) {
    read(...differs);
    return false;
  }
  const edge = fenceEdge(reading, at, before);
  // One character is all it takes to refute an empty side, and asking for none would answer
  // with none: doubling zero never grows.
  const enough = want.length || 1;
  for (let raw = 2 * enough; ; raw *= 2) {
    const lo = before ? Math.max(edge, at - raw) : at;
    const hi = before ? at : Math.min(edge, at + raw);
    const there = wordsBetween(reading, lo, hi);
    if (there.length >= enough || (before ? lo === edge : hi === edge)) {
      read(lo, hi);
      if (!want) return there === "";
      return before ? there.endsWith(want) : there.startsWith(want);
    }
  }
};
// The raw span from raw place `at` out to the first letter, read away from it, that is
// not `letters`' letter there, read the same way: before it for the words ahead of a
// copy, from it for those after. Null where raw spells all of them.
/** @param {string} raw @param {number} at @param {string} letters @param {boolean} before
 * @returns {[number, number] | null} */
function lettersDiffer(raw, at, letters, before) {
  let i = before ? at : at - 1;
  for (let k = 0; k < letters.length; k++) {
    if (before) while (--i >= 0 && kindOf(raw.charCodeAt(i)) !== 0);
    else while (++i < raw.length && kindOf(raw.charCodeAt(i)) !== 0);
    const wanted = letters.charCodeAt(before ? letters.length - 1 - k : k);
    if (i >= 0 && i < raw.length && raw.charCodeAt(i) === wanted) continue;
    return before ? [Math.max(i, 0), at] : [at, Math.min(i + 1, raw.length)];
  }
  return null;
}
// The fence a neighbourhood of `at` stops at: the last at or before it, else the reading's
// start, or the first at or after it, else its end. Fences stand in reading order.
/** @param {PageReading} reading @param {number} at @param {boolean} before */
function fenceEdge({ fences, raw }, at, before) {
  let low = 0;
  let high = fences.length;
  while (low < high) {
    const middle = (low + high) >> 1;
    if (/** @type {number} */ (fences[middle]) < at) low = middle + 1;
    else high = middle;
  }
  if (!before) return fences[low] ?? raw.length;
  return fences[low] === at ? at : (fences[low - 1] ?? 0);
}
// As much collapsed text as the caller asked for, however much raw text that takes.
// A fixed raw budget reads less than the capture wrote wherever whitespace runs dense — an
// indented line inside a <pre> — and the right occurrence then confirms none of its own
// neighbours.
//
// Counted in code points, which is the unit both captures write in: `cut` slices the
// window this returns by code point, and passages.py's reading of the same passage slices
// a Python string, which has no other unit. Counting code units here stopped the growth
// early on any neighbourhood holding an emoji — the window reached 24 of them while
// holding 23 characters — so the browser stored a prefix a character short of the one the
// file's reading stores for that same passage, and the two captures wrote different
// anchors for one passage.
/** @param {PageReading} reading @param {number} at @param {number} want @param {boolean} before */
export function neighbourhood(reading, at, want, before) {
  const edge = fenceEdge(reading, at, before);
  for (let raw = want * 2; ; raw *= 2) {
    const lo = before ? Math.max(edge, at - raw) : at;
    const hi = before ? at : Math.min(edge, at + raw);
    const text = quoteFrom(spanOf(reading, lo, hi));
    if ([...text].length >= want || (before ? lo === edge : hi === edge)) return text;
  }
}
// The words of raw[lo..hi) as `quoteFrom` reads its span: the whole reading's words
// between the two places, less the space ahead of the first.
/** @param {PageReading} reading @param {number} lo @param {number} hi */
function wordsBetween(reading, lo, hi) {
  let words = "";
  for (let k = Math.floor(lo / PIECE); k * PIECE < hi; k++) {
    const { text, places } = wordsPiece(reading, k);
    const start = k * PIECE;
    const from = /** @type {number} */ (places[Math.max(lo, start) - start]);
    const to = /** @type {number} */ (places[Math.min(hi, start + PIECE) - start]);
    words += text.slice(from, to);
  }
  return words.startsWith(" ") ? words.slice(1) : words;
}
// The reading's words are kept in pieces of this much raw text, each read the first time
// something asks for words in it, so a question about a few places reads only around them.
const PIECE = 4096;
/** @type {WeakMap<readonly IndexedSegment[], Map<number, {text: string, places: Int32Array}>>} */
const readPieces = new WeakMap();
// Piece `k`: the words the whole reading has for raw[k·PIECE..(k+1)·PIECE), read from a
// little before it, and where each raw place in it falls among them, as `visit` hears it.
/** @param {PageReading} reading @param {number} k */
function wordsPiece(reading, k) {
  const { segments, raw } = reading;
  let pieces = readPieces.get(segments);
  if (!pieces) readPieces.set(segments, (pieces = new Map()));
  const kept = pieces.get(k);
  if (kept) return kept;
  const lo = k * PIECE;
  const hi = Math.min(raw.length, lo + PIECE);
  // The read starts at the last character before the piece and continues the whole reading
  // after the segment that reading read before it, so it reaches the piece as that reading
  // does: owing a space or not, after the same block.
  let held = segmentAt(reading, lo - 1);
  let last;
  while ((last = segments[held]) && last.end === last.start) held--;
  let from = last ? Math.min(lo, last.rawStart + last.end - last.start) - 1 : lo;
  if (isPair(raw, from - 1)) from -= 1;
  // A pair the piece's end divides is read whole here, and its second half is the next
  // piece's start, where the words after the pair begin.
  const end = isPair(raw, hi - 1) ? hi + 1 : hi;
  const places = new Int32Array(hi - lo + 1).fill(-1);
  /** @type {Text | undefined} */
  let node;
  let base = 0;
  /** @param {Text} at @param {number} offset @param {number} length */
  const visit = (at, offset, length) => {
    if (at !== node) base = /** @type {number} */ (reading.positions.get((node = at)));
    const place = base + offset - lo;
    if (place >= 0 && place < places.length) places[place] = length;
  };
  const after = segments[segmentAt(reading, from - 1)];
  const text = readSegments(spanOf(reading, from, end), false, visit, after);
  // A place that holds no character — an edge between segments, a pair's second half, the
  // piece's end — falls where the next character does.
  let next = text.length;
  for (let i = hi - lo; i >= 0; i--) {
    const place = /** @type {number} */ (places[i]);
    places[i] = next = place < 0 ? next : place;
  }
  const piece = { text, places };
  pieces.set(k, piece);
  return piece;
}
// Whether raw[i] and raw[i + 1] are the two halves of one character.
/** @param {string} raw @param {number} i */
const isPair = (raw, i) =>
  i >= 0 &&
  /[\uD800-\uDBFF]/.test(raw.charAt(i)) &&
  /[\uDC00-\uDFFF]/.test(raw.charAt(i + 1));
// The reading is a function of the document and the user's settlements, so those are
// what say when it may change. Everything it is built out of is here: the page's words
// and their shape, the markers those words are read through, the vocabulary the markers
// mean something against, the slots the decisions in force retire (`settlements`), and
// the widget parts the cell walk fences on. The first two a MutationObserver reports;
// the rest have one door each.
//
// Reported is not the same as read. The runtime's chrome lives in the same document —
// the floating panel, its views, the composer — and repaints on nearly
// every gesture: one drag-select release wrote 38 records, every one of them under
// `.lf-ui`, and each would have bought a walk the reading never needed. So a record counts
// only where the reading reads, by the walk's own rules (`contextAt`) asked of the place
// the change landed, rather than by a second list of what chrome looks like.
//
// `class` is in the filter for one class. `.lf-ui` is what `uiInside` reads and the rest
// are the runtime's paint — `lf-mark-el` and its neighbours go on and off the page's own
// elements between anchor passes, and a walk apiece for a class the reading never looks
// at is the whole cost this exists to avoid. `slot` and `name` are in it for slot
// assignment, and `name` assigns only on a `<slot>`: a chrome that rewrites the
// `name` of its `<details>` rows on every paint says nothing about any words. `id` says
// nothing about them either, but an anchor's section is found by it, so its changes
// are heard and reported apart from the reading (`hear`).
const READING_MARKERS = [
  "class",
  "data-lf-said",
  "data-lf-gen",
  "data-lf-projection",
  "data-lf-datum",
  "slot",
  "name",
  "contenteditable",
  "id",
];
const WATCH_READING = {
  subtree: true,
  childList: true,
  characterData: true,
  attributes: true,
  attributeOldValue: true,
  attributeFilter: READING_MARKERS,
};
/** @type {string | undefined} */
let readingVocabulary;
/** @type {string | undefined} */
let readingSettled;
/** @type {MutationObserver | null} */
let watcher = null;
// The document whose reading a node stands in: a message's body, which is a document of
// its own (`authoredScope`), or the page's. A node in a Leaf surface outside any message
// is in none, since no document reads its words.
const DOCUMENTS = `${MESSAGE_BODY}, ${LEAF_SURFACE}`;
/** @param {Node} node @returns {Element | null} */
const readingDocument = (node) => {
  const at = closestAcross(node, DOCUMENTS);
  return !at ? pageDocument() : at.matches(MESSAGE_BODY) ? at : null;
};
// Whether text standing directly under `over` is in the reading of the document `scope`,
// with chrome counted from where that document's own walk frames it (`frameOf`): from
// the top for the page, from the body for a message. Anything but an element — a
// declared shadow root, the document, a node since detached — is answered yes, since
// over-forgetting costs a walk and under-forgetting costs a mark on words the page no
// longer says.
/** @param {Element} scope @returns {(over: Node | null) => boolean} */
const readsIn = (scope) => {
  const frame = frameOf(scope);
  return (over) => !isElement(over) || READINGS.says(contextAt(over, frame));
};
// A declared label is its document's words even inside generated widget apparatus. A
// node a record hands in stands in the document the record landed in, unless it starts
// a Leaf surface of its own, whose words no document reads.
/** @param {Node} node */
const holdsSaid = (node) =>
  isElement(node) &&
  !node.matches(LEAF_SURFACE) &&
  (node.matches(SAID) || node.querySelector(SAID) !== null);
// Whether a node can put words in the reading, standing where `read` says its document
// reads (`readsIn` of its parent). A node that starts chrome (`chromeMark`) and holds no
// label is silent wherever it goes, which is what the panel's re-rendered rows are.
/** @param {Node} node @param {boolean} read */
const speaks = (node, read) =>
  (read && !(isElement(node) && chromeMark(node) === true)) || holdsSaid(node);
// Records are read when the queue drains rather than when they were written, so a place
// is asked about as it stands now. That is still exact: a node that moved between the
// page and the chrome left a childList record at its page end, which speaks either way.
// `reads` is where the document the record landed in reads (`readsIn`).
/** @param {MutationRecord} record @param {(over: Node | null) => boolean} reads */
const changesTheReading = (record, reads) => {
  const { target } = record;
  if (record.type === "childList") {
    const read = reads(target);
    return [...record.addedNodes, ...record.removedNodes].some((n) => speaks(n, read));
  }
  if (record.type === "characterData") return reads(target.parentNode);
  // A marker moved on `target` itself, so its own markers are what is changing and only
  // its place and its labels answer — including a label it has just stopped being.
  if (!isElement(target) || record.attributeName === "id") return false;
  if (record.attributeName === "class") {
    const was = /(^|\s)lf-ui(\s|$)/.test(record.oldValue ?? "");
    if (was === target.classList.contains("lf-ui")) return false;
  }
  if (record.attributeName === "name" && target.localName !== "slot") return false;
  const wasSaid = record.attributeName === "data-lf-said" && record.oldValue !== null;
  return wasSaid || holdsSaid(target) || reads(target.parentNode);
};
// Each document's reading, kept until something it is built out of moves: the page's
// outline (`documentOutline`) and the readings of elements in its frame (`pageText`), or
// a message's outline.
// A record is replaced, never changed, so the record a reader took is which reading it
// read. A change forgets the reading of the document it lands in and that one alone
// (`forget`); a change no one document owns, the vocabulary or a settlement, forgets them
// all. What a reader keeps to know which reading it read is the record's `token`, an
// empty object, so a key or a kept answer that outlives the reading holds none of it.
/** @typedef {{token: object, outline: OutlineReading | null, within: WeakMap<Element, PageReading>}} DocumentReading */
/** @type {WeakMap<Element, DocumentReading>} */
let documents = new WeakMap();
/** @param {Element} scope */
function documentReading(scope) {
  let kept = documents.get(scope);
  if (!kept)
    documents.set(scope, (kept = { token: {}, outline: null, within: new WeakMap() }));
  return kept;
}
/** @param {Element | null} scope */
const forget = (scope) => {
  if (scope) documents.delete(scope);
};
// The page's reading is kept in pieces (`Piece`), each until a change lands in it, so a
// change re-reads only the piece it lands in. A part is a datum, the outermost on the
// climb the walk comes down (`readingPart`): a page grows large through its widgets'
// data, and a datum's words are read alone where a quote in it is found. On a page of 30
// text documents of 4 MB, reading the whole page took 2.3 to 2.6 s in Chromium and 3.6
// to 4.2 s in Firefox, and one document 60 to 130 ms. The frame is the rest of the page,
// read with each part left out where it stands (`collect`), and nothing reads the two
// together (`pageText`). A heading, header or hgroup is never a part, since it heads
// what stands outside it (`outlineFold`).
//
// The owner of each change drops the pieces it touches, and nothing else does: the
// watcher for the page's own changes (`touch`), and the doors for the rest
// (`changedAt`). A piece's token is what an element inside it keeps its answers under
// (`elementReading`), so they stand while only other pieces change. The page's own
// token moves with any piece, since the words an element in the frame holds can be any
// part's.
/** @typedef {{root: Element, at: number, heading: number}} PartMark
 * @typedef {{segments: Segment[], chains: (CellChain | null)[], marks: PartMark[],
 * outline: WalkedOutline}} Collected
 * @typedef {{block: Element | null, segments: Segment[]}} BlockRun
 * @typedef {{token: object, collected: Collected | null, reading: PageReading | null,
 * within: WeakMap<Element, PageReading>, runs: (BlockRun | PartMark)[] | null,
 * headed: boolean | null, matched: Map<string, Element[]>}} Piece */
/** @type {Piece | null} */
let frame = null;
/** @type {Map<Element, Piece>} */
let parts = new Map();
/** @returns {Piece} */
const freshPiece = () => ({
  token: {},
  collected: null,
  reading: null,
  within: new WeakMap(),
  runs: null,
  headed: null,
  matched: new Map(),
});
const framePiece = () => (frame ??= freshPiece());
/** @param {Element} root */
function partPiece(root) {
  let piece = parts.get(root);
  if (!piece) parts.set(root, (piece = freshPiece()));
  return piece;
}
// The part a node stands in: the outermost part over it, or itself, climbing as the walk
// comes down (`readingParent`), so words a slot shows stand in the part the slot does.
// Null for a node in the frame.
/** @param {Node} node @returns {Element | null} */
export function readingPart(node) {
  /** @type {Element | null} */
  let part = null;
  for (let at = /** @type {Node | null} */ (node); at; at = readingParent(at))
    if (isElement(at) && isPart(at)) part = at;
  return part;
}
// Forgets the piece `node` stands in. With `under`, as for a change to the markers the
// walk reads at `node`, the parts under it go as well, since each part's context comes
// down through it and a part under a new part is one no longer: `node` joins `beneath`,
// which a batch of changes reads once (`forgetPartsBeneath`). The frame goes too where
// `node` is a part's root, since the frame reads where each part stands and whether it
// is one.
/** @param {Node} node @param {boolean} under @param {Set<Node>} beneath
 * @returns {Element | null} the part */
function forgetPiece(node, under, beneath) {
  const part = readingPart(node);
  if (part) parts.delete(part);
  else frame = null;
  if (under) beneath.add(node);
  if (under && part === node) frame = null;
  return part;
}
// Forgets each kept part that stands under any of `nodes` as the walk comes down
// (`readingChildren`): under one in its own tree or in a declared tree under it. A node
// that holds a slot of the declared tree it stands in stands over what the slot shows,
// which is its host's children, so the parts go from that host down instead, and from
// that host's host where the host holds a slot in turn, as slots pass on what they show.
// Each is found from its node down, so a batch costs the nodes it changed and what they
// hold, however many parts are kept.
/** @param {ReadonlySet<Node>} nodes */
function forgetPartsBeneath(nodes) {
  /** @param {Node} node */
  const under = (node) => {
    if (isElement(node)) parts.delete(node);
    else if (!isShadowRoot(node)) return;
    for (const part of node.querySelectorAll(DATUM)) parts.delete(part);
    shadowRootsIn(node).forEach(under);
  };
  /** @type {Set<Node>} */
  const tops = new Set();
  for (let at of nodes) {
    for (let host; holdsSlot(at) && (host = shadowHost(at.getRootNode()));) at = host;
    tops.add(at);
  }
  tops.forEach(under);
}
// The pieces a record of the page's changes touches: the one its target stands in; for
// nodes put in or taken out, the parts they hold, which may have moved; for a marker on
// an element, everything under it; and for anything that changes which slot shows which
// of a host's children, everything under that host: its children, a slot put into or
// taken out of its tree, a node's `slot` and a slot's `name`.
/** @param {MutationRecord} record @param {Set<Node>} beneath */
function touch(record, beneath) {
  const { target } = record;
  if (record.type === "characterData") return void forgetPiece(target, false, beneath);
  if (record.type === "childList") {
    const nodes = [...record.addedNodes, ...record.removedNodes];
    const root = target.getRootNode();
    const host = shadowHost(root);
    if (host && declaredRoot(host) === root && nodes.some(holdsSlot))
      forgetPiece(host, true, beneath);
    const assigns = isElement(target) && declaredRoot(target) !== null;
    // Only the frame holds parts: what a part gains or loses is its own.
    if (forgetPiece(target, assigns, beneath)) return;
    for (const node of nodes) if (isElement(node)) beneath.add(node);
    return;
  }
  const assigns =
    record.attributeName === "slot"
      ? target.parentNode
      : record.attributeName === "name"
        ? shadowHost(target.getRootNode())
        : null;
  forgetPiece(assigns ?? target, true, beneath);
}
/** @param {Node} node */
const holdsSlot = (node) =>
  isElement(node) && (node.localName === "slot" || node.querySelector("slot") !== null);
/** Which reading of the page stands: a new value each time the page's is forgotten, so a
 * reading derived from the page's own nodes, as the visual responses are, keeps what it
 * derived while this stands. It holds nothing of the reading itself.
 * @returns {object} */
export function pageReadingVersion() {
  catchUpReading();
  return documentReading(pageDocument()).token;
}
// What the watcher heard: each document a record changes the reading of forgets it, and
// where the page's is among them, or an id moved where `elementById` looks, whoever keeps
// a record of the page's words hears what changed (`hearPageWords`). The page's records
// are each read for that; another document's stop being read once it has moved.
/** @param {readonly MutationRecord[]} records */
function hear(records) {
  /** @type {Set<Element>} */
  const moved = new Set();
  const page = pageDocument();
  const keeping = hearers.size > 0 || index.pieces.size > 0;
  /** @type {Set<Node>} */
  const written = new Set();
  /** @type {Set<string>} */
  const ids = new Set();
  /** @type {Set<Element>} */
  const renamed = new Set();
  /** @type {Set<Node>} */
  const beneath = new Set();
  // The ids an element and what it holds bear, where an id is looked for
  // (`elementById`).
  /** @param {Node} node */
  const idsUnder = (node) => {
    if (!isElement(node)) return;
    if (node.id) ids.add(node.id);
    for (const scope of [node, ...shadowRootsIn(node)])
      for (const named of scope.querySelectorAll("[id]")) ids.add(named.id);
  };
  for (const record of records) {
    const { target } = record;
    if (hearers.size && !leafSurface(target)) {
      if (record.attributeName === "id" && isElement(target)) {
        if (record.oldValue) ids.add(record.oldValue);
        if (target.id) ids.add(target.id);
        renamed.add(target);
      }
      if (record.type === "childList") {
        record.addedNodes.forEach(idsUnder);
        record.removedNodes.forEach(idsUnder);
      }
    }
    const scope = readingDocument(target);
    // Every record of the page's is read for the pieces it touches.
    if (!scope || (moved.has(scope) && scope !== page)) continue;
    if (!changesTheReading(record, readsIn(scope))) continue;
    moved.add(scope);
    if (scope !== page) continue;
    touch(record, beneath);
    if (!keeping) continue;
    if (record.type === "characterData") written.add(target);
    if (record.type !== "childList") continue;
    // The text the reading's own walk finds in what was taken out, where the page's
    // passages can have stood: the declared shadow trees it holds included, its own
    // where it is a declared host, which a walk handed the host would pass by.
    for (const node of record.removedNodes)
      if (isText(node)) written.add(node);
      else if (isElement(node))
        walk(declaredRoot(node) ?? node, (text) => written.add(text));
  }
  forgetPartsBeneath(beneath);
  for (const scope of moved) forget(scope);
  if (moved.has(page) || ids.size) tellHearers({ written, ids, renamed });
}
// A change no record reports, to what the walk reads at `node` and under it: the reading
// of the document it stands in is forgotten, and where that is the page's, so are the
// pieces it touches (`forgetPiece`), and its hearers hear it.
/** @param {Element} node */
function changedAt(node) {
  const scope = readingDocument(node);
  forget(scope);
  if (!scope || scope !== pageDocument()) return;
  const beneath = new Set();
  forgetPiece(node, true, beneath);
  forgetPartsBeneath(beneath);
  tellHearers(NOTHING_CHANGED);
}
function watchReading() {
  if (watcher) return watcher;
  watcher = new MutationObserver(hear);
  watcher.observe(document, WATCH_READING);
  return watcher;
}
// What keeps a record of where things stand in the page's words, as anchor placement
// keeps where each anchor stands (anchor-placement.js), hears that the page's reading
// changed, as it happens (`hearPageWords`, `hear`), and reads what changed off the two readings
// (`quotesChanged`), by the reading's own rules: its text, its edges and fences, and the
// order its walk puts the page's trees in. It hears what no reading shows besides: the
// text nodes a change wrote or took out (`written`), found in what it took out by the
// reading's own walk, the declared shadow trees there included, whose passages' live
// ranges the DOM moved or left in a tree no longer the page's, and which may have moved
// into or out of a section, even where the page then says just what it said before;
// and the ids the page's elements gained or lost (`ids`), with the elements whose own
// id changed (`renamed`), since an anchor's section is found by its id. Ids are read
// where `elementById` looks for one, the light tree and the declared stages on it
// (`shadowRootsIn`), which is not the walk's reach: the walk passes over a declared
// host's light children no slot shows, and an id among them is still found. A reader
// that must not read older than the DOM takes the changes not yet heard first
// (`catchUpWords`).
/** @typedef {{written: ReadonlySet<Node>, ids: ReadonlySet<string>, renamed: ReadonlySet<Element>}} WordsChange */
/** @type {Set<(change: WordsChange) => void>} */
const hearers = new Set();
const NOTHING_CHANGED = Object.freeze({
  written: new Set(),
  ids: new Set(),
  renamed: new Set(),
});
/** @param {WordsChange} change */
function tellHearers(change) {
  for (const piece of index.pieces.values())
    for (const node of change.written) piece.rewritten.add(node);
  for (const hear of hearers) hear(change);
}
// The changes the watcher holds and hasn't yet delivered, heard now, so a reader in the
// task that made them reads after them.
export function catchUpWords() {
  hear(watchReading().takeRecords());
}
/** @param {(change: WordsChange) => void} hear */
export function hearPageWords(hear) {
  watchReading();
  hearers.add(hear);
  return () => void hearers.delete(hear);
}
// A declared shadow stage is part of its document's words — `textNodesUnder` walks into
// one at its host's place in the string — and no observer crosses the boundary on its
// own. shadow-stage.js, which is the only door an x-shadow root is built through, hands
// each one here as it fills it, and again each time it adopts it. The first time forgets
// the reading of the document the root stands in, which was read without it; from then
// on the watcher reports the root's changes itself. The words it fills with may be ones
// the page already marked, which moving collapses each live range of the marks onto the
// host, so a page that has presented is presented again once the fill has moved them,
// and its marks resolve in the stage; before then, its first presentation reads them
// there.
/** @type {WeakSet<ShadowRoot>} */
const watchedRoots = new WeakSet();
/** @param {ShadowRoot} root */
export function watchPassageRoot(root) {
  if (watchedRoots.has(root)) return;
  watchedRoots.add(root);
  watchReading().observe(root, WATCH_READING);
  changedAt(root.host);
  if (readingDocument(root) === pageDocument() && pagePresented())
    queueMicrotask(presentDocument);
}
// An opaque widget and its original direct children fence the cell walk. Marking them is
// not a change to the document, so it is a change nothing else would report: a reading
// taken before a widget was fenced reads its words as ordinary page prose, and a quote
// from the paragraph above could run straight into them. The marking and the forgetting
// are one door for that reason.
/** @param {Element} root @param {Iterable<Element>} [children] */
export function fencePassageParts(root, children = root.children) {
  passageFences.add(root);
  for (const child of children) passageFences.add(child);
  changedAt(root);
}
// What the page says, once, as one string with a way back to the nodes it came from. Built
// per document state rather than per caller: every anchor a pass places is asking about the
// same document, and resolving each against its own fresh reading would let two marks in
// one pass answer for two different pages, since a widget can upgrade between them. Forty
// threads on a 13k-character page also spent it forty times: 9.3ms of index building per
// pass, besides the forty tree walks feeding it, against 1.5ms for the one read that
// replaces them.
//
// A pass is not the bound, though, because the passes are frequent and the walk grows with
// the page: the painter, the capture, the target picker and the selection surface each
// take one, and a drag-select takes one per pointer move. At a few thousand elements that
// is the better part of a second apiece, which is a page that stutters while it is only
// being read. So the reading stands until something it is built out of moves.
//
// `takeRecords` is what makes that exact rather than a frame late. An observer's callback
// runs in a microtask, so a caller that changed the page and read it back in the same task
// would be handed the reading from before its own edit. Draining the queue at the read asks
// the observer what it has seen instead of waiting to be told.
//
// `pageText()` is the frame's reading: the page's words outside its parts, with a fence
// where each part stands. A quote in prose never stands in a part, since every part is a
// datum, which the projection stamps a passage cell of its own (projection/data.js), and
// a selection whose words all lie in one datum is captured on that datum
// (anchor-resolution.js, `anchorForPassage`). So prose is searched, captured and snapped
// in the frame alone, and no reader puts the parts' words together with it.
//
// `within` asks for the words under one element, read alone with its edges as the
// reading's ends, so a neighbourhood read inside it stops there. A quote anchored in a
// datum is captured and found again in its datum's words alone, so finding one costs
// what the datum holds. A part's own reading is kept as its piece is, and another
// element's with the piece it stands in. `within` is an element the page reading
// reaches, as a datum is: under a shadow root the page doesn't read, its reading would
// hold words the page skips, whose changes no watcher reports.
/** @param {Element | null} [within] */
export function pageText(within = null) {
  catchUpReading();
  if (!within) {
    const piece = framePiece();
    if (!piece.reading) {
      const { segments, chains, marks } = frameCollected();
      piece.reading = indexed(segments, chains, marks);
      readingPieces.set(piece.reading, pageDocument());
    }
    return piece.reading;
  }
  const part = inPage(within) ? readingPart(within) : null;
  if (part && part === within) {
    const piece = partPiece(part);
    if (!piece.reading) {
      const { segments, chains } = partCollected(part);
      readingPieces.set((piece.reading = indexed(segments, chains)), part);
    }
    return piece.reading;
  }
  const kept = part ? partPiece(part).within : documentReading(pageDocument()).within;
  let reading = kept.get(within);
  if (!reading) {
    const { segments, chains } = collect(within, false);
    kept.set(within, (reading = indexed(segments, chains)));
    readingPieces.set(reading, within);
  }
  return reading;
}
// The element each kept reading is the reading of, which keys its quote index (`index`):
// a part's root, another element read alone, or the page's body for the frame.
/** @type {WeakMap<PageReading, Element>} */
const readingPieces = new WeakMap();
// The reading of the piece a node stands in: its part's, or the frame's.
/** @param {Node} node */
export const readingHolding = (node) =>
  pageText(inPage(node) ? readingPart(node) : null);
// The roots of the page's parts, in reading order.
export function readingParts() {
  catchUpReading();
  return frameCollected().marks.map(({ root }) => root);
}
function catchUpReading() {
  hear(watchReading().takeRecords());
  const vocabulary = registry.$layer?.generation;
  settlements();
  if (vocabulary !== readingVocabulary || settledKey !== readingSettled) {
    documents = new WeakMap();
    frame = null;
    parts = new Map();
    tellHearers(NOTHING_CHANGED);
  }
  readingVocabulary = vocabulary;
  readingSettled = settledKey;
}
// A reading of one element's words, kept exactly as long as the piece of its document's
// reading it stands in (`readingDocument`, `readingPart`): the watcher above is what says
// either has moved. An element in the page's frame holds whatever parts stand under it,
// so it keeps its words only while no piece of the page changes. Margin rows, the Page Map
// and every label ask the same elements for their words on every pass, and each walk
// asks every text node under the element where it stands, which on a long page costs
// more than the pass it serves. An element no document reads — chrome, a node since
// detached, a node of a parsed revision — is outside what the watcher answers for, and
// is read afresh.
//
// A kept reading is answered before asking where the element stands: it was kept only
// while its document read the element, and anything that moves the element out of that
// — its removal, chrome arriving over it — is a change that forgets the piece it stood
// in, whose token the kept reading holds.
/** @typedef {{scope: Element, part: boolean, token: object, words: Partial<Record<Reading, string>>, answers: Map<string, unknown>}} Kept */
/** @type {WeakMap<Element, Kept>} */
const keptAbout = new WeakMap();
/** @param {Element} element */
function kept(element) {
  catchUpReading();
  const about = keptAbout.get(element);
  if (!about) return null;
  const now = about.part ? parts.get(about.scope) : documents.get(about.scope);
  return now?.token === about.token ? about : null;
}
// Where to keep what an element answers: under the piece of its document's reading it
// stands in, where that document reads the element.
/** @param {Element} element */
function keeping(element) {
  const about = kept(element);
  if (about) return about;
  if (!element.isConnected || element.ownerDocument !== document) return null;
  const scope = readingDocument(element);
  if (!scope || !readsIn(scope)(element)) return null;
  const part = scope === pageDocument() ? readingPart(element) : null;
  /** @type {Kept} */
  const fresh = {
    scope: part ?? scope,
    part: part !== null,
    token: (part ? partPiece(part) : documentReading(scope)).token,
    words: {},
    answers: new Map(),
  };
  keptAbout.set(element, fresh);
  return fresh;
}
/** @param {Element} element @param {Reading} [reading] */
export function elementReading(element, reading = "says") {
  const known = kept(element)?.words[reading];
  if (known !== undefined) return known;
  const value = quoteFrom(textNodesUnder(element, reading));
  const about = keeping(element);
  if (about) about.words[reading] = value;
  return value;
}
/** An answer about an element's own children and words, such as which of them titles
 * it, kept as long as its document's reading stands, as its words are
 * (`elementReading`), and asked afresh of an element no document reads.
 * @template T @param {Element} element @param {string} question @param {() => T} answer
 * @returns {T} */
export function keptAnswer(element, question, answer) {
  const known = kept(element)?.answers;
  if (known?.has(question)) return /** @type {T} */ (known.get(question));
  const value = answer();
  keeping(element)?.answers.set(question, value);
  return value;
}
// The walk itself, over the page's words under `root`, by the page's rules for any root
// the page reading reaches (`walk`, `frame`): each word's segment, with its cell chain and
// whether a break stood before it, and the outline the walk records. A root outside the
// page, such as a widget in a message the panel shows, holds none of the page's words.
// With `marksParts`, as the frame is read, each part is left out where it stands, marked
// with how far through the words and the outline the walk had come.
/** @param {Element} root @param {boolean} marksParts @returns {Collected} */
function collect(root, marksParts) {
  /** @type {Segment[]} */
  const segments = [];
  /** @type {(CellChain | null)[]} */
  const chains = []; // the cell candidates over each segment, nearest first
  /** @type {PartMark[]} */
  const marks = [];
  const keeps = READINGS.says;
  let breakBefore = false;
  const outline = outlineFold();
  if (inPage(root))
    walk(
      root,
      (node, ctx) => {
        if (!keeps(ctx)) return;
        segments.push({ ...segmentIn(node, ctx), breakBefore });
        breakBefore = false;
        chains.push(ctx.cells);
      },
      (child, ctx) => {
        if (child.matches(LEAF_SURFACE)) return true;
        if (!marksParts || !isPart(child)) return false;
        const inner = enter(ctx, child);
        outline.enter(child, inner, true);
        marks.push({ root: child, at: segments.length, heading: outline.count() });
        outline.enter(child, inner, false);
        return true;
      },
      (ctx) => {
        if (keeps(ctx)) breakBefore = true;
      },
      outline.enter,
      null,
    );
  return { segments, chains, marks, outline: outline.read() };
}
/** @param {Element} root */
const partCollected = (root) => (partPiece(root).collected ??= collect(root, false));
const frameCollected = () => (framePiece().collected ??= collect(pageDocument(), true));
// Words in reading order as one string with a way back to the nodes they came from: a
// space or an edge between each two (`spacedFrom`), and a fence wherever the passage cell
// they stand in changes, and where a part the frame leaves out stands (`marks`).
/** @param {readonly Segment[]} segments @param {readonly (CellChain | null)[]} chains
 * @param {readonly PartMark[]} [marks] @returns {PageReading} */
function indexed(segments, chains, marks = []) {
  // Generated page-words that the registry does not model are their own passage cells:
  // the generated element a word of the reading stands in, where it is unmodelled.
  const dynamicWords = new Set();
  for (const { gen } of segments) if (gen && unmodelled(gen)) dynamicWords.add(gen);
  // A segment's cell is the nearest candidate over it that fences. The chain crosses the
  // shadow boundary (upFrom), and that is what keeps an x-shadow widget fenced. The parts
  // were remembered off the light DOM before any module ran, so nothing inside a shadow
  // tree is among them; a chain that stopped at the root would put a diff's lines in
  // no cell at all, which reads as ordinary page prose and lets a quote run from the
  // paragraph above straight into the first changed line. One move further up finds the
  // host, which is the opaque root it always was.
  /** @param {CellChain | null | undefined} chain */
  const cellOf = (chain) => {
    for (let at = chain; at; at = at.up)
      if (opaque(at.el) || at.editing || dynamicWords.has(at.el)) return at.el;
    return null;
  };

  /** @type {string[]} */
  const texts = [];
  /** @type {IndexedSegment[]} */
  const indexed = [];
  const positions = new WeakMap(); // text node -> its offset-zero position in raw
  const fences = new Set();
  let length = 0;
  /** @type {Element | null} */
  let previousCell = null;
  const parted = new Set(marks.map(({ at }) => at));
  segments.forEach((seg, k) => {
    const cell = cellOf(chains[k]);
    if (k === 0) {
      if (cell || parted.has(0)) fences.add(0);
    } else {
      if ((cell !== previousCell && (cell || previousCell)) || parted.has(k))
        fences.add(length);
      // A space where the reading reads one (`readSegments`), else an edge.
      const previous = /** @type {Segment} */ (segments[k - 1]);
      const spaced = spacedFrom(seg, previous);
      texts.push(spaced ? " " : EDGE);
      length += 1;
    }
    indexed.push({ ...seg, rawStart: length });
    positions.set(seg.node, length - seg.start);
    texts.push(seg.node.data);
    length += seg.end - seg.start;
    previousCell = cell;
  });
  if (previousCell || parted.has(segments.length)) fences.add(length);
  return {
    raw: texts.join(""),
    positions,
    fences: [...fences].sort((a, b) => a - b),
    segments: indexed,
  };
}
// A document's outline, recorded by the walk that reads it, in composed reading order:
// its headings, Leaf's chrome aside, so a slot's fallback replaced by what is assigned
// to it is none; and, for each element the walk enters, what stood over it as the walk
// reached it (`Over`): for each container out from it, the last heading met so far that
// heads that container (`headed`). Each container's record is replaced, never changed,
// when a heading arrives in it, and so is the record of each container still open inside
// it, as a header is around the title that heads what holds the header, so what an
// element was given stays as it was and what comes after stands under the heading. And for
// each heading, the nearest heading of a higher rank before it in the same container
// (`above`), as a reader takes a flow of h2s to stand under the h1 over them.
// thread/placement.js reads names and parts from it (`partOver`, `partTrail`).
const outlineFold = () => {
  /** @type {Element[]} */
  const outline = [];
  /** @type {Map<Element, number>} */
  const at = new Map();
  /** @type {Map<Element, Over | null>} */
  const over = new Map();
  /** @type {Map<Element, Element | null>} */
  const above = new Map();
  // Each container's headings still open to a later one of a lower rank, highest first.
  /** @type {Map<Element | null, Element[]>} */
  const ranks = new Map();
  const rank = (/** @type {Element} */ heading) => Number(heading.localName.slice(1));
  /** @type {{element: Element, state: Over}[]} */
  const open = [];
  return {
    /** @param {Element} element @param {ReadingContext} ctx @param {boolean} entering */
    enter(element, ctx, entering) {
      if (!entering) {
        open.pop();
        return;
      }
      over.set(element, open.at(-1)?.state ?? null);
      if (element.matches(HEADING) && !ctx.chrome) {
        at.set(element, outline.length);
        outline.push(element);
        const container = headed(element);
        const holder = open.findLastIndex((frame) => frame.element === container);
        for (let depth = holder; depth >= 0 && depth < open.length; depth++) {
          const frame = /** @type {{element: Element, state: Over}} */ (open[depth]);
          frame.state =
            depth === holder
              ? { ...frame.state, heading: element }
              : { ...frame.state, up: open[depth - 1]?.state ?? null };
        }
        const higher = ranks.get(container) ?? [];
        while (
          higher.length &&
          rank(/** @type {Element} */ (higher.at(-1))) >= rank(element)
        )
          higher.pop();
        above.set(element, higher.at(-1) ?? null);
        higher.push(element);
        ranks.set(container, higher);
      }
      const up = open.at(-1)?.state ?? null;
      open.push({ element, state: { container: element, heading: null, up } });
    },
    /** @returns {WalkedOutline} */
    read: () => ({ outline: Object.freeze(outline), at, over, above }),
    // How many headings the walk has recorded so far.
    count: () => outline.length,
  };
};
/** The outline of the document `scope` (`authoredScope`): the page's, put together from
 * the walks that read its pieces (`wholeOutline`), or a message's, walked as the page's
 * is; each kept as long as its document's reading stands.
 * @param {Element} scope @returns {OutlineReading} */
export function documentOutline(scope) {
  if (scope === pageDocument(scope.ownerDocument)) {
    catchUpReading();
    return (documentReading(pageDocument()).outline ??= wholeOutline());
  }
  if (!scope.isConnected) return outlineReading(scope);
  catchUpReading();
  const kept = documentReading(scope);
  return (kept.outline ??= outlineReading(scope));
}
/** @param {Element} root @returns {OutlineReading} */
function outlineReading(root) {
  const outline = outlineFold();
  walk(root, () => {}, null, null, outline.enter);
  return outline.read();
}
// The page's outline, put together from its pieces: the frame's, with the headings of
// each part holding one spliced in at its mark. What stood over an element in
// a part is the part's own record of it under what stood over the part in the frame
// (`joined`), so a part is read for its outline only where it holds a heading or someone
// asks what stands over an element in it. A part's headings head nothing outside it,
// since no part is a heading or a header (`PART`), and none outside it stands in a
// container inside it, so each walk records what one walk of the page would.
/** @returns {OutlineReading} */
function wholeOutline() {
  const { outline: own, marks } = frameCollected();
  /** @type {Element[]} */
  const spliced = [];
  let from = 0;
  for (const { root, heading } of marks) {
    if (!partHeaded(root)) continue;
    spliced.push(
      ...own.outline.slice(from, heading),
      ...partCollected(root).outline.outline,
    );
    from = heading;
  }
  const outline = spliced.length
    ? [...spliced, ...own.outline.slice(from)]
    : own.outline;
  /** @param {Element} element */
  const inPart = (element) => {
    const part = readingPart(element);
    return part && part !== element ? part : null;
  };
  /** @param {Element} heading */
  const aboveIn = (heading) => {
    const part = inPart(heading);
    return part ? partCollected(part).outline.above : own.above;
  };
  return {
    outline: Object.freeze(outline),
    at: spliced.length
      ? new Map(outline.map((heading, index) => [heading, index]))
      : own.at,
    over: {
      get: (element) => {
        const part = inPart(element);
        if (!part) return own.over.get(element);
        const top = own.over.get(part) ?? null;
        return joined(partCollected(part).outline.over.get(element), part, top);
      },
    },
    above: {
      has: (heading) => aboveIn(heading).has(heading),
      get: (heading) => aboveIn(heading).get(heading),
    },
  };
}
// A record a part's own walk made, which started at the part's root with nothing over it,
// standing under what stood over the root in the frame's walk (`top`).
/** @param {Over | null | undefined} state @param {Element} root @param {Over | null} top
 * @returns {Over | null | undefined} */
const joined = (state, root, top) =>
  state && {
    ...state,
    up: state.container === root ? top : (joined(state.up, root, top) ?? null),
  };
// Whether a part holds a heading of the page's outline: not where no heading stands in it,
// in a declared shadow tree under it, or among what a slot in either shows, as in most
// parts of data, which then need no walk for the outline; otherwise as its walk recorded.
/** @param {Element} root */
function partHeaded(root) {
  const piece = partPiece(root);
  /** @param {Element} element */
  const heading = (element) =>
    element.matches(HEADING) || element.querySelector(HEADING);
  /** @param {Element | ShadowRoot} scope */
  const holds = (scope) =>
    scope.querySelector(HEADING) !== null ||
    [...scope.querySelectorAll("slot")].some((slot) =>
      slot.assignedElements({ flatten: true }).some(heading),
    );
  piece.headed ??=
    partScopes(root).some(holds) && partCollected(root).outline.outline.length > 0;
  return piece.headed;
}
// The trees a part's words stand in, found natively rather than walked: the part's own
// and each declared shadow tree under it. What a slot in either shows belongs to the part
// too, wherever that node sits in the light tree.
/** @param {Element} root @returns {(Element | ShadowRoot)[]} */
const partScopes = (root) => [
  root,
  ...liveStages().filter(
    (stage) => declaredRoot(stage.host) === stage && readingUnder(stage.host, root),
  ),
];
/** The elements with one of `tags` that stand where the page reading reads its words,
 * in reading order. Each piece's are kept until that piece changes, so after a change
 * only the piece it landed in is searched again. The frame's are among the elements its
 * walk entered, which its outline records in the walk's order, each part's root where
 * the part stands (`over`). A part's are found natively in its trees (`partScopes`)
 * and among what their slots show, keeping those the walk reaches. Only the watcher
 * says a piece changed, and it hears an element arrive or leave wherever the reading
 * reads. An element's tag never changes, while a marker it bears, such as its `id` or
 * `class`, can change without the watcher hearing it. On a page of 30 text documents of 4 MB, a query of the whole page took
 * 57 ms in Chromium, and one part's 2 ms.
 * @param {readonly string[]} tags @returns {Element[]} */
export function readingElements(tags) {
  catchUpReading();
  const { outline, marks } = frameCollected();
  const parted = new Set(marks.map(({ root }) => root));
  const names = new Set(tags);
  const key = tags.join(",");
  const reads = readsIn(pageDocument());
  const piece = framePiece();
  let own = piece.matched.get(key);
  if (!own)
    piece.matched.set(
      key,
      (own = [...outline.over.keys()].filter(
        (element) =>
          parted.has(element) || (names.has(element.localName) && reads(element)),
      )),
    );
  return own.flatMap((element) =>
    parted.has(element) ? partElements(element, names, key) : [element],
  );
}
/** @param {Element} root @param {ReadonlySet<string>} names @param {string} key
 * @returns {Element[]} */
function partElements(root, names, key) {
  const piece = partPiece(root);
  const kept = piece.matched.get(key);
  if (kept) return kept;
  const scopes = partScopes(root);
  const query = [...names, "slot"].join(", ");
  /** @type {Set<Element>} */
  const found = new Set();
  /** @param {Element | ShadowRoot} scope */
  const search = (scope) => {
    if (isElement(scope) && names.has(scope.localName)) found.add(scope);
    for (const element of scope.querySelectorAll(query)) {
      if (names.has(element.localName)) found.add(element);
      if (!isHTML(element, "slot")) continue;
      for (const shown of element.assignedElements({ flatten: true }))
        if (!scopes.some((within) => within.contains(shown))) search(shown);
    }
  };
  scopes.forEach(search);
  const reads = readsIn(pageDocument());
  const matched = [...found]
    .filter((element) => walkedTo(element, root) && reads(element))
    .sort(readingOrder);
  piece.matched.set(key, matched);
  return matched;
}
// Whether the walk down from `root` reaches `node` (`readingChildren`): not where a light
// child of a host stands whose declared tree the walk reads in their place.
/** @param {Node} node @param {Element} root */
const walkedTo = (node, root) => {
  for (let at = node; at !== root;) {
    const up = readingParent(at);
    if (!up) return true;
    if (isElement(up) && declaredRoot(up) && at.parentNode === up) return false;
    at = up;
  }
  return true;
};
// The container a heading heads, from where it stands on: what holds it, or what holds
// the `header` or `hgroup` it stands in, as HTML's outline reads a page's title in its
// header heading the page's sections. What holds it is what the walk that records the
// outline came down from (`readingParent`): a slot for a heading assigned to one, so a
// heading a widget's tree draws in its slot heads what is drawn after it there, and a
// declared root's host for a heading at the top of that root.
/** @param {Element} node @returns {Element | null} */
const holder = (node) => {
  const at = readingParent(node);
  return shadowHost(at) ?? (isElement(at) ? at : null);
};
/** @param {Element} heading */
export const headed = (heading) => {
  const at = holder(heading);
  return at?.matches(HEADERS) ? holder(at) : at;
};
// The page's text blocks in reading order, each with the run of the reading's segments it
// holds there, from the frame and from each part `reads` answers true for: a reader of
// what the user sees reads no part they can't see. A datum splits its parent's words, so
// a block can hold a run on each side of one. Kept on the piece each run came from, so
// it moves exactly when its words do.
/** @param {(part: Element) => boolean} reads @returns {BlockRun[]} */
export function pageRuns(reads) {
  catchUpReading();
  const framed = frameCollected();
  const own = (framePiece().runs ??= runsOf(framed.segments, framed.marks));
  return own.flatMap((run) =>
    !("root" in run) ? [run] : reads(run.root) ? partRuns(run.root) : [],
  );
}
/** @param {Element} root @returns {BlockRun[]} */
function partRuns(root) {
  const piece = partPiece(root);
  piece.runs ??= runsOf(partCollected(root).segments, []);
  return /** @type {BlockRun[]} */ (piece.runs);
}
/** @param {readonly Segment[]} segments @param {readonly PartMark[]} marks */
function runsOf(segments, marks) {
  /** @type {(BlockRun | PartMark)[]} */
  const runs = [];
  /** @type {BlockRun | null} */
  let run = null;
  let m = 0;
  segments.forEach((segment, at) => {
    for (let mark = marks[m]; mark && mark.at <= at; mark = marks[++m]) {
      runs.push(mark);
      run = null;
    }
    if (!run || run.block !== segment.block)
      runs.push((run = { block: segment.block, segments: [] }));
    run.segments.push(segment);
  });
  runs.push(...marks.slice(m));
  return runs;
}
// The blocks of those runs, each once (`blockAt`).
/** @param {(part: Element) => boolean} reads */
export function pageBlocks(reads) {
  /** @type {Set<Element>} */
  const blocks = new Set();
  for (const { block } of pageRuns(reads)) if (block) blocks.add(block);
  return [...blocks];
}
// Where a passage's segments start and stop in that reading, as [start, stop). A passage
// is `{node, start, end}` segments and every question about the region it covers is asked
// in the reading's own coordinates, so the join between the two is one function — the
// capture writing an anchor's neighbours and the snap widening a drag both ask it. No
// segments is the document's own start: a selection that covers no quotable character has
// a position and no extent.
/** @param {PageReading} reading @param {readonly Segment[]} segments @returns {[number, number]} */
export function spanIn(reading, segments) {
  const first = segments[0];
  const last = segments.at(-1);
  /** @param {Text} node */
  const position = (node) => {
    const offset = reading.positions.get(node);
    if (offset === undefined)
      throw new RangeError("A passage must belong to the page reading it is placed in");
    return offset;
  };
  const start = first ? position(first.node) + first.start : 0;
  return [start, last ? position(last.node) + last.end : start];
}
/** @param {string} s */
const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
// Whether no fence stands strictly inside raw[from..to).
/** @param {PageReading} text @param {number} from @param {number} to */
const withinCell = (text, from, to) => fenceEdge(text, from + 1, false) >= to;

// Where a quote's words stand. Its spelling is its letters, its words run together, and
// the page is spelled alike: each character but whitespace and edges. A copy of the
// quote stands wherever the page spells it and parts its letters as the quote does: a
// space or an edge where the quote has a space, and nothing or an edge where it has
// none. An edge is where two inline elements meet, and only the page's CSS says whether
// a word ends there, so it reads either way, as `occurrences` (anchor_capture.py)
// reads one too. The places are found in the reading's own letters (`spell`), and each
// is held to its quote's spaces there (`copyAt`).
//
// What a code unit is to a quote: 0 a letter, 1 an edge, 2 whitespace by the rule a
// quote is split into words by. Each code unit is put to the rule once.
const unitKinds = new Uint8Array(0x10000).fill(3);
/** @param {number} code */
function kindOf(code) {
  let kind = unitKinds[code];
  if (kind === 3) {
    const unit = String.fromCharCode(code);
    unitKinds[code] = kind = unit === EDGE ? 1 : COLLAPSIBLE.test(unit) ? 2 : 0;
  }
  return /** @type {number} */ (kind);
}
/** @param {string} raw @param {number} i */
const gapAt = (raw, i) => kindOf(raw.charCodeAt(i)) !== 0;
// A run of a reading's letters, raw's characters but its gaps (`kindOf`), each word run
// into the next, and where each STEP-th of them stands in raw (`marks`), so a place
// among the letters is a place in the reading again by a walk of fewer than STEP
// letters (`rawAt`). A quote's copies are searched for in the letters as a string, by
// the platform's string search where the quotes are few (`eachPlace`), and a copy's
// neighbours are told apart by them first (`holds`). Spelling the 4 MB of a text
// document takes 15 ms in Chromium and 30 ms in Firefox, against 90 ms for one pass of
// the automaton over its characters; a whole reading's letters are kept with it
// (`spelledReading`), and a change spells only around itself (`carry`).
/** @typedef {{spelling: string, marks: Int32Array}} Spelled */
const STEP = 32;
// The letters of raw[lo..end), taken out by the platform's own replace, which keeps every
// code unit as it stands, and the marks counted after.
const GAPS = new RegExp(`[${EDGE}${COLLAPSE_CHARS}]+`, "g");
/** @param {string} raw @param {number} lo @param {number} end @returns {Spelled} */
function spell(raw, lo, end) {
  const spelling = (lo === 0 && end === raw.length ? raw : raw.slice(lo, end)).replace(
    GAPS,
    "",
  );
  const marks = new Int32Array(Math.ceil(spelling.length / STEP));
  for (let i = lo, n = 0; n < spelling.length; i++) {
    const code = raw.charCodeAt(i);
    if ((unitKinds[code] === 3 ? kindOf(code) : unitKinds[code]) !== 0) continue;
    if (n % STEP === 0) marks[n / STEP] = i;
    n += 1;
  }
  return { spelling, marks };
}
/** @type {WeakMap<PageReading, Spelled>} */
const spellings = new WeakMap();
/** @param {PageReading} reading */
function spelledReading(reading) {
  let spelled = spellings.get(reading);
  if (!spelled)
    spellings.set(reading, (spelled = spell(reading.raw, 0, reading.raw.length)));
  return spelled;
}
// Where letter `s` of a run spelled from `raw` stands in raw.
/** @param {string} raw @param {Spelled} spelled @param {number} s */
function rawAt(raw, { marks }, s) {
  let i = /** @type {number} */ (marks[Math.floor(s / STEP)]);
  for (let k = s % STEP; k > 0; k--) while (kindOf(raw.charCodeAt(++i)) !== 0);
  return i;
}
// The raw place just past `count` letters at or after `at`, or raw's end.
/** @param {string} raw @param {number} at @param {number} count */
function lettersFrom(raw, at, count) {
  let i = at;
  for (let seen = 0; i < raw.length && seen < count; i++) if (!gapAt(raw, i)) seen += 1;
  return i;
}
// The copy of a quote whose letters start at letter `s` of a run spelled from the
// reading, where the reading parts them as the quote does: whatever parts each letter
// from the one before (nothing, an edge or whitespace) is held to the quote's space or
// none there. Null where it parts them otherwise.
/** @param {PageReading} reading @param {Spelled} spelled @param {QuoteEntry} entry
 * @param {number} s @returns {Copy | null} */
function copyAt(reading, spelled, entry, s) {
  const { raw } = reading;
  let i = rawAt(raw, spelled, s);
  const from = i;
  for (let j = 1; j < entry.spelling.length; j++) {
    let parted = 0;
    for (let kind; (kind = kindOf(raw.charCodeAt(++i))) !== 0;)
      if (kind > parted) parted = kind;
    if (parted === (entry.spaced[j] ? 0 : 2)) return null;
  }
  return { from, to: i + 1, fenced: !withinCell(reading, from, i + 1), near: null };
}
// An automaton over a set of strings (Aho–Corasick): a trie of their code units, each
// state's longest proper suffix that is also a state (`fail`), and the nearest such
// suffix at which a string ends (`link`). One pass over a run of code units then hears
// every place each string ends in it, copies that overlap included, in time with the
// run, the strings' total length and the places found, however many of the strings
// share a start or how many lengths they come in.
/** @template E @typedef {{edges: Map<number, number>, fail: number[], link: number[],
 * ends: (E[] | null)[], depth: number[]}} Automaton */
// A state's transitions are keyed in one map by the state and the code unit together.
/** @param {number} state @param {number} code */
const edgeKey = (state, code) => state * 0x10000 + code;
/** @template E @param {Iterable<readonly [string, E]>} strings @returns {Automaton<E>} */
function automatonOf(strings) {
  /** @type {Map<number, number>} */
  const edges = new Map();
  const [fail, link, parent, code, depth] = [[0], [0], [0], [0], [0]];
  /** @type {(E[] | null)[]} */
  const ends = [null];
  for (const [string, entry] of strings) {
    let state = 0;
    for (let t = 0; t < string.length; t++) {
      const unit = string.charCodeAt(t);
      let next = edges.get(edgeKey(state, unit));
      if (next === undefined) {
        next = fail.length;
        edges.set(edgeKey(state, unit), next);
        fail.push(0);
        link.push(0);
        ends.push(null);
        parent.push(state);
        code.push(unit);
        depth.push(/** @type {number} */ (depth[state]) + 1);
      }
      state = next;
    }
    (ends[state] ??= []).push(entry);
  }
  // Each state's suffix links from those of the states above it, shallowest first.
  const states = [...fail.keys()].slice(1);
  states.sort(
    (a, b) => /** @type {number} */ (depth[a]) - /** @type {number} */ (depth[b]),
  );
  for (const state of states) {
    const unit = /** @type {number} */ (code[state]);
    let suffix = 0;
    for (let at = /** @type {number} */ (parent[state]); at !== 0;) {
      at = /** @type {number} */ (fail[at]);
      const next = edges.get(edgeKey(at, unit));
      if (next !== undefined) {
        suffix = next;
        break;
      }
    }
    fail[state] = suffix;
    link[state] = ends[suffix] ? suffix : /** @type {number} */ (link[suffix]);
  }
  return { edges, fail, link, ends, depth };
}
// Every place in a run of code units where one of an automaton's strings starts: its
// entry, and the place of its first code unit.
/** @template E @param {Automaton<E>} automaton @param {number} length
 * @param {(t: number) => number} codeAt @param {(entry: E, start: number) => void} take */
function runAutomaton({ edges, fail, link, ends, depth }, length, codeAt, take) {
  let state = 0;
  for (let t = 0; t < length; t++) {
    const unit = codeAt(t);
    for (;;) {
      const next = edges.get(edgeKey(state, unit));
      if (next !== undefined) {
        state = next;
        break;
      }
      if (state === 0) break;
      state = /** @type {number} */ (fail[state]);
    }
    for (let at = ends[state] ? state : link[state]; at; at = link[at])
      for (const entry of ends[at] ?? [])
        take(entry, t + 1 - /** @type {number} */ (depth[at]));
  }
}
// Every place each of `strings` starts in `text`, copies that overlap included, with the
// entry it came with, each string's in order. A few strings are each found by the
// platform's string search, which in the 3.3 million letters of a 4 MB text document
// takes under 1 ms a string, against 60 to 90 ms for one pass of an automaton; more are
// found by one pass of an automaton over them all (`automaton`, built where none is
// handed in), so finding many strings costs the text and the strings, not their product.
const FEW = 32;
/** @template E @param {string} text @param {readonly (readonly [string, E])[]} strings
 * @param {(entry: E, start: number) => void} take @param {() => Automaton<E>} [automaton] */
function eachPlace(text, strings, take, automaton = () => automatonOf(strings)) {
  if (strings.length > FEW) {
    runAutomaton(automaton(), text.length, (t) => text.charCodeAt(t), take);
    return;
  }
  for (const [string, entry] of strings)
    if (string)
      for (let at = text.indexOf(string); at >= 0; at = text.indexOf(string, at + 1))
        take(entry, at);
}
/** @param {string} text @param {Iterable<string>} strings @returns {Map<string, number[]>} */
export function findEach(text, strings) {
  /** @type {Map<string, number[]>} */
  const found = new Map();
  for (const string of strings) found.set(string, []);
  eachPlace(
    text,
    [...found.keys()]
      .filter(Boolean)
      .map((string) => /** @type {const} */ ([string, string])),
    (string, start) => found.get(string)?.push(start),
  );
  return found;
}
/** @typedef {{from: number, to: number, fenced: boolean, near: [number, number] | null}} Copy */
/** @typedef {{quote: string, spelling: string, spaced: Uint8Array, copies: Copy[],
 * changedAt: number}} QuoteEntry */
// A quote's spelling, and which of its letters a space stands before.
/** @param {string} quote @returns {QuoteEntry | null} */
function quoteEntry(quote) {
  const words = quote.split(COLLAPSE).filter(Boolean);
  if (!words.length) return null;
  const spelling = words.join("");
  const spaced = new Uint8Array(spelling.length);
  let at = 0;
  for (const word of words.slice(0, -1)) spaced[(at += word.length)] = 1;
  return { quote, spelling, spaced, copies: [], changedAt: 0 };
}
/** @param {Iterable<QuoteEntry>} entries */
const spellingsOf = (entries) =>
  [...entries].map((entry) => /** @type {const} */ ([entry.spelling, entry]));
/** @param {Iterable<QuoteEntry>} entries @returns {Automaton<QuoteEntry>} */
const quotesAutomaton = (entries) => automatonOf(spellingsOf(entries));
/** @param {Iterable<QuoteEntry>} entries */
const widestOf = (entries) => {
  let widest = 0;
  for (const { spelling } of entries) widest = Math.max(widest, spelling.length);
  return widest;
};
// Every copy of `entries`' quotes that starts in raw[lo..hi): each place the page spells
// a quote and parts its letters as the quote does, and whether a fence parts it. The
// whole reading is searched in its kept letters, a span of it in letters spelled from
// the span on to as many letters past it as the widest quote holds.
/** @param {PageReading} reading @param {readonly QuoteEntry[]} entries @param {number} lo
 * @param {number} hi @param {(entry: QuoteEntry, copy: Copy) => void} take
 * @param {() => Automaton<QuoteEntry>} [automaton] the automaton over `entries` */
function scan(reading, entries, lo, hi, take, automaton) {
  const { raw } = reading;
  const spelled =
    lo === 0 && hi >= raw.length
      ? spelledReading(reading)
      : spell(raw, lo, lettersFrom(raw, hi, widestOf(entries)));
  eachPlace(
    spelled.spelling,
    spellingsOf(entries),
    (entry, s) => {
      const copy = copyAt(reading, spelled, entry, s);
      if (copy && copy.from < hi) take(entry, copy);
    },
    automaton,
  );
}
// Where two readings of the page part, as the span of each that differs. Before it both
// hold the same characters, in the same text nodes at the same offsets and in the same
// blocks, with the same fences, and after it they do again, everything there standing
// moved by the difference in their lengths. A change to the page's text, to the edges or
// fences between its words, or to the order its trees are read in shows here by the
// reading's own rules, since it is the readings that are compared. Null where nothing
// differs.
/** @param {PageReading} was @param {PageReading} now
 * @returns {{from: number, was: number, now: number} | null} */
function changedSpan(was, now) {
  const [a, b] = [was.raw, now.raw];
  const shift = b.length - a.length;
  const shorter = Math.min(a.length, b.length);
  /** @param {IndexedSegment} x @param {IndexedSegment} y @param {number} by */
  const same = (x, y, by) =>
    x.node === y.node &&
    x.start === y.start &&
    x.end === y.end &&
    x.rawStart + by === y.rawStart &&
    x.block === y.block &&
    x.textBlock === y.textBlock &&
    x.words === y.words &&
    x.gen === y.gen;
  let from = 0;
  while (from < shorter && a.charCodeAt(from) === b.charCodeAt(from)) from++;
  for (let k = 0; k < was.segments.length || k < now.segments.length; k++) {
    const x = was.segments[k];
    const y = now.segments[k];
    // A segment begins at the edge before it, which says where it stands.
    const start = Math.max(0, Math.min(x?.rawStart ?? from, y?.rawStart ?? from) - 1);
    if (start >= from) break;
    if (!x || !y || !same(x, y, 0)) {
      from = start;
      break;
    }
  }
  for (let k = 0; ; k++) {
    const x = was.fences[k];
    const y = now.fences[k];
    if (x === undefined && y === undefined) break;
    if (x === y) {
      if (/** @type {number} */ (x) >= from) break;
      continue;
    }
    from = Math.min(from, x ?? from, y ?? from);
    break;
  }
  let back = 0;
  while (
    back < shorter - from &&
    a.charCodeAt(a.length - 1 - back) === b.charCodeAt(b.length - 1 - back)
  )
    back++;
  for (let k = 1; k <= was.segments.length && k <= now.segments.length; k++) {
    const x = /** @type {IndexedSegment} */ (was.segments[was.segments.length - k]);
    const y = /** @type {IndexedSegment} */ (now.segments[now.segments.length - k]);
    const xEnd = x.rawStart + x.end - x.start;
    if (a.length - xEnd >= back) break;
    if (!same(x, y, shift)) {
      back = Math.min(back, a.length - xEnd, b.length - (y.rawStart + y.end - y.start));
      break;
    }
  }
  for (let k = 1; ; k++) {
    const x = was.fences[was.fences.length - k];
    const y = now.fences[now.fences.length - k];
    if (x === undefined && y === undefined) break;
    if (x !== undefined && x + shift === y) {
      if (x < a.length - back) break;
      continue;
    }
    // A fence that moved is a change at the edge it stands at.
    if (x !== undefined) back = Math.min(back, Math.max(0, a.length - x - 1));
    if (y !== undefined) back = Math.min(back, Math.max(0, b.length - y - 1));
    break;
  }
  const span = { from, was: a.length - back, now: b.length - back };
  return span.was === from && span.now === from ? null : span;
}
// The place `count` of the page's letters before `at`, or its start.
/** @param {string} raw @param {number} at @param {number} count */
function lettersBefore(raw, at, count) {
  let i = at;
  for (let seen = 0; i > 0 && seen < count;) if (!gapAt(raw, --i)) seen += 1;
  return i;
}

// The quotes anchor placement keeps (`trackQuotes`), each with every copy it has in each
// kept reading a search asks for it: the frame's, where a quote in prose stands, and a
// datum's own, where a quote in that datum stands (`pageText`), whether the datum is a
// part or stands in one or in the frame. A reading's copies are found by one pass over it
// for every quote it lacks, when a search first asks it for one, and are carried from one
// reading of the same words to the next through what changed between the two (`carry`),
// counting each carry that changed a quote (`version`), and which carry each quote's
// copies, or the words a resolution read beside one, last changed in (`changedAt`), so a
// reader asks for the quotes changed since it last asked (`quotesChanged`). A change to
// one piece carries the copies of the readings it holds alone.
/** @typedef {{reading: PageReading, entries: Map<string, QuoteEntry>,
 * automaton: Automaton<QuoteEntry> | null, rewritten: Set<Node>}} PieceIndex */
const index = {
  /** @type {Set<string>} */
  quotes: new Set(),
  // By the element each reading is of (`readingPieces`).
  /** @type {Map<Element, PieceIndex>} */
  pieces: new Map(),
  version: 0,
};
// Each of `quotes`' copies in a piece: those a pass of its own found in this reading
// already (`askedOf`), and the rest by one search of its letters for all of them (`scan`).
/** @param {PieceIndex} piece @param {Iterable<string>} quotes */
function addQuotes(piece, quotes) {
  const { reading, entries } = piece;
  const asked = askedOf.get(reading);
  /** @type {QuoteEntry[]} */
  const fresh = [];
  for (const quote of quotes) {
    const known = asked?.has(quote);
    const found = known ? asked?.get(quote) : quoteEntry(quote);
    asked?.delete(quote); // the index carries it from here
    if (found) entries.set(quote, found);
    if (found && !known) fresh.push(found);
  }
  piece.automaton = null;
  if (fresh.length)
    scan(reading, fresh, 0, reading.raw.length, (entry, copy) =>
      entry.copies.push(copy),
    );
}
// The reading the element keyed `key` has now, read again where it changed: the frame's
// for the page's body, else the element's own words; null where the page reads it no
// longer.
/** @param {Element} key */
function pieceReading(key) {
  if (key === pageDocument()) return pageText();
  return inPage(key) ? pageText(key) : null;
}
// A piece's index brought to `now` from the reading it was last brought to. A copy before
// the change stands where it stood, one after it stands moved by what the change put in
// or took out, and one the change touched is gone; the copies there are now are read from
// the change and as many letters before it as the widest quote holds, since a copy that
// starts further back ends before the change. A text node a change rewrote (`rewritten`,
// from `tellHearers`) counts as changed wherever it stands in both, since its copies'
// ranges moved, and with the node, its place inside or outside a section. Each quote
// whose copies moved has changed, and so has one with a change in the words a resolution
// read beside a copy of it. A piece that is gone loses every copy.
/** @param {PieceIndex} piece @param {PageReading} now */
function carry(piece, now) {
  const was = piece.reading;
  const rewritten = [...piece.rewritten];
  piece.reading = now;
  piece.rewritten.clear();
  if (was === now || !piece.entries.size) return;
  const parted = changedSpan(was, now);
  // Where the change starts, and how far from each reading's end it stops.
  let from = parted?.from ?? Infinity;
  let back = parted ? was.raw.length - parted.was : Infinity;
  for (const node of rewritten) {
    const at = isText(node) ? now.positions.get(node) : undefined;
    if (at === undefined || !was.positions.has(/** @type {Text} */ (node))) continue;
    from = Math.min(from, at);
    back = Math.min(back, now.raw.length - at - /** @type {Text} */ (node).data.length);
  }
  if (from === Infinity) return;
  const span = { was: was.raw.length - back, now: now.raw.length - back };
  const shift = span.now - span.was;
  /** @type {Set<QuoteEntry>} */
  const moved = new Set();
  for (const entry of piece.entries.values()) {
    /** @type {Copy[]} */
    const copies = [];
    let changed = false;
    for (const copy of entry.copies) {
      const { near } = copy;
      if (near && near[0] <= span.was && near[1] >= from) changed = true;
      if (copy.to <= from) copies.push(copy);
      else if (copy.from >= span.was) {
        copies.push({
          from: copy.from + shift,
          to: copy.to + shift,
          fenced: copy.fenced,
          near: near && [near[0] + shift, near[1] + shift],
        });
      } else changed = true;
    }
    entry.copies = copies;
    if (changed) moved.add(entry);
  }
  const entries = [...piece.entries.values()];
  const lo = lettersBefore(now.raw, from, widestOf(entries));
  const automaton = () => (piece.automaton ??= quotesAutomaton(entries));
  scan(
    now,
    entries,
    lo,
    span.now,
    (entry, copy) => {
      if (copy.to <= from) return; // standing before the change, as it stood
      entry.copies.push(copy);
      moved.add(entry);
    },
    automaton,
  );
  if (moved.size) index.version += 1;
  for (const entry of moved) {
    entry.copies = entry.copies
      .map((copy) => ({ ...copy, near: null }))
      .sort((left, right) => left.from - right.from);
    entry.changedAt = index.version;
  }
}
// Keep the index for these quotes, each quote anchor placement's threads name: a quote it
// names no longer is let go.
/** @param {Iterable<string>} quotes */
export function trackQuotes(quotes) {
  index.quotes = new Set(quotes);
  for (const piece of index.pieces.values())
    for (const quote of piece.entries.keys())
      if (!index.quotes.has(quote)) piece.entries.delete(quote);
}
// Each indexed reading brought to the one its element has now; one the page reads no
// longer is carried to no copies and let go, and its quotes are returned.
function bringPieces() {
  /** @type {string[]} */
  const lost = [];
  for (const [key, piece] of index.pieces) {
    const now = pieceReading(key);
    if (now) carry(piece, now);
    else {
      index.pieces.delete(key);
      const held = [...piece.entries.values()].filter(({ copies }) => copies.length);
      if (held.length) index.version += 1;
      lost.push(...held.map(({ quote }) => quote));
    }
  }
  return lost;
}
// The quotes whose copies changed after the index's version `since`, the index brought
// to the page as it reads now, and the version it stands at.
/** @param {number} since */
export function quotesChanged(since) {
  catchUpReading();
  const lost = bringPieces();
  const { version } = index;
  if (version === since) return { version, quotes: [] };
  const quotes = new Set(lost);
  for (const piece of index.pieces.values())
    for (const entry of piece.entries.values())
      if (entry.changedAt > since) quotes.add(entry.quote);
  return { version, quotes: [...quotes] };
}
// A quote the index keeps, asked of a kept reading, is found in that reading's index,
// with every other quote it keeps that the reading lacks. Any other quote, as a draft's
// before anchor placement keeps it, or one asked of a reading since read again, is
// found by a pass of its own, kept with the reading, since a capture asks it at each
// width of context; the index takes it from there when it comes to keep the quote.
/** @type {WeakMap<PageReading, Map<string, QuoteEntry | null>>} */
const askedOf = new WeakMap();
/** @param {PageReading} text @param {string} quote */
function copiesOf(text, quote) {
  const key = readingPieces.get(text);
  if (key && index.quotes.has(quote) && pieceReading(key) === text) {
    let piece = index.pieces.get(key);
    if (!piece)
      index.pieces.set(
        key,
        (piece = {
          reading: text,
          entries: new Map(),
          automaton: null,
          rewritten: new Set(),
        }),
      );
    carry(piece, text);
    const { entries } = piece;
    if (!entries.has(quote))
      addQuotes(
        piece,
        [...index.quotes].filter((wanted) => !entries.has(wanted)),
      );
    const kept = entries.get(quote);
    if (kept) return kept;
  }
  let asked = askedOf.get(text);
  if (!asked) askedOf.set(text, (asked = new Map()));
  if (asked.has(quote)) return asked.get(quote) ?? null;
  const entry = quoteEntry(quote);
  if (entry)
    scan(text, [entry], 0, text.raw.length, (_, copy) => entry.copies.push(copy));
  asked.set(quote, entry);
  return entry;
}
/** @type {WeakMap<PageReading, Map<string, Map<Element | null, Copy | null>>>} */
const chosen = new WeakMap();
/** @param {PageReading} text @param {string} quote @param {{prefix?: string, suffix?: string}} anchor @param {Element | null} [within] */
export function findQuote(text, quote, anchor, within) {
  const [pre, post] = [anchor.prefix ?? "", anchor.suffix ?? ""];
  // The copies first, every time: asking them is what brings a quote the index has
  // come to keep into it (`copiesOf`), so a change to it is heard.
  const entry = copiesOf(text, quote);
  // An anchor asked of a reading again has the answer it had, which is kept with the
  // reading: a selection's anchor is asked by everything that shows or acts on it.
  let asked = chosen.get(text);
  if (!asked) chosen.set(text, (asked = new Map()));
  const question = `${quote}\u0000${pre}\u0000${post}`;
  let answers = asked.get(question);
  if (!answers) asked.set(question, (answers = new Map()));
  const known = answers.get(within ?? null);
  if (known !== undefined) return known ? spanOf(text, known.from, known.to) : [];
  if (!entry) {
    answers.set(within ?? null, null);
    return [];
  }
  // A unique exact-context occurrence wins. If no context survives, a sole quote
  // occurrence is still identifiable; two are not. Document order is not identity:
  // guessing the first copy after the intended one's neighbours changed quietly moves
  // a comment to words it was never made on. The copies are taken in order within the
  // section, each one past the last, so copies that overlap are one, the first: that is
  // the quote repeating itself, as "aa" does in "aaa", not the page saying it twice. A
  // copy a fence parts takes its place in that order and is no candidate, so the copy
  // after it is the one past it, as the file's reading takes them
  // (anchor_capture.py, `occurrences`; tests/quote_cases.json holds both to one set of
  // cases). Context is read only to tell copies apart: a sole candidate is the answer
  // whatever its neighbours say, and a second exact one settles that none is unique.
  // Every copy in the words of an element under `within` stands under it, unless a slot
  // of the element's own tree shows it words from outside it.
  const key = readingPieces.get(text);
  const all = !within || (key !== undefined && under(key, within) && !holdsSlot(key));
  /** @type {Copy[]} */
  const candidates = [];
  let end = -1;
  for (const copy of entry.copies) {
    const inside =
      all ||
      (under(pointAt(text, copy.from)?.node, within) &&
        under(pointAt(text, copy.to - 1)?.node, within));
    if (!inside || copy.from < end) continue;
    end = copy.to;
    if (!copy.fenced) candidates.push(copy);
  }
  const exact = [];
  const [preLetters, postLetters] = [pre, post].map((side) =>
    side.replace(COLLAPSE, ""),
  );
  for (const hit of candidates.length > 1 ? candidates : []) {
    if (
      !holds(text, hit.from, pre, /** @type {string} */ (preLetters), true, hit) ||
      !holds(text, hit.to, post, /** @type {string} */ (postLetters), false, hit)
    )
      continue;
    exact.push(hit);
    if (exact.length > 1) break;
  }
  const found =
    candidates.length === 1 ? candidates[0] : exact.length === 1 ? exact[0] : null;
  answers.set(within ?? null, found ?? null);
  // The characters the match covers, cut out of the index the same way a neighbourhood is —
  // walking the segments a second time to rebuild the span would be a second answer to
  // "which text is this", and the two disagree wherever an edge falls inside the match.
  return found ? spanOf(text, found.from, found.to) : [];
}

// Search can travel into native disclosures and hidden-until-found widget panels,
// but cannot expose source data hidden by CSS. Keep that presentation question out of
// the shared reading: stored quote resolution and file comparisons do not read styles.
// display: contents has no box of its own yet still speaks through its children, and
// visibility may be restored by a descendant, so neither is an ancestor veto.
function searchableWords() {
  const styles = new Map();
  const reachable = new Map();
  /** @param {Element} el */
  const style = (el) => {
    let value = styles.get(el);
    if (!value) styles.set(el, (value = getComputedStyle(el)));
    return value;
  };
  /** @param {Element | null} el @returns {boolean} */
  const canReveal = (el) => {
    if (!el) return true;
    const kept = reachable.get(el);
    if (kept !== undefined) return kept;
    const css = style(el);
    const result =
      css.display !== "none" &&
      (css.contentVisibility !== "hidden" ||
        el.getAttribute("hidden") === "until-found") &&
      canReveal(renderedParent(el));
    reachable.set(el, result);
    return result;
  };
  return (/** @type {Segment} */ { node }) => {
    const parent = renderedParent(node);
    return parent && style(parent).visibility === "visible" && canReveal(parent);
  };
}

// Every occurrence of a user's search, as passages in the page reading. This is not
// anchor resolution: a search is allowed to find repeated words, while a stored anchor
// must identify one occurrence or detach. It does keep the passage reader's other rules —
// elastic whitespace, an edge read inside a word or as a gap between two (`scan`), and
// no match crossing an opaque passage fence — so choosing a result produces exactly the
// kind of segments capture and resolution use. Each is found as it is asked for, and a
// match the page doesn't show is a step that finds nothing (null).
/** @param {PageReading} text @param {string} query @returns {Generator<Segment[] | null>} */
function* findText(text, query) {
  const words = query.split(COLLAPSE).filter(Boolean);
  if (!words.length) return;
  // A gap is whitespace and edges in any order, as one character class: a nested
  // quantifier such as `(?:[ws]+|edge)+` tries every split of a whitespace run, so a
  // word followed by a long run, and not by the next word, takes time exponential in
  // the run's length.
  const pattern = new RegExp(
    words
      .map((w) => [...w].map(escape).join(`${EDGE}*`))
      .join(`[${COLLAPSE_CHARS}${EDGE}]+`),
    "giu",
  );
  const searchable = searchableWords();
  for (let match; (match = pattern.exec(text.raw));) {
    const from = match.index;
    const to = from + match[0].length;
    const segments = spanOf(text, from, to);
    if (withinCell(text, from, to) && segments.every(searchable)) yield segments;
    // A rejected match must not consume the beginning of a reachable one.
    else {
      const start = text.raw.slice(from, from + 2);
      const point = start[Symbol.iterator]().next();
      if (!point.done) pattern.lastIndex = from + point.value.length;
      yield null;
    }
  }
}

// Every match of a search over the page's words, in reading order: the frame's and each
// part's, each found in its own reading, since a match stands in one passage cell
// (`findText`) and every part stands in one (`pageText`). Each is found as it is asked
// for, and a part is read when the search reaches it, so whoever asks can take them a
// few at a time: on a page of 30 text documents of 4 MB, reading every part takes 3 s
// in Chromium and 6 to 9 s in Firefox, and a query matching a million times takes
// seconds to check each match is one the page shows (`searchableWords`). A step that
// finds nothing, the step before a part is read or a match the page hides, is null, so a
// reader can stop before each part too. The matches are of the page as it read when the
// search began, and its reader asks again once the page has changed
// (`pageReadingVersion`).
/** @param {string} query @returns {Generator<Segment[] | null>} */
export function* pageMatches(query) {
  const framed = pageText();
  const { marks } = frameCollected();
  /** @param {PartMark} mark */
  const startOf = (mark) => framed.segments[mark.at]?.rawStart ?? Infinity;
  /** @param {PartMark} mark */
  function* inPart(mark) {
    yield null;
    yield* findText(pageText(mark.root), query);
  }
  let m = 0;
  for (const match of findText(framed, query)) {
    if (!match) {
      yield null;
      continue;
    }
    const [first] = match;
    const at = first ? (framed.positions.get(first.node) ?? 0) + first.start : 0;
    for (let mark = marks[m]; mark && startOf(mark) <= at; mark = marks[++m])
      yield* inPart(mark);
    yield match;
  }
  for (const mark of marks.slice(m)) yield* inPart(mark);
}

// Display context completes its outer language-aware word within the local window.
// Oversized tokens use the existing bounded excerpt; stored anchors retain their exact
// character windows. Search and Design descriptions share this presentation reading.
/** @param {PageReading} text @param {readonly Segment[]} segments @param {{before?: number, after?: number}} [options] */
export function contextAround(text, segments, { before = 28, after = 28 } = {}) {
  const [start, end] = spanIn(text, segments);
  /** @param {number} at @param {number} length @param {boolean} backwards */
  function side(at, length, backwards) {
    if (!length) return "";
    const budget = length * 2 + 1;
    const neighbourhoodPoints = [...neighbourhood(text, at, budget, backwards)];
    const points = backwards
      ? neighbourhoodPoints.slice(-budget)
      : neighbourhoodPoints.slice(0, budget);
    const context = points.join("");
    const boundary = backwards
      ? points.slice(0, Math.max(0, points.length - length)).join("").length
      : points.slice(0, length).join("").length;
    const word = textUnits
      .segment(context)
      .containing(backwards ? boundary : boundary - 1);
    const outer = word?.isWordLike
      ? backwards
        ? word.index
        : word.index + word.segment.length
      : boundary;
    const reachesEdge = backwards ? outer === 0 : outer === context.length;
    if (reachesEdge && points.length >= budget) {
      // An unfinished token at the local reading's edge cannot justify reading the
      // whole passage. The caller supplies the visible/spoken outer ellipsis.
      const excerpt = excerptWords(
        backwards ? points.toReversed().join("") : context,
        length,
      ).slice(0, -1);
      return backwards ? [...excerpt].toReversed().join("") : excerpt;
    }
    return (backwards ? context.slice(outer) : context.slice(0, outer)).trim();
  }
  return { before: side(start, before, true), after: side(end, after, false) };
}

/** @template {Element} [E=Element] @param {string} sel @returns {E[]} */
export function pageParts(sel) {
  /** @type {E[]} */
  const elements = pageQueryAll(sel);
  return elements.filter(inPage);
}
