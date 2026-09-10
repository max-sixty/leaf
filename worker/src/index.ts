/**
 * Public Leaf site with edge reads and isolated canonical mutation sessions.
 *
 * Cloudflare serves the immutable live shell of each product and example page. API
 * initial state stay at the edge. A request needing mutation starts the Python Leaf
 * server in a container selected by an opaque browser cookie. The container starts with
 * the same complete page directories and writes only to its own ephemeral filesystem,
 * so one reader can exercise the real event log without changing another reader's page.
 * During an image rollout, a layer mismatch pins that reader briefly to the container's
 * complete shell so a static document never reloads against an older API in a loop.
 * Accepted browser events enter a durable batch-size-one Queue and emit content-free
 * canonical metadata to Analytics Engine.
 */

import {
  Container,
  getContainer,
  type OutboundHandlerContext,
} from "@cloudflare/containers";
export { ContainerProxy } from "@cloudflare/containers";
import { type DurableObject } from "cloudflare:workers";
import * as z from "zod/mini";

import {
  activeCookie,
  activeFromCookie,
  clearContainerCookie,
  containerCookie,
  containerFromCookie,
  isPageApiRequest,
  isPageSessionFileRequest,
  isPrivatePageRequest,
  needsPageSlash,
  newSessionId,
  pageRoute,
  parseSiteManifest,
  releaseAssetRoute,
  sessionCookie,
  sessionFromCookie,
  type PageRoute,
  type SiteManifest,
} from "./routing";

export interface Env {
  ASSETS: Fetcher;
  PAGES: DurableObjectNamespace<LeafWebsiteSession>;
  AGENT_QUEUE: Queue<AgentTaskParams>;
  WEBSITE_EVENTS: AnalyticsEngineDataset;
  SOURCE_AGENT_RATE_LIMITER: RateLimit;
  OPENAI_API_KEY: string;
}

const agentTaskParamsSchema = z.object({
  sessionId: z.string().check(z.regex(/^[0-9a-f]{32}$/)),
  reference: z.string().check(z.regex(/^\d{12}$/)),
  route: z
    .string()
    .check(z.regex(/^\/(?:[a-z0-9-]+(?:\/[a-z0-9-]+)*)?$/)),
  eventId: z.string().check(z.regex(/^[A-Za-z0-9_-]{1,128}$/)),
  sourceId: z.string().check(z.minLength(1), z.maxLength(64)),
});

export type AgentTaskParams = z.infer<typeof agentTaskParamsSchema>;

const settledAgentResultSchema = z.object({ status: z.literal("settled") });
const agentResultSchemas = {
  start: z.discriminatedUnion("status", [
    settledAgentResultSchema,
    z.object({
      status: z.literal("started"),
      thread: z.string().check(z.minLength(1)),
    }),
  ]),
  reply: z.discriminatedUnion("status", [
    settledAgentResultSchema,
    z.object({
      status: z.literal("appended"),
      event: z.string().check(z.minLength(1)),
    }),
  ]),
};

type AgentResult = z.infer<
  (typeof agentResultSchemas)[keyof typeof agentResultSchemas]
>;

const GENERATION_FAILURE_REPLY =
  "I couldn’t generate a reply just now. Please send a new message to try again.";
const RATE_LIMIT_REPLY =
  "This public demo is busy right now. Please wait a minute, then send a new message.";
const CODEX_PROXY_CREDENTIAL = "leaf-outbound-proxy";
const CLOUDFLARE_CONTAINER_CA = "/etc/cloudflare/certs/cloudflare-containers-ca.crt";
interface LeafEvent {
  id: string;
  attempt?: string;
  kind: string;
  action?: string;
  revision?: number;
}

interface AcceptedEvent {
  event: LeafEvent;
  needsReply: boolean;
}

interface LeafStateAnswer {
  state?: {
    events?: LeafEvent[];
    activity?: { obligations?: Array<{ event?: string }> };
  };
}

export class LeafWebsiteSession extends Container<Env> {
  defaultPort = 8080;
  pingEndpoint = "localhost/health";
  sleepAfter = "10m";
  enableInternet = false;
  interceptHttps = true;
  allowedHosts = ["api.openai.com"];

  constructor(ctx: DurableObject["ctx"], env: Env) {
    super(ctx, env);
    this.envVars = {
      LEAF_AGENT: "Leaf guide",
      OPENAI_API_KEY: CODEX_PROXY_CREDENTIAL,
      CODEX_CA_CERTIFICATE: CLOUDFLARE_CONTAINER_CA,
    };
  }
}

