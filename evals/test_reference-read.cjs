const assert = require("node:assert/strict");
const test = require("node:test");
const path = require("node:path");
const { assertions } = require("promptfoo");

// Fixtures use Promptfoo 0.123.1 native provider metadata: these are tool
// trajectories, not model outputs, so a failed/unfinished call must never pass.
async function check(metadata, reference = "references/page-authoring\\.md") {
  const result = await assertions.runAssertions({
    test: {
      assert: [
        {
          type: "javascript",
          value: `file://${path.join(__dirname, "reference-read.cjs")}`,
          config: { path: reference },
        },
      ],
    },
    providerResponse: { output: "Finished", metadata },
  });
  return result.pass;
}

test("completed Claude reference reads and Leaf skill delivery count", async () => {
  const read = {
    name: "Read",
    input: { file_path: "/staged/leaf/references/page-authoring.md" },
    is_error: false,
    output: [{ type: "text", text: "Page authoring instructions" }],
  };
  assert.equal(await check({ toolCalls: [read] }), true);
  for (const change of [{ is_error: true }, { output: undefined }, { output: "" }]) {
    assert.equal(await check({ toolCalls: [{ ...read, ...change }] }), false);
  }
  assert.equal(
    await check({ toolCalls: [{ ...read, input: { file_path: "/different.md" } }] }),
    false,
  );
  assert.equal(await check({ toolCalls: [{ ...read, input: {} }] }), false);
  assert.equal(
    await check(
      {
        toolCalls: [
          {
            name: "Skill",
            input: { skill: "leaf:leaf" },
            is_error: false,
            output: "Launching skill: leaf:leaf",
          },
        ],
      },
      "leaf/SKILL\\.md",
    ),
    true,
  );
  assert.equal(
    await check(
      {
        toolCalls: [
          {
            name: "Skill",
            input: { skill: "other:leaf" },
            is_error: false,
            output: "Launching skill: other:leaf",
          },
        ],
      },
      "leaf/SKILL\\.md",
    ),
    false,
  );
});

test("shell evidence requires a completed successful read of the requested reference", async () => {
  const item = {
    type: "commandExecution",
    status: "completed",
    exitCode: 0,
    aggregatedOutput: "Page authoring instructions",
  };
  const accepted = [
    "cat /staged/leaf/references/page-authoring.md",
    "/bin/zsh -lc 'sed -n \"1,120p\" /staged/leaf/references/page-authoring.md'",
    "cd /staged/leaf && head -100 references/page-authoring.md",
  ];
  for (const command of accepted) {
    assert.equal(
      await check({ codexAppServer: { items: [{ ...item, command }] } }),
      true,
    );
    assert.equal(
      await check({
        toolCalls: [
          {
            name: "Bash",
            input: { command },
            is_error: false,
            output: item.aggregatedOutput,
          },
        ],
      }),
      true,
    );
  }
  for (const command of [
    "ls references/page-authoring.md",
    "echo cat references/page-authoring.md",
    "cat different.md && echo references/page-authoring.md",
    "cat different.md | echo references/page-authoring.md",
    "cat different.md",
  ]) {
    assert.equal(
      await check({ codexAppServer: { items: [{ ...item, command }] } }),
      false,
    );
  }
  for (const change of [
    { status: "inProgress" },
    { status: "declined" },
    { exitCode: 1 },
    { aggregatedOutput: "" },
    { command: undefined },
  ]) {
    assert.equal(
      await check({
        codexAppServer: {
          items: [
            {
              ...item,
              command: accepted[0],
              ...change,
            },
          ],
        },
      }),
      false,
    );
  }
  assert.equal(await check({}), false);
});
