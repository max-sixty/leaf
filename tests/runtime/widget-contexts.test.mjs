/* Publication identity survives node moves and governs declaration consumers. */
import assert from "node:assert/strict";
import test from "node:test";
import { setImmediate } from "node:timers";
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
  const { ownedAskControl } = await import("/runtime/asks/answer.js");
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
  assert.equal(ownedAskControl(owner, question.firstElementChild), true);
  bindVocabulary(question, older);
  assert.equal(ownedAskControl(owner, question.firstElementChild), false);
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

test("work inventories retain each publication's roles and state vocabulary", async () => {
  const { adoptRegistry } = await import("/runtime/registry.js");
  const { workRole, workElements, directWorkElements, workAncestor } =
    await import("/runtime/work.js");
  const goal = { role: "goal", state: "stage", done: ["finished"] };
  const old = {
    revision: 9701,
    declarations: {
      $work: {
        widgets: {
          "lf-era-scope": { role: "scope" },
          "lf-era-work": goal,
        },
      },
    },
  };
  const current = {
    revision: 9702,
    declarations: {
      $work: {
        widgets: {
          "lf-era-work": { role: "worker", state: "status", done: ["done"] },
          "lf-current-goal": { role: "goal", state: "status", done: ["done"] },
        },
      },
    },
  };
  adoptRegistry(current.declarations);
  const scope = document.createElement("lf-era-scope");
  scope.innerHTML =
    '<lf-era-work id="old"></lf-era-work><lf-era-work id="current"></lf-era-work>' +
    '<lf-current-goal id="current-goal"></lf-current-goal>';
  bindVocabulary(scope, old);
  const oldGoal = scope.querySelector("#old");
  const currentWorker = scope.querySelector("#current");
  const currentGoal = scope.querySelector("#current-goal");
  bindVocabulary(currentWorker, current);
  bindVocabulary(currentGoal, current);

  assert.equal(workRole(oldGoal, "goal"), goal);
  assert.equal(workRole(currentWorker, "goal"), null);
  assert.equal(workRole(currentWorker, "worker").state, "status");
  assert.equal(workAncestor(currentGoal, "scope"), scope);
  assert.deepEqual(workElements(scope, "goal"), [oldGoal, currentGoal]);
  assert.deepEqual(directWorkElements(scope, "goal"), [oldGoal, currentGoal]);
});

test("shared declaration readers retain the owner's publication after moving", async () => {
  const { adoptRegistry, layerFact } = await import("/runtime/registry.js");
  const old = { revision: 9801, declarations: { $tones: { primary: "old" } } };
  const current = { revision: 9802, declarations: { $tones: { primary: "current" } } };
  adoptRegistry(current.declarations);
  const olderDocument = document.implementation.createHTMLDocument("");
  olderDocument.body.innerHTML = "<main><lf-tone></lf-tone></main>";
  bindVocabulary(olderDocument, old);
  const widget = olderDocument.querySelector("lf-tone");
  const destination = document.createElement("main");
  bindVocabulary(destination, current);
  destination.append(widget);

  assert.deepEqual(layerFact(widget, "$tones"), { primary: "old" });
  assert.deepEqual(layerFact(olderDocument, "$tones"), { primary: "old" });
  assert.deepEqual(layerFact(destination, "$tones"), { primary: "current" });
  layerFact(widget, "$tones").primary = "changed";
  assert.deepEqual(layerFact(widget, "$tones"), { primary: "old" });
});

test("shared reaction chrome follows the viewed document instead of the serving kernel", async (t) => {
  const { adoptRegistry } = await import("/runtime/registry.js");
  const { applicationState } = await import("/runtime/semantic-state.js");
  const { tokenChoices } = await import("/runtime/thread/model.js");
  const { reactionTokens, createReactionController } =
    await import("/runtime/reactions.js");
  const { messageText } = await import("/runtime/thread/messages.js");
  const { fabBar, fabOptions } = await import("/runtime/composing/selection.js");
  const viewed = { approve: { glyph: "O", settles: true } };
  const kernel = { later: { glyph: "L" }, approve: { glyph: "N", settles: false } };
  adoptRegistry({ $reactions: { tokens: kernel } });
  const previous = applicationState.read().document;
  const controller = createReactionController({
    fabAnchorAt: () => null,
    syncResponseOptions: () => {},
  });
  document.body.append(fabBar);
  controller.buildReactBar({});
  controller.mount();
  t.after(() => window.happyDOM.cancelAsync());
  let retained = null;
  try {
    for (const [index, tokens] of [viewed, kernel].entries()) {
      applicationState.captureDocument({
        ...previous,
        revision: 9803 + index,
        registry: { $states: {}, $reactions: { tokens } },
      });
      await new Promise(setImmediate);
      const offered = tokenChoices(tokens, []).find(
        (choice) => choice.name === "approve",
      );
      assert.equal(messageText({ token: "approve" }), `${offered.glyph} approve`);
      assert.deepEqual(reactionTokens(), Object.entries(tokens));
      const chip = fabOptions.querySelector('[data-token="approve"]');
      assert.equal(
        chip.querySelector(".lf-response-action-glyph").textContent,
        offered.glyph,
      );
      assert.deepEqual(
        [...fabOptions.querySelectorAll(".lf-react")].map((chip) => chip.dataset.token),
        Object.keys(tokens),
      );
      if (retained) assert.equal(chip, retained);
      retained = chip;
    }
  } finally {
    applicationState.captureDocument(previous);
    fabBar.remove();
  }
});
