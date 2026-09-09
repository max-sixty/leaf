import { describe, expect, it, vi } from "vitest";

const containerHandlers = vi.hoisted(
  () => new Map<string, Record<string, (...args: never[]) => Promise<Response>>>(),
);

vi.mock("@cloudflare/containers", () => ({
  Container: class {
    static get outboundByHost() {
      return containerHandlers.get(this.name);
    }

    static set outboundByHost(
      handlers: Record<string, (...args: never[]) => Promise<Response>>,
    ) {
      containerHandlers.set(this.name, handlers);
    }
  },
  ContainerProxy: class {},
  getContainer: vi.fn(),
}));

import { getContainer } from "@cloudflare/containers";
import worker, { LeafWebsiteSession, type Env, runAgentWorkflow } from "../src/index";

const RELEASE = "a".repeat(64);
const LAYER = "edge-layer";
const MANIFEST = {
  release: RELEASE,
  pages: {
    "/": {
      assets: `/_leaf-release/${RELEASE}/root`,
      directory: "_leaf/pages/index",
      kind: "product",
      layer: LAYER,
      state: "/_leaf/state/root.json",
      states: { "1": "/_leaf/state/root.json" },
    },
    "/examples": {
      assets: `/_leaf-release/${RELEASE}/examples`,
      directory: "_leaf/pages/examples",
      kind: "product",
      layer: LAYER,
      state: "/_leaf/state/examples.json",
      states: { "1": "/_leaf/state/examples.json" },
    },
    "/examples/design-decision": {
      assets: `/_leaf-release/${RELEASE}/examples--design-decision`,
      directory: "examples/design-decision",
      kind: "example",
      layer: LAYER,
      state: "/_leaf/state/examples--design-decision--r2.json",
      states: {
        "1": "/_leaf/state/examples--design-decision--r1.json",
        "2": "/_leaf/state/examples--design-decision--r2.json",
      },
    },
    "/how-it-works": {
      assets: `/_leaf-release/${RELEASE}/how-it-works`,
      directory: "_leaf/pages/how-it-works",
      kind: "product",
      layer: LAYER,
      state: "/_leaf/state/how-it-works.json",
      states: { "1": "/_leaf/state/how-it-works.json" },
    },
    "/packages": {
      assets: `/_leaf-release/${RELEASE}/packages`,
      directory: "_leaf/pages/packages",
      kind: "product",
      layer: LAYER,
      state: "/_leaf/state/packages.json",
      states: { "1": "/_leaf/state/packages.json" },
    },
    "/registry": {
      assets: `/_leaf-release/${RELEASE}/registry`,
      directory: "_leaf/pages/registry",
      kind: "product",
      layer: LAYER,
      state: "/_leaf/state/registry.json",
      states: { "1": "/_leaf/state/registry.json" },
    },
  },
};

function environment(overrides: Partial<Env> = {}): Env {
  const allow = { limit: vi.fn(async () => ({ success: true })) } as RateLimit;
  const suppliedAssets = overrides.ASSETS;
  const rest = { ...overrides };
  delete rest.ASSETS;
  const fetch = vi.fn(async (request: Request) => {
    const pathname = new URL(request.url).pathname;
    if (pathname === "/_leaf/site.json") return Response.json(MANIFEST);
    if (pathname.startsWith("/_leaf/state/")) {
      return Response.json({
        reading: "published",
        layer: { generation: LAYER },
        publication: { kind: pathname.includes("examples--") ? "example" : "product" },
        release: RELEASE,
        now: "2000-01-01T00:00:00Z",
        taken: 0,
      });
    }
    return suppliedAssets?.fetch(request) ?? new Response("not found", { status: 404 });
  });
  return {
    ASSETS: { fetch } as unknown as Fetcher,
    PAGES: {} as DurableObjectNamespace<LeafWebsiteSession>,
    AGENT_WORKFLOW: { create: vi.fn() } as unknown as Workflow,
    WEBSITE_EVENTS: { writeDataPoint: vi.fn() },
    SOURCE_AGENT_RATE_LIMITER: allow,
    OPENAI_API_KEY: "test-key",
    ...rest,
  };
}

