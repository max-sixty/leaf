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
export { ContainerProxy } from "@cloudflare/containers";
import {
  WorkflowEntrypoint,
  type WorkflowEvent,
  type WorkflowStep,
} from "cloudflare:workers";
import { NonRetryableError } from "cloudflare:workflows";

import {
  exampleRoute,
  isExampleRequest,
  isPrivateExampleRequest,
  needsExampleSlash,
  newSessionId,
  sessionCookie,
  sessionFromCookie,
} from "./routing";

export interface Env {
  ASSETS: Fetcher;
  EXAMPLES: DurableObjectNamespace<LeafExampleSession>;
  AGENT_WORKFLOW: Workflow<AgentWorkflowParams>;
  OPENAI_API_KEY: string;
}

export interface AgentWorkflowParams {
  sessionId: string;
  slug: string;
  eventId: string;
}

type AgentResult =
  | { status: "ready"; text: string }
  | { status: "settled" }
  | { status: "appended"; event: string };

const GENERATION_FAILURE_REPLY =
  "I couldn’t generate a reply just now. Please send a new message to try again.";

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

export function authorizedOpenAIRequest(
  request: Request,
  apiKey: string,
): Request | null {
  const incoming = new URL(request.url);
  if (
    incoming.protocol !== "http:" ||
    incoming.host !== "openai.internal" ||
    !incoming.pathname.startsWith("/v1/")
  ) {
    return null;
  }
  const upstream = new URL(
    incoming.pathname + incoming.search,
    "https://api.openai.com",
  );
  const proxied = new Request(upstream, request);
  proxied.headers.set("Authorization", `Bearer ${apiKey}`);
  proxied.headers.delete("Host");
  return proxied;
}

export class LeafExampleSession extends Container<Env> {
  defaultPort = 8080;
  pingEndpoint = "localhost/health";
  sleepAfter = "10m";
  enableInternet = false;
  envVars = {
    LEAF_AGENT: "Leaf guide",
    LEAF_SESSION_ID: "leaf-website-agent",
    OPENAI_API_KEY: "injected-by-worker",
    OPENAI_BASE_URL: "http://openai.internal/v1",
  };
}

LeafExampleSession.outboundByHost = {
  "openai.internal": (request: Request, env: Env) => {
    const proxied = authorizedOpenAIRequest(request, env.OPENAI_API_KEY);
    if (proxied === null) return new Response("not found", { status: 404 });
    return fetch(proxied);
  },
};

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
    typeof params.slug !== "string" ||
    !/^[a-z0-9-]+$/.test(params.slug) ||
    typeof params.eventId !== "string" ||
    !/^[A-Za-z0-9_-]{1,128}$/.test(params.eventId)
  ) {
    throw new NonRetryableError("invalid example agent workflow parameters");
  }
  return params as AgentWorkflowParams;
}

function agentRequest(
  params: AgentWorkflowParams,
  action: "generate" | "reply",
  body: object,
): Request {
  return new Request(
    `http://container/examples/${params.slug}/_leaf/agent/${action}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    },
  );
}

async function askContainer(
  env: Env,
  params: AgentWorkflowParams,
  action: "generate" | "reply",
  body: object,
): Promise<AgentResult> {
  const response = await getContainer(env.EXAMPLES, params.sessionId).fetch(
    agentRequest(params, action, body),
  );
  const raw = await response.text();
  if (!response.ok) {
    const message = `example agent ${action} failed (${response.status}): ${raw}`;
    if (response.status < 500) throw new NonRetryableError(message);
    throw new Error(message);
  }
  let answer: Partial<AgentResult>;
  try {
    answer = JSON.parse(raw) as Partial<AgentResult>;
  } catch {
    throw new NonRetryableError(`invalid example agent ${action} response`);
  }
  const valid =
    answer.status === "settled" ||
    (action === "generate" &&
      answer.status === "ready" &&
      typeof answer.text === "string" &&
      Boolean(answer.text.trim())) ||
    (action === "reply" &&
      answer.status === "appended" &&
      typeof answer.event === "string" &&
      Boolean(answer.event));
  if (!valid) {
    throw new NonRetryableError(`invalid example agent ${action} response`);
  }
  return answer as AgentResult;
}

export async function runAgentWorkflow(
  env: Env,
  params: AgentWorkflowParams,
  step: WorkflowStep,
): Promise<AgentResult> {
  let generated: AgentResult;
  let appendStep = "append reply";
  try {
    generated = await step.do(
      "generate reply",
      {
        retries: { limit: 3, delay: "2 seconds", backoff: "exponential" },
        timeout: "2 minutes",
      },
      () => askContainer(env, params, "generate", { event: params.eventId }),
    );
  } catch {
    generated = { status: "ready", text: GENERATION_FAILURE_REPLY };
    appendStep = "append generation failure";
  }
  if (generated.status !== "ready") return generated;
  return step.do(
    appendStep,
    {
      retries: { limit: 3, delay: "2 seconds", backoff: "exponential" },
      timeout: "1 minute",
    },
    () =>
      askContainer(env, params, "reply", {
        event: params.eventId,
        text: generated.text,
      }),
  );
}

export class LeafExampleAgentWorkflow extends WorkflowEntrypoint<
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

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    const pathname = url.pathname;
    if (!isExampleRequest(pathname)) {
      return staticAssetResponse(await env.ASSETS.fetch(request));
    }
    if (isPrivateExampleRequest(pathname)) {
      return new Response("not found", { status: 404 });
    }
    if (needsExampleSlash(pathname)) {
      const canonical = new URL(request.url);
      canonical.pathname += "/";
      return Response.redirect(canonical.toString(), 308);
    }

    const secure = url.protocol === "https:";
    const existing = sessionFromCookie(request.headers.get("Cookie"), secure);
    const sessionId = existing ?? randomSessionId();
    const route = exampleRoute(pathname);
    if (route === null) return new Response("not found", { status: 404 });
    const postedRequest =
      request.method === "POST" && route.inside === "api/event"
        ? request.clone()
        : null;
    const response = await getContainer(env.EXAMPLES, sessionId).fetch(request);
    if (postedRequest) {
      const eventId = await acceptedObligation(postedRequest, response);
      if (eventId) {
        const params = { sessionId, slug: route.slug, eventId };
        await env.AGENT_WORKFLOW.createBatch([
          { id: agentWorkflowId(params), params },
        ]);
      }
    }
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
