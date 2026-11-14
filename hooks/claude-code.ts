/**
 * Leaf's Claude Code hooks module: the band above the prompt that shows the
 * session's pages, the drawing of Leaf's own rows in the conversation, the fork
 * of the conversation Leaf's clerk asks at each turn's end (`clerk`), the fork
 * that writes the agent's working line on a thread's waiting messages at once
 * (`forkReply`), and the completions a page server asks of the session's model,
 * such as a thread's title or a widget's `generate` (`complete`). Claude
 * Code loads it from the installed plugin (measured at 2.1.305). It neither
 * watches nor wakes the session: `hooks.json`'s background Stop registration
 * keeps the watch between turns. A watch here would wake with a prompt, which
 * Claude Code drops from an Escape until the user next types, so every wake after
 * an Escape became a cross-session nudge (measured at 2.1.307 with the
 * claude-code journey).
 *
 * Starting an idle turn always draws a row, and no hook or exit code wakes the
 * session without one (read in 2.1.307's source). The watch's wake is a task
 * notification whose summary `hooks.json` names (`rewakeSummary`, an internal
 * field of Claude Code's hook schema), and the module draws that row as nothing,
 * leaving the band to show the agent at work; a nudge, which comes as another
 * session's message, it draws as one dim line. The model reads both whole, and
 * ctrl+o shows them as Claude Code draws them.
 *
 * A module's processes inherit Claude Code's own environment, which names no
 * session of its own, so every call states the session and Claude Code's process
 * as a hook's environment does. That process is the parent of every process the
 * module starts (measured at Claude Code 2.1.291). A follower that fails reports
 * its diagnostics through Claude Code's UI log.
 *
 * The band has a line for each live page the session holds: the word Leaf in the
 * tone the page's Leaf panel gives its leaf, a link to the page, what is On the
 * user, and its open threads with how many hold words the user hasn't read, the
 * counts the panel marks, then the agent's status. It goes above whatever other
 * plugins draw there. Claude Code keeps an empty row between the band and the
 * prompt (measured at 2.1.306); a negative margin to close it hides the band.
 * `leaf-dev claude-code-session` runs a session that draws it from this tree.
 *
 * In the terminal a click on the link opens the page wherever the terminal runs,
 * SSH included. No escape sequence makes a terminal open a URL without a click,
 * and no `$` call reaches the user's browser, so each line ends with a button for
 * the keyboard, the first focused once ctrl+x tab takes the band, for Enter to
 * press. Where the user sits at this machine, which Leaf's server judges by
 * SSH_CONNECTION (`page_access`), it opens the page in the browser; over SSH a
 * browser started here would open on the wrong machine, so it copies the link to
 * the user's own clipboard, which OSC 52 reaches. Other surfaces draw the link as
 * an anchor their keyboard reaches.
 *
 * In the terminal one link runs from the word Leaf through the title. The desktop
 * app draws a `Link` as plain text unless it goes to https or localhost, but links
 * any http URL in `Markdown`, which takes no color, so there the title alone is a
 * markdown link (measured at the app's Claude Code 2.1.304). Linking to localhost
 * instead would open the page at another origin than every other link to it,
 * with its own cookie jar and drafts, and send the host key's cookie to whatever
 * else the user serves on localhost.
 *
 * A follower (`bin/leaf hook --harness claude-code
 * --if-claimed --pages`) prints that list, with the completions page servers ask
 * of the session (`src/leaf/completions.py`), whenever either changes, and exits
 * once the session holds no page; the launcher answers it without starting uv in a
 * session holding none. It is also the session's forks lane (`src/leaf/forks.py`):
 * each page it lists carries the threads Leaf holds for a fork's line. The session
 * takes a page only through a `leaf` command, so the
 * module starts the follower as the session starts, after each Bash call that
 * runs `leaf`, and as a turn starts or a main-loop turn ends, once none is
 * running; a request while one runs starts another once it exits.
 *
 * Claude Code generates declarations under .claude-plugin/types/ and a root
 * tsconfig.json when it loads the plugin. Those declarations are absent from
 * its npm package, so hooks/tsconfig.json type-checks only Pi and its watch owner.
 * `pnpm run check:hooks` also runs `claude plugin validate` from the Claude Code
 * that `package.json` pins, which fails where Claude Code would refuse to load this
 * module, as it refuses a `$.env.get` whose name isn't a string literal. A refused
 * module leaves the session with no band, no clerk and no thread forks, and Claude
 * Code reports the refusal only in its debug log, so the follower records the
 * process it runs in and Leaf's Stop hook tells the user where none ran
 * (`ClaudeCodeHarness.unloaded_module`).
 */

