/* Optional editing extensions share the shipped CodeMirror core. Externalizing
 * their imports preserves one state/view identity across editors and composers. */
import { build } from "esbuild";
import { writeFile } from "node:fs/promises";

const { metafile } = await build({
  stdin: {
    contents:
      'export { diff, unifiedMergeView, getOriginalDoc, originalDocChangeEffect } from "@codemirror/merge";\nexport { autocompletion, closeBrackets, closeBracketsKeymap, completionKeymap } from "@codemirror/autocomplete";',
    resolveDir: process.cwd(),
    sourcefile: "entry.mjs",
  },
  outfile: process.argv[2],
  bundle: true,
  format: "esm",
  platform: "browser",
  target: "es2022",
  minify: true,
  legalComments: "inline",
  metafile: true,
  plugins: [
    {
      name: "shared-codemirror",
      setup(builder) {
        builder.onResolve({ filter: /^@codemirror\/(state|view|language)$/ }, () => ({
          path: "/vendor/codemirror.esm.js",
          external: true,
        }));
        builder.onResolve({ filter: /^@lezer\/highlight$/ }, () => ({
          path: "/vendor/codemirror.esm.js",
          external: true,
        }));
      },
    },
  ],
});
await writeFile("meta.json", JSON.stringify(metafile));
