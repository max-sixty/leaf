/* Agent reply arrivals in the accepted conversation.

   The first presented reading establishes history. Thereafter a reply's stable
   attempt or event id identifies it across repeated reads, edits, and local-to-server
   settlement. The tracker retains identities already observed even if a later
   reading omits them; a reappearing message is still the same arrival. */
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
        message.addressable === false ||
        message.failure
      )
        continue;
      const key = message.attempt ?? message.id;
      if (known.has(key)) continue;
      known.add(key);
      if (observed !== null)
        arrivals.push({ thread: thread.root.attempt ?? thread.root.id, message });
    }
  }
  return { observed: known, arrivals };
}

export function agentReplyNotice(arrivals) {
  if (arrivals.length === 1)
    return `${arrivals[0].message.agent || "Agent"} replied — open Threads`;
  const threads = new Set(arrivals.map((arrival) => arrival.thread)).size;
  return `${arrivals.length} replies in ${threads} ${threads === 1 ? "thread" : "threads"} — open Threads`;
}

export function combineAgentReplyArrivals(older, newer) {
  const byId = new Map(
    [...older, ...newer].map((arrival) => [
      arrival.message.attempt ?? arrival.message.id,
      arrival,
    ]),
  );
  return [...byId.values()];
}