import type {
  EngineInterface,
  ModelCompleteRequest,
  Register,
  RenderElement,
  RenderSurface,
  UiPressArgument,
} from "claude-code";

// Claude Code's process, read once by `sessionOf`.
let claudePid = "";
// Whether the user reached this machine over SSH, read once by the band.
let remote: boolean | undefined;
// Whether a fork writes held thread messages' line (`forkReply`), read once with Claude
// Code's process: `LEAF_FORK_REPLIES=off` in Claude Code's environment leaves every
// message to the session, as the claude-code journey's delivery steps need.
let repliesFork = true;

// The summary `hooks.json` gives the background watch's wake, which Claude Code
// draws as a task notification's row, and the words of the nudge Leaf sends
// through session messaging (`harness.NUDGE_WORDS`). A module can import neither
// home, so its test draws both rows from them (test_interact_claude_code_module.py).
const WAKE_SUMMARY = "Leaf: new input";
const NUDGE_WORDS = "has new input, which arrives with this message.";

// A live page the session holds, as the follower prints it (`hooks.cmd_pages`).
type Leaf = {
  page_key: string;
  url: string;
  title: string;
  on_user: number;
  threads: { open: number; unread: number };
  activity: {
    presence: string;
    state: string;
    reason: string | null;
    detail: string;
  };
  // The page's threads held for a fork (`forks.held`).
  forks?: Held[];
};

// What the follower prints each time it changes (`hooks.cmd_pages`): the live pages,
// and the completions page servers ask of the session that still wait for a reply
// (`completions.pending`).
type Listing = { pages: Leaf[]; completions: Completion[] };

// A thread whose waiting messages Leaf holds for a fork, as the follower prints it.
type Held = { page: string; thread: string; inputs: string[] };

// A completion a page server asks of the session, as the follower prints it.
type Completion = { id: string; request: ModelCompleteRequest };

// The color the word Leaf wears for where the agent's side of a page stands
// (`activity.py`), in Claude Code's theme: the tone the page's Leaf panel paints its
// leaf (`.lf-dot` in chrome.css, `toneOf` in activity-words.js), muted where no
// session holds the page or the agent closed it.
function toneOf({ presence, state, reason }: Leaf["activity"]) {
  if (state === "running" || reason === "terminal") return "suggestion";
  if (presence === "here") return state === "blocked" ? "warning" : "success";
  return presence === "away" ? "warning" : "inactive";
}

/** What a line says of the agent's work, in the band's own few words: the agent's
 * sentence while it works, Quiet or Away when it has gone silent, and nothing while
 * it is ready, the usual case, which the tone already says. An All pages row
 * (`leafRow` in activity-words.js) says more, such as when the agent last checked
 * in; this module can't import it, since its graph reaches the page's framework and
 * Lit by the server's absolute paths, which no module loader here resolves. */
function statusOf({ presence, state, reason, detail }: Leaf["activity"]) {
  const stated = (word: string) => (detail ? `${word} — ${detail}` : word);
  // The agent's own sentence, or none: the tone of the word Leaf says it works.
  if (state === "running" || reason === "terminal") return detail;
  if (presence === "here") return state === "blocked" ? stated("Quiet") : "";
  return presence === "away" ? "Away" : "";
}

