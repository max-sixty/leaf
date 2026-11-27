import type { ServedState } from "../../browser/types/contract.js";
import { ReadableStream } from "node:stream/web";
import { describe, expect, it, vi } from "vitest";
import { unpackTar } from "modern-tar";
import { sqliteStorage } from "./sqlite";

const forwardedContainerFetch = vi.hoisted(() =>
  vi.fn(async (_request: Request) => new Response("container")),
);
// The session object an edge request reaches by its name.
const getByName = vi.hoisted(() => vi.fn());

vi.mock("cloudflare:workers", () => ({
  DurableObject: class {
    constructor(
      public ctx: unknown,
      public env: unknown,
    ) {}
  },
  WorkerEntrypoint: class {
    constructor(
      public ctx: unknown,
      public env: unknown,
    ) {}
  },
}));

import worker, { LeafSession, SessionOutbound, type Env } from "../src/index";
import { activeCookie } from "../src/routing";
import { STORE_FORMAT } from "../src/storage";

function executionContext(waitUntil = vi.fn()): ExecutionContext {
  return { waitUntil } as unknown as ExecutionContext;
}

const RELEASE = "a".repeat(64);
const PROTOCOL = 60;
const LAYER = "edge-layer";
const MANIFEST = {
  release: RELEASE,
  protocol: PROTOCOL,
  drafts_format: "leaf-drafts/51",
  frame_ancestors: "frame-ancestors 'self'",
  routes: {
    layer: ["runtime", "widgets", "vendor"],
    session: ["media", "revisions", "versions"],
    files: ["leaf.js", "theme.css", "shadow.css", "registry.json", "icon.svg"],
  },
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
    "/extending": {
      assets: `/_leaf-release/${RELEASE}/extending`,
      description: "The extending leaf page.",
      directory: "_leaf/pages/extending",
      image: "/media/0000000000000005.png",
      kind: "product",
      layer: LAYER,
      state: "/_leaf/state/extending.json",
      states: { "1": "/_leaf/state/extending.json" },
      title: "Extending Leaf",
    },
    "/using": {
      assets: `/_leaf-release/${RELEASE}/using`,
      description: "Working on a Leaf page.",
      directory: "_leaf/pages/using",
      image: "/media/0000000000000006.png",
      kind: "product",
      layer: LAYER,
      state: "/_leaf/state/using.json",
      states: { "1": "/_leaf/state/using.json" },
      title: "Using a Leaf page",
    },
    "/pages": {
      assets: `/_leaf-release/${RELEASE}/pages`,
      description: "Writing a Leaf page.",
      directory: "_leaf/pages/pages",
      image: "/media/0000000000000007.png",
      kind: "product",
      layer: LAYER,
      state: "/_leaf/state/pages.json",
      states: { "1": "/_leaf/state/pages.json" },
      title: "Writing a Leaf page",
    },
  },
};

const startupReport = (overrides: Record<string, unknown> = {}) => ({
  loadId: "123e4567e89b42d3a456426614174000",
  release: RELEASE,
  layer: LAYER,
  outcome: "presented",
  navigationType: "navigate",
  serverMs: 12,
  firstByteMs: 90,
  firstContentfulPaintMs: 115,
  upgradedMs: 180,
  firstStateResponseMs: 280,
  presentedMs: 310,
  ...overrides,
});
const SCOPE = `${PROTOCOL}.${STORE_FORMAT}`;
const activeMarker = (root: string, scope = SCOPE) =>
  activeCookie(true, root, scope).split(";", 1)[0];
const containerId = (sessionId: string) => `${SCOPE}:${sessionId}`;

