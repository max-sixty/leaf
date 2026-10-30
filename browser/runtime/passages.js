/* The page's one DOM reading and quote resolver.

   Passages use one representation: ordered segments `{node, start, end}` over composed
   text. `textNodesUnder` produces the segments, and quote capture, quote resolution,
   reading position, element labels, and version-comparison readings all use them. Never
   introduce another text walk for one of those jobs: the page's words are `pageText()`
   (its `segments`, `pageBlocks()`), one element's are `elementReading(el, "says" |
   "wrote")`, and both are kept until the page changes. Each segment also carries the
   `block` its words read in, their typographic `textBlock`, and the generated element
   (`gen`) they stand in, which the walk knew on its way down. A datum starts a reading
   block without inserting whitespace into inline text; a cut segment keeps these facts.

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

   `pageText` is the page's whole reading, and every caller shares one of it until the
   page changes underneath. The document reports its own changes, so anything else the
   reading is built out of has to say so here: `fencePassageParts` for the widget parts
   the cell walk fences on, `watchPassageRoot` for a declared shadow stage the walk
   crosses into, and the registry generation, which `pageText` reads each time. A new
   input with no door is a reading that goes stale silently — the mark lands on the
   words the page used to say. The reverse holds too: a change lands where the walk
   reads or it is no change to the reading, by the walk's own rules (`contextAt`), so
   the runtime repainting its chrome does not cost the page a walk.

   Native editing hosts and readonly islands inside them are passage cells. Context
   outside a field never borrows its mutable value; an actual native selection inside
   remains readable. File and browser readings share these ownership fences.
   Native textarea children initialize its value; they are never visible document
   words or surrounding quote context, before or after that value is edited.

   The walk carries its context down (`enter`): each element states once whether it
   starts chrome, silence, generated words, a block or a passage cell, rather than each
   text node climbing to ask. `pageText` indexes back from its string by segment
   (`starts`), and `pointAt` is the one way from a position in `raw` to a node and
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
   injected control. These markers are not interchangeable; `pageWords` is the
   conjunction of the first two, and the comment over it says which hole each half
   alone leaves.

   The search pattern uses only a bounded lead (`LEAD_CAP`) to locate candidates.
   `confirmRest` walks the remainder against passage text. Do not truncate the stored
   quote to satisfy a regular-expression limit; the stored quote is the passage the
   user selected.

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
import { renderedOrder, renderedParent, renderedUnder } from "./shadow-tree.js";
import { decisionFor, registry } from "./registry.js";
import { PAGE_PAINT_ATTRIBUTE, pageUpgraded } from "./page-paint.js";
import { reportPageError } from "./layer-client.js";
import { readPart } from "./semantic-state.js";
import { COLLAPSE, TEXT_BLOCK } from "./kernel-facts.js";
import { textUnits } from "./text-alignment.js";
import { excerptWords } from "./words.js";

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
let settledReading = null;
let settledDecisions;
let settled = null;
let settledKey = "[]";
function settlements() {
  if (settledDecisions !== registry.$decisions || !settledReading) {
    const decisions = (settledDecisions = registry.$decisions);
    settledReading = readPart((root) => {
      const holders = new Map();
      for (const [id, { state }] of root.effective.widgets) {
        const tag = root.document.authored.get(id)?.tag;
        const decision = decisions?.[tag];
        // A decision verb's state is an action value, which carries the detail.
        const outcome =
          decision &&
          /** @type {{detail?: {outcome?: string}} | undefined} */ (
            state[decision.verb]
          )?.detail?.outcome;
        const retires = outcome ? decision.retires[outcome] : null;
        if (retires?.length) holders.set(id, { tag, retires: [...retires] });
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
export function settledAway(el) {
  for (let at = el; at; at = at.parentElement) if (retiredSlot(at)) return true;
  const nodes = [...el.childNodes];
  return (
    nodes.some((n) => n.nodeType === 1 && retiredSlot(n)) &&
    nodes.every((n) =>
      n.nodeType === 1
        ? retiredSlot(n) || uiInside(n, el)
        : n.nodeType !== 3 || !n.data.trim(),
    )
  );
}
const GENERATED = ".lf-ui, [data-lf-gen]";
export const DATUM = "[data-lf-projection][data-lf-datum]";
// A different question the class also used to answer, and not a question about looks at
// all: which document is this element in? The runtime's layer is one container, so a
// widget inside a reply — markup frozen in the log, carried by no version — is exactly
// what that container holds, and the reading position is a place in the page rather than
// in the panel over it. `.lf-ui` reached those elements and a widget's own controls out
// on the page besides, which is the look standing in for the place.
// Across the boundary for the same reason the climb below is: the marker lives out in
// the document, so a node inside a widget's shadow tree can only reach it by leaving the
// tree, and a widget staged inside a reply would otherwise read as page content.
export const inChrome = (node) => Boolean(node && closestAcross(node, ".lf-chrome"));
// Whether the user can see a block's words, for a reading or a landing chosen among the
// page's blocks. A box is no answer: what content-visibility hides keeps its boxes where
// it would stand shown, both an inactive tab's panel (hidden="until-found") and a closed
// <details>' contents, and a `visibility: hidden` block keeps its box too. Focus can land
// on none of them.
export const showsWords = (block) =>
  block.checkVisibility({ visibilityProperty: true });
