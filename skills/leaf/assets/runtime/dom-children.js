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

/* Reconcile a live tree onto the source of another written independently of it.

   `setChildren` answers for a list its caller already holds. This answers the other
   shape of the same question, where the live side holds a reader: a caret in one
   paragraph, a selection across two, a pointer parked on a mark, focus on a control,
   an armed key sequence over the ids in front of them. All of that belongs to nodes
   rather than to markup, so it survives exactly as far as the nodes do — which is why
   this matches and mutates rather than replacing. Writing a text node's `data` moves
   the Ranges inside it with the words; an element nothing detaches never drops focus.

   Every judgement that is not the DOM's own is the caller's, since this module knows
   no registry, namespace or document:

   - `generated(node)`: the live node is the runtime's rather than the page's. It is
     never matched, never removed, and stays where it stands, because the source
     document the page is being patched onto has nothing to say about it.
   - `declared(element)`: an upgraded widget, whose children a controller owns. It is
     atomic: this either keeps the whole element or swaps the whole element.
   - `unchanged(element)`: that atomic element's authored source is the source it was
     built from, so keeping it keeps something true. The caller compares the two source
     documents, which is the only place either element's authored markup still exists.
   - `share(element)`: the attributes of this element that belong to the page. What the
     runtime writes onto an authored element is not the revision's to retire.
   - `adopt(element)`: read this source element before it joins the live tree. Joining is
     what hands a widget's children to a controller, so whatever has to be read off the
     markup a widget was written as has to be read here. It is called for the nodes that
     arrive and for nothing else, because a node that stays has already been read.
   - `retire(element)`: this live element is leaving the document, with every element
     under it. Said as it happens rather than predicted from the two sources, because
     what goes is decided here: a widget whose own markup nobody touched still leaves
     when the wrapper around it is replaced.

   Matching runs in three passes, narrowest first, and each pass only sees what the one
   before it left.

   An id is a name the author gave, so it wins outright: an element the source names is
   the element of that name, wherever either side has moved it to.

   Then the unnamed siblings, which is where a list of paragraphs lives, and where
   walking the two lists in step is wrong in the one way that costs a reader most. Insert
   a paragraph above the one they are reading and every later paragraph pairs with its
   neighbour: their own text node keeps its identity while its words are overwritten with
   the next paragraph's, and the last paragraph is dropped for want of a partner. So the
   siblings that did not change are found first, by an exact signature — node type, tag,
   and the authored words under it, skipping whatever the runtime put there — and pinned
   through `diffArrays`, which is the same vendored spine the text alignment runs on.
   Those pins are the parts of the list that stand still.

   Only the gaps between pins are then walked in step, by node type and tag alone, which
   is what pairs a paragraph with its own rewrite. An element carrying an id is never
   paired here with one carrying a different id; an id on one side only is that name
   being given or taken away, which is a thing to do to an element rather than a reason
   to replace it. */
export function patchTree(live, source, rules) {
  patchAttributes(live, source, rules.share);
  // A template's tree is its content fragment, not its children; `childNodes` is empty
  // however much markup it holds. The one template an authored page may hold is the
  // gallery's interaction page, and reading the element alone would leave the markup
  // every replay instantiates frozen at the revision it arrived in.
  const [liveTree, sourceTree] =
    live.localName === "template" && source.localName === "template"
      ? [live.content, source.content]
      : [live, source];
  patchChildren(liveTree, sourceTree, rules);
}

function patchAttributes(live, source, share) {
  const held = share(live);
  const wanted = share(source);
  for (const [name, value] of held) {
    if (wanted.has(name)) continue;
    if (name === "class") live.classList.remove(...tokens(value));
    else live.removeAttribute(name);
  }
  for (const [name, value] of wanted) {
    if (name === "class") {
      const priorClasses = held.get(name) ?? "";
      if (priorClasses === value) continue;
      live.classList.remove(...tokens(priorClasses));
      live.classList.add(...tokens(value));
    } else if (live.getAttribute(name) !== value) live.setAttribute(name, value);
  }
}

