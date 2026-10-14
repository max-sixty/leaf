/**
 * Three-way grading by an agent exploring the selected saved version live.
 * The existing workflow owns criteria; native errors remain unscored.
 * Verdicts are model judgments, with browser/agent evidence retained by the provider.
 */
import { mkdtemp } from "node:fs/promises";
import { join } from "node:path";
import { loadApiProvider } from "promptfoo";
import { z } from "zod";

const Verdict = z.strictObject({
  status: z.enum(["pass", "defect", "insufficient_evidence"]),
  reason: z.string().min(1),
});

export default async function grade(output, context, load = loadApiProvider) {
  const { phase, rubric, judge, required_widths } = context.config;
  const result = (verdict, response) => ({
    pass: verdict.status === "pass",
    score: Number(verdict.status === "pass"),
    reason: `${verdict.status}: ${verdict.reason}`,
    ...(response?.tokenUsage ? { tokensUsed: response.tokenUsage } : {}),
    metadata: {
      authoring_grade: { phase, ...verdict },
      ...(response ? { judge: response } : {}),
    },
  });
  let response;
  try {
    if (context.providerResponse.error) throw new Error(context.providerResponse.error);
    const diagnostics = context.providerResponse.metadata?.diagnostics;
    const reading = diagnostics?.phases?.[phase];
    if (!reading) throw new Error(`No recorded version ${phase}`);
    if (!reading.page)
      return result({
        status: "insufficient_evidence",
        reason: "No saved page exists for this version.",
      });
    if (!judge) throw new Error("Live judge is not configured");
    const widths = Object.fromEntries(
      (required_widths ?? Object.keys(diagnostics.widths)).map((name) => {
        if (!diagnostics.widths[name])
          throw new Error(`Unknown required width ${name}`);
        return [name, diagnostics.widths[name]];
      }),
    );
    if (!Object.keys(widths).length) throw new Error("No judge viewports configured");
    const evidence = await mkdtemp(
      join(context.providerResponse.metadata.work, "judge-"),
    );
    const prompt = `Judge version ${phase} against this criterion:
${rubric}

Request and version history (later requirements do not apply to earlier versions):
${output}

Version 1 answers the request; version 2 also answers the width preference;
version 3 also answers the comment; version 4 also applies the user's decision.
Use pass when observation establishes the whole criterion, defect for a supported
user-facing failure, or insufficient_evidence when exploration cannot settle it.`;
    const provider = await load(judge.id, { options: judge });
    response = await provider.callApi(prompt, {
      vars: {
        page: reading.page,
        payload: diagnostics.payload,
        condition: diagnostics.condition,
        widths,
        schema: z.toJSONSchema(Verdict),
        evidence,
      },
    });
    if (response.error)
      return result({ status: "unscored", reason: response.error }, response);
    const verdict = Verdict.parse(
      typeof response.output === "string"
        ? JSON.parse(response.output)
        : response.output,
    );
    return result(verdict, response);
  } catch (error) {
    return result({ status: "unscored", reason: error.message }, response);
  }
}
