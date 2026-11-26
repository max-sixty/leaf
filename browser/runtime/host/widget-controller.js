/* The public semantic adapter for one captured widget owner.

   Leaf captures identity and declarations before upgrade. This controller exposes only
   immutable publisher selections and commands validated against the newest selection;
   the owner DOM is never a semantic store. A widget draws as a custom element Leaf
   sets its `state` on (element-integration.js), which owns the widget's render
   region; the controller owns its asynchronous preparation region (`prepare`), which
   removal pauses and reconnection restores. Registered preparation also holds full
   rendering readiness until completion or removal. A package reaches `read` and
   `dispatch` (`widgetController`), and says preparation only with the event below.

   A widget's element tells the controller of its drawing through events Leaf hears
   at the document. It says it has drawing under way with `pending-task`
   (lib/pending-task.js). One an element Leaf drives dispatches on itself is that
   element's own drawing and holds its render claim (element-integration.js). Any
   other reaches the preparation region of the nearest widget the event passed
   through, or, where it passed through none, a region of the dispatching element's.
   Either way it holds full rendering readiness until it is in. And it says it holds
   its own drawing with `lf-defer` (`DeferEvent`), at whose end the document-wide
   renderers read the page again.

   It records with `lf-action` and `lf-undo`, which Leaf hears on the element itself
   (`hearRecords`) and which reach `dispatch`. */
import { untracked } from "/vendor/signals-core.js";
import {
  applicationState,
  attachApplicationPresentation,
  attachWidgetPresentation,
} from "../state/semantic-state.js";
import { dispatchWidget, invalidateDom } from "./application.js";
import {
  descriptorStillMatches,
  widgetDescriptor,
} from "../records/widget-descriptors.js";
import { DEFER } from "../lib/widget-events.js";
import { PENDING_TASK } from "../lib/pending-task.js";
import { showFailure } from "../lib/failure.js";
import { watchOwner } from "../dom/arrivals.js";
import { holdRendering } from "../base/rendering.js";

/** @typedef {ReturnType<typeof createWidgetController>} Controller
 * @typedef {Pick<Controller, "read" | "dispatch">} WidgetController
 * @typedef {import('../state/semantic-application.js').WidgetDescriptor} WidgetDescriptor
 * @typedef {ReturnType<ReturnType<typeof applicationState.selectWidget>["read"]>} WidgetReading
 * @typedef {{completion: Promise<unknown[]>}} Preparation
 * @typedef {ReturnType<typeof attachWidgetPresentation>} PreparationHandle */
/** @type {WeakMap<Element, WidgetController>} */
const controllers = new WeakMap();

// A widget Leaf drives has drawn the first sets of an arrival (element-integration.js).
// It can first appear when thread presentation mounts message markup after the global
// projection pass, so coordinate and provenance work runs again now that it and its
// units exist; state application coalesces the request.
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

  const prepared = () =>
    (preparationHandle ??= attachWidgetPresentation(descriptor.id, "preparation"));

  // The owner stands in the page at every call: `prepare` is reached by an event
  // heard at the document, and `connect` as the owner returns.
  /** @param {PromiseLike<unknown>} promise */
  const holdPreparation = (promise) => {
    if (pendingPreparations.has(promise)) {
      if (!pendingPreparations.get(promise))
        pendingPreparations.set(promise, holdRendering());
      return;
    }
    pendingPreparations.set(promise, holdRendering());
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
    handle.present((reason) => showFailure(owner, reason)).resolve(completion);

  // The controller is an owner of its own: a paint that mounts its widget connects it,
  // and what it reads to connect is its own, never that paint's.
  const connect = () =>
    untracked(() => {
      if (!owner.isConnected) return;
      for (const promise of pendingPreparations.keys()) holdPreparation(promise);
      if (preparation && !preparationHandle)
        presentPreparation(prepared(), preparation);
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
    /** @param {import("../records/pending/dispatch.js").WidgetCommand} command */
    dispatch(command) {
      if (!descriptorStillMatches(owner, descriptor)) return null;
      const delivery = dispatchWidget(descriptor, command);
      if (!delivery) return null;
      return immutable({ reading: read(), delivery });
    },
    // Hold the widget's preparation region on drawing announced from inside it
    // (`pending-task`, below). Promises announced under one reading are one
    // requirement: a later one joins the earlier rather than superseding it.
    /** @param {PromiseLike<unknown>} promise */
    prepare(promise) {
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
      presentPreparation(prepared(), preparation);
      const clear = () => {
        if (preparationBatch?.completion === completion) preparationBatch = null;
      };
      completion.then(clear, clear);
    },
  });
}

/** @type {WeakMap<Element, Controller>} */
const created = new WeakMap();
/** The controller of a widget the page has captured, made on the first call, with its
 * watch of the owner's leaving and return. Leaf's own code asks here; a package asks
 * `widgetController`.
 * @param {Element} owner */
