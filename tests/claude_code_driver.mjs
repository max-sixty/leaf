// Stands in for Claude Code around Leaf's hooks module (`hooks/claude-code.ts`):
// the `$` calls it makes, over real processes, driven one event at a time from
// stdin.
//
// Arguments: the session id, then the plugin's options as JSON. Each stdin line is
// `{"emit": <event>, "e": <input>, "answer": <result>, "hold": <bool>}`: the
// driver runs that event's hooks over `e`, the bottom of the chain, which stands
// for the settings hooks, answering with `answer`, or else with the input it
// reached, and prints `{"event", "result", "reached"}` once they resolve,
// `reached` being that input. A held event's bottom prints `{"holding": <event>}`
// and answers only once a line `{"release": true}` arrives; lines go on being
// read meanwhile. Every prompt the module submits prints as `{"submitted":
// <text>}` and every row it appends as `{"appended": <text>}`, and every watch it
// starts as `{"watching": <its payload>}`. Once a watch has exited and what its
// exit set going in the module has run as far as it can without waiting on
// anything outside, `{"watched": <its payload>}` prints. The first line printed
// is `{"pid", "events"}`: the process the module's processes see as their parent,
// and the events it hooks.
import { spawn } from "node:child_process";
import * as path from "node:path";
import * as readline from "node:readline";
import { fileURLToPath } from "node:url";
import { register } from "../hooks/claude-code.ts";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const [session, options] = [process.argv[2], JSON.parse(process.argv[3])];
const print = (line) => process.stdout.write(`${JSON.stringify(line)}\n`);
const watches = new Set();
let releaseHook;
let submissions = 0;
let appends = 0;

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
    print({
      watching: { ...JSON.parse(request.input), previous_active_watches: watches.size },
    });
  }
  const child = start(request.argv, request.env, request.input);
  if (request.argv.includes("--watch")) watches.add(child);
  let output = "";
  child.stdout.on("data", (text) => (output += text));
  const ended = new Promise((resolve) =>
    child.on("close", (code, signal) => {
      watches.delete(child);
      resolve({ code, signal });
      // The module reads the exit through promises alone, so by the next
      // macrotask it has done all it does without waiting on `$`.
      if (request.argv.includes("--watch")) {
        setImmediate(() => print({ watched: JSON.parse(request.input) }));
      }
    }),
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
      if (how === undefined && options.abortLagMs)
        throw new Error("the op was aborted");
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
      // Native cancellation can abort output before the child releases its lease.
      // Exercise that ordering deterministically instead of relying on process speed.
      if (options.abortLagMs)
        setTimeout(() => child.kill("SIGTERM"), options.abortLagMs);
      else child.kill("SIGTERM");
      stop();
      return { done: true, value: undefined };
    },
  };
}

const $ = {
  plugin: { name: "leaf", root: ROOT },
  session: {
    id: async () => session,
    append: async ({ message }) => {
      ++appends;
      print({ appended: message.content[0].text });
    },
  },
  prompt: {
    // Claude Code refuses a plugin's prompt that would run a slash command.
    submit: async ({ text }) => {
      if (text.startsWith("/"))
        throw new Error("a text beginning with / would run a command");
      ++submissions;
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
        child.on("close", (code) => {
          const finish = () => resolve({ exitCode: code ?? 1, stdout, stderr: "" });
          if (
            options.holdPromptHook &&
            init.stdin &&
            JSON.parse(init.stdin).hook_event_name === "UserPromptSubmit"
          ) {
            // The real hook has confirmed input; hold its host return across
            // turn completion so receipt and a pending wake can be distinguished.
            releaseHook = finish;
            print({ holding_hook: "UserPromptSubmit" });
          } else finish();
        });
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

let release;
for await (const line of readline.createInterface({ input: process.stdin })) {
  const {
    emit,
    e,
    answer,
    hold,
    release: releasing,
    release_hook,
    flush,
  } = JSON.parse(line);
  if (release_hook) {
    releaseHook();
    continue;
  }
  if (flush) {
    await new Promise(setImmediate);
    print({ submissions, appends });
    continue;
  }
  if (releasing) {
    release();
    continue;
  }
  let reached;
  const chain = (hooks.get(emit) ?? []).reduceRight(
    (next, hook) => (input) => hook($, input, next),
    async (input) => {
      reached = input;
      if (hold) {
        print({ holding: emit });
        await new Promise((resolve) => (release = resolve));
      }
      return answer ?? input;
    },
  );
  const done = Promise.resolve(chain(e)).then((resolved) =>
    print({ event: emit, result: resolved ?? null, reached: reached ?? null }),
  );
  if (!hold) await done;
}
