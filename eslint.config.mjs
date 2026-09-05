import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, relative, resolve } from "node:path";

const RUNTIME = join(import.meta.dirname, "skills/leaf/assets/runtime");

// The runtime's owners form one import cycle, so a module in it evaluates in whatever
// order leaf.js's imports reach it, and its body may touch only what is certainly
// initialised by then: its own declarations, a module outside the cycle (evaluated
// before any importer's body runs), and a function declaration of a cycle member —
// referenced, never called, since the callee's own imports may still be unevaluated.
// That order is fixed by the import graph and the same on every page, so a read that
// breaks the rule is no error at all until an unrelated import edge reorders the walk,
// and then a `ReferenceError` at boot on every page. The browser gate is the guarantee;
// this rule is the early, line-precise word, and it has to see the whole cycle, which
// is why the commit hook lints the runtime directory rather than the changed file. It
// reads module-scope statements, the blocks under them, and a function called in place;
// a callback another module runs during evaluation is the browser gate's to catch.
const runtimeModules = (dir = RUNTIME) =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory())
      return name === "vendor" ? [] : runtimeModules(path);
    return path.endsWith(".js") ? [path] : [];
  });
const importsOf = (path) =>
  [...readFileSync(path, "utf8").matchAll(/from "(\.[^"]+\.js)"/g)].map((m) =>
    resolve(dirname(path), m[1]),
  );
function ownerCycle() {
  const edges = new Map(runtimeModules().map((path) => [path, importsOf(path)]));
  const reaches = (from, to) => {
    const seen = new Set();
    const stack = [...(edges.get(from) ?? [])];
    while (stack.length) {
      const next = stack.pop();
      if (next === to) return true;
      if (seen.has(next)) continue;
      seen.add(next);
      stack.push(...(edges.get(next) ?? []));
    }
    return false;
  };
  return new Set([...edges.keys()].filter((path) => reaches(path, path)));
}
const exportKinds = new Map();
const exportsFunction = (path, name) => {
  if (!exportKinds.has(path)) {
    const source = readFileSync(path, "utf8");
    const declared = new Set(
      [
        ...source.matchAll(/^(?:export )?(?:async )?function\s+([A-Za-z_$][\w$]*)/gm),
      ].map((m) => m[1]),
    );
    const exported = new Set();
    for (const [, list] of source.matchAll(/^export \{([^}]*)\}\s*;/gm))
      for (const item of list.split(","))
        if (item.trim()) {
          const [local, as] = item.split(/\s+as\s+/).map((part) => part.trim());
          if (declared.has(local)) exported.add(as ?? local);
        }
    for (const local of declared)
      if (new RegExp(`^export (?:async )?function\\s+${local}\\b`, "m").test(source))
        exported.add(local);
    exportKinds.set(path, exported);
  }
  return exportKinds.get(path).has(name);
};
const evaluationOrder = {
  meta: { type: "problem", schema: [] },
  create(context) {
    const cycle = ownerCycle();
    const file = context.filename;
    if (!cycle.has(file)) return {};
    // What runs as the module evaluates: module-scope statements, the blocks under them,
    // and a function the module calls in place (an IIFE). A callback the module hands to
    // something else that calls it back during evaluation is not seen here.
    const invokedInPlace = (scope) =>
      scope.type === "function" &&
      scope.block.parent?.type === "CallExpression" &&
      scope.block.parent.callee === scope.block;
    const scopesEvaluated = (scope) =>
      (scope.type === "function" && !invokedInPlace(scope)) || scope.type === "class"
        ? []
        : [scope, ...scope.childScopes.flatMap(scopesEvaluated)];
    return {
      Program(node) {
        const moduleScope = context.sourceCode.getScope(node);
        for (const scope of scopesEvaluated(moduleScope))
          for (const reference of scope.references) {
            const definition = reference.resolved?.defs[0];
            if (definition?.type !== "ImportBinding") continue;
            const source = resolve(dirname(file), definition.parent.source.value);
            if (!cycle.has(source)) continue;
            const owner = relative(RUNTIME, source);
            const name = definition.node.imported?.name ?? definition.name.name;
            const identifier = reference.identifier;
            const parent = identifier.parent;
            const called =
              (parent.type === "CallExpression" || parent.type === "NewExpression") &&
              parent.callee === identifier;
            if (exportsFunction(source, name) && !called) continue;
            context.report({
              node: identifier,
              message: called
                ? `${owner} is in the owner cycle, so its ${name} may not be called as this module evaluates: call it in a mount step or at use.`
                : `${owner} is in the owner cycle, so its ${name} may not be read as this module evaluates: ask for it at use.`,
            });
          }
      },
    };
  },
};

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
    rules: {
      ...entryBoundary,
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
    plugins: { leaf: { rules: { "evaluation-order": evaluationOrder } } },
    rules: { ...ownerBoundary, "leaf/evaluation-order": "error" },
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
