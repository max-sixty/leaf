// Stands in for Claude Code around Leaf's hooks module (`hooks/claude-code.ts`):
// the `$` calls it makes, over real processes, driven one event at a time from
// stdin.
//
// Arguments: the session id, then the plugin's options as JSON. Each stdin line is
// `{"emit": <event>, "e": <input>}`: the driver runs that event's hooks over `e`,
// the bottom of the chain answering with the input it reached, and prints
// `{"event", "result", "reached"}` once they resolve, `reached` being that input.
// Every prompt the module submits prints as `{"submitted": <text>}` and every row
// it appends as `{"appended": <text>}`, and every watch it starts as `{"watching":
// <its payload>}`. The first line printed is `{"pid",
// "events"}`: the process the module's processes see as their parent, and the
// events it hooks.
import { spawn } from "node:child_process";
import * as path from "node:path";
import * as readline from "node:readline";
import { fileURLToPath } from "node:url";
import { register } from "../hooks/claude-code.ts";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const [session, options] = [process.argv[2], JSON.parse(process.argv[3])];
const print = (line) => process.stdout.write(`${JSON.stringify(line)}\n`);

function start(argv, env, input) {
  const child = spawn(argv[0], argv.slice(1), {
    env: { ...process.env, ...env },
    stdio: ["pipe", "pipe", "ignore"],
  });
  child.stdin.on("error", () => {});
  child.stdin.end(input ?? "");
  return child;
}

/** `$.process.spawn`: the child's output, here in one piece once it exits, then
 * how it ended. As in Claude Code, `return()` ends the read at once and
 * terminates the child, even while a read waits on it. */
function stream(request) {
  if (request.argv.includes("--watch")) {
    print({ watching: JSON.parse(request.input) });
  }
  const child = start(request.argv, request.env, request.input);
  let output = "";
  child.stdout.on("data", (text) => (output += text));
  const ended = new Promise((resolve) =>
    child.on("close", (code, signal) => resolve({ code, signal })),
  );
  let stop;
  const stopped = new Promise((resolve) => (stop = resolve));
  let finished = false;
  return {
    result: ended,
    [Symbol.asyncIterator]() {
      return this;
    },
    async next() {
      const how = await Promise.race([ended, stopped]);
      if (finished || how === undefined) return { done: true, value: how };
      if (output) {
        const text = output;
        output = "";
        return { done: false, value: { stream: "stdout", text } };
      }
      finished = true;
      return { done: true, value: how };
    },
    async return() {
      finished = true;
      child.kill("SIGTERM");
      stop();
      return { done: true, value: undefined };
    },
  };
}

const $ = {
  plugin: { name: "leaf", root: ROOT },
  session: {
    id: async () => session,
    append: async ({ message }) => print({ appended: message.content[0].text }),
  },
  prompt: {
    // Claude Code refuses a plugin's prompt that would run a slash command.
    submit: async ({ text }) => {
      if (text.startsWith("/"))
        throw new Error("a text beginning with / would run a command");
      print({ submitted: text });
    },
  },
  ui: { log: (text) => process.stderr.write(`${text}\n`) },
  process: {
    run: (argv, init = {}) =>
      new Promise((resolve) => {
        const child = start(argv, init.env, init.stdin);
        let stdout = "";
        child.stdout.on("data", (text) => (stdout += text));
        child.on("close", (code) =>
          resolve({ exitCode: code ?? 1, stdout, stderr: "" }),
        );
      }),
    spawn: stream,
  },
};

const hooks = new Map();
await register(
  (event, hook) => hooks.set(event, [...(hooks.get(event) ?? []), hook]),
  options,
);
print({ pid: process.pid, events: [...hooks.keys()] });

for await (const line of readline.createInterface({ input: process.stdin })) {
  const { emit, e } = JSON.parse(line);
  let reached;
  const chain = (hooks.get(emit) ?? []).reduceRight(
    (next, hook) => (input) => hook($, input, next),
    async (input) => (reached = input),
  );
  const result = await chain(e);
  print({ event: emit, result: result ?? null, reached: reached ?? null });
}
