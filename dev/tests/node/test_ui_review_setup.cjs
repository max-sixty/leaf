/** Opt-in smoke of the UI review config's setup on its real fixtures; no model is invoked. */
const assert = require("node:assert/strict");
const { readFile, stat } = require("node:fs/promises");
const { join } = require("node:path");
const { test } = require("node:test");

test("setup captures every candidate's frozen contrast into a packet", async (t) => {
  const { default: config } =
    await import("../../../evals/ui-review-detection/promptfooconfig.mjs");
  const { afterAll, beforeAll } =
    await import("../../../evals/ui-review-detection/hooks.mjs");
  t.after(() => afterAll({ results: [], suite: config }));
  await beforeAll({ suite: config });
  for (const { vars, description } of config.tests) {
    const packet = join(config.defaultTest.metadata.run, "candidates", vars.candidate);
    const { site, ...evidence } = JSON.parse(
      await readFile(join(packet, "input.json"), "utf8"),
    );
    assert.ok((await stat(site)).isDirectory());
    assert.ok(evidence.images.length > 1, description);
    assert.equal(evidence.images.length, evidence.evidenceLabels.length);
    assert.ok(evidence.sources.length > 0, description);
    for (const file of [...evidence.images, ...evidence.sources.map((s) => s.file)])
      assert.ok((await stat(join(packet, file))).size > 0, file);
    // Nothing a reviewer receives says which side of its pair a candidate is.
    assert.doesNotMatch(JSON.stringify(evidence), /defect|control/i, description);
  }
});
