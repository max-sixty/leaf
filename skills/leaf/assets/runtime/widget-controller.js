/* The public semantic adapter for one captured widget owner.

   Leaf captures identity and declarations before upgrade. This controller exposes only
   immutable publisher selections and commands validated against the newest selection;
   the owner DOM is never a semantic store. A widget draws as a `LeafElement`
   (leaf-element.js), which owns the widget's render region; the controller owns its
   asynchronous preparation region (`present`), which removal pauses and reconnection
   restores. Registered preparation also holds full rendering readiness until
   completion or removal. Local editing holds the widget's drawing (`defer`) until the
   gesture releases it. */
import { untracked } from "/vendor/browser-runtime.js";
import { applicationState, attachWidgetPresentation } from "./semantic-state.js";
import { dispatchWidget, invalidateDom } from "./application.js";
import { descriptorStillMatches, widgetDescriptor } from "./widget-descriptors.js";
import { failSoftUnreported } from "./widget-upgrade.js";
import { watchOwner } from "./arrivals.js";
import { holdRendering } from "./rendering.js";

const controllers = new WeakMap();
const ancestorRefreshes = new Set();
let ancestorRefreshQueued = false;
// Owners that draw themselves (`LeafElement`, leaf-element.js), each with the hold its
// gestures defer and the refresh an ancestor's remount asks of it.
const selfDrawn = new WeakMap();
export const drawsItself = (owner, drawing) => selfDrawn.set(owner, drawing);

// A widget connected to draw its reading. A data renderer may remount a nested widget
// without changing its semantic reading. Its own owner restores its state; an ancestor
// may own its placement, so refresh each mounted ancestor once for the new parent. The
// caller remembers the parent, which keeps the ancestor's corrective move from looping.
// A widget can also first appear when thread presentation mounts frozen markup after the
// global projection pass, so coordinate and provenance work runs again now that it and
// its units exist; state application coalesces the request.
export function widgetMounted(owner, descriptor, parentChanged) {
  if (parentChanged && applicationState.read().document.authored.has(descriptor.id))
    refreshAncestors(owner);
  invalidateDom();
}

function refreshAncestors(owner) {
  for (
    let ancestor = owner.parentElement;
    ancestor;
    ancestor = ancestor.parentElement
  ) {
    const drawing = selfDrawn.get(ancestor);
    if (drawing) ancestorRefreshes.add(drawing);
  }
  if (!ancestorRefreshes.size || ancestorRefreshQueued) return;
  ancestorRefreshQueued = true;
  queueMicrotask(() => {
    ancestorRefreshQueued = false;
    const pending = [...ancestorRefreshes];
    ancestorRefreshes.clear();
    for (const drawing of pending) drawing.refresh();
  });
}

const immutable = (value) => {
  if (value !== null && typeof value === "object" && !Object.isFrozen(value)) {
    for (const child of Object.values(value)) immutable(child);
    Object.freeze(value);
  }
  return value;
};

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

function createWidgetController(owner) {
  const descriptor = widgetDescriptor(owner);
  if (!descriptor)
    throw new Error(
      `leaf: <${owner.localName}>#${owner.id || "(missing id)"} has no captured widget descriptor`,
    );
  const selected = applicationState.selectWidget(descriptor);
  let deferred = false;
  let preparationHandle = null;
  const pendingPreparations = new Map();
  let preparation = null;
  let preparationBatch = null;

  const read = () =>
    descriptorStillMatches(owner, descriptor)
      ? selected.read()
      : unavailable(selected.read());

  const prepared = () => {
    if (!preparationHandle && owner.isConnected)
      preparationHandle = attachWidgetPresentation(descriptor.id, "preparation", owner);
    return preparationHandle;
  };

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

  const presentPreparation = (handle, { value, completion }) =>
    handle
      .present(value, (reason) => failSoftUnreported(owner, reason))
      .resolve(completion);

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
    dispatch(command) {
      if (!descriptorStillMatches(owner, descriptor)) return null;
      const delivery = dispatchWidget(descriptor, command);
      if (!delivery) return null;
      return immutable({ reading: read(), delivery });
    },
    // Hold the widget's drawing through a gesture that rewrites its nodes; the release
    // draws the newest reading at once and returns it.
    defer() {
      const drawing = selfDrawn.get(owner);
      if (!drawing)
        throw new Error(`<${owner.localName}> defers only a LeafElement's drawing`);
      if (deferred) throw new Error("Widget presentation is already deferred");
      deferred = true;
      const release = drawing.hold();
      let released = false;
      return () => {
        if (released) return read();
        released = true;
        deferred = false;
        release();
        invalidateDom();
        return read();
      };
    },
    present(promise) {
      const value = read();
      if (!preparationBatch || preparationBatch.value !== value) {
        preparationBatch = { value, promises: [] };
      }
      preparationBatch.promises.push(promise);
      const batch = preparationBatch;
      const completion = Promise.all(batch.promises);
      batch.completion = completion;
      preparation = { value, completion };
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

export function widgetController(owner) {
  let controller = controllers.get(owner);
  if (!controller) {
    // A custom element constructed with document.createElement receives its authored
    // id only after its constructor and field initializers run. Resolve the descriptor
    // on first use, which is normally connectedCallback, so a data renderer can build
    // a replacement with the same revision-bound identity as the authored node.
    let implementation = null;
    const resolve = () => (implementation ??= createWidgetController(owner));
    controller = Object.freeze(
      Object.fromEntries(
        ["read", "dispatch", "defer", "present"].map((method) => [
          method,
          (...args) => resolve()[method](...args),
        ]),
      ),
    );
    controllers.set(owner, controller);
  }
  return controller;
}
