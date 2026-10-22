# Solid 2 and UI dependencies

Evaluation date: 2026-10-22. Implementation: [draft PR #3462](https://github.com/max-sixty/leaf/pull/3462).

Leaf's application views and reactive state now use Solid `2.0.0-rc.16`.
WebAwesome `3.14.0` remains responsible for copy feedback and screenshot
comparison. Its private Lit implementation is bundled with those controls;
Leaf no longer exposes Lit as its application rendering or package author API.

The selection criterion is maintained behavior and integration quality. Reducing
the dependency count is not a goal. A native HTML button, search field, select
or radio is appropriate where the browser already supplies the needed behavior.
A component library is appropriate when it supplies useful behavior Leaf would
otherwise have to maintain.

## Lit versus Solid for Leaf

| Concern                            | Lit                                                      | Solid 2                                                                                |
| ---------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| Existing custom-element lifecycle  | Fits directly; lowest migration cost                     | Leaf keeps the lifecycle and gives generated views retained Solid roots                |
| Reactive state                     | Separate signal integration and redraw bridge            | Native memos, effects and projections share one graph with view updates                |
| Authored HTML and retained editing | Leaf must preserve nodes and native state across redraws | Still a Leaf responsibility; keyed rendering alone does not preserve all browser state |
| Build-free package authors         | Tagged templates                                         | Tagged templates through the shared `/vendor/solid.js` API                             |
| Parser-time first paint            | Shared initial/live Lit rendering on main                | Shared initial/live Solid rendering; live modules adopt the same nodes and graph       |
| Maturity                           | Stable and already integrated                            | Release candidate, with pinned local upstream adaptations                              |

Solid offers a more coherent reactive architecture for this application. It is
not a small dependency swap: package examples, ownership and scheduling,
first-paint delivery, focus retention, and generated bundles all change.
Remaining risks are the prerelease runtime and the cost of maintaining its
adaptations. There is no established startup speedup from this migration.

The build documents and checks the upstream seams for retained DOM movement,
quiet form writes, detached-root event collection, template traversal,
custom-element upgrade before refs, and follow-up notification when a draw
publishes a dependency it has already read. See [build/AGENTS.md](../build/AGENTS.md)
and [build/solid.mjs](../build/solid.mjs). These are review and upgrade costs,
not reasons to replace mature controls with bespoke implementations.

## UI library evaluation

Versions and package source were inspected, rather than assuming a permissive
peer range implied compatibility with Solid 2's changed API.

| Library                                                                                                  | Evidence                                                                                                                                                                                                                              | Decision                                                                                                                                                           |
| -------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| [WebAwesome 3.14.0](https://www.npmjs.com/package/@awesome.me/webawesome/v/3.14.0)                       | Framework-independent custom elements. A Chromium probe with the shipped Solid runtime passed input binding, focus/selection retention and select upgrade. Leaf's restored copy and comparison behavior also passes browser journeys. | Keep copy feedback and screenshot comparison. Load comparison with its consumer; keep Lit private to the library.                                                  |
| [Kobalte 2.0.0-alpha.4](https://www.npmjs.com/package/@kobalte/core/v/2.0.0-alpha.4)                     | Exact peers match Solid and `@solidjs/web` `2.0.0-rc.16`. Its README explicitly says components have not been fully tested.                                                                                                           | Best native Solid candidate for a future component-specific trial. Package compatibility was inspected; a complete Kobalte browser integration was not tested.     |
| [Ark UI Solid 6.0.0-next.0](https://www.npmjs.com/package/@ark-ui/solid/v/6.0.0-next.0)                  | Published source and its Zag Solid adapter still use Solid 1 APIs, despite the open-ended peer range.                                                                                                                                 | Not a drop-in dependency for this migration.                                                                                                                       |
| [Corvu 0.7.2](https://www.npmjs.com/package/corvu/v/0.7.2)                                               | Peer range is Solid `^1.8`.                                                                                                                                                                                                           | Revisit after explicit Solid 2 support.                                                                                                                            |
| [Spectrum Web Components 1.12.5](https://www.npmjs.com/package/@spectrum-web-components/bundle/v/1.12.5) | Framework-independent custom elements, with an established component set and its own visual system.                                                                                                                                   | Technically viable; changing libraries would require a separate theme and behavior integration. No demonstrated advantage for Leaf's current two library controls. |

A Kobalte trial should start with a concrete missing or inadequate control, and
compare keyboard navigation, focus after refresh, assistive semantics, touch,
print, and Leaf theme integration. Its alpha status adds another prerelease
surface today. Replacing WebAwesome wholesale has no demonstrated benefit.
