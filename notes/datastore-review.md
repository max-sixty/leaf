# Datastore review

A review of Leaf's two stores — the event log for user and agent state, and
the per-source files under `data/` for external data — against what Airtable-like pages need: rows a user
adds, cells a user edits, rows a user reorders, and data other processes supply
or read. Measurements used synthetic logs outside the repository; each claim is
marked measured, read (from code), or inferred.

The boundary between the stores is right: typed external values live under `data/`,
decisions live in the log, and the log names values by source and source revision. Neither a
document store (Claude Artifacts' `db`, Firestore) nor a CRDT fits: both drop the
single validating append door, per-event attribution, undo, and `version check`,
and Leaf already has the coordinator a CRDT exists to avoid. SQLite as the authority
would be the derived current-state file `AGENTS.md` rules out.

What is wrong sits below that boundary. Most findings reduce to one missing
identity: a row.

## Row identity

Leaf has three row models and no row primitive:

- `creates` children, whose existence is carried by the `add` action standing at
  the child's own coordinate (`projection.py` `generated_children`). Every later pick
  must repeat the whole additions map (`lf-options.js` header), undoing a pick also
  withdraws the write-in, and the browser builds the children in `lf-options.js`
  rather than generically. One consumer. (read)
- `$data.records` and `x-request.records`: keyed rows of a data source. (read)
- Units that are data keys without saying so: `lf-diff` keys by file path and
  `lf-visual-review` by case id, while `direct_dependencies` treats every unit as an
  element id and `action_rests_on` filters the paths back out. (read)

Proposal:

- A typed unit: `{element: FIELD}` or `{record: FIELD, input: X-DATA-INPUT}`, the form
  `x-request.records` already uses.
- Row existence as one verb, `row`, on its own coordinate `(owner, row, "row")`,
  whose detail carries `exists: bool`: `true` adds the row, `false` removes it, and
  the latest standing `row` action wins because a coordinate is keyed by verb. Undo
  of an adding `row` removes the row; `exists: false` also deletes authored rows. Cell actions on a removed row stay in the log and return if the removal is
  undone. The browser mints the row id so the row draws in the gesture; the door
  refuses an id any revision or earlier adding `row` used.
- The child's element declaration is the record schema, extending the `value`
  record's rule that the detail field carries the attribute's own schema. An adding
  `row` takes `{row, exists: true, fields}`; the door validates authored attributes plus folded state
  plus the patch against the whole declaration. Records only: prose is a body field
  the child declares, so `lf-options`' write-in becomes a `row` of an `lf-option`.
- A `set` verb whose coordinate is keyed per field of a patch (`meaning.coordinates`,
  one `(owner, row, "set", field)` each), so one gesture sets several cells, a paste
  is one undo, and a column needs no verb of its own.
- The runtime materialises created children from the declaration; `generated` goes.

A table then declares:

```json
{
  "lf-table": {
    "x-state": {
      "row": { "unit": { "element": "row" }, "creates": "lf-row" },
      "set": { "unit": { "element": "row" }, "fields": "fields", "record": { "kind": "value" } },
      "rank": { "unit": { "element": "row" }, "record": { "kind": "value", "attr": "rank" } }
    }
  }
}
```

The same unit with `{record, input}` gives a user cell edits on rows an external
process supplies, which today reach only `datum` anchors and requests.

## Request staleness

A request's stale-press check compares the source's revision (`requests.py`), so a
refresh of one source voids every in-flight press on every row of it; decide it per
row from the key and `bind`, at the door only (`lf-job-requests.js` repeats it).

## Position

`markup_value` compares only a position record's container, so a reorder within one
container is invisible to `version check`. (read)

## Read cost

A stamped copy of `triage-board` with 10k board moves reads in about 175 ms in the
browser and 275 ms through `leaf page state`; with 1k threads beside the moves, about
220 ms each (best of five, measured). What remains is linear: parsing the log twice
per read, one `state_projection`, and one `build_threads`. An unstamped page whose
source moved since its predecessor also pays `continuity_errors`, which folds threads
three more times. Neither warrants snapshots or incremental folding yet.

## Redundancy

- Stored `meaning` repeats `widget`, `revision`, and `generated`, and
  `stored_meaning_error` asserts it still equals a recomputation: two mechanisms for
  one guarantee. Keep the stored `coordinate`, which registry-free readers need.
- `undo`, `restated`, and a note's `settles` are one relation, "this stops
  standing"; `restated` differs in naming element ids.
- `fragments` is `records` plus one deferred field, declared beside it with an
  agreement rule and four `records or fragments` fallbacks. `records: {items, key,
  deferred?}`.
- About 250 lines of Git patch parsing sit in core `data.py` for the diff package,
  and `data capture --lines` slices text for one contract. Both belong to their
  contracts and packages, leaving one `leaf data set`.
