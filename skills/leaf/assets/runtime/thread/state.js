/* Thread readers select the application root, independent of panel rendering. */
import { readApplication } from "../semantic-state.js";

export const threadState = () => readApplication().effective.thread;
export const allThreads = () => threadState().all;
export const readThreads = () => threadState().collection;
export const threadList = () => readThreads().threads;
