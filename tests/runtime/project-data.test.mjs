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
adoptRegistry({
  $data: {
    contracts: {
      "optional-payload": {
        records: { items: "files", key: "key", deferred: "patch" },
      },
    },
  },
});

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

test("a deferred manifest refuses a rebound contract or invalid source at the same revision", async () => {
  const manifest = { source: "files", ...reading };
  for (const change of ["contract", "validity"]) {
    const candidate = structuredClone(data);
    candidate.version = change;
    if (change === "contract") candidate.sources.files.contract = "another-contract";
    else {
      delete candidate.sources.files.value;
      candidate.sources.files.error = "source is no longer valid";
    }
    acceptData(candidate, 1);
    await assert.rejects(
      loadDeferred(manifest, "text"),
      /source files revision r1 changed before loading deferred text/,
    );
  }
  acceptData(data, 1);
  assert.deepEqual(await loadDeferred(manifest, "text"), { contents: "evidence" });
});

test("an async projection retains its captured source provenance after acceptance advances", async () => {
  const { notifyDataSubscribers } = await import("/runtime/data.js");
  const { whenApplicationPresented } = await import("/runtime/semantic-state.js");
  const { LeafElement, nothing } = await import("/runtime/widget-api.js");
  adoptRegistry({
    "lf-source": {
      "x-data": { document: { contract: "text-document", source: "source" } },
    },
  });
  const initial = {
    version: "projection-original",
    sources: Object.fromEntries(
      ["document", "pinned"].map((source) => [
        source,
        { contract: "text-document", revision: "old-revision", value: 'route = "old"' },
      ]),
    ),
  };
  acceptData(initial, 1);
  // A widget drawing each delivery asynchronously, as an author's renderer may.
  customElements.define(
    "lf-source",
    class extends LeafElement {
      render() {
        this.snapshot = this.data("document");
        return nothing;
      }
      updated(changed) {
        super.updated(changed);
        this.drawing(paint(this)(this.snapshot));
      }
    },
  );
  document.body.innerHTML =
    '<main><lf-source id="live" source="document"></lf-source><lf-source id="pinned" source="pinned"></lf-source></main>';
  const { projectData } = createDataProjection({ invalidateDom() {} });
  const held = Promise.withResolvers();
  const firstProjection = Promise.withResolvers();
  let first = true;
  const paint = (node) => async (snapshot) => {
    // This is an author's async renderer, with its captured reading held explicitly.
    // Its production projection owner, rather than the latest accepted data, stamps
    // the origin that its rendered words actually came from.
    const mounting = node.id === "mounted-source" && first;
    if (mounting) {
      first = false;
      await held.promise;
    }
    const code = document.createElement("code");
    code.textContent = snapshot.value;
    node.replaceChildren(code);
    projectData(node, [{ key: "document", node: code }], { snapshot });
    if (mounting) firstProjection.resolve();
  };
  const live = document.querySelector("#live");
  const pinned = document.querySelector("#pinned");
  await new Promise((resolve) => setTimeout(resolve, 0));
  await whenApplicationPresented();
  const mounted = live.cloneNode(false);
  mounted.id = "mounted-source";
  live.after(mounted);
  await new Promise((resolve) => setTimeout(resolve, 0));
  const newer = structuredClone(initial);
  newer.version = "projection-newer";
  newer.sources.document.revision = "newer-revision";
  newer.sources.document.value = 'route = "new"';
  acceptData(newer, 1);
  held.resolve();
  await firstProjection.promise;
  const read = (node) => {
    const code = node.querySelector("code");
    return {
      text: code.textContent,
      source: code.dataset.lfSource,
      revision: code.dataset.lfSourceRevision,
    };
  };
  const beforeNotification = read(mounted);
  await notifyDataSubscribers();
  const old = { text: 'route = "old"', source: "document", revision: "old-revision" };
  const next = {
    text: 'route = "new"',
    source: "document",
    revision: "newer-revision",
  };
  assert.deepEqual(
    {
      beforeNotification,
      mounted: read(mounted),
      live: read(live),
      pinned: read(pinned),
    },
    {
      beforeNotification: old,
      mounted: next,
      live: next,
      pinned: { ...old, source: "pinned" },
    },
  );
  document.body.replaceChildren();
});
