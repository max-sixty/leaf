/* Reading a package's own document does not depend on the private event log. */
import assert from "node:assert/strict";
import test from "node:test";
import { applicationState } from "../../browser/runtime/state/semantic-state.js";
import { dispatchKey } from "../../browser/runtime/dom/keyboard/dispatch.js";
import { openingMember, showMember } from "../../browser/runtime/lib/one-shown.js";
import "../../packages/default/widgets/lf-tabs.js";

for (const phase of ["waiting", "offline"])
  test(`package tabs remain keyboard-operable while saved state is ${phase}`, () => {
    applicationState.setPhase(phase);
    const owner = document.createElement("section");
    owner.innerHTML =
      '<lf-tabs id="reading-views"><lf-tab id="first" label="First">One</lf-tab><lf-tab id="second" label="Second">Two</lf-tab></lf-tabs>';
    document.body.append(owner);
    const tabs = [...owner.querySelectorAll('[role="tab"]')];
    try {
      assert.equal(tabs.length, 2);
      tabs[0].focus();
      const press = new window.KeyboardEvent("keydown", {
        key: "ArrowRight",
        cancelable: true,
      });
      assert.equal(dispatchKey(press), true);
      assert.equal(press.defaultPrevented, true);
      assert.equal(tabs[1].getAttribute("aria-selected"), "true");
    } finally {
      owner.remove();
      applicationState.setPhase("ready");
    }
  });

test("a widget's member shown stays the one it opens on in this tab", () => {
  const holder = document.createElement("section");
  holder.id = "package-views";
  holder.innerHTML = `
    <article id="first">First</article>
    <article id="second">Second</article>
    <article><p id="third-words">Third</p></article>`;
  document.body.append(holder);
  const members = [...holder.children];
  const [first, second, third] = members;
  try {
    assert.equal(openingMember(holder, members), null);
    showMember(holder, members, third, second);
    assert.equal(first.getAttribute("hidden"), "until-found");
    assert.equal(second.hasAttribute("hidden"), false);
    assert.equal(third.hasAttribute("hidden"), false);
    // A member without an id is kept by its first descendant's.
    assert.equal(openingMember(holder, members), third);
    showMember(holder, members, null);
    assert.equal(third.getAttribute("hidden"), "until-found");
    assert.equal(openingMember(holder, members), third);
  } finally {
    holder.remove();
    sessionStorage.clear();
  }
});
