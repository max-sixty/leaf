/** Durable page records and their Python-produced, dormant delivery publication.
 *
 * Python stages one successor per page under its append lease, uploads missing
 * content-addressed chunks, then commits the returned content identity to atomically
 * publish the stored files and captured HTTP 200 responses. The identity describes
 * content, not a prepare attempt: preparing identical content keeps the same identity.
 * Committed records, staged successors and in-flight delivery/restore streams are the
 * complete set of chunk owners. Replacing or committing a stage reclaims unused
 * bytes; an interrupted upload retains at most one successor until that page retries.
 * This owner never interprets the log, computes widget state or infers activity.
 * A page's drafts store is a record of its own, the store of record, which Python
 * replaces whole with each write before it answers the write (`saveDrafts`,
 * `publish_drafts` in `worker/leaf_website/storage.py`). A save names the store and
 * version it replaces, and is taken only over that, so a save that arrives late, as
 * one whose answer the container never heard, finds a newer store and changes
 * nothing; the answer is the store held, which the container then works from. No page
 * commit carries it, so no commit puts an older store back, and a saved `api/drafts`
 * or `api/news` answer is served with the stored drafts in place of those it was
 * captured with. Each drafts store is kept under the `format` of the drafts record it
 * was written at (the manifest's `drafts_format`), and a release reads and replaces
 * only the stores at its own format, as a local Leaf reads only the
 * `drafts@<since>.json` of its own shape (`state.Record`). So a release whose Leaf
 * changed the drafts' shape finds no store for a page, and a release back at the
 * earlier shape finds that store as it was left.
 * GET /records is one uncompressed TAR snapshot: records.json first contains the
 * committed file descriptors and each page's drafts store; each referenced chunk
 * follows once as a regular file named by its hex digest. Capture and stream
 * retention share one synchronous reading. The container consumes the snapshot
 * before replacing any local inputs.
 * A page's record is its whole page directory as the session left it, every revision
 * it reads included, so a later release at the same page protocol restores and serves
 * it as a local Leaf serves a page an earlier Leaf wrote. A captured response names the
 * assets of the release whose container captured it, so the store keeps that release
 * beside each committed page and serves the page's responses only to it; under another
 * release the request wakes the container, which serves the page on its own runtime;
 * its first read of the page, a transaction like any write, saves the responses again.
 * Each request a container makes names the release its image runs (`Leaf-Release`).
 * A container running when a deploy lands keeps the previous image until its session's
 * first request after the deploy stops it (`LeafSession` in `index.ts`). The session
 * object answers a store request from a release other than its own code's with 409
 * before reading or writing anything (`pageStore`), so every commit since the object
 * moved to the deployed code was written by the deployed release's image.
 * The store itself also outlives deploys, so every later release reads the tables and
 * stored values an earlier one wrote. `STORE_FORMAT` names their shape: the tables
 * (`STORE_TABLES`, which a test pins to the format), the encodings stored in their
 * columns, and the session object's own keys (`index.ts`). A change to any of them moves
 * it, which, as a page protocol bump does, starts every visitor on the published page,
 * since the session's key names it (`recordScope`), rather than leaving a later
 * release to misread an earlier one's rows. Nothing migrates a store.
 * Delivery identity is the pathname and sorted decoded query pairs, independent
 * of the HTTP serializer used by Python or the browser. A saved response keeps the
 * headers Python captured, so it is cached as the live answer would be
 * (`CACHE_CONTROL`, `src/leaf/serving/http.py`).
 */

import * as z from "zod/mini";
import { createTarPacker } from "modern-tar";
import type {
  ServedDraftsAnswer,
  ServedNewsAnswer,
  ServedState,
} from "../../browser/types/contract.js";
import { hex, type SiteManifest } from "./routing";

// The lowercase hex SHA-256 of `bytes`: a chunk's name and a publication's identity.
async function sha256Hex(bytes: BufferSource): Promise<string> {
  return hex(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)));
}

export const CHUNK_BYTES = 1024 * 1024;
const digest = z.string().check(z.regex(/^[0-9a-f]{64}$/));
const chunks = z.array(digest);
const file = z.strictObject({ chunks, modified: z.number() });
const publicationSchema = z.strictObject({
  root: z.string(),
  record: z.record(z.string(), file),
  responses: z.record(
    z.string(),
    z.strictObject({
      headers: z.record(z.string(), z.string()),
      chunks,
    }),
  ),
});

