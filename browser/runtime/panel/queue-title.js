/* An obligation's subject, shared by On Me and package lists.
   Membership remains with the publisher. A title reads the current conversation
   or the rendered obligation or widget it names, without interpreting events. */
import { addressableLabel } from "../readings/addressable-names.js";
import { elementById } from "../readings/passages.js";
import { obligationHolding } from "../records/current-target.js";
import { obligationPlace, readObligations } from "../records/obligations/place.js";
import { threadNamed } from "../records/thread/state.js";
import { threadName } from "../records/thread/messages.js";

/** @param {import("../state/semantic-application.js").CurrentQueueItem} item */
export function queueTitle(item) {
  // A thread a reaction opened is named too, by its emoji until it has a title.
  const thread = item.thread ? threadNamed(item.thread) : null;
  const topic = thread ? threadName(thread) : "";
  // An obligation's prompt, which a to-do's title is.
  const title = item.obligation.prompt.text;
  if (title) return title;
  // A reply the agent sent reads as its own words, since one thread holds many.
  const reply = item.kind === "update" ? item.obligation.answer?.event?.id : null;
  const sent = reply && thread?.msgs.find((message) => message.id === reply);
  if (sent) return sent.body.text.trim() || topic;
  if (item.subject.kind === "widget") {
    const own = elementById(item.subject.id);
    const record = own && obligationHolding(readObligations().all, own);
    return (
      (record && addressableLabel(obligationPlace(record).context)) ||
      addressableLabel(own) ||
      topic ||
      item.id
    );
  }
  return topic || item.id;
}
