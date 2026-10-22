import assert from "node:assert/strict";
import test from "node:test";
import process from "node:process";
import { execFileSync } from "node:child_process";
import { initialOutputs } from "../../build/initial.mjs";
import * as live from "/vendor/solid.js";
import { build } from "../../build/esbuild.mjs";
import { bindToInitialSolid } from "../../build/solid.mjs";

test("a later producer uses module Solid and preserves its drawing", async () => {
  const early = document.documentElement.lfInitial.solid;
  assert.deepEqual(Object.keys(live).sort(), Object.keys(early).sort());
  for (const name of Object.keys(live)) assert.equal(live[name], early[name], name);

  // Both supported import spellings bind to the initialized instance. The initial
  // producer hands its live closure to the widget, preserving template identity too.
  const built = await build({
    stdin: {
      contents: `
        import { html, createSignal, flush } from "/vendor/solid.js";
        import { render } from "/vendor/solid.js";
        document.documentElement.lfInitial.register("lf-solid-probe", (host) => {
          const [label, setLabel] = createSignal("Initial");
          render(() => html\`<button>\${label}</button>\`, host);
          const draw = next => flush(() => setLabel(next));
          return { draw };
        });
      `,
    },
    plugins: [await bindToInitialSolid()],
    bundle: true,
    format: "iife",
    write: false,
  });
  new Function(built.outputFiles[0].text)();
  const host = document.createElement("lf-solid-probe");
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

test("classic Solid and the mapped module facade are the same instance", () => {
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
        if (resolved.url.endsWith("/assets/vendor/solid.js")) return next("/vendor/solid-shared.js", context);
        return resolved;
      }});
      assert.equal(document.documentElement.lfInitial.solid, undefined);
      new Function(readFileSync("skills/leaf/assets/vendor/solid-initial.js", "utf8"))();
      const early = document.documentElement.lfInitial.solid;
      const live = await import("/vendor/solid-shared.js");
          assert.deepEqual(Object.keys(live).sort(), Object.keys(early).sort());
      for (const name of Object.keys(live)) assert.equal(live[name], early[name], name);
    `,
    ],
    { stdio: "pipe" },
  );
});

test("the initial dependency graph follows producer imports", async () => {
  const outputs = await initialOutputs();
  const dependencies = JSON.parse(
    outputs.get("skills/leaf/assets/vendor/initial-dependencies.json"),
  );
  assert.deepEqual(dependencies, {
    "/vendor/lf-toc-initial.js": ["/vendor/solid-initial.js"],
    "/vendor/lf-activity-initial.js": ["/vendor/solid-initial.js"],
  });
});
