/** Compile-only regression for the contracts that unchecked JS previously erased. */
import type { Event, Command, Thread } from "./domain.ts";
import { createSemanticApplication } from "./application.ts";
import {
  discussed,
  threadNames,
} from "../../skills/leaf/assets/runtime/thread/model.js";
import { actionForWidget } from "../../skills/leaf/assets/runtime/pending/model.js";
import { foldProjection } from "../../skills/leaf/assets/runtime/projection/model.js";
import { createCommandDispatch } from "../../skills/leaf/assets/runtime/pending/dispatch.js";
import { stageAuthoredStates } from "../../skills/leaf/assets/runtime/projection/authored.js";
import { post, dispatchWidget } from "../../skills/leaf/assets/runtime/application.js";

type IsAny<T> = 0 extends 1 & T ? true : false;
const eventIsChecked: IsAny<Event> = false;
const threadIsChecked: IsAny<Parameters<typeof discussed>[0]> = false;
const postIsChecked: IsAny<Parameters<typeof post>[0]> = false;
const dispatchIsChecked: IsAny<Parameters<typeof dispatchWidget>[1]> = false;
const threadLookupIsChecked: IsAny<
  ReturnType<typeof threadNames> extends Map<string, infer T> ? T : never
> = false;
const projectionIsChecked: IsAny<
  ReturnType<typeof foldProjection>["desired"] extends ReadonlyMap<string, infer T>
    ? T
    : never
> = false;

function boundary(
  app: ReturnType<typeof createSemanticApplication>,
  event: Event,
  thread: Thread,
  dispatch: ReturnType<typeof createCommandDispatch>,
) {
  const command: Command = {
    kind: "action",
    widget: "choice",
    action: "choose",
    detail: { value: ["first"] },
    revision: 1,
    attempt: "local-attempt",
  };
  const produced = actionForWidget(
    { id: "choice" },
    { verb: "choose", detail: { value: ["first"] } },
    1,
  );
  app.enqueue({ ...produced, attempt: "local-attempt" }, "now");
  dispatch.post(produced);
  app.enqueue(command, "2026-10-09T12:00:00Z");
  const markupCommand = {
    kind: "comment" as const,
    revision: 1,
    attempt: "markup-comment",
    text: "hello",
    markup: "<p>hello</p>",
  };
  // @ts-expect-error Browser comments cannot carry agent-authored markup, even through a variable.
  app.enqueue(markupCommand, "now");
  const { revision: _revision, ...incomplete } = command;
  // @ts-expect-error An action producer must include the document it acts on.
  app.enqueue(incomplete, "now");
  // @ts-expect-error The actual post boundary requires the same complete command.
  dispatch.post(incomplete);
  // @ts-expect-error The exported runtime port retains the checked command contract.
  post(incomplete);
  // @ts-expect-error Admission must supply durable meaning before this becomes a record.
  const admitted: Event = {
    ...command,
    id: "logged",
    seq: 1,
    ts: "now",
    attention: false,
    author: "user",
  };
  // @ts-expect-error A message fold cannot silently read a misspelled server field.
  thread.root.attentoin;
  // @ts-expect-error Event fields are narrowed by their declared kernel kind.
  const widget: string = event.widget;
  return [
    admitted,
    widget,
    eventIsChecked,
    threadIsChecked,
    postIsChecked,
    dispatchIsChecked,
    threadLookupIsChecked,
    projectionIsChecked,
  ];
}
void boundary;
void createCommandDispatch;
void stageAuthoredStates;
