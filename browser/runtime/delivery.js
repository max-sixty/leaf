/* Event delivery. Pending records and application effects are supplied by the
   browser application owner; this module owns only POST, retry, and queue progress.

   Gestures go through one ordered queue: each waits for the one before it, and the
   user is told when one cannot get through. A kind `$events` declares `bookkeeping`
   never enters that queue. It records what the user has seen rather than something
   they did, so it is sent on its own, once, and a failure costs only a fact the page
   will observe again; it neither waits behind a gesture nor holds one up. */
import { runtime } from "./context.js";
import { completeData, postEvent, reportCarried } from "./layer-client.js";
import { afterScript } from "./rendering.js";
import { holdingError, raiseError } from "./errors.js";

const RETRY_MS = 2000;
const retryPause = () => new Promise((resolve) => setTimeout(resolve, RETRY_MS));

/** @typedef {import("../types/contract.js").ServedEventAnswer & {state?: import("./layer-client.js").StateAnswer}} EventAnswer */
// What an /api/event answer says, read the same way by both senders: accepted, with
// the state that shows the event, or refused for good (`final`, event_endpoint.py).
// An answer that is neither is incomplete.
/** @param {Response} response @param {EventAnswer} answer
 * @returns {answer is Extract<EventAnswer, { ok: true }>} */
const acceptedAnswer = (response, answer) =>
  response.ok && !!answer && "state" in answer && !("final" in answer);
/** @param {EventAnswer} answer @returns {answer is Extract<EventAnswer, { final: true }>} */
const refusedAnswer = (answer) => !!answer && "final" in answer;
/** @typedef {import("./layer-client.js").CompletedState} State
 * @typedef {import("./pending/state.js").DeliveryHandle} Entry
 * @typedef {import("../types/domain.js").Event} Event
 * @typedef {(state: State) => Promise<unknown>} ApplyState
 * @typedef {{accepted: Event | null, application?: Promise<unknown>, refusal?: string, state?: State}} DeliveryResult
 * @typedef {ReturnType<typeof import("./pending/state.js").createPendingLedger>} Ledger
 */
/** @param {ApplyState} apply @param {State} state */
const applyAnswerState = (apply, state) =>
  apply(state).catch((error) => reportCarried(error, "state in event response"));

/** @param {{ledger: Ledger, applyAcceptedState: ApplyState,
 * settleRejected: (entry: Entry, state: State | undefined) => Promise<ReturnType<Ledger["refuse"]>>,
 * settlementChanged: (entry: Entry, accepted: Event | null) => void,
 * refusedWords: typeof import("./drafts.js").keepRefusedWords}} dependencies */
