import { describe, expect, it } from "vitest";

import {
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
    expect(sessionFromCookie(`theme=dark; ${SESSION_COOKIE}=${id}`)).toBe(id);
    expect(sessionFromCookie(`${SESSION_COOKIE}=not-a-session`)).toBe(null);
    expect(sessionFromCookie(null)).toBe(null);
  });

  it("mints a host-only secure session cookie from 128 random bits", () => {
    const id = newSessionId(Uint8Array.from({ length: 16 }, (_, index) => index));
    expect(id).toBe("000102030405060708090a0b0c0d0e0f");
    expect(sessionCookie(id)).toBe(
      `${SESSION_COOKIE}=${id}; Path=/; Secure; HttpOnly; SameSite=Strict`,
    );
  });
});