export type PagePublication = z.infer<typeof publicationSchema>;
const draftsSchema = z.strictObject({
  root: z.string(),
  replaces: z.nullable(z.strictObject({ store: z.string(), version: z.number() })),
  drafts: z.strictObject({
    store: z.string(),
    version: z.number(),
    drafts: z.record(z.string(), z.record(z.string(), z.unknown())),
  }),
});
type PageDrafts = z.infer<typeof draftsSchema>;
export function readPageDrafts(value: unknown): PageDrafts {
  return draftsSchema.parse(value);
}
type WebsitePages = Pick<SiteManifest, "release" | "drafts_format"> & {
  pages: Record<string, unknown>;
};
const commitSchema = z.strictObject({ root: z.string(), identity: digest });
type PublicationCommit = z.infer<typeof commitSchema>;
export function readPublicationCommit(value: unknown): PublicationCommit {
  return commitSchema.parse(value);
}

export function readPublication(value: unknown): PagePublication {
  return publicationSchema.parse(value);
}

function responseIdentity(path: string): string {
  const address = new URL(path, "https://leaf.page/");
  address.searchParams.sort();
  return JSON.stringify([address.pathname, [...address.searchParams]]);
}

function responseEntries(publication: PagePublication) {
  return Object.entries(publication.responses).map(
    ([path, response]) => [responseIdentity(path), response] as const,
  );
}

/** Delivery dates calibrate the clock and order answers; folded content stays as
 * Python captured it. As on the live Python route, a tab naming the data version it
 * holds needs only that version back; its request owns completion of those sources.
 */
export function prepareStateDelivery(
  state: Pick<ServedState, "now" | "taken" | "data">,
  request: Request,
): void {
  const delivered = new Date();
  state.now = delivered.toISOString();
  state.taken = delivered.getTime() / 1000;
  if (request.headers.get("Leaf-Data-Version") === state.data.version)
    state.data = { version: state.data.version };
}

export const STORE_FORMAT = 2;
export const STORE_TABLES = `CREATE TABLE IF NOT EXISTS leaf_pages (
  root TEXT, staged INTEGER, identity TEXT, release TEXT, PRIMARY KEY(root, staged)
); CREATE TABLE IF NOT EXISTS leaf_files (
  root TEXT, staged INTEGER, path TEXT, chunks TEXT, modified REAL,
  PRIMARY KEY(root, staged, path)
); CREATE TABLE IF NOT EXISTS leaf_responses (
  root TEXT, staged INTEGER, path TEXT, headers TEXT, chunks TEXT,
  PRIMARY KEY(root, staged, path)
); CREATE TABLE IF NOT EXISTS leaf_blobs (
  digest TEXT PRIMARY KEY, bytes BLOB
); CREATE TABLE IF NOT EXISTS leaf_drafts (
  root TEXT, format TEXT, drafts TEXT, PRIMARY KEY(root, format)
)`;

export class PageStore {
  private deliveries = new Set<string[]>();

  constructor(private storage: DurableObjectStorage) {
    storage.sql.exec(STORE_TABLES);
  }

  private references(staged?: boolean, root?: string): string[] {
    const conditions = [];
    const bindings: (string | number)[] = [];
    if (staged !== undefined) {
      conditions.push("staged = ?");
      bindings.push(Number(staged));
    }
    if (root !== undefined) {
      conditions.push("root = ?");
      bindings.push(root);
    }
    const where = conditions.length ? ` WHERE ${conditions.join(" AND ")}` : "";
    return ["leaf_files", "leaf_responses"].flatMap((table) =>
      this.storage.sql
        .exec<{ chunks: string }>(`SELECT chunks FROM ${table}${where}`, ...bindings)
        .toArray()
        .flatMap(({ chunks }) => JSON.parse(chunks) as string[]),
    );
  }

  private collect(): void {
    const held = new Set([...this.references(), ...[...this.deliveries].flat()]);
    for (const { digest } of this.storage.sql
      .exec<{ digest: string }>("SELECT digest FROM leaf_blobs")
      .toArray()) {
      if (!held.has(digest))
        this.storage.sql.exec("DELETE FROM leaf_blobs WHERE digest = ?", digest);
    }
  }

  private erase(root: string, staged: boolean): void {
    for (const table of ["leaf_pages", "leaf_files", "leaf_responses"]) {
      this.storage.sql.exec(
        `DELETE FROM ${table} WHERE root = ? AND staged = ?`,
        root,
        Number(staged),
      );
    }
  }

  private checkRoot(root: string, manifest: WebsitePages): void {
    if (!(root in manifest.pages))
      throw new Error("publication does not name a page in this website release");
  }

