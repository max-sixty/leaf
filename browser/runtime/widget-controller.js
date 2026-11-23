/* The public semantic adapter for one captured widget owner.

   Leaf captures identity and declarations before upgrade. This controller exposes only
   immutable publisher selections and commands validated against the newest selection;
   the owner DOM is never a semantic store. Leaf sets a widget's reading on its element
   and owns its render region (element-integration.js); the controller owns its
   asynchronous preparation region (`present`), which removal pauses and reconnection
   restores. Registered preparation also holds full rendering readiness until
   completion or removal.

   A widget's element reaches all of this by events, heard here at the document:
   `pending-task` for drawing under way (`PendingTaskEvent`, widget-upgrade.js), which
   reaches the preparation region of the nearest widget it passed through, or a region
   of its own element's where it passed through none; `lf-action` and `lf-undo` to
   record and take back; and `lf-hold` for a gesture that rewrites its nodes outside a
   draw, at whose end the document-wide renderers read the page again. */
import { untracked } from "/runtime/framework.js";
import {
  applicationState,
  attachApplicationPresentation,
  attachWidgetPresentation,
} from "./semantic-state.js";
import { dispatchWidget, invalidateDom } from "./application.js";
import { descriptorStillMatches, widgetDescriptor } from "./widget-descriptors.js";
import { HOLD, PENDING_TASK, failSoftUnreported } from "./widget-upgrade.js";
import { watchOwner } from "./arrivals.js";
import { holdRendering } from "./rendering.js";

/** @typedef {ReturnType<typeof createWidgetController>} WidgetController
 * @typedef {import('./framework/application.js').WidgetDescriptor} WidgetDescriptor
 * @typedef {ReturnType<ReturnType<typeof applicationState.selectWidget>["read"]>} WidgetReading
 * @typedef {{completion: Promise<unknown[]>}} Preparation
 * @typedef {ReturnType<typeof attachWidgetPresentation>} PreparationHandle */
/** @type {WeakMap<Element, WidgetController>} */
const controllers = new WeakMap();

// A widget connected to draw its reading. It can first appear when thread presentation
// mounts message markup after the global projection pass, so coordinate and provenance
// work runs again now that it and its units exist; state application coalesces the
// request.
export function widgetMounted() {
  invalidateDom();
}

/** @template T @param {T} value @returns {T} */
const immutable = (value) => {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) immutable(child);
    Object.freeze(value);
  }
  return value;
};

/** @param {WidgetReading} reading */
const unavailable = (reading) =>
  immutable({
    ...structuredClone(reading),
    actions: Object.fromEntries(
      Object.entries(reading.actions).map(([verb, entry]) => [
        verb,
        { ...entry, available: false, undo: [] },
      ]),
    ),
  });

