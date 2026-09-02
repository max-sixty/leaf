# Experiment 52: Use the probe button's keyboard route

## Purpose

Repeat experiment 51, activating the native ui/message probe button with Enter
instead of a mouse click. This avoids the mouse-scroll ambiguity of its fixed
position inside the auto-height iframe. No Leaf runtime or transport changes.

Expected outcome: all rendering, gesture, message, CSP and network checks pass.
Leave the successful host running for inspection. This proves the reference-host
route only, not Codex's own inline renderer, wake, or compact-layout parity.

## Findings

Rendering, keyboard choice, visible anchored thread, and ui/message passed.
The no-network assertion caught a browser-managed `/icon.svg` request, outside
the fetch adapter: the banner favicon and injected CSS mask still held that
root-relative asset URL. The next build inlines those two icon references too.
This is an actual bundle completeness gap, not a weakened CSP requirement.
