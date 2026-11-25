/* Summary ranges over retained thread messages on every surface.

   The server names each active contiguous range with the exact message ids it covers.
   This module only places those ranges into message order and keeps disclosure
   mechanical. Original message nodes remain connected inside their range, so the
   widgets in messages, direct arrivals, and focus identities keep their native lifetime.
   Progress stands in no range: the transcript draws a step as a face, and each face,
   the working message's included, stands among the ranges where its words were said
   (`workingPlace`). */

/** @typedef {import("../../../types/domain.js").Thread["summaries"][number]} Summary */
/** @template M
 * @typedef {{kind: "message", message: M, summary?: never, messages?: never}
 * | {kind: "summary", summary: Summary, messages: readonly [M, ...M[]], message?: never}} MessageRange
 */

/** @template {{id: string}} M
 * @param {readonly M[]} messages
 * @param {readonly Summary[]} summaries
 * @returns {readonly MessageRange<M>[]}
 */
export function summaryRanges(messages, summaries) {
  const index = new Map(messages.map((message, at) => [message.id, { message, at }]));
  /** @type {Map<number, {summary: Summary, messages: [M, ...M[]]}>} */
  const byStart = new Map();
  const covered = new Set();
  for (const summary of summaries) {
    // Reaction replies may be absent from the visible turns. Resolve identities once,
    // keeping the originals shown in the same contiguous order as the server range.
    const visible = summary.covers.flatMap((id) => index.get(id) ?? []);
    const first = visible.at(0);
    if (!first) continue;
    for (const { message } of visible) covered.add(message.id);
    byStart.set(first.at, {
      summary,
      messages: [first.message, ...visible.slice(1).map(({ message }) => message)],
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
        }),
      );
      skipThrough = at + range.messages.length - 1;
    } else if (!covered.has(message.id)) {
      ranges.push(Object.freeze({ kind: "message", message }));
    }
  }
  return Object.freeze(ranges);
}

// The range a face stands after, by its index, or -1 before every range. A face keeps
// its words' original log position. A range stands before that face when it contains a
// message said before it; a summary keeps all its originals together even where the face
// falls inside its covered interval.
/** @template {{sequence: number}} M
 * @param {readonly MessageRange<M>[]} ranges @param {number} position */
export function workingPlace(ranges, position) {
  return ranges.findLastIndex((range) =>
    range.kind === "message"
      ? range.message.sequence <= position
      : range.messages.some((message) => message.sequence <= position),
  );
}
