// Entry CSS is bundled as text by the vendor builder.
declare module "*.css" {
  const text: string;
  export default text;
}

// The focused DBSCAN implementation is the same constructor exposed at the
// package root, whose maintained declaration owns its API.
declare module "density-clustering/lib/DBSCAN.js" {
  import { DBSCAN } from "density-clustering";
  export default DBSCAN;
}
