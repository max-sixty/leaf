/* Diff owns durable datum identities and transient source locations.
 * File identities are [destinationPath, "file"]; changed lines are
 * [destinationPath, "old"|"new", line]; context lines retain the exact pair
 * [destinationPath, "both", oldLine, newLine]. Paired identities require both numbers.
 * Source links use [sourcePath, "source", "old"|"new", line]. A rename or copy's old source
 * path names its preimage. A rename owns that original identity; a copy shares it,
 * so copies and an edited original leave an old-source request ambiguous.
 * Source requests never enter the projection: commenting on their destination records
 * its durable datum identity. Either address matches only its named side's number.
 * Ambiguous addresses detach rather than choose a file by order. Decoding validates
 * the external key once; file and line lookup consume that reading. */
/** @param {DiffCoordinate} coordinate */
export const diffDatumKey = ({ path, file, side, oldLine, newLine }) =>
  JSON.stringify(
    file
      ? [path, "file"]
      : side === "both"
        ? [path, side, oldLine, newLine]
        : [path, side, side === "old" ? oldLine : newLine],
  );

/** @param {string} path @param {string} side @param {number} line */
export const diffLocationKey = (path, side, line) =>
  JSON.stringify([path, "source", side, line]);

/** @typedef {{path: string, file?: true, source?: true, side?: string, oldLine?: number, newLine?: number}} DiffCoordinate */

/** @param {string} key @returns {DiffCoordinate | null} */
export function readDiffCoordinate(key) {
  let parts;
  try {
    parts = JSON.parse(key);
  } catch {
    return null;
  }
  if (!Array.isArray(parts) || typeof parts[0] !== "string") return null;
  const [path, side, first, second] = parts;
  if (side === "file") return parts.length === 2 ? { path, file: true } : null;
  if (side === "source") {
    if (
      parts.length !== 4 ||
      !["old", "new"].includes(first) ||
      !Number.isInteger(second) ||
      second < 1
    )
      return null;
    return {
      path,
      source: true,
      side: first,
      ...(first === "old" ? { oldLine: second } : { newLine: second }),
    };
  }
  if (!Number.isInteger(first) || first < 1) return null;
  if (side === "both")
    return parts.length === 4 && Number.isInteger(second) && second > 0
      ? { path, side, oldLine: first, newLine: second }
      : null;
  if (parts.length !== 3) return null;
  if (side === "old") return { path, side, oldLine: first };
  if (side === "new") return { path, side, newLine: first };
  return null;
}

/**
 * @template {{record: {path: string, previousPath?: string | null, operation?: string}}} Entry
 * @param {Entry[] | null | undefined} entries
 * @param {DiffCoordinate | null} coordinate
 */
export function findDiffFile(entries, coordinate) {
  if (!coordinate || !entries) return null;
  if (coordinate.source && coordinate.side === "old") {
    const renamed = entries.filter(
      ({ record }) =>
        record.operation === "rename" && record.previousPath === coordinate.path,
    );
    const [first, extra] = renamed;
    if (first) return extra ? null : first;
  }
  const matching = entries.filter(
    ({ record }) =>
      (coordinate.source && coordinate.side === "old"
        ? (record.previousPath ?? record.path)
        : record.path) === coordinate.path,
  );
  const [first, extra] = matching;
  return first && !extra ? first : null;
}

// File lookup has already chosen the source's owner; its lines carry destination paths.
/** @template {{side: string, oldLine?: number | undefined, newLine?: number | undefined}} Line
 * @param {Line[]} lines @param {DiffCoordinate | null} coordinate */
export function findDiffLine(lines, coordinate) {
  if (!coordinate) return null;
  const matching = lines.filter((line) =>
    coordinate.side === "both"
      ? line.side === "both" &&
        line.oldLine === coordinate.oldLine &&
        line.newLine === coordinate.newLine
      : coordinate.side === "old"
        ? line.side !== "new" && line.oldLine === coordinate.oldLine
        : coordinate.side === "new" &&
          line.side !== "old" &&
          line.newLine === coordinate.newLine,
  );
  const [first, extra] = matching;
  return first && !extra ? first : null;
}