// The follower's last list, how to stop the follower while one runs, and whether
// something asked for one while it ran, which may have outlived its last read.
let leaves: Leaf[] = [];
let following: { stop: () => unknown } | undefined;
let followAgain = false;

/** The session's id, once Claude Code's process is known. A module loaded or reloaded
 * mid-session sees no session.start, so whichever hook comes first reads it. */
async function sessionOf($: EngineInterface) {
  if (!claudePid) {
    claudePid = (await $.process.run(["/bin/sh", "-c", "echo $PPID"])).stdout.trim();
    repliesFork = (await $.env.get("LEAF_FORK_REPLIES")) !== "off";
  }
  return $.session.id();
}

function environment(session: string) {
  return { CLAUDE_CODE_SESSION_ID: session, CLAUDE_PID: claudePid };
}

function launcher($: EngineInterface) {
  return `${$.plugin.root}/bin/leaf`;
}

/** Log the follower's failure, to the conversation unless a signal from outside
 * the module ended it, which the launcher's shell reports as 128 plus the signal:
 * as SIGTERM ends it while a session sits idle, or SIGHUP as its terminal closes.
 * That ending is no failure of Leaf's to show the user. */
function report($: EngineInterface, text: string, code: number | null) {
  $.ui.log(text, code !== null && code > 128 ? { to: "debug" } : undefined);
}

// The command that opens its first argument in this machine's browser.
const OPENER = '[ "$(uname)" = Darwin ] && exec open "$1"; exec xdg-open "$1"';

/** What a line's button does: open the page here, or over SSH copy its link to
 * the clipboard of the surface pressed on. */
async function openPage(
  $: EngineInterface,
  { url, title }: Leaf,
  surface: RenderSurface,
) {
  try {
    if (remote) {
      const copied = await $.ui.copy({ text: url, surface });
      if (copied.isCopied) $.ui.toast(`Copied the link to ${title}`);
      else $.ui.log(`Leaf: the link to ${title} was not copied (${copied.reason})`);
      return;
    }
    const ran = await $.process.run(["/bin/sh", "-c", OPENER, "sh", url]);
    if (ran.exitCode !== 0)
      $.ui.log(
        `Leaf: opening ${title} exited with code ${ran.exitCode}${ran.stderr.trim() ? `: ${ran.stderr.trim()}` : ""}`,
      );
  } catch (error) {
    $.ui.log(`Leaf: opening ${title} failed: ${error}`);
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
      input: JSON.stringify({
        hook_event_name: "Pages",
        session_id: session,
        forks: repliesFork,
      }),
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
    // Whether it ended to be started again under the Leaf the session's delivery
    // runs now, which it says by EX_TEMPFAIL, 75 in sysexits.h (`hooks.cmd_pages`).
    let renewed = false;
    try {
      for await (const chunk of stream) {
        if (chunk.stream === "stderr") {
          stderr += chunk.text;
          continue;
        }
        const lines = (line + chunk.text).split("\n");
        line = lines.pop() ?? "";
        const last = lines.at(-1);
        if (last === undefined || following !== current) continue;
        const listed: Listing = JSON.parse(last);
        show($, listed.pages);
        for (const page of listed.pages)
          for (const held of page.forks ?? []) forkReply($, session, held);
        for (const asked of listed.completions) complete($, session, asked);
      }
      const result = await stream.result;
      renewed = result.code === 75;
      if (result.code !== 0 && !renewed && following === current)
        report(
          $,
          `Leaf: the pages follower exited with code ${result.code}${stderr.trim() ? `: ${stderr.trim()}` : ""}`,
          result.code,
        );
    } catch (error) {
      if (following === current) $.ui.log(`Leaf: the pages follower failed: ${error}`);
    } finally {
      // It exits once the session holds no page, or never starts in one holding none,
      // and to be started again under a Leaf that moved on.
      if (following === current) {
        following = undefined;
        if (followAgain || renewed) follow($, session);
        else show($, []);
      }
    }
  })();
}

