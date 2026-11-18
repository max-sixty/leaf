/**
 * Leaf's Claude Code hooks module: the band above the prompt that shows the
 * session's pages, the drawing of Leaf's own rows in the conversation, and the
 * carrier of the model calls and agents Leaf asks of the session (`carry`): forks
 * of the conversation, such as the turn-end check's and the one that writes the
 * agent's working line on a thread's waiting messages, completions on the
 * session's model, such as a thread's title, and forks with the session's tools
 * that do a thread's work. Leaf's Python decides each one and what its result
 * means, as instructions the module runs and reports on (`src/leaf/carrier.py`,
 * whose header holds that contract), so a change to Leaf's forks needs no change
 * here. The module adds what only it sees: the tool calls the main thread is
 * running (`running`), the main thread's last request (`request`), a main-loop
 * turn's end (`turnEnded`) and each spawned fork's run ending (`endFork`). Claude
 * Code runs none of this module's hooks for a working fork's tool calls, as a
 * plugin's hooks never see the calls of an agent it spawned (measured at
 * 2.1.322), so `hooks.json`'s PostToolBatch carries the fork's further input
 * (`hook_transport.carry_agent_turn`), and the fork names its own turn in its
 * `leaf` commands, as Leaf's prompt tells it (`forks.work_prompt`).
 * Claude Code loads the module from the installed plugin (measured at 2.1.305).
 * It neither watches nor wakes the session: `hooks.json`'s background Stop registration
 * keeps the watch between turns. A watch here would wake with a prompt, which
 * Claude Code drops from an Escape until the user next types, so every wake after
 * an Escape would become a cross-session nudge (measured at 2.1.307 with the
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
 * `leaf-dev journey session` runs a session that draws it from this tree.
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
 * --if-claimed --pages`) prints that list, with the instructions Leaf has for the
 * module, whenever either changes, and exits once the session holds no page; the
 * launcher answers it without starting uv in a session holding none. It is also the
 * session's forks lane (`src/leaf/forks.py`), listing a thread Leaf keeps back for a
 * line fork as it is admitted. The session takes a page only through a `leaf`
 * command, so the
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
 * module leaves the session with no band and none of Leaf's forks, and Claude
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
  activity: { kind: string; detail: string };
};

// An instruction Leaf gives the module (`src/leaf/carrier.py`, whose header holds the
// contract): its id, unique among the session's; what to run (`do`); the basis the
// module hands back untouched with each report of it; and the `request` the module
// passes as it stands to the call `do` names.
type Instruction = { id: string; do: string; basis: unknown; request?: unknown };

// What each call takes, as Claude Code declares it.
type ForkRequest = Parameters<EngineInterface["model"]["fork"]>[0];
type SpawnRequest = Parameters<EngineInterface["agent"]["spawn"]>[0];
type SendRequest = Parameters<EngineInterface["session"]["send"]>[0];

// What Leaf answers a report with: the instructions to run next, and a line for Claude
// Code's debug log.
type Answer = { do?: Instruction[]; log?: string } | undefined;

// What the follower prints each time it changes (`hooks.cmd_pages`): the live pages,
// and the instructions Leaf has for the module.
type Listing = { pages: Leaf[]; do: Instruction[] };

// The color the word Leaf wears for each activity kind, in Claude Code's theme: the
// tone the page's Leaf panel paints its leaf (`.lf-dot` in chrome.css), muted for the
// rest.
const TONES: Record<string, string> = {
  working: "suggestion",
  listening: "success",
  stalled: "warning",
  away: "warning",
};

/** What a line says of the agent's work, in the band's own few words: the agent's
 * sentence while it works, Quiet or Away when it has gone silent, and nothing while
 * it is ready, the usual case, which the tone already says. An All pages row
 * (`leafRow` in activity-words.js) says more, such as when the agent last checked
 * in; this module can't import it, since its graph reaches the page's framework and
 * Lit by the server's absolute paths, which no module loader here resolves. */
