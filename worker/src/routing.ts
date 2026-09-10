/** Pure request routing for the public Leaf pages. */

import * as z from "zod/mini";

export const SESSION_COOKIE = "__Host-leaf-page";
export const HTTP_SESSION_COOKIE = "leaf-page-local";
export const ACTIVE_COOKIE = "__Host-leaf-active";
export const HTTP_ACTIVE_COOKIE = "leaf-active-local";
export const CONTAINER_COOKIE = "__Host-leaf-container";
export const HTTP_CONTAINER_COOKIE = "leaf-container-local";

const PAGE_RESOURCE =
  /^(?:api|guidance|media|revisions|runtime|vendor|versions|widgets)(?:\/|$)|^(?:icon\.svg|leaf\.js|registry\.json|sitenote\.js|theme\.css)$/;
const SESSION_ID = /^[0-9a-f]{32}$/;
const RELEASE = /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/;
const PAGE_ROOT = /^(?:\/|\/[a-z0-9-]+(?:\/[a-z0-9-]+)*)$/;
const RELEASE_ASSET =
  /^\/_leaf-release\/(?:[0-9a-f]{40}|[0-9a-f]{64})\/[a-z0-9-]+$/;
const STATE = /^\/_leaf\/state\/[a-z0-9-]+\.json$/;
// The card image a shared link unfurls into, at the page root that stores it.
const CARD = /^(?:\/[a-z0-9-]+)*\/media\/[0-9a-f]{16}\.[a-z]+$/;

const sitePageSchema = z
  .object({
    assets: z.string().check(z.regex(RELEASE_ASSET)),
    directory: z.string().check(
      z.minLength(1),
      z.refine(
        (directory) =>
          !directory.startsWith("/") && !directory.split("/").includes(".."),
      ),
    ),
    description: z.string().check(z.minLength(1)),
    image: z.string().check(z.regex(CARD)),
    kind: z.union([z.literal("product"), z.literal("example")]),
    layer: z.string().check(z.minLength(1)),
    state: z.string().check(z.regex(STATE)),
    title: z.string().check(z.minLength(1)),
    states: z.record(
      z.string().check(z.regex(/^[1-9][0-9]*$/)),
      z.string().check(z.regex(STATE)),
    ),
  })
  .check(
    z.refine(
      (page) => Object.keys(page.states).length > 0,
      { path: ["states"] },
    ),
    z.refine(
      (page) => Object.values(page.states).includes(page.state),
      { path: ["state"] },
    ),
  );

const siteManifestSchema = z
  .object({
    release: z.string().check(z.regex(RELEASE)),
    pages: z.record(z.string().check(z.regex(PAGE_ROOT)), sitePageSchema),
  })
  .check((context) => {
    for (const [root, page] of Object.entries(context.value.pages)) {
      if (page.assets.startsWith(`/_leaf-release/${context.value.release}/`)) {
        continue;
      }
      context.issues.push({
        code: "custom",
        input: page.assets,
        message: "asset path does not match the site release",
        path: ["pages", root, "assets"],
      });
    }
  });

export type SitePage = z.infer<typeof sitePageSchema>;
export type SiteManifest = z.infer<typeof siteManifestSchema>;
export type PageRoute = Omit<SitePage, "directory"> & {
  root: string;
  inside: string;
};

export function parseSiteManifest(value: unknown): SiteManifest {
  const result = siteManifestSchema.safeParse(value);
  if (!result.success) {
    throw new Error(`invalid Leaf site manifest: ${z.prettifyError(result.error)}`);
  }
  return result.data;
}

export function releaseAssetRoute(
  pathname: string,
  pages: Record<string, SitePage>,
): { route: PageRoute; pathname: string } | null {
  for (const [root, page] of Object.entries(pages)) {
    if (!pathname.startsWith(`${page.assets}/`)) continue;
    const inside = pathname.slice(page.assets.length + 1);
    if (!PAGE_RESOURCE.test(inside) || inside.startsWith("api/")) return null;
    const publicRoot = root === "/" ? "" : root;
    return {
      route: { root, inside, ...page },
      pathname: `${publicRoot}/${inside}`,
    };
  }
  return null;
}