function environment(overrides: Partial<Env> = {}): Env {
  const allow = { limit: vi.fn(async () => ({ success: true })) } as RateLimit;
  const suppliedAssets = overrides.ASSETS;
  const rest = { ...overrides };
  delete rest.ASSETS;
  delete rest.PAGES;
  const fetch = vi.fn(async (request: Request) => {
    const pathname = new URL(request.url).pathname;
    if (pathname === "/_leaf/site.json") return Response.json(MANIFEST);
    if (pathname.startsWith("/_leaf/state/")) {
      return Response.json({
        reading: "published",
        data: {
          version: "v1",
          sources: { notes: { contract: "text", value: "Published" } },
        },
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
    PAGES: { getByName, ...overrides.PAGES } as unknown as Env["PAGES"],
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

    await expect(
      worker.fetch(new Request("https://leaf.page/"), env, executionContext()),
    ).rejects.toThrow("site manifest returned 503");
    const response = await worker.fetch(
      new Request("https://leaf.page/"),
      env,
      executionContext(),
    );

    expect(response.status).toBe(404);
    expect(env.ASSETS.fetch).toHaveBeenCalledTimes(3);
  });

  it("routes opaque samples to their allocation's exact container without cookies or agent work", async () => {
    const sessionId = "03".repeat(16);
    const sampleId = "04".repeat(16);
    const objectId = "06".repeat(32);
    const allocated = `/examples/triage-board/api/samples/${sampleId}/`;
    const sample = `/examples/triage-board/api/samples/${sampleId}~${objectId}`;
    const id = { toString: () => objectId } as DurableObjectId;
    const allocationFetch = vi.fn(async () =>
      Response.json({ url: allocated, page: `/api/samples/${sampleId}` }),
    );
    getByName.mockReturnValue({ fetch: allocationFetch } as never);
    const containerFetch = vi.fn(async (request: Request) => {
      if (
        request.method === "POST" &&
        new URL(request.url).pathname.endsWith("/api/samples")
      )
        return Response.json(
          {
            url: `${new URL(request.url).pathname}/${"07".repeat(16)}/`,
            page: `/api/samples/${sampleId}~${objectId}/api/samples/${"07".repeat(16)}`,
          },
          {
            headers: { "Access-Control-Allow-Origin": "*" },
          },
        );
      if (request.method === "OPTIONS")
        return new Response(null, {
          status: 204,
          headers: {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
          },
        });
      return Response.json(
        { ok: true },
        {
          headers: {
            "Access-Control-Allow-Origin": "*",
            "Set-Cookie": "parent-cookie-must-not-reach-the-child=1",
          },
        },
      );
    });
    const pages = {
      idFromName: vi.fn(() => id),
      idFromString: vi.fn((_value: string) => id),
      get: vi.fn((_id: DurableObjectId) => ({ fetch: containerFetch })),
    };
    const env = environment({ PAGES: pages as unknown as Env["PAGES"] });
    const waitUntil = vi.fn();
    const ctx = executionContext(waitUntil);
    const allocation = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/api/samples", {
        method: "POST",
        headers: { Cookie: `__Host-leaf-page=${sessionId}` },
        body: JSON.stringify({ template: "practice" }),
      }),
      env,
      ctx,
    );
    // The edge passes on the release a container names, which this one leaves out.
    expect(allocation.headers.get("Leaf-Release")).toBeNull();
    expect(await allocation.json()).toEqual({
      url: `${sample}/`,
      page: `/api/samples/${sampleId}~${objectId}`,
    });
    expect(pages.idFromName).toHaveBeenCalledExactlyOnceWith(containerId(sessionId));

    const paths = [
      ["GET", `${sample}/`],
      ["POST", `${sample}/api/interaction`],
      ["GET", `${sample}/revisions/r1-0123456789abcdef/leaf.js`],
      ["GET", `${sample}/api/state`],
      ["POST", `${sample}/api/event`],
      ["OPTIONS", `${sample}/api/event`],
      ["POST", `${sample}/api/samples`],
      ["GET", `${sample}/api/samples/${"07".repeat(16)}/api/state`],
    ];
    for (const [method, path] of paths) {
      // A different browser's optional cookie must not reassign the capability.
      for (const cookie of [null, `__Host-leaf-page=${"08".repeat(16)}`]) {
        const response = await worker.fetch(
          new Request(`https://leaf.page${path}`, {
            method,
            headers: { Origin: "null", ...(cookie ? { Cookie: cookie } : {}) },
            ...(method === "POST" ? { body: JSON.stringify({ kind: "comment" }) } : {}),
          }),
          env,
          ctx,
        );
        expect(response.status).toBe(method === "OPTIONS" ? 204 : 200);
        expect(response.headers.get("Set-Cookie")).toBeNull();
        expect(response.headers.get("Access-Control-Allow-Origin")).toBe("*");
        // The container names no release, and the edge adds none of its own.
        expect(response.headers.get("Leaf-Release")).toBeNull();
        if (method === "POST" && path.endsWith("/api/samples"))
          expect(await response.json()).toEqual({
            url: `${sample}/api/samples/${"07".repeat(16)}/`,
            page: `/api/samples/${sampleId}~${objectId}/api/samples/${"07".repeat(16)}`,
          });
      }
    }
    expect(allocationFetch).toHaveBeenCalledOnce();
    expect(containerFetch).toHaveBeenCalledTimes(paths.length * 2);
    expect(pages.idFromString).toHaveBeenCalledTimes(paths.length * 2);
    expect(pages.idFromString.mock.calls.every(([value]) => value === objectId)).toBe(
      true,
    );
    expect(pages.get.mock.calls.every(([value]) => value === id)).toBe(true);
    expect(waitUntil).not.toHaveBeenCalled();
    expect(env.WEBSITE_EVENTS.writeDataPoint).not.toHaveBeenCalled();
  });

  it("never treats a routing reference outside a sample prefix as parent session identity", async () => {
    const objectId = "06".repeat(32);
    const pages = { idFromString: vi.fn(), get: vi.fn() };
    const env = environment({ PAGES: pages as unknown as Env["PAGES"] });
    const response = await worker.fetch(
      new Request(
        `https://leaf.page/examples/triage-board/api/state?sample=${"04".repeat(16)}~${objectId}`,
      ),
      env,
      executionContext(),
    );
    expect(response.headers.get("Leaf-Session")).toBe("passive");
    expect(pages.idFromString).not.toHaveBeenCalled();
    expect(pages.get).not.toHaveBeenCalled();
  });

  it("refuses an invalid namespace object ID before starting a sample container", async () => {
    const pages = {
      idFromString: vi.fn(() => {
        throw new TypeError("invalid Durable Object ID");
      }),
      get: vi.fn(),
    };
    const env = environment({ PAGES: pages as unknown as Env["PAGES"] });
    const response = await worker.fetch(
      new Request(
        `https://leaf.page/api/samples/${"04".repeat(16)}~${"06".repeat(32)}/api/state`,
      ),
      env,
      executionContext(),
    );
    expect(response.status).toBe(404);
    expect(response.headers.get("Set-Cookie")).toBeNull();
    expect(pages.get).not.toHaveBeenCalled();
  });

  it.each([
    "/",
    "/how-it-works/",
    "/using/",
    "/examples/",
    "/examples/triage-board/",
    "/extending/",
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
        executionContext(),
      );

      expect(assetFetch).toHaveBeenCalledOnce();
      expect(getByName).not.toHaveBeenCalled();
      expect(response.headers.get("Content-Security-Policy")).toBe(
        MANIFEST.frame_ancestors,
      );
      expect(response.headers.get("Set-Cookie")).toMatch(
        /^__Host-leaf-page=[0-9a-f]{32}; Path=\/; Secure; HttpOnly; SameSite=Lax$/,
      );
      expect(response.headers.get("Leaf-Release")).toBe(RELEASE);
      expect(response.headers.get("Server-Timing")).toMatch(/^leaf;dur=\d+$/);
      expect(await response.text()).toBe("<!doctype html><title>Leaf</title>");
    },
  );

  it("records one content-free browser startup profile without a container", async () => {
    const sessionId = "13".repeat(16);
    const logged = vi.spyOn(console, "log").mockImplementation(() => undefined);
    try {
      const response = await worker.fetch(
        new Request("https://leaf.page/examples/triage-board/api/performance", {
          method: "POST",
          headers: {
            Cookie: `__Host-leaf-page=${sessionId}; ${activeMarker("/examples/triage-board")}`,
            "Content-Type": "text/plain;charset=UTF-8",
          },
          // Widgets can upgrade while the first state response remains pending.
          body: JSON.stringify(
            startupReport({ firstStateResponseMs: 300_001, presentedMs: 300_031 }),
          ),
        }),
        environment(),
        executionContext(),
      );

      expect(response.status).toBe(204);
      expect(getByName).not.toHaveBeenCalled();
      expect(logged).toHaveBeenCalledOnce();
      expect(logged.mock.calls[0][0]).toMatchObject({
        component: "leaf-startup",
        event: "browser_startup",
        reference: "318445474579",
        route: "/examples/triage-board",
        currentRelease: RELEASE,
        presentedMs: 300_031,
        firstContentfulPaintMs: 115,
        upgradedMs: 180,
        firstStateResponseMs: 300_001,
      });
    } finally {
      logged.mockRestore();
    }
  });

  it("records admitted opaque sample batches with joinable cloud identities", async () => {
    const logged = vi.spyOn(console, "log").mockImplementation(() => undefined);
    const sample = `/api/samples/${"04".repeat(16)}~${"06".repeat(32)}`;
    const nested = `${sample}/api/samples/${"07".repeat(16)}`;
    const forwarded: string[] = [];
    // Container admission is the credential boundary; projection remains at the edge.
    const containerFetch = vi.fn(async (request: Request) => {
      forwarded.push(await request.text());
      return new Response(null, {
        status: 204,
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Cache-Control": "no-cache",
          "Set-Cookie": "private-parent-cookie=1",
        },
      });
    });
    const env = environment({
      PAGES: {
        idFromString: vi.fn(() => ({})),
        get: vi.fn(() => ({ fetch: containerFetch })),
      } as unknown as Env["PAGES"],
    });
    const entries = [
      {
        monotonic_ms: 123,
        visibility: "visible",
        observed_at: "2026-10-10T12:00:00.000Z",
        sequence: 1,
        type: "sample",
        phase: "failed",
        sample: nested,
        error: { name: "AuthoredSampleError", status: 503, stack: "stack-secret" },
      },
      {
        monotonic_ms: 123,
        visibility: "visible",
        observed_at: "2026-10-10T12:00:01.000Z",
        sequence: 1,
        type: "click",
        target: ["button#private-secret"],
      },
    ];
    try {
      for (const [index, path] of [sample, nested].entries()) {
        const body = JSON.stringify({
          session: String(index).repeat(32),
          entries: [entries[index]],
        });
        const response = await worker.fetch(
          new Request(
            `https://leaf.page/examples/triage-board${path}/api/interaction`,
            {
              method: "POST",
              headers: { Origin: "null" },
              body,
            },
          ),
          env,
          executionContext(),
        );
        expect(response.status).toBe(204);
        expect(response.headers.get("Access-Control-Allow-Origin")).toBe("*");
        expect(response.headers.get("Set-Cookie")).toBeNull();
        expect(forwarded[index]).toBe(body);
      }
      expect(logged.mock.calls.map((call) => call[0])).toStrictEqual([
        {
          component: "leaf-interaction",
          event: "client_batch",
          route: "/examples/triage-board",
          release: RELEASE,
          sampleReference: "645988520964",
          session: "0".repeat(32),
          entries: [
            {
              monotonic_ms: 123,
              visibility: "visible",
              observed_at: entries[0].observed_at,
              sequence: 1,
              type: "sample",
              phase: "failed",
              sampleReference: "380479911687",
              error: { name: "AuthoredSampleError", status: 503 },
            },
          ],
        },
        {
          component: "leaf-interaction",
          event: "client_batch",
          route: "/examples/triage-board",
          release: RELEASE,
          sampleReference: "380479911687",
          session: "1".repeat(32),
          entries: [
            {
              monotonic_ms: 123,
              visibility: "visible",
              observed_at: entries[1].observed_at,
              sequence: 1,
              type: "click",
              target: ["button"],
            },
          ],
        },
      ]);
      const emitted = JSON.stringify(logged.mock.calls);
      expect(emitted).not.toContain("secret");
      expect(emitted).not.toContain("04".repeat(16));
      expect(emitted).not.toContain("06".repeat(32));
      expect(emitted).not.toContain("07".repeat(16));
      expect(getByName).not.toHaveBeenCalled();
    } finally {
      logged.mockRestore();
    }
  });

  it("does not log refused or invalid opaque sample batches", async () => {
    const logged = vi.spyOn(console, "log").mockImplementation(() => undefined);
    let admittedStatus = 204;
    const containerFetch = vi.fn(async (request: Request) => {
      await request.text();
      return new Response(null, {
        status: admittedStatus,
        headers: { "Access-Control-Allow-Origin": "*" },
      });
    });
    const env = environment({
      PAGES: {
        idFromString: vi.fn(() => ({})),
        get: vi.fn(() => ({ fetch: containerFetch })),
      } as unknown as Env["PAGES"],
    });
    const entry = {
      monotonic_ms: 123,
      visibility: "visible",
      observed_at: "2026-10-10T12:00:00.000Z",
      sequence: 1,
      type: "click",
    };
    const batch = { session: "1".repeat(32), entries: [entry] };
    const cases = [
      { status: 404, body: JSON.stringify(batch), expected: 404 },
      { status: 503, body: JSON.stringify(batch), expected: 503 },
      { status: 204, body: "{", expected: 204 },
      {
        status: 204,
        body: JSON.stringify({ ...batch, entries: [{ type: "click" }] }),
        expected: 204,
      },
      {
        status: 204,
        body: JSON.stringify({ ...batch, entries: Array(101).fill(entry) }),
        expected: 204,
      },
      { status: 204, body: "x".repeat(128 * 1024 + 1), expected: 204 },
    ];
    try {
      for (const item of cases) {
        admittedStatus = item.status;
        const response = await worker.fetch(
          new Request(
            `https://leaf.page/examples/triage-board/api/samples/${"04".repeat(16)}~${"06".repeat(32)}/api/interaction`,
            {
              method: "POST",
              headers: { Origin: "null" },
              body: item.body,
            },
          ),
          env,
          executionContext(),
        );
        expect(response.status).toBe(item.expected);
        expect(response.headers.get("Access-Control-Allow-Origin")).toBe("*");
        expect(response.headers.get("Set-Cookie")).toBeNull();
      }
      expect(logged).not.toHaveBeenCalled();
      expect(containerFetch).toHaveBeenCalledTimes(cases.length);
    } finally {
      logged.mockRestore();
    }
  });

  it("retains safe sample lifecycle evidence in edge interaction batches", async () => {
    const logged = vi.spyOn(console, "log").mockImplementation(() => undefined);
    const sample = `/api/samples/${"04".repeat(16)}~${"06".repeat(32)}`;
    const entries = [
      {
        monotonic_ms: 123,
        visibility: "visible",
        observed_at: "2026-10-10T12:00:00.000Z",
        sequence: 1,
        type: "sample",
        phase: "admission",
        host: 2,
        allocation: 3,
        revision: 4,
        elapsed: 23.5,
        sample,
        document: "12345678-1234-4234-8234-123456789abc",
        template: "private-template-secret",
        status: 200,
        leafDocument: "4",
      },
      {
        monotonic_ms: 123,
        visibility: "visible",
        observed_at: "2026-10-10T12:00:01.000Z",
        sequence: 2,
        type: "sample",
        phase: "failed",
        host: 2,
        allocation: 3,
        revision: 4,
        elapsed: 99,
        sample,
        document: "12345678-1234-4234-8234-123456789abc",
        operation: "release",
        reason: "reset",
        reloading: true,
        error: {
          name: "TypeError",
          status: 503,
          message: "message-secret",
          stack: "stack-secret",
          body: "body-secret",
        },
      },
      {
        monotonic_ms: 123,
        visibility: "visible",
        observed_at: "2026-10-10T12:00:02.000Z",
        sequence: 3,
        type: "sample",
        phase: "retired",
        host: 2,
        allocation: 3,
        revision: 4,
        elapsed: 101,
        sample: `/api/samples/${"04".repeat(16)}`,
        document: null,
        reason: "destroyed",
        leafDocument: null,
      },
      {
        monotonic_ms: 123,
        visibility: "visible",
        observed_at: "2026-10-10T12:00:03.000Z",
        sequence: 4,
        type: "sample",
        phase: "phase secret",
        host: -1,
        allocation: Infinity,
        revision: "4",
        elapsed: -1,
        sample: "/?token=capability-secret",
        document: "document-secret",
        leafDocument: "header-secret",
        reason: "reason secret",
        operation: "operation secret",
        error: { name: "name-secret", status: "503", message: "message-secret" },
      },
      {
        monotonic_ms: 123,
        visibility: "visible",
        observed_at: "2026-10-10T12:00:04.000Z",
        sequence: 5,
        type: "sample",
        phase: "recovering",
        reason: "parent_left",
        operation: "retry-start",
        error: { name: "QuotaExceededError" },
      },
      {
        monotonic_ms: 123,
        visibility: "visible",
        observed_at: "2026-10-10T12:00:05.000Z",
        sequence: 6,
        type: "sample",
        phase: "retrying",
        sample: `${sample}/api/samples/${"07".repeat(16)}`,
        error: { name: "AuthoredSampleError" },
      },
    ];
    try {
      const response = await worker.fetch(
        new Request("https://leaf.page/examples/triage-board/api/interaction", {
          method: "POST",
          headers: { Cookie: `__Host-leaf-page=${"17".repeat(16)}` },
          body: JSON.stringify({ session: "a".repeat(32), entries }),
        }),
        environment(),
        executionContext(),
      );
      expect(response.status).toBe(204);
      const batch = logged.mock.calls[0][0] as { entries: unknown[] };
      expect(batch.entries).toStrictEqual([
        {
          monotonic_ms: 123,
          visibility: "visible",
          observed_at: entries[0].observed_at,
          sequence: 1,
          type: "sample",
          phase: "admission",
          host: 2,
          allocation: 3,
          revision: 4,
          elapsed: 23.5,
          sampleReference: "645988520964",
          documentReference: "706379782844",
          status: 200,
          leafDocument: 4,
        },
        {
          monotonic_ms: 123,
          visibility: "visible",
          observed_at: entries[1].observed_at,
          sequence: 2,
          type: "sample",
          phase: "failed",
          host: 2,
          allocation: 3,
          revision: 4,
          elapsed: 99,
          sampleReference: "645988520964",
          documentReference: "706379782844",
          operation: "release",
          reason: "reset",
          reloading: true,
          error: { name: "TypeError", status: 503 },
        },
        {
          monotonic_ms: 123,
          visibility: "visible",
          observed_at: entries[2].observed_at,
          sequence: 3,
          type: "sample",
          phase: "retired",
          host: 2,
          allocation: 3,
          revision: 4,
          elapsed: 101,
          sampleReference: "645988520964",
          documentReference: null,
          reason: "destroyed",
          leafDocument: null,
        },
        {
          monotonic_ms: 123,
          visibility: "visible",
          observed_at: entries[3].observed_at,
          sequence: 4,
          type: "sample",
        },
        {
          monotonic_ms: 123,
          visibility: "visible",
          observed_at: entries[4].observed_at,
          sequence: 5,
          type: "sample",
          phase: "recovering",
          reason: "parent_left",
          operation: "retry-start",
          error: { name: "QuotaExceededError" },
        },
        {
          monotonic_ms: 123,
          visibility: "visible",
          observed_at: entries[5].observed_at,
          sequence: 6,
          type: "sample",
          phase: "retrying",
          sampleReference: "380479911687",
          error: { name: "AuthoredSampleError" },
        },
      ]);
      const emitted = JSON.stringify(logged.mock.calls[0][0]);
      expect(emitted).not.toContain("secret");
      expect(emitted).not.toContain("04".repeat(16));
      expect(emitted).not.toContain("06".repeat(32));
      expect(getByName).not.toHaveBeenCalled();
    } finally {
      logged.mockRestore();
    }
  });

  it("records bounded client interaction batches at the edge", async () => {
    const sessionId = "17".repeat(16);
    const logged = vi.spyOn(console, "log").mockImplementation(() => undefined);
    const env = environment();
    const url = "https://leaf.page/examples/triage-board/api/interaction";
    const headers = { Cookie: `__Host-leaf-page=${sessionId}` };
    const batch = {
      session: "a".repeat(32),
      entries: [
        {
          monotonic_ms: 123,
          visibility: "visible",
          observed_at: "2026-09-25T12:00:00.000Z",
          sequence: 1,
          type: "click",
          target: ["button#save", "div"],
          nodes: [12, 3],
          control: "button#save",
          controlNode: 12,
          pointer: { x: 12, y: 24, button: 0, secret: "pointer-secret" },
        },
        {
          monotonic_ms: 123,
          visibility: "visible",
          observed_at: "2026-09-25T12:00:01.000Z",
          sequence: 2,
          type: "input",
          target: ['input[name="private-token"]:nth-of-type(2)'],
          key: "s",
          code: "KeyS",
          location: "/?token=location-secret#fragment-secret",
          path: "/secret-path",
          value: "value-secret",
          data: "data-secret",
          selection: "selection-secret",
          clipboard: "clipboard-secret",
          label: "label-secret",
          error: "error-secret",
          json: "json-secret",
          arbitrarySecret: "arbitrary-secret",
        },
        {
          monotonic_ms: 123,
          visibility: "visible",
          observed_at: "2026-09-25T12:00:02.000Z",
          sequence: 3,
          type: "command",
          id: "navigation.back",
          binding: "Mod+ArrowLeft",
          label: "command-secret",
        },
        {
          monotonic_ms: 123,
          visibility: "visible",
          observed_at: "2026-09-25T12:00:03.000Z",
          sequence: 4,
          type: "event_response",
          kind: "action",
          status: 200,
          attempt: "attempt-secret",
          error: "response-secret",
        },
        {
          monotonic_ms: 123,
          visibility: "visible",
          observed_at: "2026-09-25T12:00:04.000Z",
          sequence: 5,
          type: "interaction_omitted",
          originalType: "input",
          bytes: 50_200,
          reason: "record_exceeds_limit",
          json: "part-secret",
        },
        {
          monotonic_ms: 234,
          visibility: "visible",
          observed_at: "2026-09-25T12:00:05.000Z",
          sequence: 6,
          type: "reply_visible",
          input_id: "abcdef01",
          reply_id: "12345678",
          attempt: "b".repeat(32),
          presentation_kind: "message_words",
          reply_kind: "failure",
          surface: "panel",
          text: "reply-secret",
          targetId: "authored-secret",
        },
      ],
    };
    try {
      const accepted = await worker.fetch(
        new Request(url, { method: "POST", headers, body: JSON.stringify(batch) }),
        env,
        executionContext(),
      );
      expect(accepted.status).toBe(204);
      expect(logged).toHaveBeenCalledOnce();
      expect(logged.mock.calls[0][0]).toStrictEqual({
        component: "leaf-interaction",
        event: "client_batch",
        reference: "964433995543",
        route: "/examples/triage-board",
        release: RELEASE,
        session: "a".repeat(32),
        entries: [
          {
            monotonic_ms: 123,
            visibility: "visible",
            observed_at: "2026-09-25T12:00:00.000Z",
            sequence: 1,
            type: "click",
            target: ["button", "div"],
            nodes: [12, 3],
            control: "button",
            controlNode: 12,
            pointer: { x: 12, y: 24, button: 0 },
          },
          {
            monotonic_ms: 123,
            visibility: "visible",
            observed_at: "2026-09-25T12:00:01.000Z",
            sequence: 2,
            type: "input",
            target: ["input:nth-of-type(2)"],
          },
          {
            monotonic_ms: 123,
            visibility: "visible",
            observed_at: "2026-09-25T12:00:02.000Z",
            sequence: 3,
            type: "command",
            id: "navigation.back",
            binding: "Mod+ArrowLeft",
          },
          {
            monotonic_ms: 123,
            visibility: "visible",
            observed_at: "2026-09-25T12:00:03.000Z",
            sequence: 4,
            type: "event_response",
            kind: "action",
            status: 200,
          },
          {
            monotonic_ms: 123,
            visibility: "visible",
            observed_at: "2026-09-25T12:00:04.000Z",
            sequence: 5,
            type: "interaction_omitted",
            originalType: "input",
            bytes: 50_200,
            reason: "record_exceeds_limit",
          },
          {
            monotonic_ms: 234,
            visibility: "visible",
            observed_at: "2026-09-25T12:00:05.000Z",
            sequence: 6,
            type: "reply_visible",
            input_id: "abcdef01",
            reply_id: "12345678",
            attempt: "b".repeat(32),
            presentation_kind: "message_words",
            reply_kind: "failure",
            surface: "panel",
          },
        ],
      });
      expect(JSON.stringify(logged.mock.calls[0][0])).not.toContain("secret");
      expect(getByName).not.toHaveBeenCalled();

      const invalid = await worker.fetch(
        new Request(url, {
          method: "POST",
          headers,
          body: JSON.stringify({ ...batch, entries: [{ type: "click" }] }),
        }),
        env,
        executionContext(),
      );
      const unbound = await worker.fetch(
        new Request(url, { method: "POST", body: JSON.stringify(batch) }),
        env,
        executionContext(),
      );
      const oversized = await worker.fetch(
        new Request(url, {
          method: "POST",
          headers,
          body: "x".repeat(128 * 1024 + 1),
        }),
        env,
        executionContext(),
      );
      const tooMany = await worker.fetch(
        new Request(url, {
          method: "POST",
          headers,
          body: JSON.stringify({
            ...batch,
            entries: Array(101).fill(batch.entries[0]),
          }),
        }),
        env,
        executionContext(),
      );
      expect(invalid.status).toBe(400);
      expect(unbound.status).toBe(400);
      expect(oversized.status).toBe(413);
      expect(tooMany.status).toBe(400);
      expect(logged).toHaveBeenCalledOnce();
      expect(getByName).not.toHaveBeenCalled();
    } finally {
      logged.mockRestore();
    }
  });

  it("has the session's container compose the page when the visitor focuses a text box", async () => {
    const sessionId = "17".repeat(16);
    const logged = vi.spyOn(console, "log").mockImplementation(() => undefined);
    const env = environment();
    const fetched = vi.fn(
      async (_request: Request) => new Response(null, { status: 204 }),
    );
    getByName.mockClear().mockReturnValue({ fetch: fetched } as never);
    const pending: Promise<unknown>[] = [];
    const focused = (control: string, textBox?: true) =>
      worker.fetch(
        new Request("https://leaf.page/examples/triage-board/api/interaction", {
          method: "POST",
          headers: { Cookie: `__Host-leaf-page=${sessionId}` },
          body: JSON.stringify({
            session: "a".repeat(32),
            entries: [
              {
                monotonic_ms: 1,
                visibility: "visible",
                observed_at: "2026-11-10T12:00:00.000Z",
                sequence: 1,
                type: "focusin",
                target: [control],
                control,
                textBox,
              },
            ],
          }),
        }),
        env,
        executionContext(vi.fn((promise: Promise<unknown>) => pending.push(promise))),
      );
    try {
      expect((await focused("button")).status).toBe(204);
      expect(pending).toHaveLength(0);
      expect((await focused("leaf-text", true)).status).toBe(204);
      await Promise.all(pending);
      expect(getByName).toHaveBeenCalledExactlyOnceWith(containerId(sessionId));
      expect(fetched).toHaveBeenCalledOnce();
      const [request] = fetched.mock.calls[0]!;
      expect(request.method).toBe("POST");
      expect(request.url).toBe(
        "http://container/examples/triage-board/_leaf/agent/prewarm",
      );
      expect(logged).toHaveBeenCalledWith(
        expect.objectContaining({ event: "container_prewarm_completed" }),
      );
    } finally {
      getByName.mockClear();
      logged.mockRestore();
    }
  });

  it("keeps what a failed start says it could not load, and bounds it", async () => {
    const sessionId = "15".repeat(16);
    const logged = vi.spyOn(console, "log").mockImplementation(() => undefined);
    try {
      const named = await worker.fetch(
        new Request("https://leaf.page/api/performance", {
          method: "POST",
          headers: { Cookie: `__Host-leaf-page=${sessionId}` },
          body: JSON.stringify(
            startupReport({
              outcome: "failed",
              upgradedMs: null,
              firstStateResponseMs: null,
              presentedMs: null,
              reason: "entry module did not load",
            }),
          ),
        }),
        environment(),
        executionContext(),
      );
      const overlong = await worker.fetch(
        new Request("https://leaf.page/api/performance", {
          method: "POST",
          headers: { Cookie: `__Host-leaf-page=${sessionId}` },
          body: JSON.stringify(
            startupReport({ outcome: "failed", reason: "x".repeat(301) }),
          ),
        }),
        environment(),
        executionContext(),
      );

      expect(named.status).toBe(204);
      expect(overlong.status).toBe(400);
      expect(logged).toHaveBeenCalledOnce();
      expect(logged.mock.calls[0][0]).toMatchObject({
        component: "leaf-startup",
        outcome: "failed",
        upgradedMs: null,
        firstStateResponseMs: null,
        reason: "entry module did not load",
      });
    } finally {
      logged.mockRestore();
    }
  });

  it("refuses unbound, oversized or non-canonical startup reports", async () => {
    const logged = vi.spyOn(console, "log").mockImplementation(() => undefined);
    try {
      const unbound = await worker.fetch(
        new Request("https://leaf.page/api/performance", {
          method: "POST",
          body: JSON.stringify(startupReport()),
        }),
        environment(),
        executionContext(),
      );
      const privateField = await worker.fetch(
        new Request("https://leaf.page/api/performance", {
          method: "POST",
          headers: { Cookie: `__Host-leaf-page=${"14".repeat(16)}` },
          body: JSON.stringify(startupReport({ private: "user content" })),
        }),
        environment(),
        executionContext(),
      );
      // A constructed Request declares no Content-Length, so the body's streamed bytes
      // bound it: 1,025 two-byte characters are over 2,048 bytes.
      const oversized = await worker.fetch(
        new Request("https://leaf.page/api/performance", {
          method: "POST",
          headers: { Cookie: `__Host-leaf-page=${"14".repeat(16)}` },
          body: "é".repeat(1025),
        }),
        environment(),
        executionContext(),
      );

      expect(unbound.status).toBe(400);
      expect(privateField.status).toBe(400);
      expect(oversized.status).toBe(413);
      expect(logged).not.toHaveBeenCalled();
      expect(getByName).not.toHaveBeenCalled();
    } finally {
      logged.mockRestore();
    }
  });

  it("requires nullable nonnegative integer upgrade and first-state response timings", async () => {
    const logged = vi.spyOn(console, "log").mockImplementation(() => undefined);
    try {
      for (const field of ["upgradedMs", "firstStateResponseMs"]) {
        for (const value of [undefined, -1, 1.5, "310"]) {
          const response = await worker.fetch(
            new Request("https://leaf.page/api/performance", {
              method: "POST",
              headers: { Cookie: `__Host-leaf-page=${"14".repeat(16)}` },
              body: JSON.stringify(startupReport({ [field]: value })),
            }),
            environment(),
            executionContext(),
          );
          expect(response.status).toBe(400);
        }
      }
      expect(logged).not.toHaveBeenCalled();
      expect(getByName).not.toHaveBeenCalled();
    } finally {
      logged.mockRestore();
    }
  });

  it("selects private state by the page protocol, across releases", async () => {
    const sessionId = "0b".repeat(16);
    const containerFetch = vi.fn(async (_request: Request) =>
      Response.json(
        { reading: "private" },
        { headers: { "Leaf-Layer": LAYER, "Leaf-Session": "active" } },
      ),
    );
    getByName.mockReturnValue({ fetch: containerFetch } as never);
    const env = environment();

    const response = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/api/state", {
        headers: {
          Cookie: `__Host-leaf-page=${sessionId}; ${activeMarker("/examples/triage-board")}`,
          "Leaf-Layer": LAYER,
          "Leaf-Release": RELEASE,
        },
      }),
      env,
      executionContext(),
    );

    expect(getByName).toHaveBeenCalledWith(containerId(sessionId));
    expect(await response.json()).toMatchObject({ reading: "private" });
    expect(response.headers.get("Set-Cookie")).toBeNull();
  });

  // A container names the release its image runs, which a deploy can leave behind the
  // edge's while the container keeps serving its tab (`LeafSession`), so the edge
  // passes the container's own release on rather than its own.
  it.each([
    ["a state read", "GET", "api/state"],
    ["a gesture", "POST", "api/event"],
  ])(
    "keeps the release of the container that answers %s",
    async (_, method, inside) => {
      const sessionId = "0d".repeat(16);
      const containerReleases: Record<string, string>[] = [
        {},
        { "Leaf-Release": "b".repeat(64) },
      ];
      for (const named of containerReleases) {
        const containerFetch = vi.fn(async (_request: Request) =>
          Response.json(
            { reading: "private" },
            { headers: { "Leaf-Layer": LAYER, ...named } },
          ),
        );
        getByName.mockReturnValue({ fetch: containerFetch } as never);

        const response = await worker.fetch(
          new Request(`https://leaf.page/examples/triage-board/${inside}`, {
            method,
            headers: {
              Cookie: `__Host-leaf-page=${sessionId}; ${activeMarker("/examples/triage-board")}`,
              "Content-Type": "application/json",
              "Leaf-Layer": LAYER,
              "Leaf-Release": RELEASE,
            },
            ...(method === "POST" && { body: JSON.stringify({ kind: "comment" }) }),
          }),
          environment(),
          executionContext(),
        );

        expect(containerFetch).toHaveBeenCalledOnce();
        expect(response.status).toBe(200);
        expect(response.headers.get("Leaf-Release")).toBe(
          named["Leaf-Release"] ?? null,
        );
      }
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
      new Request("https://leaf.page/examples/triage-board/runtime/host/state-feed.js"),
      env,
      executionContext(),
    );

    expect(await response.text()).toBe("export {};");
    expect(response.headers.get("Leaf-Release")).toBe(RELEASE);
    expect(assetFetch).toHaveBeenCalledOnce();
    expect(getByName).not.toHaveBeenCalled();
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
      executionContext(),
    );

    expect(response.headers.get("Set-Cookie")).toMatch(
      /^__Host-leaf-page=[0-9a-f]{32}; Path=\/; Secure; HttpOnly; SameSite=Lax$/,
    );
    expect(getByName).not.toHaveBeenCalled();
  });

  it("maps a release-addressed module graph to immutable edge assets", async () => {
    const assetFetch = vi.fn(
      async (_request: Request) =>
        new Response("export {};", {
          headers: { "Content-Type": "application/javascript" },
        }),
    );
    const env = environment({
      ASSETS: { fetch: assetFetch } as unknown as Fetcher,
    });

    const response = await worker.fetch(
      new Request(
        `https://leaf.page/_leaf-release/${RELEASE}/examples--triage-board/runtime/host/state-feed.js`,
      ),
      env,
      executionContext(),
    );

    expect(assetFetch.mock.calls[0][0].url).toBe(
      "https://leaf.page/examples/triage-board/runtime/host/state-feed.js",
    );
    expect(response.headers.get("Access-Control-Allow-Origin")).toBe("*");
    expect(response.headers.get("Access-Control-Expose-Headers")).toBe("*");
    expect(response.headers.get("Cache-Control")).toBe(
      "public, max-age=31536000, immutable",
    );
    expect(response.headers.get("Leaf-Release")).toBe(RELEASE);
    const preflight = await worker.fetch(
      new Request(
        `https://leaf.page/_leaf-release/${RELEASE}/examples--triage-board/runtime/host/state-feed.js`,
        {
          method: "OPTIONS",
          headers: { Origin: "null", "Access-Control-Request-Headers": "leaf-layer" },
        },
      ),
      env,
      executionContext(),
    );
    expect(preflight.status).toBe(204);
    expect(preflight.headers.get("Access-Control-Allow-Origin")).toBe("*");
    expect(preflight.headers.get("Access-Control-Allow-Methods")).toBe(
      "GET, HEAD, OPTIONS",
    );
    expect(preflight.headers.get("Access-Control-Allow-Headers")).toBe("*");
    expect(assetFetch).toHaveBeenCalledOnce();
    expect(getByName).not.toHaveBeenCalled();
  });

  it("serves a browser navigation without starting a container", async () => {
    const waitUntil = vi.fn();
    const response = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/", {
        headers: { "Sec-Fetch-Dest": "document" },
      }),
      environment({
        ASSETS: {
          fetch: async () =>
            new Response("<title>Leaf</title>", {
              headers: { "Content-Type": "text/html" },
            }),
        } as unknown as Fetcher,
      }),
      executionContext(waitUntil),
    );
    expect(response.headers.get("Set-Cookie")).toContain("__Host-leaf-page=");
    expect(getByName).not.toHaveBeenCalled();
    expect(waitUntil).not.toHaveBeenCalled();
  });

  it("does not prewarm an HTML probe that is not a browser navigation", async () => {
    const env = environment({
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
      executionContext(waitUntil),
    );

    expect(response.status).toBe(200);
    expect(getByName).not.toHaveBeenCalled();
    expect(waitUntil).not.toHaveBeenCalled();
  });

  it.each(["/media/upload.png", "/examples/triage-board/media/upload.png"])(
    "falls back to the user's container for uploaded media at %s",
    async (pathname) => {
      const sessionId = "08".repeat(16);
      const assetFetch = vi.fn(async () => new Response("not found", { status: 404 }));
      const containerFetch = vi.fn(
        async () =>
          new Response(new Uint8Array([1, 2, 3]), {
            headers: { "Content-Type": "image/png" },
          }),
      );
      getByName.mockReturnValue({ fetch: containerFetch } as never);
      const env = environment({
        ASSETS: { fetch: assetFetch } as unknown as Fetcher,
      });

      const response = await worker.fetch(
        new Request(`https://leaf.page${pathname}`, {
          headers: {
            Cookie: `__Host-leaf-page=${sessionId}; ${activeMarker(pathname.startsWith("/examples/") ? "/examples/triage-board" : "/")}`,
          },
        }),
        env,
        executionContext(),
      );

      expect(assetFetch).toHaveBeenCalledOnce();
      expect(getByName).toHaveBeenCalledWith(containerId(sessionId));
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
      executionContext(),
    );

    expect(new Uint8Array(await response.arrayBuffer())).toEqual(
      new Uint8Array([4, 5, 6]),
    );
    expect(assetFetch).toHaveBeenCalledOnce();
    expect(getByName).not.toHaveBeenCalled();
  });

  it.each([
    // A revision is named by its content, so a published copy is the same file; only a
    // revision the release didn't publish reaches the container.
    ["/examples/triage-board/revisions/r3-aabbccdd.html", 1],
    // A version is named by its number, and a record an earlier release saved holds
    // its own: the release's published version of that number may be another page.
    ["/examples/triage-board/versions/v3.html", 0],
  ])("serves an active page's %s from its own record", async (pathname, published) => {
    const sessionId = "18".repeat(16);
    const assetFetch = vi.fn(async () => new Response("not found", { status: 404 }));
    const containerFetch = vi.fn(
      async () =>
        new Response("<!doctype html><title>Private revision</title>", {
          headers: { "Content-Type": "text/html; charset=utf-8" },
        }),
    );
    getByName.mockReturnValue({ fetch: containerFetch } as never);
    const env = environment({
      ASSETS: { fetch: assetFetch } as unknown as Fetcher,
    });

    const response = await worker.fetch(
      new Request(`https://leaf.page${pathname}`, {
        headers: {
          Cookie: `__Host-leaf-page=${sessionId}; ${activeMarker("/examples/triage-board")}`,
        },
      }),
      env,
      executionContext(),
    );

    expect(assetFetch).toHaveBeenCalledTimes(published);
    expect(getByName).toHaveBeenCalledWith(containerId(sessionId));
    expect(containerFetch).toHaveBeenCalledOnce();
    expect(await response.text()).toContain("Private revision");
  });

  it("loads an active page's private document on every navigation", async () => {
    const sessionId = "19".repeat(16);
    const assetFetch = vi.fn(
      async (_request: Request) =>
        new Response("<!doctype html><title>Built</title>", {
          headers: { "Content-Type": "text/html; charset=utf-8" },
        }),
    );
    const containerFetch = vi.fn(
      async () =>
        new Response("<!doctype html><title>Published revision</title>", {
          headers: { "Content-Type": "text/html; charset=utf-8" },
        }),
    );
    getByName.mockReturnValue({ fetch: containerFetch } as never);
    const env = environment({
      ASSETS: { fetch: assetFetch } as unknown as Fetcher,
    });

    const headers = {
      Cookie: `__Host-leaf-page=${sessionId}; ${activeMarker("/examples/triage-board")}`,
    };
    const ordinary = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/", { headers }),
      env,
      executionContext(),
    );
    const neighbor = await worker.fetch(
      new Request("https://leaf.page/how-it-works/", { headers }),
      env,
      executionContext(),
    );
    const marked = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/?_leaf-revision=2", {
        headers,
      }),
      env,
      executionContext(),
    );
    // Runtime reload markers do not change which private record owns the document.
    const recovered = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/?_leaf-recovered=", {
        headers,
      }),
      env,
      executionContext(),
    );

    expect(await ordinary.text()).toContain("Published revision");
    expect(await neighbor.text()).toContain("Built");
    expect(await marked.text()).toContain("Published revision");
    expect(await recovered.text()).toContain("Published revision");
    expect(assetFetch).toHaveBeenCalledOnce();
    expect(getByName).toHaveBeenCalledTimes(3);
    expect(getByName).toHaveBeenCalledWith(containerId(sessionId));
    expect(containerFetch).toHaveBeenCalledTimes(3);
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
      executionContext(),
    );

    expect(response.status).toBe(404);
    expect(assetFetch).toHaveBeenCalledOnce();
    expect(getByName).not.toHaveBeenCalled();
    expect(response.headers.get("Set-Cookie")).toBeNull();
  });

  it.each([null, "v1", "stale"])(
    "serves fresh initial state while reusing only matching data (%s)",
    async (version) => {
      const env = environment();

      const response = await worker.fetch(
        new Request("https://leaf.page/examples/triage-board/api/state", {
          headers: version ? { "Leaf-Data-Version": version } : {},
        }),
        env,
        executionContext(),
      );

      expect(getByName).not.toHaveBeenCalled();
      expect(response.headers.get("Set-Cookie")).toBeNull();
      expect(response.headers.get("Leaf-Session")).toBe("passive");
      // A stored answer serves only a request naming the same data version.
      expect(response.headers.get("Cache-Control")).toBe("no-cache");
      expect(response.headers.get("Vary")).toBe(
        "Leaf-Data-Version, Leaf-View-Revision",
      );
      expect(response.headers.get("Leaf-Session-Reference")).toMatch(/^\d{12}$/);
      expect(response.headers.get("Leaf-Release")).toBe(RELEASE);
      const state = await response.json<Pick<ServedState, "taken" | "now" | "data">>();
      expect(state).toMatchObject({ reading: "published", release: RELEASE });
      expect(state.taken).toBeGreaterThan(0);
      expect(state.now).not.toBe("2000-01-01T00:00:00Z");
      expect(state.data).toEqual(
        version === "v1"
          ? { version: "v1" }
          : {
              version: "v1",
              sources: { notes: { contract: "text", value: "Published" } },
            },
      );
    },
  );

  it("keeps an identified but inactive user on passive edge state", async () => {
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
      executionContext(),
    );

    expect(response.headers.get("Leaf-Session")).toBe("passive");
    expect(response.headers.get("Leaf-Session-Reference")).toBe("698925386266");
    // The edge names the deployed release whatever a container is running, so a
    // user asking after a release learns nothing about one from this answer.
    expect(response.headers.get("Leaf-Release")).toBe(RELEASE);
    expect(getByName).not.toHaveBeenCalled();
  });

  it("keeps a page made active at an earlier page protocol or store format passive", async () => {
    const sessionId = "1c".repeat(16);
    const cookie = `__Host-leaf-page=${sessionId}; ${activeMarker("/examples/triage-board", `${PROTOCOL - 1}.${STORE_FORMAT}`)}`;
    const env = environment({
      ASSETS: {
        fetch: async () =>
          new Response("<!doctype html><title>New published release</title>", {
            headers: { "Content-Type": "text/html; charset=utf-8" },
          }),
      } as unknown as Fetcher,
    });
    const document = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/", {
        headers: { Cookie: cookie },
      }),
      env,
      executionContext(),
    );
    expect(await document.text()).toContain("New published release");
    expect(document.headers.get("Leaf-Release")).toBe(RELEASE);
    const state = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/api/state", {
        headers: { Cookie: cookie },
      }),
      env,
      executionContext(),
    );
    expect(state.headers.get("Leaf-Session")).toBe("passive");
    expect(await state.json()).toMatchObject({
      reading: "published",
      release: RELEASE,
    });
    expect(getByName).not.toHaveBeenCalled();
  });

  it("keeps optional geometry reports passive until their page is active", async () => {
    const sessionId = "1d".repeat(16);
    const env = environment();
    const containerFetch = vi.fn(
      async (_request: Request) => new Response(null, { status: 204 }),
    );
    getByName.mockReturnValue({ fetch: containerFetch } as never);
    const report = (cookie?: string) =>
      worker.fetch(
        new Request("https://leaf.page/examples/triage-board/api/user-view", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(cookie ? { Cookie: cookie } : {}),
          },
          body: "{}",
        }),
        env,
        executionContext(),
      );
    for (const cookie of [
      undefined,
      `__Host-leaf-page=${sessionId}`,
      `__Host-leaf-page=${sessionId}; ${activeMarker("/examples/triage-board", `${PROTOCOL - 1}.${STORE_FORMAT}`)}`,
      `__Host-leaf-page=${sessionId}; ${activeMarker("/")}`,
    ]) {
      const response = await report(cookie);
      expect(response.status).toBe(204);
      expect(response.headers.get("Leaf-Session")).not.toBe("active");
      expect(response.headers.get("Set-Cookie")).toBeNull();
    }
    expect(getByName).not.toHaveBeenCalled();
    expect(containerFetch).not.toHaveBeenCalled();

    const active = await report(
      `__Host-leaf-page=${sessionId}; ${activeMarker("/examples/triage-board")}`,
    );
    expect(active.status).toBe(204);
    expect(active.headers.get("Set-Cookie")).toBeNull();
    expect(getByName).toHaveBeenCalledWith(containerId(sessionId));
    expect(containerFetch).toHaveBeenCalledOnce();
  });

  it("answers reads unrecorded until their page is active", async () => {
    const sessionId = "1e".repeat(16);
    const attempt = "read-attempt-0001";
    const env = environment();
    const containerFetch = vi.fn(async (_request: Request) =>
      Response.json({
        ok: true,
        event: { id: "1f".repeat(16), attempt, kind: "read", revision: 1 },
        needs_reply: false,
        state: { events: [], activity: { obligations: [] } },
      }),
    );
    getByName.mockReturnValue({ fetch: containerFetch } as never);
    const read = (cookie?: string) =>
      worker.fetch(
        new Request("https://leaf.page/examples/triage-board/api/event", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            ...(cookie ? { Cookie: cookie } : {}),
          },
          body: JSON.stringify({
            kind: "read",
            attempt,
            messages: [{ message: "reply-1", version: "v1" }],
          }),
        }),
        env,
        executionContext(),
      );
    for (const cookie of [
      undefined,
      `__Host-leaf-page=${sessionId}`,
      `__Host-leaf-page=${sessionId}; ${activeMarker("/examples/triage-board", `${PROTOCOL - 1}.${STORE_FORMAT}`)}`,
      `__Host-leaf-page=${sessionId}; ${activeMarker("/")}`,
    ]) {
      const response = await read(cookie);
      // A final refusal, so the tab doesn't send these reads again this visit.
      expect(response.status).toBe(200);
      expect(await response.json()).toEqual({
        ok: false,
        final: true,
        error: expect.any(String),
        findings: [],
        attempt,
      });
      expect(response.headers.get("Leaf-Session")).toBe("passive");
      expect(response.headers.get("Set-Cookie")).toBeNull();
    }
    expect(getByName).not.toHaveBeenCalled();

    const active = await read(
      `__Host-leaf-page=${sessionId}; ${activeMarker("/examples/triage-board")}`,
    );
    expect(active.status).toBe(200);
    expect(getByName).toHaveBeenCalledWith(containerId(sessionId));
    expect(containerFetch).toHaveBeenCalledOnce();
  });

  it("activates a container for a private read the edge cannot answer", async () => {
    const sessionId = "1b".repeat(16);
    const containerFetch = vi.fn(async (_request: Request) =>
      Response.json(
        { browser: { basis: { through_seq: 0 } } },
        { headers: { "Leaf-Layer": LAYER, "Leaf-Session": "active" } },
      ),
    );
    getByName.mockReturnValue({ fetch: containerFetch } as never);

    const response = await worker.fetch(
      new Request(
        "https://leaf.page/examples/triage-board/api/view?revision=2&through_seq=0",
        { headers: { Cookie: `__Host-leaf-page=${sessionId}` } },
      ),
      environment(),
      executionContext(),
    );

    expect(containerFetch).toHaveBeenCalledOnce();
    expect(response.headers.get("Leaf-Session")).toBe("active");
    expect(response.headers.get("Leaf-Session-Reference")).toBe("610422516507");
    expect(response.headers.get("Set-Cookie")).toBe(
      `__Host-leaf-active-page-examples%2Ftriage-board=${SCOPE}; Path=/; Secure; HttpOnly; SameSite=Lax`,
    );
  });

  it("leaves the reader passive when their container never answered", async () => {
    const sessionId = "1c".repeat(16);
    // The Containers SDK's own failure, as for a container that exited while starting:
    // no answer from Python, so nothing in the container holds the page.
    const containerFetch = vi.fn(
      async (_request: Request) =>
        new Response("Failed to start container", { status: 500 }),
    );
    getByName.mockReturnValue({ fetch: containerFetch } as never);

    const response = await worker.fetch(
      new Request(
        "https://leaf.page/examples/triage-board/api/view?revision=2&through_seq=0",
        { headers: { Cookie: `__Host-leaf-page=${sessionId}` } },
      ),
      environment(),
      executionContext(),
    );

    expect(containerFetch).toHaveBeenCalledOnce();
    expect(response.status).toBe(500);
    expect(response.headers.get("Set-Cookie")).toBeNull();
    expect(response.headers.get("Leaf-Session")).toBeNull();
  });

  it("routes concurrent first uploads through the identity minted by the document", async () => {
    const containerFetch = vi.fn(async (_request: Request) =>
      Response.json(
        { path: "/media/0123456789abcdef.png" },
        { headers: { "Leaf-Layer": LAYER, "Leaf-Session": "active" } },
      ),
    );
    getByName.mockReturnValue({ fetch: containerFetch } as never);
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
      executionContext(),
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
        executionContext(),
      );

    const responses = await Promise.all([upload(), upload()]);

    expect(getByName).toHaveBeenNthCalledWith(1, containerId(sessionId));
    expect(getByName).toHaveBeenNthCalledWith(2, containerId(sessionId));
    expect(containerFetch).toHaveBeenCalledTimes(2);
    for (const response of responses) {
      expect(response.headers.get("Leaf-Session")).toBe("active");
      expect(response.headers.get("Leaf-Session-Reference")).toBe(reference);
      expect(response.headers.get("Set-Cookie")).toBe(
        `__Host-leaf-active-page-examples%2Ftriage-board=${SCOPE}; Path=/; Secure; HttpOnly; SameSite=Lax`,
      );
    }
  });

  it.each([
    ["", { "Leaf-View-Revision": "1" }],
    ["?revision=1", { "Leaf-View-Revision": "2" }],
  ])(
    "serves the requested historical revision from the release manifest: %s",
    async (query, headers) => {
      const env = environment();

      const response = await worker.fetch(
        new Request(`https://leaf.page/examples/triage-board/api/state${query}`, {
          headers,
        }),
        env,
        executionContext(),
      );

      expect(response.status).toBe(200);
      expect(vi.mocked(env.ASSETS.fetch).mock.calls[1][0]).toMatchObject({
        url: "https://leaf.page/_leaf/state/examples--triage-board--r1.json",
      });
      expect(getByName).not.toHaveBeenCalled();
    },
  );

  it("rejects a historical revision absent from the release manifest", async () => {
    const response = await worker.fetch(
      new Request("https://leaf.page/examples/triage-board/api/state", {
        headers: { "Leaf-View-Revision": "99" },
      }),
      environment(),
      executionContext(),
    );

    expect(response.status).toBe(400);
    expect(await response.text()).toBe("unknown page revision");
    expect(getByName).not.toHaveBeenCalled();
  });

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
      executionContext(),
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
          event: {
            id: eventId,
            attempt,
            kind: "action",
            action: "choose",
            revision: 2,
            detail: { private: "not analytics" },
          },
          needs_reply: false,
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
    getByName.mockReturnValue({ fetch: containerFetch } as never);
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
        executionContext(),
      );

    await request({
      kind: "action",
      attempt,
      widget: "private-widget-id",
      action: "choose",
      revision: 2,
      detail: { private: "user input" },
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

describe("page faults", () => {
  const send = (cookie: string, body: object) =>
    worker.fetch(
      new Request("https://leaf.page/examples/triage-board/api/event", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Cookie: cookie,
          // A tab still on the release before a deploy, so the record tells the
          // document's release apart from the edge's.
          "Leaf-Release": "b".repeat(64),
        },
        body: JSON.stringify(body),
      }),
      environment(),
      executionContext(),
    );

  it("logs a passive reader's page fault at the edge without activating a container", async () => {
    const sessionId = "13".repeat(16);
    const containerFetch = vi.fn();
    getByName.mockReturnValue({ fetch: containerFetch } as never);
    const logged = vi.spyOn(console, "log").mockImplementation(() => undefined);
    try {
      const response = await send(`__Host-leaf-page=${sessionId}`, {
        kind: "error",
        revision: 3,
        text: `syntax highlight failed: ${"x".repeat(400)}`,
      });

      expect(response.status).toBe(204);
      expect(response.headers.get("Leaf-Session")).toBe("passive");
      expect(response.headers.get("Leaf-Release")).toBe(RELEASE);
      expect(response.headers.get("Set-Cookie")).toBeNull();
      expect(containerFetch).not.toHaveBeenCalled();
      expect(logged).toHaveBeenCalledOnce();
      const record = logged.mock.calls[0][0];
      expect(record).toMatchObject({
        component: "leaf-page-error",
        event: "browser_page_error",
        reference: "318445474579",
        route: "/examples/triage-board",
        release: "b".repeat(64),
        currentRelease: RELEASE,
        revision: 3,
      });
      expect(record.reason).toHaveLength(300);
      expect(record.reason.startsWith("syntax highlight failed: x")).toBe(true);
    } finally {
      logged.mockRestore();
    }
  });

  it("keeps an active session's faults and a passive reader's gestures in the container", async () => {
    const sessionId = "14".repeat(16);
    const containerFetch = vi.fn(async (_request: Request) =>
      Response.json({
        ok: true,
        event: { id: "15".repeat(16), kind: "comment", revision: 1 },
        needs_reply: false,
        state: { events: [], activity: { obligations: [] } },
      }),
    );
    getByName.mockReturnValue({ fetch: containerFetch } as never);

    await send(
      `__Host-leaf-page=${sessionId}; ${activeMarker("/examples/triage-board")}`,
      {
        kind: "error",
        text: "a widget failed",
      },
    );
    await send(`__Host-leaf-page=${sessionId}`, {
      kind: "comment",
      attempt: "a-comment",
      text: "hello",
    });

    expect(containerFetch).toHaveBeenCalledTimes(2);
    const bodies = await Promise.all(
      containerFetch.mock.calls.map(([request]) => request.json()),
    );
    expect(bodies).toMatchObject([{ kind: "error" }, { kind: "comment" }]);
  });
});

