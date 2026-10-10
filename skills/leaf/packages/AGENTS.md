# Packages

`../references/packages.md` owns the package contract: layout, registry declarations,
theme rules, instructions, data contracts, and requests.
`../references/module-authoring.md` owns behavior-module obligations and the public
browser API.
The layer-wide laws a module must keep, and the map naming which runtime module
owns each concern, are in `../assets/AGENTS.md`; each runtime module's header
states its own contract. `build/AGENTS.md`, “Committed bundles”, owns generated
vendor bundles and stylesheet entrypoints. Where a bundled package has `styles/`
sources, edit them rather than its generated ready sheets.
