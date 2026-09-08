import { describe, expect, it } from "vitest";

import {
  ACTIVE_COOKIE,
  CONTAINER_COOKIE,
  HTTP_ACTIVE_COOKIE,
  HTTP_CONTAINER_COOKIE,
  HTTP_SESSION_COOKIE,
  SESSION_COOKIE,
  activeCookie,
  activeFromCookie,
  clearContainerCookie,
  containerCookie,
  containerFromCookie,
  isPageApiRequest,
  isPageMediaRequest,
  isPrivatePageRequest,
  needsPageSlash,
  newSessionId,
  pageRoute,
  sessionCookie,
  sessionFromCookie,
} from "../src/routing";

const page = (kind: "product" | "example") => ({
  assets: `/_leaf-release/${"a".repeat(64)}/page`,
  directory: "page",
  kind,
  layer: "layer",
  state: "/_leaf/state/page.json",
  states: { "1": "/_leaf/state/page.json" },
});
const pages = {
  "/": page("product"),
  "/examples": page("product"),
  "/packages": page("product"),
  "/examples/design-decision": page("example"),
};
const route = (pathname: string) => pageRoute(pathname, pages);

describe("website page routing", () => {
  it("sends product and concrete example routes to Leaf", () => {
    expect(route("/")).not.toBeNull();
    expect(route("/api/state")).not.toBeNull();
    expect(route("/examples/")).not.toBeNull();
    expect(isPageApiRequest(route("/examples/api/state"))).toBe(true);
    expect(isPageApiRequest(route("/examples/design-decision/api/state"))).toBe(true);
    expect(isPageApiRequest(route("/examples/design-decision/runtime/state-feed.js"))).toBe(false);
    expect(isPageMediaRequest(route("/media/upload.png"))).toBe(true);
    expect(isPageMediaRequest(route("/examples/design-decision/media/upload.png"))).toBe(true);
    expect(isPageMediaRequest(route("/examples/design-decision/theme.css"))).toBe(false);
    expect(route("/examples.html")).toBeNull();
    expect(route("/examples/missing/")).toBeNull();
    expect(needsPageSlash("/packages", route("/packages")!)).toBe(true);
    expect(needsPageSlash("/examples/design-decision/", route("/examples/design-decision/")!)).toBe(false);
    expect(route("/examples/api/event")).toEqual({
      root: "/examples",
      inside: "api/event",
      ...pages["/examples"],
    });
    expect(route("/examples/design-decision/api/event")).toEqual({
      root: "/examples/design-decision",
      inside: "api/event",
      ...pages["/examples/design-decision"],
    });
    expect(isPrivatePageRequest("/_leaf/pages/index/index.html")).toBe(true);
    expect(isPrivatePageRequest("/examples/design-decision/_leaf/agent/reply")).toBe(
      true,
    );
    expect(isPrivatePageRequest("/examples/design-decision/api/state")).toBe(false);
  });

  it("pins a mismatched page until its container catches the edge", () => {
    expect(activeFromCookie(`${ACTIVE_COOKIE}=1`, true)).toBe(true);
    expect(activeFromCookie(`${HTTP_ACTIVE_COOKIE}=1`, false)).toBe(true);
    expect(activeFromCookie(`${HTTP_ACTIVE_COOKIE}=1`, true)).toBe(false);
    expect(activeFromCookie(null, true)).toBe(false);
    expect(activeCookie(true)).toBe(
      `${ACTIVE_COOKIE}=1; Path=/; Secure; HttpOnly; SameSite=Lax`,
    );
    expect(activeCookie(false)).toBe(
      `${HTTP_ACTIVE_COOKIE}=1; Path=/; HttpOnly; SameSite=Lax`,
    );
    expect(containerFromCookie(`${CONTAINER_COOKIE}=1`, true)).toBe(true);
    expect(containerFromCookie(`${HTTP_CONTAINER_COOKIE}=1`, false)).toBe(true);
    expect(containerFromCookie(`${HTTP_CONTAINER_COOKIE}=1`, true)).toBe(false);
    expect(containerFromCookie(`${CONTAINER_COOKIE}=0`, true)).toBe(false);
    expect(containerFromCookie(null, true)).toBe(false);
    expect(containerCookie(true)).toBe(
      `${CONTAINER_COOKIE}=1; Path=/; Secure; HttpOnly; SameSite=Lax`,
    );
    expect(containerCookie(false)).toBe(
      `${HTTP_CONTAINER_COOKIE}=1; Path=/; HttpOnly; SameSite=Lax`,
    );
    expect(clearContainerCookie(true)).toBe(
      `${CONTAINER_COOKIE}=; Path=/; Max-Age=0; Secure; HttpOnly; SameSite=Lax`,
    );
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
