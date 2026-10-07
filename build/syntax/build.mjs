/** Build one shared engine and split registry grammars with static local imports. */
import fs from "node:fs";
import path from "node:path";
import { build } from "esbuild";

const names = JSON.parse(fs.readFileSync(process.argv[3], "utf8")).$languages.names;
const result = await build({
  entryPoints: {
    "syntax.esm": path.join(process.cwd(), "entry.mjs"),
    ...Object.fromEntries(
      names.map((name) => [`syntax/${name}`, `@shikijs/langs/${name}`]),
    ),
  },
  outdir: process.argv[2],
  chunkNames: "syntax/chunk-[hash]",
  bundle: true,
  splitting: true,
  format: "esm",
  platform: "browser",
  target: "chrome105",
  minify: true,
  legalComments: "inline",
  metafile: true,
});
fs.writeFileSync("meta.json", JSON.stringify(result.metafile));