/** Run one step of a model call Leaf asks for (`leaf hook --fork`: the clerk's
 * `clerk.cmd_fork`, a held thread's `forks.cmd_reply`, or a completion's reply,
 * `completions.cmd_reply`) with `payload`, and what it printed, or undefined where
 * it printed nothing. */
async function forkStep(
  $: EngineInterface,
  session: string,
  payload: Record<string, unknown>,
) {
  const ran = await $.process.run(
    [launcher($), "hook", "--harness", "claude-code", "--if-claimed", "--fork"],
    {
      env: environment(session),
      stdin: JSON.stringify({
        hook_event_name: "Fork",
        session_id: session,
        ...payload,
      }),
      timeoutMs: 60_000,
    },
  );
  if (ran.exitCode !== 0)
    throw new Error(
      `exited with code ${ran.exitCode}${ran.stderr.trim() ? `: ${ran.stderr.trim()}` : ""}`,
    );
  const printed = ran.stdout.trim();
  return printed ? JSON.parse(printed) : undefined;
}

// Whether a fork is out, and whether another main-loop turn ended while it was.
let forking = false;
let forkAgain = false;

/** Leaf's clerk: as a main-loop turn ends in a session holding a live page, fork the
 * conversation with the question Leaf asks of it, and hand the answer back for Leaf
 * to write (`src/leaf/clerk.py`, whose header says what it writes and why). It runs
 * off the turn's path, and a turn that ends while a fork is out starts one more
 * after it. `$.model.fork` resends the main thread's own last request, its model,
 * system prompt and tools, so the cache serves the conversation, at the session's
 * own effort (`runFork`); it takes no answer schema, so Leaf checks the answer
 * against its own (`read_answer`). What Leaf wrote goes to the debug log, beside
 * Claude Code's own lines for the fork's tokens (`Forked agent [plugin_model_fork]
 * finished`); the module logs no usage of its own, since the debug log redacts
 * a `*_tokens` field, and hands the fork's usage and time, or why it gave no answer,
 * to Leaf, which notes them with the answer in each page's diagnostics. In the
 * claude-code journey on 2026-11-04, with the session at xhigh, 102 forks at low
 * over a 57–202k-token conversation read 98% of it from the cache, cost
 * $0.04–0.12 each at list price and took 0.5–8 s. */
async function clerk($: EngineInterface, session: string) {
  if (forking) {
    forkAgain = true;
    return;
  }
  forking = true;
  try {
    do {
      forkAgain = false;
      try {
        const asked = await forkStep($, session, {});
        if (!asked) continue;
        const ran = await runFork($, asked);
        const applied = await forkStep($, session, { basis: asked.basis, ...ran });
        if (ran.answer === undefined) {
          $.ui.log(`Leaf: the clerk's fork gave no answer (${ran.failed})`, {
            to: "debug",
          });
          continue;
        }
        const wrote = applied.wrote.length;
        const changed = applied.changed.length;
        const told = applied.told.length;
        $.ui.log(
          `Leaf: the clerk wrote ${wrote} record${wrote === 1 ? "" : "s"}, changed ${changed} passage${changed === 1 ? "" : "s"} and told the agent ${told} line${told === 1 ? "" : "s"}${applied.dropped ? `, and wrote no records on a page where ${applied.dropped}` : ""}`,
          { to: "debug" },
        );
      } catch (error) {
        // An answer Leaf refused, as one that doesn't fit the schema, or a failed
        // step of Leaf's, writes nothing. The user never meets the clerk, so its
        // failures go to the debug log, and a turn that ended meanwhile still forks.
        $.ui.log(`Leaf: the clerk wrote nothing: ${error}`, { to: "debug" });
      }
    } while (forkAgain);
  } finally {
    forking = false;
  }
}

