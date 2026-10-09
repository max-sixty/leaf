/** Own one local Worker and publish its actual listening port to the verifier. */
import { createRequire } from "node:module";
import { resolve } from "node:path";

const [root, config, state] = process.argv.slice(2);
const require = createRequire(resolve(root, "worker/package.json"));
const { unstable_dev } = require("wrangler");
const server = await unstable_dev(resolve(root, "worker/src/index.ts"), {
  config,
  local: true,
  port: 0,
  inspectorPort: 0,
  persistTo: state,
  experimental: {
    enableContainers: true,
    disableDevRegistry: true,
    disableExperimentalWarning: true,
  },
});
console.log(JSON.stringify({ event: "local_worker_ready", port: server.port }));
let stopping = false;
async function stop() {
  if (stopping) return;
  stopping = true;
  await server.stop();
}
process.on("SIGTERM", stop);
process.on("SIGINT", stop);
await server.waitUntilExit();
