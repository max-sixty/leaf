/**
 * Exercise the recovery against structured GitHub REST responses. The external
 * runner queue cannot be reproduced locally: these fixtures retain the observed
 * abandoned-run fields (queued, runner_id 0, empty runner_name, no started steps)
 * and model transitions that must keep a real deployment safe.
 */
import assert from "node:assert/strict";
import { test } from "node:test";
import { execFile } from "node:child_process";
import { createServer } from "node:http";
import { once } from "node:events";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { recover } from "./publish-queue-recovery.mjs";

const now = Date.parse("2026-10-09T07:00:00Z");
const run = (id, fields = {}) => ({
  id,
  head_branch: "main",
  status: "queued",
  created_at: "2026-10-06T08:46:00Z",
  html_url: `https://github.com/max-sixty/leaf/actions/runs/${id}`,
  ...fields,
});
const job = (fields = {}) => ({
  name: "deploy-site",
  status: "queued",
  created_at: "2026-10-06T08:46:50Z",
  runner_id: 0,
  runner_name: "",
  steps: [],
  ...fields,
});

function github(
  runs,
  { jobs = [job()], onRead, onCancel, branchShas = [], settle = 0, dispatchError } = {},
) {
  const calls = [];
  const messages = [];
  const cancelling = new Map();
  let sleeps = 0;
  const state = { runs: structuredClone(runs), jobs, calls, messages };
  async function api(method, path, data) {
    calls.push([method, path, data]);
    if (method === "GET" && path.includes("/workflows/")) {
      const query = new URL(`https://api.github.com${path}`).searchParams;
      return {
        workflow_runs: structuredClone(
          state.runs.filter((value) => value.status === query.get("status")),
        ),
      };
    }
    if (path === "/git/ref/heads/main")
      return { object: { sha: branchShas.shift() ?? "latest-main" } };
    if (method === "POST" && path.endsWith("/dispatches")) {
      if (dispatchError) throw dispatchError;
      return;
    }
    const id = Number(path.match(/\/runs\/(\d+)/)[1]);
    const current = state.runs.find((value) => value.id === id);
    if (method === "POST") {
      if (onCancel) onCancel(current);
      cancelling.set(id, settle);
      return;
    }
    if (path.includes("/jobs?")) return { jobs: structuredClone(state.jobs) };
    if (onRead) onRead(current, state);
    if (cancelling.has(id)) {
      const left = cancelling.get(id);
      if (left === 0) current.status = "completed";
      else cancelling.set(id, left - 1);
    }
    return structuredClone(current);
  }
  return {
    state,
    execute: () =>
      recover({
        api,
        now,
        sleep: async () => {
          sleeps++;
        },
        report: async (message) => messages.push(message),
      }),
    mutations: () => calls.filter(([method]) => method === "POST"),
    sleeps: () => sleeps,
  };
}

test("releases an abandoned owner and leaves its healthy successor in the queue", async () => {
  const queue = github([
    run(1),
    run(2, { status: "pending", created_at: new Date(now).toISOString() }),
  ]);
  await queue.execute();
  assert.deepEqual(queue.mutations(), [["POST", "/actions/runs/1/cancel", undefined]]);
  assert.match(queue.state.messages.at(-1), /Existing publishers.*\[2\]/);
});

test("preserves healthy queues, running deployments, approvals, and jobs with execution evidence", async () => {
  for (const [fields, jobs] of [
    [{ created_at: new Date(now - 30 * 60 * 1000).toISOString() }, [job()]],
    [
      { status: "in_progress" },
      [job({ status: "in_progress", runner_id: 8, runner_name: "runner" })],
    ],
    [{ status: "waiting" }, [job()]],
    [{}, [job({ runner_id: 8 })]],
    [{}, [job({ runner_name: "runner" })]],
    [{}, [job({ steps: [{ started_at: "2026-10-09T06:59:00Z" }] })]],
    [{}, [job(), job({ name: "another-job" })]],
  ]) {
    const queue = github([run(1, fields)], { jobs });
    await queue.execute();
    assert.deepEqual(queue.mutations(), [], JSON.stringify({ fields, jobs }));
  }
});

test("re-fetches run and job state before cancellation", async () => {
  for (const onRead of [
    (current) => {
      current.status = "in_progress";
    },
    (_current, state) => {
      state.jobs[0] = job({ runner_id: 9, runner_name: "allocated-between-snapshots" });
    },
  ]) {
    const queue = github([run(1)], { onRead });
    await queue.execute();
    assert.deepEqual(queue.mutations(), []);
  }
});

test("a fresh retry of an old run keeps its runner request; an abandoned latest job qualifies", async () => {
  for (const [ageMinutes, shouldCancel] of [
    [5, false],
    [90, true],
  ]) {
    const queue = github([run(1, { run_attempt: 2 })], {
      jobs: [job({ created_at: new Date(now - ageMinutes * 60 * 1000).toISOString() })],
    });
    await queue.execute();
    assert.equal(
      queue.mutations().some(([, path]) => path.endsWith("/cancel")),
      shouldCancel,
    );
  }
});

