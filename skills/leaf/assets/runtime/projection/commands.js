/* Reader action admission and undo, assembled over supplied application commands. */
import { runtime } from "../context.js";
import { notice } from "../notifications.js";
import { elementById, inChrome } from "../passages.js";
import { widgetDescriptor } from "../widget-descriptors.js";
import { paintKeys } from "../keyboard/scopes.js";
import { pageCommand } from "../keyboard/register.js";
import { undoSentence } from "../reactions.js";
import { authoredStates } from "./authored.js";

function canUndoAction(candidate) {
  const widget = elementById(candidate.event.widget);
  return Boolean(
    widget &&
    authoredStates().has(widget.id) &&
    widgetDescriptor(widget)?.declaration["x-state"]?.[candidate.event.action],
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

  // The last thing the reader did to this page, put back. Its own key rather than the
  // platform's ⌘Z, which belongs to the box a reader is typing in and is taken by the
  // browser everywhere else: this is a page-level press like every other letter, and the
  // typing scope keeps it off a composer's words by claiming its letters. The word is
  // "undo" and never the verb it is about to state — `move` is one widget's word, and a
  // line that said it would be naming a member where the mechanism is what holds.
  pageCommand({
    id: "history.undo",
    keys: ["z"],
    does: () => undoSentence(undoable),
    line: "undo",
    // Dead while the page holds a gesture no log read accounts for, this one's own send
    // included: the walk would name the gesture *before* the one they just made and take
    // that back instead. The line drops the chip for as long as that is true rather than
    // promising a press that would undo the wrong thing.
    when: () => !unaccountedGesture() && Boolean(undoable()),
    run: (...args) => undoLast(...args),
  });

  return {
    undoable,
    undoLast,
    withdraw,
  };
}
