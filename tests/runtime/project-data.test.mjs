import assert from "node:assert/strict";
import test from "node:test";

const { acceptData, notifyDataSubscribers } = await import("/runtime/data.js");
const { adoptRegistry } = await import("/runtime/registry.js");
const { createDataProjection } = await import("/runtime/projection/data.js");
const { LeafElement } = await import("/runtime/widget-api.js");
const { nothing } = await import("/vendor/lit.js");
createDataProjection({ invalidateDom() {} });

test("a widget's marks become its datums, and a nested widget keeps its own", () => {
  adoptRegistry({
    "lf-marked": { "x-data": { rows: { contract: "rows", source: "source" } } },
    "lf-marked-inner": { "x-data": { rows: { contract: "rows", source: "source" } } },
  });
  const { projectMarked } = createDataProjection({ invalidateDom() {} });
  document.body.innerHTML = `<main><lf-marked id="outer" source="rows">
      <p data-lf-datum="api" data-lf-identity="api" data-lf-datum-label="API"
        data-lf-origin-path='["rows",0]'>Ready</p>
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
    lfOriginPath: '["rows",0]',
    lfGen: "1",
    lfProjection: "outer",
    lfSource: "rows",
    lfSourceRevision: "r1",
    lfOrigin: '{"input":"rows","path":["rows",0]}',
    description: "API",
  });
  // The inner widget's mark is its own: the outer stamp leaves it unprojected.
  assert.equal(inner.dataset.lfProjection, undefined);

  // A new label replaces the one Leaf mirrored, and words no bound value supplied
  // carry no source or origin.
  row.dataset.lfDatumLabel = "API service";
  projectMarked(outer, null);
  assert.equal(row.getAttribute("aria-description"), "API service");
  assert.deepEqual(
    [row.dataset.lfProjection, row.dataset.lfSourceRevision, row.dataset.lfOrigin],
    ["outer", undefined, undefined],
  );
  // A dropped mark retires the datum, leaving the widget's other marks to it.
  delete row.dataset.lfDatum;
  projectMarked(outer, snapshot);
  assert.deepEqual(stamp(row), {
    lfIdentity: "api",
    lfDatumLabel: "API service",
    lfOriginPath: '["rows",0]',
    description: null,
  });

  // A mark that couldn't anchor a comment to one datum is refused.
  row.dataset.lfDatum = "";
  assert.throws(() => projectMarked(outer, snapshot), /keys must be non-empty strings/);
  row.dataset.lfDatum = "api";
  row.dataset.lfOriginPath = "rows.0";
  assert.throws(() => projectMarked(outer, snapshot), /must be a JSON array/);
  row.dataset.lfOriginPath = '["rows",0]';
  const twin = row.cloneNode(true);
  delete twin.dataset.lfIdentity;
  row.after(twin);
  assert.throws(() => projectMarked(outer, snapshot), /duplicate key api/);
  document.body.replaceChildren();
});

test("a draw reported after a newer value arrived keeps the revision it drew", async () => {
  adoptRegistry({
    "lf-valued": {
      "x-data": {
        text: { contract: "text-document", source: "source", property: "value" },
      },
    },
  });
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
  releases.get("Older")();
  while (read()[0] !== "Older") await new Promise((resolve) => setTimeout(resolve, 0));
  const afterOlder = read();
  releases.get("Newer")();
  await Promise.all([older, newer]);
  assert.deepEqual(
    { first, held, afterOlder, afterNewer: read() },
    {
      first: ["First", "first"],
      held: "first",
      afterOlder: ["Older", "older"],
      afterNewer: ["Newer", "newer"],
    },
  );
  document.body.replaceChildren();
});

test("a value the widget holds keeps its revision however many newer ones arrive", async () => {
  adoptRegistry({
    "lf-held": {
      "x-data": {
        rows: { contract: "rows", source: "source", property: "value" },
        notes: { contract: "rows", source: "notes", property: "notes" },
      },
    },
    "lf-held-text": {
      "x-data": { text: { contract: "rows", source: "source", property: "value" } },
    },
  });
  // A widget that keeps drawing the first rows it was handed, as a held reading does,
  // and reports what `report` says it drew.
  let report = (widget) => ({ value: widget.held });
  class Held extends LeafElement {
    render() {
      this.held ??= this.value;
      return nothing;
    }
    updated(changed) {
      super.updated(changed);
      const p =
        this.querySelector("p") ?? this.appendChild(document.createElement("p"));
      if (p.dataset.lfDatum !== "row") p.dataset.lfDatum = "row";
      this.dispatchEvent(new CustomEvent("drawn", { detail: report(this) }));
    }
  }
  customElements.define("lf-held", class extends Held {});
  customElements.define("lf-held-text", class extends Held {});
  // A row object for `lf-held`, and its revision as a string for `lf-held-text`.
  const reading = (revision) => ({
    version: revision,
    sources: {
      rows: { contract: "rows", revision, value: { revision } },
      text: { contract: "rows", revision, value: revision },
    },
  });
  acceptData(reading("r0"), 1);
  document.body.innerHTML =
    '<main><lf-held id="held" source="rows"></lf-held>' +
    '<lf-held-text id="held-text" source="text"></lf-held-text></main>';
  const widget = document.querySelector("#held");
  const text = document.querySelector("#held-text");
  await notifyDataSubscribers();
  for (let n = 1; n <= 12; n += 1) {
    acceptData(reading(`r${n}`), 1);
    await notifyDataSubscribers();
  }
  const row = widget.querySelector("p");
  assert.deepEqual(
    [widget.value.revision, row.dataset.lfSourceRevision],
    ["r12", "r0"],
  );
  assert.deepEqual(
    [text.value, text.querySelector("p").dataset.lfSourceRevision],
    ["r12", "r0"],
  );
  for (const held of [widget, text])
    assert.equal(held.querySelector(".lf-error"), null);

  // The unbound input's words carry no source; Leaf leaves its property to the widget.
  report = () => ({ notes: "authored" });
  widget.requestUpdate();
  await widget.updateComplete;
  assert.deepEqual(
    [widget.notes, row.dataset.lfProjection, row.dataset.lfSource],
    [undefined, "held", undefined],
  );

  // A seat carries one source, so a report naming two properties is refused, and so is
  // a value Leaf never set.
  for (const detail of [{ value: widget.held, notes: "authored" }, { value: {} }]) {
    report = () => detail;
    widget.requestUpdate();
    await widget.updateComplete;
    assert.match(widget.querySelector(".lf-error").textContent, /<lf-held/);
  }
  document.body.replaceChildren();
});
