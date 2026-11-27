/**
 * Public Leaf site with edge reads and isolated canonical mutation sessions.
 *
 * Cloudflare serves untouched pages at the edge. A browser cookie selects a private
 * Durable Object, one per page protocol and store format, holding canonical page
 * records and Python-produced dormant responses. Saved content loads without starting
 * Linux. Mutations wake the Python Leaf server, which restores the record before
 * admission and publishes the record and matching delivery atomically before
 * acknowledgement. Python owns all event and activity rules; this Worker stores and
 * routes their output.
 * A visitor's records outlive a deploy at the same page protocol and store format
 * (`storage.ts`), as a local page outlives a Leaf update: the next release's container
 * restores them and serves them on its own runtime, and a new protocol or format selects
 * new records. The maintainer chose this over a record per release, which reset every
 * visitor's comments, choices and agent thread at each deploy.
 * Every answer names the release of the code that gave it (`Leaf-Release`): the edge
 * its own, a container the one its image runs, and a saved response the one whose
 * container captured it, which the store serves only to that release. A session's
 * containers run the deployed image from the deploy's first request on (`LeafSession`),
 * so a tab reloads onto the deployed release at its first answer after the deploy
 * (`transport/layer-client.js`).
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

import { DurableObject, WorkerEntrypoint } from "cloudflare:workers";
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
  prepareStateDelivery,
  readPageDrafts,
  readPublication,
  readPublicationCommit,
  STORE_FORMAT,
} from "./storage";

import { agentLog, dispatchAgentTask, prewarmContainer } from "./agent";
import {
  projectInteractionBatch,
  sampleInteractionReference,
  startsTyping,
  type InteractionProjection,
} from "./interactions";
import { proxyModelRequest } from "./model-proxy";
import {
  activeCookie,
  activeFromCookie,
  isLivePageDocumentRequest,
  isPageVersionRequest,
  isPageApiRequest,
  isPageSessionFileRequest,
  isPrivatePageRequest,
  needsPageSlash,
  hex,
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
  PAGES: DurableObjectNamespace<LeafSession>;
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
const PAGE_STORE_HOST = "leaf-state.internal";
const MODEL_HOST = "api.openai.com";
// The container's Python server (`Dockerfile`), and the environment it starts with.
// Codex holds a dummy key that only the model proxy accepts, and trusts the CA that
// Cloudflare's HTTPS interception signs with.
const CONTAINER_PORT = 8080;
const CONTAINER_ENV = {
  LEAF_AGENT: "Agent",
  OPENAI_API_KEY: "leaf-outbound-proxy",
  CODEX_CA_CERTIFICATE: "/etc/cloudflare/certs/cloudflare-containers-ca.crt",
  LEAF_PAGE_STORE_URL: `https://${PAGE_STORE_HOST}`,
};
// A page's first write waits while its container boots and composes the page's layer,
// CPU-bound work that takes about 8.7 s on `basic`'s 1/4 vCPU and 1.9 s on one vCPU.
// Cloudflare bills CPU only as it is used, so the smallest custom instance, one vCPU
// with the 3 GiB it requires, costs less than `standard-1`'s 1/2 vCPU with 4 GiB. The
// account's limit of 1,500 concurrent vCPU bounds how many run at once, the dev site's
// included.
const CONTAINER_INSTANCE = { vcpu: 1, memoryMib: 3072, diskMb: 4000 };
// How long a container keeps running after its session's last request.
const CONTAINER_IDLE_MS = 10 * 60 * 1000;
// The session object's key for the release whose image its container runs.
const CONTAINER_RELEASE = "container-release";
// A started container answers on its port within about 7 s. One that has not answered
// in many times that is stuck, and the request that waits on it fails.
const CONTAINER_READY_MS = 120_000;
const CONTAINER_POLL_MS = 100;
// A start the platform can't place yet, as just after another container stopped or
// with the account's vCPU all in use, is tried again, at growing intervals from the
// first, for this long.
const CONTAINER_PLACING_MS = 15_000;
const CONTAINER_PLACING_PAUSE_MS = 250;
interface AcceptedEvent {
  event: Event;
  needsReply: boolean;
}

/** The session object's name for itself, which its container's outbound requests carry. */
interface OutboundProps {
  session: string;
}

