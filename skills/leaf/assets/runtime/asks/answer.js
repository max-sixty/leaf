/* What an Ask was answered with, for every surface that names its answer: the Asks
   drawer's rows and a queue's rows (lf-tabs).

   Which Asks the page holds and whether each is answered are the admitted inventory's
   (`allAsks`, `unansweredAsks`), so both move when the state a gesture's POST returns
   is adopted; nothing here folds the widget's `x-awaits.answered` condition again. The
   inventory keeps an Ask the user answered after a later version settles it, so a
   region whose question is decided still reads as decided. The words are the owning
   widget's: the `answer` reader its command scope declares, over the widget's current
   state. An unanswered Ask has no answer to say, whatever its controls show. */
import { closestAcross, elementById } from "../passages.js";
import { tagsDeclaring } from "../registry.js";
import { commandScopesWithin } from "../keyboard/scopes.js";
import { under } from "../shadow.js";
import { whenWidgetsPresented } from "../semantic-state.js";
import { allAsks, unansweredAsks, watchAsks } from "./model.js";

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
function answerOf(source, ask) {
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

// Each Ask's answer: null while it is unanswered, else its widget's words for the
// answer ("" where the widget says none).
export function askAnswers(asks) {
  const unanswered = new Set(unansweredAsks().map(({ id }) => id));
  return asks.map((ask) => {
    if (unanswered.has(ask.id)) return null;
    const source = elementById(ask.sourceId);
    return source ? answerOf(source, ask) : "";
  });
}

const asksWithin = (root) =>
  allAsks().filter((ask) => {
    const source = elementById(ask.sourceId);
    return source && under(source, root);
  });

// The answers of the Asks whose source stands inside `root`, across declared shadow
// roots, in inventory order.
export const answersWithin = (root) => askAnswers(asksWithin(root));

// Calls `read` whenever the Ask reading changes, and again once the widgets answering
// the Asks inside `root` have presented it: a widget declares its answer reader as it
// renders, so a revision that rebuilds one has no words to give until then.
export function watchAnswers(owner, root, read) {
  return watchAsks(owner, () => {
    read();
    const sources = asksWithin(root).map((ask) => ask.sourceId);
    if (!sources.length) return;
    void whenWidgetsPresented(sources).then((outcome) => {
      if (outcome === "presented" && owner.isConnected) read();
    });
  });
}
