/**
 * Leaf's Claude Code hooks module: the session's watch between turns, and the band
 * above the prompt that shows the session's pages. Claude Code loads it from the
 * installed plugin (measured at 2.1.305); a Claude Code that loads no hooks module
 * keeps no watch, and input reaches its session only through the message Leaf
 * sends a session nothing watches (`presence.nudge_unwatched`).
 *
 * It keeps the watch as `hooks/pi.ts` does for a Pi session (`ClaudeCodeHarness`
 * in `skills/leaf/scripts/leaf/harness.py`):
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
 *   registration. A wake while Stop hooks run leaves its input to the watch
 *   started at turn completion. The module never makes a second mid-turn delivery.
 *
 * The prompt, tool-batch, Stop, SessionStart and SessionEnd registrations in
 * `hooks.json` carry and confirm input; the module only watches and wakes. A
 * native spawn handle does not prove startup: a watch that fails later reports its
 * error and releases the owner's slot.
 *
 * A module's processes inherit Claude Code's own environment, which names no
 * session of its own, so every call states the session and Claude Code's process
 * as a hook's environment does. That process is the parent of every process the
 * module starts (measured at Claude Code 2.1.291). Failed hooks and watches report
 * their diagnostics through Claude Code's UI log. Replacing or closing a watch
 * cancels it quietly, after waiting for its process to exit.
 *
 * The band has a line for each live page the session holds: the word Leaf in the
 * tone the page's Leaf panel gives its leaf, a link to the page, what is On the
 * user, and its open threads with how many hold words the user hasn't read, the
 * counts the panel marks, then the agent's status. It goes above whatever other
 * plugins draw there. Claude Code keeps an empty row between the band and the
 * prompt (measured at 2.1.306); a negative margin to close it hides the band.
 * `leaf-dev claude-code-session` runs a session that draws it from this tree.
 *
 * A follower (`bin/leaf hook --harness claude-code
 * --if-claimed --pages`) prints that list whenever it changes and exits once the
 * session holds no page; the launcher answers it without starting uv in a session
 * holding none. The session takes a page only through a `leaf` command, so the
 * module starts the follower as the session starts, after each Bash call that
 * runs `leaf`, and as a turn starts or a main-loop turn ends, once none is
 * running; a request while one runs starts another once it exits.
 */

import type { EngineInterface, Register, RenderElement } from "claude-code";
import { WatchOwner } from "./watch.ts";

// `hooks.json`'s timeout for Leaf's hooks.
const HOOK_TIMEOUT_MS = 20_000;

type Payload = { hook_event_name: string; session_id: string; ended_at?: number };

// Claude Code's process, read once by `sessionOf`.
let claudePid = "";
let watch = new WatchOwner();
// Whether a main-loop turn is going, from its start until turn.complete.
let running = false;

// A live page the session holds, as the follower prints it (`hooks.cmd_pages`).
type Leaf = {
  page_key: string;
  url: string;
  title: string;
  on_user: number;
  threads: { open: number; unread: number };
  activity: { kind: string; detail: string };
};

// The color the word Leaf wears for each activity kind, in Claude Code's theme: the
// tone the page's Leaf panel paints its leaf (`.lf-dot` in chrome.css), muted for the
// rest.
const TONES: Record<string, string> = {
  working: "suggestion",
  listening: "success",
  stalled: "warning",
  away: "warning",
};

/** What a line says of the agent's work, in the words of an All pages row
 * (`leafRow` in activity-words.js), less its bare Awaits: a listening page shows
 * only the detail the agent declared, since listening is the usual case. */
function statusOf({ kind, detail }: Leaf["activity"]) {
  const stated = (word: string) => (detail ? `${word} — ${detail}` : word);
  if (kind === "working") return stated("Working");
  if (kind === "stalled") return stated("Quiet");
  if (kind === "away") return "Away";
  return detail;
}

// The follower's last list, how to stop the follower while one runs, and whether
// something asked for one while it ran, which may have outlived its last read.
let leaves: Leaf[] = [];
let following: { stop: () => unknown } | undefined;
let followAgain = false;

