// Plot under its own name, the `Plot` an author's chart reads, so that the module's
// other export stays out of it: the channels a mark's tip says and the words its
// `format` gives each, which Plot works out only inside its tip's drawing
// (`getSourceChannels`). lf-chart reads Plot's answer through it rather than keeping
// a copy of Plot's rule.
export * as Plot from "@observablehq/plot";
// @ts-expect-error: Plot's module keeps it private, so it has no declaration; the plot
// row's adaptation in vendor.mjs exports it as the bundle loads the module.
export { getSourceChannels as tipSources } from "../../../node_modules/@observablehq/plot/src/marks/tip.js";
