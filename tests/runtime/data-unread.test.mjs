/* An element bound to a page data source draws nothing until the page has read its
   data, or settled offline without it. Its own file, since the page reads its data once per document: every other
   runtime test accepts data in the same process. */
import assert from "node:assert/strict";
import test from "node:test";
import { html, LeafElement } from "/runtime/widget-api.js";
import { adoptRegistry } from "/runtime/registry.js";
import { acceptData, notifyDataSubscribers } from "/runtime/data.js";
import { applicationState } from "/runtime/semantic-state.js";

const settled = async (element) => {
  await new Promise((resolve) => setTimeout(resolve, 0));
  await element.updateComplete;
};

test("a bound element draws its source only once the page has read it", async () => {
  adoptRegistry({
    "lf-listing": {
      "x-data": { rows: { source: "source", contract: "rows", property: "value" } },
    },
    "lf-unbound": {
      "x-data": { rows: { source: "source", contract: "rows", property: "value" } },
    },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  const draws = [];
  for (const tag of ["lf-listing", "lf-unbound"])
    customElements.define(
      tag,
      class extends LeafElement {
        constructor() {
          super();
          this.value = null;
        }
        render() {
          const revision = this.value?.[0].revision ?? null;
          draws.push([tag, revision]);
          return html`${revision ?? "no data"}`;
        }
      },
    );
  const bound = document.createElement("lf-listing");
  bound.id = "listing";
  bound.setAttribute("source", "deployments");
  // A declared source the element doesn't name has nothing to wait for.
  const unbound = document.createElement("lf-unbound");
  unbound.id = "unbound";
  document.body.append(bound, unbound);
  await settled(bound);
  await settled(unbound);
  // Before the state answer, an empty reading would say "no data" of a source no one
  // has read, and then move what it drew when the text came.
  assert.deepEqual(draws, [["lf-unbound", null]]);
  assert.equal(bound.textContent, "");

  // A first read that brought no state settles the page offline: no answer is coming,
  // so the source holds nothing, and the element says so.
  applicationState.setPhase("offline");
  await settled(bound);
  assert.equal(bound.textContent, "no data");

  acceptData(
    {
      version: "first",
      sources: {
        deployments: {
          contract: "rows",
          revision: "r1",
          value: [{ key: "api", revision: "r1" }],
        },
      },
    },
    1,
  );
  await notifyDataSubscribers();
  await settled(bound);
  assert.deepEqual(draws, [
    ["lf-unbound", null],
    ["lf-listing", null],
    ["lf-listing", "r1"],
  ]);
  assert.equal(bound.textContent, "r1");
  assert.equal(document.body.getAttribute("data-lf-data-version"), "first");
});
