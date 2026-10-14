# Committed bundles

This directory builds the browser files Leaf commits: everything under
`skills/leaf/assets/vendor/` and each package's `vendor/`. Installation, page init
and export use the committed files and never run a compiler, so nothing here runs on a
user's machine. Consumer installs serve the runtime's source modules, and package
authors write native JavaScript with no build.

`browser/build.mjs` is the one builder. `pnpm run build:browser` type-checks and writes
every output; `pnpm run check:browser`, part of `pnpm run check`, compares a fresh build
with the committed bytes without writing. Its header lists the outputs; each script
below owns its own:

- `browser/`: the TypeScript browser framework and its Node tests. `build.mjs`
  compiles each module to one JavaScript module, line for line, so branches conflict in
  the output only where their TypeScript conflicts. `browser/shipped.mjs` refuses a
  module an export can't load and writes each bundle's license notices.
- `runtime-bundle.mjs`: compiles the runtime into one kernel for the website, the suite
  and developer previews. Its chunks never enter Git.
- `initial.mjs`: builds each package's first-paint drawing from its `initial.js` into
  the bundle its registry names in `x-initial`.
- `styles.mjs`: resolves CSS imports in `skills/leaf/assets/styles/` and bundled
  packages' `styles/` into the committed complete sheets.
- `registry.mjs`: generates the runtime modules that carry a registry fact to the
  browser.
- `vendor.mjs`: builds every third-party bundle, one row of its `bundles` table each. A
  directory here named after a row holds that row's inputs, and a `.patch` file here is
  an upstream backport its header explains. `lit.mjs` owns how `vendor/lit.js` exports
  Lit and how bundles import it.

After `pnpm install --frozen-lockfile`, a build reproduces the committed bytes, so a
diff after rebuilding means the lock, a build script or a registry input changed.
Rebuild after any of those:

```sh
pnpm install --frozen-lockfile
pnpm run build:browser      # pnpm run check:browser compares without writing
```

`package.json` pins each package an entry imports, and the lock pins the rest.
`lit-html` is pinned at 3.3.0 because from 3.3.1 `repeat` leaves a comment behind for
each item it removes (lit/lit#5298), so a list the chrome redraws grows for as long as
the page is open. Lift the pin to a release that carries lit/lit#5299; the
closed-surface journey of `test_page_fixture_renders` fails while the leak remains.
`litModule` in `browser/build.mjs` says what the build changes in Lit's published
modules.