/** @param {Element} owner */
function createWidgetController(owner) {
  const descriptor = widgetDescriptor(owner);
  if (!descriptor)
    throw new Error(
      `leaf: <${owner.localName}>#${owner.id || "(missing id)"} has no captured widget descriptor`,
    );
  const selected = applicationState.selectWidget(descriptor);
  /** @type {PreparationHandle | null} */
  let preparationHandle = null;
  /** @type {Map<PromiseLike<unknown>, ReturnType<typeof holdRendering> | null>} */
  const pendingPreparations = new Map();
  /** @type {Preparation | null} */
  let preparation = null;
  /** @type {{value: WidgetReading, promises: PromiseLike<unknown>[], completion?: Promise<unknown[]>} | null} */
  let preparationBatch = null;

  const read = () =>
    descriptorStillMatches(owner, descriptor)
      ? selected.read()
      : unavailable(selected.read());

  const prepared = () => {
    if (!preparationHandle && owner.isConnected)
      preparationHandle = attachWidgetPresentation(descriptor.id, "preparation");
    return preparationHandle;
  };

  /** @param {PromiseLike<unknown>} promise */
  const holdPreparation = (promise) => {
    if (pendingPreparations.has(promise)) {
      if (owner.isConnected && !pendingPreparations.get(promise))
        pendingPreparations.set(promise, holdRendering());
      return;
    }
    pendingPreparations.set(promise, owner.isConnected ? holdRendering() : null);
    // A failed child reports immediately, but its siblings can still commit DOM.
    // Superseded batches can also still report failure into this connected owner.
    const settled = () => {
      // A promise reaction can precede the observer delivering its owner's departure.
      pendingPreparations.get(promise)?.(owner.isConnected ? "settle" : "cancel");
      pendingPreparations.delete(promise);
    };
    Promise.resolve(promise).then(settled, settled);
  };

  /** @param {PreparationHandle} handle @param {Preparation} preparation */
  const presentPreparation = (handle, { completion }) =>
    handle.present((reason) => failSoftUnreported(owner, reason)).resolve(completion);

  // The controller is an owner of its own: a paint that mounts its widget connects it,
  // and what it reads to connect is its own, never that paint's.
  const connect = () =>
    untracked(() => {
      if (!owner.isConnected) return;
      for (const promise of pendingPreparations.keys()) holdPreparation(promise);
      if (preparation && !preparationHandle) {
        const handle = prepared();
        if (handle) presentPreparation(handle, preparation);
      }
    });

  const disconnect = () => {
    preparationHandle?.disconnect();
    preparationHandle = null;
    for (const [promise, release] of pendingPreparations) {
      release?.("cancel");
      pendingPreparations.set(promise, null);
    }
  };

  watchOwner(owner, { connect, disconnect });

  return Object.freeze({
    read,
    /** @param {import("./pending/dispatch.js").WidgetCommand} command */
    dispatch(command) {
      if (!descriptorStillMatches(owner, descriptor)) return null;
      const delivery = dispatchWidget(descriptor, command);
      if (!delivery) return null;
      return immutable({ reading: read(), delivery });
    },
    /** @template {PromiseLike<unknown>} P @param {P} promise @returns {P} */
    present(promise) {
      const value = read();
      if (!preparationBatch || preparationBatch.value !== value) {
        preparationBatch = { value, promises: [] };
      }
      preparationBatch.promises.push(promise);
      const batch = preparationBatch;
      const completion = Promise.all(batch.promises);
      batch.completion = completion;
      preparation = { completion };
      holdPreparation(promise);
      const handle = prepared();
      if (handle) presentPreparation(handle, preparation);
      const clear = () => {
        if (preparationBatch?.completion === completion) preparationBatch = null;
      };
      completion.then(clear, clear);
      // Package code may await the concrete renderer result; the coordinator's
      // aggregate is mechanical bookkeeping, not a replacement value.
      return promise;
    },
  });
}

/** @param {Element} owner @returns {WidgetController} */
export function widgetController(owner) {
  let controller = controllers.get(owner);
  if (!controller) {
    // A custom element constructed with document.createElement receives its authored
    // id only after its constructor and field initializers run. Resolve the descriptor
    // on first use, which is normally connectedCallback, so a data renderer can build
    // a replacement with the same revision-bound identity as the authored node.
    /** @type {WidgetController | null} */
    let implementation = null;
    const resolve = () => (implementation ??= createWidgetController(owner));
    controller = Object.freeze({
      read: () => resolve().read(),
      dispatch: (command) => resolve().dispatch(command),
      present: (promise) => resolve().present(promise),
    });
    controllers.set(owner, controller);
  }
  return controller;
}

// The nearest widget an event passed through on its way out that `holds` admits.
/** @param {Event} event @param {(descriptor: WidgetDescriptor) => unknown} [holds] */
const widgetOn = (event, holds = () => true) =>
  event
    .composedPath()
    .filter((node) => node instanceof Element)
    .find((node) => {
      const descriptor = widgetDescriptor(node);
      return descriptor && holds(descriptor);
    });

// Drawing an element announces: the nearest widget the event passed through on its way
// out holds its presentation on it, as `present` does. Where it passed through none, as
// from an element with no id or one of Leaf's own surfaces, the page holds a region of
// that element's on it, so the page still reads as presented only once the drawing is in.
document.addEventListener(PENDING_TASK, (event) => {
  const owner = widgetOn(event);
  if (owner) return void widgetController(owner).present(event.complete);
  const [origin] = event.composedPath();
  if (origin instanceof Element) drawingRegion(origin)?.resolve(event.complete);
});

