import fs from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

// The browser's names the layer uses, for `no-undef`: a moved function that lost an
// import must fail the hook rather than bind to `window.*` on the first page that
// reaches it. Only names in use are listed — `open`, `top`, `parent`, `origin`, `escape`
// are locals here, and declaring the browser's copies would hide exactly the lost import
// this rule is for. A new global is added when the hook refuses it.
const browserGlobals = Object.fromEntries(
  [
    "AbortController",
    "CSS",
    "CustomEvent",
    "DOMException",
    "DOMParser",
    "DOMRect",
    "Element",
    "Event",
    "EventSource",
    "HTMLAnchorElement",
    "HTMLButtonElement",
    "HTMLDialogElement",
    "HTMLElement",
    "HTMLLinkElement",
    "HTMLScriptElement",
    "HTMLSpanElement",
    "Highlight",
    "MutationObserver",
    "Node",
    "Range",
    "ResizeObserver",
    "SVGAnimatedLength",
    "SVGElement",
    "SVGGeometryElement",
    "SVGSVGElement",
    "ShadowRoot",
    "URL",
    "URLSearchParams",
    "XMLSerializer",
    "addEventListener",
    "cancelAnimationFrame",
    "clearTimeout",
    "console",
    "crypto",
    "customElements",
    "document",
    "fetch",
    "getComputedStyle",
    "getSelection",
    "history",
    "innerHeight",
    "innerWidth",
    "localStorage",
    "location",
    "matchMedia",
    "navigator",
    "performance",
    "queueMicrotask",
    "requestAnimationFrame",
    "scrollX",
    "scrollY",
    "sessionStorage",
    "setInterval",
    "setTimeout",
    "structuredClone",
    "window",
  ].map((name) => [name, "readonly"]),
);

const entryBoundary = {
  "no-restricted-imports": [
    "error",
    {
      paths: [
        {
          name: "/leaf.js",
          message: "Import Leaf capabilities from /runtime/widget-api.js.",
        },
      ],
      patterns: [
        {
          regex: "^\\.{1,2}/(?:.*/)?(?:leaf|widget-api)\\.js$",
          message: "Do not create a relative edge to the entry or public facade.",
        },
      ],
    },
  ],
  "no-restricted-syntax": [
    "error",
    {
      selector: 'ImportExpression[source.value="/leaf.js"]',
      message: "Import Leaf capabilities statically from /runtime/widget-api.js.",
    },
    {
      selector:
        "ImportExpression[source.value=/^\\.{1,2}\\/(?:.*\\/)?(?:leaf|widget-api)\\.js$/]",
      message: "Do not create a relative edge to the entry or public facade.",
    },
  ],
};

const publicRuntimeBoundary = {
  "no-restricted-imports": [
    "error",
    {
      paths: [
        {
          name: "/leaf.js",
          message: "Import Leaf capabilities from /runtime/widget-api.js.",
        },
      ],
      patterns: [
        {
          regex: "^/runtime/(?!widget-api\\.js$)",
          message: "Behavior and probe modules use /runtime/widget-api.js.",
        },
        {
          regex: "^\\.{1,2}/(?:.*/)?runtime/",
          message: "Behavior and probe modules use /runtime/widget-api.js.",
        },
        {
          regex: "^\\.{1,2}/(?:.*/)?(?:leaf|widget-api)\\.js$",
          message: "Do not create a relative edge to the entry or public facade.",
        },
      ],
    },
  ],
  "no-restricted-syntax": [
    "error",
    {
      selector: 'ImportExpression[source.value="/leaf.js"]',
      message: "Import Leaf capabilities statically from /runtime/widget-api.js.",
    },
    {
      selector:
        'ImportExpression[source.value=/^\\/runtime\\//]:not([source.value="/runtime/widget-api.js"])',
      message: "Behavior and probe modules use /runtime/widget-api.js.",
    },
    {
      selector: "ImportExpression[source.value=/^\\.{1,2}\\/(?:.*\\/)?runtime\\//]",
      message: "Behavior and probe modules use /runtime/widget-api.js.",
    },
    {
      selector:
        "ImportExpression[source.value=/^\\.{1,2}\\/(?:.*\\/)?(?:leaf|widget-api)\\.js$/]",
      message: "Do not create a relative edge to the entry or public facade.",
    },
    {
      selector: 'ImportExpression:not([source.type="Literal"])',
      message:
        "Dynamic module paths hide dependency edges; declare a literal public import.",
    },
  ],
};

