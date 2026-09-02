# Experiment 47: Inspect the submitted comment in its thread

## Purpose

Repeat experiment 46, opening the canonical Threads panel before asserting the
comment is visible. The direct resource and transport are unchanged. Use a new
page and require new durable event IDs. Finish the CSP and ui/message checks.

Expected result: rendering, choice, and anchored comment pass again; the
reference host accepts ui/message without proving any idle Codex wake.

## Findings

Rendering, keyboard choice, and durable anchored comment passed again. Opening
Threads did not make the comment visible to the observer. The next experiment
keeps the host alive and inspects the actual panel state instead of guessing
another selector. ui/message and network assertions were not reached.
