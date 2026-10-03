// https://github.com/sverweij/dependency-cruiser
//
// The runtime's import graph. eslint reads one module at a time, so it sees the edges
// a module declares but not where they lead. Every rule here reads a route through the
// whole graph; `eslint.config.mjs` keeps the rules a module's own source answers, such
// as which specifiers an owner may name and who may write the document root.
//
// The graph includes core owners and the bundled physical renderer. Browser-absolute
// imports resolve through the same canonical resource roots as layer composition.
// The boot entry selects the actual renderer and is outside the owner graph. Vendored
// bundles have no owner edges; every other unresolved specifier is an error.

import fs from "node:fs";
import path from "node:path";

const assets = "skills/leaf/assets/";
const runtime = `${assets}runtime/`;
const overlay = "skills/leaf/packages/default/runtime/annotation-overlay/";
export const runtimeAliases = {
  "/runtime/annotation-overlay": path.resolve(overlay),
  "/runtime": path.resolve(runtime),
};
const owners = `^(?:${runtime}|${overlay})`;
const modulePath = (name) =>
  fs.existsSync(`${runtime}${name}`) ? `${runtime}${name}` : `${overlay}${name}`;

const escaped = (name) => name.replaceAll(/[.*+?^${}()|[\]\\]/g, "\\$&");
const isModule = (name) => `^${escaped(modulePath(name))}$`;
const isOneOf = (names) => `^(?:${names.map(modulePath).map(escaped).join("|")})$`;

// Each root reaches these modules and nothing else. The pure record folds take values
// and return values; the keyboard dispatcher resolves a key against the register and
// the focused scope. If one of them reached a painter or an application service, every
// caller would acquire that owner's initialization graph. image-difference.js reaches
// nothing because `leaf-dev stills` loads it into a blank page on its own.
const exactClosures = {
  "control-selectors.js": [],
  "image-difference.js": [],
  "contribution-model.js": [],
  "margin-model.js": ["contribution-model.js"],
  "margin-map-model.js": ["margin-model.js", "contribution-model.js"],
  "projection/model.js": ["collapse.js"],
  "projection/state.js": ["semantic-state.js"],
  "thread/model.js": [
    "anchor-coordinate.js",
    "thread/identity.js",
    "thread/workflow.js",
  ],
  "thread/state.js": ["semantic-state.js"],
  "thread/workflow.js": [],
  "pending/model.js": ["thread/identity.js"],
  "pending/state.js": ["semantic-state.js"],
  "keyboard/dispatch.js": [
    "context.js",
    "semantic-state.js",
    "focus.js",
    "control-selectors.js",
    "keyboard/bindings.js",
    "keyboard/layer-stack.js",
    "keyboard/register.js",
    "keyboard/scopes.js",
    "keyboard/text-entry.js",
    "pointer.js",
    "user-intent.js",
    "registry.js",
    "rendering.js",
    "repaint.js",
    "shadow.js",
    "storage.js",
  ],
};

const applicationOwners = [
  "application.js",
  "delivery.js",
  "keyboard/go-to-sequence.js",
  "keyboard/controller.js",
  "thread-panel.js",
  "pending/state.js",
  "projection/commands.js",
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
    "thread/narrowing.js",
    "thread/panel.js",
    "thread/placement.js",
    "thread/presentation.js",
    "thread/reaction-strips.js",
    "thread/replies.js",
    "thread/surfaces.js",
    "thread/thread-card.js",
    "thread/thread-list.js",
    "projection/data.js",
    "projection/presentation.js",
  ].map((root) => [root, applicationOwners]),
  ...[
    "anchor-resolution.js",
    "anchor-controls.js",
    "anchor-paint.js",
    "anchor-travel.js",
    "chrome-layout.js",
    "composing/drawing-paint.js",
    "indication.js",
    "margin-layout.js",
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
  if (!fs.existsSync(new URL(`./${modulePath(name)}`, import.meta.url)))
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
        "Core owners cannot load the selected package's physical annotation graph.",
      severity: "error",
      from: { path: `^${runtime}` },
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
    exclude: { path: [`^${assets}(?!runtime/)`, "^/vendor/", "^/checks/"] },
    // Resolve as the browser does: a specifier names its file exactly. Without this,
    // `./repaint` finds `repaint.js` and passes here while the browser 404s it.
    enhancedResolveOptions: { extensions: [] },
    webpackConfig: { fileName: ".dependency-cruiser-resolve.mjs" },
  },
};
