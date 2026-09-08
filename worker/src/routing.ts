/** Pure request routing for the public Leaf pages. */

export const SESSION_COOKIE = "__Host-leaf-page";
export const HTTP_SESSION_COOKIE = "leaf-page-local";
export const ACTIVE_COOKIE = "__Host-leaf-active";
export const HTTP_ACTIVE_COOKIE = "leaf-active-local";
export const CONTAINER_COOKIE = "__Host-leaf-container";
export const HTTP_CONTAINER_COOKIE = "leaf-container-local";

export interface PageRoute {
  root: string;
  inside: string;
  kind: "product" | "example";
  layer: string;
  state: string;
  states: Record<string, string>;
  assets: string;
}

export interface SitePage {
  assets: string;
  directory: string;
  kind: "product" | "example";
  layer: string;
  state: string;
  states: Record<string, string>;
}

export interface SiteManifest {
  release: string;
  pages: Record<string, SitePage>;
}

const PAGE_RESOURCE =
  /^(?:api|guidance|media|revisions|runtime|vendor|versions|widgets)(?:\/|$)|^(?:icon\.svg|leaf\.js|registry\.json|sitenote\.js|theme\.css)$/;
const SESSION_ID = /^[0-9a-f]{32}$/;

export function parseSiteManifest(value: unknown): SiteManifest {
  const manifest = value as Partial<SiteManifest> | null;
  if (
    manifest === null ||
    typeof manifest !== "object" ||
    typeof manifest.release !== "string" ||
    !/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/.test(manifest.release) ||
    manifest.pages === null ||
    typeof manifest.pages !== "object"
  ) {
    throw new Error("invalid Leaf site manifest");
  }
  for (const [root, page] of Object.entries(manifest.pages)) {
    if (
      (root !== "/" && !/^\/[a-z0-9-]+(?:\/[a-z0-9-]+)*$/.test(root)) ||
      page === null ||
      typeof page !== "object" ||
      !["product", "example"].includes(page.kind) ||
      typeof page.directory !== "string" ||
      !page.directory ||
      page.directory.startsWith("/") ||
      page.directory.split("/").includes("..") ||
      typeof page.assets !== "string" ||
      !/^\/_leaf-release\/(?:[0-9a-f]{40}|[0-9a-f]{64})\/[a-z0-9-]+$/.test(
        page.assets,
      ) ||
      !page.assets.startsWith(`/_leaf-release/${manifest.release}/`) ||
      typeof page.layer !== "string" ||
      !page.layer ||
      typeof page.state !== "string" ||
      !/^\/_leaf\/state\/[a-z0-9-]+\.json$/.test(page.state) ||
      page.states === null ||
      typeof page.states !== "object" ||
      !Object.keys(page.states).length ||
      !Object.entries(page.states).every(
        ([revision, state]) =>
          /^[1-9][0-9]*$/.test(revision) &&
          typeof state === "string" &&
          /^\/_leaf\/state\/[a-z0-9-]+\.json$/.test(state),
      ) ||
      !Object.values(page.states).includes(page.state)
    ) {
      throw new Error(`invalid Leaf site manifest page: ${root}`);
    }
  }
  return manifest as SiteManifest;
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

export function isPageMediaRequest(route: PageRoute | null): boolean {
  return route?.inside === "media" || route?.inside.startsWith("media/") || false;
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
