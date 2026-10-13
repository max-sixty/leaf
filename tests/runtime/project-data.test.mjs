import assert from "node:assert/strict";
import test from "node:test";

// The context reads export delivery once, when its modules load. Supply the same
// captured payload an exported page carries before importing the runtime graph.
const exported = document.createElement("script");
exported.type = "application/json";
exported.dataset.lfRuntime = "";
exported.dataset.lfOffline = "";
const reading = {
  contract: "optional-payload",
  revision: "r1",
  value: {
    files: [
      { key: "metadata" },
      { key: "empty", patch: null },
      { key: "text", patch: { contents: "evidence" } },
    ],
  },
};
const data = { version: "v1", sources: { files: reading } };
exported.textContent = JSON.stringify({ data });
document.head.append(exported);
const { loadDeferred, acceptData } = await import("/runtime/data.js");
const { adoptRegistry } = await import("/runtime/registry.js");
const { createDataProjection } = await import("/runtime/projection/data.js");
exported.remove();

test("a datum's key and identity must be words, since a comment's anchor keeps them", () => {
  // An object stringifies to the same "[object Object]" as the next one, so a comment
  // anchored on it would follow whichever datum replaced it.
  const { projectData } = createDataProjection({ invalidateDom() {} });
  const root = document.createElement("section");
  root.id = "rows";
  const row = document.createElement("p");
  root.append(row);
  document.body.append(root);
  const row1 = { id: "row-1" };
  assert.throws(
    () => projectData(root, [{ node: row, key: row1 }]),
    /keys must be non-empty strings/,
  );
  assert.throws(
    () => projectData(root, [{ node: row, key: "row-1", identity: row1 }]),
    /identity for row-1 must be a non-empty string/,
  );
  projectData(root, [{ node: row, key: "row-1", identity: "row-1" }]);
  assert.equal(row.dataset.lfIdentity, "row-1");
  root.remove();
});

test("offline deferred reads refuse absent payloads while retaining valid null", async () => {
  adoptRegistry({
    $data: {
      contracts: {
        "optional-payload": {
          records: { items: "files", key: "key", deferred: "patch" },
        },
      },
    },
  });
  acceptData(data, 1);
  const manifest = { source: "files", ...reading };
  assert.equal(await loadDeferred(manifest, "empty"), null);
  const evidence = await loadDeferred(manifest, "text");
  assert.deepEqual(evidence, { contents: "evidence" });
  evidence.contents = "changed copy";
  assert.deepEqual(await loadDeferred(manifest, "text"), { contents: "evidence" });
  await assert.rejects(loadDeferred(manifest, "metadata"), /no deferred field 'patch'/);
  await assert.rejects(
    loadDeferred(manifest, "unknown"),
    /unknown record key 'unknown'/,
  );
});