export function createDelivery({
  ledger,
  applyAcceptedState,
  settleRejected,
  settlementChanged,
  refusedWords,
}) {
  let draining = false;

  /** @param {Entry} entry */
  async function deliver(entry) {
    // That the change is not through yet stands as an error while the tries go on,
    // and leaves when the change is through or refused.
    const retrying = holdingError();
    /** @param {string} message */
    const retry = async (message) => {
      retrying(message);
      await retryPause();
    };
    try {
      return await tries(entry, retry);
    } finally {
      retrying(null);
    }
  }

  /** @param {Entry} entry @param {(message: string) => Promise<void>} retry @returns {Promise<DeliveryResult>} */
  async function tries(entry, retry) {
    for (;;) {
      if (!ledger.nameEvents(entry)) return { accepted: null };
      const { event } = entry;
      if (entry.admitted) return { accepted: entry.admitted };
      const held = runtime.data;
      const sent = await Promise.race([
        postEvent(event, held).then(
          (response) => ({ response }),
          (error) => ({ error }),
        ),
        entry.read.then((accepted) => ({ accepted })),
      ]);
      if ("accepted" in sent) return { accepted: sent.accepted };
      if ("error" in sent) {
        // A refused key ends only when the user opens the link, so say that rather
        // than promising a retry that cannot succeed on its own.
        await retry(
          runtime.keyRefused
            ? "This tab lost access — open the link again in a new tab and this goes through"
            : "Lost the connection — keep this page open and this goes through",
        );
        continue;
      }
      if (!sent.response) return { accepted: null };
      // `503` is the server saying it cannot take this yet, which the website's edge
      // sends for the minutes a container image takes to reach a user's allocation.
      // The loop already retries; what it reported without this was the failed decode
      // of a plain-text body rather than what the server said.
      if (sent.response.status === 503) {
        await retry("Not through yet — trying again…");
        continue;
      }
      const decoded = await Promise.race([
        sent.response.json().then(
          (answer) => ({ answer }),
          (error) => ({ error }),
        ),
        entry.read.then((accepted) => ({ accepted })),
      ]);
      if ("accepted" in decoded) return { accepted: decoded.accepted };
      if ("error" in decoded) {
        await retry("Not through yet — trying again…");
        continue;
      }
      /** @type {EventAnswer} */
      const answer = decoded.answer;
      if (acceptedAnswer(sent.response, answer)) {
        // An accepted answer settles this gesture only once its state holds the receipt.
        const accepted = answer.state.browser?.receipts?.find(
          (candidate) => candidate.attempt === event.attempt,
        );
        if (accepted)
          return {
            accepted,
            application: applyAnswerState(
              applyAcceptedState,
              completeData(answer.state, held),
            ),
          };
      }
      if (
        refusedAnswer(answer) &&
        (!("attempt" in answer) || answer.attempt === event.attempt)
      ) {
        return {
          accepted: null,
          ...(answer.state ? { state: completeData(answer.state, held) } : {}),
          refusal: `Couldn't ${event.kind === "edit" ? "save the edit" : "take this"} — ${answer.error || "it was refused"}`,
        };
      }
      await retry("Not through yet — trying again…");
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
        // What the refusal took down with this gesture, such as a reply to its message.
        /** @type {ReturnType<Ledger["refuse"]>} */
        let dependents = [];
        try {
          if (!accepted) {
            dependents = await settleRejected(entry, state);
          }
          settlementChanged(entry, accepted);
        } catch (error) {
          reportCarried(error, "event settlement");
        } finally {
          if (application) void application.finally(() => entry.resolve(accepted));
          else {
            entry.resolve(accepted);
            // Answer listeners restore their draft and other rejected mechanical state.
            // Each sender registered them on its answer when it sent, so a reaction
            // registered now runs after every one of them (promise reactions run in
            // registration order): the error reads where the words of every refused
            // gesture ended up, and says so where that is out of view. It is presented
            // at that script's checkpoint, so its geometry reads the foreground the
            // user will see.
            if (refusal) {
              const refused = [
                { attempt: entry.event.attempt, answer: entry.answer },
                ...dependents,
              ];
              void Promise.all(refused.map(({ answer }) => answer)).then(() =>
                afterScript(() => {
                  const { said, field } = refusedWords(
                    refused.map(({ attempt }) => attempt),
                  );
                  raiseError(said ? `${refusal}. ${said}` : refusal, {
                    subject: field,
                  });
                }),
              );
            }
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
// `keepalive` lets a send made as the document goes away reach the server.
/** @param {import("../types/contract.js").BrowserCommand} event @param {ApplyState} applyState */
export async function deliverBookkeeping(
  event,
  applyState,
  { keepalive = false } = {},
) {
  const held = runtime.data;
  let response;
  try {
    response = await postEvent(event, held, { keepalive });
  } catch {
    return "unreached";
  }
  if (!response || response.status === 503) return "unreached";
  /** @type {EventAnswer} */
  let answer;
  try {
    answer = await response.json();
  } catch {
    return "unreached";
  }
  if (answer && answer.state)
    await applyAnswerState(applyState, completeData(answer.state, held));
  return acceptedAnswer(response, answer)
    ? "accepted"
    : refusedAnswer(answer)
      ? "refused"
      : "unreached";
}
