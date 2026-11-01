/* The canonical face for each control role, shared by DOM writers and pure templates. */
const ACTION_FACES = {
  symbol: "lf-icon-action",
  word: "lf-btn",
  commit: "lf-btn primary",
  mark: "lf-mark-action",
  inline: "lf-inline-action",
  row: "lf-row",
};

/** @param {LeafActionRole} role */
export function actionClass(role, className = "") {
  const face = ACTION_FACES[role];
  if (!face)
    throw new TypeError(
      `A control's role is one of ${Object.keys(ACTION_FACES).join(", ")}, not ${role}`,
    );
  return className ? `${face} ${className}` : face;
}
