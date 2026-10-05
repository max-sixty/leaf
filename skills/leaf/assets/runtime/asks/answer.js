/* What an Ask was answered with, for every surface that names its answer: the Queue
   panel's Done rows and a queue's rows (lf-tabs).

   Which Asks the page holds and whether each is answered are the admitted inventory's
   (`allAsks`, `unansweredAsks`), so both move when the state a gesture's POST returns
   is adopted; nothing here folds the widget's `x-awaits.answered` condition again. The
   inventory keeps an Ask the user answered after a later version settles it, so a
   region whose question is decided still reads as decided.

   The words are the Ask's widget family's. The class its module defines for the
   Ask's tag declares `static answerWords(state, element)`, a function of the widget's
   state in the same publication as the inventory and of its authored markup, so the
   words are read synchronously with the Ask they describe: no reading waits for a
   widget to render, and a family has one way to say its answer. A family that declares
   none says "". An unanswered Ask has no answer to say, whatever its controls show. */
import { closestAcross, elementById } from "../passages.js";
import { tagsDeclaring } from "../registry.js";
import { selectWidgets } from "../semantic-state.js";
import { under } from "../shadow.js";
import { allAsks, unansweredAsks } from "./model.js";

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

// The words the Ask's widget family gives its current answer, or "" where it gives none.
function answerOf(ask, widgets) {
  const source = elementById(ask.sourceId);
  const state = widgets.get(ask.sourceId)?.state;
  const words = customElements.get(ask.sourceTag)?.answerWords;
  return source && state && words ? answerWords(words(state, source)) : "";
}

// Each Ask's answer: null while it is unanswered, else its widget's words for the
// answer ("" where the widget says none).
export function askAnswers(asks) {
  const unanswered = new Set(unansweredAsks().map(({ id }) => id));
  const widgets = selectWidgets();
  return asks.map((ask) => (unanswered.has(ask.id) ? null : answerOf(ask, widgets)));
}

// The answers of the Asks whose source stands inside `root`, across declared shadow
// roots, in inventory order. Interim: the inventory's "decided" reading behind it,
// which keeps an answered Ask a revision settled, is replaced by the forthcoming Tasks
// model.
export const answersWithin = (root) =>
  askAnswers(
    allAsks().filter((ask) => {
      const source = elementById(ask.sourceId);
      return source && under(source, root);
    }),
  );
