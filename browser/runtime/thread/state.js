/* Thread readers select the application root, independent of panel rendering. */
import { readPart } from "../semantic-state.js";

export const threadState = readPart((root) => root.effective.thread);
export const allThreads = readPart((root) => root.effective.thread.all);
export const readThreads = readPart((root) => root.effective.thread.collection);
export const threadList = () => readThreads().threads;
// Whether the `t` walk has anywhere to go, which a press, the walk's readiness and a
// Resolve's next step ask (thread/folding.js): the open threads' order is the walk's
// business, and sorting them for a count cost a sort of every thread per input.
export const anyOpenThread = () => threadList().some((thread) => !thread.resolved);
// What the open threads' list says while it holds none: that there are none once the
// server's reading is in, or that they can't be had while the server is offline.
// Threads' empty text and the `t` walk both say them.
export const NO_OPEN_THREADS = "No open threads";
export const THREADS_OFFLINE =
  "Current threads are unavailable while the server is offline";

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
