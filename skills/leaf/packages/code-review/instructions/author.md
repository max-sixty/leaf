This package supplies no widgets; select the evidence packages the review needs
alongside it. These suggestions help a user judge a code change, with the page's
form left to the author.

Lead with the review finding, the behavior that changes, and any unresolved
risks. Identify the revision reviewed and distinguish the change author's
description from your assessment. Keep the evidence needed to judge each claim
near it, with the full patch and supporting detail available on demand.

When control flow or ownership changes, consider a behavior diagram that shows
the difference. Keep shared steps recognizable and label additions, removals,
and changed relationships. Changes in one drawing or a matched before/after pair
can make the comparison readable without reconstructing two unrelated diagrams.

Choose evidence for the question: `diagram` for behavior or structure, and `diff`
for the exact patch and its call-tree diff. Compose a pull-request brief with
native headings, tables and disclosures: identify the repository, reviewed
revision, author, checks and source link. Bind external evidence through a
page-owned data adapter when it must refresh. Standard code, table, and disclosure
elements can carry a focused invariant, test result, or remaining uncertainty.
Use an Ask when a specific decision is owed.