const ownerBoundary = {
  "no-restricted-imports": [
    "error",
    {
      paths: [
        {
          name: "/leaf.js",
          message: "Private runtime owners never import the boot entry.",
        },
        {
          name: "/runtime/widget-api.js",
          message:
            "Private runtime owners import one another directly, not the facade.",
        },
      ],
      patterns: [
        {
          regex: "^\\.{1,2}/(?:.*/)?(?:leaf|widget-api)\\.js$",
          message: "Private runtime owners never import the entry or public facade.",
        },
      ],
    },
  ],
  "no-restricted-syntax": [
    "error",
    {
      selector: 'ImportExpression:not([source.type="Literal"])',
      message:
        "Runtime dependencies must be literal imports; computed paths belong to content loaders.",
    },
    {
      selector:
        "ImportExpression[source.value=/^\\/(?:leaf|runtime\\/widget-api)\\.js$/]",
      message: "Private runtime owners never import the entry or public facade.",
    },
    {
      selector:
        "ImportExpression[source.value=/^\\.{1,2}\\/(?:.*\\/)?(?:leaf|widget-api)\\.js$/]",
      message: "Private runtime owners never import the entry or public facade.",
    },
  ],
};

const runtimeRoot = fileURLToPath(
  new URL("./skills/leaf/assets/runtime/", import.meta.url),
);
const runtimeName = (file) =>
  path.relative(runtimeRoot, file).split(path.sep).join("/");
const assetRoot = path.dirname(runtimeRoot) + path.sep;
const runtimeDependency = (file, source) => {
  if (!source.startsWith(".") && !source.startsWith("/")) return null;
  const target = fileURLToPath(
    new URL(
      source.startsWith("/") ? `.${source}` : source,
      pathToFileURL(source.startsWith("/") ? assetRoot : file),
    ),
  );
  const name = runtimeName(target);
  return !name.startsWith("../") || name === "../leaf.js" ? name : null;
};

const exactClosures = new Map(
  Object.entries({
    "projection/model.js": [],
    "projection/state.js": [],
    "conversation/model.js": ["anchor-coordinate.js", "conversation/identity.js"],
    "conversation/state.js": [
      "anchor-coordinate.js",
      "conversation/identity.js",
      "conversation/model.js",
    ],
    "pending/model.js": ["conversation/identity.js"],
    "pending/state.js": ["conversation/identity.js", "pending/model.js"],
    "keyboard/dispatch.js": [
      "context.js",
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
  }).map(([root, allowed]) => [root, new Set(allowed)]),
);

const applicationOwners = new Set([
  "application.js",
  "delivery.js",
  "keyboard/go-to-sequence.js",
  "keyboard/controller.js",
  "keyboard/page.js",
  "thread-panel.js",
  "pending/state.js",
  "projection/commands.js",
  "requests.js",
  "state-application.js",
  "state-feed.js",
  "auxiliary-chrome.js",
]);

const forbiddenClosures = new Map([
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
  ].map((root) => [
    root,
    new Set([...applicationOwners, "conversation/presentation.js"]),
  ]),
  ...["projection/data.js", "projection/presentation.js"].map((root) => [
    root,
    applicationOwners,
  ]),
]);

