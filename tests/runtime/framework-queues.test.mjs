/* The two lists, On Me and On <agent>, the application publishes: the server's selection
   (`served_state.queues`), with this tab's unresolved sends placed against it. Each
   case adopts a whole reading the server folded (`tests/served_records.py`), so the
   lists it starts from are the ones `page state` prints. */
import assert from "node:assert/strict";
import test from "node:test";
import { createSemanticApplication } from "../../browser/runtime/state/semantic-application.js";
import { itemEnding, itemOutcome } from "../../browser/runtime/state/queues.js";
import { todoWord } from "../../browser/runtime/records/thread/workflow.js";
import { servedReading } from "../served.mjs";

const adopted = (name) => {
  const served = servedReading(name);
  const app = createSemanticApplication();
  app.identify(served.active.revision);
  // A message with markup, such as one holding a widget, draws the body the page
  // captured; this stands in its words.
  const view = served.browser.views[String(served.active.revision)];
  const messageBodies = new Map(
    view.thread.threads.map(({ id: thread, msgs }) => [
      thread,
      new Map(
        msgs.filter(({ markup }) => markup).map(({ id, text }) => [id, { text }]),
      ),
    ]),
  );
  assert.equal(app.adopt(served, { ...app.read().document, messageBodies }), true);
  return { app, served: view.queues, obligations: view.obligations };
};
const published = (app) => app.read().effective.queues;
const kinds = (items) => items.map(({ kind, id }) => [kind, id]);
// A row as the server listed it, without the workflow and obligation record this tab
// joins to it.
const listed = ({ workflow: _workflow, obligation: _obligation, ...row }) => row;

test("the browser publishes the queues the server selected", () => {
  const { app, served, obligations } = adopted("queues on both sides");
  const { on_user: onUser, on_agent: onAgent, done } = published(app);
  assert.deepEqual(onUser.map(listed), served.on_user);
  // The server names each row's record by id, a to-do's too, and this tab joins the
  // row to it.
  for (const row of [...onUser, ...onAgent, ...done])
    assert.deepEqual(
      row.obligation,
      obligations.find(({ id }) => id === row.id),
    );
  assert.deepEqual(onAgent.map(listed), served.on_agent);
  assert.deepEqual(done.map(listed), served.done);
  // Something of every kind on each list, so each placement below has an item to move.
  // Everything on the user is an obligation its own source answers.
  assert.deepEqual([...new Set(onUser.map(({ kind }) => kind))].sort(), [
    "message",
    "update",
    "widget",
  ]);
  assert.deepEqual([...new Set(onAgent.map(({ kind }) => kind))].sort(), [
    "todo",
    "update",
  ]);
});

test("a start gone quiet holds nothing, so its to-do reads Gone quiet, not On it", () => {
  const { app } = adopted("quiet start");
  const words = Object.fromEntries(
    published(app).on_agent.map(({ obligation }) => [
      obligation.prompt.text,
      todoWord(obligation).text,
    ]),
  );
  assert.deepEqual(words, {
    "Rebuild the chart": "Gone quiet",
    "Check the colours": "On it",
  });
});

test("a follow-up sent in a thread stands for the answer it was owed", () => {
  const { app } = adopted("queues on both sides");
  const owed = published(app).on_agent.find((item) => item.kind === "update");
  app.enqueue(
    {
      kind: "reply",
      parent: owed.thread,
      text: "Also this.",
      revision: 1,
      attempt: "a3",
    },
    "now",
  );
  app.enqueue(
    {
      kind: "reply",
      parent: owed.thread,
      text: "And this.",
      revision: 1,
      attempt: "a5",
    },
    "now",
  );
  // The thread is owed one answer, for its newest turn, however many are sending.
  const answers = published(app).on_agent.filter((item) => item.kind === "update");
  assert.deepEqual(kinds(answers), [["update", "update:pending:a5"]]);
  app.refuse("a5");
  // The answer falls back to the follow-up still sending, in the same thread.
  const left = published(app).on_agent.filter((item) => item.kind === "update");
  assert.deepEqual(kinds(left), [["update", "update:pending:a3"]]);
  assert.equal(left[0].thread, owed.thread);
  assert.equal(published(app).on_agent.at(-1).kind, "todo");
  app.refuse("a3");
  // A refused follow-up leaves the thread the user's to send again, and the answer
  // it was owed back on the agent.
  assert.ok(
    published(app).on_user.some(
      (item) => item.kind === "update" && item.thread === owed.thread,
    ),
  );
  assert.deepEqual(
    kinds(published(app).on_agent.filter((item) => item.kind === "update")),
    [["update", owed.id]],
  );
});

test("words sent to a question leave it on the user until the log answers", () => {
  const { app } = adopted("queues on both sides");
  const question = published(app).on_user.find((item) => item.kind === "message");
  app.enqueue(
    {
      kind: "reply",
      parent: question.thread,
      text: "Weekly.",
      revision: 1,
      attempt: "a4",
    },
    "now",
  );
  // Whether the words answer the question is the server's reading; the send itself
  // is the agent's to answer at once.
  assert.ok(published(app).on_user.some((item) => item.id === question.id));
  assert.ok(published(app).on_agent.some((item) => item.id === "update:pending:a4"));
  app.refuse("a4");
  assert.ok(published(app).on_user.some((item) => item.id === question.id));
  assert.ok(!published(app).on_agent.some((item) => item.id === "update:pending:a4"));
});

