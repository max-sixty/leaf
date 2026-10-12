/* Display wording for a Question's canonical answer. This is presentation only:
   membership, typed values and completion come from the application publication.
   A widget family formats answerWords(value, element); prose uses its typed text or token. */
import { closestAcross, elementById } from "../passages.js";
import { tagsDeclaring } from "../registry.js";

export function ownedQuestionControl(source, commandSource) {
  const selector = tagsDeclaring((entry) => entry["x-awaits"]).join(",");
  return !selector || closestAcross(commandSource, selector) === source;
}

export function questionWords(question) {
  if (question.answer === null) return "";
  if (question.source.kind === "approval") return "Approved";
  if (question.source.kind === "reply")
    return question.answer.value.text ?? question.answer.value.token ?? "";
  const source = elementById(question.source.id);
  const formatter = customElements.get(question.source.tag)?.answerWords;
  return String(source && formatter ? formatter(question.answer.value, source) : "")
    .replace(/\s+/g, " ")
    .trim();
}

/* How a finished ask ended, in the words a Done row and the floating panel show:
   its answer, an answer given elsewhere, or its withdrawal. */
export function questionEnding(question) {
  if (question.status === "withdrawn") return "Withdrawn";
  if (question.status === "answered_elsewhere") return "Answered elsewhere";
  return `Answered ${questionWords(question)}`.trim();
}
