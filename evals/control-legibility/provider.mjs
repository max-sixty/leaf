/**
 * The reader: a model shown one view, asked what each numbered control does. It sees
 * only the picture and a line about the app, never the controls' names, so its answer
 * is a first-time user's reading before hovering. `ask` gives it no tools and nothing
 * of the host's settings (`dev/leaf_dev/claude_ask.mjs`).
 */
import { readFile } from "node:fs/promises";
import { MODELS } from "../../dev/leaf_dev/arms.mjs";
import { ask } from "../../dev/leaf_dev/claude_ask.mjs";

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
  id() {
    return `control-legibility:${MODELS["claude-code"]}`;
  }
  async callApi(prompt, context) {
    const image = await readFile(context.vars.image);
    const { text, usage } = await ask({
      model: MODELS["claude-code"],
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