const IMAGE = "registry.cloudflare.com/account/leaf-website@sha256:" + "c".repeat(64);
const SESSION_OBJECT = "0a".repeat(32);

// The parts of a session object's state the tests below drive: its storage, its
// container, its name for itself and its outbound entrypoint, and the gate that holds
// other requests while one claims it. The container answers its health route at
// once, and sends every other request to `forwardedContainerFetch`.
function sessionContext(storage: DurableObjectStorage) {
  const container = {
    running: false,
    images: { leaf: IMAGE },
    start: vi.fn((_options: ContainerStartupOptions) => {
      container.running = true;
    }),
    monitor: vi.fn(async () => {}),
    destroy: vi.fn(async () => {
      container.running = false;
    }),
    setInactivityTimeout: vi.fn(async (_ms: number) => {}),
    interceptOutboundHttps: vi.fn(async (_host: string, _outbound: unknown) => {}),
    interceptAllOutboundHttp: vi.fn(async (_outbound: unknown) => {}),
    getTcpPort: vi.fn((_port: number) => ({
      fetch: async (url: string, init?: Request) =>
        url === "http://container/health"
          ? new Response("ok")
          : forwardedContainerFetch(init!),
    })),
  };
  return {
    storage,
    container,
    id: { toString: () => SESSION_OBJECT },
    exports: {
      SessionOutbound: vi.fn((options: { props: { session: string } }) => options),
    },
    blockConcurrencyWhile: <T>(operation: () => Promise<T>) => operation(),
  };
}

