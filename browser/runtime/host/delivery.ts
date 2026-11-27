/* Event delivery. Pending records and application effects are supplied by the
   browser application owner; this module owns only POST, retry, and queue progress.

   Gestures go through one ordered queue: each waits for the one before it, and the
   user is told when one cannot get through. A kind `$events` declares `bookkeeping`
   never enters that queue. It records what the user has seen rather than something
   they did, so it is sent on its own, once, and a failure costs only a fact the page
   will observe again; it neither waits behind a gesture nor holds one up. */
import { runtime } from "../state/context.js";
import {
  completeState,
  heldReading,
  postEvent,
  reportCarried,
} from "../transport/layer-client.js";
import { afterScript } from "../base/rendering.js";
import { holdingError, raiseError } from "../transport/errors.js";
import type { Event } from "../../types/domain.js";
import type { BrowserCommand, ServedEventAnswer } from "../../types/contract.js";
import type { CompletedState, StateAnswer } from "../transport/layer-client.js";
import type { DeliveryHandle, createPendingLedger } from "../records/pending/state.js";
import type { keepRefusedWords } from "../records/drafts.js";

const RETRY_MS = 2000;
const retryPause = () => new Promise((resolve) => setTimeout(resolve, RETRY_MS));

type EventAnswer = ServedEventAnswer & { state?: StateAnswer };
// What an /api/event answer says, read the same way by both senders: accepted, with
// the state that shows the event, or refused for good (`final`, event_endpoint.py).
// An answer that is neither is incomplete.
const acceptedAnswer = (
  response: Response,
  answer: EventAnswer,
): answer is Extract<EventAnswer, { ok: true }> =>
  response.ok && "state" in answer && !("final" in answer);
const refusedAnswer = (
  answer: EventAnswer,
): answer is Extract<EventAnswer, { final: true }> => "final" in answer;
type State = CompletedState;
type Entry = DeliveryHandle;
type ApplyState = (state: State) => Promise<unknown>;
type DeliveryResult = {
  accepted: Event | null;
  application?: Promise<unknown>;
  refusal?: string;
  state?: State;
};
type Ledger = ReturnType<typeof createPendingLedger>;
const applyAnswerState = (apply: ApplyState, state: State) =>
  apply(state).catch((error) => reportCarried(error, "state in event response"));

export function createDelivery({
  ledger,
  applyAcceptedState,
  settleRejected,
  settlementChanged,
  refusedWords,
}: {
  ledger: Ledger;
  applyAcceptedState: ApplyState;
  settleRejected: (
    entry: Entry,
    state: State | undefined,
  ) => Promise<ReturnType<Ledger["refuse"]>>;
  settlementChanged: (entry: Entry, accepted: Event | null) => void;
  refusedWords: typeof keepRefusedWords;
}) {
  let draining = false;

  async function deliver(entry: Entry) {
    // That the change is not through yet stands as an error while the tries go on,
    // and leaves when the change is through or refused.
    const retrying = holdingError();
    const retry = async (message: string) => {
      retrying(message);
      await retryPause();
    };
    try {
      return await tries(entry, retry);
    } finally {
      retrying(null);
    }
  }

  async function tries(
    entry: Entry,
    retry: (message: string) => Promise<void>,
  ): Promise<DeliveryResult> {
    for (;;) {
      if (!ledger.nameEvents(entry)) return { accepted: null };
      const { event } = entry;
      if (entry.admitted) return { accepted: entry.admitted };
      const held = heldReading();
      const sent = await Promise.race([
        postEvent(event, held).then(
          (answered) => ({ answered }),
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
      if (!sent.answered) return { accepted: null };
      const { response, decoded } = sent.answered;
      // `503` is the server saying it cannot take this yet, as leaf.page's container
      // host does while no container is free for the page. The loop already retries;
      // what it reported without this was the failed decode of a plain-text body
      // rather than what the server said.
      if (response.status === 503 || "error" in decoded) {
        await retry("Not through yet — trying again…");
        continue;
      }
      const answer: EventAnswer = decoded.answer;
      if (acceptedAnswer(response, answer)) {
        // An accepted answer settles this gesture only once its state holds the receipt:
        // the logged event that carries its attempt.
        const state = completeState(answer.state, held);
        const accepted = state.events.findLast(
          (candidate) => candidate.attempt === event.attempt,
        );
        if (accepted)
          return {
            accepted,
            application: applyAnswerState(applyAcceptedState, state),
          };
      }
      if (
        refusedAnswer(answer) &&
        (!("attempt" in answer) || answer.attempt === event.attempt)
      ) {
        return {
          accepted: null,
          ...(answer.state ? { state: completeState(answer.state, held) } : {}),
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
        let dependents: ReturnType<Ledger["refuse"]> = [];
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
                  const { said, field, press } = refusedWords(
                    refused.map(({ attempt }) => attempt),
                  );
                  raiseError(said ? `${refusal}. ${said}` : refusal, {
                    subject: field,
                    press,
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
export async function deliverBookkeeping(
  event: BrowserCommand,
  applyState: ApplyState,
) {
  const held = heldReading();
  let answered;
  try {
    answered = await postEvent(event, held);
  } catch {
    return "unreached";
  }
  if (!answered || answered.response.status === 503 || "error" in answered.decoded)
    return "unreached";
  const { response } = answered;
  const answer: EventAnswer = answered.decoded.answer;
  if (answer.state)
    await applyAnswerState(applyState, completeState(answer.state, held));
  return acceptedAnswer(response, answer)
    ? "accepted"
    : refusedAnswer(answer)
      ? "refused"
      : "unreached";
}
