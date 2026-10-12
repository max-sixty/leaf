/**
 * Public Leaf site with edge reads and isolated canonical mutation sessions.
 *
 * Cloudflare serves the immutable live shell, initial state, and published data of each
 * product and example page at the edge. A request needing mutation starts the Python
 * Leaf server in a container selected by an opaque browser cookie. Disposable sample
 * URLs carry the opaque container object ID alongside their own random capability,
 * so an opaque-origin child uses native requests without a browser session cookie.
 * This routing reference selects a container only beneath that sample capability;
 * it grants no access to its parent page. The container starts
 * with the same complete page directories and writes only to its own ephemeral
 * filesystem, so one user can exercise the real event log without changing another
 * user's page.
 * Containers are scoped to the deployed release, so a rollout may reset this explicitly
 * ephemeral state but never sends a new document through an older user session. The
 * container image itself rolls out after the Worker is already live, so a fresh session
 * can still start on the previous release; the edge serves the published projection in
 * place of that container's answer rather than handing the browser a release no reload
 * can reach. A private revision that changes executable code marks its one required
 * container reload in the URL; every ordinary document navigation stays at the edge.
 * Accepted browser events start their agent task in the already-selected user
 * container without holding the browser acknowledgement open. A page fault reported
 * from a passive session is the published page failing, so the edge logs it for the
 * site's maintainers instead of activating a container to hold it. Analytics Engine
 * records accepted product events; Workers Observability records the execution path,
 * whose only page words are a bounded startup or fault `reason`.
 */

import { Container, getContainer } from "@cloudflare/containers";
export { ContainerProxy } from "@cloudflare/containers";
import { type DurableObject } from "cloudflare:workers";
import * as z from "zod/mini";

import { agentLog, dispatchAgentTask, prewarmContainer } from "./agent";
import { projectInteractionBatch, sampleInteractionReference } from "./interactions";
import { proxyModelRequest } from "./model-proxy";
import {
  activeCookie,
  activeFromCookie,
  clearActiveCookie,
  isLivePageDocumentRequest,
  isPageApiRequest,
  isPageSessionFileRequest,
  isPrivatePageRequest,
  needsPageSlash,
  newSessionId,
  pageRoute,
  releaseAssetRoute,
  sessionCookie,
  sessionFromCookie,
  sessionReference,
  type PageRoute,
  type SiteManifest,
} from "./routing";

export interface Env {
  ASSETS: Fetcher;
  PAGES: DurableObjectNamespace<LeafWebsiteSession>;
  AGENT_PREWARM: "true" | "false";
  WEBSITE_EVENTS: AnalyticsEngineDataset;
  SOURCE_AGENT_RATE_LIMITER: RateLimit;
  OPENAI_API_KEY: string;
}

const siteRelease = z.string().check(z.regex(/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/));
const startupTime = z.nullable(
  z.number().check(z.int(), z.nonnegative(), z.maximum(300_000)),
);
const startupReportSchema = z.strictObject({
  version: z.literal(2),
  loadId: z.string().check(z.regex(/^[0-9a-f]{32}$/)),
  release: siteRelease,
  layer: z.string().check(z.regex(/^[A-Za-z0-9_-]{1,128}$/)),
  outcome: z.union([
    z.literal("presented"),
    z.literal("failed"),
    z.literal("timeout"),
    z.literal("abandoned"),
  ]),
  // What went wrong on the way up, on whatever outcome the page reached: a page that
  // recovered from it reports `presented` and still says what it was. Absent where
  // nothing went wrong, and bounded by the same door that bounds the whole report.
  reason: z.optional(z.string().check(z.maxLength(300))),
  navigationType: z.union([
    z.literal("navigate"),
    z.literal("reload"),
    z.literal("back_forward"),
    z.literal("prerender"),
    z.literal("unknown"),
  ]),
  serverMs: startupTime,
  firstByteMs: startupTime,
  firstContentfulPaintMs: startupTime,
  upgradedMs: startupTime,
  firstStateResponseMs: startupTime,
  presentedMs: startupTime,
});
const MAX_STARTUP_BYTES = 2048;
// The fields of the runtime's `reportPageError` event the edge reads. Admission stays
// the container's: this only recognizes a fault, which the edge logs and never admits.
const pageFaultSchema = z.object({
  kind: z.literal("error"),
  text: z.string(),
  revision: z.optional(z.number()),
});
const MAX_PAGE_FAULT_BYTES = 64 * 1024;
// The startup report's `reason` bound, for the same kind of words.
const PAGE_FAULT_REASON_CHARS = 300;
// Workers Logs captures at most 256 KiB across the whole invocation. Leave room for
// request metadata so an accepted batch can be read back without truncation.
const MAX_INTERACTION_BYTES = 128 * 1024;
const CODEX_PROXY_CREDENTIAL = "leaf-outbound-proxy";
const CLOUDFLARE_CONTAINER_CA = "/etc/cloudflare/certs/cloudflare-containers-ca.crt";
interface LeafEvent {
  id: string;
  attempt?: string;
  kind: string;
  action?: string;
  revision?: number;
}

