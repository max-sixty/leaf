/**
 * Promptfoo's setup and teardown for one run. Setup builds the public site, then
 * captures each selected candidate's labelled views and source into its packet and
 * asserts the historical contrast there, so a run whose fixture no longer shows its
 * defect or its repair stops before any model is called. It also seeds the judge's
 * home with the host's Codex login. Teardown retires that seed and counts each
 * column's grades, leaving out what could not be scored.
 */
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import { cp, mkdir, mkdtemp, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import { chromium } from "playwright";
import { python } from "../../dev/leaf_dev/arms.mjs";
import { ORIGIN, candidateContext } from "./provider.mjs";

const FIXTURES = path.join(import.meta.dirname, "fixtures");
const ROOT = path.resolve(import.meta.dirname, "../..");

async function stageSite(site) {
  await cp(path.join(FIXTURES, "public"), site, { recursive: true });
  // The recorded viewer's timeline library has left the tree; history keeps its bytes.
  const { dependency } = JSON.parse(
    await readFile(path.join(FIXTURES, "private/provenance.json"), "utf8"),
  );
  await writeFile(
    path.join(site, "assets/timeline.esm.js"),
    execFileSync("git", ["show", `${dependency.commit}:${dependency.path}`], {
      cwd: ROOT,
    }),
  );
}

/** A family's journey through its candidate, asserting the contrast it was frozen for. */
const JOURNEYS = {
  async timeline(page, screenshot, defect) {
    const events = page.locator(".vis-item.vis-box");
    assert.equal(await events.count(), 9);
    for (const event of await events.all()) assert.ok(await event.isVisible());
    assert.ok((await page.locator(".vis-text.vis-minor").count()) >= 5);
    let anchors = 0;
    for (const dot of await page.locator(".vis-dot").all())
      if (await dot.isVisible()) anchors++;
    assert.equal(anchors, defect ? 0 : 9);
    await page.getByRole("button", { name: "Press t · 1.650 s", exact: true }).click();
    await screenshot("After selecting the later t input marker");
    assert.match(await page.locator("#readout").innerText(), /1\.650 s/);
  },
  async shift(page, screenshot, defect) {
    const widget = page.locator("lf-trace");
    const image = widget.locator("img");
    await image.waitFor();
    const before = await image.boundingBox();
    await widget.getByRole("checkbox", { name: "Show intermediate frames" }).check();
    await screenshot("After enabling Show intermediate frames");
    await widget.getByRole("button", { name: "Next", exact: true }).click();
    await screenshot("After activating Next once");
    const shift = Math.abs((await image.boundingBox()).y - before.y);
    assert.ok(defect ? shift > 20 : shift < 0.1, `image moved ${shift}px`);
  },
  edge: (page, screenshot, defect) =>
    laterControls(page, screenshot, (reading) =>
      assert.equal(reading.edgeGap > 60, defect),
    ),
  cover: (page, screenshot, defect) =>
    laterControls(page, screenshot, (reading) => {
      assert.ok(Math.abs(reading.edgeGap) < 1);
      assert.equal(reading.hit, !defect);
    }),
  async press(page, screenshot, defect) {
    const first = page.locator(".msg.first");
    await first.locator(".text").hover();
    await screenshot("Pointer over the first message");
    await first.locator(".copy").click();
    await screenshot("After pressing Copy on the first message");
    await page.locator(".msg.agent .text li").first().hover();
    await screenshot("After moving the pointer onto the agent's reply");
    const shown = await first
      .locator(".copy")
      .evaluate((copy) => getComputedStyle(copy).opacity);
    assert.equal(shown === "1", defect);
  },
};

async function laterControls(page, screenshot, check) {
  const later = page.locator(".msg.later.user");
  await page.locator(".msg.agent .text li").first().hover();
  await screenshot("Pointer over the agent's reply");
  await later.locator(".text").hover();
  await screenshot("Pointer over the later reply from Me");
  const reading = await later.locator(".copy").evaluate((copy) => {
    const box = copy.getBoundingClientRect();
    const close = document.querySelector(".actions .close").getBoundingClientRect();
    return {
      opacity: getComputedStyle(copy).opacity,
      edgeGap: close.right - box.right,
      hit: copy.contains(
        document.elementFromPoint(box.x + box.width / 2, box.y + box.height / 2),
      ),
    };
  });
  assert.equal(reading.opacity, "1");
  check(reading);
}

/** Write one candidate's packet: every arm's evidence, which the provider selects from. */
async function capture(browser, run, test) {
  const { candidate } = test.vars;
  const { sourceFiles, privateVariant: variant } = test.metadata;
  const site = path.join(run, "site");
  const packet = path.join(run, "candidates", candidate);
  await mkdir(packet, { recursive: true });
  const url = `${ORIGIN}/${candidate}.html`;
  const context = await candidateContext(browser, { site, url });
  const page = await context.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(String(error)));
  await page.goto(url);
  await page.waitForFunction(() => window.__fixtureReady === true);
  const images = [];
  const evidenceLabels = [];
  async function screenshot(label) {
    const file = `view-${images.length}.png`;
    await page.screenshot({ path: path.join(packet, file) });
    images.push(file);
    evidenceLabels.push(label);
  }
  await screenshot("Initial view");
  try {
    await JOURNEYS[variant.split("-")[0]](page, screenshot, variant.endsWith("defect"));
    assert.doesNotMatch(await page.locator("body").innerText(), /undefined/);
    assert.deepEqual(errors, []);
  } catch (error) {
    throw new Error(`${variant} lost its frozen contrast: ${error.message}`, {
      cause: error,
    });
  }
  await context.close();
  const sources = [];
  for (const template of sourceFiles) {
    const name = template.replace("{candidate}", candidate);
    const file = path.join("source", name);
    await cp(path.join(site, name), path.join(packet, file));
    sources.push({ path: name, file });
  }
  await writeFile(
    path.join(packet, "input.json"),
    JSON.stringify({ images, evidenceLabels, sources, site, url }, null, 2) + "\n",
  );
}

