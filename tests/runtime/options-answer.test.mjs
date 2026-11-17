/* What a choice's answer reads as in On Me (`lf-options.answerWords`), from the group's
   authored markup alone, as a thread message keeps it while no drawing shows it. */
import assert from "node:assert/strict";
import test from "node:test";

await import("../../packages/default/widgets/lf-options.js");

test("a choice names the picks its markup holds, and none it can't find", () => {
  const template = document.createElement("template");
  template.innerHTML =
    '<lf-options id="ship">' +
    '<lf-option id="ship-friday"><strong>Ship Friday</strong> before the freeze</lf-option>' +
    '<lf-option id="ship-wait"><strong>Wait a week</strong></lf-option>' +
    "</lf-options>";
  const group = template.content.firstElementChild;
  assert.ok(group);
  const { answerWords } = customElements.get("lf-options");
  assert.equal(
    answerWords(["ship-wait", "ship-friday"], group),
    "Ship Friday, Wait a week",
  );
  assert.equal(answerWords([], group), "No options selected");
  // An option the user added, which only a drawing of the group knows: no name rather
  // than "No options selected".
  assert.equal(answerWords(["ship-monday"], group), "");
  assert.equal(answerWords(["ship-friday", "ship-monday"], group), "");
});
