/* Registered widget tags and import requirements in one authored scope.
 * This reading is shared by browser imports and website preload hints. It inspects
 * markup without executing a widget and ignores inert template contents, just as
 * querySelectorAll does. An arriving scope may itself be the widget being loaded.
 * Declared creations also need shared shadow rules before their first connection;
 * their constructors remain imports of the creating module.
 */
import { isElement } from "../lib/shadow-tree.js";

import { isElementName } from "./registry-contract.js";
import type { WidgetDeclaration } from "../../types/contract.js";

export type Scope = Document | DocumentFragment | Element;
export type Registry = Record<string, WidgetDeclaration>;
export function registeredTags(scope: Scope, registry: Registry) {
  const tags = new Set([
    ...(isElement(scope) ? [scope.localName] : []),
    ...[...scope.querySelectorAll("*")].map((element) => element.localName),
  ]);
  return [...tags].filter((tag) => isElementName(tag) && Object.hasOwn(registry, tag));
}

export function widgetImports(scope: Scope, registry: Registry) {
  const tags = registeredTags(scope, registry);
  // The module each tag has, which composition derives from the layer's files
  // (`$modules`, Python's `registry.contract.MODULES`).
  const held = ((registry as Record<string, unknown>).$modules ?? {}) as Record<
    string,
    string
  >;
  const modules = tags.filter((tag) => Object.hasOwn(held, tag));
  const shadow = tags.some(
    (tag) =>
      registry[tag]?.shadow ||
      Object.values(registry[tag]?.verbs ?? {}).some(
        (state) => state.creates && registry[state.creates.child]?.shadow,
      ),
  );
  return { modules, shadow };
}
