// Playwright owns every viewer route and its redirect. Call only its server
// primitives, as its own `show-trace` does short of opening the URL: serving
// evidence must never invoke a desktop or browser launcher.
const path = require("node:path");
const [driver, trace, host, port] = process.argv.slice(2);
const { startTraceViewerServer, traceViewerPath } = require(
  path.join(driver, "lib/coreBundle.js"),
).server;

async function serve() {
  const server = await startTraceViewerServer({
    host,
    port: Number(port),
    allowedFileRoots: () => [path.dirname(trace)],
  });
  server.installRootRedirect(
    traceViewerPath(`file?path=${encodeURIComponent(trace)}`, {}),
  );
  console.log(server.rootUrl("human-readable"));
}

serve().catch((error) => {
  console.error(error.message);
  process.exit(1);
});