let runtimeGraph;
function graphFrom(parser) {
  if (runtimeGraph) return runtimeGraph;
  const graph = new Map();
  const visitTree = (directory) => {
    for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
      const file = path.join(directory, entry.name);
      if (entry.isDirectory()) {
        visitTree(file);
        continue;
      }
      if (!file.endsWith(".js")) continue;
      const ast = parser.parse(fs.readFileSync(file, "utf8"), {
        ecmaVersion: "latest",
        sourceType: "module",
      });
      const imports = [];
      const seen = new Set();
      const walk = (node) => {
        if (!node || typeof node !== "object" || seen.has(node)) return;
        seen.add(node);
        if (
          (node.type === "ImportDeclaration" ||
            node.type === "ExportNamedDeclaration" ||
            node.type === "ExportAllDeclaration") &&
          typeof node.source?.value === "string"
        ) {
          const resourceType = node.attributes?.find(
            (attribute) => (attribute.key.name ?? attribute.key.value) === "type",
          )?.value.value;
          if (resourceType && resourceType !== "javascript") {
            const resource = runtimeDependency(file, node.source.value);
            if (resource && !fs.existsSync(path.join(runtimeRoot, resource)))
              throw new Error(
                `${runtimeName(file)} imports a missing resource: ${resource}`,
              );
          } else imports.push(node.source.value);
        } else if (
          node.type === "ImportExpression" &&
          typeof node.source?.value === "string"
        )
          imports.push(node.source.value);
        for (const value of Object.values(node)) {
          if (Array.isArray(value)) value.forEach(walk);
          else walk(value);
        }
      };
      walk(ast);
      graph.set(
        runtimeName(file),
        imports
          .map((source) => runtimeDependency(file, source))
          .filter((target) => target !== null),
      );
    }
  };
  visitTree(runtimeRoot);
  const namedModules = new Set([
    ...exactClosures.keys(),
    ...forbiddenClosures.keys(),
    ...[...exactClosures.values(), ...forbiddenClosures.values()].flatMap((names) => [
      ...names,
    ]),
  ]);
  for (const module of namedModules)
    if (!graph.has(module))
      throw new Error(`architecture/runtime-graph names a missing module: ${module}`);
  for (const [module, dependencies] of graph)
    for (const dependency of dependencies)
      if (dependency !== "../leaf.js" && !graph.has(dependency))
        throw new Error(`${module} imports a missing runtime module: ${dependency}`);
  runtimeGraph = graph;
  return graph;
}

function pathsFrom(graph, root) {
  const paths = new Map([[root, [root]]]);
  const queue = [root];
  for (const current of queue)
    for (const dependency of graph.get(current) ?? []) {
      if (!graph.has(dependency) || paths.has(dependency)) continue;
      paths.set(dependency, [...paths.get(current), dependency]);
      queue.push(dependency);
    }
  return paths;
}

function cyclicComponents(graph) {
  let nextIndex = 0;
  const indices = new Map();
  const lowLinks = new Map();
  const stack = [];
  const stacked = new Set();
  const components = [];
  const visit = (module) => {
    indices.set(module, nextIndex);
    lowLinks.set(module, nextIndex);
    nextIndex += 1;
    stack.push(module);
    stacked.add(module);
    for (const dependency of graph.get(module) ?? []) {
      if (!graph.has(dependency)) continue;
      if (!indices.has(dependency)) {
        visit(dependency);
        lowLinks.set(module, Math.min(lowLinks.get(module), lowLinks.get(dependency)));
      } else if (stacked.has(dependency))
        lowLinks.set(module, Math.min(lowLinks.get(module), indices.get(dependency)));
    }
    if (lowLinks.get(module) !== indices.get(module)) return;
    const component = [];
    let member;
    do {
      member = stack.pop();
      stacked.delete(member);
      component.push(member);
    } while (member !== module);
    if (component.length > 1 || (graph.get(module) ?? []).includes(module))
      components.push(component.sort());
  };
  for (const module of graph.keys()) if (!indices.has(module)) visit(module);
  return components;
}

