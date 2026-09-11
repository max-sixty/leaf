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
import worker, {
  LeafWebsiteSession,
  type Env,
} from "../src/index";

const RELEASE = "a".repeat(64);
const LAYER = "edge-layer";
const MANIFEST = {
  release: RELEASE,
  pages: {
    "/": {
      assets: `/_leaf-release/${RELEASE}/root`,
      description: "The leaf page.",
      directory: "_leaf/pages/index",
      image: "/media/0000000000000001.png",
      kind: "product",
      layer: LAYER,
      state: "/_leaf/state/root.json",
      states: { "1": "/_leaf/state/root.json" },
      title: "leaf",
    },
    "/examples": {
      assets: `/_leaf-release/${RELEASE}/examples`,
      description: "The leaf examples page.",
      directory: "_leaf/pages/examples",
      image: "/media/0000000000000002.png",
      kind: "product",
      layer: LAYER,
      state: "/_leaf/state/examples.json",
      states: { "1": "/_leaf/state/examples.json" },
      title: "leaf examples",
    },
    "/examples/triage-board": {
      assets: `/_leaf-release/${RELEASE}/examples--triage-board`,
      description: "The Release triage page.",
      directory: "examples/triage-board",
      image: "/examples/media/0000000000000003.jpg",
      kind: "example",
      layer: LAYER,
      state: "/_leaf/state/examples--triage-board--r2.json",
      states: {
        "1": "/_leaf/state/examples--triage-board--r1.json",
        "2": "/_leaf/state/examples--triage-board--r2.json",
      },
      title: "Release triage",
    },
    "/how-it-works": {
      assets: `/_leaf-release/${RELEASE}/how-it-works`,
      description: "The how leaf works page.",
      directory: "_leaf/pages/how-it-works",
      image: "/media/0000000000000004.png",
      kind: "product",
      layer: LAYER,
      state: "/_leaf/state/how-it-works.json",
      states: { "1": "/_leaf/state/how-it-works.json" },
      title: "how leaf works",
    },
    "/packages": {
      assets: `/_leaf-release/${RELEASE}/packages`,
      description: "The leaf packages page.",
      directory: "_leaf/pages/packages",
      image: "/media/0000000000000005.png",
      kind: "product",
      layer: LAYER,
      state: "/_leaf/state/packages.json",
      states: { "1": "/_leaf/state/packages.json" },
      title: "leaf packages",
    },
    "/registry": {
      assets: `/_leaf-release/${RELEASE}/registry`,
      description: "The leaf registry keys page.",
      directory: "_leaf/pages/registry",
      image: "/media/0000000000000006.png",
      kind: "product",
      layer: LAYER,
      state: "/_leaf/state/registry.json",
      states: { "1": "/_leaf/state/registry.json" },
      title: "leaf registry keys",
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
    AGENT_PREWARM: "false",
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
    "/examples/triage-board/",
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
      new Request("https://leaf.page/examples/triage-board/api/state", {
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
      new Request("https://leaf.page/examples/triage-board/runtime/state-feed.js"),
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
      new Request("https://leaf.page/examples/triage-board/versions/v1.html"),
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
        `https://leaf.page/_leaf-release/${RELEASE}/examples--triage-board/runtime/state-feed.js`,
      ),
      env,
    );

    expect(assetFetch.mock.calls[0][0].url).toBe(
      "https://leaf.page/examples/triage-board/runtime/state-feed.js",
    );
    expect(response.headers.get("Cache-Control")).toBe(
      "public, max-age=31536000, immutable",
    );
    expect(response.headers.get("Leaf-Release")).toBe(RELEASE);
    expect(getContainer).not.toHaveBeenCalled();
  });

  it("prewarms a fresh reader's container while returning the edge document", async () => {
    const started = Promise.resolve();
    const start = vi.fn(() => started);
    vi.mocked(getContainer).mockReturnValue({ start } as never);
    const waitUntil = vi.fn();
    const env = environment({
      AGENT_PREWARM: "true",
      ASSETS: {
        fetch: async () =>
          new Response("<!doctype html><title>Leaf</title>", {
            headers: { "Content-Type": "text/html; charset=utf-8" },
          }),
      } as unknown as Fetcher,
    });

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/", {
        headers: {
          "CF-Connecting-IP": "203.0.113.8",
          "Sec-Fetch-Dest": "document",
        },
      }),
      env,
      { waitUntil } as unknown as ExecutionContext,
    );

    expect(await response.text()).toContain("<title>Leaf</title>");
    const sessionId = response.headers
      .get("Set-Cookie")
      ?.match(/^__Host-leaf-page=([0-9a-f]{32});/)?.[1];
    expect(sessionId).toBeDefined();
    expect(waitUntil).toHaveBeenCalledOnce();
    await waitUntil.mock.calls[0][0];

    expect(env.SOURCE_AGENT_RATE_LIMITER.limit).toHaveBeenCalledWith({
      key: "prewarm:203.0.113.8",
    });
    expect(getContainer).toHaveBeenCalledWith(env.PAGES, sessionId);
    expect(start).toHaveBeenCalledOnce();
  });

  it("does not prewarm an HTML probe that is not a browser navigation", async () => {
    const env = environment({
      AGENT_PREWARM: "true",
      ASSETS: {
        fetch: async () =>
          new Response("<!doctype html><title>Leaf</title>", {
            headers: { "Content-Type": "text/html; charset=utf-8" },
          }),
      } as unknown as Fetcher,
    });
    const waitUntil = vi.fn();

    const response = await worker.fetch(
      new Request("https://leaf.page/"),
      env,
      { waitUntil } as unknown as ExecutionContext,
    );

    expect(response.status).toBe(200);
    expect(getContainer).not.toHaveBeenCalled();
    expect(waitUntil).not.toHaveBeenCalled();
  });

  it("does not allocate a container when a source exhausts its prewarm limit", async () => {
    const deny = vi.fn(async () => ({ success: false }));
    const env = environment({
      AGENT_PREWARM: "true",
      ASSETS: {
        fetch: async () =>
          new Response("<!doctype html><title>Leaf</title>", {
            headers: { "Content-Type": "text/html; charset=utf-8" },
          }),
      } as unknown as Fetcher,
      SOURCE_AGENT_RATE_LIMITER: { limit: deny } as RateLimit,
    });
    const waitUntil = vi.fn();

    const response = await worker.fetch(
      new Request("https://leaf.page/", {
        headers: {
          "CF-Connecting-IP": "203.0.113.9",
          "Sec-Fetch-Dest": "document",
        },
      }),
      env,
      { waitUntil } as unknown as ExecutionContext,
    );
    await waitUntil.mock.calls[0][0];

    expect(response.status).toBe(200);
    expect(deny).toHaveBeenCalledWith({ key: "prewarm:203.0.113.9" });
    expect(getContainer).not.toHaveBeenCalled();
  });

  it.each(["/media/upload.png", "/examples/triage-board/media/upload.png"])(
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
      new Request("https://leaf.page/examples/triage-board/media/published.png"),
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
    "/examples/triage-board/revisions/r3-aabbccdd.html",
    "/examples/triage-board/versions/v3.html",
  ])("falls back to the active reader's container for %s", async (pathname) => {
    const sessionId = "18".repeat(16);
    const assetFetch = vi.fn(async () => new Response("not found", { status: 404 }));
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
    "/examples/triage-board/media/private.png",
    "/examples/triage-board/revisions/r3-aabbccdd.html",
    "/examples/triage-board/versions/v3.html",
  ])("does not allocate a container for an anonymous %s", async (pathname) => {
    const assetFetch = vi.fn(async () => new Response("not found", { status: 404 }));
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
      new Request("https://leaf.page/examples/triage-board/api/state"),
      env,
    );

    expect(getContainer).not.toHaveBeenCalled();
    expect(response.headers.get("Set-Cookie")).toBeNull();
    expect(response.headers.get("Leaf-Session")).toBe("passive");
    expect(response.headers.get("Leaf-Session-Reference")).toMatch(/^\d{12}$/);
    expect(response.headers.get("Leaf-Release")).toBe(RELEASE);
    const state = await response.json();
    expect(state).toMatchObject({ reading: "published", release: RELEASE });
    expect(state.taken).toBeGreaterThan(0);
  });

  it("keeps an identified but inactive reader on passive edge state", async () => {
    const sessionId = "1a".repeat(16);
    const response = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/api/state", {
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
    expect(response.headers.get("Leaf-Session-Reference")).toBe("698925386266");
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
        "https://leaf.page/examples/triage-board/api/view?revision=2&through_seq=0",
        { headers: { Cookie: `__Host-leaf-page=${sessionId}` } },
      ),
      environment(),
    );

    expect(containerFetch).toHaveBeenCalledOnce();
    expect(response.headers.get("Leaf-Session")).toBe("active");
    expect(response.headers.get("Leaf-Session-Reference")).toBe("610422516507");
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
      new Request("https://leaf.page/examples/triage-board/"),
      env,
    );
    const cookie = document.headers.get("Set-Cookie")!;
    const reference = document.headers.get("Leaf-Session-Reference");
    expect(reference).toMatch(/^\d{12}$/);
    const sessionId = /__Host-leaf-page=([0-9a-f]{32})/.exec(cookie)![1];
    const upload = () =>
      worker.fetch(
        new Request("https://leaf.page/examples/triage-board/api/media", {
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
      expect(response.headers.get("Leaf-Session-Reference")).toBe(reference);
      expect(response.headers.get("Set-Cookie")).toBe(
        "__Host-leaf-active=1; Path=/; Secure; HttpOnly; SameSite=Lax",
      );
    }
  });

  it("serves the requested historical revision from the release manifest", async () => {
    const env = environment();

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/api/state", {
        headers: { "Leaf-View-Revision": "1" },
      }),
      env,
    );

    expect(response.status).toBe(200);
    expect(vi.mocked(env.ASSETS.fetch).mock.calls[1][0].url).toBe(
      "https://leaf.page/_leaf/state/examples--triage-board--r1.json",
    );
    expect(getContainer).not.toHaveBeenCalled();
  });

  it("rejects a historical revision absent from the release manifest", async () => {
    const response = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/api/state", {
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
    ["example", "/examples/triage-board/api/state", "/examples/triage-board/"],
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
      new Request("https://leaf.page/examples/triage-board/api/state", {
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
        new Request("https://leaf.page/examples/triage-board/api/event", {
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
        "/examples/triage-board",
        "example",
        "action",
        "choose",
        RELEASE,
        "663359381809",
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
      CODEX_CA_CERTIFICATE: "/etc/cloudflare/certs/cloudflare-containers-ca.crt",
    });

    const upstream = vi.fn(async () => new Response("ok"));
    vi.stubGlobal("fetch", upstream);
    const handler = containerHandlers.get("LeafWebsiteSession")?.["api.openai.com"];
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
    expect(await response.text()).toBe("website agent credential is not configured");
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
      new Request("https://leaf.page/examples/triage-board/_leaf/agent/start"),
      env,
    );

    expect(response.status).toBe(404);
    expect(getContainer).not.toHaveBeenCalled();
  });

  it.each([
    ["product", "/api/event", "/"],
    ["example", "/examples/triage-board/api/event", "/examples/triage-board"],
  ])(
    "acknowledges an accepted %s-page event before its direct dispatch completes",
    async (_kind, pathname, route) => {
      const sessionId = "01".repeat(16);
      const sessionReference = "911497130241";
      const eventId = "02".repeat(16);
      const attempt = "reader-attempt-01";
      let resolveAgentStart: (response: Response) => void = () => undefined;
      const agentStart = new Promise<Response>((resolve) => {
        resolveAgentStart = resolve;
      });
      const containerFetch = vi.fn(async (request: Request) => {
        if (new URL(request.url).pathname.endsWith("/api/event")) {
          return Response.json({
            ok: true,
            state: {
              events: [{ id: eventId, attempt, kind: "comment", revision: 1 }],
              activity: { obligations: [{ event: eventId }] },
            },
          });
        }
        return agentStart;
      });
      vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
      const waitUntil = vi.fn();
      const env = environment();

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
        { waitUntil } as unknown as ExecutionContext,
      );

      expect(response.status).toBe(200);
      expect(waitUntil).toHaveBeenCalledOnce();
      expect(env.WEBSITE_EVENTS.writeDataPoint).toHaveBeenCalledWith({
        indexes: [eventId],
        blobs: [route, _kind, "comment", null, RELEASE, sessionReference],
        doubles: [1, 1],
      });

      resolveAgentStart(Response.json({ status: "started", thread: "codex-thread" }));
      await waitUntil.mock.calls[0][0];

      const startRequest = containerFetch.mock.calls[1][0];
      expect(await startRequest.json()).toEqual({ event: eventId });
      expect(JSON.stringify([...startRequest.headers])).not.toContain("test-key");
    },
  );

  it("does not dispatch work after Leaf says the accepted event is settled", async () => {
    const sessionId = "06".repeat(16);
    const attempt = "settled-attempt-1";
    vi.mocked(getContainer).mockReturnValue({
      fetch: async () =>
        Response.json({
          ok: true,
          state: {
            events: [{ id: "07".repeat(16), attempt, kind: "comment", revision: 1 }],
            activity: { obligations: [] },
          },
        }),
    } as never);
    const waitUntil = vi.fn();

    await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/api/event", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: `__Host-leaf-page=${sessionId}`,
        },
        body: JSON.stringify({ kind: "comment", attempt }),
      }),
      environment(),
      { waitUntil } as unknown as ExecutionContext,
    );

    expect(waitUntil).not.toHaveBeenCalled();
  });

  it("settles an over-limit direct dispatch visibly", async () => {
    const sessionId = "13".repeat(16);
    const eventId = "14".repeat(16);
    const attempt = "over-limit-attempt";
    const containerFetch = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({
          ok: true,
          state: {
            events: [{ id: eventId, attempt, kind: "comment", revision: 1 }],
            activity: { obligations: [{ event: eventId }] },
          },
        }),
      )
      .mockResolvedValueOnce(
        Response.json({ status: "appended", event: "15".repeat(16) }),
      );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
    const deny = vi.fn(async () => ({ success: false }));
    const waitUntil = vi.fn();

    await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/api/event", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "CF-Connecting-IP": "203.0.113.2",
          Cookie: `__Host-leaf-page=${sessionId}`,
        },
        body: JSON.stringify({ kind: "comment", attempt }),
      }),
      environment({ SOURCE_AGENT_RATE_LIMITER: { limit: deny } as RateLimit }),
      { waitUntil } as unknown as ExecutionContext,
    );
    await waitUntil.mock.calls[0][0];

    expect(deny).toHaveBeenCalledWith({ key: "203.0.113.2" });
    expect(await containerFetch.mock.calls[1][0].json()).toEqual({
      event: eventId,
      text: "This public demo is busy right now. Please wait a minute, then send a new message.",
    });
  });

  it("settles a failed direct startup with a visible failure reply", async () => {
    const sessionId = "08".repeat(16);
    const eventId = "09".repeat(16);
    const attempt = "failed-start-attempt";
    const containerFetch = vi
      .fn()
      .mockResolvedValueOnce(
        Response.json({
          ok: true,
          state: {
            events: [{ id: eventId, attempt, kind: "comment", revision: 1 }],
            activity: { obligations: [{ event: eventId }] },
          },
        }),
      )
      .mockResolvedValueOnce(new Response("unavailable", { status: 503 }))
      .mockResolvedValueOnce(
        Response.json({ status: "appended", event: "10".repeat(16) }),
      );
    vi.mocked(getContainer).mockReturnValue({ fetch: containerFetch } as never);
    const waitUntil = vi.fn();

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/api/event", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: `__Host-leaf-page=${sessionId}`,
        },
        body: JSON.stringify({ kind: "comment", attempt }),
      }),
      environment(),
      { waitUntil } as unknown as ExecutionContext,
    );
    await waitUntil.mock.calls[0][0];

    expect(response.status).toBe(200);
    expect(await containerFetch.mock.calls[2][0].json()).toEqual({
      event: eventId,
      text: "I couldn’t generate a reply just now. Please send a new message to try again.",
    });
  });
});