describe("product-site delivery", () => {
  it("retries the site manifest after a transient asset failure", async () => {
    const env = environment();
    vi.mocked(env.ASSETS.fetch).mockResolvedValueOnce(
      new Response("unavailable", { status: 503 }),
    );

    await expect(worker.fetch(new Request("https://leaf.page/"), env)).rejects.toThrow(
      "site manifest returned 503",
    );
    const response = await worker.fetch(new Request("https://leaf.page/"), env);

    expect(response.status).toBe(404);
    expect(env.ASSETS.fetch).toHaveBeenCalledTimes(3);
  });

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
      expect(response.headers.get("Leaf-Release")).toBe(RELEASE);
      expect(await response.text()).toBe("<!doctype html><title>Leaf</title>");
    },
  );

  it("pins a same-layer session whose container belongs to another release", async () => {
    const sessionId = "0b".repeat(16);
    const containerFetch = vi.fn(async () =>
      Response.json(
        { reading: "old-release" },
        {
          headers: {
            "Leaf-Layer": LAYER,
            "Leaf-Release": "b".repeat(64),
          },
        },
      ),
    );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/state", {
        headers: {
          Cookie: `__Host-leaf-page=${sessionId}; __Host-leaf-active=1`,
          "Leaf-Layer": LAYER,
          "Leaf-Release": RELEASE,
        },
      }),
      environment(),
    );

    expect(response.headers.get("Set-Cookie")).toBe(
      "__Host-leaf-container=1; Path=/; Secure; HttpOnly; SameSite=Lax",
    );
  });

  it("serves a page's immutable runtime without allocating its session", async () => {
    const asset = new Response("export {};", {
      headers: { "Content-Type": "application/javascript" },
    });
    const assetFetch = vi.fn(async () => asset);
    const env = environment({
      ASSETS: { fetch: assetFetch } as unknown as Fetcher,
    });

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/runtime/state-feed.js"),
      env,
    );

    expect(await response.text()).toBe("export {};");
    expect(response.headers.get("Leaf-Release")).toBe(RELEASE);
    expect(assetFetch).toHaveBeenCalledOnce();
    expect(getContainer).not.toHaveBeenCalled();
    expect(response.headers.get("Set-Cookie")).toBeNull();
  });

  it("identifies a fresh historical document without allocating its session", async () => {
    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/versions/v1.html"),
      environment({
        ASSETS: {
          fetch: async () =>
            new Response("<!doctype html><title>Earlier</title>", {
              headers: { "Content-Type": "text/html; charset=utf-8" },
            }),
        } as unknown as Fetcher,
      }),
    );

    expect(response.headers.get("Set-Cookie")).toMatch(
      /^__Host-leaf-page=[0-9a-f]{32}; Path=\/; Secure; HttpOnly; SameSite=Lax$/,
    );
    expect(getContainer).not.toHaveBeenCalled();
  });

  it("maps a release-addressed module graph to immutable edge assets", async () => {
    const assetFetch = vi.fn(
      async () =>
        new Response("export {};", {
          headers: { "Content-Type": "application/javascript" },
        }),
    );
    const env = environment({
      ASSETS: { fetch: assetFetch } as unknown as Fetcher,
    });

    const response = await worker.fetch(
      new Request(
        `https://leaf.page/_leaf-release/${RELEASE}/examples--design-decision/runtime/state-feed.js`,
      ),
      env,
    );

    expect(assetFetch.mock.calls[0][0].url).toBe(
      "https://leaf.page/examples/design-decision/runtime/state-feed.js",
    );
    expect(response.headers.get("Cache-Control")).toBe(
      "public, max-age=31536000, immutable",
    );
    expect(response.headers.get("Leaf-Release")).toBe(RELEASE);
    expect(getContainer).not.toHaveBeenCalled();
  });

  it("prewarms an active reader's container while returning the edge document", async () => {
    const sessionId = "07".repeat(16);
    const started = Promise.resolve();
    const start = vi.fn(() => started);
    vi.mocked(getContainer).mockReturnValue({ start } as never);
    const waitUntil = vi.fn();
    const env = environment({
      ASSETS: {
        fetch: async () =>
          new Response("<!doctype html><title>Leaf</title>", {
            headers: { "Content-Type": "text/html; charset=utf-8" },
          }),
      } as unknown as Fetcher,
    });

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/", {
        headers: {
          Cookie: `__Host-leaf-page=${sessionId}; __Host-leaf-active=1`,
        },
      }),
      env,
      { waitUntil } as unknown as ExecutionContext,
    );

    expect(await response.text()).toContain("<title>Leaf</title>");
    expect(getContainer).toHaveBeenCalledWith(env.PAGES, sessionId);
    expect(start).toHaveBeenCalledOnce();
    expect(waitUntil).toHaveBeenCalledWith(started);
  });

  it.each(["/media/upload.png", "/examples/design-decision/media/upload.png"])(
    "falls back to the reader's container for uploaded media at %s",
    async (pathname) => {
      const sessionId = "08".repeat(16);
      const assetFetch = vi.fn(async () => new Response("not found", { status: 404 }));
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
          headers: {
            Cookie: `__Host-leaf-page=${sessionId}; __Host-leaf-active=1`,
          },
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
      new Request("https://leaf.page/examples/design-decision/media/published.png"),
      environment({
        ASSETS: { fetch: assetFetch } as unknown as Fetcher,
      }),
    );

    expect(new Uint8Array(await response.arrayBuffer())).toEqual(
      new Uint8Array([4, 5, 6]),
    );
    expect(assetFetch).toHaveBeenCalledOnce();
    expect(getContainer).not.toHaveBeenCalled();
  });

  it.each([
    "/examples/design-decision/revisions/r3-aabbccdd.html",
    "/examples/design-decision/versions/v3.html",
  ])("falls back to the active reader's container for %s", async (pathname) => {
    const sessionId = "18".repeat(16);
    const assetFetch = vi.fn(
      async () => new Response("not found", { status: 404 }),
    );
    const containerFetch = vi.fn(
      async () =>
        new Response("<!doctype html><title>Private revision</title>", {
          headers: { "Content-Type": "text/html; charset=utf-8" },
        }),
    );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
    const env = environment({
      ASSETS: { fetch: assetFetch } as unknown as Fetcher,
    });

    const response = await worker.fetch(
      new Request(`https://leaf.page${pathname}`, {
        headers: {
          Cookie: `__Host-leaf-page=${sessionId}; __Host-leaf-active=1`,
        },
      }),
      env,
    );

    expect(assetFetch).toHaveBeenCalledOnce();
    expect(getContainer).toHaveBeenCalledWith(env.PAGES, sessionId);
    expect(containerFetch).toHaveBeenCalledOnce();
    expect(await response.text()).toContain("Private revision");
    expect(response.headers.get("Leaf-Session")).toBe("active");
  });

  it.each([
    "/examples/design-decision/media/private.png",
    "/examples/design-decision/revisions/r3-aabbccdd.html",
    "/examples/design-decision/versions/v3.html",
  ])("does not allocate a container for an anonymous %s", async (pathname) => {
    const assetFetch = vi.fn(
      async () => new Response("not found", { status: 404 }),
    );
    const env = environment({
      ASSETS: { fetch: assetFetch } as unknown as Fetcher,
    });

    const response = await worker.fetch(
      new Request(`https://leaf.page${pathname}`),
      env,
    );

    expect(response.status).toBe(404);
    expect(assetFetch).toHaveBeenCalledOnce();
    expect(getContainer).not.toHaveBeenCalled();
    expect(response.headers.get("Set-Cookie")).toBeNull();
  });

  it("serves initial page state at the edge without creating a session", async () => {
    const env = environment();

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/state"),
      env,
    );

    expect(getContainer).not.toHaveBeenCalled();
    expect(response.headers.get("Set-Cookie")).toBeNull();
    expect(response.headers.get("Leaf-Session")).toBe("passive");
    expect(response.headers.get("Leaf-Release")).toBe(RELEASE);
    const state = await response.json();
    expect(state).toMatchObject({ reading: "published", release: RELEASE });
    expect(state.taken).toBeGreaterThan(0);
  });

  it("keeps an identified but inactive reader on passive edge state", async () => {
    const sessionId = "1a".repeat(16);
    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/state", {
        headers: {
          Cookie: `__Host-leaf-page=${sessionId}`,
          // A release the edge is not serving, so the answer below tells a stamp
          // of the deployed release apart from an echo of the request.
          "Leaf-Release": "b".repeat(64),
        },
      }),
      environment(),
    );

    expect(response.headers.get("Leaf-Session")).toBe("passive");
    // The edge names the deployed release whatever a container is running, so a
    // reader asking after a release learns nothing about one from this answer.
    expect(response.headers.get("Leaf-Release")).toBe(RELEASE);
    expect(getContainer).not.toHaveBeenCalled();
  });

  it("activates a container for a private read the edge cannot answer", async () => {
    const sessionId = "1b".repeat(16);
    const containerFetch = vi.fn(async () =>
      Response.json(
        { browser: { basis: { through_seq: 0 } } },
        { headers: { "Leaf-Layer": LAYER, "Leaf-Release": RELEASE } },
      ),
    );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);

    const response = await worker.fetch(
      new Request(
        "https://leaf.page/examples/design-decision/api/view?revision=2&through_seq=0",
        { headers: { Cookie: `__Host-leaf-page=${sessionId}` } },
      ),
      environment(),
    );

    expect(containerFetch).toHaveBeenCalledOnce();
    expect(response.headers.get("Leaf-Session")).toBe("active");
    expect(response.headers.get("Set-Cookie")).toBe(
      "__Host-leaf-active=1; Path=/; Secure; HttpOnly; SameSite=Lax",
    );
  });

  it("routes concurrent first uploads through the identity minted by the document", async () => {
    const containerFetch = vi.fn(async () =>
      Response.json(
        { path: "/media/0123456789abcdef.png" },
        { headers: { "Leaf-Layer": LAYER, "Leaf-Release": RELEASE } },
      ),
    );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
    const env = environment({
      ASSETS: {
        fetch: async () =>
          new Response("<!doctype html><title>Leaf</title>", {
            headers: { "Content-Type": "text/html; charset=utf-8" },
          }),
      } as unknown as Fetcher,
    });
    const document = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/"),
      env,
    );
    const cookie = document.headers.get("Set-Cookie")!;
    const sessionId = /__Host-leaf-page=([0-9a-f]{32})/.exec(cookie)![1];
    const upload = () =>
      worker.fetch(
        new Request("https://leaf.page/examples/design-decision/api/media", {
          method: "POST",
          headers: { Cookie: cookie, "Content-Type": "image/png" },
          body: new Uint8Array([1, 2, 3]),
        }),
        env,
      );

    const responses = await Promise.all([upload(), upload()]);

    expect(getContainer).toHaveBeenNthCalledWith(1, env.PAGES, sessionId);
    expect(getContainer).toHaveBeenNthCalledWith(2, env.PAGES, sessionId);
    expect(containerFetch).toHaveBeenCalledTimes(2);
    for (const response of responses) {
      expect(response.headers.get("Leaf-Session")).toBe("active");
      expect(response.headers.get("Set-Cookie")).toBe(
        "__Host-leaf-active=1; Path=/; Secure; HttpOnly; SameSite=Lax",
      );
    }
  });

  it("serves the requested historical revision from the release manifest", async () => {
    const env = environment();

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/state", {
        headers: { "Leaf-View-Revision": "1" },
      }),
      env,
    );

    expect(response.status).toBe(200);
    expect(vi.mocked(env.ASSETS.fetch).mock.calls[1][0].url).toBe(
      "https://leaf.page/_leaf/state/examples--design-decision--r1.json",
    );
    expect(getContainer).not.toHaveBeenCalled();
  });

  it("rejects a historical revision absent from the release manifest", async () => {
    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/state", {
        headers: { "Leaf-View-Revision": "99" },
      }),
      environment(),
    );

    expect(response.status).toBe(400);
    expect(await response.text()).toBe("unknown page revision");
    expect(getContainer).not.toHaveBeenCalled();
  });

  it.each([
    ["product", "/api/state", "/"],
    ["example", "/examples/design-decision/api/state", "/examples/design-decision/"],
  ])(
    "pins a mismatched %s edge layer to the container shell",
    async (_kind, statePath, documentPath) => {
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
        new Request(`https://leaf.page${statePath}`, {
          headers: {
            Cookie: `__Host-leaf-page=${sessionId}; __Host-leaf-active=1`,
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
        new Request(`https://leaf.page${documentPath}`, {
          headers: {
            Cookie:
              `__Host-leaf-page=${sessionId}; __Host-leaf-active=1; ` +
              "__Host-leaf-container=1",
          },
        }),
        env,
      );

      expect(await document.text()).toBe("<!doctype html><title>Container</title>");
      expect(document.headers.get("Leaf-Session")).toBe("active");
      expect(env.ASSETS.fetch).toHaveBeenCalledOnce();
      expect(containerFetch).toHaveBeenCalledTimes(2);
    },
  );

  it("returns a caught-up reader to the edge", async () => {
    const sessionId = "0a".repeat(16);
    const containerFetch = vi.fn(async () =>
      Response.json(
        { reading: "current-container" },
        { headers: { "Leaf-Layer": LAYER, "Leaf-Release": RELEASE } },
      ),
    );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
    const env = environment();

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/design-decision/api/state", {
        headers: {
          Cookie:
            `__Host-leaf-page=${sessionId}; __Host-leaf-active=1; ` +
            "__Host-leaf-container=1",
          "Leaf-Layer": LAYER,
          "Leaf-Release": RELEASE,
        },
      }),
      env,
    );

    expect(response.headers.get("Set-Cookie")).toBe(
      "__Host-leaf-container=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Lax",
    );
    expect(env.ASSETS.fetch).toHaveBeenCalledOnce();
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

    expect(await response.text()).toBe("body {}");
    expect(response.headers.get("Content-Security-Policy")).toBeNull();
  });
});

