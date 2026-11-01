/* Thread readers select the application root, independent of panel rendering. */
import { readPart } from "../semantic-state.js";
import { threadNames } from "./model.js";

export const threadState = readPart((root) => root.effective.thread);
export const allThreads = () => threadState().all;
export const readThreads = readPart((root) => root.effective.thread.collection);
export const threadList = () => readThreads().threads;

// The thread a name names: its id, one of its messages' ids, or this tab's attempt at
// one (`threadNames`), indexed once for each publication's threads.
/** @type {WeakMap<ReturnType<typeof allThreads>, Map<string, ReturnType<typeof allThreads>[number]>>} */
const names = new WeakMap();
/** @param {string} name */
export function threadNamed(name) {
  const threads = allThreads();
  let index = names.get(threads);
  if (!index) names.set(threads, (index = threadNames(threads)));
  return index.get(name) ?? null;
}
// The logged id of the thread `name` names, else the name as given.
/** @param {string} name */
export const threadIdNamed = (name) => threadNamed(name)?.id ?? name;
