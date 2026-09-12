/* Conversation readers select the application root, independent of panel rendering. */
import { readApplication } from "../semantic-state.js";

export const conversationState = () => readApplication().effective.conversation;
export const allThreads = () => conversationState().all;
export const threadList = () => conversationState().listed;