describe("website event analytics", () => {
  it("records only canonical metadata for accepted events", async () => {
    const sessionId = "31".repeat(16);
    const eventId = "32".repeat(16);
    const attempt = "analytics-attempt";
    const writeDataPoint = vi.fn();
    const containerFetch = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({
          ok: true,
          state: {
            events: [
              {
                id: eventId,
                attempt,
                kind: "action",
                action: "choose",
                revision: 2,
                detail: { private: "not analytics" },
              },
            ],
            activity: { obligations: [] },
          },
        }),
      )
      .mockResolvedValueOnce(
        Response.json({ ok: false, error: "refused", final: true }, { status: 400 }),
      );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
    const env = environment({ WEBSITE_EVENTS: { writeDataPoint } });
    const request = (body: object) =>
      worker.fetch(
        new Request("https://leaf.page/examples/design-decision/api/event", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Cookie: `__Host-leaf-page=${sessionId}`,
          },
          body: JSON.stringify(body),
        }),
        env,
      );

    await request({
      kind: "action",
      attempt,
      widget: "private-widget-id",
      action: "choose",
      revision: 2,
      detail: { private: "reader input" },
    });
    await request({ kind: "action", attempt: "refused-attempt" });

    expect(writeDataPoint).toHaveBeenCalledOnce();
    expect(writeDataPoint).toHaveBeenCalledWith({
      indexes: [eventId],
      blobs: [
        "/examples/design-decision",
        "example",
        "action",
        "choose",
        RELEASE,
      ],
      doubles: [2, 0],
    });
  });
});

