/* Event delivery. Pending records and application effects are supplied by the
   browser application owner; this module owns only POST, retry, and queue progress.

   Gestures go through one ordered queue: each waits for the one before it, and the
   reader is told when one cannot get through. A kind `$events` declares `bookkeeping`
   never enters that queue. It records what the reader has seen rather than something
   they did, so it is sent on its own, once, and a failure costs only a fact the page
   will observe again; it neither waits behind a gesture nor holds one up. */
import { postEvent } from "./layer-client.js";
import { notice } from "./notifications.js";
import { pendingTraffic } from "./traffic.js";
import { unresolvedAttempts } from "./pending/model.js";

export const RETRY_MS = 2000;
const retryPause = () => new Promise((resolve) => setTimeout(resolve, RETRY_MS));

export function createDelivery({
  ledger,
  currentReceipts,
  applyAcceptedState,
  settleRejected,
  settlementChanged,
  reportApplicationError,
}) {
  let draining = false;

  async function deliver(entry) {
    let announced = false;
    for (;;) {
      ledger.nameParent(entry, currentReceipts());
      if (!ledger.nameUndo(entry, currentReceipts())) return { accepted: null };
      const { event } = entry;
      if (entry.readEvent) return { accepted: entry.readEvent };
      const sent = await Promise.race([
        postEvent(event).then(
          (response) => ({ response }),
          (error) => ({ error }),
        ),
        entry.read.then((accepted) => ({ accepted })),
      ]);
      if (sent.accepted) return { accepted: sent.accepted };
      if (sent.error) {
        if (!announced) notice("Connection lost — retrying your change…");
        announced = true;
        await retryPause();
        continue;
      }
      if (!sent.response) return { accepted: null };
      // `503` is the server saying it cannot take this yet, which the website's edge
      // sends for the minutes a container image takes to reach a reader's allocation.
      // The loop already retries; what it reported without this was the failed decode
      // of a plain-text body rather than what the server said.
      if (sent.response.status === 503) {
        if (!announced) notice("The server isn't ready yet — retrying your change…");
        announced = true;
        await retryPause();
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
        if (!announced) notice("Couldn't read the answer — retrying your change…");
        announced = true;
        await retryPause();
        continue;
      }
      const answer = decoded.answer;
      const accepted = answer?.state?.browser?.receipts?.find(
        (candidate) => candidate.attempt === event.attempt,
      );
      if (sent.response.ok && answer?.ok === true && accepted) {
        const application = applyAcceptedState(answer.state).catch((error) =>
          console.error("leaf: state in event response", error),
        );
        return { accepted, application };
      }
      if (
        answer?.final === true &&
        (!("attempt" in answer) || answer.attempt === event.attempt) &&
        answer.ok === false
      ) {
        notice(`Couldn't send — ${answer.error || "the server refused it"}`);
        return { accepted: null };
      }
      if (!announced) notice("Server answer was incomplete — retrying your change…");
      announced = true;
      await retryPause();
    }
  }

  async function drain() {
    if (draining) return;
    draining = true;
    try {
      for (;;) {
        const entry = ledger.nextUnanswered();
        if (!entry) break;
        const { accepted, application } = await deliver(entry);
        if (accepted) ledger.accept(entry, accepted);
        else ledger.reject(entry);
        pendingTraffic(unresolvedAttempts(ledger.snapshot()));
        try {
          if (!accepted) {
            await settleRejected(entry);
          }
          settlementChanged(entry, accepted);
        } catch (error) {
          reportApplicationError(error);
        } finally {
          if (application) void application.finally(() => entry.resolve(accepted));
          else entry.resolve(accepted);
        }
      }
    } finally {
      draining = false;
    }
  }

  return { drain };
}

// Send one bookkeeping event and apply the state its answer carries. Resolves true once
// that state is applied, false when the server refused it or could not be reached.
export async function deliverBookkeeping(event, applyAcceptedState) {
  let response;
  try {
    response = await postEvent(event);
  } catch {
    return false;
  }
  if (!response?.ok) return false;
  let answer;
  try {
    answer = await response.json();
  } catch {
    return false;
  }
  if (answer?.ok !== true || !answer.state) return false;
  await applyAcceptedState(answer.state).catch((error) =>
    console.error("leaf: state in event response", error),
  );
  return true;
}
