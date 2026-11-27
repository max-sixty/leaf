// https://github.com/sverweij/dependency-cruiser
//
// The runtime's import graph. eslint reads one module at a time, so it sees the edges
// a module declares but not where they lead. Every rule here reads a route through the
// whole graph; `eslint.config.mjs` keeps the rules a module's own source answers, such
// as which specifiers an owner may name, which layers a module may name
// (`architecture/import-layers`) and who may write the document root.
//
// The graph is the runtime directory, the physical annotation overlay included.
// Everything outside it is excluded, the boot entry and the vendored bundles among
// them: no route between owners runs through either. The boot entry imports the overlay
// only when the page asks for it, and `core-independent-of-overlay` keeps every other
// owner from reaching it. Site-absolute `/vendor/` and `/checks/` specifiers, which the
// browser resolves and Node does not, are excluded by name; every other unresolvable
// specifier is a missing module and an error. JSON, such as the kernel registry
// `state/kernel-facts.js` imports, is excluded too: data holds no route between owners.

import fs from "node:fs";

const assets = "browser/";
const runtime = `${assets}runtime/`;
const overlay = `${runtime}annotations/annotation-overlay/`;
const owners = `^${runtime}`;

const escaped = (name) => name.replaceAll(/[.*+?^${}()|[\]\\]/g, "\\$&");
const isModule = (name) => `^${runtime}${escaped(name)}$`;
const isOneOf = (names) => `^${runtime}(?:${names.map(escaped).join("|")})$`;

// Each root reaches these modules and nothing else. The pure record folds take values
// and return values; the keyboard dispatcher resolves a key against the register and
// the focused scope. If one of them reached a painter or an application service, every
// caller would acquire that owner's initialization graph. A module of the library of
// shared web code (`lib/`) is no owner, and lint keeps each clear of every owner
// (`eslint.config.mjs`), so a root may reach one without naming it here.
const library = `^${runtime}lib/`;
// A reader of the application state reaches the publisher and the record folds it
// composes.
const applicationState = [
  "state/semantic-state.js",
  "state/version-signal.js",
  "state/semantic-application.js",
  "base/snapshot.js",
  "base/presentation.js",
  "state/obligations/source.js",
  "state/pending/model.js",
  "state/projection/model.js",
  "state/thread/model.js",
  "state/thread/identity.js",
  "state/kept.js",
  "state/kernel-facts.js",
  "state/registry-contract.js",
  "base/anchor-coordinate.js",
];
const exactClosures = {
  "base/ui-marks.js": [],
  "dom/control-selectors.js": ["base/inputs.js", "base/document-inputs.js"],
  "base/contribution-model.js": [],
  "features/margin-model.js": [
    "base/contribution-model.js",
    "records/thread/workflow.js",
    "base/voice.js",
  ],
  "features/margin-map-model.js": [
    "features/margin-model.js",
    "base/contribution-model.js",
    "records/thread/workflow.js",
    "base/voice.js",
  ],
  "state/projection/model.js": ["state/kept.js"],
  "records/projection/state.js": applicationState,
  "state/thread/model.js": [
    "base/anchor-coordinate.js",
    "state/kept.js",
    "state/thread/identity.js",
  ],
  "records/thread/state.js": applicationState,
  "records/thread/workflow.js": ["base/voice.js"],
  "state/pending/model.js": ["state/thread/identity.js", "state/kernel-facts.js"],
  "records/pending/state.js": applicationState,
  "dom/keyboard/dispatch.js": [
    ...applicationState,
    "state/context.js",
    "dom/focus.js",
    "dom/dom-move.js",
    "dom/control-selectors.js",
    "base/inputs.js",
    "base/document-inputs.js",
    "dom/keyboard/bindings.js",
    "dom/keyboard/layer-stack.js",
    "dom/keyboard/register.js",
    "dom/keyboard/scopes.js",
    "dom/keyboard/text-entry.js",
    "base/pointer.js",
    "base/rendering.js",
    "base/frame-visibility.js",
    "dom/repaint.js",
    "dom/arrivals.js",
  ],
};

const applicationOwners = [
  "host/application.js",
  "host/delivery.js",
  "panel/page-keys/go-to-sequence.js",
  "panel/page-keys/controller.js",
  "records/pending/state.js",
  "records/undo.js",
  "host/state-application.js",
  "host/state-feed.js",
];

