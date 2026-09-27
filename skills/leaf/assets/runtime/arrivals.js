/* Elements of one kind, held while they stand in the page, and the stages they stand in.

   Some of the runtime's paint belongs to an element for as long as it stands, whoever
   put it there: an external link's mark and note, and the bounded block that is a
   reading region. What produces those elements is open-ended (the served document, a
   revision patched in, a thread's message, any widget's render), so no list of
   producers can call each owner. `watchArrivals(selector, attributes, { arrive, leave })`
   watches for them instead:

   - `arrive(el)` runs for each match standing when the watch starts and each one added
     since, however deep in what was added, shadow stages included. It runs again when
     a watched attribute changes, and when the nodes beside the element change: its own
     children, or a sibling added or removed next to it. That is where an owner's paint
     stands (a link's mark inside it, its note after it), so a render that keeps the
     element and drops the paint hands the element back to be painted again. `arrive`
     is therefore idempotent, and cheap for an element whose paint still stands.
   - `leave(el)` runs once for an element that has arrived and no longer stands or
     matches. Mutation records describe intermediate moves: an element removed and added
     back in one batch has not left, so leaving is decided once the batch is read, from
     where the element stands then.

   Standing means in `document.body`, or in a declared shadow stage whose host is
   connected. No observer crosses a shadow boundary on its own, so shadow-stage.js, the
   one door a stage is built through, hands each one it fills to `watchArrivalsIn`. This
   module is the stages' one registry (`liveStages`), held weakly: a stage outlives its
   widget only as garbage. A stage built while its host was detached arrives with the
   host. */
import { under } from "./shadow.js";

const watches = new Set();
const stages = new WeakSet();
const stageRefs = new Set();

export function liveStages() {
  const live = [];
  for (const ref of stageRefs) {
    const root = ref.deref();
    if (root) live.push(root);
    else stageRefs.delete(ref);
  }
  return live;
}

const stands = (el) => {
  const root = el.getRootNode();
  return root === document
    ? document.body.contains(el)
    : root instanceof ShadowRoot && root.host.isConnected && stages.has(root);
};

// Every match in what a record names, the stages inside it included.
function* matching(node, selector) {
  if (node?.nodeType !== Node.ELEMENT_NODE) return;
  if (node.matches(selector)) yield node;
  yield* node.querySelectorAll(selector);
  for (const stage of liveStages())
    if (under(stage.host, node)) yield* stage.querySelectorAll(selector);
}

export function watchArrivals(selector, attributes, { arrive, leave }) {
  const arrived = new WeakSet();
  const offer = (el) => {
    if (stands(el) && el.matches(selector)) {
      arrived.add(el);
      arrive(el);
    } else if (arrived.delete(el)) leave(el);
  };
  const beside = (node) =>
    node?.nodeType === Node.ELEMENT_NODE && node.matches(selector) ? [node] : [];
  const observer = new MutationObserver((records) => {
    const offered = new Set();
    for (const record of records) {
      if (record.type === "attributes") {
        offered.add(record.target);
        continue;
      }
      for (const el of [
        ...beside(record.target),
        ...beside(record.previousSibling),
        ...beside(record.nextSibling),
      ])
        offered.add(el);
      for (const node of record.addedNodes)
        for (const el of matching(node, selector)) offered.add(el);
      for (const node of record.removedNodes)
        for (const el of matching(node, selector)) if (arrived.has(el)) offered.add(el);
    }
    for (const el of offered) offer(el);
  });
  const watch = { selector, attributes, observer, offer };
  watches.add(watch);
  for (const root of [document.body, ...liveStages()]) enroll(watch, root);
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

export function watchArrivalsIn(stage) {
  if (stages.has(stage)) return;
  stages.add(stage);
  stageRefs.add(new WeakRef(stage));
  for (const watch of watches) enroll(watch, stage);
}
