/**
 * Public Leaf site with edge reads and isolated canonical mutation sessions.
 *
 * Cloudflare serves untouched pages at the edge. A browser cookie selects a private,
 * release-scoped Durable Object holding canonical page records and Python-produced
 * dormant responses. Saved content loads without starting Linux. Mutations wake the
 * Python Leaf server, which restores the record before admission and publishes the
 * record and matching delivery atomically before acknowledgement. Python owns all
 * event and activity rules; this Worker stores and routes their output.
 * New releases select new demo records. A previous container image during rollout is
 * refused rather than letting it interpret the new release's document.
 * Disposable sample URLs carry the opaque container object ID alongside their own
 * random capability, so an opaque-origin child uses native requests without a browser
 * session cookie. This routing reference selects a container only beneath that sample
 * capability; it grants no access to its parent page.
 * Accepted browser events start their agent task in the already-selected user
 * container without holding the browser acknowledgement open. A page fault reported
 * from a passive session is the published page failing, so the edge logs it for the
 * site's maintainers instead of activating a container to hold it. The runtime's other
 * reports from a passive session, its viewport geometry and the messages it has shown
 * whole, are answered there unrecorded, since neither is a gesture that opens private
 * state. Analytics Engine
 * records accepted product events; Workers Observability records the execution path,
 * whose only page words are a bounded startup or fault `reason`. Native invocation
 * logs hold request headers; browser diagnostics read that evidence by trace ID.
 */

import {
  Container,
  getContainer,
  type OutboundHandlerContext,
} from "@cloudflare/containers";
export { ContainerProxy } from "@cloudflare/containers";
import { type DurableObject } from "cloudflare:workers";
import * as z from "zod/mini";
import type {
  Event,
  ServedEventAnswer,
  ServedSampleAnswer,
  ServedState,
} from "../../browser/types/contract.js";
import {
  CHUNK_BYTES,
  PageStore,
  dateStateDelivery,
  readPublication,
  readPublicationCommit,
} from "./storage";

import { agentLog, dispatchAgentTask } from "./agent";
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
  WEBSITE_EVENTS: AnalyticsEngineDataset;
  SOURCE_AGENT_RATE_LIMITER: RateLimit;
  OPENAI_API_KEY: string;
}

