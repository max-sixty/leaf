// @ts-check
/* Widget command construction and the checked submission boundary. Presentation
   and collision notices belong to the composition root; its callbacks run after
   the ledger publishes the command synchronously. */
import { actionForWidget, isThreadEvent } from "./model.js";
import { createPendingLedger } from "./state.js";
import { applicationState } from "../semantic-state.js";
import { randomId } from "../ids.js";
import { saidNow } from "../presence.js";
import { messageText } from "../thread/messages.js";

/** @typedef {import("../../../../../build/browser/domain.ts").PendingCommand} PendingCommand */
/** @typedef {import("../../../../../build/browser/domain.ts").Event} Event */
/** @typedef {import("../../../../../build/browser/application.ts").WidgetDescriptor} WidgetDescriptor */
/** @typedef {ReturnType<typeof import("../../../../../build/browser/application.ts").createSemanticApplication>} Application */
/** @typedef {ReturnType<ReturnType<Application["selectWidget"]>["read"]>["actions"][string]["undo"][number]} UndoCandidate */
/** A package's command, as `widgetController(owner).dispatch` takes it. Admission
 * judges each registry-declared detail schema.
 * @typedef {{kind: "undo", target: string} | {kind: "action", verb: string, detail?: Record<string, unknown>, attempt?: string}} WidgetCommand */

/** @typedef {{
 * afterEnqueue: (entry: import("./state.js").DeliveryHandle) => void,
 * withdraw: (event: UndoCandidate) => Promise<Event | null> | null,
 * onCollision: (attempt: string | undefined) => void,
 * }} DispatchDependencies */
export function createCommandDispatch() {
  const ledger = createPendingLedger({
    newAttempt: randomId,
    enqueue: (event) =>
      applicationState.enqueue(
        event,
        saidNow(),
        isThreadEvent(event) ? messageText(event) : undefined,
      ),
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
    return entry.answer;
  };
  /** @param {PendingCommand} event */
  const post = (event) => startPost(event) ?? Promise.resolve(null);
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
    const revision = descriptor.document.revision;
    if (revision === null) return null;
    // An adopted document lists every verb the user sends from this widget; any other,
    // a misspelling or an agent's verb, would otherwise be dropped without a word.
    const action = reading.actions[command.verb];
    if (!action)
      throw new Error(
        `<${descriptor.tag} id="${descriptor.id}"> cannot dispatch ${JSON.stringify(command.verb)}; its user verbs are: ${Object.keys(reading.actions).join(", ") || "none"}`,
      );
    if (!action.available) return null;
    return startPost(actionForWidget(descriptor, command, revision));
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
