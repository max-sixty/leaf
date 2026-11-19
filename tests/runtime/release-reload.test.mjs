/* A leaf.page document reloads on the first answer from another release
   (`admitResponse`, layer-client.js), whatever layer that answer names: only the edge
   names a release, so the edge has moved on and has a newer document to give. */
import assert from "node:assert/strict";
import test from "node:test";

const canonical = document.createElement("link");
canonical.rel = "canonical";
canonical.dataset.lfRuntime = "";
canonical.href = "https://leaf.test/examples/triage-board/";
document.head.append(canonical);
const script = document.createElement("script");
Object.assign(script.dataset, {
  lfRuntime: "",
  lfServer: "",
  lfLayer: "layer-1",
  lfRelease: "release-1",
  lfProbe: "/_leaf-release/release-1/registry.json",
});
document.head.append(script);
// A website page shares its session across tabs on a channel, which would otherwise
// hold this process open after the test.
window.BroadcastChannel = class extends window.BroadcastChannel {
  /** @param {string} name */
  constructor(name) {
    super(name);
    this.unref();
  }
};
// The previous release's assets are gone once the edge has moved on.
globalThis.fetch = async () => new Response("gone", { status: 404 });
const { admitResponse } = await import("/runtime/layer-client.js");

test("an answer from a new release with a new layer reloads the page", (t) => {
  const reload = t.mock.method(location, "reload", () => {});
  const answer = new Response("{}", {
    headers: { "Leaf-Release": "release-2", "Leaf-Layer": "layer-2" },
  });
  assert.equal(admitResponse(answer), false);
  assert.equal(reload.mock.callCount(), 1);
});
