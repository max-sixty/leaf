import { describe, expect, it, vi } from "vitest";

vi.mock("@cloudflare/containers", () => ({
  Container: class {},
  getContainer: vi.fn(),
}));

import worker, { LeafExampleSession } from "../src/index";

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
      const env = {
        ASSETS: { fetch: fetchAsset } as unknown as Fetcher,
        EXAMPLES: {} as DurableObjectNamespace<LeafExampleSession>,
      };

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
    const env = {
      ASSETS: { fetch: async () => asset } as unknown as Fetcher,
      EXAMPLES: {} as DurableObjectNamespace<LeafExampleSession>,
    };

    const response = await worker.fetch(
      new Request("https://leaf.page/theme.css"),
      env,
    );

    expect(response).toBe(asset);
    expect(response.headers.get("Content-Security-Policy")).toBeNull();
  });
});
