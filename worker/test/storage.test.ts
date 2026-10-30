import { describe, expect, it } from "vitest";
import { unpackTar } from "modern-tar";
import { CHUNK_BYTES, PageStore, type PagePublication } from "../src/storage";
import { sqliteStorage } from "./sqlite";

async function capture(
  bytes: Uint8Array,
  blobs: Map<string, Uint8Array>,
): Promise<string[]> {
  const chunks = [];
  for (let offset = 0; offset < bytes.length; offset += CHUNK_BYTES) {
    const chunk = bytes.slice(offset, offset + CHUNK_BYTES);
    const digest = Buffer.from(await crypto.subtle.digest("SHA-256", chunk)).toString(
      "hex",
    );
    blobs.set(digest, chunk);
    chunks.push(digest);
  }
  return chunks;
}

async function stage(
  store: PageStore,
  publication: PagePublication,
  blobs: Map<string, Uint8Array>,
) {
  const { identity, missing } = await store.prepare(publication, manifest);
  for (const digest of missing)
    await store.saveBlob(digest, blobs.get(digest)!.slice().buffer);
  return { root: publication.root, identity };
}

async function records(
  store: PageStore,
): Promise<Record<string, PagePublication["record"]>> {
  const entries = await unpackTar(store.records().body!);
  return JSON.parse(new TextDecoder().decode(entries[0].data!));
}

function page(root: string, chunks: string[]): PagePublication {
  return {
    root,
    release: "release",
    record: { "events.jsonl": { chunks, modified: 1_700_000_000.125 } },
    responses: {},
  };
}

