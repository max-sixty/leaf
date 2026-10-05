/**
 * Leaf's carrier in Pi: the extension does for a Pi session what `hooks.json`
 * and `scripts/loop-guard.py` do for a Claude Code one (`PiHarness` in
 * `skills/leaf/scripts/leaf/harness.py`).
 *
 * Highly experimental: a trial of Leaf on Pi. The site and most references
 * still name only Claude Code and Codex.
 *
 * It calls `bin/leaf hook --harness pi` with Claude Code's hook payload at the
 * same points of a run and puts what the hook returns in the run's context:
 *
 * - a user's prompt (`before_agent_start`) is the prompt hook;
 * - a run about to settle (`agent_before_settle`) is the Stop hook, whose
 *   context keeps the run going (`continue`);
 * - a run that settles without going on from there, as an Escape leaves it, is
 *   the Interrupt hook, which closes the turn;
 * - a session that ends, or that `/new`, `/resume` or `/fork` replaces, is
 *   SessionEnd. `/reload` keeps the session, so it only stops the watch, which
 *   the reloaded extension starts again.
 *
 * As a session starts and as each run settles, it starts the watch (the same
 * call with `--watch`), which prints a line and exits once one of the session's
 * pages has input. It then calls the prompt hook and sends what it returns,
 * which starts a run when none is going (and runs no prompt events of its
 * own), or steers the running one. A watch started as an interrupted run
 * settles wakes only for input that arrives after it, so an Escape is not
 * undone by the input the run was already handed.
 *
 * The session's shell-tool commands find the launcher as `$LEAF` and on PATH,
 * and Pi's process as LEAF_PI_PID, which is the session's lifetime. Hook
 * failures are silent, as `hooks.json` makes them: Leaf's state is its own to
 * report, and a Pi session is never held up by it beyond the hook's timeout.
 */

import { spawn, type ChildProcess } from "node:child_process";
import * as path from "node:path";
import { fileURLToPath } from "node:url";
import type { ExtensionAPI } from "@earendil-works/pi-coding-agent";

const ROOT = fileURLToPath(new URL("..", import.meta.url));
const LEAF = path.join(ROOT, "bin", "leaf");
// `hooks.json`'s timeouts for the prompt and Stop hooks, and for SessionEnd.
const HOOK_TIMEOUT_MS = 20_000;
const SESSION_END_TIMEOUT_MS = 3_000;
const CUSTOM_TYPE = "leaf";

type Payload = { hook_event_name: string; session_id: string; stop_hook_active?: boolean };

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

	const message = (content: string) => ({ customType: CUSTOM_TYPE, content, display: true });

	async function stopWatch() {
		const stopping = watch;
		watch = undefined;
		stopping?.child.kill("SIGTERM");
		await stopping?.done;
	}

	/** Keep one watch running, in the mode this ending asks for. A watch is
	 * replaced only once the one before it has exited, since the session's wait
	 * lease admits one. */
	async function ensureWatch(interrupted: boolean) {
		if (!hasUI || disposed || (watch && watch.interrupted === interrupted)) return;
		await stopWatch();
		// A shutdown, or another start, may have come while the old one exited.
		if (disposed || watch) return;
		const started = run(["hook", "--harness", "pi", "--watch"], {
			hook_event_name: interrupted ? "Interrupt" : "Stop",
			session_id: session,
		});
		const current = { ...started, interrupted };
		watch = current;
		void current.done.then((woke) => wake(current, woke));
	}

	async function wake(ended: Watch, woke: string) {
		if (watch !== ended || disposed) return;
		watch = undefined;
		if (!woke.trim()) return;
		const context = await hook({ hook_event_name: "UserPromptSubmit", session_id: session });
		if (disposed) return;
		if (!running) stopActive = false;
		// Pi starts a run when none is going and steers the running one.
		pi.sendMessage(message(context ?? `Leaf: ${woke.trim()}`), { triggerTurn: true, deliverAs: "steer" });
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

	pi.on("before_agent_start", async () => {
		stopActive = false;
		const context = await hook({ hook_event_name: "UserPromptSubmit", session_id: session });
		return context ? { message: message(context) } : undefined;
	});

	pi.on("agent_start", () => {
		running = true;
		settledByStop = false;
	});

	pi.on("agent_before_settle", async () => {
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
		if (interrupted) {
			// A watch from before would read the closed turn as the Stop hook's
			// ending, and hand the stopped run's input to a new one.
			await stopWatch();
			await hook({ hook_event_name: "Interrupt", session_id: session });
		}
		await ensureWatch(interrupted);
	});
}