/** The session's id, once Claude Code's process is known. A module loaded or reloaded
 * mid-session sees no session.start, so whichever hook comes first reads it. */
async function sessionOf($: EngineInterface) {
  if (!claudePid)
    claudePid = (await $.process.run(["/bin/sh", "-c", "echo $PPID"])).stdout.trim();
  return $.session.id();
}

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
 * and wake operations. */
async function ensureWatch($: EngineInterface, session: string, interrupted: boolean) {
  const ended = Date.now() / 1000;
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
    if (!live() || running) return;
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

/** Start the follower of the session's pages, or once the running one exits. */
function follow($: EngineInterface, session: string) {
  if (following) {
    followAgain = true;
    return;
  }
  followAgain = false;
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
        if (followAgain) follow($, session);
        else show($, []);
      }
    }
  })();
}

export const register: Register = (on) => {
  on("session.start", async ($, e, next) => {
    const started = await next(e);
    const session = await sessionOf($);
    follow($, session);
    void ensureWatch($, session, false);
    return started;
  });

  // A call that runs `leaf`, as `hooks.json`'s PreToolUse registrations match one.
  on(
    "tool.call",
    { tool: "Bash", command: /(^|[\s;&|(/])leaf(\s|$)/ },
    async ($, e, next) => {
      const result = await next(e);
      // A gate on the tool's own call: nothing after its result may fail it.
      void sessionOf($).then((session) => follow($, session));
      return result;
    },
  );

  // A resumed or cleared session raises no session.start, so its first turn follows.
  on("turn.start", ($, e, next) => {
    if (e.agentId !== undefined) return next(e);
    running = true;
    void sessionOf($).then((session) => follow($, session));
    return next(e);
  });

  on("turn.complete", async ($, e, next) => {
    const completed = await next(e);
    if (e.agentId !== undefined) return completed;
    running = false;
    const session = await sessionOf($);
    follow($, session);
    void ensureWatch($, session, e.isAborted);
    return completed;
  });

  // The band is shared: Leaf's lines go above whatever the plugins beneath draw.
  on("ui.render", { component: "AbovePrompt" }, async ($, e, next) => {
    const beneath = await next(e);
    if (leaves.length === 0 || e.props.hasSurvey) return beneath;
    const { Box, Text, Link } = $.ui.resolve(e);
    // What JSX would type; the module stays `.ts` for Node, which runs it in tests.
    const dim = (text: string) => h(Text, { dimColor: true }, text);
    // A line keeps one row, its status cut first; only the counts that aren't zero
    // show, and what waits on the user takes a color.
    const line = ({ url, title, on_user, threads, activity }: Leaf) => {
      const status = statusOf(activity);
      return h(
        Text,
        { wrap: "truncate-end" },
        // One link from the word Leaf through the title, so either opens the page.
        h(
          Link,
          { href: url },
          h(
            Text,
            { color: TONES[activity.kind] ?? "inactive", weight: "semibold" },
            "Leaf",
          ),
          " ",
          h(Text, { underline: true }, title),
        ),
        ...(on_user
          ? [dim(" · "), h(Text, { color: "warning" }, `On me ${on_user}`)]
          : []),
        // A resolved thread can still hold unread words.
        ...(threads.open || threads.unread ? [dim(` · Threads ${threads.open}`)] : []),
        ...(threads.unread
          ? [dim(", "), h(Text, { color: "suggestion" }, `${threads.unread} new`)]
          : []),
        ...(status ? [dim(` · ${status}`)] : []),
      );
    };
    return h(
      Box,
      { flexDirection: "column" },
      ...leaves.map(line),
      beneath,
    ) as RenderElement;
  });

  on("session.end", async ($, e, next) => {
    const owner = watch;
    const current = following;
    following = undefined;
    show($, []);
    await Promise.all([owner.close(), current?.stop()]);
    const ended = await next(e);
    // /clear and resume keep the module loaded without another session.start.
    if (watch === owner) watch = new WatchOwner();
    return ended;
  });
};
