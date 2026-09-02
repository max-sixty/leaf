# Experiment 48: Inspect the live direct resource

## Purpose

Reopen experiment 47's saved page in the reference host, keeping both servers
alive for browser inspection. No new gesture is claimed from its existing log.
Check that the choice replays and inspect why the submitted comment is hidden.
Then test the reference host's ui/message result independently of Codex wake.

Expected outcome: either the native Threads interaction reveals the comment,
or the live UI and console identify a missing transport dependency.

## Findings

The reopened app replayed Redis as selected. Its real Threads button revealed
the saved anchored comment, including its Sent receipt. Screenshot `results/comment.png`
shows the canonical runtime and thread panel in Codex's browser pane, hosting
the official reference host (not Codex's built-in inline MCP renderer).

The test button sent ui/message successfully; the host showed one new user
message with marker `leaf-direct-message-2d8cebef-50b3-41ca-8801-1f52f7e7e4f5`.
The resource reported presented=1, contained zero child iframes, and its sandbox
declared empty connect, resource, and frame domain lists. Browser error/warning
log was empty. No agent wake was tested.

The reason the automated observer lost its open panel was not established here.
Experiment 50 later identified the asynchronous post-send inline landing.
