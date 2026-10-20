/**
 * One disposable native home per judge call, with the caller's evidence grant.
 * Python owns the profile and login setup shared with other native evals; the
 * native Promptfoo provider owns execution, schema handling, tokens and cost.
 */
import { execFile } from "node:child_process";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { promisify } from "node:util";
import { loadApiProvider } from "promptfoo";

const execute = promisify(execFile);

export default class ScreenshotJudge {
  constructor(options) {
    this.config = options.config;
  }

  id() {
    // Promptfoo identifies agent-rubric runtimes by their native provider prefix.
    return "openai:codex-sdk:screenshots";
  }

  async callApi(prompt, context, callOptions) {
    const home = await mkdtemp(join(tmpdir(), "leaf-screenshot-judge-"));
    let provider;
    try {
      const { pythonExecutable, ...config } = this.config;
      const { stdout } = await execute(pythonExecutable, [
        fileURLToPath(new URL("./screenshot_judge.py", import.meta.url)),
        home,
        JSON.stringify(config),
      ]);
      provider = await loadApiProvider("openai:codex-sdk", {
        options: { config: JSON.parse(stdout) },
      });
      return await provider.callApi(prompt, context, callOptions);
    } finally {
      try {
        await provider?.cleanup();
      } finally {
        await rm(home, { recursive: true });
      }
    }
  }
}
