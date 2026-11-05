// @ts-check
/** Compile-only regression for the contracts that unchecked JS previously erased.
 *
 * Nothing runs it: the type check reads it, and every runtime function it calls
 * arrives as a parameter typed by its module, so it imports nothing. It is a module
 * all the same, so its types don't join the global scope. */
export {};

/** @typedef {import("./domain.js").Event} Event */
/** @typedef {import("./domain.js").Command} Command */
/** @typedef {import("./domain.js").Thread} Thread */
/** @typedef {typeof import("../runtime/framework/application.js").createSemanticApplication} CreateApplication */
/** @typedef {typeof import("../runtime/thread/model.js").discussed} Discussed */
/** @typedef {typeof import("../runtime/thread/model.js").threadNames} ThreadNames */
/** @typedef {typeof import("../runtime/projection/model.js").foldProjection} FoldProjection */
/** @typedef {typeof import("../runtime/application.js").post} Post */
/** @typedef {typeof import("../runtime/application.js").dispatchWidget} DispatchWidget */

/** @template T @typedef {0 extends 1 & T ? true : false} IsAny */
/** @type {IsAny<Event>} */
const eventIsChecked = false;
/** @type {IsAny<Parameters<Discussed>[0]>} */
const threadIsChecked = false;
/** @type {IsAny<Parameters<Post>[0]>} */
const postIsChecked = false;
/** @type {IsAny<Parameters<DispatchWidget>[1]>} */
const dispatchIsChecked = false;
/** @type {IsAny<ReturnType<ThreadNames> extends Map<string, infer T> ? T : never>} */
const threadLookupIsChecked = false;
/** @type {IsAny<ReturnType<FoldProjection>["desired"] extends ReadonlyMap<string, infer T> ? T : never>} */
const projectionIsChecked = false;

/**
 * @param {ReturnType<CreateApplication>} app
 * @param {Event} event
 * @param {Thread} thread
 * @param {ReturnType<typeof import("../runtime/pending/dispatch.js").createCommandDispatch>} dispatch
 * @param {typeof import("../runtime/pending/model.js").actionForWidget} actionForWidget
 * @param {Post} post
 */
function boundary(app, event, thread, dispatch, actionForWidget, post) {
  /** @type {Command} */
  const command = {
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
    kind: /** @type {const} */ ("comment"),
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
  /** @type {Event} */
  // @ts-expect-error Admission must supply durable meaning before this becomes a record.
  const admitted = {
    ...command,
    id: "logged",
    seq: 1,
    ts: "now",
    attention: false,
    author: "user",
  };
  // @ts-expect-error A message fold cannot silently read a misspelled server field.
  void thread.root.attentoin;
  /** @type {string} */
  // @ts-expect-error Event fields are narrowed by their declared kernel kind.
  const widget = event.widget;
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

/** @param {typeof import("../runtime/semantic-state.js").applicationPresenter} presenter
 * @param {boolean} enabled */
function presenterBoundary(presenter, enabled) {
  presenter({
    region: "typed-reading",
    reading: () => (enabled ? { count: 1 } : null),
    paint(value, current, resume) {
      // @ts-expect-error The paint receives the reading's value, never any.
      void value.missing;
      const next = resume(/** @param {number} count */ (count) => count + 1);
      // @ts-expect-error Resuming preserves the continuation's parameter type.
      next("wrong");
      return current() ? next(value.count) : 0;
    },
  });
}
void presenterBoundary;

/** @param {typeof import("../runtime/activity-words.js").pageStatus} pageStatus
 * @param {typeof import("../runtime/activity-words.js").statusModel} statusModel
 * @param {Parameters<typeof import("../runtime/activity-words.js").pageStatus>[0]} state
 * @param {Parameters<typeof import("../runtime/activity-words.js").statusModel>[1]} queues
 * @param {typeof import("../runtime/thread/workflow.js").workflowWord} workflowWord */
function wordingBoundary(pageStatus, statusModel, state, queues, workflowWord) {
  // @ts-expect-error The server's status detail is text, not an unchecked value.
  pageStatus({ ...state, activity: { ...state.activity, detail: 123 } });
  // @ts-expect-error A failed read must carry its error text.
  pageStatus(state, { reach: "faulted" });
  const status = pageStatus(state);
  statusModel(
    // @ts-expect-error A voiced part cannot smuggle a non-text value into rendering.
    { ...status, summaryParts: [{ text: 123, voice: "agent" }] },
    queues,
    "Claude",
  );
  /** @type {IsAny<Parameters<typeof workflowWord>[0]>} */
  const workflowIsChecked = false;
  /** @type {IsAny<ReturnType<typeof statusModel>["summaryParts"][number]>} */
  const partIsChecked = false;
  return [workflowIsChecked, partIsChecked];
}
void wordingBoundary;
