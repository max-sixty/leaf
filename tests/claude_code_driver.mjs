// Stands in for Claude Code around Leaf's hooks module (`hooks/claude-code.ts`):
// the `$` calls it makes, over real processes, driven one event at a time from
// stdin.
//
// Arguments: the session id, then the driver's options as JSON: `pluginRoot`, the
// plugin's directory in place of this tree, and `throwSpawn`, which makes every
// `$.process.spawn` throw. Each stdin line is `{"emit": <event>, "e": <input>}`:
// the driver runs that event's hooks over `e`, the bottom of the chain answering
// with the input it reached, and prints `{"event", "result"}` once they resolve. A
// line `{"flush": true}` prints `{"flushed": true}` once the module has done what
// it does without waiting on anything outside. Each redraw the module asks for
// prints `{"band": <tree>}`, the band above the prompt as its render hook draws
// it, each element `{tag, props, children}`; a render hook of another component is
// raised as the event `ui.render:<component>`. The first line printed is `{"pid"}`,
// the process the module's processes see as their parent.
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
    stdio: ["pipe", "pipe", "pipe"],
  });
  child.stdin.on("error", () => {});
  child.stdin.end(input ?? "");
  return child;
}

/** `$.process.spawn`: the child's output as it arrives, then how it ended. As in
 * Claude Code, `return()` ends the read at once and terminates the child, even
 * while a read waits on it. */
function stream(request) {
  if (options.throwSpawn) throw new Error("host cannot spawn");
  const child = start(request.argv, request.env, request.input);
  let output = "";
  let errors = "";
  let arrived;
  const arrival = () => new Promise((resolve) => (arrived = resolve));
  let arriving = arrival();
  const append = (add) => (text) => {
    add(text);
    arrived();
    arriving = arrival();
  };
  child.stdout.on(
    "data",
    append((text) => (output += text)),
  );
  child.stderr.on(
    "data",
    append((text) => (errors += text)),
  );
  const ended = new Promise((resolve, reject) => {
    child.on("error", reject);
    child.on("close", (code, signal) => resolve({ code, signal }));
  });
  let stop;
  const stopped = new Promise((resolve) => (stop = resolve));
  let finished = false;
  return {
    result: ended,
    [Symbol.asyncIterator]() {
      return this;
    },
    async next() {
      if (!output && !errors && !finished)
        await Promise.race([ended, stopped, arriving]);
      const how = await Promise.race([ended, stopped, Promise.resolve(null)]);
      if (finished || how === undefined) return { done: true, value: how };
      if (output) {
        const text = output;
        output = "";
        return { done: false, value: { stream: "stdout", text } };
      }
      if (errors) {
        const text = errors;
        errors = "";
        return { done: false, value: { stream: "stderr", text } };
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
  plugin: { name: "leaf", root: options.pluginRoot ?? ROOT },
  session: {
    id: async () => session,
  },
  ui: {
    // A line for Claude Code's debug log prints as `{"debug": <text>}`.
    log: (text, options) =>
      print(options?.to === "debug" ? { debug: text } : { diagnostic: text }),
    // Each element is its name, which `h` records with its props and children.
    resolve: () => ({ Box: "Box", Text: "Text", Link: "Link" }),
    // A redraw of the band, printed as `{"band": <its tree, or null>}`.
    invalidate: () => setImmediate(drawBand),
  },
  process: {
    run: (argv, init = {}) =>
      new Promise((resolve, reject) => {
        const child = start(argv, init.env, init.stdin);
        let stdout = "";
        let stderr = "";
        child.stdout.on("data", (text) => (stdout += text));
        child.stderr.on("data", (text) => (stderr += text));
        child.on("error", reject);
        child.on("close", (code) => {
          resolve({ exitCode: code ?? 1, stdout, stderr });
        });
      }),
    spawn: stream,
  },
};

const hooks = new Map();
globalThis.h = (tag, props, ...children) => ({ tag, props, children });

/** The band above the prompt, as the module's render hooks draw it over nothing. */
async function drawBand() {
  const band = { component: "AbovePrompt", props: { hasSurvey: false } };
  const chain = (hooks.get("ui.render:AbovePrompt") ?? []).reduceRight(
    (next, hook) => (input) => hook($, input, next),
    async () => null,
  );
  print({ band: await chain(band) });
}

// The driver raises each event it is given, so a matcher selects nothing here but
// a render hook's component, under which it files the hook: `ui.render:<component>`.
await register((event, ...rest) => {
  const key = event === "ui.render" ? `${event}:${rest[0].component}` : event;
  hooks.set(key, [...(hooks.get(key) ?? []), rest.at(-1)]);
});
print({ pid: process.pid });

for await (const line of readline.createInterface({ input: process.stdin })) {
  const { emit, e, flush } = JSON.parse(line);
  if (flush) {
    await new Promise(setImmediate);
    print({ flushed: true });
    continue;
  }
  const chain = (hooks.get(emit) ?? []).reduceRight(
    (next, hook) => (input) => hook($, input, next),
    async (input) => input,
  );
  print({ event: emit, result: (await chain(e)) ?? null });
}
