/** Durable page records and their Python-produced, dormant delivery publication.
 *
 * Python stages one successor per page under its append lease, uploads missing
 * content-addressed chunks, then atomically publishes files and HTTP responses.
 * Committed records, staged successors and in-flight delivery/restore streams are the
 * complete set of chunk owners. Replacing or committing a stage reclaims unused
 * bytes; an interrupted upload retains at most one successor until that page retries.
 * This owner never interprets the log, computes widget state or infers activity.
 * GET /records is one uncompressed TAR snapshot: records.json first contains the
 * committed file descriptors; each referenced chunk follows once as a regular file
 * named by its hex digest. Capture and stream retention share one synchronous
 * reading. The container consumes the snapshot before replacing any local inputs.
 */

import * as z from "zod/mini";
import { createTarPacker } from "modern-tar";

export const CHUNK_BYTES = 1024 * 1024;
const digest = z.string().check(z.regex(/^[0-9a-f]{64}$/));
const chunks = z.array(digest);
const file = z.strictObject({ chunks, modified: z.number() });
const publicationSchema = z.strictObject({
  root: z.string(),
  release: z.string(),
  record: z.record(z.string(), file),
  responses: z.record(z.string(),
    z.strictObject({
      status: z.number().check(z.int(), z.minimum(200), z.maximum(599)),
      headers: z.record(z.string(), z.string()),
      chunks,
    }),
  ),
});

export type PagePublication = z.infer<typeof publicationSchema>;

export function readPublication(value: unknown): PagePublication {
  return publicationSchema.parse(value);
}

function references(publication: PagePublication): string[] {
  return [...new Set([...Object.values(publication.record), ...Object.values(publication.responses)]
    .flatMap((entry) => entry.chunks))];
}

/** Delivery dates calibrate the browser clock and order answers; folded content
 * and its event timestamps stay exactly as Python captured them.
 */
export function dateStateDelivery(state: Record<string, unknown>): void {
  const delivered = new Date();
  state.now = delivered.toISOString();
  state.taken = delivered.getTime() / 1000;
}

export class PageStore {
  private deliveries = new Set<string[]>();

  constructor(private storage: DurableObjectStorage) {
    storage.sql.exec(`CREATE TABLE IF NOT EXISTS leaf_pages (
      root TEXT, staged INTEGER, release TEXT, PRIMARY KEY(root, staged)
    ); CREATE TABLE IF NOT EXISTS leaf_files (
      root TEXT, staged INTEGER, path TEXT, chunks TEXT, modified REAL,
      PRIMARY KEY(root, staged, path)
    ); CREATE TABLE IF NOT EXISTS leaf_responses (
      root TEXT, staged INTEGER, path TEXT, status INTEGER, headers TEXT, chunks TEXT,
      PRIMARY KEY(root, staged, path)
    ); CREATE TABLE IF NOT EXISTS leaf_blobs (
      digest TEXT PRIMARY KEY, bytes BLOB
    )`);
  }

  private references(staged?: boolean): string[] {
    const where = staged === undefined ? "" : ` WHERE staged = ${Number(staged)}`;
    return ["leaf_files", "leaf_responses"].flatMap((table) =>
      this.storage.sql.exec<{ chunks: string }>(`SELECT chunks FROM ${table}${where}`)
        .toArray().flatMap(({ chunks }) => JSON.parse(chunks) as string[]));
  }

  private collect(): void {
    const held = new Set([...this.references(), ...[...this.deliveries].flat()]);
    for (const { digest } of this.storage.sql.exec<{ digest: string }>(
      "SELECT digest FROM leaf_blobs",
    ).toArray()) {
      if (!held.has(digest)) this.storage.sql.exec("DELETE FROM leaf_blobs WHERE digest = ?", digest);
    }
  }

  private erase(root: string, staged: boolean): void {
    for (const table of ["leaf_pages", "leaf_files", "leaf_responses"]) {
      this.storage.sql.exec(`DELETE FROM ${table} WHERE root = ? AND staged = ?`, root, Number(staged));
    }
  }

  prepare(publication: PagePublication): string[] {
    return this.storage.transactionSync(() => {
      const root = publication.root;
      this.erase(root, true);
      this.storage.sql.exec("INSERT INTO leaf_pages VALUES (?, 1, ?)", root, publication.release);
      for (const [path, file] of Object.entries(publication.record)) {
        this.storage.sql.exec("INSERT INTO leaf_files VALUES (?, 1, ?, ?, ?)", root, path, JSON.stringify(file.chunks), file.modified);
      }
      for (const [path, response] of Object.entries(publication.responses)) {
        this.storage.sql.exec("INSERT INTO leaf_responses VALUES (?, 1, ?, ?, ?, ?)",
          root, path, response.status, JSON.stringify(response.headers), JSON.stringify(response.chunks));
      }
      this.collect();
      return this.missing(references(publication));
    });
  }

