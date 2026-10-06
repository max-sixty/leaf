// Promptfoo's native regex assertion has no flags. Preserve case-insensitive
// readings from the original cases, including the no-drawing guardrails.
module.exports = (output, context) => {
  const { pattern, flags, negate = false } = context.config;
  const pass = new RegExp(pattern, flags).test(output) !== negate;
  return {
    pass,
    score: Number(pass),
    reason: pass ? "Matched expectation" : "Text pattern failed",
  };
};