export async function beforeAll({ suite }) {
  const { metadata } = suite.defaultTest;
  await stageSite(path.join(metadata.run, "site"));
  const browser = await chromium.launch({ channel: "chromium", headless: true });
  try {
    for (const test of suite.tests) await capture(browser, metadata.run, test);
  } finally {
    await browser.close();
  }
  const login = path.join(
    await mkdtemp(path.join(tmpdir(), "leaf-ui-grader-")),
    ".codex",
  );
  metadata.graderProvider = python(
    "-c",
    `
import json, sys
from pathlib import Path
from leaf_dev.screenshot_judge import screenshot_judge
print(json.dumps(screenshot_judge(None, Path(sys.argv[1]))))
`,
    login,
  );
}

/** One column's counts. A missing grade is a harness or judge failure, not a miss. */
function column(rows) {
  const scored = rows.filter((row) => row.scorable);
  const grades = (kind) =>
    scored.filter((row) => row.variant.endsWith(kind)).map((row) => row.grade);
  const defects = grades("defect");
  const controls = grades("control");
  const detected = (level) =>
    defects.filter((grade) => grade.target_detection === level).length;
  return {
    samples: rows.length,
    scored: scored.length,
    unscored: rows.length - scored.length,
    defects: defects.length,
    detected: detected(2),
    concerns: detected(1),
    missed: detected(0),
    controls: controls.length,
    target_false_alarms: controls.filter((grade) => grade.target_false_alarm).length,
    unsupported_observations: scored.reduce(
      (count, row) => count + row.grade.unsupported_observations.length,
      0,
    ),
  };
}

export async function afterAll({ results, suite }) {
  const { run, graderProvider } = suite.defaultTest.metadata;
  await rm(path.dirname(graderProvider.config.login), { recursive: true });
  const rows = results.map((result) => {
    const grade =
      result.gradingResult?.componentResults?.find(
        (component) => component.metadata?.grade,
      )?.metadata.grade ?? null;
    return {
      variant: result.testCase.metadata.privateVariant,
      provider: result.provider.label,
      sample: result.response?.metadata?.evidenceDir,
      grade,
      scorable: Boolean(grade?.scorable),
      error: grade ? null : result.error,
    };
  });
  const summary = { columns: {}, rows };
  for (const label of new Set(rows.map((row) => row.provider))) {
    const counts = column(rows.filter((row) => row.provider === label));
    summary.columns[label] = counts;
    console.log(
      `${label}: graded ${counts.scored}/${counts.samples}; ` +
        `detected ${counts.detected}/${counts.defects} defects ` +
        `(${counts.concerns} partial, ${counts.missed} missed); ` +
        `${counts.target_false_alarms}/${counts.controls} control false alarms; ` +
        `${counts.unsupported_observations} unsupported observations; ` +
        `${counts.unscored} unscored.`,
    );
  }
  await writeFile(
    path.join(run, "grading-summary.json"),
    JSON.stringify(summary, null, 2) + "\n",
  );
  console.log(`Evidence: ${run}\nview: pnpm run eval:view`);
}
