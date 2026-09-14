/* Retained DOM child reconciliation. */
import { diffArrays } from "/vendor/jsdiff.esm.js";

const detach = (node) => node.remove();

// Make `parent`'s children `nodes`, in order, without moving a node already in place.
// Removing stale nodes first leaves each following survivor exactly one place forward.
export function setChildren(parent, nodes, remove = detach) {
  const keep = new Set(nodes);
  for (const child of [...parent.childNodes]) if (!keep.has(child)) remove(child);
  let cursor = parent.firstChild;
  for (const node of nodes) {
    if (node === cursor) cursor = cursor.nextSibling;
    else parent.insertBefore(node, cursor);
  }
}

/* Apply the difference between two authored revisions to the page standing between them.

   `setChildren` answers for a list its caller already holds. This answers a question the
   live tree cannot be asked at all: what did the author change. Diffing the page against
   the arriving source would answer a different one — what is different about the page —
   and everything the browser, the runtime, a reader, or a page module has done to that
   page since it loaded is different about it. A reader's open `<details>` closes, a
   tokenizer's spans are torn out of a code block nobody edited, a tab stop the runtime
   lent to put focus somewhere is taken back, and what a page module built inside an
   authored container is swept out as markup the source does not have.

   So both sides of the diff are source. `before` and `after` are the two revisions'
   authored `main`, inert and untouched by anything: whatever they agree on, this does not
   touch. `pairs` carries the correspondence, from a source node to the live node standing
   for it — built by a lockstep walk at boot, when the page is still exactly its own
   source, and kept up by every patch since.

   The live tree is therefore written only where the author wrote: a text node's differing
   run, an attribute whose value the two sources disagree on, an element one of them has
   and the other has not. A reader keeps everything else, including the things this had no
   way to recognize as theirs.

   What the caller answers, since this module knows no registry, namespace or document:

   - `pairs`: the source-to-live map, read and written here as the patch proceeds.
   - `arrive(node)`: bring this source node into the document — import it, pair the whole
     subtree, and read whatever has to be read off a widget's markup before a controller
     owns its children. Returns the live node to place.
   - `retire(element)`: this live element is leaving, with every element under it.
   - `declared(element)`: an upgraded widget, whose children are its controller's. Asked
     of the held element; a match names the same element on both sides.
   - `unchanged(before, after)`: that widget's authored markup is the same markup. The
     caller compares the digests each revision's capture recorded.
   - `same(before, after)`: two source elements are spelled the same way, read past the
     address each revision was delivered at. Asked of an element whose interior a pass
     other than a controller has taken, since no capture digested it.
   - `generated(node)`: the live node is the runtime's own. Only placement asks, because
     only placement walks live children; nothing here matches or removes on it.

   Matching runs in three passes, narrowest first, and each pass only sees what the one
   before it left. An id is a name the author gave, so it wins outright. Then the siblings
   that did not change at all are pinned by an exact signature — node type, tag, and the
   words under it — through `diffArrays`, so a list of paragraphs stays still when one is
   inserted among them. Only the gaps between those pins are diffed again, by kind alone,
   which is what pairs a paragraph with its own rewrite. */
export function patchTree(before, after, rules) {
  const live = rules.pairs.get(before);
  patchAttributes(live, before, after);
  patchChildren(tree(live), tree(before), tree(after), rules);
}

// A template's tree is its content fragment, not its children; `childNodes` is empty
// however much markup it holds.
const tree = (node) => (node.localName === "template" ? node.content : node);

// Only where the two revisions disagree. An attribute they both carry is left exactly as
// the page has it, which is the whole of how a reader's `<details open>`, a tab stop
// `focus.js` lent to land them somewhere, and anything a page module wrote survive a
// revision that never mentioned them.
function patchAttributes(live, before, after) {
  for (const { name, value } of before.attributes) {
    if (after.hasAttribute(name)) continue;
    if (name === "class") live.classList.remove(...tokens(value));
    else live.removeAttribute(name);
  }
  for (const { name, value } of after.attributes) {
    const held = before.getAttribute(name);
    if (held === value) continue;
    // Classes are a set the page shares with the runtime, so only the author's own
    // members move; every mark and state class beside them stays.
    if (name === "class") {
      live.classList.remove(...tokens(held ?? ""));
      live.classList.add(...tokens(value));
    } else live.setAttribute(name, value);
  }
}