const siteRelease = z.string().check(z.regex(/^(?:[0-9a-f]{40}|[0-9a-f]{64})$/));
// A slow state response is still startup evidence. Bound the request body below,
// not the duration the browser can observe while its upgraded page waits.
const startupTime = z.nullable(z.number().check(z.int(), z.nonnegative()));
const startupReportSchema = z.strictObject({
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
// The fields of the runtime's `read` event the edge reads, to answer it unrecorded.
const pageReadSchema = z.object({
  kind: z.literal("read"),
  attempt: z.optional(z.string()),
});
const passiveEventSchema = z.union([pageFaultSchema, pageReadSchema]);
const MAX_PASSIVE_EVENT_BYTES = 64 * 1024;
// The startup report's `reason` bound, for the same kind of words.
const PAGE_FAULT_REASON_CHARS = 300;
// Workers Logs captures at most 256 KiB across the whole invocation. Leave room for
// request metadata so an accepted batch can be read back without truncation.
const MAX_INTERACTION_BYTES = 128 * 1024;
const CODEX_PROXY_CREDENTIAL = "leaf-outbound-proxy";
const CLOUDFLARE_CONTAINER_CA = "/etc/cloudflare/certs/cloudflare-containers-ca.crt";
interface AcceptedEvent {
  event: Event;
  needsReply: boolean;
}

export class LeafWebsiteSession extends Container<Env> {
  defaultPort = 8080;
  pingEndpoint = "localhost/health";
  sleepAfter = "10m";
  enableInternet = false;
  interceptHttps = true;
  allowedHosts = ["api.openai.com", "leaf-state.internal"];
  private pages: PageStore;

  constructor(ctx: DurableObject["ctx"], env: Env) {
    super(ctx, env);
    this.pages = new PageStore(ctx.storage);
    this.envVars = {
      LEAF_AGENT: "Agent",
      OPENAI_API_KEY: CODEX_PROXY_CREDENTIAL,
      CODEX_CA_CERTIFICATE: CLOUDFLARE_CONTAINER_CA,
      LEAF_PAGE_STORE_URL: "https://leaf-state.internal",
    };
  }

  savedRecords(): Response {
    return this.pages.records();
  }

  async saveBlob(digest: string, bytes: ArrayBuffer): Promise<void> {
    await this.pages.saveBlob(digest, bytes);
  }

  async preparePublication(
    value: unknown,
  ): Promise<{ identity: string; missing: string[] }> {
    const publication = readPublication(value);
    const manifest = await siteManifest(new Request("https://leaf.page/"), this.env);
    return this.pages.prepare(publication, manifest);
  }

  async savePublication(value: unknown): Promise<void> {
    const commit = readPublicationCommit(value);
    const manifest = await siteManifest(new Request("https://leaf.page/"), this.env);
    this.pages.publish(commit, manifest);
  }

  private async forward(request: Request): Promise<Response> {
    const response = await super.fetch(request);
    if (response.status >= 500) {
      // The Containers SDK converts connection loss into an ordinary 500 without
      // logging an exception. Python stamps its own answers and logs page_fault;
      // retain the missing proxy evidence, never the body or private request URL.
      const adapter = response.headers.has("Leaf-Release");
      const body = adapter
        ? null
        : await readBoundedText(response.clone(), 1024).catch(() => null);
      console.error({
        component: "leaf-container",
        event: "http_error",
        method: request.method,
        status: response.status,
        source: adapter
          ? "adapter"
          : body === "Container suddenly disconnected, try again"
            ? "disconnected"
            : "unclassified",
      });
    }
    return response;
  }

  override async fetch(request: Request): Promise<Response> {
    if (!this.ctx.container?.running) {
      const url = new URL(request.url);
      const manifest = await siteManifest(request, this.env);
      const route = pageRoute(url.pathname, manifest);
      if (route !== null) {
        // Optional viewport observations are useful only to a running agent.
        // Like captured previews, a dormant page acknowledges them without work.
        if (request.method === "POST" && route.inside === "api/user-view") {
          return new Response(null, { status: 204 });
        }
        if (request.method !== "GET" && request.method !== "HEAD") {
          return this.forward(request);
        }
        let path = route.inside;
        if (path === "api/state") {
          const revision =
            url.searchParams.get("revision") ||
            request.headers.get("Leaf-View-Revision");
          if (revision) path += `?revision=${revision}`;
        } else if (path === "api/deferred") {
          path += `?${new URLSearchParams({
            source: url.searchParams.get("source") ?? "",
            source_revision: url.searchParams.get("source_revision") ?? "",
            key: url.searchParams.get("key") ?? "",
          })}`;
        }
        const response = await this.pages.response(
          route.root,
          path,
          request.method === "HEAD",
        );
        if (response !== null) return response;
      }
    }
    return this.forward(request);
  }
}

// Assignment invokes Container's inherited setter, which registers the handler for
// ContainerProxy. A static class field would shadow that setter.
LeafWebsiteSession.outboundByHost = {
  "leaf-state.internal": async (
    request: Request,
    env: Env,
    ctx: OutboundHandlerContext,
  ) => {
    // The proxy supplies the owning DO identity. The container cannot select a
    // different user's session by changing a URL, cookie, or request header.
    const session = env.PAGES.get(env.PAGES.idFromString(ctx.containerId));
    const path = new URL(request.url).pathname;
    if (request.method === "GET" && path === "/records") {
      return session.savedRecords();
    }
    if (request.method === "PUT" && path === "/prepare") {
      return Response.json(await session.preparePublication(await request.json()));
    }
    const blob = /^\/blobs\/([0-9a-f]{64})$/.exec(path);
    if (blob !== null && request.method === "PUT") {
      // Bound the body before it crosses the RPC boundary or enters SQLite.
      let length = 0;
      const body = request.body?.pipeThrough(
        new TransformStream<Uint8Array, Uint8Array>({
          transform(chunk, controller) {
            length += chunk.byteLength;
            if (length > CHUNK_BYTES)
              throw new Error("page storage chunk exceeds 1 MiB");
            controller.enqueue(chunk);
          },
        }),
      );
      await session.saveBlob(blob[1], await new Response(body).arrayBuffer());
      return new Response(null, { status: 204 });
    }
    if (request.method === "PUT" && path === "/publication") {
      await session.savePublication(await request.json());
      return new Response(null, { status: 204 });
    }
    return new Response("unknown page storage operation", { status: 404 });
  },
  "api.openai.com": proxyModelRequest,
};

function randomSessionId(): string {
  return newSessionId(crypto.getRandomValues(new Uint8Array(16)));
}

// A release selects its own durable record and container; new code never interprets
// a different release’s demo state. Container replacement keeps the same record.
function containerId(sessionId: string, release: string): string {
  return `${release}:${sessionId}`;
}

// The body as text, or null once it passes maxBytes, whether the client declared that
// length or streamed it without one. A request with no body reads as "".
async function readBoundedText(
  request: Request | Response,
  maxBytes: number,
): Promise<string | null> {
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
      // A cloned response shares its source: cancellation completes only when
      // the caller consumes the other branch. Release this reader without waiting.
      void reader.cancel().catch(() => {});
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
    ...parsed.data,
  });
  return new Response(null, {
    status: 204,
    headers: { "Cache-Control": "no-store" },
  });
}

