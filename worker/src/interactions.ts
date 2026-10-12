/**
 * The edge's projection of a browser interaction batch into its log record.
 *
 * A batch is validated whole, then each entry keeps only structural fields: event
 * type, time, sequence, coordinates, element tags and positions, node ids, command
 * ids, bindings, and statuses. Authored ids and names, typed or selected text, URL
 * details, and unknown client fields never reach the log, and a sample's capability
 * and document identity are logged only as support handles. `worker/README.md`,
 * "Browser diagnostics", lists the fields a record keeps.
 */

import * as z from "zod/mini";

import { sessionReference } from "./routing";

const interactionEntrySchema = z.record(z.string(), z.unknown()).check(
  z.refine(
    (entry) =>
      typeof entry.ts === "string" &&
      /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(entry.ts) &&
      typeof entry.sequence === "number" &&
      Number.isSafeInteger(entry.sequence) &&
      entry.sequence > 0 &&
      typeof entry.type === "string" &&
      /^[a-z][a-z0-9_-]{0,99}$/.test(entry.type),
  ),
);
const interactionBatchSchema = z.strictObject({
  session: z.string().check(z.regex(/^[0-9a-f]{32}$/)),
  entries: z.array(interactionEntrySchema).check(z.minLength(1), z.maxLength(100)),
});
const SAFE_KEYS = new Set([
  "Alt", "Backspace", "Control", "Delete", "End", "Enter", "Escape", "Home",
  "Meta", "PageDown", "PageUp", "Shift", "Tab", "ArrowDown", "ArrowLeft",
  "ArrowRight", "ArrowUp",
]);
const MODIFIERS = new Set(["Alt", "Control", "Meta", "Shift"]);

