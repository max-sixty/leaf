/* Publication identity survives node moves and governs declaration consumers. */
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

test("an earlier publication cannot lend its shadow, question or member roles", async () => {
  const { rememberVocabulary } = await import("/runtime/widget-contexts.js");
  const { shadowRootsIn } = await import("/runtime/shadow.js");
  const { ownedQuestionControl } = await import("/runtime/questions/answer.js");
  const { worksInside } = await import("/runtime/widget-elements.js");
  const older = {
    revision: 9601,
    declarations: {
      "lf-mixed-shadow": { "x-shadow": true },
      "lf-mixed-question": { "x-awaits": {} },
      "lf-mixed-part": { "x-owners": ["lf-mixed-container"] },
      "lf-mixed-leaf": { "x-owners": ["lf-mixed-part"] },
    },
  };
  const current = {
    revision: 9602,
    declarations: {
      "lf-mixed-shadow": {},
      "lf-mixed-question": {},
      "lf-mixed-part": {},
      "lf-mixed-container": {},
      "lf-mixed-owner": { "x-awaits": {} },
    },
  };
  rememberVocabulary(older);
  rememberVocabulary(current);
  const root = document.createElement("main");
  root.innerHTML =
    "<lf-mixed-shadow></lf-mixed-shadow><lf-mixed-shadow></lf-mixed-shadow>" +
    "<lf-mixed-owner><lf-mixed-question><span>Words</span></lf-mixed-question></lf-mixed-owner>" +
    "<lf-mixed-container><lf-mixed-part><span>Study</span></lf-mixed-part></lf-mixed-container>";
  bindVocabulary(root, current);
  const shadows = [...root.querySelectorAll("lf-mixed-shadow")];
  for (const host of shadows) host.attachShadow({ mode: "open" });
  bindVocabulary(shadows[0], older);
  assert.deepEqual(shadowRootsIn(root), [shadows[0].shadowRoot]);
  const owner = root.querySelector("lf-mixed-owner");
  const question = owner.firstElementChild;
  assert.equal(ownedQuestionControl(owner, question.firstElementChild), true);
  bindVocabulary(question, older);
  assert.equal(ownedQuestionControl(owner, question.firstElementChild), false);
  const container = root.querySelector("lf-mixed-container");
  const part = container.firstElementChild;
  assert.equal(worksInside(part.firstElementChild, container), part);
  bindVocabulary(part, older);
  assert.equal(worksInside(part.firstElementChild, container), null);
  part.innerHTML = "<lf-mixed-leaf><span>Deep reading</span></lf-mixed-leaf>";
  bindVocabulary(part, older);
  assert.equal(worksInside(part.querySelector("span"), container), null);
  part.append(document.createElement("button"));
  assert.equal(worksInside(part.lastElementChild, container), part.lastElementChild);
});
