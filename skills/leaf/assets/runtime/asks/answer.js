/* Display wording for an ask's canonical answer. This is presentation only:
   membership, typed values and completion come from the application publication.
   A widget family formats answerWords(value, element); prose uses its typed text or token. */
import { closestAcross, elementById } from "../passages.js";
import { tagsDeclaring } from "../registry.js";

export function ownedAskControl(source, commandSource) {
  const selector = tagsDeclaring((entry) => entry["x-awaits"]).join(",");
  return !selector || closestAcross(commandSource, selector) === source;
}

export function askWords(ask) {
  if (ask.answer === null) return "";
  if (ask.source.kind === "approval") return "Approved";
  if (ask.source.kind === "reply")
    return ask.answer.value.text ?? ask.answer.value.token ?? "";
  const source = elementById(ask.source.id);
  const formatter = customElements.get(ask.source.tag)?.answerWords;
  return String(source && formatter ? formatter(ask.answer.value, source) : "")
    .replace(/\s+/g, " ")
    .trim();
}

/* How a finished ask ended, in the words a Done row and the floating panel show:
   its answer, an answer given elsewhere, or its withdrawal. */
export function askEnding(ask) {
  if (ask.status === "withdrawn") return "Withdrawn";
  if (ask.status === "answered_elsewhere") return "Answered elsewhere";
  return `Answered ${askWords(ask)}`.trim();
}
