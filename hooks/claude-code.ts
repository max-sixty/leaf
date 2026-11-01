/**
 * Leaf's Claude Code hooks module: the band above the prompt that shows the
 * session's pages, the drawing of Leaf's own rows in the conversation, and the
 * fork of the conversation Leaf's clerk asks at each turn's end (`clerk`). Claude
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
 * --if-claimed --pages`) prints that list whenever it changes and exits once the
 * session holds no page; the launcher answers it without starting uv in a session
 * holding none. The session takes a page only through a `leaf` command, so the
 * module starts the follower as the session starts, after each Bash call that
 * runs `leaf`, and as a turn starts or a main-loop turn ends, once none is
 * running; a request while one runs starts another once it exits.
 *
 * Claude Code generates declarations under .claude-plugin/types/ and a root
 * tsconfig.json when it loads the plugin. Those declarations are absent from
 * its npm package, so CI's hooks/tsconfig.json checks Pi and its watch owner.
 */

import type {
  EngineInterface,
  Register,
  RenderElement,
  RenderSurface,
  UiPressArgument,
} from "claude-code";

// Claude Code's process, read once by `sessionOf`.
let claudePid = "";
// Whether the user reached this machine over SSH, read once by the band.
let remote: boolean | undefined;

// The summary `hooks.json` gives the background watch's wake, which Claude Code
// draws as a task notification's row, and the words of the nudge Leaf sends
// through session messaging (`ClaudeCodeHarness.nudge`).
const WAKE_SUMMARY = "Leaf: new input";
const NUDGE_WORDS = "has new input, which arrives with this message.";

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
 * (`leafRow` in activity-words.js), less its bare Listening and Awaits, since
 * listening is the usual case. */
function statusOf({ kind, detail }: Leaf["activity"]) {
  const stated = (word: string) => (detail ? `${word} — ${detail}` : word);
  // The agent's own sentence, as the row gives it (`leafRow`), or none: the tone of
  // the word Leaf says it works.
  if (kind === "working") return detail;
  if (kind === "stalled") return stated("Quiet");
  if (kind === "away") return "Away";
  return "";
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
        report(
          $,
          `Leaf: the pages follower exited with code ${result.code}${stderr.trim() ? `: ${stderr.trim()}` : ""}`,
          result.code,
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

/** Run one half of Leaf's clerk (`leaf hook --fork`, `clerk.cmd_fork`) with
 * `payload`, and what it printed, or undefined where it printed nothing. */
async function clerkStep(
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
 * system prompt, tools and effort, so the cache serves the conversation; it takes
 * no answer schema, so Leaf checks the answer against its own (`read_answer`).
 * What Leaf wrote goes to the debug log, beside Claude Code's own line for the
 * fork's tokens (`Forked agent [plugin_model_fork] finished`); the module logs no
 * usage of its own, since the debug log redacts a `*_tokens` field. In the
 * claude-code journey on 2026-10-29, twelve forks over a 46–77k-token
 * conversation read it all from the cache, cost $0.015–0.026 each at list price and
 * took 1–6 s. */
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
        const asked = await clerkStep($, session, {});
        if (!asked) continue;
        const reply = await $.model.fork({ prompt: asked.prompt });
        if (!reply.isAnswered) {
          $.ui.log(`Leaf: the clerk's fork gave no answer (${reply.reason})`, {
            to: "debug",
          });
          continue;
        }
        const applied = await clerkStep($, session, {
          answer: reply.text,
          basis: asked.basis,
        });
        const wrote = applied.wrote.length;
        const changed = applied.changed.length;
        const told = applied.told.length;
        $.ui.log(
          `Leaf: the clerk wrote ${wrote} record${wrote === 1 ? "" : "s"}, changed ${changed} passage${changed === 1 ? "" : "s"} and told the agent ${told} line${told === 1 ? "" : "s"}${applied.dropped ? `, and wrote no records on a page where ${applied.dropped}` : ""}`,
          { to: "debug" },
        );
      } catch (error) {
        // A failed fork, or an answer Leaf refused, as one that doesn't fit the
        // schema, writes nothing. The user never meets the clerk, so its failures go
        // to the debug log, and a turn that ended meanwhile still forks.
        $.ui.log(`Leaf: the clerk wrote nothing: ${error}`, { to: "debug" });
      }
    } while (forkAgain);
  } finally {
    forking = false;
  }
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
      const leaf = h(
        Text,
        { color: TONES[activity.kind] ?? "inactive", weight: "semibold" },
        "Leaf",
      );
      const counts = [
        ...(on_user
          ? [dim(" · "), h(Text, { color: "warning" }, `On me ${on_user}`)]
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
