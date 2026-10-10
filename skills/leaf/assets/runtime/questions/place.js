/* Mechanical placement of a Question in the current document.

   The source owns its answer; the context supplies its prompt. A unique context is
   also its standing node. When several Questions share that context each stands at
   its own source, so focus, rings, markers and arrival all name the same request.
   Frozen thread sources may have no node until the thread owner materializes them.
   Placement never changes the semantic inventory or its Question identities. */
import { elementById } from "../passages.js";
import { readQuestions } from "./model.js";

export function questionPlace(question, questions = readQuestions().all) {
  if (!question || question.source.kind !== "widget")
    return { source: null, context: null, node: null };
  const source = elementById(question.source.id);
  const context = elementById(question.prompt.target);
  const shared = questions.some((other) =>
    other.id !== question.id && other.source.kind === "widget" &&
    other.prompt.target === question.prompt.target);
  return { source, context, node: shared ? source : context };
}