// A session object whose container its first request started.
async function startedSession(storage: DurableObjectStorage, env = environment()) {
  const ctx = sessionContext(storage);
  const session = new LeafSession(ctx as never, env);
  await session.fetch(new Request("https://leaf.page/"));
  expect(ctx.container.running).toBe(true);
  forwardedContainerFetch.mockClear();
  return { ctx, session };
}

// A request a container on this release sends its session's page store.
function storeRequest(path: string, init: RequestInit = {}) {
  return new Request(`https://leaf-state.internal${path}`, {
    ...init,
    headers: { ...(init.headers as Record<string, string>), "Leaf-Release": RELEASE },
  });
}

// The container's outbound requests as the session object `containerId` names routes
// them.
function outbound(
  request: Request,
  env: Env,
  { containerId }: { containerId: string },
) {
  return new SessionOutbound({ props: { session: containerId } } as never, env).fetch(
    request,
  );
}

describe("website page agent", () => {
  it("starts the container on this release's image, sealed but for its own routes", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const { ctx } = await startedSession(storage);
      expect(ctx.container.start).toHaveBeenCalledExactlyOnceWith({
        image: IMAGE,
        instance: { vcpu: 1, memoryMib: 3072, diskMb: 4000 },
        enableInternet: false,
        env: {
          LEAF_AGENT: "Agent",
          OPENAI_API_KEY: "leaf-outbound-proxy",
          CODEX_CA_CERTIFICATE: "/etc/cloudflare/certs/cloudflare-containers-ca.crt",
          LEAF_PAGE_STORE_URL: "https://leaf-state.internal",
        },
      });
      expect(ctx.container.setInactivityTimeout).toHaveBeenCalledWith(600_000);
      const routes = { props: { session: SESSION_OBJECT } };
      expect(ctx.container.interceptOutboundHttps).toHaveBeenCalledWith("*", routes);
      expect(ctx.container.interceptAllOutboundHttp).toHaveBeenCalledWith(routes);
      for (const host of ["example.com", "169.254.169.254"]) {
        const refused = await outbound(new Request(`https://${host}/`), environment(), {
          containerId: SESSION_OBJECT,
        });
        expect(refused.status).toBe(520);
      }
    } finally {
      close();
    }
  });

  it("starts one container for the requests that arrive while it starts", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const ctx = sessionContext(storage);
      let listening!: () => void;
      const ready = new Promise<void>((resolve) => (listening = resolve));
      let checks = 0;
      ctx.container.getTcpPort.mockImplementation(() => ({
        fetch: async (url: string, init?: Request) => {
          if (url !== "http://container/health") return forwardedContainerFetch(init!);
          checks += 1;
          if (checks === 1) throw new Error("the container is not listening");
          await ready;
          return new Response("ok");
        },
      }));
      const session = new LeafSession(ctx as never, environment());
      const reads = [1, 2, 3].map(() =>
        session.fetch(new Request("https://leaf.page/examples/triage-board/api/news")),
      );
      await vi.waitFor(() => expect(checks).toBe(2));
      listening();
      for (const read of await Promise.all(reads))
        expect(await read.text()).toBe("container");
      expect(ctx.container.start).toHaveBeenCalledOnce();
    } finally {
      close();
    }
  });

  it("starts again where the platform could not place the container, and answers a crash with its reason", async () => {
    const { storage, close } = sqliteStorage();
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      const ctx = sessionContext(storage);
      // The first start finds no instance to run on, as just after another stopped.
      let starts = 0;
      ctx.container.getTcpPort.mockImplementation(() => ({
        fetch: async (url: string, init?: Request) => {
          if (url !== "http://container/health") return forwardedContainerFetch(init!);
          if (starts === 1) {
            ctx.container.running = false;
            throw new Error("the container is not listening");
          }
          return new Response("ok");
        },
      }));
      ctx.container.start.mockImplementation(() => {
        starts += 1;
        ctx.container.running = true;
      });
      ctx.container.monitor.mockRejectedValue(
        new Error("there is no container instance that can be provided"),
      );
      const session = new LeafSession(ctx as never, environment());
      const news = await session.fetch(
        new Request("https://leaf.page/examples/triage-board/api/news"),
      );
      expect(await news.text()).toBe("container");
      expect(ctx.container.start).toHaveBeenCalledTimes(2);
      expect(log).not.toHaveBeenCalled();

      // A server that exits is a fault the tab shows, not a wait.
      const crashed = Object.assign(new Error("Container exited with code 1"), {
        exitCode: 1,
      });
      const failing = sessionContext(storage);
      failing.container.getTcpPort.mockImplementation(() => ({
        fetch: async () => {
          failing.container.running = false;
          throw new Error("the container is not listening");
        },
      }));
      failing.container.monitor.mockRejectedValue(crashed);
      const response = await new LeafSession(failing as never, environment()).fetch(
        new Request("https://leaf.page/examples/triage-board/api/news"),
      );
      expect(response.status).toBe(500);
      expect(await response.text()).toBe(
        "Failed to start container: Container exited with code 1",
      );
      expect(failing.container.start).toHaveBeenCalledOnce();
      expect(log).toHaveBeenCalledExactlyOnceWith({
        component: "leaf-container",
        event: "http_error",
        method: "GET",
        status: 500,
        source: "start",
        detail: "Container exited with code 1",
        retried: false,
      });
    } finally {
      log.mockRestore();
      close();
    }
  });

  it("identifies container failure responses without logging private data", async () => {
    const { storage, close } = sqliteStorage();
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      const { session } = await startedSession(storage);
      for (const [body, headers, expected] of [
        ["private-page-content-and-secret".repeat(100), {}, "unclassified"],
        ["private-adapter-error", { "Leaf-Session": "active" }, "adapter"],
      ] as const) {
        forwardedContainerFetch.mockResolvedValueOnce(
          new Response(body, { status: 500, headers }),
        );
        const response = await session.fetch(
          new Request(
            "https://leaf.page/examples/triage-board/api/state?private=secret",
          ),
        );
        expect(response.status).toBe(500);
        expect(await response.text()).toBe(body);
        expect(log).toHaveBeenLastCalledWith({
          component: "leaf-container",
          event: "http_error",
          method: "GET",
          status: 500,
          source: expected,
          retried: false,
        });
      }
      expect(JSON.stringify(log.mock.calls)).not.toMatch(/private|secret/);
      log.mockClear();
      forwardedContainerFetch.mockResolvedValueOnce(new Response("healthy"));
      expect(
        await (await session.fetch(new Request("https://leaf.page/"))).text(),
      ).toBe("healthy");
      expect(log).not.toHaveBeenCalled();
    } finally {
      log.mockRestore();
      close();
    }
  });

  it("resends a read or a view report once when the container connection drops, but no other write", async () => {
    const { storage, close } = sqliteStorage();
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      const { session } = await startedSession(storage);
      const url = "https://leaf.page/examples/triage-board/api/news?private=secret";
      const lost = "Network connection lost.";
      forwardedContainerFetch
        .mockRejectedValueOnce(new Error(lost))
        .mockResolvedValueOnce(new Response("news"));
      const response = await session.fetch(new Request(url));
      expect(response.status).toBe(200);
      expect(await response.text()).toBe("news");
      expect(forwardedContainerFetch).toHaveBeenCalledTimes(2);
      expect(log).toHaveBeenCalledExactlyOnceWith({
        component: "leaf-container",
        event: "http_error",
        method: "GET",
        status: 500,
        source: "disconnected",
        detail: lost,
        retried: true,
      });

      // A second loss reaches the caller rather than retrying again.
      forwardedContainerFetch.mockClear();
      forwardedContainerFetch
        .mockRejectedValueOnce(new Error(lost))
        .mockRejectedValueOnce(new Error(lost));
      expect((await session.fetch(new Request(url))).status).toBe(500);
      expect(forwardedContainerFetch).toHaveBeenCalledTimes(2);

      forwardedContainerFetch.mockClear();
      forwardedContainerFetch.mockRejectedValueOnce(new Error(lost));
      const write = await session.fetch(
        new Request("https://leaf.page/examples/triage-board/api/media", {
          method: "POST",
          body: "bytes",
        }),
      );
      expect(write.status).toBe(500);
      expect(forwardedContainerFetch).toHaveBeenCalledOnce();
      expect(log).toHaveBeenLastCalledWith({
        component: "leaf-container",
        event: "http_error",
        method: "POST",
        status: 500,
        source: "disconnected",
        detail: lost,
        retried: false,
      });

      // A view report replaces only an older report of its session, so a resent
      // copy changes nothing the first one stored.
      forwardedContainerFetch.mockClear();
      forwardedContainerFetch
        .mockRejectedValueOnce(new Error(lost))
        .mockResolvedValueOnce(new Response(null, { status: 204 }));
      const view = await session.fetch(
        new Request("https://leaf.page/examples/triage-board/api/user-view", {
          method: "POST",
          body: '{"session":"s","sequence":3}',
        }),
      );
      expect(view.status).toBe(204);
      expect(forwardedContainerFetch).toHaveBeenCalledTimes(2);
      const resent = forwardedContainerFetch.mock.calls[1][0] as Request;
      expect(await resent.text()).toBe('{"session":"s","sequence":3}');
      expect(log).toHaveBeenLastCalledWith({
        component: "leaf-container",
        event: "http_error",
        method: "POST",
        status: 500,
        source: "disconnected",
        detail: lost,
        retried: true,
      });
      expect(JSON.stringify(log.mock.calls)).not.toMatch(/private|secret/);
    } finally {
      log.mockRestore();
      close();
    }
  });

  it("waits out a lost connection once for every read that met it", async () => {
    const { storage, close } = sqliteStorage();
    const log = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      const { ctx, session } = await startedSession(storage);
      let checks = 0;
      let lost = 3;
      ctx.container.getTcpPort.mockImplementation(() => ({
        fetch: async (url: string, init?: Request) => {
          if (url === "http://container/health") {
            checks += 1;
            return new Response("ok");
          }
          if (lost-- > 0) throw new Error("Network connection lost.");
          return forwardedContainerFetch(init!);
        },
      }));
      const reads = await Promise.all(
        [1, 2, 3].map(() =>
          session.fetch(
            new Request("https://leaf.page/examples/triage-board/api/news"),
          ),
        ),
      );
      for (const read of reads) expect(await read.text()).toBe("container");
      expect(checks).toBe(1);
      expect(ctx.container.start).toHaveBeenCalledOnce();
    } finally {
      log.mockRestore();
      close();
    }
  });

  it("stops a container from before a deploy at the deploy's first request", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const earlier = {
        ...environment(),
        ASSETS: {
          fetch: async () => Response.json({ ...MANIFEST, release: "b".repeat(64) }),
        } as unknown as Fetcher,
      };
      const { ctx } = await startedSession(storage, earlier);
      ctx.container.start.mockClear();
      const destroy = vi.fn(async () => {
        ctx.container.running = false;
      });
      Object.assign(ctx.container, { destroy });
      // The deploy restarts the object on the new release's code; its container still
      // runs the earlier image.
      const session = new LeafSession(ctx as never, environment());
      const state = () =>
        session.fetch(new Request("https://leaf.page/examples/triage-board/api/state"));
      expect(await (await state()).text()).toBe("container");
      expect(destroy).toHaveBeenCalledOnce();
      expect(ctx.container.start).toHaveBeenCalledOnce();
      // The container this release started stays.
      expect(await (await state()).text()).toBe("container");
      expect(destroy).toHaveBeenCalledOnce();
      expect(ctx.container.start).toHaveBeenCalledOnce();
    } finally {
      close();
    }
  });

  it("recalls saved content and private resources without starting the container", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const ctx = sessionContext(storage);
      const session = new LeafSession(ctx as never, environment());
      const responses: Record<
        string,
        { headers: Record<string, string>; chunks: string[] }
      > = {};
      const blobs = new Map<string, Uint8Array>();
      for (const [path, body] of [
        [
          "api/state?revision=2",
          JSON.stringify({
            saved: "comment and choice",
            taken: 1,
            data: {
              version: "v1",
              sources: { notes: { contract: "text", value: "Saved" } },
            },
          }),
        ],
        ["api/news", "saved-reading"],
        ["revisions/r3-private.html", "<p>Private revision</p>"],
      ]) {
        const bytes = new TextEncoder().encode(body);
        const digest = Buffer.from(
          await crypto.subtle.digest("SHA-256", bytes),
        ).toString("hex");
        blobs.set(digest, bytes);
        responses[path] = { headers: {}, chunks: [digest] };
      }
      const publication = { root: "/examples/triage-board", record: {}, responses };
      const prepared = (await (
        await session.pageStore(
          storeRequest("/prepare", {
            method: "PUT",
            body: JSON.stringify(publication),
          }),
        )
      ).json()) as { identity: string; missing: string[] };
      for (const digest of prepared.missing) {
        await session.pageStore(
          storeRequest(`/blobs/${digest}`, { method: "PUT", body: blobs.get(digest)! }),
        );
      }
      await session.pageStore(
        storeRequest("/publication", {
          method: "PUT",
          body: JSON.stringify({ root: publication.root, identity: prepared.identity }),
        }),
      );
      forwardedContainerFetch.mockClear();
      const state = await session.fetch(
        new Request("https://leaf.page/examples/triage-board/api/state", {
          headers: { "Leaf-View-Revision": "2", "Leaf-Data-Version": "v1" },
        }),
      );
      expect(state.headers.get("Leaf-State-Source")).toBe("durable");
      expect(await state.json()).toMatchObject({
        saved: "comment and choice",
        data: { version: "v1" },
      });
      expect(
        await (
          await session.fetch(
            new Request("https://leaf.page/examples/triage-board/api/news"),
          )
        ).text(),
      ).toBe("saved-reading");
      expect(
        await (
          await session.fetch(
            new Request(
              "https://leaf.page/examples/triage-board/revisions/r3-private.html",
            ),
          )
        ).text(),
      ).toContain("Private revision");
      expect(
        (
          await session.fetch(
            new Request("https://leaf.page/examples/triage-board/api/user-view", {
              method: "POST",
              body: "{}",
            }),
          )
        ).status,
      ).toBe(204);
      expect(forwardedContainerFetch).not.toHaveBeenCalled();
      expect(ctx.container.start).not.toHaveBeenCalled();
      // A container this release started.
      ctx.container.running = true;
      storage.kv.put("container-release", RELEASE);
      expect(
        await (
          await session.fetch(
            new Request("https://leaf.page/examples/triage-board/api/news"),
          )
        ).text(),
      ).toBe("container");
      expect(forwardedContainerFetch).toHaveBeenCalledOnce();
    } finally {
      close();
    }
  });

  it("stores bounded binary chunks in the outbound proxy's owning session", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const env = environment();
      const session = new LeafSession(sessionContext(storage) as never, env);
      const get = vi.fn(() => session);
      const idFromString = vi.fn((id: string) => id);
      env.PAGES = { get, idFromString } as never;
      const bytes = new TextEncoder().encode("private saved bytes");
      const digest = Buffer.from(await crypto.subtle.digest("SHA-256", bytes)).toString(
        "hex",
      );
      // Each request names the release its container runs, as Python's does
      // (`_request` in `worker/leaf_website/storage.py`).
      const ask = (
        path: string,
        init: RequestInit = {},
        release: string | null = RELEASE,
      ) =>
        outbound(
          new Request(`https://leaf-state.internal${path}`, {
            ...init,
            headers: {
              ...(init.headers as Record<string, string>),
              ...(release === null ? {} : { "Leaf-Release": release }),
            },
          }),
          env,
          { containerId: "trusted-owner" },
        );
      const absent = "f".repeat(64);
      const missing = () =>
        ask("/prepare", {
          method: "PUT",
          body: JSON.stringify({
            root: "/examples/triage-board",
            record: {
              "events.jsonl": { chunks: [digest, absent], modified: 1_700_000_000 },
            },
            responses: {},
          }),
        });
      expect(await (await missing()).json()).toEqual({
        identity: expect.stringMatching(/^[0-9a-f]{64}$/),
        missing: [digest, absent],
      });
      const put = await ask(`/blobs/${digest}`, {
        method: "PUT",
        body: bytes,
        headers: { Cookie: "__Host-leaf-page=another-user" },
      });
      expect(put.status).toBe(204);
      expect(await (await missing()).json()).toEqual({
        identity: expect.stringMatching(/^[0-9a-f]{64}$/),
        missing: [absent],
      });
      const publication = {
        root: "/examples/triage-board",
        record: { "events.jsonl": { chunks: [digest], modified: 1_700_000_000 } },
        responses: {},
      };
      const prepared = (await (
        await ask("/prepare", { method: "PUT", body: JSON.stringify(publication) })
      ).json()) as { identity: string };
      const committed = await ask("/publication", {
        method: "PUT",
        body: JSON.stringify({ root: publication.root, identity: prepared.identity }),
      });
      expect(committed.status).toBe(204);
      const drafts = { store: "store-1", version: 1, drafts: {} };
      const saved = await ask("/drafts", {
        method: "PUT",
        body: JSON.stringify({ root: publication.root, replaces: null, drafts }),
      });
      expect(await saved.json()).toEqual({ drafts });
      const snapshot = async () => {
        const answer = await ask("/records");
        expect(answer.headers.get("Content-Type")).toBe("application/x-tar");
        return unpackTar(answer.body!);
      };
      const entries = await snapshot();
      expect(entries.map(({ header }) => header.name)).toEqual([
        "records.json",
        digest,
      ]);
      expect(JSON.parse(new TextDecoder().decode(entries[0].data!))).toEqual({
        records: { "/examples/triage-board": publication.record },
        drafts: { "/examples/triage-board": drafts },
      });
      expect(new TextDecoder().decode(entries[1].data!)).toBe("private saved bytes");
      expect(idFromString.mock.calls.every(([id]) => id === "trusted-owner")).toBe(
        true,
      );
      // A refusal reaches the container as an answer carrying its reason, which
      // a thrown handler would turn into a closed connection.
      const oversized = await ask(`/blobs/${digest}`, {
        method: "PUT",
        body: new Uint8Array(1024 * 1024 + 1),
      });
      expect(oversized.status).toBe(500);
      expect(await oversized.text()).toBe("page storage chunk exceeds 1 MiB");
      // A container still on the previous image after a deploy reads nothing this
      // release shaped and writes nothing, and its refusal says so apart from a fault.
      for (const release of ["previous-release", null]) {
        const restore = await ask("/records", {}, release);
        expect(restore.status).toBe(409);
        expect(await restore.text()).toBe(`the page store serves release ${RELEASE}`);
        const write = await ask(
          "/drafts",
          {
            method: "PUT",
            body: JSON.stringify({
              root: publication.root,
              replaces: { store: drafts.store, version: drafts.version },
              drafts: { ...drafts, version: 2 },
            }),
          },
          release,
        );
        expect(write.status).toBe(409);
      }
      const held = await snapshot();
      expect(JSON.parse(new TextDecoder().decode(held[0].data!)).drafts).toEqual({
        "/examples/triage-board": drafts,
      });
    } finally {
      close();
    }
  });

  it("holds a container to its session object's release, not the handler's", async () => {
    const { storage, close } = sqliteStorage();
    try {
      // For some seconds after a deploy the object can still run the previous code, and
      // so start the previous image, while the handler already runs the deployed code.
      const previous = { ...MANIFEST, release: "previous-release" };
      const objectEnv = {
        ...environment(),
        ASSETS: { fetch: async () => Response.json(previous) } as unknown as Fetcher,
      };
      const session = new LeafSession(sessionContext(storage) as never, objectEnv);
      const env = environment();
      env.PAGES = { get: () => session, idFromString: (id: string) => id } as never;
      const restore = (release: string) =>
        outbound(
          new Request("https://leaf-state.internal/records", {
            headers: { "Leaf-Release": release },
          }),
          env,
          { containerId: "trusted-owner" },
        );
      expect((await restore("previous-release")).status).toBe(200);
      const refused = await restore(RELEASE);
      expect(refused.status).toBe(409);
      expect(await refused.text()).toBe(
        "the page store serves release previous-release",
      );
    } finally {
      close();
    }
  });

  it("keeps the OpenAI secret in the trusted outbound handler", async () => {
    const env = environment();
    const upstream = vi.fn(async (_request: Request) => new Response("ok"));
    vi.stubGlobal("fetch", upstream);
    const response = await outbound(
      new Request("https://api.openai.com/v1/responses", {
        method: "POST",
        headers: { Authorization: "Bearer leaf-outbound-proxy" },
        body: "{}",
      }),
      env,
      { containerId: "user-container" },
    );

    expect(await response.text()).toBe("ok");
    expect(env.SOURCE_AGENT_RATE_LIMITER.limit).toHaveBeenCalledWith({
      key: "model:user-container",
    });
    const forwarded = upstream.mock.calls[0][0];
    expect(forwarded.headers.get("Authorization")).toBe("Bearer test-key");
    vi.unstubAllGlobals();
  });

  it("logs content-free model timings with the Codex turn", async () => {
    const env = environment();
    const responseBody = [
      'data: {"type":"response.created"}',
      "",
      'data: {"type":"response.output_item.added","item":{"type":"reasoning","content":"private reasoning"}}',
      "",
      'data: {"type":"response.completed","response":{"output":[{"content":"private answer"}]}}',
      "",
      "data: [DONE]",
      "",
    ].join("\r\n");
    const upstream = vi.fn(
      async () =>
        new Response(
          ReadableStream.from(
            Array.from(new TextEncoder().encode(responseBody), (byte) =>
              Uint8Array.of(byte),
            ),
          ),
          {
            headers: { "x-request-id": "upstream-request" },
          },
        ),
    );
    vi.stubGlobal("fetch", upstream);
    const logged = vi.spyOn(console, "log").mockImplementation(() => undefined);
    const handler = outbound;

    try {
      const response = await handler(
        new Request("https://api.openai.com/v1/responses", {
          method: "POST",
          headers: {
            "x-codex-turn-metadata": JSON.stringify({
              request_kind: "turn",
              thread_id: "app-thread",
              turn_id: "app-turn",
              workspace: "private workspace",
            }),
          },
          body: "private prompt",
        }),
        env,
        { containerId: "user-container" },
      );

      expect(await response.text()).toBe(responseBody);
      const records = logged.mock.calls.map(([record]) => record);
      expect(
        records.map((record) => (record as Record<string, unknown>).event),
      ).toEqual([
        "model_request_started",
        "model_response_headers",
        "model_response_first_byte",
        "model_response_first_output",
        "model_response_completed",
      ]);
      expect(records[0]).toMatchObject({
        component: "leaf-agent",
        containerId: "user-container",
        requestKind: "turn",
        threadId: "app-thread",
        turnId: "app-turn",
      });
      expect(records[3]).toMatchObject({
        responseEvent: "response.output_item.added",
        outputType: "reasoning",
        upstreamRequestId: "upstream-request",
      });
      expect(records[4]).toMatchObject({
        status: 200,
      });
      expect(JSON.stringify(records)).not.toContain("private");
    } finally {
      logged.mockRestore();
      vi.unstubAllGlobals();
    }
  });

  it("logs a model body Codex cancels with its bytes and idle time", async () => {
    const keepalive = new TextEncoder().encode('data: {"type":"keepalive"}\r\n\r\n');
    let upstreamCancelled = false;
    const upstream = vi.fn(
      async () =>
        new Response(
          new ReadableStream<Uint8Array>({
            start(controller) {
              controller.enqueue(keepalive);
            },
            cancel() {
              upstreamCancelled = true;
            },
          }),
          { headers: { "x-request-id": "upstream-request" } },
        ),
    );
    vi.stubGlobal("fetch", upstream);
    const logged = vi.spyOn(console, "log").mockImplementation(() => undefined);
    const handler = outbound;

    try {
      const response = await handler(
        new Request("https://api.openai.com/v1/responses", {
          method: "POST",
          body: "{}",
        }),
        environment(),
        { containerId: "user-container" },
      );
      const reader = response.body!.getReader();
      expect((await reader.read()).value).toEqual(keepalive);
      // Codex waits on a silent stream with a read pending when it cancels.
      const pending = reader.read();
      await new Promise((resolve) => setTimeout(resolve, 0));
      await reader.cancel();
      expect((await pending).done).toBe(true);
      await new Promise((resolve) => setTimeout(resolve, 0));

      const records = logged.mock.calls.map(
        ([record]) => record as Record<string, unknown>,
      );
      expect(records.map((record) => record.event)).toEqual([
        "model_request_started",
        "model_response_headers",
        "model_response_first_byte",
        "model_response_first_output",
        "model_response_cancelled",
      ]);
      expect(records[4]).toMatchObject({
        bytes: keepalive.byteLength,
        idleMs: expect.any(Number),
        status: 200,
        upstreamRequestId: "upstream-request",
      });
      expect(upstreamCancelled).toBe(true);
    } finally {
      logged.mockRestore();
      vi.unstubAllGlobals();
    }
  });

  it("rejects other uses of the credential-injecting route", async () => {
    const handler = outbound;
    const response = await handler(
      new Request("https://api.openai.com/v1/files", { method: "POST" }),
      environment(),
      { containerId: "user-container" },
    );

    expect(response.status).toBe(403);
  });

  it("caps model calls from one user container", async () => {
    const denied = {
      limit: vi.fn(async () => ({ success: false })),
    } as unknown as RateLimit;
    const env = environment({ SOURCE_AGENT_RATE_LIMITER: denied });
    const upstream = vi.fn(async (_request: Request) => new Response("ok"));
    vi.stubGlobal("fetch", upstream);
    const handler = outbound;

    const response = await handler(
      new Request("https://api.openai.com/v1/responses", {
        method: "POST",
        body: "{}",
      }),
      env,
      { containerId: "user-container" },
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
      executionContext(),
    );

    expect(response.status).toBe(404);
    expect(getByName).not.toHaveBeenCalled();
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
      const attempt = "user-attempt-01";
      let resolveAgentStart: (response: Response) => void = () => undefined;
      const agentStart = new Promise<Response>((resolve) => {
        resolveAgentStart = resolve;
      });
      const containerFetch = vi.fn(async (request: Request) => {
        if (new URL(request.url).pathname.endsWith("/api/event")) {
          return Response.json({
            ok: true,
            event: { id: eventId, attempt, kind: "comment", revision: 1 },
            needs_reply: true,
            state: {
              events: [{ id: eventId, attempt, kind: "comment", revision: 1 }],
              activity: { obligations: [`update:${eventId}`] },
            },
          });
        }
        return agentStart;
      });
      getByName.mockReturnValue({ fetch: containerFetch } as never);
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
        executionContext(waitUntil),
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
    getByName.mockReturnValue({
      fetch: async () =>
        Response.json({
          ok: true,
          event: { id: "07".repeat(16), attempt, kind: "comment", revision: 1 },
          needs_reply: false,
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
      executionContext(waitUntil),
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
          event: { id: eventId, attempt, kind: "comment", revision: 1 },
          needs_reply: true,
          state: {
            events: [{ id: eventId, attempt, kind: "comment", revision: 1 }],
            activity: { obligations: [`update:${eventId}`] },
          },
        }),
      )
      .mockResolvedValueOnce(
        Response.json({ status: "appended", event: "15".repeat(16) }),
      );
    getByName.mockReturnValue({ fetch: containerFetch } as never);
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
      executionContext(waitUntil),
    );
    await waitUntil.mock.calls[0][0];

    expect(deny).toHaveBeenCalledWith({ key: "203.0.113.2" });
    expect(containerFetch.mock.calls[1][0].url).toBe(
      "http://container/examples/triage-board/_leaf/agent/fail",
    );
    expect(await containerFetch.mock.calls[1][0].json()).toEqual({
      event: eventId,
      failure: "rate_limited",
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
          event: { id: eventId, attempt, kind: "comment", revision: 1 },
          needs_reply: true,
          state: {
            events: [{ id: eventId, attempt, kind: "comment", revision: 1 }],
            activity: { obligations: [`update:${eventId}`] },
          },
        }),
      )
      .mockResolvedValueOnce(new Response("unavailable", { status: 503 }))
      .mockResolvedValueOnce(
        Response.json({ status: "appended", event: "10".repeat(16) }),
      );
    getByName.mockReturnValue({ fetch: containerFetch } as never);
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
      executionContext(waitUntil),
    );
    await waitUntil.mock.calls[0][0];

    expect(response.status).toBe(200);
    expect(containerFetch.mock.calls[2][0].url).toBe(
      "http://container/examples/triage-board/_leaf/agent/fail",
    );
    expect(await containerFetch.mock.calls[2][0].json()).toEqual({
      event: eventId,
      failure: "startup_failed",
    });
  });
});
