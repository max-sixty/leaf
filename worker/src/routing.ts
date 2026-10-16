/** Pure request routing for the public Leaf pages. */

export const SESSION_COOKIE = "__Host-leaf-page";
export const HTTP_SESSION_COOKIE = "leaf-page-local";
export const ACTIVE_COOKIE_PREFIX = "__Host-leaf-active";
export const HTTP_ACTIVE_COOKIE_PREFIX = "leaf-active-local";

const SESSION_ID = /^[0-9a-f]{32}$/;

// The manifest `leaf-dev site` writes beside the assets (`dev/leaf_dev/commands/site.py`), which
// ships in the same release as this Worker. The build constructs each field: the asset
// path from the release, the state from the page's current revision, the image from a
// media file `check_links` proves resolves, and the title and description from the
// page's head, which the build refuses without them. The fields the container alone
// reads, such as each page's build directory, are left out.
interface SitePage {
  /** `/_leaf-release/{release}/{key}`. */
  assets: string;
  description: string;
  /** The card image a shared link unfurls into: a path on this site, which the
   * container's page head joins to the origin. */
  image: string;
  kind: "product" | "example";
  layer: string;
  /** The current revision's entry in `states`. */
  state: string;
  /** Each revision's published projection, keyed by revision number. */
  states: Record<string, string>;
  title: string;
}

// A page's URL namespace beneath its root, by kind: its browser layer's directories,
// the directories its session writes, and the vendored files (`schema.BROWSER_DIRS`,
// `SESSION_ROUTE_DIRS`, `VENDORED_FILES`). The API directory is the page server's
// protocol prefix, fixed with the endpoints under it that this Worker handles by name.
const API_DIR = "api";
interface PageRoutes {
  layer: string[];
  session: string[];
  files: string[];
}

export interface SiteManifest {
  release: string;
  /** The header policy every HTML response adds, since a document's own <meta>
   * policy cannot govern its ancestors (`structure.FRAME_ANCESTORS_CSP`). */
  frame_ancestors: string;
  routes: PageRoutes;
  /** Keyed by public root: `/` or `/segment(/segment)*`. */
  pages: Record<string, SitePage>;
}

export type PageRoute = SitePage & {
  root: string;
  inside: string;
};

const within = (dirs: string[], inside: string): boolean =>
  dirs.some((dir) => inside === dir || inside.startsWith(`${dir}/`));

function pageResource(routes: PageRoutes, inside: string): boolean {
  return (
    routes.files.includes(inside) ||
    within([API_DIR, ...routes.layer, ...routes.session], inside)
  );
}

export function releaseAssetRoute(
  pathname: string,
  { pages, routes }: SiteManifest,
): { route: PageRoute; pathname: string } | null {
  for (const [root, page] of Object.entries(pages)) {
    if (!pathname.startsWith(`${page.assets}/`)) continue;
    const inside = pathname.slice(page.assets.length + 1);
    if (!pageResource(routes, inside) || within([API_DIR], inside)) return null;
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
  { pages, routes }: SiteManifest,
): PageRoute | null {
  const roots = Object.keys(pages).sort((left, right) => right.length - left.length);
  for (const root of roots) {
    const publicRoot = root === "/" ? "" : root;
    let inside: string;
    if (pathname === (publicRoot || "/") || pathname === `${publicRoot}/`) {
      inside = "";
    } else if (pathname.startsWith(`${publicRoot}/`)) {
      inside = pathname.slice(publicRoot.length + 1);
      if (!pageResource(routes, inside)) continue;
    } else {
      continue;
    }
    return { root, inside, ...pages[root] };
  }
  return null;
}

export function isPageApiRequest(route: PageRoute | null): boolean {
  return route !== null && within([API_DIR], route.inside);
}

/** A file the page's session writes after its publish, which a static miss may still
 * find in its container. */
export function isPageSessionFileRequest(
  route: PageRoute | null,
  { routes }: SiteManifest,
): boolean {
  return route !== null && within(routes.session, route.inside);
}

/** The page's live document: the stable address a revision activates by reloading. */
export function isLivePageDocumentRequest(route: PageRoute | null): boolean {
  return route?.inside === "";
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

/** Activation selects a private record in one release, like its Durable Object key. */
export function activeFromCookie(
  cookie: string | null,
  secure: boolean,
  pageRoot: string,
  release: string,
): boolean {
  if (cookie === null) return false;
  const prefix = secure ? ACTIVE_COOKIE_PREFIX : HTTP_ACTIVE_COOKIE_PREFIX;
  const expected = pageCookieName(prefix, pageRoot);
  return cookie.split(";").some((item) => item.trim() === `${expected}=${release}`);
}

function pageCookieName(prefix: string, pageRoot: string): string {
  const suffix =
    pageRoot === "/" ? "root" : `page-${pageRoot.slice(1).replaceAll("/", "_")}`;
  return `${prefix}-${suffix}`;
}

export function newSessionId(random: Uint8Array): string {
  return Array.from(random, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

// A support handle, not a credential: project a random identity into a short numeric
// space without disclosing it. No server door accepts this handle as identity.
export function sessionReference(sessionId: string): string {
  return (BigInt(`0x${sessionId}`) % 1_000_000_000_000n).toString().padStart(12, "0");
}

export function sessionCookie(sessionId: string, secure: boolean): string {
  const name = secure ? SESSION_COOKIE : HTTP_SESSION_COOKIE;
  const security = secure ? "; Secure" : "";
  return `${name}=${sessionId}; Path=/${security}; HttpOnly; SameSite=Lax`;
}

function pageActiveCookie(secure: boolean, pageRoot: string, value: string): string {
  const prefix = secure ? ACTIVE_COOKIE_PREFIX : HTTP_ACTIVE_COOKIE_PREFIX;
  const name = pageCookieName(prefix, pageRoot);
  const security = secure ? "; Secure" : "";
  return `${name}=${value}; Path=/${security}; HttpOnly; SameSite=Lax`;
}

export function activeCookie(
  secure: boolean,
  pageRoot: string,
  release: string,
): string {
  return pageActiveCookie(secure, pageRoot, release);
}

// The marker selects the page's private record, so it has to go when
// the user is put back on the published projection; leaving it and ignoring it would
// send the next read to that private record again.
export function clearActiveCookie(secure: boolean, pageRoot: string): string {
  return `${pageActiveCookie(secure, pageRoot, "")}; Max-Age=0`;
}
