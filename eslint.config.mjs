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
    files: ["skills/leaf/assets/leaf.js"],
    rules: {
      ...entryBoundary,
      "no-restricted-syntax": [
        "error",
        ...entryBoundary["no-restricted-syntax"].slice(1),
        {
          selector:
            "ExportNamedDeclaration, ExportDefaultDeclaration, ExportAllDeclaration",
          message: "leaf.js composes and boots the runtime; domain owners export APIs.",
        },
      ],
    },
  },
  {
    files: ["skills/leaf/assets/runtime/**/*.js"],
    rules: ownerBoundary,
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