test("waits for cancellation settlement, then dispatches latest main when no successor exists", async () => {
  const queue = github([run(1)], { settle: 2 });
  await queue.execute();
  assert.equal(queue.sleeps(), 2);
  assert.deepEqual(queue.mutations(), [
    ["POST", "/actions/runs/1/cancel", undefined],
    ["POST", "/actions/workflows/publish-site.yaml/dispatches", { ref: "main" }],
  ]);
  assert.match(queue.state.messages.at(-1), /Dispatched.*latest-main/);
});

test("does not dispatch while cancellation is still unsettled", async () => {
  const queue = github([run(1)], { settle: 100 });
  await assert.rejects(queue.execute(), /did not settle/);
  assert.equal(queue.sleeps(), 12);
  assert.deepEqual(queue.mutations(), [["POST", "/actions/runs/1/cancel", undefined]]);
});

test("a successor arriving during cancellation owns the next deployment", async () => {
  const queue = github([run(1)], {
    onRead: (_current, state) => {
      if (
        state.calls.some(([method]) => method === "POST") &&
        state.runs.length === 1
      ) {
        state.runs.push(run(2, { status: "in_progress" }));
      }
    },
  });
  await queue.execute();
  assert.equal(queue.mutations().length, 1);
  assert.match(queue.state.messages.at(-1), /Existing publishers.*\[2\]/);
});

test("dispatch failure fails recovery visibly", async () => {
  const queue = github([run(1)], { dispatchError: new Error("GitHub returned 403") });
  await assert.rejects(queue.execute(), /GitHub returned 403/);
  assert.equal(
    queue.state.messages.some((message) => message.startsWith("Dispatched")),
    false,
  );
});

test("an independent recovery's completed cancellation is harmless; other refusals fail", async () => {
  for (const status of ["completed", "in_progress"]) {
    const queue = github([run(1)], {
      onCancel: (current) => {
        current.status = status;
        const error = new Error("GitHub returned 409");
        error.status = 409;
        throw error;
      },
    });
    if (status === "completed") {
      await queue.execute();
      assert.match(queue.state.messages.at(-1), /Dispatched/);
    } else {
      await assert.rejects(queue.execute(), /GitHub returned 409/);
      assert.equal(queue.mutations().length, 1);
    }
  }
});

test("a main push during the empty-queue check causes a fresh reading before dispatch", async () => {
  const queue = github([run(1)], {
    branchShas: ["old-main", "new-main", "new-main", "new-main"],
  });
  await queue.execute();
  assert.equal(
    queue.state.calls.filter(([, path]) => path === "/git/ref/heads/main").length,
    4,
  );
  assert.match(queue.state.messages.at(-1), /new-main/);
  const changing = github([run(1)], { branchShas: ["a", "b", "c", "d", "e", "f"] });
  await assert.rejects(changing.execute(), /Main kept changing/);
  assert.equal(changing.mutations().length, 1);
});

test("the real CLI accepts GitHub's empty 202 cancellation and 204 dispatch responses", async () => {
  const current = run(1, {
    created_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
  });
  const mutations = [];
  const server = createServer(async (request, response) => {
    assert.equal(request.headers.authorization, "Bearer boundary-test-token");
    const url = new URL(request.url, "http://localhost");
    const path = url.pathname.replace("/repos/max-sixty/leaf", "");
    response.setHeader("Content-Type", "application/json");
    if (request.method === "POST") {
      let body = "";
      for await (const part of request) body += part;
      mutations.push([path, body]);
      if (path === "/actions/runs/1/cancel") {
        current.status = "completed";
        response.writeHead(202);
      } else if (path === "/actions/workflows/publish-site.yaml/dispatches") {
        response.writeHead(204);
      } else response.writeHead(404);
      response.end();
      return;
    }
    let data;
    if (path === "/actions/workflows/publish-site.yaml/runs") {
      data = {
        workflow_runs:
          current.status === url.searchParams.get("status") ? [current] : [],
      };
    } else if (path === "/actions/runs/1/jobs") data = { jobs: [job()] };
    else if (path === "/actions/runs/1") data = current;
    else if (path === "/git/ref/heads/main") data = { object: { sha: "latest-main" } };
    else response.writeHead(404);
    response.end(JSON.stringify(data));
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  try {
    const { stdout, stderr } = await promisify(execFile)(
      process.execPath,
      [fileURLToPath(new URL("./publish-queue-recovery.mjs", import.meta.url))],
      {
        timeout: 5000,
        env: {
          ...process.env,
          GITHUB_API_URL: `http://127.0.0.1:${server.address().port}`,
          GITHUB_REPOSITORY: "max-sixty/leaf",
          GITHUB_TOKEN: "boundary-test-token",
          GITHUB_STEP_SUMMARY: "",
        },
      },
    );
    assert.equal(stderr, "");
    assert.match(stdout, /Dispatched publish-site/);
    assert.deepEqual(mutations, [
      ["/actions/runs/1/cancel", ""],
      ["/actions/workflows/publish-site.yaml/dispatches", '{"ref":"main"}'],
    ]);
  } finally {
    await new Promise((resolve, reject) =>
      server.close((error) => (error ? reject(error) : resolve())),
    );
  }
});
