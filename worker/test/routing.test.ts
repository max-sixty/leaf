import { describe, expect, it } from "vitest";

import {
  HTTP_SESSION_COOKIE,
  SESSION_COOKIE,
  isExampleRequest,
  needsExampleSlash,
  newSessionId,
  sessionCookie,
  sessionFromCookie,
} from "../src/routing";

describe("website example routing", () => {
  it("sends only concrete example routes to Leaf", () => {
    expect(isExampleRequest("/examples/design-decision/")).toBe(true);
    expect(isExampleRequest("/examples/design-decision/api/state")).toBe(true);
    expect(isExampleRequest("/examples/design-decision")).toBe(true);
    expect(isExampleRequest("/examples/")).toBe(false);
    expect(isExampleRequest("/examples.html")).toBe(false);
    expect(isExampleRequest("/examples/../registry.json")).toBe(false);
    expect(needsExampleSlash("/examples/design-decision")).toBe(true);
    expect(needsExampleSlash("/examples/design-decision/")).toBe(false);
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
