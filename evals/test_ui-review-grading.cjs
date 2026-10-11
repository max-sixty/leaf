/** Exercise the real Promptfoo file assertion and public provider loader. The fake
 * replaces only the external model call: it records the native request and returns
 * canned structured grades, so no subscription or network is needed for this gate.
 */
const assert = require("node:assert/strict");
const test = require("node:test");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const { assertions } = require("promptfoo");

const rubricFile = path.join(__dirname, "ui-review-detection/rubric.json");
const assertion = {
  type: "javascript",
  value: pathToFileURL(path.join(__dirname, "ui-review-detection/grade.mjs")).href,
};
const complete = {
  scorable: true,
  evidence_sufficient: true,
  target_detection: 2,
  target_false_alarm: null,
  unsupported_observations: [],
  reasoning: "The answer connects the absent anchor to ambiguous timing.",
  supporting_excerpt: "The boxes have no visible time anchor.",
};

async function sample(
  t,
  {
    condition = "no-tools",
    events = [],
    images = [0],
    source = "",
    variant = "timeline-defect",
  } = {},
) {
  const root = await fs.mkdtemp(path.join(os.tmpdir(), "ui-grade-"));
  t.after(() => fs.rm(root, { recursive: true, force: true }));
  const evidenceDir = path.join(root, "gpt-6.1-sol-private-sample");
  const gradingDir = path.join(root, "grading");
  await fs.mkdir(evidenceDir);
  const fake = path.join(root, "fake-judge.cjs");
  const callsFile = path.join(root, "calls.jsonl");
  const baseHome = path.join(root, "native-login");
  await fs.mkdir(baseHome);
  const baseProfile =
    '[permissions.screenshots.filesystem]\n":minimal" = "read"\n"/fake/bin/codex" = "read"\n';
  await fs.writeFile(path.join(baseHome, "config.toml"), baseProfile);
  await fs.writeFile(path.join(baseHome, "auth.json"), '{"dummy":"test-only login"}');
  await fs.writeFile(
    fake,
    `const fs = require('node:fs/promises');
module.exports = class {
  constructor(options) { this.config = options.config; }
  id() { return 'fake-native-judge'; }
  async callApi(prompt, context) {
    const home = this.config.working_dir;
    const codexHome = this.config.cli_env.CODEX_HOME;
    const profile = await fs.readFile(codexHome + '/config.toml', 'utf8');
    const authMode = (await fs.stat(codexHome + '/auth.json')).mode & 0o777;
    const homeMode = (await fs.stat(home)).mode & 0o777;
    await fs.appendFile(this.config.callsFile, JSON.stringify({ prompt, context, schema: this.config.output_schema, cliConfig: this.config.cli_config, home, codexHome, profile, authMode, homeMode }) + '\\n');
    if (this.config.throwError) throw Error(this.config.throwError);
    return this.config.response;
  }
};\n`,
  );
  const request =
    "Review this viewer and explain consequences, keeping observations separate from inference.\n" +
    source;
  await fs.writeFile(path.join(evidenceDir, "request.md"), request);
  await fs.writeFile(
    path.join(evidenceDir, "candidate.json"),
    JSON.stringify({
      model: "gpt-6.1-sol",
      condition,
      nativeHarness: "secret-harness",
      systemPrompt: "PRIVATE NATIVE SYSTEM PROMPT",
      manifest: {
        images: images.map((n) => `view-${n}.png`),
        evidenceLabels: images.map((n) => `Frame ${n} supplied to candidate`),
        gold: "PRIVATE GOLD SHOULD NEVER BE COPIED",
      },
      sources: source ? [{ path: "candidate.html", sha256: "source-hash" }] : [],
    }),
  );
  await fs.writeFile(
    path.join(evidenceDir, "trace.jsonl"),
    events.map((event) => JSON.stringify(event)).join("\n"),
  );
  for (const n of images)
    await fs.writeFile(
      path.join(evidenceDir, `initial-${n}.png`),
      `initial screenshot ${n}`,
    );
  const metadata = {
    gradingDir,
    rubricFile,
    privateCase: "recording-times",
    privateVariant: variant,
    mode: "recognition",
    graderProvider: {
      id: fake,
      config: {
        callsFile,
        cli_config: { model_reasoning_effort: "low" },
        cli_env: { CODEX_HOME: baseHome },
      },
    },
  };
  const providerResponse = {
    output: "The boxes have no visible time anchor, so their timing is ambiguous.",
    metadata: {
      evidenceDir,
      responseModel: "private-response-model",
      nativeHarness: "secret-harness",
    },
  };
  return {
    root,
    evidenceDir,
    gradingDir,
    baseHome,
    baseProfile,
    metadata,
    providerResponse,
    request,
    async grade(raw = complete, responseExtras = {}) {
      metadata.graderProvider.config.response = {
        output: JSON.stringify(raw),
        tokenUsage: { total: 17 },
        ...responseExtras,
      };
      return assertions.runAssertion({
        assertion,
        test: { metadata },
        providerResponse,
      });
    },
    async calls() {
      try {
        return (await fs.readFile(callsFile, "utf8"))
          .trim()
          .split("\n")
          .map(JSON.parse);
      } catch (error) {
        if (error.code === "ENOENT") return [];
        throw error;
      }
    },
    async audit() {
      return JSON.parse(
        await fs.readFile(path.join(evidenceDir, "grade.json"), "utf8"),
      );
    },
  };
}