declare global {
  namespace Cloudflare {
    interface GlobalProps {
      mainModule: typeof import("./index");
    }
  }
}

/**
 * One visitor's session at one record scope (`recordScope`): their page records, and
 * the container that runs Leaf on them.
 *
 * The object chooses its container's image when it starts one, from the Worker
 * version it runs (Durable Object scheduling, `wrangler.toml`), so every container a
 * deploy's object starts runs that deploy's image. The object restarts on the deployed
 * code at the deploy (`code_update_strategy`), and its first request afterwards stops
 * a container still running the previous image, cutting off an agent turn running
 * then. The maintainer chose this over letting that container run until it idles. The
 * previous image's server and the deployed Worker share no version for what they send
 * each other, so its saves could fail with no reload to rescue the visitor; a page the
 * deploy added is one the previous image doesn't have; and an open tab keeps its
 * container busy, so the visitor would never reach the deployed release.
 */
export class LeafSession extends DurableObject<Env> {
  private pages: PageStore;
  // The start in progress, which every request arriving meanwhile waits on.
  private starting: Promise<void> | null = null;

  constructor(ctx: DurableObjectState, env: Env) {
    super(ctx, env);
    this.pages = new PageStore(ctx.storage);
    // A container outlives the object's restart, but not the idle timeout the previous
    // instance set, and its outbound routes still name the previous code's handler.
    const container = ctx.container;
    if (container?.running)
      void ctx.blockConcurrencyWhile(async () => {
        await this.routeOutbound();
        await container.setInactivityTimeout(CONTAINER_IDLE_MS);
        this.watch();
      });
  }

  // Hear the container stop, however it stops, so that `running` reads false at once
  // and the next request is answered from the saved records or starts a new one.
  private watch(): void {
    void this.ctx.container!.monitor().then(
      () => logContainerStop(null),
      (reason: unknown) => logContainerStop(reason),
    );
  }

  /** A request the container sent its page store, which `SessionOutbound` passes on.
   * The object answers it under its own code and refuses a container on another release
   * before reading or writing anything (`storage.ts`). The handler can't: Cloudflare can
   * run it on a newer Worker version than the object for some seconds after a deploy,
   * and the object can restart on newer code while a request the handler passed is on
   * its way. */
  async pageStore(request: Request): Promise<Response> {
    const manifest = await siteManifest(new Request("https://leaf.page/"), this.env);
    if (request.headers.get("Leaf-Release") !== manifest.release) {
      return new Response(`the page store serves release ${manifest.release}`, {
        status: 409,
      });
    }
    const path = new URL(request.url).pathname;
    if (request.method === "GET" && path === "/records") {
      return this.pages.records(manifest);
    }
    if (request.method === "PUT" && path === "/prepare") {
      const publication = readPublication(await request.json());
      return Response.json(await this.pages.prepare(publication, manifest));
    }
    const blob = /^\/blobs\/([0-9a-f]{64})$/.exec(path);
    if (blob !== null && request.method === "PUT") {
      // Bound the body before it enters SQLite.
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
      await this.pages.saveBlob(blob[1], await new Response(body).arrayBuffer());
      return new Response(null, { status: 204 });
    }
    if (request.method === "PUT" && path === "/publication") {
      this.pages.publish(readPublicationCommit(await request.json()));
      return new Response(null, { status: 204 });
    }
    if (request.method === "PUT" && path === "/drafts") {
      const drafts = readPageDrafts(await request.json());
      return Response.json({ drafts: this.pages.saveDrafts(drafts, manifest) });
    }
    return new Response("unknown page storage operation", { status: 404 });
  }

  // Every request the container sends goes to `SessionOutbound`, which names this
  // object as its owner, so the container reaches only this session's records and the
  // model API. Its Internet access is otherwise off.
  private async routeOutbound(): Promise<void> {
    const container = this.ctx.container!;
    const outbound = this.ctx.exports.SessionOutbound({
      props: { session: this.ctx.id.toString() },
    });
    await container.interceptOutboundHttps("*", outbound);
    await container.interceptAllOutboundHttp(outbound);
  }

