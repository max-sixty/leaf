/**
 * The hosted agent's start from the edge, and the `leaf-agent` records that trace it.
 *
 * The fetch handler hands an accepted event that owes a reply to `dispatchAgentTask`,
 * which reserves the source's capacity and asks the user's container to start the
 * turn, or to write the rate-limit or startup failure receipt the user reads in its
 * place. Every record these and the model proxy write goes through `leafAgentLog`,
 * whose fields `worker/README.md`, "Hosted turns", describes.
 */

import { getContainer } from "@cloudflare/containers";

import type { Env } from "./index";

interface AgentTaskParams {
  containerId: string;
  reference: string;
  route: string;
  eventId: string;
  sourceId: string;
}

// What the container answers on `/_leaf/agent/{start,fail}` (`worker/leaf_website`'s
// `_start_agent` and `_fail_agent`). The Worker reads only the status, to log it.
type AgentResult =
  | { status: "settled" }
  | { status: "started"; thread: string }
  | { status: "appended"; event: string };

// The failures the Worker reports. The container writes the third, `turn_failed`, from
// its own reading of a turn it followed, so a receipt claiming a turn was observed
// comes only from the code that observed it.
type WorkerFailure = "rate_limited" | "startup_failed";

type AgentAsk =
  | { action: "start"; event: string }
  | { action: "fail"; event: string; failure: WorkerFailure };

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

function agentRequest(params: AgentTaskParams, { action, ...body }: AgentAsk): Request {
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
  ask: AgentAsk,
): Promise<AgentResult> {
  const response = await getContainer(env.PAGES, params.containerId).fetch(
    agentRequest(params, ask),
  );
  if (!response.ok) {
    throw new Error(
      `website agent ${ask.action} failed (${response.status}): ${await response.text()}`,
    );
  }
  return (await response.json()) as AgentResult;
}

async function runAgentTask(env: Env, params: AgentTaskParams): Promise<AgentResult> {
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
      askContainer(env, params, { action: "start", event: params.eventId }),
    );
  }
  // The words the user gets belong to the adapter, which declares them beside the
  // code in `FAILURE_RECEIPTS`; naming the code here is the whole of what this knows.
  return measuredAgentOperation("failure_receipt", params, () =>
    askContainer(env, params, {
      action: "fail",
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
        askContainer(env, params, {
          action: "fail",
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
