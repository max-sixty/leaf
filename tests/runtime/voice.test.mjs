import assert from "node:assert/strict";
import test from "node:test";
import { render } from "/runtime/framework.js";
import { agentSays, leafSays, voiceOf, voiced, wordsText } from "/runtime/voice.js";

// A seat draws each word in its speaker's face, and one that holds a single face, such
// as the field's native placeholder, takes the run's one voice or none.
test("words draw in their speakers' faces, and a run wears one voice only when all share it", () => {
  const run = [
    "Draw mode · ",
    agentSays("checking the roof"),
    leafSays(" · New on me"),
  ];
  const host = document.createElement("div");
  render(voiced(run), host);
  assert.deepEqual(
    [...host.childNodes]
      .filter((node) => node.nodeType !== Node.COMMENT_NODE)
      .map((node) => [node.textContent, node.dataset?.voice ?? null]),
    [
      ["Draw mode · ", null],
      ["checking the roof", "agent"],
      [" · New on me", "leaf"],
    ],
  );
  assert.equal(wordsText(run), "Draw mode · checking the roof · New on me");
  assert.equal(voiceOf(run), null);
  assert.equal(voiceOf([leafSays("Stopped"), leafSays(" 3m ago")]), "leaf");
  assert.equal(voiceOf(agentSays("On it")), "agent");
  // The interface's own words are said by no one, and empty words don't count.
  assert.equal(voiceOf("Reply"), null);
  assert.equal(voiceOf(["", leafSays("Delivered")]), "leaf");
});
