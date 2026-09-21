/* The durable provenance a standing unit carries, derived from the same values that
   render its widget state.

   Each provenance channel gets one reading on a target: independent reader facets
   collapse to a single one, while reader, report, and restatement stay separate. An
   outline property could only show the last of these, and the projection handed to the
   margin has to preserve all three. */

import assert from "node:assert/strict";
import test from "node:test";

import { projectionOrigins } from "/runtime/projection/model.js";

const coordinate = (facet) => JSON.stringify(["t-parser", "t-parser", facet]);

const entry = (id, kind, facet, value = null, record = null) => ({
  unit: "t-parser",
  e: { id, kind },
  spec: { facet, record, unit: "widget" },
  value,
});

test("reader, reported and restated origins stand separately on one unit", () => {
  const projection = {
    classified: new Map([
      ["old-reader", { e: { id: "old-reader" }, restated: ["t-parser"] }],
    ]),
    desired: new Map([
      [coordinate("status"), entry("reader-status", "action", "status")],
      [coordinate("owner"), entry("reader-owner", "action", "owner")],
      [coordinate("progress"), entry("report-progress", "report", "progress")],
    ]),
  };

  // No entry declares a record, so none of them has an authored value to be compared
  // against and the snapshots are never read.
  assert.deepEqual(projectionOrigins(new Map(), projection), [
    { origin: "restated", unit: "t-parser" },
    { origin: "reader", unit: "t-parser" },
    { origin: "reported", unit: "t-parser" },
  ]);
});

test("a recorded facet standing at its authored value overrides nothing", () => {
  const record = { kind: "value", attr: "status", value: "status" };
  const authored = new Map([
    [
      "t-parser",
      {
        state: { status: { value: "idle" } },
        specs: new Map([["status", { facet: "status", unit: "widget", record }]]),
        positions: {},
      },
    ],
  ]);
  const desired = (value) =>
    new Map([
      [coordinate("status"), entry("reader-status", "action", "status", value, record)],
    ]);

  assert.deepEqual(
    projectionOrigins(authored, { classified: new Map(), desired: desired("idle") }),
    [],
  );
  assert.deepEqual(
    projectionOrigins(authored, { classified: new Map(), desired: desired("running") }),
    [{ origin: "reader", unit: "t-parser" }],
  );
});
