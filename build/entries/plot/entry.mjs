// Plot under its own name, the `Plot` an author's chart reads, and beside it the
// channels a mark's tip says and the lines it says them in, which Plot works out only
// inside its tip's drawing (`getSourceChannels`, `formatChannels`). lf-chart reads
// Plot's answer through them rather than keeping a copy of Plot's rules. Plot's module
// keeps both private, so neither has a declaration; the plot row's adaptation in
// vendor.mjs exports them as the bundle loads the module. Plot ships as that one
// module, so `Plot` is its exports less these two, leaving an author Plot's own API.
import * as everything from "@observablehq/plot";

// @ts-expect-error: private to Plot's module, exported by the adaptation.
const { getSourceChannels: tipSources, formatChannels: tipRows, ...Plot } = everything;
export { Plot, tipRows, tipSources };
