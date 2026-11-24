/* Leaf's host capabilities for the portable element lifecycle. Install before
   widgets connect: page presentation, authored/bound data, widget controllers and
   command dressing belong to the page, while the element owns Lit and its failures.
   A plain host supplies properties and listens to drawn without loading this module.

   A `LeafElement` asks for those capabilities itself (leaf-element.js). Any other
   custom element whose tag declares `verbs` or `inputs` is given them from outside
   (`hostDeclaredElements`), so its module needs none of Leaf's helpers. While such an
   element stands in the document or a declared shadow stage, Leaf sets on it:

   - `state`, where the element is a widget whose tag declares `verbs`: its reading
     (`widgetState`, widget-controller.js), once its class is defined and again each
     time the reading moves, whoever moved it;
   - the property each bound input names, and a written data body as its `value`
     (element-data.js, "Bound values").

   Leaf sets none of them until the reading holds every declared verb and the page has
   read the data a bound source names, so the element never draws a reading nobody has
   made yet. Each pass of sets runs in the stack that moved the reading, inside a claim
   on the element's render region. So a gesture's result is drawn before the
   `dispatchEvent` that recorded it returns, and the page reads as presented, and as
   showing a data delivery, only once the setters have returned and the drawing they
   announced with `pending-task` is in. A visual may have redrawn the parts it marks by
   then, which the pass says with `layoutChanged` (visual-parts.js).

   A setter that throws is the element's failure. The pass reports it and still makes
   its other sets, and the set that threw is owed again in the next pass. The fail-soft
   box stands after what the element holds, unless the element places its own, until a
   pass whose sets all return.

   Beside a `LeafElement`, an element driven from here draws outside the presentation
   pass that draws parents first, has no hold on its sets through a gesture (`defer`),
   is not asked to draw again when a widget inside it is remounted (`drawsItself`),
   has its keys painted only when it says they changed, and is passed by the render
   check's replay. */
import { effect, untracked } from "/runtime/framework.js";
import { LeafElement, installElementIntegration } from "./leaf-element.js";
import {
  attachApplicationPresentation,
  attachWidgetPresentation,
  queueWidgetUpdate,
  watchPresentation,
} from "./semantic-state.js";
import { widgetDescriptor } from "./widget-descriptors.js";
import {
  drawsItself,
  widgetController,
  widgetMounted,
  widgetState,
} from "./widget-controller.js";
import { paintKeysWithin } from "./keyboard/scopes.js";
import { ElementData } from "./element-data.js";
import { registry, tagsDeclaring } from "./registry.js";
import { watchArrivals, watchOwner } from "./arrivals.js";
import {
  PENDING_TASK,
  failSoftUnreported,
  failurePlaced,
  layoutChanged,
  placesFailure,
  reportFailure,
} from "./widget-upgrade.js";

export const elementIntegration = {
  attachApplicationPresentation,
  attachWidgetPresentation,
  queueWidgetUpdate,
  watchPresentation,
  widgetDescriptor,
  drawsItself,
  widgetController,
  widgetMounted,
  paintKeysWithin,
  data: (/** @type {Element} */ element, /** @type {() => void} */ stage) =>
    new ElementData(element, stage),
  shadows: (/** @type {Element} */ element) => registry[element.localName]?.shadow,
};
installElementIntegration(elementIntegration);

let regions = 0;
// An arrival offers an element again whenever its children change (arrivals.js).
/** @type {WeakSet<Element>} */
const hosted = new WeakSet();

