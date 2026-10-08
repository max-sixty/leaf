/**
 * Leaf's watcher and hook transport in Pi: the extension does for a Pi session what `hooks.json`
 * and `scripts/loop-guard.py` do for a Claude Code one (`PiHarness` in
 * `skills/leaf/scripts/leaf/harness.py`).
 *
 * Highly experimental: a trial of Leaf on Pi. The site and most references
 * still name only Claude Code and Codex.
 *
 * It calls `bin/leaf hook --harness pi` with Leaf's hook payload at the
 * same points of a run and puts what the hook returns in the run's context:
 *
 * - an accepted run (`agent_start`) opens the turn without taking input;
 * - an incoming message finalization (`message_end`) takes input before the
 *   first request; a live turn boundary (`turn_end`) takes later input;
 * - a run about to settle (`agent_before_settle`) is the Stop hook, whose
 *   context keeps the run going (`continue`);
 * - a session that ends, or that `/new`, `/resume` or `/fork` replaces, is
 *   SessionEnd. `/reload` keeps the session, so it only stops the watch, which
 *   the reloaded extension starts again.
 *
 * As a session starts and as each run settles, it starts the watch (the same
 * call with `--watch`), which prints a line and exits once one of the session's
 * pages has input. When no run is going, it sends a notification to start one.
 * The notification confirms no input: Pi may queue or clear it if a user run
 * starts meanwhile. The accepted incoming message takes the input before the
 * first model request. Input arriving during a live run enters at its next turn's end
 * (`turn_end`), where the extension calls the prompt hook and returns entries:
 * the hook confirms what it hands over, so it hands it over only once Pi takes
 * it into the session, not to a steer Pi queues behind a running tool, which
 * Escape clears. A run that settles without going on from
 * there, as an Escape leaves it, starts the watch with the Interrupt payload:
 * it closes the turn, and wakes for input that never entered the stopped turn,
 * including a held notification Escape cleared before `turn_end`. Input the run
 * received has a completed receipt cursor, so Escape is not undone by that input.
 *
 * The session's shell-tool commands find the launcher as `$LEAF` and on PATH,
 * and Pi's process as LEAF_PI_PID, which is the session's lifetime. Hook
 * failures are silent, as `hooks.json` makes them: Leaf's state is its own to
 * report, and a Pi session is never held up by it beyond the hook's timeout.
 */

import { spawn, type ChildProcess } from "node:child_process";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI, ExtensionContext } from "@earendil-works/pi-coding-agent";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const LEAF = path.join(ROOT, "bin", "leaf");
// `hooks.json`'s timeouts for the prompt and Stop hooks, and for SessionEnd. The
// prompt and Stop hooks confirm what they hand over only well inside the first
// (`CONFIRM_WITHIN` in `hook_transport.py`).
const HOOK_TIMEOUT_MS = 20_000;
const SESSION_END_TIMEOUT_MS = 3_000;
const CUSTOM_TYPE = "leaf";

type Payload = { hook_event_name: string; session_id: string; stop_hook_active?: boolean; ended_at?: number };

/** Run the launcher with `payload` on stdin, and resolve its stdout, or "" on
 * any failure. */
function run(args: string[], payload: Payload, timeout?: number): { child: ChildProcess; done: Promise<string> } {
	const child = spawn(LEAF, args, {
		stdio: ["pipe", "pipe", "ignore"],
		timeout,
	});
	const done = new Promise<string>((resolve) => {
		let out = "";
		child.stdout?.on("data", (chunk) => (out += chunk));
		child.on("error", () => resolve(""));
		child.on("close", (code) => resolve(code === 0 ? out : ""));
	});
	child.stdin?.on("error", () => {});
	child.stdin?.end(JSON.stringify(payload));
	return { child, done };
}

/** The context a hook's output puts in the turn (`Harness.hook_context`). */
async function hook(payload: Payload): Promise<string | undefined> {
	const out = (await run(["hook", "--harness", "pi"], payload, HOOK_TIMEOUT_MS).done).trim();
	if (!out) return undefined;
	try {
		return JSON.parse(out).hookSpecificOutput?.additionalContext || undefined;
	} catch {
		return undefined;
	}
}

type Watch = { child: ChildProcess; done: Promise<string>; interrupted: boolean };

