// https://github.com/sverweij/dependency-cruiser
//
// The runtime's import layers (`layers` in `dependency-cruiser.mjs`) over the graph of
// what each module names: its imports and the types its JSDoc names. A type stands in
// its module's layer as an import does, so it points down too. The other rules read
// what a module loads, which a type doesn't, so they run over the imports alone.
//
// dependency-cruiser reads JSDoc only through a TypeScript parser below version 7, and
// without one reads the imports alone and says nothing, so the pre-commit hook installs
// one beside it.

import config, { layering } from "./dependency-cruiser.mjs";

export default {
  forbidden: layering,
  options: { ...config.options, detectJSDocImports: true },
};
