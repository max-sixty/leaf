/**
 * Leaf's Claude Code hooks module: the session's watch between turns, kept by
 * the module rather than by the background Stop registration in `hooks.json`.
 * It runs only while the plugin's `hooks_module` option is on, and only in a
 * Claude Code that loads hooks modules, an early-access API.
 *
 * It does for the watch what `hooks/pi.ts` does for a Pi session
 * (`ClaudeCodeHarness` in `skills/leaf/scripts/leaf/harness.py`):
 *
 * - the session's start and each main-loop turn's end start the watch (`bin/leaf
 *   hook --harness claude-code --if-claimed --watch`), which prints a line and
 *   exits once one of the session's pages has input;
 * - a turn the user interrupts ends with no Stop hook, so the module starts the
 *   watch with the Interrupt payload, which closes the turn. Receipt distinguishes
 *   input that entered that turn from input held outside its context;
 * - a watch that wakes an idle session submits its line as a prompt, whose
 *   prompt hook hands the input over. From an Escape until the user next types,
 *   Claude Code drops every prompt a plugin submits but still takes a message
 *   from another session (measured at 2.1.300), so for a dropped prompt the
 *   module sends Leaf a WakeRefused payload, and Leaf nudges the session through
 *   that message, as admission does for a session nothing watches. A watch that
 *   wakes during a turn leaves pending input to the native PostToolBatch
 *   boundary, shared with the default registration. A wake while Stop hooks run
 *   waits for their decision before starting an idle turn. The module never
 *   makes a second mid-turn delivery.
 *
 * Once it has Claude Code's parent process, each Stop payload it passes on carries
 * `leaf_watch: "module"`, which stands down the background watch beneath it
 * (`hooks/scripts/background-watch.py`). A Claude Code that does not load the
 * module, or a module without that parent process, passes the payload unmarked, so
 * that registration goes on watching. A native spawn handle does not prove startup:
 * a watch that fails later reports its error and releases the owner's slot. The
 * prompt, Stop, SessionStart and SessionEnd registrations do the same work under
 * either watch and stay in `hooks.json`.
 *
 * TODO: once Claude Code loads modules without an opt-in, make this module the
 * only watcher and transport and drop the background Stop registration,
 * `background-watch.py`, and the interrupt half of the nudge.
 *
 * A module's processes inherit Claude Code's own environment, which names no
 * session of its own, so every call states the session and Claude Code's process
 * as a hook's environment does. That process is the parent of every process the
 * module starts (measured at Claude Code 2.1.291). Failed hooks and watches report
 * their diagnostics through Claude Code's UI log. Replacing or closing a watch
 * cancels it quietly, after waiting for its process to exit.
 *
 * Whatever the option, the module also draws a band above the prompt for each live
 * page the session holds: a link to the page, what is On the user, and its open
 * threads with how many hold words the user hasn't read, the counts the page's own
 * Leaf panel marks. A follower (`bin/leaf hook --harness claude-code --if-claimed
 * --pages`) prints that list whenever it changes and exits once the session holds
 * no page; the launcher answers it without starting uv in a session holding none.
 * The session takes a page only through a `leaf` command, so the module starts the
 * follower as the session starts, after each Bash call that runs `leaf`, and as a
 * main-loop turn ends, once none is running.
 */

import type { EngineInterface, Register, RenderElement } from "claude-code";
import { WatchOwner } from "./watch.ts";

// `hooks.json`'s timeout for Leaf's hooks.
const HOOK_TIMEOUT_MS = 20_000;

type Payload = { hook_event_name: string; session_id: string; ended_at?: number };

// Claude Code's process, read as the session starts.
let claudePid = "";
let watch = new WatchOwner();
// Whether a main-loop turn is going, from its start until its Stop hooks let it end.
let running = false;
// The Stop hooks of a turn now ending, while they run.
let stopping: Promise<unknown> | undefined;

// A live page the session holds, as the follower prints it (`presence.session_leaves`).
type Leaf = {
  page_key: string;
  url: string;
  title: string;
  on_user: number;
  threads: { open: number; unread: number };
};
// The follower's last list, and how to stop the follower while one runs.
let leaves: Leaf[] = [];
let following: { stop: () => unknown } | undefined;

function environment(session: string) {
  return { CLAUDE_CODE_SESSION_ID: session, CLAUDE_PID: claudePid };
}

