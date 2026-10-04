/**
 * Leaf's carrier in Pi: the extension does for a Pi session what `hooks.json`
 * and `scripts/loop-guard.py` do for a Claude Code one (`PiHarness` in
 * `skills/leaf/scripts/leaf/host.py`).
 *
 * It calls `bin/leaf hook` with Claude Code's hook payload at the same points
 * of a run and puts what the hook returns in the run's context:
 *
 * - a user's prompt (`before_agent_start`) is the prompt hook;
 * - a run about to settle (`agent_before_settle`) is the Stop hook, whose
 *   context keeps the run going (`continue`);
 * - a run that settles without that, as an Escape leaves it, is the Interrupt
 *   hook, which closes the turn;
 * - a session that ends, or that `/new`, `/resume` or `/fork` replaces, is
 *   SessionEnd.
 *
 * As each run settles it starts the watch (`bin/leaf hook --watch`), which
 * prints a line and exits once one of the session's pages has input. It then
 * calls the prompt hook and sends what it returns: starting a run when Pi is
 * idle, which runs no prompt events of its own, or steering the running one.
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
// `hooks.json`'s timeout for the prompt and Stop hooks.
const HOOK_TIMEOUT_MS = 20_000;
const CUSTOM_TYPE = "leaf";

type Payload = { hook_event_name: string; session_id: string; stop_hook_active?: boolean };

/** Run the launcher with `payload` on stdin, and resolve its stdout, or "" on
 * any failure. `PI_SESSION_ID` is set for it as Pi sets it for the shell tool,
 * since the extension's own environment has none. */
function run(args: string[], payload: Payload, timeout?: number): { child: ChildProcess; done: Promise<string> } {
	const child = spawn(LEAF, args, {
		env: { ...process.env, PI_SESSION_ID: payload.session_id },
		stdio: ["pipe", "pipe", "ignore"],
		timeout,
	});
	const done = new Promise<string>((resolve) => {
		let out = "";
		child.stdout?.on("data", (chunk) => (out += chunk));
		child.on("error", () => resolve(""));
		child.on("close", (code) => resolve(code === 0 ? out : ""));
	});
	child.stdin?.end(JSON.stringify(payload));
	return { child, done };
}

/** The context a hook's output puts in the turn (`Harness.hook_context`). */
async function hook(payload: Payload): Promise<string | undefined> {
	const out = (await run(["hook"], payload, HOOK_TIMEOUT_MS).done).trim();
	if (!out) return undefined;
	try {
		return JSON.parse(out).hookSpecificOutput?.additionalContext || undefined;
	} catch {
		return undefined;
	}
}

export default function leaf(pi: ExtensionAPI) {
	let session = "";
	let watch: ChildProcess | undefined;
	// Whether the Stop hook has already kept this turn going (`stop_hook_active`).
	let stopActive = false;
	// Whether the run settling now passed through `agent_before_settle`.
	let stopped = false;

	const message = (content: string) => ({ customType: CUSTOM_TYPE, content, display: true });

	function stopWatch() {
		watch?.kill("SIGTERM");
		watch = undefined;
	}

	function startWatch(ctx: ExtensionContext) {
		if (watch || !ctx.hasUI) return;
		const started = run(["hook", "--watch"], { hook_event_name: "Stop", session_id: session });
		const child = started.child;
		watch = child;
		void started.done.then(async (woke) => {
			if (watch !== child) return;
			watch = undefined;
			if (!woke.trim()) return;
			const context = await hook({ hook_event_name: "UserPromptSubmit", session_id: session });
			const content = context ?? `Leaf: ${woke.trim()}`;
			if (ctx.isIdle()) {
				stopActive = false;
				pi.sendMessage(message(content), { triggerTurn: true });
			} else {
				pi.sendMessage(message(content), { deliverAs: "steer" });
			}
		});
	}

	async function endSession() {
		stopWatch();
		if (session) await run(["session-end"], { hook_event_name: "SessionEnd", session_id: session }, 3_000).done;
	}

	pi.on("session_start", (_event, ctx) => {
		session = ctx.sessionManager.getSessionId();
		process.env.LEAF = LEAF;
		process.env.LEAF_PI_PID = String(process.pid);
		const bin = path.dirname(LEAF);
		if (!(process.env.PATH ?? "").split(path.delimiter).includes(bin)) {
			process.env.PATH = [bin, process.env.PATH].filter(Boolean).join(path.delimiter);
		}
	});

	pi.on("session_shutdown", endSession);

	pi.on("before_agent_start", async () => {
		stopActive = false;
		const context = await hook({ hook_event_name: "UserPromptSubmit", session_id: session });
		return context ? { message: message(context) } : undefined;
	});

	pi.on("agent_start", () => {
		stopped = false;
	});

	pi.on("agent_before_settle", async () => {
		stopped = true;
		const context = await hook({ hook_event_name: "Stop", session_id: session, stop_hook_active: stopActive });
		if (!context) return undefined;
		stopActive = true;
		return {
			entries: [{ type: "custom_message" as const, ...message(context) }],
			continue: true,
		};
	});

	pi.on("agent_settled", async (_event, ctx) => {
		if (!stopped) await hook({ hook_event_name: "Interrupt", session_id: session });
		startWatch(ctx);
	});
}