export function pageRoute(
  pathname: string,
  pages: Record<string, SitePage>,
): PageRoute | null {
  const roots = Object.keys(pages).sort((left, right) => right.length - left.length);
  for (const root of roots) {
    const publicRoot = root === "/" ? "" : root;
    let inside: string;
    if (pathname === (publicRoot || "/") || pathname === `${publicRoot}/`) {
      inside = "";
    } else if (pathname.startsWith(`${publicRoot}/`)) {
      inside = pathname.slice(publicRoot.length + 1);
      if (!PAGE_RESOURCE.test(inside)) continue;
    } else {
      continue;
    }
    return { root, inside, ...pages[root] };
  }
  return null;
}

export function isPageApiRequest(route: PageRoute | null): boolean {
  return route?.inside === "api" || route?.inside.startsWith("api/") || false;
}

export function isPageSessionFileRequest(route: PageRoute | null): boolean {
  const directory = route?.inside.split("/", 1)[0];
  return ["media", "revisions", "versions"].includes(directory ?? "");
}

export function needsPageSlash(pathname: string, route: PageRoute): boolean {
  return route.inside === "" && pathname !== "/" && !pathname.endsWith("/");
}

export function isPrivatePageRequest(pathname: string): boolean {
  return pathname === "/_leaf" || pathname.includes("/_leaf/");
}

export function sessionFromCookie(
  cookie: string | null,
  secure: boolean,
): string | null {
  if (cookie === null) return null;
  const expected = secure ? SESSION_COOKIE : HTTP_SESSION_COOKIE;
  for (const item of cookie.split(";")) {
    const [name, ...value] = item.trim().split("=");
    const candidate = value.join("=");
    if (name === expected && SESSION_ID.test(candidate)) return candidate;
  }
  return null;
}

export function containerFromCookie(
  cookie: string | null,
  secure: boolean,
): boolean {
  if (cookie === null) return false;
  const expected = secure ? CONTAINER_COOKIE : HTTP_CONTAINER_COOKIE;
  return cookie
    .split(";")
    .some((item) => item.trim() === `${expected}=1`);
}

export function activeFromCookie(cookie: string | null, secure: boolean): boolean {
  if (cookie === null) return false;
  const expected = secure ? ACTIVE_COOKIE : HTTP_ACTIVE_COOKIE;
  return cookie
    .split(";")
    .some((item) => item.trim() === `${expected}=1`);
}

export function newSessionId(random: Uint8Array): string {
  if (random.byteLength !== 16) {
    throw new Error("a Leaf website session id needs exactly 16 random bytes");
  }
  return Array.from(random, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function sessionCookie(sessionId: string, secure: boolean): string {
  if (!SESSION_ID.test(sessionId)) throw new Error("invalid Leaf website session id");
  const name = secure ? SESSION_COOKIE : HTTP_SESSION_COOKIE;
  const security = secure ? "; Secure" : "";
  return `${name}=${sessionId}; Path=/${security}; HttpOnly; SameSite=Lax`;
}

export function containerCookie(secure: boolean): string {
  const name = secure ? CONTAINER_COOKIE : HTTP_CONTAINER_COOKIE;
  const security = secure ? "; Secure" : "";
  return `${name}=1; Path=/${security}; HttpOnly; SameSite=Lax`;
}

export function activeCookie(secure: boolean): string {
  const name = secure ? ACTIVE_COOKIE : HTTP_ACTIVE_COOKIE;
  const security = secure ? "; Secure" : "";
  return `${name}=1; Path=/${security}; HttpOnly; SameSite=Lax`;
}

export function clearContainerCookie(secure: boolean): string {
  const name = secure ? CONTAINER_COOKIE : HTTP_CONTAINER_COOKIE;
  const security = secure ? "; Secure" : "";
  return `${name}=; Path=/; Max-Age=0${security}; HttpOnly; SameSite=Lax`;
}
