/* The Leaf application this document mounted, for code that must reach it without
   loading it. `mountApplication` sets it once; a document Leaf doesn't serve never
   does. Effect UI widgets' services (widget-services.js) read it, so a widget there
   loads none of the application, and a call made on a Leaf page runs in the task of
   the input that asked rather than after a module load. */

/** @typedef {{
 *   navigateToDatum: typeof import("./application.js").navigateToDatum,
 *   obligationActions: typeof import("./application.js").obligationActions,
 *   threadActions: typeof import("./application.js").threadActions,
 * }} MountedApplication */

/** @type {MountedApplication | null} */
let current = null;

/** The mounted application, or null where none is.
 * @returns {MountedApplication | null} */
export const mounted = () => current;

/** @param {MountedApplication} application */
export const setMounted = (application) => {
  current = application;
};
