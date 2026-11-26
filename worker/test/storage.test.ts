import type {
  ServedDraftsAnswer,
  ServedNewsAnswer,
  ServedState,
} from "../../browser/types/contract.js";
import { describe, expect, it } from "vitest";
import { unpackTar } from "modern-tar";
import { createHash } from "node:crypto";
import {
  CHUNK_BYTES,
  PageStore,
  STORE_FORMAT,
  STORE_TABLES,
  type PagePublication,
} from "../src/storage";
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
  release = RELEASE,
) {
  const { identity, missing } = await store.prepare(publication, {
    ...manifest,
    release,
  });
  for (const digest of missing)
    await store.saveBlob(digest, blobs.get(digest)!.slice().buffer);
  return { root: publication.root, identity };
}

async function snapshot(
  store: PageStore,
  release = manifest,
): Promise<{
  records: Record<string, PagePublication["record"]>;
  drafts: Record<string, ServedDraftsAnswer>;
}> {
  const entries = await unpackTar(store.records(release).body!);
  return JSON.parse(new TextDecoder().decode(entries[0].data!));
}

async function records(
  store: PageStore,
): Promise<Record<string, PagePublication["record"]>> {
  return (await snapshot(store)).records;
}

function page(root: string, chunks: string[]): PagePublication {
  return {
    root,
    record: { "events.jsonl": { chunks, modified: 1_700_000_000.125 } },
    responses: {},
  };
}

const RELEASE = "a".repeat(64);
const manifest = {
  release: RELEASE,
  drafts_format: "leaf-drafts/51",
  pages: Object.fromEntries(
    ["/", "/other", "/examples/board", "/examples/heat-loss"].map((root) => [root, {}]),
  ),
};

// The table shape each store format holds, as a digest of `STORE_TABLES`. A visitor's
// store outlives deploys, so a change to the tables moves `STORE_FORMAT` and adds its
// shape here; the earlier formats' entries stay, so none is rewritten in place.
const FORMATS: Record<number, string> = {
  1: "5bf1a647f4748ee6",
  2: "8b82439f6ccbc39f",
};

