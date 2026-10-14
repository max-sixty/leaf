# Packages

`../references/packages.md` and the `package-*.md` files beside it own the package
contract: layout, registry declarations, theme rules, instructions, data contracts,
and requests. `../references/module-authoring.md` and the `module-*.md` files beside
it own behavior-module obligations and the public browser API.
The layer-wide laws a module must keep, and the map naming which runtime module
owns each concern, are in `../assets/AGENTS.md`; each runtime module's header
states its own contract. `build/AGENTS.md`, “Committed bundles”, owns generated
vendor bundles and stylesheet entrypoints. Where a bundled package has `styles/`
sources, edit them rather than its generated ready sheets.
