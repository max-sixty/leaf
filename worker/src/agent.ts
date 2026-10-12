/**
 * The hosted agent's start from the edge, and the `leaf-agent` records that trace it.
 *
 * The fetch handler hands an accepted event that owes a reply to `dispatchAgentTask`,
 * which reserves the source's capacity and asks the user's container to start the
 * turn, or to write the rate-limit or startup failure receipt the user reads in its
 * place. `prewarmContainer` starts a container ahead of the first event. Every record
 * these and the model proxy write goes through `leafAgentLog`, whose fields
 * `worker/README.md`, "Hosted-agent diagnostics", describes.
 */

import { getContainer } from "@cloudflare/containers";
import * as z from "zod/mini";

import type { Env } from "./index";

interface AgentTaskParams {
  containerId: string;
  reference: string;
  route: string;
  eventId: string;
  sourceId: string;
}

const settledAgentResultSchema = z.object({ status: z.literal("settled") });

const agentResultSchemas = {
  start: z.discriminatedUnion("status", [
    settledAgentResultSchema,
    z.object({
      status: z.literal("started"),
      thread: z.string().check(z.minLength(1)),
    }),
  ]),
  fail: z.discriminatedUnion("status", [
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

// Every leaf-agent record. Callers project the fields they log, and never spread an
// AgentTaskParams, whose sourceId is the client's IP.
export function leafAgentLog(event: string, fields: Record<string, unknown>): void {
  console.log({ component: "leaf-agent", event, ...fields });
}

export function errorName(error: unknown): string {
  return error instanceof Error ? error.name : "unknown";
}

export function agentLog(
  event: string,
  params: Pick<AgentTaskParams, "reference" | "route" | "eventId">,
  fields: Record<string, unknown> = {},
): void {
  leafAgentLog(event, {
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
      error: errorName(error),
    });
    throw error;
  }
}

function agentRequest(
  params: AgentTaskParams,
  action: "start" | "fail",
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
  action: "start" | "fail",
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
  // The words the user gets belong to the adapter, which declares them beside the
  // code in `FAILURE_RECEIPTS`; naming the code here is the whole of what this knows.
  return measuredAgentOperation("failure_receipt", params, () =>
    askContainer(env, params, "fail", {
      event: params.eventId,
      failure: "rate_limited",
    }),
  );
}

export async function dispatchAgentTask(
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
      error: errorName(error),
    });
    try {
      await measuredAgentOperation("failure_receipt", params, () =>
        askContainer(env, params, "fail", {
          event: params.eventId,
          failure: "startup_failed",
        }),
      );
    } catch (receiptError) {
      agentLog("dispatch_abandoned", params, {
        error: errorName(receiptError),
      });
    }
  }
}

export async function prewarmContainer(
  env: Env,
  id: string,
  reference: string,
  route: string,
  sourceId: string,
): Promise<void> {
  const started = Date.now();
  leafAgentLog("container_prewarm_started", { reference, route });
  try {
    const allowed = await env.SOURCE_AGENT_RATE_LIMITER.limit({
      key: `prewarm:${sourceId}`,
    });
    if (!allowed.success) {
      leafAgentLog("container_prewarm_denied", {
        reference,
        route,
        durationMs: Date.now() - started,
      });
      return;
    }
    await getContainer(env.PAGES, id).start();
    leafAgentLog("container_prewarm_completed", {
      reference,
      route,
      durationMs: Date.now() - started,
    });
  } catch (error) {
    leafAgentLog("container_prewarm_failed", {
      reference,
      route,
      durationMs: Date.now() - started,
      error: errorName(error),
    });
  }
}
