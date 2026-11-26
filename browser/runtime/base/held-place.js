/* A place the user stood, held as plain data so that it can be stored, carried and
   read back after the nodes it was read from have gone: the caret in a text field
   (dom/focus.js, `readCaret`), where a thread view was being read
   (records/thread/reply-landing.js, `readingIn`), and the working place the menu holds
   for a press (records/history.js, `readPlace`, `returnPlace`). */

/** @typedef {[start: number, end: number, direction?: "forward" | "backward" | "none"]} Caret
 * @typedef {{offset: number} & ({message: string} | {summary: string})} ThreadReading
 * @typedef {{focus: WeakRef<Element> | null, place: WeakRef<Element> | null,
 * caret: Caret | null, ends: [[WeakRef<Node>, number], [WeakRef<Node>, number]] | null,
 * thread: {id: string, reading: ThreadReading | null} | null}} WorkingPlace
 */
export {};