// The renderers. Each receives the semantic commands it uses; one that reaches an
// application owner, through however many helpers, owns state instead of drawing it.
// The geometry and paint group adds the thread's own presenter, which composes
// them and must stay above them. A renderer in a layer below every module it must
// not reach needs no entry, since the import layers already keep it from them.
const forbiddenClosures = Object.fromEntries([
  ...[
    "records/thread/folding.js",
    "records/thread/inline.js",
    "records/thread/landing.js",
    "records/thread/messages.js",
    "records/thread/placement.js",
    "records/thread/presentation.js",
    "records/thread/reaction-strips.js",
    "records/thread/replies.js",
    "records/thread/surfaces.js",
    "records/thread/thread-card.js",
    "records/projection/data.js",
    "records/projection/presentation.js",
  ].map((root) => [root, applicationOwners]),
  ...[
    "annotations/anchor-controls.js",
    "annotations/anchor-paint.js",
    "features/anchor-travel.js",
    "panel/page-layout.js",
    "annotations/annotation-overlay/composing/drawing-paint.js",
    "annotations/annotation-overlay/margin-layout.js",
    "panel/page-geometry.js",
  ].map((root) => [root, [...applicationOwners, "records/thread/presentation.js"]]),
]);

// A rule naming a module that no longer exists matches nothing and passes, so the
// declarations above are checked against the directory before they become rules.
for (const name of new Set(
  [exactClosures, forbiddenClosures].flatMap((closures) =>
    Object.entries(closures).flatMap(([root, names]) => [root, ...names]),
  ),
))
  if (!fs.existsSync(new URL(`../${runtime}${name}`, import.meta.url)))
    throw new Error(
      `.config/dependency-cruiser.mjs names a missing runtime module: ${name}`,
    );

export default {
  forbidden: [
    {
      name: "application-behind-widget-api",
      comment:
        "Only the public widget boundary may import the runtime application " +
        "composition root.",
      severity: "error",
      from: {
        path: owners,
        pathNot: isOneOf([
          "widget-api.js",
          "widget-services.js",
          "host/widget-controller.js",
        ]),
      },
      to: { path: isModule("host/application.js") },
    },
    {
      name: "one-application-publisher",
      comment:
        "Only state/semantic-state.js constructs the application publisher, so a page " +
        "holds one application state.",
      severity: "error",
      from: { path: owners, pathNot: isModule("state/semantic-state.js") },
      to: { path: isModule("state/semantic-application.js") },
    },
    {
      name: "page-keyboard-from-boot-only",
      comment:
        "panel/page-keys/page.js declares the page's own keys as it evaluates and exports " +
        "nothing; only leaf.js imports it, for that effect.",
      severity: "error",
      from: { path: owners, pathNot: isModule("panel/page-keys/page.js") },
      to: { path: isModule("panel/page-keys/page.js") },
    },
    {
      name: "core-independent-of-overlay",
      comment:
        "Core owners cannot load the physical annotation overlay; only leaf.js " +
        "imports it, for a page that presents annotations with it.",
      severity: "error",
      from: { path: owners, pathNot: `^${overlay}` },
      to: { reachable: true, path: `^${overlay}` },
    },
    {
      name: "not-to-unresolvable",
      comment: "A runtime module names a module that is not on disk.",
      severity: "error",
      from: {},
      to: { couldNotResolve: true },
    },
    ...Object.entries(exactClosures).map(([root, allowed]) => ({
      name: `closure-of-${root}`,
      comment: `${root} reaches only: ${allowed.join(", ") || "itself"}.`,
      severity: "error",
      from: { path: isModule(root) },
      to: { reachable: true, pathNot: [isOneOf([root, ...allowed]), library] },
    })),
    ...Object.entries(forbiddenClosures).map(([root, forbidden]) => ({
      name: `no-reach-from-${root}`,
      comment: `${root} must not reach an application owner.`,
      severity: "error",
      from: { path: isModule(root) },
      to: { reachable: true, path: isOneOf(forbidden) },
    })),
  ],
  options: {
    moduleSystems: ["es6"],
    // /checks probes are supplied by the Python server, outside the runtime graph.
    exclude: {
      path: [`^${assets}(?!runtime/)`, "^/vendor/", "^/checks/", "\\.json$"],
    },
    // Resolve as the browser does: a specifier names its file exactly. Without this,
    // `./repaint` finds `dom/repaint.js` and passes here while the browser 404s it.
    enhancedResolveOptions: { extensions: [] },
  },
};
