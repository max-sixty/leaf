/* Thread readers select the application root, independent of panel rendering. */
import { readPart } from "../semantic-state.js";

export const threadState = readPart((root) => root.effective.thread);
export const allThreads = readPart((root) => root.effective.thread.all);
export const readThreads = readPart((root) => root.effective.thread.collection);
export const threadList = () => readThreads().threads;

// The thread a name names: its key, its id, one of its messages' ids, or this tab's
// attempt at one (`threadNames`), as the publisher indexed them when the threads
// arrived. A surface that lists only conversations also asks `discussed` of the answer.
/** @param {string} name */
export function threadNamed(name) {
  const { all, named } = threadState();
  const at = named.get(name);
  return at === undefined ? null : (all[at] ?? null);
}
// The logged id of the thread `name` names, else the name as given.
/** @param {string} name */
export const threadIdNamed = (name) => threadNamed(name)?.id ?? name;
