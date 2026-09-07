import { beforeEach, describe, expect, it, vi } from "vitest";

const agents = vi.hoisted(() => ({
  apiKeys: [] as string[],
  run: vi.fn(),
}));

vi.mock("@cloudflare/containers", () => ({
  Container: class {},
  getContainer: vi.fn(),
}));
vi.mock("@openai/agents-core", () => ({
  Agent: class {},
  Runner: class {
    run = agents.run;
  },
}));
vi.mock("@openai/agents-openai", () => ({
  OpenAIProvider: class {
    constructor(options: { apiKey: string }) {
      agents.apiKeys.push(options.apiKey);
    }
  },
}));

import { getContainer } from "@cloudflare/containers";
import worker, { LeafWebsiteSession, type Env, runAgentWorkflow } from "../src/index";

function environment(overrides: Partial<Env> = {}): Env {
  const allow = { limit: vi.fn(async () => ({ success: true })) } as RateLimit;
  return {
    ASSETS: { fetch: vi.fn() } as unknown as Fetcher,
    PAGES: {} as DurableObjectNamespace<LeafWebsiteSession>,
    AGENT_WORKFLOW: { create: vi.fn() } as unknown as Workflow,
    SOURCE_AGENT_RATE_LIMITER: allow,
    OPENAI_API_KEY: "test-key",
    ...overrides,
  };
}

