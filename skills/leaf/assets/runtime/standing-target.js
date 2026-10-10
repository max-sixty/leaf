/* Where the user stands: the page node a focused node stands at, one reading every
   feature takes (glossary, Standing target).

   An ordinary node on the page stands at itself. So does a node inside any Question source in the inventory,
   answered or not, wherever it is drawn: a Question frozen into a reply is where a user
   working it is, never the page Question its thread is about. A presentation can stand at the
   source target it shows in authored flow or chrome, as its owner declares (`declareSide`): the margin for its
   cluster controls, the thread card, and a thread in the Threads panel; the Questions panel
   for its rows; the details shelf for the elements that name its notes. A side's answer
   drawn in the chrome itself, such as a margin control on a widget frozen into a reply,
   stands only where a Question holds it. Chrome no side
   claims — the banner, a drawer's own controls, the panel's list — stands nowhere, and a
   press made from it means the page whole.

   Each feature takes what it needs from that place by its own rule: the Question view the
   Question source or unique context holding it, `c` and `e` its semantic target, the walks its document
   position. The chrome stands over the page rather than in it and is appended after it,
   so a chrome node measured as a place would put the user behind every Question and thread
   there is; no reader measures from one that does not stand in a Question.

   Page walks share `walkOrigin`: focus, then the selection's end, then the first
   visible reading block. Every press reads the browser afresh; no walk remembers a
   destination to use as the user's current place. */
import { documentFocused } from "./keyboard/scopes.js";
import { inChrome } from "./passages.js";
import { readQuestions } from "./questions/model.js";
import { questionPlace } from "./questions/place.js";
import { hostIn, under } from "./shadow.js";
import { pageReadingBlock } from "./reading-place.js";

const sides = new Set();

// A presentation owner's reading of the source target one of its nodes shows, or null.
export function declareSide(bridge) {
  sides.add(bridge);
  return () => sides.delete(bridge);
}

// Source containment identifies the Question before its context does. A context
// shared by several sources cannot identify one of them on its own.
export function questionHolding(questions, node) {
  if (!node) return null;
  const places = questions
    .filter((question) => question.source.kind === "widget")
    .map((question) => ({ question, ...questionPlace(question, questions) }));
  const holds = (element) => element && (element === node || under(node, element));
  const source = places.findLast((place) => holds(place.source));
  if (source) return source.question;
  const contexts = places.filter((place) => holds(place.node));
  return contexts.length === 1 ? contexts[0].question : null;
}

// The source target a presentation node shows, by its owner's declaration, or null
// for a node no side claims.
export function sideOf(node) {
  for (const side of sides) {
    const place = side(node);
    if (place) return place;
  }
  return null;
}

export function placeOf(node) {
  const at = node?.nodeType === 1 ? node : node?.parentElement;
  if (!at || at === document.body) return null;
  // A Question is the user's current action wherever it is rendered. A source-linked
  // presentation may otherwise stand in authored flow as well as fixed chrome.
  if (questionHolding(readQuestions().all, at)) return at;
  for (const side of sides) {
    const place = side(at);
    if (place)
      return inChrome(place) && !questionHolding(readQuestions().all, place)
        ? null
        : place;
  }
  return inChrome(at) ? null : at;
}

// Where the user stands now: where focus stands, or else the end of the selection, a
// caret a click left included, since a click that placed one is the user saying where
// they are.
export const standingPlace = () =>
  placeOf(documentFocused()) ?? placeOf(getSelection()?.focusNode);

// A page walk still has an origin when focus and selection name no page place. Order
// is measured in the document's tree, where a shadow block stands at its host.
export const walkOrigin = () => hostIn(standingPlace() ?? pageReadingBlock(), document);

// The Question the user stands in, answered or not: where letting go lands, and the extent
// of what `c` counts as the element they stand at.
export function heldQuestion(node = documentFocused()) {
  const question = questionHolding(readQuestions().all, placeOf(node));
  return questionPlace(question).node;
}
