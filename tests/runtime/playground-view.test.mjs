import assert from "node:assert/strict";
import test from "node:test";
import { render } from "/vendor/lit.js";
import { createPlayground } from "../../packages/playground/widgets/playground-view.js";

test("a playground reads its own fields and leaves quoted fields and their outputs alone", () => {
  const host = document.createElement("lf-playground");
  host.id = "quoted-fields-drawing";
  host.innerHTML = `
    <aside><input name="tone" value="quiet"></aside>
    <lf-sample data-lf-exhibit>
      <input name="tone" value="quoted"><input type="checkbox" name="quoted" checked>
    </lf-sample>
    <form><input name="case" value="small"></form>
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
