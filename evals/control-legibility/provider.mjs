/**
 * The reader: a model shown one view, asked what each numbered control does. It sees
 * only the picture and a line about the app, never the controls' names, so its answer
 * is a first-time user's reading before hovering. `ask` is also the judge's transport
 * (grade.mjs).
 *
 * Claude runs through the installed Agent SDK with no tools, no settings, hooks or
 * memory, and no ambient API key, so it reads the picture on the host's login alone.
 */
import { readFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { query } from "@anthropic-ai/claude-agent-sdk";

export async function ask({ model, system, content }) {
  const env = { ...process.env };
  delete env.ANTHROPIC_API_KEY;
  delete env.CLAUDE_CONFIG_DIR;
  async function* input() {
    yield {
      type: "user",
      session_id: "",
      parent_tool_use_id: null,
      message: { role: "user", content },
    };
  }
  const run = query({
    prompt: input(),
    options: {
      model,
      cwd: tmpdir(),
      env,
      tools: [],
      allowedTools: [],
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
    return { text: message.result, usage: message.usage };
  }
  throw new Error("Claude returned no result");
}

/** The JSON array a model's answer holds, whatever prose or fence surrounds it. */
export function answerArray(text) {
  const start = text.indexOf("[");
  const end = text.lastIndexOf("]");
  if (start < 0 || end < start) throw new Error(`No JSON array in: ${text}`);
  return JSON.parse(text.slice(start, end + 1));
}

const SYSTEM =
  "You are a first-time user of a web app, looking at part of its interface. Small magenta numbers label its controls; they are annotations, not part of the app.";

const TASK =
  'For each numbered control, say in a few words what you expect pressing it does, judging only from how it looks, as you would before hovering it. Where you can\'t tell, say so. Answer with only a JSON array: [{"n": 1, "does": "..."}].';

export default class ControlLegibilityReader {
  constructor(options = {}) {
    this.config = options.config ?? {};
  }
  id() {
    return `control-legibility:${this.config.model}`;
  }
  async callApi(prompt, context) {
    const image = await readFile(context.vars.image);
    const { text, usage } = await ask({
      model: this.config.model,
      system: SYSTEM,
      content: [
        {
          type: "image",
          source: {
            type: "base64",
            media_type: "image/png",
            data: image.toString("base64"),
          },
        },
        { type: "text", text: `${prompt}\n\n${TASK}` },
      ],
    });
    return {
      output: text,
      tokenUsage: {
        prompt: usage?.input_tokens,
        completion: usage?.output_tokens,
      },
    };
  }
}