const architecturePlugin = {
  rules: {
    "root-style-ownership": {
      meta: { type: "problem", schema: [] },
      create(context) {
        const file = runtimeName(context.filename ?? context.getFilename());
        // The prepaint bootstrap runs before the module graph and writes only
        // provisional choices. root-state.js is the sole standing mutation boundary.
        if (file === "bootstrap.js" || file === "root-state.js") return {};
        const source = context.sourceCode ?? context.getSourceCode();
        const propertyName = (node) =>
          node?.type === "MemberExpression"
            ? node.computed
              ? node.property.type === "Literal"
                ? node.property.value
                : null
              : node.property.name
            : null;
        const variable = (node) => {
          if (node?.type !== "Identifier") return null;
          for (let scope = source.getScope(node); scope; scope = scope.upper) {
            const found = scope.set.get(node.name);
            if (found) return found;
          }
          return null;
        };
        const initialValue = (node, seen) => {
          const found = variable(node);
          if (!found || seen.has(found)) return null;
          seen.add(found);
          const definition = found.defs.find(
            ({ type, node: declared }) =>
              type === "Variable" && declared.id.type === "Identifier",
          );
          return definition?.node.init ?? null;
        };
        const isDocument = (node, seen = new Set()) => {
          if (node?.type === "ChainExpression")
            return isDocument(node.expression, seen);
          if (node?.type === "Identifier") {
            if (node.name === "document" && !variable(node)?.defs.length) return true;
            const initial = initialValue(node, seen);
            return initial ? isDocument(initial, seen) : false;
          }
          return (
            node?.type === "MemberExpression" &&
            propertyName(node) === "document" &&
            node.object.type === "Identifier" &&
            node.object.name === "window"
          );
        };
        const isDocumentRoot = (node, seen = new Set()) => {
          if (node?.type === "ChainExpression")
            return isDocumentRoot(node.expression, seen);
          if (node?.type === "Identifier") {
            const initial = initialValue(node, seen);
            return initial ? isDocumentRoot(initial, seen) : false;
          }
          return (
            node?.type === "MemberExpression" &&
            ["documentElement", "body"].includes(propertyName(node)) &&
            isDocument(node.object, seen)
          );
        };
        const isRootStyle = (node, seen = new Set()) => {
          if (node?.type === "ChainExpression")
            return isRootStyle(node.expression, seen);
          if (node?.type === "Identifier") {
            const initial = initialValue(node, seen);
            return initial ? isRootStyle(initial, seen) : false;
          }
          return (
            node?.type === "MemberExpression" &&
            propertyName(node) === "style" &&
            isDocumentRoot(node.object, seen)
          );
        };
        const reportsRootStyleTarget = (node) =>
          isRootStyle(node) ||
          (node?.type === "MemberExpression" && isRootStyle(node.object));
        const report = (node) =>
          context.report({
            node,
            message:
              "Mutate document-root inline styles through root-state.js so authored revision replacement preserves ownership.",
          });
        return {
          AssignmentExpression(node) {
            if (reportsRootStyleTarget(node.left)) report(node);
          },
          UpdateExpression(node) {
            if (reportsRootStyleTarget(node.argument)) report(node);
          },
          CallExpression(node) {
            if (
              node.callee.type === "MemberExpression" &&
              ["setProperty", "removeProperty"].includes(propertyName(node.callee)) &&
              isRootStyle(node.callee.object)
            )
              report(node);
            if (
              node.callee.type === "MemberExpression" &&
              ["setAttribute", "removeAttribute", "toggleAttribute"].includes(
                propertyName(node.callee),
              ) &&
              isDocumentRoot(node.callee.object) &&
              node.arguments[0]?.type === "Literal" &&
              node.arguments[0].value === "style"
            )
              report(node);
            if (
              node.callee.type === "MemberExpression" &&
              node.callee.object.type === "Identifier" &&
              ["Object", "Reflect"].includes(node.callee.object.name) &&
              ["assign", "set"].includes(propertyName(node.callee)) &&
              isRootStyle(node.arguments[0])
            )
              report(node);
          },
        };
      },
    },
    "runtime-graph": {
      meta: { type: "problem", schema: [] },
      create(context) {
        return {
          Program(node) {
            const file = runtimeName(context.filename ?? context.getFilename());
            const graph = graphFrom(context.languageOptions.parser);
            const direct = graph.get(file) ?? [];
            if (direct.includes("../leaf.js"))
              context.report({
                node,
                message: "Private runtime owners never import the boot entry.",
              });
            if (file !== "widget-api.js" && direct.includes("application.js"))
              context.report({
                node,
                message:
                  "Only widget-api.js may import the runtime application composition root.",
              });
            if (file !== "keyboard/page.js" && direct.includes("keyboard/page.js"))
              context.report({
                node,
                message: "Only leaf.js may import keyboard/page.js.",
              });

            for (const component of cyclicComponents(graph))
              if (component.includes(file))
                context.report({
                  node,
                  message: `Runtime import cycle: ${component.join(" -> ")}.`,
                });

            for (const [root, allowed] of exactClosures) {
              const reached = pathsFrom(graph, root);
              const violation = [...reached]
                .filter(
                  ([dependency, route]) =>
                    dependency !== root &&
                    !allowed.has(dependency) &&
                    route.includes(file),
                )
                .sort((a, b) => a[1].length - b[1].length)[0];
              if (violation)
                context.report({
                  node,
                  message: `${root} has a forbidden transitive dependency through ${violation[1].join(" -> ")}.`,
                });
            }
            for (const [root, forbidden] of forbiddenClosures) {
              const reached = pathsFrom(graph, root);
              const violation = [...forbidden]
                .map((dependency) => reached.get(dependency))
                .filter((route) => route?.includes(file))
                .sort((a, b) => a.length - b.length)[0];
              if (violation)
                context.report({
                  node,
                  message: `${root} has a forbidden transitive dependency through ${violation.join(" -> ")}.`,
                });
            }
          },
        };
      },
    },
  },
};