  async saveBlob(name: string, bytes: ArrayBuffer): Promise<void> {
    digest.parse(name);
    if (bytes.byteLength > CHUNK_BYTES) throw new Error("page storage chunk exceeds 1 MiB");
    const actual = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)))
      .map((byte) => byte.toString(16).padStart(2, "0")).join("");
    if (actual !== name) throw new Error("page storage chunk digest does not match bytes");
    if (!this.references(true).includes(name)) {
      throw new Error("page storage chunk has no staged owner");
    }
    this.storage.sql.exec("INSERT OR IGNORE INTO leaf_blobs VALUES (?, ?)", name, new Uint8Array(bytes));
  }

  blob(name: string): ArrayBuffer | null {
    digest.parse(name);
    const rows = this.storage.sql.exec<{ bytes: ArrayBuffer }>(
      "SELECT bytes FROM leaf_blobs WHERE digest = ?", name,
    ).toArray();
    return rows[0]?.bytes ?? null;
  }

  private missing(names: string[]): string[] {
    return names.filter((name) =>
      this.storage.sql.exec("SELECT digest FROM leaf_blobs WHERE digest = ?", name)
        .toArray().length === 0,
    );
  }

  publish(publication: PagePublication): void {
    this.storage.transactionSync(() => {
      const root = publication.root;
      const pages = this.storage.sql.exec<{ release: string }>(
        "SELECT release FROM leaf_pages WHERE root = ? AND staged = 1", root).toArray();
      const files = this.storage.sql.exec<{ path: string; chunks: string; modified: number }>(
        "SELECT path, chunks, modified FROM leaf_files WHERE root = ? AND staged = 1", root).toArray();
      const responses = this.storage.sql.exec<{
        path: string; status: number; headers: string; chunks: string;
      }>("SELECT path, status, headers, chunks FROM leaf_responses WHERE root = ? AND staged = 1", root).toArray();
      if (pages[0]?.release !== publication.release
        || files.length !== Object.keys(publication.record).length
        || files.some(({ path, chunks, modified }) => chunks !== JSON.stringify(publication.record[path]?.chunks)
          || modified !== publication.record[path]?.modified)
        || responses.length !== Object.keys(publication.responses).length
        || responses.some(({ path, status, headers, chunks }) => {
          const response = publication.responses[path];
          return !response || status !== response.status || headers !== JSON.stringify(response.headers)
            || chunks !== JSON.stringify(response.chunks);
        })) throw new Error("page publication was not staged");
      const missing = this.missing(references(publication));
      if (missing.length) throw new Error(`missing page storage chunk ${missing[0]}`);
      this.erase(root, false);
      for (const table of ["leaf_pages", "leaf_files", "leaf_responses"]) {
        this.storage.sql.exec(`UPDATE ${table} SET staged = 0 WHERE root = ? AND staged = 1`, root);
      }
      this.collect();
    });
  }

  records(): Response {
    const records = Object.fromEntries(this.storage.sql.exec<{ root: string }>(
      "SELECT root FROM leaf_pages WHERE staged = 0 ORDER BY root",
    ).toArray().map(({ root }) => [root, {} as PagePublication["record"]]));
    for (const { root, path, chunks, modified } of this.storage.sql.exec<{
      root: string; path: string; chunks: string; modified: number;
    }>("SELECT root, path, chunks, modified FROM leaf_files WHERE staged = 0 ORDER BY root, path").toArray()) {
      records[root][path] = { chunks: JSON.parse(chunks), modified };
    }
    const names = [...new Set(Object.values(records)
      .flatMap((record) => Object.values(record).flatMap(({ chunks }) => chunks)))];
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
      await add("records.json", new TextEncoder().encode(JSON.stringify(records)));
      for (const name of names) {
        const bytes = this.blob(name);
        if (bytes === null) throw new Error("published page storage chunk disappeared");
        await add(name, new Uint8Array(bytes));
      }
      controller.finalize();
    })().catch((error) => controller.error(error));
    return new Response(stream, { headers: { "Content-Type": "application/x-tar" } });
  }

  private hold(names: string[], stream: ReadableStream<Uint8Array>): ReadableStream<Uint8Array> {
    this.deliveries.add(names);
    const finish = () => {
      if (this.deliveries.delete(names)) this.collect();
    };
    const reader = stream.getReader();
    return new ReadableStream({
      pull: async (controller) => {
        try {
          const { done, value } = await reader.read();
          if (done) {
            controller.close();
            finish();
          } else {
            controller.enqueue(value);
          }
        } catch (error) {
          controller.error(error);
          finish();
        }
      },
      cancel: async (reason) => {
        try {
          await reader.cancel(reason);
        } finally {
          finish();
        }
      },
    }, { highWaterMark: 0 });
  }

  private body(names: string[]): ReadableStream<Uint8Array> {
    let part = 0;
    return this.hold(names, new ReadableStream({
      pull: (controller) => {
        if (part === names.length) controller.close();
        else {
          const bytes = this.blob(names[part++]);
          if (bytes === null) throw new Error("published page storage chunk disappeared");
          controller.enqueue(new Uint8Array(bytes));
        }
      },
    }, { highWaterMark: 0 }));
  }

  async response(root: string, path: string, head: boolean): Promise<Response | null> {
    const rows = this.storage.sql.exec<{
      status: number; headers: string; chunks: string;
    }>("SELECT status, headers, chunks FROM leaf_responses WHERE root = ? AND path = ? AND staged = 0",
      root, path).toArray();
    if (rows.length === 0) return null;
    const response = rows[0];
    const headers = new Headers(JSON.parse(response.headers));
    headers.set("Cache-Control", "private, no-store");
    headers.set("Leaf-State-Source", "durable");
    if (head || response.status === 204 || response.status === 304) {
      return new Response(null, { status: response.status, headers });
    }
    const body = this.body(JSON.parse(response.chunks));
    if (path === "api/state" || path.startsWith("api/state?")) {
      const state = await new Response(body).json() as Record<string, unknown>;
      dateStateDelivery(state);
      headers.delete("Content-Length");
      return Response.json(state, { status: response.status, headers });
    }
    return new Response(body, { status: response.status, headers });
  }
}
