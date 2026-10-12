/* An obligation's subject, shared by the Questions panel and package lists.
   Membership remains with the publisher. A title reads the current conversation
   or the rendered Question/widget it names, without interpreting events. */
import { addressableLabel } from "./addressable-names.js";
import { elementById } from "./passages.js";
import { askHolding } from "./standing-target.js";
import { askPlace } from "./asks/place.js";
import { readAsks } from "./asks/model.js";
import { readThreads } from "./thread/state.js";
import { threadSummary } from "./thread/model.js";

export function queueTitle(item) {
  const thread = readThreads().threads.find((thread) => thread.id === item.thread);
  const own = elementById(item.subject.id);
  const topic = thread ? threadSummary(thread).topic : "";
  if (item.title) return item.title;
  if (item.kind === "work" && item.detail) return item.detail;
  if (item.subject.kind === "widget") {
    const ask = own && askHolding(readAsks().all, own);
    return (
      (ask && addressableLabel(askPlace(ask).context)) ||
      addressableLabel(own) ||
      topic ||
      item.id
    );
  }
  return topic || item.id;
}
