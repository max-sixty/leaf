/**
 * The judge: whether an answer makes the call its situation's rubric describes. It
 * reads the situation, the answer and the rubric, never the root text, and replies
 * `PASS` or `FAIL` with a reason, which is the assertion's reason.
 *
 * Promptfoo's cost counts the subject's calls only, so the result's metadata carries
 * what the judge's call cost.
 */
import { JUDGE_MODELS } from "../../dev/leaf_dev/arms.mjs";
import { ask } from "../../dev/leaf_dev/claude_ask.mjs";

const SYSTEM =
  "You grade one answer against a rubric. Read the situation, the answer and the rubric. Reply with exactly one line: PASS or FAIL, then a dash and at most 15 words of reason. Grade what the answer does, not how well it argues.";

export default async function grade(output, context) {
  const { text, ask: question } = context.vars;
  const verdict = await ask({
    model: JUDGE_MODELS["claude-code"],
    system: SYSTEM,
    content: [
      {
        type: "text",
        text: `Situation:\n${text}\n\nQuestion: ${question}\n\nAnswer:\n${output}\n\nRubric: ${context.test.metadata.rubric}`,
      },
    ],
  });
  const reason = verdict.text.trim();
  const pass = reason.toUpperCase().startsWith("PASS");
  return { pass, score: pass ? 1 : 0, reason, metadata: { cost: verdict.cost } };
}
