/** Opt-in smoke of the Promptfoo/native-judge adapter; no model is invoked. */
const assert = require("node:assert/strict");
const { mkdtemp, rm } = require("node:fs/promises");
const { tmpdir } = require("node:os");
const { join } = require("node:path");
const { test } = require("node:test");

test("Promptfoo passes the saved task pages to one judge and returns its grade", async (t) => {
  const { default: grade } = await import("../../leaf_dev/authoring_assertion.mjs");
  const work = await mkdtemp(join(tmpdir(), "leaf-judge-smoke-"));
  t.after(() => rm(work, { recursive: true }));
  const context = {
    config: {
      rubric: "The final decision remains readable.",
      judge: { id: "python:arrangement_eval.py" },
    },
    providerResponse: {
      metadata: {
        work,
        diagnostics: {
          criterion: "Preserve the user's final decision.",
          payload: "/runtime",
          condition: "html",
          comparison: {
            phases: { "": "4", _before_decision: "3" },
            widths: { phone: [390, 844] },
          },
          phases: { 3: { page: "/before" }, 4: { page: "/final" } },
        },
      },
    },
  };
  let calls = 0;
  const result = await grade("Original task and user feedback", context, async () => ({
    callApi: async (prompt, { vars }) => {
      calls++;
      assert.match(prompt, /Original task and user feedback/);
      assert.equal(vars.pages.final.page, "/final");
      assert.equal(vars.pages.before_decision.page, "/before");
      return { output: { status: "pass", reason: "The final decision is readable." } };
    },
  }));
  assert.equal(calls, 1);
  assert.equal(result.pass, true);
  assert.equal(result.metadata.authoring_grade.status, "pass");
});
