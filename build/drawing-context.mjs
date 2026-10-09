// Every source needs computed styles and the requested crop. Upstream skips both
// for resource-free SVG roots, returning the live SVG before any clone hook runs.
// Remove that shortcut so SVG uses the dependency's ordinary foreignObject path.
import { readFileSync, writeFileSync } from "node:fs";
import { build } from "esbuild";

const shortcut =
  "  if (isElementNode(context.node) && isSVGElementNode(context.node) && !svgHasExternalResources(context.node))\n    return context.node;\n";

const result = await build({
  stdin: {
    contents: 'export { domToCanvas } from "modern-screenshot";',
    resolveDir: process.cwd(),
    sourcefile: "drawing-context-entry.mjs",
  },
  bundle: true,
  format: "esm",
  minify: true,
  legalComments: "inline",
  outfile: process.argv[2],
  metafile: true,
  plugins: [
    {
      name: "computed-svg-context",
      setup(builder) {
        builder.onLoad(
          { filter: /modern-screenshot\/dist\/index\.mjs$/ },
          ({ path }) => {
            const source = readFileSync(path, "utf8");
            if (source.split(shortcut).length !== 2)
              throw new Error("modern-screenshot's SVG shortcut changed");
            return { contents: source.replace(shortcut, ""), loader: "js" };
          },
        );
      },
    },
  ],
});
writeFileSync("meta.json", JSON.stringify(result.metafile));
