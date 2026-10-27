// @ts-check
/* Where on the page the agent is at work.

   The server says what the agent has in hand: each workflow `at_work` on an update the
   user handed over, and each to-do with a start running on it. Where that work stands
   on the page is what the update or to-do is about, which the annotation inventory
   already places: a thread's passage, the widget a user's action was on, the element a
   to-do names. While the agent is at work on one (`progressFace` reads "working"), that
   place carries `data-lf-at-work`, which marks.css draws as a bar in the margin beside
   it, so "on it" reads as a place on the page as a collaborator's cursor does.

   It claims no more than the server knows. The agent is at work on what the user said
   about this place, which is often a rewrite of it and sometimes only an answer; the
   bar says where the work is, not that the words beside it are changing. Work with no
   place on the page, such as a to-do on the whole page or a turn the agent spends on
   its own, marks nothing here and stays in the floating panel's status. When the work
   lands as a revision, the blocks it changed take the install's tint (version.js), and
   the bar leaves once the workflow is answered.

   The mark is the rendering of server state, written on every inventory pass and never
   read back. */
import { runtime } from "./context.js";
import { elementById } from "./passages.js";
import { progressFace } from "./thread/workflow.js";
import { keeps } from "./keeps.js";

const AT_WORK = "data-lf-at-work";

/** @param {{ watch: (watcher: (entries: readonly any[]) => void) => () => void, targetFor: (entry: any) => Element | null }} inventory */
export function createAtWork(inventory) {
  let marked = new Set();
  inventory.watch((entries) => {
    const places = new Set();
    for (const entry of entries)
      if (progressFace(entry.workflowReceipt) === "working") {
        const target = inventory.targetFor(entry);
        if (target) places.add(target);
      }
    for (const todo of runtime.todos)
      if (
        todo.owner === "agent" &&
        todo.state === "open" &&
        todo.running &&
        (todo.subject.kind === "widget" || todo.subject.kind === "element")
      ) {
        const target = elementById(todo.subject.id);
        if (target) places.add(target);
      }
    for (const place of marked) if (!places.has(place)) keeps(place, AT_WORK, null);
    for (const place of places) keeps(place, AT_WORK, "");
    marked = places;
  });
}
