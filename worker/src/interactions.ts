/**
 * The edge's projection of a browser interaction batch into its log record.
 *
 * One schema both admits a batch and redacts it. A batch whose session or size
 * fails, or with an entry whose `ts`, `sequence`, or `type` fails, is refused
 * whole. Every other field is `kept` only when it is valid, and otherwise dropped,
 * so a record holds only structural fields: event type, time, sequence,
 * coordinates, element tags and positions, node ids, command ids, bindings, and
 * statuses. Authored ids and names, typed or selected text, URL details, and
 * unknown client fields never reach the log, and a sample's capability and
 * document identity are logged only as support handles.
 */

import * as z from "zod/mini";

import { sessionReference } from "./routing";

// A field the record keeps when it is valid; an invalid one is dropped without
// refusing its entry.
function kept<T extends z.ZodMiniType>(schema: T) {
  return z.catch(z.optional(schema), undefined);
}

// A field derived from the client's value, valid where the result passes `schema`.
function derived<O, T extends z.core.$ZodType<unknown, Awaited<O>>>(
  derive: (value: unknown) => O,
  schema: T,
) {
  return z.pipe(z.transform(derive), schema);
}

// The first `length` valid items of an array.
function validItems<T extends z.ZodMiniType>(item: T, length: number) {
  return z.pipe(z.array(z.unknown()), z.transform((values) => values.flatMap((value) => {
    const parsed = z.safeParse(item, value);
    return parsed.success ? [parsed.data] : [];
  }).slice(0, length)));
}

function safeLocator(value: unknown): string | null {
  if (typeof value !== "string") return null;
  // Client locators may embed authored ids and names. Keep only tag and structural
  // position; those identify page controls without copying arbitrary attribute text.
  const tag = /^([a-z][a-z0-9-]*)/.exec(value)?.[1];
  if (!tag) return null;
  const position = /:nth-of-type\(([1-9][0-9]{0,3})\)$/.exec(value)?.[1];
  return position ? `${tag}:nth-of-type(${position})` : tag;
}

export function sampleInteractionReference(page: unknown): string | null {
  if (typeof page !== "string" || page.length > 4096 ||
      !/^(?:\/api\/samples\/[a-f0-9]{32}(?:~[a-f0-9]{64})?)+$/.test(page)) return null;
  return sessionReference(page.split("/").at(-1)!.split("~")[0]);
}

const token = (length: number) =>
  z.string().check(z.regex(new RegExp(`^[a-z][a-z0-9_-]{0,${length - 1}}$`)));
const locator = derived(safeLocator, z.string());
const nodeId = z.int().check(z.positive());
const httpStatus = z.int().check(z.gte(100), z.lte(599));
const coordinates = z.tuple([z.number(), z.number()]);

const entryFields = {
  ts: z.string().check(z.regex(/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/)),
  sequence: z.int().check(z.positive()),
  type: token(100),
  trusted: kept(z.boolean()),
  target: kept(validItems(locator, 8)),
  nodes: kept(validItems(nodeId, 8)),
  control: kept(locator),
  controlNode: kept(nodeId),
  id: kept(z.string().check(z.regex(/^[A-Za-z][A-Za-z0-9_.:-]{0,127}$/))),
  binding: kept(z.string().check(z.regex(
    /^(?:(?:Mod|Alt|Shift|Control|Meta)\+){0,3}(?:[A-Za-z0-9]|Enter|Escape|Tab|Backspace|Delete|Arrow(?:Up|Down|Left|Right)|Home|End|PageUp|PageDown|Space|[?\/.,])$/,
  ))),
  originalType: kept(token(100)),
  kind: kept(token(64)),
  status: kept(httpStatus),
  key: kept(z.enum([
    "Alt", "Backspace", "Control", "Delete", "End", "Enter", "Escape", "Home",
    "Meta", "PageDown", "PageUp", "Shift", "Tab", "ArrowDown", "ArrowLeft",
    "ArrowRight", "ArrowUp",
  ])),
  repeat: kept(z.boolean()),
  modifiers: kept(validItems(z.enum(["Alt", "Control", "Meta", "Shift"]), 4)),
  pointer: kept(z.object({
    id: kept(z.number()),
    button: kept(z.number()),
    buttons: kept(z.number()),
    x: kept(z.number()),
    y: kept(z.number()),
    type: kept(z.enum(["mouse", "pen", "touch"])),
  })),
  scroll: kept(coordinates),
  viewport: kept(coordinates),
  delta: kept(z.tuple([z.number(), z.number(), z.number()])),
  checked: kept(z.boolean()),
  open: kept(z.boolean()),
  visibility: kept(z.enum(["visible", "hidden"])),
  fullscreen: kept(z.nullable(z.object({ target: locator, node: nodeId }))),
  partOf: kept(z.number()),
  part: kept(z.number()),
  parts: kept(z.number()),
  durationMs: kept(z.number()),
  responseStatus: kept(z.number()),
  transferSize: kept(z.number()),
};

const sampleFields = {
  phase: kept(token(64)),
  reason: kept(token(64)),
  operation: kept(token(64)),
  host: kept(nodeId),
  revision: kept(nodeId),
  allocation: kept(z.int().check(z.nonnegative())),
  elapsed: kept(z.number().check(z.nonnegative())),
  // A sample's canonical page identity contains its native-request credential.
  // Use the same support-handle projection as cookies; never log the credential,
  // its routing suffix, or arbitrary authored template ids.
  sample: kept(z.nullable(derived(sampleInteractionReference, z.string()))),
  document: kept(z.nullable(z.pipe(
    z.string().check(z.regex(/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/)),
    z.transform((document) => sessionReference(document.replaceAll("-", ""))),
  ))),
  leafDocument: kept(z.nullable(z.pipe(
    z.pipe(z.string().check(z.regex(/^[1-9][0-9]{0,15}$/)), z.transform(Number)),
    nodeId,
  ))),
  reloading: kept(z.boolean()),
  error: kept(z.object({
    name: kept(z.string().check(z.regex(/^[A-Z][A-Za-z0-9]{0,63}$/))),
    status: kept(httpStatus),
  })),
};

// The record names a sample's projected identities as references.
const RENAMED: Record<string, string> = { sample: "sampleReference", document: "documentReference" };

// zod leaves a dropped field as an undefined value, and an object whose every
// field was dropped as `{}`; the record keeps neither.
function compact(value: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(value).flatMap(([key, field]) => {
    if (field === undefined) return [];
    if (field === null || typeof field !== "object" || Array.isArray(field))
      return [[RENAMED[key] ?? key, field]];
    const nested = compact(field as Record<string, unknown>);
    return Object.keys(nested).length ? [[RENAMED[key] ?? key, nested]] : [];
  }));
}

const entrySchema = z.union([
  z.object({ ...entryFields, type: z.literal("sample"), ...sampleFields }),
  z.object(entryFields),
]);
const interactionBatchSchema = z.strictObject({
  session: z.string().check(z.regex(/^[0-9a-f]{32}$/)),
  entries: z.array(
    z.pipe(entrySchema, z.transform((entry: z.output<typeof entrySchema>) => compact(entry))),
  ).check(z.minLength(1), z.maxLength(100)),
});

// The batch as the edge logs it, or null when the batch is refused.
export function projectInteractionBatch(
  value: unknown,
): { session: string; entries: Record<string, unknown>[] } | null {
  const parsed = interactionBatchSchema.safeParse(value);
  return parsed.success ? parsed.data : null;
}
