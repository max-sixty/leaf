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
// dependency every owner may hold, not one of the owners whose routes these rules
// read. Its own modules, under `records/framework/`, are checked as any owner is. JSON, such as
// the kernel registry `state/kernel-facts.js` imports, is excluded too: data holds no route
// between owners.

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
  "age",
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
  "page-keys",
  "page-layout",
  "page-map-dialog",
  "page-status",
  "preview",
  "queue-walk",
  "sample-child",
  "stage-integration",
  "user-view",
  "validation",
  "visual-mark-paint",
  "widget-api",
  "work",
  "annotation-layer",
  "copyable-text",
  "field-readings",
  "file-api",
  "http-api",
  "llm-api",
  "margin-map-model",
  "names",
  "page-identity",
  "place-preview",
  "portable-api",
  "queue-title",
  "reports",
  "element-integration",
  "widget-controller",
  "application",
  "delivery",
  "element-data",
  "inline-contributions",
  "margin-bars",
  "mark-room",
  "since-seen",
  "state-application",
  "state-feed",
  "undo",
  "details-shelf",
  "semantic-news",
  "annotation-inventory",
  "change-provenance",
  "margin-model",
  "version",
  "anchor-travel",
  "composing",
  "reactions",
  "sample",
  "contributions",
  "contribution-controls",
  "framework",
  "pending",
  "thread",
  "widget-loader",
  "page-markdown",
  "widget-descriptors",
  "projection",
  "declared-words",
  "views",
  "history",
  "current-target",
  "obligations",
  "drafts",
  "carry",
  "reading-place",
  "editor-view",
  "content-layout",
  "bounds",
  "walk-position",
  "target-paint",
  "reading-regions",
  "off-flow",
  "landing-scroll",
  "key-badges",
  "heading-links",
  "design",
  "code-dressing",
  "code-copy",
  "block-controls",
  "user-place",
  "target-paint-geometry",
  "scroll-containers",
  "pointed-place",
  "media",
  "formulas",
  "element-frame",
  "data",
  "css-anchors",
  "copy-control",
  "code-lines",
  "box-motion",
  "anchor-resolution",
  "addressable-names",
  "widget-elements",
  "visible-target-parts",
  "syntax",
  "resolved-target",
  "references",
  "reach",
  "presentation",
  "passages",
  "native-selection",
  "layer-client",
  "geometry",
  "errors",
  "shadow-stage",
  "shadow",
  "registry",
  "queue-api",
  "notifications",
  "live-leaves",
  "keyboard",
  "interaction-log",
  "dom-children",
  "document-identity",
  "context",
  "activity-words",
  "user-intent",
  "semantic-state",
  "scrolling",
  "root-headers",
  "restore-state",
  "repaint",
  "queues",
  "presence",
  "page-controls",
  "move-focus",
  "motion",
  "language-paths",
  "focus",
  "element-markers",
  "element-axes",
  "dom-move",
  "design-readings",
  "control-selectors",
  "control-labels",
  "contribution-model",
  "arrivals",
  "widget-imports",
  "voice",
  "visual-parts",
  "version-signal",
  "version-picker",
  "ui-marks",
  "traffic",
  "tab-title",
  "tab-store",
  "stylesheets",
  "storage",
  "sample-protocol",
  "root-state",
  "rendering",
  "registry-contract",
  "rect",
  "reading-continuity",
  "prepaint",
  "pointer",
  "page-paint",
  "offline-delivery",
  "lib",
  "kernel-facts",
  "kept",
  "inputs",
  "ids",
  "frame-visibility",
  "field-keys",
  "dress",
  "document-inputs",
  "color-scheme",
  "chrome",
  "bootstrap",
  "base-layer",
  "anchor-coordinate",
  "abort",
];
const isLayer = (names) => `^${runtime}(?:${names.map(escaped).join("|")})(?:\\.js$|/)`;

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
for (const name of layers)
  if (
    ![`${name}.js`, name].some((path) =>
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
        "^/runtime/records/framework\\.js$",
        "\\.json$",
      ],
    },
    // Resolve as the browser does: a specifier names its file exactly. Without this,
    // `./repaint` finds `repaint.js` and passes here while the browser 404s it.
    enhancedResolveOptions: { extensions: [] },
  },
};
