// @ts-check
/* Widget command construction and the checked submission boundary. Presentation
   and collision notices belong to the composition root; its callbacks run after
   the ledger publishes the command synchronously. */
import { actionForWidget, isThreadEvent } from "./model.js";
import { createPendingLedger } from "./state.js";
import { applicationState, readApplication } from "../semantic-state.js";
import { newAttempt } from "../drafts.js";
import { saidNow } from "../presence.js";
import { messageText } from "../thread/messages.js";

/** @typedef {import("../../../../../build/browser/domain.ts").PendingCommand} PendingCommand */
/** @typedef {import("../../../../../build/browser/domain.ts").Event} Event */
/** @typedef {import("../../../../../build/browser/application.ts").WidgetDescriptor} WidgetDescriptor */
/** @typedef {ReturnType<typeof import("../../../../../build/browser/application.ts").createSemanticApplication>} Application */
/** @typedef {ReturnType<ReturnType<Application["selectWidget"]>["read"]>["actions"][string]["undo"][number]} UndoCandidate */
/** @param {unknown} value @returns {value is Record<string, unknown>} */
const detailObject = (value) => value !== null && typeof value === "object";

/** The package API is dynamic. Narrow only its command envelope here; admission
 * owns each registry-declared detail schema. @param {unknown} command
 * @returns {{kind: "undo", target: string | null} | {kind: "action", verb: string, detail: Record<string, unknown>, attempt?: string}} */
function widgetCommand(command) {
  if (command === null || typeof command !== "object" || !("kind" in command))
    throw new TypeError("Widget dispatch needs an action or exact undo command");
  if (command.kind === "undo")
    return {
      kind: "undo",
      target:
        "target" in command && typeof command.target === "string"
          ? command.target
          : null,
    };
  if (command.kind !== "action")
    throw new TypeError("Widget dispatch needs an action or exact undo command");
  const detail =
    "detail" in command && command.detail !== undefined ? command.detail : {};
  if (
    !("verb" in command) ||
    typeof command.verb !== "string" ||
    !command.verb ||
    !detailObject(detail)
  )
    throw new TypeError("Widget action commands need {kind, verb, detail}");
  return {
    kind: "action",
    verb: command.verb,
    detail,
    ...("attempt" in command && typeof command.attempt === "string"
      ? { attempt: command.attempt }
      : {}),
  };
}

/** @typedef {{
 * afterEnqueue: (entry: import("./state.js").DeliveryHandle) => Promise<unknown>,
 * withdraw: (event: UndoCandidate) => Promise<Event | null> | null,
 * onCollision: (attempt: string | undefined) => void,
 * }} DispatchDependencies */
export function createCommandDispatch() {
  const ledger = createPendingLedger({
    newAttempt,
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
    return Object.freeze({ answer: entry.answer, presentation: afterEnqueue(entry) });
  };
  /** @param {PendingCommand} event */
  const post = (event) => startPost(event)?.answer ?? Promise.resolve(null);
  /** @param {WidgetDescriptor} descriptor @param {unknown} input */
  const dispatchWidget = (descriptor, input) => {
    const command = widgetCommand(input);
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
    if (revision === null || !reading.actions[command.verb]?.available) return null;
    return startPost(actionForWidget(descriptor, command, revision))?.answer ?? null;
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
