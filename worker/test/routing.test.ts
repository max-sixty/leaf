import { describe, expect, it } from "vitest";

import {
  HTTP_SESSION_COOKIE,
  SESSION_COOKIE,
  isPageApiRequest,
  isPageMediaRequest,
  isPageRequest,
  isPrivatePageRequest,
  needsPageSlash,
  newSessionId,
  pageRoute,
  sessionCookie,
  sessionFromCookie,
} from "../src/routing";

describe("website page routing", () => {
  it("sends product and concrete example routes to Leaf", () => {
    expect(isPageRequest("/")).toBe(true);
    expect(isPageRequest("/api/state")).toBe(true);
    expect(isPageRequest("/examples/")).toBe(true);
    expect(isPageRequest("/examples/api/state")).toBe(true);
    expect(isPageRequest("/examples/design-decision/")).toBe(true);
    expect(isPageRequest("/examples/design-decision/api/state")).toBe(true);
    expect(isPageApiRequest("/api/news")).toBe(true);
    expect(isPageApiRequest("/examples/design-decision/api/state")).toBe(true);
    expect(isPageApiRequest("/examples/design-decision/runtime/state-feed.js")).toBe(
      false,
    );
    expect(isPageApiRequest("/examples/design-decision/")).toBe(false);
    expect(isPageMediaRequest("/media/upload.png")).toBe(true);
    expect(isPageMediaRequest("/examples/design-decision/media/upload.png")).toBe(
      true,
    );
    expect(isPageMediaRequest("/examples/design-decision/theme.css")).toBe(false);
    expect(isPageRequest("/media/social-card.png")).toBe(true);
    expect(isPageRequest("/examples.html")).toBe(false);
    expect(isPageRequest("/examples/../registry.json")).toBe(false);
    expect(needsPageSlash("/packages")).toBe(true);
    expect(needsPageSlash("/examples/design-decision")).toBe(true);
    expect(needsPageSlash("/examples/design-decision/")).toBe(false);
    expect(pageRoute("/examples/api/event")).toEqual({
      root: "/examples",
      inside: "api/event",
      kind: "product",
    });
    expect(pageRoute("/examples/design-decision/api/event")).toEqual({
      root: "/examples/design-decision",
      inside: "api/event",
      kind: "example",
    });
    expect(isPrivatePageRequest("/_leaf/pages/index/index.html")).toBe(true);
    expect(isPrivatePageRequest("/examples/design-decision/_leaf/agent/reply")).toBe(
      true,
    );
    expect(isPrivatePageRequest("/examples/design-decision/api/state")).toBe(false);
  });

  it("reuses only a well-formed opaque session cookie", () => {
    const id = "01".repeat(16);
    expect(sessionFromCookie(`theme=dark; ${SESSION_COOKIE}=${id}`, true)).toBe(id);
    expect(sessionFromCookie(`${HTTP_SESSION_COOKIE}=${id}`, false)).toBe(id);
    expect(
      sessionFromCookie(
        `${HTTP_SESSION_COOKIE}=${"02".repeat(16)}; ${SESSION_COOKIE}=${id}`,
        true,
      ),
    ).toBe(id);
    expect(sessionFromCookie(`${HTTP_SESSION_COOKIE}=${id}`, true)).toBe(null);
    expect(sessionFromCookie(`${SESSION_COOKIE}=not-a-session`, true)).toBe(null);
    expect(sessionFromCookie(null, true)).toBe(null);
  });

  it("mints transport-appropriate session cookies from 128 random bits", () => {
    const id = newSessionId(Uint8Array.from({ length: 16 }, (_, index) => index));
    expect(id).toBe("000102030405060708090a0b0c0d0e0f");
    expect(sessionCookie(id, true)).toBe(
      `${SESSION_COOKIE}=${id}; Path=/; Secure; HttpOnly; SameSite=Lax`,
    );
    expect(sessionCookie(id, false)).toBe(
      `${HTTP_SESSION_COOKIE}=${id}; Path=/; HttpOnly; SameSite=Lax`,
    );
  });
});
