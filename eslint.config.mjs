import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

// The runtime's primitives, by path under `runtime/`: modules that may use the browser
// but import no owner, which the rule naming them below holds.
const runtimePrimitives = [
  "anchor-coordinate.js",
  "chrome.js",
  "dom-children.js",
  "focus.js",
  "control-selectors.js",
  "keeps.js",
  "rendering.js",
  "sample-visibility.js",
  "queued-work.js",
  "repaint.js",
  "root-state.js",
  "thread/identity.js",
];

// The browser's names the layer uses, for `no-undef`: a moved function that lost an
// import must fail the hook rather than bind to `window.*` on the first page that
// reaches it. Only names in use are listed — `open`, `top`, `parent`, `origin`, `escape`
// are locals here, and declaring the browser's copies would hide exactly the lost import
// this rule is for. A new global is added when the hook refuses it.
const browserGlobals = Object.fromEntries(
  [
    "AbortController",
    "CSS",
    "CSSImportRule",
    "CSSKeyframesRule",
    "CSSScopeRule",
    "CSSStyleRule",
    "CSSStyleSheet",
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
    "IntersectionObserver",
    "MessageChannel",
    "MouseEvent",
    "MutationObserver",
    "Node",
    "NodeFilter",
    "OffscreenCanvas",
    "PerformanceObserver",
    "Range",
    "Response",
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
  "Use nextRender, nextFrame, cancelRender, or sizeObserver (runtime/rendering.js) so the settled reading counts it.";

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

const publicRuntimeBoundary = {
  "no-restricted-imports": [
    "error",
    {
      paths: [
        {
          name: "/leaf.js",
          message: "Import Leaf capabilities from /runtime/widget-api.js.",
        },
        {
          name: "/vendor/browser-runtime.js",
          message:
            "Content modules import Lit and Leaf capabilities from /runtime/widget-api.js.",
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
        {
          regex: "^\\.{1,2}/(?:.*/)?vendor/browser-runtime\\.js$",
          message:
            "Content modules import Lit and Leaf capabilities from /runtime/widget-api.js.",
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
      selector: 'ImportExpression[source.value="/vendor/browser-runtime.js"]',
      message:
        "Content modules import Lit and Leaf capabilities from /runtime/widget-api.js.",
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
      selector:
        "ImportExpression[source.value=/^\\.{1,2}\\/(?:.*\\/)?vendor\\/browser-runtime\\.js$/]",
      message:
        "Content modules import Lit and Leaf capabilities from /runtime/widget-api.js.",
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

let pagePaintAttributeValues;
function pagePaintAttributesFrom(parser) {
  if (pagePaintAttributeValues) return pagePaintAttributeValues;
  const file = path.join(runtimeRoot, "page-paint.js");
  const ast = parser.parse(fs.readFileSync(file, "utf8"), {
    ecmaVersion: "latest",
    sourceType: "module",
  });
  const declarations = ast.body.flatMap((statement) => {
    const declaration =
      statement.type === "ExportNamedDeclaration" ? statement.declaration : statement;
    return declaration?.type === "VariableDeclaration" ? declaration.declarations : [];
  });
  const record = declarations.find(
    (declaration) =>
      declaration.id.type === "Identifier" &&
      declaration.id.name === "PAGE_PAINT_ATTRIBUTE",
  );
  const attributes =
    record?.init?.type === "CallExpression" &&
    record.init.callee.type === "MemberExpression" &&
    !record.init.callee.computed &&
    record.init.callee.object.type === "Identifier" &&
    record.init.callee.object.name === "Object" &&
    record.init.callee.property.type === "Identifier" &&
    record.init.callee.property.name === "freeze" &&
    record.init.arguments[0]?.type === "ObjectExpression"
      ? record.init.arguments[0]
      : null;
  if (!attributes)
    throw new Error(
      "PAGE_PAINT_ATTRIBUTE must remain a frozen object literal for root-state linting",
    );
  pagePaintAttributeValues = new Map();
  for (const property of attributes.properties) {
    const name =
      property.type === "Property" && !property.computed
        ? property.key.type === "Identifier"
          ? property.key.name
          : property.key.value
        : null;
    const value =
      property.type === "Property" &&
      property.value.type === "Literal" &&
      typeof property.value.value === "string"
        ? property.value.value
        : null;
    if (typeof name !== "string" || value === null)
      throw new Error(
        "PAGE_PAINT_ATTRIBUTE keys and values must remain static strings for root-state linting",
      );
    pagePaintAttributeValues.set(name, value);
  }
  return pagePaintAttributeValues;
}

export const semanticStoreOwnershipRule = {
  meta: { type: "problem", schema: [] },
  create(context) {
    const file = runtimeName(context.filename ?? context.getFilename());
    const publisherExports = new Set([
      "createApplicationPublisher",
      "createSemanticApplication",
    ]);
    const browserFrameworkSource = (source) =>
      typeof source?.value === "string" &&
      /(?:^|\/)vendor\/browser-runtime\.js$/u.test(source.value);
    const report = (node, name) =>
      context.report({
        node,
        message:
          name === "createApplicationPublisher"
            ? "The raw publisher is private to the semantic application."
            : "Only semantic-state.js may construct the application publisher.",
      });
    return {
      ImportDeclaration(node) {
        if (!browserFrameworkSource(node.source)) return;
        for (const specifier of node.specifiers) {
          if (specifier.type === "ImportNamespaceSpecifier") {
            context.report({
              node: specifier,
              message:
                "Import named browser framework capabilities so semantic publisher ownership remains statically visible.",
            });
            continue;
          }
          const name = specifier.imported?.name;
          if (
            publisherExports.has(name) &&
            (name === "createApplicationPublisher" || file !== "semantic-state.js")
          )
            report(specifier, name);
        }
      },
      ExportNamedDeclaration(node) {
        if (!browserFrameworkSource(node.source)) return;
        // Only named specifiers reach here: `export * as ns from` is an
        // ExportAllDeclaration below, which answers the whole-namespace reexport.
        for (const specifier of node.specifiers) {
          const name = specifier.local?.name;
          if (publisherExports.has(name)) report(specifier, name);
        }
      },
      ImportExpression(node) {
        if (!browserFrameworkSource(node.source)) return;
        context.report({
          node,
          message:
            "Import browser framework capabilities statically so semantic publisher ownership remains visible.",
        });
      },
      ExportAllDeclaration(node) {
        if (!browserFrameworkSource(node.source)) return;
        context.report({
          node,
          message:
            "Reexport browser framework capabilities by name so semantic publisher ownership remains statically visible.",
        });
      },
    };
  },
};

// Where the user stands, and what moved them there, is focus.js's one reading
// (`onStanding`). A `focusin` or `focusout` listener hears nothing of a move between two
// nodes of one shadow tree beneath it, and a reader that tells the runtime's returns or
// the keyboard's arrivals apart for itself answers a question focus.js already answers.
// So the two event names appear nowhere else, in a listener, a list of event types, a
// comparison or a Lit binding, and `focus` and `blur` are not heard on the document or
// captured anywhere, which would hear every element beneath. An element's own `focus`
// or `blur`, and the window's, which is the system's focus, are other questions. The option names,
// by path from the repository root, the files that may still name a focus event, each
// with the reason in the config that grants it.
const standingRepoRoot = path.dirname(fileURLToPath(import.meta.url));
const STANDING_MESSAGE =
  "Read where the user stands from onStanding (runtime/focus.js): a focusin or focusout listener misses moves inside a shadow tree beneath it and guesses its own cause.";
export const standingListenersRule = {
  meta: {
    type: "problem",
    schema: [{ type: "object", additionalProperties: { type: "array" } }],
  },
  create(context) {
    const file = path
      .relative(standingRepoRoot, context.filename ?? context.getFilename())
      .split(path.sep)
      .join("/");
    const allowed = new Set(context.options[0]?.[file] ?? []);
    const named = (node, type) => {
      if (!allowed.has(type)) context.report({ node, message: STANDING_MESSAGE });
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
// (`focusDestination(node, cause)` in focus.js), since that call is the only place that
// knows whether it is a route or a return, and each reader of where they stand acts on
// the word. A plain `focus()` publishes as the user's own move. The rule knows the
// element method by its shape, no argument or an options object, so a method of the same
// name taking a key, as a contribution's `focus(entryKey, cause)` does, is another
// question. Each call to `focusDestination` names its cause, and the function is not
// handed around as a value, where a caller would call it without one. The option names
// the files that may still call `focus()`: the owner, and an element whose own `focus()`
// hands on to the editor inside it.
const PLACEMENT_MESSAGE =
  "Put the user on an element with focusDestination(node, cause) (runtime/focus.js): a plain focus() publishes as the user's own move, so a return reads as one.";
export const placementsRule = {
  meta: { type: "problem", schema: [{ type: "array", items: { type: "string" } }] },
  create(context) {
    const file = path
      .relative(standingRepoRoot, context.filename ?? context.getFilename())
      .split(path.sep)
      .join("/");
    const owner = (context.options[0] ?? []).includes(file);
    const optionsLike = (arg) =>
      arg.type === "ObjectExpression" ||
      arg.type === "SpreadElement" ||
      (arg.type === "Identifier" && /^opt/u.test(arg.name));
    return {
      CallExpression(node) {
        const { callee, arguments: args } = node;
        if (callee.type === "MemberExpression" && !callee.computed) {
          if (
            ["scrollIntoView", "scrollIntoViewIfNeeded"].includes(callee.property.name)
          )
            context.report({
              node,
              message:
                "Reveal with scrollIntoView(node, options) from runtime/landing-scroll.js: native reveal can scroll the containing page.",
            });
          if (
            ["showModal", "showPopover", "hidePopover"].includes(
              callee.property.name,
            ) &&
            file !== "skills/leaf/assets/runtime/keyboard/layer-stack.js"
          )
            context.report({
              node,
              message:
                "Use showNativeLayer(layer, options) or closeNativeLayer(layer): native focus must respect the document holding input.",
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

// A layer hands the user back as it closes in one act (`closeLayer(close, land)` in
// focus.js), so the platform's own hand-back and the owner's reach readers once, as where
// the user ends up. A return made anywhere else is a layer return beside it, which
// readers hear as a second move and holds read as a newer word. The rule admits
// `handBack(...)` only in a landing's own body: the function passed as a close's `land`,
// or one `layerLanding(...)` wraps, which a closer builds away from the call and which
// throws if it runs at any other time. A landing is synchronous, since what it does
// after an await or in a callback happens beside the close. The `close` argument hides
// the layer and places nothing, so a placement written there is refused too. So is a
// `focusDestination(..., "return")` outside a landing where a statement before it in its
// function hides something by the platform's means, a layer return spelled out by hand;
// a hide through an owner's own function, as `showFab(null)`, is out of the rule's
// sight. `letGo` lands the user on the page by a route, as `g p` does, so it is no layer
// return of itself. The option names the files that may still return the user directly.
const LAYER_RETURN_MESSAGE =
  "Hand the user back as the layer closes, in the body of closeLayer(close, land)'s land or a layerLanding (runtime/focus.js): a return beside it reaches readers as a second move.";
const CLOSE_PLACES_MESSAGE =
  "closeLayer's close hides the layer and places nothing; put the user in its land (runtime/focus.js).";
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
// (`open && (() => …)`, `standing ? () => … : letGo`).
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
      .relative(standingRepoRoot, context.filename ?? context.getFilename())
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

const architecturePlugin = {
  rules: {
    "semantic-store-ownership": semanticStoreOwnershipRule,
    "standing-listeners": standingListenersRule,
    placements: placementsRule,
    "layer-returns": layerReturnsRule,
    "root-state-ownership": {
      meta: { type: "problem", schema: [] },
      create(context) {
        const file = runtimeName(context.filename ?? context.getFilename());
        // The bootstrap and the prepaint run before the module graph and write only
        // what the first paint needs, before any authored revision has replaced the
        // root's attributes. root-state.js is the sole standing mutation boundary.
        if (["bootstrap.js", "prepaint.js", "root-state.js"].includes(file)) return {};
        const source = context.sourceCode ?? context.getSourceCode();
        const pagePaintAttributes = pagePaintAttributesFrom(
          context.languageOptions.parser,
        );
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
            message: `Mutate document-root ${kind} through root-state.js so authored revision replacement preserves ownership.`,
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
  // but a bare `npx eslint .` walks it.
  {
    ignores: [
      ".tmp/**",
      ".venv/**",
      "examples/corpus.html",
      "skills/leaf/assets/vendor/**",
      "skills/leaf/packages/*/vendor/**",
    ],
  },
  { linterOptions: { noInlineConfig: true } },
  {
    files: ["**/*.{js,mjs}"],
    languageOptions: { ecmaVersion: "latest", sourceType: "module" },
    rules: publicRuntimeBoundary,
  },
  {
    // Build tools share private runtime declarations with the browser rather than
    // duplicating them. The public facade boundary applies to page consumers.
    files: ["build/**/*.mjs", "worker/*.mjs"],
    rules: entryBoundary,
  },
  {
    // Compiler tests load their newly generated temporary output. Those paths
    // are build results, not authored browser imports hiding dependency edges.
    files: ["build/**/*.test.mjs"],
    rules: {
      "no-restricted-syntax": [
        "error",
        ...publicRuntimeBoundary["no-restricted-syntax"]
          .slice(1)
          .filter(
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
    rules: { "no-undef": "error" },
  },
  {
    files: ["build/pierre/*.mjs"],
    rules: { "no-undef": "error" },
  },
  {
    files: ["build/pierre/build.mjs"],
    languageOptions: { globals: { process: "readonly" } },
  },
  {
    // Python executes these test expressions and modules inside the browser. Their
    // source is linted here rather than hidden inside Python string literals.
    files: ["tests/browser/**/*.js"],
    languageOptions: { globals: browserGlobals },
    rules: { "no-undef": "error" },
  },
  {
    files: ["dev/leaf_dev/startup.js", "dev/leaf_dev/bench_latency.js"],
    languageOptions: { globals: browserGlobals, sourceType: "script" },
    rules: { "no-undef": "error" },
  },
  {
    // Browser diagnostics resolve published runtime entries from the page under
    // test. Those scoped URLs are data rather than static dependency edges.
    files: ["dev/leaf_dev/verify_site_browser.js", "dev/leaf_dev/bench_latency.js"],
    languageOptions: { globals: browserGlobals, sourceType: "script" },
    rules: {
      "no-undef": "error",
      "no-restricted-syntax": [
        "error",
        ...publicRuntimeBoundary["no-restricted-syntax"]
          .slice(1)
          .filter(
            (rule) => rule.selector !== 'ImportExpression:not([source.type="Literal"])',
          ),
      ],
    },
  },
  {
    files: ["skills/leaf/scripts/leaf/render-checks/*.js"],
    languageOptions: { globals: browserGlobals },
    rules: {
      ...publicRuntimeBoundary,
      "no-undef": "error",
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
    files: ["skills/leaf/scripts/leaf/render-checks/driver.js"],
    languageOptions: { sourceType: "script" },
    rules: {
      "no-restricted-syntax": [
        "error",
        ...publicRuntimeBoundary["no-restricted-syntax"]
          .slice(1)
          .filter(
            (rule) => rule.selector !== 'ImportExpression:not([source.type="Literal"])',
          ),
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
    files: [
      "skills/leaf/scripts/leaf/render-checks/replay.js",
      "skills/leaf/scripts/leaf/render-checks/runtime.js",
      "skills/leaf/scripts/leaf/render-checks/widgets.js",
    ],
    rules: {
      // Render checks use their diagnostic adapter alongside the public widget API.
      // Validation and visual-part owners remain private to the kernel.
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
              regex: "^/runtime/(?!widget-api\\.js$|check-api\\.js$)",
              message: "Render checks use the public API or diagnostic adapter.",
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
    files: ["skills/leaf/assets/leaf.js"],
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
    files: ["skills/leaf/assets/**/*.js", "skills/leaf/packages/*/**/*.js"],
    ignores: ["skills/leaf/assets/vendor/**", "skills/leaf/packages/*/vendor/**"],
    languageOptions: { globals: browserGlobals },
    rules: { "no-undef": "error" },
  },
  {
    // The settled reading answers only for the rendering callbacks and size observers it
    // counts, so the layer and its packages reach both through runtime/rendering.js.
    files: ["skills/leaf/assets/**/*.js", "skills/leaf/packages/*/**/*.js"],
    ignores: [
      "skills/leaf/assets/vendor/**",
      "skills/leaf/packages/*/vendor/**",
      "skills/leaf/assets/runtime/rendering.js",
    ],
    rules: {
      "no-restricted-globals": [
        "error",
        ...["requestAnimationFrame", "cancelAnimationFrame", "ResizeObserver"].map(
          (name) => ({ name, message: RENDERING_MESSAGE }),
        ),
      ],
      "no-restricted-properties": [
        "error",
        {
          property: "scrollIntoView",
          message:
            "Use scrollIntoView(node, options) from landing-scroll.js or widget-api.js; native scrolling crosses the document boundary into containing samples.",
        },
        ...["window", "globalThis"].flatMap((object) =>
          ["requestAnimationFrame", "cancelAnimationFrame", "ResizeObserver"].map(
            (property) => ({ object, property, message: RENDERING_MESSAGE }),
          ),
        ),
      ],
    },
  },
  {
    files: ["skills/leaf/assets/**/*.js", "skills/leaf/packages/*/**/*.js"],
    ignores: ["skills/leaf/assets/vendor/**", "skills/leaf/packages/*/vendor/**"],
    plugins: { architecture: architecturePlugin },
    rules: {
      "architecture/standing-listeners": [
        "error",
        {
          // The owner of every focus event.
          "skills/leaf/assets/runtime/focus.js": ["focusin", "focusout"],
          // Records the raw events of a session for the interaction log, the one
          // exception that is not one element's or one subtree's own question: it is a
          // recorder of events, and reads no standing from them.
          "skills/leaf/assets/runtime/interaction-log.js": ["focusin", "focusout"],
          // A reply row's own entry begins its composition. The box's host is in the
          // row's tree, so entering its shadow tree reaches the row, and a move inside
          // it is no new entry.
          "skills/leaf/assets/runtime/thread/replies.js": ["focusin"],
          // A widget's own subtree, whose controls stand in its tree: whether focus is
          // within the gloss, and the contents link the user last stood on.
          "skills/leaf/packages/default/widgets/lf-gloss.js": ["focusin", "focusout"],
          "skills/leaf/packages/default/widgets/lf-toc.js": ["focusin"],
        },
      ],
      "architecture/placements": [
        "error",
        [
          // The one placement, and the one handing on an arrival in progress.
          "skills/leaf/assets/runtime/focus.js",
          // The text field's own `focus()`, which the placement calls, hands on to the
          // editor its shadow tree holds.
          "skills/leaf/assets/runtime/composing/text-field.js",
        ],
      ],
      "architecture/layer-returns": [
        "error",
        [
          // The owner of the hand-back and the let-go.
          "skills/leaf/assets/runtime/focus.js",
        ],
      ],
    },
  },
  {
    files: [
      "skills/leaf/assets/runtime/**/*.js",
      "skills/leaf/packages/*/runtime/**/*.js",
    ],
    plugins: { architecture: architecturePlugin },
    rules: {
      ...ownerBoundary,
      "architecture/root-state-ownership": "error",
      "architecture/semantic-store-ownership": "error",
    },
  },
  {
    // These are the two boundaries that load authored/package modules, whose paths
    // are data rather than runtime dependencies. Literal imports still enter the graph.
    files: [
      "skills/leaf/assets/runtime/interaction-gallery-playback.js",
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
    // A vendored bundle is not an owner: it initializes nothing, paints nothing, and
    // reaches no other module, so a primitive may take an algorithm from one rather
    // than write a second copy of it beside the layer's. Nor is another primitive,
    // whose own imports this same rule holds: `rendering.js`, which every rendering
    // callback is counted through, or `focus.js`, which a primitive that moves the
    // user's node asks to keep them standing on it.
    files: runtimePrimitives.map((name) => `skills/leaf/assets/runtime/${name}`),
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              regex: `^(?!/vendor/|\\.\\.?/(?:${runtimePrimitives
                .map((name) => name.replaceAll(".", "\\."))
                .join("|")})$)`,
              message:
                "Runtime primitives must remain independent of other owners; only a /vendor/ bundle or another primitive may be imported.",
            },
          ],
        },
      ],
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
  {
    // Thread folding accepts values; it must not obtain them from browser
    // stores or painters. The current derived reading has the same dependency floor.
    files: [
      "skills/leaf/assets/runtime/projection/model.js",
      "skills/leaf/assets/runtime/projection/state.js",
      "skills/leaf/assets/runtime/pending/model.js",
      "skills/leaf/assets/runtime/pending/state.js",
      "skills/leaf/assets/runtime/thread/model.js",
      "skills/leaf/assets/runtime/thread/state.js",
    ],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              regex:
                "^(?!\\.\\./(?:anchor-coordinate|collapse|semantic-state)\\.js$|(?:\\.\\./thread/|\\./)(?:identity|workflow)\\.js$|\\./model\\.js$)",
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
    files: ["skills/leaf/scripts/leaf/render-checks/init.js"],
    languageOptions: { sourceType: "script" },
  },
  {
    // runtime/history.js owns this document's session history: a Back to an entry the
    // page added returns to the place it was left at only because that owner takes the
    // traversal. The prepaint bootstrap runs before any module, and only cleans marks
    // off the address the document arrived at.
    files: ["skills/leaf/assets/**/*.js", "skills/leaf/packages/**/*.js"],
    ignores: [
      "skills/leaf/assets/runtime/history.js",
      "skills/leaf/assets/runtime/bootstrap.js",
    ],
    rules: {
      "no-restricted-properties": [
        "error",
        {
          object: "history",
          property: "pushState",
          message:
            "Add and rename history entries through runtime/history.js (pushEntry, replaceEntry), which owns traversal among them.",
        },
        {
          object: "history",
          property: "replaceState",
          message:
            "Add and rename history entries through runtime/history.js (pushEntry, replaceEntry), which owns traversal among them.",
        },
      ],
    },
  },
  {
    // An import or binding nothing reads is a dependency edge the graph still carries
    // and a name the next reader has to account for. Arguments and caught errors are
    // left alone: a signature says what a callback is handed.
    files: ["**/*.{js,mjs}"],
    rules: {
      "no-unused-vars": [
        "error",
        { args: "none", caughtErrors: "none", ignoreRestSiblings: true },
      ],
    },
  },
];