function statusOf({ kind, detail }: Leaf["activity"]) {
  const stated = (word: string) => (detail ? `${word} — ${detail}` : word);
  // The agent's own sentence, or none: the tone of the word Leaf says it works.
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

// What the first hook after a load or reload reads once, which every later one awaits.
let initialized: Promise<void> | undefined;

/** The session's id, once Claude Code's process is known. A module loaded or reloaded
 * mid-session sees no session.start, so whichever hook comes first reads it, and
 * hooks that start meanwhile wait for that one read. */
async function sessionOf($: EngineInterface) {
  initialized ??= (async () => {
    claudePid = (await $.process.run(["/bin/sh", "-c", "echo $PPID"])).stdout.trim();
  })().catch((error) => {
    // A read that failed is read again by the next hook.
    initialized = undefined;
    throw error;
  });
  await initialized;
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
        void endForks($);
        void carry($, session, listed.do);
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

/** Report to Leaf (`leaf hook --fork`, `carrier.step`) with `payload` and the tool calls
 * the main thread is running, which no fork can see, and what Leaf answers: the
 * instructions to run next (`do`) and a line for the debug log (`log`), or undefined
 * where it printed nothing. */
async function tellLeaf(
  $: EngineInterface,
  session: string,
  payload: Record<string, unknown>,
): Promise<Answer> {
  const ran = await $.process.run(
    [launcher($), "hook", "--harness", "claude-code", "--if-claimed", "--fork"],
    {
      env: environment(session),
      stdin: JSON.stringify({
        hook_event_name: "Fork",
        session_id: session,
        running: [...running.values()],
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

// The instructions the module has begun, by id, so each runs once however often the
// follower lists it.
const begun = new Set<string>();

/** Run each of `instructions` not yet begun, side by side, each reporting what it came
 * to and then running what Leaf answers with (`runInstruction`); settled once every
 * report is in, a spawned agent's run aside, whose end reports as it comes
 * (`endFork`). */
async function carry(
  $: EngineInterface,
  session: string,
  instructions: Instruction[] = [],
) {
  const runs = [];
  for (const instruction of instructions) {
    if (begun.has(instruction.id)) continue;
    begun.add(instruction.id);
    runs.push(runInstruction($, session, instruction));
  }
  await Promise.all(runs);
}

/** Run `instruction`, report what it came to, and carry what Leaf answers with, whose
 * line goes to the debug log, since the user meets none of this but as the agent's.
 * Where Leaf's step fails, the module reports the instruction once more as failed,
 * with the agent it started, if any (`carrier.py`). */
async function runInstruction(
  $: EngineInterface,
  session: string,
  instruction: Instruction,
) {
  const { id, do: kind, basis } = instruction;
  let result: Record<string, unknown>;
  try {
    result = await perform($, instruction);
  } catch (error) {
    result = { failed: String(error) };
  }
  let answer: Answer;
  try {
    answer = await tellLeaf($, session, { done: id, do: kind, basis, ...result });
  } catch (error) {
    $.ui.log(`Leaf: the step for ${id} failed: ${error}`, { to: "debug" });
    const { agent } = result;
    await tellLeaf($, session, {
      done: id,
      do: kind,
      basis,
      ...(agent === undefined ? {} : { agent }),
      failed: `Leaf's step failed: ${error}`,
    }).catch(() => undefined);
    return;
  }
  if (answer?.log) $.ui.log(`Leaf: ${answer.log}`, { to: "debug" });
  await carry($, session, answer?.do);
}

/** What running `instruction` came to, as its report gives it (`carrier.py`). */
async function perform(
  $: EngineInterface,
  instruction: Instruction,
): Promise<Record<string, unknown>> {
  switch (instruction.do) {
    case "report":
      return {};
    case "fork":
      return forkConversation($, instruction.request as ForkRequest);
    case "complete":
      return complete($, instruction.request as ModelCompleteRequest);
    case "spawn":
      return spawnFork($, instruction);
    case "send":
      return resumeFork($, instruction);
    default:
      // What a Leaf newer than this module asks of it.
      return { failed: `the hooks module runs no "${instruction.do}"` };
  }
}

// Whether a main-loop turn's end is being reported, and whether another ended while it
// was.
let endReported = false;
let endedAgain = false;

/** Tell Leaf that a main-loop turn the model answered has ended, and carry what it
 * answers with, such as the fork its turn-end check asks of the conversation
 * (`src/leaf/clerk.py`, whose header says what it writes and why). It runs off the
 * turn's path, one at a time, and a turn that ends while one runs reports once more
 * after it. */
async function turnEnded($: EngineInterface, session: string) {
  if (endReported) {
    endedAgain = true;
    return;
  }
  endReported = true;
  try {
    do {
      endedAgain = false;
      try {
        const answer = await tellLeaf($, session, { turn_end: true });
        if (answer?.log) $.ui.log(`Leaf: ${answer.log}`, { to: "debug" });
        await carry($, session, answer?.do);
      } catch (error) {
        // The user never meets the turn-end check, so its failures go to the debug
        // log, and a turn that ended meanwhile still reports.
        $.ui.log(`Leaf: the turn's end went unreported: ${error}`, { to: "debug" });
      }
    } while (endedAgain);
  } finally {
    endReported = false;
  }
}

// The main thread's last request, which `$.model.fork` resends: the model and
// effort the main thread named, how many messages it carried and the newest row
// stored as it went out (`turn.step`, `sent`), with the newest row stored by the time
// of the fork (`row`), each the transcript's id from `session.append` on the doors
// `register` names. The fork reads the conversation as it would next go out: with a
// tool call running, to `sent`, since the call's tool_use can't go out before its
// result; otherwise to `row`, a turn's final reply included (`notes/fork-replies.md`,
// under the fork probes). Each fork hands this to Leaf, so a fork's diagnostics say
// where a replay cuts the conversation.
let lastStep:
  | { model: string; effort?: string | number; messages: number; sent?: string }
  | undefined;
let lastRow: string | undefined;

function request() {
  return (
    lastStep && { ...lastStep, ...(lastRow === undefined ? {} : { row: lastRow }) }
  );
}

/** Fork the conversation with Leaf's `request`, as Leaf wrote it (`carrier.fork`), and
 * what Leaf notes of the fork: its `answer`, or why it gave none (`failed`, a thrown
 * error included), with its time, its usage, and the main thread's request it resent
 * (`resent`). `$.model.fork` resends the main thread's own last request, its model,
 * system prompt and tools, so the cache serves the conversation, and denies the fork
 * every tool call; it takes no answer schema, so Leaf checks the answer against its
 * own. Claude Code's debug log has its own line for the fork's tokens (`Forked agent
 * [plugin_model_fork] finished`), and redacts a `*_tokens` field, so the module logs
 * no usage of its own and hands it to Leaf, which notes it with the answer in each
 * page's diagnostics. */
async function forkConversation(
  $: EngineInterface,
  forked: ForkRequest,
): Promise<Record<string, unknown>> {
  const resent = request();
  const started = await $.clock.now();
  let ran: Record<string, unknown>;
  try {
    const reply = await $.model.fork(forked);
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
    ...(resent ? { resent } : {}),
  };
}

// The tool calls the main thread is running, by their tool_use ids, which a fork
// can't see: the main thread's last request predates them.
const running = new Map<string, { tool: string; input: Record<string, string> }>();
// The arguments of a call a fork's prompt names, each cut to a line's worth.
const NAMED = ["command", "description", "file_path", "pattern", "url", "prompt"];

// The forks the module spawned or resumed to do a thread's work, by agent id, each with
// when its present run started and the instruction it ran (`kept`), which the run's end
// reports under. `$.state` keeps them, which a reload of this module's code leaves
// standing, so a fork made before a reload still reports its end
// (types/leaf-state.d.ts). A fork whose run ended stays, with how it ended, until Leaf
// has heard (`endFork`).
const FORKS = { plugin: "leaf", key: "forks" } as const;
type Run = { answer: string } | { failed: string };
type Fork = { started: number; id: string; do: string; basis: unknown; ended?: Run };

// How each run ended, by agent id, of the agents that ended while a spawn was in
// flight and the module hadn't registered: a fork whose run ends before
// `$.agent.spawn` returns its id (`spawnFork`). It holds anything only while a spawn
// is in flight (`spawning`), so the session's other subagents leave nothing here.
const endedEarly = new Map<string, Run>();
let spawning = 0;

// The fork runs whose end is being told to Leaf, by agent id and instruction, so a
// listing that arrives meanwhile doesn't tell it twice at once.
const ending = new Set<string>();

/** What `$.state` keeps of the instruction a fork runs. */
function kept(instruction: Instruction) {
  return { id: instruction.id, do: instruction.do, basis: instruction.basis };
}

/** Report that the run of the fork `agentId`, kept as `fork`, ended as `fork.ended`
 * says, and forget that run only once Leaf has heard: a step that failed, as one past
 * its timeout, leaves it to be told again (`endForks`), rather than the turn Leaf keeps
 * for it running on unseen until it lapses. Leaf hears each end at least once, and a
 * run the fork was resumed for since, under the same agent id, stays. */
async function endFork($: EngineInterface, agentId: string, fork: Fork) {
  const run = `${agentId} ${fork.id}`;
  if (fork.ended === undefined || ending.has(run)) return;
  ending.add(run);
  try {
    const session = await sessionOf($);
    const now = await $.clock.now();
    const answer = await tellLeaf($, session, {
      done: fork.id,
      do: fork.do,
      basis: fork.basis,
      agent: agentId,
      ended: fork.ended,
      elapsed_ms: now - fork.started,
    });
    await changeForks($, (forks) => {
      if (forks[agentId]?.id !== fork.id) return forks;
      const { [agentId]: _ended, ...rest } = forks;
      return rest;
    });
    if (answer?.log) $.ui.log(`Leaf: ${answer.log}`, { to: "debug" });
    await carry($, session, answer?.do);
  } catch (error) {
    $.ui.log(`Leaf: agent ${agentId}'s end went unreported: ${error}`, {
      to: "debug",
    });
  } finally {
    ending.delete(run);
  }
}

/** Tell Leaf again of each fork's end it hasn't heard of (`endFork`), as a
 * main-loop turn ends and as the pages follower lists a change to the session's
 * pages, which it does while the session is idle too: each change the user makes on
 * a page, when a fork shown working there would mislead them. Untold, the fork's turn
 * lapses within the working grace of its last renewal, which gives its thread to the
 * main thread, so no clock of the module's own retries it. */
async function endForks($: EngineInterface) {
  for (const [agentId, fork] of Object.entries((await $.state.get(FORKS)).value ?? {}))
    if (fork.ended !== undefined) void endFork($, agentId, fork);
}

/** Change the forks kept in `$.state` by `change`, against concurrent changes. */
async function changeForks(
  $: EngineInterface,
  change: (forks: Record<string, Fork>) => Record<string, Fork>,
) {
  for (;;) {
    const stored = await $.state.get(FORKS);
    const set = await $.state.set(FORKS, change(stored.value ?? {}), {
      ifVersion: stored.version,
    });
    if (set.isSet) return;
  }
}

/** Spawn the agent Leaf's `request` describes, a fork of the conversation with the
 * session's tools (`forks.step`): the agent it started, with how its run ended where
 * it ended before the module registered it, or why it failed. */
async function spawnFork(
  $: EngineInterface,
  instruction: Instruction,
): Promise<Record<string, unknown>> {
  let agentId: string | undefined;
  spawning += 1;
  try {
    ({ agentId } = await $.agent.spawn(instruction.request as SpawnRequest));
    if (agentId === undefined)
      return { failed: "the fork did not start: no agent started" };
    const id = agentId;
    const started = await $.clock.now();
    await changeForks($, (forks) => ({
      ...forks,
      [id]: { started, ...kept(instruction) },
    }));
    // A run that ended before the fork was registered reports its end now.
    const early = endedEarly.get(id);
    if (early === undefined) return { agent: agentId };
    await changeForks($, ({ [id]: _ended, ...forks }) => forks);
    return { agent: agentId, ended: early };
  } catch (error) {
    return agentId === undefined
      ? { failed: `the fork did not start: ${error}` }
      : { agent: agentId, failed: `Leaf could not register the fork: ${error}` };
  } finally {
    spawning -= 1;
    if (spawning === 0) endedEarly.clear();
  }
}

/** Send Leaf's `request` to the agent it names (`to.agentId`), as `$.session.send`
 * resumes a finished subagent from its transcript in a new run under the same id
 * (measured at 2.1.322): the agent, with why the send failed where it did, as it does
 * for an agent whose transcript is gone. It goes into `$.state` before the send, so the
 * end of its run, which may come before the send returns, reports. */
async function resumeFork(
  $: EngineInterface,
  instruction: Instruction,
): Promise<Record<string, unknown>> {
  const sending = instruction.request as SendRequest & {
    to: { agentId: string };
  };
  const { agentId } = sending.to;
  const started = await $.clock.now();
  await changeForks($, (forks) => ({
    ...forks,
    [agentId]: { started, ...kept(instruction) },
  }));
  let reason: string;
  try {
    const sent = await $.session.send(sending);
    if (sent.isDelivered) return { agent: agentId };
    reason = sent.reason;
  } catch (error) {
    reason = String(error);
  }
  await changeForks($, ({ [agentId]: _unresumed, ...forks }) => forks);
  return { agent: agentId, failed: `the fork could not be resumed: ${reason}` };
}

/** Make the completion `request`, as Leaf wrote it, on the session's own model client
 * (`src/leaf/completions.py`, whose header says how the request reaches the module),
 * and what it came to: the text or why there is none, with its usage and time. */
async function complete(
  $: EngineInterface,
  request: ModelCompleteRequest,
): Promise<Record<string, unknown>> {
  const started = await $.clock.now();
  let ran: Record<string, unknown>;
  try {
    const reply = await $.model.complete(request);
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
  return { ...ran, elapsed_ms: (await $.clock.now()) - started };
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

  // Only the doors of the rows the model reads in the transcript: attachments, hook
  // context, compaction summaries and notices are left to the plugins that rewrite
  // them, and Claude Code tells the user when one of those sends a row past a
  // handler beneath it; a queue record is no row of the conversation (read at
  // 2.1.322, whose doors `tsc -p tsconfig.json` checks this list against). The
  // model reads `tool-message` rows too, but on a machine with managed settings
  // `cc-plugin-sec-default` sends the body a Skill call loads on that door past a
  // person's plugins, so a handler there drew that notice at each session's first
  // Skill call (read and measured at 2.1.327). `row` stays on a tool's result until
  // the model next answers.
  for (const door of [
    "prompt",
    "command",
    "response",
    "tool-result",
    "delivery",
    "note",
  ] as const)
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

  // The run of a fork this module spawned or resumed ending, which reports its
  // instruction again; any other agent's ends with nothing for Leaf to do. A
  // main-loop turn ending tells Leaf again of each fork's end it hasn't heard of yet
  // (`endForks`).
  on("turn.complete", async ($, e, next) => {
    const completed = await next(e);
    if (e.agentId !== undefined) {
      const agentId = e.agentId;
      const run = e.reason === "answer" ? { answer: e.answer } : { failed: e.reason };
      const fork = (await $.state.get(FORKS)).value?.[agentId];
      if (fork === undefined) {
        if (spawning > 0) endedEarly.set(agentId, run);
        return completed;
      }
      if (fork.ended !== undefined) return completed;
      const ended = { ...fork, ended: run };
      await changeForks($, (forks) => ({ ...forks, [agentId]: ended }));
      void endFork($, agentId, ended);
      return completed;
    }
    const session = await sessionOf($);
    follow($, session);
    void endForks($);
    // Only a turn the model answered: an interrupted one has no reply to read.
    // Leaf, not the band, says whether the session holds a page: the band may not
    // yet list one the turn's last command claimed, and `--if-claimed` answers a
    // session holding none without starting uv.
    if (e.reason === "answer") void turnEnded($, session);
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