export default [
  {
    ignores: [
      "examples/corpus.html",
      "skills/leaf/assets/vendor/**",
      "skills/leaf/packages/*/vendor/**",
    ],
    linterOptions: { noInlineConfig: true },
  },
  {
    files: ["**/*.{js,mjs}"],
    languageOptions: { ecmaVersion: "latest", sourceType: "module" },
    rules: publicRuntimeBoundary,
  },
  {
    // This transport boot entry loads Leaf after installing the MCP fetch bridge.
    // It may boot /leaf.js, but must not reach private runtime owners.
    files: ["scripts/mcp-app/direct-entry.js"],
    rules: {
      "no-restricted-syntax": [
        "error",
        ...publicRuntimeBoundary["no-restricted-syntax"]
          .slice(1)
          .filter(
            (rule) => rule.selector !== 'ImportExpression[source.value="/leaf.js"]',
          ),
      ],
    },
  },
  {
    files: ["skills/leaf/scripts/leaf/render-checks/*.js"],
    rules: {
      ...publicRuntimeBoundary,
      "no-restricted-syntax": [
        "error",
        {
          selector: "ImportExpression",
          message: "Render probes declare every dependency with a static import.",
        },
      ],
    },
  },
  {
    files: ["skills/leaf/scripts/leaf/render-checks/widgets.js"],
    rules: {
      // This core probe validates the visual-part registry itself. Keep that diagnostic
      // out of the package facade while leaving every other probe on the public API.
      "no-restricted-imports": [
        "error",
        {
          paths: [
            {
              name: "/leaf.js",
              message: "Import Leaf capabilities from /runtime/widget-api.js.",
            },
          ],
          patterns: [
            {
              regex: "^/runtime/(?!widget-api\\.js$|visual-parts\\.js$)",
              message: "Behavior and probe modules use /runtime/widget-api.js.",
            },
            {
              regex: "^\\.{1,2}/(?:.*/)?runtime/",
              message: "Behavior and probe modules use /runtime/widget-api.js.",
            },
            {
              regex: "^\\.{1,2}/(?:.*/)?(?:leaf|widget-api)\\.js$",
              message: "Do not create a relative edge to the entry or public facade.",
            },
          ],
        },
      ],
    },
  },
  {
    files: ["skills/leaf/assets/leaf.js"],
    plugins: { architecture: architecturePlugin },
    rules: {
      ...entryBoundary,
      "architecture/root-style-ownership": "error",
      "no-restricted-syntax": [
        "error",
        ...entryBoundary["no-restricted-syntax"].slice(1),
        {
          selector:
            "ExportNamedDeclaration, ExportDefaultDeclaration, ExportAllDeclaration",
          message: "leaf.js only boots the runtime; domain owners export APIs.",
        },
      ],
    },
  },
  {
    files: ["skills/leaf/assets/**/*.js", "skills/leaf/packages/*/**/*.js"],
    ignores: ["skills/leaf/assets/vendor/**", "skills/leaf/packages/*/vendor/**"],
    languageOptions: { globals: browserGlobals },
    rules: { "no-undef": "error" },
  },
  {
    files: ["skills/leaf/assets/runtime/**/*.js"],
    plugins: { architecture: architecturePlugin },
    rules: {
      ...ownerBoundary,
      "architecture/root-style-ownership": "error",
      "architecture/runtime-graph": "error",
    },
  },
  {
    // These are the two boundaries that load authored/package modules, whose paths
    // are data rather than runtime dependencies. Literal imports still enter the graph.
    files: [
      "skills/leaf/assets/runtime/interaction-gallery.js",
      "skills/leaf/assets/runtime/widget-loader.js",
    ],
    rules: {
      "no-restricted-syntax": [
        "error",
        ...ownerBoundary["no-restricted-syntax"]
          .slice(1)
          .filter(
            (rule) => rule.selector !== 'ImportExpression:not([source.type="Literal"])',
          ),
      ],
    },
  },
  {
    // These primitives may use the browser, but importing an application owner
    // would make every caller acquire that owner's initialization and paint graph.
    files: [
      "skills/leaf/assets/runtime/anchor-coordinate.js",
      "skills/leaf/assets/runtime/chrome.js",
      "skills/leaf/assets/runtime/dom-children.js",
      "skills/leaf/assets/runtime/focus.js",
      "skills/leaf/assets/runtime/repaint.js",
      "skills/leaf/assets/runtime/root-state.js",
      "skills/leaf/assets/runtime/conversation/identity.js",
    ],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "ImportDeclaration, ImportExpression, ExportAllDeclaration, ExportNamedDeclaration[source]",
          message: "Runtime primitives must remain independent of other owners.",
        },
      ],
    },
  },
  {
    // Conversation folding accepts values; it must not obtain them from browser
    // stores or painters. The current derived reading has the same dependency floor.
    files: [
      "skills/leaf/assets/runtime/projection/model.js",
      "skills/leaf/assets/runtime/projection/state.js",
      "skills/leaf/assets/runtime/pending/model.js",
      "skills/leaf/assets/runtime/pending/state.js",
      "skills/leaf/assets/runtime/conversation/model.js",
      "skills/leaf/assets/runtime/conversation/state.js",
    ],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              regex:
                "^(?!\\.\\./anchor-coordinate\\.js$|(?:\\.\\./conversation/|\\./)identity\\.js$|\\./model\\.js$)",
              message: "Conversation readings depend only on pure record operations.",
            },
          ],
        },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "ImportExpression",
          message:
            "Conversation readings declare their record dependencies statically.",
        },
      ],
      "no-restricted-globals": [
        "error",
        ...Object.keys(browserGlobals).filter((name) => name !== "structuredClone"),
      ],
    },
  },
  {
    files: ["skills/leaf/scripts/leaf/render-checks/standalone.js"],
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector: "ImportDeclaration, ImportExpression, ExportAllDeclaration",
          message: "Standalone render probes must remain import-free.",
        },
        {
          selector: "ExportNamedDeclaration[source]",
          message: "Standalone render probes must not reexport another module.",
        },
      ],
    },
  },
  {
    files: ["skills/leaf/scripts/leaf/render-checks/init.js"],
    languageOptions: { sourceType: "script" },
  },
];
