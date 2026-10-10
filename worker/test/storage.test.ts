import { describe, expect, it } from "vitest";
import { CHUNK_BYTES, PageStore } from "../src/storage";
import { sqliteStorage } from "./sqlite";

async function upload(store: PageStore, bytes: Uint8Array): Promise<string[]> {
  const chunks = [];
  for (let offset = 0; offset < bytes.length; offset += CHUNK_BYTES) {
    const chunk = bytes.slice(offset, offset + CHUNK_BYTES);
    const digest = Buffer.from(await crypto.subtle.digest("SHA-256", chunk)).toString("hex");
    await store.saveBlob(digest, chunk.buffer);
    chunks.push(digest);
  }
  return chunks;
}

describe("durable website page records", () => {
  it("commits matching records and streamed delivery atomically, without bulk RPC bodies", async () => {
    const { storage, close } = sqliteStorage();
    try {
      const assets = { fetch: async () => new Response("immutable asset") } as unknown as Fetcher;
      const store = new PageStore(storage, assets);
      // Several valid uploads exceed the 32 MiB RPC limit cumulatively. Each
      // transfer remains at most 1 MiB and the publication contains references.
      const record: Record<string, { chunks: string[] }> = {};
      for (let part = 0; part < 40; part++) {
        record[`media/image-${part}.png`] = {
          chunks: await upload(store, new Uint8Array(CHUNK_BYTES).fill(part)),
        };
      }
      const body = new Uint8Array(2_500_000).fill(137);
      const image = await upload(store, body);
      const manifest = {
        ...record,
        ...Object.fromEntries(Array.from({ length: 20_000 }, (_, part) =>
          [`revisions/r3-private/resource-${part}.js`, { chunks: image }],
        )),
      };
      const manifestBytes = new TextEncoder().encode(JSON.stringify(manifest));
      expect(manifestBytes.byteLength).toBeGreaterThan(2 * 1024 * 1024);
      const state = await upload(store, new TextEncoder().encode('{"saved":"choice","taken":1}'));
      const publication = {
        root: "/examples/board", release: "release", record: { chunks: await upload(store, manifestBytes) },
        responses: {
          "api/state": { status: 200, headers: { "Content-Type": "application/json", "Content-Length": "28" }, chunks: state },
          "media/private.png": { status: 200, headers: { "Content-Type": "image/png" }, chunks: image },
          "revisions/leaf.js": { status: 200, headers: {}, asset: "/baseline.js" },
        },
      };
      expect(JSON.stringify(publication).length).toBeLessThan(10_000);
      store.publish(publication);
      store.publish({ root: "/", release: "release", record: { chunks: [] }, responses: {} });
      const restored = new PageStore(storage, assets);
      expect(restored.records()["/examples/board"]).toEqual(publication.record);
      for (const [part, entry] of Object.values(record).entries()) {
        expect(Buffer.from(restored.blob(entry.chunks[0])!).equals(Buffer.alloc(CHUNK_BYTES, part))).toBe(true);
      }
      const response = (await restored.response("/examples/board", "media/private.png", false))!;
      expect(Buffer.from(await response.arrayBuffer()).equals(body)).toBe(true);
      expect(response.headers.get("Cache-Control")).toBe("private, no-store");
      expect(await restored.response("/", "api/state", false)).toBeNull();
      expect(await (await restored.response("/examples/board", "media/private.png", true))!.text()).toBe("");
      expect(await (await restored.response("/examples/board", "revisions/leaf.js", false))!.text()).toBe("immutable asset");
      const savedState = (await restored.response("/examples/board", "api/state", false))!;
      expect(savedState.headers.has("Content-Length")).toBe(false);
      expect(await savedState.json()).toMatchObject({ saved: "choice" });

      // Unfinished uploads cannot replace either the record or its delivery.
      expect(() => restored.publish({
        root: "/examples/board", release: "release", record: { chunks: [] },
        responses: { "api/state": { status: 200, headers: {}, chunks: ["f".repeat(64)] } },
      })).toThrow("missing page storage chunk");
      expect(await (await restored.response("/examples/board", "api/state", false))!.json()).toMatchObject({ saved: "choice" });
      expect(restored.records()["/examples/board"]).toEqual(publication.record);
      await expect(store.saveBlob("a".repeat(64), new Uint8Array(CHUNK_BYTES + 1).buffer)).rejects.toThrow("exceeds 1 MiB");
      await expect(store.saveBlob("a".repeat(64), new Uint8Array([1]).buffer)).rejects.toThrow("digest does not match");
    } finally {
      close();
    }
  });
});
