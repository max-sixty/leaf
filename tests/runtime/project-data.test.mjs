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

test("a widget's marks become its datums, and a nested widget keeps its own", () => {
  adoptRegistry({
    "lf-marked": { "x-data": { rows: { contract: "rows", source: "source" } } },
    "lf-marked-inner": { "x-data": { rows: { contract: "rows", source: "source" } } },
  });
  const { projectMarked } = createDataProjection({ invalidateDom() {} });
  document.body.innerHTML = `<main><lf-marked id="outer" source="rows">
      <p data-lf-datum="api" data-lf-identity="api" data-lf-datum-label="API">Ready</p>
      <lf-marked-inner id="inner" source="rows"><p data-lf-datum="api">Inner</p></lf-marked-inner>
    </lf-marked></main>`;
  const outer = document.querySelector("#outer");
  const [row, inner] = document.querySelectorAll("p");
  const snapshot = { source: "rows", revision: "r1", origin: { input: "rows" } };
  projectMarked(outer, snapshot);
  const stamp = (node) => ({
    ...node.dataset,
    description: node.getAttribute("aria-description"),
  });
  assert.deepEqual(stamp(row), {
    lfDatum: "api",
    lfIdentity: "api",
    lfDatumLabel: "API",
    lfGen: "1",
    lfProjection: "outer",
    lfSource: "rows",
    lfSourceRevision: "r1",
    lfOrigin: '{"input":"rows"}',
    description: "API",
  });
  // The inner widget's mark is its own: the outer stamp leaves it unprojected.
  assert.equal(inner.dataset.lfProjection, undefined);

  // A new label replaces the one Leaf mirrored, and a dropped mark retires the datum.
  row.dataset.lfDatumLabel = "API service";
  projectMarked(outer, { ...snapshot, revision: "r2" });
  assert.equal(row.getAttribute("aria-description"), "API service");
  assert.equal(row.dataset.lfSourceRevision, "r2");
  delete row.dataset.lfDatum;
  projectMarked(outer, { ...snapshot, revision: "r3" });
  assert.deepEqual(stamp(row), { description: null });

  // Marks are refused as `projectData` refuses its datums.
  row.dataset.lfDatum = "";
  assert.throws(() => projectMarked(outer, snapshot), /keys must be non-empty strings/);
  row.dataset.lfDatum = "api";
  const twin = row.cloneNode(true);
  delete twin.dataset.lfIdentity;
  row.after(twin);
  assert.throws(() => projectMarked(outer, snapshot), /duplicate key api/);
  document.body.replaceChildren();
});

test("a draw reported after a newer value arrived keeps the revision it drew", async () => {
  const { notifyDataSubscribers } = await import("/runtime/data.js");
  const { LeafElement, nothing } = await import("/runtime/widget-api.js");
  adoptRegistry({
    "lf-valued": {
      "x-data": {
        text: { contract: "text-document", source: "source", property: "value" },
      },
    },
  });
  createDataProjection({ invalidateDom() {} });
  const reading = (revision, value) => ({
    version: revision,
    sources: { note: { contract: "text-document", revision, value } },
  });
  acceptData(reading("first", "First"), 1);
  // A widget that reads `.value` and draws each value when the test releases it, so
  // an older draw can finish after a newer one.
  const releases = new Map();
  customElements.define(
    "lf-valued",
    class extends LeafElement {
      static properties = { value: { attribute: false } };
      render() {
        return nothing;
      }
      updated(changed) {
        super.updated(changed);
        const value = this.value;
        const release = Promise.withResolvers();
        releases.set(value, release.resolve);
        if (value === "First") release.resolve();
        this.shown = release.promise.then(() => {
          const p =
            this.querySelector("p") ?? this.appendChild(document.createElement("p"));
          p.textContent = value;
          p.dataset.lfDatum = "text";
          this.dispatchEvent(new CustomEvent("drawn", { detail: { value } }));
        });
      }
      async getUpdateComplete() {
        const result = await super.getUpdateComplete();
        await this.shown;
        return result;
      }
    },
  );
  document.body.innerHTML =
    '<main><lf-valued id="note" source="note"></lf-valued></main>';
  const widget = document.querySelector("#note");
  await notifyDataSubscribers();
  const read = () => {
    const p = widget.querySelector("p");
    return [p.textContent, p.dataset.lfSourceRevision];
  };
  const first = read();

  acceptData(reading("older", "Older"), 1);
  const older = notifyDataSubscribers();
  while (!releases.has("Older")) await new Promise((resolve) => setTimeout(resolve, 0));
  acceptData(reading("newer", "Newer"), 1);
  const newer = notifyDataSubscribers();
  while (!releases.has("Newer")) await new Promise((resolve) => setTimeout(resolve, 0));
  // The data version waits on the widget's `updateComplete`, which its drawing extends.
  const held = document.body.dataset.lfDataVersion;
  releases.get("Newer")();
  await newer;
  const afterNewer = read();
  releases.get("Older")();
  await older;
  assert.deepEqual(
    { first, held, afterNewer, afterOlder: read() },
    {
      first: ["First", "first"],
      held: "first",
      afterNewer: ["Newer", "newer"],
      afterOlder: ["Older", "older"],
    },
  );
  document.body.replaceChildren();
});
