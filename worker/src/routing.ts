/** Pure request routing for the public Leaf pages. */

export const SESSION_COOKIE = "__Host-leaf-page";
export const HTTP_SESSION_COOKIE = "leaf-page-local";
export const ACTIVE_COOKIE_PREFIX = "__Host-leaf-active";
export const HTTP_ACTIVE_COOKIE_PREFIX = "leaf-active-local";

const SESSION_ID = /^[0-9a-f]{32}$/;

// The manifest `leaf-dev site build` writes beside the assets (`dev/leaf_dev/commands/site/_build.py`), which
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
  /** Each revision's published projection, keyed by revision number. A request may
   * name a revision the page lacks. */
  states: Partial<Record<string, string>>;
  title: string;
}

// A page's URL namespace beneath its root, by kind: its browser layer's directories,
// the directories its session writes, and the layer's top files (`schema.BROWSER_DIRS`,
// `SESSION_ROUTE_DIRS`, `LAYER_TOP_FILES`). The API directory is the page server's
// protocol prefix, fixed with the endpoints under it that this Worker handles by name.
const API_DIR = "api";
const VERSIONS_DIR = "versions";
interface PageRoutes {
  layer: string[];
  session: string[];
  files: string[];
}

export interface SiteManifest {
  release: string;
  /** The page protocol this release's Leaf serves and writes (`kernel_protocol`). */
  protocol: number;
  /** The `format` of the drafts record this release's Leaf keeps (`DRAFTS` in
   * `src/leaf/serving/drafts.py`), which keys a page's drafts store (`storage.ts`). */
  drafts_format: string;
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

/** One of the page's stamped versions, `versions/vN.html` (`schema.VERSION_NAME`), the
 * session directory whose files are named by number rather than by content. */
export function isPageVersionRequest(route: PageRoute | null): boolean {
  return route?.inside.startsWith(`${VERSIONS_DIR}/`) ?? false;
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

/** Activation selects a private record in one record scope (`recordScope` in
 * `index.ts`), like its Durable Object key. */
export function activeFromCookie(
  cookie: string | null,
  secure: boolean,
  pageRoot: string,
  scope: string,
): boolean {
  if (cookie === null) return false;
  const prefix = secure ? ACTIVE_COOKIE_PREFIX : HTTP_ACTIVE_COOKIE_PREFIX;
  const expected = pageCookieName(prefix, pageRoot);
  return cookie.split(";").some((item) => item.trim() === `${expected}=${scope}`);
}

function pageCookieName(prefix: string, pageRoot: string): string {
  // URI encoding preserves path identity. Parentheses are URI-safe but cookie-name
  // separators, so encode those too.
  const path = encodeURIComponent(pageRoot.slice(1))
    .replaceAll("(", "%28")
    .replaceAll(")", "%29");
  const suffix = pageRoot === "/" ? "root" : `page-${path}`;
  return `${prefix}-${suffix}`;
}

// The lowercase hex of `bytes`, which names a session minted from random bytes and a
// stored chunk by its digest.
export function hex(bytes: Uint8Array): string {
  return Array.from(bytes, (byte) => byte.toString(16).padStart(2, "0")).join("");
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

export function activeCookie(secure: boolean, pageRoot: string, scope: string): string {
  const prefix = secure ? ACTIVE_COOKIE_PREFIX : HTTP_ACTIVE_COOKIE_PREFIX;
  const name = pageCookieName(prefix, pageRoot);
  const security = secure ? "; Secure" : "";
  return `${name}=${scope}; Path=/${security}; HttpOnly; SameSite=Lax`;
}
