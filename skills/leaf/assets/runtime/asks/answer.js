/* Display wording for an ask's canonical answer. This is presentation only:
   membership, typed values and completion come from the application publication.
   A widget family formats answerWords(value, element); prose uses its typed text or token. */
import { widgetWord } from "../addressable-names.js";
import { closestAcross, elementById } from "../passages.js";
import { tagsDeclaring } from "../registry.js";
import { askedInWords } from "./model.js";

export function ownedAskControl(source, commandSource) {
  const selector = tagsDeclaring((entry) => entry["x-awaits"]).join(",");
  return !selector || closestAcross(commandSource, selector) === source;
}

/* What a row or a walk calls an item on the user's list: a widget's own word, so
   lf-options reads Options; Approval for a version's sign-off. */
export function askWord(ask) {
  if (ask.source.kind === "approval") return "Approval";
  const word = widgetWord(ask.source.tag, elementById(ask.source.id));
  return word.charAt(0).toUpperCase() + word.slice(1);
}

export function askWords(ask) {
  if (ask.answer === null) return "";
  if (ask.source.kind === "approval") return "Approved";
  if (askedInWords(ask)) return ask.answer.value.text ?? ask.answer.value.token ?? "";
  const source = elementById(ask.source.id);
  const formatter =
    /** @type {{answerWords?: (value: unknown, element: Element) => unknown}} */ (
      customElements.get(ask.source.tag)
    )?.answerWords;
  return String(source && formatter ? formatter(ask.answer.value, source) : "")
    .replace(/\s+/g, " ")
    .trim();
}

/* How a finished ask ended, in the words a Done row and the floating panel show:
   its answer, after a colon so the two never read as one phrase, an answer given
   elsewhere, or its withdrawal. */
export function askEnding(ask) {
  if (ask.status === "withdrawn") return "Withdrawn";
  if (ask.status === "answered_elsewhere") return "Answered elsewhere";
  const words = askWords(ask);
  return words ? `Answered: ${words}` : "Answered";
}
