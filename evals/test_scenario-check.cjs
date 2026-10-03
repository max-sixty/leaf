const assert = require("node:assert/strict");
const test = require("node:test");
const path = require("node:path");
const { assertions } = require("promptfoo");

test("whole trajectories need explicit successful evidence for every declared check", async () => {
  for (const [checks, expected] of [
    [{ completed: true }, true],
    [{ completed: false }, false],
    [{ completed: 1 }, false],
    [{}, false],
    [undefined, false],
  ]) {
    const result = await assertions.runAssertions({
      test: {
        assert: [
          {
            type: "javascript",
            value: `file://${path.join(__dirname, "scenario-check.cjs")}`,
            config: { check: "completed" },
          },
        ],
      },
      providerResponse: { output: "trajectory", metadata: { checks } },
    });
    assert.equal(result.pass, expected);
  }
});
