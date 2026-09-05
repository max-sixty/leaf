/**
 * Public Leaf site and isolated, canonical example sessions.
 *
 * Static product routes come from the build's asset directory. A concrete example
 * route goes to the Python Leaf server in a container selected by an opaque browser
 * cookie. The container starts with complete page directories and writes only to its
 * own ephemeral filesystem, so one reader can exercise the real event log without
 * changing another reader's example or inventing a second state implementation.
 */

import { Container, getContainer } from "@cloudflare/containers";

import {
  isExampleRequest,
  needsExampleSlash,
  newSessionId,
  sessionCookie,
  sessionFromCookie,
} from "./routing";

interface Env {
  ASSETS: Fetcher;
  EXAMPLES: DurableObjectNamespace<LeafExampleSession>;
}

export class LeafExampleSession extends Container<Env> {
  defaultPort = 8080;
  pingEndpoint = "localhost/health";
  sleepAfter = "10m";
  enableInternet = false;
}

function randomSessionId(): string {
  return newSessionId(crypto.getRandomValues(new Uint8Array(16)));
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const pathname = url.pathname;
    if (!isExampleRequest(pathname)) return env.ASSETS.fetch(request);
    if (needsExampleSlash(pathname)) {
      const canonical = new URL(request.url);
      canonical.pathname += "/";
      return Response.redirect(canonical.toString(), 308);
    }

    const secure = url.protocol === "https:";
    const existing = sessionFromCookie(request.headers.get("Cookie"), secure);
    const sessionId = existing ?? randomSessionId();
    const response = await getContainer(env.EXAMPLES, sessionId).fetch(request);
    if (existing !== null) return response;

    const headers = new Headers(response.headers);
    headers.append("Set-Cookie", sessionCookie(sessionId, secure));
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  },
};
