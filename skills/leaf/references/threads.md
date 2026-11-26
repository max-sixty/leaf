# Threads

Open a thread when the answer depends on the user. Add `--obligation` to put the
message on their On Me list until they answer. The message itself supplies the
request; no widget is needed, though a question whose answers you can list
usually takes them as a choice instead ("Ask for a pick"). Anchor it with a quote for a passage, a section id
for a diagram or image, a declared part for one box within a visual, or nothing for
the page as a whole:

```bash
leaf thread create <page> --quote "<passage in the current page>" --title "…" --obligation --text "…?"
leaf thread create <page> --section <element-id> --title "…" --text "…"
leaf thread create <page> --section <visual-id> --part <part-id> --title "…" --text "…"
leaf thread create <page> --title "…" --obligation --text "…?"
```

A visual is a widget whose declaration in `leaf page vocabulary <page>` has a `visual`
key, such as a diagram or a chart. Where that key gives `prefixes`, a thread can name
one part of the visual. Copy a part's id from `leaf page state <page>`, which
lists the parts a thread can name in each visual as `parts` on the visual's entry in
`elements`, each with its `id` and `label`. The list appears once `page check --render`,
or the page's server after you hand the page over, has read the version the page shows
with the data it holds now. So run the check if the visual has no `parts`, as after you
save the page or update its data. A visual lists only the parts it had drawn when the
check read it. A part it finds only when asked, such as a chart's single data point, or
draws only while a view of it is open, is missing from the list; name such a part as the
widget's guidance says.

`leaf thread create` anchors in the active revision as the user sees it. Quote exact
words the user can see, within one widget part, including words a page's script
draws. The command refuses a quote that matches more than one place, or is retired,
replaced, or crosses a boundary, rather than open a thread with no anchor. The thread's id is
the `id` of its opening comment, in the record the command prints.
`leaf page state <page> <message>`, `leaf thread reply`, `edit`, `resolve` and
`reopen` take the id of any message in the thread.

Link directly to a thread by adding `thread=<message-id>` to the page URL's query
parameters, preserving any existing access parameters: `?thread=<message-id>`, or
`&thread=<message-id>` when a query is already present. The link takes the user to
the thread's usual card or reader, including a page-level thread with no anchor, and
a reply's id lands them on that reply. A message's Copy link copies such a link, so
one the user pastes names a message by its id. With
an `#element-id` as well, the page lands on that element and the thread opens without
taking the user there. Input during startup cancels the automatic opening. The page
keeps `thread=` in its own address while a thread stands open, so a link the user
copies from the address bar names the thread they have open.

When the user comments on repeated words that the surrounding text cannot tell
apart, Leaf keeps the quote but not which copy they meant. The comment has
`anchor.detached: true`, and Threads keeps it with the quote it was about.

Threads lists each thread by its title, a few words naming its subject. Give one
with `--title` when you open a thread. When the user opens a thread,
Leaf usually titles it as they post. Where it hasn't, give `--title` on your first
reply in the thread; a reply without one is refused.

```bash
leaf thread create <page> --section <element-id> --title "Afternoon workshop" --text "…"
leaf thread reply <answer.ref> --done --title "Afternoon workshop" --text "…"
```

Keep a title stable. When it no
longer describes the discussion, rename it with
`leaf thread edit <page> <message> --title "<a few words>"`, which adds no
message.

