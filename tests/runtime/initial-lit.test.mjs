import assert from "node:assert/strict";
import test from "node:test";
import * as live from "/vendor/lit.js";
import { build } from "../../build/esbuild.mjs";
import { bindToInitialLit } from "../../build/lit.mjs";

test("classic producers and later modules use one Lit and preserve their drawing", async () => {
  const early = document.documentElement.lfInitial.lit;
  assert.deepEqual(Object.keys(live).sort(), Object.keys(early).sort());
  for (const name of Object.keys(live)) assert.equal(live[name], early[name], name);

  // Both supported import spellings bind to the initialized instance. The initial
  // producer hands its live closure to the widget, preserving template identity too.
  const built = await build({
    stdin: {
      contents: `
        import { html } from "lit";
        import { render } from "/vendor/lit.js";
        document.documentElement.lfInitial.register("lf-lit-probe", (host) => {
          const draw = (label) => render(html\`<button>\${label}</button>\`, host);
          draw("Initial");
          return { draw };
        });
      `,
    },
    plugins: [await bindToInitialLit()],
    bundle: true,
    format: "iife",
    write: false,
  });
  new Function(built.outputFiles[0].text)();
  const host = document.createElement("lf-lit-probe");
  document.body.append(host);
  try {
    const drawing = document.documentElement.lfInitial.paint(host);
    const button = host.querySelector("button");
    drawing.draw("Live");
    assert.equal(host.querySelector("button"), button);
    assert.equal(button.textContent, "Live");
  } finally {
    host.remove();
  }
});
