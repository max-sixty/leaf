# Committed bundles

This directory builds the browser bundles Leaf commits: everything under
`skills/leaf/assets/vendor/`, each package's `vendor/`, and `skills/leaf/mcp-app/`.
Installation, page init, and export consume that committed output and never run a
compiler, so nothing here runs on a host.

- `browser/` is the TypeScript browser framework, its Node tests, and `build.mjs`,
  which compiles it and `lit.js`. `browser/shipped.mjs` refuses a module the page
  CSP forbids and writes each bundle's license notices; every build here passes its
  output through it. `browser/generated/` holds the source maps and manifest.
- `vendor.py` rebuilds every other bundle. Where upstream publishes a loadable file
  it copies it; `pierre/`, `webawesome/`, and `mcp-app/` are the inputs of the
  bundles it has to build.

After `npm ci`, both reproduce the tracked bytes, so a diff after a rebuild means the
lock, a build script, or the registry input changed:

```sh
npm ci
npm run build:browser      # npm run check:browser compares without writing
uv run build/vendor.py     # all bundles, or name the ones to rebuild
```

Rebuild after `npm install` moves a pin or the lock, or after changing registry
input a bundle reads. `package.json` pins every JavaScript version that ships.
