import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { mkdtempSync, mkdirSync, rmSync, symlinkSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { capture, publish } from "./dependency-bundles.mjs";

const path = "skills/leaf/assets/vendor/test.js";
const head = "original-head";
const repo = "owner/leaf";
const run = {
  event: "pull_request",
  head_sha: head,
  head_repository: { full_name: repo },
};
const artifact = { head, files: [{ path, content: "new bundle" }] };

test("capture includes changed, new and deleted generated files, but rejects source edits", () => {
  const directory = mkdtempSync(join(tmpdir(), "dependency-bundles-"));
  const previous = process.cwd();
  try {
    process.chdir(directory);
    const git = (...args) => execFileSync("git", args, { stdio: "ignore" });
    git("init", "-q");
    mkdirSync("skills/leaf/assets/vendor", { recursive: true });
    writeFileSync(path, "old");
    writeFileSync("package.json", "{}");
    git("add", ".");
    git(
      "-c",
      "user.name=Test",
      "-c",
      "user.email=test@example.com",
      "commit",
      "-qm",
      "baseline",
    );
    rmSync(path);
    writeFileSync("skills/leaf/assets/vendor/chunk.js", "chunk");
    assert.deepEqual(capture().files, [
      { path, content: null },
      { path: "skills/leaf/assets/vendor/chunk.js", content: "chunk" },
    ]);
    symlinkSync("missing.js", path);
    assert.throws(capture, /not a regular file/);
    rmSync(path);
    writeFileSync("package.json", '{"tampered":true}');
    assert.throws(capture, /non-bundle path/);
  } finally {
    process.chdir(previous);
    rmSync(directory, { recursive: true });
  }
});

function endpoint({
  current = head,
  author = "dependabot[bot]",
  extra = [],
  race = false,
} = {}) {
  const calls = [];
  const api = async (method, route, data) => {
    calls.push({ method, route, data });
    if (route.endsWith("/pulls"))
      return [
        {
          number: 42,
          state: "open",
          user: { login: author },
          head: {
            sha: current,
            ref: "dependabot/npm/group",
            repo: { full_name: repo },
          },
        },
      ];
    if (route.includes("/files?"))
      return [
        { filename: "package-lock.json" },
        ...extra.map((filename) => ({ filename })),
      ];
    if (method === "GET") return { tree: { sha: "old-tree" } };
    if (route.endsWith("/trees")) return { sha: "new-tree" };
    if (route.endsWith("/commits")) return { sha: "generated-commit" };
    assert.equal(data.force, false);
    if (race) throw new Error("ref is not a fast forward");
    return {};
  };
  return { api, calls };
}

test("publisher changes only bundles on the exact Dependabot branch and preserves parent custody", async () => {
  const { api, calls } = endpoint();
  assert.equal(await publish(api, repo, run, artifact), "generated-commit");
  assert.deepEqual(calls.find((c) => c.route.endsWith("/trees")).data.tree, [
    { path, mode: "100644", type: "blob", content: "new bundle" },
  ]);
  assert.deepEqual(
    calls.find((c) => c.route.endsWith("/commits") && c.method === "POST").data.parents,
    [head],
  );
  assert.equal(
    calls.at(-1).route,
    "/repos/owner/leaf/git/refs/heads/dependabot%2Fnpm%2Fgroup",
  );
});

test("publisher refuses untrusted paths, foreign builds and non-dependency source changes before writing", async () => {
  for (const bad of [
    ".github/workflows/ci.yaml",
    "skills/leaf/assets/vendor/../runtime/evil.js",
    "skills/leaf/assets/vendor/.hidden.js",
  ]) {
    const { api, calls } = endpoint();
    await assert.rejects(
      publish(api, repo, run, { head, files: [{ path: bad, content: "bad" }] }),
      /Invalid/,
    );
    assert.equal(calls.length, 0);
  }
  for (const badRun of [
    { ...run, event: "push" },
    { ...run, head_repository: { full_name: "attacker/fork" } },
    { ...run, head_sha: "other-head" },
  ]) {
    const { api, calls } = endpoint();
    await assert.rejects(publish(api, repo, badRun, artifact));
    assert.equal(calls.length, 0);
  }
  const { api, calls } = endpoint({ extra: ["build/vendor.py"] });
  await assert.rejects(publish(api, repo, run, artifact), /non-bundle source/);
  assert.ok(calls.every((c) => c.method === "GET"));
});

test("superseded heads and other authors cannot publish; a race refuses the final write", async () => {
  for (const options of [{ current: "new-head" }, { author: "human" }]) {
    const { api, calls } = endpoint(options);
    assert.equal(await publish(api, repo, run, artifact), "superseded");
    assert.ok(calls.every((c) => c.method === "GET"));
  }
  const { api } = endpoint({ race: true });
  await assert.rejects(publish(api, repo, run, artifact), /not a fast forward/);
});
