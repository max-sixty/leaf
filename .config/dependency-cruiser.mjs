// https://github.com/sverweij/dependency-cruiser
//
// The runtime's import graph. eslint reads one module at a time, so it sees the edges
// a module declares but not where they lead. Every rule here reads a route through the
// whole graph; `eslint.config.mjs` keeps the rules a module's own source answers, such
// as which specifiers an owner may name and who may write the document root.
//
// The graph is the runtime directory, the physical annotation overlay included.
// Everything outside it is excluded, the boot entry and the vendored bundles among
// them: no route between owners runs through either. The boot entry imports the overlay
// only when the page asks for it, and `core-independent-of-overlay` keeps every other
// owner from reaching it. Site-absolute `/vendor/` and `/checks/` specifiers, which the
// browser resolves and Node does not, are excluded by name; every other unresolvable
// specifier is a missing module and an error. So is the framework's facade by its
// served path, `/runtime/records/framework.js`: like Lit beneath it, the framework is a
// dependency every owner may hold, in any layer, not one of the owners whose routes
// these rules read. Its own modules, under `records/framework/`, are checked as any
// owner is. JSON, such as the kernel registry `state/kernel-facts.js` imports, is
// excluded too: data holds no route between owners.

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
  "records/projection/model.js": ["state/kernel-facts.js", "state/kept.js"],
  "records/projection/state.js": ["state/semantic-state.js", "state/version-signal.js"],
  "records/thread/model.js": [
    "base/anchor-coordinate.js",
    "state/kept.js",
    "records/thread/identity.js",
    "records/thread/workflow.js",
    "base/voice.js",
  ],
  "records/thread/state.js": [
    "state/semantic-state.js",
    "state/version-signal.js",
    "records/thread/model.js",
    "base/anchor-coordinate.js",
    "state/kept.js",
    "records/thread/identity.js",
    "records/thread/workflow.js",
    "base/voice.js",
  ],
  "records/thread/workflow.js": ["base/voice.js"],
  "records/pending/model.js": ["records/thread/identity.js", "state/kernel-facts.js"],
  "records/pending/state.js": ["state/semantic-state.js", "state/version-signal.js"],
  "dom/keyboard/dispatch.js": [
    "state/context.js",
    "state/semantic-state.js",
    "state/version-signal.js",
    "dom/focus.js",
    "dom/dom-move.js",
    "dom/control-selectors.js",
    "base/inputs.js",
    "base/document-inputs.js",
    "base/ui-marks.js",
    "base/language-paths.js",
    "readings/scroll-containers.js",
    "dom/keyboard/bindings.js",
    "dom/keyboard/layer-stack.js",
    "dom/keyboard/register.js",
    "dom/keyboard/scopes.js",
    "dom/keyboard/text-entry.js",
    "base/pointer.js",
    "dom/user-intent.js",
    "state/registry.js",
    "state/registry-contract.js",
    "state/kernel-facts.js",
    "base/rendering.js",
    "base/frame-visibility.js",
    "dom/repaint.js",
    "dom/shadow.js",
    "dom/arrivals.js",
    "base/page-paint.js",
    "state/kept.js",
  ],
};

const applicationOwners = [
  "host/application.js",
  "host/delivery.js",
  "panel/page-keys/go-to-sequence.js",
  "panel/page-keys/controller.js",
  "records/pending/state.js",
  "annotations/undo.js",
  "host/state-application.js",
  "host/state-feed.js",
];

// The renderers. Each receives the semantic commands it uses; one that reaches an
// application owner, through however many helpers, owns state instead of drawing it.
// The geometry and paint group adds the thread's own presenter, which composes
// them and must stay above them.
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
    "readings/addressable-names.js",
    "readings/anchor-resolution.js",
    "annotations/anchor-controls.js",
    "annotations/anchor-paint.js",
    "features/anchor-travel.js",
    "panel/page-layout.js",
    "annotations/annotation-overlay/composing/drawing-paint.js",
    "annotations/annotation-overlay/margin-layout.js",
    "panel/page-geometry.js",
    "readings/target-paint.js",
  ].map((root) => [root, [...applicationOwners, "records/thread/presentation.js"]]),
]);

