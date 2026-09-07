/** Pure request routing for the public Leaf pages. */

export const SESSION_COOKIE = "__Host-leaf-page";
export const HTTP_SESSION_COOKIE = "leaf-page-local";

export interface PageRoute {
  root: string;
  inside: string;
  kind: "product" | "example";
}

const PRODUCT_ROOTS = ["/examples", "/how-it-works", "/packages", "/registry"];
const PRODUCT_ROOT_SET = new Set(["/", ...PRODUCT_ROOTS]);
const PAGE_RESOURCE =
  /^(?:api|guidance|media|revisions|runtime|vendor|versions|widgets)(?:\/|$)|^(?:icon\.svg|leaf\.js|registry\.json|theme\.css)$/;
const EXAMPLE_ROUTE = /^\/examples\/([a-z0-9-]+)(?:\/(.*))?$/;
const EXAMPLE_WITHOUT_SLASH = /^\/examples\/[a-z0-9-]+$/;
const SESSION_ID = /^[0-9a-f]{32}$/;

export function pageRoute(pathname: string): PageRoute | null {
  if (pathname === "/") return { root: "/", inside: "", kind: "product" };

  for (const root of PRODUCT_ROOTS.filter((candidate) => candidate !== "/examples")) {
    if (pathname === root || pathname === `${root}/`) {
      return { root, inside: "", kind: "product" };
    }
    if (pathname.startsWith(`${root}/`)) {
      return { root, inside: pathname.slice(root.length + 1), kind: "product" };
    }
  }

  if (pathname === "/examples" || pathname === "/examples/") {
    return { root: "/examples", inside: "", kind: "product" };
  }
  if (pathname.startsWith("/examples/")) {
    const inside = pathname.slice("/examples/".length);
    if (PAGE_RESOURCE.test(inside)) {
      return { root: "/examples", inside, kind: "product" };
    }
    const example = EXAMPLE_ROUTE.exec(pathname);
    if (example !== null) {
      return {
        root: `/examples/${example[1]}`,
        inside: example[2] ?? "",
        kind: "example",
      };
    }
  }

  const inside = pathname.slice(1);
  return PAGE_RESOURCE.test(inside) ? { root: "/", inside, kind: "product" } : null;
}

export function isPageRequest(pathname: string): boolean {
  return pageRoute(pathname) !== null;
}

export function isPageApiRequest(pathname: string): boolean {
  const route = pageRoute(pathname);
  return route?.inside === "api" || route?.inside.startsWith("api/") || false;
}

export function isPageMediaRequest(pathname: string): boolean {
  const route = pageRoute(pathname);
  return route?.inside === "media" || route?.inside.startsWith("media/") || false;
}

export function needsPageSlash(pathname: string): boolean {
  return (
    (PRODUCT_ROOT_SET.has(pathname) && pathname !== "/") ||
    EXAMPLE_WITHOUT_SLASH.test(pathname)
  );
}

export function isPrivatePageRequest(pathname: string): boolean {
  return (
    pathname === "/_leaf" ||
    pathname.startsWith("/_leaf/") ||
    (pageRoute(pathname)?.inside.startsWith("_leaf/") ?? false)
  );
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
