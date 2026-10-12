/* Mechanical placement of an ask in the current document, and the one rule for which
   asks a region of the page holds.

   The source owns its answer; the context supplies its prompt. A unique context is
   also its standing node. When several asks share that context each stands at
   its own source, so focus, rings, markers and arrival all name the same request.
   Frozen thread sources may have no node until the thread owner materializes them.
   Placement never changes the semantic inventory or its ask identities.

   A region holds an ask when the ask's source element is the region or stands under
   it (`asksIn`), shadow trees included. A withdrawn ask no longer asks anything, and an
   ask with no page node (a prose or approval ask, or a frozen source not drawn) stands
   in no region. Membership reads the complete inventory, answered asks included, and
   each consumer selects what it counts from the members: a tab row and `lf-tally`
   count every member and how many are answered, so an ask the user discussed and left
   with the agent still counts as undecided, while a goal's interventions (work.js) are
   the members whose next actor is the user, since only those stop work on the user.
   Which ask holds a node the user stands in is the converse question, standing rather
   than membership (`questionHolding`, standing-target.js), and it also falls back to an
   ask's unique context. */
import { elementById } from "../passages.js";
import { under } from "../shadow.js";
import { readQuestions } from "./model.js";

export function questionPlace(question, questions = readQuestions().all) {
  if (!question || question.source.kind !== "widget")
    return { source: null, context: null, node: null };
  const source = elementById(question.source.id);
  const context = elementById(question.prompt.target);
  const shared = questions.some(
    (other) =>
      other.id !== question.id &&
      other.source.kind === "widget" &&
      other.prompt.target === question.prompt.target,
  );
  return { source, context, node: shared ? source : context };
}

// The asks `region` holds, in the order `asks` lists them.
export function asksIn(region, asks = readQuestions().all) {
  return asks.filter((ask) => {
    if (ask.source.kind !== "widget" || ask.status === "withdrawn") return false;
    const source = elementById(ask.source.id);
    return Boolean(source && under(source, region));
  });
}