interface AcceptedEvent {
  event: LeafEvent;
  needsReply: boolean;
}

interface LeafStateAnswer {
  state?: {
    events?: LeafEvent[];
    activity?: { obligations?: Array<{ input: string | null }> };
  };
}

export class LeafWebsiteSession extends Container<Env> {
  defaultPort = 8080;
  pingEndpoint = "localhost/health";
  sleepAfter = "10m";
  enableInternet = false;
  interceptHttps = true;
  allowedHosts = ["api.openai.com"];

  constructor(ctx: DurableObject["ctx"], env: Env) {
    super(ctx, env);
    this.envVars = {
      LEAF_AGENT: "The agent",
      OPENAI_API_KEY: CODEX_PROXY_CREDENTIAL,
      CODEX_CA_CERTIFICATE: CLOUDFLARE_CONTAINER_CA,
    };
  }
}

// Assignment invokes Container's inherited setter, which registers the handler for
// ContainerProxy. A static class field would shadow that setter.
LeafWebsiteSession.outboundByHost = { "api.openai.com": proxyModelRequest };

function randomSessionId(): string {
  return newSessionId(crypto.getRandomValues(new Uint8Array(16)));
}

// Website sessions are explicitly ephemeral. A deployment starts a fresh container
// rather than routing a new static document through an older release to preserve demo
// state that the website does not promise to persist.
function containerId(sessionId: string, release: string): string {
  return `${release}:${sessionId}`;
}

function browserIdentity(request: Request): {
  browser: string;
  browserVersion: number | null;
  platform: string;
} {
  const userAgent = request.headers.get("User-Agent") ?? "";
  const browserPatterns: Array<[string, RegExp]> = [
    ["edge", /(?:Edg|EdgA|EdgiOS)\/(\d+)/],
    ["chrome", /(?:Chrome|CriOS)\/(\d+)/],
    ["firefox", /(?:Firefox|FxiOS)\/(\d+)/],
    ["safari", /Version\/(\d+).+Safari\//],
  ];
  const browserReading = browserPatterns
    .map(([browser, pattern]) => ({ browser, match: userAgent.match(pattern) }))
    .find(({ match }) => match !== null);
  const parsedVersion = browserReading ? Number(browserReading.match?.[1]) : null;
  const platform =
    /Windows/.test(userAgent)
      ? "windows"
      : /(?:iPhone|iPad)/.test(userAgent)
        ? "ios"
        : /Android/.test(userAgent)
          ? "android"
          : /CrOS/.test(userAgent)
            ? "chromeos"
            : /Macintosh/.test(userAgent)
              ? "macos"
              : /Linux/.test(userAgent)
                ? "linux"
                : "other";
  return {
    browser: browserReading?.browser ?? "other",
    browserVersion:
      parsedVersion !== null &&
      Number.isSafeInteger(parsedVersion) &&
      parsedVersion <= 9999
        ? parsedVersion
        : null,
    platform,
  };
}

// The body as text, or null once it passes maxBytes, whether the client declared that
// length or streamed it without one. A request with no body reads as "".
async function readBoundedText(request: Request, maxBytes: number): Promise<string | null> {
  if (Number(request.headers.get("Content-Length")) > maxBytes) return null;
  const reader = request.body?.getReader();
  if (!reader) return "";
  const decoder = new TextDecoder();
  let raw = "";
  let bytes = 0;
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    bytes += value.byteLength;
    if (bytes > maxBytes) {
      await reader.cancel();
      return null;
    }
    raw += decoder.decode(value, { stream: true });
  }
  return raw + decoder.decode();
}

