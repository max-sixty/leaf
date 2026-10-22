# Committed bundles

This directory builds the browser files Leaf commits: everything under
`skills/leaf/assets/vendor/`, each package's `vendor/`, the stylesheets built from
`skills/leaf/assets/styles/`, and the compiled kernel in `skills/leaf/kernel/`.
Installation, page init and export use the committed files and never run a compiler,
and package authors write native JavaScript with no build.

`browser/build.mjs` is the one builder, and its header lists every output and the
script that writes it. `pnpm run build:browser` type-checks and writes them all;
`pnpm run check:browser`, part of `pnpm run check`, compares a fresh build with the
committed bytes without writing.

```sh
pnpm install --frozen-lockfile
pnpm run build:browser
```

After `pnpm install --frozen-lockfile`, a build reproduces the committed bytes, so a
diff after rebuilding means the lock, a build script, a runtime module or a registry
input changed. A change to `skills/leaf/assets/leaf.js`, or to a `.js` module under its
`runtime/`, `vendor/` or `widgets/`, takes a rebuild in the same change. Resolve a
kernel file that conflicts in a merge by merging `main` and rebuilding, never by hand.

`package.json` pins each package an entry imports, and the lock pins the rest.
`litModule` in `browser/build.mjs` says why `lit-html` is held at 3.3.0 and when to
lift it.
