/* The public semantic adapter for one captured widget owner.

   Leaf captures identity and declarations before upgrade. This controller exposes only
   immutable publisher selections and commands validated against the newest selection;
   the owner DOM is never a semantic store. Its semantic render and asynchronous
   preparation are two stable widget-id regions: neither can supersede the other's
   proof. Local editing defers the render region at its newest unpublished reading. */
import { applicationState, attachWidgetPresentation } from "./semantic-state.js";
import { dispatchWidget, invalidateDom } from "./application.js";
import { runtime } from "./context.js";
import { renderRetired, settlementSlots } from "./passages.js";
import {
  captureWidgetReference,
  descriptorStillMatches,
  resolveWidgetReference,
  widgetDescriptor,
} from "./widget-descriptors.js";
import { failSoft } from "./widget-upgrade.js";

const controllers = new WeakMap();
const lifecycles = new WeakMap();
let lifecycleObserver = null;
const ancestorRefreshes = new Set();
let ancestorRefreshQueued = false;
let orderedRenders = new Map();
let orderedRenderQueued = false;

const { registry } = runtime;

function renderSettlement(owner, state) {
  const outcomes = settlementSlots()[owner.localName];
  if (!outcomes) return;
  const spec = registry[owner.localName]["x-state"][Object.keys(outcomes)[0]];
  const outcome = state[spec.facet].action;
  if (outcomes[outcome]) owner.setAttribute("data-lf-state", outcome);
  else owner.removeAttribute("data-lf-state");
  renderRetired(owner);
}

const visitElements = (node, visit) => {
  if (!(node instanceof Element)) return;
  visit(node);
  for (const child of node.querySelectorAll("*")) visit(child);
};

function refreshAncestorControllers(owner) {
  for (
    let ancestor = owner.parentElement;
    ancestor;
    ancestor = ancestor.parentElement
  ) {
    const lifecycle = lifecycles.get(ancestor);
    if (lifecycle) {
      ancestorRefreshes.add(lifecycle);
    }
  }
  if (!ancestorRefreshes.size || ancestorRefreshQueued) return;
  ancestorRefreshQueued = true;
  queueMicrotask(() => {
    ancestorRefreshQueued = false;
    const pending = [...ancestorRefreshes];
    ancestorRefreshes.clear();
    for (const lifecycle of pending) lifecycle.refresh();
  });
}

function queueOrderedRender(id, reading, handle, render) {
  let release;
  const completion = new Promise((resolve) => {
    release = resolve;
  });
  void handle.present(reading, completion);
  const previous = orderedRenders.get(id);
  orderedRenders.set(id, { render, release });
  // The replacement hold is already installed, so the superseded publication cannot
  // briefly look presented between two semantic readings in this rendering turn.
  previous?.release();
  if (orderedRenderQueued) return;
  orderedRenderQueued = true;
  queueMicrotask(() => {
    orderedRenderQueued = false;
    const pending = orderedRenders;
    orderedRenders = new Map();
    const order = applicationState.read().effective.widgets.keys();
    for (const id of order) {
      const queued = pending.get(id);
      if (!queued) continue;
      pending.delete(id);
      queued.render();
      queued.release();
    }
    for (const queued of pending.values()) {
      queued.render();
      queued.release();
    }
  });
}

