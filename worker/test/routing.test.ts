import { describe, expect, it } from "vitest";

import {
  ACTIVE_COOKIE_PREFIX,
  HTTP_ACTIVE_COOKIE_PREFIX,
  HTTP_SESSION_COOKIE,
  SESSION_COOKIE,
  activeCookie,
  activeFromCookie,
  isPageApiRequest,
  isPageSessionFileRequest,
  isPrivatePageRequest,
  needsPageSlash,
  newSessionId,
  pageRoute,
  parseSiteManifest,
  sessionCookie,
  sessionFromCookie,
} from "../src/routing";

const page = (kind: "product" | "example") => ({
  assets: `/_leaf-release/${"a".repeat(64)}/page`,
  description: "What a reader does here.",
  directory: "page",
  image: "/media/0123456789abcdef.jpg",
  kind,
  layer: "layer",
  state: "/_leaf/state/page.json",
  states: { "1": "/_leaf/state/page.json" },
  title: "The page",
});
const pages = {
  "/": page("product"),
  "/examples": page("product"),
  "/packages": page("product"),
  "/examples/triage-board": page("example"),
};
const route = (pathname: string) => pageRoute(pathname, pages);

describe("website page routing", () => {
  it("accepts only manifests whose current state and release paths agree", () => {
    const release = "a".repeat(64);
    const manifest = {
      release,
      pages: { "/": page("product") },
    };
    expect(parseSiteManifest(manifest)).toEqual(manifest);

    expect(() =>
      parseSiteManifest({
        ...manifest,
        pages: {
          "/": {
            ...page("product"),
            assets: `/_leaf-release/${"b".repeat(64)}/page`,
          },
        },
      }),
    ).toThrow('at pages["/"].assets');
    expect(() =>
      parseSiteManifest({
        ...manifest,
        pages: {
          "/": {
            ...page("product"),
            state: "/_leaf/state/missing.json",
          },
        },
      }),
    ).toThrow('at pages["/"].state');
    // Every page carries the card a shared link unfurls into, so a build that
    // published one without it is refused here rather than at the reader.
    const { image: _image, ...cardless } = page("product");
    expect(() =>
      parseSiteManifest({ ...manifest, pages: { "/": cardless } }),
    ).toThrow('at pages["/"].image');
    expect(() =>
      parseSiteManifest({
        ...manifest,
        pages: { "/": { ...page("product"), image: "https://elsewhere/card.png" } },
      }),
    ).toThrow('at pages["/"].image');
  });

  it("sends product and concrete example routes to Leaf", () => {
    expect(route("/")).not.toBeNull();
    expect(route("/api/state")).not.toBeNull();
    expect(route("/examples/")).not.toBeNull();
    expect(isPageApiRequest(route("/examples/api/state"))).toBe(true);
    expect(isPageApiRequest(route("/examples/triage-board/api/state"))).toBe(true);
    expect(isPageApiRequest(route("/examples/triage-board/runtime/state-feed.js"))).toBe(false);
    expect(isPageSessionFileRequest(route("/media/upload.png"))).toBe(true);
    expect(
      isPageSessionFileRequest(
        route("/examples/triage-board/revisions/r3-aabbccdd.html"),
      ),
    ).toBe(true);
    expect(
      isPageSessionFileRequest(route("/examples/triage-board/versions/v3.html")),
    ).toBe(true);
    expect(
      isPageSessionFileRequest(route("/examples/triage-board/theme.css")),
    ).toBe(false);
    expect(route("/examples.html")).toBeNull();
    expect(route("/examples/missing/")).toBeNull();
    // A crawler reads these two off the asset binding; a page route would hand
    // each reader a container session before it had seen a page.
    expect(route("/robots.txt")).toBeNull();
    expect(route("/sitemap.xml")).toBeNull();
    expect(needsPageSlash("/packages", route("/packages")!)).toBe(true);
    expect(needsPageSlash("/examples/triage-board/", route("/examples/triage-board/")!)).toBe(false);
    expect(route("/examples/api/event")).toEqual({
      root: "/examples",
      inside: "api/event",
      ...pages["/examples"],
    });
    expect(route("/examples/triage-board/api/event")).toEqual({
      root: "/examples/triage-board",
      inside: "api/event",
      ...pages["/examples/triage-board"],
    });
    expect(isPrivatePageRequest("/_leaf/pages/index/index.html")).toBe(true);
    expect(isPrivatePageRequest("/examples/triage-board/_leaf/agent/reply")).toBe(
      true,
    );
    expect(isPrivatePageRequest("/examples/triage-board/api/state")).toBe(false);
  });

  it("marks private state for only the page that owns it", () => {
    const root = "/examples/triage-board";
    expect(
      activeFromCookie(
        `${ACTIVE_COOKIE_PREFIX}-page-examples_triage-board=1`,
        true,
        root,
      ),
    ).toBe(true);
    expect(
      activeFromCookie(
        `${HTTP_ACTIVE_COOKIE_PREFIX}-page-examples_triage-board=1`,
        false,
        root,
      ),
    ).toBe(true);
    expect(
      activeFromCookie(
        `${HTTP_ACTIVE_COOKIE_PREFIX}-page-examples_triage-board=1`,
        true,
        root,
      ),
    ).toBe(false);
    expect(activeFromCookie(`${ACTIVE_COOKIE_PREFIX}-root=1`, true, root)).toBe(false);
    expect(activeFromCookie(`${ACTIVE_COOKIE_PREFIX}=1`, true, root)).toBe(false);
    expect(activeFromCookie(null, true, root)).toBe(false);
    expect(activeCookie(true, root)).toBe(
      `${ACTIVE_COOKIE_PREFIX}-page-examples_triage-board=1; Path=/; Secure; HttpOnly; SameSite=Lax`,
    );
    expect(activeCookie(false, "/")).toBe(
      `${HTTP_ACTIVE_COOKIE_PREFIX}-root=1; Path=/; HttpOnly; SameSite=Lax`,
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