const tokens = (value) => value.split(" ").filter(Boolean);

// Only the run of words that actually changed. Assigning `data` replaces the node's
// whole content, and the platform's replace-data step collapses every Range endpoint
// inside what it replaced — which is the reader's own selection, in exactly the
// paragraph a revision rewrote while they were reading it. Trimming to the differing
// middle leaves every offset on either side of it where it was, so a selection over
// words the revision kept survives the words beside it changing.
function writeText(node, next) {
  const held = node.data;
  if (held === next) return;
  let prefix = 0;
  while (prefix < held.length && prefix < next.length && held[prefix] === next[prefix])
    prefix += 1;
  let suffix = 0;
  while (
    suffix < held.length - prefix &&
    suffix < next.length - prefix &&
    held[held.length - suffix - 1] === next[next.length - suffix - 1]
  )
    suffix += 1;
  node.replaceData(
    prefix,
    held.length - prefix - suffix,
    next.slice(prefix, next.length - suffix),
  );
}

// Everything leaving, told to the caller before it goes. The element itself and every
// element under it: a widget inside a replaced wrapper is as gone as the wrapper.
function retire(node, rules) {
  if (node.nodeType !== Node.ELEMENT_NODE) return;
  rules.retire(node);
  for (const inner of node.querySelectorAll("*")) rules.retire(inner);
}

// Everything one source element stood for leaves with it: the live element, and any
// node paired under it that a page module had since moved elsewhere in the document.
// Removing the element alone would leave that node standing for a source that is gone,
// and its rebuilt replacement would then stand beside it under the same name.
function evict(before, live, rules) {
  retire(live, rules);
  live.remove();
  for (const inner of sourceNodes(before)) {
    const stray = rules.pairs.get(inner);
    // Still in some tree, and not the one that just left with the element. Asked of
    // the parent rather than the document, because a template's content is a fragment
    // nothing is ever connected to.
    if (!stray?.parentNode || live.contains(stray)) continue;
    retire(stray, rules);
    stray.remove();
  }
}

function* sourceNodes(node) {
  for (const child of tree(node).childNodes) {
    yield child;
    yield* sourceNodes(child);
  }
}

function patchChildren(liveParent, beforeParent, afterParent, rules) {
  const held = [...beforeParent.childNodes];
  const wanted = [...afterParent.childNodes];
  const matches = matchNodes(held, wanted);
  const matched = new Set(matches.values());
  for (const node of held) {
    if (matched.has(node)) continue;
    evict(node, rules.pairs.get(node), rules);
  }
  const placed = [];
  for (const node of wanted) {
    const before = matches.get(node);
    const held = before && rules.pairs.get(before);
    // An unmatched source node is new, and so is one whose live counterpart has left
    // every tree. One a page module moved elsewhere is still that element: the author's
    // change reaches it where it stands, and placement leaves it there. Standing is a
    // parent rather than a connection, since a template's content is never connected.
    const live = held?.parentNode ? held : null;
    if (!live) {
      placed.push(rules.arrive(node));
      continue;
    }
    if (node.nodeType !== Node.ELEMENT_NODE) writeText(live, node.data);
    else if (!atomic(before, live, rules)) patchTree(before, node, rules);
    else if (!kept(before, node, rules)) {
      // Its interior is not this patch's to reach into, so a changed one cannot be
      // corrected from outside. It leaves, and its replacement arrives as a new element.
      evict(before, live, rules);
      placed.push(rules.arrive(node));
      continue;
    }
    rules.pairs.set(node, live);
    if (live.parentNode === liveParent) placed.push(live);
  }
  place(liveParent, placed, rules.generated);
}

// Whether this element's interior is beyond the patch. A widget's is its controller's
// from the moment it upgrades, and the caller names those. Any element's can also be
// taken by a pass with a reason to own it: the tokenizer's spans stand where a code
// block's one authored text node stood, and the nodes this patch paired are then not
// there to write through — putting one back would stand the source's own text beside
// the colouring of it. Both are read the same way afterwards: whole, or not at all.
const atomic = (before, live, rules) =>
  rules.declared(before) ||
  [...tree(before).childNodes].some(
    (node) => rules.pairs.get(node)?.parentNode !== tree(live),
  );

