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
 */

import {
  Container,
  getContainer,
  type OutboundHandlerContext,
} from "@cloudflare/containers";
export { ContainerProxy } from "@cloudflare/containers";
import {
  type DurableObject,
  WorkflowEntrypoint,
  type WorkflowEvent,
  type WorkflowStep,
} from "cloudflare:workers";
import { NonRetryableError } from "cloudflare:workflows";

import {
  activeCookie,
  activeFromCookie,
  clearContainerCookie,
  containerCookie,
  containerFromCookie,
  isPageApiRequest,
  isPageMediaRequest,
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
  AGENT_WORKFLOW: Workflow<AgentWorkflowParams>;
  SOURCE_AGENT_RATE_LIMITER: RateLimit;
  OPENAI_API_KEY: string;
}

export interface AgentWorkflowParams {
  sessionId: string;
  route: string;
  eventId: string;
  sourceId: string;
}

type AgentResult =
  | { status: "ready" }
  | { status: "connected"; thread: string }
  | { status: "started"; thread: string }
  | { status: "settled" }
  | { status: "appended"; event: string };

const GENERATION_FAILURE_REPLY =
  "I couldn’t generate a reply just now. Please send a new message to try again.";
const RATE_LIMIT_REPLY =
  "This public demo is busy right now. Please wait a minute, then send a new message.";
const CODEX_PROXY_CREDENTIAL = "leaf-outbound-proxy";
const CLOUDFLARE_CONTAINER_CA =
  "/etc/cloudflare/certs/cloudflare-containers-ca.crt";
interface LeafEvent {
  id: string;
  attempt?: string;
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