  private async start(): Promise<void> {
    const container = this.ctx.container!;
    const { release } = await siteManifest(new Request("https://leaf.page/"), this.env);
    this.ctx.storage.kv.put(CONTAINER_RELEASE, release);
    await this.routeOutbound();
    const placing = Date.now() + CONTAINER_PLACING_MS;
    for (let pause = CONTAINER_PLACING_PAUSE_MS; ; pause *= 2) {
      container.start({
        image: container.images.leaf,
        instance: CONTAINER_INSTANCE,
        enableInternet: false,
        env: CONTAINER_ENV,
      });
      this.watch();
      try {
        await container.setInactivityTimeout(CONTAINER_IDLE_MS);
        await this.ready();
        return;
      } catch (error) {
        // A container still running never answered in time, and a process that ran
        // and exited carries its exit code; a start the platform could not place
        // carries neither, and is tried again.
        if (container.running) {
          await container.destroy().catch(() => undefined);
          throw error;
        }
        if (exitCode(error) !== undefined || Date.now() + pause >= placing) throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, pause));
    }
  }

  // The start or recovery in progress, begun by the first request that needs it. A
  // running container that lost a connection is given until its health route answers
  // again, and is stopped if it never does, so the next request starts another.
  private recovered(): Promise<void> {
    const container = this.ctx.container!;
    this.starting ??= this.ready()
      .catch(async (error: unknown) => {
        if (container.running) await container.destroy().catch(() => undefined);
        throw error;
      })
      .finally(() => (this.starting = null));
    return this.starting;
  }

  // Resolve once the container's server answers its health route
  // (`_select_page` in `worker/leaf_website`), which `start` returns before; reject
  // with the runtime's reason once the container has stopped.
  private async ready(): Promise<void> {
    const container = this.ctx.container!;
    const health = container.getTcpPort(CONTAINER_PORT);
    const deadline = Date.now() + CONTAINER_READY_MS;
    for (;;) {
      try {
        const answer = await health.fetch("http://container/health", {
          signal: AbortSignal.timeout(Math.max(deadline - Date.now(), 1)),
        });
        await answer.body?.cancel();
        if (answer.ok) return;
        throw new Error(`the container's health route answered ${answer.status}`);
      } catch (error) {
        if (!container.running)
          throw await container.monitor().then(
            () => Object.assign(new Error("the container exited"), { exitCode: 0 }),
            (reason: unknown) => reason,
          );
        if (Date.now() >= deadline) throw error;
      }
      await new Promise((resolve) => setTimeout(resolve, CONTAINER_POLL_MS));
    }
  }

  private running(): Promise<void> {
    if (this.starting === null && !this.ctx.container!.running)
      this.starting = this.start().finally(() => (this.starting = null));
    return this.starting ?? Promise.resolve();
  }

  // One attempt at the container's answer, starting the container where it is stopped.
  private async attempt(request: Request): Promise<Attempt> {
    try {
      await this.running();
    } catch (error) {
      // One the platform couldn't place is a wait the tab sits out; one that ran and
      // exited is a fault the tab shows (`host/state-feed.js`).
      const status = exitCode(error) === undefined ? 503 : 500;
      return lostAttempt("start", "Failed to start container", error, status);
    }
    let response: Response;
    try {
      response = await this.ctx
        .container!.getTcpPort(CONTAINER_PORT)
        .fetch(request.url.replace(/^https:/, "http:"), request);
    } catch (error) {
      return lostAttempt("disconnected", "Lost the container's connection", error, 500);
    }
    if (response.status < 500) return { response, failure: null };
    // Python names the session on its own answers (`Leaf-Session`,
    // `WebsitePageEndpoint`) and logs page_fault for them.
    return {
      response,
      failure: {
        source: response.headers.has("Leaf-Session") ? "adapter" : "unclassified",
      },
    };
  }

  private async forward(request: Request): Promise<Response> {
    // A connection lost while the container starts or restarts says nothing about
    // the request, so a request Python answers the same way twice gets one more
    // attempt, once the container answers its health route again or a new one has
    // started, rather than showing the visitor a 500: a read, or a view report,
    // which replaces only an older report of its session (`leaf.serving.user_views`).
    // Any other write may already have reached Python, so its loss reaches the
    // caller instead.
    const replay =
      request.method === "GET" || request.method === "HEAD"
        ? request
        : request.method === "POST" &&
            new URL(request.url).pathname.endsWith("/api/user-view")
          ? request.clone()
          : null;
    const first = await this.attempt(request);
    if (first.failure === null) return first.response;
    const retry = first.failure.source === "disconnected" && replay !== null;
    logHttpError(request, first.response, first.failure, retry);
    if (!retry) return first.response;
    await first.response.body?.cancel();
    await this.recovered().catch(() => undefined);
    const second = await this.attempt(replay);
    if (second.failure !== null)
      logHttpError(request, second.response, second.failure, false);
    return second.response;
  }

  async fetch(request: Request): Promise<Response> {
    const manifest = await siteManifest(request, this.env);
    const url = new URL(request.url);
    // Requests that arrive meanwhile wait, so none reaches the container being stopped.
    if (
      this.ctx.container?.running &&
      this.ctx.storage.kv.get(CONTAINER_RELEASE) !== manifest.release
    )
      await this.ctx.blockConcurrencyWhile(async () => {
        if (
          this.ctx.container?.running &&
          this.ctx.storage.kv.get(CONTAINER_RELEASE) !== manifest.release
        )
          await this.ctx.container.destroy();
      });
    if (!this.ctx.container?.running) {
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
        }
        // A response saved under another release names that release's files, so the
        // deployed release's container answers in its place.
        const response = await this.pages.response(route.root, path, request, manifest);
        if (response !== null) return response;
      }
    }
    return this.forward(request);
  }
}

