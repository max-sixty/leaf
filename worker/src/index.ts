/**
 * Public Leaf site with edge reads and isolated canonical mutation sessions.
 *
 * Cloudflare serves the immutable live shell, initial state, and published data of each
 * product and example page at the edge. A request needing mutation starts the Python
 * Leaf server in a container selected by an opaque browser cookie. The container starts
 * with the same complete page directories and writes only to its own ephemeral
 * filesystem, so one reader can exercise the real event log without changing another
 * reader's page.
 * Containers are scoped to the deployed release, so a rollout may reset this explicitly
 * ephemeral state but never sends a new document through an older container. A private
 * revision that changes executable code marks its one required container reload in the
 * URL; every ordinary document navigation stays at the edge.
 * Accepted browser events start their agent task in the already-selected reader
 * container without holding the browser acknowledgement open. Analytics Engine records
 * accepted product events; Workers Observability records the content-free execution path.
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
  isLivePageDocumentRequest,
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
  AGENT_PREWARM: "true" | "false";
  WEBSITE_EVENTS: AnalyticsEngineDataset;
  SOURCE_AGENT_RATE_LIMITER: RateLimit;
  OPENAI_API_KEY: string;
}

interface AgentTaskParams {
  containerId: string;
  reference: string;
  route: string;
  eventId: string;
  sourceId: string;
}

const settledAgentResultSchema = z.object({ status: z.literal("settled") });
const startupTime = z.nullable(
  z.number().check(z.int(), z.nonnegative(), z.maximum(300_000)),
);
const startupReportSchema = z.strictObject({
  version: z.literal(1),
  loadId: z.uuidv4(),
  release: z.string().check(z.regex(/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/)),
  layer: z.string().check(z.regex(/^[A-Za-z0-9_-]{1,128}$/)),
  outcome: z.union([
    z.literal("presented"),
    z.literal("failed"),
    z.literal("timeout"),
    z.literal("abandoned"),
  ]),
  navigationType: z.union([
    z.literal("navigate"),
    z.literal("reload"),
    z.literal("back_forward"),
    z.literal("prerender"),
    z.literal("unknown"),
  ]),
  serverMs: startupTime,
  firstByteMs: startupTime,
  firstContentfulPaintMs: startupTime,
  presentedMs: startupTime,
});
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

interface ModelRequestFields {
  containerId: string;
  modelRequestId: string;
  requestKind?: string;
  threadId?: string;
  turnId?: string;
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

function metadataString(
  metadata: Record<string, unknown>,
  key: string,
): string | undefined {
  const value = metadata[key];
  return typeof value === "string" && value.length > 0 && value.length <= 128
    ? value
    : undefined;
}

function modelRequestFields(
  request: Request,
  context: OutboundHandlerContext,
): ModelRequestFields {
  let metadata: Record<string, unknown> = {};
  const encoded = request.headers.get("x-codex-turn-metadata");
  if (encoded !== null) {
    try {
      const parsed: unknown = JSON.parse(encoded);
      if (typeof parsed === "object" && parsed !== null && !Array.isArray(parsed)) {
        metadata = parsed as Record<string, unknown>;
      }
    } catch {
      // Invalid optional diagnostics must not block the model request.
    }
  }
  return {
    containerId: context.containerId,
    modelRequestId: crypto.randomUUID(),
    requestKind: metadataString(metadata, "request_kind"),
    threadId: metadataString(metadata, "thread_id"),
    turnId: metadataString(metadata, "turn_id"),
  };
}

function modelLog(
  event: string,
  request: ModelRequestFields,
  fields: Record<string, unknown> = {},
): void {
  console.log({
    component: "leaf-agent",
    event,
    ...request,
    ...fields,
  });
}

function observeModelBody(
  body: ReadableStream<Uint8Array>,
  request: ModelRequestFields,
  started: number,
  status: number,
  upstreamRequestId: string | null,
): ReadableStream<Uint8Array> {
  const decoder = new TextDecoder();
  let buffer = "";
  let bytes = 0;
  let firstByte = true;
  let firstOutput = true;

  const observeFrames = (text: string): void => {
    buffer += text;
    const frames = buffer.replaceAll("\r\n", "\n").split("\n\n");
    buffer = frames.pop() ?? "";
    for (const frame of frames) {
      const data = frame
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      if (!data || data === "[DONE]") continue;
      let event: unknown;
      try {
        event = JSON.parse(data);
      } catch {
        continue;
      }
      if (typeof event !== "object" || event === null || Array.isArray(event)) {
        continue;
      }
      const record = event as Record<string, unknown>;
      const eventType = metadataString(record, "type");
      if (
        firstOutput &&
        eventType !== undefined &&
        !["response.created", "response.in_progress", "response.queued"].includes(
          eventType,
        )
      ) {
        const item = record.item;
        const outputType =
          typeof item === "object" && item !== null && !Array.isArray(item)
            ? metadataString(item as Record<string, unknown>, "type")
            : undefined;
        modelLog("model_response_first_output", request, {
          durationMs: Date.now() - started,
          responseEvent: eventType,
          outputType,
          upstreamRequestId,
        });
        firstOutput = false;
      }
    }
  };

  return body.pipeThrough(
    new TransformStream<Uint8Array, Uint8Array>({
      transform(chunk, controller) {
        bytes += chunk.byteLength;
        if (firstByte) {
          modelLog("model_response_first_byte", request, {
            durationMs: Date.now() - started,
            status,
            upstreamRequestId,
          });
          firstByte = false;
        }
        if (firstOutput) {
          observeFrames(decoder.decode(chunk, { stream: true }));
        }
        controller.enqueue(chunk);
      },
      flush() {
        if (firstOutput) {
          observeFrames(decoder.decode() + "\n\n");
        }
        modelLog("model_response_completed", request, {
          durationMs: Date.now() - started,
          status,
          bytes,
          upstreamRequestId,
        });
      },
    }),
  );
}

// Assignment invokes Container's inherited setter, which registers the handler for
// ContainerProxy. A static class field would shadow that setter.
LeafWebsiteSession.outboundByHost = {
  "api.openai.com": async (request: Request, env: Env, ctx: OutboundHandlerContext) => {
    const url = new URL(request.url);
    if (
      request.method === "GET" &&
      url.pathname === "/v1/responses" &&
      request.headers.get("upgrade")?.toLowerCase() === "websocket"
    ) {
      // Codex treats 426 as an immediate instruction to use its canonical HTTP
      // transport. A generic denial is retried with exponential backoff before the
      // same fallback, delaying every first turn while also bypassing the per-request
      // model timing records below.
      modelLog("model_transport_http_fallback", modelRequestFields(request, ctx));
      return new Response("use the Responses HTTP transport", { status: 426 });
    }
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
    const started = Date.now();
    const modelRequest = modelRequestFields(request, ctx);
    modelLog("model_request_started", modelRequest);
    const headers = new Headers(request.headers);
    headers.set("Authorization", `Bearer ${env.OPENAI_API_KEY}`);
    let response: Response;
    try {
      response = await fetch(new Request(request, { headers }));
    } catch (error) {
      modelLog("model_request_failed", modelRequest, {
        durationMs: Date.now() - started,
        error: error instanceof Error ? error.name : "unknown",
      });
      throw error;
    }
    const upstreamRequestId = response.headers.get("x-request-id");
    modelLog("model_response_headers", modelRequest, {
      durationMs: Date.now() - started,
      status: response.status,
      upstreamRequestId,
    });
    if (response.body === null) {
      modelLog("model_response_completed", modelRequest, {
        durationMs: Date.now() - started,
        status: response.status,
        bytes: 0,
        upstreamRequestId,
      });
      return response;
    }
    return new Response(
      observeModelBody(
        response.body,
        modelRequest,
        started,
        response.status,
        upstreamRequestId,
      ),
      response,
    );
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

// Website sessions are explicitly ephemeral. A deployment starts a fresh container
// rather than routing a new static document through an older release to preserve demo
// state that the website does not promise to persist.
function containerId(sessionId: string, release: string): string {
  return `${release}:${sessionId}`;
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

function prewarmLog(
  event: string,
  reference: string,
  route: string,
  fields: Record<string, unknown> = {},
): void {
  console.log({
    component: "leaf-agent",
    event,
    reference,
    route,
    ...fields,
  });
}

function browserIdentity(request: Request): {
  browser: string;
  browserVersion: number | null;
  platform: string;
} {
  const userAgent = request.headers.get("User-Agent") ?? "";
  const browserPatterns: Array<[string, RegExp]> = [
    ["edge", /(?:Edg|EdgA|EdgiOS)\/(\d+)/],
    ["chrome", /(?:Chrome|CriOS)\/(\d+)/],
    ["firefox", /(?:Firefox|FxiOS)\/(\d+)/],
    ["safari", /Version\/(\d+).+Safari\//],
  ];
  const browserReading = browserPatterns
    .map(([browser, pattern]) => ({ browser, match: userAgent.match(pattern) }))
    .find(({ match }) => match !== null);
  const parsedVersion = browserReading ? Number(browserReading.match?.[1]) : null;
  const platform =
    /Windows/.test(userAgent)
      ? "windows"
      : /(?:iPhone|iPad)/.test(userAgent)
        ? "ios"
        : /Android/.test(userAgent)
          ? "android"
          : /CrOS/.test(userAgent)
            ? "chromeos"
            : /Macintosh/.test(userAgent)
              ? "macos"
              : /Linux/.test(userAgent)
                ? "linux"
                : "other";
  return {
    browser: browserReading?.browser ?? "other",
    browserVersion:
      parsedVersion !== null &&
      Number.isSafeInteger(parsedVersion) &&
      parsedVersion <= 9999
        ? parsedVersion
        : null,
    platform,
  };
}

async function recordStartup(
  request: Request,
  manifest: SiteManifest,
  route: PageRoute,
  reference: string,
): Promise<Response> {
  if (Number(request.headers.get("Content-Length")) > 2048)
    return new Response("startup report is too large", { status: 413 });
  const raw = await request.text();
  if (raw.length > 2048) {
    return new Response("startup report is too large", { status: 413 });
  }
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return new Response("invalid startup report", { status: 400 });
  }
  const parsed = startupReportSchema.safeParse(value);
  if (!parsed.success) {
    return new Response("invalid startup report", { status: 400 });
  }
  console.log({
    component: "leaf-startup",
    event: "browser_startup",
    reference,
    route: route.root,
    currentRelease: manifest.release,
    ...browserIdentity(request),
    ...parsed.data,
  });
  return new Response(null, {
    status: 204,
    headers: { "Cache-Control": "no-store" },
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
  const response = await getContainer(env.PAGES, params.containerId).fetch(
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
      failure: "rate_limited",
    }),
  );
}

async function dispatchAgentTask(
  env: Env,
  params: AgentTaskParams,
): Promise<void> {
  const started = Date.now();
  agentLog("dispatch_started", params);
  try {
    const result = await runAgentTask(env, params);
    agentLog("dispatch_completed", params, {
      durationMs: Date.now() - started,
      status: result.status,
    });
  } catch (error) {
    agentLog("dispatch_failed", params, {
      durationMs: Date.now() - started,
      error: error instanceof Error ? error.name : "unknown",
    });
    try {
      await measuredAgentOperation("fallback_reply", params, () =>
        askContainer(env, params, "reply", {
          event: params.eventId,
          text: GENERATION_FAILURE_REPLY,
          failure: "startup_failed",
        }),
      );
    } catch (fallbackError) {
      agentLog("dispatch_abandoned", params, {
        error: fallbackError instanceof Error ? fallbackError.name : "unknown",
      });
    }
  }
}

async function prewarmContainer(
  env: Env,
  id: string,
  reference: string,
  route: string,
  sourceId: string,
): Promise<void> {
  const started = Date.now();
  prewarmLog("container_prewarm_started", reference, route);
  try {
    const allowed = await env.SOURCE_AGENT_RATE_LIMITER.limit({
      key: `prewarm:${sourceId}`,
    });
    if (!allowed.success) {
      prewarmLog("container_prewarm_denied", reference, route, {
        durationMs: Date.now() - started,
      });
      return;
    }
    await getContainer(env.PAGES, id).start();
    prewarmLog("container_prewarm_completed", reference, route, {
      durationMs: Date.now() - started,
    });
  } catch (error) {
    prewarmLog("container_prewarm_failed", reference, route, {
      durationMs: Date.now() - started,
      error: error instanceof Error ? error.name : "unknown",
    });
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
  return Response.json(state, {
    headers: {
      "Cache-Control": "no-store",
      "Leaf-Layer": route.layer,
      "Leaf-Release": manifest.release,
      "Leaf-Session": "passive",
      "Leaf-Session-Reference": reference,
    },
  });
}

export default {
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
    const active = activeFromCookie(cookie, secure, route.root);
    const sessionId = existing ?? randomSessionId();
    const privateContainer = containerId(sessionId, manifest.release);
    const reference = sessionReference(sessionId);
    if (request.method === "POST" && route.inside === "api/performance") {
      if (existing === null) {
        return new Response("startup report has no page session", { status: 400 });
      }
      return recordStartup(request, manifest, route, reference);
    }
    if (
      !active &&
      request.method === "GET" &&
      route.inside === "api/state"
    ) {
      return staticState(request, env, manifest, route, reference);
    }
    // Documents always come from the edge. The only exception is the one reload the
    // runtime marks after learning that a private revision changed executable code; its
    // current container owns that document. The runtime removes the marker on arrival,
    // so ordinary reloads and later visits return to the static shell.
    const privateRevision = url.searchParams.get("_leaf-revision");
    const privateDocumentReload =
      existing !== null &&
      active &&
      isLivePageDocumentRequest(route) &&
      /^[1-9][0-9]*$/.test(privateRevision ?? "");
    if (
      (request.method === "GET" || request.method === "HEAD") &&
      !isPageApiRequest(route) &&
      !privateDocumentReload
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
        headers.set("Server-Timing", `leaf;dur=${Date.now() - requestStarted}`);
        if (existing === null) {
          headers.append("Set-Cookie", sessionCookie(sessionId, secure));
        }
        if (
          env.AGENT_PREWARM === "true" &&
          request.method === "GET" &&
          request.headers.get("Sec-Fetch-Dest") === "document"
        ) {
          const sourceId = request.headers.get("CF-Connecting-IP") ?? "unknown";
          ctx.waitUntil(
            prewarmContainer(
              env,
              privateContainer,
              reference,
              route.root,
              sourceId,
            ),
          );
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
    const response = await getContainer(env.PAGES, privateContainer).fetch(request);
    if (postedRequest) {
      const accepted = await acceptedEvent(postedRequest, response);
      if (accepted) {
        recordAcceptedEvent(env, route, manifest.release, reference, accepted);
      }
      if (accepted?.needsReply) {
        const sourceId = request.headers.get("CF-Connecting-IP") ?? sessionId;
        const params = {
          containerId: privateContainer,
          reference,
          route: route.root,
          eventId: accepted.event.id,
          sourceId,
        };
        agentLog("event_accepted", params, {
          durationMs: Date.now() - requestStarted,
        });
        // TODO(2026-09-10): Persist the accepted event and active Codex turn identity
        // in this container's Durable Object before returning the acknowledgement.
        // TODO(2026-09-10): Add an alarm/status hook that recovers a dispatch when
        // its container disappears or it exceeds the Worker's waitUntil window.
        ctx.waitUntil(dispatchAgentTask(env, params));
      }
    }
    const headers = new Headers(response.headers);
    headers.set("Leaf-Session", "active");
    headers.set("Leaf-Session-Reference", reference);
    if (existing === null) {
      headers.append("Set-Cookie", sessionCookie(sessionId, secure));
    }
    if (!active) headers.append("Set-Cookie", activeCookie(secure, route.root));
    if (response.headers.get("Content-Type")?.startsWith("text/html")) {
      headers.set("Server-Timing", `leaf;dur=${Date.now() - requestStarted}`);
    }
    return new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers,
    });
  },
};
