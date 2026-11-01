/* Retained DOM child reconciliation. */
import { diffArrays } from "/vendor/jsdiff.esm.js";
import { move } from "./dom-move.js";

/** Source/live correspondence retains the native kind established by capture and matching.
 * @extends {WeakMap<Node, Node>} */
export class SourcePairs extends WeakMap {
  constructor() {
    super();
  }
  /** @overload @param {Element} source @returns {Element | undefined} */
  /** @overload @param {CharacterData} source @returns {CharacterData | undefined} */
  /** @overload @param {Node} source @returns {Node | undefined} */
  /** @param {Node} source */
  get(source) {
    return super.get(source);
  }

  /** @overload @param {Element} source @param {Element} live @returns {this} */
  /** @overload @param {CharacterData} source @param {CharacterData} live @returns {this} */
  /** @param {Node} source @param {Node} live */
  set(source, live) {
    return super.set(source, live);
  }

  /** @overload @param {Element} source @returns {Element} */
  /** @overload @param {CharacterData} source @returns {CharacterData} */
  /** @overload @param {Node} source @returns {Node} */
  /** @param {Node} source */
  require(source) {
    const live = this.get(source);
    if (!live) throw new Error("The authored source has no paired native node");
    return live;
  }

  /** Pair native nodes at the source-capture boundary.
   * @param {Node} source @param {Node} live */
  pair(source, live) {
    if (source instanceof Element && live instanceof Element)
      return this.set(source, live);
    if (
      source instanceof CharacterData &&
      live instanceof CharacterData &&
      source.nodeType === live.nodeType
    )
      return this.set(source, live);
    throw new Error(
      "An authored source and its live node must have the same native kind",
    );
  }
}

// Make `parent`'s children `nodes`, in order, without moving a node already in place.
/** @param {Node & ParentNode} parent @param {Iterable<Node>} nodes */
export function setChildren(parent, nodes) {
  setChildLists([[parent, nodes]]);
}

// `setChildren` for several `[parent, nodes]` lists at once, where a node can change
// lists: it moves straight from the parent it leaves to the one it joins, keeping the
// user in it, where one list at a time would remove it before the next placed
// it. Ordering walks past a stale node, so no survivor moves for it; once every list is
// placed, what still stands in a list's parent is a node no list holds, and is removed.
// Lists are placed in the order given, so name a parent before any list inside it: a
// node then moves into a parent that is already connected.
/** @param {readonly (readonly [Node & ParentNode, Iterable<Node>])[]} lists */
export function setChildLists(lists) {
  for (const [parent, nodes] of lists) orderChildren(parent, nodes);
  for (const [parent, nodes] of lists) {
    const keep = new Set(nodes);
    for (const child of [...parent.childNodes]) if (!keep.has(child)) child.remove();
  }
}

// Order this renderer's children without taking ownership of their siblings.
/** @param {Node & ParentNode} parent @param {Iterable<Node>} nodes */
export function orderChildren(parent, nodes) {
  const owned = new Set(nodes);
  order(parent, nodes, (node) => !owned.has(node));
}

// Replace a renderer-owned subtree using the same matching and text edits as an
// authored revision. The caller owns every descendant's attributes and contents;
// controls with independent state belong outside it. Current nodes pair to themselves,
// so unchanged text and native Ranges stay in place without a source mirror.
/** @param {Node & ParentNode} parent @param {Iterable<Node>} nodes */
export function setRenderedChildren(parent, nodes) {
  const after = document.createDocumentFragment();
  after.append(...nodes);
  patchChildren(parent, parent, after, {
    pairs: selfPairs(parent),
    arrive: (node) => node,
    sameValue: (held, wanted) => held === wanted,
    touched: () => {},
    declared: () => false,
    body: () => null,
    same: (held, wanted) => held.isEqualNode(wanted),
    generated: () => false,
    contains: (target, owner) => Boolean(owner?.contains(target)),
    reaches: () => false,
  });
}

/** @param {Node} parent */
function selfPairs(parent) {
  const pairs = new SourcePairs();
  for (const node of sourceNodes(parent)) pairs.pair(node, node);
  return pairs;
}

