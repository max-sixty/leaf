/** Durable page records and their Python-produced, dormant delivery publication.
 *
 * Python uploads content-addressed, bounded chunks before atomically publishing
 * the record manifest and matching HTTP responses. This owner stores opaque bytes;
 * it never interprets the log, computes widget state, or infers agent activity.
 * An interrupted upload leaves the last complete publication readable.
 */

import * as z from "zod/mini";

export const CHUNK_BYTES = 1024 * 1024;
const digest = z.string().check(z.regex(/^[0-9a-f]{64}$/));
const chunks = z.array(digest);
const publicationSchema = z.strictObject({
  root: z.string(),
  release: z.string(),
  record: z.strictObject({ chunks }),
  responses: z.record(z.string(), z.union([
    z.strictObject({
      status: z.number().check(z.int(), z.minimum(200), z.maximum(599)),
      headers: z.record(z.string(), z.string()),
      chunks,
    }),
    z.strictObject({
      status: z.number().check(z.int(), z.minimum(200), z.maximum(599)),
      headers: z.record(z.string(), z.string()),
      asset: z.string(),
    }),
  ])),
});

export type PagePublication = z.infer<typeof publicationSchema>;

export function readPublication(value: unknown): PagePublication {
  return publicationSchema.parse(value);
}

export class PageStore {
  constructor(private storage: DurableObjectStorage, private assets: Fetcher) {
    storage.sql.exec(`CREATE TABLE IF NOT EXISTS leaf_pages (
      root TEXT PRIMARY KEY, record TEXT
    ); CREATE TABLE IF NOT EXISTS leaf_responses (
      root TEXT, path TEXT, status INTEGER, headers TEXT, chunks TEXT, asset TEXT,
      PRIMARY KEY(root, path)
    ); CREATE TABLE IF NOT EXISTS leaf_blobs (
      digest TEXT PRIMARY KEY, bytes BLOB
    )`);
  }

  async saveBlob(name: string, bytes: ArrayBuffer): Promise<void> {
    digest.parse(name);
    if (bytes.byteLength > CHUNK_BYTES) throw new Error("page storage chunk exceeds 1 MiB");
    const actual = Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)))
      .map((byte) => byte.toString(16).padStart(2, "0")).join("");
    if (actual !== name) throw new Error("page storage chunk digest does not match bytes");
    this.storage.sql.exec("INSERT OR IGNORE INTO leaf_blobs VALUES (?, ?)", name, new Uint8Array(bytes));
  }

  blob(name: string): ArrayBuffer | null {
    digest.parse(name);
    const rows = this.storage.sql.exec<{ bytes: ArrayBuffer }>(
      "SELECT bytes FROM leaf_blobs WHERE digest = ?", name,
    ).toArray();
    return rows[0]?.bytes ?? null;
  }

  publish(publication: PagePublication): void {
    this.storage.transactionSync(() => {
      // Validate every reference before retiring any part of the old publication.
      const references = new Set([publication.record, ...Object.values(publication.responses)]
        .flatMap((entry) => "chunks" in entry ? entry.chunks : []));
      for (const name of references) {
        const rows = this.storage.sql.exec(
          "SELECT digest FROM leaf_blobs WHERE digest = ?", name,
        ).toArray();
        if (rows.length === 0) throw new Error(`missing page storage chunk ${name}`);
      }
      const root = publication.root;
      this.storage.sql.exec("DELETE FROM leaf_responses WHERE root = ?", root);
      this.storage.sql.exec("INSERT OR REPLACE INTO leaf_pages VALUES (?, ?)",
        root, JSON.stringify(publication.record));
      for (const [path, response] of Object.entries(publication.responses)) {
        this.storage.sql.exec("INSERT INTO leaf_responses VALUES (?, ?, ?, ?, ?, ?)",
          root, path, response.status, JSON.stringify(response.headers),
          "chunks" in response ? JSON.stringify(response.chunks) : null,
          "asset" in response ? response.asset : null);
      }
    });
  }

  records(): Record<string, PagePublication["record"]> {
    return Object.fromEntries(this.storage.sql.exec<{ root: string; record: string }>(
      "SELECT root, record FROM leaf_pages ORDER BY root",
    ).toArray().map(({ root, record }) => [root, JSON.parse(record)]));
  }

  private body(names: string[]): ReadableStream<Uint8Array> {
    let part = 0;
    return new ReadableStream({
      pull: (controller) => {
        if (part === names.length) {
          controller.close();
        } else {
          const bytes = this.blob(names[part++]);
          if (bytes === null) throw new Error("published page storage chunk disappeared");
          controller.enqueue(new Uint8Array(bytes));
        }
      },
    });
  }

  async response(root: string, path: string, head: boolean): Promise<Response | null> {
    const rows = this.storage.sql.exec<{
      status: number; headers: string; chunks: string | null; asset: string | null;
    }>("SELECT status, headers, chunks, asset FROM leaf_responses WHERE root = ? AND path = ?",
      root, path).toArray();
    if (rows.length === 0) return null;
    const response = rows[0];
    const headers = new Headers(JSON.parse(response.headers));
    headers.set("Cache-Control", "private, no-store");
    headers.set("Leaf-State-Source", "durable");
    if (head || response.status === 204 || response.status === 304) {
      return new Response(null, { status: response.status, headers });
    }
    if (response.asset !== null) {
      const asset = await this.assets.fetch(new Request(new URL(response.asset, "https://leaf.page")));
      if (!asset.ok) throw new Error(`saved page asset returned ${asset.status}`);
      return new Response(asset.body, { status: response.status, headers });
    }
    const body = this.body(JSON.parse(response.chunks!));
    if (path === "api/state" || path.startsWith("api/state?")) {
      // Date this delivery so a tab can adopt its dormant reading after a live one;
      // Python's semantic clock and folded facts remain captured.
      const state = await new Response(body).json() as Record<string, unknown>;
      state.taken = Date.now() / 1000;
      headers.delete("Content-Length");
      return Response.json(state, { status: response.status, headers });
    }
    return new Response(body, { status: response.status, headers });
  }
}