async function recordStartup(
  request: Request,
  manifest: SiteManifest,
  route: PageRoute,
  reference: string,
): Promise<Response> {
  const raw = await readBoundedText(request, MAX_STARTUP_BYTES);
  if (raw === null) {
    return new Response("startup report is too large", { status: 413 });
  }
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return new Response("invalid startup report", { status: 400 });
  }
  const parsed = startupReportSchema.safeParse(value);
  if (!parsed.success) {
    return new Response("invalid startup report", { status: 400 });
  }
  console.log({
    component: "leaf-startup",
    event: "browser_startup",
    reference,
    route: route.root,
    currentRelease: manifest.release,
    ...browserIdentity(request),
    ...parsed.data,
  });
  return new Response(null, {
    status: 204,
    headers: { "Cache-Control": "no-store" },
  });
}

// A passive session reads the published page, whose author is the site. A fault it
// reports owes no reply, so it would start no agent work; in a container it would only
// wait for the visitor's first agent turn, whose agent did not write the page either. So
// it belongs beside the startup beacon, where the site's maintainers read, rather than in
// a private container activated to hold it. Null for any other event, which goes to the
// container as before.
async function pageFault(
  request: Request,
): Promise<z.infer<typeof pageFaultSchema> | null> {
  const raw = await readBoundedText(request.clone(), MAX_PAGE_FAULT_BYTES);
  if (raw === null) return null;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  const parsed = pageFaultSchema.safeParse(value);
  return parsed.success ? parsed.data : null;
}

function recordPageFault(
  request: Request,
  fault: z.infer<typeof pageFaultSchema>,
  manifest: SiteManifest,
  route: PageRoute,
  reference: string,
): Response {
  console.log({
    component: "leaf-page-error",
    event: "browser_page_error",
    reference,
    route: route.root,
    // The document's release, which a tab not yet reloaded past a deploy still names,
    // beside the edge's, as the startup record keeps them.
    release: siteRelease.safeParse(request.headers.get("Leaf-Release")).data ?? null,
    currentRelease: manifest.release,
    revision: fault.revision ?? null,
    ...browserIdentity(request),
    reason: fault.text.slice(0, PAGE_FAULT_REASON_CHARS),
  });
  const answer = new Response(null, {
    status: 204,
    headers: { "Cache-Control": "no-store", "Leaf-Session": "passive" },
  });
  stampDelivery(answer.headers, route, manifest, reference);
  return answer;
}

type InteractionIdentity =
  | { reference: string; sampleReference?: never }
  | { sampleReference: string; reference?: never };

async function recordInteractions(
  request: Request,
  route: PageRoute,
  identity: InteractionIdentity,
  release: string,
): Promise<Response> {
  const raw = await readBoundedText(request, MAX_INTERACTION_BYTES);
  if (raw === null)
    return new Response("interaction batch is too large", { status: 413 });
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return new Response("invalid interaction batch", { status: 400 });
  }
  const batch = projectInteractionBatch(value);
  if (batch === null)
    return new Response("invalid interaction batch", { status: 400 });
  console.log({
    component: "leaf-interaction",
    event: "client_batch",
    ...identity,
    route: route.root,
    release,
    ...batch,
  });
  return new Response(null, { status: 204, headers: { "Cache-Control": "no-store" } });
}

async function acceptedEvent(
  postedRequest: Request,
  response: Response,
): Promise<AcceptedEvent | null> {
  if (!response.ok) return null;
  try {
    const posted = (await postedRequest.json()) as { attempt?: unknown };
    if (typeof posted.attempt !== "string") return null;
    const answer = (await response.clone().json()) as LeafStateAnswer;
    const event = answer.state?.events?.find(
      (candidate) => candidate.attempt === posted.attempt,
    );
    if (!event) return null;
    return {
      event,
      needsReply:
        answer.state?.activity?.obligations?.some(
          (obligation) => obligation.input === event.id,
        ) ?? false,
    };
  } catch {
    return null;
  }
}