// Put `nodes` in order under `parent`, walking past the children `passed` names, and
// moving only a node that is not already where it belongs. A retained move within one
// shadow-including tree preserves native state where the browser supports it (`move`),
// but the browser still lays the node out afresh, and Firefox then anchors scrolling on
// whatever ends the viewport. So the nodes that stay are the most that can, elements
// before text (`staying`): a revision that drops a section moves the whitespace that
// stood after it, not each section below.
/** @param {Node & ParentNode} parent @param {Iterable<Node>} nodes @param {(node: Node) => boolean} [passed] */
function order(parent, nodes, passed = () => false) {
  const list = [...nodes];
  const stay = staying(parent, list);
  let cursor = parent.firstChild;
  for (const node of list) {
    while (cursor && passed(cursor)) cursor = cursor.nextSibling;
    if (node === cursor) cursor = cursor.nextSibling;
    // Whatever stands between is moved after it, where it belongs.
    else if (stay.has(node)) cursor = node.nextSibling;
    else move(parent, node, cursor);
  }
}

// The heaviest run of `nodes` already in order under `parent`: an increasing subsequence
// of their places, where an element outweighs every text node together. Of runs that
// weigh the same it keeps the later nodes, so a swap moves the earlier of the two, as a
// cursor walk does. A Fenwick tree holds the heaviest run ending at or before each place,
// so a long list costs n log n.
/** @typedef {{node: Node, weight: number, previous: Chain | null}} Chain */
/** @param {Node} parent @param {readonly Node[]} nodes */
function staying(parent, nodes) {
  /** @type {Map<Node, number>} */
  const places = new Map([...parent.childNodes].map((node, at) => [node, at + 1]));
  const size = places.size;
  /** @type {(Chain | undefined)[]} */
  const best = new Array(size + 1);
  /** @type {Chain | null} */
  let last = null;
  for (const node of nodes) {
    const place = places.get(node);
    if (!place) continue;
    /** @type {Chain | null} */
    let before = null;
    for (let i = place - 1; i > 0; i -= i & -i) {
      const candidate = best[i];
      if (candidate && (!before || candidate.weight >= before.weight))
        before = candidate;
    }
    const weight =
      (node.nodeType === Node.ELEMENT_NODE ? nodes.length + 1 : 1) +
      (before?.weight ?? 0);
    /** @type {Chain} */
    const chain = { node, weight, previous: before };
    for (let i = place; i <= size; i += i & -i) {
      const held = best[i];
      if (!held || weight >= held.weight) best[i] = chain;
    }
    if (!last || weight >= last.weight) last = chain;
  }
  const stay = new Set();
  for (let chain = last; chain; chain = chain.previous) stay.add(chain.node);
  return stay;
}

/* Apply the difference between two authored revisions to the live page between them.

   `setChildren` answers for a list its caller already holds. This answers a question the
   live tree cannot be asked at all: what did the author change. Diffing the page against
   the arriving source would answer a different one — what is different about the page —
   and everything the browser, the runtime, a user, or a page module has done to that
   page since it loaded is different about it. A user's open `<details>` closes, a
   tokenizer's spans are torn out of a code block nobody edited, a tab stop the runtime
   lent to put focus somewhere is taken back, and what a page module built inside an
   authored container is swept out as markup the source does not have.

   So both sides of the diff are source. `before` and `after` are the two revisions'
   authored body, inert and untouched by anything: whatever they agree on, this does not
   touch. `pairs` carries the correspondence, from a source node to the live node standing
   for it — built by a lockstep walk at boot, when the page is still exactly its own
   source, and kept up by every patch since.

   The live tree is therefore written only where the author wrote: a text node's differing
   run, an attribute whose value the two sources disagree on, an element one of them has
   and the other has not. A user keeps everything else, including the things this had no
   way to recognize as theirs.

   What the caller answers, since this module knows no registry, namespace or document:

   - `pairs`: the source-to-live map, read and written here as the patch proceeds.
   - `arrive(node, parent)`: bring this source node into the document — import it, pair
     the whole subtree, and read whatever has to be read off a widget's markup before a
     controller owns its children, with `parent` as the live element it will stand under,
     since a reading about its place in the document is made before it has one. Returns
     the live node to place.
   - `sameValue(before, after)`: two revisions spell this attribute the same way.
     A resource address is written per revision, so it is read past that root.
   - `touched(element)`: this live element's attributes changed, and whatever a dressing
     pass reads off its attributes is owed again.
   - `declared(element)`: an upgraded widget, whose children are its controller's. Asked
     of the held element; a match names the same element on both sides.
   - `body(element)`: the box a widget's module built to hold every authored child of
     this live element, or null. The source's children are that box's, so the patch
     writes, places and orders them there.
   - `reaches(before, after)`: this widget's controller leaves its members where the
     author wrote them, and the two revisions differ only inside those members. What
     changed is then authored markup the patch can write, and nothing the controller
     built from the widget is stale.
   - `same(before, after)`: two source elements are spelled the same way, read past the
     address each revision was delivered at. Asked of an element whose interior a pass
     other than a controller has taken, or a widget owns.
   - `generated(node)`: the live node is the runtime's own. Only placement asks, because
     only placement walks live children; nothing here matches or removes on it.

   Matching runs in three passes, narrowest first, and each pass only sees what the one
   before it left. An id is a name the author gave, so it wins outright. Then the siblings
   that did not change at all are pinned by an exact signature — node type, tag, and the
   words under it — through `diffArrays`, so a list of paragraphs stays still when one is
   inserted among them. Only the gaps between those pins are diffed again, by kind alone,
   which is what pairs a paragraph with its own rewrite. */
