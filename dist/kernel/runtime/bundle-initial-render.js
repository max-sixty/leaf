//#region runtime/initial-render.js
const coordinator = (node) => node.ownerDocument?.documentElement?.lfInitial ?? document.documentElement.lfInitial;
const initialRender = (host) => coordinator(host).paint(host);
const initialOrigin = (node) => coordinator(node).origin(node) ?? node;
const initialParent = (node) => coordinator(node).parent(node);
const authoredBody = (host) => coordinator(host).authoredBody(host);
const initialSource = (node) => coordinator(node).reading(node);
const restoreInitialSource = (root) => coordinator(root).restoreSource(root);
const unmarkedCopy = (node) => coordinator(node).authoredCopy(node);
const fragmentId = (fragment) => document.documentElement.lfInitial.fragmentId(fragment);

//#endregion
export { authoredBody, fragmentId, initialOrigin, initialParent, initialRender, initialSource, restoreInitialSource, unmarkedCopy };