# Goal: the floating Leaf panel

> **Status (2026-10-20): landed.** The floating panel is Leaf's only chrome (#3100).
> Its contract lives in the header of `skills/leaf/assets/runtime/floating-panel.js`
> and in `skills/leaf/assets/styles/floating-panel.css`. TODO #28 holds what remains:
> the user's review of the desktop design, then the phone. The build's goal, the
> approved prototype, the user's requirements in their own words and the review
> process are in Git history; `d91b67b26` is the last commit holding them.

## Intended departures from the prototype

These are the build's departures from the prototype the user approved on 10 October;
the code now records each decision beside the rules that carry it.

- **The resting row holds the comment field.** The Leaf arrangement rests as the
  mark with counts and opens the field on the first click. The user asked for
  the field at rest (see "A resting box"). The prototype's **Line** arrangement
  shows a resting field, with On me and annotating beside it; use it as the
  reference for this row. The user chose Leaf over Line on 10 October and asked
  for the box back on 11 October. So everything except the resting row follows
  the Leaf arrangement: the mark, its menu, and how everything opens above the
  row.
- **The box resizes from its foot, in one step, and its surface follows.** The row
  stays put; the leaving view fades out (60 ms) before the arriving one fades in (90
  ms), and the surface layer follows the box's outline by a clip on the Codex panel's
  `cubic-bezier(.23,1,.32,1)`: 300 ms as the field grows a line, 120 ms as a view
  opens or closes, since the user found views slow to appear (15 October). (The first
  build tweened the card's height; a layout tween's last frame landed outside CI's
  input window as a shift.)
- **The focused field shows no ground, and wears the anchored comment box's focus
  ring** while it holds the caret, so a key that moves the caret there, `c` among
  them, shows where the words will go (the user's pick, #3097). A dark frame around
  the field at rest was the previous attempt's "form" look.
- **While the user types, Send floats in the field's end corner,** as an anchored
  comment box's does, and the counts step aside for the field; they come back when
  the caret leaves, and the line naming where the words go stays while the field holds
  words. Every line but the last runs the field's width. (The user chose the corner on
  15 October over Send standing beside the words, which kept its width empty beside
  every line.)
- **A long draft offers more room at a press:** past three lines a mark over the
  field's end widens the panel to 760px and lets the field take most of the window;
  it folds back when the field empties. The user chose this on 15 October over the
  panel widening by itself, which re-wraps every line under the caret.
- **The line over the field names where the words go only once they hide the
  placeholder that said it,** in the placeholder's words ("Comment on the page"), and
  never who reads them: the page has one agent. It shows only with no view open; over
  a view it repeated the view's head, so the user dropped it there (#2913).
- **The answer the user waits for grows the thread's view,** up to its height limit,
  with New reply only past it; other news in an open thread still moves nothing. The
  user chose growth over a reserved New reply slot on 14 October (#2916).
- **Answers are the widget's own choices** (a multiple-choice obligation shows its options and
  Done), recorded exactly as on the page; the On view has On me / On {agent} / Done.
- **Messages draw with Leaf's own reader** (the panel is a registered thread
  presentation), so questions, reactions and HTML replies work in the panel.
- **The menu carries the banner's inventory,** drawn from each contributor's declared
  row, less what the row and its views already hold (Threads, On me, the page
  comment, approval). Navigate, Annotations, About and Versions take the menu's place
  in the same box, sliding in from the right under a head that goes back; Threads and
  On, which are read rather than chosen from, open as views. The user chose this on 15
  October ("expecting it to feel like it's navigating right … and then there's no way
  to go back"), over the view keeping its place with a "‹ Menu /" crumb.
- **On a phone, a count at rest is its number beside an icon,** so the agent's status
  keeps the field ("numbers next to icons rather than saying whole words").
- **Passing notices and a walk's position are said in the empty field** (the
  overhaul; on 16 October the user asked that whatever is not anchored to the page
  stand at the panel rather than against the window).
- **The panel shows no key hints**, neither the bottom bar's resting hints nor the
  `g` sequence's destination list: the menu's rows carry their shortcuts and `?` opens
  the full reference. The user chose this over one or two hints in the line above the
  field on 13 October, to keep the panel quietest.
