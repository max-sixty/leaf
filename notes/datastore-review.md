# Datastore review

A review of Leaf's two stores — the event log for reader and agent state, and
`data.json` for external data — against what Airtable-like pages need: rows a reader
adds, cells a reader edits, rows a reader reorders, and data other processes supply
or read. Measurements used synthetic logs outside the repository; each claim is
marked measured, read (from code), or inferred.

The boundary between the stores is right: typed external values live in `data.json`,
decisions live in the log, and the log names values by source and revision. Neither a
document store (Claude Artifacts' `db`, Firestore) nor a CRDT fits: both drop the
single validating append door, per-event attribution, undo, and `version check`,
and Leaf already has the coordinator a CRDT exists to avoid. SQLite as the authority
would be the derived current-state file `AGENTS.md` rules out.

What is wrong sits below that boundary. Most findings reduce to three missing or
conflated identities: a row, a source revision, and a position.

## Row identity

Leaf has three row models and no row primitive:

- `creates` children, whose existence is carried inside whichever action currently
  wins the owner's facet (`projection.py` `generated_children`). Every later pick
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
- Row existence as its own coordinate `(owner, row, exists)`, with competing `add`
  and `remove` verbs. Undo of `add` removes the row; `remove` also deletes authored
  rows. Cell actions on a removed row stay in the log and return if the removal is
  undone. The browser mints the row id so the row draws in the gesture; the door
  refuses an id any revision or earlier `add` used.
- The child's element declaration is the record schema, extending the `value`
  record's rule that the detail field carries the attribute's own schema. `add`
  takes `{row, fields}`; the door validates authored attributes plus folded state
  plus the patch against the whole declaration. Records only: prose is a body field
  the child declares, so `lf-options`' write-in becomes an `add` of an `lf-option`.
- A facet taken from each field of a patch (`meaning.coordinates`), so one gesture
  sets several cells, a paste is one undo, and a column needs no verb of its own.
- The runtime materialises created children from the declaration; `generated` goes.

A table then declares:

```json
{
  "lf-table": {
    "x-state": {
      "add": { "unit": { "element": "row" }, "facet": "exists", "creates": "lf-row" },
      "remove": { "unit": { "element": "row" }, "facet": "exists" },
      "set": { "unit": { "element": "row" }, "facet": { "fields": "fields" }, "record": { "kind": "value" } },
      "rank": { "unit": { "element": "row" }, "facet": "rank", "record": { "kind": "value", "attr": "rank" } }
    }
  }
}
```

The same unit with `{record, input}` gives a reader cell edits on rows an external
process supplies, which today reach only `datum` anchors and requests.

## Source revision

One global counter in `data.json` serves as the store stamp, each source's revision,
and the snapshot id:

- An immutable snapshot fragment is refused as stale when another source moves:
  `data_fragment` checks the global revision before looking up the snapshot
  (`data.py` `data_fragment`; `runtime/data.js` repeats it). Reproduced with a probe;
  `lf-diff` paints a fragment error in that window. (measured)
- `http.py` picks the 409 by matching `" is stale; current revision is "` in the
  message. (read)
- `data_revision` means the global counter in `origin` and `/api/data`, and the
  source's revision in anchors and requests. (read)
- `revisions[]` exists only to answer "was N ever this source's revision". (read)
- Every `/api/state` carries every source's current value and every retained
  snapshot, and every `data set` rewrites all of them. (read)

Proposal: a per-source revision, and values by reference. `data.json` becomes an
index, `{sources: {id: {contract, rev, kept: [rev]}}}`; each value is an immutable file
served at `/api/data/<source>/<rev>`, which cannot go stale, so the 409 disappears.
`/api/state` carries `{source: {contract, rev}}`. A snapshot is a kept rev.
`{source, rev}` is the one reference form everywhere.

A request's stale-press check compares the whole source revision
(`requests.py`), so any refresh voids every in-flight press on every row; decide it
per row from the key and `bind`, at the door only (`lf-job-requests.js` repeats it).

## Position

A `position` record stores an integer sibling index. The fold replays only winning
moves, each splicing at an index measured against a list that included the moves it
dropped, so undoing one card's move can shift another. (inferred; no reproducer yet)
`markup_facet` compares only the container, so a reorder within one container is
invisible to `version check`. (read)

Proposal: order as a `value` facet holding a fractional rank string (Figma's
fractional indexing). Each row's order stands on its own coordinate, undo is exact,
and `version check` compares it like any value. Boards keep the container record and
take the rank in place of `index`. Write the undo reproducer before changing it.

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
- `x-state` and `x-report` declare one shape; `"x-state" if action else "x-report"`
  recurs. One verb declaration with `by: [reader, agent]`.
- `undo`, `restated`, and a note's `settles` are one relation, "this stops
  standing"; `restated` differs in naming element ids.
- `fragments` is `records` plus one deferred field, declared beside it with an
  agreement rule and four `records or fragments` fallbacks. `records: {items, key,
  deferred?}`.
- `label` and `lines` are envelope fields read by two widgets; about 250 lines of Git
  patch parsing sit in core `data.py` for the diff package. Both belong to their
  contracts and packages, with one `leaf data set [--keep]`.
- `working_data_documents` has no callers.

## Other processes

`seq` is already a sync id and `leaf events --after SEQ` the catch-up read. Add
`--follow` on the trigger `/api/news` uses, and state that stored event records are a
public format whose readers drop what they do not recognise.
