import assert from "node:assert/strict";
import test from "node:test";

import { createDataProjection } from "/runtime/projection/data.js";

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
