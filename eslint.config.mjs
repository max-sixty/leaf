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
    rules: ownerBoundary,
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
      "skills/leaf/assets/runtime/conversation/model.js",
      "skills/leaf/assets/runtime/conversation/state.js",
    ],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              regex: "^(?!\\.\\./anchor-coordinate\\.js$|\\./identity\\.js$|\\./model\\.js$)",
              message: "Conversation readings depend only on pure record operations.",
            },
          ],
        },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "ImportExpression",
          message: "Conversation readings declare their record dependencies statically.",
        },
      ],
      "no-restricted-globals": [
        "error",
        ...Object.keys(browserGlobals),
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
