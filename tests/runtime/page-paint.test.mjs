/* The runtime's paint is written unheard by the observers that read layout, and every
   other change, one the page makes in reaction to the paint included, is heard. */
import assert from "node:assert/strict";
import test from "node:test";
import { paint, readsLayout } from "/runtime/page-paint.js";

const WATCH = {
  subtree: true,
  attributes: true,
  attributeOldValue: true,
  attributeFilter: ["class", "style"],
};

test("a paint drops its own change and hands back what the page did in reaction", () => {
  // A page's custom element moves a button, in another shadow tree, whenever its own
  // class changes, as the trace a margin entry draws on it would change it.
  const button = document.createElement("button");
  class Mover extends HTMLElement {
    static observedAttributes = ["class"];
    attributeChangedCallback() {
      button.style.top = this.classList.contains("lf-traced") ? "40px" : "0px";
    }
  }
  customElements.define("lf-test-mover", Mover);
  const mover = document.createElement("lf-test-mover");
  mover.className = "card";
  const host = document.createElement("div");
  const tree = host.attachShadow({ mode: "open" });
  tree.append(button);
  document.body.append(mover, host);

  /** @type {MutationRecord[]} */
  const heard = [];
  const observer = new MutationObserver((records) => heard.push(...records));
  observer.observe(document, WATCH);
  observer.observe(tree, WATCH);
  readsLayout(observer, (records) => heard.push(...records));
  // An authored change made before the paint is heard, not dropped with it.
  mover.style.width = "10px";

  paint({ attribute: "class", token: "lf-traced" }, () =>
    mover.classList.add("lf-traced"),
  );

  assert.deepEqual(
    heard.map(({ target, attributeName }) => [target, attributeName]),
    [
      [mover, "style"],
      [button, "style"],
    ],
  );
  assert.equal(button.style.top, "40px");
  assert.ok(mover.classList.contains("lf-traced"));
  assert.deepEqual(observer.takeRecords(), []);
  observer.disconnect();
});

test("a paint's anchor name is dropped, and an author's restyle in the same write is not", () => {
  const box = document.createElement("div");
  box.style.color = "red";
  document.body.append(box);
  /** @type {MutationRecord[]} */
  const heard = [];
  const observer = new MutationObserver(() => {});
  observer.observe(document, WATCH);
  readsLayout(observer, (records) => heard.push(...records));

  paint({ attribute: "style", property: "anchor-name" }, () => {
    box.style.setProperty("anchor-name", "--lf-a1");
    box.style.setProperty("top", "8px");
  });

  assert.deepEqual(
    heard.map(({ target, attributeName }) => [target, attributeName]),
    [[box, "style"]],
  );
  observer.disconnect();
});
