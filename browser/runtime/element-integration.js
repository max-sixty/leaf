/* Leaf's host capabilities for the portable element lifecycle. Install before
   widgets connect: page presentation, authored/bound data, widget controllers and
   command dressing belong to the page, while the element owns Lit and its failures.
   A plain host supplies properties and listens to drawn without loading this module.

   A `LeafElement` asks for those capabilities itself. Any other custom element whose
   tag declares `verbs` or `inputs` is given them from outside (`hostDeclaredElements`),
   so it imports nothing: while it stands, Leaf sets its `state` to its widget's reading
   (`widgetState`, widget-controller.js) at first and each time that reading moves, and
   sets each bound input on the property its declaration names (element-data.js). Each
   set runs in the stack that moved the reading, inside a claim on the element's render
   region, so the page reads as presented only once the setter has returned. Drawing
   that outlasts the setter is a `pending-task` event, and recording is an `lf-action`
   event (widget-controller.js). */
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
import { failSoftUnreported, reportFailure } from "./widget-upgrade.js";

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

/** @param {Element} element */
function host(element) {
  if (element instanceof LeafElement) return;
  const descriptor = widgetDescriptor(element);
  const verbs = Object.keys(descriptor?.declaration.verbs ?? {});
  const controller = verbs.length ? widgetController(element) : null;
  // A `value` record naming an element `property` and `event` needs no module code: the
  // property shows the recorded value, and the event records the value the property holds.
  const held = verbs.flatMap((verb) => {
    const { record } = descriptor?.declaration.verbs?.[verb] ?? {};
    return record?.kind === "value" && record.event && record.property
      ? [{ verb, property: record.property, event: record.event }]
      : [];
  });
  const name = descriptor
    ? `widget:${descriptor.id}:render`
    : `element:${element.localName}:${++regions}`;
  /** @type {import("./framework/presentation.js").PresentationHandle | null} */
  let region = null;
  /** @type {import("./framework/presentation.js").PresentationTicket | null} */
  let ticket = null;
  /** @type {ReturnType<ReturnType<typeof widgetController>["read"]> | null} */
  let shown = null;
  const claim = () => {
    ticket ??= region?.present((reason) => failSoftUnreported(element, reason)) ?? null;
  };
  // A source's accepted reading claims the region, and its delivery draws.
  const data = new ElementData(element, claim);
  const draw = () => {
    claim();
    const drawing = ticket;
    ticket = null;
    try {
      if (!data.awaitsDelivery()) data.deliver();
      const reading = controller?.read();
      // A revision's replacement lacks its verbs until its document is adopted.
      if (reading && reading !== shown && verbs.every((verb) => verb in reading.state))
        untracked(() => {
          const state = widgetState(reading);
          Object.assign(element, { state });
          for (const { verb, property } of held)
            Object.assign(element, { [property]: state[verb]?.value ?? null });
        });
      shown = reading ?? null;
      // A setter that schedules its draw, as a Lit property does, says when it is in.
      drawing?.resolve(
        /** @type {{updateComplete?: unknown}} */ (element).updateComplete,
      );
    } catch (error) {
      reportFailure(element, error);
      drawing?.reject(error);
    }
  };
  /** @type {Array<(() => unknown) | null>} */
  let leaving = [];
  watchOwner(element, {
    connect() {
      region = descriptor
        ? attachWidgetPresentation(descriptor.id, "render")
        : attachApplicationPresentation(name);
      leaving = [
        effect(draw),
        data.connect(name),
        () => region?.disconnect(),
        ...held.map(({ verb, property, event }) => {
          /** @param {Event} fired */
          const record = (fired) => {
            const value = /** @type {any} */ (element)[property] ?? null;
            if (
              fired.target === element &&
              value !== (shown?.state[verb]?.value ?? null)
            )
              controller?.dispatch({ kind: "action", verb, detail: { value } });
          };
          element.addEventListener(event, record);
          return () => element.removeEventListener(event, record);
        }),
      ];
      if (descriptor) widgetMounted(element, descriptor, false);
    },
    disconnect() {
      for (const leave of leaving) leave?.();
      region = ticket = shown = null;
    },
  });
}

// Each element of a tag declaring `verbs` or `inputs`, once its module has defined it.
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
