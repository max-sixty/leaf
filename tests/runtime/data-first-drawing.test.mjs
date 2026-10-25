/* A bound element can skip Lit's initial update while data is unread. Its first
   real drawing must still hold page readiness until asynchronous work finishes. */
import assert from "node:assert/strict";
import test from "node:test";
import { html, LeafElement } from "/runtime/widget-api.js";
import { adoptRegistry } from "/runtime/registry.js";
import { acceptData, notifyDataSubscribers } from "/runtime/data.js";
import { readApplicationPresentation } from "/runtime/semantic-state.js";

test("the first drawing after unread data holds presentation", async () => {
  adoptRegistry({
    "lf-first-drawing": {
      "x-data": { rows: { source: "source", contract: "rows", property: "value" } },
    },
    $data: { contracts: { rows: { records: { items: "", key: "key" } } } },
  });
  let finish;
  customElements.define("lf-first-drawing", class extends LeafElement {
    static properties = { value: { attribute: false } };
    render() {
      return html`${this.value?.[0].key}`;
    }
    updated() {
      this.work = new Promise((done) => { finish = done; });
    }
    async getUpdateComplete() {
      const result = await super.getUpdateComplete();
      await this.work;
      return result;
    }
  });
  const element = document.createElement("lf-first-drawing");
  element.id = "first-drawing";
  element.setAttribute("source", "jobs");
  document.body.append(element);
  try {
    await new Promise((done) => setTimeout(done, 0));
    await element.updateComplete;
    assert.equal(element.hasUpdated, false, "unread data skips the initial update");
    acceptData({ version: "first", sources: { jobs: {
      contract: "rows", revision: "r1", value: [{ key: "api" }],
    } } }, 1);
    const delivered = notifyDataSubscribers();
    await new Promise((done) => setTimeout(done, 0));
    assert.equal(element.textContent, "api");
    assert.ok(readApplicationPresentation().pending.some((region) =>
      region.startsWith("element:lf-first-drawing#")),
    "the first drawing still owes its asynchronous result");
    finish();
    await delivered;
    await element.updateComplete;
    assert.ok(!readApplicationPresentation().pending.some((region) =>
      region.startsWith("element:lf-first-drawing#")));
  } finally {
    finish?.();
    element.remove();
  }
});
