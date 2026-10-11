/* The work queues the application publishes: the server's selection
   (`served_state.queues`), with this tab's unresolved sends placed against it. Each
   case adopts a whole reading the server folded (`tests/served_records.py`), so the
   queues it starts from are the ones `page state` prints. */
import assert from "node:assert/strict";
import test from "node:test";
import { createSemanticApplication } from "./application.ts";
import { servedReading } from "../../tests/served.mjs";

const adopted = (name) => {
  const served = servedReading(name);
  const app = createSemanticApplication();
  app.identify(served.active.revision);
  assert.equal(app.adopt(served), true);
  return { app, served: served.browser.views[String(served.active.revision)].queues };
};
const published = (app) => app.read().effective.queues;
const kinds = (items) => items.map(({ kind, id }) => [kind, id]);
// An item as the server listed it, without the workflow and offers this tab adds.
const listed = ({ workflow: _workflow, offers: _offers, ...item }) => item;

test("the browser publishes the queues the server selected", () => {
  const { app, served } = adopted("queues on both sides");
  const { onYou, onAgent, done } = published(app);
  assert.deepEqual(onYou.map(listed), served.on_you);
  assert.deepEqual(onAgent.map(listed), served.on_agent);
  assert.deepEqual(done.map(listed), served.done);
  // Something of every kind on each side, so each placement below has an item to move.
  assert.deepEqual(
    [...new Set(onYou.map(({ kind }) => kind))].sort(),
    ["question", "recovery", "task"],
  );
  assert.deepEqual(
    [...new Set(onAgent.map(({ kind }) => kind))].sort(),
    ["answer", "task"],
  );
});

test("a start gone quiet holds nothing, so its task shows no line in hand", () => {
  const { app } = adopted("quiet start");
  const running = Object.fromEntries(
    published(app).onAgent.map((item) => [item.title, item.running?.text ?? null]),
  );
  assert.deepEqual(running, {
    "Rebuild the chart": null,
    "Check the colours": "Comparing the palette",
  });
});

test("a follow-up sent in a thread stands for the answer it was owed", () => {
  const { app } = adopted("queues on both sides");
  const owed = published(app).onAgent.find((item) => item.kind === "answer");
  app.enqueue(
    { kind: "reply", parent: owed.thread, text: "Also this.", revision: 1, attempt: "a3" },
    "now",
  );
  const answers = published(app).onAgent.filter((item) => item.kind === "answer");
  assert.deepEqual(kinds(answers), [["answer", "pending:a3"]]);
  assert.equal(answers[0].thread, owed.thread);
  assert.equal(published(app).onAgent.at(-1).kind, "task");
  app.refuse("a3");
  // A refused follow-up leaves the thread the user's to send again.
  assert.ok(
    published(app).onYou.some(
      (item) => item.kind === "recovery" && item.thread === owed.thread,
    ),
  );
});

test("prose sent beside a Question takes it off the user until the log answers", () => {
  const { app } = adopted("queues on both sides");
  const asked = published(app).onYou.find(
    (item) => item.kind === "question" && item.question.source.kind === "reply",
  );
  app.enqueue(
    { kind: "reply", parent: asked.thread, text: "Weekly.", revision: 1, attempt: "a4" },
    "now",
  );
  assert.ok(!published(app).onYou.some((item) => item.id === asked.id));
  app.refuse("a4");
  assert.ok(published(app).onYou.some((item) => item.id === asked.id));
});

test("a pending widget gesture changes no Question membership", () => {
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
  assert.deepEqual(kinds(published(app).onYou), kinds(before.onYou));
  assert.deepEqual(kinds(published(app).onAgent), kinds(before.onAgent));
});

test("a Done this tab sends ends its task at once, and its undo puts it back", () => {
  const { app } = adopted("queues on both sides");
  const task = published(app).onYou.find((item) => item.offers.done);
  const ended = () =>
    published(app)
      .done.filter((item) => item.kind === "task")
      .map(({ id, state }) => [id, state]);
  app.enqueue({ kind: "task_end", task: task.id, outcome: "done", attempt: "d" }, "now");
  assert.ok(!published(app).onYou.some((item) => item.id === task.id));
  assert.deepEqual(ended(), [[task.id, "done"]]);
  // A refused Done puts the task back as the log has it.
  app.refuse("d");
  assert.ok(published(app).onYou.some((item) => item.id === task.id));
  assert.deepEqual(ended(), []);

  const later = adopted("user done").app;
  const { outcome } = servedReading("user done").browser.ended_tasks.find(
    ({ id }) => id === task.id,
  );
  later.enqueue({ kind: "undo", undoes: outcome.id, attempt: "u" }, "now");
  assert.ok(published(later).onYou.some((item) => item.id === task.id));
  assert.ok(!published(later).done.some((item) => item.id === task.id));
});

test("Done lists completed Questions and explicit tasks through their own records", () => {
  const { app } = adopted("done");
  const { done } = published(app);
  const answered = done.find((item) => item.kind === "question");
  assert.equal(answered.question.status, "answered");
  assert.equal(answered.id, answered.question.id);
  assert.equal(answered.state, "done");
  assert.ok(
    done.some((item) => item.kind === "task" && item.title === "Check the colours"),
  );
});

test("only an explicit user task offers Done", () => {
  const { app } = adopted("queues on both sides");
  const { onYou, onAgent } = published(app);
  const offered = [...onYou, ...onAgent].filter((item) => item.offers.done);
  assert.deepEqual(
    offered.map(({ kind, owner }) => [kind, owner]),
    [["task", "user"]],
  );
});