// The main thread's last request, which `$.model.fork` resends: the model and
// effort the main thread named, how many messages it carried and the newest row
// stored as it went out (`turn.step`, `sent`), with the newest row stored by the time
// of the fork (`row`), each the transcript's id from `session.append`, which skips
// attachments, hook context and compaction summaries. The fork reads the
// conversation as it would next go out: with a tool call running, to `sent`, since
// the call's tool_use can't go out before its result; otherwise to `row`, a turn's
// final reply included (`notes/fork-replies.md`, under the fork probes, and a
// turn-end ask in the claude-code journey on 2026-11-01 that quoted only that reply).
// Each fork hands this to Leaf, so a fork's diagnostics say where a replay cuts the
// conversation.
let lastStep:
  | { model: string; effort?: string | number; messages: number; sent?: string }
  | undefined;
let lastRow: string | undefined;

function request() {
  return (
    lastStep && { ...lastStep, ...(lastRow === undefined ? {} : { row: lastRow }) }
  );
}

/** Fork the conversation with the prompt Leaf asked for, and what Leaf notes of the
 * fork: its `answer`, or why it gave none (`failed`, a thrown error included), with
 * its time, its usage, and the main thread's request it resent (`request`).
 *
 * The fork thinks at the session's effort, and Leaf's prompt asks it to answer
 * straight away (`clerk.py` and `forks.py` say what that costs). A fork at another
 * effort reads the conversation from the cache only where Claude Code's per-message
 * effort reaches the model; elsewhere, as on Vertex, through a proxy that rewrites
 * mid-conversation system messages, or with `CLAUDE_CODE_DISABLE_EXPERIMENTAL_BETAS`,
 * it writes the conversation to the cache again from the session's first reply on
 * (#5891, #5904). Learning that per backend from each check's usage (#5892, #5907)
 * cost a stored answer per backend, a rewrite to learn it and another to check it
 * again each week. */
async function runFork(
  $: EngineInterface,
  asked: { prompt: string },
): Promise<Record<string, unknown>> {
  const resent = request();
  const started = await $.clock.now();
  let ran: Record<string, unknown>;
  try {
    // TODO: fork at `low` effort again (`$.model.fork({ prompt, effort: "low" })`)
    // once Claude Code carries a change of effort per message on every backend it
    // serves, with no environment variable to set (`ModelForkRequest.effort`).
    const reply = await $.model.fork({ prompt: asked.prompt });
    ran = {
      ...(reply.isAnswered ? { answer: reply.text } : { failed: reply.reason }),
      ...("usage" in reply ? { usage: reply.usage } : {}),
    };
  } catch (error) {
    ran = { failed: String(error) };
  }
  return {
    ...ran,
    elapsed_ms: (await $.clock.now()) - started,
    ...(resent ? { request: resent } : {}),
  };
}

// The tool calls the main thread is running, by their tool_use ids, which a fork
// can't see: the main thread's last request predates them.
const running = new Map<string, { tool: string; input: Record<string, string> }>();
// The arguments of a call a fork's prompt names, each cut to a line's worth.
const NAMED = ["command", "description", "file_path", "pattern", "url", "prompt"];

// The held threads a fork has been made for, by page, thread and newest message.
const replied = new Set<string>();

/** Fork the conversation for the agent's working line on a held thread's waiting
 * messages, which Leaf posts before it hands them to the session
 * (`src/leaf/forks.py`, whose header holds the states a thread moves through).
 * Leaf writes the prompt and checks again that
 * the thread is held; the module adds the calls the session is running, makes the
 * fork, and hands back the line, or the failure, which hands the thread over. Forks
 * for different threads run side by side, and the follower lists a held thread until
 * its fork decides, so each is made once. Its outcomes go to the debug log and the
 * page's diagnostics, since the user meets the line only as the agent's. */
