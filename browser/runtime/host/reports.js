/* The page's history as a widget reads it.

   `readHistory()` selects the server's history reading: `events`, the newest logged
   events, newest first, each already carrying its thread, whether it was undone, and
   a gesture's words as its own document had them, and the application's `phase`, so a
   widget never replaces a reading it retained with the empty one a page shows before
   it is `ready`. A worker's report is a row of kind
   `report`, naming its widget, with its words as `excerpt`; the report in force on a
   widget is its `state`. A LeafElement reads the history in render(), so Lit follows
   both its first reading and later publications. */
import { readPart } from "../state/semantic-state.js";

export const readHistory = readPart((root) => ({
  phase: root.phase,
  events: root.authoritative?.browser.history ?? [],
}));
