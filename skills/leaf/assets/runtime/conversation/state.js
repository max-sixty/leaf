/* The current conversation projection installed by panel reconciliation. */
import { conversational } from "./model.js";

let current = { all: [], listed: [] };

export const allThreads = () => current.all;
export const threadList = () => current.listed;

// Reconciliation is the sole writer. Keeping the complete fold here gives anchors,
// drawings, panel cards, and inline surfaces one reading of the same projection.
export function setThreads(next) {
  current = { all: next, listed: next.filter(conversational) };
}
