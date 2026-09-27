/* Elements of one kind, held while they stand in the page.

   Some of the runtime's paint belongs to an element for as long as it stands, whoever
   put it there: an external link's mark and the bounded block that is a reading region.
   What produces those elements is open-ended (the served document, a revision patched
   in, a thread's message, any widget's render), so no list of producers can call each
   owner. `watchArrivals` watches for them instead, by a selector and the attributes that
   decide or change what the element needs: `arrive(el)` runs for each one standing now,
   each one added since, and each one whose watched attribute changes while it stands;
   `leave(el)` runs for one that has arrived and no longer stands or matches. `arrive`
   may run again for an element already standing, so it is idempotent.

   Standing means in `document.body`, or in a declared shadow root while its host is
   connected. No observer crosses a shadow boundary on its own, so shadow-stage.js, the
   one door an x-shadow root is built through, enrolls each root it fills
   (`watchArrivalsIn`), and every watch, earlier or later, reads it.

   Mutation records describe intermediate moves: an element removed and added back in
   one batch has not left, so leaving is decided once the batch is read, from where the
   element stands then. */
const watches = new Set();
// The enrolled shadow roots, held weakly: a root outlives its widget only as garbage.
const enrolled = new WeakSet();
const shadowRoots = new Set();
const liveRoots = () => {
  const live = [document.body];
  for (const ref of shadowRoots) {
    const root = ref.deref();
    if (root) live.push(root);
    else shadowRoots.delete(ref);
  }
  return live;
};

const stands = (el) => {
  const root = el.getRootNode();
  return root === document
    ? document.body.contains(el)
    : root instanceof ShadowRoot && root.host.isConnected && enrolled.has(root);
};

function* matching(node, selector) {
  if (node.nodeType !== Node.ELEMENT_NODE) return;
  if (node.matches(selector)) yield node;
  yield* node.querySelectorAll(selector);
}

export function watchArrivals(selector, attributes, { arrive, leave }) {
  const arrived = new WeakSet();
  const offer = (el) => {
    if (stands(el) && el.matches(selector)) {
      arrived.add(el);
      arrive(el);
    } else if (arrived.delete(el)) leave(el);
  };
  const observer = new MutationObserver((records) => {
    const offered = new Set();
    for (const record of records) {
      // An element whose own children change is offered again: a link's mark is one.
      offered.add(record.target);
      for (const node of record.addedNodes)
        for (const el of matching(node, selector)) offered.add(el);
      for (const node of record.removedNodes)
        for (const el of matching(node, selector)) if (arrived.has(el)) offered.add(el);
    }
    for (const el of offered)
      if (
        el.nodeType === Node.ELEMENT_NODE &&
        (arrived.has(el) || el.matches(selector))
      )
        offer(el);
  });
  const watch = { selector, attributes, observer, offer };
  watches.add(watch);
  for (const root of liveRoots()) enroll(watch, root);
}

function enroll({ selector, attributes, observer, offer }, root) {
  observer.observe(root, {
    childList: true,
    subtree: true,
    attributes: true,
    attributeFilter: attributes,
  });
  for (const el of root.querySelectorAll(selector)) offer(el);
}

export function watchArrivalsIn(root) {
  if (enrolled.has(root)) return;
  enrolled.add(root);
  shadowRoots.add(new WeakRef(root));
  for (const watch of watches) enroll(watch, root);
}
