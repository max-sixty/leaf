/**
 * The outbound handler between a website container and the OpenAI Responses API.
 *
 * The container holds a dummy OpenAI credential and no internet route except this
 * host, so the Worker's key never enters a model-visible process. The handler admits
 * only the Responses HTTP request, applies the per-container model rate limit, and
 * logs request, header, first-byte, first-output and completion timings. Of the
 * streamed response it records only the type of the first output event and its item,
 * never content. `worker/README.md`, "Sandbox and rate limits" and "Hosted-agent
 * diagnostics", describe both.
 */

import { type OutboundHandlerContext } from "@cloudflare/containers";

import { errorName, leafAgentLog } from "./agent";
import type { Env } from "./index";

interface ModelRequestFields {
  containerId: string;
  modelRequestId: string;
  requestKind?: string;
  threadId?: string;
  turnId?: string;
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