// An element's own region, attached while it stands and announces drawing.
/** @type {WeakMap<Element, {handle: PreparationHandle | null}>} */
const drawingRegions = new WeakMap();
let drawings = 0;
/** @param {Element} origin */
function drawingRegion(origin) {
  let region = drawingRegions.get(origin);
  if (!region) {
    const held = (region = { handle: /** @type {PreparationHandle | null} */ (null) });
    drawingRegions.set(origin, held);
    watchOwner(origin, {
      disconnect() {
        held.handle?.disconnect();
        held.handle = null;
      },
    });
  }
  if (!origin.isConnected) return null;
  region.handle ??= attachApplicationPresentation(
    `element:${origin.localName}:drawing:${++drawings}`,
  );
  return region.handle.present((reason) => failSoftUnreported(origin, reason));
}

// A hold an element has on its nodes through a gesture that rewrites them
// (`HoldEvent`): as it ends, the document-wide renderers read the page again.
document.addEventListener(HOLD, (event) => {
  const read = () => void invalidateDom();
  Promise.resolve(event.complete).then(read, read);
});

// The action in force for a verb, or for one of its units, that the user may take back.
/** @param {WidgetReading["actions"][string] | undefined} action @param {string} [unit] */
const takenBack = (action, unit) => {
  const held = action?.inForce.find(
    (entry) => unit === undefined || entry.unit === unit,
  )?.event;
  return (held && action?.undo.find((event) => event.id === held.id)) ?? null;
};

// A widget's reading as the `state` property Leaf sets on an element that draws itself
// without Leaf's helpers (element-integration.js): each declared verb's folded state,
// with whether the user may act on it now, why not, and whether `lf-undo` would take
// its action in force back.
/** @param {WidgetReading} reading */
export const widgetState = ({ state, actions }) =>
  Object.fromEntries(
    Object.entries(state).map(([verb, held]) => [
      verb,
      {
        ...held,
        available: actions[verb]?.available ?? false,
        unavailable: actions[verb]?.unavailable ?? null,
        undoable: Boolean(takenBack(actions[verb])),
      },
    ]),
  );

// Recording announced from outside Leaf's helpers. A widget dispatches a cancelable,
// bubbling, composed `lf-action` whose detail is `{verb, detail, says?, attempt?}`, or
// `lf-undo` whose detail is `{verb, unit?}`, and the nearest recording widget on the
// event's way out sends it as `dispatch` does: the widget's reading holds the result
// before `dispatchEvent` returns. `attempt` is the id a draft minted for the words the
// action sends (`sendDraft`, drafts.js), so a refusal gives them back to that draft. The event's `delivery` resolves to the admitted event, or
// null once the server refuses it; an action Leaf sends nothing for is cancelled, so
// `dispatchEvent` returns false.
/** @param {CustomEvent & {delivery?: unknown}} event
 * @param {(reading: WidgetReading) => import("./pending/dispatch.js").WidgetCommand | null} command */
function record(event, command) {
  const owner = widgetOn(event, ({ declaration }) => declaration.verbs);
  if (!owner) return;
  let delivery = null;
  try {
    const controller = widgetController(owner);
    const sent = command(controller.read());
    delivery = (sent && controller.dispatch(sent)?.delivery) ?? null;
  } finally {
    if (delivery) event.delivery = delivery;
    else event.preventDefault();
  }
}
document.addEventListener("lf-action", (event) =>
  record(event, () => ({ ...event.detail, kind: "action" })),
);
document.addEventListener("lf-undo", (event) =>
  record(event, ({ actions }) => {
    const taken = takenBack(actions[event.detail.verb], event.detail.unit);
    return (
      taken && {
        kind: "undo",
        target: ("attempt" in taken ? taken.attempt : null) ?? taken.id,
      }
    );
  }),
);