type HttpFailure =
  | { source: "adapter" | "unclassified" }
  | { source: "start" | "disconnected"; detail: string };

interface Attempt {
  response: Response;
  failure: HttpFailure | null;
}

// A container that failed to start or dropped the connection, as the visitor's 503
// or 500.
// The platform's sentence about it is the log's `detail`; neither Python's body nor
// the request URL is logged.
function lostAttempt(
  source: "start" | "disconnected",
  summary: string,
  error: unknown,
  status: number,
): Attempt {
  const detail = error instanceof Error ? error.message : String(error);
  return {
    response: new Response(`${summary}: ${detail}`, { status }),
    failure: { source, detail },
  };
}

// The exit code the runtime gives a container's process that ran and exited.
function exitCode(error: unknown): number | undefined {
  const code = (error as { exitCode?: unknown } | null)?.exitCode;
  return typeof code === "number" ? code : undefined;
}

// A container's exit, with the runtime's reason where it gives one, such as an idle
// stop or an exit code.
function logContainerStop(reason: unknown): void {
  console.log({
    component: "leaf-container",
    event: "container_stopped",
    ...(reason !== null && {
      detail: reason instanceof Error ? reason.message : String(reason),
    }),
  });
}

function logHttpError(
  request: Request,
  response: Response,
  failure: HttpFailure,
  retried: boolean,
): void {
  console.error({
    component: "leaf-container",
    event: "http_error",
    method: request.method,
    status: response.status,
    ...failure,
    retried,
  });
}

/** Every request a session's container sends out. The session object that started the
 * container names itself in `props`, so no URL, cookie or header the container sends
 * selects another visitor's records. */
export class SessionOutbound extends WorkerEntrypoint<Env, OutboundProps> {
  async fetch(request: Request): Promise<Response> {
    const { session } = this.ctx.props;
    switch (new URL(request.url).hostname) {
      case PAGE_STORE_HOST:
        try {
          const store = this.env.PAGES.get(this.env.PAGES.idFromString(session));
          return await store.pageStore(request);
        } catch (error) {
          // A handler that throws reaches the container as a connection closed without
          // a response, so answer with the store's reason for the container to log.
          return new Response(error instanceof Error ? error.message : String(error), {
            status: 500,
          });
        }
      case MODEL_HOST:
        return proxyModelRequest(request, this.env, session);
      default:
        return new Response("Origin is disallowed", { status: 520 });
    }
  }
}

function randomSessionId(): string {
  return hex(crypto.getRandomValues(new Uint8Array(16)));
}

// What a visitor's record is readable by: Leaf's page protocol for the page files, and
// the store's own format for the tables holding them (`STORE_FORMAT`). Each scope has
// its own durable record and container, so a deploy that keeps both keeps a visitor's
// page, and one that moves either starts them on the published page. Container
// replacement keeps the same record.
function recordScope(manifest: SiteManifest): string {
  return `${manifest.protocol}.${STORE_FORMAT}`;
}