// The runtime's import layers, top first. A module imports only modules of its own
// layer and of the layers listed after it. The entry points form the top layer and stay
// at the runtime's top level, since pages, packages, the server and the render checks
// load them by served path. Each other layer is a directory of the runtime. The library
// of shared web code (`lib/`) keeps its served path and belongs to the bottom layer.
// A module anywhere else at the top level fails `layering-unplaced`: move it into a
// layer no higher than any module that imports it and no lower than any module it
// imports.
//
// When a `layering` rule fails, make the import point down, by passing the value or
// callback in or by moving what it needs to a layer below both. Where the module itself
// stands in the wrong layer, move the module instead. `dependency-cruiser-known.json`
// holds the imports that still point up, which the hook passes over. It only shrinks:
// delete an entry once its import goes, and fix a new upward import rather than adding
// one.
const layers = [
  {
    name: "Entry points and diagnostics",
    paths: [
      "bootstrap.js",
      "prepaint.js",
      "check-api.js",
      "validation.js",
      "widget-api.js",
      "portable-api.js",
      "stage-integration.js",
      "age.js",
    ],
  },
  { name: "Floating panel, page dialogs and page keys", paths: ["panel/"] },
  { name: "Annotation presentation, composing and undo", paths: ["annotations/"] },
  { name: "Application and widget host", paths: ["host/"] },
  {
    name: "Page features: annotation inventory, contributions, version travel",
    paths: ["features/"],
  },
  { name: "Records and history", paths: ["records/"] },
  { name: "Page readings, places and paint", paths: ["readings/"] },
  { name: "Transport, errors and notices", paths: ["transport/"] },
  { name: "DOM, geometry, focus and the key register", paths: ["dom/"] },
  { name: "State and registry", paths: ["state/"] },
  { name: "Primitives and the library", paths: ["base/", "lib/"] },
];
// A path names a file exactly and a directory by everything under it.
const inLayers = (paths) =>
  `^${runtime}(?:${paths.map((path) => escaped(path) + (path.endsWith("/") ? "" : "$")).join("|")})`;

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
for (const { paths } of layers)
  for (const path of paths)
    if (!fs.existsSync(new URL(`../${runtime}${path}`, import.meta.url)))
      throw new Error(
        `.config/dependency-cruiser.mjs names a missing runtime module: ${path}`,
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
        pathNot: isOneOf(["widget-api.js", "host/widget-controller.js"]),
      },
      to: { path: isModule("host/application.js") },
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
    ...layers.slice(1).map(({ name, paths }, at) => ({
      name: "layering",
      comment: `${name} imports only its own layer and the layers after it in \`layers\`.`,
      severity: "error",
      from: { path: inLayers(paths) },
      to: { path: inLayers(layers.slice(0, at + 1).flatMap((layer) => layer.paths)) },
    })),
    {
      name: "layering-unplaced",
      comment:
        "Each runtime module is an entry point or stands in a layer's directory.",
      severity: "error",
      from: { path: owners, pathNot: inLayers(layers.flatMap((layer) => layer.paths)) },
      to: {},
    },
  ],
  options: {
    moduleSystems: ["es6"],
    // /checks probes are supplied by the Python server, outside the runtime graph.
    exclude: {
      path: [
        `^${assets}(?!runtime/)`,
        "^/vendor/",
        "^/checks/",
        "^/runtime/records/framework\\.js$",
        "\\.json$",
      ],
    },
    // Resolve as the browser does: a specifier names its file exactly. Without this,
    // `./repaint` finds `repaint.js` and passes here while the browser 404s it.
    enhancedResolveOptions: { extensions: [] },
  },
};
