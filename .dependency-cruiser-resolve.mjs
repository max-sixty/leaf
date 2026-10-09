// Dependency-cruiser's supported resolver seam reads the served runtime addresses.
// The owner configuration supplies their one source-to-resource mapping.
import { runtimeAliases } from "./.dependency-cruiser.mjs";
export default { resolve: { alias: runtimeAliases } };
