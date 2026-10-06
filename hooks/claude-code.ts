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
 *   hook --harness claude-code --watch`), which prints a line and exits once one
 *   of the session's pages has input;
 * - a turn the user interrupts ends with no Stop hook, so the module starts the
 *   watch with the Interrupt payload, which closes the turn and wakes only for
 *   input that arrives after it;
 * - a watch that wakes an idle session submits its line as a prompt, whose
 *   prompt hook hands the input over; one that wakes during a turn calls the
 *   prompt hook itself and appends what it returns to that turn, which reads it
 *   at its next step.
 *
 * Once it can start the watch, each Stop payload it passes on carries `leaf_watch:
 * "module"`, which stands the background registration beneath it down
 * (`hooks/scripts/loop-guard.py`). A Claude Code that does not load the module, or
 * a module that cannot start the watch, passes the payload unmarked, so that
 * registration goes on watching. The prompt, Stop, SessionStart and
 * SessionEnd registrations do the same work under either watch and stay in
 * `hooks.json`.
 *
 * A module's processes inherit Claude Code's own environment, which names no
 * session of its own, so every call states the session and Claude Code's process
 * as a hook's environment does. That process is the parent of every process the
 * module starts (measured at Claude Code 2.1.291). Failures are silent, as
 * `hooks.json` makes them, but for a wake Claude Code refuses, which goes to its
 * debug log.
 */

import type { EngineInterface, Register } from 'claude-code'

// `hooks.json`'s timeout for the prompt hook, inside which it confirms what it
// hands over (`CONFIRM_WITHIN` in `hook_carrier.py`).
const HOOK_TIMEOUT_MS = 20_000

type Payload = { hook_event_name: string; session_id: string; ended_at?: number }
type Watch = {
  stop: () => Promise<unknown>
  done: Promise<string>
  interrupted: boolean
}

// Claude Code's process, read as the session starts.
let claudePid = ''
let watch: Watch | undefined
// Whether a main-loop turn is going, from its start until its Stop hooks run.
let running = false

function environment(session: string) {
  return { CLAUDE_CODE_SESSION_ID: session, CLAUDE_PID: claudePid }
}

function launcher($: EngineInterface) {
  return `${$.plugin.root}/bin/leaf`
}

/** The context a hook's output puts in the turn (`Harness.hook_context`). */
async function hook($: EngineInterface, payload: Payload): Promise<string | undefined> {
  try {
    const ran = await $.process.run([launcher($), 'hook', '--harness', 'claude-code'], {
      env: environment(payload.session_id),
      stdin: JSON.stringify(payload),
      timeoutMs: HOOK_TIMEOUT_MS,
    })
    if (ran.exitCode !== 0 || !ran.stdout.trim()) return undefined
    return JSON.parse(ran.stdout).hookSpecificOutput?.additionalContext || undefined
  } catch {
    return undefined
  }
}

async function stopWatch() {
  const stopping = watch
  watch = undefined
  await stopping?.stop()
  await stopping?.done
}

/** Keep one watch running for this ending. A watch at a Stop ending goes on past
 * another Stop ending; any other ending replaces it, and an interrupted one
 * always starts afresh, since its watch closes the turn and looks at the logs
 * anew. A watch is replaced only once the one before it has exited, since the
 * session's wait lease admits one, and one from before would read the closed
 * turn as the Stop hook's ending. Without Claude Code's process the module keeps
 * no watch, and leaves the turn's ending to the registrations beneath it. */
async function ensureWatch($: EngineInterface, session: string, interrupted: boolean) {
  // The watch closes the turn after this returns, so it states when it ended,
  // in POSIX seconds.
  const ended = Date.now() / 1000
  if (!claudePid || (watch && !watch.interrupted && !interrupted)) return
  await stopWatch()
  // Another ending may have started one while the old one exited.
  if (watch) return
  const payload: Payload = {
    hook_event_name: interrupted ? 'Interrupt' : 'Stop',
    session_id: session,
    ended_at: ended,
  }
  const stream = $.process.spawn({
    argv: [launcher($), 'hook', '--harness', 'claude-code', '--watch'],
    env: environment(session),
    input: JSON.stringify(payload),
  })
  const done = (async () => {
    let out = ''
    try {
      for await (const chunk of stream) if (chunk.stream === 'stdout') out += chunk.text
      return (await stream.result).code === 0 ? out.trim() : ''
    } catch {
      return ''
    }
  })()
  const current = { stop: () => stream.return(undefined as never), done, interrupted }
  watch = current
  void done.then(woke => wake($, session, current, woke))
}

async function wake($: EngineInterface, session: string, ended: Watch, woke: string) {
  if (watch !== ended) return
  watch = undefined
  if (!woke) return
  try {
    // Claude Code refuses a plugin's prompt that starts with `/`, as the watch's
    // line, a page's path, does.
    const prompt = `Leaf: ${woke}`
    if (running) {
      const context = await hook($, { hook_event_name: 'UserPromptSubmit', session_id: session })
      // The turn may have ended while the hook ran, and an idle session reads an
      // appended row only at its next turn. The prompt that starts one has its
      // prompt hook carry the handed input back as a move still owed its answer.
      if (running) {
        await $.session.append({
          message: { type: 'user', content: [{ type: 'text', text: context ?? prompt }] },
        })
        return
      }
    }
    await $.prompt.submit({ text: prompt })
  } catch (error) {
    // A wake Claude Code refuses leaves the input to the next turn's prompt hook.
    $.ui.log(`Leaf: the watch's wake was refused: ${error}`, { to: 'debug' })
  }
}

export const register: Register = (on, options) => {
  if (options.hooks_module !== true) return

  on('session.start', async ($, e, next) => {
    const started = await next(e)
    const parent = await $.process.run(['/bin/sh', '-c', 'echo $PPID'])
    claudePid = parent.stdout.trim()
    void ensureWatch($, await $.session.id(), false)
    return started
  })

  on('turn.start', ($, e, next) => {
    running = true
    return next(e)
  })

  on('classic.Stop', ($, e, next) => {
    running = false
    // Without Claude Code's process the watch cannot run, so the registration
    // beneath keeps it.
    return next(claudePid ? Object.assign({}, e, { leaf_watch: 'module' }) : e)
  })

  on('turn.complete', async ($, e, next) => {
    const completed = await next(e)
    if (e.agentId !== undefined) return completed
    running = false
    void ensureWatch($, await $.session.id(), e.isAborted)
    return completed
  })

  on('session.end', async ($, e, next) => {
    await stopWatch()
    return next(e)
  })
}
