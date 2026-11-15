# Checks and guidance for the authoring agent

## Leave taste to the authoring agent

Code enforces only what Leaf needs to work: a contract between modules, or a guarantee
the user relies on, such as a gesture being recorded or a field staying still as the
user types in it (`browser/AGENTS.md`, "The page holds still under the user's aim"). Taste goes
in the shipped instructions as a
goal with its reason, so the authoring agent weighs it against its own page. A CSS
rule, validator or Layout that fixes how many tiles share a row overrides every page
that needs another number. A check may report what it sees, as the render check names
where a tile row wraps, and leave the decision to the agent.

`page check` and its render checks enforce Leaf's page contracts: they report widget
initialization failures and unintended clipping of content or controls.
A rare authoring mistake costs one fix, or a clearer line in the instruction the agent
misread, so prefer widening a general check to adding one for a particular mistake.
Add a narrow check, or a note a command prints, only where agents get something wrong
on real pages and fix it when told. Before adding one, estimate its precision (the
share of firings that were needed) and recall (the share of the failure's occurrences
it catches) on real pages and sessions, not only on the failure that prompted it, and
weigh them with what a missed failure costs.

## When to pass guidance back to the authoring agent

Pass guidance back when it helps the author improve the user's result, weighed against
the interruption and the cost of another rule (root `AGENTS.md`, "Leaf's role"). First
ask whether Leaf should provide the behavior itself, so the author needn't work around
incidental markup restrictions.

Refuse input only when proceeding would break a guarantee, and say how to fix it where
the author can act. Use the owning parser or validator rather than repeating its rules,
and let its message reach the author: `patch_manifest.py` stores a patch as given, and
`lf-diff` reports a file it can't draw with `reportFailure`. A reader's current
limitation alone doesn't justify a restriction. Where the author must judge the
evidence, report the observation without making it a requirement, and say what was
checked and what was not. When a markup contract changes, update its reader,
validation, dependent layout rules and instructions together.

Data passed between Leaf modules over a channel only Leaf can write needs no input
validation. This includes the server's answer to the browser and the build manifest
the Worker reads. The reader uses that data directly, and the producer's tests verify
its shape. Data a person or agent can modify is input, even when Leaf code sent it:
a request the browser posts, a file an agent edits, or the answer from leaf.page's
container, where a visitor directs the agent.
