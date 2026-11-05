// Preload in Playwright's Node driver with NODE_OPTIONS=--require=... .
// Workers invocation logs cannot explain a connection that never reached a Worker.
// Keep socket lifecycle evidence in CI stderr, without Node's NODE_DEBUG=http/net
// dumps: those can include authentication headers. Never log paths, headers (except
// the response's cf-ray), bodies, error messages, or TLS session/key material.
const { channel } = require("node:diagnostics_channel");

const sockets = new WeakMap();
let nextSocket = 0;
let nextRequest = 0;

function record(event, fields) {
  process.stderr.write(
    `${JSON.stringify({ component: "leaf-http-transport", at: new Date().toISOString(), event, ...fields })}\n`,
  );
}

channel("http.client.request.start").subscribe(({ request }) => {
  const socket = request.socket;
  if (!sockets.has(socket)) {
    const id = ++nextSocket;
    sockets.set(socket, id);
    const peer = () => ({
      socket: id,
      localAddress: socket.localAddress,
      localPort: socket.localPort,
      remoteAddress: socket.remoteAddress,
      remotePort: socket.remotePort,
    });
    record("socket", peer());
    socket.once("connect", () => record("connect", peer()));
    socket.once("secureConnect", () =>
      record("tls", {
        ...peer(),
        protocol: socket.getProtocol(),
        alpn: socket.alpnProtocol,
        authorized: socket.authorized,
      }),
    );
    socket.once("end", () => record("end", { socket: id }));
    socket.once("error", (error) =>
      record("socket-error", { socket: id, code: error.code }),
    );
    socket.once("close", (hadError) => record("close", { socket: id, hadError }));
  }
  const fields = {
    request: ++nextRequest,
    socket: sockets.get(socket),
    reused: request.reusedSocket,
  };
  const started = performance.now();
  const elapsed = () => Math.round(performance.now() - started);
  record("request", fields);
  request.once("error", (error) =>
    record("request-error", { ...fields, elapsedMs: elapsed(), code: error.code }),
  );
  request.once("response", (response) => {
    record("response", {
      ...fields,
      elapsedMs: elapsed(),
      status: response.statusCode,
      // Cloudflare's ray is the join key with Workers Observability. Restrict its
      // shape too, so a server cannot smuggle arbitrary header data into the log.
      ray: /^[a-f0-9]+-[a-z]+$/i.test(response.headers["cf-ray"] || "")
        ? response.headers["cf-ray"]
        : undefined,
    });
    response.once("end", () =>
      record("response-end", { ...fields, elapsedMs: elapsed() }),
    );
    response.once("aborted", () =>
      record("response-aborted", { ...fields, elapsedMs: elapsed() }),
    );
  });
});

record("enabled", { node: process.version });