test("real assertion sends anonymous actual evidence, preserving labels and operation order", async (t) => {
  const events = [
    { type: "request", value: { model: "gpt-6.1-sol", thoughts: "PRIVATE REQUEST" } },
    { type: "assistant", value: { thoughts: "PRIVATE NATIVE REASONING" } },
    {
      type: "tool-call",
      value: {
        name: "browser",
        id: "PRIVATE TRANSPORT ID",
        arguments: { action: "click", name: "Next" },
      },
    },
    {
      type: "tool-result",
      value: [
        {
          type: "text",
          text: '{"visibleText":"Intermediate frame","remainingOperations":11}',
        },
        { type: "image", data: "PRIVATE BINARY SUMMARY" },
      ],
    },
    { type: "tool-call", value: { action: "press", key: "ArrowLeft" } },
    {
      type: "tool-result",
      value: [
        { type: "text", text: "Previous frame" },
        { type: "image", data: "PRIVATE BINARY SUMMARY" },
      ],
    },
  ];
  for (let operation = 3; operation < 10; operation++)
    events.push(
      { type: "tool-call", value: { action: "click", name: "Unavailable" } },
      {
        type: "tool-result",
        value: [
          { type: "text", text: "Browser operation failed: no matching control" },
        ],
      },
    );
  events.push(
    { type: "tool-call", value: { action: "snapshot" } },
    {
      type: "tool-result",
      value: [
        { type: "text", text: "Final frame" },
        { type: "image", data: "PRIVATE BINARY SUMMARY" },
      ],
    },
  );
  const fixture = await sample(t, { condition: "browser", events, images: [0, 1] });
  // Captures intentionally arrive out of directory order; numeric operation order
  // still places operation 2 before 10, after all initially supplied screenshots.
  for (const n of [10, 2, 1])
    await fs.writeFile(
      path.join(fixture.evidenceDir, `browser-${n}.png`),
      `capture ${n}`,
    );
  const result = await fixture.grade();
  assert.equal(result.pass, true, result.reason);
  assert.deepEqual(result.namedScores, {
    unsupported_observations: 0,
    target_detection: 2,
  });
  assert.equal(Object.hasOwn(result.namedScores, "target_false_alarm"), false);
  const calls = await fixture.calls();
  assert.equal(calls.length, 1);
  const call = calls[0];
  assert.deepEqual(call.context, { vars: {} });
  assert.equal(call.schema.additionalProperties, false);
  assert.ok(call.schema.required.includes("target_false_alarm"));
  assert.deepEqual(call.cliConfig, { model_reasoning_effort: "low" });
  assert.equal(
    call.profile,
    fixture.baseProfile.replace(
      "[permissions.screenshots.filesystem]\n",
      `[permissions.screenshots.filesystem]\n${JSON.stringify(`${result.metadata.packetDir}/**`)} = "read"\n`,
    ),
  );
  assert.equal(call.authMode, 0o600);
  assert.equal(call.homeMode, 0o700);
  assert.equal(call.home.startsWith(fixture.gradingDir), false);
  await assert.rejects(fs.access(call.home), { code: "ENOENT" });
  assert.equal(
    await fs.readFile(path.join(fixture.baseHome, "config.toml"), "utf8"),
    fixture.baseProfile,
  );
  const content = JSON.parse(call.prompt);
  const packet = JSON.parse(content[0].text);
  assert.equal(packet.sample.request, fixture.request);
  assert.equal(packet.sample.answer, fixture.providerResponse.output);
  assert.deepEqual(packet.sample.browser_trace.slice(0, 4), [
    { operation: 1, type: "tool-call", arguments: { action: "click", name: "Next" } },
    {
      operation: 1,
      type: "tool-result",
      content: ['{"visibleText":"Intermediate frame","remainingOperations":11}'],
      hasScreenshot: true,
    },
    {
      operation: 2,
      type: "tool-call",
      arguments: { action: "press", key: "ArrowLeft" },
    },
    {
      operation: 2,
      type: "tool-result",
      content: ["Previous frame"],
      hasScreenshot: true,
    },
  ]);
  assert.deepEqual(packet.sample.browser_trace.at(-1), {
    operation: 10,
    type: "tool-result",
    content: ["Final frame"],
    hasScreenshot: true,
  });
  assert.deepEqual(
    content
      .filter((item) => item.type === "text")
      .slice(1)
      .map((item) => item.text),
    [
      "Frame 0 supplied to candidate",
      "Frame 1 supplied to candidate",
      "Browser operation 1 result screenshot",
      "Browser operation 2 result screenshot",
      "Browser operation 10 result screenshot",
    ],
  );
  const actualImages = [];
  for (const item of content.filter((item) => item.type === "local_image")) {
    assert.equal(path.dirname(path.dirname(item.path)), fixture.gradingDir);
    actualImages.push(await fs.readFile(item.path, "utf8"));
  }
  assert.deepEqual(actualImages, [
    "initial screenshot 0",
    "initial screenshot 1",
    "capture 1",
    "capture 2",
    "capture 10",
  ]);
  for (const secret of [
    "gpt-6.1-sol",
    "secret-harness",
    "private-response-model",
    "PRIVATE",
    fixture.evidenceDir,
  ])
    assert.equal(call.prompt.includes(secret), false, `Judge saw ${secret}`);
  const audit = await fixture.audit();
  assert.equal(audit.rawGrade.target_false_alarm, null);
  assert.equal(audit.candidateIdentity.requestedModel, "gpt-6.1-sol");
  assert.equal(audit.evidence.length, 5);
  assert.match(audit.rubric.sha256, /^[a-f0-9]{64}$/);
  assert.equal(audit.judge.status, "completed");
  assert.equal(typeof audit.judge.elapsedMs, "number");
  assert.equal(audit.result.metadata.grade.scorable, true);
  assert.deepEqual(
    JSON.parse(
      await fs.readFile(path.join(result.metadata.packetDir, "raw-grade.json"), "utf8"),
    ),
    complete,
  );
});

test("code-only sends the complete source without image or browser claims", async (t) => {
  const source =
    '<file path="candidate.html">\n' +
    "const pinnedDependency = true;\n".repeat(15000) +
    "</file>";
  const fixture = await sample(t, { condition: "code-only", images: [], source });
  const result = await fixture.grade();
  assert.equal(result.pass, true, result.reason);
  const content = JSON.parse((await fixture.calls())[0].prompt);
  assert.equal(content.length, 1);
  const packet = JSON.parse(content[0].text);
  assert.equal(packet.sample.request, fixture.request);
  assert.equal(
    packet.rubric.source_only,
    JSON.parse(await fs.readFile(rubricFile, "utf8")).source_only,
  );
  assert.deepEqual(packet.sample.browser_trace, []);
});

test("labelled-transition controls reach the judge with their supplied sequence and no personal tool trace", async (t) => {
  const controls = JSON.parse(
    await fs.readFile(
      path.join(__dirname, "ui-review-detection/grader-controls.json"),
      "utf8",
    ),
  );
  const labels = [
    "Initial view",
    "After enabling Show intermediate frames",
    "After activating Next once",
  ];
  for (const control of controls.controls.filter(
    (item) => item.privateCase === "recording-stepping",
  )) {
    const fixture = await sample(t, {
      condition: control.condition,
      variant: control.privateVariant,
      images: [0, 1, 2],
    });
    fixture.metadata.privateCase = control.privateCase;
    const candidateFile = path.join(fixture.evidenceDir, "candidate.json");
    const candidate = JSON.parse(await fs.readFile(candidateFile, "utf8"));
    candidate.manifest.evidenceLabels = labels;
    await fs.writeFile(candidateFile, JSON.stringify(candidate));
    fixture.providerResponse.output = JSON.stringify(control.answer);
    const expected = {
      ...complete,
      ...control.expected,
      unsupported_observations: control.expected.unsupported_observations
        ? ["Claims twenty personal browser interactions absent from trace"]
        : [],
    };
    const result = await fixture.grade(expected);
    assert.equal(result.metadata.grade.scorable, true, result.reason);
    assert.equal(result.pass, control.expected.unsupported_observations === 0);
    const content = JSON.parse((await fixture.calls())[0].prompt);
    const packet = JSON.parse(content[0].text);
    assert.equal(packet.sample.answer, JSON.stringify(control.answer));
    assert.deepEqual(packet.sample.browser_trace, []);
    assert.deepEqual(
      content
        .filter((item) => item.type === "text")
        .slice(1)
        .map((item) => item.text),
      labels,
    );
  }
});

test("raw metrics retain their ranges and controls allow residual findings", async (t) => {
  const defect = await sample(t);
  const partial = await defect.grade({ ...complete, target_detection: 1 });
  assert.equal(partial.pass, false);
  assert.equal(partial.namedScores.target_detection, 1);
  const invented = await defect.grade({
    ...complete,
    unsupported_observations: ["Claims an unperformed drag"],
  });
  assert.equal(invented.pass, false);
  assert.equal(invented.namedScores.unsupported_observations, 1);
  const control = await sample(t, { variant: "timeline-control" });
  const clean = await control.grade({
    ...complete,
    target_detection: null,
    target_false_alarm: 0,
    reasoning:
      "Criticizes residual clutter, while recognizing the visible timing anchors.",
  });
  assert.equal(clean.pass, true, clean.reason);
  assert.deepEqual(clean.namedScores, {
    unsupported_observations: 0,
    target_false_alarm: 0,
  });
  const falseAlarm = await control.grade({
    ...complete,
    target_detection: null,
    target_false_alarm: 1,
  });
  assert.equal(falseAlarm.pass, false);
  assert.equal(falseAlarm.namedScores.target_false_alarm, 1);
});

test("insufficient evidence, invalid grades and native failures never become scored misses", async (t) => {
  const fixture = await sample(t);
  for (const raw of [
    {
      ...complete,
      scorable: false,
      evidence_sufficient: false,
      target_detection: null,
    },
    { ...complete, target_detection: 3 },
    { ...complete, unexpected: "field" },
    { ...complete, target_detection: null, target_false_alarm: 0 },
  ]) {
    const result = await fixture.grade(raw);
    assert.equal(result.metadata.scorable, false, result.reason);
    assert.deepEqual(result.namedScores, {});
    assert.match(result.reason, /^Unscored:/);
  }
  for (const response of [
    { error: "Native judge transport failed" },
    { output: "not JSON" },
  ]) {
    const result = await fixture.grade(complete, response);
    assert.equal(result.metadata.scorable, false, result.reason);
    assert.deepEqual(result.namedScores, {});
  }
  fixture.metadata.graderProvider.config.throwError = "Native judge exception";
  const thrown = await fixture.grade();
  assert.equal(thrown.metadata.scorable, false, thrown.reason);
  assert.deepEqual(thrown.namedScores, {});
  assert.equal((await fixture.calls()).length, 7);
  for (const call of await fixture.calls())
    await assert.rejects(fs.access(call.home), { code: "ENOENT" });
});

test("unobservable tool-free targets and broken evidence are explicitly unscored", async (t) => {
  const fixture = await sample(t);
  fixture.metadata.noToolsTargetUnobservable = true;
  fixture.metadata.mode = "discovery";
  const result = await fixture.grade();
  assert.equal(result.metadata.scorable, false);
  assert.equal(result.metadata.grade.scorable, false);
  assert.equal(result.metadata.grade.target_detection, null);
  assert.equal(result.metadata.rawGrade.target_detection, 2);
  assert.deepEqual(result.namedScores, {});
  assert.equal((await fixture.calls()).length, 1);
  const broken = await sample(t, {
    condition: "browser",
    events: [
      { type: "tool-call", value: { action: "snapshot" } },
      {
        type: "tool-result",
        value: [
          { type: "text", text: '{"remainingOperations":11}' },
          { type: "image", data: "screenshot" },
        ],
      },
    ],
  });
  const missingCapture = await broken.grade();
  assert.equal(missingCapture.metadata.scorable, false, missingCapture.reason);
  assert.deepEqual(missingCapture.namedScores, {});
  assert.equal((await broken.calls()).length, 0);
  const failed = await sample(t);
  failed.providerResponse.error = "Candidate did not complete";
  const failure = await failed.grade();
  assert.equal(failure.metadata.scorable, false, failure.reason);
  assert.equal((await failed.calls()).length, 0);
});
