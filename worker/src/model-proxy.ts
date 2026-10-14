/**
 * The outbound handler between a website container and the OpenAI Responses API.
 *
 * The container holds a dummy OpenAI credential and no internet route except this
 * host, so the Worker's key never enters a model-visible process. The handler admits
 * only the Responses HTTP request, applies the per-container model rate limit, and
 * logs request, header, first-byte, first-output and completion timings. Of the
 * streamed response it records only the type of the first output event and its item,
 * never content. `worker/README.md`, "Sandbox and rate limits" and "Hosted turns",
 * describe both.
 */

import { type OutboundHandlerContext } from "@cloudflare/containers";
import * as z from "zod/mini";

import { errorName, leafAgentLog } from "./agent";
import type { Env } from "./index";

interface ModelRequestFields {
  containerId: string;
  modelRequestId: string;
  requestKind?: string;
  threadId?: string;
  turnId?: string;
}

// Both readings are optional diagnostics: a label that fails is dropped, and an
// unreadable value reads as one carrying no labels, so neither blocks the request.
const label = z.catch(
  z.optional(z.string().check(z.minLength(1), z.maxLength(128))),
  undefined,
);
const turnMetadata = z.catch(
  z.object({ request_kind: label, thread_id: label, turn_id: label }),
  {},
);
const responseEvent = z.catch(
  z.object({ type: label, item: z.catch(z.optional(z.object({ type: label })), undefined) }),
  {},
);

function jsonValue(text: string | null): unknown {
  if (text === null) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

function modelRequestFields(
  request: Request,
  context: OutboundHandlerContext,
): ModelRequestFields {
  const metadata = turnMetadata.parse(
    jsonValue(request.headers.get("x-codex-turn-metadata")),
  );
  return {
    containerId: context.containerId,
    modelRequestId: crypto.randomUUID(),
    requestKind: metadata.request_kind,
    threadId: metadata.thread_id,
    turnId: metadata.turn_id,
  };
}

function modelLog(
  event: string,
  request: ModelRequestFields,
  fields: Record<string, unknown> = {},
): void {
  leafAgentLog(event, { ...request, ...fields });
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
      const event = responseEvent.parse(jsonValue(data));
      if (
        firstOutput &&
        event.type !== undefined &&
        !["response.created", "response.in_progress", "response.queued"].includes(
          event.type,
        )
      ) {
        modelLog("model_response_first_output", request, {
          durationMs: Date.now() - started,
          responseEvent: event.type,
          outputType: event.item?.type,
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

// The container's only route out: Codex's Responses API request, with the dummy
// credential the container holds replaced by the Worker's key. Every other request to
// the host is refused before it leaves.
export async function proxyModelRequest(
  request: Request,
  env: Env,
  ctx: OutboundHandlerContext,
): Promise<Response> {
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
      error: errorName(error),
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
}
