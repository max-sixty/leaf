// The localhost probe admits its reference host and server-side clients only.
import assert from "node:assert/strict";
import { request } from "node:http";

const base = new URL(process.argv[2]);
const call = (route, method, headers) =>
  new Promise((resolve, reject) => {
    const req = request(
      new URL(route, base),
      {
        method,
        setHost: false,
        headers: {
          Host: base.host,
          Accept: "application/json,text/event-stream",
          "Content-Type": "application/json",
          ...headers,
        },
      },
      (res) => {
        let body = "";
        res.setEncoding("utf8");
        res.on("data", (chunk) => {
          body += chunk;
        });
        res.on("end", () => resolve({ status: res.statusCode, body }));
        res.on("error", reject);
      },
    );
    req.on("error", reject);
    req.setTimeout(5000, () => req.destroy(new Error("HTTP probe timed out")));
    req.end(
      method === "POST"
        ? JSON.stringify({ jsonrpc: "2.0", id: 1, method: "ping" })
        : undefined,
    );
  });

const cases = [
  ["server-side localhost", { Host: `localhost:${base.port}` }, true],
  ["server-side IPv4", { Host: `127.0.0.1:${base.port}` }, true],
  ["reference host", { Origin: "http://localhost:8080" }, true],
  ["foreign host", { Host: `attacker.invalid:${base.port}` }, false],
  ["missing host", { Host: "" }, false],
  ["foreign origin", { Origin: "http://attacker.invalid" }, false],
  ["opaque origin", { Origin: "null" }, false],
];
const checks = [];
for (const [name, headers, allowed] of cases) {
  for (const [route, method, success] of [
    ["/health", "GET", 200],
    ["/mcp", "POST", 200],
    ["/mcp", "OPTIONS", 204],
  ]) {
    const response = await call(route, method, headers);
    assert.equal(
      response.status,
      allowed ? success : 403,
      `${name}: ${method} ${route}`,
    );
    if (allowed && method === "GET")
      assert.equal(typeof JSON.parse(response.body).page, "string");
    if (allowed && method === "POST") {
      const data = response.body.split("\n").find((line) => line.startsWith("data: "));
      assert.deepEqual(JSON.parse(data.slice(6)), {
        result: {},
        jsonrpc: "2.0",
        id: 1,
      });
    }
    checks.push({ client: name, method, route, status: response.status });
  }
}
console.log(JSON.stringify({ passed: true, checks }, null, 2));
