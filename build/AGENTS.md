# Committed bundles

This directory builds every browser bundle Leaf commits: everything under
`skills/leaf/assets/vendor/` and each package's `vendor/`. Install, page init, and
export read the committed output and never run a compiler.

- `browser/` is the TypeScript browser framework, its Node tests, and `build.mjs`,
  which compiles it and `lit.js`. `browser/generated/` holds the source maps and
  manifest.
- `vendor.py` rebuilds every other bundle, copying a file where upstream publishes
  one a browser can load and building the rest from `pierre/` and `webawesome/`.
- `browser/shipped.mjs` checks every build's output: it refuses a module an export
  cannot load and writes the bundle's license notices.

After `npm ci`, both builds reproduce the tracked bytes, so a diff after a rebuild
means the lock, a build script, or the registry input a bundle reads changed.
Rebuild after any of those changes:

```sh
npm ci
npm run build:browser      # npm run check:browser compares without writing
uv run build/vendor.py     # all bundles, or name the ones to rebuild
```

`package.json` pins every JavaScript version that ships. `lit-html` is held at
3.3.0, below what `lit` would take, because from 3.3.1 `repeat` leaves a comment
behind for each item it removes (lit/lit#5298), so a list the chrome redraws grows
for as long as the page is open. Lift the pin to a release that carries
lit/lit#5299; `test_a_closed_surface_leaves_the_page_as_it_found_it` fails while
the leak stands.