/** @typedef {{pairs: SourcePairs, contains: (target: Node, owner: Node | null | undefined) => boolean,
 * declared: (element: Element) => boolean, body: (element: Element) => Element | null,
 * reaches: (before: Element, after: Element) => boolean,
 * same: (before: Element, after: Element) => boolean, sameValue: (before: string, after: string) => boolean}} RetentionRules */
/** @typedef {RetentionRules & {arrive: (node: Node, parent: Node) => Node,
 * touched: (element: Element) => void, generated: (node: Node) => boolean}} PatchRules */
/** @param {Element} before @param {Element} after @param {PatchRules} rules */
export function patchTree(before, after, rules) {
  const live = rules.pairs.require(before);
  patchAttributes(live, before, after, rules);
  patchChildren(holder(live, rules), tree(before), tree(after), rules);
}

// Whether the authored patch preserves this native node. An owned target needs its
// complete authored subtree and every containing owner kept; runtime chrome remains
// with its own renderer. Use the patch's matching and ownership rules for both readings.
// `contains(node, owner)` reads containment in the caller’s rendered tree. This is a
// reading only; the commit rechecks it against the current source/live pairs.
/** @param {Element} before @param {Element} after @param {Node | null | undefined} target @param {RetentionRules} rules */
export function patchRetains(before, after, target, rules) {
  if (!target?.isConnected) return false;
  // Runtime chrome is outside the authored patch. Ask source pairs, not DOM place:
  // eviction also removes authored nodes a page module moved outside its original parent.
  if (!sourceOwns(before, target, rules)) return true;
  return retainedWithin(before, after, target, rules);
}

/** @param {Node} source @param {Node} target @param {RetentionRules} rules */
function sourceOwns(source, target, rules) {
  const owns = (/** @type {Node} */ node) =>
    rules.contains(target, rules.pairs.get(node));
  if (owns(source)) return true;
  for (const node of sourceNodes(source)) if (owns(node)) return true;
  return false;
}

/** @param {Element} before @param {Element} after @param {Node} target @param {RetentionRules} rules @returns {boolean} */
function retainedWithin(before, after, target, rules) {
  const live = rules.pairs.get(before);
  if (!live || !sourceOwns(before, target, rules)) return false;
  // An unchanged source also preserves editors its renderer added underneath it.
  if (rules.same(before, after)) return true;
  if (live === target) return false;
  // A containing identity is part of the durable anchor even when the rendered
  // subject is an anonymous paragraph. Keep its attributes as well as its node.
  if (
    before.attributes.length !== after.attributes.length ||
    [...before.attributes].some(({ name, value }) => {
      const attribute = after.getAttributeNode(name);
      return !attribute || !rules.sameValue(value, attribute.value);
    })
  )
    return false;
  const children = [...tree(before).childNodes];
  const arriving = [...tree(after).childNodes];
  const forward = matchNodes(children, arriving);
  const matches = new SourcePairs();
  for (const wanted of arriving) {
    const held = forward.get(wanted);
    if (held) matches.pair(held, wanted);
  }
  for (const held of children) {
    if (!(held instanceof Element)) continue;
    const node = rules.pairs.get(held);
    if (!node || !sourceOwns(held, target, rules)) continue;
    const wanted = matches.get(held);
    if (!wanted) return false;
    // Like patchTree, the root is traversed; atomic ownership is decided for each
    // child by patchChildren, which either keeps that complete subtree or rebuilds it.
    const retains = atomic(held, wanted, node, rules)
      ? rules.same(held, wanted)
      : retainedWithin(held, wanted, target, rules);
    if (!retains) return false;
  }
  // A moved editor can have a logical source owner and a different physical one.
  // Every such path must survive, including an owned child absent from the new source.
  // With no authored child owning it, the target is generated content the patch keeps.
  return true;
}

