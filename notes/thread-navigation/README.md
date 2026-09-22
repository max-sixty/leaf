# Threads accordion playground

Accordion is the chosen interaction. The current page explores spacing: Compact
(32px rows), Comfortable (40px), and Airy (48px), plus panel and roomy reading widths.
Author labels sit above messages; the reply field spans the conversation width. One header carries topic, count, and status;
there is no repeated status bar inside. Draft markers, a one-line composer, disclosure
chevrons, and title/Escape collapse keep the dense layout operable.

Click a title, type a draft, change spacing, and collapse the thread from its title (or
press Escape).
Simulated replies stay local to the sketch; only Choose layout submits a configuration
to the agent. Cmd/Ctrl+Enter adds a simulated reply. Refresh resets the simulations.
The real Leaf Threads panel implements the compact accordion and remains available
for feedback independently of the sketch. Counts use a shared column across all rows.
Use Enter/Space on a title, arrows or Home/End between titles, t/Shift+t to walk
threads, and c to reply. In the real Threads panel, Escape leaves an inner reply
or narrowing interaction first, then closes the whole surface from either a title
or conversation. The page-local sketch still uses Escape to collapse its selected
mock conversation.

```sh
scripts/preview.py --source notes/thread-navigation/playground.html --slot thread-navigation --reader --background
```

The companion log and `threads.json` supply the release discussion fixture and its
anchors. The runtime uses the selected compact accordion; the page-local sketch keeps
spacing alternatives available for design discussion. Its illustrative activity labels
are separate from the runtime's existing delivery readings.