// Assignment invokes Container's inherited setter, which registers the handler for
// ContainerProxy. A static class field would shadow that setter.
LeafWebsiteSession.outboundByHost = {
  "api.openai.com": async (request: Request, env: Env, ctx: OutboundHandlerContext) => {
    const url = new URL(request.url);
    if (request.method !== "POST" || url.pathname !== "/v1/responses") {
      return new Response("blocked website agent request", { status: 403 });
    }
    if (!env.OPENAI_API_KEY) {
      return new Response("website agent credential is not configured", {
        status: 503,
      });
    }
    const capacity = await env.SOURCE_AGENT_RATE_LIMITER.limit({
      key: `model:${ctx.containerId}`,
    });
    if (!capacity.success) {
      return new Response("website agent model limit reached", { status: 429 });
    }
    const headers = new Headers(request.headers);
    headers.set("Authorization", `Bearer ${env.OPENAI_API_KEY}`);
    return fetch(new Request(request, { headers }));
  },
};

function randomSessionId(): string {
  return newSessionId(crypto.getRandomValues(new Uint8Array(16)));
}

// A support handle, not a credential: it projects the whole random cookie into a short
// numeric space while leaving 88 bits unknown, and no server door accepts it as identity.
function sessionReference(sessionId: string): string {
  return (BigInt(`0x${sessionId}`) % 1_000_000_000_000n).toString().padStart(12, "0");
}

function agentLog(
  event: string,
  params: Pick<AgentTaskParams, "reference" | "route" | "eventId">,
  fields: Record<string, unknown> = {},
): void {
  console.log({
    component: "leaf-agent",
    event,
    reference: params.reference,
    route: params.route,
    eventId: params.eventId,
    ...fields,
  });
}

async function measuredAgentOperation<T>(
  event: string,
  params: AgentTaskParams,
  operation: () => Promise<T>,
): Promise<T> {
  const started = Date.now();
  agentLog(`${event}_started`, params);
  try {
    const result = await operation();
    agentLog(`${event}_completed`, params, { durationMs: Date.now() - started });
    return result;
  } catch (error) {
    agentLog(`${event}_failed`, params, {
      durationMs: Date.now() - started,
      error: error instanceof Error ? error.name : "unknown",
    });
    throw error;
  }
}