// The widget's word on its obligation, as `widgetAnswered` reads it, for one widget.
const says = (widget, answered) => (/** @type {string} */ asked) =>
  asked === widget ? answered : undefined;
const record = (app, id) => app.read().effective.obligations.byId.get(id);

test("a widget's gesture answers its question in the task that draws it", () => {
  const { app } = adopted("queues on both sides");
  const before = published(app);
  const onUser = () => published(app).on_user.some(({ id }) => id === "widget:pick");
  assert.ok(onUser());
  app.enqueue(
    {
      kind: "action",
      widget: "pick",
      action: "choose",
      detail: { value: ["one"] },
      revision: 1,
      attempt: "a2",
    },
    "now",
  );
  // Until the widget says, a gesture moves nothing on either list.
  assert.deepEqual(kinds(published(app).on_user), kinds(before.on_user));
  assert.deepEqual(kinds(published(app).on_agent), kinds(before.on_agent));
  app.answer("a2", says("pick", true));
  // The event carries the word to the log, and the question leaves On Me for Done
  // before the server has read the pick.
  assert.equal(app.entry("a2")?.event.answered, true);
  assert.ok(!onUser());
  assert.ok(published(app).done.some(({ id }) => id === "widget:pick"));
  const answered = record(app, "widget:pick");
  assert.deepEqual(
    [answered.state, answered.answered, answered.next_actor],
    ["done", true, null],
  );
  // A refusal returns the question to where the server has it.
  app.refuse("a2");
  assert.ok(onUser());
  assert.equal(record(app, "widget:pick").state, "waiting");
});

test("a gesture that leaves its widget open says nothing new", () => {
  const { app } = adopted("queues on both sides");
  const before = published(app);
  app.enqueue(
    {
      kind: "action",
      widget: "pick",
      action: "choose",
      detail: { value: [] },
      revision: 1,
      attempt: "a2",
    },
    "now",
  );
  app.answer("a2", says("pick", false));
  assert.equal(app.entry("a2")?.event.answered, false);
  assert.deepEqual(kinds(published(app).on_user), kinds(before.on_user));
  assert.equal(record(app, "widget:pick").state, "waiting");
});

test("undoing the act that answered a question asks it again at once", () => {
  const { app } = adopted("done");
  const answered = record(app, "widget:ship");
  assert.equal(answered.state, "done");
  const id = /** @type {string} */ (answered.answer?.event?.id);
  app.enqueue({ kind: "undo", undoes: id, attempt: "a9" }, "now");
  app.answer("a9", says("ship", false));
  assert.equal(app.entry("a9")?.event.answered, false);
  const reopened = record(app, "widget:ship");
  assert.deepEqual(
    [reopened.state, reopened.answered, reopened.next_actor],
    ["waiting", false, "user"],
  );
  assert.ok(published(app).on_user.some(({ id }) => id === "widget:ship"));
});

test("a gesture on nothing that asks carries no word", () => {
  const { app } = adopted("queues on both sides");
  app.enqueue({ kind: "comment", text: "Hm.", revision: 1, attempt: "a3" }, "now");
  app.answer("a3", () => true);
  assert.equal("answered" in (app.entry("a3")?.event ?? {}), false);
});

test("Done lists completed obligations and to-dos through their own records", () => {
  const { app } = adopted("done");
  const { done } = published(app);
  const answered = done.find((item) => item.kind === "widget");
  assert.deepEqual(
    [answered.obligation.state, answered.obligation.outcome, answered.obligation.end],
    ["done", "done", null],
  );
  assert.equal(answered.id, answered.obligation.id);
  assert.deepEqual(itemOutcome(answered), { text: "Done", voice: "leaf" });
  const todo = done.find((item) => item.kind === "todo");
  assert.equal(todo.obligation.prompt.text, "Check the colours");
  // The agent's end of its own to-do is its act, with the detail it gave.
  assert.deepEqual(itemOutcome(todo), { text: "Done", voice: "agent" });
  assert.equal(itemEnding(todo).detail, "Matched the theme");
});

test("an item lands in the Done of the list it left, newest first", () => {
  const { app } = adopted("done");
  const { done } = published(app);
  const owners = Object.fromEntries(done.map((item) => [item.id, item.owner]));
  // The answered obligation leaves On Me, and the ended to-do On <agent>. The comment
  // the agent answered with a to-do stays owed through it (`workflows.py`).
  assert.deepEqual(owners, { "widget:ship": "user", e4: "agent" });
  const times = done.map((item) => Date.parse(itemEnding(item).ended));
  assert.ok(times.every(Number.isFinite));
  assert.deepEqual(
    times,
    times.toSorted((a, b) => b - a),
  );
  // A comment the agent answered keeps the record On <agent> listed it under, so a row
  // moving to Done is the same item, now answered by the reply.
  const sent = published(adopted("queues on both sides").app).done.find(
    (item) => item.kind === "update",
  );
  assert.deepEqual(
    [sent.id, sent.obligation.state, sent.obligation.answer.event.id],
    ["update:e1", "done", "e2"],
  );
});
