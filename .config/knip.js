// knip, run by pre-commit's `knip` hook: the modules, exports and types nothing reads,
// and the static import cycles, which leave the modules in them no order to evaluate
// in: whichever runs first can read another's bindings before they exist.
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
import { typescriptModules } from "../build/typescript.mjs";
import { ROOTS } from "../tests/served-paths.mjs";

// TypeScript's `paths` takes the first candidate that holds the name, so the root a
// served page prefers comes first.
const composed = (directory) =>
  ROOTS.toReversed().map((root) => `${relative(".", root)}/${directory}/*`);

export default {
  entry: [
    // Boot, the public package API, and what pages, samples and exports load by URL.
    "browser/leaf.js",
    "browser/runtime/{widget-api,portable-api,bootstrap,host/sample,base/offline-delivery}.js",
    // The suite's windows into a page, whose members Python names
    // (`__lfCheckApi()`, `__lfOverlayApi()`).
    "browser/runtime/{,annotations/annotation-overlay/}check-api.js",
    // A widget module, which its registry entry names by tag.
    "{browser,packages/*,docs/*,tests/fixtures/packages/*}/widgets/lf-*.js",
    // The render gate's probes, which Python calls by name, and the script an export
    // draws its page with.
    "src/leaf/source/render-checks/*.js",
    "src/leaf/pages/static-export.js",
    // Scripts the suite injects into pages, and the pages' own.
    "tests/*.{js,mjs}",
    "tests/{page_scripts,fixtures}/**/*.js",
    "examples/**/*.{js,mjs}",
    // Programs Node, the Workers runtime and the harnesses run.
    "tests/runtime/*.test.mjs",
    "{build,dev,evals,.github/scripts}/**/*.{js,mjs,cjs}",
    "hooks/*.ts",
    "worker/{src/index,test/**/*}.ts",
    ".config/dependency-cruiser.mjs",
    // A TypeScript module, whose imports name the JavaScript compiled beside it
    // (build/typescript.mjs): knip follows those to read what each export serves, and
    // the module itself to read which types it uses.
    ...(await typescriptModules()),
  ],
  project: ["**/*.{js,mjs,cjs,ts}", "!**/vendor/**"],
  // Declarations generated per schema definition or bundle export, whichever a reader
  // selects.
  ignore: ["browser/types/{contract,lit,signals-core}.d.ts"],
  paths: {
    "/runtime/*": composed("runtime"),
    "/vendor/*": composed("vendor"),
    "/widgets/*": composed("widgets"),
    "/checks/*": ["src/leaf/source/render-checks/*"],
  },
  include: ["files", "exports", "types", "cycles"],
  // Knip grades a cycle a warning by default, which exits 0.
  rules: { cycles: "error" },
};
