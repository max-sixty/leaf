/* The two lists, On me and On <agent>, the application publishes: the server's selection
   (`served_state.queues`), with this tab's unresolved sends placed against it. Each
   case adopts a whole reading the server folded (`tests/served_records.py`), so the
   lists it starts from are the ones `page state` prints. */
import assert from "node:assert/strict";
import test from "node:test";
import { createSemanticApplication } from "../../browser/runtime/framework/application.js";
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
  return {
    app,
    served: view.queues,
    obligations: view.obligations,
    todos: served.browser.todos,
  };
};
const published = (app) => app.read().effective.queues;
const kinds = (items) => items.map(({ kind, id }) => [kind, id]);
// A row as the server listed it, without the workflow, offers and obligation or to-do
// record this tab joins to it.
const listed = ({
  workflow: _workflow,
  offers: _offers,
  obligation: _obligation,
  todo: _todo,
  ...row
}) => row;

test("the browser publishes the queues the server selected", () => {
  const { app, served, obligations, todos } = adopted("queues on both sides");
  const { on_user: onUser, on_agent: onAgent, done } = published(app);
  assert.deepEqual(onUser.map(listed), served.on_user);
  // The server names an obligation's record by id, and this tab joins the row to it.
  for (const row of [...onUser, ...onAgent, ...done].filter(
    ({ kind, owner }) => kind !== "todo" || owner === "user",
  ))
    assert.deepEqual(
      row.obligation,
      obligations.find(({ id }) => id === row.id),
    );
  // Agent work keeps its to-do record; user work is an obligation.
  for (const row of onAgent.filter(({ kind }) => kind === "todo"))
    assert.deepEqual(
      row.todo,
      todos.find(({ id }) => id === row.id),
    );
  assert.deepEqual(onAgent.map(listed), served.on_agent);
  assert.deepEqual(done.map(listed), served.done);
  // Something of every kind on each list, so each placement below has an item to move.
  assert.deepEqual([...new Set(onUser.map(({ kind }) => kind))].sort(), [
    "message",
    "todo",
    "update",
    "widget",
  ]);
  assert.deepEqual([...new Set(onAgent.map(({ kind }) => kind))].sort(), [
    "todo",
    "update",
  ]);
});

test("a start gone quiet holds nothing, so its to-do shows no line in hand", () => {
  const { app } = adopted("quiet start");
  const running = Object.fromEntries(
    published(app).on_agent.map(({ todo }) => [todo.title, todo.running?.text ?? null]),
  );
  assert.deepEqual(running, {
    "Rebuild the chart": null,
    "Check the colours": "Comparing the palette",
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

test("a Done this tab sends ends its to-do at once, and its undo puts it back", () => {
  const { app } = adopted("queues on both sides");
  const todo = published(app).on_user.find((item) => item.offers.done);
  const ended = () =>
    published(app)
      .done.filter((item) => item.kind === "todo")
      .map(({ id, state }) => [id, state]);
  app.enqueue(
    { kind: "todo_end", todo: todo.id, outcome: "done", attempt: "d" },
    "now",
  );
  assert.ok(!published(app).on_user.some((item) => item.id === todo.id));
  assert.equal(
    app.read().effective.obligations.all.find((item) => item.id === todo.id).status,
    "answered",
  );
  assert.deepEqual(ended(), [[todo.id, "done"]]);
  // A refused Done puts the to-do back as the log has it.
  app.refuse("d");
  assert.ok(published(app).on_user.some((item) => item.id === todo.id));
  assert.equal(
    app.read().effective.obligations.all.find((item) => item.id === todo.id).next_actor,
    "user",
  );
  assert.deepEqual(ended(), []);

  const later = adopted("user done").app;
  const { outcome } = servedReading("user done").browser.todos.find(
    ({ id }) => id === todo.id,
  );
  later.enqueue({ kind: "undo", undoes: outcome.id, attempt: "u" }, "now");
  assert.ok(published(later).on_user.some((item) => item.id === todo.id));
  assert.ok(!published(later).done.some((item) => item.id === todo.id));
});

test("Done lists completed obligations and to-dos through their own records", () => {
  const { app } = adopted("done");
  const { done } = published(app);
  const answered = done.find((item) => item.kind === "widget");
  assert.equal(answered.obligation.status, "answered");
  assert.equal(answered.id, answered.obligation.id);
  assert.equal(answered.state, "done");
  assert.ok(
    done.some(
      (item) => item.kind === "todo" && item.todo.title === "Check the colours",
    ),
  );
});

test("an item lands in the Done of the list it left, newest first", () => {
  const { app } = adopted("done");
  const { done } = published(app);
  const owners = Object.fromEntries(done.map((item) => [item.id, item.owner]));
  // The answered obligation leaves On me; the ended to-do and the comment the agent
  // answered leave On <agent>.
  assert.deepEqual(owners, {
    "widget:ship": "user",
    e4: "agent",
    "update:e2": "agent",
  });
  // The comment keeps the record On <agent> listed it under, so a row moving to Done is
  // the same item, now answered by the reply.
  const sent = done.find((item) => item.id === "update:e2");
  assert.deepEqual(
    [sent.kind, sent.obligation.status, sent.obligation.answer.event.id],
    ["update", "answered", "e3"],
  );
  const times = done.map((item) => Date.parse(item.ended));
  assert.deepEqual(
    times,
    times.toSorted((a, b) => b - a),
  );
});

test("only a to-do on the user offers Done", () => {
  const { app } = adopted("queues on both sides");
  const { on_user: onUser, on_agent: onAgent } = published(app);
  const offered = [...onUser, ...onAgent].filter((item) => item.offers.done);
  assert.deepEqual(
    offered.map(({ kind, owner }) => [kind, owner]),
    [["todo", "user"]],
  );
});