describe("durable website page records", () => {
  it("moves its store format with the shape of its tables", () => {
    const shape = createHash("sha256").update(STORE_TABLES).digest("hex").slice(0, 16);
    expect(
      FORMATS[STORE_FORMAT],
      "the store's tables changed: move STORE_FORMAT and record this shape for it",
    ).toBe(shape);
  });

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
              "cache-control": "private, max-age=31536000, immutable",
              etag: `"${"a".repeat(64)}"`,
              "leaf-server": "website-release",
            },
            chunks,
          };
        }
      }
      expect(Buffer.byteLength(JSON.stringify(publication))).toBeGreaterThan(2_000_000);
      const publicationCommit = await stage(store, publication, blobs);
      store.publish(publicationCommit);
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
          manifest,
        ))!.text(),
      ).toBe("immutable module");
    } finally {
      await new Promise((resolve) => setImmediate(resolve));
      close();
    }
  });

  it("restores a page saved by an earlier release but serves its responses only to that release", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const store = new PageStore(storage);
      const blobs = new Map<string, Uint8Array>();
      const document = await capture(
        new TextEncoder().encode('<script src="/_leaf-release/a/leaf.js"></script>'),
        blobs,
      );
      const publication = {
        ...page("/", document),
        responses: {
          "": { headers: { "Content-Type": "text/html" }, chunks: document },
        },
      };
      store.publish(await stage(store, publication, blobs));
      const request = new Request("https://leaf.page/");
      expect(await store.response("/", "", request, manifest)).not.toBeNull();
      // The next release's container restores the record whole, and wakes for the
      // document rather than serving one that names the earlier release's assets.
      const next = { ...manifest, release: "b".repeat(64) };
      expect((await records(store))["/"]).toEqual(publication.record);
      expect(await store.response("/", "", request, next)).toBeNull();
      store.publish(await stage(store, publication, blobs, next.release));
      expect(await store.response("/", "", request, next)).not.toBeNull();
      expect(await store.response("/", "", request, manifest)).toBeNull();
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
        record: { "media/private.png": { chunks: image, modified: 1_700_000_000.125 } },
        responses: {
          "api/state": {
            headers: { "Content-Type": "application/json", "Content-Length": "28" },
            chunks: state,
          },
          "media/private.png": {
            headers: {
              "Content-Type": "image/png",
              "Cache-Control": "private, max-age=31536000, immutable",
            },
            chunks: image,
          },
          "revisions/leaf.js": { headers: {}, chunks: entry },
        },
      };
      expect(JSON.stringify(publication).length).toBeLessThan(10_000);
      const publicationCommit = await stage(store, publication, blobs);
      store.publish(publicationCommit);
      const empty = page("/", []);
      const emptyCommit = await stage(store, empty, blobs);
      store.publish(emptyCommit);
      const restored = new PageStore(storage);
      expect((await records(restored))["/examples/board"]).toEqual(publication.record);
      const response = (await restored.response(
        "/examples/board",
        "media/private.png",
        new Request("https://leaf.page/"),
        manifest,
      ))!;
      expect(Buffer.from(await response.arrayBuffer()).equals(body)).toBe(true);
      // Served as Python captured it, so it is cached as the live answer would be.
      expect(response.headers.get("Cache-Control")).toBe(
        "private, max-age=31536000, immutable",
      );
      expect(
        await restored.response(
          "/",
          "api/state",
          new Request("https://leaf.page/"),
          manifest,
        ),
      ).toBeNull();
      expect(
        await (await restored.response(
          "/examples/board",
          "media/private.png",
          new Request("https://leaf.page/", { method: "HEAD" }),
          manifest,
        ))!.text(),
      ).toBe("");
      expect(
        await (await restored.response(
          "/examples/board",
          "revisions/leaf.js",
          new Request("https://leaf.page/"),
          manifest,
        ))!.text(),
      ).toBe('import "./runtime/private.js";');
      const requestedAt = Date.now();
      const savedState = (await restored.response(
        "/examples/board",
        "api/state",
        new Request("https://leaf.page/"),
        manifest,
      ))!;
      expect(savedState.headers.has("Content-Length")).toBe(false);
      for (const version of ["v1", "stale"]) {
        const response = (await restored.response(
          "/examples/board",
          "api/state",
          new Request("https://leaf.page/api/state", {
            headers: { "Leaf-Data-Version": version },
          }),
          manifest,
        ))!;
        const reading = await response.json<Pick<ServedState, "taken" | "data">>();
        expect(reading).toMatchObject({ saved: "choice" });
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
      const delivered = await savedState.json<Pick<ServedState, "taken" | "now">>();
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
      expect(() => restored.publish(unfinishedCommit)).toThrow(
        "missing page storage chunk",
      );
      expect(
        await (await restored.response(
          "/examples/board",
          "api/state",
          new Request("https://leaf.page/"),
          manifest,
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

  it("commits identical prepared content by identity and rejects replaced content or a page outside the release", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const store = new PageStore(storage);
      const blobs = new Map<string, Uint8Array>();
      const first = page("/", await capture(new Uint8Array([1]), blobs));
      const commit = await stage(store, first, blobs);
      // Dictionary order is serialization detail, while chunk order is content.
      const repeated = await store.prepare(
        { responses: first.responses, record: first.record, root: first.root },
        manifest,
      );
      expect(repeated.identity).toBe(commit.identity);
      store.publish(commit);
      const successor = page("/", await capture(new Uint8Array([2]), blobs));
      const next = await stage(store, successor, blobs);
      expect(() => store.publish(commit)).toThrow("was not staged");
      await expect(store.prepare(page("/missing", []), manifest)).rejects.toThrow(
        "does not name a page in this website release",
      );
      expect((await records(store))["/"]).toEqual(first.record);
      store.publish(next);
      expect((await records(store))["/"]).toEqual(successor.record);
    } finally {
      await new Promise((resolve) => setImmediate(resolve));
      close();
    }
  });

  it("serves and restores a page's drafts store, which no later commit puts back", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const store = new PageStore(storage);
      const blobs = new Map<string, Uint8Array>();
      const reading = (version: number, text: string): ServedDraftsAnswer => ({
        store: "store-1",
        version,
        drafts: { general: { attempt: `a${version}`, text, version } },
      });
      const captured = reading(1, "Words the commit captured");
      const headers = {
        "Content-Type": "application/json",
        "Content-Length": "1",
        "Leaf-Release": "release",
      };
      const commit = async () => {
        const publication = page("/", []);
        for (const [path, body] of [
          ["api/drafts", captured],
          [
            "api/news",
            { reading: "r1", pages: null, drafts: { store: "store-1", version: 1 } },
          ],
        ] as const)
          publication.responses[path] = {
            headers,
            chunks: await capture(
              new TextEncoder().encode(JSON.stringify(body)),
              blobs,
            ),
          };
        store.publish(await stage(store, publication, blobs));
      };
      await commit();
      const latest = reading(3, "Words typed since");
      store.saveDrafts({ root: "/", replaces: null, drafts: latest }, manifest);
      // A commit that captured its drafts before the latest write lands after it.
      await commit();
      const get = (path: string) =>
        store.response("/", path, new Request("https://leaf.page/"), manifest);
      const drafts = (await get("api/drafts"))!;
      expect(await drafts.json()).toEqual(latest);
      expect(drafts.headers.has("Content-Length")).toBe(false);
      expect(drafts.headers.get("Leaf-Release")).toBe("release");
      expect(await (await get("api/news"))!.json<ServedNewsAnswer>()).toEqual({
        reading: "r1",
        pages: null,
        drafts: { store: "store-1", version: 3 },
      });
      // A page whose only write is a draft has no saved document to serve, and its
      // store still restores.
      const other = reading(1, "Typed on a page never sent to");
      store.saveDrafts({ root: "/other", replaces: null, drafts: other }, manifest);
      expect(
        await store.response(
          "/other",
          "api/drafts",
          new Request("https://leaf.page/"),
          manifest,
        ),
      ).toBeNull();
      expect((await snapshot(new PageStore(storage))).drafts).toEqual({
        "/": latest,
        "/other": other,
      });
      expect(() =>
        store.saveDrafts(
          { root: "/missing", replaces: null, drafts: latest },
          manifest,
        ),
      ).toThrow("not name a page in this website release");
    } finally {
      await new Promise((resolve) => setImmediate(resolve));
      close();
    }
  });

  it("takes a drafts save only over the store it replaces, so a late save changes nothing", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const store = new PageStore(storage);
      const reading = (version: number, text: string): ServedDraftsAnswer => ({
        store: "store-1",
        version,
        drafts: { general: { attempt: text, text, version } },
      });
      const save = (
        replaces: { store: string; version: number } | null,
        drafts: ServedDraftsAnswer,
      ) => store.saveDrafts({ root: "/", replaces, drafts }, manifest);
      const first = reading(1, "First words");
      expect(save(null, first)).toEqual(first);
      // Two saves over the same store, with the same next version: the one taken
      // first is acknowledged, and the other, arriving late, finds it held.
      const acknowledged = reading(2, "Words the tab was answered for");
      expect(save({ store: "store-1", version: 1 }, acknowledged)).toEqual(
        acknowledged,
      );
      expect(save({ store: "store-1", version: 1 }, reading(2, "A late save"))).toEqual(
        acknowledged,
      );
      expect(save(null, reading(1, "A new store's first save"))).toEqual(acknowledged);
      expect((await snapshot(store)).drafts).toEqual({ "/": acknowledged });
    } finally {
      await new Promise((resolve) => setImmediate(resolve));
      close();
    }
  });

  it("reads and replaces only the drafts stores written at its own drafts shape", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const store = new PageStore(storage);
      const reading = (identity: string, text: string): ServedDraftsAnswer => ({
        store: identity,
        version: 1,
        drafts: { general: { attempt: text, text, version: 1 } },
      });
      const earlier = reading("store-1", "Words written at the earlier shape");
      store.saveDrafts({ root: "/", replaces: null, drafts: earlier }, manifest);
      // A release whose Leaf changed the drafts' shape, at the same page protocol,
      // finds no store, and starts its own beside the earlier one.
      const next = {
        ...manifest,
        release: "b".repeat(64),
        drafts_format: "leaf-drafts/57",
      };
      expect((await snapshot(store, next)).drafts).toEqual({});
      const later = reading("store-2", "Words written at the later shape");
      expect(
        store.saveDrafts({ root: "/", replaces: null, drafts: later }, next),
      ).toEqual(later);
      expect((await snapshot(store, next)).drafts).toEqual({ "/": later });
      // A release back at the earlier shape, as after a rollback, finds its store as
      // it left it.
      expect((await snapshot(store)).drafts).toEqual({ "/": earlier });
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
        store.publish(publicationCommit);
      }
      expect(store.blob(held.record["events.jsonl"].chunks[0])).not.toBeNull();
      store.publish(heldCommit);
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
      store.publish(nextCommit);
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
      store.publish(firstCommit);
      const neighbor = page("/other", chunks);
      const neighborCommit = await stage(store, neighbor, blobs);
      store.publish(neighborCommit);
      const reading = (await store.response(
        "/",
        "media/file",
        new Request("https://leaf.page/"),
        manifest,
      ))!;
      const cancelled = (await store.response(
        "/",
        "media/file",
        new Request("https://leaf.page/"),
        manifest,
      ))!;
      const restored = store.records(manifest);
      const cancelledRestore = store.records(manifest);
      const next = page("/", []);
      const nextCommit = await stage(store, next, blobs);
      store.publish(nextCommit);
      const emptyNeighbor = page("/other", []);
      const emptyNeighborCommit = await stage(store, emptyNeighbor, blobs);
      store.publish(emptyNeighborCommit);
      expect(Buffer.from(await reading.arrayBuffer()).equals(bytes)).toBe(true);
      expect(store.blob(chunks[2])).not.toBeNull();
      const archive = await unpackTar(restored.body!);
      expect(archive.map(({ header }) => header.name)).toEqual([
        "records.json",
        ...chunks,
      ]);
      expect(JSON.parse(new TextDecoder().decode(archive[0].data!))).toEqual({
        records: { "/": first.record, "/other": neighbor.record },
        drafts: {},
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