describe("website page agent", () => {
  it("keeps the OpenAI secret in the trusted outbound handler", async () => {
    const env = environment();
    const session = new LeafWebsiteSession({} as never, env);

    expect(session.enableInternet).toBe(false);
    expect(session.interceptHttps).toBe(true);
    expect(session.allowedHosts).toEqual(["api.openai.com"]);
    expect(session.envVars).toMatchObject({
      LEAF_AGENT: "Leaf guide",
      OPENAI_API_KEY: "leaf-outbound-proxy",
      CODEX_CA_CERTIFICATE:
        "/etc/cloudflare/certs/cloudflare-containers-ca.crt",
    });

    const upstream = vi.fn(async () => new Response("ok"));
    vi.stubGlobal("fetch", upstream);
    const handler = containerHandlers.get("LeafWebsiteSession")?.[
      "api.openai.com"
    ];
    expect(handler).toBeDefined();
    const context = {
      containerId: "reader-container",
      className: "LeafWebsiteSession",
    };
    const response = await handler!(
      new Request("https://api.openai.com/v1/responses", {
        method: "POST",
        headers: { Authorization: "Bearer leaf-outbound-proxy" },
        body: "{}",
      }),
      env,
      context,
    );

    expect(await response.text()).toBe("ok");
    expect(env.SOURCE_AGENT_RATE_LIMITER.limit).toHaveBeenCalledWith({
      key: "model:reader-container",
    });
    const forwarded = upstream.mock.calls[0][0];
    expect(forwarded.headers.get("Authorization")).toBe("Bearer test-key");
    vi.unstubAllGlobals();
  });

  it("rejects other uses of the credential-injecting route", async () => {
    const handler = LeafWebsiteSession.outboundByHost["api.openai.com"];
    const response = await handler(
      new Request("https://api.openai.com/v1/files", { method: "POST" }),
      environment(),
      { containerId: "reader-container", className: "LeafWebsiteSession" },
    );

    expect(response.status).toBe(403);
  });

  it("fails explicitly when the deployed OpenAI secret is absent", async () => {
    const env = environment();
    Object.defineProperty(env, "OPENAI_API_KEY", { value: undefined });
    const upstream = vi.fn(async () => new Response("ok"));
    vi.stubGlobal("fetch", upstream);
    const handler = LeafWebsiteSession.outboundByHost["api.openai.com"];

    const response = await handler(
      new Request("https://api.openai.com/v1/responses", {
        method: "POST",
        body: "{}",
      }),
      env,
      { containerId: "reader-container", className: "LeafWebsiteSession" },
    );

    expect(response.status).toBe(503);
    expect(await response.text()).toBe(
      "website agent credential is not configured",
    );
    expect(upstream).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("caps model calls from one reader container", async () => {
    const denied = {
      limit: vi.fn(async () => ({ success: false })),
    } as unknown as RateLimit;
    const env = environment({ SOURCE_AGENT_RATE_LIMITER: denied });
    const upstream = vi.fn(async () => new Response("ok"));
    vi.stubGlobal("fetch", upstream);
    const handler = LeafWebsiteSession.outboundByHost["api.openai.com"];

    const response = await handler(
      new Request("https://api.openai.com/v1/responses", {
        method: "POST",
        body: "{}",
      }),
      env,
      { containerId: "reader-container", className: "LeafWebsiteSession" },
    );

    expect(response.status).toBe(429);
    expect(upstream).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
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
            events: [{ id: eventId, attempt, kind: "comment", revision: 1 }],
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
      expect(env.WEBSITE_EVENTS.writeDataPoint).toHaveBeenCalledWith({
        indexes: [eventId],
        blobs: [route, _kind, "comment", null, RELEASE],
        doubles: [1, 1],
      });
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
            events: [
              { id: "07".repeat(16), attempt, kind: "comment", revision: 1 },
            ],
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
            events: [{ id: eventId, attempt, kind: "comment", revision: 1 }],
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
            events: [{ id: eventId, attempt, kind: "comment", revision: 1 }],
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
            events: [{ id: eventId, attempt, kind: "comment", revision: 1 }],
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

  it("starts the page's hosted Codex task inside its container", async () => {
    const params = {
      sessionId: "03".repeat(16),
      route: "/examples/design-decision",
      eventId: "04".repeat(16),
      sourceId: "203.0.113.1",
    };
    const containerFetch = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ status: "ready" }))
      .mockResolvedValueOnce(
        Response.json({ status: "started", thread: "codex-thread" }),
      );
    vi.mocked(getContainer).mockReturnValue({
      fetch: containerFetch,
    } as never);
    const step = {
      do: vi.fn(async (_name, _config, callback) => callback()),
    };
    const result = await runAgentWorkflow(environment(), params, step as never);

    expect(result).toEqual({ status: "started", thread: "codex-thread" });
    expect(step.do.mock.calls.map(([name]) => name)).toEqual([
      "read turn",
      "reserve model capacity",
      "start Codex task",
    ]);
    expect(await containerFetch.mock.calls[0][0].json()).toEqual({
      event: params.eventId,
    });
    expect(await containerFetch.mock.calls[1][0].json()).toEqual({
      event: params.eventId,
    });
    expect(
      containerFetch.mock.calls.some(([request]) =>
        JSON.stringify([...request.headers]).includes("test-key"),
      ),
    ).toBe(false);
  });

  it("leaves later events to the page's standing Codex carrier", async () => {
    const params = {
      sessionId: "21".repeat(16),
      route: "/examples/design-decision",
      eventId: "22".repeat(16),
      sourceId: "203.0.113.4",
    };
    const containerFetch = vi.fn(async () =>
      Response.json({ status: "connected", thread: "codex-thread" }),
    );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
    const env = environment();
    const step = {
      do: vi.fn(async (_name, _config, callback) => callback()),
    };

    const result = await runAgentWorkflow(env, params, step as never);

    expect(result).toEqual({ status: "connected", thread: "codex-thread" });
    expect(step.do.mock.calls.map(([name]) => name)).toEqual(["read turn"]);
    expect(env.SOURCE_AGENT_RATE_LIMITER.limit).not.toHaveBeenCalled();
  });

  it("settles an over-limit task start visibly", async () => {
    const params = {
      sessionId: "13".repeat(16),
      route: "/examples/design-decision",
      eventId: "14".repeat(16),
      sourceId: "203.0.113.2",
    };
    const containerFetch = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ status: "ready" }))
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

  it("settles a turn visibly after Codex startup exhausts its retries", async () => {
    const params = {
      sessionId: "08".repeat(16),
      route: "/examples/design-decision",
      eventId: "09".repeat(16),
      sourceId: "203.0.113.3",
    };
    const containerFetch = vi
      .fn()
      .mockResolvedValueOnce(Response.json({ status: "ready" }))
      .mockResolvedValueOnce(
        Response.json({ status: "appended", event: "10".repeat(16) }),
      );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
    const step = {
      do: vi.fn(async (name, _config, callback) => {
        if (name === "start Codex task") throw new Error("Codex unavailable");
        return callback();
      }),
    };

    const result = await runAgentWorkflow(environment(), params, step as never);

    expect(result).toEqual({ status: "appended", event: "10".repeat(16) });
    expect(step.do.mock.calls.map(([name]) => name)).toEqual([
      "read turn",
      "reserve model capacity",
      "start Codex task",
      "append startup failure",
    ]);
    expect(await containerFetch.mock.calls[1][0].json()).toEqual({
      event: params.eventId,
      text: "I couldn’t generate a reply just now. Please send a new message to try again.",
    });
  });
});