function containerId(sessionId: string, scope: string): string {
  return `${scope}:${sessionId}`;
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
  for (;;) {
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
  return new Response(null, { status: 204 });
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

// The runtime sends no read until its session is active (`records/thread/read.js`), so this
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
  const answer = Response.json(refusal, { headers: { "Leaf-Session": "passive" } });
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
    headers: { "Leaf-Session": "passive" },
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
  admitted: (batch: InteractionProjection) => void = () => undefined,
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
  admitted(batch);
  return new Response(null, { status: 204 });
}

// The event an accepted POST's answer names, and whether it owes the agent an
// answer, as the event door says (`event_endpoint.with_state`).
async function acceptedEvent(response: Response): Promise<AcceptedEvent | null> {
  if (!response.ok) return null;
  try {
    const answer = (await response.clone().json()) as ServedEventAnswer;
    if (answer.ok !== true) return null;
    return { event: answer.event, needsReply: answer.needs_reply };
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

// The isolate keeps the manifest once a request has read it, and keeps no promise of
// it: a promise settles only in the request that made it, so one shared while pending
// never settles for the others once that request ends, as when its browser navigates
// away, and every later request in the isolate fails.
const manifests = new WeakMap<object, SiteManifest>();

async function siteManifest(request: Request, env: Env): Promise<SiteManifest> {
  const known = manifests.get(env.ASSETS as object);
  if (known) return known;
  const response = await env.ASSETS.fetch(
    new Request(new URL("/_leaf/site.json", request.url)),
  );
  if (!response.ok) throw new Error(`site manifest returned ${response.status}`);
  const manifest = (await response.json()) as SiteManifest;
  manifests.set(env.ASSETS as object, manifest);
  return manifest;
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
  prepareStateDelivery(state, request);
  // Stored and asked for again before each reuse, as every Leaf server's state answer
  // is (`CACHE_CONTROL`, `src/leaf/serving/http.py`), so it names the request headers its body
  // turns on.
  const answer = Response.json(state, {
    headers: {
      "Cache-Control": "no-cache",
      Vary: "Leaf-Data-Version, Leaf-View-Revision",
      "Leaf-Session": "passive",
    },
  });
  stampDelivery(answer.headers, route, manifest, reference);
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
    const scope = recordScope(manifest);
    const active = activeFromCookie(cookie, secure, route.root, scope);
    const sessionId = existing ?? randomSessionId();
    const privateContainer = containerId(sessionId, scope);
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
      const sourceId = request.headers.get("CF-Connecting-IP") ?? sessionId;
      return recordInteractions(
        request,
        route,
        { reference },
        manifest.release,
        (batch) => {
          if (startsTyping(batch))
            ctx.waitUntil(
              prewarmContainer(env, privateContainer, reference, route.root, sourceId),
            );
        },
      );
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
    // An active page's current document and its versions belong to its private
    // record, including on ordinary reload, since their addresses don't name their
    // content: a record an earlier release saved holds its own versions, which the
    // release's published ones of the same number are not. Revisions and media are
    // named by their content, so a published copy is the same file. The DO can serve
    // these documents while the container sleeps.
    const privateDocument =
      active && (isLivePageDocumentRequest(route) || isPageVersionRequest(route));
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
    const posted = request.method === "POST" && route.inside === "api/event";
    const response = await env.PAGES.getByName(privateContainer).fetch(request);
    if (posted) {
      const accepted = await acceptedEvent(response);
      if (accepted) {
        // The release of the container that admitted it.
        const admitting = response.headers.get("Leaf-Release") ?? manifest.release;
        recordAcceptedEvent(env, route, admitting, reference, accepted);
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
    answer.headers.set("Leaf-Session-Reference", reference);
    if (existing === null) {
      answer.headers.append("Set-Cookie", sessionCookie(sessionId, secure));
    }
    // Only Python's own answer, which names its session (`Leaf-Session: active`), shows
    // the container holds the page. The session object's failure for a container that
    // never started names none, so neither the visitor's cookie nor their browser pins
    // later reads to that container.
    if (!active && response.headers.has("Leaf-Session"))
      answer.headers.append("Set-Cookie", activeCookie(secure, route.root, scope));
    if (response.headers.get("Content-Type")?.startsWith("text/html")) {
      answer.headers.set("Server-Timing", `leaf;dur=${Date.now() - requestStarted}`);
    }
    return answer;
  },
};
