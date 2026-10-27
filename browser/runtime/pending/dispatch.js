// @ts-check
/* Widget command construction and the checked submission boundary. Presentation
   and collision notices belong to the composition root; its callbacks run after
   the ledger publishes the command synchronously. */
import { actionForWidget, isThreadEvent } from "./model.js";
import { createPendingLedger } from "./state.js";
import { applicationState, readApplication } from "../semantic-state.js";
import { randomId } from "../ids.js";
import { saidNow } from "../presence.js";
import { recordInteraction } from "../interaction-log.js";
import { messageText } from "../thread/messages.js";

/** @typedef {import("../../types/domain.js").PendingCommand} PendingCommand */
/** @typedef {import("../../types/domain.js").Event} Event */
/** @typedef {import("../framework/application.js").WidgetDescriptor} WidgetDescriptor */
/** @typedef {ReturnType<typeof import("../framework/application.js").createSemanticApplication>} Application */
/** @typedef {ReturnType<ReturnType<Application["selectWidget"]>["read"]>["actions"][string]["undo"][number]} UndoCandidate */
/** A package's command, as `widgetController(owner).dispatch` takes it. Admission
 * judges each registry-declared detail schema. An action's `says` names the gesture in
 * the widget's words: the one name Leaf acknowledges it by once the log admits it, and
 * names it by when the user undoes it.
 * @typedef {{kind: "undo", target: string} | {kind: "action", verb: string, detail?: Record<string, unknown>, attempt?: string, says?: string}} WidgetCommand */

/** @typedef {{
 * afterEnqueue: (entry: import("./state.js").DeliveryHandle) => void,
 * named: (entry: import("./state.js").DeliveryHandle, says: string) => void,
 * withdraw: (event: UndoCandidate) => Promise<Event | null> | null,
 * onCollision: (attempt: string | undefined) => void,
 * }} DispatchDependencies */
export function createCommandDispatch() {
  const submitted = new Set();
  const ledger = createPendingLedger({
    newAttempt: randomId,
    enqueue: (event) => {
      // Capture local Send before publication or a prior transport can delay it.
      // Retrying the same attempt does not begin another response-time interval.
      if (!submitted.has(event.attempt)) {
        submitted.add(event.attempt);
        recordInteraction("event_submit", { kind: event.kind, attempt: event.attempt });
      }
      return applicationState.enqueue(
        event,
        saidNow(),
        isThreadEvent(event) ? messageText(event) : undefined,
      );
    },
  });
  /** @type {DispatchDependencies | null} */
  let dependencies = null;
  const current = () => {
    if (!dependencies) throw new Error("Leaf application has not been mounted");
    return dependencies;
  };
  /** @param {PendingCommand} event */
  const startPost = (event) => {
    const { onCollision, afterEnqueue } = current();
    const entry = ledger.enqueue(event);
    if (!entry) {
      onCollision(event.attempt);
      return null;
    }
    afterEnqueue(entry);
    return entry;
  };
  /** @param {PendingCommand} event */
  const post = (event) => startPost(event)?.answer ?? Promise.resolve(null);
  /** @param {WidgetDescriptor} descriptor @param {WidgetCommand} command */
  const dispatchWidget = (descriptor, command) => {
    const { withdraw } = current();
    const reading = applicationState.selectWidget(descriptor).read();
    if (command.kind === "undo") {
      const candidate = Object.values(reading.actions)
        .flatMap(({ undo }) => undo)
        .find(
          (event) =>
            ("attempt" in event && event.attempt === command.target) ||
            event.id === command.target,
        );
      return candidate ? withdraw(candidate) : null;
    }
    const revision = readApplication().document.revision;
    if (revision === null) return null;
    // An adopted document lists every verb the user sends from this widget; any other,
    // a misspelling or an agent's verb, would otherwise be dropped without a word.
    const action = reading.actions[command.verb];
    if (!action)
      throw new Error(
        `<${descriptor.tag} id="${descriptor.id}"> cannot dispatch ${JSON.stringify(command.verb)}; its user verbs are: ${Object.keys(reading.actions).join(", ") || "none"}`,
      );
    if (!action.available) return null;
    const entry = startPost(actionForWidget(descriptor, command, revision));
    if (!entry) return null;
    if (command.says) current().named(entry, command.says);
    return entry.answer;
  };
  return Object.freeze({
    ledger,
    /** @param {DispatchDependencies} installed */
    mount(installed) {
      dependencies = installed;
    },
    post,
    dispatchWidget,
  });
}