/** @param {Element} element */
function host(element) {
  if (hosted.has(element)) return;
  hosted.add(element);
  const descriptor = widgetDescriptor(element);
  const verbs = Object.keys(descriptor?.declaration.verbs ?? {});
  const controller = verbs.length ? widgetController(element) : null;
  const visual = Boolean(registry[element.localName]?.visual);
  const name = descriptor
    ? `widget:${descriptor.id}:render`
    : `element:${element.localName}:${++regions}`;
  /** @type {import("./framework/presentation.js").PresentationHandle | null} */
  let region = null;
  // The open claim the next pass settles.
  /** @type {import("./framework/presentation.js").PresentationTicket | null} */
  let ticket = null;
  /** @type {import("./widget-controller.js").WidgetReading | null} */
  let shown = null;
  let written = false;
  /** @type {HTMLElement | null} */
  let box = null;
  const claim = () => {
    ticket ??= region?.present((reason) => failSoftUnreported(element, reason)) ?? null;
  };
  // A source's accepted reading claims the region, and its delivery draws.
  const data = new ElementData(element, claim);
  // The element may hold nodes no later set makes again, so its failure stands after
  // them, in the tree that shows them.
  if (!failurePlaced(element))
    placesFailure(element, (placed) => {
      box?.remove();
      box = placed;
      (element.shadowRoot ?? element).append(placed);
      return true;
    });
  // The drawing that the sets of the pass under way announce.
  /** @type {PromiseLike<unknown>[] | null} */
  let announced = null;
  element.addEventListener(PENDING_TASK, (event) =>
    announced?.push(
      /** @type {import("./widget-upgrade.js").PendingTaskEvent} */ (event).complete,
    ),
  );
  // Every set the element is owed, each made whether or not another threw.
  /** @param {import("./widget-controller.js").WidgetReading | null} reading */
  const set = (reading) => {
    /** @type {unknown[]} */
    const failures = [];
    /** @param {() => void} owed */
    const attempt = (owed) => {
      try {
        owed();
      } catch (error) {
        failures.push(error);
      }
    };
    // What a setter reads is the element's own to follow, never the pass's.
    if (!written)
      attempt(() => {
        untracked(() => data.initialize());
        written = true;
      });
    attempt(() => data.deliver());
    if (reading && reading !== shown)
      attempt(() => {
        untracked(() => Object.assign(element, { state: widgetState(reading) }));
        shown = reading;
      });
    return failures;
  };
  // What a pass's sets came to, said to whoever hears it: the claim, the page's error
  // report, and the readers of a visual's layout.
  /** @param {import("./framework/presentation.js").PresentationTicket | null} drawing
   * @param {PromiseLike<unknown>[]} tasks @param {unknown[]} failures */
  const settle = (drawing, tasks, failures) => {
    if (visual) layoutChanged(element);
    if (failures.length) {
      reportFailure(element, failures[0]);
      drawing?.reject(failures[0]);
      return;
    }
    box?.remove();
    box = null;
    const drawn = Promise.all(tasks);
    drawing?.resolve(drawn);
    // The drawing the sets announced may redraw the marks as it lands.
    if (visual && tasks.length)
      void drawn.then(
        () => layoutChanged(element),
        () => {},
      );
  };
  const draw = () => {
    claim();
    const drawing = ticket;
    ticket = null;
    const reading = controller?.read() ?? null;
    // A revision's replacement lacks its verbs until its document is adopted.
    if (
      (reading && !verbs.every((verb) => verb in reading.state)) ||
      data.awaitsDelivery()
    ) {
      drawing?.resolve();
      return;
    }
    /** @type {PromiseLike<unknown>[]} */
    const tasks = [];
    announced = tasks;
    const failures = set(reading);
    announced = null;
    untracked(() => settle(drawing, tasks, failures));
  };
  /** @type {Element | null} */
  let parent = null;
  /** @type {(() => void) | null} */
  let leave = null;
  watchOwner(element, {
    // A paint that mounts the element connects it inside that paint, and what the
    // connection reads is its own to follow, never that paint's.
    connect: () =>
      untracked(() => {
        const attached = descriptor
          ? attachWidgetPresentation(descriptor.id, "render")
          : attachApplicationPresentation(name);
        region = attached;
        const leaveData = data.connect(name);
        const stop = effect(draw);
        leave = () => {
          stop();
          leaveData?.();
          attached.disconnect();
        };
        const parentChanged = parent !== element.parentElement;
        parent = element.parentElement;
        if (descriptor) widgetMounted(element, descriptor, parentChanged);
      }),
    disconnect() {
      leave?.();
      leave = region = ticket = null;
    },
  });
}

/** Drive each element whose tag declares `verbs` or `inputs`, and whose class is no
 * `LeafElement`, from outside while it stands. A tag is watched once its class is
 * defined: a property set on an element before its upgrade would be the element's own,
 * and hide the class's setter from every later set. */
export function hostDeclaredElements() {
  for (const tag of tagsDeclaring((entry) => entry.verbs || entry.inputs))
    void customElements.whenDefined(tag).then(() => {
      if (customElements.get(tag)?.prototype instanceof LeafElement) return;
      watchArrivals(tag, [], { arrive: host, leave() {} });
    });
}
