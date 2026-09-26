/* Panel-only summary ranges over retained thread messages.

   The server names each active contiguous range with the exact message ids it covers.
   This module only places those ranges into message order and keeps disclosure
   mechanical. Original message nodes remain connected inside their range, so frozen
   authored widgets, direct arrivals, and focus identities keep their native lifetime. */

export function summaryRanges(messages, summaries = []) {
  const index = new Map(messages.map((message, at) => [message.id, at]));
  const byStart = new Map();
  const covered = new Set();

  for (const summary of summaries) {
    // Reaction replies belong to the server's complete range but are already omitted
    // from the visible turns. Place the remaining originals around that intentional
    // absence rather than treating the canonical range as malformed.
    const visible = summary.covers?.filter((id) => index.has(id)) ?? [];
    const positions = visible.map((id) => index.get(id));
    if (
      !positions.length ||
      positions.some((at, offset) => at !== positions[0] + offset)
    )
      continue;
    byStart.set(positions[0], summary);
    for (const id of visible) covered.add(id);
  }

  const ranges = [];
  for (let at = 0; at < messages.length; at += 1) {
    const summary = byStart.get(at);
    if (summary) {
      ranges.push(
        Object.freeze({
          kind: "summary",
          key: `summary:${summary.id}`,
          summary,
          messages: Object.freeze(
            summary.covers
              .filter((id) => index.has(id))
              .map((id) => messages[index.get(id)]),
          ),
        }),
      );
      at += ranges.at(-1).messages.length - 1;
    } else if (!covered.has(messages[at].id)) {
      ranges.push(
        Object.freeze({
          kind: "message",
          key: `message:${messages[at].key}`,
          message: messages[at],
        }),
      );
    }
  }
  return Object.freeze(ranges);
}

// Where each run of unread messages starts ("new") and where the read message after one
// stands ("end"), keyed by message key, across the ranges as the panel shows them. A
// collapsed summary shows none of its messages, so a run does not continue across it.
export function unreadBoundaries(ranges) {
  const boundaries = new Map();
  let precedingUnread = false;
  for (const range of ranges) {
    if (range.kind === "summary" && !range.expanded) {
      precedingUnread = false;
      continue;
    }
    for (const message of range.kind === "message" ? [range.message] : range.messages) {
      if (message.unread && !precedingUnread) boundaries.set(message.key, "new");
      if (!message.unread && precedingUnread) boundaries.set(message.key, "end");
      precedingUnread = Boolean(message.unread);
    }
  }
  return boundaries;
}