// Whether the two revisions spell such an element the same way. A widget answers from
// the digests its captures recorded, which is the markup the server read of each; nothing
// else has a capture, and answers from the markup itself, read past the delivery address
// each revision wrote into it.
const kept = (before, after, rules) =>
  rules.declared(before) ? rules.unchanged(before, after) : rules.same(before, after);

function matchNodes(held, wanted) {
  const matches = new Map();
  const matched = new Set();
  const byId = new Map();
  for (const node of held)
    if (node.nodeType === Node.ELEMENT_NODE && node.id && !byId.has(node.id))
      byId.set(node.id, node);
  for (const node of wanted) {
    if (node.nodeType !== Node.ELEMENT_NODE || !node.id) continue;
    const match = byId.get(node.id);
    if (!match || match.localName !== node.localName || matched.has(match)) continue;
    matches.set(node, match);
    matched.add(match);
  }
  alignRest(
    held.filter((node) => !matched.has(node)),
    wanted.filter((node) => !matches.has(node)),
    matches,
  );
  return matches;
}

const COLLAPSE = /\s+/g;

// Exact enough that two of them being equal means the revision left this sibling alone,
// and loose enough that reindenting the source does not unpin the whole list. Both sides
// are authored markup, so every word under the node is the author's to compare.
const signature = (node) => {
  if (node.nodeType !== Node.ELEMENT_NODE) return `${node.nodeType}:${node.data}`;
  const words = (node.localName === "template" ? node.content : node).textContent;
  return `1:${node.localName}#${node.id}:${words.replace(COLLAPSE, " ").trim()}`;
};

function alignRest(held, wanted, matches) {
  let heldAt = 0;
  let wantedAt = 0;
  let gapHeld = [];
  let gapWanted = [];
  const closeGap = () => {
    pairInGap(gapHeld, gapWanted, matches);
    gapHeld = [];
    gapWanted = [];
  };
  for (const run of diffArrays(held.map(signature), wanted.map(signature))) {
    const count = run.value.length;
    if (run.added) gapWanted.push(...wanted.slice(wantedAt, (wantedAt += count)));
    else if (run.removed) gapHeld.push(...held.slice(heldAt, (heldAt += count)));
    else {
      closeGap();
      for (let at = 0; at < count; at++)
        matches.set(wanted[wantedAt + at], held[heldAt + at]);
      heldAt += count;
      wantedAt += count;
    }
  }
  closeGap();
}

// Inside one edited stretch: these are the siblings the revision rewrote, and a rewrite
// is still the element it rewrote. Diffed rather than walked in step, because a stretch
// holds insertions too and a cursor meets them in the two ways that cost a reader their
// node. A sibling of another kind above the one they are reading — a heading, a list, an
// unnamed widget — is nothing the cursor can pair, so it spends the cursor and the
// reader's own paragraph is left with no partner and removed. A sibling of the same kind
// above it takes the pairing that belonged to the paragraph below.
//
// Compared rather than keyed, because what may pair here is not an equality. Two elements
// the source names differently are never each other; an element named on one side only is
// that name being given or taken away, which is a thing to do to an element. A key can
// state the first or the second and not both — `p#a` would have to equal `p` while `p#a`
// differs from `p#b` — so the rule travels as the comparator it is.
function pairInGap(held, wanted, matches) {
  let heldAt = 0;
  let wantedAt = 0;
  for (const run of diffArrays(held, wanted, { comparator: interchangeable })) {
    const count = run.value.length;
    if (run.added) wantedAt += count;
    else if (run.removed) heldAt += count;
    else {
      for (let at = 0; at < count; at++)
        matches.set(wanted[wantedAt + at], held[heldAt + at]);
      heldAt += count;
      wantedAt += count;
    }
  }
}

const interchangeable = (held, wanted) =>
  held.nodeType === wanted.nodeType &&
  (held.nodeType !== Node.ELEMENT_NODE ||
    (held.localName === wanted.localName && !(held.id && wanted.id)));

// The ordering pass of `setChildren`, walking past what the runtime put here. A node
// already standing in its place is left alone, which is the whole point: the common
// revision moves nothing at all.
function place(parent, nodes, generated) {
  let cursor = parent.firstChild;
  for (const node of nodes) {
    while (cursor && generated(cursor)) cursor = cursor.nextSibling;
    if (node === cursor) cursor = cursor.nextSibling;
    else parent.insertBefore(node, cursor);
  }
}
