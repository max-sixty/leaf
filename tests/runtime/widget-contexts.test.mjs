/* Imported arrivals retain their publication when mounted or moved elsewhere. */
import assert from "node:assert/strict";
import test from "node:test";
import { bindVocabulary, vocabularyFor } from "/runtime/widget-contexts.js";

test("imported text and comments retain their publication independently of placement", () => {
  const publication = { revision: 2 };
  const destination = document.createElement("div");
  bindVocabulary(destination, { revision: 1 });
  for (const source of [
    document.createTextNode("New passage"),
    document.createComment("New author note"),
  ]) {
    const arriving = document.importNode(source, true);
    bindVocabulary(arriving, publication);
    destination.append(arriving);
    assert.equal(vocabularyFor(arriving), publication);
  }
});

test("publication binding follows element descendants across later reparenting", () => {
  const sourceDocument = document.implementation.createHTMLDocument("");
  sourceDocument.body.innerHTML = "<section><b>Passage</b></section>";
  const fragment = document.createDocumentFragment();
  const fragmentChild = document.createElement("section");
  fragmentChild.innerHTML = "<b>Passage</b>";
  fragment.append(fragmentChild);
  const element = document.createElement("section");
  element.innerHTML = "<b>Passage</b>";
  const destination = document.createElement("div");
  bindVocabulary(destination, { revision: 1 });
  const publication = { revision: 2 };
  for (const root of [sourceDocument, fragment, element]) {
    const passage = root.querySelector("b");
    bindVocabulary(root, publication);
    assert.equal(vocabularyFor(root), publication);
    destination.append(passage);
    assert.equal(vocabularyFor(passage), publication);
  }
});
