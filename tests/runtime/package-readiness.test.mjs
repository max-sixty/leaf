/* Reading a package's own document does not depend on the private event log. */
import assert from "node:assert/strict";
import test from "node:test";
import { applicationState } from "../../browser/runtime/semantic-state.js";
import { dispatchKey } from "../../browser/runtime/keyboard/dispatch.js";
import "../../packages/default/widgets/lf-tabs.js";

for (const phase of ["waiting", "offline"])
  test(`package tabs remain keyboard-operable while saved state is ${phase}`, () => {
    applicationState.setPhase(phase);
    const owner = document.createElement("section");
    owner.innerHTML =
      '<lf-tabs id="reading-views"><lf-tab data-lf-view id="first" label="First">One</lf-tab><lf-tab data-lf-view id="second" label="Second">Two</lf-tab></lf-tabs>';
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