function forkReply($: EngineInterface, session: string, held: Held) {
  const key = `${held.page} ${held.thread} ${held.inputs.at(-1)}`;
  if (replied.has(key)) return;
  replied.add(key);
  void (async () => {
    try {
      const calls = [...running.values()];
      const asked = await forkStep($, session, { thread: held, running: calls });
      if (!asked) return;
      const ran = await runFork($, asked);
      const outcome = await forkStep($, session, {
        thread: held,
        running: calls,
        ...ran,
      });
      $.ui.log(`Leaf: a fork took thread ${held.thread}: ${outcome?.outcome}`, {
        to: "debug",
      });
    } catch (error) {
      // Leaf's own step failed. Telling Leaf hands the thread to the session now and
      // notes why in the page, which a session without a debug log keeps nowhere
      // else; where Leaf can't be told either, the hold runs out.
      $.ui.log(`Leaf: the fork for thread ${held.thread} failed: ${error}`, {
        to: "debug",
      });
      await forkStep($, session, {
        thread: held,
        failed: `Leaf's step failed: ${error}`,
      }).catch(() => undefined);
    }
  })();
}

// The completions made for Leaf, by request, so each is made once.
const completed = new Set<string>();

/** Make a completion a page server asks of the session, such as a thread's title
 * (`src/leaf/completions.py`, whose header says how the request reaches the
 * module): `$.model.complete` with the request as Leaf wrote it, on the session's
 * own model client, then hand Leaf what it came to, the text or why there is none,
 * with its usage and time. The page server waits for the reply until its deadline
 * and fails the request where none comes, so a reply Leaf couldn't take goes only
 * to the debug log. */
function complete($: EngineInterface, session: string, asked: Completion) {
  if (completed.has(asked.id)) return;
  completed.add(asked.id);
  void (async () => {
    const started = await $.clock.now();
    let ran: Record<string, unknown>;
    try {
      const reply = await $.model.complete(asked.request);
      ran = reply.isAnswered
        ? { text: reply.text, usage: reply.usage }
        : {
            failed: reply.reason,
            ...(reply.reason === "api-error"
              ? { status: reply.status, error: reply.error }
              : {}),
            usage: reply.usage,
          };
    } catch (error) {
      // A request the engine refuses to send, such as one for a blocked model.
      ran = { failed: String(error) };
    }
    try {
      await forkStep($, session, {
        completion: asked.id,
        ...ran,
        elapsed_ms: (await $.clock.now()) - started,
      });
    } catch (error) {
      $.ui.log(`Leaf: the reply to completion ${asked.id} was lost: ${error}`, {
        to: "debug",
      });
    }
  })();
}

