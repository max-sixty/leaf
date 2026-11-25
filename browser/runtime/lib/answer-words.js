// @ts-check
/* An obligation's answer in words fit to show, as On Me and a Done row say it: the
   words of a reply or reaction that answered it, else what its widget's class makes of
   the answer's value and the widget's element (`static answerWords(value, element)`,
   module-state.md, "Declared widget state"), else nothing. `element` is the widget's
   authored element, by default the one the page holds under the obligation's source
   id; Leaf's own callers pass the one a thread message holds too. */
import { labelWords } from "./words.js";

/** @param {import("../state/semantic-application.js").ObligationRecord} item
 * @param {Element | null} [element] */
export function answerWords(item, element = document.getElementById(item.source.id)) {
  if (item.answer === null) return "";
  if (item.source.kind === "message") {
    // A reply's or a reaction's answer (events.md).
    const { text, token } = /** @type {{text?: string, token?: string}} */ (
      item.answer.value
    );
    return text ?? token ?? "";
  }
  if (item.source.kind !== "widget") return "";
  const formatter = customElements.get(item.source.tag)?.answerWords;
  return labelWords(element && formatter ? formatter(item.answer.value, element) : "");
}
