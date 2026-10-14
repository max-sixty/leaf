/* Thread readers select the application root, independent of panel rendering. */
import { readPart } from "../semantic-state.js";

export const threadState = readPart((root) => root.effective.thread);
export const allThreads = () => threadState().all;
export const readThreads = readPart((root) => root.effective.thread.collection);
export const threadList = () => readThreads().threads;
