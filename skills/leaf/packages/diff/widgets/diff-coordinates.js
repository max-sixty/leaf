/* Diff owns durable datum identities and transient source locations.
 * File identities are [destinationPath, "file"]; changed lines are
 * [destinationPath, "old"|"new", line]; context lines retain the exact pair
 * [destinationPath, "both", oldLine, newLine]. Paired identities require both numbers.
 * Source links use [sourcePath, "source", "old"|"new", line]. A rename's old source
 * path names its preimage, even when that path also names another file's destination.
 * Source requests never enter the projection: commenting on their destination records
 * its durable datum identity. Either address matches only its named side's number.
 * Decoding validates the external key once; file and line lookup consume that reading. */
export const diffDatumKey = ({ path, file, side, oldLine, newLine }) =>
  JSON.stringify(
    file
      ? [path, "file"]
      : side === "both"
        ? [path, side, oldLine, newLine]
        : [path, side, side === "old" ? oldLine : newLine],
  );

export const diffLocationKey = (path, side, line) =>
  JSON.stringify([path, "source", side, line]);

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

export function findDiffFile(entries, coordinate) {
  if (!coordinate || !entries) return null;
  if (coordinate.source && coordinate.side === "old") {
    const renamed = entries.find(
      ({ record }) => record.previousPath === coordinate.path,
    );
    if (renamed) return renamed;
  }
  return (
    entries.find(
      ({ record }) =>
        (coordinate.source && coordinate.side === "old"
          ? (record.previousPath ?? record.path)
          : record.path) === coordinate.path,
    ) ?? null
  );
}

// File lookup has already chosen the source's owner; its lines carry destination paths.
export function findDiffLine(lines, coordinate) {
  return lines.find((line) =>
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
}