describe("product-site delivery", () => {
  it.each([
    "/",
    "/how-it-works/",
    "/registry/",
    "/examples/",
    "/examples/design-decision/",
    "/packages/",
  ])(
    "serves the product document %s without starting its container",
    async (pathname) => {
      const assetFetch = vi.fn(
        async () =>
          new Response("<!doctype html><title>Leaf</title>", {
            headers: { "Content-Type": "text/html; charset=utf-8" },
          }),
      );
      const env = environment({
        ASSETS: { fetch: assetFetch } as unknown as Fetcher,
      });

      const response = await worker.fetch(
        new Request(`https://leaf.page${pathname}`),
        env,
      );

      expect(assetFetch).toHaveBeenCalledOnce();
      expect(getContainer).not.toHaveBeenCalled();
      expect(response.headers.get("Content-Security-Policy")).toBe(
        "frame-ancestors 'none'",
      );
      expect(response.headers.get("Set-Cookie")).toMatch(
        /^__Host-leaf-page=[0-9a-f]{32}; Path=\/; Secure; HttpOnly; SameSite=Lax$/,
      );
      expect(await response.text()).toBe("<!doctype html><title>Leaf</title>");
    },
  );

  it("serves a page's immutable runtime without allocating its session", async () => {
    const asset = new Response("export {};", {
      headers: { "Content-Type": "application/javascript" },
    });
    const assetFetch = vi.fn(async () => asset);
    const env = environment({
      ASSETS: { fetch: assetFetch } as unknown as Fetcher,
    });

    const response = await worker.fetch(
      new Request(
        "https://leaf.page/examples/design-decision/runtime/state-feed.js",
      ),
      env,
    );

    expect(response).toBe(asset);
    expect(assetFetch).toHaveBeenCalledOnce();
    expect(getContainer).not.toHaveBeenCalled();
    expect(response.headers.get("Set-Cookie")).toBeNull();
  });

  it.each([
    "/media/upload.png",
    "/examples/design-decision/media/upload.png",
  ])(
    "falls back to the reader's container for uploaded media at %s",
    async (pathname) => {
      const sessionId = "08".repeat(16);
      const assetFetch = vi.fn(
        async () => new Response("not found", { status: 404 }),
      );
      const containerFetch = vi.fn(
        async () =>
          new Response(new Uint8Array([1, 2, 3]), {
            headers: { "Content-Type": "image/png" },
          }),
      );
      vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
      const env = environment({
        ASSETS: { fetch: assetFetch } as unknown as Fetcher,
      });

      const response = await worker.fetch(
        new Request(`https://leaf.page${pathname}`, {
          headers: { Cookie: `__Host-leaf-page=${sessionId}` },
        }),
        env,
      );

      expect(assetFetch).toHaveBeenCalledOnce();
      expect(getContainer).toHaveBeenCalledWith(env.PAGES, sessionId);
      expect(containerFetch).toHaveBeenCalledOnce();
      expect(response.headers.get("Content-Type")).toBe("image/png");
      expect(new Uint8Array(await response.arrayBuffer())).toEqual(
        new Uint8Array([1, 2, 3]),
      );
    },
  );

  it("keeps published media on the edge", async () => {
    const media = new Response(new Uint8Array([4, 5, 6]), {
      headers: { "Content-Type": "image/png" },
    });
    const assetFetch = vi.fn(async () => media);
    const response = await worker.fetch(
      new Request(
        "https://leaf.page/examples/design-decision/media/published.png",
      ),
      environment({
        ASSETS: { fetch: assetFetch } as unknown as Fetcher,
      }),
    );

    expect(response).toBe(media);
    expect(assetFetch).toHaveBeenCalledOnce();
    expect(getContainer).not.toHaveBeenCalled();
  });

  it("keeps page state on the reader's canonical container", async () => {
    const containerFetch = vi.fn(async () => Response.json({ reading: "state-1" }));
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
    const env = environment();

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/state"),
      env,
    );

    expect(containerFetch).toHaveBeenCalledOnce();
    expect(env.ASSETS.fetch).not.toHaveBeenCalled();
    expect(response.headers.get("Set-Cookie")).toMatch(
      /^__Host-leaf-page=[0-9a-f]{32}; Path=\/; Secure; HttpOnly; SameSite=Lax$/,
    );
    expect(await response.json()).toEqual({ reading: "state-1" });
  });

  it("pins a mismatched edge layer to the container shell", async () => {
    const sessionId = "09".repeat(16);
    const containerFetch = vi.fn(async () =>
      Response.json(
        { reading: "old-container" },
        { headers: { "Leaf-Layer": "container-layer" } },
      ),
    );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
    const env = environment();

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/state", {
        headers: {
          Cookie: `__Host-leaf-page=${sessionId}`,
          "Leaf-Layer": "edge-layer",
        },
      }),
      env,
    );

    expect(response.headers.get("Set-Cookie")).toBe(
      "__Host-leaf-container=1; Path=/; Secure; HttpOnly; SameSite=Lax",
    );

    const documentResponse = new Response("<!doctype html><title>Container</title>", {
      headers: { "Content-Type": "text/html; charset=utf-8" },
    });
    containerFetch.mockResolvedValue(documentResponse);
    const document = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/", {
        headers: {
          Cookie: `__Host-leaf-page=${sessionId}; __Host-leaf-container=1`,
        },
      }),
      env,
    );

    expect(document).toBe(documentResponse);
    expect(env.ASSETS.fetch).not.toHaveBeenCalled();
    expect(containerFetch).toHaveBeenCalledTimes(2);
  });

  it("returns a caught-up reader to the edge", async () => {
    const sessionId = "0a".repeat(16);
    const containerFetch = vi.fn(async () =>
      Response.json(
        { reading: "current-container" },
        { headers: { "Leaf-Layer": "current-layer" } },
      ),
    );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
    const assetFetch = vi.fn(async () =>
      Response.json({ $layer: { generation: "current-layer" } }),
    );
    const env = environment({
      ASSETS: { fetch: assetFetch } as unknown as Fetcher,
    });

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/state", {
        headers: {
          Cookie:
            `__Host-leaf-page=${sessionId}; ` +
            "__Host-leaf-container=1",
          "Leaf-Layer": "current-layer",
        },
      }),
      env,
    );

    expect(response.headers.get("Set-Cookie")).toBe(
      "__Host-leaf-container=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Lax",
    );
    expect(assetFetch).toHaveBeenCalledOnce();
    expect(assetFetch.mock.calls[0][0].url).toBe(
      "https://leaf.page/examples/design-decision/registry.json",
    );
  });

  it("passes a static non-HTML asset through unchanged", async () => {
    const asset = new Response("body {}", {
      headers: { "Content-Type": "text/css" },
    });
    const env = environment({
      ASSETS: { fetch: async () => asset } as unknown as Fetcher,
    });

    const response = await worker.fetch(
      new Request("https://leaf.page/sitenote.js"),
      env,
    );

    expect(response).toBe(asset);
    expect(response.headers.get("Content-Security-Policy")).toBeNull();
  });
});

