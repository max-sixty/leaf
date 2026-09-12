/* The public semantic adapter for one captured widget owner.

   Leaf captures identity and declarations before upgrade. This controller exposes only
   immutable publisher selections and commands validated against the newest selection;
   the owner DOM is never a semantic store. Local editing may defer subscriber paint
   once, and asynchronous visible preparation joins the existing presentation queue
   through one seam until the epoch coordinator replaces that queue. */
import { applicationState } from "./semantic-state.js";
import { dispatchWidget, invalidateDom } from "./application.js";
import {
  descriptorStillMatches,
  widgetDescriptor,
} from "./widget-descriptors.js";
import { registerPresentation } from "./widget-upgrade.js";

const controllers = new WeakMap();

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
        { ...entry, available: false },
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
  typeof target === "string" ? target : target?.attempt ?? target?.id ?? null;

const undoCandidate = (reading, target) => {
  const wanted = commandTarget(target);
  if (!wanted) return null;
  return Object.values(reading.actions)
    .flatMap(({ undo }) => undo)
    .find((event) => event.attempt === wanted || event.id === wanted);
};

function createWidgetController(owner) {
  if (!(owner instanceof Element))
    throw new TypeError("A widget controller needs an Element owner");
  const descriptor = widgetDescriptor(owner);
  if (!descriptor)
    throw new Error(
      `leaf: <${owner.localName}>#${owner.id || "(missing id)"} has no captured widget descriptor`,
    );
  const selected = applicationState.selectWidget(descriptor);
  const subscriptions = new Set();
  let deferred = false;
  let stopSelection = null;

  const read = () =>
    descriptorStillMatches(owner, descriptor) ? selected.read() : unavailable(selected.read());

  const publish = () => {
    if (deferred) return;
    for (const subscription of [...subscriptions]) subscription(read());
  };

  return Object.freeze({
    read,
    subscribe(callback) {
      if (typeof callback !== "function")
        throw new TypeError("A widget subscription needs a callback");
      subscriptions.add(callback);
      if (!stopSelection) stopSelection = selected.subscribe(publish);
      else callback(read());
      return () => {
        subscriptions.delete(callback);
        if (!subscriptions.size) {
          stopSelection?.();
          stopSelection = null;
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
      const delivery = dispatchWidget(
        descriptor,
        undo ? { kind: "undo", target: commandTarget(command.target) } : command,
      );
      if (!delivery) return null;
      return immutable({ reading: read(), delivery });
    },
    defer() {
      if (deferred) throw new Error("Widget presentation is already deferred");
      deferred = true;
      let resumed = false;
      return () => {
        if (resumed) return read();
        resumed = true;
        deferred = false;
        for (const subscription of [...subscriptions]) subscription(read());
        invalidateDom();
        return read();
      };
    },
    present(promise) {
      return registerPresentation(Promise.resolve(promise));
    },
  });
}

export function widgetController(owner) {
  let controller = controllers.get(owner);
  if (!controller) {
    controller = createWidgetController(owner);
    controllers.set(owner, controller);
  }
  return controller;
}