function agentRequest(
  params: AgentTaskParams,
  action: "start" | "reply",
  body: object,
): Request {
  const root = params.route === "/" ? "" : params.route;
  return new Request(`http://container${root}/_leaf/agent/${action}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function askContainer(
  env: Env,
  params: AgentTaskParams,
  action: "start" | "reply",
  body: object,
): Promise<AgentResult> {
  const response = await getContainer(env.PAGES, params.sessionId).fetch(
    agentRequest(params, action, body),
  );
  const raw = await response.text();
  if (!response.ok) {
    throw new Error(`website agent ${action} failed (${response.status}): ${raw}`);
  }
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    throw new Error(`invalid website agent ${action} response`);
  }
  const result = agentResultSchemas[action].safeParse(value);
  if (!result.success) {
    throw new Error(`invalid website agent ${action} response`);
  }
  return result.data;
}

async function runAgentTask(
  env: Env,
  params: AgentTaskParams,
): Promise<AgentResult> {
  const allowed = await measuredAgentOperation(
    "capacity_reservation",
    params,
    async () =>
      (
        await env.SOURCE_AGENT_RATE_LIMITER.limit({
          key: params.sourceId,
        })
      ).success,
  );
  if (allowed) {
    return measuredAgentOperation("container_start", params, () =>
      askContainer(env, params, "start", { event: params.eventId }),
    );
  }
  return measuredAgentOperation("fallback_reply", params, () =>
    askContainer(env, params, "reply", {
      event: params.eventId,
      text: RATE_LIMIT_REPLY,
    }),
  );
}

const START_ATTEMPTS = 3;

async function processAgentMessage(
  env: Env,
  message: Message<unknown>,
): Promise<void> {
  const parsed = agentTaskParamsSchema.safeParse(message.body);
  if (!parsed.success) {
    console.log({
      component: "leaf-agent",
      event: "queue_rejected",
      error: "invalid_params",
    });
    message.ack();
    return;
  }
  const params = parsed.data;
  agentLog("queue_started", params, {
    durationMs: Math.max(0, Date.now() - message.timestamp.getTime()),
    attempts: message.attempts,
  });
  try {
    if (message.attempts <= START_ATTEMPTS) {
      await runAgentTask(env, params);
    } else {
      agentLog("queue_startup_failed", params, { attempts: message.attempts - 1 });
      await measuredAgentOperation("fallback_reply", params, () =>
        askContainer(env, params, "reply", {
          event: params.eventId,
          text: GENERATION_FAILURE_REPLY,
        }),
      );
    }
    message.ack();
  } catch (error) {
    agentLog("queue_retrying", params, {
      attempts: message.attempts,
      error: error instanceof Error ? error.name : "unknown",
    });
    message.retry({ delaySeconds: 2 ** Math.min(message.attempts, 3) });
  }
}

async function acceptedEvent(
  postedRequest: Request,
  response: Response,
): Promise<AcceptedEvent | null> {
  if (!response.ok) return null;
  try {
    const posted = (await postedRequest.json()) as { attempt?: unknown };
    if (typeof posted.attempt !== "string") return null;
    const answer = (await response.clone().json()) as LeafStateAnswer;
    const event = answer.state?.events?.find(
      (candidate) => candidate.attempt === posted.attempt,
    );
    if (!event) return null;
    return {
      event,
      needsReply:
        answer.state?.activity?.obligations?.some(
          (obligation) => obligation.event === event.id,
        ) ?? false,
    };
  } catch {
    return null;
  }
}

function recordAcceptedEvent(
  env: Env,
  route: PageRoute,
  release: string,
  reference: string,
  accepted: AcceptedEvent,
): void {
  env.WEBSITE_EVENTS.writeDataPoint({
    indexes: [accepted.event.id],
    blobs: [
      route.root,
      route.kind,
      accepted.event.kind,
      accepted.event.action ?? null,
      release,
      reference,
    ],
    doubles: [accepted.event.revision ?? 0, accepted.needsReply ? 1 : 0],
  });
}

async function enqueueAgentTask(
  env: Env,
  params: AgentTaskParams,
): Promise<void> {
  const started = Date.now();
  await env.AGENT_QUEUE.send(params);
  agentLog("queue_admitted", params, { durationMs: Date.now() - started });
}

function staticAssetResponse(response: Response): Response {
  const contentType = response.headers.get("Content-Type")?.split(";", 1)[0].trim();
  if (contentType?.toLowerCase() !== "text/html") return response;

  const headers = new Headers(response.headers);
  headers.append("Content-Security-Policy", "frame-ancestors 'none'");
  return new Response(response.body, {
    status: response.status,
    statusText: response.statusText,
    headers,
  });
}

const manifests = new WeakMap<object, Promise<SiteManifest>>();

async function siteManifest(request: Request, env: Env): Promise<SiteManifest> {
  let pending = manifests.get(env.ASSETS as object);
  if (!pending) {
    const url = new URL("/_leaf/site.json", request.url);
    pending = env.ASSETS.fetch(new Request(url)).then(async (response) => {
      if (!response.ok) throw new Error(`site manifest returned ${response.status}`);
      return parseSiteManifest(await response.json());
    });
    manifests.set(env.ASSETS as object, pending);
    pending.catch(() => manifests.delete(env.ASSETS as object));
  }
  return pending;
}

function stampedStaticResponse(
  response: Response,
  route: PageRoute,
  release: string,
): Response {
  const staticResponse = staticAssetResponse(response);
  const headers = new Headers(staticResponse.headers);
  headers.set("Leaf-Layer", route.layer);
  headers.set("Leaf-Release", release);
  return new Response(staticResponse.body, {
    status: staticResponse.status,
    statusText: staticResponse.statusText,
    headers,
  });
}

async function staticState(
  request: Request,
  env: Env,
  manifest: SiteManifest,
  route: PageRoute,
  reference: string,
): Promise<Response> {
  const viewRevision = request.headers.get("Leaf-View-Revision");
  const statePath = viewRevision === null ? route.state : route.states[viewRevision];
  if (statePath === undefined) {
    return new Response("unknown page revision", { status: 400 });
  }
  const url = new URL(statePath, request.url);
  const response = await env.ASSETS.fetch(new Request(url));
  if (!response.ok) return new Response("state unavailable", { status: 503 });
  const state = (await response.json()) as Record<string, unknown>;
  const now = new Date();
  state.now = now.toISOString();
  state.taken = now.getTime() / 1000;
  const headers = new Headers({
    "Cache-Control": "no-store",
    "Content-Type": "application/json; charset=utf-8",
    "Leaf-Layer": route.layer,
    "Leaf-Release": manifest.release,
    "Leaf-Session": "passive",
    "Leaf-Session-Reference": reference,
  });
  return Response.json(state, { headers });
}

export default {
  async queue(batch: MessageBatch<unknown>, env: Env): Promise<void> {
    await Promise.all(
      batch.messages.map((message) => processAgentMessage(env, message)),
    );
  },

  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const requestStarted = Date.now();
    const url = new URL(request.url);
    const pathname = url.pathname;
    if (isPrivatePageRequest(pathname)) {
      return new Response("not found", { status: 404 });
    }
    const manifest = await siteManifest(request, env);
    const releasedAsset = releaseAssetRoute(pathname, manifest.pages);
    if (releasedAsset !== null) {
      const assetUrl = new URL(request.url);
      assetUrl.pathname = releasedAsset.pathname;
      const response = stampedStaticResponse(
        await env.ASSETS.fetch(new Request(assetUrl, request)),
        releasedAsset.route,
        manifest.release,
      );
      const headers = new Headers(response.headers);
      headers.set("Cache-Control", "public, max-age=31536000, immutable");
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers,
      });
    }
    const route = pageRoute(pathname, manifest.pages);
    if (route === null) {
      return staticAssetResponse(await env.ASSETS.fetch(request));
    }
    if (needsPageSlash(pathname, route)) {
      const canonical = new URL(request.url);
      canonical.pathname += "/";
      return Response.redirect(canonical.toString(), 308);
    }

    const secure = url.protocol === "https:";
    const cookie = request.headers.get("Cookie");
    const existing = sessionFromCookie(cookie, secure);
    const active = activeFromCookie(cookie, secure);
    const containerOnly = containerFromCookie(cookie, secure);
    const sessionId = existing ?? randomSessionId();
    const reference = sessionReference(sessionId);
    if (
      !active &&
      !containerOnly &&
      request.method === "GET" &&
      route.inside === "api/state"
    ) {
      return staticState(request, env, manifest, route, reference);
    }
    if (
      (request.method === "GET" || request.method === "HEAD") &&
      !isPageApiRequest(route) &&
      !containerOnly
    ) {
      const response = stampedStaticResponse(
        await env.ASSETS.fetch(request),
        route,
        manifest.release,
      );
      if (
        response.status !== 404 ||
        !isPageSessionFileRequest(route) ||
        existing === null ||
        !active
      ) {
        if (!response.headers.get("Content-Type")?.startsWith("text/html")) {
          return response;
        }
        const headers = new Headers(response.headers);
        headers.set("Leaf-Session-Reference", reference);
        if (existing === null) {
          headers.append("Set-Cookie", sessionCookie(sessionId, secure));
        } else if (active) {
          ctx.waitUntil(getContainer(env.PAGES, sessionId).start());
        }
        return new Response(response.body, {
          status: response.status,
          statusText: response.statusText,
          headers,
        });
      }
    }
    const postedRequest =
      request.method === "POST" && route.inside === "api/event"
        ? request.clone()
        : null;
    const response = await getContainer(env.PAGES, sessionId).fetch(request);
    if (postedRequest) {
      const accepted = await acceptedEvent(postedRequest, response);
      if (accepted) {
        recordAcceptedEvent(env, route, manifest.release, reference, accepted);
      }
      if (accepted?.needsReply) {
        const sourceId = request.headers.get("CF-Connecting-IP") ?? sessionId;
        const params = {
          sessionId,
          reference,
          route: route.root,
          eventId: accepted.event.id,
          sourceId,
        };
        agentLog("event_accepted", params, {
          durationMs: Date.now() - requestStarted,
        });
        await enqueueAgentTask(env, params);
      }
    }
    const requestLayer = request.headers.get("Leaf-Layer");
    const requestRelease = request.headers.get("Leaf-Release");
    const responseLayer = response.headers.get("Leaf-Layer");
    const responseRelease = response.headers.get("Leaf-Release");
    const needsContainer =
      (requestLayer !== null &&
        responseLayer !== null &&
        requestLayer !== responseLayer) ||
      (requestRelease !== null &&
        responseRelease !== null &&
        requestRelease !== responseRelease);
    const containerCaughtUp =
      containerOnly &&
      requestLayer !== null &&
      requestLayer === responseLayer &&
      route.layer === responseLayer &&
      requestRelease !== null &&
      requestRelease === responseRelease &&
      manifest.release === responseRelease;
    if (existing !== null && active && !needsContainer && !containerCaughtUp) {
      const headers = new Headers(response.headers);
      headers.set("Leaf-Session", "active");
      headers.set("Leaf-Session-Reference", reference);
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers,
      });
    }

    const headers = new Headers(response.headers);
    headers.set("Leaf-Session", "active");
    headers.set("Leaf-Session-Reference", reference);
    if (existing === null) {
      headers.append("Set-Cookie", sessionCookie(sessionId, secure));
    }
    if (!active) headers.append("Set-Cookie", activeCookie(secure));
    if (needsContainer) headers.append("Set-Cookie", containerCookie(secure));
    if (containerCaughtUp) {
      headers.append("Set-Cookie", clearContainerCookie(secure));
    }
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  },
};
