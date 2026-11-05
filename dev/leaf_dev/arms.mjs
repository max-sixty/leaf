/**
 * What an experiment's Node config, provider or grader reads from `arms.py`, so model
 * ids keep their one home there (`dev/AGENTS.md`, "Experiments").
 */
import { execFileSync } from "node:child_process";
import { delimiter, resolve, sep } from "node:path";

const ROOT = resolve(import.meta.dirname, "../..");

/**
 * The JSON that Python prints given `args`, run in `leaf_dev`'s environment. `pnpm run`
 * puts this checkout's directories first on PATH, so they are left out for the child:
 * its `codex_program` finds the host's CLI, as it does under a `leaf-dev` command.
 */
export function python(...args) {
  const PATH = process.env.PATH.split(delimiter)
    .filter((entry) => !entry.startsWith(ROOT + sep))
    .join(delimiter);
  const output = execFileSync("uv", ["run", "python", ...args], {
    cwd: ROOT,
    encoding: "utf8",
    env: { ...process.env, PATH },
    stdio: ["ignore", "pipe", "inherit"],
  });
  return JSON.parse(output);
}

export const { MODELS, JUDGE_MODELS, COMPARED_MODELS } = python("-m", "leaf_dev.arms");
