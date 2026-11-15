/* The two lists, On Me and On <agent>, the application publishes: the server's selection
   (`served_state.queues`), with this tab's unresolved sends placed against it. Each
   case adopts a whole reading the server folded (`tests/served_records.py`), so the
   lists it starts from are the ones `page state` prints. */
import assert from "node:assert/strict";
import test from "node:test";
import { createSemanticApplication } from "../../browser/runtime/framework/application.js";
import { itemEnding, itemOutcome } from "../../browser/runtime/queues.js";
import { todoWord } from "../../browser/runtime/thread/workflow.js";
import { servedReading } from "../served.mjs";

const adopted = (name) => {
  const served = servedReading(name);
  const app = createSemanticApplication();
  app.identify(served.active.revision);
  // A message with markup, such as one holding a widget, draws the body the page
  // captured; this stands in its words.
  const view = served.browser.views[String(served.active.revision)];
  const messageBodies = new Map(
    view.thread.threads.flatMap(({ msgs }) =>
      msgs.filter(({ markup }) => markup).map(({ id, text }) => [id, { text }]),
    ),
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
  assert.equal(answers[0].thread, owed.thread);
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

test("a pending widget gesture changes no obligation membership", () => {
  const { app } = adopted("queues on both sides");
  const before = published(app);
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
  assert.deepEqual(kinds(published(app).on_user), kinds(before.on_user));
  assert.deepEqual(kinds(published(app).on_agent), kinds(before.on_agent));
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
