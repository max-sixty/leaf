import js from "@eslint/js";
import globals from "globals";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import kernel from "./browser/runtime/kernel-registry.json" with { type: "json" };
import { PAGE_PAINT_ATTRIBUTE } from "./browser/runtime/base/page-paint.js";

const publicRuntimePaths = kernel["$public-modules"].paths.filter((path) =>
  path.startsWith("/runtime/"),
);
const publicRuntimeModules = publicRuntimePaths
  .map((path) => path.slice("/runtime/".length).replaceAll(".", "\\."))
  .join("|");

// The runtime's primitives, by path under `runtime/`: modules that may use the browser
// but import no owner, which the rule naming them below holds.
const runtimePrimitives = [
  "base/anchor-coordinate.js",
  "base/chrome.js",
  "dom/dom-children.js",
  "dom/dom-move.js",
  "dom/focus.js",
  "dom/control-selectors.js",
  "base/inputs.js",
  "base/document-inputs.js",
  "base/pointer.js",
  "base/rendering.js",
  "base/frame-visibility.js",
  "dom/repaint.js",
  "state/root-state.js",
  "state/thread/identity.js",
  "base/ui-marks.js",
];

// The browser's names the layer uses, for `no-undef`: a moved function that lost an
// import must fail the hook rather than bind to `window.*` on the first page that
// reaches it. Only names in use are listed — `open`, `top`, `parent`, `origin`, `escape`
// are locals here, and declaring the browser's copies would hide exactly the lost import
// this rule is for. A new global is added when the hook refuses it.
const browserGlobals = Object.fromEntries(
  [
    "AbortController",
    "AbortSignal",
    "Animation",
    "CSS",
    "CSSAnimation",
    "CSSImportRule",
    "CSSKeyframesRule",
    "CSSLayerBlockRule",
    "CSSScopeRule",
    "CSSStyleRule",
    "CSSStyleSheet",
    "CSSTransition",
    "CharacterData",
    "CommandEvent",
    "CustomEvent",
    "DOMException",
    "DOMParser",
    "DOMPoint",
    "DOMRect",
    "Document",
    "DocumentTimeline",
    "Element",
    "ErrorEvent",
    "Event",
    "EventSource",
    "FileReader",
    "FocusEvent",
    "HTMLAnchorElement",
    "HTMLButtonElement",
    "HTMLCanvasElement",
    "HTMLDetailsElement",
    "HTMLDialogElement",
    "HTMLDivElement",
    "HTMLElement",
    "HTMLFieldSetElement",
    "HTMLIFrameElement",
    "HTMLImageElement",
    "HTMLInputElement",
    "HTMLLabelElement",
    "HTMLLinkElement",
    "HTMLScriptElement",
    "HTMLSelectElement",
    "HTMLSpanElement",
    "HTMLTemplateElement",
    "HTMLTextAreaElement",
    "HTMLVideoElement",
    "Headers",
    "Highlight",
    "ImageData",
    "InputEvent",
    "IntersectionObserver",
    "KeyboardEvent",
    "KeyframeEffect",
    "MessageChannel",
    "MouseEvent",
    "MutationObserver",
    "Node",
    "NodeFilter",
    "NodeList",
    "OffscreenCanvas",
    "PerformanceNavigationTiming",
    "PerformanceObserver",
    "PerformanceResourceTiming",
    "PointerEvent",
    "Range",
    "ResizeObserver",
    "Response",
    "SVGAnimatedLength",
    "SVGElement",
    "SVGGeometryElement",
    "SVGGraphicsElement",
    "SVGImageElement",
    "SVGSVGElement",
    "SVGTextElement",
    "SVGUseElement",
    "ScrollTimeline",
    "ShadowRoot",
    "StaticRange",
    "Text",
    "ToggleEvent",
    "URL",
    "URLSearchParams",
    "WheelEvent",
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
    "reportError",
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

const RENDERING_MESSAGE =
  "Use nextRender, nextFrame, cancelRender, or sizeObserver (runtime/lib/frame-pass.js) so the settled reading counts it.";
const RENDERING_NAMES = [
  "requestAnimationFrame",
  "cancelAnimationFrame",
  "ResizeObserver",
];
// The one of them a package still reaches through runtime/lib/frame-pass.js alone.
const PACKAGE_RENDERING_NAMES = ["ResizeObserver"];
/** @param {string[]} names */
const renderingProperties = (names) =>
  ["window", "globalThis"].flatMap((object) =>
    names.map((property) => ({ object, property, message: RENDERING_MESSAGE })),
  );
const RENDERING_PROPERTIES = renderingProperties(RENDERING_NAMES);
const HISTORY_PROPERTIES = ["pushState", "replaceState"].map((property) => ({
  object: "history",
  property,
  message:
    "Add and rename history entries through runtime/records/history.js (pushEntry, replaceEntry), which owns traversal among them.",
}));
const ID_PROPERTIES = [
  {
    property: "randomUUID",
    message:
      "Mint ids with runtime/base/ids.js: crypto.randomUUID is absent outside a secure context, such as a page `leaf --host` serves over plain HTTP.",
  },
];

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

const entryMessage =
  "A fold test imports the owner it is about, never the page's entry.";

const publicRuntimeImports = {
  paths: [
    {
      name: "/leaf.js",
      message: "Import Leaf capabilities from /runtime/widget-api.js.",
    },
  ],
  patterns: [
    {
      regex: `^/runtime/(?!(?:${publicRuntimeModules})$)`,
      message: "Use the public package API described in module-authoring.md.",
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
};

const publicRuntimeSyntax = [
  {
    selector: 'ImportExpression[source.value="/leaf.js"]',
    message: "Import Leaf capabilities statically from /runtime/widget-api.js.",
  },
  {
    selector: `ImportExpression[source.value=/^\\/runtime\\//]:not(${publicRuntimePaths.map((path) => `[source.value="${path}"]`).join(", ")})`,
    message: "Use the public package API described in module-authoring.md.",
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
];

const publicRuntimeBoundary = {
  "no-restricted-imports": ["error", publicRuntimeImports],
  "no-restricted-syntax": ["error", ...publicRuntimeSyntax],
};

const ownerRuntimeSyntax = [
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
  {
    selector:
      'AssignmentExpression[operator="+="][left.type="MemberExpression"][left.property.name="value"]',
    message:
      "`x.value += 1` reads the signal before writing it, and inside a paint subscribes that paint to its own write; advance a version signal with tick() from state/version-signal.js.",
  },
  {
    selector:
      ":matches(ExportNamedDeclaration, ExportAllDeclaration)[source.value=/(?:^|\\/)lib\\/[^\\/]+$/]",
    message:
      "Nothing re-exports the library: each module that uses a library module imports it by its own path (browser/AGENTS.md, “The library of shared web code”).",
  },
];

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
  "no-restricted-syntax": ["error", ...ownerRuntimeSyntax],
};

// What a module of the library (browser/runtime/lib/) may import: a /vendor/ bundle or
// a module beside it in that flat directory, by a path with no `..`, written or
// percent-encoded, to climb out of either.
const librarySpecifier = "(?:/vendor/(?!.*(?:\\.\\.|%))|\\./[^/\\\\%]+$)";
const LIBRARY_MESSAGE =
  "The library imports only /vendor/ bundles and its own modules (browser/AGENTS.md, “The library of shared web code”): code that needs the runtime is not library code.";

const runtimeRoot = fileURLToPath(new URL("./browser/runtime/", import.meta.url));
const runtimeName = (file) =>
  path.relative(runtimeRoot, file).split(path.sep).join("/");

// The runtime's import layers, top first (`architecture/import-layers`). A module names
// only modules of its own layer and of the layers listed after it, whether it imports
// them or names their types in its JSDoc. The entry points form the top layer and stay
// at the runtime's top level, since pages, packages, the server and the render checks
// load them by served path. Each other layer is a directory of the runtime. The library
// of shared web code (`lib/`) keeps its served path and belongs to the bottom layer.
// A module anywhere else fails too: move it into a layer no higher than any module that
// names it and no lower than any module it names.
//
// When a module names one above it, make the name point down, by passing the value or
// callback in or by moving what it needs to a layer below both. Where a module types a
// collaborator it is handed by its provider's type, it declares the members it calls
// instead, as a typedef beside it; the provider meets that typedef, and the type check
// checks it where the provider is passed in. Where the module itself stands in the
// wrong layer, move the module instead.
const runtimeLayers = [
  {
    name: "Entry points and diagnostics",
    paths: [
      "bootstrap.js",
      "prepaint.js",
      "check-api.js",
      "validation.js",
      "widget-api.js",
      "effect-widget.js",
      "widget-services.js",
      "portable-api.js",
      "stage-integration.js",
      "age.js",
    ],
  },
  { name: "Floating panel, page dialogs and page keys", paths: ["panel/"] },
  { name: "Annotation presentation and composing", paths: ["annotations/"] },
  { name: "Application and widget host", paths: ["host/"] },
  {
    name: "Page features: annotation inventory, contributions, version travel",
    paths: ["features/"],
  },
  { name: "Records, history and undo", paths: ["records/"] },
  { name: "Page readings, places and paint", paths: ["readings/"] },
  { name: "Transport, errors and notices", paths: ["transport/"] },
  { name: "DOM, geometry, focus and the key register", paths: ["dom/"] },
  { name: "State and registry", paths: ["state/"] },
  { name: "Primitives and the library", paths: ["base/", "lib/"] },
];
// A layer naming a module that no longer exists would place a later file of that name,
// so each name is checked against the directory as the config loads.
for (const { paths } of runtimeLayers)
  for (const name of paths)
    if (!fs.existsSync(path.join(runtimeRoot, name)))
      throw new Error(`eslint.config.mjs places a missing runtime module: ${name}`);
// The layer a module stands in, by its path under `runtime/`: a path names a file
// exactly and a directory by everything under it.
const layerOf = (name) =>
  runtimeLayers.findIndex(({ paths }) =>
    paths.some((place) =>
      place.endsWith("/") ? name.startsWith(place) : name === place,
    ),
  );
// The modules a module's JSDoc names, read as TypeScript reads them: from each `/** … */`
// block, with each line's leading `*` set aside, every `import` `(` string `)`, with any
// whitespace between the tokens, and every `@import … from "…"`, whose braces may span
// lines. An `@example` holds code rather than types, up to the next tag, and other
// comments name nothing. TypeScript resolves a type's specifier that names no file by
// trying it with `.js` and with `.d.ts`. The rule reads runtime modules alone, so the
// ambient declarations of `browser/types/` are outside what it reads, and a type a
// global names, such as an element's `lfPreview` or a tag in `HTMLElementTagNameMap`,
// may stand in any layer.
const JSDOC_IMPORTS = [
  /\bimport\s*\(\s*(["'])([^"'\n]*)\1\s*\)/gu,
  /@import\b[^@]*?\bfrom\s*(["'])([^"'\n]*)\1/gu,
];
/** @param {{type: string, value: string}} comment */
const jsdocNames = (comment) => {
  if (comment.type !== "Block" || !comment.value.startsWith("*")) return [];
  const text = comment.value
    .replace(/^[ \t]*\*/gmu, "")
    .replace(/@example\b[\s\S]*?(?=\s@\S|$)/gu, "");
  return JSDOC_IMPORTS.flatMap((pattern) =>
    [...text.matchAll(pattern)].map(([, , specifier]) => specifier),
  );
};
/** @param {string} name */
const typeFile = (name) =>
  [name, `${name}.js`, `${name}.d.ts`].find((candidate) =>
    fs.existsSync(path.join(runtimeRoot, candidate)),
  ) ?? name;
// The runtime module a specifier names, by its path under `runtime/`, resolved as the
// browser resolves it from the module's served URL (`/runtime/…`); null where it names
// none. A bare specifier is an import map's to resolve, one that doesn't parse as a URL
// is the browser's and the type check's to refuse, and a path outside `/runtime/`, such
// as a `/vendor/` bundle, a `/checks/` probe or browser/types/, holds no runtime module.
// JSON is data.
const SERVED = new URL("https://page.invalid/runtime/");
const servedName = (file, specifier) => {
  if (!/^\.{0,2}\//u.test(specifier) || !URL.canParse(specifier, new URL(file, SERVED)))
    return null;
  const url = new URL(specifier, new URL(file, SERVED));
  if (url.origin !== SERVED.origin || !url.pathname.startsWith(SERVED.pathname))
    return null;
  const name = url.pathname.slice(SERVED.pathname.length);
  let decoded = name;
  try {
    decoded = decodeURIComponent(name);
  } catch {
    // A malformed escape is served as written.
  }
  return decoded.endsWith(".json") ? null : decoded;
};
export const importLayersRule = {
  meta: { type: "problem", schema: [] },
  create(context) {
    const file = runtimeName(context.filename);
    const here = layerOf(file);
    const placed = (name) => runtimeLayers[name].name;
    /** @param {{node?: unknown, loc?: unknown}} at @param {string} specifier */
    const check = (at, specifier, type = false) => {
      const served = here < 0 ? null : servedName(file, specifier);
      if (served === null) return;
      const there = layerOf(type ? typeFile(served) : served);
      if (there < 0 || there >= here) return;
      context.report({
        ...at,
        message: `${placed(here)} names only its own layer and the layers below it (\`runtimeLayers\`, eslint.config.mjs); ${specifier} stands in ${placed(there)}.`,
      });
    };
    /** @param {any} node */
    const source = (node) =>
      node?.type === "Literal"
        ? node.value
        : node?.type === "TemplateLiteral" && node.expressions.length === 0
          ? node.quasis[0].value.cooked
          : null;
    /** @param {any} node */
    const named = (node) => {
      const specifier = source(node.source);
      if (typeof specifier === "string") check({ node }, specifier);
    };
    return {
      Program(node) {
        if (here < 0)
          context.report({
            node,
            message: `${file} stands in no layer: it is an entry point or stands in a layer's directory (\`runtimeLayers\`, eslint.config.mjs).`,
          });
        for (const comment of context.sourceCode.getAllComments())
          for (const specifier of jsdocNames(comment))
            check({ loc: comment.loc }, specifier, true);
      },
      ImportDeclaration: named,
      ImportExpression: named,
      ExportNamedDeclaration: (node) => node.source && named(node),
      ExportAllDeclaration: named,
    };
  },
};

const pagePaintAttributeValues = new Map(Object.entries(PAGE_PAINT_ATTRIBUTE));

// The user’s current location, and what moved them there, is dom/focus.js's one reading
// (`onCurrentLocation`). A `focusin` or `focusout` listener hears nothing of a move between two
// nodes of one shadow tree beneath it, and a reader that tells the runtime's returns or
// the keyboard's arrivals apart for itself answers a question dom/focus.js already answers.
// So the two event names appear nowhere else, in a listener, a list of event types, a
// comparison or a Lit binding, and `focus` and `blur` are not heard on the document or
// captured anywhere, which would hear every element beneath. An element's own `focus`
// or `blur`, and the window's, which is the system's focus, are other questions. The option names,
// by path from the repository root, the files that may still name a focus event, each
// with the reason in the config that grants it.
const repoRoot = path.dirname(fileURLToPath(import.meta.url));
const CURRENT_LOCATION_MESSAGE =
  "Read the user’s current location from onCurrentLocation (runtime/dom/focus.js): a focusin or focusout listener misses moves inside a shadow tree beneath it and guesses its own cause.";
const currentLocationListenersRule = {
  meta: {
    type: "problem",
    schema: [{ type: "object", additionalProperties: { type: "array" } }],
  },
  create(context) {
    const file = path
      .relative(repoRoot, context.filename ?? context.getFilename())
      .split(path.sep)
      .join("/");
    const allowed = new Set(context.options[0]?.[file] ?? []);
    const named = (node, type) => {
      if (!allowed.has(type))
        context.report({ node, message: CURRENT_LOCATION_MESSAGE });
    };
    // Capturing `focus` or `blur` on any node hears every element beneath it, the
    // window's included.
    const capturing = (options) =>
      (options?.type === "Literal" && options.value === true) ||
      (options?.type === "ObjectExpression" &&
        options.properties.some(
          (property) =>
            property.key?.name === "capture" &&
            property.value.type === "Literal" &&
            property.value.value === true,
        ));
    const documentReceiver = (callee) =>
      callee.type === "MemberExpression" &&
      callee.object.type === "Identifier" &&
      callee.object.name === "document";
    return {
      Literal(node) {
        if (node.value === "focusin" || node.value === "focusout")
          named(node, node.value);
      },
      TemplateElement(node) {
        for (const [, type] of node.value.raw.matchAll(/@(focusin|focusout)\s*=/gu))
          named(node, type);
      },
      CallExpression(node) {
        const { callee } = node;
        const method =
          callee.type === "MemberExpression" && !callee.computed
            ? callee.property.name
            : null;
        const type = node.arguments[0];
        if (
          method === "addEventListener" &&
          (documentReceiver(callee) || capturing(node.arguments[2])) &&
          type?.type === "Literal" &&
          (type.value === "focus" || type.value === "blur")
        )
          named(node, type.value);
      },
    };
  },
};

// Every focus the runtime and the packages place says what moved the user there
// (`focusDestination(node, cause)` in dom/focus.js), since that call is the only place that
// knows whether it is a route or a return, and each reader of where they stand acts on
// the word. A plain `focus()` publishes as the user's own move. The rule knows the
// element method by its shape, no argument or an options object, so a method of the same
// name taking a key, as a contribution's `focus(entryKey, cause)` does, is another
// question. Each call to `focusDestination` names its cause, and the function is not
// handed around as a value, where a caller would call it without one. The option names
// the files that may still call `focus()`: the owner, and an element whose own `focus()`
// hands on to the editor inside it.
const PLACEMENT_MESSAGE =
  "Put the user on an element with focusDestination(node, cause) (runtime/dom/focus.js): a plain focus() publishes as the user's own move, so a return reads as one.";
const placementsRule = {
  meta: { type: "problem", schema: [{ type: "array", items: { type: "string" } }] },
  create(context) {
    const file = path
      .relative(repoRoot, context.filename ?? context.getFilename())
      .split(path.sep)
      .join("/");
    const owner = (context.options[0] ?? []).includes(file);
    const optionsLike = (arg) =>
      arg.type === "ObjectExpression" ||
      arg.type === "SpreadElement" ||
      (arg.type === "Identifier" && /^opt/u.test(arg.name));
    // CodeMirror's imported state effect asks its view's scroll handler to reveal;
    // it is not the browser method. Resolve the binding to an `EditorView` a vendored
    // bundle exports, the runtime's CodeMirror or a package's own, so aliases work and
    // a local element merely named EditorView does not gain an exception.
    const editorReveal = (callee) => {
      if (callee.object.type !== "Identifier") return false;
      for (
        let scope = context.sourceCode.getScope(callee);
        scope;
        scope = scope.upper
      ) {
        const binding = scope.set.get(callee.object.name);
        if (!binding) continue;
        return binding.defs.some(
          (definition) =>
            definition.type === "ImportBinding" &&
            definition.node.imported?.name === "EditorView" &&
            /(?:^|\/)vendor\/[^/]+\.js$/u.test(
              definition.parent.source.value,
            ),
        );
      }
      return false;
    };
    return {
      CallExpression(node) {
        const { callee, arguments: args } = node;
        if (callee.type === "MemberExpression" && !callee.computed) {
          if (
            ["scrollIntoView", "scrollIntoViewIfNeeded"].includes(
              callee.property.name,
            ) &&
            !(callee.property.name === "scrollIntoView" && editorReveal(callee))
          )
            context.report({
              node,
              message:
                "Reveal with scrollIntoView(node, options) from runtime/readings/landing-scroll.js: native reveal can scroll the containing page.",
            });
        }
        if (callee.type === "Identifier" && callee.name === "focusDestination") {
          if (args.length < 2)
            context.report({ node, message: "focusDestination names its cause." });
          return;
        }
        if (
          owner ||
          callee.type !== "MemberExpression" ||
          callee.computed ||
          callee.property.name !== "focus"
        )
          return;
        if (args.length === 0 || (args.length === 1 && optionsLike(args[0])))
          context.report({ node, message: PLACEMENT_MESSAGE });
      },
      Identifier(node) {
        if (node.name !== "focusDestination") return;
        const { parent } = node;
        if (
          (parent.type === "CallExpression" && parent.callee === node) ||
          parent.type === "ImportSpecifier" ||
          parent.type === "ExportSpecifier" ||
          (parent.type === "FunctionDeclaration" && parent.id === node)
        )
          return;
        context.report({
          node,
          message: "Call focusDestination with its cause rather than passing it on.",
        });
      },
    };
  },
};

// The runtime opens and closes its native layers through `showNativeLayer` and
// `closeNativeLayer` (dom/keyboard/layer-stack.js), which inside a live sample keep the
// browser's focusing steps from taking focus from the page around it or scrolling that
// page. The option names the owner.
const nativeLayersRule = {
  meta: { type: "problem", schema: [{ type: "array", items: { type: "string" } }] },
  create(context) {
    const file = path
      .relative(repoRoot, context.filename ?? context.getFilename())
      .split(path.sep)
      .join("/");
    if ((context.options[0] ?? []).includes(file)) return {};
    return {
      CallExpression(node) {
        const { callee } = node;
        if (
          callee.type === "MemberExpression" &&
          !callee.computed &&
          ["showModal", "showPopover", "hidePopover"].includes(callee.property.name)
        )
          context.report({
            node,
            message:
              "Use showNativeLayer(layer, options) or closeNativeLayer(layer): native focus must respect the document holding input.",
          });
      },
    };
  },
};

// Where the user stands is read through `focused()` in dom/focus.js, or `focused(tree)` for
// the node representing it in one tree, as `tree.activeElement` retargets focus. A raw
// `activeElement`, of the document or of a shadow root, misses a label press that holds
// the user on the element they stood on, and the document's stops at the host of the
// shadow tree they stand in, so a copy of that reading answers differently from every
// other at exactly those edges. A frame's `contentDocument.activeElement` is the frame
// page's own question. The option names the files that may still read it.
const CURRENT_LOCATION_READ_MESSAGE =
  "Read the user’s current location with focused() (runtime/dom/focus.js), or focused(tree) for the node representing it in one document or shadow root: a raw activeElement misses a label press holding them and focus inside shadow trees.";
export const currentLocationReadsRule = {
  meta: { type: "problem", schema: [{ type: "array", items: { type: "string" } }] },
  create(context) {
    const file = path
      .relative(repoRoot, context.filename ?? context.getFilename())
      .split(path.sep)
      .join("/");
    if ((context.options[0] ?? []).includes(file)) return {};
    return {
      MemberExpression(node) {
        if (
          !node.computed &&
          node.property.name === "activeElement" &&
          !(
            node.object.type === "MemberExpression" &&
            !node.object.computed &&
            node.object.property.name === "contentDocument"
          )
        )
          context.report({ node, message: CURRENT_LOCATION_READ_MESSAGE });
      },
      // `scope.contains(focused())`, in either reading, stops at a shadow root and misses a
      // node slotted into the scope, where `currentLocationIn(scope)` climbs as rendered.
      CallExpression(node) {
        const { callee, arguments: args } = node;
        if (
          callee.type === "MemberExpression" &&
          !callee.computed &&
          callee.property.name === "contains" &&
          args.length === 1 &&
          args[0].type === "CallExpression" &&
          args[0].callee.type === "Identifier" &&
          args[0].callee.name === "focused"
        )
          context.report({
            node,
            message:
              "Ask whether the user’s current location is in a scope with currentLocationIn(scope) (runtime/dom/focus.js): contains() stops at a shadow root.",
          });
      },
    };
  },
};

// Whether a node is an open native layer, or stands in one, is asked of lib/shadow-tree.js
// (`nativeLayerKind`, `isNativeLayer`, `nativeLayerHolding`), and which are open of dom/keyboard/layer-stack.js
// (`nativeLayers`). A selector naming the open state answers it again, and the copies
// drift: a `dialog[open]` read once counted the auxiliary envelope, a nonmodal dialog
// that is always open, as a layer. A reader that also wants a nonmodal dialog asks the
// dialog's own `open`. The rule reads the selector a `matches`, `closest` or
// `querySelector(All)` call is given; the option names the owner.
const OPEN_LAYER_SELECTOR = /:popover-open|:modal\b|dialog\[open\]/u;
const SELECTOR_METHODS = new Set([
  "matches",
  "closest",
  "querySelector",
  "querySelectorAll",
]);
export const openLayersRule = {
  meta: { type: "problem", schema: [{ type: "array", items: { type: "string" } }] },
  create(context) {
    const file = path
      .relative(repoRoot, context.filename ?? context.getFilename())
      .split(path.sep)
      .join("/");
    if ((context.options[0] ?? []).includes(file)) return {};
    return {
      CallExpression(node) {
        const { callee } = node;
        const [selector] = node.arguments;
        if (
          callee.type !== "MemberExpression" ||
          callee.computed ||
          !SELECTOR_METHODS.has(callee.property.name) ||
          !selector
        )
          return;
        const text =
          selector.type === "Literal"
            ? selector.value
            : selector.type === "TemplateLiteral"
              ? selector.quasis.map((quasi) => quasi.value.cooked).join("")
              : null;
        if (typeof text === "string" && OPEN_LAYER_SELECTOR.test(text))
          context.report({
            node,
            message:
              "Ask lib/shadow-tree.js whether a node is an open layer or stands in one (nativeLayerKind, isNativeLayer, nativeLayerHolding) rather than selecting the open state.",
          });
      },
    };
  },
};

// A script moves a box through the scroll owners: a reveal through readings/landing-scroll.js's
// `scrollIntoView`, bounded `within` the one box that may move, an end through
// `scrollToEnd` and a relative move through `moveScrollerBy` (dom/scrolling.js). A sum
// written into `scrollTop` or `scrollLeft` is how a reveal is hand-rolled, with its own
// reading of the band and the edge, so the rule refuses every assignment to either; a
// script that sets an offset outright says so with `scrollTo`, which the runtime hears
// as a script's write whoever makes it (runtime/dom/arrivals.js, `heardWrite`). The option
// names the files that may still assign one.
//
// Such a call says how it moves the box. With no `behavior`, the box's own
// `scroll-behavior` decides, which a page is free to set to smooth on the box it
// scrolls, and a writer that reads the page just after its write, as a tab set
// putting a view back at its place does, would read it before the glide moved it. The
// rule reads a `scrollTo`, `scroll` or `scrollBy` call, on a box or bare, that writes
// its options out without one, or gives two offsets, which can't name one; options a
// call is handed are their writer's.
export const scrollWritesRule = {
  meta: { type: "problem", schema: [{ type: "array", items: { type: "string" } }] },
  create(context) {
    const file = path
      .relative(repoRoot, context.filename ?? context.getFilename())
      .split(path.sep)
      .join("/");
    const assigns = (context.options[0] ?? []).includes(file);
    return {
      AssignmentExpression({ left }) {
        if (
          !assigns &&
          left.type === "MemberExpression" &&
          !left.computed &&
          ["scrollTop", "scrollLeft"].includes(left.property.name)
        )
          context.report({
            node: left,
            message:
              "Reveal with scrollIntoView(node, {block, within}) from runtime/readings/landing-scroll.js, or set an offset outright, a package with scrollTo({top, left, behavior}) and the runtime with setScroll (runtime/dom/arrivals.js), scrollToEnd or moveScrollerBy (runtime/dom/scrolling.js), rather than assigning a scroll offset.",
          });
      },
      CallExpression(node) {
        const { callee, arguments: args } = node;
        const called =
          callee.type === "Identifier"
            ? callee.name
            : callee.type === "MemberExpression" && !callee.computed
              ? callee.property.name
              : null;
        if (!["scrollTo", "scroll", "scrollBy"].includes(called)) return;
        const [options] = args;
        const unsaid =
          args.length === 2 ||
          (options?.type === "ObjectExpression" &&
            !options.properties.some(
              (property) =>
                property.type === "SpreadElement" ||
                (!property.computed &&
                  (property.key.name ?? property.key.value) === "behavior"),
            ));
        if (unsaid)
          context.report({
            node,
            message:
              'Say how the write moves the box, as scrollTo({top, left, behavior: "instant"}) does: left out, the box\'s own scroll-behavior decides, which a page may set to smooth.',
          });
      },
    };
  },
};

// The runtime hears a scroll's end through `watchScrollEnds` (runtime/dom/arrivals.js),
// which ends each box's scroll once however many frames a script writes it in; a
// listener of its own hears every frame of a glide as a scroll that ended. The option
// names the runtime files that may listen.
const scrollEndsRule = {
  meta: { type: "problem", schema: [{ type: "array", items: { type: "string" } }] },
  create(context) {
    const file = path
      .relative(repoRoot, context.filename ?? context.getFilename())
      .split(path.sep)
      .join("/");
    if (
      !file.startsWith("browser/runtime/") ||
      (context.options[0] ?? []).includes(file)
    )
      return {};
    return {
      CallExpression(node) {
        const [type] = node.arguments;
        if (
          node.callee.type === "MemberExpression" &&
          !node.callee.computed &&
          node.callee.property.name === "addEventListener" &&
          type?.type === "Literal" &&
          type.value === "scrollend"
        )
          context.report({
            node,
            message:
              "Hear a scroll's end with watchScrollEnds (runtime/dom/arrivals.js), which ends a glide once rather than on each of its frames.",
          });
      },
    };
  },
};

// A node that already stands somewhere moves through `move(parent, node, before)`
// (runtime/dom/dom-move.js), or `setChildren` beside it, which keeps the user's focus, caret
// and native state in it; a plain insertion takes the node out first, which blurs it.
// Which nodes stand somewhere is not visible in source, so the rule refuses what it can
// read. `insertBefore` and `moveBefore` are the mover's own calls, refused unless the
// node is made in the same expression. `append`, `prepend`, `before`, `after`,
// `appendChild`, `replaceChildren` and `replaceWith` mostly place new nodes, so they are
// refused only where a condition around them asks where the node stands (its parent or
// a sibling, or whether something contains it): a node that may stand elsewhere already.
// The option names the files that may still call the platform's movers.
const MOVE_MESSAGE =
  "Place a node that may already stand somewhere with move(parent, node, before) or setChildren (runtime/dom/dom-move.js, dom/dom-children.js; widget-api.js in a package): a plain insertion blurs it and drops its caret.";
const MADE = new Set([
  "createElement",
  "createElementNS",
  "createTextNode",
  "createComment",
  "createDocumentFragment",
  "cloneNode",
  "importNode",
]);
const INSERTS = new Set([
  "append",
  "prepend",
  "before",
  "after",
  "appendChild",
  "replaceChildren",
  "replaceWith",
]);
const PLACEMENT = new Set([
  "parentNode",
  "parentElement",
  "nextSibling",
  "previousSibling",
  "nextElementSibling",
  "previousElementSibling",
]);
export const movesRule = {
  meta: { type: "problem", schema: [{ type: "array", items: { type: "string" } }] },
  create(context) {
    const file = path
      .relative(repoRoot, context.filename ?? context.getFilename())
      .split(path.sep)
      .join("/");
    if ((context.options[0] ?? []).includes(file)) return {};
    const text = (node) => context.sourceCode.getText(node);
    const method = (node) =>
      node.callee.type === "MemberExpression" && !node.callee.computed
        ? node.callee.property.name
        : null;
    const placementOf = (node) =>
      node.type === "MemberExpression" &&
      !node.computed &&
      PLACEMENT.has(node.property.name);
    // Whether `test` asks where one of `names` stands.
    const asksWhere = (test, names) => {
      if (!test || typeof test.type !== "string") return false;
      if (placementOf(test) && names.has(text(test.object))) return true;
      if (
        test.type === "BinaryExpression" &&
        [test.left, test.right].some((side) => names.has(text(side))) &&
        [test.left, test.right].some(placementOf)
      )
        return true;
      if (
        test.type === "CallExpression" &&
        method(test) === "contains" &&
        test.arguments.some((argument) => names.has(text(argument)))
      )
        return true;
      return Object.entries(test).some(
        ([key, value]) =>
          key !== "parent" &&
          (Array.isArray(value)
            ? value.some((each) => asksWhere(each, names))
            : asksWhere(value, names)),
      );
    };
    // The conditions the call runs under, within its own function.
    const conditions = function* (node) {
      for (let at = node; at.parent && !isFunction(at.parent); at = at.parent) {
        const { parent } = at;
        if (
          (parent.type === "IfStatement" || parent.type === "ConditionalExpression") &&
          parent.test !== at
        )
          yield parent.test;
        else if (parent.type === "LogicalExpression" && parent.right === at)
          yield parent.left;
      }
    };
    return {
      CallExpression(node) {
        const name = method(node);
        if (name === "insertBefore" || name === "moveBefore") {
          const [inserted] = node.arguments;
          if (!(inserted?.type === "CallExpression" && MADE.has(method(inserted))))
            context.report({ node, message: MOVE_MESSAGE });
          return;
        }
        if (!INSERTS.has(name)) return;
        const names = new Set(
          node.arguments
            .filter((argument) => argument.type !== "SpreadElement")
            .map(text),
        );
        for (const test of conditions(node))
          if (asksWhere(test, names)) {
            context.report({ node, message: MOVE_MESSAGE });
            return;
          }
      },
    };
  },
};

// A layer hands the user back as it closes in one act (`closeLayer(close, land)` in
// dom/focus.js), so the platform's own hand-back and the owner's reach readers once, as where
// the user ends up. A return made anywhere else is a layer return beside it, which
// readers hear as a second move and holds read as a newer word. The rule admits
// `handBack(...)` only in a landing's own body: the function passed as a close's `land`,
// or one the kernel's `layerLanding(...)` wraps, which a closer builds away from the call
// and which throws if it runs at any other time. A landing is synchronous, since what it
// does after an await or in a callback happens beside the close. The `close` argument
// hides the layer and places nothing, so a placement written there is refused too. So is a
// `focusDestination(..., "return")` outside a landing where a statement before it in its
// function hides something by the platform's means, a layer return spelled out by hand;
// a hide through an owner's own function, as `showFab(null)`, is out of the rule's
// sight. `letGo` lands the user on the page by a route, as `g p` does, so it is no layer
// return of itself. The option names the files that may still return the user directly.
const LAYER_RETURN_MESSAGE =
  "Hand the user back as the layer closes, in the body of closeLayer(close, land)'s land, or of a layerLanding (runtime/dom/focus.js): a return beside it reaches readers as a second move.";
const CLOSE_PLACES_MESSAGE =
  "closeLayer's close hides the layer and places nothing; put the user in its land (runtime/dom/focus.js).";
const HIDING_CALLS = new Set(["hide", "hidePopover", "close"]);
// Whether `node` hides something by the platform's own means: a dialog's or popover's
// close, `hidden = true`, or a style that takes the box out of view. A function it
// defines runs later, so what that does is not this statement's.
function hidesSomething(node) {
  if (!node || typeof node.type !== "string" || /Function/u.test(node.type))
    return false;
  if (
    node.type === "CallExpression" &&
    node.callee.type === "MemberExpression" &&
    !node.callee.computed &&
    HIDING_CALLS.has(node.callee.property.name)
  )
    return true;
  if (
    node.type === "AssignmentExpression" &&
    node.left.type === "MemberExpression" &&
    !node.left.computed &&
    ((node.left.property.name === "hidden" && node.right.value === true) ||
      (node.left.property.name === "visibility" && node.right.value === "hidden") ||
      (node.left.property.name === "display" && node.right.value === "none"))
  )
    return true;
  return Object.entries(node).some(
    ([key, value]) =>
      key !== "parent" &&
      (Array.isArray(value) ? value.some(hidesSomething) : hidesSomething(value)),
  );
}
const isCall = (node, name) =>
  node?.type === "CallExpression" &&
  ((node.callee.type === "Identifier" && node.callee.name === name) ||
    (node.callee.type === "MemberExpression" &&
      !node.callee.computed &&
      node.callee.property.name === name));
const isFunction = (node) => /Function/u.test(node.type);
// The function `node` runs in, if any.
const enclosingFunction = (node) => {
  for (let at = node.parent; at; at = at.parent) if (isFunction(at)) return at;
  return null;
};
// The argument a function value is passed as, through the choices that pick it
// (`open && (() => …)`, `currentLocation ? () => … : letGo`).
const argumentOf = (fn) => {
  let at = fn;
  while (
    at.parent.type === "LogicalExpression" ||
    (at.parent.type === "ConditionalExpression" && at.parent.test !== at)
  )
    at = at.parent;
  const call = at.parent;
  return call.type === "CallExpression"
    ? { call, index: call.arguments.indexOf(at) }
    : null;
};
export const layerReturnsRule = {
  meta: { type: "problem", schema: [{ type: "array", items: { type: "string" } }] },
  create(context) {
    const file = path
      .relative(repoRoot, context.filename ?? context.getFilename())
      .split(path.sep)
      .join("/");
    if ((context.options[0] ?? []).includes(file)) return {};
    // Whether the function `node` runs in is a landing: a close's `land` or a function
    // `layerLanding` wraps, and synchronous.
    const landing = (node) => {
      const fn = enclosingFunction(node);
      if (!fn || fn.async) return false;
      const passed = argumentOf(fn);
      return Boolean(
        passed &&
        ((isCall(passed.call, "closeLayer") && passed.index === 1) ||
          (isCall(passed.call, "layerLanding") && passed.index === 0)),
      );
    };
    // Whether the function `node` runs in is a close's `close`.
    const inClose = (node) => {
      const fn = enclosingFunction(node);
      const passed = fn && argumentOf(fn);
      return Boolean(passed && isCall(passed.call, "closeLayer") && passed.index === 0);
    };
    // Whether a statement before `node` in its own function hides something.
    const afterHide = (node) => {
      for (let at = node; at.parent; at = at.parent) {
        const { parent } = at;
        if (isFunction(parent)) return false;
        const run =
          parent.type === "SequenceExpression"
            ? parent.expressions
            : parent.type === "SwitchCase"
              ? parent.consequent
              : Array.isArray(parent.body)
                ? parent.body
                : null;
        if (run?.slice(0, run.indexOf(at)).some(hidesSomething)) return true;
      }
      return false;
    };
    // The local names each placement goes by in this file, an alias included.
    const names = {
      handBack: new Set(["handBack"]),
      focusDestination: new Set(["focusDestination"]),
      letGo: new Set(["letGo"]),
    };
    const calls = (node, which) =>
      (node.callee.type === "Identifier" && names[which].has(node.callee.name)) ||
      (node.callee.type === "MemberExpression" &&
        !node.callee.computed &&
        node.callee.property.name === which);
    return {
      ImportSpecifier(node) {
        names[node.imported.name]?.add(node.local.name);
      },
      CallExpression(node) {
        const handsBack = calls(node, "handBack");
        const places =
          handsBack || calls(node, "focusDestination") || calls(node, "letGo");
        if (places && inClose(node)) {
          context.report({ node, message: CLOSE_PLACES_MESSAGE });
          return;
        }
        const returnsAfterHide =
          calls(node, "focusDestination") &&
          node.arguments[1]?.value === "return" &&
          afterHide(node);
        if ((handsBack || returnsAfterHide) && !landing(node))
          context.report({ node, message: LAYER_RETURN_MESSAGE });
      },
      // Handed on as a value, it is called where no landing frames it.
      Identifier(node) {
        if (!names.handBack.has(node.name)) return;
        const { parent } = node;
        if (
          (parent.type === "CallExpression" && parent.callee === node) ||
          parent.type === "ImportSpecifier" ||
          parent.type === "ExportSpecifier" ||
          (parent.type === "MemberExpression" && parent.property === node) ||
          (parent.type === "FunctionDeclaration" && parent.id === node)
        )
          return;
        context.report({ node, message: LAYER_RETURN_MESSAGE });
      },
    };
  },
};

// A module that awaits outside every function, anywhere in a rolldown build, turns off
// the build's chunk optimization (`mergeCommonChunks`, `avoidRedundantChunkLoads`) for
// every module in it, since that is how rolldown keeps a waiting module's execution
// order, and the build says nothing. When leaf.js awaited at its top level, every page
// loaded eleven more kernel chunks before it presented. Both builds compile from this
// tree: the kernel from `browser/`, and the website's rebundle from each published
// layer, which adds the packages' widgets and an example's own. It is a rule of its own
// rather than a `no-restricted-syntax` selector because a file takes that rule's options
// from the last block matching it, and the runtime's blocks set their own.
const topLevelAwaitRule = {
  meta: { type: "problem", schema: [] },
  create(context) {
    const report = (node) => {
      for (let scope = node.parent; scope; scope = scope.parent)
        if (/Function/u.test(scope.type)) return;
      context.report({
        node,
        message:
          "A top-level await turns off the bundler's chunk merging for the whole build; await inside a function the module calls.",
      });
    };
    return {
      AwaitExpression: report,
      "ForOfStatement[await=true]": report,
      'VariableDeclaration[kind="await using"]': report,
    };
  },
};

// A notice's or an error's words name no key: the step they point to is a press the
// panel's field offers (panel/field-readings.js, `press`). The rule reads every string a
// module writes for the form such words took before, a dash or a semicolon and then a
// shortcut, a character or `g` and one, doing something ("— v shows them", "; g i
// resumes it"), past a count or the article ("— 3 changes", "— a process exited"). It
// catches that form, not every way of spelling a key.
const SPELLED_KEY = /(?:—|;)\s+(?:g\s+)?[^\s\daAI]\s+[a-z]+s\b/u;
export const spelledKeysRule = {
  meta: { type: "problem", schema: [] },
  create(context) {
    /** @param {any} node @param {unknown} text */
    const check = (node, text) => {
      if (typeof text === "string" && SPELLED_KEY.test(text))
        context.report({
          node,
          message:
            "Offer the step as a press (transport/notifications.js, `press`; transport/errors.js), or in an announcement say its key through `saying` (dom/keyboard/control-keys.js), which a package's `lf-announce` reaches by giving its rows (`{words, rows}`), rather than spelling it in the words: both name a key only while it would work.",
        });
    };
    return {
      Literal: (node) => check(node, node.value),
      TemplateElement: (node) => check(node, node.value.cooked),
    };
  },
};

const architecturePlugin = {
  rules: {
    "current-location-listeners": currentLocationListenersRule,
    placements: placementsRule,
    "native-layers": nativeLayersRule,
    "scroll-writes": scrollWritesRule,
    "scroll-ends": scrollEndsRule,
    "current-location-reads": currentLocationReadsRule,
    "open-layers": openLayersRule,
    moves: movesRule,
    "layer-returns": layerReturnsRule,
    "top-level-await": topLevelAwaitRule,
    "spelled-keys": spelledKeysRule,
    "import-layers": importLayersRule,
    "root-state-ownership": {
      meta: { type: "problem", schema: [] },
      create(context) {
        const file = runtimeName(context.filename ?? context.getFilename());
        // The bootstrap and the prepaint run before the module graph and write only
        // what the first paint needs, before any authored revision has replaced the
        // root's attributes. state/root-state.js is the sole mutation boundary after that.
        if (["bootstrap.js", "prepaint.js", "state/root-state.js"].includes(file))
          return {};
        const source = context.sourceCode ?? context.getSourceCode();
        const pagePaintAttributes = pagePaintAttributeValues;
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
          const definition = found.defs.find(({ type }) => type === "Variable");
          if (!definition?.node.init) return null;
          if (
            found.references.some((reference) => reference.isWrite() && !reference.init)
          )
            return null;
          if (definition.node.id.type === "Identifier") return definition.node.init;
          if (definition.node.id.type !== "ObjectPattern") return null;
          const property = definition.node.id.properties.find(
            (candidate) =>
              candidate.type === "Property" &&
              candidate.value.type === "Identifier" &&
              candidate.value.name === node.name,
          );
          if (!property) return null;
          const literalKey =
            property.key.type === "Literal" && typeof property.key.value === "string";
          if (property.computed && !literalKey) return null;
          return {
            type: "MemberExpression",
            object: definition.node.init,
            property: property.key,
            computed: property.computed || literalKey,
          };
        };
        const staticString = (node, seen = new Set()) => {
          if (node?.type === "Literal" && typeof node.value === "string")
            return node.value;
          if (node?.type === "TemplateLiteral" && node.expressions.length === 0)
            return node.quasis[0].value.cooked;
          if (node?.type === "Identifier") {
            const initial = initialValue(node, seen);
            return initial ? staticString(initial, seen) : null;
          }
          return null;
        };
        const memberName = (node) =>
          node?.type === "MemberExpression"
            ? node.computed
              ? staticString(node.property)
              : node.property.name
            : null;
        const importsPagePaintAttributes = (node) => {
          const found = variable(node);
          return Boolean(
            found?.defs.some(
              (definition) =>
                definition.type === "ImportBinding" &&
                definition.node.type === "ImportSpecifier" &&
                definition.node.imported.name === "PAGE_PAINT_ATTRIBUTE" &&
                /(?:^|\/)page-paint\.js$/u.test(definition.parent.source.value),
            ),
          );
        };
        const isPagePaintAttributeRegistry = (node, seen = new Set()) => {
          if (node?.type === "ChainExpression")
            return isPagePaintAttributeRegistry(node.expression, seen);
          if (node?.type !== "Identifier") return false;
          if (importsPagePaintAttributes(node)) return true;
          const initial = initialValue(node, seen);
          return initial ? isPagePaintAttributeRegistry(initial, seen) : false;
        };
        const pagePaintAttributeValue = (node, seen = new Set()) => {
          if (node?.type === "ChainExpression")
            return pagePaintAttributeValue(node.expression, seen);
          if (node?.type === "Identifier") {
            const initial = initialValue(node, seen);
            return initial ? pagePaintAttributeValue(initial, seen) : null;
          }
          const name = memberName(node);
          return name !== null && isPagePaintAttributeRegistry(node.object, seen)
            ? (pagePaintAttributes.get(name) ?? null)
            : null;
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
        const isRootFacade = (node, name, seen = new Set()) => {
          if (node?.type === "ChainExpression")
            return isRootFacade(node.expression, name, seen);
          if (node?.type === "Identifier") {
            const initial = initialValue(node, seen);
            return initial ? isRootFacade(initial, name, seen) : false;
          }
          return (
            node?.type === "MemberExpression" &&
            memberName(node) === name &&
            isDocumentRoot(node.object, seen)
          );
        };
        const isRootDataset = (node) => isRootFacade(node, "dataset");
        const isRootClassList = (node) => isRootFacade(node, "classList");
        const ownsDatasetKey = (key) =>
          typeof key === "string" && /^lf[A-Z]/u.test(key);
        const ownsDatasetMember = (node) => ownsDatasetKey(memberName(node));
        const ownsDatasetObject = (node) =>
          node?.type === "ObjectExpression" &&
          node.properties.every(
            (property) =>
              property.type === "Property" &&
              property.kind === "init" &&
              ownsDatasetKey(
                !property.computed && property.key.type === "Identifier"
                  ? property.key.name
                  : staticString(property.key),
              ),
          );
        const ownsClassTokens = (operation, nodes) => {
          const tokens =
            operation === "toggle"
              ? nodes.slice(0, 1)
              : operation === "replace"
                ? nodes.slice(0, 2)
                : nodes;
          return tokens.every((argument) => staticString(argument)?.startsWith("lf-"));
        };
        const reportsRootStyleTarget = (node) =>
          isRootStyle(node) ||
          (node?.type === "MemberExpression" && isRootStyle(node.object));
        const report = (node, kind) =>
          context.report({
            node,
            message: `Mutate document-root ${kind} through state/root-state.js so authored revision replacement preserves ownership.`,
          });
        return {
          AssignmentExpression(node) {
            if (reportsRootStyleTarget(node.left)) report(node, "inline styles");
            else if (
              node.left.type === "MemberExpression" &&
              isRootDataset(node.left.object) &&
              !ownsDatasetMember(node.left)
            )
              report(node, "attributes");
            else if (
              node.left.type === "MemberExpression" &&
              isRootClassList(node.left.object)
            )
              report(node, "attributes");
            else if (
              node.left.type === "MemberExpression" &&
              isDocumentRoot(node.left.object)
            )
              report(node, "attributes");
          },
          UpdateExpression(node) {
            if (reportsRootStyleTarget(node.argument)) report(node, "inline styles");
            else if (
              node.argument.type === "MemberExpression" &&
              isRootDataset(node.argument.object) &&
              !ownsDatasetMember(node.argument)
            )
              report(node, "attributes");
            else if (
              node.argument.type === "MemberExpression" &&
              isRootClassList(node.argument.object)
            )
              report(node, "attributes");
            else if (
              node.argument.type === "MemberExpression" &&
              isDocumentRoot(node.argument.object)
            )
              report(node, "attributes");
          },
          UnaryExpression(node) {
            if (
              node.operator === "delete" &&
              node.argument.type === "MemberExpression" &&
              ((isRootDataset(node.argument.object) &&
                !ownsDatasetMember(node.argument)) ||
                isRootClassList(node.argument.object) ||
                isDocumentRoot(node.argument.object))
            )
              report(node, "attributes");
          },
          CallExpression(node) {
            if (
              node.callee.type === "MemberExpression" &&
              ["setProperty", "removeProperty"].includes(propertyName(node.callee)) &&
              isRootStyle(node.callee.object)
            )
              report(node, "inline styles");
            if (
              node.callee.type === "MemberExpression" &&
              ["setAttribute", "removeAttribute", "toggleAttribute"].includes(
                propertyName(node.callee),
              ) &&
              isDocumentRoot(node.callee.object)
            ) {
              const attribute =
                staticString(node.arguments[0]) ??
                pagePaintAttributeValue(node.arguments[0]);
              if (!attribute?.startsWith("data-lf-"))
                report(node, attribute === "style" ? "inline styles" : "attributes");
            }
            if (
              node.callee.type === "MemberExpression" &&
              ["add", "remove", "toggle", "replace"].includes(
                propertyName(node.callee),
              ) &&
              isRootClassList(node.callee.object) &&
              !ownsClassTokens(propertyName(node.callee), node.arguments)
            )
              report(node, "attributes");
            if (
              node.callee.type === "MemberExpression" &&
              node.callee.object.type === "Identifier" &&
              ["Object", "Reflect"].includes(node.callee.object.name) &&
              ["assign", "set"].includes(propertyName(node.callee))
            ) {
              if (isRootStyle(node.arguments[0])) report(node, "inline styles");
              else if (isDocumentRoot(node.arguments[0])) report(node, "attributes");
              else if (isRootClassList(node.arguments[0])) report(node, "attributes");
              else if (isRootDataset(node.arguments[0])) {
                const operation = propertyName(node.callee);
                const owned =
                  operation === "assign"
                    ? node.arguments.slice(1).every(ownsDatasetObject)
                    : ownsDatasetKey(staticString(node.arguments[1]));
                if (!owned) report(node, "attributes");
              }
            }
          },
        };
      },
    },
  },
};

export default [
  // Generated, vendored, and installed files, ignored everywhere. An `ignores` list
  // is global only in a config object that carries nothing else, so this one stands
  // alone; beside another key it would ignore those paths for that config alone and
  // leave every later one linting them. `.venv` is uv's, and holds Playwright's
  // bundled JavaScript: the pre-commit hook passes staged files and never reaches it,
  // but a bare `pnpm exec eslint .` walks it.
  {
    ignores: [
      ".tmp/**",
      ".venv/**",
      "browser/vendor/**",
      "packages/*/vendor/**",
      "evals/ui-review-detection/fixtures/**",
    ],
  },
  { linterOptions: { noInlineConfig: true } },
  js.configs.recommended,
  {
    rules: {
      "array-callback-return": ["error", { allowImplicit: true }],
      "no-constructor-return": "error",
      "no-new-wrappers": "error",
      "no-unreachable-loop": "error",
      "no-unsafe-negation": ["error", { enforceForOrderingRelations: true }],
      // A `let` declared ahead of the closures that read it, and assigned once after
      // them, stays a `let`: as a `const` it would move below its readers.
      "prefer-const": ["error", { ignoreReadBeforeAssign: true }],
    },
  },
  {
    files: [
      "*.mjs",
      ".config/*.mjs",
      ".github/scripts/*.mjs",
      "build/**/*.mjs",
      "worker/*.mjs",
      "dev/**/*.mjs",
      "evals/**/*.mjs",
      "tests/*.mjs",
    ],
    languageOptions: { globals: globals.nodeBuiltin },
  },
  {
    files: ["**/*.cjs"],
    languageOptions: { globals: globals.node },
  },
  {
    files: [
      "examples/**/*.js",
      "docs/**/*.js",
      "evals/**/fixtures/**/*.js",
      "tests/fixtures/**/*.js",
      "tests/*_watch.js",
      "tests/watch_platform.js",
      "dev/leaf_dev/main_thread.js",
      "dev/leaf_dev/frames.js",
    ],
    languageOptions: { globals: globals.browser },
  },
  {
    // Playwright's Node drivers also execute callbacks in the page's realm.
    files: [
      "evals/ui-review-detection/hooks.mjs",
      "evals/ui-review-detection/provider.mjs",
    ],
    languageOptions: { globals: browserGlobals },
  },
  {
    // render_harness.shift_watch_source binds these runtime readings around the sensor.
    files: ["tests/shift_watch.js"],
    languageOptions: {
      globals: Object.fromEntries(
        [
          "interactive",
          "pressControls",
          "caretKeys",
          "clippingAxes",
          "renderedParent",
          "skipped",
          "elementAxes",
          "scrollAxes",
          "nativePerformance",
          "nativeFrame",
          "nativeTask",
        ].map((name) => [name, "readonly"]),
      ),
    },
  },
  {
    files: ["**/*.{js,mjs,cjs}"],
    languageOptions: { ecmaVersion: "latest" },
    rules: publicRuntimeBoundary,
  },
  {
    // Build tools share private runtime declarations with the browser rather than
    // duplicating them. The public facade boundary applies to page consumers.
    files: ["build/**/*.mjs", "worker/*.mjs", "eslint.config.mjs"],
    rules: entryBoundary,
  },
  {
    // Compiler tests load their newly generated temporary output. Those paths
    // are build results, not authored browser imports hiding dependency edges.
    files: ["build/**/*.test.mjs"],
    rules: {
      "no-restricted-syntax": [
        "error",
        ...publicRuntimeSyntax.filter(
          (rule) => rule.selector !== 'ImportExpression:not([source.type="Literal"])',
        ),
      ],
    },
  },
  {
    // The browser framework's and runtime's own fold tests exercise private owners,
    // which the facade rule would forbid; the entry stays out of reach, because a
    // test is not a page and booting one would import the whole layer to read one fold.
    files: ["tests/runtime/**/*.mjs", "build/browser/**/*.test.mjs"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          paths: [{ name: "/leaf.js", message: entryMessage }],
          patterns: [{ regex: "^\\.{1,2}/(?:.*/)?leaf\\.js$", message: entryMessage }],
        },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: 'ImportExpression[source.value="/leaf.js"]',
          message: entryMessage,
        },
        {
          selector: "ImportExpression[source.value=/^\\.{1,2}\\/(?:.*\\/)?leaf\\.js$/]",
          message: entryMessage,
        },
      ],
    },
  },
  {
    // Runtime tests exercise browser owners; compiler tests run in Node.
    files: ["tests/runtime/**/*.mjs"],
    languageOptions: { globals: browserGlobals },
  },
  {
    // Python executes these test expressions and modules inside the browser. Their
    // source is linted here rather than hidden inside Python string literals.
    files: [
      "tests/page_scripts/**/*.js",
      "dev/leaf_dev/geometry.js",
      "dev/leaf_dev/focus_rings.js",
      "dev/leaf_dev/control_name.js",
    ],
    languageOptions: { globals: browserGlobals },
  },
  {
    files: ["dev/leaf_dev/startup.js", "dev/leaf_dev/painted.js"],
    languageOptions: { globals: browserGlobals, sourceType: "script" },
  },
  {
    // Browser diagnostics resolve published runtime entries from the page under
    // test. Those scoped URLs are data rather than static dependency edges.
    files: ["dev/leaf_dev/website.js", "dev/leaf_dev/painted.js"],
    languageOptions: { globals: browserGlobals, sourceType: "script" },
    rules: {
      "no-restricted-syntax": [
        "error",
        ...publicRuntimeSyntax.filter(
          (rule) => rule.selector !== 'ImportExpression:not([source.type="Literal"])',
        ),
      ],
    },
  },
  {
    files: ["src/leaf/source/render-checks/*.js"],
    languageOptions: { globals: browserGlobals },
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
    // The Playwright driver imports the probe route Python selects at runtime. It is
    // the loader being tested; every probe behind that route keeps static imports.
    files: ["src/leaf/source/render-checks/driver.js"],
    languageOptions: { sourceType: "script" },
    rules: {
      "no-restricted-syntax": [
        "error",
        ...publicRuntimeSyntax.filter(
          (rule) => rule.selector !== 'ImportExpression:not([source.type="Literal"])',
        ),
      ],
    },
  },
  {
    files: ["src/leaf/source/render-checks/*.js"],
    rules: {
      // Render checks use their diagnostic adapter alongside the public widget API.
      // Every other runtime owner remains private to the kernel.
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
              regex: "^/runtime/(?!widget-api\\.js$|check-api\\.js$|lib/[^/\\\\%]+$)",
              message:
                "Render checks use the public API, the library or the diagnostic adapter.",
            },
            {
              regex: "^\\.{1,2}/(?:.*/)?runtime/",
              message: "Render checks use absolute runtime boundaries.",
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
    files: ["browser/leaf.js"],
    plugins: { architecture: architecturePlugin },
    rules: {
      ...entryBoundary,
      "architecture/root-state-ownership": "error",
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
    files: ["browser/**/*.js", "packages/*/**/*.js"],
    languageOptions: { globals: browserGlobals },
  },
  {
    // What the kernel build and the website's rebundle compile (`topLevelAwaitRule`).
    files: [
      "browser/**/*.js",
      "packages/*/**/*.js",
      "examples/**/*.page/widgets/**/*.js",
    ],
    plugins: { architecture: architecturePlugin },
    rules: { "architecture/top-level-await": "error" },
  },
  {
    // The settled reading answers only for the rendering callbacks and size observers it
    // counts, so the layer and its packages reach both through the library's pass
    // (runtime/lib/frame-pass.js), which the reading hears (runtime/base/rendering.js). The
    // packages' block below names the calls a package makes itself.
    files: ["browser/**/*.js", "packages/*/**/*.js"],
    // Prepaint runs before the module graph, so it cannot call the scheduler.
    ignores: [
      "browser/runtime/lib/frame-pass.js",
      "browser/runtime/base/rendering.js",
      "browser/runtime/prepaint.js",
    ],
    rules: {
      "no-restricted-globals": [
        "error",
        ...RENDERING_NAMES.map((name) => ({ name, message: RENDERING_MESSAGE })),
      ],
    },
  },
  {
    files: ["browser/**/*.js", "packages/*/**/*.js"],
    plugins: { architecture: architecturePlugin },
    rules: {
      "architecture/current-location-listeners": [
        "error",
        {
          // The owner of every focus event.
          "browser/runtime/dom/focus.js": ["focus", "focusin", "focusout"],
          // Records the raw events of a session for the interaction log, the one
          // exception that is not one element's or one subtree's own question: it is a
          // recorder of events, and does not read the current location from them.
          "browser/runtime/transport/interaction-log.js": ["focusin", "focusout"],
          // A reply row's own entry begins its composition. The box's host is in the
          // row's tree, so entering its shadow tree reaches the row, and a move inside
          // it is no new entry.
          "browser/runtime/records/thread/replies.js": ["focusin"],
          // A widget's own subtree, whose controls stand in its tree: whether focus is
          // within the gloss, and the contents link the user last stood on.
          "packages/default/widgets/lf-gloss.js": ["focusin", "focusout"],
          "packages/default/widgets/lf-toc.js": ["focusin"],
          // The text field's empty line hands focus that lands on it to the editor it
          // builds, in its own shadow tree.
          "browser/runtime/annotations/composing/text-field.js": ["focusin"],
        },
      ],
      "architecture/placements": [
        "error",
        [
          // The one placement, and the one handing on an arrival in progress.
          "browser/runtime/dom/focus.js",
          // The text field's own `focus()`, which the placement calls, hands on to the
          // editor its shadow tree holds.
          "browser/runtime/annotations/composing/text-field.js",
          // The shared CodeMirror adapter places its own native editor.
          "browser/runtime/annotations/editor-view.js",
          // A held release stands in for the browser's own press, so it focuses the
          // target as that press does, ringless; dom/focus.js reads it as the press's.
          "browser/runtime/annotations/preview.js",
        ],
      ],
      "architecture/native-layers": [
        "error",
        [
          // The owner.
          "browser/runtime/dom/keyboard/layer-stack.js",
        ],
      ],
      "architecture/open-layers": [
        "error",
        [
          // The owner.
          "browser/runtime/lib/shadow-tree.js",
        ],
      ],
      "architecture/scroll-ends": [
        "error",
        [
          // The one owner of a scroll's end.
          "browser/runtime/dom/arrivals.js",
        ],
      ],
      "architecture/scroll-writes": [
        "error",
        [
          // A carried node's offsets, kept in a record under their own names until
          // its replacement takes them.
          "browser/runtime/records/carry.js",
        ],
      ],
      "architecture/layer-returns": [
        "error",
        [
          // The owner of the hand-back and the let-go.
          "browser/runtime/dom/focus.js",
        ],
      ],
      "architecture/current-location-reads": [
        "error",
        [
          // The one reading of the user’s current location.
          "browser/runtime/dom/focus.js",
          // The editor asks whether its own content holds focus inside the closed
          // root it renders in, which dom/focus.js, reading through open roots, cannot see.
          "browser/runtime/annotations/editor-view.js",
          "browser/runtime/annotations/composing/text-field.js",
        ],
      ],
      "architecture/moves": [
        "error",
        [
          // The one mover.
          "browser/runtime/dom/dom-move.js",
          // Its parser-time hook inserts the first drawing before modules run.
          "browser/runtime/prepaint.js",
        ],
      ],
      "architecture/spelled-keys": "error",
    },
  },
  {
    // Kernel widgets use their private owners; package widgets use the public API.
    files: ["browser/widgets/**/*.js"],
    rules: entryBoundary,
  },
  {
    files: ["browser/runtime/**/*.{js,mjs}"],
    plugins: { architecture: architecturePlugin },
    rules: {
      ...ownerBoundary,
      "architecture/root-state-ownership": "error",
      "architecture/import-layers": "error",
    },
  },
  {
    // This is the boundary that loads authored/package modules, whose paths are
    // data rather than runtime dependencies. Literal imports still enter the graph.
    files: ["browser/runtime/records/widget-loader.js"],
    rules: {
      "no-restricted-syntax": [
        "error",
        ...ownerRuntimeSyntax.filter(
          (rule) => rule.selector !== 'ImportExpression:not([source.type="Literal"])',
        ),
      ],
    },
  },
  {
    // These primitives may use the browser, but importing an application owner
    // would make every caller acquire that owner's initialization and paint graph.
    // A vendored algorithm is not an application owner, so a primitive may reuse
    // one rather than write a second copy of it beside the layer's, with its imports
    // subject to the same boundary. Nor is another primitive,
    // whose own imports this same rule holds: `base/rendering.js`, which every rendering
    // callback is counted through, or `dom/focus.js`, which a primitive that moves the
    // user's node asks to keep their current location on it. Nor is a module of the
    // library (lib/), which its own block below keeps clear of every owner.
    files: runtimePrimitives.map((name) => `browser/runtime/${name}`),
    rules: {
      "no-restricted-syntax": [
        "error",
        {
          selector:
            "ImportExpression, ExportAllDeclaration, ExportNamedDeclaration[source]",
          message: "Runtime primitives import statically and re-export nothing.",
        },
      ],
    },
  },
  // The same boundary for each primitive, which names the others by its own path to them.
  ...runtimePrimitives.map((name) => {
    const relative = (to) => {
      const specifier = path.posix.relative(path.posix.dirname(name), to);
      return (specifier.startsWith(".") ? specifier : `./${specifier}`).replaceAll(
        ".",
        "\\.",
      );
    };
    return {
      files: [`browser/runtime/${name}`],
      rules: {
        "no-restricted-imports": [
          "error",
          {
            patterns: [
              {
                regex: `^(?!/vendor/|${relative("lib")}/[^/\\\\%]+$|(?:${runtimePrimitives
                  .map(relative)
                  .join("|")})$)`,
                message:
                  "Runtime primitives must remain independent of other owners; only a /vendor/ bundle, a library module (lib/) or another primitive may be imported.",
              },
            ],
          },
        ],
      },
    };
  }),
  {
    // The library of shared web code holds none of the page's state and reaches none
    // of Leaf's (browser/AGENTS.md, "The library of shared web code"), so a module of
    // it names only a /vendor/ bundle and the modules beside it, whether it imports
    // statically or lazily. That keeps out the runtime, and with it the kernel registry,
    // which is not in the graph the import graph's check reads. So each module loads in a document
    // Leaf did not compose. A module holds one concern, so none gathers the others'
    // exports.
    files: ["browser/runtime/lib/**/*.js"],
    rules: {
      "no-restricted-imports": [
        "error",
        { patterns: [{ regex: `^(?!${librarySpecifier})`, message: LIBRARY_MESSAGE }] },
      ],
      "no-restricted-syntax": [
        "error",
        ...ownerRuntimeSyntax,
        {
          selector: `ImportExpression[source.type="Literal"]:not([source.value=/^${librarySpecifier.replaceAll("/", "\\/")}/])`,
          message: LIBRARY_MESSAGE,
        },
        {
          selector: "ExportAllDeclaration, ExportNamedDeclaration[source]",
          message:
            "A library module re-exports nothing: its importer names the module that holds what it needs.",
        },
      ],
    },
  },
  {
    // Thread folding accepts values; it must not obtain them from browser
    // stores or painters. The current derived reading has the same dependency floor.
    // Of the library, a fold reaches only the rank keys (lib/rank.js), which take
    // values too.
    files: [
      "browser/runtime/state/projection/model.js",
      "browser/runtime/records/projection/state.js",
      "browser/runtime/state/pending/model.js",
      "browser/runtime/records/pending/state.js",
      "browser/runtime/state/thread/model.js",
      "browser/runtime/records/thread/state.js",
    ],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              regex:
                "^(?!\\.\\./\\.\\./(?:base/anchor-coordinate|state/semantic-state|lib/rank)\\.js$|\\.\\./(?:kept|kernel-facts|thread/identity)\\.js$|\\./identity\\.js$)",
              message: "Thread readings depend only on pure record operations.",
            },
          ],
        },
      ],
      "no-restricted-syntax": [
        "error",
        {
          selector: "ImportExpression",
          message: "Thread readings declare their record dependencies statically.",
        },
      ],
      "no-restricted-globals": [
        "error",
        ...Object.keys(browserGlobals).filter((name) => name !== "structuredClone"),
      ],
    },
  },
  {
    files: ["src/leaf/source/render-checks/init.js"],
    languageOptions: { sourceType: "script" },
  },
  {
    // The script an export draws its page with (`exporting.static_document`).
    files: ["src/leaf/pages/static-export.js"],
    languageOptions: { globals: browserGlobals, sourceType: "script" },
  },
  {
    // Properties the layer and its packages reach only through their owner. A file
    // takes a rule's options from the last block matching it, not a merge of every
    // block's, so all of them stand in this one list, and the history owners' block
    // and the packages' block below repeat the others.
    files: ["browser/**/*.js", "packages/*/**/*.js"],
    rules: {
      "no-restricted-properties": [
        "error",
        ...RENDERING_PROPERTIES,
        ...HISTORY_PROPERTIES,
        ...ID_PROPERTIES,
      ],
    },
  },
  {
    // runtime/records/history.js owns this document's session history: a Back to an entry the
    // page added returns to the place it was left at only because that owner takes the
    // traversal. The prepaint bootstrap runs before any module, and only cleans marks
    // off the address the document arrived at.
    files: ["browser/runtime/records/history.js", "browser/runtime/bootstrap.js"],
    rules: {
      "no-restricted-properties": ["error", ...RENDERING_PROPERTIES, ...ID_PROPERTIES],
    },
  },
  {
    // Where a package writes the browser's own call, because the runtime's function
    // adds nothing to it. Motion that may run until the user stops it, such as
    // playback, calls the browser's frame, which the settled reading doesn't count; a
    // size observer stays counted. The open-layers and current-location-reads rules hold
    // the runtime to one reading of every node and of where the user is, and a package
    // asks its own popover or dialog whether it is open, and its own tree's
    // `activeElement` what is focused there, so both rules are off here whole. A package
    // opens and closes its popover or dialog with the browser's own methods, whose focus
    // return Leaf reads as a return, so the native-layers and layer-returns rules are
    // off here too. A package sets a box's scroll offset with the browser's own
    // `scrollTo`, which the runtime hears as it is made (runtime/dom/arrivals.js), under the
    // scroll-writes rule the layer keeps. Each other rule repeats what it keeps of the
    // layer's, since a file takes a rule's options from the last block matching it.
    files: ["packages/*/**/*.js"],
    rules: {
      "no-restricted-globals": [
        "error",
        ...PACKAGE_RENDERING_NAMES.map((name) => ({
          name,
          message: RENDERING_MESSAGE,
        })),
      ],
      "no-restricted-properties": [
        "error",
        ...renderingProperties(PACKAGE_RENDERING_NAMES),
        ...HISTORY_PROPERTIES,
        ...ID_PROPERTIES,
      ],
      "architecture/open-layers": "off",
      "architecture/current-location-reads": "off",
      "architecture/native-layers": "off",
      "architecture/layer-returns": "off",
    },
  },
  {
    // An import or binding nothing reads is a dependency edge the graph still carries
    // and a name the next reader has to account for. Arguments are the type checks'
    // (`noUnusedParameters`), which count a use in a JSDoc type where this rule
    // doesn't. A callback keeps an argument it must take to reach a later one behind a
    // `_`, so its signature still says what it is handed. Caught errors are left alone.
    files: ["**/*.{js,mjs,cjs}"],
    rules: {
      "no-unused-vars": [
        "error",
        { args: "none", caughtErrors: "none", ignoreRestSiblings: true },
      ],
    },
  },
];
