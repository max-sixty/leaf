"""The tests whose pages still make a layout shift `shift_watch.js` fails, each a defect
waiting on its fix, by the report it keeps (`render_harness.clean_browser`).

Fixing a defect deletes its lines. A test joins only as a defect to fix, never as
behavior to keep (`tests/AGENTS.md`, "Consume a browser error where it is caused")."""

UNASKED = " moved without input"

KNOWN_SHIFTS = {}
