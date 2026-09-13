/* Retained DOM child reconciliation. */

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

   Matching is by id first and by position second, and a positional match needs the same
   node type, the same tag, and no id on either side: an element the source names is that
   element or is new, never whichever unnamed element stands in its place. */
export function patchTree(live, source, rules) {
  patchAttributes(live, source, rules.share);
  patchChildren(live, source, rules);
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

function patchChildren(live, source, rules) {
  const held = [...live.childNodes].filter((node) => !rules.generated(node));
  const wanted = [...source.childNodes];
  const matches = matchNodes(held, wanted);
  const matched = new Set(matches.values());
  for (const node of held) if (!matched.has(node)) node.remove();
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
      match.remove();
      rules.adopt(node);
      placed.push(node);
    }
  }
  place(live, placed, rules.generated);
}

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
  const rest = held.filter((node) => !matched.has(node));
  let cursor = 0;
  for (const node of wanted) {
    if (matches.has(node)) continue;
    while (cursor < rest.length && !interchangeable(rest[cursor], node)) cursor += 1;
    if (cursor >= rest.length) break;
    matches.set(node, rest[cursor]);
    cursor += 1;
  }
  return matches;
}

const interchangeable = (held, wanted) =>
  held.nodeType === wanted.nodeType &&
  (held.nodeType !== Node.ELEMENT_NODE ||
    (held.localName === wanted.localName && !held.id && !wanted.id));

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
