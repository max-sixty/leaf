/* What one of eslint.config.mjs's own rules reports on a piece of code.

   eslint lives in pre-commit's environment, not this one, so a rule's visitors run
   here over acorn's tree, which is the ESTree eslint hands them, with what a rule
   reads from eslint's context beside it: each node's `parent` and the source text
   (`sourceCode.getText`). */
import { parse } from "acorn";

// The messages `rule` reports on `code` in `filename`, given its `options`.
export function ruleReports(rule, code, { filename, options = [] }) {
  const reports = [];
  const visitors = rule.create({
    filename,
    options,
    sourceCode: { getText: (node) => code.slice(node.start, node.end) },
    report: ({ message }) => reports.push(message),
  });
  const walk = (node, parent) => {
    node.parent = parent;
    visitors[node.type]?.(node);
    for (const [key, value] of Object.entries(node)) {
      if (key === "parent") continue;
      for (const child of Array.isArray(value) ? value : [value])
        if (child && typeof child.type === "string") walk(child, node);
    }
  };
  walk(parse(code, { ecmaVersion: "latest", sourceType: "module" }), null);
  return reports;
}
