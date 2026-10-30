/** One live agent grades the final result and its predecision controls. */
import { mkdtemp } from "node:fs/promises";
import { join } from "node:path";
import { loadApiProvider } from "promptfoo";
import { z } from "zod";

const Verdict = z.strictObject({
  status: z.enum(["pass", "defect", "insufficient_evidence"]),
  reason: z.string().min(1),
});

export default async function grade(output, context, load = loadApiProvider) {
  let response;
  const result = (verdict) => ({
    pass: verdict.status === "pass",
    score: Number(verdict.status === "pass"),
    reason: `${verdict.status}: ${verdict.reason}`,
    ...(response?.tokenUsage ? { tokensUsed: response.tokenUsage } : {}),
    metadata: {
      authoring_grade: verdict,
      ...(response ? { judge: response } : {}),
    },
  });
  try {
    if (context.providerResponse.error) throw new Error(context.providerResponse.error);
    const { diagnostics, work, checks } = context.providerResponse.metadata;
    if (!checks.completed)
      throw new Error(
        "Native author did not complete; inspect retained native evidence.",
      );
    const pages = Object.fromEntries(
      Object.entries(diagnostics.comparison.phases).map(([suffix, phase]) => [
        suffix ? "before_decision" : "final",
        {
          page: diagnostics.phases[phase].page,
          payload: diagnostics.payload,
          condition: diagnostics.condition,
        },
      ]),
    );
    if (Object.values(pages).some((page) => !page.page))
      return result({
        status: "insufficient_evidence",
        reason: "A required saved page is missing.",
      });
    const evidence = await mkdtemp(join(work, "judge-"));
    const provider = await load(context.config.judge.id, {
      options: context.config.judge,
    });
    const prompt = `Judge the completed task against this criterion:
${diagnostics.criterion ?? ""}
${context.config.rubric}

Saved request and later user messages:
${diagnostics.comparison.brief}

Original browser decision task:
${diagnostics.comparison.decision_task ?? ""}

Author output and feedback:
${output}

The final page is the author's result after all user feedback. The optional
before_decision page is for operating its decision controls. Apply only feedback
that exists for this task. Use pass when observation establishes the criterion,
defect for a supported user-facing failure, or insufficient_evidence when
exploration cannot settle it.`;
    response = await provider.callApi(prompt, {
      prompt: { raw: prompt, label: context.config.rubric },
      vars: {
        pages,
        widths: diagnostics.comparison.widths,
        schema: z.toJSONSchema(Verdict),
        evidence,
      },
    });
    if (response.error) throw new Error(response.error);
    return result(
      Verdict.parse(
        typeof response.output === "string"
          ? JSON.parse(response.output)
          : response.output,
      ),
    );
  } catch (error) {
    return result({ status: "unscored", reason: error.message });
  }
}
