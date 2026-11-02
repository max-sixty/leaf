// knip, run by pre-commit's `knip` hook: the modules, exports and types nothing reads.
//
// Knip follows imports from the entries, the modules something other than an import
// loads, and resolves a root-absolute specifier the way a served page answers it: the
// composed `/runtime/`, `/vendor/` and `/widgets/` directories (tests/served-paths.mjs)
// and the render gate's probes at `/checks/`. An entry's own exports count as read,
// since its loader reads them by name, so an unused one there goes unreported. A
// namespace import that its module both reads members of and passes whole counts as
// reading only those members (knip's guide, "Namespace Imports"), so hand the
// receiver what it calls.
//
// It replaced a check of Leaf's own that counted an export read wherever a Python,
// HTML or Markdown file named it as a word, which kept every facade re-export whose
// name the package references document alive.
import { relative } from "node:path";
import { ROOTS } from "./tests/served-paths.mjs";

// TypeScript's `paths` takes the first candidate that holds the name, so the root a
// served page prefers comes first.
const composed = (directory) =>
  ROOTS.toReversed().map((root) => `${relative(".", root)}/${directory}/*`);

export default {
  entry: [
    // Boot, the public package API, and what pages, samples and exports load by URL.
    "browser/leaf.js",
    "browser/runtime/{widget-api,portable-api,bootstrap,sample,offline-delivery}.js",
    // The suite's windows into a page, whose members Python names
    // (`__lfCheckApi()`, `__lfOverlayApi()`).
    "browser/runtime/{,annotation-overlay/}check-api.js",
    // A widget module, which its registry entry names by tag.
    "{browser,packages/*,tests/fixtures/packages/*}/widgets/lf-*.js",
    // The render gate's probes, which Python calls by name.
    "src/leaf/render-checks/*.js",
    // Scripts the suite injects into pages, and the pages' own.
    "tests/*.{js,mjs}",
    "tests/{page_scripts,fixtures}/**/*.js",
    "examples/**/*.{js,mjs}",
    // Programs Node, the Workers runtime and the harnesses run.
    "tests/runtime/*.test.mjs",
    "{build,dev,evals,.github/scripts}/**/*.{js,mjs,cjs}",
    "hooks/*.ts",
    "worker/{src/index,test/**/*}.ts",
    ".dependency-cruiser.mjs",
  ],
  project: ["**/*.{js,mjs,cjs,ts}", "!**/vendor/**", "!dist/**"],
  // Declarations generated per schema definition or bundle export, whichever a reader
  // selects.
  ignore: ["browser/types/{contract,lit,signals-core}.d.ts"],
  paths: {
    "/runtime/*": composed("runtime"),
    "/vendor/*": composed("vendor"),
    "/widgets/*": composed("widgets"),
    "/checks/*": ["src/leaf/render-checks/*"],
  },
  include: ["files", "exports", "types"],
};
