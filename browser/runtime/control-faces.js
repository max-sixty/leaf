/* The canonical face for each control role, shared by DOM writers and pure templates.

   Leaf's controls come from a closed set of roles, and each role wears one face
   (components/controls.css). A widget names the role and never the face's classes,
   so two controls of one kind cannot be drawn two ways; this table is the only place
   the classes are spelled (`test_controls_are_built_by_role_and_never_by_face` in
   `tests/model/test_interact_layer.py` holds that), and every press a bundled module
   builds wears one (`test_every_press_is_built_by_role_or_family`).

   - `symbol`: a press drawn as one of Leaf's icons, named by its tooltip and
     accessible name (browser/AGENTS.md): quiet at rest, the chip under a hovering
     pointer or visible focus.
   - `word`: a press that says what it does in words, quiet as a symbol is. A toggle
     is a word whose `aria-pressed` the theme draws as selected.
   - `commit`: the one press on a surface that commits the user's work, framed in the
     accent.
   - `mark`: a small symbol seated on the thing it acts on, at a corner or on a
     block's border toolbar, where a larger face would cover the thing.
   - `inline`: a press read as part of the line of words it stands in, such as a
     thread's held news or a quote's Full quote, drawn as words in the accent at the
     line's size with no frame. One that announces news waiting says so with
     `data-lf-news`, which draws it in the danger ink, and one whose words say a
     warning with `data-lf-tone="warn"`, in the warning's.
   - `row`: one row of a list or menu, whose words are what the reader scans, so they
     stand in the ink; the row under the pointer or the keys is washed, and the row
     the list stands on (`aria-current`) wears the accent's stripe and tint.
   - `answer`: one of the answers a question offers, such as a decision's choices on
     an On me card, framed so the set reads as one to pick from, the chosen one
     (`aria-pressed`) marked in the ok tone as the page marks its chosen option.
   - `entry`: a margin entry, a glyph out in the page's margin whose label a pointer
     or a key reveals, framed by what it promises: an action raised, a disclosure
     ringed, a status ghosted (contribution-controls.js). A reaction in the margin is
     an entry.
   - `reaction`: a reaction's token in a message's strip, its own glyph rather than
     an action's symbol, quiet until hovered and kept in the accent while in force.
   - `response`: a choice of the response bar, Comment, Suggest or a reaction, which
     floats over the page and so wears the field's frame, height and lift
     (widget-elements.js, `responseAction`).
   - `gutter`: a line's number in a code view's gutter, which takes a comment on its
     line, as a diff's do: the number in the code's muted ink, a + before it under
     the keys.
   - `picture`: a picture that opens larger in the media viewer, a message's or a
     draft's, whose face is the picture itself, unframed, under a magnifier.

   A difference that was only a past choice is not a role: a symbol once came bordered
   in some widgets and quiet in others, a word framed in some, quiet in others and a
   list's row in a third, four presses among words drew four faces of their own, seven
   lists drew their rows six ways, and the floating panel drew its own face for every
   control in it, before each merged. */
const ACTION_FACES = {
  symbol: "lf-icon-action",
  word: "lf-btn",
  commit: "lf-btn primary",
  mark: "lf-mark-action",
  inline: "lf-inline-action",
  row: "lf-row",
  answer: "lf-answer",
  entry: "lf-margin-face",
  reaction: "lf-reaction",
  response: "lf-response-face",
  gutter: "lf-gutter",
  picture: "lf-picture",
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
