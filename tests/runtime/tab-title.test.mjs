/* The tab's title carries On me's count in front of the authored title, follows it to
   zero, and leaves the authored title to every reader that asks for it (All pages). */
import assert from "node:assert/strict";
import test from "node:test";

const { authoredTitle, paintTabTitle } = await import("/runtime/tab-title.js");
const settled = () => new Promise((resolve) => setTimeout(resolve));

test("the count leads the title while above zero and follows it to zero", async () => {
  const authored = document.createElement("title");
  authored.textContent = "Finish the ship review";
  document.head.append(authored);

  paintTabTitle(2);
  assert.equal(document.title, "(2) Finish the ship review");
  paintTabTitle(1);
  assert.equal(document.title, "(1) Finish the ship review");
  paintTabTitle(0);
  assert.equal(document.title, "Finish the ship review");
  assert.equal(document.head.querySelectorAll("title").length, 1);

  // A revision changes the authored title while a count is showing.
  paintTabTitle(3);
  authored.textContent = "Ship review, revised";
  await settled();
  assert.equal(document.title, "(3) Ship review, revised");
  paintTabTitle(0);
  assert.equal(document.title, "Ship review, revised");
});

test("All pages reads the authored title whatever the tab shows", () => {
  paintTabTitle(2);
  assert.match(document.title, /^\(2\) /);
  assert.doesNotMatch(authoredTitle(), /^\(/);
  paintTabTitle(0);
});
