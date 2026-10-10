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
 *   watch with the Interrupt payload, which closes the turn. Receipt distinguishes
 *   input that entered that turn from input held outside its context;
 * - a watch that wakes an idle session submits its line as a prompt, whose
 *   prompt hook hands the input over; one that wakes during a turn calls the
 *   prompt hook itself and appends what it returns to that turn, which reads it
 *   at its next step. The appended row joins the session's transcript at once,
 *   and stays there through an Escape (measured at 2.1.291), so the hook's
 *   confirmation holds: the input is in the session's context. Claude Code
 *   shows neither that row nor the prompt hook's context in the terminal. A
 *   wake while a turn's Stop hooks run waits for them, since Leaf's hands over
 *   what is pending and decides whether the turn goes on;
 * - a delivery Leaf's Stop hook hands over as a turn ends, which Claude Code
 *   would print in full, goes into the session the same way, and the turn goes
 *   on with one line in its place.
 *
 * Once it has Claude Code's parent process, each Stop payload carries `leaf_watch:
 * "module"`, which stands the background registration beneath it down
 * (`hooks/scripts/loop-guard.py`). A Claude Code that does not load the module, or
 * a module without that parent process, passes the payload unmarked, so that
 * registration goes on watching. A native spawn handle does not prove startup:
 * a watch that fails later reports its error and releases the owner's slot.
 * The prompt, Stop, SessionStart and
 * SessionEnd registrations do the same work under either watch and stay in
 * `hooks.json`.
 *
 * TODO: once Claude Code loads modules without an opt-in, make this module the
 * only watcher and transport and drop the background Stop registration, `loop-guard.py`, and
 * the interrupt half of the nudge.
 *
 * A module's processes inherit Claude Code's own environment, which names no
 * session of its own, so every call states the session and Claude Code's process
 * as a hook's environment does. That process is the parent of every process the
 * module starts (measured at Claude Code 2.1.291). Failed hooks and watches report
 * their diagnostics through Claude Code's UI log. Replacing or closing a watch
 * cancels it quietly, after waiting for its process to exit.
 */

import type { EngineInterface, Register } from 'claude-code'
import { WatchOwner } from './watch.ts'

// `hooks.json`'s timeout for the prompt hook, inside which it confirms what it
// hands over (`CONFIRM_WITHIN` in `hook_transport.py`).
const HOOK_TIMEOUT_MS = 20_000
// The line an inline delivery opens with (`INLINE_DELIVERY` in `hook_transport.py`),
// and the line the turn goes on with once the module has appended one.
const INLINE_DELIVERY = 'Leaf has new input for your turn.'
const DELIVERED = "Leaf added the page's new input to your context above; answer it before you end the turn."

type Payload = { hook_event_name: string; session_id: string; ended_at?: number }

// Claude Code's process, read as the session starts.
let claudePid = ''
let watch = new WatchOwner()
// Whether a main-loop turn is going, from its start until its Stop hooks let it end.
let running = false
// The Stop hooks of a turn now ending, while they run.
let stopping: Promise<unknown> | undefined

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
    if (ran.exitCode !== 0) {
      $.ui.log(`Leaf: ${payload.hook_event_name} hook exited with code ${ran.exitCode}${ran.stderr.trim() ? `: ${ran.stderr.trim()}` : ''}`)
      return undefined
    }
    if (!ran.stdout.trim()) return undefined
    return JSON.parse(ran.stdout).hookSpecificOutput?.additionalContext || undefined
  } catch (error) {
    $.ui.log(`Leaf: ${payload.hook_event_name} hook failed: ${error}`)
    return undefined
  }
}

/** The watch owner serializes endings; the adapter supplies Claude Code's process
 * and wake operations. Without its parent process, the registration keeps watch. */
async function ensureWatch($: EngineInterface, session: string, interrupted: boolean) {
  const ended = Date.now() / 1000
  if (!claudePid) return
  const owner = watch
  await owner.ensure(interrupted, () => {
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
    let cancelled = false
    const done = (async () => {
      let out = ''
      let stderr = ''
      let readError: unknown
      try {
        for await (const chunk of stream) {
          if (chunk.stream === 'stdout') out += chunk.text
          else if (chunk.stream === 'stderr') stderr += chunk.text
        }
      } catch (error) {
        // Cancellation can abort output before the process releases its lease.
        readError = error
      }
      try {
        const result = await stream.result
        if (cancelled) return ''
        if (result.code !== 0 || readError) {
          $.ui.log(`Leaf: watch failed (${readError ?? `exit code ${result.code}`})${stderr.trim() ? `: ${stderr.trim()}` : ''}`)
          return ''
        }
        return out.trim()
      } catch (error) {
        if (!cancelled) $.ui.log(`Leaf: watch failed: ${error}${stderr.trim() ? `: ${stderr.trim()}` : ''}`)
        return ''
      }
    })()
    return {
      stop: () => {
        cancelled = true
        return stream.return(undefined as never)
      },
      done,
    }
  }, (output, live) => wake($, session, owner, output, live)).catch(error => {
    $.ui.log(`Leaf: watch could not start: ${error}`)
  })
}

/** Whether the turn goes on, once any Stop hooks now running have returned. They
 * hand over the input pending as they run, and decide whether the turn goes on,
 * so a wake waits for them rather than carrying that input beside them. */
async function turnGoesOn() {
  while (stopping) await stopping.catch(() => undefined)
  return running
}

function append($: EngineInterface, text: string) {
  return $.session.append({ message: { type: 'user', content: [{ type: 'text', text }] } })
}

async function wake($: EngineInterface, session: string, owner: WatchOwner, woke: string, live: () => boolean) {
  if (!woke) return
  try {
    // Claude Code refuses a plugin's prompt that starts with `/`, as the watch's
    // line, a page's path, does.
    const prompt = `Leaf: ${woke}`
    const ongoing = await turnGoesOn()
    if (!live()) return
    if (ongoing) {
      const context = await hook($, { hook_event_name: 'UserPromptSubmit', session_id: session })
      if (!owner.open) return
      // The hook has confirmed what it hands over, so that goes into the session
      // even where the turn ended while the hook ran: an idle session reads an
      // appended row at its next turn, which the prompt below starts.
      if (context) await append($, context)
      const ongoing = await turnGoesOn()
      // Confirmed input still needs an idle turn even if another watch started;
      // a session that ended meanwhile owns neither an append nor a new prompt.
      if (!owner.open || (!context && !live())) return
      if (ongoing) {
        if (!context) await append($, prompt)
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
    const ending = (async () => {
      // Without Claude Code's process the watch cannot run, so the registration
      // beneath keeps it.
      const result = await next(claudePid ? Object.assign({}, e, { leaf_watch: 'module' }) : e)
      const contexts = result.additionalContext ?? []
      // Claude Code prints a Stop hook's context in the terminal, so a delivery
      // Leaf's Stop hook hands over goes into the session as an appended row,
      // which it does not show, and the turn goes on with one line.
      const shown: string[] = []
      for (const context of contexts) {
        if (!context.startsWith(INLINE_DELIVERY)) {
          shown.push(context)
          continue
        }
        try {
          await append($, context)
          shown.push(DELIVERED)
        } catch (error) {
          $.ui.log(`Leaf: the Stop hook's delivery was not appended: ${error}`, { to: 'debug' })
          shown.push(context)
        }
      }
      // A Stop hook's context keeps the turn going.
      running = shown.length > 0 || result.block !== undefined
      return contexts.length ? Object.assign({}, result, { additionalContext: shown }) : result
    })()
    stopping = ending
    const settled = () => {
      if (stopping === ending) stopping = undefined
    }
    ending.then(settled, settled)
    return ending
  })

  on('turn.complete', async ($, e, next) => {
    const completed = await next(e)
    if (e.agentId !== undefined) return completed
    running = false
    void ensureWatch($, await $.session.id(), e.isAborted)
    return completed
  })

  on('session.end', async ($, e, next) => {
    const owner = watch
    await owner.close()
    const ended = await next(e)
    // /clear and resume keep the module loaded without another session.start.
    if (watch === owner) watch = new WatchOwner()
    return ended
  })
}
