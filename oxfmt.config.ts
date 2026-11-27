// The formatter's settings, which oxfmt finds here, and the TypeScript build formats
// its output with (build/typescript.mjs).
export default {
  // Ruff's default width, so Python and everything else wrap at the same length.
  printWidth: 88,
  // package.json keeps its authored key order.
  sortPackageJson: false,
  ignorePatterns: [
    // TOML keeps its authors' layout: uv writes dependency lists one per line, and
    // Ruff's rule selections are grouped by line.
    "**/*.toml",
    // Bundled JavaScript keeps the compiler's layout and minification.
    "browser/vendor/",
    "packages/**/vendor/",
    // Generated sources keep the bytes their producer writes and checks
    // (`build/styles.mjs`, `build/browser/build.mjs`, `build/browser/contract-types.mjs`).
    "browser/styles/vendor/",
    "browser/types/contract.d.ts",
    "browser/types/lit.d.ts",
    // Compiler paths keep the browser build's generated JSON layout.
    "browser/types/tsconfig.paths.json",
    // The panel's served row keeps the bytes its generator draws (build/panel-row.mjs).
    "browser/runtime/panel-row.html",
    // Padding the glossary's table cells would take it past the harness's
    // 30,000-character single-read limit.
    ".claude/skills/developing-leaf/references/glossary.md",
    // Package locks, Tend workflows, recorded test output and the protocol baseline
    // keep their producers' bytes.
    "**/pnpm-lock.yaml",
    ".github/workflows/tend-*.yaml",
    "**/_regtest_outputs/",
    "build/browser/protocol-baseline.json",
    // Frozen, hash-checked source evidence must retain its original bytes.
    "evals/ui-review-detection/fixtures/public/",
  ],
};
