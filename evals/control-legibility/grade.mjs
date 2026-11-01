/**
 * The judge: whether each control's reading names an action it stands for. A model
 * compares meanings, so "throw away my edits" matches Discard; a reading that names
 * another of the app's actions is a misreading, the failure this eval exists to find.
 *
 * The score is the share of controls read as one of their actions. The reason lists
 * every control read otherwise, with the reading, so a run says which control to fix.
 */
import { answerArray, ask } from "./provider.mjs";

const SYSTEM =
  "You compare what a user expected a control to do with what it does. Judge meaning, not wording.";

const said = (actions) => actions.map((a) => `${a.name} (${a.does})`).join(" or ");
const names = (control) => control.stands_for.map((a) => a.name).join("/");

function task(controls, readings, vocabulary) {
  return [
    "Each control below stands for the actions listed beside it, and a user who saw only the control wrote what they expected pressing it to do.",
    "For each control, give a verdict:",
    '- "matches": the reading describes one of its actions.',
    '- "misread": the reading describes something else; in "reads_as", name the app action it describes from the list below, or else that action in a few words.',
    '- "unclear": the reading says it can\'t tell, or is too vague to name an action.',
    'Answer with only a JSON array: [{"n": 1, "verdict": "matches", "reads_as": null}].',
    "",
    "The app's actions:",
    ...vocabulary.map((a) => `- ${a.name}: ${a.does}`),
    "",
    ...controls.map((control) => {
      const reading = readings.find((r) => Number(r.n) === control.n);
      return `${control.n}. Stands for: ${said(control.stands_for)}. Read as: ${reading?.does ?? "(no reading)"}`;
    }),
  ].join("\n");
}

export default async function grade(output, context) {
  const { controls, vocabulary } = context.test.metadata;
  let readings;
  try {
    readings = answerArray(output);
  } catch (error) {
    return { pass: false, score: 0, reason: `Unscored: ${error.message}` };
  }
  const { text } = await ask({
    model: context.test.vars.judgeModel,
    system: SYSTEM,
    content: [{ type: "text", text: task(controls, readings, vocabulary) }],
  });
  const verdicts = answerArray(text);
  const results = controls.map((control) => {
    const verdict = verdicts.find((v) => Number(v.n) === control.n) ?? {
      verdict: "unclear",
    };
    const reading = readings.find((r) => Number(r.n) === control.n)?.does;
    return {
      pass: verdict.verdict === "matches",
      score: verdict.verdict === "matches" ? 1 : 0,
      reason: `#${control.n} ${names(control)}: ${verdict.verdict}${
        verdict.reads_as ? ` as ${verdict.reads_as}` : ""
      } ("${reading ?? "no reading"}")`,
    };
  });
  const legible = results.filter((r) => r.pass).length;
  return {
    pass: legible === controls.length,
    score: legible / controls.length,
    namedScores: { legible: legible / controls.length },
    reason:
      results
        .filter((r) => !r.pass)
        .map((r) => r.reason)
        .join("\n") || "Every control read as one of its actions.",
    componentResults: results,
  };
}
