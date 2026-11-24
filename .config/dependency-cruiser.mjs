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
// caller would acquire that owner's initialization graph. A module of the library of
// shared web code (`lib/`) is no owner, and lint keeps each clear of every owner
// (`eslint.config.mjs`), so a root may reach one without naming it here.
const library = `^${runtime}lib/`;
const exactClosures = {
  "queued-work.js": [],
  "control-selectors.js": ["inputs.js", "document-inputs.js"],
  "shadow-tree.js": [],
  "contribution-model.js": ["icon-paths.js", "words.js", "kernel-facts.js"],
  "margin-model.js": [
    "contribution-model.js",
    "icon-paths.js",
    "words.js",
    "kernel-facts.js",
    "thread/workflow.js",
    "voice.js",
  ],
  "margin-map-model.js": [
    "margin-model.js",
    "contribution-model.js",
    "icon-paths.js",
    "words.js",
    "kernel-facts.js",
    "thread/workflow.js",
    "voice.js",
  ],
  "projection/model.js": ["kernel-facts.js", "kept.js"],
  "projection/state.js": ["semantic-state.js", "version-signal.js", "queued-work.js"],
  "thread/model.js": [
    "anchor-coordinate.js",
    "kept.js",
    "thread/identity.js",
    "thread/workflow.js",
    "voice.js",
  ],
  "thread/state.js": [
    "semantic-state.js",
    "version-signal.js",
    "queued-work.js",
    "thread/model.js",
    "anchor-coordinate.js",
    "kept.js",
    "thread/identity.js",
    "thread/workflow.js",
    "voice.js",
  ],
  "thread/workflow.js": ["voice.js"],
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
    "inputs.js",
    "document-inputs.js",
    "control-keys.js",
    "language-paths.js",
    "syntax-languages.js",
    "shadow-tree.js",
    "scroll-containers.js",
    "keeps.js",
    "keyboard/bindings.js",
    "keyboard/layer-stack.js",
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
    "page-paint.js",
    "kept.js",
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
    "anchor-paint.js",
    "anchor-travel.js",
    "page-layout.js",
    "annotation-overlay/composing/drawing-paint.js",
    "annotation-overlay/margin-layout.js",
    "page-geometry.js",
    "target-paint.js",
  ].map((root) => [root, [...applicationOwners, "thread/presentation.js"]]),
]);

