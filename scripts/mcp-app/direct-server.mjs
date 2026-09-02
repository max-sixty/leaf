// The official Node MCP SDK carries the protocol; Python still owns Leaf state.
import { createRequire } from "node:module";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { appendFile } from "node:fs/promises";
import path from "node:path";

const [page, bundle, modules, observations, port] = process.argv.slice(2);
const require = createRequire(path.join(modules, "../package.json"));
const { McpServer } = require("@modelcontextprotocol/sdk/server/mcp.js");
const { StdioServerTransport } = require("@modelcontextprotocol/sdk/server/stdio.js");
const { createMcpExpressApp } = require("@modelcontextprotocol/sdk/server/express.js");
const {
  StreamableHTTPServerTransport,
} = require("@modelcontextprotocol/sdk/server/streamableHttp.js");
const {
  registerAppResource,
  registerAppTool,
  RESOURCE_MIME_TYPE,
} = require("@modelcontextprotocol/ext-apps/server");
const { z } = require("zod");
const repo = path.resolve(new URL(import.meta.url).pathname, "../../..");
const worker = spawn(
  path.join(repo, ".venv/bin/python"),
  ["-u", path.join(repo, "scripts/mcp-app/direct.py"), page, bundle],
  { stdio: ["pipe", "pipe", "inherit"] },
);
const pending = new Map();
let nextId = 0;
createInterface({ input: worker.stdout }).on("line", (line) => {
  const answer = JSON.parse(line);
  const request = pending.get(answer.id);
  pending.delete(answer.id);
  if (answer.error) request.reject(new Error(answer.error));
  else request.resolve(answer.result);
});
worker.on("exit", () => {
  for (const request of pending.values())
    request.reject(new Error("Leaf worker exited"));
  pending.clear();
});
process.on("exit", () => worker.kill());
process.on("SIGTERM", () => process.exit(0));
process.on("SIGINT", () => process.exit(0));
const ask = (method, args = {}) =>
  new Promise((resolve, reject) => {
    const id = ++nextId;
    pending.set(id, { resolve, reject });
    worker.stdin.write(JSON.stringify({ id, method, args }) + "\n");
  });
const { html } = await ask("document");
const uri = "ui://leaf-direct-probe/page.html";
const result = (value) => ({
  content: [{ type: "text", text: "Leaf probe response" }],
  structuredContent: value,
});
const makeServer = () => {
  const server = new McpServer({ name: "leaf-direct-probe", version: "45" });
  const ui = {
    csp: { connectDomains: [], resourceDomains: [], frameDomains: [] },
    prefersBorder: false,
  };
  registerAppResource(
    server,
    "Leaf directly in ui://",
    uri,
    { _meta: { ui } },
    async () => ({
      contents: [{ uri, mimeType: RESOURCE_MIME_TYPE, text: html, _meta: { ui } }],
    }),
  );
  const tool = (
    name,
    description,
    inputSchema,
    readOnlyHint,
    callback,
    visibility = ["app"],
  ) =>
    registerAppTool(
      server,
      name,
      {
        description,
        inputSchema,
        annotations: { readOnlyHint, destructiveHint: false, openWorldHint: false },
        _meta: { ui: { resourceUri: uri, visibility } },
      },
      async (args) => result(await callback(args)),
    );
  const view = { view_revision: z.number().int().positive().nullable().optional() };
  tool(
    "leaf_direct_present",
    "Present the canonical Leaf runtime directly in the MCP resource, without a nested HTTP frame.",
    {},
    true,
    async () => ({
      page,
      resource: uri,
      bytes: Buffer.byteLength(html),
      rendering: "unverified until the app reports presented",
    }),
    ["model"],
  );
  tool(
    "leaf_probe_state",
    "Read this page's canonical browser projection.",
    view,
    true,
    (args) => ask("state", args),
  );
  tool("leaf_probe_reading", "Read the page change token.", {}, true, () =>
    ask("reading"),
  );
  tool(
    "leaf_probe_event",
    "Validate and append a reader gesture through Leaf's normal event door.",
    {
      ...view,
      event: z.record(z.string(), z.unknown()),
      generation: z.string(),
    },
    false,
    (args) => ask("event", args),
  );
  tool(
    "leaf_probe_report",
    "Record this experiment's rendering or message diagnostics outside the Leaf log.",
    {
      detail: z.record(z.string(), z.unknown()),
    },
    false,
    async ({ detail }) => {
      await appendFile(observations, JSON.stringify(detail) + "\n");
      return { recorded: true };
    },
  );
  return server;
};

if (!port) await makeServer().connect(new StdioServerTransport());
else {
  // The SDK checks Host for every route. Check browser Origin at the same edge;
  // server-side MCP clients omit it, while the reference host has one origin.
  const app = createMcpExpressApp();
  const origin = "http://localhost:8080";
  app.use((req, res, next) => {
    if (req.headers.origin !== undefined && req.headers.origin !== origin) {
      res.status(403).json({
        jsonrpc: "2.0",
        error: { code: -32000, message: "Invalid Origin" },
        id: null,
      });
      return;
    }
    res.setHeader("Access-Control-Allow-Origin", origin);
    res.setHeader(
      "Access-Control-Allow-Headers",
      "content-type,mcp-protocol-version,mcp-session-id",
    );
    res.setHeader("Access-Control-Allow-Methods", "GET,POST,OPTIONS,DELETE");
    res.setHeader("Access-Control-Expose-Headers", "mcp-session-id");
    if (req.method === "OPTIONS") {
      res.writeHead(204).end();
      return;
    }
    next();
  });
  app.get("/health", (_req, res) => res.json({ page }));
  app.all("/mcp", async (req, res) => {
    const transport = new StreamableHTTPServerTransport({
      sessionIdGenerator: undefined,
    });
    const server = makeServer();
    try {
      await server.connect(transport);
      res.on("close", () => {
        void server.close();
      });
      await transport.handleRequest(req, res, req.body);
    } catch (error) {
      console.error(error);
      if (!res.headersSent) res.writeHead(500).end();
    }
  });
  app.listen(Number(port), "127.0.0.1", () =>
    console.error(`Direct probe MCP listening on ${port}`),
  );
}
