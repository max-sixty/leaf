/* Reader action admission and undo, assembled over supplied application commands. */
import {
  answeredContext,
  askEntry,
  isAwaiting,
  projectedParent,
} from "../asks/model.js";
import { runtime } from "../context.js";
import { notice } from "../notifications.js";
import { elementById, inChrome, settlementSlots } from "../passages.js";
import { quoted } from "../widget-elements.js";
import { stateSpecs } from "../registry.js";
import { paintKeys } from "../keyboard/scopes.js";
import { authoredFacet, authoredStates, stateCoordinate, unitOf } from "./authored.js";
import { currentProjection } from "./state.js";

const { registry } = runtime;

const projectedFacet = (widget, spec, winners = currentProjection().desired) => {
  const coordinate = stateCoordinate(widget.id, widget.id, spec);
  const winner = winners.get(coordinate);
  return winner ? winner.value : authoredFacet(coordinate);
};

function requirementTarget(widget, target, context) {
  if (target === "self") return widget;
  const owners = registry[widget.localName]["x-owners"] ?? [];
  for (
    let node = projectedParent(widget, context);
    node;
    node = projectedParent(node, context)
  )
    if (registry[node.localName])
      return owners.includes(node.localName) && askEntry(node) ? node : null;
  return null;
}

export function requirementMatches(widget, spec) {
  const requirement = spec.requires;
  const context = answeredContext();
  const target = requirementTarget(widget, requirement.target, context);
  return Boolean(target && isAwaiting(target, context) === requirement.awaiting);
}

function actionMatches(widget, action) {
  const spec = registry[widget.localName]?.["x-state"]?.[action];
  return Boolean(spec && (!spec.requires || requirementMatches(widget, spec)));
}

function canUndoAction(candidate) {
  const widget = elementById(candidate.event.widget);
  return Boolean(
    widget &&
    authoredStates.has(widget.id) &&
    (widget.renderState || settlementSlots()[widget.localName]),
  );
}

export function createProjectionCommands({ post, stateApplying, unaccountedGesture }) {
  const actionAvailable = (widget, action) =>
    runtime.statePhase !== "waiting" &&
    !quoted(widget) &&
    actionMatches(widget, action);

  async function sendAction(widget, action, detail, { attempt } = {}) {
    if (quoted(widget)) {
      console.error(
        `leaf: <${widget.localName}> is exhibited (x-exhibit); action ${action} refused`,
      );
      return null;
    }
    if (!actionAvailable(widget, action)) return null;
    return post({
      kind: "action",
      revision: runtime.currentRevision,
      widget: widget.id,
      action,
      detail,
      ...(attempt && { attempt }),
    });
  }

  function actionStands(event) {
    if (!(runtime.browser?.receipts ?? []).some((receipt) => receipt.id === event.id))
      return true;
    const widget = elementById(event.widget);
    const spec = widget && registry[widget.localName]?.["x-state"]?.[event.action];
    if (!widget || !spec) return false;
    const unit = unitOf(event, spec);
    if (typeof unit !== "string") return false;
    return (
      currentProjection().actions.get(stateCoordinate(event.widget, unit, spec))?.e
        .id === event.id
    );
  }

  function undoable() {
    if (stateApplying()) return null;
    for (const candidate of runtime.view?.undo ?? []) {
      const event = candidate.event;
      if (event.kind === "resolve" || event.kind === "unresolve" || event.token)
        return event;
      if (
        event.kind === "done" &&
        event.revision === runtime.currentRevision &&
        event.version === runtime.currentStamp
      )
        return event;
      const widget = event.kind === "action" && elementById(event.widget);
      if (
        widget &&
        (inChrome(widget) || event.revision === runtime.currentRevision) &&
        canUndoAction(candidate)
      )
        return event;
    }
    return null;
  }

  function undoableAction(widget, action, unit = null) {
    if (stateApplying()) return null;
    const candidate = (runtime.view?.undo ?? []).find(({ event }) => {
      if (
        event.kind !== "action" ||
        event.widget !== widget.id ||
        event.action !== action ||
        (!inChrome(widget) && event.revision !== runtime.currentRevision)
      )
        return false;
      if (unit === null) return true;
      const spec = stateSpecs().find(
        ({ tag, channel, verb }) =>
          tag === widget.localName && channel === "x-state" && verb === action,
      )?.spec;
      return spec && unitOf(event, spec) === unit;
    });
    return candidate && canUndoAction(candidate) ? candidate.event : null;
  }

  const words = {
    resolve: "Reopened the thread",
    unresolve: "Resolved the thread again",
    action: "Took back your last change",
    done: "Took back your approval",
  };

  async function withdraw(event) {
    if (stateApplying() || unaccountedGesture()) {
      notice("Wait for the current change to finish before undoing");
      return null;
    }
    runtime.undoing = true;
    paintKeys();
    try {
      const accepted = await post({ kind: "undo", undoes: event.id });
      if (accepted)
        notice(
          `${event.token ? `Took back your ${event.token}` : words[event.kind]} — sent`,
        );
      return accepted;
    } finally {
      runtime.undoing = false;
      paintKeys();
    }
  }

  async function undoLast() {
    const event = undoable();
    if (event) await withdraw(event);
  }

  return {
    actionAvailable,
    actionStands,
    projectedFacet,
    sendAction,
    undoable,
    undoableAction,
    undoLast,
    withdraw,
  };
}
