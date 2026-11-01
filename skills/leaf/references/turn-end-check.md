# Turn-end check

This message comes from Leaf, not the user. You are a fork of this session, made as
the agent's turn ended, to check the page against the conversation. The main
session carries on separately and never reads this exchange. Leaf turns your
answer into records on the page and messages the agent hears at its next step.
Don't call tools and don't continue the work: answer from the conversation above
and the page state below.

The user follows the work on the page, and On me lists everything waiting on them.
Late in a long session both drift from the conversation in the ways below. Name only
what the conversation shows; an empty list is a complete answer.

## Asks waiting on the user

Leaf's rule for what goes On me, the one the agent follows (`conversation-loop.md`,
"The On lists"), comes after this check. Name each ask that rule puts On me which
the agent left to the user, in its replies or anywhere in the conversation, where
no On me item holds it and the user hasn't answered it since. Leaf puts each
ask On me as the agent's own, a question in a new thread and a step as a to-do,
and the agent takes the user's answer or withdraws the ask. For each, give:

- `kind`: `step` for an action the user takes and then confirms with Done, such as
  running a command or trying a build; `question` for anything they answer, decide
  or permit.
- `title`: for a question, a few words naming its thread's subject ("Merging the
  two mark styles"); for a step, the action itself, whole, since it is the only
  text the user reads of it ("Run /reload-plugins in this Claude session").
- `text`: for a question, the message that asks it, as the agent would write it.
  The user reads it on the page, perhaps days later and without the chat, so say
  what is waiting, why it arises and what each answer leads to, naming things as
  the page does, and end with the question. It shows in a narrow card, so keep it
  to at most four short sentences of Markdown, and link a pull request or commit
  by its URL where the conversation gives one. For a step, leave it empty.
- `passage`: where the ask concerns one passage of the page, a few of its words,
  exactly as the page shows them and found nowhere else on it, which the ask then
  stands on; otherwise empty, and it stands on the page as a whole.
- `quote`: the agent's words that leave it to the user.

## Findings for the agent

Leaf passes each of these to the agent as a message, for the agent to act on, and
first makes a stale passage's fix itself where you give one. Name:

- `stale`: what a page, not a reply, still says that the work or the conversation
  has since changed, such as a result, a capture, a lede, a question it still asks,
  or a section the user dropped in chat. Name only what the conversation shows the
  page saying now, quoting its words where it holds them, and leave out what the
  page might still say. Where a few of the page's words say it and a few new words
  fix it, give the fix as `edit`: `words`, the page's words exactly as its text
  below shows them and found nowhere else on it, and `replacement`, the words that
  should stand there now, written as the page writes. Leaf makes the change and
  tells the agent, which can undo it. Leave `edit` null where the fix needs more
  than a sentence or a choice the conversation hasn't made; the agent revises the
  page.
- `settled`: an On me item the user has answered elsewhere, such as in chat, or
  that the work has made moot. The agent records the answer or withdraws the item.
- `unshown`: work the agent promised the user, or set running, such as a
  background job or a subagent, that no page shows as owed or under way. Leave out
  servers, watchers and wait loops that only serve the agent's own checks. The
  agent decides whether it belongs on its list.

For each, give its `kind`, the `page`, a `summary` the agent can act on without
rereading the conversation, as `quote` the words it rests on, the agent's or the
user's, so the agent can find the original message, and its `edit`, null except
for a stale passage's fix.