export const register: Register = (on) => {
  on("session.start", async ($, e, next) => {
    const started = await next(e);
    const session = await sessionOf($);
    follow($, session);
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

  // Every call the main thread runs, for the prompt of a fork made meanwhile.
  on("tool.call", async ($, e, next) => {
    if (e.agentId !== undefined) return next(e);
    const input: Record<string, string> = {};
    for (const name of NAMED) {
      const value = (e as Record<string, unknown>)[name];
      if (typeof value === "string") input[name] = value.slice(0, 300);
    }
    running.set(e.tool_use_id, { tool: e.tool, input });
    try {
      return await next(e);
    } finally {
      running.delete(e.tool_use_id);
    }
  });

  on("turn.step", async function* ($, e, next) {
    if (e.agentId === undefined)
      lastStep = {
        model: e.model,
        messages: e.messageCount,
        ...(e.effort === undefined ? {} : { effort: e.effort }),
        ...(lastRow === undefined ? {} : { sent: lastRow }),
      };
    return yield* next(e);
  });

  // Only the doors of the conversation's own rows: attachments, hook context and
  // compaction summaries are left to the plugins that rewrite them, and Claude Code
  // tells the user when one of those sends a row past a handler beneath it (read
  // at 2.1.321).
  for (const door of ["model", "prompt", "tool-message", "queue", "note"] as const)
    on("session.append", { door }, async ($, e, next) => {
      const stored = await next(e);
      if (e.agentId === undefined && stored.deny === undefined) lastRow = stored.uuid;
      return stored;
    });

  // A resumed or cleared session raises no session.start, so its first turn follows.
  on("turn.start", ($, e, next) => {
    if (e.agentId !== undefined) return next(e);
    void sessionOf($).then((session) => follow($, session));
    return next(e);
  });

  on("turn.complete", async ($, e, next) => {
    const completed = await next(e);
    if (e.agentId !== undefined) return completed;
    const session = await sessionOf($);
    follow($, session);
    // Only a turn the model answered: an interrupted one has no reply to read.
    // Leaf, not the band, says whether the session holds a page: the band may not
    // yet list one the turn's last command claimed, and `--if-claimed` answers a
    // session holding none without starting uv.
    if (e.reason === "answer") void clerk($, session);
    return completed;
  });

  // The band is shared: Leaf's lines go above whatever the plugins beneath draw.
  // Leaf's own rows in the conversation stay quiet, unless ctrl+o expands them; the
  // model reads them whole either way.
  on("ui.render", { component: "UserMessage" }, async ($, e, next) => {
    if (e.props.isExpanded) return next(e);
    const { origin, text } = e.props;
    const { Box, Text } = $.ui.resolve(e);
    if (origin.kind === "task-notification" && text === WAKE_SUMMARY)
      return h(Box, {}) as RenderElement;
    if (origin.kind === "peer" && text.includes(NUDGE_WORDS))
      return h(Text, { dimColor: true }, "Leaf: new input") as RenderElement;
    return next(e);
  });

  on("ui.render", { component: "AbovePrompt" }, async ($, e, next) => {
    const beneath = await next(e);
    if (leaves.length === 0 || e.props.hasSurvey) return beneath;
    const { Box, Text, Link, Markdown, Button } = $.ui.resolve(e);
    if (e.surface === "terminal") remote ??= Boolean(await $.env.get("SSH_CONNECTION"));
    // What JSX would type; the module stays `.ts` for Node, which runs it in tests.
    const dim = (text: string) => h(Text, { dimColor: true }, text);
    // A line keeps one row, its status cut first; only the counts that aren't zero
    // show, and what waits on the user takes a color.
    const line = (page: Leaf, index: number) => {
      const { url, title, on_user, threads, activity } = page;
      const status = statusOf(activity);
      const leaf = h(Text, { color: toneOf(activity), weight: "semibold" }, "Leaf");
      const counts = [
        ...(on_user
          ? [dim(" · "), h(Text, { color: "warning" }, `On Me ${on_user}`)]
          : []),
        // A resolved thread can still hold unread words.
        ...(threads.open || threads.unread ? [dim(` · Threads ${threads.open}`)] : []),
        ...(threads.unread
          ? [dim(", "), h(Text, { color: "suggestion" }, `${threads.unread} new`)]
          : []),
        ...(status ? [dim(` · ${status}`)] : []),
      ];
      if (e.surface === "terminal") {
        // The button stays whole at the line's end while the text before it is cut.
        return h(
          Box,
          { gap: 1 },
          h(
            Text,
            { wrap: "truncate-end" },
            h(Link, { href: url }, leaf, " ", h(Text, { underline: true }, title)),
            ...counts,
          ),
          h(
            Box,
            { flexShrink: 0 },
            h(Button, {
              key: page.page_key,
              label: remote ? "copy link" : "open",
              plain: true,
              dimColor: true,
              ...(index === 0 ? { autoFocus: true } : {}),
              onPress: (press: UiPressArgument) =>
                void openPage($, page, press.surface),
            }),
          ),
        );
      }
      // The title keeps its width and the counts are cut, as the terminal's
      // truncation cuts them.
      const escaped = title.replace(/[!-/:-@[-`{-~]/g, "\\$&");
      return h(
        Box,
        { flexDirection: "row", overflow: "hidden" },
        h(Box, { flexShrink: 0 }, h(Text, {}, leaf, " ")),
        h(Box, { flexShrink: 0 }, h(Markdown, { text: `[${escaped}](${url})` })),
        ...(counts.length
          ? [h(Box, { minWidth: 0 }, h(Text, { wrap: "truncate-end" }, ...counts))]
          : []),
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
    const current = following;
    following = undefined;
    show($, []);
    await current?.stop();
    return next(e);
  });
};