const manifest = {
  release: "release",
  pages: Object.fromEntries(
    ["/", "/other", "/examples/board", "/examples/heat-loss"].map((root) => [root, {}]),
  ),
};

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
      const publicationCommit = await stage(store, publication, blobs);
      store.publish(publicationCommit, manifest);
      expect((await records(new PageStore(storage)))[publication.root]).toEqual(
        publication.record,
      );
      const sizes = storage.sql
        .exec<{ bytes: number }>(
          `SELECT MAX(
        length(root) + length(path) + length(headers) + length(chunks) + 16
      ) AS bytes FROM leaf_responses`,
        )
        .toArray();
      expect(sizes[0].bytes).toBeLessThan(2_000_000);
      const last = Object.keys(publication.responses).at(-1)!;
      expect(
        await (await store.response(
          publication.root,
          last,
          new Request("https://leaf.page/"),
        ))!.text(),
      ).toBe("immutable module");
    } finally {
      await new Promise((resolve) => setImmediate(resolve));
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
      const state = await capture(
        new TextEncoder().encode(
          JSON.stringify({
            saved: "choice",
            data: {
              version: "v1",
              sources: { notes: { contract: "text", value: "Saved" } },
            },
            taken: 1,
            now: "1970-01-01T00:00:01.000Z",
            activity: { status: "waiting", since: "1970-01-01T00:00:01.000Z" },
          }),
        ),
        blobs,
      );
      const entry = await capture(
        new TextEncoder().encode('import "./runtime/private.js";'),
        blobs,
      );
      const publication = {
        root: "/examples/board",
        release: "release",
        record: { "media/private.png": { chunks: image, modified: 1_700_000_000.125 } },
        responses: {
          "api/state": {
            headers: { "Content-Type": "application/json", "Content-Length": "28" },
            chunks: state,
          },
          "media/private.png": {
            headers: { "Content-Type": "image/png" },
            chunks: image,
          },
          "revisions/leaf.js": { headers: {}, chunks: entry },
        },
      };
      expect(JSON.stringify(publication).length).toBeLessThan(10_000);
      const publicationCommit = await stage(store, publication, blobs);
      store.publish(publicationCommit, manifest);
      const empty = page("/", []);
      const emptyCommit = await stage(store, empty, blobs);
      store.publish(emptyCommit, manifest);
      const restored = new PageStore(storage);
      expect((await records(restored))["/examples/board"]).toEqual(publication.record);
      const response = (await restored.response(
        "/examples/board",
        "media/private.png",
        new Request("https://leaf.page/"),
      ))!;
      expect(Buffer.from(await response.arrayBuffer()).equals(body)).toBe(true);
      expect(response.headers.get("Cache-Control")).toBe("private, no-store");
      expect(
        await restored.response("/", "api/state", new Request("https://leaf.page/")),
      ).toBeNull();
      expect(
        await (await restored.response(
          "/examples/board",
          "media/private.png",
          new Request("https://leaf.page/", { method: "HEAD" }),
        ))!.text(),
      ).toBe("");
      expect(
        await (await restored.response(
          "/examples/board",
          "revisions/leaf.js",
          new Request("https://leaf.page/"),
        ))!.text(),
      ).toBe('import "./runtime/private.js";');
      const requestedAt = Date.now();
      const savedState = (await restored.response(
        "/examples/board",
        "api/state",
        new Request("https://leaf.page/"),
      ))!;
      expect(savedState.headers.has("Content-Length")).toBe(false);
      for (const version of ["v1", "stale"]) {
        const response = (await restored.response(
          "/examples/board",
          "api/state",
          new Request("https://leaf.page/api/state", {
            headers: { "Leaf-Data-Version": version },
          }),
        ))!;
        const reading = await response.json();
        expect(reading.saved).toBe("choice");
        expect(reading.taken).toBeGreaterThan(1);
        expect(reading.data).toEqual(
          version === "v1"
            ? { version: "v1" }
            : {
                version: "v1",
                sources: { notes: { contract: "text", value: "Saved" } },
              },
        );
      }
      const delivered = (await savedState.json()) as {
        saved: string;
        taken: number;
        now: string;
        activity: { status: string; since: string };
      };
      expect(delivered).toMatchObject({
        saved: "choice",
        activity: { status: "waiting", since: "1970-01-01T00:00:01.000Z" },
      });
      expect(Date.parse(delivered.now)).toBe(delivered.taken * 1000);
      expect(Date.parse(delivered.now)).toBeGreaterThanOrEqual(requestedAt);

      const unfinished = {
        ...publication,
        record: {},
        responses: {
          "api/state": { headers: {}, chunks: ["f".repeat(64)] },
        },
      };
      const { identity } = await restored.prepare(unfinished, manifest);
      const unfinishedCommit = { root: unfinished.root, identity };
      expect(() => restored.publish(unfinishedCommit, manifest)).toThrow(
        "missing page storage chunk",
      );
      expect(
        await (await restored.response(
          "/examples/board",
          "api/state",
          new Request("https://leaf.page/"),
        ))!.json(),
      ).toMatchObject({ saved: "choice" });
      expect((await records(restored))["/examples/board"]).toEqual(publication.record);
      await expect(
        store.saveBlob("a".repeat(64), new Uint8Array(CHUNK_BYTES + 1).buffer),
      ).rejects.toThrow("exceeds 1 MiB");
      await expect(
        store.saveBlob("a".repeat(64), new Uint8Array([1]).buffer),
      ).rejects.toThrow("digest does not match");
    } finally {
      await new Promise((resolve) => setImmediate(resolve));
      close();
    }
  });

  it("commits identical prepared content by identity and rejects replaced content or a changed release", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const store = new PageStore(storage);
      const blobs = new Map<string, Uint8Array>();
      const first = page("/", await capture(new Uint8Array([1]), blobs));
      const commit = await stage(store, first, blobs);
      // Dictionary order is serialization detail, while chunk order is content.
      const repeated = await store.prepare(
        {
          responses: first.responses,
          record: first.record,
          release: first.release,
          root: first.root,
        },
        manifest,
      );
      expect(repeated.identity).toBe(commit.identity);
      store.publish(commit, manifest);
      const successor = page("/", await capture(new Uint8Array([2]), blobs));
      const next = await stage(store, successor, blobs);
      expect(() => store.publish(commit, manifest)).toThrow("was not staged");
      expect(() =>
        store.publish(next, { ...manifest, release: "new-release" }),
      ).toThrow("does not name a page in this website release");
      expect(() => store.publish(next, { ...manifest, pages: {} })).toThrow(
        "does not name a page in this website release",
      );
      expect((await records(store))["/"]).toEqual(first.record);
      store.publish(next, manifest);
      expect((await records(store))["/"]).toEqual(successor.record);
    } finally {
      await new Promise((resolve) => setImmediate(resolve));
      close();
    }
  });

  it("reclaims old log tails and interrupted successors while protecting another page's upload", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const store = new PageStore(storage);
      const blobs = new Map<string, Uint8Array>();
      const held = page("/other", await capture(new Uint8Array([7]), blobs));
      const heldCommit = await stage(store, held, blobs);
      for (let index = 0; index < 30; index++) {
        const tail = new Uint8Array(512_000 + index).fill(97);
        tail[tail.length - 1] = index;
        const publication = page("/", await capture(tail, blobs));
        const publicationCommit = await stage(store, publication, blobs);
        store.publish(publicationCommit, manifest);
      }
      expect(store.blob(held.record["events.jsonl"].chunks[0])).not.toBeNull();
      store.publish(heldCommit, manifest);
      expect(
        storage.sql
          .exec<{ size: number }>("SELECT sum(length(bytes)) size FROM leaf_blobs")
          .toArray()[0].size,
      ).toBe(512_030);
      const abandoned = page("/", await capture(new Uint8Array([8]), blobs));
      await stage(store, abandoned, blobs);
      const next = page("/", await capture(new Uint8Array([9]), blobs));
      const nextCommit = await stage(store, next, blobs);
      expect(store.blob(abandoned.record["events.jsonl"].chunks[0])).toBeNull();
      expect((await records(store))["/"]["events.jsonl"].chunks).not.toEqual(
        next.record["events.jsonl"].chunks,
      );
      store.publish(nextCommit, manifest);
      expect(
        storage.sql
          .exec<{ size: number }>("SELECT sum(length(bytes)) size FROM leaf_blobs")
          .toArray()[0].size,
      ).toBe(2);
      const rogue = new Uint8Array([10]);
      const [digest] = await capture(rogue, blobs);
      await expect(store.saveBlob(digest, rogue.buffer)).rejects.toThrow(
        "no staged owner",
      );
    } finally {
      await new Promise((resolve) => setImmediate(resolve));
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
      const first = {
        ...page("/", chunks),
        responses: { "media/file": { headers: {}, chunks } },
      };
      first.record["revisions/r2-private/shared.js"] = {
        chunks: [...chunks, chunks[0]],
        modified: 1_700_000_000,
      };
      const firstCommit = await stage(store, first, blobs);
      store.publish(firstCommit, manifest);
      const neighbor = page("/other", chunks);
      const neighborCommit = await stage(store, neighbor, blobs);
      store.publish(neighborCommit, manifest);
      const reading = (await store.response(
        "/",
        "media/file",
        new Request("https://leaf.page/"),
      ))!;
      const cancelled = (await store.response(
        "/",
        "media/file",
        new Request("https://leaf.page/"),
      ))!;
      const restored = store.records();
      const cancelledRestore = store.records();
      const next = page("/", []);
      const nextCommit = await stage(store, next, blobs);
      store.publish(nextCommit, manifest);
      const emptyNeighbor = page("/other", []);
      const emptyNeighborCommit = await stage(store, emptyNeighbor, blobs);
      store.publish(emptyNeighborCommit, manifest);
      expect(Buffer.from(await reading.arrayBuffer()).equals(bytes)).toBe(true);
      expect(store.blob(chunks[2])).not.toBeNull();
      const archive = await unpackTar(restored.body!);
      expect(archive.map(({ header }) => header.name)).toEqual([
        "records.json",
        ...chunks,
      ]);
      expect(JSON.parse(new TextDecoder().decode(archive[0].data!))).toEqual({
        "/": first.record,
        "/other": neighbor.record,
      });
      expect(
        Buffer.concat(archive.slice(1).map(({ data }) => Buffer.from(data!))).equals(
          bytes,
        ),
      ).toBe(true);
      await cancelled.body!.cancel();
      await new Promise((resolve) => setImmediate(resolve));
      expect(store.blob(chunks[2])).not.toBeNull();
      await cancelledRestore.body!.cancel();
      await new Promise((resolve) => setImmediate(resolve));
      expect(store.blob(chunks[2])).toBeNull();
    } finally {
      await new Promise((resolve) => setImmediate(resolve));
      close();
    }
  });
});