// The Leaf surface a node stands in, wherever it is seated: the chrome root, or a
// surface of the runtime's own that its owner seats inside page content — the response
// bar in a widget's outlet, a thread a widget places beside its lines. Each such surface
// marks itself `data-lf-runtime`, so the reading travels with the node rather than with
// the place it stands. A press mode that comments on or chooses the page leaves these
// working.
export const LEAF_SURFACE = ".lf-chrome, [data-lf-runtime]";
export const leafSurface = (node) => (node ? closestAcross(node, LEAF_SURFACE) : null);
// The two together, which is what an affordance acting on where the pointer or the caret
// is actually needs: the page's own words, as against the layer over them and as against
// the apparatus inside them. Either half alone leaves a hole, and the hole `.lf-ui` left
// was this one — a declared label is nearer than the panel and answers for itself, so a
// drag across a question an agent asked in a reply read as a passage of the page. It
// raised the page's 💬 and wrote an anchor onto a thread's own id, into an append-only
// log, naming a section no version holds. `leaf thread create --section` refuses exactly that
// from the file side, and file capture is the reading that is supposed to promise less.
export const pageWords = (node) => Boolean(node) && !inChrome(node) && !inUi(node);
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
export const elementOver = (n) => {
  if (n.parentElement) return n.parentElement;
  throw bareTextRefusal(n);
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
function refusesBareText(root) {
  let bare = root.firstChild;
  while (bare && (bare.nodeType !== Node.TEXT_NODE || !bare.data.trim()))
    bare = bare.nextSibling;
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
// The widget a reading belongs to. `.lf-ui` says the runtime built this rather than the
// author, and a reading rooted at the document takes that straight: everything the layer
// holds is the layer's, which is the whole of what the anchor pass and the authored
// reading need. Inside a widget it is a different sentence, and the widget is where it changes.
//
// A widget riding a message stands inside the floating panel, so the panel is `.lf-ui`
// over every word it says — and read straight, a question an agent asked in a reply says
// nothing whatever. That silence did not read as one: it read as an empty slot, so the
// group named its options by their ids in the accessibility tree, On me named the
// question by its id, and every widget reading its own words in a message got "" and fell
// back to something else.
//
// So chrome between the words and their widget is that widget's own apparatus, and chrome
// above the widget is somebody else's. Rooting the search at the element handed in says
// almost the same thing and is wrong in one case that matters: a reading can start
// *inside* generated chrome. A thread box's messages are `<p>`s the runtime built,
// on the page, inside the group they belong to — so bounded at the block, each of them
// stopped being generated, and the authored reading took the user's own comments for
// words the author wrote.
const frameOf = (node) => {
  for (let a = node?.nodeType === 1 ? node : upFrom(node); a; a = upFrom(a))
    if (a.localName?.startsWith("lf-")) return a;
  return null;
};
// What a reading carries down to the text under an element. Every question the walk
// asks of a text node is a question about the elements over it, and each is one rule
// read at one element (`enter`): whether it is chrome or a declared label, the nearer
// deciding (`uiInside`'s rule); whether it silences what it holds (`silences`); whether
// an upgrade generated it (`GENERATED`); which generated element and which text block
// the words stand in; and whether it is one of the passage cells `pageText` fences on.
// Carried down, each element answers once for everything under it; asked per text node,
// the same answers came from a climb apiece, most of them to the body.
//
// Three of the facts stop at a shadow boundary and the rest cross it, because that is
// how the readings they carry are defined: `closest` for chrome, silence and the
// generated marks, the climb through hosts (`closestAcross`, `upFrom`) for blocks and
// cells. A declared root therefore starts its tree-local facts over (`crossed`).
//
// The same rules asked of one element are `contextAt`: the element's ancestors folded
// through `enter` from the top. A walk starts from it at its root, and the page reading's
// watcher asks it where a change landed (`pageReads`), so what the reading skips and what
// it ignores changing are one rule, run in two directions.
const NO_CONTEXT = Object.freeze({
  chrome: false,
  silenced: false,
  generated: false,
  gen: null,
  block: null,
  textBlock: null,
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
const chromeMark = (el) => (el.matches(UI_MARKS) ? !el.matches(SAID) : null);
// What no label can speak through, however it is marked: an inline script, the
// stylesheet a rendered diagram carries inside its <svg>, and a slot the user's
// decision took off the page, or a native field's default-value markup. Chrome is the rest of what the anchor pass skips and
// the one part a label yields — it is a look, and a look cannot make a word the
// runtime's.
const SILENT_TAGS = new Set(["script", "style", "textarea"]);
const silences = (el) => SILENT_TAGS.has(el.localName) || retiredSlot(el);
// A generated element whose words the file cannot model: one the registry does not
// declare as an `x-says` edge of the element holding it. Controls and the hidden comment
// count hold no accepted text, and x-says spans are already in the file-side reading.
const unmodelled = (el) => {
  const attr = el.getAttribute("data-lf-said");
  return !(attr && registry[el.parentElement?.localName]?.["x-says"]?.[attr]);
};
// Automatic control capture uses authored or registry-declared words, never the
// mutable value of a native editing host. A user's actual Range remains readable.
export const fileModelsPassage = (segments) =>
  segments.every(
    ({ node, gen }) =>
      !node.parentElement.isContentEditable && (!gen || !unmodelled(gen)),
  );
// A cell candidate: an opaque widget or one of its original direct children, which
// always fence, or an unmodelled generated element, which fences once a word of the
// page's reading is its own (`readPage`).
const opaque = (el) => passageFences.has(el);
// Editing values and readonly islands inside them are separate passage cells.
// Capture and resolution both stop context at those native ownership boundaries.
const editingBoundary = (el) =>
  Boolean(el.isContentEditable) !== Boolean(el.parentElement?.isContentEditable);
// One element's rules applied to the context over it. `inFrame` is false only for a
// point query's ancestors above the reading's frame, where chrome and the generated
// marks are somebody else's (`frameOf`). An element that starts nothing — most spans,
// links and wrappers — hands its parent's context down unchanged.
function enter(ctx, el, inFrame = true) {
  const marked = el.hasAttributes() && el.matches(MARKS);
  const textBlock = BLOCK_TAGS.has(el.localName);
  const block = textBlock || el.matches(DATUM);
  const editing = editingBoundary(el);
  const cell = opaque(el) || editing || (marked && el.matches(GEN) && unmodelled(el));
  const silent = !ctx.silenced && silences(el);
  if (!marked && !block && !cell && !silent) return ctx;
  const chrome = (marked && inFrame ? chromeMark(el) : null) ?? ctx.chrome;
  const generated = ctx.generated || (marked && inFrame && el.matches(GENERATED));
  return {
    chrome,
    silenced: ctx.silenced || silent,
    generated,
    gen: marked && el.matches(GEN) ? el : ctx.gen,
    block: block ? el : ctx.block,
    textBlock: textBlock ? el : ctx.textBlock,
    island: marked && el.matches(ISLAND) ? el : ctx.island,
    cells: cell ? { el, editing, up: ctx.cells } : ctx.cells,
  };
}
// The tree-local facts start over inside a declared shadow root, as `closest` does.
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
function contextAt(el, frame) {
  const over = [];
  for (let a = el; a; a = upFrom(a)) over.push(a);
  let ctx = NO_CONTEXT;
  let inFrame = !frame;
  for (let i = over.length - 1; i >= 0; i--) {
    const a = over[i];
    if (a === frame) inFrame = true;
    if (a.parentNode?.nodeType === Node.DOCUMENT_FRAGMENT_NODE) ctx = crossed(ctx);
    ctx = enter(ctx, a, inFrame);
  }
  return ctx;
}
// A whole text node as a segment of the context it stands in. Its block is `blockAt`'s
// answer, carried.
const segmentIn = (node, ctx) => ({
  node,
  start: 0,
  end: node.data.length,
  block: ctx.block ?? (ctx.island ? upFrom(ctx.island) : null),
  textBlock: ctx.textBlock ?? (ctx.island ? upFrom(ctx.island) : null),
  gen: ctx.gen,
});
// Which text each named reading keeps. `says` skips the runtime's own words and whatever
// is silenced; `wrote` skips everything an upgrade generated, a declared label included.
// `unsilenced` is `says` with nothing silenced, for the one reader asking whether words
// the page silences are still on screen (render-checks, `retiredSlots`). Like every
// reading its chrome is bounded at the root's frame, so chrome above that widget is not
// its apparatus: a settled slot under a bare `.lf-ui` ancestor still shows its words.
const READINGS = {
  says: (ctx) => !ctx.chrome && !ctx.silenced,
  wrote: (ctx) => !ctx.generated,
  unsilenced: (ctx) => !ctx.chrome,
};
// The `wrote` reading asked of one node: whether it is authored, within the frame `root`
// stands in. Revision installs ask it of every node they place, so it climbs natively
// with the selector `enter`'s generated test is the element form of.
export const authored = (root) => {
  const frame = frameOf(root);
  return (n) => !overIn(n.nodeType === 1 ? n : elementOver(n), GENERATED, frame);
};
// The composed tree, not the light one: a widget that renders the page's words into an
// open shadow root (x-shadow) shows the user what its shadow tree holds, and a host's
// own children stop rendering the moment it has one. A TreeWalker sees none of that — it
// stops dead at the boundary — so the walk is written out, and it is the same walk in
// both directions: a host's shadow root stands in for its children, a <slot> stands for
// what was assigned to it, and everything else is the light DOM it always was. Nothing
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
function walk(root, onText, skip = null, onBreak = null, onElement = null) {
  const frame = frameOf(root);
  const passed = new Map();
  const contextOver = (node) => {
    const over = elementOver(node);
    return passed.get(over) ?? contextAt(over, frame);
  };
  const visitElement = (child, ctx) => {
    if (skip?.(child)) return;
    const inner = enter(ctx, child);
    if (child.localName === "br") {
      onBreak?.(inner);
    } else if (child.localName === "slot") {
      passed.set(child, inner);
      onElement?.(child, inner, true);
      for (const assigned of child.assignedNodes({ flatten: true }))
        assigned.nodeType === Node.TEXT_NODE
          ? onText(assigned, contextOver(assigned))
          : visitElement(assigned, contextOver(assigned));
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
  const visit = (node, ctx, host = null) => {
    const element = host ?? (node.nodeType === Node.ELEMENT_NODE ? node : null);
    if (element) onElement?.(element, ctx, true);
    for (let child = node.firstChild; child; child = child.nextSibling) {
      if (child.nodeType === Node.TEXT_NODE) {
        if (node.nodeType !== Node.ELEMENT_NODE && !child.data.trim()) continue;
        // A shadow root's own text has no element over it, which elementOver refuses:
        // a root the walk crosses into was asked first, so this is a root handed in.
        if (node.nodeType !== Node.ELEMENT_NODE) elementOver(child);
        onText(child, ctx);
      } else if (child.nodeType === Node.ELEMENT_NODE) visitElement(child, ctx);
    }
    if (element) onElement?.(element, ctx, false);
  };
  // A declared tree handed in as the root reads where its host stands, its tree-local
  // facts starting over as they do when the walk crosses into it; the document starts
  // with nothing over it.
  const host = shadowHost(root);
  const start =
    root.nodeType === Node.ELEMENT_NODE
      ? contextAt(root, frame)
      : host
        ? crossed(contextAt(host, frame))
        : NO_CONTEXT;
  visit(root, start);
}
// One named reading's segments under `root`, carrying their reading block (`blockAt`),
// typographic text block and generated element (`gen`, the nearest `[data-lf-gen]`
// in their tree).
// `boundary(element, segmentsSoFar)` answering true leaves that element's words out of
// the walk, for a reader that stands something else in their place (render-checks,
// `shownVerbatim`). The lines format also carries computed block boundaries and
// whitespace; ordinary passage readings never ask the browser for these styles.
export function textNodesUnder(
  root,
  reading = "says",
  boundary = null,
  format = "prose",
) {
  const keeps = READINGS[reading];
  const segments = [];
  let breakBefore = false;
  let lineBefore = "";
  const styles = new Map();
  const style = (element) => {
    if (!styles.has(element)) styles.set(element, getComputedStyle(element));
    return styles.get(element);
  };
  walk(
    root,
    (node, ctx) => {
      if (keeps(ctx)) {
        segments.push({
          ...segmentIn(node, ctx),
          breakBefore,
          ...(format === "lines" && {
            lineBefore,
            whiteSpace: style(renderedParent(node)).whiteSpaceCollapse,
          }),
        });
        breakBefore = false;
        lineBefore = "";
      }
    },
    boundary && ((child) => boundary(child, segments.length)),
    (ctx) => {
      if (keeps(ctx)) {
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

// closest() stops at a shadow boundary, so a node inside a widget's shadow tree can't
// reach the section that holds it or the chrome marker above it — both out in the
// document. Same climb as upFrom, asked with a selector at each tree it passes through.
export function closestAcross(node, selector) {
  let el = node?.nodeType === Node.ELEMENT_NODE ? node : upFrom(node);
  while (el) {
    const hit = el.closest(selector);
    if (hit) return hit;
    el = shadowHost(el.getRootNode());
  }
  return null;
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
/** @param {string} id @param {Document | Element} [root] */
export const elementById = (id, root = document) => {
  const found =
    root === document
      ? document.getElementById(id)
      : root.querySelector(`[id="${CSS.escape(id)}"]`);
  if (found) return found;
  for (const shadow of shadowRootsIn(root)) {
    const inside = shadow.getElementById(id);
    if (inside) return inside;
  }
  return null;
};

// The root of the authored document a node stands in. A message's widget markup is a
// document of its own, placed in that message's body; everything else is the page's
// `main`. A widget resolving a reference among its own document's elements searches
// here, so markup a message quotes neither answers for the page nor reaches into it.
// `doc` is a parsed revision's document, where a version reads its authored `main`.
export const pageDocument = (doc = document) => doc.querySelector("body > main");
// The box the page's Layout arranges: `main`, or the shown child of a `main` that carries
// no Layout itself (layouts.css, `--lf-layout-box`). The margin, the rail and the
// Layout's regions read this box; the authored content is still `pageDocument`.
const isLayoutBox = (box) =>
  getComputedStyle(box).getPropertyValue("--lf-layout-box").trim() === "1";
export const layoutBox = () => {
  const main = document.querySelector("body > main");
  if (!main || isLayoutBox(main)) return main;
  const parts = main.querySelector(':scope > [data-lf-views="parts"]');
  const boxes = [
    ...main.children,
    ...[...(parts?.children ?? [])].flatMap((part) => [...part.children]),
  ];
  return boxes.find((box) => box.checkVisibility() && isLayoutBox(box)) ?? main;
};

export const authoredScope = (node) =>
  closestAcross(node, ".lf-msg-body") ?? pageDocument();

// elementFromPoint retargets to the host for a point over a shadow tree, so it names the
// widget rather than the thing in it, and each root answers for its own. Mark hit testing
// and item aim both use this exact reading, so a projected datum inside a declared shadow
// tree can outrank its host. Only a declared root is entered: another library's tree is
// its control's insides, whose ids (Web Awesome Copy's `#copy-button`) the page never
// authored, so the hit stays at the control.
export const elementFromPointAcross = (x, y) => {
  let el = document.elementFromPoint(x, y);
  while (el && declaredRoot(el)) {
    const inner = el.shadowRoot.elementFromPoint(x, y);
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
export const pageQueryAll = (selector) =>
  [document, ...pageShadowRoots()].flatMap((root) => [
    ...root.querySelectorAll(selector),
  ]);

// A native Range compares one DOM tree. Its light-DOM endpoints can sit inside
// slots, where retargeting every shadow word to its host also selects the host's
// unrelated header. Compare boundary points in the rendered order instead, using
// the same slot-aware ancestry as navigation and layout.
const beforePoint = (node, container, offset) => {
  if (node === container) return false;
  if (container.nodeType === Node.TEXT_NODE || offset === 0)
    return renderedOrder(node, container) < 0;
  const next = container.childNodes[offset];
  return next
    ? renderedOrder(node, next) < 0
    : renderedUnder(node, container) || renderedOrder(node, container) < 0;
};
const coveredBy = (range, node) =>
  !beforePoint(node, range.startContainer, range.startOffset) &&
  (node === range.endContainer ||
    beforePoint(node, range.endContainer, range.endOffset));

// The page reading's segments a range covers, clipped to where it starts and ends.
// Callers place a passage in that reading (`spanIn`), so the segments are the reading's
// own. A walk from the range's own root reads whatever that root holds: select-all
// beside an x-shadow widget composes a range over <html>, and the reading has no
// position for its <title>.
export function segmentsIn(range) {
  const segments = [];
  for (const segment of pageText().segments) {
    const { node } = segment;
    if (!coveredBy(range, node)) continue;
    const start = node === range.startContainer ? range.startOffset : 0;
    const end = node === range.endContainer ? range.endOffset : segment.end;
    if (end > start) segments.push({ ...segment, start, end });
  }
  return segments;
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
export const segmentBlock = (segment) => segment.block ?? segment.node.parentElement;
// Typography follows the HTML text blocks, independently of projected datum identity.
const segmentTextBlock = (segment) => segment.textBlock ?? segment.node.parentElement;
const COLLAPSIBLE = new RegExp(`^(?:${COLLAPSE.source})$`, "u");

// The normalized reading and, when requested, one DOM span for each character in it.
// A block boundary or explicit line break contributes the same collapsed space as
// authored whitespace, mapped to the start of the segment after it. Text and its DOM
// route come from this one walk,
// so a consumer that paints a reading cannot disagree with `quoteFrom` about its words.
function readSegments(segments, mapCharacters) {
  let text = "";
  const units = [];
  let pendingSpace = null;
  const push = (character, start, end) => {
    if (COLLAPSIBLE.test(character)) {
      if (text)
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
  segments.forEach((seg, i) => {
    if (
      i &&
      (seg.breakBefore || segmentTextBlock(seg) !== segmentTextBlock(segments[i - 1]))
    ) {
      const point = { node: seg.node, offset: seg.start };
      push(" ", point, point);
    }
    let offset = seg.start;
    for (const character of seg.node.data.slice(seg.start, seg.end)) {
      const end = offset + character.length;
      push(character, { node: seg.node, offset }, { node: seg.node, offset: end });
      offset = end;
    }
  });
  return mapCharacters ? { text, units } : text;
}
export const quoteFrom = (segments) =>
  /** @type {string} */ (readSegments(segments, false));
export const readingFrom = (segments) =>
  /** @type {{text: string, units: {text: string, start: any, end: any}[]}} */ (
    readSegments(segments, true)
  );
// Cutting one to length is the caller's business and always by code point: half a surrogate
// pair is a character no UTF-8 file can hold, and a quote is written to one.
export const cut = (text, from, to) => [...text].slice(from, to).join("");

// Copyable words use the same segments as prose, with the walk's computed line
// boundaries and whitespace. They need no DOM-coordinate map; quote readings above
// keep their own normalization unchanged.
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
/** @param {{format?: "prose" | "lines"}} [options] */
export const says = (el, options = {}) => {
  const segments = textNodesUnder(el, "says", null, options.format);
  return options.format === "lines" ? linesFrom(segments) : quoteFrom(segments);
};
// The other question, and a different answer: what the *author* wrote here, with
// everything an upgrade generated left out. A version comparison keys sources by it and
// paints a source's words onto the live block that reads the same; a widget asks it to name
// one of its own parts, where `says` would hand back the widget's own declared labels
// along with the words — a picked row's mark is the page speaking, so it is in the
// reading a user points at and out of the row's name.
export const wrote = (el) => quoteFrom(textNodesUnder(el, "wrote"));

// A passage as one Range: what paints it, and what measures it for a scroll.
export function rangeOf(segments) {
  const range = document.createRange();
  range.setStart(segments[0].node, segments[0].start);
  range.setEnd(segments.at(-1).node, segments.at(-1).end);
  return range;
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
// So a gap has to match *something* that separates words. Whitespace is one; an element
// boundary is the other, and it leaves no character behind, which is why the raw text is
// built with one standing in for it. Between the characters of a single word only a
// boundary may fall — `<strong>bold</strong>text` reads as one word and is quoted as one —
// and without that floor a gap could match nothing at all, so "set up" would find "setup"
// in an earlier sentence and anchor there for good.
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
// `raw` (`starts`): segment k's characters are raw[starts[k] .. starts[k] + its length),
// and the one raw character after each segment but the last is an EDGE. Every question
// of the form "which node and offset is raw[i]" goes through `segmentAt`.
//
// The last segment starting at or before `i`, or -1 before the first.
function segmentAt({ starts }, i) {
  let lo = 0;
  let hi = starts.length - 1;
  if (hi < 0 || i < starts[0]) return -1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (starts[mid] <= i) lo = mid;
    else hi = mid - 1;
  }
  return lo;
}
// Where raw[i] came from, as `{node, offset, segment}`, or null for an EDGE or a position
// outside the reading.
export function pointAt(reading, i) {
  const k = segmentAt(reading, i);
  if (k === -1) return null;
  const segment = reading.segments[k];
  const offset = i - reading.starts[k];
  return offset < segment.end - segment.start
    ? { node: segment.node, offset: segment.start + offset, segment }
    : null;
}
// The characters of raw[lo..hi) as segments, so a neighbourhood can be read back with the
// same function that wrote it down. Edges hold no character and are simply absent.
function spanOf(reading, lo, hi) {
  const { segments, starts } = reading;
  const out = [];
  for (let k = Math.max(0, segmentAt(reading, lo)); k < segments.length; k++) {
    const seg = segments[k];
    const from = starts[k];
    if (from >= hi) break;
    const a = Math.max(lo, from);
    const b = Math.min(hi, from + seg.end - seg.start);
    if (b > a)
      out.push({
        ...seg,
        start: seg.start + a - from,
        end: seg.start + b - from,
        breakBefore: seg.breakBefore && a === from,
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
// neighbours out of the whole document — a section is a filter on where a passage may sit,
// not on what surrounds it — so both sides are full except against the document's own
// ends. Anchors written before context reached past the section carry a side clipped at
// that edge; they confirm at that shorter bar, which is the bar they were stored under.
//
// The bar is what the capture actually produces, not a number picked to fit: across every
// selection in the shipped examples, an unmodified page confirms its stored context in full.
//
// An empty side is the case worth stating, because reading it as an absent constraint is
// what sends a comment to a copy it was never made on. The capture reads the whole
// document, so a side comes out empty only where the passage had nothing at all beside it:
// the top or bottom of the page, the one place no capture can give two sides to. That is
// not a missing constraint but the tightest one there is, and it is checkable — a candidate
// confirms it by also having nothing there, which exactly one occurrence does. Refusing to
// read it that way handed the last copy's mark to the first.
const holds = (reading, at, want, before) => {
  // One character is all it takes to refute an empty side, and asking for none would answer
  // with none: doubling zero never grows.
  const there = neighbourhood(reading, at, want.length || 1, before);
  if (!want) return there === "";
  return before ? there.endsWith(want) : there.startsWith(want);
};
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
// anchors for one passage. `holds` asks in the other unit (`want.length`, the stored
// string's own, which is what its endsWith compares in), and that is an over-decision this can
// only over-satisfy: reaching N code points takes at least N code units, so its window is
// never the one short of confirming that a repeated anchor would detach over.
export function neighbourhood(reading, at, want, before) {
  const { fences } = reading;
  const edge = before
    ? (fences.filter((f) => f <= at).at(-1) ?? 0)
    : (fences.find((f) => f >= at) ?? reading.raw.length);
  for (let raw = want * 2; ; raw *= 2) {
    const lo = before ? Math.max(edge, at - raw) : at;
    const hi = before ? at : Math.min(edge, at + raw);
    const text = quoteFrom(spanOf(reading, lo, hi));
    if ([...text].length >= want || (before ? lo === edge : hi === edge)) return text;
  }
}
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
// `name` of its `<details>` rows on every paint says nothing about any words.
const READING_MARKERS = [
  "class",
  "data-lf-said",
  "data-lf-gen",
  "data-lf-projection",
  "data-lf-datum",
  "slot",
  "name",
  "contenteditable",
];
const WATCH_READING = {
  subtree: true,
  childList: true,
  characterData: true,
  attributes: true,
  attributeOldValue: true,
  attributeFilter: READING_MARKERS,
};
let reading = null;
let elementReadings = new WeakMap();
let readingVocabulary;
let readingSettled;
let watcher = null;
// Whether text standing directly under `over` is in the page's reading. The page's
// reading is rooted at the body, which is no widget's frame. Anything but an element — a
// declared shadow root, the document, a node since detached — is answered yes, since
// over-forgetting costs a walk and under-forgetting costs a mark on words the page no
// longer says.
const pageReads = (over) =>
  over?.nodeType !== 1 || READINGS.says(contextAt(over, null));
// A declared label is the page's words wherever it stands, chrome included, so a subtree
// holding one is read whatever its place says.
const holdsSaid = (node) =>
  node.nodeType === 1 && (node.matches(SAID) || node.querySelector(SAID) !== null);
// Whether a node can put words in the reading, standing where `read` says the page reads
// (`pageReads` of its parent). A node that starts chrome (`chromeMark`) and holds no
// label is silent wherever it goes, which is what the panel's re-rendered rows are.
const speaks = (node, read) =>
  (read && !(node.nodeType === 1 && chromeMark(node) === true)) || holdsSaid(node);
// Records are read when the queue drains rather than when they were written, so a place
// is asked about as it stands now. That is still exact: a node that moved between the
// page and the chrome left a childList record at its page end, which speaks either way.
const changesTheReading = (record) => {
  const { target } = record;
  if (record.type === "childList") {
    const read = pageReads(target);
    return [...record.addedNodes, ...record.removedNodes].some((n) => speaks(n, read));
  }
  if (record.type === "characterData") return pageReads(target.parentNode);
  // A marker moved on `target` itself, so its own markers are what is changing and only
  // its place and its labels answer — including a label it has just stopped being.
  if (record.attributeName === "class") {
    const was = /(^|\s)lf-ui(\s|$)/.test(record.oldValue ?? "");
    if (was === target.classList.contains("lf-ui")) return false;
  }
  if (record.attributeName === "name" && target.localName !== "slot") return false;
  const wasSaid = record.attributeName === "data-lf-said" && record.oldValue !== null;
  return wasSaid || holdsSaid(target) || pageReads(target.parentNode);
};
// Which page reading stands: it advances each time one is forgotten, so a reading
// derived from the page's own nodes, as the visual responses are, keeps what it derived
// while this stands.
let readingVersion = 0;
const forgetReading = () => {
  reading = null;
  elementReadings = new WeakMap();
  readingVersion += 1;
};
export function pageReadingVersion() {
  catchUpReading();
  return readingVersion;
}
function watchReading() {
  if (watcher) return watcher;
  watcher = new MutationObserver((records) => {
    if (records.some(changesTheReading)) forgetReading();
  });
  watcher.observe(document, WATCH_READING);
  return watcher;
}
// A declared shadow stage is part of the page's words — `textNodesUnder` walks into one
// at its host's place in the string — and no observer crosses the boundary on its own.
// shadow-stage.js, which is the only door an x-shadow root is built through, hands each
// one here as it fills it.
export function watchPassageRoot(root) {
  watchReading().observe(root, WATCH_READING);
  forgetReading();
}
// An opaque widget and its original direct children fence the cell walk. Marking them is
// not a change to the document, so it is a change nothing else would report: a reading
// taken before a widget was fenced reads its words as ordinary page prose, and a quote
// from the paragraph above could run straight into them. The marking and the forgetting
// are one door for that reason.
export function fencePassageParts(root, children = root.children) {
  passageFences.add(root);
  for (const child of children) passageFences.add(child);
  forgetReading();
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
export function pageText() {
  catchUpReading();
  return (reading ??= readPage());
}
function catchUpReading() {
  const moved = watchReading().takeRecords().some(changesTheReading);
  const vocabulary = registry.$layer?.generation;
  settlements();
  if (moved || vocabulary !== readingVocabulary || settledKey !== readingSettled)
    forgetReading();
  readingVocabulary = vocabulary;
  readingSettled = settledKey;
}
// A reading of one page element's words, kept exactly as long as the page reading: the
// watcher above is what says either has moved. Margin rows, the Page Map and every
// label ask the same elements for their words on every pass, and each walk asks every
// text node under the element where it stands, which on a long page costs more than
// the pass it serves. An element whose words the page does not read — chrome, a node
// since detached, a node of a parsed revision — is outside what the watcher answers
// for, and is read afresh.
//
// A kept reading is answered before asking where the element stands: it was kept only
// while the page read the element, and anything that moves the element out of that —
// its removal, chrome arriving over it — is a change the watcher forgets every kept
// reading for.
export function elementReading(element, reading = "says") {
  catchUpReading();
  let kept = elementReadings.get(element);
  if (kept?.[reading] !== undefined) return kept[reading];
  const value = quoteFrom(textNodesUnder(element, reading));
  if (element.isConnected && element.ownerDocument === document && pageReads(element)) {
    if (!kept) elementReadings.set(element, (kept = {}));
    kept[reading] = value;
  }
  return value;
}
// The walk itself.
function readPage() {
  const segments = [];
  const cellChains = []; // the cell candidates over each segment, nearest first
  const keeps = READINGS.says;
  let breakBefore = false;
  walk(
    document.body,
    (node, ctx) => {
      if (!keeps(ctx)) return;
      segments.push({ ...segmentIn(node, ctx), breakBefore });
      breakBefore = false;
      cellChains.push(ctx.cells);
    },
    null,
    (ctx) => {
      if (keeps(ctx)) breakBefore = true;
    },
  );

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
  const cellOf = (chain) => {
    for (let at = chain; at; at = at.up)
      if (opaque(at.el) || at.editing || dynamicWords.has(at.el)) return at.el;
    return null;
  };

  const parts = [];
  const starts = [];
  const positions = new WeakMap(); // text node -> its offset-zero position in raw
  const fences = new Set();
  let length = 0;
  let previousCell = null;
  segments.forEach((seg, k) => {
    const cell = cellOf(cellChains[k]);
    if (k === 0) {
      if (cell) fences.add(0);
    } else {
      if (cell !== previousCell && (cell || previousCell)) fences.add(length);
      parts.push(seg.breakBefore ? " " : EDGE);
      length += 1;
    }
    starts.push(length);
    positions.set(seg.node, length - seg.start);
    parts.push(seg.node.data);
    length += seg.end - seg.start;
    previousCell = cell;
  });
  if (previousCell) fences.add(length);
  return {
    raw: parts.join(""),
    starts,
    positions,
    fences: [...fences].sort((a, b) => a - b),
    segments,
  };
}
// The page's text blocks in reading order: each block (`blockAt`) holding a word of the
// page's reading, once. Kept on the reading it came from, so it moves exactly when the
// words do and costs nothing to ask again until then.
export function pageBlocks() {
  const text = pageText();
  if (!text.blocks) {
    const seen = new Set();
    text.blocks = text.segments
      .map(({ block }) => block)
      .filter((block) => block && !seen.has(block) && seen.add(block));
  }
  return text.blocks;
}
// Where a passage's segments start and stop in that reading, as [start, stop). A passage
// is `{node, start, end}` segments and every question about the region it covers is asked
// in the reading's own coordinates, so the join between the two is one function — the
// capture writing an anchor's neighbours and the snap widening a drag both ask it. No
// segments is the document's own start: a selection that covers no quotable character has
// a position and no extent.
export function spanIn(reading, segments) {
  const first = segments[0];
  const last = segments.at(-1);
  const start = first ? reading.positions.get(first.node) + first.start : 0;
  return [start, last ? reading.positions.get(last.node) + last.end : start];
}
const escape = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
// How much of a quote the search compiles into its pattern. The bound is the pattern's,
// never the passage's: one expression covering every word of a long passage is a term
// per character, and V8 refuses to compile one that long at all — a ceiling a user
// reaches by selecting a page and pressing c. Measured on the corpus: 1.3ms at this
// length, 11.6ms at five thousand characters, and a SyntaxError at twelve. So the lead
// finds the candidates and the rest of the quote is walked against the text from each,
// which is a comparison per character rather than a term, and the search stays flat in
// the passage's length instead of ending at a wall.
const LEAD_CAP = 400;
// The rest of a quote, matched from `at` by the pattern's own rules: any run of
// whitespace or edges between words, an edge free to fall between two characters of
// one. Answers where the passage ends, or -1 where the text stops saying it.
function confirmRest(raw, at, words) {
  let i = at;
  for (const w of words) {
    const gap = i;
    while (i < raw.length && (raw[i] === EDGE || /\s/.test(raw[i]))) i++;
    if (i === gap) return -1; // two words the text runs together are not these two
    for (const ch of w) {
      while (raw[i] === EDGE) i++;
      if (!raw.startsWith(ch, i)) return -1;
      i += ch.length;
    }
  }
  return i;
}
const withinCell = (text, from, to) =>
  !text.fences.some((fence) => from < fence && fence < to);

export function findQuote(text, quote, anchor, within) {
  const { raw } = text;
  const words = quote.trim().split(/\s+/).filter(Boolean);
  if (!words.length) return [];
  // Whole words up to the cap, and never none: a single word longer than it is still
  // the only lead there is, and one that spent the cap exactly is not worth a term
  // the walk would take anyway.
  const lead = [];
  for (let spent = 0; words.length > lead.length;) {
    const next = words[lead.length];
    if (lead.length && spent + next.length > LEAD_CAP) break;
    lead.push(next);
    spent += next.length + 1;
  }
  const rest = words.slice(lead.length);
  const pattern = new RegExp(
    lead.map((w) => [...w].map(escape).join(`${EDGE}*`)).join(`[\\s${EDGE}]+`),
    "g",
  );
  // A unique exact-context occurrence wins. If no context survives, a sole quote
  // occurrence is still identifiable; two are not. Document order is not identity:
  // guessing the first copy after the intended one's neighbours changed quietly moves
  // a comment to words it was never made on. matchAll steps past each lead, so two
  // occurrences overlapping within it are one candidate — which is the lead's own
  // repetition and not the passage's, since the walk still has to confirm the rest.
  const [pre, post] = [anchor.prefix ?? "", anchor.suffix ?? ""];
  const candidates = [];
  const exact = [];
  for (const at of raw.matchAll(pattern)) {
    const stop = confirmRest(raw, at.index + at[0].length, rest);
    if (stop === -1 || !withinCell(text, at.index, stop)) continue;
    if (
      within &&
      !(
        under(pointAt(text, at.index).node, within) &&
        under(pointAt(text, stop - 1).node, within)
      )
    )
      continue;
    const hit = { from: at.index, to: stop };
    candidates.push(hit);
    if (holds(text, hit.from, pre, true) && holds(text, hit.to, post, false))
      exact.push(hit);
  }
  const found =
    exact.length === 1
      ? exact[0]
      : exact.length === 0 && candidates.length === 1
        ? candidates[0]
        : null;
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
  const style = (el) => {
    if (!styles.has(el)) styles.set(el, getComputedStyle(el));
    return styles.get(el);
  };
  const canReveal = (el) => {
    if (!el) return true;
    if (reachable.has(el)) return reachable.get(el);
    const css = style(el);
    const result =
      css.display !== "none" &&
      (css.contentVisibility !== "hidden" ||
        el.getAttribute("hidden") === "until-found") &&
      canReveal(renderedParent(el));
    reachable.set(el, result);
    return result;
  };
  return ({ node }) => {
    const parent = renderedParent(node);
    return parent && style(parent).visibility === "visible" && canReveal(parent);
  };
}

// Every occurrence of a user's search, as passages in the page reading. This is not
// anchor resolution: a search is allowed to find repeated words, while a stored anchor
// must identify one occurrence or detach. It does keep the passage reader's other rules —
// elastic whitespace and element edges, and no match crossing an opaque passage fence —
// so choosing a result produces exactly the kind of segments capture and resolution use.
export function findText(text, query) {
  const words = query.trim().split(/\s+/u).filter(Boolean);
  if (!words.length) return [];
  const pattern = new RegExp(
    words.map((w) => [...w].map(escape).join(`${EDGE}*`)).join(`[\\s${EDGE}]+`),
    "giu",
  );
  const out = [];
  const searchable = searchableWords();
  for (let match; (match = pattern.exec(text.raw));) {
    const from = match.index;
    const to = from + match[0].length;
    const segments = spanOf(text, from, to);
    if (withinCell(text, from, to) && segments.every(searchable)) out.push(segments);
    // A rejected match must not consume the beginning of a reachable one.
    else
      pattern.lastIndex =
        from + String.fromCodePoint(text.raw.codePointAt(from)).length;
  }
  return out;
}

// Display context completes its outer language-aware word within the local window.
// Oversized tokens use the existing bounded excerpt; stored anchors retain their exact
// character windows. Search and Design descriptions share this presentation reading.
export function contextAround(text, segments, { before = 28, after = 28 } = {}) {
  const [start, end] = spanIn(text, segments);
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

export function pageParts(sel) {
  return pageQueryAll(sel).filter((el) => !inChrome(el));
}
