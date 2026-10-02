/**
 * Check native Promptfoo agent metadata for successful reference consumption.
 * Claude exposes completed Read/Skill results. Shell reads (Claude Bash and
 * Codex commandExecution) are evidence heuristics: a successful read command
 * naming the requested path and returning text, not proof of every byte read.
 * The regex in assertion.config.path selects the reference across staged paths.
 */
function hasOutput(output) {
  if (typeof output === "string") return output.trim().length > 0;
  if (Array.isArray(output)) return output.some((block) => hasOutput(block?.text));
  return false;
}

function readCommand(command, path) {
  if (typeof command !== "string") return false;
  // App Server reports shell wrappers as well as bare command strings.
  const wrapper = command.match(
    /^\S*\b(?:bash|zsh|fish|sh)\s+-[a-z]*c\s+(['"])([\s\S]*)\1$/,
  );
  const body = wrapper ? wrapper[2] : command;
  return body.split(/&&|\|\||[;|\n]/).some((part) => {
    // Deliberately restrict this heuristic to familiar commands that emit reads.
    const reading = part
      .trim()
      .match(
        /^(?:\/[\w./-]+\/)?(?:cat|sed|head|tail|less|more|bat|rg|grep)\s+([\s\S]*)$/,
      );
    return reading !== null && path.test(reading[1]);
  });
}

module.exports = function referenceRead(_output, context) {
  const path = new RegExp(context.config.path);
  const metadata = context.providerResponse.metadata ?? {};
  const claude = (metadata.toolCalls ?? []).some((call) => {
    if (call.is_error !== false || !hasOutput(call.output)) return false;
    if (call.name === "Read") {
      return (
        typeof call.input?.file_path === "string" && path.test(call.input.file_path)
      );
    }
    if (call.name === "Skill") {
      return (
        /^(?:leaf:)?leaf$/.test(call.input?.skill) && path.test("skills/leaf/SKILL.md")
      );
    }
    return call.name === "Bash" && readCommand(call.input?.command, path);
  });
  const codex = (metadata.codexAppServer?.items ?? []).some(
    (item) =>
      item.type === "commandExecution" &&
      item.status === "completed" &&
      item.exitCode === 0 &&
      hasOutput(item.aggregatedOutput) &&
      readCommand(item.command, path),
  );
  const pass = claude || codex;
  return {
    pass,
    score: Number(pass),
    reason: pass
      ? `Successful reference-read evidence for ${path}`
      : `No successful reference-read evidence for ${path}`,
  };
};