function recordAcceptedEvent(
  env: Env,
  route: PageRoute,
  release: string,
  reference: string,
  accepted: AcceptedEvent,
): void {
  env.WEBSITE_EVENTS.writeDataPoint({
    indexes: [accepted.event.id],
    blobs: [
      route.root,
      route.kind,
      accepted.event.kind,
      accepted.event.action ?? null,
      release,
      reference,
    ],
    doubles: [accepted.event.revision ?? 0, accepted.needsReply ? 1 : 0],
  });
}

// A fetched asset's headers are immutable, so this takes the one copy each edge answer
// to a static file makes; the stamps after it edit that copy in place.
function staticAssetResponse(response: Response, manifest: SiteManifest): Response {
  const answer = new Response(response.body, response);
  const contentType = response.headers.get("Content-Type")?.split(";", 1)[0].trim();
  if (contentType?.toLowerCase() === "text/html") {
    answer.headers.append("Content-Security-Policy", manifest.frame_ancestors);
  }
  return answer;
}

// The headers naming the release and layer an edge answer belongs to, and the session
// it answers when it answers one. Leaf-Session stays with each caller.
function stampDelivery(
  headers: Headers,
  route: PageRoute,
  manifest: SiteManifest,
  reference?: string,
): void {
  headers.set("Leaf-Layer", route.layer);
  headers.set("Leaf-Release", manifest.release);
  if (reference !== undefined) headers.set("Leaf-Session-Reference", reference);
}

const manifests = new WeakMap<object, Promise<SiteManifest>>();

async function siteManifest(request: Request, env: Env): Promise<SiteManifest> {
  let pending = manifests.get(env.ASSETS as object);
  if (!pending) {
    const url = new URL("/_leaf/site.json", request.url);
    pending = env.ASSETS.fetch(new Request(url)).then(async (response) => {
      if (!response.ok) throw new Error(`site manifest returned ${response.status}`);
      return (await response.json()) as SiteManifest;
    });
    manifests.set(env.ASSETS as object, pending);
    pending.catch(() => manifests.delete(env.ASSETS as object));
  }
  return pending;
}

function stampedStaticResponse(
  response: Response,
  route: PageRoute,
  manifest: SiteManifest,
): Response {
  const answer = staticAssetResponse(response, manifest);
  stampDelivery(answer.headers, route, manifest);
  return answer;
}

async function staticState(
  request: Request,
  env: Env,
  manifest: SiteManifest,
  route: PageRoute,
  reference: string,
): Promise<Response> {
  const viewRevision = request.headers.get("Leaf-View-Revision");
  const statePath = viewRevision === null ? route.state : route.states[viewRevision];
  if (statePath === undefined) {
    return new Response("unknown page revision", { status: 400 });
  }
  const url = new URL(statePath, request.url);
  const response = await env.ASSETS.fetch(new Request(url));
  if (!response.ok) return new Response("state unavailable", { status: 503 });
  const state = (await response.json()) as Record<string, unknown>;
  const now = new Date();
  state.now = now.toISOString();
  state.taken = now.getTime() / 1000;
  const answer = Response.json(state, {
    headers: { "Cache-Control": "no-store", "Leaf-Session": "passive" },
  });
  stampDelivery(answer.headers, route, manifest, reference);
  return answer;
}

