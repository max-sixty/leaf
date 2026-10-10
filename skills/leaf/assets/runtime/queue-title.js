/* An obligation's subject, shared by the Questions panel and package lists.
   Membership remains with the publisher. A title reads the current conversation
   or the rendered Question/widget it names, without interpreting events. */
import { addressableLabel } from "./anchor-resolution.js";
import { elementById } from "./passages.js";
import { questionHolding } from "./standing-target.js";
import { questionPlace } from "./questions/place.js";
import { readQuestions } from "./questions/model.js";
import { readThreads } from "./thread/state.js";
import { threadSummary } from "./thread/model.js";

export function queueTitle(item) {
  const thread = readThreads().threads.find((thread) => thread.id === item.thread);
  const own = elementById(item.subject.id);
  const topic = thread ? threadSummary(thread).topic : "";
  if (item.title) return item.title;
  if (item.kind === "work" && item.detail) return item.detail;
  if (item.subject.kind === "widget") {
    const question = own && questionHolding(readQuestions().all, own);
    return (
      (question && addressableLabel(questionPlace(question).context)) ||
      addressableLabel(own) ||
      topic ||
      item.id
    );
  }
  return topic || item.id;
}
