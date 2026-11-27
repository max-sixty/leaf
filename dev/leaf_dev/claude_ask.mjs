/**
 * One question put to Claude, for an experiment's reader, subject or judge
 * (`dev/AGENTS.md`, "Experiments"). `system` is the model's whole system prompt and
 * `content` the blocks of one user message.
 *
 * Claude runs through the installed Agent SDK on the host's login, never an ambient
 * API key, from the system's temporary directory. It has no tools and no MCP servers,
 * and reads none of the host's settings, plugins, hooks, memory or project
 * instructions. Claude Code still adds a few lines of its own to the request, such as
 * the working directory and the date, so `system` is not quite all the model reads.
 *
 * `cost` is Claude Code's estimate of the call in dollars at API prices.
 */
import { tmpdir } from "node:os";
import { query } from "@anthropic-ai/claude-agent-sdk";

export async function ask({ model, system, content }) {
  const env = { ...process.env };
  delete env.ANTHROPIC_API_KEY;
  delete env.CLAUDE_CONFIG_DIR;
  async function* input() {
    /** @type {import("@anthropic-ai/claude-agent-sdk").SDKUserMessage} */
    const message = {
      type: "user",
      session_id: "",
      parent_tool_use_id: null,
      message: { role: "user", content },
    };
    yield message;
  }
  const run = query({
    prompt: input(),
    options: {
      model,
      cwd: tmpdir(),
      env,
      tools: [],
      allowedTools: [],
      strictMcpConfig: true,
      settingSources: [],
      settings: { autoMemoryEnabled: false, disableAllHooks: true },
      persistSession: false,
      permissionMode: "dontAsk",
      systemPrompt: system,
      maxTurns: 1,
    },
  });
  for await (const message of run) {
    if (message.type !== "result") continue;
    if (message.subtype !== "success" || message.is_error)
      throw new Error(`Claude did not complete: ${message.subtype}`);
    return { text: message.result, usage: message.usage, cost: message.total_cost_usd };
  }
  throw new Error("Claude returned no result");
}
