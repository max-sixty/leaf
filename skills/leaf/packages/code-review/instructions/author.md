This package has no widgets. Select it together with the packages for the evidence the
review needs: `diagram` for behavior or structure, and `diff` for the exact patch and
its call-tree diff.

Lead with the finding, the behavior that changes, and any unresolved risks. Name the
revision you reviewed, and keep the change author's description apart from your own
assessment. Put the evidence for each claim beside it, with the full patch and
supporting detail a click away.

When control flow or ownership changes, consider a diagram of the behavior that shows
the difference: one drawing with what is added, removed or reconnected marked, or a
matched before and after pair, keeping the shared steps recognizable.

Write the pull-request brief with native headings, tables and disclosures, naming the
repository, reviewed revision, author, checks and source link. Bind evidence through a
page-owned data adapter when it must refresh. Put each decision the user owes on On me
(`references/authoring-decisions.md`).
