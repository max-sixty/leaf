import assert from "node:assert/strict";
import test from "node:test";
import { claimantDiagnostics } from "/runtime/page-about.js";

const held = {
  agent: "Claude",
  claim_session: "5cbebdab-029d-4fab-9c35-3ec68cb7c35d",
  session_name: "Fix the build",
  session_cwd: "/Users/me/workspace/api",
  session_alive: true,
};

test("the agent session row names the session the page's comments reach", () => {
  assert.equal(
    claimantDiagnostics(held),
    [
      "Agent session",
      "agent: Claude",
      "name: Fix the build",
      "id: 5cbebdab-029d-4fab-9c35-3ec68cb7c35d",
      "directory: /Users/me/workspace/api",
      "running: true",
    ].join("\n"),
  );
});

test("a session with no name copies none, and one that ended says so", () => {
  const ended = { ...held, session_name: null, session_alive: false };
  assert.ok(!claimantDiagnostics(ended).includes("name:"));
  assert.ok(claimantDiagnostics(ended).endsWith("running: false"));
});
