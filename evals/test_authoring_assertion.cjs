const assert = require("node:assert/strict");
const { mkdtemp, rm } = require("node:fs/promises");
const { tmpdir } = require("node:os");
const { join } = require("node:path");
const { test } = require("node:test");

test("live verdicts select the saved phase and preserve gaps and native failures", async () => {
  const { default: grade } = await import("../dev/leaf_dev/authoring_assertion.mjs");
  const work = await mkdtemp(join(tmpdir(), "leaf-judge-test-"));
  try {
    const context = {
      config: {
        phase: 2,
        rubric: "Keep the queue beside the detail.",
        judge: {
          id: "python:arrangement_eval.py",
          config: { pythonExecutable: "python" },
        },
      },
      providerResponse: {
        metadata: {
          work,
          diagnostics: {
            payload: "/runtime",
            condition: "html",
            widths: { narrow: [900, 900], phone: [390, 844] },
            phases: { 2: { page: "/samples/page-phase2", captures: {} } },
          },
        },
      },
    };
    // Replace only the model provider. Real browser/calibration checks exercise
    // exploration; this holds phase selection and Promptfoo's typed result boundary.
    for (const status of ["pass", "defect", "insufficient_evidence"]) {
      const result = await grade(
        "Original request and messages",
        context,
        async (id, options) => {
          assert.equal(id, "python:arrangement_eval.py");
          assert.equal(options.options.config.pythonExecutable, "python");
          return {
            callApi: async (prompt, request) => {
              assert.match(prompt, /version 3 also answers the comment/);
              assert.equal(request.vars.page, "/samples/page-phase2");
              assert.equal(request.vars.payload, "/runtime");
              assert.deepEqual(
                request.vars.widths,
                context.providerResponse.metadata.diagnostics.widths,
              );
              assert.deepEqual(request.vars.schema.properties.status.enum, [
                "pass",
                "defect",
                "insufficient_evidence",
              ]);
              assert.ok(request.vars.evidence.startsWith(work));
              return {
                output: { status, reason: "Observed criterion evidence." },
                tokenUsage: { total: 12 },
                metadata: { evidence: request.vars.evidence },
              };
            },
          };
        },
      );
      assert.equal(result.metadata.authoring_grade.status, status);
      assert.equal(result.pass, status === "pass");
      assert.equal(result.tokensUsed.total, 12);
      assert.ok(result.metadata.judge.metadata.evidence.startsWith(work));
    }
    for (const response of [
      { error: "Native transport failed", metadata: { evidence: work } },
      { output: { status: "maybe", reason: "Invalid verdict" } },
      { output: "Malformed JSON" },
    ]) {
      const result = await grade("Request", context, async () => ({
        callApi: async () => response,
      }));
      assert.equal(result.metadata.authoring_grade.status, "unscored");
      assert.equal(result.pass, false);
    }
    const missing = structuredClone(context);
    delete missing.providerResponse.metadata.diagnostics.phases[2].page;
    const absent = await grade("Request", missing, async () =>
      assert.fail("No page called model"),
    );
    assert.equal(absent.metadata.authoring_grade.status, "insufficient_evidence");
    context.config.required_widths = ["narrow"];
    const preference = await grade("Request", context, async () => ({
      callApi: async (_, request) => {
        assert.deepEqual(request.vars.widths, { narrow: [900, 900] });
        return { output: { status: "pass", reason: "Required viewport explored." } };
      },
    }));
    assert.equal(preference.metadata.authoring_grade.status, "pass");
  } finally {
    await rm(work, { recursive: true });
  }
});
