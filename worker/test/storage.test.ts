import { describe, expect, it } from "vitest";
import { unpackTar } from "modern-tar";
import { CHUNK_BYTES, PageStore, type PagePublication } from "../src/storage";
import { sqliteStorage } from "./sqlite";

async function capture(bytes: Uint8Array, blobs: Map<string, Uint8Array>): Promise<string[]> {
  const chunks = [];
  for (let offset = 0; offset < bytes.length; offset += CHUNK_BYTES) {
    const chunk = bytes.slice(offset, offset + CHUNK_BYTES);
    const digest = Buffer.from(await crypto.subtle.digest("SHA-256", chunk)).toString("hex");
    blobs.set(digest, chunk);
    chunks.push(digest);
  }
  return chunks;
}

async function stage(store: PageStore, publication: PagePublication, blobs: Map<string, Uint8Array>) {
  const missing = store.prepare(publication);
  for (const digest of missing) await store.saveBlob(digest, blobs.get(digest)!.slice().buffer);
}

async function records(store: PageStore): Promise<Record<string, PagePublication["record"]>> {
  const entries = await unpackTar(store.records().body!);
  return JSON.parse(new TextDecoder().decode(entries[0].data!));
}

function page(root: string, chunks: string[]): PagePublication {
  return { root, release: "release", record: { "events.jsonl": { chunks, modified: 1_700_000_000.125 } }, responses: {} };
}

