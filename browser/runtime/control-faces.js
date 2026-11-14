/* The canonical face for each control role, shared by DOM writers and pure templates.

   Leaf's controls come from a closed set of roles, and each role wears one face
   (components/controls.css). A widget names the role and never the face's classes,
   so two controls of one kind cannot be drawn two ways; this table is the only place
   the classes are spelled (`test_controls_are_built_by_role_and_never_by_face` in
   `tests/model/test_interact_layer.py` holds that), and every press a bundled module
   builds wears one (`test_every_press_is_built_by_role`). Only the role's rules, the
   library's generated into styles/vendor/webawesome-native.css and Leaf's in
   controls.css, draw its ink, ground, frame and lift, keyed by its face class and the
   attributes a press declares, which are its states and the variants named below
   (`test_a_press_wears_its_role_s_face_alone`); the class a widget writes beside the
   role places the press, and the widget sets its type and density.

   - `symbol`: a press drawn as one of Leaf's icons, named by its tooltip and
     accessible name (browser/AGENTS.md): quiet at rest, with the library's fill under
     a hovering pointer, and the chip while what it opens shows (`aria-expanded`). One
     that commits what it stands in, as Send and a rewrite's Save do, is in the
     accent (`data-lf-tone="accent"`). A disc (`data-lf-disc`) is drawn in its
     action's own ink (`data-lf-tone`: `accent`, `ink`, `positive` or `negative`) and
     shows its state on a disc behind the glyph rather than a chip, as the composer's
     Send and Dictate and a thread's Resolve and Reopen do.
   - `word`: a press that says what it does in words, quiet as a symbol is. A toggle
     is a word whose `aria-pressed` the theme draws as selected.
   - `commit`: the one press on a surface that commits the user's work, framed in the
     accent; pressed (`aria-pressed`), as a question's Done once answered, in the ok
     tone.
   - `mark`: a small symbol seated on the thing it acts on, at a corner or on a
     block's border toolbar, where a larger face would cover the thing. One riding a
     corner stands on a patch of its ground (`data-lf-corner`), and one standing alone
     as its block's toolbar, as a code block's Copy does, wears the toolbar's frame
     (`data-lf-bar`).
   - `inline`: a press read as part of the line of words it stands in, such as a
     thread's held news or a quote's Full quote, drawn as words in the accent at the
     line's size with no frame. One that announces news waiting says so with
     `data-lf-news` and keeps the accent the unread dot wears. One standing among
     a box's empty words (`data-lf-hint`), as a passing notice's Undo does at the
     floating panel field's end, wears those words' dim face, as the word and key that
     enter the box do (composing/input.js, `pressAtRest`).
   - `row`: one row of a list or menu, whose words are what the reader scans, so they
     stand in the ink; the row under the pointer or the keys is washed, and the row
     the list stands on (`aria-current`) wears the accent's stripe and tint. A step
     still ahead of it (`data-lf-ahead`) stands in the muted ink, and the row of the
     thread whose passage the pointer is on (`.lf-mark-hover`) in that passage's
     wash. A row that is its group's band (`data-lf-band`), as Done and Resolved are,
     takes the band's ink. A thread's row on the user's turn says so in its closing
     words.
   - `answer`: one of the answers a question offers, such as a decision's choices on
     an On Me card, framed so the set reads as one to pick from, the chosen one
     (`aria-pressed`) marked in the ok tone as the page marks its chosen option.
   - `entry`: a margin entry, a glyph out in the page's margin whose label a pointer
     or a key reveals, framed by what it promises: an action raised, a disclosure
     ringed, a status ghosted (contribution-controls.js), with its tone
     (`data-lf-tone`) on its glyph. A change's entry, a disclosure, is raised as an
     action is (`data-lf-kinds="change"`). One in force (`aria-pressed`), as a reaction the
     user left in the margin is, stands on the chip, and a row standing as a pin over
     its block (`data-lf-place="pin"`) fills its entries with the pin's attention
     colour.
   - `reaction`: a reaction's token in a message's strip, its own glyph rather than
     an action's symbol, quiet until hovered and kept in the accent while in force.
   - `response`: a choice of the response bar, Comment, Suggest or a reaction, which
     floats over the page and so wears the field's frame, height and lift
     (widget-elements.js, `responseAction`); a reaction among them is a toggle
     (`aria-pressed`) and wears a reaction's states.
   - `gutter`: a line's number in a code view's gutter, which takes a comment on its
     line, as a diff's do: the number in the code's muted ink, a + before it under
     the keys. The keys reach its line through the target picker, so Go-to gives it
     no chip of its own (keyboard/go-to-sequence.js).
   - `picture`: a picture that opens larger in the media viewer, a message's or a
     draft's, whose face is the picture itself, unframed, under a magnifier. One that
     crops or draws its picture, as a draft's attachment and drawing do, wears a
     picture's frame (`data-lf-frame`).
   - `fold`: the line a folded group stands as, such as a settled decision's "Settled ·
     Ship Friday" over its options, which opens and closes the group
     (`aria-expanded`). It runs the group's width, its words at weight 600 after the
     disclosure arrow (`.lf-disclosure-marker`), unframed until a hovering pointer
     draws its edge.
   - `proxy`: a hidden stand-in, for the keyboard or a screen reader, for something on
     the page the pointer takes by itself: a gloss's phrase, a commented block (its
     comment note), a picture and its declared parts (their response proxies). Its face
     is an invisible carrier, a pixel out of flow that takes no pointer, since what it
     stands for is what the user sees. Its focus rings that thing with the ring the
     thing would wear focused itself, and that thing is in view: a gloss's proxy stands
     at its phrase, so the browser's own focus scroll shows it, and the phrase wears
     the ring on visible focus, since a press on the phrase focuses it too (gloss.css);
     a note or a picture's proxy stands on the details shelf, apart from the page,
     which nothing but the keys or assistive technology reaches, so any focus on it
     rings its target and brings the target into view (details-shelf.js).

   A difference that was only a past choice is not a role: a symbol once came bordered
   in some widgets and quiet in others, a word framed in some, quiet in others and a
   list's row in a third, four presses among words drew four faces of their own, seven
   lists drew their rows six ways, and the floating panel drew its own face for every
   control in it, before each merged. */
const ACTION_FACES = {
  symbol: "lf-icon-action",
  word: "lf-btn",
  commit: "lf-btn lf-commit",
  mark: "lf-mark-action",
  inline: "lf-inline-action",
  row: "lf-row",
  answer: "lf-answer",
  entry: "lf-margin-face",
  reaction: "lf-reaction",
  response: "lf-response-face",
  gutter: "lf-gutter",
  picture: "lf-picture",
  fold: "lf-fold",
  proxy: "lf-proxy",
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
