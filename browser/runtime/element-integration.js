/* Leaf's side of the protocol a widget has with its host. Every custom element is
   hosted the same way, from outside, whether it is a plain `HTMLElement` or built on
   `LeafElement` (leaf-element.js): it imports nothing to be hosted.

   Leaf hosts each element of a tag declaring `verbs` or `inputs`. While the element
   stands, Leaf sets each bound input on the property its declaration names
   (element-data.js) and then its `state`: its widget's reading (`widgetState`,
   widget-controller.js) where it records under an id the page captured, and an empty
   reading where it only reads data. `state` is `null` from the moment Leaf hosts the
   element until it has set everything the element draws from, which a source nobody
   has read yet (`awaitsData`, data.js) or a revision's replacement whose document is
   not adopted holds back, so an element can tell "nothing yet" from "no host", which
   leaves `state` undefined. Each set runs in the stack that moved the reading, inside
   a claim on the element's render region, so the page reads as presented only once the
   setter has returned and the `updateComplete` the element then holds, if it has one,
   has settled. An element that holds the page's data version holds it until that draw.
   Where one publication moves several readings, their `state`s are set in the page's
   rendered order, a parent before what it holds, whichever module was defined first: a
   parent's draw may move a member to where that member's own draw then finds it.

   An element is hosted when it says `lf-connect` (widget-upgrade.js, `CONNECT`),
   before that event returns, or else once Leaf sees it arrive and its module has
   defined it. On `lf-connect` Leaf also dresses the element's open shadow root
   (shadow-stage.js), whatever its tag declares.

   Drawing that outlasts a setter is a `pending-task` event, recording is an
   `lf-action` event, and a gesture that rewrites the element's nodes is an `lf-hold`
   event (widget-controller.js). */
import { effect, signal, untracked } from "/runtime/framework.js";
import {
  attachApplicationPresentation,
  attachWidgetPresentation,
} from "./semantic-state.js";
import { widgetDescriptor } from "./widget-descriptors.js";
import { widgetController, widgetMounted, widgetState } from "./widget-controller.js";
import { ElementData } from "./element-data.js";
import { registry, tagsDeclaring } from "./registry.js";
import { watchArrivals, watchOwner } from "./arrivals.js";
import { CONNECT, failSoftUnreported, reportFailure } from "./widget-upgrade.js";
import { adoptShadowStage } from "./shadow-stage.js";
import { byRenderedOrder } from "./shadow-tree.js";
import { tick } from "./version-signal.js";

let regions = 0;
const EMPTY = Object.freeze({});

// The `state`s a publication owes, each by its element. Every reading's own effect
// claims its region and adds to them as the publication notifies it; writing `owed`
// there queues the one effect below behind all of those, still inside the publication.
/** @type {Map<Element, () => void>} */
const owing = new Map();
const owed = signal(0);
effect(() => {
  owed.value;
  if (!owing.size) return;
  const sets = byRenderedOrder([...owing], ([element]) => element);
  owing.clear();
  untracked(() => {
    for (const [, set] of sets) set();
  });
});

