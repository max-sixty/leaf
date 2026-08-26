/* The one helper surface behavior modules import.

   Domain owners stay directly importable to the browser entry while this module
   decides which of their capabilities widgets may rely on. The entry module still
   contains most helper implementations; its reexport is temporary until those
   implementations move to their owners. */
export * from "../leaf.js";
export { tabStore } from "./storage.js";
export { langForPath, synNodes, syntax, tokenLines } from "./syntax.js";