A message is Markdown, and HTML in it draws where you write it, as on GitHub: a
formula inside a sentence, a native table, a bounded log, or a choice ("Ask for a
pick" below). Native HTML needs no widget wrapper. Leaf reads it by CommonMark's
rules, as GitHub does. Start a block of HTML after a blank line, with its opening tag
alone on its line. Markdown doesn't read the block's own lines, so backticks in a
`<summary>` or a choice's option show as typed; mark code there with `<code>`. The
next blank line ends the block and Markdown resumes, so a blank line inside a widget
or `<details>` splits it. Text whose blank lines matter, such as
code, goes in a Markdown fence or in a `<pre>` opening its own line after a blank
line; inside a widget, leave a blank line before and after it. HTML among words
belongs to their paragraph, and Markdown still reads the words inside it. Write a `<`
meant as text in backticks or as `&lt;`. Ids must be new, used in no
version of the page and no earlier message. Leaf checks the HTML as it checks a page,
and refuses document settings or a stylesheet for the whole page. An `lf-sample`
template gives the user a live practice page in the thread (`live-samples.md`).

```bash
leaf thread reply <answer.ref> --done <<'EOF'
The deploy passed.

<details>
<summary>Log of <code>make deploy</code></summary>
<pre>Ready
Done</pre>
</details>
EOF
```

Leaf checks the HTML when you post it, and draws a data widget, such as a chart or
diagram, once first: a widget that fails to draw refuses the message with its error.
Fix it and post again. Where Leaf has no browser, the failure reaches you instead as an
`error` event when the user opens the thread; answer with a corrected reply.

A thread shows in a narrow card or panel, so a paragraph that reads fine in chat is a
wall there. The user should take in at a glance what a message tells them and what it
asks of them. A message is generally a sentence or two; where it has several points,
give each a short paragraph or item, and a question a paragraph of its own. The page
carries the work. Record a decision, result, or deferred work on the page and link it
from the reply with a fragment link such as
`[the decision](#decision)`, which previews its target while the user points at it and
opens any tab or group hiding it. The thread already reaches the passage or section it
is on, as a card beside it or by Show on page in the panel, so a link to it takes the
user nowhere new; say in words what changed in it. To point
at lines of an `lf-code` block, put them after its id and a colon, in the grammar of
its `hi` attribute: `[the retry](#client:12-18)`. Where
the reasoning matters to someone using the result, keep the thread anchored to that
section. Where a message rests on a source, such as a rule, a file or an earlier
message, quote the whole passage it turns on, conditions included, so the user can
check the message against it where they read; a passage longer than a few lines goes
in a `<details>`.

Use `--text` for a one-liner, and `--file`, or a heredoc on stdin, for anything
longer. A `math` fence holds a display formula, and `<code class="language-math">` a
formula inside a sentence, where Markdown still reads the LaTeX: write `\\{` for `\{`
and `\*` for `*` (`page-authoring.md`, "Markup").

To send an image, run `leaf page media <page> <file>`
and put the `path` it prints in your text as a Markdown image.

`leaf thread reply` takes either a delivered `answer.ref` or a page and message id:

```bash
leaf thread reply <answer.ref> --done --text "The deploy passed."
leaf thread reply <page> <message> --text "The monitoring window has ended."
```

Use the whole `answer.ref` when answering a delivered update or posting progress on
it. The reference identifies the page, thread and exact input being answered.
A message posted by page and message id answers nothing, so an answer its thread
owes stays owed.
While the session an update was delivered to holds the page,
`leaf page state` shows the same `ref` on the update's `answer`. A reply on a `ref`
delivered before the user's newer correction does not answer that correction.

Successful answers check the saved `index.html` and make it the active revision
with the answer; the first answer on a revision also notes the advice `page check`
gives. Progress and failure reports use the active revision without checking or
publishing an in-progress draft. Rerunning an
answer with the same `ref`, text and flags adds nothing.

When an answer has `writer: "turn"`, which only a Codex turn receives, your turn's
final text answers it, and `harness-codex.md`, "Replies", says when to use
`leaf thread reply` instead. To
have a command hub worker answer, forward it the `answer.ref` as that package's
coordinator instructions say.

## Preserve revised anchors

When a revision rewrites a quoted passage, check every open thread on it, including
ones you are not answering this turn. `leaf page check`, and the first successful
reply on a revision, list each open thread whose anchor no longer resolves and where the
revision moves it: to its section if that survives, otherwise detached.

Where you know what replaced the passage, move the thread onto it in the reply that
reports the change, with `--section`, narrowed by `--quote` or, in a visual,
`--part`:

```bash
leaf thread reply <answer.ref> --done --section <element-id> --quote "<new passage>" --text "Updated this and moved the thread to the result."
```

When the subject itself leaves the page, detach the thread rather than moving it onto
nearby content:

```bash
leaf thread reply <answer.ref> --done --detach --text "Removed this; the thread no longer has a page target."
```

A detached thread stays open in Threads, its quote marked as not in the latest
version. A later reply may move it to a real replacement;
open a new thread for a different subject. Don't resolve a thread to get rid of an
anchor you removed: Leaf leaves a resolved thread's anchor as it was, so if the user
reopens it, it points at something the page no longer shows.

Every answer declares whose move it leaves:

- `--obligation`: the user's. It leaves them a decision, or something to try or
  review before making one, or asks them for an answer or permission. It creates
  `message:<its id>` on On Me until their next reply or a settling reaction answers
  it, or they resolve the thread, so the answer stays on their list even where the
  decision it informs is already there. Where you can list the answers, a choice in
  the message usually asks instead ("Ask for a pick").

  Where their reply left a question standing, as when they asked something back or
  the step is still to do, give `--obligation` its id, repeating the flag for each
  such question. Their reply took the question off On Me whatever it said;
  `--obligation <id>` returns the same item there, standing on this message, until
  their next reply, so a plan step naming it reads open again. Anything more you need
  from them, even on the same subject, is a new question and takes no id.

- `--todo "<what you owe>"`: yours. It promises work it does not deliver, and opens
  that to-do on the thread under the reply's id until `leaf task end <page> <reply-id>`
  ([Long-running work](conversation-loop.md#long-running-work)). A later `--done` on
  the same reference posts its reply in the thread, and Leaf names the to-do still
  open for `leaf task end`.

  Where the work can't start until something you don't control happens, such as the
  user's pick elsewhere on the page or another change landing, add
  `--waiting-on "<what>"`, naming it in a few words as the user knows it. Each
  delivery from the page lists the to-do under `held`, so you meet it again when
  input that may end its wait arrives ([event batches](event-batches.md)).

- `--done`: nobody's. It delivers what the message asked for and leaves the user
  nothing to decide.

```bash
leaf thread reply <answer.ref> --obligation --text "How long must exports be kept?"
leaf thread reply <answer.ref> --todo "Rebuild the banner quieter" --text "Rebuilding it; it lands in v4."
leaf thread reply <answer.ref> --todo "Redo the card's top line" --waiting-on "Whose Words" --text "Held until Whose Words lands, since the top line depends on it."
```

The answer's head shows what it leaves: **Waiting on me** while its question is open,
and **Still to do**, or **Waiting on <what>**, until you start or end the to-do. A
promise declared `--done` reads as finished work.

### Ask for a pick

When a message asks the user to choose among answers you can list, such as which of two
ways to proceed, whether to take an action or whether a step they took worked, you can
send the answers in the message in a widget that asks, such as an `<lf-options id="…">`
holding an `<lf-option id="…">` for each. Picking an option is generally quicker and
easier for the user than typing a reply, so a choice usually serves them better than
answers listed in words. The user answers with a press in the thread, and the choice
waits on them until they do, so the message takes no `--obligation`: beside the choice
it would keep the message on their On Me list after they pick, as the command notes.
The text holds the question, what is true of every option and your
reason; each card holds what is true of its option alone, such as what choosing it
does and costs. The choice needs no heading or group round it. Title each option by
what choosing it does and mark the one you advise (`authoring-on-me.md`, "What a
question holds"). In the titles, as in your text, “I” means you and “you” the user:
“Hold it until you've read it”, not “Hold it for my review”.

```bash
leaf thread reply <answer.ref> <<'EOF'
Which store should own sessions? I'd keep the account store, which already expires them.

<lf-options id="session-store">
<lf-option id="session-store-account" label="Keep the account store" recommended><strong>Keep the account store</strong></lf-option>
<lf-option id="session-store-own" label="Give sessions their own store"><strong>Give sessions their own store</strong> One more service to run.</lf-option>
</lf-options>
EOF
```

If the user answers in words instead, the delivery of their reply lists the question
in `waiting`; once you have answered, resolve the thread as `conversation-loop.md`,
"The On lists", says. Another widget that asks works the same way, such
as an `lf-draft` marked `required` for wording the user edits. A decision the page
records, or one whose evidence needs the column, goes on the page beside its subject
(`authoring-on-me.md`), linked from the reply.

### Progress messages

Use `--ephemeral` for progress while work is underway:

```bash
leaf thread reply <answer.ref> --ephemeral --text "Checking the keyboard route."
```

It does not answer the update, so a turn whose final message is the answer still
posts that message. On an update you owe it starts the update. Posted on the same
reference after an answer that opened a to-do, or on the to-do's own message, it
starts that to-do. Its text becomes your line in Leaf's panel status, so keep it to one line
([conversation loop, "When to write"](conversation-loop.md#when-to-write)). In a
thread that owes no reply, use `leaf thread reply <page> <message> --ephemeral`.

The thread shows your latest progress as one dim working message where you posted
it, and progress never counts as unread. Your next message in the thread replaces it,
progress included, but progress the user has written after stays until your next
reply. Where nothing in the thread before it still waits on your answer, it also goes
when your turn ends.
Progress carries only text;
questions, to-dos, HTML, anchor moves and failure receipts each need a reply of
their own.

A widget that asks in a message keeps its thread at "Your turn" until the
user answers it ("Ask for a pick"). A thread you open waits on nobody by itself:
`--obligation` registers the message's request without a widget.

Correct a message you or an earlier agent wrote, without adding a turn:

```bash
leaf thread edit <page> <message> --text "Corrected wording."
```

The page labels it `edited`, and the log keeps every wording. An edit may change the
message's HTML too. An answer the user gave a widget in it stays with the widget's
ids, and shows on whatever the edit leaves under them.

While your reply is still the thread's latest message and the user hasn't answered
it, a correction to it, or a later finding of yours that changes its answer, goes
into that reply with `leaf thread edit` rather than a new reply, so the user returns
to the current answer rather than to messages that correct one another. Keep new
replies for news the user is waiting on, such as a result you promised, and for
answering a delivered update, which an edit does not answer. Where you already
posted such a correction as a new reply, fold it and the reply it corrects under one
summary that gives the answer as it now stands, as short as any summary ("Summarize a
long discussion"): `leaf thread summarize <page> --from <earlier-reply> --through
<correction> --text "<the current answer>"`.

An ordinary reply leaves the thread open, or reopens one you resolved, so the user can
inspect the answer; the user usually resolves it. Resolve a thread yourself only when
the user asks, when an event's `handling` says to, when its question was settled
elsewhere (`conversation-loop.md`, "The On lists"), or when no review or follow-up could
change the outcome, which finishing the work does not show by itself. When unsure, leave
it open. First answer any unanswered user message in it:

```bash
leaf thread resolve <page> <message>
```

A thread the user resolved is one they are done with. Resolving takes it off their
list and takes back nothing they asked there, so your answer, or a result you
promised, goes into the closed thread with nothing on their list to announce it; the
record `leaf thread reply` prints says so. Bringing the thread back is your call:

```bash
leaf thread reopen <page> <message>
```

Reopen it, before or after your message, for news they would want to stop and read,
such as that you could not do what they asked, or a result that changes something they
rely on. Leave it closed where your message only delivers what they asked for. A
question to them there, in words or as a pick, reopens it by itself.

## What the user has read

Each thread in `leaf page state <page>` and `leaf page state <page> <message>`
lists under `unread` your messages the user has not read in their current wording. A
message counts as read once its whole body, or the whole of a summary folding it, has
been on screen, once the user marks the thread read, or once they act in the thread
after it: reply, react, answer a widget, resolve or reopen. `leaf thread edit` makes a message unread again. Unread
does not change whose turn it is: an unread message needs no follow-up, and a read
one is not an answer.

## Summarize a long discussion

When a thread's topic has moved on, or settled detail buries the current exchange,
summarize the earlier discussion as part of answering new input, without waiting to
be asked. New input may carry `summary_hint`, a suggested range. Read the originals
with `leaf page state <page> <message>` and choose a contiguous range yourself,
starting and ending on spoken messages rather than reactions.

Fold what compresses most: settled detail and finished exchanges, whose outcome a
few sentences carry. Keep in full the messages whose wording still matters
to the current exchange, such as the question a kept answer replies to, or an opening
message whose words still frame the thread. A folded message that still asks
something of the user stays on their On Me list, and going to it there opens the
fold; where they need its words or its widget to answer, keep it in full or say in
the summary what it asks. A range may take in summaries already in the thread, and
the new summary replaces every one it overlaps, whole. Take them in, as the hint does, so the user reads one
account of the earlier discussion rather than a row of summaries.

A summary is what the user reads in place of the messages it folds, and they open
those only for detail, so a summary helps only when it is much shorter than they are:
a few sentences, usually under sixty words, saying where the range landed. Give each
decision with its reason in a clause, the answer that now stands where a later
message corrected an earlier one, and what is still open. Write it from the original
messages rather than only from the summaries it replaces, and leave the steps that led
there, and the detail, to the originals.

Put the range's outcomes in the page too, and write the summary:

```bash
leaf thread summarize <page> --from <first-message-id> --through <last-message-id> --file summary.md
```

The summary replaces the range in the thread, and the originals stay available to
unfold. It answers nothing. A recap in an ordinary reply folds nothing.

To fold messages
without a summary, pass an empty `--text`:

```bash
leaf thread summarize <page> --from <first-message-id> --through <last-message-id> --text ''
```

Either form takes `--label <name>` where the range has a name worth giving it; the
thread shows the name in bold ahead of the summary's words.

A summary stands as written when a message it folds is rewritten or taken back, by
the user or by you, so summarize the range again where the change alters what the
summary reports. A delivery's `summaries` list the messages each one folds, and
`thread edit` names the summary over a message you edit.
