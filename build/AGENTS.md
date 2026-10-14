# Committed bundles

This directory builds the browser bundles Leaf commits: everything under
`skills/leaf/assets/vendor/` and each package's `vendor/`.
Installation, page init, and export consume that committed output and never run a
compiler, so nothing here runs on a host.

`runtime-bundle.mjs` compiles the kernel for the website, suite, and developer
previews. `leaf_dev.distribution` shares one compiled payload per relevant byte
revision; producer metadata gets a new installation snapshot without recompiling.
The named runtime entries include core and optional overlay diagnostics, so core
checks never load the physical renderer. Generated kernel chunks never enter Git.
Consumer installs serve the source modules; package authors use native JavaScript
without a build.

`browser/build.mjs` is the one builder: `pnpm run build:browser` writes every
output below, and `pnpm run check:browser`, part of `pnpm run check`, compares a
fresh build with the committed bytes without writing. Both first type-check the
framework and the browser's JavaScript (`browser/tsconfig.json` and
`browser/tsconfig.runtime.json`; the `typecheck` header in `browser/build.mjs`).

- `browser/` is the TypeScript browser framework, its Node tests, and `build.mjs`,
  which compiles each of its modules to one JavaScript module, line for line, and
  vendors Lit and Signals for it. `browser/shipped.mjs` refuses a module an
  export cannot load and writes each bundle's license notices; every build here passes its
  output through it. Branches that change the framework therefore conflict in its
  output only where their TypeScript conflicts, and `check:browser` confirms a merge
  equals a rebuild. `runtime-bundle.mjs` compiles the framework into the kernel for
  delivery.
- `initial.mjs` builds each package's synchronous initial drawing from its
  `initial.js` into the one bundle its registry declares with `x-initial`.
- `styles.mjs` resolves native CSS imports in component source entrypoints under
  `skills/leaf/assets/styles/` and bundled packages' `styles/` into the committed
  complete sheets. Consumers load no imports and run no compiler.
- `registry.mjs` generates the runtime modules that carry a registry fact to the
  browser, one row per module.
- `vendor.mjs` builds every third-party bundle outside the framework, bundling what
  each consumer needs or adapting an upstream browser module, one row of its
  `bundles` table per bundle. A directory under `build/` named after a row holds
  that row's inputs. `lit.mjs` owns how `vendor/lit.js` names Lit's exports and how
  a bundle binds its Lit imports to that copy.
  `floating-ui-zoom.patch` backports upstream #3492 to the locked 1.8.0 ESM;
  `floating-ui-element-zoom.patch` locally completes that conversion for a floating
  element zoomed relative to an Element offset parent, including border origins
  and overflow lengths.

After `pnpm install --frozen-lockfile`, the build reproduces the tracked bytes, so a
diff after a rebuild means the lock, a build script, or the registry input an output
reads changed.
Rebuild after any of those changes:

```sh
pnpm install --frozen-lockfile
pnpm run build:browser      # pnpm run check:browser compares without writing
```

Rebuild after `pnpm install` moves a pin or the lock, or after changing registry
input a bundle reads. `package.json` pins each package an entry imports, and the lock
pins the rest of each closure.
`lit-html` is held at 3.3.0, below what `lit` would take: from 3.3.1, `repeat` leaves
a comment behind for each item it removes (lit/lit#5298), so a list the chrome redraws
grows for as long as the page is open. `browser/build.mjs` backports lit/lit#5218
to that pin so optional `ref(undefined)` survives disconnection and reconnection.
The build also routes lit-html's keyed and child-part insertions through
`runtime/dom-move.js`, which keeps the user's place across a move and native state
where the browser supports it. It adapts the published modules in memory and fails
if a locked seam changes.
Lift it to a release
that carries lit/lit#5299; the closed-surface journey of
`test_page_fixture_renders` fails while the leak stands.
