/* Event delivery. Pending records and application effects are supplied by the
   browser application owner; this module owns only POST, retry, and queue progress.

   Gestures go through one ordered queue: each waits for the one before it, and the
   user is told when one cannot get through. A kind `$events` declares `bookkeeping`
   never enters that queue. It records what the user has seen rather than something
   they did, so it is sent on its own, once, and a failure costs only a fact the page
   will observe again; it neither waits behind a gesture nor holds one up. */
import { runtime } from "./context.js";
import { postEvent } from "./layer-client.js";
import { notice } from "./notifications.js";
import { afterScript } from "./rendering.js";

const RETRY_MS = 2000;
const retryPause = () => new Promise((resolve) => setTimeout(resolve, RETRY_MS));

// What an /api/event answer says, read the same way by both senders: "accepted" when
// the server took the event and returned the state that shows it, "refused" when its
// refusal is final (event_endpoint.py), and otherwise "incomplete".
const readEventAnswer = (response, answer) =>
  response.ok && answer?.ok === true && answer.state
    ? "accepted"
    : answer?.final === true
      ? "refused"
      : "incomplete";
const applyAnswerState = (apply, state) =>
  apply(state).catch((error) => console.error("leaf: state in event response", error));

export function createDelivery({
  ledger,
  applyAcceptedState,
  settleRejected,
  settlementChanged,
  reportApplicationError,
}) {
  let draining = false;

  async function deliver(entry) {
    let announced = false;
    // Say once that the change is not through yet, then wait before the next try.
    const retry = async (message) => {
      if (!announced) notice(message);
      announced = true;
      await retryPause();
    };
    for (;;) {
      ledger.nameParent(entry);
      if (!ledger.nameUndo(entry)) return { accepted: null };
      const { event } = entry;
      if (entry.admitted) return { accepted: entry.admitted };
      const sent = await Promise.race([
        postEvent(event).then(
          (response) => ({ response }),
          (error) => ({ error }),
        ),
        entry.read.then((accepted) => ({ accepted })),
      ]);
      if (sent.accepted) return { accepted: sent.accepted };
      if (sent.error) {
        // A refused key ends only when the user opens the link, so say that rather
        // than promising a retry that cannot succeed on its own.
        await retry(
          runtime.keyRefused
            ? "Key refused — open Leaf's link in a new tab and your change will send"
            : "Connection lost — retrying your change…",
        );
        continue;
      }
      if (!sent.response) return { accepted: null };
      // `503` is the server saying it cannot take this yet, which the website's edge
      // sends for the minutes a container image takes to reach a user's allocation.
      // The loop already retries; what it reported without this was the failed decode
      // of a plain-text body rather than what the server said.
      if (sent.response.status === 503) {
        await retry("The server isn't ready yet — retrying your change…");
        continue;
      }
      const decoded = await Promise.race([
        sent.response.json().then(
          (answer) => ({ answer }),
          (error) => ({ error }),
        ),
        entry.read.then((accepted) => ({ accepted })),
      ]);
      if (decoded.accepted) return { accepted: decoded.accepted };
      if (decoded.error) {
        await retry("Couldn't read the answer — retrying your change…");
        continue;
      }
      const answer = decoded.answer;
      const reading = readEventAnswer(sent.response, answer);
      // An accepted answer settles this gesture only once its state holds the receipt.
      const accepted =
        reading === "accepted" &&
        answer.state.browser?.receipts?.find(
          (candidate) => candidate.attempt === event.attempt,
        );
      if (accepted)
        return {
          accepted,
          application: applyAnswerState(applyAcceptedState, answer.state),
        };
      if (
        reading === "refused" &&
        (!("attempt" in answer) || answer.attempt === event.attempt) &&
        answer.ok === false
      ) {
        return {
          accepted: null,
          state: answer.state,
          refusal: `Couldn't send — ${answer.error || "the server refused it"}`,
        };
      }
      await retry("Server answer was incomplete — retrying your change…");
    }
  }

  async function drain() {
    if (draining) return;
    draining = true;
    try {
      for (;;) {
        const entry = ledger.nextSending();
        if (!entry) break;
        const { accepted, application, refusal, state } = await deliver(entry);
        if (accepted) ledger.accept(entry, accepted);
        try {
          if (!accepted) {
            await settleRejected(entry, state);
          }
          settlementChanged(entry, accepted);
        } catch (error) {
          reportApplicationError(error);
        } finally {
          if (application) void application.finally(() => entry.resolve(accepted));
          else {
            entry.resolve(accepted);
            // Answer listeners restore their draft and other rejected mechanical state.
            // Present feedback at this script's checkpoint, after those listeners,
            // so its geometry reads the foreground the user will actually see.
            if (refusal) afterScript(() => notice(refusal));
          }
        }
      }
    } finally {
      draining = false;
    }
  }

  return { drain };
}

// Send one bookkeeping event and apply the state its answer carries. Resolves
// "accepted" once that state is applied, "refused" when the server's answer is final,
// and "unreached" when no complete answer came back, which a later send may still get.
export async function deliverBookkeeping(event, applyState) {
  let response;
  try {
    response = await postEvent(event);
  } catch {
    return "unreached";
  }
  if (!response || response.status === 503) return "unreached";
  let answer;
  try {
    answer = await response.json();
  } catch {
    return "unreached";
  }
  const reading = readEventAnswer(response, answer);
  if (answer?.state) await applyAnswerState(applyState, answer.state);
  return reading === "incomplete" ? "unreached" : reading;
}
