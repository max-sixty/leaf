/* Registration and preparation of publication-owned widget implementations.
   Native registries and module promises are physical owners, never semantic state.
   A temporary scoped shadow root upgrades original nodes before their first mount;
   those nodes retain their registered implementation in the ordinary light DOM. */
import { runtimeModule, runtimeResource, offlineInteractive } from "./context.js";
import { widgetImports } from "./widget-imports.js";
import {
  knownVocabulary,
  rememberVocabulary,
  bindVocabulary,
  vocabularyFor,
} from "./widget-contexts.js";
const preparations = new Map();

export function publicationVocabulary(revision, declarations, root, primary = false) {
  if (knownVocabulary(revision)) return knownVocabulary(revision);
  const registry = primary ? customElements : new window.CustomElementRegistry();
  const scope = document.createElement("div").attachShadow({ mode: "open", registry });
  const resource = (path) =>
    offlineInteractive ? runtimeResource(`${root}${path}`) : `${root}${path}`;
  const module = (path) => runtimeModule(`${root}${path}`);
  const modules = new Map();
  const initializers = new Map();
  const context = Object.freeze({
    revision,
    declarations,
    registry,
    resource,
    scope,
    shadowRules: { text: "", loading: null },
    register(tag, constructor) {
      const existing = registry.get(tag);
      if (existing && existing !== constructor)
        throw new Error(
          `Leaf vocabulary r${revision} already owns a different ${tag} constructor`,
        );
      if (!existing) registry.define(tag, constructor);
    },
    async load(root) {
      await Promise.all(
        widgetImports(root, declarations).modules.map((tag) => {
          if (!modules.has(tag))
            modules.set(
              tag,
              import(module(`/widgets/${tag}.js`)).then(({ default: constructor }) => {
                context.register(tag, constructor);
              }),
            );
          return modules.get(tag);
        }),
      );
    },
    loadInitializer(path) {
      if (!initializers.has(path))
        initializers.set(
          path,
          new Promise((resolve, reject) => {
            const script = document.createElement("script");
            script.src = resource(path);
            script.dataset.lfVocabulary = String(revision);
            script.onload = () => {
              script.remove();
              resolve();
            };
            script.onerror = () => {
              script.remove();
              reject(
                new Error(
                  `Leaf vocabulary r${revision} initial renderer failed: ${path}`,
                ),
              );
            };
            document.head.append(script);
          }),
        );
      return initializers.get(path);
    },
    prepare(markup) {
      const template = document.createElement("template");
      template.innerHTML = markup;
      const root = template.content;
      bindVocabulary(root, context);
      for (const element of root.children)
        element.dataset.lfVocabulary = String(revision);
      return root;
    },
    upgrade(root) {
      scope.append(...root.childNodes);
      registry.upgrade(scope);
      root.append(...scope.childNodes);
      return root;
    },
    importNode(node) {
      const imported = scope.importNode(node, true);
      bindVocabulary(imported, context);
      return imported;
    },
    createElement(tag) {
      const element = scope.createElement(tag);
      bindVocabulary(element, context);
      return element;
    },
  });
  rememberVocabulary(context);
  return context;
}
export function requireVocabulary(revision, root) {
  if (preparations.has(revision)) return preparations.get(revision);
  if (knownVocabulary(revision)) return Promise.resolve(knownVocabulary(revision));
  const preparation = (async () => {
    const response = await fetch(
      offlineInteractive
        ? runtimeResource(`${root}/registry.json`)
        : `${root}/registry.json`,
    );
    if (!response.ok)
      throw new Error(
        `Leaf vocabulary r${revision} failed to load (${response.status})`,
      );
    const context = publicationVocabulary(revision, await response.json(), root);
    const stylesheet = document.createElement("link");
    stylesheet.rel = "stylesheet";
    stylesheet.href = offlineInteractive
      ? runtimeResource(`${root}/widget-theme.css`)
      : `${root}/widget-theme.css`;
    const loaded = new Promise((resolve, reject) => {
      stylesheet.onload = resolve;
      stylesheet.onerror = () =>
        reject(
          new Error(
            `Leaf vocabulary r${revision} stylesheet failed to load: ${stylesheet.href}`,
          ),
        );
    });
    document.head.append(stylesheet);
    await loaded;
    return context;
  })();
  preparations.set(revision, preparation);
  return preparation;
}
export function createWidgetElement(owner, tag, constructor) {
  const context = vocabularyFor(owner);
  context.register(tag, constructor);
  return context.createElement(tag);
}
