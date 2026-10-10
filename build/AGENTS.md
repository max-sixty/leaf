# Committed bundles

This directory builds the browser bundles Leaf commits: everything under
`skills/leaf/assets/vendor/` and each package's `vendor/`.
Installation, page init, and export consume that committed output and never run a
compiler, so nothing here runs on a host.

`runtime-bundle.mjs` compiles the kernel for both website delivery and prepared
installations. `leaf-dev distribution` writes installation output under `.tmp/`;
CI verifies it and publishes the `prepared` branch. Generated kernel chunks never
enter development branches. Installers follow that branch and copy ready files;
package authors continue to use native JavaScript without a build.

- `browser/` is the TypeScript browser framework, its Node tests, and `build.mjs`,
  which compiles each of its modules to one JavaScript module, line for line, and
  vendors Lit and Signals for it. `browser/shipped.mjs` refuses a module an
  export cannot load and writes each bundle's license notices; every build here passes its
  output through it. Branches that change the framework therefore conflict in its
  output only where their TypeScript conflicts, and `check:browser` confirms a merge
  equals a rebuild. `runtime-bundle.mjs` compiles the framework into the kernel for
  delivery.
- `initial.mjs` builds each package's synchronous initial drawing from its
  `initial.js` into the one bundle its registry declares with `x-initial`;
  `build:browser` and `check:browser` include these outputs.
- `styles.mjs` resolves native CSS imports in component source entrypoints under
  `skills/leaf/assets/styles/` and bundled packages' `styles/` into the committed
  complete sheets. `build:styles` writes them; `check:styles` verifies them through
  the existing browser and bundle gates. Consumers load no imports and run no compiler.
- `vendor.py` rebuilds every third-party bundle outside the framework, bundling what
  each consumer needs or adapting an upstream browser module. `pierre/` and
  `webawesome/` hold the inputs their builders use.
  `floating-ui-zoom.patch` backports upstream #3492 to the locked 1.8.0 ESM;
  its builder records the upstream commit and applies it to private package copies.

After `npm ci`, both builds reproduce the tracked bytes, so a diff after a rebuild
means the lock, a build script, or the registry input a bundle reads changed.
Rebuild after any of those changes:

```sh
npm ci
npm run build:browser      # npm run check:browser compares without writing
uv run build/vendor.py     # all bundles, or name the ones to rebuild
```

Rebuild after `npm install` moves a pin or the lock, or after changing registry
input a bundle reads. `package.json` pins every JavaScript version that ships.
`lit-html` is held at 3.3.0, below what `lit` would take: from 3.3.1, `repeat` leaves
a comment behind for each item it removes (lit/lit#5298), so a list the chrome redraws
grows for as long as the page is open. The releases it skips carry typings and a fix
to the `ref` directive, which neither Leaf nor Web Awesome uses. Lift it to a release
that carries lit/lit#5299; the closed-surface journey of
`test_a_still_page_comes_back_from_every_journey_as_it_was` fails while the leak stands.
