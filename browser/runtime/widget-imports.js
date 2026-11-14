/* Registered widget tags and import requirements in one authored scope.
 * This reading is shared by browser imports and website preload hints. It inspects
 * markup without executing a widget and ignores inert template contents, just as
 * querySelectorAll does. An arriving scope may itself be the widget being loaded.
 * Declared creations also need shared shadow rules before their first connection;
 * their constructors remain imports of the creating module.
 */
import { isElement } from "./shadow-tree.js";

import { isElementName } from "./registry-contract.js";

/** @typedef {Document | DocumentFragment | Element} Scope
 * @typedef {Record<string, import("../types/contract.js").WidgetDeclaration>} Registry */
/** @param {Scope} scope @param {Registry} registry */
export function registeredTags(scope, registry) {
  const tags = new Set([
    ...(isElement(scope) ? [scope.localName] : []),
    ...[...scope.querySelectorAll("*")].map((element) => element.localName),
  ]);
  return [...tags].filter((tag) => isElementName(tag) && Object.hasOwn(registry, tag));
}

/** @param {Scope} scope @param {Registry} registry */
export function widgetImports(scope, registry) {
  const tags = registeredTags(scope, registry);
  // The module each tag has, which composition derives from the layer's files
  // (`$modules`, Python's `registry.contract.MODULES`).
  const held = /** @type {Record<string, string>} */ (
    /** @type {Record<string, unknown>} */ (registry).$modules ?? {}
  );
  const modules = tags.filter((tag) => Object.hasOwn(held, tag));
  const shadow = tags.some(
    (tag) =>
      registry[tag]?.["x-shadow"] ||
      Object.values(registry[tag]?.["x-state"] ?? {}).some(
        (state) => state.creates && registry[state.creates.child]?.["x-shadow"],
      ),
  );
  return { modules, shadow };
}