// A template's tree is its content fragment, not its children; `childNodes` is empty
// however much markup it holds.
/** @template {Node} T @param {T} node @returns {T | DocumentFragment} */
const tree = (node) => (node instanceof HTMLTemplateElement ? node.content : node);
// Where a live element's authored children stand: its tree, or the authored body its
// widget's module moved them into.
/** @param {Element} live @param {RetentionRules} rules */
const holder = (live, rules) => rules.body(live) ?? tree(live);

// Only where the two revisions disagree. An attribute they both carry is left exactly as
// the page has it, which is the whole of how a user's `<details open>`, a tab stop
// `focus.js` lent to land them somewhere, and anything a page module wrote survive a
// revision that never mentioned them.
/** @param {Element} live @param {Element} before @param {Element} after @param {PatchRules} rules */
function patchAttributes(live, before, after, rules) {
  let changed = false;
  for (const { name, value } of [...before.attributes]) {
    if (after.hasAttribute(name)) continue;
    if (name === "class") live.classList.remove(...tokens(value));
    else if (name === "style") restyle(live, value, "");
    else live.removeAttribute(name);
    changed = true;
  }
  for (const { name, value } of after.attributes) {
    const held = before.getAttribute(name);
    if (held !== null && rules.sameValue(held, value)) continue;
    // Classes and inline declarations are sets the page shares with the runtime, so
    // only the author's own members move; every mark, state class and property the
    // runtime wrote beside them stays.
    if (name === "class") {
      live.classList.remove(...tokens(held ?? ""));
      live.classList.add(...tokens(value));
    } else if (name === "style") restyle(live, held ?? "", value);
    else live.setAttribute(name, value);
    changed = true;
  }
  if (changed) rules.touched(live);
}

// The runtime and page scripts write properties of their own inline on authored
// elements, `body`'s included (composing/aim.js, content-layout.js), so a revision
// writes the author's new text and, after it, whatever the live element holds that
// neither the old text nor the new one declares, in one write. The carried part goes as
// serialized text: a shorthand written with `var()` reads back empty longhand by
// longhand, so moving declarations by name drops it.
/** @param {Element} live @param {string} held @param {string} next */
function restyle(live, held, next) {
  const parse = (/** @type {string} */ text) => {
    const parsed = document.createElement("div").style;
    parsed.cssText = text;
    return parsed;
  };
  const names = (/** @type {CSSStyleDeclaration} */ declared) =>
    Array.from({ length: declared.length }, (_, at) => declared.item(at));
  const carried = parse(live.getAttribute("style") ?? "");
  for (const property of [...names(parse(held)), ...names(parse(next))])
    carried.removeProperty(property);
  const text = [next.trim().replace(/;\s*$/, ""), carried.cssText]
    .filter(Boolean)
    .join("; ");
  if (text) live.setAttribute("style", text);
  else live.removeAttribute("style");
}

// Source text, so any run of whitespace separates two classes.
/** @param {string} value */
const tokens = (value) => value.split(/\s+/).filter(Boolean);

// Only the run of words that actually changed. Assigning `data` replaces the node's
// whole content, and the platform's replace-data step collapses every Range endpoint
// inside what it replaced — which is the user's own selection, in exactly the
// paragraph a revision rewrote while they were reading it. Trimming to the differing
// middle leaves every offset on either side of it where it was, so a selection over
// words the revision kept survives the words beside it changing.
/** @param {CharacterData} node @param {string} next */
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