  async prepare(
    publication: PagePublication,
    manifest: WebsitePages,
  ): Promise<{ identity: string; missing: string[] }> {
    this.checkRoot(publication.root, manifest);
    // JSON's replacer sorts every object while preserving array order. Normalize
    // response addresses by the same rule used to store and serve them.
    const descriptor = JSON.stringify(
      { ...publication, responses: Object.fromEntries(responseEntries(publication)) },
      (_key, value) =>
        value && typeof value === "object" && !Array.isArray(value)
          ? Object.fromEntries(
              Object.entries(value).sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0)),
            )
          : value,
    );
    const identity = await sha256Hex(new TextEncoder().encode(descriptor));
    return this.storage.transactionSync(() => {
      const root = publication.root;
      this.erase(root, true);
      this.storage.sql.exec(
        "INSERT INTO leaf_pages VALUES (?, 1, ?, ?)",
        root,
        identity,
        manifest.release,
      );
      for (const [path, file] of Object.entries(publication.record)) {
        this.storage.sql.exec(
          "INSERT INTO leaf_files VALUES (?, 1, ?, ?, ?)",
          root,
          path,
          JSON.stringify(file.chunks),
          file.modified,
        );
      }
      for (const [path, response] of responseEntries(publication)) {
        this.storage.sql.exec(
          "INSERT INTO leaf_responses VALUES (?, 1, ?, ?, ?)",
          root,
          path,
          JSON.stringify(response.headers),
          JSON.stringify(response.chunks),
        );
      }
      this.collect();
      return { identity, missing: this.missing(this.references(true, root)) };
    });
  }

  async saveBlob(name: string, bytes: ArrayBuffer): Promise<void> {
    digest.parse(name);
    if (bytes.byteLength > CHUNK_BYTES)
      throw new Error("page storage chunk exceeds 1 MiB");
    const actual = await sha256Hex(bytes);
    if (actual !== name)
      throw new Error("page storage chunk digest does not match bytes");
    if (!this.references(true).includes(name)) {
      throw new Error("page storage chunk has no staged owner");
    }
    this.storage.sql.exec(
      "INSERT OR IGNORE INTO leaf_blobs VALUES (?, ?)",
      name,
      new Uint8Array(bytes),
    );
  }

  blob(name: string): ArrayBuffer | null {
    digest.parse(name);
    const rows = this.storage.sql
      .exec<{
        bytes: ArrayBuffer;
      }>("SELECT bytes FROM leaf_blobs WHERE digest = ?", name)
      .toArray();
    return rows[0]?.bytes ?? null;
  }

  private missing(names: string[]): string[] {
    return [...new Set(names)].filter(
      (name) =>
        this.storage.sql
          .exec("SELECT digest FROM leaf_blobs WHERE digest = ?", name)
          .toArray().length === 0,
    );
  }

  publish(commit: PublicationCommit): void {
    this.storage.transactionSync(() => {
      const root = commit.root;
      const pages = this.storage.sql
        .exec<{ identity: string }>(
          "SELECT identity FROM leaf_pages WHERE root = ? AND staged = 1",
          root,
        )
        .toArray();
      if (pages[0]?.identity !== commit.identity)
        throw new Error("page publication was not staged");
      const missing = this.missing(this.references(true, root));
      if (missing.length) throw new Error(`missing page storage chunk ${missing[0]}`);
      this.erase(root, false);
      for (const table of ["leaf_pages", "leaf_files", "leaf_responses"]) {
        this.storage.sql.exec(
          `UPDATE ${table} SET staged = 0 WHERE root = ? AND staged = 1`,
          root,
        );
      }
      this.collect();
    });
  }

  /** Take a page's drafts store where the one held is the one it `replaces`, and
   * answer with the store held once it has: the one saved, or the one that turned
   * it away. */
  saveDrafts(value: PageDrafts, manifest: WebsitePages): ServedDraftsAnswer | null {
    this.checkRoot(value.root, manifest);
    const held = this.drafts(value.root, manifest);
    const replaces = value.replaces;
    if (
      replaces === null
        ? held !== null
        : held?.store !== replaces.store || held.version !== replaces.version
    )
      return held;
    this.storage.sql.exec(
      "INSERT OR REPLACE INTO leaf_drafts VALUES (?, ?, ?)",
      value.root,
      manifest.drafts_format,
      JSON.stringify(value.drafts),
    );
    return value.drafts as ServedDraftsAnswer;
  }

  private drafts(root: string, manifest: WebsitePages): ServedDraftsAnswer | null {
    const rows = this.storage.sql
      .exec<{ drafts: string }>(
        "SELECT drafts FROM leaf_drafts WHERE root = ? AND format = ?",
        root,
        manifest.drafts_format,
      )
      .toArray();
    return rows.length ? (JSON.parse(rows[0].drafts) as ServedDraftsAnswer) : null;
  }

  records(manifest: WebsitePages): Response {
    const records = Object.fromEntries(
      this.storage.sql
        .exec<{ root: string }>(
          "SELECT root FROM leaf_pages WHERE staged = 0 ORDER BY root",
        )
        .toArray()
        .map(({ root }) => [root, {} as PagePublication["record"]]),
    );
    for (const { root, path, chunks, modified } of this.storage.sql
      .exec<{
        root: string;
        path: string;
        chunks: string;
        modified: number;
      }>(
        "SELECT root, path, chunks, modified FROM leaf_files WHERE staged = 0 ORDER BY root, path",
      )
      .toArray()) {
      records[root][path] = { chunks: JSON.parse(chunks), modified };
    }
    const drafts = Object.fromEntries(
      this.storage.sql
        .exec<{ root: string; drafts: string }>(
          "SELECT root, drafts FROM leaf_drafts WHERE format = ? ORDER BY root",
          manifest.drafts_format,
        )
        .toArray()
        .map(({ root, drafts }) => [root, JSON.parse(drafts)]),
    );
    const names = [
      ...new Set(
        Object.values(records).flatMap((record) =>
          Object.values(record).flatMap(({ chunks }) => chunks),
        ),
      ),
    ];
    const { readable, controller } = createTarPacker();
    const stream = this.hold(names, readable);
    // Capture descriptors and retain their chunks synchronously before yielding.
    // TAR supplies framing and backpressure; one restore crosses the outbound
    // proxy once, regardless of how many revisions share these chunks.
    void (async () => {
      const add = async (name: string, bytes: Uint8Array) => {
        const writer = controller.add({ name, size: bytes.byteLength }).getWriter();
        await writer.write(bytes);
        await writer.close();
      };
      await add(
        "records.json",
        new TextEncoder().encode(JSON.stringify({ records, drafts })),
      );
      for (const name of names) {
        const bytes = this.blob(name);
        if (bytes === null) throw new Error("published page storage chunk disappeared");
        await add(name, new Uint8Array(bytes));
      }
      controller.finalize();
    })().catch((error) => controller.error(error));
    return new Response(stream, { headers: { "Content-Type": "application/x-tar" } });
  }

  private hold(
    names: string[],
    stream: ReadableStream<Uint8Array>,
  ): ReadableStream<Uint8Array> {
    this.deliveries.add(names);
    const finish = () => {
      if (this.deliveries.delete(names)) this.collect();
    };
    const { readable, writable } = new TransformStream<Uint8Array, Uint8Array>();
    void stream.pipeTo(writable).then(finish, finish);
    return readable;
  }

  private body(names: string[]): ReadableStream<Uint8Array> {
    let part = 0;
    return this.hold(
      names,
      new ReadableStream(
        {
          pull: (controller) => {
            if (part === names.length) controller.close();
            else {
              const bytes = this.blob(names[part++]);
              if (bytes === null)
                throw new Error("published page storage chunk disappeared");
              controller.enqueue(new Uint8Array(bytes));
            }
          },
        },
        { highWaterMark: 0 },
      ),
    );
  }

  /** The response the page's last commit captured at `path`, or null where it captured
   * none under the manifest's release. */
  async response(
    root: string,
    path: string,
    request: Request,
    manifest: WebsitePages,
  ): Promise<Response | null> {
    const rows = this.storage.sql
      .exec<{
        headers: string;
        chunks: string;
      }>(
        `SELECT headers, chunks FROM leaf_responses JOIN leaf_pages USING (root, staged)
         WHERE root = ? AND path = ? AND staged = 0 AND release = ?`,
        root,
        responseIdentity(path),
        manifest.release,
      )
      .toArray();
    if (rows.length === 0) return null;
    const response = rows[0];
    const headers = new Headers(JSON.parse(response.headers));
    // Served while the container is stopped, so the tab reads that its next write
    // waits for the container to launch (`writeLaunchesAgent` in `transport/layer-client.js`).
    headers.set("Leaf-State-Source", "durable");
    const drafts =
      path === "api/drafts" || path === "api/news" ? this.drafts(root, manifest) : null;
    if (drafts !== null) headers.delete("Content-Length");
    if (request.method === "HEAD") return new Response(null, { headers });
    if (drafts !== null && path === "api/drafts")
      return Response.json(drafts, { headers });
    const body = this.body(JSON.parse(response.chunks));
    if (drafts !== null) {
      const news = (await new Response(body).json()) as ServedNewsAnswer;
      news.drafts = { store: drafts.store, version: drafts.version };
      return Response.json(news, { headers });
    }
    if (path === "api/state" || path.startsWith("api/state?")) {
      const state = (await new Response(body).json()) as ServedState;
      prepareStateDelivery(state, request);
      headers.delete("Content-Length");
      return Response.json(state, { headers });
    }
    return new Response(body, { headers });
  }
}
