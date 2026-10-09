---
origin: Codex 01a0f8ce-7246-7912-9922-e0bd42ae3097, PR 1516
validation: Original 0/3 and revised 3/3 on the full browser contract, with identical case text
drop: ^SHIP\b
keep: ^REVISE\b
keep: (padding|geometry|position|size)
---
The user asked: "code blocks should have a copy button, on their right, probably Web Awesome's? implement and merge."
The initial implementation used an absolutely positioned button anchored inside the upper right of each code frame. Long first lines could run beneath it. The reviewer added a browser assertion requiring buttonBottom <= firstSourceLineTop. The final implementation keeps the button absolutely positioned and adds top padding equal to its 32px height to each code block. The theme reserves this space before first paint. Code lines move down 32px relative to the merge base and each block becomes 32px taller. There is no motion during startup, hover or click. Clipboard, focus, touch, and render gates pass. Before/after screenshots show a new blank strip above the code with the button at its right edge. The previous agent wrote: "Its reserved row keeps it clear of source text." Review whether this implementation is ready to ship.
