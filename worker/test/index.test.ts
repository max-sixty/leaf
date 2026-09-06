import { describe, expect, it, vi } from "vitest";

vi.mock("@cloudflare/containers", () => ({
  Container: class {},
  getContainer: vi.fn(),
}));

import { getContainer } from "@cloudflare/containers";
import worker, {
  LeafExampleSession,
  type Env,
  authorizedOpenAIRequest,
  runAgentWorkflow,
} from "../src/index";

function environment(overrides: Partial<Env> = {}): Env {
  return {
    ASSETS: { fetch: vi.fn() } as unknown as Fetcher,
    EXAMPLES: {} as DurableObjectNamespace<LeafExampleSession>,
    AGENT_WORKFLOW: { createBatch: vi.fn() } as unknown as Workflow,
    OPENAI_API_KEY: "test-key",
    ...overrides,
  };
}

describe("product-site delivery", () => {
  it.each(["/", "/how-it-works", "/registry", "/examples", "/packages"])(
    "denies framing for the static HTML route %s",
    async (pathname) => {
      const fetchAsset = vi.fn(
        async () =>
          new Response("<!doctype html><title>Leaf</title>", {
            headers: { "Content-Type": "text/html; charset=utf-8" },
          }),
      );
      const env = environment({
        ASSETS: { fetch: fetchAsset } as unknown as Fetcher,
      });

      const response = await worker.fetch(
        new Request(`https://leaf.page${pathname}`),
        env,
      );

      expect(fetchAsset).toHaveBeenCalledOnce();
      expect(response.headers.get("Content-Security-Policy")).toBe(
        "frame-ancestors 'none'",
      );
      expect(await response.text()).toBe("<!doctype html><title>Leaf</title>");
    },
  );

  it("passes a static non-HTML asset through unchanged", async () => {
    const asset = new Response("body {}", {
      headers: { "Content-Type": "text/css" },
    });
    const env = environment({
      ASSETS: { fetch: async () => asset } as unknown as Fetcher,
    });

    const response = await worker.fetch(
      new Request("https://leaf.page/theme.css"),
      env,
    );

    expect(response).toBe(asset);
    expect(response.headers.get("Content-Security-Policy")).toBeNull();
  });
});

describe("website example agent", () => {
  it("fixes OpenAI egress to one upstream and replaces the container credential", () => {
    const request = authorizedOpenAIRequest(
      new Request("http://openai.internal/v1/responses?include=usage", {
        method: "POST",
        headers: { Authorization: "Bearer visible-in-container" },
        body: "{}",
      }),
      "worker-secret",
    );

    expect(request?.url).toBe(
      "https://api.openai.com/v1/responses?include=usage",
    );
    expect(request?.headers.get("Authorization")).toBe("Bearer worker-secret");
    expect(
      authorizedOpenAIRequest(
        new Request("http://openai.internal/not-the-api"),
        "worker-secret",
      ),
    ).toBeNull();
  });

  it("never exposes the container's agent routes on the public origin", async () => {
    const env = environment();
    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/_leaf/agent/generate"),
      env,
    );

    expect(response.status).toBe(404);
    expect(getContainer).not.toHaveBeenCalled();
  });

  it("starts one durable workflow for the accepted event that still needs a reply", async () => {
    const sessionId = "01".repeat(16);
    const eventId = "02".repeat(16);
    const attempt = "reader-attempt-01";
    const containerFetch = vi.fn(async () =>
      Response.json({
        ok: true,
        state: {
          events: [{ id: eventId, attempt }],
          activity: { obligations: [{ event: eventId }] },
        },
      }),
    );
    vi.mocked(getContainer).mockReturnValue({
      fetch: containerFetch,
    } as never);
    const createBatch = vi.fn(async () => []);
    const env = environment({
      AGENT_WORKFLOW: { createBatch } as unknown as Workflow,
    });

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/event", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: `__Host-leaf-example=${sessionId}`,
        },
        body: JSON.stringify({ kind: "comment", attempt }),
      }),
      env,
    );

    expect(response.status).toBe(200);
    expect(createBatch).toHaveBeenCalledWith([
      {
        id: `reply-${sessionId}-${eventId}`,
        params: { sessionId, slug: "design-decision", eventId },
      },
    ]);
  });

  it("does not restart work after Leaf says the accepted event is settled", async () => {
    const sessionId = "06".repeat(16);
    const attempt = "settled-attempt-1";
    vi.mocked(getContainer).mockReturnValue({
      fetch: async () =>
        Response.json({
          ok: true,
          state: {
            events: [{ id: "07".repeat(16), attempt }],
            activity: { obligations: [] },
          },
        }),
    } as never);
    const createBatch = vi.fn(async () => []);
    const env = environment({
      AGENT_WORKFLOW: { createBatch } as unknown as Workflow,
    });

    await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/event", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: `__Host-leaf-example=${sessionId}`,
        },
        body: JSON.stringify({ kind: "comment", attempt }),
      }),
      env,
    );

    expect(createBatch).not.toHaveBeenCalled();
  });

  it("runs generation and append as separate retryable workflow steps", async () => {
    const params = {
      sessionId: "03".repeat(16),
      slug: "design-decision",
      eventId: "04".repeat(16),
    };
    const containerFetch = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ status: "ready", text: "A reply." }))
      .mockResolvedValueOnce(
        Response.json({ status: "appended", event: "05".repeat(16) }),
      );
    vi.mocked(getContainer).mockReturnValue({
      fetch: containerFetch,
    } as never);
    const step = {
      do: vi.fn(async (_name, _config, callback) => callback()),
    };

    const result = await runAgentWorkflow(environment(), params, step as never);

    expect(result).toEqual({ status: "appended", event: "05".repeat(16) });
    expect(step.do).toHaveBeenCalledTimes(2);
    expect(await containerFetch.mock.calls[0][0].json()).toEqual({
      event: params.eventId,
    });
    expect(await containerFetch.mock.calls[1][0].json()).toEqual({
      event: params.eventId,
      text: "A reply.",
    });
  });

  it("settles a turn visibly after generation exhausts its retries", async () => {
    const params = {
      sessionId: "08".repeat(16),
      slug: "design-decision",
      eventId: "09".repeat(16),
    };
    const containerFetch = vi.fn(async () =>
      Response.json({ status: "appended", event: "10".repeat(16) }),
    );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
    const step = {
      do: vi.fn(async (name, _config, callback) => {
        if (name === "generate reply") throw new Error("model unavailable");
        return callback();
      }),
    };

    const result = await runAgentWorkflow(environment(), params, step as never);

    expect(result).toEqual({ status: "appended", event: "10".repeat(16) });
    expect(step.do.mock.calls.map(([name]) => name)).toEqual([
      "generate reply",
      "append generation failure",
    ]);
    expect(await containerFetch.mock.calls[0][0].json()).toEqual({
      event: params.eventId,
      text: "I couldn’t generate a reply just now. Please send a new message to try again.",
    });
  });
});