function safeLocator(value: unknown): string | null {
  if (typeof value !== "string") return null;
  // Client locators may embed authored ids and names. Keep only tag and structural
  // position; those identify page controls without copying arbitrary attribute text.
  const tag = /^([a-z][a-z0-9-]*)/.exec(value)?.[1];
  if (!tag) return null;
  const position = /:nth-of-type\(([1-9][0-9]{0,3})\)$/.exec(value)?.[1];
  return position ? `${tag}:nth-of-type(${position})` : tag;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function safeNodeId(value: unknown): number | null {
  return typeof value === "number" && Number.isSafeInteger(value) && value > 0 ? value : null;
}

function coordinatePair(value: unknown): number[] | null {
  if (!Array.isArray(value) || value.length !== 2) return null;
  const pair = value.map(finiteNumber);
  return pair.every((number) => number !== null) ? pair as number[] : null;
}

function httpStatus(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= 100 && value <= 599
    ? value : null;
}

export function sampleInteractionReference(page: unknown): string | null {
  if (typeof page !== "string" || page.length > 4096 ||
      !/^(?:\/api\/samples\/[a-f0-9]{32}(?:~[a-f0-9]{64})?)+$/.test(page)) return null;
  return sessionReference(page.split("/").at(-1)!.split("~")[0]);
}

function projectSampleEntry(entry: Record<string, unknown>): Record<string, unknown> {
  const projected: Record<string, unknown> = {};
  for (const field of ["phase", "reason", "operation"] as const)
    if (typeof entry[field] === "string" && /^[a-z][a-z0-9_-]{0,63}$/.test(entry[field]))
      projected[field] = entry[field];
  for (const field of ["host", "revision"] as const) {
    const value = safeNodeId(entry[field]);
    if (value !== null) projected[field] = value;
  }
  if (typeof entry.allocation === "number" && Number.isSafeInteger(entry.allocation) && entry.allocation >= 0)
    projected.allocation = entry.allocation;
  const elapsed = finiteNumber(entry.elapsed);
  if (elapsed !== null && elapsed >= 0) projected.elapsed = elapsed;
  // A sample's canonical page identity contains its native-request credential.
  // Use the same support-handle projection as cookies; never log the credential,
  // its routing suffix, or arbitrary authored template ids.
  const sample = sampleInteractionReference(entry.sample);
  if (sample !== null) projected.sampleReference = sample;
  else if (entry.sample === null) projected.sampleReference = null;
  if (typeof entry.document === "string" &&
      /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(entry.document))
    projected.documentReference = sessionReference(entry.document.replaceAll("-", ""));
  else if (entry.document === null) projected.documentReference = null;
  if (typeof entry.leafDocument === "string" && /^[1-9][0-9]{0,15}$/.test(entry.leafDocument)) {
    const revision = safeNodeId(Number(entry.leafDocument));
    if (revision !== null) projected.leafDocument = revision;
  } else if (entry.leafDocument === null) projected.leafDocument = null;
  if (typeof entry.reloading === "boolean") projected.reloading = entry.reloading;
  if (entry.error && typeof entry.error === "object" && !Array.isArray(entry.error)) {
    const value = entry.error as Record<string, unknown>;
    const error: Record<string, unknown> = {};
    if (typeof value.name === "string" && /^[A-Z][A-Za-z0-9]{0,63}$/.test(value.name))
      error.name = value.name;
    const status = httpStatus(value.status);
    if (status !== null) error.status = status;
    if (Object.keys(error).length) projected.error = error;
  }
  return projected;
}

function projectInteractionEntry(entry: Record<string, unknown>): Record<string, unknown> {
  const projected: Record<string, unknown> = {
    ts: entry.ts,
    sequence: entry.sequence,
    type: entry.type,
  };
  if (typeof entry.trusted === "boolean") projected.trusted = entry.trusted;
  if (Array.isArray(entry.target)) {
    projected.target = entry.target.slice(0, 8).map(safeLocator).filter(Boolean);
  }
  if (Array.isArray(entry.nodes))
    projected.nodes = entry.nodes.slice(0, 8).map(safeNodeId).filter((value) => value !== null);
  const control = safeLocator(entry.control);
  if (control) projected.control = control;
  const controlNode = safeNodeId(entry.controlNode);
  if (controlNode !== null) projected.controlNode = controlNode;
  if (typeof entry.id === "string" && /^[A-Za-z][A-Za-z0-9_.:-]{0,127}$/.test(entry.id))
    projected.id = entry.id;
  if (typeof entry.binding === "string" &&
      /^(?:(?:Mod|Alt|Shift|Control|Meta)\+){0,3}(?:[A-Za-z0-9]|Enter|Escape|Tab|Backspace|Delete|Arrow(?:Up|Down|Left|Right)|Home|End|PageUp|PageDown|Space|[?\/.,])$/.test(entry.binding))
    projected.binding = entry.binding;
  if (typeof entry.originalType === "string" && /^[a-z][a-z0-9_-]{0,99}$/.test(entry.originalType))
    projected.originalType = entry.originalType;
  if (typeof entry.kind === "string" && /^[a-z][a-z0-9_-]{0,63}$/.test(entry.kind))
    projected.kind = entry.kind;
  const status = httpStatus(entry.status);
  if (status !== null) projected.status = status;
  if (SAFE_KEYS.has(entry.key as string)) projected.key = entry.key;
  if (typeof entry.repeat === "boolean") projected.repeat = entry.repeat;
  if (Array.isArray(entry.modifiers)) {
    projected.modifiers = entry.modifiers.filter((value) => MODIFIERS.has(value)).slice(0, 4);
  }
  if (entry.pointer && typeof entry.pointer === "object" && !Array.isArray(entry.pointer)) {
    const input = entry.pointer as Record<string, unknown>;
    const pointer: Record<string, unknown> = {};
    for (const field of ["id", "button", "buttons", "x", "y"]) {
      const value = finiteNumber(input[field]);
      if (value !== null) pointer[field] = value;
    }
    if (["mouse", "pen", "touch"].includes(input.type as string)) pointer.type = input.type;
    if (Object.keys(pointer).length) projected.pointer = pointer;
  }
  for (const field of ["scroll", "viewport"] as const) {
    const pair = coordinatePair(entry[field]);
    if (pair) projected[field] = pair;
  }
  if (Array.isArray(entry.delta) && entry.delta.length === 3) {
    const delta = entry.delta.map(finiteNumber);
    if (delta.every((number) => number !== null)) projected.delta = delta;
  }
  if (typeof entry.checked === "boolean") projected.checked = entry.checked;
  if (typeof entry.open === "boolean") projected.open = entry.open;
  if (["visible", "hidden"].includes(entry.visibility as string))
    projected.visibility = entry.visibility;
  if (entry.fullscreen === null) projected.fullscreen = null;
  else if (entry.fullscreen && typeof entry.fullscreen === "object" && !Array.isArray(entry.fullscreen)) {
    const value = entry.fullscreen as Record<string, unknown>;
    const target = safeLocator(value.target);
    const node = safeNodeId(value.node);
    if (target && node !== null) projected.fullscreen = { target, node };
  }
  for (const field of ["partOf", "part", "parts", "durationMs", "responseStatus", "transferSize"] as const) {
    const value = finiteNumber(entry[field]);
    if (value !== null) projected[field] = value;
  }
  if (entry.type === "sample") Object.assign(projected, projectSampleEntry(entry));
  return projected;
}

// The batch as the edge logs it, or null when it fails the batch schema.
export function projectInteractionBatch(
  value: unknown,
): { session: string; entries: Record<string, unknown>[] } | null {
  const parsed = interactionBatchSchema.safeParse(value);
  if (!parsed.success) return null;
  return {
    session: parsed.data.session,
    entries: parsed.data.entries.map(projectInteractionEntry),
  };
}
