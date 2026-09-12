/* Reader action admission and undo, assembled over supplied application commands. */
import { runtime } from "../context.js";
import { notice } from "../notifications.js";
import { elementById, inChrome, settlementSlots } from "../passages.js";
import { paintKeys } from "../keyboard/scopes.js";
import { authoredStates } from "./authored.js";

const { registry } = runtime;

function canUndoAction(candidate) {
  const widget = elementById(candidate.event.widget);
  return Boolean(
    widget &&
    authoredStates().has(widget.id) &&
    (widget.renderState || settlementSlots()[widget.localName]),
  );
}

export function createProjectionCommands({ post, stateApplying, unaccountedGesture }) {
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

  const words = {
    resolve: "Reopened the thread",
    unresolve: "Resolved the thread again",
    action: "Took back your last change",
    done: "Took back your approval",
  };

  async function withdraw(event, { allowPending = false } = {}) {
    if (stateApplying() || (!allowPending && unaccountedGesture())) {
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
    if (stateApplying() || unaccountedGesture()) {
      notice("Wait for the current change to finish before undoing");
      return;
    }
    const event = undoable();
    if (event) await withdraw(event);
  }

  return {
    undoable,
    undoLast,
    withdraw,
  };
}
