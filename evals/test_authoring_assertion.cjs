const assert = require("node:assert/strict");
const { test } = require("node:test");

test("visual verdicts preserve gaps and native failures through the existing provider", async () => {
  const { default: grade } = await import("../dev/leaf_dev/authoring_assertion.mjs");
  const context = {
    config: {
      phase: 2,
      rubric: "Keep the queue beside the detail.",
      judge: { id: "openai:codex-sdk", config: { model: "recorded-model" } },
    },
    providerResponse: {
      metadata: {
        diagnostics: {
          phases: {
            2: {
              captures: { narrow: ["/shots/narrow.png"] },
              observations: { limitation: "Second item unselected" },
            },
          },
        },
      },
    },
  };
  // Replace only the remote provider boundary. Prompt/schema and status transport
  // remain real; semantic calibration uses independently captured fixed controls.
  for (const status of ["pass", "defect", "insufficient_evidence"]) {
    const result = await grade(
      "Original request and messages",
      context,
      async (id, options) => {
        assert.equal(id, "openai:codex-sdk");
        assert.equal(options.options.config.model, "recorded-model");
        assert.deepEqual(options.options.config.output_schema.properties.status.enum, [
          "pass",
          "defect",
          "insufficient_evidence",
        ]);
        return {
          callApi: async (prompt) => {
            assert.match(prompt, /Second item unselected/);
            assert.match(prompt, /supported defect survives another observation gap/);
            assert.match(prompt, /version 3 also answers the comment/);
            return {
              output: { status, reason: "Recorded criterion evidence." },
              tokenUsage: { total: 12 },
            };
          },
        };
      },
    );
    assert.equal(result.metadata.authoring_grade.status, status);
    assert.equal(result.pass, status === "pass");
    assert.equal(result.tokensUsed.total, 12);
  }
  for (const response of [
    { error: "Native transport failed" },
    { output: { status: "maybe", reason: "Invalid verdict" } },
    { output: "Malformed JSON" },
  ]) {
    const result = await grade("Request", context, async () => ({
      callApi: async () => response,
    }));
    assert.equal(result.metadata.authoring_grade.status, "unscored");
    assert.equal(result.pass, false);
    assert.equal(result.metadata.authoring_grade.phase, 2);
  }
  const noImages = structuredClone(context);
  noImages.providerResponse.metadata.diagnostics.phases[2].captures.narrow = [];
  const result = await grade("Request", noImages, async () =>
    assert.fail("missing capture called model"),
  );
  assert.equal(result.metadata.authoring_grade.status, "insufficient_evidence");
  const partial = structuredClone(context);
  partial.providerResponse.metadata.diagnostics.phases[2].captures.phone = [];
  for (const status of ["pass", "defect"]) {
    const result = await grade("Request", partial, async () => ({
      callApi: async (prompt) => {
        assert.match(prompt, /No screenshots at phone/);
        assert.match(prompt, /"narrow":\["\/shots\/narrow.png"\],"phone":\[\]/);
        return { output: { status, reason: "Supported observation." } };
      },
    }));
    assert.equal(
      result.metadata.authoring_grade.status,
      status === "pass" ? "insufficient_evidence" : "defect",
    );
  }
  partial.config.required_widths = ["narrow"];
  const preference = await grade("Request", partial, async () => ({
    callApi: async () => ({
      output: { status: "pass", reason: "The required width is captured." },
    }),
  }));
  assert.equal(preference.metadata.authoring_grade.status, "pass");
});
