import assert from "node:assert/strict";
import test from "node:test";
import { render } from "/vendor/lit.js";
import { createPlayground } from "../../packages/playground/widgets/playground-view.js";

test("a playground collects its own controls and leaves quoted value slots alone", () => {
  const host = document.createElement("lf-playground");
  host.id = "quoted-controls-drawing";
  host.innerHTML = `
    <lf-playground-control name="tone" kind="text" value="quiet"><strong>Tone</strong></lf-playground-control>
    <lf-playground-preview><lf-sample data-lf-exhibit>
      <lf-playground-control name="tone" kind="text" value="quoted"><strong>Quoted tone</strong></lf-playground-control>
      <lf-playground-control name="quoted" kind="toggle" value="true"><strong>Quoted toggle</strong></lf-playground-control>
    </lf-sample></lf-playground-preview>
    <lf-playground-output><lf-playground-value for="tone"></lf-playground-value>
      <lf-sample data-lf-exhibit><lf-playground id="quoted-output-drawing">
        <lf-playground-control name="tone" kind="text" value="quoted"><strong>Quoted tone</strong></lf-playground-control>
        <lf-playground-control name="inner-tone" kind="text" value="independent"><strong>Inner tone</strong></lf-playground-control>
        <lf-playground-preview><p>Inner preview</p></lf-playground-preview>
        <lf-playground-output><lf-playground-value for="tone"></lf-playground-value>
          <lf-playground-value for="inner-tone"></lf-playground-value></lf-playground-output>
      </lf-playground></lf-sample>
    </lf-playground-output>`;
  const quote = host.querySelector("lf-playground-preview lf-sample");
  const quotedOutput = host.querySelector("lf-playground-output lf-sample");
  const nested = quotedOutput.querySelector("lf-playground");
  const nestedView = createPlayground(nested);
  render(nestedView.render(), nested, { host: nested });
  const view = createPlayground(host);
  render(view.render({ values: { ...view.defaults, tone: "bold" } }), host, { host });
  assert.deepEqual(
    view.controls.map((control) => control.getAttribute("name")),
    ["tone"],
  );
  assert.deepEqual(view.defaults, { tone: "quiet" });
  assert.equal(quote.querySelectorAll("input").length, 0);
  assert.equal(
    view.output.querySelector(':scope > lf-playground-value[for="tone"]').textContent,
    "bold",
  );
  assert.deepEqual(
    [...quotedOutput.querySelectorAll("lf-playground-value")].map(
      (slot) => slot.textContent,
    ),
    ["quoted", "independent"],
  );
});