  static outboundByHost = {
    "api.openai.com": async (
      request: Request,
      env: Env,
      ctx: OutboundHandlerContext,
    ) => {
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

  constructor(ctx: DurableObject["ctx"], env: Env) {
    super(ctx, env);
    this.envVars = {
      LEAF_AGENT: "Leaf guide",
      OPENAI_API_KEY: CODEX_PROXY_CREDENTIAL,
      CODEX_CA_CERTIFICATE: CLOUDFLARE_CONTAINER_CA,
    };
  }
}

function randomSessionId(): string {
  return newSessionId(crypto.getRandomValues(new Uint8Array(16)));
}

function agentWorkflowId({ sessionId, eventId }: AgentWorkflowParams): string {
  return `reply-${sessionId}-${eventId}`;
}

function validatedAgentParams(value: unknown): AgentWorkflowParams {
  const params = value as Partial<AgentWorkflowParams> | null;
  if (
    params === null ||
    typeof params !== "object" ||
    typeof params.sessionId !== "string" ||
    !/^[0-9a-f]{32}$/.test(params.sessionId) ||
    typeof params.route !== "string" ||
    !/^\/(?:[a-z0-9-]+(?:\/[a-z0-9-]+)*)?$/.test(params.route) ||
    typeof params.eventId !== "string" ||
    !/^[A-Za-z0-9_-]{1,128}$/.test(params.eventId) ||
    typeof params.sourceId !== "string" ||
    params.sourceId.length === 0 ||
    params.sourceId.length > 64
  ) {
    throw new NonRetryableError("invalid website agent workflow parameters");
  }
  return params as AgentWorkflowParams;
}

function agentRequest(
  params: AgentWorkflowParams,
  action: "turn" | "start" | "reply",
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
  params: AgentWorkflowParams,
  action: "turn" | "start" | "reply",
  body: object,
): Promise<AgentResult> {
  const response = await getContainer(env.PAGES, params.sessionId).fetch(
    agentRequest(params, action, body),
  );
  const raw = await response.text();
  if (!response.ok) {
    const message = `website agent ${action} failed (${response.status}): ${raw}`;
    if (response.status < 500) throw new NonRetryableError(message);
    throw new Error(message);
  }
  let answer: Partial<AgentResult>;
  try {
    answer = JSON.parse(raw) as Partial<AgentResult>;
  } catch {
    throw new NonRetryableError(`invalid website agent ${action} response`);
  }
  const valid =
    answer.status === "settled" ||
    (action === "turn" && answer.status === "ready") ||
    (action === "turn" &&
      answer.status === "connected" &&
      typeof answer.thread === "string" &&
      Boolean(answer.thread)) ||
    (action === "start" &&
      answer.status === "started" &&
      typeof answer.thread === "string" &&
      Boolean(answer.thread)) ||
    (action === "reply" &&
      answer.status === "appended" &&
      typeof answer.event === "string" &&
      Boolean(answer.event));
  if (!valid) {
    throw new NonRetryableError(`invalid website agent ${action} response`);
  }
  return answer as AgentResult;
}

export async function runAgentWorkflow(
  env: Env,
  params: AgentWorkflowParams,
  step: WorkflowStep,
): Promise<AgentResult> {
  let fallback = GENERATION_FAILURE_REPLY;
  let appendStep = "append startup failure";
  try {
    const turn = await step.do(
      "read turn",
      {
        retries: { limit: 3, delay: "2 seconds", backoff: "exponential" },
        timeout: "1 minute",
      },
      () => askContainer(env, params, "turn", { event: params.eventId }),
    );
    if (turn.status !== "ready") return turn;
    const allowed = await step.do(
      "reserve model capacity",
      {
        retries: { limit: 3, delay: "2 seconds", backoff: "exponential" },
        timeout: "1 minute",
      },
      async () =>
        (
          await env.SOURCE_AGENT_RATE_LIMITER.limit({
            key: params.sourceId,
          })
        ).success,
    );
    if (allowed) {
      return await step.do(
        "start Codex task",
        {
          retries: { limit: 3, delay: "2 seconds", backoff: "exponential" },
          timeout: "2 minutes",
        },
        () => askContainer(env, params, "start", { event: params.eventId }),
      );
    } else {
      fallback = RATE_LIMIT_REPLY;
      appendStep = "append rate limit";
    }
  } catch {
    // The deterministic fallback closes the exact event after startup retries.
  }
  return step.do(
    appendStep,
    {
      retries: { limit: 3, delay: "2 seconds", backoff: "exponential" },
      timeout: "1 minute",
    },
    () =>
      askContainer(env, params, "reply", {
        event: params.eventId,
        text: fallback,
      }),
  );
}

export class LeafWebsiteAgentWorkflow extends WorkflowEntrypoint<
  Env,
  AgentWorkflowParams
> {
  async run(event: WorkflowEvent<AgentWorkflowParams>, step: WorkflowStep) {
    return runAgentWorkflow(this.env, validatedAgentParams(event.payload), step);
  }
}

async function acceptedObligation(
  postedRequest: Request,
  response: Response,
): Promise<string | null> {
  if (!response.ok) return null;
  try {
    const posted = (await postedRequest.json()) as { attempt?: unknown };
    if (typeof posted.attempt !== "string") return null;
    const answer = (await response.clone().json()) as LeafStateAnswer;
    const event = answer.state?.events?.find(
      (candidate) => candidate.attempt === posted.attempt,
    );
    if (
      !event ||
      !answer.state?.activity?.obligations?.some(
        (obligation) => obligation.event === event.id,
      )
    ) {
      return null;
    }
    return event.id;
  } catch {
    return null;
  }
}

async function resumeFailedWorkflow(env: Env, workflowId: string): Promise<void> {
  const instance = await env.AGENT_WORKFLOW.get(workflowId);
  const state = await instance.status();
  if (state.status === "errored" || state.status === "terminated") {
    await instance.restart();
  }
}

async function startAgentWorkflow(
  env: Env,
  params: AgentWorkflowParams,
): Promise<void> {
  const workflowId = agentWorkflowId(params);
  try {
    await env.AGENT_WORKFLOW.create({ id: workflowId, params });
  } catch (error) {
    // Treat a duplicate id as success and revive a failed prior attempt. Preserve
    // the outbox's retry signal when no workflow exists to answer the durable event.
    try {
      await resumeFailedWorkflow(env, workflowId);
    } catch {
      throw error;
    }
  }
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
  });
  return Response.json(state, { headers });
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
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
    if (
      !active &&
      !containerOnly &&
      request.method === "GET" &&
      route.inside === "api/state"
    ) {
      return staticState(request, env, manifest, route);
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
      if (response.status !== 404 || !isPageMediaRequest(route)) {
        if (!response.headers.get("Content-Type")?.startsWith("text/html")) {
          return response;
        }
        const headers = new Headers(response.headers);
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
      const eventId = await acceptedObligation(postedRequest, response);
      if (eventId) {
        const sourceId = request.headers.get("CF-Connecting-IP") ?? sessionId;
        const params = { sessionId, route: route.root, eventId, sourceId };
        await startAgentWorkflow(env, params);
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
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers,
      });
    }

    const headers = new Headers(response.headers);
    headers.set("Leaf-Session", "active");
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
