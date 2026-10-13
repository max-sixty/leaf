/* Summary ranges over retained thread messages on every surface.

   The server names each active contiguous range with the exact message ids it covers.
   This module only places those ranges into message order and keeps disclosure
   mechanical. Original message nodes remain connected inside their range, so frozen
   authored widgets, direct arrivals, and focus identities keep their native lifetime.
   Progress no answer has folded yet is gathered the same way (`withPendingProgress`),
   so when the answer's fold arrives its messages move from one range to the next. */

export function summaryRanges(messages, summaries = []) {
  const index = new Map(messages.map((message, at) => [message.id, at]));
  const byStart = new Map();
  const covered = new Set();

  for (const summary of summaries) {
    // The server's range is contiguous in message order, and reaction replies belong to
    // it though the visible turns omit them, so the originals still shown stay
    // contiguous around that intentional absence.
    const visible = summary.covers.filter((id) => index.has(id));
    if (!visible.length) continue;
    byStart.set(index.get(visible[0]), summary);
    for (const id of visible) covered.add(id);
  }

  const ranges = [];
  for (let at = 0; at < messages.length; at += 1) {
    const summary = byStart.get(at);
    if (summary) {
      ranges.push(
        Object.freeze({
          kind: "summary",
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
          message: messages[at],
        }),
      );
    }
  }
  return Object.freeze(ranges);
}

// The ranges with each run of pending progress gathered into a range of its own. A
// progress message no summary covers is one no answer has folded yet (the server folds
// completed progress, `events._ephemeral_ranges`), so it is a step of work still in hand:
// the thread draws it as its progress line, and keeps the messages behind that line's
// disclosure. The range is named for its first message, so it keeps its identity, and
// its disclosure state, as the run grows.
export function withPendingProgress(ranges) {
  const gathered = [];
  for (const range of ranges) {
    const progress = range.kind === "message" && range.message.progress;
    const run = gathered.at(-1);
    if (progress && run?.summary?.pending) {
      run.summary.covers.push(range.message.id);
      run.messages.push(range.message);
    } else if (progress)
      gathered.push({
        kind: "summary",
        summary: {
          id: `progress:${range.message.id}`,
          covers: [range.message.id],
          pending: true,
        },
        messages: [range.message],
      });
    else gathered.push(range);
  }
  return Object.freeze(
    gathered.map((range) =>
      range.summary?.pending
        ? Object.freeze({
            ...range,
            summary: Object.freeze({
              ...range.summary,
              covers: Object.freeze(range.summary.covers),
            }),
            messages: Object.freeze(range.messages),
          })
        : range,
    ),
  );
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
