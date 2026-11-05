/* Summary ranges over retained thread messages on every surface.

   The server names each active contiguous range with the exact message ids it covers.
   This module only places those ranges into message order and keeps disclosure
   mechanical. Original message nodes remain connected inside their range, so frozen
   authored widgets, direct arrivals, and focus identities keep their native lifetime.
   Pending progress is gathered the same way (`withPendingProgress`); completed
   progress is omitted from the presentation before ranges are built. The
   working message stands among the ranges where its words were said (`workingPlace`). */

/** @typedef {import("../../types/domain.js").Thread["summaries"][number] & {pending?: false}} Summary */
/** @typedef {{id: string, covers: readonly string[], pending: true, protected?: never, label?: never, text?: never}} PendingSummary */
/** @template M
 * @typedef {{kind: "message", message: M, summary?: never, messages?: never}
 * | {kind: "summary", summary: Summary | PendingSummary, messages: readonly [M, ...M[]], last: M, message?: never}} MessageRange
 */

/** @template {{id: string}} M
 * @param {readonly M[]} messages
 * @param {readonly Summary[]} summaries
 * @returns {readonly MessageRange<M>[]}
 */
export function summaryRanges(messages, summaries = []) {
  const index = new Map(messages.map((message, at) => [message.id, { message, at }]));
  /** @type {Map<number, {summary: Summary, messages: [M, ...M[]], last: M}>} */
  const byStart = new Map();
  const covered = new Set();
  for (const summary of summaries) {
    // Reaction replies may be absent from the visible turns. Resolve identities once,
    // keeping the originals shown in the same contiguous order as the server range.
    const visible = summary.covers.flatMap((id) => index.get(id) ?? []);
    const first = visible.at(0);
    if (!first) continue;
    let last = first.message;
    for (const { message } of visible) {
      covered.add(message.id);
      last = message;
    }
    byStart.set(first.at, {
      summary,
      messages: [first.message, ...visible.slice(1).map(({ message }) => message)],
      last,
    });
  }
  /** @type {MessageRange<M>[]} */
  const ranges = [];
  let skipThrough = -1;
  for (const [at, message] of messages.entries()) {
    if (at <= skipThrough) continue;
    const range = byStart.get(at);
    if (range) {
      ranges.push(
        Object.freeze({
          kind: "summary",
          summary: range.summary,
          messages: Object.freeze(range.messages),
          last: range.last,
        }),
      );
      skipThrough = at + range.messages.length - 1;
    } else if (!covered.has(message.id)) {
      ranges.push(Object.freeze({ kind: "message", message }));
    }
  }
  return Object.freeze(ranges);
}

// The ranges with each run of pending progress gathered into a range of its own. A
// progress message no summary covers is one no answer has completed
// (`events.progress_completions`). The thread draws each run
// as its face, its latest step, where it was said (transcript.js), and keeps its messages
// behind it. The range is named for its first message, so it keeps its identity, and
// its disclosure state, as the run grows.
/** @template {{id: string, progress?: boolean}} M
 * @param {readonly MessageRange<M>[]} ranges
 * @returns {readonly MessageRange<M>[]}
 */
export function withPendingProgress(ranges) {
  /** @type {MessageRange<M>[]} */
  const gathered = [];
  for (const range of ranges) {
    const run = gathered.at(-1);
    if (range.kind === "message" && range.message.progress) {
      if (run?.kind === "summary" && run.summary.pending) {
        /** @type {[M, ...M[]]} */
        const messages = [...run.messages, range.message];
        gathered[gathered.length - 1] = Object.freeze({
          kind: "summary",
          summary: Object.freeze({
            ...run.summary,
            covers: Object.freeze([...run.summary.covers, range.message.id]),
          }),
          messages: Object.freeze(messages),
          last: range.message,
        });
      } else {
        /** @type {[M]} */
        const messages = [range.message];
        gathered.push(
          Object.freeze({
            kind: "summary",
            summary: Object.freeze({
              id: `progress:${range.message.id}`,
              covers: Object.freeze([range.message.id]),
              pending: true,
            }),
            messages: Object.freeze(messages),
            last: range.message,
          }),
        );
      }
    } else gathered.push(range);
  }
  return Object.freeze(gathered);
}

// The work line keeps its original log position. A range stands before that line
// when it contains a message said before it; a summary keeps all its originals
// together even where the line falls inside its covered interval.
/** @template {{sequence: number}} M
 * @param {readonly MessageRange<M>[]} ranges @param {number} position */
export function workingPlace(ranges, position) {
  const at = ranges.findLastIndex((range) =>
    range.kind === "message"
      ? range.message.sequence <= position
      : range.messages.some((message) => message.sequence <= position),
  );
  if (at < 0)
    throw new Error(
      `The working message at ${position} precedes every transcript range`,
    );
  return at;
}
