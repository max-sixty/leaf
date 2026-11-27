// Compiled from mounted.ts by build/typescript.mjs; edit that file.
/* The Leaf application this document mounted, for code that must reach it without
   loading it. `mountApplication` sets it once; a document Leaf doesn't serve never
   does. Effect UI widgets' services (widget-services.js) read it, so a widget there
   loads none of the application, and a call made on a Leaf page runs in the task of
   the input that asked rather than after a module load. */

let current = null;

/** The mounted application, or null where none is. */
export const mounted = () => current;

export const setMounted = (application) => {
  current = application;
};
