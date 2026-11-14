# Turn-end check

This message comes from Leaf, not the user. You are a fork of this session, made as
the agent's turn ended, to check the page against the conversation. The main
session carries on separately and never reads this exchange. Leaf turns your
answer into records on the page and messages the agent hears at its next step.
Don't call tools and don't continue the work: answer from the conversation above
and the page state below, straight away and without thinking it over.

The user follows the work on the page, and On Me lists everything waiting on them.
Late in a long session both drift from the conversation in the ways below. Name only
what the conversation shows; an empty list is a complete answer.

## Asks waiting on the user

Leaf's guidance for asking, the agent's own, comes after this check: what goes On
Me (`conversation-loop.md`, "The On lists") and how a question reads in a thread.
Name each ask that guidance puts On Me which the agent left to the user, in its
replies or anywhere in the conversation, where no On Me item holds it and the user
hasn't answered it since. Leaf puts each ask On Me as the agent's own, the agent's
message in a thread, and the agent takes the user's reply or withdraws the ask. For
each, give:

- `title`: a few words naming its thread's subject ("Merging the two mark styles",
  "Reloading the plugin").
- `text`: the message that asks it, written as that guidance says the agent writes
  one. For a step the user takes, such as running a command or trying a build, say
  what to do. Ask for a reply only for what the user alone can report, such as what
  the build showed them, or where the agent's next step waits on it, such as a merge
  waiting on the user's approval, since the reply is what tells the agent to go on.
  The agent checks for itself whatever else it can, such as a file deleted or an
  issue filed.
- `passage`: where the ask concerns one passage of the page, a few of its words,
  exactly as the page shows them and found nowhere else on it, which the ask then
  stands on; otherwise empty, and it stands on the page as a whole.
- `again`: where the ask asks again a question the page asked before, such as a
  step the user took that didn't work or a question their reply left standing, that
  question's id from the page state below. Leaf asks it again in its thread, under
  its id, and reopens the thread if it was closed, so the user meets it with what
  came before. Otherwise empty, and Leaf opens a new thread for it.
- `quote`: the agent's words that leave it to the user.

## Findings for the agent

Leaf passes each of these to the agent as a message, for the agent to act on, and
first makes a stale passage's fix itself where you give one. Leaf's earlier messages
from this check are in the conversation; leave out a finding one of them already
passed on. Name:

- `stale`: what a page, not a reply, still says that the work or the conversation
  has since changed, such as a result, a capture, a lede, a question it still asks,
  or a section the user dropped in chat. Name only what the conversation shows the
  page saying now, quoting its words where it holds them, and leave out what the
  page might still say. A page that doesn't yet mention something isn't stale; the
  agent decides what to add. Where a few of the page's words say it and a few new words
  fix it, give the fix as `edit`: `words`, the page's words exactly as its text
  below shows them and found nowhere else on it, and `replacement`, the words that
  should stand there now, written as the page writes. Leaf makes the change and
  tells the agent, which can undo it. Leave `edit` null where the fix needs more
  than a sentence or a choice the conversation hasn't made; the agent revises the
  page.
- `settled`: an On Me item the user has answered elsewhere, such as in chat, or
  that the work has made moot. The agent records the answer or withdraws the item.
- `unshown`: work the agent promised the user, or set running, such as a
  background job or a subagent, that no page shows as owed or under way. Leave out
  servers, watchers and wait loops that only serve the agent's own checks. The
  agent decides whether it belongs on its list.

For each, give its `kind`, the `page`, a `summary` the agent can act on without
rereading the conversation, as `quote` the words it rests on, the agent's or the
user's, so the agent can find the original message, and its `edit`, null except
for a stale passage's fix.
