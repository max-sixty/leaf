import assert from "node:assert/strict";
import test from "node:test";
import process from "node:process";
import { execFileSync } from "node:child_process";
import { initialOutputs } from "../../build/initial.mjs";
import * as live from "/vendor/lit.js";
import { build } from "../../build/esbuild.mjs";
import { bindToInitialLit } from "../../build/lit.mjs";

test("a later producer uses module Lit and preserves its drawing", async () => {
  const early = document.documentElement.lfInitial.lit;
  assert.equal(globalThis.litHtmlVersions.length, 1);
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

test("classic Lit and the mapped module facade are the same instance", () => {
  execFileSync(
    process.execPath,
    [
      "--import",
      new URL("./dom.mjs", import.meta.url).pathname,
      "--input-type=module",
      "-e",
      `
      import assert from "node:assert/strict";
      import { readFileSync } from "node:fs";
      import { registerHooks } from "node:module";
      registerHooks({ resolve(specifier, context, next) {
        const resolved = next(specifier, context);
        if (resolved.url.endsWith("/browser/vendor/lit.js")) return next("/vendor/lit-shared.js", context);
        return resolved;
      }});
      assert.equal(document.documentElement.lfInitial.lit, undefined);
      new Function(readFileSync("browser/vendor/lit-initial.js", "utf8"))();
      const early = document.documentElement.lfInitial.lit;
      const live = await import("/vendor/lit-shared.js");
      assert.equal(globalThis.litHtmlVersions.length, 1);
      assert.deepEqual(Object.keys(live).sort(), Object.keys(early).sort());
      for (const name of Object.keys(live)) assert.equal(live[name], early[name], name);
    `,
    ],
    { stdio: "pipe" },
  );
});

test("removing repeated chrome rows does not leave accumulating markers", () => {
  const host = document.createElement("div");
  document.body.append(host);
  try {
    const draw = (items) =>
      live.render(
        live.html`${live.repeat(
          items,
          (item) => item,
          (item) => live.html`<span>${item}</span>`,
        )}`,
        host,
      );
    draw(["first", "second"]);
    draw([]);
    const emptySize = host.childNodes.length;
    for (let index = 0; index < 20; index += 1) {
      draw(["first", "second"]);
      draw([]);
    }
    assert.equal(host.childNodes.length, emptySize);
  } finally {
    host.remove();
  }
});

test("the initial dependency graph follows producer imports", async () => {
  const outputs = await initialOutputs();
  const dependencies = JSON.parse(
    outputs.get("browser/vendor/initial-dependencies.json"),
  );
  assert.deepEqual(dependencies, {
    "/vendor/lf-toc-initial.js": ["/vendor/lit-initial.js"],
    "/vendor/lf-activity-initial.js": ["/vendor/lit-initial.js"],
    "/vendor/lf-shot-initial.js": ["/vendor/lit-initial.js"],
    "/vendor/lf-motion-initial.js": ["/vendor/lit-initial.js"],
    "/vendor/lf-timeline-initial.js": ["/vendor/lit-initial.js"],
  });
});
