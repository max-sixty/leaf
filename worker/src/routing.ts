/** Pure request routing for the public site worker. */

export const SESSION_COOKIE = "__Host-leaf-example";
export const HTTP_SESSION_COOKIE = "leaf-example-local";

const EXAMPLE_PATH = /^\/examples\/[a-z0-9-]+(?:\/|$)/;
const EXAMPLE_WITHOUT_SLASH = /^\/examples\/[a-z0-9-]+$/;
const SESSION_ID = /^[0-9a-f]{32}$/;

export function isExampleRequest(pathname: string): boolean {
  return EXAMPLE_PATH.test(pathname);
}

export function needsExampleSlash(pathname: string): boolean {
  return EXAMPLE_WITHOUT_SLASH.test(pathname);
}

export function sessionFromCookie(cookie: string | null, secure: boolean): string | null {
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
  return `${name}=${sessionId}; Path=/${security}; HttpOnly; SameSite=Strict`;
}
