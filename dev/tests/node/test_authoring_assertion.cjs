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
            brief:
              "Build a review page. Later request: keep the chosen option visible.",
            decision_task: "Select the second option and submit the review.",
            phases: { "": "4", _before_decision: "3" },
            widths: { phone: [390, 844] },
          },
          phases: { 3: { page: "/before" }, 4: { page: "/final" } },
        },
      },
    },
  };
  for (const shortTask of [false, true]) {
    const sample = structuredClone(context);
    const diagnostics = sample.providerResponse.metadata.diagnostics;
    if (shortTask) {
      delete diagnostics.criterion;
      diagnostics.condition = "leaf";
      diagnostics.comparison.brief = "Build a page whose review choices remain saved.";
      diagnostics.comparison.decision_task = null;
      diagnostics.comparison.phases = { "": "1" };
      diagnostics.phases = { 1: { page: "/final" } };
    }
    const output = shortTask
      ? "<main><h1>Review choices</h1></main>"
      : "Comment answer: the second option remains selected.";
    let calls = 0;
    const result = await grade(output, sample, async () => ({
      callApi: async (prompt, { vars }) => {
        calls++;
        assert.ok(
          prompt.includes(`Saved request and later user messages:
${diagnostics.comparison.brief}`),
        );
        assert.ok(
          prompt.includes(`Author output and feedback:
${output}`),
        );
        if (!shortTask)
          assert.match(prompt, /Select the second option and submit the review/);
        assert.match(prompt, /The final decision remains readable/);
        assert.doesNotMatch(prompt, /undefined/);
        assert.equal(vars.pages.final.page, "/final");
        assert.equal(
          vars.pages.before_decision?.page,
          shortTask ? undefined : "/before",
        );
        return {
          output: { status: "pass", reason: "The final decision is readable." },
        };
      },
    }));
    assert.equal(calls, 1);
    assert.equal(result.pass, true);
    assert.equal(result.metadata.authoring_grade.status, "pass");
  }
});
