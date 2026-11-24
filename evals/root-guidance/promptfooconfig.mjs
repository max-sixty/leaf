/**
 * Given only Leaf's root text, the root `AGENTS.md` with the `SOUL.md` it imports, does
 * a fresh agent make the calls the maintainer has made? README.md says how to run it
 * and read the results.
 *
 * A column is one arm, a version of the root text: `head` is this working tree's, and
 * `base` is the text at the merge base with the local `main`, declared only where it
 * differs from `head`. A row is one situation in `situations.json`.
 *
 * This is a JavaScript config because the arms are read from the tree.
 */
import { execFileSync } from "node:child_process";
import { readFileSync } from "node:fs";
import path from "node:path";
import { python } from "../../dev/leaf_dev/arms.mjs";

const HERE = import.meta.dirname;
const ROOT = path.resolve(HERE, "../..");
const IMPORT = "@skills/leaf/SOUL.md\n";

const git = (...args) => execFileSync("git", args, { cwd: ROOT, encoding: "utf8" });

/**
 * The root text as `read` finds its two files: `AGENTS.md`, with the line that imports
 * `SOUL.md` replaced by that file's text below its title.
 */
function rootText(read) {
  const around = read("AGENTS.md").split(IMPORT);
  if (around.length !== 2)
    throw new Error(`AGENTS.md must import SOUL.md once, as ${IMPORT.trim()}`);
  const soul = read("skills/leaf/SOUL.md");
  return around.join(soul.slice(soul.indexOf("\n") + 1).replace(/^\n+/, ""));
}

const base = python(
  "-c",
  "import json; from leaf_dev.arms import merge_base; print(json.dumps(merge_base()))",
);
const arms = {
  base: rootText((file) => git("show", `${base}:${file}`)),
  head: rootText((file) => readFileSync(path.join(ROOT, file), "utf8")),
};
if (arms.base === arms.head) delete arms.base;

const situations = JSON.parse(readFileSync(path.join(HERE, "situations.json"), "utf8"));

export default {
  description: `Root guidance on ${git("describe", "--always", "--dirty").trim()}${
    arms.base ? `, against ${base.slice(0, 10)}` : ""
  }`,
  prompts: ["{{text}}\n\n{{ask}}"],
  providers: Object.entries(arms).map(([arm, text]) => ({
    id: "file://provider.mjs",
    label: arm,
    config: { arm, text },
  })),
  tests: situations.map(({ id, kind, source, text, ask, rubric }) => ({
    description: id,
    vars: { text, ask },
    metadata: { kind, source, rubric },
    // A metric per kind, so Promptfoo totals each arm's calls apart from its guardrails.
    assert: [{ type: "javascript", value: "file://grade.mjs", metric: kind }],
  })),
  outputPath: path.join(ROOT, ".tmp/root-guidance/results.json"),
  sharing: false,
  evaluateOptions: { maxConcurrency: 6, cache: false },
};