function launcher($: EngineInterface) {
  return `${$.plugin.root}/bin/leaf`;
}

/** Run Leaf's hook on `payload`, an event no registration answers. */
async function hook($: EngineInterface, payload: Payload): Promise<void> {
  try {
    const ran = await $.process.run(
      [launcher($), "hook", "--harness", "claude-code", "--if-claimed"],
      {
        env: environment(payload.session_id),
        stdin: JSON.stringify(payload),
        timeoutMs: HOOK_TIMEOUT_MS,
      },
    );
    if (ran.exitCode !== 0) {
      $.ui.log(
        `Leaf: ${payload.hook_event_name} hook exited with code ${ran.exitCode}${ran.stderr.trim() ? `: ${ran.stderr.trim()}` : ""}`,
      );
    }
  } catch (error) {
    $.ui.log(`Leaf: ${payload.hook_event_name} hook failed: ${error}`);
  }
}

/** The watch owner serializes endings; the adapter supplies Claude Code's process
 * and wake operations. Without its parent process, the registration keeps watch. */
async function ensureWatch($: EngineInterface, session: string, interrupted: boolean) {
  const ended = Date.now() / 1000;
  if (!claudePid) return;
  const owner = watch;
  await owner
    .ensure(
      interrupted,
      () => {
        const payload: Payload = {
          hook_event_name: interrupted ? "Interrupt" : "Stop",
          session_id: session,
          ended_at: ended,
        };
        const stream = $.process.spawn({
          argv: [
            launcher($),
            "hook",
            "--harness",
            "claude-code",
            "--if-claimed",
            "--watch",
          ],
          env: environment(session),
          input: JSON.stringify(payload),
        });
        let cancelled = false;
        const done = (async () => {
          let out = "";
          let stderr = "";
          let readError: unknown;
          try {
            for await (const chunk of stream) {
              if (chunk.stream === "stdout") out += chunk.text;
              else if (chunk.stream === "stderr") stderr += chunk.text;
            }
          } catch (error) {
            // Cancellation can abort output before the process releases its lease.
            readError = error;
          }
          try {
            const result = await stream.result;
            if (cancelled) return "";
            if (result.code !== 0 || readError) {
              $.ui.log(
                `Leaf: watch failed (${readError ?? `exit code ${result.code}`})${stderr.trim() ? `: ${stderr.trim()}` : ""}`,
              );
              return "";
            }
            return out.trim();
          } catch (error) {
            if (!cancelled)
              $.ui.log(
                `Leaf: watch failed: ${error}${stderr.trim() ? `: ${stderr.trim()}` : ""}`,
              );
            return "";
          }
        })();
        return {
          stop: () => {
            cancelled = true;
            return stream.return(undefined as never);
          },
          done,
        };
      },
      (output, live) => wake($, session, output, live),
    )
    .catch((error) => {
      $.ui.log(`Leaf: watch could not start: ${error}`);
    });
}

/** Whether the turn goes on, once any Stop hooks now running have returned. They
 * decide whether the turn goes on, so a wake waits for them rather than starting
 * a turn beside one they continue. */
async function turnGoesOn() {
  while (stopping) await stopping.catch(() => undefined);
  return running;
}

async function wake(
  $: EngineInterface,
  session: string,
  woke: string,
  live: () => boolean,
) {
  if (!woke) return;
  try {
    // Claude Code refuses a plugin's prompt that starts with `/`, as the watch's
    // line, a page's path, does.
    const prompt = `Leaf: ${woke}`;
    const ongoing = await turnGoesOn();
    if (!live() || ongoing) return;
    // Claude Code drops a plugin's prompt from an Escape until the user next types,
    // and drops one queued when they press it; Claude Code's debug log says why.
    const submitted = await $.prompt.submit({ text: prompt });
    if (submitted?.drop !== undefined)
      await hook($, { hook_event_name: "WakeRefused", session_id: session });
  } catch (error) {
    // A wake that fails outright leaves the input to the next turn's prompt hook.
    $.ui.log(`Leaf: the watch's wake was refused: ${error}`, { to: "debug" });
  }
}

function show($: EngineInterface, listed: Leaf[]) {
  leaves = listed;
  $.ui.invalidate("ui.render");
}

