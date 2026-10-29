import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import {
  copyFileSync,
  mkdtempSync,
  mkdirSync,
  rmSync,
  symlinkSync,
  writeFileSync,
} from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { test } from "node:test";
import { pathToFileURL } from "node:url";
import { capture, publish } from "./dependency-bundles.mjs";

const path = "browser/vendor/test.js";
const theme = "browser/styles/vendor/webawesome-theme.css";
const head = "original-head";
const repo = "owner/leaf";
const run = {
  event: "pull_request",
  head_sha: head,
  head_repository: { full_name: repo },
};
const artifact = {
  head,
  files: [
    { path, content: "new bundle" },
    { path: theme, content: "new theme" },
  ],
};

test("the trusted publisher loads its build declaration without installed dependencies", () => {
  const directory = mkdtempSync(join(tmpdir(), "dependency-publisher-"));
  try {
    for (const name of [".github/scripts", "build", "packages"])
      mkdirSync(join(directory, name), { recursive: true });
    for (const name of [".github/scripts/dependency-bundles.mjs", "build/styles.mjs"])
      copyFileSync(new URL(`../../${name}`, import.meta.url), join(directory, name));
    execFileSync(process.execPath, [
      "--input-type=module",
      "-e",
      `await import(${JSON.stringify(pathToFileURL(join(directory, ".github/scripts/dependency-bundles.mjs")).href)})`,
    ]);
  } finally {
    rmSync(directory, { recursive: true });
  }
});

test("capture includes changed, new and deleted generated files, but rejects source edits", () => {
  const directory = mkdtempSync(join(tmpdir(), "dependency-bundles-"));
  const previous = process.cwd();
  try {
    process.chdir(directory);
    const git = (...args) => execFileSync("git", args, { stdio: "ignore" });
    git("init", "-q");
    mkdirSync("browser/vendor", { recursive: true });
    mkdirSync("browser/styles/vendor", { recursive: true });
    writeFileSync(path, "old");
    writeFileSync(theme, "old theme");
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
    writeFileSync(theme, "new theme");
    writeFileSync("browser/vendor/chunk.js", "chunk");
    // The kernel compiles from the bundles, so a bump rebuilds it too.
    mkdirSync("dist/kernel/runtime", { recursive: true });
    writeFileSync("dist/kernel/kernel.json", "{}");
    writeFileSync("dist/kernel/runtime/bundle-state.js", "state");
    assert.deepEqual(capture().files, [
      { path: theme, content: "new theme" },
      { path, content: null },
      { path: "browser/vendor/chunk.js", content: "chunk" },
      { path: "dist/kernel/kernel.json", content: "{}" },
      { path: "dist/kernel/runtime/bundle-state.js", content: "state" },
    ]);
    rmSync("dist/kernel", { recursive: true });
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
  lock = "pnpm-lock.yaml",
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
        ...(lock ? [{ filename: lock }] : []),
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
  const { api, calls } = endpoint({
    extra: ["package.json", "pnpm-workspace.yaml", theme],
  });
  assert.equal(await publish(api, repo, run, artifact), "generated-commit");
  assert.deepEqual(calls.find((c) => c.route.endsWith("/trees")).data.tree, [
    { path, mode: "100644", type: "blob", content: "new bundle" },
    { path: theme, mode: "100644", type: "blob", content: "new theme" },
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
    "browser/vendor/../runtime/evil.js",
    "browser/vendor/.hidden.js",
    "browser/base.css",
    "browser/styles/theme.css",
    "packages/default/defaults.css",
    "browser/runtime/authored.css",
    "packages/playground/defaults.css",
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
  for (const options of [
    { extra: ["build/vendor.mjs"] },
    { lock: "package-lock.json" },
    { lock: null, extra: ["package.json", "pnpm-workspace.yaml"] },
  ]) {
    const { api, calls } = endpoint(options);
    await assert.rejects(publish(api, repo, run, artifact), /non-bundle source/);
    assert.ok(calls.every((c) => c.method === "GET"));
  }
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