const tokens = (value) => value.split(" ").filter(Boolean);

// Everything leaving, told to the caller before it goes. The element itself and every
// element under it: a widget inside a replaced wrapper is as gone as the wrapper.
function retire(node, rules) {
  if (node.nodeType !== Node.ELEMENT_NODE) return;
  rules.retire(node);
  for (const inner of node.querySelectorAll("*")) rules.retire(inner);
}

function patchChildren(live, source, rules) {
  const held = [...live.childNodes].filter((node) => !rules.generated(node));
  const wanted = [...source.childNodes];
  const matches = matchNodes(held, wanted, rules);
  const matched = new Set(matches.values());
  for (const node of held)
    if (!matched.has(node)) {
      retire(node, rules);
      node.remove();
    }
  const placed = [];
  for (const node of wanted) {
    const match = matches.get(node);
    if (!match) {
      if (node.nodeType === Node.ELEMENT_NODE) rules.adopt(node);
      placed.push(node);
      continue;
    }
    if (match.nodeType !== Node.ELEMENT_NODE) {
      // The same node, so the browser carries every Range boundary inside it across the
      // edit rather than collapsing a selection the reader is still holding.
      if (match.data !== node.data) match.data = node.data;
      placed.push(match);
    } else if (!rules.declared(match)) {
      patchTree(match, node, rules);
      placed.push(match);
    } else if (rules.unchanged(match)) placed.push(match);
    else {
      // A widget renders from its own authored markup, so a changed one cannot be
      // corrected from outside. It leaves, and its replacement arrives as a new element.
      retire(match, rules);
      match.remove();
      rules.adopt(node);
      placed.push(node);
    }
  }
  place(live, placed, rules.generated);
}

function matchNodes(held, wanted, rules) {
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
    rules,
  );
  return matches;
}

// The words this node puts in front of a reader, as the page's rather than the layer's.
// A declared widget has none to offer by the time this runs — its children belong to a
// controller — so its tag stands for it and the recursion below sorts out the rest.
function authoredText(node, rules) {
  if (rules.generated(node)) return "";
  if (node.nodeType !== Node.ELEMENT_NODE) return node.data ?? "";
  if (rules.declared(node)) return "";
  let text = "";
  const children = node.localName === "template" ? node.content : node;
  for (const child of children.childNodes) text += authoredText(child, rules);
  return text;
}

const COLLAPSE = /\s+/g;

// Exact enough that two of them being equal means the revision left this sibling alone,
// and loose enough that reindenting the source does not unpin the whole list.
const signature = (node, rules) => {
  if (node.nodeType !== Node.ELEMENT_NODE) return `${node.nodeType}:${node.data}`;
  if (node.id) return `1:${node.localName}#${node.id}`;
  return `1:${node.localName}:${authoredText(node, rules).replace(COLLAPSE, " ").trim()}`;
};

function alignRest(held, wanted, matches, rules) {
  let heldAt = 0;
  let wantedAt = 0;
  let gapHeld = [];
  let gapWanted = [];
  const closeGap = () => {
    pairInOrder(gapHeld, gapWanted, matches);
    gapHeld = [];
    gapWanted = [];
  };
  for (const run of diffArrays(
    held.map((node) => signature(node, rules)),
    wanted.map((node) => signature(node, rules)),
  )) {
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

// Inside one edited stretch, where walking in step is the right answer: these are the
// siblings the revision rewrote, and a rewrite is still the element it rewrote.
function pairInOrder(held, wanted, matches) {
  let cursor = 0;
  for (const node of wanted) {
    while (cursor < held.length && !interchangeable(held[cursor], node)) cursor += 1;
    if (cursor >= held.length) break;
    matches.set(node, held[cursor]);
    cursor += 1;
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
