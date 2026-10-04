// Stands in for Pi around Leaf's extension (`hooks/pi.ts`): the handful of
// ExtensionAPI calls it makes, driven one Pi event at a time from stdin.
//
// Each stdin line is `{"emit": <event>, "idle": <bool>}`: the driver calls that
// event's handlers with a context reporting `idle` and prints
// `{"event", "result"}` once they resolve. Every message the extension sends
// prints as `{"sent", "options"}`. The first line printed is `{"pid"}`, the
// process the extension states as Pi's.
import * as readline from "node:readline";
import leaf from "../hooks/pi.ts";

const session = process.argv[2];
const handlers = new Map();
let idle = true;
const print = (line) => process.stdout.write(`${JSON.stringify(line)}\n`);
const ctx = {
	hasUI: true,
	isIdle: () => idle,
	sessionManager: { getSessionId: () => session },
};

leaf({
	on: (event, handler) => handlers.set(event, [...(handlers.get(event) ?? []), handler]),
	sendMessage: (message, options) => print({ sent: message, options }),
});
print({ pid: process.pid });

for await (const line of readline.createInterface({ input: process.stdin })) {
	const { emit, idle: now = idle } = JSON.parse(line);
	idle = now;
	let result;
	for (const handler of handlers.get(emit) ?? []) {
		result = (await handler({ type: emit }, ctx)) ?? result;
	}
	print({ event: emit, result: result ?? null });
}
