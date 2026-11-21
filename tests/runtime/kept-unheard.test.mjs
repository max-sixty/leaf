import "/runtime/stage-integration.js";
/* Some of what a reading of the page reads is not what the page's reading hears: a
   datum's source and identity, or a role that makes a picture's holder a press. A
   change to one reaches a reading kept from it (kept.js) through its announcement,
   the document presented (`presentDocument`) or a widget's layout changing
   (`layoutChanged`), which its reader follows. */
import assert from "node:assert/strict";
import test from "node:test";

import { resolveAnchor, unclaimedVisualGesture } from "/runtime/anchor-resolution.js";
import { kept } from "/runtime/kept.js";
import { registry } from "/runtime/registry.js";
import { presentDocument } from "/runtime/semantic-state.js";
import { layoutChanged } from "/runtime/widget-upgrade.js";

test("a kept datum's place follows its source's revision once the document is presented", async () => {
  Object.assign(registry, { $layer: { generation: "kept-unheard-datum" } });
  document.body.innerHTML =
    '<main><div id="w" data-lf-source="feed"><div id="row" data-lf-projection="w" ' +
    'data-lf-datum="row" data-lf-source="feed" data-lf-identity="i1" ' +
    'data-lf-source-revision="r1">Row words</div></div></main>';
  const anchor = {
    section: "w",
    datum: "row",
    identity: "i1",
    source: "feed",
    source_revision: "r1",
  };
  const where = (/** @type {ReturnType<typeof resolveAnchor>} */ found) => [
    found?.kind,
    found?.status,
  ];
  const placed = kept(() => where(resolveAnchor(anchor)));
  assert.deepEqual(placed(), where(resolveAnchor(anchor)));
  for (const at of document.querySelectorAll("[data-lf-source-revision]"))
    at.setAttribute("data-lf-source-revision", "r2");
  document.querySelector("#row")?.setAttribute("data-lf-identity", "i2");
  await presentDocument();
  assert.deepEqual(placed(), where(resolveAnchor(anchor)));
  document.body.replaceChildren();
});

test("whether a picture's holder is a press follows a widget's layout changing", () => {
  document.body.innerHTML = '<main><div id="holder"><img id="pic" alt=""></div></main>';
  const picture = /** @type {Element} */ (document.querySelector("#pic"));
  const holder = /** @type {Element} */ (document.querySelector("#holder"));
  const unclaimed = kept(() => unclaimedVisualGesture(picture));
  assert.equal(unclaimed(), true);
  holder.setAttribute("role", "button");
  layoutChanged(holder);
  assert.equal(unclaimed(), unclaimedVisualGesture(picture));
  assert.equal(unclaimed(), false);
  document.body.replaceChildren();
});