export function controllerOf(owner) {
  let controller = created.get(owner);
  if (!controller) created.set(owner, (controller = createWidgetController(owner)));
  return controller;
}

/** What a package reads and records of a widget: `read` and `dispatch`. A custom
 * element constructed with document.createElement receives its authored id only after
 * its constructor and field initializers run, so the descriptor is resolved on first
 * use, which is normally connectedCallback, and a data renderer can build a
 * replacement with the same revision-bound identity as the authored node.
 * @param {Element} owner @returns {WidgetController} */
export function widgetController(owner) {
  let controller = controllers.get(owner);
  if (!controller) {
    controller = Object.freeze({
      read: () => controllerOf(owner).read(),
      /** @param {import("../records/pending/dispatch.js").WidgetCommand} command */
      dispatch: (command) => controllerOf(owner).dispatch(command),
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

// The drawing each element has announced on itself and not finished, and the holds
// it has on its own drawing. A claim on the element's own region waits for all the
// drawing under way when it settles, so a later claim never lets go of an earlier
// drawing, and for the holds standing when it was made, since the element draws
// nothing under one: a hold that begins in the draw a claim is for does not keep that
// claim. A drawing also holds full rendering readiness while its element stands, as a
// preparation does (`holdPreparation`): it lets go as the element leaves and holds
// again on its return. A hold does not, since nothing is being drawn.
/** Each drawing under way, with its hold on rendering readiness while its element stands.
 * @type {WeakMap<Element, Map<PromiseLike<unknown>, ReturnType<typeof holdRendering> | null>>} */
const underWay = new WeakMap();
/** @type {WeakMap<Element, Set<PromiseLike<unknown>>>} */
const holding = new WeakMap();
/** The drawing `element` has under way. @param {Element} element */
export const drawingOf = (element) => Promise.all(underWay.get(element)?.keys() ?? []);
/** Whether `element` has drawing under way. @param {Element} element */
export const isDrawing = (element) => Boolean(underWay.get(element)?.size);
/** The holds standing on `element` now. @param {Element} element */
export const holdsOn = (element) => [...(holding.get(element) ?? [])];
/** Count a drawing `element` announced on itself. @param {Element} element
 * @param {PromiseLike<unknown>} complete */
export function announceDrawing(element, complete) {
  let drawings = underWay.get(element);
  if (!drawings) {
    const all = (drawings = new Map());
    underWay.set(element, all);
    watchOwner(element, {
      connect() {
        for (const [drawing, release] of all)
          if (!release) all.set(drawing, holdRendering());
      },
      disconnect() {
        for (const [drawing, release] of all) {
          release?.("cancel");
          all.set(drawing, null);
        }
      },
    });
  }
  const all = drawings;
  all.set(complete, element.isConnected ? holdRendering() : null);
  const done = () => {
    // A promise reaction can precede the observer delivering the element's departure.
    all.get(complete)?.(element.isConnected ? "settle" : "cancel");
    all.delete(complete);
  };
  Promise.resolve(complete).then(done, done);
}

// The `pending-task` events an element Leaf drives has already counted as its own
// drawing (element-integration.js), which owns that element's render region.
/** @type {WeakSet<Event>} */
const drawingsTaken = new WeakSet();
/** @param {Event} event */
export const takeDrawing = (event) => drawingsTaken.add(event);

// Drawing announced anywhere else: the nearest widget the event passed through on its
// way out holds its preparation on it (`prepare`). Where it passed through none, as
// from an element with no id or one of Leaf's own surfaces, the page holds a region of
// that element's on it, so the page still reads as presented only once the drawing is
// in.
document.addEventListener(PENDING_TASK, (event) => {
  if (drawingsTaken.has(event)) return;
  const owner = widgetOn(event);
  if (owner) return void controllerOf(owner).prepare(event.complete);
  const [origin] = event.composedPath();
  if (!(origin instanceof Element)) return;
  const held = holdsOn(origin);
  announceDrawing(origin, event.complete);
  ownRegion(origin)?.resolve(Promise.all([drawingOf(origin), ...held]));
});

// An element's own region, attached while it stands and announces drawing.
/** @type {WeakMap<Element, {handle: PreparationHandle | null}>} */
const ownRegions = new WeakMap();
let regions = 0;
/** @param {Element} origin */
function ownRegion(origin) {
  let region = ownRegions.get(origin);
  if (!region) {
    const held = (region = { handle: /** @type {PreparationHandle | null} */ (null) });
    ownRegions.set(origin, held);
    watchOwner(origin, {
      disconnect() {
        held.handle?.disconnect();
        held.handle = null;
      },
    });
  }
  if (!origin.isConnected) return null;
  region.handle ??= attachApplicationPresentation(
    `element:${origin.localName}:drawing:${++regions}`,
  );
  return region.handle.present((reason) => showFailure(origin, reason));
}

// A hold an element has on its own drawing while it rewrites its nodes
// (`DeferEvent`). A claim on the element's region made while it stands waits for the
// hold to end, since the element draws nothing until then, and as it ends the
// document-wide renderers read the page again.
document.addEventListener(DEFER, (event) => {
  const [origin] = event.composedPath();
  let holds = origin instanceof Element ? holding.get(origin) : null;
  if (!holds && origin instanceof Element) holding.set(origin, (holds = new Set()));
  holds?.add(event.complete);
  const ended = () => {
    holds?.delete(event.complete);
    void invalidateDom();
  };
  Promise.resolve(event.complete).then(ended, ended);
});

// Each unit of a verb whose action in force the user may take back, with the Undo
// candidate that takes it back.
/** @param {WidgetReading["actions"][string] | undefined} action */
const undoCandidates = (action) => {
  const undo = new Map(action?.undo.map((event) => [event.id, event]));
  /** @type {Map<string, WidgetReading["actions"][string]["undo"][number]>} */
  const units = new Map();
  for (const { unit, event } of action?.inForce ?? []) {
    const candidate = undo.get(event.id);
    if (candidate) units.set(unit, candidate);
  }
  return units;
};

// A widget's reading as the immutable `state` property Leaf sets on an element it
// drives from outside (element-integration.js): each declared verb's folded state, with
// whether the user may act on it now (`available`), the reason they may not where Leaf
// has one to give (`unavailable`), and whether `lf-undo` would take back the action in
// force (`undoable`), which a verb holding a state for each unit says on each unit. A
// verb the agent writes reads as one the user may neither act on nor take back.
/** @param {WidgetReading} reading @returns {import("../../types/domain.js").WidgetState} */
export const widgetState = ({ state, actions }) =>
  immutable(
    Object.fromEntries(
      Object.entries(state).map(([verb, held]) => {
        const undoable = undoCandidates(actions[verb]);
        const offered = {
          available: actions[verb]?.available ?? false,
          unavailable: actions[verb]?.unavailable ?? null,
        };
        return [
          verb,
          "units" in held
            ? {
                ...held,
                units: Object.fromEntries(
                  Object.entries(held.units).map(([unit, at]) => [
                    unit,
                    { ...at, undoable: undoable.has(unit) },
                  ]),
                ),
                ...offered,
              }
            : { ...held, undoable: undoable.size > 0, ...offered },
        ];
      }),
    ),
  );

// What a widget records and takes back, heard on the element Leaf drives
// (element-integration.js): an `lf-action` event whose detail is `{verb, detail, says?,
// attempt?}`, or `lf-undo` whose detail is `{verb, unit?}`, naming the unit where the
// verb holds a state for each. Leaf listens on the element, where it also sets `state`,
// so an event the element dispatches on itself needs no options and is heard wherever
// the element stands, in a thread message or another widget's shadow tree as on the
// page. An event that bubbles to the element from a node inside it is heard too, as
// any listener hears one. It belongs to the nearest widget declaring `verbs` that it
// passed through, so the element records none that came up from such a widget inside
// it. It records none once it has left the page.
//
// `detail` is the action's own detail, under the name the verb's declaration and the
// log give it. It stays a member of its own: its fields are the package's to name, and
// a field beside `verb`, `says` and `attempt` could take one of their names. `attempt`
// is the id a draft minted for the words the action sends (`sendDraft`, records/drafts.js), so
// a refusal gives them back to that draft.
//
// The widget's reading holds the result before `dispatchEvent` returns. Leaf sets
// `delivery` on an event it sends, which resolves to the event the server admitted, or
// null once it refuses; an event Leaf sends nothing for, as while the action is
// unavailable or no action in force can be taken back, has none.
/** @param {Element} owner A widget whose tag declares `verbs`. */
export function hearRecords(owner) {
  const controller = controllerOf(owner);
  /** @param {ElementEventMap["lf-action" | "lf-undo"]} event
   * @param {(reading: WidgetReading) => import("../records/pending/dispatch.js").WidgetCommand | null | undefined} command */
  const record = (event, command) => {
    if (!owner.isConnected) return;
    if (widgetOn(event, ({ declaration }) => declaration.verbs) !== owner) return;
    const sent = command(controller.read());
    const delivery = sent && controller.dispatch(sent)?.delivery;
    if (delivery) event.delivery = delivery;
  };
  owner.addEventListener("lf-action", (event) =>
    record(event, () => {
      const { verb, detail, says, attempt } = event.detail;
      return {
        kind: "action",
        verb,
        ...(detail && { detail }),
        ...(says && { says }),
        ...(attempt && { attempt }),
      };
    }),
  );
  owner.addEventListener("lf-undo", (event) =>
    record(event, ({ state, actions }) => {
      const { verb, unit } = event.detail;
      const units = undoCandidates(actions[verb]);
      const candidate =
        state[verb] && "units" in state[verb]
          ? units.get(unit ?? "")
          : units.values().next().value;
      return (
        candidate && {
          kind: "undo",
          target: ("attempt" in candidate ? candidate.attempt : null) ?? candidate.id,
        }
      );
    }),
  );
}
