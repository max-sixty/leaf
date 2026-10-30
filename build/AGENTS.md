# Committed bundles

This directory builds every browser file Leaf commits but doesn't write by hand: the
third-party bundles and stylesheets, JavaScript from TypeScript runtime owners,
the runtime's table of the bundles' grammars and the kernel in `dist/kernel/`.
Installation, page init
and export use the committed files and never run a compiler, and package authors write
native JavaScript with no build.

`browser/build.mjs` is the one builder, and its header lists every output and the
script that writes it. `pnpm run build:browser` type-checks and writes them all;
`pnpm run check:browser`, part of `pnpm run check`, compares a fresh build with the
committed bytes without writing.

After `pnpm install --frozen-lockfile`, a build reproduces the committed bytes, so a
diff after rebuilding means the lock, a build script, a runtime module or a registry
input changed. A change to `browser/leaf.js`, to a `.js` module under its `runtime/`,
`vendor/` or `widgets/`, to a runtime `.ts` owner, or to the kernel registry
`runtime/kernel-registry.json`,
which the kernel compiles in, takes a rebuild in the same change. Resolve a
kernel file that conflicts in a merge by merging `main` and rebuilding, never by hand.

`package.json` pins each package an entry imports, and the lock pins the rest.
`litModule` in `browser/build.mjs` says why `lit-html` is held at 3.3.0 and when to
lift it.
