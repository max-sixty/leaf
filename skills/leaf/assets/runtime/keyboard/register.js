/* Core scope declarations join the element register at boot. Readers inspect the same
   objects; this module never imports a feature to discover its commands. */
import { bindings } from "./bindings.js";
export const ELEMENTS = Symbol("the scopes of the focused element");
let scopes;
let reference;
let typing;
let workspace;
export function registerPageScopes(
  declarations,
  universalReference,
  textEntry,
  workspaceLayer,
) {
  scopes = declarations;
  reference = universalReference;
  typing = textEntry;
  workspace = workspaceLayer;
}
export const pageScopes = () => scopes;
export const universalReference = () => reference;
export const allButTheReference = (binding) => !bindings(reference).includes(binding);
export const textEntryScope = () => typing;
export const coveringWorkspaceSurface = () => workspace.coveringSurface();
export const coveringWorkspaceFocus = () => workspace.coveringFocus();
export const workspaceAllowsNativeLayer = (node, establishedOver) =>
  workspace.allowsNativeLayer(node, establishedOver);
export const openWorkspaceSurfaceFor = (node) => workspace.openSurfaceFor(node);
