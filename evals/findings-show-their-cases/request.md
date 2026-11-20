The user's standing instructions, from their CLAUDE.md, include: "Reading what you
hand him takes his time too. To him a page of 3,000 words is a long one, however much
work lies behind it. On a page, draw a design rather than describing it, and count the
words the page shows on arrival before you hand it over."

You are working on Leaf with its maintainer, the user. At the end of each agent turn,
Leaf's turn-end check asks a fork of the session what the user should be asked, and
the fork posts each such question as an ask in a thread: a short Markdown message,
often ending in option cards (`lf-options`) the user presses. An eval judge faults an
ask on two form rules:

- A. The question stands on its own line, in a paragraph of its own, rather than
  sharing a paragraph with the facts or advice around it.
- B. When the ask carries option cards, its words leave what each option does to the
  cards, rather than going through each option again.

In the eval, the `ask-question` case broke these rules 6 times in 8 when the fork was
replayed under the user's interactive Claude Code system prompt, and 2 times in 7 under
the headless `claude -p` prompt (p = 0.13). Rule A reached the turn-end check's prompt
on `main` with #6502 at 10:04 PT on 19 November, and rule B with #6536 and #6545 by
14:54 PT.

The user asked: "is this only the eval, or do my real sessions' forks write asks like
this too?" You sent a worker to read the forks' asks on the user's real pages. It
reported:

> Live forks write the same form. Of the 24 newest fork-posted choice asks (all from
> interactive `cli` sessions), 15 break rule A or B. Most of those 24 were written
> before either rule was in Leaf's turn-end check prompt.
>
> **Counts.** The forks posted 83 asks since 2026-11-16 21:00Z: 79 choices and 4
> words-only. Of the 24 newest choices:
>
> - **Fails A:** 14. Eight put the question in a paragraph with its facts; four
>   (`3bf598fd`, `e3d07595`, `be083ef9`, `20b90cf1`) add only one advice or aside
>   sentence; two (`a277c981`, `3402d5d0`) ask no question at all.
> - **Fails B:** 5, all from 11-19 08:03Z or earlier. Three are clear (`a277c981`,
>   `3402d5d0`, `2b6691bc`) and two borderline (`777a43e6`, `7767205c`).
> - **Fails either:** 15 of 24.
>
> **Failing asks (page, event id)**
>
> - fork-messages: `8d23a17a`, `777a43e6`, `7767205c`, `465fc747`
> - card-rewritten-quote: `3bf598fd`
> - gh-needs-me: `e3d07595`, `a277c981`
> - draft-dot-page-dir: `e82c7594`, `d6cd64f5`, `0146706b`, `2b6691bc`
> - fork-roadmap: `c56a44b5`
> - compact-when-done-release: `be083ef9`, `20b90cf1`
> - panel-status-whole: `3402d5d0`
>
> **Which prompt they ran under.** Rule A reached the prompt on `main` with #6502 at
> 11-19 18:04Z, and rule B with #6536 and #6545 between 22:22 and 22:54Z. Of the 7 asks
> written after both landed, 3 fail A and none fail B. I didn't pin which plugin
> version each session's hook actually ran, and sessions keep the plugin they loaded at
> start. So this is a timing split, not a confirmed version split.
>
> **Examples**
>
> - Pass (`60dc97a0`): facts paragraph, then "Shall I merge it?" alone on its own line.
> - Fail A (`8d23a17a`, 11-20 05:45Z): "Should I merge PR #6574 once its rework passes
>   its eval and journey? The rework deletes Leaf's heavy fork and has the main session
>   judge every thread message…"
>
> 24 asks is enough to answer yes, but only 7 came after both rules landed, which is
> too few to compare closely with the eval's 6 of 8 and 2 of 7. The extracted asks are
> in `fork-asks/choice24.json`: each ask's page, event id, time, title and full text,
> newest first.

Write a Leaf page that answers the user's question and asks whether you should take
on the fix: reword the turn-end check's guidance on an ask's form, and score it on
`ask-question` under the live prefix, base beside head, for about $5.
