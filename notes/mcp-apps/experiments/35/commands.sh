#!/bin/bash
set -e
cd "$(git rev-parse --show-toplevel)"

# Use a fresh slot: preview replaces an existing slot's disposable page.
test ! -e .tmp/previews/codex-full
uv run python scripts/preview.py ship-review --slot codex-full --background
bin/leaf status .tmp/previews/codex-full working 'Testing the full Codex browser and feedback loop'
bin/leaf codex start .tmp/previews/codex-full

# Open the exact printed URL through Codex's open_in_codex browser target.
# Browser interactions are recorded in browser.js and this task's tool trace.
# Inspect events after the gestures:
# bin/leaf events .tmp/previews/codex-full
# After the delivery starts a later turn, carry the selected option as `chosen`
# and add the test-result note shown in README.md. Then:
# bin/leaf version check .tmp/previews/codex-full --render
# bin/leaf version stamp .tmp/previews/codex-full --text 'Codex smoke: carry the queued keyboard choice and record its return'
# After the comment's delivery, update the test-result note, then:
# bin/leaf version check .tmp/previews/codex-full
# bin/leaf reply .tmp/previews/codex-full --to 8dec5efbdfc8fe3869338ea2f66d16c2 --text 'Confirmed: this anchored comment started a new turn in the same Codex task. The test-result note is on the page, and the review choice is unchanged.'
# bin/leaf version stamp .tmp/previews/codex-full --text 'Codex smoke: anchored comment returned and answered in the same page'
# bin/leaf status .tmp/previews/codex-full waiting 'Select text to comment or try the option controls'
