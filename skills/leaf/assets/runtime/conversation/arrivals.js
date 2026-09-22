/* Agent reply arrivals in the accepted conversation.

   The first presented reading establishes history. Thereafter a reply's stable
   attempt or event id identifies it across repeated reads, edits, and local-to-server
   settlement. The tracker retains identities already observed even if a later
   reading omits them; a reappearing message is still the same arrival. */
import { messageKey } from "./identity.js";
import { isAddressable, threadKey } from "./model.js";

export function agentReplyArrivals(observed, threads) {
  const known = new Set(observed ?? []);
  const arrivals = [];
  for (const thread of threads) {
    for (const message of thread.msgs) {
      // A streamed answer is a provisional turn, not a log event. A failure
      // receipt closes a host obligation, but is not a spoken answer.
      if (
        message.author !== "agent" ||
        message.kind !== "reply" ||
        !isAddressable(message) ||
        message.failure
      )
        continue;
      const key = messageKey(message);
      if (known.has(key)) continue;
      known.add(key);
      if (observed !== null)
        arrivals.push({ thread: threadKey(thread), message });
    }
  }
  return { observed: known, arrivals };
}

export function agentReplyNotice(arrivals) {
  if (arrivals.length === 1)
    return `${arrivals[0].message.agent || "Agent"} replied`;
  const threads = new Set(arrivals.map((arrival) => arrival.thread)).size;
  return `${arrivals.length} replies in ${threads} ${threads === 1 ? "thread" : "threads"}`;
}

export function combineAgentReplyArrivals(older, newer) {
  const byId = new Map(
    [...older, ...newer].map((arrival) => [messageKey(arrival.message), arrival]),
  );
  return [...byId.values()];
}