describe("website page agent", () => {
  beforeEach(() => {
    agents.apiKeys.length = 0;
    agents.run.mockReset();
  });

  it("never exposes the container's agent routes on the public origin", async () => {
    const env = environment();
    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/_leaf/agent/turn"),
      env,
    );

    expect(response.status).toBe(404);
    expect(getContainer).not.toHaveBeenCalled();
  });

  it.each([
    ["product", "/api/event", "/"],
    ["example", "/examples/design-decision/api/event", "/examples/design-decision"],
  ])(
    "starts one durable workflow for an accepted %s-page event that needs a reply",
    async (_kind, pathname, route) => {
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
      const create = vi.fn(async () => ({ id: `reply-${sessionId}-${eventId}` }));
      const env = environment({
        AGENT_WORKFLOW: { create } as unknown as Workflow,
      });

      const response = await worker.fetch(
        new Request(`https://leaf.page${pathname}`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "CF-Connecting-IP": "203.0.113.1",
            Cookie: `__Host-leaf-page=${sessionId}`,
          },
          body: JSON.stringify({ kind: "comment", attempt }),
        }),
        env,
      );

      expect(response.status).toBe(200);
      expect(create).toHaveBeenCalledWith({
        id: `reply-${sessionId}-${eventId}`,
        params: {
          sessionId,
          route,
          eventId,
          sourceId: "203.0.113.1",
        },
      });
    },
  );

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
    const create = vi.fn();
    const env = environment({
      AGENT_WORKFLOW: { create } as unknown as Workflow,
    });

    await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/event", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: `__Host-leaf-page=${sessionId}`,
        },
        body: JSON.stringify({ kind: "comment", attempt }),
      }),
      env,
    );

    expect(create).not.toHaveBeenCalled();
  });

  it("keeps the accepted response when a duplicate workflow already exists", async () => {
    const sessionId = "11".repeat(16);
    const eventId = "12".repeat(16);
    const attempt = "retried-reader-attempt";
    vi.mocked(getContainer).mockReturnValue({
      fetch: async () =>
        Response.json({
          ok: true,
          state: {
            events: [{ id: eventId, attempt }],
            activity: { obligations: [{ event: eventId }] },
          },
        }),
    } as never);
    const env = environment({
      AGENT_WORKFLOW: {
        create: vi.fn(async () => {
          throw new Error("workflow already exists");
        }),
        get: vi.fn(async () => ({
          id: `reply-${sessionId}-${eventId}`,
          status: vi.fn(async () => ({ status: "running" })),
        })),
      } as unknown as Workflow,
    });

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/event", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: `__Host-leaf-page=${sessionId}`,
        },
        body: JSON.stringify({ kind: "comment", attempt }),
      }),
      env,
    );

    expect(response.status).toBe(200);
    expect((await response.json()).ok).toBe(true);
  });

  it("keeps the retry signal when workflow admission failed", async () => {
    const sessionId = "16".repeat(16);
    const eventId = "17".repeat(16);
    const attempt = "unadmitted-reader-attempt";
    vi.mocked(getContainer).mockReturnValue({
      fetch: async () =>
        Response.json({
          ok: true,
          state: {
            events: [{ id: eventId, attempt }],
            activity: { obligations: [{ event: eventId }] },
          },
        }),
    } as never);
    const env = environment({
      AGENT_WORKFLOW: {
        create: vi.fn(async () => {
          throw new Error("workflow admission unavailable");
        }),
        get: vi.fn(async () => {
          throw new Error("workflow does not exist");
        }),
      } as unknown as Workflow,
    });

    await expect(
      worker.fetch(
        new Request("https://leaf.page/examples/design-decision/api/event", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Cookie: `__Host-leaf-page=${sessionId}`,
          },
          body: JSON.stringify({ kind: "comment", attempt }),
        }),
        env,
      ),
    ).rejects.toThrow("workflow admission unavailable");
  });

  it("restarts an existing workflow that failed before answering", async () => {
    const sessionId = "18".repeat(16);
    const eventId = "19".repeat(16);
    const attempt = "failed-workflow-attempt";
    vi.mocked(getContainer).mockReturnValue({
      fetch: async () =>
        Response.json({
          ok: true,
          state: {
            events: [{ id: eventId, attempt }],
            activity: { obligations: [{ event: eventId }] },
          },
        }),
    } as never);
    const restart = vi.fn(async () => undefined);
    const env = environment({
      AGENT_WORKFLOW: {
        create: vi.fn(async () => {
          throw new Error("workflow already exists");
        }),
        get: vi.fn(async () => ({
          id: `reply-${sessionId}-${eventId}`,
          status: vi.fn(async () => ({ status: "errored" })),
          restart,
        })),
      } as unknown as Workflow,
    });

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/event", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: `__Host-leaf-page=${sessionId}`,
        },
        body: JSON.stringify({ kind: "comment", attempt }),
      }),
      env,
    );

    expect(response.status).toBe(200);
    expect(restart).toHaveBeenCalledOnce();
  });

  it("runs the model outside the container and appends through Leaf", async () => {
    const params = {
      sessionId: "03".repeat(16),
      route: "/examples/design-decision",
      eventId: "04".repeat(16),
      sourceId: "203.0.113.1",
    };
    const containerFetch = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ status: "ready", turn: { reply_to: params.eventId } }),
      )
      .mockResolvedValueOnce(
        Response.json({ status: "appended", event: "05".repeat(16) }),
      );
    vi.mocked(getContainer).mockReturnValue({
      fetch: containerFetch,
    } as never);
    const step = {
      do: vi.fn(async (_name, _config, callback) => callback()),
    };
    agents.run.mockResolvedValueOnce({ finalOutput: " A reply. " });

    const result = await runAgentWorkflow(environment(), params, step as never);

    expect(result).toEqual({ status: "appended", event: "05".repeat(16) });
    expect(step.do.mock.calls.map(([name]) => name)).toEqual([
      "read turn",
      "reserve model capacity",
      "generate reply",
      "append reply",
    ]);
    expect(agents.apiKeys).toEqual(["test-key"]);
    expect(agents.run).toHaveBeenCalledWith(
      expect.anything(),
      JSON.stringify({ reply_to: params.eventId }),
      { maxTurns: 1 },
    );
    expect(await containerFetch.mock.calls[0][0].json()).toEqual({
      event: params.eventId,
    });
    expect(await containerFetch.mock.calls[1][0].json()).toEqual({
      event: params.eventId,
      text: "A reply.",
    });
    expect(
      containerFetch.mock.calls.some(([request]) =>
        JSON.stringify([...request.headers]).includes("test-key"),
      ),
    ).toBe(false);
  });

  it("settles an over-limit turn without calling the model", async () => {
    const params = {
      sessionId: "13".repeat(16),
      route: "/examples/design-decision",
      eventId: "14".repeat(16),
      sourceId: "203.0.113.2",
    };
    const containerFetch = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ status: "ready", turn: { reply_to: params.eventId } }),
      )
      .mockResolvedValueOnce(
        Response.json({ status: "appended", event: "15".repeat(16) }),
      );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
    const deny = vi.fn(async () => ({ success: false }));
    const env = environment({
      SOURCE_AGENT_RATE_LIMITER: { limit: deny } as RateLimit,
    });
    const step = {
      do: vi.fn(async (_name, _config, callback) => callback()),
    };

    const result = await runAgentWorkflow(env, params, step as never);

    expect(result).toEqual({ status: "appended", event: "15".repeat(16) });
    expect(deny).toHaveBeenCalledOnce();
    expect(deny).toHaveBeenCalledWith({ key: params.sourceId });
    expect(agents.run).not.toHaveBeenCalled();
    expect(step.do.mock.calls.map(([name]) => name)).toEqual([
      "read turn",
      "reserve model capacity",
      "append rate limit",
    ]);
    expect(await containerFetch.mock.calls[1][0].json()).toEqual({
      event: params.eventId,
      text: "This public demo is busy right now. Please wait a minute, then send a new message.",
    });
  });

  it("settles a turn visibly after generation exhausts its retries", async () => {
    const params = {
      sessionId: "08".repeat(16),
      route: "/examples/design-decision",
      eventId: "09".repeat(16),
      sourceId: "203.0.113.3",
    };
    const containerFetch = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({ status: "ready", turn: { reply_to: params.eventId } }),
      )
      .mockResolvedValueOnce(
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
      "read turn",
      "reserve model capacity",
      "generate reply",
      "append generation failure",
    ]);
    expect(await containerFetch.mock.calls[1][0].json()).toEqual({
      event: params.eventId,
      text: "I couldn’t generate a reply just now. Please send a new message to try again.",
    });
  });
});
