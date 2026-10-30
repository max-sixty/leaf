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
  /** @type {Record<string, string>} */
  const phaseIds = { "": "5", _before_decision: "3", _before_revision: "4" };
  /** @type {Record<string, { page?: string }>} */
  const phases = {
    3: { page: "/before" },
    4: { page: "/recorded" },
    5: { page: "/final" },
  };
  const context = {
    config: {
      rubric: "The final decision remains readable.",
      judge: { id: "python:arrangement_eval.py" },
    },
    providerResponse: {
      metadata: {
        work,
        checks: { completed: true, page: true },
        diagnostics: {
          criterion: "Preserve the user's final decision.",
          payload: "/runtime",
          condition: "html",
          decision: {
            route: "copied",
            gestures: [],
            message: "Keep the second option and record my additional review note.",
          },
          comparison: {
            brief:
              "Build a review page. Later request: keep the chosen option visible.",
            decision_task: "Select the second option and submit the review.",
            phases: phaseIds,
            widths: { phone: [390, 844] },
          },
          phases,
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
      id: () => "test judge",
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
        assert.deepEqual(
          vars.handovers,
          shortTask ? {} : { final: diagnostics.decision },
        );
        assert.deepEqual(vars.pages, {
          final: {
            page: "/final",
            payload: "/runtime",
            condition: diagnostics.condition,
          },
          ...(shortTask
            ? {}
            : {
                before_decision: {
                  page: "/before",
                  payload: "/runtime",
                  condition: diagnostics.condition,
                },
                before_revision: {
                  page: "/recorded",
                  payload: "/runtime",
                  condition: diagnostics.condition,
                },
              }),
        });
        return {
          output: { status: "pass", reason: "The final decision is readable." },
        };
      },
    }));
    assert.equal(calls, 1);
    assert.equal(result.pass, true);
    assert.equal(result.metadata.authoring_grade.status, "pass");
  }

  // The same missing output means different things after a native failure or completion.
  const missing = structuredClone(context);
  delete missing.providerResponse.metadata.diagnostics.phases[5].page;
  missing.providerResponse.metadata.checks.page = false;
  let unexpectedCalls = 0;
  const unexpectedJudge = async () => {
    unexpectedCalls++;
    throw new Error("Missing output must not reach the judge.");
  };
  missing.providerResponse.metadata.checks.completed = false;
  const incomplete = await grade("Original task", missing, unexpectedJudge);
  assert.equal(incomplete.metadata.authoring_grade.status, "unscored");
  assert.match(incomplete.reason, /Native author did not complete/);
  missing.providerResponse.metadata.checks.completed = true;
  const completedWithoutPage = await grade("Original task", missing, unexpectedJudge);
  assert.equal(
    completedWithoutPage.metadata.authoring_grade.status,
    "insufficient_evidence",
  );
  assert.equal(unexpectedCalls, 0);
});