// Cloudflare activates a Worker and its assets in one operation and rolls the container
// application's image out in another, so for the first minutes of a deployment the edge
// already serves the new release while containers still answer for the previous one. The
// browser's only move against a foreign release is to reload, and the document it would
// reload onto is the one this edge just gave it, so handing that answer on leaves the
// page restarting for as long as the rollout runs. The edge answers for itself instead:
// the user is unseated, reads the published projection at the release their document
// belongs to, and waits to send rather than landing a gesture in a container that is
// about to be replaced.
async function rollingOut(
  request: Request,
  env: Env,
  manifest: SiteManifest,
  route: PageRoute,
  reference: string,
  cookies: string[],
): Promise<Response> {
  let answer: Response;
  if (request.method === "GET" && route.inside === "api/state") {
    answer = await staticState(request, env, manifest, route, reference);
  } else {
    answer = new Response("this release is still starting", {
      status: 503,
      headers: { "Retry-After": "5", "Cache-Control": "no-store" },
    });
    stampDelivery(answer.headers, route, manifest, reference);
  }
  for (const cookie of cookies) answer.headers.append("Set-Cookie", cookie);
  return answer;
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const requestStarted = Date.now();
    const url = new URL(request.url);
    const pathname = url.pathname;
    if (isPrivatePageRequest(pathname)) {
      return new Response("not found", { status: 404 });
    }
    const manifest = await siteManifest(request, env);
    const releasedAsset = releaseAssetRoute(pathname, manifest);
    if (releasedAsset !== null) {
      if (request.method === "OPTIONS")
        return new Response(null, {
          status: 204,
          headers: {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, HEAD, OPTIONS",
            "Access-Control-Allow-Headers": "*",
          },
        });
      const assetUrl = new URL(request.url);
      assetUrl.pathname = releasedAsset.pathname;
      const response = stampedStaticResponse(
        await env.ASSETS.fetch(new Request(assetUrl, request)),
        releasedAsset.route,
        manifest,
      );
      response.headers.set("Cache-Control", "public, max-age=31536000, immutable");
      response.headers.set("Access-Control-Allow-Origin", "*");
      response.headers.set("Access-Control-Expose-Headers", "*");
      return response;
    }
    const route = pageRoute(pathname, manifest);
    if (route === null) {
      return staticAssetResponse(await env.ASSETS.fetch(request), manifest);
    }
    if (needsPageSlash(pathname, route)) {
      const canonical = new URL(request.url);
      canonical.pathname += "/";
      return Response.redirect(canonical.toString(), 308);
    }

    // An opaque sample has no session cookie. The first sample segment carries a
    // namespace object ID for routing; Python admits only the independent random
    // sample capability. Nested samples retain this first routing reference.
    const sample = /^api\/samples\/[a-f0-9]{32}~([a-f0-9]{64})(?:\/|$)/.exec(route.inside);
    if (sample) {
      let id: DurableObjectId;
      try {
        id = env.PAGES.idFromString(sample[1]);
      } catch {
        return new Response("not found", { status: 404 });
      }
      const sampleReference = request.method === "POST" && route.inside.endsWith("/api/interaction")
        ? sampleInteractionReference(`/${route.inside.slice(0, -"/api/interaction".length)}`)
        : null;
      const interaction = sampleReference === null ? null : { request: request.clone(), sampleReference };
      const fetched = await env.PAGES.get(id).fetch(request);
      const response = new Response(fetched.body, fetched);
      response.headers.delete("Set-Cookie");
      // Only the container can admit this capability. After admission, retain the
      // same bounded, redacted cloud evidence as a parent batch; the clone lets
      // the native request also keep its full local trace.
      if (interaction !== null && response.status === 204)
        await recordInteractions(interaction.request, route, { sampleReference: interaction.sampleReference }, manifest.release);
      return response;
    }

    const secure = url.protocol === "https:";
    const cookie = request.headers.get("Cookie");
    const existing = sessionFromCookie(cookie, secure);
    const active = activeFromCookie(cookie, secure, route.root);
    const sessionId = existing ?? randomSessionId();
    const privateContainer = containerId(sessionId, manifest.release);
    const reference = sessionReference(sessionId);
    if (request.method === "POST" && route.inside === "api/performance") {
      if (existing === null) {
        return new Response("startup report has no page session", { status: 400 });
      }
      return recordStartup(request, manifest, route, reference);
    }
    if (request.method === "POST" && route.inside === "api/interaction") {
      if (existing === null) {
        return new Response("interaction batch has no page session", { status: 400 });
      }
      return recordInteractions(request, route, { reference }, manifest.release);
    }
    if (!active && request.method === "POST" && route.inside === "api/event") {
      const fault = await pageFault(request);
      if (fault !== null) {
        if (existing === null) {
          return new Response("page error has no page session", { status: 400 });
        }
        return recordPageFault(request, fault, manifest, route, reference);
      }
    }
    if (
      !active &&
      request.method === "GET" &&
      route.inside === "api/state"
    ) {
      return staticState(request, env, manifest, route, reference);
    }
    // Documents always come from the edge. The only exception is the one reload the
    // runtime marks after learning that a private revision changed executable code; its
    // current container owns that document. The runtime removes the marker on arrival,
    // so ordinary reloads and later visits return to the static shell.
    const privateRevision = url.searchParams.get("_leaf-revision");
    const privateDocumentReload =
      existing !== null &&
      active &&
      isLivePageDocumentRequest(route) &&
      /^[1-9][0-9]*$/.test(privateRevision ?? "");
    if (
      (request.method === "GET" || request.method === "HEAD") &&
      !isPageApiRequest(route) &&
      !privateDocumentReload
    ) {
      const response = stampedStaticResponse(
        await env.ASSETS.fetch(request),
        route,
        manifest,
      );
      if (
        response.status !== 404 ||
        !isPageSessionFileRequest(route, manifest) ||
        existing === null ||
        !active
      ) {
        if (!response.headers.get("Content-Type")?.startsWith("text/html")) {
          return response;
        }
        response.headers.set("Leaf-Session-Reference", reference);
        response.headers.set("Server-Timing", `leaf;dur=${Date.now() - requestStarted}`);
        if (existing === null) {
          response.headers.append("Set-Cookie", sessionCookie(sessionId, secure));
        }
        if (
          env.AGENT_PREWARM === "true" &&
          request.method === "GET" &&
          request.headers.get("Sec-Fetch-Dest") === "document"
        ) {
          const sourceId = request.headers.get("CF-Connecting-IP") ?? "unknown";
          ctx.waitUntil(
            prewarmContainer(
              env,
              privateContainer,
              reference,
              route.root,
              sourceId,
            ),
          );
        }
        return response;
      }
    }
    const postedRequest =
      request.method === "POST" && route.inside === "api/event"
        ? request.clone()
        : null;
    const response = await getContainer(env.PAGES, privateContainer).fetch(request);
    const containerRelease = response.headers.get("Leaf-Release");
    if (containerRelease !== null && containerRelease !== manifest.release) {
      const cookies = [clearActiveCookie(secure, route.root)];
      if (existing === null) cookies.push(sessionCookie(sessionId, secure));
      return rollingOut(request, env, manifest, route, reference, cookies);
    }
    if (postedRequest) {
      const accepted = await acceptedEvent(postedRequest, response);
      if (accepted) {
        recordAcceptedEvent(env, route, manifest.release, reference, accepted);
      }
      if (accepted?.needsReply) {
        const sourceId = request.headers.get("CF-Connecting-IP") ?? sessionId;
        const params = {
          containerId: privateContainer,
          reference,
          route: route.root,
          eventId: accepted.event.id,
          sourceId,
        };
        agentLog("event_accepted", params, {
          durationMs: Date.now() - requestStarted,
        });
        // TODO: a dispatch does not yet survive its container (TODO.md, "Make a
        // leaf.page dispatch survive its container").
        ctx.waitUntil(dispatchAgentTask(env, params));
      }
    }
    let body: BodyInit | null = response.body;
    if (request.method === "POST" && route.inside === "api/samples" && response.ok) {
      const answer = await response.json() as { url: string; page: string };
      const allocated = new URL(answer.url, request.url);
      const objectId = env.PAGES.idFromName(privateContainer).toString();
      allocated.pathname = `${allocated.pathname.slice(0, -1)}~${objectId}/`;
      answer.url = allocated.pathname;
      answer.page = `${answer.page}~${objectId}`;
      body = JSON.stringify(answer);
    }
    const answer = new Response(body, response);
    if (body !== response.body) {
      answer.headers.delete("Content-Length");
      answer.headers.delete("Content-Encoding");
    }
    answer.headers.set("Leaf-Session", "active");
    answer.headers.set("Leaf-Session-Reference", reference);
    if (existing === null) {
      answer.headers.append("Set-Cookie", sessionCookie(sessionId, secure));
    }
    if (!active) answer.headers.append("Set-Cookie", activeCookie(secure, route.root));
    if (response.headers.get("Content-Type")?.startsWith("text/html")) {
      answer.headers.set("Server-Timing", `leaf;dur=${Date.now() - requestStarted}`);
    }
    return answer;
  },
};