describe("durable website page records", () => {
  it("keeps revision descriptors below the SQL row limit as history exceeds 2 MB", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const store = new PageStore(storage);
      const blobs = new Map<string, Uint8Array>();
      const chunks = await capture(new TextEncoder().encode("immutable module"), blobs);
      const publication = page("/examples/heat-loss", []);
      // Heat-loss captures roughly 155 resources per revision. Thirty revisions
      // exceed the platform's 2 MB row limit even with one tiny shared body.
      for (let revision = 1; revision <= 30; revision++) {
        for (let resource = 0; resource < 155; resource++) {
          const path = `revisions/r${revision}-0123456789abcdef/runtime/modules/resource-${resource}.js`;
          publication.record[path] = { chunks, modified: 1_700_000_000.125 };
          publication.responses[path] = {
            status: 200,
            headers: {
              "content-type": "application/javascript; charset=utf-8",
              "content-length": "16",
              "cache-control": "private, no-store",
              etag: `"${"a".repeat(64)}"`,
              "leaf-server": "website-release",
            },
            chunks,
          };
        }
      }
      expect(Buffer.byteLength(JSON.stringify(publication))).toBeGreaterThan(2_000_000);
      await stage(store, publication, blobs);
      store.publish(publication);
      expect((await records(new PageStore(storage)))[publication.root]).toEqual(publication.record);
      const sizes = storage.sql.exec<{ bytes: number }>(`SELECT MAX(
        length(root) + length(path) + length(headers) + length(chunks) + 16
      ) AS bytes FROM leaf_responses`).toArray();
      expect(sizes[0].bytes).toBeLessThan(2_000_000);
      const last = Object.keys(publication.responses).at(-1)!;
      expect(await (await store.response(publication.root, last, false))!.text()).toBe("immutable module");
    } finally {
      close();
    }
  });

  it("commits matching records and streamed delivery atomically, without bulk RPC bodies", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const store = new PageStore(storage);
      const blobs = new Map<string, Uint8Array>();
      // A single allowed image spans storage chunks; manifests carry references.
      const body = new Uint8Array(2_500_000).fill(137);
      const image = await capture(body, blobs);
      const state = await capture(new TextEncoder().encode(JSON.stringify({
        saved: "choice", taken: 1, now: "1970-01-01T00:00:01.000Z",
        activity: { status: "waiting", since: "1970-01-01T00:00:01.000Z" },
      })), blobs);
      const entry = await capture(new TextEncoder().encode('import "./runtime/private.js";'), blobs);
      const publication = {
        root: "/examples/board", release: "release", record: { "media/private.png": { chunks: image, modified: 1_700_000_000.125 } },
        responses: {
          "api/state": { status: 200, headers: { "Content-Type": "application/json", "Content-Length": "28" }, chunks: state },
          "media/private.png": { status: 200, headers: { "Content-Type": "image/png" }, chunks: image },
          "revisions/leaf.js": { status: 200, headers: {}, chunks: entry },
        },
      };
      expect(JSON.stringify(publication).length).toBeLessThan(10_000);
      await stage(store, publication, blobs);
      store.publish(publication);
      const empty = page("/", []);
      await stage(store, empty, blobs);
      store.publish(empty);
      const restored = new PageStore(storage);
      expect((await records(restored))["/examples/board"]).toEqual(publication.record);
      const response = (await restored.response("/examples/board", "media/private.png", false))!;
      expect(Buffer.from(await response.arrayBuffer()).equals(body)).toBe(true);
      expect(response.headers.get("Cache-Control")).toBe("private, no-store");
      expect(await restored.response("/", "api/state", false)).toBeNull();
      expect(await (await restored.response("/examples/board", "media/private.png", true))!.text()).toBe("");
      expect(await (await restored.response("/examples/board", "revisions/leaf.js", false))!.text()).toBe('import "./runtime/private.js";');
      const requestedAt = Date.now();
      const savedState = (await restored.response("/examples/board", "api/state", false))!;
      expect(savedState.headers.has("Content-Length")).toBe(false);
      const delivered = await savedState.json() as {
        saved: string; taken: number; now: string; activity: { status: string; since: string };
      };
      expect(delivered).toMatchObject({
        saved: "choice", activity: { status: "waiting", since: "1970-01-01T00:00:01.000Z" },
      });
      expect(Date.parse(delivered.now)).toBe(delivered.taken * 1000);
      expect(Date.parse(delivered.now)).toBeGreaterThanOrEqual(requestedAt);

      const unfinished = {
        ...publication, record: {},
        responses: { "api/state": { status: 200, headers: {}, chunks: ["f".repeat(64)] } },
      };
      restored.prepare(unfinished);
      expect(() => restored.publish(unfinished)).toThrow("missing page storage chunk");
      expect(await (await restored.response("/examples/board", "api/state", false))!.json()).toMatchObject({ saved: "choice" });
      expect((await records(restored))["/examples/board"]).toEqual(publication.record);
      await expect(store.saveBlob("a".repeat(64), new Uint8Array(CHUNK_BYTES + 1).buffer)).rejects.toThrow("exceeds 1 MiB");
      await expect(store.saveBlob("a".repeat(64), new Uint8Array([1]).buffer)).rejects.toThrow("digest does not match");
    } finally {
      close();
    }
  });

  it("reclaims old log tails and interrupted successors while protecting another page's upload", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const store = new PageStore(storage);
      const blobs = new Map<string, Uint8Array>();
      const held = page("/other", await capture(new Uint8Array([7]), blobs));
      await stage(store, held, blobs);
      for (let index = 0; index < 30; index++) {
        const tail = new Uint8Array(512_000 + index).fill(97);
        tail[tail.length - 1] = index;
        const publication = page("/", await capture(tail, blobs));
        await stage(store, publication, blobs);
        store.publish(publication);
      }
      expect(store.blob(held.record["events.jsonl"].chunks[0])).not.toBeNull();
      store.publish(held);
      expect(storage.sql.exec<{ size: number }>("SELECT sum(length(bytes)) size FROM leaf_blobs").toArray()[0].size)
        .toBe(512_030);
      const abandoned = page("/", await capture(new Uint8Array([8]), blobs));
      await stage(store, abandoned, blobs);
      const next = page("/", await capture(new Uint8Array([9]), blobs));
      await stage(store, next, blobs);
      expect(store.blob(abandoned.record["events.jsonl"].chunks[0])).toBeNull();
      expect((await records(store))["/"]["events.jsonl"].chunks).not.toEqual(next.record["events.jsonl"].chunks);
      store.publish(next);
      expect(storage.sql.exec<{ size: number }>("SELECT sum(length(bytes)) size FROM leaf_blobs").toArray()[0].size).toBe(2);
      const rogue = new Uint8Array([10]);
      const [digest] = await capture(rogue, blobs);
      await expect(store.saveBlob(digest, rogue.buffer)).rejects.toThrow("no staged owner");
    } finally {
      close();
    }
  });

  it("retains chunks of replaced delivery and restore snapshots until readers finish or cancel", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const store = new PageStore(storage);
      const blobs = new Map<string, Uint8Array>();
      const bytes = new Uint8Array(2_500_000);
      bytes.fill(1, 0, CHUNK_BYTES);
      bytes.fill(2, CHUNK_BYTES, 2 * CHUNK_BYTES);
      const chunks = await capture(bytes, blobs);
      const first = { ...page("/", chunks), responses: { "media/file": { status: 200, headers: {}, chunks } } };
      first.record["revisions/r2-private/shared.js"] = { chunks: [...chunks, chunks[0]], modified: 1_700_000_000 };
      await stage(store, first, blobs);
      store.publish(first);
      const neighbor = page("/other", chunks);
      await stage(store, neighbor, blobs);
      store.publish(neighbor);
      const reading = (await store.response("/", "media/file", false))!;
      const cancelled = (await store.response("/", "media/file", false))!;
      const restored = store.records();
      const cancelledRestore = store.records();
      const next = page("/", []);
      await stage(store, next, blobs);
      store.publish(next);
      const emptyNeighbor = page("/other", []);
      await stage(store, emptyNeighbor, blobs);
      store.publish(emptyNeighbor);
      expect(Buffer.from(await reading.arrayBuffer()).equals(bytes)).toBe(true);
      expect(store.blob(chunks[2])).not.toBeNull();
      const archive = await unpackTar(restored.body!);
      expect(archive.map(({ header }) => header.name)).toEqual(["records.json", ...chunks]);
      expect(JSON.parse(new TextDecoder().decode(archive[0].data!))).toEqual({ "/": first.record, "/other": neighbor.record });
      expect(Buffer.concat(archive.slice(1).map(({ data }) => Buffer.from(data!))).equals(bytes)).toBe(true);
      await cancelled.body!.cancel();
      expect(store.blob(chunks[2])).not.toBeNull();
      await cancelledRestore.body!.cancel();
      expect(store.blob(chunks[2])).toBeNull();
    } finally {
      close();
    }
  });
});