function watchLifetime(owner, lifecycle) {
  lifecycles.set(owner, lifecycle);
  if (lifecycleObserver) return;
  lifecycleObserver = new MutationObserver((records) => {
    const changed = new Set();
    for (const record of records) {
      for (const node of record.addedNodes)
        visitElements(node, (el) => changed.add(el));
      for (const node of record.removedNodes)
        visitElements(node, (el) => changed.add(el));
    }
    // Mutation records describe intermediate moves. `isConnected` after the whole
    // batch distinguishes a real removal from Leaf's presentation-only reparenting.
    for (const element of changed) {
      const ownerLifecycle = lifecycles.get(element);
      if (!ownerLifecycle) continue;
      if (element.isConnected) ownerLifecycle.connect();
      else ownerLifecycle.disconnect();
    }
  });
  lifecycleObserver.observe(document.documentElement, {
    childList: true,
    subtree: true,
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
    requests: Object.fromEntries(
      Object.entries(reading.requests).map(([verb, entry]) => [
        verb,
        { ...entry, available: false },
      ]),
    ),
  });

const commandTarget = (target) =>
  typeof target === "string" && target ? target : null;

const undoCandidate = (reading, target) => {
  const wanted = commandTarget(target);
  if (!wanted) return null;
  return Object.values(reading.actions)
    .flatMap(({ undo }) => undo)
    .find((event) => event.attempt === wanted || event.id === wanted);
};

const plainObject = (value) =>
  value !== null && typeof value === "object" && !Array.isArray(value);

const exactKeys = (value, keys) =>
  plainObject(value) &&
  Object.keys(value).length === keys.length &&
  keys.every((key) => key in value);

const validTargetReference = (reference) => {
  if (reference?.kind === "id")
    return (
      exactKeys(reference, ["kind", "id"]) &&
      typeof reference.id === "string" &&
      Boolean(reference.id)
    );
  if (reference?.kind !== "structure") return false;
  const keys = "anchor" in reference ? ["kind", "anchor", "path"] : ["kind", "path"];
  return (
    exactKeys(reference, keys) &&
    (!("anchor" in reference) ||
      (typeof reference.anchor === "string" && Boolean(reference.anchor))) &&
    Array.isArray(reference.path) &&
    reference.path.every(
      (step) =>
        exactKeys(step, ["tree", "tag"]) &&
        ["light", "shadow"].includes(step.tree) &&
        typeof step.tag === "string" &&
        Boolean(step.tag),
    )
  );
};

function validateReferences(descriptor, command) {
  const channel = command.kind === "action" ? "x-state" : "x-request";
  const roles = Object.keys(
    descriptor.declaration[channel]?.[command.verb]?.references ?? {},
  ).sort();
  const supplied = "references" in command ? command.references : {};
  if (
    !exactKeys(supplied, roles) ||
    Object.values(supplied).some((reference) => !validTargetReference(reference))
  )
    throw new TypeError(
      `Widget ${command.kind} ${command.verb} references must match declared roles ${JSON.stringify(roles)}`,
    );
}

function createWidgetController(owner) {
  if (!(owner instanceof Element))
    throw new TypeError("A widget controller needs an Element owner");
  const descriptor = widgetDescriptor(owner);
  if (!descriptor)
    throw new Error(
      `leaf: <${owner.localName}>#${owner.id || "(missing id)"} has no captured widget descriptor`,
    );
  const selected = applicationState.selectWidget(descriptor);
  const stateFacets = new Set(
    ["x-state", "x-report"].flatMap((channel) =>
      Object.values(descriptor.declaration[channel] ?? {}).map(({ facet }) => facet),
    ),
  );
  const orderedPosition = ["x-state", "x-report"].some((channel) =>
    Object.values(descriptor.declaration[channel] ?? {}).some(
      (spec) => spec.unit === "widget" && spec.record?.kind === "position",
    ),
  );
  const subscriptions = new Set();
  let deferred = false;
  let deferredReading = null;
  let deferredHold = null;
  let stopSelection = null;
  let renderHandle = null;
  let renderedReading = null;
  let renderedStatus = null;
  let preparationHandle = null;
  let preparation = null;
  let preparationBatch = null;
  let connectedParent = null;

  const read = () =>
    descriptorStillMatches(owner, descriptor)
      ? selected.read()
      : unavailable(selected.read());

  const render = () => {
    if (!renderHandle && owner.isConnected)
      renderHandle = attachWidgetPresentation(descriptor.id, "render", owner);
    return renderHandle;
  };

  const prepared = () => {
    if (!preparationHandle && owner.isConnected)
      preparationHandle = attachWidgetPresentation(descriptor.id, "preparation", owner);
    return preparationHandle;
  };

  const presentPreparation = (handle, value, completion) =>
    handle.present(value, completion, (reason) => failSoft(owner, reason));

  const presentRender = (reading, callbacks) => {
    const firstRender = renderedReading !== reading;
    if (firstRender) {
      renderedReading = reading;
      renderedStatus = null;
    } else if (renderedStatus !== "complete") {
      return;
    }
    const handle = render();
    const failures = [];
    const complete = [...stateFacets].every((facet) => facet in reading.state);
    if (complete && firstRender) {
      try {
        owner.renderState?.(reading.state);
      } catch (error) {
        failures.push(
          new Error(
            `<${owner.localName}> renderState threw: ${error?.message ?? error}`,
            { cause: error },
          ),
        );
      }
      try {
        renderSettlement(owner, reading.state);
      } catch (error) {
        failures.push(error);
      }
      // Auxiliary subscribers may read DOM established by the total render. If that
      // prerequisite failed, the one fail-soft owns this reading instead of running
      // callbacks against a partial view.
    }
    if (complete && !failures.length) {
      for (const subscription of callbacks) {
        try {
          subscription(reading);
        } catch (error) {
          failures.push(error);
        }
      }
    }
    renderedStatus = !complete ? "incomplete" : failures.length ? "failed" : "complete";
    const failure =
      failures.length > 1
        ? new AggregateError(failures, "widget presentation failed")
        : failures[0];
    if (handle) {
      const completion = failure
        ? Promise.reject(failure)
        : complete && owner.updateComplete?.then
          ? owner.updateComplete
          : undefined;
      // An incomplete startup reading has no DOM to present, but its ticket still
      // commits so the provisional publication can settle. Its subscribers first run
      // when the publisher supplies every declared facet.
      void handle.present(reading, completion, (reason) => failSoft(owner, reason));
    }
  };

  const scheduleRender = (reading, callbacks) => {
    if (!orderedPosition) {
      presentRender(reading, callbacks);
      return;
    }
    const handle = render();
    if (!handle) {
      presentRender(reading, callbacks);
      return;
    }
    queueOrderedRender(descriptor.id, reading, handle, () => {
      if (owner.isConnected && stopSelection)
        presentRender(
          reading,
          callbacks.filter((callback) => subscriptions.has(callback)),
        );
    });
  };

  const holdRender = (reading) => {
    deferredReading = reading;
    const handle = render();
    if (!handle) return;
    let release;
    const completion = new Promise((resolve) => {
      release = resolve;
    });
    const prior = deferredHold;
    deferredHold = { release };
    void handle.present(reading, completion);
    // The newer ticket is installed before the old hold settles, so an obsolete value
    // cannot briefly acknowledge the current epoch between two deferred publications.
    prior?.release();
  };

  const publish = () => {
    const reading = read();
    if (deferred) {
      holdRender(reading);
      return;
    }
    scheduleRender(reading, [...subscriptions]);
  };

  const connect = () => {
    if (!owner.isConnected) return;
    if (subscriptions.size && !stopSelection) {
      const parentChanged = connectedParent !== owner.parentElement;
      connectedParent = owner.parentElement;
      render();
      stopSelection = selected.subscribe(publish);
      // A data renderer may remount a nested widget without changing its semantic
      // reading. Its own controller restores its facets; a parent controller may own
      // its placement, so refresh each mounted ancestor once for the new parent. The
      // remembered parent prevents the parent's corrective reparenting from looping.
      if (parentChanged && applicationState.read().document.authored.has(descriptor.id))
        refreshAncestorControllers(owner);
      // A controller can first appear when conversation presentation mounts frozen
      // markup after the global projection pass. Re-run coordinate/provenance work now
      // that this owner and its units exist; state application coalesces the request.
      invalidateDom();
    }
    if (preparation && !preparationHandle) {
      const handle = prepared();
      if (handle)
        void presentPreparation(handle, preparation.value, preparation.completion);
    }
  };

  const disconnect = () => {
    stopSelection?.();
    stopSelection = null;
    renderHandle?.disconnect();
    renderHandle = null;
    preparationHandle?.disconnect();
    preparationHandle = null;
    deferredHold?.release();
    deferredHold = null;
    deferredReading = null;
    renderedReading = null;
    renderedStatus = null;
  };

  const refresh = () => {
    if (!owner.isConnected || !stopSelection) return;
    renderedReading = null;
    renderedStatus = null;
    publish();
  };

  watchLifetime(owner, { connect, disconnect, refresh });

  return Object.freeze({
    read,
    subscribe(callback) {
      if (typeof callback !== "function")
        throw new TypeError("A widget subscription needs a callback");
      subscriptions.add(callback);
      if (!stopSelection) connect();
      else scheduleRender(read(), [callback]);
      return () => {
        subscriptions.delete(callback);
        if (!subscriptions.size) {
          stopSelection?.();
          stopSelection = null;
          renderHandle?.disconnect();
          renderHandle = null;
          deferredHold?.release();
          deferredHold = null;
          deferredReading = null;
          renderedReading = null;
          renderedStatus = null;
        }
      };
    },
    dispatch(command) {
      const semantic = ["action", "request"].includes(command?.kind);
      const undo = command?.kind === "undo";
      if (!semantic && !undo)
        throw new TypeError(
          "Widget dispatch needs an action, request, or exact undo command",
        );
      if (
        semantic &&
        (typeof command.verb !== "string" ||
          !command.verb ||
          command.detail === null ||
          typeof (command.detail ?? {}) !== "object")
      )
        throw new TypeError(
          "Widget action and request commands need {kind, verb, detail}",
        );
      if (semantic) validateReferences(descriptor, command);
      if (!descriptorStillMatches(owner, descriptor)) return null;
      const before = read();
      if (undo && !undoCandidate(before, command.target)) return null;
      if (
        semantic &&
        !(command.kind === "action"
          ? before.actions[command.verb]?.available
          : before.requests[command.verb]?.available)
      )
        return null;
      if (
        semantic &&
        Object.values(command.references ?? {}).some(
          (reference) => resolveWidgetReference(owner, reference).status !== "resolved",
        )
      )
        return null;
      const delivery = dispatchWidget(
        descriptor,
        undo ? { kind: "undo", target: commandTarget(command.target) } : command,
      );
      if (!delivery) return null;
      return immutable({ reading: read(), delivery });
    },
    reference(target) {
      return immutable(captureWidgetReference(owner, target));
    },
    defer() {
      if (deferred) throw new Error("Widget presentation is already deferred");
      deferred = true;
      // The gesture may mutate the live DOM without changing semantic identity. Resume
      // must therefore run the total renderer even when the publisher reading is the
      // same object that preceded the gesture.
      renderedReading = null;
      renderedStatus = null;
      let resumed = false;
      return () => {
        if (resumed) return read();
        resumed = true;
        deferred = false;
        const latest = deferredReading ?? read();
        const hold = deferredHold;
        deferredReading = null;
        deferredHold = null;
        if (subscriptions.size) scheduleRender(latest, [...subscriptions]);
        hold?.release();
        invalidateDom();
        return latest;
      };
    },
    present(promise) {
      if (!promise?.then) throw new TypeError("Widget presentation must be a promise");
      const value = read();
      if (!preparationBatch || preparationBatch.value !== value) {
        preparationBatch = { value, promises: [] };
      }
      preparationBatch.promises.push(promise);
      const batch = preparationBatch;
      const completion = Promise.all(batch.promises);
      batch.completion = completion;
      preparation = { value, completion };
      const handle = prepared();
      if (handle) void presentPreparation(handle, value, completion);
      const clear = () => {
        if (preparationBatch?.completion === completion) preparationBatch = null;
      };
      completion.then(clear, clear);
      // Package code may await the concrete renderer result (lf-diff does); the
      // coordinator's aggregate is mechanical bookkeeping, not a replacement value.
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
        ["read", "subscribe", "dispatch", "reference", "defer", "present"].map(
          (method) => [method, (...args) => resolve()[method](...args)],
        ),
      ),
    );
    controllers.set(owner, controller);
  }
  return controller;
}