// Everything one source element stood for leaves with it: the live element, and any
// node paired under it that a page module had since moved elsewhere in the document.
// Removing the element alone would leave that node standing for a source that is gone,
// and its rebuilt replacement would then stand beside it under the same name.
/** @param {Node} before @param {Node} live @param {PatchRules} rules */
function evict(before, live, rules) {
  live.parentNode?.removeChild(live);
  for (const inner of sourceNodes(before)) {
    const stray = rules.pairs.get(inner);
    // Still in some tree, and not the one that just left with the element. Asked of
    // the parent rather than the document, because a template's content is a fragment
    // nothing is ever connected to.
    if (!stray?.parentNode || live.contains(stray)) continue;
    stray.parentNode.removeChild(stray);
  }
}

/** @param {Node} node @returns {Generator<ChildNode>} */
function* sourceNodes(node) {
  for (const child of tree(node).childNodes) {
    yield child;
    yield* sourceNodes(child);
  }
}

/** @param {Node & ParentNode} liveParent @param {Node} beforeParent @param {Node} afterParent @param {PatchRules} rules */
function patchChildren(liveParent, beforeParent, afterParent, rules) {
  const held = [...beforeParent.childNodes];
  const wanted = [...afterParent.childNodes];
  const matches = matchNodes(held, wanted);
  const matched = new Set(wanted.map((node) => matches.get(node)));
  for (const node of held) {
    if (!matched.has(node)) evict(node, rules.pairs.require(node), rules);
  }
  const placed = [];
  for (const node of wanted) {
    const pair = patchPair(node, matches, rules.pairs);
    // A new source, or one whose live counterpart has left every tree, arrives afresh.
    // A node a page module moved elsewhere keeps that native owner and its place.
    if (!pair || !pair.live.parentNode) {
      placed.push(rules.arrive(node, liveParent));
      continue;
    }
    const { live } = pair;
    if (pair.kind === "data") {
      writeText(pair.live, pair.after.data);
      rules.pairs.set(pair.after, pair.live);
    } else {
      const { before, after } = pair;
      if (!atomic(before, after, pair.live, rules)) patchTree(before, after, rules);
      else if (!rules.same(before, after)) {
        evict(before, pair.live, rules);
        placed.push(rules.arrive(after, liveParent));
        continue;
      } else pairInterior(before, after, rules);
      rules.pairs.set(after, pair.live);
    }
    if (live.parentNode === liveParent) placed.push(live);
  }
  // Walk past runtime-owned siblings and move only the authored nodes that changed order.
  order(liveParent, placed, rules.generated);
}

/** @typedef {{kind: "element", before: Element, after: Element, live: Element} |
 * {kind: "data", before: CharacterData, after: CharacterData, live: CharacterData}} PatchPair */
/** @param {Node} after @param {SourcePairs} matches @param {SourcePairs} pairs @returns {PatchPair | null} */
function patchPair(after, matches, pairs) {
  if (after instanceof Element) {
    const before = matches.get(after);
    const live = before && pairs.get(before);
    return before && live ? { kind: "element", before, after, live } : null;
  }
  if (after instanceof CharacterData) {
    const before = matches.get(after);
    const live = before && pairs.get(before);
    return before && live ? { kind: "data", before, after, live } : null;
  }
  throw new Error("Authored child nodes must be elements or character data");
}

// A kept element's interior is the same markup in both revisions, so each of its source
// nodes stands for whatever live node the one it replaces stood for, wherever the
// controller holds it now. A digest that matched over markup of another shape pairs
// nothing rather than pair the wrong nodes.
/** @param {Element} before @param {Element} after @param {PatchRules} rules */
function pairInterior(before, after, rules) {
  const held = [...sourceNodes(before)];
  const wanted = [...sourceNodes(after)];
  if (held.length !== wanted.length) return;
  const originals = held[Symbol.iterator]();
  for (const node of wanted) {
    const original = originals.next().value;
    if (!original)
      throw new Error("An unchanged source must retain its complete node sequence");
    const live = rules.pairs.get(original);
    if (live) rules.pairs.pair(node, live);
  }
}

