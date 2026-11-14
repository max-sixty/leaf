# Preview a page

`uv run leaf-dev preview <example>` serves a live page that follows source and browser-runtime
edits at one URL; `--source <file>` serves any HTML file. Its module header
(`dev/leaf_dev/commands/preview.py`) covers slots, restarts and which previews detach.
Start one that stays in the foreground as a long-running command (`run_in_background`
in Claude Code).

Python, schema and dependency edits require restarting the preview; its log says when.
For a user preview, stop its page server and rerun the same preview command to keep its
URL and comments. A plain preview starts fresh on restart.

Drive only plain previews, since every click this session drives on a `--user`
preview arrives as an unanswered update, and start a `--user` preview only from the
session the user talks to. Don't close a preview to quiet the loop; `page close` ends
the agent's side of the page, which the panel shows as Page closed.

For finite checks, prefer `leaf-dev probe` or `stills`, which close their servers when
they finish. Serve a scratch or repro page only with those or a plain `leaf-dev preview
--source`, never `bin/leaf server start` or `page claim`, which bind the page to the
session running them (a subagent's parent), whose turn-end checks and On me list then
fill with its asks. Serve the smallest fixture that keeps the journey and its
surroundings. Separate page directories keep reviewers' comments apart, and fresh
browser contexts keep browser storage apart, without another browser or Python
process. Close a browser session you opened when you finish with it; a custom runner
closes its servers and browsers on success, failure and cancellation. Previews and
trace viewers handed to the user keep running for their review.

In Codex, start the preview with `--user` from the current chat, which connects the
page to this chat before printing the URL. Open the printed URL with the section's
fragment through `mcp__codex_app__open_in_codex` as a browser target with
`placement: "right"`, and tell the user to comment on the page to steer this chat.
Comments inside a live sample stay in that sample.
