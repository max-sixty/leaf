/* Served threads, workflows and activity, as `/api/state` sends them.

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

// A whole served reading, `{ threads, workflows }`, whose premise is the named case.
export function servedReading(name) {
  if (!Object.hasOwn(RECORDS.readings, name))
    throw new Error(`served_records.py folds no reading named ${name}`);
  return structuredClone(RECORDS.readings[name]);
}

// An ask as Questions lists it, holding `ask`; `changes` set where it stands, for a
// test whose served reading states its asks by hand.
export const servedAskItem = (ask, changes) =>
  served("ask_item", {
    id: ask.id,
    thread: ask.thread,
    title: ask.prompt.text,
    ask,
    ...changes,
  });

// The same admitted undo/refusal/revision sequence used by the Python fold test.
export const servedGestureSequence = () => structuredClone(RECORDS.gestures);

// Cross-runtime typed ask values use the same real server fold.
export const servedAskValues = () => structuredClone(RECORDS.ask_values);

// `state_definition_cases.json`'s pairs as the definitions Python records.
export const servedStateDefinitions = () => structuredClone(RECORDS.state_definitions);
