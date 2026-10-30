/* Reading a package's own document does not depend on the private event log. */
import assert from "node:assert/strict";
import test from "node:test";
import { applicationState } from "../../browser/runtime/semantic-state.js";
import { dispatchKey } from "../../browser/runtime/keyboard/dispatch.js";
import { adoptRegistry } from "../../browser/runtime/registry.js";
import "../../packages/default/widgets/lf-tabs.js";

adoptRegistry({ "lf-tabs": { "x-views": { members: "lf-tab" } } });

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

test("generated package views resolve declarations before opening or keeping a view", async () => {
  const { openingView, keepView, viewMembers } =
    await import("../../browser/runtime/storage.js");
  adoptRegistry({
    "lf-package-views": { "x-views": { members: ".view", parts: true } },
  });
  const holders = ["opening", "keeping"].map((id) => {
    const holder = document.createElement("lf-package-views");
    holder.id = `package-${id}`;
    // A package-generated holder can contain real views, beside generated apparatus.
    holder.setAttribute("data-lf-gen", "");
    holder.innerHTML = `
      <article id="${id}-first" class="view">First</article>
      <article id="${id}-second" class="view">Second</article>
      <article class="view" data-lf-gen>Apparatus</article>
      <p data-lf-view>Former member</p>
      <section><article class="view">Nested view</article></section>`;
    document.body.append(holder);
    return holder;
  });
  try {
    const [opening, keeping] = holders;
    const [first, second, apparatus, former] = opening.children;
    assert.equal(openingView(opening), first);
    assert.equal(openingView(opening, null), null);
    assert.deepEqual(viewMembers(opening), [first, second]);
    assert.equal(opening.getAttribute("data-lf-views"), "parts");
    assert.equal(apparatus.hasAttribute("data-lf-view"), false);
    assert.equal(former.hasAttribute("data-lf-view"), false);

    first.classList.remove("view");
    assert.equal(openingView(opening), second);
    assert.equal(first.hasAttribute("data-lf-view"), false);

    const [leaving, selected] = keeping.children;
    keepView(keeping, selected);
    assert.equal(leaving.getAttribute("hidden"), "until-found");
    assert.equal(selected.hasAttribute("hidden"), false);
    assert.equal(openingView(keeping), selected);
  } finally {
    for (const holder of holders) holder.remove();
  }
});