/** @type {WeakSet<Element>} */
const hosted = new WeakSet();
/** @param {Element} element */
function host(element) {
  if (hosted.has(element)) return;
  hosted.add(element);
  const descriptor = widgetDescriptor(element);
  const verbs = Object.keys(descriptor?.declaration.verbs ?? {});
  const controller = verbs.length ? widgetController(element) : null;
  const reads = Boolean(registry[element.localName]?.inputs);
  const name = descriptor
    ? `widget:${descriptor.id}:render`
    : `element:${element.localName}:${++regions}`;
  /** @type {import("./framework/presentation.js").PresentationHandle | null} */
  let region = null;
  /** @type {import("./framework/presentation.js").PresentationTicket | null} */
  let ticket = null;
  // What `state` holds: undefined before the first set, null while more is owed, else
  // the reading it was made from.
  /** @type {object | null | undefined} */
  let shown;
  const claim = () => {
    ticket ??= region?.present((reason) => failSoftUnreported(element, reason)) ?? null;
  };
  // A source's accepted reading claims the region, and its delivery draws.
  const data = new ElementData(element, claim);
  // The first set is made as the element connects, so its `setup()` reads it; each
  // later one waits its turn among the readings its publication moved.
  let first = true;
  const draw = () => {
    claim();
    const drawing = ticket;
    ticket = null;
    /** @param {(() => void) | null} [write] */
    const settle = (write) => {
      try {
        if (write) untracked(write);
        // A setter that schedules its draw, as a Lit property does, says when it is in.
        drawing?.resolve(
          /** @type {{updateComplete?: unknown}} */ (element).updateComplete,
        );
      } catch (error) {
        reportFailure(element, error);
        drawing?.reject(error);
      }
    };
    /** @type {(() => void) | null} */
    let write = null;
    try {
      const delivered = !data.awaitsDelivery();
      if (delivered) data.deliver();
      const reading = controller?.read();
      // A revision's replacement lacks its verbs until its document is adopted.
      const whole = !reading || verbs.every((verb) => verb in reading.state);
      const next =
        !delivered || !whole ? null : (reading ?? (reads ? EMPTY : undefined));
      if (next !== undefined && next !== shown) {
        shown = next;
        const state = reading && next === reading ? widgetState(reading) : next && {};
        write = () => Object.assign(element, { state });
      }
    } catch (error) {
      reportFailure(element, error);
      drawing?.reject(error);
      return;
    }
    if (first || !write) {
      first = false;
      return settle(write);
    }
    owing.set(element, () => settle(write));
    tick(owed);
  };
  /** @type {Array<(() => unknown) | null>} */
  let leaving = [];
  try {
    untracked(() => data.initialize());
  } catch (error) {
    reportFailure(element, error);
  }
  watchOwner(element, {
    connect() {
      region = descriptor
        ? attachWidgetPresentation(descriptor.id, "render")
        : attachApplicationPresentation(name);
      leaving = [effect(draw), data.connect(name), () => region?.disconnect()];
      if (descriptor) widgetMounted();
    },
    // The element keeps what was set on it while away, so a return sets `state` again
    // only where its reading has moved.
    disconnect() {
      for (const leave of leaving) leave?.();
      region = ticket = null;
    },
  });
}

/** @param {Element} element */
const declares = (element) => {
  const entry = registry[element.localName];
  return Boolean(entry?.verbs || entry?.inputs);
};

// An element that asks is hosted before its `lf-connect` returns, so its `setup()` and
// first draw read what Leaf set. Its open shadow root is dressed whatever it declares.
/** @type {WeakSet<ShadowRoot>} */
const dressed = new WeakSet();
document.addEventListener(CONNECT, (event) => {
  const element = event.composedPath()[0];
  if (!(element instanceof Element)) return;
  untracked(() => {
    const root = element.shadowRoot;
    if (root && !dressed.has(root)) {
      dressed.add(root);
      adoptShadowStage(root);
    }
    if (declares(element)) host(element);
  });
});

// Each other element of a tag declaring `verbs` or `inputs`, once its module has
// defined it.
/** @type {WeakSet<Element>} */
const met = new WeakSet();
export function hostDeclaredElements() {
  const tags = tagsDeclaring((entry) => Boolean(entry.verbs || entry.inputs));
  if (!tags.length) return;
  watchArrivals(tags.join(","), [], {
    arrive(element) {
      if (met.has(element)) return;
      met.add(element);
      // A tag no module defines keeps no element alive waiting for one.
      const waiting = new WeakRef(element);
      void customElements.whenDefined(element.localName).then(() => {
        const defined = waiting.deref();
        if (defined) host(defined);
      });
    },
    leave() {},
  });
}
