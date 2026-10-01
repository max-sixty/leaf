# Datastore review

This note considers editable table rows and externally supplied records. The current
storage contract is [page-storage.md](../skills/leaf/scripts/leaf/page-storage.md):
authored markup supplies initial values, the event log records user and agent changes,
and `data/` holds external values. A row feature should use those owners.

## Current capabilities

A creating action gives its child a separate state key: owner widget, child id, and
verb. `lf-options` sends `add`, then an ordinary `choose`; changing or undoing the
pick leaves the added option in place. `projection.generated_children` supplies the
children to file readers, while `lf-options-addition.js` materializes option nodes in
the browser. The registry limits a creating action to the child's id and words; it
cannot yet create a record with several fields.

Position records preserve both the container and the gap between units. The
`recorded_state` reading compares the container and nearest preceding unit shared by
both documents, so `page check` detects a same-container reorder that contradicts the
user's move. `tests/test_interact_document.py` exercises both that case and later
revisions that must retain the recorded order.

Some state units identify external records rather than elements: `lf-diff` uses file
paths and `lf-visual-review` uses case ids. Their declarations name a detail field as
the unit, without declaring which source owns that record. `direct_dependencies`
includes the unit among identities; `action_rests_on` retains identities contained by
the owner. A typed record unit remains a possible way to state that distinction.

## Remaining proposal

Before extending the protocol, build a concrete table task that needs editable rows.
Use it to test these requirements:

- Identify a state unit as an authored element or a record in a declared data input.
  A possible declaration is `{element: FIELD}` or
  `{record: FIELD, input: X-DATA-INPUT}`; this is a proposal, not accepted registry syntax.
- Add or remove a row independently of its cell values. Undoing a removal should
  restore the row and its earlier edits; removing an authored row needs an explicit
  action as well.
- Create a row from fields validated against its declaration, and materialize it
  through one shared runtime path.
- Let one gesture change several cells while each field retains its own state key.
  A pasted patch should be withdrawn by one undo.
- Give edits to externally supplied rows a declared source and record identity.
  Test how those edits behave when the external source changes.

An `exists` value on a row action and a per-field `set` action are candidate designs.
The first task should establish whether these fit the existing action model before
introducing new verbs, a record schema, or a generic child renderer.