export default function leaf(pi: ExtensionAPI) {
	let session = "";
	let hasUI = false;
	// Set as Pi shuts this instance down: Pi refuses a stale instance's calls,
	// so a wake still in flight then sends nothing.
	let disposed = false;
	let watch: Watch | undefined;
	// Whether a run is going, from `agent_start` until it settles.
	let running = false;
	// Whether the Stop hook has already kept this turn going (`stop_hook_active`).
	let stopActive = false;
	// Whether the run settling now went on from `agent_before_settle`, which
	// asked Pi to continue it; an abort can settle it there instead.
	let settledByStop = false;
	// Whether the watch woke during the run, so its next turn's end takes the input.
	let handOff = false;

	const message = (content: string) => ({ customType: CUSTOM_TYPE, content, display: true });

	async function stopWatch() {
		const stopping = watch;
		watch = undefined;
		stopping?.child.kill("SIGTERM");
		await stopping?.done;
	}

	/** Keep one watch running for this ending. A watch at a Stop ending goes on
	 * past another Stop ending; any other ending replaces it, and an interrupted
	 * one always starts afresh, since its watch closes the turn and looks at the
	 * logs anew. A watch is replaced only once the one before it has exited,
	 * since the session's wait lease admits one, and one from before would read
	 * the closed turn as the Stop hook's ending. */
	async function ensureWatch(interrupted: boolean) {
		// The watch closes the turn after this returns, so it states when it ended,
		// in POSIX seconds.
		const ended = Date.now() / 1000;
		if (!hasUI || disposed || (watch && !watch.interrupted && !interrupted)) return;
		await stopWatch();
		// A shutdown, or another start, may have come while the old one exited.
		if (disposed || watch) return;
		const started = run(["hook", "--harness", "pi", "--watch"], {
			hook_event_name: interrupted ? "Interrupt" : "Stop",
			session_id: session,
			ended_at: ended,
		});
		const current = { ...started, interrupted };
		watch = current;
		void current.done.then((woke) => wake(current, woke));
	}

	function wake(ended: Watch, woke: string) {
		if (watch !== ended || disposed) return;
		watch = undefined;
		if (!woke.trim()) return;
		// A notification can be queued or cleared by Pi. Receipt belongs only to
		// accepted message finalization or a live turn boundary Pi persists.
		handOff = true;
		if (running) return;
		stopActive = false;
		pi.sendMessage(message(`Leaf: ${woke.trim()}`), { triggerTurn: true, deliverAs: "steer" });
	}

	pi.on("session_start", (_event, ctx) => {
		session = ctx.sessionManager.getSessionId();
		hasUI = ctx.hasUI;
		process.env.LEAF = LEAF;
		process.env.LEAF_PI_PID = String(process.pid);
		const bin = path.dirname(LEAF);
		if (!(process.env.PATH ?? "").split(path.delimiter).includes(bin)) {
			process.env.PATH = [bin, process.env.PATH].filter(Boolean).join(path.delimiter);
		}
		void ensureWatch(false);
	});

	pi.on("session_shutdown", async (event) => {
		disposed = true;
		await stopWatch();
		if (event.reason !== "reload") {
			await run(["session-end"], { hook_event_name: "SessionEnd", session_id: session }, SESSION_END_TIMEOUT_MS)
				.done;
		}
	});

	pi.on("agent_start", async () => {
		const first = !running;
		running = true;
		settledByStop = false;
		// Internal continuations keep this run's Stop policy. Only an accepted
		// new run opens Leaf's turn; prompt preparation accepts no delivery.
		if (!first) return;
		stopActive = false;
		handOff = true;
		await hook({ hook_event_name: "TurnStart", session_id: session });
	});

	async function takeInput(ctx: ExtensionContext): Promise<string | undefined> {
		// Cancelled boundaries cannot receive held input. A receipt started while
		// live is committed by Pi even if cancellation arrives during the hook.
		if (!handOff || ctx.signal?.aborted) return undefined;
		handOff = false;
		return hook({ hook_event_name: "UserPromptSubmit", session_id: session });
	}

	pi.on("message_end", async (event, ctx) => {
		const incoming = event.message;
		if (incoming.role !== "user" && !(incoming.role === "custom" && incoming.customType === CUSTOM_TYPE)) {
			return undefined;
		}
		const context = await takeInput(ctx);
		if (!context) return undefined;
		// Pi finalizes this accepted message into both its session and model
		// context before the first request. Preserve the original user's input.
		const content = typeof incoming.content === "string" ? [{ type: "text" as const, text: incoming.content }] : incoming.content;
		return { message: { ...incoming, content: [...content, { type: "text" as const, text: context }] } };
	});

	pi.on("turn_end", async (_event, ctx) => {
		const context = await takeInput(ctx);
		return context
			? { entries: [{ type: "custom_message" as const, ...message(context) }], continue: true }
			: undefined;
	});

	pi.on("agent_before_settle", async () => {
		// The Stop hook hands over whatever is pending.
		handOff = false;
		const context = await hook({ hook_event_name: "Stop", session_id: session, stop_hook_active: stopActive });
		if (!context) {
			settledByStop = true;
			return undefined;
		}
		stopActive = true;
		return {
			entries: [{ type: "custom_message" as const, ...message(context) }],
			continue: true,
		};
	});

	pi.on("agent_settled", async () => {
		const interrupted = running && !settledByStop;
		running = false;
		// The queued handoff is gone. The new watch finds input this run never
		// received; its receipt cursor keeps handed input for the next prompt.
		handOff = false;
		await ensureWatch(interrupted);
	});
}
