// https://github.com/sverweij/dependency-cruiser
//
// The runtime's import graph. eslint reads one module at a time, so it sees the edges
// a module declares but not where they lead. Every rule here reads a route through the
// whole graph; `eslint.config.mjs` keeps the rules a module's own source answers, such
// as which specifiers an owner may name and who may write the document root.
//
// The graph is the runtime directory plus `leaf.js`, which is in it so that an owner
// importing the boot entry shows up as an edge. Everything else outside the directory
// is excluded, vendored bundles among them; a bundle reaches no other module, so it is
// never a route between owners. Two runtime modules name a bundle by its site-absolute
// `/vendor/` specifier, which the browser resolves and Node does not, so that form is
// excluded under its own name. Every other unresolvable specifier is a missing module
// and an error.

import fs from "node:fs";

const assets = "skills/leaf/assets/";
const runtime = `${assets}runtime/`;
const bootEntry = `${assets}leaf.js`;

const escaped = (name) => name.replaceAll(/[.*+?^${}()|[\]\\]/g, "\\$&");
const isModule = (name) => `^${runtime}${escaped(name)}$`;
const isOneOf = (names) => `^${runtime}(?:${names.map(escaped).join("|")})$`;

// Each root reaches these modules and nothing else. The pure record folds take values
// and return values; the keyboard dispatcher resolves a key against the register and
// the focused scope. If either reached a painter or an application service, every
// caller would acquire that owner's initialization graph.
const exactClosures = {
  "projection/model.js": [],
  "projection/state.js": ["semantic-state.js"],
  "conversation/model.js": ["anchor-coordinate.js", "conversation/identity.js"],
  "conversation/state.js": ["semantic-state.js"],
  "pending/model.js": ["conversation/identity.js"],
  "pending/state.js": ["semantic-state.js"],
  "keyboard/dispatch.js": [
    "context.js",
    "semantic-state.js",
    "focus.js",
    "keyboard/bindings.js",
    "keyboard/register.js",
    "keyboard/return-stack.js",
    "keyboard/scopes.js",
    "keyboard/text-entry.js",
    "native-layers.js",
    "registry.js",
    "repaint.js",
    "shadow.js",
  ],
};

const applicationOwners = [
  "application.js",
  "delivery.js",
  "keyboard/go-to-sequence.js",
  "keyboard/controller.js",
  "keyboard/page.js",
  "thread-panel.js",
  "pending/state.js",
  "projection/commands.js",
  "state-application.js",
  "state-feed.js",
  "auxiliary-chrome.js",
];

// The renderers. Each receives the semantic commands it uses; one that reaches an
// application owner, through however many helpers, owns state instead of drawing it.
// The geometry and paint group adds the conversation's own presenter, which composes
// them and must stay above them.
const forbiddenClosures = Object.fromEntries([
  ...[
    "conversation/acknowledgments.js",
    "conversation/box.js",
    "conversation/folding.js",
    "conversation/inline.js",
    "conversation/landing.js",
    "conversation/messages.js",
    "conversation/narrowing.js",
    "conversation/panel.js",
    "conversation/placement.js",
    "conversation/presentation.js",
    "conversation/reaction-strips.js",
    "conversation/replies.js",
    "conversation/surfaces.js",
    "conversation/thread-card.js",
    "conversation/thread-list.js",
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
    "margin-layout.js",
    "page-geometry.js",
    "target-paint.js",
  ].map((root) => [root, [...applicationOwners, "conversation/presentation.js"]]),
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
      name: "no-boot-entry",
      comment: "Private runtime owners never import the boot entry.",
      severity: "error",
      from: { path: `^${runtime}` },
      to: { path: `^${escaped(bootEntry)}$` },
    },
    {
      name: "application-behind-widget-api",
      comment:
        "Only the public widget boundary may import the runtime application " +
        "composition root.",
      severity: "error",
      from: {
        path: `^${runtime}`,
        pathNot: isOneOf(["widget-api.js", "widget-controller.js"]),
      },
      to: { path: isModule("application.js") },
    },
    {
      name: "page-keyboard-from-boot-only",
      comment: "Only leaf.js may import keyboard/page.js.",
      severity: "error",
      from: { path: `^${runtime}`, pathNot: isModule("keyboard/page.js") },
      to: { path: isModule("keyboard/page.js") },
    },
    {
      name: "no-cycle",
      comment:
        "A cycle has no boot order; whichever module the browser evaluates first " +
        "reads the other's bindings before they exist.",
      severity: "error",
      from: { path: `^${runtime}` },
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
    exclude: { path: [`^${assets}(?!runtime/|leaf\\.js$)`, "^/vendor/"] },
    // leaf.js is a node in the graph rather than a route through it. Following it
    // would add a second set of edges into every owner it boots.
    doNotFollow: { path: `^${escaped(bootEntry)}$` },
  },
};
