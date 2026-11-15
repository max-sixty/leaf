/**
 * Does a reviewer find a defect Leaf's UI work missed, and leave its repaired control
 * alone? README.md says how to run it and read the results.
 *
 * A column is one model on one arm, and `--filter-providers` selects among them. A row
 * is one candidate of a frozen defect/control pair. `hooks.mjs` prepares each run's
 * candidates and summarises its grades.
 *
 * This is a JavaScript config because the columns come from the model pins in
 * `arms.py`: each harness's author and judge, and the compared models.
 */
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { parse } from "yaml";
import { COMPARED_MODELS, JUDGE_MODELS, MODELS } from "../../dev/leaf_dev/arms.mjs";

const HERE = import.meta.dirname;
const ROOT = path.resolve(HERE, "../..");

// Evals on the host's logins must not silently switch to ambient API billing.
for (const key of [
  "OPENAI_API_KEY",
  "CODEX_API_KEY",
  "ANTHROPIC_API_KEY",
  "CLAUDE_CONFIG_DIR",
])
  delete process.env[key];

const RUN = path.join(
  ROOT,
  ".tmp/ui-review-detection",
  new Date().toISOString().replaceAll(":", "-"),
);
const COMMIT = execFileSync("git", ["describe", "--always", "--dirty"], {
  cwd: ROOT,
  encoding: "utf8",
}).trim();

/** The evidence each arm gives a reviewer (README.md, "Arms"). */
const ARMS = {
  "no-tools": { condition: "no-tools" },
  browser: { condition: "browser" },
  discovery: { condition: "browser", mode: "discovery" },
  "code-only": { condition: "code-only" },
};
const REVIEWERS = new Set([
  ...Object.entries(JUDGE_MODELS).flatMap(([harness, judge]) => [
    MODELS[harness],
    judge,
  ]),
  ...COMPARED_MODELS,
]);

const { cases } = parse(readFileSync(path.join(HERE, "cases.yaml"), "utf8"));
const { variants } = JSON.parse(
  readFileSync(path.join(HERE, "fixtures/private/provenance.json"), "utf8"),
);

export default {
  description: `UI review on ${COMMIT}`,
  prompts: ["{{prompt}}"],
  extensions: ["file://hooks.mjs:beforeAll", "file://hooks.mjs:afterAll"],
  providers: [...REVIEWERS].flatMap((model) =>
    Object.entries(ARMS).map(([arm, evidence]) => ({
      id: "file://provider.mjs",
      label: `${model}/${arm}`,
      config: { model, ...evidence, run: RUN },
    })),
  ),
  defaultTest: {
    metadata: {
      run: RUN,
      gradingDir: path.join(RUN, "grading"),
      rubricFile: path.join(HERE, "rubric.json"),
    },
    assert: [{ type: "javascript", value: "file://grade.mjs", metric: "ui-review" }],
  },
  tests: Object.entries(variants).map(([variant, candidate]) => {
    const [name, task] = Object.entries(cases).find(
      ([, { family }]) => family === variant.split("-")[0],
    );
    return {
      description: variant,
      // Vars that stay the same from run to run, so Promptfoo matches a row across
      // runs, as its viewer and `--filter-failing` do.
      vars: { prompt: task.prompt, candidate },
      metadata: {
        sourceFiles: task.source_files,
        privateCase: name,
        privateVariant: variant,
      },
    };
  }),
  outputPath: path.join(RUN, "results.json"),
  sharing: false,
  evaluateOptions: { maxConcurrency: 2, showProgressBar: false, cache: false },
};
