export { parsePatchFiles, parseDiffFromFile } from "@pierre/diffs";
// The patch of two texts, which `parseDiffFromFile` already draws on, for a diff that
// compares two texts as it compares any patch, and the text one hunk of it taken back
// leaves, for a diff's Revert.
export { structuredPatch, formatPatch, applyPatch, reversePatch } from "diff";
