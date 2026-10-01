# Packages

`../references/packages.md` owns the package contract: layout, registry declarations,
theme rules, guidance, data contracts, requests, and what a widget module owes.
`../assets/AGENTS.md` holds the layer-wide rules a module keeps and names the
runtime module that owns each concern; each runtime module's header states its own
contract. `build/vendor.py` generates each package's `vendor/` (`build/AGENTS.md`).