/** Start the follower of the session's pages, unless one runs. */
function follow($: EngineInterface, session: string) {
  if (following) return;
  let stream: ReturnType<EngineInterface["process"]["spawn"]>;
  try {
    stream = $.process.spawn({
      argv: [
        launcher($),
        "hook",
        "--harness",
        "claude-code",
        "--if-claimed",
        "--pages",
      ],
      env: environment(session),
      input: JSON.stringify({ hook_event_name: "Pages", session_id: session }),
    });
  } catch (error) {
    $.ui.log(`Leaf: the pages follower could not start: ${error}`);
    return;
  }
  const current = { stop: () => stream.return(undefined as never) };
  following = current;
  void (async () => {
    let line = "";
    let stderr = "";
    try {
      for await (const chunk of stream) {
        if (chunk.stream === "stderr") {
          stderr += chunk.text;
          continue;
        }
        const lines = (line + chunk.text).split("\n");
        line = lines.pop() ?? "";
        const last = lines.at(-1);
        if (last !== undefined && following === current) show($, JSON.parse(last));
      }
      const result = await stream.result;
      if (result.code !== 0 && following === current)
        $.ui.log(
          `Leaf: the pages follower exited with code ${result.code}${stderr.trim() ? `: ${stderr.trim()}` : ""}`,
        );
    } catch (error) {
      if (following === current) $.ui.log(`Leaf: the pages follower failed: ${error}`);
    } finally {
      // It exits once the session holds no page, or never starts in one holding none.
      if (following === current) {
        following = undefined;
        show($, []);
      }
    }
  })();
}

export const register: Register = (on, options) => {
  const watching = options.hooks_module === true;

  on("session.start", async ($, e, next) => {
    const started = await next(e);
    const session = await $.session.id();
    follow($, session);
    if (watching) {
      const parent = await $.process.run(["/bin/sh", "-c", "echo $PPID"]);
      claudePid = parent.stdout.trim();
      void ensureWatch($, session, false);
    }
    return started;
  });

  on("tool.call", { tool: "Bash" }, async ($, e, next) => {
    const result = await next(e);
    // A gate on the tool's own call: nothing after its result may fail it.
    if (/\bleaf\b/.test(e.command))
      void $.session.id().then((session) => follow($, session));
    return result;
  });

  on("turn.complete", async ($, e, next) => {
    const completed = await next(e);
    if (e.agentId !== undefined) return completed;
    const session = await $.session.id();
    follow($, session);
    if (watching) {
      running = false;
      void ensureWatch($, session, e.isAborted);
    }
    return completed;
  });

  on("ui.render", { component: "AbovePrompt" }, ($, e, next) => {
    if (leaves.length === 0 || e.props.hasSurvey) return next(e);
    const { Box, Text, Link } = $.ui.resolve(e);
    // What JSX would type; the module stays `.ts` for Node, which runs it in tests.
    return h(
      Box,
      { flexDirection: "column" },
      ...leaves.map(({ url, title, on_user, threads }) =>
        h(
          Text,
          { dimColor: true },
          "Leaf ",
          h(Link, { href: url }, title),
          ` · On me ${on_user} · Threads ${threads.open}`,
          threads.unread ? `, ${threads.unread} new` : "",
        ),
      ),
    ) as RenderElement;
  });

  on("session.end", async ($, e, next) => {
    const owner = watch;
    const current = following;
    following = undefined;
    leaves = [];
    await Promise.all([owner.close(), current?.stop()]);
    const ended = await next(e);
    // /clear and resume keep the module loaded without another session.start.
    if (watch === owner) watch = new WatchOwner();
    return ended;
  });

  if (!watching) return;

  on("turn.start", ($, e, next) => {
    running = true;
    return next(e);
  });

  on("classic.Stop", ($, e, next) => {
    const ending = (async () => {
      // The mark stands the background watch down, since the module keeps the
      // watch; without Claude Code's process it cannot, and that registration does.
      const result = await next(
        claudePid ? Object.assign({}, e, { leaf_watch: "module" }) : e,
      );
      // A Stop hook's context keeps the turn going.
      running =
        (result.additionalContext ?? []).length > 0 || result.block !== undefined;
      return result;
    })();
    stopping = ending;
    const settled = () => {
      if (stopping === ending) stopping = undefined;
    };
    ending.then(settled, settled);
    return ending;
  });
};
