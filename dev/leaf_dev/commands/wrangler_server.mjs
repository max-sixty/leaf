/** Own one local Worker and publish its actual listening port to the verifier. */
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { randomBytes } from "node:crypto";
import { once } from "node:events";

const [root, config, state] = process.argv.slice(2);
const require = createRequire(resolve(root, "package.json"));
const { unstable_startWorker } = require("wrangler");
const server = await unstable_startWorker({
  config,
  entrypoint: resolve(root, "worker/src/index.ts"),
  dev: {
    remote: false,
    server: { hostname: "127.0.0.1", port: 0 },
    inspector: { port: 0 },
    persist: state,
    // Verification serves a frozen release; watching its assets can exhaust
    // macOS file descriptors before workerd starts.
    watch: false,
    enableContainers: true,
    containerBuildId: randomBytes(4).toString("hex"),
  },
});
try {
  const url = await server.url;
  console.log(JSON.stringify({ event: "local_worker_ready", port: Number(url.port) }));
  await Promise.race([
    once(server.raw, "teardown"),
    once(process, "SIGTERM"),
    once(process, "SIGINT"),
  ]);
} finally {
  await server.dispose();
}
