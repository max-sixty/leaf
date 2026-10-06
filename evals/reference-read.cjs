/**
 * Check native Promptfoo agent metadata for successful reference consumption.
 * Claude exposes completed Read/Skill results. Shell reads (Claude Bash and
 * Codex commandExecution) are evidence heuristics: a successful read command
 * naming the requested path after brace expansion and returning text, not proof
 * of every byte read. Quoted and escaped spans are ineligible for expansion;
 * this is still a read-evidence heuristic, not a shell interpreter.
 * The regex in assertion.config.path selects the reference across staged paths.
 */
const { expand } = require("brace-expansion");

function expandedReadArguments(text) {
  // Protect whole quoted/escaped spans before expansion; restoring them keeps
  // the original heuristic's literal-path matching. Never execute the command.
  let prefix = "__leaf_read_literal__";
  while (text.includes(prefix)) prefix += "_";
  const literals = [];
  const protectedText = text.replace(
    /\\[\s\S]|'[^']*'|"(?:\\[\s\S]|[^"\\])*"/g,
    (literal) => `${prefix}${literals.push(literal) - 1}__`,
  );
  return expand(protectedText).map((argument) =>
    argument.replace(
      new RegExp(`${prefix}(\\d+)__`, "g"),
      (_token, index) => literals[Number(index)],
    ),
  );
}

function hasOutput(output) {
  if (typeof output === "string") return output.trim().length > 0;
  if (Array.isArray(output)) return output.some((block) => hasOutput(block?.text));
  return false;
}

function readCommand(command, path) {
  if (typeof command !== "string") return false;
  // App Server reports shell wrappers as well as bare command strings.
  const wrapper = command.match(
    /^\S*\b(bash|zsh|fish|sh)\s+-[a-z]*c\s+(['"])([\s\S]*)\2$/,
  );
  const body = wrapper ? wrapper[3] : command;
  // Expand only the known Bash/Zsh wrapper semantics, or bare Bash-tool
  // commands. Other recognized shells keep the original literal-path reading.
  const expandsBraces = !wrapper || ["bash", "zsh"].includes(wrapper[1]);
  return body.split(/&&|\|\||[;|\n]/).some((part) => {
    // Deliberately restrict this heuristic to familiar commands that emit reads.
    const reading = part
      .trim()
      .match(
        /^(?:\/[\w./-]+\/)?(?:cat|sed|head|tail|less|more|bat|rg|grep)\s+([\s\S]*)$/,
      );
    return (
      reading !== null &&
      (expandsBraces ? expandedReadArguments(reading[1]) : [reading[1]]).some(
        (argument) => path.test(argument),
      )
    );
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
