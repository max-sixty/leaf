/* Conversation readers select the application root, independent of panel rendering. */
import { readApplication } from "../semantic-state.js";

export const allThreads = () => readApplication().effective.conversation.all;
export const threadList = () => readApplication().effective.conversation.listed;