// Whether this element's interior is beyond the patch. A widget's is its controller's
// from the moment it upgrades, and the caller names those. Any element's can also be
// taken by a pass with a reason to own it: the tokenizer's spans stand where a code
// block's one authored text node stood, and the nodes this patch paired are then not
// there to write through — putting one back would stand the source's own text beside
// the colouring of it. Both are read the same way afterwards: whole, or not at all.
// A widget whose controller only builds beside its members, or around the authored
// body holding them, is neither, for a revision that leaves everything but their
// interiors alone: a page written as tabs keeps every tab the author did not touch,
// rather than rebuilding the page for one sentence.
// A stylesheet's parsed rules belong to CSSOM. Replacing a changed source owner
// reparses its original text, including when only its access declaration changed.
/** @param {Element} before @param {Element} after @param {Element} live @param {RetentionRules} rules */
const atomic = (before, after, live, rules) =>
  before.matches('style, link[rel~="stylesheet" i]') ||
  (rules.declared(before) && !rules.reaches(before, after)) ||
  [...tree(before).childNodes].some(
    (node) => rules.pairs.get(node)?.parentNode !== holder(live, rules),
  );

/** @param {readonly Node[]} held @param {readonly Node[]} wanted */
function matchNodes(held, wanted) {
  const matches = new SourcePairs();
  /** @type {Set<Node>} */
  const matched = new Set();
  /** @type {Map<string, Element>} */
  const byId = new Map();
  for (const node of held)
    if (node instanceof Element && node.id && !byId.has(node.id))
      byId.set(node.id, node);
  for (const node of wanted) {
    if (!(node instanceof Element) || !node.id) continue;
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

/** jsdiff's unchanged runs pair these two source positions.
 * @param {readonly Node[]} nodes @param {number} index */
function diffNode(nodes, index) {
  const node = nodes[index];
  if (!node) throw new Error("A child diff named a source position outside its input");
  return node;
}

const COLLAPSE = /\s+/g;

// Exact enough that two of them being equal means the revision left this sibling alone,
// and loose enough that reindenting the source does not unpin the whole list. Both sides
// are authored markup, so every word under the node is the author's to compare.
/** @param {Node} node */
const signature = (node) => {
  if (node instanceof CharacterData) return `${node.nodeType}:${node.data}`;
  if (!(node instanceof Element))
    throw new Error("Authored child nodes must be elements or character data");
  const words = tree(node).textContent ?? "";
  return `1:${node.localName}#${node.id}:${words.replace(COLLAPSE, " ").trim()}`;
};

/** @param {readonly Node[]} held @param {readonly Node[]} wanted @param {SourcePairs} matches */
function alignRest(held, wanted, matches) {
  let heldAt = 0;
  let wantedAt = 0;
  /** @type {Node[]} */
  let gapHeld = [];
  /** @type {Node[]} */
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
        matches.pair(diffNode(wanted, wantedAt + at), diffNode(held, heldAt + at));
      heldAt += count;
      wantedAt += count;
    }
  }
  closeGap();
}

// Inside one edited stretch: these are the siblings the revision rewrote, and a rewrite
// is still the element it rewrote. Diffed rather than walked in step, because a stretch
// holds insertions too and a cursor meets them in the two ways that cost a user their
// node. A sibling of another kind above the one they are reading — a heading, a list, an
// unnamed widget — is nothing the cursor can pair, so it spends the cursor and the
// user's own paragraph is left with no partner and removed. A sibling of the same kind
// above it takes the pairing that belonged to the paragraph below.
//
// Compared rather than keyed, because what may pair here is not an equality. Two elements
// the source names differently are never each other; an element named on one side only is
// that name being given or taken away, which is a thing to do to an element. A key can
// state the first or the second and not both — `p#a` would have to equal `p` while `p#a`
// differs from `p#b` — so the rule travels as the comparator it is.
/** @param {Node[]} held @param {Node[]} wanted @param {SourcePairs} matches */
function pairInGap(held, wanted, matches) {
  let heldAt = 0;
  let wantedAt = 0;
  for (const run of diffArrays(held, wanted, { comparator: interchangeable })) {
    const count = run.value.length;
    if (run.added) wantedAt += count;
    else if (run.removed) heldAt += count;
    else {
      for (let at = 0; at < count; at++)
        matches.pair(diffNode(wanted, wantedAt + at), diffNode(held, heldAt + at));
      heldAt += count;
      wantedAt += count;
    }
  }
}

/** @param {Node} held @param {Node} wanted */
const interchangeable = (held, wanted) =>
  held.nodeType === wanted.nodeType &&
  (!(held instanceof Element) ||
    (wanted instanceof Element &&
      held.localName === wanted.localName &&
      !(held.id && wanted.id)));