// The runtime's children, its files and directories, in one order: each imports only
// the children after it. The order is the one a greedy heuristic for a minimum
// feedback arc set found over the children's imports (Eades, Lin and Smyth), not a
// design: it holds the direction the code already mostly takes, so an import that
// turns against it is noticed when it is written. A child the order doesn't name fails
// `layering-unplaced`; place it after every child that imports it and before every
// child it imports. When a `layering` rule fails, make the import point the other
// way, by passing the value or callback in or by moving what it needs to a child
// after both; where the order itself is wrong for a child, move the child instead.
// `dependency-cruiser-known.json` holds the backward imports that remain, which the
// hook passes over. It only shrinks: delete an entry once its import goes, and fix a
// new backward import rather than adding one.
const layers = [
  "anchor-controls",
  "anchor-note-view",
  "anchor-paint",
  "anchor-placement",
  "annotation-overlay",
  "change-walk",
  "check-api",
  "floating-panel",
  "navigation",
  "page-about",
  "page-geometry",
  "page-inspection",
  "page-layout",
  "page-map-dialog",
  "page-status",
  "preview",
  "queue-walk",
  "stage-integration",
  "user-view",
  "validation",
  "visual-mark-paint",
  "widget-api",
  "work",
  "annotation-layer",
  "copyable-text",
  "element-integration",
  "field-readings",
  "file-api",
  "http-api",
  "llm-api",
  "margin-map-model",
  "mark-room",
  "page-identity",
  "place-preview",
  "portable-api",
  "queue-title",
  "reports",
  "widget-controller",
  "application",
  "delivery",
  "element-data",
  "inline-contributions",
  "leaf-element",
  "margin-bars",
  "shadow-stage",
  "since-seen",
  "state-application",
  "state-feed",
  "undo",
  "annotation-view",
  "data",
  "details-shelf",
  "live-leaves",
  "semantic-news",
  "composing",
  "design",
  "editor-view",
  "reactions",
  "sample",
  "annotation-inventory",
  "change-provenance",
  "contributions",
  "margin-model",
  "version",
  "anchor-travel",
  "carry",
  "contribution-controls",
  "pointed-place",
  "references",
  "thread",
  "content-layout",
  "drafts",
  "framework",
  "pending",
  "restore-state",
  "visible-target-parts",
  "widget-loader",
  "code-copy",
  "design-readings",
  "heading-links",
  "markdown",
  "media",
  "widget-descriptors",
  "block-controls",
  "copy-control",
  "projection",
  "declared-words",
  "code-dressing",
  "code-lines",
  "formulas",
  "syntax",
  "keyboard",
  "history",
  "sample-child",
  "walk-position",
  "current-target",
  "obligations",
  "reading-place",
  "bounds",
  "anchor-resolution",
  "addressable-names",
  "target-paint",
  "resolved-target",
  "reading-regions",
  "presentation",
  "passages",
  "off-flow",
  "layer-client",
  "landing-scroll",
  "errors",
  "user-place",
  "target-paint-geometry",
  "scroll-containers",
  "notifications",
  "element-frame",
  "css-anchors",
  "box-motion",
  "widget-elements",
  "reach",
  "geometry",
  "native-selection",
  "control-labels",
  "user-intent",
  "storage",
  "shadow",
  "repaint",
  "registry",
  "queue-api",
  "move-focus",
  "interaction-log",
  "focus",
  "element-markers",
  "dom-children",
  "document-identity",
  "context",
  "activity-words",
  "visual-parts",
  "semantic-state",
  "scrolling",
  "root-headers",
  "queues",
  "presence",
  "pointer",
  "page-controls",
  "motion",
  "language-paths",
  "keeps",
  "element-axes",
  "dom-move",
  "control-selectors",
  "control-keys",
  "contribution-model",
  "arrivals",
  "words",
  "widget-upgrade",
  "widget-imports",
  "walk-declaration",
  "voice",
  "version-signal",
  "version-picker",
  "traffic",
  "time-axis",
  "text-alignment",
  "tab-title",
  "tab-store",
  "syntax-tokens",
  "syntax-languages",
  "stylesheets",
  "shown-box",
  "shadow-tree",
  "sample-protocol",
  "root-state",
  "role-button-press",
  "rendering",
  "registry-contract",
  "rect",
  "reading-continuity",
  "queued-work",
  "prepaint",
  "page-paint",
  "offline-delivery",
  "kernel-facts",
  "kept",
  "inputs",
  "ids",
  "icons",
  "icon-paths",
  "frame-visibility",
  "field-keys",
  "exception",
  "dress",
  "document-inputs",
  "control-faces",
  "color-scheme",
  "chrome",
  "canvas",
  "bootstrap",
  "base-layer",
  "anchor-coordinate",
  "abort",
];
const isLayer = (names) => `^${runtime}(?:${names.map(escaped).join("|")})(?:\\.js$|/)`;

// A rule naming a module that no longer exists matches nothing and passes, so the
// declarations above are checked against the directory before they become rules. A
// layer names a directory, or a file without its `.js`.
for (const name of new Set([
  ...[exactClosures, forbiddenClosures].flatMap((closures) =>
    Object.entries(closures).flatMap(([root, names]) => [root, ...names]),
  ),
  ...layers,
]))
  if (
    ![name, `${name}.js`].some((path) =>
      fs.existsSync(new URL(`../${runtime}${path}`, import.meta.url)),
    )
  )
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
    ...layers.slice(1).map((name, at) => ({
      name: "layering",
      comment: `${name} imports only the children after it in \`layers\`.`,
      severity: "error",
      from: { path: isLayer([name]) },
      to: { path: isLayer(layers.slice(0, at + 1)) },
    })),
    {
      name: "layering-unplaced",
      comment: "Each child of the runtime has a place in `layers`.",
      severity: "error",
      from: { path: owners, pathNot: isLayer(layers) },
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
        "^/runtime/framework\\.js$",
        "\\.json$",
      ],
    },
    // Resolve as the browser does: a specifier names its file exactly. Without this,
    // `./repaint` finds `repaint.js` and passes here while the browser 404s it.
    enhancedResolveOptions: { extensions: [] },
  },
};
