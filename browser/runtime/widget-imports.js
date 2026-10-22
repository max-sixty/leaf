/* Registered widget tags and import requirements in one authored scope.
 * This reading is shared by browser imports and website preload hints. It inspects
 * markup without executing a widget and ignores inert template contents, just as
 * querySelectorAll does. An arriving scope may itself be the widget being loaded.
 * Declared creations also need shared shadow rules before their first connection;
 * their constructors remain imports of the creating module.
 */
import { isElementName } from "./registry-contract.js";

export function registeredTags(scope, registry) {
  const tags = new Set([
    ...(scope.localName ? [scope.localName] : []),
    ...[...scope.querySelectorAll("*")].map((element) => element.localName),
  ]);
  return [...tags].filter((tag) => isElementName(tag) && Object.hasOwn(registry, tag));
}

export function widgetImports(scope, registry) {
  const initializers = [];
  const modules = [];
  const tags = registeredTags(scope, registry);
  for (const tag of tags) {
    const entry = registry[tag];
    if (entry?.["x-initial"]) initializers.push({ tag, path: entry["x-initial"] });
    if (entry?.["x-upgrade"]) modules.push(tag);
  }
  const shadow = tags.some(
    (tag) =>
      registry[tag]["x-shadow"] ||
      Object.values(registry[tag]["x-state"] ?? {}).some(
        (state) => state.creates && registry[state.creates.child]["x-shadow"],
      ),
  );
  return { initializers, modules, shadow };
}
