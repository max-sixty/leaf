/* Mechanical placement of an obligation in the current document, and the one rule for which
   obligations a region of the page holds.

   A widget's source owns its answer; the context supplies its prompt. A unique context
   is also its current node. When several obligations share that context each stands at
   its own source, so focus, rings, markers and arrival all name the same request.
   A record unit stands at its projected datum, even when it is the widget's only
   obligation; the owning widget still supplies its commands and answer formatter.
   Frozen thread sources may have no node until the thread owner materializes them.
   A to-do on the user stands at its subject, the element or widget it names, or at the
   page's head for a to-do on the page as a whole (`pageHead`), so its mark, ring and
   arrival are a widget obligation's. It has no source, since no element takes its
   answer: the user's Done ends it wherever they press it. A to-do on a thread, a
   question answered in words and an update stand nowhere on the page; their thread or
   widget owner draws them. Placement never changes the semantic inventory or its
   obligation identities.

   A region holds an obligation when the obligation's source element is the region or stands under
   it (`obligationsIn`), shadow trees included. A withdrawn obligation no longer asks anything, and
   an obligation with no source (a question answered in words, an update's, a to-do, or a
   frozen source not drawn) stands in no region, so a region counts what its widgets
   ask. Membership reads the complete
   inventory, answered obligations included, and each consumer selects what it counts from
   the members: a tab row and `lf-tally` count every member, how many are answered, and
   whose turn the open ones are by next actor, so an obligation the user discussed and left
   with the agent counts as unanswered and on the agent; and a goal's
   interventions (work.js) are the members whose next actor is the user, since only those
   stop work on the user.
   Which obligation holds a node the user is in is the converse question, current location rather
   than membership (`obligationHolding`, current-target.js). It reads every placed
   obligation, to-dos included, and also falls back to an obligation's unique context. */
import { projectedDatum } from "../anchor-resolution.js";
import { elementById, inChrome, pageDocument } from "../passages.js";
import { under } from "../shadow.js";
import { readObligations } from "./model.js";

const NOWHERE = Object.freeze({ source: null, context: null, node: null });

export function obligationPlace(item, items = readObligations().all) {
  if (item?.source.kind === "todo") {
    const node = subjectPlace(item.source.subject);
    return node ? { source: null, context: node, node } : NOWHERE;
  }
  if (item?.source.kind !== "widget") return NOWHERE;
  const owner = elementById(item.source.id);
  const source = item.source.unit ? projectedDatum(owner, item.source.unit) : owner;
  const context = elementById(item.prompt.target);
  const shared = items.some(
    (other) =>
      other.id !== item.id &&
      other.source.kind === "widget" &&
      other.prompt.target === item.prompt.target,
  );
  return { source, context, node: item.source.unit || shared ? source : context };
}

// Where a to-do's or an update's subject stands on the page: the element or widget it
// names, the page's head for the page as a whole, and nowhere for a thread, which its
// owner draws.
export const subjectPlace = (subject) =>
  subject.kind === "page"
    ? pageHead()
    : subject.kind === "thread"
      ? null
      : elementById(subject.id);

// The page's head, where a to-do on the page as a whole stands: its first top-level
// heading, else its first heading, else the first element of its content. Being on the
// head is being on that element or in it, so a page with no heading takes its first
// block rather than `main`, which would put the user on the to-do anywhere on the page.
const HEADINGS = ["h1", "h1, h2, h3, h4, h5, h6"];
function pageHead() {
  for (const selector of HEADINGS) {
    const heading = [...document.querySelectorAll(selector)].find(
      (candidate) => !inChrome(candidate),
    );
    if (heading) return heading;
  }
  const content = pageDocument();
  return content?.firstElementChild ?? content ?? document.body.firstElementChild;
}

// The obligations `region` holds, in the order `obligations` lists them.
export function obligationsIn(region, items = readObligations().all) {
  return items.filter((item) => {
    if (item.status === "withdrawn") return false;
    const { source } = obligationPlace(item, items);
    return Boolean(source && under(source, region));
  });
}