// The events a passive session's runtime sends on its own, which the edge answers
// rather than activating a private container to hold them. Null for any other event,
// which goes to the container as before.
//
// A passive session reads the published page, whose author is the site. A fault it
// reports owes no reply, so it would start no agent work; in a container it would only
// wait for the visitor's first agent turn, whose agent did not write the page either. So
// it belongs beside the startup beacon, where the site's maintainers read
// (`recordPageFault`). A read is the runtime's report that an agent message was on
// screen, not a gesture, so like geometry it opens no private state (`unrecordedRead`).
async function passiveEvent(
  request: Request,
): Promise<z.infer<typeof passiveEventSchema> | null> {
  const raw = await readBoundedText(request.clone(), MAX_PASSIVE_EVENT_BYTES);
  if (raw === null) return null;
  let value: unknown;
  try {
    value = JSON.parse(raw);
  } catch {
    return null;
  }
  const parsed = passiveEventSchema.safeParse(value);
  return parsed.success ? parsed.data : null;
}

// The runtime sends no read until its session is active (`thread/read.js`), so this
// answers one that arrives anyway, as from a tab whose runtime predates that rule. It
// is refused as final, which the runtime takes as "don't send it again this visit", and
// under a 200, since a browser logs a failed fetch as a console error.
function unrecordedRead(
  read: z.infer<typeof pageReadSchema>,
  manifest: SiteManifest,
  route: PageRoute,
  reference: string,
): Response {
  const refusal: ServedEventAnswer = {
    ok: false,
    final: true,
    error: "A published page records no reads until you act on it",
    findings: [],
    ...(read.attempt !== undefined && { attempt: read.attempt }),
  };
  const answer = Response.json(refusal, {
    headers: { "Cache-Control": "no-store", "Leaf-Session": "passive" },
  });
  stampDelivery(answer.headers, route, manifest, reference);
  return answer;
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
  if (batch === null) return new Response("invalid interaction batch", { status: 400 });
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
    // An accepted event's answer carries the page's state (`event_endpoint.accept_event`).
    const answer = (await response.clone().json()) as ServedEventAnswer;
    if (answer.ok !== true) return null;
    const { state } = answer;
    const event = state.events.find(
      (candidate) => candidate.attempt === posted.attempt,
    );
    if (!event) return null;
    // An update the agent owes an answer publishes its own obligation, on the agent
    // until it answers (`obligations.update_obligation`).
    return {
      event,
      needsReply: state.activity.obligations.includes(`update:${event.id}`),
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
  const viewRevision =
    new URL(request.url).searchParams.get("revision") ||
    request.headers.get("Leaf-View-Revision");
  const statePath = viewRevision === null ? route.state : route.states[viewRevision];
  if (statePath === undefined) {
    return new Response("unknown page revision", { status: 400 });
  }
  const url = new URL(statePath, request.url);
  const response = await env.ASSETS.fetch(new Request(url));
  if (!response.ok) return new Response("state unavailable", { status: 503 });
  const state = (await response.json()) as ServedState;
  dateStateDelivery(state);
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
    const sample = /^api\/samples\/[a-f0-9]{32}~([a-f0-9]{64})(?:\/|$)/.exec(
      route.inside,
    );
    if (sample) {
      let id: DurableObjectId;
      try {
        id = env.PAGES.idFromString(sample[1]);
      } catch {
        return new Response("not found", { status: 404 });
      }
      const sampleReference =
        request.method === "POST" && route.inside.endsWith("/api/interaction")
          ? sampleInteractionReference(
              `/${route.inside.slice(0, -"/api/interaction".length)}`,
            )
          : null;
      const interaction =
        sampleReference === null ? null : { request: request.clone(), sampleReference };
      const fetched = await env.PAGES.get(id).fetch(request);
      const response = new Response(fetched.body, fetched);
      response.headers.delete("Set-Cookie");
      // Only the container can admit this capability. After admission, retain the
      // same bounded, redacted cloud evidence as a parent batch; the clone lets
      // the native request also keep its full local trace.
      if (interaction !== null && response.status === 204)
        await recordInteractions(
          interaction.request,
          route,
          { sampleReference: interaction.sampleReference },
          manifest.release,
        );
      return response;
    }

    const secure = url.protocol === "https:";
    const cookie = request.headers.get("Cookie");
    const existing = sessionFromCookie(cookie, secure);
    const active = activeFromCookie(cookie, secure, route.root, manifest.release);
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
    // Geometry is disposable observation, not a gesture that opens private state.
    if (!active && request.method === "POST" && route.inside === "api/user-view") {
      return new Response(null, { status: 204 });
    }
    if (!active && request.method === "POST" && route.inside === "api/event") {
      const event = await passiveEvent(request);
      if (event?.kind === "read") {
        return unrecordedRead(event, manifest, route, reference);
      }
      if (event?.kind === "error") {
        if (existing === null) {
          return new Response("page error has no page session", { status: 400 });
        }
        return recordPageFault(request, event, manifest, route, reference);
      }
    }
    if (!active && request.method === "GET" && route.inside === "api/state") {
      return staticState(request, env, manifest, route, reference);
    }
    // An active page's current document belongs to its private record, including
    // on ordinary reload. Its DO can serve that document while the container sleeps.
    const privateDocument = active && isLivePageDocumentRequest(route);
    if (
      (request.method === "GET" || request.method === "HEAD") &&
      !isPageApiRequest(route) &&
      !privateDocument
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
        response.headers.set(
          "Server-Timing",
          `leaf;dur=${Date.now() - requestStarted}`,
        );
        if (existing === null) {
          response.headers.append("Set-Cookie", sessionCookie(sessionId, secure));
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
        // Accepted page events are already durable; active Codex turn identity
        // belongs to the running process.
        // TODO: a dispatch does not yet survive its container (issue #4080,
        // "Make a leaf.page dispatch survive its container").
        ctx.waitUntil(dispatchAgentTask(env, params));
      }
    }
    let body: BodyInit | null = response.body;
    if (request.method === "POST" && route.inside === "api/samples" && response.ok) {
      const answer = (await response.json()) as ServedSampleAnswer;
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
    if (!active)
      answer.headers.append(
        "Set-Cookie",
        activeCookie(secure, route.root, manifest.release),
      );
    if (response.headers.get("Content-Type")?.startsWith("text/html")) {
      answer.headers.set("Server-Timing", `leaf;dur=${Date.now() - requestStarted}`);
    }
    return answer;
  },
};
