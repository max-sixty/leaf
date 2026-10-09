// The native verifier waits for Leaf's completed watch notification before
// cancelling the tool that holds its input. Observing close after its listeners
// and promise handlers have run distinguishes handoff from lease release.
// This writes only an RPC frame to the verifier, never a session message.
import childProcess from "node:child_process";
import { syncBuiltinESMExports } from "node:module";

// Capture the protocol stream before Pi redirects extension output. Sharing
// its Writable keeps this frame ordered behind any backpressured RPC frame.
const writeProtocol = process.stdout.write.bind(process.stdout);
const spawn = childProcess.spawn;
childProcess.spawn = function (file, args, options) {
  const child = spawn.call(this, file, args, options);
  if (args?.[0] === "hook" && args.includes("pi") && args.includes("--watch")) {
    child.once("close", (code) => {
      setImmediate(() => {
        writeProtocol(`${JSON.stringify({ type: "leaf_watch_closed", code })}\n`);
      });
    });
  }
  return child;
};
syncBuiltinESMExports();
