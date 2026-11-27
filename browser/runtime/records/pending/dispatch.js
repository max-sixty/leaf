// Compiled from dispatch.ts by build/typescript.mjs; edit that file.
/* Widget command construction and the checked submission boundary. Presentation
   and collision notices belong to the composition root; its callbacks run after
   the ledger publishes the command synchronously.

   A widget's action, and an undo of one, carries what the widget says of its
   obligation as the gesture leaves its state (`awaits`). The ledger publishes the
   gesture first, so the widget's reading holds it, then asks the widget
   (`answered`, the composition root's), and the word joins the event before transport
   sends it. */
import { actionForWidget, isThreadEvent } from "../../state/pending/model.js";
import { createPendingLedger } from "./state.js";
import { applicationState, readApplication } from "../../state/semantic-state.js";
import { randomId } from "../../base/ids.js";
import { saidNow } from "../../state/presence.js";
import { writeLaunchesAgent } from "../../transport/layer-client.js";
import { recordInteraction } from "../../transport/interaction-log.js";
import { messageText } from "../thread/messages.js";

/** A widget's command, as its controller's `dispatch` takes it from the `lf-action` or
 * `lf-undo` the widget records with (`hearRecords`, host/widget-controller.js). Admission
 * judges each registry-declared detail schema. An action's `says` names the gesture in
 * the widget's words: the one name Leaf acknowledges it by once the log admits it, and
 * names it by when the user undoes it. */

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
        writeLaunchesAgent(),
      );
    },
  });
  let dependencies = null;
  const current = () => {
    if (!dependencies) throw new Error("Leaf application has not been mounted");
    return dependencies;
  };
  const startPost = (event) => {
    const { onCollision, afterEnqueue, answered } = current();
    const entry = ledger.enqueue(event);
    if (!entry) {
      onCollision(event.attempt);
      return null;
    }
    applicationState.answer(entry.event.attempt, answered);
    afterEnqueue(entry);
    return entry;
  };
  const post = (event) => startPost(event)?.answer ?? Promise.resolve(null);
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
    mount(installed) {
      dependencies = installed;
    },
    post,
    dispatchWidget,
  });
}
