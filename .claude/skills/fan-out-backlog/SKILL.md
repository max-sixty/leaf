---
name: fan-out-backlog
description: Runs a campaign of parallel agents on Leaf's backlog issues while the user is away, each item reviewed and landed, or left as a decision for the user. Use for "fan out the backlog", "grind the backlog", or a batch of agent-ready items when spare tokens are plentiful.
---

# Fanning out the backlog

Turn the backlog items that need no judgment from the user into reviewed,
landed changes, and leave the user only the decisions the work raised. The user's
attention is the scarce resource: they read the results, not the work, so every
PR has to be right without them. Load `/developing-leaf` for repository work.

## When to run one

The maintainer isn't sure a backlog campaign beats doing work as it comes up,
and prefers the latter by default. So run one only when there are many spare
tokens to spend, and not on a schedule or from Tend.

## Choose the items

`TODO.md`, "Backlog", gives the query for the issues an agent can take unattended:
labelled `backlog`, not `waits-on-user`, and claimed by no pull request. Small
items batch well; a large item whose design is settled suits one agent for the
whole run.

Before dispatching an item, establish that it is still live and its premise
true, by running something: a probe, the test it names, a reproduction.
A premise checked by reading the code is a guess, and those guesses were wrong
for 3 of 10 items in one run, while every premise checked by running was right.
Check also that no open PR, other session or other campaign already works on the
item (`gh pr list`, `claude agents`, `wt list`): an unlinked PR is invisible to the
query. In one run two campaigns on the same list duplicated four PRs, and other
sessions landed two more of its items on main mid-run.

## Run the agents

Give each item one agent in its own worktree (`isolation: "worktree"`), briefed
with [`references/brief.md`](references/brief.md) and a paragraph of its own:
the issue number and text, what the pre-check found, and what a finished result
shows. The brief says how; the paragraph says what. An item that changes shipped
instructions also names the eval cases to score, with a paired `--base` arm
(`/developing-leaf`, "Score an instruction change"): an unpaired comparison
against an earlier run once showed a sentence lifting a case from 1/7 to 8/8,
when paired, main alone reached 3/4.

Claude Code runs at most 20 subagents at once, and 20 agents drove an 18-core
Mac's load to 20–58, which made wall-clock benchmarks useless. Run performance
items on a quiet host or measure CPU time, and queue the rest as slots free.

Keep a ledger in `.tmp/` with each agent's item, outcome, PR, cost and the
`friction` its report lists. Friction that recurs is the run's own finding: fix
it in the repository or tooling when it's yours, add it to the brief when it is
how the run works, and report the rest.

Take the counts you report from GitHub
(`gh pr list --state all --limit 300 --search "head:grind/"`), not from the
ledger or your memory of the run: a run this long compacts several times, and
counts carried across a compaction drift.

## Review every PR

Give each PR an independent reviewer in its own worktree, briefed with the PR
and what to check, not with the author's conclusions, and told to verify by
running and to weigh what the change adds (`/developing-leaf`, "Weigh what a
change adds"). In one run 22 of 55 PRs had a substantive defect: a regression, a
false central claim, a red test, or lost input, and reviewers who checked
correctness alone passed every addition the user later cut.

Send the findings back to the author with `SendMessage`, since it holds the
context to fix them in minutes, and review every fix again: an unreviewed fix in
that run broke the eval comparison arms.

When main moves under a PR, have its author merge main in, take what main
landed, and re-measure what the PR still changes.

## Land as you go

Once a PR's review and the reviews of its fixes pass, mark it ready
(`gh pr ready`). Tend then reviews and lands it under `running-tend`'s
**Landing**, which reserves some changes, such as agent instructions, for the
maintainer; send Tend's findings to the author as above. Drafts held for the
user in one run waited 50 hours at the median while main took 297 commits;
other sessions fixed 6 of 47 first, and the user then landed the rest with one
choice.

A PR stays a draft, with its decision on the user's page, when it leaves a call
for the user, or when it adds something beyond the repair and the test that
protects it that later changes must keep working with: a new mechanism, gate,
public option, dependency or protocol bump. The author lists these under `adds`
in its report, and the reviewer checks the list.

Mark PRs ready as their reviews finish rather than all at once: each ready PR
starts Tend runs, which share one GitHub API quota that six agents landing in
parallel once used up.

## Hand over

Put the results on a Leaf page: what landed, grouped so the user can read by
theme, the measurements that show it, the PRs still open and why, and what you
learned about running the campaign. Register each decision a PR leaves
to the user on their On me list, including calls an agent made that they may
reverse. An agent's report names its calls for a reader who knows the PR, and the
user hasn't opened it, so each decision says what the user sees today, what the PR
changes, and what choosing each option leads to, with a picture of each result for a UI
call (`/developing-leaf`, "Choose what the user reviews"). A campaign that found nothing to
change in an item reports that as a result.
