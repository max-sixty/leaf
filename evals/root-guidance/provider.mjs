/**
 * The subject: a model whose whole instructions are one arm's root text, asked what it
 * does in one situation. It answers in two lines: `DO`, what it does, and `PASSAGE`,
 * the words of the root text that most decided it, which a reader of a failure looks
 * for first.
 */
import { MODELS } from "../../dev/leaf_dev/arms.mjs";
import { ask } from "../../dev/leaf_dev/claude_ask.mjs";

const frame = (text) =>
  `You are an agent working in the Leaf repository for its maintainer. The text between the markers is every instruction you have about Leaf.\n\n=== INSTRUCTIONS ===\n${text}\n=== END INSTRUCTIONS ===\n`;

const FORM =
  'Reply in exactly this form and nothing else:\nDO: <what you do, at most 90 words>\nPASSAGE: "<the words from your instructions that most decide this, at most 30 words, verbatim>" or none';

export default class RootGuidanceSubject {
  constructor({ config }) {
    this.config = config;
  }
  id() {
    return `root-guidance:${MODELS["claude-code"]}:${this.config.arm}`;
  }
  async callApi(prompt) {
    const { text, usage, cost } = await ask({
      model: MODELS["claude-code"],
      system: frame(this.config.text),
      content: [{ type: "text", text: `${prompt}\n\n${FORM}` }],
    });
    return {
      output: text,
      cost,
      tokenUsage: {
        prompt:
          usage.input_tokens +
          usage.cache_read_input_tokens +
          usage.cache_creation_input_tokens,
        completion: usage.output_tokens,
        cached: usage.cache_read_input_tokens,
      },
    };
  }
}
