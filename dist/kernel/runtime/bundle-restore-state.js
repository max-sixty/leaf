import {
  DESIGN_MODE_KEY,
  tabStore
} from "./bundle-user-place.js";

// runtime/restore-state.js
var ANNOTATIONS_KEY = "lf-annotations";
var USER_VIEW_RESTORE_CASES = [
  { name: "design mode on", ...tabStore.where(DESIGN_MODE_KEY), value: "1" },
  { name: "annotations hidden", ...tabStore.where(ANNOTATIONS_KEY), value: "hidden" }
];
function restoreUserView({ setDesignMode }) {
  if (tabStore.get(DESIGN_MODE_KEY) === "1") setDesignMode(true, { spoken: false });
}

export {
  ANNOTATIONS_KEY,
  USER_VIEW_RESTORE_CASES,
  restoreUserView
};
