/* The Leaf application this document mounted, for code that must reach it without
   loading it. `mountApplication` sets it once; a document Leaf doesn't serve never
   does. Effect UI widgets' services (widget-services.js) read it, so a widget there
   loads none of the application, and a call made on a Leaf page runs in the task of
   the input that asked rather than after a module load. */
import type {
  navigateToDatum,
  obligationActions,
  threadActions,
} from "./application.js";
import type { showHeldReadings } from "../records/thread/held-news.js";
import type { threadList } from "../records/thread/state.js";

export type MountedApplication = {
  navigateToDatum: typeof navigateToDatum;
  obligationActions: typeof obligationActions;
  threadActions: typeof threadActions;
  threadList: typeof threadList;
  showHeldReadings: typeof showHeldReadings;
};

let current: MountedApplication | null = null;

/** The mounted application, or null where none is. */
export const mounted = (): MountedApplication | null => current;

export const setMounted = (application: MountedApplication) => {
  current = application;
};
