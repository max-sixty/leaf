// Stands in for Claude Code around Leaf's hooks module (`hooks/claude-code.ts`):
// the `$` calls it makes, over real processes, driven one event at a time from
// stdin.
//
// Arguments: the session id, then the driver's options as JSON: `pluginRoot`, the
// plugin's directory in place of this tree; `throwSpawn`, which makes every
// `$.process.spawn` throw; `forkReply`, the text `$.model.fork` answers with;
// `forkRejects`, which makes every fork reject; and `env`, Claude Code's
// environment, all that `$.env`
// reads and what the module's processes inherit over the driver's own. Each stdin line is `{"emit": <event>, "e": <input>}`:
// the driver runs that event's hooks over `e`, the bottom of the chain answering
// with the input it reached, and prints `{"event", "result"}` once they resolve. A
// line `{"flush": true}` prints `{"flushed": true}` once the module has done what
// it does without waiting on anything outside. Each redraw the module asks for
// prints `{"band": {terminal, desktop}}`, the band above the prompt as its render
// hook draws it for each surface, each element `{tag, props, children}`; a render
// hook of another component is raised as the event `ui.render:<component>`. The
// first line printed is `{"pid"}`, the process the module's processes see as
// their parent. A line `{"press": <key>}` presses the Button of that key in the
// terminal's band last drawn; what a press copies prints as `{"copied": <text>}`,
// and a toast as `{"toast": <text>}`.
import { spawn } from "node:child_process";
import * as path from "node:path";
import * as readline from "node:readline";
import { fileURLToPath } from "node:url";
import { register } from "../hooks/claude-code.ts";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const [session, options] = [process.argv[2], JSON.parse(process.argv[3])];
const print = (line) => process.stdout.write(`${JSON.stringify(line)}\n`);
let band = { terminal: null, desktop: null };

function start(argv, env, input) {
  const child = spawn(argv[0], argv.slice(1), {
    env: { ...process.env, ...options.env, ...env },
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
  env: {
    get: async (name) => options.env?.[name],
  },
  clock: {
    now: async () => Date.now(),
  },
  ui: {
    // A line for Claude Code's debug log prints as `{"debug": <text>}`.
    log: (text, options) =>
      print(options?.to === "debug" ? { debug: text } : { diagnostic: text }),
    // Each element is its name, which `h` records with its props and children.
    resolve: () => ({
      Box: "Box",
      Text: "Text",
      Link: "Link",
      Markdown: "Markdown",
      Button: "Button",
    }),
    copy: async ({ text }) => {
      print({ copied: text });
      return { isCopied: true };
    },
    toast: (text) => print({ toast: text }),
    // A redraw of the band, printed as `{"band": {<surface>: <its tree, or null>}}`.
    invalidate: () => setImmediate(drawBand),
  },
  // A fork answers with `options.forkReply`, printing the prompt it was asked as
  // `{"forked": <prompt>}`; with none it has nothing to fork, as before a turn's end.
  model: {
    fork: async ({ prompt }) => {
      print({ forked: prompt });
      if (options.forkRejects) throw new Error("the model refused the request");
      const usage = {
        input_tokens: 10,
        output_tokens: 20,
        cache_read_input_tokens: 1000,
        cache_creation_input_tokens: 0,
      };
      return options.forkReply === undefined
        ? { isAnswered: false, reason: "nothing-to-fork" }
        : { isAnswered: true, text: options.forkReply, usage };
    },
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

/** The band above the prompt on each surface that draws one, as the module's
 * render hooks draw it over nothing. */
async function drawBand() {
  const chain = (hooks.get("ui.render:AbovePrompt") ?? []).reduceRight(
    (next, hook) => (input) => hook($, input, next),
    async () => null,
  );
  const draw = (surface) =>
    chain({ component: "AbovePrompt", surface, props: { hasSurvey: false } });
  band = { terminal: await draw("terminal"), desktop: await draw("desktop") };
  print({ band });
}

/** The element of the terminal's band last drawn whose key is `key`. */
function drawn(key, node = band.terminal) {
  if (node === null || typeof node !== "object") return undefined;
  if (node.props?.key === key) return node;
  for (const child of node.children) {
    const found = drawn(key, child);
    if (found) return found;
  }
}

// The driver raises each event it is given, so a matcher selects nothing here but
// a render hook's component, under which it files the hook: `ui.render:<component>`.
await register((event, ...rest) => {
  const key = event === "ui.render" ? `${event}:${rest[0].component}` : event;
  hooks.set(key, [...(hooks.get(key) ?? []), rest.at(-1)]);
});
print({ pid: process.pid });

for await (const line of readline.createInterface({ input: process.stdin })) {
  const { emit, e, flush, press } = JSON.parse(line);
  if (press !== undefined) {
    drawn(press).props.onPress({ element: press, surface: "terminal" });
    continue;
  }
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
