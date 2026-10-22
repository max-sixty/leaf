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
// <text>}`, or as `{"dropped": <text>}` once an Escape (a `turn.complete` that
// `isAborted`) has stopped the session, since Claude Code drops a plugin's prompt
// until the user next types, which this driver's user never does. Every watch it
// starts prints as `{"watching": <its payload>}`. Once a watch has exited and what its exit set
// going in the module has run as far as it can without waiting on anything
// outside, `{"watched": <its payload>}` prints. Each redraw the module asks for
// prints `{"band": {terminal, desktop}}`, the band above the prompt as its render
// hook draws it for each surface, each element `{tag, props, children}`. The
// first line printed is `{"pid", "events"}`: the process the module's processes
// see as their parent, and the events it hooks.
import { spawn } from "node:child_process";
import * as path from "node:path";
import * as readline from "node:readline";
import { fileURLToPath } from "node:url";
import { register } from "../hooks/claude-code.ts";

const ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const [session, options] = [process.argv[2], JSON.parse(process.argv[3])];
const print = (line) => process.stdout.write(`${JSON.stringify(line)}\n`);
const watches = new Set();
let submissions = 0;
let stopped = false;

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
  if (options.throwWatchSpawn) throw new Error("host cannot spawn watch");
  if (request.argv.includes("--watch")) {
    print({
      watching: { ...JSON.parse(request.input), previous_active_watches: watches.size },
    });
  }
  const child = start(request.argv, request.env, request.input);
  if (request.argv.includes("--watch")) watches.add(child);
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
    child.on("close", (code, signal) => {
      watches.delete(child);
      resolve({ code, signal });
      // The module reads the exit through promises alone, so by the next
      // macrotask it has done all it does without waiting on `$`.
      if (request.argv.includes("--watch")) {
        setImmediate(() => print({ watched: JSON.parse(request.input) }));
      }
    });
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
      if (how === undefined && options.abortLagMs)
        throw new Error("the op was aborted");
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
  plugin: { name: "leaf", root: options.pluginRoot ?? ROOT },
  session: {
    id: async () => session,
  },
  prompt: {
    // Claude Code refuses a plugin's prompt that would run a slash command.
    submit: async ({ text }) => {
      if (text.startsWith("/"))
        throw new Error("a text beginning with / would run a command");
      if (stopped) {
        print({ dropped: text });
        return { drop: "the session was stopped and nobody has sent input since" };
      }
      ++submissions;
      print({ submitted: text });
      return { text };
    },
  },
  ui: {
    log: (text) => print({ diagnostic: text }),
    // Each element is its name, which `h` records with its props and children.
    resolve: () => ({ Box: "Box", Text: "Text", Link: "Link", Markdown: "Markdown" }),
    // A redraw of the band, printed as `{"band": {<surface>: <its tree, or null>}}`.
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

/** The band above the prompt on each surface that draws one, as the module's
 * render hooks draw it over nothing. */
async function drawBand() {
  const chain = (hooks.get("ui.render") ?? []).reduceRight(
    (next, hook) => (input) => hook($, input, next),
    async () => null,
  );
  const draw = (surface) =>
    chain({ component: "AbovePrompt", surface, props: { hasSurvey: false } });
  print({ band: { terminal: await draw("terminal"), desktop: await draw("desktop") } });
}

// The driver raises each event it is given, so a matcher selects nothing here.
await register(
  (event, ...rest) => hooks.set(event, [...(hooks.get(event) ?? []), rest.at(-1)]),
  options,
);
print({ pid: process.pid, events: [...hooks.keys()] });

let release;
for await (const line of readline.createInterface({ input: process.stdin })) {
  const { emit, e, answer, hold, release: releasing, flush } = JSON.parse(line);
  if (flush) {
    await new Promise(setImmediate);
    print({ submissions });
    continue;
  }
  if (releasing) {
    release();
    continue;
  }
  if (emit === "turn.complete" && e.isAborted) stopped = true;
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
