/** Pure request routing for the public site worker. */

export const SESSION_COOKIE = "__Host-leaf-example";

const EXAMPLE_PATH = /^\/examples\/[a-z0-9-]+(?:\/|$)/;
const EXAMPLE_WITHOUT_SLASH = /^\/examples\/[a-z0-9-]+$/;
const SESSION_ID = /^[0-9a-f]{32}$/;

export function isExampleRequest(pathname: string): boolean {
  return EXAMPLE_PATH.test(pathname);
}

export function needsExampleSlash(pathname: string): boolean {
  return EXAMPLE_WITHOUT_SLASH.test(pathname);
}

export function sessionFromCookie(cookie: string | null): string | null {
  if (cookie === null) return null;
  for (const item of cookie.split(";")) {
    const [name, ...value] = item.trim().split("=");
    if (name === SESSION_COOKIE) {
      const candidate = value.join("=");
      return SESSION_ID.test(candidate) ? candidate : null;
    }
  }
  return null;
}

export function newSessionId(random: Uint8Array): string {
  if (random.byteLength !== 16) {
    throw new Error("a Leaf website session id needs exactly 16 random bytes");
  }
  return Array.from(random, (byte) => byte.toString(16).padStart(2, "0")).join("");
}

export function sessionCookie(sessionId: string): string {
  if (!SESSION_ID.test(sessionId)) throw new Error("invalid Leaf website session id");
  return `${SESSION_COOKIE}=${sessionId}; Path=/; Secure; HttpOnly; SameSite=Strict`;
}
