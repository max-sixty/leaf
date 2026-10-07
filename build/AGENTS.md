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
  which compiles it and `lit.js`. `browser/shipped.mjs` refuses a module an
  export cannot load and writes each bundle's license notices; every build here passes its
  output through it. `browser/generated/` holds the source maps and manifest.
- `initial.mjs` builds each package's synchronous initial drawing from its
  `runtime/initial.js` into the one bundle its registry declares with `x-initial`;
  `build:browser` and `check:browser` include these outputs.
- `vendor.py` rebuilds every third-party bundle outside the framework. Where upstream publishes a loadable file
  it copies it; `pierre/` and `webawesome/` are the inputs of the bundles it has
  to build.

After `npm ci`, both reproduce the tracked bytes, so a diff after a rebuild means the
lock, a build script, or the registry input changed:

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
