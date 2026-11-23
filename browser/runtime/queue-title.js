/* An obligation's subject, shared by On Me and package lists.
   Membership remains with the publisher. A title reads the current conversation
   or the rendered obligation or widget it names, without interpreting events. */
import { addressableLabel } from "./addressable-names.js";
import { elementById } from "./passages.js";
import { obligationHolding } from "./current-target.js";
import { obligationPlace } from "./obligations/place.js";
import { readObligations } from "./obligations/model.js";
import { threadNamed } from "./thread/state.js";
import { discussed } from "./thread/model.js";
import { threadName } from "./thread/messages.js";

/** @param {import("./framework/application.js").CurrentQueueItem} item */
export function queueTitle(item) {
  const named = item.thread ? threadNamed(item.thread) : null;
  const thread = named && discussed(named) ? named : null;
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
