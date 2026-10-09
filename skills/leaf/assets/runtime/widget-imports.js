/* Registered widget tags and import requirements in one authored scope.
 * This reading is shared by browser imports and website preload hints. It inspects
 * markup without executing a widget and ignores inert template contents, just as
 * querySelectorAll does. An arriving scope may itself be the widget being loaded.
 */
export function registeredTags(scope, registry) {
  const tags = new Set([
    ...(scope.localName ? [scope.localName] : []),
    ...[...scope.querySelectorAll("*")].map((element) => element.localName),
  ]);
  return [...tags].filter((tag) => Object.hasOwn(registry, tag));
}

export function widgetImports(scope, registry) {
  const initializers = [];
  const modules = [];
  for (const tag of registeredTags(scope, registry)) {
    const entry = registry[tag];
    if (entry?.["x-initial"]) initializers.push({ tag, path: entry["x-initial"] });
    if (entry?.["x-upgrade"]) modules.push(tag);
  }
  return { initializers, modules };
}
