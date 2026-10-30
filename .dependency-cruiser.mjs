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
// served path, `/runtime/framework.js`: like Lit beneath it, the framework is a
// dependency every owner may hold, not one of the owners whose routes these rules
// read. Its own modules, under `framework/`, are checked as any owner is. JSON, such as
// the kernel registry `kernel-facts.js` imports, is excluded too: data holds no route
// between owners.

import fs from "node:fs";

const assets = "browser/";
const runtime = `${assets}runtime/`;
const overlay = `${runtime}annotation-overlay/`;
const owners = `^${runtime}`;

const escaped = (name) => name.replaceAll(/[.*+?^${}()|[\]\\]/g, "\\$&");
const isModule = (name) => `^${runtime}${escaped(name)}$`;
const isOneOf = (names) => `^${runtime}(?:${names.map(escaped).join("|")})$`;

// Each root reaches these modules and nothing else. The pure record folds take values
// and return values; the keyboard dispatcher resolves a key against the register and
// the focused scope. If one of them reached a painter or an application service, every
// caller would acquire that owner's initialization graph.
const exactClosures = {
  "queued-work.js": [],
  "control-selectors.js": [],
  "shadow-tree.js": [],
  "contribution-model.js": ["icon-paths.js", "words.js", "kernel-facts.js"],
  "margin-model.js": [
    "contribution-model.js",
    "icon-paths.js",
    "words.js",
    "kernel-facts.js",
    "thread/workflow.js",
  ],
  "margin-map-model.js": [
    "margin-model.js",
    "contribution-model.js",
    "icon-paths.js",
    "words.js",
    "kernel-facts.js",
    "thread/workflow.js",
  ],
  "projection/model.js": ["kernel-facts.js"],
  "projection/state.js": ["semantic-state.js", "version-signal.js", "queued-work.js"],
  "thread/model.js": [
    "anchor-coordinate.js",
    "thread/identity.js",
    "thread/workflow.js",
  ],
  "thread/state.js": [
    "semantic-state.js",
    "version-signal.js",
    "queued-work.js",
    "thread/model.js",
    "anchor-coordinate.js",
    "thread/identity.js",
    "thread/workflow.js",
  ],
  "thread/workflow.js": [],
  "pending/model.js": ["thread/identity.js", "kernel-facts.js"],
  "pending/state.js": ["semantic-state.js", "version-signal.js", "queued-work.js"],
  "keyboard/dispatch.js": [
    "context.js",
    "semantic-state.js",
    "version-signal.js",
    "queued-work.js",
    "focus.js",
    "dom-move.js",
    "control-selectors.js",
    "shadow-tree.js",
    "keeps.js",
    "keyboard/bindings.js",
    "keyboard/layer-stack.js",
    // Modal seating carries the existing chrome sheet into a source shadow root.
    "stylesheets.js",
    "keyboard/register.js",
    "keyboard/scopes.js",
    "keyboard/text-entry.js",
    "role-button-press.js",
    "keeps.js",
    "pointer.js",
    "user-intent.js",
    "registry.js",
    "registry-contract.js",
    "kernel-facts.js",
    "rendering.js",
    "frame-visibility.js",
    "repaint.js",
    "shadow.js",
    "arrivals.js",
    // A widget's declared commands arrive by the event it dispatches, and a malformed
    // declaration is reported as its failure.
    "widget-upgrade.js",
    "exception.js",
    "page-paint.js",
  ],
};

const applicationOwners = [
  "application.js",
  "delivery.js",
  "keyboard/go-to-sequence.js",
  "keyboard/controller.js",
  "pending/state.js",
  "undo.js",
  "state-application.js",
  "state-feed.js",
];

// The renderers. Each receives the semantic commands it uses; one that reaches an
// application owner, through however many helpers, owns state instead of drawing it.
// The geometry and paint group adds the thread's own presenter, which composes
// them and must stay above them.
const forbiddenClosures = Object.fromEntries([
  ...[
    "thread/box.js",
    "thread/folding.js",
    "thread/inline.js",
    "thread/landing.js",
    "thread/messages.js",
    "thread/placement.js",
    "thread/presentation.js",
    "thread/reaction-strips.js",
    "thread/replies.js",
    "thread/surfaces.js",
    "thread/thread-card.js",
    "projection/data.js",
    "projection/presentation.js",
  ].map((root) => [root, applicationOwners]),
  ...[
    "addressable-names.js",
    "anchor-resolution.js",
    "anchor-controls.js",
    "annotation-overlay/anchor-paint.js",
    "anchor-travel.js",
    "page-layout.js",
    "annotation-overlay/composing/drawing-paint.js",
    "annotation-overlay/margin-layout.js",
    "page-geometry.js",
    "target-paint.js",
  ].map((root) => [root, [...applicationOwners, "thread/presentation.js"]]),
]);

// A rule naming a module that no longer exists matches nothing and passes, so the
// declarations above are checked against the directory before they become rules.
for (const name of new Set(
  [exactClosures, forbiddenClosures].flatMap((closures) =>
    Object.entries(closures).flatMap(([root, names]) => [root, ...names]),
  ),
))
  if (!fs.existsSync(new URL(`./${runtime}${name}`, import.meta.url)))
    throw new Error(`.dependency-cruiser.mjs names a missing runtime module: ${name}`);

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
        pathNot: isOneOf(["widget-api.js", "widget-controller.js"]),
      },
      to: { path: isModule("application.js") },
    },
    {
      name: "page-keyboard-from-boot-only",
      comment:
        "keyboard/page.js declares the page's own keys as it evaluates and exports " +
        "nothing; only leaf.js imports it, for that effect.",
      severity: "error",
      from: { path: owners, pathNot: isModule("keyboard/page.js") },
      to: { path: isModule("keyboard/page.js") },
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
      name: "no-cycle",
      comment:
        "A cycle has no boot order; whichever module the browser evaluates first " +
        "reads the other's bindings before they exist.",
      severity: "error",
      from: { path: owners },
      to: { circular: true },
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
      to: { reachable: true, pathNot: isOneOf([root, ...allowed]) },
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
      path: [
        `^${assets}(?!runtime/)`,
        "^/vendor/",
        "^/checks/",
        "^/runtime/framework\\.js$",
        "\\.json$",
      ],
    },
    // Resolve as the browser does: a specifier names its file exactly. Without this,
    // `./repaint` finds `repaint.js` and passes here while the browser 404s it.
    enhancedResolveOptions: { extensions: [] },
  },
};
