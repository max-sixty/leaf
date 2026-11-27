import assert from "node:assert/strict";
import test from "node:test";
import { render } from "/vendor/lit.js";
import { createPlayground } from "../../packages/playground/widgets/playground-view.js";

test("a playground reads its own fields and leaves quoted and generated fields and their outputs alone", () => {
  const host = document.createElement("lf-playground");
  host.id = "quoted-fields-drawing";
  host.innerHTML = `
    <aside><input name="tone" value="quiet"></aside>
    <lf-sample data-lf-exhibit>
      <input name="tone" value="quoted"><input type="checkbox" name="quoted" checked>
    </lf-sample>
    <form><input name="case" value="small"></form>
    <div data-lf-gen="1"><input type="range" name="time" value="0"></div>
    <select name="speed" data-lf-gen="1"><option value="1">1</option></select>
    <lf-playground-output><output for="tone"></output>
      <lf-sample data-lf-exhibit><lf-playground id="quoted-output-drawing">
        <input name="tone" value="quoted"><input name="inner-tone" value="independent">
        <lf-playground-output><output for="tone"></output>
          <output for="inner-tone"></output></lf-playground-output>
      </lf-playground></lf-sample>
    </lf-playground-output>`;
  document.body.append(host);
  const quotedOutput = host.querySelector("lf-playground-output lf-sample");
  const nested = quotedOutput.querySelector("lf-playground");
  const nestedView = createPlayground(nested);
  render(nestedView.render(), nested, { host: nested });
  const view = createPlayground(host);
  render(view.render({ values: { ...view.defaults, tone: "bold" } }), host, { host });
  assert.deepEqual([...view.fields.keys()], ["tone"]);
  assert.deepEqual(view.defaults, { tone: "quiet" });
  assert.equal(host.querySelector("aside input").value, "bold");
  assert.equal(
    view.output.querySelector(':scope > output[for="tone"]').textContent,
    "bold",
  );
  assert.deepEqual(
    [...quotedOutput.querySelectorAll("output")].map((slot) => slot.textContent),
    ["quoted", "independent"],
  );
  host.remove();
});

test("a reading follows its field while a script's provider writes the instruction", () => {
  const host = document.createElement("lf-playground");
  host.id = "provided-instruction-reading";
  host.innerHTML = `
    <aside><input type="range" name="q" min="0" max="5" step="0.5" value="3">
      <output for="q">3</output></aside>
    <p>Preview</p>
    <lf-playground-output>Use q.</lf-playground-output>`;
  document.body.append(host);
  const view = createPlayground(host);
  render(view.render({ values: { q: 1.5 }, instruction: "Use q 1.5." }), host, {
    host,
  });
  assert.equal(host.querySelector('aside output[for="q"]').textContent, "1.5");
  assert.equal(view.output.textContent, "Use q 1.5.");
  host.remove();
});
