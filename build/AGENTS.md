# Committed bundles

This directory builds every browser file Leaf commits but doesn't write by hand: the
third-party bundles and stylesheets and the runtime's table of the bundles' grammars.
Installation, page init and export use the committed files and never run a compiler,
and package authors write native JavaScript with no build. It also holds the kernel
compiler (`runtime-bundle.mjs`), which only a prepared installation runs, so the
tree commits no kernel and a runtime edit needs no rebuild.

`browser/build.mjs` is the one builder, and its header lists every output and the
script that writes it. `pnpm run build:browser` type-checks and writes them all;
`pnpm run check:browser`, part of `pnpm run check`, compares a fresh build with the
committed bytes without writing.

After `pnpm install --frozen-lockfile`, a build reproduces the committed bytes, so a
diff after rebuilding means the lock, a build script or a registry input changed.

`package.json` pins each package an entry imports, and the lock pins the rest.
`litModule` in `browser/build.mjs` says why `lit-html` is held at 3.3.0 and when to
lift it.
