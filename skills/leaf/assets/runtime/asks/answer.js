/* What an Ask was answered with, for every surface that names its answer: the Asks
   drawer's rows and a queue's rows (lf-tabs).

   Whether an Ask is answered is the admitted inventory's (`unansweredAsks`), so it moves
   when the state a gesture's POST returns is adopted; nothing here folds the widget's
   `x-awaits.answered` condition again. The words are the owning widget's: the `answer`
   reader its command scope declares, over the widget's current state. An unanswered
   Ask has no answer to say, whatever its controls show. A widget holding no answer
   gives "", as an undo leaves it before the log reopens the Ask, so a surface that
   says the words can drop them in the turn the undo is sent. */
import { closestAcross, elementById } from "../passages.js";
import { tagsDeclaring } from "../registry.js";
import { commandScopesWithin } from "../keyboard/scopes.js";
import { unansweredAsks } from "./model.js";

// Whether a command declared inside an Ask's source belongs to that Ask rather than to
// another Ask nested in it.
export function ownedAskControl(source, commandSource) {
  const selector = tagsDeclaring((entry) => entry["x-awaits"]).join(",");
  return !selector || closestAcross(commandSource, selector) === source;
}

const answerWords = (value) =>
  String(value ?? "")
    .replace(/\s+/g, " ")
    .trim();

// The words the Ask's own widget gives its current answer, or "" where it gives none.
function answerOf(ask) {
  const source = elementById(ask.sourceId);
  if (!source) return "";
  const readers = [
    ...new Set(
      commandScopesWithin(source)
        .filter(
          ({ source: commandSource, answer }) =>
            answer && ownedAskControl(source, commandSource),
        )
        .map(({ answer }) => answer),
    ),
  ];
  if (readers.length > 1)
    throw new TypeError(`Ask ${ask.id} has more than one answer reader`);
  return answerWords(readers[0]?.());
}

// Each Ask's answer: null while it is unanswered, else its widget's words for the answer
// ("" where the widget says none).
export function askAnswers(asks) {
  const unanswered = new Set(unansweredAsks().map(({ id }) => id));
  return asks.map((ask) => (unanswered.has(ask.id) ? null : answerOf(ask)));
}
