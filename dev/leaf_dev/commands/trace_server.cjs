// Playwright owns every viewer route and its redirect. Call only its server
// primitives: serving evidence must never invoke a desktop or browser launcher.
const path = require("node:path");
const [driver, trace, host, port] = process.argv.slice(2);
const { startTraceViewerServer, installRootRedirect } = require(
  path.join(driver, "lib/coreBundle.js"),
).server;

async function serve() {
  const server = await startTraceViewerServer({
    host,
    port: Number(port),
    allowedFileRoots: () => [path.dirname(trace)],
  });
  await installRootRedirect(server, `file?path=${encodeURIComponent(trace)}`, {});
  console.log(server.urlPrefix("human-readable"));
}

serve().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
