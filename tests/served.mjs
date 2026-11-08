/* Served threads, workflows, activity and whole answers, as `/api/state` sends them.

   Each importing process reads what `tests/served_records.py` folds through the
   server, so it carries every field the server sends. A test changes only the
   fields its case is about. Naming a field the server does not send throws: a test cannot state
   a record the runtime would never be handed. */
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";

const RECORDS = JSON.parse(
  execFileSync("uv", ["run", "tests/served_records.py"], {
    cwd: fileURLToPath(new URL("..", import.meta.url)),
    encoding: "utf8",
  }),
);

function served(kind, changes) {
  const record = structuredClone(RECORDS[kind]);
  for (const field of Object.keys(changes))
    if (!Object.hasOwn(record, field))
      throw new Error(`The server sends no ${kind} field ${field}`);
  return { ...record, ...changes };
}

// A thread holding `msgs`, opened by the first of them: nobody's turn, nothing unread,
// until `changes` say otherwise.
export const servedThread = (msgs, changes = {}) =>
  served("thread", { id: msgs[0].id, root: msgs[0], msgs, ...changes });

// A workflow for a message the agent has not picked up yet.
export const servedWorkflow = (changes = {}) => served("workflow", changes);

// The activity of a page a live session holds, owing nothing; `counts` changes only
// the counts it names.
export function servedActivity({ counts = {}, ...changes } = {}) {
  const activity = served("activity", changes);
  for (const name of Object.keys(counts))
    if (!Object.hasOwn(activity.counts, name))
      throw new Error(`The server sends no activity count ${name}`);
  return { ...activity, counts: { ...activity.counts, ...counts } };
}

// The whole answer for a page with an empty log. An answer nests records, so
// `changes` reach into them: a record this answer sends with fields is changed
// field by field, and naming a field it lacks throws. Any other value is replaced:
// a list, a record sent empty (a map, such as `files`), or a null. Replacing a
// record or a list with a value of another kind throws. What a replaced list or
// map holds, and what replaces a null, go unchecked.
export const servedState = (changes = {}) =>
  nested(structuredClone(RECORDS.state), changes, "state");

const kind = (value) =>
  Array.isArray(value) ? "list" : value?.constructor === Object ? "record" : "value";
function nested(record, changes, path) {
  for (const [field, value] of Object.entries(changes)) {
    const at = `${path}.${field}`;
    if (!Object.hasOwn(record, field))
      throw new Error(`The server sends no ${path} field ${field}`);
    const held = record[field];
    if (kind(held) !== "value" && kind(value) !== kind(held))
      throw new Error(`The server sends ${at} as a ${kind(held)}`);
    record[field] =
      kind(held) === "record" && Object.keys(held).length > 0
        ? nested(held, value, at)
        : value;
  }
  return record;
}

// A whole served reading, `{ threads, workflows }`, whose premise is the named case.
export function servedReading(name) {
  if (!Object.hasOwn(RECORDS.readings, name))
    throw new Error(`served_records.py folds no reading named ${name}`);
  return structuredClone(RECORDS.readings[name]);
}

// The On Me row naming `obligation`; `changes` set where it stands, for a test whose served
// reading states its obligations by hand.
export const servedObligationRow = (item, changes) =>
  served("obligation_row", { id: item.id, thread: item.thread, ...changes });

// The same admitted undo/refusal/revision sequence used by the Python fold test.
export const servedGestureSequence = () => structuredClone(RECORDS.gestures);

// Answers that complete a reading the browser holds, `{name, held, tail, whole}`:
// that reading, the answer to a request naming it, and the whole answer.
export const servedTails = () => structuredClone(RECORDS.tails);

// Cross-runtime typed obligation values use the same real server fold.
export const servedObligationValues = () => structuredClone(RECORDS.obligation_values);

// `state_definition_cases.json`'s pairs as the definitions Python records.
export const servedStateDefinitions = () => structuredClone(RECORDS.state_definitions);
