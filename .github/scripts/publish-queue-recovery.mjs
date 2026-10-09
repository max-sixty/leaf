/**
 * Recover publish-site's runner queue without interrupting a deployment.
 * GitHub's job timeout begins on a runner, so it cannot release an abandoned
 * workflow concurrency owner. Only hour-old queued deploy jobs that still have
 * neither a runner nor started steps qualify. Re-read that evidence before
 * ordinary cancellation, await settlement, then let an existing successor run.
 * Dispatch main only when recovery removed the last active publisher.
 */
import { appendFile } from "node:fs/promises";
import { pathToFileURL } from "node:url";
import { setTimeout } from "node:timers/promises";

const workflow = "publish-site.yaml";
const activeStatuses = ["queued", "pending", "in_progress", "waiting", "requested"];
const staleAfter = 60 * 60 * 1000;

function stale(run, now) {
  return (
    run.head_branch === "main" &&
    run.status === "queued" &&
    now - Date.parse(run.created_at) >= staleAfter
  );
}

function abandoned(jobs, now) {
  return (
    jobs.length === 1 &&
    jobs[0].name === "deploy-site" &&
    jobs[0].status === "queued" &&
    // The run keeps its original created_at when re-run; the latest attempt's
    // job timestamp measures how long this particular runner request waited.
    now - Date.parse(jobs[0].created_at) >= staleAfter &&
    jobs[0].runner_id === 0 &&
    !jobs[0].runner_name &&
    jobs[0].steps.every((step) => !step.started_at)
  );
}

export async function recover({ api, now = Date.now(), sleep = setTimeout, report }) {
  async function pages(path, key) {
    const values = [];
    for (let page = 1; ; page++) {
      const data = await api("GET", `${path}&per_page=100&page=${page}`);
      values.push(...data[key]);
      if (data[key].length < 100) return values;
    }
  }

  async function active() {
    const runs = new Map();
    for (const status of activeStatuses) {
      for (const run of await pages(
        `/actions/workflows/${workflow}/runs?branch=main&status=${status}`,
        "workflow_runs",
      )) {
        runs.set(run.id, run);
      }
    }
    return [...runs.values()];
  }

  const cancelled = [];
  const initial = await active();
  for (const candidate of initial.filter((run) => stale(run, now))) {
    const path = `/actions/runs/${candidate.id}`;
    // Job pagination matters even though publish-site currently has one job:
    // a future extra job must make this policy refuse, not hide an active runner.
    const run = await api("GET", path);
    const jobs = await pages(`${path}/jobs?filter=latest`, "jobs");
    if (!stale(run, now) || !abandoned(jobs, now)) {
      await report(
        `Preserved [run ${run.id}](${run.html_url}): its latest job is fresh, its state changed, or a job may have started.`,
      );
      continue;
    }
    try {
      await api("POST", `${path}/cancel`);
    } catch (error) {
      // Independent recovery runs may race the same cancellation. A completed
      // run already released its slot; every other refusal remains actionable.
      if (error.status !== 409 || (await api("GET", path)).status !== "completed")
        throw error;
    }
    await report(`Requested cancellation of [queued run ${run.id}](${run.html_url}).`);
    let settled = false;
    for (let attempt = 0; attempt <= 12; attempt++) {
      const current = await api("GET", path);
      if (current.status === "completed") {
        settled = true;
        break;
      }
      if (attempt < 12) await sleep(5000);
    }
    if (!settled)
      throw new Error(
        `Cancellation of run ${run.id} did not settle within one minute.`,
      );
    cancelled.push(run.id);
  }

  if (cancelled.length === 0) {
    await report("No abandoned queued publisher qualified for cancellation.");
    return;
  }

  // A new push can create a successor during recovery. Re-read the branch and
  // queue together rather than dispatching from the original empty snapshot.
  for (let attempt = 0; attempt < 3; attempt++) {
    const before = await api("GET", "/git/ref/heads/main");
    const remaining = await active();
    if (remaining.length) {
      await report(
        `Existing publishers retain the queue: ${remaining.map((run) => `[${run.id}](${run.html_url})`).join(", ")}.`,
      );
      return;
    }
    const after = await api("GET", "/git/ref/heads/main");
    if (before.object.sha !== after.object.sha) continue;
    // workflow_dispatch with GITHUB_TOKEN can start another workflow. It uses
    // main at dispatch time, including a push racing this final branch reading.
    await api("POST", `/actions/workflows/${workflow}/dispatches`, { ref: "main" });
    await report(`Dispatched publish-site on main (${after.object.sha}).`);
    return;
  }
  throw new Error(
    "Main kept changing during recovery; an empty publish queue could not be confirmed.",
  );
}

async function main() {
  const { GITHUB_API_URL, GITHUB_REPOSITORY, GITHUB_TOKEN, GITHUB_STEP_SUMMARY } =
    process.env;
  const report = async (message) => {
    process.stdout.write(`${message}\n`);
    if (GITHUB_STEP_SUMMARY) await appendFile(GITHUB_STEP_SUMMARY, `${message}\n\n`);
  };
  async function api(method, path, data) {
    const response = await fetch(
      `${GITHUB_API_URL}/repos/${GITHUB_REPOSITORY}${path}`,
      {
        method,
        headers: {
          Authorization: `Bearer ${GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json",
          "X-GitHub-Api-Version": "2022-11-28",
          "Content-Type": "application/json",
        },
        body: data === undefined ? undefined : JSON.stringify(data),
      },
    );
    if (!response.ok) {
      const error = new Error(
        `${method} ${path}: GitHub returned ${response.status}: ${await response.text()}`,
      );
      error.status = response.status;
      throw error;
    }
    // Cancellation accepts the request with an empty 202 response; dispatch
    // returns an empty 204. Only the read endpoints return JSON.
    return response.status === 202 || response.status === 204
      ? undefined
      : response.json();
  }
  try {
    await recover({ api, report });
  } catch (error) {
    await report(`Recovery failed: ${error.message}`);
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href)
  await main();
