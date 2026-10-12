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
      const store = new PageStore(storage);
      // A single allowed image spans storage chunks; manifests carry references.
      const body = new Uint8Array(2_500_000).fill(137);
      const image = await upload(store, body);
      const manifestBytes = new TextEncoder().encode(JSON.stringify({
        "media/private.png": { chunks: image },
      }));
      const state = await upload(store, new TextEncoder().encode(JSON.stringify({
        saved: "choice", taken: 1, now: "1970-01-01T00:00:01.000Z",
        activity: { status: "waiting", since: "1970-01-01T00:00:01.000Z" },
      })));
      const entry = await upload(store, new TextEncoder().encode('import "./runtime/private.js";'));
      const publication = {
        root: "/examples/board", release: "release", record: { chunks: await upload(store, manifestBytes) },
        responses: {
          "api/state": { status: 200, headers: { "Content-Type": "application/json", "Content-Length": "28" }, chunks: state },
          "media/private.png": { status: 200, headers: { "Content-Type": "image/png" }, chunks: image },
          "revisions/leaf.js": { status: 200, headers: {}, chunks: entry },
        },
      };
      expect(JSON.stringify(publication).length).toBeLessThan(10_000);
      store.publish(publication);
      store.publish({ root: "/", release: "release", record: { chunks: [] }, responses: {} });
      const restored = new PageStore(storage);
      expect(restored.missing([...image, "f".repeat(64), "f".repeat(64)]))
        .toEqual(["f".repeat(64)]);
      expect(restored.records()["/examples/board"]).toEqual(publication.record);
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
      // A saved response must not pull the browser's clock back to publication.
      expect(Date.parse(delivered.now)).toBe(delivered.taken * 1000);
      expect(Date.parse(delivered.now)).toBeGreaterThanOrEqual(requestedAt);

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
